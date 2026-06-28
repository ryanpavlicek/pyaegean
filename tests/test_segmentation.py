"""Unsupervised Harris morpheme segmentation (analysis.segmentation).

A synthetic corpus with a planted productive suffix: a handful of shared stems,
each appearing both bare and with a common ``-ID`` ending. The successor-variety
curve must spike at the stem/suffix boundary (many stems, one shared suffix), so
the suffix is cut off and rises to the top of the candidate-morph ranking.
"""

from __future__ import annotations

from aegean.analysis.segmentation import Segmentation, candidate_morphs, segment

# Stems that recur across the vocabulary; the productive suffix is the sign "ID".
# Each stem is attested both bare and with the suffix, plus a few unsuffixed
# distractors so the boundary signal comes from real branching, not the planting.
STEMS = ["KA-NU", "PA-RO", "SI-DA", "TU-RE", "WA-KO", "ME-NA", "QI-SU", "ZO-PI"]
SUFFIX = "ID"

SYLLABIC = (
    [stem for stem in STEMS]
    + [f"{stem}-{SUFFIX}" for stem in STEMS]
    + ["KA-NU-WE", "PA-RO-SA", "LO-NE", "DE-RI-KU"]
)


def _seg(word: str, corpus: list[str]) -> Segmentation:
    by_word = {s.word: s for s in segment(corpus)}
    return by_word[word]


class TestUnits:
    def test_syllabic_splits_on_hyphen(self) -> None:
        (s,) = segment(["KU-RO-XX"])
        assert s.units == ("KU", "RO", "XX")

    def test_alphabetic_splits_on_characters(self) -> None:
        (s,) = segment(["logos"])
        assert s.units == tuple("logos")

    def test_empty_and_single_unit_uncut(self) -> None:
        segs = segment(["", "A", "MU"])
        assert segs[0].cuts == () and segs[0].pieces == ()
        assert segs[1].cuts == () and segs[1].pieces == ("A",)
        assert segs[2].cuts == () and segs[2].pieces == ("MU",)


class TestPlantedSuffix:
    def test_suffix_is_cut_off(self) -> None:
        # Each stem+suffix word must be cut exactly at the stem/suffix boundary,
        # leaving the suffix as its own final piece.
        for stem in STEMS:
            word = f"{stem}-{SUFFIX}"
            s = _seg(word, SYLLABIC)
            assert SUFFIX in s.pieces, (word, s.pieces)
            assert s.pieces[-1] == SUFFIX, (word, s.pieces)

    def test_suffix_tops_the_candidate_ranking(self) -> None:
        ranked = candidate_morphs(SYLLABIC, min_count=2)
        assert ranked, "expected at least one recurring candidate morph"
        morph, count = ranked[0]
        assert morph == SUFFIX
        # All eight stems carry it, all distinct words -> count 8.
        assert count == len(STEMS)

    def test_min_count_filters(self) -> None:
        # A suffix on a single word can never reach min_count >= 2.
        corpus = ["KA-NU", "KA-NU-XQ", "PA-RO", "SI-DA"]
        assert candidate_morphs(corpus, min_count=2) == []

    def test_distinct_words_not_token_repeats(self) -> None:
        # Repeating one suffixed word many times must not inflate its count:
        # the morph is borne by distinct word *types*.
        corpus = ["KA-NU", "PA-RO", "KA-NU-ID"] + ["PA-RO-ID"] * 20
        ranked = dict(candidate_morphs(corpus, min_count=2))
        assert ranked.get(SUFFIX) == 2


class TestAlphabetic:
    def test_greek_nominal_suffix_segmented(self) -> None:
        # Shared stems branching into a common -os ending vs bare/other endings.
        stems = ["log", "nom", "top", "kosm", "dem", "anthrop"]
        corpus = (
            [s + "os" for s in stems]
            + [s + "on" for s in stems]
            + [s + "oi" for s in stems[:3]]
        )
        ranked = dict(candidate_morphs(corpus, min_count=3))
        # The three competing endings each branch off a shared stem boundary.
        assert ranked.get("os", 0) >= 3
        sample = _seg("logos", corpus)
        assert "log" in sample.pieces


class TestDeterminismAndShape:
    def test_input_order_and_duplicates_preserved(self) -> None:
        corpus = ["PA-RO-ID", "KA-NU", "PA-RO-ID"]
        segs = segment(corpus)
        assert [s.word for s in segs] == corpus
        assert segs[0] == segs[2]

    def test_pieces_reconstruct_the_word(self) -> None:
        for s in segment(SYLLABIC):
            joiner = "-" if "-" in s.word else ""
            assert joiner.join(s.pieces) == s.word

    def test_cuts_are_in_range_and_sorted(self) -> None:
        for s in segment(SYLLABIC + ["logos", "kosmos"]):
            assert list(s.cuts) == sorted(s.cuts)
            assert all(0 < c < len(s.units) for c in s.cuts)

    def test_repeatable(self) -> None:
        assert candidate_morphs(SYLLABIC, min_count=2) == candidate_morphs(
            SYLLABIC, min_count=2
        )

    def test_min_count_one_rejects_below(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            candidate_morphs(SYLLABIC, min_count=0)
