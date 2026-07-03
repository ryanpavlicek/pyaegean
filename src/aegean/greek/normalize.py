"""Unicode normalization and Beta Code ↔ Unicode conversion for Greek.

Beta Code is the ASCII transliteration of polytonic Greek used by the TLG and
Perseus. This implements the common subset: the 24 letters (with ``*`` marking
capitals and ``s1/s2/s3`` sigma variants) and the diacritics — smooth ``)`` and
rough ``(`` breathings, acute ``/``, grave ``\\``, circumflex ``=``, diaeresis
``+``, and iota subscript ``|``. Output is NFC (precomposed) by default.

`normalize` also has a **lenient mode** (``lenient=True``) for OCR'd or messy
epigraphic text: it repairs Latin letters embedded in Greek words, Beta-Code
diacritic remnants attached to Greek letters, and stray combining marks — each
repair reported through a `NormalizationWarning` instead of failing or silently
mangling downstream.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from typing import Literal

NormForm = Literal["NFC", "NFD", "NFKC", "NFKD"]


class NormalizationWarning(UserWarning):
    """Emitted by ``normalize(..., lenient=True)`` for each class of repair."""

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

# Beta Code reserves these ASCII characters as markup (breathings, accents,
# subscript, the capital marker, and the sigma-variant digits after ``s``).
# A literal one of these in the source text would otherwise be re-read as
# markup on the way back, so ``unicode_to_betacode`` escapes each with a
# leading backtick and ``betacode_to_unicode`` emits the escaped character
# verbatim. The backtick itself is escaped (`` `` ``) so the scheme is total.
_BETA_ESCAPE = "`"
_BETA_RESERVED = frozenset(_BETA_TO_MARK) | {"*", _BETA_ESCAPE}


# ── lenient repair (OCR / messy epigraphic text) ────────────────────────────
# Latin letters repaired inside Greek-dominated words. The set is restricted to
# letters where the visual lookalike and the Beta-Code remnant agree on the same
# Greek letter (so the repair is right under either failure mode); ambiguous
# letters (c, f, j, l, p, q, y) are warned about but left alone. Lowercase ``v``
# is the one shape-only call: it has no Beta-Code reading, and in Greek OCR a
# stray ``v`` is overwhelmingly a misread upsilon (the ``-ευς`` ending scanned
# as ``-εvς``), not a nu, so it maps to ``υ``.
_LATIN_TO_GREEK: dict[str, str] = {
    "A": "Α", "B": "Β", "E": "Ε", "Z": "Ζ", "H": "Η", "I": "Ι", "K": "Κ",
    "M": "Μ", "N": "Ν", "O": "Ο", "P": "Ρ", "T": "Τ", "X": "Χ", "Y": "Υ",
    "a": "α", "b": "β", "d": "δ", "e": "ε", "g": "γ", "h": "η", "i": "ι",
    "k": "κ", "m": "μ", "n": "ν", "o": "ο", "r": "ρ", "s": "σ", "t": "τ",
    "u": "υ", "v": "υ", "w": "ω", "x": "χ", "z": "ζ",
}
# A wordish span: ASCII letters, Greek letters, and combining marks.
_WORDISH_RE = re.compile(r"[A-Za-z\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f]+")
_GREEK_LETTER_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")

# Which base letters each Beta-Code remnant mark may attach to.
_MARK_BASES: dict[str, str] = {
    ")": "αεηιουωρ", "(": "αεηιουωρ",  # breathings: vowels + rho
    "/": "αεηιουω", "\\": "αεηιουω", "=": "αηιυω",  # accents: vowels
    "+": "ιυ",  # diaeresis
    "|": "αηω",  # iota subscript
}


def _bare(ch: str) -> str:
    """Lowercase base letter, diacritics stripped."""
    d = unicodedata.normalize("NFD", ch.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def _greek_dominates(span: str) -> bool:
    """True when Greek letters outnumber Latin letters in a wordish span.

    The repair only fires on Greek-dominated tokens, so a normal Latin word with
    one stray Greek glyph (``modelα``) is left untouched and the "only touches
    Greek words" guarantee holds. A tie (equal Greek and Latin letters) is not
    Greek-dominated."""
    greek = sum(1 for ch in span if _GREEK_LETTER_RE.match(ch))
    latin = sum(1 for ch in span if ch.isascii() and ch.isalpha())
    return greek > latin


def _repair_latin(text: str) -> tuple[str, list[str]]:
    """Map Latin letters inside Greek-dominated words to their Greek letters."""
    repaired: list[str] = []
    unmapped: list[str] = []

    def fix(m: re.Match[str]) -> str:
        span = m.group(0)
        if not _greek_dominates(span):
            return span  # pure-Latin or Latin-dominated: not ours to touch
        out = []
        for j, ch in enumerate(span):
            if ch in _LATIN_TO_GREEK:
                rep = _LATIN_TO_GREEK[ch]
                if rep == "σ" and j == len(span) - 1:
                    rep = "ς"  # word-final sigma
                repaired.append(f"{ch}→{rep}")
                out.append(rep)
            else:
                if ch.isascii() and ch.isalpha():
                    unmapped.append(ch)
                out.append(ch)
        return "".join(out)

    fixed = _WORDISH_RE.sub(fix, text)
    notes = []
    if repaired:
        notes.append(f"repaired {len(repaired)} Latin letter(s) in Greek words ({', '.join(sorted(set(repaired)))})")
    if unmapped:
        notes.append(
            f"left {len(unmapped)} ambiguous Latin letter(s) in Greek words unrepaired ({', '.join(sorted(set(unmapped)))})"
        )
    return fixed, notes


def _repair_marks(text: str) -> tuple[str, list[str]]:
    """Convert Beta-Code remnant diacritics after Greek letters; drop stray combining marks."""
    out: list[str] = []
    beta_fixed = 0
    stray_dropped = 0
    for ch in text:
        if unicodedata.combining(ch):
            prev = out[-1] if out else ""
            if not prev or not (prev.isalpha() or unicodedata.combining(prev)):
                stray_dropped += 1  # no base letter to attach to
                continue
            out.append(ch)
            continue
        if ch in _MARK_BASES and out:
            # find the base letter this would attach to (skip prior marks)
            k = len(out) - 1
            while k >= 0 and unicodedata.combining(out[k]):
                k -= 1
            base = out[k] if k >= 0 else ""
            if base and _GREEK_LETTER_RE.match(base) and _bare(base) in _MARK_BASES[ch]:
                out.append(_BETA_TO_MARK[ch])
                beta_fixed += 1
                continue
        out.append(ch)
    notes = []
    if beta_fixed:
        notes.append(f"converted {beta_fixed} Beta-Code remnant diacritic(s) to combining marks")
    if stray_dropped:
        notes.append(f"dropped {stray_dropped} stray combining mark(s) with no base letter")
    return "".join(out), notes


def normalize(text: str, form: NormForm = "NFC", *, lenient: bool = False) -> str:
    """Unicode-normalize Greek text (``NFC`` precomposed by default).

    ``lenient=True`` first repairs common artifacts of OCR'd or half-converted
    text: Latin letters embedded in Greek words (``λόγoς`` with a Latin *o*),
    Beta-Code diacritics left attached to Greek letters (``μη=νιν``), and stray
    combining marks with no base letter, emitting a `NormalizationWarning`
    describing each repair class. The Latin repair only fires on Greek-dominated
    words (more Greek letters than Latin), so pure-Latin words and a normal Latin
    word carrying one stray Greek glyph (``modelα``) both pass through untouched.
    A stray ``v`` reads as a misread upsilon (``υ``), the dominant Greek-OCR
    confusion, not as ``ν``."""
    if lenient:
        text, latin_notes = _repair_latin(text)
        text, mark_notes = _repair_marks(text)
        for note in latin_notes + mark_notes:
            warnings.warn(f"lenient normalize: {note}", NormalizationWarning, stacklevel=2)
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
    """Convert a Beta Code string to precomposed (NFC) polytonic Greek.

    A backtick escapes the character after it (``unicode_to_betacode`` uses this
    to protect literal reserved markup), so ``` `( ``` emits a literal ``(``
    rather than a smooth breathing."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == _BETA_ESCAPE:
            # Emit the next character verbatim (or a lone trailing backtick).
            if i + 1 < n:
                out.append(text[i + 1])
                i += 2
            else:
                out.append(_BETA_ESCAPE)
                i += 1
            continue
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
    ``s``). Round-trips with `betacode_to_unicode`: any literal ASCII that Beta
    Code reserves as markup (``( ) / \\ = + | *`` and the ``s1``/``s2``/``s3``
    sigma digits, plus the backtick escape itself) is backtick-escaped, so Greek
    text with embedded parentheses, arithmetic, or other punctuation survives
    the trip unchanged. (ASCII *letters* are Beta Code's own alphabet, so plain
    Latin words are read back as Greek; this maps Greek, not mixed prose.)

    Lunate sigma (ϲ U+03F2 / Ϲ U+03F9) is a display variant of sigma and is
    normalized to a standard sigma (``s``) here, so it converts cleanly but does
    not round-trip back to the lunate glyph."""
    out: list[str] = []
    last_was_sigma = False
    for ch in unicodedata.normalize("NFD", text):
        if ch in _MARK_TO_BETA:
            out.append(_MARK_TO_BETA[ch])
            last_was_sigma = False
            continue
        if ch in ("ς", "ϲ"):  # final sigma and lowercase lunate sigma (U+03F2)
            out.append("s")
            last_was_sigma = True
            continue
        if ch == "Ϲ":  # capital lunate sigma (U+03F9): emit *s, not the raw glyph
            out.append("*s")
            last_was_sigma = True
            continue
        low = ch.lower()
        if low in _GREEK_TO_BETA:
            beta = _GREEK_TO_BETA[low]
            out.append("*" + beta if ch.isupper() else beta)
            last_was_sigma = beta == "s"
        else:
            # A literal reserved char, or a sigma-variant digit that would bind
            # to a preceding emitted ``s``, is escaped so the reader emits it
            # verbatim instead of consuming it as markup.
            if ch in _BETA_RESERVED or (last_was_sigma and ch in _SIGMA_VARIANTS):
                out.append(_BETA_ESCAPE)
            out.append(ch)
            last_was_sigma = False
    return "".join(out)
