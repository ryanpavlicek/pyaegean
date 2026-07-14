"""Stage B: train the joint UPOS + morphology tagger on the chosen encoder (GreBerta).

One shared encoder with 10 token-classification heads: UPOS (UD-convention labels, so
the model learns the CCONJ/SCONJ lexical split and the copular AUX contextually) plus
the 9 XPOS positions, from which UD FEATS render deterministically (agdt_ud.
feats_from_xpos — validated at 100% agreement). Loss is the sum of per-head CE.

Selection: per-epoch dev evaluation (UPOS accuracy + exact-FEATS accuracy); the best
checkpoint (by their mean) is kept. Output under --out:
    model/         encoder + heads state_dict (torch.save) + tokenizer + labels.json
    metrics.json   per-epoch dev metrics + the final selection

Plain loop, bf16 auto-detect — same conventions as bakeoff_upos.py. Defaults sized for
the G4 (RTX PRO 6000 Blackwell) / A100 plan; identical-budget discipline does NOT apply
here (this is the real model, not a bake-off) — tune freely on dev, never on test.

Usage (after build_tagger_dataset.py):
    python training/train_tagger.py --model bowphs/GreBerta
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
from agdt_ud import feats_from_xpos  # noqa: E402
from aegean.greek import neural_preprocessing as prep  # noqa: E402

HEADS = list(prep.TAG_HEADS)  # upos + the 9 XPOS positions


class JointTagger(nn.Module):
    """A shared encoder with one linear token-classification head per label set."""

    def __init__(self, model_name: str, label_sizes: dict[str, int]) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(0.1)
        self.heads = nn.ModuleDict({h: nn.Linear(hidden, n) for h, n in label_sizes.items()})

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> dict[str, torch.Tensor]:
        hidden = self.dropout(
            self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        )
        return {h: head(hidden) for h, head in self.heads.items()}


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def encode(example: dict, tokenizer, maps: dict[str, dict[str, int]], max_len: int) -> dict:
    return prep.build_supervision(example, tokenizer, maps, max_len)


def collate(batch: list[dict], pad_id: int) -> dict[str, torch.Tensor]:
    width = max(len(b["input_ids"]) for b in batch)
    def pad(key: str, value: int) -> torch.Tensor:
        return torch.tensor([b[key] + [value] * (width - len(b[key])) for b in batch])
    out = {"input_ids": pad("input_ids", pad_id), "attention_mask": pad("attention_mask", 0),
           "word_index": pad("word_index", -100)}
    for h in HEADS:
        out[f"labels_{h}"] = pad(f"labels_{h}", -100)
    return out


def evaluate(model, dl, device, amp_dtype, inv_x: list[dict[int, str]]) -> dict[str, float]:
    """Dev metrics: UPOS accuracy + exact-FEATS accuracy (rendered from predicted XPOS)."""
    model.eval()
    n = upos_ok = feats_ok = 0
    ce = nn.CrossEntropyLoss(ignore_index=-100)
    loss_sum = 0.0
    with torch.no_grad():
        for batch in dl:
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask")}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                logits = model(**inputs)
            loss_sum += sum(
                ce(logits[h].float().flatten(0, 1).cpu(), batch[f"labels_{h}"].flatten())
                .item()
                for h in HEADS
            )
            preds = {h: logits[h].argmax(-1).cpu() for h in HEADS}
            gold_upos = batch["labels_upos"]
            for r in range(gold_upos.shape[0]):
                for c in range(gold_upos.shape[1]):
                    if gold_upos[r, c].item() == -100:
                        continue
                    n += 1
                    upos_ok += int(preds["upos"][r, c].item() == gold_upos[r, c].item())
                    pred_x = "".join(
                        inv_x[i][preds[f"x{i}"][r, c].item()] for i in range(9)
                    )
                    gold_x = "".join(
                        inv_x[i][batch[f"labels_x{i}"][r, c].item()] for i in range(9)
                    )
                    feats_ok += int(feats_from_xpos(pred_x) == feats_from_xpos(gold_x))
    model.train()
    return {"upos_acc": upos_ok / n, "feats_acc": feats_ok / n, "n": n,
            "dev_loss": loss_sum / max(1, len(dl))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="bowphs/GreBerta")
    ap.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "tagger"))
    ap.add_argument("--epochs", type=int, default=4)
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
    stats = json.loads((data_dir / "tagger-stats.json").read_text(encoding="utf-8"))
    train_rows = load_jsonl(data_dir / "tagger-train.jsonl")
    dev_rows = load_jsonl(data_dir / "tagger-dev.jsonl")
    if args.limit_train:
        train_rows = train_rows[: args.limit_train]

    maps: dict[str, dict[str, int]] = {
        "upos": {lab: i for i, lab in enumerate(stats["upos_labels"])}
    }
    for i, chars in enumerate(stats["xpos_position_chars"]):
        maps[f"x{i}"] = {ch: j for j, ch in enumerate(chars)}
    inv_x = [{j: ch for ch, j in maps[f"x{i}"].items()} for i in range(9)]

    tokenizer = AutoTokenizer.from_pretrained(args.model, add_prefix_space=True)
    prep.configure_tokenizer(tokenizer, args.max_len)
    prep.validate_tokenizer_contract(tokenizer, args.max_len)
    model = JointTagger(args.model, {h: len(maps[h]) for h in HEADS}).to(device)
    pad_id = tokenizer.pad_token_id or 0

    enc_train = [encode(r, tokenizer, maps, args.max_len) for r in train_rows]
    enc_dev = [encode(r, tokenizer, maps, args.max_len) for r in dev_rows]
    g = torch.Generator().manual_seed(args.seed)
    dl_train = DataLoader(enc_train, batch_size=args.batch, shuffle=True, generator=g,
                          collate_fn=lambda b: collate(b, pad_id))
    dl_dev = DataLoader(enc_dev, batch_size=64, collate_fn=lambda b: collate(b, pad_id))

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
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask")}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                logits = model(**inputs)
                loss = sum(
                    ce(logits[h].flatten(0, 1), batch[f"labels_{h}"].flatten().to(device))
                    for h in HEADS
                )
            scaler.scale(loss).backward()
            scaler.step(optim)
            scaler.update()
            optim.zero_grad()
            sched.step()
            if i % 200 == 0:
                print(f"epoch {epoch} step {i}/{len(dl_train)} loss {loss.item():.3f}", flush=True)
        m = evaluate(model, dl_dev, device, amp_dtype, inv_x)
        m["epoch"] = epoch
        history.append(m)
        print(f"epoch {epoch}: dev UPOS {m['upos_acc']:.4f}  FEATS {m['feats_acc']:.4f}", flush=True)
        score = (m["upos_acc"] + m["feats_acc"]) / 2
        if score > best:
            best = score
            torch.save(model.state_dict(), out / "model" / "joint_tagger.pt")
            prep.configure_tokenizer(tokenizer, args.max_len)
            tokenizer.save_pretrained(out / "model")
            (out / "model" / "labels.json").write_text(
                json.dumps({"model_name": args.model, "heads": HEADS, "tag_heads": HEADS, "maps": maps,
                            **prep.contract_metadata(args.max_len)},
                           ensure_ascii=False), encoding="utf-8")

    metrics = {
        "model": args.model, "history": history,
        "best": max(history, key=lambda m: (m["upos_acc"] + m["feats_acc"]) / 2),
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
