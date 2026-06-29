# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## 0.14.2 (2026-06-29)

### Added
- **Contested find-spot flag in the gazetteer.** `aegean.geo.SiteCoord` gains an optional
  `contested` reason string (with an `is_contested` convenience property), and the geo
  GeoDataFrames carry a matching `contested` column. The bundled Margiana (Turkmenistan) entry is
  flagged: it is kept for corpus fidelity (and cross-project parity), but no Linear A inscription is
  accepted from Central Asia, so it is never silently mapped as a genuine find-spot.

## 0.14.1 (2026-06-29)

### Fixed
- **`analysis.wilson_interval`** clamps an out-of-range count: `k > n` made p̂ > 1 and drove the
  variance (and its square root) negative; it now returns a valid in-[0,1] interval, and `n <= 0`
  returns the no-information interval `(0, 1)`.
- **`analysis.fit_heaps`** rejects a constant-x growth curve relative to the data scale instead of an
  exact-zero comparison, which float roundoff defeated into a fabricated power-law fit.

Both are unreachable from the library's own callers (`pmi_interval` keeps `joint ≤ total`; a real
vocabulary-growth curve has increasing token counts), but they match the degenerate-input contract the
rest of the statistics layer already upholds. Surfaced by a cross-repo audit of the Linear A Research
Workbench, whose ported helpers shared the same gaps.

## 0.14.0 (2026-06-28)

### Added
- **Generalizing rule-based lemmatizer (always-offline default).** With no backend loaded,
  `greek.lemmatize` now strips the regular second-declension and thematic-verb endings to recover the
  citation form (`νόμου → νόμος`) instead of only consulting a seed table. On the full Nestle 1904 New
  Testament it lifts the offline baseline from 14.5% to 15.4% (about 1,300 regular forms recovered against
  28 mis-strips), with conservative guards (contracted nominatives like `Ἰησοῦς`, neuter `-ον` nouns,
  indeclinables) preventing the regressions a naive stripper introduces. The opt-in treebank and neural
  backends remain far more accurate for serious work.
- **Whole-token and substring search modes.** `db.search(..., mode="token")` (the default) matches a
  whole token literally, so `KU-RO` matches only the token `KU-RO`, never `PO-TO-KU-RO`; `mode="substring"`
  (CLI `aegean db search --substring`) opts into the within-token search.

### Changed
- **`db.search` matches whole tokens by default.** The FTS index previously split hyphenated
  transliterations, so `KU-RO` matched the subsequence inside any longer token (`search("DA-RO")` returned
  7 hits, none of them the token `DA-RO`). Search now matches an exact whole token; pass `mode="substring"`
  for the previous within-token behaviour. The call signature is unchanged.

### Fixed
- **Accentuation:** word-final `-οις` / `-αις` (dative plural) count long, so dative plurals accent on the
  penult (`ἀνθρώποις`), not the antepenult.
- **Sandhi:** elided proclitics (`ἀπ'`, `ἐπ'`, `καθ'`, …) now resolve; the accent-keyed entries were
  unreachable under the accent-blind lookup.
- **Scansion:** `scan_hexameter` scans Iliad 1.3 to its canonical pattern via a curated long-by-nature
  lexicon, instead of returning a wrong greedy reading.
- **Beta Code:** `unicode_to_betacode` / `betacode_to_unicode` round-trip text containing literal
  `( ) / \ = + |` through a backtick escape.
- **Lenient OCR normalize:** maps Latin `v` to upsilon (the common misreading) and only repairs
  Greek-dominated tokens, leaving a mostly-Latin token untouched.
- **Collocation:** `fishers_exact` returns 1.0 on an impossible 2×2 table instead of raising.
- **Translation grounding:** the rare-word gloss gate no longer glosses every word on all-common text;
  `clean_gloss` no longer leaks etymology fragments; and the concise-gloss cascade no longer falls back to
  LSJ's archaic first sense when no concise dictionary is loaded.
