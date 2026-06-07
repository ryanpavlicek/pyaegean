"""Built-in script plugins. Importing this package registers them."""

from __future__ import annotations

from . import greek  # noqa: F401 — registers Ancient Greek + its corpus loader
from . import lineara  # noqa: F401 — registers Linear A + its corpus loader

__all__ = ["lineara", "greek"]
