# Translation

`aegean.translate` is pyaegean's **hybrid translator**: it builds deterministic,
local grounding from the toolkit's own tooling (Greek morphology and dependency
syntax, or Linear A sign→sound transliteration), then hands the text plus that
evidence to the key-gated [AI Layer](AI-Layer) to produce a translation. The
grounding step is real and local; the translation itself is a **model
hypothesis**, returned as an exploratory, provenanced result like everything
else in the AI layer.

> **Read this first: this is a translation *aid*, not a finished translation
> model.** It pairs the package's deterministic analysis with a general-purpose
> language model you supply a key for. Every output is an `ExploratoryResult`,
> labeled `EXPLORATORY`, carrying the exact local facts it rested on. It is
> never a citable, verified translation, and on the **undeciphered** scripts
> (Linear A, and by extension the other Aegean syllabaries) the "translation" is
> a guess built on a phonetic reading of the signs, never a decipherment. What
> pyaegean can and cannot claim is on the **[Limitations](Limitations)** page.

The idea is simple: a bare model translates Ancient Greek from its training
memory alone. Here, the model is first told the lemma, part of speech, case
role, voice, and clause structure that pyaegean computes reliably, plus the real
meaning of any non-compositional idiom present, so its draft is anchored to
local facts you can audit rather than to its own recall. The translation stays
generative, but the grounding under it is deterministic and traceable.

This page covers the translation layer specifically. For the full generative
surface (gloss, decipherment hypotheses, ask, summarize, extract), the providers
and clients, response caching, and the grounded-generation eval, see the
[AI Layer](AI-Layer).

---

## At a glance

```python
from aegean import translate

# hybrid: build local grounding, then call the model
r = translate.translate("ἦν ὁ λόγος", script="greek", client=client)
print(r.labeled())     # the translation with its EXPLORATORY tag
print(r.trace())       # the local facts that grounded it
```

```bash
# the CLI translate command is the hybrid translator
aegean ai translate "ἦν ὁ λόγος" --script greek --target English --trace
aegean ai translate "KU-RO DA-RO" --script lineara    # exploratory: Linear A is undeciphered
echo "μῆνιν ἄειδε θεά" | aegean ai translate -          # '-' reads stdin
```

Two functions make up the Python surface:

| Function | Returns | What it does |
| --- | --- | --- |
| `translate.translate(text, *, script=, target=, mode=, verify=, client=)` | `ExploratoryResult` | Build local grounding, then translate. |
| `translate.grounding_for(text, script, *, mode=)` | `list[GroundingItem]` | Just the local grounding, so you can inspect it before spending a call. |

Both are re-exported from `aegean.translate`. The CLI command `aegean ai
translate` routes through `translate.translate`.

---

## The grounding: what the model is told

`grounding_for` returns the deterministic, local evidence, each item tagged with
its **source** so the result's `trace()` names where it came from. It never
raises: grounding is best-effort, and a missing backend simply yields fewer
lines rather than an error.

```python
from aegean import translate

translate.grounding_for("ἦν ὁ λόγος", "greek")
# [GroundingItem('ἦν = εἰμί (verb, ...)',  'analysis:morphology', 'ἦν'),
#  GroundingItem('ὁ = ὁ (det)',            'analysis:morphology', 'ὁ'),
#  GroundingItem('λόγος = λόγος (noun, ...)', 'analysis:morphology', 'λόγος')]

translate.grounding_for("KU-RO DA-RO", "lineara")
# [GroundingItem('KU-RO → /kuro/', 'transliteration', 'KU-RO'),
#  GroundingItem('DA-RO → /daro/', 'transliteration', 'DA-RO')]
```

For Greek, the grounding is assembled from `greek.pipeline(text, parse=True)`:
a per-token morphology line, a clause skeleton from the dependency parse, a
rare-word flag, and an idiom gloss for any non-compositional phrase present. For
Linear A, the grounding is the sign→sound transliteration of each hyphenated word
(`analysis` of the signs, not a reading of them). Any other `script` yields no
grounding.

### Grounding modes (Greek)

For Greek, `mode` selects how much analysis to ground with. The default is
**morphology-first**, deliberately: an auto-selected dictionary gloss can surface
the wrong or an archaic sense and mislead the model, whereas morphology, voice,
case role, and clause structure are facts the toolkit computes reliably.