- **Idioms:** nested sub-idioms are suppressed on the lemma path too (the longest idiom wins).
- **Clause skeleton:** copular clauses keep the copula and the predicate nominal/adjective, instead of
  labelling a preposition-phrase-internal noun the predicate.
- **EpiDoc:** a LOST token round-trips as LOST, distinct from RESTORED, instead of becoming RESTORED.

### Documentation
- Every public function now ships a correctness test (CONTRIBUTING and the release gate require it).
- `query(output='words')` counts are documented as document frequency, distinct from
  `Corpus.word_frequencies()` token frequency.

## 0.13.0 (2026-06-28)

### Added
- **Idiom / multiword-expression grounding.** `ai.idiom_glosses(text)` detects non-compositional Greek
  idioms (ἐφ' ἡμῖν "in our power", οὐκ ἔστιν ὅπως "there is no way that", οἷός τε "be able to", …) from
  a curated bundled lexicon and grounds their real meaning, the error class that per-token morphology
  grounding cannot reach. Detection is surface plus contiguous-lemma matching (so inflected idioms are
  caught); idioms are added to the morphology and full translation grounding by default.
- **Post-hoc verify translation** (`translate(..., verify=True)`; `aegean ai translate --verify`):
  translates the passage first, then checks the draft against the gold morphology, glosses, and idioms
  and repairs definite contradictions (wrong voice, subject/object, case, a wrong rare-word or idiom
  sense, omission/addition). Because the analysis only checks the draft, it can catch errors without
  ever biasing the translation. Costs a second model call; recommended for hard or high-stakes passages.

## 0.12.0 (2026-06-28)

### Changed
- **Grounded translation now defaults to morphology-first grounding.** `aegean.translate.translate`
  and `grounding_for` take a `mode` parameter (`"morphology"`, `"lemma"`, `"full"`, `"none"`),
  defaulting to **`"morphology"`**: the model is grounded in deterministic lemma, part-of-speech, voice,
  case-role, and clause-structure analysis from the pipeline, with rare-word flags, and no
  automatically-selected dictionary glosses. Deterministic morphology reliably helps a model with the
  grammar (voice, subject/object, case), whereas an auto-selected sense gloss can surface the wrong
  sense and mislead it. The previous lemma-plus-gloss behaviour is preserved as `mode="lemma"`. CLI:
  `aegean ai translate --mode`.

### Added
- **Concise, common-sense-first glosses for `mode="full"`.** When glosses are wanted, `mode="full"`
  adds them from a cascade of concise dictionaries (Middle Liddell, Cunliffe, Abbott-Smith, Dodson),
  rarity-gated to the words that need them and cleaned, instead of the first sense of LSJ (a historical
  lexicon whose opening sense is often the archaic one, e.g. καιρός "a row of thrums in the loom" before
  "the right time"). New helpers `ai.concise_gloss` and `ai.clean_gloss`. Most useful for rare or
  technical vocabulary and for weaker models. A new Recipe (Get the best AI translation) and a notebook
  section walk through choosing the mode.

## 0.11.0 (2026-06-28)

### Added
- **Accent placement** (`greek.place_accent`, `recessive_accent`, `persistent_accent`; `aegean greek
  accentuate`): predicts a word's accent from the Greek accentuation laws (the law of limitation,
  recessive vs persistent accent, the properispomenon rule). Dichrona (α/ι/υ, undetermined from
  spelling) are flagged honestly rather than guessed; a supplied lemma or vowel length resolves them.
- **Crasis / elision / movable-nu resolver** (`greek.resolve_sandhi`, `resolve_sentence`; `aegean greek
  sandhi`): expands surface contractions to their underlying word(s) (κἀγώ to καί + ἐγώ, τἀμά to
  τὰ + ἐμά) through a small, contribution-friendly curated lexicon. Conservative: unlisted or ambiguous
  forms are flagged uncertain, never over-expanded.
