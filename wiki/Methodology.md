# Methodology

This page consolidates pyaegean's evidentiary framework, Greek NLP evaluation
protocol, leakage controls, model training and quantization procedure, and data
provenance rules. Each section points to its primary record:

- Evaluation protocol, leakage controls, and metric definitions:
  [Benchmarks](Benchmarks) and [Greek NLP](Greek-NLP)
- Training scripts and int8 quantization records:
  [`training/README.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/README.md)
  and [`training/results/`](https://github.com/ryanpavlicek/pyaegean/tree/main/training/results)
- Data sources, licenses, and cache versioning:
  [Data & Provenance](Data-and-Provenance)
- Evidence tiers and auditing workflows:
  [For Specialists](For-Specialists) and [Limitations](Limitations)

Every measured figure on this page can be reproduced with the commands listed
below.

---

## Contents

| Section | Scope | Primary source |
| --- | --- | --- |
| [1. Evidence-tier framework](#1-the-evidence-tier-framework) | Distinction between facts, measurements, and hypotheses | [For Specialists](For-Specialists) |
| [2. Evaluation methodology](#2-evaluation-methodology) | Greek NLP evaluation protocol and metrics | [Benchmarks](Benchmarks) |
| [3. Leakage control](#3-leakage-control) | Separation of training and test treebanks | [Benchmarks](Benchmarks) |
| [4. Training and quantization](#4-training-and-quantization) | Joint GreBerta training stages and weight-only quantization | [`training/README.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/README.md) |
| [5. Data provenance, licensing, and reproducibility](#5-data-provenance-licensing-and-reproducibility) | Licensing boundaries, version manifests, and review receipts | [Data & Provenance](Data-and-Provenance) |

---

## 1. The evidence-tier framework

Every output in pyaegean falls into one of three registers. The register marks
the kind of claim being made and determines how errors are handled.

| Register | Scope | Marking | Error handling |
| --- | --- | --- | --- |
| **Established** | Facts taken from editions, lexica, and Unicode: Linear B and Cypriot sign values, Greek lexicon and morphology (Perseus AGDT, LSJ), bundled transliterations, and the find-site gazetteer. | Source citations (`info` / `cite`, [Data & Provenance](Data-and-Provenance), `NOTICE`). | **Correction** against the source |
| **Measured** | Model accuracies evaluated on held-out folds without training leakage (Greek lemmatizer, tagger, parser, and neural pipeline). | Reproducible protocol ([Benchmarks](Benchmarks), [Greek NLP](Greek-NLP)). | **Reproduce or challenge** the figure |
| **Exploratory** | Analytical output over undeciphered scripts (cross-linguistic distances, morphological clusters, structure heuristics, metrological estimates) and all AI-layer output. | `[EXPLORATORY …]` tag, `exploratory=True` flag, red Jupyter badge, and auditable `trace()`. | **Validation** (confirm or refute) |

### Editorial certainty on tokens

Each token carries a `ReadingStatus` following Leiden and EpiDoc conventions.
The status round-trips through JSON, SQLite, and token-carrier EpiDoc:

| `ReadingStatus` | Meaning | EpiDoc / Leiden |
| --- | --- | --- |
| `certain` | Securely read (default) | — |
| `unclear` | Damaged but legible | `<unclear>` / underdot |
| `restored` | Editorially supplied | `<supplied>` / `[ ]` |
| `lost` | Not preserved / lacuna | `<gap>` or `<supplied reason="undefined">` / `[---]` |

Bundled corpora are normalized transcriptions, mostly `certain` with preserved
damage markers. In the bundled Linear A corpus, 552 tokens load as `LOST` and
120 as `UNCLEAR`, affecting 366 of the 1,721 documents; downstream code can
filter or weight damaged tokens directly.

### Undeciphered scripts

pyaegean covers two undeciphered scripts and never emits translations for them:

- **Linear A** (`lineara`): 50 of the 342 signs in the bundled inventory carry
  working sound values drawn from the 81 signs shared with Linear B, each with a
  `confidence` attribute. The remaining signs have no agreed reading. Phonetic
  transcription uses Linear B values strictly as a working convention, and Linear
  A has no Greek-reading bridge.
- **Cypro-Minoan** (`cyprominoan`): none of its 99 catalogued signs has an
  accepted sound value. pyaegean provides only the sign inventory and
  sign-sequence tokenization, with no transliteration or lexicon.

Linear B and the Cypriot syllabary write Greek, so both carry established
Greek-reading bridges.

### Auditing exploratory output

Every generative AI call returns an `ExploratoryResult` carrying an
`[EXPLORATORY …]` prefix and a `trace()` method listing the local grounding
items by source and reference. A trace reading
`grounding: none (ungrounded generation …)` indicates that the model relied only
on its pretraining weights. Grounding fidelity is tested via `ai.run_eval` /
`aegean ai eval`, which measures **groundedness** and **fabrication rate** on
fixed cases. See [For Specialists](For-Specialists) for details.

---

## 2. Evaluation methodology

Greek NLP accuracy figures are measured on standard Ancient Greek benchmarks
under a fixed, reproducible protocol. Full tables, cross-tool comparisons, and
literature citations appear on [Benchmarks](Benchmarks) (mirrored from
`docs/benchmarks.md`).

### Protocol

- **Test sets.** Universal Dependencies Ancient Greek test folds:
  `UD_Ancient_Greek-Perseus` (commit `331ddef`, CC BY-NC-SA 2.5) and
  `UD_Ancient_Greek-PROIEL` (commit `a4ab8d4`, CC BY-NC-SA 3.0). Both are
  fetched to cache strictly for evaluation, never bundled and never trained on.
- **Scorer.** The official CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`,
  MPL-2.0), fetched with a pinned SHA-256 digest. Reported figures are F1 per
  metric.
- **Gold tokenization.** Models run over each fold's gold `FORM` column so
  scores reflect tagging, lemmatization, and parsing rather than tokenizer
  differences. End-to-end evaluation from raw text through pyaegean's own
  tokenizer scores 99.97 tokens F1 on UD Perseus and tracks gold-tokenization
  metrics closely.
- **No tagset reconciliation on UD folds.** UPOS and lemmas are scored verbatim;
  treebank convention differences count against pyaegean here (unlike
  `greek.evaluate_on_proiel`, which reconciles tagsets to isolate model errors).
- **Lemma scoring.** UD folds use exact string matching with no extra
  normalization because UD gold is already NFC and free of homograph-index
  digits. Differences in principal parts, movable nu, or proper-noun citation
  forms count as errors. Native-corpus evaluations (`evaluate_on_nt` and
  `evaluate_on_proiel`) apply NFC normalization and strip homograph-index digits
  because those golds are not pre-normalized.
- **Train / dev / test split.** Models train on the leakage-checked corpus
  (§3). Development folds govern early stopping, checkpoint selection, schedule
  tuning, and quantization gating. Test folds are evaluated once on the frozen
  release candidate and never used for selection.

### Successor checkpoint selection

While the historical v3 script selected checkpoints by a local average of LAS
and lemma accuracy, successor selection enforces a frozen, machine-readable
policy over the leakage-checked Perseus and PapyGreek development sources. The
policy binds the exact release decoder, guards all seven reported tasks globally
and per source alongside OOV lemma accuracy, and weights literary and
documentary sources equally. No guarded development metric may drop more than
0.01 percentage point below its baseline.

The selector verifies the source manifest and every candidate report, recomputes
scores from integer counts, rejects missing or mismatched evidence, and ranks
passing candidates by Pareto fronts with deterministic tie-breakers. It operates
exclusively on development evidence and never executes a model or reads a locked
test fold. Locked test folds are scored once after a candidate is frozen.

Export and optimization sit inside this gate. Conversion commands stage an
artifact, rebuild reference and candidate development reports from prediction
records, and compare every guarded metric plus decoded UPOS, XPOS, UFeats,
lemma, head, and relation. A framework export must be prediction-identical to
its reference; an optimized artifact must reduce total artifact bytes while
staying within its declared tolerances. Qualification runs the full development
set through ONNX Runtime on CPU in sequential/windowed mode, recording latency,
resident memory, artifact size, runtime versions, and the active execution
provider (probing CUDA if installed). These private development records govern
promotion; they are not published benchmarks and never touch locked test folds.
A smaller ONNX graph is not guaranteed to run faster.

### Metric definitions

All metrics are percentages against human-annotated gold data (higher is better):

| Metric | Definition |
| --- | --- |
| **UPOS** | Universal Dependencies 17-tag coarse part of speech. |
| **XPOS** | Treebank-specific fine-grained tag; incomparable across treebanks with distinct tagsets (`n/a` where schemes differ). |
| **UFeats** | Full morphological feature bundle (case, number, gender, tense, mood, voice, person). Exact-match only: every feature must agree. |
| **Lemma** | Dictionary citation form (`λέγει` → `λέγω`). |
| **UAS** | Unlabeled Attachment Score: share of tokens attached to the correct syntactic head. |
| **LAS** | Labeled Attachment Score: correct syntactic head and correct dependency relation label. |

The evaluator reports **F1** per metric. **Bootstrap confidence intervals**
(e.g. `[89.6, 90.9]`) estimate sampling variability by resampling sentences with
replacement (`greek.bootstrap_ud`, default 999 resamples).

### Measured neural pipeline scores

The shipped joint model (`grc-joint-v3`, activated via
`greek.use_neural_pipeline()` with the `[neural]` extra) uses a single GreBerta
encoder to predict UPOS, XPOS, UD FEATS, dependency trees (single-root
Chu-Liu/Edmonds MST decoding, supporting non-projective trees), and lemmas.
Measured through pyaegean's own CPU sequential inference path:

| Test fold | Lemma | UAS | LAS | UPOS | UFeats | XPOS |
| --- | --- | --- | --- | --- | --- | --- |
| UD Perseus (in family) | 94.27 | 90.24 | 85.65 | 97.02 | 96.03 | 93.47 |
| UD PROIEL (out of domain) | 90.51 | 82.47 | 63.50 | 86.68 | 59.43 | n/a |

Historical decoder-v1 training has five seed replicates; across those five
seeds, UD Perseus test mean ± standard deviation was LAS 85.58 ± 0.10, UAS
90.15 ± 0.12, UPOS 97.00 ± 0.06, UFeats 96.06 ± 0.04, lemma 94.30 ± 0.02, and
XPOS 93.52 ± 0.05 (PROIEL LAS 63.50 ± 0.04). Those numbers document historical
decoder-v1 training variance and are not decoder-v2 replicates. Within-fold 95%
percentile bootstrap confidence intervals (999 resamples) accompany every
headline figure on [Benchmarks](Benchmarks).

Out-of-domain PROIEL scores are always reported alongside in-family Perseus
scores because no pyaegean model trains on PROIEL. Much of the PROIEL UFeats and
LAS drop stems from annotation-scheme divergence between the two UD conversions:
PROIEL encodes feature types absent from Perseus and uses an incompatible XPOS
tagset.

A second out-of-domain test evaluates the pipeline against the **Nestle 1904**
Greek New Testament (`greek.evaluate_on_nt()`): lemma 87.96 and reconciled UPOS
86.75 across 137,303 tokens. No NT text enters training.

### Zero-dependency baseline

The pure-Python stack (`use_treebank() + use_tagger() + use_lemmatizer() +
use_parser()`) runs offline without third-party dependencies (Perseus test UPOS
86.73, PROIEL test UPOS 78.84). Because its lookup tables and parser derive from
the full AGDT (which includes the UD-Perseus test sentences), its Perseus score is
an in-training upper bound reported for reference, while the held-out PROIEL
score reflects generalization. Accuracy claims rest on the neural pipeline.

### Reproducing the measurements

```python
from aegean import greek

greek.use_neural_pipeline()
greek.evaluate_on_ud("perseus", "test")   # in-family
greek.evaluate_on_ud("proiel", "test")    # out of domain
greek.evaluate_on_nt()                    # Koine / NT, out of domain
```

```bash
aegean greek eval nt
```

Every published score is stored in `training/results/published-claims.json`.
`tests/test_benchmark_claims.py` checks documentation echoes against that
registry on every commit, and `scripts/check_benchmarks.py` re-measures the
offline-stack rows. Full tables, external system comparisons, and citations live
on [Benchmarks](Benchmarks); evaluation functions are documented on
[Greek NLP](Greek-NLP#standard-benchmark-evaluation-universal-dependencies).

---

## 3. Leakage control

UD Perseus converts sentences directly from the Perseus AGDT, so naive training
on AGDT leaks the evaluation set. Two controls prevent test leakage in the
neural pipeline:

- **UD-Perseus exclusion manifest.** `greek.agdt_ud_overlap()` maps every
  UD-Perseus dev and test sentence back to its AGDT source and confirms identity
  by NFC form-sequence matching: **2,443 form-identical sentences across 5 AGDT
  files**. Neural training excludes every sentence in that manifest (cached at
  `ud-grc/agdt-ud-exclusion.json`).
- **Held-out PROIEL and cross-treebank deduplication.** No pyaegean model trains
  on PROIEL. Combined-corpus training adds the Gorman and Pedalion treebanks
  (both CC BY-SA 4.0); overlap checks exclude 1,591 Gorman sentences and 155
  Pedalion sentences matching either evaluation fold, and Gorman's Herodotus
  files (which share text with PROIEL's `hdt.xml`) are dropped at source.

The pure-Python baseline is the sole exception: it builds directly from the full
AGDT, making its Perseus score an in-training upper bound and its PROIEL score
the out-of-domain figure.

Licensing enforces the same split: models train exclusively on CC BY-SA
treebanks (AGDT, Gorman, Pedalion), while CC BY-NC-SA evaluation treebanks (UD
Perseus, UD PROIEL, PROIEL) are fetched solely for evaluation and never enter
training (§5).

---

## 4. Training and quantization

Training code lives in
[`training/`](https://github.com/ryanpavlicek/pyaegean/tree/main/training) and
does not ship in the Python wheel. Trained weights are published as GitHub
release assets and fetched to the local cache on demand. Evidence files for all
recorded runs live in
[`training/results/`](https://github.com/ryanpavlicek/pyaegean/tree/main/training/results).

### Data splits

- **Train:** AGDT + Gorman + Pedalion (~1.41M tokens), minus all sentences in
  the UD-Perseus dev+test exclusion manifest (`greek.agdt_ud_overlap()`).
- **Dev:** AGDT sentences corresponding to the UD-Perseus dev fold, used for
  early stopping, checkpoint selection, schedule tuning, and quantization
  gating.
- **Test:** Disjoint from train and dev; scored once via
  `greek.evaluate_on_ud("perseus", "test")` against the finished model.

`training/data/` and `training/out/` are gitignored; datasets rebuild
deterministically from cached upstream sources.

### Model stages

A single **GreBerta** encoder backs all tasks in one forward pass, built across
five stages:

- **Stage A (encoder selection):** Fine-tune UPOS across candidate encoders
  under an equal budget; select on dev accuracy, unseen-form generalization,
  size, and license. GreBerta (Apache-2.0 RoBERTa for Ancient Greek) is the
  shipped base encoder.
- **Stage B (joint tagger):** Predict UPOS, XPOS, and UD FEATS on UD-convention
  labels converted from AGDT.
- **Stage C (biaffine parser):** Add Dozat–Manning arc and relation scorers on
  the shared encoder with single-root Chu-Liu/Edmonds MST decoding.
- **Stage D (lemmatizer):** Add a word-level Chrupała edit-script classifier
  plus a train-only form lookup on the same checkpoint.
- **Stage E (export and quantization):** Export torch-free fp32 ONNX (hosted as
  `grc-joint-v2` for reproducibility), then apply weight-only quantization to
  build the shipped `grc-joint-v3` asset.

Candidate joint checkpoints adhere to the dependency-free
`pyaegean-neural-preprocessing-v1` contract across training, evaluation, and
runtime inference. Checkpoints record their annotation profile, NFC
normalization, pretokenized RoBERTa policy, alignment rules, and subword limit;
export validates each field against the serialized tokenizer, requires a unique
model identity, rejects stale or foreign output files, and writes a schema-1
content manifest. The published `grc-joint-v3` asset retains its original
manifest, behavior, and measured numbers unchanged.

Successor training receipts bind the exact selection-policy file and digest so a
checkpoint stays tied to its selection criteria. Operational records bind the
report's model identity and full bundle digest. Optimization accepts only the
exact fp32 source named in its reference evidence and writes reproducible
archives for passing candidates.

The runtime registry defines four variant labels (`default`, `fast`, `compact`,
and optional `balanced`) independently of any successor model:

- `default`: the release-selected artifact (currently `grc-joint-v3`); makes no
  speed or size claim.
- `compact`: artifact size ≤ 90% of the reference.
- `fast`: five same-environment full CPU runs with median latency ≤ 90% of the
  reference and at least four candidate runs faster than the reference median.
- `balanced`: meets the `compact` size bound plus five runs with median latency
  and median peak resident memory each ≤ 105% of the reference.

An ONNX numeric format never earns a variant label without meeting these gates.
Until a qualified successor earns them, `fast`, `compact`, and `balanced` remain
reserved and unavailable. Public award receipts record operational summaries and
hashes rather than development scores, predictions, rejected candidates, or raw
timing series.

### Quantization

The shipped `grc-joint-v3` archive is **173 MB** (`tar.gz`; 182 MB uncompressed
`model.onnx`), roughly 3× smaller than the fp32 `grc-joint-v2` reference
(518 MB `tar.gz`; 556 MB uncompressed). In the recorded decoder-v1 comparison,
UD Perseus test scores matched fp32 within ±0.02 points (UPOS 97.0, UFeats 96.0,
lemma 94.3, UAS 90.2, LAS 85.7). The recipe applies **weight-only int8 + fp16
with fp32 activations**: ONNX Runtime `MatMulNBits` (block size 128, symmetric)
on MatMul weights, fp16 on remaining weights (including the ~160 MB word
embedding table), and fp32 activations throughout.

Full int8 quantization (quantized activations) collapses the GreBerta encoder
because of activation outliers: recorded dynamic and static int8 runs dropped
UPOS from 97 to 16–32 and LAS from 86 to 1–13, exceeding the ≤ 0.3-point
acceptance gate. Those excluded runs are recorded in
`training/results/gate-report.json`, and shipped sizes and accuracy comparisons
in `training/results/v3-quantize-report.json`.

Weight-only quantization trades CPU throughput for download size: `MatMulNBits`
CPU kernels run at roughly 20–70 words/s versus ~300 words/s for fp32 on the
development machine. Throughput varies by hardware and sentence length and is
illustrative rather than a pinned benchmark. Throughput-sensitive workloads can
fetch the fp32 `grc-joint-v2` release asset instead. The quantized asset
requires `onnxruntime >= 1.23` for its 8-bit `MatMulNBits` CPU kernel. Both
models run torch-free on `numpy` + `onnxruntime` and load only when activated.

### Annotation and domain profile records

The annotation registry records output provenance without altering model
evaluation. Immutable, SHA-256-identified `AnnotationProfile` records declare
output labels, relation schemes, segmentation, normalization, mapping direction,
and reversibility/loss. `DomainProfile` records describe source scope and
editorial layer; they are caller-supplied metadata, not text-profile detectors.

Inference emits the canonical Perseus/AGDT-derived UD convention. Differences
between Perseus/AGDT and UD-PROIEL (POS collapse, token splits, missing
features, dependency restructuring) are documented as diagnostic comparisons and
can be non-invertible. Native-PROIEL XML evaluation strips `#N` homograph
suffixes and omits empty tokens; exact UD-fold evaluation does not. The
PapyGreek `orig` fold swaps in diplomatic `FORM` spellings while retaining
regularized-layer gold analyses. Receipt schema 4 binds the runtime variant,
composed output profile, and ordered post-processing steps; schemas 1–3 remain
readable for hosted evidence, and `grc-joint-v3`'s identity stays unchanged.

---

## 5. Data provenance, licensing, and reproducibility

Full per-dataset provenance and licensing live on
[Data & Provenance](Data-and-Provenance).

### Bundled vs. fetched assets

Code and small text JSON tables are bundled in the wheel and work offline with
zero third-party dependencies. Large or license-restricted assets are fetched on
demand into a persistent local cache and verified by SHA-256. CI's
`scripts/check_footprint.py` enforces wheel size limits and zero-dependency
import speed. Cached downloads persist until deleted explicitly.

### Licensing separation

- **Training treebanks (CC BY-SA):** AGDT (CC BY-SA 3.0), Gorman (CC BY-SA 4.0),
  and Pedalion (CC BY-SA 4.0). Derived model weights are published under
  ShareAlike terms as fetched release assets, never bundled.
- **Evaluation treebanks (CC BY-NC-SA):** UD-Perseus (CC BY-NC-SA 2.5),
  UD-PROIEL (CC BY-NC-SA 3.0), and PROIEL (CC BY-NC-SA 3.0), plus the CoNLL
  2018 scorer (MPL-2.0). Fetched strictly for `evaluate_on_ud()` /
  `evaluate_on_proiel()`, with NonCommercial and ShareAlike terms passing
  through to the user.

The base encoder `bowphs/GreBerta` is Apache-2.0; the derived `grc-joint`
release archive is CC BY-SA 4.0; the pyaegean wheel remains Apache-2.0. Bundled
Aegean sign data derives from the Unicode Character Database (Unicode-3.0), and
the Linear A corpus JSON derives from GORILA via `mwenge/lineara.xyz`
(Apache-2.0) without redistributing facsimile plates. NonCommercial corpora
(DAMOS, SigLA, IIP, IGCyr, Crete, Homer Multitext) and CC0 Nestle 1904 NT are
catalogued on [Data & Provenance](Data-and-Provenance).

### Pinning an analysis

`data.versions()` outputs a JSON manifest recording `package`, `bundled` (live
SHA-256 hashes of bundled JSON files), and `fetched` (pinned URL, SHA-256,
license, and cache status for every remote asset):

```python
import json
import aegean
from aegean import data

with open("data-versions.json", "w", encoding="utf-8") as f:
    json.dump({"package": aegean.__version__, "data": data.versions()}, f, indent=2)
```

```bash
aegean data versions --json > data-versions.json
```

Store `aegean.__version__` and this manifest alongside published results, or
package the corpus (or license-clean retrieval pointer), review CSVs, analysis
receipts, and generated citations into a single SHA-256-verified archive with
`aegean bundle create`. Loaded literary works record their upstream commit in
`Provenance.data_version`, and filtered corpora carry subset metadata in
citations. Cite the underlying scholarly edition alongside pyaegean; see
[For Specialists](For-Specialists) and
[Citing Computational Assistance](Citing-Computational-Assistance).

### Training-environment evidence

`training/environment-lock.json` is a non-authorizing template. Reviewed records
under `training/results/a17-environment/` capture a 48-package resolver closure,
CPython 3.12.13, a clean source commit, and an NVIDIA RTX PRO 6000 Blackwell
Server Edition allocation (CUDA 12.8, cuDNN 9.10.2, compute capability 12.0,
96 GB-class VRAM, bf16). GreBerta was resolved at an immutable commit via
metadata only, and a deterministic fixture receipt binds configuration, input,
output, hardware, environment, and artifact hashes without running a model.
These records document environment capture only; they make no training or model
quality claim.

### Bounded public review receipt

From a clean checkout, `python scripts/reproduce_review.py` verifies every file
in the canonical public review manifest by SHA-256 and reproduces one small,
project-authored offline result without network access, model execution,
bytecode writes, or cache creation. It is an integrity and regression check
rather than a neural benchmark rerun or external peer review. See
[Independent Review](Independent-Review) for model and data cards, scope, and
the discrepancy reporting form.

---

## See also

- [Greek NLP](Greek-NLP): pipeline usage, backend tiers, and evaluation calls
- [Benchmarks](Benchmarks): full evaluation tables, external comparisons, and citations
- [Data & Provenance](Data-and-Provenance): dataset registry, licenses, and cache layout
- [For Specialists](For-Specialists): evidence tiers, auditing, and contributing corrections
- [Independent Review](Independent-Review): bounded review command and evidence map
- [Limitations](Limitations): boundaries of evidence, licensing, accuracy, and scope
