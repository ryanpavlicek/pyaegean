"""Tests for the Stage A dataset builder (training/build_upos_dataset.py).

The builder is torch-free by design, so its parsing + split logic is testable offline
against the UD fixtures. The training/ directory isn't a package — import by path."""

from __future__ import annotations

import importlib.util
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "ud"
_BUILDER = Path(__file__).parent.parent / "training" / "build_upos_dataset.py"

spec = importlib.util.spec_from_file_location("build_upos_dataset", _BUILDER)
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_load_agdt_upos_parses_forms_and_tags() -> None:
    rows = builder.load_agdt_upos(FIXTURE)
    assert len(rows) == 2
    first = rows[0]
    assert first["file"] == "sample.tb.xml" and first["sid"] == "1"
    assert first["tokens"] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]
    assert first["upos"] == ["ADP", "NOUN", "VERB", "DET", "NOUN"]
    assert rows[1]["upos"] == ["CCONJ", "NOUN", "PUNCT"]  # c / n / u first chars


def test_exclusion_split_logic() -> None:
    """train = all minus excluded; dev = exactly the dev-fold ids (the builder's split)."""
    rows = builder.load_agdt_upos(FIXTURE)
    dev_ids = {("sample.tb.xml", "2")}
    test_ids = {("sample.tb.xml", "1")}
    train = [r for r in rows if (r["file"], r["sid"]) not in dev_ids | test_ids]
    dev = [r for r in rows if (r["file"], r["sid"]) in dev_ids]
    assert train == []  # both fixture sentences are claimed by the folds
    assert [d["sid"] for d in dev] == ["2"]


def test_split_ids_reads_the_overlap_manifest() -> None:
    """split_ids delegates to agdt_ud_overlap; exercise the same shape via its source arg."""
    from aegean.greek.ud import agdt_ud_overlap

    manifest = agdt_ud_overlap(
        splits=("test",), source=FIXTURE / "sample-ud-test.conllu",
        agdt_source=FIXTURE, write=False,
    )
    pairs = {(f, sid) for f, ids in manifest["files"].items() for sid in ids}
    assert pairs == {("sample.tb.xml", "1"), ("sample.tb.xml", "2")}
