"""The bundled Greek seed corpus and the Greek script plugin."""

from __future__ import annotations

import aegean
from aegean.core.model import TokenKind


def test_greek_registered():
    assert "greek" in aegean.registered_scripts()


def test_load_greek_corpus():
    corpus = aegean.load("greek")
    assert len(corpus) == 5
    iliad = corpus.get("iliad-1.1")
    assert iliad is not None
    assert [t.text for t in iliad.words] == [
        "μῆνιν", "ἄειδε", "θεὰ", "Πηληϊάδεω", "Ἀχιλῆος"
    ]
    assert iliad.meta.scribe == "Homer"
    assert iliad.meta.period == "Archaic (epic)"


def test_greek_provenance():
    corpus = aegean.load("greek")
    assert corpus.provenance is not None
    assert "public domain" in corpus.provenance.license.lower()


def test_greek_inventory():
    script = aegean.get_script("greek")
    inv = script.sign_inventory
    assert len(inv) == 25  # 24 letters + final sigma
    assert inv.by_glyph("α").label == "alpha"
    assert inv.by_glyph("ω").phonetic == "ɔː"


def test_greek_script_tokenize_and_nlp():
    script = aegean.get_script("greek")
    toks = script.tokenize("ἐν ἀρχῇ, ἦν")
    assert [t.kind for t in toks].count(TokenKind.WORD) == 3
    # the script exposes the NLP pipeline as a capability
    assert script.nlp.betacode_to_unicode("lo/gos") == "λόγος"  # type: ignore[attr-defined]


def test_greek_word_frequencies():
    corpus = aegean.load("greek")
    freqs = dict(corpus.word_frequencies())
    # "λόγος" occurs twice in the John 1:1 sample
    assert freqs.get("λόγος") == 2
