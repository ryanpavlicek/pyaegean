# Benchmarks

This page collects pyaegean's measured Greek NLP results, the evaluation protocol
that produced them, and cited comparison numbers from the literature. The opt-in
**[neural pipeline](Greek-NLP#the-neural-pipeline-opt-in)**
(`greek.use_neural_pipeline()`, the `[neural]` extra) is evaluated end-to-end on
the UD Ancient Greek (Perseus) benchmark through the shipped package using the
official CoNLL 2018 evaluator.

Every figure on this page follows the recorded protocol and matches the canonical
record in `docs/benchmarks.md`. Published numbers live in
`training/results/published-claims.json`; per-commit tests verify that the
documentation matches the registry exactly, and the offline-stack rows are
re-measured against it. See [Reproduce the numbers](#reproduce-the-numbers) to
run any evaluation locally, and
[Where this lives](#where-this-lives-canonical-source) for how published figures
are updated.

## What the metrics mean

All metrics are percentages against human-annotated gold (higher is better):

- **UPOS**: Universal Part of Speech from UD's 17-tag inventory (noun, verb,
  adjective, preposition, etc.).
- **XPOS**: Language-specific part-of-speech tag from each treebank's own
  fine-grained tagset. Marked `n/a` where tagsets are not cross-comparable.
- **UFeats**: Universal Features (case, number, gender, tense, mood, voice,
  person). Scored exact-match across all features on a token, making it the
  strictest word-level tag.
- **Lemma**: Dictionary citation form (`λέγει` → `λέγω`, `ἀνθρώπους` → `ἄνθρωπος`).
- **UAS**: Unlabeled Attachment Score — fraction of tokens attached to the
  correct syntactic head.
- **LAS**: Labeled Attachment Score — fraction of tokens with both the correct
  head and the correct dependency relation.

## The neural pipeline (shipped)

The shipped joint model (`grc-joint-v3`) is a single GreBerta-encoder checkpoint
predicting UPOS, XPOS, UD FEATS, dependency trees (decoded by single-root
Chu-Liu/Edmonds MST, supporting non-projective trees natively), and lemmas in
one forward pass. It is trained leakage-clean on the audited AGDT + Gorman +
Pedalion corpus (1.41 M tokens). Measured through pyaegean's own inference code
with gold tokenization and the official CoNLL 2018 evaluator:

| Test fold | Lemma | UAS | LAS | UPOS | UFeats | XPOS |
| --- | --- | --- | --- | --- | --- | --- |
| UD Perseus | **94.27** | **90.24** | **85.65** | 97.02 | 96.03 | 93.47 |
| UD PROIEL | 90.51 | 82.47 | 63.50 | 86.68 | 59.43 | n/a |

UD PROIEL is an **out-of-domain** fold that no pyaegean model trains on (see
[Leakage controls](#leakage-controls)). Its lower LAS and UFeats scores reflect
annotation convention differences between the two UD conversions (PROIEL marks
five feature types absent from Perseus and uses a different XPOS tagset) in
addition to domain shift.

**Historical seed replication.** Five decoder-v1 training runs of this recipe
averaged **LAS 85.58 ± 0.10**, UAS 90.15 ± 0.12, UPOS 97.00 ± 0.06, UFeats
96.06 ± 0.04, lemma 94.30 ± 0.02, and XPOS 93.52 ± 0.05 (PROIEL LAS
63.50 ± 0.04). These runs document training stability across seeds under decoder
v1; the current checkpoint scores and confidence intervals below were measured
with decoder v2.

The table below lists pyaegean's UD Perseus scores and 95% confidence intervals
beside cited published results. The margin column shows the arithmetic
difference:

| Metric | pyaegean | 95% CI | cited comparison | margin |
| --- | --- | --- | --- | --- |
| UPOS | 97.02 | [96.76, 97.29] | 95.83 (2023) | +1.19 |
| XPOS | 93.47 | [93.09, 93.90] | 91.09 (2023) | +2.38 |
| UFeats | 96.03 | [95.75, 96.33] | 92.56 (odyCy 2023) | +3.47 |
| Lemma | 94.27 | [93.89, 94.62] | 91.14 (GreTa+Chars 2023) | +3.13 |
| UAS | 90.24 | [89.62, 90.80] | 88.20 (2023) | +2.04 |
| LAS | 85.65 | [84.94, 86.29] | 83.98 (2023) | +1.67 |

Confidence intervals are sentence-level percentile bootstraps with 999 resamples
(the default of `greek.bootstrap_ud()`). The lower bounds (LAS 84.94, UAS 89.62)
remain above the cited 83.98 / 88.20 numbers. Full citations appear in
[Cross-tool comparison](#cross-tool-comparison-with-citations).

## Legacy aggregate calibration

Schema-1 aggregate calibration remains available via `use_calibration()` and the
legacy flat confidence fields. It applies temperature scaling fitted on the UD
Perseus **dev** fold (one scalar temperature per head) as an unscoped UPOS and
composed-lemma proxy for `grc-joint-v3`:

| Head | Temperature | Dev ECE (raw → calibrated) | Test ECE (calibrated) |
| --- | --- | --- | --- |
| UPOS | 1.34 | 0.94% → 0.19% | 1.11% (raw was 1.95%) |
| Lemma | 0.66 | 8.77% → 5.39% | 6.29% |

The lemma row calibrates the edit-script head against composed-lemma accuracy.
Offline lexicon, rule, seed, and paradigm outputs carry no neural confidence.
These figures measure literary-prose calibration for `grc-joint-v3` and do not
function as an out-of-domain detector. Full protocol details are in
`docs/benchmarks.md`; evidence is stored in
`training/results/calibration-2026-07-11.json`.

The typed confidence API (`token_confidence`, `sentence_confidence`) attaches
task, source, and domain scope together with explicit unavailability reasons. A
locked-test-qualified **Schema-2 calibration registry**
(`calibration_registry_v2.json`, loaded via `greek.use_calibration_registry()`)
is bundled for `grc-joint-v3`. Its logit-affine parameters were fitted strictly
on development folds (`literary` on UD Perseus dev and `documentary_native` on
PapyGreek dev) across all six tasks (`upos`, `xpos`, `feats`, `lemma`, `head`,
`relation`) and all four lemma routes, then evaluated once on the five locked
test folds (`training/results/stage1-oov-rerank-and-calibration-2026-11-24.json`).
No default abstention threshold is bundled; callers set thresholds via
`AbstentionPolicy` or rank review sheets with
`priority="calibrated_risk", budget=N`.

| Locked test fold (`confidence_domain`) | Lemma ECE15 (raw → calibrated) | Brier (raw → calibrated) |
| --- | --- | --- |
| UD Perseus test (`literary`) | 0.0566 → 0.0138 | 0.0598 → 0.0493 |
| UD PROIEL test (`literary`) | 0.0882 → 0.0363 | 0.0955 → 0.0752 |
| Tragedy — *Bacchae* (`literary`) | 0.1118 → 0.0545 | 0.1257 → 0.0972 |
| PapyGreek `reg` (`documentary_native`) | 0.0819 → 0.0258 | 0.0957 → 0.0772 |
| PapyGreek `orig` (`documentary_native`) | 0.1252 → 0.0609 | 0.1455 → 0.1149 |

## Opt-in weighted OOV lemma reranker

`greek.use_oov_lemma_reranker(config="weighted")` enables a bundled opt-in
post-processor (`oov_lemma_reranker_v1.json`) that leaves `grc-joint-v3` weights
untouched and incurs zero overhead when inactive. For out-of-vocabulary words,
it combines the joint model's top-10 edit-script predictions with train-only
orthographic, Koine phonetic, and preverb-stripped candidates using frozen
dev-fitted weights with no external dictionary leakage. Across all 79,462 tokens
of the five locked test folds, it corrected 1,645 lemmas while regressing 145
(net +1,500 tokens, >11:1 win/loss ratio; evidence in
`training/results/stage1-oov-rerank-and-calibration-2026-11-24.json`):

| Locked test fold | `grc-joint-v3` default Lemma | + weighted OOV reranker | Gain (pp) |
| --- | --- | --- | --- |
| UD Perseus test | 94.27 | **94.96** | +0.69 |
| UD PROIEL test | 90.51 | **91.47** | +0.96 |
| Tragedy (*Bacchae* 1–169) | 87.89 | **89.39** | +1.50 |
| PapyGreek (`reg`) | 89.63 | **91.66** | +2.03 |
| PapyGreek (`orig` diplomatic) | 85.62 | **89.06** | +3.43 |

## Out of domain: Koine / New Testament

`greek.evaluate_on_nt()` scores the shipped neural pipeline against the
**Nestle 1904** New Testament's own gold lemmas and morphology. Because the
model trains on AGDT, Gorman, and Pedalion and never on the NT, this provides an
out-of-domain Koine check independent of PROIEL's NT annotation.

| Test set | Lemma | UPOS (reconciled) | scored tokens |
| --- | --- | --- | --- |
| Nestle 1904 NT (whole) | 87.96 | 86.75 | 137,303 |

Nestle 1904 lemma accuracy sits below the PROIEL-NT row (90.51) mainly because
Nestle 1904 lemma conventions differ from AGDT (principal-part choices,
proper-noun citation forms, movable-nu). UPOS is reconciled (`PROPN` → `NOUN`,
`SCONJ` → `CCONJ`, `AUX` → `VERB`) to isolate genuine POS errors from
Robinson-versus-UD tagset differences. UFeats, UAS, and LAS are omitted because
Robinson morphology does not map one-to-one onto UD FEATS and Nestle 1904 has no
dependency trees. For out-of-domain Koine parsing, the UD PROIEL test fold
above (mostly New Testament text, UAS 82.47) is the closest measured figure.

## Documentary Koine: the PapyGreek fold

Documentary Greek parsing is measured on 1,551 sentences (22,227 tokens) of
papyrus letters and petitions from the PapyGreek Treebanks (CC BY-SA), converted
to the same AGDT scheme used in training.

The primary row scores PapyGreek's **regularized** (`reg`) layer, where editors
normalized spelling toward standard Koine. The raw diplomatic (`orig`) layer,
retaining phonetic spellings and itacism, is evaluated on its own fold via
`evaluate_on_papygreek(layer="orig")` over the same sentences and gold
annotations (reported in the next section).

Of 4,557 annotated source sentences, 1,551 remain after filtering: 1,793 are
excluded for artificial elliptic or inserted nodes that gold tokenization cannot
score, 678 for incomplete annotations, 354 for sentence-form overlap with
training data, 145 for belonging to Trismegistos works present in Pedalion
training, and 36 that fail to yield a clean reading. Work-level exclusions are
applied before exact and punctuation-stripped NFC sentence-form guards. The
earlier 24,105-token row (which retained 145 sentences from 29 overlapping
works) is historical. Excluding elliptic sentences skews the fold toward
complete clauses. Full accounting is in
`training/results/papygreek-fold-manifest.json`.

| Test set | UPOS | XPOS | UFeats | Lemma | UAS | LAS | CLAS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PapyGreek (documentary Koine) | 91.53 | 77.19 | 88.73 | 89.63 | 85.51 | 79.57 | 75.41 |

Scheme-matched out-of-domain parsing scores about +16 LAS points higher than the
convention-divergent PROIEL row. Reproduce with `aegean greek eval papygreek`.
Evaluation runs CPU-sequential (`batch_size=None`) with whole-word windowing for
sentences exceeding the single-pass token limit; partial placeholder tails are
never scored.

The two weakest cells in the row are heavily shaped by annotation conventions,
quantified by `aegean greek eval papygreek --drift`: 4.98 of the 8.47 UPOS gap
points (58.79% of all UPOS errors) fall on coordinating conjunctions alone
(`καί`, `δέ`, `τε`, which carry three incompatible tags across the merged
training treebanks), and 13.31 of the 22.81 XPOS gap points come from convention
or encoding mismatches (coordinator pos-code, common gender `c`, and a gold
`_`-slot artifact). Forgiving those three buckets brings XPOS to 90.50%. This
breakdown is diagnostic only and leaves the published row unchanged.

### Opt-in documentary levers

Two opt-in, default-off post-processing layers adjust neural output for
documentary Greek while keeping default output byte-identical to `grc-joint-v3`.
Each carries its own registry variant row so the baseline PapyGreek row remains
untouched.

- **Lever A** (`greek.use_documentary_reconciliation()`) relabels the closed
  coordinator class (`καί`, `δέ`, `τε`, …) only when the model outputs the
  invalid `X`/`b` tag. On the corrected fold, it modifies 775 UPOS and 783 XPOS
  cells (+3.13 UPOS, +3.18 XPOS) while leaving all other fields identical.
  Earlier dev-selection deltas predated the work-level fold correction and are
  historical. The aggressive `ADV`/`d` option regresses literary text and is
  recommended against.
- **Lever B** (`greek.use_documentary_lemma_rescue()`) looks up unresolved
  neural lemmas in the guarded seed and paradigm tables only (ending-stripping
  rules are excluded because they break even on documentary text and regress
  literary text), recording the result under `SEED` or `PARADIGM` rather than
  `NEURAL`. It makes no additional changes on the corrected fold, so no lemma
  gain is claimed.

Both variants were measured sequentially with full coverage on the pinned fold:

| Variant on the PapyGreek fold | UPOS / XPOS / UFeats / Lemma / UAS / LAS / CLAS |
| --- | --- |
| + Lever A (coordinator reconciliation, conservative) | 94.66 / 80.36 / 88.73 / 89.63 / 85.51 / 79.57 / 75.41 |
| + Lever A + Lever B (lemma OOV rescue, with `use_paradigms`) | 94.66 / 80.36 / 88.73 / 89.63 / 85.51 / 79.57 / 75.41 |

## Diplomatic orthography and Byzantine verse

The diplomatic (`orig`) PapyGreek fold (identical sentences and gold, 1,453
surface form differences) measures the effect of unregularized documentary
spelling: UPOS 90.57 / XPOS 74.64 / UFeats 86.15 / lemma 85.62 / UAS 84.32 /
LAS 77.57 / CLAS 72.97, compared with 91.53 / 77.19 / 88.73 / 89.63 / 85.51 /
79.57 / 75.41 on `reg`. Lemmatization shows the sharpest drop (which the opt-in
weighted OOV reranker above recovers by +3.43 pp to 89.06).

On the DBBE Byzantine book-epigram fold (9,191 tokens of unedited medieval
verse, tagging only), the neural pipeline scores UPOS 86.75 / XPOS 79.23 /
UFeats 81.91 / lemma 76.69. Reproduce with
`aegean greek eval papygreek --layer orig` and `aegean greek eval dbbe`.

## Verse, out of domain: tragedy

The verse fold (manual gold from UNESP Trees, CC BY-SA 4.0; Euripides *Bacchae*
1–169, leakage-checked against training) is a leakage-clean tragedy evaluation;
no prior one is known to us. Because the sample is small (735 tokens), it
carries wide confidence intervals and is reported with its sample size and CI
rather than as a headline: UPOS 90.88 / UFeats 88.16 / lemma 87.89 / UAS 79.73 /
LAS 73.33 (LAS 95% CI [69.75, 78.28]). Tragedy parses roughly 6 LAS points below
the documentary fold, reflecting the difficulty of poetic word order. Reproduce
with `aegean greek eval verse --track tragedy`.

## Pure-Python offline baseline

The zero-dependency stack (`use_treebank() + use_tagger() + use_lemmatizer() +
use_parser()`) runs without optional neural dependencies:

| Fold | UPOS | Lemma | UAS |
| --- | --- | --- | --- |
| Perseus test ⚠ | 86.73 | 97.65 ⚠ | 37.43 |
| PROIEL test | 78.84 | 85.63 (90.38 with the neural lemmatizer) | 35.44 |

Cells marked ⚠ are **in-training upper bounds**: the baseline lookup, tagger,
edit-tree lemmatizer, and arc-eager parser are built from the full AGDT, which
includes the UD-Perseus test sentences (97.65 Perseus lemma reflects lookup
memorization). The PROIEL fold gives the leakage-free baseline. LAS is omitted
because the arc-eager parser emits Prague labels rather than UD relations.
(Perseus: 1,306 sentences / 20,959 words; PROIEL: 1,047 sentences / 13,314
words.)

On the **full New Testament** (137,303 tokens), the bare offline lemmatizer
(`greek.lemmatize` with no backends active) scores **66.98%** (**71.21%** with
the opt-in `greek.use_paradigms()` backend, whose ambiguity guards leave
capitalized surfaces and multi-lemma forms unresolved instead of picking
arbitrarily). This is the "~67% on the full NT" figure cited in
[Limitations](Limitations); the offline-stack guard re-measures it when code
changes.

## Held-out generalization (pure-Python backends)

The opt-in pure-Python tagger and lemmatizer are evaluated in context on a
leakage-free 90/10 AGDT sentence split, reporting the **unseen-form** subset
(forms absent from the training split) separately:

| POS: held-out AGDT (≈54k tokens) | overall | unseen forms |
| --- | --- | --- |
| pyaegean tagger (pure Python, averaged perceptron) | 84.4% | 83.6% |

| Lemma: held-out AGDT | overall | unseen forms |
| --- | --- | --- |
| pyaegean lemmatizer (pure Python, edit-tree) | 84.5% | 40.3% |
| pyaegean `[neural]` lemmatizer (GreTa seq2seq, opt-in) | ~92% | **76.3%** |

A bare treebank lookup scores 0% on unseen forms. Reproduce with
`greek.evaluate_tagger(holdout=0.1)` and `greek.evaluate_lemmatizer()`. Because
unseen Greek lemmas frequently involve stem or accent changes beyond suffix
rewrites, the seq2seq `[neural]` lemmatizer improves unseen accuracy from 40.3%
to 76.3%. Method details are in
[Greek NLP](Greek-NLP#generalizing-pos-tagger-opt-in).

## Evaluation protocol

- **Test sets.** `UD_Ancient_Greek-Perseus` (commit `331ddef`, CC BY-NC-SA 2.5)
  and `UD_Ancient_Greek-PROIEL` (commit `a4ab8d4`, CC BY-NC-SA 3.0), fetched to
  the local cache for evaluation only, never bundled or trained on.
- **Scorer.** Official CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`,
  MPL 2.0), fetched and verified against SHA-256
  `1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`. Reported
  figures are CoNLL F1 percentages.
- **Gold tokenization.** Primary scores run on each fold's gold `FORM` column to
  separate tagging, lemmatization, and parsing from tokenization. End-to-end
  evaluation from raw text through pyaegean's tokenizer achieves tokens F1 99.97
  on Perseus, tracking gold-tokenization accuracy closely.
- **No tagset reconciliation.** UPOS and lemmas on UD folds are scored verbatim.
  Convention differences count as errors here (unlike `greek.evaluate_on_proiel`,
  which reconciles tagsets).
- **Train / dev / test separation.** Training uses AGDT, Gorman, and Pedalion
  minus the UD exclusion manifest. Development folds control early stopping,
  checkpoint selection, schedule tuning, and quantization gates; test folds are
  scored once on the finished checkpoint. Full training protocol is in
  [`training/README.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/README.md).
- **Lemma scoring.** UD folds use exact string match with no post-normalization
  (UD gold is NFC without homograph digits). Native checks (`evaluate_on_nt`,
  `evaluate_on_proiel`) apply NFC normalization and strip `#N` homograph digits
  because those native files are not pre-normalized.
- **Bootstrap CIs.** `greek.bootstrap_ud()` computes sentence-level percentile
  intervals over 999 resamples by default.

### Leakage controls

Because UD Perseus is derived from AGDT, naive training on AGDT leaks the test
set. Two controls prevent leakage in the neural pipeline:

- **UD-Perseus exclusion manifest.** `greek.agdt_ud_overlap()` maps every
  UD-Perseus `dev` and `test` sentence to its AGDT source and verifies identity
  by NFC form-sequence match: **2,443 sentences across 5 AGDT files, all
  form-identical**. All of them are removed before training.
- **PROIEL held out completely.** No pyaegean model trains on PROIEL. For the
  combined training set (AGDT + Gorman + Pedalion, CC BY-SA 4.0), the overlap
  audit removed 1,591 Gorman and 155 Pedalion sentences matching either
  evaluation fold, and excluded Gorman's Herodotus files (shared with PROIEL's
  `hdt.xml`) at source.

This leakage exclusion applies to the neural pipeline; the legacy pure-Python
baseline trains on the full AGDT and its Perseus-fold scores are marked ⚠ as an
in-training upper bound.

## Cross-tool comparison (with citations)

From Kostkan, Kardos, Mortensen & Nielbo, *"OdyCy: A general-purpose NLP
pipeline for Ancient Greek"*, LaTeCH-CLfL 2023
([PDF](https://aclanthology.org/2023.latechclfl-1.14.pdf)), Tables 1–2. Each
pipeline runs its own tokenizer and is scored with spaCy evaluation scripts.
Best per metric in **bold**.

**UD Perseus test fold:**

| Pipeline | POS | Morph | Lemma | UAS | LAS |
| --- | --- | --- | --- | --- | --- |
| odyCy (joint) | **95.39** | **92.56** | 83.20 | **78.80** | **73.09** |
| odyCy (perseus) | 95.00 | 91.98 | 82.56 | 76.71 | 70.31 |
| greCy (perseus) | 93.50 | 90.59 | 75.10 | 76.34 | 70.20 |
| Stanza (perseus) | 91.05 | 91.03 | **87.58** | 78.69 | 71.82 |
| UDPipe (perseus) | 80.95 | 85.70 | 82.73 | 63.97 | 55.81 |
| CLTK | 80.50 | 61.49 | 79.46 | 33.05 | 24.25 |

**UD PROIEL test fold:**

| Pipeline | POS | Morph | Lemma | UAS | LAS |
| --- | --- | --- | --- | --- | --- |
| greCy (proiel) | **98.23** | **94.05** | **98.06** | **85.74** | **82.28** |
| odyCy (joint) | 97.81 | 93.46 | 94.41 | 83.17 | 79.03 |
| Stanza (proiel) | 97.39 | 92.20 | 97.21 | 81.51 | 77.48 |
| CLTK | 96.95 | 90.76 | 96.50 | 57.61 | 54.57 |
| UDPipe (proiel) | 95.97 | 88.62 | 93.17 | 72.40 | 67.48 |

The same paper documents steep cross-treebank drops (for example, Stanza-perseus
scores 59.00 UAS on PROIEL), motivating out-of-domain and unseen-form reporting
alongside in-domain results.

Riemenschneider & Frank (2023), *"Exploring Large Language Models for Classical
Philology"* ([ACL](https://aclanthology.org/2023.acl-long.846/)), report UD
Perseus test scores (trained on UD 2.10 train, gold tokenization, official CoNLL
evaluator, mean of three seeds): GreBERTa **UAS 88.20 / LAS 83.98**, UPOS 95.83,
XPOS 91.09, and GreTa seq2seq lemma **91.14**. Those are the "2023" comparison
entries in the CI table above.

Celano (2025), *"A State-of-the-Art Morphosyntactic Parser and Lemmatizer for
Ancient Greek"* (LM4DH 2025,
[arXiv:2410.12055](https://arxiv.org/abs/2410.12055)), fine-tunes Trankit and
GreTa on AGDT + Gorman + Pedalion (~1.26 M tokens normalized to the AGDT scheme)
and evaluates on his own splits (Trankit UAS 82.28 / LAS 76.67; GreTa lemma
91.17), reproducing Riemenschneider & Frank's UD rows only as a loose reference
across different schemes. pyaegean's joint model uses the same CC BY-SA 4.0
AGDT + Gorman + Pedalion training sources.

Two additional reference points, each measured under its own protocol and listed
for context rather than direct table comparison:

- **Stanza published scores**
  ([performance page](https://stanfordnlp.github.io/stanza/performance.html)),
  under Stanza's own tokenization: **grc_perseus** UPOS 92.41 / UFeats 91.11 /
  lemma 87.86 / UAS 79.46 / LAS 73.97, and **grc_proiel** (in-domain) UPOS
  97.42 / lemma 97.18 / LAS 79.02. Stanza's self-reported Perseus lemma (87.86)
  sits 0.28 above the 87.58 in the OdyCy table; pyaegean's 94.27 is +6.4 above
  Stanza and +3.1 above the GreTa 91.14 comparison row.
- **DILEMMA** ([repository](https://github.com/ciscoriordan/dilemma)) uses a
  similar torch-free ONNX inference path for Greek tagging and lemmatization. It
  publishes accuracy on its own multi-period datasets (93.7% equiv-adjusted on
  DiGreC, 99.7% on Classical Greek) without UD Perseus UAS/LAS scores, so it is
  listed as an architectural reference rather than a same-fold comparison.

**Out-of-domain comparison.** Published PROIEL-trained models train on PROIEL
itself, whereas pyaegean never does. Comparing Perseus-trained systems on the
PROIEL test fold gives 82.47 UAS for pyaegean versus 59.00 UAS for
Stanza-perseus (an arithmetic difference of ~23 UAS).

## Model size and throughput

The shipped checkpoint is quantized to about **173 MB** (`tar.gz`; **182 MB**
uncompressed `model.onnx`), roughly 3× smaller than the fp32 reference
(**518 MB** `tar.gz` / **556 MB** uncompressed). In the recorded decoder-v1
quantization check, UD Perseus test scores remained within ±0.02 (UPOS 97.0 /
UFeats 96.0 / lemma 94.3 / UAS 90.2 / LAS 85.7). Quantization applies
weight-only int8 (`onnxruntime` `MatMulNBits`, block size 128, symmetric) plus
fp16 on remaining tensors while keeping activations in fp32. Full int8
activation quantization breaks the GreBerta encoder due to activation outliers
(dropping UPOS to 16–32 and LAS to 1–13). The shipped bundle requires
**`onnxruntime >= 1.23`** (the `[neural]` floor); the fp32 artifact remains
hosted at the `grc-joint-v2` release for reproducibility.

On CPU, weight-only int8 kernels run slower than fp32: roughly **20–70 words/s**
quantized versus roughly **300 words/s** fp32 on the development machine,
depending on sentence length. Throughput depends on CPU architecture, core
count, and input length, and is reported as an order-of-magnitude estimate
rather than a pinned benchmark; it is re-measured when the model or
`onnxruntime` floor changes.

## Reproduce the numbers

Score the shipped neural pipeline with gold tokenization on the UD and NT folds:

```python
from aegean import greek
greek.use_neural_pipeline()
greek.evaluate_on_ud("perseus", "test")   # {'upos': …, 'ufeats': …, 'lemma': …, 'uas': …, 'las': …, 'xpos': …}
greek.evaluate_on_ud("proiel", "test")    # out of domain
greek.evaluate_on_nt()                    # whole Nestle 1904 NT (≈1 h on plain CPU)
greek.bootstrap_ud("perseus", "test")     # percentile CIs, 999 resamples
```

From the shell (`pip install "pyaegean[cli,neural]"`):

```bash
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval ud --fold proiel --split test --neural
aegean greek eval nt --neural
```

Offline-baseline and held-out AGDT numbers reproduce with the pure-Python
backends and `greek.evaluate_tagger()`, `greek.evaluate_lemmatizer()`, and
`greek.evaluate_parser()`. See
[Greek NLP](Greek-NLP#standard-benchmark-evaluation-universal-dependencies) and
[Evaluation](Evaluation) for all `aegean greek eval` targets. These commands
fetch gold data and may train baseline models locally, so run them only when
reproducing benchmarks.

## A note on the Aegean scripts

The accuracy tables above cover Ancient Greek NLP. Linear B and Cypriot include
Greek-reading bridges, while **Linear A and Cypro-Minoan are undeciphered**, so
there is no gold reading to score translations against and pyaegean never
presents exploratory analyses as ground truth. Aegean-script tooling is verified
by corpus-fidelity and round-trip invariants (see [Linear A](Linear-A),
[Cypriot](Cypriot), and [Limitations](Limitations)).

## Where this lives (canonical source)

`docs/benchmarks.md` in the repository is the canonical, registry-pinned record
for every number on this page. Published values are stored in
`training/results/published-claims.json`; `tests/test_benchmark_claims.py`
verifies on every commit that the docs, README, and wiki match the registry
exactly, and `scripts/check_benchmarks.py --measure` re-runs the offline-stack
rows against it. Any re-measurement updates the registry, evidence file, and
documentation in a single commit.

Related pages: [Methodology](Methodology),
[Greek NLP](Greek-NLP#reproduce-the-numbers-from-the-shell),
[For Specialists](For-Specialists),
[Data and Provenance](Data-and-Provenance), and
[Limitations](Limitations).
