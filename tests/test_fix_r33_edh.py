"""Regression: EDH '#'-delimited variant merges and <choice> doubling (fix wave r33).

EDH bakes several parallel forms of a word into the edition text, joined by a literal '#' (the
edited form, further editorial variants, then the diplomatic all-capitals form), marks an inline
diplomatic-to-edited letter correspondence as edited=DIPLOMATIC (capitals after '='), and encodes
a correction as a real TEI <choice><corr>/<sic>. The shared extractor walked both <choice> members
(leaking a stray capital) and left the '#'/'=' apparatus baked into Token.text -- e.g. doc HD013935
produced 'πέμΝπτης#πέμπτης#πέΝπτης'. The EDH build now resolves <choice> to its edited member and
routes the '#'-variants to Token.alt; the default extractor behaviour is unchanged so the other
epigraphy corpora (isicily/iip/iospe/igcyr), which call edition_tokens() without the flag, stay
byte-identical.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _epidoc import (  # noqa: E402
    _strip_diplomatic_eq,
    edition_tokens,
    resolve_inline_variants,
)

_NS = 'xmlns="http://www.tei-c.org/ns/1.0"'

# The exact HD013935 construct: a real <choice><corr>μ</corr><sic>Ν</sic> in the first '#'-form, a
# <supplied> in the second, and the diplomatic all-capitals third form -- flanked by plain words.
_HD013935 = (
    '<lb n="1"/>φυλῆς '
    'πέ<choice><corr>μ</corr><sic>Ν</sic></choice>πτης'
    '#πέ<supplied reason="omitted">μ</supplied>πτης'
    '#πέΝπτης Βορείδος'
)


def _edition(inner: str) -> ET.Element:
    return ET.fromstring(f'<div {_NS} type="edition"><ab>{inner}</ab></div>')


def _edh_tokens(inner: str) -> list[tuple[str, tuple[str, ...]]]:
    """Extract as scripts/build_edh_corpus does: choice-aware, then '#'-variant resolution."""
    out: list[tuple[str, tuple[str, ...]]] = []
    for line in edition_tokens(_edition(inner), choice_prefer=True):
        for word, _status in line:
            text, alt = resolve_inline_variants(word)
            out.append((text, alt))
    return out


def test_hd013935_construct_extracts_one_reading_with_variants() -> None:
    toks = _edh_tokens(_HD013935)
    # the merged '#'/choice token becomes a single clean reading, the diplomatic form an alternate
    assert ("πέμπτης", ("πέΝπτης",)) in toks
    words = [t for t, _ in toks]
    # the stray capital leaked by <sic>Ν</sic> is gone; no apparatus artefact survives in a reading
    assert "πέμΝπτης" not in words
    for t, _ in toks:
        assert "#" not in t and "=" not in t
    # plain words on either side of the merged token are untouched
    assert "φυλῆς" in words and "Βορείδος" in words


def test_equals_diplomatic_correspondence_is_dropped() -> None:
    # HD035396-style: <supplied>Th=ΗΤ</supplied> baked inline; the diplomatic side is capitals.
    inner = (
        '<lb n="1"/><supplied reason="omitted">Th=ΗΤ</supplied>iodotuς'
        '#<supplied reason="omitted">Th</supplied>iodotuς#ΗΤIODOTUς'
    )
    assert _edh_tokens(inner) == [("Thiodotuς", ("ΗΤIODOTUς",))]


def test_resolve_inline_variants_known_answers() -> None:
    assert resolve_inline_variants("πέμπτης#πέμπτης#πέΝπτης") == ("πέμπτης", ("πέΝπτης",))
    assert resolve_inline_variants("Th=ΗΤiodotuς#Thiodotuς#ΗΤIODOTUς") == (
        "Thiodotuς",
        ("ΗΤIODOTUς",),
    )
    # duplicate forms across '#' collapse; the primary is excluded from its own alternates
    assert resolve_inline_variants("καὶ=Ε#καὶ#κΕ") == ("καὶ", ("κΕ",))
    # a word without '#' is returned unchanged, with no alternates
    assert resolve_inline_variants("Αὐρ(ήλιος)") == ("Αὐρ(ήλιος)", ())
    assert resolve_inline_variants("|(δηνάρια)") == ("|(δηνάρια)", ())


def test_strip_diplomatic_eq_keeps_the_edited_side() -> None:
    assert _strip_diplomatic_eq("Th=ΗΤiodotuς") == "Thiodotuς"      # multi-capital run
    assert _strip_diplomatic_eq("γυναι=Ικὶ") == "γυναικὶ"           # single-capital run
    assert _strip_diplomatic_eq("κατάκει=Ιται=Ε") == "κατάκειται"   # two markers in one form
    assert _strip_diplomatic_eq("νίκης") == "νίκης"                 # no marker: identity


def test_default_extractor_is_unchanged_and_keeps_choice_doubling() -> None:
    # Guard for the other epigraphy corpora: edition_tokens() with the default flag must keep BOTH
    # <choice> members (the historical, byte-identical behaviour). Only choice_prefer=True, which
    # the EDH build opts into, collapses to the edited member.
    ed = _edition('πέ<choice><corr>μ</corr><sic>Ν</sic></choice>πτης')
    (default_word, _s1), = edition_tokens(ed)[0]
    assert default_word == "πέμΝπτης"
    (preferred_word, _s2), = edition_tokens(ed, choice_prefer=True)[0]
    assert preferred_word == "πέμπτης"


def test_choice_prefers_expansion_and_regularization() -> None:
    # <choice><abbr>/<expan> already resolved to the expansion (abbr is skipped); confirm the new
    # branch keeps that, and that <reg> wins over <orig>.
    ed = _edition('<choice><abbr>Αὐρ</abbr><expan>Αὐρ<ex>ήλιος</ex></expan></choice> '
                  '<choice><orig>ΝΕΙΚΗ</orig><reg>νίκη</reg></choice>')
    words = [w for line in edition_tokens(ed, choice_prefer=True) for (w, _s) in line]
    assert words == ["Αὐρήλιος", "νίκη"]
