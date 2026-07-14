# Methodology

This page explains how pyaegean turns source material into data, analysis, and
measured claims. It is meant to stand on its own: links point to detailed tables
and API entries, but the methodological contract is stated here.

This site is built from `main`. APIs identified as main-branch previews on the
[home page](index.md) may not yet be present in the latest PyPI release.

The central distinction is between three kinds of result:

| Register | What belongs in it | How to interpret it |
| --- | --- | --- |
| **Established** | Readings and facts taken from editions, lexica, catalogues, Unicode, and other named sources | A sourced claim that can be corrected when the source or transcription is wrong |
| **Measured** | Accuracy, calibration, coverage, and other quantities produced by a declared protocol | A reproducible observation with a population, metric, model or rule set, and evaluation procedure |
| **Exploratory** | Statistical leads over undeciphered material and generative AI output | A hypothesis for review, never a reading or ground truth |

These registers do different work. A statistically unusual Linear A pattern can
be measured correctly while its linguistic interpretation remains exploratory.
Likewise, a neural parse is a model prediction even when its aggregate accuracy
has been measured on a held-out corpus.

## Source data and editorial evidence

The common data model is built from `Corpus`, `Document`, `Token`, and
`Provenance` objects. Script-specific loaders convert source editions into that
model while retaining source and licence metadata. They preserve editorial
apparatus when the source format exposes it, and exports retain that information
where the target format can represent it.

Every token can carry one of four editorial states:

| State | Meaning |
| --- | --- |
| `certain` | The reading is treated as secure by the edition |
| `unclear` | The signs or letters are damaged but read |
| `restored` | Text has been supplied by an editor |
| `lost` | The surface is missing or illegible |

An analysis over restored text is therefore distinguishable from an analysis
over preserved text. The status does not make an editorial restoration true or
false; it keeps the evidential boundary visible.

Small, redistributable datasets may be bundled. Larger corpora, dictionaries,
and models are registered assets that are fetched on demand, checked against a
recorded SHA-256 digest, and stored in the user cache. A new asset is a new
versioned object rather than a mutation of a previously published one. Use
`aegean.data.versions()` to see the selected source, version, licence, URL, and
digest. The complete source and licence inventory is in the
[Data and Provenance guide](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)
and `NOTICE`.

## Architecture and reproducibility

The core has no heavy runtime dependency. Script packages depend on the core,
and analysis, I/O, visualization, databases, model adapters, and interfaces sit
above those packages. Optional dependencies are imported only when their feature
is activated. This keeps a plain `import aegean` independent of a model runtime,
network client, or dataframe library.

The default Greek analysis path is the zero-heavy-dependency baseline. Calls such
as `greek.use_treebank()`, `greek.use_tagger()`, and
`greek.use_neural_pipeline()` deliberately change the active backend. For
concurrent or independently configured work, `GreekPipeline()` creates an
isolated baseline and `GreekPipeline.neural()` creates an isolated neural
runtime. Its immutable configuration records the model, tokenizer,
normalization, segmentation policy, and execution provider. This makes the
meaning of "the pipeline" inspectable rather than implicit.

Randomized analytical methods accept or record their seed. An
`AnalysisReceipt` records the model and dataset identities, model-manifest
digest, tokenizer revision, runtime provider, and analyzed token counts. An
`EvalReceipt` records the data manifest and model id, evaluation fold, declared
protocol, and scores, with an extension field for additional metadata. Receipts
identify what was run and make mismatched artifacts visible; they do not by
themselves certify that a protocol or conclusion is sound.

## Greek analysis methods

Greek analysis separates normalization, tokenization, linguistic prediction,
and review. The baseline uses deterministic rules and curated tables. Optional
pure-Python backends add treebank lookup and trained tagger, lemmatizer, and
parser components. The neural backend supplies contextual UPOS, XPOS, UD
features, lemmas, and dependency trees from one shared encoder.

Annotated token records can identify the source of a lemma and whether review is
recommended. This is important because attested lookup, a neural edit script, a
rule, a user correction, and an unresolved identity fallback do not carry the
same evidence.

