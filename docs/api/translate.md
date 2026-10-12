# aegean.translate

## Translation, notes, and optional checking

```python
from aegean import ai, greek, translate

client = ai.get_client("openrouter", model="openai/gpt-5.4")
pipeline = greek.GreekPipeline.neural()
result = translate.translate(
    "τὸν παῖδα ὁ ἀνὴρ ὁρᾷ.",
    greek_pipeline=pipeline,
    grounding_failure="strict",
    style="annotated",       # default; "concise" keeps the displayed reading short
    verify=True,             # optional: two model calls, not independent human review
    client=client,
)
print(result.text)            # translation only when the response is structured
print(result.labeled())       # exploratory label and model-reported notes
print(result.data["uncertainties"])
print(result.data["changes"]) # before, after, reason, evidence for each reported change
print(result.draft.text)      # initial ungrounded draft, retained with its own notes
result.to_json("translation.json")
```

Set `OPENROUTER_API_KEY` securely before a live call. The neural model requires
the `[neural]` extra and model activation; OpenRouter requires `[openrouter]`.
The same styles are supported by the lower-level `ai.translate` and
`ai.verify_translation` functions. Checking remains off by default.

Supply surrounding Greek, speaker labels, and cited editorial notes with
`source_context`, separately from the passage being translated:

```python
from pathlib import Path

context = Path("source-context.txt").read_text(encoding="utf-8")
result = translate.translate(
    "τὸν παῖδα ὁ ἀνὴρ ὁρᾷ.", source_context=context,
    greek_pipeline=pipeline, verify=True, client=client,
)
assert result.data["source_context"] == context
assert result.draft.data["source_context"] == context
```

Both calls receive the same context; only the target passage is analyzed and
translated. Context is fenced as source material, with instructions to use it
for interpretation rather than follow directions embedded in it. Supply source
citations and distinguish editorial notes from quoted Greek. Surrounding text
is not fetched automatically by these string-based APIs.

`ai.translate` and `ai.verify_translation` accept the same keyword. Checking a
saved `ExploratoryResult` inherits its recorded context when the keyword is
omitted or `None`. A different explicit context raises `ValueError` before any
provider call; start a new translation to change the context of an existing
context-bound draft. A string draft or older result without recorded context
can receive explicit context. Supplied strings, including whitespace, survive
JSON round trips and traces exactly.

Structured responses separate the final reading from uncertainty and change
reports. `result.data["raw_response"]` preserves the exact provider text.
`result.draft` preserves the initial result, including provider/model, prompt
version and notes. JSON export/reload keeps both stages; `result.trace()` shows
the draft, notes, changes and supplied evidence. A change reason is a model's
explanation, not a recorded human review decision or verified citation.

Plain JSON and a single complete Markdown JSON fence are accepted locally;
surrounding prose or multiple response blocks are not silently discarded.
If a provider returns malformed JSON or the wrong field types, no extra paid
repair call is made. The raw answer remains in `result.text` and
`data["raw_response"]`; `data["format_status"]` is `"unstructured"`, and the
unavailable structured fields are `None`. This means notes were not successfully
extracted, not that no uncertainties or changes exist. Check `format_status`
before processing these fields automatically. Older saved results may have
`data=None` and no draft.

For a structured draft and final answer, `data["text_changed"]` records an exact
text comparison. If the wording differs but the model reports an empty changes
array, `data["change_report_status"]` flags `"unreported_text_difference"` and
the labeled output calls attention to it. This comparison does not judge the
meaning or certify the reported reasons. A string draft, legacy/unstructured
draft, or unstructured final is marked `"not_comparable"` for this local check.
The same applies if a retained draft's text has been edited independently of its
structured translation field; `comparison_note` explains that mismatch.

Concise output retains notes in JSON and the trace, and signals that notes are
available. Use annotated output when reading the explanation alongside the
translation. Plain `result.text` is intentionally just the reading for structured
responses; use `labeled()` when displaying a result to retain its status.

```bash
aegean ai translate 'τὸν παῖδα ὁ ἀνὴρ ὁρᾷ.' \
  --provider openrouter --model openai/gpt-5.4 \
  --greek-backend neural --verify --source-context-file source-context.txt \
  --style concise --output translation.json

aegean ai translate 'τὸν παῖδα ὁ ἀνὴρ ὁρᾷ.' \
  --provider openrouter --model openai/gpt-5.4 \
  --greek-backend neural --verify --style annotated --trace --output translation.txt
```

Translation `.txt` files automatically include the audit trace, even without
`--trace`, so a saved concise reading does not discard its notes or draft.
`--trace` also displays these details on the terminal. These commands
make separate paid requests; JSON is the preferred reusable archive.
Use `--source-context` for inline context or `--source-context-file` for a UTF-8
file; the two options are mutually exclusive.

Translation and checking use a 2,048-token output allowance per call. Set
`max_tokens` in Python or `--max-tokens` on the CLI for longer passages or more
detailed notes. The value must be a positive integer. It is a maximum, not a
request to fill that space; provider truncation can still occur. The package
preserves malformed or incomplete structured output and makes no repair call.

The Greek corpus reader supplies the selected line's source metadata and up to
one neighboring reader line on each side, within the same document. It retains
available speaker labels, citations, and editorial reading states. Source-aligned
slices preserve their characters; older token-only records are labeled as
reconstructed text. The selected line remains the translation target.

## Greek evidence

Dependency evidence describes the supplied parse, including subordinate clauses
and coordinated subjects. It does not silently correct a wrong parse. Review
the source and the relationships relevant to your reading.

UD `Tense=Past` is a morphological tag, not a sufficient claim that a subjunctive,
infinitive or participle describes past time. Grounding preserves raw features
and separates morphological labels from temporal interpretation. Missing aspect
information is not silently filled in as an aorist analysis.

::: aegean.translate
