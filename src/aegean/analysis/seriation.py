"""Seriation and rough chronology for assemblage data (EXPLORATORY).

Two classic archaeological tools, ported to the corpus model:

- :func:`chronology` reads each document's free-text ``meta.period`` into a numeric
  ``(start, end)`` year span, **reusing** :func:`aegean.viz.parse_period` (the same
  best-effort origDate reader the timeline plot uses), and reports the fraction it
  could not parse. What is unparseable is counted and surfaced, never guessed.
- :func:`seriate` builds the Brainerd-Robinson similarity matrix over an abundance
  table (rows = assemblages / documents, columns = types) and orders the rows by a
  deterministic spectral ordering (the Fiedler vector of the similarity's Laplacian),
  the seriation ordering that puts similar assemblages next to each other. Rows sharing
  no type at all are related by no similarity evidence, so the similarity graph is
  seriated one connected block at a time and the blocks are then placed by a stated
  convention. The result is independent of the order the rows were supplied in (up to
  the inherent reversal); where the similarity leaves the sequence genuinely
  undetermined, :func:`seriate` says so instead of inventing an order.

**Exploratory.** Seriation orders assemblages by *compositional similarity*; it is a
hypothesis about relative sequence, not a date. It has no inherent direction (an
ordering and its exact reverse are equally good solutions) and no absolute anchor:
tying either end to a calendar year needs external evidence. On the undeciphered
Aegean material a "type" is a sign or word form, so a seriation reflects graphotactic
or scribal drift as readily as time. Treat the output as a lead for a specialist to
test against stratigraphy and palaeography, never as dating evidence in itself.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..core.model import Document, TokenKind

__all__ = [
    "DocumentSpan",
    "Chronology",
    "chronology",
    "brainerd_robinson",
    "SeriationResult",
    "seriate",
]


def _documents(corpus: Any) -> list[Document]:
    """Coerce a single Document, a corpus, a query's results, or an iterable to a list.

    `Corpus.query` returns `aegean.analysis.QueryResults`, whose matched documents are its
    ``inscriptions``, so a queried subset can be dated or seriated directly. Anything else
    that yields documents (a `Corpus`, a plain list) is taken as it comes; anything that
    does not raises a ``TypeError`` naming what arrived."""
    if isinstance(corpus, Document):
        return [corpus]
    docs = getattr(corpus, "inscriptions", None)
    if docs is None:
        docs = getattr(corpus, "documents", corpus)
    try:
        out = list(docs)
    except TypeError:
        raise TypeError(
            f"expected a corpus or documents, got {type(corpus).__name__}"
        ) from None
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _matched_documents(obj: Any) -> list[Document] | None:
    """A query's matched documents, or ``None`` for anything that is not a result set.

    `Corpus.query` returns `aegean.analysis.QueryResults`, which holds its matches in
    ``inscriptions``. Standing the matches in for the result set at the entry point lets
    every path below treat a query exactly as it treats the same list of documents."""
    docs = getattr(obj, "inscriptions", None)
    return None if docs is None else list(docs)


def _is_corpus_like(obj: Any) -> bool:
    """True if ``obj`` is a Document, a Corpus (has ``.documents``), a query's results
    (which carry their matches in ``inscriptions``), or an iterable whose first element is
    a Document. A bare 2-D number matrix is not corpus-like."""
    if isinstance(obj, Document):
        return True
    docs = _matched_documents(obj)
    if docs is None:
        docs = getattr(obj, "documents", None)
    if docs is not None:
        docs = list(docs)
        return bool(docs) and isinstance(docs[0], Document)
    # A plain list/tuple/iterable of Documents (but not a matrix of numbers).
    try:
        first = next(iter(obj), None)
    except TypeError:
        return False
    return isinstance(first, Document)


# --------------------------------------------------------------------------- #
# Chronology
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DocumentSpan:
    """One document's parsed date span (EXPLORATORY, best-effort).

    ``start``/``end`` are years with BCE negative and CE positive (e.g. ``-480``);
    both are ``None`` when ``meta.period`` carried no readable century or era-qualified
    year. ``midpoint`` is ``(start + end) / 2`` when parsed, else ``None``. The span
    comes from :func:`aegean.viz.parse_period`, a heuristic for aggregate binning, not
    a dating authority."""

    doc_id: str
    period_text: str
    start: int | None
    end: int | None

    @property
    def parsed(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def midpoint(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return (self.start + self.end) / 2


@dataclass(frozen=True)
class Chronology:
    """Per-document parsed date spans for a corpus (EXPLORATORY).

    ``spans`` is one :class:`DocumentSpan` per document in corpus order (parseable or
    not, never dropped). ``parsed``/``unparsed`` count how many spans carry a readable
    date; ``unparsed_fraction`` is ``unparsed / total``. A high unparsed fraction means
    the corpus's date metadata is mostly free text this reader cannot resolve, and any
    downstream ordering rests on only the parsed remainder."""

    spans: tuple[DocumentSpan, ...]
    parsed: int
    unparsed: int
    total: int

    @property
    def unparsed_fraction(self) -> float:
        return self.unparsed / self.total if self.total else 0.0

    def parsed_spans(self) -> list[DocumentSpan]:
        """Only the spans with a readable date, in corpus order."""
        return [s for s in self.spans if s.parsed]


def chronology(corpus: Any) -> Chronology:
    """Parse every document's ``meta.period`` into a numeric year span (EXPLORATORY).

    Reuses :func:`aegean.viz.parse_period` (BCE negative, CE positive) on each
    document's free-text date, returning a :class:`Chronology` that pairs the parsed
    spans with an honest count of what could not be read.

    Parameters
    ----------
    corpus:
        A ``Corpus``, ``QueryResults``, or iterable of ``Document``.

    **Caveat (EXPLORATORY).** ``parse_period`` is a best-effort reader of origDate-style
    strings, not a dating authority; a returned span is a coarse century-level bin, and
    the unparsed fraction is reported precisely because a corpus's dates are often
    imprecise or unreadable. This is input for a chronological hypothesis, not a date."""
    # Imported here, not at module scope: aegean.viz imports this package, so a
    # top-level import makes ``import aegean.viz`` fail in a fresh interpreter.
    from ..viz import parse_period

    docs = _documents(corpus)
    spans: list[DocumentSpan] = []
    parsed = 0
    for d in docs:
        text = d.meta.period or ""
        rng = parse_period(text)
        if rng is None:
            spans.append(DocumentSpan(d.id, text, None, None))
        else:
            parsed += 1
            spans.append(DocumentSpan(d.id, text, rng[0], rng[1]))
    total = len(docs)
    return Chronology(
        spans=tuple(spans),
        parsed=parsed,
        unparsed=total - parsed,
        total=total,
    )


# --------------------------------------------------------------------------- #
# Brainerd-Robinson similarity + seriation ordering
# --------------------------------------------------------------------------- #


def _to_matrix(rows: Sequence[Sequence[float]]) -> list[list[float]]:
    mat = [[float(x) for x in row] for row in rows]
    if not mat:
        raise ValueError("matrix has no rows")
    width = len(mat[0])
    if width == 0:
        raise ValueError("matrix rows are empty")
    if any(len(row) != width for row in mat):
        raise ValueError("all matrix rows must have the same number of columns")
    if any(x < 0 for row in mat for x in row):
        raise ValueError("abundance counts must be non-negative")
    return mat


def _row_percentages(mat: Sequence[Sequence[float]]) -> list[list[float]]:
    """Each row rescaled to sum to 100 (relative abundance); an all-zero row stays zero."""
    out: list[list[float]] = []
    for row in mat:
        total = sum(row)
        if total <= 0:
            out.append([0.0] * len(row))
        else:
            out.append([100.0 * x / total for x in row])
    return out


def brainerd_robinson(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """The Brainerd-Robinson similarity matrix of an abundance table.

    Each row of ``matrix`` (an assemblage's type counts) is first rescaled to sum to
    100, then the similarity of two rows ``p`` and ``q`` is
    ``BR = 200 - Σ_k |p_k - q_k|``: **200** for identical proportional profiles, **0**
    for no shared types. The result is a symmetric ``n × n`` matrix with 200 on the
    diagonal.

    Raises ``ValueError`` on an empty or ragged matrix or negative counts. This is a
    proportional-abundance similarity; on undeciphered material the "types" are signs
    or word forms, so read it as compositional similarity, not chronology (EXPLORATORY)."""
    pct = _row_percentages(_to_matrix(matrix))
    n = len(pct)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        pi = pct[i]
        sim[i][i] = 200.0 if sum(pi) > 0 else 0.0
        for j in range(i + 1, n):
            d = sum(abs(a - b) for a, b in zip(pi, pct[j], strict=True))
            s = 200.0 - d
            sim[i][j] = s
            sim[j][i] = s
    return sim


def _argsort(values: Sequence[float]) -> tuple[int, ...]:
    """Indices that sort ``values`` ascending, ties broken by original index (stable)."""
    return tuple(sorted(range(len(values)), key=lambda i: (values[i], i)))


# Above this row count the dense Jacobi eigensolver (O(n^3) per sweep) is too slow; a
# constant-deflated, positive-shifted power iteration is used instead. Real assemblage tables
# are far smaller than this, so the exact solver covers every ordinary seriation.
_DENSE_SOLVER_MAX_N = 160

# Two rows with no type in common score exactly 0 in exact arithmetic; rescaling the rows to
# percentages leaves a few ulps of the 0..200 scale behind, so a similarity at or below this
# is arithmetic residue, not a shared type. Genuine overlap is orders of magnitude larger:
# one shared occurrence in a million tokens still scores about 1e-4.
_EDGE_TOLERANCE = 1e-9

# The seriation axis is a unit vector, so rows whose components differ by no more than this
# sit at the same position on it. Real structure separates rows by far more; solver residue
# is around 1e-15.
_TIE_TOLERANCE = 1e-9

# Relative separation between the Fiedler eigenvalue and the next one. At or below this the
# eigenvalue is repeated, its eigenspace has more than one dimension, and no single vector is
# *the* seriation axis.
_DEGENERACY_TOLERANCE = 1e-9

# Squared distance below which two power-iteration runs from different starting vectors have
# converged on the same axis (up to sign). The iteration stops at a step-to-step change of
# 1e-14, so converged runs agree far more closely than this; a repeated eigenvalue leaves them
# order-1 apart.
_AXIS_AGREEMENT = 1e-8

# One row's identity for ordering purposes: either the counts as supplied or, where the
# similarity's own notion of sameness is what matters, the row rescaled to percentages.
Key = tuple[float, ...]


def _components(sim: list[list[float]]) -> list[tuple[int, ...]]:
    """The connected components of the similarity graph, each sorted ascending.

    Two rows are linked when their Brainerd-Robinson similarity clears
    :data:`_EDGE_TOLERANCE`, that is when they share at least one type. Rows in different
    components share nothing, so no similarity evidence relates them at all. Which rows form
    a component is a property of the counts, not of the order the rows were supplied in."""
    n = len(sim)
    seen = [False] * n
    out: list[tuple[int, ...]] = []
    for start in range(n):
        if seen[start]:
            continue
        seen[start] = True
        stack = [start]
        members: list[int] = []
        while stack:
            i = stack.pop()
            members.append(i)
            for j in range(n):
                if j != i and not seen[j] and sim[i][j] > _EDGE_TOLERANCE:
                    seen[j] = True
                    stack.append(j)
        out.append(tuple(sorted(members)))
    return out


def _jacobi_eigh(
    matrix: list[list[float]], *, max_sweeps: int = 100
) -> tuple[list[float], list[list[float]], int]:
    """Eigenvalues and eigenvectors of a small symmetric matrix (cyclic Jacobi rotation).

    Returns ``(eigenvalues, eigenvectors, sweeps)`` where ``eigenvectors[k]`` is the unit
    eigenvector for ``eigenvalues[k]``. Deterministic and basis-independent: the result does
    not depend on the order the rows and columns were supplied in, which is what makes the
    seriation ordering permutation-invariant."""
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    sweeps = 0
    for sweep in range(1, max_sweeps + 1):
        sweeps = sweep
        off = math.sqrt(sum(a[i][j] * a[i][j] for i in range(n) for j in range(i + 1, n)))
        if off <= 1e-13:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                if apq == 0.0:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * apq)
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                cos = 1.0 / math.sqrt(t * t + 1.0)
                sin = t * cos
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = cos * akp - sin * akq
                    a[k][q] = sin * akp + cos * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = cos * apk - sin * aqk
                    a[q][k] = sin * apk + cos * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = cos * vkp - sin * vkq
                    v[k][q] = sin * vkp + cos * vkq
    eigvals = [a[i][i] for i in range(n)]
    eigvecs = [[v[i][j] for i in range(n)] for j in range(n)]
    return eigvals, eigvecs, sweeps


def _fiedler_power(
    sim: list[list[float]], row_sum: list[float], max_iter: int, *, phase: float = 1.0
) -> tuple[list[float], int, bool]:
    """The Fiedler vector by constant-deflated, positive-shifted power iteration (large-n path).

    Powers ``M = cI - L`` (``L = D - S`` the Laplacian, ``c`` above ``L``'s spectral radius so
    ``M`` is positive definite and cannot sign-flip between steps); each step removes the
    constant component (the trivial eigenvector) and renormalizes, converging on the vector
    itself rather than on its ``argsort``. So the limit is the seriation axis regardless of the
    input row order, avoiding the order-dependence and sign-flip oscillation of the naive
    reciprocal-averaging iteration.

    ``phase`` shifts the starting vector. A simple eigenvalue draws every start to the same
    limit, so re-running with a different phase and comparing is how the large-matrix path
    detects a repeated eigenvalue, which has no single limit to converge on.

    The third return value reports whether the iteration settled inside ``max_iter`` steps. An
    unsettled run still depends on its starting vector, so its axis is not an answer the data
    determines on its own."""
    n = len(sim)
    shift = 2.0 * max(row_sum) + 1.0
    x = [math.sin(phase + i) for i in range(n)]
    mean = sum(x) / n
    x = [xi - mean for xi in x]
    norm = math.sqrt(sum(xi * xi for xi in x)) or 1.0
    x = [xi / norm for xi in x]
    used = 0
    converged = False
    for used in range(1, max_iter + 1):
        y = [
            (shift - row_sum[i]) * x[i] + sum(sim[i][j] * x[j] for j in range(n))
            for i in range(n)
        ]
        mean = sum(y) / n
        y = [yi - mean for yi in y]
        norm = math.sqrt(sum(yi * yi for yi in y))
        if norm < 1e-14:
            converged = True
            break
        y = [yi / norm for yi in y]
        # Converge on the vector direction (sign-agnostic), not on the argsort.
        conv = min(
            sum((a - b) ** 2 for a, b in zip(x, y, strict=True)),
            sum((a + b) ** 2 for a, b in zip(x, y, strict=True)),
        )
        x = y
        if conv < 1e-14:
            converged = True
            break
    return x, used, converged


def _block_axis(sub: list[list[float]], max_iter: int) -> tuple[list[float], int, bool]:
    """The seriation axis of one connected block, plus whether the axis is undetermined.

    The axis is the eigenvector of the second-smallest eigenvalue of the graph Laplacian
    ``L = D - S`` (spectral seriation): sorting rows by its components puts compositionally
    similar rows next to each other. A direct symmetric eigensolver handles ordinary (small)
    blocks, so the axis does not depend on the order the rows were given in; a constant-
    deflated power iteration is the fallback when the block is too large for it.

    The third return value is ``True`` when the similarity does not single out one axis, so no
    ordering of that block follows from it. The dense path reads that off the eigenvalue gap: a
    repeated Fiedler eigenvalue spans an eigenspace in which every vector is an equally good
    axis. The large-matrix path cannot see the spectrum, so it asks the equivalent question
    directly, does the answer depend on where the iteration started: an unsettled iteration
    fails that on its own (and is not solved twice, which keeps the slowest case from paying
    for the diagnostic), and a settled one is re-run from a different start and compared."""
    n = len(sub)
    row_sum = [sum(row) for row in sub]
    if n <= _DENSE_SOLVER_MAX_N:
        laplacian = [
            [(row_sum[i] if i == j else 0.0) - sub[i][j] for j in range(n)] for i in range(n)
        ]
        eigvals, eigvecs, used = _jacobi_eigh(laplacian)
        # L is a PSD graph Laplacian: on a connected block the smallest eigenvalue is 0 (the
        # constant vector) and the second-smallest is the Fiedler / seriation axis.
        by_value = sorted(range(n), key=lambda k: eigvals[k])
        second, third = eigvals[by_value[1]], eigvals[by_value[2]]
        scale = max(abs(third), abs(second), 1.0)
        return eigvecs[by_value[1]], used, (third - second) <= _DEGENERACY_TOLERANCE * scale
    axis, used, converged = _fiedler_power(sub, row_sum, max_iter, phase=1.0)
    if not converged:
        return axis, used, True
    check, used_check, _ = _fiedler_power(sub, row_sum, max_iter, phase=0.5)
    agreement = min(
        sum((a - b) ** 2 for a, b in zip(axis, check, strict=True)),
        sum((a + b) ** 2 for a, b in zip(axis, check, strict=True)),
    )
    return axis, max(used, used_check), agreement > _AXIS_AGREEMENT


def _axis_places(axis: list[float], profiles: Sequence[Key]) -> tuple[list[list[int]], int]:
    """Group a block's rows into the places they occupy along its axis.

    Rows whose axis components differ by no more than :data:`_TIE_TOLERANCE` share one place:
    the axis does not separate them, so the seriation has nothing to say about their relative
    order. Also returns how many rows share a place with a row of a *different proportional
    profile*, the rows whose order is therefore left to a convention. Rows of the same profile
    share a place too, but Brainerd-Robinson compares proportions, so it holds them to be the
    same assemblage and any arrangement of them is the same seriation: no ambiguity to report."""
    places: list[list[int]] = []
    for idx in _argsort(axis):
        if places and axis[idx] - axis[places[-1][-1]] <= _TIE_TOLERANCE:
            places[-1].append(idx)
        else:
            places.append([idx])
    unseparated = sum(
        len(p) for p in places if len(p) > 1 and len({profiles[i] for i in p}) > 1
    )
    return places, unseparated


def _canonical_direction(places: list[list[int]], keys: Sequence[Key]) -> list[list[int]]:
    """Face a block the way its composition sequence sorts first.

    A seriation has no direction, so the two readings are equally valid; fixing one from the
    compositions (never from the row indices, which a permutation changes) is what lets blocks
    be concatenated into an ordering that survives permuting the input. Each place is compared
    by the *set* of compositions standing at it, so the choice cannot depend on how rows
    sharing a place happen to be arranged."""
    forward = [tuple(sorted(keys[i] for i in place)) for place in places]
    if list(reversed(forward)) < forward:
        return list(reversed(places))
    return places


def _flatten_places(places: list[list[int]], keys: Sequence[Key]) -> tuple[int, ...]:
    """Read the places out in order, arranging rows that share one by their supplied counts.

    Rows sharing a place are arranged by the counts the caller supplied rather than by the
    proportions the similarity compares, because two rows can be identical to Brainerd-Robinson
    (a tablet with one sign and a tablet with three of that same sign are both 100% of one type)
    while the caller can plainly tell them apart. Ordering on what the caller supplied is what
    makes the returned sequence reproducible for them.

    Applied only once the direction is settled: arranging shared places before that would let
    the direction rule compare sequences that differ inside a place, which is precisely the
    detail the seriation does not determine."""
    order: list[int] = []
    for place in places:
        order.extend(sorted(place, key=lambda i: (keys[i], i)) if len(place) > 1 else place)
    return tuple(order)


@dataclass(frozen=True)
class _Solution:
    """One solved seriation: the blocks in final sequence, plus what stayed undetermined."""

    blocks: tuple[tuple[int, ...], ...]
    iterations: int
    undetermined: int
    unseparated: int

    @property
    def order(self) -> tuple[int, ...]:
        return tuple(i for block in self.blocks for i in block)


def _seriation_order(
    sim: list[list[float]], keys: Sequence[Key], profiles: Sequence[Key], max_iter: int
) -> _Solution:
    """Seriate each connected block of the similarity graph, then place the blocks.

    Rows in different blocks share no type, so the similarity says nothing about their relative
    order and the spectral axis of the whole matrix is not even well defined (its Laplacian has
    one zero eigenvalue per block). Each block is therefore seriated on its own and faced by
    :func:`_canonical_direction`; the blocks are then laid out largest at one end, ties broken by
    composition, so that the main sequence leads and the reading is reproducible. Finally the
    whole ordering is faced by the smaller row index, the documented canonical direction.

    Every step is decided by the counts rather than by row positions, so permuting the input
    returns the same ordering or its exact reverse. ``max_iter`` bounds the large-block
    iteration."""
    iterations = 0
    undetermined = 0
    unseparated = 0
    blocks: list[tuple[int, ...]] = []
    for members in _components(sim):
        if len(members) <= 2:
            # One row has nothing to order; two rows are adjacent either way round, so they
            # are two places with no axis needed to tell them apart.
            places = [[i] for i in members]
        else:
            sub = [[sim[i][j] for j in members] for i in members]
            axis, used, degenerate = _block_axis(sub, max_iter)
            iterations = max(iterations, used)
            if degenerate:
                undetermined += len(members)
            local, unpicked = _axis_places(axis, [profiles[i] for i in members])
            unseparated += unpicked
            places = [[members[p] for p in place] for place in local]
        blocks.append(_flatten_places(_canonical_direction(places, keys), keys))
    blocks.sort(key=lambda block: (-len(block), tuple(keys[i] for i in block)))
    if blocks and blocks[0][0] > blocks[-1][-1]:
        # Canonicalize direction; the exact reverse is an equally valid seriation.
        blocks = [tuple(reversed(block)) for block in reversed(blocks)]
    return _Solution(
        blocks=tuple(blocks),
        iterations=iterations,
        undetermined=undetermined,
        unseparated=unseparated,
    )


def _abundance_from_corpus(
    corpus: Any,
) -> tuple[list[list[float]], list[str], list[str]]:
    """A document × sign-type count matrix from a corpus.

    Rows are documents (kept only if they carry at least one sign token), columns are
    the sign labels that occur **in sorted label order**, cells are per-document counts.
    Sign labels come from each WORD/LOGOGRAM token's ``signs`` (the same convention as
    ``aegean stats``). Sorting the columns keeps the table itself independent of the order
    the documents arrived in; first-seen column order would make otherwise identical
    corpora produce differently shaped rows."""
    docs = _documents(corpus)
    type_index: dict[str, int] = {}
    rows: list[dict[int, float]] = []
    doc_labels: list[str] = []
    for d in docs:
        counts: dict[int, float] = {}
        for t in d.tokens:
            if t.kind not in (TokenKind.WORD, TokenKind.LOGOGRAM):
                continue
            signs = list(t.signs) or (
                t.text.split("-") if "-" in t.text else [t.text]
            )
            for s in signs:
                idx = type_index.setdefault(s, len(type_index))
                counts[idx] = counts.get(idx, 0.0) + 1.0
        if counts:
            rows.append(counts)
            doc_labels.append(d.id)
    if not rows:
        raise ValueError("corpus has no sign-bearing documents to seriate")
    type_labels = sorted(type_index)
    column = {type_index[label]: c for c, label in enumerate(type_labels)}
    dense = [[0.0] * len(type_labels) for _ in rows]
    for r, counts in enumerate(rows):
        for seen_at, value in counts.items():
            dense[r][column[seen_at]] = value
    return dense, doc_labels, type_labels


@dataclass(frozen=True)
class SeriationResult:
    """A seriation ordering plus the similarity it was built from (EXPLORATORY).

    ``order`` is the row indices of the input in seriated sequence (apply it to the
    original rows to read them in order). ``similarity`` is the Brainerd-Robinson matrix
    in the *original* row order. ``labels`` names the rows when the input was a corpus
    (document ids), else ``None``. ``iterations`` is how many solver passes ran for the
    hardest block (Jacobi sweeps for the dense eigensolver, power-iteration steps for the
    large-matrix fallback).

    ``components`` splits ``order`` into the connected blocks of the similarity graph, in
    the sequence they appear. More than one block means some rows share no type with the
    rest: **the order between blocks is a convention** (largest block at one end, then by
    composition) and carries no similarity evidence, so read a sequence only within a block.
    ``ambiguous`` is ``True`` when the similarity leaves part of the sequence undetermined
    even inside a block, which :func:`seriate` also warns about.

    The largest block is at one END, not necessarily at ``components[0]``: the global
    direction flip that makes the ordering reproducible reverses the block sequence
    with everything else, so reading ``components[0]`` as "the main sequence" is wrong
    about half the time. Read the largest block by size, not by position.

    The ordering is deterministic and independent of the input row order, but it has no
    inherent direction: ``order`` and its exact reverse are equally valid seriation
    solutions. It is a compositional-sequence hypothesis, not a date."""

    order: tuple[int, ...]
    similarity: tuple[tuple[float, ...], ...]
    iterations: int
    labels: tuple[str, ...] | None
    components: tuple[tuple[int, ...], ...]
    ambiguous: bool

    def ordered_labels(self) -> tuple[str, ...] | None:
        """The row labels in seriated order, or ``None`` if the input was a bare matrix."""
        if self.labels is None:
            return None
        return tuple(self.labels[i] for i in self.order)


def seriate(
    matrix_or_corpus: Any,
    *,
    labels: Sequence[str] | None = None,
    max_iter: int = 200,
) -> SeriationResult:
    """Seriate an abundance table (or a corpus) by Brainerd-Robinson similarity (EXPLORATORY).

    Builds the Brainerd-Robinson similarity matrix (see :func:`brainerd_robinson`) and
    orders the rows so that compositionally similar assemblages sit next to each other,
    using a deterministic spectral ordering (the Fiedler vector of the similarity's
    Laplacian). The ordering does not depend on the order the rows were supplied in, up to
    the inherent reversal.

    Assemblages that share no type at all are related by no similarity evidence, so the
    similarity graph is seriated one connected block at a time and the blocks are laid out
    largest at one end (ties broken by composition). ``result.components`` reports that split:
    when it holds more than one block, a sequence is meaningful only *within* a block. Where
    the similarity leaves rows undetermined even inside a block, the result is flagged
    ``ambiguous`` and a ``UserWarning`` says which rows and why.

    Parameters
    ----------
    matrix_or_corpus:
        Either a 2-D abundance table (rows = assemblages, columns = type counts) or a
        ``Corpus``, the ``QueryResults`` of a ``Corpus.query``, or a ``Document``
        iterable, in which case a document × sign-type count matrix is built
        automatically (rows are the sign-bearing documents, columns the signs that
        occur).
    labels:
        Optional row labels for a matrix input (must match the row count). Ignored for a
        corpus input, where document ids are used.
    max_iter:
        Cap on iterations for the large-matrix power-iteration fallback (the dense
        eigensolver used for ordinary tables ignores it). Must be positive.

    Returns a :class:`SeriationResult`. Raises ``ValueError`` on an empty/ragged matrix,
    a labels-length mismatch, or a corpus with no sign-bearing documents.

    **Caveat (EXPLORATORY).** The ordering is a hypothesis about relative sequence from
    compositional similarity, with no direction and no calendar anchor; on undeciphered
    scripts a "type" is a sign, so the axis may track scribal or graphotactic drift, not
    time. Corroborate against external evidence before reading chronology into it."""
    if max_iter <= 0:
        raise ValueError("max_iter must be positive")
    row_labels: tuple[str, ...] | None
    # A query's results stand in for their matched documents from here on, so seriating
    # a subset behaves exactly like seriating the same list of documents (including the
    # empty case, which is a table with no rows).
    matched = _matched_documents(matrix_or_corpus)
    if matched is not None:
        matrix_or_corpus = matched
    # Classifying the input peeks at its first element, which consumes a one-shot
    # iterator. ``seriate(d for d in corpus if ...)`` is the natural filtering idiom,
    # so materialize once and classify the list.
    if not isinstance(matrix_or_corpus, Document) and not hasattr(
        matrix_or_corpus, "documents"
    ):
        try:
            matrix_or_corpus = list(matrix_or_corpus)
        except TypeError:
            pass
    if _is_corpus_like(matrix_or_corpus):
        matrix, doc_labels, _types = _abundance_from_corpus(matrix_or_corpus)
        row_labels = tuple(doc_labels)
    else:
        matrix = _to_matrix(matrix_or_corpus)
        if labels is not None:
            if len(labels) != len(matrix):
                raise ValueError(
                    f"labels has {len(labels)} entries but the matrix has {len(matrix)} rows"
                )
            row_labels = tuple(labels)
        else:
            row_labels = None
    sim = brainerd_robinson(matrix)
    # Two identities per row: what the caller supplied, which orders anything they can tell
    # apart, and the proportional profile, which is all the similarity itself compares.
    keys: list[Key] = [tuple(row) for row in matrix]
    profiles: list[Key] = [tuple(row) for row in _row_percentages(matrix)]
    solved = _seriation_order(sim, keys, profiles, max_iter)
    total = len(keys)
    if solved.undetermined:
        warnings.warn(
            f"seriation axis undetermined for {solved.undetermined} of {total} rows: the"
            " similarity does not single out one axis for their block, so the sequence returned"
            " is one of several equally good solutions and may change with the input row order",
            stacklevel=2,
        )
    if solved.unseparated:
        warnings.warn(
            f"{solved.unseparated} of {total} rows of differing composition sit at the same"
            " position on the seriation axis: their relative order follows a fixed convention,"
            " not the similarity",
            stacklevel=2,
        )
    return SeriationResult(
        order=solved.order,
        similarity=tuple(tuple(row) for row in sim),
        iterations=solved.iterations,
        labels=row_labels,
        components=solved.blocks,
        ambiguous=bool(solved.undetermined or solved.unseparated),
    )
