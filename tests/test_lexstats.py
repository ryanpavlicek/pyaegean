"""Vocabulary-richness & information estimators (aegean.analysis.stats).

Ported 1:1 from the Linear A Research Workbench's ``lexstats.test.ts``; the
values match, including a bit-for-bit reproduction of the workbench's
``mulberry32`` PRNG (so seeded resamples agree across the two tools).
"""

from __future__ import annotations

import math

import pytest

from aegean.analysis.stats import (
    bootstrap_counts_ci,
    chao1,
    fit_heaps,
    fit_zipf_mandelbrot_mle,
    mattr,
    miller_madow_entropy,
    mulberry32,
    shannon_entropy,
)

# Ground-truth values captured from the workbench's JavaScript implementation.
_JS_M42 = [
    0.60110375192016363,
    0.44829055899754167,
    0.85246579349040985,
    0.66973404143936932,
    0.17481389874592423,
]
_JS_M7 = [
    0.01170475315302610,
    0.06195825757458806,
    0.97690763277933002,
    0.69902870571240783,
    0.52144526853226125,
]


class TestMulberry32:
    def test_deterministic_per_seed(self) -> None:
        a = mulberry32(42)
        b = mulberry32(42)
        seq_a = [a() for _ in range(5)]
        assert seq_a == [b() for _ in range(5)]
        c = mulberry32(7)
        assert [c() for _ in range(5)] != seq_a

    def test_matches_javascript_bit_for_bit(self) -> None:
        a = mulberry32(42)
        assert [a() for _ in range(5)] == pytest.approx(_JS_M42, abs=1e-12)
        b = mulberry32(7)
        assert [b() for _ in range(5)] == pytest.approx(_JS_M7, abs=1e-12)

    def test_uniform_ish(self) -> None:
        r = mulberry32(1)
        total = 0.0
        for _ in range(2000):
            v = r()
            assert 0.0 <= v < 1.0
            total += v
        assert 0.45 < total / 2000 < 0.55


class TestShannonEntropy:
    def test_zero_for_single_category_and_log2k_for_uniform(self) -> None:
        assert shannon_entropy([10]) == 0
        assert shannon_entropy([5, 5, 5, 5]) == pytest.approx(2, abs=1e-10)
        assert shannon_entropy([1, 1]) == pytest.approx(1, abs=1e-10)

    def test_hand_computed_skewed(self) -> None:
        # p = [0.5, 0.25, 0.25] -> H = 1.5 bits
        assert shannon_entropy([2, 1, 1]) == pytest.approx(1.5, abs=1e-10)

    def test_ignores_zeros_and_empty(self) -> None:
        assert shannon_entropy([5, 0, 5, 0]) == pytest.approx(1, abs=1e-10)
        assert shannon_entropy([]) == 0
        assert shannon_entropy([0, 0]) == 0


class TestMillerMadow:
    def test_adds_correction_term(self) -> None:
        counts = [2, 1, 1]
        expected = 1.5 + (3 - 1) / (2 * 4 * math.log(2))
        assert miller_madow_entropy(counts) == pytest.approx(expected, abs=1e-10)

    def test_corrects_toward_truth(self) -> None:
        # True uniform over 8 categories = 3 bits; this skewed 16-token draw
        # lands the plug-in estimate well under 3, the MM correction recovers it.
        sample = [5, 3, 3, 1, 1, 1, 1, 1]
        mle = shannon_entropy(sample)
        mm = miller_madow_entropy(sample)
        assert mm > mle
        assert abs(mm - 3) < abs(mle - 3)

    def test_degenerates_safely(self) -> None:
        assert miller_madow_entropy([10]) == 0
        assert miller_madow_entropy([]) == 0


class TestBootstrapCountsCI:
    def test_brackets_and_deterministic(self) -> None:
        counts = [40, 30, 20, 10]
        h = shannon_entropy(counts)
        ci1 = bootstrap_counts_ci(counts, shannon_entropy, seed=3)
        ci2 = bootstrap_counts_ci(counts, shannon_entropy, seed=3)
        assert ci1 == ci2
        assert ci1[0] <= h
        assert ci1[1] >= h - 0.05
        assert ci1[0] < ci1[1]
        # bit-for-bit against the workbench (same mulberry32 stream)
        assert ci1 == pytest.approx((1.7111658177478524, 1.9341160233044175), abs=1e-12)

    def test_narrows_as_sample_grows(self) -> None:
        small = [8, 6, 4, 2]
        big = [c * 50 for c in small]
        a1, b1 = bootstrap_counts_ci(small, shannon_entropy, seed=5)
        a2, b2 = bootstrap_counts_ci(big, shannon_entropy, seed=5)
        assert b2 - a2 < b1 - a1
        assert (a1, b1) == pytest.approx((1.3366664819166874, 1.9527241956246546), abs=1e-12)

    def test_empty_distribution(self) -> None:
        assert bootstrap_counts_ci([0, 0], shannon_entropy) == (0.0, 0.0)


