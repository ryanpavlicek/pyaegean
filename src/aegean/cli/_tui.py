"""The ``aegean tui`` command — launch the Textual terminal UI.

A thin launcher: it lazy-imports Textual behind the ``[tui]`` extra check (the
same clean-error pattern ``aegean plot`` uses for matplotlib), then hands off to
:func:`aegean.tui.app.run_tui`. Registering it here, with the import inside the
function body, keeps ``import aegean`` and the built CLI free of Textual.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ._common import fail


def register(app: typer.Typer) -> None:
    app.command()(tui)


def tui(
    review: Annotated[
        list[str] | None,
        typer.Option(
            "--review",
            "-r",
            help="Open directly in the annotation review screen with one or more review CSVs (pass twice to adjudicate conflicts).",
        ),
    ] = None,
    corpus: Annotated[
        str | None,
        typer.Option(
            "--corpus",
            "-c",
            help="Open directly on a corpus id or JSON/SQLite path (also supplies context for --review merges).",
        ),
    ] = None,
) -> None:
    """Launch the interactive terminal UI: browse corpora, review annotations
    and reviewer disagreements, run the live Greek workbench, and manage local data.

    Needs the tui extra: pip install 'pyaegean\\[tui]'.
    """
    try:
        import textual  # noqa: F401
    except ImportError:
        raise fail(
            "the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'"
        ) from None

    from aegean.tui.app import run_tui

    run_tui(corpus=corpus, review_paths=tuple(review or ()))
