"""Tests for the Linear B script plugin (offline; sign data is bundled from the Unicode UCD)."""

from __future__ import annotations

import aegean
from aegean.core.script import get_script
from aegean.scripts.linearb import gloss, greek_reading, word_to_phonetic
from aegean.scripts.linearb.inventory import linear_b_inventory


def test_registered() -> None:
    assert "linearb" in aegean.registered_scripts()
    assert get_script("linearb").name == "Linear B"


def test_sign_inventory() -> None:
    signs = list(linear_b_inventory())
    assert len(signs) == 211
    syllabograms = [s for s in signs if s.attrs.get("signClass") == "syllabogram"]
    assert len(syllabograms) == 74
    assert all(s.phonetic for s in syllabograms)  # deciphered: every syllabogram has a value
    a = next(s for s in signs if s.label == "A")
    assert a.phonetic == "a"
    assert a.attrs["bennett"] == "B008"
    wine = next(s for s in signs if s.attrs.get("commodity") == "WINE")
    assert wine.attrs["signClass"] == "ideogram"


def test_word_to_phonetic() -> None:
    # qa-si-re-u → gʷasileus (the labiovelar, ancestor of βασιλεύς)
    assert word_to_phonetic("QA-SI-RE-U") == "kwasireu"
    assert word_to_phonetic("PO-ME") == "pome"           # ποιμήν, "shepherd"
    assert word_to_phonetic("WA-NA-KA") == "wanaka"       # ϝάναξ, "king"
    assert word_to_phonetic("TI-RI-PO-DE") == "tiripode"  # τρίποδε, "two tripods"


def test_greek_bridge() -> None:
    assert greek_reading("PO-ME") == ("ποιμήν", "shepherd")
    assert greek_reading("po-me") == ("ποιμήν", "shepherd")  # case-insensitive
    lemma, _ = greek_reading("QA-SI-RE-U")  # gʷasileus → βασιλεύς
    assert lemma == "βασιλεύς"
    assert gloss("WO-NO") == "wine"  # οἶνος
    assert greek_reading("XY-ZZ") is None


def test_corpus_loads_and_classifies() -> None:
    corpus = aegean.load("linearb")
    assert len(corpus) >= 2
    doc = next(d for d in corpus if d.id == "PY Er 312")
    kinds = {t.text: t.kind.name for t in doc.tokens}
    assert kinds["GRA"] == "LOGOGRAM"          # the grain ideogram
    assert kinds["30"] == "NUMERAL"
    assert kinds["WA-NA-KA-TE-RO"] == "WORD"
