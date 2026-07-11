"""``aegean db`` — the SQLite persistence layer (aegean.db) from the shell.

Build a queryable SQLite database from any corpus, append to it, and full-text search it.
The database is a faithful round-trip (documents + tokens + provenance) with an FTS5 text
index; load it back in Python with ``Corpus.from_sql(path)`` or stream it with
``aegean.db.stream(path)``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from ._common import (
    CORPUS_ARG,
    JSON_OPT,
    RESULT_OPT,
    emit_result,
    fail,
    load_corpus,
    table,
    writing,
)

db_app = typer.Typer(
    help="SQLite persistence: build, append to, and full-text search a corpus database.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Registered corpora that are themselves hosted as a SQLite database, so `aegean db search <id>`
# searches them directly (fetching the asset on first use) instead of requiring a built .db file.
_DB_CORPORA = {"ddbdp"}


def _resolve_db(path: Path) -> Path:
    """Resolve a DB-backed corpus id (e.g. ``ddbdp``) to its fetched SQLite path; a real file path
    passes through unchanged. Lets ``aegean db search ddbdp "..."`` work like a built ``.db``."""
    if path.exists() or str(path) not in _DB_CORPORA:
        return path
    if str(path) == "ddbdp":
        from aegean.scripts.greek import ddbdp_db

        return ddbdp_db()
    return path


def live_progress(verb: str) -> Callable[[int, int], None]:
    """A document-count progress painter for the db read/write hooks (`aegean.db`'s
    ``progress=``), e.g. ``live_progress("writing")``. Same behavior as the eval live
    line in ``_greek.py``: one repainted stderr line, TTY-only."""

    def paint(done: int, total: int) -> None:
        # A single repainted stderr line, TTY-only: piped/captured runs (CI, --json > f)
        # stay clean, but a scholar building or loading a 57k-document DDbDP-sized
        # database sees the minutes-long run moving.
        if not sys.stderr.isatty():
            return
        step = max(1, total // 200)
        if done % step and done != total:
            return
        end = "\n" if done == total else ""
        print(f"\r  {verb} {done:,}/{total:,} documents ({100 * done // total}%)",
              file=sys.stderr, end=end, flush=True)

    return paint


def _load_source(spec: str) -> Any:
    """Load the corpus behind ``spec`` with a live progress line where one is possible:
    a DB-backed corpus id (``ddbdp``) or an existing ``.db``/``.sqlite`` file materializes
    through ``from_sqlite(progress=...)`` (the ~100 s DDbDP load is no longer silent);
    every other spec resolves through the shared `load_corpus` unchanged."""
    p = Path(spec)
    if spec not in _DB_CORPORA and not (
        p.suffix.lower() in {".db", ".sqlite", ".sqlite3"} and p.exists()
    ):
        return load_corpus(spec)
    try:
        if spec in _DB_CORPORA:  # a registered id wins over a same-named file (read_corpus rule)
            from aegean.scripts.greek import ddbdp_db

            target = ddbdp_db()  # fetches + unpacks on first use, like load_corpus would
        else:
            target = p
        from aegean.db import from_sqlite

        return from_sqlite(target, progress=live_progress("loading"))
    except Exception as exc:  # fetch/parse failure — one clean line, same as load_corpus
        raise fail(f"could not load corpus {spec!r}: {exc}") from None


@db_app.command()
def build(
    corpus: str = CORPUS_ARG,
    output: Path = typer.Option(..., "--output", "-o", help="Destination .db file."),
    no_fts: bool = typer.Option(False, "--no-fts", help="Skip the FTS5 full-text index."),
) -> None:
    """Write a corpus to a SQLite database (documents + tokens, queryable, with FTS5)."""
    from aegean.db import to_sqlite

    c = _load_source(corpus)
    with writing(output):
        to_sqlite(c, output, fts=not no_fts, progress=live_progress("writing"))
    print(f"wrote {len(c)} documents to {output}", file=sys.stderr)
    freqs = c.word_frequencies()
    word = freqs[0][0] if freqs else "<word>"
    print(f"search it:  aegean db search {output} {word}")


@db_app.command()
def add(
    source: str = typer.Argument(
        ..., help="Corpus to add: an id, a .json/.db file, a Greek work id, or '-'."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Existing .db to append into."),
) -> None:
    """Append or update documents in an existing SQLite corpus DB (upsert by document id).

    A document whose id already exists is replaced; new ids are added. Build the database
    first with `aegean db build`. Example: aegean db add tlg0012.tlg002 -o homer.db"""
    from aegean.db import to_sqlite

    if not output.exists():
        raise fail(f"no database to append to: {output} (create it with `aegean db build`)")
    c = _load_source(source)
    with writing(output):
        to_sqlite(c, output, append=True, progress=live_progress("writing"))
    print(f"added/updated {len(c)} documents in {output}")


@db_app.command()
def search(
    path: Path = typer.Argument(
        ..., help="A SQLite corpus DB (from `aegean db build`) or a DB-backed corpus id (ddbdp)."
    ),
    query: str = typer.Argument(..., help="Text to find — a whole token by default (e.g. KU-RO)."),
    limit: int = typer.Option(50, "--limit", "--top", help="Max hits; 0 = all."),
    substring: bool = typer.Option(
        False, "--substring",
        help="Match the query within tokens (KU-RO also finds PO-TO-KU-RO) instead of the "
             "default exact whole-token match.",
    ),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Search a SQLite corpus's tokens; prints (doc, position, text) hits.

    Matches a whole token literally by default (``KU-RO`` matches only the token ``KU-RO``,
    never ``PO-TO-KU-RO``); pass ``--substring`` to match within tokens. The database is
    opened read-only: a search never creates or modifies a file."""
    import sqlite3

    from aegean.db import search as db_search

    path = _resolve_db(path)
    if not path.exists():
        raise fail(f"no database at {path} (build one with `aegean db build`)")
    try:
        hits = db_search(path, query, limit=limit, mode="substring" if substring else "token")
    except sqlite3.Error:
        raise fail(
            f"{path} is not a corpus database (build one with `aegean db build`)"
        ) from None
    payload = [{"doc_id": d, "position": p, "text": t} for d, p, t in hits]
    if emit_result(payload, json_output=json_out, output=output):
        return
    if not hits:
        hint = "" if substring else " (whole-token) — pass --substring to match within tokens"
        print(f"no matches{hint}")
        return
    table(
        f"'{query}' in {path.name}",
        ["doc", "pos", "text"],
        [[d, str(p) if p is not None else "-", t] for d, p, t in hits],
    )
