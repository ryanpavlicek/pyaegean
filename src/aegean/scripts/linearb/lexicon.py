"""Bridge from Linear B to the Greek track: Mycenaean words → their Classical Greek readings.

Linear B writes Mycenaean Greek, so a transliterated word resolves to a Greek lemma — ``PO-ME``
is ποιμήν ("shepherd"), ``WA-NA-KA`` is ϝάναξ/ἄναξ ("king"). The bundled lexicon holds the
well-established equations; pass a returned lemma to :func:`aegean.greek.gloss` /
:func:`aegean.greek.lookup` (with the LSJ backend active) for the full dictionary entry.
"""

from __future__ import annotations

import re
from functools import lru_cache

from ...data import load_bundled_json

_STRIP = re.compile(r"[\[\]?]")           # editorial markers
_SUBSCRIPT = str.maketrans("₂₃₄", "234")  # normalize a₂ ↔ a2


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, dict[str, str]]:
    return dict(load_bundled_json("linearb", "lexicon.json"))


def _norm(word: str) -> str:
    return _STRIP.sub("", word.upper().translate(_SUBSCRIPT))


def greek_reading(word: str) -> tuple[str, str] | None:
    """The Classical Greek ``(lemma, gloss)`` for a transliterated Linear B word, or ``None``.

    With the LSJ backend active (:func:`aegean.greek.use_lsj`), pass the returned lemma to
    :func:`aegean.greek.lookup` for the full entry.
    """
    entry = _lexicon().get(_norm(word))
    return (entry["lemma"], entry["gloss"]) if entry else None


def gloss(word: str) -> str | None:
    """A short English gloss for a Linear B word, or ``None`` if it is not in the lexicon."""
    reading = greek_reading(word)
    return reading[1] if reading else None
