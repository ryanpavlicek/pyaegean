"""Optional field-level scholarly review: predictions out, decisions and corrections back.

Automated analysis does not end the workflow. This module exports a corpus's per-token
annotations to a plain CSV a scholar can open in a spreadsheet, correct, and hand back:
`to_review_table` writes one reviewable row per word (the machine's lemma / POS / morphology,
its evidence class and a "needs review" flag, and blank columns for field decisions,
corrections, notes, and evidence); `from_review_table` reads them back onto the corpus,
keeping the machine's value under a ``<field>__pred`` key and stamping who reviewed it and a
provenance note. A lemma correction also becomes ``lemma_source=user`` and
``lemma_verified=true`` while preserving the predicted source. The join key is
the stable ``alignment_source_token_id`` when present, with ``doc_id`` +
``position`` retained for pre-A4 tables.

Several reviewers can correct their own copy of the SAME export and have the corrections
combined: `merge_review_tables` merges the copies, applying every correction the reviewers
agree on (or that only one made) and surfacing every genuine disagreement as a `ReviewConflict`
rather than silently picking a winner; `apply_merged` lands the agreed subset onto the corpus,
stamping all contributing reviewers. Reviewer identity travels in the ``reviewer`` column.

Zero-dependency: CSV via the stdlib ``csv`` module, written with a UTF-8 BOM so a spreadsheet
opens the Greek correctly. The corpus is rebuilt immutably (``dataclasses.replace``); nothing
is edited in place. The predictions come from an existing corpus's ``Token.annotations`` (for
the New Testament, the gold lemma/morph/Strong's are already there; for other corpora, run
`aegean.greek.annotate.annotate_corpus` first to fill them)."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from .._atomic import atomic_path

if TYPE_CHECKING:
    from ..core.corpus import Corpus
    from ..core.model import Token

__all__ = [
    "REVIEW_COLUMNS",
    "MergedReview",
    "ReviewApplication",
    "ReviewConflict",
    "ReviewerValue",
    "apply_merged",
    "apply_review_table",
    "from_review_table",
    "merge_review_tables",
    "needs_review_flag",
    "to_review_table",
]

# The columns of a review table. The first block is read-only context + prediction + triage;
# the reviewer fills ``decision_*`` (accept/correct/defer/reject), ``correct_*``, and notes.
# Blank decisions retain the historical correction-only contract: blanks never verify.
# Identity is recorded in ``reviewer`` (used when several copies are merged; blank = anonymous,
# in which case the merge falls back to the file name).
REVIEW_COLUMNS: tuple[str, ...] = (
    "doc_id", "position", "line_no", "ref", "token",       # identity / join key (read-only)
    "alignment_document_id", "alignment_sentence_id", "alignment_source_token_id",
    "alignment_original_text",
    "alignment_start_char", "alignment_end_char", "alignment_whitespace_before",
    "alignment_normalized_text", "alignment_normalization_ops",
    "form_diplomatic", "form_regularized", "form_normalized", "form_model_input",
    "form_model_input_source", "form_model_input_ops", "form_segments",
    "form_editorial_status", "form_supplied_text", "form_unclear_text", "form_lost_text",
    "form_supplied", "form_unclear", "form_lost", "form_has_damage",
    "form_has_uncertainty", "form_state_json",
    "pred_lemma", "pred_pos", "pred_morph",                # machine prediction (read-only)
    "evidence_class", "source_citation", "needs_review",   # provenance + triage (read-only)
    "correct_lemma", "correct_pos", "correct_morph",       # reviewer fills
    "reviewer_note", "reviewer",                            # reviewer fills
    "decision_lemma", "decision_pos", "decision_morph",    # reviewer fills; blank = no decision
    "reviewer_evidence",                                   # reviewer fills; citation / link
    "reviewer_records",                                    # merge attribution (JSON; read-only)
)

FORM_STATE_COLUMNS: tuple[str, ...] = (
    "form_diplomatic", "form_regularized", "form_normalized", "form_model_input",
    "form_model_input_source", "form_model_input_ops", "form_segments",
    "form_editorial_status", "form_supplied_text", "form_unclear_text", "form_lost_text",
    "form_supplied", "form_unclear", "form_lost", "form_has_damage",
    "form_has_uncertainty", "form_state_json",
)


def _low_confidence() -> frozenset[str]:
    """Lemma fallback classes selected by the canonical
    predicate (`aegean.greek.needs_review`) so the two can never drift apart. Imported
    lazily to keep ``import aegean.io`` free of the greek package."""
    from ..greek.lemmatize import LemmaSource, needs_review

    return frozenset(s.value for s in LemmaSource if needs_review(s))


def needs_review_flag(annotations: dict[str, str], *, source_key: str = "lemma_source") -> bool:
    """Read the review flag, with fallbacks for older annotation records.

    Prefer the explicit ``review_recommended`` annotation. Otherwise infer it from
    the lemma source (``identity`` / ``unresolved``), then the legacy
    ``lemma_known=false`` signal when no source is present. A token carrying none
    of these signals is not flagged. False does not certify correctness, and no
    confidence threshold or POS/dependency error check is applied.
    """
    explicit = annotations.get("review_recommended")
    if explicit is not None and explicit.lower() in ("true", "false"):
        return explicit.lower() == "true"
    src = annotations.get(source_key)
    if src is not None:
        return src in _low_confidence()
    return annotations.get("lemma_known", "").lower() == "false"


# A cell beginning with one of these becomes a live formula when the CSV is opened in a
# spreadsheet (CSV formula injection) — and a spreadsheet is exactly where a review table
# goes. Guarded cells get the standard leading-apostrophe neutralization on write, and the
# apostrophe is stripped again on read so the round-trip is clean.
_FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")


def _guard_cell(value: str) -> str:
    return "'" + value if value.startswith(_FORMULA_LEADERS) else value


def _unguard_cell(value: str) -> str:
    return value[1:] if value.startswith("'") and value[1:].startswith(_FORMULA_LEADERS) else value


def _morph(annotations: dict[str, str]) -> str:
    """The token's morphology annotation: the corpus ``morph`` (NT Robinson) or UD ``feats``."""
    return annotations.get("morph") or annotations.get("feats") or ""


