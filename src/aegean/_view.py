"""Canonical library-to-row mappings shared by the CLI and the terminal UI.

Two surfaces render the same numbers: ``aegean balance`` / ``aegean greek
pipeline`` on the command line, and the ``aegean tui`` document-analysis and
Greek-workbench panes. When each surface shapes rows from the raw dataclasses on
its own, the two drift (the workbench cross-surface-drift lesson). These
functions are the single source of those row dicts, so a CLI cell and a TUI cell
are mathematically incapable of disagreeing.

Both return plain ``list[dict]`` with JSON-ready values, so the CLI can emit them
as ``--json`` unchanged and the TUI can drop them straight into a table. Nothing
here imports typer, rich, or textual: it is the pure seam both front ends call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # type-only: keep this module import-clean
    from .core.model import Document
    from .greek.pipeline import TokenRecord

__all__ = [
    "balance_rows",
    "format_confidence",
    "pipeline_rows",
    "pipeline_rows_from_records",
]


def balance_rows(document: "Document") -> list[dict[str, Any]]:
    """Every reconciled total line of one document as row dicts.

    Wraps :func:`aegean.analysis.balance_check`, mapping each `BalanceCheck` to
    the exact row the ``aegean balance`` command emits: ``doc``, ``marker``
    (KU-RO / TO-SO), ``stated`` (the written total), ``computed`` (the summed
    items), ``difference`` (computed minus stated), ``items`` (item count), and
    ``balances`` (whether the two agree). Empty when the document states no
    total.

    Exploratory: on the undeciphered scripts, section boundaries are heuristic
    and the metrology is contested, so a "balance" is evidence to weigh, not a
    reading."""
    from .analysis import balance_check

    return [
        {
            "doc": document.id,
            "marker": chk.marker,
            "stated": chk.stated_total,
            "computed": chk.computed_sum,
            "difference": chk.difference,
            "items": chk.item_count,
            "balances": chk.balances,
        }
        for chk in balance_check(document)
    ]


def pipeline_rows(
    text: str, *, parse: bool = False, with_confidence: bool = False
) -> list[dict[str, Any]]:
    """One row per token from the Greek analysis pipeline.

    Wraps :func:`aegean.greek.pipeline`, mapping each `TokenRecord` to a row with
    ``sentence`` / ``index`` position, ``text``, ``upos``, ``lemma``,
    ``lemma_source`` (the lemma's evidence class: ``"attested"`` / ``"neural"``
    / ``"rule"`` / ``"seed"`` / ``"paradigm"`` / ``"identity"`` / ``"unresolved"`` /
    ``"punct"``), ``lemma_known`` (``False`` marks a lemma to
    verify — an identity fall-through or unresolved miss), and the optional
    ``head`` / ``relation`` / ``xpos`` / ``feats`` fields (filled by the parser or
    the neural pipeline, ``None`` otherwise). Backends follow whatever is active,
    exactly as `pipeline` does.

    ``with_confidence=True`` threads through to `pipeline`; when it yields tokens
    that carry a calibrated confidence (the neural pipeline active AND a calibration
    loaded), every row additionally gains ``upos_confidence`` / ``lemma_confidence``
    (floats or ``None``). With the feature off — the default, or the offline cascade
    where there is no model prediction to calibrate — those keys are absent, so the
    rows are byte-identical to before (see `pipeline_rows_from_records`)."""
    from .greek import pipeline

    return pipeline_rows_from_records(
        pipeline(text, parse=parse, with_confidence=with_confidence)
    )


def pipeline_rows_from_records(records: "list[TokenRecord]") -> list[dict[str, Any]]:
    """The row mapping for `TokenRecord`s already produced by `greek.pipeline`.

    The CLI calls `pipeline` itself (to handle a not-loaded parser cleanly) and
    then maps here, so the CLI ``--json`` and the TUI workbench emit the exact
    same rows from the exact same code.

    Calibrated confidence is an optional COLUMN, not a per-row field: only when at
    least one record carries a non-``None`` ``upos_confidence`` / ``lemma_confidence``
    (the neural pipeline active, a calibration loaded, and the call asked for it) do
    all rows gain the two keys — the per-row value may still be ``None`` for a head
    the model does not itself produce (within the neural pipeline: an identity
    fall-through, punctuation, or an undecoded token; a lookup-composed lemma still
    carries one, since the calibration covers the model's internal training-form
    lookup). Absent otherwise, so a call without confidence produces byte-identical
    rows to a build without the feature."""
    rows: list[dict[str, Any]] = [
        {
            "sentence": r.sentence,
            "index": r.index,
            "text": r.text,
            "upos": r.upos,
            "lemma": r.lemma,
            "lemma_source": r.lemma_source.value,
            "lemma_known": r.lemma_known,
            "head": r.head,
            "relation": r.relation,
            "xpos": r.xpos,
            "feats": r.feats,
        }
        for r in records
    ]
    if any(
        r.upos_confidence is not None or r.lemma_confidence is not None for r in records
    ):
        for row, r in zip(rows, records):
            row["upos_confidence"] = r.upos_confidence
            row["lemma_confidence"] = r.lemma_confidence
    return rows


def format_confidence(
    upos_confidence: float | None, lemma_confidence: float | None
) -> str:
    """Render a token's two calibrated confidences as one compact cell.

    ``"<upos>/<lemma>"`` to two decimals, with ``"—"`` for a head that carries no
    calibrated number (within the neural pipeline, a lemma the model does not itself
    produce: an identity fall-through, punctuation, or an undecoded token; a
    lookup-composed lemma still carries one, since the calibration covers the model's
    internal training-form lookup), and ``"—"`` alone when neither head has one.
    Shared so the CLI pipeline table, the TUI workbench line, and the reader's
    analysis table format the confidence column identically."""
    if upos_confidence is None and lemma_confidence is None:
        return "—"

    def _one(v: float | None) -> str:
        return f"{v:.2f}" if v is not None else "—"

    return f"{_one(upos_confidence)}/{_one(lemma_confidence)}"
