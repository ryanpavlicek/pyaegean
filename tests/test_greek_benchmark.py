"""The Greek benchmark harness: scores the pipeline against the bundled gold
set and compares an arbitrary (e.g. CLTK) lemmatizer on the same gold."""

from __future__ import annotations

import pytest

from aegean.greek import benchmark


def test_run_benchmark_returns_a_score_per_stage():
    scores = benchmark.run_benchmark()
    assert set(scores) == {
        "betacode", "tokenize", "syllabify", "accent", "lemma", "pos", "scansion", "morphology",
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
    assert scores["betacode"].accuracy == 1.0


def test_seed_lemmatizer_covers_its_easy_core():
    # The hand-curated seed table is correct for the regular forms it covers.
    from aegean.greek import lemmatize

    core = {
        "lemma": [
            {"word": "λόγου", "lemma": "λόγος"},
            {"word": "ἦν", "lemma": "εἰμί"},
            {"word": "θεόν", "lemma": "θεός"},
            {"word": "πάντα", "lemma": "πᾶς"},
            {"word": "ἀνθρώπων", "lemma": "ἄνθρωπος"},
        ]
    }
    assert benchmark.score_lemmatizer(lemmatize, core).accuracy == 1.0


def test_baseline_has_headroom_on_full_gold():
    # The grown gold includes irregular/open-class forms the seed/rule baseline
    # misses — that gap (below 100%) is what the treebank backend closes.
    s = benchmark.run_benchmark()
    assert s["lemma"].accuracy < 1.0
    assert s["pos"].accuracy < 1.0


def test_compare_against_a_candidate_lemmatizer():
    cmp = benchmark.compare_lemmatizers(lambda w: w)  # naive: never inflects
    assert cmp["candidate"].accuracy == 0.0
    assert cmp["pyaegean"].accuracy > cmp["candidate"].accuracy


def test_custom_gold_is_honored():
    from aegean.greek import lemmatize

    gold = {"lemma": [{"word": "λόγου", "lemma": "λόγος"}]}
    s = benchmark.score_lemmatizer(lemmatize, gold)
    assert s.total == 1 and s.correct == 1


def test_score_pos_and_compare_pos_taggers():
    from aegean.greek import pos_tag

    assert benchmark.score_pos(pos_tag).accuracy > 0.0
    cmp = benchmark.compare_pos_taggers(lambda w: "X")  # a tagger that's never right
    assert cmp["candidate"].accuracy == 0.0
    assert cmp["pyaegean"].accuracy > cmp["candidate"].accuracy


def test_compare_modes_shows_treebank_lift(tmp_path, monkeypatch):
    # Offline: build a small lexicon from the synthetic AGDT fixture into a temp
    # cache, then confirm the treebank backend scores at least as well as the
    # baseline (strictly better on lemma, where the fixture covers ἄνδρα→ἀνήρ).
    import pathlib

    from aegean.greek import treebank
    from aegean.greek.treebank import build_lexicon

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    fixture = pathlib.Path(__file__).parent / "fixtures" / "agdt"
    build_lexicon(source_dir=fixture, force=True)
    try:
        res = benchmark.compare_modes(build=False)
    finally:
        treebank.disable_treebank()
    assert res["treebank"]["lemma"].correct > res["baseline"]["lemma"].correct
    assert res["treebank"]["pos"].correct >= res["baseline"]["pos"].correct


def test_cltk_comparison_runs_if_installed():
    """Documents the cross-tool comparison. CLTK is a benchmark target, never a
    dependency. CLTK 2.x runs Ancient Greek through a stanza/LLM backend, so this
    *skips* (rather than fails) whenever CLTK, that backend, or its models aren't
    available — which is the common case in CI and most dev envs."""
    pytest.importorskip("cltk")
    from cltk import NLP

    try:
        nlp = NLP(language_code="grc", suppress_banner=True)

        def cltk_lemma(word: str) -> str:
            doc = nlp.analyze(text=word)
            return doc.words[0].lemma if doc.words else word

        cmp = benchmark.compare_lemmatizers(cltk_lemma)
    except Exception as exc:
        pytest.skip(f"CLTK grc backend unavailable: {type(exc).__name__}: {exc}")
    assert 0.0 <= cmp["candidate"].accuracy <= 1.0
    assert 0.0 <= cmp["pyaegean"].accuracy <= 1.0
