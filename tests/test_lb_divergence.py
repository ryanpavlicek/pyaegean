"""Linear A vs Linear B sign-frequency divergence + Spearman.

Ported from the workbench's ``src/lib/linearB.ts``. The headline real-corpus
result (≈43 shared values, Spearman rho ≈ 0.15 between the two scripts' use of
the shared signary) needs the full DAMOS download and the bundled phonetic map;
here the functions are checked on synthetic anchors.
"""

from __future__ import annotations

import math

import pytest

from aegean.analysis.lb_divergence import (
    build_lb_divergence,
    linear_a_sign_value_counts,
    parse_damos_frequencies,
)
from aegean.analysis.stats import spearman_rho


class TestSpearmanRho:
    def test_perfect_and_anti(self) -> None:
        assert spearman_rho([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) == pytest.approx(1.0)
        assert spearman_rho([1, 2, 3, 4, 5], [10, 8, 6, 4, 2]) == pytest.approx(-1.0)

    def test_ties_average_ranks(self) -> None:
        assert spearman_rho([1, 1, 2, 3, 4], [1, 2, 2, 3, 4]) == pytest.approx(
            0.9210526315789473, abs=1e-12
        )

    def test_degenerate(self) -> None:
        assert spearman_rho([1, 2], [1, 2]) == 0.0  # n < 3
        assert spearman_rho([1, 2, 3], [4, 5]) == 0.0  # length mismatch
        assert spearman_rho([5, 5, 5], [1, 2, 3]) == 0.0  # constant series


class TestParseDamos:
    def test_counts_multi_sign_syllabogram_words(self) -> None:
        payload = {
            "_meta": {"version": "v2", "generated": "2025", "cite": "DAMOS"},
            "documents": [{"content": ".1. ku-ro da-i\n.2. ka-ko VIR 3"}],
        }
        lb = parse_damos_frequencies(payload)
        assert lb.counts == {"ku": 1, "ro": 1, "da": 1, "i": 1, "ka": 1, "ko": 1}
        assert lb.total_signs == 6
        assert lb.word_tokens == 3  # ku-ro, da-i, ka-ko; VIR and the numeral skipped
        assert lb.doc_count == 1
        assert lb.version == "v2"

    def test_strips_brackets_and_dots(self) -> None:
        # An editorial bracket and a damaged-sign underdot (NFD combining) are
        # stripped, not excluded.
        payload = {"documents": [{"content": "[ku]-rọ"}]}
        lb = parse_damos_frequencies(payload)
        assert lb.counts == {"ku": 1, "ro": 1}


class TestLinearAValueCounts:
    def test_token_weighted_by_value(self) -> None:
        la = linear_a_sign_value_counts([("KU-RO", 2), ("DA-I", 1), ("GRA-PA", 5)])
        # GRA-PA is a commodity-head word -> not lexical -> skipped entirely.
        assert la.total_signs == 6
        assert la.by_value["ku"].count == 2
        assert la.by_value["ku"].labels == ["KU"]
        assert la.by_value["ro"].count == 2
        assert la.by_value["i"].count == 1


class TestBuildDivergence:
    def test_join_on_shared_values(self) -> None:
        la = linear_a_sign_value_counts([("KU-RO", 2), ("DA-I", 1)])
        payload = {"documents": [{"content": ".1. ku-ro da-i\n.2. ka-ko"}]}
        lb = parse_damos_frequencies(payload)
        rows = {r.value: r for r in build_lb_divergence(la, lb)}
        # Both sides total 6 signs; ku is 2x in A, 1x in B. Smoothed add-half:
        # log2((2.5/7)/(1.5/7)) = log2(2.5/1.5).
        assert rows["ku"].la_count == 2
        assert rows["ku"].lb_count == 1
        assert rows["ku"].log_ratio == pytest.approx(math.log2(2.5 / 1.5), abs=1e-12)
        # "ka"/"ko" appear only in LB -> not shared -> absent
        assert "ka" not in rows

    def test_empty_when_a_side_empty(self) -> None:
        lb = parse_damos_frequencies({"documents": [{"content": "ku-ro"}]})
        la = linear_a_sign_value_counts([])
        assert build_lb_divergence(la, lb) == []
