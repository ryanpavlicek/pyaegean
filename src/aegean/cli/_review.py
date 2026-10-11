"""``aegean review`` — the human-in-the-loop review round-trip from the shell.

`export` writes a corpus's machine annotations to a reviewable CSV (one row per word: the
predicted lemma / POS / morphology, its evidence class, a ``needs_review`` flag, and blank
columns for corrections); `apply` reads a reviewed CSV back onto the corpus and saves the
corrected result, preserving each machine value and stamping the reviewer. See the
`aegean.io.review` module for the table format."""

from __future__ import annotations

import contextlib
import os
import shlex
import tempfile
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

import typer

from ._common import CORPUS_ARG, console, fail, load_corpus, table, write_corpus, writing
from ._greek import LEMMATIZER_OPT, NEURAL_LEMM_OPT, NEURAL_OPT, TAGGER_OPT, _activate

if TYPE_CHECKING:
    from ..core.corpus import Corpus


review_app = typer.Typer(
    help="Export annotations for optional field-level review, and apply decisions or corrections.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _apply_hint(
    corpus: str, output: Path, *, annotate: bool, tagger: bool, lemmatizer: bool,
    neural_lemmatizer: bool, neural: bool,
) -> str:
    args = ["aegean", "review", "apply", corpus, str(output), "-o", "corrected.json"]
    if annotate:
        args.append("--annotate")
        args.extend(flag for flag, enabled in (
            ("--tagger", tagger), ("--lemmatizer", lemmatizer),
            ("--neural-lemmatizer", neural_lemmatizer), ("--neural", neural),
        ) if enabled)
    return shlex.join(args)


