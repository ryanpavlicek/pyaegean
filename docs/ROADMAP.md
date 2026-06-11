# pyaegean roadmap — the 0.8.0 program

**Status:** `main` holds the 0.8.0 hardening pass (full Linear A sign repertoire, `ReadingStatus` +
schema-valid EpiDoc, Pleiades alignment, honest scope docs). The `v0.8.0` tag is **deliberately not
cut**: everything in this document ships under 0.8.0. There is no 0.9.0 on the horizon — 0.8.0 is
the release where the gaps get *fixed*, not footnoted.

**The principle shift.** The pre-release reviews surfaced shortfalls we initially addressed with
honest documentation. Honest documentation stays — but as the floor, not the fix. Where a gap can
be closed with engineering, we close it. This document consolidates, in one place:

1. the review findings that are not yet *fixed* (only disclosed),
2. the **Greek NLP accuracy program** — parity or better with the leading neural pipelines,
3. the external reviewer's criticisms and big-ticket proposals (CLI first; web demo parked), and
4. everything outstanding from the prior roadmap (`docs/PLAN.md`).

Work packages are sequenced roughly by (value ÷ risk); WP3 is the long pole and runs in parallel
with the others (its training cycles are offline). `v0.8.0` tags when WP1–WP6 are done and the WP3
targets are met — the tag then publishes to PyPI via OIDC and mints the first Zenodo DOI, which gets
wired into the README badge, `CITATION.cff`, and the BibTeX block.

---

## WP1 — Quick wins (usability paper-cuts)

> **Status: DONE (2026-06-11).** `greek.pipeline()` (per-token records, backends-aware),
> the syllabification exception lexicon (Smyth §140 compounds, test-enforced),
> `normalize(..., lenient=True)` (warned repairs for OCR artifacts), citation automation
> (`Provenance.bibtex()/.apa()`, `Corpus.cite()`, subset notes on `filter()`, citable
> `QueryResults`), the CONTRIBUTING menu + deprecation policy, the scansion-statement
> audit (one stale `docs/PLAN.md` line fixed), and the CLAUDE.md refresh.

Small, high-leverage items, mostly from the external review; one session.

- **`greek.pipeline()` convenience layer.** One call that runs
  tokenize → tag → lemmatize → (optional) parse over a text and returns per-token records, with
  flags choosing the active backends. Non-experts should not have to compose nine functions.
  *(Reviewer: "no single high-level analyze/pipeline function.")*
- **Syllabification exception list.** A small curated lexicon of the lexicalised exceptions the
  rules can't capture, consulted before the rule engine. *(Reviewer.)*
- **Defensive normalization mode.** `normalize(..., lenient=True)` (name TBD): tolerate and warn on
  the artifacts of OCR'd or messy epigraphic text (stray combining marks, lookalike Latin letters,
  malformed Beta Code) instead of failing or silently mangling. *(Reviewer: "real-world robustness.")*
- **Citation automation.** `Provenance.bibtex()` / `.apa()`, and `cite()` on query results and
  filtered sub-corpora, so the exact subset used in a paper is citable in one call. *(Reviewer §6.)*
- **CONTRIBUTING.md expansion + deprecation policy.** A menu of small-scope contributions (add a
  sign-inventory fact, a syllabification exception, a collocation measure, a gazetteer alignment), and
  a lightweight documented deprecation policy (deprecate in a minor, remove no sooner than the next
  minor, warnings carry the replacement). *(Reviewer §7.)*
- **Scansion documentation audit.** One precise statement of coverage (hexameter + elegiac
  pentameter; synizesis *declined*, never inferred; iambic/lyric out of scope for now) applied
  consistently across README/wiki/docstrings. *(Reviewer flagged a perceived mismatch.)*
- **CLAUDE.md refresh.** The working-notes file still describes v0.2.0; bring it to current state and
  point it here.

**Acceptance:** each item has tests where it's code, and the docs/docstrings say exactly what ships.

## WP2 — The `aegean` CLI (big ticket #1)

