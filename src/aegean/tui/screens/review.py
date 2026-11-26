"""Interactive annotation and reviewer-disagreement adjudication screen.

Supports three entry points:

- a single review CSV exported by ``aegean review export`` (either the full
  schema or ``layout="editable"`` with its ``.companion.json`` snapshot);
- two or more reviewers' copies of the same export merged with
  ``merge_review_tables(..., on_conflict="report")``, surfacing each genuine
  disagreement as numbered one-key options (``1`` / ``2`` / ``3``);
- a live corpus queue generated on demand via ``to_review_table`` (using
  calibrated risk priority when calibrated confidence annotations are present).

All state transitions delegate to :class:`aegean.tui._review_data.ReviewSession`
so saving preserves immutable snapshot hashes and round-trips cleanly through
``aegean review apply``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from .._review_data import (
    FILTER_MODES,
    REVIEW_FIELD_NAMES,
    ReviewItem,
    ReviewSession,
)

if TYPE_CHECKING:
    from ...core.corpus import Corpus

__all__ = ["ReviewScreen"]

_EMPTY_DETAIL = (
    "[b]Annotation & Disagreement Review[/b]\n\n"
    "Enter a review CSV path (or comma-separated reviewer CSVs, or a corpus id like "
    "[b]nt[/b]) above and press [b]Load[/b], or launch directly with:\n"
    "  [dim]aegean tui --review review.csv[/dim]\n"
    "  [dim]aegean tui --review alice.csv --review bob.csv --corpus nt[/dim]\n\n"
    "[b]Keys:[/b] [b]a[/b] accept · [b]e[/b] edit · [b]1/2/3[/b] pick conflict option · "
    "[b]d[/b] defer · [b]x[/b] reject · [b]n/p[/b] next/prev unresolved · "
    "[b]f[/b] cycle filter · [b]s[/b] save"
)


class ReviewScreen(Screen[None]):
    """Split-pane interactive annotation and conflict-resolution workspace."""

    BINDINGS = [
        Binding("a", "accept", "Accept"),
        Binding("e", "edit", "Edit"),
        Binding("1", "pick_option(0)", "Pick 1", show=False),
        Binding("2", "pick_option(1)", "Pick 2", show=False),
        Binding("3", "pick_option(2)", "Pick 3", show=False),
        Binding("d", "defer", "Defer"),
        Binding("x", "reject", "Reject"),
        Binding("n", "next_unresolved", "Next"),
        Binding("p", "prev_unresolved", "Prev"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("s", "save", "Save"),
        Binding("o", "focus_open", "Open"),
    ]

    DEFAULT_CSS = """
    ReviewScreen #review-top {
        height: auto;
        padding: 0 1;
        border-bottom: solid $primary-darken-2;
    }
    ReviewScreen #review-status {
        height: auto;
        padding: 0 0 1 0;
        color: $text;
    }
    ReviewScreen #review-open-row {
        height: auto;
        margin-bottom: 1;
    }
    ReviewScreen #review-open-input {
        width: 1fr;
    }
    ReviewScreen #review-main {
        height: 1fr;
    }
    ReviewScreen #review-left {
        width: 48;
        border-right: solid $primary-darken-2;
    }
    ReviewScreen #review-table {
        height: 1fr;
        max-height: 1fr;
    }
    ReviewScreen #review-right {
        width: 1fr;
        padding: 1 2;
    }
    ReviewScreen #review-context,
    ReviewScreen #review-fields,
    ReviewScreen #review-conflicts,
    ReviewScreen #review-evidence {
        height: auto;
        margin-bottom: 1;
    }
    ReviewScreen #review-editor {
        height: auto;
        border: round $primary-darken-1;
        padding: 1;
        margin-top: 1;
    }
    ReviewScreen .edit-row {
        height: auto;
        margin-bottom: 1;
    }
    ReviewScreen .edit-label {
        width: 12;
        padding-top: 1;
        color: $text-muted;
    }
    ReviewScreen .edit-input {
        width: 1fr;
    }
    ReviewScreen #review-edit-actions {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.session: ReviewSession | None = None
        self.filter_mode: str = "all"
        self._visible_indices: list[int] = []
        self._selected_item_index: int | None = None
        self._loaded_signature: tuple[tuple[str, ...], str | None] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="review-top"):
            yield Static("Annotation review — no file loaded", id="review-status")
            with Horizontal(id="review-open-row"):
                yield Input(
                    placeholder="review.csv (or a.csv,b.csv) or corpus id — press Enter to load",
                    id="review-open-input",
                )
                yield Button("Load", id="review-load-btn", variant="primary")
                yield Button("Filter: all", id="review-filter-btn")
                yield Button("Save", id="review-save-btn", variant="success")
        with Horizontal(id="review-main"):
            with Vertical(id="review-left"):
                yield DataTable(id="review-table", cursor_type="row")
            with VerticalScroll(id="review-right"):
                yield Static(_EMPTY_DETAIL, id="review-context")
                yield Static("", id="review-fields")
                yield Static("", id="review-conflicts")
                yield Static("", id="review-evidence")
                with Vertical(id="review-editor"):
                    yield Static("[b]Edit current token[/b]  (Enter or Apply to commit)", id="review-edit-title")
                    for fname, placeholder in (
                        ("lemma", "corrected lemma (matches prediction → accept)"),
                        ("pos", "UD POS tag (e.g. NOUN, VERB, ADJ)"),
                        ("morph", "morphology / UD features"),
                        ("head", "dependency head index (0 for root)"),
                        ("deprel", "dependency relation (e.g. nsubj, obj, root)"),
                        ("note", "reviewer note"),
                        ("evidence", "citation or textual evidence"),
                    ):
                        with Horizontal(classes="edit-row"):
                            yield Static(f"{fname}:", classes="edit-label")
                            yield Input(
                                placeholder=placeholder,
                                id=f"edit-{fname}",
                                classes="edit-input",
                            )
                    with Horizontal(id="review-edit-actions"):
                        yield Button("Apply edits", id="review-apply-edit-btn", variant="primary")
                        yield Button("Accept all (a)", id="review-accept-btn", variant="success")
                        yield Button("Defer (d)", id="review-defer-btn")
                        yield Button("Reject (x)", id="review-reject-btn", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#review-table", DataTable)
        table.add_columns("Status", "Ref", "Token", "Lemma", "Conf")
        self._sync_from_app_state()

    def on_screen_resume(self) -> None:
        self._sync_from_app_state()

    # ── loading & state sync ─────────────────────────────────────────────────

    def _sync_from_app_state(self) -> None:
        state = getattr(self.app, "state", None)
        if state is None:
            return
        paths = tuple(getattr(state, "review_paths", ()) or ())
        corpus_id = getattr(state, "selected_corpus", None)
        sig = (paths, corpus_id)
        if not paths or sig == self._loaded_signature:
            return
        self._loaded_signature = sig
        try:
            self.load_paths(paths, corpus_id=corpus_id)
        except Exception as exc:
            self.notify(f"Could not open review: {exc}", severity="error")

    def _resolve_corpus(self, corpus_id: str | None) -> "Corpus | None":
        if not corpus_id:
            return None
        from ... import load
        from ...core.corpus import Corpus

        p = Path(corpus_id)
        if p.is_file():
            if p.suffix.lower() == ".db":
                from ...db import from_sqlite

                return from_sqlite(p)
            return Corpus.from_json(p)
        return load(corpus_id)

    def load_paths(
        self,
        paths: tuple[str, ...] | list[str],
        *,
        corpus: "Corpus | None" = None,
        corpus_id: str | None = None,
        reviewer: str = "",
    ) -> None:
        """Load one review CSV, multiple CSVs to adjudicate, or a corpus id."""
        resolved_corpus = corpus or self._resolve_corpus(corpus_id)
        clean = [p.strip() for p in paths if p and p.strip()]
        if not clean:
            return
        if len(clean) == 1 and not Path(clean[0]).is_file():
            # Treat a non-file single token as a corpus id for a live review queue.
            c = self._resolve_corpus(clean[0])
            if c is None:
                raise ValueError(f"could not load corpus or review file: {clean[0]}")
            session = ReviewSession.from_corpus(c, reviewer=reviewer)
        elif len(clean) == 1:
            session = ReviewSession.from_csv(clean[0], corpus=resolved_corpus, reviewer=reviewer)
        else:
            if resolved_corpus is None:
                raise ValueError(
                    "multi-reviewer merge requires a corpus (pass --corpus <id-or-path>)"
                )
            session = ReviewSession.from_merge(clean, resolved_corpus, reviewer=reviewer)
        self.load_session(session)

    def load_session(self, session: ReviewSession) -> None:
        """Attach an already-constructed :class:`ReviewSession` and render it."""
        self.session = session
        self.filter_mode = "conflicts" if session.summary_counts()["conflicts"] > 0 else "all"
        self._selected_item_index = None
        self._refresh_all(select_first=True)
        table = self.query_one("#review-table", DataTable)
        table.focus()

    # ── rendering ────────────────────────────────────────────────────────────

    def _refresh_all(self, *, select_first: bool = False) -> None:
        self._refresh_status()
        self._refresh_table(select_first=select_first)
        self._refresh_detail()

    def _refresh_status(self) -> None:
        status = self.query_one("#review-status", Static)
        fbtn = self.query_one("#review-filter-btn", Button)
        fbtn.label = f"Filter: {self.filter_mode}"
        if self.session is None:
            status.update("Annotation review — no file loaded")
            return
        counts = self.session.summary_counts()
        src = (
            f"merge ({len(self.session.source_paths)} files)"
            if self.session.is_merge
            else self.session.source_paths[0].name
        )
        dirty = " [yellow]*unsaved[/yellow]" if self.session.dirty else ""
        conflict_txt = (
            f" · [red]{counts['conflicts']} conflicts[/red]"
            if counts["conflicts"]
            else " · 0 conflicts"
        )
        status.update(
            f"[b]{src}[/b]{dirty}  |  "
            f"resolved [green]{counts['resolved']}[/green]/{counts['total']} · "
            f"flagged {counts['flagged']}{conflict_txt}  |  "
            f"filter: [cyan]{self.filter_mode}[/cyan]"
        )

    def _refresh_table(self, *, select_first: bool = False) -> None:
        table = self.query_one("#review-table", DataTable)
        table.clear()
        if self.session is None:
            self._visible_indices = []
            self._selected_item_index = None
            return
        self._visible_indices = self.session.filtered_indices(self.filter_mode)
        for idx in self._visible_indices:
            it = self.session.items[idx]
            conf_s = f"{it.confidence:.2f}" if it.confidence is not None else "—"
            lemma_s = it.effective_value("lemma") or "—"
            table.add_row(
                it.status_tag,
                it.ref[:14],
                it.token[:16],
                lemma_s[:16],
                conf_s,
                key=str(idx),
            )
        if not self._visible_indices:
            self._selected_item_index = None
            return
        if select_first or self._selected_item_index not in self._visible_indices:
            self._selected_item_index = self._visible_indices[0]
            table.move_cursor(row=0)
        else:
            row_pos = self._visible_indices.index(self._selected_item_index)
            table.move_cursor(row=row_pos)

    def _current_item(self) -> ReviewItem | None:
        if self.session is None or self._selected_item_index is None:
            return None
        if 0 <= self._selected_item_index < len(self.session.items):
            return self.session.items[self._selected_item_index]
        return None

    def _refresh_detail(self) -> None:
        ctx_w = self.query_one("#review-context", Static)
        fld_w = self.query_one("#review-fields", Static)
        cnf_w = self.query_one("#review-conflicts", Static)
        evd_w = self.query_one("#review-evidence", Static)

        item = self._current_item()
        if item is None:
            ctx_w.update(
                _EMPTY_DETAIL
                if self.session is None
                else f"No tokens match filter [b]{self.filter_mode}[/b]. Press [b]f[/b] to cycle filters."
            )
            fld_w.update("")
            cnf_w.update("")
            evd_w.update("")
            return

        # 1. Token header & sentence context
        form_bits: list[str] = []
        if item.form_diplomatic:
            form_bits.append(f"diplomatic: {item.form_diplomatic}")
        if item.form_regularized and item.form_regularized != item.form_diplomatic:
            form_bits.append(f"regularized: {item.form_regularized}")
        if item.form_editorial_status:
            form_bits.append(f"status: {item.form_editorial_status}")
        if item.form_has_damage:
            form_bits.append("[yellow]damaged[/yellow]")
        if item.form_has_uncertainty:
            form_bits.append("[yellow]uncertain[/yellow]")
        conf_txt = f"{item.confidence:.3f}" if item.confidence is not None else "n/a"
        ctx_lines = [
            f"[b]{item.token}[/b]  [dim]({item.ref} · pos {item.position} · {item.status_tag})[/dim]",
            f"Context: {item.sentence_context or item.token}",
            f"Evidence class: {item.evidence_class or '—'} · Confidence: {conf_txt}"
            + (" · [yellow]needs review[/yellow]" if item.needs_review else ""),
        ]
        if form_bits:
            ctx_lines.append("Form: " + " · ".join(form_bits))
        ctx_w.update("\n".join(ctx_lines))

        # 2. Field comparison block
        field_lines = ["[b]Fields[/b]"]
        for fname in REVIEW_FIELD_NAMES:
            pred = item.pred.get(fname, "") or "—"
            dec = item.decisions.get(fname, "") or "open"
            corr = item.corrections.get(fname, "")
            marker = "*" if fname in item.active_fields else " "
            val_part = f" → [green]{corr}[/green]" if corr else ""
            conflict_flag = " [red][CONFLICT][/red]" if fname in item.unresolved_conflicts else ""
            field_lines.append(f" {marker} {fname:<6}  pred={pred:<18}  [{dec}]{val_part}{conflict_flag}")
        fld_w.update("\n".join(field_lines))

        # 3. Reviewer conflicts (when present)
        unresolved = item.unresolved_conflicts
        if unresolved:
            clines = ["[b][red]Reviewer disagreements[/red][/b]  (press 1 / 2 / 3 to resolve)"]
            for fname, opts in unresolved.items():
                clines.append(f"  Field [b]{fname}[/b]:")
                for i, opt in enumerate(opts, 1):
                    note_s = f" — {opt.note}" if opt.note else ""
                    clines.append(f"    [{i}] {opt.label}{note_s}")
            cnf_w.update("\n".join(clines))
        else:
            cnf_w.update("")

        # 4. Supporting lexicon & notes
        lex = ReviewSession.lexicon_summary(item.effective_value("lemma") or item.token)
        ev_lines: list[str] = []
        if lex:
            ev_lines.append(f"[b]Lexicon:[/b] {lex}")
        if item.reviewer:
            ev_lines.append(f"[b]Reviewer:[/b] {item.reviewer}")
        if item.note:
            ev_lines.append(f"[b]Note:[/b] {item.note}")
        if item.evidence:
            ev_lines.append(f"[b]Evidence:[/b] {item.evidence}")
        evd_w.update("\n".join(ev_lines))

        # 5. Populate inline edit inputs for this token
        for fname in REVIEW_FIELD_NAMES:
            inp = self.query_one(f"#edit-{fname}", Input)
            inp.value = item.effective_value(fname)
        self.query_one("#edit-note", Input).value = item.note
        self.query_one("#edit-evidence", Input).value = item.evidence

    # ── event handlers ───────────────────────────────────────────────────────

    def _in_input(self) -> bool:
        return isinstance(self.focused, Input)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None or event.row_key.value is None:
            return
        try:
            idx = int(str(event.row_key.value))
        except ValueError:
            return
        if idx != self._selected_item_index:
            self._selected_item_index = idx
            self._refresh_detail()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "review-load-btn":
            self._load_from_input()
        elif bid == "review-filter-btn":
            self.action_cycle_filter()
        elif bid == "review-save-btn":
            self.action_save()
        elif bid == "review-apply-edit-btn":
            self._commit_editor_fields()
        elif bid == "review-accept-btn":
            self._accept_current()
        elif bid == "review-defer-btn":
            self._defer_current()
        elif bid == "review-reject-btn":
            self._reject_current()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "review-open-input":
            self._load_from_input()
        elif (event.input.id or "").startswith("edit-"):
            self._commit_editor_fields()

    def _load_from_input(self) -> None:
        raw = self.query_one("#review-open-input", Input).value.strip()
        if not raw:
            return
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        corpus_id = getattr(getattr(self.app, "state", None), "selected_corpus", None)
        try:
            self.load_paths(parts, corpus_id=corpus_id)
            self.notify(f"Loaded {len(self.session.items) if self.session else 0} review rows")
        except Exception as exc:
            self.notify(f"Load failed: {exc}", severity="error")

    def _commit_editor_fields(self) -> None:
        item = self._current_item()
        if self.session is None or item is None:
            return
        idx = item.index
        changed = False
        for fname in REVIEW_FIELD_NAMES:
            val = self.query_one(f"#edit-{fname}", Input).value.strip()
            pred = item.pred.get(fname, "")
            current_eff = item.effective_value(fname)
            if val != current_eff or (val and val == pred and not item.decisions.get(fname)):
                self.session.correct_field(idx, fname, val)
                changed = True
        note_val = self.query_one("#edit-note", Input).value.strip()
        ev_val = self.query_one("#edit-evidence", Input).value.strip()
        if note_val != item.note or ev_val != item.evidence:
            self.session.set_note(idx, note_val, evidence=ev_val)
            changed = True
        self.query_one("#review-table", DataTable).focus()
        self._refresh_all()
        if changed:
            self.notify(f"Updated {item.token}")

    def _accept_current(self) -> None:
        item = self._current_item()
        if self.session is None or item is None:
            return
        accepted = self.session.accept_item(item.index)
        if not accepted:
            self.notify("No predicted fields to accept on this token", severity="warning")
            return
        nxt = self.session.next_unresolved(item.index)
        if nxt is not None:
            self._selected_item_index = nxt
        self._refresh_all()

    def _defer_current(self) -> None:
        item = self._current_item()
        if self.session is None or item is None:
            return
        self.session.defer_item(item.index)
        self._refresh_all()

    def _reject_current(self) -> None:
        item = self._current_item()
        if self.session is None or item is None:
            return
        self.session.reject_item(item.index)
        self._refresh_all()

    # ── key actions ──────────────────────────────────────────────────────────

    def action_accept(self) -> None:
        if self._in_input():
            return
        self._accept_current()

    def action_defer(self) -> None:
        if self._in_input():
            return
        self._defer_current()

    def action_reject(self) -> None:
        if self._in_input():
            return
        self._reject_current()

    def action_edit(self) -> None:
        if self._in_input() or self._current_item() is None:
            return
        self.query_one("#edit-lemma", Input).focus()

    def action_pick_option(self, option_index: int) -> None:
        if self._in_input():
            return
        item = self._current_item()
        if self.session is None or item is None:
            return
        unresolved = item.unresolved_conflicts
        if not unresolved:
            return
        fname = next(iter(unresolved))
        opts = unresolved[fname]
        if option_index >= len(opts):
            return
        chosen = self.session.pick_conflict_option(item.index, fname, option_index)
        self.notify(f"Resolved {fname} → {chosen.label}")
        if not item.has_conflicts:
            nxt = self.session.next_unresolved(item.index)
            if nxt is not None:
                self._selected_item_index = nxt
        self._refresh_all()

    def action_next_unresolved(self) -> None:
        if self._in_input() or self.session is None:
            return
        cur = self._selected_item_index if self._selected_item_index is not None else -1
        nxt = self.session.next_unresolved(cur)
        if nxt is not None:
            self._selected_item_index = nxt
            if nxt not in self._visible_indices:
                self.filter_mode = "all"
            self._refresh_all()

    def action_prev_unresolved(self) -> None:
        if self._in_input() or self.session is None:
            return
        cur = self._selected_item_index if self._selected_item_index is not None else 0
        prv = self.session.prev_unresolved(cur)
        if prv is not None:
            self._selected_item_index = prv
            if prv not in self._visible_indices:
                self.filter_mode = "all"
            self._refresh_all()

    def action_cycle_filter(self) -> None:
        if self._in_input():
            return
        idx = FILTER_MODES.index(self.filter_mode)
        self.filter_mode = FILTER_MODES[(idx + 1) % len(FILTER_MODES)]
        self._refresh_all(select_first=True)

    def action_save(self) -> None:
        if self._in_input() or self.session is None:
            return
        try:
            saved = self.session.save()
            self._refresh_status()
            self.notify(f"Saved review table to {saved}")
        except Exception as exc:
            self.notify(f"Save failed: {exc}", severity="error")

    def action_focus_open(self) -> None:
        if self._in_input():
            return
        self.query_one("#review-open-input", Input).focus()
