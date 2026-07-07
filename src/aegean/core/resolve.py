"""Resolve a corpus from many kinds of input — the single entry point the CLI and Python
share so every corpus operation accepts the same flexible source.

`read_corpus(spec)` accepts a registered corpus id, a Greek work id, a saved ``.json`` or
``.db`` file, or JSON on stdin. Heavy and sqlite-backed branches import lazily, so importing
this module stays dependency-clean (no sqlite3, no pandas at import time).

This module also hosts the shared forgiving-resolution helpers, typer-free so every layer
(CLI, REPL, MCP server, plain Python) inherits the same behavior: :func:`suggest` for
did-you-mean hints over any candidate list, and :func:`resolve_document` for forgiving
document-id lookup inside a corpus.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only: keep this module import-clean
    from .corpus import Corpus
    from .model import Document

# A CTS-style Greek work id, e.g. tlg0012.tlg001 (the Iliad). Cannot collide with a
# registered id (none contain a dot) and is matched before falling through to file paths.
_WORK_ID_RE = re.compile(r"^tlg\d+\.tlg\d+$", re.IGNORECASE)

_DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")


class CorpusNotFound(ValueError):
    """Raised when a corpus spec matches no registered id, work id, or readable file."""


def suggest(name: str, candidates: Iterable[str], *, n: int = 3, cutoff: float = 0.5) -> list[str]:
    """Close matches for a mistyped ``name`` among ``candidates``, best first.

    The shared did-you-mean helper (difflib, case-insensitive): the CLI, REPL, MCP server,
    and Python errors all suggest from the same rule. Matches are returned in the
    candidates' original spelling; the list is empty when nothing is close enough.

    >>> suggest("linera", ["lineara", "linearb", "greek"], n=2)
    ['lineara', 'linearb']
    """
    import difflib

    pool: dict[str, str] = {}
    for c in candidates:
        pool.setdefault(c.casefold(), c)
    hits = difflib.get_close_matches(name.casefold(), list(pool), n=n, cutoff=cutoff)
    return [pool[h] for h in hits]


def resolve_document(corpus: "Corpus", doc_id: str) -> "tuple[Document | None, list[str]]":
    """Resolve a document id in ``corpus`` forgivingly.

    Exact id first; then the section alone for prefixed ids, so a Greek work's book
    addresses without repeating the work id (``1`` finds ``tlg0012.tlg001:1`` when it is
    the only such tail); then a unique case- and space-insensitive match (``ht13``,
    ``py ta 641``).

    Returns ``(document, [])`` on a match, or ``(None, near_matches)`` where
    ``near_matches`` holds up to five ids containing the folded input (for a did-you-mean
    hint). Typer-free: the CLI, REPL, MCP server, and Python callers share this one rule."""

    def _fold(s: str) -> str:
        return "".join(s.split()).casefold()

    doc = corpus.get(doc_id)
    if doc is not None:
        return doc, []
    tails = [d for d in corpus if ":" in d.id and d.id.split(":", 1)[1] == doc_id]
    if len(tails) == 1:
        return tails[0], []
    folded = [d for d in corpus if _fold(d.id) == _fold(doc_id)]
    if len(folded) == 1:
        return folded[0], []
    # dot-insensitive fallback, so a dotted NT reference resolves to its space form
    # (``Matt.1`` -> ``Matt 1``). Only accepted when it is unique, so it can't guess.
    def _fold_dots(s: str) -> str:
        return _fold(s).replace(".", "")

    dotted = [d for d in corpus if _fold_dots(d.id) == _fold_dots(doc_id)]
    if len(dotted) == 1:
        return dotted[0], []
    near = sorted({d.id for d in corpus if _fold(doc_id) and _fold(doc_id) in _fold(d.id)})[:5]
    return None, near


def resolve_documents(corpus: "Corpus", doc_id: str) -> "list[Document]":
    """Resolve a document id, OR a ``prefix lo-hi`` chapter range, to the matching documents.

    A plain id (or forgiving variant) returns the single matching document. A range like
    ``"Matt 1-3"`` expands to the documents ``"Matt 1"``, ``"Matt 2"``, ``"Matt 3"`` (each
    resolved forgivingly), in order, keeping only those that exist. Returns ``[]`` when nothing
    matches — the caller then reports the friendly did-you-mean via :func:`resolve_document`."""
    import re

    doc, _near = resolve_document(corpus, doc_id)
    if doc is not None:
        return [doc]
    match = re.match(r"^(.*?)\s*(\d+)\s*-\s*(\d+)$", doc_id.strip())
    if match is not None:
        prefix, lo, hi = match.group(1).strip(), int(match.group(2)), int(match.group(3))
        if lo <= hi:
            out: list[Document] = []
            for n in range(lo, hi + 1):
                part, _ = resolve_document(corpus, f"{prefix} {n}".strip())
                if part is not None:
                    out.append(part)
            if out:
                return out
    return []


def read_corpus(spec: str) -> "Corpus":
    """Resolve a corpus from ``spec``, in this order of precedence:

    1. ``"-"`` reads a JSON corpus from **stdin**; a string starting with ``{`` is parsed
       as inline JSON (the output of :meth:`Corpus.to_json`).
    2. an exact **registered id** (``"lineara"``, ``"damos"``, ``"nt"``, …) → the bundled or
       fetched corpus. A registered id always wins over a same-named file; case is forgiven
       as a last resort (``"LINEARA"`` loads lineara when nothing else matches).
    3. a **Greek work id** like ``"tlg0012.tlg001"`` → fetched from Perseus / First1KGreek
       via :func:`aegean.greek.load_work` (network on first use, then cached).
    4. a **file path**: ``.json`` → :meth:`Corpus.from_json`; ``.db`` / ``.sqlite`` /
       ``.sqlite3`` → :meth:`Corpus.from_sql`.

    Raises :class:`CorpusNotFound` (a ``ValueError``) listing the accepted forms when nothing
    matches, with a did-you-mean suggestion when the spec is close to a registered id.
    This is what ``aegean.load`` is to a single id, generalized to any source.
    """
    if not isinstance(spec, str):
        raise CorpusNotFound(f"corpus spec must be a string, got {type(spec).__name__}")

    from .corpus import Corpus

    # 1. stdin / inline JSON
    if spec == "-":
        import sys

        return Corpus.from_json(sys.stdin.read())
    if spec.lstrip().startswith("{"):
        return Corpus.from_json(spec)

    # 2. registered id — import aegean so every built-in loader is registered first
    import aegean  # noqa: F401 — registers lineara/linearb/cypriot/cyprominoan/greek/nt/damos/sigla
    from .corpus import _LOADERS

    if spec in _LOADERS:
        return Corpus.load(spec)

    # 3. Greek work id
    if _WORK_ID_RE.match(spec):
        from ..greek import load_work

        return load_work(spec)

    # 4. file by extension
    p = Path(spec)
    suffix = p.suffix.lower()
    if suffix == ".json":
        if not p.exists():
            raise CorpusNotFound(f"no such corpus file: {p}")
        return Corpus.from_json(p)
    if suffix in _DB_SUFFIXES:
        if not p.exists():
            raise CorpusNotFound(f"no such corpus file: {p}")
        return Corpus.from_sql(p)

    # 5. nothing matched — forgive case on registered ids, then suggest before failing
    by_fold = {k.casefold(): k for k in _LOADERS}
    if spec.casefold() in by_fold:
        return Corpus.load(by_fold[spec.casefold()])
    ids = ", ".join(sorted(_LOADERS))
    hint = ""
    if suffix in (".txt", ".csv", ".tsv") or p.is_dir():
        hint = (
            f". To load plain text, import it first: `aegean import {spec} -o corpus.json` "
            "(or aegean.io.from_text_file / from_csv / from_text_dir)"
        )
    close = suggest(spec, sorted(_LOADERS), n=2)
    lead = f"unknown corpus {spec!r}"
    if close:
        lead += f" — did you mean {' or '.join(repr(m) for m in close)}? "
    else:
        lead += "; "
    raise CorpusNotFound(
        lead + f"expected a registered id ({ids}), a Greek work id like "
        f"tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin" + hint
    )
