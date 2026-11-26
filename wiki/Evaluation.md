# Evaluation

This page documents pyaegean's evaluation infrastructure: how the Greek pipeline
is scored, which gold datasets are used, what scoring protocol applies, and how
leakage and reproducibility are enforced. Every published accuracy figure in
pyaegean comes from these functions. Gold datasets are fetched from pinned
commits or SHA-256-verified release assets, training sentences overlapping the
UD evaluation splits are excluded by manifest, and convention mismatches are
measured separately from prediction errors.

Three rules govern the evaluation stack:

- **Official scorer.** Universal Dependencies folds are scored with the official
  CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`), fetched once and
  verified against a pinned SHA-256 digest.
- **Explicit leakage exclusion.** Because UD Ancient Greek (Perseus) is converted
  from the AGDT treebank that pyaegean trains on, an audited manifest lists every
  overlapping sentence so the shipped neural model excludes them from training.
- **Evaluation-only boundaries.** The UD and PROIEL treebanks are fetched to the
  local cache strictly for scoring, never bundled in the wheel and never trained
  on, respecting their NonCommercial and ShareAlike terms.

The Greek pipeline and backends are documented in [Greek NLP](Greek-NLP);
dataset provenance and licences are in [Data & Provenance](Data-and-Provenance);
full measured numbers, confidence intervals, and cross-tool comparisons are in
[Benchmarks](Benchmarks).

## Evaluators

Every evaluator scores whichever backends are active when called. Activate the
desired backend first (`use_treebank`, `use_tagger`, `use_lemmatizer`,
`use_neural_lemmatizer`, `use_neural_pipeline`, `use_parser`; see
[Greek NLP](Greek-NLP)). Each evaluator has a CLI mirror under
`aegean greek eval`.

| Evaluator | Python | Gold data | Purpose |
| --- | --- | --- | --- |
| Standard benchmark | `evaluate_on_ud` | UD Ancient Greek (Perseus / PROIEL), official CoNLL 2018 scorer | UPOS, XPOS, UFeats, Lemma, UAS, LAS, CLAS |
| Sampling variability | `bootstrap_ud` | UD folds | Percentile confidence intervals resampled by sentence |
| Out-of-AGDT treebank | `evaluate_on_proiel` | PROIEL treebank (NT + Herodotus) | Out-of-domain lemma and reconciled POS accuracy |
| Out-of-domain Koine (NT) | `evaluate_on_nt` | Nestle 1904 gold (full 27-book NT) | Out-of-domain lemma and reconciled UPOS accuracy |
| Documentary Koine | `evaluate_on_papygreek` | PapyGreek treebank (`reg` and `orig` layers) | Documentary papyrus parsing and tagging (CoNLL 2018 scorer) |
| Byzantine verse | `evaluate_on_dbbe` | DBBE book-epigram gold | Medieval verse tagging and lemmatization (no parse trees) |
| Classical tragedy | `evaluate_on_verse` | UNESP Trees (*Bacchae* 1–169) | Small-sample verse parsing and tagging with wide CIs |
| Error analysis | `proiel_error_analysis`, `ud_error_analysis`, `nt_error_analysis`, `heldout_error_analysis`, `proiel_drift`, `papygreek_convention_report` | Any gold fold | POS confusion matrices, per-POS accuracy, lemma confusions, and convention decompositions (see [When the Tool Is Wrong](When-the-Tool-Is-Wrong)) |
| Held-out (in-AGDT) | `evaluate_tagger`, `evaluate_lemmatizer`, `evaluate_parser` | 90/10 AGDT sentence split | Leakage-free generalization of each pure-Python backend |
| Leakage manifest | `agdt_ud_overlap` | AGDT ↔ UD-Perseus | Exact sentence IDs excluded from training |
| Reproducibility receipt | `eval_receipt` | Any scores dict | Content-addressed, tamper-evident evaluation record |

The held-out `evaluate_tagger`, `evaluate_lemmatizer`, and `evaluate_parser`
checks (90/10 AGDT split with separate unseen-form metrics) are covered alongside
their backends in [Greek NLP](Greek-NLP#held-out-generalization). The sections
below cover the gold-benchmark, out-of-domain, leakage, and receipt APIs.

## Standard-benchmark evaluation: `evaluate_on_ud`

`evaluate_on_ud(treebank="perseus", split="test", ...)` scores the active
pipeline on a Universal Dependencies Ancient Greek fold with the official CoNLL
2018 evaluator. `treebank` accepts `"perseus"` or `"proiel"`; `split` accepts
`"train"`, `"dev"`, or `"test"`. Each fold is fetched to the local cache from a
pinned upstream commit on first use.

```python
from aegean import greek

