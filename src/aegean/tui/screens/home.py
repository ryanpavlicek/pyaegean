"""The Home screen: corpus overview and global key legend."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from .. import data as adapter
from ..widgets import CorpusList

__all__ = ["HomeScreen"]

_KEYS = (
    "keys:  c corpus browser   g Greek workbench   b Biblical Greek   l library manager   "
    "r review   w works   d data/env   : console   t theme   Esc back   ? help   ctrl+p commands   q quit"
)

_INTRO = (
    "pyaegean — Ancient Greek and the Aegean syllabic scripts. Select a corpus below "
    "(↑/↓ then Enter) to browse documents, or press l (library manager — download/remove "
    "corpora, packs, works, and models), b (Biblical Greek), g (Greek workbench), r (annotation review), or : (console)."
)

_CORPORA_TITLE = "Corpora  —  ↑/↓ to choose, Enter to browse"


class HomeScreen(Screen[None]):
    """The landing screen: corpus overview and global key legend."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
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
