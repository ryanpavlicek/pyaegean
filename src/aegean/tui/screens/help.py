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

  h   Home                 l   Library manager (download/remove everything)
  c   Corpus browser       b   Biblical Greek study (NT, MSS, Strong's, LXX)
  g   Greek workbench      r   Annotation & conflict review (CSVs & risk queues)
  w   Works library        d   Data & environment   ·   : Command console
  t   Theme picker         Esc Back / exit input   ·   ? Help   ·   q Quit
  ctrl+p   Command palette (open a corpus, fetch, jump, theme…)

[b]In the corpus browser (c)[/b]  /  focus search · Tab cycle panes · f download
  selected uninstalled corpus · type a sign pattern (KU-*) to search ·
  In the reader: ↑/↓ line · ←/→ word · i inline gloss · Enter / a analyze line

[b]Annotation review (r)[/b]  open a review CSV, multi-reviewer merge, or corpus
  risk queue · a accept · e edit fields · 1/2/3 pick conflict option · d defer ·
  x reject · n/p next/prev unresolved · f cycle filter · s save CSV

[b]Biblical Greek study (b)[/b]  interlinear NT · 5-edition comparison · 2nd–5th c.
  manuscript witnesses · Strong's word study · LXX (55 books) & NT Catenae ·
  f downloads any missing text for the active tab/edition directly inline

[b]Library manager (l)[/b]  unified view of packs (biblical, aegean, epigraphy,
  lexica, neural), installed texts, corpora, works, commentaries, and models ·
  / filter · f download · o open · x remove

[b]Command console (:)[/b]  type any command without the 'aegean' prefix
  (e.g. library install biblical, bible compare John 1.18) ·
  ↑/↓ pick · Tab/Enter complete · Esc close · use CORPUS sets session corpus

[dim]Press Esc or q to close.[/dim]
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