greek.use_neural_pipeline()                 # score the shipped model ([neural] extra)
scores = greek.evaluate_on_ud("perseus", "test")
# {'treebank': 'perseus', 'split': 'test', 'parsed': True,
#  'upos': …, 'xpos': …, 'ufeats': …, 'lemma': …,
#  'uas': …, 'las': …, 'clas': …, 'n_words': …, 'n_sentences': …}
```

The returned dict maps each metric name to an accuracy in `[0, 1]`, along with
word and sentence counts. `parse` defaults to whether a parser is active (either
the neural pipeline or `use_parser()`); with `parse=False`, `uas`, `las`, and
`clas` are `None`. `xpos` and `ufeats` are populated only under the neural
pipeline; the pure-Python cascade leaves those columns empty.

**Measured headline** (UD Ancient Greek Perseus test, neural pipeline, gold
tokenization):

| UD Perseus test | UPOS | UFeats | Lemma | UAS | LAS |
| --- | --- | --- | --- | --- | --- |
| neural pipeline | 97.0 | 96.0 | 94.3 | 90.2 | 85.7 |

The full protocol, cross-tool comparison tables, and out-of-domain PROIEL-test
figures (lemma 90.51, UAS 82.47, UPOS 86.68) are in [Benchmarks](Benchmarks).

### Protocol summary

- **Gold tokenization.** The pipeline runs over each fold's gold `FORM` column so
  the metrics isolate tagging, lemmatization, and parsing quality from tokenizer
  differences.
- **No tagset collapsing.** UPOS and lemmas are scored strictly as emitted. Any
  convention mismatch counts as an error here (unlike `evaluate_on_proiel`, which
  reconciles coarse tagsets to separate real errors from scheme differences).
- **Dependency labels.** The shipped neural pipeline predicts UD relations, so
  LAS is scored directly against UD gold. The pure-Python arc-eager parser emits
  AGDT/Prague labels, making only UAS comparable; it is reported as a baseline.

### Pinned CoNLL 2018 scorer and lossless CoNLL-U loader

`evaluate_on_ud` does not rely on a custom scorer. It fetches the official
`conll18_ud_eval.py` (MPL-2.0) once, verifies its SHA-256 digest
(`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`), caches it,
and imports it directly. Any modified file fails the hash check before execution.

Gold folds are likewise pinned to fixed upstream commits so re-runs read
identical input. `greek.ud.ud_path(treebank, split)` returns the cached path
(fetching on first use), and `greek.ud.load_conllu(path)` parses each sentence
into two linked views: `UDSentence.rows` preserves all ten columns, multiword
ranges, empty nodes, enhanced `DEPS`, and `MISC`; `UDSentence.tokens` exposes the
syntactic-word projection consumed by the evaluator and the v3 model.
`UDSentence.projection` tracks original word IDs and any omitted structural rows.
The scoring path predicts only syntactic words, so preserved gold multiword rows,
empty nodes, and enhanced arcs never enter system predictions.

## Confidence intervals: `bootstrap_ud`

`bootstrap_ud` measures sampling variability around a fold's point estimates. The
active pipeline runs once over the fold, and then `n_resamples` sentence-level
resamples (with replacement) are scored through the official evaluator to compute
percentile confidence intervals.

```python
greek.use_neural_pipeline()
cis = greek.bootstrap_ud("perseus", "test")      # {'upos': BootstrapCI, 'lemma': …, 'las': …, …}
cis["las"].estimate, cis["las"].low, cis["las"].high
```

Resampling operates at the **sentence** level because tokens within a sentence
are not independent. Defaults are `n_resamples=999`, `level=0.95`, and `seed=0`
for deterministic intervals. `metrics` selects which metrics to compute; when no
parser is active, `uas` and `las` are omitted. Each entry is a `BootstrapCI`
(see [Analysis](Analysis)). Intervals reflect sampling variability within the
evaluated fold, not general model uncertainty across other genres or periods.

## Out-of-AGDT evaluation: `evaluate_on_proiel`

Because pyaegean's trainable backends all learn from AGDT-derived data, a held-out
AGDT split measures in-source generalization only. `evaluate_on_proiel` scores the
active pipeline against the independently annotated **PROIEL treebank** (Greek New
Testament and Herodotus), which no pyaegean model trains on.

```python
from aegean import greek

