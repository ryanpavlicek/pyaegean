"""Benchmark and evaluation reproduction command (``aegean greek eval``)."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from pathlib import Path

import typer

from ._common import (
    JSON_OPT,
    RESULT_OPT,
    emit_result,
    fail,
    table,
)

_TAGGER_OPT = typer.Option(False, "--tagger", help="Activate the generalizing POS tagger (trains from the AGDT on first use).")
_LEMMATIZER_OPT = typer.Option(False, "--lemmatizer", help="Activate the edit-tree lemmatizer (trains from the AGDT on first use).")
_NEURAL_LEMM_OPT = typer.Option(False, "--neural-lemmatizer", help="Activate the seq2seq lemmatizer (~232 MB model, \\[neural] extra).")
_NEURAL_OPT = typer.Option(False, "--neural", help="Activate the joint neural pipeline (~173 MB model, \\[neural] extra).")


def evaluate(
    target: str = typer.Argument(
        ...,
        help="ud, proiel, nt, papygreek, dbbe, verse, tagger, lemmatizer, or parser "
        "(heavy: fetches/trains).",
    ),
    fold: str = typer.Option(
        "perseus", "--fold", help="For ud: which UD Ancient Greek fold, perseus or proiel."
    ),
    fold_alias: str | None = typer.Option(
        None, "--treebank", hidden=True, help="Deprecated alias for --fold."
    ),
    split: str = typer.Option("test", "--split", help="For ud: dev or test."),
    track: str = typer.Option(
        "all", "--track",
        help="For verse: tragedy or all. Small-sample, wide CIs.",
    ),
    layer: str = typer.Option(
        "reg", "--layer",
        help="For papygreek: reg (the regularized reading behind the published numbers) or "
             "orig (the raw diplomatic orthography — same sentences and gold, harder input).",
    ),
    bootstrap: bool = typer.Option(
        False, "--bootstrap", help="For ud: percentile CIs over the fold's sentences (slower)."
    ),
    drift: bool = typer.Option(
        False, "--drift",
        help="For ud/proiel/nt: an error analysis (POS confusion matrix, per-POS accuracy, "
             "lemma confusions) instead of the aggregate score. For papygreek: the "
             "UPOS/XPOS convention decomposition (coordinator / common-gender / '_'-encoding "
             "vs real error).",
    ),
    by_genre: bool = typer.Option(
        False, "--by-genre",
        help="For ud: score the fold sliced by literary genre (epic/tragedy/prose, from the "
             "sent_id author). Note: the leakage-clean Perseus test fold is prose-only.",
    ),
    batch_size: int | None = typer.Option(
        None, "--batch-size",
        help="For ud/nt/papygreek/dbbe/verse with the neural pipeline: run the encoder over N "
             "sentences at a time (faster on long folds; the published numbers use the "
             "sequential default).",
    ),
    documentary: bool = typer.Option(
        False, "--documentary",
        help="For ud/nt/papygreek/verse score runs: apply the opt-in documentary-Koine post-"
             "processing over the neural pipeline (closed-class coordinator reconciliation + "
             "offline lemma OOV rescue). Off by default; a separate opt-in variant, not the "
             "published number.",
    ),
    neural: bool = _NEURAL_OPT,
    tagger: bool = _TAGGER_OPT,
    lemmatizer: bool = _LEMMATIZER_OPT,
    neural_lemmatizer: bool = _NEURAL_LEMM_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Reproduce pyaegean's measured numbers (official evaluators, fetched gold data).

    `ud` scores the active pipeline on a UD Ancient Greek fold with the official
    CoNLL 2018 evaluator; `proiel` is the neutral out-of-AGDT check; the rest
    are the leakage-free held-out evaluations of the trainable backends."""
    from aegean import greek
    from . import _greek

    if fold_alias is not None:
        # On every other greek command --treebank is the boolean AGDT activation;
        # here it was the fold selector. Deprecated in 0.17, removal per policy.
        print("aegean: `greek eval --treebank` is deprecated; use --fold", file=sys.stderr)
        fold = fold_alias
    if fold not in ("perseus", "proiel"):
        raise fail("--fold must be perseus or proiel")
    if split not in ("dev", "test"):
        raise fail("--split must be dev or test")
    if track != "all" and target != "verse":
        raise fail("--track applies to `eval verse` (tragedy/all)")
    if track == "hexameter":
        # the fold is tragedy-only since v2: the sliver once labeled hexameter was the
        # Maximus prose paraphrase (see docs/benchmarks.md).
        raise fail("--track hexameter was removed: the sliver was the Maximus prose "
                   "paraphrase, not verse; the fold is tragedy-only (--track tragedy or all)")
    if track not in ("all", "tragedy"):
        raise fail("--track must be tragedy or all")
    if layer not in ("reg", "orig"):
        raise fail("--layer must be reg or orig")
    if layer != "reg" and target != "papygreek":
        raise fail("--layer applies to `eval papygreek` (reg/orig)")
    if layer == "orig" and drift:
        # --drift is the convention decomposition, which reproduces the published (reg)
        # numbers and runs sequentially on the reg fold; it has no orig variant.
        raise fail("--layer orig does not combine with --drift (the convention decomposition "
                   "is the reg-fold reproduction)")
    if target == "dbbe" and (drift or by_genre or bootstrap):
        # the DBBE fold carries no dependency trees and is a single small register row: it is
        # tagging-only, so the drift decomposition / genre slices / bootstrap CIs do not apply.
        raise fail("`eval dbbe` is tagging-only (the DBBE fold has no dependency trees): it has "
                   "no --drift/--by-genre/--bootstrap; run the plain score (optionally --batch-size)")
    if target == "verse" and drift:
        # a small-sample genre fold: no convention decomposition, just the score. Rejected here
        # so an invalid flag never triggers the model load.
        raise fail("`eval verse` has no --drift decomposition; run the plain score "
                   "(optionally --track tragedy)")
    if target in ("papygreek", "nt") and (bootstrap or by_genre):
        # --bootstrap (percentile CIs) and --by-genre (author→genre slices) are ud-only.
        raise fail(f"`eval {target}` has no --bootstrap/--by-genre (those are ud-only): run "
                   "the score (--drift/--documentary/--batch-size apply)")
    if batch_size is not None:
        if batch_size < 1:
            raise fail("--batch-size must be at least 1")
        # bootstrap_ud and the error analyses run their own inference loops without a
        # batching hook; --by-genre threads batch_size through pipeline_conllu like ud.
        if (
            target not in ("ud", "nt", "papygreek", "dbbe", "verse")
            or drift or (bootstrap and not by_genre)
        ):
            raise fail("--batch-size applies to `eval ud`, `eval nt`, `eval papygreek`, "
                       "`eval dbbe`, and `eval verse` score runs (not --drift/--bootstrap)")
    if documentary and (
        target not in ("ud", "nt", "papygreek", "verse") or drift or bootstrap or by_genre
    ):
        raise fail("--documentary applies to `eval ud`, `eval nt`, `eval papygreek`, and "
                   "`eval verse` score runs (not --drift/--bootstrap/--by-genre); it "
                   "post-processes the neural pipeline's output.")
    _greek._activate(
        tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
    )

    restore_reconciliation_off = False
    restore_rescue_off = False
    restore_paradigms_off = False
    restore_neural_off = False

    def _apply_documentary() -> None:
        # The two opt-in documentary levers post-process the neural pipeline, so it must be
        # active (ud does not auto-activate it — force it on here); reconciliation is the
        # conservative default (X/b drift only). Toggled off again before the result is emitted.
        from aegean.greek import joint, paradigms

        nonlocal restore_reconciliation_off, restore_rescue_off
        nonlocal restore_paradigms_off, restore_neural_off
        if joint.active() is None:
            _greek._activate(neural=True)
            restore_neural_off = True
        # Preserve pre-existing session state: the REPL can keep these levers active
        # deliberately, and a one-shot eval must not disable or reconfigure them.
        if not greek.documentary_reconciliation_active():
            greek.use_documentary_reconciliation()
            restore_reconciliation_off = True
        if not greek.documentary_lemma_rescue_active():
            greek.use_documentary_lemma_rescue()
            restore_rescue_off = True
        # Lever B consults the paradigm table, so activate it here too.  The
        # current work-disjoint fold shows no additional lemma lift from this
        # lever, but the command still exposes the complete configured profile.
        restore_paradigms_off = paradigms.active() is None
        if restore_paradigms_off:
            greek.use_paradigms()

    @contextlib.contextmanager
    def _documentary_scope() -> Iterator[None]:
        """Apply the per-run levers and restore every prior state, even on failure."""
        try:
            if documentary:
                _apply_documentary()
            yield
        finally:
            if restore_reconciliation_off:
                greek.disable_documentary_reconciliation()
            if restore_rescue_off:
                greek.disable_documentary_lemma_rescue()
            if restore_paradigms_off:
                greek.disable_paradigms()
            if restore_neural_off:
                greek.disable_neural_pipeline()

    def emit_drift(report: object) -> None:  # ErrorAnalysis -> --json dict / text summary
        if emit_result(report.as_dict(), json_output=json_out, output=output):  # type: ignore[attr-defined]
            return
        print(report.summary())  # type: ignore[attr-defined]

    def live_progress(done: int, total: int) -> None:
        # A single repainted stderr line, TTY-only: piped/captured runs (CI, --json > f)
        # stay clean, but a scholar watching the ~1 h NT eval sees it moving.
        if not sys.stderr.isatty():
            return
        step = max(1, total // 200)
        if done % step and done != total:
            return
        end = "\n" if done == total else ""
        print(f"\r  scoring {done:,}/{total:,} sentences ({100 * done // total}%)",
              file=sys.stderr, end=end, flush=True)

    result: object
    if target == "ud":
        if drift:
            if fold == "proiel":
                # the PROIEL drift view includes the convention decomposition: the
                # measured split of the UFeats/LAS gaps into scheme-absent vs shared
                _greek._activate(neural=True)
                emit_drift(greek.proiel_convention_report(split=split, progress=live_progress))
                return
            emit_drift(greek.ud_error_analysis(treebank=fold, split=split))
            return
        if by_genre:
            # batch_size is forwarded only when given, so the default invocation stays
            # identical to the recorded protocol's call (same pattern below).
            if batch_size is not None:
                by = greek.evaluate_by_genre(
                    fold, split, bootstrap=bootstrap, progress=live_progress,
                    batch_size=batch_size,
                )
            else:
                by = greek.evaluate_by_genre(fold, split, bootstrap=bootstrap, progress=live_progress)
            unmapped = by.pop("_unmapped", {}).get("authors", [])
            if emit_result({**by, "_unmapped": unmapped}, json_output=json_out, output=output):
                return
            rows = []
            for genre, d in by.items():
                flag = " (thin)" if d.get("thin") else ""
                cells = [f"{k}={d[k]}" for k in ("upos", "lemma", "uas", "las") if k in d]
                rows.append([f"{genre}{flag}", str(d["n_sentences"]), str(d["n_words"]), ", ".join(cells)])
            table(f"eval ud {fold}/{split} by genre", ["genre", "sents", "words", "metrics"], rows)
            if unmapped:
                print(f"unmapped authors (counted as 'other'): {', '.join(unmapped)}", file=sys.stderr)
            return
        with _documentary_scope():
            if bootstrap:
                cis = greek.bootstrap_ud(treebank=fold, split=split)
                result = {
                    k: f"{ci.estimate:.4f} [{ci.low:.4f}, {ci.high:.4f}]"
                    for k, ci in cis.items()
                }
            elif batch_size is not None:
                result = greek.evaluate_on_ud(
                    treebank=fold, split=split, progress=live_progress, batch_size=batch_size
                )
            else:
                result = greek.evaluate_on_ud(treebank=fold, split=split, progress=live_progress)
    elif target == "proiel":
        if drift:
            emit_drift(greek.proiel_error_analysis())
            return
        result = greek.evaluate_on_proiel(progress=live_progress)
    elif target == "nt":
        _greek._activate(neural=True)  # the NT fold reports the shipped neural model's number
        if drift:
            emit_drift(greek.nt_error_analysis())
            return
        with _documentary_scope():
            if batch_size is not None:
                result = greek.evaluate_on_nt(progress=live_progress, batch_size=batch_size)
            else:
                result = greek.evaluate_on_nt(progress=live_progress)
    elif target == "papygreek":
        _greek._activate(neural=True)  # the documentary-Koine fold reports the shipped neural model
        if drift:
            # the convention decomposition: the measured split of the UPOS/XPOS gaps into
            # coordinator / common-gender / '_'-encoding convention vs residual real error.
            # One canonical SEQUENTIAL run (batch-32 is not prediction-identical on this fold).
            emit_drift(greek.papygreek_convention_report(progress=live_progress))
            return
        with _documentary_scope():
            # layer is forwarded only when non-default, so the reg (published-protocol) call
            # stays byte-identical to evaluate_on_papygreek(progress=...); batch_size likewise.
            if layer != "reg":
                if batch_size is not None:
                    result = greek.evaluate_on_papygreek(
                        layer=layer, progress=live_progress, batch_size=batch_size
                    )
                else:
                    result = greek.evaluate_on_papygreek(layer=layer, progress=live_progress)
            elif batch_size is not None:
                result = greek.evaluate_on_papygreek(
                    progress=live_progress, batch_size=batch_size
                )
            else:
                result = greek.evaluate_on_papygreek(progress=live_progress)
    elif target == "dbbe":
        # tagging-only Byzantine-verse fold, reported by the shipped neural model; --documentary
        # (a documentary-Koine lever) is rejected above, so no post-processing branch here.
        _greek._activate(neural=True)
        if batch_size is not None:
            result = greek.evaluate_on_dbbe(progress=live_progress, batch_size=batch_size)
        else:
            result = greek.evaluate_on_dbbe(progress=live_progress)
    elif target == "verse":
        _greek._activate(neural=True)  # the verse fold reports the shipped neural model's number
        tr = None if track == "all" else track
        with _documentary_scope():
            if batch_size is not None:
                result = greek.evaluate_on_verse(
                    track=tr, progress=live_progress, batch_size=batch_size
                )
            else:
                result = greek.evaluate_on_verse(track=tr, progress=live_progress)
    elif target == "tagger":
        result = greek.evaluate_tagger()
    elif target == "lemmatizer":
        result = greek.evaluate_lemmatizer()
    elif target == "parser":
        _greek._activate(parser=True)
        result = greek.evaluate_parser()
    else:
        raise fail("target must be ud, proiel, nt, papygreek, dbbe, verse, tagger, lemmatizer, "
                   "or parser")
    if emit_result(result, json_output=json_out, output=output):
        return
    if isinstance(result, dict):
        table(f"eval: {target}", ["metric", "value"], [[k, str(v)] for k, v in result.items()])
    else:
        print(result)

def register(greek_app: typer.Typer) -> None:
    """Attach the ``eval`` command to ``greek_app``."""
    greek_app.command("eval")(evaluate)
