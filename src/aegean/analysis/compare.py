"""Cross-script phonetic comparison: line up a word in one script against a word
in another by their **sound**, not their signs.

The deciphered Aegean scripts already romanize to a common Latin phoneme string
(``scripts.<script>.phonetic.word_to_phonetic``); this module adds a romanizer
for **alphabetic Greek** and wires all of them into the existing weighted
phonetic distance / alignment (``analysis.distance`` / ``analysis.align``). So a
Linear B word and its alphabetic-Greek descendant — or a Cypriot and a Greek
form — can be scored and aligned segment by segment.

    >>> round(phonetic_compare("po-me", "linearb", "ποιμήν", "greek").similarity, 2)
    0.62
    >>> # labiovelar qa → kwa: the k drops (del) and w → b shows as a far substitution
    >>> [c.op for c in phonetic_compare("qa-si-re-u", "linearb",
    ...                                 "βασιλεύς", "greek").alignment][:3]
    ['del', 'sub-far', 'match']

**Exploratory, and doubly so here.** Two cautions stack: the distance metric's
phoneme classes are a linguistic judgement (see ``distance``), *and* the
syllabic scripts spell defectively — Linear B and Cypriot drop word-final
consonants, omit the second element of clusters, and do not write
aspiration/voicing — so a Greek form looks *longer* than its syllabic spelling
and the absolute distance is inflated. The useful signal is the **ranking**
(which candidate is nearest), not the raw number, and an alignment shows a
*hypothesised* correspondence, never an established sound law. ``fold_aspiration``
maps θ/φ/χ → t/p/k so the Greek side meets the syllabaries' aspiration-blind
orthography halfway.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .align import AlignCell, align_phonetic
from .distance import (
    DEFAULT_PHONETIC_CLASSES,
    DEFAULT_WEIGHTS,
    PhoneticClasses,
    PhoneticWeights,
    phonetic_distance,
)

__all__ = [
    "PhoneticComparison",
    "romanize_greek",
    "to_phonemes",
    "phonetic_compare",
    "nearest",
    "PHONEME_SCRIPTS",
]

# Alphabetic Greek → the Latin phoneme alphabet the distance metric uses. Letter
# by letter (no monophthongization): the syllabaries write diphthongs out
# (a-i, e-u …), so ει/αυ → "ei"/"au" line up with them naturally. ē/ō (macron)
# are in distance.BASE_VOWELS, so η/ω count as vowels.
_GREEK_MAP = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "ē",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "ks",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "u",
    "φ": "ph", "χ": "kh", "ψ": "ps", "ω": "ō",
}
_ASPIRATES = {"th": "t", "ph": "p", "kh": "k"}
_VELARS_AFTER_GAMMA = set("γκχξ")  # γ before a velar is a nasal (ἄγγελος → angelos)


def romanize_greek(text: str, *, fold_aspiration: bool = False) -> str:
    """Romanize alphabetic Greek to the Latin phoneme alphabet.

    Strips accents, breathings, iota subscript, and diaeresis (NFD, then drop
    combining marks), lowercases, and maps each letter: θ→th, φ→ph, χ→kh,
    ξ→ks, ψ→ps, η→ē, ω→ō, and γ→n before a velar (γγ/γκ/γχ/γξ). Rough breathing
    (the /h/) is dropped with the other diacritics — the syllabaries don't write
    it either. ``fold_aspiration`` further maps θ/φ/χ → t/p/k for a fairer match
    against aspiration-blind syllabic spelling. Non-Greek letters pass through."""
    base = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c)
    )
    chars = list(base)
    out: list[str] = []
    for idx, ch in enumerate(chars):
        if ch == "γ" and idx + 1 < len(chars) and chars[idx + 1] in _VELARS_AFTER_GAMMA:
            out.append("n")
            continue
        seg = _GREEK_MAP.get(ch)
        if seg is None:
            if ch.isalpha():
                out.append(ch)
            continue
        out.append(_ASPIRATES[seg] if fold_aspiration and seg in _ASPIRATES else seg)
    return "".join(out)


def _romanize_syllabic(script: str) -> Callable[[str, dict[str, str] | None], str]:
    from importlib import import_module

    mod = import_module(f"..scripts.{script}.phonetic", __package__)
    fn: Callable[[str, dict[str, str] | None], str] = mod.word_to_phonetic
    return fn


# The scripts a word can be reduced to phonemes for. Cypro-Minoan is undeciphered
# (conventional CM-numbers, no sound values), so it is deliberately absent.
PHONEME_SCRIPTS = ("greek", "lineara", "linearb", "cypriot")


def to_phonemes(
    word: str,
    script: str,
    *,
    fold_aspiration: bool = False,
    overrides: dict[str, str] | None = None,
) -> str:
    """Reduce ``word`` (in ``script``) to a Latin phoneme string.

    ``greek`` romanizes alphabetic text; ``lineara`` / ``linearb`` / ``cypriot``
    map a hyphenated transliteration through their sign→sound tables (``overrides``
    tests alternative sign values). Raises ``ValueError`` for an unsupported
    script (e.g. undeciphered Cypro-Minoan)."""
    if script == "greek":
        return romanize_greek(word, fold_aspiration=fold_aspiration)
    if script in PHONEME_SCRIPTS:
        phon = _romanize_syllabic(script)(word, overrides)
        if fold_aspiration:
            # syllabic output is already aspiration-blind, but a researcher's
            # overrides could introduce th/ph/kh — fold for symmetry with Greek.
            for k, v in _ASPIRATES.items():
                phon = phon.replace(k, v)
        return phon
    raise ValueError(
        f"no phonetic reduction for script {script!r}; supported: {', '.join(PHONEME_SCRIPTS)}"
    )


@dataclass(frozen=True, slots=True)
class PhoneticComparison:
    """One cross-script comparison: the two words, their script ids, their
    romanized phoneme strings, the normalized distance (0 = identical, 1 = wholly
    different), its ``similarity`` complement, and the per-segment ``alignment``."""

    word_a: str
    word_b: str
    script_a: str
    script_b: str
    phonemes_a: str
    phonemes_b: str
    distance: float
    similarity: float
    alignment: tuple[AlignCell, ...]


def phonetic_compare(
    word_a: str,
    script_a: str,
    word_b: str,
    script_b: str,
    *,
    weights: PhoneticWeights = DEFAULT_WEIGHTS,
    classes: PhoneticClasses = DEFAULT_PHONETIC_CLASSES,
    fold_aspiration: bool = False,
    overrides_a: dict[str, str] | None = None,
    overrides_b: dict[str, str] | None = None,
) -> PhoneticComparison:
    """Compare two words across scripts by sound: romanize each, then run the
    weighted phonetic distance and the per-segment alignment.

    The classic bridge is ``phonetic_compare("po-me", "linearb", "ποιμήν",
    "greek")`` — Linear B *po-me* against Greek *poimēn* 'shepherd'. Tune the
    metric with ``weights``/``classes`` (see ``distance``) and meet defective
    syllabic spelling with ``fold_aspiration``."""
    pa = to_phonemes(word_a, script_a, fold_aspiration=fold_aspiration, overrides=overrides_a)
    pb = to_phonemes(word_b, script_b, fold_aspiration=fold_aspiration, overrides=overrides_b)
    dist = phonetic_distance(pa, pb, weights, classes)
    return PhoneticComparison(
        word_a=word_a,
        word_b=word_b,
        script_a=script_a,
        script_b=script_b,
        phonemes_a=pa,
        phonemes_b=pb,
        distance=dist,
        similarity=1.0 - dist,
        alignment=tuple(align_phonetic(pa, pb, weights, classes)),
    )


def nearest(
    word: str,
    script: str,
    candidates: Iterable[str],
    candidate_script: str,
    *,
    top: int = 5,
    weights: PhoneticWeights = DEFAULT_WEIGHTS,
    classes: PhoneticClasses = DEFAULT_PHONETIC_CLASSES,
    fold_aspiration: bool = False,
) -> list[tuple[str, float]]:
    """Rank ``candidates`` (in ``candidate_script``) by phonetic distance to
    ``word`` (in ``script``), nearest first; returns ``(candidate, distance)``
    for the ``top`` closest (``top=0`` = all).

    The intended use is decipherment-adjacent triage — e.g. which alphabetic
    Greek words sound closest to a Linear B form — where the **ordering** is the
    result and the absolute distances are secondary (see the module caution).
    Candidates that cannot be romanized are skipped."""
    target = to_phonemes(word, script, fold_aspiration=fold_aspiration)
    scored: list[tuple[str, float]] = []
    for cand in candidates:
        try:
            cp = to_phonemes(cand, candidate_script, fold_aspiration=fold_aspiration)
        except ValueError:
            continue
        scored.append((cand, phonetic_distance(target, cp, weights, classes)))
    scored.sort(key=lambda kv: (kv[1], kv[0]))
    return scored[:top] if top > 0 else scored
