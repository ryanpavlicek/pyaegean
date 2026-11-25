"""The unified Library Manager screen (`l` in ``aegean tui``).

One place inside the terminal UI to inspect, search, download, open, and remove
every resource pyaegean supports:

- **Packs**: one-click install/remove for named packs (``biblical``,
  ``aegean``, ``epigraphy``, ``lexica``, ``neural``);
- **Installed**: everything currently available offline on disk across all
  categories (bundled corpora, downloaded datasets, downloaded Greek literary
  works, patristic commentaries, lexica, and models);
- **Corpora & Biblical**: all 14 Aegean/Greek corpora and 5 Biblical & Koine
  Greek bundles;
- **Works & Commentaries**: searchable catalogue of ~1,778 Perseus /
  First1KGreek literary works and 48 patristic commentaries;
- **Lexica & Models**: all 5 hosted dictionaries, NLP/neural models, and media
  assets.
"""

from __future__ import annotations

from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
)
from textual.worker import get_current_worker

from .. import data as adapter

__all__ = ["LibraryScreen"]

_WORKS_DISPLAY_CAP = 200


def _fmt_size(n: int | None, hint: str = "") -> str:
    if n is not None and n > 0:
        if n >= 1_000_000_000:
            return f"{n / 1_000_000_000:.1f} GB"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f} MB"
        if n >= 1_000:
            return f"{n / 1_000:.1f} KB"
        return f"{n} B"
    return hint or "—"


def _status_text(item: Any) -> str:
    if item.status == "bundled":
        return "bundled"
    if item.status == "installed":
        return f"installed ({_fmt_size(item.bytes)})"
    return f"available ({item.size_hint})"


