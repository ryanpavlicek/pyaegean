"""Stage C: train the joint tagger-parser (biaffine, Dozat–Manning) on GreBerta.

One shared encoder, three groups of heads:
  - the Stage B tagging heads (UPOS + 9 XPOS positions), kept so the single Stage E
    artifact serves the whole pipeline;
  - biaffine **arc** scores (each word picks a head among {ROOT} ∪ words);
  - biaffine **relation** scores (a UD deprel per arc).

Graph-based decoding (greedy for dev selection; Chu-Liu/Edmonds MST with a single-root
constraint at final evaluation) handles Ancient Greek's pervasive non-projectivity —
the structural reason the arc-eager baseline capped at UAS 0.51.

Loss = Σ tagging CE + arc CE + relation CE (relations scored at gold arcs). Selection on
dev LAS (greedy). Output under --out: model/ (state_dict + labels.json + tokenizer) and
metrics.json. Plain bf16-auto loop, as throughout.

Usage (after build_parser_dataset.py):
    python training/train_parser.py --model bowphs/GreBerta
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import feats_from_xpos  # noqa: E402,F401  (re-exported for eval)

TAG_HEADS = ["upos"] + [f"x{i}" for i in range(9)]


class Biaffine(nn.Module):
    """Biaffine scorer with bias terms on both sides (Dozat & Manning 2017)."""

    def __init__(self, in_dim: int, out_dim: int = 1) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.zeros(out_dim, in_dim + 1, in_dim + 1))
        nn.init.xavier_uniform_(self.weight)

    def forward(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        ones = x.new_ones(*x.shape[:-1], 1)
        x = torch.cat((x, ones), dim=-1)
        y = torch.cat((y, y.new_ones(*y.shape[:-1], 1)), dim=-1)
        return torch.einsum("bxi,oij,byj->boxy", x, self.weight, y)  # [B, out, Wx, Wy]


class JointParser(nn.Module):
    """Shared encoder + tagging heads + biaffine arc/relation scorers.

    With ``n_scripts > 0`` (Stage D), a word-level lemma head classifies edit scripts —
    the full pipeline (tags, morphology, trees, lemmas) in one checkpoint."""

    def __init__(self, model_name: str, tag_sizes: dict[str, int], n_rels: int,
                 arc_dim: int = 512, rel_dim: int = 128, n_scripts: int = 0) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(0.1)
        self.tag_heads = nn.ModuleDict({h: nn.Linear(hidden, n) for h, n in tag_sizes.items()})
        def mlp(out: int) -> nn.Sequential:
            return nn.Sequential(nn.Linear(hidden, out), nn.GELU(), nn.Dropout(0.33))
        self.arc_dep, self.arc_head = mlp(arc_dim), mlp(arc_dim)
        self.rel_dep, self.rel_head = mlp(rel_dim), mlp(rel_dim)
        self.arc_attn = Biaffine(arc_dim, 1)
        self.rel_attn = Biaffine(rel_dim, n_rels)
        self.lemma_head = nn.Linear(hidden, n_scripts) if n_scripts else None

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor,
                word_pos: torch.Tensor):
        """word_pos: [B, W] subword index of each word's first subword (0-padded)."""
        hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        hidden = self.dropout(hidden)
        tag_logits = {h: head(hidden) for h, head in self.tag_heads.items()}  # subword-level
        idx = word_pos.unsqueeze(-1).expand(-1, -1, hidden.size(-1))
        words = hidden.gather(1, idx)                       # [B, W, H]
        root = hidden[:, :1]                                # <s> stands in for ROOT
        cands = torch.cat((root, words), dim=1)             # [B, W+1, H]
        arc = self.arc_attn(self.arc_dep(words), self.arc_head(cands)).squeeze(1)  # [B, W, W+1]
        rel = self.rel_attn(self.rel_dep(words), self.rel_head(cands))             # [B, R, W, W+1]
        lem = self.lemma_head(words) if self.lemma_head is not None else None      # [B, W, S]
        return tag_logits, arc, rel, lem


# ---- decoding: the single-root Chu-Liu/Edmonds MST lives in the package ------------
from aegean.greek.mst import decode_mst  # noqa: E402,F401  (re-exported for the eval scripts)


# ---- data ----------------------------------------------------------------------------


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
    kept: list[int] = []                          # word ids that survived truncation
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
    # parser labels over the KEPT words; a gold head beyond truncation maps to -100
    old2new = {w: i for i, w in enumerate(kept)}
    heads, rels = [], []
    for w in kept:
        g = example["head"][w]                    # 0 = root, else 1-based old index
        if g == 0:
            heads.append(0)
        else:
            heads.append(old2new[g - 1] + 1 if (g - 1) in old2new else -100)
        rels.append(maps["deprel"][example["deprel"][w]])
    out["arc_heads"] = heads
    out["arc_rels"] = [r if h != -100 else -100 for h, r in zip(heads, rels)]
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
        "n_words": torch.tensor([len(b["word_pos"]) for b in batch]),
    }
    for h in TAG_HEADS:
        out[f"labels_{h}"] = pad(f"labels_{h}", -100, sub_w)
    return out