> **Status: DONE (2026-06-11), with scope EXPANDED per the maintainer** — not just the v1 set
> below but essentially the whole public API: 12 corpus commands (incl. `show`, `sign`,
> `bridge`, subset-aware `cite`), the full `aegean greek` group (16 commands incl. `normalize
> --lenient`, `betacode`, `ipa`, `morph`, `gloss`, `pipeline`, and `eval` reproductions, with
> backend flags for every `use_*()` activation), `aegean analyze` (6 commands incl. the
> association-statistics `assoc`), `aegean data` (fetch/cache from the shell), and the
> exploratory-labeled, key-gated `aegean ai` group. Conventions held: `--json` everywhere,
> stdin via `-`, clean exit codes, CliRunner coverage for every command offline, a wiki
> reference page (`wiki/CLI.md`) with shell recipes. The config file was dropped in favour of
> environment variables (`PYAEGEAN_CACHE`, per-dataset URL overrides) — fewer moving parts,
> same control.

A command-line interface so classicists and epigraphers can use the toolkit without writing Python,
and so the data layer becomes scriptable/pipeable in shell workflows. *(Reviewer's top adoption
unlock; the web demo is parked — see “Declined / parked”.)*

- **Stack:** `typer` + `rich`, as the `[cli]` extra (`pip install "pyaegean[cli]"`); console script
  `aegean`. The core stays zero-dep; the CLI is opt-in.
- **Commands (v1 set):**
  - `aegean info <corpus>` — size, provenance, citation, license.
  - `aegean load <corpus> [--site … --period … --id …] [--output f.json]` — filter + export.
  - `aegean query <corpus> "<pattern>" [--stats]` — sign-pattern / compound query.
  - `aegean search <corpus> --pattern "KU-*-RO"` — pattern search with frequency stats.
  - `aegean stats <corpus> [--signs|--words]` — inventories and frequency tables.
  - `aegean balance <doc-id> [--verbose]` — accounting reconciliation.
  - `aegean scan hexameter|pentameter "<line>" [--pretty]` — scansion.
  - `aegean syllabify|lemmatize|tag "<text>" [--neural]` — Greek NLP one-shots.
  - `aegean export <corpus> --format json|csv|parquet|epidoc --output <path>`.
  - `aegean geo <corpus> [--geojson out.geojson]` — site table / GeoJSON export.
- **Conventions:** `--json` on every command for machine-readable output; `rich` tables for humans;
  exit codes that script cleanly; shell completion; a small config file
  (`~/.config/pyaegean/config.toml`) for default corpus and cache location.
- **Tests:** `typer.testing.CliRunner` coverage for every command; a docs page of worked shell
  recipes.

**Acceptance:** every command above works against the bundled corpora offline, `--json` everywhere,
CI-tested, documented.

## WP3 — Greek NLP accuracy program (“parity or better”)

> **Status: DONE and SHIPPED (2026-06-11).** The joint neural pipeline
> (`greek.use_neural_pipeline()`, the `grc-joint-v1` release asset) measures **above every
> published number on the UD Perseus test fold** — lemma 94.40 / UAS 89.16 / LAS 84.38 /
> UPOS 96.94 / UFeats 96.12 through the shipped pip path, confirmed end-to-end from raw
> text (tokens F1 99.97) — leakage-clean, one checkpoint, official evaluator. The full
> stage-by-stage record, protocol, and comparison tables: `docs/benchmarks.md`;
> evidence: `training/results/`. Sections 3.0–3.7 below are the program **as designed**
> (planning language preserved for the record); the results live in `docs/benchmarks.md`.

**Goal:** pyaegean's Greek NLP must measure **at least as good as the leading neural pipelines for
Ancient Greek** on the field's standard benchmarks — not only on our own honesty-first metrics.

### 3.0 Where the field actually is (verified numbers)

