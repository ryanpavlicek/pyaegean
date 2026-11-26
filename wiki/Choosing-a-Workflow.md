# Choosing a Workflow

This page maps common research and teaching goals to a complete sequence of
pyaegean steps: which corpus to load, which analysis tier to enable, how much
per-token detail to keep, how to review and correct annotations, and how to
package and cite results.

[Choosing a Pipeline](Choosing-a-Pipeline) answers the narrower question of
which Greek backend fits a given text. This page combines backend selection
with review, packaging, and citation, then points to matching walkthroughs in
[Recipes](Recipes).

You assemble a workflow from ordinary API calls and CLI flags; there is no
global mode switch. Pick a corpus, enable a backend (or stay on the offline
baseline), select your output and review path, and record citations.

## Summary

| Goal | Workflow | Details |
| --- | --- | --- |
| **Teaching and demonstration** | Bundled samples, offline baseline first so fallback rules are visible, then a stronger backend for contrast. | [§ Teaching](#teaching-and-demonstration) |
| **Research toward a citable result** | Edition matching your question, highest suitable backend, full per-token records, human review of annotations, portable research bundle and subset citation. | [§ Research](#research-toward-a-citable-result) |
| **Exploratory decipherment** | Undeciphered corpora (`lineara`, `cyprominoan`), structural tools tested against null models, exploratory labels retained on every output. | [§ Exploratory](#exploratory-decipherment) |
| **Reproducible benchmarking** | Locked evaluation folds, fixed protocol, pinned datasets, evaluation receipts, and the claims registry. | [§ Benchmarking](#reproducible-benchmarking) |

## Three decisions every workflow makes

### 1. Which pipeline tier

The Greek stack provides a zero-dependency default plus three opt-in tiers
activated with a single call or CLI flag:

- **Offline baseline** (zero dependencies, default): `greek.pipeline(text)`
  with no extra backend enabled.
- **Attested-gold lookup**: `greek.use_treebank()` (CLI `--treebank`), serving
  attested lemmas, morphology, and POS from the Perseus treebank lexicon.
- **Trained pure-Python**: `greek.use_tagger()`, `greek.use_lemmatizer()`, and
  `greek.use_parser()`, generalizing beyond lookup without heavy dependencies.
- **Neural**: `greek.use_neural_pipeline()` (`[neural]` extra, CLI `--neural`),
  predicting UPOS, UD FEATS, lemma, and dependency trees in one pass. Published
  benchmark figures apply to the neural pipeline.

[Choosing a Pipeline](Choosing-a-Pipeline) compares these tiers by material and
constraints; [Greek NLP](Greek-NLP) and [Benchmarks](Benchmarks) report
measured accuracy for each.

### 2. How much detail to keep and review

Choose the output granularity your task requires:

| Need | API / CLI | Output |
| --- | --- | --- |
| Lemma only | `greek.lemmatize(word)` | citation form string |
| Lemma with provenance | `greek.lemmatize_sourced(word)` | `(lemma, LemmaSource)`; `greek.needs_review(source)` flags fallbacks; `greek.lemmatize_verbose` returns `(lemma, known)` |
| Full per-token analysis | `greek.pipeline(text)` | one `TokenRecord` per token with `lemma_source`, `lemma_resolved`, `lemma_verified`, and `review_recommended`, plus `head` / `relation` (with a parser or neural backend) and `xpos` / `feats` (neural only) |
| Editable review table | `aegean review export` → edit → `aegean review apply` | CSV/editable spreadsheet with `needs_review`, corrected fields, and stamped reviewer metadata |
| Interactive terminal review & conflict adjudication | `aegean tui --review` (or `r` in `aegean tui`) | field-level inspection, sentence context, calibrated-risk ordering, and multi-reviewer conflict resolution |

Each `LemmaSource` (`attested`, `neural_lookup`, `neural_edit`, generic
`neural`, `rule`, `seed`, `paradigm`, `identity`, `unresolved`, `punct`, or
`user`) records how a lemma was produced. Tokens marked `identity` or
`unresolved` warrant inspection; resolved predictions can also contain errors.
See [Reading a Parse](Reading-a-Parse) and
[When the Tool Is Wrong](When-the-Tool-Is-Wrong).

### 3. How to package and cite

Every corpus, subset, and bundle records its provenance:

- `corpus.cite()`, `.filter(...).cite()`, and `QueryResults.cite()` record the
  edition, license, and exact filter or query.
- `aegean.__version__` and `CITATION.cff` pin the toolkit release.
- `greek.eval_receipt` records the protocol and settings behind any measured
  accuracy figure.
- Reviewed corpora store machine predictions alongside corrections under
  `<field>__pred` keys with a `review:` provenance note.
- Portable research bundles (`aegean.bundle` / `aegean bundle create|inspect|verify|extract|hydrate`)
  package redistributable corpora (or SHA-256 retrieval pointers for
  non-commercial datasets), citations (`CITATIONS.bib`, `CITATIONS.txt`),
  workbench workspace backups, editable review tables, and evaluation receipts
  into one deterministic, SHA-256-verified `.zip` archive.

See [Citing Computational Assistance](Citing-Computational-Assistance) for
worked methods-section wording.

---

## Teaching and demonstration

*Show how automated Greek or Aegean analysis behaves and where heuristics fail.*

- **Corpus.** Bundled sample corpora, the bundled NT sample (`John 1`, `Phlm 1`),
  and the bundled Swete LXX sample (`Gen 1:1–5`, `Ps 22:1–6`) run offline
  (`from aegean.greek import bible`). To demonstrate a full literary passage,
  fetch one work once (`aegean greek work tlg0012.tlg001`).
- **Pipeline.** Run the zero-dependency baseline first so students can inspect
  evidence classes (`seed` articles, `rule` guesses on regular endings,
  `unresolved` irregular forms), then enable `use_treebank()` or
  `use_neural_pipeline()` on the same passage to show the contrast.
- **Detail.** Call `greek.pipeline()` and display `lemma_source` next to each
  lemma. `needs_review` isolates identity/unresolved fallbacks; check resolved
  rows as well, since heuristic tags can be wrong even when a lemma resolves.
  See [Reading a Parse](Reading-a-Parse).
- **Citation.** End classroom examples with `corpus.cite()` so students see the
  edition and license attached to every dataset.
- **Start with:** [Tutorial](Tutorial), [Reading a Parse](Reading-a-Parse), and
  the single-task examples in [Recipes](Recipes).

## Research toward a citable result

*Produce an annotated subset, lexical statistic, or corpus export for
publication.*

- **Corpus.** Load the edition your question requires: a literary work
  (`greek.load_work`), a Greek New Testament or Septuagint passage
  (`from aegean.greek import bible` → `bible.load_nt`, `bible.load_lxx`),
  Patristic or Byzantine texts (`patrologia`, `apostolic-fathers`,
  `pseudepigrapha`, `byzantine`, `homer-scholia`), or any of the seven Greek
  epigraphic corpora (`isicily`, `iip`, `iospe`, `igcyr`, `aphrodisias`,
  `crete`, `edh`) and `ddbdp` documentary papyri. Install themed packs with
  `aegean library install <pack>` (or individual datasets with `aegean data`).
  For inscriptions and papyri, preserve the apparatus (`ReadingStatus` and
  `edition_fidelity`; see [Using Critical Editions](Using-Critical-Editions)).
  Query or stream `ddbdp` via `aegean find` / `aegean.db` instead of loading
  all 57,331 texts into memory.
- **Pipeline.** Use `use_treebank()` for attested-gold lemmas with minimal
  dependencies, or `use_neural_pipeline()` for the highest measured accuracy
  across UPOS, morphology, lemmas, and syntax. Check
  [Choosing a Pipeline](Choosing-a-Pipeline) and [Benchmarks](Benchmarks) for
  out-of-domain accuracy outside Classical literary prose.
- **Review.** Retain full `TokenRecord` outputs. `review_recommended` catches
  only `identity` and `unresolved` lemmas and does not verify correctness. For
  publishable annotations, review tokens either through spreadsheet round-trips
  (`aegean review export` with `--selection all|flagged|unverified` → edit →
  `aegean review apply`) or directly in the terminal with `aegean tui --review`
  (`r` key in `aegean tui`), which supports single-reviewer editing and
  multi-reviewer conflict adjudication. See
  [When the Tool Is Wrong](When-the-Tool-Is-Wrong).
- **Package and cite.** Record `cite()` on the exact subset,
  `aegean.__version__`, and an `eval_receipt` for any reported accuracy score.
  State which fields were machine-predicted and human-reviewed
  ([Citing Computational Assistance](Citing-Computational-Assistance)). Use
  `aegean bundle create` to archive a SHA-256-verified, license-clean snapshot
  for supplementary materials or collaborators.
- **Start with:** the end-to-end workflows in
  [Recipes → Workflows: end to end](Recipes#workflows-end-to-end):
  [epigraphist](Recipes#a--the-epigraphist-from-a-site-filter-to-a-citable-subset),
  [papyrologist](Recipes#b--the-papyrologist-ddbdp-without-loading-it),
  [literary classicist](Recipes#c--the-literary-classicist-catalogue-metre-gloss-citation),
  [New Testament scholar](Recipes#d--the-new-testament-scholar-gold-morphology-to-concordance),
  [corpus linguist](Recipes#e--the-corpus-linguist-numbers-with-a-receipt), and
  [toolsmith](Recipes#h--the-toolsmith-one-database-and-tools-for-agents).

## Exploratory decipherment

*Investigate structural patterns in undeciphered Aegean material without
claiming deciphered readings.*

- **Corpus.** Linear A (`lineara`, `sigla`) and Cypro-Minoan (`cyprominoan`).
  Linear B (`linearb`, `damos`) and Cypriot (`cypriot`) are deciphered and
  support the Greek-reading bridge (`aegean bridge`), providing a deciphered
  comparative baseline.
- **Tools.** Linear A and Cypro-Minoan have no reading pipeline or Greek
  bridge. Start from established data (sign inventories, accounting structure),
  apply exploratory quantitative tools (morphological clustering, dispersion,
  sign surprisal, structure classification), and test patterns against null
  models; a null result is still informative. To inspect any of the four Aegean
  scripts visually in the browser (`workbench-app-v2.1.0`), run
  `aegean workbench --corpus <id-or-path>` or export a multi-script bundle with
  `aegean.io.to_workbench_bundle`.
- **Labeling.** Exploratory and AI-assisted outputs carry `[EXPLORATORY …]`
  labels and an inspectable `trace()`. Keep the label attached to derived
  results; AI hypotheses remain exploratory and unverified until a specialist
  evaluates them.
- **Citation.** Report exploratory outputs as computationally generated
  hypotheses with their `trace()` preserved so others can verify or refute
  them. See [Citing Computational Assistance](Citing-Computational-Assistance)
  and [For Specialists](For-Specialists).
- **Start with:**
  [Aegean-scripts researcher](Recipes#f--the-aegean-scripts-researcher-exploratory-and-labeled-as-such)
  and, if generative assistance is used,
  [AI-assisted translator](Recipes#g--the-ai-assisted-translator-key-gated).

## Reproducible benchmarking

*Measure accuracy, reproduce published scores, or audit error classes.*

- **Data.** Universal Dependencies Ancient Greek folds (UD-Perseus, UD-PROIEL),
  Nestle 1904 NT gold, and domain evaluation folds. Evaluation folds are
  leakage-checked and never used in training; see
  [Methodology → leakage control](Methodology#3-leakage-control).
- **Pipeline.** Use `use_neural_pipeline()` for published benchmark scores. The
  offline stack provides a floor (noting in-training overlap caveats where
  applicable on Perseus).
- **Execution.** Run `greek.evaluate_on_ud("perseus", "test")`,
  `evaluate_on_proiel`, and `evaluate_on_nt`; compute confidence intervals with
  `greek.bootstrap_ud`; inspect per-category errors with
  `aegean greek eval … --drift`; and slice by genre with
  `greek.evaluate_by_genre` (`aegean greek eval ud --by-genre --neural`).
- **Reproducibility.** Pin datasets with `data.versions()` (`aegean data versions`)
  and record `aegean.__version__`. Published figures live in
  `training/results/published-claims.json` and are checked against documentation
  by the test suite.
- **Citation.** Attach an `eval_receipt` and report each figure alongside its
  evaluation protocol
  ([Citing Computational Assistance](Citing-Computational-Assistance)). Package
  receipts and manifests into a verifiable `.zip` with `aegean bundle create`.
- **Start with:** [Benchmarks](Benchmarks), [Methodology](Methodology), and
  [corpus linguist](Recipes#e--the-corpus-linguist-numbers-with-a-receipt).

## See also

- [Choosing a Pipeline](Choosing-a-Pipeline): selecting a Greek backend by text
  type and constraints.
- [Recipes](Recipes): single-task recipes and eight end-to-end walkthroughs.
- [Reading a Parse](Reading-a-Parse): token fields and `LemmaSource` evidence
  classes.
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): common error classes and
  the review loop.
- [Citing Computational Assistance](Citing-Computational-Assistance): citing
  corpora, tool versions, evaluation scores, and human-reviewed annotations.
- [Benchmarks](Benchmarks) and [Methodology](Methodology): published scores and
  evaluation protocol.
- [For Specialists](For-Specialists): established vs. exploratory surfaces and
  how to submit corrections.
