# training/ — Greek NLP model training

Training code for the Greek NLP models. Nothing in this directory ships in the wheel;
trained artifacts are published as GitHub release assets and fetched to the cache, never
bundled. The evaluation protocol and all benchmark numbers are in `docs/benchmarks.md`.
The public [independent review kit](../review/README.md) provides the one-command
evidence receipt plus the shipped model and data cards.

## Shipped model

The shipped release asset is **`grc-joint-v3`**: the combined-corpus checkpoint quantized
weight-only (int8 MatMulNBits, block 128, symmetric on the MatMul weights; fp16 elsewhere,
including the word-embedding table; activations kept fp32), ~173 MB, produced from the fp32
`grc-joint-v2` checkpoint by `quantize_grc_joint.py`. The fp32 `grc-joint-v2` (~518 MB) is
retained for reproducibility. One GreBerta encoder serves UPOS, XPOS, UD FEATS, dependency
trees, and lemmas. On the UD Ancient Greek (Perseus) test fold it scores lemma 94.27 /
UAS 90.24 / LAS 85.65 / UPOS 97.02 / UFeats 96.03 / XPOS 93.47, and lemma 90.51 on PROIEL
(out of domain). The recorded decoder-v1 quantization comparison was lossless within ±0.02
on its measured metrics. Five historical decoder-v1 training seeds averaged LAS
85.58 ± 0.10 / UAS 90.15 ± 0.12; that is training-stability evidence, not decoder-v2
replication.

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

`build_full_dataset.py --with-extras` reads an exact, commit-pinned source inventory and
applies `canonicalization-policy-v2.json`. The policy records each corpus's annotation
profile and the deliberately narrow source-to-canonical corrections. Every output sentence
keeps its source identity and token ids plus a SHA-256 binding to its original source labels;
the pinned source remains the authority for recovering those labels.

Each build also writes `training-data-manifest.json`, which binds the policy, every source
file, every generated file, split counts, overlap exclusions, and aggregate label
transformations by SHA-256. The builder verifies that manifest before it reports success.
This makes a corrected training input reviewable and reproducible without publishing model
selection results or reading the locked test labels.

## Development evaluation contract

`development_manifest.py`, `run_development_evaluation.py`, and
`development_report.py` define the model-selection and regression-gate population without
touching a locked test fold. The checked-in
`results/development-source-manifest.json` is a **non-performance** source contract: 1,344
unique items (1,030 Perseus and 314 PapyGreek), covering 26,610 tagging tokens and 21,622
parsing tokens. Every item records its source, work/document/sentence identity, tasks,
annotation profile, frequency/OOV context, content digest, and exposure status.

The manifest builder rejects source, work, document, sentence-form, task, profile, and
locked-fold leakage. It also records unavailable domains explicitly: no eligible
document-disjoint development source currently exists for tragedy/poetry, New Testament,
Byzantine Greek, or diplomatic PapyGreek. Absence is not filled with a locked or
training-seen substitute.

The live runner activates `grc-joint-v3`, uses CPU-sequential inference and complete-word
overlap windows, and verifies that every selected gold token receives a prediction. Its
report recomputes UPOS, XPOS, UFeats, lemma, UAS, LAS, and official CLAS F1, then requires
exact parity with the CoNLL-2018 evaluator. Predictions, performance values, error samples,
and development reports remain private and gitignored; only the source manifest is public.
This freezes an auditable gate population without turning development performance into a
published benchmark claim.

## Declarative candidate selection

`model-selection-gate-v3.json` replaces an implicit checkpoint score with a frozen,
content-addressed policy for successor-model experiments. It is bound to the checked-in
development manifest and requires the package's sequential, complete-window, single-root MST
decoder. The reference policy protects UPOS, XPOS, UFeats, lemma, UAS, LAS, and CLAS globally
and on both available sources, plus per-token OOV-lemma accuracy (the `lemma@oov-token` band).
Earlier gate versions stay checked in as historical evidence. Each protected value may fall no more
than 0.01 percentage point below its baseline. Literary Perseus and documentary PapyGreek each
receive half of the target weight, so a gain on the larger source cannot silently erase a loss
on the smaller one.

`model_selection.py` consumes the actual verified manifest, one baseline descriptor, and one
or more candidate descriptors. Each descriptor embeds a verified development report and binds
the selection-gate and completed training-receipt digests plus measurements under the gate's
named operational profile. The selector recomputes every score from integer item counts,
rejects manifest/decoder/profile mismatches and hard regressions, forms Pareto fronts across
all target task/source values, then applies only the recorded deterministic tie breakers. It
does not load a model, run inference, or inspect a locked test fold.

```bash
python training/model_selection.py \
    --gate training/model-selection-gate-v3.json \
    --manifest training/results/development-source-manifest.json \
    --baseline training/out/selection/baseline.json \
    --candidate training/out/selection/candidate-seed-1.json \
    --candidate training/out/selection/candidate-seed-2.json \
    --output training/out/selection/result.json
```

