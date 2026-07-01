"""Linear A sign→sound mapping (shared Linear B values) + word transcription."""

from __future__ import annotations

import re
from functools import lru_cache

from ...data import load_bundled_json

# Only the "*" of unread sign labels (*118) is dropped for the table lookup.
# Subscripted signs (RA₂, PA₃, TA₂, PU₂) are distinct signs, not variants of
# the plain series: they are looked up as written, so they read only where the
# table attests a value for that exact sign.
_CLEAN = re.compile(r"\*")


@lru_cache(maxsize=1)
def phonetic_map() -> dict[str, str]:
    return dict(load_bundled_json("lineara", "phonetic_map.json"))


def word_to_phonetic(word: str, overrides: dict[str, str] | None = None) -> str:
    """Convert a hyphenated Linear A word to its phonetic Latin form.

    Unknown signs fall through lowercased; subscripted signs (RA₂, PA₃, ...)
    count as unknown unless the sign-values table carries a reading for that
    exact sign, never the plain series' value. ``overrides`` lets a researcher
    test alternative sign values (hypothesis testing).
    """
    m = phonetic_map() if not overrides else {**phonetic_map(), **overrides}
    return "".join(m.get(_CLEAN.sub("", s), s.lower()) for s in word.split("-"))
