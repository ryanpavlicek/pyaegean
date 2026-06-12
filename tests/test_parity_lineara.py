"""Ported analysis run over the real bundled Linear A corpus (1,721 docs).

Spot-checks that the algorithms behave sensibly end-to-end on real data, not
just on the hand-built golden fixtures. These are sanity invariants, not
decipherment claims — the corpus is undeciphered.
"""

from __future__ import annotations

import aegean
from aegean.analysis import (
    extract_root,
    find_morphological_clusters,
    phonetic_distance,
    word_matches_sign_pattern,
)


def test_corpus_loads():
    corpus = aegean.load("lineara")
    assert len(corpus) == 1721


def test_word_frequencies_and_root_on_real_words():
    corpus = aegean.load("lineara")
    freqs = corpus.word_frequencies()
    assert freqs and all(c > 0 for _, c in freqs)
    # KU-RO ("total") is one of the most frequent multi-sign words.
    words = {w for w, _ in freqs}
    assert "KU-RO" in words
    assert extract_root("KU-RO") == "kr"


def test_phonetic_distance_is_a_metric_on_real_vocab():
    corpus = aegean.load("lineara")
    sample = [w for w, _ in corpus.word_frequencies()[:30]]
    for w in sample:
        assert phonetic_distance(w.lower(), w.lower()) == 0
    a, b = sample[0].lower(), sample[1].lower()
    assert phonetic_distance(a, b) == phonetic_distance(b, a)
    assert 0 <= phonetic_distance(a, b) <= 1


def test_sign_pattern_search_over_corpus():
    corpus = aegean.load("lineara")
    hits = [w for w, _ in corpus.word_frequencies() if word_matches_sign_pattern(w, "KU-*-RO")]
    # KU-?-RO words exist (e.g. compounds around the KU-RO accounting term).
    assert all(w.split("-")[0] == "KU" and w.split("-")[-1] == "RO" for w in hits)


def test_morphology_clusters_on_real_corpus():
    corpus = aegean.load("lineara")
    clusters = find_morphological_clusters(corpus.word_frequencies())
    # The real vocabulary yields some productive-suffix clusters at defaults.
    assert clusters
    for c in clusters:
        assert len(c.members) >= 2
        assert c.total_count == sum(m.count for m in c.members)
