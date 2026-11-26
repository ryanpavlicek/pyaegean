# How to read a pyaegean parse

This page explains each field on pyaegean's per-token Greek analysis and how to
distinguish attested lookups, neural predictions, and unresolved fallbacks. For
running the pipeline and enabling optional backends, see
[Greek NLP](Greek-NLP).

Every `TokenRecord` stores both the predicted annotation and the mechanism that
produced it, separating dictionary lookups from rule guesses and unresolved
tokens.

## Fields on `TokenRecord`

`greek.pipeline(text)` returns one `TokenRecord` per token. On the opening
clause of John:

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

| Field | Meaning |
| --- | --- |
| `text` | Surface token (punctuation is kept as its own token) |
| `upos` | Universal Dependencies coarse part of speech (`NOUN`, `VERB`, `ADP`, …) |
| `lemma` | Dictionary citation form |
| `lemma_source` | Origin of the lemma decision (see below) |
| `lemma_resolved` | `True` when the output reflects a lemma decision rather than an identity or unresolved fallback |
| `lemma_verified` | `True` when an imported human lemma correction (`user`) is recorded |
| `review_recommended` | `True` when `lemma_source` is `identity` or `unresolved` (not a general error detector) |
| `lemma_known` | Deprecated alias for `lemma_resolved` |
| `head`, `relation` | Syntactic head (`index`; `0` = root) and dependency relation; populated when a parser or the neural pipeline is active |
| `xpos`, `feats` | Fine-grained morphological tag and UD feature string; populated by the neural pipeline |
| `lemma_source_path` | Internal neural lemma branch when exposed (`lookup_form_upos`, `lookup_form`, `edit_script`, `lookup_lower_fallback`, or `identity_fallback`) |
| `token_confidence`, `sentence_confidence` | Optional typed confidence evidence carrying task, source, domain, and explicit unavailability reasons |

Under the zero-dependency baseline, `head`, `relation`, `xpos`, and `feats` are
`None`. Activating `greek.use_parser()` or `greek.use_neural_pipeline()`
populates them.

## Provenance classes: `lemma_source`

Every lemma records how it was selected. Provenance does not rank accuracy: an
attested lookup or neural prediction can still be wrong in context.

| `lemma_source` | Source | Scope and limits |
| --- | --- | --- |
| `attested` | Direct lookup in the Perseus treebank lexicon | Attested, accented form; context-free |
| `neural_lookup` | Joint neural model training-form lookup | Model-resolved; not human-verified |
| `neural_edit` | Joint neural model non-identity contextual edit script | Model-resolved; accuracy varies by domain |
| `neural` | Neural backend that does not expose its internal branch | Model-resolved; accuracy varies by backend and domain |
| `rule` | Ending-stripping rule layer (e.g. `νόμου` → `νόμος`) | Reliable on regular paradigms only |
| `seed` | Bundled seed table or closed-class form (articles, particles, pronouns) | Curated |
| `paradigm` | Curated UniMorph inflection-table lookup (`greek.use_paradigms()`) | Curated inflectional form |
| `identity` | Model returned the surface form unchanged as a fallback | Verify manually; no active resolution |
| `unresolved` | Baseline rules exhausted; surface form returned unchanged | Verify manually; tool could not lemmatize |
| `punct` | Punctuation or numeral token | Not applicable |
| `user` | Human correction imported via the review workflow | Human-verified; prior prediction and source remain preserved beside it |

`review_recommended` is `True` whenever `lemma_source` is `identity` or
`unresolved`, letting you filter unresolved tokens directly:
`[r for r in records if r.review_recommended]`. A `False` value does not
certify the lemma, POS, morphology, or parse tree.

On `TokenRecord`, `lemma_verified` marks an imported human lemma correction
(`user`). Through the corpus review workflow, a reviewer can also explicitly
accept an unchanged prediction, setting its verification flag while preserving
the original prediction source. Blank legacy correction cells do not imply
acceptance, and verifying a lemma does not certify other fields. In review
CSVs, the `needs_review` column checks an explicit review flag first, then
`lemma_source`, then legacy metadata when no source is stored. Use
`lemma_resolved` and `lemma_verified` in new code instead of the deprecated
`lemma_known` alias.

A lemma identical to the surface form can still be a genuine analysis. For
`λόγος`, the neural model reports `neural_lookup` (or `neural`) rather than
`identity`; `lemma_source` records how the answer was produced, not whether the
string changed.

## Evidence registers

Across pyaegean, outputs belong to three registers:

- **Established** (deciphered-script bridges, curated readings): errors are
  bugs to report and correct.
- **Measured** (statistical and neural NLP): reproducible under a stated
  protocol; expect the per-genre error rates documented on
  [Benchmarks](Benchmarks).
- **Exploratory** (Linear A and Cypro-Minoan analysis, AI-layer readings and
  translations): labeled unverified at the point of use; treat as hypotheses.

When `lemma_source` is `identity` or `unresolved`, the token falls outside
confident automated resolution and should be checked against a lexicon or
commentary.

## Scoped confidence evidence

With `with_confidence=True`, neural output attaches typed confidence objects
for UPOS, XPOS, FEATS, lemma, head, relation, and a sentence aggregate. Each
populated value records its model, calibration source, source path, optional
domain, sample count, and measured metric. Unavailable scores carry explicit
reasons (`missing_calibration`, `unsupported_source`, `unsupported_domain`).
Legacy flat confidence attributes remain for compatibility and carry no domain
claim. The `confidence_domain` label is caller-supplied rather than detected
automatically.

For calibrated probabilities (where a 0.85 score tracks an ~85% empirical
accuracy rate on matched texts), activate the bundled Schema-2 registry with
`greek.use_calibration_registry()` and pass `confidence_domain="literary"` for
literary prose or `confidence_domain="documentary_native"` for documentary
papyri. Calibrated scores remain statistical estimates rather than scholarly
certainty. To apply explicit review cutoffs without altering the parse, pass a
caller-defined `AbstentionPolicy` via `confidence_policy` (returning `accept`,
`review`, or `unavailable` alongside its canonical hash), or prioritize review
spreadsheets by calibrated risk with `priority="calibrated_risk", budget=N`.
pyaegean imposes no default threshold on an edition.

## See also

- [Greek NLP](Greek-NLP): running the pipeline and activating backends
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): error profiles and
  human-in-the-loop correction workflows
- [For Specialists](For-Specialists): evidence registers and audit trails
- [Benchmarks](Benchmarks) and [Glossary](Glossary): measured scores and terms
