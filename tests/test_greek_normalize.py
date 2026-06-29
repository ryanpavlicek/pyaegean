"""Beta Code ↔ Unicode conversion and Unicode normalization for Greek."""

from __future__ import annotations

import warnings

import pytest

from aegean.greek import (
    NormalizationWarning,
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


# (text with literal reserved punctuation, expected escaped beta code)
ROUNDTRIP_LITERALS = [
    ("(ἐν ἀρχῇ)", "`(e)n a)rxh=|`)"),         # parentheses around a phrase
    ("λόγος (ἀρχή)", "lo/gos `(a)rxh/`)"),     # parenthetical Greek gloss
    ("ἡ τιμή = 5 + 3", "h( timh/ `= 5 `+ 3"),  # arithmetic signs
    ("ὁδός | ἀγορά", "o(do/s `| a)gora/"),    # literal pipe (not iota subscript)
    ("λόγος1", "lo/gos`1"),                    # digit after final sigma, not s1
]


@pytest.mark.parametrize("text,beta", ROUNDTRIP_LITERALS)
def test_unicode_betacode_escapes_literal_punctuation(text, beta):
    # the reserved markup chars are backtick-escaped on the way out ...
    assert unicode_to_betacode(text) == beta
    # ... and read back verbatim, so Greek text with punctuation round-trips.
    assert betacode_to_unicode(unicode_to_betacode(text)) == text


def test_parenthetical_round_trips_identically():
    # the audit's headline case: a parenthetical must survive unchanged.
    text = "(ἐν ἀρχῇ)"
    assert betacode_to_unicode(unicode_to_betacode(text)) == text
    # without the escape the leading '(' would be re-read as a rough breathing.
    assert "ἑ" not in betacode_to_unicode(unicode_to_betacode(text))


def test_backtick_escape_char_itself_round_trips():
    # a literal backtick must not be mistaken for the escape introducer.
    text = "ἀρχή`τέλος"
    assert unicode_to_betacode(text) == "a)rxh/``te/los"
    assert betacode_to_unicode(unicode_to_betacode(text)) == text


def test_betacode_escape_reads_next_char_literally():
    # reader-side: `( is a literal '(', independent of the writer.
    assert betacode_to_unicode("`(a`)") == "(α)"
    assert betacode_to_unicode("a`=b") == "α=β"  # '=' would be a circumflex bare


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


# ── lenient mode (OCR / messy text repair) ───────────────────────────────────
def test_lenient_repairs_latin_lookalikes_in_greek_words():
    with pytest.warns(NormalizationWarning, match="Latin letter"):
        assert normalize("λόγoς", lenient=True) == "λόγος"  # Latin o inside a Greek word


def test_lenient_word_final_sigma():
    with pytest.warns(NormalizationWarning):
        assert normalize("λόγοs", lenient=True) == "λόγος"  # Latin s at word end → ς


def test_lenient_leaves_pure_latin_words_alone():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no warning may fire
        assert normalize("ὁ λόγος said hello", lenient=True) == "ὁ λόγος said hello"


def test_lenient_converts_betacode_remnant_diacritics():
    with pytest.warns(NormalizationWarning, match="Beta-Code remnant"):
        assert normalize("μη=νιν", lenient=True) == "μῆνιν"
    # a parenthesis after a consonant is punctuation, not a breathing
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert normalize("λόγος(", lenient=True) == "λόγος("


def test_lenient_drops_stray_combining_marks():
    stray = "́" + "ἀρχῇ"  # combining acute with no base letter
    with pytest.warns(NormalizationWarning, match="stray combining mark"):
        assert normalize(stray, lenient=True) == "ἀρχῇ"


def test_lenient_v_maps_to_upsilon_not_nu():
    # a stray Latin v in Greek OCR is a misread upsilon, not a nu:
    # the -ευς ending scanned as -εvς must repair to -ευς (βασιλεύς).
    with pytest.warns(NormalizationWarning, match="Latin letter"):
        out = normalize("βασιλεvς", lenient=True)
    assert out == "βασιλευς"
    assert "ν" not in out  # mapped to upsilon, never nu


def test_lenient_only_repairs_greek_dominated_words():
    # one Greek glyph stranded in an otherwise-Latin token does NOT trigger the
    # Latin→Greek mapping: the token is left exactly as given, and silently.
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no warning may fire
        assert normalize("modelα", lenient=True) == "modelα"
    # but a Greek-dominated token (one stray Latin o) is still repaired.
    with pytest.warns(NormalizationWarning, match="Latin letter"):
        assert normalize("λόγoς", lenient=True) == "λόγος"


def test_lenient_dominance_is_a_strict_majority():
    # a 1-Greek / 1-Latin tie is not Greek-dominated, so it is left alone.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert normalize("oα", lenient=True) == "oα"  # Latin o + Greek alpha


def test_strict_mode_is_unchanged_and_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert normalize("λόγoς") == "λόγoς"  # the Latin o survives strict mode
