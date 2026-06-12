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
    """Load a corpus by script id, failing with the list of valid ids."""
    import aegean

    try:
        return aegean.load(name)
    except Exception:
        ids = ", ".join(sorted(aegean.registered_scripts()))
        raise fail(f"unknown corpus {name!r}; available: {ids}") from None


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
    """Render a rich table to the console."""
    from rich.table import Table

    t = Table(title=title)
    for c in columns:
        t.add_column(c)
    for r in rows:
        t.add_row(*r)
    console().print(t)


CORPUS_ARG = typer.Argument(..., help="Corpus id (e.g. lineara, linearb, cypriot, greek).")
JSON_OPT = typer.Option(False, "--json", help="Machine-readable JSON on stdout.")
