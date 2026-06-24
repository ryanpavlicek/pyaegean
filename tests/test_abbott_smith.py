"""Tests for the Abbott-Smith TEI dictionary backend (NT)."""

from __future__ import annotations

from pathlib import Path

from aegean import greek
from aegean.greek import abbott_smith
from aegean.greek.lexindex import IndexLexicon

FIXTURE = Path(__file__).parent / "fixtures" / "abbott_smith" / "sample.tei.xml"


def _lex() -> IndexLexicon:
    return IndexLexicon(abbott_smith._INFO, abbott_smith.index_from_tei(FIXTURE))


def test_parse_glosses_joined():
    lex = _lex()
    assert len(lex) == 2
    g = lex.gloss("λόγος")
    assert g is not None
    assert g.startswith("λόγος:")
    assert "a word" in g and "a saying" in g and "statement" in g
    assert lex.gloss("ἀγάπη") == "ἀγάπη: love"


def test_lookup_lexentry():
    e = _lex().lookup("ἀγάπη")
    assert e is not None
    assert e.headword == "ἀγάπη"
    assert e.lexicon == "abbott-smith"


def test_registered_in_registry():
    scopes = {i.id: i.scope for i in greek.lexica()}
    assert scopes.get("abbott-smith") == "NT"
