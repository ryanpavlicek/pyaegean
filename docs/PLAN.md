# pyaegean — a specialist Python package for Ancient Greek (alphabetic + Aegean syllabic)

## Context

The Linear A Workbench (TS) is web-only; researchers publish in Python (Jupyter/pandas). Research
confirmed: **no Python package exists** for any Aegean syllabic script (Linear A/B, Cypro-Minoan,
Cypriot), and the canonical corpora (DAMOS, LiBER, lineara.xyz, SigLA) are **web-only with no API**.
**CLTK** is the incumbent for Ancient Greek NLP — but it is a *generalist* across many ancient
languages.

**Strategic goal (revised, per user):** pyaegean is a **Greek specialist** — a deep, focused package
for **Ancient Greek specifically**, spanning **alphabetic Greek (Archaic→Koine) AND the Aegean
syllabic scripts (Linear A/B, Cypriot)** — aiming over time for thorough, high-quality Greek coverage,
measured against CLTK as a friendly benchmark, plus specialty tooling for the Aegean scripts: Linear
A/B analysis, translation, and a pluggable multi-provider AI layer. CLTK is an excellent
general-purpose library across many ancient languages; pyaegean is deliberately narrower and Greek-
focused. Standalone repo; does not modify the workbench.

## Locked decisions

- **Name** PyPI `pyaegean`, `import aegean` (verify availability; note branding tension below).
- **Repo** new standalone; Apache-2.0; provenance/attribution first-class.
- **Positioning** a Greek specialist; aim to meet or exceed CLTK's Greek coverage over time, measured
  by benchmark (do **not** depend on CLTK). May benchmark against it and reuse the same **open data**
  (not its code).
- **Coverage** alphabetic Ancient Greek (full NLP) + Aegean syllabic scripts; Greek is first-class.
- **Center of gravity** corpus **data layer**, with Greek NLP + AI + translation as headline capabilities.
- **AI** multi-provider (Anthropic *default/latest Claude*, OpenAI, xAI Grok, Google Gemini); all four
  jobs: translation/glossing, decipherment hypotheses, Greek-NLP assist/disambiguation, corpus
  Q&A/summarization. Keys via env/config; grounded; all generative output labeled exploratory. **v0.2.**
- **Greek NLP data** HYBRID, evolve over time: open-data baseline (Perseus/PROIEL treebanks, Morpheus,
  LSJ, First1KGreek) → progressively our own + AI-improved components.
- **v0.1** core + Linear A (incl. downloader) + **Greek start** (corpus loader + first NLP components).
- **Data** bundle only tiny JSON in the wheel; **download the 500 MB Linear A corpus from the
  linearaworkbench repo** (no re-host) into a user cache; host freely-licensable Linear B / Greek data
  as pyaegean release assets; wrap DAMOS/LiBER/Perseus from upstream. No Git LFS; CI wheel-size guard.
- **Claude Code plugin** parked as a tracked side project.

## Architecture — strict downward-only layers

```
SIDE  Claude Code plugin (separate side project; consumes the public API)
L6  ai (aegean.ai)         provider-agnostic LLM clients: Anthropic(default)/OpenAI/Grok/Gemini
                           capabilities: translate · gloss · decipher_hypotheses · nlp_assist · ask/summarize
                           key mgmt · grounding (lexicon/corpus) · response cache · "exploratory" labeling
L5  translate              hybrid: lexicon+morphology grounding → LLM; Greek & Linear B → English
L5  greek (aegean.greek)   FULL Greek NLP: normalize(unicode/betacode) · tokenize · syllabify · accentuation
                           · phonology/IPA · lemmatize · morphology · POS · (later) dependency parse · prosody/meter
                           · LSJ lexicon · treebank loaders.  Hybrid open-data seed + our code + AI augment.
L4  io · data · adapters   JSON/EpiDoc/CSV/Parquet · bundled registry + downloader/cache · DAMOS/LiBER/Perseus/lineara.xyz
L3  analysis               script-agnostic + Aegean-specific: distance · align · morphology-cluster · collocation
                           · patterns · query · accounting · structure  (generic stats → scipy)
L2  scripts (plugins)      lineara (v0.1) · greek (v0.1 start) · linearb / cypriot / cyprominoan (later)
L1  core                   Corpus · Document · Token · Sign · SignInventory · Numeral · Script(ABC) · Registry
                           · Provenance · lazy DataFrame interop   (zero heavy deps)
```
A `Script` is a plugin (ABC) the core knows only by interface. Greek and Linear A are both just
registered scripts; `greek`/`translate`/`ai` are capability layers above. CLTK is **not** a dependency
at any layer — it is a benchmark target.

