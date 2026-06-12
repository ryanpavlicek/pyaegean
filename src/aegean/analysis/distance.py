"""Weighted phonetic edit distance, phonetic class schemes, root extraction,
and sequence-level Levenshtein.

A faithful port of the distance / scheme / sequence parts of the workbench
``src/lib/algorithms.ts``; results match the shared golden fixtures.

**Exploratory.** The cross-linguistic phonetic distance scores a substitution
as cheap (vowel↔vowel or same articulatory class) or expensive ("far"); *which*
phonemes count as same-class is a linguistic judgement, exposed to the
researcher via `PhoneticScheme`. A small distance between a Linear A word
and a reconstructed form is a lead to weigh, never proof — the script is
undeciphered.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

# ── Phonetic class scheme (researcher-configurable) ──────────────────────────
# Base vowel set — plain a/e/i/o/u plus the long (macron), circumflex, and acute
# variants that appear in the comparison wordlists. Vowel membership was an
# unambiguous fix, not a judgement call, so it is not part of the scheme.
BASE_VOWELS = "aeiou" + "āēīōū" + "âêîôû" + "áéíóú" + "ḗṓ"

# Base consonant classes — Linear A's own inventory plus the "clear win"
# extensions (emphatic ṭ, palatovelars ḱ/ǵ, velar fricative ḫ). The contested
# members are layered on per the active scheme. Index positions are referenced
# below, so keep them stable.
BASE_CONSONANT_CLASSES: list[list[str]] = [
    ["p", "b"],                          # 0 labials
    ["t", "d", "ṭ"],                     # 1 dentals/alveolars + emphatic ṭ
    ["k", "g", "q", "ḱ", "ǵ", "ḫ"],      # 2 velars/uvulars + palatovelars + ḫ
    ["s", "z", "š", "ṣ"],                # 3 sibilants
    ["m", "n", "ṇ"],                     # 4 nasals
    ["l", "r"],                          # 5 liquids
    ["j", "w"],                          # 6 glides
]
_CLASS_DENTAL = 1
_CLASS_VELAR = 2
_CLASS_SIBILANT = 3


@dataclass(frozen=True, slots=True)
class PhoneticClasses:
    """Concrete vowel set + consonant-class tables for the distance metric."""

    vowels: str
    consonant_classes: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class PhoneticScheme:
    """The four typologically ambiguous decisions, exposed for tuning."""

    interdentals: str = "dental"          # "dental" | "sibilant" | "off"  (ṯ ḏ)
    pharyngeal_h: str = "velar"           # "velar" | "off"  (ḥ)
    voiced_postalveolar: str = "sibilant"  # "sibilant" | "off"  (ž)
    strip_notation: bool = True           # strip * ₁₂₃ ʰ ʷ ◌̥ from reference forms


# Default = the parity-tested behavior. Changing nothing leaves results identical.
DEFAULT_PHONETIC_SCHEME = PhoneticScheme()

# Conservative = only the indisputable base classes; contested phonemes score a
# full mismatch.
CONSERVATIVE_PHONETIC_SCHEME = PhoneticScheme(
    interdentals="off",
    pharyngeal_h="off",
    voiced_postalveolar="off",
    strip_notation=True,
)


def build_phonetic_classes(
    scheme: PhoneticScheme = DEFAULT_PHONETIC_SCHEME,
) -> PhoneticClasses:
    """Assemble concrete class tables from a scheme."""
    classes = [list(g) for g in BASE_CONSONANT_CLASSES]
    if scheme.interdentals == "dental":
        classes[_CLASS_DENTAL] += ["ṯ", "ḏ"]
    elif scheme.interdentals == "sibilant":
        classes[_CLASS_SIBILANT] += ["ṯ", "ḏ"]
    if scheme.pharyngeal_h == "velar":
        classes[_CLASS_VELAR].append("ḥ")
    if scheme.voiced_postalveolar == "sibilant":
        classes[_CLASS_SIBILANT].append("ž")
    return PhoneticClasses(BASE_VOWELS, tuple(tuple(g) for g in classes))


DEFAULT_PHONETIC_CLASSES = build_phonetic_classes(DEFAULT_PHONETIC_SCHEME)

# Pure-notation marks with no segmental value on the Linear A side: hyphen,
# reconstruction asterisk, PIE laryngeal subscripts ₁₂₃ (U+2081-2083), the
# labialization/aspiration modifier letters ʰ ʷ (U+02B0/02B7), and the
# combining syllabic ring below (U+0325).
_REF_STRIP_RE = re.compile(
    "[-*₁₂₃ʰʷ̥]"
)


@dataclass(frozen=True, slots=True)
class PhoneticWeights:
    """Tunable substitution / indel costs, kept in [0,1] so the normalized
    distance stays in [0,1]."""

    vowel: float = 0.3        # vowel ↔ vowel substitution
    same_class: float = 0.5   # same articulatory-class consonant substitution
    far: float = 1.0          # any other substitution
    indel: float = 1.0        # insertion / deletion


DEFAULT_WEIGHTS = PhoneticWeights()


def _is_vowel(c: str, cl: PhoneticClasses) -> bool:
    return c in cl.vowels


def _same_class(x: str, y: str, cl: PhoneticClasses) -> bool:
    return any(x in g and y in g for g in cl.consonant_classes)


def _sub_cost(
    ai: str,
    bj: str,
    w: PhoneticWeights,
    cl: PhoneticClasses,
) -> float:
    if ai == bj:
        return 0.0
    if _is_vowel(ai, cl) and _is_vowel(bj, cl):
        return w.vowel
    if _same_class(ai, bj, cl):
        return w.same_class
    return w.far


def reference_key(raw_word: str, strip_notation: bool = True) -> str:
    """Bare comparison key for a reference word: drop hyphens (so syllables
    concatenate like the Linear A side) and lowercase. With ``strip_notation``,
    also remove pure-notation marks (reconstruction ``*``, PIE laryngeal
    subscripts ₁₂₃, the labialization/aspiration modifiers ʰ ʷ, and the
    combining syllabic ring U+0325). So PIE ``*ǵʰésr̥`` → ``ǵésr``."""
    if strip_notation:
        s = _REF_STRIP_RE.sub("", raw_word)
    else:
        s = raw_word.replace("-", "")
    return s.lower()


def describe_phonetic_scheme(s: PhoneticScheme) -> str:
    """One-line scheme description, for stamping into saved findings/reports so
    a match ranking stays reproducible."""
    return (
        f"interdentals={s.interdentals}, ḥ={s.pharyngeal_h}, "
        f"ž={s.voiced_postalveolar}, "
        f"strip-notation={'on' if s.strip_notation else 'off'}"
    )


def phonetic_distance(
    a: str,
    b: str,
    w: PhoneticWeights = DEFAULT_WEIGHTS,
    cl: PhoneticClasses = DEFAULT_PHONETIC_CLASSES,
) -> float:
    """Weighted Levenshtein over phonetic strings, normalized to [0,1] by the
    longer length. Vowel↔vowel swaps cost 0.3, same-class consonants 0.5,
    everything else 1 (see `PhoneticWeights`)."""
    na, nb = len(a), len(b)
    m = [[0.0] * (nb + 1) for _ in range(na + 1)]
    for i in range(na + 1):
        m[i][0] = i * w.indel
    for j in range(nb + 1):
        m[0][j] = j * w.indel
    for i in range(1, na + 1):
        for j in range(1, nb + 1):
            m[i][j] = min(
                m[i - 1][j] + w.indel,
                m[i][j - 1] + w.indel,
                m[i - 1][j - 1] + _sub_cost(a[i - 1], b[j - 1], w, cl),
            )
    return m[na][nb] / max(na, nb, 1)


# Consonant skeleton — drop vowels, lowercase. Used for root-cognate grouping.
_VOWEL_STRIP_RE = re.compile(f"[{re.escape(BASE_VOWELS)}]")


def extract_root(word: str, overrides: dict[str, str] | None = None) -> str:
    """The consonant skeleton of a word's phonetic form (vowels stripped),
    e.g. ``KU-RO`` → ``kr``. Exploratory root-cognate heuristic."""
    from ..scripts.lineara.phonetic import word_to_phonetic  # lazy: avoids cycle

    return _VOWEL_STRIP_RE.sub("", word_to_phonetic(word, overrides))


_TOKEN_DIGITS = re.compile(r"^[0-9¹²³⁴⁵⁶⁷⁸⁹⁰⅟₁₂₃₄₅₆₇₈₉₀≈𐄁]+$")


def is_numeral_token(w: str) -> bool:
    """True for digit / superscript / subscript / approx numeral tokens."""
    return bool(_TOKEN_DIGITS.match(w))


def sequence_distance(a: Sequence[object], b: Sequence[object]) -> int:
    """Standard Levenshtein over arbitrary token sequences — compares whole
    inscriptions as ordered bags of words."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    curr = [0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[m]


def sequence_similarity(a: Sequence[object], b: Sequence[object]) -> float:
    """Sequence distance normalized to a 0–1 similarity (1 = identical)."""
    max_len = max(len(a), len(b), 1)
    return 1 - sequence_distance(a, b) / max_len
