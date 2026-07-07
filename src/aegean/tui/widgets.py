"""Reusable widgets shared across the TUI screens.

Four small widgets over Textual's `ListView` / `DataTable` / `Static` that hold
the presentation the screens compose. Each is a thin adapter from the plain
dataclasses :mod:`aegean.tui.data` returns to a Textual view, so a screen never
formats a row itself. Centralizing them here gives every screen one stable
widget API and keeps row formatting in a single place.

The library boundary stays in :mod:`aegean.tui.data`: these widgets take already-
shaped rows and render them. They import Textual (this file lives under
``aegean.tui`` and is never imported by ``import aegean``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable, ListItem, ListView, Static

if TYPE_CHECKING:
    from .data import BalanceRow, CorpusEntry, DocDetail, DocRow

__all__ = ["CorpusList", "DocTable", "DetailPane", "KeyValueTable"]

# Editorial status -> a short marker for the detail pane. Undeciphered corpora
# are almost entirely certain, but a bring-your-own EpiDoc corpus populates the
# apparatus, and the NT/Greek texts can carry it.
_STATUS_MARK = {
    "certain": "",
    "unclear": "?",
    "restored": "[ ]",
    "lost": "---",
}


class CorpusList(ListView):
    """A selectable list of corpora, each line ``id — blurb`` (with a ``·
    undeciphered`` tag and a ``· fetch`` tag where the data is not on disk).

    The selected corpus id is read from ``highlighted_child`` (its ``name``), so
    a screen reacts to selection without tracking indices itself."""

    def set_corpora(self, corpora: "list[CorpusEntry]") -> None:
        """Replace the list contents with ``corpora``."""
        self.clear()
        for entry in corpora:
            label = f"{entry.id} — {entry.blurb}"
            if entry.undeciphered:
                label += "  · undeciphered"
            if not entry.downloaded:
                label += "  · fetch"
            self.append(ListItem(Static(label), name=entry.id))

    @property
    def selected_id(self) -> str | None:
        """The id of the highlighted corpus, or ``None`` when nothing is
        highlighted."""
        child = self.highlighted_child
        return None if child is None else child.name

    def highlight_id(self, corpus_id: str) -> None:
        """Move the highlight to the list item for ``corpus_id`` (a no-op if it is not
        listed), so the loaded corpus/work stays selected on the left."""
        for i, child in enumerate(self.children):
            if getattr(child, "name", None) == corpus_id:
                self.index = i
                return


class DocTable(DataTable[str]):
    """A document table: id, site, period, words, and heuristic structure.

    Row keys are the document ids, so a screen resolves the selected row back to
    a document id via the ``RowSelected`` event's ``row_key``."""

    def set_documents(self, rows: "list[DocRow]") -> None:
        """Replace the table with one row per document (id as the row key)."""
        self.clear(columns=True)
        self.add_columns("id", "site", "period", "words", "structure")
        for r in rows:
            self.add_row(
                r.id,
                r.site or "-",
                r.period or "-",
                str(r.n_words),
                r.structure,
                key=r.id,
            )


class KeyValueTable(DataTable[str]):
    """A two-column key/value table (the doctor version/extra rows, a document's
    metadata). Not selectable; a compact read-only display."""

    def set_pairs(self, title_left: str, title_right: str, pairs: "list[tuple[str, str]]") -> None:
        """Replace the table with ``(key, value)`` rows under the given headers."""
        self.clear(columns=True)
        self.add_columns(title_left, title_right)
        for key, value in pairs:
            self.add_row(key, value)


