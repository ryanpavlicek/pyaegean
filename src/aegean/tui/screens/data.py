"""The Data Store screen: the environment report and the fetchable datasets.

Two read-only reports plus one action, all offline until the user asks for a
download:

1. the environment report, verbatim from :func:`aegean.tui.data.doctor_report`
   (the same :func:`aegean._doctor.build_report` the ``aegean doctor``
   command renders): the Python and pyaegean versions, which optional extras are
   importable, the local data store's location and size, the neural model
   bundles, and the opt-in analysis cache, each as a two-column
   :class:`~aegean.tui.widgets.KeyValueTable`;
2. the dataset table, from :func:`aegean.tui.data.dataset_rows` (the same
   per-dataset state ``aegean data list`` reports): every fetchable dataset, its
   download state, and its on-disk size;
3. a Fetch action for the highlighted not-yet-downloaded dataset, which runs
   :func:`aegean.tui.data.fetch_dataset` on a Textual worker so the UI stays
   live, drives a progress line, refreshes the row on completion, and surfaces
   any failure as a one-line notification (never a crash).

There is no remove action in this first version (a deletion in a TUI is a
footgun; download-only keeps the surface small and safe). This screen is pure
view over the adapter: it imports nothing from the library directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, ProgressBar, Static

from .. import data as adapter
from ..widgets import KeyValueTable

if TYPE_CHECKING:
    from textual.worker import Worker

__all__ = ["DataStoreScreen"]


def _human_size(n: int | None) -> str:
    """A short human size for a byte count (``None`` for an unmeasured one)."""
    if n is None:
        return "-"
    from ...cli._data import _human_size as _hs

    return _hs(int(n))


def _extra_state(extra: dict[str, object]) -> str:
    """A one-line install state for a doctor extras row."""
    if extra["installed"]:
        return "installed"
    missing = extra["missing"]
    modules = extra["modules"]
    assert isinstance(missing, list) and isinstance(modules, list)
    if len(missing) == len(modules):
        return "not installed"
    return f"partial (missing: {', '.join(missing)})"


class DataStoreScreen(Screen[None]):
    """The data store: the offline environment report and the fetchable datasets,
    with a per-dataset download action on a worker."""

    BINDINGS = [
        ("f", "fetch", "Fetch"),
        ("r", "refresh_store", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="data-body"):
            yield Static("environment", id="data-report-title")
            yield KeyValueTable(id="data-versions")
            yield KeyValueTable(id="data-extras")
            yield KeyValueTable(id="data-store")
            yield KeyValueTable(id="data-models")
            yield KeyValueTable(id="data-cache")
            yield Static("datasets", id="data-datasets-title")
            yield DataTable(id="data-datasets")
            with Horizontal(id="data-actions"):
                yield Button("Fetch selected", id="data-fetch", variant="primary")
                yield ProgressBar(id="data-progress", show_eta=False)
            yield Static("", id="data-status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_report()
        self._render_datasets()

    # ── rendering ─────────────────────────────────────────────────────────────
    def _render_report(self) -> None:
        """Populate the five doctor key/value tables from the adapter report."""
        report = adapter.doctor_report()

        versions = report["versions"]
        self.query_one("#data-versions", KeyValueTable).set_pairs(
            "environment",
            "value",
            [
                ("pyaegean", str(versions["pyaegean"])),
                ("python", str(versions["python"])),
                ("platform", str(versions["platform"])),
            ],
        )

        self.query_one("#data-extras", KeyValueTable).set_pairs(
            "optional extra",
            "state",
            [(str(e["extra"]), _extra_state(e)) for e in report["extras"]],
        )

        store = report["data_store"]
        store_pairs: list[tuple[str, str]] = []
        if store["path"] is None:
            store_pairs.append(("location", f"unavailable: {store['error']}"))
        else:
            store_pairs.append(("location", str(store["path"])))
            store_pairs.append(("writable", "yes" if store["writable"] else "no"))
            store_pairs.append(("total size", _human_size(store["total_bytes"])))
            for orphan in store["orphans"]:
                store_pairs.append(
                    (str(orphan["file"]), f"leftover partial download · fix: {orphan['fix']}")
                )
        self.query_one("#data-store", KeyValueTable).set_pairs(
            "data store", "state", store_pairs
        )

        model_pairs: list[tuple[str, str]] = []
        for m in report["models"]:
            if m["downloaded"] is None:
                state = "unknown (data store unavailable)"
            elif m["downloaded"]:
                state = "downloaded"
            else:
                state = f"not downloaded · {m['fetch']}"
            model_pairs.append((str(m["name"]), state))
        self.query_one("#data-models", KeyValueTable).set_pairs(
            "neural model bundle", "state", model_pairs
        )

        cache = report["analysis_cache"]
        if cache["enabled"]:
            entries = int(cache["entries"])
            cache_state = f"on · {entries} entr{'y' if entries == 1 else 'ies'}"
        elif cache["enabled"] is None:
            cache_state = f"unavailable: {cache['error']}"
        else:
            cache_state = "off"
        self.query_one("#data-cache", KeyValueTable).set_pairs(
            "analysis cache", "state", [("analysis cache", cache_state)]
        )

    def _render_datasets(self) -> None:
        """Populate the dataset table (row key = dataset name)."""
        table = self.query_one("#data-datasets", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        # explicit column keys so update_cell(name, "state"/"size", …) resolves
        # against the same keys after a fetch refreshes a row in place
        table.add_column("dataset", key="dataset")
        table.add_column("state", key="state")
        table.add_column("size", key="size")
        table.add_column("license", key="license")
        for row in adapter.dataset_rows():
            state = "downloaded" if row.downloaded else "not downloaded"
            table.add_row(
                row.name,
                state,
                _human_size(row.bytes) if row.downloaded else "-",
                row.license,
                key=row.name,
            )

    def _refresh_dataset_row(self, name: str) -> None:
        """Re-read one dataset's state and update its row in place."""
        table = self.query_one("#data-datasets", DataTable)
        by_name = {r.name: r for r in adapter.dataset_rows()}
        row = by_name.get(name)
        if row is None:
            return
        state = "downloaded" if row.downloaded else "not downloaded"
        table.update_cell(name, "state", state)
        table.update_cell(name, "size", _human_size(row.bytes) if row.downloaded else "-")

    # ── selection ─────────────────────────────────────────────────────────────
    def _selected_dataset(self) -> str | None:
        """The highlighted dataset's name, or ``None`` when nothing is
        highlighted."""
        table = self.query_one("#data-datasets", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key, _col = table.coordinate_to_cell_key(table.cursor_coordinate)
        except Exception:  # no cell under the cursor
            return None
        return None if row_key.value is None else str(row_key.value)

    def _is_downloaded(self, name: str) -> bool:
        return any(r.name == name and r.downloaded for r in adapter.dataset_rows())

    # ── fetch action ──────────────────────────────────────────────────────────
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "data-fetch":
            self.action_fetch()

    def action_refresh_store(self) -> None:
        """Re-read the environment report and dataset table from disk."""
        self._render_report()
        self._render_datasets()
        self._set_status("refreshed")

    def action_fetch(self) -> None:
        """Fetch the highlighted dataset on a worker (a no-op if it is already
        downloaded or nothing is selected)."""
        name = self._selected_dataset()
        if name is None:
            self._set_status("select a dataset to fetch")
            return
        if self._is_downloaded(name):
            self._set_status(f"{name} is already downloaded")
            return
        self._start_progress()
        self._fetch_worker(name)

    @work(thread=True, exclusive=True, group="fetch")
    def _fetch_worker(self, name: str) -> None:
        """Download ``name`` off the UI thread, marshalling every UI touch back
        through :meth:`App.call_from_thread` so the screen stays responsive."""

        def progress(message: str) -> None:
            self.app.call_from_thread(self._set_status, message)

        try:
            adapter.fetch_dataset(name, on_progress=progress)
        except adapter.TuiError as exc:
            self.app.call_from_thread(self._fetch_failed, name, str(exc))
            return
        self.app.call_from_thread(self._fetch_done, name)

    # ── worker callbacks (run on the UI thread) ───────────────────────────────
    def _fetch_done(self, name: str) -> None:
        self._stop_progress(finished=True)
        self._refresh_dataset_row(name)
        self._render_report()  # store size / total changed
        self._set_status(f"stored {name}")

    def _fetch_failed(self, name: str, message: str) -> None:
        self._stop_progress(finished=False)
        self._set_status(f"could not fetch {name}: {message}")
        self.app.notify(message, title=f"fetch {name} failed", severity="error")

    # ── progress + status ─────────────────────────────────────────────────────
    def _start_progress(self) -> None:
        bar = self.query_one("#data-progress", ProgressBar)
        bar.update(total=None)  # indeterminate: the fetch reports no byte progress

    def _stop_progress(self, *, finished: bool) -> None:
        bar = self.query_one("#data-progress", ProgressBar)
        bar.update(total=100, progress=100 if finished else 0)

    def _set_status(self, message: str) -> None:
        self.query_one("#data-status", Static).update(message)

    def on_worker_state_changed(self, event: "Worker.StateChanged") -> None:
        """Nothing to do here for the happy paths (the worker marshals its own
        completion); kept so a cancelled/errored worker cannot leave the progress
        bar spinning."""
        from textual.worker import WorkerState

        if event.worker.group != "fetch":
            return
        if event.state in (WorkerState.CANCELLED, WorkerState.ERROR):
            self._stop_progress(finished=False)
