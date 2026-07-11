"""Citation-scheme awareness for load_work addressing (ITEM 8).

The Perseus / First1KGreek TEI editions declare, in their ``<refsDecl>``, exactly
how each work is cited (the CTS ``<cRefPattern>`` levels: book/line, section,
book/chapter/section, …). This surface:

* reads that declared scheme (`_citation_scheme` / the public `citation_scheme`),
  driven by the edition's own ``cRefPattern`` rather than any hardcoded per-author
  knowledge;
* uses it to make a failed ``--ref`` name how the work IS addressed and label the
  values that exist by their declared level (``book`` vs ``section`` vs ``line``),
  instead of the old fixed word "sections";
* changes NOTHING about which refs resolve — every existing ref form yields the
  identical documents whether or not the edition declares a refsDecl (pinned here).

Offline correctness tests: each scheme archetype is a small authored TEI fixture
parsed directly through the same ``parse_tei_work`` seam the other work tests use.
One guarded case exercises a live-cached work when the machine has one; it is
skipped (never fetched) otherwise, so the suite stays network-free.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from aegean.scripts.greek.perseus import (
    _citation_scheme,
    _scheme_path,
    canonical_citation,
    citation_scheme,
    list_fetched_works,
    parse_tei_work,
)

# ── TEI fixture builders (one per declared-scheme archetype) ─────────────────────
def _tei(refs_decl: str, body_divs: str, *, title: str = "Ἔργον", author: str = "Auctor") -> bytes:
    """A minimal but well-formed TEI work: an optional ``refs_decl`` block plus the
    ``<body>`` edition div content ``body_divs``."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        "  <teiHeader><fileDesc>\n"
        f'    <titleStmt><title xml:lang="grc">{title}</title><author>{author}</author></titleStmt>\n'
        "    <publicationStmt><p>fixture</p></publicationStmt>\n"
        "    <sourceDesc><p>authored test fixture</p></sourceDesc>\n"
        f"  </fileDesc><encodingDesc>{refs_decl}</encodingDesc></teiHeader>\n"
        "  <text><body>\n"
        '    <div type="edition" n="urn:cts:greekLit:test" xml:lang="grc">\n'
        f"{body_divs}\n"
        "    </div>\n"
        "  </body></text>\n"
        "</TEI>\n"
    ).encode("utf-8")


# refsDecl blocks (the replacementPattern content is irrelevant to us; we read n + group count)
_RD_BOOK_LINE = (
    '<refsDecl n="CTS">'
    r'<cRefPattern n="line" matchPattern="(\w+).(\w+)" replacementPattern="x/l"/>'
    r'<cRefPattern n="book" matchPattern="(\w+)" replacementPattern="x"/>'
    "</refsDecl>"
)
_RD_SECTION = (
    '<refsDecl n="CTS">'
    r'<cRefPattern n="section" matchPattern="(\w+)" replacementPattern="x"/>'
    "</refsDecl>"
)
_RD_BOOK_CHAP_SEC = (
    '<refsDecl n="CTS">'
    r'<cRefPattern n="section" matchPattern="(\w+).(\w+).(\w+)" replacementPattern="x"/>'
    r'<cRefPattern n="chapter" matchPattern="(\w+).(\w+)" replacementPattern="x"/>'
    r'<cRefPattern n="book" matchPattern="(\w+)" replacementPattern="x"/>'
    "</refsDecl>"
)
_RD_CHAP_SUBCHAP = (
    '<refsDecl n="CTS">'
    r'<cRefPattern n="subchapter" matchPattern="(\w+).(\w+)" replacementPattern="x"/>'
    r'<cRefPattern n="chapter" matchPattern="(\w+)" replacementPattern="x"/>'
    "</refsDecl>"
)
_RD_LINE = (  # drama: one global line level, matchPattern is (.+)
    '<refsDecl n="CTS">'
    r'<cRefPattern n="line" matchPattern="(.+)" replacementPattern="x//l"/>'
    "</refsDecl>"
)
_RD_VOLUME_BOOK_SECTION = (
    '<refsDecl n="CTS">'
    r'<cRefPattern n="section" matchPattern="(\w+).(\w+).(\w+)" replacementPattern="x"/>'
    r'<cRefPattern n="epigraph|book" matchPattern="(\w+).(\w+)" replacementPattern="x"/>'
    r'<cRefPattern n="volume" matchPattern="(\w+)" replacementPattern="x"/>'
    "</refsDecl>"
)

