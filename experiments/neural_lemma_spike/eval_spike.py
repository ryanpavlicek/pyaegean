"""Torch-free eval of the spike model on the dev split — reproduces heldout's
lemma_all / lemma_unseen, vs the pure-Python baseline (40.3% unseen) and stanza/CLTK (62.8%).

Run AFTER Colab training, on the downloaded artifacts:

    pip install onnxruntime tokenizers numpy        # NO torch
    python eval_spike.py --model model.onnx --tokenizer tokenizer.json \
                         --labels data/labels.json --dev data/dev.jsonl

This is exactly the inference path pyaegean[neural] would use in production: tokenizers ->
onnxruntime -> argmax the edit-tree head -> apply_tree. Reuses pyaegean's apply_tree/_norm.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from aegean.greek.lemmatizer import _norm, apply_tree
from aegean.greek.treebank import _clean_lemma


def _iter_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--dev", required=True)
    args = ap.parse_args()

    trees = json.load(open(args.labels, encoding="utf-8"))["trees"]
    tok = Tokenizer.from_file(args.tokenizer)
    sess = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"])
    input_names = {i.name for i in sess.get_inputs()}

    n_all = n_un = ok_all = ok_un = 0
    for sent in _iter_jsonl(args.dev):
        forms = sent["tokens"]
        enc = tok.encode(forms, is_pretokenized=True)
        ids = np.array([enc.ids], dtype=np.int64)
        feed: dict[str, np.ndarray] = {"input_ids": ids}
        if "attention_mask" in input_names:
            feed["attention_mask"] = np.array([enc.attention_mask], dtype=np.int64)
        if "token_type_ids" in input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        logits = sess.run(None, feed)[0][0]  # [seq_len, num_labels]

        first_pos: dict[int, int] = {}
        for pos, wid in enumerate(enc.word_ids):
            if wid is not None and wid not in first_pos:
                first_pos[wid] = pos

        for wi, form in enumerate(forms):
            if not sent["scored"][wi]:
                continue
            n_all += 1
            unseen = not sent["seen"][wi]
            n_un += unseen
            pos = first_pos.get(wi)
            if pos is None:
                pred = _norm(form)
            else:
                tree = json.loads(trees[int(np.argmax(logits[pos]))])
                out = apply_tree(tree, _norm(form))
                pred = out if out is not None else _norm(form)
            if _clean_lemma(pred) == sent["lemmas"][wi]:
                ok_all += 1
                ok_un += unseen

    def pct(c: int, n: int) -> str:
        return f"{c / n:.1%}" if n else "n/a"

    print(f"neural lemma: all {pct(ok_all, n_all)}  UNSEEN {pct(ok_un, n_un)}  "
          f"(n_all={n_all} n_unseen={n_un})")
    print("baselines:    pure-Python unseen 40.3%   stanza/CLTK unseen 62.8%")
    print("VERDICT:", "BEATS stanza on unseen lemma" if (ok_un / n_un if n_un else 0) > 0.628
          else "does NOT beat stanza yet — iterate")


if __name__ == "__main__":
    main()
