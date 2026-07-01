"""Diaeresis marks vowel hiatus: never a diphthong (syllabify + to_ipa).

A diaeresis on ι/υ (ϊ, ϋ, and the accented forms ΐ, ῒ, ΰ, ῢ, …) is the explicit
orthographic mark that the vowel does NOT form a diphthong with the preceding
one (Smyth §8: προ-ΐ-στη-μι). The syllabifier and the IPA transcriber both used
the bare vowel pair, merging marked hiatus into one nucleus. Known answers here
follow Smyth's syllable rules (§8 diaeresis, §140 division); the true-diphthong
controls pin that ordinary diphthongs are untouched."""

from __future__ import annotations

import unicodedata

import pytest

from aegean.greek import accentuation, syllabify, to_ipa
from aegean.greek.meter import scan_hexameter
from aegean.greek.prosody import syllable_quantities


# ── syllabify: diaeresis vowels are their own nucleus ────────────────────────
@pytest.mark.parametrize(
    "word,expected",
    [
        ("προΐστημι", ["προ", "ΐ", "στη", "μι"]),  # Smyth §8's own example (ο|ϊ)
        ("ἀϋπνία", ["ἀ", "ϋ", "πνί", "α"]),        # α|ϋ hiatus; πν a valid onset
        ("πραΰς", ["πρα", "ΰς"]),                  # two syllables (άυ would be one)
        ("Γάϊος", ["Γά", "ϊ", "ος"]),              # Latin Gāius, trisyllabic
        ("πραῢς", ["πρα", "ῢς"]),                  # grave + diaeresis (U+1FE2)
        ("Πηληϊάδεω", ["Πη", "λη", "ϊ", "ά", "δε", "ω"]),  # Il. 1.1
    ],
)
def test_diaeresis_blocks_diphthong(word, expected):
    assert syllabify(word) == expected


@pytest.mark.parametrize(
    "word,expected",
    [
        ("αἴρω", ["αἴ", "ρω"]),
        ("εὑρίσκω", ["εὑ", "ρί", "σκω"]),
        ("οὐρανός", ["οὐ", "ρα", "νός"]),
    ],
)
def test_true_diphthongs_unchanged(word, expected):
    assert syllabify(word) == expected


def test_combining_representation_matches_precomposed():
    # ι + U+0308 + U+0301 composes to ΐ under the module's NFC normalization;
    # the combining spelling must syllabify identically to the precomposed one.
    combining = "\u03c0\u03c1\u03bf\u03b9\u0308\u0301\u03c3\u03c4\u03b7\u03bc\u03b9"
    assert syllabify(combining) == ["προ", "ΐ", "στη", "μι"]


def test_uncomposable_combining_diaeresis_still_marks_hiatus():
    # ύ (acute precomposed) + a following U+0308 does not NFC-compose (blocked
    # composition), so the bare combining mark survives; it must still split
    # the vowels, and the syllables must join back to the (NFC) input.
    blocked = "\u03c0\u03c1\u03b1\u03cd\u0308\u03c2"
    sylls = syllabify(blocked)
    assert len(sylls) == 2
    assert sylls[0] == "πρα"
    assert "".join(sylls) == unicodedata.normalize("NFC", blocked)


# ── downstream consumers see the corrected boundaries ────────────────────────
def test_accentuation_of_marked_hiatus():
    info = accentuation("πραΰς")
    assert info.syllables == ("πρα", "ΰς")
    assert info.classification == "oxytone"  # acute on the (real) ultima


def test_prosody_quantities_of_marked_hiatus():
    # προ (open ο) light; ΐ (open dichronon) common; στη heavy; μι common.
    assert syllable_quantities("προΐστημι") == ["light", "common", "heavy", "common"]


def test_iliad_1_1_scansion_survives():
    # Πηληϊάδεω carries a diaeresis AND needs synizesis (-εω as one nucleus);
    # the meter's own handling of both must be undisturbed.
    sc = scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")
    assert sc.meter == "hexameter"
    assert sc.pattern == "—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×"


# ── to_ipa: marked hiatus transcribes as two nuclei in both periods ──────────
@pytest.mark.parametrize(
    "word,attic,koine",
    [
        ("προΐστημι", "proistɛːmi", "proistimi"),  # not oi̯ / y
        ("πραΰς", "prays", "prays"),               # not au̯ / av
    ],
)
def test_ipa_diaeresis_hiatus(word, attic, koine):
    assert to_ipa(word, "attic") == attic
    assert to_ipa(word, "koine") == koine


@pytest.mark.parametrize(
    "word,attic,koine",
    [
        ("οὐρανός", "uːranos", "uranos"),
        ("αὐτός", "au̯tos", "avtos"),
    ],
)
def test_ipa_true_diphthongs_unchanged(word, attic, koine):
    assert to_ipa(word, "attic") == attic
    assert to_ipa(word, "koine") == koine
