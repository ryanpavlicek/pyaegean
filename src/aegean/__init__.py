"""pyaegean — a specialist Python toolkit for Ancient Greek and the Aegean
syllabic scripts (Linear A, Linear B, Cypriot, and Cypro-Minoan).

A script-agnostic corpus data layer; a deep Greek NLP track (opt-in Perseus-treebank
lemmas/POS, LSJ glossing, a dependency parser, an unseen-form POS tagger, edit-tree and
neural lemmatizers, and a benchmark harness); a multi-provider AI/translation layer; and
optional geographic mapping (``aegean.geo``, the ``[geo]`` extra). The core is dependency-free
and imports instantly; the heavier backends are opt-in and fetched to cache.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from . import ai  # noqa: F401 — multi-provider AI layer (SDKs lazy/optional)
from . import analysis  # noqa: F401
from . import cache  # noqa: F401 — opt-in persistent cache for expensive analyses (off by default)
from . import geo  # noqa: F401 — geographic analysis (geopandas/shapely lazy/optional)
from . import greek  # noqa: F401 — Greek NLP pipeline
from . import io  # noqa: F401 — EpiDoc/CSV/Parquet export adapters
from . import scripts  # noqa: F401 — registers built-in scripts (Linear A, Greek)
from . import translate  # noqa: F401 — hybrid lexicon+LLM translation
from . import viz  # noqa: F401 — one-line plots (matplotlib lazy/optional, the [viz] extra)
from .core import (
    Corpus,
    Document,
    DocumentMeta,
    Provenance,
    ReadingStatus,
    Script,
    Sign,
    SignInventory,
    Token,
    TokenKind,
    get_script,
    register,
    registered_scripts,
)

try:
    __version__ = _pkg_version("pyaegean")
except PackageNotFoundError:  # pragma: no cover - running from a source tree, uninstalled
    __version__ = "0.0.0+unknown"


def load(script_id: str) -> Corpus:
    """Load a bundled corpus, e.g. ``aegean.load("lineara")``."""
    return Corpus.load(script_id)


__all__ = [
    "Corpus",
    "Document",
    "DocumentMeta",
    "Sign",
    "SignInventory",
    "Token",
    "TokenKind",
    "ReadingStatus",
    "Provenance",
    "Script",
    "load",
    "get_script",
    "register",
    "registered_scripts",
    "analysis",
    "cache",
    "geo",
    "greek",
    "ai",
    "io",
    "translate",
    "viz",
    "__version__",
]
