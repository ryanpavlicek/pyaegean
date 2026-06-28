"""Paired system-vs-system significance tests: McNemar + paired bootstrap."""

from __future__ import annotations

import math

import pytest

from aegean.analysis.significance import (
    McNemarResult,
    PairedBootstrapResult,
    mcnemar,
    paired_bootstrap,
)


# ── McNemar's test ───────────────────────────────────────────────────────────


def test_mcnemar_identical_systems_no_discordance():
    # Two systems with identical per-item correctness: no discordant items, so
    # the test is undefined and reports the neutral p = 1.0.
    correct = [True, False, True, True, False, True]
    r = mcnemar(correct, list(correct))
    assert isinstance(r, McNemarResult)
    assert r.b == 0 and r.c == 0
    assert r.p_value == 1.0
    assert r.method == "exact"


def test_mcnemar_counts_only_discordant():
    # A right where B wrong twice (b=2); B right where A wrong once (c=1);
    # concordant items are ignored.
    a = [True, True, True, False, True]
    b = [False, False, True, True, True]
    r = mcnemar(a, b)
    assert r.b == 2 and r.c == 1
    assert r.method == "exact"  # b + c = 3 <= threshold


def test_mcnemar_small_uniformly_better_is_significant():
    # A correct on every item, B correct on none: 30 discordant items all one
    # way (b=30, c=0). Even via the exact binomial this is decisive.
    a = [True] * 30
    b = [False] * 30
    r = mcnemar(a, b)
    assert r.b == 30 and r.c == 0
    assert r.p_value < 0.001


def test_mcnemar_exact_matches_hand_computed_binomial():
    # b=3, c=0, n=3: two-sided binomial p = 2 * P(X <= 0) = 2 * (1/8) = 0.25.
    a = [True, True, True]
    b = [False, False, False]
    r = mcnemar(a, b)
    assert r.method == "exact"
    assert r.p_value == pytest.approx(0.25)


def test_mcnemar_balanced_discordance_is_not_significant():
    # Equal discordance both directions (b == c): no evidence either system is
    # better, p should be high (= 1.0 for the symmetric exact case b == c).
    a = [True] * 6 + [False] * 6
    b = [False] * 6 + [True] * 6
    r = mcnemar(a, b)
    assert r.b == 6 and r.c == 6
    assert r.p_value == pytest.approx(1.0)


def test_mcnemar_chi2_branch_for_large_n():
    # Force the chi-square branch with many discordant items skewed one way.
    a = [True] * 60 + [False] * 10
    b = [False] * 60 + [True] * 10
    r = mcnemar(a, b)
    assert r.method == "chi2"
    assert r.b == 60 and r.c == 10
    # Continuity-corrected chi-square: (|60-10| - 1)^2 / 70 = 49^2 / 70.
    assert r.statistic == pytest.approx((49.0 * 49.0) / 70.0)
    assert r.p_value < 0.001


def test_mcnemar_exact_threshold_switches_method():
    # Exactly at the threshold uses exact; one above uses chi2.
    a = [True] * 25
    b = [False] * 25
    assert mcnemar(a, b, exact_threshold=25).method == "exact"
    assert mcnemar([True] * 26, [False] * 26, exact_threshold=25).method == "chi2"


def test_mcnemar_length_mismatch_raises():
    with pytest.raises(ValueError):
        mcnemar([True, False], [True])


# ── paired bootstrap ─────────────────────────────────────────────────────────


def test_paired_bootstrap_identical_systems_ci_spans_zero():
    # Identical per-item scores: every difference is 0, so the mean difference
    # is 0 and the whole CI collapses onto 0 (it "spans" 0 trivially).
    scores = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    r = paired_bootstrap(scores, list(scores), n_resamples=499, seed=7)
    assert isinstance(r, PairedBootstrapResult)
    assert r.mean_difference == 0.0
    assert r.low <= 0.0 <= r.high
    assert r.low == 0.0 and r.high == 0.0
    # No resample favours either system when all differences are zero.
    assert r.frac_a == 0.0 and r.frac_b == 0.0


