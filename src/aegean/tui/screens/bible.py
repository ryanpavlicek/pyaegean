"""The Biblical & Koine Greek study screen (`b` in ``aegean tui``).

Brings all five Biblical & Koine Greek specialist workflows into one interactive
terminal workspace:

- **Interlinear**: read any Greek NT passage with word-by-word lemma, Robinson
  morphology, Strong's number, and Koine gloss (works offline on John 1 &
  Philemon 1, and all 27 books once cached);
- **Editions**: compare Nestle 1904, SBLGNT, Statistical Restoration GNT,
  Byzantine Majority Text, and Textus Receptus with word-level textual diffs;
- **Manuscripts**: compare extant 2nd–5th c. CE uncials and papyri
  (Sinaiticus, Vaticanus, Alexandrinus, Ephraemi, Bezae, Washingtonianus,
  P45–P75) with *nomina sacra* expansions and scribal corrections;
- **Word Study**: Strong's / Extended Strong's lookup, etymological root tree,
  NT book and morphology distribution, and concordance verses;
- **LXX & Catenae**: filterable catalogue of all 55 Swete Septuagint books and
  48 Greek patristic commentaries (NT *Catenae* + Origen), plus inline
  LXX ↔ Masoretic Psalm numbering conversion.
"""

from __future__ import annotations

from textual.app import ComposeResult
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


class BiblicalScreen(Screen[None]):
    """Interactive Biblical & Koine Greek study screen."""

    DEFAULT_CSS = """
    BiblicalScreen #bible-bar {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
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
        ("slash", "focus_passage", "Passage"),
        ("r", "refresh_passage", "Reload"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="bible-bar"):
            yield Input(
                value="John 1.1-5",
                placeholder="Passage (e.g. John 1.1-5, John 1.18, Rom 8.28)",
                id="bible-passage",
            )
            yield Select(_EDITIONS, value="nestle1904", allow_blank=False, id="bible-edition")
            yield Button("Load", id="bible-load", variant="primary")
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
                        placeholder="Filter LXX/Catenae or type a Psalm number (e.g. 23, Isa, John, Origen)",
                        id="bible-lxx-filter",
                    )
                with VerticalScroll(classes="bible-scroll"):
                    yield Static("", id="bible-lxx", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_passage_views()
        self._refresh_study()
        self._refresh_lxx()

    @property
    def _edition(self) -> str:
        val = self.query_one("#bible-edition", Select).value
        return str(val) if val is not Select.BLANK else "nestle1904"

    @property
    def _hand(self) -> str:
        val = self.query_one("#bible-hand", Select).value
        return str(val) if val is not Select.BLANK else "original"

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

    def _refresh_study(self) -> None:
        query = self.query_one("#bible-study-input", Input).value
        self.query_one("#bible-study", Static).update(
            adapter.bible_word_study_text(query, offline=True)
        )

    def _refresh_lxx(self) -> None:
        flt = self.query_one("#bible-lxx-filter", Input).value
        self.query_one("#bible-lxx", Static).update(adapter.bible_lxx_and_catenae_text(flt))

    def action_focus_passage(self) -> None:
        self.query_one("#bible-passage", Input).focus()

    def action_refresh_passage(self) -> None:
        self._refresh_passage_views()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bible-load":
            self._refresh_passage_views()

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
