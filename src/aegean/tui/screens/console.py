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
from textual.containers import Horizontal, Vertical
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
    command and every ``group sub`` pair, plus the shell-only directives.

    Sub-groups are detected with the REPL's duck-typed ``_is_group`` (typer's ``TyperGroup``
    is not a ``click.Group`` for ``isinstance``, so the old check silently offered no
    subcommands — ``greek scan``, ``data fetch`` and the rest never completed)."""
    from aegean.cli._repl import _is_group

    out: list[str] = []
    for name, cmd in sorted(group.commands.items()):
        out.append(name)
        if _is_group(cmd):
            for sub in sorted(getattr(cmd, "commands", {})):
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
    # The log and the prompt live in one Vertical that fills the space between the Header and
    # the Footer. The prompt must NOT be docked to the bottom: a bottom dock lands on the same
    # row the Footer auto-docks to, and the Footer then paints over the input so the cursor,
    # the typed text, and the ghost completion are all invisible. Inside the body the log takes
    # the free space (1fr) and the prompt keeps its own one-row line just above the Footer.
    DEFAULT_CSS = """
    #console-body { height: 1fr; }
    #console-log { height: 1fr; border: round $primary-darken-2; padding: 0 1; }
    #console-prompt { height: 1; width: 1fr; margin: 0 1; }
    #console-prompt-mark { width: 8; padding: 0 1 0 0; color: $success; text-style: bold; }
    #console-input { border: none; background: transparent; padding: 0; height: 1; width: 1fr; }
    """

    _history: list[str]
    _hist_pos: int

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="console-body"):
            yield RichLog(id="console-log", highlight=False, markup=False, wrap=True)
            with Horizontal(id="console-prompt"):
                yield Static("aegean>", id="console-prompt-mark")
                yield Input(
                    placeholder="any command without 'aegean' (Tab/→ completes · ↑/↓ history)",
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

        # The log must never take focus away from the prompt: if it did, a bare letter would
        # fall through to a global binding (q quits the app) instead of being typed. It still
        # auto-scrolls to the newest output and scrolls under the mouse wheel.
        log.can_focus = False
        inp = self.query_one("#console-input", Input)
        inp.suggester = SuggestFromList(_command_candidates(self._group), case_sensitive=False)
        log.write(
            "aegean command console — type any command without the 'aegean' prefix. "
            "Tab/→ completes · ↑/↓ history · :examples for starters · :help for this menu."
        )
        # Show the command map on entry, exactly like `aegean repl` does, so the available
        # commands are visible up front instead of only surfacing as you type.
        self._dispatch_worker(":help")
        self.call_after_refresh(inp.focus)

    def on_screen_resume(self) -> None:
        # Re-focus the prompt every time the console is shown (on_mount only fires on the first
        # mount; a re-entry would otherwise leave the prompt unfocused and letters would navigate).
        if getattr(self, "_group", None) is not None:
            self.call_after_refresh(self.query_one("#console-input", Input).focus)

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
        """Keep every keystroke going to the prompt.

        If focus ever drifts off the input (a click on the log, a terminal focus quirk), a
        printable key re-focuses the prompt and is swallowed, so a bare letter can never trigger
        a global binding (q would quit the whole app) instead of typing. When the prompt is
        focused it consumes printable keys itself before this runs, so here Up/Down only recall
        history and non-printable keys (Esc) still bubble to the app for navigation.
        """
        inp = self.query_one("#console-input", Input)
        if self.focused is not inp:
            char = getattr(event, "character", None)
            if char is not None and char.isprintable():
                inp.focus()
                event.stop()
            return
        if not self._history or event.key not in ("up", "down"):
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
