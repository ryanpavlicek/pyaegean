"""Local confirmation of the GreTa seq2seq lemmatizer on the held-out dev split.

Loads the optimum-exported ONNX (`ORTModelForSeq2SeqLM`) and generates the lemma per
dev form via onnxruntime, reporting `DEV lemma all/UNSEEN` — the same number cell 6b
prints in Colab. This is a dev-time confirmation; the shipped runtime will use a
hand-rolled numpy greedy-decode loop so torch stays out of the package dependency set.

    pip install "optimum[onnxruntime]" transformers sentencepiece
    python eval_seq2seq.py --model path/to/unzipped_onnx_dir --dev data/dev.jsonl
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import unicodedata

from optimum.onnxruntime import ORTModelForSeq2SeqLM
from transformers import AutoTokenizer

ML = 32


def _clean(s: str) -> str:
    return re.sub(r"\d+$", "", unicodedata.normalize("NFC", s))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, type=pathlib.Path, help="unzipped optimum onnx dir")
    ap.add_argument("--dev", required=True, type=pathlib.Path, help="dev.jsonl (per-token)")
    ap.add_argument("--batch", type=int, default=128)
    a = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(str(a.model))
    model = ORTModelForSeq2SeqLM.from_pretrained(str(a.model))

    dev = [json.loads(line) for line in a.dev.open(encoding="utf-8")]
    forms = sorted({d["form"] for d in dev if d["scored"]})
    pred: dict[str, str] = {}
    for i in range(0, len(forms), a.batch):
        b = forms[i:i + a.batch]
        enc = tok(b, return_tensors="pt", padding=True, truncation=True, max_length=ML)
        enc.pop("token_type_ids", None)  # GreTa's tokenizer emits these; T5.generate rejects them
        gen = model.generate(**enc, max_length=ML, num_beams=1)
        for form, dec in zip(b, tok.batch_decode(gen, skip_special_tokens=True)):
            pred[form] = dec

    n_all = n_un = ok_all = ok_un = 0
    for d in dev:
        if not d["scored"]:
            continue
        n_all += 1
        un = not d["seen"]
        n_un += un
        if _clean(pred[d["form"]]) == d["lemma"]:
            ok_all += 1
            ok_un += un
    print(f"DEV lemma — all {ok_all / n_all:.1%}  UNSEEN {ok_un / n_un:.1%}   "
          f"(beat: stanza 62.8% unseen)")


if __name__ == "__main__":
    main()
