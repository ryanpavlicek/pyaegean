# Methodology

This page describes how pyaegean turns source material into data, analysis, and
measured claims. It stands on its own: links lead to detailed tables and API
entries, but the methodological contract is stated here. It documents the
current PyPI release.

pyaegean keeps three kinds of result apart:

| Register | What belongs in it | How to read it |
| --- | --- | --- |
| **Established** | Readings and facts from editions, lexica, catalogues, Unicode, and other named sources | A sourced claim. Correct it when the source or transcription is wrong. |
| **Measured** | Accuracy, calibration, coverage, and other quantities from a declared protocol | A reproducible observation with a population, a metric, a model or rule set, and an evaluation procedure. |
| **Exploratory** | Statistical leads over undeciphered material, and generative AI output | A hypothesis for review, never a reading or ground truth. |

The registers do different work. A Linear A pattern can be measured correctly
while its linguistic interpretation stays exploratory. A neural parse is a model
prediction even after its aggregate accuracy has been measured on a held-out
corpus.

## Source data and editorial evidence

The data model is built from `Corpus`, `Document`, `Token`, and `Provenance`
objects. Script-specific loaders convert source editions into that model and
keep the source and licence metadata. They preserve the editorial apparatus when
the source format exposes it, and exports keep that information when the target
format can hold it.

Every token can carry one of four editorial states:

| State | Meaning |
| --- | --- |
| `certain` | The edition treats the reading as secure |
| `unclear` | The signs or letters are damaged but read |
| `restored` | An editor supplied the text |
| `lost` | The surface is missing or illegible |

An analysis over restored text is therefore distinct from an analysis over
preserved text. The state does not make an editorial restoration true or false.
It keeps the evidential boundary visible.

An import that exposes more than one spelling can also carry a typed
`TokenFormState`. `diplomatic` is the supplied or original form. `regularized`
and `normalized` are optional editorial or preprocessing forms. `model_input`
records the exact string sent to an analyzer, which is model provenance rather
than a statement about the source. Ordered segments keep track of which pieces
are certain, supplied, unclear, or lost, together with semantic source
references where the edition provides them. `pipeline_tokens()` selects a model
form deterministically and records both the selection and any normalization, so
a prediction traces back to its editorial evidence.

This typed state is available when a token-carrier EpiDoc source exposes the
matching choices or apparatus. The six currently hosted epigraphy and papyri
assets are still legacy aggregate-status data and do not yet provide
`TokenFormState`.

Small, redistributable datasets may be bundled. Larger corpora, dictionaries,
and models are registered assets. Each one is fetched on demand, checked against
a recorded SHA-256 digest, and stored in the user cache. A new asset is a new
versioned object, never a mutation of a published one. `aegean.data.versions()`
shows the selected source, version, licence, URL, and digest. The full source
and licence inventory is in the
[Data and Provenance guide](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)
and in `NOTICE`.

## Architecture and reproducibility

The core has no heavy runtime dependency. Script packages depend on the core.
Analysis, I/O, visualization, databases, model adapters, and interfaces sit
above them. An optional dependency is imported only when its feature runs. A
plain `import aegean` therefore stays independent of any model runtime, network
client, or dataframe library.

The default Greek analysis path is the zero-heavy-dependency baseline.
`greek.use_treebank()`, `greek.use_tagger()`, and `greek.use_neural_pipeline()`
change the active backend on purpose. For concurrent or separately configured
work, `GreekPipeline()` builds an isolated baseline and `GreekPipeline.neural()`
builds an isolated neural runtime. Its immutable configuration records the model,
tokenizer, annotation profile, normalization, backend segmentation contract, and
execution provider. The baseline contract is `pyaegean-punctuation-v1`. For the
published `grc-joint-v3` bundle the neural contract is `pretokenized`: the model
receives sentence-sized word lists and does not choose document boundaries.
Neither backend identity is the per-call document splitter. `sentence_policy` is
the separate choice that groups raw or typed text before analysis.

