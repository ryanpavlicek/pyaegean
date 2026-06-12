"""Validate the authored AGDT→UD converter (agdt_ud.py) against UD-Perseus folds.

For every UD sentence whose sent_id resolves into the AGDT (file@sid) with identical
forms, convert the AGDT side (postag + tree context) with agdt_ud and measure agreement
with the UD gold UPOS and FEATS. Evaluation-only use of the CC BY-NC-SA UD data.

Usage:  python training/validate_agdt_ud.py [--split train] [--show 12]
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import copular_flags, feats_from_xpos, upos_from_xpos  # noqa: E402

from aegean.greek.treebank import _clean_lemma, agdt_dir  # noqa: E402
from aegean.greek.ud import load_conllu, ud_path  # noqa: E402


def agdt_sentences(path: Path) -> dict[str, list[dict]]:
    """sid → tokens [{form, lemma, xpos, has_pnom_child}] for one AGDT file."""
    out: dict[str, list[dict]] = {}
    for _ev, sent in ET.iterparse(str(path), events=("end",)):
        if sent.tag.rsplit("}", 1)[-1] != "sentence":
            continue
        words = [w for w in sent if w.tag.rsplit("}", 1)[-1] == "word" and w.get("form")]
        attrs = [
            {"id": w.get("id") or "", "head": w.get("head") or "",
             "relation": w.get("relation") or ""}
            for w in words
        ]
        flags = copular_flags(attrs)
        sid = sent.get("id") or ""
        if sid:
            out[sid] = [
                {
                    "form": unicodedata.normalize("NFC", w.get("form") or ""),
                    "lemma": _clean_lemma(w.get("lemma") or ""),
                    "xpos": w.get("postag") or "",
                    "has_pnom_child": flag,
                    "relation": w.get("relation") or "",
                }
                for w, flag in zip(words, flags)
            ]
        sent.clear()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", default="train")
    ap.add_argument("--show", type=int, default=12, help="top disagreement patterns to print")
    args = ap.parse_args()

    sents = load_conllu(ud_path("perseus", args.split))
    base = agdt_dir(download=True)
    cache: dict[str, dict[str, list[dict]]] = {}

    n = upos_ok = feats_ok = skipped = 0
    upos_errs: Counter[tuple[str, str, str]] = Counter()
    feats_errs: Counter[tuple[str, str, str]] = Counter()
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
        for g, t in zip(gold, s.tokens):
            n += 1
            pred_upos = upos_from_xpos(
                g["form"], g["xpos"], lemma=g["lemma"],
                has_pnom_child=g["has_pnom_child"], own_relation=g["relation"],
            )
            pred_feats = feats_from_xpos(g["xpos"])
            if pred_upos == t.upos:
                upos_ok += 1
            else:
                upos_errs[(g["xpos"][:1], pred_upos, t.upos)] += 1
            if pred_feats == t.feats:
                feats_ok += 1
            else:
                feats_errs[(g["xpos"], pred_feats, t.feats)] += 1

    print(f"split={args.split}  aligned tokens={n}  skipped sentences={skipped}")
    print(f"UPOS  agreement: {upos_ok}/{n} = {upos_ok/n:.4%}")
    print(f"FEATS agreement: {feats_ok}/{n} = {feats_ok/n:.4%}")
    if upos_errs:
        print("\ntop UPOS disagreements (xpos[0], ours -> UD):")
        for (ch, ours, ud), c in upos_errs.most_common(args.show):
            print(f"  {ch!r} {ours:>6} -> {ud:<6} ×{c}")
    if feats_errs:
        print("\ntop FEATS disagreements (xpos, ours -> UD):")
        for (x, ours, ud), c in feats_errs.most_common(args.show):
            print(f"  {x!r}\n    ours: {ours}\n    UD:   {ud}   ×{c}")


if __name__ == "__main__":
    main()
