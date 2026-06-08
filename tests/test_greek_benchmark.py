"""The Greek benchmark harness: scores the pipeline against the bundled gold
set and compares an arbitrary (e.g. CLTK) lemmatizer on the same gold."""

from __future__ import annotations

import pytest

from aegean.greek import benchmark


def test_run_benchmark_returns_a_score_per_stage():
    scores = benchmark.run_benchmark()
    assert set(scores) == {
        "tokenize", "syllabify", "accent", "lemma", "pos", "scansion", "morphology",
    }
    for s in scores.values():
        assert s.total > 0
        assert 0 <= s.correct <= s.total
        assert 0.0 <= s.accuracy <= 1.0


def test_deterministic_stages_match_gold_exactly():
    # tokenize/syllabify/accent are deterministic and correct against the
    # independently-authored gold, so they should score 100%.
    scores = benchmark.run_benchmark()
    assert scores["tokenize"].accuracy == 1.0
    assert scores["syllabify"].accuracy == 1.0
    assert scores["accent"].accuracy == 1.0
    assert scores["scansion"].accuracy == 1.0


def test_seed_lemmatizer_covers_gold():
    # The (hand-curated, correctly-accented) seed table covers the lemma gold;
    # the seed is still a baseline, not a full lemmatizer (real coverage comes
    # from the treebank-derived lexicon — see docs/PLAN.md).
    s = benchmark.run_benchmark()["lemma"]
    assert s.accuracy == 1.0


def test_compare_against_a_candidate_lemmatizer():
    cmp = benchmark.compare_lemmatizers(lambda w: w)  # naive: never inflects
    assert cmp["candidate"].accuracy == 0.0
    assert cmp["pyaegean"].accuracy > cmp["candidate"].accuracy


def test_custom_gold_is_honored():
    from aegean.greek import lemmatize

    gold = {"lemma": [{"word": "λόγου", "lemma": "λόγος"}]}
    s = benchmark.score_lemmatizer(lemmatize, gold)
    assert s.total == 1 and s.correct == 1


def test_cltk_comparison_runs_if_installed():
    """Documents the cross-tool comparison. Skipped unless CLTK is installed —
    CLTK is a benchmark target, never a dependency."""
    cltk = pytest.importorskip("cltk")
    nlp = cltk.NLP(language="grc", suppress_banner=True)

    def cltk_lemma(word: str) -> str:
        doc = nlp.analyze(text=word)
        return doc.lemmata[0] if doc.lemmata else word

    cmp = benchmark.compare_lemmatizers(cltk_lemma)
    assert 0.0 <= cmp["candidate"].accuracy <= 1.0
    assert 0.0 <= cmp["pyaegean"].accuracy <= 1.0
