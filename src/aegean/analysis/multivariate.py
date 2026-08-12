"""Multivariate exploration: correspondence analysis, UPGMA, label propagation.

Ported 1:1 from the Linear A Research Workbench's ``src/lib/multivariate.ts``:

- **correspondence analysis** — the biplot behind "which sites/scribes pattern
  with which words/commodities": an SVD of the standardized residuals of a
  contingency table by power iteration with deflation, keeping the top two axes,
  so rows and columns share a plane.
- **UPGMA with bootstrap support** — average-linkage hierarchical clustering of
  labeled count vectors (cosine distance), with feature-resampled bootstrap
  support per node.
- **label propagation** — Raghavan et al. (2007) weighted community detection
  with deterministic tie-breaks and a seeded visit order.

All deterministic — power iteration from a fixed start vector, seeded resamples
(the same ``mulberry32`` stream as the workbench), ordered tie-breaks — so a
result is reproducible. Exploratory on undeciphered material.
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .stats import mulberry32

__all__ = [
    "CAPoint",
    "CAResult",
    "correspondence_analysis",
    "DendroMerge",
    "DendroResult",
    "upgma_with_bootstrap",
    "label_propagation",
]


# ── correspondence analysis ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CAPoint:
    """A row or column in the CA plane: ``x``/``y`` principal coordinates and
    ``mass`` (its marginal share of the table, which drives point size)."""

    label: str
    x: float
    y: float
    mass: float


@dataclass(frozen=True)
class CAResult:
    """Correspondence-analysis biplot: ``rows`` and ``cols`` in a shared plane,
    the share of total ``inertia`` on axes 1 and 2, and ``total_inertia``."""

    rows: list[CAPoint]
    cols: list[CAPoint]
    inertia: tuple[float, float]
    total_inertia: float


def _power_iterate(
    ata: list[list[float]], skip: list[list[float]]
) -> tuple[float, list[float]] | None:
    """Leading eigenpair of a symmetric PSD matrix by power iteration, deflated
    against the vectors in ``skip``. Returns ``(eigenvalue, eigenvector)``."""
    m = len(ata)
    if m == 0:
        return None
    # Fixed, slightly asymmetric start vector — deterministic, not accidentally
    # orthogonal to anything.
    v = [1 + (i + 1) / m for i in range(m)]

    def orthogonalize(vec: list[float]) -> None:
        for u in skip:
            dot = sum(vec[i] * u[i] for i in range(m))
            for i in range(m):
                vec[i] -= dot * u[i]

    value = 0.0
    for _ in range(300):
        orthogonalize(v)
        nxt = [sum(ata[i][j] * v[j] for j in range(m)) for i in range(m)]
        norm = math.sqrt(sum(x * x for x in nxt))
        if norm < 1e-12:
            return None
        v = [x / norm for x in nxt]
        value = norm
    return value, v


def correspondence_analysis(
    row_labels: Sequence[str],
    col_labels: Sequence[str],
    counts: Sequence[Sequence[float]],
) -> CAResult | None:
    """Correspondence analysis of a rows × columns contingency table.

    Keeps the top two axes. Rows and columns land in the same plane: a row sits
    in the direction of the columns it over-uses; distance from the origin is
    deviation from the average profile. Returns ``None`` when there are fewer
    than 3 rows or columns, any zero-margin row/column (filter those first), or
    the table is independent (no inertia to plot)."""
    nr = len(row_labels)
    nc = len(col_labels)
    if nr < 3 or nc < 3:
        return None
    n = sum(counts[i][j] for i in range(nr) for j in range(nc))
    if n <= 0:
        return None
    r = [sum(counts[i][j] for j in range(nc)) / n for i in range(nr)]
    c = [sum(counts[i][j] for i in range(nr)) / n for j in range(nc)]
    if any(x == 0 for x in r) or any(x == 0 for x in c):
        return None
    s_mat = [[0.0] * nc for _ in range(nr)]
    total_inertia = 0.0
    for i in range(nr):
        for j in range(nc):
            p = counts[i][j] / n
            s = (p - r[i] * c[j]) / math.sqrt(r[i] * c[j])
            s_mat[i][j] = s
            total_inertia += s * s
    if total_inertia < 1e-12:
        return None
    ata = [[0.0] * nc for _ in range(nc)]
    for a in range(nc):
        for b in range(a, nc):
            s = sum(s_mat[i][a] * s_mat[i][b] for i in range(nr))
            ata[a][b] = s
            ata[b][a] = s
    first = _power_iterate(ata, [])
    if first is None:
        return None
    second = _power_iterate(ata, [first[1]])
    sigma1 = math.sqrt(max(0.0, first[0]))
    sigma2 = math.sqrt(max(0.0, second[0])) if second is not None else 0.0
    v1 = first[1]
    v2 = second[1] if second is not None else [0.0] * nc

    def u(v: list[float], sigma: float) -> list[float]:
        if sigma < 1e-12:
            return [0.0] * nr
        return [sum(s_mat[i][j] * v[j] for j in range(nc)) / sigma for i in range(nr)]

    u1 = u(v1, sigma1)
    u2 = u(v2, sigma2)
    rows = [
        CAPoint(
            label=label,
            x=(u1[i] / math.sqrt(r[i])) * sigma1,
            y=(u2[i] / math.sqrt(r[i])) * sigma2,
            mass=r[i],
        )
        for i, label in enumerate(row_labels)
    ]
    cols = [
        CAPoint(
            label=label,
            x=(v1[j] / math.sqrt(c[j])) * sigma1,
            y=(v2[j] / math.sqrt(c[j])) * sigma2,
            mass=c[j],
        )
        for j, label in enumerate(col_labels)
    ]
    return CAResult(
        rows=rows,
        cols=cols,
        inertia=(sigma1 * sigma1 / total_inertia, sigma2 * sigma2 / total_inertia),
        total_inertia=total_inertia,
    )


# ── UPGMA with bootstrap support ─────────────────────────────────────────────


@dataclass(frozen=True)
class DendroMerge:
    """One merge: the two child cluster ids, the ``height`` (cosine distance) it
    joined at, the sorted member ``labels`` it creates, and bootstrap
    ``support`` (0–1; 1 for the trivially-present root)."""

    a: int
    b: int
    height: float
    members: list[str]
    support: float


@dataclass(frozen=True)
class DendroResult:
    """A dendrogram: the leaf ``labels``, the ``merges`` (leaves are ids
    0..n-1; merge k creates id n+k), and the left→right leaf ``order``."""

    labels: list[str]
    merges: list[DendroMerge]
    order: list[str]


def _cosine_distance(
    a: Mapping[str, float], b: Mapping[str, float], features: Sequence[str]
) -> float:
    dot = na = nb = 0.0
    for f in features:
        x = a.get(f, 0.0)
        y = b.get(f, 0.0)
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 1.0
    return 1 - dot / math.sqrt(na * nb)


def _key(x: int, y: int) -> str:
    return f"{x}|{y}" if x < y else f"{y}|{x}"


@dataclass(frozen=True)
class _Merge:
    a: int
    b: int
    height: float
    members: list[int]  # item indices


def _upgma_merges(
    items: Sequence[tuple[str, Mapping[str, float]]], features: Sequence[str]
) -> list[_Merge]:
    n = len(items)
    members: dict[int, list[int]] = {i: [i] for i in range(n)}
    dist: dict[str, float] = {}
    ids = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            dist[_key(i, j)] = _cosine_distance(items[i][1], items[j][1], features)
    merges: list[_Merge] = []
    while len(ids) > 1:
        best: tuple[int, int] | None = None
        best_d = math.inf
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                d = dist.get(_key(ids[x], ids[y]), math.inf)
                if d < best_d - 1e-12:
                    best_d = d
                    best = (ids[x], ids[y])
        if best is None:
            break
        a, b = best
        new_id = n + len(merges)
        ma, mb = members[a], members[b]
        merged = sorted(ma + mb)
        members[new_id] = merged
        for k in ids:
            if k in (a, b):
                continue
            da = dist[_key(a, k)]
            db = dist[_key(b, k)]
            dist[_key(new_id, k)] = (len(ma) * da + len(mb) * db) / (len(ma) + len(mb))
        merges.append(_Merge(a=a, b=b, height=best_d, members=merged))
        ids.remove(a)
        ids.remove(b)
        ids.append(new_id)
    return merges


def upgma_with_bootstrap(
    items: Sequence[tuple[str, Mapping[str, float]]],
    *,
    iters: int = 100,
    seed: int = 42,
) -> DendroResult | None:
    """Average-linkage UPGMA over labeled count vectors (cosine distance) with
    feature-resampled bootstrap support.

    ``items`` is a sequence of ``(label, counts)`` pairs. Support for each node
    is the share of bootstrap replicates (features resampled with replacement,
    the standard move when features carry the signal) whose tree contains exactly
    the same member set. Returns ``None`` below 3 items or 2 features. Read
    support below ~0.5 as weak."""
    n = len(items)
    if n < 3:
        return None
    vocab = list(dict.fromkeys(f for _, counts in items for f in counts))
    if len(vocab) < 2:
        return None
    ref = _upgma_merges(items, vocab)
    rand = mulberry32(seed)

    def member_key(m: list[int]) -> str:
        return ",".join(str(i) for i in m)

    want: dict[str, int] = {member_key(m.members): 0 for m in ref}
    for _ in range(iters):
        sample = [vocab[int(rand() * len(vocab))] for _ in range(len(vocab))]
        seen = {member_key(m.members) for m in _upgma_merges(items, sample)}
        for k in want:
            if k in seen:
                want[k] += 1
    merges = [
        DendroMerge(
            a=m.a,
            b=m.b,
            height=m.height,
            members=sorted(items[i][0] for i in m.members),
            support=1.0 if len(m.members) == n else want.get(member_key(m.members), 0) / iters,
        )
        for m in ref
    ]
    order: list[str] = []

    def walk(idx: int) -> None:
        if idx < n:
            order.append(items[idx][0])
            return
        mm = ref[idx - n]
        walk(mm.a)
        walk(mm.b)

    walk(n + len(ref) - 1)
    return DendroResult(labels=[it[0] for it in items], merges=merges, order=order)


# ── label-propagation communities ────────────────────────────────────────────


# The floor the derived round budget never falls below. A graph of a few dozen nodes settles in
# under ten rounds, so the floor leaves the small end an order of magnitude of headroom without
# the per-node allowance below having to reach down that far.
_MIN_DERIVED_MAX_ITERS = 50

# Rounds allowed per node. How many rounds a graph needs is set by how far a label must travel
# along it, and a path graph, the structure that makes that distance largest, settles in about
# 0.6 rounds per node (measured from 50 to 500 nodes: 31, 60, 112, 179, 298 rounds). One round
# per node clears that worst case with margin, and no graph on the same nodes needs more, since
# adding edges only shortens the distances a label crosses.
_ITERATIONS_PER_NODE = 1

# The node visits (rounds times nodes) the derived budget may spend. A round costs work
# proportional to the graph's size, so the per-node budget alone would grow the total with the
# square of the node count; this allowance is what holds that in check, capping the derived
# budget at roughly a second of work. Past it the budget falls with size instead of rising, so
# a graph too large to settle within the allowance is reported unsettled rather than run longer.
_DERIVED_WORK_ALLOWANCE = 400_000


def _default_max_iters(n: int) -> int:
    """The round budget for a graph of ``n`` nodes when the caller names none.

    The budget has three regimes. It rises with the graph to a peak at 632 nodes, because up to
    there a larger graph needs more rounds to settle and a round is still cheap. Past the peak
    :data:`_DERIVED_WORK_ALLOWANCE` decides instead and the budget falls with size. From 8,000
    nodes the allowance has dropped below :data:`_MIN_DERIVED_MAX_ITERS`, so every graph from
    there up gets exactly the floor. A caller who wants a graph past the peak run further names
    its own ``max_iters``, which is then used as given."""
    if n < 1:
        return _MIN_DERIVED_MAX_ITERS
    return max(_MIN_DERIVED_MAX_ITERS, min(_ITERATIONS_PER_NODE * n, _DERIVED_WORK_ALLOWANCE // n))


def label_propagation(
    nodes: Sequence[str],
    edges: Iterable[tuple[str, str, float]],
    *,
    seed: int = 7,
    max_iters: int | None = None,
) -> dict[str, int]:
    """Weighted label-propagation community detection (Raghavan et al. 2007).

    ``edges`` is an iterable of ``(a, b, weight)`` tuples (undirected;
    self-loops and edges to unknown nodes are ignored). Deterministic via the
    seeded visit-order shuffle and ``label < current`` tie-break. Returns
    ``{node: community_id}`` with communities renumbered by descending size.
    Good for coloring a few hundred nodes — not a modularity method for large
    graphs.

    Rounds run until no node changes label, which is what makes the labelling the graph's
    own: a run stopped before then returns labels still in mid-flight, splitting one
    community into the several fragments a label had not yet crossed. Such a run warns,
    since nothing in the returned mapping distinguishes it from a settled one.

    ``max_iters`` caps the rounds; ``None`` derives the cap from the graph's own node count,
    since how far a label has to travel to settle scales with the graph."""
    budget = _default_max_iters(len(nodes)) if max_iters is None else max_iters
    rand = mulberry32(seed)
    label = {nd: i for i, nd in enumerate(nodes)}
    nbrs: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for a, b, w in edges:
        if a not in label or b not in label or a == b:
            continue
        nbrs[a].append((b, w))
        nbrs[b].append((a, w))
    order_arr = list(nodes)
    settled = False
    # The most recent round's count. A budget of zero rounds runs none, and leaves every node
    # where it started, which is the count this stands at.
    changed = len(nodes)
    for _ in range(budget):
        for i in range(len(order_arr) - 1, 0, -1):
            j = int(rand() * (i + 1))
            order_arr[i], order_arr[j] = order_arr[j], order_arr[i]
        changed = 0
        for nd in order_arr:
            ns = nbrs.get(nd)
            if not ns:
                continue
            weight: dict[int, float] = {}
            for to, w in ns:
                lab = label[to]
                weight[lab] = weight.get(lab, 0.0) + w
            best_label = label[nd]
            best_w = -math.inf
            for lab, w in weight.items():
                if w > best_w or (w == best_w and lab < best_label):
                    best_w = w
                    best_label = lab
            if best_label != label[nd]:
                label[nd] = best_label
                changed += 1
        if changed == 0:
            settled = True
            break
    if not settled:
        warnings.warn(
            f"label propagation was still moving {changed} of {len(nodes)} nodes when it reached"
            f" its budget of {budget} rounds: the communities returned are mid-propagation, so a"
            " single community may appear split, and raising max_iters gives it the rounds it"
            " needs",
            stacklevel=2,
        )
    sizes: dict[int, int] = {}
    for lab in label.values():
        sizes[lab] = sizes.get(lab, 0) + 1
    renumber: dict[int, int] = {}
    for i, (old, _) in enumerate(sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))):
        renumber[old] = i
    return {nd: renumber[lab] for nd, lab in label.items()}