def evaluate(model, dl, device, amp_dtype) -> dict[str, float]:
    """Greedy dev UAS/LAS + UPOS accuracy (MST is reserved for the final UD eval)."""
    model.eval()
    n = uas = las = n_tag = upos_ok = 0
    with torch.no_grad():
        for batch in dl:
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask", "word_pos")}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                tag_logits, arc, rel, _lem = model(**inputs)
            arc = arc.float().cpu()
            rel = rel.float().cpu()
            up = tag_logits["upos"].argmax(-1).cpu()
            gold_up = batch["labels_upos"]
            mask_tag = gold_up != -100
            n_tag += int(mask_tag.sum())
            upos_ok += int((up[mask_tag] == gold_up[mask_tag]).sum())
            pred_heads = arc.argmax(-1)                       # [B, W]
            gh, gr = batch["arc_heads"], batch["arc_rels"]
            B, W = gh.shape
            ar = rel.permute(0, 2, 3, 1)                      # [B, W, W+1, R]
            for b in range(B):
                for wi in range(int(batch["n_words"][b])):
                    if gh[b, wi].item() == -100:
                        continue
                    n += 1
                    ph = int(pred_heads[b, wi])
                    if ph == gh[b, wi].item():
                        uas += 1
                        pr = int(ar[b, wi, ph].argmax())
                        if pr == gr[b, wi].item():
                            las += 1
    model.train()
    return {"uas": uas / n, "las": las / n, "upos_acc": upos_ok / n_tag, "n_arcs": n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="bowphs/GreBerta")
    ap.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "parser"))
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
    stats = json.loads((data_dir / "parser-stats.json").read_text(encoding="utf-8"))
    train_rows = load_jsonl(data_dir / "parser-train.jsonl")
    dev_rows = load_jsonl(data_dir / "parser-dev.jsonl")
    if args.limit_train:
        train_rows = train_rows[: args.limit_train]

    maps: dict[str, dict[str, int]] = {
        "upos": {lab: i for i, lab in enumerate(stats["upos_labels"])},
        "deprel": {lab: i for i, lab in enumerate(stats["deprels"])},
    }
    for i, chars in enumerate(stats["xpos_position_chars"]):
        maps[f"x{i}"] = {ch: j for j, ch in enumerate(chars)}

    tokenizer = AutoTokenizer.from_pretrained(args.model, add_prefix_space=True)
    model = JointParser(args.model, {h: len(maps[h]) for h in TAG_HEADS},
                        n_rels=len(maps["deprel"])).to(device)
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
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                tag_logits, arc, rel, _lem = model(**inputs)
                loss = sum(
                    ce(tag_logits[h].flatten(0, 1), batch[f"labels_{h}"].flatten().to(device))
                    for h in TAG_HEADS
                )
                loss = loss + ce(arc.flatten(0, 1), gh.flatten())
                # relation loss at gold arcs
                gh_safe = gh.clamp(min=0)
                rel_at_gold = rel.permute(0, 2, 3, 1).gather(
                    2, gh_safe.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, rel.size(1))
                ).squeeze(2)                                   # [B, W, R]
                loss = loss + ce(rel_at_gold.flatten(0, 1), gr.flatten())
            scaler.scale(loss).backward()
            scaler.step(optim)
            scaler.update()
            optim.zero_grad()
            sched.step()
            if i % 200 == 0:
                print(f"epoch {epoch} step {i}/{len(dl_train)} loss {loss.item():.3f}", flush=True)
        m = evaluate(model, dl_dev, device, amp_dtype)
        m["epoch"] = epoch
        history.append(m)
        print(f"epoch {epoch}: dev UAS {m['uas']:.4f}  LAS {m['las']:.4f}  UPOS {m['upos_acc']:.4f}",
              flush=True)
        if m["las"] > best:
            best = m["las"]
            torch.save(model.state_dict(), out / "model" / "joint_parser.pt")
            tokenizer.save_pretrained(out / "model")
            (out / "model" / "labels.json").write_text(
                json.dumps({"model_name": args.model, "tag_heads": TAG_HEADS, "maps": maps},
                           ensure_ascii=False), encoding="utf-8")

    metrics = {
        "model": args.model, "history": history,
        "best": max(history, key=lambda m: m["las"]),
        "wall_s": round(time.time() - t0, 1),
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2) if device == "cuda" else None,
        "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
        "precision": precision, "epochs": args.epochs, "lr": args.lr, "batch": args.batch,
        "max_len": args.max_len, "seed": args.seed, "n_train_sentences": len(train_rows),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    print(json.dumps(metrics["best"], indent=1))


if __name__ == "__main__":
    main()
