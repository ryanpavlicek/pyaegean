"""Paired significance testing: does system A differ from system B?

The evaluation harness can put a confidence interval on a *single* system's
score (``bootstrap_ci_seq`` over a fold's sentences). This module answers the
complementary question, *do two systems differ significantly on the same
items?*, with two paired tests over gold-aligned, per-item results:

- **McNemar's test** for two systems' *binary* per-item correctness. Only the
  discordant items matter, those one system gets right and the other wrong
  (counts ``b`` and ``c``); concordant items carry no signal about which system
  is better. For few discordant items the **exact two-sided binomial** is used
  (``b`` ~ Binomial(b+c, ½) under H₀); otherwise the **continuity-corrected
  chi-square** ``(|b−c|−1)² / (b+c)`` on one degree of freedom (Edwards 1948).
- **Paired bootstrap** over the per-item score *differences* ``A−B``. Resampling
  the item-level differences with replacement (the same ``mulberry32`` stream
  used elsewhere, so a cited interval reproduces on re-run) gives a percentile
  CI on the mean difference plus the fraction of resamples favouring each
  system. Scores are any per-item numbers (0/1 accuracy, per-sentence LAS, a
  similarity), not just binary.

Both tests treat items as the exchangeable unit and assume the two systems were
run on the *same* items in the *same* order (gold-aligned). They quantify
whether an observed gap is more than sampling noise; they say nothing about
whether the items themselves are representative.

**A scholarly caution.** A significant difference on a held-out fold is evidence
about *these* items under *this* metric, not a universal ranking. On small or
fragmentary material (most Aegean evaluation sets) pair the p-value and CI with
the effect size, the mean difference, before reading much into a verdict; a tiny
but consistent gap can clear significance without mattering. Comparisons over an
**undeciphered** script's putative readings are **exploratory**: the test can
say two heuristics disagree, never that either is correct.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .stats import mulberry32

__all__ = [
    "McNemarResult",
    "mcnemar",
    "PairedBootstrapResult",
    "paired_bootstrap",
]


# ── McNemar's test (paired binary correctness) ───────────────────────────────


@dataclass(frozen=True)
class McNemarResult:
    """McNemar's paired test on two systems' binary correctness.

    ``b`` = items system A got right and B wrong; ``c`` = B right, A wrong;
    these *discordant* counts are all the test uses (``n = b + c``). ``method``
    is ``"exact"`` (two-sided binomial, used for small ``n``) or
    ``"chi2"`` (continuity-corrected chi-square, 1 dof). ``statistic`` is the
    chi-square value for ``"chi2"`` and ``min(b, c)`` for ``"exact"``;
    ``p_value`` is two-sided. A small ``p_value`` means the systems differ on
    the items where they disagree."""

    b: int
    c: int
    statistic: float
    p_value: float
    method: str


def _binom_two_sided_half(k: int, n: int) -> float:
    """Two-sided p-value for k successes in n Bernoulli(½) trials.

    Exact, in pure stdlib via ``math.comb``. The distribution is symmetric, so
    the two-sided p-value is ``min(1, 2 · P(X ≤ min(k, n−k)))``."""
    if n <= 0:
        return 1.0
    lo = min(k, n - k)
    tail = math.fsum(math.comb(n, i) for i in range(lo + 1)) / (2.0**n)
    return min(1.0, 2.0 * tail)


def mcnemar(
    correct_a: Sequence[bool],
    correct_b: Sequence[bool],
    *,
    exact_threshold: int = 25,
) -> McNemarResult:
    """McNemar's test for whether two systems' per-item correctness differs.

    ``correct_a`` / ``correct_b`` are equal-length, gold-aligned booleans (item
    *i* right or wrong for each system). Only discordant items contribute:
    ``b`` = A-right/B-wrong, ``c`` = A-wrong/B-right. When ``b + c ≤
    exact_threshold`` the **exact two-sided binomial** is used (reliable for the
    small discordant counts typical of a single fold); otherwise the
    **continuity-corrected chi-square** ``(|b−c|−1)² / (b+c)`` with its 1-dof
    tail. No discordant items (``b + c = 0``) is an undefined test and returns
    ``p_value = 1.0``. Raises ``ValueError`` on a length mismatch.

    >>> r = mcnemar([True, True, False], [True, False, False])
    >>> r.b, r.c, r.method
    (1, 0, 'exact')
    """
    if len(correct_a) != len(correct_b):
        raise ValueError("correct_a and correct_b must be the same length")
    b = sum(1 for a, bb in zip(correct_a, correct_b, strict=True) if a and not bb)
    c = sum(1 for a, bb in zip(correct_a, correct_b, strict=True) if bb and not a)
    n = b + c
    if n == 0:
        return McNemarResult(b=b, c=c, statistic=0.0, p_value=1.0, method="exact")
    if n <= exact_threshold:
        return McNemarResult(
            b=b,
            c=c,
            statistic=float(min(b, c)),
            p_value=_binom_two_sided_half(min(b, c), n),
            method="exact",
        )
    dev = abs(b - c) - 1.0
    corrected = dev if dev > 0 else 0.0
    chi2 = (corrected * corrected) / n
    # 1-dof chi-square survival function in pure stdlib: P(X² ≥ x) = erfc(√(x/2)).
    p = math.erfc(math.sqrt(chi2 / 2.0)) if chi2 > 0 else 1.0
    return McNemarResult(b=b, c=c, statistic=chi2, p_value=p, method="chi2")


# ── paired bootstrap (per-item score differences) ────────────────────────────


@dataclass(frozen=True)
class PairedBootstrapResult:
    """A paired percentile bootstrap on per-item score differences ``A − B``.

    ``mean_difference`` is the observed mean of ``scores_a[i] − scores_b[i]``
    (positive = A scores higher on average). ``[low, high]`` is the ``level``
    percentile interval over the resampled mean differences: a band entirely
    above 0 favours A, entirely below favours B, straddling 0 is inconclusive.
    ``frac_a`` / ``frac_b`` are the fractions of resamples whose mean difference
    favoured A / B (resamples with a mean difference of exactly 0 count toward
    neither, so the two need not sum to 1)."""

    mean_difference: float
    low: float
    high: float
    level: float
    n_resamples: int
    frac_a: float
    frac_b: float


def paired_bootstrap(
    scores_a: Sequence[float],
    scores_b: Sequence[float],
    *,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
) -> PairedBootstrapResult:
    """Paired bootstrap CI on the mean per-item score difference ``A − B``.

    ``scores_a`` / ``scores_b`` are equal-length, gold-aligned per-item scores
    (0/1 accuracy, a per-sentence metric, any number). The per-item differences
    are resampled with replacement ``n_resamples`` times; the returned interval
    is the ``level`` percentile band on the mean difference, with the fraction
    of resamples favouring each system. Reproducible by ``seed`` (the shared
    ``mulberry32`` stream); vary it to gauge Monte-Carlo wobble. The band
    quantifies sampling variability *given these items* only. Raises
    ``ValueError`` on a length mismatch, fewer than two items, or a ``level``
    outside ``(0, 1)``.

    >>> r = paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0], seed=1)
    >>> r.mean_difference, r.low > 0
    (1.0, True)
    """
    if len(scores_a) != len(scores_b):
        raise ValueError("scores_a and scores_b must be the same length")
    n = len(scores_a)
    if n < 2:
        raise ValueError("paired bootstrap needs at least 2 items")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    diffs = [float(a) - float(bb) for a, bb in zip(scores_a, scores_b, strict=True)]
    mean_diff = math.fsum(diffs) / n

    rng = mulberry32(seed)
    means: list[float] = []
    favour_a = 0
    favour_b = 0
    for _ in range(n_resamples):
        total = 0.0
        for _i in range(n):
            total += diffs[int(rng() * n)]
        m = total / n
        means.append(m)
        if m > 0:
            favour_a += 1
        elif m < 0:
            favour_b += 1

    means.sort()

    def quantile(q: float) -> float:
        pos = q * (len(means) - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        return means[lo] + (means[hi] - means[lo]) * (pos - lo)

    alpha = (1.0 - level) / 2.0
    return PairedBootstrapResult(
        mean_difference=mean_diff,
        low=quantile(alpha),
        high=quantile(1.0 - alpha),
        level=level,
        n_resamples=n_resamples,
        frac_a=favour_a / n_resamples,
        frac_b=favour_b / n_resamples,
    )
