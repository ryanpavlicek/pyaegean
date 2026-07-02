"""Linear A data/loader/phonetic regressions.

Pins four fixes: the *903 sign-table entry no longer duplicates the vowel I's
glyph/codepoint (U+1061A, LINEAR A SIGN AB028; the upstream corpus renders
*903 with the Aegean check mark U+10102, whose skip drifted the sign-table
alignment by one glyph), the SignInventory glyph/codepoint indexes warn on
duplicates and keep the first entry instead of silently shadowing, the
tokenizer classifies subscripted signs (PA₃) and variant-letter ligatures
(VIR+*313b) as logograms, and ``word_to_phonetic`` no longer reads the
distinct signs RA₂/PA₃/TA₂/PU₂ as plain ra/pa/ta/pu. The corrected phonetic
behavior is also pinned in the shared golden fixture (the workbench carries
the same values as of 1.5.5).

NOT errors, verified against Younger's readings and the upstream mapping: the
*904 and *905 entries carry genuine glyphs under upstream alias labels — *904
is GORILA *319 (U+1066B, the I-beam sign in HT 132 / HT Zd 155 / HT Zd 157+156)
and *905 is the fraction sign J (U+10746) used as a sign-group member on
HT Wa 1025. Do not re-flag them for wearing "someone else's" codepoint.
"""

from __future__ import annotations

import re
import warnings

import pytest

import aegean
from aegean.core.model import Sign, SignInventory, TokenKind
from aegean.scripts.lineara.inventory import linear_a_inventory
from aegean.scripts.lineara.loader import classify
from aegean.scripts.lineara.phonetic import word_to_phonetic


def test_sign_903_carries_no_glyph_or_codepoint():
    """*903 is a GORILA complex sign with no Unicode codepoint (the Linear A
    block ends at A807); U+1061A / 𐘚 belongs to the vowel I. The old entry
    duplicated I's glyph and codepoint."""
    inv = linear_a_inventory()
    s903 = inv.by_label("*903")
    assert s903 is not None
    assert s903.glyph is None
    assert s903.codepoint is None
    # the glyph and codepoint resolve to the sign that actually owns them
    i = inv.by_glyph("𐘚")
    assert i is not None and i.label == "I" and i.phonetic == "i"
    by_cp = inv.by_codepoint(0x1061A)
    assert by_cp is not None and by_cp.label == "I"


def test_inventory_glyph_and_codepoint_maps_are_injective():
    """No two Linear A signs share a glyph or a codepoint (the *903 duplicate
    was the only violation)."""
    inv = linear_a_inventory()
    glyphs = [s.glyph for s in inv if s.glyph]
    cps = [s.codepoint for s in inv if s.codepoint is not None]
    assert len(glyphs) == len(set(glyphs))
    assert len(cps) == len(set(cps))


def test_bundled_inventory_builds_without_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        SignInventory(list(linear_a_inventory().signs), "lineara")


def test_duplicate_glyph_guard_warns_and_keeps_first():
    a = Sign("A1", glyph="X", codepoint=1)
    b = Sign("B2", glyph="X", codepoint=2)
    with pytest.warns(UserWarning, match="duplicate glyph/codepoint"):
        inv = SignInventory([a, b], "test")
    assert inv.by_glyph("X") is a  # first wins, not last
    assert inv.by_codepoint(1) is a and inv.by_codepoint(2) is b
    assert inv.by_label("B2") is b  # the duplicate sign itself is still listed
    assert len(inv) == 2


def test_duplicate_codepoint_guard_warns_and_keeps_first():
    c = Sign("C1", glyph="Y", codepoint=7)
    d = Sign("C2", glyph="Z", codepoint=7)
    with pytest.warns(UserWarning, match=r"codepoint U\+0007"):
        inv = SignInventory([c, d], "test")
    assert inv.by_codepoint(7) is c
    assert inv.by_glyph("Y") is c and inv.by_glyph("Z") is d


def test_classify_subscripted_standalone_signs_as_logograms():
    for text in ("PA₃", "TA₂", "RA₂", "PU₂"):
        tok = classify(text, 0, 0)
        assert tok.kind is TokenKind.LOGOGRAM
        assert tok.signs == (text,)  # the subscript stays part of the label


def test_classify_variant_letter_ligatures_as_logograms():
    for text in ("VIR+*313a", "VIR+*313b", "VIR+*313c", "CAPm+KU", "OLE+QIf", "VINb+WI"):
        assert classify(text, 0, 0).kind is TokenKind.LOGOGRAM


def test_classify_still_rejects_prose_strays():
    # upstream data strays must not become logograms
    for text in ("None", "double mina"):
        assert classify(text, 0, 0).kind is TokenKind.UNKNOWN


def test_classify_existing_kinds_unchanged():
    assert classify("KU-RO", 0, 0).kind is TokenKind.WORD
    assert classify("GRA", 0, 0).kind is TokenKind.LOGOGRAM
    assert classify("VIR+[?]", 0, 0).kind is TokenKind.LOGOGRAM
    assert classify("5", 0, 0).kind is TokenKind.NUMERAL


def test_corpus_variant_sign_tokens_regained():
    """The bundled corpus has exactly 27 standalone subscripted signs and
    variant-letter ligatures (5x PA₃, 3x TA₂, 3x RA₂, 2x PU₂, 7x VIR+*313a/b/c,
    2x CAPm+KU, 3x OLE/GRA+QIf, 1x GRA+BOSm, 1x VINb+WI); they classify as
    logograms and no longer fall out of the token-kind stats as UNKNOWN."""
    c = aegean.load("lineara")
    marked = [
        t for d in c for t in d.tokens
        if any(ch in t.text for ch in "₂₃₄") or re.search(r"[a-z]", t.text)
    ]
    regained = [t for t in marked if t.kind is TokenKind.LOGOGRAM]
    assert len(regained) == 27
    assert not [
        t for t in marked
        if t.kind is TokenKind.UNKNOWN and t.text in {"PA₃", "TA₂", "RA₂", "PU₂"}
    ]
    # the prose strays in the data stay UNKNOWN
    kinds = {t.text: t.kind for d in c for t in d.tokens}
    assert kinds["None"] is TokenKind.UNKNOWN
    assert kinds["double mina"] is TokenKind.UNKNOWN


def test_word_to_phonetic_subscripted_signs_not_read_as_plain():
    # RA₂/PA₃/PU₂ are distinct signs with no shared Linear B value in the
    # bundled table: they fall through lowercased (the unknown-sign path)
    # instead of borrowing the plain series' reading.
    assert word_to_phonetic("SA-RA₂") == "sara₂"
    assert word_to_phonetic("SA-RA₂") != word_to_phonetic("SA-RA")
    assert word_to_phonetic("KU-PA₃-NU") == "kupa₃nu"
    assert word_to_phonetic("KI-RE-TA₂") == "kireta₂"
    assert word_to_phonetic("A-PU₂-NA-DU") == "apu₂nadu"


def test_word_to_phonetic_subscript_value_comes_from_the_table_only():
    # a plain-series value must not leak onto the subscripted sign...
    assert word_to_phonetic("SA-RA₂", {"RA": "xx"}) == "sara₂"
    # ...but a value attested for the exact sign reads it
    assert word_to_phonetic("SA-RA₂", {"RA₂": "rya"}) == "sarya"


def test_word_to_phonetic_unchanged_for_plain_and_star_signs():
    assert word_to_phonetic("KU-RO") == "kuro"
    assert word_to_phonetic("PA-I-TO") == "paito"
    assert word_to_phonetic("KU-*118") == "ku*118"  # unread star label falls through
