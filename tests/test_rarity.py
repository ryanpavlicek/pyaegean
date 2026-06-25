"""Terminology rarity — corpus-relative difficulty scoring, fully offline.

A tiny hand-built Greek reference corpus (with controlled frequencies, including common
function words) is the basis; the score of a text is relative to it.
"""

from __future__ import annotations

import pytest

from aegean import greek
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind

# common → rare; includes function words so they score low (as in a real reference corpus)
REF = {"ὁ": 50, "καί": 40, "θεός": 10, "λόγος": 8, "ἄνθρωπος": 4, "σφάκελος": 1}


def _corpus(freq: dict[str, int]) -> Corpus:
    words = [w for w, n in freq.items() for _ in range(n)]
    toks = [Token(text=w, kind=TokenKind.WORD) for w in words]
    doc = Document(id="d0", script_id="greek", tokens=toks, lines=[list(range(len(toks)))])
    return Corpus(documents=[doc], script_id="greek")


def test_rarity_orders_by_corpus_frequency() -> None:
    r = greek.terminology_rarity("ὁ λόγος σφάκελος", _corpus(REF))
    by = {w.word: w for w in r.words}
    assert by["ὁ"].rarity < by["λόγος"].rarity < by["σφάκελος"].rarity
    assert by["ὁ"].label == "common" and by["σφάκελος"].label == "hapax"


def test_absent_word_is_maximally_rare() -> None:
    r = greek.terminology_rarity("νεολογισμος", _corpus(REF))  # not in the reference corpus
    assert r.words[0].count == 0
    assert r.words[0].rarity == pytest.approx(1.0) and r.words[0].label == "absent"


def test_overall_higher_for_rarer_text() -> None:
    c = _corpus(REF)
    easy = greek.terminology_rarity("ὁ καί θεός", c).overall
    hard = greek.terminology_rarity("σφάκελος ἄνθρωπος", c).overall
    assert hard > easy


def test_gold_lemma_annotation_is_used() -> None:
    # a token carrying a gold lemma is counted by that lemma — no lemmatizer needed
    tok = Token(text="λόγῳ", kind=TokenKind.WORD, annotations={"lemma": "λόγος"})
    doc = Document(id="d", script_id="greek", tokens=[tok, tok, tok], lines=[[0, 1, 2]])
    r = greek.terminology_rarity("λόγος", Corpus(documents=[doc], script_id="greek"))
    assert r.words[0].lemma == "λόγος" and r.words[0].count == 3


def test_hardest_surfaces_rare_terms() -> None:
    r = greek.terminology_rarity("ὁ θεός σφάκελος", _corpus(REF))
    assert r.hardest(1)[0].word == "σφάκελος"


def test_empty_text() -> None:
    r = greek.terminology_rarity("", _corpus(REF))
    assert r.overall == 0.0 and r.words == ()
