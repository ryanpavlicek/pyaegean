"""Bridge from the Cypriot syllabary to Greek: Arcado-Cypriot words → their Greek readings.

The Cypriot syllabary writes Greek, so a transliterated word resolves to a Greek lemma —
``PA-SI-LE-U-SE`` is βασιλεύς ("king"). The bundled lexicon holds the well-established
equations; pass a returned lemma to `aegean.greek.gloss` / `aegean.greek.lookup`
(with the LSJ backend active) for the full dictionary entry.
"""

from __future__ import annotations

import re
from functools import lru_cache

from ...data import load_bundled_json

_STRIP = re.compile(r"[\[\]?]")  # editorial markers


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, dict[str, str]]:
    return dict(load_bundled_json("cypriot", "lexicon.json"))


def _norm(word: str) -> str:
    return _STRIP.sub("", word.upper())


def greek_reading(word: str) -> tuple[str, str] | None:
    """The Greek ``(lemma, gloss)`` for a transliterated Cypriot word, or ``None``."""
    entry = _lexicon().get(_norm(word))
    return (entry["lemma"], entry["gloss"]) if entry else None


def gloss(word: str) -> str | None:
    """A short English gloss for a Cypriot word, or ``None`` if it is not in the lexicon."""
    reading = greek_reading(word)
    return reading[1] if reading else None
