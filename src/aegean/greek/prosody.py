"""Greek prosody — syllable quantity (metrical weight).

Classifies each syllable of a word as **heavy**, **light**, or **common**
(undetermined) using the standard rules, building on
`aegean.greek.syllabify.syllabify`:

- a syllable is **heavy** if it is *closed* (ends in a consonant — "long by
  position") or its nucleus is long (η, ω, a circumflex, an iota-subscript
  vowel, or a diphthong);
- **light** if it is open with a short nucleus (ε, ο);
- **common** if it is open with a *dichronon* nucleus (α, ι, υ), whose length
  isn't determinable from spelling alone.

Baseline scope: quantities are computed within a single word. Two cross-word /
contextual refinements are intentionally not applied: a short vowel before a
mute+liquid cluster is reported at its natural quantity here (the cluster
syllabifies as the next syllable's onset, so the syllable stays open: πέ-τρος
scans light), not the either-way *common* that `aegean.greek.meter` applies,
and word-final length before a following word isn't resolved. These are leads
for a full metrical scansion, not a finished scanner.
"""

from __future__ import annotations

import unicodedata

from .syllabify import DOUBLE_CONSONANTS, syllabify

_LONG = set("ηω")
_SHORT = set("εο")
_COMMON = set("αιυ")  # dichrona
_VOWELS = _LONG | _SHORT | _COMMON
_DIPHTHONGS = {"αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ", "ωυ"}
_CIRCUMFLEX = "͂"
_IOTA_SUBSCRIPT = "ͅ"

HEAVY = "heavy"
LIGHT = "light"
COMMON = "common"


def _onset_is_double(syllable: str) -> bool:
    """Whether the syllable begins with a double consonant (ζ/ξ/ψ), which is two
    consonants and so makes the preceding open syllable long by position."""
    for c in unicodedata.normalize("NFD", syllable):
        if unicodedata.combining(c):
            continue
        return c.lower() in DOUBLE_CONSONANTS
    return False


def _quantity(syllable: str, next_syllable: str | None = None) -> str:
    nfd = unicodedata.normalize("NFD", syllable)
    long_mark = _CIRCUMFLEX in nfd or _IOTA_SUBSCRIPT in nfd
    base = [c.lower() for c in nfd if not unicodedata.combining(c)]
    nucleus = "".join(c for c in base if c in _VOWELS)
    closed = bool(base) and base[-1] not in _VOWELS

    if closed:
        return HEAVY  # long by position (a consonant closes this syllable)
    # Long by position when the next syllable opens with a double consonant (ζ/ξ/ψ): it is
    # written as one letter, so it does not close this syllable, but it counts as two
    # consonants (Smyth §144). Without this the vowel before ζ/ξ/ψ was reported short.
    if next_syllable is not None and _onset_is_double(next_syllable):
        return HEAVY
    if long_mark or (len(nucleus) == 2 and nucleus in _DIPHTHONGS):
        return HEAVY
    if len(nucleus) == 1:
        v = nucleus[0]
        if v in _LONG:
            return HEAVY
        if v in _SHORT:
            return LIGHT
        return COMMON  # dichronon, open syllable
    # No single determinable nucleus (e.g. hiatus or vowel-less chunk).
    return COMMON


def _quantities(syllables: list[str]) -> list[str]:
    return [
        _quantity(s, syllables[i + 1] if i + 1 < len(syllables) else None)
        for i, s in enumerate(syllables)
    ]


def syllable_quantities(word: str) -> list[str]:
    """The metrical quantity of each syllable: ``"heavy"`` / ``"light"`` /
    ``"common"`` (in syllable order)."""
    return _quantities(syllabify(word))


def scan(word: str) -> list[tuple[str, str]]:
    """``(syllable, quantity)`` pairs for a word."""
    sylls = syllabify(word)
    return list(zip(sylls, _quantities(sylls)))