def to_review_table(
    corpus: "Corpus",
    path: str | Path,
    *,
    source_key: str = "lemma_source",
    selection: Literal["all", "flagged", "unverified"] = "all",
    reviewer: str = "",
) -> int:
    """Write one reviewable row per WORD token of ``corpus`` to ``path`` (CSV, UTF-8 BOM).

    Each row carries the token's identity (stable source-token ID plus
    ``doc_id``/``position``/``line_no``/``ref``), exact source span and normalization,
    existing ``pred_lemma``/``pred_pos``/``pred_morph`` values from its annotations, the
    ``evidence_class`` and a ``needs_review`` flag, the corpus citation, and blank
    ``decision_*`` / ``correct_*`` / ``reviewer_note`` / ``reviewer_evidence`` columns.
    Decisions are per field: accept, correct, defer, or reject; blank is no decision.
    ``selection="all"``
    exports every eligible word; ``"flagged"`` exports only rows selected by
    `needs_review_flag`; ``"unverified"`` exports words without an explicit
    ``lemma_verified`` string equal to ``true`` (case-insensitive); all other values
    remain included. Verification is not inferred from the lemma source or review
    metadata. These scopes use no confidence threshold;
    excluded rows can still contain errors. Existing source annotations can be exported
    without generating predictions.
    Pass ``reviewer`` to pre-stamp every row's ``reviewer``
    column (hand a named copy to each reviewer when the corrected copies will be merged with
    `merge_review_tables`); it is left blank by default. Returns the number of rows written.

    A token without a ``position`` is not exported: the apply join key is
    ``doc_id`` + ``position``, so a correction on such a row could never be applied. Cells
    that would open as a live formula in a spreadsheet are neutralized with a leading
    apostrophe (stripped again by `from_review_table`)."""
    if selection not in ("all", "flagged", "unverified"):
        raise ValueError("selection must be 'all', 'flagged', or 'unverified'")

    from ..core.model import TokenKind
    from .._view import _form_state_fields

    prov = corpus.provenance
    citation = (prov.citation or prov.source) if prov is not None else ""
    rows: list[list[str]] = []
    for doc in corpus.documents:
        ref_base = doc.id
        for tok in doc.tokens:
            if tok.kind is not TokenKind.WORD:
                continue
            if tok.position is None:
                continue  # no join key: a correction here could never round-trip
            a = tok.annotations
            flag = needs_review_flag(a, source_key=source_key)
            if selection == "flagged" and not flag:
                continue
            if selection == "unverified":
                verified = a.get("lemma_verified")
                if isinstance(verified, str) and verified.lower() == "true":
                    continue
            form_fields = _form_state_fields(tok.form_state)
            form_fields["form_state_json"] = (
                json.dumps(
                    tok.form_state.to_dict(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if tok.form_state is not None
                else None
            )
            form_cells = _review_form_state_cells(form_fields)
            rows.append([
                doc.id,
                str(tok.position),
                str(tok.line_no if tok.line_no is not None else ""),
                _guard_cell(a.get("ref", ref_base)),
                _guard_cell(tok.text),
                _guard_cell(tok.alignment.document_id if tok.alignment is not None else ""),
                _guard_cell(tok.alignment.sentence_id or "" if tok.alignment is not None else ""),
                _guard_cell(tok.alignment.source_token_id if tok.alignment is not None else ""),
                _guard_cell(tok.alignment.original_text if tok.alignment is not None else ""),
                str(tok.alignment.start_char if tok.alignment is not None else ""),
                str(tok.alignment.end_char if tok.alignment is not None else ""),
                _guard_cell(tok.alignment.whitespace_before if tok.alignment is not None else ""),
                _guard_cell(tok.alignment.normalized_text if tok.alignment is not None else ""),
                _guard_cell(
                    json.dumps(
                        list(tok.alignment.normalization_ops),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    if tok.alignment is not None
                    else ""
                ),
                *(_guard_cell(form_cells[col]) for col in FORM_STATE_COLUMNS),
                _guard_cell(a.get("lemma", "")),
                _guard_cell(a.get("upos", "")),
                _guard_cell(_morph(a)),
                a.get(source_key, ""),
                _guard_cell(citation),
                "yes" if flag else "",
                "", "", "", "",  # correct_lemma, correct_pos, correct_morph, reviewer_note
                _guard_cell(reviewer),
                "", "", "", "", "",  # field decisions, evidence, merge attribution
            ])
    _write_review_rows(path, [dict(zip(REVIEW_COLUMNS, r)) for r in rows], _preguarded=True)
    return len(rows)


# (review-table correction column -> its prediction column -> default annotation key)
_CORRECTIONS: tuple[tuple[str, str, str], ...] = (
    ("correct_lemma", "pred_lemma", "lemma"),
    ("correct_pos", "pred_pos", "upos"),
    ("correct_morph", "pred_morph", "morph"),
)

_ACTIONS = frozenset({"accept", "correct", "defer", "reject"})
_DECISION_COLUMNS = tuple("decision_" + col.removeprefix("correct_") for col, _, _ in _CORRECTIONS)


def _field_decision(row: Mapping[str, str | None], column: str) -> tuple[str, str, bool]:
    """Validate one editable field; infer corrections only for legacy blank decisions."""
    decision_col = "decision_" + column.removeprefix("correct_")
    action = _cell(row, decision_col).lower()
    value = _cell(row, column)
    if action and action not in _ACTIONS:
        raise ValueError(f"{decision_col} must be accept, correct, defer, reject, or blank")
    if action == "correct" and not value:
        raise ValueError(f"{decision_col}=correct requires {column}")
    if action in {"accept", "defer", "reject"} and value:
        raise ValueError(f"{decision_col}={action} requires a blank {column}")
    return action or ("correct" if value else ""), value, bool(action)


def _field_reviewers(
    row: Mapping[str, str | None], name: str, *, reviewer: str,
) -> list[dict[str, str]]:
    """Keep individual attribution when a merged CSV crosses the apply boundary."""
    encoded = _cell(row, "reviewer_records")
    if not encoded:
        return [{"reviewer": reviewer or "anonymous", "note": _cell(row, "reviewer_note"),
                 "evidence": _cell(row, "reviewer_evidence")}]
    try:
        records = json.loads(encoded)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid reviewer_records JSON") from exc
    if not isinstance(records, dict) or not isinstance(records.get(name), list) or not records[name]:
        raise ValueError(f"reviewer_records must attribute the reviewed {name} field")
    result = records[name]
    if any(
        not isinstance(record, dict)
        or not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip()
        or any(not isinstance(record.get(key, ""), str) for key in ("note", "evidence"))
        for record in result
    ):
        raise ValueError("invalid reviewer_records attribution")
    return cast(list[dict[str, str]], result)


def _cell(row: Mapping[str, str | None], col: str) -> str:
    """A row cell, None-safe, whitespace-stripped, with the formula guard removed."""
    return _unguard_cell((row.get(col) or "").strip())


def _exact_cell(row: Mapping[str, str | None], col: str) -> str:
    """A read-only source cell with formula protection removed but no whitespace loss."""
    return _unguard_cell(row.get(col) or "")


def _review_form_state_cells(fields: Mapping[str, object]) -> dict[str, str]:
    """Serialize JSON-ready form fields into stable CSV cells."""
    out: dict[str, str] = {}
    for col in FORM_STATE_COLUMNS:
        value = fields.get(col)
        if value is None:
            out[col] = ""
        elif isinstance(value, bool):
            out[col] = "true" if value else "false"
        elif isinstance(value, (list, dict)):
            out[col] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            out[col] = str(value)
    return out


def _form_state_matches_row(token: "Token", row: Mapping[str, str | None]) -> bool:
    """Check a new-format review row still describes this token's typed form state.

    Legacy review files have no ``form_*`` columns and intentionally skip this
    check; their existing identity/text guards remain unchanged.
    """
    if not any(col in row for col in FORM_STATE_COLUMNS):
        return True
    from .._view import _form_state_fields

    fields = _form_state_fields(token.form_state)
    fields["form_state_json"] = (
        json.dumps(
            token.form_state.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if token.form_state is not None
        else None
    )
    expected = _review_form_state_cells(fields)
    return all(_exact_cell(row, col) == expected[col] for col in FORM_STATE_COLUMNS)


def _has_corrections(row: Mapping[str, str | None]) -> bool:
    """Whether a row carries a correction or an explicit scholarly decision."""
    return any(_cell(row, col) for col in (*_CORRECTION_COLUMNS, *_DECISION_COLUMNS))


def _morph_key(annotations: dict[str, str]) -> str:
    """The annotation key a morphology correction belongs under: the key that supplied the
    displayed prediction (``morph`` for NT Robinson, ``feats`` for UD), defaulting to ``morph``."""
    if annotations.get("morph"):
        return "morph"
    if annotations.get("feats"):
        return "feats"
    return "morph"


def _validate_explicit_prediction(
    row: Mapping[str, str | None], annotations: dict[str, str], *,
    action: str, value: str, machine: str, key: str, label: str,
) -> None:
    """A decision must refer to the displayed prediction and its current source."""
    if action == "accept" and not machine.strip():
        raise ValueError(f"{label}: cannot accept an absent {key} prediction")
    if action == "correct" and value == machine:
        raise ValueError(f"{label}: unchanged {key} requires accept, not correct")
    source_changed = (
        key == "lemma" and "evidence_class" in row
        and _exact_cell(row, "evidence_class") != annotations.get("lemma_source", "")
    )
    if (key in annotations and annotations[key] != machine) or source_changed:
        raise ValueError(f"{label}: {key} prediction changed since export; export a fresh review table")


def _alignment_matches_row(token: "Token", row: Mapping[str, str | None]) -> bool:
    """Whether a source-aware review row still names this exact source token."""
    source_id = _exact_cell(row, "alignment_source_token_id")
    if not source_id:
        return True  # schema-1 review table: legacy doc/position/text checks apply
    alignment = token.alignment
    if alignment is None or source_id != alignment.source_token_id:
        return False
    row_ops = _cell(row, "alignment_normalization_ops")
    expected_ops = json.dumps(
        list(alignment.normalization_ops), ensure_ascii=False, separators=(",", ":")
    )
    return (
        (not _exact_cell(row, "alignment_document_id")
         or _exact_cell(row, "alignment_document_id") == alignment.document_id)
        and (not _exact_cell(row, "alignment_sentence_id")
             or _exact_cell(row, "alignment_sentence_id") == (alignment.sentence_id or ""))
        and (not _cell(row, "alignment_start_char")
             or _cell(row, "alignment_start_char") == str(alignment.start_char))
        and (not _cell(row, "alignment_end_char")
             or _cell(row, "alignment_end_char") == str(alignment.end_char))
        and (not _exact_cell(row, "alignment_original_text")
             or _exact_cell(row, "alignment_original_text") == alignment.original_text)
        and _exact_cell(row, "alignment_whitespace_before") == alignment.whitespace_before
        and (not _exact_cell(row, "alignment_normalized_text")
             or _exact_cell(row, "alignment_normalized_text") == alignment.normalized_text)
        and (not row_ops or row_ops == expected_ops)
    )


def _row_position(cell: str) -> int | None:
    """A review row's token index, or ``None`` when the cell cannot supply one.

    ``str.isdigit`` is the wrong test on both sides: it rejects values ``int`` accepts
    (a spreadsheet's ``-1`` or ``+1``) and accepts values ``int`` rejects (``²`` is a
    digit by Unicode but raises on conversion). Parse it directly instead, and treat a
    negative index as unusable rather than letting it address the sequence from the end.
    """
    try:
        index = int(cell)
    except (TypeError, ValueError):
        return None
    return index if index >= 0 else None


def _row_has_correction(row: Mapping[str, str | None]) -> bool:
    """Whether a review row actually carries reviewer content worth landing."""
    return _has_corrections(row)


@dataclass(frozen=True)
class _ParsedTable:
    """One review table as read: how many data rows it held, and those rows keyed for
    application (duplicates collapsed, unusable positions dropped)."""

    rows: int
    corrections: dict[tuple[str, int], dict[str, str | None]]


# The columns a file must carry to be a review table at all: the join key plus somewhere
# for the reviewer to write. A file without them cannot express a correction, so reading
# it can only ever produce an empty result that looks like a clean apply.
_JOIN_COLUMNS: tuple[str, ...] = ("doc_id", "position")
_CORRECTION_COLUMNS: tuple[str, ...] = tuple(col for col, _pred, _key in _CORRECTIONS)


def _check_review_header(path: str | Path, fieldnames: "Sequence[str] | None") -> None:
    """Confirm a CSV's header is a review table's, raising `ValueError` when it is not."""
    if fieldnames is None:
        raise ValueError(
            f"{path} is not a review table: the file is empty (no header row). "
            "Export one with `aegean review export` (or `aegean.io.to_review_table`)."
        )
    present = {name.strip() for name in fieldnames if name}
    missing = [col for col in _JOIN_COLUMNS if col not in present]
    if not any(col in present for col in (*_CORRECTION_COLUMNS, *_DECISION_COLUMNS)):
        missing.append(" or ".join((*_CORRECTION_COLUMNS, *_DECISION_COLUMNS)))
    if missing:
        raise ValueError(
            f"{path} is not a review table: no {', '.join(missing)} column. "
            f"Its columns are {', '.join(sorted(present)) or '(none)'}. "
            "Export one with `aegean review export` (or `aegean.io.to_review_table`), "
            "fill the correct_* columns, and apply that file."
        )


def _parse_corrections(path: str | Path) -> _ParsedTable:
    """Read a review CSV into a ``(doc_id, position) -> row`` map, None-safely.

    The header is checked first: a file that carries neither the join key nor a
    correction column is not a review table and raises `ValueError` rather than reading
    as an empty set of corrections, which lands nothing and looks like a clean apply.

    Duplicate rows for one token are collapsed; duplicates that carry *conflicting*
    corrections raise `ValueError` (the reviewer must resolve them). A malformed CSV (an
    unclosed quote, an over-long field) surfaces as a clean `ValueError`, not a raw
    ``csv.Error``. This is the shared parse behind `from_review_table` and
    `merge_review_tables`.

    A row whose ``position`` cell is not a usable index is skipped when it carries no
    correction, but RAISES when it does: silently dropping a reviewer's correction is
    the one outcome this loop must never produce. Spreadsheets reformat an integer
    column readily (``1`` becomes ``1.0``, a stray sign or space creeps in), so the
    unusable-position case is a realistic way to lose scholarly work, not a
    hypothetical."""
    corrections: dict[tuple[str, int], dict[str, str | None]] = {}
    source_keys: dict[str, tuple[str, int]] = {}
    seen = 0
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            _check_review_header(path, reader.fieldnames)
            for row in reader:
                seen += 1
                for column, _, _ in _CORRECTIONS:
                    _field_decision(row, column)
                pos = (row.get("position") or "").strip()
                index = _row_position(pos)
                if index is None:
                    if _row_has_correction(row):
                        raise ValueError(
                            f"review table {path}: a row carrying a correction has an "
                            f"unusable position {pos!r} (token {_cell(row, 'token')!r}); "
                            "fix the position column so the correction can be applied"
                        )
                    continue
                key = (row.get("doc_id") or "", index)
                source_key = _exact_cell(row, "alignment_source_token_id")
                if source_key:
                    prior_key = source_keys.get(source_key)
                    if prior_key is not None and prior_key != key:
                        raise ValueError(
                            f"review table {path}: source token id {source_key!r} appears "
                            "on more than one row"
                        )
                    source_keys[source_key] = key
                prev = corrections.get(key)
                if prev is not None:
                    same = all(
                        _cell(prev, c) == _cell(row, c)
                        for c in (*_CORRECTION_COLUMNS, *_DECISION_COLUMNS,
                                  "reviewer", "reviewer_note", "reviewer_evidence", "reviewer_records")
                    )
                    if not same:
                        raise ValueError(
                            f"review table {path}: duplicate rows for {key[0]} position "
                            f"{key[1]} carry conflicting corrections; resolve the duplicates"
                        )
                corrections[key] = row
    except csv.Error as exc:
        raise ValueError(f"malformed review CSV {path}: {exc}") from exc
    return _ParsedTable(rows=seen, corrections=corrections)


def _apply_corrections(
    corrections: Mapping[tuple[str, int], Mapping[str, str | None]],
    corpus: "Corpus",
    *,
    label: str,
    default_reviewer: str = "",
    note_extra: str = "",
    reviewers: tuple[str, ...] | None = None,
) -> "tuple[Corpus, int, int]":
    """Land ``corrections`` onto ``corpus``, returning a NEW corpus (the input is not
    mutated) and the number of tokens it changed.

    Rows prefer stable source-token identity and fall back to ``doc_id`` + ``position`` for
    old tables. Each matched row's source identity/span and exported ``token`` text are
    verified against the token it matched: a mismatch raises `ValueError`
    (naming the rows in ``label``) rather than silently landing a correction on the wrong word,
    and a correction whose row matches no token likewise raises. Each corrected field keeps the
    machine value under ``<field>__pred`` and the token is stamped ``review_status="corrected"``
    plus ``reviewed_by`` (from the row's ``reviewer`` cell, or ``default_reviewer``). The shared
    apply core behind both the single-reviewer and the merged paths.

    ``reviewers`` carries the structured set of contributing reviewers for the provenance
    attribution (the merged path passes `MergedReview.reviewers`). It is used verbatim rather
    than re-derived from a joined ``reviewer`` cell, so a reviewer name that itself contains a
    comma (``"Smith, John"``) is credited as one person, not split. When ``None`` (the
    single-reviewer path), each row's ``reviewer`` cell is one identity and is credited whole."""
    corrected = 0
    reviewed = 0
    mismatched: list[str] = []
    applied_keys: set[tuple[str, int]] = set()
    applied_reviewers: set[str] = set()
    new_docs = []
    by_source_id = {
        _exact_cell(row, "alignment_source_token_id"): (key, row)
        for key, row in corrections.items()
        if _exact_cell(row, "alignment_source_token_id")
    }
    for doc in corpus.documents:
        new_tokens = list(doc.tokens)
        for i, tok in enumerate(doc.tokens):
            if tok.position is None:
                continue
            legacy_key = (doc.id, tok.position)
            source_match = (
                by_source_id.get(tok.alignment.source_token_id)
                if tok.alignment is not None
                else None
            )
            matched_key, crow = (
                source_match if source_match is not None else (legacy_key, corrections.get(legacy_key))
            )
            if crow is None:
                continue
            applied_keys.add(matched_key)
            source_id = _exact_cell(crow, "alignment_source_token_id")
            if source_id and not _alignment_matches_row(tok, crow):
                    if _has_corrections(crow):
                        mismatched.append(
                            f"{doc.id} position {tok.position}: source alignment does not "
                            "match the exported row"
                        )
                    continue
            if not _form_state_matches_row(tok, crow):
                if _has_corrections(crow):
                    mismatched.append(
                        f"{doc.id} position {tok.position}: form state does not match the exported row"
                    )
                continue
            row_token = _exact_cell(crow, "token")
            if row_token and row_token != tok.text:
                if _has_corrections(crow):
                    mismatched.append(
                        f"{doc.id} position {tok.position}: table says {row_token!r}, "
                        f"corpus has {tok.text!r}"
                    )
                continue  # never apply a correction to a different word
            edits: dict[str, str] = {}
            events: list[dict[str, str]] = []
            who = _cell(crow, "reviewer") or default_reviewer
            note = _cell(crow, "reviewer_note")
            evidence = _cell(crow, "reviewer_evidence")
            value_changed = False
            for col, pred_col, default_key in _CORRECTIONS:
                action, val, explicit = _field_decision(crow, col)
                if not action:
                    continue
                akey = _morph_key(tok.annotations) if col == "correct_morph" else default_key
                # the machine value the reviewer actually saw: the row's own pred_* cell
                # (present even when the applied-to corpus carries no annotations, e.g. the
                # `review export --annotate` flow), falling back to the current annotation
                machine = (
                    _exact_cell(crow, pred_col) if pred_col in crow
                    else tok.annotations.get(akey, "")
                )
                if explicit:
                    _validate_explicit_prediction(
                        crow, tok.annotations, action=action, value=val, machine=machine,
                        key=akey, label=f"{label} at {doc.id} position {tok.position}",
                    )
                if not explicit and val == machine:
                    continue  # unchanged legacy correction cells do not imply acceptance
                if action in {"accept", "correct"}:
                    if action == "accept":
                        val = machine
                    edits[akey] = val
                    edits[f"{akey}__pred"] = tok.annotations.get(f"{akey}__pred", machine)
                    value_changed |= val != tok.annotations.get(akey, "")
                records = _field_reviewers(crow, col.removeprefix("correct_"), reviewer=who)
                edits[f"{akey}_verified"] = "true" if action in {"accept", "correct"} else "false"
                edits[f"{akey}_review_decision"] = action
                edits[f"{akey}_reviewed_by"] = ", ".join(record["reviewer"] for record in records)
                edits[f"{akey}_review_note"] = _join_notes([
                    (record["reviewer"], record.get("note", "")) for record in records if record.get("note")
                ])
                edits[f"{akey}_review_evidence"] = _join_notes([
                    (record["reviewer"], record.get("evidence", ""))
                    for record in records if record.get("evidence")
                ])
                for record in records:
                    events.append({
                        "field": akey, "action": action, "prediction": machine,
                        "value": val if action in {"accept", "correct"} else machine,
                        "reviewer": record["reviewer"], "note": record.get("note", ""),
                        "evidence": record.get("evidence", ""),
                        "prediction_source": (
                            _exact_cell(crow, "evidence_class") if akey == "lemma" else ""
                        ),
                        "date": date.today().isoformat(),
                    })
            if not edits:
                continue
            lemma_action = edits.get("lemma_review_decision")
            if lemma_action == "correct":
                # A corrected lemma is human-verified evidence, not the machine source
                # that produced the exported prediction. Preserve the old source beside
                # the old value so provenance remains complete.
                prior_source = tok.annotations.get("lemma_source") or _cell(crow, "evidence_class")
                if prior_source:
                    edits["lemma_source__pred"] = tok.annotations.get("lemma_source__pred", prior_source)
                edits["lemma_source"] = "user"
                edits["lemma_resolved"] = "true"
                edits["lemma_verified"] = "true"
                edits["review_recommended"] = "false"
                edits["lemma_known"] = "true"  # compatibility field during deprecation
            elif lemma_action == "accept":
                edits["lemma_resolved"] = "true"
                edits["review_recommended"] = "false"
                edits["lemma_known"] = "true"
            elif lemma_action in {"defer", "reject"}:
                edits["review_recommended"] = "true"
            actions = {event["action"] for event in events}
            edits["review_status"] = (
                {"accept": "accepted", "correct": "corrected", "defer": "deferred", "reject": "rejected"}
                [next(iter(actions))] if len(actions) == 1 else "reviewed"
            )
            if who or any(_cell(crow, c) for c in _DECISION_COLUMNS):
                # `who` is the display attribution kept verbatim (a merged cell may join
                # several reviewers, and one name may itself contain a comma). When the
                # structured `reviewers` set is not supplied, this is the single-reviewer
                # path where the whole cell is one identity — credit it whole, never split.
                edits["reviewed_by"] = who or "anonymous"
                if reviewers is None:
                    applied_reviewers.update(event["reviewer"] for event in events)
            if note:
                edits["review_note"] = note
            if evidence:
                edits["review_evidence"] = evidence
            history_text = tok.annotations.get("review_history", "[]")
            try:
                history = json.loads(history_text)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"{label}: invalid existing review_history") from exc
            if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
                raise ValueError(f"{label}: invalid existing review_history")
            for event in events:
                previous = next((
                    item for item in reversed(history)
                    if item.get("field") == event["field"] and item.get("reviewer") == event["reviewer"]
                ), None)
                if previous != event or tok.annotations.get(f"{event['field']}_review_decision") == "stale":
                    history.append(event)
            edits["review_history"] = json.dumps(history, ensure_ascii=False, separators=(",", ":"))
            annotations = {**tok.annotations, **edits}
            if annotations != tok.annotations:
                new_tokens[i] = replace(tok, annotations=annotations)
                reviewed += 1
                corrected += int(value_changed)
        new_docs.append(replace(doc, tokens=new_tokens))

    if mismatched:
        shown = "; ".join(mismatched[:5]) + ("; …" if len(mismatched) > 5 else "")
        raise ValueError(
            f"{label} does not match this corpus ({len(mismatched)} corrected "
            f"row(s) name a different token — was it exported from another corpus, or has "
            f"the corpus changed?): {shown}"
        )
    orphaned = [
        k for k, row in corrections.items() if k not in applied_keys and _has_corrections(row)
    ]
    if orphaned:
        shown = ", ".join(f"{d} position {p}" for d, p in orphaned[:5])
        shown += ", …" if len(orphaned) > 5 else ""
        raise ValueError(
            f"{label}: {len(orphaned)} corrected row(s) match no token in this "
            f"corpus ({shown}) — pass the same corpus the table was exported from"
        )

    prov = corpus.provenance
    if prov is not None and reviewed:  # a no-op apply leaves provenance untouched
        if default_reviewer:
            who_text = f" by {default_reviewer}"
        elif reviewers:
            # the structured set (merged path): joined for display, but each element is a
            # whole reviewer identity, so a comma-bearing name stays intact
            who_text = f" by {', '.join(reviewers)}"
        elif applied_reviewers:
            who_text = f" by {', '.join(sorted(applied_reviewers))}"
        else:
            who_text = ""
        outcome = (
            f"{corrected} tokens corrected" if corrected == reviewed
            else f"{reviewed} tokens reviewed ({corrected} corrected)"
        )
        note = f"review: {outcome}{who_text}{note_extra} ({date.today().isoformat()})"
        prov = replace(prov, notes=prov.notes + (note,))
    from ..core.corpus import Corpus

    return Corpus(new_docs, corpus.sign_inventory, prov, corpus.script_id), corrected, reviewed


@dataclass(frozen=True)
class ReviewApplication:
    """What landing one review table did: the corrected corpus and what it was asked to do.

    ``rows`` is how many rows the table held, ``corrections`` how many of them carried a
    reviewer's value, and ``corrected`` how many tokens actually changed (a correction
    equal to the value the reviewer was shown changes nothing). Reading all three tells a
    caller whether an apply that raised nothing actually did anything. ``decisions`` counts
    explicit field actions and ``reviewed`` counts tokens whose annotations or audit trail
    changed. An acceptance can therefore have zero ``corrected`` and positive ``reviewed``.
    Legacy correction-only counts retain their meaning."""

    corpus: "Corpus"
    rows: int
    corrections: int
    corrected: int
    decisions: int = 0
    reviewed: int = 0


def apply_review_table(
    path: str | Path, corpus: "Corpus", *, reviewer: str = ""
) -> ReviewApplication:
    """`from_review_table`, reporting what the table contained and how much of it landed.

    Same reading, same guards, same corrected corpus (on `ReviewApplication.corpus`); use
    this when a no-op needs to be distinguishable from a successful apply."""
    parsed = _parse_corrections(path)
    applied, corrected, reviewed = _apply_corrections(
        parsed.corrections, corpus, label=f"review table {path}", default_reviewer=reviewer
    )
    return ReviewApplication(
        corpus=applied,
        rows=parsed.rows,
        corrections=sum(
            1 for row in parsed.corrections.values()
            if any(_cell(row, col) for col in _CORRECTION_COLUMNS)
        ),
        corrected=corrected,
        decisions=sum(
            bool(_cell(row, col)) for row in parsed.corrections.values() for col in _DECISION_COLUMNS
        ),
        reviewed=reviewed,
    )


def from_review_table(path: str | Path, corpus: "Corpus", *, reviewer: str = "") -> "Corpus":
    """Read field decisions/corrections from ``path`` onto a NEW immutable corpus.

    ``decision_lemma``, ``decision_pos``, and ``decision_morph`` take ``accept``, ``correct``,
    ``defer``, or ``reject``. Accept requires an existing prediction; correct requires a
    different nonempty ``correct_*`` value. Defer/reject retain the prediction but mark
    the field unverified. Explicit decisions refuse predictions that changed since export.
    Each field records its decision, verification, reviewer, note, and evidence under its
    actual annotation key (``lemma``, ``upos``, ``morph`` or ``feats``). ``review_history``
    is a JSON audit trail preserving the prediction and each reviewer decision. No action
    certifies another field, a dependency tree, or a lexical sense.

    Blank decisions keep the legacy correction-only behavior: blank cells and a correction
    equal to the displayed prediction change nothing and never imply approval. A reviewer
    comes from the CSV, then the ``reviewer`` argument, then ``anonymous``. Merged CSVs carry
    individual field attribution in the read-only ``reviewer_records`` JSON column.

    Rows prefer stable source-token identity and fall back to ``doc_id`` + ``position`` for
    old tables. Source alignment and exported ``token`` text are verified: a mismatch (the corpus changed
    between export and apply, or the wrong corpus was passed) raises `ValueError` naming the
    rows rather than silently landing a correction on the wrong word. Duplicate rows for one
    token with conflicting corrections, corrections whose row matches no token, and a
    malformed CSV also raise `ValueError`.

    For each row whose ``correct_*`` differs from the machine value the reviewer saw (the
    row's own ``pred_*`` cell, falling back to the token's current annotation), the token's
    annotation for that field is set to the corrected value, the machine value is preserved
    under ``<field>__pred`` (retaining the first prediction across repeated reviews), and the token is stamped ``reviewed_by`` /
    ``review_status="corrected"`` (plus ``review_note`` when the reviewer left one). A
    morphology correction lands on the same key that supplied the displayed prediction
    (``morph`` or UD ``feats``). Rows left blank change nothing. The stamped reviewer is
    the row's identity, falling back to ``reviewer`` when given. A ``review:`` provenance
    note records reviewed/corrected tokens. A file that is not a review table (no
    ``doc_id`` / ``position``, neither ``correct_*`` nor ``decision_*`` columns, or no header) raises rather than
    reading as zero corrections. The input corpus is not mutated. Use `apply_review_table`
    for the same result plus the counts."""
    return apply_review_table(path, corpus, reviewer=reviewer).corpus


# ── multi-reviewer merge ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ReviewerValue:
    """One reviewer's field action/value, with optional note and evidence."""

    reviewer: str
    value: str
    note: str = ""
    action: str = "correct"
    evidence: str = ""


@dataclass(frozen=True)
class ReviewConflict:
    """One field of one token where reviewers proposed different actions or values.

    ``field`` is the human field name (``lemma`` / ``pos`` / ``morph``); ``options`` lists each
    reviewer's proposed value (and note). A conflict is never resolved silently — it is surfaced
    for a human to settle."""

    doc_id: str
    position: int
    token: str
    field: str
    options: tuple[ReviewerValue, ...]


@dataclass(frozen=True)
class MergedReview:
    """The result of merging several reviewers' corrected copies of one export.

    ``rows`` is the clean, agreed subset as review-table rows (ready to write or to apply with
    `apply_merged`); ``conflicts`` are the disagreements held back for a human; ``reviewers`` is
    every reviewer whose decisions/corrections are in ``rows``; ``source_paths`` records the merged
    tables. Use ``to_csv`` to write the agreed subset back out as a review table."""

    rows: tuple[dict[str, str], ...]
    conflicts: tuple[ReviewConflict, ...]
    reviewers: tuple[str, ...]
    source_paths: tuple[str, ...] = field(default_factory=tuple)

    def to_csv(self, path: str | Path) -> None:
        """Write the agreed (clean) subset as a review CSV (UTF-8 BOM, formula-guarded)."""
        _write_review_rows(path, self.rows)


def _write_review_rows(
    path: str | Path,
    rows: Iterable[Mapping[str, str]],
    *,
    _preguarded: bool = False,
) -> None:
    """Write review-table rows (dicts keyed by `REVIEW_COLUMNS`) to a CSV, atomically.

    Cells are formula-guarded on write unless ``_preguarded`` (the row values already carry the
    guard, as `to_review_table` produces them)."""
    guard = (lambda v: v) if _preguarded else _guard_cell
    with atomic_path(path) as tmp:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(REVIEW_COLUMNS)
            for r in rows:
                w.writerow([guard(str(r.get(col, ""))) for col in REVIEW_COLUMNS])


def _reviewer_of_file(
    corrections: Mapping[tuple[str, int], Mapping[str, str | None]], path: Path
) -> str:
    """The reviewer identity for one table: the distinct non-blank ``reviewer`` column value,
    or the file stem when the column is blank. A table naming more than one reviewer raises."""
    names = sorted({_cell(r, "reviewer") for r in corrections.values() if _cell(r, "reviewer")})
    if len(names) > 1:
        raise ValueError(
            f"review table {path}: names more than one reviewer ({', '.join(names)}); "
            f"a single table must come from a single reviewer"
        )
    return names[0] if names else path.stem


def _verify_against_corpus(
    files: list[tuple[str, Mapping[tuple[str, int], Mapping[str, str | None]], str]],
    corpus: "Corpus",
) -> None:
    """Confirm every table is a corrected copy of *this* corpus's export: each corrected row's
    ``(doc_id, position)`` must exist in the corpus and its ``token`` text must match the corpus
    token there. A row that names a different token (a table exported from another corpus) or one
    that matches no token raises `ValueError` — the same 0.32.0 guards `from_review_table`
    applies, checked once up front across every table."""
    corpus_tokens: dict[tuple[str, int], Token] = {}
    corpus_source_tokens: dict[str, tuple[str, int, Token]] = {}
    for doc in corpus.documents:
        for tok in doc.tokens:
            if tok.position is not None:
                corpus_tokens[(doc.id, tok.position)] = tok
                if tok.alignment is not None:
                    corpus_source_tokens[tok.alignment.source_token_id] = (
                        doc.id,
                        tok.position,
                        tok,
                    )
    mismatched: list[str] = []
    orphaned: list[str] = []
    for name, corr, _path in files:
        for (doc_id, pos), row in corr.items():
            if not _has_corrections(row):
                continue  # only corrected rows are load-bearing (mirrors from_review_table)
            source_id = _exact_cell(row, "alignment_source_token_id")
            source_match = corpus_source_tokens.get(source_id) if source_id else None
            token = source_match[2] if source_match is not None else corpus_tokens.get((doc_id, pos))
            if token is None:
                orphaned.append(f"{doc_id} position {pos} ({name})")
                continue
            row_token = _exact_cell(row, "token")
            if not _alignment_matches_row(token, row):
                mismatched.append(
                    f"{doc_id} position {pos}: {name} has changed source alignment"
                )
            elif not _form_state_matches_row(token, row):
                mismatched.append(f"{doc_id} position {pos}: {name} has changed form state")
            elif row_token and row_token != token.text:
                mismatched.append(
                    f"{doc_id} position {pos}: {name} has {row_token!r}, "
                    f"corpus has {token.text!r}"
                )
            else:
                for col, pred_col, default_key in _CORRECTIONS:
                    action, value, explicit = _field_decision(row, col)
                    if explicit:
                        annotation_key = _morph_key(token.annotations) if col == "correct_morph" else default_key
                        machine = (
                            _exact_cell(row, pred_col) if pred_col in row
                            else token.annotations.get(annotation_key, "")
                        )
                        _validate_explicit_prediction(
                            row, token.annotations, action=action, value=value, machine=machine,
                            key=annotation_key, label=f"review table by {name} at {doc_id} position {pos}",
                        )
    if mismatched:
        shown = "; ".join(sorted(mismatched)[:5]) + ("; …" if len(mismatched) > 5 else "")
        raise ValueError(
            f"merge_review_tables: {len(mismatched)} corrected row(s) name a different token "
            f"than the corpus (was a table exported from another corpus?): {shown}"
        )
    if orphaned:
        shown = ", ".join(sorted(orphaned)[:5]) + (", …" if len(orphaned) > 5 else "")
        raise ValueError(
            f"merge_review_tables: {len(orphaned)} corrected row(s) match no token in the "
            f"corpus ({shown}) — pass the same corpus the tables were exported from"
        )


def _join_notes(notes: list[tuple[str, str]]) -> str:
    """Combine reviewers' notes for one merged token: one reviewer's note verbatim, or several
    attributed as ``reviewer: note``."""
    if not notes:
        return ""
    if len(notes) == 1:
        return notes[0][1]
    return "; ".join(f"{rev}: {note}" for rev, note in sorted(notes))


def _conflict_message(conflicts: list[ReviewConflict]) -> str:
    lines = [
        f"  {c.doc_id} position {c.position} {c.token!r} {c.field}: "
        + ", ".join(f"{o.reviewer}={o.action}:{o.value!r}" for o in c.options)
        for c in conflicts
    ]
    return (
        f"merge_review_tables: {len(conflicts)} conflicting correction(s) across reviewers "
        f"(resolve them, or pass on_conflict='report' to apply the agreed subset):\n"
        + "\n".join(lines)
    )


def merge_review_tables(
    paths: Iterable[str | Path],
    corpus: "Corpus",
    *,
    on_conflict: str = "error",
) -> MergedReview:
    """Merge several reviewers' corrected copies of the SAME review export.

    Each table in ``paths`` is a corrected copy of one `to_review_table` export. Corrections the
    reviewers agree on (or that only one reviewer made) are combined into `MergedReview.rows`;
    where two reviewers give different values for the same field of the same token, the
    disagreement is surfaced as a `ReviewConflict` and never silently resolved. With
    ``on_conflict="error"`` any conflict raises `ValueError` listing them all; with
    ``on_conflict="report"`` the conflicts are returned in `MergedReview.conflicts` and the
    agreed subset stays applicable (`apply_merged`).

    Reviewer identity comes from each table's ``reviewer`` column (or, when blank, the file
    name). The tables must be copies of one export: a table whose token text disagrees at a
    shared ``(doc_id, position)`` raises (a wrong-corpus mix-up), as does a reviewer name that
    appears in more than one table (identities must be distinct to attribute a conflict).
    ``corpus`` is used to verify the export's shape; the corrections are landed by
    `apply_merged`."""
    if on_conflict not in ("error", "report"):
        raise ValueError("on_conflict must be 'error' or 'report'")
    path_list = [Path(p) for p in paths]
    if not path_list:
        raise ValueError("merge_review_tables: no review tables to merge")

    files: list[tuple[str, Mapping[tuple[str, int], Mapping[str, str | None]], str]] = []
    for p in path_list:
        corr = _parse_corrections(p).corrections
        files.append((_reviewer_of_file(corr, p), corr, str(p)))

    names = [name for name, _corr, _path in files]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(
            f"merge_review_tables: reviewer name(s) {', '.join(repr(d) for d in dupes)} "
            f"appear in more than one table; give each table a distinct reviewer "
            f"(fill the 'reviewer' column, or rename the files)"
        )

    _verify_against_corpus(files, corpus)

    all_keys = sorted({key for _name, corr, _path in files for key in corr})
    merged_rows: list[dict[str, str]] = []
    conflicts: list[ReviewConflict] = []
    contributors: set[str] = set()

    for doc_id, pos in all_keys:
        key = (doc_id, pos)
        ctx = next(corr[key] for _name, corr, _path in files if key in corr)
        token = _exact_cell(ctx, "token")
        # Source spans, whitespace, forms, and predictions are immutable context.
        # Trimming them here would make a verified aligned export impossible to apply.
        merged: dict[str, str] = {col: _exact_cell(ctx, col) for col in REVIEW_COLUMNS}
        for col in (*_CORRECTION_COLUMNS, *_DECISION_COLUMNS, "reviewer_note", "reviewer",
                    "reviewer_evidence", "reviewer_records"):
            merged[col] = ""
        row_reviewers: set[str] = set()
        records: dict[str, list[dict[str, str]]] = {}
        has_clean = False
        for col, _pred, _default in _CORRECTIONS:
            proposals = [
                (name, *_field_decision(corr[key], col), corr[key])
                for name, corr, _path in files
                if key in corr and _field_decision(corr[key], col)[0]
            ]
            values = {(action, value) for _n, action, value, _explicit, _row in proposals}
            if not values:
                continue
            if len(values) == 1:
                action, value = next(iter(values))
                merged[col] = value
                if any(explicit for _n, _a, _v, explicit, _row in proposals):
                    merged["decision_" + col.removeprefix("correct_")] = action
                has_clean = True
                row_reviewers.update(name for name, _a, _v, _explicit, _row in proposals)
                records[col.removeprefix("correct_")] = [
                    {"reviewer": name, "note": _cell(row, "reviewer_note"),
                     "evidence": _cell(row, "reviewer_evidence")}
                    for name, _a, _v, _explicit, row in proposals
                ]
            else:
                conflicts.append(
                    ReviewConflict(
                        doc_id=doc_id, position=pos, token=token,
                        field=col[len("correct_"):],
                        options=tuple(
                            ReviewerValue(n, v, _cell(row, "reviewer_note"), a,
                                          _cell(row, "reviewer_evidence"))
                            for n, a, v, _explicit, row in proposals
                        ),
                    )
                )
        if has_clean:
            notes = [
                (name, _cell(corr[key], "reviewer_note"))
                for name, corr, _path in files
                if name in row_reviewers and key in corr and _cell(corr[key], "reviewer_note")
            ]
            merged["reviewer"] = ", ".join(sorted(row_reviewers))
            merged["reviewer_note"] = _join_notes(notes)
            merged["reviewer_evidence"] = _join_notes([
                (name, _cell(corr[key], "reviewer_evidence"))
                for name, corr, _path in files
                if name in row_reviewers and key in corr and _cell(corr[key], "reviewer_evidence")
            ])
            merged["reviewer_records"] = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
            merged_rows.append(merged)
            contributors |= row_reviewers

    if on_conflict == "error" and conflicts:
        raise ValueError(_conflict_message(conflicts))

    return MergedReview(
        rows=tuple(merged_rows),
        conflicts=tuple(conflicts),
        reviewers=tuple(sorted(contributors)),
        source_paths=tuple(str(p) for p in path_list),
    )


def apply_merged(merged: MergedReview, corpus: "Corpus") -> "Corpus":
    """Land a `MergedReview`'s agreed corrections onto ``corpus``, returning a NEW corpus.

    Runs the agreed (clean) subset through the same apply core as `from_review_table`, so every
    guard still fires (each row's ``token`` text is verified against the corpus; a wrong-corpus
    mismatch or an orphaned row raises). Each corrected field keeps the machine value under
    ``<field>__pred``; every contributing reviewer is stamped on the token (``reviewed_by``) and
    listed in the ``review:`` provenance note, which records that it came from a merge."""
    corrections: dict[tuple[str, int], Mapping[str, str | None]] = {}
    for row in merged.rows:
        pos = (row.get("position") or "").strip()
        index = _row_position(pos)
        if index is None:
            # Same rule as `_parse_corrections`: a row with nothing to land is
            # skipped, but one carrying a reviewer's correction must never be
            # dropped in silence just because its position cell is unusable.
            if _row_has_correction(row):
                raise ValueError(
                    f"merged review table: a row carrying a correction has an unusable "
                    f"position {pos!r} (token {_cell(row, 'token')!r}); fix the position "
                    "column in the source table so the correction can be applied"
                )
            continue
        corrections[(row.get("doc_id") or "", index)] = row
    note_extra = f" (merged from {len(merged.source_paths)} review tables)"
    applied, _corrected, _reviewed = _apply_corrections(
        corrections, corpus, label="the merged review table", note_extra=note_extra,
        reviewers=merged.reviewers,
    )
    return applied
