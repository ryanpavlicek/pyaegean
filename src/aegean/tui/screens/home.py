"""The Home screen: the landing view.

Three things live here permanently:

1. the undeciphered-script honesty banner (Linear A and Cypro-Minoan are
   undeciphered; analysis is exploratory, not a reading) — the honesty rule the
   CLI and docstrings carry, made visible the moment the app opens;
2. the corpus overview (each corpus, its blurb, and whether its data is on
   disk), read from :func:`aegean.tui.data.list_corpora` — offline, nothing is
   loaded;
3. the global-key legend, so navigation is discoverable without the command
   palette.

Home is pure view: it calls the adapter, never the library.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from .. import data as adapter
from ..widgets import CorpusList

__all__ = ["HomeScreen"]

_BANNER = (
    "Linear A and Cypro-Minoan are undeciphered. Any structural analysis of them "
    "is exploratory, not a reading."
)

_KEYS = (
    "keys:  c corpus browser   g Greek workbench   w works library   d data store   "
    ": console   t theme   Esc back   ? help   ctrl+p commands   q quit"
)

_INTRO = (
    "pyaegean — Ancient Greek and the Aegean syllabic scripts. Pick a corpus below "
    "(↑/↓ then Enter) to browse and read its documents. The keys open the tools: "
    "g the Greek workbench (analyze a line of Greek), w the works library (fetch and "
    "read real Greek works), : a console that runs any command."
)

_CORPORA_TITLE = "Corpora  —  ↑/↓ to choose, Enter to browse"


class HomeScreen(Screen[None]):
    """The landing screen: honesty banner, corpus overview, and key legend."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(_BANNER, id="home-banner")
        with VerticalScroll(id="home-body"):
            yield Static(_INTRO, id="home-intro")
            yield Static(_CORPORA_TITLE, id="home-corpora-title")
            yield CorpusList(id="home-corpora")
            yield Static(_KEYS, id="home-keys")
        yield Footer()

    def on_mount(self) -> None:
        corpora = self.query_one("#home-corpora", CorpusList)
        corpora.set_corpora(adapter.list_corpora())
        # Make it obvious the list is the active menu: highlight the first row and focus
        # it, so ↑/↓/Enter work immediately (not only after the user discovers Tab).
        if corpora.children:
            corpora.index = 0
            corpora.focus()

    def on_list_view_selected(self, event: CorpusList.Selected) -> None:
        """Opening a corpus from the overview jumps to the corpus browser."""
        corpus_id = event.item.name
        if corpus_id is not None:
            app = self.app
            if hasattr(app, "open_corpus"):
                app.open_corpus(corpus_id)  # type: ignore[attr-defined]
