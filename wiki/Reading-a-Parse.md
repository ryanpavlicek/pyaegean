# How to read a pyaegean parse

This page explains what pyaegean's per-token analysis actually tells you, field by field, and
how to tell a grounded answer from a guess. It is written for someone who can read Ancient
Greek but is new to automated analysis. If you want the how-to for running the pipeline,
start at [Greek NLP](Greek-NLP); this page is about interpreting what comes back.

The one thing to carry away: **a parse is evidence, not a verdict.** pyaegean marks how it
reached each answer so you can weigh it, and it is designed to say "I am guessing here" rather
than hide it.

## One token, every field

`greek.pipeline(text)` returns one `TokenRecord` per token. Run on the opening of John:

```python
from aegean import greek
for r in greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος"):
    print(r.index, r.text, r.upos, r.lemma, r.lemma_source.value)
# 1 ἐν    ADP  ἐν    seed
# 2 ἀρχῇ  NOUN ἀρχή  seed
# 3 ἦν    VERB εἰμί  seed
# 4 ὁ     DET  ὁ     seed
# 5 λόγος NOUN λόγος seed
```

| Field | What it means |
| --- | --- |
| `text` | the token as it appears (punctuation is kept as its own token) |
| `upos` | the coarse part of speech, in the Universal Dependencies scheme (NOUN, VERB, ADP, …) |
| `lemma` | the dictionary (citation) form |
| `lemma_source` | **where the lemma came from** (see the next section) |
| `lemma_resolved` | whether the output is a real lemma decision rather than a surface fallback |
| `lemma_verified` | whether a human reviewer explicitly verified or corrected the lemma |
| `review_recommended` | whether the lemma should be checked |
| `lemma_known` | deprecated compatibility alias for `lemma_resolved` |
| `head`, `relation` | the syntactic head (by `index`; `0` = sentence root) and its relation, filled only when a parser or the neural pipeline is active |
| `xpos`, `feats` | the fine-grained morphological tag and its feature string, filled only by the neural pipeline |
| `lemma_source_path` | the neural lemma composition path, when exposed (`lookup_form_upos`, `lookup_form`, `edit_script`, `lookup_lower_fallback`, or `identity_fallback`) |
| `token_confidence`, `sentence_confidence` | optional typed evidence with task/source/domain scope and explicit unavailable reasons; never a scholarly certainty |

`head`/`relation`/`xpos`/`feats` are `None` under the zero-dependency baseline. They appear
once you turn on a parser (`greek.use_parser()`) or the joint neural pipeline
(`greek.use_neural_pipeline()`).

## The evidence class: `lemma_source`

Every lemma carries the class of evidence behind it, so you know how much to trust it before
you build on it:

| `lemma_source` | How the lemma was found | How much to trust it |
| --- | --- | --- |
| `attested` | a direct hit in the Perseus treebank lexicon | high: an attested, correctly accented form |
| `neural_lookup` | the joint model selected a lemma from its training-form lookup | model-resolved; not the same as human verification |
| `neural_edit` | the joint model produced a non-identity contextual edit script | model-resolved; confidence depends on domain |
| `neural` | an older neural backend produced a lemma but does not expose its internal branch | model-resolved; confidence depends on backend and domain |
| `rule` | recovered by the ending-stripping rule layer (e.g. `νόμου` → `νόμος`) | good for the regular paradigms it covers |
| `seed` | the bundled seed table or a closed-class word (the article, particles, …) | high: curated |
| `paradigm` | a curated UniMorph inflection-table lookup, opt-in via `use_paradigms()` | high: a curated inflectional form |
| `identity` | a model was asked but returned the surface form unchanged | **verify**: not a real analysis |
| `unresolved` | the baseline was exhausted; the form is returned as-is | **verify**: the tool could not lemmatize it |
| `punct` | a punctuation or numeral token, its own "lemma" | n/a |
| `user` | a human correction imported through the review workflow | human-verified; the machine prediction and source remain preserved beside it |

`review_recommended` is `True` for `identity` and `unresolved`, so a quick filter for
"what should I check?" is `[r for r in records if r.review_recommended]`. The
same signal drives the ["needs review" column](When-the-Tool-Is-Wrong) in a review table.
`lemma_known` remains temporarily as a deprecated alias of `lemma_resolved`.

A subtle but important point: a lemma that equals the surface form is not automatically a
guess. `λόγος` is the lemma of `λόγος`; the neural model reports that as `neural` (a genuine
analysis, normally `neural_lookup`), not `identity`. The class reflects *how the answer was reached*, not whether the
string changed.

## Three registers of output

Across the whole toolkit, output falls into three registers. Reading the register is how you
know what kind of claim you are looking at:

- **Established** (bridges for deciphered scripts, curated readings): if it is wrong, it is a
  bug. Report it.
- **Measured** (accuracy numbers, the neural pipeline): reproducible against a stated
  protocol. Check it against [Benchmarks](Benchmarks) and expect the error rates documented
  there, by text type where available.
- **Exploratory** (Linear A / Cypro-Minoan analysis, AI readings, generative translation):
  labeled unverified at the point of use. Treat it as a hypothesis to test, never as a
  reading.

A `lemma_source` of `identity` or `unresolved` is the pipeline being honest that a particular
token has slipped from "measured" toward "you are on your own here." That is the signal to
reach for a dictionary or a commentary.

## Confidence is scoped evidence, not a verdict

With `with_confidence=True`, neural output may carry typed confidence for UPOS, XPOS,
FEATS, lemma, head, relation, and a sentence aggregate. Every available value identifies
the model, calibration, source path, optional domain, sample count, and measured metric; an
unavailable value carries a reason such as `missing_calibration`, `unsupported_source`, or
`unsupported_domain`. The legacy flat confidence fields are compatibility views and do not
establish a domain claim. A `confidence_domain` label is supplied by the caller, not inferred
by the model, and no out-of-domain warning is implied without evidence.

If a review workflow needs thresholds, pass a caller-owned `AbstentionPolicy` as
`confidence_policy`. It records its canonical hash and returns `accept`, `review`, or
`unavailable` without changing the parse. There are no bundled thresholds: source/task
calibration and coverage-risk measurements remain a development-only evidence task.

## See also

- [Greek NLP](Greek-NLP): running the pipeline and turning on the backends.
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): the kinds of mistakes to expect, and how
  to correct them.
- [For Specialists](For-Specialists): the register model in full, with the audit trail.
- [Benchmarks](Benchmarks) and [Glossary](Glossary): the measured numbers and the terms.