# bodies
_BODY_BOOK_LINE = (
    '<div type="textpart" subtype="book" n="1">'
    '<l n="1">μῆνιν ἄειδε θεά</l><l n="2">οὐλομένην ἣ μυρία</l></div>'
    '<div type="textpart" subtype="book" n="2"><l n="1">ἄνδρα μοι ἔννεπε</l></div>'
)
_BODY_SECTION = (
    '<div type="textpart" subtype="section" n="17"><p>ὅτι μὲν ὑμεῖς.</p></div>'
    '<div type="textpart" subtype="section" n="18"><p>πρῶτον μὲν οὖν.</p></div>'
)
_BODY_BOOK_CHAP_SEC = (
    '<div type="textpart" subtype="book" n="1">'
    '<div type="textpart" subtype="chapter" n="1">'
    '<div type="textpart" subtype="section" n="1"><p>Δαρείου καὶ Παρυσάτιδος.</p></div>'
    "</div></div>"
)
_BODY_LINE_DRAMA = (
    '<div type="textpart" subtype="episode">'
    '<l n="1">ὦ τέκνα</l><l n="2">Κάδμου</l><l n="3">τροφή</l></div>'
)
_BODY_VOL_BOOK_SEC = (
    '<div type="textpart" subtype="volume" n="1">'
    '<div type="textpart" subtype="book" n="1">'
    '<div type="textpart" subtype="section" n="1"><p>ἀρχὴ τοῦ λόγου.</p></div>'
    "</div></div>"
)


def _scheme(refs_decl: str, body: str = _BODY_BOOK_LINE) -> list[str]:
    return _citation_scheme(ET.fromstring(_tei(refs_decl, body)))


# ── _citation_scheme: the declared levels per archetype ─────────────────────────
def test_scheme_book_line() -> None:
    assert _scheme(_RD_BOOK_LINE) == ["book", "line"]


def test_scheme_single_section() -> None:
    assert _scheme(_RD_SECTION, _BODY_SECTION) == ["section"]


def test_scheme_book_chapter_section() -> None:
    assert _scheme(_RD_BOOK_CHAP_SEC, _BODY_BOOK_CHAP_SEC) == ["book", "chapter", "section"]


def test_scheme_chapter_subchapter() -> None:
    assert _scheme(_RD_CHAP_SUBCHAP) == ["chapter", "subchapter"]


def test_scheme_global_line() -> None:
    # matchPattern (.+) is one capture group -> a single "line" level
    assert _scheme(_RD_LINE, _BODY_LINE_DRAMA) == ["line"]


def test_scheme_three_levels_with_alternated_name() -> None:
    # the CapiTainS "epigraph|book" alternated level name is preserved verbatim
    assert _scheme(_RD_VOLUME_BOOK_SECTION, _BODY_VOL_BOOK_SEC) == [
        "volume",
        "epigraph|book",
        "section",
    ]


def test_scheme_empty_without_refsdecl() -> None:
    assert _scheme("", _BODY_BOOK_LINE) == []


def test_scheme_ignores_commented_out_pattern() -> None:
    # an Aristotle-style commented cRefPattern is XML comment text, not an element:
    # only the two live patterns count
    rd = (
        '<refsDecl n="CTS">'
        r'<!-- <cRefPattern n="section" matchPattern="(\w+).(\w+).(\w+)" replacementPattern="x"/> -->'
        r'<cRefPattern n="subchapter" matchPattern="(\w+).(\w+)" replacementPattern="x"/>'
        r'<cRefPattern n="chapter" matchPattern="(\w+)" replacementPattern="x"/>'
        "</refsDecl>"
    )
    assert _scheme(rd) == ["chapter", "subchapter"]


def test_scheme_prefers_the_cts_refsdecl() -> None:
    # a non-CTS refsDecl present alongside the CTS one must not win
    rd = (
        '<refsDecl n="other"><cRefPattern n="page" matchPattern="(\\w+)" replacementPattern="x"/>'
        "</refsDecl>" + _RD_BOOK_LINE
    )
    assert _scheme(rd) == ["book", "line"]


def test_scheme_path_normalizes_alternated_name() -> None:
    assert _scheme_path(["volume", "epigraph|book", "section"]) == "volume.epigraph/book.section"
    assert _scheme_path(["book", "line"]) == "book.line"
    assert _scheme_path([]) == ""


# ── positive resolution is unchanged (output-verifying) ─────────────────────────
def test_book_line_range_still_resolves_exact_lines() -> None:
    _, _, docs = parse_tei_work(_tei(_RD_BOOK_LINE, _BODY_BOOK_LINE), "w", ref="1.1-1.2")
    assert len(docs) == 1 and len(docs[0].lines) == 2
    assert [t.text for t in docs[0].line_tokens[0]] == ["μῆνιν", "ἄειδε", "θεά"]


def test_single_section_resolves_its_paragraph() -> None:
    _, _, docs = parse_tei_work(_tei(_RD_SECTION, _BODY_SECTION), "w", ref="17")
    assert docs[0].id == "w:17"
    assert [t.text for t in docs[0].tokens[:3]] == ["ὅτι", "μὲν", "ὑμεῖς"]


def test_nested_book_chapter_section_resolves_the_leaf() -> None:
    _, _, docs = parse_tei_work(_tei(_RD_BOOK_CHAP_SEC, _BODY_BOOK_CHAP_SEC), "w", ref="1.1.1")
    assert docs[0].id == "w:1.1.1"
    assert "Δαρείου" in " ".join(t.text for t in docs[0].tokens)


def test_global_line_resolves_across_a_wrapping_div() -> None:
    # the drama line lives under an episode div with no @n; a bare line ref still finds it
    _, _, docs = parse_tei_work(_tei(_RD_LINE, _BODY_LINE_DRAMA), "w", ref="2")
    assert [t.text for t in docs[0].tokens] == ["Κάδμου"]