The public segmentation API is deterministic and source-preserving.
`greek.segment_text()` exposes the named `default`, `prose`, `verse`,
`inscription`, and `papyrus` policies as `SegmentationResult` objects with
ordered half-open source spans, stable policy IDs, and provenance. Built-in
rules claim no confidence. A caller-supplied segmenter may attach confidence
metadata; the runtime still validates the bounds, ordering, coverage, and policy
identity, and the tokenization path also rejects any span that bisects a token.
For pre-tokenized input, a complete contiguous run of explicit
`SourceAlignment.sentence_id` values takes precedence over policy and
punctuation; a partial or non-contiguous run is rejected. This keeps
edition-provided sentence structure intact instead of merging it with
heuristics. `greek.segment_sentences()` is an alias for `segment_text()`.

Randomized analytical methods accept or record their seed. An `AnalysisReceipt`
records what produced an analysis: the model, dataset, runtime-variant registry
and evidence identities, model-manifest digest, tokenizer revision, runtime
provider, and analyzed token count. An `EvalReceipt` records the data manifest,
model id, evaluation fold, declared protocol, and scores, plus an extension field
for extra metadata. A receipt identifies what ran and makes a mismatched artifact
visible. It does not by itself certify that a protocol or conclusion is sound.

## Greek analysis methods

Greek analysis keeps normalization, tokenization, linguistic prediction, and
review separate. The baseline uses deterministic rules and curated tables.
Optional pure-Python backends add treebank lookup and trained tagger,
lemmatizer, and parser components. The neural backend supplies contextual UPOS,
XPOS, UD features, lemmas, and dependency trees from one shared encoder.

An annotated token record can name the source of a lemma and whether review is
advised. This matters because an attested lookup, a neural edit script, a rule, a
user correction, and an unresolved identity fallback do not carry the same
evidence.

The `grc-joint` data entry currently resolves to the published `grc-joint-v3`
neural artifact. It uses a GreBerta encoder with task heads for part of speech
and morphology, a biaffine dependency parser, and an edit-script lemma head with
a training-only lookup. Dependency decoding uses a single-root Chu-Liu/Edmonds
maximum spanning tree, so it supports non-projective trees. The `grc-joint-v2`
fp32 artifact stays available from its archived release as a reproducibility
reference.

The v3 export uses weight-only int8 MatMulNBits for matrix weights, fp16
elsewhere, and fp32 activations. Quantization is accepted by comparing decoded
predictions and evaluation metrics against the fp32 artifact, not by assuming
that a smaller file is equivalent. CPU throughput depends on the hardware and is
reported only as an illustration, not as a portable benchmark.

### Evaluation protocol

Published Greek NLP accuracy is measured through the installed package, not read
from a training framework. The canonical protocol is:

1. Fetch a pinned evaluation fold and verify its digest.
2. Run the selected artifact with ONNX Runtime's CPU execution provider, one
   sentence at a time. Sequential inference is canonical because batched
   inference is not prediction-identical on every fold.
3. Supply the gold `FORM` tokens when measuring linguistic heads. Separate
   end-to-end rows measure the package tokenizer from raw text.
4. Score with the pinned official CoNLL 2018 UD evaluator. UD lemma scoring is
   exact string match with no extra normalization.
5. Report the fold, token count, metric definition, artifact identity, and,
   where appropriate, a sentence-bootstrap confidence interval.

The primary UD folds are pinned revisions of Ancient Greek Perseus (`331ddef`)
and Ancient Greek PROIEL (`a4ab8d4`). The official scorer is pinned by SHA-256
(`1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16`).
Perseus is the in-family literary evaluation. PROIEL is held out from training
and gives an out-of-domain result from a different annotation tradition. Further
folds test the New Testament, documentary papyri in regularized and diplomatic
orthography, a small tragedy sample, and Byzantine book epigrams. These folds are
reported separately because register, annotation scheme, available labels, and
sample size all differ.

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

XPOS values do not compare directly between treebanks. LAS and UFeats also
reflect annotation conventions, not only linguistic competence. For that reason
pyaegean reports each out-of-domain row in its native scheme and measures known
convention differences separately, rather than rewriting the gold.

### Train, development, and test separation

