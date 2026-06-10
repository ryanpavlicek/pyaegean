"""Build the leakage-clean AGDT UPOS dataset for the Stage A encoder bake-off.

Torch-free: needs only pyaegean (installed or on PYTHONPATH) and the network on first run
(to fetch the AGDT and the UD folds into the cache). Outputs JSONL next to this script:

    training/data/upos-train.jsonl   AGDT sentences NOT referenced by any UD-Perseus
                                     dev/test sentence (the leakage-exclusion manifest)
    training/data/upos-dev.jsonl     the AGDT sentences behind the UD-Perseus DEV fold —
                                     already excluded from training, stable, citable
    training/data/stats.json         counts + label inventory + provenance

The AGDT sentences behind the UD-Perseus TEST fold are written to neither file: they are
reserved for the final `aegean.greek.evaluate_on_ud("perseus", "test")` measurement only.

Each JSONL row: {"file": …, "sid": …, "tokens": [...], "upos": [...]} — UPOS in the
AGDT-native coarse mapping (`aegean.greek.treebank` first-character scheme). The bake-off
compares encoders *relative* to each other on this scheme; the UD-convention label work
(PROPN/SCONJ splits) is Stage B's, where absolute UD numbers start to matter.

Usage:  python training/build_upos_dataset.py [--out training/data]
"""

from __future__ import annotations

import argparse
import json
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from aegean.greek.treebank import _POS, agdt_dir
from aegean.greek.ud import agdt_ud_overlap


def load_agdt_upos(base: Path) -> list[dict[str, Any]]:
    """Every AGDT sentence as {file, sid, tokens, upos} (empty forms skipped)."""
    rows: list[dict[str, Any]] = []
    for fp in sorted(base.glob("*.tb.xml")):
        cur_tokens: list[str] = []
        cur_upos: list[str] = []
        sid = ""
        for _event, elem in ET.iterparse(str(fp), events=("start", "end")):
            tag = elem.tag.rsplit("}", 1)[-1]
            if _event == "start" and tag == "sentence":
                sid = elem.get("id") or ""
                cur_tokens, cur_upos = [], []
            elif _event == "end":
                if tag == "word":
                    form = elem.get("form")
                    if form:
                        postag = elem.get("postag") or ""
                        cur_tokens.append(unicodedata.normalize("NFC", form))
                        cur_upos.append(_POS.get(postag[:1], "X") if postag else "X")
                elif tag == "sentence":
                    if sid and cur_tokens:
                        rows.append(
                            {"file": fp.name, "sid": sid, "tokens": cur_tokens, "upos": cur_upos}
                        )
                    elem.clear()
    return rows


def split_ids(split: str) -> set[tuple[str, str]]:
    """(file, sid) pairs of the AGDT sentences behind one UD-Perseus fold."""
    manifest = agdt_ud_overlap(splits=(split,), verify=False, write=False)
    return {(f, sid) for f, ids in manifest["files"].items() for sid in ids}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("fetching/locating AGDT + UD folds (cache) ...", flush=True)
    base = agdt_dir(download=True)
    dev_ids = split_ids("dev")
    test_ids = split_ids("test")
    rows = load_agdt_upos(base)

    train = [r for r in rows if (r["file"], r["sid"]) not in dev_ids | test_ids]
    dev = [r for r in rows if (r["file"], r["sid"]) in dev_ids]

    for name, data in (("upos-train.jsonl", train), ("upos-dev.jsonl", dev)):
        with open(out / name, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    labels = sorted({u for r in rows for u in r["upos"]})
    train_vocab = {t.lower() for r in train for t in r["tokens"]}
    dev_tokens = sum(len(r["tokens"]) for r in dev)
    dev_unseen = sum(1 for r in dev for t in r["tokens"] if t.lower() not in train_vocab)
    stats = {
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agdt_sentences": len(rows),
        "train_sentences": len(train),
        "dev_sentences": len(dev),
        "reserved_test_sentences": len(test_ids),
        "train_tokens": sum(len(r["tokens"]) for r in train),
        "dev_tokens": dev_tokens,
        "dev_unseen_tokens": dev_unseen,
        "labels": labels,
        "protocol": (
            "train = AGDT minus the UD-Perseus dev+test exclusion manifest; "
            "dev = the manifest's UD-dev sentences; UD-test sentences reserved for "
            "greek.evaluate_on_ud only. See docs/benchmarks.md."
        ),
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
