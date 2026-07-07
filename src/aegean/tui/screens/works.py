"""The Works library screen: browse the ~1,800-work Greek catalogue, fetch, and open.

The corpus browser (``c``) reads corpora and fetched works; this screen is where a
work *enters* the cache. It searches the bundled catalogue (case-insensitive, by
author or title), shows which works are already downloaded, and fetches one work —
or every work by an author — on a Textual worker (the same download pattern as the
data store), then opens a fetched work in the corpus browser. Pure view over the
adapter; imports nothing from the library directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, ProgressBar, Static

from .. import data as adapter

if TYPE_CHECKING:
    from textual.worker import Worker

__all__ = ["WorksScreen"]

_RENDER_CAP = 200  # the catalogue is ~1,800 works; render a slice and note the rest


class WorksScreen(Screen[None]):
    """Search the Greek work catalogue, fetch works, and open a fetched one."""

    BINDINGS = [
        ("slash", "focus_search", "Search"),
        ("f", "fetch", "Fetch"),
        ("a", "fetch_author", "Fetch author"),
        ("o", "open_work", "Open"),
        ("r", "refresh", "Refresh"),
    ]

    # The body fills the space between the Header and the Footer (height: 1fr). Without it the
    # 1fr table over-expands past the bottom of the screen and pushes the action buttons off
    # screen, under and below the Footer.
    DEFAULT_CSS = """
    #works-body { height: 1fr; }
    #works-search { margin: 0 1; }
    #works-table { height: 1fr; }
    #works-actions { height: auto; }
    #works-status { color: $text-muted; padding: 0 1; }
    """

    _fetching: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="works-body"):
            yield Input(placeholder="author or title, e.g. plato / homer / Ἰλιάς", id="works-search")
            yield Static("", id="works-status")
            yield DataTable(id="works-table")
            with Horizontal(id="works-actions"):
                yield Button("Fetch selected", id="works-fetch", variant="primary")
                yield Button("Fetch all by author", id="works-fetch-author")
                yield Button("Open", id="works-open")
                yield ProgressBar(id="works-progress", show_eta=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#works-table", DataTable)
        table.cursor_type = "row"
        table.add_column("id", key="id")
        table.add_column("author", key="author")
        table.add_column("title", key="title")
        table.add_column("source", key="source")
        table.add_column("state", key="state")
        self._populate("")  # start on the downloaded works (the user's library)

    def on_screen_resume(self) -> None:
        # a fetch may have happened elsewhere; re-read state for the current query
        self._populate(self.query_one("#works-search", Input).value)

    # ── rendering ─────────────────────────────────────────────────────────────
    def _rows_for(self, query: str) -> list["adapter.WorkRow"]:
        if query.strip():
            return adapter.catalog_rows(query=query)
        return [r for r in adapter.catalog_rows() if r.fetched]  # empty query: the library

    def _populate(self, query: str) -> None:
        rows = self._rows_for(query)
        table = self.query_one("#works-table", DataTable)
        table.clear()
        for r in rows[:_RENDER_CAP]:
            table.add_row(r.id, r.author, r.title, r.source,
                          "downloaded" if r.fetched else "-", key=r.id)
        if not query.strip():
            self._set_status(
                f"{len(rows)} downloaded — type to search the ~1,800-work catalogue"
                if rows else "no works downloaded yet — type an author or title to search"
            )
        elif len(rows) > _RENDER_CAP:
            self._set_status(f"{len(rows)} matches; showing {_RENDER_CAP} — narrow your search")
        else:
            self._set_status(f"{len(rows)} match{'' if len(rows) == 1 else 'es'}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "works-search":
            self._populate(event.value)

    def _refresh_row(self, work_id: str) -> None:
        by_id = {r.id: r for r in adapter.catalog_rows(query=work_id)}
        row = by_id.get(work_id)
        if row is not None and row.fetched:
            try:
                self.query_one("#works-table", DataTable).update_cell(work_id, "state", "downloaded")
            except Exception:  # the row may not be in the current view
                pass

    # ── selection ─────────────────────────────────────────────────────────────
    def _selected(self) -> "adapter.WorkRow | None":
        table = self.query_one("#works-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        except Exception:
            return None
        if row_key.value is None:
            return None
        matches = [r for r in adapter.catalog_rows(query=str(row_key.value))
                   if r.id == str(row_key.value)]
        return matches[0] if matches else None

    # ── actions ───────────────────────────────────────────────────────────────
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "works-fetch":
            self.action_fetch()
        elif event.button.id == "works-fetch-author":
            self.action_fetch_author()
        elif event.button.id == "works-open":
            self.action_open_work()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on a highlighted work opens it — the same as the 'o' key (Enter is not
        advertised as a separate binding, it just does the natural thing)."""
        self.action_open_work()

    def action_focus_search(self) -> None:
        self.query_one("#works-search", Input).focus()

    def action_refresh(self) -> None:
        self._populate(self.query_one("#works-search", Input).value)

    def action_open_work(self) -> None:
        row = self._selected()
        if row is None:
            self._set_status("select a work to open")
            return
        if not row.fetched:
            self._set_status(f"{row.id} is not downloaded — fetch it first (f)")
            return
        self.app.open_corpus(row.id)  # type: ignore[attr-defined]  # loads via read_corpus_spec

    def action_fetch(self) -> None:
        row = self._selected()
        if row is None:
            self._set_status("select a work to fetch")
            return
        if row.fetched:
            self._set_status(f"{row.id} is already downloaded — open it (o)")
            return
        if self._fetching is not None:
            self._set_status(f"already fetching {self._fetching}")
            return
        self._fetching = row.id
        self._start_progress()
        self._fetch_worker(row.id)

    def action_fetch_author(self) -> None:
        row = self._selected()
        if row is None or not row.author:
            self._set_status("select a work whose author to fetch")
            return
        if self._fetching is not None:
            self._set_status(f"already fetching {self._fetching}")
            return
        self._fetching = f"all by {row.author}"
        self._start_progress()
        self._fetch_author_worker(row.author)

    # ── workers ───────────────────────────────────────────────────────────────
    @work(thread=True, exclusive=True, group="fetch")
    def _fetch_worker(self, work_id: str) -> None:
        from textual.worker import get_current_worker

        worker = get_current_worker()

        def progress(message: str) -> None:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._set_status, message)

        try:
            adapter.fetch_work(work_id, on_progress=progress, abort=lambda: worker.is_cancelled)
        except adapter.FetchCanceled:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._fetch_failed, work_id, "canceled")
            return
        except adapter.TuiError as exc:
            self.app.call_from_thread(self._fetch_failed, work_id, str(exc))
            return
        finally:
            self._fetching = None
        self.app.call_from_thread(self._fetch_done, work_id)

    @work(thread=True, exclusive=True, group="fetch")
    def _fetch_author_worker(self, author: str) -> None:
        from textual.worker import get_current_worker

        worker = get_current_worker()

        def progress(message: str) -> None:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._set_status, message)

        try:
            done = adapter.fetch_author_works(
                author, on_progress=progress, abort=lambda: worker.is_cancelled
            )
        except adapter.FetchCanceled:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._fetch_failed, author, "canceled")
            return
        except adapter.TuiError as exc:
            self.app.call_from_thread(self._fetch_failed, author, str(exc))
            return
        finally:
            self._fetching = None
        self.app.call_from_thread(self._fetch_author_done, author, len(done))

    # ── worker callbacks (UI thread) ──────────────────────────────────────────
    def _fetch_done(self, work_id: str) -> None:
        self._stop_progress(finished=True)
        self._refresh_row(work_id)
        self._set_status(f"stored {work_id} — open it (o)")

    def _fetch_author_done(self, author: str, count: int) -> None:
        self._stop_progress(finished=True)
        self._populate(self.query_one("#works-search", Input).value)
        self._set_status(f"{author}: {count} work{'' if count == 1 else 's'} in the cache")

    def _fetch_failed(self, what: str, message: str) -> None:
        self._stop_progress(finished=False)
        self._set_status(f"could not fetch {what}: {message}")
        self.app.notify(message, title=f"fetch {what} failed", severity="error")

    # ── progress + status ─────────────────────────────────────────────────────
    def _start_progress(self) -> None:
        self.query_one("#works-progress", ProgressBar).update(total=None)

    def _stop_progress(self, *, finished: bool) -> None:
        self.query_one("#works-progress", ProgressBar).update(
            total=100, progress=100 if finished else 0
        )

    def _set_status(self, message: str) -> None:
        self.query_one("#works-status", Static).update(message)

    def on_worker_state_changed(self, event: "Worker.StateChanged") -> None:
        from textual.worker import WorkerState

        if event.worker.group == "fetch" and event.state in (
            WorkerState.CANCELLED, WorkerState.ERROR
        ):
            self._stop_progress(finished=False)
