# training/ — model training for the Greek NLP pipeline

> **The shipped model.** `grc-joint-v2` is the combined-corpus checkpoint, with two changes
> over the first build: the AGDT→UD converter attaches non-coordination commas to the
> following token (the UD-Perseus convention), and the relation head is trained on the model's
> predicted arcs, not only gold arcs. As exported and re-measured through the shipped ONNX
> pipeline, the UD Ancient Greek (Perseus) test fold is lemma 94.29 / UAS 90.23 / LAS 85.64 /
> UPOS 97.04 / UFeats 96.04 / XPOS 93.48, and PROIEL lemma 90.50. Across five seed replicates
> the recipe averages LAS 85.58 ± 0.10 / UAS 90.15 ± 0.12. Per-stage raw metrics are under
> `results/`; the full protocol and tables are in `docs/benchmarks.md`.

Training-side code for the Greek NLP models (`docs/benchmarks.md` has the protocol and
the numbers). Nothing in this directory ships in the wheel; trained artifacts are
published as GitHub release assets and fetched to the cache, never bundled.

## Stage A — encoder bake-off

**Question:** which pretrained encoder carries Stages B–E?
**Method:** identical quick UPOS fine-tune per candidate on the leakage-clean AGDT split;
decide on dev accuracy (primary), unseen-form accuracy (generalization), size/speed, and
license.

### Candidates

| Model | Arch | License | Role |
|---|---|---|---|
| `bowphs/GreBerta` | RoBERTa, grc monolingual | Apache-2.0 | **shippable candidate** |
| `bowphs/PhilBerta` | RoBERTa, grc+la+en trilingual | Apache-2.0 | **shippable candidate** |
| `pranaydeeps/Ancient-Greek-BERT` | BERT (the odyCy backbone) | **GPL-3.0** | reference point only: calibrates against the odyCy starting point; fine-tuned weights are NOT redistributable under this project's licensing |

(GreBerta/PhilBerta are the GreTa authors' encoders: same Apache-2.0 lineage as the
neural lemmatizer pyaegean already redistributes.)

### Decision rule

1. License gate first: the shipped encoder must be Apache/MIT-class (GreBerta or
   PhilBerta). Ancient-Greek-BERT's score is measured for calibration only.
2. Among shippable candidates: highest dev UPOS accuracy wins; an unseen-form accuracy
   gap > 1 point overrides a smaller overall gap (generalization is what these models are for).
3. Ties broken by size (smaller → smaller ONNX artifact in Stage E) and wall time.
4. Record the decision + all metrics tables in `docs/benchmarks.md`.

### Running it (Colab — planned hardware: G4, with A100 backup)

The expected accelerator is a **Colab G4** (NVIDIA RTX PRO 6000 Blackwell Server Edition,
96 GB), with **A100** as backup and H100 opportunistic. The script auto-detects precision:
**bf16** on Blackwell/Ampere-class GPUs (no loss scaler), fp16 on older cards, and enables
TF32 matmuls. At 96 GB, base-size encoders at the default batch are nowhere near memory
limits: expect a few minutes per candidate, not tens.

The pip install provides the `aegean` package; the `training/` scripts are deliberately
**not** in the wheel, so clone the repo for them and run them from the clone:

```bash
pip install "git+https://github.com/ryanpavlicek/pyaegean" torch transformers numpy
git clone https://github.com/ryanpavlicek/pyaegean.git pyaegean_repo

python pyaegean_repo/training/build_upos_dataset.py   # fetches AGDT + UD folds to cache; writes data/ in the clone
python pyaegean_repo/training/bakeoff_upos.py --model bowphs/GreBerta
python pyaegean_repo/training/bakeoff_upos.py --model bowphs/PhilBerta
python pyaegean_repo/training/bakeoff_upos.py --model pranaydeeps/Ancient-Greek-BERT
```

Before the Colab runtime recycles, save the result files:
`pyaegean_repo/training/out/<model>/metrics.json` (one per candidate).

