"""Cypriot syllabary script plugin (the deciphered Aegean syllabary for Greek)."""

from __future__ import annotations

from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import loader  # noqa: F401 — registers the Corpus loader on import
from .inventory import cypriot_inventory
from .lexicon import CypriotLexEntry, gloss, greek_reading, lexicon_entries, lexicon_entry
from .loader import classify
from .phonetic import word_to_phonetic

__all__ = [
    "Cypriot",
    "CypriotLexEntry",
    "gloss",
    "greek_reading",
    "lexicon_entries",
    "lexicon_entry",
    "word_to_phonetic",
]


class Cypriot(Script):
    """The Cypriot syllabary — Arcado-Cypriot Greek."""

    id = "cypriot"
    name = "Cypriot syllabary"

    @property
    def sign_inventory(self) -> SignInventory:
        return cypriot_inventory().copy()  # independent copy: a caller's attrs edit must not leak

    def tokenize(self, raw: str) -> list[Token]:
        return [classify(w, None, i) for i, w in enumerate(raw.split())]


register(Cypriot())