greek.use_neural_pipeline()       # score the shipped joint model (or activate baseline backends)
greek.evaluate_on_proiel()        # {'lemma': …, 'pos': …, 'n': …} over the PROIEL gold
```

`tag_sentence` maps a sentence's forms to `(lemma, pos)` pairs and defaults to
the active pyaegean pipeline. Two scoring rules govern the output:

- **Lemma comparison.** Lemmas are compared after NFC normalization and stripping
  PROIEL's `#N` homograph suffixes (`εἰμί#1` → `εἰμί`), so formatting suffixes do
  not inflate error counts.
- **Reconciled POS.** PROIEL's UD-only distinctions collapse on both gold and
  predictions (`PROPN` → `NOUN`, `SCONJ` → `CCONJ`, `AUX` → `VERB`). Punctuation
  and numerals are excluded, matching the held-out AGDT evaluation.

PROIEL is a neutral out-of-domain benchmark for pyaegean, though it is part of the
training data for some external systems (such as Stanza's `grc_proiel`), so it is
not a level cross-tool comparison against PROIEL-trained models. Cite Haug &
Jøhndal (2008) when reporting PROIEL results.

`greek.load_proiel_gold()` returns the parsed gold sentences directly, and
`greek.proiel_dir()` returns the local cache directory for the fetched XML.

### Separating convention drift from errors: `proiel_drift`

Scoring an AGDT-trained model on PROIEL conflates model mistakes with annotation
convention differences. `proiel_drift()` re-tags the same gold using the same
reconciled tagger as `evaluate_on_proiel()` and returns a `DriftReport`:

```python
report = greek.proiel_drift()
print(report.summary())     # top gold → predicted POS confusions with their share
report.top_share            # share of POS errors in the single largest confusion pair
report.pos_accuracy, report.lemma_accuracy
```

`DriftReport` provides the gold-to-predicted POS confusion matrix
(`pos_confusions`, sorted most frequent first), sample lemma mismatches
(`lemma_mismatches`), and token counts. A high `top_share` indicates concentrated
convention divergence, whereas a flat tail reflects scattered model errors.
`proiel_drift()` is strictly diagnostic and does not alter `evaluate_on_proiel()`
scores.

## Out-of-domain Koine: `evaluate_on_nt`

`evaluate_on_nt()` scores predictions against the **Nestle 1904** corpus's gold
lemmas and reconciled UPOS (the same gold loaded by `bible.load_nt()`). Unlike
PROIEL's NT annotation, this evaluates against Nestle 1904 directly; neither
source appears in pyaegean's training corpus (AGDT + Gorman + Pedalion).

```python
from aegean import greek

greek.use_neural_pipeline()          # score the shipped neural model
greek.evaluate_on_nt()               # {'lemma': …, 'upos': …, 'n': …}
greek.evaluate_on_nt(book="John")    # single book
```

The default predictor is the active pipeline; pass a custom `tag_sentence`
callable to evaluate another system. As with PROIEL, lemmas are normalized and
UPOS is reconciled (`PROPN` → `NOUN`, `SCONJ` → `CCONJ`, `AUX` → `VERB`). Finer
morphological features are excluded because the Robinson tagset does not map
one-to-one onto UD FEATS, and Nestle 1904 carries no dependency trees. Measured
scores and convention notes appear in [Benchmarks](Benchmarks).

## Leakage manifest and exclusions: `agdt_ud_overlap`

UD Ancient Greek (Perseus) is converted from the AGDT treebank, and its sentence
IDs point back to AGDT source files (for example `tlg0008….tb.xml@197`). Scoring
an AGDT-trained model on those sentences would measure memorization rather than
generalization. `agdt_ud_overlap()` builds the verifiable exclusion manifest:

```python
manifest = greek.agdt_ud_overlap()          # splits=("dev", "test") by default
manifest["n_sentences"]                     # count of overlapping AGDT sentences
manifest["files"]["<agdt-file>"]            # sentence IDs to exclude per file
manifest["verified"]                        # {'checked': …, 'form_identical': …}
```

For the requested UD splits (default `dev` and `test`), the function maps every
UD sentence to its AGDT source and verifies identity by comparing NFC form
sequences against the actual AGDT files. The cached JSON manifest records the UD
commit, splits, pyaegean version, per-file sentence IDs, and verification counts.

What this manifest enforces:

- **Shipped neural model.** Every UD-Perseus `dev` and `test` sentence in the
  manifest is removed before training, keeping Perseus test scores leakage-clean.
- **PROIEL.** No pyaegean model trains on PROIEL.
- **Pure-Python baseline backends.** The legacy full-AGDT treebank lookup,
  tagger, lemmatizer, and parser include the Perseus test sentences; their
  Perseus scores are marked as in-training upper bounds. Their leakage-free
  evaluations are the 90/10 held-out AGDT splits and the out-of-AGDT PROIEL and
  NT checks.

Every trained model release must honor this manifest. Details are in
[Benchmarks](Benchmarks) and
[Data & Provenance](Data-and-Provenance#the-greek-neural-joint-pipeline-model-grc-joint-use_neural_pipeline-neural).

## Evaluation receipts: `eval_receipt`

`eval_receipt` wraps any scores dict in a content-addressed, tamper-evident
record binding the numbers to the package version, data manifest
(`aegean.data.versions()`), active neural model ID, treebank, split, and
protocol. Its `id` is a truncated SHA-256 digest of the canonical sorted-key JSON
representation of all fields, so changing any score, version, model ID, or data
digest changes `id`.

```python
scores = greek.evaluate_on_ud("perseus", "test")   # or any metric → value mapping
r = greek.eval_receipt(scores, treebank="perseus", split="test", protocol="conll18")

r.id                       # e.g. 'a15940ec010157d0' — content hash of the record
r.verify()                 # True — re-hashes stored fields and confirms match with r.id
r.package_version, r.model_id   # resolved automatically from the environment
```

`EvalReceipt` is frozen and supports round-trip serialization via `as_dict()`,
`as_json()`, and `EvalReceipt.from_dict(data)`. `r.verify(other)` checks whether
two receipts share the exact same content hash. Pass explicit `package_version=`,
`manifest=`, and `model_id=` arguments to build a deterministic receipt offline
without touching the network or cache; pass `extra=` for additional metadata
(random seeds, evaluator SHA-256, fold manifests).

A receipt pins inputs and outputs; it does not validate experimental design. To
pin the underlying data versions alongside a receipt, export
`aegean data versions --json` (see
[Data & Provenance](Data-and-Provenance#data-versioning--pinning-for-papers)).

## Evaluation-set licences

Gold evaluation folds are fetched on demand into the local cache for scoring
only. They are never bundled in the wheel and never trained on. Because the two
UD Ancient Greek repositories specify different Creative Commons versions in
their respective READMEs at the pinned commits, each dataset's licence is tracked
separately:

| Evaluation set | Licence | Use |
| --- | --- | --- |
| UD Ancient Greek — Perseus | CC BY-NC-SA 2.5 | `evaluate_on_ud`; evaluation only, never bundled or trained on |
| UD Ancient Greek — PROIEL | CC BY-NC-SA 3.0 | `evaluate_on_ud`; evaluation only, never bundled or trained on |
| PROIEL treebank (NT + Herodotus) | CC BY-NC-SA 3.0 | `evaluate_on_proiel`; evaluation only, never bundled or trained on |
| PapyGreek folds (`reg` / `orig`) | CC BY-SA 4.0 | `evaluate_on_papygreek`; evaluation only, never bundled or trained on |
| DBBE book-epigram fold | CC BY 4.0 | `evaluate_on_dbbe`; evaluation only, never bundled or trained on |
| UNESP Trees verse fold | CC BY-SA 4.0 | `evaluate_on_verse`; evaluation only, never bundled or trained on |
| CoNLL 2018 evaluator (`conll18_ud_eval.py`) | MPL-2.0 | Fetched, SHA-256-pinned, imported from cache |
| Nestle 1904 NT gold (`nt-corpus`) | CC0 (morphology/lemmas); base text public domain | `evaluate_on_nt` (full 27-book asset required) |

The UD and PROIEL treebanks carry NonCommercial and ShareAlike terms that apply
directly to downstream users. Nestle 1904 annotations are CC0, which permits
bundling the two-chapter offline sample (John 1 and Philemon 1) and hosting the
full corpus asset. Complete provenance, commits, and attribution notices appear
in [Data & Provenance](Data-and-Provenance#the-proiel-evaluation-set-evaluate_on_proiel)
and the repository `NOTICE` file.

## Reproducing numbers from the shell

Every evaluator has a CLI mirror (`pip install "pyaegean[cli]"`). Run
`aegean greek eval TARGET` to reproduce published figures against the fetched
gold datasets:

| `eval` target | What it measures |
| --- | --- |
| `ud` | Active pipeline on a UD fold (CoNLL 2018 scorer); `--fold perseus\|proiel`, `--split dev\|test`, `--bootstrap`, `--by-genre`, `--drift`, `--documentary`, `--batch-size N` |
| `proiel` | Out-of-AGDT lemma and reconciled POS check; `--drift` for error analysis |
| `papygreek` | Documentary-Koine fold; `--layer reg\|orig`, `--drift` for UPOS/XPOS convention decomposition, `--documentary`, `--batch-size N` |
| `dbbe` | Byzantine book-epigram fold (tagging and lemmatization only); `--batch-size N` |
| `verse` | Small-sample tragedy fold; `--track tragedy\|all`, `--documentary`, `--batch-size N` |
| `nt` | Neural or active pipeline against Nestle 1904 gold; `--drift`, `--documentary`, `--batch-size N` |
| `tagger` | Held-out 90/10 AGDT POS evaluation |
| `lemmatizer` | Held-out 90/10 AGDT lemma evaluation |
| `parser` | Held-out 90/10 AGDT dependency evaluation |

```bash
aegean greek eval ud --fold perseus --split test --neural   # standard benchmark, shipped model
aegean greek eval ud --fold perseus --bootstrap --neural    # with percentile confidence intervals
aegean greek eval proiel --neural-lemmatizer                # out-of-AGDT check
aegean greek eval proiel --drift                            # error breakdown on PROIEL
aegean greek eval papygreek --drift                         # documentary UPOS/XPOS convention decomposition
aegean greek eval papygreek --layer orig --neural           # diplomatic orthography layer
aegean greek eval dbbe --neural                             # Byzantine book epigrams (tagging only)
aegean greek eval verse --track tragedy --neural            # tragedy small-sample fold
aegean greek eval nt --neural                               # shipped neural model on full Greek NT
```

Backend flags (`--neural`, `--tagger`, `--lemmatizer`, `--neural-lemmatizer`)
select the active stack. On `ud`, UAS and LAS are computed whenever a parser is
active. Pass `--json` and `-o` to write structured results. These commands fetch
gold datasets (and `tagger`, `lemmatizer`, and `parser` may train models locally
if needed), so run them when reproducing benchmarks rather than for routine text
analysis.

## See also

- [Greek NLP](Greek-NLP): pipeline, backends, and held-out AGDT generalization numbers
- [Data & Provenance](Data-and-Provenance): licences, provenance, and pinned commits for evaluation datasets and models
- [Analysis](Analysis): statistical utilities behind `bootstrap_ud` and significance tests
- [Benchmarks](Benchmarks): full methodology, leakage controls, comparison tables, and cited numbers
- [Limitations](Limitations): scope and known gaps for each backend
