"""Stage D: train the FULL joint model — tags + trees + lemmas on one encoder.

The Stage C JointParser with its lemma head enabled: a word-level classifier over
**edit scripts** (Chrupała edit trees, reusing aegean.greek.lemmatizer's pure-Python
build/apply), so lemmatization is context-sensitive (the encoder disambiguates
homographs by sentence) with no autoregressive decoding. The dev evaluation reports
the lemma **compositions** with the train-only lookup, so the final test run can use
whichever the dev data prefers:

  neural-only    apply the predicted script; identity on failure
  lookup-first   (form|UPOS) lookup → form lookup → neural → lowercase lookup → identity
  neural-first   neural → lookups → identity
  unseen-neural  form lookup if the form was seen in training, else neural (the shipped
                 hybrid's shape, leakage-clean)

Loss = Σ tagging CE + arc CE + relation CE + script CE. Selection on dev (LAS + best
lemma composition)/2. Output: model/ (state_dict + labels.json + tokenizer + the
lookup/scripts copied in — everything Stage E exports) and metrics.json.

Usage (after build_full_dataset.py):
    python training/train_full.py --model bowphs/GreBerta
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).parent))
from train_parser import TAG_HEADS, JointParser  # noqa: E402

from aegean.greek.lemmatizer import apply_tree  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def encode(example: dict, tokenizer, maps: dict[str, dict[str, int]], max_len: int) -> dict:
    enc = tokenizer(example["tokens"], is_split_into_words=True, truncation=True,
                    max_length=max_len)
    word_ids = enc.word_ids()
    out = {k: enc[k] for k in ("input_ids", "attention_mask")}
    tag_labels: dict[str, list[int]] = {h: [] for h in TAG_HEADS}
    word_pos: list[int] = []
    kept: list[int] = []
    prev = None
    for si, wid in enumerate(word_ids):
        first = wid is not None and wid != prev
        tag_labels["upos"].append(maps["upos"][example["upos"][wid]] if first else -100)
        for i in range(9):
            tag_labels[f"x{i}"].append(maps[f"x{i}"][example["xpos"][wid][i]] if first else -100)
        if first:
            word_pos.append(si)
            kept.append(wid)
        prev = wid
    for h in TAG_HEADS:
        out[f"labels_{h}"] = tag_labels[h]
    out["word_pos"] = word_pos
    old2new = {w: i for i, w in enumerate(kept)}
    heads, rels, scripts = [], [], []
    for w in kept:
        g = example["head"][w]
        if g == 0:
            heads.append(0)
        else:
            heads.append(old2new[g - 1] + 1 if (g - 1) in old2new else -100)
        rels.append(maps["deprel"][example["deprel"][w]])
        scripts.append(example["script"][w])
    out["arc_heads"] = heads
    out["arc_rels"] = [r if h != -100 else -100 for h, r in zip(heads, rels)]
    out["scripts"] = scripts
    out["kept"] = kept
    return out


def collate(batch: list[dict], pad_id: int) -> dict[str, torch.Tensor]:
    sub_w = max(len(b["input_ids"]) for b in batch)
    word_w = max(len(b["word_pos"]) for b in batch)
    def pad(key: str, value: int, width: int) -> torch.Tensor:
        return torch.tensor([b[key] + [value] * (width - len(b[key])) for b in batch])
    out = {
        "input_ids": pad("input_ids", pad_id, sub_w),
        "attention_mask": pad("attention_mask", 0, sub_w),
        "word_pos": pad("word_pos", 0, word_w),
        "arc_heads": pad("arc_heads", -100, word_w),
        "arc_rels": pad("arc_rels", -100, word_w),
        "scripts": pad("scripts", -100, word_w),
        "n_words": torch.tensor([len(b["word_pos"]) for b in batch]),
    }
    for h in TAG_HEADS:
        out[f"labels_{h}"] = pad(f"labels_{h}", -100, sub_w)
    return out


class LemmaComposer:
    """Resolve a lemma from the predicted script + the train-only lookup, per composition."""

    def __init__(self, scripts: list[str], lookup: dict[str, dict[str, str]]) -> None:
        self.trees = [json.loads(k) for k in scripts]
        self.form = lookup["form"]
        self.form_upos = lookup["form_upos"]
        self.form_lower = lookup["form_lower"]

    def neural(self, form: str, sid: int) -> str | None:
        if 0 <= sid < len(self.trees):
            return apply_tree(self.trees[sid], form)
        return None

    def resolve(self, mode: str, form: str, upos: str, sid: int) -> str:
        looked = self.form_upos.get(f"{form}|{upos}") or self.form.get(form)
        low = self.form_lower.get(form.lower())
        neur = self.neural(form, sid)
        if mode == "neural-only":
            return neur or form
        if mode == "lookup-first":
            return looked or neur or low or form
        if mode == "neural-first":
            return neur or looked or low or form
        if mode == "unseen-neural":
            return looked or low or neur or form
        raise ValueError(mode)


MODES = ("neural-only", "lookup-first", "neural-first", "unseen-neural")


def evaluate(model, dl, dev_rows, device, amp_dtype, composer: LemmaComposer,
             inv_upos: dict[int, str]) -> dict:
    model.eval()
    n = uas = las = n_tag = upos_ok = 0
    n_lem = 0
    lem_ok = dict.fromkeys(MODES, 0)
    ri = 0
    with torch.no_grad():
        for batch in dl:
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask", "word_pos")}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                tag_logits, arc, rel, lem = model(**inputs)
            arc = arc.float().cpu()
            ar = rel.float().cpu().permute(0, 2, 3, 1)
            sm = lem.float().cpu().argmax(-1)
            up_sub = tag_logits["upos"].argmax(-1).cpu()
            gold_up = batch["labels_upos"]
            mask_tag = gold_up != -100
            n_tag += int(mask_tag.sum())
            upos_ok += int((up_sub[mask_tag] == gold_up[mask_tag]).sum())
            pred_heads = arc.argmax(-1)
            gh, gr = batch["arc_heads"], batch["arc_rels"]
            for b in range(gh.shape[0]):
                enc_row = dl.dataset[ri]
                row = dev_rows[ri]
                ri += 1
                kept = enc_row["kept"]
                for wi in range(int(batch["n_words"][b])):
                    w = kept[wi]
                    if gh[b, wi].item() != -100:
                        n += 1
                        ph = int(pred_heads[b, wi])
                        if ph == gh[b, wi].item():
                            uas += 1
                            if int(ar[b, wi, ph].argmax()) == gr[b, wi].item():
                                las += 1
                    n_lem += 1
                    form = row["tokens"][w]
                    gold_lemma = row["lemma"][w]
                    upos_pred = inv_upos[int(up_sub[b, batch["word_pos"][b, wi]])]
                    sid = int(sm[b, wi])
                    for mode in MODES:
                        if composer.resolve(mode, form, upos_pred, sid) == gold_lemma:
                            lem_ok[mode] += 1
    model.train()
    out = {"uas": uas / n, "las": las / n, "upos_acc": upos_ok / n_tag, "n_arcs": n,
           "n_lemmas": n_lem}
    for mode in MODES:
        out[f"lemma_{mode.replace('-', '_')}"] = lem_ok[mode] / n_lem
    out["lemma_best"] = max(lem_ok.values()) / n_lem
    out["lemma_best_mode"] = max(MODES, key=lambda m: lem_ok[m])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="bowphs/GreBerta")
    ap.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "full"))
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--precision", choices=("auto", "bf16", "fp16", "fp32"), default="auto")
    ap.add_argument("--limit-train", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    precision = args.precision
    if precision == "auto":
        precision = ("bf16" if device == "cuda" and torch.cuda.is_bf16_supported()
                     else "fp16" if device == "cuda" else "fp32")
    amp_dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}.get(precision)
    use_scaler = precision == "fp16"
    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    data_dir = Path(args.data_dir)
    stats = json.loads((data_dir / "full-stats.json").read_text(encoding="utf-8"))
    scripts: list[str] = json.loads((data_dir / "lemma-scripts.json").read_text(encoding="utf-8"))
    lookup = json.loads((data_dir / "lemma-lookup.json").read_text(encoding="utf-8"))
    train_rows = load_jsonl(data_dir / "full-train.jsonl")
    dev_rows = load_jsonl(data_dir / "full-dev.jsonl")
    if args.limit_train:
        train_rows = train_rows[: args.limit_train]

    maps: dict[str, dict[str, int]] = {
        "upos": {lab: i for i, lab in enumerate(stats["upos_labels"])},
        "deprel": {lab: i for i, lab in enumerate(stats["deprels"])},
    }
    for i, chars in enumerate(stats["xpos_position_chars"]):
        maps[f"x{i}"] = {ch: j for j, ch in enumerate(chars)}
    inv_upos = {i: lab for lab, i in maps["upos"].items()}
    composer = LemmaComposer(scripts, lookup)

    tokenizer = AutoTokenizer.from_pretrained(args.model, add_prefix_space=True)
    model = JointParser(args.model, {h: len(maps[h]) for h in TAG_HEADS},
                        n_rels=len(maps["deprel"]), n_scripts=len(scripts)).to(device)
    pad_id = tokenizer.pad_token_id or 0

    enc_train = [encode(r, tokenizer, maps, args.max_len) for r in train_rows]
    enc_dev = [encode(r, tokenizer, maps, args.max_len) for r in dev_rows]
    g = torch.Generator().manual_seed(args.seed)
    dl_train = DataLoader(enc_train, batch_size=args.batch, shuffle=True, generator=g,
                          collate_fn=lambda b: collate(b, pad_id))
    dl_dev = DataLoader(enc_dev, batch_size=32, collate_fn=lambda b: collate(b, pad_id))

    steps = math.ceil(len(dl_train)) * args.epochs
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr)
    sched = get_linear_schedule_with_warmup(optim, int(steps * 0.1), steps)
    scaler = torch.amp.GradScaler(device, enabled=use_scaler)
    ce = nn.CrossEntropyLoss(ignore_index=-100)

    out = Path(args.out)
    (out / "model").mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    best = -1.0
    t0 = time.time()
    model.train()
    for epoch in range(args.epochs):
        for i, batch in enumerate(dl_train):
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask", "word_pos")}
            gh = batch["arc_heads"].to(device)
            gr = batch["arc_rels"].to(device)
            gs = batch["scripts"].to(device)
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                tag_logits, arc, rel, lem = model(**inputs)
                loss = sum(
                    ce(tag_logits[h].flatten(0, 1), batch[f"labels_{h}"].flatten().to(device))
                    for h in TAG_HEADS
                )
                loss = loss + ce(arc.flatten(0, 1), gh.flatten())
                gh_safe = gh.clamp(min=0)
                rel_at_gold = rel.permute(0, 2, 3, 1).gather(
                    2, gh_safe.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, rel.size(1))
                ).squeeze(2)
                loss = loss + ce(rel_at_gold.flatten(0, 1), gr.flatten())
                loss = loss + ce(lem.flatten(0, 1), gs.flatten())
            scaler.scale(loss).backward()
            scaler.step(optim)
            scaler.update()
            optim.zero_grad()
            sched.step()
            if i % 200 == 0:
                print(f"epoch {epoch} step {i}/{len(dl_train)} loss {loss.item():.3f}", flush=True)
        m = evaluate(model, dl_dev, dev_rows, device, amp_dtype, composer, inv_upos)
        m["epoch"] = epoch
        history.append(m)
        print(f"epoch {epoch}: dev UAS {m['uas']:.4f}  LAS {m['las']:.4f}  "
              f"UPOS {m['upos_acc']:.4f}  lemma(best={m['lemma_best_mode']}) "
              f"{m['lemma_best']:.4f}", flush=True)
        score = (m["las"] + m["lemma_best"]) / 2
        if score > best:
            best = score
            torch.save(model.state_dict(), out / "model" / "joint_full.pt")
            tokenizer.save_pretrained(out / "model")
            (out / "model" / "labels.json").write_text(
                json.dumps({"model_name": args.model, "tag_heads": TAG_HEADS, "maps": maps,
                            "n_scripts": len(scripts), "epochs": args.epochs,
                            "seed": args.seed, "best_epoch": epoch},
                           ensure_ascii=False), encoding="utf-8")
            shutil.copy(data_dir / "lemma-scripts.json", out / "model" / "lemma-scripts.json")
            shutil.copy(data_dir / "lemma-lookup.json", out / "model" / "lemma-lookup.json")

    metrics = {
        "model": args.model, "history": history,
        "best": max(history, key=lambda m: (m["las"] + m["lemma_best"]) / 2),
        "wall_s": round(time.time() - t0, 1),
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2) if device == "cuda" else None,
        "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
        "precision": precision, "epochs": args.epochs, "lr": args.lr, "batch": args.batch,
        "max_len": args.max_len, "seed": args.seed, "n_train_sentences": len(train_rows),
        "n_scripts": len(scripts),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    print(json.dumps(metrics["best"], indent=1))


if __name__ == "__main__":
    main()