Each run writes `training/out/<model>/metrics.json`. The fixed budget: 2 epochs, lr 5e-5,
effective batch 32 (native `--batch 32`), max-len 256, seed 42: **must stay identical
across candidates**; that's the bake-off. On a faster GPU the same commands simply finish
sooner — don't retune. (Fallback only: on a 16 GB-class card, keep the budget with
`--batch 16 --grad-accum 2`, and `--precision fp16` if bf16 is unsupported.) Robustness
check, since G4 time makes it cheap: repeat the top two candidates with `--seed 7`.

Smoke-test the plumbing before a GPU session: `--limit-train 500 --epochs 1` (runs on CPU too).

### The data protocol (what build_upos_dataset.py enforces)

- **train** = AGDT minus every sentence in the UD-Perseus dev+test exclusion manifest
  (`aegean.greek.agdt_ud_overlap`; 2,443 sentences, 100% form-verified).
- **dev** = exactly the AGDT sentences behind the UD-Perseus *dev* fold: never trained
  on, stable across runs, and citable.
- The AGDT sentences behind the UD-Perseus *test* fold appear in **neither** file: final
  numbers come only from `greek.evaluate_on_ud("perseus", "test")` against a finished
  model.
- Labels are AGDT-native coarse UPOS (relative bake-off measure). The UD-convention label
  work (PROPN/SCONJ) is Stage B, where absolute UD-fold numbers start to matter.

`training/data/` and `training/out/` are gitignored: datasets rebuild deterministically
from the cache, and bake-off checkpoints are throwaway (`--save-model` exists for
debugging only). What comes back from a GPU session is the `metrics.json` files.

## Stage B — the joint UPOS + morphology tagger (on GreBerta)

**Targets (UD Perseus test):** UPOS ≥ 95.4, UFeats ≥ 92.6: the best published numbers
(see `docs/benchmarks.md`).

**Labels.** The model trains on **UD-convention labels** built by the authored,
validated AGDT→UD converter (`agdt_ud.py`): UPOS directly (15 labels: it learns the
CCONJ/SCONJ lexical split and the copular AUX from context) plus the 9 XPOS positions,
from which UD FEATS render deterministically. Converter agreement with the UD-Perseus
conversion, measured on the train fold (`validate_agdt_ud.py`, evaluation-only use):
**UPOS 99.94%, FEATS 100.00%**: label noise sits far below model error.

**Run (same clone setup as Stage A):**

```bash
python pyaegean_repo/training/build_tagger_dataset.py
python pyaegean_repo/training/train_tagger.py --model bowphs/GreBerta
python pyaegean_repo/training/eval_tagger_ud.py \
    --checkpoint pyaegean_repo/training/out/tagger/model --treebank perseus --split test \
    --out pyaegean_repo/training/out/tagger/ud-perseus-test.json
python pyaegean_repo/training/eval_tagger_ud.py \
    --checkpoint pyaegean_repo/training/out/tagger/model --treebank proiel --split test \
    --out pyaegean_repo/training/out/tagger/ud-proiel-test.json
```

Defaults: 4 epochs, lr 3e-5, batch 32, bf16 auto: per-epoch dev selection keeps the
best checkpoint. This is the real model, not a bake-off: tuning on **dev** is fair game
(epochs/lr; e.g. try 6 epochs if dev is still improving); the **test folds are
measured once, at the end**. Bring back: `out/tagger/metrics.json`, the two
`ud-*-test.json` files, and: unlike Stage A: **the checkpoint directory itself**
(`out/tagger/model/`, ~500 MB; save it to Drive). Stage C trains the parser on the same
encoder, and Stage E exports it to ONNX.

If UPOS lands short of target, the first lever is more epochs; the second is adding the
Gorman (CC0) prose treebanks to the training data (same XML schema: extend the builder).

## Stage C — the biaffine parser (joint with tagging, on GreBerta)

**Targets (UD Perseus test):** UAS ≥ 78.8, LAS ≥ 73.1: the best published numbers.

**Trees.** The model trains on **UD-convention dependency trees** built by the authored,
validated AGDT→UD converter (`agdt_ud_deps.py`): the structural Prague→UD transforms
(coordination promotion, AuxP/AuxC demotion, copula promotion, punctuation re-attachment)
plus a POS-sensitive label map. Agreement with the UD-Perseus conversion, measured on the
train fold (`validate_agdt_ud_deps.py`): **96.5% heads, 94.5% head+label**: the residue
is dominated by UD-Perseus's irregular comma attachment.

