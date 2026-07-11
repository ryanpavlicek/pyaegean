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
| `lemma_known` | a plain `True`/`False`: `False` marks a lemma you should check |
| `head`, `relation` | the syntactic head (by `index`; `0` = sentence root) and its relation, filled only when a parser or the neural pipeline is active |
| `xpos`, `feats` | the fine-grained morphological tag and its feature string, filled only by the neural pipeline |

`head`/`relation`/`xpos`/`feats` are `None` under the zero-dependency baseline. They appear
once you turn on a parser (`greek.use_parser()`) or the joint neural pipeline
(`greek.use_neural_pipeline()`).

## The evidence class: `lemma_source`

Every lemma carries the class of evidence behind it, so you know how much to trust it before
you build on it:

| `lemma_source` | How the lemma was found | How much to trust it |
| --- | --- | --- |
| `attested` | a direct hit in the Perseus treebank lexicon | high: an attested, correctly accented form |
| `neural` | a real prediction from the joint neural model | high on in-domain text, less so far from it |
| `rule` | recovered by the ending-stripping rule layer (e.g. `νόμου` → `νόμος`) | good for the regular paradigms it covers |
| `seed` | the bundled seed table or a closed-class word (the article, particles, …) | high: curated |
| `paradigm` | a curated UniMorph inflection-table lookup, opt-in via `use_paradigms()` | high: a curated inflectional form |
| `identity` | a model was asked but returned the surface form unchanged | **verify**: not a real analysis |
| `unresolved` | the baseline was exhausted; the form is returned as-is | **verify**: the tool could not lemmatize it |
| `punct` | a punctuation or numeral token, its own "lemma" | n/a |

`lemma_known` is simply `False` for `identity` and `unresolved` and `True` otherwise, so a
quick filter for "what should I check?" is `[r for r in records if not r.lemma_known]`. The
same signal drives the ["needs review" column](When-the-Tool-Is-Wrong) in a review table.

A subtle but important point: a lemma that equals the surface form is not automatically a
guess. `λόγος` is the lemma of `λόγος`; the neural model reports that as `neural` (a genuine
analysis), not `identity`. The class reflects *how the answer was reached*, not whether the
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

## See also

- [Greek NLP](Greek-NLP): running the pipeline and turning on the backends.
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): the kinds of mistakes to expect, and how
  to correct them.
- [For Specialists](For-Specialists): the register model in full, with the audit trail.
- [Benchmarks](Benchmarks) and [Glossary](Glossary): the measured numbers and the terms.
