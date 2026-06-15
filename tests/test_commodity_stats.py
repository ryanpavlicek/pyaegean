"""Sign-bigram PMI and commodity/ideogram line statistics.

Ported from the workbench's Sign-Transitions, Commodity Catalog, and Semantic
Classifier modules; anchors are the worked examples from that source.
"""

from __future__ import annotations

import pytest

from aegean.analysis.collocation import sign_bigram_pmi, sign_bigram_pmis
from aegean.analysis.commodity import (
    ideogram_group_exclusivity,
    line_cooccurrence_pmi,
)


class TestSignBigramPmi:
    def test_core(self) -> None:
        assert sign_bigram_pmi(3, 4, 3, 6) == pytest.approx(0.5849625007211562, abs=1e-12)
        assert sign_bigram_pmi(1, 4, 3, 6) == pytest.approx(-1.0, abs=1e-12)
        assert sign_bigram_pmi(0, 4, 3, 6) is None  # never-attested pair
        assert sign_bigram_pmi(2, 0, 3, 6) is None  # zero marginal

    def test_corpus_wrapper(self) -> None:
        pmis = sign_bigram_pmis([("a-b", 3), ("a-c", 1), ("b-c", 2)])
        assert pmis[("a", "b")] == pytest.approx(0.5849625007211562, abs=1e-12)
        assert pmis[("a", "c")] == pytest.approx(-1.0, abs=1e-12)
        assert pmis[("b", "c")] == pytest.approx(1.0, abs=1e-12)
        assert ("b", "a") not in pmis  # never attested -> absent

    def test_subscript_folding(self) -> None:
        # RA₂ folds to RA2, so these merge into one left-sign.
        pmis = sign_bigram_pmis([("RA₂-XO", 1), ("RA2-XO", 1)])
        assert ("RA2", "XO") in pmis


class TestLineCooccurrencePmi:
    def test_worked_example(self) -> None:
        lines = [
            ["GRA", "A-B", "5"],
            ["KU-RO", "10"],
            ["GRA", "A-B", "KU-RO"],
            ["VIN", "C-D"],
        ]
        result = line_cooccurrence_pmi(lines, "GRA")
        # KU-RO shares only one line with GRA (joint=1) -> filtered by min_joint=2
        assert result == [("A-B", pytest.approx(1.0, abs=1e-12))]

    def test_empty_when_commodity_absent(self) -> None:
        assert line_cooccurrence_pmi([["X-Y", "Z-W"]], "GRA") == []


class TestIdeogramGroupExclusivity:
    def test_worked_example(self) -> None:
        rows = {
            (r.group, r.word): r
            for r in ideogram_group_exclusivity(
                [["GRA", "ku-ro", "da-i"], ["OLE+U", "ku-ro", "ki-ro"], ["GRA", "da-i"]]
            )
        }
        assert rows[("GRA", "da-i")].exclusivity == pytest.approx(1.0, abs=1e-12)
        assert rows[("GRA", "da-i")].count == 2
        assert rows[("GRA", "ku-ro")].exclusivity == pytest.approx(0.5, abs=1e-12)
        assert rows[("OLE", "ku-ro")].exclusivity == pytest.approx(0.5, abs=1e-12)
        assert rows[("OLE", "ki-ro")].exclusivity == pytest.approx(1.0, abs=1e-12)
        # OLE+U folds into the OLE group; gloss carried from the catalog.
        assert rows[("OLE", "ku-ro")].gloss == "olive oil"

    def test_exclusivity_sums_to_one_per_word(self) -> None:
        rows = ideogram_group_exclusivity(
            [["GRA", "ku-ro"], ["OLE", "ku-ro"]]
        )
        by_word: dict[str, float] = {}
        for r in rows:
            by_word[r.word] = by_word.get(r.word, 0.0) + r.exclusivity
        assert by_word["ku-ro"] == pytest.approx(1.0, abs=1e-12)