| `mode` | Grounds with | When to use |
| --- | --- | --- |
| `"morphology"` (default) | Per-token lemma, part of speech, case/voice/tense; a clause skeleton (predicate, subject, object) from the dependency parse; a rare-word flag; and a gloss of any idiom present. **No dictionary glosses on ordinary words.** | The recommended default: reliable facts a model can use directly. |
| `"full"` | The `"morphology"` lines (idiom glosses included) **plus** concise dictionary glosses, gated to the text's rare content words. | Rare, technical, or documentary vocabulary a model is likely to misread. |
| `"lemma"` (legacy) | Lemma lines plus gated content-word LSJ glosses. | Back-compatibility with the pre-morphology grounding. |
| `"none"` | Nothing (the bare text is sent). | A baseline, or when you want the model unaided. |

An unrecognized `mode` raises `ValueError` naming the valid modes, so a typo
never silently falls through to a different grounding style.

The `"full"` glosses come from a **concise, common-sense-first** dictionary
cascade (Middle Liddell, Cunliffe for Homer, Abbott-Smith / Dodson for the New
Testament), cleaned, and gated to the rare words:

```python
translate.grounding_for("σπεῖρε τὴν ἄρουραν", "greek", mode="full")
# morphology lines for each token, plus a rarity flag, plus concise glosses
# for the flagged rare content words (σπεῖρε, ἄρουραν) when a concise
# dictionary is loaded.
```

The rarity gate uses the full, SHA-256-verified NT only when that asset is already
in the local data store. It never downloads an optional reference corpus during a
translation, and it never substitutes the bundled John 1 + Philemon sample. Without
the full corpus, morphology grounding continues and the rarity flag is simply absent.

The gloss cascade is **never** taken from LSJ's first sense: LSJ orders senses
etymologically, so its lead sense is frequently the archaic meaning (καιρός,
βίος, λόγος), and asserting it would inject exactly the errors this layer exists
to avoid. If no concise dictionary is loaded, the `"full"` glosses are simply
absent (load one with `greek.use_lexicon("middle-liddell")` and kin). See the AI
Layer's [gated gloss grounding](AI-Layer#gated-lsj-gloss-grounding) for the
mechanics and `ai.grounding.content_glosses` for the reusable builder.

### Grounding depends on the active lemmatizer

Coverage of rare or inflected forms, and the clause skeleton, depends on which
Greek backend is loaded. The bundled baseline seed table strips the regular
second-declension and thematic-verb endings but misses irregular and
unrecognized forms, so a grounded translation on those is only partly grounded.
`translate.translate` raises a warning when only the baseline is active, naming
the fix: call `greek.use_treebank()`, or `greek.use_neural_pipeline()` for gold
morphology and a dependency parse, first. See [Greek NLP](Greek-NLP) for the
backends and their measured accuracy.

---

## Idiom / multiword-expression grounding

The one translation-error class per-token morphology structurally cannot reach
is the **non-compositional idiom**, where the phrase means something the words do
not: `ἐφ' ἡμῖν` is "in our power", not "upon us"; `οὐκ ἔστιν ὅπως` is "there is no
way that", not "it is not how"; `οἷός τε εἰμί` is "be able to". A literal,
token-by-token reading is wrong, and the lemma and case lines only reinforce the
literal reading. A phrase-level gloss of the real meaning gives the model the one
fact it needs, so idiom glosses ride with the **default** morphology grounding
(and with `mode="full"`).

The layer is a **curated lexicon** of vetted non-compositional expressions
(bundled as `data/bundled/greek/idioms.json`), not an exhaustive idiom
dictionary. `ai.idiom_glosses(text)` returns one `GroundingItem` per match
(source `lexicon:idiom`), and it is best-effort and never raises:

```python
from aegean import ai
ai.idiom_glosses("διὰ τοῦτο ἐφ' ἡμῖν ἐστιν")
# [GroundingItem('διὰ τοῦτο: for this reason, therefore', 'lexicon:idiom', 'διὰ τοῦτο'),
#  GroundingItem("ἐφ' ἡμῖν: in our power, up to us", 'lexicon:idiom', "ἐφ' ἡμῖν")]
```

