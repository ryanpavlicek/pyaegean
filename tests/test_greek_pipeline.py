"""Greek NLP stages: tokenize, syllabify, accent analysis, baseline lemmatize."""

from __future__ import annotations

import pytest

from aegean.core.model import TokenKind
from aegean.greek import (
    accentuation,
    lemmatize,
    lemmatize_verbose,
    sentences,
    syllabify,
    tokenize,
    tokenize_words,
)


# ── tokenization ─────────────────────────────────────────────────────────────
def test_tokenize_words_drops_punctuation():
    assert tokenize_words("ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός.") == [
        "ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος", "καὶ", "θεός"
    ]


def test_tokenize_keeps_elision_apostrophe():
    # Sappho's elided forms keep their internal/trailing apostrophe in one token
    words = tokenize_words("ποικιλόθρον’ ἀθανάτ’ Ἀφρόδιτα")
    assert words == ["ποικιλόθρον’", "ἀθανάτ’", "Ἀφρόδιτα"]


def test_tokenize_types_words_and_punct():
    toks = tokenize("λόγος, καί")
    assert [(t.text, t.kind) for t in toks] == [
        ("λόγος", TokenKind.WORD),
        (",", TokenKind.PUNCT),
        ("καί", TokenKind.WORD),
    ]


def test_sentences_split_on_greek_punctuation():
    assert sentences("ἐν ἀρχῇ ἦν ὁ λόγος. καὶ θεός ἦν;") == [
        "ἐν ἀρχῇ ἦν ὁ λόγος",
        "καὶ θεός ἦν",
    ]


# ── syllabification ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "word,expected",
    [
        ("λόγος", ["λό", "γος"]),
        ("ἄνθρωπος", ["ἄν", "θρω", "πος"]),   # muta cum liquida: θρ stays together
        ("θάλασσα", ["θά", "λασ", "σα"]),       # doubled σσ splits
        ("Μῆνιν", ["Μῆ", "νιν"]),
        ("ποικιλόθρον", ["ποι", "κι", "λό", "θρον"]),  # οι diphthong
        ("ἀρχῇ", ["ἀρ", "χῇ"]),
        ("Ἀχιλῆος", ["Ἀ", "χι", "λῆ", "ος"]),  # vowel hiatus η|ο
    ],
)
def test_syllabify(word, expected):
    assert syllabify(word) == expected


# ── accent analysis ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "word,acc,pos,cls",
    [
        ("λόγος", "acute", 2, "paroxytone"),
        ("θεά", "acute", 1, "oxytone"),
        ("ἄνθρωπος", "acute", 3, "proparoxytone"),
        ("Μῆνιν", "circumflex", 2, "properispomenon"),
        ("πρὸς", "grave", 1, "barytone"),
    ],
)
def test_accentuation(word, acc, pos, cls):
    info = accentuation(word)
    assert info.accent_type == acc
    assert info.position_from_end == pos
    assert info.classification == cls


def test_accentuation_unaccented():
    info = accentuation("ανθρωπος")  # no accent marks
    assert info.accent_type is None
    assert info.classification is None


# ── baseline lemmatization ───────────────────────────────────────────────────
def test_lemmatize_seed_table():
    assert lemmatize("λόγου") == "λόγος"
    assert lemmatize("ἦν") == "εἰμί"
    assert lemmatize("θεόν") == "θεός"


def test_lemmatize_unknown_returns_normalized_form():
    lemma, known = lemmatize_verbose("ξενικον")
    assert known is False
    assert lemma == "ξενικον"
