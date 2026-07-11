"""Regression tests for the R33 hands/dossiers correctness pass.

Covers three fixes in :mod:`aegean.analysis.hands` and its CLI wiring:

1. ``dossiers`` (and the series breakdown in the hand groupings) is defined for
   Linear B designations only, so a non-Linear-B corpus errors cleanly instead of
   inventing a dossier out of an unrelated id scheme (e.g. an ``IG XV 1, 217``
   inscription number). ``series_of`` stays a pure parser.
2. A grouping key is one distinct editorial attribution string (a hand number,
   possibly qualified), not one distinct scribe: qualified attributions are counted
   separately, never silently merged.
3. A residual / unconventional series prefix is grouped as parsed, not dropped and
   not asserted to be an attested archival set.

All offline (bundled corpora + hand-built fixtures). Assertions verify the actual
output (known answers / property invariants), not merely that a call runs.
"""

from __future__ import annotations

import pytest

import aegean
from aegean.analysis.hands import by_hand, dossiers, hand_profile, series_of
from aegean.core.corpus import Corpus


# ── Finding 1: series grouping is Linear B only ──────────────────────────────


def test_dossiers_rejects_non_linear_b_corpus() -> None:
    # cypriot ids look like "IG XV 1, 1"; without the guard the parser reads "XV"
    # and invents archival dossiers. The guard must refuse the whole corpus.
    cypriot = aegean.load("cypriot")
    assert cypriot.script_id != "linearb"
    with pytest.raises(ValueError, match="Linear B"):
        dossiers(cypriot)


def test_dossiers_still_works_on_linear_b() -> None:
    # The guard must not disturb the legitimate Linear B path (known answers from
    # the bundled linearb sample).
    result = dossiers(aegean.load("linearb"))
    by_key = {(d.site, d.series): d.doc_count for d in result}
    assert by_key[("Knossos", "Np")] == 3
    assert by_key[("Mycenae", "Ge")] == 3


def test_series_of_is_a_pure_parser() -> None:
    # series_of does not check the script: it reads whatever second field the id
    # carries, so an inscription number still parses (that is exactly why dossiers
    # has to guard). This pins the "pure parser" contract.
    assert series_of("IG XV 1, 217") == "XV"
    assert series_of("KN Fp(1) 1 (138)") == "Fp"
    assert series_of("HT1") is None  # single-token Linear A id: no series


def _designation_corpus(script_id: str) -> Corpus:
    # Same ids/hands under two scripts, so only the script gate can change the
    # series breakdown.
    return Corpus.from_records(
        [
            {"id": "IG XV 1, 1", "text": "a b", "meta": {"site": "Amathus", "scribe": "S1"}},
            {"id": "IG XV 1, 2", "text": "c d", "meta": {"site": "Amathus", "scribe": "S1"}},
        ],
        script_id=script_id,
    )


def test_by_hand_series_breakdown_is_linear_b_only() -> None:
    # On a non-Linear-B corpus the series breakdown must be empty (no spurious "XV"),
    # while the hand grouping itself still works.
    non_lb = by_hand(_designation_corpus("cypriot"))
    assert [g.hand for g in non_lb] == ["S1"]
    assert non_lb[0].series == {}
    assert non_lb[0].doc_count == 2  # the tablets are still counted

    # The identical ids under linearb DO get the series breakdown.
    lb = by_hand(_designation_corpus("linearb"))
    assert lb[0].series == {"XV": 2}


def test_hand_profile_series_breakdown_is_linear_b_only() -> None:
    non_lb = hand_profile(_designation_corpus("cypriot"), "S1")
    assert non_lb.series == {}
    assert non_lb.doc_count == 2

    lb = hand_profile(_designation_corpus("linearb"), "S1")
    assert lb.series == {"XV": 2}


# ── Finding 2: grouping keys are attribution strings, not scribes ────────────


def _qualified_hands_corpus() -> Corpus:
    return Corpus.from_records(
        [
            {"id": "KN Da 1156 (117)", "text": "a-ko-ra", "meta": {"site": "Knossos", "scribe": "117"}},
            {"id": "KN Da 1157 (117)", "text": "qe-to", "meta": {"site": "Knossos", "scribe": "117"}},
            {"id": "KN Db 1196 (117?)", "text": "ki-ri", "meta": {"site": "Knossos", "scribe": "117?"}},
            {"id": "KN Dv 1234 (124-S)", "text": "ko-wa", "meta": {"site": "Knossos", "scribe": "124-S"}},
        ],
        script_id="linearb",
    )


def test_by_hand_counts_distinct_attribution_strings_not_scribes() -> None:
    # "117", "117?" and "124-S" are three distinct attribution strings. A qualified
    # attribution must NOT be folded into the bare hand number, so the group count is
    # the number of distinct attribution strings, not of distinct scribes.
    groups = by_hand(_qualified_hands_corpus())
    hands = {g.hand for g in groups}
    assert hands == {"117", "117?", "124-S"}
    assert len(groups) == 3
    # The bare "117" attribution has its two tablets; "117?" is separate.
    by_key = {g.hand: g.doc_count for g in groups}
    assert by_key["117"] == 2
    assert by_key["117?"] == 1


# ── Finding 3: residual prefixes are grouped as parsed, not claimed ──────────


def test_residual_prefix_is_grouped_as_parsed() -> None:
    # A single-capital "X" (the unclassified-fragment class) is a residual prefix.
    # It must be grouped as parsed (present in the output), the honest behavior the
    # softened framing describes; it is neither dropped nor merged with real series.
    corpus = Corpus.from_records(
        [
            {"id": "KN X 9873 (-)", "text": "a-ko-ra", "meta": {"site": "Knossos", "scribe": "999"}},
            {"id": "KN Da 1156 (117)", "text": "qe-to", "meta": {"site": "Knossos", "scribe": "117"}},
        ],
        script_id="linearb",
    )
    keys = {(d.site, d.series) for d in dossiers(corpus)}
    assert ("Knossos", "X") in keys
    assert ("Knossos", "Da") in keys


# ── CLI surfacing ────────────────────────────────────────────────────────────


def test_cli_dossiers_non_linear_b_is_clean_error() -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), ["analyze", "dossiers", "cypriot"])
    assert r.exit_code != 0
    assert "Linear B" in r.output
    # No raw traceback leaked to the user.
    assert "Traceback" not in r.output
