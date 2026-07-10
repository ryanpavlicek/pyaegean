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
- **Train / dev / test discipline.** Training is the AGDT minus the UD-Perseus dev+test
  exclusion manifest. The **dev** fold (the AGDT sentences behind UD-Perseus dev) is used for
  early stopping, checkpoint selection, light schedule tuning (epochs / lr), and the
  quantization gate (weight-only int8 + fp16 passes losslessly; full int8 activations are
  rejected there, see below); the **test** folds are scored once on the finished model and never used
  for any selection. Full protocol in `training/README.md`.
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

(The same paper shows every single-treebank model collapsing on the *other* treebank:
e.g. Stanza-perseus scores 59.00 UAS on PROIEL, which is why pyaegean keeps out-of-domain
and unseen-form measurement first-class.)

A newer baseline raises the parsing bar above that table: Riemenschneider & Frank 2024,
*“A State-of-the-Art Morphosyntactic Parser and Lemmatizer for Ancient Greek”*
(<https://arxiv.org/abs/2410.12055>: the GreBERTa/GreTa authors), reports on the UD
Perseus test fold (models trained on the UD train fold; gold tokenization): GreBERTa-based
parsing **UAS 88.20 / LAS 83.98**, POS 95.83, XPOS 91.09; and a GreTa lemmatizer at 91.17
lemma accuracy on their own (AGDT + Gorman + Pedalion, normalized) folds. Their main
models train on AGDT + Gorman + Pedalion (~1.26 M tokens): the same license-clean data
lever (Gorman and Pedalion, both CC BY-SA 4.0) the pyaegean joint model uses.

Two more recent reference points, each reported under its *own* evaluation, so points of
reference rather than rows in the single-protocol table above:

- **Stanza's published model-performance numbers**
  (<https://stanfordnlp.github.io/stanza/performance.html>), under Stanza's own tokenization,
  give **grc_perseus** UPOS 92.41 / UFeats 91.11 / lemma 87.86 / UAS 79.46 / LAS 73.97, and
  **grc_proiel** (in-domain for that model) UPOS 97.42 / lemma 97.18 / LAS 79.02. Its
  self-reported Perseus lemma (87.86) edges the 87.58 measured in the table above; pyaegean's
  94.27 still leads it by +6.4.
- **DILEMMA** (<https://github.com/ciscoriordan/dilemma>) is the closest *architectural* peer: a
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
LAS 63.50 ± 0.04), so the headline figures are representative, not a lucky seed. On UD
Perseus test every metric is above the best published number we could find, and each lead
clears both that seed spread and a within-fold bootstrap confidence interval:

| Metric | pyaegean | 95% CI | best published | margin |
|---|---|---|---|---|
| UPOS | 97.02 | [96.76, 97.29] | 95.83 (2024) | +1.19 |
| XPOS | 93.48 | [93.09, 93.91] | 91.09 (2024) | +2.39 |
| UFeats | 96.04 | [95.75, 96.34] | 92.56 (odyCy 2023) | +3.48 |
| Lemma | 94.27 | [93.89, 94.62] | 87.86 (Stanza model card) | +6.41 |
| UAS | 90.24 | [89.62, 90.80] | 88.20 (2024) | +2.04 |
| LAS | 85.65 | [84.93, 86.29] | 83.98 (2024) | +1.67 |

(CIs are percentile bootstrap over the fold's sentences, 999 resamples: `greek.bootstrap_ud`'s
default, so the reproduction command matches; the 2-decimal bounds are stable across resample counts.)

Three things keep these honest:

- **The leads are robust, LAS and UAS included.** The +1.67 LAS and +2.04 UAS margins are
  large next to both the seed spread (±0.10 / ±0.12) and the within-fold CIs above, whose lower
  bounds (84.93 / 89.62) sit well above the published 83.98 / 88.20. An earlier single-run build
  had a thin, within-noise LAS lead; the converter comma fix and the predicted-arc relation
  training above turned it into a robust one (and tightened the seed spread fourfold).
- **PROIEL is out of domain.** The in-domain published systems train on the PROIEL fold
  itself; pyaegean never does. Against a *Perseus-trained* published system, the like-for-like
  out-of-domain comparison, pyaegean leads by ~23 UAS (82.48 vs the Perseus-trained Stanza
  baseline's 59.00 on this fold). The remaining PROIEL
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
about 3× smaller than the fp32 build (518 MB tar.gz / 556 MB uncompressed) and lossless on
**accuracy**: UD Perseus test scores are unchanged within ±0.02 (UPOS 97.0 / UFeats 96.0 /
lemma 94.3 / UAS 90.2 / LAS 85.6). The trade-off is **CPU throughput**: the int8 MatMulNBits
kernels run several times slower than fp32 MatMul on this workload (roughly 20–70 words/s
quantized vs roughly 300 words/s fp32 on the development machine), so the quantized default
optimizes download size and disk, not speed — throughput-sensitive work can fetch the fp32
`grc-joint-v2` asset instead. The measured file sizes and the lossless comparison are recorded
in `training/results/v3-quantize-report.json` (the rejected full-int8 recipe in
`gate-report.json`). The recipe is **weight-only int8 + fp16, activations kept fp32**:
onnxruntime MatMulNBits (block 128, symmetric) on the MatMul weights, fp16 on everything
else (crucially the 160 MB word-embedding table). Activations stay fp32 by design.

This is the recipe that works because the obvious one does not: **full int8 (quantized
activations) collapses the GreBerta encoder.** Its activation outliers do not survive
8-bit quantization, so every dynamic or static int8-activation recipe we tried dropped
UPOS from 97 to 16–32 and LAS from 86 to 1–13 (an earlier dynamic-quantization attempt
broke it on the dev set, UPOS 98.30 → 23.34). Keeping activations fp32 and quantizing only
the weights avoids the outlier problem and ships the size win at no accuracy cost.

The quantized model requires **onnxruntime ≥ 1.23** (the 8-bit MatMulNBits CPU kernel); the
`[neural]` extra floor was raised from 1.17 to 1.23 accordingly. The fp32 model stays
available at the `grc-joint-v2` release for reproducibility.

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
