"""pyaegean — a specialist Python toolkit for Ancient Greek and the Aegean
syllabic scripts (Linear A, Linear B, Cypriot, and Cypro-Minoan).

Provides a script-agnostic corpus data layer with lossless JSON/SQLite persistence and
resumable annotation jobs (``aegean.db``); a deep Ancient Greek NLP track (offline
baseline, joint neural tagger/parser/lemmatizer with opt-in OOV lemma reranking and
calibrated confidence, a multi-dictionary registry, metrical scansion, and a benchmark
harness); spreadsheet review and multi-reviewer merge workflows (``aegean.io``); an
exploratory multi-provider AI/translation layer (``aegean.ai``, ``aegean.translate``);
and optional geographic mapping (``aegean.geo``, the ``[geo]`` extra). The core is
dependency-free and imports instantly; heavier backends and corpora are opt-in and
fetched to cache.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

# Keep top-level import independent of importlib.metadata's comparatively large
# discovery stack. The release gate pins this value to pyproject.toml.
__version__ = "0.65.0"

from . import scripts  # noqa: F401 — registers built-in scripts (Linear A, Greek)
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

if TYPE_CHECKING:
    from . import ai, analysis, biblical, cache, geo, greek, io, translate, viz
    from .core.diagnose import DiagnoseReport, diagnose
    from .core.resolve import read_corpus


_LAZY_SUBMODULES: frozenset[str] = frozenset(
    {"ai", "analysis", "biblical", "cache", "geo", "greek", "io", "translate", "viz"}
)
_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "read_corpus": (".core.resolve", "read_corpus"),
    "diagnose": (".core.diagnose", "diagnose"),
    "DiagnoseReport": (".core.diagnose", "DiagnoseReport"),
}


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


def __getattr__(name: str) -> object:
    """Load top-level subpackages and diagnostic helpers lazily on first access."""
    if name in _LAZY_SUBMODULES:
        from importlib import import_module

        mod = import_module(f".{name}", __name__)
        globals()[name] = mod
        return mod
    target = _LAZY_ATTRS.get(name)
    if target is not None:
        from importlib import import_module

        mod_path, attr = target
        val = getattr(import_module(mod_path, __name__), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include lazily exported namespaces and helpers in module discovery."""
    return sorted({*globals(), *_LAZY_SUBMODULES, *_LAZY_ATTRS})


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
    "biblical",
    "cache",
    "geo",
    "greek",
    "ai",
    "io",
    "translate",
    "viz",
    "__version__",
]