The output records every rejection and the deterministic ranking under the exact gate digest;
it remains development-only evidence. The old `(LAS + lemma) / 2` local field in
`train_full.py` belongs to the historical v3 recipe and is not a valid successor-model
selection or release gate.

## Integrated artifact qualification

`artifact-qualification-gate-v3.json` binds export and optimization to the development
manifest and current selection policy. `export_onnx.py` and `quantize_grc_joint.py` build in a
private staging directory and create the final directory and deterministic archive only after an
isolated qualification process returns a reproducible `qualified=true` decision. Failed candidates
remain staged working material and are never presented as release artifacts.

The v1 gate files remain available only to verify evidence created under the earlier decoder.
New evaluations and qualification commands use the v2 gates and corrected decoder identity.

Qualification rebuilds both development reports from gold plus their prediction artifacts. It
checks every protected task/source/OOV metric and separately compares decoded UPOS, XPOS, UFeats,
lemma, head, and dependency-relation values, so compensating errors cannot disappear inside an
aggregate score. Framework export requires exact decoded parity. Artifact optimization retains the
selection-policy regression ceilings, limits disagreement in every output field, and must reduce
total artifact bytes.

The operational record measures CPU-sequential, complete-window inference over the whole
development manifest after warm-up. It records latency per 100 scored tokens, total and model bytes,
resident memory, runtime versions, and the active provider. CPU is mandatory. CUDA is probed when
installed; an absent optional provider is recorded without failing, while an installed provider
must run and remain inside the same decoded-output limit. The absolute size, latency, and memory
ceilings are safeguards, not performance claims. In particular, weight-only quantization is not
called fast merely because it is smaller; runtime labels require the separate award below.

Reference and candidate preprocessing/output contracts must match. Runtime evidence is bound to
the report's model identity and complete artifact digest, and optimization additionally requires
the supplied source artifact to match the reference operational record exactly. Candidate reports,
predictions, timings, and rejected artifacts stay in the gitignored `training/out/` tree. The gate
does not read a locked test fold and does not change the published `grc-joint-v3` artifact or its
measurements.

For a frozen candidate, the command sequence is:

```bash
# First produce a verified development report and predictions for the trained PyTorch candidate.
python training/export_onnx.py \
    --checkpoint training/out/full/model \
    --model-id grc-joint-v4-candidate-fp32 \
    --perseus-dev-source training/data/grc_perseus-ud-dev.conllu \
    --papygreek-tagging-source training/data/papygreek-dev-tagging.conllu \
    --papygreek-parse-source training/data/papygreek-dev-parse.conllu \
    --reference-report training/out/reference/development-report.json \
    --reference-predictions training/out/reference/predictions-SHA256.json

# Optimize only the fp32 artifact that produced the supplied operational evidence.
python training/quantize_grc_joint.py \
    training/out/export/grc-joint-v4-candidate-fp32 \
    --model-id grc-joint-v4-candidate-compact \
    --perseus-dev-source training/data/grc_perseus-ud-dev.conllu \
    --papygreek-tagging-source training/data/papygreek-dev-tagging.conllu \
    --papygreek-parse-source training/data/papygreek-dev-parse.conllu \
    --reference-report training/out/qualification/grc-joint-v4-candidate-fp32-export/development-report.json \
    --reference-predictions training/out/qualification/grc-joint-v4-candidate-fp32-export/predictions-SHA256.json \
    --reference-operational training/out/qualification/grc-joint-v4-candidate-fp32-export/operational-evidence.json
```

The source paths and content-addressed prediction filename are examples; use the exact private
artifacts emitted by the frozen run.

## Runtime variant awards

`runtime-variant-policy-v1.json` freezes the operational meaning of `fast`, `compact`, and
optional `balanced`; `default` is the release-selected artifact and makes no speed or size
claim. `runtime_variant_award.py` accepts only a passing `optimization` qualification and
the exact complete-CPU operational records bound to it. It checks artifact identity, manifest,
development population, provider, environment, repetition count, and every label threshold,
then writes a deterministic content-addressed award.

```bash
python training/runtime_variant_award.py \
    --label compact \
    --qualification training/out/qualification/candidate/qualification-report.json \
    --reference-operational training/out/reference/operational-evidence.json \
    --candidate-operational training/out/qualification/candidate/operational-evidence.json \
    --output training/out/qualification/candidate/compact-award.json
```

`compact` uses one deterministic size pair. `fast` and `balanced` require exactly five
same-environment records for both reference and candidate, supplied by repeating the two
operational options. The tool emits operational summaries and hashes, not development task
scores, predictions, rejected artifacts, or raw timing series. A report does not activate a
label by itself: a released artifact must also receive its own immutable dataset key and asset
pin, and the package registry must bind the exact qualification, award, bundle, and asset
digests. Until then, `fast`, `compact`, and `balanced` remain reserved and unavailable.

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

