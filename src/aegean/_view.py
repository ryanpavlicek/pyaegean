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
    from .greek.sentence_segmentation import SegmenterLike

__all__ = [
    "balance_rows",
    "format_confidence",
    "pipeline_rows",
    "pipeline_rows_from_records",
]


def _form_state_fields(state: Any) -> dict[str, Any]:
    """Return one token's editorial form state as JSON-ready ``form_*`` fields.

    The helper deliberately reads the typed state, never ``Token.annotations``.
    It is private because the public contract is the row keys, not this adapter;
    tabular, review, MCP, and TUI surfaces share it to prevent divergent
    serialization or a dataclass object leaking into JSON.
    """
    if state is None:
        return {}
    return {
        "form_diplomatic": state.diplomatic,
        "form_regularized": state.regularized,
        "form_normalized": state.normalized,
        "form_model_input": state.model_input,
        "form_model_input_ops": list(state.model_input_ops),
        "form_model_input_source": state.model_input_source,
        "form_segments": [segment.to_dict() for segment in state.segments],
        "form_editorial_status": state.editorial_status.value,
        "form_supplied_text": state.supplied_text,
        "form_unclear_text": state.unclear_text,
        "form_lost_text": state.lost_text,
        "form_supplied": state.supplied,
        "form_unclear": state.unclear,
        "form_lost": state.lost,
        "form_has_damage": state.has_damage,
        "form_has_uncertainty": state.has_uncertainty,
    }


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
    text: str,
    *,
    parse: bool = False,
    with_confidence: bool = False,
    sentence_policy: str = "default",
    segmenter: "SegmenterLike | None" = None,
) -> list[dict[str, Any]]:
    """One row per token from the Greek analysis pipeline.

    Wraps :func:`aegean.greek.pipeline`, mapping each `TokenRecord` to a row with
    ``sentence`` / ``index`` position, ``text``, ``upos``, ``lemma``,
    ``lemma_source`` (the lemma's exact evidence class), ``lemma_resolved``,
    ``lemma_verified``, ``review_recommended``, and the deprecated ``lemma_known``
    compatibility key, plus the optional
    ``head`` / ``relation`` / ``xpos`` / ``feats`` fields (filled by the parser or
    the neural pipeline, ``None`` otherwise). Source-aligned records additionally
    carry ``alignment_*`` fields for exact original text, code-point offsets,
    whitespace, normalization provenance, and stable source identity. Backends
    follow whatever is active, exactly as `pipeline` does.

    ``with_confidence=True`` threads through to `pipeline`; when it yields tokens
    that carry a calibrated confidence (the neural pipeline active AND a calibration
    loaded), every row additionally gains ``upos_confidence`` / ``lemma_confidence``
    (floats or ``None``). With the feature off, the default or the offline cascade
    where there is no model prediction to calibrate, those confidence keys are absent;
    source-alignment keys remain independent (see `pipeline_rows_from_records`)."""
    from .greek import pipeline

    return pipeline_rows_from_records(
        pipeline(
            text,
            parse=parse,
            with_confidence=with_confidence,
            sentence_policy=sentence_policy,
            segmenter=segmenter,
        )
    )


def pipeline_rows_from_records(records: "list[TokenRecord]") -> list[dict[str, Any]]:
    """The row mapping for `TokenRecord`s already produced by `greek.pipeline`.

    The CLI calls `pipeline` itself (to handle a not-loaded parser cleanly) and
    then maps here, so the CLI ``--json`` and the TUI workbench emit the exact
    same rows from the exact same code.

    Calibrated confidence is an optional COLUMN, not a per-row field: only when at
    least one record carries a non-``None`` ``upos_confidence`` / ``lemma_confidence``
    (the neural pipeline active, a calibration loaded, and the call asked for it) do
    all rows gain the two keys. The per-row value may still be ``None`` for a head
    the model does not itself produce (within the neural pipeline: an identity
    fall-through, punctuation, or an undecoded token; a lookup-composed lemma still
    carries one, since the calibration covers the model's internal training-form
    lookup). They are absent otherwise; alignment fields are added independently for
    records that carry a source mapping."""
    rows: list[dict[str, Any]] = [
        {
            "sentence": r.sentence,
            "index": r.index,
            "text": r.text,
            "upos": r.upos,
            "lemma": r.lemma,
            "lemma_source": r.lemma_source.value,
            "lemma_resolved": r.lemma_resolved,
            "lemma_verified": r.lemma_verified,
            "review_recommended": r.review_recommended,
            "lemma_known": r.lemma_resolved,
            "head": r.head,
            "relation": r.relation,
            "xpos": r.xpos,
            "feats": r.feats,
            "neural_analyzed": r.neural_analyzed,
            "analysis_complete": r.analysis_complete,
            "analysis_warning": r.analysis_warning,
            "analysis_receipt": (
                r.analysis_receipt.to_dict() if r.analysis_receipt is not None else None
            ),
        }
        for r in records
    ]
    for row, record in zip(rows, records):
        row.update(
            {
                "boundary_policy": record.boundary_policy,
                "boundary_policy_id": record.boundary_policy_id,
                "boundary_provenance": record.boundary_provenance,
                "boundary_confidence": record.boundary_confidence,
                "boundary_start_char": record.boundary_start_char,
                "boundary_end_char": record.boundary_end_char,
            }
        )
    for row, record in zip(rows, records):
        form_state = getattr(record, "form_state", None)
        if form_state is not None:
            row.update(_form_state_fields(form_state))
    if any(
        r.upos_confidence is not None or r.lemma_confidence is not None for r in records
    ):
        for row, r in zip(rows, records):
            row["upos_confidence"] = r.upos_confidence
            row["lemma_confidence"] = r.lemma_confidence
    if any(getattr(record, "lemma_source_path", None) is not None for record in records):
        for row, record in zip(rows, records):
            row["lemma_source_path"] = getattr(record, "lemma_source_path", None)
    if any(
        getattr(record, "token_confidence", None) is not None
        or getattr(record, "sentence_confidence", None) is not None
        for record in records
    ):
        for row, record in zip(rows, records):
            token_confidence = getattr(record, "token_confidence", None)
            sentence_confidence = getattr(record, "sentence_confidence", None)
            row["token_confidence"] = (
                token_confidence.to_dict() if token_confidence is not None else None
            )
            row["sentence_confidence"] = (
                sentence_confidence.to_dict()
                if sentence_confidence is not None
                else None
            )
    for row, record in zip(rows, records):
        alignment = record.alignment
        if alignment is None:
            continue
        row.update(
            {
                "alignment_document_id": alignment.document_id,
                "alignment_sentence_id": alignment.sentence_id,
                "alignment_source_token_id": alignment.source_token_id,
                "alignment_original_text": alignment.original_text,
                "alignment_start_char": alignment.start_char,
                "alignment_end_char": alignment.end_char,
                "alignment_whitespace_before": alignment.whitespace_before,
                "alignment_normalized_text": alignment.normalized_text,
                "alignment_normalization_ops": list(alignment.normalization_ops),
            }
        )
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