The `grc-joint` data entry currently resolves to the published
`grc-joint-v3` neural artifact. It uses a GreBerta encoder with task heads for
part of speech and morphology, a biaffine dependency parser, and an edit-script
lemma head with a training-only lookup. Dependency decoding uses a single-root
Chu-Liu/Edmonds maximum spanning tree, so non-projective trees are supported.
The `grc-joint-v2` fp32 artifact remains available from its archived release as
a reproducibility reference.

The v3 export uses weight-only int8 MatMulNBits for matrix weights, fp16
elsewhere, and fp32 activations. Quantization is accepted by comparing decoded
predictions and evaluation metrics against the fp32 artifact, not by assuming a
smaller file is equivalent. CPU throughput is hardware-dependent and is
reported only as illustrative performance, not as a portable benchmark.

### Evaluation protocol

Published Greek NLP accuracy is measured through the installed package, not by
reading values directly from a training framework. The canonical protocol is:

1. Fetch a pinned evaluation fold and verify its digest.
2. Run the selected artifact with ONNX Runtime's CPU execution provider, one
   sentence at a time. Sequential inference is canonical because batched
   inference is not prediction-identical on every fold.
3. Supply the gold `FORM` tokens when measuring linguistic heads. Separate
   end-to-end rows measure the package tokenizer from raw text.
4. Score with the pinned official CoNLL 2018 UD evaluator. UD lemma scoring is
   exact string match without extra normalization.
5. Report the fold, token count, metric definition, artifact identity, and where
   appropriate a sentence-bootstrap confidence interval.

The primary UD folds are pinned revisions of Ancient Greek Perseus (`331ddef`)
and Ancient Greek PROIEL (`a4ab8d4`). The official scorer is pinned by SHA-256
(`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`).
Perseus is the in-family literary evaluation. PROIEL is held out from training
and supplies an out-of-domain result with a different annotation tradition.
Additional folds test the New Testament, documentary papyri in regularized and
diplomatic orthography, a small tragedy sample, and Byzantine book epigrams.
These folds are reported separately because register, annotation scheme,
available labels, and sample size differ.

The full metric tables, exact commit and scorer digests, sample sizes,
confidence intervals, and citations are in [Benchmarks](benchmarks.md).

### Metric definitions

| Metric | What it measures |
| --- | --- |
| Tokens | Agreement between predicted and gold token spans |
| UPOS | Universal part of speech |
| XPOS | A treebank's language-specific tag |
| UFeats | Exact agreement on the full set of UD morphological features |
| Lemma | Exact agreement on the dictionary form under the fold's protocol |
| UAS | Correct syntactic parent, without the relation label |
| LAS | Correct syntactic parent and dependency relation |

XPOS values are not automatically comparable between treebanks. LAS and UFeats
also reflect annotation conventions as well as linguistic competence. For that
reason, pyaegean reports out-of-domain rows in their native scheme and separately
measures known convention differences instead of silently rewriting the gold.

### Train, development, and test separation

The joint model trains on the permitted AGDT, Gorman, and Pedalion material. UD
Perseus evaluation material is excluded by normalized form-sequence identity,
not merely by filename or corpus label. This matters because an aggregator can
contain the same sentence under a different provenance path. PROIEL is not a
training source. Additional folds are leakage-checked sentence by sentence;
this catches and excludes overlaps such as PapyGreek material also present in
Pedalion.

The development fold is used for early stopping, checkpoint selection, schedule
decisions, calibration, and export or quantization gates. A locked test fold is
not used to choose an architecture or threshold. The finished candidate is then
measured under the recorded protocol.

The pure-Python treebank baseline has a different epistemic status: its AGDT
lookup data includes the source of the UD Perseus test material. Its Perseus
lookup score is therefore an in-training upper bound, not a held-out
generalization result. Its PROIEL row is the more informative baseline comparison.

### Calibration and scope

Accuracy and confidence answer different questions. Where calibrated confidence
is available, expected calibration error and reliability information are
measured for the exact exported artifact. A high confidence value is still a
model estimate, not scholarly certainty, and it does not override editorial
status.

The evaluation suite deliberately exposes scope limits:

