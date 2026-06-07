# AI Layer

`aegean.ai` (v0.2) is a **multi-provider**, **optional**, **grounded** AI layer.
Every generative output is labeled **exploratory** with full provenance —
readings of this material are hypotheses, never ground truth.

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
r.kind               # 'translate' | 'gloss' | 'decipher' | 'nlp_assist' | 'ask'
r.exploratory        # True
r.provider, r.model, r.prompt_version
r.grounding          # the evidence that was fed in
r.labeled()          # output prefixed with an unmistakable EXPLORATORY tag
r.provenance()       # dict for logging/export
```

## Grounding & prompt-injection safety

Feed real evidence so the model reasons over the corpus, and wrap untrusted
source text so embedded instructions can't steer it.

```python
from aegean import ai
ctx = ai.corpus_context(aegean.load("greek"), limit=10)   # top words as evidence
ai.wrap_untrusted("…source…")                             # delimited, do-not-follow
ai.ask("…", grounding=ctx, client=client)
```

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
translate.grounding_for("ἦν ὁ λόγος", "greek")     # ['ἦν → lemma εἰμί', ...]
translate.grounding_for("KU-RO DA-RO", "lineara")  # ['KU-RO → /kuro/', ...]

r = translate.translate("ἦν ὁ λόγος", script="greek", client=client)
print(r.labeled())
```

## Errors

- `ProviderNotInstalled` — the provider's SDK isn't installed (`pip install
  'pyaegean[<provider>]'`).
- `MissingAPIKey` — no key in the env or `api_key=`.
- `UnknownProvider` — unregistered provider id.
