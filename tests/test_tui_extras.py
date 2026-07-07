"""Pilot tests for the TUI usability additions: theme preview + persistence,
the help overlay, Esc back-navigation, and the koine IPA selector.
"""

from __future__ import annotations

import asyncio
import types

import pytest

pytest.importorskip("textual")

from textual.widgets import Select  # noqa: E402

from aegean.tui import data as adapter  # noqa: E402
from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.greek import GreekWorkbenchScreen  # noqa: E402
from aegean.tui.screens.help import HelpScreen  # noqa: E402
from aegean.tui.screens.theme import ThemeScreen  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def test_theme_previews_on_highlight_without_dismissing_and_persists_on_select(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, object] = {}
    monkeypatch.setattr(adapter, "load_tui_config", lambda: dict(saved))
    monkeypatch.setattr(adapter, "save_tui_config", lambda d: saved.update(d))

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.action_theme()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ThemeScreen)
            some_theme = next(t for t in app.available_themes if t != app.theme)
            # highlight applies the theme live and does NOT dismiss the modal
            screen.on_option_list_option_highlighted(types.SimpleNamespace(option_id=some_theme))
            await pilot.pause()
            assert app.theme == some_theme
            assert isinstance(app.screen, ThemeScreen)  # still open to try more
            # selecting (Enter) persists and dismisses
            screen.on_option_list_option_selected(types.SimpleNamespace(option_id=some_theme))
            await pilot.pause()
            assert not isinstance(app.screen, ThemeScreen)
            assert saved.get("theme") == some_theme

    _run(body())


def test_persisted_theme_is_applied_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def body() -> None:
        probe = AegeanApp()
        target = next(t for t in probe.available_themes if t != probe.theme)
        monkeypatch.setattr(adapter, "load_tui_config", lambda: {"theme": target})
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert app.theme == target

    _run(body())


def test_question_mark_opens_the_help_overlay_not_home() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            baseline = len(app.screen_stack)
            app.action_help()
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            assert len(app.screen_stack) == baseline + 1  # a modal pushed, not a nav

    _run(body())


def test_escape_walks_back_to_the_previous_screen() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert app._current_screen_name == "home"
            app.goto("corpus")
            await pilot.pause()
            assert app._current_screen_name == "corpus"
            app.set_focus(None)  # so Esc goes back rather than blurring an input
            app.action_go_back()
            await pilot.pause()
            assert app._current_screen_name == "home"
            # Esc at Home with empty history is a safe no-op
            app.action_go_back()
            await pilot.pause()
            assert app._current_screen_name == "home"

    _run(body())


def test_greek_ipa_period_selector_switches_to_koine() -> None:
    # the adapter accepts the koine period (the screen wires this selector to it)
    assert adapter.greek_ipa("θεός", period="koine").ok
    assert adapter.greek_ipa("θεός", period="attic").ok

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.goto("greek")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GreekWorkbenchScreen)
            select = screen.query_one("#greek-period", Select)
            assert screen._period == "attic"
            select.value = "koine"
            await pilot.pause()
            assert screen._period == "koine"

    _run(body())
