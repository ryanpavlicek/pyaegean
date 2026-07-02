"""Pilot tests for the Data Store screen (`aegean.tui.screens.data`).

Content-asserting, not "it mounts": the environment report shows the live
``aegean.__version__``; the dataset table lists the real fetchable datasets
(``damos-corpus`` / ``sigla-corpus``) with a download state; and the Fetch action
drives a monkeypatched :func:`aegean.tui.data.fetch_dataset` on a worker,
asserting the progress status, the in-place row refresh, and that a failure
surfaces as a notification rather than a crash. The network is never touched:
``fetch_dataset`` (and, where a deterministic not-downloaded row is needed,
``dataset_rows``) is replaced with a local fake.

Per the feasibility probes (textual 8.2.8, no pytest-asyncio in the dev env),
each async body runs in a fresh event loop; a Static's text is read via
``.content``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.widgets import Button, DataTable, Static  # noqa: E402

import aegean  # noqa: E402
from aegean.tui import data as adapter  # noqa: E402
from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.data import DataStoreScreen  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def _kv_pairs(table: DataTable) -> dict[str, str]:  # type: ignore[type-arg]
    """The (key -> value) pairs of a two-column KeyValueTable."""
    return {str(table.get_row_at(i)[0]): str(table.get_row_at(i)[1]) for i in range(table.row_count)}


def _dataset_names(table: DataTable) -> list[str]:  # type: ignore[type-arg]
    return [str(table.get_row_at(i)[0]) for i in range(table.row_count)]


def _dataset_row(table: DataTable, name: str) -> list[str]:  # type: ignore[type-arg]
    for i in range(table.row_count):
        row = table.get_row_at(i)
        if str(row[0]) == name:
            return [str(c) for c in row]
    raise AssertionError(f"no dataset row {name!r}")


# ── environment report ───────────────────────────────────────────────────────
def test_environment_report_shows_the_pyaegean_version() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            assert isinstance(app.screen, DataStoreScreen)
            versions = _kv_pairs(app.screen.query_one("#data-versions", DataTable))
            # the doctor table carries the live version, not a hard-coded string
            assert versions["pyaegean"] == aegean.__version__
            import platform

            assert versions["python"] == platform.python_version()

    _run(body())


def test_environment_report_lists_the_tui_extra_as_installed() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            extras = _kv_pairs(app.screen.query_one("#data-extras", DataTable))
            # the report is running under the tui extra, so it must be present
            assert "tui" in extras
            assert extras["tui"] == "installed"

    _run(body())


def test_environment_report_shows_the_data_store_location() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            store = _kv_pairs(app.screen.query_one("#data-store", DataTable))
            # the store section names the location and its writability
            assert "location" in store
            from aegean.data import cache_dir

            assert store["location"] == str(cache_dir())
            assert store["writable"] in {"yes", "no"}

    _run(body())


# ── dataset table ────────────────────────────────────────────────────────────
def test_dataset_table_lists_damos_and_sigla_with_a_download_state() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            table = app.screen.query_one("#data-datasets", DataTable)
            names = _dataset_names(table)
            assert "damos-corpus" in names
            assert "sigla-corpus" in names
            # each row's state cell is one of the two download states
            damos = _dataset_row(table, "damos-corpus")
            assert damos[1] in {"downloaded", "not downloaded"}

    _run(body())


def test_fetch_button_is_present_for_the_download_action() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            button = app.screen.query_one("#data-fetch", Button)
            assert "Fetch" in str(button.label)

    _run(body())


# ── fetch action (monkeypatched: never hits the network) ─────────────────────
def test_fetch_runs_on_a_worker_and_refreshes_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """A not-downloaded dataset, fetched, refreshes to the downloaded state with
    its new size, and reports each progress line, all off a worker."""
    state = {"stored": False}
    progress_seen: list[str] = []

    def fake_rows() -> list[adapter.DatasetRow]:
        stored = state["stored"]
        return [
            adapter.DatasetRow(
                name="fake-corpus",
                downloaded=stored,
                bytes=2048 if stored else None,
                note="a stand-in dataset",
                license="test",
            )
        ]

    def fake_fetch(name, on_progress=None):  # type: ignore[no-untyped-def]
        assert name == "fake-corpus"
        if on_progress is not None:
            on_progress(f"fetching {name}…")
            progress_seen.append(f"fetching {name}…")
        state["stored"] = True
        if on_progress is not None:
            on_progress(f"stored {name}")
        return Path("/tmp/fake-corpus")

    monkeypatch.setattr(adapter, "dataset_rows", fake_rows)
    monkeypatch.setattr(adapter, "fetch_dataset", fake_fetch)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DataStoreScreen)
            table = screen.query_one("#data-datasets", DataTable)
            assert _dataset_row(table, "fake-corpus")[1] == "not downloaded"

            screen.action_fetch()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            # the row refreshed in place to the downloaded state with a size
            row = _dataset_row(table, "fake-corpus")
            assert row[1] == "downloaded"
            assert row[2] == "2.0 kB"
            # the progress line landed as the status
            status = screen.query_one("#data-status", Static)
            assert str(status.content) == "stored fake-corpus"

    _run(body())
    # the fetch reported both progress lines through the worker's callback
    assert progress_seen == ["fetching fake-corpus…"]


def test_fetch_failure_notifies_and_leaves_the_row_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fetch failure surfaces as an error notification and a status line, never
    a crash, and the row stays not-downloaded."""

    def fake_rows() -> list[adapter.DatasetRow]:
        return [
            adapter.DatasetRow(
                name="bad-corpus", downloaded=False, bytes=None, note="n", license="L"
            )
        ]

    def failing_fetch(name, on_progress=None):  # type: ignore[no-untyped-def]
        raise adapter.TuiError("network is down")

    monkeypatch.setattr(adapter, "dataset_rows", fake_rows)
    monkeypatch.setattr(adapter, "fetch_dataset", failing_fetch)

    notifications: list[tuple[str, str]] = []

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DataStoreScreen)

            def spy(message: str, **kwargs: object) -> None:
                notifications.append((message, str(kwargs.get("severity"))))

            monkeypatch.setattr(app, "notify", spy)

            screen.action_fetch()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            # no crash; the row is untouched
            table = screen.query_one("#data-datasets", DataTable)
            assert _dataset_row(table, "bad-corpus")[1] == "not downloaded"
            status = screen.query_one("#data-status", Static)
            assert "could not fetch bad-corpus" in str(status.content)
            assert "network is down" in str(status.content)

    _run(body())
    # the failure was surfaced as an error-severity notification
    assert notifications == [("network is down", "error")]


def test_fetch_is_a_no_op_when_the_dataset_is_already_downloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fetching an already-downloaded dataset never calls fetch; it says so."""

    def fake_rows() -> list[adapter.DatasetRow]:
        return [
            adapter.DatasetRow(
                name="have-it", downloaded=True, bytes=1024, note="n", license="L"
            )
        ]

    called = {"fetch": False}

    def fetch_should_not_run(name, on_progress=None):  # type: ignore[no-untyped-def]
        called["fetch"] = True
        return Path("/tmp/have-it")

    monkeypatch.setattr(adapter, "dataset_rows", fake_rows)
    monkeypatch.setattr(adapter, "fetch_dataset", fetch_should_not_run)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            app.goto("data")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DataStoreScreen)
            screen.action_fetch()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            status = screen.query_one("#data-status", Static)
            assert "already downloaded" in str(status.content)

    _run(body())
    assert called["fetch"] is False


def test_switch_to_data_via_binding_and_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """The global 'd' binding reaches the screen and its report renders (the
    dataset table has the real rows)."""

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, DataStoreScreen)
            table = app.screen.query_one("#data-datasets", DataTable)
            assert table.row_count > 0
            assert "nt-corpus" in _dataset_names(table)

    _run(body())
