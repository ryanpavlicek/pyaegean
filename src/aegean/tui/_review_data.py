"""Headless session model for interactive annotation and conflict review in the TUI.

Loads a single review CSV (``full`` or ``editable`` + ``.companion.json``), a
multi-reviewer conflict merge (via :func:`aegean.io.review.merge_review_tables`),
or a live corpus review queue (via :func:`aegean.io.review.to_review_table`),
tracks field-level decisions, surfaces sentence context and offline lexicon
evidence, and saves back cleanly without mutating immutable snapshot columns.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .._atomic import atomic_path
from ..io.review import (
    EDITABLE_REVIEW_COLUMNS,
    REVIEW_COLUMNS,
    ReviewerValue,
    _cell,
    _check_review_header,
    _exact_cell,
    _guard_cell,
    _load_companion_rows,
    _rehydrate_editable_row,
    _row_position,
    _write_review_rows,
    from_review_table,
    merge_review_tables,
    review_companion_path,
    to_review_table,
)

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = [
    "FILTER_MODES",
    "REVIEW_FIELD_NAMES",
    "ConflictOption",
    "ReviewItem",
    "ReviewSession",
]

REVIEW_FIELD_NAMES: tuple[str, ...] = ("lemma", "pos", "morph", "head", "deprel")
FILTER_MODES: tuple[str, ...] = ("all", "unresolved", "conflicts", "flagged")


@dataclass(frozen=True, slots=True)
class ConflictOption:
    """One reviewer's proposed action and value for a conflicted field."""

    reviewer: str
    action: str
    value: str
    note: str = ""
    evidence: str = ""

    @property
    def label(self) -> str:
        if self.action == "correct":
            return f"{self.reviewer}: {self.value}"
        if self.value:
            return f"{self.reviewer}: {self.action} ({self.value})"
        return f"{self.reviewer}: {self.action}"


@dataclass(slots=True)
class ReviewItem:
    """One reviewable token row inside a :class:`ReviewSession`."""

    index: int
    row_id: str
    doc_id: str
    position: int | None
    line_no: str
    ref: str
    token: str
    dependency_sentence_id: str
    dependency_index: str
    form_diplomatic: str
    form_regularized: str
    form_editorial_status: str
    form_has_damage: bool
    form_has_uncertainty: bool
    needs_review: bool
    evidence_class: str
    confidence: float | None
    review_fields: tuple[str, ...]
    inclusion_reasons: tuple[str, ...]
    pred: dict[str, str]
    decisions: dict[str, str]
    corrections: dict[str, str]
    reviewer: str = ""
    note: str = ""
    evidence: str = ""
    sentence_context: str = ""
    conflicts: dict[str, tuple[ConflictOption, ...]] = field(default_factory=dict)
    raw_row: dict[str, str] = field(default_factory=dict)
    edited: bool = False

    @property
    def active_fields(self) -> tuple[str, ...]:
        fields = [f for f in self.review_fields if f in REVIEW_FIELD_NAMES]
        if fields:
            return tuple(fields)
        present = [f for f in REVIEW_FIELD_NAMES if self.pred.get(f) or f in self.conflicts]
        return tuple(present) if present else ("lemma",)

    @property
    def unresolved_conflicts(self) -> dict[str, tuple[ConflictOption, ...]]:
        return {
            fname: opts
            for fname, opts in self.conflicts.items()
            if not self.decisions.get(fname) and not self.corrections.get(fname)
        }

    @property
    def has_conflicts(self) -> bool:
        return bool(self.unresolved_conflicts)

    @property
    def is_resolved(self) -> bool:
        if self.has_conflicts:
            return False
        targets = self.active_fields
        # A token is considered resolved once at least one decision/correction is made
        # for every active field that carries a prediction (or any field if none predicted).
        decidable = [f for f in targets if self.pred.get(f) or f in self.conflicts]
        if not decidable:
            decidable = list(targets[:1])
        return all(
            bool(self.decisions.get(f) or self.corrections.get(f))
            for f in decidable
        )

    @property
    def status_tag(self) -> str:
        if self.has_conflicts:
            return "CONFLICT"
        if any(self.decisions.get(f) == "defer" for f in self.active_fields):
            return "DEFER"
        if self.is_resolved:
            return "DONE"
        if self.needs_review:
            return "FLAG"
        return "OPEN"

    def effective_value(self, fname: str) -> str:
        if self.corrections.get(fname):
            return self.corrections[fname]
        return self.pred.get(fname, "")


