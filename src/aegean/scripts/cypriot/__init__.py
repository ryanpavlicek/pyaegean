"""Cypriot syllabary script plugin (the deciphered Aegean syllabary for Greek)."""

from __future__ import annotations

from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import loader  # noqa: F401 — registers the Corpus loader on import
from .inventory import cypriot_inventory
from .lexicon import gloss, greek_reading
from .loader import classify
from .phonetic import word_to_phonetic

__all__ = ["Cypriot", "gloss", "greek_reading", "word_to_phonetic"]


class Cypriot(Script):
    id = "cypriot"
    name = "Cypriot syllabary"

    @property
    def sign_inventory(self) -> SignInventory:
        return cypriot_inventory()

    def tokenize(self, raw: str) -> list[Token]:
        return [classify(w, None, i) for i, w in enumerate(raw.split())]


register(Cypriot())
