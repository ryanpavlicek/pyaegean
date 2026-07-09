"""Correctness tests for ``greek.profile.profile_text`` / ``TextProfile``.

``profile_text`` returns a frozen, read-only ``TextProfile`` of the OBSERVABLE
surface features of a raw string: a script observation, ``is_polytonic`` /
``looks_like_betacode`` flags, a ``majuscule_ratio`` and a digit/numeral ratio,
whether editorial brackets are present, and basic counts. It is a describe-only
primitive, so it must NOT emit an interpretive genre or out-of-distribution
label.

Every test below checks the actual profiled OUTPUT against a hand-checked input
(a known boolean, an exact ratio, a bracket present/absent contrast, a counted
number), never merely that the call runs.
"""

from __future__ import annotations

import dataclasses

import pytest

from aegean.greek import TextProfile, profile_text

# Homer, Iliad 1.1 opening, precomposed (NFC) polytonic Greek.
POLYTONIC = "μῆνιν ἄειδε θεά"
# The same words in Beta Code (ASCII letters + betacode markup).
BETACODE = "mh=nin a)/eide qea/"

# The spec names some fields exactly (is_polytonic, looks_like_betacode,
# majuscule_ratio, has_editorial_brackets) so those are asserted by name. The
# script observation, digit/numeral ratio, and counts have a less-fixed name, so
# resolve them tolerantly while still asserting the value is correct.
_SCRIPT_FIELDS = ("script", "script_guess", "guessed_script", "alphabet")
_DIGIT_FIELDS = ("digit_or_numeral_ratio", "digit_ratio", "numeral_ratio", "numeric_ratio")
_CHAR_COUNT_FIELDS = ("char_count", "n_chars", "num_chars", "chars", "length", "char_len")
_WORD_COUNT_FIELDS = ("word_count", "n_words", "num_words", "words", "token_count")


def _field_names(profile: TextProfile) -> list[str]:
    if dataclasses.is_dataclass(profile):
        return [f.name for f in dataclasses.fields(profile)]
    return [n for n in dir(profile) if not n.startswith("_")]


def _first(profile: TextProfile, names: tuple[str, ...]) -> object:
    """Return the first present attribute among ``names`` (correctness of the
    value is asserted by the caller); fail loudly if the profile carries none."""
    for name in names:
        if hasattr(profile, name):
            return getattr(profile, name)
    raise AssertionError(
        f"TextProfile exposes none of {names!r}; fields present: {_field_names(profile)}"
    )


def _script(profile: TextProfile) -> str:
    return str(_first(profile, _SCRIPT_FIELDS)).lower()


def test_profile_text_returns_a_textprofile() -> None:
    result = profile_text(POLYTONIC)
    assert isinstance(result, TextProfile)


def test_polytonic_greek_is_polytonic_and_greek_script() -> None:
    """Real Unicode polytonic Greek: accents/breathings present, Greek script,
    and NOT mistaken for Beta Code."""
    p = profile_text(POLYTONIC)
    assert p.is_polytonic is True
    assert "greek" in _script(p)
    assert p.looks_like_betacode is False


def test_betacode_string_looks_like_betacode() -> None:
    """The ASCII Beta Code transliteration is flagged as Beta Code and is not
    reported as Unicode polytonic Greek (it carries no combining diacritics)."""
    p = profile_text(BETACODE)
    assert p.looks_like_betacode is True
    assert p.is_polytonic is False


def test_all_caps_greek_has_high_majuscule_ratio() -> None:
    """An all-caps, majuscule inscription-style string reads as almost entirely
    uppercase; the lowercase form of the same text does not."""
    caps = "ΜΗΝΙΝΑΕΙΔΕΘΕΑ"  # all uppercase, no spaces -> ratio is 1.0
    p_caps = profile_text(caps)
    assert 0.99 <= p_caps.majuscule_ratio <= 1.0
    # It is still observed as Greek, just in majuscule.
    assert "greek" in _script(p_caps)

    p_lower = profile_text(POLYTONIC)  # no uppercase letters at all
    assert p_lower.majuscule_ratio == 0.0
    assert p_caps.majuscule_ratio > p_lower.majuscule_ratio


