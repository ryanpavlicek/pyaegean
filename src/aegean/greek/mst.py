"""Single-root maximum-spanning-arborescence decoding (Chu-Liu/Edmonds).

Graph-based tree decoding for the neural dependency parser (`aegean.greek.joint`):
unlike transition-based decoding, an arborescence handles Ancient Greek's pervasive
non-projectivity natively. numpy is imported lazily (it ships with the ``[neural]``
extra), so ``import aegean`` stays dependency-free.
"""

from __future__ import annotations

from typing import Any

__all__ = ["decode_mst"]


def _cle(scores: Any, np: Any) -> Any:
    """Max spanning arborescence rooted at node 0. ``scores[d, h]`` = score of the h→d
    arc; row 0 (the root as dependent) is ignored. Returns head[] with head[0] = -1."""
    n = scores.shape[0]
    heads = scores.argmax(axis=1)
    heads[0] = -1
    for d in range(1, n):
        if heads[d] == d:
            s = scores[d].copy()
            s[d] = -np.inf
            heads[d] = int(s.argmax())

    def find_cycle() -> list[int] | None:
        color = [0] * n
        for start in range(1, n):
            if color[start]:
                continue
            path, v = [], start
            while v != -1 and color[v] == 0:
                color[v] = 1
                path.append(v)
                v = int(heads[v]) if heads[v] >= 0 else -1
            if v != -1 and color[v] == 1 and v in path:
                return path[path.index(v):]
            for u in path:
                color[u] = 2
        return None

    cycle = find_cycle()
    if cycle is None:
        return heads
    cyc = set(cycle)
    cyc_score = sum(scores[d, heads[d]] for d in cycle)
    keep = [v for v in range(n) if v not in cyc]
    new_of = {v: i for i, v in enumerate(keep)}
    c_new = len(keep)
    m = len(keep) + 1
    new_scores = np.full((m, m), -np.inf)
    best_in: dict[int, int] = {}
    best_out: dict[int, int] = {}
    for d in range(1, n):
        for h in range(n):
            if d == h:
                continue
            s = scores[d, h]
            if d in cyc and h not in cyc:
                gain = s - scores[d, heads[d]]
                key = new_of[h]
                if cyc_score + gain > new_scores[c_new, key]:
                    new_scores[c_new, key] = cyc_score + gain
                    best_in[key] = d
            elif d not in cyc and h in cyc:
                if s > new_scores[new_of[d], c_new]:
                    new_scores[new_of[d], c_new] = s
                    best_out[new_of[d]] = h
            elif d not in cyc and h not in cyc:
                new_scores[new_of[d], new_of[h]] = s
    sub = _cle(new_scores, np)
    out = heads.copy()
    for d_new in range(1, m):
        h_new = int(sub[d_new])
        if d_new == c_new:                       # the arc that breaks the cycle
            enter_dep = best_in[h_new]
            out[enter_dep] = keep[h_new]
        elif h_new == c_new:                     # arcs hanging off the cycle
            out[keep[d_new]] = best_out[d_new]
        else:
            out[keep[d_new]] = keep[h_new]
    return out


def decode_mst(arc_scores: Any) -> list[int]:
    """Heads for one sentence from arc scores ``[W, W+1]`` (column 0 = ROOT), with a
    single-root constraint. Returns CoNLL-U HEAD values (0 = root, else 1-based)."""
    import numpy as np  # lazy: ships with the [neural] extra

    try:
        scores = np.asarray(arc_scores, dtype=np.float64)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("arc scores must be numeric") from exc
    if scores.ndim != 2 or scores.shape[1] != scores.shape[0] + 1:
        raise ValueError("arc scores must have shape [words, words + 1]")
    if np.isnan(scores).any() or np.isposinf(scores).any():
        raise ValueError("arc scores may contain finite values or negative infinity only")
    w = scores.shape[0]
    if w == 0:
        return []
    full = np.full((w + 1, w + 1), -np.inf)
    full[1:, :] = scores
    # A self-loop is never a dependency-tree edge, even if a caller supplied a
    # finite diagonal value.
    full[np.arange(1, w + 1), np.arange(1, w + 1)] = -np.inf
    if not np.isfinite(full[1:]).any(axis=1).all():
        raise ValueError("every dependent requires at least one finite candidate head")

    def valid_tree(heads: Any) -> bool:
        if len(heads) != w + 1:
            return False
        values = [int(heads[d]) for d in range(1, w + 1)]
        if values.count(0) != 1:
            return False
        for dependent, head in enumerate(values, start=1):
            if head < 0 or head > w or head == dependent:
                return False
            if not np.isfinite(full[dependent, head]):
                return False
            seen: set[int] = set()
            node = dependent
            while node:
                if node in seen:
                    return False
                seen.add(node)
                node = values[node - 1]
        return True

    # Penalize every ROOT edge by more than the largest possible score
    # difference between two W-edge arborescences.  Every valid arborescence
    # needs at least one ROOT edge, so its unconstrained optimum then has exactly
    # one.  Among single-root trees the common penalty leaves the original score
    # ordering unchanged.  Scaling first avoids overflow for extreme finite inputs.
    finite = np.isfinite(full)
    scale = max(1.0, float(np.abs(full[finite]).max()))
    scaled = full.copy()
    scaled[finite] /= scale
    finite_values = scaled[finite]
    span = float(finite_values.max() - finite_values.min())
    penalty = 1.0 + w * span
    # The penalty subtraction is float64 arithmetic: a ROOT-score difference far
    # below one ulp of the penalty would be absorbed, and the collapsed tie could
    # resolve to a suboptimal root child.  Score matrices derived from float32
    # model logits sit several orders of magnitude above this threshold, so the
    # guard is a pure inspection there and the penalized path runs unchanged; it
    # can fire only for extreme mixed-magnitude float64 inputs, which take the
    # exact per-root fallback instead.
    absorption_risk = False
    root_column = scaled[1:, 0]
    root_values = np.unique(root_column[np.isfinite(root_column)])
    if len(root_values) > 1:
        min_gap = float(np.diff(root_values).min())
        largest = float(np.abs(root_values).max())
        if min_gap <= 64.0 * float(np.spacing(penalty + largest)):
            absorption_risk = True
    if not absorption_risk:
        constrained = scaled.copy()
        constrained[1:, 0] -= penalty
        try:
            heads = _cle(constrained, np)
        except (KeyError, ValueError, IndexError) as exc:
            raise ValueError(
                "arc scores do not contain a valid single-root arborescence"
            ) from exc
        if not valid_tree(heads):
            raise ValueError("arc scores do not contain a valid single-root arborescence")
        return [int(h) for h in heads[1:]]

    # Exact fallback: force each candidate root child in turn on the unpenalized
    # scaled matrix and keep the best legal tree.  No penalty arithmetic is
    # involved, so the result is exact up to ordinary float64 summation.
    best_total = -np.inf
    best_heads: Any = None
    for candidate in range(1, w + 1):
        if not np.isfinite(scaled[candidate, 0]):
            continue
        forced = scaled.copy()
        root_score = forced[candidate, 0]
        forced[1:, 0] = -np.inf
        forced[candidate, 0] = root_score
        try:
            heads = _cle(forced, np)
        except (KeyError, ValueError, IndexError):
            continue
        if not valid_tree(heads):
            continue
        total = float(sum(scaled[d, int(heads[d])] for d in range(1, w + 1)))
        if best_heads is None or total > best_total:
            best_total = total
            best_heads = heads
    if best_heads is None:
        raise ValueError("arc scores do not contain a valid single-root arborescence")
    return [int(h) for h in best_heads[1:]]
