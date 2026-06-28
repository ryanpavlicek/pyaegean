"""Greek accent *placement* — the laws that decide where the accent legally falls.

Where :mod:`aegean.greek.accent` *reads* an accent that is already written, this module
*places* one: given a bare (unaccented) word and its accent class, it predicts the legal
accent (acute or circumflex) and which syllable carries it, following the limitation laws
(Smyth §150-187):

- the accent stands on one of the last three syllables only;
- the **antepenult** can be accented only if the ultima vowel is short (the σωτῆρα law);
- a **circumflex** stands only on a long vowel, and on the penult only before a short ultima
  (the properispomenon rule);
- **recessive** accent (finite verbs) recedes as far toward the antepenult as those laws allow;
- **persistent** accent (nominals) stays on the lemma's syllable unless a lengthened ultima
  forces it one syllable toward the end.

It restores accents on the rule engine's bare lemmas, on OCR / epigraphic / scriptio-continua
text, and gives a verifiable cross-check on scansion (a circumflex forces a long penult).

**Honest scope.** Accent length depends on *vowel* length, which Greek spelling leaves
**undetermined** for the dichrona α/ι/υ (a problem the metrical scanner shares as ``common``).
When a dichronon is the deciding factor the placement is returned with ``certain=False`` and a
note; pass ``ultima_length`` / ``penult_length`` (e.g. from morphology) to resolve it. Out of
scope, and flagged rather than guessed: enclitic/proclitic accent interaction, crasis, and the
declension-specific specials (oxytone genitive/dative circumflex, contracted nouns).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .syllabify import syllabify

_ACUTE = "́"
_GRAVE = "̀"
_CIRCUMFLEX = "͂"
_IOTA_SUBSCRIPT = "ͅ"
_ACCENT_MARKS = {_ACUTE, _GRAVE, _CIRCUMFLEX}

_VOWELS = set("αεηιουω")
_LONG_VOWELS = set("ηω")
_SHORT_VOWELS = set("εο")
_DICHRONA = set("αιυ")
_DIPHTHONGS = {"αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ", "ωυ"}

LONG = "long"
SHORT = "short"
UNDETERMINED = "undetermined"

# (accent type, distance-from-end) → traditional name; mirrors accent._CLASSIFY.
_CLASSIFY = {
    ("acute", 1): "oxytone",
    ("acute", 2): "paroxytone",
    ("acute", 3): "proparoxytone",
    ("circumflex", 1): "perispomenon",
    ("circumflex", 2): "properispomenon",
}


@dataclass(frozen=True, slots=True)
class AccentPlacement:
    """A predicted accent placement."""

    form: str                    # the accented form
    accent_type: str             # "acute" | "circumflex"
    position_from_end: int       # 1=ultima, 2=penult, 3=antepenult
    classification: str          # oxytone / paroxytone / properispomenon / …
    certain: bool                # False if a dichronon length was the deciding factor
    note: str = ""               # the rule applied, or what was undetermined


def _strip_accents(word: str) -> str:
    """Remove acute/grave/circumflex marks, keeping breathings, subscript, dieresis."""
    nfd = unicodedata.normalize("NFD", word)
    return unicodedata.normalize("NFC", "".join(c for c in nfd if c not in _ACCENT_MARKS))


def _bases(chars: str) -> str:
    """The lowercase base letters of a string, diacritics stripped."""
    nfd = unicodedata.normalize("NFD", chars.lower())
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _vowel_length(syllable: str, *, is_final: bool) -> str:
    """LONG / SHORT / UNDETERMINED vowel length of a syllable, by the accentuation rules."""
    nfd = unicodedata.normalize("NFD", syllable)
    if _CIRCUMFLEX in nfd or _IOTA_SUBSCRIPT in nfd:
        return LONG
    nucleus = "".join(c for c in _bases(syllable) if c in _VOWELS)
    if len(nucleus) >= 2:  # diphthong
        if is_final and nucleus in {"αι", "οι"}:
            return SHORT  # final -αι / -οι count short for accent (optative/locative excepted)
        return LONG
    if len(nucleus) == 1:
        v = nucleus[0]
        if v in _LONG_VOWELS:
            return LONG
        if v in _SHORT_VOWELS:
            return SHORT
        return UNDETERMINED  # dichronon α/ι/υ — not decidable from spelling
    return UNDETERMINED


def _attach_accent(syllable: str, mark: str) -> str:
    """Place ``mark`` on the syllable's accent-bearing vowel (the last vowel of the nucleus)."""
    nfd = list(unicodedata.normalize("NFD", syllable))
    vowel_idx = [i for i, ch in enumerate(nfd) if not unicodedata.combining(ch) and _bases(ch) in _VOWELS]
    if not vowel_idx:
        return syllable
    target = vowel_idx[-1]  # the second vowel of a diphthong carries the accent
    insert = target + 1
    while insert < len(nfd) and unicodedata.combining(nfd[insert]):
        insert += 1  # after the vowel's existing breathing/dieresis
    nfd.insert(insert, mark)
    return unicodedata.normalize("NFC", "".join(nfd))


