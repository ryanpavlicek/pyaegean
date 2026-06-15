"""Resolve a corpus from many kinds of input — the single entry point the CLI and Python
share so every corpus operation accepts the same flexible source.

`read_corpus(spec)` accepts a registered corpus id, a Greek work id, a saved ``.json`` or
``.db`` file, or JSON on stdin. Heavy and sqlite-backed branches import lazily, so importing
this module stays dependency-clean (no sqlite3, no pandas at import time).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only: keep this module import-clean
    from .corpus import Corpus

# A CTS-style Greek work id, e.g. tlg0012.tlg001 (the Iliad). Cannot collide with a
# registered id (none contain a dot) and is matched before falling through to file paths.
_WORK_ID_RE = re.compile(r"^tlg\d+\.tlg\d+$", re.IGNORECASE)

_DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")


class CorpusNotFound(ValueError):
    """Raised when a corpus spec matches no registered id, work id, or readable file."""


def read_corpus(spec: str) -> "Corpus":
    """Resolve a corpus from ``spec``, in this order of precedence:

    1. ``"-"`` reads a JSON corpus from **stdin**; a string starting with ``{`` is parsed
       as inline JSON (the output of :meth:`Corpus.to_json`).
    2. an exact **registered id** (``"lineara"``, ``"damos"``, ``"nt"``, …) → the bundled or
       fetched corpus. A registered id always wins over a same-named file.
    3. a **Greek work id** like ``"tlg0012.tlg001"`` → fetched from Perseus / First1KGreek
       via :func:`aegean.greek.load_work` (network on first use, then cached).
    4. a **file path**: ``.json`` → :meth:`Corpus.from_json`; ``.db`` / ``.sqlite`` /
       ``.sqlite3`` → :meth:`Corpus.from_sql`.

    Raises :class:`CorpusNotFound` (a ``ValueError``) listing the accepted forms when nothing
    matches. This is what ``aegean.load`` is to a single id, generalized to any source.
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

    # 5. nothing matched
    ids = ", ".join(sorted(_LOADERS))
    hint = ""
    if suffix in (".txt", ".csv", ".tsv") or p.is_dir():
        hint = (
            f". To load plain text, import it first: `aegean import {spec} -o corpus.json` "
            "(or aegean.io.from_text_file / from_csv / from_text_dir)"
        )
    raise CorpusNotFound(
        f"unknown corpus {spec!r}; expected a registered id ({ids}), a Greek work id like "
        f"tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin" + hint
    )
