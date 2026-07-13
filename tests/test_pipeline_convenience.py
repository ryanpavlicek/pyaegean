"""The one-call `greek.pipeline()` convenience layer (offline; baseline + stubbed joint)."""

from __future__ import annotations

import pytest

from aegean import greek
from aegean.greek import LemmaSource, TokenRecord


def test_pipeline_baseline_records():
    recs = greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος. καὶ θεός ἦν ὁ λόγος.")
    assert all(isinstance(r, TokenRecord) for r in recs)
    assert {r.sentence for r in recs} == {0, 1}
    assert [r.text for r in recs if r.sentence == 0] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος", "."]
    first = recs[0]
    assert (first.text, first.upos, first.lemma) == ("ἐν", "ADP", "ἐν")
    assert first.index == 1 and first.head is None and first.relation is None
    assert first.xpos is None and first.feats is None  # neural-only fields
    assert first.lemma_source is LemmaSource.SEED and first.lemma_resolved
    assert first.lemma_verified is False and first.review_recommended is False


def test_pipeline_records_carry_the_lemma_source_class():
    # νόμου is recovered by the rule layer; πατρός is outside the baseline's scope.
    by_text = {r.text: r for r in greek.pipeline("νόμου πατρός.")}
    assert by_text["νόμου"].lemma_source is LemmaSource.RULE
    assert by_text["νόμου"].lemma == "νόμος" and by_text["νόμου"].lemma_resolved
    assert by_text["πατρός"].lemma_source is LemmaSource.UNRESOLVED
    assert by_text["πατρός"].lemma_resolved is False
    assert by_text["πατρός"].review_recommended is True
    assert by_text["."].lemma_source is LemmaSource.PUNCT


def test_pipeline_keeps_punctuation_as_records():
    recs = greek.pipeline("ἦν ὁ λόγος.")
    assert recs[-1].text == "." and recs[-1].upos == "PUNCT"
    assert recs[-1].lemma == "." and recs[-1].lemma_resolved  # punct is its own lemma
    assert recs[-1].lemma_source is LemmaSource.PUNCT


def test_pipeline_indexes_restart_per_sentence():
    recs = greek.pipeline("ἦν ὁ λόγος. καὶ θεός.")
    second = [r for r in recs if r.sentence == 1]
    assert [r.index for r in second] == list(range(1, len(second) + 1))


def test_pipeline_empty_text():
    assert greek.pipeline("") == []
    assert greek.pipeline("   ") == []


def test_pipeline_parse_requires_a_parser():
    with pytest.raises(greek.ParserNotLoadedError):
        greek.pipeline("ἦν ὁ λόγος.", parse=True)


def test_pipeline_uses_the_joint_model_when_active(monkeypatch):
    pytest.importorskip("numpy")
    from aegean.greek import joint
    from test_joint import _stub_model

    monkeypatch.setattr(joint, "_ACTIVE", _stub_model())
    recs = greek.pipeline("ὁ λόγος ἐστί")
    assert [r.upos for r in recs] == ["DET", "NOUN", "VERB"]
    assert [r.lemma for r in recs] == ["ὁ", "λόγος", "εἰμί"]
    assert [r.head for r in recs] == [2, 3, 0]  # filled without parse=True
    assert [r.relation for r in recs] == ["det", "nsubj", "root"]  # UD labels
    assert all(r.xpos is not None and r.feats is not None for r in recs)
    # ὁ and ἐστί resolve via the model's lookups (NEURAL, known); λόγος comes out of the
    # edit script equal to its surface form with no lookup confirming it, so it is the
    # honest IDENTITY fall-through (needs review), not a grounded neural lemma
    assert [r.lemma_resolved for r in recs] == [True, False, True]
    assert [r.lemma_source for r in recs] == [
        LemmaSource.NEURAL_LOOKUP, LemmaSource.IDENTITY, LemmaSource.NEURAL_LOOKUP,
    ]


def test_lemma_known_is_a_deprecated_compatibility_alias():
    rec = greek.pipeline("πατρός")[0]
    with pytest.deprecated_call(match="lemma_resolved"):
        assert rec.lemma_known is rec.lemma_resolved
