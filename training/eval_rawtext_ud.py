"""Raw-text end-to-end check: the shipped pipeline from `# text` to scored CoNLL-U.

The headline protocol (docs/benchmarks.md) feeds gold tokens. This script removes that
last asterisk: it takes each UD sentence's raw ``# text``, tokenizes with pyaegean's own
`aegean.greek.tokenize` (words and punctuation), runs the active neural pipeline, and scores with the
official evaluator — whose character-based alignment handles tokenization differences,
exactly as the published systems were scored. Requires `use_neural_pipeline` (run after
the artifact is fetchable).

Usage:  python training/eval_rawtext_ud.py [--treebank perseus] [--split test] [--out f]
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from aegean import greek
from aegean.greek.ud import _eval_module, load_conllu, ud_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--treebank", default="perseus", choices=("perseus", "proiel"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    greek.use_neural_pipeline()
    gold_path = ud_path(args.treebank, args.split)
    sentences = load_conllu(gold_path)

    lines: list[str] = []
    skipped = 0
    for sent in sentences:
        text = sent.text or " ".join(t.form for t in sent.tokens)
        if not sent.text:
            skipped += 1  # no raw text in the fold; fall back to joined forms
        words = [t.text for t in greek.tokenize(text)]  # words AND punctuation:
        # the official evaluator aligns by the character stream, so every gold
        # character (commas included) must appear in the system tokens
        if not words:
            words = [t.form for t in sent.tokens]
        ana = greek.analyze_sentence(words)
        if sent.sent_id:
            lines.append(f"# sent_id = {sent.sent_id}")
        lines.append(f"# text = {text}")
        for i, w in enumerate(ana.tokens):
            misc = "_" if i + 1 < len(ana.tokens) else "_"
            lines.append("\t".join((
                str(i + 1), w, ana.lemma[i], ana.upos[i], ana.xpos[i], ana.feats[i],
                str(ana.head[i]), ana.deprel[i], "_", misc)))
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
        "protocol": "raw-text (own tokenization, character-aligned by the official evaluator)",
        "treebank": args.treebank, "split": args.split,
        "tokens_f1": scores["Tokens"].f1,
        "lemma": scores["Lemmas"].f1,
        "uas": scores["UAS"].f1, "las": scores["LAS"].f1, "clas": scores["CLAS"].f1,
        "upos": scores["UPOS"].f1, "xpos": scores["XPOS"].f1, "ufeats": scores["UFeats"].f1,
        "n_sentences": len(sentences), "sentences_without_raw_text": skipped,
    }
    text_out = json.dumps(result, indent=1)
    print(text_out)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text_out, encoding="utf-8")


if __name__ == "__main__":
    main()
