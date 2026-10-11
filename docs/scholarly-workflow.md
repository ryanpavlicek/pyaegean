# A scholarly workflow

The source edition, analyzer predictions, and a scholar's decisions answer different questions. Keep
their provenance available throughout the workflow.

## Preserve the reading before analyzing it

```python
from aegean import io

corpus = io.from_text("ὁ παῖς ἀκούει. Latin 123\n", doc_id="example")
document = corpus.documents[0]
assert document.source_text == "ὁ παῖς ἀκούει. Latin 123\n"
document.validate_source_alignment()
print([token.text for token in document.words])
```

The default import retains decoded text and character offsets. Non-Greek words,
numerals, and punctuation remain accessible as tokens but do not enter Greek word
counts. `token_view="words"` explicitly requests the older lossy import. File
decoding can remove a BOM; decoded-text reconstruction is not a promise of original
file bytes. Archive the source file and its checksum separately.

Perseus `source_text` is the selected TEI reading, with its documented whitespace
normalization and apparatus selection, rather than raw XML. Structured speaker
labels retain their role and speech context. EpiDoc imports preserve supported
typed editorial forms and numeric carrier `@value`; semantic XML export does not
preserve arbitrary XML layout or every attribute. JSON and SQLite preserve the
complete supported corpus state. Record edition, passage, license, source hash,
and `corpus.cite()` alongside the archive.

## Choose analysis explicitly

```python
from aegean import greek

pipeline = greek.GreekPipeline.neural()  # requires [neural]; fetches the pinned model
records = pipeline.analyze("ὁ παῖς ἀκούει.")
print(pipeline.config.to_dict())
```

The no-extra baseline provides limited rule/lookup analysis. Neural output remains
model prediction, including when a dependency tree is structurally valid. Preserve
configuration and analysis receipts with exported results. Use explicit long-input
policies and inspect coverage; a partial annotation is not a complete analysis.
Confidence flags do not currently establish independently calibrated error rates
for every genre, period, or field. Register differences matter: regularized and
diplomatic papyrus readings can produce different analyses.

## Review the evidence needed for the claim

Search, vocabulary exploration, provisional translation, and exploratory statistics
can proceed without a review gate. Before relying on an individual reading, review
the relevant lemma, POS, morphology, or dependency against its context and edition.
For aggregate research, audit a sample of ordinary outputs as well as flagged ones,
and measure precision/recall against independently annotated material.

The [review workflow](review.md) supports per-field acceptance, correction,
deferral, and rejection. Accepting an unchanged lemma is a real recorded decision;
it does not certify syntax or lexical sense. Reanalysis marks replaced decisions
stale. CSV snapshot checks do not independently bind identical values to a model
revision, so regenerate review tables after replacing an analysis.

## State the population being counted

```python
surface = corpus.word_frequencies(view="surface")
normalized = corpus.word_frequencies(view="normalized")
secure_lemmas = corpus.word_frequencies(view="lemma", statuses=["certain"])
print(secure_lemmas.metadata, secure_lemmas.cite())
```

Lemma counts use existing annotations and exclude missing lemmas. Normalization
preserves accents and breathings; surface spelling remains accessible. Token and
document frequency have different denominators. Compare results with and without
restored or unclear readings when those choices affect the argument. See
[research semantics](research-semantics.md) for exact rules and account arithmetic.
An arithmetically exact total does not validate a damaged reading or a metrological
interpretation. Map coordinates need archaeological identity checks as well as
distance checks.

## Compare translations with visible evidence

```python
from aegean import ai, translate

client = ai.get_client("openrouter", model="your/vendor-model-id")
result = translate.translate(
    document.source_text,
    greek_pipeline=pipeline,
    mode="morphology",
    grounding_failure="strict",
    client=client,
)
print(result.labeled())
print(result.trace())
```

Configure `OPENROUTER_API_KEY` securely. `ai.annotation_evidence(document.tokens)`
can provide existing field-level decisions as supplemental `grounding`; use
`source_annotated=True` only when those annotations actually come from the edition.
Prediction, source annotation, current human decision, and unclassified evidence
remain distinguishable in the prompt and trace.

Compare `mode="none"`, baseline morphology, neural morphology, and `verify=True`
with the same model and passage. Verification asks the same provider to inspect
its draft using the evidence; it is not independent scholarly review. Checking
stays optional. With `verify=True`, `result.draft` retains the original reading,
notes and provenance. Structured `result.data` separates uncertainty from reported
changes and their reasons; neither is a human acceptance decision. Use
`style="annotated"` to display the notes, or `style="concise"` for a short reading
with the details retained in JSON and `trace()`. A malformed provider response is
marked unstructured and kept verbatim; unavailable notes are not treated as an
empty list of concerns. See [the translation guide](api/translate.md).

Keep complete
outputs, prompts, model identifiers, grounding, failures, latency, and cost. Blind
the condition labels for raters and assess meaning, syntax, lexical sense, omitted
or invented content, treatment of uncertainty, and readability separately. Use
more than one qualified reader and adjudicate disagreements. Familiar literary
passages can measure memorization as well as translation; include independently
selected material and constructed minimal pairs, labeled as such.

Treat textual variants as distinct readings unless the edition supports a
relationship between them. The prompt asks the model to avoid inventing a
revision history, author identity or bibliographic attribution. This instruction
does not verify its claims: check supporting evidence before citing them.

Operational tests establish preservation, routing, arithmetic, and interface
behavior. They cannot establish translation accuracy or replace independent gold
for dialect, period, meter, accentuation, phonology, or textual criticism.
