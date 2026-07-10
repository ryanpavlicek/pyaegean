"""Human-in-the-loop review tables: machine annotations out, corrected annotations back.

Automated analysis does not end the workflow. This module exports a corpus's per-token
annotations to a plain CSV a scholar can open in a spreadsheet, correct, and hand back:
`to_review_table` writes one reviewable row per word (the machine's lemma / POS / morphology,
its evidence class and a "needs review" flag, and blank columns for the reviewer's
corrections and notes); `from_review_table` reads the corrections back onto the corpus,
keeping the machine's value under a ``<field>__pred`` key and stamping who reviewed it and a
provenance note. The join key is ``doc_id`` + ``position``.

Zero-dependency: CSV via the stdlib ``csv`` module, written with a UTF-8 BOM so a spreadsheet
opens the Greek correctly. The corpus is rebuilt immutably (``dataclasses.replace``); nothing
is edited in place. The predictions come from an existing corpus's ``Token.annotations`` (for
the New Testament, the gold lemma/morph/Strong's are already there; for other corpora, run
`aegean.greek.annotate.annotate_corpus` first to fill them)."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from .._atomic import atomic_path

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["REVIEW_COLUMNS", "needs_review_flag", "to_review_table", "from_review_table"]

# The columns of a review table. The first block is read-only context + prediction + triage;
# the reviewer fills the ``correct_*`` and ``reviewer_note`` columns (blank = accept as-is).
REVIEW_COLUMNS: tuple[str, ...] = (
    "doc_id", "position", "line_no", "ref", "token",       # identity / join key (read-only)
    "pred_lemma", "pred_pos", "pred_morph",                # machine prediction (read-only)
    "evidence_class", "source_citation", "needs_review",   # provenance + triage (read-only)
    "correct_lemma", "correct_pos", "correct_morph", "reviewer_note",  # reviewer fills
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
) -> int:
    """Write one reviewable row per WORD token of ``corpus`` to ``path`` (CSV, UTF-8 BOM).

    Each row carries the token's identity (``doc_id``/``position``/``line_no``/``ref``), the
    machine ``pred_lemma``/``pred_pos``/``pred_morph`` from its annotations, the
    ``evidence_class`` and a ``needs_review`` flag, the corpus citation, and blank
    ``correct_*`` / ``reviewer_note`` columns for the reviewer. With ``only_needs_review`` only
    the flagged rows are written. Returns the number of rows written.

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
            ])
    with atomic_path(path) as tmp:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(REVIEW_COLUMNS)
            w.writerows(rows)
    return len(rows)


# (review-table correction column -> its prediction column -> default annotation key)
_CORRECTIONS: tuple[tuple[str, str, str], ...] = (
    ("correct_lemma", "pred_lemma", "lemma"),
    ("correct_pos", "pred_pos", "upos"),
    ("correct_morph", "pred_morph", "morph"),
)


def _cell(row: dict[str, str | None], col: str) -> str:
    """A row cell, None-safe, whitespace-stripped, with the formula guard removed."""
    return _unguard_cell((row.get(col) or "").strip())


def _has_corrections(row: dict[str, str | None]) -> bool:
    return any(_cell(row, col) for col, _pred, _key in _CORRECTIONS)


def _morph_key(annotations: dict[str, str]) -> str:
    """The annotation key a morphology correction belongs under: the key that supplied the
    displayed prediction (``morph`` for NT Robinson, ``feats`` for UD), defaulting to ``morph``."""
    if annotations.get("morph"):
        return "morph"
    if annotations.get("feats"):
        return "feats"
    return "morph"


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
    (``morph`` or UD ``feats``). Rows left blank change nothing. A ``review:`` provenance
    note records how many tokens were corrected. The input corpus is not mutated."""
    # DictReader values are str, but a short/long row yields None under the restkey; keep the
    # map value type honest and read every cell None-safely. A malformed CSV (an unclosed
    # quote, an over-long field) surfaces as a clean ValueError, not a raw csv.Error.
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

    corrected = 0
    mismatched: list[str] = []
    applied_keys: set[tuple[str, int]] = set()
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
            if reviewer:
                edits["reviewed_by"] = reviewer
            note = _cell(crow, "reviewer_note")
            if note:
                edits["review_note"] = note
            new_tokens[i] = replace(tok, annotations={**tok.annotations, **edits})
            corrected += 1
        new_docs.append(replace(doc, tokens=new_tokens))

    if mismatched:
        shown = "; ".join(mismatched[:5]) + ("; …" if len(mismatched) > 5 else "")
        raise ValueError(
            f"review table {path} does not match this corpus ({len(mismatched)} corrected "
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
            f"review table {path}: {len(orphaned)} corrected row(s) match no token in this "
            f"corpus ({shown}) — pass the same corpus the table was exported from"
        )

    prov = corpus.provenance
    if prov is not None and corrected:  # a no-op apply leaves provenance untouched
        who = f" by {reviewer}" if reviewer else ""
        note = f"review: {corrected} tokens corrected{who} ({date.today().isoformat()})"
        prov = replace(prov, notes=prov.notes + (note,))
    from ..core.corpus import Corpus

    return Corpus(new_docs, corpus.sign_inventory, prov, corpus.script_id)
