# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## Unreleased

## 0.8.6 (2026-06-23)

### Changed
- Refined wording across the README and wiki for clarity and consistency.

## 0.8.5 (2026-06-16)

### Fixed
- The `aegean` command line now starts under typer ≥ 0.26 (which vendors its own Click and no
  longer installs the standalone `click` package). The interactive shell reaches Click through
  typer instead of importing `click` directly, so a fresh `pip install "pyaegean[cli]"` works.
  (0.8.4 could fail to start the `aegean` command when standalone `click` was absent.)

## 0.8.4 (2026-06-16)

### Added
- **Interactive shell** (`aegean repl`). Starts a prompt where you run subcommands without
  the `aegean` prefix (`stats lineara --top 5`, `greek catalog plato`, `ai translate …`),
  with Tab-completion of commands and options and a recallable history. Each line is
  dispatched through the same command tree, so behaviour is identical to the one-shot CLI;
  a bad command prints its error and the shell stays open. When stdin is not a terminal the
  shell reads one command per line, so it is scriptable too. (Adds `prompt_toolkit` to the
  `[cli]` extra; `import aegean` stays dependency-free.)

## 0.8.3 (2026-06-15)

### Changed
- The in-browser demo (docs/demo) now has a live example of **every feature that runs
  client-side**: Greek word analysis (syllables / accent / IPA / morphology), Koine glossing,
  the work catalogue, the syllabary→Greek bridge, Linear A accounting reconciliation, the file
  importer, and cross-script phonetic comparison, alongside the existing Beta Code, NLP
  pipeline, scansion, and Linear A sign-search examples.
- Refreshed the README "About the author" section.

## 0.8.2 (2026-06-15)

### Added
- **Universal corpus input** (`aegean.read_corpus`, and every `aegean` corpus command). A
  command's corpus argument now accepts not just a registered id but a **Greek work id**
  (`tlg0012.tlg001`), a path to a saved **`.json`** or **`.db`** corpus, or **`-`** for JSON on
  stdin, so e.g. `aegean db build tlg0012.tlg001 -o iliad.db`, `aegean stats iliad.json`, and
  `aegean export tlg0012.tlg002 -f csv -o odyssey.csv` all work without writing Python.
- **Combine corpora** (`aegean combine`; `aegean.combine`, `Corpus.merge`, `Corpus.subset`):
  merge several corpora or works into one and save it: `aegean combine tlg0012.tlg001
  tlg0012.tlg002 -o homer.db` puts all of Homer in one database. Duplicate document ids are
  handled explicitly (`--on-conflict error|first|last|suffix`), and the merged provenance names
  every source so `cite` stays truthful.
- **Save results to files** (`--output/-o` on `stats`, `keyness`, `dispersion`, `search`, and
  `analyze {assoc,cooccur,clusters,hands}`): write a command's result as `.json`, `.csv`
  (stdlib, no pandas), or `.txt` by extension, no shell redirection needed.
- **Save AI outputs** (`--output/-o` on `ai {translate,gloss,hypotheses,ask,extract}`;
  `ExploratoryResult.to_dict`/`to_json`/`from_dict`): export a translation/gloss as `.json`
  (text + provenance + grounding) or `.txt` (labeled text). The **exploratory** label and
  grounding are preserved on disk, so a saved result can't be mistaken for ground truth.
- **Append to a database** (`aegean db add`, `aegean.db.to_sqlite(..., append=True)`,
  `Corpus.to_sql(..., append=True)`): upsert documents into an existing SQLite corpus by id
  (a matching id is replaced, new ids are added; the FTS index is refreshed), so a database
  can be built up incrementally, e.g. `aegean db add tlg0012.tlg002 -o homer.db`.
- **Save a queried subset** (`aegean query ... -o out.json|.db`, `QueryResults.to_corpus`):
  write the inscriptions a query matched as a reusable corpus, with a `subset:` provenance note
  so `cite` on the result names the query.
