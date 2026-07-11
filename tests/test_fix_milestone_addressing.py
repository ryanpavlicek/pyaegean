"""Milestone sub-page addressing: Stephanus sub-pages (Plato ``17a``) and Bekker
lines (Aristotle ``1447a10``) that live in ``<milestone>`` markers outside the CTS
``<div>`` citation scheme.

Offline: the milestone cases parse authored TEI fixtures directly (one per marker
convention), so the marker-span extraction is verified on known content without any
network — the same seam tests/test_work_addressing.py uses. A handful of live-cached
spot checks run only when the real Perseus editions are already in the local cache
(pure local read, skipped otherwise)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.scripts.greek.perseus import canonical_citation, parse_tei_work

# ── authored fixtures ────────────────────────────────────────────────────────────

# Plato-style: two section <div>s (Stephanus pages 17, 18), each a <p> whose text is
# delimited by unit="section" milestones carrying the FULL Stephanus n ("17a", "17b").
# A unit="page" milestone (n="17") shares the section div — the a/b/c sub-pages are the
# addressable finer unit. 17c is the last sub-page of page 17, so its span must run to
# 18a in the *next* div (a marker boundary crossing a textpart boundary).
STEPHANUS = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt>
    <title xml:lang="grc">Ἀπολογία</title>
    <author>Πλάτων</author>
  </titleStmt>
  <publicationStmt><p>fixture</p></publicationStmt>
  <sourceDesc><p>authored</p></sourceDesc>
  </fileDesc>
  <encodingDesc><refsDecl n="CTS">
    <cRefPattern n="section" matchPattern="(\\w+)"
      replacementPattern="#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1'])"/>
  </refsDecl></encodingDesc></teiHeader>
  <text><body>
    <div type="edition" xml:lang="grc" n="urn:cts:greekLit:tlg0059.tlg002.test-grc1">
      <div type="textpart" subtype="section" n="17">
        <p><milestone unit="page" resp="Stephanus" n="17"/>
          <milestone unit="section" resp="Stephanus" n="17a"/> ἄλφα πρῶτον λόγος.
          <milestone unit="section" resp="Stephanus" n="17b"/> βῆτα<note>skip this note</note> δεύτερον.
          <milestone unit="section" resp="Stephanus" n="17c"/> γάμμα τρίτον τέλος.</p>
      </div>
      <div type="textpart" subtype="section" n="18">
        <p><milestone unit="page" resp="Stephanus" n="18"/>
          <milestone unit="section" resp="Stephanus" n="18a"/> δέλτα τέταρτον ἀρχή.</p>
      </div>
    </div>
  </body></text>
</TEI>
""".encode()

# Aristotle-style: chapter/subchapter <div>s with unit="page" (Bekker page "1447a") and
# unit="line" milestones whose n is PAGE-RELATIVE ("8", "10", "15" — they repeat on the
# next page). Page 1447a's lines span TWO subchapter divs, so a whole-page span and a
# line-span must both flatten across the div boundary; the same line n "10" appears under
# both 1447a and 1447b, so the page prefix must scope which "10" a "1447b10" ref means.
BEKKER = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt>
    <title xml:lang="grc">Περὶ ποιητικῆς</title>
    <author>Ἀριστοτέλης</author>
  </titleStmt>
  <publicationStmt><p>fixture</p></publicationStmt>
  <sourceDesc><p>authored</p></sourceDesc>
  </fileDesc>
  <encodingDesc><refsDecl n="CTS">
    <cRefPattern n="subchapter" matchPattern="(\\w+).(\\w+)"
      replacementPattern="#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1']/tei:div[@n='$2'])"/>
    <cRefPattern n="chapter" matchPattern="(\\w+)"
      replacementPattern="#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1'])"/>
  </refsDecl></encodingDesc></teiHeader>
  <text><body>
    <div type="edition" xml:lang="grc" n="urn:cts:greekLit:tlg0086.tlg034.test-grc1">
      <div type="textpart" subtype="chapter" n="1">
        <div type="textpart" subtype="subchapter" n="1">
          <p><milestone unit="page" resp="Bekker" n="1447a"/>
            <milestone unit="line" resp="Bekker" n="8"/> ὀκτὼ γραμμή.
            <milestone unit="line" resp="Bekker" n="10"/> δέκα γραμμή.</p>
        </div>
        <div type="textpart" subtype="subchapter" n="2">
          <p><milestone unit="line" resp="Bekker" n="15"/> δεκαπέντε γραμμή.
            <milestone unit="page" resp="Bekker" n="1447b"/>
            <milestone unit="line" resp="Bekker" n="8"/> ὀκτὼβητα γραμμή.
            <milestone unit="line" resp="Bekker" n="10"/> δεκαβητα γραμμή.</p>
        </div>
      </div>
    </div>
  </body></text>