**Model.** One shared encoder with the Stage B tagging heads **plus** biaffine arc and
relation scorers (Dozat–Manning). Decoding is graph-based: greedy for dev selection,
single-root Chu-Liu/Edmonds MST at evaluation — so non-projectivity (the arc-eager
baseline's structural cap) is handled natively. The saved checkpoint serves the whole
pipeline: UPOS, XPOS, FEATS, heads, relations: this is the artifact Stage E exports.

**Run (same clone setup):**

```bash
python pyaegean_repo/training/build_parser_dataset.py
python pyaegean_repo/training/train_parser.py --model bowphs/GreBerta
python pyaegean_repo/training/eval_parser_ud.py \
    --checkpoint pyaegean_repo/training/out/parser/model --treebank perseus --split test \
    --out pyaegean_repo/training/out/parser/ud-perseus-test.json
python pyaegean_repo/training/eval_parser_ud.py \
    --checkpoint pyaegean_repo/training/out/parser/model --treebank proiel --split test \
    --out pyaegean_repo/training/out/parser/ud-proiel-test.json
```

Defaults: 6 epochs, lr 3e-5, batch 32, bf16 auto; selection on dev LAS. Tune on dev
(more epochs if still improving); test folds are measured once at the end. Bring back
`metrics.json`, both `ud-*-test.json`, and **the checkpoint** (`out/parser/model/`,
~520 MB → Drive): it supersedes the Stage B artifact (same tagging heads included)
and is what Stage E exports to ONNX.

## Stage D — the full model: tags + trees + lemmas (one checkpoint)

**Target (UD Perseus test): lemma ≥ 87.6**: from a **leakage-clean** lemmatizer (the
shipped hybrid's lookup contains the fold, so its 97.65 is an in-training number; the
clean reference is PROIEL 90.38).

**Design.** The Stage C JointParser with its lemma head on: a word-level classifier over
**edit scripts** (Chrupała edit trees, reusing `aegean.greek.lemmatizer`'s pure-Python
build/apply: 9,263 classes cover 98.5% of train / 96.7% of dev tokens), composed with a
**train-only lookup** (form, form|UPOS, lowercased). Context-sensitivity comes free from
the encoder (homographs disambiguate by sentence), with no autoregressive decoding — and
the artifact stays ONE checkpoint serving UPOS/XPOS/FEATS/heads/deprels/lemmas. The lemma
supervision is byte-identical to UD's lemma column (validated on all 159,895 aligned
train tokens). Even with an untrained head, the lookup alone floors dev lemma at ~82%.

**Run (same clone setup; notebook: `training/stage_d_full.ipynb`):**

```bash
python pyaegean_repo/training/build_full_dataset.py
python pyaegean_repo/training/train_full.py --model bowphs/GreBerta
# pick --compose from the dev line the trainer prints (lemma_best_mode), then:
python pyaegean_repo/training/eval_full_ud.py \
    --checkpoint pyaegean_repo/training/out/full/model --compose <best-mode> \
    --treebank perseus --split test --out pyaegean_repo/training/out/full/ud-perseus-test.json
python pyaegean_repo/training/eval_full_ud.py \
    --checkpoint pyaegean_repo/training/out/full/model --compose <best-mode> \
    --treebank proiel --split test --out pyaegean_repo/training/out/full/ud-proiel-test.json
```

Selection: (dev LAS + best lemma composition)/2. Bring back `metrics.json`, both
`ud-*-test.json`, and **the checkpoint** (`out/full/model/`, ~550 MB → Drive: weights +
tokenizer + labels.json + the lemma scripts/lookup): this is THE Stage E artifact,
superseding Stage C's. If lemma lands short, the levers are more epochs, a lower
--min-freq when building (more script classes), and a morph-conditioned seq2seq as the
unseen-form tier (the shipped GreTa pattern, retrained leakage-clean).
