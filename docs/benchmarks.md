# Greek NLP benchmarks — protocol and numbers

The measurement backbone of the WP3 accuracy program (see `ROADMAP.md`): how pyaegean is
scored on the field's standard Ancient Greek benchmarks, what the field's published numbers
are, the leakage controls that keep the comparison honest, and pyaegean's own measured
results. Public-facing docs (README/wiki) carry only pyaegean's own numbers; the cross-tool
tables live here, with citations.

## Protocol

- **Test sets:** the Universal Dependencies Ancient Greek test folds —
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
  so the protocols are close but not identical — noted for precision.)
- **No tagset reconciliation:** UPOS and lemmas are scored exactly as emitted. Convention
  gaps (e.g. the AGDT scheme has no PROPN/SCONJ on the PROIEL fold's conventions) count
  against pyaegean here, unlike `greek.evaluate_on_proiel`, which reconciles tagsets to
  isolate real errors.
- **DEPREL:** pyaegean's current parser emits AGDT/Prague labels (PRED, SBJ, ATR, AuxP…),
  not UD relations, so its **LAS against UD gold is structurally ≈0 and is not reported**;
  **UAS** (unlabeled attachment) is comparable. The Stage C parser will emit UD relations
  (via an AGDT→UD conversion of the CC BY-SA training data), making LAS comparable.
- Reproduce with:

  ```python
  from aegean import greek
  greek.use_treebank(); greek.use_tagger(); greek.use_lemmatizer(); greek.use_parser()
  greek.evaluate_on_ud("perseus", "test")
  greek.evaluate_on_ud("proiel", "test")
  ```

## Leakage controls

- **UD Perseus is converted from the AGDT** — its sentence ids point directly at AGDT
  files (`tlg0008….tb.xml@197`). `greek.agdt_ud_overlap()` resolves every UD-Perseus
  dev+test sentence to its AGDT source and verifies the reference by NFC form-sequence
  comparison. Result against the pinned commits: **2,443 sentences across 5 AGDT files,
  2,443/2,443 form-identical**. The manifest is cached
  (`ud-grc/agdt-ud-exclusion.json`) and **every model trained from Stage A on must
  exclude these sentences from its training split**.
- **The current (0.8.0-era) production models are in-training on the Perseus fold.** The
  perceptron tagger, edit-tree lemmatizer, arc-eager parser, treebank lookup, and the
  neural lemmatizer's gold lookup are all built from the *full* AGDT — which contains the
  UD-Perseus test sentences. Their Perseus-fold scores below are therefore an
  **in-training upper bound**, reported for orientation, not as generalization claims.
  The PROIEL fold is the honest current number (no pyaegean model trains on PROIEL).
- **Open audit item:** the neural lemmatizer's training mix includes the Gorman (CC0) and
  Pedalion (CC BY-SA) treebanks. Whether their texts overlap the PROIEL fold's content
  (Herodotus) has not yet been audited; until it is, treat the neural rows on PROIEL with
  that asterisk. (Stage A's dataset builder will settle this with the same id/text-match
  approach used for the AGDT manifest.)

## The field's published numbers

From Kostkan, Kardos, Mortensen & Nielbo, *“OdyCy — A general-purpose NLP pipeline for
Ancient Greek”*, LaTeCH-CLfL 2023 (<https://aclanthology.org/2023.latechclfl-1.14.pdf>),
Tables 1–2 — each pipeline's own tokenization, spaCy evaluation scripts. Best per metric
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

(The same paper shows every single-treebank model collapsing on the *other* treebank —
e.g. Stanza-perseus scores 59.00 UAS on PROIEL — which is why pyaegean keeps out-of-domain
and unseen-form measurement first-class.)

**Newer baseline (found in a freshness sweep, 2026-06-10):** Riemenschneider & Frank 2024,
*“A State-of-the-Art Morphosyntactic Parser and Lemmatizer for Ancient Greek”*
(<https://arxiv.org/abs/2410.12055> — the GreBERTa/GreTa authors), reports on the UD
Perseus test fold (models trained on the UD train fold; gold tokenization): GreBERTa-based
parsing **UAS 88.20 / LAS 83.98**, POS 95.83, XPOS 91.09; and a GreTa lemmatizer at 91.17
lemma accuracy on their own (AGDT+Gorman+Pedalion, normalized) folds. This **raises the
parsing bar** above the odyCy-era table: the live targets are UAS ≥ 88.2 / LAS ≥ 84.0.
Their main models train on AGDT+Gorman+Pedalion (~1.26 M tokens, ≈2.45× pyaegean's
current AGDT-only split) — the same license-clean data lever (Gorman CC0, Pedalion
CC BY-SA) already named in ROADMAP WP3 §3.6, which is pyaegean's planned response.

## pyaegean — Stage 0 baseline (current stack, pre-program)

Measured with the protocol above, pyaegean 0.8.0-dev. “Pure-Python stack” =
`use_treebank() + use_tagger() + use_lemmatizer() + use_parser()` (zero heavy
dependencies); “+ neural lemma” adds `use_neural_lemmatizer()` (the `[neural]` extra).

| Fold | Stack | UPOS | Lemma | UAS | LAS |
|---|---|---|---|---|---|
| Perseus test ⚠ | pure-Python | 87.05 | 97.65 | 37.89 | n/a |
| Perseus test ⚠ | + neural lemma | 87.05 | 97.65 | 37.89 | n/a |
| PROIEL test | pure-Python | 75.03 | 85.26 | 33.51 | n/a |
| PROIEL test | + neural lemma | 75.03 | **90.38** | 33.48 | n/a |

(Perseus: 1,306 sentences / 20,959 words; PROIEL: 1,047 / 13,314. pyaegean 0.8.0-dev,
2026-06-10.) ⚠ = in-training upper bound (see Leakage controls) — the 97.65 Perseus lemma
is the lookup *memorizing* the fold, exhibit A for why the exclusion manifest exists; the
neural tier changes nothing on Perseus for the same reason (the lookup answers first). LAS
n/a: Prague labels vs UD gold.

**Reading the honest (PROIEL) rows against the targets:**

- **Lemma 90.38** (with the `[neural]` seq2seq; 85.26 pure-Python) vs the 94.41 target —
  the neural tier delivers exactly where designed (out-of-domain unseen forms, +5.1), and
  the remaining ~4-point gap is Stage D's job (sentence-context conditioning). For
  perspective: 90.38 *clean out-of-domain* sits at the level the published out-of-domain
  systems reach on this fold (odyCy-perseus: 91.36) — subject to the Gorman/Pedalion
  overlap audit flagged above.
- **UPOS 75.03** vs 97.81 — the unreconciled protocol charges the AGDT-scheme tagger for
  its PROPN/SCONJ conventions on top of real errors (the reconciled `evaluate_on_proiel`
  number is substantially higher, which bounds the convention share); Stage B's neural
  tagger trains and emits UD-convention tags, removing the convention tax entirely.
- **UAS 33.5** vs 83.17 — the chasm: a greedy, projective-only arc-eager parser on
  ~69%-non-projective Greek, exactly what Stage C's graph-based biaffine parser is for.

A side discovery of this baseline run: the first PROIEL pass crashed on an
out-of-vocabulary form and exposed (and fixed) an infinite-recursion bug in the
`use_tagger()`+`use_lemmatizer()` combination — see the 0.8.0 changelog.

## Stage A — encoder bake-off (decided: GreBerta)

Identical fixed-budget UPOS fine-tune per candidate (2 epochs, lr 5e-5, effective batch
32, max-len 256, seed 42, bf16) on the leakage-clean AGDT split (514,824 train tokens;
dev = the 22,135 tokens behind the UD-Perseus dev fold, 2,614 of them unseen forms; zero
truncation for any candidate). Run 2026-06-10 on an A100-80GB (the G4/A100 plan's
backup); raw metrics in `training/results/stage-a/`.

| Encoder | License | dev UPOS | unseen forms | params | wall |
|---|---|---|---|---|---|
| **bowphs/GreBerta** | Apache-2.0 | **97.85** | 98.01 | 125.4 M | 89 s |
| bowphs/PhilBerta | Apache-2.0 | 97.83 | **98.20** | 134.6 M | 88 s |
| pranaydeeps/Ancient-Greek-BERT *(reference)* | GPL-3.0 | 96.98 | 96.94 | 112.3 M | 88 s |

**Decision (per the training/README.md rule): `bowphs/GreBerta` carries Stages B–E.**
The two Apache candidates are statistically tied — 0.02 points overall (≈4 tokens) and
0.19 on unseen forms, far under the 1-point override threshold — so the tie breaks on
size: GreBerta is ~7% smaller (a smaller Stage E artifact) and monolingual Greek.
PhilBerta is the named fallback (and the trilingual option if Latin ever matters).

Calibration: both Apache candidates beat the odyCy backbone (Ancient-Greek-BERT) by
~0.9 points overall and ~1.1–1.3 on unseen forms under the identical budget — the chosen
backbone starts *ahead* of the published pipeline's starting point. Caveat for reading
the numbers: this dev set is AGDT-native 13-label UPOS, not the UD test fold — it ranks
encoders; absolute UD-fold claims start in Stage B.

## Stage B — joint neural tagger (targets met)

GreBerta + 10 token-classification heads (UPOS + the 9 XPOS positions; UD FEATS rendered
by the validated converter), trained on the **leakage-clean** AGDT split (the 2,443
UD-Perseus dev/test sentences excluded) with UD-convention labels. 6 epochs, lr 3e-5,
batch 32, bf16, 155 s on an RTX PRO 6000 Blackwell (peak 5.2 GB); best epoch selected on
dev (97.68 UPOS / 96.53 FEATS). Run 2026-06-10; raw metrics in
`training/results/stage-b/`. Gold-tokenization protocol, as throughout.

| Test fold | Metric | pyaegean Stage B | best published | published Perseus-trained best |
|---|---|---|---|---|
| UD Perseus | UPOS | **96.18** | 95.39 (odyCy-joint) | — |
| UD Perseus | UFeats | **95.32** | 92.56 (odyCy-joint) | — |
| UD Perseus | XPOS (9-char) | 92.21 | — | — |
| UD PROIEL | UPOS | **87.31** | 98.23 (greCy-proiel, in-domain) | 84.88 (odyCy-perseus) |
| UD PROIEL | UFeats | **58.95** | 94.05 (greCy-proiel, in-domain) | 57.44 (odyCy-perseus) |

**Both Stage B targets are met on UD Perseus test — above every published number**: UPOS
96.18 vs the 95.39 best (+0.8) and UFeats 95.32 vs the 92.56 best (+2.8), from a model
that never saw the test sentences in training. Out-of-domain (PROIEL), where the
in-domain systems train on the fold itself, the honest comparison is against the
*Perseus-trained* published systems — and Stage B beats all of them on both metrics
(UPOS 87.31 vs 84.88/80.93/80.42; UFeats 58.95 vs 57.44/56.11/56.00). The low absolute
PROIEL UFeats is convention-capped (PROIEL annotates five extra feature types the
Perseus scheme lacks), and PROIEL XPOS is structurally 0 (a different tagset entirely) —
both expected. Versus the Stage 0 baseline, PROIEL UPOS moved **75.03 → 87.31**.

Scoreboard against the definition of done, after Stage B: UD-Perseus **POS ✓, morph ✓**;
lemma 90.4 (Stage D to close); **UAS/LAS pending — Stage C, the biaffine parser.**

## Stage C — biaffine parser (targets demolished)

The joint tagger-parser: one GreBerta encoder carrying the Stage B tagging heads **plus**
biaffine arc/relation scorers (Dozat–Manning), trained on the leakage-clean AGDT split
with UD-convention trees from the validated converter (`agdt_ud_deps.py`; 96.5% heads /
94.5% head+label agreement — see the Stage C scaffolding commit). Decoding: single-root
Chu-Liu/Edmonds MST, so non-projectivity is handled natively. 6 epochs, lr 3e-5, batch
32, bf16, 161 s on an RTX PRO 6000 Blackwell (peak 5.4 GB); selection on dev LAS (best:
86.53 / 82.81). Run 2026-06-10; raw metrics in `training/results/stage-c/`.

| Test fold | Metric | pyaegean Stage C | best published | published Perseus-trained best |
|---|---|---|---|---|
| UD Perseus | UAS | **87.49** | 78.80 (odyCy-joint) | — |
| UD Perseus | LAS | **82.30** | 73.09 (odyCy-joint) | — |
| UD Perseus | CLAS | 80.03 | — | — |
| UD Perseus | UPOS / UFeats | 96.21 / 95.19 | 95.39 / 92.56 | — |
| UD PROIEL | UAS | **81.61** | 85.74 (greCy-proiel, in-domain) | 64.55 (odyCy-perseus) |
| UD PROIEL | LAS | **63.18** | 82.28 (greCy-proiel, in-domain) | 48.72 (odyCy-perseus) |

**Both Stage C targets are met with ~9 points to spare**: UAS 87.49 vs the published best
78.80 (+8.7), LAS 82.30 vs 73.09 (+9.2) — from a leakage-clean model, with the tagging
metrics still above every published number in the same checkpoint. Against the Stage 0
arc-eager baseline, Perseus UAS moved **37.9 → 87.5**. The wins compound from three
choices: graph-based decoding (Ancient Greek is ~69% non-projective sentences), ~2.7×
the training data of the UD-trained systems (31,112 leakage-clean AGDT sentences vs the
11,476-sentence UD train fold), and a strong monolingual encoder.

Out-of-domain (PROIEL): UAS 81.61 / LAS 63.18 beats every published *Perseus-trained*
system by ~17 / ~14.5 points — and the out-of-domain UAS sits within 1.6 points of
odyCy-joint's **in-domain** 83.17. The LAS gap to in-domain systems is largely deprel-
convention divergence between the two treebanks' UD conversions (the same effect capping
PROIEL UFeats), the NC-variant gate's territory if PROIEL-side parity is ever pursued.

Scoreboard after Stage C: UD-Perseus **POS ✓ morph ✓ UAS ✓ LAS ✓** against the odyCy-era
published field, leakage-clean. Against the **2024 baseline** (see above), tagging still
leads (POS 96.21 vs 95.83; XPOS 92.21 vs 91.09) but parsing trails by 0.7 UAS / 1.7 LAS
(87.49/82.30 vs 88.20/83.98) — the planned close is the Gorman+Pedalion data extension
(≈2.45× training tokens). Remaining: **lemma** (Stage D — ≥ 87.6 on Perseus test from a
leakage-clean lemmatizer; the current hybrid's lookup contains the fold, so its 97.65 is
an in-training number).

## Stage D — the full model (the odyCy-era definition of done is complete)

The complete joint model: GreBerta + tagging heads + biaffine parser + the **edit-script
lemma head** (9,263 train-only classes) composed with the train-only lookup
(`lookup-first`, the dev-preferred mode). Trained leakage-clean, 9 epochs / 254 s on an
RTX PRO 6000 Blackwell (bf16, peak 5.8 GB); dev best: lemma 90.32, LAS 82.76. Run
2026-06-10; raw metrics in `training/results/stage-d/`.

| Test fold | Lemma | UAS | LAS | UPOS | UFeats |
|---|---|---|---|---|---|
| UD Perseus | **87.71** | 87.41 | 82.23 | 96.37 | 95.19 |
| UD PROIEL | 85.83 | 81.04 | 62.67 | 87.67 | 59.01 |

**Lemma 87.71 clears the 87.58 odyCy-era bar — by 0.13 points** (a thin, single-seed
margin, stated plainly). With it, **the original WP3 definition of done is complete on
UD Perseus**: all five metrics — POS 96.37, morph 95.19, lemma 87.71, UAS 87.41, LAS
82.23 — above the 2023-published field, leakage-clean, from **one checkpoint**. Parsing
and tagging held at their Stage C levels (±0.1, noise) with the lemma loss added.

Two honest observations that shape the next step:

1. **Against the raised 2024 bar** (arXiv:2410.12055): parsing trails by 0.8 UAS /
   1.75 LAS, and their lemmatizer's 91.17 (own folds) likely outpaces our 87.71.
2. **On PROIEL, the Stage D lemma (85.83) is *weaker* than the currently-shipped hybrid's
   90.38** — the shipped GreTa seq2seq *generates* novel lemmas and trained on ~2.45×
   the data (AGDT+Gorman+Pedalion), while the edit-script head classifies into a closed
   inventory. The shipped hybrid therefore **remains the package's lemmatizer** unless
   Stage D+ beats it on both folds.

Both gaps point at the same lever: the **Gorman (CC0) + Pedalion (CC BY-SA) data
extension** (the 2024 system's mix, ~2.45× tokens) — one combined retrain (Stage D+),
with the overlap audit extended to PROIEL (Gorman includes Herodotus), is the planned
close for parsing, lemma, and the PROIEL regression at once.

## WP3 targets (definition of done)

- **UD Perseus test:** ≥ the best published number on every metric — POS ≥ 95.4,
  morph ≥ 92.6, lemma ≥ 87.6, UAS ≥ 78.8, LAS ≥ 73.1 — from a model whose training split
  excludes the overlap manifest above (i.e. a *real* held-out claim, unlike the baseline
  rows).
- **UD PROIEL test:** ≥ odyCy-joint on every metric (POS 97.81, morph 93.46, lemma 94.41,
  UAS 83.17, LAS 79.03); stretch to best-published via the optional NC-variant gate
  (ROADMAP WP3 §3.6).
- All numbers reproduced by the public benchmark notebook; unseen-form and out-of-domain
  honesty metrics maintained alongside.
