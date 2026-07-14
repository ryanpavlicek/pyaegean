# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## 0.48.0 (2026-07-14)

### Added

- Neural training, evaluation, and package inference now share a dependency-free,
  versioned preprocessing contract for NFC forms, pretokenized Roberta alignment,
  whole-word truncation, label supervision, and lemma composition.
- Candidate joint-model checkpoints record their annotation profile, preprocessing version,
  tokenizer policy, and subword limit. The ONNX exporter requires a new model
  identity and produces a schema-1 content manifest under a distinct asset name.

### Changed

- Candidate joint-model training and evaluation configure and validate the serialized tokenizer
  once, use the same manifest-owned subword limit, and reject incompatible non-Roberta
  tokenizers before training.
- Export manifests retain model/license provenance, bind required sidecars and tokenizer
  bytes, and are refreshed for every exported graph variant.
  The published `grc-joint-v3` artifact, default, and measurements are unchanged.

### Fixed

- Training no longer supervises a final word split by subword truncation, accepts
  out-of-range lemma-script targets, or treats the CoNLL-U `_` placeholder and unchanged
  identity edits as resolved neural lemmas.
- New-model export refuses the existing `grc-joint` data key, immutable v3 identity,
  stale/foreign output directories, malformed checkpoint metadata, and mismatched
  preprocessing or tokenizer contracts.

## 0.47.0 (2026-07-14)

### Added

- Typed Greek confidence records now carry task, model, source path, optional domain,
  calibration identity, measured support, and explicit unavailable reasons. Caller-supplied
  `AbstentionPolicy` values produce hashed `accept`/`review`/`unavailable` decisions through
  Python (`confidence_domain` / `confidence_policy`) and the matching CLI options.
- Development-only fitting helpers now include `fit_temperature` and monotone
  `fit_logit_affine`; they fit caller-provided pairs and do not imply a domain calibration,
  threshold, or release claim.
- Neural analysis receipts use schema 2 when confidence calibration or policy hashes
  participate, while schema-1 receipts and the legacy flat confidence fields remain readable.
- Training reproducibility contracts now validate content-addressed environment locks,
  resolver-closure evidence, clean-repository closure-scoped preflight reports, and
  completed run receipts.
  The committed Colab lock remains an explicitly non-authorizing, unverified template until
  a live G4-preferred or A100-fallback environment is captured and promoted.

### Changed

- Lemma output records the exact composition path (`lookup_form_upos`, `lookup_form`,
  `edit_script`, `lookup_lower_fallback`, or `identity_fallback`). Typed confidence does not
  invent thresholds or out-of-domain claims; empirical source/task calibration remains
  evidence-gated.
- The 2026-07-10 GPU verification note now distinguishes the 0.33.0 release it supported
  from the captured runtime's structured 0.32.0 package version; measurements are unchanged.
- The live asset-integrity checker now uses the same verified Python 3.14 TLS compatibility
  path as package downloads; certificate and hostname verification remain enabled.

## 0.46.0 (2026-07-14)

A source-preserving Greek sentence-segmentation release. It separates the
document boundary policy selected for an analysis from the preprocessing
contract recorded by a pipeline backend, while preserving the published
`grc-joint-v3` model and its measured results.

### Added

- `segment_text()` and its `segment_sentences()` alias return immutable sentence
  boundaries with half-open source spans, stable policy identities, provenance,
  and strict JSON round trips.
- Named `default`, `prose`, `verse`, `inscription`, and `papyrus` policies expose
  their deterministic rules. A validated plugin seam accepts edition-specific
  segmenters without adding a runtime dependency or presenting rule scores as
  calibrated confidence.
- The Greek tokenize and pipeline commands accept `--sentence-policy`; sentence
  tokenization also offers `--rich` source-span and provenance output.

### Changed

- Raw and typed Greek analysis now use the same sentence-policy component.
  Complete, contiguous source `sentence_id` runs take precedence over inferred
  punctuation; partial, non-contiguous, and cross-document IDs are rejected.
- Terminal token records and shared interface rows carry boundary policy,
  provenance, optional confidence, and source spans when alignments prove them.
- `GreekPipelineConfig.segmentation` continues to identify backend preprocessing:
  the baseline records `pyaegean-punctuation-v1`, and the published neural bundle
  records `pretokenized`. Per-call `sentence_policy` independently chooses document
  boundaries before backend analysis.

### Fixed

- Sentence rules protect dotted abbreviations and numeric forms, keep punctuation
  clusters source-aligned, and avoid treating restored, unclear, or lost typed
  punctuation as observed boundary evidence.
- Baseline parser output with a token-count mismatch now fails with a clear error
  instead of producing misaligned records.

## 0.45.0 (2026-07-14)

A model-independent Greek foundation release. It makes runtime configuration,
long-input handling, source alignment, documentary form state, CoNLL-U structure,
analysis provenance, and the supported Python API explicit while preserving the
published `grc-joint-v3` model and its measured results.

### Added

- `GreekPipeline` instances isolate neural, treebank, lemmatizer, reconciliation,
  and profile configuration. Existing module-level helpers delegate to a default
  instance, while independent pipelines can run concurrently without changing one
  another.
- Neural analysis now returns a versioned contract with task support, completion
  status, warnings, confidence availability, and an exact analysis receipt. The
  receipt records model and asset identity, tokenizer and preprocessing versions,
  provider, profile, normalization, segmentation, and long-input behavior.
- Long neural inputs have explicit `strict`, `partial`, and `windowed` policies.
  Strict mode refuses overflow, partial mode marks omitted analysis, and windowed
  mode recombines overlapping windows with deterministic ownership and a valid
  single-root dependency tree.
- `SourceAlignment` records exact source slices, offsets, whitespace, normalization,
  and stable token identity. JSON, SQLite, tabular/review exports, CLI/MCP views, and
  Greek pipeline records preserve or display the alignment where applicable.
- CoNLL-U documents now preserve comments, multiword-token ranges, empty nodes,
  enhanced dependencies, and MISC fields. Predictive helpers remain word-only and
  refuse unsupported copied structures rather than presenting gold data as a model
  prediction.
- `TokenFormState`, `FormSegment`, and `SourceMarkupRef` distinguish diplomatic,
  regularized, normalized, and exact analyzer-input forms while retaining supplied,
  unclear, and lost segments with semantic markup provenance. Token-carrier EpiDoc,
  CoNLL-U, JSON, SQLite, CSV/Parquet, review files, CLI/MCP output, the TUI reader,
  and typed-token Greek analysis carry the distinction. Existing downloadable
  inscription and papyrus assets retain their legacy aggregate reading status.
- Lemma output now separates resolution, source, confidence, human verification,
  and review recommendation. Lookup, edit-script, identity fallback, and user
  correction remain distinct through runtime and review surfaces.
- The neural bundle manifest is versioned and authoritative for compatible runtime
  configuration. Corrupt, incomplete, or incompatible bundles fail before activation,
  while the existing v3 bundle retains its established behavior.
- `scripts/api-manifest.json` defines the reviewed facade modules and explicit public
  symbols. `scripts/check_api.py` protects all grandfathered names and signatures,
  rejects unsupported facade drift, and provides an explicit reviewed snapshot path
  after a completed deprecation cycle.

### Changed

- `pyaegean[all]` now includes the neural runtime. Translation can select deterministic
  or neural local grounding explicitly; provider generation remains separate from the
  local linguistic analysis supplied as grounding.
- Checkpoint validation uses risk profiles for documentation, code, persistence, and
  public-API changes. Documentation guards cover wiki integrity, help output, surface
  parity, benchmark claims, corpus facts, and a strict documentation-site build.

### Fixed

- `scripts/check_benchmarks.py --help` now exits after displaying help instead of
  continuing into benchmark checks.
- Checkpoint output configures UTF-8 before replaying captured command output, so
  box-drawing and Greek text do not crash a legacy Windows console.
- Neural activation and annotation preserve prior runtime state after both success and
  failure, and typed-token annotation retains the established rule-based behavior when
  no neural backend is active.
- Review-file integrity distinguishes an absent optional form from an explicitly empty
  form, and SQLite schema migration rolls back completely if an append fails.

## 0.44.2 (2026-07-12)

A correctness and crash-safety patch for caches, downloads, derived artifacts,
New Testament evaluation, and user-written outputs.

### Fixed

- Analysis-cache keys now distinguish lists from tuples, accept heterogeneous
  dictionary keys, and bypass unkeyable custom fingerprints. Independent SQLite
  cache instances use WAL/busy waiting and degrade to a cache miss or skipped write
  instead of surfacing lock contention to an analysis.
- Cross-process file locks now use kernel ownership on a persistent sentinel rather
  than check-then-unlink leases, closing the stale-holder/successor ABA race. Direct
  URL downloads also serialize by destination and recheck the completed artifact.
- Downloads reject negative `Content-Length` values. Tar extraction rejects device
  and FIFO members and caps both member count and expanded size.
- Derived models, indexes, extracted members, CLI results, GeoJSON, calibration,
  workbench, and exploratory-result files now replace their destination atomically.
  Failed extraction swaps restore the prior directory, including recovery from an
  interrupted swap that left it under `.old`.
- Default NT evaluation and error analysis refuse the bundled two-chapter sample as
  benchmark gold. Translation and AI rarity gates consult only an already-cached,
  SHA-256-verified full NT and never trigger a download for optional grounding.
- A documentary evaluation that implicitly activates the neural pipeline restores
  the previous off state on both success and failure.

## 0.44.1 (2026-07-12)

A reliability patch for downloads, persistent caches, offline lexical grounding,
and repeated evaluation in long-lived sessions.

### Fixed

- Downloads stop after the declared `Content-Length` instead of probing the socket
  once more, and a reset after a complete close-delimited response is accepted only
  when the assembled file matches its pinned SHA-256. Unpinned mirror responses
  remain strict and resumable rather than accepting potentially truncated content.
- Dataset and response-cache lock files gained ownership tokens and live-holder
  heartbeats, preventing a long active download from being mistaken for an abandoned
  lock. Version 0.44.2 subsequently replaced that lease design with kernel ownership
  to close its remaining check/unlink race.
- Persistent AI response caches merge each writer's changed keys over the latest
  complete on-disk generation, so independent clients no longer erase one another's
  cached completions.
- Newly extracted datasets embed their source checksum inside the atomically swapped
  directory while retaining the compatibility sidecar. A process interruption between
  the directory swap and sidecar write can no longer make stale content look like a
  trusted legacy extraction after an asset is re-pinned.
- The translation rarity gate no longer treats the bundled John 1 + Philemon sample
  as a representative New Testament frequency corpus. When the full corpus is
  unavailable it reports no rarity signal and degrades to ordinary content glossing.
- `aegean greek eval --documentary` restores reconciliation, lemma-rescue, and
  paradigm state even when scoring fails, and preserves settings that were already
  active in a long-lived REPL session.
- SQLite corpus appends update only the affected full-text rows inside the append
  transaction instead of dropping and recreating the FTS table, so concurrent searches
  no longer fail intermittently with `database is locked`.

## 0.44.0 (2026-07-11)

A correctness and fidelity release: every evaluation fold's gold reviewed and
corrected where defective, the affected rows re-measured, and a set of fixes
across the documentary levers, the CLI, the data store, and the docs.

### Fixed — gold data and conversion

- **AGDT→UD conversion, leaf apposition.** The converter mapped a leaf `APOS`
  relation to `cc`, a label UD reserves for coordinating-conjunction words; it
  now emits `appos`. The AGDT-derived folds were rebuilt on the corrected
  conversion — 73 DEPREL cells in the PapyGreek fold (v3) and its orig layer
  (v2), 15 in the verse fold (v2), 54 across the dev tracks (v2) — with every
  other cell byte-identical. The shipped model was trained under the old
  convention and now shows the confusion as a measured error (see
  `docs/benchmarks.md` and the wiki Limitations page).
- **The verse fold is tragedy-only (v2).** The 3-sentence sliver previously
  labeled hexameter is the Maximus *prose paraphrase* (the sentences do not
  scan) and was removed; `--track hexameter` is rejected with the reason. 11
  malformed gold lemmas (Latin homoglyph vowels, LSJ citation-form tails) were
  repaired, and the build now validates every emitted lemma is a clean Greek
  headword.
- **The DBBE fold drops mis-tagged marker glyphs (v2).** 11 non-linguistic
  glyphs (crosses, dividers, a koronis) that the gold mis-filed as words are
  now excluded like their mirror class, and a standalone `+` segments by form,
  splitting one 59-token run-on: 825 sentences / 9,191 tokens. The register
  wording follows DBBE's documented 7th–15th c. scope.
- **Re-measured rows** (sequential, one-shot; unchanged-by-construction metrics
  came back byte-identical): verse tragedy lemma 87.89 / LAS 73.33 (LAS CI
  [69.75, 78.28]); DBBE UPOS 86.74 / XPOS 76.40 / UFeats 85.86 / lemma 76.71;
  PapyGreek LAS 79.85 (reg, both lever variants) and 77.61 (orig) — the
  apposition correction prices the trained-in `cc` reading into LAS honestly.

### Fixed — documentary levers

- The Greek numeral sign (keraia) is no longer folded into the elision-mark
  set, so Milesian numerals (δʹ, τʹ) can never be relabeled CCONJ by the
  coordinator reconciliation.
- Lemma-rescue results now carry their true SEED/PARADIGM evidence class on
  every surface (pipeline records, explain, review export, `lemmatize_sourced`)
  instead of an incorrect IDENTITY "surface form unchanged" note, via the
  additive `SentenceAnalysis.lemma_source_override` channel; default-off output
  is byte-identical.
- `aegean greek eval --documentary` now activates the paradigm table, so the
  CLI reproduces the registry `documentary_full` lemma row; the rescue-cascade
  docstring names the real tiers (seed → paradigm).

### Fixed — CLI, evaluation entrances, data store, TUI

- `greek eval verse --drift` is rejected before any model load; `eval
  papygreek` and `eval nt` reject the ud-only `--bootstrap`/`--by-genre`
  instead of silently ignoring them; the `--batch-size`/`--documentary` option
  help lists the real target sets.
- An empty fold or empty track raises a clean error naming the track and
  source instead of a misleading evaluator crash.
- `greek work --ref` prints a follow-up that actually works for
  milestone/nested/range/comma refs, and a comma-list hint carries the full
  ref.
- `aegean data list` now counts, and `aegean data remove` now reclaims, the
  decompressed CoNLL-U the evaluation folds materialize (previously invisible
  and orphaned); `data fetch --version` prints a load hint only for corpora
  `aegean.load(version=)` supports; `aegean.load("sigla", version=...)` no
  longer falsely reports that no historical pins exist.
- The TUI console's `:exit`/`:quit`/`:q`/`exit`/`quit` now leave the console.

### Documentation and attribution

- NOTICE gains the verse-fold (UNESP Trees, CC BY-SA 4.0) attribution and
  corrects the DBBE author initial (C. Swaelens).
- Bekker addressing is documented with its real semantics: a line ref opens
  the span to the next *marked* line (Perseus marks every ~5th line; unmarked
  line numbers resolve to nothing), `1447a` is a page-column, and the whole
  page is the comma list `1447a,1447b`; the worked example cites the *Poetics*
  (tlg0086.tlg034). The MCP `greek_work` docstring documents milestone and
  comma-list refs.
- The orig-layer framing states the reg/orig pair measures raw documentary
  usage (orthography plus a minority of morphosyntactic regularizations); the
  Data-and-Provenance table carries every fetchable dataset, with a guard
  pinning table completeness.

## 0.43.0 (2026-07-11)

Two more firsts for the evaluation record: the cost of scribal orthography,
measured, and Byzantine verse.

### Added
- **The diplomatic-orthography row**: `greek.evaluate_on_papygreek(layer="orig")`
  (CLI: `aegean greek eval papygreek --layer orig`) scores the same 1,696
  sentences and gold as the published PapyGreek row, with the FORM column
  carrying the scribes' actual spellings (1,637 tokens differ: itacism,
  vowel-quantity confusion, nasal assimilation). Measured once, sequentially:
  UPOS 90.00 / UFeats 85.90 / lemma 81.80 / UAS 84.33 / LAS 77.64 against the
  regularized row's 91.05 / 88.57 / 86.13 / 85.71 / 79.89 — the pair isolates
  what documentary orthography costs, and lemma composition takes the largest
  hit. The fold is a pure form-swap of the regularized one (gold columns
  byte-identical, leakage re-checked on the diplomatic forms).
- **Byzantine verse tagging**: `greek.evaluate_on_dbbe()` (CLI: `aegean greek
  eval dbbe`) scores the pipeline against the DBBE gold standard (Swaelens,
  De Vos & Lefever, Language Resources and Evaluation 2025; CC BY 4.0): 822
  sentences / 9,203 tokens of unedited medieval book epigrams in scribal
  orthography, gold POS and lemma, leakage-checked. Measured once: UPOS 86.61 /
  XPOS 76.34 / UFeats 85.87 / lemma 76.74, with the mapped-tagset and
  Attic-lemma caveats stated. Tagging only: the gold carries no trees.