def test_editorial_brackets_are_detected() -> None:
    """A restoration in square brackets is observable apparatus; a clean line is
    not."""
    bracketed = profile_text("μῆνιν [ἄειδε] θεά")
    assert bracketed.has_editorial_brackets is True

    clean = profile_text(POLYTONIC)
    assert clean.has_editorial_brackets is False


def test_latin_english_is_latin_script_not_polytonic() -> None:
    """Plain English prose: a Latin-script (non-Greek) observation, no polytonic
    diacritics, and not Beta Code."""
    p = profile_text("The quick brown fox jumps")
    script = _script(p)
    assert "greek" not in script
    assert any(token in script for token in ("latin", "roman", "ascii"))
    assert p.is_polytonic is False
    assert p.looks_like_betacode is False


def test_digit_ratio_reflects_arabic_digits() -> None:
    """A string containing digits has a positive digit/numeral ratio; a
    digit-free string reports zero."""
    with_digits = profile_text("ἔτους 15 μηνὸς 3")
    assert float(_first(with_digits, _DIGIT_FIELDS)) > 0.0  # type: ignore[arg-type]

    without_digits = profile_text(POLYTONIC)
    assert float(_first(without_digits, _DIGIT_FIELDS)) == 0.0  # type: ignore[arg-type]


def test_counts_are_correct() -> None:
    """The character count matches a space-free string's length and the word
    count matches a three-word line."""
    chars = profile_text("αβγδε")
    assert int(_first(chars, _CHAR_COUNT_FIELDS)) == 5  # type: ignore[call-overload]

    words = profile_text(POLYTONIC)  # three whitespace-separated words
    assert int(_first(words, _WORD_COUNT_FIELDS)) == 3  # type: ignore[call-overload]


def test_empty_string_is_a_safe_zero_profile() -> None:
    """The empty string must not raise and yields an all-off, zero-count
    profile."""
    p = profile_text("")
    assert isinstance(p, TextProfile)
    assert p.is_polytonic is False
    assert p.looks_like_betacode is False
    assert p.has_editorial_brackets is False
    assert p.majuscule_ratio == 0.0
    assert float(_first(p, _DIGIT_FIELDS)) == 0.0  # type: ignore[arg-type]
    assert int(_first(p, _CHAR_COUNT_FIELDS)) == 0  # type: ignore[call-overload]
    assert int(_first(p, _WORD_COUNT_FIELDS)) == 0  # type: ignore[call-overload]


def test_ratios_are_within_the_unit_interval() -> None:
    """Every reported ratio is a proper fraction in [0, 1] (a property that must
    hold for any input, checked on a mixed-content string)."""
    p = profile_text("ΜΗΝΙΝ [abc] 123 θεά")
    assert 0.0 <= p.majuscule_ratio <= 1.0
    assert 0.0 <= float(_first(p, _DIGIT_FIELDS)) <= 1.0  # type: ignore[arg-type]


def test_profile_never_emits_a_genre_or_ood_label() -> None:
    """The profile is describe-only: it must expose no interpretive genre or
    out-of-distribution / out-of-domain label field."""
    p = profile_text(POLYTONIC)
    names = {n.lower() for n in _field_names(p)}
    for forbidden in ("genre", "ood", "out_of_distribution", "out_of_domain", "out-of"):
        assert not any(forbidden in n for n in names), (
            f"TextProfile must not carry a {forbidden!r} field; found {sorted(names)}"
        )
    assert not hasattr(p, "genre")
    assert "genre" not in repr(p).lower()


def test_profile_is_frozen() -> None:
    """``TextProfile`` is a read-only value object: its fields cannot be
    reassigned."""
    p = profile_text(POLYTONIC)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        p.is_polytonic = True  # type: ignore[misc]