def _render(syllables: list[str], pos_from_end: int, accent_type: str) -> str:
    idx = len(syllables) - pos_from_end
    out = list(syllables)
    out[idx] = _attach_accent(out[idx], _CIRCUMFLEX if accent_type == "circumflex" else _ACUTE)
    return unicodedata.normalize("NFC", "".join(out))


def _lengths(syllables: list[str], ultima_length: str | None, penult_length: str | None
             ) -> tuple[str, str]:
    n = len(syllables)
    u = ultima_length or _vowel_length(syllables[-1], is_final=True)
    p = penult_length or (_vowel_length(syllables[-2], is_final=False) if n >= 2 else SHORT)
    return u, p


def _penult_accent(penult: str, ultima: str) -> tuple[str, bool]:
    """Accent type for an accented penult, and whether it is certain. A circumflex needs a
    long penult before a short ultima; a long ultima forces acute regardless of the penult."""
    if penult == LONG and ultima == SHORT:
        return "circumflex", True
    if ultima == LONG or penult == SHORT:
        return "acute", True
    return "acute", False  # could be circumflex; a dichronon leaves it undetermined


def recessive_accent(word: str, *, ultima_length: str | None = None,
                     penult_length: str | None = None) -> AccentPlacement:
    """Place a **recessive** accent (finite verbs): as far toward the antepenult as the laws allow."""
    bare = _strip_accents(word)
    syllables = syllabify(bare)
    n = len(syllables)
    if n == 0:
        return AccentPlacement(word, "acute", 1, "oxytone", True, "empty")
    u, p = _lengths(syllables, ultima_length, penult_length)
    certain, note = True, "recessive"

    if n >= 3 and u != LONG:
        # antepenult, unless the ultima is (undetermined and) actually long
        pos, acc = 3, "acute"
        if u == UNDETERMINED:
            certain, note = False, "recessive; antepenult assumes a short ultima (dichronon undetermined)"
    elif n >= 2:
        pos = 2
        acc, ok = _penult_accent(p, u)
        if not ok:
            certain, note = False, "recessive; penult acute/circumflex undetermined (dichronon)"
    else:
        pos = 1
        acc = "circumflex" if u == LONG else "acute"
        if u == UNDETERMINED:
            certain, note = False, "monosyllable; circumflex/acute undetermined (dichronon)"

    form = _render(syllables, pos, acc)
    return AccentPlacement(form, acc, pos, _CLASSIFY[(acc, pos)], certain, note)


def persistent_accent(form: str, lemma: str, *, ultima_length: str | None = None,
                      penult_length: str | None = None) -> AccentPlacement:
    """Place a **persistent** accent (nominals): keep the lemma's syllable unless a lengthened
    ultima forces it one syllable toward the end. ``lemma`` supplies the home syllable via its
    own written accent."""
    from .accent import accentuation

    home = accentuation(lemma).position_from_end
    bare = _strip_accents(form)
    syllables = syllabify(bare)
    n = len(syllables)
    if n == 0 or home is None:
        return recessive_accent(form, ultima_length=ultima_length, penult_length=penult_length)
    u, p = _lengths(syllables, ultima_length, penult_length)
    certain, note = True, "persistent"

    pos = min(home, n)  # the form may have fewer syllables than the lemma
    if pos == 3 and u == LONG:
        pos = 2  # σωτῆρα law: a long ultima pulls the accent off the antepenult
        note = "persistent; σωτῆρα law moved the accent to the penult"
    elif pos == 3 and u == UNDETERMINED:
        certain, note = False, "persistent; antepenult vs penult undetermined (dichronon ultima)"

    if pos == 2:
        acc, ok = _penult_accent(p, u)
        if not ok:
            certain = False
            note += "; penult acute/circumflex undetermined (dichronon)"
    elif pos == 1:
        acc = "acute"  # oxytone stays acute (gen/dat circumflex of oxytones is out of scope)
    else:
        acc = "acute"

    out = _render(syllables, pos, acc)
    return AccentPlacement(out, acc, pos, _CLASSIFY[(acc, pos)], certain, note)


def place_accent(word: str, *, recessive: bool, lemma: str | None = None,
                 ultima_length: str | None = None, penult_length: str | None = None
                 ) -> AccentPlacement:
    """Place an accent: ``recessive=True`` for finite verbs, else persistent (``lemma`` required)."""
    if recessive or lemma is None:
        return recessive_accent(word, ultima_length=ultima_length, penult_length=penult_length)
    return persistent_accent(word, lemma, ultima_length=ultima_length, penult_length=penult_length)