def test_scheme_presence_does_not_change_the_resolved_documents() -> None:
    """The regression pin: the declared scheme is purely cosmetic to resolution —
    the SAME ref yields byte-identical documents with and without a refsDecl."""
    for ref in ("1", "1.1", "1.1-1.2", "1.1,2.1", "2"):
        _, _, with_rd = parse_tei_work(_tei(_RD_BOOK_LINE, _BODY_BOOK_LINE), "w", ref=ref)
        _, _, without = parse_tei_work(_tei("", _BODY_BOOK_LINE), "w", ref=ref)
        assert [d.id for d in with_rd] == [d.id for d in without]
        assert [[t.text for t in d.tokens] for d in with_rd] == [
            [t.text for t in d.tokens] for d in without
        ]
        assert [d.lines for d in with_rd] == [d.lines for d in without]


def test_whole_work_load_without_ref_is_unaffected() -> None:
    _, _, docs = parse_tei_work(_tei(_RD_BOOK_LINE, _BODY_BOOK_LINE), "w")
    assert [d.id for d in docs] == ["w:1", "w:2"]


# ── scheme-aware error messages (the clean win) ─────────────────────────────────
def test_unresolved_ref_names_the_declared_scheme_and_level() -> None:
    # Plato-style: a sub-page reference like "17a" is not a declared section div
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei(_RD_SECTION, _BODY_SECTION), "w", ref="17a")
    msg = str(exc.value)
    assert "selected no text" in msg
    assert "cited by section" in msg
    assert "section values present: 17, 18" in msg


def test_top_level_miss_uses_the_top_level_word_not_sections() -> None:
    # a book miss says "book values present", not the old fixed word "sections"
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei(_RD_BOOK_CHAP_SEC, _BODY_BOOK_CHAP_SEC), "w", ref="99")
    msg = str(exc.value)
    assert "cited by book.chapter.section" in msg
    assert "book values present: 1" in msg


def test_nested_miss_uses_the_matched_depth_level_word() -> None:
    # book 1 exists, chapter 99 does not: the message labels the level that failed
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei(_RD_BOOK_CHAP_SEC, _BODY_BOOK_CHAP_SEC), "w", ref="1.99")
    assert "chapter values present: 1" in str(exc.value)


def test_out_of_range_line_names_the_line_level_and_span() -> None:
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei(_RD_LINE, _BODY_LINE_DRAMA), "w", ref="9999")
    msg = str(exc.value)
    assert "cited by line" in msg
    assert "line values present: 1–3" in msg


def test_crossing_textparts_names_scheme_and_suggests_comma_list() -> None:
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei(_RD_SECTION, _BODY_SECTION), "w", ref="17-18")
    msg = str(exc.value)
    assert "crosses textparts" in msg  # the pinned distinction is preserved
    assert "cited by section" in msg
    assert "'17,18'" in msg  # the concrete, ready-to-run alternative


def test_alternated_level_name_reads_with_a_slash_in_messages() -> None:
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei(_RD_VOLUME_BOOK_SECTION, _BODY_VOL_BOOK_SEC), "w", ref="99")
    assert "cited by volume.epigraph/book.section" in str(exc.value)


# ── the no-refsDecl fallback wording is byte-identical (regression pin) ──────────
def test_without_refsdecl_keeps_generic_sections_wording() -> None:
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei("", _BODY_BOOK_LINE), "w", ref="99")
    msg = str(exc.value)
    assert "sections here: 1, 2" in msg  # the historical wording, unchanged
    assert "cited by" not in msg  # no scheme note when nothing is declared


def test_without_refsdecl_keeps_generic_lines_wording() -> None:
    with pytest.raises(ValueError) as exc:
        parse_tei_work(_tei("", _BODY_LINE_DRAMA), "w", ref="9999")
    msg = str(exc.value)
    assert "lines present: 1–3" in msg
    assert "cited by" not in msg


# ── canonical citation is untouched by the scheme work (guard) ──────────────────
def test_canonical_citation_unchanged() -> None:
    assert canonical_citation("tlg0012.tlg001", "1.1-1.50", "Homer", "Iliad") == "Homer, Iliad 1.1-1.50"


# ── public citation_scheme against a live-cached work, when present ──────────────
def test_public_citation_scheme_on_a_cached_work_if_available() -> None:
    """Exercises the public fetch-backed accessor only against a work already in the
    local cache, so the suite never hits the network. Skipped when nothing is cached
    (e.g. CI)."""
    cached = {w["id"] for w in list_fetched_works()}
    # a known scheme per work id; try whichever is present
    expected = {
        "tlg0012.tlg001": ["book", "line"],  # Iliad
        "tlg0012.tlg002": ["book", "line"],  # Odyssey
    }
    hit = next((wid for wid in expected if wid in cached), None)
    if hit is None:
        pytest.skip("no scheme-known Greek work is cached locally")
    assert citation_scheme(hit) == expected[hit]
