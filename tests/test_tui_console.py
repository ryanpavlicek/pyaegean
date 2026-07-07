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

from textual.widgets import Input, RichLog  # noqa: E402

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
