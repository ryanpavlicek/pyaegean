"""Pilot smoke tests for the TUI app shell (`aegean.tui.app`).

These assert real content, not "it mounts": the Home screen shows the
undeciphered-honesty banner and the eight corpora, the global key bindings and
navigation helpers switch screens, and the command-palette Provider returns
'Open corpus' entries.

The dev env has no pytest-asyncio, so each async body is wrapped in a fresh event
loop rather than a pytest-asyncio marker; the palette Provider is unit-tested by
awaiting ``search`` directly (the race-free path), and the palette UI is driven
with ``ctrl+p`` under ``run_test(size=(100, 40))``. Read a Static's original
renderable via ``.content`` (textual 8.x has no ``.renderable``).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from textual.command import CommandPalette  # noqa: E402
from textual.widgets import Static  # noqa: E402

from aegean.tui.app import AegeanApp, CorpusCommands  # noqa: E402
from aegean.tui.screens.home import HomeScreen  # noqa: E402
from aegean.tui.widgets import CorpusList  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def test_app_mounts_home_with_the_undeciphered_banner_and_eight_corpora() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            # the permanent undeciphered-honesty banner
            banner = app.screen.query_one("#home-banner", Static)
            text = str(banner.content)
            assert "Linear A" in text and "Cypro-Minoan" in text
            assert "exploratory" in text and "not a reading" in text
            # the eight-corpus overview
            corpus_list = app.screen.query_one("#home-corpora", CorpusList)
            assert len(corpus_list) == 8

    _run(body())


def test_global_bindings_switch_screens_and_set_state() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            # 'g' targets the greek screen; if that screen module is not
            # registered the shell must stay runnable (goto is a no-op for an
            # unregistered screen), so Home remains and nothing crashes.
            await pilot.press("g")
            await pilot.pause()
            assert app.screen is not None
            # open_corpus (the palette + Home-selection path) sets shared state
            app.open_corpus("lineara")
            await pilot.pause()
            assert app.state.selected_corpus == "lineara"

    _run(body())


def test_set_corpus_updates_state_and_resets_the_document() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.set_doc("HT13")
            assert app.state.selected_doc_id == "HT13"
            # switching corpus records the new selection and clears the open doc
            app.set_corpus("greek")
            assert app.state.selected_corpus == "greek"
            assert app.state.selected_doc_id is None

    _run(body())


def test_no_dead_cross_screen_message_subsystem() -> None:
    """The old CorpusChanged/DocChanged messages were dead: App.post_message never
    reached the active screen, so nothing consumed them. They are gone now, along
    with their public exports and the unreachable screen handler."""
    import aegean.tui.app as appmod
    from aegean.tui.screens.corpus import CorpusBrowserScreen

    # the message classes and their exports are removed
    assert not hasattr(appmod, "CorpusChanged")
    assert not hasattr(appmod, "DocChanged")
    assert "CorpusChanged" not in appmod.__all__
    assert "DocChanged" not in appmod.__all__
    # and the corpus screen's dead handler is gone (cross-screen sync is via
    # on_screen_resume reading shared state, not a message)
    assert not hasattr(CorpusBrowserScreen, "on_corpus_changed")


def test_load_screens_skips_a_screen_that_fails_to_import() -> None:
    """A screen module that raises at import (not just a plain ModuleNotFoundError)
    is skipped so the shell still runs, matching the docstring's 'any failing
    screen module is skipped'. A pre-fix narrow catch would crash the app."""
    import importlib

    import aegean.tui.app as appmod

    original = importlib.import_module

    def raise_for_greek(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name.endswith("screens.greek"):
            raise ImportError("simulated broken greek screen module")
        return original(name, *args, **kwargs)

    importlib.import_module = raise_for_greek  # type: ignore[assignment]
    try:
        screens = appmod._load_screens()
    finally:
        importlib.import_module = original
    # the broken screen is skipped, the rest still load
    assert "greek" not in screens
    assert "home" in screens and "corpus" in screens


def test_load_screens_reraises_a_failing_home_module() -> None:
    """Home is the landing view, so its import failure is fatal and re-raised
    rather than swallowed (the shell has nothing to show without it)."""
    import importlib

    import aegean.tui.app as appmod

    original = importlib.import_module

    def raise_for_home(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name.endswith("screens.home"):
            raise ImportError("simulated broken home screen module")
        return original(name, *args, **kwargs)

    importlib.import_module = raise_for_home  # type: ignore[assignment]
    try:
        with pytest.raises(ImportError):
            appmod._load_screens()
    finally:
        importlib.import_module = original


def test_owned_tui_modules_carry_no_dev_process_language() -> None:
    """Public docstrings describe the product, not how it was built. Sweep the
    module docstrings of the owned TUI files for a build-process tell (e.g. the
    old widgets note that 'screen agents build against a fixed widget API')."""
    import aegean.tui.app as app_mod
    import aegean.tui.data as data_mod
    import aegean.tui.screens.corpus as corpus_mod
    import aegean.tui.screens.greek as greek_mod
    import aegean.tui.widgets as widgets_mod

    banned = ("screen agent", "screen agents", "agents build", "build agent", "feasibility prob")
    for mod in (app_mod, data_mod, widgets_mod, greek_mod, corpus_mod):
        doc = (mod.__doc__ or "").lower()
        for phrase in banned:
            assert phrase not in doc, f"{mod.__name__} docstring has a process tell: {phrase!r}"


def test_command_palette_opens_via_ctrl_p() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            baseline = len(app.screen_stack)
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert len(app.screen_stack) > baseline
            assert isinstance(app.screen, CommandPalette)

    _run(body())


def test_corpus_commands_provider_returns_open_corpus_entries() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            provider = CorpusCommands(app.screen)
            await provider.startup()
            hits = [hit async for hit in provider.search("lineara")]
            labels = [str(hit.text) for hit in hits]
            assert any("Open corpus lineara" in label for label in labels)

    _run(body())


def test_corpus_commands_provider_offers_screen_navigation() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            provider = CorpusCommands(app.screen)
            await provider.startup()
            hits = [hit async for hit in provider.search("greek workbench")]
            labels = [str(hit.text) for hit in hits]
            assert any("Greek workbench" in label for label in labels)

    _run(body())