- **Work and book discovery** for the Greek loaders. `greek.popular_works()` and
  `aegean greek works` list a curated, verified catalog of well-known Perseus works with
  their CTS ids (Homer, the tragedians, Herodotus, Plato, …); `greek.nt_books()` and
  `aegean greek nt-books` list the 27 New Testament books and the names `load_nt` accepts.
  `aegean greek work` now points at the catalog. Both are pure metadata (offline).
- **Full work catalogue** (`greek.catalog()`, `aegean greek catalog`): a bundled, offline
  discovery index of **every** work with a Greek (`-grc`) edition in Perseus
  canonical-greekLit + First1KGreek: 1,778 works, far beyond the 25 curated highlights:
  searchable by author, title (English or Greek), free-text, or source. Each entry's id loads
  directly with `load_work`. Metadata only (id/author/title/Greek title/source); the texts
  themselves stay CC BY-SA and fetched on demand, never bundled. Regenerate with
  `scripts/build_greek_catalogue.py`.
- **Bring your own text files** (`aegean import`; `aegean.io.from_text`, `from_text_file`,
  `from_text_dir`, `from_csv`): import a plain `.txt` file, a folder of text files, or a CSV
  into a `Corpus`: `aegean import myplato.txt -o myplato.json` then `aegean stats
  myplato.json`. `--split whole|paragraph|line` chooses how a text becomes documents; Greek
  text is tokenized with the Greek tokenizer, other scripts by whitespace. The
  `read_corpus`/`CORPUS` error now points at `aegean import` when handed a `.txt`/`.csv`.

### Fixed
- **`Corpus` with duplicate document ids** is now self-consistent: the constructor collapses
  duplicates to one document per id (keeping the last, which is what `.get()` already returned)
  and warns, so `.documents`, `len()`, iteration, `fingerprint()`, and the id lookup all agree
  instead of disagreeing (`.documents` had kept both copies while `.get()` saw only the last).
- **`aegean analyze cooccur`** now returns a deterministic order: by shared-document count,
  then alphabetically by word to break ties, so its output is reproducible across runs
  (it previously inherited the hash-order of per-document word sets, shuffling tied rows).
- **Linear A sound-value count** corrected in the docs: 47 of the 344 inventory signs carry
  an assigned sound value (the source docstring, README, and wiki had said 84).
- **In-browser demo** failed on every action: `import aegean` raised `ModuleNotFoundError`
  because the opt-in analysis cache did a top-level `import sqlite3`, which Pyodide unvendors.
  `aegean.cache` now imports sqlite3 lazily, so `import aegean` works without it (Pyodide, or
  a Python built without sqlite3); the demo also loads sqlite3 for the published wheel and
  uses a clearer Linear A search example (`*-RO`). The footprint guard now asserts that
  `import aegean` never imports sqlite3.

## 0.8.1 (2026-06-14)

### Added
- **Greek New Testament corpus** (`greek.load_nt`, `aegean.load("nt")`): the Nestle 1904 NT
  with a gold lemma, Robinson morphology, Strong's number, reconciled UD UPOS, and a Koine
  gloss on every token (carried in the new `Token.annotations`). `load_work`-style reference
  addressing (`load_nt("John", ref="1.1-18")`). Text is public domain and the
  morphology/lemmas/Strong's are CC0 (biblicalhumanities/Nestle1904): one book is bundled as
  an offline sample, the full 27 books fetch to cache on demand.
- **Koine glossing** (`greek.use_dodson` / `gloss_nt` / `gloss_strongs` / `lookup_nt`): the
  Dodson Greek lexicon (CC0), bundled in the wheel (the Koine counterpart to `use_lsj`). The
  NT corpus self-glosses from it offline.
- **NT evaluation fold** (`greek.evaluate_on_nt`, `aegean greek eval nt`): scores the neural
  pipeline against the Nestle 1904 gold (lemma + reconciled UPOS): a Nestle-own-gold
  complement to the PROIEL out-of-AGDT check. Numbers in `docs/benchmarks.md`.