The joint model trains on the permitted AGDT, Gorman, and Pedalion material. UD
Perseus evaluation material is excluded by normalized form-sequence identity, not
by filename or corpus label, because an aggregator can hold the same sentence
under a different provenance path. PROIEL is not a training source. The
additional folds are leakage-checked sentence by sentence. PapyGreek adds a
stronger source-native work-identity guard before the sentence check: any
PapyGreek document whose Trismegistos identity appears in Pedalion's documentary
training source is excluded whole, and the retained sentences are then checked by
full and punctuation-stripped NFC form tuples against all three training sources.
This catches both cross-repository work copies and sentence copies filed under a
different provenance path.

Development material drives early stopping, checkpoint selection, schedule
decisions, calibration, and the export or quantization gates. A locked test fold
never chooses an architecture or a threshold. The finished candidate is then
measured under the recorded protocol.

Successor-model selection uses the checked-in multi-domain development manifest
instead of the historical v3 script's single `(LAS + lemma) / 2` field. A
content-addressed gate declares the exact decoder, the protected task and source
slices, the target weights, the operational limits, the promotion floor, and the
deterministic tie breakers before training. It gives Perseus and PapyGreek equal
total target weight, and it allows at most 0.01 percentage point of regression on
any protected development value, including per-token out-of-vocabulary lemma
accuracy. The selector requires the actual manifest, recomputes every score from
verified item counts, and rejects mismatched or unavailable evidence. It never
runs inference or reads a locked test fold. The final locked matrix stays a
one-shot release measurement after the candidate is frozen.

Exported and optimized successor artifacts pass a second content-addressed gate
bound to the same development manifest and selection policy. The conversion
commands stage their output and promote it only after they rebuild the reference
and candidate reports from the prediction artifacts. Framework export requires
exact decoded parity. Optimization checks every protected metric and every
decoded field, and must reduce the total artifact size. The gate also measures
the whole development population on CPU in sequential windowed mode, and records
latency, resident memory, artifact bytes, runtime versions, and provider
activation, probing CUDA when it is available. These are private development
qualification records, not published benchmark rows. They do not read a locked
test fold, and they do not imply that a smaller artifact is faster.

The pure-Python treebank baseline has a different epistemic status. Its AGDT
lookup data includes the source of the UD Perseus test material, so its Perseus
lookup score is an in-training upper bound, not a held-out generalization result.
Its PROIEL row is the more informative baseline comparison.

### Calibration and scope

Accuracy and confidence answer different questions. The typed confidence contract
(`TokenConfidence`, `SentenceConfidence`, and `ConfidenceResult`) records the
task, model, source path, optional domain, calibration hash, sample count, and
measured ECE and Brier support. It returns either a value in `[0, 1]` or an
explicit reason for being unavailable. The compatibility `upos_confidence` and
`lemma_confidence` fields do not become scoped just because typed output is
available. A high confidence value is still a model estimate, not scholarly
certainty, and it does not override editorial status.

Scope is resolved by the schema-2 `CalibrationRegistry`. An exact model, task,
source, and domain entry takes precedence, and only an entry marked broad may
serve as a fallback. `confidence_domain=` is a caller-supplied label, not a genre
detector. An `AbstentionPolicy` is likewise caller-owned: its thresholds produce
accept, review, or unavailable decisions and carry a canonical policy hash. No
threshold is bundled, and no out-of-domain claim is implied. A development-only
baseline now covers the available literary and documentary sources under a
deterministic source and task manifest, and records error anatomy, frequency and
OOV bands, long-input coverage, and official-score parity. That baseline freezes
the population for later gates. It does not retroactively create source-specific
calibrations or abstention thresholds; a dedicated fit and validation step is
still required before a calibration can ship, and the legacy aggregate
calibration is not generalized by label.

The evaluation suite exposes its scope limits on purpose:

- The Perseus development and test material is prose, so it cannot establish
  equal performance on verse.
- The tragedy fold is small and travels with its sample size and wide confidence
  intervals.
- PapyGreek separates editorially regularized forms from diplomatic forms.
- The Byzantine DBBE material supplies tagging and lemma gold, not dependency
  trees.
