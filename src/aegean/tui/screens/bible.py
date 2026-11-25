"""The Biblical & Koine Greek study screen (`b` in ``aegean tui``).

Brings all five Biblical & Koine Greek specialist workflows into one interactive
terminal workspace with inline one-click downloads when an optional dataset
(``nt-corpus``, ``nt-editions``, ``nt-witnesses``, ``strongs-greek``,
``lxx-corpus``) is not yet installed:

- **Interlinear**: read any Greek NT or Septuagint passage with word-by-word
  lemma, Robinson morphology, Strong's number, and Koine gloss;
- **Editions**: compare Nestle 1904, SBLGNT, Statistical Restoration GNT,
  Byzantine Majority Text, and Textus Receptus with word-level textual diffs;
- **Manuscripts**: compare extant 2nd–5th c. CE uncials and papyri
  (Sinaiticus, Vaticanus, Alexandrinus, Ephraemi, Bezae, Washingtonianus,
  P45–P75) with *nomina sacra* expansions and scribal corrections;
- **Word Study**: Strong's / Extended Strong's lookup, etymological root tree,
  NT book and morphology distribution, and concordance verses;
- **LXX & Catenae**: filterable catalogue of all 55 Swete Septuagint books and
  48 Greek patristic commentaries (NT *Catenae* + Origen), inline LXX reading
  and search, plus LXX ↔ Masoretic Psalm numbering conversion.
"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.worker import get_current_worker

from .. import data as adapter

__all__ = ["BiblicalScreen"]

_EDITIONS: tuple[tuple[str, str], ...] = (
    ("Nestle 1904 (annotated)", "nestle1904"),
    ("SBLGNT (2010)", "sblgnt"),
    ("SRGNT (CNTR)", "srgnt"),
    ("Byzantine Majority", "byz"),
    ("Textus Receptus", "tr"),
)

_HANDS: tuple[tuple[str, str], ...] = (
    ("original hand", "original"),
    ("corrected hand", "corrected"),
)

_TAB_TO_KIND: dict[str, str] = {
    "tab-bible-interlinear": "interlinear",
    "tab-bible-editions": "editions",
    "tab-bible-witnesses": "witnesses",
    "tab-bible-study": "study",
    "tab-bible-lxx": "lxx",
}


class BiblicalScreen(Screen[None]):
    """Interactive Biblical & Koine Greek study screen with inline downloads."""

    DEFAULT_CSS = """
    BiblicalScreen #bible-bar {
        height: auto;
        padding: 0 1;
        margin-bottom: 0;
    }
    BiblicalScreen #bible-passage {
        width: 1fr;
    }
    BiblicalScreen #bible-edition {
        width: 28;
    }
    BiblicalScreen #bible-load {
        width: 10;
    }
    BiblicalScreen #bible-fetch-bar {
        height: auto;
        padding: 0 1;
        margin: 0 1 1 1;
        border: round $accent;
        background: $panel;
        align-vertical: middle;
    }
    BiblicalScreen #bible-fetch-bar.hidden {
        display: none;
    }
    BiblicalScreen #bible-fetch-msg {
        width: 1fr;
        padding: 0 1;
        content-align-vertical: middle;
    }
    BiblicalScreen #bible-fetch-one {
        margin-right: 1;
    }
    BiblicalScreen #bible-tabs {
        height: 1fr;
    }
    BiblicalScreen .bible-scroll {
        height: 1fr;
        padding: 1 2;
    }
    BiblicalScreen .bible-subbar {
        height: auto;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("slash", "focus_passage", "Passage", show=True),
        Binding("f", "fetch_missing", "Download", show=True),
        Binding("r", "refresh_passage", "Reload", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._missing_ids: list[str] = []
        self._fetching: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="bible-bar"):
            yield Input(
                value="John 1.1-5",
                placeholder="Passage (e.g. John 1.1-5, John 1.18, Rom 8.28, Gen 1.1-5)",
                id="bible-passage",
            )
            yield Select(_EDITIONS, value="nestle1904", allow_blank=False, id="bible-edition")
            yield Button("Load", id="bible-load", variant="primary")
        with Horizontal(id="bible-fetch-bar", classes="hidden"):
            yield Static("", id="bible-fetch-msg", markup=False)
            yield Button("Download", id="bible-fetch-one", variant="primary")
            yield Button("Biblical Pack", id="bible-fetch-pack", variant="default")
        with TabbedContent(id="bible-tabs"):
            with TabPane("Interlinear", id="tab-bible-interlinear"):
                with VerticalScroll(classes="bible-scroll"):
                    yield Static("", id="bible-interlinear", markup=False)
            with TabPane("Editions", id="tab-bible-editions"):
                with VerticalScroll(classes="bible-scroll"):
                    yield Static("", id="bible-editions", markup=False)
            with TabPane("Manuscripts", id="tab-bible-witnesses"):
                with Horizontal(classes="bible-subbar"):
                    yield Select(_HANDS, value="original", allow_blank=False, id="bible-hand")
                with VerticalScroll(classes="bible-scroll"):
                    yield Static("", id="bible-witnesses", markup=False)
            with TabPane("Word Study", id="tab-bible-study"):
                with Horizontal(classes="bible-subbar"):
                    yield Input(
                        value="G3056",
                        placeholder="Strong's ID (G3056, G26) or Greek word (λόγος, ἀγάπη)",
                        id="bible-study-input",
                    )
                with VerticalScroll(classes="bible-scroll"):
                    yield Static("", id="bible-study", markup=False)
            with TabPane("LXX & Catenae", id="tab-bible-lxx"):
                with Horizontal(classes="bible-subbar"):
                    yield Input(
                        value="",
                        placeholder="Filter LXX/Catenae, read (Gen 1.1-5), search (φῶς), or Psalm (23)",
                        id="bible-lxx-filter",
                    )
                with VerticalScroll(classes="bible-scroll"):
                    yield Static("", id="bible-lxx", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()

    def on_screen_resume(self) -> None:
        """Refresh views on return (e.g., after installing assets in Library Manager)."""
        self._refresh_all()

    @property
    def _edition(self) -> str:
        val = self.query_one("#bible-edition", Select).value
        return str(val) if val is not Select.BLANK else "nestle1904"

    @property
    def _hand(self) -> str:
        val = self.query_one("#bible-hand", Select).value
        return str(val) if val is not Select.BLANK else "original"

    @property
    def _active_tab_kind(self) -> str:
        tabs = self.query_one("#bible-tabs", TabbedContent)
        return _TAB_TO_KIND.get(str(tabs.active or ""), "interlinear")

    def _refresh_all(self) -> None:
        self._refresh_passage_views()
        self._refresh_study()
        self._refresh_lxx()
        self._update_fetch_bar()

    def _refresh_passage_views(self) -> None:
        passage = self.query_one("#bible-passage", Input).value or "John 1.1-5"
        self.query_one("#bible-interlinear", Static).update(
            adapter.bible_read_text(passage, edition=self._edition, offline=True)
        )
        self.query_one("#bible-editions", Static).update(
            adapter.bible_compare_text(passage, offline=True)
        )
        self.query_one("#bible-witnesses", Static).update(
            adapter.bible_witnesses_text(passage, hand=self._hand, offline=True)
        )
        self._update_fetch_bar()

    def _refresh_study(self) -> None:
        query = self.query_one("#bible-study-input", Input).value
        self.query_one("#bible-study", Static).update(
            adapter.bible_word_study_text(query, offline=True)
        )
        self._update_fetch_bar()

    def _refresh_lxx(self) -> None:
        flt = self.query_one("#bible-lxx-filter", Input).value
        self.query_one("#bible-lxx", Static).update(adapter.bible_lxx_and_catenae_text(flt))
        self._update_fetch_bar()

    def _update_fetch_bar(self) -> None:
        """Show the inline download bar whenever the active view needs an uninstalled bundle."""
        if self._fetching or not self.is_mounted:
            return
        passage = self.query_one("#bible-passage", Input).value or "John 1.1-5"
        missing = adapter.missing_bible_items(
            tab=self._active_tab_kind,
            edition=self._edition,
            passage=passage,
        )
        bar = self.query_one("#bible-fetch-bar", Horizontal)
        self._missing_ids = [it.id for it in missing]
        if not missing:
            bar.add_class("hidden")
            return
        bar.remove_class("hidden")
        first = missing[0]
        if len(missing) == 1:
            msg = f"Not downloaded: {first.title} ({first.id}, {first.size_hint})"
            btn_label = f"Download {first.id}"
        else:
            names = ", ".join(it.id for it in missing)
            msg = f"Not downloaded: {names}"
            btn_label = f"Download ({len(missing)})"
        self.query_one("#bible-fetch-msg", Static).update(msg)
        btn_one = self.query_one("#bible-fetch-one", Button)
        btn_one.label = btn_label
        btn_one.disabled = False
        self.query_one("#bible-fetch-pack", Button).disabled = False

    def action_focus_passage(self) -> None:
        self.query_one("#bible-passage", Input).focus()

    def action_refresh_passage(self) -> None:
        self._refresh_all()

    def action_fetch_missing(self) -> None:
        """Download the missing dataset(s) needed by the active view (key ``f``)."""
        if self._fetching:
            return
        if not self._missing_ids:
            self.notify("All texts for this view are already installed.", severity="information")
            return
        self._start_download(list(self._missing_ids))

    def _start_download(self, targets: list[str]) -> None:
        self._fetching = True
        bar = self.query_one("#bible-fetch-bar", Horizontal)
        bar.remove_class("hidden")
        self.query_one("#bible-fetch-one", Button).disabled = True
        self.query_one("#bible-fetch-pack", Button).disabled = True
        label = ", ".join(targets)
        self.query_one("#bible-fetch-msg", Static).update(f"Downloading {label}…")
        self._download_worker(targets)

    @work(exclusive=True, thread=True, group="bible-fetch")
    def _download_worker(self, targets: list[str]) -> None:
        worker = get_current_worker()

        def on_progress(msg: str) -> None:
            if self.app.is_running:
                try:
                    self.app.call_from_thread(self._set_fetch_status, msg)
                except RuntimeError:
                    pass

        try:
            results = adapter.library_install(
                targets,
                on_progress=on_progress,
                abort=lambda: worker.is_cancelled,
            )
        except adapter.FetchCanceled as exc:
            self._finish_download(None, str(exc), canceled=True)
            return
        except adapter.TuiError as exc:
            self._finish_download(None, str(exc), canceled=False)
            return
        self._finish_download(results, None, canceled=False)

    def _set_fetch_status(self, msg: str) -> None:
        if self.is_mounted:
            self.query_one("#bible-fetch-msg", Static).update(msg)

    def _finish_download(
        self,
        results: list[object] | None,
        error: str | None,
        *,
        canceled: bool,
    ) -> None:
        if not self.app.is_running:
            return
        try:
            self.app.call_from_thread(self._apply_download_done, results, error, canceled)
        except RuntimeError:
            return

    def _apply_download_done(
        self,
        results: list[object] | None,
        error: str | None,
        canceled: bool,
    ) -> None:
        self._fetching = False
        if not self.is_mounted:
            return
        self.query_one("#bible-fetch-one", Button).disabled = False
        self.query_one("#bible-fetch-pack", Button).disabled = False
        if error is not None:
            self.notify(error, severity="warning" if canceled else "error")
            self._update_fetch_bar()
            return
        installed = [r for r in (results or []) if getattr(r, "status", "") == "installed"]
        if installed:
            names = ", ".join(getattr(r, "id", "") for r in installed)
            self.notify(f"Installed {names}", severity="information")
        self._refresh_all()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bible-load":
            self._refresh_passage_views()
        elif event.button.id == "bible-fetch-one":
            self.action_fetch_missing()
        elif event.button.id == "bible-fetch-pack":
            if not self._fetching:
                self._start_download(["biblical"])

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "bible-passage":
            self._refresh_passage_views()
        elif event.input.id == "bible-study-input":
            self._refresh_study()
        elif event.input.id == "bible-lxx-filter":
            self._refresh_lxx()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "bible-lxx-filter":
            self._refresh_lxx()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id in ("bible-edition", "bible-hand"):
            self._refresh_passage_views()

    def on_tabbed_content_tab_activated(self, _event: TabbedContent.TabActivated) -> None:
        self._update_fetch_bar()
