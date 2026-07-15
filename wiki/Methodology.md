# Methodology

This page gathers, in one findable place, **how pyaegean knows what it claims to
know**: how the Greek NLP models are evaluated, how they are trained and
quantized, where every dataset comes from and under what licence, how the
training data is kept clean of the evaluation folds, and how the toolkit marks
the line between settled scholarship and machine-generated hypothesis.

None of this is new material: it is the methodology already recorded across the
project, pulled together here for a reviewer who wants the whole picture at once.
Each section names the primary source and links onward:

- the evaluation protocol, leakage controls, and metric definitions:
  [Benchmarks](Benchmarks)
  and [Greek NLP](Greek-NLP)
- the model training and int8 quantization discipline:
  [`training/README.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/README.md)
  with the evidence files in
  [`training/results/`](https://github.com/ryanpavlicek/pyaegean/tree/main/training/results)
- data sources, licences, and the reproducibility manifest:
  [Data & Provenance](Data-and-Provenance)
- the established / measured / exploratory framework and how to audit a result:
  [For Specialists](For-Specialists) and [Limitations](Limitations)

This is a documentation page, not an academic paper, and it does not claim to be
one. It describes what the code and data actually do, with the commands to
reproduce every number yourself.

---

## At a glance

| Section | The question it answers | Primary source |
| --- | --- | --- |
| [Evidence-tier framework](#1-the-evidence-tier-framework) | Is this a fact, a measurement, or a hypothesis? | [For Specialists](For-Specialists) |
| [Evaluation methodology](#2-evaluation-methodology) | How are the Greek NLP numbers measured, and what do they mean? | [Benchmarks](Benchmarks) |
| [Leakage control](#3-leakage-control) | How is the test set kept out of training? | [Benchmarks](Benchmarks) |
| [Training and quantization](#4-training-and-quantization) | How is the shipped model built and shrunk without losing accuracy? | [`training/README.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/README.md) |
| [Provenance, licensing, reproducibility](#5-data-provenance-licensing-and-reproducibility) | Where does every byte come from, and may I redistribute it? | [Data & Provenance](Data-and-Provenance) |

---

## 1. The evidence-tier framework

Everything pyaegean reports falls into one of three registers, and each result is
marked so you always know which one you are looking at. The register also tells
you what a *wrong* result is: a correction, a challenge to a number, or a
refutation of a hypothesis.

| Register | What it covers | How it is marked | If it is wrong, it is a… |
| --- | --- | --- | --- |
| **Established** | Facts carried from editions, lexica, and the Unicode standard: Linear B / Cypriot sign values, the Greek lexicon and morphology (Perseus AGDT, LSJ), bundled transliterations, the find-site gazetteer. | Each cites its source (`info` / `cite`, [Data & Provenance](Data-and-Provenance), `NOTICE`). | **correction** |
| **Measured** | Model accuracies reported leakage-free on held-out data (the Greek lemmatizer / tagger / parser and the neural pipeline). | A number with a reproducible protocol (this page, [Greek NLP](Greek-NLP), `docs/benchmarks.md`). | **reproduce or challenge** the number |
| **Exploratory** | Anything decipherment-adjacent over the **undeciphered** Linear A material (cross-linguistic distances, morphological clusters, structure heuristics, metrological guesses) and **all** AI-layer output. | An explicit `[EXPLORATORY …]` tag, an `exploratory=True` flag, a red badge in Jupyter, and an auditable `trace()`. | **validation** (confirm or refute) |

### Editorial certainty travels with every token

Every token carries an **editorial certainty** following Leiden / EpiDoc
conventions, so an edition's apparatus survives into the data model and back out
through the EpiDoc and JSON round-trips. The four states are exhaustive:

| `ReadingStatus` | Meaning | EpiDoc / Leiden |
| --- | --- | --- |
| `certain` | securely read (the default) |— |
| `unclear` | damaged but read | `<unclear>` / underdot |
| `restored` | editorially supplied | `<supplied>` / `[ ]` |
| `lost` | not preserved / lacuna | `<gap>` or `<supplied reason="undefined">` / `[---]` |

The bundled corpora are normalized transcriptions, mostly `certain` with a real
fraction damaged. In the bundled Linear A corpus 552 tokens load as `LOST` and
120 as `UNCLEAR` (together touching 366 of the 1,721 documents), so any analysis
can choose to trust, weight, or exclude them rather than have the damage hidden.

### The undeciphered scripts are never presented as read

pyaegean covers two **undeciphered** scripts, and treats them honestly:

- **Linear A** (`lineara`): of 342 signs in the bundled inventory, **50 carry an
  empirical sound value**, drawn from the 81 signs shared with the Linear B grid
  and each stamped with a `confidence`; the rest have no agreed reading. The
  phonetic transcription uses Linear B sound values only as a **working
  convention**. There is deliberately **no Greek-reading bridge** for Linear A;
  anything in that direction lives in the exploratory AI layer, labeled as such.
- **Cypro-Minoan** (`cyprominoan`): of its **99 catalogued signs, none** carries a
  settled sound value, so pyaegean offers no transliteration or lexicon for it,
  only the sign inventory and sign-sequence tokenization.

The two deciphered syllabaries (Linear B, Cypriot) *do* carry a Greek-reading
bridge, because those scripts write Greek; that bridge is **established**, not
exploratory.

### Auditing an exploratory result

Because exploratory output is only as good as the evidence under it, the AI layer
makes that evidence visible. Every generative result returns an
`ExploratoryResult` you can audit: the `[EXPLORATORY …]` label travels with the
text, `trace()` groups the exact local facts the model was given by source and
ref, and a trace that reads `grounding: none (ungrounded generation …)` tells you
the answer rested on the model's parametric knowledge alone. Grounding fidelity
itself is *measured* like an accuracy number (`ai.run_eval`, `aegean ai eval`),
scoring **groundedness** and **fabrication rate** rather than authority. The full
walkthrough is on [For Specialists](For-Specialists).

---

## 2. Evaluation methodology

The Greek NLP accuracy numbers are the project's **measured** claims. They are
scored on the standard Ancient Greek benchmarks under a fixed, reproducible
protocol. The full protocol, the cross-tool comparison tables, and their
citations are in
[Benchmarks](Benchmarks);
this section summarizes it and reports **pyaegean's own numbers** (per the wiki
convention, cross-tool comparisons stay in the benchmarks doc).

