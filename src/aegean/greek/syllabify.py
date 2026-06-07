"""Ancient Greek syllabification (rule-based).

Standard pedagogical rules: every syllable has one vowel/diphthong nucleus; a
single consonant between vowels joins the following syllable; a consonant
cluster splits so that the largest valid Greek onset (a single consonant, a
stop+liquid/nasal "muta cum liquida", or a known initial cluster) opens the
following syllable and the rest closes the preceding one; doubled consonants
split. This is a baseline: a few lexicalised exceptions exist that the rules
don't capture.
"""

from __future__ import annotations

import unicodedata

_VOWELS = set("αεηιουω")
_STOPS = set("πβφτδθκγχ")
_LIQUIDS_NASALS = set("λρμν")
# Two-consonant clusters that can begin a Greek word (so they stay together).
_VALID_ONSETS = {
    "στ", "σπ", "σκ", "σφ", "σθ", "σχ", "σμ", "σβ",
    "πτ", "κτ", "φθ", "χθ", "πν", "κν", "γν", "δμ", "τμ", "θν", "πς",
    "βδ", "γδ", "σς",
}
# Diphthongs (two vowels that share one nucleus). ι/υ subscript handled via base.
_DIPHTHONGS = {"αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ", "ωυ"}


def _base(ch: str) -> str:
    """Lowercase base letter with diacritics stripped (for classification)."""
    d = unicodedata.normalize("NFD", ch.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def _is_vowel(ch: str) -> bool:
    return _base(ch) in _VOWELS


def _valid_onset(cluster: list[str]) -> bool:
    """Whether a 2-consonant cluster may open a syllable."""
    if len(cluster) != 2:
        return False
    a, b = _base(cluster[0]), _base(cluster[1])
    if a == b:
        return False  # doubled consonant always splits
    if a in _STOPS and b in _LIQUIDS_NASALS:
        return True  # muta cum liquida
    return (a + b) in _VALID_ONSETS


def syllabify(word: str) -> list[str]:
    """Split a Greek word into syllables (NFC). Non-letters pass through."""
    chars = list(unicodedata.normalize("NFC", word))
    if not chars:
        return []

    # Group into vowel-nucleus and consonant units, tracking original chars.
    units: list[tuple[str, list[str]]] = []  # (kind "V"|"C", chars)
    i = 0
    while i < len(chars):
        if _is_vowel(chars[i]):
            nucleus = [chars[i]]
            # absorb a following vowel if the pair is a diphthong
            if i + 1 < len(chars) and _is_vowel(chars[i + 1]):
                pair = _base(chars[i]) + _base(chars[i + 1])
                if pair in _DIPHTHONGS:
                    nucleus.append(chars[i + 1])
                    i += 1
            units.append(("V", nucleus))
        else:
            units.append(("C", [chars[i]]))
        i += 1

    vowel_positions = [k for k, (kind, _) in enumerate(units) if kind == "V"]
    if not vowel_positions:
        return ["".join(chars)]  # no nucleus → single chunk

    # Build syllables nucleus by nucleus.
    syllables: list[str] = []
    start = 0  # index into units for the current syllable
    for vi, upos in enumerate(vowel_positions):
        is_last = vi == len(vowel_positions) - 1
        if is_last:
            end = len(units)  # last nucleus takes all trailing consonants
        else:
            next_v = vowel_positions[vi + 1]
            cluster = [units[k][1][0] for k in range(upos + 1, next_v)]
            n = len(cluster)
            if n == 0:
                onset = 0
            elif n == 1:
                onset = 1
            else:
                onset = 2 if _valid_onset(cluster[-2:]) else 1
            end = next_v - onset
        chunk = "".join("".join(units[k][1]) for k in range(start, end))
        syllables.append(chunk)
        start = end
    return syllables
