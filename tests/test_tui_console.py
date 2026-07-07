"""Tests for the command console (`aegean.tui.screens.console`) and its capture.

The console gives the TUI full CLI parity by dispatching through the same Typer
group the REPL uses and capturing the output. The capture is the delicate part
(two-thirds of CLI output bypasses the rich console), so it is unit-tested
directly: all three streams land in the buffer and the swapped console is always
restored. A Pilot test confirms a submitted line runs on a worker and neither the
input nor the app breaks on a bad command.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

pytest.importorskip("textual")

from textual.widgets import Footer, Input, RichLog  # noqa: E402

from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.console import (  # noqa: E402
    CommandConsoleScreen,
    capture_dispatch,
    run_console_command,
)


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def test_capture_dispatch_captures_all_streams_and_restores_the_console() -> None:
    from aegean.cli import _common

    prior = _common._console

    def dispatch() -> None:
        _common.console().print("RICH-OUT")
        print("STDOUT-OUT")
        sys.stderr.write("STDERR-OUT\n")

    out = capture_dispatch(dispatch)
    assert "RICH-OUT" in out and "STDOUT-OUT" in out and "STDERR-OUT" in out
    # the global console is restored to exactly what it was before
    assert _common._console is prior


def test_run_console_command_runs_a_real_offline_command() -> None:
    from aegean.cli._repl import _Session
    from aegean.tui.screens.console import _build_group

    group = _build_group()
    out = run_console_command(group, "info lineara", _Session())
    assert "lineara" in out.lower()
    # a bad command surfaces an error but does not raise
    err = run_console_command(group, "stats definitely-not-a-corpus", _Session())
    assert err.strip()  # some error text was captured, no exception


def test_submitting_a_line_runs_a_worker_and_clears_the_input() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            log = screen.query_one("#console-log", RichLog)
            before = len(log.lines)
            inp = screen.query_one("#console-input", Input)
            inp.value = "info lineara"
            screen.on_input_submitted(Input.Submitted(inp, "info lineara"))
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert inp.value == ""  # the input cleared
            assert len(log.lines) > before  # output landed in the log
            assert isinstance(app.screen, CommandConsoleScreen)  # no crash

    _run(body())


def test_a_bad_line_does_not_crash_the_console() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            screen.on_input_submitted(Input.Submitted(inp, "stats nope-corpus"))
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, CommandConsoleScreen)

    _run(body())


def test_console_has_a_suggester_and_up_arrow_recalls_history() -> None:
    import types

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            assert inp.suggester is not None  # predictive completion is wired
            for line in ("info lineara", "stats lineara"):
                screen.on_input_submitted(Input.Submitted(inp, line))
                await pilot.pause()
                await app.workers.wait_for_complete()
            inp.focus()
            await pilot.pause()
            screen.on_key(types.SimpleNamespace(key="up", stop=lambda: None))
            assert inp.value == "stats lineara"  # most recent first
            screen.on_key(types.SimpleNamespace(key="up", stop=lambda: None))
            assert inp.value == "info lineara"

    _run(body())


def test_a_stray_key_refocuses_the_prompt_instead_of_quitting_the_app() -> None:
    """If focus drifts off the prompt (a click, a terminal quirk), a bare letter must NOT
    fall through to a global binding — pressing 'q' would otherwise quit the whole app."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            # the log can never steal focus and turn typing into navigation
            assert screen.query_one("#console-log", RichLog).can_focus is False
            # force focus away, as a click on the log or a terminal focus glitch would
            app.set_focus(None)
            await pilot.pause()
            await pilot.press("q")  # the letter that quits the app
            await pilot.pause()
            assert isinstance(app.screen, CommandConsoleScreen)  # did NOT quit
            assert app.focused is inp  # the prompt reclaimed focus
            # and now ordinary letters type into the prompt rather than navigating away
            await pilot.press("q", "u", "i", "t")
            await pilot.pause()
            assert inp.value == "quit"
            assert isinstance(app.screen, CommandConsoleScreen)

    _run(body())


def test_console_prompt_is_visible_above_the_footer() -> None:
    """The prompt must occupy its own row strictly above the Footer and fit within the screen.

    A bottom-docked prompt lands on the Footer's row, and the Footer paints over it, hiding the
    cursor, the typed text, and the ghost completion — the input works but nothing is visible.
    This pins the layout so that collision can't return, and confirms the prompt actually paints.
    """

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await pilot.pause()
            scr = app.screen
            inp = scr.query_one("#console-input", Input)
            foot = scr.query_one(Footer)
            assert inp.region.y < foot.region.y  # prompt on its own row, above the footer
            assert inp.region.x + inp.region.width <= scr.size.width  # no width overflow
            assert app.focused is inp  # focused, so keystrokes land in it
            await pilot.press("q", "u", "i", "c")
            await pilot.pause()
            svg = app.export_screenshot()
            assert "aegean&gt;" in svg or "aegean>" in svg  # the prompt mark is painted
            assert "quic" in svg  # the typed text is painted (not hidden under the footer)

    _run(body())


def test_escape_still_leaves_the_console() -> None:
    """Esc is not printable, so the safety net lets it bubble to the app's back navigation.
    Per the app-wide convention a focused input blurs on the first Esc, then a second Esc
    (nothing focused) walks the history back — the console must not trap the user."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, CommandConsoleScreen)
            await pilot.press("escape")  # blurs the prompt
            await pilot.pause()
            await pilot.press("escape")  # walks back
            await pilot.pause()
            assert not isinstance(app.screen, CommandConsoleScreen)  # navigated back

    _run(body())
