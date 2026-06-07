"""Greek accent analysis.

Identifies the accented syllable and the accent type (acute / grave /
circumflex), and classifies the word by the traditional scheme (oxytone,
paroxytone, proparoxytone, perispomenon, properispomenon, barytone). Operates
on the syllabification from :mod:`aegean.greek.syllabify`.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .syllabify import syllabify

_ACUTE = "́"
_GRAVE = "̀"
_CIRCUMFLEX = "͂"
_ACCENTS = {_ACUTE: "acute", _GRAVE: "grave", _CIRCUMFLEX: "circumflex"}

# (accent type, distance-from-end) → traditional name. Distance: 1=ultima,
# 2=penult, 3=antepenult.
_CLASSIFY = {
    ("acute", 1): "oxytone",
    ("acute", 2): "paroxytone",
    ("acute", 3): "proparoxytone",
    ("circumflex", 1): "perispomenon",
    ("circumflex", 2): "properispomenon",
    ("grave", 1): "barytone",
}


@dataclass(frozen=True, slots=True)
class AccentInfo:
    """The accent analysis of one word."""

    syllables: tuple[str, ...]
    accent_type: str | None          # "acute" | "grave" | "circumflex" | None
    position_from_end: int | None    # 1=ultima, 2=penult, 3=antepenult, else None
    classification: str | None       # oxytone / paroxytone / … / None if unaccented


def _accent_in(syllable: str) -> str | None:
    for ch in unicodedata.normalize("NFD", syllable):
        if ch in _ACCENTS:
            return _ACCENTS[ch]
    return None


def accentuation(word: str) -> AccentInfo:
    """Analyse the accent of a single Greek word."""
    sylls = syllabify(word)
    for idx, syl in enumerate(sylls):
        acc = _accent_in(syl)
        if acc is not None:
            pos = len(sylls) - idx  # 1 = ultima
            return AccentInfo(
                tuple(sylls), acc, pos, _CLASSIFY.get((acc, pos))
            )
    return AccentInfo(tuple(sylls), None, None, None)
