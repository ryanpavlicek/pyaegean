"""Permutation / Monte-Carlo null models for the Aegean structure heuristics.

The highest-integrity move for an undeciphered-script toolkit: never report a
structure statistic as a bare number. Pair it with an explicit *null* and a
p-value, so a reader knows whether the value is what randomness alone would
produce. This module supplies seeded null generators and a single
:func:`monte_carlo_p` driver that scores any statistic against them.

A "word" here is a multi-sign token written sign-hyphen-sign (the convention of
:mod:`aegean.analysis.surprisal` and :mod:`aegean.analysis.edge`): e.g.
``"A-TA-I-WA-JA"``. A statistic is any ``Callable[[Sequence[str]], float]`` over
such a word list, the larger the more "structured" (the p-value is one-sided,
upper-tail). Bring your own: graphotactic surprisal, an affix edge-bias total, a
repeat count, a clustering score.

Two nulls, and *exactly* what each preserves:

- ``within_word`` — **within-word sign permutation.** Pools every sign of the
  corpus and redeals it into words of the original lengths. Preserves: the
  per-word length (so the length distribution is identical) and the corpus-wide
  unigram-sign multiset (so each sign's total count is identical, hence the
  unigram distribution). Destroys: sign *order* and any within-word sign
  co-occurrence. Use it to ask "is the observed sign *ordering* / adjacency
  structure more than the unigram frequencies and word lengths force?"
- ``reshuffle`` — **length-stratified whole-word reshuffle.** Permutes the word
  list within length strata (words of equal sign-length are shuffled among
  themselves). Preserves: every word *intact* (its exact internal sign
  sequence) and the per-length word counts. Destroys: word *position* in the
  list / the pairing of a word with its document slot. Use it for statistics
  that read positional or sequential arrangement of whole words, where the
  within-word structure must be held fixed.

Both draw from :func:`aegean.analysis.stats.mulberry32`, so a reported p-value
is reproducible from its ``seed`` and ``n``.

**Exploratory.** On an undeciphered script (Linear A, Cypro-Minoan) a small
p-value says the statistic departs from the stated null. It does **not** confirm
a linguistic interpretation, a morpheme, or a reading. It surfaces a lead that
survived an explicit chance baseline, nothing more. Honest reporting names the
null, the seed, and ``n`` alongside the p-value.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .stats import mulberry32

__all__ = [
    "MonteCarloResult",
    "within_word_null",
    "length_reshuffle_null",
    "monte_carlo_p",
]

Statistic = Callable[[Sequence[str]], float]


@dataclass(frozen=True)
class MonteCarloResult:
    """A Monte-Carlo permutation test of one structure statistic against a null.

    ``observed`` is the statistic on the real word list. ``p_value`` is the
    one-sided (upper-tail) permutation p-value ``(1 + #{null ≥ observed}) / (1 +
    n)`` — the add-one form (Davison & Hinkley 1997, North et al. 2002), so it is
    never exactly 0 and is valid for finite ``n``. ``null_mean`` and the
    ``[null_low, null_high]`` percentile band summarize the null distribution at
    ``level`` confidence; ``n`` is the number of null replicates and ``null``
    names the generator. A small ``p_value`` means the observed value sits in the
    upper tail of what the null produces (more "structured" than chance under
    *that* null); a ``p_value`` near 0.5 means it is unremarkable."""

    observed: float
    p_value: float
    null_mean: float
    null_low: float
    null_high: float
    level: float
    n: int
    null: str


def _shuffle(items: list[str], rand: Callable[[], float]) -> list[str]:
    """In-place Fisher-Yates shuffle of ``items`` using ``rand`` (returns the list)."""
    for i in range(len(items) - 1, 0, -1):
        j = int(rand() * (i + 1))
        if j > i:  # rand() == 1.0 cannot occur, but guard the index defensively
            j = i
        items[i], items[j] = items[j], items[i]
    return items


def _signs_of(word: str) -> list[str]:
    """The signs of one word, splitting on ``-`` (a single-sign word is one sign)."""
    return word.split("-")


def within_word_null(words: Sequence[str], rand: Callable[[], float]) -> list[str]:
    """One within-word sign-permutation null replicate of ``words``.

    Pools every sign across the whole corpus, shuffles the pool, and redeals it
    into words of the *original* sign-lengths (in order). **Preserves** the
    per-word length sequence and the corpus-wide unigram-sign multiset (each
    sign's total count); **destroys** sign order and within-word co-occurrence.
    ``rand`` is a zero-argument ``[0, 1)`` source (e.g. from
    :func:`aegean.analysis.stats.mulberry32`)."""
    lengths = [len(_signs_of(w)) for w in words]
    pool: list[str] = []
    for w in words:
        pool.extend(_signs_of(w))
    _shuffle(pool, rand)
    out: list[str] = []
    pos = 0
    for length in lengths:
        out.append("-".join(pool[pos : pos + length]))
        pos += length
    return out


def length_reshuffle_null(words: Sequence[str], rand: Callable[[], float]) -> list[str]:
    """One length-stratified whole-word reshuffle replicate of ``words``.

    Groups the words by sign-length and shuffles each length stratum among its
    own members, then reassembles in the original length-slot order.
    **Preserves** every word intact (its exact internal sign sequence) and the
    per-length word counts; **destroys** the position of a word within its
    length stratum. ``rand`` is a zero-argument ``[0, 1)`` source."""
    by_len: dict[int, list[str]] = {}
    lengths = [len(_signs_of(w)) for w in words]
    for length, w in zip(lengths, words, strict=True):
        by_len.setdefault(length, []).append(w)
    for bucket in by_len.values():
        _shuffle(bucket, rand)
    cursor = dict.fromkeys(by_len, 0)
    out: list[str] = []
    for length in lengths:
        i = cursor[length]
        out.append(by_len[length][i])
        cursor[length] = i + 1
    return out


_NULLS: dict[str, Callable[[Sequence[str], Callable[[], float]], list[str]]] = {
    "within_word": within_word_null,
    "reshuffle": length_reshuffle_null,
}


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated quantile of an already-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def monte_carlo_p(
    observed: float,
    statistic: Statistic,
    words: Sequence[str],
    *,
    null: str = "within_word",
    n: int = 999,
    seed: int = 0,
    level: float = 0.95,
) -> MonteCarloResult:
    """One-sided permutation p-value of a structure ``statistic`` against a null.

    Generates ``n`` null word lists with the chosen ``null`` generator (each
    seeded from ``mulberry32(seed)``), scores ``statistic`` on each, and compares
    the ``observed`` value to that null distribution.

    The p-value is the add-one upper-tail estimate ``(1 + #{null ≥ observed}) /
    (1 + n)``: it is one-sided, treats *larger* statistic values as more
    "structured", and is bounded away from 0 so a finite ``n`` never reports an
    impossibly exact result. Pass ``observed = statistic(words)`` for the usual
    case; it is a separate argument only so a precomputed or differently
    measured observed value can be tested against the same null.

    ``null`` is ``"within_word"`` (within-word sign permutation: holds word
    lengths and the unigram-sign counts, breaks sign order) or ``"reshuffle"``
    (length-stratified whole-word reshuffle: holds each word intact, breaks word
    position). See the module docstring for exactly what each preserves.

    **Exploratory.** A small p-value means the statistic exceeds what this null
    produces; it is evidence of *structure relative to the null*, not a
    decipherment or a linguistic claim. Always report the null name, ``seed``,
    and ``n`` with the number.
    """
    if null not in _NULLS:
        raise ValueError(f"null must be one of {sorted(_NULLS)}, got {null!r}")
    if n < 1:
        raise ValueError("n must be at least 1")
    if not 0 < level < 1:
        raise ValueError("level must be in (0, 1)")
    generate = _NULLS[null]
    rand = mulberry32(seed)
    null_values: list[float] = []
    at_least = 0
    for _ in range(n):
        value = float(statistic(generate(words, rand)))
        null_values.append(value)
        if value >= observed:
            at_least += 1
    null_values.sort()
    mean = sum(null_values) / n
    alpha = (1.0 - level) / 2.0
    return MonteCarloResult(
        observed=observed,
        p_value=(1 + at_least) / (1 + n),
        null_mean=mean,
        null_low=_percentile(null_values, alpha),
        null_high=_percentile(null_values, 1.0 - alpha),
        level=level,
        n=n,
        null=null,
    )