class DetailPane(Static):
    """The document detail: a header (id, metadata, structure), the token lines
    with their editorial apparatus marked, and, for an undeciphered corpus, the
    exploratory caveat.

    The reader is focusable and line-addressable: ↑/↓ (and PgUp/PgDn/Home/End) move
    a highlighted line cursor, and Enter or ``a`` posts :class:`LineChosen` for that
    line so the screen can open the analysis modal. It renders as one console-markup
    string (not a nested widget tree), so ``str(.content)`` reads back the plain text
    in tests. Balance rows, when supplied, are appended as a small table."""

    can_focus = True

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("pageup", "cursor_page_up", "Page up", show=False),
        Binding("pagedown", "cursor_page_down", "Page down", show=False),
        Binding("home", "cursor_first", "First line", show=False),
        Binding("end", "cursor_last", "Last line", show=False),
        Binding("enter", "choose_line", "Analyze line"),
        Binding("a", "choose_line", "Analyze line"),
    ]

    #: The caveat shown for undeciphered corpora, matching the CLI/docstring copy.
    UNDECIPHERED_CAVEAT = (
        "Linear A and Cypro-Minoan are undeciphered; structural analysis is "
        "exploratory, not a reading."
    )

    class LineChosen(Message):
        """Posted when the user picks the current reader line (Enter / ``a``)."""

        def __init__(self, line_number: int, line_text: str, token_texts: tuple[str, ...]) -> None:
            self.line_number = line_number
            self.line_text = line_text
            self.token_texts = token_texts
            super().__init__()

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._detail: DocDetail | None = None
        self._balances: list[BalanceRow] = []
        self._cursor = 0
        self._header_rows = 0

    def show_document(
        self, detail: "DocDetail", balances: "list[BalanceRow] | None" = None
    ) -> None:
        """Render one document's detail (and its balance table, if any), with the line
        cursor reset to the first line."""
        self._detail = detail
        self._balances = balances or []
        self._cursor = 0
        self._rebuild()

    def _rebuild(self) -> None:
        # Built as a console-markup string (Static renders markup): the current line is
        # wrapped in [reverse] so it reads as highlighted. Every piece of document text is
        # rich-escaped first so a restored-reading mark ("[ ]") or a stray bracket in the
        # data can never be mistaken for markup. str(.content) still yields the plain text.
        from rich.markup import escape

        detail = self._detail
        if detail is None:
            return
        meta_bits = [b for b in (detail.site, detail.period, detail.support, detail.scribe) if b]
        header = [detail.id]
        if meta_bits:
            header.append(" · ".join(meta_bits))
        header.append(
            f"{detail.n_words} words · {detail.n_tokens} tokens · structure: {detail.structure}"
        )
        if detail.undeciphered:
            header.append(self.UNDECIPHERED_CAVEAT)
        header.append("")
        out = [escape(row) for row in header]
        self._header_rows = len(header)
        for i, line in enumerate(detail.lines):
            cells = []
            for tok in line.tokens:
                mark = _STATUS_MARK.get(tok.status, "")
                cells.append(f"{tok.text}{mark}" if mark else tok.text)
            row_text = escape(f"{line.number:>3}  " + " ".join(cells))
            out.append(f"[reverse]{row_text}[/reverse]" if i == self._cursor else row_text)
        if self._balances:
            out.append("")
            out.append("accounting balance")
            for b in self._balances:
                verdict = "balances" if b.balances else "OFF"
                out.append(
                    escape(
                        f"    {b.marker}: stated {b.stated:g} vs computed {b.computed:g} "
                        f"(diff {b.difference:+g}) — {verdict}"
                    )
                )
        self.update("\n".join(out))

    # ── line cursor ───────────────────────────────────────────────────────────
    def _line_count(self) -> int:
        return len(self._detail.lines) if self._detail else 0

    def _move_cursor(self, delta: int) -> None:
        n = self._line_count()
        if n == 0:
            return
        new = max(0, min(n - 1, self._cursor + delta))
        if new == self._cursor:
            return
        self._cursor = new
        self._rebuild()
        self._scroll_to_cursor()

    def _scroll_to_cursor(self) -> None:
        """Keep the cursor line within the enclosing scroll container's viewport."""
        parent = self.parent
        scroll_to = getattr(parent, "scroll_to", None)
        if scroll_to is None:
            return
        y = self._header_rows + self._cursor
        top = getattr(parent, "scroll_offset", None)
        top_y = top.y if top is not None else 0
        height = getattr(parent, "size", None)
        view = height.height if height is not None else 0
        if view <= 0:
            return
        if y < top_y:
            scroll_to(y=y, animate=False)
        elif y >= top_y + view:
            scroll_to(y=y - view + 1, animate=False)

    def action_cursor_up(self) -> None:
        self._move_cursor(-1)

    def action_cursor_down(self) -> None:
        self._move_cursor(1)

    def action_cursor_page_up(self) -> None:
        self._move_cursor(-10)

    def action_cursor_page_down(self) -> None:
        self._move_cursor(10)

    def action_cursor_first(self) -> None:
        self._move_cursor(-self._line_count())

    def action_cursor_last(self) -> None:
        self._move_cursor(self._line_count())

    def action_choose_line(self) -> None:
        if self._detail is None or not self._detail.lines:
            return
        line = self._detail.lines[self._cursor]
        token_texts = tuple(tok.text for tok in line.tokens)
        self.post_message(self.LineChosen(line.number, " ".join(token_texts), token_texts))

    @property
    def cursor_line(self) -> int:
        """The current line's 0-based index (for tests / callers)."""
        return self._cursor
