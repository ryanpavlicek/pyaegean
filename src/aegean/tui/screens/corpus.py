"""The Corpus Browser screen: browse a corpus, filter its documents, and read
one document with its editorial apparatus and accounting analysis.

Three panes, left to right:

1. the corpus list (the thirteen browsable corpora plus any downloaded Greek
   works, each marked when its data is not yet on disk);
2. the document table for the selected corpus, above a search box (``/`` focuses
   it) that filters the table by document id and, for a sign pattern, surfaces
   the matching words;
3. the document detail: the token lines with their editorial status marked
   (unclear / restored / lost), the heuristic structure, an accounting-balance
   analysis when the document states a total, and, for an undeciphered corpus,
   the exploratory caveat.

The screen is pure view: it calls :mod:`aegean.tui.data` (the adapter) and the
shared widgets, and imports nothing from the library. All analysis (structure,
balances) is the adapter's, so the numbers match the CLI by construction.

Undeciphered-script honesty: for Linear A and Cypro-Minoan the detail pane shows
the exploratory caveat at the point the analysis is read, matching the CLI and
the docstrings. The caveat is rendered by :class:`DetailPane` from the detail's
``undeciphered`` flag, so it cannot be forgotten.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static
from textual.worker import get_current_worker

from .. import data as adapter
from ..widgets import CorpusList, DetailPane, DocTable

if TYPE_CHECKING:
    from ...core.corpus import Corpus
    from ..data import DocRow

__all__ = ["CorpusBrowserScreen"]

_NO_CORPUS = "Select a corpus on the left to browse its documents."
_PICK_DOC = "Select a document to read it."
_SEARCH_PLACEHOLDER = "filter by id, or a sign pattern like KU-*-RO   (press / to focus)"


class CorpusBrowserScreen(Screen[None]):
    """Browse a corpus, filter its documents, and read one document's apparatus,
    structure, and accounting balance."""

    # Screen-scoped layout: the three panes side by side. The shared widget looks
    # (#corpus-list width/border, DetailPane padding) live in app.tcss; this only
    # arranges this screen's own containers and is scoped to it by Textual.
    DEFAULT_CSS = """
    CorpusBrowserScreen {
        layout: horizontal;
    }
    CorpusBrowserScreen #corpus-middle {
        width: 1fr;
    }
    CorpusBrowserScreen #corpus-right-wrap {
        width: 1fr;
    }
    CorpusBrowserScreen #corpus-right {
        height: 1fr;
        border: round $primary-darken-2;
    }
    CorpusBrowserScreen #corpus-right:focus-within {
        border: round $accent;
        background: $boost;
    }
    CorpusBrowserScreen #corpus-inspector {
        height: auto;
        padding: 0 1;
        color: $text-muted;
        border-top: solid $primary-darken-2;
    }
    CorpusBrowserScreen #corpus-list:focus {
        border-right: solid $accent;
    }
    CorpusBrowserScreen #corpus-status {
        color: $text-muted;
        height: auto;
        padding: 0 1;
    }
    CorpusBrowserScreen #corpus-download-bar {
        height: auto;
        padding: 0 1;
        margin: 0 1;
        border: round $accent;
        background: $panel;
        align-vertical: middle;
    }
    CorpusBrowserScreen #corpus-download-bar.hidden {
        display: none;
    }
    CorpusBrowserScreen #corpus-download-msg {
        width: 1fr;
        padding: 0 1;
    }
    CorpusBrowserScreen #corpus-docs {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("f", "download_missing", "Download", show=True),
        Binding("tab", "cycle_focus", "Cycle panes", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        # The loaded corpus and its full (unfiltered) document rows, cached so
        # filtering never reloads. Both are None until a corpus is opened.
        self._corpus: Corpus | None = None
        self._all_rows: list[DocRow] = []
        # The id currently loaded into the table, so re-showing this screen only
        # reloads when the shared selection has actually changed.
        self._loaded_id: str | None = None
        self._loading_id: str | None = None
        self._load_gen: int = 0
        self._shown_doc_id: str | None = None
        self._pending_download_corpus: str | None = None
        self._pending_download_asset: str | None = None
        self._downloading: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield CorpusList(id="corpus-list")
        with Vertical(id="corpus-middle"):
            yield Input(placeholder=_SEARCH_PLACEHOLDER, id="corpus-search")
            yield Static("", id="corpus-status")
            with Horizontal(id="corpus-download-bar", classes="hidden"):
                yield Static("", id="corpus-download-msg", markup=False)
                yield Button("Download", id="corpus-download-btn", variant="primary")
            yield DocTable(id="corpus-docs")
        # A scroll container, not a plain Vertical, so a long document (a whole Iliad
        # book) scrolls: Tab focuses it, then arrows / PageUp / PageDown / mouse wheel
        # move through the text. Below it sits a one-line live token inspector bar.
        with Vertical(id="corpus-right-wrap"):
            with VerticalScroll(id="corpus-right"):
                yield DetailPane(_NO_CORPUS, id="corpus-detail")
            yield Static("", id="corpus-inspector", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_corpus_list()
        docs = self.query_one("#corpus-docs", DocTable)
        docs.cursor_type = "row"
        # A titled border on the reading pane, so it is obvious when Tab has landed there
        # (the title + border turn accent-coloured on focus via the :focus rule above).
        self.query_one("#corpus-right", VerticalScroll).border_title = "reading"
        self._sync_to_state()

    def on_screen_resume(self) -> None:
        """Whenever the screen is shown again, reconcile with the shared
        selection: a corpus opened from Home, the works library, or the command
        palette while this screen was hidden is loaded here on return. The list is
        rebuilt first so a work fetched since we mounted appears as its own item."""
        self._refresh_corpus_list()
        self._sync_to_state()

    def _refresh_corpus_list(self) -> None:
        """List the registered corpora AND every downloaded Greek work, so an opened work
        is a permanent, selectable menu item (not a transient load that vanishes when the
        selection changes). Keep the highlight on the loaded corpus/work."""
        corpus_list = self.query_one("#corpus-list", CorpusList)
        corpus_list.set_corpora(list(adapter.list_corpora()) + adapter.fetched_work_entries())
        active_id = self._loaded_id or self._loading_id
        if active_id is not None:
            corpus_list.highlight_id(active_id)

    def _sync_to_state(self) -> None:
        """Load the shared-selected corpus if it differs from what is displayed."""
        selected = self.app.state.selected_corpus  # type: ignore[attr-defined]
        if (
            selected is not None
            and selected != self._loaded_id
            and selected != self._loading_id
        ):
            self._open_corpus(selected)

    def _hide_download_bar(self) -> None:
        self._pending_download_corpus = None
        self._pending_download_asset = None
        if self.is_mounted:
            self.query_one("#corpus-download-bar", Horizontal).add_class("hidden")

    # ── corpus selection ──────────────────────────────────────────────────────
    def on_list_view_selected(self, event: CorpusList.Selected) -> None:
        """Choosing a corpus on the left loads it and sets the shared selection."""
        corpus_id = event.item.name
        if corpus_id is not None:
            self.app.set_corpus(corpus_id)  # type: ignore[attr-defined]
            self._open_corpus(corpus_id)

    def _open_corpus(self, corpus_id: str) -> None:
        """Load ``corpus_id`` into the document table off the UI thread.

        If ``corpus_id`` is a fetchable corpus that has not yet been downloaded,
        shows an inline Download bar so the user can fetch it with one click (or
        key ``f``) and automatically open it once stored."""
        status = self.query_one("#corpus-status", Static)
        missing = adapter.missing_corpus_item(corpus_id)
        if missing is not None:
            self._load_gen += 1
            self._loading_id = None
            self._corpus = None
            self._all_rows = []
            self._loaded_id = None
            self._shown_doc_id = None
            self._pending_download_corpus = corpus_id
            self._pending_download_asset = missing.id
            self.query_one("#corpus-docs", DocTable).set_documents([])
            self.query_one("#corpus-list", CorpusList).highlight_id(corpus_id)
            status.update(f"{corpus_id} is not downloaded yet ({missing.size_hint}).")
            bar = self.query_one("#corpus-download-bar", Horizontal)
            bar.remove_class("hidden")
            self.query_one("#corpus-download-msg", Static).update(
                f"{missing.title} ({missing.size_hint}) is not downloaded yet."
            )
            btn = self.query_one("#corpus-download-btn", Button)
            btn.label = f"Download {corpus_id}"
            btn.disabled = self._downloading
            self.query_one("#corpus-detail", DetailPane).update(
                f"{missing.title}\n\n"
                f"Press f (or click Download above) to install {missing.id} ({missing.size_hint}), "
                "or press l to open the Library Manager."
            )
            return

        self._hide_download_bar()
        self._shown_doc_id = None
        self._load_gen += 1
        self._loading_id = corpus_id
        status.update(f"loading {corpus_id}…")
        self._load_corpus_worker(corpus_id, self._load_gen)

    def action_download_missing(self) -> None:
        """Download the currently selected uninstalled corpus (key ``f``)."""
        if self._downloading or not self._pending_download_asset or not self._pending_download_corpus:
            return
        self._downloading = True
        corpus_id = self._pending_download_corpus
        asset_id = self._pending_download_asset
        self.query_one("#corpus-download-btn", Button).disabled = True
        self.query_one("#corpus-download-msg", Static).update(f"Downloading {asset_id}…")
        self._download_corpus_worker(corpus_id, asset_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "corpus-download-btn":
            self.action_download_missing()

    @work(exclusive=True, thread=True, group="corpus-download")
    def _download_corpus_worker(self, corpus_id: str, asset_id: str) -> None:
        worker = get_current_worker()

        def on_progress(msg: str) -> None:
            if self.app.is_running:
                try:
                    self.app.call_from_thread(self._set_download_msg, msg)
                except RuntimeError:
                    pass

        try:
            adapter.library_install(
                [asset_id],
                on_progress=on_progress,
                abort=lambda: worker.is_cancelled,
            )
        except adapter.FetchCanceled as exc:
            self._deliver_download_done(corpus_id, asset_id, str(exc), canceled=True)
            return
        except adapter.TuiError as exc:
            self._deliver_download_done(corpus_id, asset_id, str(exc), canceled=False)
            return
        self._deliver_download_done(corpus_id, asset_id, None, canceled=False)

    def _set_download_msg(self, msg: str) -> None:
        if self.is_mounted:
            self.query_one("#corpus-download-msg", Static).update(msg)

    def _deliver_download_done(
        self, corpus_id: str, asset_id: str, error: str | None, *, canceled: bool
    ) -> None:
        if not self.app.is_running:
            return
        try:
            self.app.call_from_thread(
                self._apply_download_done, corpus_id, asset_id, error, canceled
            )
        except RuntimeError:
            return

    def _apply_download_done(
        self, corpus_id: str, asset_id: str, error: str | None, canceled: bool
    ) -> None:
        self._downloading = False
        if not self.is_mounted:
            return
        self.query_one("#corpus-download-btn", Button).disabled = False
        if error is not None:
            self.notify(error, severity="warning" if canceled else "error")
            self.query_one("#corpus-download-msg", Static).update(error)
            return
        self.notify(f"Installed {asset_id}", severity="information")
        self._refresh_corpus_list()
        self._open_corpus(corpus_id)

    @work(exclusive=True, thread=True, group="corpus-load")
    def _load_corpus_worker(self, corpus_id: str, gen: int) -> None:
        """Read ``corpus_id`` and build its document rows on a background thread."""
        worker = get_current_worker()
        if worker.is_cancelled:
            return
        try:
            corpus = adapter.read_corpus_spec(corpus_id)
            if worker.is_cancelled:
                return
            rows = adapter.document_rows(corpus)
        except adapter.TuiError as exc:
            if worker.is_cancelled:
                return
            self._deliver_corpus_result(corpus_id, gen, None, [], str(exc))
            return
        if worker.is_cancelled:
            return
        self._deliver_corpus_result(corpus_id, gen, corpus, rows, None)

    def _deliver_corpus_result(
        self,
        corpus_id: str,
        gen: int,
        corpus: "Corpus | None",
        rows: "list[DocRow]",
        error: str | None,
    ) -> None:
        """Hop back to the UI thread unless the app has already stopped."""
        if not self.app.is_running:
            return
        try:
            self.app.call_from_thread(
                self._apply_loaded_corpus, corpus_id, gen, corpus, rows, error
            )
        except RuntimeError:
            return

    def _apply_loaded_corpus(
        self,
        corpus_id: str,
        gen: int,
        corpus: "Corpus | None",
        rows: "list[DocRow]",
        error: str | None,
    ) -> None:
        """Apply a completed background corpus load on the UI thread."""
        if gen != self._load_gen or not self.is_mounted:
            return
        self._loading_id = None
        status = self.query_one("#corpus-status", Static)
        detail = self.query_one("#corpus-detail", DetailPane)
        if error is not None or corpus is None:
            self._corpus = None
            self._all_rows = []
            self._loaded_id = None
            self.query_one("#corpus-docs", DocTable).set_documents([])
            status.update(error or f"failed to load {corpus_id}")
            detail.update(_NO_CORPUS)
            return
        self._corpus = corpus
        self._all_rows = rows
        self._loaded_id = corpus_id
        self.query_one("#corpus-list", CorpusList).highlight_id(corpus_id)
        self.query_one("#corpus-search", Input).value = ""
        self._render_rows(self._all_rows)
        status.update(f"{corpus_id}: {len(self._all_rows)} documents")
        detail.update(_PICK_DOC)

    def _render_rows(self, rows: "list[DocRow]") -> None:
        self.query_one("#corpus-docs", DocTable).set_documents(rows)

    # ── search / filter ───────────────────────────────────────────────────────
    def action_focus_search(self) -> None:
        """``/`` focuses the search box."""
        self.query_one("#corpus-search", Input).focus()

    def action_cycle_focus(self) -> None:
        """``tab`` cycles list -> search -> table -> reader (so the reader is reachable;
        once focused, ↑/↓ move the line cursor and Enter / ``a`` analyzes that line)."""
        order = ("#corpus-list", "#corpus-search", "#corpus-docs", "#corpus-detail")
        focused = self.focused
        current = -1
        for i, sel in enumerate(order):
            if focused is self.query_one(sel):
                current = i
                break
        self.query_one(order[(current + 1) % len(order)]).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the document table as the query changes.

        A document matches when its id contains the query (case-insensitive). For
        a sign pattern (``KU-*-RO``), the words in the corpus that match are also
        surfaced in the status line, keeping the corpus-wide sign search reachable
        from the same box.

        The id filter is a fast in-memory pass and runs inline. The corpus-wide
        sign search scans every word in the corpus, so it is dispatched to an
        exclusive background worker: a keystroke never blocks the UI, and a fresh
        keystroke cancels the previous still-running search before its own."""
        if event.input.id != "corpus-search":
            return
        query = event.value.strip()
        corpus = self._corpus
        if corpus is None:
            return
        if not query:
            self._render_rows(self._all_rows)
            self.query_one("#corpus-status", Static).update(
                f"{len(self._all_rows)} documents"
            )
            return
        folded = query.casefold()
        filtered = [r for r in self._all_rows if folded in r.id.casefold()]
        self._render_rows(filtered)
        status = f"{len(filtered)} of {len(self._all_rows)} documents match id {query!r}"
        if self._looks_like_pattern(query):
            self.query_one("#corpus-status", Static).update(f"{status}  ·  searching {query}…")
            self._sign_search(query, status)
        else:
            self.query_one("#corpus-status", Static).update(status)

    @work(exclusive=True, thread=True, group="sign-search")
    def _sign_search(self, query: str, base_status: str) -> None:
        """Run the corpus-wide sign search off the UI thread and append its result
        to ``base_status``.

        A thread worker so a large-corpus scan never freezes the UI; ``exclusive``
        so a newer keystroke supersedes this search. Cancellation of a running
        thread is cooperative, so a superseded search can still FINISH its scan —
        the ``is_cancelled`` check below is what keeps its stale result from
        overwriting the newer query's status line. Widget updates hop back to the
        UI thread via :meth:`call_from_thread`."""
        from textual.worker import get_current_worker

        worker = get_current_worker()
        corpus = self._corpus
        if corpus is None:
            return
        matches = adapter.search_corpus(corpus, query)
        if matches:
            shown = ", ".join(f"{w} ({n})" for w, n in matches[:6])
            more = "" if len(matches) <= 6 else f", +{len(matches) - 6} more"
            status = f"{base_status}  ·  words matching {query}: {shown}{more}"
        else:
            status = f"{base_status}  ·  no words match {query}"
        if worker.is_cancelled:  # superseded by a newer keystroke: discard, don't render
            return
        self.app.call_from_thread(
            self.query_one("#corpus-status", Static).update, status
        )

    @staticmethod
    def _looks_like_pattern(query: str) -> bool:
        """Whether the query is a multi-sign wildcard pattern worth running as a
        corpus word search (contains a hyphen or a ``*`` wildcard)."""
        return "-" in query or "*" in query

    # ── document detail + analysis ────────────────────────────────────────────
    def on_data_table_row_selected(self, event: DocTable.RowSelected) -> None:
        """Reading a document row renders its apparatus-aware detail plus the
        accounting-balance analysis (both from the adapter)."""
        if self._corpus is None:
            return
        doc_id = event.row_key.value
        if doc_id is None:
            return
        self.app.set_doc(doc_id)  # type: ignore[attr-defined]
        self._show_document(doc_id)

    def _show_document(self, doc_id: str) -> None:
        self._shown_doc_id = None
        detail = self.query_one("#corpus-detail", DetailPane)
        corpus = self._corpus
        if corpus is None:
            return
        try:
            info = adapter.document_detail(corpus, doc_id)
            document = adapter._resolve_document(corpus, doc_id)
        except adapter.TuiError as exc:
            detail.update(str(exc))
            return
        balances = adapter.balance_rows(document)
        detail.show_document(info, balances)
        self._shown_doc_id = info.id
        # start a freshly-opened document at the top; hint the reader's line cursor + analysis
        self.query_one("#corpus-right", VerticalScroll).scroll_home(animate=False)
        self.query_one("#corpus-status", Static).update(
            f"{doc_id} — Tab to reader: ↑/↓ line · ←/→ word · i interlinear · Enter/a analyze"
        )

    def on_detail_pane_token_highlighted(self, event: DetailPane.TokenHighlighted) -> None:
        """Update the one-line token inspector bar beneath the reader."""
        script_id = self._corpus.script_id if self._corpus is not None else "greek"
        summary = adapter.format_token_inspector(event.token, script_id=script_id)
        self.query_one("#corpus-inspector", Static).update(f"L{event.line_number}: {summary}")

    def on_detail_pane_line_chosen(self, event: DetailPane.LineChosen) -> None:
        """Open the analysis modal for the reader line the user chose (Enter / ``a``)."""
        corpus = self._corpus
        if corpus is None:
            return
        from .analysis import LineAnalysisScreen

        self.app.push_screen(
            LineAnalysisScreen(
                script_id=corpus.script_id,
                line_number=event.line_number,
                line_text=event.line_text,
                token_texts=event.token_texts,
                source_context=(
                    adapter._line_source_context(
                        corpus, self._shown_doc_id, event.line_number, token_texts=event.token_texts,
                    )
                    if corpus.script_id == "greek" else None
                ),
            )
        )
