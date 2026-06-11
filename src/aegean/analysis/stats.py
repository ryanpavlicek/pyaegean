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
from typing import Any

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
    docs = _documents(corpus)
    if len(docs) < 2:
        raise ValueError("bootstrap needs at least 2 documents")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    rng = _random.Random(seed)
    values = sorted(
        float(statistic(rng.choices(docs, k=len(docs)))) for _ in range(n_resamples)
    )

    def quantile(q: float) -> float:
        # linear interpolation between order statistics
        pos = q * (len(values) - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)

    alpha = (1.0 - level) / 2.0
    return BootstrapCI(
        estimate=float(statistic(docs)),
        low=quantile(alpha),
        high=quantile(1.0 - alpha),
        level=level,
        n_resamples=n_resamples,
    )
