"""Tests for aegean.io: EpiDoc (TEI) export — round-tripping through the reader — and CSV/Parquet.

The EpiDoc *writer* uses the stdlib XML module (no extra needed); the round-trip tests read the
output back with the lxml-based reader, so they skip when lxml is absent (like test_linearb)."""

from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from aegean.io import to_csv, to_epidoc, to_parquet, write_epidoc

FIXTURE = Path(__file__).parent / "fixtures" / "linearb-epidoc"

# Pinned EpiDoc release; the schema is fetched + cached, and the validation test skips if unreachable.
_EPIDOC_RNG_URL = "https://epidoc.stoa.org/schema/9.4/tei-epidoc.rng"


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
    assert 'type="edition"' in s  # EpiDoc's required edition division
    assert "<publicationStmt>" in s  # required, in order, by TEI's fileDesc
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


@pytest.fixture(scope="session")
def epidoc_rng():  # type: ignore[no-untyped-def]
    """A compiled EpiDoc RelaxNG validator, fetched once + cached; skips if it can't be fetched."""
    etree = pytest.importorskip("lxml.etree")
    cache = Path(tempfile.gettempdir()) / "pyaegean-tei-epidoc-9.4.rng"
    if not cache.exists():
        try:
            with urllib.request.urlopen(_EPIDOC_RNG_URL, timeout=30) as resp:
                cache.write_bytes(resp.read())
        except Exception as exc:  # offline / CI without network — skip, don't fail
            pytest.skip(f"EpiDoc schema unavailable: {exc}")
    try:
        return etree.RelaxNG(etree.parse(str(cache)))
    except Exception as exc:  # pragma: no cover - corrupt cache
        cache.unlink(missing_ok=True)
        pytest.skip(f"EpiDoc schema unusable: {exc}")


def test_epidoc_export_validates_against_epidoc_schema(epidoc_rng) -> None:  # type: ignore[no-untyped-def]
    """The export is real EpiDoc: it validates against the official EpiDoc RelaxNG schema."""
    from lxml import etree

    samples = [
        to_epidoc(_doc()),                                  # hand-built Linear B doc
        to_epidoc(aegean.load("lineara").get("HT13")),      # a bundled Linear A tablet
    ]
    for xml in samples:
        tree = etree.fromstring(xml.encode("utf-8"))
        assert epidoc_rng.validate(tree), epidoc_rng.error_log


def test_editorial_status_roundtrips(tmp_path: Path) -> None:
    """ReadingStatus survives write→read: restored→<supplied>, unclear→<unclear>, and back."""
    pytest.importorskip("lxml")
    from aegean.scripts.linearb import parse_epidoc

    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), line_no=0, position=0,
              status=ReadingStatus.CERTAIN),
        Token("DA-RO", TokenKind.WORD, ("DA", "RO"), line_no=0, position=1,
              status=ReadingStatus.RESTORED),
        Token("OVIS", TokenKind.LOGOGRAM, ("OVIS",), line_no=0, position=2,
              status=ReadingStatus.UNCLEAR),  # a <g> can't carry markup → emitted as <seg>
    ]
    doc = Document(id="KN X 9", script_id="linearb", tokens=toks, lines=[[0, 1, 2]],
                   meta=DocumentMeta(site="Knossos"))
    xml = to_epidoc(doc)
    assert "<supplied" in xml and "<unclear>" in xml  # editorial markup is emitted

    p = tmp_path / "kn_x_9.xml"
    p.write_text(xml, encoding="utf-8")
    back = parse_epidoc(p)[0]
    assert [t.status for t in back.tokens] == [
        ReadingStatus.CERTAIN, ReadingStatus.RESTORED, ReadingStatus.UNCLEAR,
    ]


def test_reading_status_survives_json_roundtrip() -> None:
    """The lossless JSON round-trip preserves a token's ReadingStatus."""
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), line_no=0, position=0),
        Token("DA-RO", TokenKind.WORD, ("DA", "RO"), line_no=0, position=1,
              status=ReadingStatus.RESTORED),
    ]
    doc = Document(id="X1", script_id="linearb", tokens=toks, lines=[[0, 1]])
    back = Corpus.from_json(Corpus([doc], script_id="linearb").to_json())
    assert [t.status for t in back.get("X1").tokens] == [
        ReadingStatus.CERTAIN, ReadingStatus.RESTORED,
    ]
