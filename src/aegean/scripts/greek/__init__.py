"""Greek script plugin.

Registers Greek as a :class:`~aegean.core.script.Script` and its bundled sample
corpus loader. The script's ``nlp`` capability exposes the :mod:`aegean.greek`
pipeline.
"""

from __future__ import annotations

from types import ModuleType

from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import loader  # noqa: F401 — registers the Corpus loader on import
from .inventory import greek_inventory

__all__ = ["Greek"]


class Greek(Script):
    """Ancient Greek — the alphabetic script; the full NLP pipeline is on ``.nlp``."""

    id = "greek"
    name = "Ancient Greek"

    @property
    def sign_inventory(self) -> SignInventory:
        return greek_inventory()

    def tokenize(self, raw: str) -> list[Token]:
        from ...greek.tokenize import tokenize as _tokenize

        return _tokenize(raw)

    @property
    def nlp(self) -> ModuleType:
        """The Greek NLP pipeline module (normalize/tokenize/syllabify/…)."""
        from ... import greek

        return greek


register(Greek())
