"""Regression: the command console's exit words must leave the console.

The console dropdown advertises ``:exit`` ("leave the console") and the REPL runner
defines ``_EXIT_WORDS = {:exit, :quit, :q, exit, quit}``, but the dispatch discarded
``_run_line``'s stop signal, so every exit word was a silent no-op — the prompt cleared
and nothing happened, leaving Esc as the only way out. The fix intercepts an exit word on
submit and leaves via the app's own back-navigation (the same path Esc walks).

These are TUI Pilot tests; ``test_fix_*`` does not match the conftest's ``test_tui_``
auto-grouping, so the module is pinned to the ``tui`` xdist group explicitly (serial under
``pytest -n N --dist loadgroup``, a no-op serial otherwise).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

pytestmark = pytest.mark.xdist_group("tui")

from textual.widgets import Input, RichLog  # noqa: E402

from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.console import CommandConsoleScreen  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


@pytest.mark.parametrize("word", [":exit", ":quit", ":q", "exit", "quit"])
def test_exit_word_leaves_the_console(word: str) -> None:
    """Submitting any of the five REPL exit words leaves the console via the app's
    screen-history back navigation (returns to the previously shown screen), not a no-op."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")  # a previous screen so back-navigation has somewhere to go
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            inp.value = word
            screen.on_input_submitted(Input.Submitted(inp, word))
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not isinstance(app.screen, CommandConsoleScreen)  # left the console
            assert app.screen is app.get_screen("corpus")  # back to the previous screen

    _run(body())


def test_exit_word_typed_at_the_prompt_leaves_the_console() -> None:
    """The keyboard path leaves too: typing an exit word and pressing Enter (the dropdown
    resolves, then Enter submits) walks back off the console screen."""

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
            await pilot.press(*list("quit"))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not isinstance(app.screen, CommandConsoleScreen)  # left the console

    _run(body())


def test_help_directive_stays_on_the_console() -> None:
    """Control: a non-exit directive (:help) renders output and keeps the user on the
    console — only the exit words leave, everything else dispatches normally."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            log = screen.query_one("#console-log", RichLog)
            before = len(log.lines)
            inp = screen.query_one("#console-input", Input)
            inp.value = ":help"
            screen.on_input_submitted(Input.Submitted(inp, ":help"))
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, CommandConsoleScreen)  # stayed on the console
            assert len(log.lines) > before  # :help rendered the command map

    _run(body())


def test_exit_word_does_not_dispatch_to_the_worker() -> None:
    """An exit word is handled on submit, before dispatch: the runner (which produces no
    output for exit words) is never invoked, so no ``aegean> exit`` echo is written and the
    input clears. This pins that the fix short-circuits rather than dispatching a no-op."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            log = screen.query_one("#console-log", RichLog)
            inp = screen.query_one("#console-input", Input)
            inp.value = ":exit"
            screen.on_input_submitted(Input.Submitted(inp, ":exit"))
            await pilot.pause()
            assert inp.value == ""  # the prompt cleared
            # the exit line is never echoed: the fix short-circuits before the dispatch that
            # would write "aegean> <line>", so no such echo lands in the log
            plain_after = "\n".join(str(line) for line in log.lines)
            assert "aegean> :exit" not in plain_after

    _run(body())


if __name__ == "__main__":
    for _word in (":exit", ":quit", ":q", "exit", "quit"):
        test_exit_word_leaves_the_console(_word)
    test_exit_word_typed_at_the_prompt_leaves_the_console()
    test_help_directive_stays_on_the_console()
    test_exit_word_does_not_dispatch_to_the_worker()
