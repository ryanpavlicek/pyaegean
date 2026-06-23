# Greek NLP benchmarks — protocol and numbers

How pyaegean is scored on the standard Ancient Greek benchmarks: the protocol, the
leakage controls that keep the comparison honest, the field's published numbers, and
pyaegean's own measured results. The README and wiki carry only pyaegean's own numbers;
the cross-tool tables live here, with citations.

## Protocol

- **Test sets:** the Universal Dependencies Ancient Greek test folds:
  `UD_Ancient_Greek-Perseus` (commit `331ddef`) and `UD_Ancient_Greek-PROIEL` (commit
  `a4ab8d4`), both CC BY-NC-SA 3.0, fetched to the cache for **evaluation only** (never
  bundled, never trained on).
- **Scorer:** the official CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`,
  MPL 2.0), fetched sha256-pinned
  (`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`) and imported from
  the cache. Reported figures are the evaluator's F1 per metric.
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
  early stopping, checkpoint selection, light schedule tuning (epochs / lr), and the int8
  quantization gate; the **test** folds are scored once on the finished model and never used
  for any selection. Full protocol in `training/README.md`.
- **Lemma scoring.** Lemmas use the evaluator's exact string match, NFC-normalized with
  homograph-index digits stripped, and **no** case- or diacritic-folding. Convention
  differences (principal-part choice, movable-nu, proper-noun citation form) therefore count
  as errors rather than being normalized away.
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

## pyaegean — the neural pipeline (shipped)

The shipped joint model (`grc-joint-v2`, activated by `greek.use_neural_pipeline()`, the
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
| UD Perseus | **94.29** | **90.23** | **85.64** | 97.04 | 96.04 | 93.48 |
| UD PROIEL | 90.50 | 82.47 | 63.47 | 86.71 | 59.43 | n/a |

The shipped checkpoint is one of five seed replicates of this recipe; across those seeds the
UD Perseus test mean ± standard deviation is **LAS 85.58 ± 0.10**, UAS 90.15 ± 0.12,
UPOS 97.00 ± 0.06, UFeats 96.06 ± 0.04, lemma 94.30 ± 0.02, XPOS 93.52 ± 0.05 (PROIEL
LAS 63.50 ± 0.04), so the headline figures are representative, not a lucky seed. On UD
Perseus test every metric is above the best published number we could find, and each lead
clears both that seed spread and a within-fold bootstrap confidence interval:

| Metric | pyaegean | 95% CI | best published | margin |
|---|---|---|---|---|
| UPOS | 97.04 | [96.77, 97.32] | 95.83 (2024) | +1.21 |
| XPOS | 93.48 | [93.09, 93.90] | 91.09 (2024) | +2.39 |
| UFeats | 96.04 | [95.74, 96.34] | 92.56 (odyCy 2023) | +3.48 |
| Lemma | 94.29 | [93.91, 94.63] | 87.58 (Stanza, same fold) | +6.71 |
| UAS | 90.23 | [89.56, 90.80] | 88.20 (2024) | +2.03 |
| LAS | 85.64 | [84.91, 86.29] | 83.98 (2024) | +1.66 |

(CIs are percentile bootstrap over the fold's sentences, 500 resamples, via `greek.bootstrap_ud`.)

Three things keep these honest:

- **The leads are robust, LAS and UAS included.** The +1.66 LAS and +2.03 UAS margins are
  large next to both the seed spread (±0.10 / ±0.12) and the within-fold CIs above, whose lower
  bounds (84.91 / 89.56) sit well above the published 83.98 / 88.20. An earlier single-run build
  had a thin, within-noise LAS lead; the converter comma fix and the predicted-arc relation
  training above turned it into a robust one (and tightened the seed spread fourfold).
- **PROIEL is out of domain.** The in-domain published systems train on the PROIEL fold
  itself; pyaegean never does. Against the *Perseus-trained* published systems: the
  like-for-like out-of-domain comparison: pyaegean leads by ~17 UAS. The remaining PROIEL
  LAS and UFeats gaps are largely deprel- and feature-convention divergence between the two
  treebanks' UD conversions (PROIEL annotates five feature types the Perseus scheme lacks,
  and PROIEL XPOS is a different tagset entirely).
- **Raw text, end to end.** From each sentence's raw text through pyaegean's own tokenizer
  (tokens F1 99.97) to the evaluator, the scores track the gold-tokenization figures above
  closely, so tokenization is not a bottleneck on this fold. Throughput is ≈450 words/s on
  plain CPU.

The model ships fp32 (~518 MB): int8 dynamic quantization broke it on the dev set
(UPOS 98.30 → 23.34), so the quantization gate rejected it. Selective quantization is a
known follow-up; correctness ships first.

### Koine / New Testament (Nestle 1904 own gold)

`greek.evaluate_on_nt()` scores the shipped pipeline against the **Nestle 1904** NT's own
gold lemmas and morphology: a complement to the UD-PROIEL row above, which measures the
model against a *different* project's NT annotation. Both are genuinely out of domain: the
model trains on AGDT + Gorman + Pedalion, never on the NT.

| Test set | Lemma | UPOS (reconciled) | scored tokens |
|---|---|---|---|
| Nestle 1904 NT (whole) | 87.04 | 87.57 | 137,303 |

Reproduce: `aegean greek eval nt` (or `greek.use_neural_pipeline(); greek.evaluate_on_nt()`).
Gold-tokenized, all 27 books, ≈10 min on plain CPU.

What is and isn't reported, and why:

- **Lemma** is the clean metric. It sits a few points under the PROIEL-NT lemma (90.6)
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

## pyaegean — the pure-Python baseline

The zero-dependency stack (`use_treebank() + use_tagger() + use_lemmatizer() +
use_parser()`) is the offline, no-heavy-deps path. It is a baseline, and reads like one:

| Fold | UPOS | Lemma | UAS |
|---|---|---|---|
| Perseus test ⚠ | 87.05 | 97.65 ⚠ | 37.89 |
| PROIEL test | 75.03 | 85.26 (90.38 with the neural lemmatizer) | 33.51 |

⚠ = in-training upper bound (see Leakage controls); the 97.65 Perseus lemma is the lookup
memorizing the fold. LAS is not comparable here: the arc-eager parser emits Prague labels,
not UD relations. The baseline exists for the zero-install path; the neural pipeline carries
the accuracy claims.

(Perseus: 1,306 sentences / 20,959 words; PROIEL: 1,047 / 13,314.)
