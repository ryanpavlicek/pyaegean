"""The Home screen: the landing view.

Three things live here permanently:

1. the undeciphered-script honesty banner (Linear A and Cypro-Minoan are
   undeciphered; analysis is exploratory, not a reading) — the honesty rule the
   CLI and docstrings carry, made visible the moment the app opens;
2. the eight-corpus overview (each corpus, its blurb, and whether its data is on
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
    "keys:  c corpus   g Greek   d data   h home   ? help   ctrl+p commands   q quit"
)

_INTRO = (
    "pyaegean — Ancient Greek and the Aegean syllabic scripts. Browse the corpora "
    "below, or press a key to jump to the Greek workbench or the data store."
)


class HomeScreen(Screen[None]):
    """The landing screen: honesty banner, corpus overview, and key legend."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(_BANNER, id="home-banner")
        with VerticalScroll(id="home-body"):
            yield Static(_INTRO, id="home-intro")
            yield Static("corpora", id="home-corpora-title")
            yield CorpusList(id="home-corpora")
            yield Static(_KEYS, id="home-keys")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#home-corpora", CorpusList).set_corpora(adapter.list_corpora())

    def on_list_view_selected(self, event: CorpusList.Selected) -> None:
        """Opening a corpus from the overview jumps to the corpus browser."""
        corpus_id = event.item.name
        if corpus_id is not None:
            app = self.app
            if hasattr(app, "open_corpus"):
                app.open_corpus(corpus_id)  # type: ignore[attr-defined]
