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

    w = arc_scores.shape[0]
    full = np.full((w + 1, w + 1), -np.inf)
    full[1:, :] = arc_scores
    heads = _cle(full, np)
    root_children = [d for d in range(1, w + 1) if heads[d] == 0]
    if len(root_children) > 1:
        best = max(root_children, key=lambda d: full[d, 0])
        constrained = full.copy()
        for d in root_children:
            if d != best:
                constrained[d, 0] = -np.inf
        heads = _cle(constrained, np)
    return [int(h) for h in heads[1:]]
