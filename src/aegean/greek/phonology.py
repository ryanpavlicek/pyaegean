"""Greek phonology — reconstructed IPA transcription.

Transcribes Greek to IPA for two periods:

- ``"attic"`` — Classical Attic (5th–4th c. BCE): aspirated φ θ χ = /pʰ tʰ kʰ/,
  voiced stops β γ δ = /b ɡ d/, ζ = /zd/, distinctive vowel length, υ = /y/,
  rough breathing = /h/.
- ``"koine"`` — Hellenistic/Imperial Koine: fricativized φ θ χ = /f θ x/,
  β γ δ = /v ɣ ð/, ζ = /z/, iotacism in progress (η, ει → /i/; αι → /e/; οι → /y/),
  length neutralized, breathing lost.

**Reconstructed and approximate.** Ancient pronunciation is inferred, and several
values are scholarly judgement calls (the quality of ε/η, ει/ου as monophthongs,
the realization of υ and the long diphthongs, the date of iotacism). Treat the
output as a documented reconstruction, not a recording.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

Period = Literal["attic", "koine"]

_ROUGH = "̔"      # U+0314 dasia
_CIRCUMFLEX = "͂"  # U+0342 perispomeni
_IOTA_SUB = "ͅ"   # U+0345 ypogegrammeni
_VOWELS = set("αεηιουω")
_VELARS = set("γκχξ")  # γ before one of these is a velar nasal /ŋ/

_ATTIC_VOWEL = {"α": "a", "ε": "e", "η": "ɛː", "ι": "i", "ο": "o", "υ": "y", "ω": "ɔː"}
_ATTIC_DIPH = {
    "αι": "ai̯", "ει": "eː", "οι": "oi̯", "υι": "yi̯",
    "αυ": "au̯", "ευ": "eu̯", "ου": "uː", "ηυ": "ɛːu̯", "ωυ": "ɔːu̯",
}
_ATTIC_CONS = {
    "β": "b", "γ": "ɡ", "δ": "d", "ζ": "zd", "θ": "tʰ", "κ": "k", "λ": "l",
    "μ": "m", "ν": "n", "ξ": "ks", "π": "p", "ρ": "r", "σ": "s", "ς": "s",
    "τ": "t", "φ": "pʰ", "χ": "kʰ", "ψ": "ps",
}

_KOINE_VOWEL = {"α": "a", "ε": "e", "η": "i", "ι": "i", "ο": "o", "υ": "y", "ω": "o"}
_KOINE_DIPH = {
    "αι": "e", "ει": "i", "οι": "y", "υι": "y",
    "αυ": "av", "ευ": "ev", "ου": "u", "ηυ": "iv", "ωυ": "ov",
}
_KOINE_CONS = {
    "β": "v", "γ": "ɣ", "δ": "ð", "ζ": "z", "θ": "θ", "κ": "k", "λ": "l",
    "μ": "m", "ν": "n", "ξ": "ks", "π": "p", "ρ": "r", "σ": "s", "ς": "s",
    "τ": "t", "φ": "f", "χ": "x", "ψ": "ps",
}

_TABLES = {
    "attic": (_ATTIC_VOWEL, _ATTIC_DIPH, _ATTIC_CONS),
    "koine": (_KOINE_VOWEL, _KOINE_DIPH, _KOINE_CONS),
}


def _groups(word: str) -> list[tuple[str, set[str]]]:
    """Split into (base-letter, combining-marks) groups via NFD."""
    out: list[tuple[str, set[str]]] = []
    for ch in unicodedata.normalize("NFD", word):
        if unicodedata.combining(ch):
            if out:
                out[-1][1].add(ch)
        else:
            out.append((ch.lower(), set()))
    return out


def _word_ipa(word: str, period: Period) -> str:
    vowel, diph, cons = _TABLES[period]
    groups = _groups(word)
    if not groups:
        return word

    parts: list[str] = []

    # Rough breathing → leading /h/ (Attic only; lost in Koine). It sits on the
    # first vowel of the initial cluster (the second vowel of a diphthong).
    for idx, (c, marks) in enumerate(groups):
        if c in _VOWELS:
            cluster_rough = _ROUGH in marks or (
                idx + 1 < len(groups) and _ROUGH in groups[idx + 1][1]
            )
            if cluster_rough and period == "attic":
                parts.append("h")
            break
        if c not in _VOWELS:  # a consonant precedes any vowel → no leading h
            break

    i = 0
    n = len(groups)
    while i < n:
        c, marks = groups[i]
        nxt = groups[i + 1][0] if i + 1 < n else ""
        pair = c + nxt

        if c in _VOWELS and nxt in _VOWELS and pair in diph:
            parts.append(diph[pair])
            i += 2
            continue
        if c in _VOWELS:
            v = vowel[c]
            if period == "attic" and (_CIRCUMFLEX in marks or _IOTA_SUB in marks):
                if not v.endswith("ː"):
                    v += "ː"
            parts.append(v)
            i += 1
            continue
        if c == "γ" and nxt in _VELARS:
            parts.append("ŋ")
            i += 1
            continue
        if c == "ρ" and _ROUGH in marks:
            parts.append("r̥" if period == "attic" else "r")
            i += 1
            continue
        parts.append(cons.get(c, c))
        i += 1

    return "".join(parts)


def to_ipa(text: str, period: Period = "attic") -> str:
    """Transcribe Greek ``text`` to reconstructed IPA. Whitespace-separated
    words are transcribed independently and rejoined with spaces."""
    if period not in _TABLES:
        raise ValueError(f"period must be 'attic' or 'koine'; got {period!r}")
    return " ".join(_word_ipa(w, period) for w in text.split())
