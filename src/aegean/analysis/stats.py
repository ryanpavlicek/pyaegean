"""Corpus statistics: dispersion, keyness, and bootstrap confidence intervals.

The quantitative layer for comparing *whole corpora and subsets* — pure stdlib
(``math``, ``random``, ``collections``), working over any loadable corpus
(``lineara``, ``damos``, a ``filter()`` subset, or a plain document list).

Three families, each the corpus-linguistics standard:

- **Dispersion** — how *evenly* an item spreads across the documents of a
  corpus, not just how often it occurs. Gries' *deviation of proportions* (DP;
  Gries 2008), with the normalization of Lijffijt & Gries (2012).
- **Keyness** — which items are characteristic of one (sub)corpus against a
  reference: Dunning's (1993) log-likelihood G² for significance (the form of
  Rayson & Garside 2000) and Hardie's (2014) log-ratio for effect size.
- **Bootstrap** — percentile confidence intervals for *any* corpus statistic by
  resampling documents with replacement (Efron & Tibshirani 1993).

Frequencies follow the same conventions as ``Corpus.word_frequencies()`` and
``aegean stats``: ``kind="words"`` counts lexical WORD tokens; ``kind="signs"``
counts the individual signs of every token (syllabograms, logograms, …).

**A scholarly caution.** These are descriptive instruments. On small or
fragmentary corpora (most Aegean material) a significant G² flags an imbalance
worth *inspecting*, not a proven fact about the language; pair significance
(G², p) with effect size (log-ratio) and dispersion before reading anything
into a number.
"""

from __future__ import annotations

import math
import random as _random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from ..cache import memoize as _memoize
from ..core.model import Document, TokenKind
from .collocation import chi_squared_p_value, log_likelihood_ratio_2x2

__all__ = [
    "Dispersion",
    "KeynessRow",
    "BootstrapCI",
    "dispersion",
    "dispersions",
    "keyness",
    "bootstrap_ci",
    "bootstrap_ci_seq",
    "bootstrap_dict_seq",
    # vocabulary richness & information (count-vector estimators)
    "mulberry32",
    "shannon_entropy",
    "miller_madow_entropy",
    "bootstrap_counts_ci",
    "Chao1Result",
    "chao1",
    "mattr",
    "HeapsFit",
    "fit_heaps",
    "ZipfMandelbrotFit",
    "fit_zipf_mandelbrot_mle",
    "spearman_rho",
]


def _documents(corpus: Any) -> list[Document]:
    """Coerce a Corpus / QueryResults / iterable of Documents to a list."""
    docs = getattr(corpus, "documents", corpus)
    out = list(docs)
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _items_of(doc: Document, kind: str) -> list[str]:
    """The countable items of one document — same conventions as the CLI."""
    if kind == "words":
        return [t.text for t in doc.tokens if t.kind is TokenKind.WORD]
    if kind == "signs":
        out: list[str] = []
        for t in doc.tokens:
            out.extend(t.signs or (t.text.split("-") if "-" in t.text else [t.text]))
        return out
    raise ValueError(f"kind must be 'words' or 'signs', got {kind!r}")


# ── dispersion ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Dispersion:
    """How evenly one item spreads over the documents of a corpus.

    ``dp`` is Gries' deviation of proportions: 0 = the item is distributed
    exactly as the document sizes predict; values toward 1 = concentrated in
    few documents. ``dp_norm`` rescales by the attainable maximum
    (Lijffijt & Gries 2012) so corpora with different size profiles compare.
    ``range`` is the count of documents attesting the item (out of ``parts``
    documents that have any items at all)."""

    item: str
    frequency: int
    range: int
    parts: int
    dp: float
    dp_norm: float


def _dispersion_tables(
    docs: Sequence[Document], kind: str
) -> tuple[list[float], list[Counter[str]], int]:
    """Per-document size shares, per-document counts, and the corpus total."""
    per_doc = [Counter(_items_of(d, kind)) for d in docs]
    sizes = [sum(c.values()) for c in per_doc]
    total = sum(sizes)
    if total == 0:
        raise ValueError("corpus has no countable items")
    # Documents with no items of this kind carry no share of the corpus and are
    # not parts in Gries' sense; drop them so min(share) is well-defined.
    keep = [i for i, n in enumerate(sizes) if n > 0]
    per_doc = [per_doc[i] for i in keep]
    shares = [sizes[i] / total for i in keep]
    return shares, per_doc, total


