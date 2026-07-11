# Choosing a workflow

pyaegean gives you many corpora, several analysis tiers, and a range of output
formats. This page starts from the practical question, *who are you and what do
you want out of the toolkit*, and routes you to a whole working sequence: which
corpus, which pipeline, how much detail to keep, how to catch and correct
errors, and how to cite the result.

It sits one level above [Choosing a Pipeline](Choosing-a-Pipeline), which
answers the narrower question of which analysis tier to run on a given text.
This page chains that choice together with output verbosity, the correction
loop, and citation into an end-to-end workflow, then points you into the
matching walkthrough in [Recipes](Recipes).

A workflow here is a sequence you assemble from the toolkit's ordinary calls and
flags, not a single global setting. You pick a corpus, activate a pipeline tier
(or leave the offline baseline in place), decide how much of the analysis to
keep, and choose a citation. Each step is a normal call, so you can mix and
match freely across the four shapes below.

## At a glance

| Audience / goal | The shape of the workflow | Read on |
| --- | --- | --- |
| **Teaching and demonstration** | Bundled samples, the offline baseline first so the uncertainty is visible, then a stronger tier for contrast; keep parses readable. | [§ Teaching](#teaching-and-demonstration) |
| **Research toward a citable result** | The edition your question needs, the highest tier you can run, full per-token records, review the flagged tokens, cite the exact subset. | [§ Research](#research-toward-a-citable-result) |
| **Exploratory decipherment** | The undeciphered scripts, structure tools tested against null models, every result kept under its exploratory label, never a reading. | [§ Exploratory](#exploratory-decipherment) |
| **Reproducible benchmarking** | The evaluation folds, a fixed protocol, pinned data, evaluation receipts, the claims registry. | [§ Benchmarking](#reproducible-benchmarking) |

## Three things every workflow settles

Whatever your goal, a workflow makes three decisions. The four sections that
follow are really just four ways of setting these three dials.

### 1. Which pipeline tier

The Greek stack has a baseline and two opt-in tiers you activate with a single
call (or the matching CLI flag):

- **Offline baseline** (zero dependencies, the default): `greek.pipeline(text)`
  with no backend active. The honest floor.
- **Attested-gold**: `greek.use_treebank()` (CLI `--treebank`), a lookup in the
  Perseus treebank lexicon.
- **Trained pure-Python**: `greek.use_tagger()`, then `greek.use_lemmatizer()`
  and `greek.use_parser()`, which generalize beyond the lookup.
- **Neural**: `greek.use_neural_pipeline()` (the `[neural]` extra, CLI
  `--neural`), one model that fills part of speech, morphology, lemma, and a
  dependency tree per token. The neural pipeline, not the baseline, carries the
  accuracy claims.

[Choosing a Pipeline](Choosing-a-Pipeline) weighs the tiers against your text
type and constraints; [Greek NLP → the stages at a glance](Greek-NLP#the-stages-at-a-glance)
and [Benchmarks](Benchmarks) give the measured accuracy of each.

### 2. How much detail to keep

Output verbosity is a dial, from a bare lemma to a correctable table. Turn it up
as far as your goal needs and no further:

| You want… | Use | What you get |
| --- | --- | --- |
| Just the lemma | `greek.lemmatize(word)` | the citation form as a string |
| The lemma and how it was reached | `greek.lemmatize_sourced(word)` | `(lemma, LemmaSource)`; `greek.needs_review(source)` gives a triage flag, and `greek.lemmatize_verbose` a plain `(lemma, known)` bool |
| A full per-token analysis | `greek.pipeline(text)` | one `TokenRecord` per token carrying `lemma_source`, `lemma_known`, plus `head` / `relation` (under a parser or the neural pipeline) and `xpos` / `feats` (neural pipeline only) |
| A table you can correct | `aegean review export` → fix → `aegean review apply` | machine annotations with a `needs_review` column, corrected columns, and a stamped reviewer |

The evidence class (`LemmaSource`: `attested`, `neural`, `rule`, `seed`,
`paradigm`, `identity`, `unresolved`, `punct`) is the key to reading a parse: an `identity`
or `unresolved` lemma is the pipeline flagging a token you should check.
[Reading a Parse](Reading-a-Parse) explains every field, and
[When the Tool Is Wrong](When-the-Tool-Is-Wrong) covers the export / fix /
re-import loop in full.

### 3. How to cite

Every corpus and every subset carries its provenance, so you cite exactly what
you used:

- `corpus.cite()` (and `.filter(...).cite()`, `QueryResults.cite()`) records the
  edition, the licence, and the filter or query behind a subset.
- `aegean.__version__` and `CITATION.cff` pin the tool release.
- An evaluation receipt (`greek.eval_receipt`) records the settings behind any
  accuracy figure you report.
- Reviewed output keeps each machine value under a `<field>__pred` key and a
  `review:` provenance note, so you can say which fields were machine-produced
  and human-corrected.

The full how-to, including a worked methods-section phrasing, is on
[Citing Computational Assistance](Citing-Computational-Assistance).

---

## Teaching and demonstration

*You want to show how automated analysis works, and where it is unsure, on
examples a class can read.*

- **Corpus.** The bundled sample corpora and the offline NT sample (John 1 and
  Philemon) work with no fetch, so a lesson runs anywhere. For a real passage,
  fetch a single work once (`aegean greek work tlg0012.tlg001`).
- **Pipeline.** Start on the zero-dependency baseline, because the point of
  teaching is the contrast: on the baseline the evidence classes are visible (a
  `seed` article, a `rule` guess on a regular ending, an `unresolved` form the
  tool cannot handle), and then the same passage improves when you switch on
  `use_treebank()` or `use_neural_pipeline()`. Running more than one tier is the
  lesson.
- **Verbosity.** Use `greek.pipeline` and show `lemma_source` alongside each
  lemma; `needs_review` turns "trust this one, check that one" into something a
  student can see. [Reading a Parse](Reading-a-Parse) is written for exactly
  this reader.
- **Cite.** Even a classroom example should name its edition, so end with
  `corpus.cite()`; it models the habit.
- **Start from.** The [Tutorial](Tutorial) for the guided tour, then
  [Reading a Parse](Reading-a-Parse), and the single-move recipes for scansion,
  syllabification, and the Greek-reading bridge in [Recipes](Recipes).

## Research toward a citable result

*You want an annotation, a statistic, or a subset that will go into a paper.*

- **Corpus.** The edition your question needs: a literary work
  (`greek.load_work`), the Koine New Testament with its gold annotations
  (`greek.load_nt`), or one of the epigraphic and documentary corpora
  (`isicily`, `iip`, `iospe`, `igcyr`, `edh`, `ddbdp`). For inscriptions and
  papyri, keep the editorial apparatus in view: tokens carry a `ReadingStatus`
  and each corpus an `edition_fidelity` flag (see
  [Using Critical Editions](Using-Critical-Editions)). The Duke Databank
  (`ddbdp`) is a search-and-stream corpus, not one to load into memory; recipe B
  shows the method.
- **Pipeline.** The highest tier you can run: `use_treebank()` for attested-gold
  lemmas, or `use_neural_pipeline()` for the highest measured accuracy.
  [Choosing a Pipeline](Choosing-a-Pipeline) weighs them for your text, and
  [Benchmarks](Benchmarks) reports how far each generalizes off Classical
  literary Greek.
- **Verbosity.** Keep full `TokenRecord`s. Triage with `needs_review` or
  `lemma_known`, and for anything you will publish, run the human-in-the-loop
  step: `aegean review export` (add `--only-needs-review` to see just the flagged
  tokens), correct the table, and `aegean review apply`. The corrected corpus
  records what a human changed. See
  [When the Tool Is Wrong](When-the-Tool-Is-Wrong).
- **Cite.** `cite()` on the exact subset, `aegean.__version__`, and an
  `eval_receipt` for any accuracy figure. State which fields were
  machine-produced and reviewed, per
  [Citing Computational Assistance](Citing-Computational-Assistance).
- **Start from.** The persona walkthroughs in
  [Recipes → Workflows: end to end](Recipes#workflows-end-to-end):
  [the epigraphist](Recipes#a--the-epigraphist-from-a-site-filter-to-a-citable-subset),
  [the papyrologist](Recipes#b--the-papyrologist-ddbdp-without-loading-it),
  [the literary classicist](Recipes#c--the-literary-classicist-catalogue-metre-gloss-citation),
  [the New Testament scholar](Recipes#d--the-new-testament-scholar-gold-morphology-to-concordance),
  [the corpus linguist](Recipes#e--the-corpus-linguist-numbers-with-a-receipt), and
  [the toolsmith](Recipes#h--the-toolsmith-one-database-and-tools-for-agents).

## Exploratory decipherment

*You want to hunt for structure in undeciphered material without asserting a
reading.*

- **Corpus.** Linear A (`lineara`) and Cypro-Minoan (`cyprominoan`). For a
  deciphered contrast, Linear B and Cypriot do read as Greek through the bridge
  (`aegean bridge`), but that is established data, a different register from
  anything below.
- **Pipeline.** There is no reading pipeline for the undeciphered scripts, and
  deliberately no Greek-reading bridge for Linear A. Start from what is secure
  (the accounting shape, the sign inventory), then use the exploratory analysis
  tools (morphological clusters, dispersion, sign surprisal, the structure
  classifier), and test every hunch against a null model so a pattern is not
  mistaken for a result. A negative is a result too.
- **Verbosity and labeling.** Exploratory output carries an `[EXPLORATORY …]`
  label and an auditable `trace()`; keep the label with the result. Any AI-layer
  hypothesis is grounded and inspectable before a provider key is involved, and
  is a labeled hypothesis, never a reading.
- **Cite.** Present exploratory output as hypotheses generated with
  computational assistance, carrying the label, and let the `trace()` travel so
  others can confirm or refute it. See
  [Citing Computational Assistance](Citing-Computational-Assistance) and the
  validation path in [For Specialists](For-Specialists).
- **Start from.**
  [the Aegean-scripts researcher](Recipes#f--the-aegean-scripts-researcher-exploratory-and-labeled-as-such),
  and, if key-gated generation is in play,
  [the AI-assisted translator](Recipes#g--the-ai-assisted-translator-key-gated).

## Reproducible benchmarking

*You want to measure accuracy, or reproduce or challenge a published number.*

- **Data.** The Universal Dependencies Ancient Greek folds (UD-Perseus,
  UD-PROIEL) and the Nestle 1904 NT gold. These are fetched for evaluation only,
  never trained on; the leakage controls are documented on
  [Methodology → leakage control](Methodology#3-leakage-control).
- **Pipeline.** `use_neural_pipeline()` for the headline numbers. The offline
  stack is reported as a floor, with an in-training upper-bound caveat on the
  Perseus fold.
- **How to run.** `greek.evaluate_on_ud("perseus", "test")` and
  `evaluate_on_proiel` / `evaluate_on_nt` for the folds; `greek.bootstrap_ud`
  for a confidence interval; `aegean greek eval … --drift` for an error analysis
  instead of a single score; and `greek.evaluate_by_genre` (CLI
  `aegean greek eval ud --by-genre`) for a genre slice.
- **Reproducibility.** Pin the data with `data.versions()` (CLI
  `aegean data versions`) and record `aegean.__version__`. Every published number
  lives in the claims registry (`training/results/published-claims.json`) and is
  pinned to the docs, so a documented figure cannot drift silently.
- **Cite.** Attach an `eval_receipt` to any number you report, and cite the
  number with its protocol, not on its own
  ([Citing Computational Assistance](Citing-Computational-Assistance)).
- **Start from.** [Benchmarks](Benchmarks) for the protocol and the field's
  published numbers, [Methodology](Methodology) for the whole picture in one
  place, and [the corpus linguist](Recipes#e--the-corpus-linguist-numbers-with-a-receipt)
  for the "numbers with a receipt" discipline, applied here to model accuracy.

## See also

- [Choosing a Pipeline](Choosing-a-Pipeline): which analysis tier to run on a
  given text.
- [Recipes](Recipes): the single-move task recipes and the eight end-to-end
  persona walkthroughs this page routes into.
- [Reading a Parse](Reading-a-Parse): the per-token fields and the evidence
  classes.
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): the kinds of error to expect
  and the correction loop.
- [Citing Computational Assistance](Citing-Computational-Assistance): citing the
  corpus, the version, a measured number, and reviewed output.
- [Benchmarks](Benchmarks) and [Methodology](Methodology): the measured numbers
  and the protocol behind them.
- [For Specialists](For-Specialists): the register model and how to submit a
  correction or a validation.
