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

# Evidence classes that mean "not a grounded analysis" (see aegean.greek.LemmaSource).
_LOW_CONFIDENCE: frozenset[str] = frozenset({"identity", "unresolved"})


def needs_review_flag(annotations: dict[str, str], *, source_key: str = "lemma_source") -> bool:
    """Whether a token's annotation should be verified by a human.

    True when its evidence class (``annotations[source_key]``, e.g. from
    `aegean.greek.annotate.annotate_corpus`) is a low-confidence class (``identity`` /
    ``unresolved``); failing that, when ``lemma_known`` is the string ``"false"``. A token
    that carries neither signal (for example a gold-annotated corpus) is **not** flagged."""
    src = annotations.get(source_key)
    if src is not None:
        return src in _LOW_CONFIDENCE
    return annotations.get("lemma_known", "").lower() == "false"


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
    the flagged rows are written. Returns the number of rows written."""
    from ..core.model import TokenKind

    prov = corpus.provenance
    citation = (prov.citation or prov.source) if prov is not None else ""
    rows: list[list[str]] = []
    for doc in corpus.documents:
        ref_base = doc.id
        for tok in doc.tokens:
            if tok.kind is not TokenKind.WORD:
                continue
            a = tok.annotations
            flag = needs_review_flag(a, source_key=source_key)
            if only_needs_review and not flag:
                continue
            rows.append([
                doc.id,
                str(tok.position if tok.position is not None else ""),
                str(tok.line_no if tok.line_no is not None else ""),
                a.get("ref", ref_base),
                tok.text,
                a.get("lemma", ""),
                a.get("upos", ""),
                _morph(a),
                a.get(source_key, ""),
                citation,
                "yes" if flag else "",
                "", "", "", "",  # correct_lemma, correct_pos, correct_morph, reviewer_note
            ])
    with atomic_path(path) as tmp:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(REVIEW_COLUMNS)
            w.writerows(rows)
    return len(rows)


# (review-table field -> annotation key) for the three correctable columns
_CORRECTIONS: tuple[tuple[str, str], ...] = (
    ("correct_lemma", "lemma"), ("correct_pos", "upos"), ("correct_morph", "morph"),
)


def from_review_table(path: str | Path, corpus: "Corpus", *, reviewer: str = "") -> "Corpus":
    """Read reviewer corrections from ``path`` back onto ``corpus``, returning a NEW corpus.

    Rows are matched to tokens by ``doc_id`` + ``position``. For each row whose ``correct_*``
    differs from the machine value, the token's annotation for that field is set to the
    corrected value, the machine value is preserved under ``<field>__pred``, and the token is
    stamped ``reviewed_by`` / ``review_status="corrected"`` (plus ``review_note`` when the
    reviewer left one). Rows left blank change nothing. A ``review:`` provenance note records
    how many tokens were corrected. The input corpus is not mutated."""
    # DictReader values are str, but a short/long row yields None under the restkey; keep the
    # map value type honest and read every cell None-safely.
    corrections: dict[tuple[str, int], dict[str, str | None]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pos = (row.get("position") or "").strip()
            if not pos.isdigit():
                continue
            corrections[(row.get("doc_id") or "", int(pos))] = row

    corrected = 0
    new_docs = []
    for doc in corpus.documents:
        new_tokens = list(doc.tokens)
        for i, tok in enumerate(doc.tokens):
            if tok.position is None:
                continue
            crow = corrections.get((doc.id, tok.position))
            if crow is None:
                continue
            edits: dict[str, str] = {}
            for col, key in _CORRECTIONS:
                val = (crow.get(col) or "").strip()
                if val and val != tok.annotations.get(key, ""):
                    edits[key] = val
                    edits[f"{key}__pred"] = tok.annotations.get(key, "")
            if not edits:
                continue
            edits["review_status"] = "corrected"
            if reviewer:
                edits["reviewed_by"] = reviewer
            note = (crow.get("reviewer_note") or "").strip()
            if note:
                edits["review_note"] = note
            new_tokens[i] = replace(tok, annotations={**tok.annotations, **edits})
            corrected += 1
        new_docs.append(replace(doc, tokens=new_tokens))

    prov = corpus.provenance
    if prov is not None and corrected:  # a no-op apply leaves provenance untouched
        who = f" by {reviewer}" if reviewer else ""
        note = f"review: {corrected} tokens corrected{who} ({date.today().isoformat()})"
        prov = replace(prov, notes=prov.notes + (note,))
    from ..core.corpus import Corpus

    return Corpus(new_docs, corpus.sign_inventory, prov, corpus.script_id)
