"""Bridge from the Cypriot syllabary to Greek: Arcado-Cypriot words → their Greek readings.

The Cypriot syllabary writes Greek, so a transliterated word resolves to a Greek lemma —
``PA-SI-LE-U-SE`` is βασιλεύς ("king"). The bundled lexicon holds the well-established
equations; pass a returned lemma to `aegean.greek.gloss` / `aegean.greek.lookup`
(with the LSJ backend active) for the full dictionary entry.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from ...data import load_bundled_json

__all__ = ["CypriotLexEntry", "gloss", "greek_reading", "lexicon_entries", "lexicon_entry"]

_STRIP = re.compile(r"[\[\]?.]")  # editorial markers + trailing sentence punctuation
_UNDERDOT = "̣"  # COMBINING DOT BELOW (Leiden: damaged but legible reading)


@dataclass(frozen=True, slots=True)
class CypriotLexEntry:
    """One attested Arcado-Cypriot syllabic form and its source-cited Greek reading."""

    form: str
    lemma: str
    gloss: str
    greek_form: str = ""
    attestation: str = ""
    site: str = ""
    citation: str = ""
    license: str = ""


@lru_cache(maxsize=1)
def _lexicon() -> dict[str, CypriotLexEntry]:
    raw = load_bundled_json("cypriot", "lexicon.json")
    return {
        key: CypriotLexEntry(
            form=key,
            lemma=str(val["lemma"]),
            gloss=str(val["gloss"]),
            greek_form=str(val.get("greek_form", "")),
            attestation=str(val.get("attestation", "")),
            site=str(val.get("site", "")),
            citation=str(val.get("citation", "")),
            license=str(val.get("license", "")),
        )
        for key, val in raw.items()
    }


def _norm(word: str) -> str:
    # Drop the Leiden underdot (a damaged-but-legible sign is still a known reading, so
    # PẠ-SI-LE-U-SE must resolve like PA-SI-LE-U-SE) along with editorial brackets and
    # trailing sentence-final periods (e.g. IG XV 1 Marion epitaphs ending in 'e-mi.').
    decomposed = unicodedata.normalize("NFD", word).replace(_UNDERDOT, "")
    return _STRIP.sub("", unicodedata.normalize("NFC", decomposed).upper())


def lexicon_entries() -> dict[str, CypriotLexEntry]:
    """Return a shallow copy of the bundled source-cited Cypriot lexicon."""
    return dict(_lexicon())


def lexicon_entry(word: str) -> CypriotLexEntry | None:
    """Return the full source-cited :class:`CypriotLexEntry` for ``word``, or ``None``."""
    return _lexicon().get(_norm(word))


def greek_reading(word: str) -> tuple[str, str] | None:
    """The Greek ``(lemma, gloss)`` for a transliterated Cypriot word, or ``None``."""
    entry = lexicon_entry(word)
    return (entry.lemma, entry.gloss) if entry else None


def gloss(word: str) -> str | None:
    """A short English gloss for a Cypriot word, or ``None`` if it is not in the lexicon."""
    reading = greek_reading(word)
    return reading[1] if reading else None
