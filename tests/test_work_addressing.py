"""Richer load_work citation addressing: line ranges within a book, multiple
comma-separated refs, and the canonical citation for exactly what was selected.

Offline: every case parses the authored TEI fixture directly (no network); only
the TEI-parsing / ref-grammar surface is exercised, the same seam
tests/test_greek_works.py uses."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.core.model import TokenKind
from aegean.scripts.greek.perseus import (
    canonical_citation,
    parse_tei_work,
)

FIXTURE = Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml"
# The fixture: book 1 (two verse <l> lines) + chapter 2 (two <p> blocks).
BLOB = FIXTURE.read_bytes()


# ── line ranges within one book (already supported; asserted on exact content) ──
def test_line_range_selects_exactly_the_addressed_lines() -> None:
    _, _, docs = parse_tei_work(BLOB, "w", ref="1.1-1.2")
    assert len(docs) == 1
    d = docs[0]
    assert d.id == "w:1.1-1.2"
    assert len(d.lines) == 2  # both verse lines
    assert [t.text for t in d.line_tokens[0]] == ["μῆνιν", "ἄειδε", "θεὰ"]


def test_single_line_range_selects_one_line() -> None:
    _, _, docs = parse_tei_work(BLOB, "w", ref="1.1")
    assert len(docs) == 1 and len(docs[0].lines) == 1
    assert [t.text for t in docs[0].tokens[:3]] == ["μῆνιν", "ἄειδε", "θεὰ"]


# ── multiple refs (comma list) → one Document per entry, in order ───────────────
def test_multiple_whole_part_refs_yield_one_document_each() -> None:
    _, _, docs = parse_tei_work(BLOB, "w", ref="1,2")
    assert [d.id for d in docs] == ["w:1", "w:2"]
    # book 1 is verse; chapter 2 is prose — both two physical lines here
    assert [len(d.lines) for d in docs] == [2, 2]
    assert [t.text for t in docs[0].line_tokens[0]] == ["μῆνιν", "ἄειδε", "θεὰ"]
    assert [t.text for t in docs[1].line_tokens[0]][:5] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]


def test_multiple_verse_line_refs_select_each_line() -> None:
    _, _, docs = parse_tei_work(BLOB, "w", ref="1.1,1.2")
    assert [d.id for d in docs] == ["w:1.1", "w:1.2"]
    assert [len(d.lines) for d in docs] == [1, 1]
    assert [t.text for t in docs[0].tokens[:3]] == ["μῆνιν", "ἄειδε", "θεὰ"]
    assert "μυρία" in " ".join(t.text for t in docs[1].tokens)


def test_multiple_refs_preserve_order_and_drop_exact_duplicates() -> None:
    # source order kept; an exact duplicate entry collapses (no duplicate-id corpus)
    _, _, docs = parse_tei_work(BLOB, "w", ref="2,1")
    assert [d.id for d in docs] == ["w:2", "w:1"]
    _, _, deduped = parse_tei_work(BLOB, "w", ref="1.1,1.1")
    assert [d.id for d in deduped] == ["w:1.1"]


def test_multiple_refs_may_span_textparts_where_a_hyphen_range_may_not() -> None:
    # a comma list resolves each entry independently, so it may cross textparts,
    # unlike a hyphen range (which is refused, see below)
    _, _, docs = parse_tei_work(BLOB, "w", ref="1.1,2")
    assert [d.id for d in docs] == ["w:1.1", "w:2"]
    assert docs[0].tokens[0].text == "μῆνιν"
    assert docs[1].line_tokens[0][0].text == "ἐν"


# ── the range/comma distinction is honoured (regression guard) ──────────────────
def test_hyphen_range_crossing_textparts_still_refused() -> None:
    # "1-2" is a RANGE (not a comma list): it must still refuse, naming both parts
    with pytest.raises(ValueError, match="crosses textparts"):
        parse_tei_work(BLOB, "w", ref="1-2")


def test_comma_and_range_combine() -> None:
    # each comma entry may itself be a within-part range
    _, _, docs = parse_tei_work(BLOB, "w", ref="1.1-1.2,2")
    assert [d.id for d in docs] == ["w:1.1-1.2", "w:2"]
    assert len(docs[0].lines) == 2 and len(docs[1].lines) == 2


# ── adversarial refs ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["1,", ",1", "1,,2", "1, ,2", ","])
def test_empty_comma_entry_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="empty entry|empty|malformed"):
        parse_tei_work(BLOB, "w", ref=bad)


def test_reversed_line_range_within_a_comma_list_is_rejected() -> None:
    # a descending range anywhere in the list fails the whole selection
    with pytest.raises(ValueError, match="descending"):
        parse_tei_work(BLOB, "w", ref="1.2-1.1")
    with pytest.raises(ValueError, match="descending"):
        parse_tei_work(BLOB, "w", ref="1.1,1.2-1.1")


def test_unresolvable_comma_entry_names_available_sections() -> None:
    with pytest.raises(ValueError, match="sections here|selected no text"):
        parse_tei_work(BLOB, "w", ref="1,99")


def test_prose_punctuation_survives_a_comma_selection() -> None:
    _, _, docs = parse_tei_work(BLOB, "w", ref="2")
    assert any(t.kind is TokenKind.PUNCT for t in docs[0].tokens)


# ── canonical citation for exactly what was selected ────────────────────────────
def test_canonical_citation_whole_work() -> None:
    assert canonical_citation("tlg0012.tlg001", None, "Homer", "Iliad") == "Homer, Iliad"


def test_canonical_citation_line_range() -> None:
    assert (
        canonical_citation("tlg0012.tlg001", "1.1-1.50", "Homer", "Iliad")
        == "Homer, Iliad 1.1-1.50"
    )


def test_canonical_citation_multiple_refs_joined_with_semicolons() -> None:
    assert (
        canonical_citation("tlg0012.tlg001", "1.1,1.5", "Homer", "Iliad")
        == "Homer, Iliad 1.1; 1.5"
    )


def test_canonical_citation_falls_back_to_the_work_id_without_author_title() -> None:
    assert canonical_citation("tlg0012.tlg001", "1") == "tlg0012.tlg001 1"


def test_canonical_citation_title_only() -> None:
    assert canonical_citation("w", "3", author="", title="Ἔργον") == "Ἔργον 3"