- **Per-token annotations** (`Token.annotations`): an optional `dict[str, str]` on the core
  `Token` (mirroring `Sign.attrs`) for script-specific facts; round-trips losslessly and
  surfaces as `to_dataframe` columns.
- **In-browser demo** (`docs/demo/`, published with the docs site at `/demo/`): the core
  toolkit running entirely client-side via Pyodide: Beta Code → Unicode, the Greek pipeline,
  metrical scansion, and Linear A wildcard sign search: no install, no server.
- **MCP server** (`aegean-mcp`, the `[mcp]` extra): a Model Context Protocol server exposing
  the toolkit to agents (Claude Code and other MCP clients): list/inspect corpora, wildcard
  sign search, accounting reconciliation, the Greek pipeline, verse scansion, and Koine
  glossing, as MCP tools over stdio.
- **Aeolic lyric scansion** (`greek.scan_aeolic`, `greek.AEOLIC_LINES`): the glyconic,
  pherecratean, sapphic (hendecasyllable + adonean) and alcaic (hendecasyllable / enneasyllable
  / decasyllable) line types, as fixed quantity templates: a line scans-or-declines like the
  existing hexameter / pentameter / trimeter. Also `scan_line(line, "<aeolic type>")`. Adds
  three-vowel synizesis (θεούς-type) to the curated, test-enforced synizesis lexicon.
- **`aegean workbench`** (CLI): fetch the Linear A Research Workbench's static build to the
  cache (sha256-pinned, ~3 MB) and serve it locally: the browser UI over the corpus and
  analysis modules, with cached Linear A facsimile imagery mounted at `/upstream/images/`
  when present.