- **Wider closed-class coverage** in the zero-dependency rule POS/morphology: the indefinite and
  interrogative τις/τίς (distinguished by the written accent), the relative ὅς/ἥ/ὅ paradigm,
  determiners (ἄλλος/ἕκαστος/πᾶς), the low cardinals and ordinals, and more particles now tag and
  analyse correctly (`analyze("τις")` is no longer empty).
- **LSJ sense selection** (`ai.select_sense`) and a **grounding-regime detector** (`ai.grounding_regime`):
  offline, deterministic helpers that rank an LSJ entry's senses by fit to a context and estimate
  whether grounding a generation step will help, stay neutral, or hurt for a given text. Exploratory.
- **Evaluation receipts** (`greek.eval_receipt`): a content-addressed, tamper-evident record tying an
  evaluation result to its exact inputs (package version, data manifest, model id, protocol, scores),
  for reproducibility.
- **Paired significance testing** (`analysis.mcnemar`, `analysis.paired_bootstrap`): tests whether two
  systems differ significantly on a shared evaluation set, rather than only bounding one system's score.
- **Aegean structure tooling** (exploratory): Monte-Carlo null models with explicit, documented nulls
  (`analysis.monte_carlo_p`) so a structure statistic carries a p-value against a stated baseline;
  distributional sign embeddings (`analysis.sign_embeddings`); unsupervised morpheme segmentation
  (`analysis.segment`, `candidate_morphs`); and Brown sign-class induction (`analysis.induce_classes`),
  aimed at the least-served script, Cypro-Minoan.

## 0.10.0 (2026-06-25)

### Changed
- **Quantized neural pipeline** (`grc-joint`): the joint tagger/parser/lemmatizer now ships quantized
  at **~173 MB** (down from ~518 MB, about 3x smaller), with **no loss of accuracy** on the UD Ancient
  Greek Perseus benchmark (UPOS 97.0 / UFeats 96.0 / lemma 94.3 / UAS 90.2 / LAS 85.6, identical to the
  fp32 model within rounding). The recipe is weight-only int8 on the matrix weights plus fp16
  elsewhere, keeping activations in full precision; full int8 (quantized activations) collapses the
  encoder, so it is avoided. The `[neural]` extra now requires `onnxruntime>=1.23`; the fp32 model
  remains available at the `grc-joint-v2` release for reproducibility.

## 0.9.0 (2026-06-24)

### Added
- **Cypriot syllabic corpus** (`aegean.load("cypriot")`): 178 inscriptions of *Inscriptiones
  Graecae* XV 1, the Berlin-Brandenburg Academy digital edition (CC BY 4.0), bundled as a hosted
  snapshot with transliteration, editorial apparatus, find-place/date/material, and translations.
  The corpus grows from a 2-document illustrative sample to a real syllabic corpus.
- **Inflection synthesis** (`greek.inflect(lemma, **features)`, `greek.paradigm(lemma)`): the
  inverse of lemmatization, generating the attested inflected forms of a lemma from the AGDT.
  Activate with `greek.use_inflector()`. CLI: `aegean greek inflect`.
- **Terminology rarity** (`greek.terminology_rarity(text, corpus)`): a corpus-relative
  vocabulary-rarity score that flags rare or technical vocabulary, a translation-difficulty signal.
  CLI: `aegean greek rarity`.
- **Dialect and register tags** (`greek.usage(word)`): a word's dialect (Doric, Attic, Ionic, …)
  and register (poetic, medical, comic, …), mined from its LSJ entry. CLI: `aegean greek usage`.
- **Gated gloss grounding for translation** (`aegean.translate(text, glosses=True)`): adds gated,
  content-word LSJ glosses to the grounding (a polysemy gate, with an optional frequency gate), and
  warns when only the baseline lemmatizer is active. CLI: `aegean ai translate --glosses/--no-glosses`.
