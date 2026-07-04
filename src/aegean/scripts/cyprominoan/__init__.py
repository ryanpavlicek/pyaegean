"""Cypro-Minoan script plugin (the undeciphered Bronze Age script of Cyprus).

Structurally a syllabary (a Linear A relative), Cypro-Minoan has no settled phonetic values, so the
plugin offers a sign inventory and tokenization only — no transliteration, lexicon, or Greek bridge.
"""

from __future__ import annotations

from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import loader  # noqa: F401 — registers the Corpus loader on import
from .inventory import cyprominoan_inventory
from .loader import classify

__all__ = ["CyproMinoan"]


class CyproMinoan(Script):
    """Cypro-Minoan — the undeciphered Bronze Age script of Cyprus (sign inventory only)."""

    id = "cyprominoan"
    name = "Cypro-Minoan"

    @property
    def sign_inventory(self) -> SignInventory:
        return cyprominoan_inventory().copy()  # independent copy: a caller's attrs edit must not leak

    def tokenize(self, raw: str) -> list[Token]:
        return [classify(w, None, i) for i, w in enumerate(raw.split())]


register(CyproMinoan())