- The Perseus development and test material is prose, so it cannot establish
  equal performance on verse.
- The tragedy fold is small and must travel with its sample size and wide
  confidence intervals.
- PapyGreek distinguishes editorially regularized forms from diplomatic forms.
- The Byzantine DBBE material supplies tagging and lemma gold, not dependency
  trees.
- PROIEL uses features and dependency conventions that the Perseus-derived
  training scheme does not always express.
- The frozen v3 model learned an older apposition-label conversion. Corrected
  gold exposes that known error until a future model is trained on the corrected
  convention.

These are properties of the evidence, not exceptions to be normalized away.

## Aegean-script analysis

Linear B and the Cypriot syllabary are deciphered writing systems for Greek, so
their sign readings and Greek bridges can be sourced and tested as established
data. Linear A and Cypro-Minoan are undeciphered. pyaegean does not present a
phonetic convention, statistical association, clustering result, or generated
reading for those scripts as a decipherment.

The analytical layer works from observable units such as sign sequences,
positions, find-sites, document types, commodities, numerals, and editorial
states. Its methods include frequency and association measures, graph and
sequence analysis, positional and successor statistics, correspondence analysis,
clustering, metrological profiles, and accounting reconciliation.

Methods ported from the Linear A Research Workbench are tested against shared
golden fixtures derived from the original implementation. Statistical helpers
also have known-answer or property tests. This establishes what the code
computes. It does not establish a linguistic interpretation of the result.

Association measures are reported with their counts and assumptions. Where a
null model is used, its randomization preserves the declared structural feature,
such as word length or within-word sign membership, and records the seed and
number of samples. Small or sparse observations are not promoted to readings.
Accounting reconciliation checks whether written quantities satisfy an explicit
arithmetic convention; it does not infer the language of an account.

Cross-script phonetic distance is configurable because a working Linear A sound
value inherited from a shared Linear B sign is a convention, not a settled
Linear A reading. Results built on that convention remain exploratory and should
be tested under alternative schemes.

## Grounded translation and generative AI

`aegean.translate.translate()` combines local evidence with a selected language
model provider. The default Greek grounding mode builds morphology, idiom, and
syntactic evidence with the active Greek backend. If the neural pipeline is
active, that evidence uses its contextual predictions and dependency tree. If
it is not active, the baseline or other explicitly enabled backend is used.
`mode="full"` adds gated dictionary evidence, while `mode="none"` deliberately
requests ungrounded generation.

Grounding is not a guarantee that a translation is correct. It makes the local
evidence available and auditable. The returned `ExploratoryResult` preserves the
provider and grounding trace and is labeled exploratory. For Greek,
`verify=True` first produces an ungrounded draft and then checks it against the
local evidence, which reduces one source of prompt bias but can still inherit an
incorrect analysis. For Linear A, any generated translation is necessarily a
hypothesis because the script remains undeciphered.

## Claims, review, and reproduction

Published benchmark values are registered in
`training/results/published-claims.json`. Evidence files record the artifact and
protocol behind the values, and automated checks keep documentation echoes tied
to that registry. Corpus counts have a parallel registry. The registries prevent
a prose edit from silently changing a measurement; they do not replace rerunning
the relevant protocol when its model, data, scorer, or code changes.

Typical reproduction entry points are:

```bash
pip install "pyaegean[neural]"
```

```python
from aegean import data, greek

data.versions()                              # asset identities and digests
greek.use_neural_pipeline()                 # fetch grc-joint and activate its v3 artifact
greek.evaluate_on_ud("perseus", "test")    # in-family UD evaluation
greek.evaluate_on_ud("proiel", "test")     # out-of-domain UD evaluation
```

Some full-fold evaluations take hours on CPU. The detailed
[benchmark protocol](benchmarks.md) states which calls reproduce each row and
which evidence file records the published run.

Corrections should preserve the distinction between source transcription,
measured behavior, and interpretation. A source error is corrected with a
citation. A measured claim is challenged by reproducing its declared protocol.
An exploratory result is confirmed or refuted with additional evidence and
remains labeled exploratory until that review exists.
