"""Shared helpers for MCP server tool modules."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _did_you_mean(name: str, candidates: Iterable[str]) -> str:
    """A parenthetical did-you-mean fragment for an unknown-name error, or ``""``."""
    from ..core.resolve import suggest

    close = suggest(name, candidates, n=2)
    if not close:
        return ""
    return f" (did you mean {' or '.join(repr(c) for c in close)}?)"


def _dictionary_unavailable(dictionary: str) -> str:
    """The structured-error text for a hosted dictionary that cannot be opened on this machine."""
    return (
        f"the {dictionary} dictionary is unavailable here: its index is not readable in the "
        "local data store and could not be downloaded. Retry when the machine is online; "
        "data_status lists what the store already holds, and koine_gloss reaches the bundled "
        "Dodson (Koine NT) lexicon offline"
    )


def _load_corpus_impl(corpus: str) -> tuple[Any, dict[str, Any] | None]:
    """Load a registry corpus, forgiving case; ``(None, {"error": ...})`` when unknown."""
    import aegean
    from ..core.corpus import _LOADERS

    ids = sorted(_LOADERS)
    if corpus not in _LOADERS:
        by_fold = {k.casefold(): k for k in ids}
        folded = by_fold.get(corpus.casefold())
        if folded is None:
            return None, {
                "error": f"unknown corpus {corpus!r}{_did_you_mean(corpus, ids)}; "
                f"available: {', '.join(ids)}"
            }
        corpus = folded
    from ..data import DataNotAvailableError

    try:
        return aegean.load(corpus), None
    except DataNotAvailableError as exc:
        return None, {"error": f"corpus {corpus!r} is not available: {exc}"}


def _load_corpus(corpus: str) -> tuple[Any, dict[str, Any] | None]:
    """Dispatch through ``aegean.mcp_server._load_corpus`` so test monkeypatches work cleanly."""
    from .. import mcp_server

    fn = getattr(mcp_server, "_load_corpus", _load_corpus_impl)
    return fn(corpus)


def _find_doc(c: Any, corpus: str, doc_id: str) -> tuple[Any, dict[str, Any] | None]:
    """Resolve ``doc_id`` in ``c`` forgivingly, returning ``(doc, None)`` or ``(None, error)``."""
    from ..core.resolve import resolve_document

    doc, near = resolve_document(c, doc_id)
    if doc is not None:
        return doc, None
    hint = f" (matches: {', '.join(near)})" if near else ""
    return None, {"error": f"no document {doc_id!r} in {corpus!r}{hint}"}


def _human_size(n: int) -> str:
    """Compact human-readable byte count for the data-store listing."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


def _looks_like_path(value: str) -> bool:
    """Reject filesystem-path-looking arguments on MCP tools (names/IDs only invariant)."""
    v = value.strip()
    if "/" in v or "\\" in v:
        return True
    vl = v.lower()
    return vl.endswith((".json", ".gz", ".db", ".sqlite", ".sqlite3", ".xml", ".txt", ".csv"))
