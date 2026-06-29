"""``aegean db`` — the SQLite persistence layer (aegean.db) from the shell.

Build a queryable SQLite database from any corpus and full-text search it. The database is
a faithful round-trip (documents + tokens + provenance) with an FTS5 text index; load it
back in Python with ``Corpus.from_sql(path)`` or stream it with ``aegean.db.stream(path)``.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ._common import CORPUS_ARG, JSON_OPT, emit_json, fail, load_corpus, table

db_app = typer.Typer(
    help="SQLite persistence: build a corpus database and full-text search it.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@db_app.command()
def build(
    corpus: str = CORPUS_ARG,
    output: Path = typer.Option(..., "--output", "-o", help="Destination .db file."),
    no_fts: bool = typer.Option(False, "--no-fts", help="Skip the FTS5 full-text index."),
) -> None:
    """Write a corpus to a SQLite database (documents + tokens, queryable, with FTS5)."""
    from aegean.db import to_sqlite

    c = load_corpus(corpus)
    to_sqlite(c, output, fts=not no_fts)
    print(f"wrote {len(c)} documents to {output}")


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
    c = load_corpus(source)
    to_sqlite(c, output, append=True)
    print(f"added/updated {len(c)} documents in {output}")


@db_app.command()
def search(
    path: Path = typer.Argument(..., help="A SQLite corpus DB (from `aegean db build`)."),
    query: str = typer.Argument(..., help="Text to find — a whole token by default (e.g. KU-RO)."),
    limit: int = typer.Option(50, "--limit", help="Max hits."),
    substring: bool = typer.Option(
        False, "--substring",
        help="Match the query within tokens (KU-RO also finds PO-TO-KU-RO) instead of the "
             "default exact whole-token match.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Search a SQLite corpus's tokens; prints (doc, position, text) hits.

    Matches a whole token literally by default (``KU-RO`` matches only the token ``KU-RO``,
    never ``PO-TO-KU-RO``); pass ``--substring`` to match within tokens."""
    from aegean.db import search as db_search

    hits = db_search(path, query, limit=limit, mode="substring" if substring else "token")
    if json_out:
        emit_json([{"doc_id": d, "position": p, "text": t} for d, p, t in hits])
        return
    if not hits:
        print("no matches")
        return
    table(
        f"'{query}' in {path.name}",
        ["doc", "pos", "text"],
        [[d, str(p), t] for d, p, t in hits],
    )
