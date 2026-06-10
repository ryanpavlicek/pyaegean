"""Built-in script plugins. Importing this package registers them."""

from __future__ import annotations

from . import cypriot  # noqa: F401 — registers the Cypriot syllabary + its corpus loader
from . import greek  # noqa: F401 — registers Ancient Greek + its corpus loader
from . import lineara  # noqa: F401 — registers Linear A + its corpus loader
from . import linearb  # noqa: F401 — registers Linear B + its corpus loader

__all__ = ["cypriot", "lineara", "linearb", "greek"]
