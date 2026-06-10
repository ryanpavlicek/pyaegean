"""Build the leakage-clean AGDT dataset for Stage C (biaffine parser, joint with tagging).

Rows carry everything the joint model trains on — UD-convention UPOS (the validated
agdt_ud converter), the 9-char XPOS, and **UD-convention dependency trees** from the
validated agdt_ud_deps converter (96.5% head / 94.5% head+label agreement with the
UD-Perseus conversion):

    {"file", "sid", "tokens", "upos", "xpos", "head": [0=root, 1-based…], "deprel": […]}

Split protocol identical to Stages A/B: train = AGDT minus the UD-Perseus dev+test
exclusion manifest; dev = the manifest's UD-dev sentences; UD-test reserved.

Usage:  python training/build_parser_dataset.py [--out training/data]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xml.etree.ElementTree as ET  # noqa: E402
import unicodedata  # noqa: E402

from agdt_ud import copular_flags, upos_from_xpos  # noqa: E402
from agdt_ud_deps import convert_tree  # noqa: E402

from aegean.greek.treebank import _clean_lemma, agdt_dir  # noqa: E402
from build_upos_dataset import split_ids  # noqa: E402


def load_agdt_parsed(base: Path) -> list[dict]:
    rows: list[dict] = []
    for fp in sorted(base.glob("*.tb.xml")):
        for _ev, sent in ET.iterparse(str(fp), events=("end",)):
            if sent.tag.rsplit("}", 1)[-1] != "sentence":
                continue
            words = [w for w in sent if w.tag.rsplit("}", 1)[-1] == "word" and w.get("form")]
            sid = sent.get("id") or ""
            if sid and words:
                attrs = [
                    {"id": w.get("id") or "", "head": w.get("head") or "",
                     "relation": w.get("relation") or "",
                     "form": unicodedata.normalize("NFC", w.get("form") or ""),
                     "lemma": _clean_lemma(w.get("lemma") or ""),
                     "xpos": (w.get("postag") or "").ljust(9, "-")[:9]}
                    for w in words
                ]
                flags = copular_flags(attrs)
                tree = convert_tree(attrs)
                rows.append({
                    "file": fp.name, "sid": sid,
                    "tokens": [a["form"] for a in attrs],
                    "upos": [
                        upos_from_xpos(a["form"], a["xpos"], lemma=a["lemma"],
                                       has_pnom_child=f, own_relation=a["relation"])
                        for a, f in zip(attrs, flags)
                    ],
                    "xpos": [a["xpos"] for a in attrs],
                    "head": [h for h, _r in tree],
                    "deprel": [r for _h, r in tree],
                })
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
    dev_ids = split_ids("dev")
    excluded = dev_ids | split_ids("test")
    rows = load_agdt_parsed(base)
    train = [r for r in rows if (r["file"], r["sid"]) not in excluded]
    dev = [r for r in rows if (r["file"], r["sid"]) in dev_ids]
    for name, data in (("parser-train.jsonl", train), ("parser-dev.jsonl", dev)):
        with open(out / name, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats = {
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_sentences": len(train), "dev_sentences": len(dev),
        "train_tokens": sum(len(r["tokens"]) for r in train),
        "dev_tokens": sum(len(r["tokens"]) for r in dev),
        "upos_labels": sorted({u for r in rows for u in r["upos"]}),
        "deprels": sorted({d for r in rows for d in r["deprel"]}),
        "xpos_position_chars": [sorted({x[i] for r in rows for x in r["xpos"]}) for i in range(9)],
        "protocol": "Stage C: UD-convention trees from agdt_ud_deps; split as Stages A/B.",
    }
    (out / "parser-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "xpos_position_chars"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
