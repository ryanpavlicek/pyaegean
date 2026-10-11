# Independent review

## Reviewing annotations while researching

Annotation review is optional. Search, first-pass analysis, vocabulary exploration,
and provisional exports do not require approval. Review the fields that support
your research claim; also sample unflagged material, since a low-risk flag does
not establish correctness.

```bash
aegean review export corpus.json -o review.csv --selection unverified --reviewer Alice
# Fill field decisions in the CSV, then apply them to the same corpus.
aegean review apply corpus.json review.csv -o reviewed.json
```

Use `--selection all` for every eligible word or `--selection flagged` for the
existing review flag. `unverified` checks the requested fields, with lemma as the
default. Repeat `--field` to select lemma, POS, morphology, dependency head, or
dependency relation. Rows record why they were included. A reproducible sample of
unflagged material helps check what the flag misses:

```bash
aegean review export corpus.json -o grammar.csv --selection unverified --field pos --field morph
aegean review export corpus.json -o sample.csv --selection sample --sample-size 40 --seed 17
```

To generate predictions first, add `--annotate` and backend flags such as
`--neural` to **export**. Export saves the actual annotated corpus beside the CSV
and prints its path. `--annotated-output analysis.json` chooses that path; an
existing file is refused. Apply and merge against this saved analysis. Running
annotation again creates a new analysis even if its predicted words agree, so a
fresh run cannot stand in for the saved review source. Printed commands quote
paths for a POSIX shell.

Set `decision_lemma`, `decision_pos`, or `decision_morph` independently. Dependency
review also provides `decision_head` and `decision_deprel`:

| Decision | What to enter | Result |
| --- | --- | --- |
| `accept` | Leave the corresponding `correct_*` cell blank. | Verify the unchanged, existing prediction for this field. |
| `correct` | Enter a different, nonempty value in `correct_*`. | Save and verify the correction while preserving the original prediction. |
| `defer` | Leave `correct_*` blank. | Retain the prediction and mark this field unverified for later work. |
| `reject` | Leave `correct_*` blank. | Retain the rejected prediction as evidence and mark this field unverified; no replacement is inferred. |
| Blank | Optionally enter a correction. | Preserve the older correction-only behavior; an unchanged value or blank row conveys no approval. |

`reviewer` identifies the scholar; `reviewer_note` records the reason; and
`reviewer_evidence` accepts a citation, URL, or other evidence reference. A blank
identity falls back to `review apply --reviewer`, then to `anonymous`. Notes and
evidence apply only to fields with a decision or an actual legacy correction.
Accepting a lemma does not verify POS, morphology, dependencies, or lexical sense.

The saved corpus keeps per-field decisions and verification, the first prediction
under `<field>__pred`, and a structured `review_history` with every action,
prediction, value, reviewer, note, evidence, source class, and date. Reannotation
invalidates the current decisions for fields it replaces while retaining history;
export a new table to reconsider them. Applying explicit decisions from a table
whose prediction or source alignment changed raises an error.

New CSV snapshots bind source/form alignment, predictions, and the available
analysis identity, including model/configuration evidence when present.
Renumbering tokens or changing document context requires a fresh export.
Reannotation gives the replaced analysis a new generation and invalidates old
snapshots even when the displayed values agree. Source/custom annotations without
model identity remain explicitly unknown. Preserve the snapshot columns; they
record identity, not an accuracy guarantee. Older CSVs without these bindings
retain their existing source/value checks and cannot prove model identity.

For dependency review, select `--field head --field deprel`. With `--annotate --neural`,
these fields explicitly request syntax annotation, including generated morphology
and parsed punctuation. The Python equivalent is
`greek.annotate_corpus(corpus, with_dependencies=True)` with the neural backend active;
ordinary annotation keeps its lemma/POS behavior. Each selected sentence
includes its complete indexed context, including parsed punctuation. Heads use
the sentence's **1-based token index**, with **0 for the root**, rather than corpus
positions or source-token IDs. Explicit sentence ownership must be available;
the reviewer does not guess it from line breaks. Applying dependency edits checks
complete membership, valid heads, a single root, root labels, and absence of
cycles before saving the result. A malformed tree produces no partial changes.

Several scholars can review copies of the same export, then run
`aegean review merge alice.csv bob.csv --corpus corpus.json -o merged.csv`.
Conflicting actions or corrections remain unresolved; `--on-conflict report`
writes only the agreed subset. A merged CSV's read-only `reviewer_records` column
preserves each person's field attribution, note, and evidence, including when
different people checked different fields. Keep source, alignment, prediction,
and merge-attribution columns intact.

## Reproducing the public evidence

pyaegean includes a one-command review path for people who want to check the
public evidence before reading the rest of the repository:

```bash
git clone https://github.com/ryanpavlicek/pyaegean.git
cd pyaegean
python scripts/reproduce_review.py
```

The command runs on CPython 3.10 through 3.14. It uses the standard library and
the checked-out zero-dependency source. It verifies a canonical SHA-256 manifest
whose records each choose byte-exact or cross-platform canonical-LF hashing, runs
the project-authored offline regression fixture and one baseline Greek sentence,
and compares the result byte-for-byte with the reviewed expectation. When Git is
available, it also reports the commit and whether the checkout is clean.

It does not download or run the neural model, use the network, write bytecode, or
create a pyaegean cache. The fixture result is not a neural accuracy claim:
reproducing the published neural rows needs the complete pinned protocol on the
[Benchmarks](benchmarks.md) page.

```mermaid
flowchart TD
    A["Clean source checkout"] --> B["Verify manifest and record hashes"]
    A --> C["Run zero-dependency fixture"]
    B --> D["Receipt with exact digests"]
    C --> D
    D --> E["Inspect the model, data, claims, and limitations"]
    E --> F["Report a match or discrepancy"]
```

## Reading the receipt

A pass establishes two things:

1. Every public record in the review manifest has the reviewed bytes.
2. The deterministic offline journey gives the reviewed result on this interpreter.

A pass does not certify the scholarly interpretation of a source, rerun a large
model, or amount to outside peer review. `--json` prints the complete
machine-readable receipt. `--allow-dirty` is available for local diagnosis, but a
dirty run is not clean reproduction evidence.

## What to inspect next

The repository's [independent review kit](https://github.com/ryanpavlicek/pyaegean/tree/main/review)
contains the canonical manifest, a model card, a data card, an evidence map, a
limitations matrix, and the discrepancy-report path. The measured-value registry is
[`training/results/published-claims.json`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/results/published-claims.json),
and this site's [Methodology](methodology.md) page explains the data, architecture,
evaluation, and review rules in full.

The model card identifies the shipped artifact and its intended use. The data card
describes training and evaluation roles, separation, licenses, and coverage limits.
The wiki's [Validation and review](https://github.com/ryanpavlicek/pyaegean/wiki/Validation-and-Review)
page states what has and has not had outside review, and
[Limitations](https://github.com/ryanpavlicek/pyaegean/wiki/Limitations) keeps the
full boundary register.

## Reporting a mismatch

Open an [independent-review discrepancy](https://github.com/ryanpavlicek/pyaegean/issues/new?template=reproduction_discrepancy.yml)
with the exact command, package version, Git commit or source-archive hash, manifest
SHA-256, deterministic-result SHA-256, environment, observed output, and all local
modifications. Record a discrepancy exactly; it is useful evidence.

Prospective maintainers can start with the ownership slices in
[`CONTRIBUTING.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md).