- **PROIEL convention-drift report** (`greek.proiel_drift()`): a part-of-speech confusion matrix
  and lemma-mismatch breakdown of the out-of-AGDT PROIEL evaluation, separating annotation-convention
  divergence from real error. CLI: `aegean greek eval proiel --drift`.

## 0.8.10 (2026-06-24)

### Added
- **EpiDoc inbound reader** (`aegean.io.from_epidoc` / `read_epidoc`, and `aegean import --epidoc`):
  load any EpiDoc TEI edition (a file or a folder of `.xml`) into a `Corpus` — the inverse of the
  EpiDoc writer. Recovers the id, find-place, token/line stream, editorial certainty
  (`<unclear>`/`<supplied>`), and `<app>` alternate readings, using only the stdlib XML parser
  (no extra dependency).

## 0.8.9 (2026-06-24)

### Added
- **OpenRouter AI provider** (`provider="openrouter"`, the `[openrouter]` extra): a fifth
  built-in provider reaching many models from one key through OpenRouter's OpenAI-compatible
  gateway. Set `OPENROUTER_API_KEY` for the key and `OPENROUTER_MODEL` for the `vendor/model`
  id (e.g. `anthropic/claude-3.5-sonnet`); works everywhere `--provider` is accepted.
- **Fuller CLI parity** with the Python API: `aegean greek nt` (load a New Testament book or
  passage with its gold annotations), `aegean ai summarize`, `aegean geo --word` (a word's
  per-site attestation map), `aegean greek eval ud --bootstrap` (percentile CIs), and a Linear A
  Workbench round-trip (`export -f workbench` / `import --workbench`).

## 0.8.8 (2026-06-24)

### Added
- **Pluggable lexicon registry** for Greek dictionaries. `greek.lexica()` lists the
  available dictionaries; `greek.use_lexicon(id)` activates a hosted one;
  `greek.gloss(word, dictionary=id)` and `greek.entry(word, dictionary=id)` resolve a word
  against a chosen (or any active) dictionary; `greek.lexicon_link(word)` builds a Logeion
  or Perseus deep-link for dictionaries that are not hosted. LSJ and Dodson are now backends
  in the registry; `use_lsj` / `use_dodson` / `gloss` / `lookup` keep working unchanged.
- **Three new dictionaries** behind the registry, each fetched to the cache on first use
  and built into a lemma→entry index (never bundled): the Intermediate Greek-English
  Lexicon (Middle Liddell, classical), Cunliffe's Lexicon of the Homeric Dialect (Homeric),
  and Abbott-Smith's Manual Greek Lexicon of the New Testament (Koine).
- CLI: `aegean greek lexica` lists the dictionaries, `aegean greek gloss --dict <id>` glosses
  from a chosen one, and `aegean greek lexicon-link <word>` builds a deep-link.

### Changed
- **`load_work` reference addressing** is stricter and clearer: malformed refs (empty
  components like `1..2`, a stray `-`) and descending verse ranges (`1.50-1.1`) raise with
  the reason, and the "selected no text" error lists the sections (or the line range) present
  where the ref failed.

## 0.8.7 (2026-06-23)

### Changed
- Neural pipeline model `grc-joint-v2`. UD Perseus test parsing improves to LAS 85.6 /
  UAS 90.2 (from 84.4 / 89.2), the best published result on every metric and stable across
  five training seeds. Two training changes: the AGDT→UD converter attaches
  non-coordination commas to the following token, and the relation head trains on predicted
  arcs rather than only gold arcs.

### Added
- Bootstrap confidence intervals for the UD evaluation: `greek.bootstrap_ud`, plus the
  generic `analysis.bootstrap_ci_seq` and `analysis.bootstrap_dict_seq`.
- Beta Code round-trip stage in the internal regression set (`greek.benchmark`).

