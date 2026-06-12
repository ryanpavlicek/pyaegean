"""Build the leakage-clean AGDT dataset for Stage B (joint UPOS + morphology tagger).

Like build_upos_dataset.py (same split protocol: train = AGDT minus the UD-Perseus
dev+test exclusion manifest; dev = the manifest's UD-dev sentences; UD-test reserved),
but each row carries **UD-convention labels** built by the validated converter
(agdt_ud.py — 99.94% UPOS / 100% FEATS agreement with the UD conversion):

    {"file": …, "sid": …, "tokens": […], "upos": […UD-convention…], "xpos": […9-char…]}

The trainer predicts UPOS directly (learning the CCONJ/SCONJ lexical split and the
copular AUX contextually) plus the 9 XPOS positions, from which UD FEATS render
deterministically (feats_from_xpos).

Usage:  python training/build_tagger_dataset.py [--out training/data]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import copular_flags, upos_from_xpos  # noqa: E402

from aegean.greek.treebank import _clean_lemma, agdt_dir  # noqa: E402
from build_upos_dataset import split_ids  # noqa: E402


def load_agdt_tagged(base: Path) -> list[dict[str, Any]]:
    """Every AGDT sentence as {file, sid, tokens, upos(UD), xpos} via the converter."""
    rows: list[dict[str, Any]] = []
    for fp in sorted(base.glob("*.tb.xml")):
        for _ev, sent in ET.iterparse(str(fp), events=("end",)):
            if sent.tag.rsplit("}", 1)[-1] != "sentence":
                continue
            words = [w for w in sent if w.tag.rsplit("}", 1)[-1] == "word" and w.get("form")]
            sid = sent.get("id") or ""
            if sid and words:
                attrs = [
                    {"id": w.get("id") or "", "head": w.get("head") or "",
                     "relation": w.get("relation") or ""}
                    for w in words
                ]
                flags = copular_flags(attrs)
                tokens, upos, xpos = [], [], []
                for w, flag in zip(words, flags):
                    tag = (w.get("postag") or "").ljust(9, "-")[:9]
                    tokens.append(unicodedata.normalize("NFC", w.get("form") or ""))
                    xpos.append(tag)
                    upos.append(
                        upos_from_xpos(
                            tokens[-1], tag, lemma=_clean_lemma(w.get("lemma") or ""),
                            has_pnom_child=flag, own_relation=w.get("relation") or "",
                        )
                    )
                rows.append({"file": fp.name, "sid": sid, "tokens": tokens,
                             "upos": upos, "xpos": xpos})
            sent.clear()
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("fetching/locating AGDT + UD folds (cache) ...", flush=True)
    base = agdt_dir(download=True)
    excluded = split_ids("dev") | split_ids("test")
    dev_ids = split_ids("dev")
    rows = load_agdt_tagged(base)

    train = [r for r in rows if (r["file"], r["sid"]) not in excluded]
    dev = [r for r in rows if (r["file"], r["sid"]) in dev_ids]
    for name, data in (("tagger-train.jsonl", train), ("tagger-dev.jsonl", dev)):
        with open(out / name, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    upos_labels = sorted({u for r in rows for u in r["upos"]})
    pos_chars = [sorted({x[i] for r in rows for x in r["xpos"]}) for i in range(9)]
    stats = {
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_sentences": len(train),
        "dev_sentences": len(dev),
        "train_tokens": sum(len(r["tokens"]) for r in train),
        "dev_tokens": sum(len(r["tokens"]) for r in dev),
        "upos_labels": upos_labels,
        "xpos_position_chars": pos_chars,
        "protocol": (
            "Stage B: UD-convention labels from the validated AGDT->UD converter "
            "(agdt_ud.py); split identical to build_upos_dataset.py. See docs/benchmarks.md."
        ),
    }
    (out / "tagger-stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in stats.items() if k != "xpos_position_chars"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
