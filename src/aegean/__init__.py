"""pyaegean — a specialist Python toolkit for Ancient Greek and the Aegean
syllabic scripts (Linear A/B).

A script-agnostic corpus data layer with Linear A fully implemented, a Greek NLP
track (opt-in Perseus-treebank lemmas/POS, LSJ glossing, a projective dependency
parser, an unseen-POS tagger, edit-tree and neural lemmatizers, and a CLTK benchmark
harness), and a multi-provider AI/translation layer. The core is dependency-free;
the Greek backends are opt-in.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from . import ai  # noqa: F401 — multi-provider AI layer (SDKs lazy/optional)
from . import analysis  # noqa: F401
from . import greek  # noqa: F401 — Greek NLP pipeline
from . import scripts  # noqa: F401 — registers built-in scripts (Linear A, Greek)
from . import translate  # noqa: F401 — hybrid lexicon+LLM translation
from .core.corpus import Corpus
from .core.script import get_script, register, registered_scripts

try:
    __version__ = _pkg_version("pyaegean")
except PackageNotFoundError:  # pragma: no cover - running from a source tree, uninstalled
    __version__ = "0.0.0+unknown"


def load(script_id: str) -> Corpus:
    """Load a bundled corpus, e.g. ``aegean.load("lineara")``."""
    return Corpus.load(script_id)


__all__ = [
    "Corpus",
    "load",
    "get_script",
    "register",
    "registered_scripts",
    "analysis",
    "greek",
    "ai",
    "translate",
    "__version__",
]
