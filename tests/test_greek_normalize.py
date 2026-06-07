"""Beta Code ↔ Unicode conversion and Unicode normalization for Greek."""

from __future__ import annotations

import pytest

from aegean.greek import (
    betacode_to_unicode,
    normalize,
    strip_diacritics,
    unicode_to_betacode,
)

# (beta code, expected precomposed Greek)
FORWARD = [
    ("lo/gos", "λόγος"),
    ("*mh=nin", "Μῆνιν"),
    (")/anqrwpos", "ἄνθρωπος"),
    ("(o", "ὁ"),
    ("tw=|", "τῷ"),
    ("qea/", "θεά"),
    ("*)axilh=os", "Ἀχιλῆος"),
]


@pytest.mark.parametrize("beta,greek", FORWARD)
def test_betacode_to_unicode(beta, greek):
    assert betacode_to_unicode(beta) == greek


def test_final_sigma_is_context_sensitive():
    assert betacode_to_unicode("lo/gos").endswith("ς")     # word-final → ς
    assert betacode_to_unicode("sofo/s").count("σ") == 1   # medial σ + final ς
    assert betacode_to_unicode("s1ofo/s2") == "σοφός"      # explicit s1/s2 variants


def test_sigma_variants():
    assert betacode_to_unicode("s3") == "ϲ"  # lunate sigma


@pytest.mark.parametrize("_,greek", FORWARD)
def test_unicode_betacode_roundtrip(_, greek):
    # unicode → beta → unicode is stable for supported text
    assert betacode_to_unicode(unicode_to_betacode(greek)) == greek


def test_strip_diacritics():
    assert strip_diacritics("ἄνθρωπος") == "ανθρωπος"
    assert strip_diacritics("τῷ") == "τω"
    assert strip_diacritics("Ἀχιλῆος") == "Αχιληος"


def test_normalize_nfc_default():
    # combining acute on Greek omicron composes to the precomposed ό
    decomposed = "ο" + "́"  # omicron (U+03BF) + combining acute (U+0301)
    assert normalize(decomposed) == "ό"
    assert len(normalize(decomposed)) == 1
    assert normalize(decomposed, "NFD") == decomposed
