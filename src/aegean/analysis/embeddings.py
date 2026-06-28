"""Distributional sign embeddings: a vector per sign from co-occurrence (EXPLORATORY).

Learns one dense vector per sign of a script from how signs *neighbour* each other
inside words: a count matrix over (left-neighbour, right-neighbour) contexts plus two
slot columns (word-initial, word-final), reweighted by positive pointwise mutual
information (PPMI), then reduced to ``dim`` dimensions by a truncated SVD. Signs that
appear in similar contexts land near each other.

The pipeline is the classic count-based word-embedding recipe (Levy, Goldberg &
Dagan 2015) applied to *signs within words* rather than words within sentences, since
Aegean documents are short and the meaningful unit of adjacency is the word.

**Exploratory.** A vector is a *representation of distribution*, not a phonetic or
semantic value: two signs that score as neighbours share graphotactic context, which
may reflect a shared sound, a shared morphological slot, or nothing but the small
sample. On undeciphered scripts (Linear A, Cypro-Minoan) these vectors surface
structure to inspect, never a reading; and Aegean corpora are tiny by embedding
standards (a few thousand sign tokens), so the geometry is noisy and the low end of a
neighbour list is barely better than chance. Read it as a lead generator. The SVD is
deterministic (a fixed-start power iteration with deflation, the same routine as the
correspondence-analysis biplot), so a result is reproducible.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..core.model import Document, TokenKind

__all__ = [
    "SignEmbeddings",
    "sign_embeddings",
]

_INIT = "▸INIT"   # word-initial slot context (▸INIT — cannot collide with a sign label)
_FINAL = "▸FINAL"  # word-final slot context (▸FINAL)


def _documents(corpus: Any) -> list[Document]:
    """Coerce a single Document / Corpus / QueryResults / iterable to a list."""
    if isinstance(corpus, Document):
        return [corpus]
    docs = getattr(corpus, "documents", corpus)
    out = list(docs)
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _signs_of(token: Any) -> list[str]:
    """The sign labels of one token — same convention as ``aegean stats``."""
    return list(token.signs) or (token.text.split("-") if "-" in token.text else [token.text])


def _words_as_signs(docs: Sequence[Document]) -> list[list[str]]:
    """Every WORD token as its list of sign labels (multi-sign words only)."""
    out: list[list[str]] = []
    for d in docs:
        for t in d.tokens:
            if t.kind is not TokenKind.WORD:
                continue
            parts = _signs_of(t)
            if len(parts) >= 2:
                out.append(parts)
    return out


@dataclass(frozen=True)
class SignEmbeddings:
    """Dense distributional vectors for the signs of a script (EXPLORATORY).

    ``vocab`` is the row order of ``vectors`` (one ``dim``-vector per sign, already
    SVD-reduced and L2-normalized). ``window`` records the neighbour radius used.
    The vectors capture *distributional* similarity only; see the module docstring
    on why, on undeciphered or tiny corpora, neighbour lists are leads, not truth.
    """

    vocab: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]
    dim: int
    window: int

    def __post_init__(self) -> None:
        if len(self.vocab) != len(self.vectors):
            raise ValueError("vocab and vectors must align")

    def _index(self, sign: str) -> int:
        try:
            return self.vocab.index(sign)
        except ValueError:
            raise KeyError(sign) from None

    def vector(self, sign: str) -> tuple[float, ...]:
        """The (L2-normalized) embedding of ``sign``. Raises ``KeyError`` if unseen."""
        return self.vectors[self._index(sign)]

    def neighbours(self, sign: str, k: int = 5) -> list[tuple[str, float]]:
        """The ``k`` nearest signs to ``sign`` by cosine similarity, closest first.

        ``sign`` itself is excluded. Vectors are unit-normalized, so cosine is a dot
        product; a returned score near 1 means near-identical context profiles, near
        0 means unrelated. On a tiny corpus treat only the very top of the list as
        meaningful (EXPLORATORY: distributional, not phonetic, similarity)."""
        if k <= 0:
            return []
        i = self._index(sign)
        vi = self.vectors[i]
        scored = [
            (self.vocab[j], sum(a * b for a, b in zip(vi, vj, strict=True)))
            for j, vj in enumerate(self.vectors)
            if j != i
        ]
        scored.sort(key=lambda kv: (-kv[1], kv[0]))
        return scored[:k]


def _cooccurrence(
    words: Sequence[Sequence[str]], window: int
) -> tuple[list[str], list[str], dict[tuple[int, int], float]]:
    """Sparse (sign, context) co-occurrence counts.

    Contexts are the left/right neighbour signs within ``window`` positions inside a
    word (each tagged by direction so a left vs right neighbour is a distinct
    context), plus two slot columns for the word-initial and word-final position.
    Returns the sign vocabulary, the context vocabulary, and a sparse
    ``{(sign_row, ctx_col): count}`` map."""
    sign_ids: dict[str, int] = {}
    ctx_ids: dict[str, int] = {}
    cells: dict[tuple[int, int], float] = {}

    def sign_id(s: str) -> int:
        return sign_ids.setdefault(s, len(sign_ids))

    def ctx_id(c: str) -> int:
        return ctx_ids.setdefault(c, len(ctx_ids))

    def add(row: int, col: int) -> None:
        cells[(row, col)] = cells.get((row, col), 0.0) + 1.0

    for w in words:
        n = len(w)
        for i, s in enumerate(w):
            row = sign_id(s)
            if i == 0:
                add(row, ctx_id(_INIT))
            if i == n - 1:
                add(row, ctx_id(_FINAL))
            for d in range(1, window + 1):
                if i - d >= 0:
                    add(row, ctx_id(f"L{d}:{w[i - d]}"))
                if i + d < n:
                    add(row, ctx_id(f"R{d}:{w[i + d]}"))

    signs = sorted(sign_ids, key=lambda s: sign_ids[s])
    contexts = sorted(ctx_ids, key=lambda c: ctx_ids[c])
    return signs, contexts, cells


def _ppmi(
    n_rows: int, n_cols: int, cells: dict[tuple[int, int], float]
) -> list[list[float]]:
    """Dense PPMI matrix from sparse co-occurrence counts.

    ``PPMI(s, c) = max(0, log₂( p(s, c) / (p(s)·p(c)) ))`` with maximum-likelihood
    marginals over the whole count table. Negative (under-represented) associations
    are clipped to 0, the standard PPMI choice."""
    total = sum(cells.values())
    matrix = [[0.0] * n_cols for _ in range(n_rows)]
    if total <= 0:
        return matrix
    row_sum = [0.0] * n_rows
    col_sum = [0.0] * n_cols
    for (r, c), v in cells.items():
        row_sum[r] += v
        col_sum[c] += v
    for (r, c), v in cells.items():
        denom = row_sum[r] * col_sum[c]
        if denom <= 0:
            continue
        pmi = math.log2((v * total) / denom)
        if pmi > 0:
            matrix[r][c] = pmi
    return matrix


def _gram(matrix: list[list[float]], n_cols: int) -> list[list[float]]:
    """The column Gram matrix ``MᵀM`` (n_cols × n_cols, symmetric PSD)."""
    g = [[0.0] * n_cols for _ in range(n_cols)]
    for row in matrix:
        for a in range(n_cols):
            ra = row[a]
            if ra == 0.0:
                continue
            ga = g[a]
            for b in range(a, n_cols):
                ga[b] += ra * row[b]
    for a in range(n_cols):
        for b in range(a + 1, n_cols):
            g[b][a] = g[a][b]
    return g


def _leading_eigenpair(
    gram: list[list[float]], skip: list[list[float]]
) -> tuple[float, list[float]] | None:
    """Leading eigenpair of a symmetric PSD matrix by power iteration, deflated
    against the vectors in ``skip``. Mirrors ``multivariate._power_iterate``: a
    fixed, slightly asymmetric start vector keeps the result deterministic."""
    m = len(gram)
    if m == 0:
        return None
    v = [1 + (i + 1) / m for i in range(m)]

    def orthogonalize(vec: list[float]) -> None:
        for u in skip:
            dot = sum(vec[i] * u[i] for i in range(m))
            for i in range(m):
                vec[i] -= dot * u[i]

    value = 0.0
    for _ in range(300):
        orthogonalize(v)
        nxt = [sum(gram[i][j] * v[j] for j in range(m)) for i in range(m)]
        norm = math.sqrt(sum(x * x for x in nxt))
        if norm < 1e-12:
            return None
        v = [x / norm for x in nxt]
        value = norm
    return value, v


def _truncated_svd(
    matrix: list[list[float]], n_cols: int, dim: int
) -> list[list[float]]:
    """Row coordinates of a rank-``dim`` truncated SVD of ``matrix``.

    Diagonalizes the column Gram matrix ``MᵀM`` by deflated power iteration to get
    the top right singular vectors ``V`` and singular values ``σ``, then returns the
    row embeddings ``U·Σ = M·V`` (each row a sign). Components whose singular value
    collapses to ~0 are dropped, so the output may have fewer than ``dim`` columns."""
    gram = _gram(matrix, n_cols)
    eigvecs: list[list[float]] = []
    sigmas: list[float] = []
    for _ in range(min(dim, n_cols)):
        pair = _leading_eigenpair(gram, eigvecs)
        if pair is None:
            break
        eigval, vec = pair
        sigma = math.sqrt(max(0.0, eigval))
        if sigma < 1e-9:
            break
        eigvecs.append(vec)
        sigmas.append(sigma)
    # Row coordinates U·Σ = M·V (V's columns are the eigenvectors).
    out: list[list[float]] = []
    for row in matrix:
        coords = [sum(row[j] * vec[j] for j in range(n_cols)) for vec in eigvecs]
        out.append(coords)
    return out


def _l2_normalize(vec: list[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-12:
        return tuple(vec)
    return tuple(x / norm for x in vec)


def sign_embeddings(
    corpus: Any, *, dim: int = 50, window: int = 1
) -> SignEmbeddings:
    """Learn a distributional vector per sign from a script corpus (EXPLORATORY).

    Builds a (sign × context) co-occurrence table from sign adjacency *within words*
    (left/right neighbours up to ``window`` positions, plus word-initial and
    word-final slot columns), reweights it with PPMI, and reduces each row to at most
    ``dim`` dimensions with a deterministic truncated SVD; the returned vectors are
    L2-normalized so :meth:`SignEmbeddings.neighbours` reads as cosine similarity.

    Parameters
    ----------
    corpus:
        A ``Corpus``, ``QueryResults``, or iterable of ``Document``. Only multi-sign
        WORD tokens contribute (single-sign words have no internal adjacency).
    dim:
        The maximum embedding dimensionality. The effective dimension is capped at
        the context-vocabulary size and at the number of non-degenerate singular
        values, so small corpora yield shorter vectors.
    window:
        Neighbour radius in signs (``1`` = immediate neighbours only).

    Returns a :class:`SignEmbeddings`. Raises ``ValueError`` if the corpus has no
    multi-sign words or ``dim``/``window`` is not positive.

    **Caveat (EXPLORATORY).** The vectors encode distributional context, not phonetic
    or semantic value; on undeciphered scripts they are a structure-surfacing aid, not
    a decipherment, and on the small Aegean corpora the geometry is noisy. Trust only
    the strongest neighbours and corroborate before reading anything into them.
    """
    if dim <= 0:
        raise ValueError("dim must be positive")
    if window <= 0:
        raise ValueError("window must be positive")
    words = _words_as_signs(_documents(corpus))
    if not words:
        raise ValueError("corpus has no multi-sign words to learn from")
    signs, contexts, cells = _cooccurrence(words, window)
    matrix = _ppmi(len(signs), len(contexts), cells)
    target = min(dim, len(contexts))
    reduced = _truncated_svd(matrix, len(contexts), target)
    vectors = tuple(_l2_normalize(row) for row in reduced)
    eff_dim = len(vectors[0]) if vectors else 0
    return SignEmbeddings(
        vocab=tuple(signs),
        vectors=vectors,
        dim=eff_dim,
        window=window,
    )
