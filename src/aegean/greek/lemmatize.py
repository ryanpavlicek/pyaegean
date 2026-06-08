"""Baseline Greek lemmatization (open-data seed).

A small bundled form→lemma table (seeded from the sample corpus) plus an
identity fallback. This is a **baseline** placeholder for v0.1: a real
morphological analyzer / Morpheus-style engine and full treebank-derived tables
land in the deeper Greek NLP track (see docs/PLAN.md). Unknown forms are
returned normalized (NFC), unchanged — flagged via :func:`lemmatize_verbose`.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from ..data import load_bundled_json


@lru_cache(maxsize=1)
def _lemma_table() -> dict[str, str]:
    raw = load_bundled_json("greek", "lemmata.json")
    # Normalize keys to lowercase NFC so lookup is robust to input form.
    return {
        unicodedata.normalize("NFC", k.lower()): unicodedata.normalize("NFC", v)
        for k, v in raw.items()
    }


def lemmatize_verbose(word: str) -> tuple[str, bool]:
    """Return ``(lemma, known)``. ``known`` is False when the form wasn't found and
    the (normalized) input is returned unchanged.

    When the AGDT treebank backend is active (see :func:`aegean.greek.use_treebank`),
    its attested, correctly-accented lemma is preferred; otherwise the bundled seed
    table is consulted."""
    from . import treebank

    lex = treebank.active()
    if lex is not None:
        hit = lex.lemmatize(word)
        if hit is not None:
            return hit, True
    key = unicodedata.normalize("NFC", word.lower())
    table = _lemma_table()
    if key in table:
        return table[key], True
    return unicodedata.normalize("NFC", word), False


def lemmatize(word: str) -> str:
    """The seed lemma for a form, or the normalized form itself if unknown."""
    return lemmatize_verbose(word)[0]
