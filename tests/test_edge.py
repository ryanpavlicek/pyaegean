"""Positional / edge keyness and morphological productivity (analysis.edge).

Ported from the Linear A Research Workbench's Morphology / Positional-Grammar
modules; anchors are the worked examples extracted from that source.
"""

from __future__ import annotations

import pytest

from aegean.analysis.edge import (
    affix_edge_bias,
    baayen_productivity,
    edge_bias_g2,
    positional_bias,
    positional_bias_g2,
    successor_variety,
)


class TestEdgeBiasG2:
    def test_core_anchors(self) -> None:
        assert edge_bias_g2(6, 7, 1, 7) == pytest.approx(7.924864143603013, abs=1e-9)
        assert edge_bias_g2(1, 7, 0, 7) == pytest.approx(1.4632934791895598, abs=1e-9)

    def test_sign_and_degenerate(self) -> None:
        # interior-leaning -> negative
        assert edge_bias_g2(0, 7, 6, 7) < 0
        # empty edge or interior population -> 0
        assert edge_bias_g2(0, 0, 1, 7) == 0.0
        assert edge_bias_g2(1, 7, 0, 0) == 0.0

    def test_corpus_wrapper(self) -> None:
        rows = {
            r.affix: r
            for r in affix_edge_bias(
                [("A-RO", 2), ("TI-RO", 3), ("RO-WA", 1), ("QA-RO", 1)],
                affix_len=1,
                mode="suffix",
            )
        }
        assert rows["RO"].edge_count == 6
        assert rows["RO"].interior == 1
        assert rows["RO"].g2 == pytest.approx(7.924864143603013, abs=1e-9)
        assert rows["WA"].edge_count == 1
        assert rows["WA"].interior == 0
        assert rows["WA"].g2 == pytest.approx(1.4632934791895598, abs=1e-9)


class TestPositionalBiasG2:
    def test_core_anchor(self) -> None:
        assert positional_bias_g2(3, 4, 3, 7) == pytest.approx(5.062032308856136, abs=1e-9)

    def test_corpus_wrapper(self) -> None:
        rows = {
            r.word: r
            for r in positional_bias(
                [["A-B", "C-D", "E-F"], ["A-B", "G-H"], ["A-B"]]
            )
        }
        ab = rows["A-B"]
        assert (ab.initial, ab.medial, ab.final) == (3, 0, 1)  # lone-word double-counts edges
        assert ab.dominant == "initial"
        assert ab.g2 == pytest.approx(5.062032308856136, abs=1e-9)
        # hapaxes are not scored
        assert "C-D" not in rows


class TestBaayenProductivity:
    def test_worked_example(self) -> None:
        rows = {
            r.affix: r
            for r in baayen_productivity(
                [("KU-RO", 5), ("PA-RO", 1), ("SI-RO", 1), ("KU-PA", 3), ("DI-NA", 1)],
                affix_len=1,
                mode="suffix",
            )
        }
        ro = rows["RO"]
        assert ro.count == 7
        assert ro.distinct == 3
        assert ro.hapax == 2
        assert ro.productivity == pytest.approx(2 / 7, abs=1e-12)
        assert rows["PA"].productivity == 0.0
        assert rows["NA"].productivity == 1.0


class TestSuccessorVariety:
    def test_worked_example(self) -> None:
        sv = successor_variety(
            ["A-B-X", "A-B-Y", "A-B-Z", "A-C", "A-D", "P-Q-M", "P-Q-N", "P-R"]
        )
        assert sv.total == 1
        row = sv.rows[0]
        assert row.stem == "A-B"
        assert row.variety == 3
        assert row.parent_variety == 3
        assert row.ratio == pytest.approx(1.2, abs=1e-12)

    def test_too_sparse(self) -> None:
        sv = successor_variety(["KU-RO", "KU-RO-2"])
        assert sv.total == 0
        assert sv.rows == []
