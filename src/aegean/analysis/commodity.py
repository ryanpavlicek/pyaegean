"""Linear A commodity / ideogram corpus analyses, over physical lines.

Two line-level statistics ported from the workbench's Commodity Catalog and
Semantic Classifier modules:

- **line co-occurrence PMI** — how much more often than chance a transaction
  term shares a *line* with a given commodity logogram.
- **ideogram-group exclusivity** — what fraction of a word's ideogram
  co-occurrences fall in one commodity group (1.0 = the word is seen only with
  that one commodity).

Both take an iterable of *lines* (each a list of token strings) and use the
curated commodity catalog in :mod:`aegean.scripts.lineara.commodities`. They are
exploratory descriptions of an undeciphered corpus, not lexical claims.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..scripts.lineara.commodities import (
    COMMODITIES,
    commodity_head,
    is_undeciphered_logogram,
)

__all__ = [
    "line_cooccurrence_pmi",
    "ExclusivityRow",
    "ideogram_group_exclusivity",
]


def _ideogram_of(token: str) -> str | None:
    """The commodity-group key of a token: its catalog head, else the raw
    ``*NNN`` undeciphered logogram, else ``None``."""
    head = commodity_head(token)
    if head is not None:
        return head
    if is_undeciphered_logogram(token):
        return token
    return None


def line_cooccurrence_pmi(
    lines: Iterable[Sequence[str]],
    head: str,
    *,
    min_joint: int = 2,
) -> list[tuple[str, float]]:
    """Line-level PMI of each transaction term against a commodity ``head``,
    strongest first.

    The event space is the set of physical lines: a term and the commodity are
    each counted once per line they appear on (deduplicated). For a term *t* with
    ``joint`` lines holding both, ``commodity_lines`` holding the commodity, and
    ``term_lines`` holding the term, out of ``total_lines`` lines::

        PMI(t) = log₂( joint · total_lines / (commodity_lines · term_lines) )

    A *term* is any token containing a hyphen; a *commodity* is any token that
    resolves to ``head`` via the catalog (ligatures / sex markers folded) or, for
    ``*NNN``, the raw logogram. Only terms sharing at least ``min_joint`` lines
    with the commodity are returned (a hard cutoff, not smoothing); PMI may be
    negative. ``head`` may be a catalog head (``"GRA"``) or an undeciphered
    ``"*NNN"``."""
    total_lines = 0
    commodity_lines = 0
    term_lines: dict[str, int] = defaultdict(int)
    joint: dict[str, int] = defaultdict(int)
    for line in lines:
        total_lines += 1
        terms = {t for t in line if "-" in t}
        for t in terms:
            term_lines[t] += 1
        heads = {g for g in (_ideogram_of(tok) for tok in line) if g is not None}
        if head in heads:
            commodity_lines += 1
            for t in terms:
                joint[t] += 1
    if commodity_lines == 0 or total_lines == 0:
        return []
    out: list[tuple[str, float]] = []
    for t, j in joint.items():
        if j < min_joint:
            continue
        pmi = math.log2((j * total_lines) / (commodity_lines * term_lines[t]))
        out.append((t, pmi))
    out.sort(key=lambda tp: (-tp[1], tp[0]))
    return out


@dataclass(frozen=True)
class ExclusivityRow:
    """One (ideogram group, co-occurring word) pair: the in-group co-occurrence
    ``count``, the word's ``word_total`` across all groups, and ``exclusivity`` =
    count / word_total (1.0 = the word is seen only with this group)."""

    group: str
    gloss: str
    word: str
    count: int
    word_total: int
    exclusivity: float


def ideogram_group_exclusivity(lines: Iterable[Sequence[str]]) -> list[ExclusivityRow]:
    """How exclusively each hyphenated word co-occurs (per line) with one
    ideogram group.

    For every line, each ideogram occurrence is paired with each hyphenated word
    on the same line (multiplicity kept, not deduplicated). ``exclusivity`` of a
    word in a group is its in-group co-occurrence count divided by its total
    ideogram co-occurrences across all groups — so values for a fixed word sum to
    1 across groups. A high exclusivity with a count ≥ 2 is the workbench's
    "strong domain evidence" signal. This is a descriptive share, not an
    association test (no smoothing, no expected-value model)."""
    cooc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for line in lines:
        line_words = [w for w in line if "-" in w]
        for tok in line:
            g = _ideogram_of(tok)
            if g is None:
                continue
            for ww in line_words:
                if ww == tok:
                    continue
                cooc[g][ww] += 1
    word_total: dict[str, int] = defaultdict(int)
    for counts in cooc.values():
        for w, c in counts.items():
            word_total[w] += c

    def _gloss(group: str) -> str:
        entry = COMMODITIES.get(group)
        return entry.gloss if entry is not None else "undeciphered commodity"

    rows: list[ExclusivityRow] = []
    for group in sorted(cooc, key=lambda g: (-len(cooc[g]), g)):
        for word, count in sorted(
            cooc[group].items(), key=lambda wc: (-(wc[1] / word_total[wc[0]]), -wc[1], wc[0])
        ):
            rows.append(
                ExclusivityRow(
                    group=group,
                    gloss=_gloss(group),
                    word=word,
                    count=count,
                    word_total=word_total[word],
                    exclusivity=count / word_total[word],
                )
            )
    return rows