class LibraryScreen(Screen[None]):
    """Unified Library Manager for corpora, Biblical bundles, works, lexica, and models."""

    DEFAULT_CSS = """
    LibraryScreen #lib-header {
        height: auto;
        padding: 0 2;
        color: $text-muted;
    }
    LibraryScreen #lib-search {
        margin: 0 1 1 1;
    }
    LibraryScreen #lib-tabs {
        height: 1fr;
    }
    LibraryScreen DataTable {
        height: 1fr;
        max-height: 1fr;
    }
    LibraryScreen #lib-actions {
        height: auto;
        padding: 0 1;
        margin-top: 1;
        align-vertical: middle;
    }
    LibraryScreen #lib-actions Button {
        margin-right: 1;
    }
    LibraryScreen #lib-status {
        width: 1fr;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("f", "install_selected", "Download", show=True),
        Binding("o", "open_selected", "Open", show=True),
        Binding("x", "remove_selected", "Remove", show=True),
        Binding("r", "refresh_all", "Reload", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._busy: bool = False
        self._tab_items: dict[str, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="lib-header", markup=False)
        yield Input(
            placeholder="Filter current tab (e.g. biblical, damos, Plato, Iliad, lsj)  —  press / to focus",
            id="lib-search",
        )
        with TabbedContent(id="lib-tabs"):
            with TabPane("Packs", id="tab-lib-packs"):
                yield DataTable(id="lib-packs-table")
            with TabPane("Installed", id="tab-lib-installed"):
                yield DataTable(id="lib-installed-table")
            with TabPane("Corpora & Biblical", id="tab-lib-corpora"):
                yield DataTable(id="lib-corpora-table")
            with TabPane("Works & Commentaries", id="tab-lib-works"):
                yield DataTable(id="lib-works-table")
            with TabPane("Lexica & Models", id="tab-lib-models"):
                yield DataTable(id="lib-models-table")
        with Horizontal(id="lib-actions"):
            yield Button("Download (f)", id="lib-install", variant="primary")
            yield Button("Open (o)", id="lib-open", variant="default")
            yield Button("Remove (x)", id="lib-remove", variant="error")
            yield Static("", id="lib-status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._init_tables()
        self._populate_all()

    def on_screen_resume(self) -> None:
        self._populate_all()

    def _init_tables(self) -> None:
        packs = self.query_one("#lib-packs-table", DataTable)
        packs.cursor_type = "row"
        packs.add_columns("pack", "status", "size", "title", "contents")

        for tid in (
            "#lib-installed-table",
            "#lib-corpora-table",
            "#lib-works-table",
            "#lib-models-table",
        ):
            tbl = self.query_one(tid, DataTable)
            tbl.cursor_type = "row"
            tbl.add_columns("id", "category", "status", "title")

    def _populate_all(self) -> None:
        query = self.query_one("#lib-search", Input).value.strip()
        snap = adapter.library_summary()
        self.query_one("#lib-header", Static).update(
            f"Store: {snap['store_path']}  ·  "
            f"{snap['bundled_count']} bundled  ·  "
            f"{snap['downloaded_count']} downloaded ({snap['installed_size'] or '0 B'})"
        )
        self._populate_packs(query)
        self._populate_installed(query)
        self._populate_corpora(query)
        self._populate_works(query)
        self._populate_models(query)
        self._sync_action_buttons()

    def _populate_packs(self, query: str) -> None:
        tbl = self.query_one("#lib-packs-table", DataTable)
        tbl.clear()
        ql = query.lower()
        row_map: dict[str, Any] = {}
        for st in adapter.library_packs():
            p = st.pack
            if ql and ql not in f"{p.id} {p.title} {p.description} {' '.join(p.items)}".lower():
                continue
            state = "complete" if st.complete else f"{st.installed_count}/{st.total_count} installed"
            tbl.add_row(p.id, state, p.size_hint, p.title, ", ".join(p.items), key=p.id)
            row_map[p.id] = st
        self._tab_items["tab-lib-packs"] = row_map

    def _populate_installed(self, query: str) -> None:
        tbl = self.query_one("#lib-installed-table", DataTable)
        tbl.clear()
        items = adapter.library_items(status="installed", query=query or None, include_works=True)
        row_map: dict[str, Any] = {}
        for it in items:
            tbl.add_row(it.id, it.category, _status_text(it), it.title, key=it.id)
            row_map[it.id] = it
        self._tab_items["tab-lib-installed"] = row_map

    def _populate_corpora(self, query: str) -> None:
        tbl = self.query_one("#lib-corpora-table", DataTable)
        tbl.clear()
        all_items = adapter.library_items(query=query or None, include_works=False)
        items = [it for it in all_items if it.category in ("corpus", "bible")]
        row_map: dict[str, Any] = {}
        for it in items:
            tbl.add_row(it.id, it.category, _status_text(it), it.title, key=it.id)
            row_map[it.id] = it
        self._tab_items["tab-lib-corpora"] = row_map

    def _populate_works(self, query: str) -> None:
        tbl = self.query_one("#lib-works-table", DataTable)
        tbl.clear()
        works = adapter.library_items(category="work", query=query or None, limit=_WORKS_DISPLAY_CAP)
        row_map: dict[str, Any] = {}
        for it in works:
            tbl.add_row(it.id, it.category, _status_text(it), it.title, key=it.id)
            row_map[it.id] = it
        self._tab_items["tab-lib-works"] = row_map

    def _populate_models(self, query: str) -> None:
        tbl = self.query_one("#lib-models-table", DataTable)
        tbl.clear()
        all_items = adapter.library_items(query=query or None, include_works=False)
        items = [it for it in all_items if it.category in ("lexicon", "model", "other")]
        row_map: dict[str, Any] = {}
        for it in items:
            tbl.add_row(it.id, it.category, _status_text(it), it.title, key=it.id)
            row_map[it.id] = it
        self._tab_items["tab-lib-models"] = row_map

    def _active_tab_and_table(self) -> tuple[str, DataTable[Any]]:
        tab_id = str(self.query_one("#lib-tabs", TabbedContent).active or "tab-lib-packs")
        table_map = {
            "tab-lib-packs": "#lib-packs-table",
            "tab-lib-installed": "#lib-installed-table",
            "tab-lib-corpora": "#lib-corpora-table",
            "tab-lib-works": "#lib-works-table",
            "tab-lib-models": "#lib-models-table",
        }
        return tab_id, self.query_one(table_map.get(tab_id, "#lib-packs-table"), DataTable)

    def _selected_key_and_obj(self) -> tuple[str | None, Any | None]:
        tab_id, tbl = self._active_tab_and_table()
        if tbl.row_count == 0 or tbl.cursor_row < 0 or tbl.cursor_row >= tbl.row_count:
            return None, None
        row = tbl.get_row_at(tbl.cursor_row)
        key = str(row[0])
        return key, self._tab_items.get(tab_id, {}).get(key)

    def _sync_action_buttons(self) -> None:
        if not self.is_mounted:
            return
        btn_install = self.query_one("#lib-install", Button)
        btn_open = self.query_one("#lib-open", Button)
        btn_remove = self.query_one("#lib-remove", Button)
        if self._busy:
            btn_install.disabled = True
            btn_open.disabled = True
            btn_remove.disabled = True
            return
        key, obj = self._selected_key_and_obj()
        if key is None or obj is None:
            btn_install.disabled = True
            btn_open.disabled = True
            btn_remove.disabled = True
            return
        if hasattr(obj, "pack"):  # PackStatus
            btn_install.disabled = obj.complete
            btn_open.disabled = obj.pack.id != "biblical"
            btn_remove.disabled = obj.installed_count == 0
        else:  # LibraryItem
            btn_install.disabled = obj.installed
            can_open = obj.installed and (
                obj.open_spec is not None or obj.category == "bible"
            )
            btn_open.disabled = not can_open
            btn_remove.disabled = not obj.removable

    def action_focus_search(self) -> None:
        self.query_one("#lib-search", Input).focus()

    def action_refresh_all(self) -> None:
        self._populate_all()

    def action_install_selected(self) -> None:
        if self._busy:
            return
        key, obj = self._selected_key_and_obj()
        if key is None or obj is None:
            return
        if hasattr(obj, "pack"):
            if obj.complete:
                self.notify(f"Pack {key!r} is already installed.", severity="information")
                return
        elif obj.installed:
            self.notify(f"{key!r} is already installed.", severity="information")
            return
        self._busy = True
        self._sync_action_buttons()
        self.query_one("#lib-status", Static).update(f"Downloading {key}…")
        self._install_worker(key)

    def action_open_selected(self) -> None:
        key, obj = self._selected_key_and_obj()
        if key is None or obj is None:
            return
        if hasattr(obj, "pack"):
            if obj.pack.id == "biblical":
                self.app.goto("bible")  # type: ignore[attr-defined]
            return
        if not obj.installed:
            self.notify(f"Download {key!r} first (press f).", severity="warning")
            return
        if obj.open_spec is not None:
            self.app.open_corpus(obj.open_spec)  # type: ignore[attr-defined]
        elif obj.category == "bible":
            self.app.goto("bible")  # type: ignore[attr-defined]

    def action_remove_selected(self) -> None:
        if self._busy:
            return
        key, obj = self._selected_key_and_obj()
        if key is None or obj is None:
            return
        if hasattr(obj, "pack"):
            if obj.installed_count == 0:
                self.notify(f"Nothing from pack {key!r} is installed.", severity="information")
                return
        elif not obj.removable:
            msg = f"{key!r} is bundled and cannot be removed." if obj.status == "bundled" else f"{key!r} is not installed."
            self.notify(msg, severity="warning")
            return
        try:
            results = adapter.library_remove([key])
        except adapter.TuiError as exc:
            self.notify(str(exc), severity="error")
            return
        reclaimed = sum(r.bytes_reclaimed for r in results if r.status == "removed")
        n_removed = sum(1 for r in results if r.status == "removed")
        if n_removed:
            self.query_one("#lib-status", Static).update(
                f"Removed {key} ({_fmt_size(reclaimed)} reclaimed)"
            )
            self.notify(f"Removed {key} ({_fmt_size(reclaimed)} reclaimed)", severity="information")
        self._populate_all()

    @work(exclusive=True, thread=True, group="lib-install")
    def _install_worker(self, target: str) -> None:
        worker = get_current_worker()

        def on_progress(msg: str) -> None:
            if self.app.is_running:
                try:
                    self.app.call_from_thread(self._set_status, msg)
                except RuntimeError:
                    pass

        try:
            results = adapter.library_install(
                [target],
                on_progress=on_progress,
                abort=lambda: worker.is_cancelled,
            )
        except adapter.FetchCanceled as exc:
            self._finish_install(target, None, str(exc), canceled=True)
            return
        except adapter.TuiError as exc:
            self._finish_install(target, None, str(exc), canceled=False)
            return
        self._finish_install(target, results, None, canceled=False)

    def _set_status(self, msg: str) -> None:
        if self.is_mounted:
            self.query_one("#lib-status", Static).update(msg)

    def _finish_install(
        self,
        target: str,
        results: list[Any] | None,
        error: str | None,
        *,
        canceled: bool,
    ) -> None:
        if not self.app.is_running:
            return
        try:
            self.app.call_from_thread(self._apply_install_done, target, results, error, canceled)
        except RuntimeError:
            return

    def _apply_install_done(
        self,
        target: str,
        results: list[Any] | None,
        error: str | None,
        canceled: bool,
    ) -> None:
        self._busy = False
        if not self.is_mounted:
            return
        if error is not None:
            self.query_one("#lib-status", Static).update(error)
            self.notify(error, severity="warning" if canceled else "error")
            self._sync_action_buttons()
            return
        installed = [r for r in (results or []) if getattr(r, "status", "") == "installed"]
        if installed:
            msg = f"Installed {len(installed)} item(s) for {target}"
            self.query_one("#lib-status", Static).update(msg)
            self.notify(msg, severity="information")
        else:
            self.query_one("#lib-status", Static).update(f"{target} already installed")
        self._populate_all()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "lib-search":
            self._populate_all()

    def on_tabbed_content_tab_activated(self, _event: TabbedContent.TabActivated) -> None:
        self._sync_action_buttons()

    def on_data_table_row_highlighted(self, _event: DataTable.RowHighlighted) -> None:
        self._sync_action_buttons()

    def on_data_table_row_selected(self, _event: DataTable.RowSelected) -> None:
        key, obj = self._selected_key_and_obj()
        if key is None or obj is None:
            return
        if hasattr(obj, "pack"):
            if obj.complete and obj.pack.id == "biblical":
                self.action_open_selected()
            elif not obj.complete:
                self.action_install_selected()
            return
        if obj.installed and (obj.open_spec is not None or obj.category == "bible"):
            self.action_open_selected()
        elif not obj.installed:
            self.action_install_selected()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "lib-install":
            self.action_install_selected()
        elif event.button.id == "lib-open":
            self.action_open_selected()
        elif event.button.id == "lib-remove":
            self.action_remove_selected()