### Fixed
- `docs/benchmarks.md`: corrected the Gorman treebank license to CC BY-SA 4.0, documented
  the train/dev/test split and lemma scoring, and added seed mean ± std and bootstrap CIs.

## 0.8.6 (2026-06-23)

### Changed
- Wording refinements across the README and wiki.

## 0.8.5 (2026-06-16)

### Fixed
- The `aegean` command starts under typer ≥ 0.26, which vendors its own Click. The
  interactive shell now reaches Click through typer instead of importing `click` directly.

## 0.8.4 (2026-06-16)

### Added
- Interactive shell (`aegean repl`): run subcommands without the `aegean` prefix, with
  Tab-completion and history. Adds `prompt_toolkit` to the `[cli]` extra.

## 0.8.3 (2026-06-15)

### Changed
- The in-browser demo covers every client-side feature: Greek word analysis, Koine
  glossing, the work catalogue, the syllabary→Greek bridge, Linear A accounting, the file
  importer, and cross-script comparison.
- Refreshed the README "About the author" section.

## 0.8.2 (2026-06-15)

### Added
- Universal corpus input (`aegean.read_corpus`, every `aegean` corpus command): accepts a
  registered id, a Greek work id, a `.json`/`.db` path, or `-` for JSON on stdin.
- Combine corpora (`aegean combine`; `aegean.combine`, `Corpus.merge`, `Corpus.subset`),
  with explicit duplicate-id handling (`--on-conflict`) and merged provenance.
- Save results to files (`-o/--output` on `stats`, `keyness`, `dispersion`, `search`, and
  the `analyze` commands): `.json`, `.csv`, or `.txt` by extension.
- Save AI outputs (`-o` on `ai` commands; `ExploratoryResult.to_dict/to_json/from_dict`),
  preserving the exploratory label and grounding.
- Append to a database (`aegean db add`, `to_sqlite(append=True)`, `Corpus.to_sql(append=True)`):
  upsert documents by id and refresh the FTS index.
- Save a queried subset (`aegean query ... -o`, `QueryResults.to_corpus`) with a `subset:`
  provenance note.
- Work and book discovery: `greek.popular_works()` / `aegean greek works` and
  `greek.nt_books()` / `aegean greek nt-books` (offline metadata).
- Full work catalogue (`greek.catalog()`, `aegean greek catalog`): an offline index of
  1,778 Greek works in Perseus canonical-greekLit + First1KGreek, searchable by author,
  title, or source. Metadata only; texts fetch on demand.
- Import your own text (`aegean import`; `aegean.io.from_text`, `from_text_file`,
  `from_text_dir`, `from_csv`): `.txt`, a folder, or CSV into a `Corpus`, with
  `--split whole|paragraph|line`.

### Fixed
- `Corpus` with duplicate document ids is now self-consistent: the constructor collapses
  duplicates to one document per id (keeping the last) and warns.
- `aegean analyze cooccur` returns a deterministic order (shared-document count, then word).
- Linear A sound-value count corrected in the docs: 47 of 344 inventory signs carry a sound
  value (was stated as 84).
- In-browser demo: `aegean.cache` imports sqlite3 lazily, so `import aegean` works under
  Pyodide. The footprint guard now asserts `import aegean` never imports sqlite3.

## 0.8.1 (2026-06-14)

### Added
- Greek New Testament corpus (`greek.load_nt`, `aegean.load("nt")`): Nestle 1904 with gold
  lemma, Robinson morphology, Strong's number, reconciled UPOS, and a Koine gloss per token
  (in `Token.annotations`). One book bundled; the full 27 fetch to cache.
- Koine glossing (`greek.use_dodson` / `gloss_nt` / `gloss_strongs` / `lookup_nt`): the
  Dodson lexicon (CC0), bundled.
- NT evaluation fold (`greek.evaluate_on_nt`, `aegean greek eval nt`).
- Per-token annotations (`Token.annotations`): optional `dict[str, str]`, round-trips
  losslessly and surfaces as `to_dataframe` columns.
