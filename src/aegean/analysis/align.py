"""Alignment: per-phoneme alignment of two phonetic strings, and word-level
multiple-sequence alignment of inscriptions.

Faithful port of the alignment routines in the workbench ``src/lib/algorithms.ts``
(`align_phonetic`) and ``src/lib/compareAlign.ts`` (`align_sequences`).
The HTML/Markdown report builder from ``compareAlign.ts`` is presentational and
intentionally not ported.

**Exploratory**, like the underlying distance metric: an alignment visualizes a
*hypothesised* phoneme correspondence, not an established sound law.
"""

from __future__ import annotations

from dataclasses import dataclass

from .distance import (
    DEFAULT_PHONETIC_CLASSES,
    DEFAULT_WEIGHTS,
    PhoneticClasses,
    PhoneticWeights,
    _is_vowel,
    _same_class,
    _sub_cost,
)

# Per-position alignment operation.
#   "match" | "sub-vowel" | "sub-class" | "sub-far" | "ins" (gap in a) | "del"
AlignOp = str


@dataclass(frozen=True, slots=True)
class AlignCell:
    """One aligned position: a char from ``a`` (or "" for ins), a char from
    ``b`` (or "" for del), and the operation that relates them."""

    a: str
    b: str
    op: AlignOp


def align_phonetic(
    a: str,
    b: str,
    w: PhoneticWeights = DEFAULT_WEIGHTS,
    cl: PhoneticClasses = DEFAULT_PHONETIC_CLASSES,
) -> list[AlignCell]:
    """Run the weighted Levenshtein, then backtrace to emit a per-position
    alignment classifying each substitution as vowel / same-class / far."""
    n, m = len(a), len(b)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i * w.indel
    for j in range(m + 1):
        d[0][j] = j * w.indel
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j] + w.indel,
                d[i][j - 1] + w.indel,
                d[i - 1][j - 1] + _sub_cost(a[i - 1], b[j - 1], w, cl),
            )

    out: list[AlignCell] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            ai, bj = a[i - 1], b[j - 1]
            cost = _sub_cost(ai, bj, w, cl)
            if d[i][j] == d[i - 1][j - 1] + cost:
                if ai == bj:
                    op = "match"
                elif _is_vowel(ai, cl) and _is_vowel(bj, cl):
                    op = "sub-vowel"
                elif _same_class(ai, bj, cl):
                    op = "sub-class"
                else:
                    op = "sub-far"
                out.append(AlignCell(ai, bj, op))
                i -= 1
                j -= 1
                continue
        if i > 0 and d[i][j] == d[i - 1][j] + w.indel:
            out.append(AlignCell(a[i - 1], "", "del"))
            i -= 1
            continue
        out.append(AlignCell("", b[j - 1], "ins"))
        j -= 1
    out.reverse()
    return out


# ── Word-level multiple-sequence alignment (progressive Needleman–Wunsch) ────
# One aligned position: a word (or None gap) for each inscription column.
AlnPos = list[str | None]


def _rep_word(p: AlnPos) -> str | None:
    for word in p:
        if word:
            return word
    return None


def add_sequence(aln: list[AlnPos], seq: list[str], prior_n: int) -> list[AlnPos]:
    """Add one word sequence to a growing alignment via Needleman–Wunsch at the
    word level (exact-token match rewarded, substitution columns allowed, gaps
    penalized). ``prior_n`` is how many sequences are already in the alignment."""
    P = len(aln)
    L = len(seq)
    GAP, MATCH, MIS = -1, 2, 0
    dp = [[0] * (L + 1) for _ in range(P + 1)]
    # traceback: 0 diag, 1 up (gap in new seq), 2 left (new column)
    tb = [[0] * (L + 1) for _ in range(P + 1)]
    for i in range(1, P + 1):
        dp[i][0] = dp[i - 1][0] + GAP
        tb[i][0] = 1
    for j in range(1, L + 1):
        dp[0][j] = dp[0][j - 1] + GAP
        tb[0][j] = 2
    for i in range(1, P + 1):
        for j in range(1, L + 1):
            r = _rep_word(aln[i - 1])
            s = MATCH if (r is not None and r == seq[j - 1]) else MIS
            diag = dp[i - 1][j - 1] + s
            up = dp[i - 1][j] + GAP
            left = dp[i][j - 1] + GAP
            best, t = diag, 0
            if up > best:
                best, t = up, 1
            if left > best:
                best, t = left, 2
            dp[i][j] = best
            tb[i][j] = t

    out: list[AlnPos] = []
    i, j = P, L
    while i > 0 or j > 0:
        t = tb[i][j] if (i > 0 and j > 0) else (1 if i > 0 else 2)
        if t == 0:
            out.append([*aln[i - 1], seq[j - 1]])
            i -= 1
            j -= 1
        elif t == 1:
            out.append([*aln[i - 1], None])
            i -= 1
        else:
            out.append([*([None] * prior_n), seq[j - 1]])
            j -= 1
    out.reverse()
    return out


def align_sequences(seqs: list[list[str]]) -> list[AlnPos]:
    """Progressive multiple alignment of word sequences (e.g. several
    inscriptions). Returns aligned positions, one column per input sequence."""
    if not seqs:
        return []
    aln: list[AlnPos] = [[w] for w in seqs[0]]
    for k in range(1, len(seqs)):
        aln = add_sequence(aln, seqs[k], k)
    return aln
