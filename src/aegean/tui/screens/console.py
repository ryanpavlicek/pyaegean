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

import threading
from typing import TYPE_CHECKING, Any, Callable

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.worker import Worker

__all__ = [
    "CommandConsoleScreen",
    "CompletionDropdown",
    "capture_dispatch",
    "run_console_command",
]

_CAPTURE_LOCK = threading.Lock()


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
    with _CAPTURE_LOCK:
        prior = _common._console
        _common._console = capture
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                dispatch()
        finally:
            _common._console = prior
    return buf.getvalue()


_CACHED_GROUP: Any = None
_CACHED_COMPLETIONS: tuple[tuple[str, str], ...] | None = None


def _build_group() -> Any:
    """The live root Click group (the same surface bare ``aegean`` exposes)."""
    global _CACHED_GROUP
    if _CACHED_GROUP is None:
        import typer

        from aegean.cli import _build_app

        _CACHED_GROUP = typer.main.get_command(_build_app())
    return _CACHED_GROUP


# The shell-only directives, with a one-line description each (mirroring the REPL's
# dropdown, which shows a command's short help beside it). ``use`` keeps its trailing
# space so accepting it leaves the cursor ready for the corpus id.
_DIRECTIVES: tuple[tuple[str, str], ...] = (
    ("use ", "set a session corpus (corpus-first commands default to it)"),
    (":examples", "copyable starter command lines"),
    (":help", "show the command map"),
    (":exit", "leave the console"),
)


def _short_help(cmd: Any) -> str:
    """A command's one-line description for the dropdown, collapsed to a single line."""
    from aegean.cli._complete import short_help

    return short_help(cmd)


def _command_completions(group: Any) -> list[tuple[str, str]]:
    """``(command-path, description)`` pairs for the console's completion catalog: every
    top-level command and every nested subcommand path at arbitrary depth (including
    3-level paths such as ``greek interop export`` and ``bible read``), plus shell directives."""
    global _CACHED_COMPLETIONS
    if _CACHED_GROUP is not None and group is _CACHED_GROUP:
        if _CACHED_COMPLETIONS is None:
            from aegean.cli._complete import walk_command_paths

            _CACHED_COMPLETIONS = tuple(walk_command_paths(group, include_directives=True))
        return list(_CACHED_COMPLETIONS)
    from aegean.cli._complete import walk_command_paths

    return walk_command_paths(group, include_directives=True)


def _command_candidates(group: Any) -> list[str]:
    """The command-path strings alone (for tests and callers inspecting the command catalog)."""
    return [cand for cand, _ in _command_completions(group)]


def run_console_command(group: Any, line: str, session: Any) -> str:
    """Dispatch one console line through the REPL's own runner, capturing the output."""
    from aegean.cli._repl import _run_line

    def _dispatch() -> None:
        # The screen intercepts exit words before dispatch (they are the only lines for which
        # _run_line returns its stop signal), so the bool is always True here and discarded.
        _run_line(group, line, session)

    return capture_dispatch(_dispatch)


class CompletionDropdown(OptionList):
    """A floating completion list under the console prompt: command paths with a dim
    description column, filtered as you type.

    It overlays ABOVE the log via the console body's layer system (a dedicated
    ``dropdown`` layer, docked to the bottom of the body just above the one-row prompt),
    so it never reflows the layout and can never land on the Footer's row (the 0.20.4
    geometry hazard). It never takes focus — the prompt keeps focus so every printable
    key types (the 0.20.3 safety contract); the screen drives the highlight and accepts a
    completion on the user's behalf."""

    can_focus = False

    @staticmethod
    def option_for(candidate: str, description: str) -> Option:
        """One option: the command path, then its description dimmed. Built as a Rich
        ``Text`` (OptionList renders renderables directly), with the candidate as the
        option id so the screen can read back the highlighted completion."""
        from rich.text import Text

        label = Text(candidate.strip(), style="bold")
        if description:
            label.append("  ")
            label.append(description, style="dim")
        return Option(label, id=candidate)


