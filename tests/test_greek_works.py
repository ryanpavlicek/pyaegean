"""The Perseus/First1KGreek work loader: TEI parsing + edition selection (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.core.model import TokenKind
from aegean.scripts.greek.perseus import (
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
