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

__all__ = ["balance_rows", "pipeline_rows", "pipeline_rows_from_records"]


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


def pipeline_rows(text: str, *, parse: bool = False) -> list[dict[str, Any]]:
    """One row per token from the Greek analysis pipeline.

    Wraps :func:`aegean.greek.pipeline`, mapping each `TokenRecord` to a row with
    ``sentence`` / ``index`` position, ``text``, ``upos``, ``lemma``,
    ``lemma_source`` (the lemma's evidence class, e.g. ``"attested"`` / ``"neural"``
    / ``"rule"`` / ``"identity"``), ``lemma_known`` (``False`` marks a lemma to
    verify — an identity fall-through or unresolved miss), and the optional
    ``head`` / ``relation`` / ``xpos`` / ``feats`` fields (filled by the parser or
    the neural pipeline, ``None`` otherwise). Backends follow whatever is active,
    exactly as `pipeline` does."""
    from .greek import pipeline

    return pipeline_rows_from_records(pipeline(text, parse=parse))


def pipeline_rows_from_records(records: "list[TokenRecord]") -> list[dict[str, Any]]:
    """The row mapping for `TokenRecord`s already produced by `greek.pipeline`.

    The CLI calls `pipeline` itself (to handle a not-loaded parser cleanly) and
    then maps here, so the CLI ``--json`` and the TUI workbench emit the exact
    same rows from the exact same code."""
    return [
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