### Protocol

- **Test sets.** The Universal Dependencies Ancient Greek test folds:
  `UD_Ancient_Greek-Perseus` (commit `331ddef`, CC BY-NC-SA 2.5) and
  `UD_Ancient_Greek-PROIEL` (commit `a4ab8d4`, CC BY-NC-SA 3.0). Both are fetched
  to the cache for **evaluation only**: never bundled, never trained on.
- **Scorer.** The official CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`,
  MPL 2.0), fetched sha256-pinned and imported from the cache. Reported figures
  are the evaluator's **F1** per metric.
- **Gold tokenization.** pyaegean runs over each fold's gold `FORM` column, so the
  scores measure tagging / lemma / parsing quality rather than tokenizer
  agreement. The neural pipeline is *also* measured end-to-end from raw text
  through pyaegean's own tokenizer (tokens F1 99.97), and the scores track the
  gold-tokenization figures closely, so tokenization is not a bottleneck on this
  fold.
- **No tagset reconciliation on the UD folds.** UPOS and lemmas are scored exactly
  as emitted; convention gaps count against pyaegean here, unlike
  `greek.evaluate_on_proiel`, which reconciles tagsets to isolate real errors.
- **Lemma scoring.** On the UD folds, lemmas use the evaluator's exact string
  match with **no** added normalization (the UD gold is already NFC and carries no
  homograph-index digits). Convention differences (principal-part choice,
  movable-nu, proper-noun citation form) therefore count as errors rather than
  being normalized away. The native-corpus checks (`evaluate_on_nt` /
  `evaluate_on_proiel`) apply a light clean-up (NFC plus homograph-digit
  stripping) because those golds are not pre-normalized.
- **Train / dev / test discipline.** Training is the leakage-clean corpus (below).
  The **dev** material is used for early stopping, checkpoint selection, light
  schedule tuning, and the quantization gate; the **test** folds are scored once
  on the finished model and never used for any selection.

### How successor checkpoints are selected

The historical v3 training script kept a local average of LAS and lemma accuracy. Future
successor experiments instead use one frozen, machine-readable selection policy over the
leakage-checked Perseus and PapyGreek development sources. The policy names the exact release
decoder, protects all seven reported tasks globally and by source plus OOV lemma behavior,
and gives the literary and documentary sources equal total weight. No protected development
value may fall more than 0.01 percentage point below its baseline.

The selector verifies the real source manifest and each candidate's report, recomputes scores
from integer counts, rejects missing or mismatched evidence, and ranks surviving candidates by
Pareto fronts and declared deterministic tie breakers. This is development-only work: the
selector neither runs a model nor sees a locked test fold. The locked tests remain a one-shot
measurement only after the complete candidate has been frozen.

Export and optimization are part of that gate rather than separate packaging chores. The
conversion commands first create a staged artifact, rebuild reference and candidate development
reports from their prediction records, and compare every protected task/source metric plus decoded
UPOS, XPOS, UFeats, lemma, head, and relation. A framework export must be exactly prediction-
identical to its reference. An optimized artifact may use only the declared small tolerances and
must actually reduce total artifact bytes.

Qualification also runs the complete development population through ONNX Runtime on CPU in
sequential/windowed mode and records latency, resident memory, artifact size, runtime versions, and
the active execution provider. CUDA is probed when installed. These private development records
decide whether a candidate may be promoted; they are not published benchmark numbers and do not
read the locked test folds. A smaller graph is not automatically described as faster.

### What the metrics mean

All are percentages against a human-annotated gold standard; higher is better.

| Metric | In plain terms |
| --- | --- |
| **UPOS** | Universal part of speech: the basic word class from UD's 17-tag set. |
| **XPOS** | The language-specific (treebank's own) finer-grained tag; not comparable across treebanks with different tagsets, so sometimes marked n/a. |
| **UFeats** | The full morphology (case, number, gender, tense, mood, voice, person). A word counts only if *every* feature is right: the strictest word-level tag. |
| **Lemma** | The dictionary / citation form (`λέγει` → `λέγω`). |
| **UAS** | Unlabeled Attachment Score: the fraction of words hooked to the correct syntactic parent. |
| **LAS** | Labeled Attachment Score: UAS, but the dependency link must also carry the right relation label. The usual headline parsing number. |

Two supporting terms: the scorer reports **F1** (the balance of precision and
recall) per metric, and a **bootstrap confidence interval** (e.g. `[89.6, 90.9]`)
is the range a score would plausibly fall in on similar data, estimated by
re-sampling the fold's sentences. A narrow interval means the number is stable,
not a lucky fold.

### pyaegean's measured numbers (the shipped neural pipeline)

The shipped joint model (`grc-joint-v3`, activated by
`greek.use_neural_pipeline()`, the `[neural]` extra) is one GreBerta-encoder
checkpoint serving UPOS, XPOS, UD FEATS, dependency trees (single-root
Chu-Liu/Edmonds MST decoding, so non-projectivity is handled natively), and
lemmas. Measured through the package's own inference code:

| Test fold | Lemma | UAS | LAS | UPOS | UFeats | XPOS |
| --- | --- | --- | --- | --- | --- | --- |
| UD Perseus (in family) | 94.27 | 90.24 | 85.65 | 97.02 | 96.04 | 93.48 |
| UD PROIEL (out of domain) | 90.51 | 82.48 | 63.50 | 86.69 | 59.43 | n/a |

The shipped checkpoint is one of **five seed replicates** of the recipe; across
those seeds the UD Perseus test mean ± standard deviation is LAS 85.58 ± 0.10,
UAS 90.15 ± 0.12, UPOS 97.00 ± 0.06, UFeats 96.06 ± 0.04, lemma 94.30 ± 0.02,
XPOS 93.52 ± 0.05 (PROIEL LAS 63.50 ± 0.04), so the headline figures are
representative, not a lucky seed. Within-fold 95% bootstrap confidence intervals
(percentile bootstrap over the fold's sentences, `greek.bootstrap_ud`'s default of
999 resamples) accompany every headline number in `docs/benchmarks.md`.

**Out of domain is always reported alongside in-family.** PROIEL is a treebank
none of pyaegean's models train on, so its numbers are the honest generalization
figure. The remaining PROIEL LAS and UFeats gaps are largely convention
divergence between the two treebanks' UD conversions (PROIEL annotates feature
types the Perseus scheme lacks, and its XPOS is a different tagset entirely), a
measurement boundary rather than a model defect.

A second out-of-domain check scores the pipeline against the **Nestle 1904** Greek
New Testament's own gold (`greek.evaluate_on_nt()`): lemma 87.96, UPOS
(reconciled) 86.75 over 137,303 tokens. The model never trains on the NT.

### The pure-Python baseline is a floor, not the accuracy story

The zero-dependency stack (`use_treebank() + use_tagger() + use_lemmatizer() +
use_parser()`) is the offline, no-heavy-deps path and reads like a baseline
(Perseus test UPOS 86.73, PROIEL test UPOS 78.83). Its tagger, lemmatizer, and
parser are built from the *full* AGDT, which contains the UD-Perseus test
sentences, so its Perseus-fold scores are an **in-training upper bound** reported
for orientation; the PROIEL fold is its honest number. The neural pipeline, not
the baseline, carries the accuracy claims.

### Reproduce the numbers

```python
from aegean import greek
greek.use_neural_pipeline()
greek.evaluate_on_ud("perseus", "test")   # in-family
greek.evaluate_on_ud("proiel", "test")    # out of domain
greek.evaluate_on_nt()                     # Koine / NT, out of domain
```

```bash
aegean greek eval nt          # the NT row from the shell
```

The published offline-stack rows are re-measured against the claims registry by
`scripts/check_benchmarks.py`; every published number lives in
`training/results/published-claims.json`, and `tests/test_benchmark_claims.py`
pins the docs to the registry so a documented number cannot drift silently. Full
tables, the field's published numbers, and citations:
[Benchmarks](Benchmarks).
The evaluation call sites are documented on
[Greek NLP → Standard-benchmark evaluation](Greek-NLP#standard-benchmark-evaluation-universal-dependencies)
and [Greek NLP → Neutral evaluation](Greek-NLP#neutral-evaluation-out-of-agdt).

---

## 3. Leakage control

UD Perseus is converted from the AGDT, the treebank pyaegean's Greek backends are
built from, so a naïve evaluation would leak the test set into training. Two
controls keep the neural pipeline's numbers honest:

- **The UD-Perseus exclusion manifest.** `greek.agdt_ud_overlap()` resolves every
  UD-Perseus dev and test sentence to its AGDT source and verifies the reference
  by NFC form-sequence comparison: **2,443 sentences across 5 AGDT files, all
  form-identical**. The neural model's training split excludes all of them (cached
  at `ud-grc/agdt-ud-exclusion.json`).
- **PROIEL is held out entirely.** No pyaegean model trains on PROIEL, so it is a
  genuine out-of-domain fold. The combined-corpus model adds the Gorman and
  Pedalion treebanks (both CC BY-SA 4.0); the overlap audit excluded 1,591 Gorman
  and 155 Pedalion sentences matching either evaluation fold, and Gorman's
  Herodotus files (the same work as PROIEL's `hdt.xml`) are excluded at source.

One caveat applies to the **pure-Python baseline** only, not the neural pipeline:
it is built from the full AGDT (which contains the UD-Perseus test sentences), so
its Perseus-fold scores are an in-training upper bound, and the PROIEL fold is its
honest number. This is stated in place wherever the baseline is reported.

The licence split behind these controls is not incidental: the **models train
only on the CC BY-SA treebanks** (AGDT, Gorman, Pedalion), which permit it, while
the **CC BY-NC-SA evaluation treebanks** (UD Perseus, UD PROIEL, PROIEL) are
fetched for evaluation only and never trained on, satisfying both the leakage
discipline and the NonCommercial obligation at once (see §5).

---

## 4. Training and quantization

The training code lives in
[`training/`](https://github.com/ryanpavlicek/pyaegean/tree/main/training) and
**nothing in it ships in the wheel**; trained artifacts are published as GitHub
release assets and fetched to the cache, never bundled. The evidence for every
claim below is in
[`training/results/`](https://github.com/ryanpavlicek/pyaegean/tree/main/training/results).

### Data protocol

Training data is leakage-clean against the evaluation folds (§3):

- **train** = AGDT + Gorman + Pedalion (about 1.41 M tokens), minus every sentence
  in the UD-Perseus dev+test exclusion manifest (`greek.agdt_ud_overlap`).
- **dev** = the AGDT sentences behind the UD-Perseus dev fold (early stopping,
  checkpoint selection, light schedule tuning, and the quantization gate).
- **test** = in neither train nor dev; final numbers come only from
  `greek.evaluate_on_ud("perseus", "test")` against a finished model.

`training/data/` and `training/out/` are gitignored; the datasets rebuild
deterministically from the cache.

### The model, in stages

One **GreBerta** encoder serves every task from a single forward pass. It is built
in five stages, each with a dataset builder and a training script:

- **Stage A — encoder selection.** Fine-tune UPOS on each candidate encoder under
  an identical budget; pick on dev accuracy, generalization to unseen forms, size,
  and licence. GreBerta (a RoBERTa for Ancient Greek, Apache-2.0) is the shipped
  encoder.
- **Stage B — joint tagger.** UPOS + XPOS + UD FEATS on the GreBerta encoder,
  trained on UD-convention labels from the AGDT→UD converter.
- **Stage C — biaffine parser.** Dozat–Manning arc and relation scorers on the
  shared encoder, with single-root Chu-Liu/Edmonds MST decoding at evaluation
  (non-projective trees handled natively).
- **Stage D — lemmas.** A word-level edit-script classifier (Chrupała edit trees)
  plus a train-only lookup, on the same checkpoint.
- **Stage E — export and quantize.** Export to ONNX (fp32, torch-free at
  inference: the reproducibility `grc-joint-v2` asset), then quantize weight-only
  to produce the shipped `grc-joint-v3` asset.

Candidate joint checkpoints use the shared, dependency-free
`pyaegean-neural-preprocessing-v1` contract for training, evaluation, and package
inference. The checkpoint records its annotation profile, NFC normalization,
pretokenized Roberta policy, alignment rules, and subword limit; export validates
those fields against the serialized tokenizer. The exporter requires a distinct
model identity, refuses stale or foreign output files, and binds every required
artifact in a schema-1 content manifest. The published `grc-joint-v3` archive keeps
its legacy manifest, behavior, and measurements unchanged.

Each successor training receipt binds the exact selection-policy file and digest, so the
checkpoint cannot be separated from the rule that selected it.

Each candidate's operational record is also bound to the report's model identity and complete
bundle digest. Optimization accepts only the exact fp32 source named by its reference evidence,
and passing candidates receive reproducible archives. Labels such as `fast` or `compact` require a
separate evidence-backed variant decision; an ONNX numeric format does not earn a label by itself.

The runtime registry freezes `default`, `fast`, `compact`, and optional `balanced` independently
of any successor artifact. `default` means the release-selected artifact and makes no speed or
size claim; it remains the exact `grc-joint-v3` asset. `compact` requires artifact bytes no greater
than 90% of the reference. `fast` requires five same-environment complete CPU runs, median latency
no greater than 90% of the reference, and at least four candidate runs below the reference median.
`balanced` combines the compact bound with five runs whose median latency and median peak resident
memory are each no greater than 105% of the reference. These are label definitions, not accuracy
claims. Until a qualified successor earns them, the three non-default labels remain reserved and
unavailable. Public award receipts contain operational summaries and hashes, not development
scores, predictions, rejected candidates, or raw timing series.

### The quantization discipline

The shipped model is **quantized at about 173 MB** (tar.gz; 182 MB uncompressed
`model.onnx`), roughly 3× smaller than the fp32 build (518 MB tar.gz / 556 MB
uncompressed), while the measured UD Perseus test scores are
unchanged within ±0.02 (UPOS 97.0 / UFeats 96.0 / lemma 94.3 / UAS 90.2 /
LAS 85.6). The recipe is **weight-only int8 + fp16, activations kept fp32**:
onnxruntime MatMulNBits (block 128, symmetric) on the MatMul weights, fp16 on
everything else (crucially the ~160 MB word-embedding table), activations fp32 by
design.

**Full int8 (quantized activations) is excluded because it collapses the GreBerta
encoder.** Its activation outliers do not survive 8-bit quantization: the recorded
dynamic and static recipes dropped UPOS from 97 to 16–32 and LAS from 86 to 1–13.
Full int8 exceeded the ≤0.3-point acceptance limit and is not shipped. Keeping
activations fp32 and quantizing only the weights reduces the artifact size without
a measured accuracy loss. The excluded recipe is recorded
in `training/results/gate-report.json`, and the shipped sizes plus the measured
score comparison in `training/results/v3-quantize-report.json`.

The trade-off the quantization *does* carry is **CPU throughput**, not accuracy:
the int8 MatMulNBits kernels run several times slower than fp32 MatMul on this
workload (roughly 20–70 words/s quantized versus roughly 300 words/s fp32 on the
development machine), so the quantized default optimizes download size and disk,
not speed. Throughput is **hardware-dependent and illustrative, not a pinned
benchmark** (unlike the accuracy figures, which are deterministic and
re-measured), and throughput-sensitive work can fetch the fp32 `grc-joint-v2`
asset instead. The quantized model needs `onnxruntime >= 1.23` (the 8-bit
MatMulNBits CPU kernel), so the `[neural]` extra floor was raised from 1.17 to
1.23; the fp32 model stays available at the `grc-joint-v2` release for
reproducibility.

Both models run **torch-free** at inference, on numpy + onnxruntime, loaded only
on activation.

### Annotation and domain profile records

The annotation registry is a provenance layer, not another model evaluation. Typed
`AnnotationProfile` values declare output labels, relation scheme, segmentation,
normalization, mapping direction, reversibility/loss, and evidence. `DomainProfile`
values describe the source scope and layer; they are not detectors and are not
selected from `TextProfile`/`profile_text` or from the confidence `domain` label.
Profiles are immutable, canonically serialized, and SHA-256 identified.

The canonical output convention remains the supported inference path. Perseus/AGDT
and UD-PROIEL differences (including POS collapse, token-row differences, feature
gaps, and dependency restructuring) are diagnostic and can be non-invertible, not a
general source-compatible conversion mode. The separate native-PROIEL XML evaluation
projection strips `#N` homograph suffixes and omits empty tokens; exact UD-fold
scoring does not use that cleanup. The
PapyGreek `orig` convention changes the diplomatic `FORM` surface while retaining
regularized-layer gold analyses and documented fallbacks. Receipt schema 4 binds the
runtime variant, composed output profile, and ordered post-processing identity when
present. Schemas 1 through 3 remain readable for current hosted evidence, and the
`grc-joint-v3` identity remains unchanged.