def test_paired_bootstrap_uniformly_better_ci_all_positive():
    # System A correct on every item, B on none: every difference is +1, so the
    # mean difference is 1 and the entire CI sits above 0.
    a = [1.0] * 40
    b = [0.0] * 40
    r = paired_bootstrap(a, b, n_resamples=999, seed=3)
    assert r.mean_difference == pytest.approx(1.0)
    assert r.low > 0.0
    assert r.frac_a == 1.0
    assert r.frac_b == 0.0


def test_paired_bootstrap_uniformly_worse_ci_all_negative():
    # Mirror image: A worse everywhere -> mean difference -1, CI all negative.
    a = [0.0] * 40
    b = [1.0] * 40
    r = paired_bootstrap(a, b, n_resamples=999, seed=3)
    assert r.mean_difference == pytest.approx(-1.0)
    assert r.high < 0.0
    assert r.frac_b == 1.0
    assert r.frac_a == 0.0


def test_paired_bootstrap_noisy_tie_ci_spans_zero():
    # Two systems that trade wins evenly: mean difference near 0 and the CI
    # straddles 0 (inconclusive), with neither system favoured overwhelmingly.
    a = [1.0, 0.0] * 20
    b = [0.0, 1.0] * 20
    r = paired_bootstrap(a, b, n_resamples=999, seed=11)
    assert r.mean_difference == pytest.approx(0.0)
    assert r.low < 0.0 < r.high


def test_paired_bootstrap_continuous_scores():
    # Non-binary per-item scores (e.g. per-sentence LAS): A consistently ~0.05
    # better. The CI should land above 0 and frac_a dominate.
    a = [0.90, 0.85, 0.88, 0.92, 0.80, 0.95, 0.87, 0.83, 0.91, 0.86]
    b = [0.85, 0.80, 0.83, 0.87, 0.75, 0.90, 0.82, 0.78, 0.86, 0.81]
    r = paired_bootstrap(a, b, n_resamples=999, seed=5)
    assert r.mean_difference == pytest.approx(0.05, abs=1e-9)
    assert r.low > 0.0
    assert r.frac_a > 0.9


def test_paired_bootstrap_is_reproducible_by_seed():
    # Continuous, distinct per-item differences so quantile endpoints don't snap
    # to a tiny shared set of discrete values across seeds.
    a = [0.91, 0.42, 0.77, 0.13, 0.58, 0.64, 0.29, 0.86, 0.05, 0.73]
    b = [0.10, 0.55, 0.34, 0.61, 0.22, 0.48, 0.71, 0.19, 0.66, 0.37]
    r1 = paired_bootstrap(a, b, n_resamples=400, seed=42)
    r2 = paired_bootstrap(a, b, n_resamples=400, seed=42)
    r3 = paired_bootstrap(a, b, n_resamples=400, seed=43)
    # Same seed -> identical interval and fractions (reproducible by default).
    assert (r1.low, r1.high, r1.frac_a, r1.frac_b) == (r2.low, r2.high, r2.frac_a, r2.frac_b)
    # The point estimate is seed-independent (it is the observed mean difference).
    assert r1.mean_difference == r3.mean_difference
    # A different seed gives a (generally) different interval.
    assert (r1.low, r1.high) != (r3.low, r3.high)


def test_paired_bootstrap_fractions_in_unit_interval():
    a = [1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
    b = [0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]
    r = paired_bootstrap(a, b, n_resamples=600, seed=9)
    assert 0.0 <= r.frac_a <= 1.0
    assert 0.0 <= r.frac_b <= 1.0
    assert r.frac_a + r.frac_b <= 1.0 + 1e-12
    assert r.low <= r.mean_difference <= r.high or math.isclose(r.low, r.high)


def test_paired_bootstrap_length_mismatch_raises():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0, 0.0], [1.0])


def test_paired_bootstrap_too_few_items_raises():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0], [0.0])


def test_paired_bootstrap_bad_level_raises():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0, 0.0], [0.0, 1.0], level=1.5)
