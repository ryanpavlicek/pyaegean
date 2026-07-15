# Model card: `grc-joint-v3`

## Summary

`grc-joint-v3` is the currently shipped optional Ancient Greek neural artifact. A
single GreBerta encoder serves UPOS, XPOS, Universal Dependencies features,
dependency parsing, and lemmatization. The inference bundle uses weight-only int8
MatMulNBits for matrix weights, fp16 elsewhere, and fp32 activations. It is fetched
to the user's cache and is not included in the Python wheel.

The stable runtime label `default` resolves to this exact artifact. `fast`, `compact`,
and `balanced` are reserved and unavailable unless a future artifact earns them under
the checked-in measurement policy. The canonical identity and hashes are in
[`neural-runtime-variants.json`](../src/aegean/data/bundled/greek/neural-runtime-variants.json).

## Intended use

- Contextual analysis of tokenized Ancient Greek: part of speech, morphology,
  dictionary headword, and dependency structure.
- Research assistance where users inspect predictions against the source and the
  stated domain and annotation limits.
- Reproducible evaluation through pyaegean's public package API and recorded
  benchmark protocol.

The model is not intended to establish a unique philological reading, replace an
edition or expert annotation, translate undeciphered scripts, or provide calibrated
confidence outside the scope carried by the returned confidence record.

## Architecture and output

| Component | Function |
| --- | --- |
| GreBerta encoder | Shared contextual word representation |
| Joint tagging heads | UPOS, treebank-specific XPOS, and UD feature bundles |
| Biaffine parser | Dependency arcs and relation labels |
| Single-root Chu-Liu/Edmonds decoder | Complete, potentially non-projective dependency tree |
| Edit-script lemma head plus train-only lookup | Composed dictionary headword |

Inference is ONNX-based and does not require PyTorch. Gold-token evaluation uses
pretokenized input, sequential CPU inference, complete-word overlap windows, and the
pinned CoNLL 2018 evaluator. See [Methodology](../docs/methodology.md) for the full
runtime and evaluation account.

## Training and evaluation

Training uses permitted AGDT, Gorman, and Pedalion material after exclusion of the
UD Perseus development and test sentences by normalized form-sequence identity.
UD Perseus development material is used for model development. Its locked test fold
is report-only after the candidate is frozen. PROIEL is not a training source and is
reported separately as out-of-domain evidence. See the [data card](DATA_CARD.md) for
licenses, partitions, and additional evaluation domains.

The authoritative measured values, sample sizes, protocols, confidence intervals,
and comparison caveats are in [`docs/benchmarks.md`](../docs/benchmarks.md). The
machine-readable registry is
[`published-claims.json`](../training/results/published-claims.json). This card does
not duplicate that registry because a copied number can drift from its evidence.

## Quantization and artifact identity

The model was derived from the fp32 `grc-joint-v2` checkpoint. Weight-only
quantization was accepted by comparing decoded predictions and metrics with the fp32
reference. A full-int8-activation attempt failed its quality gate and was rejected.
The historical conversion and size evidence is
[`v3-quantize-report.json`](../training/results/v3-quantize-report.json).

The archive is approximately 173 MB. Its content identity is not its filename:
reviewers should use the asset and bundle-manifest SHA-256 values in the runtime
registry. The [one-command review](README.md) hashes the registry and supporting
evidence but intentionally does not download or execute the model.

## Limitations and risks

- Results are strongest on in-family literary prose and weaker or convention-capped
  in some other registers and treebanks.
- XPOS, UFeats, and dependency labels can differ because annotation traditions differ,
  not only because linguistic predictions differ.
- The shipped v3 model learned an old AGDT conversion in which bare apposition could
  become `cc`; the corrected converter affects future training, not these frozen weights.
- Calibration is empirical and scoped. It is not a universal probability of scholarly
  correctness.
- Model output can inherit errors and representational limits from its annotated data.
- Tokenization and source normalization remain separate decisions from the model heads.

The maintained, fuller register is the wiki's
[Limitations](https://github.com/ryanpavlicek/pyaegean/wiki/Limitations) page.

## License and citation

The model bundle is CC BY-SA 4.0 because its training data carries ShareAlike terms.
The package code is Apache-2.0. Artifact citation and upstream attributions travel in
the fetched bundle manifest and package notices; consult [`NOTICE`](../NOTICE) and
[`training/README.md`](../training/README.md) before redistribution.

## Review status

The component datasets and methods rest on outside scholarship, but pyaegean's model,
integration, and reported conclusions have not undergone formal external scholarly
peer review or an external software audit. Independent reproduction and critical
findings are invited through the [review kit](README.md).
