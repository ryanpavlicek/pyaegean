# Greek NLP benchmarks — protocol and numbers

How pyaegean is scored on the standard Ancient Greek benchmarks: the protocol, the
leakage controls that keep the comparison honest, the field's published numbers, and
pyaegean's own measured results. The README and wiki carry only pyaegean's own numbers;
the cross-tool tables live here, with citations.

## What the metrics mean

The tables below score six things a pipeline does to each word (and to the sentence as a
whole). All are percentages: higher is better, and each is the fraction the system got right
against the human-annotated gold standard.

- **UPOS** — *Universal Part Of Speech.* The basic word class (noun, verb, adjective,
  preposition, ...) from Universal Dependencies' 17-tag set. "Did it identify what kind of
  word this is?"
- **XPOS** — the *language-specific* part-of-speech tag: the treebank's own finer-grained
  tagset (more categories than UPOS). Not comparable across treebanks that use different
  tagsets, so it is sometimes marked n/a.
- **UFeats** — *Universal Features:* the full morphology of the word — case, number, gender,
  tense, mood, voice, person. A word counts only if *every* feature is right, so this is the
  strictest word-level tag. "Did it get the complete grammatical parse of the word?"
- **Lemma** — the dictionary/citation form you would look up: `λέγει` → `λέγω`, `ἀνθρώπους`
  → `ἄνθρωπος`. "Did it recover the headword?"
- **UAS** — *Unlabeled Attachment Score:* the fraction of words hooked to the correct
  syntactic parent (which other word each word grammatically depends on). It measures the
  shape of the sentence's dependency tree, ignoring the name of each link.
- **LAS** — *Labeled Attachment Score:* UAS, but the link must *also* carry the right relation
  label (subject, object, modifier, ...). Stricter than UAS (right parent **and** right
  relation), and the usual headline number for parsing quality.

Two supporting terms: the scorer reports **F1** (the balance of precision and recall) per
metric, and a **bootstrap confidence interval** (e.g. `[89.6, 90.9]`) is the range a score
would plausibly fall in on similar data, estimated by re-sampling the fold's sentences — a
narrow interval means the number is stable, not a lucky fold.

## Protocol

- **Test sets:** the Universal Dependencies Ancient Greek test folds:
  `UD_Ancient_Greek-Perseus` (commit `331ddef`, CC BY-NC-SA 2.5) and `UD_Ancient_Greek-PROIEL`
  (commit `a4ab8d4`, CC BY-NC-SA 3.0), fetched to the cache for **evaluation only** (never
  bundled, never trained on).
