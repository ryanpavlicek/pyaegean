"""Scribal-hand + archival-series tooling (aegean.analysis.hands).

Correctness on a hand-built Linear B fixture with known answers, plus the bundled
``linearb`` sample (offline; DAMOS is fetch-only so never used in tests) and the
``analyze dossiers`` / ``analyze hand`` CLI commands.
"""

from __future__ import annotations

import json

import pytest

from aegean.analysis.hands import (
    HandGroup,
    HandReport,
    SeriesDossier,
    by_hand,
    dossiers,
    hand_profile,
    series_of,
)
from aegean.core.corpus import Corpus


def _corpus() -> Corpus:
    return Corpus.from_records(
        [
            {"id": "KN Da 1156 (117)", "text": "a-ko-ra qe-to",
             "meta": {"site": "Knossos", "scribe": "117", "period": "LM IIIA"}},
            {"id": "KN Da 1157 (117)", "text": "a-ko-ra ki-ri",
             "meta": {"site": "Knossos", "scribe": "117", "period": "LM IIIA"}},
            {"id": "KN Db 1196 + 8233 (117)", "text": "a-ko-ra",
             "meta": {"site": "Knossos", "scribe": "117", "period": "LM IIIA"}},
            {"id": "KN Fp(1) 1 (138)", "text": "pa-de e-ra",
             "meta": {"site": "Knossos", "scribe": "138", "period": "LM IIIB"}},
            {"id": "PY Aa 62", "text": "ko-wa",
             "meta": {"site": "Pylos", "scribe": ""}},        # no hand -> skipped by by_hand
            {"id": "SID 1 (-)", "text": "foo",
             "meta": {"site": "Nowhere", "scribe": ""}},       # no parseable series
        ],
        script_id="linearb",
    )


# ── series_of ────────────────────────────────────────────────────────────────


def test_series_of_parses_designation() -> None:
    assert series_of("KN Fp(1) 1 + 31 (138)") == "Fp"   # sub-set marker folded to parent
    assert series_of("PY Ta 641") == "Ta"
    assert series_of("KN Db 1196 + 8233 (117)") == "Db"
    assert series_of("KN X 9873 (-)") == "X"


def test_series_of_no_series_is_none() -> None:
    assert series_of("SID 1 (-)") is None       # only a site code + number
    assert series_of("KN") is None              # nothing after the site code
    assert series_of("") is None


def test_series_of_accepts_document_or_string() -> None:
    doc = _corpus().documents[0]
    assert series_of(doc) == series_of(doc.id) == "Da"


# ── by_hand ──────────────────────────────────────────────────────────────────


def test_by_hand_groups_with_site_and_series() -> None:
    groups = by_hand(_corpus())
    assert isinstance(groups[0], HandGroup)
    assert [g.hand for g in groups] == ["117", "138"]     # tablet count desc
    h117 = groups[0]
    assert h117.doc_count == 3
    assert h117.sites == {"Knossos": 3}
    assert h117.series == {"Da": 2, "Db": 1}              # most-common first
    assert h117.periods == {"LM IIIA": 3}
    assert h117.doc_ids == ["KN Da 1156 (117)", "KN Da 1157 (117)", "KN Db 1196 + 8233 (117)"]


def test_by_hand_skips_documents_without_a_hand() -> None:
    hands = {g.hand for g in by_hand(_corpus())}
    assert hands == {"117", "138"}                        # PY Aa 62 / SID 1 (no scribe) dropped


def test_by_hand_min_docs() -> None:
    assert [g.hand for g in by_hand(_corpus(), min_docs=2)] == ["117"]


def test_by_hand_empty_corpus() -> None:
    assert by_hand(Corpus([], script_id="linearb")) == []


# ── hand_profile ─────────────────────────────────────────────────────────────


def test_hand_profile_counts_and_vocabulary() -> None:
    rep = hand_profile(_corpus(), "117")
    assert isinstance(rep, HandReport)
    assert rep.doc_count == 3
    assert rep.token_count == 5 and rep.word_count == 5
    assert rep.series == {"Da": 2, "Db": 1}
    assert rep.sites == {"Knossos": 3}
    assert rep.top_words[0] == ("a-ko-ra", 3)             # most frequent lexical word


def test_hand_profile_top_n_limits_vocabulary() -> None:
    rep = hand_profile(_corpus(), "117", top_n=1)
    assert rep.top_words == [("a-ko-ra", 3)]
    assert rep.word_count == 5                            # count is over the whole slice


def test_hand_profile_unknown_hand_raises() -> None:
    with pytest.raises(ValueError, match="no documents attributed"):
        hand_profile(_corpus(), "999")


# ── dossiers ─────────────────────────────────────────────────────────────────


def test_dossiers_group_by_site_and_series() -> None:
    result = dossiers(_corpus())
    assert isinstance(result[0], SeriesDossier)
    keys = [(d.site, d.series, d.doc_count) for d in result]
    assert keys[0] == ("Knossos", "Da", 2)               # count desc, then site, series
    assert ("Knossos", "Db", 1) in keys
    assert ("Knossos", "Fp", 1) in keys
    assert ("Pylos", "Aa", 1) in keys
    da = result[0]
    assert da.hands == {"117": 2}
    assert da.doc_ids == ["KN Da 1156 (117)", "KN Da 1157 (117)"]
    assert da.token_count == 4 and da.word_count == 4


def test_dossiers_exclude_unparseable_series() -> None:
    # SID 1 (-) has no series, so it belongs to no dossier
    assert not any("Nowhere" in (d.site,) for d in dossiers(_corpus()))
    assert all(d.series for d in dossiers(_corpus()))


def test_dossiers_min_docs() -> None:
    assert [(d.site, d.series) for d in dossiers(_corpus(), min_docs=2)] == [("Knossos", "Da")]


def test_dossiers_empty_corpus() -> None:
    assert dossiers(Corpus([], script_id="linearb")) == []


# ── against the bundled linearb sample (offline) ─────────────────────────────


def test_dossiers_on_bundled_linearb_sample() -> None:
    import aegean

    result = dossiers(aegean.load("linearb"))
    by_key = {(d.site, d.series): d for d in result}
    assert by_key[("Knossos", "Np")].doc_count == 3      # KN Np 267 / 272 / 85
    assert by_key[("Mycenae", "Ge")].doc_count == 3


# ── CLI ──────────────────────────────────────────────────────────────────────


def _run(args: list[str]) -> str:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), args)
    assert r.exit_code == 0, r.output
    return r.stdout


def test_cli_dossiers_json() -> None:
    rows = json.loads(_run(["analyze", "dossiers", "linearb", "--json"]))
    by_key = {(row["site"], row["series"]): row for row in rows}
    assert by_key[("Knossos", "Np")]["doc_count"] == 3
    assert by_key[("Mycenae", "Ge")]["doc_count"] == 3


def test_cli_hand_json() -> None:
    data = json.loads(_run(["analyze", "hand", "linearb", "Hand 2", "--json"]))
    assert data["hand"] == "Hand 2"
    assert data["doc_count"] == 1
    assert data["series"] == {"Ta": 1}                   # PY Ta 641


def test_cli_dossiers_non_linear_b_errors() -> None:
    # dossiers is defined for Linear B designations only; a non-Linear-B corpus must
    # error cleanly (never invent a dossier out of an unrelated id, never a traceback)
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), ["analyze", "dossiers", "lineara"])
    assert r.exit_code != 0
    assert "Linear B" in r.output