def _dp(item: str, shares: Sequence[float], per_doc: Sequence[Counter[str]]) -> Dispersion:
    freq = sum(c[item] for c in per_doc)
    if freq == 0:
        raise ValueError(f"item {item!r} does not occur in the corpus")
    dp = 0.5 * sum(
        abs(c[item] / freq - share) for c, share in zip(per_doc, shares, strict=True)
    )
    max_dp = 1.0 - min(shares)
    return Dispersion(
        item=item,
        frequency=freq,
        range=sum(1 for c in per_doc if c[item]),
        parts=len(per_doc),
        dp=dp,
        dp_norm=dp / max_dp if max_dp > 0 else 0.0,
    )


def dispersion(corpus: Any, item: str, *, kind: str = "words") -> Dispersion:
    """Gries' DP for one item over the documents of ``corpus``.

    ``DP = ½ · Σᵢ |vᵢ − sᵢ|`` where ``sᵢ`` is document *i*'s share of the
    corpus (in items of this ``kind``) and ``vᵢ`` the share of the item's
    occurrences falling in document *i* (Gries 2008). ``dp_norm`` divides by
    the attainable maximum ``1 − min(sᵢ)`` (Lijffijt & Gries 2012). Raises
    ``ValueError`` if the item never occurs."""
    shares, per_doc, _ = _dispersion_tables(_documents(corpus), kind)
    return _dp(item, shares, per_doc)


@_memoize(version="1")
def dispersions(
    corpus: Any,
    *,
    kind: str = "words",
    min_frequency: int = 2,
    top: int = 0,
) -> list[Dispersion]:
    """DP for every item with ``frequency ≥ min_frequency``, most evenly
    dispersed first (ties: higher frequency first). ``top`` truncates (0 = all).

    Reading the ranking: a frequent item with *low* ``dp_norm`` is corpus-wide
    vocabulary; a frequent item with *high* ``dp_norm`` lives in few documents
    (a formulaic or genre/site-bound term) — on Aegean material often the more
    interesting case."""
    shares, per_doc, _ = _dispersion_tables(_documents(corpus), kind)
    totals: Counter[str] = Counter()
    for c in per_doc:
        totals.update(c)
    rows = [
        _dp(item, shares, per_doc)
        for item, n in totals.items()
        if n >= min_frequency
    ]
    rows.sort(key=lambda r: (r.dp_norm, -r.frequency, r.item))
    return rows[:top] if top > 0 else rows


# ── keyness ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KeynessRow:
    """One item's keyness in a target (sub)corpus against a reference.

    ``log_likelihood`` is Dunning's G² (significance: is the imbalance more
    than chance?); ``p_value`` its χ²₁ tail. ``log_ratio`` is Hardie's log₂
    ratio of relative frequencies (effect size: *how big* is the difference?)
    — positive = overused in the target, negative = underused; each whole
    point is a doubling. Zero counts are smoothed (default +0.5) for the
    ratio only, never for G²."""

    item: str
    target_count: int
    target_total: int
    reference_count: int
    reference_total: int
    log_likelihood: float
    log_ratio: float
    p_value: float


@_memoize(version="1")
def keyness(
    target: Any,
    reference: Any,
    *,
    kind: str = "words",
    min_target: int = 2,
    smoothing: float = 0.5,
) -> list[KeynessRow]:
    """Key items of ``target`` against ``reference``, strongest first.

    For each item the 2×2 table is (count in target, rest of target, count in
    reference, rest of reference); G² follows Rayson & Garside (2000) and the
    log-ratio Hardie (2014). Items need ``target_count ≥ min_target`` *or* to
    be similarly frequent in the reference (so marked *under*-use surfaces
    too). Sorted by G² descending — filter ``log_ratio > 0`` for the target's
    own vocabulary, ``< 0`` for what it conspicuously lacks.

    The two corpora must be distinct texts (a subset vs its complement is the
    classic design: ``keyness(c.filter(site="Pylos"), rest)``)."""
    t_counts: Counter[str] = Counter()
    for d in _documents(target):
        t_counts.update(_items_of(d, kind))
    r_counts: Counter[str] = Counter()
    for d in _documents(reference):
        r_counts.update(_items_of(d, kind))
    n1, n2 = sum(t_counts.values()), sum(r_counts.values())
    if n1 == 0 or n2 == 0:
        raise ValueError("both corpora must contain countable items")

    rows: list[KeynessRow] = []
    for item in set(t_counts) | set(r_counts):
        a, b = t_counts[item], r_counts[item]
        if a < min_target and b < min_target:
            continue
        g2 = log_likelihood_ratio_2x2(a, n1, a + b, n1 + n2)
        sa = a if a > 0 and b > 0 else a + smoothing
        sb = b if a > 0 and b > 0 else b + smoothing
        rows.append(
            KeynessRow(
                item=item,
                target_count=a,
                target_total=n1,
                reference_count=b,
                reference_total=n2,
                log_likelihood=g2,
                log_ratio=math.log2((sa / n1) / (sb / n2)),
                p_value=chi_squared_p_value(g2),
            )
        )
    rows.sort(key=lambda r: (-r.log_likelihood, r.item))
    return rows