## Core data model (`aegean.core`) — unchanged essence, generalized for Greek

Frozen `@dataclass(slots=True)` value objects; numpy/pandas lazy.
- **`Script` ABC** + `ScriptRegistry`: `id`, `unicode_ranges`, `tokenize`, `transliterate`/`to_glyphs`,
  `sign_inventory`, optional capabilities (`phonetic_map`, `numeral_system`, `nlp`). Greek's `nlp`
  capability returns the `aegean.greek` pipeline; Linear A's returns `None`.
- **`Sign`** (syllabogram | letter | logogram), **`Token`** (`kind`: WORD/LOGOGRAM/NUMERAL/SEPARATOR/…
  plus Greek adds PUNCT), **`Document`** (+ `DocumentMeta`), **`Corpus`** (the hub:
  `load()/from_json()/from_epidoc()`, `.filter()`, `.query()`, **`.to_dataframe(level=…)`**,
  `.word_frequencies()`, `.to_json/parquet/epidoc`, `.provenance`), **`NumeralSystem`**/`AegeanNumerals`.
- Greek `Document`s carry token-level NLP annotations (lemma/POS/morph/IPA) when the pipeline has run,
  surfaced in `.to_dataframe(level="token")`.

## Greek NLP track (`aegean.greek`) — the Greek-specialist core

Pipeline of composable, individually-callable stages (each a function + a class for reuse):
`normalize` (NFC/NFD, betacode↔unicode, diacritic handling) → `tokenize` (word/sentence) →
`syllabify` → `accentuate`/accent analysis → `phonology` (IPA, by period) → `lemmatize` →
`morphology` (full parse: case/number/gender/tense/voice/mood/person) → `pos` → (v0.3+) `parse`
(dependency, trained on PROIEL/Perseus) → `prosody`/`meter` (hexameter/iambic scansion) →
`lexicon` (LSJ lookup). Hybrid sourcing: ship/download open data (Morpheus tables, treebanks, LSJ),
implement our own engine, and let `aegean.ai.nlp_assist` disambiguate/fill gaps. **Benchmark harness**
(`tests/benchmark_greek/`) scores each stage against gold treebanks and, as a reference point, against
CLTK — tracking "are we at least as good on Greek" as a measured metric.

## AI layer (`aegean.ai`) — v0.2, multi-provider

- **Provider abstraction**: `LLMClient` ABC + adapters `anthropic.py`, `openai.py`, `grok.py`
  (OpenAI-compatible base-url), `gemini.py`. `get_client(provider=…, model=…)`; **default provider
  Anthropic, default model = the latest flagship Claude (configurable; keep current).** Keys from env
  (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`XAI_API_KEY`/`GEMINI_API_KEY`) or explicit config; **never
  logged**.
- **Capabilities** (all four): `translate()`, `gloss()`, `decipher_hypotheses()` (Linear A; cites
  corpus evidence), `nlp_assist()` (lemma/POS/parse disambiguation), `ask()`/`summarize()` over a
  `Corpus`+commentary.
- **Grounding & safety**: feed the model our lexicon/morphology/corpus context (RAG-style) so it
  reasons over real data; **every generative output is wrapped with an `exploratory`/unverified flag +
  provenance** (which model, prompt version); response caching keyed on (provider, model, prompt) to
  control cost; corpus text treated as untrusted input (prompt-injection aware).
- SDKs are **optional extras** (`pip install pyaegean[anthropic|openai|grok|gemini|ai]`), guarded imports.

## Package layout (`src/` layout, additions in **bold**)

