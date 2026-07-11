"""``aegean review`` — the human-in-the-loop review round-trip from the shell.

`export` writes a corpus's machine annotations to a reviewable CSV (one row per word: the
predicted lemma / POS / morphology, its evidence class, a ``needs_review`` flag, and blank
columns for corrections); `apply` reads a reviewed CSV back onto the corpus and saves the
corrected result, preserving each machine value and stamping the reviewer. See the
`aegean.io.review` module for the table format."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ._common import CORPUS_ARG, console, fail, load_corpus, table, write_corpus, writing
from ._greek import LEMMATIZER_OPT, NEURAL_LEMM_OPT, NEURAL_OPT, TAGGER_OPT, _activate

review_app = typer.Typer(
    help="Export machine annotations for human review, and apply the corrections back.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@review_app.command()
def export(
    corpus: str = CORPUS_ARG,
    output: Path = typer.Option(..., "--output", "-o", help="Destination .csv review table."),
    only_needs_review: bool = typer.Option(
        False, "--only-needs-review",
        help="Write only the tokens flagged for review (low-confidence lemmas).",
    ),
    annotate: bool = typer.Option(
        False, "--annotate",
        help="Fill lemma/POS annotations from the pipeline first — needed for a corpus that "
             "has none (any imported text; the NT already carries gold annotations).",
    ),
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
) -> None:
    """Write a reviewable CSV table: one row per word token with the machine lemma, POS,
    morphology, evidence class, and a needs-review flag, plus blank correction columns.

    Open it in a spreadsheet, fill the ``correct_*`` columns, then feed it to
    ``aegean review apply``. Example: aegean review apply nt reviewed.csv -o nt-fixed.json"""
    from aegean import greek
    from aegean.io import to_review_table

    if output.suffix.lower() != ".csv":
        raise fail("review export writes a .csv table (pass -o table.csv)")
    c = load_corpus(corpus)
    if annotate:
        _activate(tagger=tagger, lemmatizer=lemmatizer,
                  neural_lemmatizer=neural_lemmatizer, neural=neural)
        c = greek.annotate_corpus(c)
    with writing(output):
        n = to_review_table(c, output, only_needs_review=only_needs_review)
    print(f"wrote {n} review rows to {output}", file=sys.stderr)
    # When the corpus was annotated for this export, apply must annotate too, or the
    # accepted machine values would be missing from the corrected corpus.
    extra = " --annotate" if annotate else ""
    print(
        f"correct the columns, then:  aegean review apply {corpus} {output} "
        f"-o corrected.json{extra}"
    )


@review_app.command()
def apply(
    corpus: str = CORPUS_ARG,
    table: Path = typer.Argument(..., help="The reviewed .csv table (from `review export`)."),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Destination .json / .db for the corrected corpus."
    ),
    reviewer: str = typer.Option("", "--reviewer", help="Name stamped on each correction."),
    annotate: bool = typer.Option(
        False, "--annotate",
        help="Fill machine annotations from the pipeline before applying — pass it whenever "
             "the export used it, so accepted (uncorrected) predictions land in the corrected "
             "corpus too, not only the reviewer's changes.",
    ),
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
) -> None:
    """Apply a reviewed table's corrections back onto ``corpus`` and save the result.

    Matches rows to tokens by document id + position, verifying each row's exported token
    text against the corpus (a mismatch is an error, never a silent wrong-word edit); each
    corrected field keeps the machine value under ``<field>__pred`` and records the reviewer.
    Pass the SAME corpus the table was exported from, and repeat ``--annotate`` (plus any
    backend flags) if the export used it."""
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
) -> None:
    """Combine several reviewers' corrected copies of one export into one review table.

    Corrections the reviewers agree on (or that only one made) are merged; a genuine
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
            "agreed_corrections": len(merged.rows),
            "conflicts": [
                {
                    "doc_id": k.doc_id, "position": k.position, "token": k.token,
                    "field": k.field,
                    "options": [
                        {"reviewer": o.reviewer, "value": o.value, "note": o.note}
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
                    opt.reviewer, opt.value, opt.note,
                ])
        table(
            "review conflicts (reviewers disagree — not applied)",
            ["doc", "pos", "token", "field", "reviewer", "value", "note"],
            rows,
        )

    if output is not None:
        if output.suffix.lower() != ".csv":
            raise fail("review merge writes a .csv table (pass -o merged.csv)")
        with writing(output):
            merged.to_csv(output)
        print(f"wrote {len(merged.rows)} merged review rows to {output}", file=sys.stderr)
        print(f"then:  aegean review apply {corpus} {output} -o corrected.json")

    who = ", ".join(merged.reviewers) or "—"
    n_conf = len(merged.conflicts)
    console().print(
        f"merged {len(tables)} tables by {who}: {len(merged.rows)} agreed correction(s), "
        f"{n_conf} conflict(s)",
        style="dim", markup=False,
    )
    if n_conf and on_conflict == "error":
        raise fail(
            f"{n_conf} unresolved conflict(s) across reviewers; resolve them, or re-run with "
            f"--on-conflict report to keep the agreed subset"
        )