- PROIEL uses features and dependency conventions that the Perseus-derived
  training scheme does not always express.
- The frozen v3 model learned an older apposition-label conversion, so corrected
  gold exposes that known error until a future model trains on the corrected
  convention.

pyaegean reports these properties of the evidence rather than smoothing them
over.

### Annotation and domain profile methodology

Annotation and domain profiles record conventions and provenance. They do not
retrain the model, change the decoder, or add a score. `AnnotationProfile`
describes the output labels, relation scheme, segmentation, normalization,
mappings, reversibility or loss, and evidence. `DomainProfile` describes the
declared source scope and layer. It is not a genre detector and is never inferred
from `TextProfile` or `profile_text`. The caller-supplied confidence `domain` is
a separate calibration scope label.

Registry values are typed, immutable, canonically serialized, and identified by
SHA-256. A mapping that collapses labels, depends on lexical or contextual
information, omits source rows, or restructures dependencies is disclosed as
non-invertible rather than guessed. The canonical output convention stays the
supported inference path. The UD-PROIEL and Perseus/AGDT convention differences
are diagnostic, not a source-compatible output mode. The separate native-PROIEL
XML evaluation projection strips `#N` homograph suffixes and omits empty tokens;
exact UD-fold scoring does neither. PapyGreek's `orig` variant changes the
diplomatic `FORM` surface while keeping the regularized-layer gold analyses and
its documented fallbacks.

When documentary reconciliation, lemma rescue, or a paradigm resource contributes
to production neural output, receipt schema 4 binds the composed output profile
ID and SHA-256, the ordered post-processing identity, the runtime label, and the
registry and evidence digests. Receipt schemas 1 through 3 stay readable for the
current hosted evidence; the current pipeline configuration is schema 2. The
published `grc-joint-v3` identity is unchanged. This binding is provenance, not a
model or accuracy claim.

### Training reproducibility environment

The training environment files define an inference-free reproducibility contract.
The prospective `training/environment-lock.json` template and validator describe
the required direct dependencies, the immutable backbone resolution, the
repository, data, and config hashes, and the completed run-receipt fields. The
template is explicitly non-authorizing. The reviewed live records are published
separately under `training/results/a17-environment/`. They bind a single
nine-root resolver closure, CPython 3.12.13, the exact clean source state, and
one NVIDIA RTX PRO 6000 Blackwell Server Edition allocation with CUDA 12.8, Torch
CUDA 12.8, cuDNN 9.10.2, 96 GB-class VRAM, compute capability 12.0, and bf16
precision. Preflight re-observed the environment before promotion. Immutable
GreBerta resolution used repository metadata at the frozen commit and downloaded
no weights. The completed deterministic fixture receipt also binds the config,
input, output, hardware, and artifact digests without running the model. These
records validate the reproduction environment and the receipt path. They make no
model-quality, training, or performance claim.

A candidate joint-model checkpoint records one executable preprocessing contract:
the annotation profile, NFC normalization, pretokenized segmentation, tokenizer
specials and subword limit, alignment policy, supervision mappings, and lemma
composition order. Training and evaluation import the same dependency-free
implementation that package inference uses. Export validates those checkpoint
fields against the serialized tokenizer, requires a new model and asset identity,
and writes a content-addressed schema-1 manifest for each exported graph variant.
The published `grc-joint-v3` artifact keeps its exact legacy manifest, behavior,
and measurements.

A completed successor-model training receipt also binds the exact declarative
selection-gate file and its canonical digest. This keeps the policy that selected
a checkpoint attached to the run, instead of leaving it as an editable score in a
training script.

Artifact qualification binds each operational record back to the report's model
identity and complete bundle digest. An optimization source must match its
reference operational record exactly. A passing candidate receives a
deterministic archive; a rejected one stays private staging material. Runtime
labels such as `fast` or `compact` are separate decisions, earned from the
measured record rather than inferred from an ONNX numeric format.

