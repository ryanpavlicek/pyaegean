"""Property-based invariants for the ported algorithms, mirroring the
workbench ``src/lib/algorithms.properties.test.ts``."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from aegean.analysis import (
    chi_squared_2x2,
    chi_squared_p_value,
    fishers_exact,
    log_likelihood_ratio_2x2,
    phonetic_distance,
    sequence_distance,
    sequence_similarity,
    wilson_interval,
)

# Restrict to phonemes the metric actually reasons about so the vowel /
# same-class / far branches are all exercised.
_phoneme = st.text(alphabet="aeioukgptdbmnrlsz", max_size=8)
_tokens = st.lists(st.sampled_from(["a", "b", "c", "d"]), max_size=8)


@st.composite
def _table(draw):
    total = draw(st.integers(min_value=1, max_value=300))
    count_a = draw(st.integers(min_value=0, max_value=total))
    count_b = draw(st.integers(min_value=0, max_value=total))
    joint = draw(
        st.integers(min_value=max(0, count_a + count_b - total), max_value=min(count_a, count_b))
    )
    return joint, count_a, count_b, total


# ── phonetic distance ────────────────────────────────────────────────────────
@given(_phoneme)
def test_distance_identity(s):
    assert phonetic_distance(s, s) == 0


@given(_phoneme, _phoneme)
def test_distance_symmetric(a, b):
    assert phonetic_distance(a, b) == phonetic_distance(b, a)


@given(_phoneme, _phoneme)
def test_distance_normalized(a, b):
    d = phonetic_distance(a, b)
    assert 0 <= d <= 1


@given(_phoneme, _phoneme)
def test_distance_positive_for_distinct(a, b):
    if a and b and a != b:
        assert phonetic_distance(a, b) > 0


# ── sequence distance / similarity ───────────────────────────────────────────
@given(_tokens, _tokens)
def test_sequence_symmetric_and_zero(a, b):
    assert sequence_distance(a, b) == sequence_distance(b, a)
    assert sequence_distance(a, a) == 0


@given(_tokens, _tokens)
def test_sequence_bounded(a, b):
    assert sequence_distance(a, b) <= max(len(a), len(b))


@given(_tokens, _tokens)
def test_sequence_similarity_bounds(a, b):
    sim = sequence_similarity(a, b)
    assert 0 <= sim <= 1
    if a == b:
        assert sim == 1


# ── wilson interval ──────────────────────────────────────────────────────────
@given(st.integers(min_value=1, max_value=500), st.data())
def test_wilson_bounds(n, data):
    k = data.draw(st.integers(min_value=0, max_value=n))
    lo, hi = wilson_interval(k, n)
    assert 0 <= lo <= hi <= 1


# ── collocation statistics ───────────────────────────────────────────────────
@given(_table())
def test_chi_squared_nonneg_symmetric(table):
    joint, a, b, total = table
    x = chi_squared_2x2(joint, a, b, total)
    assert x >= 0
    assert x == chi_squared_2x2(joint, b, a, total)


@given(_table())
def test_llr_nonneg_symmetric(table):
    joint, a, b, total = table
    g = log_likelihood_ratio_2x2(joint, a, b, total)
    assert g >= -1e-9
    assert abs(g - log_likelihood_ratio_2x2(joint, b, a, total)) < 1e-6


@given(_table())
def test_fisher_is_probability(table):
    joint, a, b, total = table
    p = fishers_exact(joint, a, b, total)
    assert 0 <= p <= 1


@given(
    st.floats(min_value=0, max_value=50, allow_nan=False),
    st.floats(min_value=0, max_value=50, allow_nan=False),
)
def test_p_value_bounded_and_monotone(x, y):
    px = chi_squared_p_value(x)
    assert 0 <= px <= 1
    if x <= y:
        assert chi_squared_p_value(y) <= px + 1e-9
