# Contributing to pyaegean

Thanks for your interest! pyaegean is a specialist Python toolkit for Ancient
Greek (alphabetic + Aegean syllabic), focused on deep, high-quality Greek coverage.
The [README](README.md#roadmap) has the roadmap: what's shipped and what's next.

## Setup

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy
```

## Efficient local validation

The checkpoint runner orders local checks from fastest to most expensive and stops
at the first failure. Choose the profile that matches the highest-risk part of the
change and name every directly affected test file:

```bash
python scripts/check_checkpoint.py --profile code --test tests/test_example.py --dry-run
python scripts/check_checkpoint.py --profile code --test tests/test_example.py
python scripts/check_checkpoint.py --profile code --test tests/test_example.py --full
```

Use `docs` for documentation-only changes, `code` for internal implementation,
`public-api` when exported behavior or signatures change, and `persistence` for a
stored schema or interchange format. The profiles add relevant static, API,
documentation, footprint, and compatibility guards; they do not replace the
focused correctness, adversarial, or journey tests required below.
Install `.[dev,docs]` before using the `docs` profile.

Reserve `--full` for the reviewed, final code tree. A successful run writes an
ignored receipt under `build/`; `python scripts/check_checkpoint.py
--verify-receipt` confirms whether it still describes the current HEAD, index,
worktree, and untracked nonignored files. Any public-tree change invalidates the
receipt. GitHub Actions remains the authoritative supported-Python matrix after a
push.

For a documentation-only change, run the `docs` profile plus any directly
affected executable-example or demo test, and omit `--full`. If the same change
touches source code, a script, dependencies, a data or persistence format, or an
input to a measured claim, use the corresponding broader profile and run one
full suite on the final reviewed tree.

## Good first contributions (a menu)

Small, well-scoped facts that make the toolkit better without touching the
architecture: each has an obvious home and an obvious test:

- **A syllabification exception.** Compounds divide at the point of union
  (Smyth §140), which pure phonotactics can't see. Add the form to
  `_EXCEPTIONS` in `src/aegean/greek/syllabify.py` with its correct division;
  the test suite automatically checks that your entry joins back to the form
  *and* differs from the rule engine (entries the rules already get right are
  rejected as dead weight).
- **A sign-inventory fact.** A sound value, variant glyph, or attribute
  correction for a Linear A/B, Cypriot, or Cypro-Minoan sign
  (`src/aegean/data/bundled/<script>/signs.json`), with a source.
- **A gazetteer alignment.** A find-site missing its Pleiades ID
  (`src/aegean/data/bundled/geo/site_coordinates.json`): cite the Pleiades URI.
- **A collocation / statistics measure.** A new association measure in
  `src/aegean/analysis/collocation.py` with a literature reference and a
  golden-value test.
- **A closed-class form.** A missing article/particle/pronoun form in the
  POS lexicon (`src/aegean/greek/pos.py`).
- **A benchmark sentence.** Gold lemma/POS items for the Greek benchmark
  harness (`aegean.greek.benchmark`), with the edition you read them from.

For anything larger, open an issue first so the design can be agreed before
you write code.

## Contributing sourced data

Additions to the bundled lexica, sign tables, gazetteer, and benchmark gold are
welcome when each is a single fact backed by a citation. This is the path for the
Greek coverage additions in particular: a missing lemma (a form the lemmatizer
does not resolve), a wrong lemma (a form it resolves incorrectly), missing
morphology (part of speech or features for a form), and poetic, dialectal, Koine,
or epigraphic forms that the ordinary Attic-prose rules do not reach. The
[Data contribution](.github/ISSUE_TEMPLATE/data_contribution.yml) issue form
collects the same fields.

State, for each entry:

- **The source**: the edition, dictionary, or citation the fact comes from (an
  LSJ or Middle Liddell entry, a treebank, or a named edition with a passage or
  document reference). Nothing enters a bundled table without one; this applies
  the "Provenance & attribution" and "Measured claims only" principles below to
  data.
- **The form**, exactly as written, with its accents and any editorial marks.
- **The lemma**, the dictionary headword the form belongs under.
- **The morphology**, if known: part of speech and features (for example "noun,
  genitive singular").
- **A scope note**: the register, dialect, or genre the form belongs to (for
  example Homeric, Doric, Koine, or an inscription), and how widely it is
  attested. Keep the entry to what the source supports; do not generalize one
  attestation into a full paradigm.
- **A test**, per the Tests section below: a correctness test that checks the
  recorded reading is the one the code returns, so a later change cannot silently
  drop it.

To find candidates, `greek.missing_forms(corpus)` (CLI:
`aegean greek missing-forms CORPUS`) reports the word forms in a corpus that the
lemmatizer does not resolve, grouped by form with where each one occurs. The results reflect whichever lemmatizer is active when you run it (the
offline baseline by default; a loaded treebank or neural backend resolves more),
so run it against the coverage you ship. It points to forms worth reviewing, not
to corrections: confirm each against a source before adding it.

To fix an existing reading, use the Correction issue form. To confirm or refute
an exploratory (decipherment, cross-linguistic, or AI) result, use the Validation
form; those outputs are labeled hypotheses, not facts.

## Regenerating bundled data

Some bundled JSON is generated, not hand-edited, by the scripts in `scripts/`:
regenerate it there rather than editing the JSON by hand. The Greek-works
discovery catalogue (`src/aegean/data/bundled/greek/works_catalogue.json`, behind
`greek.catalog()` / `aegean greek catalog`) is built by
`scripts/build_greek_catalogue.py`, which crawls Perseus canonical-greekLit and
First1KGreek at the commits pinned in `aegean.scripts.greek.perseus._SOURCES`:
so bumping a pin and rerunning the script keeps the catalogue in lockstep with
what `load_work` actually fetches. It records metadata only (id/author/title/Greek
title/source); the texts stay CC BY-SA and fetched on demand, never bundled. The
sibling builders (`build_dodson_lexicon.py`, `build_nt_corpus.py`,
`build_damos_corpus.py`, `build_sigla_corpus.py`, the Linear B builders) document
their own sources and methods in their module docstrings.

## Principles

- **Script-agnostic core.** New writing systems are plugins: subclass
  `aegean.core.Script`, `register()` it, and register a corpus loader. The core
  never imports a specific script.
- **Zero hard third-party deps in the core.** `import aegean` is instant and loads
  nothing heavy; `pandas` is the optional `[data]` extra (lazy-imported only inside
  `to_dataframe`); collocation stats are pure stdlib. `scripts/check_footprint.py`
  enforces this in CI: import-clean, import-fast, and a code+JSON-only wheel.
- **No large/binary assets in the repo or wheel.** Use the `aegean.data.fetch()`
  download-to-cache layer for corpora and trained models.
- **Faithful, parity-tested ports.** When porting analysis from the workbench,
  assert against shared golden values in `tests/fixtures/golden/`.
- **Label exploratory output.** The Linear A material is undeciphered; any
  decipherment, cross-linguistic, metrological, or AI-generated result must be
  marked exploratory/unverified with provenance, in docstrings and at use.
- **Provenance & attribution** are first-class. Cite underlying editions; keep
  `NOTICE` accurate as data sources are added.
- **Measured claims only.** Accuracy numbers in docs must come from a
  reproducible evaluation (see `docs/benchmarks.md` for the protocol);
  comparisons with other tools live in `docs/benchmarks.md` and, with citations,
  on the wiki's Benchmarks page (both pinned to the claims registry), never in
  the README.

## Deprecation policy

pyaegean is pre-1.0, but the public API is treated as a contract:

The supported entry points are the facade modules listed in the
[API reference](https://pyaegean.xyz/api/). Existing lower-level paths that were
already released remain compatibility-protected, but new implementation modules
are not added to the contract automatically. `scripts/api-manifest.json` is the
reviewed facade list, while `scripts/api-baseline.json` retains both supported and
grandfathered names. Run `python scripts/check_api.py` before proposing an API
change; release snapshots refuse legacy breaks and add only reviewed facade names.
Add a new supported facade by reviewing `api-manifest.json` before the release
snapshot. After the required deprecation cycle is complete, a deliberate removal
still requires reviewing the reported break and passing
`--snapshot --accept-breaking-snapshot`; ordinary snapshots never erase or rewrite
grandfathered contracts.

1. **Deprecate in a minor release, remove no sooner than the next minor.**
   A symbol deprecated in 0.x.0 keeps working through every 0.x.* and may be
   removed in 0.(x+1).0 at the earliest.
2. **Warnings carry the replacement.** Every deprecation emits a
   `DeprecationWarning` that names the replacement API and the release that
   introduced the deprecation: never a bare "this is deprecated".
3. **The CHANGELOG records both ends**: the release that deprecates and the
   release that removes.
4. **Data and models version forward.** Fetched artifacts are sha256-pinned
   release assets; a new model is a new asset name (`grc-joint-v2`), never a
   mutation of an existing one, so cached environments keep working.

## Tests

Every public function gets a **correctness** test, old and new: a test that checks
the actual output is *right*, not merely that the call runs without error. Use gold
or hand-computed expected values, a known-answer case, or a property invariant
(round-trip identity, range bound, symmetry, monotonicity). Ports get parity tests
against `tests/fixtures/golden/`; statistical functions get cross-checks against a
hand-computed or reference (`scipy`) value; invariants get property tests
(`hypothesis`). A new public function is not done until it has one. Keep `pytest`
green and the wheel small.

Two more dimensions ship WITH the correctness tests, in the same change:

- **Adversarial input, when the feature accepts external input** (a user file, pasted
  text, a CSV from a spreadsheet, network data, an environment variable): malformed,
  truncated, hostile, and mismatched inputs must produce a clean, named error or a
  documented degradation, never a raw traceback, a silent wrong result, or a hang.
  Probe at least: the malformed file, the wrong-but-plausible input (a CSV from a
  different corpus, a stale artifact), and the pathological size/shape (an unclosed
  quote, a combining-mark flood, a huge field). The review-table importer shipped
  correctness-tested but not adversarially tested, and three of its input defects
  survived two releases.
- **The full journey, when the feature is a step in one** (import → analyze → export,
  fetch → load → save): at least one test walks the whole path and re-reads the final
  artifact, asserting the content — segments that each pass can still lose data at the
  seams (an export that silently drops a column its consumers rely on). The
  `tests/test_journey_*.py` files are the pattern.

## Surface parity

Every user-facing capability is carried by the two primary surfaces (the Python API
and the `aegean` CLI), and then deliberately either surfaced or not on each of the
four secondary surfaces: the browser demo (`docs/demo/`), the MCP server
(`aegean.mcp_server`), the walkthrough notebooks (`notebooks/`), and the terminal UI
(`aegean tui`). `scripts/surface-manifest.json` is the ledger of those decisions: one
entry per capability with, for all four secondary surfaces, either `covered` (naming
where) or `excluded` (naming a reason from the manifest's controlled vocabulary).

A new capability updates the manifest in the same change: add its entry and choose a
covered-or-excluded verdict per surface. Excluding a surface is a first-class choice,
not an omission — record the reason (needs a fetch, needs the neural model, needs an
API key, a heavy dependency, a filesystem path the surface cannot offer, or simply
not applicable there). `tests/test_surface_parity.py` diffs the demo's registered
functions and `aegean.mcp_server.TOOLS` against the manifest in both directions, so a
new demo card or MCP tool without a manifest entry fails, and it fails any capability
that leaves a surface undecided or uses a reason outside the vocabulary.

Two of those checks are stricter than a bare presence test, because a bare filename
survives the very drift it is meant to catch:

- A `notebooks`-covered `where` is an object `{notebook, marker}`, not a filename. The
  `marker` is a distinctive substring (usually the call the cell demonstrates), and the
  guard opens the named notebook and asserts the marker really appears in one of its
  code cells. Deleting or renaming the covering cell then fails the guard in the same
  commit; a bare filename would have stayed green.
- The `site_nav` block is a tracked part of the manifest, reconciled against
  `mkdocs.yml`'s top-level navigation in both directions: every tracked entry is either
  `covered` (pointing at a tracked surface or a capability id) or `excluded` (with a
  reason), scaffolding pages are listed as `structural`, and no live nav entry may be
  left undecided. Adding or removing a top-level Pages-site nav entry without recording
  it here fails.

## The propagation step

When a fix or a feature creates a recurring pattern — a guard, a normalization, an
atomic write, a freshness stamp, a structured-error wrapper, a shared view layer — the
same change extracts the shared helper and lands a parity test that enumerates every
sibling call site and asserts the invariant across all of them.
`tests/test_propagation_parity.py` is the home for these. A future sibling added
without the fix then fails a test in the same commit, rather than becoming the next
un-propagated straggler a later audit has to hunt down. This is the same discipline
`scripts/surface-manifest.json` and the Surface parity section above apply to the four
secondary surfaces: turn "remember to update the other places too" into a test.