</TEI>
""".encode()


def _text(doc: object) -> str:
    return " ".join(t.text for t in doc.tokens)  # type: ignore[attr-defined]


# ── Stephanus sub-pages (exact marker match) ─────────────────────────────────────
def test_stephanus_subpage_extracts_its_own_span() -> None:
    _, _, docs = parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17a")
    assert len(docs) == 1
    d = docs[0]
    assert d.id == "tlg0059.tlg002:17a"
    txt = _text(d)
    assert "ἄλφα" in txt and "πρῶτον" in txt
    # the span stops at the next section marker (17b) — no bleed into 17b/17c
    assert "βῆτα" not in txt and "γάμμα" not in txt


def test_stephanus_subpage_skips_editorial_notes() -> None:
    _, _, docs = parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17b")
    txt = _text(docs[0])
    assert "βῆτα" in txt and "δεύτερον" in txt
    assert "skip" not in txt.lower()  # <note> content excluded


def test_stephanus_last_subpage_of_a_page_stops_at_next_page_marker() -> None:
    # 17c is the last sub-page of page 17; the next section marker is 18a in the NEXT
    # <div>. The span must run to 18a (crossing the textpart boundary) and stop there.
    _, _, docs = parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17c")
    txt = _text(docs[0])
    assert "γάμμα" in txt and "τέλος" in txt
    assert "δέλτα" not in txt  # 18a's text is not swept in


def test_stephanus_whole_page_div_still_resolves_as_before() -> None:
    # "17" is a <div n="17"> — the existing div path, unchanged: the whole page 17
    _, _, docs = parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17")
    txt = _text(docs[0])
    assert docs[0].id == "tlg0059.tlg002:17"
    assert "ἄλφα" in txt and "βῆτα" in txt and "γάμμα" in txt


def test_stephanus_subpages_as_a_comma_list() -> None:
    _, _, docs = parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17a,17c")
    assert [d.id for d in docs] == ["tlg0059.tlg002:17a", "tlg0059.tlg002:17c"]
    assert "ἄλφα" in _text(docs[0]) and "γάμμα" in _text(docs[1])


# ── Bekker page + line (composite marker match) ──────────────────────────────────
def test_bekker_whole_page_spans_across_subchapter_divs() -> None:
    # page 1447a runs through subchapter 1 AND subchapter 2 — a per-<p> walk would
    # truncate it; the flat stream keeps the full page and stops at the next page (1447b)
    _, _, docs = parse_tei_work(BEKKER, "tlg0086.tlg034", ref="1447a")
    txt = _text(docs[0])
    assert docs[0].id == "tlg0086.tlg034:1447a"
    assert "ὀκτὼ" in txt and "δέκα" in txt and "δεκαπέντε" in txt  # lines 8,10,15
    assert "ὀκτὼβητα" not in txt  # page 1447b's line 8 is excluded


def test_bekker_line_extracts_the_page_relative_span() -> None:
    _, _, docs = parse_tei_work(BEKKER, "tlg0086.tlg034", ref="1447a10")
    d = docs[0]
    assert d.id == "tlg0086.tlg034:1447a10"
    txt = _text(d)
    assert "δέκα" in txt  # line 10's text
    assert "ὀκτὼ" not in txt  # not line 8
    assert "δεκαπέντε" not in txt  # stops at line 15 (the next line marker)


def test_bekker_first_line_of_page() -> None:
    _, _, docs = parse_tei_work(BEKKER, "tlg0086.tlg034", ref="1447a8")
    txt = _text(docs[0])
    assert "ὀκτὼ" in txt and "δέκα" not in txt


def test_bekker_same_relative_line_number_is_scoped_to_its_page() -> None:
    # line "10" exists on BOTH pages; "1447b10" must pick page 1447b's line 10, not
    # 1447a's — the page prefix scopes the relative line search
    _, _, a = parse_tei_work(BEKKER, "tlg0086.tlg034", ref="1447a10")
    _, _, b = parse_tei_work(BEKKER, "tlg0086.tlg034", ref="1447b10")
    assert "δέκα" in _text(a[0]) and "δεκαβητα" not in _text(a[0])
    assert "δεκαβητα" in _text(b[0]) and "δέκα " not in _text(b[0]) + " "


# ── fallback: a work with no such markers, or an unknown marker ───────────────────
def test_unknown_stephanus_subpage_falls_back_to_scheme_error() -> None:
    with pytest.raises(ValueError, match="selected no text|section"):
        parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17z")


def test_unknown_bekker_line_falls_back_to_scheme_error() -> None:
    # page 1447a exists but has no line 99
    with pytest.raises(ValueError, match="selected no text|chapter|subchapter"):
        parse_tei_work(BEKKER, "tlg0086.tlg034", ref="1447a99")


def test_marker_ref_on_a_work_without_milestones_still_errors_cleanly() -> None:
    # the plain sample fixture has no milestones — a non-numeric leftover must still
    # raise the scheme-naming error, exactly as before this feature
    sample = (Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml").read_bytes()
    with pytest.raises(ValueError, match="selected no text"):
        parse_tei_work(sample, "w", ref="17a")


# ── canonical citation carries the marker ref verbatim ───────────────────────────
def test_canonical_citation_stephanus_subpage() -> None:
    assert (
        canonical_citation("tlg0059.tlg002", "17a", "Plato", "Apology") == "Plato, Apology 17a"
    )


def test_canonical_citation_bekker_line() -> None:
    assert (
        canonical_citation("tlg0086.tlg034", "1447a10", "Aristotle", "Poetics")
        == "Aristotle, Poetics 1447a10"
    )


# ── sibling range across textparts: refusal + a comma suggestion that round-trips ─
def test_sibling_textpart_range_is_refused_with_a_comma_suggestion() -> None:
    # "17-18" is two section <div>s; one Document per textpart is the model, so a hyphen
    # range across them is refused and the message offers the comma list "17,18".
    with pytest.raises(ValueError, match="crosses textparts") as exc:
        parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17-18")
    assert "17,18" in str(exc.value)


def test_the_suggested_comma_list_round_trips_to_one_document_per_part() -> None:
    # exactly the comma list the refusal above suggests must resolve to both parts
    _, _, docs = parse_tei_work(STEPHANUS, "tlg0059.tlg002", ref="17,18")
    assert [d.id for d in docs] == ["tlg0059.tlg002:17", "tlg0059.tlg002:18"]
    assert "ἄλφα" in _text(docs[0]) and "δέλτα" in _text(docs[1])


# ── regression: the existing ref grammar is byte-identical (no milestones present) ─
def test_existing_ref_forms_unchanged_by_milestone_support() -> None:
    sample = (Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml").read_bytes()
    # a whole textpart, a nested div, a verse line-range, and a comma list — all as before
    _, _, whole = parse_tei_work(sample, "w", ref="1")
    assert whole[0].id == "w:1"
    _, _, verse = parse_tei_work(sample, "w", ref="1.1")
    assert [t.text for t in verse[0].tokens[:3]] == ["μῆνιν", "ἄειδε", "θεὰ"]
    _, _, rng = parse_tei_work(sample, "w", ref="1.1-1.2")
    assert len(rng[0].lines) == 2
    _, _, both = parse_tei_work(sample, "w", ref="1,2")
    assert [d.id for d in both] == ["w:1", "w:2"]


# ── live-cached spot checks (skipped unless the real editions are already cached) ─
def _cached(work_id: str) -> bytes | None:
    from aegean.data import cache_dir

    root = cache_dir() / "greek-works"
    if not root.exists():
        return None
    hits = sorted(root.glob(f"*/*/{work_id}.*-grc*.xml"))
    return hits[0].read_bytes() if hits else None


def test_live_plato_apology_stephanus_17a() -> None:
    blob = _cached("tlg0059.tlg002")
    if blob is None:
        pytest.skip("Plato Apology not in the local cache")
    _, _, docs = parse_tei_work(blob, "tlg0059.tlg002", ref="17a")
    assert docs[0].id == "tlg0059.tlg002:17a"
    # the opening words of the Apology (Stephanus 17a)
    assert docs[0].tokens[0].text == "ὅτι"
    assert "ὑμεῖς" in _text(docs[0])


def test_live_aristotle_poetics_bekker_1447a10() -> None:
    blob = _cached("tlg0086.tlg034")
    if blob is None:
        pytest.skip("Aristotle Poetics not in the local cache")
    _, _, page = parse_tei_work(blob, "tlg0086.tlg034", ref="1447a")
    _, _, line = parse_tei_work(blob, "tlg0086.tlg034", ref="1447a10")
    assert page[0].id == "tlg0086.tlg034:1447a"
    # line 10's span is a proper, shorter sub-span of the whole page
    assert len(line[0].tokens) < len(page[0].tokens)
    assert line[0].tokens[0].text == "εἰ"  # "εἰ μέλλει καλῶς ἕξειν …" (Bekker 1447a10)
