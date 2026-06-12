"""Validate the authored AGDT→UD dependency converter against UD-Perseus folds.

Converts every aligned AGDT sentence with agdt_ud_deps.convert_tree and measures
head (UAS-style) and head+label (LAS-style) agreement with the UD gold, printing the
top disagreement patterns. Evaluation-only use of the CC BY-NC-SA UD data.

Usage:  python training/validate_agdt_ud_deps.py [--split train] [--show 14]
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud_deps import convert_tree  # noqa: E402

from aegean.greek.treebank import agdt_dir  # noqa: E402
from aegean.greek.ud import load_conllu, ud_path  # noqa: E402


def agdt_sentences(path: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for _ev, sent in ET.iterparse(str(path), events=("end",)):
        if sent.tag.rsplit("}", 1)[-1] != "sentence":
            continue
        words = [w for w in sent if w.tag.rsplit("}", 1)[-1] == "word" and w.get("form")]
        sid = sent.get("id") or ""
        if sid:
            out[sid] = [
                {"id": w.get("id") or "", "head": w.get("head") or "",
                 "relation": w.get("relation") or "",
                 "form": unicodedata.normalize("NFC", w.get("form") or ""),
                 "lemma": w.get("lemma") or "", "xpos": w.get("postag") or ""}
                for w in words
            ]
        sent.clear()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="train")
    ap.add_argument("--show", type=int, default=14)
    args = ap.parse_args()

    sents = load_conllu(ud_path("perseus", args.split))
    base = agdt_dir(download=True)
    cache: dict[str, dict[str, list[dict]]] = {}

    n = head_ok = both_ok = label_ok = skipped = 0
    head_err: Counter[str] = Counter()    # by AGDT base relation
    label_err: Counter[tuple[str, str, str]] = Counter()  # (agdt rel, ours, UD) where head was right
    for s in sents:
        if "@" not in s.sent_id:
            skipped += 1
            continue
        fname, _, sid = s.sent_id.rpartition("@")
        if fname not in cache:
            fp = base / fname
            cache[fname] = agdt_sentences(fp) if fp.exists() else {}
        gold = cache[fname].get(sid)
        if gold is None or [g["form"] for g in gold] != [t.form for t in s.tokens]:
            skipped += 1
            continue
        pred = convert_tree(gold)
        for g, (ph, pr), t in zip(gold, pred, s.tokens):
            n += 1
            h_ok = ph == t.head
            l_ok = pr == t.deprel
            head_ok += int(h_ok)
            label_ok += int(l_ok)
            both_ok += int(h_ok and l_ok)
            if not h_ok:
                head_err[(g["relation"] or "").split("_")[0]] += 1
            elif not l_ok:
                label_err[((g["relation"] or "").split("_")[0], pr, t.deprel)] += 1

    print(f"split={args.split}  aligned tokens={n}  skipped sentences={skipped}")
    print(f"head  (UAS-like) agreement: {head_ok}/{n} = {head_ok/n:.4%}")
    print(f"label agreement:            {label_ok}/{n} = {label_ok/n:.4%}")
    print(f"head+label (LAS-like):      {both_ok}/{n} = {both_ok/n:.4%}")
    print("\ntop head disagreements by AGDT relation:")
    for rel, c in head_err.most_common(args.show):
        print(f"  {rel:8} ×{c}")
    print("\ntop label disagreements where the head was right (AGDT rel, ours -> UD):")
    for (rel, ours, ud), c in label_err.most_common(args.show):
        print(f"  {rel:8} {ours:>8} -> {ud:<8} ×{c}")


if __name__ == "__main__":
    main()