The reference points are the published evaluations in Kostkan et al. 2023, *“OdyCy — A
general-purpose NLP pipeline for Ancient Greek”* (LaTeCH-CLfL 2023,
<https://aclanthology.org/2023.latechclfl-1.14.pdf>), which benchmarks odyCy, greCy, Stanza, UDPipe,
and CLTK on the two UD Ancient Greek test folds. Best published score per metric:

| Test set | POS | Morph | Lemma | UAS | LAS |
|---|---|---|---|---|---|
| **UD Perseus (test)** | **95.39** (odyCy-joint) | **92.56** (odyCy-joint) | **87.58** (Stanza-perseus) | **78.80** (odyCy-joint) | **73.09** (odyCy-joint) |
| **UD PROIEL (test)** | **98.23** (greCy-proiel) | **94.05** (greCy-proiel) | **98.06** (greCy-proiel) | **85.74** (greCy-proiel) | **82.28** (greCy-proiel) |

Context that matters: odyCy is exactly *Ancient-Greek-BERT + dense tagging heads + spaCy's
transition parser*, trained jointly on both treebanks. The paper also shows every system collapses
out-of-domain (a Perseus-trained model on PROIEL and vice versa), which is why pyaegean's
leakage-free / unseen-form discipline is worth keeping as a differentiator.

pyaegean today (our own AGDT-native held-out protocol — *not directly comparable*, which is itself
part of the problem WP3.1 fixes): POS 84.4, lemma ~92 overall / 76.3 unseen, parser UAS 0.51 on all
text (arc-eager, projective-only). The tagger and parser are the real gaps; the hybrid lemmatizer is
already in the published pack's range.

### 3.1 Stage 0 — a comparable evaluation harness (no training yet)

- Build a **CoNLL-U adapter**: run the active pyaegean pipeline over a UD test fold and emit CoNLL-U,
  scored with the official UD eval script. Includes an AGDT→UD UPOS/feats reconciliation map
  (extending the PROIEL-eval tagset work) and the lemma-normalization conventions the paper
  describes (diacritics, dash-compounds).
- **Reproduce the field's numbers locally** with the odyCy team's open evaluation code, pinning tool
  versions, so our comparison rows are measured by us, not transcribed.
- **Leakage control (critical):** UD Perseus is a conversion of the AGDT — its test sentences exist
  in our AGDT training source. Before any training, build the sentence-level exclusion list (UD
  Perseus dev+test ∩ AGDT, by document/sentence id and by text match) and apply it to every training
  split. Same audit for Gorman/Pedalion overlap. Without this, any “parity” claim would be leakage.
- Deliverable: `docs/benchmarks.md` + a runnable benchmark notebook with every number reproduced.
  Score the *current* (perceptron/arc-eager) stack on the UD folds too, so the program's delta is
  public from day one.

### 3.2 Stage A — encoder backbone bake-off

- Candidates: **Ancient-Greek-BERT** (Singh et al. 2021 — the odyCy backbone),
  **PhilBERTa/PhilTa** (Riemenschneider & Frank 2023), GreBERTa; verify each model's license for
  redistribution of fine-tuned weights as a release asset.
- Bake-off protocol: identical quick fine-tune (UPOS head, fixed budget) on the leakage-clean AGDT
  split; pick on dev accuracy + size + license. Document the decision.

### 3.3 Stage B — joint neural tagger (UPOS + full morphology)

- Token-classification heads (UPOS + per-feature morph) on the chosen encoder, fine-tuned on
  leakage-clean AGDT (CC BY-SA) — optionally + Gorman (CC BY 4.0) and Pedalion, the mix already used
  for the GreTa lemmatizer.
- **Targets:** ≥ 95.4 POS and ≥ 92.6 morph on UD Perseus test; ≥ 97.8 POS on UD PROIEL test
  (odyCy-joint's number — see the licensing note in 3.6 for the PROIEL stretch).
- Ships as `greek.use_neural_tagger()`; the averaged-perceptron stays as the zero-dep fallback and
  the unseen-form honesty numbers stay in the docs alongside the benchmark numbers.

### 3.4 Stage C — graph-based neural parser

- A **biaffine** dependency parser (Dozat–Manning) over the same encoder, multi-task with the tagger
  (one shared backbone → one fetched artifact). Graph-based decoding (Chu-Liu/Edmonds MST, pure
  numpy) handles Ancient Greek's pervasive **non-projectivity natively** — the structural reason our
  arc-eager baseline is capped, and a plausible edge over odyCy's transition-based parser.
- **Targets:** ≥ 78.8 UAS / ≥ 73.1 LAS on UD Perseus test (best published); stretch: beat them, and
  approach greCy's 85.7/82.3 on PROIEL within the licensing constraints (3.6).
- Ships as `greek.use_neural_parser()`; arc-eager stays as the zero-dep fallback;
  `greek.evaluate_parser()` gains UAS/LAS on both protocols (AGDT-native and UD).

### 3.5 Stage D — lemmatizer v2 (context-aware)

- Keep the hybrid (gold lookup → neural → edit-tree → seed). Upgrade the neural stage with
  **sentence context / predicted morphology conditioning** (the prior roadmap's “context-aware
  lemmatizer”), so ambiguous forms resolve by context rather than per-word frequency.
- **Targets:** ≥ 87.6 lemma on UD Perseus test (Stanza's lead); ≥ 94.4 on PROIEL (odyCy-joint);
  push our unseen-form number 76.3 → 80+; keep ≥ 92 overall on the AGDT-native protocol.

### 3.6 Packaging, licensing, training infrastructure

- **Inference stays torch-free**: ONNX int8 via onnxruntime + tokenizers + numpy — the `[neural]`
  extra's existing dependency set, unchanged. One shared-encoder multi-task artifact
  (~110–150 MB int8) fetched-to-cache as a GitHub release asset (sha256, the `grc-lemma-neural-v1`
  pattern), never bundled; the footprint guard is untouched.
- **Licensing:** training on AGDT (CC BY-SA 3.0) + Gorman (CC BY 4.0) (+ Pedalion) keeps the model
  redistributable under CC BY-SA, like the existing lemmatizer. UD Perseus/PROIEL are CC BY-NC-SA →
  **evaluation only** (the established PROIEL-eval precedent). If the BY-SA-clean model can't reach
  PROIEL-side parity (domain gap: we don't train on its NT/Herodotus text), the decision gate is an
  *optional, clearly-labeled NC model variant* trained +PROIEL — shipped as a separate asset, never
  the default.
- **Training code** lives in `training/` in this repo (excluded from the wheel): dataset builders
  (with the leakage exclusions), fine-tune scripts, ONNX export + int8 quantization, eval runners,
  and a model card per artifact (data, license, metrics, protocol). Runs on Colab-class GPUs (the
  GreTa fine-tune precedent).
- **Quantization gate:** every artifact is evaluated fp32 vs int8; int8 ships only if the drop is
  ≤ 0.3 points on every headline metric, else fp16.

### 3.7 Definition of done (WP3)

- On **UD Perseus test**: ≥ best published number on **every** metric (POS, morph, lemma, UAS, LAS).
- On **UD PROIEL test**: ≥ odyCy-joint on every metric; stretch to best-published via the NC-variant
  gate if needed.
- All numbers reproduced by the public benchmark notebook; protocol + leakage controls documented in
  `docs/benchmarks.md`; wiki/README updated (our own numbers in public docs; the comparison tables
  live in the benchmark docs with citations).
- `greek.pipeline()` (WP1) defaults to the best active stack; unseen-form and out-of-domain honesty
  metrics remain first-class alongside the benchmark numbers.

## WP4 — Corpora: fix the thinness (not just disclose it)

> **Status: IN PROGRESS (2026-06-11) — the framework is shipped; corpus-data expansion
> remains.** Done: **alphabetic Greek on demand**
> (`greek.load_work` — Perseus canonical-greekLit + First1KGreek, commit-pinned; the Iliad
> verified live as 24 books / 127,339 tokens), **data versioning** (`aegean.data.versions()`,
> `Provenance.data_version`, pinning-for-papers recipe), **`Corpus.from_records()`** + the
> `register_loader` recipe, and **variant readings** (`Token.alt` with the EpiDoc
> `<app>/<lem>/<rdg>` round-trip, schema-validated). Also done: the **Linear A apparatus
> audit** (552 LOST + 120 UNCLEAR tokens recovered by interpretation; see the item below),
> **Linear B expansion** (18 tablets / 150 lexicon entries, all source-attested), and
> **Cypriot growth** (17 entries). Remaining: the DAMOS/LiBER inquiries (drafts in
> `docs/inquiries/`, awaiting send + answers), **SigLA integration** (license resolved —
> published CC BY-NC-SA 4.0 — but no advertised download endpoint; a format courtesy
> contact, then a fetch-to-cache loader), and `load_work` hardening (cached/authed
> edition discovery, deeper textpart addressing).

The 0.8.0-hardening pass *documented* that the non-Linear-A corpora are vestigial. This WP makes
them real where licensing allows.

- **Alphabetic Greek — a real corpus, on demand.** A fetch-to-cache TEI reader for
  **Perseus canonical-greekLit / First1KGreek** (CC BY-SA): load any covered work into the standard
  `Corpus`/`Document` model (`aegean.load("greek")` keeps the offline 5-passage sample; a new
  `greek` corpus fetcher exposes the real thing). This is the single biggest "5 famous quotes" fix.
  *(Shipped as `greek.load_work`.)* Hardening follow-up: cache/authenticate the edition-discovery
  listing (the unauthenticated GitHub API is rate-limited at scale), address textparts below the
  top level, and surface dropped `<note>`/`<bibl>` apparatus on request.
- **Linear B.** (a) *DONE (2026-06-11), with an honesty adjustment*: the sample grew 2 → **18
  tablets** (every addition a sourced Wiktionary quotation citing its tablet, with translation —
  nothing typed from memory) and the lexicon 45 → **150 entries** (the hand-curated core layered
  with every kaikki/Wiktionary entry that *states* its Ancient Greek equation). The original
  "~25 / 300+" estimates hit a real ceiling: many Mycenaean words have **no** alphabetic Greek
  descendant to bridge to, and unstated equations won't be authored from memory — 150 verified
  beats 300 plausible. `[X]`-restored readings now load as `ReadingStatus.RESTORED`.
  (b) **DAMOS — now a loadable corpus (DONE, 2026-06-11).** DAMOS (Oslo) is **CC BY-NC-SA 4.0**;
  its public web API was located and the transliterations + core metadata for ~5,900 tablets
  decoded into the hosted `damos-corpus` asset, loadable via **`aegean.load("damos")`**
  (`scripts/build_damos_corpus.py`; NonCommercial + ShareAlike pass-through; fetched, never
  bundled). This is the openly-licensed full Linear B corpus the bundled sample stood in for.
  The courtesy letter still stands as a stability/format check. **LiBER** (CNR) is
  all-rights-reserved with a metadata-only public endpoint, so it stays bring-your-own
  (`PYAEGEAN_LINEARB_CORPUS`) pending its reply. The BYO EpiDoc path stays first-class.
- **Cypriot.** *DONE (modest, as planned)*: lexicon 13 → 17 — four Idalion Bronze equations
  verified against the published readings (Chadwick) added to the Masson/ICS-sourced core.
- **Linear A apparatus (the deepest unfixed finding).** Phased:
  1. **Audit upstream** — *DONE (2026-06-11)*: the pipeline was lossless all along (pyaegean's
     bundle is marker-identical to upstream); the apparatus was present but uninterpreted. The
     upstream marks erased/illegible signs with the unassigned codepoint U+1076B (its own
     `stripErased()` confirms the intent); the loader now reads it — standalone runs →
     `ReadingStatus.LOST` (552 tokens), damaged-at-break words and `[?]`-bracketed uncertain
     readings → `UNCLEAR` (120 tokens); tablet ruling dashes → separators. 366 of 1,721
     documents now carry editorial status, regression-pinned in tests. Restorations and dotted
     readings were dropped upstream and are NOT recoverable from this source — that is SigLA's
     role (step 2).
  2. **SigLA integration — SHIPPED (2026-06-11).** Licensing was resolved without inquiry (the
     site publishes the dataset CC BY-NC-SA 4.0; the paper invites use "outside the interface"
     and notes copies can be hosted). The dataset shipped inside the web app as OCaml-Marshal
     payloads with no export endpoint — so pyaegean gained a pure-Python **Marshal reader**
     (`scripts/lineara/sigla.py`, three structural self-checks, offline-tested), a converter
     (`scripts/build_sigla_corpus.py`) emitting the JSON database the paper describes, the
     **`sigla-corpus-v1` release asset** (sha256-pinned, NC-labeled, ~1 MB), and
     `aegean.load("sigla")`: 781 documents with typology/site/**dimensions**/period/EFA refs
     and 5,065 sign attestations in tablet order. Cross-validated against the bundled GORILA
     corpus (547/651 shared docs at ≥60% overlap under 28 data-derived notation equivalences;
     residue = rare-ligature notation). Remaining refinements: numerals/erasure flags and word
     grouping (preserved as `raw_flags`), and the format courtesy contact (sent) as a
     stability check.
  3. **Corpus v2**: a GORILA-faithful bundled corpus with editorial status populated, with SigLA
     enrichment as the opt-in fetched layer (NC data stays out of the Apache-2.0 wheel). If the
     upstream audit dead-ends, the documented limitation stands — but we will have actually tried
     to fix it.
- **Data versioning & reproducibility.** A version + sha256 manifest for every bundled dataset and
  fetched asset (`aegean.data.versions()`); `Provenance` carries the data version; a “pinning for
  papers” recipe. *(Reviewer §2.)*
- **User corpora as a framework.** Public `Corpus.from_records()` + documented `register_loader`
  recipe + custom-EpiDoc ingestion guide, so a scholar's own inscriptions get the full API (query,
  DataFrames, provenance, export). *(Reviewer §2.)*
- **Variant readings.** Extend the token model for *alternate readings* (e.g. `Token.alt:
  tuple[str, ...]`, EpiDoc `<app>/<rdg>` ↔ round-trip), complementing `ReadingStatus`. Paleographic
  sign-variant analysis proper waits on SigLA-grade data. *(Reviewer §2.)*

## WP5 — Analysis & visualization

> **Done (2026-06-11).** Statistics layer ✓, visualization helpers ✓, and comparative
> phonetics ✓ all shipped — WP5 complete.

- ~~**Visualization helpers** (lazy matplotlib via the `[data]`/`[viz]` extra): sign-frequency bars,
  collocation networks, scansion grids, accounting-discrepancy views — convenient one-liners, not a
  plotting framework.~~ **Done** — `aegean.viz` (the `[viz]` extra): frequency bars, dispersion
  scatter, keyness bars, co-occurrence network, balance diagonal, scansion grid; CLI `aegean plot`.
  *(Reviewer §3.)*
- ~~**Statistics layer**: dispersion measures (e.g. Gries' DP), keyness (log-ratio, log-likelihood),
  bootstrap confidence intervals — pure stdlib where feasible, with scholarly framing in docstrings.~~
  **Done** — `aegean.analysis.stats`: Gries' DP (+ Lijffijt & Gries normalization), keyness
  (G² Rayson-&-Garside form + Hardie log-ratio), percentile bootstrap over documents; CLI
  `aegean dispersion` / `aegean keyness`. *(Reviewer §3.)*
- ~~**Comparative phonetics**: generalize the distance/alignment module for cross-script comparison
  (Linear B ↔ alphabetic Greek, Cypriot variants) — exploratory-labeled where it touches
  undeciphered material.~~ **Done** — `aegean.analysis.compare`: `romanize_greek`, `phonetic_compare`,
  and cross-script `nearest`; CLI `aegean analyze compare`/`nearest`. *(Reviewer §3.)*

## WP6 — AI layer credibility

> **Done (2026-06-11).** All four items shipped — WP6 complete.

- ~~**Grounding traceability**: every `ExploratoryResult` carries a structured trace — which corpus
  entries, analysis steps, and rules built its grounding — rendered human-readably
  (`result.trace()`).~~ **Done** — `GroundingItem(content, source, ref)` + `ExploratoryResult.trace()`;
  CLI `--trace`. *(Reviewer §4 — “a strong differentiator.”)*
- ~~**Structured outputs**: JSON-mode for capabilities, so AI output can feed pipelines/databases.~~
  **Done** — `ai.extract` + `ai.parse_json`; CLI `aegean ai extract`. *(Reviewer §4.)*
- ~~**Grounded-generation eval harness**: fixed cases with known answers; measure grounding fidelity
  (does the output use the evidence? does it fabricate?) the way the lemmatizer is measured.~~
  **Done** — `aegean.ai.eval` (`GroundingCase`, `run_eval`, `DEFAULT_CASES`); CLI `aegean ai eval`.
  *(Reviewer §4.)*
- ~~**Expert validation loop**: a “For specialists” wiki page, GitHub issue templates for corrections
  /validations from domain experts, and a living limitations register.~~ **Done** — three GitHub
  issue forms (correction / validation / data-contribution) + the For-Specialists wiki page, with
  Limitations as the living register. *(Reviewer: validation.)*

## WP7 — Engineering

> **In progress (2026-06-11).** Persistent cache ✓ shipped; large-corpus readiness next.

- ~~**Opt-in persistent cache** for expensive analyses (collocations, clustering, large queries) —
  stdlib-based (sqlite/json), no new hard dependency, off by default.~~ **Done** — `aegean.cache`
  (sqlite + pickle, off by default), `@memoize` on `find_morphological_clusters` / `dispersions` /
  `keyness`, keyed on `Corpus.fingerprint()`; CLI `aegean cache`, env `PYAEGEAN_ANALYSIS_CACHE`.
  *(Reviewer §5.)*
- **Large-corpus readiness**: a short design note + lazy iterators where free now; streaming proper
  is deferred until a corpus that needs it exists (First1KGreek via WP4 is the test case).
  *(Reviewer §5.)*

## WP8 — Geo / linked data

- Extend Pleiades coverage past 26/56 where places exist; **contribute the missing Bronze Age sites
  upstream to Pleiades** (the good-citizen move that also fixes our nulls), and consider ToposText
  cross-ids. GeoJSON export (`aegean geo --geojson`, WP2).

## WP9 — Docs, recipes, community

- **Recipes**: end-to-end scholarly workflows (“reconcile accounting across the HT corpus and export
  discrepancies”, “map a word's distribution”, “lemmatize and cite a chapter”). *(Reviewer §7.)*
- **Benchmark notebook** (WP3 deliverable) maintained as living documentation.
- Wiki/README refresh as each WP lands; CHANGELOG discipline + the WP1 deprecation policy in force.

---

## Declined / parked (with rationale)

- **Pydantic/msgspec core** — conflicts with the zero-dependency invariant that defines the package;
  `mypy --strict`, frozen dataclasses, and round-trip tests already cover the failure modes. Won't do.
- **Database backend (SQLAlchemy/Postgres)** — unnecessary at current corpus scale; revisit post-1.0
  if WP4 produces corpora that demand it.
- **Web demo / explorer** — explicitly low priority per the maintainer; the linearaworkbench web app
  already covers the visual Linear A use case. Parked post-0.8.0; the CLI (WP2) is the adoption play.
- **CLTK compatibility layer** — deliberate independence; the benchmark harness already scores any
  external callable on shared gold, which is the interoperability that matters for evaluation.
- **Stale review observations** (predate the hardening pass): EpiDoc round-tripping is now
  schema-valid with editorial status (deeper apparatus support continues in WP4); the scansion docs
  already state that synizesis is declined, not inferred (WP1 makes the statement uniform).

## Release checklist — `v0.8.0`

1. WP1–WP6 complete; WP3 definition-of-done met (WP7–WP9 items that slip become 0.8.x patches).
2. Full gate: ruff, mypy, pytest, footprint (import-clean / import-fast / wheel), notebooks, CI matrix.
3. CHANGELOG: fold the program into `## 0.8.0`; date it.
4. GitHub Release, tag `v0.8.0` → OIDC publish to PyPI (versions are never reused).
5. Zenodo mints the first concept+version DOI → wire the DOI badge into README, `CITATION.cff`,
   and the BibTeX block.

## Post-0.8.0 → 1.0

The first three items below come straight from the
[Limitations](https://github.com/ryanpavlicek/pyaegean/wiki/Limitations) inventory — engineering
limits a release cycle can lift:

- **Iambic and lyric scansion + a synizesis lexicon.** Extend `meter` beyond dactylic
  hexameter/elegiac pentameter (iambic trimeter first), and curate a lexicalised **synizesis
  lexicon** on the syllabification-exception pattern (test-enforced entries, contribution-friendly) —
  so the lines that today honestly fail to scan can scan honestly.
- **Morpheus-backed offline morphology.** Fold Morpheus's morphological tables (per applicable
  license; NOTICE carries the forward attribution) into the zero-dependency rule tier, closing the
  irregular/third-declension/contract gaps and restoring accents on reconstructed lemmas without
  requiring the treebank or neural backends.
- **Shrink the neural pipeline model.** Selective quantization of `grc-joint` (518 MB fp32 today;
  whole-model int8 failed the ≤0.3-point accuracy gate and was rejected) — per-component int8/fp16
  under the same gate — plus optional GPU execution providers for onnxruntime.
- **JOSS paper** (the methods write-up 1.0 waits on) — the WP3 benchmark protocol is half the paper;
  seed-variance repeats for the tight margins belong to this write-up.
- **Workbench bridge**: `aegean workbench` fetches + serves the linearaworkbench static build
  (release-asset, fetch-to-cache).
- **Koine / Biblical Greek track**: NT corpus loader + Koine-tuned lemma/morphology
  (MorphGNT/SBLGNT/Nestle1904), building on the Koine phonology mode.
- **Web demo** (parked above) if adoption warrants.
- **1.0 criteria**: evidence of external use + the methods write-up submitted + an API-freeze review.

## Traceability — external review → work packages

| Reviewer item | Where |
|---|---|
| CLI | **WP2** |
| Web demo/explorer | Parked (per maintainer) |
| Convenience `pipeline()`/`analyze()` | WP1 |
| Syllabification exceptions | WP1 |
| Scansion doc clarity | WP1 (verified largely stale) |
| Defensive normalization for messy text | WP1 |
| Neural methodology transparency | WP3.1 (benchmarks doc + notebook) |
| Data versioning / reproducibility | WP4 |
| User-provided corpora as framework | WP4 |
| Variant readings & paleography | WP4 |
| Visualization helpers | WP5 |
| Phonetic/comparative tools | WP5 |
| Statistics / hypothesis testing | WP5 |
| Grounding traceability | WP6 |
| Structured AI outputs | WP6 |
| Grounded-generation eval harness | WP6 |
| Expert validation loop | WP6 |
| Smart caching | WP7 |
| Lazy/streaming corpora | WP7 (design note; deferred) |
| Pydantic/msgspec | Declined (zero-dep invariant) |
| Deeper EpiDoc round-tripping | Done (schema-valid + `ReadingStatus`); apparatus depth in WP4 |
| Database backend | Parked post-1.0 |
| Citation automation | WP1 |
| CONTRIBUTING pathways + deprecation policy | WP1 |
| Scholarly recipes | WP9 |
