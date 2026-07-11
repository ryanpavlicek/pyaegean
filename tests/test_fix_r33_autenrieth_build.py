"""Regression tests for the r33 Autenrieth build fixes (four verified findings).

All offline, on inline Perseus-shaped TEI fixtures written to a temp file and run through
``scripts/build_autenrieth_index.py``. Each asserts the actual output, not that the build
merely runs:

1. lemma + headword derive from ``<orth>``, not a malformed ``D.H.``/stray-period ``key``;
2. the ``<*>`` quantity/placeholder marker is stripped (no ``<>`` leak) and digamma stays
   in body spans only;
3. the ``de/vw`` byform of δέω drops its ``v`` and merges with δέω 'bind' (both senses);
4. Homeric book-letter references inside ``<bibl>`` (``*a 278``) are converted (Α 278).

Plus the well-formed-Greek gate: an entry that yields no Greek lemma through either path is
skipped and reported, and the final index contains zero non-Greek lemmas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_autenrieth_index as bx  # noqa: E402

# A compact Perseus-shaped document. ``&lt;*&gt;`` is how the source encodes the ``<*>``
# placeholder mark; ElementTree parses it back to a literal ``<*>`` in the text.
_TEI = """<?xml version="1.0" encoding="utf-8"?>
<TEI.2><text><body><div1 type="alphabetic letter" n="a">
  <entryFree key="D.H.=mos1"><orth lang="greek">dh=mos</orth>: <gloss>land, then community, people</gloss>, <bibl n="x">Il. 12.211</bibl>.</entryFree>
  <entryFree key="a)a/w"><orth lang="greek">a&lt;*&gt;)a&lt;*&gt;/w</orth> (<foreign lang="greek">a)va/w</foreign>): <gloss>hurt, deceive</gloss>.</entryFree>
  <entryFree key="de/vw1"><orth lang="greek">de/vw</orth>: only aor., <gloss>stood in need of</gloss>, <bibl n="x">Il. 18.100</bibl>.</entryFree>
  <entryFree key="de/w1"><orth lang="greek">de/w</orth>: <gloss>bind</gloss>, fasten.</entryFree>
  <entryFree key="a)nti/bios"><orth lang="greek">a)nti/bios</orth>: <gloss>hostile</gloss>, <bibl n="x">*a 278</bibl>.</entryFree>
  <entryFree key="e)u/.cestos"><orth lang="greek">e)u/.-cestos</orth>: <gloss>well-polished</gloss>.</entryFree>
  <entryFree key="*dh=los"><orth lang="greek">*dh=los</orth>: <gloss>Delos, the island</gloss>, <bibl n="x">Od. 6.162</bibl>.</entryFree>
  <entryFree key="D.H.=los"><orth lang="greek">dh=los</orth>: <gloss>clear, evident</gloss>.</entryFree>
  <entryFree key="a)/nac"><orth lang="greek">a)/nac</orth> (<foreign lang="greek">va/nac</foreign>): <gloss>lord</gloss>.</entryFree>
  <entryFree key="mh=nis"><orth lang="greek">mh=nis</orth>: <gloss>wrath</gloss>, <bibl n="x">Il. 1.75</bibl>.</entryFree>
  <entryFree key="ei)d'a)/ge"><orth lang="greek">ei) d' a)/ge</orth>: <gloss>come on</gloss>.</entryFree>
