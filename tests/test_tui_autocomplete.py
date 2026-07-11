"""Tests for the command console's completion dropdown (`aegean.tui.screens.console`).

The console gained a floating completion list (the terminal-UI equivalent of the REPL's
prompt_toolkit dropdown): typing filters command paths shown with a dim description
column; Up/Down move the highlight without leaving the prompt; Tab/Enter accept the
highlighted completion; Esc closes the list before it lets the app navigate back. These
tests pin that contract, the geometry (the list overlays above the log and never lands on
the Footer's row), and that the pre-existing key-safety rules (printable keys always type,
the two-stage Esc still leaves) survive.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from textual.widgets import Footer, Input  # noqa: E402

from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.console import (  # noqa: E402
    CommandConsoleScreen,
    CompletionDropdown,
    _command_completions,
)


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def _dropdown_ids(dd: CompletionDropdown) -> list[str]:
    return [dd.get_option_at_index(i).id for i in range(dd.option_count)]


def test_command_completions_pair_each_candidate_with_a_description() -> None:
    """The dropdown mirrors the REPL's descriptions: every command path is paired with its
    short help. This verifies the actual descriptions, not merely that the list is built."""
    from aegean.tui.screens.console import _build_group

    pairs = dict(_command_completions(_build_group()))
    # a leaf command carries its own help; a subcommand pair too
    assert pairs.get("quickstart")  # non-empty description
    assert pairs.get("greek scan")
    # the shell-only directives carry fixed descriptions
    assert pairs["use "] and pairs[":examples"] and pairs[":help"] and pairs[":exit"]
    # an option renders the candidate + description into a Rich renderable (no crash)
    opt = CompletionDropdown.option_for("greek scan", pairs["greek scan"])
    assert opt.id == "greek scan"


def test_typing_a_prefix_opens_the_dropdown_with_filtered_candidates() -> None:
    """Typing a command prefix opens the list filtered to matching command paths."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            dd = screen.query_one("#console-completions", CompletionDropdown)
            assert dd.display is False  # closed until you type
            await pilot.press(*"greek sc")
            await pilot.pause()
            assert dd.display is True
            ids = _dropdown_ids(dd)
            assert "greek scan" in ids  # the subcommand pair is offered
            assert all(c.startswith("greek sc") for c in ids)  # prefix-filtered

    _run(body())


def test_empty_input_and_no_match_keep_the_dropdown_closed() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            dd = screen.query_one("#console-completions", CompletionDropdown)
            screen._refilter("")  # empty: nothing to complete
            assert dd.display is False
            screen._refilter("zzzznotacommand")  # no candidate matches
            assert dd.display is False

    _run(body())


def test_down_then_enter_accepts_a_completion_into_the_input() -> None:
    """Down moves the highlight without leaving the prompt; Enter accepts the highlighted
    completion into the input (a leaf command fills with a trailing space and closes)."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            dd = screen.query_one("#console-completions", CompletionDropdown)
            await pilot.press(*"greek")
            await pilot.pause()
            assert dd.display is True
            assert app.focused is inp  # the highlight moves but focus stays on the prompt
            first = screen._highlighted_candidate()
            await pilot.press("down")
            await pilot.pause()
            moved = screen._highlighted_candidate()
            assert moved is not None and moved != first  # the highlight advanced
            assert app.focused is inp
            await pilot.press("enter")
            await pilot.pause()
            assert inp.value == moved + " "  # accepted, ready for the next word
            assert dd.display is False  # a leaf command closes the list

    _run(body())


def test_tab_accepts_the_highlighted_completion() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            dd = screen.query_one("#console-completions", CompletionDropdown)
            await pilot.press(*"quick")
            await pilot.pause()
            assert dd.display is True
            assert screen._highlighted_candidate() == "quickstart"
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value == "quickstart "  # Tab completed it
            assert isinstance(app.screen, CommandConsoleScreen)  # Tab did not move focus off

    _run(body())


def test_escape_closes_the_dropdown_before_leaving_the_console() -> None:
    """Esc closes the dropdown first and stays on the console (the input keeps focus so the
    user can carry on typing). With the dropdown closed the standard two-stage Esc (blur,
    then walk back) leaves — Esc never leaves the console while the dropdown is open."""

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
            inp = screen.query_one("#console-input", Input)
            dd = screen.query_one("#console-completions", CompletionDropdown)
            await pilot.press(*"greek")
            await pilot.pause()
            assert dd.display is True
            await pilot.press("escape")  # closes the dropdown only
            await pilot.pause()
            assert dd.display is False
            assert isinstance(app.screen, CommandConsoleScreen)  # did NOT leave
            assert app.focused is inp  # still focused, ready to type
            # dropdown closed: the two-stage Esc now leaves (blur, then back)
            await pilot.press("escape")  # blur
            await pilot.pause()
            await pilot.press("escape")  # walk back
            await pilot.pause()
            assert not isinstance(app.screen, CommandConsoleScreen)

    _run(body())


def test_typing_still_lands_in_the_prompt_with_the_dropdown_active() -> None:
    """The 0.20.3 key-safety rule survives the dropdown: printable keys always type into the
    prompt (a bare letter never triggers a global binding, e.g. 'q' never quits)."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            inp = screen.query_one("#console-input", Input)
            await pilot.press("q", "u", "i", "t")  # 'q' is the app's quit key
            await pilot.pause()
            assert inp.value == "quit"  # it typed, it did not quit
            assert isinstance(app.screen, CommandConsoleScreen)

    _run(body())


def test_the_dropdown_overlays_above_the_prompt_without_reaching_the_footer() -> None:
    """The completion list is a layer overlay: it must not reflow the log and must sit
    strictly above the prompt, well clear of the docked Footer's row (the 0.20.4 hazard)."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            from textual.widgets import RichLog

            log = screen.query_one("#console-log", RichLog)
            inp = screen.query_one("#console-input", Input)
            foot = screen.query_one(Footer)
            dd = screen.query_one("#console-completions", CompletionDropdown)
            log_height = log.region.height
            # open a tall list (a group with many subcommands), so it would collide if docked wrong
            screen._refilter("greek ")
            await pilot.pause()
            await pilot.pause()
            assert dd.display is True
            assert dd.option_count >= 10  # tall enough to matter
            # the overlay did not push the log around
            assert log.region.height == log_height
            # it sits strictly above the prompt, which stays on its own row above the Footer
            assert dd.region.y + dd.region.height <= inp.region.y
            assert inp.region.y < foot.region.y
            # and never reaches the Footer's row
            assert dd.region.y + dd.region.height <= foot.region.y

    _run(body())


def test_a_completed_command_still_executes() -> None:
    """Completing a command and then running it works end to end: accept a command, finish
    the line, submit, and the output lands in the log."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("console")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CommandConsoleScreen)
            from textual.widgets import RichLog

            inp = screen.query_one("#console-input", Input)
            log = screen.query_one("#console-log", RichLog)
            # complete "info" from a prefix via Tab
            await pilot.press(*"inf")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            assert inp.value == "info "
            before = len(log.lines)
            # finish the line and run it
            inp.value = "info lineara"
            screen.on_input_submitted(Input.Submitted(inp, "info lineara"))
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert inp.value == ""  # cleared on submit
            assert len(log.lines) > before  # output landed
            assert isinstance(app.screen, CommandConsoleScreen)  # no crash

    _run(body())
