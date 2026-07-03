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

    Renders as text (not a nested widget tree) so a screen reads it back via
    ``.content`` in tests. Balance rows, when supplied, are appended as a small
    accounting table."""

    #: The caveat shown for undeciphered corpora, matching the CLI/docstring copy.
    UNDECIPHERED_CAVEAT = (
        "Linear A and Cypro-Minoan are undeciphered; structural analysis is "
        "exploratory, not a reading."
    )

    def show_document(
        self, detail: "DocDetail", balances: "list[BalanceRow] | None" = None
    ) -> None:
        """Render one document's detail (and its balance table, if any)."""
        self.update(self._detail_text(detail, balances or []))

    def _detail_text(self, detail: "DocDetail", balances: "list[BalanceRow]") -> str:
        meta_bits = [
            b for b in (detail.site, detail.period, detail.support, detail.scribe) if b
        ]
        lines = [detail.id]
        if meta_bits:
            lines.append(" · ".join(meta_bits))
        lines.append(
            f"{detail.n_words} words · {detail.n_tokens} tokens · structure: {detail.structure}"
        )
        if detail.undeciphered:
            lines.append(self.UNDECIPHERED_CAVEAT)
        lines.append("")
        for line in detail.lines:
            cells = []
            for tok in line.tokens:
                mark = _STATUS_MARK.get(tok.status, "")
                cells.append(f"{tok.text}{mark}" if mark else tok.text)
            lines.append(f"{line.number:>3}  " + " ".join(cells))
        if balances:
            lines.append("")
            lines.append("accounting balance")
            for b in balances:
                verdict = "balances" if b.balances else "OFF"
                lines.append(
                    f"    {b.marker}: stated {b.stated:g} vs computed {b.computed:g} "
                    f"(diff {b.difference:+g}) — {verdict}"
                )
        return "\n".join(lines)
