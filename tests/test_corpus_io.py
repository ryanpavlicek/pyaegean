"""Tests for the Corpus lossless JSON round-trip (to_json/from_json/from_dict) and the
first-class Corpus.query() predicate API added in 0.6.0."""

from __future__ import annotations

import json
from pathlib import Path

import aegean
from aegean.analysis import FilterRow
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Sign, SignInventory, Token, TokenKind
from aegean.core.provenance import Provenance


def _sample_corpus() -> Corpus:
    """A small corpus exercising every token kind, multiple lines, image refs, sign attrs,
    and a fully-populated provenance — i.e. the fields the lossy to_dict() would drop."""
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), glyphs="𐀓𐀫", line_no=0, position=0),
        Token("5", TokenKind.NUMERAL, ("5",), line_no=0, position=1),
        Token("GRA", TokenKind.LOGOGRAM, ("GRA",), line_no=0, position=2),
        Token("𐄁", TokenKind.SEPARATOR, ("𐄁",), line_no=1, position=3),
        Token("PA-I-TO", TokenKind.WORD, ("PA", "I", "TO"), line_no=1, position=4),
    ]
    doc = Document(
        id="HT13", script_id="lineara", tokens=toks, lines=[[0, 1, 2], [3, 4]],
        glyphs="𐀓𐀫", transcription="KU-RO 5 GRA", translations=["total: 5 (illustrative)"],
        meta=DocumentMeta(
            site="Haghia Triada", support="tablet", scribe="s1", findspot="villa",
            period="LMIB", name="HT 13", images=("ht13a.jpg", "ht13b.jpg"),
        ),
    )
    inv = SignInventory(
        [Sign("KU", glyph="𐀓", codepoint=0x10053, phonetic="ku", script_id="lineara",
              attrs={"sharedWithLinearB": True, "altGlyphs": ["𐀓"]})],
        "lineara",
    )
    prov = Provenance(source="Synthetic", license="CC0", citation="Test (2026).",
                      url="https://example.org", notes=("a note", "another"))
    return Corpus([doc], sign_inventory=inv, provenance=prov, script_id="lineara")


def test_roundtrip_preserves_everything() -> None:
    c = _sample_corpus()
    c2 = Corpus.from_json(c.to_json())
    assert c2.script_id == c.script_id
    assert c2.documents == c.documents          # dataclass __eq__ over tokens/lines/meta/...
    assert c2.provenance == c.provenance        # frozen dataclass __eq__ (incl. notes tuple)
    assert c2.sign_inventory is not None
    assert c2.sign_inventory.signs == c.sign_inventory.signs


def test_roundtrip_real_corpus() -> None:
    c = aegean.load("lineara")
    c2 = Corpus.from_json(c.to_json(indent=None))
    assert len(c2) == len(c) == 1721
    assert c2.documents == c.documents
    assert c2.sign_inventory is not None and c.sign_inventory is not None
    assert c2.sign_inventory.signs == c.sign_inventory.signs
    assert c2.provenance == c.provenance


def test_to_json_file_and_string_sources(tmp_path: Path) -> None:
    c = _sample_corpus()
    p = tmp_path / "corpus.json"
    assert c.to_json(p) is None and p.exists()              # writing returns None
    assert Corpus.from_json(p).documents == c.documents      # Path source
    assert Corpus.from_json(str(p)).documents == c.documents  # path-like string source
    assert Corpus.from_json(p.read_text(encoding="utf-8")).documents == c.documents  # JSON string


def test_to_json_is_lossless_where_to_dict_is_not() -> None:
    c = _sample_corpus()
    full = json.loads(c.to_json())
    kinds = [t["kind"] for t in full["documents"][0]["tokens"]]
    assert kinds == ["word", "numeral", "logogram", "separator", "word"]  # full stream
    assert full["documents"][0]["lines"] == [[0, 1, 2], [3, 4]]            # physical lines
    assert full["signInventory"]["signs"][0]["attrs"]["sharedWithLinearB"] is True
    # by contrast, to_dict() keeps only WORD text and drops the rest
    assert c.to_dict()["documents"][0]["words"] == ["KU-RO", "PA-I-TO"]


def test_query_inscription_scope_matches_filter() -> None:
    c = aegean.load("lineara")
    via_query = {d.id for d in c.query([FilterRow("site-is", "Haghia Triada")]).inscriptions}
    via_filter = {d.id for d in c.filter(site="Haghia Triada")}
    assert via_query and via_query == via_filter


def test_query_word_output() -> None:
    c = aegean.load("lineara")
    prefix = c.word_frequencies()[0][0].split("-")[0]  # first sign of the top word — present
    words = c.query([FilterRow("word-prefix", prefix)], output="words").words
    assert words and all(w.upper().startswith(prefix.upper()) for w, _ in words)