---

## 5. Data provenance, licensing, and reproducibility

The full accounting of where every byte comes from is on
[Data & Provenance](Data-and-Provenance); this section surfaces the parts that
bear on trusting a result.

### Bundled vs fetched, and why the wheel stays small

Code and tiny text JSON are **bundled** and work offline with zero third-party
dependencies. Large or licence-restricted assets are **never bundled**: they are
fetched on demand into a local, sha256-verified cache. The wheel ships only code +
tiny JSON, and CI's `scripts/check_footprint.py` enforces exactly that (plus an
instant, heavy-dependency-free import). A fetched dataset is **permanent until you
delete it**: the "cache" is a permanent local store, not an evicting one.

### The licence split that keeps training clean

The provenance rules and the leakage rules are the same rules seen from two sides:

- **Trained on (permit it):** the AGDT (CC BY-SA 3.0), Gorman (CC BY-SA 4.0), and
  Pedalion (CC BY-SA 4.0) treebanks. The derived artifacts are republished under
  the same ShareAlike terms, clearly labeled, and fetched to the cache, never
  bundled.
- **Evaluation only, never trained on:** the UD Ancient Greek treebanks
  (UD-Perseus CC BY-NC-SA 2.5; UD-PROIEL CC BY-NC-SA 3.0) and the PROIEL treebank
  (CC BY-NC-SA 3.0), plus the CoNLL-2018 evaluator (MPL-2.0). These are fetched for
  `evaluate_on_ud()` / `evaluate_on_proiel()` only, and their NonCommercial +
  ShareAlike obligations pass through to you.

