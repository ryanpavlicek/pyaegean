"""Pilot tests for the Corpus Browser screen (`aegean.tui.screens.corpus`).

These assert real rendered content, never merely that the screen mounts: after
opening Linear A the document table carries all 1,721 rows; reading the known
accounting tablet HT13 shows its first-line token text (KA-U-DE-TA), the
accounting balance (KU-RO stated 130.5 vs computed 131.0), and the
undeciphered-script caveat; and the search box filters the table by id and
surfaces a sign pattern's matching words.

The dev env has no pytest-asyncio (textual 8.2.8), so each async body runs in a
fresh event loop rather than via a pytest-asyncio marker; a Static's rendered
text is read via ``.content`` (textual 8.x has no ``.renderable``). Run with
``PYTHONUTF8=1`` so the Greek/Linear A signs render.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from textual.widgets import Input, Static  # noqa: E402

from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.corpus import CorpusBrowserScreen  # noqa: E402
from aegean.tui.widgets import CorpusList, DetailPane, DocTable  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def _open_lineara(app: AegeanApp) -> CorpusBrowserScreen:
    """Open Linear A in the corpus browser (the real Home/palette entry path)."""
    app.open_corpus("lineara")
    screen = app.screen
    assert isinstance(screen, CorpusBrowserScreen)
    return screen


def test_opening_lineara_loads_all_1721_documents() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            docs = screen.query_one("#corpus-docs", DocTable)
            assert docs.row_count == 1721
            # the status line reports the count too
            status = str(screen.query_one("#corpus-status", Static).content)
            assert "1721 documents" in status

    _run(body())


def test_reading_ht13_shows_its_first_line_tokens_and_structure() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            docs = screen.query_one("#corpus-docs", DocTable)
            docs.focus()
            docs.move_cursor(row=docs.get_row_index("HT13"))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            detail = str(screen.query_one("#corpus-detail", DetailPane).content)
            # the document's first-line first token (the apparatus-aware view)
            assert "KA-U-DE-TA" in detail
            # the heuristic structure category for this accounting tablet
            assert "accounting" in detail
            # selecting a row updates the shared document selection
            assert app.state.selected_doc_id == "HT13"

    _run(body())


def test_ht13_analysis_pane_shows_the_accounting_balance() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            docs = screen.query_one("#corpus-docs", DocTable)
            docs.focus()
            docs.move_cursor(row=docs.get_row_index("HT13"))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            detail = str(screen.query_one("#corpus-detail", DetailPane).content)
            # the shared balance analysis: KU-RO's stated total does not reconcile
            assert "accounting balance" in detail
            assert "KU-RO" in detail
            assert "130.5" in detail  # stated total
            assert "131" in detail  # computed sum
            assert "OFF" in detail  # it does not balance (diff 0.5)

    _run(body())


def test_undeciphered_caveat_shows_for_lineara() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            docs = screen.query_one("#corpus-docs", DocTable)
            docs.focus()
            docs.move_cursor(row=docs.get_row_index("HT13"))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            detail = str(screen.query_one("#corpus-detail", DetailPane).content)
            # the exact honesty copy, at the point the analysis is read
            assert DetailPane.UNDECIPHERED_CAVEAT in detail
            assert "undeciphered" in detail and "exploratory" in detail

    _run(body())


def test_search_box_filters_documents_by_id() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            docs = screen.query_one("#corpus-docs", DocTable)
            search = screen.query_one("#corpus-search", Input)
            # a narrow id filter reduces the table but keeps the exact match
            search.value = "HT13"
            await pilot.pause()
            assert 0 < docs.row_count < 1721
            assert docs.is_valid_row_index(docs.get_row_index("HT13"))
            # clearing the box restores the full corpus
            search.value = ""
            await pilot.pause()
            assert docs.row_count == 1721

    _run(body())


def test_search_box_surfaces_sign_pattern_word_matches() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            search = screen.query_one("#corpus-search", Input)
            # a wildcard sign pattern runs the corpus-wide word search and shows
            # the matches in the status line (KU-MA-RO is the one KU-*-RO word).
            # The search runs on a background worker so the UI never blocks, so we
            # wait for it to finish before reading the status.
            search.value = "KU-*-RO"
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            status = str(screen.query_one("#corpus-status", Static).content)
            assert "KU-MA-RO" in status

    _run(body())


def test_sign_search_is_dispatched_to_a_worker_not_run_inline() -> None:
    """The corpus-wide sign search method is a Textual ``@work`` worker, so a
    keystroke returns without running the (potentially large-corpus) scan on the
    UI thread. Calling it yields a Worker rather than the search result, and the
    matches land in the status only after the worker completes."""
    from textual.worker import Worker

    # the method is worker-wrapped: it does not run the scan inline
    assert hasattr(CorpusBrowserScreen._sign_search, "__wrapped__")

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            # calling the decorated method dispatches a worker (returns a Worker),
            # rather than blocking to return the search result
            result = screen._sign_search("KU-*-RO", "base")
            assert isinstance(result, Worker)
            await app.workers.wait_for_complete()
            await pilot.pause()
            status = str(screen.query_one("#corpus-status", Static).content)
            assert "KU-MA-RO" in status

    _run(body())


def test_sign_search_via_the_search_box_lands_after_the_worker() -> None:
    """End to end: typing a sign pattern shows the immediate id-filter status,
    then the corpus word matches after the background search completes."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            search = screen.query_one("#corpus-search", Input)
            search.value = "KU-*-RO"
            await pilot.pause()
            # the immediate status carries the id-filter line
            interim = str(screen.query_one("#corpus-status", Static).content)
            assert "KU-*-RO" in interim
            # after the worker finishes the word matches are appended
            await app.workers.wait_for_complete()
            await pilot.pause()
            final = str(screen.query_one("#corpus-status", Static).content)
            assert "KU-MA-RO" in final

    _run(body())


