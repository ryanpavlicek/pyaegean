"""Permutation / Monte-Carlo null models for the structure heuristics.

Checks the two null generators preserve exactly what they claim, and that
:func:`monte_carlo_p` gives a small p-value on a planted regularity and a
non-significant one on data that already matches its null.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import pytest

from aegean.analysis.null_models import (
    MonteCarloResult,
    length_reshuffle_null,
    monte_carlo_p,
    within_word_null,
)
from aegean.analysis.stats import mulberry32


def _signs(words: Sequence[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        out.extend(w.split("-"))
    return out


def _lengths(words: Sequence[str]) -> list[int]:
    return [len(w.split("-")) for w in words]


# ── what each null preserves ────────────────────────────────────────────────


def test_within_word_preserves_lengths_and_unigram_multiset() -> None:
    words = ["A-B-C", "A-A", "B-C-D-E", "C"]
    rand = mulberry32(7)
    null = within_word_null(words, rand)
    # per-word length sequence identical
    assert _lengths(null) == _lengths(words)
    # corpus-wide unigram-sign multiset identical (so the unigram distribution is)
    assert Counter(_signs(null)) == Counter(_signs(words))


def test_within_word_actually_permutes() -> None:
    # A strongly ordered corpus: the null should (with this seed) change order.
    words = ["A-B-C-D-E"] * 20
    null = within_word_null(words, mulberry32(1))
    assert null != list(words)
    assert _lengths(null) == _lengths(words)
    assert Counter(_signs(null)) == Counter(_signs(words))


def test_reshuffle_preserves_words_intact_and_length_counts() -> None:
    words = ["A-B", "C-D-E", "F-G", "H-I-J", "K-L"]
    null = length_reshuffle_null(words, mulberry32(3))
    # every word is preserved verbatim (only their positions move)
    assert Counter(null) == Counter(words)
    # per-length counts preserved, in the original length-slot order
    assert _lengths(null) == _lengths(words)


def test_reshuffle_stays_within_length_strata() -> None:
    # Two strata: length-2 and length-3. A length-2 slot must hold a length-2 word.
    words = ["A-B", "C-D-E", "F-G", "H-I-J"]
    for seed in range(20):
        null = length_reshuffle_null(words, mulberry32(seed))
        assert _lengths(null) == [2, 3, 2, 3]
        assert Counter(null) == Counter(words)


def test_nulls_are_seed_reproducible() -> None:
    words = ["A-B-C", "D-E", "F-G-H-I"]
    assert within_word_null(words, mulberry32(42)) == within_word_null(words, mulberry32(42))
    assert length_reshuffle_null(words, mulberry32(42)) == length_reshuffle_null(
        words, mulberry32(42)
    )


# ── monte_carlo_p: signal vs null-consistent data ───────────────────────────


def _ordered_pair_count(words: Sequence[str]) -> float:
    """A toy ordering statistic: how many adjacent sign pairs are alphabetically
    ascending. A canonically ordered corpus maximizes it; a within-word
    permutation that only holds the unigram counts cannot keep it high."""
    score = 0
    for w in words:
        s = w.split("-")
        for a, b in zip(s, s[1:], strict=False):
            if a < b:
                score += 1
    return float(score)


def test_planted_ordering_gives_small_p() -> None:
    # Planted regularity: every word's signs are in strict ascending order.
    words = ["A-B-C-D", "B-C-D-E", "A-C-E-G", "B-D-F-H"] * 8
    observed = _ordered_pair_count(words)
    res = monte_carlo_p(observed, _ordered_pair_count, words, null="within_word", n=499, seed=0)
    assert isinstance(res, MonteCarloResult)
    assert res.observed == observed
    # The within-word null breaks ordering, so observed sits far in the upper tail.
    assert res.p_value < 0.01
    assert res.observed > res.null_high
    assert res.null_low <= res.null_mean <= res.null_high


def test_null_consistent_data_is_not_significant() -> None:
    # Build a corpus by *applying the null once* to an arbitrary base: it is then
    # an ordinary draw from that null, so its statistic should look typical.
    base = ["A-B-C", "B-A-C", "C-A-B", "A-C-B", "B-C-A"] * 6
    sampled = within_word_null(base, mulberry32(99))
    observed = _ordered_pair_count(sampled)
    res = monte_carlo_p(observed, _ordered_pair_count, sampled, null="within_word", n=499, seed=5)
    # A typical draw from the null is not in the extreme tail.
    assert res.p_value > 0.05


def test_reshuffle_positional_signal() -> None:
    # A statistic that reads word *position*: how many times a marked word sits
    # in an even slot. All words share one length stratum so the reshuffle can
    # move the marked word freely across positions.
    def marked_in_even(words: Sequence[str]) -> float:
        return float(sum(1 for i, w in enumerate(words) if i % 2 == 0 and w == "KU-RO"))

    # Planted: the marked word "KU-RO" only ever appears in even slots; odd slots
    # hold a filler word of the same length.
    words = ["KU-RO" if i % 2 == 0 else "PA-RO" for i in range(40)]
    observed = marked_in_even(words)
    res = monte_carlo_p(observed, marked_in_even, words, null="reshuffle", n=499, seed=0)
    # The length-stratified reshuffle keeps each word intact but moves it across
    # slots, so the perfect even-slot alignment of every "KU-RO" is unusual.
    assert res.p_value < 0.05
    assert res.observed >= res.null_high


# ── api contract / validation ───────────────────────────────────────────────


def test_p_value_is_seed_reproducible() -> None:
    words = ["A-B-C", "B-C-D", "C-D-E"] * 5
    obs = _ordered_pair_count(words)
    a = monte_carlo_p(obs, _ordered_pair_count, words, n=200, seed=11)
    b = monte_carlo_p(obs, _ordered_pair_count, words, n=200, seed=11)
    assert a == b


def test_add_one_p_value_bounds() -> None:
    # p is always in (0, 1]: never exactly 0, even when observed beats every null.
    words = ["A-B-C-D-E"] * 10
    huge = 1e9  # nothing in the null can reach this
    res = monte_carlo_p(huge, _ordered_pair_count, words, n=99, seed=0)
    assert res.p_value == pytest.approx(1 / (1 + 99))
    assert 0 < res.p_value <= 1


def test_invalid_arguments_raise() -> None:
    words = ["A-B", "C-D"]
    with pytest.raises(ValueError, match="null must be one of"):
        monte_carlo_p(0.0, _ordered_pair_count, words, null="nope")
    with pytest.raises(ValueError, match="n must be at least 1"):
        monte_carlo_p(0.0, _ordered_pair_count, words, n=0)
    with pytest.raises(ValueError, match="level must be in"):
        monte_carlo_p(0.0, _ordered_pair_count, words, level=1.5)