Model cards make the base-vs-derivative licence explicit: the neural pipeline's
base encoder is **bowphs/GreBerta** (Apache-2.0), and the released `grc-joint`
bundle is **CC BY-SA 4.0**, fetched to the cache, never bundled, so the wheel
itself stays **Apache-2.0**. The bundled Aegean sign data is from the Unicode
Character Database (Unicode licence); the Linear A corpus JSON is GORILA via
mwenge/lineara.xyz (Apache-2.0), with the facsimile imagery referenced, never
redistributed. The per-source rights table, including the NonCommercial DAMOS /
SigLA corpora and the CC0 Nestle 1904 NT, is on
[Data & Provenance](Data-and-Provenance).

### Pinning an analysis for reproducibility

Every dataset pyaegean can touch is versioned and hashable. `data.versions()`
returns a manifest with `package`, `bundled` (each JSON file hashed straight from
the installed wheel), and `fetched` (each remote asset's pinned URL, pinned
sha256, licence, and cached state). Matching sha256s mean byte-identical data.

```python
import json, aegean
from aegean import data
with open("data-versions.json", "w", encoding="utf-8") as f:
    json.dump({"package": aegean.__version__, "data": data.versions()}, f, indent=2)
```

```bash
aegean data versions --json > data-versions.json
```

