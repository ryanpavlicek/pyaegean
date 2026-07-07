"""Pilot tests for the Works library screen (`aegean.tui.screens.works`).

The catalogue search filters the table; a fetch runs on a worker (with a
monkeypatched adapter so the network is never touched) and flips the row to
downloaded; opening a fetched work sets the shared selection and lands on the
corpus browser. The command palette gains the works-library and open-work
entries. Per the harness rules: fresh event loop per body, ``.content`` for a
Static, ``wait_for_complete`` for the worker.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.widgets import DataTable, Input, Static  # noqa: E402

from aegean.tui import data as adapter  # noqa: E402
from aegean.tui.app import AegeanApp, CorpusCommands  # noqa: E402
from aegean.tui.screens.corpus import CorpusBrowserScreen  # noqa: E402
from aegean.tui.screens.works import WorksScreen  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def _row(w_id: str, *, fetched: bool = False) -> adapter.WorkRow:
    return adapter.WorkRow(
        id=w_id, author="Homer", title="Iliad", greek_title="Ἰλιάς",
        source="perseus", fetched=fetched, bytes=(2048 if fetched else None),
    )


def test_search_filters_the_catalogue_table(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_catalog(query=None, *, author=None, title=None, source=None):  # type: ignore[no-untyped-def]
        rows = [_row("tlg0012.tlg001"), _row("tlg0012.tlg002")]
        if query and "iliad" in query.lower():
            return rows[:1]
        return rows

    monkeypatch.setattr(adapter, "catalog_rows", fake_catalog)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("works")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WorksScreen)
            screen.query_one("#works-search", Input).value = "iliad"
            await pilot.pause()
            table = screen.query_one("#works-table", DataTable)
            assert table.row_count == 1
            assert str(table.get_row_at(0)[0]) == "tlg0012.tlg001"

    _run(body())


def test_fetch_runs_on_a_worker_and_marks_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {"stored": False}

    def fake_catalog(query=None, *, author=None, title=None, source=None):  # type: ignore[no-untyped-def]
        return [_row("tlg0012.tlg001", fetched=state["stored"])]

    def fake_fetch(work_id, on_progress=None, abort=None):  # type: ignore[no-untyped-def]
        assert work_id == "tlg0012.tlg001"
        state["stored"] = True
        if on_progress is not None:
            on_progress(f"stored {work_id}")
        return Path("/tmp/tlg0012.tlg001.xml")

    monkeypatch.setattr(adapter, "catalog_rows", fake_catalog)
    monkeypatch.setattr(adapter, "fetch_work", fake_fetch)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("works")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WorksScreen)
            screen.query_one("#works-search", Input).value = "homer"
            await pilot.pause()
            screen.action_fetch()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            table = screen.query_one("#works-table", DataTable)
            assert str(table.get_row_at(0)[4]) == "downloaded"
            assert "stored" in str(screen.query_one("#works-status", Static).content)

    _run(body())


def test_a_failing_fetch_notifies_and_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    notes: list[str] = []

    def fake_catalog(query=None, *, author=None, title=None, source=None):  # type: ignore[no-untyped-def]
        return [_row("tlg0012.tlg001")]

    def boom(work_id, on_progress=None, abort=None):  # type: ignore[no-untyped-def]
        raise adapter.TuiError("network down")

    monkeypatch.setattr(adapter, "catalog_rows", fake_catalog)
    monkeypatch.setattr(adapter, "fetch_work", boom)

    async def body() -> None:
        app = AegeanApp()
        app.notify = lambda *a, **k: notes.append(str(a[0]) if a else "")  # type: ignore[method-assign]
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("works")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WorksScreen)
            screen.query_one("#works-search", Input).value = "homer"
            await pilot.pause()
            screen.action_fetch()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, WorksScreen)  # still alive, no crash
            assert "network down" in str(screen.query_one("#works-status", Static).content)

    _run(body())
    assert any("network down" in n for n in notes)


def test_open_a_fetched_work_lands_on_the_corpus_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_catalog(query=None, *, author=None, title=None, source=None):  # type: ignore[no-untyped-def]
        return [_row("tlg0012.tlg001", fetched=True)]

    def fake_spec(spec):  # type: ignore[no-untyped-def]
        import aegean

        return aegean.load("lineara")  # a small real corpus stands in for the work

    monkeypatch.setattr(adapter, "catalog_rows", fake_catalog)
    monkeypatch.setattr(adapter, "read_corpus_spec", fake_spec)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("works")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WorksScreen)
            screen.query_one("#works-search", Input).value = "homer"
            await pilot.pause()
            screen.action_open_work()
            await pilot.pause()
            assert app.state.selected_corpus == "tlg0012.tlg001"
            assert isinstance(app.screen, CorpusBrowserScreen)

    _run(body())


def test_palette_offers_the_works_library_and_open_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "fetched_work_ids", lambda: ["tlg0012.tlg001"])

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            provider = CorpusCommands(app.screen)
            await provider.startup()
            labels = [str(hit.text) async for hit in provider.search("work")]
            assert any("Works library" in label for label in labels)
            assert any("Open work tlg0012.tlg001" in label for label in labels)

    _run(body())


def test_enter_on_a_work_opens_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enter (DataTable RowSelected) on a fetched work opens it, the same as the 'o' key."""
    import types

    monkeypatch.setattr(adapter, "catalog_rows",
                        lambda *a, **k: [_row("tlg0012.tlg001", fetched=True)])

    def fake_spec(spec):  # type: ignore[no-untyped-def]
        import aegean

        return aegean.load("lineara")

    monkeypatch.setattr(adapter, "read_corpus_spec", fake_spec)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("works")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WorksScreen)
            screen.query_one("#works-search", Input).value = "homer"
            await pilot.pause()
            screen.on_data_table_row_selected(types.SimpleNamespace())  # Enter delegates to open
            await pilot.pause()
            assert app.state.selected_corpus == "tlg0012.tlg001"

    _run(body())
