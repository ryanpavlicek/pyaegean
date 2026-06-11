"""Build the leakage-clean dataset for Stage D — the full joint model (tags + trees + lemmas).

Rows extend the Stage C parser rows with the lemma supervision (validated byte-identical
to the UD-Perseus lemma column on all 159,895 aligned train tokens):

    {"file","sid","tokens","upos","xpos","head","deprel","lemma","script"}

``script`` is the per-token **edit-script class**: the Chrupała edit tree transforming
form → lemma (reusing `aegean.greek.lemmatizer`'s pure-Python build_tree/apply_tree;
trees are JSON-native, so the inventory is a list of JSON keys). The inventory keeps
scripts seen ≥ --min-freq times in TRAIN; rarer pairs get label -100 (the lookup or the
identity fallback covers them at inference). Also written, all TRAIN-ONLY (these ship
with Stage E, so they must never see the test folds):

    lemma-scripts.json   the script inventory (id → JSON edit tree)
    lemma-lookup.json    {"form": {exact NFC form → most frequent lemma},
                          "form_upos": {"form|UPOS" → most frequent lemma},
                          "form_lower": {lowercased form → most frequent lemma}}

Usage:  python training/build_full_dataset.py [--out training/data] [--min-freq 2]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import copular_flags, upos_from_xpos  # noqa: E402
from agdt_ud_deps import convert_tree  # noqa: E402

from aegean.greek.lemmatizer import _key, build_tree  # noqa: E402
from aegean.greek.treebank import _clean_lemma, agdt_dir  # noqa: E402
from build_upos_dataset import split_ids  # noqa: E402


def load_agdt_full(base: Path) -> list[dict]:
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
                    "lemma": [a["lemma"] or a["form"] for a in attrs],
                })
            sent.clear()
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--min-freq", type=int, default=2)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("fetching/locating AGDT + UD folds (cache) ...", flush=True)
    base = agdt_dir(download=True)
    dev_ids = split_ids("dev")
    excluded = dev_ids | split_ids("test")
    rows = load_agdt_full(base)
    train = [r for r in rows if (r["file"], r["sid"]) not in excluded]
    dev = [r for r in rows if (r["file"], r["sid"]) in dev_ids]

    # --- the edit-script inventory + train-only lookups (TRAIN data only) ----------
    script_counts: Counter[str] = Counter()
    form_lemma: dict[str, Counter[str]] = {}
    form_upos_lemma: dict[str, Counter[str]] = {}
    lower_lemma: dict[str, Counter[str]] = {}
    for r in train:
        for form, upos, lemma in zip(r["tokens"], r["upos"], r["lemma"]):
            script_counts[_key(build_tree(form, lemma))] += 1
            form_lemma.setdefault(form, Counter())[lemma] += 1
            form_upos_lemma.setdefault(f"{form}|{upos}", Counter())[lemma] += 1
            lower_lemma.setdefault(form.lower(), Counter())[lemma] += 1
    scripts = [k for k, c in script_counts.most_common() if c >= args.min_freq]
    script_id = {k: i for i, k in enumerate(scripts)}

    def label(form: str, lemma: str) -> int:
        return script_id.get(_key(build_tree(form, lemma)), -100)

    for split_rows in (train, dev):
        for r in split_rows:
            r["script"] = [label(f, le) for f, le in zip(r["tokens"], r["lemma"])]

    for name, data in (("full-train.jsonl", train), ("full-dev.jsonl", dev)):
        with open(out / name, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "lemma-scripts.json").write_text(json.dumps(scripts, ensure_ascii=False),
                                            encoding="utf-8")
    (out / "lemma-lookup.json").write_text(json.dumps({
        "form": {f: c.most_common(1)[0][0] for f, c in form_lemma.items()},
        "form_upos": {k: c.most_common(1)[0][0] for k, c in form_upos_lemma.items()},
        "form_lower": {f: c.most_common(1)[0][0] for f, c in lower_lemma.items()},
    }, ensure_ascii=False), encoding="utf-8")

    n_train = sum(len(r["tokens"]) for r in train)
    cov_train = sum(1 for r in train for s in r["script"] if s != -100)
    n_dev = sum(len(r["tokens"]) for r in dev)
    cov_dev = sum(1 for r in dev for s in r["script"] if s != -100)
    stats = {
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_sentences": len(train), "dev_sentences": len(dev),
        "train_tokens": n_train, "dev_tokens": n_dev,
        "n_scripts": len(scripts), "min_freq": args.min_freq,
        "script_coverage_train": round(cov_train / n_train, 4),
        "script_coverage_dev": round(cov_dev / n_dev, 4),
        "upos_labels": sorted({u for r in rows for u in r["upos"]}),
        "deprels": sorted({d for r in rows for d in r["deprel"]}),
        "xpos_position_chars": [sorted({x[i] for r in rows for x in r["xpos"]}) for i in range(9)],
        "protocol": "Stage D: parser rows + lemma supervision + edit-script classes; "
                    "inventory and lookups are train-only. See docs/benchmarks.md.",
    }
    (out / "full-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "xpos_position_chars"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
