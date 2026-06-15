"""Graphotactic surprisal: a Witten-Bell-smoothed sign-bigram model.

A first-order sign-bigram model over a multi-sign word vocabulary, scored
*leave-one-out* so a word never earns credit for transitions only it attests.
High mean surprisal = a sign sequence the rest of the corpus doesn't write —
candidate loanwords, foreign names, scribal errors, or damaged readings. This is
sequence-level only: it knows nothing about phonetic values or meaning, and on a
small undeciphered corpus it is exploratory.

Ported 1:1 from the Linear A Research Workbench's ``src/lib/surprisal.ts``;
values match the TS unit tests. Pair it with a lexical-token filter
(:func:`aegean.scripts.lineara.commodities.is_lexical_word`) to score real words
rather than logogram chains.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

__all__ = [
    "SignBigramModel",
    "train_sign_bigram_model",
    "SurprisalStep",
    "WordSurprisal",
    "word_surprisal",
]

_START = "^"
_END = "$"


def _transitions_of(word: str) -> list[tuple[str, str]]:
    """The transitions of a word with boundary markers: ^→p₁, p₁→p₂, …, pₙ→$."""
    parts = word.split("-")
    out: list[tuple[str, str]] = [(_START, parts[0])]
    for i in range(len(parts) - 1):
        out.append((parts[i], parts[i + 1]))
    out.append((parts[-1], _END))
    return out


@dataclass(frozen=True)
class SignBigramModel:
    """A trained first-order sign-bigram model.

    ``bigram`` maps a context to (next → token count); contexts include ``^`` and
    nexts include ``$``. ``context_total`` is the outgoing tokens per context,
    ``cont_types`` the distinct continuations per context (Witten-Bell's T(a)),
    ``next_count`` the next-symbol token counts (the backoff distribution),
    ``total`` the transition-token total, and ``vocab`` the number of distinct
    next symbols."""

    bigram: dict[str, dict[str, int]]
    context_total: dict[str, int]
    cont_types: dict[str, int]
    next_count: dict[str, int]
    total: int
    vocab: int


def train_sign_bigram_model(words: Iterable[tuple[str, int]]) -> SignBigramModel:
    """Train the bigram model on a multi-sign vocabulary, token-weighted.

    ``words`` is an iterable of ``(word, count)`` pairs; single-sign words (no
    ``-``) are skipped. A transition in a 20× word counts 20 times — the model
    describes what scribes actually wrote, not the type list."""
    bigram: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    context_total: dict[str, int] = defaultdict(int)
    next_count: dict[str, int] = defaultdict(int)
    total = 0
    for word, count in words:
        if "-" not in word:
            continue
        for a, b in _transitions_of(word):
            bigram[a][b] += count
            context_total[a] += count
            next_count[b] += count
            total += count
    cont_types = {a: len(inner) for a, inner in bigram.items()}
    return SignBigramModel(
        bigram={a: dict(inner) for a, inner in bigram.items()},
        context_total=dict(context_total),
        cont_types=cont_types,
        next_count=dict(next_count),
        total=total,
        vocab=len(next_count),
    )


@dataclass(frozen=True)
class SurprisalStep:
    """One transition's surprisal in bits, showing *where* a word is improbable."""

    from_: str
    to: str
    bits: float


@dataclass(frozen=True)
class WordSurprisal:
    """A scored word: ``mean`` bits per transition (boundaries included — the
    headline number) and the per-transition ``steps``."""

    mean: float
    steps: list[SurprisalStep]


def word_surprisal(model: SignBigramModel, word: str, self_count: int = 0) -> WordSurprisal:
    """Score ``word`` against the model.

    ``self_count`` is the word's own corpus token count: its contribution is
    subtracted from every count before computing probabilities (leave-one-out),
    *per occurrence* — a word like a-b-a-b carries a→b twice, so its two
    self-occurrences are both removed there. Pass 0 to score a hypothetical word
    not in the corpus. Probabilities use add-one-smoothed Witten-Bell backoff, so
    unseen symbols keep nonzero mass and bits stay finite and non-negative."""
    trans = _transitions_of(word)
    self_bg: dict[tuple[str, str], int] = defaultdict(int)
    self_ctx: dict[str, int] = defaultdict(int)
    self_next: dict[str, int] = defaultdict(int)
    if self_count > 0:
        for a, b in trans:
            self_bg[(a, b)] += self_count
            self_ctx[a] += self_count
            self_next[b] += self_count
    total_adj = max(1, model.total - self_count * len(trans))
    steps: list[SurprisalStep] = []
    total_bits = 0.0
    for a, b in trans:
        raw_ab = model.bigram.get(a, {}).get(b, 0)
        cab = max(0, raw_ab - self_bg.get((a, b), 0))
        ca = max(0, model.context_total.get(a, 0) - self_ctx.get(a, 0))
        t = model.cont_types.get(a, 0)
        # If removing this word zeroes the transition type, T(a) shrinks too.
        if cab == 0 and raw_ab > 0:
            t = max(0, t - 1)
        cb = max(0, model.next_count.get(b, 0) - self_next.get(b, 0))
        p_bg = (cb + 1) / (total_adj + model.vocab + 1)
        denom = ca + t
        p = (cab + t * p_bg) / denom if denom > 0 else p_bg
        bits = -math.log2(min(1.0, max(p, 1e-12)))
        steps.append(SurprisalStep(from_=a, to=b, bits=bits))
        total_bits += bits
    return WordSurprisal(mean=total_bits / len(trans) if trans else 0.0, steps=steps)