def _parse_json_list(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ()
    if isinstance(parsed, list):
        return tuple(str(x) for x in parsed if isinstance(x, str))
    return ()


def _parse_confidence(
    inclusion_reasons: Sequence[str],
    annotations: dict[str, str] | None = None,
    fields: Sequence[str] = REVIEW_FIELD_NAMES,
) -> float | None:
    for reason in inclusion_reasons:
        if reason.startswith("calibrated_confidence:"):
            raw = reason.split(":", 1)[1].strip()
            try:
                val = float(raw)
                if 0.0 <= val <= 1.0:
                    return val
            except ValueError:
                pass
    if annotations:
        vals: list[float] = []
        for f in fields:
            raw = annotations.get(f"confidence_{f}", "")
            if raw:
                try:
                    val = float(raw)
                    if 0.0 <= val <= 1.0:
                        vals.append(val)
                except ValueError:
                    pass
        if vals:
            return min(vals)
    return None


def _build_corpus_token_map(corpus: "Corpus | None") -> dict[tuple[str, int], tuple[str, dict[str, str]]]:
    """Map ``(doc_id, position)`` to ``(highlighted_context, token.annotations)``."""
    if corpus is None:
        return {}
    out: dict[tuple[str, int], tuple[str, dict[str, str]]] = {}
    for doc in corpus.documents:
        toks = doc.tokens
        for idx, tok in enumerate(toks):
            if tok.position is None:
                continue
            lo = max(0, idx - 6)
            hi = min(len(toks), idx + 7)
            parts = []
            for j in range(lo, hi):
                text = toks[j].text
                parts.append(f"[{text}]" if j == idx else text)
            prefix = "… " if lo > 0 else ""
            suffix = " …" if hi < len(toks) else ""
            out[(doc.id, tok.position)] = (f"{prefix}{' '.join(parts)}{suffix}", dict(tok.annotations))
    return out


def _attach_row_contexts(items: list[ReviewItem]) -> None:
    """Fill missing ``sentence_context`` from neighboring rows in the same document."""
    by_doc: dict[str, list[ReviewItem]] = {}
    for it in items:
        by_doc.setdefault(it.doc_id, []).append(it)
    for doc_items in by_doc.values():
        for i, it in enumerate(doc_items):
            if it.sentence_context:
                continue
            lo = max(0, i - 5)
            hi = min(len(doc_items), i + 6)
            parts = [
                f"[{doc_items[j].token}]" if j == i else doc_items[j].token
                for j in range(lo, hi)
            ]
            prefix = "… " if lo > 0 else ""
            suffix = " …" if hi < len(doc_items) else ""
            it.sentence_context = f"{prefix}{' '.join(parts)}{suffix}"


def _item_from_row(
    idx: int,
    row: dict[str, str],
    *,
    row_id: str,
    corpus_map: dict[tuple[str, int], tuple[str, dict[str, str]]],
    conflicts: dict[str, tuple[ConflictOption, ...]] | None = None,
) -> ReviewItem:
    doc_id = _exact_cell(row, "doc_id")
    pos = _row_position(_cell(row, "position"))
    review_fields = _parse_json_list(_exact_cell(row, "review_fields")) or ("lemma",)
    inclusion_reasons = _parse_json_list(_exact_cell(row, "inclusion_reasons"))

    corpus_ctx, corpus_ann = corpus_map.get((doc_id, pos), ("", {})) if pos is not None else ("", {})
    dep_ctx = _exact_cell(row, "dependency_sentence_context")
    sentence_context = dep_ctx or corpus_ctx

    pred = {f: _exact_cell(row, f"pred_{f}") for f in REVIEW_FIELD_NAMES}
    decisions = {f: _cell(row, f"decision_{f}").lower() for f in REVIEW_FIELD_NAMES}
    corrections = {f: _cell(row, f"correct_{f}") for f in REVIEW_FIELD_NAMES}

    # Backfill implicit correction action for legacy correction-only rows
    for f in REVIEW_FIELD_NAMES:
        if corrections[f] and not decisions[f]:
            decisions[f] = "correct"

    conf = _parse_confidence(inclusion_reasons, corpus_ann, review_fields)

    return ReviewItem(
        index=idx,
        row_id=row_id,
        doc_id=doc_id,
        position=pos,
        line_no=_cell(row, "line_no"),
        ref=_cell(row, "ref") or doc_id,
        token=_exact_cell(row, "token"),
        dependency_sentence_id=_exact_cell(row, "dependency_sentence_id"),
        dependency_index=_cell(row, "dependency_index"),
        form_diplomatic=_exact_cell(row, "form_diplomatic"),
        form_regularized=_exact_cell(row, "form_regularized"),
        form_editorial_status=_exact_cell(row, "form_editorial_status"),
        form_has_damage=_cell(row, "form_has_damage").lower() == "true",
        form_has_uncertainty=_cell(row, "form_has_uncertainty").lower() == "true",
        needs_review=_cell(row, "needs_review").lower() in ("yes", "true", "1"),
        evidence_class=_exact_cell(row, "evidence_class"),
        confidence=conf,
        review_fields=review_fields,
        inclusion_reasons=inclusion_reasons,
        pred=pred,
        decisions=decisions,
        corrections=corrections,
        reviewer=_cell(row, "reviewer"),
        note=_cell(row, "reviewer_note"),
        evidence=_cell(row, "reviewer_evidence"),
        sentence_context=sentence_context,
        conflicts=dict(conflicts) if conflicts else {},
        raw_row=dict(row),
    )


class ReviewSession:
    """In-memory review and conflict-adjudication session backed by review CSVs."""

    def __init__(
        self,
        items: list[ReviewItem],
        *,
        source_paths: tuple[Path, ...],
        layout: Literal["full", "editable"] = "full",
        corpus: "Corpus | None" = None,
        reviewer: str = "",
        is_merge: bool = False,
        editable_fieldnames: tuple[str, ...] = EDITABLE_REVIEW_COLUMNS,
    ) -> None:
        self.items = items
        self.source_paths = source_paths
        self.layout: Literal["full", "editable"] = layout
        self.corpus = corpus
        self.default_reviewer = reviewer
        self.is_merge = is_merge
        self._editable_fieldnames = editable_fieldnames
        self.dirty = False

    # ── constructors ─────────────────────────────────────────────────────────

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        corpus: "Corpus | None" = None,
        reviewer: str = "",
    ) -> "ReviewSession":
        csv_path = Path(path)
        corpus_map = _build_corpus_token_map(corpus)
        items: list[ReviewItem] = []
        layout: Literal["full", "editable"] = "full"
        editable_fieldnames: tuple[str, ...] = EDITABLE_REVIEW_COLUMNS

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, strict=True)
            _check_review_header(csv_path, reader.fieldnames)
            fieldnames = list(reader.fieldnames or ())
            fset = set(fieldnames)
            is_editable = "row_id" in fset and "review_snapshot" not in fset
            companion_rows = _load_companion_rows(csv_path) if is_editable else None
            if is_editable:
                layout = "editable"
                editable_fieldnames = tuple(fieldnames)
            for idx, raw_row in enumerate(reader):
                if None in raw_row or any(v is None for v in raw_row.values()):
                    raise ValueError(f"malformed review CSV {csv_path}: row {idx + 1} does not match header")
                row_id = _cell(raw_row, "row_id") if is_editable else ""
                full_row_any = (
                    _rehydrate_editable_row(csv_path, raw_row, companion_rows)
                    if companion_rows is not None
                    else raw_row
                )
                full_row = {k: str(v or "") for k, v in full_row_any.items()}
                if not row_id:
                    row_id = (
                        _exact_cell(full_row, "alignment_source_token_id")
                        or f"{_exact_cell(full_row, 'doc_id')}#{_cell(full_row, 'position')}"
                    )
                items.append(_item_from_row(idx, full_row, row_id=row_id, corpus_map=corpus_map))

        _attach_row_contexts(items)
        inferred_reviewer = reviewer
        if not inferred_reviewer:
            names = sorted({it.reviewer for it in items if it.reviewer})
            if len(names) == 1:
                inferred_reviewer = names[0]
        return cls(
            items,
            source_paths=(csv_path,),
            layout=layout,
            corpus=corpus,
            reviewer=inferred_reviewer,
            is_merge=False,
            editable_fieldnames=editable_fieldnames,
        )

    @classmethod
    def from_merge(
        cls,
        paths: Sequence[str | Path],
        corpus: "Corpus",
        *,
        reviewer: str = "",
    ) -> "ReviewSession":
        path_tuple = tuple(Path(p) for p in paths)
        merged = merge_review_tables(path_tuple, corpus, on_conflict="report")
        corpus_map = _build_corpus_token_map(corpus)

        # Index conflicts by (doc_id, position) -> field -> ConflictOption tuple
        conflict_map: dict[tuple[str, int], dict[str, tuple[ConflictOption, ...]]] = {}
        for conflict in merged.conflicts:
            key = (conflict.doc_id, conflict.position)
            opts = tuple(
                ConflictOption(
                    reviewer=opt.reviewer,
                    action=opt.action,
                    value=opt.value,
                    note=opt.note,
                    evidence=opt.evidence,
                )
                for opt in conflict.options
                if isinstance(opt, ReviewerValue)
            )
            conflict_map.setdefault(key, {})[conflict.field] = opts

        # Gather complete baseline rows from the first file so conflicted rows
        # without any clean fields are still surfaced in the adjudication queue.
        first_session = cls.from_csv(path_tuple[0], corpus=corpus, reviewer=reviewer)
        base_by_key: dict[tuple[str, int], dict[str, str]] = {}
        ordered_keys: list[tuple[str, int]] = []
        for it in first_session.items:
            if it.position is not None:
                k = (it.doc_id, it.position)
                base_by_key[k] = dict(it.raw_row)
                ordered_keys.append(k)

        merged_by_key: dict[tuple[str, int], dict[str, str]] = {}
        for mrow in merged.rows:
            pos = _row_position(_cell(mrow, "position"))
            if pos is not None:
                k = (_exact_cell(mrow, "doc_id"), pos)
                merged_by_key[k] = dict(mrow)
                if k not in base_by_key:
                    base_by_key[k] = dict(mrow)
                    ordered_keys.append(k)

        items: list[ReviewItem] = []
        for idx, key in enumerate(ordered_keys):
            row = merged_by_key.get(key)
            if row is None:
                # Start with clean mutable fields for rows that only had conflicts
                row = {col: _exact_cell(base_by_key[key], col) for col in REVIEW_COLUMNS}
                for f in REVIEW_FIELD_NAMES:
                    row[f"decision_{f}"] = ""
                    row[f"correct_{f}"] = ""
                row["reviewer"] = ""
                row["reviewer_note"] = ""
                row["reviewer_evidence"] = ""
                row["reviewer_records"] = ""
            row_id = (
                _exact_cell(row, "alignment_source_token_id")
                or f"{key[0]}#{key[1]}"
            )
            items.append(
                _item_from_row(
                    idx,
                    row,
                    row_id=row_id,
                    corpus_map=corpus_map,
                    conflicts=conflict_map.get(key),
                )
            )

        _attach_row_contexts(items)
        return cls(
            items,
            source_paths=path_tuple,
            layout="full",
            corpus=corpus,
            reviewer=reviewer or "adjudicator",
            is_merge=True,
        )

    @classmethod
    def from_corpus(
        cls,
        corpus: "Corpus",
        *,
        save_path: str | Path | None = None,
        selection: Literal["all", "flagged", "unverified", "sample"] = "all",
        fields: Sequence[str] = ("lemma", "pos", "morph"),
        priority: Literal["auto", "document", "calibrated_risk"] = "auto",
        budget: int | None = None,
        reviewer: str = "",
    ) -> "ReviewSession":
        if save_path is None:
            tmp_dir = Path(tempfile.mkdtemp(prefix="aegean-review-"))
            target = tmp_dir / "review.csv"
        else:
            target = Path(save_path)
            target.parent.mkdir(parents=True, exist_ok=True)

        chosen_priority: Literal["document", "calibrated_risk"] = "document"
        if priority == "calibrated_risk":
            chosen_priority = "calibrated_risk"
        elif priority == "auto":
            has_cal = any(
                any(f"confidence_{f}" in tok.annotations for f in fields)
                for doc in corpus.documents
                for tok in doc.tokens
            )
            chosen_priority = "calibrated_risk" if has_cal else "document"

        effective_budget = budget if chosen_priority == "calibrated_risk" else None
        to_review_table(
            corpus,
            target,
            selection=selection,
            reviewer=reviewer,
            fields=fields,
            layout="editable",
            priority=chosen_priority,
            budget=effective_budget,
        )
        return cls.from_csv(target, corpus=corpus, reviewer=reviewer)

    # ── queries & navigation ─────────────────────────────────────────────────

    def summary_counts(self) -> dict[str, int]:
        total = len(self.items)
        resolved = sum(1 for it in self.items if it.is_resolved)
        conflicts = sum(1 for it in self.items if it.has_conflicts)
        flagged = sum(1 for it in self.items if it.needs_review)
        return {
            "total": total,
            "resolved": resolved,
            "unresolved": total - resolved,
            "conflicts": conflicts,
            "flagged": flagged,
        }

    def filtered_indices(self, mode: str = "all") -> list[int]:
        if mode == "unresolved":
            return [it.index for it in self.items if not it.is_resolved]
        if mode == "conflicts":
            return [it.index for it in self.items if it.has_conflicts]
        if mode == "flagged":
            return [it.index for it in self.items if it.needs_review]
        return [it.index for it in self.items]

    def next_unresolved(self, current_index: int) -> int | None:
        n = len(self.items)
        if n == 0:
            return None
        for offset in range(1, n + 1):
            idx = (current_index + offset) % n
            if not self.items[idx].is_resolved:
                return idx
        return None

    def prev_unresolved(self, current_index: int) -> int | None:
        n = len(self.items)
        if n == 0:
            return None
        for offset in range(1, n + 1):
            idx = (current_index - offset) % n
            if not self.items[idx].is_resolved:
                return idx
        return None

    # ── mutations ────────────────────────────────────────────────────────────

    def _stamp_reviewer(self, item: ReviewItem, reviewer: str | None) -> None:
        who = (reviewer or self.default_reviewer or item.reviewer).strip()
        if who:
            item.reviewer = who
        item.edited = True
        self.dirty = True

    def accept_item(
        self,
        index: int,
        *,
        field_name: str | None = None,
        reviewer: str | None = None,
    ) -> list[str]:
        """Accept machine predictions for ``field_name`` or all predicted active fields."""
        item = self.items[index]
        targets = (field_name,) if field_name else item.active_fields
        accepted: list[str] = []
        for fname in targets:
            if fname not in REVIEW_FIELD_NAMES:
                continue
            if item.pred.get(fname, "").strip():
                item.decisions[fname] = "accept"
                item.corrections[fname] = ""
                accepted.append(fname)
        if accepted:
            self._stamp_reviewer(item, reviewer)
        return accepted

    def defer_item(
        self,
        index: int,
        *,
        field_name: str | None = None,
        reviewer: str | None = None,
    ) -> None:
        item = self.items[index]
        targets = (field_name,) if field_name else item.active_fields
        for fname in targets:
            if fname in REVIEW_FIELD_NAMES:
                item.decisions[fname] = "defer"
                item.corrections[fname] = ""
        self._stamp_reviewer(item, reviewer)

    def reject_item(
        self,
        index: int,
        *,
        field_name: str | None = None,
        reviewer: str | None = None,
    ) -> None:
        item = self.items[index]
        targets = (field_name,) if field_name else item.active_fields
        for fname in targets:
            if fname in REVIEW_FIELD_NAMES:
                item.decisions[fname] = "reject"
                item.corrections[fname] = ""
        self._stamp_reviewer(item, reviewer)

    def correct_field(
        self,
        index: int,
        field_name: str,
        value: str,
        *,
        note: str | None = None,
        evidence: str | None = None,
        reviewer: str | None = None,
    ) -> str:
        """Set a field correction (auto-converting identical values to ``accept``)."""
        if field_name not in REVIEW_FIELD_NAMES:
            raise ValueError(f"unknown review field: {field_name!r}")
        item = self.items[index]
        cleaned = value.strip()
        predicted = item.pred.get(field_name, "")
        if not cleaned:
            item.decisions[field_name] = ""
            item.corrections[field_name] = ""
            action = "cleared"
        elif cleaned == predicted:
            item.decisions[field_name] = "accept"
            item.corrections[field_name] = ""
            action = "accept"
        else:
            item.decisions[field_name] = "correct"
            item.corrections[field_name] = cleaned
            action = "correct"
        if note is not None:
            item.note = note.strip()
        if evidence is not None:
            item.evidence = evidence.strip()
        self._stamp_reviewer(item, reviewer)
        return action

    def pick_conflict_option(
        self,
        index: int,
        field_name: str,
        option_index: int,
        *,
        reviewer: str | None = None,
    ) -> ConflictOption:
        """Resolve one field conflict by picking ``option_index`` (0-based)."""
        item = self.items[index]
        options = item.conflicts.get(field_name)
        if not options or not (0 <= option_index < len(options)):
            raise IndexError(f"invalid conflict option {option_index} for {field_name}")
        opt = options[option_index]
        if opt.action == "correct":
            self.correct_field(index, field_name, opt.value, reviewer=reviewer)
        elif opt.action == "accept":
            self.accept_item(index, field_name=field_name, reviewer=reviewer)
        elif opt.action == "defer":
            self.defer_item(index, field_name=field_name, reviewer=reviewer)
        elif opt.action == "reject":
            self.reject_item(index, field_name=field_name, reviewer=reviewer)
        else:
            self.correct_field(index, field_name, opt.value, reviewer=reviewer)
        if opt.note and opt.note not in item.note:
            item.note = f"{item.note}; {opt.note}".lstrip("; ") if item.note else opt.note
        if opt.evidence and opt.evidence not in item.evidence:
            item.evidence = (
                f"{item.evidence}; {opt.evidence}".lstrip("; ")
                if item.evidence
                else opt.evidence
            )
        return opt

    def set_note(
        self,
        index: int,
        note: str,
        *,
        evidence: str | None = None,
        reviewer: str | None = None,
    ) -> None:
        item = self.items[index]
        item.note = note.strip()
        if evidence is not None:
            item.evidence = evidence.strip()
        self._stamp_reviewer(item, reviewer)

    # ── lexicon evidence ─────────────────────────────────────────────────────

    @staticmethod
    def lexicon_summary(query: str) -> str:
        """Best-effort offline Greek lexicon lookup for review evidence."""
        term = query.strip()
        if not term:
            return ""
        try:
            from ..greek import lexicons as reg

            if reg.active_lexica():
                found = reg.gloss(term)
                if found:
                    return found
        except Exception:
            pass
        try:
            from ..greek import koine

            dodson = koine.use_dodson()
            entry = dodson.lookup(term)
            if entry is None:
                return ""
            parts = [entry.lemma]
            if entry.gloss:
                parts.append(f"— {entry.gloss}")
            if entry.strongs:
                parts.append(f"({entry.strongs})")
            return " ".join(parts)
        except Exception:
            return ""

    # ── persistence & corpus apply ───────────────────────────────────────────

    def _updated_full_row(self, item: ReviewItem) -> dict[str, str]:
        row = {col: _exact_cell(item.raw_row, col) for col in REVIEW_COLUMNS}
        for f in REVIEW_FIELD_NAMES:
            row[f"decision_{f}"] = item.decisions.get(f, "")
            row[f"correct_{f}"] = item.corrections.get(f, "")
        row["reviewer"] = item.reviewer
        row["reviewer_note"] = item.note
        row["reviewer_evidence"] = item.evidence
        # If the user edited a merged row, clear stale reviewer_records JSON so
        # `_field_reviewers` attributes the updated single reviewer cleanly.
        if item.edited:
            row["reviewer_records"] = ""
        return row

    def save(self, path: str | Path | None = None) -> Path:
        """Write review decisions back to disk, preserving immutable snapshots."""
        target = Path(path) if path is not None else self.source_paths[0]
        target.parent.mkdir(parents=True, exist_ok=True)

        if self.layout == "editable" and not self.is_merge:
            src_companion = review_companion_path(self.source_paths[0])
            dst_companion = review_companion_path(target)
            if src_companion.resolve() != dst_companion.resolve() and src_companion.is_file():
                shutil.copy2(src_companion, dst_companion)

            cols = self._editable_fieldnames
            with atomic_path(target) as tmp:
                with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(cols)
                    for item in self.items:
                        full = self._updated_full_row(item)
                        cells = [
                            _guard_cell(item.row_id if col == "row_id" else full.get(col, ""))
                            for col in cols
                        ]
                        writer.writerow(cells)
        else:
            rows = [self._updated_full_row(item) for item in self.items]
            _write_review_rows(target, rows)

        self.dirty = False
        return target

    def apply_to_corpus(
        self,
        corpus: "Corpus | None" = None,
        *,
        output_path: str | Path | None = None,
    ) -> tuple["Corpus", int]:
        """Validate and apply all review decisions to ``corpus`` via `from_review_table`."""
        target_corpus = corpus or self.corpus
        if target_corpus is None:
            raise ValueError("no corpus attached to this review session")
        with tempfile.TemporaryDirectory(prefix="aegean-apply-") as td:
            tmp_csv = Path(td) / "review.csv"
            self.save(tmp_csv)
            updated = from_review_table(tmp_csv, target_corpus)
        if output_path is not None:
            updated.to_json(output_path)
        self.corpus = updated
        applied_count = sum(1 for it in self.items if it.is_resolved)
        return updated, applied_count
