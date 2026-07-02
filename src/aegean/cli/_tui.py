"""The ``aegean tui`` command — launch the Textual terminal UI.

A thin launcher: it lazy-imports Textual behind the ``[tui]`` extra check (the
same clean-error pattern ``aegean plot`` uses for matplotlib), then hands off to
:func:`aegean.tui.app.run_tui`. Registering it here, with the import inside the
function body, keeps ``import aegean`` and the built CLI free of Textual.
"""

from __future__ import annotations

import typer

from ._common import fail


def register(app: typer.Typer) -> None:
    app.command()(tui)


def tui() -> None:
    """Launch the interactive terminal UI: browse corpora and inspect a document,
    the live Greek workbench (pipeline, scansion, syllables, IPA), and the local
    data store.

    Needs the tui extra: pip install 'pyaegean\\[tui]'.
    """
    try:
        import textual  # noqa: F401
    except ImportError:
        raise fail(
            "the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'"
        ) from None

    from aegean.tui.app import run_tui

    run_tui()