The runtime-label registry freezes four names independently of any successor
artifact. `default` means the release-selected artifact and makes no operational
claim; it stays the exact `grc-joint-v3` asset. `fast`, `compact`, and the
optional `balanced` stay unavailable until a qualified optimization earns a
runtime-variant award. `compact` requires artifact bytes no greater than 90% of
the reference. `fast` requires five same-environment complete CPU runs, a median
latency no greater than 90% of the reference, and at least four candidate runs
below the reference median. `balanced` combines the compact bound with five runs
whose median latency and median peak resident memory are each no greater than
105% of the reference. These thresholds define the labels; they are not
task-accuracy claims. A public award receipt contains identities, operational
summaries, checks, and hashes. Development scores, predictions, rejected
candidates, and raw timing series stay private.

## Aegean-script analysis

Linear B and the Cypriot syllabary are deciphered writing systems for Greek, so
their sign readings and Greek bridges can be sourced and tested as established
data. Linear A and Cypro-Minoan are undeciphered. pyaegean does not present a
phonetic convention, a statistical association, a clustering result, or a
generated reading for those scripts as a decipherment.

The analytical layer works from observable units: sign sequences, positions,
find-sites, document types, commodities, numerals, and editorial states. Its
methods include frequency and association measures, graph and sequence analysis,
positional and successor statistics, correspondence analysis, clustering,
metrological profiles, and accounting reconciliation.

Methods ported from the Linear A Research Workbench are tested against shared
golden fixtures derived from the original implementation. The statistical helpers
also have known-answer or property tests. This establishes what the code
computes. It does not establish a linguistic interpretation of the result.

Association measures are reported with their counts and assumptions. When a null
model is used, its randomization preserves the declared structural feature, such
as word length or within-word sign membership, and records the seed and the
number of samples. A small or sparse observation is not promoted to a reading.
Accounting reconciliation checks whether written quantities satisfy an explicit
arithmetic convention; it does not infer the language of an account.

Cross-script phonetic distance is configurable because a Linear A sound value
inherited from a shared Linear B sign is a convention, not a settled Linear A
reading. A result built on that convention stays exploratory and should be tested
under alternative schemes.

## Grounded translation and generative AI

`aegean.translate.translate()` combines local evidence with a selected
language-model provider. The default Greek grounding mode builds morphology,
idiom, and syntactic evidence with the active Greek backend. If the neural
pipeline is active, that evidence uses its contextual predictions and dependency
tree; otherwise the baseline or another enabled backend is used. `mode="full"`
adds gated dictionary evidence, and `mode="none"` requests ungrounded generation
on purpose.

Grounding does not guarantee a correct translation. It makes the local evidence
available and auditable. The returned `ExploratoryResult` keeps the provider and
grounding trace and is labeled exploratory. For Greek, `verify=True` first
produces an ungrounded draft and then checks it against the local evidence, which
reduces one source of prompt bias but can still inherit an incorrect analysis.
For Linear A, any generated translation is necessarily a hypothesis, because the
script is undeciphered.

## Claims, review, and reproduction

Published benchmark values are registered in
`training/results/published-claims.json`. Evidence files record the artifact and
protocol behind each value, and automated checks keep the documentation echoes
tied to that registry. Corpus counts have a parallel registry. The registries
stop a prose edit from silently changing a measurement. They do not replace
rerunning the relevant protocol when its model, data, scorer, or code changes.

The shortest bounded evidence check runs from a clean source checkout:

```bash
python scripts/reproduce_review.py
```

It verifies the canonical review records by SHA-256 and reproduces a small,
project-authored offline fixture with no network access, model execution,
bytecode, or cache writes. Its receipt identifies the manifest, the deterministic
result, the package, the interpreter, and the Git state. This establishes
integrity and one deterministic regression result. It does not reproduce the
neural rows or amount to outside review. The [Independent review](review.md) page
maps that receipt to the model card, data card, limitations, and discrepancy
form.

The neural reproduction entry points are:

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

A correction should preserve the distinction between source transcription,
measured behavior, and interpretation. Correct a source error with a citation.
Challenge a measured claim by reproducing its declared protocol. Confirm or
refute an exploratory result with more evidence; it stays labeled exploratory
until that review exists.
