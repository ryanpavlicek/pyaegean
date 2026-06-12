"""Linear B sign→sound mapping + word transcription.

Linear B is deciphered, so these phonetic values are settled scholarship (unlike Linear A's
empirical mapping). The complex signs ``a2``/``a3``/``pu2`` are distinct from ``a``/``pu``, so
their digit is part of the value and is preserved (only editorial markers are stripped).
"""

from __future__ import annotations

import re
from functools import lru_cache

from ...data import load_bundled_json

_STRIP = re.compile(r"[*\[\]?]")           # editorial markers, not part of the sign value
_SUBSCRIPT = str.maketrans("₂₃₄", "234")   # normalize a₂ ↔ a2


@lru_cache(maxsize=1)
def phonetic_map() -> dict[str, str]:
    return dict(load_bundled_json("linearb", "phonetic_map.json"))


def word_to_phonetic(word: str, overrides: dict[str, str] | None = None) -> str:
    """Convert a hyphenated Linear B word to its phonetic Latin form.

    Unknown signs fall through lowercased. ``overrides`` lets a researcher test alternative
    sign values.
    """
    m = phonetic_map() if not overrides else {**phonetic_map(), **overrides}
    return "".join(
        m.get(_STRIP.sub("", s.translate(_SUBSCRIPT)), s.lower()) for s in word.split("-")
    )