- In-browser demo (`docs/demo/`, published at `/demo/`): the core toolkit client-side via
  Pyodide.
- MCP server (`aegean-mcp`, the `[mcp]` extra): exposes corpora, sign search, accounting,
  the Greek pipeline, scansion, and Koine glossing as MCP tools.
- Aeolic lyric scansion (`greek.scan_aeolic`): glyconic, pherecratean, sapphic, and alcaic
  line types. Adds three-vowel synizesis to the curated lexicon.
- `aegean workbench`: fetch the Linear A Research Workbench static build (sha256-pinned) and
  serve it locally.
- Scribal-hand analysis (`aegean.analysis.scribal_hands` / `hand_keyness`): profile DAMOS
  scribal hands and surface what is characteristic of each.
- SQLite persistence (`Corpus.to_sql` / `from_sql`, `aegean.db`): documents and tokens as
  rows with an optional FTS5 index, provenance preserved. `aegean.db.stream(path)` yields
  documents one at a time.

### Packaging
- License declared as the PEP 639 SPDX expression (`license = "Apache-2.0"`); wheel/sdist
  carry Metadata 2.4.
- Python 3.14 added to the CI matrix and classifiers.
- `MANIFEST.in` excludes `tests/`; README links absolutized for PyPI.
- Workbench round-trip (`aegean.io.to_workbench` / `from_workbench_export`).

## 0.8.0 (2026-06-10)

First beta of the 0.8 line: a complete Linear A sign repertoire, an editorial-status model
with a schema-valid EpiDoc round-trip, Pleiades-aligned find-sites and geographic analysis,
the full Greek NLP track including a neural pipeline, the DAMOS and SigLA corpora on demand,
and a hosted API reference.

### Added
- Neural Greek pipeline (`greek.use_neural_pipeline`, the `[neural]` extra): one
  jointly-trained, torch-free model for POS, UD FEATS, dependency trees, and lemmas. UD
  Ancient Greek (Perseus) test: 96.9 UPOS / 96.1 UFeats / 94.4 lemma / 89.2 UAS / 84.4 LAS.
  Inference is onnxruntime + numpy; the model fetches to cache.
- Standard-benchmark evaluation (`greek.evaluate_on_ud`) with the official CoNLL 2018
  evaluator, plus `greek.agdt_ud_overlap` for the leakage manifest.
- One-call analysis (`greek.pipeline`): tokenize → sentence-split → tag → lemmatize → parse.
- Full DAMOS Linear B corpus (`aegean.load("damos")`): ~5,900 tablets (CC BY-NC-SA),
  fetched to cache, carrying scribal hand, find-context, and object class.
- SigLA Linear A corpus (`aegean.load("sigla")`): 781 documents (CC BY-NC-SA).
- Full Unicode Linear A sign repertoire (344 signs).
- Editorial status on tokens (`ReadingStatus`) and variant readings (`Token.alt`), both
  surviving the JSON and EpiDoc round-trips. EpiDoc export is schema-valid and CI-validated.
- Real Greek works on demand (`greek.load_work`): a fetch-to-cache TEI reader for Perseus
  canonical-greekLit and First1KGreek, with citation addressing.
- Geographic analysis (`aegean.geo`, the `[geo]` extra): corpus → GeoDataFrame from a
  bundled, Pleiades-aligned gazetteer.
- Corpus statistics (`aegean.analysis.stats`): Gries' DP dispersion, Dunning log-likelihood
  keyness with log-ratio, and bootstrap confidence intervals (pure stdlib).
- Visualization (`aegean.viz`, the `[viz]` extra) and `aegean plot`.
- Cross-script phonetic comparison (`aegean.analysis.compare`).
- The `aegean` command line (the `[cli]` extra): the toolkit without writing Python, with
  `--json` everywhere and stdin piping.
