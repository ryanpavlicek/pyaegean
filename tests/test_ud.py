"""Tests for aegean.greek.ud — the UD/CoNLL-U evaluation harness.

The fixture is a 2-sentence mini fold whose ``sent_id``s reference a mini AGDT file, so
the leakage-overlap builder is exercised end-to-end offline. The one network-dependent
piece — the official conll18 evaluator — is fetched once and the test skips if offline
(the EpiDoc-schema test pattern)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.greek.ud import UDSentence, agdt_ud_overlap, load_conllu, pipeline_conllu

FIXTURE = Path(__file__).parent / "fixtures" / "ud"
CONLLU = FIXTURE / "sample-ud-test.conllu"


def test_load_conllu_skips_mwt_and_empty_nodes() -> None:
    sents = load_conllu(CONLLU)
    assert len(sents) == 2
    first = sents[0]
    assert isinstance(first, UDSentence)
    assert first.sent_id == "sample.tb.xml@1"
    assert [t.form for t in first.tokens] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]  # 4-5 and 5.1 skipped
    assert [t.head for t in first.tokens] == [3, 3, 0, 5, 3]
    assert first.tokens[0].upos == "ADP" and first.tokens[2].deprel == "root"
    assert sents[1].tokens[-1].upos == "PUNCT"


def test_pipeline_conllu_gold_tokenization() -> None:
    sents = load_conllu(CONLLU)
    out = pipeline_conllu(sents, parse=False)
    rows = [ln.split("\t") for ln in out.splitlines() if ln and not ln.startswith("#")]
    assert all(len(r) == 10 for r in rows)  # CoNLL-U has exactly 10 columns
    assert [r[1] for r in rows[:5]] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]  # gold FORMs preserved
    assert rows[0][3] == "ADP" and rows[3][3] == "DET"  # closed-class cascade
    assert rows[-1][3] == "PUNCT"
    assert all(r[2] for r in rows)  # a lemma is always emitted


def test_agdt_ud_overlap_builds_verified_manifest(tmp_path: Path) -> None:
    manifest = agdt_ud_overlap(
        splits=("test",), source=CONLLU, agdt_source=FIXTURE, write=False
    )
    assert manifest["files"] == {"sample.tb.xml": ["1", "2"]}
    assert manifest["n_sentences"] == 2
    # both sentences resolve into the AGDT fixture and match form-for-form
    assert manifest["verified"] == {"checked": 2, "form_identical": 2}


def test_evaluate_on_ud_against_fixture() -> None:
    """End-to-end through the official evaluator (skips offline)."""
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR, evaluate_on_ud

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            from aegean.greek.ud import _eval_module

            _eval_module()
        except Exception as exc:
            pytest.skip(f"official evaluator unavailable offline: {exc}")
    res = evaluate_on_ud("perseus", "test", source=CONLLU, parse=False)
    assert res["n_sentences"] == 2 and res["n_words"] == 8
    assert 0.0 <= res["upos"] <= 1.0 and 0.0 <= res["lemma"] <= 1.0
    assert res["uas"] is None and res["las"] is None  # parse=False → not meaningful
    assert res["upos"] >= 0.5  # closed classes + PUNCT alone clear this on the fixture
