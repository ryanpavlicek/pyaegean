"""Unicode normalization and Beta Code ↔ Unicode conversion for Greek.

Beta Code is the ASCII transliteration of polytonic Greek used by the TLG and
Perseus. This implements the common subset: the 24 letters (with ``*`` marking
capitals and ``s1/s2/s3`` sigma variants) and the diacritics — smooth ``)`` and
rough ``(`` breathings, acute ``/``, grave ``\\``, circumflex ``=``, diaeresis
``+``, and iota subscript ``|``. Output is NFC (precomposed) by default.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

NormForm = Literal["NFC", "NFD", "NFKC", "NFKD"]

_BETA_TO_GREEK: dict[str, str] = {
    "a": "α", "b": "β", "g": "γ", "d": "δ", "e": "ε", "z": "ζ", "h": "η",
    "q": "θ", "i": "ι", "k": "κ", "l": "λ", "m": "μ", "n": "ν", "c": "ξ",
    "o": "ο", "p": "π", "r": "ρ", "s": "σ", "t": "τ", "u": "υ", "f": "φ",
    "x": "χ", "y": "ψ", "w": "ω",
}
_GREEK_TO_BETA: dict[str, str] = {v: k for k, v in _BETA_TO_GREEK.items()}

# Beta Code diacritic symbol → combining mark.
_BETA_TO_MARK: dict[str, str] = {
    ")": "̓",  # smooth breathing (psili)
    "(": "̔",  # rough breathing (dasia)
    "/": "́",  # acute (oxia)
    "\\": "̀",  # grave (varia)
    "=": "͂",  # circumflex (perispomeni)
    "+": "̈",  # diaeresis
    "|": "ͅ",  # iota subscript (ypogegrammeni)
}
_MARK_TO_BETA: dict[str, str] = {v: k for k, v in _BETA_TO_MARK.items()}

_SIGMA_VARIANTS = {"1": "σ", "2": "ς", "3": "ϲ"}


def normalize(text: str, form: NormForm = "NFC") -> str:
    """Unicode-normalize Greek text (``NFC`` precomposed by default)."""
    return unicodedata.normalize(form, text)


def strip_diacritics(text: str) -> str:
    """Remove all combining diacritics (accents, breathings, subscripts),
    keeping the base letters. Returns NFC."""
    decomposed = unicodedata.normalize("NFD", text)
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", bare)


def _is_word_break(ch: str) -> bool:
    return not (ch.lower() in _BETA_TO_GREEK or ch in _BETA_TO_MARK or ch == "*")


def betacode_to_unicode(text: str) -> str:
    """Convert a Beta Code string to precomposed (NFC) polytonic Greek."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        capital = False
        if ch == "*":
            capital = True
            i += 1
        # Diacritics may appear between '*' and the capital letter.
        pre_marks: list[str] = []
        while i < n and text[i] in _BETA_TO_MARK:
            pre_marks.append(_BETA_TO_MARK[text[i]])
            i += 1
        if i >= n:
            if capital:
                out.append("*")
            out.extend(_BETA_TO_MARK and pre_marks)
            break
        c = text[i]
        low = c.lower()
        if low not in _BETA_TO_GREEK:
            # Not a letter: emit any stray pre-marks then the char verbatim.
            out.extend(pre_marks)
            out.append(c)
            i += 1
            continue
        base = _BETA_TO_GREEK[low]
        i += 1
        # Sigma variant (s1/s2/s3) or context-sensitive final sigma.
        if low == "s" and i < n and text[i] in _SIGMA_VARIANTS:
            base = _SIGMA_VARIANTS[text[i]]
            i += 1
            final_sigma_ok = False
        else:
            final_sigma_ok = low == "s"
        marks = list(pre_marks)
        while i < n and text[i] in _BETA_TO_MARK:
            marks.append(_BETA_TO_MARK[text[i]])
            i += 1
        if final_sigma_ok and (i >= n or _is_word_break(text[i])):
            base = "ς"
        if capital:
            base = base.upper()
        out.append(base + "".join(marks))
    return unicodedata.normalize("NFC", "".join(out))


def unicode_to_betacode(text: str) -> str:
    """Convert polytonic Greek to Beta Code (capitals as ``*``; final sigma as
    ``s``). Round-trips with `betacode_to_unicode` for supported text."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", text):
        if ch in _MARK_TO_BETA:
            out.append(_MARK_TO_BETA[ch])
            continue
        if ch in ("ς", "ϲ"):
            out.append("s")
            continue
        low = ch.lower()
        if low in _GREEK_TO_BETA:
            beta = _GREEK_TO_BETA[low]
            out.append("*" + beta if ch.isupper() else beta)
        else:
            out.append(ch)
    return "".join(out)