class CommandConsoleScreen(Screen[None]):
    """A REPL-style console with full CLI parity (any command, captured output)."""

    BINDINGS = [
        ("slash", "focus_input", "Input"),
        ("i", "focus_input", "Input"),
    ]

    # A prompt LINE, not a boxed form: the input is borderless with an "aegean>" mark, so
    # it reads like a shell. As you type, a floating completion dropdown appears above the
    # prompt (command paths + descriptions), plus an inline ghost-text suggestion and
    # up/down history, the way the REPL feels.
    # The log and the prompt live in one Vertical that fills the space between the Header and
    # the Footer. The prompt must NOT be docked to the bottom: a bottom dock lands on the same
    # row the Footer auto-docks to, and the Footer then paints over the input so the cursor,
    # the typed text, and the ghost completion are all invisible. Inside the body the log takes
    # the free space (1fr) and the prompt keeps its own one-row line just above the Footer.
    # The dropdown lives on a dedicated "dropdown" layer of the body and is docked to the
    # body's bottom (lifted one row to clear the prompt): a layer overlays the log WITHOUT
    # reflowing it, and being bounded by the body it can never reach the Footer's row.
    DEFAULT_CSS = """
    #console-body { height: 1fr; layers: base dropdown; }
    #console-log { height: 1fr; layer: base; border: round $primary-darken-2; padding: 0 1; }
    #console-prompt { height: 1; layer: base; width: 1fr; margin: 0 1; }
    #console-prompt-mark { width: 8; padding: 0 1 0 0; color: $success; text-style: bold; }
    #console-input { border: none; background: transparent; padding: 0; height: 1; width: 1fr; }
    #console-completions {
        layer: dropdown; dock: bottom; margin: 0 1 1 1;
        width: auto; min-width: 40; max-width: 100%;
        height: auto; max-height: 12;
        border: round $primary; background: $panel; display: none;
    }
    """

    _history: list[str]
    _hist_pos: int
    _completions: list[tuple[str, str]]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="console-body"):
            yield RichLog(id="console-log", highlight=False, markup=False, wrap=True)
            with Horizontal(id="console-prompt"):
                yield Static("aegean>", id="console-prompt-mark")
                yield Input(
                    placeholder="any command without 'aegean' "
                    "(↑/↓ pick · Tab/Enter complete · Esc close · ↑/↓ history when closed)",
                    id="console-input",
                )
            yield CompletionDropdown(id="console-completions")
        yield Footer()

    def on_mount(self) -> None:
        from aegean.cli._repl import _Session

        self._session = _Session()
        self._history = []
        self._hist_pos = 0
        self._completions = []
        # Setting the input value in code (history recall) posts an Input.Changed; this flag
        # tells that handler to close the dropdown once rather than reopening it on the recalled
        # line, so recalling history never hijacks the next Up/Down for the dropdown.
        self._suppress_filter = False
        log = self.query_one("#console-log", RichLog)
        try:
            self._group = _build_group()
        except ModuleNotFoundError:
            self._group = None
            log.write("the command console needs the [cli] extra — pip install 'pyaegean[cli]'")
            self.query_one("#console-input", Input).disabled = True
            return
        from textual.suggester import Suggester

        # The log must never take focus away from the prompt: if it did, a bare letter would
        # fall through to a global binding (q quits the app) instead of being typed. It still
        # auto-scrolls to the newest output and scrolls under the mouse wheel.
        log.can_focus = False
        inp = self.query_one("#console-input", Input)
        self._completions = _command_completions(self._group)
        group = self._group
        history_ref = self._history

        class _ConsoleSuggester(Suggester):
            def __init__(self) -> None:
                super().__init__(use_cache=False, case_sensitive=False)

            async def get_suggestion(self, value: str) -> str | None:
                from aegean.cli._complete import suggest_inline

                return suggest_inline(group, value, history=history_ref, directives=True)

        # Inline ghost-text combines session history + live command/flag/value prediction
        # (accepted with →); the dropdown offers the full ranked list with descriptions.
        inp.suggester = _ConsoleSuggester()
        log.write(
            "aegean command console — type any command without the 'aegean' prefix. "
            "A completion list opens as you type: ↑/↓ pick · Tab/Enter complete · Esc close. "
            "↑/↓ recall history when the list is closed. :examples for starters · :help for this menu."
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

    # ── the completion dropdown ────────────────────────────────────────────────
    def _dropdown(self) -> CompletionDropdown:
        return self.query_one("#console-completions", CompletionDropdown)

    def _dropdown_open(self) -> bool:
        return bool(self._dropdown().display)

    def _is_group_path(self, line: str) -> bool:
        """True when ``line`` names a Click/Typer command group (not a leaf command)."""
        if self._group is None:
            return False
        import typer

        from aegean.cli._complete import is_group

        parts = line.strip().split()
        if not parts:
            return False
        ctx = typer.Context(self._group, info_name="aegean")
        cmd: Any = self._group
        for tok in parts:
            if not is_group(cmd):
                return False
            sub = cmd.get_command(ctx, tok)
            if sub is None:
                return False
            cmd = sub
        return is_group(cmd)

    def _refilter(self, value: str) -> None:
        """Rebuild the dropdown from live context-aware completions (commands at any nesting
        depth, leaf option flags, and offline domain values) for the typed line ``value``."""
        if self._group is None:
            return
        dd = self._dropdown()
        if not value.strip():
            self._close_dropdown()
            return
        from aegean.cli._complete import complete_line

        items = complete_line(self._group, value, directives=True)
        entries: list[tuple[str, str]] = [(item.full_line, item.description) for item in items]
        seen = {full for full, _ in entries}

        # When typing a command/group prefix without a trailing space (e.g. "greek" or "bible"),
        # also surface matching subcommand paths so Up/Down can jump straight into a subcommand.
        if not value.endswith(" "):
            low = value.lstrip().casefold()
            for cmd_path, desc in self._completions:
                if cmd_path.casefold().startswith(low) and cmd_path not in seen:
                    seen.add(cmd_path)
                    entries.append((cmd_path, desc))

        if not entries:
            self._close_dropdown()
            return
        dd.clear_options()
        dd.add_options([CompletionDropdown.option_for(full, desc) for full, desc in entries[:25]])
        dd.highlighted = 0
        dd.display = True

    def _close_dropdown(self) -> None:
        self._dropdown().display = False

    def _highlighted_candidate(self) -> str | None:
        dd = self._dropdown()
        idx = dd.highlighted
        if idx is None or idx < 0 or idx >= dd.option_count:
            return None
        return dd.get_option_at_index(idx).id

    def _move_highlight(self, delta: int) -> None:
        dd = self._dropdown()
        n = dd.option_count
        if n == 0:
            return
        cur = dd.highlighted if dd.highlighted is not None else 0
        dd.highlighted = max(0, min(n - 1, cur + delta))
        scroll = getattr(dd, "scroll_to_highlight", None)
        if callable(scroll):
            scroll()

    def _accept_candidate(self, candidate: str) -> None:
        """Fill the prompt with the highlighted completion (a trailing space so the cursor
        is ready for the next word). A command group keeps the dropdown open showing its
        subcommands; a leaf command or argument closes the list until the user types or
        presses Tab again."""
        inp = self.query_one("#console-input", Input)
        filled = candidate if candidate.endswith(" ") else candidate.rstrip() + " "
        is_grp = self._is_group_path(candidate)
        if not is_grp:
            self._suppress_filter = True
        inp.value = filled
        inp.cursor_position = len(inp.value)
        if is_grp:
            self._refilter(inp.value)
        else:
            self._close_dropdown()
        inp.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "console-input":
            return
        if self._suppress_filter:
            self._suppress_filter = False
            self._close_dropdown()
            return
        self._refilter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "console-input":
            return
        # Enter with the dropdown open ACCEPTS the highlighted completion when it extends
        # what the user typed (not an exact match, and never a stale option for another line).
        # With the dropdown closed (or on an exact match), Enter submits — the ordinary case.
        typed = event.value.strip()
        if self._dropdown_open():
            cand = self._highlighted_candidate()
            if (
                cand is not None
                and cand.rstrip() != typed
                and cand.casefold().startswith(typed.casefold())
            ):
                self._accept_candidate(cand)
                return
            self._close_dropdown()
        line = typed
        event.input.value = ""
        if not line:
            return
        # An exit word is exactly where the REPL runner returns its stop signal; leave the
        # console instead of dispatching it to a silent no-op (the runner produces no output
        # for these, so a dispatched exit word would just clear the prompt and do nothing).
        from aegean.cli._repl import _EXIT_WORDS

        if line in _EXIT_WORDS:
            self._leave_console()
            return
        self._history.append(line)
        self._hist_pos = len(self._history)
        if self._group is None:
            return
        self.query_one("#console-log", RichLog).write(f"aegean> {line}")
        self._dispatch_worker(line)

    def _leave_console(self) -> None:
        """Leave the console the same way Esc does: blur the prompt, then walk the app's
        screen-history back. This reuses the app-owned back-navigation (``action_go_back``)
        rather than introducing a second navigation mechanism; blurring first collapses the
        two-Esc dance (first Esc blurs the input, second walks back) into one step."""
        app = self.app
        app.set_focus(None)
        app.action_go_back()  # type: ignore[attr-defined]

    def on_key(self, event: Any) -> None:
        """Keep every keystroke going to the prompt and drive the completion dropdown.

        If focus ever drifts off the input (a click on the log, a terminal focus quirk), a
        printable key re-focuses the prompt and is swallowed, so a bare letter can never trigger
        a global binding (q would quit the whole app) instead of typing. When the prompt is
        focused it consumes printable keys itself before this runs, so here only the navigation
        keys are handled:

        - Tab accepts the highlighted completion when open, or opens live completions on demand
          when closed (and never moves focus off the prompt);
        - Esc closes the dropdown first, and only bubbles to the app's back-navigation when
          the dropdown is already closed;
        - Up/Down move the dropdown highlight while it is open, and recall history when it is
          closed (the original behaviour).
        """
        inp = self.query_one("#console-input", Input)
        if self.focused is not inp:
            char = getattr(event, "character", None)
            if char is not None and char.isprintable():
                inp.focus()
                event.stop()
            return
        key = event.key
        open_ = self._dropdown_open()
        if key == "escape":
            if open_:
                self._close_dropdown()
                event.stop()  # consumed here, so the app's Esc back-navigation does not fire
            return  # closed: let Esc bubble to the app (blur the input, then walk back)
        if key == "tab":
            if open_:
                cand = self._highlighted_candidate()
                if cand is not None:
                    self._accept_candidate(cand)
            else:
                self._refilter(inp.value)
            event.stop()  # never let Tab move focus off the prompt
            return
        if key not in ("up", "down"):
            return
        if open_:
            self._move_highlight(1 if key == "down" else -1)
            event.stop()
            return
        if not self._history:
            return
        self._suppress_filter = True  # the recalled line must not reopen the dropdown
        if key == "up":
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
