# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## Unreleased

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
