"""Score a trained Stage B tagger checkpoint on a UD test fold (the headline number).

Runs the JointTagger over the fold's gold tokens (the same gold-tokenization protocol as
aegean.greek.evaluate_on_ud), renders predictions as CoNLL-U — UPOS directly, XPOS as
the 9 predicted position characters, FEATS via the validated feats_from_xpos — and
scores against gold with the official CoNLL 2018 evaluator. Reported metrics: UPOS,
XPOS, UFeats (lemma/heads are placeholders here; those come from Stages C/D).

Usage:  python training/eval_tagger_ud.py --checkpoint training/out/tagger/model \
            [--treebank perseus] [--split test]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import torch
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import feats_from_xpos  # noqa: E402
from train_tagger import HEADS, JointTagger, collate, encode  # noqa: E402

from aegean.greek.ud import _eval_module, load_conllu, ud_path  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", required=True, help="the saved model/ directory")
    ap.add_argument("--treebank", default="perseus", choices=("perseus", "proiel"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None, help="optional path for the metrics JSON")
    args = ap.parse_args()

    ckpt = Path(args.checkpoint)
    spec = json.loads((ckpt / "labels.json").read_text(encoding="utf-8"))
    maps: dict[str, dict[str, int]] = spec["maps"]
    inv = {h: {i: lab for lab, i in m.items()} for h, m in maps.items()}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    amp_dtype = (
        torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported()
        else torch.float16 if device == "cuda" else None
    )
    tokenizer = AutoTokenizer.from_pretrained(ckpt, add_prefix_space=True)
    model = JointTagger(spec["model_name"], {h: len(maps[h]) for h in HEADS})
    model.load_state_dict(torch.load(ckpt / "joint_tagger.pt", map_location=device))
    model.to(device).eval()

    gold_path = ud_path(args.treebank, args.split)
    sentences = load_conllu(gold_path)

    lines: list[str] = []
    from torch.utils.data import DataLoader

    rows = [{"tokens": [t.form for t in s.tokens],
             "upos": ["X"] * len(s.tokens),                # dummies: encode() needs labels
             "xpos": ["---------"] * len(s.tokens)} for s in sentences]
    pad_id = tokenizer.pad_token_id or 0
    enc = [encode(r, tokenizer, maps, 256) for r in rows]
    dl = DataLoader(enc, batch_size=64, collate_fn=lambda b: collate(b, pad_id))

    si = 0
    with torch.no_grad():
        for batch in dl:
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask")}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                logits = model(**inputs)
            preds = {h: logits[h].argmax(-1).cpu() for h in HEADS}
            word_index = batch["word_index"]
            for r in range(word_index.shape[0]):
                sent = sentences[si]
                si += 1
                upos = ["X"] * len(sent.tokens)
                xpos = ["---------"] * len(sent.tokens)
                for c in range(word_index.shape[1]):
                    wid = word_index[r, c].item()
                    if wid == -100:
                        continue
                    upos[wid] = inv["upos"][preds["upos"][r, c].item()]
                    xpos[wid] = "".join(
                        inv[f"x{i}"][preds[f"x{i}"][r, c].item()] for i in range(9)
                    )
                if sent.sent_id:
                    lines.append(f"# sent_id = {sent.sent_id}")
                for i, t in enumerate(sent.tokens):
                    head = 0 if i == 0 else 1
                    rel = "root" if i == 0 else "dep"
                    lines.append("\t".join((
                        str(i + 1), t.form, "_", upos[i], xpos[i],
                        feats_from_xpos(xpos[i]), str(head), rel, "_", "_",
                    )))
                lines.append("")

    ev = _eval_module()
    with tempfile.TemporaryDirectory() as td:
        sys_path = Path(td) / "system.conllu"
        sys_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with open(gold_path, encoding="utf-8") as gf:
            gold_ud = ev.load_conllu(gf)
        with open(sys_path, encoding="utf-8") as sf:
            system_ud = ev.load_conllu(sf)
    scores = ev.evaluate(gold_ud, system_ud)
    result = {
        "checkpoint": str(ckpt), "treebank": args.treebank, "split": args.split,
        "upos": scores["UPOS"].f1, "xpos": scores["XPOS"].f1, "ufeats": scores["UFeats"].f1,
        "n_sentences": len(sentences),
        "n_words": sum(len(s.tokens) for s in sentences),
    }
    text = json.dumps(result, indent=1)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