- **Margin-milestone addressing**: `--ref 17a` opens a Stephanus sub-page and
  `--ref 1447a10` a Bekker line, read generically from each edition's declared
  milestone markup; every existing ref form is unchanged.
- **Parity machinery hardening**: notebook coverage claims are now
  machine-checked (each carries a marker asserted to appear in a code cell of
  the named notebook), and the documentation site's navigation joined the
  tracked surfaces.

### Fixed
- The catalogue build script's GitHub-token gate now requires an exact
  `api.github.com` hostname rather than a substring match, and a legacy test's
  deprecated `tempfile.mktemp` calls are replaced; seven code-scanning false
  positives were dismissed with written justifications.

## 0.42.0 (2026-07-11)

The first leakage-clean tragedy evaluation.

### Added
- **The verse fold** (`greek.evaluate_on_verse`, CLI `aegean greek eval verse
  [--track tragedy|hexameter|all]`): gold manual dependency annotation of
  Euripides, *Bacchae* 1-169 from the UNESP Trees project (Perseids/Arethusa,
  CC BY-SA 4.0), found by a deep multi-avenue search after every known treebank
  avenue had been verified blocked, converted through the same machinery as every
  other fold, and leakage-checked sentence-by-sentence in its build (0 overlaps
  with training; the only Euripides the model trains on is *Medea*). The gold
  survived a close scholarly spot-check before any number was pinned. Measured
  (CPU sequential): tragedy UPOS 90.88 / UFeats 92.79 / lemma 87.35 / UAS 79.73 /
  LAS 73.06 over 735 tokens, with wide bootstrap confidence intervals disclosed —
  a small-sample genre-conditioned datapoint, never a headline number, and the
  first honest tragedy accuracy anywhere. The substantive finding: tragedy parses
  ~7 LAS points below documentary papyri — poetic word order and hyperbaton are
  materially harder than either prose register. A directional sliver of didactic
  hexameter (Maximus, 25 tokens) rides along as a footnote, deliberately unpinned.

## 0.41.0 (2026-07-11)

The documentary levers land with their measured rows, SigLA grows to 802
documents, and the work-addressing, lexicon, and distribution surfaces each take
a step.

### Added
- **Opt-in documentary levers, measured**: `greek.use_documentary_reconciliation()`
  relabels the closed coordinator class (καί, δέ, τε, ...) only where the model
  emitted the always-wrong `X` reading, and `greek.use_documentary_lemma_rescue()`
  consults the curated offline tiers (seed, then the guarded paradigm table; the
  ending rules deliberately excluded by measurement) for lemmas the model honestly
  left unresolved, each rescue carrying its own evidence class. Both are off by
  default and byte-identical when off; CLI: `greek eval --documentary`. Measured
  once, sequentially, on the pinned PapyGreek fold: reconciliation lifts the
  opt-in row to UPOS 94.31 / XPOS 80.06 (from 91.05 / 76.76) with every other
  metric byte-identical; adding the rescue lifts lemma to 86.36. On the literary
  dev fold the conservative reconciliation touched 9 of 22,135 tokens with zero
  regressions; the aggressive variant exists but is documented against. The
  published baseline row is unchanged: the levers earn their own registry rows.
- **SigLA corpus v4**: 802 documents (up from 781), adding the Thebes, Khania,
  Gournia, Knossos, Phaistos, and Kea pieces of the newer SigLA release; homophone
  subscripts and apparatus classification carried through; one upstream word
  re-division (PE 2) accepted as legitimate re-editing.
- **Citation-scheme awareness for fetched works**: `greek.citation_scheme(work)`
  reports how an edition addresses itself (book.line for verse, Stephanus sections
  for Plato, book.chapter.section for prose historians), read from each TEI's own
  declared structure; a `--ref` that does not resolve now names the work's scheme
  and suggests the exact comma list for sibling ranges.
- **The Suda** joins the lexicon registry as a deep-link entry (the Suda On Line;
  translations CC BY-NC-SA, the Adler Greek text public domain) alongside
  Montanari and Slater: 9 registry lexica (6 hosted, 3 deep-link).
- **The browser demo joins the documentation site's table of contents** ("Try it
  in your browser" on https://ryanpavlicek.github.io/pyaegean/), and a conda-forge
  recipe is prepared for submission.

### Fixed
- The four TEI choice-corpus builders share one extraction driver again
  (`choice_prefer` threaded through `build_greek_corpus`, byte-identical output
  proven against the conformance battery); the export-format registry is a single
  canonical constant (`aegean.io.EXPORT_FORMATS`); the paradigms, phonetic-compare,
  and visualization capabilities gained their missing notebook coverage.

## 0.40.0 (2026-07-11)

Documentary-Greek research infrastructure, a measured cross-script null result,
surface parity across the demo/MCP/notebooks, and the anti-drift machinery that
keeps every surface current from now on.

### Added
- **The PapyGreek convention decomposition**: `greek.papygreek_convention_report()`
  (CLI: `aegean greek eval papygreek --drift`) reproduces the published
  documentary-Koine row exactly, then partitions its two weakest cells. Of the
  8.95-point UPOS gap, 5.13 points (57.3% of all UPOS errors) sit on the
  coordinator class alone (καί, δέ, τε: tagged under three incompatible
  conventions in the merged training treebanks); of the 23.24-point XPOS gap,
  13.62 points are convention or encoding, and forgiving them XPOS would read
  90.38%. A measurement decomposition only, mirroring the PROIEL one; the
  published row is unchanged.
- **PapyGreek dev folds** (`papygreek-dev-tagging`, `papygreek-dev-parse`;
  `greek.evaluate_on_papygreek_dev(track=...)`): document-disjoint experiment
  data built only from the source documents that contributed nothing to the
  pinned test fold, leakage-refiltered against the training set. Improvement
  experiments validate here; the test fold is measured once per shipped change
  and never fitted to. These folds never produce a published number.
- **Cross-script Procrustes alignment, shipped with the null it measured**
  (`analysis.align_scripts`, `rank_known_pairs`, `recover_identity`; exploratory):
  aligning Linear A to Linear B distributional sign embeddings recovers **no**
  correspondence signal at this corpus scale — leave-one-out over the 53
  chart-shared sign pairs scores top-1 0.000 with top-5 at chance, while
  self-alignment recovers 90.1% (the misses are distributional twins), so the
  failure is absence of signal, not broken machinery. The module ships as the
  instrument that measured that negative result; a test pins the null so any
  change that suddenly "finds signal" fails loudly and demands scrutiny. Every
  output is exploratory-labelled and nothing here reads a sign.
- **A completion dropdown in the TUI command console**: typing opens a floating
  list of matching commands with a one-line description each (`↑`/`↓` pick,
  `Tab`/`Enter` complete, `Esc` closes); the inline ghost-text still previews the
  best match, history recall and the console's key-safety rules are unchanged,
  and no new dependency was added.
- **Two MCP tools** (fifteen → seventeen): `greek_explain` (each token's lemma
  evidence class in plain language) and `corpus_diagnose` (the corpus health
  report as structured data). **Six browser-demo cards** (explain, diagnose,
  apparatus summary, Linear B dossiers, seriation, allograph groups) and the
  0.34–0.39 features woven into all four notebooks.
- **Anti-drift machinery**, so surfaces stop lagging features: a surface-parity
  manifest (`scripts/surface-manifest.json`) where every capability declares
  covered-or-excluded per surface, enforced by a guard test in both directions;
  an EpiDoc extraction conformance battery run against every epigraphy builder
  (the reading-fusion class can never ship silently again); registry
  exhaustiveness tests (evidence classes, lexica, providers, corpus ids, export
  formats enumerated live against every consumer surface); a corpus-facts
  registry pinning document/token counts to their doc echoes, re-measured weekly;
  and `aegean.data.fetch_text`, the shared fetch-and-materialize helper carrying
  the capped decompress, atomic write, and re-pin freshness stamp (with
  `expect_gzip` so a declared-gzip asset refuses a corrupt body instead of
  materializing it). Contribution rules for both are in CONTRIBUTING.

### Fixed
- The machinery caught its first drift while being built: the CLI cheatsheet's
  export-format table had omitted the RDF formats since 0.36.0 (now listed and
  pinned), a stale SigLA version label, and two evidence-class enumerations that
  had fallen behind the registry.

## 0.39.0 (2026-07-11)

The correctness-and-fidelity release: nine data assets rebuilt against their
sources, the paradigm backend made honest on ambiguous forms, and a wide set of
fixes across the export, visualization, and data-management surfaces.

### Fixed
- **The paradigm backend no longer serves arbitrary picks as grounded lemmas.**
  With `use_paradigms()` active, a form matching more than one distinct paradigm
  lemma (φωτός is the genitive of both φώς and φῶς), or a capitalized surface
  (Πέτρος is not the common noun πέτρος), now falls through as an honest miss
  instead of a confident wrong answer, and the nominal table is consulted only
  where the guarded ending rules do not already resolve the form (so ἔχει stays
  the verb ἔχω, never the noun ἔχις). Paradigm hits report their own evidence
  class, `LemmaSource.PARADIGM` (previously folded into `seed`), and
  `greek explain` names the UniMorph table. Re-measured on the full NT: the
  backend's lift is now 66.98% → 71.21% (was 71.96%), trading 0.75 accuracy
  points to cut confidently-wrong grounded lemmas from 742 to 218 and
  wrong-where-the-baseline-was-right from 420 to 10.
- **`grc-paradigms` rebuilt (v2)** with a gender cross-check: noun genders are
  now validated against attested treebank data plus a curated feminine
  second-declension list (Smyth §230 N.), fixing the textbook feminines the
  UniMorph source mislabels (ἡ δοκός, ἡ κιβωτός, ἡ ψῆφος, ἡ γνάθος) and filling
  unambiguous -μα neuters: 4,338 gender cells corrected or filled across 284
  lemmas.
- **The Autenrieth index rebuilt (v2)**: lemma keys and headwords now derive from
  each entry's own `<orth>` Beta Code behind a well-formed-Greek gate, recovering
  22 core Homeric headwords the malformed Perseus key attributes had made
  unreachable (δῆμος, δηλέομαι, δημοβόρος, δήν, δηρός, ἐύξεστος, …) and giving
  δῆλος "clear" back its own entry beside the island Δῆλος; the vowel-quantity
  placeholder no longer corrupts 82 definition bodies; both Autenrieth homographs
  of δέω merge under one reachable entry; Greek inside citations converts. 9,660
  lemmas.
- **The SigLA corpus rebuilt (v3)**: the homophone signs AB76 RA₂, AB29 PU₂, and
  AB66 TA₂ are now decoded from SigLA's own transliteration pairs instead of
  collapsing onto plain RA/PU/TA (64 attestations; HT 1 reads QE-RA₂-U, agreeing
  with GORILA and the bundled corpus). Apparatus statuses unchanged; the loader's
  apparatus note now states SigLA's actual reading categories.
- **Five epigraphy corpora rebuilt** to fix apparatus-handling defects in the
  extraction: EDH (v3) no longer bakes `#`-joined parallel word-forms into token
  text (132 tokens across 81 inscriptions now carry one reading with the variants
  as alternates), and isicily / iip / iospe / igcyr (v3) no longer fuse both
  members of a TEI `<choice>` into one garbled token — the preferred member is
  kept (expansion over regularization over correction, the same policy the DDbDP
  extractor has always used), correcting 725 documents across the four corpora
  and tightening reading statuses the discarded member had wrongly inflated.
- **The PapyGreek fold rebuilt (v2)**: five gold lemma cells carrying PapyGreek's
  internal numeral-value annotation (`β|num:2|`) reduce to the plain letter-numeral
  reading; the registry lemma cell moves 86.11 → 86.13 (+5 tokens, every other
  metric byte-identical). The fold's decompressed cache now records which archive
  it came from, so a re-pinned fold re-extracts instead of silently serving the
  old gold, and the extraction is atomic.
- **`viz.parse_period` reads cross-era and abbreviated dates correctly**: each
  side of a range now parses its own era, so "27 BC - 14 AD" spans the epoch
  instead of collapsing to a BCE range, "5th cent. BCE" is a century rather than
  the year 5, and Roman-numeral century ranges ("II-III century C.E.") span both
  centuries — 904 shipped documents' chronologies corrected, with no previously
  parsed string lost.
- **`analysis.seriate` is now deterministic and input-order-invariant**: the
  ordering comes from the Fiedler eigenvector of the similarity Laplacian
  (a pure-Python Jacobi eigensolver) with a canonical direction, so any
  permutation of the same assemblages recovers the same sequence up to the
  documented reversal; the old power iteration could return a different, wrong
  ordering depending on input order.
- **GEXF export is readable by networkx again**: `analysis.graph.to_gexf` writes
  the 1.2draft namespace both networkx and Gephi accept (the 1.3 namespace made
  `networkx.read_gexf` reject every export).
- **Geo aggregation collapses whitespace variants of one site**:
  `geo.to_geodataframe(level="site")` and `geo.word_distribution` aggregate by
  the normalized gazetteer key and emit the canonical site label (line-split
  spellings previously produced duplicate rows at identical coordinates), and
  `viz.plot_findspots` resolves through the same index so its counts agree.
- **`analysis.hands.dossiers` requires a Linear B corpus**: running it against
  another script's corpus invented archival series from unrelated designations
  ("IG XV 1" is not a series); it now raises a clear error, and the hands/dossier
  docstrings state that hand counts are editorial attribution strings, not a
  census of scribes.
- **Versioned cache entries are now managed disk**: `aegean data list` counts
  `name@version` entries fetched via `--version`, `data remove NAME` reclaims
  them, and `data remove NAME --version v1` removes one pinned version
  surgically (previously they were invisible and unremovable).
- **RDF export hardening**: an unusable `base_uri` (a space or control character)
  raises a clear error instead of producing a JSON-LD document that silently
  drops every node; a Trismegistos subject is minted only from a note that is
  exactly a TM identifier (never from prose that mentions one); DDbDP subjects
  use the `http://papyri.info/ddbdp/…` scheme papyri.info's own linked data uses
  (the https form was a distinct RDF node co-referring with nothing); a corrupt
  cached DDbDP URI map degrades to Trismegistos subjects with a warning instead
  of raising.
- **Citations deduplicate comma-list references**: loading a work with a
  duplicated passage reference no longer repeats it in `cite()`.
- **Reviewer names containing commas survive the review merge**: merged
  provenance credits "Smith, John" as one reviewer, not two.
- **A corrupt or partial bundled calibration file** raises the calibrated-
  confidence error with reinstall guidance instead of leaking a JSON traceback,
  and the docs now state precisely which lemmas carry a calibrated confidence:
  the neural pipeline's calibrated lemma confidence covers its full composition
  including the internal training-form lookup (that inclusion is the calibration
  target); lemmas resolved by an offline lexicon backend carry none.
- **Benchmark prose corrections**: the PapyGreek section now discloses that
  scoring is on the regularized spelling layer and gives the full exclusion
  accounting (1,696 of 4,557 sentences kept, with the manifest published), and
  the PROIEL decomposition names its quantities correctly (36.5 is the total LAS
  gap; 19.0, the label-only component, is the UAS-to-LAS gap).

### Added
- `greek.LemmaSource.PARADIGM`, `ParadigmLexicon.lemma_options` (the distinct
  lemma set for a form), `aegean.data.versioned_bytes` /
  `aegean.data.versioned_entry_paths`, and `aegean data remove --version`.

## 0.38.0 (2026-07-11)

The research-workflow release: collaborate on corrections, pin exact data versions,
and the first documentary-Greek parsing evaluation.

### Added
- **The first documentary-Greek dependency evaluation**: `greek.evaluate_on_papygreek()`
  (CLI: `aegean greek eval papygreek`) scores the neural pipeline on a new fold of
  1,696 sentences / 24,105 tokens of papyrus letters and petitions, converted from
  the PapyGreek Treebanks (CC BY-SA 4.0) through the same AGDT scheme the model
  trains under. Measured: UPOS 91.05 / UFeats 88.57 / lemma 86.11 / UAS 85.71 /
  LAS 79.89 — scheme-matched out-of-domain parsing runs ~16 LAS points above the
  convention-capped PROIEL row. The fold is leakage-checked sentence-by-sentence
  against the training set: 354 overlapping sentences were found (Pedalion ships a
  documentary-papyri subset) and excluded.
- **The PROIEL convention decomposition**: `greek.proiel_convention_report()` (CLI:
  `greek eval ud --fold proiel --drift`) turns the qualitative "convention-capped"
  caveat into measured numbers — 24.2 of the 40.6 UFeats gap points are feature
  types the model's scheme cannot emit, and 19.0 of the 36.5 LAS gap points are
  correctly-attached words labeled by a different convention, 68.9% of them in five
  systematic relation pairs. A measurement decomposition only: the published rows
  are unchanged.
