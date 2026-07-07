# Benchmarks

This page collects pyaegean's own measured Greek NLP results, the evaluation
protocol that produces them, and the field's published numbers side by side, with
citations. The headline: the opt-in **[neural pipeline](Greek-NLP#the-neural-pipeline-opt-in)**
(`greek.use_neural_pipeline()`, the `[neural]` extra) is **state of the art on the
UD Ancient Greek (Perseus) benchmark**, measured end-to-end through the shipped
package with the official CoNLL 2018 evaluator.

Every number here comes from the recorded protocol and matches the canonical
source in the repository,
`docs/benchmarks.md` (in the repository),
which is registry-pinned: each published figure lives in
`training/results/published-claims.json`, a per-commit test asserts the docs carry
exactly those values, and the offline-stack rows are re-measured against the
registry. See [Reproduce the numbers](#reproduce-the-numbers) below to run any of
them yourself, and [Where this lives](#where-this-lives-canonical-source) for how a
number is allowed to change.

## What the metrics mean

All are percentages against the human-annotated gold: higher is better.

- **UPOS**: Universal Part Of Speech, the basic word class (noun, verb, adjective,
  preposition, ...) from UD's 17-tag set.
- **XPOS**: the language-specific part-of-speech tag, the treebank's own finer-grained
  tagset. Not comparable across treebanks with different tagsets, so it is sometimes
  marked n/a.
- **UFeats**: Universal Features, the full morphology (case, number, gender, tense,
  mood, voice, person). A word counts only if *every* feature is right, so this is the
  strictest word-level tag.
- **Lemma**: the dictionary/citation form (`λέγει` → `λέγω`, `ἀνθρώπους` → `ἄνθρωπος`).
- **UAS**: Unlabeled Attachment Score, the fraction of words hooked to the correct
  syntactic parent.
- **LAS**: Labeled Attachment Score, UAS where the link must *also* carry the right
  relation label. The usual headline number for parsing quality.

## The neural pipeline (shipped)

The shipped joint model (`grc-joint-v3`) is one GreBerta-encoder checkpoint serving
UPOS, XPOS, UD FEATS, dependency trees (single-root Chu-Liu/Edmonds MST decoding, so
non-projectivity is handled natively), and lemmas from a single forward pass. It is
trained leakage-clean on the audited AGDT + Gorman + Pedalion corpus (1.41 M tokens).
Measured through the package's own inference code, gold-tokenized, official CoNLL
2018 evaluator:

| Test fold | Lemma | UAS | LAS | UPOS | UFeats | XPOS |
| --- | --- | --- | --- | --- | --- | --- |
| UD Perseus | **94.29** | **90.23** | **85.64** | 97.04 | 96.04 | 93.48 |
| UD PROIEL | 90.50 | 82.47 | 63.47 | 86.71 | 59.43 | n/a |

UD PROIEL is a genuine **out-of-domain** fold: no pyaegean model ever trains on it
(see [Leakage controls](#leakage-controls)). Its lower LAS and UFeats are largely
deprel- and feature-convention divergence between the two treebanks' UD conversions
(PROIEL annotates five feature types the Perseus scheme lacks, and PROIEL XPOS is a
different tagset entirely), not raw error.

**Not a lucky seed.** The shipped checkpoint is one of five seed replicates of this
recipe. Across those seeds the UD Perseus test mean plus or minus standard deviation
is **LAS 85.58 ± 0.10**, UAS 90.15 ± 0.12, UPOS 97.00 ± 0.06, UFeats 96.06 ± 0.04,
lemma 94.30 ± 0.02, XPOS 93.52 ± 0.05 (PROIEL LAS 63.50 ± 0.04), so the headline
figures are representative.

On UD Perseus test every metric is above the best published number we could find,
and each lead clears both that seed spread and a within-fold bootstrap confidence
interval:

| Metric | pyaegean | 95% CI | best published | margin |
| --- | --- | --- | --- | --- |
| UPOS | 97.04 | [96.77, 97.32] | 95.83 (2024) | +1.21 |
| XPOS | 93.48 | [93.09, 93.90] | 91.09 (2024) | +2.39 |
| UFeats | 96.04 | [95.74, 96.34] | 92.56 (odyCy 2023) | +3.48 |
| Lemma | 94.29 | [93.91, 94.63] | 87.86 (Stanza model card) | +6.43 |
| UAS | 90.23 | [89.56, 90.80] | 88.20 (2024) | +2.03 |
| LAS | 85.64 | [84.91, 86.29] | 83.98 (2024) | +1.66 |

CIs are percentile bootstrap over the fold's sentences, 999 resamples
(`greek.bootstrap_ud`'s default, so the reproduction command matches). The lower
bounds (LAS 84.91, UAS 89.56) sit well above the published 83.98 / 88.20, so the
parsing leads are robust, not within noise. The cross-tool sources for the "best
published" column are cited in [Cross-tool comparison](#cross-tool-comparison-with-citations).

## Out of domain: Koine / New Testament

`greek.evaluate_on_nt()` scores the same shipped pipeline against the **Nestle 1904**
New Testament's own gold lemmas and morphology. This is genuinely out of domain: the
model trains on AGDT + Gorman + Pedalion, never on the NT. It complements the UD
PROIEL row (a different project's NT annotation).

| Test set | Lemma | UPOS (reconciled) | scored tokens |
| --- | --- | --- | --- |
| Nestle 1904 NT (whole) | 87.03 | 86.75 | 137,303 |

Lemma is the clean metric; it sits a few points under the PROIEL-NT lemma (90.50)
largely because Nestle 1904's lemma conventions differ from the AGDT the model
learned (principal-part choice, proper-noun citation form, movable-nu). UPOS is
compared under a reconciled tagset (PROPN→NOUN, SCONJ→CCONJ, AUX→VERB), so it
measures real disagreement rather than a Robinson-vs-UD convention gap. Finer UD
features and UAS/LAS are not reported here: the Robinson morph tagset does not align
feature-for-feature with UD FEATS, and the Nestle 1904 word list carries no
dependency trees, so those numbers would be convention artefacts rather than
accuracy.

## Pure-Python offline baseline

The zero-dependency stack (`use_treebank() + use_tagger() + use_lemmatizer() +
use_parser()`) is the offline, no-heavy-deps path. It is a baseline, and reads like
one:

| Fold | UPOS | Lemma | UAS |
| --- | --- | --- | --- |
| Perseus test ⚠ | 86.73 | 97.65 ⚠ | 37.43 |
| PROIEL test | 78.83 | 85.63 (90.38 with the neural lemmatizer) | 35.41 |

The ⚠ cells are an **in-training upper bound**: the baseline's tagger, edit-tree
lemmatizer, arc-eager parser, and treebank lookup are built from the *full* AGDT,
which contains the UD-Perseus test sentences, so the 97.65 Perseus lemma is the
lookup memorizing the fold. The PROIEL fold is their honest number. LAS is not
comparable here (the arc-eager parser emits Prague labels, not UD relations). The
baseline exists for the zero-install path; the neural pipeline carries the accuracy
claims. (Perseus: 1,306 sentences / 20,959 words; PROIEL: 1,047 / 13,314.)

On the **full New Testament**, the fully offline lemmatizer (no backends active,
`greek.lemmatize` per token) scores **66.16%** over 137,303 tokens. This is the
"~66% on the full NT" figure quoted on [Limitations](Limitations); it is re-measured
by the offline-stack guard because it moves with the code.

## Held-out generalization (pure-Python backends)

The opt-in pure-Python tagger and lemmatizer are measured on a leakage-free 90/10
AGDT sentence split, scored *in context*, with the **unseen-form** subset (forms
absent from the training split) called out separately. Since the AGDT is these
models' own training source, the unseen-form column is the honest generalization
measure.

| POS: held-out AGDT (≈54k tokens) | overall | unseen forms |
| --- | --- | --- |
| pyaegean tagger (pure Python, averaged perceptron) | 84.4% | 83.6% |

| Lemma: held-out AGDT | overall | unseen forms |
| --- | --- | --- |
| pyaegean lemmatizer (pure Python, edit-tree) | 84.5% | 40.3% |
| pyaegean `[neural]` lemmatizer (GreTa seq2seq, opt-in) | ~92% | **76.3%** |

For contrast, on the same tokens a bare treebank lookup scores 0% on unseen forms
(no entry). Reproduce with `greek.evaluate_tagger(holdout=0.1)` and
`greek.evaluate_lemmatizer()`. Recovering an unseen Greek lemma often means an
internal stem or accent change rather than a suffix swap, which is where the
pure-Python edit-tree reaches its limit and the seq2seq `[neural]` backend pulls
ahead (0% → 76.3% on unseen). Full method descriptions are on
[Greek NLP](Greek-NLP#generalizing-pos-tagger-opt-in).

## Evaluation protocol

- **Test sets.** The Universal Dependencies Ancient Greek test folds,
  `UD_Ancient_Greek-Perseus` (commit `331ddef`, CC BY-NC-SA 2.5) and
  `UD_Ancient_Greek-PROIEL` (commit `a4ab8d4`, CC BY-NC-SA 3.0), fetched to the cache
  for **evaluation only**, never bundled and never trained on.
- **Scorer.** The official CoNLL 2018 shared-task evaluator (`conll18_ud_eval.py`,
  MPL 2.0), fetched sha256-pinned
  (`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`). Reported
  figures are the evaluator's F1 per metric.
- **Gold tokenization.** pyaegean runs over each fold's gold FORM column, so its
  scores measure tagging, lemma, and parsing quality, not tokenizer agreement. The
  neural pipeline is *also* measured end-to-end from raw text through pyaegean's own
  tokenizer (tokens F1 99.97), and the scores track the gold-tokenization figures
  closely, so tokenization is not a bottleneck on this fold.
- **No tagset reconciliation.** UPOS and lemmas are scored exactly as emitted.
  Convention gaps count against pyaegean here, unlike `greek.evaluate_on_proiel`,
  which reconciles tagsets to isolate real errors.
- **Train / dev / test discipline.** Training is the AGDT (plus Gorman and Pedalion)
  minus the UD exclusion manifest. The dev fold drives early stopping, checkpoint
  selection, light schedule tuning, and the quantization gate; the test folds are
  scored once on the finished model and never used for any selection. Full protocol
  in [`training/README.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/training/README.md).
- **Lemma scoring.** On the UD folds, lemmas use the evaluator's exact string match
  with no added normalization (the UD gold is already NFC and carries no homograph
  digits), so convention differences count as errors rather than being normalized
  away. The native-corpus checks `evaluate_on_nt` / `evaluate_on_proiel` apply a
  light NFC-plus-homograph-digit clean-up, since those golds are not pre-normalized.
- **Bootstrap CIs.** `greek.bootstrap_ud()` gives a percentile confidence interval
  over a fold's sentences (999 resamples by default): a narrow interval means the
  number is stable, not a lucky fold.

### Leakage controls

UD Perseus is converted from the AGDT, the treebank pyaegean's Greek backends are
built from, so a naive evaluation would leak the test set into training. Two controls
keep the neural pipeline's numbers honest:

- **The UD-Perseus exclusion manifest.** `greek.agdt_ud_overlap()` resolves every
  UD-Perseus dev+test sentence to its AGDT source and verifies it by NFC form-sequence
  comparison: **2,443 sentences across 5 AGDT files, all form-identical**. The neural
  model's training split excludes all of them.
- **PROIEL is held out entirely.** No pyaegean model trains on PROIEL, so it is a
  genuine out-of-domain fold. The combined-corpus model adds the Gorman and Pedalion
  treebanks (both CC BY-SA 4.0); the overlap audit excluded 1,591 Gorman + 155
  Pedalion sentences matching either evaluation fold, and Gorman's Herodotus files
  (the same work as PROIEL's `hdt.xml`) are excluded at source.

One caveat applies only to the pure-Python baseline, not the neural pipeline: its
lookup and models are built from the *full* AGDT, which contains the UD-Perseus test
sentences, so its Perseus-fold scores are an in-training upper bound (marked ⚠ above).

## Cross-tool comparison (with citations)

From Kostkan, Kardos, Mortensen & Nielbo, *"OdyCy: A general-purpose NLP pipeline for
Ancient Greek"*, LaTeCH-CLfL 2023
([PDF](https://aclanthology.org/2023.latechclfl-1.14.pdf)), Tables 1–2: each pipeline
tokenizes its own text and is scored with spaCy evaluation scripts. Best per metric in
**bold**.

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

The same paper shows every single-treebank model collapsing on the *other* treebank
(e.g. Stanza-perseus scores 59.00 UAS on PROIEL), which is why pyaegean keeps
out-of-domain and unseen-form measurement first-class.

A newer baseline raises the parsing bar above that table: Riemenschneider & Frank
2024, *"A State-of-the-Art Morphosyntactic Parser and Lemmatizer for Ancient Greek"*
([arXiv:2410.12055](https://arxiv.org/abs/2410.12055), the GreBERTa/GreTa authors),
reports on the UD Perseus test fold (models trained on the UD train fold, gold
tokenization): GreBERTa-based parsing **UAS 88.20 / LAS 83.98**, POS 95.83, XPOS
91.09, and a GreTa lemmatizer at 91.17 lemma accuracy on their own (AGDT + Gorman +
Pedalion, normalized) folds. Their main models use the same license-clean data lever
(Gorman and Pedalion, both CC BY-SA 4.0) the pyaegean joint model uses. These are the
"2024" entries in the CI/margin table above.

Two more reference points, each reported under its *own* evaluation, so points of
reference rather than rows in the single-protocol table above:

- **Stanza's published model-performance numbers**
  ([performance page](https://stanfordnlp.github.io/stanza/performance.html)), under
  Stanza's own tokenization, give **grc_perseus** UPOS 92.41 / UFeats 91.11 / lemma
  87.86 / UAS 79.46 / LAS 73.97, and **grc_proiel** (in-domain for that model) UPOS
  97.42 / lemma 97.18 / LAS 79.02. Its self-reported Perseus lemma (87.86) edges the
  87.58 measured in the OdyCy table; pyaegean's 94.29 still leads it by +6.4, and it is
  the "Stanza model card" entry in the CI/margin table above.
- **DILEMMA** ([repository](https://github.com/ciscoriordan/dilemma)) is the closest
  *architectural* peer: a Greek tagger/lemmatizer on the same torch-free ONNX inference
  path pyaegean uses. It is lemmatizer-first and publishes accuracy only on its own
  multi-period benchmarks (93.7% equiv-adjusted on its DiGreC treebank, 99.7% on
  Classical Greek), not UD Ancient Greek Perseus UAS/LAS, so there is no same-fold
  parsing number to compare. It is a design peer here, not a measured row.

**The out-of-domain lead is like-for-like.** The in-domain published systems train on
the PROIEL fold itself; pyaegean never does. Against a *Perseus-trained* published
system, the fair out-of-domain comparison, pyaegean leads by roughly 23 UAS on PROIEL
(82.47 vs the Perseus-trained Stanza baseline's 59.00 on that fold).

## Model size and throughput

The model ships **quantized at about 173 MB** (tar.gz; 182 MB uncompressed
`model.onnx`), about 3× smaller than the fp32 build (518 MB tar.gz / 556 MB
uncompressed) and **lossless on accuracy**: UD Perseus test scores are unchanged
within ±0.02 (UPOS 97.0 / UFeats 96.0 / lemma 94.3 / UAS 90.2 / LAS 85.6). The recipe
is weight-only int8 (onnxruntime MatMulNBits, block 128, symmetric) plus fp16 on
everything else, keeping activations at fp32 by design. Full int8 (quantized
activations) collapses the GreBerta encoder (its activation outliers do not survive
8-bit quantization, dropping UPOS from 97 to 16–32 and LAS from 86 to 1–13), so the
weight-only recipe is the one that ships the size win at no accuracy cost. It requires
**onnxruntime ≥ 1.23** (the `[neural]` floor); the fp32 model stays available at the
`grc-joint-v2` release for reproducibility.

The trade-off is **CPU throughput**: the int8 kernels run several times slower than
fp32 on this workload, roughly **20–70 words/s** quantized versus roughly **300
words/s** fp32 on the development machine (sentence-length dependent). Unlike the
accuracy figures, throughput is **hardware-dependent and illustrative, not a pinned
benchmark**: it scales with the CPU, core count, and workload, so read it as an
order-of-magnitude guide. It is re-measured only when the model or the `onnxruntime`
floor changes, not automatically per release.

## Reproduce the numbers

The shipped neural pipeline, gold-tokenized, on both UD test folds:

```python
from aegean import greek
greek.use_neural_pipeline()
greek.evaluate_on_ud("perseus", "test")   # {'upos': …, 'ufeats': …, 'lemma': …, 'uas': …, 'las': …, 'xpos': …}
greek.evaluate_on_ud("proiel", "test")    # out of domain
greek.evaluate_on_nt()                     # whole Nestle 1904 NT (≈1 h on plain CPU)
greek.bootstrap_ud("perseus", "test")      # percentile CIs, 999 resamples
```

From the shell (`pip install "pyaegean[cli,neural]"`):

```bash
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval ud --fold proiel --split test --neural
aegean greek eval nt --neural
```

The offline-baseline rows and the held-out generalization numbers reproduce with the
pure-Python backends and `greek.evaluate_tagger()` / `greek.evaluate_lemmatizer()` /
`greek.evaluate_parser()`. The full `aegean greek eval` target table and the
evaluation functions are documented on
[Greek NLP](Greek-NLP#standard-benchmark-evaluation-universal-dependencies). These
targets are heavy: they fetch gold data and may train, so run them only to reproduce
a number.

## A note on the Aegean scripts

The accuracy tables on this page are Greek NLP metrics. The Aegean syllabic scripts
are scored differently: Linear B and Cypriot carry Greek-reading bridges, but **Linear
A and Cypro-Minoan are undeciphered**, so there is no gold reading to score a
"translation" against and pyaegean never presents one as fact. Their tooling is
measured by corpus-fidelity and round-trip invariants (documented on
[Linear A](Linear-A), [Cypriot](Cypriot), and [Limitations](Limitations)), not by an
accuracy percentage.

## Where this lives (canonical source)

`docs/benchmarks.md` (in the repository)
in the repository is the canonical, registry-pinned source for every number on this
page. Each published figure is stored in `training/results/published-claims.json`;
`tests/test_benchmark_claims.py` asserts the docs (and their README and wiki echoes)
carry exactly those values per commit and offline, so a documented number cannot drift
without the registry, and `scripts/check_benchmarks.py --measure` re-runs the
offline-stack rows against it. A legitimate re-measure updates the registry, the docs,
and the evidence file in a single commit.

For the surrounding detail, see the
[Methodology](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/methodology.md)
notes, the evaluation tooling and reproduction targets on
[Greek NLP](Greek-NLP#reproduce-the-numbers-from-the-shell), the reproducibility and
"reproduce or challenge the number" stance on [For Specialists](For-Specialists), the
data licences and provenance of every fetched fold and model on
[Data and Provenance](Data-and-Provenance), and the honest scope of each component on
[Limitations](Limitations).
