"""The ``Script`` plugin contract and registry.

A writing system (Linear A, Greek, …) is a plugin the core knows only by
interface. New scripts register themselves; the core never imports them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .model import SignInventory, Token


class Script(ABC):
    """A writing system the package can read and analyse."""

    id: str = ""
    name: str = ""

    @property
    @abstractmethod
    def sign_inventory(self) -> SignInventory: ...

    @abstractmethod
    def tokenize(self, raw: str) -> list[Token]:
        """Split a raw transliteration string into typed tokens."""


_REGISTRY: dict[str, Script] = {}


def register(script: Script) -> None:
    _REGISTRY[script.id] = script


def get_script(script_id: str) -> Script:
    try:
        return _REGISTRY[script_id]
    except KeyError:
        raise KeyError(
            f"no script {script_id!r} registered; available: {sorted(_REGISTRY)}"
        ) from None


def registered_scripts() -> list[str]:
    return sorted(_REGISTRY)
