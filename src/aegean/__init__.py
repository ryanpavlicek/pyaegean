"""pyaegean — the definitive Python toolkit for Ancient Greek and the Aegean
syllabic scripts (Linear A/B).

v0.1: a script-agnostic corpus data layer with Linear A fully implemented (the
analytical core ported from the Linear A Workbench) and the Greek track begun.
"""

from __future__ import annotations

from . import ai  # noqa: F401 — multi-provider AI layer (SDKs lazy/optional)
from . import analysis  # noqa: F401
from . import greek  # noqa: F401 — Greek NLP pipeline
from . import scripts  # noqa: F401 — registers built-in scripts (Linear A, Greek)
from . import translate  # noqa: F401 — hybrid lexicon+LLM translation
from .core.corpus import Corpus
from .core.script import get_script, register, registered_scripts

__version__ = "0.1.0.dev0"


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
