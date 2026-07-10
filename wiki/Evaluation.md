# Evaluation

This page documents pyaegean's **evaluation infrastructure**: how the Greek
pipeline is scored, on which gold data, under which protocol, and with which
integrity guarantees. Every accuracy number the project publishes comes out of
these functions, and every one is designed to be **reproducible** (fetched,
pinned, hashable gold), **leakage-free** (nothing the model trained on is scored
as if unseen), and **honest** (convention gaps are separated from real error, and
the caveats travel with the number).

Three properties run through all of it:

- **Standard tooling, not a bespoke scorer.** The Universal Dependencies folds are
  scored with the *official CoNLL 2018 shared-task evaluator*, fetched and pinned
  by sha256, so the numbers sit on the same measuring stick the field uses.
- **Leakage is controlled, not assumed away.** UD Ancient Greek (Perseus) is
  converted from the AGDT that pyaegean's backends learn from, so a leakage manifest
  enumerates exactly which sentences must stay out of training, and the shipped
  neural model honours it.
- **Evaluation-only data stays evaluation-only.** The UD and PROIEL treebanks are
  fetched to the cache for scoring, never bundled and never trained on. Their
  NonCommercial + ShareAlike terms are respected.

The Greek pipeline itself, and the backends these functions score, are documented on
[Greek NLP](Greek-NLP); the provenance and licences of every fetched dataset are on
[Data & Provenance](Data-and-Provenance); the full protocol, comparison tables, and
measured numbers with citations live in the methodology and benchmarks record,
[Benchmarks](Benchmarks).

## The evaluators at a glance

Every evaluator scores **whatever backends are active** when you call it, so activate
what you want measured first (`use_treebank`, `use_tagger`, `use_lemmatizer`,
`use_neural_lemmatizer`, `use_neural_pipeline`, `use_parser`; see
[Greek NLP](Greek-NLP)). Each has a CLI mirror under `aegean greek eval`.

| Evaluator | Python | Gold | What it answers |
| --- | --- | --- | --- |
| Standard benchmark | `evaluate_on_ud` | UD Ancient Greek (Perseus / PROIEL), official CoNLL 2018 scorer | the field-standard UPOS / UFeats / Lemma / UAS / LAS |
| Sampling variability | `bootstrap_ud` | same folds | percentile confidence intervals over the fold's sentences |
| Neutral out-of-AGDT | `evaluate_on_proiel` | PROIEL treebank (NT + Herodotus) | how pyaegean reads Greek it never trained on |
| Error analysis | `proiel_error_analysis` / `ud_error_analysis` / `nt_error_analysis` / `heldout_error_analysis` (and `proiel_drift`) | any gold fold | the kinds of error: POS confusion matrix, per-POS accuracy, lemma confusions, seen/unseen (see [When the Tool Is Wrong](When-the-Tool-Is-Wrong)) |
| Out-of-domain Koine | `evaluate_on_nt` | Nestle 1904 own gold | the shipped neural model on the Greek NT |
| Held-out (in-AGDT) | `evaluate_tagger` / `evaluate_lemmatizer` / `evaluate_parser` | 90/10 AGDT sentence split | leakage-free generalization of each trainable backend |
| Leakage manifest | `agdt_ud_overlap` | AGDT ↔ UD-Perseus | which sentences training must exclude |
| Reproducibility receipt | `eval_receipt` | any scores dict | a content-addressed, tamper-evident record of a result |