# ── bootstrap ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BootstrapCI:
    """A percentile bootstrap interval: the statistic on the full corpus
    (``estimate``) and the [``low``, ``high``] band holding ``level`` of the
    resampled values."""

    estimate: float
    low: float
    high: float
    level: float
    n_resamples: int


_T = TypeVar("_T")


def _percentile_ci(
    values: list[float], estimate: float, level: float, n_resamples: int
) -> BootstrapCI:
    """A percentile CI from bootstrap replicate ``values`` (linear-interpolated quantiles)."""
    vs = sorted(values)

    def quantile(q: float) -> float:
        pos = q * (len(vs) - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        return vs[lo] + (vs[hi] - vs[lo]) * (pos - lo)

    alpha = (1.0 - level) / 2.0
    return BootstrapCI(
        estimate=estimate,
        low=quantile(alpha),
        high=quantile(1.0 - alpha),
        level=level,
        n_resamples=n_resamples,
    )


def bootstrap_ci_seq(
    items: Sequence[_T],
    statistic: Callable[[Sequence[_T]], float],
    *,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
) -> BootstrapCI:
    """Percentile bootstrap CI for ``statistic(items)``, resampling items with replacement.

    The unit-agnostic core behind :func:`bootstrap_ci` (which resamples documents). Reach
    for it directly when the resampling unit is something else — e.g. the sentences of a
    held-out evaluation fold, where a per-fold metric is bootstrapped over its sentences.
    ``seed`` makes the interval **reproducible by default** — vary it to see Monte-Carlo
    wobble. The band quantifies sampling variability *given these items* only.
    """
    n = len(items)
    if n < 2:
        raise ValueError("bootstrap needs at least 2 items")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    rng = _random.Random(seed)
    values = [float(statistic(rng.choices(items, k=n))) for _ in range(n_resamples)]
    return _percentile_ci(values, float(statistic(items)), level, n_resamples)


def bootstrap_dict_seq(
    items: Sequence[_T],
    statistic: Callable[[Sequence[_T]], dict[str, float]],
    *,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, BootstrapCI]:
    """Bootstrap several metrics that share one computation, over resampled ``items``.

    ``statistic(items)`` returns a ``{name: value}`` mapping; every name is bootstrapped
    over the **same** resamples, with one ``statistic`` call per resample. Use it when a
    single expensive call yields all the metrics at once — e.g. scoring an evaluation fold,
    where re-running the scorer once per metric would be wasteful. The intervals are jointly
    consistent (drawn from the same resamples) and reproducible by ``seed``.
    """
    n = len(items)
    if n < 2:
        raise ValueError("bootstrap needs at least 2 items")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    point = statistic(items)
    acc: dict[str, list[float]] = {k: [] for k in point}
    rng = _random.Random(seed)
    for _ in range(n_resamples):
        sample = statistic(rng.choices(items, k=n))
        for k in acc:
            acc[k].append(float(sample[k]))
    return {k: _percentile_ci(acc[k], float(point[k]), level, n_resamples) for k in point}


def bootstrap_ci(
    corpus: Any,
    statistic: Callable[[Sequence[Document]], float],
    *,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
) -> BootstrapCI:
    """Percentile bootstrap CI for ``statistic(documents)``.

    Documents are the resampling unit (drawn with replacement, original size),
    the right grain for corpus questions where tokens within a document are
    not independent (Efron & Tibshirani 1993). The ``seed`` makes the interval
    **reproducible by default** — vary it to see Monte-Carlo wobble. The band
    quantifies sampling variability *given these documents*; it cannot speak
    to what was never excavated.

    >>> mean_doc_words = lambda docs: sum(
    ...     len([t for t in d.tokens if t.kind is TokenKind.WORD]) for d in docs
    ... ) / len(docs)
    >>> bootstrap_ci(corpus, mean_doc_words)   # doctest: +SKIP
    BootstrapCI(estimate=7.1, low=6.4, high=7.9, level=0.95, n_resamples=999)
    """
    return bootstrap_ci_seq(
        _documents(corpus), statistic, n_resamples=n_resamples, level=level, seed=seed
    )


# ── vocabulary richness & information (count-vector estimators) ──────────────
# Exact-math estimators over raw count vectors / token streams — no corpus
# types — so the sign-entropy panels and the vocabulary-richness numbers share
# one implementation. Ported 1:1 from the Linear A Research Workbench's
# ``lexstats`` (the TS unit tests are mirrored in ``tests/test_lexstats.py`` and
# the values match, including a bit-for-bit reproduction of its PRNG).


def mulberry32(seed: int) -> Callable[[], float]:
    """A tiny, fast, seeded 32-bit PRNG (mulberry32).

    Returns a zero-argument callable yielding floats in ``[0, 1)``. Every
    resample / permutation here runs from an explicit seed so a cited number is
    reproducible on re-run; the 32-bit arithmetic reproduces the workbench's
    JavaScript implementation bit-for-bit, so both tools agree given one seed.
    """
    state = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ ((t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def shannon_entropy(counts: Sequence[float]) -> float:
    """Shannon entropy in bits of a count vector (maximum-likelihood plug-in).

    Zero counts contribute nothing; returns 0 for an empty or single-category
    vector."""
    n = 0.0
    for c in counts:
        if c > 0:
            n += c
    if n <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / n
        h -= p * math.log2(p)
    return h


def miller_madow_entropy(counts: Sequence[float]) -> float:
    """Miller–Madow bias-corrected entropy in bits.

    The plug-in estimator systematically *under*estimates entropy in small
    samples (unseen categories contribute nothing); the first-order correction
    adds ``(K − 1) / (2·N·ln 2)`` bits, ``K`` = observed categories,
    ``N`` = sample size. Still an underestimate when many categories are unseen
    — the honest situation for sign bigrams in a few-thousand-token corpus."""
    n = 0.0
    k = 0
    for c in counts:
        if c > 0:
            n += c
            k += 1
    if n <= 0 or k <= 1:
        return shannon_entropy(counts)
    return shannon_entropy(counts) + (k - 1) / (2 * n * math.log(2))


def bootstrap_counts_ci(
    counts: Sequence[float],
    stat: Callable[[list[int]], float],
    *,
    iters: int = 200,
    seed: int = 1,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile bootstrap CI for any ``stat`` of a count vector.

    Resamples ``N`` tokens from the empirical distribution (multinomial with
    ``p̂ᵢ = cᵢ/N``) and hands the resampled count vector — same length, same
    category order — to ``stat``; returns the ``[α/2, 1−α/2]`` percentile
    interval. Deterministic via ``seed`` (the same mulberry32 stream as the
    workbench). The resample treats tokens as independent draws, which corpus
    tokens are not (words repeat whole), so the interval is a **lower bound** on
    the real uncertainty."""
    rand = mulberry32(seed)
    cum: list[float] = []
    acc = 0.0
    for c in counts:
        acc += max(0.0, c)
        cum.append(acc)
    if acc == 0:
        return (0.0, 0.0)
    n = int(acc)
    length = len(counts)
    stats: list[float] = []
    for _ in range(iters):
        resampled = [0] * length
        for _d in range(n):
            u = rand() * n
            lo, hi = 0, length - 1
            while lo < hi:
                mid = (lo + hi) >> 1
                if cum[mid] > u:
                    hi = mid
                else:
                    lo = mid + 1
            resampled[lo] += 1
        stats.append(stat(resampled))
    stats.sort()

    def at(q: float) -> float:
        # mulberry32 + Math.round-style nearest-rank, to match the workbench.
        idx = min(iters - 1, max(0, int(math.floor(q * (iters - 1) + 0.5))))
        return stats[idx]

    return (at(alpha / 2), at(1 - alpha / 2))


@dataclass(frozen=True)
class Chao1Result:
    """Chao1 richness estimate: ``estimate`` total types, ``unseen`` =
    ``estimate − S_obs``, and a log-normal 95% CI ``[ci_low, ci_high]``. It is a
    **lower bound** — it only sees the rare-type tail."""

    estimate: float
    ci_low: float
    ci_high: float
    unseen: float


def chao1(s_obs: float, f1: float, f2: float) -> Chao1Result:
    """Chao1 lower-bound vocabulary size from observed types and the hapax /
    *dis legomena* counts.

    ``Ŝ = S_obs + F₁²/(2F₂)`` when ``F₂ > 0``; the bias-corrected
    ``Ŝ = S_obs + F₁(F₁−1)/2`` when ``F₂ = 0``. Uses Chao's (1987) variance and
    the standard log-normal CI on the unseen-type count."""
    if s_obs <= 0 or f1 <= 0:
        return Chao1Result(estimate=s_obs, ci_low=s_obs, ci_high=s_obs, unseen=0.0)
    if f2 > 0:
        r = f1 / f2
        estimate = s_obs + (f1 * f1) / (2 * f2)
        variance = f2 * (0.5 * r * r + r * r * r + 0.25 * r * r * r * r)
    else:
        estimate = s_obs + (f1 * (f1 - 1)) / 2
        variance = (
            (f1 * (f1 - 1)) / 2
            + (f1 * (2 * f1 - 1) * (2 * f1 - 1)) / 4
            - (f1 * f1 * f1 * f1) / (4 * estimate)
        )
    t = estimate - s_obs
    if t <= 0 or variance <= 0:
        return Chao1Result(estimate=estimate, ci_low=estimate, ci_high=estimate, unseen=t)
    k = math.exp(1.96 * math.sqrt(math.log(1 + variance / (t * t))))
    return Chao1Result(estimate=estimate, ci_low=s_obs + t / k, ci_high=s_obs + t * k, unseen=t)


def mattr(tokens: Sequence[str], window: int = 100) -> float | None:
    """MATTR — moving-average type-token ratio (Covington & McFall 2010).

    The mean TTR over every sliding window of ``window`` tokens. Unlike raw TTR
    it does not shrink mechanically as the stream grows, so differently sized
    slices compare. Returns ``None`` when the stream is shorter than one
    window."""
    n = len(tokens)
    if n < window or window <= 0:
        return None
    in_window: dict[str, int] = {}
    types = 0
    for i in range(window):
        c = in_window.get(tokens[i], 0) + 1
        in_window[tokens[i]] = c
        if c == 1:
            types += 1
    total = types / window
    windows = 1
    for i in range(window, n):
        out = tokens[i - window]
        oc = in_window.get(out, 1) - 1
        if oc == 0:
            del in_window[out]
            types -= 1
        else:
            in_window[out] = oc
        inc = in_window.get(tokens[i], 0) + 1
        in_window[tokens[i]] = inc
        if inc == 1:
            types += 1
        total += types / window
        windows += 1
    return total / windows


@dataclass(frozen=True)
class HeapsFit:
    """Heaps' law fit ``V(N) = k·N^β``: ``beta < 1`` = sublinear vocabulary
    growth (normal for language). ``r2`` is in log–log space."""

    k: float
    beta: float
    r2: float


def fit_heaps(points: Sequence[tuple[float, float]]) -> HeapsFit | None:
    """Fit Heaps' law ``V(N) = k·N^β`` by least squares in log–log space over a
    vocabulary-growth curve of ``(tokens, types)`` points. Needs at least five
    points with ``tokens ≥ 1`` and ``types ≥ 1``; returns ``None`` otherwise."""
    pts = [(tok, typ) for tok, typ in points if tok >= 1 and typ >= 1]
    if len(pts) < 5:
        return None
    sx = sy = sxx = sxy = syy = 0.0
    n = len(pts)
    for tok, typ in pts:
        x = math.log(tok)
        y = math.log(typ)
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y
        syy += y * y
    denom = n * sxx - sx * sx
    # A constant-x curve (no real growth) has denom == 0 mathematically, but float
    # roundoff leaves a tiny residue (~1e-13) that an exact-zero check misses,
    # yielding a fabricated fit. Reject relative to the data scale instead.
    eps = 1e-9
    if denom <= eps * max(n * sxx, 1.0):
        return None
    beta = (n * sxy - sx * sy) / denom
    log_k = (sy - beta * sx) / n
    ss_tot = syy - (sy * sy) / n
    ss_res = ss_tot - (beta * (n * sxy - sx * sy)) / n
    r2 = 1 - ss_res / ss_tot if ss_tot > eps * max(syy, 1.0) else 0.0
    return HeapsFit(k=math.exp(log_k), beta=beta, r2=r2)


@dataclass(frozen=True)
class ZipfMandelbrotFit:
    """Truncated Zipf–Mandelbrot MLE fit ``p(r) ∝ (r+β)^(−s)`` over the observed
    ranks. ``ks`` is the one-sample Kolmogorov–Smirnov statistic over token-share
    CDFs (smaller = closer; **no p-value** — the parameters are estimated from
    the same data). ``r2_log`` is log-space R²; ``log_z`` the log normalizer."""

    s: float
    beta: float
    ks: float
    r2_log: float
    log_z: float


def _zm_log_lik(freqs: Sequence[float], s: float, beta: float) -> float:
    z = 0.0
    for r in range(1, len(freqs) + 1):
        z += (r + beta) ** (-s)
    log_z = math.log(z)
    ll = 0.0
    for r in range(1, len(freqs) + 1):
        ll += freqs[r - 1] * (-s * math.log(r + beta) - log_z)
    return ll


def fit_zipf_mandelbrot_mle(freqs: Sequence[float]) -> ZipfMandelbrotFit | None:
    """Fit a truncated Zipf–Mandelbrot rank–frequency model by maximizing the
    multinomial log-likelihood over a coarse ``(s, β)`` grid refined twice
    around the optimum. ``freqs`` are rank-ordered frequencies (rank 1 first);
    returns ``None`` for fewer than five ranks."""
    if len(freqs) < 5:
        return None
    best_s, best_beta, best_ll = 1.0, 0.0, -math.inf

    def evaluate(s: float, beta: float) -> None:
        nonlocal best_s, best_beta, best_ll
        ll = _zm_log_lik(freqs, s, beta)
        if ll > best_ll:
            best_s, best_beta, best_ll = s, beta, ll

    # Coarse grid, then two refinement passes around the running optimum. The
    # float accumulation mirrors the workbench loop exactly (same grid points).
    s = 0.2
    while s <= 3.0001:
        beta = 0.0
        while beta <= 15.0001:
            evaluate(s, beta)
            beta += 0.5
        s += 0.1
    for pass_i in range(2):
        s_step = 0.02 if pass_i == 0 else 0.004
        b_step = 0.1 if pass_i == 0 else 0.02
        s0, b0 = best_s, best_beta
        s = s0 - 5 * s_step
        while s <= s0 + 5 * s_step:
            beta = max(0.0, b0 - 5 * b_step)
            while beta <= b0 + 5 * b_step:
                evaluate(max(0.01, s), beta)
                beta += b_step
            s += s_step

    s, beta = best_s, best_beta
    z = 0.0
    for r in range(1, len(freqs) + 1):
        z += (r + beta) ** (-s)
    log_z = math.log(z)

    n = 0.0
    for f in freqs:
        n += f
    if n <= 0:
        return None
    cum_emp = cum_fit = ks = 0.0
    for r in range(1, len(freqs) + 1):
        cum_emp += freqs[r - 1] / n
        cum_fit += ((r + beta) ** (-s)) / z
        d = abs(cum_emp - cum_fit)
        if d > ks:
            ks = d

    sy = syy = ss_res = 0.0
    m = 0
    for r in range(1, len(freqs) + 1):
        if freqs[r - 1] <= 0:
            continue
        obs = math.log(freqs[r - 1])
        fit = math.log(n) - s * math.log(r + beta) - log_z
        sy += obs
        syy += obs * obs
        ss_res += (obs - fit) * (obs - fit)
        m += 1
    ss_tot = syy - (sy * sy) / m
    r2_log = max(0.0, 1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return ZipfMandelbrotFit(s=s, beta=beta, ks=ks, r2_log=r2_log, log_z=log_z)


def spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation, with average ranks for ties.

    One number for "do two paired series rank their items the same way?" — e.g.
    do two scripts use a shared signary in the same proportions? Returns 0 for
    fewer than 3 points, mismatched lengths, or a constant series."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return 0.0

    def rank(vals: Sequence[float]) -> list[float]:
        idx = sorted(range(n), key=lambda i: vals[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[idx[j + 1]] == vals[idx[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[idx[k]] = avg
            i = j + 1
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = vx = vy = 0.0
    for i in range(n):
        dx = rx[i] - mx
        dy = ry[i] - my
        cov += dx * dy
        vx += dx * dx
        vy += dy * dy
    return cov / math.sqrt(vx * vy) if vx > 0 and vy > 0 else 0.0