Detection is **surface- and lemma-based, not a parser**, and matches two ways:

- **surface** (primary): an accent-insensitive match of the idiom's surface form,
  with elision/apostrophe normalized away, so fixed idioms are caught verbatim
  (including their elided and gapped-correlative spellings, e.g.
  `οὐ μόνον ... ἀλλὰ καί`);
- **contiguous lemma match** (secondary): the idiom's content lemmas appearing as
  an *adjacent* run among the text's lemmas, which catches inflected idioms
  (`οἷός τε ἐστί` for the lexicon's `οἷός τε εἰμί`) without firing on the same
  function words scattered across an unrelated sentence. Its inflection coverage
  tracks the active lemmatizer.

On overlapping matches the longest idiom wins and its shorter sub-idioms are
suppressed; identical glosses are de-duplicated. A gloss is a meaning aid, not a
syntactic claim.

---

## Post-hoc verify: translate, then check and repair

`verify=True` (Greek only) runs a **translate-then-check-and-repair** pass instead
of a single grounded call, at the cost of a second model call. It is the safest
ordering for hard or high-stakes passages:

1. The text is translated **raw**, with no grounding in the prompt, so the local
   analysis cannot bias the draft.
2. The full grounding (morphology, idiom glosses, and concise glosses, as for
   `mode="full"`) is then supplied to a second call that checks the draft against
   it and corrects **only** definite contradictions (a wrong voice, subject or
   object, case relation, a rare word's or idiom's sense, an omission or
   addition), keeping the draft where it is already right.

```python
r = translate.translate("ἦν ὁ λόγος", script="greek", verify=True, client=client)
```

```bash
aegean ai translate "ἦν ὁ λόγος" --script greek --verify
```

Because the grounding only ever reaches the checker, it cannot bias the initial
draft. A wrong analysis can still mislead the repair step, so the pass is only as
sound as the grounding it checks against. `verify` supersedes `mode` for Greek
(the checker always sees the full grounding); for non-Greek scripts it has no
effect and the normal single call is used. For choosing between the modes and
verify, see [Recipe 26](Recipes#26--get-the-best-ai-translation-out-of-pyaegean).

---

## Providers: the key-gated `[ai]` layer

Translation runs through the same providers as the rest of the AI layer: five hosted
(Anthropic, OpenAI, Grok, Gemini, OpenRouter) plus `local`, which runs a model on your own
machine through an OpenAI-compatible server (Ollama, LM Studio, llama.cpp, vLLM) with no key
or network. See [AI Layer → Using a local model](AI-Layer#using-a-local-model-ollama-lm-studio-llamacpp-vllm).
The core library has **zero third-party dependencies**; a provider's SDK is an
optional extra, imported only when you actually call it, and nothing runs (or
costs anything) until you build a client (with a hosted provider's API key, or a
no-key local server via the `local` provider). Keys come from the environment and
are never logged.

| Provider | id | Key env var | Default model |
| --- | --- | --- | --- |
| Anthropic (default) | `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| xAI Grok | `grok` | `XAI_API_KEY` | `grok-2-latest` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-1.5-pro` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-4o-mini` |

Install one provider, or all three SDKs at once with the `[ai]` extra (Grok and
OpenRouter reach through the OpenAI-compatible endpoint, so they need no separate
SDK):

```bash
pip install "pyaegean[anthropic]"    # the default provider
pip install "pyaegean[ai]"           # all providers at once
pip install "pyaegean[cli]"          # the `aegean` command-line tool
```

The model is configurable and current by design (an explicit `model=`, then the
`<PROVIDER>_MODEL` env var, then the built-in default). Pass a pre-built client
to `translate.translate(..., client=...)`; the default is a fresh Anthropic
client. See the AI Layer's [Providers & clients](AI-Layer#providers--clients) and
[Model selection](AI-Layer#model-selection) for the full picture, and
[Installation](Installation) for the extras matrix.

---

## Every output is exploratory and provenanced

`translate.translate` returns the same `ExploratoryResult` as the rest of the AI
layer, so the caveat and the grounding travel with the text:

```python
r = translate.translate("ἦν ὁ λόγος", script="greek", client=client)

r.labeled()      # the translation prefixed with an unmistakable EXPLORATORY tag
r.trace()        # the local facts that grounded it, grouped by source
r.provenance()   # a dict for logging/export: provider, model, prompt version, grounding
r.exploratory    # always True — preserved through save and reload
```

`labeled()` is what you show a human, so a translation can never be mistaken for a
verified fact:

```text
[EXPLORATORY · translate · anthropic/claude-sonnet-4-6]
"was the word" (the copula ἦν + predicate nominal λόγος; …).
```

`trace()` names exactly which local facts anchored the translation, so a reader
can check the output against its grounding rather than taking it on trust. When
nothing was fed in, the trace flags the generation as ungrounded, the weakest
case. The result also serializes to JSON with the `exploratory` flag intact
(`.to_json()` / `ExploratoryResult.from_dict`), so a translation you wrote out
last week is still a labeled hypothesis when you read it back. See the AI Layer's
[result object](AI-Layer#what-every-result-looks-like-exploratoryresult) and
[saving results](AI-Layer#saving-ai-results) for the details.

### Linear A and the undeciphered scripts

Linear A is **undeciphered**. Its grounding is a sign→sound transliteration, not a
meaning, and the resulting "translation" is a model's guess built on that
phonetic reading. It is the sharpest edge of the exploratory caveat and must never
be presented as a reading. For the deterministic, evidence-based analysis that
should anchor any such guess, and for cautious decipherment hypotheses tied to
cited corpus evidence, see [Linear A](Linear-A) and the AI Layer's
[decipherment hypotheses](AI-Layer#decipherment-hypotheses).

---

## CLI reference

`aegean ai translate TEXT` is the hybrid translator from the shell.

| Flag | Default | Meaning |
| --- | --- | --- |
| `TEXT` |— | Source text. `-` reads stdin. |
| `--script` | `greek` | `greek` or `lineara` (drives the local grounding). |
| `--target` | `English` | Target language. |
| `--mode` | `morphology` | Grounding style: `morphology`, `full`, `lemma` (legacy), `none`. |
| `--glosses` / `--no-glosses` | on | Legacy; superseded by `--mode`. Toggles glosses in the `lemma`/`full` modes. |
| `--verify` | off | Greek only: translate raw, then check and repair against the full grounding (a second call). |
| `--provider` | `anthropic` | `anthropic`, `openai`, `grok`, `gemini`, `openrouter`, or `local`. |
| `--model` | provider default | Model override. |
| `--output` / `-o` | — | Save the result (`.json` full result, `.txt` labeled text). |
| `--trace` | off | Print the grounding provenance under the answer. |
| `--json` | off | Emit one machine-readable document and nothing else. |

```bash
aegean ai translate "σπεῖρε τὴν ἄρουραν" --script greek --mode full --trace
aegean ai translate "ἦν ὁ λόγος" --script greek --verify
aegean ai translate "KU-RO DA-RO" --script lineara --trace   # exploratory
```

Shared CLI conventions (a `-` argument reads stdin, `--json` prints one document,
`--output/-o` saves to a file) are on the [CLI](CLI) page.

---

## Notes & limitations

- **A translation here is a hypothesis, not a fact.** The label, the trace, and
  the [grounded-generation eval](AI-Layer#grounded-generation-eval) all exist to
  keep that front of mind. On the undeciphered scripts, nothing this layer
  produces is a reading.
- **The grounding is deterministic; the translation is generative.** The value is
  that the model reasons over real, local, auditable evidence rather than its
  training memory alone. Feed it a richer lemmatizer for fuller grounding.
- **Prefer the deterministic tools where they exist.** For tagging, lemmatizing,
  scansion, and syntax, use [Greek NLP](Greek-NLP); for Linear A/B tablet
  accounting, use [Analysis](Analysis) and [Linear A](Linear-A). This layer is
  for the step those cannot do, and its output should be checked against them.
- **Costs and keys are yours.** Nothing runs until you build a client with a key;
  use the AI layer's [response cache](AI-Layer#response-caching) to avoid paying
  twice for the same prompt.

For the full generative surface see the **[AI Layer](AI-Layer)**, and for the
boundary of what pyaegean can and cannot claim see **[Limitations](Limitations)**.