The held-out `evaluate_tagger` / `evaluate_lemmatizer` / `evaluate_parser`
evaluations (the leakage-free 90/10 AGDT split, with an unseen-form subset called
out separately) are documented alongside their backends on
[Greek NLP](Greek-NLP#held-out-generalization). This page covers the
gold-benchmark, out-of-domain, leakage, and receipt infrastructure.

## Standard-benchmark evaluation: `evaluate_on_ud`

`evaluate_on_ud(treebank, split)` scores the active pipeline on a **Universal
Dependencies** Ancient Greek test fold with the **official CoNLL 2018 shared-task
evaluator**. `treebank` is `"perseus"` or `"proiel"`; `split` is `"train"`,
`"dev"`, or `"test"`. The fold is fetched to the cache on first use (pinned to a
fixed commit) and scored where it lands.

```python
from aegean import greek

greek.use_neural_pipeline()                 # score the shipped model (the [neural] extra)
scores = greek.evaluate_on_ud("perseus", "test")
# {'treebank': 'perseus', 'split': 'test', 'parsed': True,
#  'upos': …, 'xpos': …, 'ufeats': …, 'lemma': …,
#  'uas': …, 'las': …, 'clas': …, 'n_words': …, 'n_sentences': …}
```

The returned dict is metric to accuracy in `[0, 1]`, plus the fold's word and
sentence counts. `parse` defaults to whether a parser is active (the neural
pipeline or `use_parser`); with `parse=False`, `uas`/`las`/`clas` come back as
`None`. `xpos` and `ufeats` are only meaningful under the neural pipeline (the
pure-Python cascade does not emit those columns, so they score as empty against
gold).

**The measured headline** (UD Ancient Greek Perseus test, neural pipeline,
end-to-end from raw text, tokens F1 99.97):

| UD Perseus test | UPOS | UFeats | Lemma | UAS | LAS |
| --- | --- | --- | --- | --- | --- |
| neural pipeline | 97.0 | 96.0 | 94.3 | 90.2 | 85.6 |

The full protocol, the comparison tables against other systems, and the
out-of-domain PROIEL-test figures (lemma 90.51, UAS 82.48, UPOS 86.69) are in
[Benchmarks](Benchmarks).

### The protocol, in short

The measurement choices are deliberate, and each one makes the number *harder*
rather than flattering:

- **Gold tokenization.** The pipeline runs over each fold's gold `FORM` column, so
  the scores measure tagging, lemma, and parsing quality, not tokenizer agreement.
- **No tagset collapsing.** UPOS and lemmas are scored exactly as the pipeline
  emits them, with no reconciliation against UD conventions, so convention gaps
  count against the score rather than being smoothed away. (This is the opposite
  choice from `evaluate_on_proiel` below, which *does* reconcile, because there the
  question is different.)
- **Dependency labels.** The shipped neural pipeline emits **UD relations**, so
  **LAS** is scored directly against UD gold. The legacy pure-Python arc-eager
  parser emits AGDT/Prague labels, for which only **UAS** is comparable; it is
  reported as a baseline, not as the accuracy claim.

### The official CoNLL 2018 scorer, pinned

pyaegean does not ship its own scorer for the UD folds. `evaluate_on_ud` fetches
the **official `conll18_ud_eval.py`** (the CoNLL 2018 shared-task evaluator,
MPL-2.0) once, verifies it against a pinned sha256
(`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`), caches it,
and imports it from there. The pipeline's CoNLL-U output is scored by that exact
module, so the numbers are on the same instrument as the field's published
results, and a swapped or tampered scorer fails the hash check before it can run.

The gold folds are pinned too: each UD treebank is fetched from a fixed upstream
commit, so a re-run reads byte-identical data. `greek.ud.ud_path(treebank, split)`
returns the cached fold path (fetching on first use), and `greek.ud.load_conllu(path)`
parses a CoNLL-U file into `UDSentence` / `UDToken` objects (multiword-token
ranges and empty nodes are skipped, so each sentence holds exactly the syntactic
words the evaluator scores).

## Confidence intervals: `bootstrap_ud`

A single accuracy is a point estimate; `bootstrap_ud` reports the sampling
variability around it. The active pipeline runs **once** over the fold, then each
of `n_resamples` draws re-scores a sentence resample (with replacement) through the
official evaluator, giving a percentile confidence interval per metric.

```python
greek.use_neural_pipeline()
cis = greek.bootstrap_ud("perseus", "test")      # {'upos': BootstrapCI, 'lemma': …, 'las': …, …}
cis["las"].estimate, cis["las"].low, cis["las"].high
```

The **sentence** is the resampling unit (tokens within a sentence are not
independent), matching the standard practice for treebank metrics. Defaults are
`n_resamples=999`, `level=0.95`, `seed=0` (so the band is reproducible); `metrics`
selects which to report, and with no parser active `uas`/`las` are dropped. Each
value is a `BootstrapCI` (see [Analysis](Analysis) for the stats layer). The band
describes sampling variability *given this fold*, not uncertainty about the model
in general.

## Neutral, out-of-AGDT evaluation: `evaluate_on_proiel`

The held-out AGDT numbers are leakage-free *within* the AGDT, but every pyaegean
backend is built from the AGDT, so they do not show how the system fares on text
from a **different** source. `evaluate_on_proiel` closes that gap: it scores the
active pipeline against the **PROIEL treebank** (the Greek New Testament and
Herodotus, independently annotated), which none of pyaegean's models has ever
seen. Every form there is a genuine generalization test.

```python
from aegean import greek
greek.use_treebank(); greek.use_neural_lemmatizer()   # measure the full pipeline
greek.evaluate_on_proiel()        # {'lemma': …, 'pos': …, 'n': …} over the PROIEL gold
```

`tag_sentence` maps a sentence's forms to `(lemma, pos)` per token and defaults to
pyaegean's current pipeline, honouring whichever backends are active. Two honesty
choices shape the metrics:

- **Lemma is the clean metric.** Lemmas are compared after Unicode normalization and
  after dropping PROIEL's `#N` homograph suffix (`εἰμί#1` becomes `εἰμί`), so a lemma
  match measures agreement, not annotation formatting.
- **POS is scored under a reconciled tagset.** PROIEL's UD-only distinctions collapse
  on *both* gold and prediction (PROPN to NOUN, SCONJ to CCONJ, AUX to VERB), so the
  POS figure reflects real disagreement rather than a Robinson-vs-UD convention gap.
  Punctuation and numerals are not scored, matching the held-out AGDT evaluation.

This is a neutral check **for pyaegean specifically**. PROIEL is *in-training* for
some other systems (for example stanza's `grc_proiel` model), so it is not a level
field for cross-tool comparison; it answers "how well does pyaegean read Greek it
never trained on." Cite Haug & Jøhndal (2008) for PROIEL.

`greek.load_proiel_gold()` returns the parsed gold sentences directly, and
`greek.proiel_dir()` returns the cache directory of the fetched PROIEL XML.

### Where the gap comes from: `proiel_drift`

Scoring an AGDT-trained model on the differently-annotated PROIEL conflates real
mistakes with convention differences. `proiel_drift` separates the two: it re-tags
the same gold with the same (reconciled) tagger `evaluate_on_proiel` uses and
returns a `DriftReport`.

```python
report = greek.proiel_drift()
print(report.summary())     # the top gold → predicted POS confusions, with their share
report.top_share            # fraction of POS errors in the single most common pair
report.pos_accuracy, report.lemma_accuracy
```

A `DriftReport` carries the gold-to-predicted POS confusion matrix
(`pos_confusions`, most-frequent first), a sample of lemma mismatches
(`lemma_mismatches`), and the scored counts. A high `top_share` (most POS errors
concentrated in a few pairs) points to a systematic convention difference; a long
flat tail points to scattered real error. `proiel_drift` only *explains* the gap;
`evaluate_on_proiel`'s reported number is unchanged.

## Out-of-domain Koine: `evaluate_on_nt`

`evaluate_on_nt` scores against the **Nestle 1904** corpus's own gold lemmas and
morphology (the same gold `greek.load_nt` carries), a complement to the PROIEL
check: PROIEL scores against a *different project's* annotation of the NT, while
this scores against Nestle's own. Neither source is in pyaegean's training data
(the models train on AGDT + Gorman + Pedalion), so both are genuine out-of-domain
Koine checks.

```python
greek.use_neural_pipeline()          # the NT fold reports the shipped model's number
greek.evaluate_on_nt()               # {'lemma': …, 'upos': …, 'n': …}
greek.evaluate_on_nt(book="John")    # or one book
```

The default predictor is the neural joint pipeline, so the figure reflects the
shipped model; pass your own `tag_sentence` to score something else. As with PROIEL,
**lemma is the clean metric** and **UPOS is compared under the reconciled tagset**
(PROPN to NOUN, SCONJ to CCONJ, AUX to VERB). Finer morphological features are
deliberately **not** scored here: the Robinson tagset and pyaegean's UD FEATS do not
align feature-for-feature, so a UFeats number would be a convention artefact, not an
accuracy. The measured numbers and the convention notes are in
[Benchmarks](Benchmarks).

## The leakage manifest and exclusion discipline: `agdt_ud_overlap`

UD Ancient Greek (Perseus) is **converted from the AGDT** that pyaegean's backends
train on, so its sentence ids point straight back at AGDT source files (a UD sentence
id looks like `tlg0008….tb.xml@197`). Scoring an AGDT-trained model on those same
sentences would be measuring memorization, not generalization. `agdt_ud_overlap`
builds the manifest that makes the exclusion enforceable.

```python
manifest = greek.agdt_ud_overlap()          # splits=("dev", "test") by default
manifest["n_sentences"]                       # how many AGDT sentences appear in the UD folds
manifest["files"]["<agdt-file>"]              # the sentence ids to exclude, per file
manifest["verified"]                          # {'checked': …, 'form_identical': …}
```

It collects every AGDT sentence appearing in the given UD splits (default: dev +
test, the folds that must stay unseen), and **verifies** each reference by comparing
NFC form sequences against the actual AGDT files, so the manifest is not a name match
but a checked identity. The result is cached as JSON and records the UD commit, the
splits, the pyaegean version, the per-file sentence ids, and the verification counts.

The exclusion discipline this enforces:

- **The shipped neural model's training split removes every UD-Perseus dev + test
  sentence** named in this manifest, so its Perseus-fold scores are **leakage-clean**.
- **PROIEL is clean for every pyaegean model**, because none of them train on PROIEL.
- **The legacy full-AGDT backends** (the pure-Python treebank lookup, tagger,
  lemmatizer, and parser) *have* seen those sentences, so their Perseus-fold scores
  are an **in-training upper bound**, not a generalization claim. The held-out
  evaluations (a disjoint 90/10 AGDT split) and the out-of-AGDT PROIEL / NT checks are
  where those backends are honestly measured.

Every future trained model must honour this manifest. The protocol is spelled out in
[Benchmarks](Benchmarks);
the model-side leakage story is on
[Data & Provenance](Data-and-Provenance#the-greek-neural-joint-pipeline-model-grc-joint-use_neural_pipeline-neural).

## Evaluation receipts: `eval_receipt`

A score is only reproducible if you know exactly what produced it. `eval_receipt`
wraps a scores dict in a **content-addressed, tamper-evident** record that ties the
result to its inputs: the package version, the full data manifest
(`aegean.data.versions()`), the active neural model id, the treebank, the split, and
the protocol. The `id` is a short sha256 over the canonical (sorted-key) JSON of every
field, so identical inputs always give the identical id, and changing any field, a
different score, a bumped version, a swapped model, a different data sha256, changes it.

```python
scores = greek.evaluate_on_ud("perseus", "test")   # or any metric → value mapping
r = greek.eval_receipt(scores, treebank="perseus", split="test", protocol="conll18")

r.id                       # e.g. 'a15940ec010157d0' — the content hash of the whole record
r.verify()                 # True — re-hashes the stored fields and confirms they still produce r.id
r.package_version, r.model_id   # resolved automatically from the environment
```

An `EvalReceipt` is frozen and serializes both ways: `r.as_dict()` / `r.as_json()`
write the full record (id included) and `EvalReceipt.from_dict(data)` reads it back.
`r.verify(other)` confirms two receipts describe the byte-identical evaluation (the
same content-addressed id), so a number quoted in a paper can be checked against the
receipt that produced it. Pass `package_version=` / `manifest=` / `model_id=` to
override the resolved environment for a fully deterministic, offline receipt (the call
then touches neither the network nor the filesystem), and `extra=` carries any further
reproducibility metadata (a seed, the evaluator sha, a fold manifest).

A receipt records *what was run*; it does not certify that the protocol is sound or the
scores correct. It pins inputs, not conclusions. To pin the *data* a receipt refers to,
dump the manifest alongside it (`aegean data versions --json`); see
[Data & Provenance](Data-and-Provenance#data-versioning--pinning-for-papers).

## The evaluation-set licences

The gold data these evaluators score against is fetched to the cache **for evaluation
only**: never bundled in the wheel, and never trained on. The two UD Ancient Greek folds
carry *different* Creative Commons versions (each treebank's own README at the pinned
commit states its own), so pyaegean records the licence per treebank rather than
blanket-stating one:

| Evaluation set | Licence | Use |
| --- | --- | --- |
| UD Ancient Greek — Perseus | CC BY-NC-SA 2.5 | fetched for `evaluate_on_ud`; never bundled, never trained on |
| UD Ancient Greek — PROIEL | CC BY-NC-SA 3.0 | fetched for `evaluate_on_ud`; never bundled, never trained on |
| PROIEL treebank (NT + Herodotus) | CC BY-NC-SA 3.0 | fetched for `evaluate_on_proiel`; never bundled, never trained on |
| CoNLL 2018 evaluator (`conll18_ud_eval.py`) | MPL-2.0 | fetched, sha256-pinned, imported from cache |
| Nestle 1904 NT gold (`nt-corpus`) | CC0 (morphology/lemmas); base text public domain | gold for `evaluate_on_nt` |

All three treebanks are **NonCommercial + ShareAlike**, and those obligations **pass
through to you**: you may not use them commercially, and you must ShareAlike. Because
the Nestle 1904 gold is CC0, it carries no such obligation, which is why one NT book can
be bundled and the full NT corpus redistributed. The full per-dataset accounting,
including provenance and pinned commits, is on
[Data & Provenance](Data-and-Provenance#the-proiel-evaluation-set-evaluate_on_proiel),
and the attribution statements are in the repository `NOTICE`.

## Reproduce the numbers from the shell

Every evaluator has a CLI mirror (`pip install "pyaegean[cli]"`). `aegean greek eval
TARGET` reproduces any of the measured figures with the official evaluators and the
fetched gold data:

| `eval` target | What it measures |
| --- | --- |
| `ud` | active pipeline on a UD fold (CoNLL 2018 evaluator); `--fold perseus\|proiel`, `--split dev\|test`, `--bootstrap` for CIs |
| `proiel` | the neutral out-of-AGDT check (lemma + POS); `--drift` for the convention-vs-error breakdown |
| `nt` | the neural pipeline against the Nestle 1904 gold |
| `tagger` | the held-out AGDT POS evaluation |
| `lemmatizer` | the held-out AGDT lemma evaluation |
| `parser` | the held-out AGDT dependency evaluation |

```bash
aegean greek eval ud --fold perseus --split test --neural   # the standard benchmark, shipped model
aegean greek eval ud --fold perseus --bootstrap --neural    # with percentile confidence intervals
aegean greek eval proiel --neural-lemmatizer                # neutral out-of-AGDT check
aegean greek eval proiel --drift                            # where the out-of-AGDT gap comes from
aegean greek eval nt                                        # the neural model on the Greek NT
```

The backend flags (`--neural`, `--tagger`, `--lemmatizer`, `--neural-lemmatizer`)
choose which pipeline is scored; for `ud`, `uas`/`las` are reported whenever a parser
is active (the neural pipeline includes one);
`--json` and `-o` write machine-readable output. These commands are **heavy**: they
fetch gold data (and `tagger`/`lemmatizer`/`parser` may train a model), so run them
only when you actually want to reproduce a number.

## See also

- [Greek NLP](Greek-NLP) — the pipeline and backends these evaluators score, and the
  held-out AGDT generalization numbers.
- [Data & Provenance](Data-and-Provenance) — the licence, provenance, and pinned
  version of every fetched evaluation set and model.
- [Analysis](Analysis) — the statistics layer behind `bootstrap_ud` and the
  significance tests.
- [Benchmarks](Benchmarks)
  — the full methodology, the leakage controls, the comparison tables, and every
  measured number with its citation.
- [Limitations](Limitations) — the honest scope of each backend the numbers describe.
