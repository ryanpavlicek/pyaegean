# Development

This page is for people who want to **work on pyaegean itself**: build it from
source, run the same checks CI runs, and add a corpus, a sign value, or a
lexicon entry. If you only want to *use* the toolkit, start at
[Getting Started](Getting-Started) instead; you don't need any of this.

You don't have to be a seasoned Python developer to contribute. Most useful
additions are small, well-scoped facts: a sound value for one sign, a Greek
reading for one syllabic word, a syllabification exception, and each has an
obvious home in a JSON file and an automatic test. The sections below walk
through all of it, with copy-pasteable commands and the real output you should
see.

> New to the layout of the codebase and *why* it's split the way it is? Read the
> [Architecture](Architecture) page alongside this one: it explains the layering
> rules this page tells you how to follow.

---

## Build from source

You need **Python 3.10 or newer** and `git`. Clone the repo and install it in
**editable** mode (`-e`), so your changes take effect without reinstalling, with
the `[dev]` extra that pulls in everything the checks need:

```bash
git clone https://github.com/ryanpavlicek/pyaegean
cd pyaegean
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -e ".[dev]"
```

Confirm it imported:

```bash
python -c "import aegean; print(aegean.__version__, aegean.registered_scripts())"
# 0.27.0 ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

### The `[dev]` extra — what it installs

`pip install -e ".[dev]"` gives you the test runner, the linters, the build
tools, and the optional runtime backends so the whole suite can run in one
environment:

| Tool | Why it's there |
| --- | --- |
| `pytest`, `pytest-cov` | the test suite + coverage |
| `hypothesis` | property-based tests for invariants |
| `mypy` | strict static type-checking (enforced in CI) |
| `ruff` | linter / formatter check |
| `build`, `twine` | wheel build + package metadata check |
| `nbmake`, `ipykernel` | execute the example notebooks under pytest |
| `pandas` | exercise the `[data]` DataFrame interop in tests |
| `typer`, `rich` | the `aegean` CLI (the `[cli]` extra) |
| `lxml` | EpiDoc TEI export (the `[epidoc]` extra) |
| `matplotlib` | one-line plots (the `[viz]` extra) |
| `mcp` | the `aegean-mcp` Model Context Protocol server |
| `textual` | the `aegean tui` terminal UI (the `[tui]` extra) |

The `[dev]` extra deliberately does **not** include the heavy neural backend
(`onnxruntime`, `tokenizers`, `numpy`) or the AI provider SDKs: those tests run
without them and skip the parts that need a model or an API key. If you're
working on the neural pipeline specifically, add `pip install -e ".[neural]"`.
The full list of extras is in [Installation](Installation).

---

## The check suite (the merge gate)

Every change must pass the full gate before it lands on `main`. These are the
exact commands CI runs: run them locally first and you'll never be surprised by
a red build. A **green local gate is necessary but not always sufficient**: a
couple of checks (notably anything that renders CLI `--help`) can behave
differently in CI's terminal width, so watch the CI run on your shipping commit
too.

```bash
ruff check src tests                       # 1. lint
mypy                                       # 2. strict type-check
pytest                                     # 3. the test suite
python scripts/check_footprint.py          # 4. import-clean + import-fast
```

And the packaging checks (only needed when you touch packaging/data):

```bash
python -m build && python -m twine check dist/*
python scripts/check_footprint.py --wheel "dist/*.whl"   # wheel = code + JSON only
```

Pinned remote assets (release tarballs + commit-pinned upstream sources) are verified on a
weekly schedule by `.github/workflows/assets.yml`, not per-PR — link rot is a function of
time, not of any one change. Run it yourself anytime:

```bash
python scripts/check_assets.py                 # every pinned URL still resolves
python scripts/check_assets.py --verify-hashes # also sha256-verify the release assets (slow)
python scripts/check_gazetteer.py              # every Pleiades-linked find-site is near its place
```

A quick smoke check that the bundled corpus still loads:

```bash
python -c "import aegean; print(len(aegean.load('lineara')))"   # 1721
```

### What each step looks like when it passes

**1. Lint (ruff).** Line length 100, `src` + `tests` checked:

```bash
ruff check src tests
# All checks passed!
```

**2. Type-check (mypy).** Strict mode over `src/aegean`. The config lives in
`pyproject.toml` (`[tool.mypy] strict = true`); third-party libs that ship no
stubs (pandas, numpy, the provider SDKs, onnxruntime, lxml, …) are listed as
`ignore_missing_imports` overrides, so a clean run means *your* types are clean:

```bash
mypy
# Success: no issues found in 144 source files
```

**3. Tests (pytest).** Run the whole suite, or a single file while you iterate:

```bash
pytest                       # full suite, quiet (-q is the default via pyproject)
pytest tests/test_numerals.py -q
# ......                                                                   [100%]
```

In CI the test job runs with coverage (`pytest --cov=aegean
--cov-report=term-missing`) across the full Python matrix.

**4. Footprint guard.** This is the check that defends the project's defining
promise: that `import aegean` is instant and pulls in nothing heavy. Run it
**after a core-only install** (no extras) for a faithful reading; with `[dev]`
installed the heavy libs are present in the environment but still must not be
*imported by* `import aegean`:

```bash
python scripts/check_footprint.py
# loaded on import: none
# OK  import-clean
# cold import best 226 ms (bound 500); samples [229, 230, 234, 226, 231]
# OK  import-fast
```

The wheel check asserts the built wheel ships only code + JSON: no binaries:

```bash
python scripts/check_footprint.py --wheel "dist/*.whl"
# wheel dist/pyaegean-0.27.0-py3-none-any.whl: 3557 KB uncompressed, 187 files
# OK  nothing-heavy-bundled
```

`twine check` confirms the package metadata (README rendering, classifiers,
license expression) is valid for PyPI:

```bash
python -m twine check dist/*
# Checking dist/pyaegean-0.27.0-py3-none-any.whl: PASSED
```

### The footprint guard in detail

`scripts/check_footprint.py` enforces three invariants. It replaced an old
"wheel must be under N MB" byte cap that was theater: the wheel is tiny no
matter what, so the cap could never fail while saying nothing about what
actually matters.

| Check | Run with | What it asserts |
| --- | --- | --- |
| **import-clean** | (no args) | `import aegean` loads **no** heavy third-party module and none of the stdlib modules Pyodide unvendors (so the in-browser demo keeps working) |
| **import-fast** | (no args) | cold `import aegean` (fastest of 5 subprocess runs, after a warmup) stays under **500 ms** |
| **nothing-heavy-bundled** | `--wheel <path>` | the wheel contains code + JSON only: no `.so/.pyd/.dll/.onnx/.npy/.gz/...`: under a 5 MB accident tripwire |

The "heavy" watch-list is `pandas, numpy, scipy, lxml, anthropic, openai,
google, torch, onnxruntime, tokenizers, transformers, geopandas, shapely`, plus
the stdlib `sqlite3` (which Pyodide unvendors: a top-level `import sqlite3`
once broke the browser demo, so the guard doubles as a regression sentinel). If
you add a feature that needs one of these, the guard will fail until you make
that import **lazy** (see the next section).

### What CI runs

CI (GitHub Actions, `.github/workflows/ci.yml`) has four jobs:

| Job | What it does |
| --- | --- |
| **test** | `ruff` → `mypy` (enforcing) → `pytest` with coverage, across **Python 3.10–3.14** |
| **notebooks** | executes the example notebooks under `notebooks/` with `nbmake` |
| **build** | `python -m build`, `twine check`, and the **wheel** footprint check |
| **footprint** | installs the **core only** (no extras), then the import-clean + import-fast guard |

CI declares least-privilege permissions (`contents: read`); publishing lives in
a separate `release.yml` that escalates per-job only where it needs
`id-token: write` for OIDC trusted publishing.

---

## The zero-dependency, import-clean philosophy

This is the single most important convention to internalize, because the build
will reject changes that break it. Two rules:

1. **The core has zero hard third-party dependencies.** Look at
   `pyproject.toml`: `dependencies = []`. Installing pyaegean installs the full
   library and the full Linear A corpus and nothing else. `numpy`/`pandas`,
   `onnxruntime`, `lxml`, `matplotlib`, and the provider SDKs are all **optional
   extras**, never hard requirements. Collocation statistics, numerals, the
   query engine, structure detection: all pure standard library.

2. **`import aegean` stays instant and clean.** Anything heavy must be imported
   **inside the function that needs it**, not at module top level. This keeps
   the cold import fast and lets the package import under Pyodide in the browser.

The pattern, straight from the codebase: `Corpus.to_dataframe` imports pandas
lazily and turns its absence into a helpful error rather than a crash at import:

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

Do the same for any new heavy import: import it at the top of the function, and
when it's an optional extra, catch `ModuleNotFoundError` and name the extra in
the message. The footprint guard verifies you did.

**No bundled binaries.** Large or license-restricted assets (corpora, trained
models, the facsimile imagery) are **never** committed or shipped in the wheel.
They go through the download-to-cache layer (`aegean.data.fetch`), which is
sha256-verified, atomic, and idempotent. See
[Data and Provenance](Data-and-Provenance) for the full story and the table of
fetchable assets.

---

## Conventions

- **Lazy heavy imports.** As above: `numpy`/`pandas`, `onnxruntime`, `lxml`, and
  provider SDKs are imported inside the functions that need them.
- **Script-agnostic core.** New writing systems are plugins. The core
  (`aegean.core`) never imports a specific script: it knows them only through
  the `Script` interface and a loader registry.
- **No large/binary assets in the repo or wheel.** Use `aegean.data.fetch()`.
- **Exploratory labeling.** The Linear A material is undeciphered. Any
  decipherment, cross-linguistic, metrological, or AI-generated result must be
  marked exploratory/unverified, with provenance, in docstrings **and** at the
  point of use. See [Limitations](Limitations).
- **Faithful, parity-tested ports.** Behavior ported from the Linear A Workbench
  asserts against shared golden values in `tests/fixtures/golden/`, so the
  Python port can't silently diverge from the TypeScript original.
- **Provenance & attribution are first-class.** Cite the underlying editions;
  keep `NOTICE` accurate as data sources are added.
- **Measured claims only.** Accuracy numbers in docs must come from a
  reproducible evaluation (`docs/benchmarks.md` has the protocol); tool-to-tool
  comparisons live there, not in the README or wiki.

### Good first contributions

Small facts with an obvious home and an automatic test: the menu from
`CONTRIBUTING.md`:

| Contribution | Where it goes | What checks it |
| --- | --- | --- |
| A syllabification exception | `_EXCEPTIONS` in `src/aegean/greek/syllabify.py` (with its division) | the suite checks it rejoins to the form *and* differs from the rule engine (entries the rules already get right are rejected) |
| A sign-inventory fact (sound value, variant glyph, attribute fix) | `src/aegean/data/bundled/<script>/signs.json` | inventory tests; include a source |
| A gazetteer alignment (a find-site's Pleiades ID) | `src/aegean/data/bundled/geo/site_coordinates.json` | cite the Pleiades URI |
| A collocation / association measure | `src/aegean/analysis/collocation.py` | a golden-value test + a literature reference |
| A closed-class form (article/particle/pronoun) | the POS lexicon, `src/aegean/greek/pos.py` | the POS tests |
| A benchmark sentence (gold lemma/POS) | `aegean.greek.benchmark` | name the edition you read it from |

For anything larger, open an issue first so the design can be agreed before you
write code.

### Deprecation policy

pyaegean is pre-1.0, but the public API is treated as a contract:

1. **Deprecate in a minor release, remove no sooner than the next minor.** A
   symbol deprecated in 0.x.0 keeps working through every 0.x.* and may be
   removed in 0.(x+1).0 at the earliest.
2. **Warnings carry the replacement.** Every deprecation emits a
   `DeprecationWarning` that names the replacement API and the release that
   introduced the deprecation.
3. **The CHANGELOG records both ends**: the release that deprecates and the
   release that removes.
4. **Data and models version forward.** Fetched artifacts are sha256-pinned
   release assets; a new model is a new asset name (`grc-joint-v2`), never a
   mutation of an existing one, so cached environments keep working.

---

## How a script plugin is wired

A writing system is a plugin the core knows only by interface. There are two
registries, both populated on `import aegean`:

- the **script registry**: `aegean.core.script.register(script)` records a
  `Script` instance under its `id` (powers `registered_scripts()`,
  `get_script()`, tokenization, the sign inventory);
- the **loader registry**: `aegean.core.corpus.register_loader(id, fn)` records
  a zero-arg function that returns a `Corpus` (powers `aegean.load(id)` /
  `Corpus.load(id)`).

The `Script` contract is small (`src/aegean/core/script.py`):

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

The Cypriot plugin is a compact worked example
(`src/aegean/scripts/cypriot/__init__.py`):

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

1. **Subclass `core.Script`**: set `id`, `name`, and implement `sign_inventory`
   and `tokenize`, and `register()` the instance.
2. **Register a corpus loader** with `core.corpus.register_loader(id, fn)`.
3. **Import your plugin** from `src/aegean/scripts/__init__.py` so it registers
   on `import aegean`.

See `src/aegean/scripts/lineara` and `src/aegean/scripts/greek` for full worked
examples, and [Architecture](Architecture) for the layering rules a plugin must
respect (the core never imports a script; a script imports up into the core).

---

## Adding a corpus

You have two routes, depending on whether the data is yours to add to the
package or yours to keep local.

### A. Build your own corpus at runtime (no repo change)

`Corpus.from_records` turns plain dict records into a full `Corpus`: filter,
query, DataFrames, citation, export all work. Each record needs an `"id"` and
its text as one of `"lines"` (a list of physical lines), `"words"` (a flat
list), or `"text"` (a whitespace-tokenized string). This runs today against the
installed package:

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

Numerals are inferred by parseability; tokens can be a string or a dict with
`kind`, `status`, and `alt`. To make it loadable **by name**, register a loader
(no file edit needed):

```python
aegean.core.corpus.register_loader("myfind", lambda: corpus)
aegean.load("myfind")
```

For a corpus you carry across sessions, the loader can read from a fetchable
asset (next section) or from a local file via the `Corpus.to_json` /
`from_json` / `to_sql` / `from_sql` round-trips.

If your material is already **plain text or a CSV**, skip the `from_records`
boilerplate: `aegean.io.from_text` / `from_text_file` / `from_text_dir` /
`from_csv` build the same `Corpus` for you (Greek text runs through the Greek
tokenizer; other scripts split on whitespace), and the `aegean import` CLI does
it with no Python. See [Your own corpus](Data-and-Provenance#your-own-corpus).

### B. Bundle a small sample corpus in the package

The Cypriot loader (`src/aegean/scripts/cypriot/loader.py`) is the model:

1. Add the sample JSON under `src/aegean/data/bundled/<script>/`.
2. Build `Document`s into a `Corpus` in your loader, attach a `Provenance` that
   states the **source, license, and citation**, and `register_loader(id, fn)`
   it (cache the build with `@lru_cache(maxsize=1)`).
3. Keep it **small and redistributable**: only bundle what the license allows.
   Larger corpora (DAMOS, SigLA) and license-restricted ones are **fetched**,
   not bundled.

### C. Host a large / restricted corpus as a fetchable asset

Add a `DataSpec` to `_REMOTE` in `src/aegean/data/__init__.py` with a pinned
`url`, `sha256`, `license`, and `note`; the loader calls `aegean.data.fetch(id)`
to download-and-verify into the cache the first time it's used. This is how
`aegean.load("damos")`, `"sigla"`, and `"nt"` work. Every fetchable asset's URL
can be overridden with a `PYAEGEAN_<NAME>_URL` env var so a user can point at
their own licensed copy. The full list of currently registered assets:

```python
import aegean
sorted(aegean.data.versions()["fetched"])
# ['abbott-smith-index', 'agdt-derived', 'cunliffe-index', 'damos-corpus',
#  'grc-joint', 'grc-lemma-neural', 'lineara-images', 'linearb-corpus',
#  'lsj-index', 'middle-liddell-index', 'nt-corpus', 'sigla-corpus',
#  'workbench-app']
```

See [Data and Provenance](Data-and-Provenance) for the licensing rules that
decide bundle-vs-fetch, and `aegean.data.versions()` for the reproducibility
manifest (every bundled file's sha256 + size, and every fetchable asset's pinned
URL/sha256/license/cache-state) you should record alongside published results.

---

## Adding or correcting a sign value

Sign inventories are built from JSON sign tables under
`src/aegean/data/bundled/<script>/signs.json`. Each entry is a flat object; the
inventory builder maps the known keys onto a `Sign` and carries the rest into
`Sign.attrs`. A Linear A entry looks like this:

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
| `label` | the transliteration label (e.g. `DA`, `A`): the lookup key |
| `glyph` | the Unicode character, when known |
| `codepoint` | its integer code point |
| `phonetic` | the sound value, or absent for an unread Linear A sign |
| `attrs.*` | script-specific facts; for Linear A: `sharedWithLinearB`, `linearAOnly`, `total` (attestations), `confidence`, `altGlyphs`, `source` |

To **correct a sound value or attribute**, edit the entry in `signs.json` and
**cite a source**. Linear A sound values are an *empirical* alignment, not
canon: each carries a `confidence`, and most of the repertoire (carried from
the Unicode Character Database, `source="ucd"`) has no agreed reading at all.
Treat values as evidence; see [Linear A](Linear-A) and [Limitations](Limitations).

Verify your edit two ways: Python and CLI:

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

The `SignInventory` lookups available to a test or a feature:
`by_label`, `by_glyph`, `by_codepoint`, `signs`, and `to_dataframe`.

---

## Adding a lexicon entry

The deciphered syllabaries (Cypriot, Linear B) carry a bundled lexicon that maps
a transliterated word to its **Greek reading**: a `(lemma, gloss)` pair. The
file is `src/aegean/data/bundled/<script>/lexicon.json`, keyed by the normalized
(uppercased, editorial-markers stripped) transliteration:

```json
{ "A-KA-TA": { "lemma": "ἀγαθός", "gloss": "good" } }
```

Add the equation with a source (the Cypriot lexicon holds the well-established
ones: e.g. `PA-SI-LE-U-SE` → βασιλεύς). Then verify through the bridge:

```python
from aegean import scripts
scripts.cypriot.greek_reading("PA-SI-LE-U-SE")   # ('βασιλεύς', 'king')
scripts.cypriot.gloss("PA-SI-LE-U-SE")           # 'king'
```

Pass the returned lemma to `aegean.greek.gloss` / `aegean.greek.lookup` (with
the LSJ backend active) for the full dictionary entry. See
[Cypriot](Cypriot) and [Greek NLP](Greek-NLP) for the reading bridge and the
dictionary backends.

---

## Tests, parity, and golden fixtures

Every behavior gets a test. The conventions:

- **Ports get parity tests.** When you port analysis from the Linear A
  Workbench, assert against the **shared golden values** in
  `tests/fixtures/golden/` (e.g. `algorithms.json`, extracted from the
  workbench's own `*.test.ts`). Numeric tolerances mirror the TypeScript
  `toBeCloseTo(value, digits)`. Two implementations asserting the *same* numbers
  is how the Python port can never silently drift. Any deliberate divergence
  from the TypeScript behavior is documented in `tests/fixtures/golden/README.md`.
- **Invariants get property tests** with `hypothesis` (e.g. syllables rejoin to
  the original word; an alignment is symmetric).
- **Data edits get data tests**: the syllabification-exception check rejects an
  entry the rules already get right; inventory tests check the sign tables load.

Run a focused file while you iterate, the whole suite before you push:

```bash
pytest tests/test_algorithms.py -q
pytest                                # full suite
```

---

## Repository layout

```
src/aegean/
  core/      model corpus script provenance numerals
  scripts/   lineara/{loader,inventory,phonetic,sigla,commodities}  greek/{loader,inventory,nt,perseus}
             linearb/{loader,inventory,phonetic,lexicon,epidoc,damos}
             cypriot/{loader,inventory,phonetic,lexicon}
             cyprominoan/{loader,inventory}  (undeciphered — signs only)
  analysis/  distance align collocation morphology patterns query accounting structure
  greek/     normalize tokenize syllabify accent prosody meter phonology pos morphology lemmatize
             pipeline (one-call records) treebank (AGDT lexicon) lexicon (LSJ)
             syntax (dependency parser) neural_lemmatizer (GreTa seq2seq)
             joint (neural pipeline) mst udfeats
             proiel (out-of-AGDT eval) ud (UD eval) benchmark (harness)
  io/        text (.txt/.csv/folder import) epidoc (TEI export)
             tabular (CSV/Parquet export) workbench (Workbench JSON I/O)
  cli/       the `aegean` command ([cli] extra; typer+rich, imported only by the console script)
  ai/        client cache providers grounding capabilities
  translate/ (hybrid lexicon+LLM)
  data/      bundled/{lineara,linearb,cypriot,cyprominoan,greek,geo}/*.json  + fetch()/cache
tests/       fixtures/golden/   (+ parity, property, and corpus tests)
wiki/        this documentation (published to the GitHub wiki by CI)
docs/        benchmarks.md, methodology.md, large-corpora.md + the API-reference site (mkdocs)
```

---

## Editing this wiki

These pages live in `wiki/` **in the main repo** and are published to the GitHub
wiki automatically by `.github/workflows/wiki.yml` on push to `main`. Edit the
Markdown here and open a normal change: do **not** edit the wiki UI directly, or
the next sync will overwrite it. The API reference is separate: it's a mkdocs
site under `docs/` (build it with the `[docs]` extra) published to GitHub Pages.

---

## Notes & limitations

- The **footprint guard reads truest after a core-only install** (`pip install
  .`, no extras). With `[dev]` installed the heavy libraries exist in the
  environment, so import-clean's job is to prove `import aegean` still doesn't
  *touch* them. CI runs the guard in a clean core-only job for exactly this
  reason.
- A **green local gate is necessary but not always sufficient.** A few checks
  depend on terminal width or environment specifics: anything rendering CLI
  `--help` text can pass locally and fail in CI's narrower terminal. Watch the
  CI run on your shipping commit.
- **Heavy and network examples** (the neural pipeline, AI providers, fetching a
  large corpus) need an extra installed and/or a download, so they aren't part
  of the fast local gate. They're covered by their own opt-in tests.
- Linear A is **undeciphered**; the sign sound values are empirical and
  confidence-weighted, and any decipherment/cross-linguistic/metrological/AI
  output is exploratory. Keep new contributions honestly labeled: see
  [Limitations](Limitations).

For the conceptual map of the codebase, read [Architecture](Architecture). For
the data-licensing rules behind bundle-vs-fetch, read
[Data and Provenance](Data-and-Provenance).