- Grounded AI layer (`aegean.ai`): structured grounding with a provenance trace, JSON-mode
  extraction, and a groundedness eval harness.
- Iambic trimeter scansion (`greek.scan_trimeter`) with resolution, plus a curated synizesis
  lexicon.
- More Greek core: lenient normalization, a syllabification exception lexicon, and a PROIEL
  out-of-AGDT evaluator (`greek.evaluate_on_proiel`).
- Linear B sample (18 tablets) and Greek-bridge lexicon (150 entries); Cypriot lexicon (17).
- Opt-in analysis cache (`aegean.cache`) and streaming corpus views.
- Lossless JSON round-trip, compound `query()`, CSV/Parquet export, citation automation,
  and a data-versioning manifest (`data.versions()`).
- Wider public API and a hosted API reference.

### Changed
- Core has zero hard third-party dependencies; pandas is the `[data]` extra.
  `scripts/check_footprint.py` enforces import-clean/import-fast/code+JSON-only in CI.
- `greek.evaluate` renamed `greek.evaluate_parser` (the one breaking rename, before the API
  freeze).

### Fixed
- Infinite recursion with `use_tagger()` + `use_lemmatizer()` both active on an
  out-of-treebank form.
- The AI `summarize` capability now labels its result `kind="summarize"`.

## 0.7.0 (2026-06-10)

### Added
- EpiDoc (TEI) export (`aegean.io.to_epidoc`, `write_epidoc`): the inverse of the reader, so
  a written corpus reloads through `parse_epidoc`. Uses the stdlib XML writer.
- CSV / Parquet export (`aegean.io.to_csv`, `to_parquet`): CSV needs `[data]`, Parquet needs
  `[parquet]`.
- `aegean.io` exposed as a top-level subpackage.

## 0.6.0 (2026-06-10)

### Added
- Lossless JSON round-trip on `Corpus` (`to_json` / `from_json` / `from_dict`).
- `Corpus.query(filters, output=...)`: the compound-query engine as a first-class method,
  returning `QueryResults`.

## 0.5.0 (2026-06-10)

### Added
- Out-of-AGDT evaluation (`greek.evaluate_on_proiel`): scores the lemmatizer/tagger against
  PROIEL (Greek NT + Herodotus), a source none of pyaegean's models train on. Fetched for
  evaluation only (CC BY-NC-SA 3.0).
- Cypro-Minoan (`aegean.scripts.cyprominoan`): a 99-sign inventory from the Unicode Character
  Database, sign inventory and tokenization only (undeciphered; no transliteration or
  bridge).

## 0.4.0 (2026-06-10)

### Added
- Linear B script (`aegean.scripts.linearb`): a 211-sign inventory and phonetic map,
  `word_to_phonetic` transliteration, and `Corpus.load("linearb")`.
- Linear B → Greek bridge (`greek_reading`, `gloss`): a curated Mycenaean→Greek lexicon
  (`PO-ME → ποιμήν`).
- Linear B accounting: the engine recognises `to-so`/`to-sa` totals (markers are per-script).
- Bring-your-own Linear B corpus: a DAMOS-style EpiDoc reader (the `[epidoc]` extra) via
  `PYAEGEAN_LINEARB_CORPUS`. No Linear B corpus is bundled (DAMOS is CC BY-NC-SA).
- Cypriot syllabary (`aegean.scripts.cypriot`): a 55-sign inventory, transliteration, a
  curated Cypriot→Greek bridge (`PA-SI-LE-U-SE → βασιλεύς`), and a sample corpus.

### Changed
- Linear B and Cypriot sign data bundled from the Unicode Character Database (Unicode-3.0
  license; attribution in NOTICE).

## 0.3.0 (2026-06-10)

### Added
- Generalizing POS tagger (opt-in `greek.use_tagger()`): an averaged-perceptron sequence
  tagger (pure Python) trained on the AGDT, predicting POS for unseen forms. 84.4% overall /
  83.6% on unseen forms (90/10 AGDT split). Built on first use, cached.