To pin an analysis for a paper, record `aegean.__version__` and dump this manifest
alongside your results. Loaded literary works additionally record the exact
upstream commit as `Provenance.data_version`, and every `Corpus` carries a
`Provenance` that stamps exports and produces a citation of the **exact subset**
you used. Cite the underlying edition, not pyaegean's wrapper: the mechanics are
on [For Specialists](For-Specialists) and [Data & Provenance](Data-and-Provenance).

### Training-environment evidence

The prospective `training/environment-lock.json` remains an explicitly
non-authorizing template. The separately reviewed records under
`training/results/a17-environment/` bind the complete 48-package resolver closure,
CPython 3.12.13, a clean source commit, and one NVIDIA RTX PRO 6000 Blackwell
Server Edition allocation with CUDA runtime and Torch CUDA 12.8, cuDNN 9.10.2,
compute capability 12.0, 96 GB-class VRAM, and bf16 precision. The preflight was
re-observed before promotion; GreBerta was resolved at its immutable commit through
metadata only; and a deterministic fixture receipt binds the config, input, output,
hardware, environment, and artifact hashes without model execution.

These records establish that the reproduction environment and receipt path were
captured consistently. They do not show that v4 has been trained, and they make no
model-quality or performance claim. The published evidence summary indexes only the
normalized reviewed records; raw package-manager metadata remains private because it
contains a large amount of unrelated project-link metadata.

### Bounded public review receipt

From a clean source checkout, `python scripts/reproduce_review.py` verifies the
canonical public evidence records by SHA-256 and reproduces one small,
project-authored offline result. It does not use the network, execute a model, write
bytecode, or create a pyaegean cache. The receipt is an integrity and regression
check, not a substitute for the neural protocol or external scholarly review. See
[Independent Review](Independent-Review) for the model card, data card, limitations,
and discrepancy path.

---

## See also

- [Greek NLP](Greek-NLP): the pipeline, the evaluation call sites, and the tier
  switch (baseline → treebank → neural)
- [Benchmarks](Benchmarks):
  the full protocol, the field's published numbers, and citations
- [Data & Provenance](Data-and-Provenance): every dataset, licence, and the cache
  layout
- [For Specialists](For-Specialists): auditing, citing, and correcting a result
- [Independent Review](Independent-Review): the bounded evidence receipt and reviewer map
- [Limitations](Limitations): the candid register of what the toolkit can and
  cannot claim