- **Scribal-hand analysis** (`aegean.analysis.scribal_hands` / `hand_keyness`): profile each
  DAMOS scribal hand (tablets, sites, chronology, the hand's most frequent words) and surface
  what is characteristic of one hand versus all the others via the same log-likelihood keyness
 (over the hands DAMOS records in `meta.scribe`).
- **SQLite persistence** (`Corpus.to_sql` / `Corpus.from_sql`, `aegean.db`): a faithful,
  queryable round-trip of a corpus to a stdlib-`sqlite3` database: documents and tokens as
  rows with an optional FTS5 text index (`aegean.db.search`), and provenance + sign inventory
  preserved so a DB-loaded corpus cites exactly like a JSON-loaded one. `aegean.db.stream(path)`
  yields documents one at a time for large databases, without materializing the corpus.
- **GORILA online**: the Linear A corpus provenance (and README / NOTICE / wiki) now points
  to the digitized GORILA volumes in the École française d'Athènes' CEFAEL library.

### Packaging
- Declared the license as the PEP 639 SPDX expression (`license = "Apache-2.0"`), dropping the
  deprecated trove classifier; the wheel/sdist now carry Metadata 2.4 with `License-Expression`.
- Test and classify **Python 3.14** (added to the CI matrix and the trove classifiers).
- `MANIFEST.in` excludes `tests/` from the sdist; the six repo-relative README links are
  absolutized so they resolve on the PyPI description page.
- **Workbench round-trip** (`aegean.io`): `to_workbench(corpus, path=None)` emits the
  [Linear A Research Workbench](https://linearaworkbench.xyz/)'s
  inscription-record JSON, so any corpus — your own `from_records` finds included — opens in
  the browser app via its `?corpus=<url>` loader; `from_workbench_export(source)` loads the
  workbench's schema-v1 corpus exports (Data Export module or static data API) back into a
  `Corpus`, carrying glyphs, transcriptions, image references, and the export's own metadata
  into the provenance.

## 0.8.0 (2026-06-10)

A hardening pass for scholarly use: a complete Linear A sign repertoire, an editorial-status
model with a schema-valid EpiDoc round-trip, Pleiades-aligned find-sites and geographic
analysis, the full Greek NLP track through a state-of-the-art neural pipeline, the DAMOS and
SigLA corpora on demand, a wider public API, and a hosted API reference. Released as **beta**;
the API is close to stable but may still shift before 1.0.

### Added
- **Neural Greek pipeline** (`greek.use_neural_pipeline`, the `[neural]` extra): one
  jointly-trained, torch-free model for POS, full morphology (UD FEATS), UD dependency trees,
  and lemmas. Measured above every published UD Ancient Greek (Perseus) number:
  96.9 UPOS / 96.1 UFeats / 94.4 lemma / 89.2 UAS / 84.4 LAS, end-to-end from raw text.
  Inference is onnxruntime + numpy; the model is fetched to cache, never bundled. Protocol and
  tables in `docs/benchmarks.md`.
- **Standard-benchmark evaluation** (`greek.evaluate_on_ud`): scores the active pipeline on the
  UD Ancient Greek test folds with the official CoNLL 2018 evaluator, plus `greek.agdt_ud_overlap`
  for the leakage-exclusion manifest.
- **One-call analysis** (`greek.pipeline`): tokenize → sentence-split → tag → lemmatize → parse
  in a single pass, returning per-token records.
- **Full DAMOS Linear B corpus** (`aegean.load("damos")`): F. Aurora's Database of Mycenaean at
  Oslo (~5,900 tablets, CC BY-NC-SA), decoded to a release asset and fetched to cache. Carries
  scribal hand, find-context, and object class, so scribe-level work is one-liners
  (`damos.filter(scribe="117")`).
- **SigLA Linear A corpus** (`aegean.load("sigla")`): the Salgarella & Castellan palaeographic
  database (781 documents, CC BY-NC-SA) with typology, dimensions, periods, SigLA's own word
  division, and commodity ideograms.
- **Full Unicode Linear A sign repertoire**: the bundled inventory now covers the entire Unicode
  Linear A block (344 signs) rather than only the 84 transliteration-aligned signs.
- **Editorial status on tokens** (`ReadingStatus`: CERTAIN / UNCLEAR / RESTORED / LOST) and
  **variant readings** (`Token.alt`), both surviving the JSON and EpiDoc round-trips. EpiDoc
  export is now schema-valid against the official RelaxNG and CI-validated.
- **Real Greek works on demand** (`greek.load_work`): a fetch-to-cache TEI reader for Perseus
  canonical-greekLit and First1KGreek (CC BY-SA). One call loads a work into the corpus model:
  the Iliad as 24 books / ~127k tokens — with citation addressing (`ref="1.1-1.50"`).
- **Geographic analysis** (`aegean.geo`, the `[geo]` extra): corpus → geopandas GeoDataFrame from
  a bundled, Pleiades-aligned Aegean gazetteer (33/56 sites, each coordinate-verified).
- **Corpus statistics** (`aegean.analysis.stats`): Gries' DP dispersion, Dunning log-likelihood
  keyness with log-ratio effect size, and bootstrap confidence intervals: pure stdlib, over any
  corpus or subset.
- **Visualization one-liners** (`aegean.viz`, the `[viz]` extra): frequency, dispersion, keyness,
  co-occurrence network, accounting-balance, and scansion plots; `aegean plot` from the shell.
- **Cross-script phonetic comparison** (`aegean.analysis.compare`): align a word in one script
  against another by sound, and rank a wordlist by phonetic closeness across scripts.
- **The `aegean` command line** (the `[cli]` extra): the whole toolkit without writing Python:
  corpus, Greek pipeline, analysis, data, and the exploratory AI layer — with `--json` everywhere
  and stdin piping. Imported only by the console script, so `import aegean` stays
  dependency-free.
- **Grounded AI layer** (`aegean.ai`): structured grounding (`GroundingItem`) with an auditable
  provenance trace, JSON-mode extraction, and a grounded-generation eval harness
  (`aegean.ai.eval`) that scores groundedness and fabrication.
- **Iambic trimeter scansion** (`greek.scan_trimeter`) with resolution, plus a curated synizesis
  lexicon: alongside hexameter and pentameter.
- **More Greek core**: lenient normalization (`greek.normalize(..., lenient=True)`), a
  syllabification exception lexicon (compounds divide at the point of union), and a neutral
  out-of-AGDT PROIEL evaluator (`greek.evaluate_on_proiel`).
- **Linear B sample & lexicon expansion**: the bundled illustrative sample grows to 18 tablets and
  the Greek-bridge lexicon to 150 source-attested entries; the Cypriot lexicon to 17.
- **Opt-in analysis cache** (`aegean.cache`, off by default) and **streaming corpus views**
  (`Corpus.iter_documents/iter_tokens/iter_words`) for large corpora.
- **Lossless JSON round-trip**, a compound **`query()`**, **CSV/Parquet export**, **citation
  automation** (`Provenance.bibtex()/.apa()`, `Corpus.cite()` down to the exact subset), and a
  **data-versioning manifest** (`data.versions()`).
- **Prebuilt artifacts for a fast first use**: the opt-in Greek backends prefer small
  project-hosted assets (LSJ index, AGDT-derived bundle) over slow local builds, with
  build-from-source as the fallback.
- **Wider public API**: the core value types and the analysis/Greek error types are re-exported
  from the top-level namespaces.
- **Hosted API reference** and an **expert validation loop** (GitHub issue forms for corrections,
  validations, and data contributions, plus the For Specialists wiki page).

### Changed
- **Core now has zero hard third-party dependencies**: `import aegean` loads nothing heavy;
  pandas is the optional `[data]` extra. `scripts/check_footprint.py` enforces import-clean,
  import-fast, code+JSON-only in CI.
- `greek.evaluate` renamed `greek.evaluate_parser`, for consistency with `evaluate_tagger` /
  `evaluate_lemmatizer` (the one breaking rename, made ahead of an API freeze).
- Documentation states scope honestly throughout: the inventory's read-vs-unread split, the
  ~40 Linear A tablets with a checkable total, and which corpora are illustrative samples vs.
  fetched in full.

### Fixed
- Infinite recursion with `use_tagger()` + `use_lemmatizer()` both active, when lemmatizing a
  form outside the treebank lookup.
- The AI `summarize` capability now labels its result `kind="summarize"` (was mislabeled `"ask"`).

## 0.7.0 (2026-06-10)

Fills the `aegean.io` package with export adapters, completing the EpiDoc read+write round-trip.

### Added
- **EpiDoc (TEI) export** (`aegean.io.to_epidoc`, `aegean.io.write_epidoc`): serialize a `Document`
  or `Corpus` to EpiDoc TEI XML: the inverse of the bring-your-own reader, so a corpus written out
  reloads through `parse_epidoc` with the same ids, find-places, tokens, and lines. Uses the stdlib
  XML writer, so export needs no extra dependency.
- **CSV / Parquet export** (`aegean.io.to_csv`, `aegean.io.to_parquet`): write a corpus's
  document/token/word DataFrame to CSV or Parquet. CSV needs the `[data]` extra (pandas); Parquet
  also needs the new `[parquet]` extra (pyarrow).
- `aegean.io` is exposed as a top-level subpackage.

## 0.6.0 (2026-06-10)

Rounds out the corpus data layer: a lossless JSON round-trip and a first-class compound query.

### Added
- **Lossless JSON round-trip** on `Corpus`: `to_json(path=None)` serializes the entire corpus:
  every token (kind, signs, glyphs, line/position), the physical lines, full document metadata,
  the sign inventory, and provenance — and `from_json` / `from_dict` reconstruct it exactly. The
  existing `to_dict` stays as the compact, lossy summary.
- **`Corpus.query(filters, output=...)`**: the compound-query predicate engine (field registry,
  AND/OR/NOT, inscription/word output) is now a first-class corpus method, complementing the
  exact-match `filter(**meta)`. Returns `QueryResults` (`.inscriptions` / `.words`).

## 0.5.0 (2026-06-10)

Completes the Aegean syllabic set with **Cypro-Minoan**, and adds a neutral **out-of-AGDT
evaluation** of the Greek NLP stack against the PROIEL treebank.

### Added
- **Neutral out-of-AGDT evaluation** (`aegean.greek.evaluate_on_proiel`): scores the Greek
  lemmatizer/tagger against the PROIEL treebank (Greek NT + Herodotus), a source none of
  pyaegean's models trained on, for an honest cross-source generalization number. PROIEL is
  fetched to the cache for evaluation only (CC BY-NC-SA 3.0, never bundled); gold lemmas are
  homograph-normalized and POS compared under a reconciled tagset (PROPN→NOUN, SCONJ→CCONJ).
- **Cypro-Minoan** (`aegean.scripts.cyprominoan`): the undeciphered Bronze Age script of Cyprus,
  completing the Aegean syllabic set. A 99-sign inventory built from the Unicode Character Database
  (the "Cypro-Minoan" block), with conventional sign numbers (`CM001` …) and no phonetic values:
  the script is undeciphered, so the plugin offers the sign inventory and sign-sequence tokenization
  only, plus `Corpus.load("cyprominoan")` over a small illustrative sample. No transliteration,
  lexicon, or Greek bridge, by design.

## 0.4.0 (2026-06-10)

Adds **Linear B** and the **Cypriot syllabary**: the two deciphered Aegean syllabaries that
write Greek: through the same script-plugin model as Linear A. All Linear A analysis remains
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
  `PYAEGEAN_LINEARB_CORPUS`. No corpus is bundled or fetched by default: none is openly licensed
  (DAMOS is CC BY-NC-SA): only a small illustrative sample of canonical tablets.

- **Cypriot syllabary** (`aegean.scripts.cypriot`): the deciphered Aegean syllabary for the
  Arcado-Cypriot dialect of Greek. A 55-sign inventory and phonetic map from the Unicode
  Character Database, `word_to_phonetic` transliteration, a curated Cypriot→Greek bridge
  (`greek_reading`, `gloss`; `PA-SI-LE-U-SE → βασιλεύς`), and `Corpus.load("cypriot")` with a
  small illustrative sample.

### Changed
- Linear B and Cypriot sign data are bundled from the Unicode Character Database (Unicode-3.0
  license; attribution added to NOTICE).

## 0.3.0 (2026-06-10)

Adds opt-in Greek tagging and lemmatization that generalize to unseen forms: including a
neural lemmatizer backend for unseen-form lemma — and makes the core dependency-free. All
Linear A analysis remains exploratory.

### Added
- **Generalizing POS tagger** (opt-in): `greek.use_tagger()` trains an averaged-perceptron
  sequence tagger (pure Python, no heavy deps) on the AGDT that predicts part of speech for
  **unseen** forms from suffix/prefix/shape/accent + left-to-right context features: where
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
  of an unseen form, reaching **76.3% on unseen forms**. It ships as a hybrid (a bundled gold
  lookup answers seen forms exactly; the seq2seq handles the rest, ~92% overall). Inference is **torch-free**: a numpy greedy decode over int8 ONNX via onnxruntime,
  imported only on activation, so `import aegean` stays instant. The model (~232 MB, CC BY-SA) is
  fetched-to-cache, sha256-verified, never bundled; install with `pip install 'pyaegean[neural]'`.
- **Leakage-free held-out evaluation** (`aegean.greek.heldout`): splits the AGDT by
  sentence, flags dev forms unseen in training, and scores any tagger/lemmatizer (a pyaegean
  mode or a CLTK pipeline) on the disjoint unseen subset: the generalization measure
  behind the model numbers.

### Changed
- `pos_tag`/`pos_tags` consult the trained tagger (when active) for the open-class forms the
  closed-class lexicon and treebank lookup don't cover, generalizing tags to unseen text.
- `lemmatize`/`lemmatize_verbose` consult the neural backend, then the trained edit-tree
  lemmatizer (whichever is active), after the treebank lookup: generalizing lemmas to unseen forms.
- **Core now has zero hard third-party dependencies.** `pandas` moved to a new optional
  `[data]` extra (lazy-imported only by `to_dataframe`, which raises a clear install hint if
  it's missing); `scipy` was dropped entirely: the two collocation statistics (χ² p-value,
  Fisher's exact) are now pure stdlib (`math.erfc`/`math.lgamma`). `pip install pyaegean` no
  longer pulls pandas/numpy/scipy. *Breaking only if you called `to_dataframe()` without
  installing `pyaegean[data]`.*
- **Footprint policy replaces the wheel-size guard.** The `<3 MB` wheel check is gone (it was
  a no-op beside the old hard deps); `scripts/check_footprint.py` now enforces the invariants
  that matter: `import aegean` loads no heavy module, imports fast, and the wheel ships only
  code + JSON.

## 0.2.0 (2026-06-08)

Deepens the Greek NLP track with two opt-in, gold-data backends and a revamped
tutorial. All Linear A analysis remains exploratory.

### Added
- **LSJ glossing** (opt-in): `greek.use_lsj()` fetches the full Perseus
  Liddell-Scott-Jones lexicon (CC BY-SA 4.0, ~270 MB) into the cache and builds a
  derived gzipped index; `greek.gloss(word)` and `greek.lookup(word)` return a concise
  gloss or the full `LSJEntry`. Composes with the lemmatizer: an inflected form
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

## 0.1.0 (2026-06-08)

First public release (alpha). A specialist Python toolkit for Ancient Greek and the
Aegean syllabic scripts; analysis of the undeciphered Linear A material is always
labeled exploratory, never presented as ground truth.

### Added
- **Core** (`aegean.core`): a script-agnostic model: `Corpus`, `Document`, `Token`,
  `Sign`, `SignInventory`, `Numeral`, a `Script` plugin registry, and `Provenance`
  that travels with every corpus and stamps exports.
- **Linear A** (`aegean.scripts.lineara`): bundled 1,721-inscription corpus, 84-sign
  inventory, sign→sound map, and transliteration.
- **Analysis** (`aegean.analysis`): accounting reconciliation (KU-RO / PO-TO-KU-RO),
  wildcard sign-pattern search, weighted phonetic distance + alignment, morphology
  clustering, collocation statistics, a compound query engine, and tablet-structure
  classification: all parity-tested against golden fixtures.
- **Greek NLP** (`aegean.greek`): Unicode/Beta Code normalization, tokenization,
  syllabification, accent and prosody analysis, dactylic-meter scansion (hexameter +
  elegiac pentameter), reconstructed IPA (Attic/Koine), POS tagging, a rule-based
  morphological analyzer, and a baseline lemmatizer. An **opt-in** treebank backend
  (`greek.use_treebank()`, Perseus AGDT v2.1) supplies attested, correctly-accented
  lemmas and gold POS for known forms. A benchmark harness scores the pipeline and
  measures the treebank lift.
- **AI layer** (`aegean.ai`, `aegean.translate`): a provider-agnostic LLM client
  (Anthropic, OpenAI, xAI Grok, Gemini: SDKs optional), response caching, corpus
  grounding with prompt-injection wrapping, and hybrid lexicon+LLM translation. Every
  generative result is a provenanced, exploratory-labeled `ExploratoryResult`.
- **Data** (`aegean.data`): bundled JSON corpora plus a `fetch()` download-to-cache
  layer (sha256-verified, atomic, idempotent) for large assets: e.g. the Linear A
  facsimile imagery and the AGDT treebank: which are never bundled or re-hosted.

### Notes
- Requires Python ≥ 3.10. `numpy`/`pandas`/`scipy` and provider SDKs are imported lazily.
- Licensing: code Apache-2.0; Linear A corpus JSON via GORILA/mwenge; Linear A imagery
  © École Française d'Athènes and others (fetched, not redistributed); the Perseus
  AGDT treebank is CC BY-SA 3.0 (fetched + built in the cache, not bundled). See
  `NOTICE`.