</div1></body></text></TEI.2>
"""


@pytest.fixture
def built(tmp_path):
    src = tmp_path / "auten.xml"
    src.write_text(_TEI, encoding="utf-8")
    report: list[str] = []
    idx = bx.index_from_tei(src, report=report)
    return idx, report


# ── unit helpers ─────────────────────────────────────────────────────────────

def test_is_greek_lemma_gate():
    assert bx.is_greek_lemma("δῆμος")
    assert bx.is_greek_lemma("ἀχαιοί")
    assert bx.is_greek_lemma("δηθά")  # decomposed macro/accent stacks (combining marks) ok
    # rejects a leaked period, angle bracket, Latin letter, apostrophe, empty
    assert not bx.is_greek_lemma("δῆμ.ος")
    assert not bx.is_greek_lemma("α<>ω")
    assert not bx.is_greek_lemma("model")
    assert not bx.is_greek_lemma("εἰδ'ἄγε")
    assert not bx.is_greek_lemma("")


def test_first_orth_form_first_and_dehyphenated():
    # first comma form only
    assert bx.first_orth_form("dhqa/, dh/q)") == "dhqa/"
    # morpheme hyphens + surrounding whitespace removed
    assert bx.first_orth_form("a)a/ - sxetos") == "a)a/sxetos"
    assert bx.first_orth_form("a)-a_/a_tos") == "a)a_/a_tos"
    # line-wrap newline collapsed
    assert bx.first_orth_form("e)k -\n            punqa/nomai") == "e)kpunqa/nomai"


def test_headword_no_digamma_body_keeps_digamma():
    # finding 3: v→ϝ only in body spans, never in lemma/headword derivation
    assert bx.headword("a)/nac") == "ἄναξ"
    assert bx.lemma_key("a)/nac") == "ἄναξ"
    assert bx.beta_to_unicode("va/nac") == "ϝάναξ"  # body converter keeps it
    # the spurious de/vw byform drops its v → δέω (merges with δέω 'bind')
    assert bx.headword("de/vw") == "δέω"
    assert bx.headword("de/vw1") == "δέω"  # trailing homograph digit stripped too


def test_case_fold_collision_of_proper_and_common():
    # island (capital) and adjective (lower) share one lowercase lemma key
    assert bx.lemma_key("*dh=los") == "δῆλος"
    assert bx.lemma_key("dh=los") == "δῆλος"
    # headword preserves case for display
    assert bx.headword("*dh=los") == "Δῆλος"
    assert bx.headword("dh=los") == "δῆλος"


def test_marker_and_period_stripping_helpers():
    # <*> placeholder no longer detaches the breathing/accent
    assert bx.beta_to_unicode("a<*>)a<*>/w") == "ἀάω"
    # stray period in a malformed key/orth dropped in headword derivation
    assert bx.headword("e)u/.cestos") == "ἐύξεστος"


# ── finding 1: derive from <orth>, not the malformed key ─────────────────────

def test_dh_key_recovered_from_orth(built):
    idx, _ = built
    # δῆμος was unreachable under key="D.H.=mos1"; now derived from <orth>dh=mos
    assert "δῆμος" in idx
    assert idx["δῆμος"]["hw"] == "δῆμος"
    assert "people" in idx["δῆμος"]["def"]
    # no D.H. / period artifact leaked as a lemma anywhere
    assert all(bx.is_greek_lemma(k) for k in idx)


def test_stray_period_key_recovered(built):
    idx, _ = built
    assert "ἐύξεστος" in idx  # key="e)u/.cestos" (stray period) recovered
    assert "well-polished" in idx["ἐύξεστος"]["def"]


# ── finding 2: <*> marker + digamma placement ────────────────────────────────

def test_star_marker_stripped_in_entry(built):
    idx, _ = built
    assert "ἀάω" in idx
    assert idx["ἀάω"]["hw"] == "ἀάω"
    assert "<" not in idx["ἀάω"]["hw"] and ">" not in idx["ἀάω"]["hw"]
    # the etymological digamma survives in the body span (a)va/w → ἀϝάω)
    assert "ϝ" in idx["ἀάω"]["def"]


def test_no_headword_has_angle_bracket_leak(built):
    idx, _ = built
    assert not [k for k, r in idx.items() if "<" in r["hw"] or ">" in r["hw"]]


def test_digamma_only_in_body_not_headword(built):
    idx, _ = built
    assert "ϝάναξ" not in idx  # not a headword/lemma
    assert idx["ἄναξ"]["hw"] == "ἄναξ"
    assert "ϝάναξ" in idx["ἄναξ"]["def"]  # kept in the etymological body span


# ── finding 3: δέω merge ─────────────────────────────────────────────────────

def test_deo_homographs_merge(built):
    idx, _ = built
    assert "δέϝω" not in idx  # the buggy digamma headword is gone
    assert "δέω" in idx
    body = idx["δέω"]["def"]
    assert " | " in body
    assert "bind" in body
    assert "stood in need of" in body


# ── finding 4: bibl book-letter conversion ───────────────────────────────────

def test_bibl_book_letter_converted(built):
    idx, _ = built
    body = idx["ἀντίβιος"]["def"]
    assert "Α 278" in body  # *a 278 → Iliad Α 278
    assert "*a" not in body
    # plain ascii citations are untouched
    assert "Il. 1.75" in idx["μῆνις"]["def"]


# ── well-formed gate: skip + report; δῆλος/Δῆλος both senses; μῆνις unchanged ──

def test_non_greek_entry_skipped_and_reported(built):
    idx, report = built
    # the hortatory phrase εἰ δ' ἄγε carries an elision apostrophe: not a Greek lemma
    assert "ei)d'a)/ge" in report
    assert not any("ἄγε" in k for k in idx)


def test_delos_both_senses_present(built):
    idx, _ = built
    body = idx["δῆλος"]["def"]
    assert "Delos" in body  # island (Δῆλος) sense preserved
    assert "clear, evident" in body  # adjective (δῆλος) sense no longer lost
    assert "Δῆλος:" in body and "δῆλος:" in body  # both separately labelled


def test_menis_unchanged(built):
    idx, _ = built
    assert idx["μῆνις"]["hw"] == "μῆνις"
    assert "wrath" in idx["μῆνις"]["def"]


def test_report_optional_backcompat(tmp_path):
    # index_from_tei without a report list still builds (existing callers)
    src = tmp_path / "a.xml"
    src.write_text(_TEI, encoding="utf-8")
    idx = bx.index_from_tei(src)
    assert "δῆμος" in idx and "δέω" in idx
