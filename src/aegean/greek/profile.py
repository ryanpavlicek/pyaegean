"""Descriptive text profiling: observable features of a raw Greek/Aegean string.

`profile_text` reports **only what is directly observable** in the input string:
which writing system the characters fall in, whether Greek is polytonic or bare,
whether the ASCII looks like Beta Code, the majuscule proportion, editorial
apparatus markers, and digit/numeral density.

It deliberately does **not** predict a genre, register, dialect, or an
"out-of-domain" label, and carries no accuracy or confidence estimate. That is a
design rule, not an omission: an unreliable classifier that warns about its own
unreliability invites false confidence. Callers get the raw features and draw
their own conclusions. Every field is a measured count or ratio over the input.

Pure, stdlib-only (``unicodedata``), and fast: one NFC pass, one NFD pass, and a
few linear scans, with no data files or heavy imports loaded. Runs of combining
marks are capped before normalizing, so a hostile mark flood (Zalgo text) cannot
push the normalize passes quadratic.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .normalize import _is_greek_letter

__all__ = ["TextProfile", "profile_text"]


# ── combining marks (NFD codepoints) ────────────────────────────────────────
_ACUTE = "́"
_GRAVE = "̀"
_CIRCUMFLEX = "͂"
_ACCENT_MARKS = frozenset({_ACUTE, _GRAVE, _CIRCUMFLEX})
_SMOOTH = "̓"  # smooth breathing (psili)
_ROUGH = "̔"  # rough breathing (dasia)
_BREATHING_MARKS = frozenset({_SMOOTH, _ROUGH})

# ── editorial apparatus markers (Leiden), as they appear in RAW text ─────────
# Canonical marker inventory mirrors the Cypriot loader's constants
# (scripts/cypriot/loader.py): square brackets = lacuna/restored, ⟦⟧ = erased,
# <> = editorial insertion, () = expanded abbreviation, U+0323 = underdot
# (damaged but legible). The profiler only COUNTS these; it never strips them.
_UNDERDOT = "̣"
_EDITORIAL_CORE = frozenset("[]") | frozenset(("⟦", "⟧", _UNDERDOT))
# () and <> are counted as editorial only when the text is not Beta-Code-like,
# where "(" ")" are breathings rather than an expansion apparatus.
_EDITORIAL_AMBIGUOUS = frozenset("()<>")
_EDITORIAL_ALL = _EDITORIAL_CORE | _EDITORIAL_AMBIGUOUS

# ── Beta Code signal ────────────────────────────────────────────────────────
# Markers of TLG/Perseus Beta Code, anchored the way Beta Code actually places
# them so ordinary English ("and/or", "I/O"), file paths, and source code do
# not trip it: an accent symbol directly after a VOWEL letter (Beta Code accents
# follow the vowel they modify), a diaeresis after i/u, an iota subscript after
# a/h/w, the capital marker "*" at a word start, or a sigma variant s1/s2/s3
# after a letter. The weak breathing symbols ") (" are excluded because ordinary
# parentheses would match them; they are handled by the editorial-bracket path.
_BETA_SIGNAL_RE = re.compile(
    r"[aehiouwAEHIOUW][/\\=]"  # accent after a vowel (lo/gos, mh=nin, qea/)
    r"|[iuIU]\+"  # diaeresis (i+, u+)
    r"|[ahwAHW]\|"  # iota subscript (tw=| -> w|)
    r"|(?<![A-Za-z0-9])\*[A-Za-z]"  # capital marker at a word start (*a)qh/nh)
    r"|[A-Za-z][sS][123](?![0-9])"  # sigma variants (s1/s2/s3) inside a word
)

# ── Greek alphabetic-numeral signs (the letters themselves are counted as
# letters; these signs mark numeral use). Everything else numeric is caught by
# Unicode category "N" (digits, superscripts, subscripts, vulgar fractions).
_KERAIA = "ʹ"  # Greek numeral sign (keraia)
_LOWER_KERAIA = "͵"  # Greek lower numeral sign
_NUMERAL_EXTRAS = frozenset((_KERAIA, _LOWER_KERAIA))

_TOKEN_RE = re.compile(r"\S+")
_MIXED_FLOOR = 0.15  # each script must reach this share of letters to read "mixed"


@dataclass(frozen=True, slots=True)
class TextProfile:
    """Observable, descriptive features of one raw text string.

    Every field is a direct measurement of the input, not a prediction. There is
    deliberately no genre, register, or out-of-domain label: this profiles what
    the characters are, not what the text is about. ``script`` names the writing
    system most letters fall in by codepoint block (``greek`` / ``latin`` /
    ``mixed`` / ``other``); ``greek_ratio`` and ``latin_ratio`` expose the
    underlying evidence so a caller need not trust the label alone."""

    char_count: int  # total characters in the input (whitespace included)
    token_count: int  # whitespace-delimited runs containing a letter or digit
    letter_count: int  # alphabetic characters, any script
    script: str  # dominant block by observation: greek | latin | mixed | other
    greek_ratio: float  # Greek-block letters / all letters (0.0 if no letters)
    latin_ratio: float  # ASCII Latin letters / all letters (0.0 if no letters)
    is_polytonic: bool  # any accent or breathing present (else bare Greek)
    has_accent: bool  # any acute / grave / circumflex on a Greek letter
    has_breathing: bool  # any smooth / rough breathing on a Greek letter
    polytonic_ratio: float  # Greek letters bearing an accent/breathing / Greek letters
    majuscule_ratio: float  # uppercase Greek letters / all Greek letters
    looks_like_betacode: bool  # ASCII Latin with Beta Code markup and no Unicode Greek
    has_editorial_brackets: bool  # any editorial apparatus marker present
    editorial_mark_count: int  # count of editorial apparatus markers (see module notes)
    digit_or_numeral_ratio: float  # numeric characters / non-whitespace characters


def _diacritic_stats(nfd: str) -> tuple[int, int, bool, bool]:
    """Walk NFD text once, attributing combining accents/breathings to the Greek
    base letter they follow. Returns (greek_letters, polytonic_letters,
    has_accent, has_breathing)."""
    greek_letters = 0
    polytonic_letters = 0
    has_accent = False
    has_breathing = False
    cur_greek = False
    cur_poly = False
    for ch in nfd:
        if unicodedata.combining(ch):
            if cur_greek and ch in _ACCENT_MARKS:
                has_accent = True
                cur_poly = True
            elif cur_greek and ch in _BREATHING_MARKS:
                has_breathing = True
                cur_poly = True
            continue
        # A new base character: account for the base just finished.
        if cur_greek:
            greek_letters += 1
            if cur_poly:
                polytonic_letters += 1
        cur_greek = _is_greek_letter(ch)
        cur_poly = False
    if cur_greek:  # the final base character
        greek_letters += 1
        if cur_poly:
            polytonic_letters += 1
    return greek_letters, polytonic_letters, has_accent, has_breathing


def _looks_like_betacode(
    text: str, greek_count: int, latin_count: int, nonspace: int
) -> bool:
    """Heuristic: does the ASCII look like transliterated Beta Code Greek?

    Requires no real Unicode Greek, a Latin-letter-dominated body, and DENSE Beta
    Code markers: real Beta Code carries an accent on most words, so at least one
    word in three must show a signal. A stray "I/O" or "a/b" in ordinary English
    prose, a file path, or source code stays below the density bar.
    """
    if greek_count or not latin_count or not nonspace:
        return False
    if latin_count / nonspace < 0.5:
        return False
    signals = len(_BETA_SIGNAL_RE.findall(text))
    if not signals:
        return False
    words = len(_TOKEN_RE.findall(text))
    return signals >= max(1, words // 3)


# Real polytonic Greek stacks at most a few combining marks on one base letter (breathing +
# accent + diaeresis + iota subscript); anything past this cap is a decorative/hostile flood.
_MAX_COMBINING_RUN = 8


def _cap_combining_runs(text: str, cap: int = _MAX_COMBINING_RUN) -> str:
    """Truncate runs of combining marks longer than ``cap``.

    Unicode canonical (re)ordering inside ``normalize`` is quadratic within a single run of
    combining marks with mixed combining classes, so an adversarial mark flood (Zalgo text)
    would otherwise blow up the two normalize passes. Real text is untouched: no natural
    Greek stacks more than a handful of marks. One linear pass."""
    run = 0
    out: list[str] | None = None  # built lazily: the common case copies nothing
    for i, ch in enumerate(text):
        if unicodedata.combining(ch):
            run += 1
            if run > cap:
                if out is None:
                    out = list(text[:i])
                continue
        else:
            run = 0
        if out is not None:
            out.append(ch)
    return text if out is None else "".join(out)


def _is_numeric(ch: str) -> bool:
    return ch in _NUMERAL_EXTRAS or unicodedata.category(ch).startswith("N")


def _script_of(greek_ratio: float, latin_ratio: float, letter_count: int) -> str:
    if letter_count == 0:
        return "other"
    if greek_ratio >= _MIXED_FLOOR and latin_ratio >= _MIXED_FLOOR:
        return "mixed"
    if greek_ratio >= 0.5:
        return "greek"
    if latin_ratio >= 0.5:
        return "latin"
    return "other"


def profile_text(text: str) -> TextProfile:
    """Compute the observable feature profile of ``text``.

    Reports measured features only (script blocks, polytonic vs bare, Beta Code
    look, majuscule share, editorial markers, numeral density) and never predicts
    a genre or an out-of-domain label. An empty string yields an all-zero profile
    with ``script="other"``.
    """
    text = _cap_combining_runs(text)  # bound the normalize passes on a hostile mark flood
    nfc = unicodedata.normalize("NFC", text)
    nfd = unicodedata.normalize("NFD", text)

    char_count = len(text)
    nonspace = sum(1 for c in text if not c.isspace())
    letter_count = sum(1 for c in nfc if c.isalpha())
    greek_count = sum(1 for c in nfc if _is_greek_letter(c))
    latin_count = sum(1 for c in nfc if c.isascii() and c.isalpha())

    greek_ratio = greek_count / letter_count if letter_count else 0.0
    latin_ratio = latin_count / letter_count if letter_count else 0.0

    greek_letters, polytonic_letters, has_accent, has_breathing = _diacritic_stats(nfd)
    polytonic_ratio = polytonic_letters / greek_letters if greek_letters else 0.0

    majuscule = sum(1 for c in nfc if _is_greek_letter(c) and c.isupper())
    majuscule_ratio = majuscule / greek_count if greek_count else 0.0

    betacode = _looks_like_betacode(text, greek_count, latin_count, nonspace)

    marks = _EDITORIAL_CORE if betacode else _EDITORIAL_ALL
    editorial_mark_count = sum(1 for c in text if c in marks)

    numeric = sum(1 for c in text if _is_numeric(c))
    digit_or_numeral_ratio = numeric / nonspace if nonspace else 0.0

    token_count = sum(
        1 for m in _TOKEN_RE.finditer(text) if any(c.isalnum() for c in m.group())
    )

    return TextProfile(
        char_count=char_count,
        token_count=token_count,
        letter_count=letter_count,
        script=_script_of(greek_ratio, latin_ratio, letter_count),
        greek_ratio=round(greek_ratio, 4),
        latin_ratio=round(latin_ratio, 4),
        is_polytonic=has_accent or has_breathing,
        has_accent=has_accent,
        has_breathing=has_breathing,
        polytonic_ratio=round(polytonic_ratio, 4),
        majuscule_ratio=round(majuscule_ratio, 4),
        looks_like_betacode=betacode,
        has_editorial_brackets=editorial_mark_count > 0,
        editorial_mark_count=editorial_mark_count,
        digit_or_numeral_ratio=round(digit_or_numeral_ratio, 4),
    )
