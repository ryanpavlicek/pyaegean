# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## 0.8.0 — 2026-06-10

A hardening pass for scholarly use: a complete Linear A sign repertoire, an editorial-status model
with a schema-valid EpiDoc round-trip, Pleiades-aligned find-sites, geographic analysis, a wider
public API, and a hosted API reference. Released as **beta** — the API is close to stable, but a 1.0
waits on external use and a short methods write-up.

### Added
- **Full Linear A sign repertoire.** The bundled inventory now covers the entire Unicode Linear A
  block (344 signs) instead of only the 84 transliteration-aligned signs; those 84 keep their
  conventional sound values and confidence, the rest are carried from the Unicode Character Database
  (`attrs["source"] == "ucd"`) with no assigned reading. Closes a gap where most *attested* glyphs
  had no inventory entry.
- **Editorial status on tokens** (`ReadingStatus`: `CERTAIN` / `UNCLEAR` / `RESTORED` / `LOST`). The
  EpiDoc reader populates it from `<unclear>` / `<supplied>` / `<gap>` markup and the writer emits it
  back, so editorial certainty round-trips (it survives the JSON round-trip too). The bundled Linear A
  corpus is a normalized transcription with no full Leiden apparatus, so its tokens are `CERTAIN`;
  the field is for bring-your-own EpiDoc corpora and future data.
- **Geographic analysis** (`aegean.geo`, the `[geo]` extra): a bundled Aegean find-site gazetteer
  plus `to_geodataframe(corpus, level="inscription"|"site")` and `word_distribution(corpus, word)` —
  turning a corpus into a geopandas GeoDataFrame (EPSG:4326) for spatial analysis and mapping.
- **Pleiades alignment** for the gazetteer: 26 of the 56 find-sites carry a Pleiades place id
  (`SiteCoord.pleiades` / `pleiades_uri`), surfaced as a `pleiades` column in the GeoDataFrames, for
  linked-open-data work; minor findspots not in Pleiades are left null.
- **Wider public API surface** (toward a stable API): the core value types (`Document`, `Token`,
  `Sign`, `SignInventory`, `DocumentMeta`, `Provenance`, `Script`, `ReadingStatus`) are re-exported
  from the top-level `aegean` namespace; `aegean.analysis` now exports `BalanceCheck`,
  `CompiledSignPattern`, and the `Output`/`Connector` query types; and `aegean.greek` exports the
  backend errors (`ParserNotLoadedError`, `LexiconNotLoadedError`, …) raised by its opt-in functions.
