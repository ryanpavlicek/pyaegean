"""Seriation and rough chronology for assemblage data (EXPLORATORY).

Two classic archaeological tools, ported to the corpus model:

- :func:`chronology` reads each document's free-text ``meta.period`` into a numeric
  ``(start, end)`` year span, **reusing** :func:`aegean.viz.parse_period` (the same
  best-effort origDate reader the timeline plot uses), and reports the fraction it
  could not parse. What is unparseable is counted and surfaced, never guessed.
- :func:`seriate` builds the Brainerd-Robinson similarity matrix over an abundance
  table (rows = assemblages / documents, columns = types) and orders the rows by a
  deterministic, spectral-free iterative mean-position refinement, the seriation
  ordering that puts similar assemblages next to each other.

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


def _seriation_order(sim: list[list[float]], max_iter: int) -> tuple[tuple[int, ...], int]:
    """Order rows by centred power iteration on the similarity matrix.

    This is reciprocal averaging without a full eigensolver: iterate
    ``score_i <- Σ_j S_ij score_j / Σ_j S_ij`` (a similarity-weighted mean of the other
    rows' positions), re-centre to remove the trivial constant component, and re-scale.
    Power iteration on the row-normalized similarity, deflated against the constant
    eigenvector by the re-centring, converges to the seriation axis (the second
    eigenvector); ``argsort`` of it is the ordering. Deterministic: the start vector is
    fixed and slightly asymmetric, mirroring the embeddings SVD routine."""
    n = len(sim)
    if n <= 2:
        return tuple(range(n)), 0
    row_sum = [sum(sim[i]) for i in range(n)]
    # Fixed, slightly asymmetric, mean-centred start (deterministic).
    scores = [1.0 + (i + 1) / n for i in range(n)]
    mean = sum(scores) / n
    scores = [s - mean for s in scores]
    prev_order: tuple[int, ...] | None = None
    used = 0
    for used in range(1, max_iter + 1):
        nxt: list[float] = []
        for i in range(n):
            rs = row_sum[i]
            if rs <= 0:
                nxt.append(0.0)
            else:
                nxt.append(sum(sim[i][j] * scores[j] for j in range(n)) / rs)
        mean = sum(nxt) / n
        nxt = [x - mean for x in nxt]
        norm = math.sqrt(sum(x * x for x in nxt))
        if norm < 1e-12:
            break
        nxt = [x / norm for x in nxt]
        order = _argsort(nxt)
        if order == prev_order:
            break
        prev_order = order
        scores = nxt
    return _argsort(scores), used


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
    (document ids), else ``None``. ``iterations`` is how many refinement passes ran.

    The ordering has no inherent direction: ``order`` and its reverse are equally valid
    seriation solutions. It is a compositional-sequence hypothesis, not a date."""

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
    using a deterministic, spectral-free iterative mean-position refinement.

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
        Cap on refinement passes (the routine stops early once the ordering is stable).

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
