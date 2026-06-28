"""Baseline Greek POS tagging — closed classes are reliable; open-class is a
suffix heuristic."""

from __future__ import annotations

import pytest

from aegean.greek import pos_tag, pos_tags


@pytest.mark.parametrize(
    "word,tag",
    [
        ("ὁ", "DET"), ("τὸν", "DET"), ("τῆς", "DET"),   # article (grave folded)
        ("ἐν", "ADP"), ("πρὸς", "ADP"), ("εἰς", "ADP"),  # prepositions
        ("καὶ", "CCONJ"), ("δὲ", "CCONJ"),               # conjunctions
        ("μὲν", "PART"), ("οὐκ", "PART"), ("μή", "PART"),  # particles
        ("αὐτὸν", "PRON"), ("ὅς", "PRON"),               # pronouns
        ("ἦν", "VERB"), ("ἐστίν", "VERB"),               # copula paradigm
    ],
)
def test_closed_class_tags(word, tag):
    assert pos_tag(word) == tag


def test_open_class_heuristic_and_fallback():
    assert pos_tag("λόγος") == "NOUN"      # unknown → NOUN fallback
    assert pos_tag("λέγουσιν") == "VERB"   # -ουσιν verb ending
    assert pos_tag("γράφειν") == "VERB"    # -ειν infinitive


def test_numbers_and_punctuation():
    assert pos_tag("5") == "NUM"
    assert pos_tag(".") == "PUNCT"


def test_pos_tags_over_a_sentence():
    tagged = pos_tags("ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός.")
    by_word = dict(tagged)
    assert by_word["ἐν"] == "ADP"
    assert by_word["ὁ"] == "DET"
    assert by_word["ἦν"] == "VERB"
    assert by_word[","] == "PUNCT"
    assert by_word["καὶ"] == "CCONJ"


def test_grave_is_folded_to_acute_for_lookup():
    assert pos_tag("καὶ") == pos_tag("καί") == "CCONJ"


@pytest.mark.parametrize(
    "word,tag",
    [
        # interrogative vs enclitic indefinite (told apart by the accent)
        ("τίς", "PRON"), ("τί", "PRON"), ("τις", "PRON"), ("τι", "PRON"),
        ("τίνος", "PRON"), ("τινός", "PRON"),
        # relative ὅς ἥ ὅ and a few oblique forms
        ("ὅς", "PRON"), ("ἥ", "PRON"), ("ὅ", "PRON"), ("ᾧ", "PRON"), ("ὧν", "PRON"),
        # determiners
        ("ἄλλος", "DET"), ("ἕκαστος", "DET"), ("πᾶς", "DET"),
        # cardinals (NUM) and ordinals (ADJ, per UD)
        ("εἷς", "NUM"), ("μία", "NUM"), ("ἕν", "NUM"), ("δύο", "NUM"),
        ("τρεῖς", "NUM"), ("τέσσαρες", "NUM"),
        ("πρῶτος", "ADJ"), ("δεύτερος", "ADJ"), ("τρίτος", "ADJ"),
        # remaining common particles
        ("μέντοι", "PART"), ("καίτοι", "PART"), ("δῆτα", "PART"), ("γοῦν", "PART"),
        ("τοίνυν", "PART"), ("που", "PART"), ("ποτε", "PART"), ("πως", "PART"),
    ],
)
def test_added_closed_class_tags(word, tag):
    assert pos_tag(word) == tag
