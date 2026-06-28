"""Unsupervised morpheme segmentation by Harris bidirectional letter/sign variety.

Zellig Harris's (1955, 1967) cut-point method, the classic distributional
heuristic for finding morpheme boundaries with no dictionary and no labels. The
idea: walk along a word one unit at a time and count, over the whole word list,
how many *distinct* units can follow the prefix you have so far (the **successor
variety**). At a real morpheme boundary the next unit is comparatively
unconstrained — many words share the stem but branch into different affixes — so
the variety *spikes*. Running the same count on the reversed words gives
**predecessor variety**, which spikes at the same boundaries from the other side.
A boundary is placed wherever either curve shows a local peak.

A *unit* is a single sign for hyphen-joined syllabic words (``KU-RO`` -> ``KU``,
``RO``) and a single character otherwise (Greek or romanized letters); the two
never mix within a word. Token frequencies are ignored: the tries are built over
the word **types**, which is how Harris variety is defined (a stem's branching is
a property of the vocabulary, not of how often each word was written).

Two entry points:

- :func:`segment` returns one :class:`Segmentation` per input word, with the
  inferred cuts and the resulting unit-group pieces.
- :func:`candidate_morphs` ranks the recurring *final* pieces (the segment that
  ends each word) by how many distinct words carry them — a quick read on which
  word-final strings behave like a shared, productive suffix.

**EXPLORATORY.** This is a distributional heuristic, not a morphological
analysis. A recurring final unit-string is a *candidate* morph: a string the
vocabulary reuses, **not** a confirmed morpheme, and certainly not a gloss. On
undeciphered scripts (Linear A, Cypro-Minoan) it surfaces structure and leads
only, never ground truth. It is also weakest exactly where the Aegean material
is hardest: corpora dominated by hapax legomena give the variety counts very
little to work with, so treat the cuts as hypotheses to inspect, not findings.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = [
    "Segmentation",
    "segment",
    "candidate_morphs",
]


def _units(word: str) -> tuple[str, ...]:
    """Split a word into segmentation units.

    Hyphen-joined syllabic words split on ``-`` into signs (``KU-RO`` ->
    ``("KU", "RO")``); everything else splits into single characters. Empty
    sign fields (a leading, trailing, or doubled ``-``) are dropped."""
    if "-" in word:
        return tuple(p for p in word.split("-") if p)
    return tuple(word)


class _Trie:
    """A prefix trie over unit sequences, recording the branching set at each node.

    Built once over the whole (de-duplicated) word list. ``variety(prefix)`` is
    Harris's successor variety: the number of distinct units that immediately
    follow ``prefix`` somewhere in the vocabulary. The reverse trie (words fed in
    reversed) yields predecessor variety the same way."""

    __slots__ = ("_children",)

    def __init__(self, sequences: Iterable[Sequence[str]]) -> None:
        # Map each prefix (as a tuple) to the set of units seen immediately after it.
        children: dict[tuple[str, ...], set[str]] = defaultdict(set)
        for seq in sequences:
            prefix: tuple[str, ...] = ()
            for unit in seq:
                children[prefix].add(unit)
                prefix = (*prefix, unit)
        self._children = children

    def variety(self, prefix: Sequence[str]) -> int:
        """Distinct units that follow ``prefix`` across the vocabulary (0 if none)."""
        return len(self._children.get(tuple(prefix), ()))


@dataclass(frozen=True)
class Segmentation:
    """One word's Harris segmentation.

    ``word`` is the input string; ``units`` its unit sequence (signs for a
    hyphen-joined word, characters otherwise); ``cuts`` the inferred boundary
    offsets into ``units`` (each ``c`` means a boundary *before* ``units[c]``, so
    cuts are in ``1 .. len(units)-1``); and ``pieces`` the resulting unit-group
    morphs, each joined the same way the word was (``-`` for signs, else
    concatenated). A single-unit or empty word has no cuts and one piece."""

    word: str
    units: tuple[str, ...]
    cuts: tuple[int, ...]
    pieces: tuple[str, ...]


def _peak_cuts(curve: Sequence[int]) -> set[int]:
    """Cut offsets at the local peaks of one direction's variety ``curve``.

    ``curve[i]`` is the branching variety after the prefix of length ``i + 1``,
    measured over the vocabulary; ``curve[i]`` peaking marks a boundary *after*
    that prefix, i.e. a cut at offset ``i + 1``. A peak is a *strict* local
    maximum, a non-decrease into the position and a strict decrease out of it, so
    a plateau cuts at its last position (before the variety falls) and a flat
    curve proposes nothing. The first position is therefore a peak when it
    strictly exceeds its right neighbour, the dominant case for predecessor
    variety where the count is highest right at the affix boundary. The offsets
    returned are in ``1 .. len(curve) - 1`` (the caller clamps to a word's
    valid range)."""
    n = len(curve)
    cuts: set[int] = set()
    for i in range(n):
        up = i == 0 or curve[i] >= curve[i - 1]
        down = i < n - 1 and curve[i] > curve[i + 1]
        if up and down:
            cuts.add(i + 1)
    return cuts


def _segment_units(
    units: tuple[str, ...], forward: _Trie, backward: _Trie
) -> tuple[int, ...]:
    """Bidirectional Harris cut offsets for one word's ``units``.

    Successor variety is read forward off ``forward``; predecessor variety is read
    off ``backward`` over the reversed units, then its peaks are mirrored back into
    forward offsets. The two cut sets are unioned (a boundary either direction
    proposes is kept)."""
    n = len(units)
    if n < 2:
        return ()
    # Successor variety after each prefix of length 1 .. n-1.
    succ = [forward.variety(units[:i]) for i in range(1, n)]
    # Predecessor variety: walk the reversed word, score, mirror offsets.
    rev = units[::-1]
    pred = [backward.variety(rev[:i]) for i in range(1, n)]

    left_cuts = _peak_cuts(succ)
    # A predecessor peak at reversed cut-offset c detaches the last c units, i.e.
    # a boundary at forward offset n - c.
    right_cuts = {n - c for c in _peak_cuts(pred)}
    cuts = {c for c in (left_cuts | right_cuts) if 0 < c < n}
    return tuple(sorted(cuts))


def _join(units: Sequence[str], hyphenated: bool) -> str:
    return "-".join(units) if hyphenated else "".join(units)


def _pieces(units: tuple[str, ...], cuts: tuple[int, ...], hyphenated: bool) -> tuple[str, ...]:
    bounds = [0, *cuts, len(units)]
    return tuple(
        _join(units[a:b], hyphenated) for a, b in zip(bounds, bounds[1:]) if b > a
    )


def segment(words: Iterable[str]) -> list[Segmentation]:
    """Harris bidirectional segmentation for every word, input order preserved.

    Forward and backward unit tries are built once over the de-duplicated word
    list; each word is then cut at the local peaks of its successor- and
    predecessor-variety curves (the two boundary sets are unioned). Duplicate
    input words yield identical :class:`Segmentation` records. Single-unit and
    empty words return uncut, with one piece (or none).

    EXPLORATORY: the cuts are distributional hypotheses. See the module
    docstring; on hapax-heavy undeciphered corpora the variety signal is thin."""
    word_list = list(words)
    seen: list[tuple[str, ...]] = []
    seen_set: set[tuple[str, ...]] = set()
    for w in word_list:
        u = _units(w)
        if u and u not in seen_set:
            seen_set.add(u)
            seen.append(u)
    forward = _Trie(seen)
    backward = _Trie([u[::-1] for u in seen])

    out: list[Segmentation] = []
    for w in word_list:
        units = _units(w)
        hyphenated = "-" in w
        cuts = _segment_units(units, forward, backward)
        out.append(
            Segmentation(
                word=w,
                units=units,
                cuts=cuts,
                pieces=_pieces(units, cuts, hyphenated),
            )
        )
    return out


def candidate_morphs(words: Iterable[str], *, min_count: int = 2) -> list[tuple[str, int]]:
    """Recurring word-final candidate morphs, by the count of distinct words bearing them.

    Each word is segmented (see :func:`segment`); a word's **final** piece, i.e.
    the unit-group after its last cut, is taken as its candidate suffix. The count
    for a morph is the number of *distinct* word types ending in it (so a single
    word repeated cannot inflate a morph), and only morphs reaching ``min_count``
    distinct words and at least one cut (the word actually had a stem before the
    morph) are returned. Sorted by count descending, then by the morph string.

    EXPLORATORY: a high count means the vocabulary reuses that final string after
    a variety-peak boundary, a *candidate* productive suffix, never a confirmed
    morpheme or a meaning. Read the ranking as leads to inspect."""
    if min_count < 1:
        raise ValueError(f"min_count must be >= 1, got {min_count}")
    bearers: dict[str, set[str]] = defaultdict(set)
    for seg in segment(words):
        if not seg.cuts or len(seg.pieces) < 2:
            continue
        bearers[seg.pieces[-1]].add(seg.word)
    counts = Counter({morph: len(ws) for morph, ws in bearers.items()})
    rows = [(morph, n) for morph, n in counts.items() if n >= min_count]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows
