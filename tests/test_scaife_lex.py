"""Tests for the Scaife JSONL dictionary backend (Middle Liddell / Cunliffe)."""

from __future__ import annotations

from pathlib import Path

from aegean import greek
from aegean.greek import scaife_lex
from aegean.greek.lexicons import LexiconInfo

FIXTURE = Path(__file__).parent / "fixtures" / "scaife" / "entries.jsonl"


def _lex() -> scaife_lex.ScaifeLexicon:
    data = scaife_lex.index_from_files([FIXTURE])
    info = LexiconInfo(
        id="fixture", name="t", scope="x", license="y", source="z", hosted=True
    )
    return scaife_lex.ScaifeLexicon(info, data)


def test_parse_both_jsonl_shapes():
    lex = _lex()
    assert len(lex) == 3
    # Cunliffe-style direct "definition"
    assert lex.gloss("λόγος") == "λόγος: word, speech, account"
    # Middle-Liddell-style nested data.content, with the leading headword line dropped
    assert lex.gloss("θεός") == "θεός: God, a god"


def test_lookup_returns_lexentry():
    lex = _lex()
    e = lex.lookup("ἄνθρωπος")
    assert e is not None
    assert e.headword == "ἄνθρωπος"
    assert e.lexicon == "fixture"
    assert "human being" in e.body


def test_accent_folding_and_miss():
    lex = _lex()
    assert lex.gloss("λογος") is not None  # accent-folded hit
    assert lex.lookup("ξυνωρίς") is None  # not in the fixture


def test_dictionaries_registered():
    ids = {i.id: i.scope for i in greek.lexica()}
    assert ids.get("middle-liddell") == "classical"
    assert ids.get("cunliffe") == "Homeric"
