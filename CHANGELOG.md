# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## 0.4.0 — Unreleased

Adds **Linear B** — the deciphered Aegean syllabary for Mycenaean Greek — through the same
script-plugin model as Linear A. All Linear A analysis remains exploratory.

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

### Changed
- Linear B sign data is bundled from the Unicode Character Database (Unicode-3.0 license;
  attribution added to NOTICE).

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
