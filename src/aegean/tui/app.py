"""The Textual application shell: screens, global keys, shared state, and the
command palette.

:class:`AegeanApp` is the foundation the screens plug into. It owns:

- the :data:`AegeanApp.SCREENS` registry (``home`` / ``corpus`` / ``greek`` /
  ``data`` / ``works`` / ``console``): a new screen is one ``screens/<name>.py``
  module, registered by name, with no other file changes (a small plugin pattern);
  the theme and help overlays are modal screens pushed on demand;
- :class:`AppState`, the shared selection (``selected_corpus`` /
  ``selected_doc_id``) that screens read from ``self.app.state`` and mutate only
  through :meth:`AegeanApp.set_corpus` / :meth:`AegeanApp.set_doc`; a screen
  reconciles to the current selection when it is shown (the corpus browser does
  this in ``on_screen_resume``), so there is no cross-screen message to route;
- the global key bindings (quit, the screen switches, the command console, the
  theme picker, Esc-to-go-back, help, and the command palette) and
  :class:`CorpusCommands`, the palette provider that exposes the same navigation
  as searchable commands.

:func:`run_tui` is what ``aegean tui`` calls.

Screen registration is resilient: an absent or failing screen module is skipped
so the shell still runs (the registry names every screen; each only needs to
exist to appear), the same defensive-plugin discipline the script layer uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.widgets import Footer, Header, Input

from . import data as adapter

if TYPE_CHECKING:
    from textual.screen import Screen

__all__ = ["AegeanApp", "AppState", "run_tui"]


@dataclass
class AppState:
    """The selection shared across screens: the corpus a user is browsing and the
    document they have opened in it. Mutated only through the app's ``set_corpus``
    / ``set_doc`` helpers; a screen reads it back when it is shown."""

    selected_corpus: str | None = None
    selected_doc_id: str | None = None


# The screens the app registers, each ``(name, module, class)``. Registration
# below imports each spec defensively, so an absent or failing screen module
# leaves the app runnable with whatever screens do import.
_SCREEN_SPECS: tuple[tuple[str, str, str], ...] = (
    ("home", "screens.home", "HomeScreen"),
    ("corpus", "screens.corpus", "CorpusBrowserScreen"),
    ("greek", "screens.greek", "GreekWorkbenchScreen"),
    ("data", "screens.data", "DataStoreScreen"),
    ("works", "screens.works", "WorksScreen"),
    ("console", "screens.console", "CommandConsoleScreen"),
)


def _load_screens() -> dict[str, "type[Screen[Any]]"]:
    """The available screens, importing each spec defensively.

    A screen module that is absent or fails to import is skipped so the shell
    still runs with whatever screens do import; the full set is declared in
    ``_SCREEN_SPECS`` and a screen appears as soon as its ``screens/<name>.py``
    exists."""
    import importlib

    screens: dict[str, type[Screen[Any]]] = {}
    for name, module_tail, class_name in _SCREEN_SPECS:
        try:
            module = importlib.import_module(f"{__package__}.{module_tail}")
        except Exception:
            # Any failure importing a screen module (absent, a broken import, or
            # an error at module top level) is skipped so the shell still runs
            # with whatever screens do import. Home is the shell's landing view,
            # so its failure is fatal and re-raised rather than swallowed.
            if name == "home":
                raise
            continue
        screens[name] = getattr(module, class_name)
    return screens


class CorpusCommands(Provider):
    """Command-palette commands: open any corpus, jump to a screen, or fetch a
    dataset — the discoverability layer over the same adapter the key bindings
    drive.

    Unit-tested by awaiting :meth:`search` directly (the race-free path); the
    palette UI is driven with ``ctrl+p`` in the app tests."""

    async def search(self, query: str) -> Hits:
        from functools import partial

        matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, AegeanApp)

        commands: list[tuple[str, Callable[[], None], str]] = []
        for cid in adapter.CORPUS_IDS:
            commands.append(
                (f"Open corpus {cid}", partial(app.open_corpus, cid), f"Browse the {cid} corpus")
            )
        for name, screen in (
            ("Go to Home", "home"),
            ("Go to Corpus browser", "corpus"),
            ("Go to Greek workbench", "greek"),
            ("Go to Data store", "data"),
            ("Go to Works library", "works"),
            ("Go to Command console", "console"),
        ):
            commands.append(
                (name, partial(app.goto, screen), f"Switch to the {screen} screen")
            )
        commands.append(("Theme…", app.action_theme, "Preview and set the color theme"))
        commands.append(("Help / keys", app.action_help, "Show the key and command reference"))
        for wid in adapter.fetched_work_ids():
            commands.append(
                (f"Open work {wid}", partial(app.open_corpus, wid), "Open this fetched Greek work")
            )
        for row in adapter.dataset_rows():
            if not row.downloaded:
                commands.append(
                    (
                        f"Fetch dataset {row.name}",
                        partial(app.goto, "data"),
                        "Open the data store to fetch it",
                    )
                )

        for label, callback, help_text in commands:
            score = matcher.match(label)
            if score > 0:
                yield Hit(score, matcher.highlight(label), callback, help=help_text)


class AegeanApp(App[None]):
    """The pyaegean terminal UI: browse corpora, the Greek workbench, and the
    data store, all offline."""

    TITLE = "aegean"
    SUB_TITLE = "Ancient Greek + Aegean scripts"
    CSS_PATH = "app.tcss"

    COMMANDS = App.COMMANDS | {CorpusCommands}

    # The screen registry, resolved from ``_SCREEN_SPECS`` at class-definition
    # time: Home always, plus each of corpus / greek / data whose
    # ``screens/<name>.py`` module imports cleanly. A screen is added by creating
    # its module named in ``_SCREEN_SPECS``; nothing else in this file changes.
    # (Textual rejects placeholder values, so absent screens are simply omitted
    # rather than declared as None.)
    SCREENS = _load_screens()  # type: ignore[assignment]

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("h", "switch('home')", "Home"),
        Binding("c", "switch('corpus')", "Corpus"),
        Binding("g", "switch('greek')", "Greek"),
        Binding("d", "switch('data')", "Data"),
        Binding("w", "switch('works')", "Works"),
        Binding("colon", "console", "Console"),
        Binding("t", "theme", "Theme"),
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
        self._current_screen_name: str | None = None
        # a history of switched-to main screens, so Esc can walk back (modals use
        # the real screen_stack; the flat main screens need this app-owned list).
        self._screen_history: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen("home")
        self._current_screen_name = "home"
        # apply a persisted theme if it is still a known one (a removed theme is ignored)
        saved = adapter.load_tui_config().get("theme")
        if isinstance(saved, str) and saved in self.available_themes:
            self.theme = saved

    # ── navigation ──────────────────────────────────────────────────────────
    def action_switch(self, name: str) -> None:
        """Switch to a registered screen by name (a no-op for one not present)."""
        self.goto(name)

    def goto(self, name: str, *, record: bool = True) -> None:
        """Show screen ``name`` if it is registered (a no-op otherwise).

        When ``name`` is already the current screen, ``switch_screen`` is a no-op
        and does not post ``ScreenResume``, so a screen that reconciles to the
        shared selection in ``on_screen_resume`` (the corpus browser) would keep
        showing the old selection after ``open_corpus`` from the palette. Drive
        that reconcile directly in the already-current case.

        ``record`` pushes the screen being left onto the back-history; a back step
        passes ``record=False`` so returning doesn't re-record and cause a loop."""
        if name not in self.SCREENS:
            return
        if name == self._current_screen_name:
            resume = getattr(self.get_screen(name), "on_screen_resume", None)
            if callable(resume):
                resume()
            return
        if record and self._current_screen_name is not None:
            self._screen_history.append(self._current_screen_name)
        self._current_screen_name = name
        self.switch_screen(name)

    def action_go_back(self) -> None:
        """Esc: exit a focused input first, else return to the previous screen.

        A focused text input consumes the visual context, so Esc blurs it and stays
        on the screen; a second Esc (nothing focused) walks the history back. At Home
        with an empty history, Esc is a safe no-op."""
        if isinstance(self.focused, Input):
            self.set_focus(None)
            return
        if self._screen_history:
            self.goto(self._screen_history.pop(), record=False)

    def action_help(self) -> None:
        """Open the help / key-reference overlay."""
        try:
            from .screens.help import HelpScreen
        except Exception:  # a broken/absent help module must not crash the shell
            self.notify("help is unavailable", severity="error")
            return
        self.push_screen(HelpScreen())

    def action_theme(self) -> None:
        """Open the theme picker (live preview; stays open until you pick or cancel)."""
        try:
            from .screens.theme import ThemeScreen
        except Exception:
            self.notify("the theme picker is unavailable", severity="error")
            return
        self.push_screen(ThemeScreen())

    def action_console(self) -> None:
        """Switch to the command console (full CLI parity)."""
        self.goto("console")

    def open_corpus(self, corpus_id: str) -> None:
        """Select ``corpus_id`` and switch to the corpus browser."""
        self.set_corpus(corpus_id)
        self.goto("corpus")

    # ── shared state ────────────────────────────────────────────────────────
    def set_corpus(self, corpus_id: str) -> None:
        """Set the selected corpus and clear any open document. A screen picks up
        the change when it is shown (the corpus browser reconciles in
        ``on_screen_resume``)."""
        self.state.selected_corpus = corpus_id
        self.state.selected_doc_id = None

    def set_doc(self, doc_id: str) -> None:
        """Set the selected document."""
        self.state.selected_doc_id = doc_id


def run_tui() -> None:
    """Construct and run the terminal UI (the ``aegean tui`` entry point)."""
    AegeanApp().run()
