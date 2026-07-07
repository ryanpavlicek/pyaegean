"""The help overlay: a modal listing the global keys and the command palette.

Opened with ``?``. Replaces the old behaviour where ``?`` silently navigated Home
(a surprise): pressing ``?`` now shows a reference of every global key and what the
command palette (``ctrl+p``) can do, and dismisses on ``Esc`` / ``q`` / ``Enter``.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

__all__ = ["HelpScreen"]

_HELP = """[b]aegean — keys[/b]

  h   Home                 w   Works library
  c   Corpus browser       :   Command console (any CLI command)
  g   Greek workbench      t   Theme picker (live preview)
  d   Data store           ?   This help
  Esc Back / exit input    q   Quit
  ctrl+p   Command palette (open a corpus, fetch, jump, theme…)

[b]In the corpus browser[/b]  /  focus search · Tab cycle panes · type a sign
  pattern (KU-*) to search · open: <spec> loads any work id or file
  In the reader: ↑/↓ move the line cursor · Enter / a analyze the line
  (parse/tag, neural, IPA, translate for Greek; signs + Greek reading for syllabic)

[b]Works library (w)[/b]  search by author/title · f fetch · a fetch whole author
  · Enter open a fetched work in the corpus browser

[b]Command console (:)[/b]  type any command without the 'aegean' prefix
  (e.g. stats lineara --top 5) · use CORPUS sets a session corpus

[dim]Undeciphered scripts (Linear A, Cypro-Minoan) show exploratory analysis,
never a reading.  Esc or q to close.[/dim]
"""


class HelpScreen(ModalScreen[None]):
    """A dismissable overlay of the global keys and palette capabilities."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("enter", "close", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    #help-box { width: 72; height: auto; max-height: 90%; border: round $primary;
                background: $panel; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(_HELP, id="help-body")

    def action_close(self) -> None:
        self.dismiss()
