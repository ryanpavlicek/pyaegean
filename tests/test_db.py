"""SQLite persistence: to_sql/from_sql round-trip, full-text search, and lazy streaming
(aegean.db)."""

from __future__ import annotations

from pathlib import Path

from aegean import db
from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document,
    DocumentMeta,
    ReadingStatus,
    Sign,
    SignInventory,
    Token,
    TokenKind,
)
from aegean.core.provenance import Provenance


def _sample() -> Corpus:
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), glyphs="𐀓𐀫", line_no=0, position=0),
        Token("5", TokenKind.NUMERAL, ("5",), line_no=0, position=1),
        Token("λόγος", TokenKind.WORD, glyphs="λόγος", line_no=1, position=2,
              annotations={"lemma": "λόγος", "strongs": "3056"}),
        Token("[A-DU]", TokenKind.WORD, line_no=1, position=3,
              status=ReadingStatus.RESTORED, alt=("A-DU",)),
    ]
    doc = Document(
        id="HT13", script_id="lineara", tokens=toks, lines=[[0, 1], [2, 3]],
        glyphs="𐀓𐀫", transcription="KU-RO 5", translations=["total: 5"],
        meta=DocumentMeta(site="Haghia Triada", support="tablet", period="LMIB",
                          name="HT 13", images=("ht13.jpg",), notes=("a note",)),
    )
    doc2 = Document(id="HT14", script_id="lineara", tokens=[
        Token("A-DU", TokenKind.WORD, ("A", "DU"), line_no=0, position=0)],
        lines=[[0]], meta=DocumentMeta(site="Haghia Triada", period="LMIB"))
    inv = SignInventory(
        [Sign("KU", glyph="𐀓", codepoint=0x10053, phonetic="ku", script_id="lineara",
              attrs={"sharedWithLinearB": True})], "lineara")
    prov = Provenance(source="Synthetic", license="CC0", citation="Test (2026).",
                      url="https://example.org", notes=("subset:test",))
    return Corpus([doc, doc2], sign_inventory=inv, provenance=prov, script_id="lineara")


def test_roundtrip_preserves_everything(tmp_path: Path) -> None:
    c = _sample()
    p = tmp_path / "corpus.db"
    c.to_sql(p)
    c2 = Corpus.from_sql(p)
    assert c2.script_id == c.script_id
    assert c2.documents == c.documents          # dataclass __eq__ over tokens/lines/meta/annotations
    assert c2.provenance == c.provenance
    assert c2.sign_inventory is not None
    assert c2.sign_inventory.signs == c.sign_inventory.signs


def test_module_functions_match_methods(tmp_path: Path) -> None:
    c = _sample()
    p = tmp_path / "c.db"
    db.to_sqlite(c, p)
    assert db.from_sqlite(p).documents == c.documents


def test_search_finds_tokens(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    _sample().to_sql(p)
    hits = db.search(p, "λόγος")
    assert ("HT13", 2, "λόγος") in hits
    adu = {(d, t) for d, _pos, t in db.search(p, "A-DU")}
    assert ("HT14", "A-DU") in adu


def test_search_no_fts_exact_fallback(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    _sample().to_sql(p, fts=False)              # no FTS index -> indexed exact-match fallback
    assert any(t == "KU-RO" for _d, _pos, t in db.search(p, "KU-RO"))


def _embedding_corpus() -> Corpus:
    # D2's token PO-TO-KU-RO *embeds* D1's token KU-RO. A literal token search for KU-RO must not
    # leak PO-TO-KU-RO; the _sample() fixture has no token that embeds another, so it could not
    # catch the FTS-subsequence / LIKE-substring over-match this regression guards.
    d1 = Document(id="D1", script_id="lineara", lines=[[0]], meta=DocumentMeta(site="x"),
                  tokens=[Token("KU-RO", TokenKind.WORD, ("KU", "RO"), line_no=0, position=0)])
    d2 = Document(id="D2", script_id="lineara", lines=[[0]], meta=DocumentMeta(site="x"),
                  tokens=[Token("PO-TO-KU-RO", TokenKind.WORD, ("PO", "TO", "KU", "RO"),
                                line_no=0, position=0)])
    return Corpus([d1, d2], script_id="lineara")


def test_search_token_mode_is_exact_on_both_paths(tmp_path: Path) -> None:
    c = _embedding_corpus()
    for fts in (True, False):
        p = tmp_path / f"emb_{fts}.db"
        c.to_sql(p, fts=fts)
        hits = db.search(p, "KU-RO")                       # default mode="token"
        assert {t for _d, _pos, t in hits} == {"KU-RO"}, f"fts={fts}: leaked {hits}"
        assert {d for d, _pos, _t in hits} == {"D1"}, f"fts={fts}"   # only the exact-KU-RO doc


def test_search_substring_mode_overmatches_by_design(tmp_path: Path) -> None:
    c = _embedding_corpus()
    for fts in (True, False):
        p = tmp_path / f"sub_{fts}.db"
        c.to_sql(p, fts=fts)
        texts = {t for _d, _pos, t in db.search(p, "KU-RO", mode="substring")}
        assert texts == {"KU-RO", "PO-TO-KU-RO"}, f"fts={fts}: {texts}"


def test_stream_matches_from_sql(tmp_path: Path) -> None:
    c = _sample()
    p = tmp_path / "c.db"
    c.to_sql(p)
    streamed = list(db.stream(p))
    assert [d.id for d in streamed] == [d.id for d in c.documents]
    assert streamed == c.documents              # lazily streamed docs equal the originals


def test_real_corpus_roundtrip(tmp_path: Path) -> None:
    import aegean

    c = aegean.load("lineara")
    p = tmp_path / "lineara.db"
    c.to_sql(p)
    c2 = Corpus.from_sql(p)
    assert len(c2) == len(c) == 1721
    assert c2.documents == c.documents
    assert len(list(db.stream(p))) == 1721
