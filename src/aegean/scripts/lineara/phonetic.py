"""Linear A sign→sound mapping (shared Linear B values) + word transcription."""

from __future__ import annotations

import re
from functools import lru_cache

from ...data import load_bundled_json

_CLEAN = re.compile(r"[₂₃₄*]")


@lru_cache(maxsize=1)
def phonetic_map() -> dict[str, str]:
    return dict(load_bundled_json("lineara", "phonetic_map.json"))


def word_to_phonetic(word: str, overrides: dict[str, str] | None = None) -> str:
    """Convert a hyphenated Linear A word to its phonetic Latin form.

    Unknown signs fall through lowercased. ``overrides`` lets a researcher test
    alternative sign values (hypothesis testing).
    """
    m = phonetic_map() if not overrides else {**phonetic_map(), **overrides}
    return "".join(m.get(_CLEAN.sub("", s), s.lower()) for s in word.split("-"))
