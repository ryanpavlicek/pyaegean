"""The ``aegean tui`` terminal user interface (the ``[tui]`` extra).

A focused research cockpit over the highest-value offline reads: browse the
thirteen corpora and inspect one document (with its accounting balance and
structure), the live Greek workbench (pipeline, scansion, syllables, IPA), and
the local data store. Built on Textual; installed with ``pip install
'pyaegean[tui]'`` and launched with ``aegean tui``.

Every screen is a thin view over an existing library call routed through
:mod:`aegean.tui.data`, the testable adapter seam that holds all the library
knowledge (screens never touch :mod:`aegean.analysis` / :mod:`aegean.greek` /
:mod:`aegean.data` directly). The balance and pipeline numbers come from the
shared :mod:`aegean._view` mappings, so the TUI and the CLI cannot disagree.

Importing this package (and Textual) is deferred: ``import aegean`` pulls none
of it, keeping the zero-dependency core clean. The entry point lazy-imports
Textual behind the ``[tui]`` extra check.
"""

from __future__ import annotations

__all__ = ["run_tui"]


def run_tui() -> None:
    """Launch the terminal UI (a thin re-export of :func:`aegean.tui.app.run_tui`)."""
    from .app import run_tui as _run

    _run()
