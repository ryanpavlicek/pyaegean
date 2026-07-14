"""pyaegean — a specialist Python toolkit for Ancient Greek and the Aegean
syllabic scripts (Linear A, Linear B, Cypriot, and Cypro-Minoan).

A script-agnostic corpus data layer; a deep Greek NLP track (opt-in Perseus-treebank
lemmas/POS, LSJ glossing, a dependency parser, an unseen-form POS tagger, edit-tree and
neural lemmatizers, and a benchmark harness); a multi-provider AI/translation layer; and
optional geographic mapping (``aegean.geo``, the ``[geo]`` extra). The core is dependency-free
and imports instantly; the heavier backends are opt-in and fetched to cache.
"""

from __future__ import annotations

from collections.abc import Iterable

# Keep top-level import independent of importlib.metadata's comparatively large
# discovery stack. The release gate pins this value to pyproject.toml.
__version__ = "0.49.0"

from . import ai  # noqa: F401 — multi-provider AI layer (SDKs lazy/optional)
from . import cache  # noqa: F401 — opt-in persistent cache for expensive analyses (off by default)
from . import geo  # noqa: F401 — geographic analysis (geopandas/shapely lazy/optional)
from . import greek  # noqa: F401 — Greek NLP pipeline
from . import io  # noqa: F401 — corpus interchange, review, and persistence adapters
from . import scripts  # noqa: F401 — registers built-in scripts (Linear A, Greek)
from . import translate  # noqa: F401 — hybrid lexicon+LLM translation
from ._log import set_verbosity  # opt-in library logging (off by default; stdlib logging)
from .core import (
    Corpus,
    Document,
    DocumentMeta,
    FormSegment,
    Provenance,
    ReadingStatus,
    Script,
    Sign,
    SignInventory,
    SourceAlignment,
    SourceMarkupRef,
    Token,
    TokenFormState,
    TokenKind,
    get_script,
    register,
    registered_scripts,
)

def load(script_id: str, *, version: str | None = None) -> Corpus:
    """Load a registered corpus by id, e.g. ``aegean.load("lineara")``.

    The Aegean corpora and the Greek sample texts are bundled and load offline;
    the rest (``nt``, ``damos``, ``sigla``, the epigraphy corpora, ``ddbdp``)
    fetch to the local data store on first use.

    ``version`` (optional) loads a kept **historical** release of a fetched corpus
    the project still hosts, for reproducing an earlier analysis (e.g.
    ``aegean.load("isicily", version="v1")`` for the pre-0.29.0 I.Sicily data). It
    is accepted only for corpora with kept historical pins (``isicily``, ``iip``,
    ``iospe``, ``igcyr``, ``edh``, ``ddbdp``); the default loads the current data.

    Each call returns an independent copy (see `Corpus.copy`), so mutating the
    result never leaks into a later ``load()`` of the same corpus."""
    return Corpus.load(script_id, version=version)


from .core.resolve import read_corpus  # noqa: E402 — flexible loader (id/work/file/stdin)
from .core.diagnose import DiagnoseReport, diagnose  # noqa: E402 — corpus health report


def __getattr__(name: str) -> object:
    """Load the mutually dependent analysis/visualization facades on first use."""

    if name in {"analysis", "viz"}:
        from importlib import import_module

        # Analysis owns the established cycle-breaking order: its seriation module
        # imports viz only after the multivariate records viz needs are available.
        import_module(".analysis", __name__)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include lazily exported namespaces in module discovery."""

    return sorted({*globals(), "analysis", "viz"})


def combine(corpora: "Iterable[Corpus]", *, dedupe: str = "error") -> Corpus:
    """Merge several corpora into one (see `Corpus.merge`).

    ``corpora`` is any iterable of `Corpus`; ``dedupe`` handles duplicate document ids
    (``"error"`` (default), ``"first"``, ``"last"``, or ``"suffix"``)."""
    items = list(corpora)
    if not items:
        raise ValueError("combine() needs at least one corpus")
    return items[0].merge(*items[1:], dedupe=dedupe)


__all__ = [
    "Corpus",
    "Document",
    "DocumentMeta",
    "FormSegment",
    "Sign",
    "SignInventory",
    "SourceAlignment",
    "SourceMarkupRef",
    "Token",
    "TokenFormState",
    "TokenKind",
    "ReadingStatus",
    "Provenance",
    "Script",
    "load",
    "read_corpus",
    "combine",
    "diagnose",
    "DiagnoseReport",
    "get_script",
    "register",
    "registered_scripts",
    "set_verbosity",
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
