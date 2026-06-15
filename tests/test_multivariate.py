"""Multivariate analysis: correspondence analysis, UPGMA, label propagation.

Ported 1:1 from the Linear A Research Workbench's ``multivariate.test.ts``, plus
the aegean.viz per-axis CA layout companion.
"""

from __future__ import annotations

import math

from aegean.analysis.multivariate import (
    correspondence_analysis,
    label_propagation,
    upgma_with_bootstrap,
)
from aegean.viz import correspondence_layout


class TestCorrespondenceAnalysis:
    def test_separates_block_structure_on_axis1(self) -> None:
        res = correspondence_analysis(
            ["r0", "r1", "r2", "r3"],
            ["A", "B", "C", "D"],
            [[30, 25, 1, 2], [28, 31, 2, 1], [1, 2, 33, 27], [2, 1, 26, 30]],
        )
        assert res is not None
        assert res.inertia[0] > 0.8
        by = {p.label: p for p in res.rows}
        assert math.copysign(1, by["r0"].x) == math.copysign(1, by["r1"].x)
        assert math.copysign(1, by["r2"].x) == math.copysign(1, by["r3"].x)
        assert math.copysign(1, by["r0"].x) != math.copysign(1, by["r2"].x)
        col_a = next(c for c in res.cols if c.label == "A")
        col_c = next(c for c in res.cols if c.label == "C")
        assert math.copysign(1, col_a.x) == math.copysign(1, by["r0"].x)
        assert math.copysign(1, col_c.x) == math.copysign(1, by["r2"].x)

    def test_null_for_independent_and_degenerate(self) -> None:
        r = [10, 20, 30]
        c = [1, 2, 3]
        table = [[ri * cj for cj in c] for ri in r]
        assert correspondence_analysis(["a", "b", "c"], ["x", "y", "z"], table) is None
        assert (
            correspondence_analysis(["a", "b"], ["x", "y", "z"], [[1, 2, 3], [4, 5, 6]])
            is None
        )

    def test_deterministic(self) -> None:
        table = [[5, 1, 0, 2], [4, 2, 1, 1], [0, 6, 5, 0], [1, 4, 6, 1], [2, 0, 1, 7]]
        labels = ["p", "q", "r", "s", "t"]
        cols = ["w", "x", "y", "z"]
        assert correspondence_analysis(labels, cols, table) == correspondence_analysis(
            labels, cols, table
        )


_ITEMS = [
    ("siteA1", {"ku": 30, "ro": 28, "pa": 2}),
    ("siteA2", {"ku": 25, "ro": 30, "pa": 1}),
    ("siteB1", {"za": 22, "te": 18, "ku": 1}),
    ("siteB2", {"za": 19, "te": 24, "ro": 2}),
]


class TestUpgmaWithBootstrap:
    def test_pairs_similar_items_with_support(self) -> None:
        res = upgma_with_bootstrap(_ITEMS, iters=60, seed=9)
        assert res is not None
        pair_keys = ["+".join(m.members) for m in res.merges]
        assert "siteA1+siteA2" in pair_keys
        assert "siteB1+siteB2" in pair_keys
        a = next(m for m in res.merges if "+".join(m.members) == "siteA1+siteA2")
        assert a.support > 0.8
        root = res.merges[-1]
        assert len(root.members) == 4
        assert root.support == 1.0

    def test_deterministic_and_null_below_three(self) -> None:
        assert upgma_with_bootstrap(_ITEMS, iters=30, seed=5) == upgma_with_bootstrap(
            _ITEMS, iters=30, seed=5
        )
        assert upgma_with_bootstrap(_ITEMS[:2]) is None


class TestLabelPropagation:
    def test_two_cliques_with_weak_bridge(self) -> None:
        nodes = ["a1", "a2", "a3", "b1", "b2", "b3"]
        edges = [
            ("a1", "a2", 5), ("a1", "a3", 5), ("a2", "a3", 5),
            ("b1", "b2", 5), ("b1", "b3", 5), ("b2", "b3", 5),
            ("a3", "b1", 1),
        ]
        com = label_propagation(nodes, edges, seed=3)
        assert com["a1"] == com["a2"] == com["a3"]
        assert com["b1"] == com["b2"] == com["b3"]
        assert com["a1"] != com["b1"]

    def test_isolated_node_and_determinism(self) -> None:
        nodes = ["x", "y", "lone"]
        edges = [("x", "y", 2)]
        a = label_propagation(nodes, edges, seed=11)
        assert a == label_propagation(nodes, edges, seed=11)
        assert a["x"] == a["y"]
        assert a["lone"] != a["x"]


class TestCorrespondenceLayout:
    def test_per_axis_scaling_pins_outlier(self) -> None:
        # A cloud of 10 small x plus one far outlier beyond the 90th percentile:
        # the outlier pins to the edge, the cloud keeps its spread (it would
        # collapse to ~0 under global-max scaling).
        points = [(0.1 * i, 0.0) for i in range(1, 11)] + [(100.0, 0.0)]
        out = correspondence_layout(points)
        assert out[-1][0] == 1.0  # outlier pinned at the right edge
        assert all(-1.0 <= x <= 1.0 for x, _ in out)
        assert out[9][0] > 0.5  # the cloud still spreads, not crushed to ~0
        assert out[1][0] > out[0][0]  # order preserved

    def test_empty(self) -> None:
        assert correspondence_layout([]) == []
