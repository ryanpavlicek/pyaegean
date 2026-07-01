"""Ancient Greek syllabification (rule-based, with a curated exception lexicon).

Standard pedagogical rules: every syllable has one vowel/diphthong nucleus; a
vowel written with a diaeresis (ϊ, ϋ) marks hiatus and is its own nucleus, never
the second member of a diphthong (Smyth §8: προ-ΐ-στη-μι); a single consonant
between vowels joins the following syllable; a consonant cluster splits so that
the largest valid Greek onset (a single consonant, a stop+liquid/nasal "muta cum
liquida", or a known initial cluster) opens the following syllable and the rest
closes the preceding one; doubled consonants split.

Pure phonotactics missplits **compounds**, which divide at the point of union
(Smyth §140): rule-only output gives ``εἰ-σφέ-ρω`` where the correct division is
``εἰσ-φέ-ρω``. A small curated lexicon of such lexicalised forms is consulted
before the rule engine (`_EXCEPTIONS` below — contributions welcome, see
``CONTRIBUTING.md``). Forms not in the lexicon, including inflected variants of
listed compounds, fall back to the rules.
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
_DIAERESIS = "̈"  # combining diaeresis (dialytika)

# Lexicalised exceptions the phonotactic rules can't capture: compounds divide
# at the point of union (Smyth §140), so the prefix keeps its final consonant
# even where the cluster could open the next syllable (σφ, σκ, κλ, …). Keys are
# NFC dictionary forms; values are the correct division. Every entry must
# differ from the rule engine's output (tests enforce this).
_EXCEPTIONS: dict[str, tuple[str, ...]] = {
    # ἐκ- compounds (κ + liquid/nasal would join the next syllable by rule)
    "ἐκλείπω": ("ἐκ", "λεί", "πω"),
    "ἐκλύω": ("ἐκ", "λύ", "ω"),
    "ἐκμανθάνω": ("ἐκ", "μαν", "θά", "νω"),
    # εἰσ- compounds (σ + stop is a valid onset by rule)
    "εἰσφέρω": ("εἰσ", "φέ", "ρω"),
    "εἰσφορά": ("εἰσ", "φο", "ρά"),
    "εἰσβαίνω": ("εἰσ", "βαί", "νω"),
    "εἰσπέμπω": ("εἰσ", "πέμ", "πω"),
    # προσ- compounds
    "προσφέρω": ("προσ", "φέ", "ρω"),
    "προσβάλλω": ("προσ", "βάλ", "λω"),
    "προσκυνέω": ("προσ", "κυ", "νέ", "ω"),
    "προσμένω": ("προσ", "μέ", "νω"),
    # δυσ- compounds
    "δυσμενής": ("δυσ", "με", "νής"),
    "δυσχερής": ("δυσ", "χε", "ρής"),
    "δύσκολος": ("δύσ", "κο", "λος"),
    "δύσφημος": ("δύσ", "φη", "μος"),
}


def _base(ch: str) -> str:
    """Lowercase base letter with diacritics stripped (for classification)."""
    d = unicodedata.normalize("NFD", ch.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def _is_vowel(ch: str) -> bool:
    return _base(ch) in _VOWELS


def _marks_hiatus(ch: str) -> bool:
    """Whether ``ch`` carries a diaeresis (ϊ, ϋ, ΐ, ῧ, …): the explicit mark that
    the vowel does NOT form a diphthong with the preceding one (Smyth §8)."""
    return _DIAERESIS in unicodedata.normalize("NFD", ch)


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
    """Split a Greek word into syllables (NFC). Non-letters pass through.

    Lexicalised compound divisions (`_EXCEPTIONS`, Smyth §140) take precedence
    over the phonotactic rules; the original casing is preserved."""
    nfc = unicodedata.normalize("NFC", word)
    exception = _EXCEPTIONS.get(nfc) or _EXCEPTIONS.get(nfc.lower())
    if exception is not None and len("".join(exception)) == len(nfc):
        # slice the original by the exception's syllable lengths → casing kept
        out, start = [], 0
        for syl in exception:
            out.append(nfc[start:start + len(syl)])
            start += len(syl)
        return out
    return _rule_syllabify(nfc)


def _rule_syllabify(word: str) -> list[str]:
    """The phonotactic rule engine (no exception lexicon)."""
    chars = list(unicodedata.normalize("NFC", word))
    if not chars:
        return []

    # Group into vowel-nucleus and consonant units, tracking original chars.
    units: list[tuple[str, list[str]]] = []  # (kind "V"|"C", chars)
    i = 0
    while i < len(chars):
        if _is_vowel(chars[i]):
            nucleus = [chars[i]]
            # absorb a following vowel if the pair is a diphthong; a diaeresis on
            # the second vowel (προΐστημι, πραΰς) marks hiatus and blocks the merge
            if i + 1 < len(chars) and _is_vowel(chars[i + 1]):
                pair = _base(chars[i]) + _base(chars[i + 1])
                hiatus = _marks_hiatus(chars[i + 1]) or (
                    # a combining diaeresis NFC could not fuse into the vowel
                    i + 2 < len(chars) and chars[i + 2] == _DIAERESIS
                )
                if pair in _DIPHTHONGS and not hiatus:
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
