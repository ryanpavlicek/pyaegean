# aegean.greek

::: aegean.greek

## Streaming neural sentence analysis

`iter_analyze_sentences(sentences, batch_size=None)` is the bounded-memory API for
an iterable of already tokenized Greek sentences. It captures the active neural
backend, opt-in documentary state, and (when requested) confidence calibration when
called, pulls and yields one sentence at a time by default, preserves
source order and each result's `AnalysisReceipt`, and applies synchronous
backpressure. A positive `batch_size` holds at most one transactional chunk; a
failed chunk yields nothing, while earlier yielded results remain valid.

`analyze_sentences(...)` is the compatibility collector over that engine and still
returns a complete list. `GreekPipeline.iter_analyze_sentences(...)` provides the
same iterator against an isolated instance. These APIs do not make raw-text
`pipeline()`, corpus annotation, or CoNLL-U serialization streaming. Batching is a
throughput option; the published benchmark protocol remains sequential CPU inference.

## Sentence-policy registries

The facade also exports two immutable mappings that document the supported rule
contracts:

- `POLICY_IDS` maps each named policy to its stable identity. It also contains the
  `explicit` identity used when complete source `sentence_id` runs supply boundaries.
- `POLICY_RULES` maps the five inferred policies (`default`, `prose`, `verse`,
  `inscription`, and `papyrus`) to their plain-language rule descriptions.

Use these mappings for inspection and provenance; do not modify or interpret a rule
identity as a measured confidence value.

## Typed confidence and abstention

`pipeline()`/`pipeline_tokens()` and `GreekPipeline.analyze()` accept the additive
`confidence_domain=` and `confidence_policy=` arguments when confidence is requested.
Their `TokenRecord` results carry `TokenConfidence`/`SentenceConfidence` values with task,
source-path, domain, calibration, and explicit unavailable-reason fields. `AbstentionPolicy` thresholds are
caller-supplied and hashed into each decision; no default threshold or automatic OOD claim
is provided. A schema-2 `AnalysisReceipt` records calibration and policy hashes when those
artifacts participate in analysis.

For development data, `fit_temperature(logits, correct)` fits a top-1 temperature and
`fit_logit_affine(probs, correct)` fits monotone `(slope, intercept)` parameters for a
logit-affine `CalibrationEntry`. Both are parameter-fitting helpers only: they do not select
domains, thresholds, or release evidence.
