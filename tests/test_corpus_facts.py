"""Corpus FACTS stay pinned to their registry (the published-claims pattern, for counts).

``training/results/corpus-facts.json`` records each loadable corpus's document / token /
word counts and the Aegean sign-inventory headline facts (signs, signs with a sound value,
read signs). This test makes a rebuild that changes a count a failure unless the registry
AND every doc echo move together:

* the five bundled corpora are re-measured live here (offline, per-PR) and must equal the
  registry rows, so a data change that shifts a count fails until the registry is updated;
* every echo in the registry's ``echoes`` list (a doc site that states a count) is checked
  against its fact, so a stale doc number, or a registry number changed without updating the
  docs, fails here. Adding an echo site is a one-line registry edit.

``scripts/check_corpus_facts.py`` re-measures the nine fetched corpora too (network, weekly).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import aegean
from aegean.data import load_bundled_json

ROOT = Path(__file__).resolve().parents[1]

# corpora whose data is bundled in the wheel, so they measure live with no network.
_BUNDLED = ("lineara", "linearb", "cypriot", "cyprominoan", "greek")
# the scripts that ship a bundled sign inventory.
_SIGN_SCRIPTS = ("lineara", "linearb", "cypriot", "cyprominoan", "greek")
_NUMERIC_CORPUS = ("documents", "tokens", "words", "ig_xv1_inscriptions")
_NUMERIC_SIGN = ("signs", "with_sound_values", "read")


def _registry() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (ROOT / "training/results/corpus-facts.json").read_text(encoding="utf-8")
    )
    return data


def _measure_corpus(corpus_id: str) -> dict[str, int]:
    """Documents / tokens / words of a loaded corpus, the way the registry counts them."""
    corpus = aegean.load(corpus_id)
    return {
        "documents": len(corpus),
        "tokens": sum(len(d.tokens) for d in corpus),
        "words": sum(len(d.words) for d in corpus),
    }


def _inventories() -> dict[str, Any]:
    from aegean.scripts.cypriot.inventory import cypriot_inventory
    from aegean.scripts.cyprominoan.inventory import cyprominoan_inventory
    from aegean.scripts.greek.inventory import greek_inventory
    from aegean.scripts.lineara.inventory import linear_a_inventory
    from aegean.scripts.linearb.inventory import linear_b_inventory

    return {
        "lineara": linear_a_inventory(),
        "linearb": linear_b_inventory(),
        "cypriot": cypriot_inventory(),
        "cyprominoan": cyprominoan_inventory(),
        "greek": greek_inventory(),
    }


def _measure_inventory(inv) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """The registry's sign facts: total signs, signs carrying a sound value, and read signs
    (those with alignment evidence, ``attrs["source"] != "ucd"``; Linear A's unaligned
    Unicode-chart entries are the only ones marked ``ucd``)."""
    aligned = [s for s in inv if s.attrs.get("source") != "ucd"]
    return {
        "signs": len(inv),
        "with_sound_values": sum(1 for s in inv if s.phonetic),
        "read": len(aligned),
    }


def _num(text: str) -> int:
    return int(text.replace(",", "").strip())


def _fact_value(reg: dict[str, Any], fact: str) -> int:
    section, corpus_id, metric = fact.split(".")
    value: int = reg[section][corpus_id][metric]
    return value


# ── (a) the bundled corpora and inventories measure to the registry ──────────────────
def test_bundled_corpora_measure_to_the_registry() -> None:
    reg = _registry()["corpora"]
    for corpus_id in _BUNDLED:
        got = _measure_corpus(corpus_id)
        row = reg[corpus_id]
        for metric in ("documents", "tokens", "words"):
            assert got[metric] == row[metric], (
                f"{corpus_id}.{metric}: measured {got[metric]} vs registry {row[metric]} "
                "— re-measure and update training/results/corpus-facts.json and the doc echoes"
            )


def test_cypriot_ig_xv1_subcount_measures_to_the_registry() -> None:
    """The bundled Cypriot corpus is the 178 IG XV 1 inscriptions plus 2 illustrative
    samples (180 total); the 178 sub-count is stated across the docs, so it is pinned too."""
    reg = _registry()["corpora"]["cypriot"]
    ig_count = len(load_bundled_json("cypriot", "ig_inscriptions.json"))
    assert ig_count == reg["ig_xv1_inscriptions"]
    sample_count = len(load_bundled_json("cypriot", "sample_inscriptions.json"))
    assert ig_count + sample_count == reg["documents"]


def test_bundled_sign_inventories_measure_to_the_registry() -> None:
    reg = _registry()["sign_inventories"]
    for name, inv in _inventories().items():
        got = _measure_inventory(inv)
        row = reg[name]
        for metric in _NUMERIC_SIGN:
            assert got[metric] == row[metric], (
                f"{name} sign inventory {metric}: measured {got[metric]} vs registry {row[metric]}"
            )


# ── (b) every doc echo shows the registry value ─────────────────────────────────────
def test_every_doc_echo_matches_the_registry() -> None:
    reg = _registry()
    for echo in reg["echoes"]:
        path = ROOT / echo["file"]
        assert path.exists(), f"echo file missing: {echo['file']}"
        text = path.read_text(encoding="utf-8")
        matches = re.findall(echo["pattern"], text)
        assert matches, (
            f"echo site not found ({echo['fact']} in {echo['file']}): "
            f"/{echo['pattern']}/ — the doc was reworded or removed; update the registry echo"
        )
        want = _fact_value(reg, echo["fact"])
        for m in matches:
            assert _num(m) == want, (
                f"{echo['file']}: {echo['fact']} echo says {m!r} but the registry says {want} "
                "— fix the doc and the registry together"
            )


# ── (c) the registry is internally consistent and complete ──────────────────────────
def test_registry_covers_every_loadable_corpus_and_bundled_inventory() -> None:
    reg = _registry()
    from aegean.core.corpus import _LOADERS
    from aegean.tui.data import CORPUS_IDS

    # the browsable corpora plus ddbdp (excluded from the TUI list only) are the 14 loadable
    # ones; every one must carry a fact row, and there must be no phantom rows.
    expected = set(CORPUS_IDS) | {"ddbdp"}
    assert set(reg["corpora"]) == expected, (
        "corpus-facts.json corpora do not match the loadable set; a new corpus needs a fact row"
    )
    for corpus_id in reg["corpora"]:
        assert corpus_id in _LOADERS, f"{corpus_id} is not a registered loader"
    assert set(reg["sign_inventories"]) == set(_SIGN_SCRIPTS)


def test_registry_facts_are_positive_ints() -> None:
    reg = _registry()
    for corpus_id, row in reg["corpora"].items():
        assert isinstance(row["measured_from"], str) and row["measured_from"] in {
            "bundled",
            "cached-asset",
        }, corpus_id
        for metric in _NUMERIC_CORPUS:
            if metric in row:
                value = row[metric]
                assert isinstance(value, int) and value > 0, f"{corpus_id}.{metric} = {value}"
    for name, row in reg["sign_inventories"].items():
        for metric in _NUMERIC_SIGN:
            value = row[metric]
            # cyprominoan is undeciphered: 0 signs carry a sound value (a valid count).
            assert isinstance(value, int) and value >= 0, f"{name}.{metric} = {value}"
        assert row["signs"] > 0 and row["read"] > 0, name


def test_every_echo_is_well_formed() -> None:
    reg = _registry()
    for echo in reg["echoes"]:
        # the fact must resolve to an int in the registry
        assert isinstance(_fact_value(reg, echo["fact"]), int), echo["fact"]
        # exactly one capture group, so re.findall yields the number the test compares
        assert re.compile(echo["pattern"]).groups == 1, (
            f"echo pattern must have exactly one capture group: {echo['pattern']!r}"
        )
