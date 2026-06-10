"""Linear A script plugin (the undeciphered Minoan syllabary).

Linear A is **undeciphered**: ``word_to_phonetic`` applies the conventional sign→sound values
(shared with Linear B) as a working hypothesis, never an attested reading. All Linear A output is
exploratory — see the analysis modules' caveats and [[Data-and-Provenance]]."""

from __future__ import annotations

from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import loader  # noqa: F401 — registers the Corpus loader on import
from .inventory import linear_a_inventory
from .loader import classify
from .phonetic import word_to_phonetic

__all__ = ["LinearA", "word_to_phonetic"]


class LinearA(Script):
    """Linear A — the undeciphered Minoan syllabary (all analysis is exploratory)."""

    id = "lineara"
    name = "Linear A"

    @property
    def sign_inventory(self) -> SignInventory:
        return linear_a_inventory()

    def tokenize(self, raw: str) -> list[Token]:
        return [classify(w, None, i) for i, w in enumerate(raw.split())]


register(LinearA())
