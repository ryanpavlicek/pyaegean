# Validation and review

This page records how pyaegean verifies its code, benchmarks, and data, how to
review annotations interactively, how to package reproducible research bundles,
and which parts of the project have received outside peer review.

Related documentation covers the evaluation protocol
([Methodology](Methodology)), measured scores ([Benchmarks](Benchmarks)), and
dataset licensing ([Data & Provenance](Data-and-Provenance)).

---

## Summary

| Question | Status | Reference |
| --- | --- | --- |
| Are accuracy figures reproducible? | Yes, via a fixed protocol on held-out folds with reproduction commands. | [Benchmarks](Benchmarks), [Methodology](Methodology) |
| Is the test set excluded from training? | Yes, via an exclusion manifest and a license split. | [Methodology](Methodology#3-leakage-control) |
| Do public functions have output-checking tests? | Yes, required for all public APIs. | [CONTRIBUTING](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#tests) |
| Are published numbers guarded against drift? | Yes, pinned to a JSON registry checked on every commit. | [Claims registry](#claims-registry) |
| Has the software undergone external scholarly peer review? | No. | [External review status](#external-review-status) |
| Has it undergone a formal external software audit? | No. | [External review status](#external-review-status) |
| How are errors or challenges submitted? | Through the Correction, Validation, Data-contribution, or Reproduction-discrepancy issue forms. | [Reporting errors and submitting findings](#reporting-errors-and-submitting-findings) |

---

## Internal verification

The checks below run inside the project repository and in continuous
integration across all supported Python versions prior to release, alongside
linting and type-checking.

### Output-checking tests

Every public function must have a test asserting its output against gold data,
a hand-computed value, or a formal invariant (round-trip preservation, range
bound, or symmetry). A test that only checks that a call runs without raising an
exception is insufficient. Two earlier defects (a dead elision entry and an
incorrect dative-plural accent) passed execution-only checks before output
assertions caught them.

### Benchmark protocol and leakage controls

UD-Perseus and UD-PROIEL test folds are scored with the official CoNLL 2018
evaluator (SHA-256-pinned) over gold tokenization, accompanied by 95% bootstrap
confidence intervals. The Nestle 1904 Greek New Testament provides an additional
out-of-domain check scored as plain accuracy for lemmas and reconciled UPOS
(the NT gold lacks dependency trees). Out-of-domain figures are always reported
alongside in-family scores.

Two controls prevent test leakage: `greek.agdt_ud_overlap()` maps every
UD-Perseus dev and test sentence back to its AGDT source and removes it from
training, and models train only on CC BY-SA treebanks while CC BY-NC-SA
treebanks remain strictly evaluation-only. Full details appear on
[Methodology](Methodology) and [Benchmarks](Benchmarks).

### Claims registry

Every published benchmark number is recorded in
`training/results/published-claims.json`. `tests/test_benchmark_claims.py`
asserts that documentation echoes match that registry on every commit, and
`scripts/check_benchmarks.py` re-measures the offline-stack rows against it.
Any updated measurement lands with its evidence file, registry update, and
documentation update in the same commit.

### Adversarial internal audits

Before major milestones, the repository undergoes internal adversarial reviews
targeting correctness, regressions in recent diffs, propagation of bug fixes
across sibling code paths, handling of malformed or hostile inputs, agreement
between documented examples and live execution, and philological accuracy
against standard authorities (Smyth, LSJ, and published editions). Every
candidate finding is reproduced independently before changing code, and
confirmed fixes ship with regression tests.

---

## External review status

Internal automated tests and audits catch code regressions, stale numbers, and
data defects, but they do not constitute external scholarly peer review or an
independent software audit.

**Upstream scholarship.** Established-tier data (sign values, Greek lexica and
morphology, bundled transliterations, treebank annotations, and evaluation
golds) derives from published, externally reviewed scholarly editions and
datasets (GORILA, Perseus AGDT, LSJ, Nestle 1904, DAMOS, epigraphic corpora,
and the CoNLL 2018 evaluator). Every record cites its source, and errors in
transcription or mapping are corrected against that authority.

**pyaegean software and derived results.** The codebase, its integration of
upstream sources, its measured benchmark numbers, and its exploratory outputs
have not received external scholarly peer review or an external software audit.
Measured numbers are reproducible from the recorded protocol, not externally
certified. Undeciphered-script analyses (Linear A and Cypro-Minoan) and all
AI-layer outputs carry explicit exploratory labels at the point of use. See
[For Specialists](For-Specialists) and [Limitations](Limitations).

---

## Interactive annotation and disagreement review in the TUI

Automated annotations can be audited and adjudicated directly in the terminal
using `aegean tui` (requires `pip install 'pyaegean[tui]'`) without leaving the
review workflow or editing raw CSV columns by hand.

Launch directly into the review workspace with one review table or multiple
reviewers' copies of the same export:

```bash
# Review a single exported CSV (full schema or --layout editable with .companion.json)
aegean tui --review review.csv

# Adjudicate disagreements between two reviewers against the source corpus
aegean tui --review alice.csv --review bob.csv --corpus nt
```

From anywhere inside `aegean tui`, press **`r`** to open the Annotation Review
screen. You can type a single CSV path, comma-separated CSV paths to merge and
adjudicate, or a corpus ID (such as `nt`) to generate a live review queue sorted
by calibrated risk when calibrated confidence annotations are present.

When two or more CSVs are loaded, pyaegean merges them with
`merge_review_tables(..., on_conflict="report")` and presents each genuine
disagreement as numbered one-key choices (`1`, `2`, `3`). Screen bindings:

- `a`: accept current prediction
- `e`: edit lemma, POS, morphology, dependency fields, or reviewer note
- `1` / `2` / `3`: pick a conflict resolution option
- `d`: defer token
- `x`: reject token
- `n` / `p`: jump to next or previous unresolved token
- `f`: cycle status filters
- `s`: save changes

Saving preserves the immutable snapshot hashes and companion metadata so the
saved CSV passes straight into `aegean review apply`. See [TUI](TUI) and
[When the Tool Is Wrong](When-the-Tool-Is-Wrong).

---

## Reproducible research bundles

To share a study with collaborators, reviewers, or an archive, package all
inputs, human review artifacts, receipts, and citations into a single
deterministic, SHA-256-verified `.zip` archive (`aegean-research-bundle/1`)
using `aegean bundle` or the Python `aegean.bundle` module:

```bash
# Create a license-clean bundle with corpus, review CSVs, and evaluation receipts
aegean bundle create study-bundle.zip \
  --corpus isicily \
  --title "Sicilian funerary lemmas" \
  --review review.csv \
  --receipt eval-receipt.json

# Inspect manifest metadata and member hashes without extracting
aegean bundle inspect study-bundle.zip

# Verify archive path safety and SHA-256 checksums for every member
aegean bundle verify study-bundle.zip

# Unpack and reconstruct corpus + workspace (pass --fetch for pointer corpora)
aegean bundle hydrate study-bundle.zip ./reproduced-study --fetch
```

By default (`--embed-corpus auto`), redistributable corpora are embedded as
`corpus.json.gz`, while NonCommercial or restricted corpora (such as `damos`,
`sigla`, `iip`, `igcyr`, `crete`, or `homer-scholia`) are recorded as
license-clean retrieval pointers (`CorpusReference`) so the bundle remains
redistributable; `aegean bundle hydrate --fetch` reconstructs the exact corpus
from its pinned upstream asset. Passing `--embed-corpus always` embeds an NC
corpus for private archival and marks `manifest.redistributable = false` with an
explicit warning.

Every bundle automatically includes:

- `manifest.json` with `pyaegean` version, policy flags, and per-member SHA-256
  digests
- any supplied review CSVs alongside their `.companion.json` snapshots
- any supplied analysis or evaluation receipts and optional workbench state
  backups (`--state`)
- generated citations in `CITATIONS.bib`, `CITATIONS.txt`, and `citations.json`

The same operations are available in Python via `aegean.bundle`
(`create_bundle`, `inspect_bundle`, `verify_bundle`, `extract_bundle`, and
`hydrate_bundle`).

---

## One-command evidence check

An independent reviewer can verify the repository's public evidence records from
a clean source checkout with:

```bash
python scripts/reproduce_review.py
```

The script checks every file in `review/review-manifest-v1.json` by SHA-256 and
reproduces one small, project-authored offline result without network access,
neural model execution, bytecode writes, or cache creation. A pass confirms
file integrity and offline regression parity; it does not rerun the neural
benchmarks or establish external certification. See
[Independent Review](Independent-Review) for the model card, data card, and
discrepancy reporting workflow.

---

## Reporting errors and submitting findings

External corrections and refutations are recorded with their source citations.
Four GitHub issue forms cover the standard cases (New issue → select a
template):

| Form | Use when | Include |
| --- | --- | --- |
| **Correction** | An established fact is wrong (sign value, gloss, lemma, bridge reading, or benchmark item) | Exact value and published source |
| **Validation** | Confirming or refuting an exploratory result | Output, verdict, reasoning, and `trace()` |
| **Data contribution** | Adding a single sourced, openly licensed fact | Fact and citation |
| **Reproduction discrepancy** | Review script, benchmark protocol, or digest fails to match | Versions, hashes, environment, expected and observed output, and local edits |

Check [Limitations](Limitations) for known boundaries before filing, and see
[For Specialists](For-Specialists) (§6) for target file paths and tests. Open a
form from the
[issue chooser](https://github.com/ryanpavlicek/pyaegean/issues/new/choose), or
review the
[contribution menu](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#good-first-contributions-a-menu)
for pull requests.

---

## See also

- [For Specialists](For-Specialists): evidence tiers and contribution paths
- [Benchmarks](Benchmarks) and [Methodology](Methodology): measured scores,
  evaluation protocol, and leakage controls
- [Independent Review](Independent-Review): bounded verification command, model
  and data cards, and discrepancy form
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): error analysis and
  review CSV workflows
- [TUI](TUI): terminal browser, workbench, and interactive annotation review
- [Citing Computational Assistance](Citing-Computational-Assistance): citing
  editions, versions, receipts, and bundles
- [Data & Provenance](Data-and-Provenance) and [Limitations](Limitations):
  upstream datasets, licenses, and documented limits
