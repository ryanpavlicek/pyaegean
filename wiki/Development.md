# Development

## Setup

```bash
git clone https://github.com/ryanpavlicek/pyaegean
cd pyaegean
pip install -e ".[dev]"
```

## The check suite (the merge gate)

Every change must pass the full gate before it lands on `main`:

```bash
pytest                                   # full test suite
python -c "import aegean; print(len(aegean.load('lineara')))"   # 1721
ruff check src tests                     # lint (clean)
mypy                                     # type-check (clean; enforced in CI)
python -m build && python -m twine check dist/*
python scripts/check_footprint.py --wheel "dist/*.whl"   # wheel = code + JSON only
python scripts/check_footprint.py                        # import-clean + import-fast
```

CI (GitHub Actions) runs `ruff`, `mypy` (enforcing), the `pytest` matrix across
Python 3.10–3.13, a build job with `twine check`, and a footprint job
(`scripts/check_footprint.py`) that asserts `import aegean` loads no heavy deps,
imports fast, and that the wheel ships only code + JSON.

## Conventions

- **Lazy heavy imports.** `numpy`/`pandas`, `onnxruntime`, and provider SDKs are
  imported inside the functions that need them. Keep `import aegean` instant.
- **No bundled binaries.** Large assets go through the
  [download-to-cache](Data-and-Provenance) layer.
- **Exploratory labeling.** Any cross-linguistic, accounting, decipherment, or
  AI method documents its caveat and is labeled unverified at point of use.
- **Faithful ports.** Behavior ported from the Linear A Workbench asserts against
  shared golden fixtures (`tests/fixtures/golden/`) so the Python port can't
  silently diverge.

## Adding a script plugin

1. Subclass `core.Script` (`id`, `name`, `sign_inventory`, `tokenize`) and
   `register()` it.
2. Register a corpus loader with `core.corpus.register_loader(id, fn)`.
3. Import your plugin from `aegean/scripts/__init__.py` so it registers on
   `import aegean`.

See `aegean/scripts/lineara` and `aegean/scripts/greek` for worked examples, and
the [Architecture](Architecture) page for the layering rules.

## Layout

```
src/aegean/
  core/      model corpus script provenance numerals
  scripts/   lineara/{loader,inventory,phonetic}  greek/{loader,inventory}
             linearb/{loader,inventory,phonetic,lexicon,epidoc}
             cypriot/{loader,inventory,phonetic,lexicon}
             cyprominoan/{loader,inventory}  (undeciphered — signs only)
  analysis/  distance align collocation morphology patterns query accounting structure
  greek/     normalize tokenize syllabify accent prosody meter phonology pos morphology lemmatize
             treebank (AGDT lexicon) lexicon (LSJ) syntax (dependency parser)
             neural_lemmatizer (GreTa seq2seq) joint (neural pipeline) mst udfeats
             proiel (out-of-AGDT eval) ud (UD eval) benchmark (harness)
  io/        epidoc (TEI export) tabular (CSV/Parquet export)
  ai/        client cache providers grounding capabilities
  translate/ (hybrid lexicon+LLM)
  data/      bundled/{lineara,linearb,cypriot,cyprominoan,greek}/*.json  + fetch()/cache
tests/       fixtures/golden/   (+ parity, property, and corpus tests)
wiki/        this documentation (published to the GitHub wiki by CI)
docs/        PLAN.md (approved design), methodology.md
```

## Editing this wiki

These pages live in `wiki/` in the main repo and are published to the GitHub
wiki automatically by `.github/workflows/wiki.yml` on push to `main`. Edit the
Markdown here and open a normal change — do **not** edit the wiki UI directly, or
the next sync will overwrite it.
