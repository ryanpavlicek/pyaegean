# AI Layer

> **Exploratory material.** Every generative output here is a labeled,
> provenanced *hypothesis* — never ground truth, and on the undeciphered
> scripts never a reading. The full picture of what pyaegean can and cannot
> claim is on the **[Limitations](Limitations)** page.

`aegean.ai` is a **multi-provider**, **optional**, **grounded** AI layer built
on local, deterministic grounding evidence.

> Providers' SDKs are optional extras, imported lazily. `import aegean` never
> requires them. API keys are read from the environment and never logged.

## Providers & clients

| Provider | id | SDK extra | Key env var | Model env var |
| --- | --- | --- | --- | --- |
| Anthropic (default) | `anthropic` | `pyaegean[anthropic]` | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` |
| OpenAI | `openai` | `pyaegean[openai]` | `OPENAI_API_KEY` | `OPENAI_MODEL` |
| xAI Grok | `grok` | `pyaegean[grok]` | `XAI_API_KEY` | `XAI_MODEL` |
| Google Gemini | `gemini` | `pyaegean[gemini]` | `GEMINI_API_KEY` | `GEMINI_MODEL` |

```python
from aegean import ai
ai.list_providers()                      # ['anthropic', 'gemini', 'grok', 'openai']
client = ai.get_client("anthropic")      # needs pyaegean[anthropic] + a key
client = ai.get_client("openai", model="gpt-4o")
```

### Model selection

The model is **configurable and current** (model ids drift): each provider
resolves its model from an explicit `model=` argument, then `<PROVIDER>_MODEL`,
then a default constant. Point `ANTHROPIC_MODEL` at the latest flagship Claude
for maximum capability.

## Capabilities

All capabilities accept an optional `client=` (defaults to Anthropic) and
`grounding=` (an iterable of evidence strings), and return an
`ExploratoryResult`.

```python
from aegean import ai
r = ai.translate("μῆνιν ἄειδε θεά", source="Ancient Greek", client=client)
ai.gloss("ἐν ἀρχῇ ἦν ὁ λόγος", client=client)
ai.decipher_hypotheses("KU-RO DA-RO", client=client)   # cautious, cited, undeciphered
ai.nlp_assist("ἦν", task="lemma + POS", client=client)
ai.ask("What sites attest KU-RO?", grounding=[...], client=client)
ai.summarize(text, client=client)
```

### Exploratory results

```python
r.text               # the model's output
r.kind               # 'translate' | 'gloss' | 'decipher' | 'nlp_assist' | 'ask' | 'summarize' | 'extract'
r.exploratory        # True
r.provider, r.model, r.prompt_version
r.grounding          # the evidence fed in — a tuple of GroundingItem(content, source, ref)
r.labeled()          # output prefixed with an unmistakable EXPLORATORY tag
r.trace()            # human-readable provenance: the local facts that grounded it
r.provenance()       # dict for logging/export
```

## Grounding, traceability & prompt-injection safety

Feed real evidence so the model reasons over the corpus, and wrap untrusted
source text so embedded instructions can't steer it. Every piece of evidence is
a **`GroundingItem`** carrying not just the text shown to the model but *where it
came from* — so the result can be audited back to the local, non-generative
facts it rested on.

```python
from aegean import ai

corpus = aegean.load("lineara")
ctx = ai.corpus_context(corpus, limit=10)              # top words → corpus:lineara items
ctx += ai.cooccurrence_evidence(corpus, "KU-RO")       # analysis:cooccurrence items
# ai.lexicon_evidence(["λόγος", "θεός"])               # lexicon:LSJ glosses (needs use_lsj)
ai.wrap_untrusted("…source…")                          # delimited, do-not-follow

r = ai.decipher_hypotheses("KU-RO", grounding=ctx, client=client)
print(r.trace())
# EXPLORATORY decipher via anthropic/claude-… (prompt 2026.06-v1)
#   grounded in 13 item(s) from 2 source(s):
#   • analysis:cooccurrence (3):
#       - co-occurs with KU-RO: KI-RO (×5)
#   • corpus:lineara (10):
#       - KU-RO (×37)
#       …
```

Plain strings are still accepted as grounding (tagged `source="custom"`). On the
CLI, add `--trace` to `aegean ai translate|gloss|hypotheses|ask` to print the
provenance trace under the answer.

## Structured output (`extract`)

When you need data, not prose, `ai.extract` asks for JSON and parses it into
`result.data` — so the AI layer can feed a pipeline or database. Describe the
shape with `schema` (a `field → description` mapping, or a free-form string); the
parse is lenient (a ```json fence, or a bare object/array inside prose, both
work), and `result.data` is `None` (never an exception) if nothing parseable
comes back.

```python
from aegean import ai

r = ai.extract(
    ".2 di-we OLE S 1   .3 GRA 3",
    schema={"commodity": "ideogram", "unit": "metrogram", "amount": "number"},
    client=client,
)
r.data        # [{'commodity': 'OLE', 'unit': 'S', 'amount': 1}, {'commodity': 'GRA', 'amount': 3}]

ai.parse_json('the answer is {"x": [1, 2]} ok')   # {'x': [1, 2]} — the standalone parser
```

From the shell: `aegean ai extract "OLE S 1" --fields commodity,amount` prints the
parsed JSON, ready to pipe into `jq`. Still exploratory — the extraction is a
model hypothesis, not a verified parse.

## Response caching

A sha256-keyed cache (provider, model, system, prompt) makes repeats free and
deterministic — in-memory, or persisted to JSON.

```python
cache = ai.ResponseCache("~/.cache/pyaegean/ai.json")
client = ai.get_client("anthropic", cache=cache)
```

## Hybrid translation (`aegean.translate`)

Builds deterministic **local** grounding (Greek baseline lemmas, Linear A
transliteration), then delegates the translation to the AI layer.

```python
from aegean import translate
translate.grounding_for("ἦν ὁ λόγος", "greek")     # [GroundingItem('ἦν → lemma εἰμί', 'lemmatizer'), …]
translate.grounding_for("KU-RO DA-RO", "lineara")  # [GroundingItem('KU-RO → /kuro/', 'transliteration'), …]

r = translate.translate("ἦν ὁ λόγος", script="greek", client=client)
print(r.labeled())
print(r.trace())     # names the lemmatizer / transliteration grounding
```

## Errors

- `ProviderNotInstalled` — the provider's SDK isn't installed (`pip install
  'pyaegean[<provider>]'`).
- `MissingAPIKey` — no key in the env or `api_key=`.
- `UnknownProvider` — unregistered provider id.
