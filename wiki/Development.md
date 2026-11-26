# Development

This page covers contributing to pyaegean: building from source, running CI
checks locally, and adding corpora, sign values, or lexicon entries. To use the
toolkit rather than modify it, start with [Getting Started](Getting-Started).

Many useful contributions are small, well-scoped data updates (a sign value, a
syllabic Greek equation, or a syllabification exception), each with a JSON file
and an automated test. Read [Architecture](Architecture) alongside this page for
module layering rules.

---

## Build from source

Requires Python 3.10 or newer and `git`. Clone the repository and install in
editable mode (`-e`) with the `[dev]` extra:

```bash
git clone https://github.com/ryanpavlicek/pyaegean
cd pyaegean
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -e ".[dev]"
```

For full-stack work including the neural Greek pipeline, install
`pip install -e ".[dev,all]"` (`[all]` includes `[neural]`; `[parquet]` stays a
separate opt-in because of its compiled dependency). For framework adapters, add
`pip install -e ".[dev,all,interop]"` (CLTK installs on Python 3.13+ only).

The default `pytest` run excludes `framework_interop`, `released_wheel`, and
`neural_integration` markers while running core schemas, bundles, CLI behavior,
lazy imports, and missing-extra errors. Run real spaCy, Stanza, and CLTK adapter
tests with `pytest -m framework_interop`.

Verify the install:

```bash
python -c "import aegean; print(aegean.__version__, aegean.registered_scripts())"
# 0.72.0 ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

### What `[dev]` installs

`pip install -e ".[dev]"` installs test runners, linters, build tools, static
API validation, and the optional runtime extras exercised by the core test
matrix. Real framework-adapter tests additionally need `[interop]`:

| Tool | Role |
| --- | --- |
| `pytest`, `pytest-cov`, `pytest-xdist` | test suite, coverage, parallel execution |
| `hypothesis` | property-based tests for invariants |
| `mypy` | strict static type checking (enforced in CI) |
| `ruff` | linter and formatter checks |
| `griffelib`, `PyYAML` | static validation of the public API facade (`scripts/check_api.py`) |
| `build`, `twine` | wheel/sdist builds and PyPI metadata validation |
| `nbmake`, `ipykernel` | execute example notebooks under pytest |
| `pandas` | DataFrame interop tests (`[data]`) |
| `typer`, `rich`, `prompt_toolkit` | `aegean` CLI and REPL (`[cli]`) |
| `lxml` | Linear B DAMOS EpiDoc import and schema validation (`[epidoc]`); generic token-carrier EpiDoc uses stdlib XML |
| `spaCy`, `Stanza`, `CLTK` | real-object interop tests when `[interop]` is installed (CLTK requires Python 3.13+) |
| `matplotlib` | static plotting (`[viz]`) |
| `mcp` | `aegean-mcp` Model Context Protocol server (`[mcp]`) |
| `textual` | `aegean tui` terminal UI (`[tui]`) |

`[dev]` excludes `[neural]` (`onnxruntime`, `tokenizers`, `numpy`) and AI
provider SDKs; tests requiring models or provider keys skip when absent. Install
`pip install -e ".[neural]"` when working on the neural pipeline. See
[Installation](Installation) for the complete extras matrix.

---

## The check suite (the merge gate)

Every change must pass these checks before landing on `main`. Local runs catch
most defects, though a few checks (such as tests wrapping CLI `--help` output)
depend on CI terminal width, so check the CI run after pushing too.

```bash
ruff check src tests                       # 1. lint
mypy                                       # 2. strict type-check
python scripts/check_api.py                # 3. public API facade check
pytest                                     # 4. test suite
python scripts/check_footprint.py          # 5. import-clean + import-fast
```

Packaging checks when modifying packaging or bundled data:

```bash
python -m build && python -m twine check dist/*
python scripts/check_footprint.py --wheel "dist/*.whl" --sdist "dist/*.tar.gz"
```

Pinned remote assets (release archives and commit-pinned upstream sources) are
checked weekly by `.github/workflows/assets.yml` rather than per PR. Run them
locally anytime:

```bash
python scripts/check_assets.py                 # verify every pinned URL resolves
python scripts/check_assets.py --verify-hashes # verify release asset SHA-256 digests (slow)
python scripts/check_gazetteer.py              # verify Pleiades-linked find-site coordinates
```

Quick corpus smoke check:

```bash
python -c "import aegean; print(len(aegean.load('lineara')))"   # 1721
```

### Expected output for each check

**1. Lint (ruff).** Line length 100 across `src` and `tests`:

```bash
ruff check src tests
# All checks passed!
```

**2. Type-check (mypy).** Strict mode (`[tool.mypy] strict = true` in
`pyproject.toml`) across `src/aegean` and tracked training helper scripts;
untyped optional libraries sit under `ignore_missing_imports`:

```bash
mypy
# Success: no issues found in 237 source files
```

**3. Tests (pytest).** Run the full suite or a focused file:

```bash
pytest                       # full suite (-q set in pyproject.toml)
pytest tests/test_numerals.py -q
# ......                                                                   [100%]
```

Run in parallel with `pytest -n 4 --dist loadgroup`. `tests/conftest.py` pins
TUI Pilot tests to a single worker group (use `--dist loadgroup`, not
`loadfile`). CI runs `pytest --cov=aegean --cov-report=term-missing` across the
supported Python matrix.

**4. Footprint guard.** Verifies that `import aegean` stays fast and pulls zero
heavy dependencies. Run against a core-only install (no extras) for a clean
baseline; with `[dev]` installed, heavy libraries exist in the environment and
still must remain absent from `sys.modules` after `import aegean`:

```bash
python scripts/check_footprint.py
# loaded on import: none
# OK  import-clean
# cold import best 350 ms (bound 750); samples [353, 359, 364, 350, 356]
# OK  import-fast
```

Wheel check confirming code and JSON only (no binaries):

```bash
python scripts/check_footprint.py --wheel "dist/*.whl"
# wheel dist/pyaegean-0.72.0-py3-none-any.whl: ... KB uncompressed, ... files
# OK  nothing-heavy-bundled
```

Metadata check for PyPI:

```bash
python -m twine check dist/*
# Checking dist/pyaegean-0.72.0-py3-none-any.whl: PASSED
```

### The footprint guard in detail

`scripts/check_footprint.py` enforces core import cleanliness, cold-import speed,
and a 6 MiB uncompressed wheel ceiling:

| Check | Invocation | Assertion |
| --- | --- | --- |
| **import-clean** | (no args) | `import aegean` imports zero watched heavy packages and no stdlib modules unvendored by Pyodide |
| **import-fast** | (no args) | fastest of 5 cold subprocess imports (after 1 warmup) stays under 750 ms on Windows and 500 ms in CI |
| **nothing-heavy-bundled** | `--wheel <path>` | wheel contains code and JSON only (no `.so`, `.pyd`, `.dll`, `.onnx`, `.npy`, `.gz`, …) under the 6 MiB ceiling |

Watched modules: `pandas`, `numpy`, `scipy`, `lxml`, `anthropic`, `openai`,
`google`, `torch`, `onnxruntime`, `tokenizers`, `transformers`, `geopandas`,
`shapely`, `textual`, `markdown_it`, plus stdlib `sqlite3` (unvendored by
Pyodide; a top-level `import sqlite3` breaks the browser demo). Import all of
these lazily inside functions.

### What CI runs

`.github/workflows/ci.yml` defines ten jobs:

| Job | Scope |
| --- | --- |
| **test** | `ruff` → `mypy` → `scripts/check_api.py` → `pytest` with coverage across Python 3.10–3.15 |
| **cross-platform** | storage, locking, Unicode, SQLite, and review tests natively on Windows and macOS |
| **extras-ai-viz** | installs `[dev,ai,viz-interactive]` and runs offline AI SDK and Plotly tests without skips |
| **geo** | installs `[dev,geo,parquet]` and runs the suite with `-rs` so geopandas and pyarrow tests execute |
| **interop** | installs `[dev,interop]` on Python 3.14 and runs real spaCy, Stanza, and CLTK adapter tests |
| **neural-integration** | provisions the pinned neural model and runs bounded CPU integration tests without skips |
| **demo-released-wheel** | verifies `docs/demo` against the published PyPI wheel |
| **notebooks** | executes notebooks under `notebooks/` via `nbmake` |
| **build** | `python -m build`, `twine check`, wheel + sdist footprint checks, and candidate-wheel demo check |
| **footprint** | core-only install (no extras), followed by `import-clean` and `import-fast` |

CI declares least-privilege `contents: read` permissions; publishing runs in
`release.yml` with per-job `id-token: write` for OIDC trusted publishing.

---

## Zero-dependency core and lazy imports

The build enforces two dependency rules:

1. **Zero core third-party dependencies.** `pyproject.toml` keeps
   `dependencies = []`. Core modeling, collocation statistics, numerals, queries,
   structure detection, SQLite persistence, and research bundles use the Python
   standard library alone. `numpy`/`pandas`, `onnxruntime`, `lxml`,
   `matplotlib`, `textual`, and provider SDKs are optional extras.
2. **Lazy heavy imports.** Import optional or heavy libraries inside the
   function that needs them, never at module top level, keeping cold imports
   fast and preserving Pyodide compatibility.

Standard pattern (from `Corpus.to_dataframe`):

```python
def to_dataframe(self, level: str = "document"):
    try:
        import pandas as pd  # lazy, optional [data] extra
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "to_dataframe() needs pandas; install it with: pip install 'pyaegean[data]'"
        ) from exc
    ...
```

Catch `ModuleNotFoundError` for optional extras and name the install command in
the message.

Large or license-restricted assets (corpora, trained models, imagery) never go
into git or the wheel; route them through `aegean.data.fetch` (SHA-256-verified,
atomic, idempotent). See [Data and Provenance](Data-and-Provenance).

---

## Conventions

- **Lazy heavy imports.** Import `numpy`, `pandas`, `onnxruntime`, `lxml`,
  `textual`, and provider SDKs inside functions.
- **Script-agnostic core.** Writing systems are plugins; `aegean.core` accesses
  scripts only through `Script` and loader registries.
- **No large/binary assets in git or wheels.** Use `aegean.data.fetch()`.
- **Exploratory labeling.** Linear A and Cypro-Minoan are undeciphered. Mark all
  decipherment, cross-linguistic, metrological, and AI outputs exploratory with
  provenance in docstrings and at point of use ([Limitations](Limitations)).
- **Parity-tested ports.** Behavior ported from the Linear A Workbench asserts
  against shared golden fixtures in `tests/fixtures/golden/` so Python and
  TypeScript outputs cannot diverge.
- **Provenance and attribution.** Cite underlying editions and update `NOTICE`
  when adding data sources.
- **Measured claims only.** Published accuracy figures must come from
  reproducible evaluations (`docs/benchmarks.md` and [Benchmarks](Benchmarks))
  pinned in the claims registry.

### Good first contributions

Well-scoped additions from `CONTRIBUTING.md`:

| Contribution | Location | Automated check |
| --- | --- | --- |
| Syllabification exception | `_EXCEPTIONS` in `src/aegean/greek/syllabify.py` | verifies division rejoins to form and differs from rule output |
| Sign-inventory fact (sound value, variant glyph, attribute) | `src/aegean/data/bundled/<script>/signs.json` | inventory tests; cite a scholarly source |
| Gazetteer alignment (Pleiades ID) | `src/aegean/data/bundled/geo/site_coordinates.json` | `scripts/check_gazetteer.py`; include Pleiades URI |
| Collocation / association measure | `src/aegean/analysis/collocation.py` | golden-value test + literature reference |
| Closed-class Greek form | `src/aegean/greek/pos.py` | POS tests |
| Gold benchmark sentence | `aegean.greek.benchmark` | cite the printed edition |

For larger features, open an issue first to agree on scope and interface.

### Pre-1.0 API policy

Supported facade modules are listed in the
[API reference](https://pyaegean.xyz/api/) and tracked in
`scripts/api-manifest.json`. `python scripts/check_api.py` verifies statically
that the facade resolves without importing optional dependencies. Newly added
internal modules do not automatically become supported public API.

Until the `v4` Greek NLP work completes, pre-1.0 APIs may change directly when
needed, with user-visible changes recorded in `CHANGELOG.md` and synced across
the manifest, docs, and tests. Compatibility remains mandatory for currently
hosted assets, models, and published evidence. Fetched artifacts version forward
under new content-addressed names; a `v4` candidate must never overwrite or
mutate `grc-joint-v3`.

---

## How a script plugin is wired

Two registries populate on `import aegean`:

- **script registry**: `aegean.core.script.register(script)` registers a
  `Script` instance under its `id` (`registered_scripts()`, `get_script()`,
  tokenization, sign inventory).
- **loader registry**: `aegean.core.corpus.register_loader(id, fn)` registers a
  zero-argument loader returning a `Corpus` (`aegean.load(id)` /
  `Corpus.load(id)`).

The `Script` interface (`src/aegean/core/script.py`):

```python
class Script(ABC):
    id: str = ""
    name: str = ""

    @property
    @abstractmethod
    def sign_inventory(self) -> SignInventory: ...

    @abstractmethod
    def tokenize(self, raw: str) -> list[Token]: ...
```

Minimal plugin (`src/aegean/scripts/cypriot/__init__.py`):

```python
class Cypriot(Script):
    id = "cypriot"
    name = "Cypriot syllabary"

    @property
    def sign_inventory(self) -> SignInventory:
        return cypriot_inventory()

    def tokenize(self, raw: str) -> list[Token]:
        return [classify(w, None, i) for i, w in enumerate(raw.split())]

register(Cypriot())
```

### Adding a new script plugin

1. Subclass `core.Script`, define `id`, `name`, `sign_inventory`, and
   `tokenize`, and call `register(...)`.
2. Register a corpus loader with `core.corpus.register_loader(id, fn)`.
3. Import the plugin module in `src/aegean/scripts/__init__.py` so it registers
   on `import aegean`.

See `src/aegean/scripts/lineara` and `src/aegean/scripts/greek` for complete
examples, and [Architecture](Architecture) for layering rules (core never
imports scripts).

---

## Adding a corpus

### A. Build a corpus at runtime (no repo change)

`Corpus.from_records` builds a `Corpus` from plain dicts with `"id"` and
`"lines"`, `"words"`, or `"text"`:

```python
from aegean.core.corpus import Corpus

corpus = Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="lineara")

len(corpus)                 # 2
corpus.word_frequencies()   # [('A-DU', 1), ('KU-RO', 1)]
corpus.cite()               # 'User-supplied corpus (Corpus.from_records)'
```

Numerals are inferred by parseability; tokens may be strings or dicts with
`kind`, `status`, and `alt`. Register by name at runtime:

```python
aegean.core.corpus.register_loader("myfind", lambda: corpus)
aegean.load("myfind")
```

For plain text or CSV files, use `aegean.io.from_text`, `from_text_file`,
`from_text_dir`, `from_csv`, or `aegean import`. See
[Data and Provenance → Your own corpus](Data-and-Provenance#your-own-corpus).

### B. Bundle a small sample corpus in the package

Follow `src/aegean/scripts/cypriot/loader.py`:

1. Place compact JSON under `src/aegean/data/bundled/<script>/`.
2. Build `Document` objects in a `@lru_cache(maxsize=1)` loader with explicit
   `Provenance` (source, license, citation) and register it via
   `register_loader(id, fn)`.
3. Bundle only small, license-compatible data. Large or NonCommercial/ShareAlike
   corpora must be fetched, never bundled.

### C. Host a large or restricted corpus as a fetchable asset

Add a `DataSpec` entry to `_REMOTE` in `src/aegean/data/_registry.py` with
pinned `url`, `sha256`, `license`, and `note`, and call `aegean.data.fetch(id)`
inside the loader. Every asset supports a `PYAEGEAN_<NAME>_URL` override. List
registered remote assets with:

```python
import aegean
sorted(aegean.data.versions()["fetched"])
```

See [Data and Provenance](Data-and-Provenance) for licensing rules and
`aegean.data.versions()`.

---

## Adding or correcting a sign value

Sign inventories live in `src/aegean/data/bundled/<script>/signs.json`. Known
keys map onto `Sign` attributes and remaining keys populate `Sign.attrs`:

```json
{
  "label": "A",
  "glyph": "𐘇",
  "codepoint": 67079,
  "phonetic": "a",
  "sharedWithLinearB": true,
  "linearAOnly": false,
  "total": 74,
  "confidence": 1,
  "altGlyphs": []
}
```

| Field | Meaning |
| --- | --- |
| `label` | transliteration label (lookup key, such as `DA`, `A`) |
| `glyph` | Unicode character, if encoded |
| `codepoint` | integer Unicode codepoint |
| `phonetic` | sound value, or omitted for unread Linear A signs |
| `attrs.*` | script-specific metadata (`sharedWithLinearB`, `linearAOnly`, `total`, `confidence`, `altGlyphs`, `source`) |

Cite a scholarly source when editing any sign value or attribute. Linear A sound
values are empirical alignments carrying confidence scores, and most UCD-derived
signs have no established reading ([Linear A](Linear-A),
[Limitations](Limitations)).

Verify edits from Python and the CLI:

```python
import aegean
s = aegean.load("lineara").sign_inventory.by_label("DA")
print(s.label, s.glyph, s.codepoint, s.phonetic)   # DA 𐘀 67072 da
print(s.attrs)
# {'sharedWithLinearB': True, 'linearAOnly': False, 'total': 40,
#  'confidence': 1, 'altGlyphs': []}
```

```bash
aegean sign lineara DA
#            lineara sign DA
# ┌─────────────────────────┬─────────┐
# │ field                   │ value   │
# ├─────────────────────────┼─────────┤
# │ label                   │ DA      │
# │ glyph                   │ 𐘀       │
# │ codepoint               │ U+10600 │
# │ phonetic                │ da      │
# │ attrs.sharedWithLinearB │ True    │
# │ attrs.linearAOnly       │ False   │
# │ attrs.total             │ 40      │
# │ attrs.confidence        │ 1       │
# │ attrs.altGlyphs         │ []      │
# └─────────────────────────┴─────────┘
```

`SignInventory` exposes `by_label`, `by_glyph`, `by_codepoint`, `signs`, and
`to_dataframe`.

---

## Adding a lexicon entry

Deciphered syllabaries (`cypriot`, `linearb`) store `(lemma, gloss)` equations
in `src/aegean/data/bundled/<script>/lexicon.json`, keyed by normalized
(uppercased, editorial-markers stripped) transliteration:

```json
{ "A-KA-TA": { "lemma": "ἀγαθός", "gloss": "good" } }
```

Include a scholarly source, then verify via the reading bridge:

```python
from aegean import scripts
scripts.cypriot.greek_reading("PA-SI-LE-U-SE")   # ('βασιλεύς', 'king')
scripts.cypriot.gloss("PA-SI-LE-U-SE")           # 'king'
```

Pass the returned lemma to `aegean.greek.gloss` or `aegean.greek.lookup` (with
an active lexicon) for full entries. See [Cypriot](Cypriot) and
[Greek NLP](Greek-NLP).

---

## Tests, parity, and golden fixtures

- **Parity tests for ports.** Algorithms ported from the Linear A Workbench
  assert against shared fixtures in `tests/fixtures/golden/` (such as
  `algorithms.json` extracted from the workbench's `*.test.ts`), matching
  TypeScript numeric tolerances so Python and TypeScript cannot drift. Document
  deliberate divergences in `tests/fixtures/golden/README.md`.
- **Property tests for invariants.** Use `hypothesis` for algebraic invariants
  (syllables rejoin to input; alignment symmetry).
- **Data validation tests.** Syllabification exceptions must differ from rule
  output; sign inventories and bundled JSON files are validated on load.

```bash
pytest tests/test_algorithms.py -q
pytest
```

---

## Repository layout

```
src/aegean/
  core/        model corpus script provenance numerals apparatus catalog diagnose resolve word_views
  scripts/     lineara/{loader,inventory,phonetic,sigla,commodities}
               greek/{loader,inventory,nt,perseus,ddbdp,patrologia}
               linearb/{loader,inventory,phonetic,lexicon,epidoc,damos}
               cypriot/{loader,inventory,phonetic,lexicon,analysis}
               cyprominoan/{loader,inventory}  (undeciphered — signs only)
  analysis/    distance align collocation morphology patterns query accounting structure
               allographs clustering commodity compare edge embeddings graph hands
               lb_divergence multivariate null_models procrustes profiling scribal
               segmentation seriation significance stats surprisal
  greek/       normalize tokenize syllabify accent prosody meter phonology pos morphology lemmatize
               pipeline treebank lexicon lexicons paradigms syntax neural_lemmatizer
               joint mst udfeats lemma_rerank documentary confidence calibrate
               bible/{_catalogs,_editions,_lxx,_mes,_strongs,_study,_witnesses}
               proiel ud papygreek dbbe verse_eval nt_eval benchmark
  io/          text epidoc tabular workbench rdf review interop
  bundle.py    zero-dep portable SHA-256 research bundles (aegean-research-bundle/1)
  library.py   unified pack/corpus/work/model library manager
  cli/         `aegean` CLI + REPL ([cli] extra; typer + rich + prompt_toolkit)
  tui/         `aegean tui` terminal UI ([tui] extra; textual), including
               tui/screens/review.py and tui/_review_data.py
  db.py        SQLite corpus persistence + FTS5 search (+ db_jobs.py resumable jobs)
  geo/         Pleiades-aligned gazetteer (GeoDataFrames require [geo])
  viz.py       plotting ([viz] matplotlib; [viz-interactive] plotly)
  cache.py     opt-in analysis cache
  mcp/         MCP tool implementations + mcp_server.py (`aegean-mcp`, [mcp] extra)
  ai/          client cache providers grounding idioms sense capabilities eval
  translate/   hybrid morphology/lexicon + LLM translator
  data/        bundled/{lineara,linearb,cypriot,cyprominoan,greek,geo}/*.json + _registry.py / fetch()
tests/         fixtures/golden/ (+ parity, property, CLI, TUI, and corpus tests)
wiki/          documentation pages (synced to the GitHub wiki by CI)
docs/          benchmarks.md, methodology.md, large-corpora.md + mkdocs API reference site
```

---

## Editing this wiki

Wiki pages live under `wiki/` in the main repository and sync to the GitHub wiki
automatically via `.github/workflows/wiki.yml` on push to `main`. Edit Markdown
files in git instead of the GitHub wiki web editor, which the next sync
overwrites. The mkdocs API reference lives under `docs/` (built with the
`[docs]` extra) and publishes to GitHub Pages.

---

## Notes & limitations

- **Run the footprint guard on a core-only install** (`pip install .`) for an
  unmasked check. With `[dev]` installed, `import-clean` still verifies that
  `import aegean` does not import heavy packages into `sys.modules`.
- **Check CI after local passes.** Width-sensitive tests (such as CLI `--help`
  rendering) can differ between local terminals and CI runners.
- **Heavy and network-dependent tests** (neural models, AI providers, large
  corpus fetches, real framework interop) run in opt-in markers or dedicated CI
  jobs rather than the fast local gate.
- **Label exploratory work explicitly.** Linear A and Cypro-Minoan are
  undeciphered; sign sound values carry confidence weights, and decipherment,
  cross-linguistic, metrological, and AI outputs must carry caveats
  ([Limitations](Limitations)).

See [Architecture](Architecture) for the module map and
[Data and Provenance](Data-and-Provenance) for licensing rules.