def _save_annotation_snapshot(corpus: "Corpus", destination: Path) -> None:
    """Publish fully written JSON without replacing an existing user artifact."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".review-analysis-",
                                     suffix=".json", delete=False) as stream:
        staging = Path(stream.name)
    try:
        corpus.to_json(staging)
        # A hard link atomically fails if destination exists. Both paths have the
        # same parent/filesystem; unlinking staging leaves the published bytes.
        os.link(staging, destination)
    finally:
        staging.unlink(missing_ok=True)


@review_app.command()
def export(
    corpus: str = CORPUS_ARG,
    output: Path = typer.Option(..., "--output", "-o", help="Destination .csv review table."),
    selection: str = typer.Option(
        "all", "--selection",
        help="Rows to export: all, flagged (existing lemma review flag), unverified "
             "(any requested field lacks its own verified=true), or sample (seeded "
             "unflagged words). No confidence threshold.",
    ),
    fields: list[str] = typer.Option(["lemma"], "--field",
        help="Requested review field; repeat for lemma, pos, morph, head, deprel. Default lemma."),
    sample_size: int | None = typer.Option(None, "--sample-size",
        help="Number of unflagged words for --selection sample; requires a nonnegative integer."),
    seed: int = typer.Option(0, "--seed", help="Deterministic unflagged sample seed."),
    annotated_output: Path | None = typer.Option(None, "--annotated-output",
        help="Save generated analysis to a new .json file; default is a unique file beside the CSV. "
             "Requires --annotate; existing files are never replaced."),
    annotate: bool = typer.Option(
        False, "--annotate",
        help="Generate and save lemma/POS predictions; requested head/deprel also generates "
             "complete neural morphology/syntax. Apply the saved analysis shown in the hint. "
             "Omit to review existing source annotations.",
    ),
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
    reviewer: str = typer.Option("", "--reviewer", help="Pre-fill reviewer identity in the CSV."),
) -> None:
    """Write a CSV with lemma, POS, morphology, evidence, and optional field decisions.

    Fill ``decision_*`` with accept/correct/defer/reject; correct also requires a
    different ``correct_*`` value. Blank decisions preserve correction-only behavior.
    Add reviewer identity, notes, and evidence, then feed the table to
    ``aegean review apply``. Example: aegean review apply nt reviewed.csv -o nt-fixed.json"""
    if selection not in ("all", "flagged", "unverified", "sample"):
        raise fail("--selection must be 'all', 'flagged', 'unverified', or 'sample'")
    if not fields or len(set(fields)) != len(fields) or any(
        name not in ("lemma", "pos", "morph", "head", "deprel") for name in fields
    ):
        raise fail("--field must name distinct lemma, pos, morph, head, deprel fields")
    if selection == "sample" and (sample_size is None or sample_size < 0):
        raise fail("--selection sample requires a nonnegative --sample-size")
    if selection != "sample" and sample_size is not None:
        raise fail("--sample-size requires --selection sample")
    if annotated_output is not None and not annotate:
        raise fail("--annotated-output requires --annotate")
    if annotated_output is not None and annotated_output.suffix.lower() != ".json":
        raise fail("--annotated-output must be a new .json file")

    from aegean import greek
    from aegean.io import to_review_table

    if output.suffix.lower() != ".csv":
        raise fail("review export writes a .csv table (pass -o table.csv)")
    c = load_corpus(corpus)
    analysis_path: Path | None = None
    if annotate:
        _activate(tagger=tagger, lemmatizer=lemmatizer,
                  neural_lemmatizer=neural_lemmatizer, neural=neural)
        try:
            c = (greek.annotate_corpus(c, with_dependencies=True)
                 if set(fields) & {"head", "deprel"} else greek.annotate_corpus(c))
        except ValueError as exc:
            raise fail(f"could not annotate review source: {exc}") from None
        generation = next((token.annotations["analysis_generation"] for doc in c.documents
                           for token in doc.tokens if "analysis_generation" in token.annotations), uuid4().hex)
        analysis_path = annotated_output or output.with_name(f"{output.stem}.analysis-{generation}.json")
        try:
            _save_annotation_snapshot(c, analysis_path)
        except OSError as exc:
            raise fail(f"could not save annotated review source {analysis_path}: {exc}") from None
    try:
        with writing(output):
            n = to_review_table(
                c, output, selection=cast(Literal["all", "flagged", "unverified", "sample"], selection),
                reviewer=reviewer, fields=fields, sample_size=sample_size, seed=seed,
            )
    except (OSError, ValueError) as exc:
        if analysis_path is not None:
            with contextlib.suppress(OSError):
                analysis_path.unlink(missing_ok=True)
        raise fail(f"could not export review table: {exc}") from None
    except BaseException:
        if analysis_path is not None:
            with contextlib.suppress(OSError):
                analysis_path.unlink(missing_ok=True)
        raise
    print(f"wrote {n} review rows to {output}", file=sys.stderr)
    if analysis_path is not None:
        print(f"saved generated analysis to {analysis_path}", file=sys.stderr)
    hint = _apply_hint(str(analysis_path) if analysis_path is not None else corpus,
                       output, annotate=False, tagger=False, lemmatizer=False,
                       neural_lemmatizer=False, neural=False)
    print(f"record field decisions or corrections, then:  {hint}")


@review_app.command()
def apply(
    corpus: str = CORPUS_ARG,
    table: Path = typer.Argument(..., help="The reviewed .csv table (from `review export`)."),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Destination .json / .db for the corrected corpus."
    ),
    reviewer: str = typer.Option("", "--reviewer", help="Reviewer identity when the CSV leaves it blank."),
    annotate: bool = typer.Option(
        False, "--annotate",
        help="Generate a new analysis before applying old correction-only tables. "
             "Bound snapshots require the saved export analysis; a fresh run is stale even if values repeat.",
    ),
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
) -> None:
    """Apply optional field decisions and corrections, retaining predictions and history.

    Matches stable source-token IDs (legacy: document id + position) and verifies source
    alignment/text. Accept/correct verifies only the named field; defer/reject retains its
    prediction unverified. Blank rows never imply approval. Each field records its
    reviewer, note, and evidence; the original prediction and decision history survive.
    Pass the SAME corpus the table was exported from, and repeat ``--annotate`` (plus any
    backend flags) only for older correction-only tables. New exports bind the saved
    analysis; reannotation requires a fresh table even when predictions repeat."""
    from aegean import greek
    from aegean.io import from_review_table

    if not table.exists():
        raise fail(f"no review table at {table} (create one with `aegean review export`)")
    c = load_corpus(corpus)
    if annotate:
        _activate(tagger=tagger, lemmatizer=lemmatizer,
                  neural_lemmatizer=neural_lemmatizer, neural=neural)
        c = greek.annotate_corpus(c)
    try:
        corrected = from_review_table(table, c, reviewer=reviewer)
    except (OSError, ValueError, KeyError) as exc:
        raise fail(f"could not read review table {table}: {exc}") from None
    write_corpus(corrected, output)
    note = corrected.provenance.notes[-1] if corrected.provenance and corrected.provenance.notes else ""
    print(f"wrote {output}" + (f"  ({note})" if note.startswith("review:") else ""), file=sys.stderr)


@review_app.command()
def merge(
    tables: list[Path] = typer.Argument(
        ..., help="Two or more reviewed .csv tables — corrected copies of the SAME export."
    ),
    corpus: str = typer.Option(
        ..., "--corpus", "-c", help="The corpus the tables were exported from (id / path / '-')."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the merged (agreed) review table here (.csv)."
    ),
    on_conflict: str = typer.Option(
        "error", "--on-conflict",
        help="'error' (fail when reviewers disagree) or 'report' (list conflicts, keep the "
             "agreed subset).",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit the merge result as JSON."),
    annotate: bool = typer.Option(
        False, "--annotate", help="Generate an analysis for old correction-only tables; bound snapshots require the saved export analysis.",
    ),
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
) -> None:
    """Combine several reviewers' decisions and corrections on copies of one export.

    Field actions/values the reviewers agree on (or that only one proposed) are merged; a
    disagreement on the same token is listed, never silently resolved. Reviewer identity comes
    from each table's ``reviewer`` column (or the file name when blank). Write the agreed subset
    with ``-o merged.csv`` and apply it with ``aegean review apply``. Example:
    aegean review merge alice.csv bob.csv --corpus nt -o merged.csv --on-conflict report"""
    from aegean.io import merge_review_tables

    if on_conflict not in ("error", "report"):
        raise fail("--on-conflict must be 'error' or 'report'")
    if len(tables) < 2:
        raise fail("review merge needs at least two review tables to combine")
    for t in tables:
        if not t.exists():
            raise fail(f"no review table at {t}")
    c = load_corpus(corpus)
    if annotate:
        from aegean import greek

        _activate(tagger=tagger, lemmatizer=lemmatizer,
                  neural_lemmatizer=neural_lemmatizer, neural=neural)
        c = greek.annotate_corpus(c)
    # Always merge in report mode so the conflicts are structured and can be shown; the
    # --on-conflict flag then decides whether an unresolved conflict is a failure.
    try:
        merged = merge_review_tables(tables, c, on_conflict="report")
    except (OSError, ValueError, KeyError) as exc:
        raise fail(f"could not merge review tables: {exc}") from None

    if json_out:
        from ._common import emit_json

        emit_json({
            "tables": [str(t) for t in tables],
            "reviewers": list(merged.reviewers),
            "agreed_corrections": sum(
                any(row.get(column) for column in ("correct_lemma", "correct_pos", "correct_morph", "correct_head", "correct_deprel"))
                for row in merged.rows
            ),
            "agreed_review_rows": len(merged.rows),
            "conflicts": [
                {
                    "doc_id": k.doc_id, "position": k.position, "token": k.token,
                    "field": k.field,
                    "options": [
                        {"reviewer": o.reviewer, "value": o.value, "note": o.note,
                         "action": o.action, "evidence": o.evidence}
                        for o in k.options
                    ],
                }
                for k in merged.conflicts
            ],
        })
        if output is not None:
            with writing(output):
                merged.to_csv(output)
        if merged.conflicts and on_conflict == "error":
            raise typer.Exit(1)
        return

    if merged.conflicts:
        rows: list[list[str]] = []
        for k in merged.conflicts:
            for i, opt in enumerate(k.options):
                rows.append([
                    k.doc_id if i == 0 else "",
                    str(k.position) if i == 0 else "",
                    k.token if i == 0 else "",
                    k.field if i == 0 else "",
                    opt.reviewer, opt.action, opt.value, opt.note,
                ])
        table(
            "review conflicts (reviewers disagree — not applied)",
            ["doc", "pos", "token", "field", "reviewer", "action", "value", "note"],
            rows,
        )

    if output is not None:
        if output.suffix.lower() != ".csv":
            raise fail("review merge writes a .csv table (pass -o merged.csv)")
        with writing(output):
            merged.to_csv(output)
        print(f"wrote {len(merged.rows)} merged review rows to {output}", file=sys.stderr)
        hint = _apply_hint(corpus, output, annotate=annotate, tagger=tagger, lemmatizer=lemmatizer,
                           neural_lemmatizer=neural_lemmatizer, neural=neural)
        print(f"then:  {hint}")

    who = ", ".join(merged.reviewers) or "—"
    n_conf = len(merged.conflicts)
    console().print(
        f"merged {len(tables)} tables by {who}: {len(merged.rows)} agreed review row(s), "
        f"{n_conf} conflict(s)",
        style="dim", markup=False,
    )
    if n_conf and on_conflict == "error":
        raise fail(
            f"{n_conf} unresolved conflict(s) across reviewers; resolve them, or re-run with "
            f"--on-conflict report to keep the agreed subset"
        )
