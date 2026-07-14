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
trees, and lemmas. On the UD Ancient Greek (Perseus) test fold it scores lemma 94.27 /
UAS 90.24 / LAS 85.65 / UPOS 97.02 / UFeats 96.04 / XPOS 93.48, and lemma 90.51 on PROIEL
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

## Shared preprocessing contract

Candidate joint checkpoints use the dependency-free
`aegean.greek.neural_preprocessing` contract in both training and package inference. Its
version is saved in `labels.json` together with the canonical annotation profile
`pyaegean-canonical-v1`, NFC
normalization, pretokenized segmentation, Roberta special-token policy, and subword limit.
The same implementation performs first-subword alignment, removes a final word split by
right truncation, builds tag/dependency/edit-script supervision, and composes lookup,
edit-script, lowercase, and identity lemma paths. This prevents a training checkpoint and
its exported runtime from silently interpreting the same token sequence differently.

`export_onnx.py` requires an explicit new candidate identity. It refuses
`grc-joint-v3`, validates the checkpoint metadata against the saved tokenizer, and writes a
schema-1 content manifest for each exported graph variant. Reusing an output directory with
stale artifact files is refused.
The published v3 archive retains its exact legacy manifest and preprocessing behavior.

## Reproducible training contract

`environment-lock.json` is an honestly labelled training-environment **template**, not a captured Colab
environment. It records `verification.state = "unverified-template"`,
`dependencies.scope = "direct-requirements"`, and `dependencies.complete = false`; the
validator therefore reports `ready_for_training = false` and refuses to bind a completed
run receipt to it. The nine package versions are candidate direct requirements whose
individual availability was checked, not a rehearsed combination or dependency closure.

The template's Python/Linux/libc values and CUDA 12.8 reference came from
`results/gpu-verify-2026-07-10.json`, a prior runtime/provider check for pyaegean 0.32.0,
not a training-environment capture. Driver, CUDA runtime, and cuDNN are deliberately not
frozen from that result. The allocation policy is G4-class RTX PRO 6000 Blackwell preferred,
with NVIDIA A100 fallback; the completed receipt must record the exact allocated GPU,
memory, compute capability, driver, CUDA runtime and Torch build, cuDNN, and precision.
Candidate capture inspects the live G4/A100 allocation and freezes its driver, CUDA runtime,
Torch CUDA build, and cuDNN versions; captured and validated locks require every field.

Before training, the live allocation must resolve the complete training dependency closure
and capture a normalized resolver manifest: resolver tool/version, direct roots, every
resolved distribution/version, and the manifest's file record and content digest. The
captured candidate uses `scope = "training-dependency-closure"` and `complete = true`.
Preflight compares every member of that closure but ignores unrelated Colab preinstalls;
`full-environment` remains available when whole-image identity is desired. Missing,
additional, or version-divergent closure members and absent/tampered resolver evidence fail
closed.

The transition is automated and content-addressed. `environment_definition_sha256` hashes
only the frozen Python/platform/dependencies/accelerator/backbone definition. A preflight
receipt binds that stable digest. Promotion adds the receipt digest and changes
`captured-candidate` to `validated`, then recomputes the document `lock_sha256` without
changing the definition digest; this avoids a self-hash cycle. CUDA runtime is queried from
the loaded `libcudart` API independently of the Torch CUDA build value. The GreBerta encoder
and tokenizer are already pinned to the immutable Git commit in `backbone.revision`;
training code and notebooks must pass that value as the Hugging Face `revision`, never
resolve mutable `main`. This prospective contract does not rebuild or change the
identity/evidence of `grc-joint-v3`.

Promotion revalidates the receipt's full observation: exact Python, platform, package
inventory, clean repository state, allowed non-null GPU allocation, and every frozen
accelerator version. An `ok` flag with missing or hand-authored observations is insufficient.

The standard-library-only validator performs no download, training, or model inference:

```bash
# Validate the template structure, immutable revisions, provenance, and lock digest.
# This succeeds structurally but reports ready_for_training=false.
python training/validate_reproducibility.py lock

# Normalize a complete pip --report (generated with the full intended roots/closure).
python training/validate_reproducibility.py resolver-manifest \
    --pip-report training/out/RUN/pip-report.json \
    --output training/out/RUN/resolver-manifest.json

# Verify the exact closure and capture the live platform plus approved CUDA allocation.
python training/validate_reproducibility.py capture \
    --resolver-manifest training/out/RUN/resolver-manifest.json \
    --output training/out/RUN/environment-candidate.json --repository-root .

# Compare closure, resolver evidence, frozen accelerator fields, allocation, and clean Git.
python training/validate_reproducibility.py preflight \
    --lock training/out/RUN/environment-candidate.json --repository-root . \
    --output training/out/RUN/preflight.json

# Bind the successful receipt without changing the stable environment-definition digest.
python training/validate_reproducibility.py promote \
    --lock training/out/RUN/environment-candidate.json \
    --preflight training/out/RUN/preflight.json \
    --output training/out/RUN/environment-validated.json

# After a run writes a completed receipt, verify its digest and re-hash every recorded
# lock, config, generated dataset, and output artifact.
python training/validate_reproducibility.py receipt training/out/RUN/run-receipt.json \
    --lock training/out/RUN/environment-validated.json --repository-root .
```

The exact schemas are `contracts/environment-lock.schema.json`,
`contracts/resolver-manifest.schema.json`, `contracts/preflight.schema.json`, and
`contracts/run-receipt.schema.json`. `reproducibility.py` supplies canonical hashing,
repository-relative file records, resolver normalization, capture/promotion, package/Git and
CUDA metadata capture, completed-receipt construction, and offline verification. A validated
lock requires a complete evidence-bound training closure or full environment. A completed
receipt must record the identical inventory, a clean repository commit, exact backbone and
corpus commits, command/config/seed, generated-data/output hashes, and allocated hardware.

## Running

The `training/` scripts are not in the wheel, so clone the repo and run them from the
clone. Training runs on a single GPU (the scripts auto-detect bf16/fp16); datasets fetch
the AGDT and UD folds to the cache on first build. The commands below describe the legacy
stage flow; they are not compliant with the reproducibility contract until the orchestrating
script or notebook reads `backbone.revision` from the lock and passes it to every
`from_pretrained` call.

```bash
# The candidate direct versions in the template are not yet a runnable environment lock.
git clone https://github.com/ryanpavlicek/pyaegean.git
python pyaegean/training/build_full_dataset.py
python pyaegean/training/train_full.py --model bowphs/GreBerta
python pyaegean/training/export_onnx.py \
    --checkpoint pyaegean/training/out/full/model \
    --model-id grc-joint-v4-dev1
python pyaegean/training/eval_full_ud.py \
    --checkpoint pyaegean/training/out/full/model --treebank perseus --split test
```