```
src/aegean/
  core/      model.py corpus.py script.py provenance.py numerals.py dataframe.py
  scripts/   lineara/{__init__,inventory,phonetic,loader}.py   **greek/{__init__,inventory,loader}.py**
  analysis/  distance align morphology collocation patterns query accounting structure .py
  **greek/   normalize tokenize syllabify accent phonology lemmatize morphology pos parse prosody lexicon .py**
  **translate/ __init__.py (hybrid lexicon+LLM)**
  **ai/      client.py (ABC) anthropic.py openai.py grok.py gemini.py prompts/ grounding.py cache.py**
  io/        json_io epidoc tabular .py
  data/      registry.py _cache.py  bundled/lineara/*.json  **bundled/greek/*.json (small seeds)**
  adapters/  base.py  (damos liber lineara_xyz sigla perseus first1kgreek .py — phased)
  integrations/ geo.py        # note: no cltk dependency — pyaegean implements its own Greek NLP
tests/ fixtures/golden/  benchmark_greek/  test_parity_lineara.py  test_benchmark_greek.py
```

## Data hosting (download-first; structurally avoids the 500 MB problem)

- **Bundled in wheel** (offline-capable basics): compact Linear A text JSON (~hundreds KB),
  small Greek seeds (sample texts, betacode tables). Wheel **< ~3 MB**; CI guard fails otherwise.
- **`aegean.data.fetch(name)`** → `platformdirs` user cache, sha256-verified, idempotent, graceful
  `DataNotAvailableError` (names the exact call + license). Registry `DataSpec(name, kind, url, sha256, license)`.
  - `fetch("lineara")` / `fetch("lineara-images")` → **download from the `ryanpavlicek/linearaworkbench`
    repo** (pinned release tag / raw URLs) — the 500 MB lives there; we never re-host it.
  - **pyaegean repo release assets** host freely-licensable **Linear B** data and **Greek** resources
    (First1KGreek CC-BY, treebanks, LSJ where permitted) — this is what the freed repo space is for.
  - DAMOS/LiBER/Perseus → adapters fetch from **upstream**, cache, no re-host (licensing permitting).
- No Git LFS; no binaries committed; clean clone is a few MB.

## Dependencies

- **Python ≥ 3.10**, mypy/pyright strict, `py.typed`.
- **Core**: `numpy`, `pandas`, `scipy` (lazy). Greek NLP: `regex`, `lxml` (TEI), our own engine; treebank/lexicon data downloaded.
- **Extras**: `[anthropic]`,`[openai]`,`[grok]`,`[gemini]`,`[ai]`(all) · `[epidoc]`(lxml/PyEpiDoc) ·
  `[geo]`(geopandas) · `[align]`(biopython, optional) · `[all]`. All AI/adapter imports guarded.

## Parity, benchmarking & correctness

1. **Linear A parity** — shared language-neutral **golden fixtures** extracted from the TS tests
   (`algorithms/numerals/compareAlign/signPattern/queryEngine.test.ts`); both repos assert the same
   JSON; `test_parity_lineara.py` runs ported analysis over the real corpus (CI-blocking). scipy
   replaces the TS erf/lgamma approximations, validated against golden.
2. **Greek benchmark** — `test_benchmark_greek.py` scores lemmatizer/POS/morph/parse against gold
   treebanks **and, as a reference point, against CLTK**; "at least as good as CLTK on Greek" is a
   measured, tracked metric, not a vibe.
3. **AI** — provider adapters tested with mocked HTTP (no live keys in CI); grounding/labeling/caching
   unit-tested; a tiny optional live smoke gated behind a secret.
4. **Property tests** (`hypothesis`) mirror the TS `*.properties.test.ts` invariants.

## Packaging & infra

`hatchling`/PEP 621, `src/` layout, bundled data via `force-include`. `pytest`+`cov`+`hypothesis`;
coverage gate; matrix Py 3.10–3.13 × {no-extras, [all]}. GitHub Actions: `ruff`, `mypy --strict`, tests,
build, `twine check`, **wheel-size guard**, OIDC publish on tag. Docs `mkdocs-material`+`mkdocstrings`;
port methodology + limitations into docstrings. Provenance: per-dataset `DataSpec.license`/`citation`,
`Corpus.provenance.cite()`, `CITATION.cff`, `NOTICE` (GORILA, DAMOS, LiBER, Perseus, First1KGreek).

## Roadmap (sequenced by value × feasibility)

- **v0.1** Core + Linear A (downloader for the workbench 500 MB corpus) + **Greek start**: Greek corpus
  loader (First1KGreek/Perseus subset) + first NLP stages (normalize/betacode, tokenize, syllabify,
  accentuation, baseline lemmatize via open data). Linear A parity suite. Offline basics.
