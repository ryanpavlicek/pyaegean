# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

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
