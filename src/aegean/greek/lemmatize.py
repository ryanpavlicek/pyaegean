"""Baseline Greek lemmatization (open-data seed).

A small bundled form→lemma table (seeded from the sample corpus) plus an
identity fallback. This is the seed tier of the lemmatization cascade: the
treebank, neural, and edit-tree backends (opt-in) handle the heavier work,
and this table is the final fallback. Unknown forms are returned normalized
(NFC), unchanged — flagged via `lemmatize_verbose`.
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

    When the AGDT treebank backend is active (see `aegean.greek.use_treebank`),
    its attested, correctly-accented lemma is preferred; next, when the neural backend is
    active (see `aegean.greek.use_neural_lemmatizer`), its GreTa seq2seq prediction is
    used — it generalizes well to unseen forms (76.3%); next the trained edit-tree lemmatizer
    (see `aegean.greek.use_lemmatizer`); otherwise the bundled seed table is consulted."""
    from . import treebank

    lex = treebank.active()
    if lex is not None:
        hit = lex.lemmatize(word)
        if hit is not None:
            return hit, True
    from . import neural_lemmatizer

    if neural_lemmatizer.active() is not None:  # GreTa seq2seq — strong on unseen forms
        pred = neural_lemmatizer.predict(word)
        return pred, pred != unicodedata.normalize("NFC", word)
    from . import lemmatizer

    if lemmatizer.active() is not None:  # trained generalizer for unseen forms
        pred = lemmatizer.predict(word)
        # A prediction identical to the (normalized) form is an identity fall-through, so
        # mirror the seed-table contract: known=False when the form is returned unchanged.
        return pred, pred != unicodedata.normalize("NFC", word)
    key = unicodedata.normalize("NFC", word.lower())
    table = _lemma_table()
    if key in table:
        return table[key], True
    return unicodedata.normalize("NFC", word), False


def lemmatize(word: str) -> str:
    """The seed lemma for a form, or the normalized form itself if unknown."""
    return lemmatize_verbose(word)[0]
