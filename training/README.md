# training/ — Greek NLP model training

Training code for the Greek NLP models. Nothing in this directory ships in the wheel;
trained artifacts are published as GitHub release assets and fetched to the cache, never
bundled. The evaluation protocol and all benchmark numbers are in `docs/benchmarks.md`.

## Shipped model

The shipped release asset is **`grc-joint-v3`**: the combined-corpus checkpoint quantized
weight-only (int8 MatMulNBits, block 128, symmetric on the MatMul weights; fp16 elsewhere,
including the word-embedding table; activations kept fp32), ~173 MB, produced from the fp32
`grc-joint-v2` checkpoint by `quantize_grc_joint.py`. The fp32 `grc-joint-v2` (~518 MB) is
retained for reproducibility. One GreBerta encoder serves UPOS, XPOS, UD FEATS, dependency
trees, and lemmas. On the UD Ancient Greek (Perseus) test fold it scores lemma 94.29 /
UAS 90.23 / LAS 85.64 / UPOS 97.04 / UFeats 96.04 / XPOS 93.48, and lemma 90.50 on PROIEL
(out of domain); quantization is lossless within ±0.02 on those metrics. Across five training
seeds the recipe averages LAS 85.58 ± 0.10 / UAS 90.15 ± 0.12.

## Pipeline

The model is built in stages. Each stage has a dataset builder and a training script in
this directory; `results/` holds the shipped-model evidence (the grc-joint-v2 seed
replicates, the export gate report, and bootstrap CIs).

- **Stage A — encoder selection.** Fine-tune UPOS on each candidate encoder under an
  identical budget; pick on dev accuracy, generalization to unseen forms, size, and
  license. GreBerta (RoBERTa, Ancient Greek, Apache-2.0) is the shipped encoder.
- **Stage B — joint tagger.** UPOS + XPOS + UD FEATS on the GreBerta encoder, trained on
  UD-convention labels from the AGDT→UD converter (`agdt_ud.py`).
- **Stage C — biaffine parser.** Dozat–Manning arc and relation scorers on the shared
  encoder, with single-root Chu-Liu/Edmonds MST decoding at evaluation (non-projective
  trees handled natively). Trees come from the AGDT→UD dependency converter
  (`agdt_ud_deps.py`).
- **Stage D — lemmas.** A word-level edit-script classifier (Chrupała edit trees) plus a
  train-only lookup, on the same checkpoint. The result is one model serving tags, trees,
  and lemmas.
- **Stage E — export and quantize.** Export the checkpoint to ONNX (fp32, torch-free at
  inference; this is the reproducibility `grc-joint-v2` asset), then quantize weight-only
  (int8 MatMulNBits + fp16) with `quantize_grc_joint.py` to produce the shipped `grc-joint-v3`
  asset (~173 MB, lossless within ±0.02 on the UD Perseus metrics). The alternative full int8
  with *quantized activations* was gated on a ≤0.3-point drop and rejected: the GreBerta
  encoder's activation outliers collapse under 8-bit activations (UPOS 97→16–32). Keeping
  activations fp32 and quantizing only the weights ships the size win at no accuracy cost.

## Data protocol

Training data is leakage-clean against the evaluation folds:

- **train** = AGDT + Gorman + Pedalion, minus every sentence in the UD-Perseus dev+test
  exclusion manifest (`greek.agdt_ud_overlap`).
- **dev** = the AGDT sentences behind the UD-Perseus dev fold.
- **test** = in neither train nor dev; final numbers come only from
  `greek.evaluate_on_ud("perseus", "test")` against a finished model.

`training/data/` and `training/out/` are gitignored; datasets rebuild deterministically
from the cache.

## Running

The `training/` scripts are not in the wheel, so clone the repo and run them from the
clone. Training runs on a single GPU (the scripts auto-detect bf16/fp16); datasets fetch
the AGDT and UD folds to the cache on first build.

```bash
pip install "git+https://github.com/ryanpavlicek/pyaegean" torch transformers numpy
git clone https://github.com/ryanpavlicek/pyaegean.git
python pyaegean/training/build_full_dataset.py
python pyaegean/training/train_full.py --model bowphs/GreBerta
python pyaegean/training/eval_full_ud.py \
    --checkpoint pyaegean/training/out/full/model --treebank perseus --split test
```