- **v0.2** **AI layer** (Anthropic default + OpenAI + Grok + Gemini) wired to all four jobs;
  **translation/glossing**; corpus Q&A; decipherment-hypothesis support; NLP-assist disambiguation.
- **v0.3** Deepen Greek NLP (measured against the CLTK benchmark): full morphological analyzer, POS,
  dependency parsing (PROIEL/Perseus-trained), prosody/meter, LSJ integration; publish the benchmark.
  *(Landed: opt-in Perseus AGDT v2.1 treebank lemmatizer/morphology + POS via `greek.use_treebank()`;
  benchmark harness measures the lift — lemma 28%→100%, POS 50%→100% on the gold set. CLTK live
  head-to-head documented but pending a stanza/LLM backend.)*
- **v0.4** **Linear B**: DAMOS/LiBER adapters + `LinearB` script + freely-licensed data hosted in the
  pyaegean repo (gated by licensing confirmation).
- **v0.5** Cypriot syllabary + Cypro-Minoan.
- **Side project** Claude Code plugin exposing pyaegean (translate/gloss/decipher/ask) as slash-commands/MCP.
- **v1.0** Stable: alphabetic + all syllabic scripts uniform through one API; Greek NLP measured at
  least on par with CLTK; AI + translation integrated; full EpiDoc round-trip.

## Critical reference files (TS repo, to port from)

`src/lib/algorithms.ts` (distance/schemes/alignment/morphology/stats), `numerals.ts` (numerals +
KU-RO accounting), `signPattern.ts`, `compareAlign.ts`, `queryEngine.ts`, `corpusExport.ts`+`types.ts`
(schema), `public/corpus/{inscriptions,signs}.json` (Linear A data — downloaded, not bundled whole),
`src/data/*` (phoneticMap/languages/siteCoords/commodities/abNumbers), `docs/METHODOLOGY.md`, the
`*.test.ts` files (golden-fixture source).

## Open questions / risks

1. **Name vs scope** — `pyaegean`/`aegean` reads "Bronze Age Aegean," but scope is *all* Ancient Greek
   incl. Classical/Koine. Keep the name (chosen) but consider tagline/branding that says "Ancient Greek";
   revisit before publish if desired.
2. **Matching CLTK on Greek is a multi-year arc** — full morphology+parsing+meter is large. v0.1–0.2 will
   *not* yet rival CLTK across the board; the benchmark harness makes progress honest and measurable. Set expectations.
3. **AI**: provider SDK choices (Grok via OpenAI-compatible client; Gemini via `google-genai`); cost/rate
   limits; **prompt-injection** from untrusted corpus text; never log keys; default model id drifts —
   keep it configurable and current. All generative output must stay clearly labeled exploratory.
4. **Licensing** — confirm what Greek/Linear B data may be hosted in the pyaegean repo (First1KGreek
   CC-BY ✓; Perseus CC-BY-SA; LSJ status; PROIEL); DAMOS/LiBER permission for caching (gates v0.4).
5. **Linear A 500 MB from workbench repo** — pin a release tag so the download URL is stable; ensure the
   workbench repo keeps the assets available.
6. **Metrology/accounting + decipherment + AI readings are all exploratory** — keep them under explicit
   "exploratory/unverified" labels with provenance; never present as ground truth.

## Verification (v0.1 end-to-end)

- `pip install -e ".[all]"`; `python -c "import aegean; c=aegean.Corpus.load('lineara'); print(len(c))"` → **1721**.
- `aegean.data.fetch("lineara-images")` downloads from the workbench repo to the cache (sha-verified); a
  second call is a no-op; offline-without-fetch raises a clear `DataNotAvailableError`.
- Linear A: `c.to_dataframe(level="word")` non-empty; `c.filter(site="HT")`/`c.query(...)` reduce;
  ported analysis spot-checks (distance, KU-RO accounting balance, `KU-*-RO` patterns); `pytest`
  `test_parity_lineara.py` matches golden fixtures.
- Greek start: load a First1KGreek/Perseus sample → `aegean.greek.tokenize/normalize/syllabify/accentuate`
  produce correct output on known lines; betacode↔unicode round-trips; baseline lemmatize runs.
- Infra: `mypy --strict` clean; `python -m build` wheel **< ~3 MB** (size guard); `twine check`; `mkdocs build`.
- (v0.2 preview) AI adapters unit-test against mocked HTTP; grounding + exploratory-labeling asserted; no key ever logged.
