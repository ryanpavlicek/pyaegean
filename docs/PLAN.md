# pyaegean — a specialist Python package for Ancient Greek (alphabetic + Aegean syllabic)

## Context

The Linear A Workbench (TS) is web-only; researchers publish in Python (Jupyter/pandas). Research
confirmed: **no Python package exists** for any Aegean syllabic script (Linear A/B, Cypro-Minoan,
Cypriot), and the canonical corpora (DAMOS, LiBER, lineara.xyz, SigLA) are **web-only with no API**.
**CLTK** is the incumbent for Ancient Greek NLP — but it is a *generalist* across many ancient
languages.

**Strategic goal:** pyaegean is a **Greek specialist** — a deep, focused package
for **Ancient Greek specifically**, spanning **alphabetic Greek (Archaic→Koine) AND the Aegean
syllabic scripts (Linear A/B, Cypriot)** — aiming for thorough, high-quality Greek coverage,
plus specialty tooling for the Aegean scripts: Linear A/B analysis, translation, and a pluggable
multi-provider AI layer. CLTK is an excellent general-purpose library across many ancient languages;
pyaegean is deliberately narrower and deeper for Greek. Standalone repo; does not modify the workbench.

## Locked decisions

- **Name** PyPI `pyaegean`, `import aegean` (note branding tension below).
- **Repo** standalone; Apache-2.0; provenance/attribution first-class.
- **Positioning** a Greek specialist; deep, high-quality Greek coverage (do **not** depend on CLTK).
  A CLTK benchmark harness lets a user score pyaegean or a CLTK pipeline on the same gold set, and
  pyaegean may reuse the same **open data** (not CLTK's code).
- **Coverage** alphabetic Ancient Greek (full NLP) + Aegean syllabic scripts; Greek is first-class.
- **Center of gravity** corpus **data layer**, with Greek NLP + AI + translation as headline capabilities.
- **AI** multi-provider (Anthropic *default/latest Claude*, OpenAI, xAI Grok, Google Gemini); all four
  jobs: translation/glossing, decipherment hypotheses, Greek-NLP assist/disambiguation, corpus
  Q&A/summarization. Keys via env/config; grounded; all generative output labeled exploratory.
- **Greek NLP data** HYBRID: open-data foundation (Perseus/PROIEL treebanks, Morpheus, LSJ,
  First1KGreek) plus our own and AI-improved components.
- **Data** bundle only tiny JSON in the wheel; **download the 500 MB Linear A corpus from the
  linearaworkbench repo** (no re-host) into a user cache; host freely-licensable Linear B / Greek data
  as pyaegean release assets; wrap DAMOS/LiBER/Perseus from upstream. No Git LFS; CI footprint guard.
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
                           · patterns · query · accounting · structure  (generic stats, pure Python)
L2  scripts (plugins)      lineara (v0.1) · greek (v0.1 start) · linearb / cypriot / cyprominoan (later)
L1  core                   Corpus · Document · Token · Sign · SignInventory · Numeral · Script(ABC) · Registry
                           · Provenance · lazy DataFrame interop   (zero heavy deps)
```
A `Script` is a plugin (ABC) the core knows only by interface. Greek and Linear A are both just
registered scripts; `greek`/`translate`/`ai` are capability layers above. CLTK is **not** a dependency
at any layer; the benchmark harness merely scores against a CLTK pipeline on a shared gold set.

## Core data model (`aegean.core`) — unchanged essence, generalized for Greek

Frozen `@dataclass(slots=True)` value objects; numpy/pandas lazy.
- **`Script` ABC** + `ScriptRegistry`: `id`, `unicode_ranges`, `tokenize`, `transliterate`/`to_glyphs`,
  `sign_inventory`, optional capabilities (`phonetic_map`, `numeral_system`, `nlp`). Greek's `nlp`
  capability returns the `aegean.greek` pipeline; Linear A's returns `None`.
- **`Sign`** (syllabogram | letter | logogram), **`Token`** (`kind`: WORD/LOGOGRAM/NUMERAL/SEPARATOR/…
  plus Greek adds PUNCT), **`Document`** (+ `DocumentMeta`), **`Corpus`** (the hub — shipped:
  `load()`, `.get()`, `.filter()`, `.word_frequencies()`, **`.to_dataframe(level=…)`**, `.to_dict()`,
  `.provenance`; *planned*: `from_json`/`from_epidoc`, `.query()`, `.to_json`/`parquet`/`epidoc`),
  **`NumeralSystem`**/`AegeanNumerals`.
- Greek `Document`s carry token-level NLP annotations (lemma/POS/morph/IPA) when the pipeline has run,
  surfaced in `.to_dataframe(level="token")`.

## Greek NLP track (`aegean.greek`) — the Greek-specialist core

Pipeline of composable, individually-callable stages (each a function + a class for reuse):
`normalize` (NFC/NFD, betacode↔unicode, diacritic handling) → `tokenize` (word/sentence) →
`syllabify` → `accentuate`/accent analysis → `phonology` (IPA, by period) → `lemmatize` →
`morphology` (full parse: case/number/gender/tense/voice/mood/person) → `pos` → `parse`
(dependency, trained on AGDT) → `prosody`/`meter` (hexameter/iambic scansion) →
`lexicon` (LSJ lookup). Hybrid sourcing: ship/download open data (Morpheus tables, treebanks, LSJ),
implement our own engine, and let `aegean.ai.nlp_assist` disambiguate/fill gaps. The **benchmark
harness** (`tests/benchmark_greek/`) scores each stage against gold treebanks, and can also score a
CLTK pipeline on the same gold set for a side-by-side reference point.

## AI layer (`aegean.ai`) — multi-provider

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
  io/        json_io epidoc tabular .py        (planned; currently an empty stub)
  data/      registry.py _cache.py  bundled/lineara/*.json  **bundled/greek/*.json (small seeds)**
  adapters/  base.py  (damos liber lineara_xyz sigla perseus first1kgreek .py — phased; stub)
  integrations/ geo.py (planned; stub)  # no cltk dependency — pyaegean implements its own Greek NLP
tests/ fixtures/golden/  benchmark_greek/  test_parity_lineara.py  test_benchmark_greek.py
```

## Data hosting (download-first; structurally avoids the 500 MB problem)

- **Bundled in wheel** (offline-capable basics): compact Linear A text JSON (~hundreds KB),
  small Greek seeds (sample texts, betacode tables) — code + JSON only. The footprint guard
  (`scripts/check_footprint.py`) fails if a heavy binary is bundled or `import aegean` loads heavy deps.
- **`aegean.data.fetch(name)`** → `platformdirs` user cache, sha256-verified, idempotent, graceful
  `DataNotAvailableError` (names the exact call + license). Registry `DataSpec(name, kind, url, sha256, license)`.
  - The Linear A **text** JSON is bundled in the wheel; only `fetch("lineara-images")` is a remote
    download — from the `ryanpavlicek/linearaworkbench` repo (pinned release tag) — never re-hosted.
  - **pyaegean repo release assets** host freely-licensable **Linear B** data and **Greek** resources
    (First1KGreek CC-BY, treebanks, LSJ where permitted) — this is what the freed repo space is for.
  - DAMOS/LiBER/Perseus → adapters fetch from **upstream**, cache, no re-host (licensing permitting).
- No Git LFS; no binaries committed; clean clone is a few MB.

## Dependencies

- **Python ≥ 3.10**, mypy/pyright strict, `py.typed`.
- **Core**: zero hard third-party dependencies — pure Python; `import aegean` is instant. Greek NLP
  engines are pure Python; treebank/lexicon data is downloaded to cache on activation.
- **Extras**: `[data]`(pandas, DataFrame interop) · `[neural]`(onnxruntime/tokenizers/numpy, the GreTa
  seq2seq lemmatizer) · `[anthropic]`,`[openai]`,`[grok]`,`[gemini]`,`[ai]`(all) · `[epidoc]`(lxml/PyEpiDoc) ·
  `[geo]`(geopandas) · `[align]`(biopython, optional) · `[all]`. All AI/adapter/neural imports guarded.

## Parity, benchmarking & correctness

1. **Linear A parity** — shared language-neutral **golden fixtures** extracted from the TS tests
   (`algorithms/numerals/compareAlign/signPattern/queryEngine.test.ts`); both repos assert the same
   JSON; `test_parity_lineara.py` runs ported analysis over the real corpus (CI-blocking). Pure-Python
   implementations of the erf/lgamma functions are validated against the golden fixtures.
2. **Greek benchmark** — `test_benchmark_greek.py` scores lemmatizer/POS/morph/parse against gold
   treebanks; the harness can also score a CLTK pipeline on the same gold set as a reference point.
3. **AI** — provider adapters tested with mocked HTTP (no live keys in CI); grounding/labeling/caching
   unit-tested; a tiny optional live smoke gated behind a secret.
4. **Property tests** (`hypothesis`) mirror the TS `*.properties.test.ts` invariants.

## Packaging & infra

`hatchling`/PEP 621, `src/` layout, bundled data via `force-include`. `pytest`+`cov`+`hypothesis`;
coverage gate; matrix Py 3.10–3.13 × {no-extras, [all]}. GitHub Actions: `ruff`, `mypy --strict`, tests,
build, `twine check`, **footprint guard** (import-clean / import-fast / code+JSON wheel), OIDC publish on tag. Docs `mkdocs-material`+`mkdocstrings`;
port methodology + limitations into docstrings. Provenance: per-dataset `DataSpec.license`/`citation`,
`Corpus.provenance.cite()`, `CITATION.cff`, `NOTICE` (GORILA, DAMOS, LiBER, Perseus, First1KGreek).

## Roadmap (sequenced by value × feasibility)

Shipped through **0.4.0**: core + Linear A (with the workbench-corpus downloader) and the Greek start
(corpus loader, normalize/betacode, tokenize, syllabify, accentuation, baseline lemmatize); the
multi-provider **AI layer** (Anthropic default + OpenAI + Grok + Gemini) wired to all four jobs, with
translation/glossing, corpus Q&A, decipherment-hypothesis support, and NLP-assist disambiguation; and
a deepened Greek NLP stack with these opt-in, fetched-to-cache backends:

- `greek.use_treebank()` — Perseus AGDT lemma/POS/morphology lookup for attested forms.
- `greek.use_lsj()` — Perseus LSJ glossing (`gloss`/`lookup`).
- `greek.use_parser()` — arc-eager + averaged-perceptron dependency parser (pure Python),
  ~0.67 UAS / 0.57 LAS on projective AGDT.
- `greek.use_tagger()` — generalizing POS tagger (averaged perceptron, pure Python), ~84% on unseen
  forms, evaluated on a leakage-free held-out AGDT split via `greek.evaluate_tagger()`
  (`aegean.greek.heldout`).
- `greek.use_lemmatizer()` — generalizing lemmatizer (edit-trees + averaged-perceptron reranker,
  POS-conditioned), pure Python, ~40% on unseen forms, evaluated via `greek.evaluate_lemmatizer()`.
- `greek.use_neural_lemmatizer()` (the `[neural]` extra) — a GreTa (Ancient-Greek T5) seq2seq exported
  to int8 ONNX that generates the lemma, reaching 76.3% on unseen forms; a bundled gold lookup answers
  seen forms and the seq2seq handles unseen. Torch-free (numpy + onnxruntime, loaded only on
  activation); the ~232 MB model is fetched to cache, never bundled (CC BY-SA 4.0, fine-tuned from
  GreTa on the AGDT / Pedalion / Gorman treebanks).

The `lemmatize()` cascade resolves a form via treebank lookup (seen) → neural seq2seq (unseen) →
edit-tree → seed table. The benchmark harness can score these stages, or a CLTK pipeline, on a shared
gold set.

Linear B and the Cypriot syllabary shipped in **0.4.0** — the two deciphered Aegean syllabaries that
write Greek — each with a Unicode-built sign inventory, transliteration, and a Greek-reading bridge;
Linear B adds per-script accounting (`to-so`/`to-sa`) and a bring-your-own EpiDoc corpus reader.
**Cypro-Minoan** (undeciphered; a 99-sign Unicode inventory and sign-sequence tokenization, no
phonetics or bridge — modelled on Linear A) has since landed on `main`, completing the Aegean
syllabic set; it releases in the next version.

Planned:

- **Out-of-AGDT gold set**: a hand-checked, neutral evaluation set so the Greek-NLP numbers don't
  lean on the AGDT (which is in-training for the systems compared against).
- **Context-aware lemmatizer**: a sentence-context v2 of the `[neural]` backend, to push past the
  76.3% isolated-form ceiling on unseen lemma (larger, uncertain payoff).
- **Data layer / IO**: the compound `query` engine, JSON round-trip (`to_json`/`from_json`), and
  CSV/Parquet/EpiDoc write adapters — toward the v1.0 full EpiDoc round-trip.
- **Koine / Biblical Greek** (low priority): NT corpus loader + Koine-tuned lemmatization/morphology
  from an openly-licensed tagged Greek NT (MorphGNT/SBLGNT or the Nestle1904 trees), building on the
  existing Koine phonology mode (`to_ipa(…, "koine")`) and the John 1:1 sample.
- **Workbench bridge**: fetch the linearaworkbench static build (release asset, fetch-to-cache like
  `lineara-images`) and serve it locally — e.g. an `aegean workbench` command — so the Python toolkit
  and the visual workbench share corpus data.
- **Side project** Claude Code plugin exposing pyaegean (translate/gloss/decipher/ask) as slash-commands/MCP.
- **1.0** Stable: alphabetic + all syllabic scripts uniform through one API; deep, well-measured Greek
  NLP; AI + translation integrated; full EpiDoc round-trip.

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
2. **Greek NLP is a large, long arc** — full morphology + parsing + meter is a multi-year effort, and
   the early releases cover only part of it. The benchmark harness keeps progress honest and measurable;
   set expectations accordingly.
3. **AI**: provider SDK choices (Grok via OpenAI-compatible client; Gemini via `google-genai`); cost/rate
   limits; **prompt-injection** from untrusted corpus text; never log keys; default model id drifts —
   keep it configurable and current. All generative output must stay clearly labeled exploratory.
4. **Licensing** — confirm what Greek/Linear B data may be hosted in the pyaegean repo (First1KGreek
   CC-BY ✓; Perseus CC-BY-SA; LSJ status; PROIEL); DAMOS/LiBER permission for caching (gates Linear B).
5. **Linear A 500 MB from workbench repo** — pin a release tag so the download URL is stable; ensure the
   workbench repo keeps the assets available.
6. **Metrology/accounting + decipherment + AI readings are all exploratory** — keep them under explicit
   "exploratory/unverified" labels with provenance; never present as ground truth.

## Verification (end-to-end)

- `pip install -e ".[all]"`; `python -c "import aegean; c=aegean.Corpus.load('lineara'); print(len(c))"` → **1721**.
- `aegean.data.fetch("lineara-images")` downloads from the workbench repo to the cache (sha-verified); a
  second call is a no-op; offline-without-fetch raises a clear `DataNotAvailableError`.
- Linear A: `c.to_dataframe(level="word")` non-empty; `c.filter(site="HT")`/`c.query(...)` reduce;
  ported analysis spot-checks (distance, KU-RO accounting balance, `KU-*-RO` patterns); `pytest`
  `test_parity_lineara.py` matches golden fixtures.
- Greek start: load a First1KGreek/Perseus sample → `aegean.greek.tokenize/normalize/syllabify/accentuate`
  produce correct output on known lines; betacode↔unicode round-trips; baseline lemmatize runs.
- Infra: `mypy --strict` clean; `python -m build`; footprint guard (`check_footprint.py`: import-clean, import-fast, code+JSON-only wheel); `twine check`; `mkdocs build`.
- AI: adapters unit-test against mocked HTTP; grounding + exploratory-labeling asserted; no key ever logged.
