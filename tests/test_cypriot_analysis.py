"""Cypriot descriptive analysis (aegean.scripts.cypriot.analysis).

Numbers pinned to the bundled Inscriptiones Graecae XV 1 corpus + shipped sign
table / lexicon (all offline), plus the ``analyze syllabary`` / ``analyze bridge``
CLI commands and adversarial (empty-corpus) behaviour.
"""

from __future__ import annotations

import json

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.scripts.cypriot.analysis import (
    BridgeCoverage,
    SyllabaryProfile,
    bridge_coverage,
    syllabary_profile,
)


def _cypriot() -> Corpus:
    return aegean.load("cypriot")


# ── syllabary_profile ────────────────────────────────────────────────────────


def test_syllabary_profile_grid_and_gaps() -> None:
    prof = syllabary_profile(_cypriot())
    assert isinstance(prof, SyllabaryProfile)
    assert prof.grid_size == 55                 # the full Cypriot syllabary grid
    assert prof.attested_count == 54            # every grid cell but one is used
    assert prof.gap_count == 1
    assert prof.gaps == ["XA"]                  # the one unattested grid sign
    assert prof.sign_tokens == 1621             # total syllabogram occurrences


def test_syllabary_profile_sorted_by_frequency() -> None:
    signs = syllabary_profile(_cypriot()).signs
    assert len(signs) == 55
    assert signs[0].label == "SE" and signs[0].count == 108   # most frequent sign
    counts = [s.count for s in signs]
    assert counts == sorted(counts, reverse=True)             # descending
    # the gap sign is present, attested False, count 0
    xa = next(s for s in signs if s.label == "XA")
    assert xa.count == 0 and xa.attested is False


def test_syllabary_profile_defaults_to_bundled_corpus() -> None:
    assert syllabary_profile().grid_size == syllabary_profile(_cypriot()).grid_size == 55


def test_syllabary_profile_empty_corpus_all_gaps() -> None:
    prof = syllabary_profile(Corpus([], script_id="cypriot"))
    assert prof.grid_size == 55                 # falls back to the packaged grid
    assert prof.attested_count == 0
    assert prof.gap_count == 55
    assert prof.sign_tokens == 0


# ── bridge_coverage ──────────────────────────────────────────────────────────


def test_bridge_coverage_totals() -> None:
    cov = bridge_coverage(_cypriot())
    assert isinstance(cov, BridgeCoverage)
    assert cov.word_tokens == 448
    assert cov.read_tokens == 33
    assert cov.coverage_pct == pytest.approx(100 * 33 / 448)
    assert cov.distinct_forms == 355
    assert cov.distinct_read_forms == 10        # 10 of 355 forms are in the lexicon


def test_bridge_coverage_by_status() -> None:
    cov = bridge_coverage(_cypriot())
    assert cov.read_by_status == {"certain": 26, "unclear": 4, "restored": 3}
    assert cov.words_by_status == {"certain": 255, "unclear": 149, "restored": 44}
    # read tokens never exceed the word tokens of the same status
    for status, n in cov.read_by_status.items():
        assert n <= cov.words_by_status[status]


def test_bridge_coverage_readings_sorted_and_correct() -> None:
    cov = bridge_coverage(_cypriot())
    top = cov.readings[0]
    assert (top.form, top.lemma, top.count) == ("e-mi", "εἰμί", 19)   # εἰμί 'I am', 19x
    counts = [r.count for r in cov.readings]
    assert counts == sorted(counts, reverse=True)
    # the flagship king word resolves
    king = next(r for r in cov.readings if r.form == "pa-si-le-u-se")
    assert king.lemma == "βασιλεύς"


def test_bridge_coverage_defaults_to_bundled_corpus() -> None:
    assert bridge_coverage().read_tokens == bridge_coverage(_cypriot()).read_tokens == 33


def test_bridge_coverage_empty_corpus() -> None:
    cov = bridge_coverage(Corpus([], script_id="cypriot"))
    assert cov.word_tokens == 0
    assert cov.read_tokens == 0
    assert cov.coverage_pct == 0.0              # no ZeroDivisionError
    assert cov.readings == []


def test_bridge_coverage_no_readings_when_lexicon_misses() -> None:
    # a corpus of plausible-but-unlisted forms -> zero coverage, no crash
    c = Corpus.from_records(
        [{"id": "x", "words": ["zzz-yyy", "qq-rr"]}], script_id="cypriot"
    )
    cov = bridge_coverage(c)
    assert cov.word_tokens == 2 and cov.read_tokens == 0
    assert cov.coverage_pct == 0.0


# ── CLI ──────────────────────────────────────────────────────────────────────


def _run(args: list[str]) -> str:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), args)
    assert r.exit_code == 0, r.output
    return r.stdout


def test_cli_syllabary_json() -> None:
    data = json.loads(_run(["analyze", "syllabary", "cypriot", "--json"]))
    assert data["grid_size"] == 55
    assert data["attested_count"] == 54
    assert data["gaps"] == ["XA"]


def test_cli_bridge_json() -> None:
    data = json.loads(_run(["analyze", "bridge", "cypriot", "--json"]))
    assert data["word_tokens"] == 448
    assert data["read_tokens"] == 33
    assert data["read_by_status"] == {"certain": 26, "unclear": 4, "restored": 3}
