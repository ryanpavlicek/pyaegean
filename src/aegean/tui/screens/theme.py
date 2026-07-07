"""The theme picker: a modal that previews themes live and only persists on Enter.

Textual's built-in ``ctrl+p -> Theme`` closes the moment you pick, so you cannot
try several before committing, and it does not remember your choice. This modal
fixes both: highlighting a theme applies it immediately (``App.theme`` is a
reactive), so ``up``/``down`` previews across the whole list without dismissing;
``Enter`` keeps and **persists** the highlighted theme (to ``tui.json`` via the
adapter, loaded on next launch), and ``Esc`` closes keeping whatever is previewed.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .. import data as adapter

__all__ = ["ThemeScreen"]


class ThemeScreen(ModalScreen[None]):
    """Preview themes live (on highlight) and persist the chosen one on Enter."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    DEFAULT_CSS = """
    ThemeScreen { align: center middle; }
    #theme-box { width: 46; height: 24; border: round $primary; background: $panel; padding: 1 2; }
    #theme-title { text-style: bold; padding-bottom: 1; }
    #theme-list { height: 1fr; }
    #theme-hint { color: $text-muted; padding-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-box"):
            yield Static("Theme  ·  ↑/↓ preview · Enter keep · Esc cancel", id="theme-title")
            yield OptionList(id="theme-list")
            yield Static("", id="theme-hint")

    def on_mount(self) -> None:
        options = self.query_one("#theme-list", OptionList)
        themes = sorted(self.app.available_themes)
        for name in themes:
            options.add_option(Option(name, id=name))
        current = self.app.theme
        if current in themes:
            options.highlighted = themes.index(current)
        options.focus()

    def on_option_list_option_highlighted(self, event: Any) -> None:
        if event.option_id:
            self.app.theme = event.option_id  # live preview; the modal stays open
            self.query_one("#theme-hint", Static).update(f"preview: {event.option_id}")

    def on_option_list_option_selected(self, event: Any) -> None:
        # Enter keeps AND persists the highlighted theme.
        name = event.option_id or self.app.theme
        self.app.theme = name
        config = adapter.load_tui_config()
        config["theme"] = name
        adapter.save_tui_config(config)
        self.dismiss()

    def action_close(self) -> None:
        # Esc closes keeping the previewed theme for this session (not persisted).
        self.dismiss()
