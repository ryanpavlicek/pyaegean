"""Collocation statistics over 2×2 word-pair contingency tables.

A faithful port of the statistical helpers in the workbench
``src/lib/algorithms.ts``. The workbench hand-rolled erf (Abramowitz & Stegun)
and lgamma (Lanczos) approximations; here the stdlib ``math.erfc`` and
``math.lgamma`` stand in (verified accurate to ~1e-14 against the golden
fixtures), so ``import aegean`` stays zero-dependency and instant. Results match
the shared golden fixtures within the asserted tolerances.

For a word pair (a, b) across N documents the table is::

    a11 = joint count (both)     a12 = a only
    a21 = b only                 a22 = neither

**Exploratory.** On a small, undeciphered corpus these association scores flag
candidate collocations to inspect — they are not confirmed lexical units.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

from .patterns import normalize_sign_label


def _cells(
    joint: int, count_a: int, count_b: int, total: int
) -> tuple[int, int, int, int] | None:
    """The four cell counts, or None if the table is degenerate/impossible."""
    a11 = joint
    a12 = count_a - joint
    a21 = count_b - joint
    a22 = total - count_a - count_b + joint
    if (
        a11 < 0
        or a12 < 0
        or a21 < 0
        or a22 < 0
        or count_a == 0
        or count_b == 0
        or count_a == total
        or count_b == total
    ):
        return None
    return a11, a12, a21, a22


def chi_squared_2x2(joint: int, count_a: int, count_b: int, total: int) -> float:
    """Yates-corrected chi-squared test statistic for the 2×2 table.

    The continuity correction subtracts N/2 from ``|ad − bc|`` and clamps the
    corrected deviation at 0 (so near-independent pairs score ~0, not a small
    spurious positive). Returns 0 for degenerate tables."""
    cells = _cells(joint, count_a, count_b, total)
    if cells is None:
        return 0.0
    a11, a12, a21, a22 = cells
    dev = abs(a11 * a22 - a12 * a21) - total / 2
    corrected = dev if dev > 0 else 0.0
    numerator = total * corrected * corrected
    denominator = count_a * count_b * (total - count_a) * (total - count_b)
    return numerator / denominator if denominator > 0 else 0.0


def log_likelihood_ratio_2x2(
    joint: int, count_a: int, count_b: int, total: int
) -> float:
    """Log-likelihood ratio (G²) for the 2×2 table — Dunning (1993), the
    corpus-linguistics standard. ``G² = 2 · Σ O·ln(O/E)`` over the four cells;
    more robust than χ² for the sparse, low-count pairs of a small corpus.
    Returns 0 for degenerate tables; larger = stronger association."""
    cells = _cells(joint, count_a, count_b, total)
    if cells is None:
        return 0.0
    a11, a12, a21, a22 = cells
    e11 = (count_a * count_b) / total
    e12 = (count_a * (total - count_b)) / total
    e21 = ((total - count_a) * count_b) / total
    e22 = ((total - count_a) * (total - count_b)) / total

    def term(o: float, e: float) -> float:
        return o * math.log(o / e) if o > 0 and e > 0 else 0.0

    return 2 * (term(a11, e11) + term(a12, e12) + term(a21, e21) + term(a22, e22))


def chi_squared_p_value(x: float) -> float:
    """p-value for chi-squared with 1 degree of freedom: P(X² ≥ x). In [0,1],
    and non-increasing in ``x``."""
    if x <= 0:
        return 1.0
    # 1-dof chi-squared survival function in pure stdlib: P(X² ≥ x) = erfc(√(x/2)).
    return math.erfc(math.sqrt(x / 2.0))


def fishers_exact(joint: int, count_a: int, count_b: int, total: int) -> float:
    """Fisher's exact test, two-sided, for the 2×2 table: the summed
    hypergeometric probability of all tables with the same marginals whose
    probability is ≤ the observed table's. More accurate than χ² for small
    expected counts but O(N) per pair. Returns 1 for a degenerate margin or an
    impossible table (one whose implied cell counts are negative)."""
    # A degenerate margin or an impossible table (an implied cell < 0, e.g.
    # joint > count_a) has no admissible hypergeometric support; ``_cells``
    # rejects exactly those, matching χ²/G²'s shared guard and avoiding a
    # ``math.lgamma`` domain error on the negative ``count - joint`` arguments.
    if _cells(joint, count_a, count_b, total) is None:
        return 1.0

    def ln_choose(n: int, k: int) -> float:
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

    def ln_p(k: int) -> float:
        return (
            ln_choose(count_a, k)
            + ln_choose(total - count_a, count_b - k)
            - ln_choose(total, count_b)
        )

    observed_ln_p = ln_p(joint)
    k_min = max(0, count_a + count_b - total)
    k_max = min(count_a, count_b)
    total_p = 0.0
    for k in range(k_min, k_max + 1):
        ln = ln_p(k)
        if ln <= observed_ln_p + 1e-12:  # tolerate float fuzz around the observed table
            total_p += math.exp(ln)
    return min(1.0, total_p)


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion p̂ = k/n. Stays inside
    [0,1] with good coverage even at small/extreme p̂. ``z = 1.96`` ≈ 95%."""
    if n <= 0:
        return (0.0, 1.0)
    kc = min(max(k, 0), n)  # clamp an out-of-range count: k>n would make p̂>1 and
    p = kc / n              # drive the variance negative (sqrt of a negative)
    denom = 1 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denom
    half = (z / denom) * math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def pmi_interval(
    joint: int, count_a: int, count_b: int, total: int
) -> tuple[float, float]:
    """Propagate a Wilson interval on the joint probability into a pointwise
    mutual information confidence interval (log₂ space), holding the marginals
    fixed. A zero lower joint clamps PMI low to a finite floor (−20)."""
    if total == 0 or count_a == 0 or count_b == 0:
        return (-math.inf, math.inf)
    pj_low, pj_high = wilson_interval(joint, total)
    pa = count_a / total
    pb = count_b / total
    denom = pa * pb
    lo = math.log2(pj_low / denom) if pj_low > 0 else -20.0
    hi = math.log2(pj_high / denom)
    return (lo, hi)


