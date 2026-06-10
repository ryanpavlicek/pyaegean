"""Tests for aegean.io: EpiDoc (TEI) export — round-tripping through the reader — and CSV/Parquet.

The EpiDoc *writer* uses the stdlib XML module (no extra needed); the round-trip tests read the
output back with the lxml-based reader, so they skip when lxml is absent (like test_linearb)."""

from __future__ import annotations

from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.io import to_csv, to_epidoc, to_parquet, write_epidoc

FIXTURE = Path(__file__).parent / "fixtures" / "linearb-epidoc"


def _doc() -> Document:
    toks = [
        Token("A-NO-QO-TA", TokenKind.WORD, ("A", "NO", "QO", "TA"), line_no=0, position=0),
        Token("OVIS", TokenKind.LOGOGRAM, ("OVIS",), line_no=0, position=1),
        Token("30", TokenKind.NUMERAL, ("30",), line_no=0, position=2),
        Token("TO-SO", TokenKind.WORD, ("TO", "SO"), line_no=1, position=3),
        Token("50", TokenKind.NUMERAL, ("50",), line_no=1, position=4),
    ]
    return Document(
        id="KN X 1", script_id="linearb", tokens=toks, lines=[[0, 1, 2], [3, 4]],
        meta=DocumentMeta(site="Knossos", support="Tablet", name="KN X 1"),
    )


def test_to_epidoc_string_is_valid_tei() -> None:
    s = to_epidoc(_doc())
    assert s.startswith("<?xml")
    assert "http://www.tei-c.org/ns/1.0" in s  # TEI namespace declared
    assert "<idno>KN X 1</idno>" in s and "<origPlace>Knossos</origPlace>" in s
    assert s.count("<lb") == 2  # one <lb/> per physical line


def test_epidoc_corpus_roundtrip_via_reader(tmp_path: Path) -> None:
    pytest.importorskip("lxml")
    from aegean.scripts.linearb import parse_epidoc

    docs1 = parse_epidoc(FIXTURE)
    out = tmp_path / "epidoc"
    write_epidoc(Corpus(docs1, script_id="linearb"), out)
    assert (out / "KN_Sc_230.xml").exists()  # the doc id is sanitized into a filename
    assert parse_epidoc(out) == docs1  # full Document equality after write → read


def test_write_single_document_to_file(tmp_path: Path) -> None:
    pytest.importorskip("lxml")
    from aegean.scripts.linearb import parse_epidoc

    p = tmp_path / "kn_x_1.xml"
    write_epidoc(_doc(), p)
    back = parse_epidoc(p)[0]
    assert back.id == "KN X 1" and back.meta.site == "Knossos"
    assert [t.text for t in back.tokens] == ["A-NO-QO-TA", "OVIS", "30", "TO-SO", "50"]
    assert [t.kind for t in back.tokens] == [
        TokenKind.WORD, TokenKind.LOGOGRAM, TokenKind.NUMERAL, TokenKind.WORD, TokenKind.NUMERAL,
    ]
    assert back.lines == [[0, 1, 2], [3, 4]]


def test_to_csv_document_and_token_levels(tmp_path: Path) -> None:
    c = aegean.load("linearb")
    doc_csv = tmp_path / "doc.csv"
    to_csv(c, doc_csv, level="document")
    assert doc_csv.read_text(encoding="utf-8").splitlines()[0].startswith("id,script_id,site")

    tok_csv = tmp_path / "tok.csv"
    to_csv(c, tok_csv, level="token")
    assert "text" in tok_csv.read_text(encoding="utf-8").splitlines()[0]


def test_to_parquet_or_clear_error(tmp_path: Path) -> None:
    c = aegean.load("linearb")
    p = tmp_path / "lb.parquet"
    try:
        import pyarrow  # noqa: F401
    except ModuleNotFoundError:
        with pytest.raises(ImportError, match=r"pyaegean\[parquet\]"):
            to_parquet(c, p)
    else:
        to_parquet(c, p)
        assert p.exists()