- Generalizing lemmatizer (opt-in `greek.use_lemmatizer()`): a Chrupała edit-tree model with
  an averaged-perceptron reranker (pure Python). 84.5% overall / 40.3% on unseen forms.
- Neural lemmatizer backend (opt-in `[neural]`, `greek.use_neural_lemmatizer()`): a
  fine-tuned GreTa seq2seq exported to ONNX, 76.3% on unseen forms, ~92% overall as a hybrid
  with a bundled gold lookup. Torch-free numpy decode over int8 ONNX. Model (~232 MB,
  CC BY-SA) fetched to cache.
- Leakage-free held-out evaluation (`aegean.greek.heldout`): splits the AGDT by sentence and
  scores on the unseen subset.

### Changed
- `pos_tag`/`pos_tags` and `lemmatize` consult the trained backends (when active) for forms
  the lexicon and treebank lookup don't cover.
- Core has zero hard third-party dependencies: pandas moved to `[data]`, scipy dropped (the
  two collocation statistics are now pure stdlib). *Breaking only if you called
  `to_dataframe()` without `[data]`.*
- Footprint policy replaces the wheel-size guard.

## 0.2.0 (2026-06-08)

### Added
- LSJ glossing (opt-in `greek.use_lsj()`): fetches the Perseus LSJ lexicon (CC BY-SA 4.0,
  ~270 MB) and builds a derived index; `gloss(word)` / `lookup(word)`. Composes with the
  lemmatizer (`ἀνδρός` → `ἀνήρ`).
- Dependency parser (opt-in baseline, `greek.use_parser()`): an arc-eager
  averaged-perceptron parser (pure Python); `parse()` returns a `DepTree`, `evaluate()`
  reports held-out UAS/LAS (~0.67 / 0.57 projective). Arc-eager builds only projective trees.
- A revamped end-to-end tutorial notebook.

### Changed
- Documentation refreshed across the README and wiki for the 0.2.0 Greek NLP track.

## 0.1.0 (2026-06-08)

First public release (alpha). A specialist toolkit for Ancient Greek and the Aegean syllabic
scripts; analysis of the undeciphered Linear A material is always labeled exploratory.

### Added
- Core (`aegean.core`): a script-agnostic model (`Corpus`, `Document`, `Token`, `Sign`,
  `SignInventory`, `Numeral`, a `Script` plugin registry, and `Provenance`).
- Linear A (`aegean.scripts.lineara`): a bundled 1,721-inscription corpus, 84-sign
  inventory, sign→sound map, and transliteration.
- Analysis (`aegean.analysis`): accounting reconciliation, wildcard sign search, phonetic
  distance + alignment, morphology clustering, collocation statistics, a query engine, and
  tablet-structure classification.
- Greek NLP (`aegean.greek`): normalization, tokenization, syllabification, accent and
  prosody, dactylic scansion, reconstructed IPA, POS tagging, a rule-based morphological
  analyzer, a baseline lemmatizer, and an opt-in Perseus AGDT treebank backend.
- AI layer (`aegean.ai`, `aegean.translate`): a provider-agnostic LLM client (Anthropic,
  OpenAI, Grok, Gemini), response caching, corpus grounding, and hybrid translation. Every
  generative result is a provenanced, exploratory-labeled `ExploratoryResult`.
- Data (`aegean.data`): bundled JSON corpora plus a `fetch()` download-to-cache layer
  (sha256-verified) for large assets.

### Notes
- Requires Python ≥ 3.10. `numpy`/`pandas`/`scipy` and provider SDKs are imported lazily.
- Licensing: code Apache-2.0; Linear A corpus JSON via GORILA/mwenge; Linear A imagery not
  redistributed; Perseus AGDT is CC BY-SA 3.0 (fetched, not bundled). See `NOTICE`.