class TestChao1:
    def test_classic_formula_f2_positive(self) -> None:
        # S=50, F1=10, F2=5 -> 50 + 100/10 = 60
        r = chao1(50, 10, 5)
        assert r.estimate == pytest.approx(60, abs=1e-10)
        assert r.unseen == pytest.approx(10, abs=1e-10)
        assert 50 <= r.ci_low < 60
        assert r.ci_high > 60

    def test_bias_corrected_form_f2_zero(self) -> None:
        # S=20, F1=4, F2=0 -> 20 + 4*3/2 = 26
        assert chao1(20, 4, 0).estimate == pytest.approx(26, abs=1e-10)

    def test_observed_when_no_hapaxes(self) -> None:
        r = chao1(30, 0, 5)
        assert r.estimate == 30
        assert r.ci_low == 30
        assert r.ci_high == 30


class TestMattr:
    def test_equals_averaged_window_ttr(self) -> None:
        # window 2 over A B A A: windows AB, BA, AA -> TTRs 1, 1, 0.5
        assert mattr(["A", "B", "A", "A"], 2) == pytest.approx((1 + 1 + 0.5) / 3, abs=1e-10)

    def test_all_distinct_and_constant(self) -> None:
        assert mattr(["a", "b", "c", "d", "e"], 3) == pytest.approx(1, abs=1e-10)
        assert mattr(["x", "x", "x", "x"], 4) == pytest.approx(0.25, abs=1e-10)

    def test_none_when_shorter_than_window(self) -> None:
        assert mattr(["a", "b"], 100) is None
        assert mattr([], 10) is None

    def test_length_insensitive_for_stationary_stream(self) -> None:
        short = ["A" if i % 2 else "B" for i in range(40)]
        long = ["A" if i % 2 else "B" for i in range(400)]
        assert mattr(short, 4) == pytest.approx(0.5, abs=1e-10)
        assert mattr(long, 4) == pytest.approx(0.5, abs=1e-10)


class TestFitHeaps:
    def test_recovers_power_law(self) -> None:
        points = [((i + 1) * 20, 3.5 * ((i + 1) * 20) ** 0.55) for i in range(50)]
        fit = fit_heaps(points)
        assert fit is not None
        assert fit.k == pytest.approx(3.5, abs=1e-3)
        assert fit.beta == pytest.approx(0.55, abs=1e-6)
        assert fit.r2 == pytest.approx(1, abs=1e-6)

    def test_skips_zero_points_and_too_few(self) -> None:
        assert fit_heaps([(0, 0)]) is None
        assert fit_heaps([(0, 0), (10, 8), (20, 14)]) is None


class TestFitZipfMandelbrot:
    def test_recovers_synthetic_params(self) -> None:
        s0, b0 = 1.2, 2.5
        freqs = [round(50_000 * ((r + b0) ** -s0)) for r in range(1, 301)]
        fit = fit_zipf_mandelbrot_mle(freqs)
        assert fit is not None
        assert fit.s == pytest.approx(s0, abs=0.05)
        assert abs(fit.beta - b0) < 0.75
        assert fit.ks < 0.02
        assert fit.r2_log > 0.98

    def test_plain_zipf_beta_near_zero(self) -> None:
        freqs = [round(20_000 * (r**-1)) for r in range(1, 201)]
        fit = fit_zipf_mandelbrot_mle(freqs)
        assert fit is not None
        assert fit.s == pytest.approx(1, abs=0.05)
        assert fit.beta < 1

    def test_large_ks_for_uniform(self) -> None:
        fit = fit_zipf_mandelbrot_mle([50] * 100)
        assert fit is not None
        assert fit.s < 0.3

    def test_none_for_tiny_inputs(self) -> None:
        assert fit_zipf_mandelbrot_mle([5, 3]) is None
        assert fit_zipf_mandelbrot_mle([]) is None
