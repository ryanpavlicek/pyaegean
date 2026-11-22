"""Regression tests for Greek and syllabic philological correctness (§13)."""

from __future__ import annotations

import pathlib

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind


def test_iota_subscript_preserved_in_word_folding_and_dodson() -> None:
    from aegean.geo import _fold_word
    from aegean.greek.koine import DodsonEntry, DodsonLexicon, _exact_key

    assert _fold_word("ἐκκλησίᾳ") != _fold_word("ἐκκλησίαι")
    assert _fold_word("Ἐκκλησίᾳ") == _fold_word("ἐκκλησίᾳ")
    assert _fold_word("ΛΌΓΟΣ") == _fold_word("λόγος")

    assert _exact_key("ἐκκλησίᾳ") != _exact_key("ἐκκλησίαι")
    lex = DodsonLexicon(
        {
            "1": DodsonEntry("1", "ἐκκλησίᾳ", "to an assembly", "to an assembly"),
            "2": DodsonEntry("2", "ἐκκλησίαι", "assemblies", "assemblies"),
        }
    )
    assert lex.lookup("ἐκκλησίᾳ") == lex.by_strongs("1")
    assert lex.lookup("ἐκκλησίαι") == lex.by_strongs("2")


def test_mcp_geo_map_preserves_iota_subscript_and_normalizes_sites(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean import mcp_server

    doc_dat = Document(
        id="d1",
        script_id="greek",
        tokens=[Token("ἐκκλησίᾳ", TokenKind.WORD, (), None, 0, 0)],
        lines=[[0]],
        meta=DocumentMeta(site="Knossos\n"),
    )
    doc_nom = Document(
        id="d2",
        script_id="greek",
        tokens=[Token("ἐκκλησίαι", TokenKind.WORD, (), None, 0, 0)],
        lines=[[0]],
        meta=DocumentMeta(site="Pylos"),
    )
    corpus = Corpus([doc_dat, doc_nom], script_id="greek")
    monkeypatch.setattr(mcp_server, "_load_corpus", lambda _name: (corpus, None))

    res_dat = mcp_server.geo_sites("greek", word="ἐκκλησίᾳ")
    assert [r["site"] for r in res_dat["sites"]] == ["Knossos"]
    res_nom = mcp_server.geo_sites("greek", word="ἐκκλησίαι")
    assert [r["site"] for r in res_nom["sites"]] == ["Pylos"]


def test_morphology_imperfect_2sg_and_iota_subscript_verbs() -> None:
    from aegean.greek.morphology import analyze

    impf = [a for a in analyze("ἔλυες") if a.pos == "VERB"]
    assert any(
        a.tense == "impf" and a.voice == "act" and a.mood == "ind"
        and a.person == "2" and a.number == "sg" and a.lemma == "λυω"
        for a in impf
    )

    stem_sub = [a for a in analyze("ᾄδεις") if a.pos == "VERB"]
    assert any(a.tense == "pres" and a.person == "2" and a.number == "sg" for a in stem_sub)

    subj = [a for a in analyze("λύῃς") if a.pos == "VERB"]
    assert any(
        a.tense == "pres" and a.mood == "subj" and a.person == "2" and a.number == "sg"
        and a.lemma == "λυω"
        for a in subj
    )
    # Plain -ης (no iota subscript) stays nominal, not subjunctive verb.
    assert not any(a.pos == "VERB" for a in analyze("τιμῆς"))
    # Dative singulars ending in iota subscript stay nominal.
    assert not any(a.pos == "VERB" for a in analyze("λόγῳ"))
    assert not any(a.pos == "VERB" for a in analyze("ἀρχῇ"))


def test_sandhi_grave_crasis_and_rough_breathing_crasis() -> None:
    from aegean.greek.sandhi import resolve_sandhi

    r_grave = resolve_sandhi("κἀγὼ")
    assert r_grave.kind == "crasis" and not r_grave.uncertain
    assert r_grave.words == ("καί", "ἐγώ")

    for surface, expected in (
        ("ἁνήρ", ("ὁ", "ἀνήρ")),
        ("ἁνὴρ", ("ὁ", "ἀνήρ")),
        ("ἅνθρωπος", ("ὁ", "ἄνθρωπος")),
    ):
        r = resolve_sandhi(surface)
        assert r.kind == "crasis" and not r.uncertain, surface
        assert r.words == expected, surface


def test_tagger_form_features_not_poisoned_by_treebank_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek import tagger, treebank
    from aegean.greek.morphology import Analysis, _bare

    class _FakeLexicon:
        def analyze(self, word: str) -> tuple[Analysis, ...]:
            return (Analysis(lemma=word, pos="INTJ"),)

    tagger._form_features.cache_clear()
    try:
        monkeypatch.setattr(treebank, "active", lambda: _FakeLexicon())
        feats_with_tb = tagger._form_features("λύεις", _bare("λύεις"))
        assert "rule=VERB" in feats_with_tb
        assert "rule=INTJ" not in feats_with_tb
    finally:
        tagger._form_features.cache_clear()


def test_neural_pos_tags_segments_sentences_and_uses_windowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from aegean.greek import joint, pos

    calls: list[tuple[list[str], str]] = []

    def _fake_analyze(words: list[str], *, long_input: str = "strict", **_kw: object) -> object:
        calls.append((list(words), long_input))
        if len(calls) == 2 and long_input == "strict":
            raise joint.NeuralInputTooLongError(
                input_tokens=len(words), analyzed_tokens=2, max_subwords=256
            )
        return SimpleNamespace(upos=tuple("PUNCT" if w == "." else "NOUN" for w in words))

    monkeypatch.setattr(joint, "active", lambda: object())
    monkeypatch.setattr(joint, "analyze_sentence", _fake_analyze)

    out = pos.pos_tags("ὁ ἄνθρωπος λέγει. ὁ θεὸς ἀκούει.")
    assert calls == [
        (["ὁ", "ἄνθρωπος", "λέγει", "."], "strict"),
        (["ὁ", "θεὸς", "ἀκούει", "."], "strict"),
        (["ὁ", "θεὸς", "ἀκούει", "."], "windowed"),
    ]
    assert [tok for tok, _tag in out] == [
        "ὁ", "ἄνθρωπος", "λέγει", ".", "ὁ", "θεὸς", "ἀκούει", ".",
    ]


def test_hiatus_combining_marks_and_muta_cum_liquida() -> None:
    from aegean.greek import syllabify, to_ipa
    from aegean.greek.meter import _Item, _is_diphthong, _is_muta_cum_liquida, _items

    assert syllabify("ὄις") == ["ὄ", "ις"]
    assert syllabify("ἀυτή") == ["ἀ", "υ", "τή"]
    assert syllabify("πάις") == ["πά", "ις"]
    assert not _is_diphthong("ὄ", "ι")
    assert not _is_diphthong("ἀ", "υ")
    assert _is_diphthong("α", "ὐ")

    assert to_ipa("ὄις", "attic") == "ois"
    assert to_ipa("«ἡμέρα»", "attic") == "«hɛːmera»"

    # Koine αυ/ευ devoicing before voiceless consonants vs voiced environments
    assert to_ipa("αὐτός", "koine") == "aftos"
    assert to_ipa("εὐχαριστῶ", "koine") == "efxaristo"
    assert to_ipa("αὐλή", "koine") == "avli"
    assert to_ipa("εὐαγγέλιον", "koine") == "evaŋɣelion"

    # Combining marks (macron + acute, underdot) stay attached to their vowel, never consonants
    items = _items("\u1fb1\u0301\u03c1\u03b1 \u03b1\u0323\u03bd")
    assert all(it.base != "" for it in items)
    assert [it.is_vowel for it in items] == [True, False, True, True, False]

    # Muta cum liquida applies only within one word, not across a word boundary
    same_word = [
        _Item(False, "π", "π", 0, False),
        _Item(False, "ρ", "ρ", 0, False),
    ]
    cross_word = [
        _Item(False, "κ", "κ", 0, False),
        _Item(False, "ρ", "ρ", 1, True),
    ]
    assert _is_muta_cum_liquida(same_word) is True
    assert _is_muta_cum_liquida(cross_word) is False


def test_cypriot_single_signs_and_latin_apparatus() -> None:
    from aegean.scripts.cypriot.loader import classify

    tok = classify("ta", 0, 0)
    assert tok.kind is TokenKind.WORD and tok.signs == ("ta",)

    tok_dot = classify("se.", 0, 1)
    assert tok_dot.kind is TokenKind.WORD and tok_dot.signs == ("se",)
    assert tok_dot.status is ReadingStatus.UNCLEAR

    linea = classify("linea", 0, 2)
    assert linea.kind is TokenKind.SEPARATOR and linea.signs == ()
    assert "apparatus" in linea.annotations

    evanidus = classify("evanidus", 0, 3)
    assert evanidus.kind is TokenKind.UNKNOWN and evanidus.signs == ()
    assert evanidus.status is ReadingStatus.LOST
    assert "apparatus" in evanidus.annotations


def test_syllabic_phonetic_overrides_normalize_keys() -> None:
    from aegean.scripts.cypriot.phonetic import word_to_phonetic as cyp_phon
    from aegean.scripts.lineara.phonetic import word_to_phonetic as la_phon
    from aegean.scripts.linearb.phonetic import word_to_phonetic as lb_phon

    assert cyp_phon("PA-SI", overrides={"pa": "X"}) == "Xsi"
    assert la_phon("KU-RO", overrides={"ku": "Q"}) == "Qro"
    assert lb_phon("a₂-ro", overrides={"a₂": "ha"}) == "haro"


def test_linearb_epidoc_qualifiers_nested_elements_and_loader_empty_signs(
    tmp_path: pathlib.Path,
) -> None:
    from aegean.scripts.linearb.epidoc import parse_epidoc
    from aegean.scripts.linearb.loader import classify

    assert classify("-wa--na-", 0, 0).signs == ("wa", "na")

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>KN Da 1</title></titleStmt></fileDesc></teiHeader>
  <text><body>
    <w>wa-<g>na</g>-ka</w>
    <g>OVIS:m</g>
    <num>100</num>
  </body></text>
</TEI>
"""
    p = tmp_path / "kn_da_1.xml"
    p.write_text(xml, encoding="utf-8")
    docs = parse_epidoc(p)
    assert len(docs) == 1
    toks = docs[0].tokens
    assert [t.text for t in toks] == ["WA-NA-KA", "OVIS:m", "100"]
    assert [t.kind for t in toks] == [TokenKind.WORD, TokenKind.LOGOGRAM, TokenKind.NUMERAL]
