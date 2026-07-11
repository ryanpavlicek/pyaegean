"""Seriation and rough chronology for assemblage data (EXPLORATORY).

Two classic archaeological tools, ported to the corpus model:

- :func:`chronology` reads each document's free-text ``meta.period`` into a numeric
  ``(start, end)`` year span, **reusing** :func:`aegean.viz.parse_period` (the same
  best-effort origDate reader the timeline plot uses), and reports the fraction it
  could not parse. What is unparseable is counted and surfaced, never guessed.
- :func:`seriate` builds the Brainerd-Robinson similarity matrix over an abundance
  table (rows = assemblages / documents, columns = types) and orders the rows by a
  deterministic spectral ordering (the Fiedler vector of the similarity's Laplacian),
  the seriation ordering that puts similar assemblages next to each other. The result
  is independent of the order the rows were supplied in (up to the inherent reversal).

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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..core.model import Document, TokenKind
from ..viz import parse_period

__all__ = [
    "DocumentSpan",
    "Chronology",
    "chronology",
    "brainerd_robinson",
    "SeriationResult",
    "seriate",
]


def _documents(corpus: Any) -> list[Document]:
    """Coerce a single Document / Corpus / QueryResults / iterable to a list of Documents."""
    if isinstance(corpus, Document):
        return [corpus]
    docs = getattr(corpus, "documents", corpus)
    out = list(docs)
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _is_corpus_like(obj: Any) -> bool:
    """True if ``obj`` is a Document, a Corpus (has ``.documents``), or an iterable whose
    first element is a Document. A bare 2-D number matrix is not corpus-like."""
    if isinstance(obj, Document):
        return True
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
    sim: list[list[float]], row_sum: list[float], max_iter: int
) -> tuple[list[float], int]:
    """The Fiedler vector by constant-deflated, positive-shifted power iteration (large-n path).

    Powers ``M = cI - L`` (``L = D - S`` the Laplacian, ``c`` above ``L``'s spectral radius so
    ``M`` is positive definite and cannot sign-flip between steps); each step removes the
    constant component (the trivial eigenvector) and renormalizes, converging on the vector
    itself rather than on its ``argsort``. So the limit is the seriation axis regardless of the
    input row order, avoiding the order-dependence and sign-flip oscillation of the naive
    reciprocal-averaging iteration."""
    n = len(sim)
    shift = 2.0 * max(row_sum) + 1.0
    x = [math.sin(1.0 + i) for i in range(n)]
    mean = sum(x) / n
    x = [xi - mean for xi in x]
    norm = math.sqrt(sum(xi * xi for xi in x)) or 1.0
    x = [xi / norm for xi in x]
    used = 0
    for used in range(1, max_iter + 1):
        y = [
            (shift - row_sum[i]) * x[i] + sum(sim[i][j] * x[j] for j in range(n))
            for i in range(n)
        ]
        mean = sum(y) / n
        y = [yi - mean for yi in y]
        norm = math.sqrt(sum(yi * yi for yi in y))
        if norm < 1e-14:
            break
        y = [yi / norm for yi in y]
        # Converge on the vector direction (sign-agnostic), not on the argsort.
        conv = min(
            sum((a - b) ** 2 for a, b in zip(x, y, strict=True)),
            sum((a + b) ** 2 for a, b in zip(x, y, strict=True)),
        )
        x = y
        if conv < 1e-14:
            break
    return x, used


def _seriation_order(sim: list[list[float]], max_iter: int) -> tuple[tuple[int, ...], int]:
    """Order rows by the Fiedler vector of the Brainerd-Robinson similarity's Laplacian.

    The seriation axis is the eigenvector of the second-smallest eigenvalue of the graph
    Laplacian ``L = D - S`` (spectral seriation): sorting the rows by that vector's components
    puts compositionally similar rows next to each other. The eigenvector is found by a direct
    symmetric eigensolver for ordinary (small) matrices, so the ordering is deterministic and
    does not depend on the order the rows were given in; a constant-deflated power iteration is
    the fallback when the matrix is too large for the dense solver. The direction is
    canonicalized (the smaller row index at the low end) so repeated calls agree; the reverse
    ordering is an equally valid seriation. ``max_iter`` bounds the fallback iteration."""
    n = len(sim)
    if n <= 2:
        return tuple(range(n)), 0
    row_sum = [sum(sim[i]) for i in range(n)]
    if n <= _DENSE_SOLVER_MAX_N:
        laplacian = [
            [(row_sum[i] if i == j else 0.0) - sim[i][j] for j in range(n)] for i in range(n)
        ]
        eigvals, eigvecs, used = _jacobi_eigh(laplacian)
        # L is a PSD graph Laplacian: the smallest eigenvalue is 0 (constant vector); the
        # second-smallest is the Fiedler / seriation axis.
        by_value = sorted(range(n), key=lambda k: eigvals[k])
        axis = eigvecs[by_value[1]]
    else:
        axis, used = _fiedler_power(sim, row_sum, max_iter)
    order = _argsort(axis)
    if order[0] > order[-1]:  # canonicalize direction; the exact reverse is equally valid
        order = tuple(reversed(order))
    return order, used


def _abundance_from_corpus(
    corpus: Any,
) -> tuple[list[list[float]], list[str], list[str]]:
    """A document × sign-type count matrix from a corpus.

    Rows are documents (kept only if they carry at least one sign token), columns are
    the sign labels that occur, cells are per-document counts. Sign labels come from
    each WORD/LOGOGRAM token's ``signs`` (the same convention as ``aegean stats``)."""
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
    width = len(type_index)
    dense = [[row.get(c, 0.0) for c in range(width)] for row in rows]
    type_labels = sorted(type_index, key=lambda s: type_index[s])
    return dense, doc_labels, type_labels


@dataclass(frozen=True)
class SeriationResult:
    """A seriation ordering plus the similarity it was built from (EXPLORATORY).

    ``order`` is the row indices of the input in seriated sequence (apply it to the
    original rows to read them in order). ``similarity`` is the Brainerd-Robinson matrix
    in the *original* row order. ``labels`` names the rows when the input was a corpus
    (document ids), else ``None``. ``iterations`` is how many solver passes ran (Jacobi
    sweeps for the dense eigensolver, power-iteration steps for the large-matrix fallback).

    The ordering is deterministic and independent of the input row order, but it has no
    inherent direction: ``order`` and its exact reverse are equally valid seriation
    solutions. It is a compositional-sequence hypothesis, not a date."""

    order: tuple[int, ...]
    similarity: tuple[tuple[float, ...], ...]
    iterations: int
    labels: tuple[str, ...] | None

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
    Laplacian). The ordering does not depend on the order the rows were supplied in.

    Parameters
    ----------
    matrix_or_corpus:
        Either a 2-D abundance table (rows = assemblages, columns = type counts) or a
        ``Corpus`` / ``Document`` iterable, in which case a document × sign-type count
        matrix is built automatically (rows are the sign-bearing documents, columns the
        signs that occur).
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
    order, iterations = _seriation_order(sim, max_iter)
    return SeriationResult(
        order=order,
        similarity=tuple(tuple(row) for row in sim),
        iterations=iterations,
        labels=row_labels,
    )