- **Multi-reviewer corrections**: `io.merge_review_tables` and
  `aegean review merge A.csv B.csv --corpus X` combine several reviewers' copies of
  a review export, applying agreements and surfacing per-field conflicts (never
  silently resolving them); the applied corpus stamps every contributing reviewer.
- **Versioned data pinning for reproducibility**: `aegean.load(id, version="v1")`
  and `aegean data fetch <name> --version v1` fetch the superseded historical pin
  of a dataset (the six 0.29-era epigraphy corpora keep their v1 assets hosted,
  with the original checksums recovered and enforced), so a paper can name and
  re-fetch the exact data snapshot it used.
- **Autenrieth's Homeric Dictionary** joins the lexicon registry
  (`use_lexicon("autenrieth")`): 9,663 lemma entries from the Perseus digitization
  of the 1891 public-domain text, homograph senses merged rather than dropped.
  Slater's Lexicon to Pindar stays deep-link-only: the 1969 De Gruyter edition
  remains in copyright (verified against the publisher's live catalogue).
- **Richer work citations**: `load_work` refs accept comma lists ("1.1,1.5"), and
  the exact canonical citation of what was selected ("Homer, Iliad 1.1-1.50") now
  travels in provenance, `corpus.cite()`, and a `cite it:` line on `greek work`.

## 0.37.0 (2026-07-11)

Deeper Aegean scholarship: apparatus everywhere, scribal hands, and an offline
paradigm backend for Greek.

### Added
- **The offline paradigm backend**: `greek.use_paradigms()` fetches a nominal
  paradigm table derived from UniMorph Ancient Greek (CC BY-SA, 25,643 forms) and
  slots it into the offline lemmatization and morphology cascade, covering the
  irregular and third-declension nominals the ending rules cannot (γυναικός → γυνή,
  πατράσι → πατήρ, ὕδατος → ὕδωρ, each verified against Smyth). Measured on the full
  Nestle 1904 NT: offline lemma accuracy 66.98% → 71.96% with the backend active
  (7,251 corrections, 420 regressions on genuine lexical ambiguities; evidence:
  `training/results/paradigms-lift-2026-07-11.json`).
- **SigLA editorial apparatus decoded**: the fetched 781-document SigLA Linear A
  corpus now carries `ReadingStatus` like every other corpus — 309 tokens across 205
  documents that previously loaded as securely read are now honestly UNCLEAR, with
  each SigLA marker's meaning verified against the project's own documentation and
  the composition notation deliberately left out of certainty judgments.
- **A uniform apparatus surface** (`core.apparatus`): `alt_readings()` lists every
  token carrying alternate readings in one shape across corpora, and
  `apparatus_summary()` profiles a corpus's editorial state; `corpus.diagnose()` now
  counts alternate-reading tokens in its status profile.
- **Scribal hands and dossiers for Linear B** (`analysis.hands`): documents grouped
  by the editors' hand attributions, per-hand profiles, and site-and-series dossiers
  (the standard Mycenological working unit) over the DAMOS metadata — 291 hands and
  212 dossiers in the full corpus. CLI: `aegean analyze hand`, `analyze dossiers`.
- **Cypriot analysis parity** (`scripts.cypriot.analysis`): a syllabary profile
  against the ICS grid (54 of 55 signs attested in IG XV 1; the gap is XA) and a
  Greek-bridge coverage report by editorial status. CLI: `analyze syllabary`,
  `analyze bridge`.
- **Seriation and chronology tools** (`analysis.seriation`, exploratory):
  Brainerd-Robinson similarity with a deterministic ordering for assemblage
  hypothesis-generation, and `chronology()` parsing date metadata into spans with
  the unparsed fraction always reported.
- **Allograph reporting** (`analysis.allographs`, exploratory): the variant-form
  groups the sign inventories actually encode (homophone numbers like RA/RA₂,
  catalogue suffixes), with the line drawn explicitly at palaeographic allography,
  which the data does not carry.

## 0.36.0 (2026-07-11)

Linked Open Data, a wider gazetteer, and new ways to see the corpora.

### Added
- **Linked Open Data export**: `aegean export <corpus> -f ttl` (Turtle) or `-f jsonld`
  (JSON-LD), `io.to_rdf` in Python. Subject URIs come from the authoritative
  identifiers in the data, never invented: DDbDP documents get their real papyri.info
  URIs (via a new fetched identifier map harvested from papyri.info's own source data;
  57,331 of 57,331 documents resolve), EDH documents their Trismegistos URIs, I.Sicily
  its project URIs; documents without an external identifier use a documented `urn:`
  fallback or your `--base-uri`. Every document carries Dublin Core terms, WGS84
  coordinates where a findspot is known, and the corpus license as a machine-readable
  triple, so NonCommercial obligations travel with the data.
- **The find-site gazetteer now covers the Greek epigraphy corpora**: 38 new
  find-places (94 sites total, 78 Pleiades-linked), each verified against its live
  Pleiades representative point before linking; `aegean geo` yields rows for
  isicily/igcyr/iospe/iip/edh, and find-place labels split across lines in the source
  now resolve to their gazetteer row. Coverage and the deliberately-unlinked cases
  (modern names, medieval places, region-level labels) are recorded with the data.
  Pleiades (CC BY) is now credited in NOTICE.
- **Sign co-occurrence graph export** (`analysis.graph`): GEXF and GraphML writers for
  pattern-hunting in Gephi or networkx, using the same counting conventions as the
  existing co-occurrence analysis; exploratory framing carried in the module.
- **Three new plot kinds**: `aegean plot findspots` (find-site map), `plot timeline`
  (documents over parsed date ranges, with the unparsed fraction stated on the
  figure), and `plot signnet` (the co-occurrence network). Each accepts
  `backend="plotly"` for an interactive version via the new `[viz-interactive]` extra;
  matplotlib remains the default.

## 0.35.0 (2026-07-11)

Calibrated confidence for the neural pipeline: a number you can trust, or no number at all.

### Added
- **Per-token calibrated confidence** on the neural pipeline's UPOS and lemma
  predictions: `greek.use_calibration()` loads the shipped calibration, then
  `greek.pipeline(text, with_confidence=True)` (CLI: `--confidence` on `greek pipeline`
  and `greek explain`; the TUI shows the column when active). The number is an estimate
  of the probability the prediction is correct, produced by temperature scaling — the
  raw softmax is deliberately never exposed, and asking for confidence without a
  calibration is an error, not a fallback. The calibration is fitted on the UD Perseus
  dev fold only and its quality is measured: expected calibration error 1.11% (UPOS)
  and 6.29% (lemma) on the test fold, protocol and caveats in the Benchmarks pages.
  Lemmas resolved by an offline lexicon backend carry no model confidence; their
  evidence class (`attested`/`seed`) speaks for them. Within the neural pipeline the
  calibrated lemma confidence covers the model's full composition, including its
  internal training-form lookup: that inclusion is what the calibration is fitted
  on. New public API: `use_calibration`,
  `disable_calibration`, `Calibration`, `fit_temperature`, `ece`,
  `temperature_softmax`, `top1_confidence`, `UncalibratedConfidenceError`; the fitting
  and measurement protocol ships as `training/calibrate_temperature.py` with its
  evidence file.

## 0.34.0 (2026-07-11)

Finding your way in, and seeing what the tools did: a documentation, diagnostics, and
explainability release.

### Added
- **A researcher-facing documentation site.** The project site
  (<https://ryanpavlicek.github.io/pyaegean/>) now opens with a landing page: a
  60-second quick start, a find-your-path router by kind of researcher, and the install
  matrix, with the API reference as a section beside it. The README gained the same
  quick start for researchers near the top.
- **Three persona walkthrough notebooks** under `notebooks/`: the epigraphist
  (inscriptions, apparatus, export, citation), the New Testament reader (gold
  annotations, glossing, the review loop end to end), and the Aegean researcher (all
  four scripts, accounting, the honesty framing). Every offline cell executes in CI;
  heavy cells sit behind the notebooks' one `RUN_HEAVY` switch.
- **`greek.explain_pipeline(text)`** (CLI: `aegean greek explain`) renders a
  plain-language account of what the pipeline did to each token — the lemma's evidence
  class, whether it needs review, and what that class means — derived from the same
  records `pipeline()` returns, never a re-run. Deliberately class-based: there are no
  confidence numbers.
- **`corpus.diagnose()`** (CLI: `aegean doctor corpus <id> [--deep]`) builds a corpus
  health report: reading-status profile, accounting reconciliation (a discrepancy is
  reported as a lead, never a verdict), numeral-pattern anomalies, provenance and
  citation completeness, review state, and (deep) sign-frequency outliers; renders to
  terminal, Markdown, or a DataFrame for sharing.
- **Library logging.** `aegean.set_verbosity("info")` (callable or context manager,
  env `PYAEGEAN_LOG`) turns on stdlib logging of the fetch/load/build journey. Off by
  default, never logs corpus text, and adds nothing to import time.
- **Progress everywhere long.** `progress=` callbacks (and TTY live lines on the CLI)
  now cover the whole-corpus SQLite materialise (`aegean.load("ddbdp")` end to end),
  `to_sqlite`/append, token-level CSV/Parquet export, corpus annotation, and dataset
  downloads (byte-level, resume-aware) with archive extraction. Defaults change
  nothing: every output is byte-identical with the callback off.
- **A public-API stability gate.** `scripts/check_api.py` diffs the package's public
  surface (2,200+ names, statically analyzed) against a committed baseline in CI;
  removing or changing a public signature without its deprecation cycle now fails the
  build. A new wiki **Data Model** page documents the object hierarchy, annotation
  conventions, persistence contracts, and extension invariants for advanced users.

### Fixed
- **The rule lemmatizer no longer fabricates lemmas for contracted `-οῦς` nouns.**
  Ἰησοῦ was confidently lemmatized to the non-word Ἰησός (and the κύριος paradigm to
  the mis-accented κυρίος); curated seeds now resolve Ἰησοῦς, νοῦς, χοῦς, and the
  κύριος family correctly, and the contract-noun genitive can no longer strip to a
  fabricated form (regular genitives like Χριστοῦ → Χριστός are untouched). Measured
  on the full Nestle 1904 NT: +1,135 tokens corrected, zero regressions; the offline
  NT lemma figure moves 66.16 → 66.98 (evidence re-measured through
  `scripts/check_benchmarks.py`).
- **Error messages tell you what, where, and what to do next.** An EpiDoc directory
  import now names the file (not just the directory) a parse error lives in, a missing
  path says `no such EpiDoc file:` like its siblings, and a source that yields zero
  documents is an error instead of a cheerful empty corpus. A failed download no
  longer claims a partial file was kept when nothing was downloaded, and says what is
  and is not in your local store. `aegean.load` gained the same case-folding and
  did-you-mean the other entry points had. Activating the neural pipeline without the
  `[neural]` extra says to install it before any download starts, and a corrupt cached
  model bundle explains how to re-fetch instead of leaking an onnxruntime traceback.
  Opening a file that is not a pyaegean corpus database, and querying with an unknown
  field, both name the problem and the fix at the library level, matching what the CLI
  already did.

## 0.33.0 (2026-07-10)

GPU execution and batched inference for the neural backends.

### Added
- **The neural pipeline uses a GPU automatically when one is available.** Both neural
  backends (the joint pipeline and the GreTa lemmatizer) select their ONNX Runtime
  execution providers through one shared resolver: CUDA preferred, then DirectML,
  always with the CPU as fallback; a plain CPU install behaves exactly as before.
  `PYAEGEAN_ORT_PROVIDERS` (comma-separated provider names) overrides the selection
  as given, and an unavailable name is a clean error listing what the install offers.
  New `greek.neural_backend_info()` reports the available and active providers.
- **Batched neural inference.** `greek.analyze_sentences(sentences, batch_size=N)`
  runs N sentences per model call; the evaluators accept the same `batch_size`
  (`evaluate_on_ud`, `evaluate_by_genre`, `evaluate_on_nt`, `heldout.score`; CLI:
  `aegean greek eval ud --batch-size 32`). Verified prediction-identical to
  sequential inference, CPU and GPU, on a fixed verification set (evidence:
  `training/results/gpu-verify-2026-07-10.json`): zero token-level differences,
  with CPU batching about 4x faster and a data-center GPU at `batch_size=32` about
  90x. Every published benchmark number remains measured on the CPU provider,
  sequentially; the recorded protocol is unchanged.

## 0.32.0 (2026-07-10)

A correctness and end-to-end reliability release: the full user journeys (import your own
text, annotate, review, export, re-read; fetch, analyze, export) are now tested as whole
lifecycles, and the defects that audit surfaced are fixed.

### Fixed
- **The review loop kept every machine value through the documented CLI journey.**
  `review apply` gained `--annotate` (and the backend flags), matching `review export`; the
  export's printed next-step command includes it. `from_review_table` now takes each
  `<field>__pred` from the table's own `pred_*` column (the value the reviewer actually saw),
  so the audit trail survives even against a freshly-loaded corpus.
- **Corrections can no longer land on the wrong word.** `from_review_table` verifies each
  row's exported token text against the token it matched and raises a clear error on a
  mismatch (a changed or wrong corpus), on duplicate rows with conflicting corrections, and
  on corrected rows that match no token. A malformed CSV surfaces as a clean error. A
  morphology correction lands on the same key that supplied the prediction (`morph` or UD
  `feats`), tokens without a position are no longer exported (their corrections could never
  round-trip), and cells that would execute as spreadsheet formulas are neutralized on export.
- **The neural lemmatizer no longer emits the `_` placeholder as a lemma**, and an
  edit-script identity result on an out-of-vocabulary form is now honestly
  `identity`/needs-review rather than a grounded `neural` lemma, restoring the pre-0.28
  calibration (a genuine identity lemma from a lookup, e.g. a nominative, stays resolved).
  `missing_forms` now sees unresolved forms under the neural pipeline. Measured on the full
  recorded protocol (evidence: `training/results/lemma-remeasure-2026-07-09.json`): NT lemma
  87.03 → 87.96 (+0.93, about 1,280 of 137,303 tokens), UD Perseus lemma 94.29 → 94.27
  (AGDT capitalizes proper-noun lemmas), UD PROIEL lemma 90.50 → 90.51; UPOS/UAS/LAS are
  untouched by the fix. The neural benchmark rows are re-pinned to the same run, which also
  trues up a few hundredths of pre-existing evaluation-path drift on the non-lemma cells.
- `evaluate_by_genre(bootstrap=True)` no longer aborts on a genre bucket with a single
  sentence; the bucket falls back to point scores and stays flagged thin.
- **Token-level CSV/Parquet/DataFrame exports carry the editorial reading status** (a
  `status` column), so a spreadsheet can tell a restored reading from a securely-read one.
- Merging corpora (`aegean.combine`, multi-corpus databases) keeps `edition_fidelity` when
  every input agrees on one value.
- The `local` AI provider: the missing `pyaegean[local]` extra now exists, the response
  cache keys on the endpoint URL (two local servers can host different models under one
  name), and the TUI reader's translate option recognizes a configured keyless local server
  and routes to the first configured provider rather than assuming Anthropic.
- An extract dataset fetched from an env-override mirror now records what was extracted, so
  a later pinned fetch re-validates it; `aegean doctor` reports a leftover superseded
  extraction (`<name>.old`) with the right fix.
- The text profiler bounds hostile combining-mark floods and no longer mistakes ordinary
  English, file paths, or source code for Beta Code (accent markers must follow vowels, and
  real Beta Code density is required).
- The TUI now marks unresolved/identity lemmas with their evidence class in the workbench
  pipeline tab and the reader's offline/neural analyses, matching the CLI.
- The browser demo's text inputs no longer collapse to a sliver on the cards that pair a
  dropdown with an input (the Greek bridge, sign inventory lookup, EpiDoc export, and cite
  cards): a dropdown now sizes to its content and the input takes the remaining row.

### Added
- **Progress reporting on the long evaluations.** `evaluate_on_ud`, `evaluate_by_genre`,
  `evaluate_on_proiel`, `evaluate_on_nt`, `heldout.score`, and `pipeline_conllu` accept a
  `progress(done, total)` callback, and `aegean greek eval` paints a live per-sentence
  progress line on the terminal (TTY only, so piped and scripted runs stay clean). The
  whole-NT evaluation runs about an hour on plain CPU; it no longer runs silently.
- **`aegean greek missing-forms CORPUS`**: the unresolved word forms of a corpus, ranked by
  frequency, as candidates for a sourced contribution (the CLI face of
  `greek.missing_forms`).
- `from_workbench_export(..., script_id=)` so a non-Linear-A corpus re-imports under its own
  script; the workbench and EpiDoc docs now state exactly what those formats do and do not
  preserve (annotations and, for workbench, reading status are not carried).
- **End-to-end journey tests** covering import → annotate → review → export → re-read across
  formats, and a real fetch → registered loader → analyze → export → re-read chain.

## 0.31.0 (2026-07-09)

Run the AI layer on a model on your own machine, with no API key or network.

### Added
- **Local model provider.** A new `local` AI provider talks to any OpenAI-compatible server, so
  the model runs on your own machine: **Ollama** (the default, `http://localhost:11434/v1`), **LM
  Studio**, **llama.cpp**'s server, **vLLM**, and **LocalAI**. Configure it with `PYAEGEAN_LOCAL_URL`,
  `PYAEGEAN_LOCAL_MODEL`, and an optional `PYAEGEAN_LOCAL_API_KEY`. It uses the `openai` extra (no new
  dependency), needs no key or network, and grounding, exploratory labeling, provenance, caching, and
  `translate(verify=True)` all work as they do for a hosted provider. Reachable from Python
  (`ai.get_client("local", model=…)`, `translate(..., client=…)`) and the CLI (`--provider local`).
  New wiki section: "Using a local model".

### Changed
- The getting-started notebook is now linked from the **Getting Started** and **Tutorial** wiki pages
  (as a standalone runnable tour, noted as an alternative that does not follow those pages), not only
  from the README.
- Documentation consistency pass across the recent releases: the `local` provider, the `aegean greek
  profile` command, and the six-provider list are reflected everywhere the AI layer, providers, and
  command maps are described.

## 0.30.0 (2026-07-09)

Guidance and process: help a user pick the right pipeline and workflow, describe what a text
actually is, surface coverage gaps for sourced contributions, and document how quality is checked.

### Added
- **Descriptive text profiler.** `greek.profile_text(text)` returns a `TextProfile` of observable
  features (writing system, polytonic vs bare vowels, a Beta Code look, majuscule share, editorial
  brackets, numeral density, counts). It describes what the characters are; it deliberately does not
  predict a genre or an "out of domain" label. CLI: `aegean greek profile TEXT` (`--json`).
- **Coverage helper.** `greek.missing_forms(corpus)` lists the word forms the offline lemmatizer does
  not resolve, grouped by form with a representative location and a count: the bridge from the
  evidence class (0.28.0) to a sourced contribution.
- **Guidance pages** (wiki): "Choosing a Pipeline" (material to backend), "Choosing a Workflow"
  (audience/goal to an end-to-end workflow), and "Validation and Review" (an honest record of how
  quality is checked, what has and has not had external review, and how to submit a finding).
- **Sourced-data contribution path.** The data-contribution issue form and CONTRIBUTING now ask for
  the source, form, lemma, morphology, a scope note, and a test, across missing/wrong lemma, missing
  morphology, and poetic/dialectal/Koine/epigraphic forms.

### Changed
- The `xdist_group` pytest marker is registered in `pyproject.toml`, so a plain `pytest` run without
  `pytest-xdist` no longer emits `PytestUnknownMarkWarning`.

## 0.29.0 (2026-07-09)

Critical-edition fidelity for the epigraphy and papyri corpora, and genre-aware evaluation.

### Added
- **Reading status on every epigraphic and papyrological token.** The six inscription and
  papyrus corpora (`isicily`, `iip`, `iospe`, `igcyr`, `edh`, `ddbdp`) now carry each editor's
  apparatus through to every token: `Token.status` is `CERTAIN`, `UNCLEAR`, `RESTORED`, or
  `LOST` (a word takes the most severe status touching its letters), and the corpus provenance
  records an `edition_fidelity` flag (`apparatus-preserved,normalized`, or
  `apparatus-preserved,epichoric` for IGCyr's archaic Cyrenaean spelling). Restored or damaged
  readings are no longer presented as if securely on the object. Status round-trips through JSON,
  SQLite, and EpiDoc export. New wiki page: "Using critical editions".
- **Genre-sliced UD evaluation.** `greek.evaluate_by_genre()` (CLI: `aegean greek eval ud
  --by-genre`) buckets a fold by its `sent_id` author into literary genres and scores each
  bucket with the official evaluator. The new "Genre and register" section of the benchmarks
  document records what the folds do and do not support: the leakage-clean Perseus test fold is
  prose-only, so a held-out epic/tragedy accuracy is future annotation work, not a current claim.

### Fixed
- **The epigraphy corpora flattened the editorial apparatus.** Restored (`<supplied>`), unclear
  (`<unclear>`), and lost readings were marked as certain text. They now carry their true reading
  status. The apparatus assets were rebuilt and re-hosted as `-v2` (same documents and reading
  text as `-v1`, now with the apparatus preserved); older pyaegean releases keep loading the
  `-v1` assets they pinned.
- **A re-pinned `extract` dataset was served stale from the cache.** `fetch()` re-validated a
  single-file dataset against its pinned sha256 but returned an unpacked archive directory
  without checking it, so a rebuilt archive was never picked up. Unpacked datasets now record the
  archive's sha256 and re-download when the pin changes. Existing DDbDP caches predate the stamp,
  so to pick up the reading-status `ddbdp` v2 run `aegean data remove ddbdp` (or
  `fetch("ddbdp-corpus", force=True)`); the five inscription corpora refresh automatically.
- I.Sicily and the other EpiDoc corpora no longer emit a stray `Text` section-heading token
  (three IGCyr documents were affected); the shared extractor now skips edition `<head>` labels.

### Changed
- **DDbDP refreshed from upstream:** 57,329 -> 57,331 documentary papyri (two papyri added and
  two re-edited at papyri.info since the previous build), rebuilt with reading status.

## 0.28.0 (2026-07-09)

Trust signals in the output: see where each analysis came from, what kinds of errors to
expect, and correct them with a human in the loop.

### Added
- **Evidence class on every lemma.** `greek.pipeline()` records now carry `lemma_source`
  (`aegean.greek.LemmaSource`): `attested` (treebank), `neural`, `rule`, `seed`, `identity`
  (a model returned the surface form unchanged), `unresolved` (baseline miss), or `punct`. A
  new `greek.lemmatize_sourced()` exposes it directly and `greek.needs_review()` flags the two
  classes worth checking. The class flows through `greek pipeline --json` and the CLI table.
  Note for code that *constructs* `TokenRecord` (an output type; construction is rare):
  the `lemma_known` init field was replaced by `lemma_source` in this release, so
  `TokenRecord(..., lemma_known=...)` must become `TokenRecord(..., lemma_source=...)`;
  *reading* `record.lemma_known` is unchanged (it is a derived property).
- **Error analysis for scholars.** A new `aegean.greek.erroranalysis` module (POS confusion
  matrix, per-POS accuracy, lemma confusions, seen-vs-unseen) generalizes the former
  PROIEL-only drift report to UD-Perseus, the NT, and the AGDT held-out split:
  `aegean greek eval {ud,proiel,nt} --drift`, and `greek.{proiel,ud,nt,heldout}_error_analysis`.
- **Human review loop.** `aegean review export` writes a corpus's annotations to a reviewable
  CSV (machine lemma / POS / morphology, the evidence class, a `needs_review` flag, blank
  correction columns); `aegean review apply` reads corrections back onto the corpus, keeping
  each machine value under `<field>__pred` and stamping the reviewer and a provenance note.
  New `aegean.io.to_review_table` / `from_review_table` and `greek.annotate_corpus`.
- **Teaching pages:** "How to read a pyaegean parse", "When the tool is wrong", and "Citing
  computational assistance" (wiki).

### Fixed
- Under the neural joint pipeline, `lemma_known` was hard-coded `True`, so an identity
  fall-through (the model returning the surface form) wrongly read as a known lemma. It is now
  decided by which branch of the lemma composition fired, so a real analysis whose lemma equals
  the surface form (a nominative singular) is still `known`, while a true fall-through is not.

## 0.27.2 (2026-07-08)

A data-store fix, and much more to read and try: a bigger browser demo, a full-coverage
notebook, and workflow-level documentation.

### Fixed
- `aegean data fetch` of a prebuilt lexicon index (`lsj-index`, `middle-liddell-index`,
  `cunliffe-index`, `abbott-smith-index`) now stores the artifact under its real on-disk
  name, the same end state the lexicon backends produce, so `data list`, `doctor`, and
  `data remove` all agree with the fetch (previously a plain fetch left a raw-named file
  that `list` reported as not downloaded and `remove` could not see). A raw-named copy
  left by an earlier fetch is adopted in place, without re-downloading, and `data remove`
  now cleans one up.

### Added
- **Browser demo**: 15 new cards (29 total), one per offline feature — accentuation,
  sandhi, prosody, honest lemmatization, a New Testament verse with its gold annotations,
  idiom glosses, Linear A statistics and compound queries, Aegean numerals, sign lookup
  across all five scripts, a Linear B tablet with its Greek bridge readings, a Cypro-Minoan
  document, find-site geography, citation + fingerprint, and EpiDoc export.
- **Notebook**: a "whole toolkit at a glance" appendix (38 new cells) covering the Python
  surface end to end, plus real, optionally-runnable cells for the heavy features (the
  DDbDP database, the joint neural pipeline, generative translation), gated on the
  notebook's one `RUN_HEAVY` switch with the requirements spelled out; automated runs
  print `[skipped]`.
- **Recipes**: eight end-to-end workflows (epigraphist, papyrologist, literary classicist,
  New Testament scholar, corpus linguist, Aegean-scripts researcher, AI-assisted
  translator, toolsmith/agent-builder), each cross-linked to the task recipes.
- **CLI guide**: a how-to-read-a-command primer, a common-tasks cookbook, worked
  multi-flag examples for the confusing paths, a real REPL session, and a
  what-went-wrong section with the actual error messages. **TUI guide**: key-by-key
  walkthroughs (first five minutes, fetching corpora, the works library, the command
  console) and a reader's guide to the apparatus colouring.

## 0.27.1 (2026-07-08)

A documentation accuracy pass across the whole project.

### Fixed
- `NOTICE` corrections: the UD Ancient Greek treebank licenses are now stated per treebank
  (Perseus CC BY-NC-SA 2.5, PROIEL CC BY-NC-SA 3.0), and the Middle Liddell, Cunliffe, and
  Abbott-Smith derived lexicon indexes now carry their own attribution entry (Perseus Digital
  Library, Scaife Viewer, and translatable-exegetical-tools digitizations).
- README, wiki, and CLI/MCP help text caught up with the corpus catalogue: the six epigraphic
  and papyrological corpora (I.Sicily, IIP, IOSPE, IGCyr/GVCyr, EDH, DDbDP) now appear in the
  feature summary, the fetchable-dataset tables (all 19 assets), the corpus-id lists, the shown
  error outputs, and the TUI/MCP surface descriptions.
- Scholarly and technical docstring corrections: the prosody module no longer claims
  muta-cum-liquida is always heavy-by-position; the lemmatizer cascade documents the neural
  joint pipeline as its first tier; the accounting docstring lists all total markers (KU-RA,
  PO-TO-KU-RO, TO-SO-DE); scribal hands are documented for the bundled Linear A corpus as well
  as DAMOS; stale one-book NT sample references now say John 1 + Philemon.
- `wiki/Evaluation.md` documented a `greek eval` invocation that consumed its own flag as a
  fold name, and pointed at `greek.ud_path`/`greek.load_conllu` at the wrong import level; both
  corrected. Fingerprint examples re-measured; the Bacchae line mis-citation in Meters fixed.
- `docs/large-corpora.md` now documents the shipped streaming path (`aegean.db.stream`) and
  DDbDP as the corpus it serves, instead of describing both as deferred.

## 0.27.0 (2026-07-08)

The Duke Databank of Documentary Papyri — 57k Greek papyri, full-text searchable.

### Added
- **`aegean.load("ddbdp")`** — the **Duke Databank of Documentary Papyri** via papyri.info
  (**CC BY 3.0**): **57,329 Greek documentary papyri, ~4.4M tokens**. By far the largest corpus
  pyaegean ships, so it is hosted and read as a **SQLite database with full-text search**, not JSON.
  The reading text is extracted resolving the papyrological apparatus (`<reg>` over `<orig>`,
  `<lem>` over `<rdg>`, `<add>` over `<del>`, abbreviation expansions kept whole), with each
  document's citation, date, place, and Trismegistos/HGV ids. Mirrored as a sha256-pinned release
  asset (fetched + unpacked on demand, never bundled).
- **`aegean.scripts.greek.ddbdp_db()`** and **`aegean db search ddbdp "…"`** — the memory-friendly
  access path: instant full-text search and flat-memory streaming (`aegean.db.stream(ddbdp_db())`)
  over all 57k papyri without materialising the whole corpus. `aegean.load("ddbdp")` still returns
  the entire corpus in memory for those who want it (heavy — several GB of RAM).
- `aegean db search` now accepts a DB-backed corpus id (`ddbdp`) directly, fetching the asset on
  first use, in addition to a built `.db` file path.

## 0.26.0 (2026-07-08)

The Greek subset of the Epigraphic Database Heidelberg.

### Added
- **`aegean.load("edh")`** — the **1,286 pure-Greek inscriptions** of the Epigraphic Database
  Heidelberg (Heidelberg Academy of Sciences and Humanities, **CC BY-SA 4.0**), extracted from the
  frozen (2021) EDH data dump. EDH is overwhelmingly Latin; this is its Ancient-Greek subset — the
  editions marked `xml:lang="grc"` — Imperial-period Koine (dedications, boundary and funerary
  texts, verse epitaphs), largely onomastic. Each document keeps its ancient place, date, modern
  find-place, and Trismegistos id (for cross-referencing). Because the EDH project has closed, this
  also preserves a corpus that will not be republished. Mirrored as a sha256-pinned release asset
  (fetched on demand, never bundled); attribution travels in the corpus provenance and `NOTICE`.
  Also fetchable as `aegean data fetch edh`.

### Fixed
- The TUI corpus overview now correctly reports the Greek-epigraphy corpora (I.Sicily, IIP, IOSPE,
  IGCyr, EDH) as **fetch-on-demand**, not bundled — previously they read as always-downloaded, so a
  screen could not prompt their fetch.

## 0.25.0 (2026-07-07)

The Greek inscriptions of Cyrenaica — archaic Doric and verse.

### Added
- **`aegean.load("igcyr")`** — the **997 Greek inscriptions** of Cyrenaica, from IGCyr²/GVCyr²
  (eds. C. Dobias-Lalou et al., Università di Bologna, **CC BY-NC-SA 4.0**), with a descriptive
  title, find-place, and date. This is a high-value dialect corpus: it includes the archaic
  epichoric **Doric** and the GVCyr metrical/**verse** subset, and its text preserves the epichoric
  letterforms (e.g. `ō`/`ē` for long o/e) — non-normalized Greek, valuable for dialect study.
  Mirrored as a sha256-pinned release asset (fetched on demand, never bundled); attribution travels
  in the corpus provenance and `NOTICE`. Also fetchable as `aegean data fetch igcyr`.

## 0.24.0 (2026-07-07)

More epigraphic Greek, and a preservation mirror.

### Added
- **Two more Greek-inscription corpora**, both fetched on demand and now **mirrored** in the
  pyaegean repo (a preservation hedge against the upstream sources going offline):
  - **`aegean.load("iip")`** — the **2,113 Greek inscriptions** of IIP (Inscriptions of
    Israel/Palestine, Brown University, **CC BY-NC 4.0**), with find-place and coordinates. Adds
    regional and late-antique Greek epigraphy (much of it in majuscule, as inscribed).
  - **`aegean.load("iospe")`** — the **1,194 Greek inscriptions** of IOSPE (Ancient Inscriptions of
    the Northern Black Sea, King's College London, data **CC BY**): Tyras, Olbia, Chersonesos, and
    Byzantine texts, with find-place and date.

  Both are sha256-pinned release assets, never bundled; attribution travels in the corpus
  provenance and `NOTICE`. Also fetchable as friendly stems (`aegean data fetch iip` / `iospe`).

### Changed
- The terminal-setup docs now recommend the best **free** classicist Greek fonts for polytonic and
  epigraphic Greek — **New Athena Unicode** (the scholarly standard) plus the OFL **Gentium Plus**,
  **Cardo**, and **GFS** families.

## 0.23.0 (2026-07-07)

Epigraphic Greek: the I.Sicily inscriptions.

### Added
- **The I.Sicily Greek-inscriptions corpus** (`aegean.load("isicily")` / `aegean info isicily` /
  `aegean data fetch isicily`). I.Sicily (ISicily/ISicily, **CC BY 4.0**) is an EpiDoc corpus of
  the inscriptions of ancient Sicily; pyaegean now hosts the **2,855 primary-Greek texts** — their
  Greek reading extracted from each inscription's primary edition (line breaks resolved,
  abbreviations expanded, restored/uncertain letters kept, lost gaps and symbols dropped) with the
  ancient find-place, date, and coordinates. This adds **epigraphic** Greek (real inscriptions on
  stone) alongside pyaegean's literary (Perseus) and New Testament Greek. Fetched on demand,
  sha256-pinned, never bundled; CC BY attribution to I.Sicily travels in the corpus provenance and
  `NOTICE`. Also fetchable as the friendly stem: `aegean data fetch isicily`.

## 0.22.0 (2026-07-07)

Manage downloaded Greek works, and a friendlier Linear B data path.

### Added
- **Delete downloaded Greek works.** `aegean greek works --remove <id>` removes one work,
  `--remove-author <name>` removes every downloaded work by an author, and `--remove-all`
  clears them all (the only way a fetched work leaves disk; re-fetch with `aegean greek work
  <id>`). In the TUI Works library, `x` removes the highlighted downloaded work. Library:
  `greek.remove_fetched_works(ids=…, author=…, remove_all=…)`.

### Changed
- **A friendly Linear B corpus path.** `aegean data fetch damos` now works directly (dataset
  stems resolve, so you no longer need the `-corpus` suffix — `nt`, `sigla` too). `data fetch
  linearb` no longer hits a bare "no pinned URL" wall: it points you at **DAMOS** (a ready,
  directly-fetchable corpus, ~5,900 tablets, CC BY-NC-SA 4.0), is honest that **LiBER** is
  browse-only (liber.cnr.it has no public download or API and is rights-restricted), and shows
  how to import your own licensed export. `data remove` accepts the same stems.

## 0.21.0 (2026-07-07)

Analyze a line while you read it, in the TUI.

### Added
- **In-reader line analysis.** With the corpus reader focused, `↑`/`↓` (and PgUp/PgDn,
  Home/End) move a highlighted **line cursor**, and `Enter` or `a` opens an **analysis
  popup** for that line. The analyses offered fit the line's script:
  - **Greek** (alphabetic Greek, the NT, fetched Greek works): the **offline parser/tagger**
    (instant), the **neural pipeline** (best-in-class tags + a dependency parse; needs the
    `[neural]` extra and downloads the model on first use), **IPA**, and **translation**.
  - **Linear B / Cypriot** (deciphered): the **Greek reading + gloss** and the **sign values**.
  - **Linear A / Cypro-Minoan** (undeciphered): the **sign glyphs** and, for Linear A, an
    **exploratory transliteration** — both plainly labelled as not a reading.

  **Translation is optional and BYOAI-gated**: it appears only when a provider API key is
  configured (e.g. `OPENAI_API_KEY`), and the popup says so otherwise rather than pretending
  to translate. The neural and translation runs happen on a background worker, so the UI never
  blocks. Esc closes the popup.

## 0.20.6 (2026-07-07)

### Changed
- **The TUI corpus reader now shows a focus highlight.** When you Tab to the reading pane it
  carries a "reading" border title and its border turns accent-coloured, so it is obvious the
  reader is active (and that the arrow keys will scroll it) without having to test-scroll. The
  corpus list's border likewise highlights when it holds focus.

## 0.20.5 (2026-07-07)

The TUI command console now shows the CLI hints the REPL shows.

### Fixed
- **Predictive completion now includes subcommands.** The ghost-text completion offered only
  top-level commands: `greek scan`, `data fetch`, `analyze clusters` and the rest never
  completed, because the sub-group check used `isinstance(cmd, click.Group)` and typer's
  `TyperGroup` is not a `click.Group`. It now duck-types the same way the REPL completer does,
  so typing `greek sc` suggests `greek scan`.

### Changed
- **The console prints the command map on entry**, exactly like `aegean repl`, so the available
  commands are visible up front instead of only surfacing as you type. The intro line advertises
  the directives: `Tab/→` completes, `↑/↓` recalls history, `:examples` prints starter lines,
  `:help` reprints the menu.

## 0.20.4 (2026-07-07)

Fixes for TUI layout collisions where widgets landed on the same row as the Header or Footer
and were painted over.

### Fixed
- **The command console prompt is now visible.** It was docked to the bottom on the same row
  the Footer occupies, so the Footer painted over it: the cursor, the typed text, and the ghost
  completion were all hidden, even though the input was working. The prompt now sits on its own
  row just above the Footer. (This completes the console fix begun in 0.20.3, which stopped a
  stray key from quitting the app but left the prompt hidden.)
- **The Works library action buttons are back on screen.** The table over-expanded and pushed
  the "Fetch selected", "Fetch all by author", and "Open" buttons off the bottom of the screen,
  below the Footer. The table now fills only the space above the buttons.
- **The Greek workbench input no longer overlaps the header.** It was docked to the top on the
  Header's row; it now flows just below the Header.

## 0.20.3 (2026-07-07)

A TUI command-console input fix.

### Fixed
- **The TUI command console now captures every keystroke.** If focus ever drifted off the
  prompt (a click on the output, or a terminal focus quirk), a bare letter fell through to a
  global shortcut instead of being typed — pressing `q` quit the whole app. The prompt now
  holds focus reliably (the output pane can no longer take it), and any stray key re-focuses
  the prompt rather than triggering a shortcut, so typing a command always works. `Esc` still
  leaves the console.

## 0.20.2 (2026-07-04)

More follow-up fixes to the TUI, and a documentation ordering improvement.

### Fixed
- **Downloaded Greek works are now permanent, selectable items in the TUI corpus browser.**
  Opening a fetched work (say the Iliad) previously loaded it transiently: it vanished the
  moment the selection changed. Every downloaded work now appears in the left list as its own
  entry (`author — title (Greek work)`), stays highlighted when open, and reloads when chosen —
  clearly distinct from the bundled "greek" sample-texts corpus.

### Changed
- In the TUI works library, **Enter** on a highlighted work opens it, the same as the `o` key.
- On the **Benchmarks** and **Methodology** wiki pages and in `docs/benchmarks.md`, the "what the
  metrics mean" section now comes before the score tables, so the terms are defined before the
  numbers that use them.

## 0.20.1 (2026-07-04)

Follow-up fixes to the 0.20.0 CLI/REPL/TUI work.

### Fixed
- **GitHub token discovery.** Fetching Greek works now finds a token in the `GH_TOKEN`
  environment variable and, when no token variable is set, falls back to the GitHub CLI's
  stored auth (`gh auth token`) — so a machine already authenticated with `gh auth login`
  hits the 5,000/hour rate limit automatically, without exporting anything. The rate-limit
  message names all the ways to authenticate.
- **The TUI document reader could not scroll.** A long document (a whole Iliad book) was
  clipped to the visible height with no way to see the rest. The reader is now a scroll
  container in the Tab cycle: Tab focuses it, then the arrow keys, PageUp/PageDown, and the
  mouse wheel move through the text.

### Changed
- **The TUI command console reads like a shell.** The boxed input is now a borderless
  `aegean>` prompt line with predictive command completion (Tab or → accepts the ghosted
  suggestion) and up/down history recall.
- **The TUI home screen is clearer.** The corpus list is framed as a menu, opens focused with
  the first entry highlighted (so ↑/↓/Enter work immediately), and the intro and key legend
  distinguish the tools the keys open (the Greek workbench, `g`) from browsing a corpus.

## 0.20.0 (2026-07-04)

A CLI/REPL/TUI usability and parity release: the terminal UI reaches feature parity with the CLI,
the Greek work library becomes first-class in the TUI, and a set of reported paper-cuts are fixed.

### Added
- **`aegean greek work all AUTHOR`** bulk-fetches every work by an author (case-insensitive),
  e.g. `aegean greek work all homer`, with `--dry-run`, `--limit`, a confirmation for large sets,
  idempotent resume, and clear guidance when the unauthenticated GitHub rate limit is reached.
- **`aegean greek works --downloaded`** lists the Greek works already in the local cache, and a
  single `aegean greek work <id>` now states whether it was downloaded or already cached, and where.
- **`aegean greek nt BOOK [PASSAGE]`** takes the chapter or range as a positional and renders the
  passage text: `aegean greek nt John 1`, `aegean greek nt Matt 1-3`. `aegean show` reads chapter
  ranges too (`show nt "Matt 1-3"`), and a dotted reference resolves (`show nt "Matt.1"`).
- **`aegean repl`** shows the command menu on startup, the same map bare `aegean` prints.
- **The terminal UI (`aegean tui`) reaches CLI parity and grows:** a **Works library** (`w`) to
  search the ~1,800-work catalogue and fetch a work or a whole author and open it; a **command
  console** (`:`) that runs any `aegean` command with full CLI/REPL parity; the corpus browser now
  opens fetched Greek works and files; a live-preview, persistent **theme picker** (`t`); a **help**
  overlay (`?`); **Esc** to exit an input or go back to the previous screen; and an Attic/Koine IPA
  selector in the Greek workbench.
- A richer offline Greek sample: the bundled New Testament sample is now two chapters, **John 1 and
  Philemon 1** (Nestle 1904, CC0), fully annotated.
- New wiki pages: **Benchmarks**, **Methodology**, **TUI**, **MCP server**, **New Testament**,
  **Evaluation**, and **Translation**, with a restructured sidebar. The benchmark and methodology
  material is now readable directly in the wiki rather than only in the repository.

## 0.19.16 (2026-07-04)

A scholarly-correctness pass ahead of a review by university professors of Ancient Greek: a
14-lens philology panel (metrical scansion, accentuation, morphology, reconstructed phonology,
dialect, Beta Code, the Greek shown in the docs, Linear B, Cypriot, the undeciphered-script
honesty framing, benchmark methodology, provenance, and framing), each finding independently
verified. The core philological surface came back clean; six localized defects are fixed.

### Fixed
- **Linear B lexicon — the reading `O-KA` = ἔχω "to hold" was a fabrication** and is removed.
  ἔχω is written *e-ke* (which the lexicon already carries correctly); *o-ka* is the distinct
  word of the Pylos "o-ka tablets", whose Greek reading is not securely established, so the
  bridge now returns an honest miss rather than a confident wrong equation.
- **Linear B lexicon — `A-PI-QO-TO`** kept its correct sense (a round, rimmed table) but was
  lemmatized as ἀμφίβροτος, the Homeric shield-epithet ("man-covering"), a mis-etymology. The
  lemma now records the honest analysis (ἀμφί- with the root of βαίνω, "go round"; no attested
  Classical form).
- **Lemmatizer — first-declension masculine `-ης` genitives** (προφήτου, Ἰωάνου, Ἡρῴδου) no
  longer fabricate a confident `-ος` non-word. The `-ου` ending cannot be told from the
  second-declension genitive, so for the common such nouns the strip is suppressed to an honest
  miss (72 confident-wrong lemmas removed on the full New Testament; all 4,275 genuine `-ος`
  genitives preserved; published accuracy unchanged).
- **Lemmatizer — a neuter carrying the acute an enclitic throws onto its ultima** (δῶρόν, as in
  δῶρόν ἐστιν) is now read as the neuter δῶρον, not the non-word `*δῶρός`; a grave-accented
  neuter (ἱερὸν) normalizes to its citation form.
- **Provenance — the UD Ancient Greek evaluation folds carry different licenses**:
  UD-Perseus is CC BY-NC-SA 2.5, UD-PROIEL is CC BY-NC-SA 3.0 (each per its own README at the
  pinned commit). The blanket "3.0" is corrected across the code and docs, and the version is
  now recorded per treebank.

## 0.19.15 (2026-07-04)

The Cypriot loader now decodes the rest of the IG XV 1 Leiden apparatus, completing the
apparatus handling begun in 0.19.9.

### Fixed
- **Illegible-sign marks are no longer read as syllabograms.** A Leiden dot on the line
  (`..`, one dot per illegible sign), a figure-dash filling a lost-sign slot in a lacuna, and
  an unread `?` previously appeared as literal "signs" inside a word (`i-te-o-..-..-..-ja`
  produced signs including `..`), and such a token could be marked `CERTAIN`. Each now marks a
  sign whose reading is not preserved: it is kept in the token text (to show the position) but
  dropped from the sign list, the token reads `UNCLEAR` (or `LOST` when the whole token is
  illegible marks), and a marker attached to a legible sign (a trailing period, an `?`) is
  stripped off the label. A retrograde arrow `↓` is recorded as a writing-direction marker,
  not a sign. The raw marked form is kept in `annotations["leiden"]` and the inscription
  `paritySha256` is unchanged (no text field changed — the fix is in the loader).

## 0.19.14 (2026-07-04)

An Ancient Greek scholarly-correctness pass, verifying the Greek against the standard
references (Smyth, LSJ, West, Ventris-Chadwick) and correcting ten confirmed errors. Metrical
scansion, reconstructed pronunciation, Beta Code, and the Greek examples shown in the
documentation were all checked and found correct.

### Fixed
- **Accent placement.** An oxytone noun/adjective now takes the circumflex in the genitive and
  dative when the ultima is long (θεός → gen. θεοῦ, dat. θεῷ; τιμή → τιμῆς, τιμῇ), per Smyth
  §163a; and the πόλις/πῆχυς type keeps its antepenult accent in the -εως/-εων genitive
  (πόλεως, not πολέως), per Smyth §275.
- **Syllable quantity.** A vowel before a double consonant ζ/ξ/ψ is now correctly heavy by
  position (ὄζος, τάξις; Smyth §144); the word-level prosody agrees with the line-level
  metrical scanner, which already applied the rule.
- **The offline lemmatizer no longer fabricates a non-word.** The augmented thematic aorist/
  imperfect in -ον (εἶπον, ἦλθον, ἔλαβον), the -όω contract verb 3sg in circumflexed -οῖ
  (δηλοῖ, σταυροῖ), the genitive/dative of a common second-declension neuter (ἔργου, δώρου),
  and the ψ/ξ sigmatic future (γράψει, διώξει) were each stripped to a confident but spurious
  -ος/-ω lemma; they now return an honest miss instead. Measured on the full Nestle 1904 New
  Testament, this removes 618 confidently-wrong lemmas without losing a single correct one.
- **Two Linear B lexicon readings corrected**: `po-ni-ki-ja` is φοινίκια "crimson" (not the
  ethnonym Φοίνικες), and `ki-ti-me-na` is the land-tenure participle κτιμένα (not the Homeric
  compound ἐϋκτίμενος), per Ventris-Chadwick.
- **Dictionary glossing** strips a leading grammatical/morphological note ("gen.", "Imp. pl.",
  "Epic also", "Root", "not used in pl.") so the actual English sense surfaces, instead of
  emitting the note as the meaning (φέρω → "carry", not "Imp. pl").

### Added
- **Propagation-parity safeguards** (`tests/test_propagation_parity.py`): for each bug class
  that has recurred as a fix applied to one site but not its siblings, a test now enumerates
  every sibling and asserts the invariant across all of them (the double-consonant quantity
  rule shares one source between prosody and meter; every script's phonetic bridge strips the
  Leiden underdot and folds case; every provider adapter wraps a call failure; every MCP corpus
  tool returns a structured error; every export is atomic; every cache/hash key is injective).
  Adding a sibling that lacks the fix now fails a test in the same commit. In passing this made
  the Anthropic and OpenAI adapters wrap a transport failure and the Linear A phonetic bridge
  strip the underdot, matching their siblings.

## 0.19.13 (2026-07-04)

A documentation-freshness pass: every documentation code block was re-run against the current
code and the shown outputs that had drifted were corrected. No library behaviour changed.

### Fixed
- **Corrected drifted example outputs in the wiki.** Several shown results were stale after
  earlier releases: the Linear A assigned-sound-value count (now 50, after ZE/ZO were read in
  0.19.8) on the Limitations page, the bundled `signs.json` byte size and the corpus JSON length
  on the Data-and-Provenance and Architecture pages, and the tie-order of the `dispersion` and
  `cooccur` example tables (both are deterministic; the docs showed the pre-0.19.6 order). The
  documented outputs now match the current code.
- Added regression guards that pin the documented `dispersion` and `cooccur` outputs and the
  Linear A sound-value count, so a future change that alters them fails a test and the
  documentation is updated in the same commit.

## 0.19.12 (2026-07-04)

A security and robustness pass over the untrusted-input surfaces: the parsers, importers, the
fetch/cache layer, and the work-fetch path handling of a hostile file or a crafted argument.
Six hardening fixes, each pinned by a regression test.

### Fixed
- **EpiDoc import is linear, not quadratic.** A deeply nested TEI document made the importer
  O(tokens x depth), so a small hostile-but-well-formed file could hang `aegean import --epidoc`
  for minutes on one CPU. The apparatus-membership and reading-status lookups are now
  precomputed in single passes, so parsing is linear (a large nesting that took seconds now
  takes a fraction of a second) with identical output.
- **Loading a prebuilt index caps its decompressed size.** A `.json.gz` lexicon/model index is
  decompressed with a size limit, so a swapped mirror (when a `PYAEGEAN_<NAME>_URL` override
  disables the checksum) cannot inflate a tiny file into gigabytes and exhaust memory.
- **`load_work` rejects a path-like work id.** A work id containing a path separator or `..` is
  refused, so a crafted id cannot escape the pinned Perseus repository and fetch a forged
  edition from an arbitrary source. (The MCP tool already did this; the guard now covers the
  CLI and the Python API too.)
- **A malformed corpus file fails cleanly at load.** `Corpus.from_json` / `from_dict` now
  validate that each line's token indices are in range and raise a clear error naming the
  document, instead of loading a corrupt object that crashes later with a bare `IndexError`.
- **The analysis cache is hardened.** Its file is created owner-only, and enabling a cache in a
  directory writable by other users warns that a cached value is unpickled on read (a shared
  cache is a code-execution trust boundary); the documentation states this for the
  `PYAEGEAN_ANALYSIS_CACHE` redirect.
- **EpiDoc import records only the file name in provenance.** The importer stamped the full
  absolute import path into the corpus provenance and every citation, leaking the user's
  directory layout into a shared export; it now uses the basename, like the other importers.

## 0.19.11 (2026-07-04)

A propagation audit: for each bug class already fixed at one site, every sibling site was
checked and the ones the fix had not reached were corrected. Eight fixes covering fourteen
sites, each pinned by a regression test.

### Fixed
- **Rebuilding a corpus database no longer risks the existing one.** `to_sqlite` (and
  `aegean db build` / `aegean export --format sqlite`) deleted the current `.db` before
  rebuilding, so a full disk or interruption mid-build left no recoverable file. It now builds
  into a temporary database and atomically replaces the target, so a failed rebuild leaves the
  prior database intact. The same temp-then-replace is applied to the JSON, CSV, Parquet, and
  EpiDoc exports, which likewise overwrote a prior file in place.
- **The Gemini provider wraps a network failure like the others.** A transport error (a
  dropped connection or timeout) is not a Gemini API-error subclass, so it leaked out of a call
  as a raw exception; it is now wrapped in `ProviderCallError`, matching the Anthropic and
  OpenAI adapters.
- **Every MCP corpus tool reports a fetch failure cleanly.** The shared corpus-loading helper
  did not catch a download failure, so a cold-cache `damos`/`sigla` fetch could leak a raw
  exception out of seven tools; it now returns the structured error the rest of the surface
  uses.
- **Cypriot transcription reads a damaged-but-legible sign correctly.** `word_to_phonetic`
  (and `analysis.compare.to_phonemes(..., "cypriot")`) now strips the Leiden underdot before
  the sign lookup, the fix Linear B already had.
- **Linear A transcription folds case.** `word_to_phonetic` now upper-cases before the lookup,
  so the standard lowercase transliteration reads the Q- and Z-series (`qa-de` → `kwade`)
  instead of falling through to raw text, matching Linear B and Cypriot.
- **The offline lemmatizer no longer fabricates a present from a sigmatic future.** The guard
  that blocks the `-ει/-εις → -ω` strip on a sigmatic future (`δώσει`) now also covers the
  other thematic endings (`δώσομεν`, `δώσετε`, `δώσουσιν`), which were stripped to a confident
  wrong `-ω` lemma; genuine present verbs still resolve.
- **A stored sign inventory can no longer be corrupted by a caller.** The `sign_inventory`
  accessors returned a shared cached inventory whose per-sign `attrs` were live dicts, so an
  edit leaked into every later reader and a subsequent load; each accessor now returns an
  independent copy, matching `Corpus.copy`.
- **Building a prebuilt lexicon index leaves no orphaned download.** `fetch_prebuilt` copied
  the fetched file to the built-index name and left the original behind, uncounted and
  unremovable; a single-file dataset is now moved into place, so no redundant copy lingers.

## 0.19.10 (2026-07-04)

A regression audit of the recent fix churn: the areas most changed across 0.19.1 through
0.19.9 were re-examined for defects those changes introduced, alongside the code no prior pass
had touched. Five regressions and two pre-existing bugs fixed, each pinned by a regression test.

### Fixed
- **`aegean data remove` can delete every downloaded dataset again.** 0.19.1 taught `data list`
  and `doctor` to recognize a dataset stored under a different filename (a prebuilt lexicon
  index, an `agdt-derived` member) but left `remove` probing only the default location, so those
  five datasets showed as downloaded yet refused removal, and their disk space could not be
  reclaimed. `remove` now uses the same on-disk-aware lookup, so the two commands agree.
- **Opening a corpus from the command palette works while the corpus browser is already open.**
  A 0.19.1 cleanup removed the message the browser used to reload on an in-place selection change,
  so selecting a different corpus from the palette while already on that screen silently kept the
  old one displayed. The browser now reconciles to the new selection in that case too.
- **`clean_gloss` keeps a real meaning that begins with a derivation abbreviation.** The 0.19.2
  guard that drops bare grammatical-derivation pointers ("adverb of", "comp. of") was too broad
  and also discarded genuine glosses like "composed of", "control of", "advantage of", leaving
  those words ungrounded. The guard now matches only when the abbreviation is a whole token.
- **The analysis cache no longer crashes a worker mid-call when it is reconfigured.** After
  0.19.7 made the cache usable from worker threads, calling `cache.enable`/`cache.disable` from
  one thread could raise a "closed database" error in a memoized call running on another. A
  concurrent close now degrades to a cache miss (the value is recomputed), honoring the
  cache's never-changes-a-result contract.
- **`persistent_accent` places the accent correctly on imparisyllabic third-declension nouns.**
  A noun that gains a syllable in the oblique cases (σῶμα → σώματος, ῥήτωρ → ῥήτορος) had its
  accent anchored from the end of the word, landing it on the penult; it now tracks the stem
  syllable from the start and recedes to the antepenult as required.
- **Workbench import attaches each document's surface forms by id.** `from_workbench_export`
  paired glyphs/transcription/images to documents positionally, but a repeated id (e.g. two
  tablet sides labeled the same) collapses to one document, which shifted every later document's
  extras onto the wrong id and dropped the last one. Extras are now keyed by id.
- The stale "48 signs carry a sound value" figure on the Limitations page is corrected to 50
  (the ZE/ZO reading in 0.19.8), matching the rest of the documentation.

## 0.19.9 (2026-07-03)

A correctness pass over the surfaces the prior audit sweeps had covered least: the AI provider
and cache layer, the MCP dictionary tool, SQLite search, and the Linear B and Cypriot script
bridges. Seven defects fixed, each pinned by a regression test that reproduces the failure and
checks the corrected output.

### Fixed
- **`db.search` no longer crashes on a token stored without a position.** A token saved with
  `position=None` (a supported, round-tripped state since 0.19.4) crashed the search with a
  `TypeError` when it matched, in both token and substring modes, because the position was
  coerced with `int()`. The position is now returned as-is (`None` stays `None`; the return
  type is `(doc_id, int | None, text)`).
- **A provider that returns an empty response no longer leaks a raw `IndexError`.** An
  OpenAI-compatible gateway (notably OpenRouter) can return HTTP 200 with an empty `choices`
  list when an upstream vendor errors or a moderation filter fires. The adapter read
  `choices[0]` outside the error-wrapping block, so this surfaced as a bare `IndexError`
  instead of the clean `ProviderCallError` the rest of the AI layer raises; it now raises
  `ProviderCallError` (carrying any `error` payload the gateway sent).
- **The AI response cache key is injective.** The key joined its fields with a NUL separator
  and no length prefix, so a NUL in the system prompt or prompt could shift a field boundary
  and collide two logically distinct requests, serving one the other's cached completion. It
  now length-prefixes each field, the same fix `Corpus.fingerprint` uses. Cache files written
  by earlier releases still load; their entries simply miss under the new key and recompute.
- **The MCP `greek_gloss` tool returns a structured error on a dictionary fetch failure.** A
  first, cold-cache use of a hosted dictionary while offline (or on a network / HTTP / checksum
  failure) leaked a raw exception out of the tool instead of the `{"error": ...}` payload the
  rest of the MCP surface returns; it is now caught and reported in the structured form.
- **Linear B `word_to_phonetic` reads a damaged-but-legible sign correctly.** A sign carrying
  the Leiden underdot (U+0323, "damaged but legible") fell through to its raw transliteration
  instead of its settled phonetic value (so `pọ-me` transcribed as `pọme`, not `pome`). The
  underdot is now normalized away before the sign lookup, matching the sibling lexicon bridge;
  this also corrects `analysis.compare.to_phonemes` for such words.
- **The Cypriot loader decodes more of the IG XV 1 Leiden apparatus.** Erasure brackets `⟦⟧`
  (deleted by the scribe, still legible), editorial-insertion angle brackets `<>`, and
  abbreviation-expansion parentheses `()` previously leaked into sign labels and left the token
  mislabeled `CERTAIN`. They are now stripped from the emitted token and its signs (the marked
  form is kept in `annotations["leiden"]`) and mapped to the right status: `⟦⟧` reads
  `UNCLEAR`, `<>` reads `RESTORED`, and `()` reads `CERTAIN` (a secure reading).
- **Linear B EpiDoc import keeps a fully-uncertain word.** An apparatus `<app>` with variant
  `<rdg>` readings but no editor-preferred `<lem>` dropped the word entirely. It now emits a
  token (reading the first variant, flagged `UNCLEAR`, with the remaining variants as
  alternate readings).

### Changed
- The published CPU-throughput figure in `docs/benchmarks.md` is now explicitly framed as
  hardware-dependent and illustrative, not a pinned benchmark like the accuracy rows, with the
  dependency-drift trigger (a model or `onnxruntime` floor change) that warrants a re-measure
  named in the claims registry.

## 0.19.8 (2026-07-03)

A cross-repo sign-table reconciliation: the Linear A z-series signs **ZE** and **ZO** now read as
signs in both the bundled inventory and the Linear A Research Workbench, closing the last standing
data discrepancy between the two projects.

### Fixed
- **ZE and ZO now read as Linear A signs.** Both are securely attested z-series syllabograms
  (ZE 46 times, ZO twice in the bundled corpus), but each occurs only as a standalone single-sign
  word, so the workbench's hyphenated-word sign aligner never walked them and both projects had
  carried them as unreadable Unicode-chart entries with no sound value. They are now read from
  their own attestations: ZE maps to U+1063C (dze, confidence 1, unanimous across its 46
  attestations); ZO maps to U+1060E (dzo, confidence 0, the chart identity, its 2 attestations
  too short to align). The aligned/read-sign count moves 95 to 97 (manifest `signCount` 95 to 97),
  and the count of signs carrying an assigned sound value moves 48 to 50. The inscription-level
  parity contract (`paritySha256`) is unchanged, as it hashes the shared text fields and not sign
  phonetics, so the corpus the two projects share does not drift. Mirrored in the Linear A
  Research Workbench 1.6.1, whose rebuilt served app (`aegean workbench`) now embeds the 97-sign
  table.

## 0.19.7 (2026-07-03)

A concurrency and thread-safety pass: the surfaces real concurrent use touches (worker
threads, overlapping MCP calls, parallel CLI processes, shared caches) were driven under
aligned concurrent workloads and every reproducible failure fixed, each pinned by a
regression test.

### Fixed
- **The analysis cache is thread-safe.** Enabling it (`cache.enable()` or
  `PYAEGEAN_ANALYSIS_CACHE`) made every memoized analysis call from any other thread crash
  with a SQLite thread-identity error — including cache hits and even `cache.disable()`.
  The connection is now shared safely behind a lock, so threaded code behaves identically
  with the cache on or off, as the cache's contract promises.
- **A paid AI response can no longer be lost to a cache-write collision.** Concurrent
  `set()` calls on a shared persistent `ResponseCache` collided on one temp file (crashing
  on Windows with the response already received, discarding it). Each persist now uses a
  unique temp name behind a lock, and a failing disk write degrades to memory-only instead
  of raising out of `complete()`.
- **SQLite reads can no longer be torn by a concurrent append.** `from_sqlite` and
  `stream()` read each document's row and tokens in separate statements, so an
  `append=True` writer committing in between could yield a document whose metadata and
  tokens came from different versions — silently. Reads now run inside transactions
  (whole-load for `from_sqlite`, per-document for `stream`), two simultaneous appenders
  take the write lock before their bookkeeping reads, and a `search()` that lands in the
  append's FTS-rebuild window falls back to the exact-match path instead of raising.
- **Concurrent fetches of one dataset are serialized.** Two `fetch()` calls for the same
  dataset (threads or processes) shared one partial-download file and one extraction
  staging directory, corrupting each other; a per-dataset lock now serializes them — the
  later caller waits, then returns the completed artifact. `aegean data remove` refuses
  cleanly while a fetch holds the lock (and reports a file-in-use error as one line, not a
  traceback).
- **A TUI download can actually be cancelled.** `fetch()` gained an abort hook, polled
  between transfer chunks, and the TUI's download worker is wired to it: quitting the app
  no longer blocks until the download completes (the partial file stays resumable), a
  second fetch press while one runs is refused instead of starting a duplicate transfer,
  and a superseded corpus search no longer writes its stale result over the newer query's
  status line.
- **`aegean workbench` stops cleanly on Ctrl+C** even when a client holds an in-flight
  request it has stopped reading (handler threads no longer block shutdown).

## 0.19.6 (2026-07-03)

A compatibility, dependency-floor, and performance pass: artifacts were cross-tested against
earlier released versions, every declared dependency minimum was install-tested at its exact
floor, and the quantified performance statements were re-measured. Each code fix is pinned by a
regression test.

### Fixed
- **Every declared dependency floor is now a verified floor.** Several extras declared minimums
  that failed outright in a freshly resolved environment: typer 0.12–0.15 crashes with today's
  click (the CLI floor is now `typer>=0.16`); tokenizers below 0.20 cannot load the shipped
  neural models' tokenizer files (`tokenizers>=0.20`, and the loader now names that fix instead
  of surfacing a bare parser error); mcp below 1.2 lacks the server API (`mcp>=1.2`, and
  `aegean-mcp` now says "upgrade mcp" rather than pointing at an extra that is already
  installed); pandas, pyarrow, shapely, anthropic, and openai floors predated the numpy 2 /
  httpx 0.28 era and could not even import as resolved today (raised to `pandas>=2.2.2`,
  `pyarrow>=16.1`, `shapely>=2.0.4`, `anthropic>=0.40`, `openai>=1.55.3`).
- **`pip install "pyaegean[tui]"` now installs a working `aegean tui`.** The extra omitted the
  CLI dependencies the documented two-line quickstart needs; it now carries them. Independently,
  the environment report the TUI's data screen renders moved to a CLI-free module
  (`aegean._doctor`), so a Python-API launch without the CLI installed degrades gracefully
  instead of crashing the screen.
- **Word queries no longer pay for co-occurrence they don't use.** `run_query` built the full
  word co-occurrence map on every call; on the New Testament corpus that was ~4 s and over a
  gigabyte of allocations per query. The map is now built only when a `word-cooccurs-with`
  filter is present, with identical results.
- **Corpus-wide dispersion is now a single pass.** `dispersions()` recomputed Gries' DP with a
  full corpus scan per vocabulary item; on the DAMOS corpus that was ~11 s. A postings-based
  formulation with identical values brings it to well under a second.
- **Schema versions are now checked on load.** Every corpus artifact records a schema version
  that no reader ever consulted; `from_json`/`from_sqlite`/`stream` now refuse a file written
  by a newer schema with the fix named ("upgrade pyaegean"), while missing or older versions
  load normally.

### Documentation
- **Corrected the neural pipeline's CPU throughput.** The published ~450 words/s was measured
  on the earlier full-precision model; the shipped quantized bundle measures roughly
  20–70 words/s (sentence-length dependent). The quantization section now states the real
  trade-off — the ~3× size reduction costs CPU throughput, with the fp32 asset available where
  speed matters — and the figures are pinned in the claims registry.
- The extras table carries the corrected floors, and the `tui` row notes the CLI dependencies
  ride along.

## 0.19.5 (2026-07-03)

### Fixed
- **Databases written by earlier releases load again.** 0.19.4's token-order fix added a column
  that the reader then required, so a `.db` file written by 0.19.3 or earlier failed with
  "no such column: token_order". Reading an old file now orders by its stored `position` (the
  best an old file carries), and appending into one migrates it in place (the column is added
  and backfilled), so existing corpus databases keep working unchanged.
- The `Corpus.copy` docstring states the measured cost honestly (one pass over the tokens, on
  the order of 100–200 ms for the largest corpora), replacing a stale "a few milliseconds" claim.

## 0.19.4 (2026-07-03)

An executable-documentation, robustness, and property-testing pass: every code example in the
README and wiki was executed and compared to its shown output, the exposed input surfaces
(importers, CLI, the local workbench server, search) were probed with adversarial input, and the
round-trip invariants (JSON, SQLite, EpiDoc, Beta Code, tokenize/syllabify) were property-tested.
15 code defects fixed, each pinned by a regression test; 33 documentation examples re-measured
against the current code.

### Fixed
- **The SQLite round-trip preserves token order.** A token whose `position` was `None` (for
  example one appended to a document) moved to the front of the document on reload, and
  out-of-order positions were silently re-sorted, corrupting the document against the stored
  line structure. Tokens now carry an explicit order column, so `from_sqlite` returns exactly
  the list `to_sqlite` was given (`position` stays pure data).
- **The corpus fingerprint is collision-proof.** The content hash serialized fields with
  separator bytes, so a control character embedded in the data could make two different corpora
  hash identically (a wrong-answer risk for the analysis cache). Every field is now
  length-prefixed, making the serialization injective.
- **Robust input handling.** `db.search` no longer raises on a query containing a NUL (the
  token itself already stored fine); a 300-digit numeral no longer crashes the accounting sum
  (it reads as infinite and reports non-balancing); `aegean import --epidoc` reports malformed
  XML as a clean one-line error instead of a traceback; the import CLI's default encoding now
  strips an Excel byte-order mark, matching `from_csv`; piping a table-printing command into a
  reader that exits early (such as `| head`) no longer dumps a traceback on Windows; the local
  workbench server returns a clean 404 for a request with invalid percent-encoding instead of
  dropping the connection.
- **Greek edge cases.** A word with a doubled leading apostrophe now tokenizes consistently
  between `tokenize` and `tokenize_words`; a medial sigma before an epigraphic letter outside
  the Beta Code alphabet (digamma) no longer folds to final sigma on the round trip; a
  combining accent that cannot precompose onto a macron- or breve-marked vowel now stays with
  its vowel in syllabification and scansion instead of splitting the word. The Beta Code and
  EpiDoc round-trip caveats (combining length marks; XML whitespace normalization) are now
  documented where the round-trip claims are made.
- `ResponseCache` expands a leading `~` in its path, so a home-relative cache file lands under
  the user's home directory.

### Documentation
- **Every shown example output in the wiki was re-run against the current code** and corrected
  where it had drifted: the cross-script comparison and nearest-neighbour figures (the
  labiovelar `qa → kwa` romanization), corpus fingerprints, the Linear A metrology, dossier,
  and balance tables, the IG XV 1 corpus example, geography coordinates and GeoDataFrame
  shapes, the fetchable-assets list (three lexicon indexes were missing), the FAQ extras table,
  the `usage`/`rarity`/`nearest`/keyness CLI outputs, the plot-scansion example (its input now
  actually scans), and the Tutorial's morphology walk-through, which now shows the output a
  reader actually gets when following the page in order.

## 0.19.3 (2026-07-03)

A methodology-and-provenance audit: a third adversarial pass focused on the parts the earlier
sweeps did not reach, the correctness of the measured numbers, the evaluation methodology, and
the limitations documentation, plus live testing of the bring-your-own-AI providers. Every code
fix is pinned by an output-verifying regression test.

### Fixed
- **A provider API error now surfaces as the library's clean error.** A failed AI call (a bad
  model id, an invalid key, a rate limit, a network drop) leaked the underlying SDK exception as
  a raw traceback out of `translate()` / `ask()`. All provider adapters (Anthropic, the
  OpenAI-compatible OpenAI/Grok/OpenRouter path, and Gemini) now wrap the SDK error in a single
  `ProviderCallError` (an `AIError`), preserving the original as its cause.
- **The corpus fingerprint covers `signs`, `glyphs`, and `alt`.** The content hash that keys the
  analysis cache hashed each token's text, kind, status, and annotations but not its decomposed
  `signs`, so two corpora differing only in their sign labels hashed identically and a cached
  sign-level `dispersions()` / `keyness()` could return the first corpus's result for the second.
  All three fields now vary the hash.
- **BibTeX citations are LaTeX-safe.** `Provenance.bibtex()` emitted field values (a title, a URL
  with `&`/`%`, a subset note) without escaping, so the entry broke at compile (`%` comments out
  the line, `&` is an alignment error). Field values are now escaped.
- Removed an unused constant in the neural pipeline (`joint._TAG_HEADS`).

### Documentation — measured numbers and methodology
- **Re-measured the pure-Python baseline table** in `docs/benchmarks.md`: five of its six UD/PROIEL
  cells had drifted since the offline tagger/lemmatizer changed and were never re-measured (PROIEL
  UPOS was off by ~3.8 points). Updated to the current stack (Perseus UPOS 86.73 / UAS 37.43;
  PROIEL UPOS 78.83 / lemma 85.63 / UAS 35.41).
- **Corrected the UD lemma-scoring description:** on the UD folds lemmas are scored by exact string
  match with no normalization (the UD gold is already NFC and homograph-free); the NFC +
  homograph-digit clean-up applies only to the native-corpus NT/PROIEL checks.
- **Fixed unreconstructible or mismatched benchmark statements:** the out-of-domain parsing lead
  over a Perseus-trained baseline is ~23 UAS (82.47 vs 59.00), not ~17; the bootstrap CIs use 999
  resamples (the reproducible default); and the bring-your-own quantization evidence is recorded in
  a new `training/results/v3-quantize-report.json` (measured sizes and the lossless comparison).
- **`training/README.md` now describes what actually ships:** the release asset is the quantized
  `grc-joint-v3` (weight-only int8 + fp16, ~173 MB), produced from the fp32 `grc-joint-v2`
  reproducibility checkpoint; the "int8 failed the gate" note refers to the rejected full-int8
  activation recipe.
- **New plain-language metric definitions** in `docs/benchmarks.md`: what UPOS, XPOS, UFeats, Lemma,
  UAS, and LAS each measure, so the tables read without prior NLP background.

### Documentation — corpus and packaging facts
- Corrected stale limitations: the Cypriot corpus is the bundled 178-inscription IG XV 1 (not "two
  illustrative inscriptions"); Linear B accounting `balance_check` folds case and fires over the
  lowercase DAMOS corpus (since 0.15.0).
- The extras table gains the `tui` extra and the `all` extra is corrected to
  `ai,epidoc,geo,data,cli,viz,mcp,tui`.
- The bundled-JSON provenance table adds the two files it omitted (`cypriot/ig_inscriptions.json`,
  `greek/idioms.json`) and corrects two byte sizes, so it again matches `data.versions()`.
- Clarified the SigLA figure: 1,376 word-division groups load as ~1,868 WORD tokens.

## 0.19.2 (2026-07-03)

A deep correctness pass: a fresh adversarial audit surfaced 28 confirmed defects across the
Greek, Aegean-script, data, and interface layers, each reproduced and then fixed with an
output-verifying regression test.

### Fixed
- **Loaded corpora no longer share mutable per-token state.** Editing a token's `annotations`
  (or a sign's `attrs`) on one loaded corpus leaked into every other copy and every later
  `load()` of the same bundled corpus, and silently changed a fresh load's fingerprint (the
  analysis-cache key). `Corpus.copy()` now gives each token and sign an independent dict, so an
  edit stays isolated and the copy still fingerprints identically to the original.
- **The offline lemmatizer stops fabricating verbs.** The thematic `-ει/-εις → -ω` rule invented
  non-existent `-ω` verbs for third-declension noun datives (`πόλει → *πόλω`), sigmatic futures
  (`δώσει`), aorist-passive participles (`ἀποκριθείς`), and `-εί` indeclinables (`ἐπεί`), and
  marked them as confidently recovered. It is now held back from those look-alike classes and the
  frequent third-declension datives are read to their correct noun lemma (`πόλει → πόλις`). Net
  effect on the full New Testament: accuracy up slightly and ~780 fewer fabricated lemmas, with
  every genuine present verb (`λέγει → λέγω`) still recovered.
- **Elegiac pentameter accepts a short final syllable** (brevis in longo): the closing anceps
  position no longer rejects a line ending in a naturally short open vowel.
- **Case-insensitive syllabic transcription.** `word_to_phonetic` for Linear B and Cypriot now
  folds case before lookup, so the standard lowercase (DAMOS / IG XV) transliteration reads the
  Q-, Z-, and X-series signs correctly instead of falling through to raw text.
- **Subscript sign labels resolve.** A sign the corpus prints with a Unicode subscript (`RA₂`)
  now resolves in the inventory whether it is stored as `RA₂` or `RA2`.
- **The Leiden underdot is a known reading.** The Cypriot and Linear B Greek-reading bridges now
  strip the combining underdot (damaged but legible) before lexicon lookup, so a legible damaged
  token resolves like its clean form.
- **Word-scope corpus queries work on alphabetic Greek.** `word-contains` / `word-prefix` /
  `word-suffix` and the other word predicates were gated on a hyphen and so matched nothing on
  Greek (and on single-sign Aegean) words; they now operate on every word token.
- **Full-text search finds punctuation tokens.** A token that the SQLite tokenizer reduces to
  empty (a standalone `·` or `—`) is now found in the default token-mode search.
- **CSV import tolerates an Excel byte-order mark.** `from_csv` defaults to a BOM-stripping
  encoding, so a spreadsheet-exported file no longer loses its id column or fails to find its
  text column.
- **EpiDoc export stays well-formed.** Token text carrying XML-invalid control characters is
  cleaned on export, so the document always re-parses.
- **Sandhi coverage.** A sentence-initial capitalized elision (`Ταῦτ' → Ταῦτα`) is now restored,
  and the unaccented enclitic copula forms (`ἐστιν`, `εἰσιν`, `φασιν`) are recognized as
  movable-nu, while the look-alike i-stem accusatives still pass through unclaimed.
- **Tokenizer consistency.** A leading prodelision apostrophe (`'στι` for `ἐστι`) is now
  classified as a word by both `tokenize` and `tokenize_words`, so `pipeline()` no longer drops
  it.
- **Morphology of the demonstratives.** The oblique forms of `οὗτος` / `ἐκεῖνος` (`τούτου`,
  `ταύτην`, `ἐκείνων`) now analyze as pronouns with case/number/gender instead of falling through
  to spurious noun readings; the smooth intensive `αὐτή` is unaffected.
- **Capital lunate sigma** (`Ϲ`) converts to Beta Code instead of leaking through untransliterated.
- **Cleaner glosses for translation grounding.** A dictionary line that is only a
  grammatical-derivation pointer (`adverb of …`, `comp. of …`, `a strengthd. form of …`) now
  yields no gloss rather than an `"adverb of"` fragment, while a real meaning that merely contains
  `of` / `from` is kept.
- **Data-store visibility reaches every surface.** The MCP `data_status` tool and the terminal
  UI's data screen now report a dataset fetched under a different filename as downloaded, matching
  `aegean data list` and `aegean doctor`.
- **MCP `query_corpus` no longer inverts on a string.** A `negate` value of `"false"` / `"no"` /
  `"0"` was read by a raw boolean conversion as true and silently returned the opposite result
  set; it is now coerced the same forgiving way as the boolean filter values.
- Smaller correctness fixes: the accounting balance no longer raises on a marker-set mismatch;
  `format_value` never renders a tiny negative as `-0`; the rarity heuristic counts the ordinary
  letter phi; a corpus doc-store size scan skips a file that vanishes mid-walk. Documentation:
  the quickstart command count (seven commands across eight steps) and the DAMOS/SigLA fetch
  sizes are stated consistently across the wiki.

## 0.19.1 (2026-07-02)

A full-program audit pass: three confirmed defects fixed, each pinned by a regression test.

### Fixed
- **Grand-total accounting reconciles correctly.** A `PO-TO-KU-RO` grand total that follows one or
  more `KU-RO` subtotals was summed against an empty running list, so it reported a computed sum of
  0 (on the bundled HT122b: stated 97, computed 0 instead of 65). It now sums the subtotals the way
  the reference implementation does (HT122b reconciles to 65, difference -32). The fix reaches
  `aegean balance`, the MCP tool, and the terminal UI, which now all route the accounting and
  pipeline tables through the shared `aegean._view` layer, so the three surfaces cannot disagree.
- **The AI response cache survives a corrupt file.** A truncated or garbage cache file (from a
  killed process or a full disk) is now treated as a cache miss rather than raising, and writes are
  atomic so no partial file is ever observable.
- **The data store reports what is actually downloaded.** Datasets fetched as an unpacked archive
  or a prebuilt index (the LSJ index, the AGDT models) were shown as "not downloaded" by
  `aegean data list` and `aegean doctor` even when present; the on-disk probe now checks each
  dataset's real footprint. The reproducibility manifest also marks a mirror-overridden URL's
  checksum as unenforced, since verification is skipped for a user's own mirror.
- **Smaller corrections.** Negative accounting quantities keep their sign; the Linear A
  sound-value count is corrected to 48 in the docs and inventory docstring; the terminal UI flags
  SigLA as undeciphered, runs its corpus search off the UI thread, and no longer carries a dead
  cross-screen message subsystem; `paired_bootstrap` validates `n_resamples`.

## 0.19.0 (2026-07-02)

### Added
- **`aegean tui` — a terminal UI.** An app-like research cockpit in the terminal (the opt-in
  `[tui]` extra, built on Textual): browse the corpora, inspect a document with its editorial
  apparatus and an inline accounting/structure analysis, a live Greek workbench that scans,
  syllabifies, glosses, and transcribes as you type, and the local data store with one-key
  dataset fetches. It is a focused view over the highest-value offline reads, not a second
  front-end for every command, and it never touches the network except when you ask it to fetch
  a dataset. Undeciphered scripts carry their caveat on screen, as everywhere else. The core stays
  zero-dependency: `import aegean` loads no part of Textual, and the UI is reached only through
  `aegean tui`. A shared view layer (`aegean._view`) computes the accounting and pipeline tables
  once, so the TUI and the CLI can never show different numbers.

## 0.18.0 (2026-07-02)

The guided release: the CLI learns to explain itself, check itself, and hold a session's context.

### Added
- **`aegean doctor`** — a one-command, fully-offline environment check: Python and package
  versions, which optional extras are installed (with the install line for the ones that aren't),
  the local data store (size, what's downloaded, leftover partial downloads named with their
  `aegean data remove` fix, and whether the store is writable), downloaded models, and the
  analysis cache. `--json` for the machine report; exit 1 when it finds a real problem. The first
  thing to run when something isn't working.
- **`aegean quickstart`** — the guided first five minutes, running eight real commands (all
  offline, all on bundled data): a corpus overview, a tablet, an accounting check, a sign search,
  the Greek pipeline, a hexameter scan, the data store, and where to go next. `--no-run` prints
  the tour without executing it.
- **A session corpus in the REPL.** `use lineara` sets a default corpus, so afterward `show HT13`,
  `balance ht13`, and `stats` need no corpus argument; `:examples` lists runnable one-liners across
  the toolkit, and command history persists between sessions where the platform supports it.
- **Shell completion, now documented.** `aegean --install-completion` (typer's built-in) was always
  there but unmentioned; the install and terminal-setup docs now cover it, along with a
  **"Set up your terminal"** guide (Windows Terminal over the legacy console, and the font needed
  for Linear A/B glyphs to render instead of showing as boxes).
- **A fifteenth MCP tool, `greek_work`** — load a Greek work by catalogue id (fetched to the store
  on first use), so an agent can reach the ~1,800-work corpus, not only the bundled registry.
- **`aegean data fetch --json`** emits `{name, path, bytes}`, completing the `--json` coverage the
  0.17.0 notes described (it had been added to `cite`, `combine`, and `import` but not `fetch`).

### Changed
- **`--top` and `--limit` are interchangeable** on every command that ranks or caps rows; the
  primary name each command showed still shows first, and a guard test keeps any future command
  from offering only one of the pair. A drift guard likewise keeps every MCP tool named in the
  documentation.

## 0.17.0 (2026-07-02)

The friendliness release: a systematic pass over every command's failure modes, dead ends, and
inconsistencies; all 74 commands now fail cleanly on bad input.

### Added
- **Did-you-mean, everywhere names are typed.** A misspelled corpus id suggests the close ones
  (`aegean load linera` → "did you mean 'lineara' or 'linearb'?"), and registered ids match
  case-insensitively as a fallback (`aegean info LINEARA` works). The same suggestions cover
  dataset names (`data fetch`/`remove`), query `--where` fields, NT book names, sign labels, and
  import `--script` values, in the CLI, the REPL, Python, and over MCP alike.
- **Six new MCP tools** (8 → 14), so an agent can do what the CLI can: `cite_corpus` (plain,
  BibTeX, or APA, with metadata filters citing the exact subset), `query_corpus` (the compound
  query engine), `data_status` (the local store: downloaded state and sizes), `greek_catalog`
  (search the ~1,800-work catalogue), `geo_sites` (coordinates, Pleiades ids, contested flags,
  per-site word attestations), and `greek_gloss` (the registry dictionaries). All fourteen tools
  now share one error convention: a structured `error` payload with suggestions, never a raised
  exception, and document ids are resolved as forgivingly as the CLI resolves them.
- **Hints at dead ends.** Empty search/query/load results, a fetched work, an imported file, and
  a built database each end with one dim line naming the next command; the bare `aegean` help
  points to a quickstart and the documentation.
- **Wider `--json` and `-o` coverage.** `cite`, `combine`, and `import` emit `--json`;
  `balance`, `greek pipeline`, `analyze structure`, `analyze hands`, `db search`, and
  `ai eval` save with `-o`; `stats`, `dispersion`, `balance`, `geo`, `structure`, and `hands`
  accept the shared metadata filters (`--site`/`--period`/`--scribe`/`--support`).
- **The web demo reads Cypriot inscriptions.** A new card loads a bundled *Inscriptiones
  Graecae* XV 1 inscription entirely in the browser: find-place, transliteration lines, the
  Greek reading where the text is Greek, and the source-edition link. The demo now covers all
  four Aegean scripts.

### Changed
- **Saving is uniform.** Every `-o` creates missing parent directories, prints one
  `wrote <path>` confirmation to stderr (stdout stays clean for data), and combines with
  `--json` instead of silently overriding it; corpus-writing commands dispatch by extension, so
  `-o corpus.db` writes real SQLite everywhere.
- **`aegean data store`** is the new name of `aegean data cache` (the old name remains as a
  deprecated alias): it is a permanent store, not an evicting cache, and the analysis cache
  (`aegean cache`) is now clearly a different thing.
- **`greek eval --fold`** replaces the fold-selector meaning of `--treebank` (deprecated alias
  kept; the backend-activation `--treebank` on tag/lemmatize/morph is unchanged).
- **`db search` opens databases read-only** (searching a missing or non-database path can no
  longer create an empty file as a side effect), and `--limit 0` means unlimited there, in
  `aegean.db.search`, and in the MCP `search_signs`.

### Fixed
- **The file-writing traceback class.** Thirteen `-o` paths (load, query, export in every
  format, geo, db build, plot, stats and its siblings, ai results) crashed with a raw traceback
  when the target directory didn't exist or wasn't writable; all now share one guard and fail in
  one line.
- **Validation before work, in one line.** Non-numeric `--where` values, unknown `export`/`geo`
  `--level`s (including geo's silently-ignored one), bad `greek eval --fold/--split`, malformed
  or out-of-range `workbench --port`, unknown `work`/`catalog --source`, invalid `inflect`
  feature values, and malformed NT refs all fail with a clean message instead of a traceback or
  a silent no-op; a `--ref` that selects nothing in a fetched work errors instead of returning
  the whole work mislabeled.
- **Missing optional extras surface their install command** (`export -f csv` without pandas,
  `geo` without geopandas) instead of a traceback; help text renders bracketed extras
  literally, so `aegean plot --help` no longer instructs `pip install 'pyaegean'` with the
  `[viz]` eaten by markup.
- **`greek rarity --corpus`** goes through the standard corpus resolver (`.db` files and clean
  errors) instead of a raw JSON load; the four neural-backend activation paths share the
  standard activation errors; `ai translate`'s grounding-quality warning prints as a visible
  stderr line instead of a swallowed Python warning; `greek nt-books` and group help maps name
  every command and end with CLI (not Python) follow-ups.

## 0.16.0 (2026-07-02)

### Added
- **`aegean data remove`** deletes downloaded dataset(s) from the local store (`remove NAME`, or
  `--all`), printing exactly what was removed and the space reclaimed; partial-download leftovers
  are cleaned with it. `aegean data list` gains a **downloaded** column showing what is actually on
  disk, with real sizes.

### Changed
- **The data store says what it is.** A fetched dataset is a complete, permanent local download:
  nothing is re-fetched, evicted, or expires until `data remove` deletes it or `fetch --force`
  replaces it. The CLI help, `data cache` output, module documentation, and wiki now state this
  guarantee plainly (the word "cache" had suggested downloads might not persist).
- **The Linear A sign table carries the corrected alignment data.** The workbench's 1.6.0 corpus
  rebuild fixed its sign aligner (the upstream damage marker no longer counts as a sign), growing
  the transliteration-aligned evidence from 127 to 236 inscriptions and the aligned signs from 84
  to 95 (recovering PU, PU₂, QI and twelve more, each verified against its Unicode chart name);
  AB-shared classification now follows the Unicode chart (66 AB-shared). The bundled table and
  manifest mirror it; the cross-project parity checksum is unchanged.
- **The bundled workbench app pin moves to 1.6.0**, carrying the workbench's stored-XSS fixes and
  the corrected sign table, so `aegean workbench` serves them.

### Fixed
- **CLI tables render square brackets literally.** Cell text was parsed as rich markup, so a value
  like `[neural]` in a dataset note silently vanished from `aegean data list`; cells are data, not
  markup, and now render as written.
- **`aegean show` (and `balance`, `analyze structure`) resolve document ids forgivingly.** A Greek
  work's book or section addresses without repeating the work id (`aegean show tlg0012.tlg001 1`,
  not `... tlg0012.tlg001:1`), case and spacing are forgiven (`ht13`, `py ta 641`), an ambiguous
  short id is never guessed (the candidates are listed instead), and the not-found error names the
  closest ids and the corpus size. `aegean greek work` now ends with the exact `show` command that
  reads the loaded text.
- **KU-RA counts as a stated total.** It is KU-RO's variant (two bundled tablets, ZA 20 and
  ARKH 2); the accounting layer now checks it, moving the measured checkable-total figures from
  35 tablets / 39 total lines to **37 / 41** (documented everywhere the old numbers appeared).
  Approximate readings (`≈ ¹⁄₆`) parse at the editor's value instead of dropping from line sums,
  which also reclassifies 29 fraction-bearing tokens that had been left unclassified.
- **The libation word list carries only attested forms.** The restoration fragment
  `A-DI-KI-TE-TE-DU` (zero corpus tokens) is replaced by the four attested a-di-ki-te family forms
  from Younger's readings of the PK Za vessels; three PK Za inscriptions now classify as libation
  (census: libation 15 → 18), and a liveness test keeps dead entries out.
- **Query: `word-contains-sign` matches sign labels as written.** `*301` (or `301`, any case) now
  finds `*301`-bearing words, and subscripted signs match only themselves (`RA₂` no longer answers
  for `RA`); a blank min/max-syllables value matches neutrally instead of raising.
- **Workbench exports re-import faithfully.** The importer reads the export schema's real field
  spellings (`period`, the nested images block), so dating and imagery survive the round trip.

## 0.15.1 (2026-07-01)

### Added
- **Resumable downloads.** A dropped or stalled connection no longer costs the whole download:
  `fetch()` keeps the partial file on network failures, retries up to twice within the call, and
  resumes with an HTTP `Range` request (guarded by `If-Range` and a recorded-length check, so a
  republished asset restarts cleanly from zero instead of splicing). A truncated response body is
  detected against the declared length rather than trusted. The sha256 verification of the
  completed file is unchanged and remains the final arbiter.

### Changed
- **The bundled workbench app pin moves to 1.5.5**, picking up the workbench's mirrored sign-table
  and phonetic corrections (the `*903` glyph fix and subscripted-sign reading that shipped here in
  0.15.0), so `aegean workbench` serves the same data conventions this library uses. The `*904`
  and `*905` sign entries are genuine, verified against Younger's readings: alias labels for
  GORILA `*319` and the fraction sign J.

## 0.15.0 (2026-07-01)

A correctness pass across the toolkit's convention boundaries: the places where a well-tested
code path meets a second data source with different conventions (upper vs lower transliteration,
suffixed morphology tags, Leiden apparatus, Unicode normalization, grave vs acute). Every fix
ships with a regression test pinning the corrected output.

### Fixed
- **NT gold UPOS: suffixed Robinson tags are reconciled correctly.** `PRT-N`, `CONJ-N`, `ADV-I`,
  `COND-K` and kin mapped to `X` because only bare tags were looked up, mistagging 3,566 tokens
  (2.6% of the corpus), among them every negative particle (οὐ, μή). Suffixes never change a
  closed-class tag's word class; the bare tag now wins (`PRT-*` → PART, `CONJ-*` → CCONJ,
  `ADV-*` → ADV, `COND-K` → SCONJ), leaving only the ARAM/HEB loanword tags as `X`. The
  out-of-domain NT benchmark row is re-measured against the corrected gold with the shipped
  model: lemma 87.03 / UPOS 86.75 (n = 137,303). The previously published 87.57 UPOS dated to
  the retired grc-joint-v1 model (0.8.1) and had gone stale when v2 shipped; the full
  decomposition (model generation, quantization, gold correction, normalization) is recorded in
  `docs/benchmarks.md`.
- **Offline lemmatizer: grave accents and the closed-class inventory.** Lookups now fold running-text
  graves to the citation acute (δὲ → δέ) and NFC-normalize, and the closed-class table covers the
  article's oblique forms, pronouns, and the high-frequency particles; `known=True` now always means
  a genuine table or rule validation, never a fabricated stem. Measured on the full NT under the
  recorded protocol (`greek.evaluate_on_nt` scoring): 45.2% → 66.0% lemma accuracy, 28,578 fixes
  against 12 regressions. This also corrects the 0.14.0 note's "14.5% → 15.4%": that figure was a
  byte-level comparison against pre-NFC gold, not the protocol score; the docs now carry the
  protocol-scored number.
- **Linear B accounting works on DAMOS.** The accounting markers matched uppercase only, so the
  lowercase DAMOS transliterations yielded zero `balance_check` totals across 5,932 tablets, and
  `to-so`/`o-pe-ro` leaked into `account_dossiers` as "account holders". Marker matching now folds
  case, `TO-SO-DE` joins the total markers, and DAMOS yields 130 tablets with stated totals
  (255 checks, 52 balancing exactly). Bundled Linear A results are unchanged (35 tablets, 39 totals;
  the README figure is corrected from "≈40" to the measured 35).
- **Cypriot inscriptions carry their editorial apparatus.** The IG loader emitted every token as
  CERTAIN and leaked Leiden markup into token text; underdotted (uncertain) readings now load as
  UNCLEAR and bracketed restorations as RESTORED, with clean text and the apparatus preserved in
  annotations (118 UNCLEAR + 56 RESTORED across the bundled corpus).
- **Linear A sign table: `*903` no longer wears the vowel I's glyph.** The entry duplicated
  U+1061A / 𐘚 (the Unicode block has no `*9xx` codepoints; glyph and codepoint are now empty), and
  `SignInventory` warns on duplicate glyph/codepoint entries instead of silently letting the last
  one shadow lookups. The tokenizer also recognizes standalone subscripted signs (PA₃, TA₂) and
  variant-letter ligatures (VIR+*313b) as logograms (27 bundled tokens regained from UNKNOWN) and
  `word_to_phonetic` reads subscripted signs as the distinct signs they are, never borrowing the
  plain series' value (the shared golden fixture value `raro` is corrected to `ra₂ro`; the
  workbench mirrors this in its next release).
- **Workbench image server: Windows path traversal closed.** The local facsimile server's guard
  only rejected forward-slash `..` segments; backslash and percent-encoded forms could escape the
  imagery directory. Requests are now decoded and separator-normalized, and the resolved path must
  remain inside the imagery root. The bundled workbench asset pin also moves from 1.5.1 to 1.5.4,
  picking up the workbench's own sanitizer hardening and gazetteer corrections.
- **`load_work` refuses to silently truncate.** A citation range crossing textparts (e.g.
  `1.1-2.50`) returned only the start part while the document id claimed the full range; it now
  raises a clear error naming the parts involved.
- **SQLite append keeps every corpus's provenance.** `to_sql(append=True)` dropped the appended
  corpus's provenance and license; the database now stores all of them, so `from_sql(...).cite()`
  cites everything that went in.
- **Empty geo results return empty GeoDataFrames.** `to_geodataframe` and `word_distribution` on a
  corpus with no mapped sites (or a word with no attestations) crashed with an opaque geometry
  error; both now return a schema-correct empty GeoDataFrame, matching the CLI's existing hint.
- **`db.search` case handling is measured and truthful.** Substring mode now matches Greek
  case-insensitively (SQLite `LIKE` folds ASCII only); the docstring states exactly what each mode
  folds (FTS5 token mode folds case but not accents).
- **AI layer provenance and caching.** Grounding passed as a generator was consumed twice, so the
  model saw it but the provenance recorded none of it: it is materialized once. The response-cache
  key now includes `max_tokens`, so a truncated completion is never served for a longer request.
  An unknown grounding mode raises with the valid modes instead of silently degrading to legacy
  lemma grounding. The verify-mode docs state the honest contract: the analysis cannot bias the
  draft, though a wrong analysis can still mislead the repair.
- **EpiDoc export never silently overwrites.** Two document ids sanitizing to the same filename
  produced one file; colliding names now get deterministic suffixes with a warning naming both ids.
- **NT loading and fetching hygiene.** `load_nt` NFC-normalizes text, lemma, and normalized forms at
  load (the source edition mixes oxia and tonos precomposition), and requesting a non-bundled book
  offline explains what is bundled and how to fetch the corpus instead of a misleading error.
  Downloads use a 30-second timeout instead of hanging on a stalled connection, and archive
  extraction validates symlink/hardlink targets before unpacking.
- **Greek tokenizer: ano teleia and the Greek question mark are punctuation.** The letter class
  spanned the whole Greek block, so U+0387 and U+037E glued into word tokens (3,330 such tokens
  when tokenizing the bundled NT's text; now zero). `pos_tag` shares the corrected letter class.
- **Diaeresis marks hiatus.** `syllabify` and `to_ipa` merged explicitly-marked non-diphthongs
  (προΐστημι is προ-ΐ-στη-μι, Smyth §8); a diaeresis vowel now never joins the preceding vowel,
  in precomposed and combining forms alike. Metrical scansion already handled this and is
  unchanged.
- **γάρ and οὖν are tagged CCONJ, not SCONJ.** Neither can subordinate a clause; the NT gold is
  unanimous (γάρ 1038/1038, οὖν 496/496) and AGDT has no conjunction reading for either.
- **The movable-nu rule only claims what it can validate.** It fires on `-ουσι(ν)` and a curated
  host lexicon (copula and athematic third persons, high-frequency dative plurals, accent-aware so
  ποσίν is listed while πόσιν is not); third-declension i-stem accusatives (γνῶσιν, φύσιν, πίστιν)
  no longer receive a fabricated bare alternative.
- **Docs carry the re-measured numbers.** The stale v1 PROIEL scores in the wiki are replaced with
  the shipped model's recorded figures, and "state of the art on the UD Ancient Greek benchmarks"
  is scoped to the measured claim (the UD Perseus test fold).

### Changed
- **`aegean.load()` returns an independent copy.** The cached loaders shared one mutable `Corpus`
  per process, so mutating `corpus.documents` corrupted every later `load()` of the same id. Each
  call now returns a structural copy (about 3 ms for the bundled Linear A corpus; frozen tokens are
  shared, containers are fresh), and the new `Corpus.copy()` is public.
- **`Corpus.fingerprint` covers what analyses consume.** It hashed only document ids and token
  text, so corpora differing in token kind, reading status, or annotations shared a fingerprint and
  the opt-in analysis cache could serve results computed for a different corpus. It now hashes
  kind, status, and annotations (and the data version); all fingerprints rotate once.

### Removed
- The empty `aegean.adapters` and `aegean.integrations` placeholder packages (0-byte, never
  documented, nothing imported them).

## 0.14.4 (2026-06-29)

### Fixed
- **Gazetteer coordinates corrected against Pleiades.** A full validation pass of the geo gazetteer
  against the Pleiades representative points found five find-site coordinates that had drifted from
  their place: Zominthos (~7.5 km), Kythera (~8.4 km), Pylos (~9.4 km), and the Cyprus and Margiana
  island centroids. All are now aligned to the Pleiades point.

### Added
- **Seven more find-sites aligned to Pleiades** (33 → 40 of 56): Ugarit (Ras Shamra), Sitia, the
  Skotino cave, Fourni and Troullos (Archanes), Poros (the harbour of Knossos), and Pyrgos, which
  had been mislocated by 39 km and is now corrected to Myrtos-Pyrgos.
- **`scripts/check_gazetteer.py`** — a repo-only guard (run weekly via `assets.yml`) that fails if a
  Pleiades-linked find-site drifts more than 6 km from its Pleiades point, so the gazetteer cannot
  silently rot.

## 0.14.3 (2026-06-29)

### Fixed
- **`geo --word` matches case-insensitively.** It was the only word-search path that did not fold
  case (`db.search`, the query engine, and `aegean search` already do), so `geo lineara --word
  ku-ro` found nothing while `KU-RO` worked. The CLI and `aegean.geo.word_distribution` now both
  fold case.
- **`aegean workbench` serves the facsimile imagery again.** The cached `lineara-images` asset
  unpacks into an `images/` subdirectory; the local server looked one level too high, so every
  facsimile returned 404 even after the asset was fetched.

### Added
- **`aegean workbench --fetch-images`** downloads the ~116 MB Linear A imagery in one step, and the
  command now hints how to fetch it when it is not cached.
- **`aegean geo` on a corpus without find-sites** prints a one-line explanation instead of an empty
  grid, and its `--help` notes which corpora produce rows (lineara, linearb, cypriot, cyprominoan,
  sigla, damos).

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
