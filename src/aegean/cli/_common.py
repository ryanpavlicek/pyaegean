"""Shared CLI plumbing: output conventions, corpus loading, stdin handling.

Conventions every command follows:

- ``--json`` prints one machine-readable JSON document to stdout (nothing else);
  without it, output is a human-readable rich rendering.
- A positional ``TEXT`` argument of ``-`` reads the text from stdin (pipeable).
- Errors print one line to stderr and exit with code 1; usage errors exit 2
  (typer's default). Success is exit 0.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import sys
from pathlib import Path
from typing import Any

import typer

# One console for human output; created lazily so --json paths never import rich.
_console: Any = None


def console() -> Any:
    """The shared rich Console (stdout)."""
    global _console
    if _console is None:
        from rich.console import Console

        _console = Console()
    return _console


def fail(message: str) -> "typer.Exit":
    """Print ``message`` to stderr and return an exit-1 (raise the result)."""
    print(f"aegean: {message}", file=sys.stderr)
    return typer.Exit(code=1)


def to_plain(obj: Any) -> Any:
    """Recursively convert dataclasses/enums/tuples/sets to JSON-ready values."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_plain(v) for v in obj]
    return obj


def emit_json(data: Any) -> None:
    """Print one JSON document (ensure_ascii=False so Greek stays readable)."""
    print(json.dumps(to_plain(data), ensure_ascii=False, indent=2))


def read_text(text: str) -> str:
    """A TEXT argument; ``-`` reads stdin (so commands compose in pipes)."""
    if text == "-":
        return sys.stdin.read().strip()
    return text


def load_corpus(name: str) -> Any:
    """Resolve a corpus from a registered id, a Greek work id, a .json/.db file, or '-'.

    Delegates to :func:`aegean.read_corpus`; failures become a clean one-line CLI error."""
    from aegean.core.resolve import CorpusNotFound, read_corpus

    try:
        return read_corpus(name)
    except CorpusNotFound as exc:
        raise fail(str(exc)) from None
    except Exception as exc:  # network/parse/etc. — surface a clean message, not a traceback
        raise fail(f"could not load corpus {name!r}: {exc}") from None


def write_corpus(corpus: Any, path: Path) -> None:
    """Write a corpus to ``.json`` (lossless JSON) or ``.db``/``.sqlite`` (SQLite) by extension."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        corpus.to_json(path)
    elif suffix in (".db", ".sqlite", ".sqlite3"):
        corpus.to_sql(path)
    else:
        raise fail(f"output {path.name!r}: use a .json or .db/.sqlite extension")


def write_result(data: Any, output: Path) -> None:
    """Save a command result by extension: ``.json`` (same shape as ``--json``), ``.csv``
    (tabular rows, via the stdlib ``csv`` — no pandas), or ``.txt`` (a tab-separated/plain
    rendering). Lets non-Python users keep results without shell redirection."""
    suffix = output.suffix.lower()
    plain = to_plain(data)
    if suffix == ".json":
        output.write_text(json.dumps(plain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    rows = _result_rows(plain)
    if suffix == ".csv":
        if rows is None:
            raise fail("this result isn't a table; save it as .json")
        _write_csv(rows, output)
        return
    if suffix in (".txt", ""):
        output.write_text(_result_text(plain, rows), encoding="utf-8")
        return
    raise fail(f"output {output.name!r}: use a .json, .csv, or .txt extension")


def _result_rows(plain: Any) -> "list[dict[str, Any]] | None":
    """The row list to tabulate: a list of dicts, a flat dict as a single row, or the first
    list-of-dicts value inside a dict; ``None`` when the result isn't tabular."""
    if isinstance(plain, list) and plain and all(isinstance(r, dict) for r in plain):
        return plain
    if isinstance(plain, dict):
        if plain and all(not isinstance(v, (list, dict)) for v in plain.values()):
            return [plain]
        for v in plain.values():
            if isinstance(v, list) and v and all(isinstance(r, dict) for r in v):
                return v
    return None


def _columns(rows: "list[dict[str, Any]]") -> list[str]:
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    return cols


def _write_csv(rows: "list[dict[str, Any]]", output: Path) -> None:
    import csv

    cols = _columns(rows)
    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                    for k, v in r.items()
                }
            )


def _result_text(plain: Any, rows: "list[dict[str, Any]] | None") -> str:
    if rows is not None:
        cols = _columns(rows)
        lines = ["\t".join(cols)]
        lines += ["\t".join(str(r.get(c, "")) for c in cols) for r in rows]
        return "\n".join(lines) + "\n"
    if isinstance(plain, dict):
        return "\n".join(f"{k}\t{v}" for k, v in plain.items()) + "\n"
    return json.dumps(plain, ensure_ascii=False, indent=2) + "\n"


RESULT_OPT = typer.Option(
    None, "--output", "-o", help="Save the result to a file (.json, .csv, or .txt by extension)."
)


def apply_meta_filters(
    corpus: Any, site: str | None, period: str | None, scribe: str | None, support: str | None
) -> Any:
    """Apply the standard metadata filters shared by several commands."""
    meta = {
        k: v
        for k, v in (("site", site), ("period", period), ("scribe", scribe), ("support", support))
        if v is not None
    }
    return corpus.filter(**meta) if meta else corpus


def table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    """Render a rich table to the console.

    Cell content is data, never rich markup: square brackets in values (an
    extra name like ``[neural]``, a bracketed apparatus reading) must render
    literally, so cells are wrapped in ``Text`` to disable markup parsing."""
    from rich.table import Table
    from rich.text import Text

    t = Table(title=title)
    for c in columns:
        t.add_column(c)
    for r in rows:
        t.add_row(*(Text(cell) for cell in r))
    console().print(t)


CORPUS_ARG = typer.Argument(
    ..., help="A corpus id (lineara, linearb, cypriot, cyprominoan, greek, nt, damos, sigla), "
              "a Greek work id (tlg0012.tlg001), a path to a .json/.db corpus, or '-' for JSON "
              "on stdin."
)
JSON_OPT = typer.Option(False, "--json", help="Machine-readable JSON on stdout.")
