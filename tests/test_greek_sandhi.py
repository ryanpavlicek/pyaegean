"""Crasis / elision / movable-nu sandhi resolution."""

from __future__ import annotations

import unicodedata

import pytest

from aegean.greek.sandhi import ResolvedForm, resolve_sandhi, resolve_sentence

# Curated crasis cases: surface form → underlying words (Smyth §62–69).
CRASIS = [
    ("κἀγώ", ("καί", "ἐγώ")),
    ("τἀμά", ("τὰ", "ἐμά")),
    ("χἠ", ("καί", "ἡ")),
    ("τοὔνομα", ("τὸ", "ὄνομα")),
    ("κᾆτα", ("καί", "εἶτα")),
    ("τἆλλα", ("τὰ", "ἄλλα")),
    ("κἀκεῖνος", ("καί", "ἐκεῖνος")),
]


@pytest.mark.parametrize("surface,words", CRASIS)
def test_crasis_curated(surface: str, words: tuple[str, ...]) -> None:
    r = resolve_sandhi(surface)
    assert r.kind == "crasis"
    assert not r.uncertain
    assert r.resolved
    assert r.words == words


def test_crasis_unlisted_is_flagged_not_guessed() -> None:
    # A coronis-bearing form absent from the lexicon must be left intact + flagged.
    fake = unicodedata.normalize("NFC", "ζ" + "α" + "̓" + "βγ")  # consonant + smooth-vowel
    r = resolve_sandhi(fake)
    assert r.kind == "crasis"
    assert r.uncertain
    assert r.words == (fake,)  # never over-expanded


def test_elision_proclitic() -> None:
    r = resolve_sandhi("δ'")
    assert r.kind == "elision"
    assert not r.uncertain
    assert r.words == ("δέ",)


def test_elision_listed_full_word() -> None:
    r = resolve_sandhi("ταῦτ'")  # listed full-word elision: ταῦτ' -> ταῦτα
    assert r.kind == "elision"
    assert not r.uncertain
    assert r.words == ("ταῦτα",)


def test_elision_unrecoverable_is_flagged() -> None:
    r = resolve_sandhi("ἔδωκ'")  # not a listed proclitic/word
    assert r.kind == "elision"
    assert r.uncertain
    assert r.words == ("ἔδωκ",)  # clipped stem kept, not invented


def test_movable_nu_negative_particle() -> None:
    for surface in ("οὐκ", "οὐχ"):
        r = resolve_sandhi(surface)
        assert r.kind == "movable-nu"
        assert r.words == ("οὐ",)
    # bare οὐ carries no sandhi
    assert resolve_sandhi("οὐ").kind is None


def test_movable_nu_verb_ending() -> None:
    r = resolve_sandhi("ἐστίν")
    assert r.kind == "movable-nu"
    assert r.words == ("ἐστίν",)  # citation form kept
    assert "ἐστί" in r.alternatives  # the ν-less alternant recorded


def test_non_sandhi_word_passes_through_unchanged() -> None:
    for w in ("ἄνθρωπος", "λόγος", "θεά", "αὐτός", "εὐθύς"):
        r = resolve_sandhi(w)
        assert r.kind is None
        assert not r.uncertain
        assert r.words == (w,)


def test_returns_resolvedform() -> None:
    assert isinstance(resolve_sandhi("λόγος"), ResolvedForm)


def test_resolve_sentence_flattens() -> None:
    forms = resolve_sentence("κἀγώ δ' οὐκ ἄνθρωπος")
    flat = [w for r in forms for w in r.words]
    assert flat == ["καί", "ἐγώ", "δέ", "οὐ", "ἄνθρωπος"]
    # one ResolvedForm per surface word
    assert len(forms) == 4


def test_diphthong_breathing_is_not_crasis() -> None:
    # smooth breathing on the second vowel of an initial diphthong must NOT trip
    # the coronis detector (regression guard).
    for w in ("οὐ", "αὐτός", "εὐθύς", "οἶνος"):
        assert resolve_sandhi(w).kind != "crasis"
