"""Invisible format characters must not silently fabricate a lemma.

Copying Greek out of a PDF, a browser, or a word processor routinely carries a
zero-width space, soft hyphen, word joiner, or BOM into the middle of a word.
Nothing is visible, but the form stops matching any lexicon key, so an ATTESTED
lookup degrades into an ending-rule guess that invents a non-word *and* keeps the
invisible character inside it -- reported as ``LemmaSource.RULE``, which
`needs_review` treats as grounded. The user has no way to see why.

``lenient=True`` is exactly the documented home for this ("repairs common artifacts
of OCR'd or half-converted text"), and it warns per repair class. Strict
``normalize`` keeps its contract: it is Unicode normalization and nothing else.
"""

from __future__ import annotations

import unicodedata
import warnings

import pytest


from aegean import greek
from aegean.greek.normalize import NormalizationWarning


@pytest.fixture(autouse=True, scope="module")
def _restore_backends():
    """Leave the process as this module found it.

    Backend activation is global session state, so a module that turns one on and walks
    away changes what unrelated tests see -- which under ``pytest -n`` means a different
    worker, and a failure with no visible cause. Everything this file activates is turned
    off again here."""
    yield
    from aegean import greek

    for name in (
        "disable_neural_pipeline",
        "disable_treebank",
        "disable_lsj",
        "disable_lexicon",
        "disable_paradigms",
        "disable_tagger",
        "disable_parser",
        "disable_lemmatizer",
        "disable_neural_lemmatizer",
        "disable_calibration",
    ):
        try:
            getattr(greek, name)()
        except Exception:  # pragma: no cover - a backend that was never active
            pass


INVISIBLES = {
    "zero-width space": "​",
    "zero-width non-joiner": "‌",
    "zero-width joiner": "‍",
    "soft hyphen": "­",
    "word joiner": "⁠",
    "byte order mark": "﻿",
    "left-to-right mark": "‎",
}


@pytest.mark.parametrize("name,char", sorted(INVISIBLES.items()))
def test_lenient_drops_invisible_format_characters(name: str, char: str) -> None:
    dirty = "ἀνθ" + char + "ρώπου"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cleaned = greek.normalize(dirty, lenient=True)
    assert cleaned == "ἀνθρώπου", name
    assert any(issubclass(w.category, NormalizationWarning) for w in caught), name


@pytest.mark.parametrize("char", sorted(INVISIBLES.values()))
def test_strict_normalize_keeps_its_documented_contract(char: str) -> None:
    # Strict normalize is Unicode normalization; it must not silently drop content.
    dirty = "ἀνθ" + char + "ρώπου"
    assert greek.normalize(dirty) == unicodedata.normalize("NFC", dirty)


def test_clean_text_is_untouched_and_warns_nothing() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert greek.normalize("ἀνθρώπου", lenient=True) == "ἀνθρώπου"
    assert not [w for w in caught if issubclass(w.category, NormalizationWarning)]


def test_every_shipped_corpus_is_free_of_format_characters() -> None:
    """The premise that makes this change inert for published numbers.

    If a corpus ever ships Cf characters, stripping them in lenient mode could move
    a measured value, and this test says so before that can happen quietly.
    """
    import aegean

    for corpus_id in ("greek", "nt"):
        corpus = aegean.load(corpus_id)
        offenders = [
            token.text
            for document in corpus.documents
            for token in document.tokens
            if any(unicodedata.category(ch) == "Cf" for ch in token.text)
        ]
        assert not offenders, f"{corpus_id} carries format characters: {offenders[:5]}"


def test_lenient_repairs_compose_with_the_existing_ones() -> None:
    # An invisible character AND a Latin homoglyph in one word: both repaired.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cleaned = greek.normalize("​λόγoς", lenient=True)
    assert "​" not in cleaned
    assert cleaned == "λόγος"
    assert len([w for w in caught if issubclass(w.category, NormalizationWarning)]) >= 2


def test_lemma_lookup_recovers_after_the_repair() -> None:
    greek.use_treebank()
    dirty = "ἀνθ​ρώπου"
    before = greek.lemmatize_sourced(dirty)
    after = greek.lemmatize_sourced(greek.normalize(dirty, lenient=True))
    assert "​" in before[0], "the defect: the invented lemma carried the invisible char"
    assert after[0] == "ἄνθρωπος"
    assert after[1].name == "ATTESTED"
