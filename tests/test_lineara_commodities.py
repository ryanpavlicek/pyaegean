"""Linear A commodity catalog + lexical-word filter (scripts.lineara.commodities).

Ported from the Linear A Research Workbench; the lexical-word cases mirror
``src/lib/surprisal.test.ts``'s ``isLexicalWord`` suite and the commodity-head
behavior matches ``src/data/commodities.ts``.
"""

from __future__ import annotations

from aegean.scripts.lineara.commodities import (
    COMMODITIES,
    commodity_head,
    is_lexical_word,
    is_undeciphered_logogram,
)


class TestCommodityHead:
    def test_known_heads_and_modifiers(self) -> None:
        assert commodity_head("GRA") == "GRA"
        assert commodity_head("OLE+U") == "OLE"  # ligature modifier stripped
        assert commodity_head("VIR+[?]") == "VIR"  # bracketed uncertainty
        assert commodity_head("OVISm") == "OVIS"  # sex marker
        assert commodity_head("OVISf") == "OVIS"

    def test_non_commodities(self) -> None:
        assert commodity_head("KU") is None
        assert commodity_head("KU-RO") is None  # hyphenated word, not a logogram
        assert commodity_head("*301") is None


class TestUndecipheredLogogram:
    def test_starred_numbers(self) -> None:
        assert is_undeciphered_logogram("*301") is True
        assert is_undeciphered_logogram("*405") is True
        assert is_undeciphered_logogram("GRA") is False
        assert is_undeciphered_logogram("KU-RO") is False


class TestIsLexicalWord:
    def test_accepts_syllabic_words(self) -> None:
        # syllabic words, including ones with sub-400 starred signs
        assert is_lexical_word("KU-RO") is True
        assert is_lexical_word("A-TA-I-*301-WA-JA") is True
        assert is_lexical_word("A-SA-SA-RA-ME") is True

    def test_rejects_logogram_chains_and_damage(self) -> None:
        assert is_lexical_word("*405-VS-*906") is False  # *400+ vessel series
        assert is_lexical_word("*307+*387-GRA+QE") is False  # ligature
        assert is_lexical_word("HIDE+[?]-*328") is False  # bracketed damage
        assert is_lexical_word("GRA-PA") is False  # commodity head part
        assert is_lexical_word("*301-*306") is False  # pure starred chain
        assert is_lexical_word("KU") is False  # single sign


def test_catalog_shape() -> None:
    # A faithful port of the curated catalog: the heads the filter keys off.
    assert {"GRA", "OLE", "VIN", "OVIS", "VIR", "TELA"} <= set(COMMODITIES)
    assert COMMODITIES["GRA"].category == "agricultural"
    assert COMMODITIES["OVIS"].category == "livestock"
