# Contributing to pyaegean

Thanks for your interest! pyaegean is a specialist Python toolkit for Ancient
Greek (alphabetic + Aegean syllabic), focused on deep, high-quality Greek coverage.
See `docs/ROADMAP.md` for the living plan (what's shipped and what remains);
`docs/PLAN.md` is the original design, kept as a historical record.

## Setup

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy
```

## Good first contributions (a menu)

Small, well-scoped facts that make the toolkit better without touching the
architecture — each has an obvious home and an obvious test:

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
  (`src/aegean/data/bundled/geo/site_coordinates.json`) — cite the Pleiades URI.
- **A collocation / statistics measure.** A new association measure in
  `src/aegean/analysis/collocation.py` with a literature reference and a
  golden-value test.
- **A closed-class form.** A missing article/particle/pronoun form in the
  POS lexicon (`src/aegean/greek/pos.py`).
- **A benchmark sentence.** Gold lemma/POS items for the Greek benchmark
  harness (`aegean.greek.benchmark`), with the edition you read them from.

For anything larger, open an issue first so the design can be agreed before
you write code.

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
  comparisons with other tools live there, not in the README/wiki.

## Deprecation policy

pyaegean is pre-1.0, but the public API is treated as a contract:

1. **Deprecate in a minor release, remove no sooner than the next minor.**
   A symbol deprecated in 0.x.0 keeps working through every 0.x.* and may be
   removed in 0.(x+1).0 at the earliest.
2. **Warnings carry the replacement.** Every deprecation emits a
   `DeprecationWarning` that names the replacement API and the release that
   introduced the deprecation — never a bare "this is deprecated".
3. **The CHANGELOG records both ends**: the release that deprecates and the
   release that removes.
4. **Data and models version forward.** Fetched artifacts are sha256-pinned
   release assets; a new model is a new asset name (`grc-joint-v2`), never a
   mutation of an existing one, so cached environments keep working.

## Tests

Every behavior gets a test. Ports get parity tests; invariants get property
tests (`hypothesis`). Keep `pytest` green and the wheel small.
