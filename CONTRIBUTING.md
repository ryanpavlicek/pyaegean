# Contributing to pyaegean

Thanks for your interest! pyaegean is a specialist Python toolkit for Ancient
Greek (alphabetic + Aegean syllabic), focused on deep, high-quality Greek coverage.
See `docs/PLAN.md` for the architecture.

## Setup

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy
```

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

## Tests

Every behavior gets a test. Ports get parity tests; invariants get property
tests (`hypothesis`). Keep `pytest` green and the wheel small.
