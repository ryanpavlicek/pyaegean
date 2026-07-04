"""Linear B sign→sound mapping + word transcription.

Linear B is deciphered, so these phonetic values are settled scholarship (unlike Linear A's
empirical mapping). The complex signs ``a2``/``a3``/``pu2`` are distinct from ``a``/``pu``, so
their digit is part of the value and is preserved (only editorial markers are stripped).
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ...data import load_bundled_json

_STRIP = re.compile(r"[*\[\]?]")           # editorial markers, not part of the sign value
_SUBSCRIPT = str.maketrans("₂₃₄", "234")   # normalize a₂ ↔ a2
_UNDERDOT = "̣"  # COMBINING DOT BELOW (Leiden: damaged but legible = a known reading)


@lru_cache(maxsize=1)
def phonetic_map() -> dict[str, str]:
    return dict(load_bundled_json("linearb", "phonetic_map.json"))


def _lookup_key(sign: str) -> str:
    """Normalize one transliterated sign to its uppercase sign-table key.

    Folds subscripts (a₂ -> A2), drops editorial markers, and removes the Leiden
    underdot (U+0323, "damaged but legible" = a settled reading) — the sibling lexicon
    bridge strips it too, so `pọ-me` reads as `pome`, not the raw `pọme`. Without this a
    damaged-but-legible DAMOS sign silently falls through to its transliteration.
    """
    recomposed = unicodedata.normalize("NFC", unicodedata.normalize("NFD", sign).replace(_UNDERDOT, ""))
    return _STRIP.sub("", recomposed.translate(_SUBSCRIPT)).upper()


def word_to_phonetic(word: str, overrides: dict[str, str] | None = None) -> str:
    """Convert a hyphenated Linear B word to its phonetic Latin form.

    Unknown signs fall through lowercased. ``overrides`` lets a researcher test alternative
    sign values.
    """
    m = phonetic_map() if not overrides else {**phonetic_map(), **overrides}
    # The sign table is keyed uppercase; lowercase input is the DAMOS (and general
    # scholarly) convention, so fold to upper before lookup or the Q-/Z-series and
    # other signs silently fall through to their raw transliteration.
    return "".join(m.get(_lookup_key(s), s.lower()) for s in word.split("-"))