- **Hosted API reference** ([ryanpavlicek.github.io/pyaegean](https://ryanpavlicek.github.io/pyaegean/)):
  a browsable reference for every public module, class, and function, generated from the docstrings and
  type hints with pdoc and published to GitHub Pages (the new `[docs]` extra).
- **The neural Greek pipeline** (`greek.use_neural_pipeline`, the `[neural]` extra): one
  jointly-trained model (GreBerta encoder + tagging heads + biaffine parser + edit-script
  lemmatizer) serving UPOS, full morphology (UD FEATS), **UD dependency trees** (single-root MST
  decoding — non-projectivity handled natively), and lemmas. Trained leakage-clean on AGDT +
  Gorman + Pedalion (1.41M tokens); measured **above every published UD Ancient Greek number**
  through the shipped artifact and package (UD Perseus test: UPOS 96.94, UFeats 96.12,
  lemma 94.40, UAS 89.16, LAS 84.38; confirmed end-to-end from raw text at tokens F1 99.97 —
  protocol and tables in `docs/benchmarks.md`).
  Once active, `pos_tags`/`pos_tag`, `parse` (then returning UD relations), and `lemmatize` all
  use it; `analyze_sentence` exposes the full joint analysis. Torch-free inference
  (onnxruntime + tokenizers + numpy); the model bundle (CC BY-SA 4.0) is fetched to cache,
  never bundled.
- **Standard-benchmark evaluation** (`greek.evaluate_on_ud`): scores the active pipeline on the
  Universal Dependencies Ancient Greek test folds (Perseus/PROIEL; CC BY-NC-SA, fetched to cache for
  evaluation only) with the official, sha256-pinned CoNLL 2018 evaluator — the protocol behind the
  field's published numbers. `greek.agdt_ud_overlap` builds the AGDT↔UD-Perseus leakage-exclusion
  manifest (2,443 sentences, 100% form-verified) that model training must honour. Protocol, leakage
  controls, and measured baselines: `docs/benchmarks.md`.
- **One-call analysis** (`greek.pipeline`): tokenize → sentence split → POS-tag → lemmatize
  (→ parse) over a text in a single call, returning per-token `TokenRecord`s (punctuation kept).
  Uses whatever backends are active; with the neural pipeline active, one model pass fills every
  field (UPOS, XPOS, FEATS, lemma, UD head/relation).
- **Lenient normalization** (`greek.normalize(..., lenient=True)`): repairs — and warns about, via
  `NormalizationWarning` — the artifacts of OCR'd or half-converted text: Latin letters embedded in
  Greek words, Beta-Code diacritic remnants attached to Greek letters, and stray combining marks.
  Conservative by design (only repairs where the visual lookalike and Beta Code agree, and only
  where a mark is phonologically possible); strict mode is unchanged.
- **Syllabification exception lexicon**: lexicalised compounds divide at the point of union
  (Smyth §140) — `syllabify("εἰσφέρω")` now gives `εἰσ-φέ-ρω` where phonotactics alone said
  `εἰ-σφέ-ρω`. A curated, test-enforced lexicon consulted before the rule engine (every entry must
  provably differ from the rules); one-line contributions welcome (`CONTRIBUTING.md`).
- **Citation automation**: `Provenance.bibtex()` / `.apa()`; `Corpus.cite(style)` cites the corpus
  — and, after `filter()`, the **exact subset** (a recorded `subset:` note with the filter and
  counts); `Corpus.query()` results carry provenance + the query summary, so
  `QueryResults.cite(style)` cites the exact result set used in a paper.
- **Corpus statistics** (`aegean.analysis.stats`, pure stdlib): **dispersion** — Gries' deviation
  of proportions (DP, with the Lijffijt & Gries normalization) for how evenly an item spreads over
  documents; **keyness** — Dunning's log-likelihood G² (Rayson & Garside form) plus Hardie's
  log-ratio effect size for what distinguishes a (sub)corpus from a reference; and **bootstrap
  confidence intervals** for any corpus statistic (percentile, documents as the resampling unit,
  reproducible by default). Works over any corpus or `filter()` subset; on DAMOS,
  `keyness(pylos, rest)` surfaces the Pylos land-tenure vocabulary (pe-mo, o-na-to, ko-to-na…)
  immediately. New CLI commands: `aegean dispersion` and `aegean keyness` (subset-vs-rest via
  `--site/--period/...`, or corpus-vs-corpus via `--reference`).
- **The DAMOS Linear B corpus, loadable** (`aegean.load("damos")`): the most complete edition of
  the Mycenaean (Linear B) corpus — F. Aurora's Database of Mycenaean at Oslo, CC BY-NC-SA 4.0 —
  decoded from the DAMOS public web API into a hosted `damos-corpus` release asset (~5,900 tablets
  from Knossos, Pylos, Thebes, Mycenae, Tiryns and more, with transliterations, site, series, and
  chronology). One `Document` per tablet, the transliteration tokenised into words / numerals /
  logograms with the DAMOS comma-slash word dividers; the verbatim transliteration is kept in
  `Document.transcription`. This is the openly-licensed full corpus the bundled Linear B sample
  stood in for. The NonCommercial + ShareAlike obligations pass through to the user; the data is
  fetched to the cache, never bundled (`scripts/build_damos_corpus.py` documents the build). Cite
  DAMOS (Aurora 2015) in academic work.
- **Prebuilt artifacts for a fast first use.** The opt-in Greek backends now prefer small
  project-hosted prebuilt assets over slow local builds (with build-from-source as the
  automatic fallback): `greek.use_lsj()` fetches a ~15 MB prebuilt LSJ index (`lsj-index-v1`)
  instead of downloading ~270 MB of Perseus TEI and building it, and `greek.use_treebank()` /
  `use_tagger()` / `use_lemmatizer()` / `use_parser()` share one ~15 MB AGDT-derived bundle
  (`agdt-derived-v1`) instead of a 75 MB download and minutes of training. Both assets carry
  the source licenses (CC BY-SA 4.0 / 3.0), are sha256-pinned, and are never bundled; a new
  `data.fetch_prebuilt()` helper drives the prefer-then-fall-back logic.
- **The SigLA corpus, loadable** (`aegean.load("sigla")`): the Linear A paleographical
  database (Salgarella & Castellan, CC BY-NC-SA 4.0 — fetched on demand, never bundled)
  decoded from its published web-app payload into the JSON its paper describes, hosted as the
  sha256-pinned `sigla-corpus-v1` release asset (~1 MB). 781 documents with metadata the
  bundled corpus never had — typology, find-site, **physical dimensions**, period, EFA plate
  refs — and 5,065 sign attestations in tablet order (sign-level granularity; word boundaries
  are not in this dataset version). Built by `scripts/build_sigla_corpus.py` over a new
  pure-Python **OCaml Marshal reader** (three structural self-checks; offline-tested), and
  cross-validated against the bundled GORILA corpus: 547/651 shared documents at ≥60% sign
  overlap under 28 data-derived notation equivalences (`*120↔GRA`, `*302↔OLE`, …) — the
  residue is rare-ligature notation, not data error.
- **Linear B sample and lexicon expansion (source-verified)** — the bundled illustrative sample
  grows 2 → 18 tablets (PY Ta 641 and PY Er 312 hand-curated, plus sixteen one-line excerpts from
  Pylos/Knossos/Mycenae tablets taken from *sourced quotations* in Wiktionary's Mycenaean Greek
  entries, each citing its tablet and carrying a translation), and the Greek-bridge lexicon grows
  45 → 150 entries (the curated core layered with every Wiktionary entry that states its Ancient
  Greek equation — `e-ra-wo → ἔλαιον`, `ku-ru-so → χρυσός`, …; extraction scripts in `scripts/`,
  attribution in `NOTICE`). `[X]`-restored readings now load as `ReadingStatus.RESTORED`. The
  Cypriot lexicon grows 13 → 17 with verified Idalion Bronze equations (κασίγνητος, ἄνευ, …).
- **Linear A editorial status recovered from the data** — the WP4 upstream audit found the
  apparatus signal was never lost, only unread: the upstream marks erased/illegible signs with
  a placeholder codepoint (U+1076B; its own tooling names it "erased"), and pyaegean's bundle
  carries it byte-identically. The loader now interprets it: standalone erased-sign runs load
  as `ReadingStatus.LOST` (552 tokens), damaged-at-break words and `[?]`-bracketed uncertain
  readings as `UNCLEAR` (120 tokens), and tablet ruling dashes as separators — 366 of the
  1,721 documents now carry editorial status (regression-pinned). Restorations and dotted
  readings were dropped upstream and remain absent; SigLA integration is the planned path.
- **Real Greek works on demand** (`greek.load_work("tlg0012.tlg001")`, CLI `aegean greek work`):
  a fetch-to-cache TEI reader for **Perseus canonical-greekLit** and **First1KGreek** (CC BY-SA).
  One call loads a work into the standard corpus model — the Iliad arrives as 24 book-Documents
  (~127k tokens) with real verse lines; prose works split by chapter/paragraph. Downloads are
  pinned to an upstream commit (recorded as `Provenance.data_version`) for reproducibility, and
  editorial `<note>`/`<bibl>` subtrees are excluded from the text. The bundled 5-passage sample
  remains the offline default; this closes the "five famous quotes" gap for alphabetic Greek.
- **Data versioning for reproducibility** (`aegean.data.versions()`, `aegean data versions`):
  a manifest of every bundled data file (sha256 + size, hashed from the installed wheel) and
  every fetchable asset (pinned sha256, cache state). Bundled corpora stamp
  `Provenance.data_version`; the "pinning for papers" recipe is in the Data & Provenance wiki.
- **`Corpus.from_records()`** — build a corpus from plain dicts, so a scholar's own
  inscriptions get the full API (filter, query, DataFrames, citation, export, EpiDoc).
  Records carry `lines`/`words`/`text` plus metadata; tokens may be dicts with `kind`,
  `status`, and `alt`. Pair with `register_loader` to make it loadable by name.
- **Variant readings** (`Token.alt`): alternate readings alongside editorial `status`,
  surviving both round-trips — JSON (omitted when empty, so existing files stay valid) and
  EpiDoc, where they become a critical apparatus (`<app><lem>…</lem><rdg>…</rdg></app>`,
  validated against the official EpiDoc RelaxNG schema) and parse back to one token.
- **The `aegean` command line** (the `[cli]` extra: typer + rich; console script `aegean`,
  also `python -m aegean.cli`): the whole toolkit without writing Python. Corpus commands
  (`info`, `load`, `show`, `search`, `query`, `stats`, `balance`, `cite`, `export`, `geo`,
  `sign`, `bridge`), the full Greek pipeline (`aegean greek normalize|betacode|strip|tokenize|
  syllabify|accent|quantities|scan|ipa|tag|lemmatize|morph|parse|gloss|pipeline|eval`, with
  `--neural`/`--treebank`/… flags standing in for the `use_*()` activations), analysis
  (`distance`, `align`, `assoc`, `cooccur`, `clusters`, `structure`), the data layer
  (`data list|fetch|cache`), and the exploratory-labeled AI layer (`ai translate|gloss|
  hypotheses|ask|providers`). Conventions: `--json` on every command, `-` reads stdin,
  clean exit codes (`balance --strict` exits 1 on a discrepancy). The CLI is imported only
  by the console script, so `import aegean` stays dependency-free.

### Changed
- **EpiDoc export is now schema-valid.** Output is wrapped in the required `<div type="edition">`
  (with a `publicationStmt`) and is validated in CI against the official EpiDoc RelaxNG schema
  (fetched to cache; skipped offline). The reader/writer also carry editorial status (see above).
- **`greek.evaluate` is renamed `greek.evaluate_parser`**, for consistency with `evaluate_tagger` /
  `evaluate_lemmatizer` (the one breaking rename, made ahead of an API freeze).
- Documentation states scope honestly: the inventory's read-vs-unread split, that accounting
  reconciliation applies to the ~40 Linear A tablets carrying a stated total, that the non-Linear-A
  bundled corpora are illustrative samples (bring-your-own for a full Linear B corpus), and where the
  Greek NLP stack sits (the zero-dependency core favours portability and transparent evaluation;
  the opt-in neural pipeline carries the accuracy claims).
- `CONTRIBUTING.md` now opens with a menu of small, well-scoped contributions (syllabification
  exceptions, sign facts, gazetteer alignments, collocation measures, …) and documents the
  **deprecation policy**: deprecate in a minor, remove no sooner than the next minor, warnings
  always name the replacement.

### Fixed
- The AI `summarize` capability now labels its result `kind="summarize"` (previously mislabeled `"ask"`).
- **Infinite recursion with `use_tagger()` + `use_lemmatizer()` both active**: lemmatizing a form
  outside the treebank lookup recursed to death (edit-tree lemmatizer → POS features → rule
  morphology → lemmatizer …). The rule-based morphology engine now reads only the bundled seed
  table for its lemma hints — which also keeps its analysis cache valid and the tagger's features
  identical between training and inference, whatever backends are active.

## 0.7.0 — 2026-06-10

Fills the `aegean.io` package with export adapters, completing the EpiDoc read+write round-trip.

### Added
- **EpiDoc (TEI) export** (`aegean.io.to_epidoc`, `aegean.io.write_epidoc`): serialize a `Document`
  or `Corpus` to EpiDoc TEI XML — the inverse of the bring-your-own reader, so a corpus written out
  reloads through `parse_epidoc` with the same ids, find-places, tokens, and lines. Uses the stdlib
  XML writer, so export needs no extra dependency.
- **CSV / Parquet export** (`aegean.io.to_csv`, `aegean.io.to_parquet`): write a corpus's
  document/token/word DataFrame to CSV or Parquet. CSV needs the `[data]` extra (pandas); Parquet
  also needs the new `[parquet]` extra (pyarrow).
- `aegean.io` is exposed as a top-level subpackage.

## 0.6.0 — 2026-06-10

Rounds out the corpus data layer: a lossless JSON round-trip and a first-class compound query.

### Added
- **Lossless JSON round-trip** on `Corpus`: `to_json(path=None)` serializes the entire corpus —
  every token (kind, signs, glyphs, line/position), the physical lines, full document metadata,
  the sign inventory, and provenance — and `from_json` / `from_dict` reconstruct it exactly. The
  existing `to_dict` stays as the compact, lossy summary.
- **`Corpus.query(filters, output=...)`**: the compound-query predicate engine (field registry,
  AND/OR/NOT, inscription/word output) is now a first-class corpus method, complementing the
  exact-match `filter(**meta)`. Returns `QueryResults` (`.inscriptions` / `.words`).

## 0.5.0 — 2026-06-10

Completes the Aegean syllabic set with **Cypro-Minoan**, and adds a neutral **out-of-AGDT
evaluation** of the Greek NLP stack against the PROIEL treebank.

### Added
- **Neutral out-of-AGDT evaluation** (`aegean.greek.evaluate_on_proiel`): scores the Greek
  lemmatizer/tagger against the PROIEL treebank (Greek NT + Herodotus) — a source none of
  pyaegean's models trained on — for an honest cross-source generalization number. PROIEL is
  fetched to the cache for evaluation only (CC BY-NC-SA 3.0, never bundled); gold lemmas are
  homograph-normalized and POS compared under a reconciled tagset (PROPN→NOUN, SCONJ→CCONJ).
- **Cypro-Minoan** (`aegean.scripts.cyprominoan`): the undeciphered Bronze Age script of Cyprus,
  completing the Aegean syllabic set. A 99-sign inventory built from the Unicode Character Database
  (the "Cypro-Minoan" block), with conventional sign numbers (`CM001` …) and no phonetic values —
  the script is undeciphered, so the plugin offers the sign inventory and sign-sequence tokenization
  only, plus `Corpus.load("cyprominoan")` over a small illustrative sample. No transliteration,
  lexicon, or Greek bridge, by design.

## 0.4.0 — 2026-06-10

Adds **Linear B** and the **Cypriot syllabary** — the two deciphered Aegean syllabaries that
write Greek — through the same script-plugin model as Linear A. All Linear A analysis remains
exploratory.

### Added
- **Linear B script** (`aegean.scripts.linearb`): registered as a `Script` alongside Linear A.
  A 211-sign inventory and phonetic map built from the Unicode Character Database (74 syllabograms,
  14 undeciphered symbols, 123 ideograms/monograms), `word_to_phonetic` transliteration with the
  labiovelar and affricate values, and `Corpus.load("linearb")`.
- **Linear B → Greek bridge** (`greek_reading`, `gloss`): a curated Mycenaean→Greek lexicon maps a
  transliterated word to its Classical Greek lemma and gloss (`PO-ME → ποιμήν`, "shepherd"), to
  compose with the LSJ backend for the full dictionary entry.
- **Linear B accounting**: the numeral/accounting engine recognises Linear B's `to-so`/`to-sa`
  totals (markers are now per-script; Linear A's `KU-RO` is unchanged), so `balance_check`
  reconciles Mycenaean tablets.
- **Bring-your-own Linear B corpus**: a DAMOS-style EpiDoc reader (`parse_epidoc`,
  `load_epidoc_corpus`, the `[epidoc]` extra) parses a user-supplied corpus locally via
  `PYAEGEAN_LINEARB_CORPUS`. No corpus is bundled or fetched by default — none is openly licensed
  (DAMOS is CC BY-NC-SA) — only a small illustrative sample of canonical tablets.

- **Cypriot syllabary** (`aegean.scripts.cypriot`): the deciphered Aegean syllabary for the
  Arcado-Cypriot dialect of Greek. A 55-sign inventory and phonetic map from the Unicode
  Character Database, `word_to_phonetic` transliteration, a curated Cypriot→Greek bridge
  (`greek_reading`, `gloss`; `PA-SI-LE-U-SE → βασιλεύς`), and `Corpus.load("cypriot")` with a
  small illustrative sample.

### Changed
- Linear B and Cypriot sign data are bundled from the Unicode Character Database (Unicode-3.0
  license; attribution added to NOTICE).

## 0.3.0 — 2026-06-10

Adds opt-in Greek tagging and lemmatization that generalize to unseen forms — including a
neural lemmatizer backend for unseen-form lemma — and makes the core dependency-free. All
Linear A analysis remains exploratory.

### Added
- **Generalizing POS tagger** (opt-in): `greek.use_tagger()` trains an averaged-perceptron
  sequence tagger (pure Python, no heavy deps) on the AGDT that predicts part of speech for
  **unseen** forms from suffix/prefix/shape/accent + left-to-right context features — where
  the treebank lookup (attested forms only) and the suffix heuristic fail. `greek.pos_tags()`
  uses it in context when active; `greek.evaluate_tagger()` reports leakage-free held-out
  accuracy. Measured **84.4% POS overall / 83.6% on unseen forms** on a 90/10 AGDT split
  (vs ~0% for the lookup and ~50% for the heuristic on unseen). The ~2.2 MB model is built on
  first use, cached, never bundled.
- **Generalizing lemmatizer** (opt-in): `greek.use_lemmatizer()` trains a Chrupała-style
  **edit-tree** model with an averaged-perceptron reranker (pure Python) on the AGDT. It
  learns inflection→lemma transforms (incl. accent shifts) that generalize to unseen forms,
  conditioned on POS from the tagger. `greek.lemmatize` uses it (when active) for forms the
  treebank lookup doesn't cover; `greek.evaluate_lemmatizer()` reports leakage-free held-out
  accuracy. Measured **84.5% overall / 40.3% on unseen forms** on a 90/10 AGDT split (the
  lookup is 0% on unseen). For unseen forms the opt-in **neural backend** below goes further;
  this pure-Python model already lifts unseen lemma from the lookup's 0% with no heavy deps.
- **Neural lemmatizer backend** (opt-in `[neural]`): `greek.use_neural_lemmatizer()` activates a
  fine-tuned **GreTa** (Ancient-Greek T5) seq2seq, exported to ONNX, that *generates* the lemma
  of an unseen form — reaching **76.3% on unseen forms**. It ships as a hybrid (a bundled gold
  lookup answers seen forms exactly; the seq2seq handles the rest, ~92% overall). Inference is **torch-free** — a numpy greedy decode over int8 ONNX via onnxruntime,
  imported only on activation, so `import aegean` stays instant. The model (~232 MB, CC BY-SA) is
  fetched-to-cache, sha256-verified, never bundled; install with `pip install 'pyaegean[neural]'`.
- **Leakage-free held-out evaluation** (`aegean.greek.heldout`): splits the AGDT by
  sentence, flags dev forms unseen in training, and scores any tagger/lemmatizer (a pyaegean
  mode or a CLTK pipeline) on the disjoint unseen subset — the honest generalization measure
  behind the model numbers.

### Changed
- `pos_tag`/`pos_tags` consult the trained tagger (when active) for the open-class forms the
  closed-class lexicon and treebank lookup don't cover, generalizing tags to unseen text.
- `lemmatize`/`lemmatize_verbose` consult the neural backend, then the trained edit-tree
  lemmatizer (whichever is active), after the treebank lookup — generalizing lemmas to unseen forms.
- **Core now has zero hard third-party dependencies.** `pandas` moved to a new optional
  `[data]` extra (lazy-imported only by `to_dataframe`, which raises a clear install hint if
  it's missing); `scipy` was dropped entirely — the two collocation statistics (χ² p-value,
  Fisher's exact) are now pure stdlib (`math.erfc`/`math.lgamma`). `pip install pyaegean` no
  longer pulls pandas/numpy/scipy. *Breaking only if you called `to_dataframe()` without
  installing `pyaegean[data]`.*
- **Footprint policy replaces the wheel-size guard.** The `<3 MB` wheel check is gone (it was
  a no-op beside the old hard deps); `scripts/check_footprint.py` now enforces the invariants
  that matter — `import aegean` loads no heavy module, imports fast, and the wheel ships only
  code + JSON.

## 0.2.0 — 2026-06-08

Deepens the Greek NLP track with two opt-in, gold-data backends and a revamped
tutorial. All Linear A analysis remains exploratory.

### Added
- **LSJ glossing** (opt-in): `greek.use_lsj()` fetches the full Perseus
  Liddell-Scott-Jones lexicon (CC BY-SA 4.0, ~270 MB) into the cache and builds a
  derived gzipped index; `greek.gloss(word)` and `greek.lookup(word)` return a concise
  gloss or the full `LSJEntry`. Composes with the lemmatizer — an inflected form
  resolves via its lemma (e.g. `ἀνδρός` → `ἀνήρ`).
- **Dependency parser** (opt-in, baseline): `greek.use_parser()` trains an arc-eager +
  averaged-perceptron parser (pure Python, no heavy deps) on the AGDT; `greek.parse()`
  returns a `DepTree` with native AGDT/Prague labels, and `greek.evaluate()` reports
  held-out UAS/LAS (~0.67 / 0.57 on projective sentences, ~0.51 / 0.42 across all text).
  An honest baseline: arc-eager builds only projective trees, which is a documented limit.
- A revamped, end-to-end tutorial notebook (`notebooks/getting-started.ipynb`) that
  walks one line of Homer down the full pipeline, then turns the toolkit on Linear A.

### Changed
- Documentation refreshed across the README and wiki to present the complete Greek NLP
  track (treebank lemmas/POS, LSJ glossing, dependency parser, CLTK benchmark) for 0.2.0.

## 0.1.0 — 2026-06-08

First public release (alpha). A specialist Python toolkit for Ancient Greek and the
Aegean syllabic scripts; analysis of the undeciphered Linear A material is always
labeled exploratory, never presented as ground truth.

### Added
- **Core** (`aegean.core`): a script-agnostic model — `Corpus`, `Document`, `Token`,
  `Sign`, `SignInventory`, `Numeral`, a `Script` plugin registry, and `Provenance`
  that travels with every corpus and stamps exports.
- **Linear A** (`aegean.scripts.lineara`): bundled 1,721-inscription corpus, 84-sign
  inventory, sign→sound map, and transliteration.
- **Analysis** (`aegean.analysis`): accounting reconciliation (KU-RO / PO-TO-KU-RO),
  wildcard sign-pattern search, weighted phonetic distance + alignment, morphology
  clustering, collocation statistics, a compound query engine, and tablet-structure
  classification — all parity-tested against golden fixtures.
- **Greek NLP** (`aegean.greek`): Unicode/Beta Code normalization, tokenization,
  syllabification, accent and prosody analysis, dactylic-meter scansion (hexameter +
  elegiac pentameter), reconstructed IPA (Attic/Koine), POS tagging, a rule-based
  morphological analyzer, and a baseline lemmatizer. An **opt-in** treebank backend
  (`greek.use_treebank()`, Perseus AGDT v2.1) supplies attested, correctly-accented
  lemmas and gold POS for known forms. A benchmark harness scores the pipeline and
  measures the treebank lift.
- **AI layer** (`aegean.ai`, `aegean.translate`): a provider-agnostic LLM client
  (Anthropic, OpenAI, xAI Grok, Gemini — SDKs optional), response caching, corpus
  grounding with prompt-injection wrapping, and hybrid lexicon+LLM translation. Every
  generative result is a provenanced, exploratory-labeled `ExploratoryResult`.
- **Data** (`aegean.data`): bundled JSON corpora plus a `fetch()` download-to-cache
  layer (sha256-verified, atomic, idempotent) for large assets — e.g. the Linear A
  facsimile imagery and the AGDT treebank — which are never bundled or re-hosted.

### Notes
- Requires Python ≥ 3.10. The wheel stays under 3 MB (CI-guarded); `numpy`/`pandas`/
  `scipy` and provider SDKs are imported lazily.
- Licensing: code Apache-2.0; Linear A corpus JSON via GORILA/mwenge; Linear A imagery
  © École Française d'Athènes and others (fetched, not redistributed); the Perseus
  AGDT treebank is CC BY-SA 3.0 (fetched + built in the cache, not bundled). See
  `NOTICE`.
