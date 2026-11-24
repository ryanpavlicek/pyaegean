"""The Greek workbench: a live, offline analysis surface for one line of Greek.

A single text :class:`~textual.widgets.Input` at the top drives four tabs that
update as the user types (a short ~0.12 s debounce coalesces fast typing; every
backend is zero-dep, offline, and instant):

- **pipeline** — per-token analysis (sentence:index, text, UPOS, lemma) from
  :func:`aegean.tui.data.greek_pipeline`, the sentence number kept so a
  multi-sentence line stays unambiguous;
- **scansion** — the metrical scan against a meter chosen in a small selector
  (hexameter / pentameter / trimeter), the foot glyphs and caesura, or the
  friendly "does not scan" message when the line does not fit the meter;
- **syllables** — the syllabification of the first word, hyphenated;
- **IPA** — the reconstructed transcription, word by word, in the period chosen
  in a selector (Attic or Koine).

Everything here goes through :mod:`aegean.tui.data`, which never raises to the
UI: a bad meter or an unscannable line arrives as ``result.error`` text and is
shown in the tab, not as a traceback. The screen is pure view.

The syllables tab operates on a single word, so it uses the first whitespace
token of the input (syllabification is a per-word operation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from textual.timer import Timer

__all__ = ["GreekWorkbenchScreen"]

_PLACEHOLDER = "type Greek (or press b for Beta Code, e.g. mh=nin a)/eide qea/)"

# All 10 supported meters (epic, elegiac, dramatic, and Aeolic lyric).
_METERS: tuple[tuple[str, str], ...] = (
    ("hexameter", "hexameter"),
    ("pentameter", "pentameter"),
    ("trimeter", "trimeter"),
    ("glyconic", "glyconic"),
    ("pherecratean", "pherecratean"),
    ("sapphic hendecasyllable", "sapphic_hendecasyllable"),
    ("adonean", "adonean"),
    ("alcaic hendecasyllable", "alcaic_hendecasyllable"),
    ("alcaic enneasyllable", "alcaic_enneasyllable"),
    ("alcaic decasyllable", "alcaic_decasyllable"),
)

# The reconstruction periods the IPA tab offers (Attic 5th c. vs Koine).
_PERIODS: tuple[tuple[str, str], ...] = (
    ("Attic", "attic"),
    ("Koine", "koine"),
)

# Shown in each tab before anything is typed.
_EMPTY_HINT = "type a line above"


class GreekWorkbenchScreen(Screen[None]):
    """The Greek workbench screen: an input (Unicode or live Beta Code) over live
    pipeline / lexicon / scansion / syllables / IPA tabs."""

    DEFAULT_CSS = """
    GreekWorkbenchScreen #greek-betacode-bar {
        height: auto;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("slash", "focus_input", "Search"),
        ("b", "toggle_betacode", "Beta Code"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._betacode_mode = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder=_PLACEHOLDER, id="greek-input")
        yield Static("", id="greek-betacode-bar", markup=False)
        with TabbedContent(id="greek-tabs"):
            with TabPane("pipeline", id="tab-pipeline"):
                yield Static(_EMPTY_HINT, id="greek-pipeline")
            with TabPane("lexicon", id="tab-lexicon"):
                yield Static(_EMPTY_HINT, id="greek-lexicon")
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
                with Horizontal(id="greek-period-row"):
                    yield Static("period:", id="greek-period-label")
                    yield Select(
                        _PERIODS,
                        value="attic",
                        allow_blank=False,
                        id="greek-period",
                    )
                yield Static(_EMPTY_HINT, id="greek-ipa")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input so the user can type immediately."""
        self.query_one("#greek-input", Input).focus()

    # ── the selected meter / period / resolved Greek text ───────────────────
    @property
    def _meter(self) -> str:
        """The meter currently chosen in the scansion selector."""
        value = self.query_one("#greek-meter", Select).value
        return str(value) if value is not Select.BLANK else "hexameter"

    @property
    def _period(self) -> str:
        """The reconstruction period chosen in the IPA selector."""
        value = self.query_one("#greek-period", Select).value
        return str(value) if value is not Select.BLANK else "attic"

    @property
    def betacode_mode(self) -> bool:
        """Whether ASCII Beta Code conversion is enabled for input."""
        return self._betacode_mode

    def _resolve_text(self, raw: str) -> str:
        if self._betacode_mode and raw.strip():
            return adapter.greek_betacode(raw)
        return raw

    @property
    def _text(self) -> str:
        """The current resolved Greek input text."""
        return self._resolve_text(self.query_one("#greek-input", Input).value)

    # ── live updates ────────────────────────────────────────────────────────
    _debounce: "Timer | None" = None

    def action_focus_input(self) -> None:
        """Focus the text input (the ``/`` binding)."""
        self.query_one("#greek-input", Input).focus()

    def action_toggle_betacode(self) -> None:
        """Toggle live ASCII Beta Code -> Unicode conversion (the ``b`` binding)."""
        self._betacode_mode = not self._betacode_mode
        raw = self.query_one("#greek-input", Input).value
        self._refresh_all(raw)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-render every tab as the line changes, coalescing keystrokes with a short
        debounce so a fast typist doesn't re-run all backends per character."""
        text = event.value
        if self._debounce is not None:
            self._debounce.stop()
        self._debounce = self.set_timer(0.12, lambda: self._refresh_all(text))

    def on_select_changed(self, event: Select.Changed) -> None:
        """Re-render the tab whose selector changed (meter -> scansion, period -> IPA)."""
        if event.select.id == "greek-meter":
            self._render_scansion(self._text)
        elif event.select.id == "greek-period":
            self._render_ipa(self._text)

    def _refresh_all(self, raw_text: str) -> None:
        text = self._resolve_text(raw_text)
        bar = self.query_one("#greek-betacode-bar", Static)
        if self._betacode_mode:
            bar.update(f"Beta Code ON → {text}" if text.strip() else "Beta Code ON (type ASCII, e.g. mh=nin)")
        else:
            bar.update("")
        self._render_pipeline(text)
        self._render_lexicon(text)
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
        result = adapter.greek_pipeline(text, with_confidence=adapter.confidence_available())
        if not result.ok:
            target.update(result.error)
            return
        from aegean._view import format_confidence

        lines = [
            f"{r['sentence']}:{r['index']:<3}  {r['text']}  {r['upos']}  {r['lemma']}"
            + (f"  [{r.get('lemma_source', '?')}]" if r.get("review_recommended", False) else "")
            + (
                f"  {format_confidence(r['upos_confidence'], r['lemma_confidence'])}"
                if "upos_confidence" in r
                else ""
            )
            for r in result.rows
        ]
        target.update("\n".join(lines) if lines else "no tokens")

    def _render_lexicon(self, text: str) -> None:
        target = self.query_one("#greek-lexicon", Static)
        if not text.strip():
            target.update(_EMPTY_HINT)
            return
        result = adapter.greek_gloss(text)
        if not result.ok:
            target.update(result.error)
            return
        lines = [
            f"{r['word']}  →  {r['lemma']}"
            + (f"  ({r['strongs']})" if r["strongs"] else "")
            + (f"  —  {r['gloss']}  [{r['source']}]" if r["gloss"] else "  —  (no gloss)")
            for r in result.rows
        ]
        target.update("\n".join(lines) if lines else "no words")

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
        result = adapter.greek_ipa(text, period=self._period)
        if not result.ok:
            target.update(result.error)
            return
        target.update(result.summary or "no transcription")
