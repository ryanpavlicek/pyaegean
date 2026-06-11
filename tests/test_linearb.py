"""Tests for the Linear B script plugin (offline; sign data is bundled from the Unicode UCD)."""

from __future__ import annotations

import pathlib

import pytest

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


def test_expanded_lexicon_and_samples() -> None:
    """The WP4 expansion: every entry source-verified (curated layer + the
    Wiktionary/kaikki extract with a stated Ancient Greek equation)."""
    import json
    from pathlib import Path

    lex = json.loads(
        (Path(__file__).parents[1] / "src/aegean/data/bundled/linearb/lexicon.json")
        .read_text(encoding="utf-8")
    )
    assert len(lex) == 150
    assert all(v["lemma"] and v["gloss"] for v in lex.values())
    # extracted equations alongside the original curated ones
    assert greek_reading("e-ra-wo") == ("ἔλαιον", "olive oil")
    assert greek_reading("ku-ru-so")[0] == "χρυσός"
    assert greek_reading("po-me") == ("ποιμήν", "shepherd")  # curated layer intact

    corpus = aegean.load("linearb")
    assert len(corpus) == 18  # 2 curated + 16 sourced one-line excerpts
    assert {d.meta.site for d in corpus} >= {"Pylos", "Knossos", "Mycenae"}
    assert all(d.translations for d in corpus)  # every excerpt carries its translation


def test_restored_reading_status() -> None:
    from aegean.core.model import ReadingStatus, TokenKind

    corpus = aegean.load("linearb")
    ko = next(t for t in corpus.get("KN Ga 675").tokens if t.text == "[KO]")
    assert ko.status is ReadingStatus.RESTORED  # editor-supplied reading
    assert ko.kind is TokenKind.LOGOGRAM and ko.signs == ("KO",)


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


def test_epidoc_parse() -> None:
    pytest.importorskip("lxml")
    from aegean.analysis import balance_check
    from aegean.scripts.linearb import load_epidoc_corpus, parse_epidoc

    fixture = pathlib.Path(__file__).parent / "fixtures" / "linearb-epidoc"
    docs = parse_epidoc(fixture)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.id == "KN Sc 230"
    assert doc.meta.site == "Knossos"
    assert len(doc.lines) == 3
    texts = [t.text for t in doc.tokens]
    assert "A-NO-QO-TA" in texts  # lowercase EpiDoc normalized to uppercase
    assert "OVIS" in texts and "30" in texts
    # the to-so total reconciles (30 + 20 == 50) once parsed as a Linear B account
    corpus = load_epidoc_corpus(fixture)
    checks = balance_check(next(iter(corpus)))
    assert checks and checks[0].marker == "TO-SO" and checks[0].balances


def test_accounting_to_so_total() -> None:
    from aegean.core.numerals import (
        LINEAR_B_MARKERS,
        check_balances,
        markers_for,
        parse_account_lines,
    )

    assert markers_for("linearb").total == frozenset({"TO-SO", "TO-SA"})
    assert markers_for("lineara").total == frozenset({"KU-RO"})  # Linear A unchanged
    rows = [["A-KO-SO-TA", "OVIS", "50"], ["TU-RI-SI-JO", "OVIS", "30"], ["TO-SO", "OVIS", "80"]]
    lines = parse_account_lines(rows, LINEAR_B_MARKERS)
    assert [li.role for li in lines] == ["item", "item", "total"]
    checks = check_balances(lines, LINEAR_B_MARKERS)
    assert len(checks) == 1
    assert checks[0].marker == "TO-SO"
    assert checks[0].balances  # 50 + 30 == 80