def test_plain_id_filter_does_not_spawn_a_sign_search_worker() -> None:
    """A plain id filter (no hyphen or wildcard) is not a sign pattern, so it runs
    inline and never dispatches the corpus-wide search worker."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            search = screen.query_one("#corpus-search", Input)
            # 'HT1' has no '-' or '*', so it is an id filter, not a sign pattern
            search.value = "HT1"
            await pilot.pause()
            assert len(app.workers) == 0
            status = str(screen.query_one("#corpus-status", Static).content)
            # a pure id filter, no word-match clause appended
            assert "documents match id" in status
            assert "words matching" not in status

    _run(body())


def test_focus_search_binding_focuses_the_input() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            # '/' focuses the search box (the design's search key)
            await pilot.press("slash")
            await pilot.pause()
            assert app.focused is screen.query_one("#corpus-search", Input)

    _run(body())


def test_bad_corpus_shows_a_clean_message_not_a_traceback() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CorpusBrowserScreen)
            screen._open_corpus("nope-not-a-corpus")
            await pilot.pause()
            status = str(screen.query_one("#corpus-status", Static).content)
            docs = screen.query_one("#corpus-docs", DocTable)
            assert "nope-not-a-corpus" in status
            assert docs.row_count == 0

    _run(body())


def test_selecting_a_different_corpus_in_the_list_reloads_the_table() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _open_lineara(app)
            await pilot.pause()
            docs = screen.query_one("#corpus-docs", DocTable)
            assert docs.row_count == 1721
            # highlight Linear B (a small bundled corpus) in the list and pick it
            corpus_list = screen.query_one("#corpus-list", CorpusList)
            corpus_list.focus()
            corpus_list.index = 1
            await pilot.pause()
            assert corpus_list.selected_id == "linearb"
            await pilot.press("enter")
            await pilot.pause()
            # the table now reflects the newly selected corpus, not Linear A's 1721
            assert docs.row_count == 18
            assert app.state.selected_corpus == "linearb"

    _run(body())


def test_corpus_opened_elsewhere_loads_on_return_to_the_screen() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # open Linear A on the browser, then leave to Home
            _open_lineara(app)
            await pilot.pause()
            app.goto("home")
            await pilot.pause()
            # a different corpus is opened from Home / the palette
            app.open_corpus("cypriot")
            await pilot.pause()
            # returning to the browser reconciles to the new selection on resume
            screen = app.screen
            assert isinstance(screen, CorpusBrowserScreen)
            docs = screen.query_one("#corpus-docs", DocTable)
            assert docs.row_count == 180  # the Cypriot corpus, not Linear A's 1721
            assert app.state.selected_corpus == "cypriot"

    _run(body())


def test_greek_corpus_has_no_undeciphered_caveat() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.open_corpus("greek")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CorpusBrowserScreen)
            docs = screen.query_one("#corpus-docs", DocTable)
            assert docs.row_count > 0
            docs.focus()
            docs.move_cursor(row=0)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            detail = str(screen.query_one("#corpus-detail", DetailPane).content)
            # a deciphered corpus carries no exploratory caveat
            assert "undeciphered" not in detail

    _run(body())


if __name__ == "__main__":  # a convenience runner outside pytest
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
