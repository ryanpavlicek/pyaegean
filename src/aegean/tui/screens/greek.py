"""The Greek workbench: a live, offline analysis surface for one line of Greek.

A single text :class:`~textual.widgets.Input` at the top drives four tabs that
update as the user types (each keystroke, no debounce, because every backend is
zero-dep, offline, and instant):

- **pipeline** — per-token analysis (index, text, UPOS, lemma) from
  :func:`aegean.tui.data.greek_pipeline`;
- **scansion** — the metrical scan against a meter chosen in a small selector
  (hexameter / pentameter / trimeter), the foot glyphs and caesura, or the
  friendly "does not scan" message when the line does not fit the meter;
- **syllables** — the syllabification of the first word, hyphenated;
- **IPA** — the reconstructed Attic transcription, word by word.

Everything here goes through :mod:`aegean.tui.data`, which never raises to the
UI: a bad meter or an unscannable line arrives as ``result.error`` text and is
shown in the tab, not as a traceback. The screen is pure view.

The syllables tab operates on a single word, so it uses the first whitespace
token of the input (syllabification is a per-word operation).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from .. import data as adapter

__all__ = ["GreekWorkbenchScreen"]

_PLACEHOLDER = "type Greek, e.g. μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"

# The meters the scansion tab offers, in the selector. Values are the meter
# names the adapter's greek_scan understands.
_METERS: tuple[tuple[str, str], ...] = (
    ("hexameter", "hexameter"),
    ("pentameter", "pentameter"),
    ("trimeter", "trimeter"),
)

# Shown in each tab before anything is typed.
_EMPTY_HINT = "type a line above"


class GreekWorkbenchScreen(Screen[None]):
    """The Greek workbench screen: an input over live pipeline / scansion /
    syllables / IPA tabs, each re-rendered on every keystroke."""

    BINDINGS = [
        ("slash", "focus_input", "Search"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder=_PLACEHOLDER, id="greek-input")
        with TabbedContent(id="greek-tabs"):
            with TabPane("pipeline", id="tab-pipeline"):
                yield Static(_EMPTY_HINT, id="greek-pipeline")
            with TabPane("scansion", id="tab-scansion"):
                with Horizontal(id="greek-meter-row"):
                    yield Static("meter:", id="greek-meter-label")
                    yield Select(
                        _METERS,
                        value="hexameter",
                        allow_blank=False,
                        id="greek-meter",
                    )
                yield Static(_EMPTY_HINT, id="greek-scansion")
            with TabPane("syllables", id="tab-syllables"):
                yield Static(_EMPTY_HINT, id="greek-syllables")
            with TabPane("IPA", id="tab-ipa"):
                yield Static(_EMPTY_HINT, id="greek-ipa")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input so the user can type immediately."""
        self.query_one("#greek-input", Input).focus()

    # ── the selected meter ──────────────────────────────────────────────────
    @property
    def _meter(self) -> str:
        """The meter currently chosen in the scansion selector."""
        value = self.query_one("#greek-meter", Select).value
        return str(value) if value is not Select.BLANK else "hexameter"

    @property
    def _text(self) -> str:
        """The current input text."""
        return self.query_one("#greek-input", Input).value

    # ── live updates ────────────────────────────────────────────────────────
    def action_focus_input(self) -> None:
        """Focus the text input (the ``/`` binding)."""
        self.query_one("#greek-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-render every tab as the line changes (each backend is instant)."""
        self._refresh_all(event.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Re-scan when the meter selector changes."""
        self._render_scansion(self._text)

    def _refresh_all(self, text: str) -> None:
        self._render_pipeline(text)
        self._render_scansion(text)
        self._render_syllables(text)
        self._render_ipa(text)

    # Each renderer writes plain text into its tab's Static, read back in tests
    # via ``.content``. On an empty line the tab shows the hint; on a backend
    # error it shows the friendly ``.error`` message the adapter produced.
    def _render_pipeline(self, text: str) -> None:
        target = self.query_one("#greek-pipeline", Static)
        if not text.strip():
            target.update(_EMPTY_HINT)
            return
        result = adapter.greek_pipeline(text)
        if not result.ok:
            target.update(result.error)
            return
        lines = [f"{r['index']:>3}  {r['text']}  {r['upos']}  {r['lemma']}" for r in result.rows]
        target.update("\n".join(lines) if lines else "no tokens")

    def _render_scansion(self, text: str) -> None:
        target = self.query_one("#greek-scansion", Static)
        if not text.strip():
            target.update(_EMPTY_HINT)
            return
        result = adapter.greek_scan(text, self._meter)
        if not result.ok:
            target.update(result.error)
            return
        feet = "  ".join(f"{r['pattern']} {r['foot']}" for r in result.rows)
        target.update(f"{result.summary}\n{feet}" if feet else result.summary)

    def _render_syllables(self, text: str) -> None:
        target = self.query_one("#greek-syllables", Static)
        first = text.split()[0] if text.split() else ""
        if not first:
            target.update(_EMPTY_HINT)
            return
        result = adapter.greek_syllables(first)
        if not result.ok:
            target.update(result.error)
            return
        target.update(result.summary or "no syllables")

    def _render_ipa(self, text: str) -> None:
        target = self.query_one("#greek-ipa", Static)
        if not text.strip():
            target.update(_EMPTY_HINT)
            return
        result = adapter.greek_ipa(text, period="attic")
        if not result.ok:
            target.update(result.error)
            return
        target.update(result.summary or "no transcription")
