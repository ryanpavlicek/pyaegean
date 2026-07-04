"""Cypriot syllabary sign→sound mapping + word transcription.

The Cypriot syllabary is more phonetically transparent than Linear B, so a transliterated word is
already close to its spoken Greek form. The values are settled (deciphered).
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ...data import load_bundled_json

_STRIP = re.compile(r"[*\[\]?]")  # editorial markers, not part of the sign value
_UNDERDOT = "̣"  # COMBINING DOT BELOW (Leiden: damaged but legible = a settled reading)


@lru_cache(maxsize=1)
def phonetic_map() -> dict[str, str]:
    return dict(load_bundled_json("cypriot", "phonetic_map.json"))


def _lookup_key(sign: str) -> str:
    # Drop the Leiden underdot before lookup, matching the sibling Cypriot lexicon and
    # the Linear B phonetic bridge; otherwise a damaged-but-legible sign (wi-ti-ḷẹ-ra-nu)
    # falls through to its raw transliteration instead of its settled value.
    recomposed = unicodedata.normalize("NFC", unicodedata.normalize("NFD", sign).replace(_UNDERDOT, ""))
    # Keyed uppercase; the IG XV convention writes signs lowercase, so fold to upper
    # or signs like XA/XE fall through as raw 'xa'/'xe' instead of ksa/kse.
    return _STRIP.sub("", recomposed).upper()


def word_to_phonetic(word: str, overrides: dict[str, str] | None = None) -> str:
    """Convert a hyphenated Cypriot word to its phonetic Latin form.

    Unknown signs fall through lowercased. ``overrides`` lets a researcher test alternative
    sign values.
    """
    m = phonetic_map() if not overrides else {**phonetic_map(), **overrides}
    return "".join(m.get(_lookup_key(s), s.lower()) for s in word.split("-"))