`environment-lock.json` is an honestly labelled prospective training-environment **template**, not the
captured Colab environment. It records `verification.state = "unverified-template"`,
`dependencies.scope = "direct-requirements"`, and `dependencies.complete = false`; the
validator therefore reports `ready_for_training = false` and refuses to bind a completed
run receipt to it. The nine direct versions were subsequently resolved together in the
reviewed live capture, but the reusable template remains separate from that environment-specific
validated lock and complete transitive closure.

The template's Python/Linux/libc values and CUDA 12.8 reference came from
`results/gpu-verify-2026-07-10.json`, a prior runtime/provider check for pyaegean 0.32.0,
not a training-environment capture. Driver, CUDA runtime, and cuDNN are deliberately not
frozen from that result. The allocation policy is G4-class RTX PRO 6000 Blackwell preferred,
with NVIDIA A100 fallback; the completed receipt must record the exact allocated GPU,
memory, compute capability, driver, CUDA runtime and Torch build, cuDNN, and precision.
Candidate capture inspects the live G4/A100 allocation and freezes its driver, CUDA runtime,
Torch CUDA build, cuDNN, exact device names/count, per-device VRAM and compute capability,
and the selected bf16/fp16 precision; captured and validated locks require every field.

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

Promotion revalidates the receipt's full observation against a fresh live probe: exact
Python, platform, all nine direct roots and their resolved closure, the required clean source
commit, allowed non-null GPU allocation, and every frozen accelerator field. An `ok` flag with
missing or hand-authored observations is insufficient.

The live environment capture is complete. The reviewed normalized records in
`results/a17-environment/` contain the resolver manifest, successful preflight, validated lock,
immutable GreBerta metadata proof, deterministic fixture output and completed-run receipt, plus a
content-addressed summary. The capture used CPython 3.12.13 on one NVIDIA RTX PRO 6000 Blackwell
Server Edition, CUDA runtime and Torch CUDA 12.8, cuDNN 9.10.2, compute capability 12.0, bf16,
and a 96 GB-class allocation. The source workflow used an external venv, bootstrapped pinned pip
without relying on `ensurepip`, and resolved all nine direct roots in one operation. It downloaded
no model weights and performed no training, inference, or linguistic evaluation. The raw pip
report and full operator archive are retained privately because package metadata contains a large
set of unrelated project URLs; no credentials or credential-like values were found in review.

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
    --expected-commit "$CANDIDATE_SHA" \
    --output training/out/RUN/preflight.json

# Bind the successful receipt without changing the stable environment-definition digest.
python training/validate_reproducibility.py promote \
    --lock training/out/RUN/environment-candidate.json \
    --preflight training/out/RUN/preflight.json \
    --output training/out/RUN/environment-validated.json \
    --repository-root . --expected-commit "$CANDIDATE_SHA"

# After a run writes a completed receipt, verify its digest and re-hash every recorded
# lock, config, generated dataset, and output artifact.
python training/validate_reproducibility.py receipt training/out/RUN/run-receipt.json \
    --lock training/out/RUN/environment-validated.json --repository-root .

# After inspecting the raw archive, summarize only normalized records for publication.
python training/a17_colab.py reviewed-summary \
    --evidence-dir training/out/RUN --repository-root . \
    --output training/out/RUN/reviewed-evidence-summary.json
```

The exact schemas are `contracts/environment-lock.schema.json`,
`contracts/resolver-manifest.schema.json`, `contracts/preflight.schema.json`,
`contracts/run-receipt.schema.json`, `contracts/run-receipt-v2.schema.json`,
`contracts/model-selection-gate.schema.json`, `contracts/backbone-resolution.schema.json`,
and `contracts/evidence-summary.schema.json`. `reproducibility.py` supplies canonical hashing,
repository-relative file records, resolver normalization, capture/promotion, package/Git and
CUDA metadata capture, completed-receipt construction, and offline verification. A validated
lock requires a complete evidence-bound training closure or full environment. A completed
receipt must record the identical inventory, a clean repository commit, exact backbone and
corpus commits, command/config/seed, generated-data/output hashes, allocated hardware, and the
selection gate's file and canonical digest. New model-training receipts use schema 2. Schema 1
remains readable only for the already-reviewed inference-free environment fixture.

## Running

The `training/` scripts are not in the wheel, so clone the repo and run them from the
clone. Training runs on a single GPU (the scripts auto-detect bf16/fp16); datasets fetch
the AGDT and UD folds to the cache on first build. The commands below describe the historical
v3 stage flow only. They are not the v4 orchestration and are not compliant with the current
reproducibility and selection contracts until an orchestrating script or notebook reads
`backbone.revision` from the lock, passes it to every `from_pretrained` call, writes a schema-2
training receipt, and applies the frozen development gate. The test command is shown only to
reproduce the historical recipe; a new candidate must not use a locked test fold for selection.

```bash
# The candidate direct versions in the template are not yet a runnable environment lock.
git clone https://github.com/ryanpavlicek/pyaegean.git
python pyaegean/training/build_full_dataset.py --with-extras
python pyaegean/training/train_full.py --model bowphs/GreBerta
python pyaegean/training/eval_full_ud.py \
    --checkpoint pyaegean/training/out/full/model --treebank perseus --split test
```
