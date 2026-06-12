"""Cypriot syllabary sign→sound mapping + word transcription.

The Cypriot syllabary is more phonetically transparent than Linear B, so a transliterated word is
already close to its spoken Greek form. The values are settled (deciphered).
"""

from __future__ import annotations

import re
from functools import lru_cache

from ...data import load_bundled_json

_STRIP = re.compile(r"[*\[\]?]")  # editorial markers, not part of the sign value


@lru_cache(maxsize=1)
def phonetic_map() -> dict[str, str]:
    return dict(load_bundled_json("cypriot", "phonetic_map.json"))


def word_to_phonetic(word: str, overrides: dict[str, str] | None = None) -> str:
    """Convert a hyphenated Cypriot word to its phonetic Latin form.

    Unknown signs fall through lowercased. ``overrides`` lets a researcher test alternative
    sign values.
    """
    m = phonetic_map() if not overrides else {**phonetic_map(), **overrides}
    return "".join(m.get(_STRIP.sub("", s), s.lower()) for s in word.split("-"))
