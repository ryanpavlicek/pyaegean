"""Re-measure every corpus's counts against the corpus-facts registry.

Corpus counts drift when an asset is rebuilt (a corpus re-extracted upstream, a loader change)
or when a bundled corpus is edited: the number in ``training/results/corpus-facts.json`` and
the doc echoes pinned to it then no longer describe the data. ``tests/test_corpus_facts.py``
re-measures the five bundled corpora offline on every PR and pins the docs to the registry;
this script re-measures ALL fourteen loadable corpora (the nine fetched ones need the network
on first run) plus the five bundled sign inventories, so a rebuilt asset that moved a count is
caught. Run it weekly in CI and at the pre-cut gate whenever a corpus asset or loader changed.

It complements the test the way ``scripts/check_benchmarks.py`` complements
``tests/test_benchmark_claims.py``: the test catches a doc/registry divergence instantly and
offline; this catches a registry/reality divergence for the fetched corpora the test cannot
load without the network.

The DDbDP count is read straight from its SQLite tables (a ``COUNT(*)`` over ``documents`` and
``tokens``), not by materialising the 4.4M-token corpus into memory, which would cost minutes and
gigabytes of RAM; it equals what ``aegean.load("ddbdp")`` would build.

Exit 0 = every re-measured count matches the registry; exit 1 = drift, with a per-row report.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
_FIELDS = ("documents", "tokens", "words")


def _registry() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (ROOT / "training/results/corpus-facts.json").read_text(encoding="utf-8")
    )
    return data


def _measure_ddbdp() -> dict[str, int]:
    from aegean.scripts.greek.ddbdp import ddbdp_db

    path = ddbdp_db()  # fetches + unpacks on first use
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        documents = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tokens")
        tokens = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tokens WHERE kind='word'")
        words = cur.fetchone()[0]
    finally:
        con.close()
    return {"documents": documents, "tokens": tokens, "words": words}


def _measure_corpus(corpus_id: str) -> dict[str, int]:
    import aegean

    corpus = aegean.load(corpus_id)
    return {
        "documents": len(corpus),
        "tokens": sum(len(d.tokens) for d in corpus),
        "words": sum(len(d.words) for d in corpus),
    }


def _measure_inventories() -> dict[str, dict[str, int]]:
    from aegean.scripts.cypriot.inventory import cypriot_inventory
    from aegean.scripts.cyprominoan.inventory import cyprominoan_inventory
    from aegean.scripts.greek.inventory import greek_inventory
    from aegean.scripts.lineara.inventory import linear_a_inventory
    from aegean.scripts.linearb.inventory import linear_b_inventory

    invs = {
        "lineara": linear_a_inventory(),
        "linearb": linear_b_inventory(),
        "cypriot": cypriot_inventory(),
        "cyprominoan": cyprominoan_inventory(),
        "greek": greek_inventory(),
    }
    out: dict[str, dict[str, int]] = {}
    for name, inv in invs.items():
        aligned = [s for s in inv if s.attrs.get("source") != "ucd"]
        out[name] = {
            "signs": len(inv),
            "with_sound_values": sum(1 for s in inv if s.phonetic),
            "read": len(aligned),
        }
    return out


def main() -> int:
    reg = _registry()
    failures: list[str] = []

    for corpus_id, row in reg["corpora"].items():
        measured = _measure_ddbdp() if corpus_id == "ddbdp" else _measure_corpus(corpus_id)
        for field in _FIELDS:
            want = row[field]
            got = measured[field]
            status = "ok" if got == want else "DRIFT"
            print(f"{status:5}  {corpus_id:12} {field:9} measured {got} vs registry {want}")
            if status == "DRIFT":
                failures.append(f"{corpus_id} {field}: {want} -> {got}")

    # the Cypriot IG XV 1 sub-count (bundled JSON record count)
    from aegean.data import load_bundled_json

    ig = len(load_bundled_json("cypriot", "ig_inscriptions.json"))
    want = reg["corpora"]["cypriot"]["ig_xv1_inscriptions"]
    status = "ok" if ig == want else "DRIFT"
    print(f"{status:5}  {'cypriot':12} {'ig_xv1':9} measured {ig} vs registry {want}")
    if status == "DRIFT":
        failures.append(f"cypriot ig_xv1_inscriptions: {want} -> {ig}")

    inv_measured = _measure_inventories()
    for name, inv_got in inv_measured.items():
        inv_row = reg["sign_inventories"][name]
        for field in ("signs", "with_sound_values", "read"):
            inv_want = inv_row[field]
            status = "ok" if inv_got[field] == inv_want else "DRIFT"
            print(
                f"{status:5}  {name:12} sign:{field:12} "
                f"measured {inv_got[field]} vs registry {inv_want}"
            )
            if status == "DRIFT":
                failures.append(f"{name} sign {field}: {inv_want} -> {inv_got[field]}")

    if failures:
        print(
            "\nFAIL  corpus counts no longer reproduce — re-measure, then update "
            "training/results/corpus-facts.json AND every doc echo in the same commit:"
        )
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK  every re-measured corpus count matches the registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
