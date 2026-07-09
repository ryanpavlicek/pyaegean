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

from ._common import CORPUS_ARG, fail, load_corpus, write_corpus, writing
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
    print(f"correct the columns, then:  aegean review apply {corpus} {output} -o corrected.json")


@review_app.command()
def apply(
    corpus: str = CORPUS_ARG,
    table: Path = typer.Argument(..., help="The reviewed .csv table (from `review export`)."),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Destination .json / .db for the corrected corpus."
    ),
    reviewer: str = typer.Option("", "--reviewer", help="Name stamped on each correction."),
) -> None:
    """Apply a reviewed table's corrections back onto ``corpus`` and save the result.

    Matches rows to tokens by document id + position; each corrected field keeps the machine
    value under ``<field>__pred`` and records the reviewer. Pass the SAME corpus the table was
    exported from."""
    from aegean.io import from_review_table

    if not table.exists():
        raise fail(f"no review table at {table} (create one with `aegean review export`)")
    c = load_corpus(corpus)
    try:
        corrected = from_review_table(table, c, reviewer=reviewer)
    except (OSError, ValueError, KeyError) as exc:
        raise fail(f"could not read review table {table}: {exc}") from None
    write_corpus(corrected, output)
    note = corrected.provenance.notes[-1] if corrected.provenance and corrected.provenance.notes else ""
    print(f"wrote {output}" + (f"  ({note})" if note.startswith("review:") else ""), file=sys.stderr)
