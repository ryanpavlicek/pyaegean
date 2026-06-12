"""Stage A encoder bake-off: identical quick UPOS fine-tune per candidate backbone.

Fine-tunes one Hugging Face encoder with a token-classification head on the leakage-clean
AGDT UPOS dataset (see build_upos_dataset.py) under a FIXED budget, and reports dev
accuracy overall + on unseen forms, parameter count, wall time, and peak VRAM — the
numbers the Stage A decision is made on (see training/README.md).

Deliberately a plain training loop (AdamW + linear warmup + mixed-precision autocast),
not the Trainer API, so it survives transformers version churn and hides nothing.

Defaults target the planned hardware — a Colab G4 (NVIDIA RTX PRO 6000 Blackwell Server
Edition, 96 GB) with A100 as backup: bf16 autocast (auto-detected; no loss scaler
needed), native batch 32, max length 256. On older fp16-only GPUs (e.g. a T4) precision
auto-falls-back to fp16 + GradScaler; add --batch 16 --grad-accum 2 there to keep the
same effective batch of 32. The budget (epochs, lr, effective batch, max-len, seed) must
stay IDENTICAL across candidates — that is the bake-off.

Usage (after build_upos_dataset.py):
    python training/bakeoff_upos.py --model bowphs/GreBerta
    python training/bakeoff_upos.py --model bowphs/PhilBerta
    python training/bakeoff_upos.py --model pranaydeeps/Ancient-Greek-BERT   # reference only (GPL-3.0)
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import (
    AutoConfig,
    AutoModelForTokenClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def encode(example: dict, tokenizer, label2id: dict[str, int], max_len: int) -> dict:
    """Tokenize a pre-split sentence; label the first subword of each word (-100 elsewhere)."""
    enc = tokenizer(
        example["tokens"], is_split_into_words=True, truncation=True, max_length=max_len
    )
    word_ids = enc.word_ids()
    labels, first_subword_word = [], []
    prev = None
    for wid in word_ids:
        if wid is None or wid == prev:
            labels.append(-100)
        else:
            labels.append(label2id[example["upos"][wid]])
            first_subword_word.append(wid)
        prev = wid
    enc = {k: enc[k] for k in ("input_ids", "attention_mask")}
    enc["labels"] = labels
    enc["word_index"] = [w if lab != -100 else -100 for w, lab in zip(
        [wid if wid is not None else -100 for wid in word_ids], labels)]
    enc["n_words"] = len(example["tokens"])
    enc["n_labeled"] = len(first_subword_word)
    return enc


def collate(batch: list[dict], pad_id: int) -> dict[str, torch.Tensor]:
    width = max(len(b["input_ids"]) for b in batch)
    def pad(key: str, value: int) -> torch.Tensor:
        return torch.tensor([b[key] + [value] * (width - len(b[key])) for b in batch])
    return {
        "input_ids": pad("input_ids", pad_id),
        "attention_mask": pad("attention_mask", 0),
        "labels": pad("labels", -100),
        "word_index": pad("word_index", -100),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "out"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--precision", choices=("auto", "bf16", "fp16", "fp32"), default="auto")
    ap.add_argument("--limit-train", type=int, default=0, help="smoke runs: cap train sentences")
    ap.add_argument("--save-model", action="store_true", help="bake-off models are throwaway by default")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.precision == "auto":
        precision = (
            "bf16" if device == "cuda" and torch.cuda.is_bf16_supported()
            else "fp16" if device == "cuda" else "fp32"
        )
    else:
        precision = args.precision
    amp_dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}.get(precision)
    use_scaler = precision == "fp16"  # bf16 needs no loss scaling
    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True  # free speed on Ampere+/Blackwell
        torch.backends.cudnn.allow_tf32 = True

    data_dir = Path(args.data_dir)
    train_rows = load_jsonl(data_dir / "upos-train.jsonl")
    dev_rows = load_jsonl(data_dir / "upos-dev.jsonl")
    if args.limit_train:
        train_rows = train_rows[: args.limit_train]
    # Stable label inventory from the dataset build (stats.json) — never derived from a
    # (possibly limited) run's rows, so every candidate trains over the identical space.
    stats_path = data_dir / "stats.json"
    if stats_path.exists():
        labels = json.loads(stats_path.read_text(encoding="utf-8"))["labels"]
    else:
        labels = sorted({u for r in train_rows + dev_rows for u in r["upos"]})
    label2id = {lab: i for i, lab in enumerate(labels)}
    train_vocab = {t.lower() for r in train_rows for t in r["tokens"]}
    # Fixed denominators: every candidate is scored over the SAME dev token set; tokens a
    # tokenizer truncates away are counted as errors, not silently dropped (else high
    # subword fertility would shrink a candidate's denominator and bias the comparison).
    total_dev = sum(len(r["tokens"]) for r in dev_rows)
    total_dev_unseen = sum(
        1 for r in dev_rows for t in r["tokens"] if t.lower() not in train_vocab
    )

    config = AutoConfig.from_pretrained(args.model)
    tok_kwargs = {"add_prefix_space": True} if config.model_type in ("roberta", "gpt2", "bart") else {}
    tokenizer = AutoTokenizer.from_pretrained(args.model, **tok_kwargs)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model, num_labels=len(labels), id2label={i: lab for lab, i in label2id.items()},
        label2id=label2id,
    ).to(device)

    enc_train = [encode(r, tokenizer, label2id, args.max_len) for r in train_rows]
    enc_dev = [encode(r, tokenizer, label2id, args.max_len) for r in dev_rows]
    truncated_dev = sum(r["n_words"] - r["n_labeled"] for r in enc_dev)
    pad_id = tokenizer.pad_token_id or 0

    g = torch.Generator().manual_seed(args.seed)
    dl_train = DataLoader(
        enc_train, batch_size=args.batch, shuffle=True, generator=g,
        collate_fn=lambda b: collate(b, pad_id),
    )
    dl_dev = DataLoader(enc_dev, batch_size=64, collate_fn=lambda b: collate(b, pad_id))

    steps = math.ceil(len(dl_train) / args.grad_accum) * args.epochs
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr)
    sched = get_linear_schedule_with_warmup(optim, int(steps * 0.1), steps)
    scaler = torch.amp.GradScaler(device, enabled=use_scaler)

    t0 = time.time()
    model.train()
    for epoch in range(args.epochs):
        for i, batch in enumerate(dl_train):
            wi = batch.pop("word_index")
            del wi
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                loss = model(**batch).loss / args.grad_accum
            scaler.scale(loss).backward()
            if (i + 1) % args.grad_accum == 0 or i + 1 == len(dl_train):
                scaler.step(optim)
                scaler.update()
                optim.zero_grad()
                sched.step()
            if i % 200 == 0:
                print(f"epoch {epoch} step {i}/{len(dl_train)} loss {loss.item()*args.grad_accum:.3f}", flush=True)

    # --- dev evaluation: overall + unseen-form accuracy --------------------------
    model.eval()
    n_all = ok_all = n_unseen = ok_unseen = 0
    with torch.no_grad():
        for bi, batch in enumerate(dl_dev):
            word_index = batch.pop("word_index")
            batch_rows = dev_rows[bi * 64 : bi * 64 + word_index.shape[0]]
            inputs = {k: v.to(device) for k, v in batch.items() if k != "labels"}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                logits = model(**inputs).logits
            preds = logits.argmax(-1).cpu()
            labels_t = batch["labels"]
            for r in range(labels_t.shape[0]):
                forms = batch_rows[r]["tokens"]
                for c in range(labels_t.shape[1]):
                    gold = labels_t[r, c].item()
                    if gold == -100:
                        continue
                    unseen = forms[word_index[r, c].item()].lower() not in train_vocab
                    correct = int(preds[r, c].item() == gold)
                    n_all += 1
                    ok_all += correct
                    if unseen:
                        n_unseen += 1
                        ok_unseen += correct

    metrics = {
        "model": args.model,
        "dev_upos_acc": ok_all / total_dev if total_dev else 0.0,
        "dev_upos_acc_unseen": ok_unseen / total_dev_unseen if total_dev_unseen else 0.0,
        "n_dev_tokens": total_dev,
        "n_dev_unseen": total_dev_unseen,
        "n_dev_tokens_scored": n_all,
        "n_dev_unseen_scored": n_unseen,
        "dev_tokens_truncated": truncated_dev,
        "params_m": round(sum(p.numel() for p in model.parameters()) / 1e6, 1),
        "wall_s": round(time.time() - t0, 1),
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2) if device == "cuda" else None,
        "device": device,
        "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
        "precision": precision,
        "epochs": args.epochs, "lr": args.lr, "batch": args.batch,
        "grad_accum": args.grad_accum, "max_len": args.max_len, "seed": args.seed,
        "n_train_sentences": len(train_rows), "labels": labels,
    }
    slug = args.model.replace("/", "__")
    out = Path(args.out) / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    if args.save_model:
        model.save_pretrained(out / "model")
        tokenizer.save_pretrained(out / "model")
    print(json.dumps(metrics, indent=1))


if __name__ == "__main__":
    main()
