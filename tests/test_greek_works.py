"""The Perseus/First1KGreek work loader: TEI parsing + edition selection (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.core.model import TokenKind
from aegean.scripts.greek.perseus import (
    _parse_ref,
    _work_dir,
    parse_tei_work,
    pick_edition,
)

FIXTURE = Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml"


def test_parse_tei_work_structure():
    title, author, docs = parse_tei_work(FIXTURE.read_bytes(), "tlg9999.tlg001")
    assert title == "Ἔργον"  # the grc title wins over the Latin one
    assert author == "Testius"
    assert [d.id for d in docs] == ["tlg9999.tlg001:1", "tlg9999.tlg001:2"]
    assert docs[0].meta.name == "Ἔργον — book 1"


def test_parse_tei_verse_lines_and_note_exclusion():
    _, _, docs = parse_tei_work(FIXTURE.read_bytes(), "w")
    book = docs[0]
    assert len(book.lines) == 2  # one physical line per <l>
    assert [t.text for t in book.line_tokens[0]] == ["μῆνιν", "ἄειδε", "θεὰ"]
    line2 = " ".join(t.text for t in book.line_tokens[1])
    assert "editorial" not in line2 and "exclude" not in line2  # <note> dropped
    assert "μυρία" in line2


def test_parse_tei_prose_blocks_and_bibl_exclusion():
    _, _, docs = parse_tei_work(FIXTURE.read_bytes(), "w")
    prose = docs[1]
    assert len(prose.lines) == 2  # one per <p>
    p1 = [t.text for t in prose.line_tokens[0]]
    assert p1[:5] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]
    assert "Ev" not in p1 and "Jo" not in p1  # <bibl> dropped
    assert any(t.kind is TokenKind.PUNCT for t in prose.tokens)  # punctuation kept


def test_notes_carried_into_meta():
    # <note>/<bibl> are excluded from the running text but kept in meta.notes.
    _, _, docs = parse_tei_work(FIXTURE.read_bytes(), "w")
    book, chapter = docs
    assert any("editorial note" in n for n in book.meta.notes)   # the <note>
    assert any("Ev. Jo." in n for n in chapter.meta.notes)        # the <bibl>
    assert all("editorial" not in t.text for t in book.tokens)    # still out of the text


def test_ref_selects_a_textpart():
    _, _, docs = parse_tei_work(FIXTURE.read_bytes(), "w", ref="1")
    assert len(docs) == 1
    assert docs[0].id == "w:1" and docs[0].meta.name == "Ἔργον — 1"
    assert len(docs[0].lines) == 2


def test_ref_selects_a_verse_line_range():
    # book 1, line 1 only (book 1 has no nested div, so the trailing 1 is a line)
    _, _, one = parse_tei_work(FIXTURE.read_bytes(), "w", ref="1.1")
    assert len(one[0].lines) == 1
    assert [t.text for t in one[0].tokens[:3]] == ["μῆνιν", "ἄειδε", "θεὰ"]
    # a range over both lines
    _, _, both = parse_tei_work(FIXTURE.read_bytes(), "w", ref="1.1-1.2")
    assert len(both[0].lines) == 2 and both[0].id == "w:1.1-1.2"


def test_ref_selects_a_nested_div():
    # "2" addresses the prose chapter (its own top-level div); two <p> blocks
    _, _, docs = parse_tei_work(FIXTURE.read_bytes(), "w", ref="2")
    assert docs[0].id == "w:2" and len(docs[0].lines) == 2


def test_ref_with_no_match_raises():
    with pytest.raises(ValueError, match="selected no text"):
        parse_tei_work(FIXTURE.read_bytes(), "w", ref="99")


def test_ref_no_match_error_lists_sections():
    with pytest.raises(ValueError, match="sections here"):
        parse_tei_work(FIXTURE.read_bytes(), "w", ref="99")


@pytest.mark.parametrize("bad", ["1..2", ".1", "1.", "-", "1-", "-1", "1--2", "   "])
def test_parse_ref_rejects_malformed(bad):
    with pytest.raises(ValueError):
        _parse_ref(bad)


def test_parse_ref_rejects_descending_range():
    with pytest.raises(ValueError, match="descending"):
        _parse_ref("1.50-1.1")


def test_parse_ref_valid_forms():
    assert _parse_ref("1") == (["1"], ["1"])
    assert _parse_ref("1.2") == (["1", "2"], ["1", "2"])
    assert _parse_ref("1.1-1.50") == (["1", "1"], ["1", "50"])
    assert _parse_ref("1.1-50") == (["1", "1"], ["1", "50"])


def test_notes_survive_the_json_round_trip():
    import aegean
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind

    doc = Document(
        id="w:1", script_id="greek",
        tokens=[Token("λόγος", TokenKind.WORD)], lines=[[0]],
        meta=DocumentMeta(name="X", notes=("a scholion", "Ev. Jo. 1.1")),
    )
    c = aegean.Corpus([doc], script_id="greek")
    back = aegean.Corpus.from_json(c.to_json())
    assert back.documents[0].meta.notes == ("a scholion", "Ev. Jo. 1.1")


def test_parse_tei_requires_body():
    with pytest.raises(ValueError, match="no TEI <body>"):
        parse_tei_work(b"<TEI xmlns='http://www.tei-c.org/ns/1.0'/>", "w")


def test_pick_edition_prefers_highest_greek():
    names = [
        "__cts__.xml",
        "tlg0012.tlg001.perseus-eng3.xml",
        "tlg0012.tlg001.perseus-grc1.xml",
        "tlg0012.tlg001.perseus-grc2.xml",
    ]
    assert pick_edition(names) == "tlg0012.tlg001.perseus-grc2.xml"
    assert pick_edition(names, "perseus-grc1") == "tlg0012.tlg001.perseus-grc1.xml"
    assert pick_edition(names, "nope") is None
    assert pick_edition(["__cts__.xml", "a.perseus-eng1.xml"]) is None  # no Greek edition


def test_work_dir_validation():
    assert _work_dir("tlg0012.tlg001") == "data/tlg0012/tlg001"
    with pytest.raises(ValueError, match="tlg0012.tlg001"):
        _work_dir("not-a-work")


def test_github_listing_is_cached_per_ref(tmp_path, monkeypatch):
    """A second listing for the same (repo, ref, path) never touches the network —
    refs are immutable commits, so the cache can't go stale."""
    import urllib.request

    from aegean.scripts.greek import perseus

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    calls = []

    class _Resp:
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *a):  # type: ignore[no-untyped-def]
            return False

        def read(self) -> bytes:
            return b'[{"name": "x.tlg001.perseus-grc1.xml"}, {"name": "__cts__.xml"}]'

    def fake_urlopen(req, timeout=0):  # type: ignore[no-untyped-def]
        calls.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    first = perseus._github_listing("o/r", "data/x/y", "a" * 40)
    second = perseus._github_listing("o/r", "data/x/y", "a" * 40)
    assert first == second == ["x.tlg001.perseus-grc1.xml", "__cts__.xml"]
    assert len(calls) == 1  # the second call was served from the cache


def test_github_listing_sends_token_when_set(tmp_path, monkeypatch):
    import urllib.request

    from aegean.scripts.greek import perseus

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    monkeypatch.setenv("PYAEGEAN_GITHUB_TOKEN", "tok-123")
    seen = {}

    class _Resp:
        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *a):  # type: ignore[no-untyped-def]
            return False

        def read(self) -> bytes:
            return b"[]"

    def fake_urlopen(req, timeout=0):  # type: ignore[no-untyped-def]
        seen["auth"] = req.get_header("Authorization")
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    perseus._github_listing("o/r", "data/a/b", "b" * 40)
    assert seen["auth"] == "Bearer tok-123"
