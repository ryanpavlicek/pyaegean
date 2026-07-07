"""The in-reader line-analysis modal.

Opened from the corpus reader on the highlighted line (Enter / ``a``). It offers the
analyses that fit the line's script — for Greek the offline parser/tagger, the neural
pipeline, IPA, and (optional, BYOAI) translation; for Linear B / Cypriot the Greek
reading + gloss and sign values; for the undeciphered scripts sign values and an
exploratory transliteration, plainly caveated. All of that logic lives in the
``tui.data`` adapter; this screen is a thin view over it.

Fast analyses run inline; the slow ones (the neural model, a translation call) run on a
Textual worker with a loading line, so the UI never blocks. Esc closes the modal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .. import data as adapter

if TYPE_CHECKING:
    from textual.worker import Worker

__all__ = ["LineAnalysisScreen"]

# The analyses that need to run off the UI thread (a model load / inference, a network
# translation call). Everything else is instant and renders inline.
_SLOW = frozenset({"neural", "translate"})


def format_result(result: adapter.AnalysisResult) -> str:
    """Render an :class:`~aegean.tui.data.AnalysisResult` to display text: a title, then
    either an aligned table (columns + rows) or a prose block, then any note/caveat.
    Kept module-level and Textual-free so it can be unit-tested directly."""
    if not result.ok:
        return result.error or "analysis failed"
    out: list[str] = []
    if result.title:
        out.append(result.title)
        out.append("")
    if result.columns:
        widths = [len(c) for c in result.columns]
        for row in result.rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        out.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(result.columns)))
        out.append("  ".join("-" * widths[i] for i in range(len(result.columns))))
        for row in result.rows:
            out.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
        if not result.rows:
            out.append("(nothing to show)")
    elif result.text:
        out.append(result.text)
    else:
        out.append("(nothing to show)")
    if result.note:
        out.append("")
        out.append(result.note)
    return "\n".join(out)


class LineAnalysisScreen(ModalScreen[None]):
    """A centered popup that analyses one reader line. Given the line's script, number,
    text, and token surface forms, it lists the fitting analyses and runs the chosen one."""

    DEFAULT_CSS = """
    LineAnalysisScreen { align: center middle; }
    #analysis-box {
        width: 90%; max-width: 100; height: 90%; max-height: 90%;
        border: round $primary; background: $panel; padding: 1 2;
    }
    #analysis-line { text-style: bold; color: $accent; height: auto; padding-bottom: 1; }
    #analysis-options { height: auto; max-height: 8; border: round $primary-darken-2; }
    #analysis-output-scroll { height: 1fr; border: round $primary-darken-2; margin-top: 1; }
    #analysis-output { height: auto; padding: 0 1; }
    #analysis-hint { color: $text-muted; height: auto; padding-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(
        self, *, script_id: str, line_number: int, line_text: str, token_texts: tuple[str, ...]
    ) -> None:
        super().__init__()
        self._script_id = script_id
        self._line_number = line_number
        self._line_text = line_text
        self._token_texts = token_texts
        self._options = {o.key: o for o in adapter.line_analyses(script_id)}

    def compose(self) -> ComposeResult:
        with Vertical(id="analysis-box"):
            shown = self._line_text if len(self._line_text) <= 80 else self._line_text[:77] + "…"
            yield Static(f"line {self._line_number}:  {shown}", id="analysis-line")
            options = [
                Option(self._option_label(o), id=o.key) for o in self._options.values()
            ]
            yield OptionList(*options, id="analysis-options")
            with VerticalScroll(id="analysis-output-scroll"):
                yield Static("", id="analysis-output")
            yield Static("↑/↓ choose · Enter run · Esc close", id="analysis-hint")

    @staticmethod
    def _option_label(opt: adapter.AnalysisOption) -> str:
        if opt.available:
            return opt.label
        return f"{opt.label}  ·  unavailable: {opt.detail}"

    def on_mount(self) -> None:
        # Run the first available analysis immediately so the popup is never empty, and
        # keep the options list focused so the arrow keys pick a different one.
        options = self.query_one("#analysis-options", OptionList)
        options.focus()
        first = next((o for o in self._options.values() if o.available), None)
        if first is not None:
            self._run(first.key)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        key = event.option.id
        if key is not None:
            self._run(key)

    def _run(self, key: str) -> None:
        opt = self._options.get(key)
        output = self.query_one("#analysis-output", Static)
        if opt is not None and not opt.available:
            output.update(f"{opt.label} is unavailable.\n\n{opt.detail}")
            return
        if key in _SLOW:
            output.update("analyzing…")
            self._analyze_worker(key)
            return
        result = adapter.run_line_analysis(
            key, script_id=self._script_id, text=self._line_text, token_texts=self._token_texts
        )
        output.update(format_result(result))

    @work(thread=True, exclusive=True, group="analyze")
    def _analyze_worker(self, key: str) -> None:
        from textual.worker import get_current_worker

        worker = get_current_worker()
        try:
            result = adapter.run_line_analysis(
                key, script_id=self._script_id, text=self._line_text, token_texts=self._token_texts
            )
        except Exception as exc:  # the adapter is total, but never let a worker crash the app
            result = adapter.AnalysisResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        if not worker.is_cancelled:
            self.app.call_from_thread(self._show_result, result)

    def _show_result(self, result: adapter.AnalysisResult) -> None:
        self.query_one("#analysis-output", Static).update(format_result(result))

    def on_worker_state_changed(self, event: "Worker.StateChanged") -> None:  # noqa: ARG002
        return

    def action_close(self) -> None:
        self.dismiss()

    # A stable hook the tests use to read what is currently shown.
    def output_text(self) -> Any:
        return self.query_one("#analysis-output", Static).content
