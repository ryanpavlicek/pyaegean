"""Unified full-text search CLI command: ``aegean find QUERY [TARGET]``.

Searches any bundled or hosted corpus, the Greek New Testament (all 9 editions),
the 55-book Swete Septuagint (``lxx``), the 33-volume *Patrologia Graeca*
(``patrologia`` or ``PG073``), Perseus/First1KGreek works (``tlg0012.tlg001``),
or local ``.json``/``.json.gz``/``.db`` corpora using diacritic-insensitive
SQLite FTS5 sidecar indexes.
"""

from __future__ import annotations

from typing import Any

import typer

from ._common import JSON_OPT, console, emit_json, fail, table


def register(app: typer.Typer) -> None:
    app.command("find")(find_cmd)


def find_cmd(
    query: str = typer.Argument(
        ...,
        help="Search term or phrase (Greek diacritics folded by default unless --exact).",
    ),
    target: str = typer.Argument(
        "nt",
        help=(
            "Target to search: corpus id (nt, isicily, patrologia, apostolic-fathers, ...), "
            "'lxx', 'nt-editions', a PG volume (PG073), a book name (John, Gen), "
            "a TLG work id (tlg0012.tlg001), or a local .json/.json.gz/.db file."
        ),
    ),
    book: str | None = typer.Option(
        None, "--book", "-b", help="Restrict to one book or Patrologia Graeca volume."
    ),
    edition: str | None = typer.Option(
        None,
        "--edition",
        "-e",
        help="NT edition when searching nt / nt-editions (nestle1904, sblgnt, srgnt, bhp, tisch, wh, byz, antoniades, tr).",
    ),
    limit: int = typer.Option(
        25, "--limit", "--top", "-n", help="Maximum hits to show (0 = all)."
    ),
    exact: bool = typer.Option(
        False, "--exact", help="Require exact diacritic and case match."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use local cache / bundled sample without network."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Fast diacritic-insensitive full-text search across any corpus, Bible, or archive."""
    from aegean.search import search_text

    try:
        hits = search_text(
            query,
            target,
            limit=limit,
            exact=exact,
            book=book,
            edition=edition,
            offline=offline,
        )
    except Exception as exc:
        raise fail(str(exc)) from None

    payload: dict[str, Any] = {
        "query": query,
        "target": target,
        "count": len(hits),
        "hits": [h.to_dict() for h in hits],
    }
    if json_out:
        emit_json(payload)
        return

    if not hits:
        console().print(f"No matches for {query!r} in {target!r}.")
        return

    rows = [[h.ref, h.snippet] for h in hits]
    table(
        f"find {query!r} in {target} ({len(hits)} hit(s))",
        ["ref", "snippet"],
        rows,
    )
    console().print(
        f"[dim]Tip: pass --json for full text & metadata, or --limit {max(50, limit * 2)} for more hits.[/dim]"
    )
