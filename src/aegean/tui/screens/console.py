"""The command console: a REPL inside the TUI, for full CLI/REPL parity.

The REPL already dispatches every command through one Typer group, so this screen
mirrors it: type any command without the ``aegean`` prefix and its output renders
in a scrolling log. It reuses the REPL's own ``_run_line`` (so ``use CORPUS``,
``:examples`` and every command behave identically) and captures the output.

Capturing is belt-and-suspenders because two-thirds of CLI output never goes through
the rich console: it swaps ``aegean.cli._common._console`` for a forced-terminal
capture console (so ``console().print`` / tables land in the buffer with styling) and
redirects ``stdout``/``stderr`` (so bare ``print`` / ``emit_json`` / error lines land
in the same buffer, in order). The captured ANSI is parsed back into styled text.

Dispatch runs on an exclusive worker so the swapped global can never race between two
commands, and so a long or networked command keeps the UI responsive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static

if TYPE_CHECKING:
    from textual.worker import Worker

__all__ = ["CommandConsoleScreen", "capture_dispatch", "run_console_command"]


def capture_dispatch(dispatch: Callable[[], None]) -> str:
    """Run ``dispatch()`` capturing stdout, stderr, and the CLI's rich console into one
    ANSI string, always restoring the swapped console. Textual-free and unit-testable."""
    import contextlib
    import io

    import rich.console

    from aegean.cli import _common

    buf = io.StringIO()
    capture = rich.console.Console(
        file=buf, force_terminal=True, color_system="truecolor", width=100, soft_wrap=False
    )
    prior = _common._console
    _common._console = capture
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            dispatch()
    finally:
        _common._console = prior
    return buf.getvalue()


def _build_group() -> Any:
    """The live root Click group (the same surface bare ``aegean`` exposes)."""
    import typer

    from aegean.cli import _build_app

    return typer.main.get_command(_build_app())


def _command_candidates(group: Any) -> list[str]:
    """Command-path candidates for the console's predictive completion: every top-level
    command and every ``group sub`` pair, plus the shell-only directives."""
    import click

    out: list[str] = []
    for name, cmd in sorted(group.commands.items()):
        out.append(name)
        if isinstance(cmd, click.Group):
            for sub in sorted(cmd.commands):
                out.append(f"{name} {sub}")
    out += ["use ", ":examples", ":help", ":exit"]
    return out


def run_console_command(group: Any, line: str, session: Any) -> str:
    """Dispatch one console line through the REPL's own runner, capturing the output."""
    from aegean.cli._repl import _run_line

    def _dispatch() -> None:
        _run_line(group, line, session)  # its bool return (stop-the-loop) is irrelevant here

    return capture_dispatch(_dispatch)


class CommandConsoleScreen(Screen[None]):
    """A REPL-style console with full CLI parity (any command, captured output)."""

    BINDINGS = [
        ("slash", "focus_input", "Input"),
        ("i", "focus_input", "Input"),
    ]

    # A prompt LINE, not a boxed form: the input is borderless with an "aegean>" mark, so
    # it reads like a shell. It gains predictive ghost-text completion (Tab/→ accepts) and
    # up/down history, the way the REPL feels.
    DEFAULT_CSS = """
    #console-log { height: 1fr; border: round $primary-darken-2; padding: 0 1; }
    #console-prompt { dock: bottom; height: 1; margin: 0 1; }
    #console-prompt-mark { width: auto; padding: 0 1 0 0; color: $success; text-style: bold; }
    #console-input { border: none; background: transparent; padding: 0; height: 1; }
    """

    _history: list[str]
    _hist_pos: int

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="console-log", highlight=False, markup=False, wrap=True)
        with Horizontal(id="console-prompt"):
            yield Static("aegean>", id="console-prompt-mark")
            yield Input(
                placeholder="any command without 'aegean' (Tab/→ completes · ↑/↓ history · :examples)",
                id="console-input",
            )
        yield Footer()

    def on_mount(self) -> None:
        from aegean.cli._repl import _Session

        self._session = _Session()
        self._history = []
        self._hist_pos = 0
        log = self.query_one("#console-log", RichLog)
        try:
            self._group = _build_group()
        except ModuleNotFoundError:
            self._group = None
            log.write("the command console needs the [cli] extra — pip install 'pyaegean[cli]'")
            self.query_one("#console-input", Input).disabled = True
            return
        from textual.suggester import SuggestFromList

        inp = self.query_one("#console-input", Input)
        inp.suggester = SuggestFromList(_command_candidates(self._group), case_sensitive=False)
        log.write(
            "aegean command console — any command (no 'aegean' prefix). Tab completes, ↑ recalls. "
            "Try:  quickstart"
        )
        inp.focus()

    def action_focus_input(self) -> None:
        self.query_one("#console-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "console-input":
            return
        line = event.value.strip()
        event.input.value = ""
        if not line:
            return
        self._history.append(line)
        self._hist_pos = len(self._history)
        if self._group is None:
            return
        self.query_one("#console-log", RichLog).write(f"aegean> {line}")
        self._dispatch_worker(line)

    def on_key(self, event: Any) -> None:
        """Up/Down recall previous commands while the prompt is focused (the REPL feel)."""
        if not self._history:
            return
        inp = self.query_one("#console-input", Input)
        if self.focused is not inp or event.key not in ("up", "down"):
            return
        if event.key == "up":
            self._hist_pos = max(0, self._hist_pos - 1)
            inp.value = self._history[self._hist_pos]
        else:
            self._hist_pos = min(len(self._history), self._hist_pos + 1)
            inp.value = "" if self._hist_pos >= len(self._history) else self._history[self._hist_pos]
        inp.cursor_position = len(inp.value)
        event.stop()

    @work(thread=True, exclusive=True, group="console")
    def _dispatch_worker(self, line: str) -> None:
        from textual.worker import get_current_worker

        worker = get_current_worker()
        try:
            text = run_console_command(self._group, line, self._session)
        except Exception as exc:  # a runner failure must never crash the screen
            text = f"aegean: {exc}"
        if not worker.is_cancelled:
            self.app.call_from_thread(self._append, text)

    def _append(self, text: str) -> None:
        from rich.text import Text

        log = self.query_one("#console-log", RichLog)
        rendered = Text.from_ansi(text.rstrip("\n")) if text.strip() else Text("")
        if rendered.plain:
            log.write(rendered)

    def on_worker_state_changed(self, event: "Worker.StateChanged") -> None:  # noqa: ARG002
        return
