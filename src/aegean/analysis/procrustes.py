"""Cross-script alignment, and the measured null that calibrates it (EXPLORATORY).

**What this measured, first.** Run on the current bundled data (2026-07-11), the
leave-one-out test this module ships found **no recoverable Linear A to Linear B sign
correspondence at this corpus scale**. Aligning the Linear A sign embeddings to the
Linear B syllabogram embeddings and asking, for each of the 53 signs the two scripts
share by transliteration value, where its true Linear B counterpart lands among the 73
candidates: **top-1 recovery 0.000, top-5 recovery 0.094** (chance is 5/73 = 0.068),
**median rank 26 of 73** (chance median 37). The very same machinery, aligned to a space
to *itself*, recovers **90.1%** of signs at rank 1 (the 16 misses are distributionally
identical signs, chiefly hapax ``*NNN`` signs that share one context and resolve to a
tied twin), so the cross-script failure is not a broken alignment: there is simply no
signal to recover. In-sample ranks with no hold-out look near-perfect, but that is pure
overfitting; the leave-one-out numbers above are the honest result. Evidence and full
protocol: ``training/results/procrustes-null-2026-07-11.json``.

**So the module's primary value is the calibration methodology, not the hypotheses.** It
ships the two checks that MEASURE whether an alignment carries signal, and reports
whatever they show:

- :func:`recover_identity` aligns a script's embedding to *itself* from a subset of
  anchors and asks how often a held-out sign's top-ranked correspondence is itself.
  Self-alignment should recover almost every sign; a high (near, not exactly, 1.0) floor
  is what tells a genuine null (no signal) apart from broken code.
- :func:`rank_known_pairs` runs Linear A against Linear B on the signs the two scripts
  share by transliteration value (the AB "chart-shared" signs, a partial ground truth)
  and reports, by leave-one-out, where each known pair's true target lands in the ranked
  list. Whatever that rank distribution shows, weak or strong, *is* the result. On the
  bundled corpora it is the null above.

The ranked-hypothesis API (:func:`align_scripts`, :meth:`ProcrustesAlignment.hypotheses`)
exists for anyone re-running the calibration with different embeddings, a larger corpus,
or a different seed dictionary. It is **not** a decipherment aid: a high alignment score
means two signs occupy similar *distributional* positions in their respective tiny
corpora, which can reflect a shared value, a shared graphotactic slot, or the noise of a
few hundred sign tokens. Nothing here reads a sign. Every returned object is labelled
exploratory and every score is a geometry statistic, not a probability of correspondence.
Read the calibration before, and instead of, the leads.

The linear algebra is pure-Python power iteration (the same deterministic routine as the
embeddings SVD), so results are reproducible and the core stays dependency-free.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .embeddings import SignEmbeddings, sign_embeddings
from .stats import mulberry32

__all__ = [
    "Correspondence",
    "ProcrustesAlignment",
    "align_embeddings",
    "align_scripts",
    "shared_label_anchors",
    "IdentityCheck",
    "recover_identity",
    "RankReport",
    "rank_known_pairs",
]

_SUBSCRIPT_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def _fold(label: str) -> str:
    """Fold subscript sign-numbers to ASCII digits (RA₂ -> RA2), then upper-case."""
    return label.translate(_SUBSCRIPT_DIGITS).upper()


# --------------------------------------------------------------------------- #
# Small dense-matrix helpers (pure Python, deterministic)
# --------------------------------------------------------------------------- #

Matrix = list[list[float]]
Vec = list[float]


def _unit(vec: Sequence[float]) -> Vec:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-12:
        return list(vec)
    return [x / norm for x in vec]


def _prep(emb: SignEmbeddings, dim: int) -> tuple[tuple[str, ...], list[Vec]]:
    """Truncate every embedding to ``dim`` leading dimensions and re-unit-normalize.

    Embedding columns are ordered by singular value, so the leading ``dim`` are the most
    informative; truncation lets two spaces of different effective dimensionality be
    aligned in a shared ``dim``. Re-normalizing keeps cosine scoring well-defined."""
    vecs = [_unit(v[:dim]) for v in emb.vectors]
    return emb.vocab, vecs


def _covariance(x_rows: Sequence[Vec], y_rows: Sequence[Vec], dim: int) -> Matrix:
    """The cross-covariance ``C = Xᵀ Y`` (dim × dim) over paired anchor rows."""
    c: Matrix = [[0.0] * dim for _ in range(dim)]
    for x, y in zip(x_rows, y_rows, strict=True):
        for a in range(dim):
            xa = x[a]
            if xa == 0.0:
                continue
            row = c[a]
            for b in range(dim):
                row[b] += xa * y[b]
    return c


def _gram(mat: Matrix, dim: int) -> Matrix:
    """The symmetric matrix ``MᵀM`` (dim × dim)."""
    g: Matrix = [[0.0] * dim for _ in range(dim)]
    for row in mat:
        for a in range(dim):
            ra = row[a]
            if ra == 0.0:
                continue
            ga = g[a]
            for b in range(a, dim):
                ga[b] += ra * row[b]
    for a in range(dim):
        for b in range(a + 1, dim):
            g[b][a] = g[a][b]
    return g


def _leading_eigenpair(gram: Matrix, skip: list[Vec]) -> tuple[float, Vec] | None:
    """Leading eigenpair of a symmetric PSD matrix by power iteration, deflated against
    ``skip``. A fixed, slightly asymmetric start keeps the result deterministic (the same
    routine as :mod:`aegean.analysis.embeddings`)."""
    m = len(gram)
    if m == 0:
        return None
    v = [1.0 + (i + 1) / m for i in range(m)]

    def orthogonalize(vec: Vec) -> None:
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


def _procrustes_rotation(cov: Matrix, dim: int) -> Matrix:
    """Orthogonal ``R = U Vᵀ`` from the SVD ``C = U Σ Vᵀ`` of the cross-covariance.

    Diagonalizes ``G = CᵀC`` by deflated power iteration to get the right singular vectors
    ``V`` and singular values ``σ``; recovers the left singular vectors ``u_i = C v_i /
    σ_i``; and returns ``R = Σ_i u_i v_iᵀ``. For a full-rank ``C`` this is the exact
    orthogonal Procrustes solution minimizing ``‖X R − Y‖``; a degenerate direction
    (σ ≈ 0) is skipped (exploratory: the anchors did not constrain that axis)."""
    gram = _gram([[cov[i][j] for j in range(dim)] for i in range(dim)], dim)
    eigvecs: list[Vec] = []
    sigmas: list[float] = []
    for _ in range(dim):
        pair = _leading_eigenpair(gram, eigvecs)
        if pair is None:
            break
        eigval, vvec = pair
        sigma = math.sqrt(max(0.0, eigval))
        if sigma < 1e-9:
            break
        eigvecs.append(vvec)
        sigmas.append(sigma)
    r: Matrix = [[0.0] * dim for _ in range(dim)]
    for vvec, sigma in zip(eigvecs, sigmas, strict=True):
        # u = C v / sigma  (left singular vector)
        u = [sum(cov[i][j] * vvec[j] for j in range(dim)) / sigma for i in range(dim)]
        # R += outer(u, v)
        for i in range(dim):
            ui = u[i]
            if ui == 0.0:
                continue
            ri = r[i]
            for j in range(dim):
                ri[j] += ui * vvec[j]
    return r


def _apply(vec: Vec, rot: Matrix, dim: int) -> Vec:
    """Row-vector times rotation: ``vec @ R``."""
    return [sum(vec[k] * rot[k][j] for k in range(dim)) for j in range(dim)]


# --------------------------------------------------------------------------- #
# Public alignment API
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Correspondence:
    """One ranked cross-script sign-correspondence hypothesis (EXPLORATORY).

    ``source_sign`` (in the source script) is aligned nearest to ``target_sign`` (in the
    target script) with cosine ``score`` in the rotated space, at 1-based ``rank`` among
    all target signs for this source sign. A high score means similar distributional
    position, **not** a reading or a decipherment; corroborate before use."""

    source_sign: str
    target_sign: str
    score: float
    rank: int


@dataclass(frozen=True)
class ProcrustesAlignment:
    """A learned source→target embedding alignment and its hypothesis generator (EXPLORATORY).

    ``rotation`` is the orthogonal ``dim × dim`` matrix mapping the (truncated,
    re-normalized) source space onto the target space; ``anchor_fit`` is the mean cosine
    of the anchor pairs after rotation (1 = perfect fit on the seeds). Use
    :meth:`correspondences` for one source sign or :meth:`hypotheses` for a ranked global
    list. These are geometry statistics offered as leads for a specialist, never readings."""

    source_script: str
    target_script: str
    dim: int
    n_anchors: int
    anchor_fit: float
    rotation: tuple[tuple[float, ...], ...]
    source_vocab: tuple[str, ...]
    source_vectors: tuple[tuple[float, ...], ...]
    target_vocab: tuple[str, ...]
    target_vectors: tuple[tuple[float, ...], ...]

    def _aligned(self, source_sign: str) -> Vec:
        try:
            i = self.source_vocab.index(source_sign)
        except ValueError:
            raise KeyError(source_sign) from None
        rot = [list(r) for r in self.rotation]
        return _apply(list(self.source_vectors[i]), rot, self.dim)

    def correspondences(self, source_sign: str, k: int = 5) -> list[Correspondence]:
        """The ``k`` best target-sign hypotheses for one source sign, strongest first.

        Ranks every target sign by cosine similarity to the rotated source vector.
        Raises ``KeyError`` if ``source_sign`` is not in the source vocabulary
        (EXPLORATORY: distributional geometry, not a reading)."""
        if k <= 0:
            return []
        a = self._aligned(source_sign)
        scored = [
            (t, sum(x * y for x, y in zip(a, tv, strict=True)))
            for t, tv in zip(self.target_vocab, self.target_vectors, strict=True)
        ]
        scored.sort(key=lambda kv: (-kv[1], kv[0]))
        return [
            Correspondence(source_sign, t, s, rank)
            for rank, (t, s) in enumerate(scored[:k], start=1)
        ]

    def hypotheses(self, *, k: int = 1, top: int | None = None) -> list[Correspondence]:
        """A ranked global list of correspondence hypotheses across all source signs.

        Takes each source sign's top ``k`` target matches and returns them sorted by score
        (strongest first). ``top`` truncates the returned list. Every entry is exploratory
        and the score is an alignment statistic, not a probability of correspondence."""
        out: list[Correspondence] = []
        for s in self.source_vocab:
            out.extend(self.correspondences(s, k=k))
        out.sort(key=lambda c: (-c.score, c.source_sign, c.target_sign))
        return out[:top] if top is not None else out


def _rotation_from_anchors(
    src_vocab: tuple[str, ...],
    src_vecs: list[Vec],
    tgt_vocab: tuple[str, ...],
    tgt_vecs: list[Vec],
    anchors: Sequence[tuple[str, str]],
    dim: int,
) -> tuple[Matrix, float]:
    """Learn the Procrustes rotation from anchor pairs; return ``(R, anchor_fit)``."""
    src_index = {s: i for i, s in enumerate(src_vocab)}
    tgt_index = {s: i for i, s in enumerate(tgt_vocab)}
    x_rows: list[Vec] = []
    y_rows: list[Vec] = []
    for s, t in anchors:
        if s in src_index and t in tgt_index:
            x_rows.append(src_vecs[src_index[s]])
            y_rows.append(tgt_vecs[tgt_index[t]])
    if not x_rows:
        raise ValueError("no anchor pair has both signs present in the two vocabularies")
    cov = _covariance(x_rows, y_rows, dim)
    rot = _procrustes_rotation(cov, dim)
    # Anchor fit: mean cosine of aligned source anchors vs their targets.
    fits = []
    for x, y in zip(x_rows, y_rows, strict=True):
        a = _apply(x, rot, dim)
        fits.append(sum(p * q for p, q in zip(a, y, strict=True)))
    fit = sum(fits) / len(fits) if fits else 0.0
    return rot, fit


def align_embeddings(
    source: SignEmbeddings,
    target: SignEmbeddings,
    anchors: Sequence[tuple[str, str]],
    *,
    source_script: str = "source",
    target_script: str = "target",
) -> ProcrustesAlignment:
    """Align two sign-embedding spaces by orthogonal Procrustes on anchor pairs (EXPLORATORY).

    Learns the orthogonal rotation mapping ``source`` onto ``target`` from the ``anchors``
    (a seed dictionary of ``(source_sign, target_sign)`` correspondences), truncating both
    spaces to their common leading dimensionality. The returned :class:`ProcrustesAlignment`
    generates ranked correspondence hypotheses.

    Raises ``ValueError`` if either space is empty or no anchor pair is present in both
    vocabularies.

    **Caveat (EXPLORATORY).** Alignment between an undeciphered and a deciphered script is
    not decipherment; a score reflects distributional position in tiny corpora. Calibrate
    with :func:`recover_identity` and :func:`rank_known_pairs` before trusting any lead."""
    if not source.vocab or not target.vocab:
        raise ValueError("both embeddings must have a non-empty vocabulary")
    dim = min(source.dim, target.dim)
    if dim <= 0:
        raise ValueError("embeddings have no usable dimensions")
    src_vocab, src_vecs = _prep(source, dim)
    tgt_vocab, tgt_vecs = _prep(target, dim)
    rot, fit = _rotation_from_anchors(
        src_vocab, src_vecs, tgt_vocab, tgt_vecs, anchors, dim
    )
    n = sum(
        1
        for s, t in anchors
        if s in set(src_vocab) and t in set(tgt_vocab)
    )
    return ProcrustesAlignment(
        source_script=source_script,
        target_script=target_script,
        dim=dim,
        n_anchors=n,
        anchor_fit=fit,
        rotation=tuple(tuple(row) for row in rot),
        source_vocab=tuple(src_vocab),
        source_vectors=tuple(tuple(v) for v in src_vecs),
        target_vocab=tuple(tgt_vocab),
        target_vectors=tuple(tuple(v) for v in tgt_vecs),
    )


def shared_label_anchors(
    source: SignEmbeddings, target: SignEmbeddings
) -> list[tuple[str, str]]:
    """Anchor pairs where a source and target sign share a transliteration value.

    Matches signs by folded label (subscripts to ASCII, upper-cased), so a source ``RA₂``
    pairs with a target ``RA2``. Returns ``(source_label, target_label)`` pairs using each
    vocabulary's own spelling, in source-label order. For Linear A vs Linear B these are
    the AB chart-shared signs, a partial ground truth for calibration."""
    tgt_by_fold: dict[str, str] = {}
    for tgt in target.vocab:
        tgt_by_fold.setdefault(_fold(tgt), tgt)
    pairs: list[tuple[str, str]] = []
    for src in source.vocab:
        match = tgt_by_fold.get(_fold(src))
        if match is not None:
            pairs.append((src, match))
    pairs.sort()
    return pairs


def align_scripts(
    source_corpus: Any,
    target_corpus: Any,
    *,
    source_script: str = "source",
    target_script: str = "target",
    dim: int = 50,
    window: int = 1,
    anchors: Sequence[tuple[str, str]] | None = None,
) -> ProcrustesAlignment:
    """Build sign embeddings for two corpora and align them by Procrustes (EXPLORATORY).

    Convenience wrapper: learns :func:`aegean.analysis.embeddings.sign_embeddings` for each
    corpus, then :func:`align_embeddings`. When ``anchors`` is ``None`` the shared-value
    signs (:func:`shared_label_anchors`) are used as the seed dictionary.

    **Caveat (EXPLORATORY).** See :func:`align_embeddings`. Cross-script alignment produces
    hypotheses for a human expert, not readings."""
    src = sign_embeddings(source_corpus, dim=dim, window=window)
    tgt = sign_embeddings(target_corpus, dim=dim, window=window)
    if anchors is None:
        anchors = shared_label_anchors(src, tgt)
    return align_embeddings(
        src,
        tgt,
        anchors,
        source_script=source_script,
        target_script=target_script,
    )


# --------------------------------------------------------------------------- #
# Calibration (the honesty architecture)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IdentityCheck:
    """How well aligning a space to itself recovers the identity (calibration).

    ``top1_recovery`` / ``top5_recovery`` are the fractions of the evaluated signs whose
    own sign is the rank-1 / within-rank-5 correspondence after learning the rotation from
    an anchor subset. ``anchor_fraction`` records the split; ``n`` is the number of signs
    evaluated. With ``anchor_fraction = 1.0`` (all signs anchored) recovery is near-perfect
    and is the sanity floor: on a clean, well-separated space it is 1.0, and on a real
    corpus it falls short of 1.0 only where distinct signs share an identical context
    vector (distributional twins that resolve to a tied sibling), for example 0.901 on the
    bundled Linear A. A lower fraction measures how well a partial seed generalizes. A
    floor down near chance would instead signal broken machinery, not a real null."""

    n: int
    top1_recovery: float
    top5_recovery: float
    anchor_fraction: float


def recover_identity(
    emb: SignEmbeddings,
    *,
    anchor_fraction: float = 0.5,
    seed: int = 1,
) -> IdentityCheck:
    """Align an embedding to itself from an anchor subset and measure identity recovery.

    Splits the vocabulary into an anchor set (``anchor_fraction``) and an evaluation set
    (the remainder, or the whole vocabulary when ``anchor_fraction = 1.0``) using a seeded
    deterministic shuffle, learns the source→source rotation from the anchors, and reports
    how often an evaluated sign's top-ranked correspondence is itself. Aligning a space to
    itself should recover almost every sign (it falls short only on distributional twins,
    distinct signs with an identical context vector), so a high but sub-perfect score is
    the expected calibration sanity floor; a floor near chance would instead signal broken
    machinery rather than a genuine null.

    Raises ``ValueError`` for an out-of-range ``anchor_fraction`` or an empty vocabulary."""
    if not 0.0 < anchor_fraction <= 1.0:
        raise ValueError("anchor_fraction must be in (0, 1]")
    vocab = list(emb.vocab)
    if not vocab:
        raise ValueError("embedding has an empty vocabulary")
    order = _seeded_order(len(vocab), seed)
    shuffled = [vocab[i] for i in order]
    n_anchor = max(1, round(len(shuffled) * anchor_fraction))
    anchor_signs = shuffled[:n_anchor]
    if anchor_fraction >= 1.0:
        eval_signs = list(vocab)
    else:
        eval_signs = shuffled[n_anchor:] or list(vocab)
    anchors = [(s, s) for s in anchor_signs]
    alignment = align_embeddings(emb, emb, anchors)
    top1 = 0
    top5 = 0
    for s in eval_signs:
        corr = alignment.correspondences(s, k=5)
        ranked = [c.target_sign for c in corr]
        if ranked and ranked[0] == s:
            top1 += 1
        if s in ranked:
            top5 += 1
    n = len(eval_signs)
    return IdentityCheck(
        n=n,
        top1_recovery=top1 / n if n else 0.0,
        top5_recovery=top5 / n if n else 0.0,
        anchor_fraction=anchor_fraction,
    )


@dataclass(frozen=True)
class RankReport:
    """Where known correspondence pairs land in the ranked hypotheses (calibration).

    ``ranks`` is the 1-based rank of each known pair's true target sign among all
    ``n_targets`` target signs (lower is better; rank 1 = recovered). ``top1`` / ``top5``
    are the fractions at rank ≤ 1 / ≤ 5; ``median_rank`` / ``mean_rank`` summarize the
    distribution. ``leave_one_out`` records whether each pair was held out of the anchors
    when it was scored (the honest generalization measure). Whatever this shows, weak or
    strong, is the honest strength of the cross-script signal (EXPLORATORY)."""

    n: int
    n_targets: int
    ranks: tuple[int, ...]
    top1: float
    top5: float
    median_rank: float
    mean_rank: float
    leave_one_out: bool

    @property
    def chance_median(self) -> float:
        """The median rank pure chance would give (``(n_targets + 1) / 2``), for comparison."""
        return (self.n_targets + 1) / 2


def rank_known_pairs(
    source: SignEmbeddings,
    target: SignEmbeddings,
    pairs: Sequence[tuple[str, str]],
    *,
    leave_one_out: bool = True,
) -> RankReport:
    """Report where known correspondence pairs rank in the aligned hypotheses (calibration).

    For each known ``(source_sign, target_sign)`` pair, learns the alignment and finds the
    rank of ``target_sign`` in the source sign's ranked correspondence list. With
    ``leave_one_out=True`` (default) the pair being scored is excluded from the anchors, so
    the rank measures genuine generalization rather than memorized anchors. With
    ``leave_one_out=False`` a single alignment is learned from all pairs and reused.

    Only pairs whose both signs are in the two vocabularies are scored. Raises ``ValueError``
    if none qualify. Whatever rank distribution results is the honest measure of how much
    the geometry recovers the known mapping, weak or strong (EXPLORATORY)."""
    valid = [
        (s, t)
        for s, t in pairs
        if s in set(source.vocab) and t in set(target.vocab)
    ]
    if not valid:
        raise ValueError("no known pair has both signs present in the two vocabularies")
    n_targets = len(target.vocab)
    ranks: list[int] = []
    if not leave_one_out:
        alignment = align_embeddings(source, target, valid)
    for idx, (s, t) in enumerate(valid):
        if leave_one_out:
            held = valid[:idx] + valid[idx + 1 :]
            if not held:
                held = valid  # single pair: nothing to hold out
            alignment = align_embeddings(source, target, held)
        corr = alignment.correspondences(s, k=n_targets)
        rank = next((c.rank for c in corr if c.target_sign == t), n_targets)
        ranks.append(rank)
    ranks_sorted = sorted(ranks)
    n = len(ranks)
    median = (
        ranks_sorted[n // 2]
        if n % 2 == 1
        else (ranks_sorted[n // 2 - 1] + ranks_sorted[n // 2]) / 2
    )
    return RankReport(
        n=n,
        n_targets=n_targets,
        ranks=tuple(ranks),
        top1=sum(1 for r in ranks if r <= 1) / n,
        top5=sum(1 for r in ranks if r <= 5) / n,
        median_rank=float(median),
        mean_rank=sum(ranks) / n,
        leave_one_out=leave_one_out,
    )


def _seeded_order(n: int, seed: int) -> list[int]:
    """A deterministic Fisher-Yates shuffle of ``range(n)`` driven by ``mulberry32``."""
    rand = mulberry32(seed)
    order = list(range(n))
    for i in range(n - 1, 0, -1):
        j = int(rand() * (i + 1))
        if j > i:
            j = i
        order[i], order[j] = order[j], order[i]
    return order