- **Scorer:** the official CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`,
  MPL 2.0), fetched sha256-pinned
  (`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`) and imported from
  the cache. Reported figures are the evaluator's F1 per metric.
- **Execution:** every published number is measured on the CPU provider
  (`CPUExecutionProvider`), one sentence per model call. GPU execution and batched
  inference (both added in 0.33.0) are throughput conveniences, verified
  prediction-identical to the protocol path on a fixed verification set
  (`training/results/gpu-verify-2026-07-10.json`); a registry re-measure may use them
  only after a full-fold identity check against the sequential CPU run.
- **Gold tokenization:** pyaegean runs over each fold's gold FORM column, so its scores
  measure tagging/lemma/parsing quality, not tokenizer agreement. (The published numbers
  below let each pipeline tokenize raw text; their token accuracy on these folds is ≈100%,
  so the protocols are close but not identical: noted for precision.) The neural pipeline
  is also measured end-to-end from raw text (below), and the numbers hold.
- **No tagset reconciliation:** UPOS and lemmas are scored exactly as emitted. Convention
  gaps (e.g. the AGDT scheme has no PROPN/SCONJ on the PROIEL fold's conventions) count
  against pyaegean here, unlike `greek.evaluate_on_proiel`, which reconciles tagsets to
  isolate real errors.
- **Train / dev / test discipline.** The shipped v3 recipe trained on AGDT minus the
  UD-Perseus dev+test exclusion manifest and used the AGDT sentences behind UD-Perseus dev for
  early stopping, checkpoint selection, light schedule tuning, and its quantization gate.
  Successor experiments use the frozen, leakage-audited Perseus/PapyGreek development manifest
  and a declarative seven-task, source-balanced gate; they do not use any locked test fold for
  selection. Test folds are scored once on the finished candidate. Full protocol in
  `training/README.md`.
- **Lemma scoring.** On the UD folds, lemmas use the evaluator's exact string match with
  **no** added normalization: the UD-Ancient-Greek gold is already NFC and carries no
  homograph-index digits, so none is stripped, and there is no case- or diacritic-folding.
  Convention differences (principal-part choice, movable-nu, proper-noun citation form)
  therefore count as errors rather than being normalized away. (The native-corpus checks
  `evaluate_on_nt` / `evaluate_on_proiel` do apply a light lemma clean-up, NFC plus
  homograph-digit stripping, since those golds are not pre-normalized.)
- **Reproduce** the shipped pipeline with:

  ```python
  from aegean import greek
  greek.use_neural_pipeline()
  greek.evaluate_on_ud("perseus", "test")
  greek.evaluate_on_ud("proiel", "test")
  ```

  Reviewers who first want to verify the checked-in evidence bytes and a small
  zero-dependency result can run `python scripts/reproduce_review.py` from a clean
  source checkout. That bounded receipt does not download the model or reproduce
  the neural values above; this protocol remains the authority for those rows.

## Leakage controls

UD Perseus is converted from the AGDT: the treebank pyaegean's Greek backends are built
from — so a naïve evaluation would leak the test set into training. Two controls keep the
neural pipeline's numbers honest:

- **The UD-Perseus exclusion manifest.** `greek.agdt_ud_overlap()` resolves every
  UD-Perseus dev+test sentence to its AGDT source and verifies the reference by NFC
  form-sequence comparison: **2,443 sentences across 5 AGDT files, all form-identical**.
  The neural model's training split excludes all of them (cached at
  `ud-grc/agdt-ud-exclusion.json`).
- **PROIEL is held out entirely.** No pyaegean model trains on PROIEL, so it is a genuine
  out-of-domain fold. The combined-corpus model adds the Gorman and Pedalion
  treebanks (both CC BY-SA 4.0); the overlap audit excluded 1,591 Gorman + 155 Pedalion sentences
  matching either evaluation fold, and Gorman's Herodotus files (the same work as PROIEL's
  `hdt.xml`) are excluded at source.

One caveat applies to the **pure-Python baseline** below, not the neural pipeline: its
tagger, edit-tree lemmatizer, arc-eager parser, and treebank lookup are built from the
*full* AGDT, which contains the UD-Perseus test sentences. Their Perseus-fold scores are
therefore an in-training upper bound, reported for orientation; the PROIEL fold is their
honest number.

## The field's published numbers

From Kostkan, Kardos, Mortensen & Nielbo, *“OdyCy: A general-purpose NLP pipeline for
Ancient Greek”*, LaTeCH-CLfL 2023 (<https://aclanthology.org/2023.latechclfl-1.14.pdf>),
Tables 1–2: each pipeline's own tokenization, spaCy evaluation scripts. Best per metric
in **bold**.

**UD Perseus test fold:**

| Pipeline | POS | Morph | Lemma | UAS | LAS |
|---|---|---|---|---|---|
| odyCy (joint) | **95.39** | **92.56** | 83.20 | **78.80** | **73.09** |
| odyCy (perseus) | 95.00 | 91.98 | 82.56 | 76.71 | 70.31 |
| greCy (perseus) | 93.50 | 90.59 | 75.10 | 76.34 | 70.20 |
| Stanza (perseus) | 91.05 | 91.03 | **87.58** | 78.69 | 71.82 |
| UDPipe (perseus) | 80.95 | 85.70 | 82.73 | 63.97 | 55.81 |
| CLTK | 80.50 | 61.49 | 79.46 | 33.05 | 24.25 |

**UD PROIEL test fold:**

| Pipeline | POS | Morph | Lemma | UAS | LAS |
|---|---|---|---|---|---|
| greCy (proiel) | **98.23** | **94.05** | **98.06** | **85.74** | **82.28** |
| odyCy (joint) | 97.81 | 93.46 | 94.41 | 83.17 | 79.03 |
| Stanza (proiel) | 97.39 | 92.20 | 97.21 | 81.51 | 77.48 |
| CLTK | 96.95 | 90.76 | 96.50 | 57.61 | 54.57 |
| UDPipe (proiel) | 95.97 | 88.62 | 93.17 | 72.40 | 67.48 |

(The same paper shows substantial cross-treebank degradation: for example,
Stanza-perseus scores 59.00 UAS on PROIEL, which is why pyaegean keeps
out-of-domain and unseen-form measurement first-class.)

Riemenschneider & Frank's 2023 paper,
*“Exploring Large Language Models for Classical Philology”* (ACL,
<https://aclanthology.org/2023.acl-long.846/>), reports on the UD Perseus test fold
(models trained on the UD train fold, UD 2.10; gold tokenization; the official CoNLL
evaluator; mean of three seeds): GreBERTa **UAS 88.20 / LAS 83.98**, UPOS 95.83,
XPOS 91.09, and a GreTa seq2seq lemmatizer at **91.14** (the published UD-Perseus
lemma comparison used below). Separately, Celano 2025, *“A State-of-the-Art
Morphosyntactic Parser and Lemmatizer for Ancient Greek”* (LM4DH 2025,
<https://arxiv.org/abs/2410.12055>),
fine-tunes Trankit and GreTa on AGDT + Gorman + Pedalion (~1.26 M tokens, normalized to
the AGDT scheme) and reports on his own folds (Trankit UAS 82.28 / LAS 76.67; GreTa
lemma 91.17), reprinting the Riemenschneider & Frank UD rows for loose comparison only
(the schemes differ). That AGDT + Gorman + Pedalion combination is the same
license-clean data lever (Gorman and Pedalion, both CC BY-SA 4.0) the pyaegean joint
model uses.

Two more recent reference points, each reported under its *own* evaluation, so points of
reference rather than rows in the single-protocol table above:

- **Stanza's published model-performance numbers**
  (<https://stanfordnlp.github.io/stanza/performance.html>), under Stanza's own tokenization,
  give **grc_perseus** UPOS 92.41 / UFeats 91.11 / lemma 87.86 / UAS 79.46 / LAS 73.97, and
  **grc_proiel** (in-domain for that model) UPOS 97.42 / lemma 97.18 / LAS 79.02. Its
  self-reported Perseus lemma (87.86) is 0.28 above the 87.58 measured in the table above;
  pyaegean's row is 94.27, an arithmetic difference of +6.4 from Stanza's value.
- **DILEMMA** (<https://github.com/ciscoriordan/dilemma>) is an *architectural* peer: a
  Greek tagger/lemmatizer on the same torch-free ONNX inference path pyaegean uses. But it is
  lemmatizer-first and publishes accuracy only on its own multi-period benchmarks (93.7%
  equiv-adjusted on its DiGreC treebank, 99.7% on Classical Greek), not UD Ancient Greek Perseus
  UAS/LAS, so there is no same-fold parsing number to compare. It is a design peer here, not a
  measured row.

## pyaegean — the neural pipeline (shipped)

The shipped joint model (`grc-joint-v3`, activated by `greek.use_neural_pipeline()`, the
`[neural]` extra) is one GreBerta-encoder checkpoint serving UPOS, XPOS, UD FEATS,
dependency trees (single-root Chu-Liu/Edmonds MST decoding, so non-projectivity is handled
natively), and lemmas. Trained leakage-clean on the audited AGDT + Gorman + Pedalion
corpus (1.41 M tokens). Two changes over the first build lift the parsing scores: the
AGDT→UD converter now attaches non-coordination commas to the following token (the
UD-Perseus convention), and the relation head is trained on the model's *predicted* arcs,
not only gold arcs, so it learns the relation that is actually read at inference. Measured
through the package's own inference code, fetching the release asset (sha256-verified,
onnxruntime CPU):

| Test fold | Lemma | UAS | LAS | UPOS | UFeats | XPOS |
|---|---|---|---|---|---|---|
| UD Perseus | **94.27** | **90.24** | **85.65** | 97.02 | 96.04 | 93.48 |
| UD PROIEL | 90.51 | 82.48 | 63.50 | 86.69 | 59.43 | n/a |

The shipped checkpoint is one of five seed replicates of this recipe; across those seeds the
UD Perseus test mean ± standard deviation is **LAS 85.58 ± 0.10**, UAS 90.15 ± 0.12,
UPOS 97.00 ± 0.06, UFeats 96.06 ± 0.04, lemma 94.30 ± 0.02, XPOS 93.52 ± 0.05 (PROIEL
LAS 63.50 ± 0.04). The table places the shipped checkpoint and its confidence intervals beside
the cited published comparison rows; the margin column is the arithmetic difference:

| Metric | pyaegean | 95% CI | cited comparison | margin |
|---|---|---|---|---|
| UPOS | 97.02 | [96.76, 97.29] | 95.83 (2023) | +1.19 |
| XPOS | 93.48 | [93.09, 93.91] | 91.09 (2023) | +2.39 |
| UFeats | 96.04 | [95.75, 96.34] | 92.56 (odyCy 2023) | +3.48 |
| Lemma | 94.27 | [93.89, 94.62] | 91.14 (GreTa+Chars 2023) | +3.13 |
| UAS | 90.24 | [89.62, 90.80] | 88.20 (2023) | +2.04 |
| LAS | 85.65 | [84.93, 86.29] | 83.98 (2023) | +1.67 |

(CIs are percentile bootstrap over the fold's sentences, 999 resamples: `greek.bootstrap_ud`'s
default, so the reproduction command matches; the 2-decimal bounds are stable across resample counts.)

Three things keep these honest:

- **Confidence intervals and replication.** The +1.67 LAS and +2.04 UAS margins are
  large next to the seed spread (±0.10 / ±0.12), and the within-fold lower bounds
  (84.93 / 89.62) exceed the cited 83.98 / 88.20 rows. The converter comma fix and
  predicted-arc relation training also tightened the seed spread fourfold relative to an
  earlier single-run build.
- **PROIEL is out of domain.** The in-domain published systems train on the PROIEL fold
  itself; pyaegean never does. Against a *Perseus-trained* published system, the like-for-like
  out-of-domain comparison is 82.48 versus the Perseus-trained Stanza baseline's 59.00 on
  this fold, an arithmetic difference of ~23 UAS. The remaining PROIEL
  LAS and UFeats gaps are largely deprel- and feature-convention divergence between the two
  treebanks' UD conversions (PROIEL annotates five feature types the Perseus scheme lacks,
  and PROIEL XPOS is a different tagset entirely).
- **Raw text, end to end.** From each sentence's raw text through pyaegean's own tokenizer
  (tokens F1 99.97) to the evaluator, the scores track the gold-tokenization figures above
  closely, so tokenization is not a bottleneck on this fold. Throughput of the shipped
  quantized model is roughly **20–70 words/s on plain CPU** (sentence-length dependent,
  measured on the development machine); the fp32 `grc-joint-v2` bundle reaches roughly
  300 words/s on the same machine — see the quantization trade-off below. Unlike the
  accuracy figures above (deterministic given the model and gold data, and re-measured by
  `scripts/check_benchmarks.py`), throughput is **hardware-dependent and illustrative, not a
  pinned benchmark**: it scales with the CPU, core count, and workload, so read it as an
  order-of-magnitude guide. It is re-measured only when the model or the `onnxruntime` floor
  changes (a dependency-drift trigger), not automatically per release.

The model ships **quantized at about 173 MB** (tar.gz; 182 MB uncompressed `model.onnx`),
about 3× smaller than the fp32 build (518 MB tar.gz / 556 MB uncompressed). The measured
UD Perseus test scores are unchanged within ±0.02 (UPOS 97.0 / UFeats 96.0 /
lemma 94.3 / UAS 90.2 / LAS 85.6). The trade-off is **CPU throughput**: the int8 MatMulNBits
kernels run several times slower than fp32 MatMul on this workload (roughly 20–70 words/s
quantized vs roughly 300 words/s fp32 on the development machine), so the quantized default
optimizes download size and disk, not speed; throughput-sensitive work can fetch the fp32
`grc-joint-v2` asset instead. The measured file sizes and score comparison are recorded
in `training/results/v3-quantize-report.json` (the rejected full-int8 recipe in
`gate-report.json`). The recipe is **weight-only int8 + fp16, activations kept fp32**:
onnxruntime MatMulNBits (block 128, symmetric) on the MatMul weights, fp16 on everything
else (crucially the 160 MB word-embedding table). Activations stay fp32 by design.

**Full int8 (quantized activations) is excluded because it collapses the GreBerta
encoder.** Its activation outliers do not survive 8-bit quantization: the recorded
dynamic and static recipes dropped UPOS from 97 to 16–32 and LAS from 86 to 1–13,
including a development-set dynamic result of UPOS 98.30 → 23.34. Keeping activations
fp32 and quantizing only the weights avoids the outlier problem and reduces the artifact
size without a measured accuracy loss.

The quantized model requires **onnxruntime ≥ 1.23** (the 8-bit MatMulNBits CPU kernel); the
`[neural]` extra floor was raised from 1.17 to 1.23 accordingly. The fp32 model stays
available at the `grc-joint-v2` release for reproducibility.

### Legacy aggregate calibration (temperature scaling + ECE)

The published schema-1 calibration remains readable through `greek.use_calibration()`
and the compatibility `upos_confidence`/`lemma_confidence` fields. It is a legacy aggregate
for the published `grc-joint-v3` UPOS and composed-lemma proxy, not source-, domain-, or
task-complete evidence. The number is an estimate of prediction correctness produced by
temperature scaling (never raw softmax), with one temperature per head fitted on the UD
Perseus **dev** fold only (the test fold is report-only):

| Head | Temperature | Dev ECE (raw → calibrated) | Test ECE (calibrated) |
|---|---|---|---|
| UPOS | 1.34 | 0.94% → 0.19% | 1.11% (raw was 1.95%) |
| Lemma | 0.66 | 8.77% → 5.39% | 6.29% |

Dev n = 22,135 tokens; test n = 20,959 (report-only, one shot). The lemma figure calibrates
the edit-script head against whether the *composed lemma* matched gold (a documented proxy),
and offline lexicon/rule/seed/paradigm outputs carry no neural confidence. These figures are
literary-prose evidence for this exact artifact; they do not establish equal calibration on
other domains or an OOD detector. Reproduce with `training/calibrate_temperature.py`;
evidence is in `training/results/calibration-2026-07-11.json`.

The additive typed API (`token_confidence`, `sentence_confidence`) adds task/source/domain
scope, explicit unavailable reasons, calibration hashes, and caller-owned
`AbstentionPolicy` decisions. A schema-2 `CalibrationRegistry` and coverage-risk report for
those scopes are still pending a fresh development-only inference gate. No bundled threshold
is implied; until that evidence exists, do not turn a typed unavailable result into zero or
claim out-of-domain calibration.

### Koine / New Testament (Nestle 1904 own gold)

`greek.evaluate_on_nt()` scores the shipped pipeline against the **Nestle 1904** NT's own
gold lemmas and morphology: a complement to the UD-PROIEL row above, which measures the
model against a *different* project's NT annotation. Both are genuinely out of domain: the
model trains on AGDT + Gorman + Pedalion, never on the NT.

| Test set | Lemma | UPOS (reconciled) | scored tokens |
|---|---|---|---|
| Nestle 1904 NT (whole) | 87.96 | 86.75 | 137,303 |

Reproduce: `aegean greek eval nt` (or `greek.use_neural_pipeline(); greek.evaluate_on_nt()`).
Gold-tokenized, all 27 books, ≈1 h on plain CPU. Measured with the shipped quantized
`grc-joint-v3` bundle against the corrected NT gold (suffixed Robinson closed-class tags
reconcile to their real UPOS since 0.15.0; they previously fell to `X`).

History of this row, because each generation was measured: the earlier published 87.04 / 87.57
was recorded (0.8.1) with the **grc-joint-v1** model against the pre-correction gold, and was
not re-measured when v2 replaced v1 (0.8.7). Decomposed per effect on a fixed book (Mark):
the v1 → v2 model change costs about 1.8 UPOS out of domain here (the trade that bought v2's
across-the-board UD Perseus/PROIEL gains); int8 quantization (v3, 0.10.0) costs a further
~0.1, consistent with its Perseus-lossless gate; the gold correction adds ~+0.35; Unicode
normalization of the gold has zero effect. Lemma was stable across those three generations
(87.04 → 87.03); the 0.32.0 lemma-composition fix then raised it to 87.96 (+0.93, about
1,280 tokens): a sentence-initial capitalized form absent from the training lookups
previously surfaced its own capitalized surface as the lemma, and now resolves through the
lowercase lookup (verified prediction-level on Mark: 205 changes, 191 corrected, none newly
wrong; UPOS untouched). See `training/results/lemma-remeasure-2026-07-09.json`.

What is and isn't reported, and why:

- **Lemma** is the clean metric. It sits a few points under the PROIEL-NT lemma (90.51)
  largely because Nestle 1904's lemma conventions differ from the AGDT the model learned
  (principal-part choice, proper-noun citation form, movable-nu): a real convention gap as
  much as model error; scoring only normalizes NFC + homograph digits, not lemma style.
- **UPOS** is compared under the same reconciled tagset as the PROIEL check (PROPN→NOUN,
  SCONJ→CCONJ, AUX→VERB), so it measures real disagreement rather than a Robinson-vs-UD
  convention gap.
- **Not reported:** finer UD features and UAS/LAS. The Robinson morph tagset and pyaegean's
  UD FEATS do not align feature-for-feature, and the Nestle 1904 word list carries no UD
  dependency trees: a UFeats or LAS number here would be a convention artefact, not an
  accuracy (the same reasoning as the PROIEL UFeats note above).

### Genre and register: what the folds support (and what they don't)

A fair question for any Greek parser is "how much can I trust this on Homer, on tragedy, on
Koine prose?" `greek.evaluate_by_genre("perseus", "test")` (CLI: `aegean greek eval ud
--by-genre`) buckets a UD fold by its `sent_id` author, maps each author to a literary genre
(epic, tragedy, comedy, prose), and scores each bucket separately with the official evaluator,
reporting the per-bucket sentence and word counts and, optionally, bootstrap CIs.

Running the discovery step on the leakage-clean folds gives an important, and limiting, result:

| Fold | Genre composition | Authors |
|---|---|---|
| UD Perseus **test** | 100% prose | Athenaeus (`tlg0008`) |
| UD Perseus **dev** | 100% prose | Thucydides, Plutarch, Athenaeus |
| UD Perseus **train** | epic, tragedy, prose | Homer, Sophocles, Hesiod, Aeschylus, Herodotus, and others |

The epic and tragic material lives in the *training* fold; the held-out test and dev folds are
entirely prose (the test fold is a single imperial-prose author, Athenaeus). So the shipped
Perseus test numbers, and every published Perseus number in this document, describe accuracy on
literary prose. A genre-conditioned test accuracy for epic or tragedy is **not** something the
current leakage-clean data can report: measuring it honestly would require a held-out
epic/tragedy slice that the model has not trained on, which is future annotation work, not a
number we can pin today. `evaluate_by_genre` is shipped so that this can be checked and, once
such a slice exists, reported; run against the Perseus test fold today it returns a single
`prose` bucket equal to the overall Perseus score.

On register (Classical literary vs Koine), the closest available signal is the contrast between
the Perseus rows (literary, and as shown here prose) and the Nestle 1904 NT row (Koine): lemma
94.27 on Perseus against 87.96 on the NT. That gap is real but is **not** a clean register
effect, because register co-varies with the annotation project: the NT row is a different
treebank's conventions and a genuinely out-of-domain fold, so the difference mixes register,
convention, and domain. It is reported as orientation, not as a measured "Koine penalty."

### Documentary Koine: the PapyGreek fold

Documentary Greek (letters, petitions, receipts on papyrus) had no parsing
evaluation here until this fold: **1,551 sentences / 22,227 tokens** converted from
the PapyGreek Treebanks (CC BY-SA 4.0) to UD CoNLL-U through the same AGDT
conversion the model trains under, so the numbers measure domain transfer rather
than annotation-convention divergence.

**Scoring is on PapyGreek's regularized layer.** Each token has two readings, the
diplomatic `orig` and the editorially regularized `reg`; this fold uses `reg`, the
reading whose spelling the editors normalized toward standard Koine (and whose
Leiden/EpiDoc apparatus is stripped to the reading text). The scores are therefore a
regularized-text figure. They do not measure the model on the raw documentary
orthography (phonetic spellings, itacism, non-standard case and agreement) that the
`orig` layer preserves and that is meaningfully harder. That harder input now has its
own fold: the diplomatic `orig` surface layer (`papygreek-fold-orig` — the same 1,551
sentences and the same gold, with the raw diplomatic form as the token), scored by
`greek.evaluate_on_papygreek(layer="orig")` (CLI `aegean greek eval papygreek --layer
orig`). Its row appears below.

**Exclusion accounting.** The fold keeps 1,551 of the 4,557 annotated sentences in
the source; the full accounting is in `training/results/papygreek-fold-manifest.json`.
The exclusions, largest first: 1,793 sentences carry an artificial node (an elliptic
or inserted token with no surface form), which gold-tokenization scoring cannot
include without empty-node handling that would inject conversion artifacts; 678 are
not fully annotated (a real token missing its `reg` form, head, relation, postag, or
lemma, including trees whose syntax was never completed); 354 are leakage overlaps
with the training set at the sentence-form level; 145 more belong to a PapyGreek
Trismegistos work identity present in the Pedalion training source; and 36 do not
reduce to a clean reading after apparatus stripping (an illegibility marker or a
fully-erased word). Dropping the
elliptic sentences biases the fold toward syntactically complete material, so the
measured accuracy sits above what a corpus that retained ellipsis would give.

The current fold applies two independent guards. It excludes a whole PapyGreek
document whenever its source-native Trismegistos work identity occurs in Pedalion's
documentary training source, then applies the sentence-level NFC form-tuple check
(full and punctuation-stripped) against all three training sources. The prior fold's
sentence-only check missed 145 sentences from 29 training-overlapping works; that
24,105-token measurement remains historical but is no longer the current
generalization claim.

| Test set | UPOS | XPOS | UFeats | Lemma | UAS | LAS | CLAS | scored tokens |
|---|---|---|---|---|---|---|---|---|
| PapyGreek (documentary Koine) | 91.53 | 77.19 | 88.73 | 86.10 | 85.50 | 79.56 | 75.40 | 22,227 |

Reproduce: `aegean greek eval papygreek` (or `greek.evaluate_on_papygreek()`).
Scheme-matched out-of-domain parsing differs from the convention-capped PROIEL row
by about +16 LAS points, the quantitative confirmation of the decomposition
below. The published protocol is CPU-sequential (`batch_size=None`) and uses
complete-word overlapping windows for sentences beyond the model's single-pass
subword budget. Partial placeholder tails are never scored. The historical decoder
did silently emit placeholders for one retained over-limit regularized sentence;
that coverage defect is another reason the old row is historical rather than
directly comparable.

### Verse, out of domain: a leakage-clean tragedy evaluation

No manually-annotated Greek verse treebank outside the model's own training data
was previously known to us: the canonical epic and tragedy treebanks are all in
the AGDT+Gorman+Pedalion training set (the leakage-clean UD-Perseus test fold is
100% prose). The verse fold fills that gap with gold from the UNESP Trees
project (Perseids/Arethusa manual annotation, CC BY-SA 4.0): **tragedy only** —
Euripides, *Bacchae* 1-169, 36 sentences / 735 tokens after the standard
selection policy. The fold is leakage-checked sentence-by-sentence in its build
(0 overlaps; the only Euripides in training is *Medea*). Gold diligence: an
eight-sentence scholarly spot-check preceded the first pin, and a subsequent
specialist review pass corrected the fold build (v2) — a 25-token sliver first
labeled hexameter was identified as the Maximus *prose paraphrase* and removed,
15 leaf-apposition relations were corrected from the converter's `cc` to
`appos`, and 11 malformed gold lemmas (Latin homoglyph vowels, LSJ citation-form
tails) were repaired.

**This is a small-sample datapoint with wide confidence intervals, never a
headline number.**

| Track | UPOS | UFeats | Lemma | UAS | LAS | tokens |
|---|---|---|---|---|---|---|
| Tragedy (Bacchae) | 90.88 | 92.79 | 87.89 | 79.73 | 73.33 | 735 |

Tragedy 95% CIs (percentile bootstrap, 999): UPOS [88.40, 92.96], lemma
[85.44, 90.10], UAS [75.84, 84.68], LAS [69.75, 78.28]. The substantive finding:
tragedy LAS (~73) runs well below the documentary fold (~80) — poetic word order
and hyperbaton are materially harder to parse than either prose register, which
is precisely what this fold exists to measure. Reproduce:
`aegean greek eval verse --track tragedy` (evidence:
`training/results/verse-eval-v2-2026-07-11.json`).

### The diplomatic-orthography row, and Byzantine verse

The orig-layer fold (`evaluate_on_papygreek(layer="orig")`) scores the same
1,551 sentences and gold as the row above, with the FORM column carrying the
scribes' actual readings (1,453 tokens differ — mostly orthographic: itacism,
vowel-quantity confusion, nasal assimilation, voicing, gemination; a minority
are the editors' morphosyntactic regularizations, e.g. non-standard case,
number, or εἰς/ἐν substitution, so the pair measures the cost of raw documentary
usage, not spelling alone). Measured once, CPU sequential:

| Fold | UPOS | XPOS | UFeats | Lemma | UAS | LAS | CLAS |
|---|---|---|---|---|---|---|---|
| PapyGreek, regularized (above) | 91.53 | 77.19 | 88.73 | 86.10 | 85.50 | 79.56 | 75.40 |
| PapyGreek, diplomatic (orig) | 90.57 | 74.64 | 86.15 | 82.05 | 84.32 | 77.55 | 72.94 |

The pair isolates the cost of the scribes' non-standard documentary usage:
lemma takes the largest hit (−4.05 points — phonetic spellings break lemma
composition), morphology loses ~2.58, attachment the least. Only 6.5% of tokens
differ in surface form, so the per-changed-token degradation is steep.
(Evidence: `training/results/papygreek-orig-eval-v3-2026-07-15.json`.)

**Byzantine verse (tagging only).** `greek.evaluate_on_dbbe()` scores the
pipeline against the DBBE gold standard (Swaelens, De Vos & Lefever, LRE 2025;
CC BY 4.0): 825 sentences / 9,191 tokens of unedited medieval book epigrams,
7th–15th c., non-normalized scribal orthography. The gold carries POS and lemma
but no trees, so this is a tagging row; the DBBE tagset is mapped to UPOS and
gold lemmas are normalized Attic headwords, both stated caveats. Measured once,
CPU sequential: **UPOS 86.74 / XPOS 76.40 / UFeats 85.86 / lemma 76.71** —
leakage-checked (0 overlaps). (Evidence:
`training/results/dbbe-eval-v2-2026-07-11.json`.)

### PapyGreek convention decomposition

The PapyGreek row's two weakest cells are largely convention, not model quality,
and `greek.papygreek_convention_report()` (CLI: `aegean greek eval papygreek
--drift`) measures it the same way the PROIEL decomposition does: it reproduces
UPOS/XPOS from the model's own outputs (equal to the official evaluator exactly)
and partitions each gap. Measurement only; the published row is unchanged.
(22,227 words, neural pipeline, full-coverage CPU sequential; evidence:
`training/results/papygreek-convention-decomp-v2-2026-07-15.json`.)

**UPOS.** Of the 8.47-point gap, 4.98 points (58.79% of all UPOS errors) sit on one
closed class: the coordinators (gold `CCONJ` — καί, δέ, τε …). The merged training
treebanks tag these words under three incompatible conventions (the AGDT
conjunction code, an adverb reading, and a non-AGDT code that maps to `X`), so the
model's label for them is unstable and drifts in the documentary register.

**XPOS.** Of the 22.81-point gap, 13.31 points are convention or encoding: the
same coordinator pos-code (5.01), the model's common-gender `c` where the fold's
gold commits to a specific gender (5.69), and gold tags carrying a literal `_`
slot where the model writes `-` (2.61). Forgiving those three, XPOS would read
90.50%; the residual 9.50 points are genuine morphology error, dominated by real
gender confusion. The 9-position tag is convention-capped on this fold, not
broken.

**A recorded conversion correction (0.44.0).** The AGDT→UD converter that builds
both the training labels and the AGDT-derived evaluation folds mapped a *leaf*
`APOS` relation (an appositive attached directly under its antecedent) to `cc` —
a label UD reserves for coordinating-conjunction words. The converter now emits
`appos`, and the folds were rebuilt and re-measured (73 gold cells in the
PapyGreek fold, 15 in the verse fold; DEPREL only, every other cell
byte-identical). The shipped `grc-joint` model was **trained under the old
convention**, so it systematically predicts `cc` for bare appositives; against
the corrected gold that surfaces as a genuine, measured `appos`/`cc` confusion
in the LAS rows rather than being hidden inside matching-but-wrong labels. A
future retraining absorbs the correction into the model itself.

### Opt-in documentary levers

Two optional post-processing layers reconcile the shipped neural pipeline's output
to the documentary register named in the decomposition above, without touching the
model, the default pipeline, or any published number. Both are **opt-in and off by
default**, and the pipeline is **byte-identical to the shipped model until a lever is
switched on** (a fresh session, or `disable_*`, restores exactly the model's own
output). Each is a composition layer, exactly like `use_paradigms`, so it earns its
**own** opt-in registry variant row rather than moving the published PapyGreek row,
which is **unchanged**. Both post-process the active neural pipeline, so it must be
active first (`greek.use_neural_pipeline()`).

**Lever A — coordinator reconciliation** (`greek.use_documentary_reconciliation()`).
The conservative default relabels only the closed coordinator set (καί, δέ, τε, ἀλλά,
ἤ, οὐδέ, οὔτε, μηδέ, μήτε) and only when the model emits the always-wrong `X` / `b`
reading — never a legitimate tag for a coordinator — so it cannot mislabel a correct
token. The current corrected test-fold measurement changes exactly 775 UPOS and 783
XPOS cells, improving UPOS by 3.13 points and XPOS by 3.18 while every other field is
byte-identical. Earlier development-selection deltas predated the work-level leakage
correction and remain historical design records, not current leakage-clean claims. The
aggressive `ADV` / `d` variant remains recommended against.

**Lever B — lemma OOV rescue** (`greek.use_documentary_lemma_rescue()`). When the model
leaves a lemma unresolved (the honest identity fall-through), the guarded offline cascade
is consulted — the bundled seed table and, when `use_paradigms()` is active, the UniMorph
paradigm table: **seed and guarded-paradigm tiers only**. The generalizing
ending-stripping rules are **deliberately excluded**: on the OOV residue the model already
left unresolved they fabricate about as often as they fix (measured **break-even on the
documentary dev fold, net-negative on the literary dev fold**), so the rescue keeps only
the curated, correctly-accented tiers. A rescue only replaces an unresolved lemma, never
overrides a resolved neural lemma, and carries its own evidence class (`SEED` / `PARADIGM`,
never `NEURAL`). On the corrected fold it makes no additional prediction beyond Lever A,
so the current evidence claims no lemma gain.

Each lever is measured **once, sequentially**, on the pinned PapyGreek fold (batched
inference is not prediction-identical on this fold, so these rows share the fold's
CPU-sequential protocol) and pinned as its own registry variant row; the published
PapyGreek row above is untouched. (Neural pipeline, full-coverage CPU sequential;
evidence: `training/results/documentary-levers-v3-2026-07-15.json`.)

| Variant on the PapyGreek fold | UPOS / XPOS / UFeats / Lemma / UAS / LAS / CLAS |
| --- | --- |
| + Lever A (coordinator reconciliation, conservative) | 94.66 / 80.36 / 88.73 / 86.10 / 85.50 / 79.56 / 75.40 |
| + Lever A + Lever B (lemma OOV rescue, with `use_paradigms`) | 94.66 / 80.36 / 88.73 / 86.10 / 85.50 / 79.56 / 75.40 |

### PROIEL convention decomposition

The out-of-domain UD-PROIEL row above (UFeats 59.43, UAS 82.48, LAS 63.50) is held
down less by model error than by annotation-convention divergence.
`greek.proiel_convention_report()` (CLI: `aegean greek eval ud --fold proiel --drift`)
measures that divergence directly, reproducing UFeats/UAS/LAS from the model's own
outputs (equal to the official evaluator to four decimals) and partitioning each gap.
This is a measurement decomposition only: it changes none of the published numbers,
it accounts for them. (13,314 words, neural pipeline; evidence:
`training/results/proiel-convention-decomp-2026-07-11.json`.)

**UFeats.** Of the 40.6-point gap, 24.2 points are *scheme-absent* features — UD
feature types the AGDT scheme cannot emit at all (PROIEL uses exactly five the
Perseus scheme lacks: `PronType`, `Definite`, `Polarity`, `Reflex`, `Poss`; 3,224
words carry at least one) — and 16.4 points are disagreement inside the shared
scheme. On the 10,090 words whose gold features are all scheme-shared, the model
scores UFeats **78.4**. Within the shared types, the well-shared morphology agrees
closely (Number 99.6%, VerbForm 99.7%, Case 99.0%, Mood 99.0%, Tense 98.3%, Voice
94.2%, Gender 91.9%), while three shared types diverge by convention rather than
competence: `Aspect` (29.2%: PROIEL marks aspect on the aorist where the Perseus
scheme does not), `Degree` (6.5%: PROIEL marks `Degree=Pos` on the plain positive),
and `Person` (77.9%). The 16.4 shared points are therefore an upper bound on genuine
morphological error.

**LAS.** Of the 36.5-point LAS gap (100 − LAS), 17.5 points are attachment errors
(100 − UAS) and 19.0 points (2,526 tokens, the UAS-to-LAS gap) are attachment-correct
but label-wrong. That relabelling
mass is systematic, not scattered — the top five gold-to-predicted confusions carry
68.9% of it, and each is a known convention pair between the two UD conversions:
`discourse → advmod` (24.1%: PROIEL tags the sentential particles μέν, δέ, γάρ, οὖν
`discourse`, a relation the AGDT scheme lacks), `det → nmod` (17.6%), `obl → obj`
(11.0%) with `obl → iobj` (3.2%), `amod → nmod` (8.2%), and `cc → advmod` (8.1%).
None of these is a wrong tree; each is a correctly-attached relation named by the
model's own convention.

## pyaegean — the pure-Python baseline

The zero-dependency stack (`use_treebank() + use_tagger() + use_lemmatizer() +
use_parser()`) is the offline, no-heavy-deps path. It is a baseline, and reads like one:

| Fold | UPOS | Lemma | UAS |
|---|---|---|---|
| Perseus test ⚠ | 86.73 | 97.65 ⚠ | 37.43 |
| PROIEL test | 78.83 | 85.63 (90.38 with the neural lemmatizer) | 35.41 |

⚠ = in-training upper bound (see Leakage controls); the 97.65 Perseus lemma is the lookup
memorizing the fold. LAS is not comparable here: the arc-eager parser emits Prague labels,
not UD relations. The baseline exists for the zero-install path; the neural pipeline carries
the accuracy claims.

(Perseus: 1,306 sentences / 20,959 words; PROIEL: 1,047 / 13,314.)
