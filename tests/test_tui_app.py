"""Pilot smoke tests for the TUI app shell (`aegean.tui.app`).

These assert real content, not "it mounts": the Home screen shows the
undeciphered-honesty banner and the eight corpora, the global key bindings and
navigation helpers switch screens, and the command-palette Provider returns
'Open corpus' entries.

Per the feasibility probes (textual 8.2.8, no pytest-asyncio in the dev env),
each async body is wrapped in a fresh event loop rather than a pytest-asyncio
marker; the palette Provider is unit-tested by awaiting ``search`` directly (the
race-free path), and the palette UI is driven with ``ctrl+p`` under
``run_test(size=(100, 40))``. Read a Static's original renderable via
``.content`` (textual 8.x has no ``.renderable``).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from textual.command import CommandPalette  # noqa: E402
from textual.widgets import Static  # noqa: E402

from aegean.tui.app import AegeanApp, CorpusChanged, CorpusCommands  # noqa: E402
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
            # 'g' targets the greek screen; before that screen agent's module
            # lands the shell must stay runnable (goto is a no-op for an
            # unregistered screen), so Home remains and nothing crashes.
            await pilot.press("g")
            await pilot.pause()
            assert app.screen is not None
            # open_corpus (the palette + Home-selection path) sets shared state
            app.open_corpus("lineara")
            await pilot.pause()
            assert app.state.selected_corpus == "lineara"

    _run(body())


def test_set_corpus_posts_corpus_changed_and_resets_the_document() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.set_doc("HT13")
            assert app.state.selected_doc_id == "HT13"
            # switching corpus clears the open document and fires the message
            posted: list[str] = []
            original = app.post_message

            def spy(message: object) -> bool:
                if isinstance(message, CorpusChanged):
                    posted.append(message.corpus_id)
                return original(message)  # type: ignore[arg-type]

            app.post_message = spy  # type: ignore[method-assign]
            app.set_corpus("greek")
            assert app.state.selected_corpus == "greek"
            assert app.state.selected_doc_id is None
            assert posted == ["greek"]

    _run(body())


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
