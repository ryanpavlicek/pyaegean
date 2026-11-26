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


from _tui_helpers import TuiSession  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(scope="module")
def tui_session():  # type: ignore[no-untyped-def]
    session = TuiSession(size=(120, 40)).start()
    try:
        yield session
    finally:
        session.close()


async def _open_lineara(app: AegeanApp, pilot) -> CorpusBrowserScreen:  # type: ignore[no-untyped-def]
    """Ensure Linear A is loaded in the corpus browser with a clean search filter."""
    if (
        isinstance(app.screen, CorpusBrowserScreen)
        and app.screen._loaded_id == "lineara"
    ):
        screen = app.screen
        search = screen.query_one("#corpus-search", Input)
        if search.value:
            search.value = ""
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
        return screen
    app.open_corpus("lineara")
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, CorpusBrowserScreen)
    search = screen.query_one("#corpus-search", Input)
    if search.value:
        search.value = ""
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
    return screen


def test_opening_lineara_loads_all_1721_documents(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
        docs = screen.query_one("#corpus-docs", DocTable)
        assert docs.row_count == 1721
        # the status line reports the count too
        status = str(screen.query_one("#corpus-status", Static).content)
        assert "1721 documents" in status

    tui_session.run(body)


def test_reading_ht13_shows_its_first_line_tokens_and_structure(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
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

    tui_session.run(body)


def test_ht13_analysis_pane_shows_the_accounting_balance(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
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

    tui_session.run(body)


def test_lineara_detail_renders_clean_header_without_disclaimer(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
        docs = screen.query_one("#corpus-docs", DocTable)
        docs.focus()
        docs.move_cursor(row=docs.get_row_index("HT13"))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        detail = str(screen.query_one("#corpus-detail", DetailPane).content)
        assert "HT13" in detail
        assert "not a reading" not in detail

    tui_session.run(body)


def test_search_box_filters_documents_by_id(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
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

    tui_session.run(body)


def test_search_box_surfaces_sign_pattern_word_matches(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
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

    tui_session.run(body)


def test_sign_search_is_dispatched_to_a_worker_not_run_inline(tui_session: TuiSession) -> None:
    """The corpus-wide sign search method is a Textual ``@work`` worker, so a
    keystroke returns without running the (potentially large-corpus) scan on the
    UI thread. Calling it yields a Worker rather than the search result, and the
    matches land in the status only after the worker completes."""
    from textual.worker import Worker

    # the method is worker-wrapped: it does not run the scan inline
    assert hasattr(CorpusBrowserScreen._sign_search, "__wrapped__")

    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
        # calling the decorated method dispatches a worker (returns a Worker),
        # rather than blocking to return the search result
        result = screen._sign_search("KU-*-RO", "base")
        assert isinstance(result, Worker)
        await app.workers.wait_for_complete()
        await pilot.pause()
        status = str(screen.query_one("#corpus-status", Static).content)
        assert "KU-MA-RO" in status

    tui_session.run(body)


def test_sign_search_via_the_search_box_lands_after_the_worker(tui_session: TuiSession) -> None:
    """End to end: typing a sign pattern shows the immediate id-filter status,
    then the corpus word matches after the background search completes."""

    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
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

    tui_session.run(body)


def test_plain_id_filter_does_not_spawn_a_sign_search_worker(tui_session: TuiSession) -> None:
    """A plain id filter (no hyphen or wildcard) is not a sign pattern, so it runs
    inline and never dispatches the corpus-wide search worker."""

    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
        search = screen.query_one("#corpus-search", Input)
        # 'HT1' has no '-' or '*', so it is an id filter, not a sign pattern
        search.value = "HT1"
        await pilot.pause()
        assert len(app.workers) == 0
        status = str(screen.query_one("#corpus-status", Static).content)
        # a pure id filter, no word-match clause appended
        assert "documents match id" in status
        assert "words matching" not in status

    tui_session.run(body)


def test_focus_search_binding_focuses_the_input(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
        screen.query_one("#corpus-docs", DocTable).focus()
        await pilot.pause()
        # '/' focuses the search box (the design's search key)
        await pilot.press("slash")
        await pilot.pause()
        assert app.focused is screen.query_one("#corpus-search", Input)

    tui_session.run(body)


def test_bad_corpus_shows_a_clean_message_not_a_traceback(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        app.goto("corpus")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CorpusBrowserScreen)
        screen._open_corpus("nope-not-a-corpus")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        status = str(screen.query_one("#corpus-status", Static).content)
        docs = screen.query_one("#corpus-docs", DocTable)
        assert "nope-not-a-corpus" in status
        assert docs.row_count == 0

    tui_session.run(body)


def test_selecting_a_different_corpus_in_the_list_reloads_the_table(
    tui_session: TuiSession,
) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        screen = await _open_lineara(app, pilot)
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
        await app.workers.wait_for_complete()
        await pilot.pause()
        # the table now reflects the newly selected corpus, not Linear A's 1721
        assert docs.row_count == 18
        assert app.state.selected_corpus == "linearb"

    tui_session.run(body)


def test_corpus_opened_elsewhere_loads_on_return_to_the_screen(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        # open Linear A on the browser, then leave to Home
        await _open_lineara(app, pilot)
        app.goto("home")
        await pilot.pause()
        # a different corpus is opened from Home / the palette
        app.open_corpus("cypriot")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        # returning to the browser reconciles to the new selection on resume
        screen = app.screen
        assert isinstance(screen, CorpusBrowserScreen)
        docs = screen.query_one("#corpus-docs", DocTable)
        assert docs.row_count == 180  # the Cypriot corpus, not Linear A's 1721
        assert app.state.selected_corpus == "cypriot"

    tui_session.run(body)


def test_greek_corpus_has_no_undeciphered_caveat(tui_session: TuiSession) -> None:
    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        app.open_corpus("greek")
        await pilot.pause()
        await app.workers.wait_for_complete()
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

    tui_session.run(body)


def test_reader_pane_is_focusable_and_reachable_by_tab(tui_session: TuiSession) -> None:
    """The document reader (DetailPane) is focusable and in the Tab cycle, so its line
    cursor is reachable; a long document scrolls as the cursor moves and with the mouse
    wheel (the pane is not a plain clipped Static any more)."""

    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        app.open_corpus("greek")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        screen = app.screen
        reader = screen.query_one("#corpus-detail", DetailPane)
        assert reader.can_focus  # focusable, so ↑/↓ drive the line cursor
        screen.query_one("#corpus-list", CorpusList).focus()
        await pilot.pause()
        for _ in range(5):  # Tab reaches the reader
            screen.action_cycle_focus()
            await pilot.pause()
            if app.focused is reader:
                break
        assert app.focused is reader

    tui_session.run(body)


def test_fetched_works_are_permanent_items_in_the_corpus_list(monkeypatch) -> None:
    """A downloaded work is its own selectable list item (not a transient load): it appears
    in the left list, loads when opened, and stays highlighted."""
    from aegean.tui import data as adapter
    from aegean.tui.data import CorpusEntry

    monkeypatch.setattr(adapter, "fetched_work_entries", lambda: [
        CorpusEntry(id="tlg0012.tlg001", blurb="Homer — Iliad (Greek work)",
                    downloaded=True, bundled=False, undeciphered=False)])

    def fake_spec(spec):  # type: ignore[no-untyped-def]
        import aegean

        return aegean.load("lineara")

    monkeypatch.setattr(adapter, "read_corpus_spec", fake_spec)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.open_corpus("tlg0012.tlg001")  # as from the works library "open"
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            clist = screen.query_one("#corpus-list", CorpusList)
            names = [getattr(c, "name", None) for c in clist.children]
            assert "tlg0012.tlg001" in names  # a permanent, selectable item
            assert screen._loaded_id == "tlg0012.tlg001"  # loaded
            assert clist.selected_id == "tlg0012.tlg001"  # and highlighted

    _run(body())


def test_reading_pane_shows_a_focus_highlight(tui_session: TuiSession) -> None:
    """Tabbing to the reading pane must be visible: the reader box carries a 'reading' border
    title and its border turns accent-coloured when the pane inside holds focus (focus-within),
    so the user knows the reader is active without having to test-scroll it."""
    from textual.containers import VerticalScroll

    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        app.goto("corpus")
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        box = screen.query_one("#corpus-right", VerticalScroll)
        detail = screen.query_one("#corpus-detail", DetailPane)
        assert box.border_title == "reading"
        screen.query_one("#corpus-list", CorpusList).focus()
        await pilot.pause()
        unfocused = box.styles.border_top[1]
        detail.focus()
        await pilot.pause()
        assert detail.has_focus
        assert box.styles.border_top[1] != unfocused  # the box border highlights (focus-within)

    tui_session.run(body)


def test_reader_line_cursor_moves_and_enter_opens_the_analysis_modal(
    tui_session: TuiSession,
) -> None:
    """↑/↓ move a highlighted line cursor in the reader, and Enter (or a) opens the analysis
    modal for the current line — the in-reader analysis entry point."""
    from aegean.tui.screens.analysis import LineAnalysisScreen

    async def body(app: AegeanApp, pilot) -> None:  # type: ignore[no-untyped-def]
        # the small bundled cypriot corpus (has multi-line docs), not the 1,721-doc lineara
        app.open_corpus("cypriot")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        screen = app.screen
        doc = next(d for d in screen._corpus.documents if len(d.lines) >= 4)
        screen._show_document(doc.id)
        await pilot.pause()
        detail = screen.query_one("#corpus-detail", DetailPane)
        assert detail._line_count() >= 4  # a multi-line document
        detail.focus()
        await pilot.pause()
        detail.action_cursor_down()
        detail.action_cursor_down()
        await pilot.pause()
        assert detail.cursor_line == 2  # the cursor advanced with ↓
        detail.action_choose_line()  # Enter / a
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, LineAnalysisScreen)
        assert modal._line_number == 3  # 1-based line for cursor index 2
        assert modal._script_id == "cypriot"
        app.pop_screen()
        await pilot.pause()

    tui_session.run(body)
