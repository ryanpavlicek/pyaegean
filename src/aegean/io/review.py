"""Human-in-the-loop review tables: machine annotations out, corrected annotations back.

Automated analysis does not end the workflow. This module exports a corpus's per-token
annotations to a plain CSV a scholar can open in a spreadsheet, correct, and hand back:
`to_review_table` writes one reviewable row per word (the machine's lemma / POS / morphology,
its evidence class and a "needs review" flag, and blank columns for the reviewer's
corrections and notes); `from_review_table` reads the corrections back onto the corpus,
keeping the machine's value under a ``<field>__pred`` key and stamping who reviewed it and a
provenance note. The join key is ``doc_id`` + ``position``.

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
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from .._atomic import atomic_path

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = [
    "REVIEW_COLUMNS",
    "MergedReview",
    "ReviewConflict",
    "ReviewerValue",
    "apply_merged",
    "from_review_table",
    "merge_review_tables",
    "needs_review_flag",
    "to_review_table",
]

# The columns of a review table. The first block is read-only context + prediction + triage;
# the reviewer fills the ``correct_*`` and ``reviewer_note`` columns (blank = accept as-is) and
# records who they are in ``reviewer`` (used when several copies are merged; blank = anonymous,
# in which case the merge falls back to the file name).
REVIEW_COLUMNS: tuple[str, ...] = (
    "doc_id", "position", "line_no", "ref", "token",       # identity / join key (read-only)
    "pred_lemma", "pred_pos", "pred_morph",                # machine prediction (read-only)
    "evidence_class", "source_citation", "needs_review",   # provenance + triage (read-only)
    "correct_lemma", "correct_pos", "correct_morph",       # reviewer fills
    "reviewer_note", "reviewer",                            # reviewer fills
)


def _low_confidence() -> frozenset[str]:
    """Evidence classes meaning "not a grounded analysis", derived from the ONE canonical
    predicate (`aegean.greek.needs_review`) so the two can never drift apart. Imported
    lazily to keep ``import aegean.io`` free of the greek package."""
    from ..greek.lemmatize import LemmaSource, needs_review

    return frozenset(s.value for s in LemmaSource if needs_review(s))


def needs_review_flag(annotations: dict[str, str], *, source_key: str = "lemma_source") -> bool:
    """Whether a token's annotation should be verified by a human.

    True when its evidence class (``annotations[source_key]``, e.g. from
    `aegean.greek.annotate.annotate_corpus`) is a low-confidence class (``identity`` /
    ``unresolved``); failing that, when ``lemma_known`` is the string ``"false"``. A token
    that carries neither signal (for example a gold-annotated corpus) is **not** flagged."""
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
    only_needs_review: bool = False,
    reviewer: str = "",
) -> int:
    """Write one reviewable row per WORD token of ``corpus`` to ``path`` (CSV, UTF-8 BOM).

    Each row carries the token's identity (``doc_id``/``position``/``line_no``/``ref``), the
    machine ``pred_lemma``/``pred_pos``/``pred_morph`` from its annotations, the
    ``evidence_class`` and a ``needs_review`` flag, the corpus citation, and blank
    ``correct_*`` / ``reviewer_note`` columns for the reviewer. With ``only_needs_review`` only
    the flagged rows are written. Pass ``reviewer`` to pre-stamp every row's ``reviewer``
    column (hand a named copy to each reviewer when the corrected copies will be merged with
    `merge_review_tables`); it is left blank by default. Returns the number of rows written.

    A token without a ``position`` is not exported: the apply join key is
    ``doc_id`` + ``position``, so a correction on such a row could never be applied. Cells
    that would open as a live formula in a spreadsheet are neutralized with a leading
    apostrophe (stripped again by `from_review_table`)."""
    from ..core.model import TokenKind

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
            if only_needs_review and not flag:
                continue
            rows.append([
                doc.id,
                str(tok.position),
                str(tok.line_no if tok.line_no is not None else ""),
                _guard_cell(a.get("ref", ref_base)),
                _guard_cell(tok.text),
                _guard_cell(a.get("lemma", "")),
                _guard_cell(a.get("upos", "")),
                _guard_cell(_morph(a)),
                a.get(source_key, ""),
                _guard_cell(citation),
                "yes" if flag else "",
                "", "", "", "",  # correct_lemma, correct_pos, correct_morph, reviewer_note
                _guard_cell(reviewer),
            ])
    _write_review_rows(path, [dict(zip(REVIEW_COLUMNS, r)) for r in rows], _preguarded=True)
    return len(rows)


# (review-table correction column -> its prediction column -> default annotation key)
_CORRECTIONS: tuple[tuple[str, str, str], ...] = (
    ("correct_lemma", "pred_lemma", "lemma"),
    ("correct_pos", "pred_pos", "upos"),
    ("correct_morph", "pred_morph", "morph"),
)


def _cell(row: Mapping[str, str | None], col: str) -> str:
    """A row cell, None-safe, whitespace-stripped, with the formula guard removed."""
    return _unguard_cell((row.get(col) or "").strip())


def _has_corrections(row: Mapping[str, str | None]) -> bool:
    return any(_cell(row, col) for col, _pred, _key in _CORRECTIONS)


def _split_reviewers(value: str) -> list[str]:
    """The individual reviewer names in a (possibly comma-joined) ``reviewer`` cell."""
    return [name.strip() for name in value.split(",") if name.strip()]


def _morph_key(annotations: dict[str, str]) -> str:
    """The annotation key a morphology correction belongs under: the key that supplied the
    displayed prediction (``morph`` for NT Robinson, ``feats`` for UD), defaulting to ``morph``."""
    if annotations.get("morph"):
        return "morph"
    if annotations.get("feats"):
        return "feats"
    return "morph"


def _parse_corrections(path: str | Path) -> dict[tuple[str, int], dict[str, str | None]]:
    """Read a review CSV into a ``(doc_id, position) -> row`` map, None-safely.

    Duplicate rows for one token are collapsed; duplicates that carry *conflicting*
    corrections raise `ValueError` (the reviewer must resolve them). A malformed CSV (an
    unclosed quote, an over-long field) surfaces as a clean `ValueError`, not a raw
    ``csv.Error``. This is the shared parse behind `from_review_table` and
    `merge_review_tables`."""
    corrections: dict[tuple[str, int], dict[str, str | None]] = {}
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                pos = (row.get("position") or "").strip()
                if not pos.isdigit():
                    continue
                key = (row.get("doc_id") or "", int(pos))
                prev = corrections.get(key)
                if prev is not None:
                    same = all(_cell(prev, c) == _cell(row, c) for c, _p, _k in _CORRECTIONS)
                    if not same:
                        raise ValueError(
                            f"review table {path}: duplicate rows for {key[0]} position "
                            f"{key[1]} carry conflicting corrections; resolve the duplicates"
                        )
                corrections[key] = row
    except csv.Error as exc:
        raise ValueError(f"malformed review CSV {path}: {exc}") from exc
    return corrections


def _apply_corrections(
    corrections: Mapping[tuple[str, int], Mapping[str, str | None]],
    corpus: "Corpus",
    *,
    label: str,
    default_reviewer: str = "",
    note_extra: str = "",
) -> "Corpus":
    """Land ``corrections`` onto ``corpus``, returning a NEW corpus (the input is not mutated).

    Rows are matched to tokens by ``doc_id`` + ``position``, and each matched row's exported
    ``token`` text is verified against the token it matched: a mismatch raises `ValueError`
    (naming the rows in ``label``) rather than silently landing a correction on the wrong word,
    and a correction whose row matches no token likewise raises. Each corrected field keeps the
    machine value under ``<field>__pred`` and the token is stamped ``review_status="corrected"``
    plus ``reviewed_by`` (from the row's ``reviewer`` cell, or ``default_reviewer``). The shared
    apply core behind both the single-reviewer and the merged paths."""
    corrected = 0
    mismatched: list[str] = []
    applied_keys: set[tuple[str, int]] = set()
    applied_reviewers: set[str] = set()
    new_docs = []
    for doc in corpus.documents:
        new_tokens = list(doc.tokens)
        for i, tok in enumerate(doc.tokens):
            if tok.position is None:
                continue
            crow = corrections.get((doc.id, tok.position))
            if crow is None:
                continue
            applied_keys.add((doc.id, tok.position))
            row_token = _cell(crow, "token")
            if row_token and row_token != tok.text:
                if _has_corrections(crow):
                    mismatched.append(
                        f"{doc.id} position {tok.position}: table says {row_token!r}, "
                        f"corpus has {tok.text!r}"
                    )
                continue  # never apply a correction to a different word
            edits: dict[str, str] = {}
            for col, pred_col, default_key in _CORRECTIONS:
                val = _cell(crow, col)
                if not val:
                    continue
                akey = _morph_key(tok.annotations) if col == "correct_morph" else default_key
                # the machine value the reviewer actually saw: the row's own pred_* cell
                # (present even when the applied-to corpus carries no annotations, e.g. the
                # `review export --annotate` flow), falling back to the current annotation
                machine = _cell(crow, pred_col) or tok.annotations.get(akey, "")
                if val != machine:
                    edits[akey] = val
                    edits[f"{akey}__pred"] = machine
            if not edits:
                continue
            edits["review_status"] = "corrected"
            who = _cell(crow, "reviewer") or default_reviewer
            if who:
                edits["reviewed_by"] = who
                applied_reviewers.update(_split_reviewers(who))
            note = _cell(crow, "reviewer_note")
            if note:
                edits["review_note"] = note
            new_tokens[i] = replace(tok, annotations={**tok.annotations, **edits})
            corrected += 1
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
    if prov is not None and corrected:  # a no-op apply leaves provenance untouched
        if default_reviewer:
            who_text = f" by {default_reviewer}"
        elif applied_reviewers:
            who_text = f" by {', '.join(sorted(applied_reviewers))}"
        else:
            who_text = ""
        note = f"review: {corrected} tokens corrected{who_text}{note_extra} ({date.today().isoformat()})"
        prov = replace(prov, notes=prov.notes + (note,))
    from ..core.corpus import Corpus

    return Corpus(new_docs, corpus.sign_inventory, prov, corpus.script_id)


def from_review_table(path: str | Path, corpus: "Corpus", *, reviewer: str = "") -> "Corpus":
    """Read reviewer corrections from ``path`` back onto ``corpus``, returning a NEW corpus.

    Rows are matched to tokens by ``doc_id`` + ``position``, and each matched row's exported
    ``token`` text is verified against the token it matched: a mismatch (the corpus changed
    between export and apply, or the wrong corpus was passed) raises `ValueError` naming the
    rows rather than silently landing a correction on the wrong word. Duplicate rows for one
    token with conflicting corrections, corrections whose row matches no token, and a
    malformed CSV also raise `ValueError`.

    For each row whose ``correct_*`` differs from the machine value the reviewer saw (the
    row's own ``pred_*`` cell, falling back to the token's current annotation), the token's
    annotation for that field is set to the corrected value, the machine value is preserved
    under ``<field>__pred``, and the token is stamped ``reviewed_by`` /
    ``review_status="corrected"`` (plus ``review_note`` when the reviewer left one). A
    morphology correction lands on the same key that supplied the displayed prediction
    (``morph`` or UD ``feats``). Rows left blank change nothing. The stamped reviewer is
    ``reviewer`` when given, else each row's own ``reviewer`` column. A ``review:`` provenance
    note records how many tokens were corrected. The input corpus is not mutated."""
    corrections = _parse_corrections(path)
    return _apply_corrections(
        corrections, corpus, label=f"review table {path}", default_reviewer=reviewer
    )


# ── multi-reviewer merge ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ReviewerValue:
    """One reviewer's proposed value for a field (with their note, if any)."""

    reviewer: str
    value: str
    note: str = ""


@dataclass(frozen=True)
class ReviewConflict:
    """One field of one token where reviewers proposed different corrections.

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
    every reviewer whose corrections are in ``rows``; ``source_paths`` records the merged
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
    corpus_tokens: dict[tuple[str, int], str] = {}
    for doc in corpus.documents:
        for tok in doc.tokens:
            if tok.position is not None:
                corpus_tokens[(doc.id, tok.position)] = tok.text
    mismatched: list[str] = []
    orphaned: list[str] = []
    for name, corr, _path in files:
        for (doc_id, pos), row in corr.items():
            if not _has_corrections(row):
                continue  # only corrected rows are load-bearing (mirrors from_review_table)
            if (doc_id, pos) not in corpus_tokens:
                orphaned.append(f"{doc_id} position {pos} ({name})")
                continue
            row_token = _cell(row, "token")
            if row_token and row_token != corpus_tokens[(doc_id, pos)]:
                mismatched.append(
                    f"{doc_id} position {pos}: {name} has {row_token!r}, "
                    f"corpus has {corpus_tokens[(doc_id, pos)]!r}"
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
        + ", ".join(f"{o.reviewer}={o.value!r}" for o in c.options)
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
        corr = _parse_corrections(p)
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
        token = _cell(ctx, "token")
        merged: dict[str, str] = {col: _cell(ctx, col) for col in REVIEW_COLUMNS}
        for col in ("correct_lemma", "correct_pos", "correct_morph", "reviewer_note", "reviewer"):
            merged[col] = ""
        row_reviewers: set[str] = set()
        has_clean = False
        for col, _pred, _default in _CORRECTIONS:
            proposals = [
                (name, _cell(corr[key], col), _cell(corr[key], "reviewer_note"))
                for name, corr, _path in files
                if key in corr and _cell(corr[key], col)
            ]
            values = {value for _n, value, _note in proposals}
            if not values:
                continue
            if len(values) == 1:
                merged[col] = next(iter(values))
                has_clean = True
                row_reviewers.update(name for name, _v, _note in proposals)
            else:
                conflicts.append(
                    ReviewConflict(
                        doc_id=doc_id, position=pos, token=token,
                        field=col[len("correct_"):],
                        options=tuple(ReviewerValue(n, v, note) for n, v, note in proposals),
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
        if pos.isdigit():
            corrections[(row.get("doc_id") or "", int(pos))] = row
    note_extra = f" (merged from {len(merged.source_paths)} review tables)"
    return _apply_corrections(
        corrections, corpus, label="the merged review table", note_extra=note_extra
    )