def sign_bigram_pmi(
    joint: int, left_total: int, right_total: int, grand_total: int
) -> float | None:
    """Pointwise mutual information (bits) of an adjacent ordered sign pair a→b.

    ``joint`` is the directed adjacency count of a→b; ``left_total`` the total
    outgoing adjacencies from a (a as the left/previous sign); ``right_total``
    the total incoming adjacencies to b (b as the right/next sign);
    ``grand_total`` all adjacency-pair tokens. Returns
    ``log₂(joint·grand / (left·right))`` — positive = the pair occurs more often
    than the two signs' slot frequencies predict, negative = less. Returns
    ``None`` (PMI undefined) when any input is zero, e.g. a never-attested pair.
    Directed: PMI(a→b) ≠ PMI(b→a) in general. Unsmoothed, so rare pairs read high."""
    if joint <= 0 or left_total <= 0 or right_total <= 0 or grand_total <= 0:
        return None
    return math.log2((joint * grand_total) / (left_total * right_total))


def sign_bigram_pmis(
    words: Iterable[tuple[str, int]],
) -> dict[tuple[str, str], float]:
    """Directed sign-bigram PMI (bits) for every adjacent sign pair attested in a
    multi-sign word vocabulary.

    ``words`` is an iterable of ``(word, count)`` pairs (hyphen-joined signs, a
    token frequency); adjacencies are token-weighted and subscript sign labels
    are folded (``RA₂`` → ``RA2``). No boundary markers — interior adjacencies
    only. Returns ``{(a, b): pmi}`` over attested pairs (a never-attested pair is
    simply absent, its PMI being undefined)."""
    outgoing: dict[tuple[str, str], int] = defaultdict(int)
    for word, count in words:
        parts = [normalize_sign_label(p) for p in word.split("-")]
        if len(parts) < 2:
            continue
        for a, b in zip(parts, parts[1:], strict=False):
            outgoing[(a, b)] += count
    left: dict[str, int] = defaultdict(int)
    right: dict[str, int] = defaultdict(int)
    grand = 0
    for (a, b), v in outgoing.items():
        left[a] += v
        right[b] += v
        grand += v
    result: dict[tuple[str, str], float] = {}
    for (a, b), v in outgoing.items():
        pmi = sign_bigram_pmi(v, left[a], right[b], grand)
        if pmi is not None:
            result[(a, b)] = pmi
    return result
