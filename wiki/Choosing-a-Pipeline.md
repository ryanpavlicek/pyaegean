# Choosing a Pipeline

pyaegean gives you several ways to tag, lemmatize, parse, and gloss Ancient
Greek, from a zero-dependency baseline that runs the moment you import the
package to an opt-in neural model. None of them is the right answer for every
task. The best choice depends on what your material actually is (a clean
digital edition, a broken inscription, a scanned page) and on what you are
optimizing for (accuracy, portability, speed, transparency, or coverage).

This page is a chooser. It maps a kind of material to a recommended backend,
gives the exact call that turns that backend on, and states the trade-off you
accept in return. For the stage-by-stage tour of what each function does, see
[Greek NLP](Greek-NLP); for the measured numbers and the evaluation protocol
behind them, see [Benchmarks](Benchmarks).

## Inspect first: `greek.profile_text`

Before you choose, look at what you have. `greek.profile_text` reads a passage
and reports a description of it, so you are matching a backend to the real
material rather than to an assumption about it.

```python
from aegean import greek

profile = greek.profile_text("ἐν ἀρχῇ ἦν ὁ λόγος.")
```

The profile describes surface features of the text, such as which script it
contains, whether it carries polytonic accents and breathings or is bare of
them, whether it looks like Beta Code awaiting conversion, and how much of it
the zero-dependency baseline already resolves. It is **descriptive**: it
reports these features and does not pick a pipeline for you. Read the profile,
then match what you see against the table below and decide.

## Material to pipeline

| Your material | Start with | The call that enables it | The trade-off |
| --- | --- | --- | --- |
| **Clean digital text** (a well-edited literary passage or `load_work` corpus) | the neural pipeline for measured generalization, or the treebank lexicon for attested-gold lemmas without heavy deps | `greek.use_neural_pipeline()` / `greek.use_treebank()` | the neural pipeline has published in-domain and out-of-domain measurements (see [Benchmarks](Benchmarks)) but needs the `[neural]` extra and a model fetch; the treebank stays light but only covers attested forms |
| **A damaged inscription or papyrus** (restorations, lacunae, unclear readings) | any Greek tier on the *certain* text, plus the reading-status apparatus and a manual review of anything editorial | a Greek tier above, then `sentence_policy="inscription"` or `"papyrus"`, `greek.needs_review(...)`, and the `ReadingStatus` on each token | analysis of restored or lost text is editorial, not attested; treat it as a lead to check, not a result (see [Using Critical Editions](Using-Critical-Editions)) |
| **OCR'd or noisy text** | lenient normalization to repair, then a tier, then a review pass | `greek.normalize(text, lenient=True)` first, then a backend | repair fixes common artifacts and warns about each, but garbage in is still garbage out: plan to review |
| **Teaching** | the offline baseline plus a concise dictionary | default (no backend), with `greek.use_dodson()` or `greek.use_lexicon("middle-liddell")` for glosses | favours transparency, an instant import, and reproducibility over the last points of accuracy; the rules are inspectable and the same for every student |
| **Verse or line-oriented material** | the same backend, with physical-line boundaries made explicit | `greek.pipeline(text, sentence_policy="verse")` or `greek.segment_text(text, policy="verse")` | every non-empty physical line becomes a sentence boundary; confirm that this matches the edition's sentence convention |
| **Benchmarking** | the evaluation harness on leakage-clean folds | `greek.evaluate_on_ud(...)` / `greek.bootstrap_ud(...)` | scores what the code actually does against gold, with out-of-domain always reported next to in-family (see [Benchmarks](Benchmarks)) |

Glossing is a separate axis from tagging: the **dictionary registry**
(`use_lsj`, `use_dodson`, `use_lexicon`) answers "what does this word mean" and
composes with any of the tagging tiers above.

## Choose sentence segmentation explicitly

Sentence segmentation is a document decision, separate from the choice of tagger,
lemmatizer, parser, or neural model. The default is conservative and protects dotted
abbreviations and numbers. Use a named policy when the source has a different
boundary convention:

| Policy | Best fit | Boundary behavior |
| --- | --- | --- |
| `default` | mixed or unknown text | period, semicolon/Greek question mark, ano teleia/middle dot, `!`, and `?`, with dotted abbreviations/numbers protected |
| `prose` | literary prose | the same conservative punctuation rules, with a descriptive name |
| `verse` | lineated verse | prose rules plus each non-empty physical line |
| `inscription` | epigraphic text | only strong `.`, `!`, and `?`; weak marks stay in the current sentence |
| `papyrus` | papyrological text with editorial brackets | strong `.`, `!`, and `?`; marks inside balanced `[]`, `⟦⟧`, and `<>` are ignored |

```python
from aegean import greek

result = greek.segment_text(text, policy="papyrus")
records = greek.pipeline(text, sentence_policy="papyrus")
```

`segment_text()` returns exact source spans and a stable `policy_id`; the historical
`greek.sentences()` projection still returns trimmed strings without terminal marks.
For a source-specific rule, pass a `SentenceSegmenter`-compatible object or callable
as `segmenter=`. pyaegean validates that plugin output is ordered, non-overlapping,
in range, and gap-free over non-whitespace text; tokenization additionally rejects
boundaries that bisect a token. Built-in
rules have no confidence score; a plugin confidence, when supplied, is only metadata
in `[0, 1]`, not a calibration claim.

When using `pipeline_tokens()`, complete contiguous `SourceAlignment.sentence_id`
runs take precedence over punctuation, the selected policy, and any plugin. Partial
or non-contiguous IDs are rejected. This lets an edition's explicit sentence IDs win
without silently mixing them with a heuristic splitter.

## The backends, and their trade-offs

| Backend | Enable it with | Accuracy | Dependencies | Speed | Coverage |
| --- | --- | --- | --- | --- | --- |
| Offline baseline | nothing (the default) | reliable on closed classes and regular paradigms; limited on open-class and irregular forms | none (standard library only) | instant import, fast | every token, fully offline |
| Treebank lexicon | `greek.use_treebank()` | gold lemmas and features for attested forms | none heavy (one prebuilt index fetch, then cached) | instant after the fetch | attested forms only |
| Pure-Python trained | `greek.use_tagger()`, then `greek.use_lemmatizer()`, `greek.use_parser()` | generalizes to unseen forms (figures in [Greek NLP](Greek-NLP)) | none heavy (small models fetched, then cached) | fast | open-class and unseen forms |
| Neural pipeline | `greek.use_neural_pipeline()` | the highest measured on the UD Perseus benchmark (see [Benchmarks](Benchmarks)) | the `[neural]` extra (onnxruntime, no torch) | one model fetch, then CPU inference (throughput in [Greek NLP](Greek-NLP)) | UPOS, UD FEATS, dependency trees, and lemmas from one pass |
| Dictionary registry | `greek.use_lsj()`, `greek.use_dodson()`, `greek.use_lexicon(id)` | curated scholarly dictionaries | none heavy (index fetch; Dodson is bundled, no download) | instant after the fetch | glossing, not tagging |
| Manual review | `aegean review export` / `apply`, or `greek.annotate_corpus(...)` | as good as the reviewer | none (the `[cli]` extra for the export and apply commands) | human-paced | whatever you choose to check |

The `use_*` calls select the convenient module-level default. A server, notebook host, or
test suite that needs configurations to coexist should construct `GreekPipeline()` for an
isolated baseline or `GreekPipeline.neural()` for an isolated neural runtime. Its immutable
`config` records the model, tokenizer, profile, normalization, and the backend's
segmentation contract (for a neural instance, copied from the model manifest), plus
live execution providers. The baseline's contract is `pyaegean-punctuation-v1`; a
neural instance copies its `pretokenized` value from the model manifest. Neither is
the document's `sentence_policy`.
Choose `sentence_policy` on each `analyze()`/`pipeline()` call. `GreekPipeline.from_config(...)`
refuses a different live configuration rather than silently substituting it.

A few notes that decide most cases:

- **The baseline costs nothing and hides nothing.** It has zero third-party
  dependencies, imports instantly, and is transparent about its rules, which is
  why it is the default and the recommendation for teaching. Its limit is
  open-class precision on unseen and irregular forms.
- **The treebank is the light accuracy win.** `use_treebank()` fetches one
  prebuilt lexicon once, then serves attested, correctly accented lemmas and
  full features with no heavy dependency. It cannot help with a form the corpus
  never attests: for that, add the trained tiers or the neural pipeline.
- **The trained pure-Python tiers generalize.** `use_lemmatizer()` conditions
  on the tagger, so call `use_tagger()` first. They reach unseen forms that pure
  lookup cannot, while keeping the zero-heavy-dependency profile.
- **The neural pipeline is the accuracy ceiling.** One forward pass fills
  UPOS, morphology, a dependency tree, and the lemma for every token. It needs
  the `[neural]` extra and a one-time model fetch, and CPU inference is slower
  than the lookups. When accuracy matters most and you can install the extra,
  this is the choice.
- **Every record tells you how far to trust it.** Each pipeline record carries a
  `lemma_source` (`attested`, `neural_lookup`, `neural_edit`, generic `neural`,
  `rule`, `seed`, `paradigm`, `identity`, `unresolved`, `punct`, or `user`) and
  an explicit `review_recommended`, so you can route the
  uncertain tokens to a human rather than trusting the whole output uniformly.
  See [Reading a Parse](Reading-a-Parse).

## Reading the five materials in more depth

**Clean digital text.** A well-edited literary passage is where the neural
pipeline earns its download: `greek.use_neural_pipeline()` gives the best
measured morphology, lemmas, and dependency trees. If you would rather stay
light, `greek.use_treebank()` supplies gold lemmas for attested forms with no
heavy dependency, and the offline baseline is fine for a first look. Add
`greek.use_lsj()` or a registry dictionary when you also want glosses.

**A damaged inscription or papyrus.** The six epigraphy and papyri corpora
carry a per-token `ReadingStatus` (certain, unclear, restored, lost) and a
`Provenance.edition_fidelity` flag. Run whichever Greek tier you like on the
text, but read the apparatus: a lemma or parse sitting on restored or lost
characters is an editor's reconstruction, not attested Greek, and should be
labelled that way in anything you publish. Route those tokens through a review
pass. The full workflow, including how the apparatus is preserved, is on
[Using Critical Editions](Using-Critical-Editions). For DDbDP, search or stream
the corpus rather than loading all of it into memory.

**OCR'd or noisy text.** Start with `greek.normalize(text, lenient=True)`,
which repairs the common artifacts of scanned editions and half-converted files
(Latin letters inside Greek words, stray Beta-Code diacritics, orphaned
combining marks) and warns about each repair it makes. Then pick a tier as
above. Noise that survives repair will produce wrong analyses, so a review pass
is part of the plan, not an optional extra.

**Teaching.** The offline baseline is the teaching default: it installs with
nothing extra, imports instantly, gives the same answer on every machine, and
its syllabification, accent, prosody, and morphology rules are inspectable, so a
class can see the reasoning rather than a black box. Pair it with a concise
dictionary: `greek.use_dodson()` for Koine and the New Testament (bundled, no
download), or `greek.use_lexicon("middle-liddell")` for the classical
Intermediate Lexicon.

**Benchmarking.** To compare tiers or reproduce a published number, use the
evaluation harness rather than eyeballing output. `greek.evaluate_on_ud(...)`
scores against the leakage-clean UD folds with the official CoNLL 2018
evaluator, `greek.bootstrap_ud(...)` gives confidence intervals, and
out-of-domain results (UD PROIEL, the NT) are reported alongside the in-family
scores. The protocol, the leakage controls, and the comparison tables are on
[Benchmarks](Benchmarks).

## If your material is an Aegean script

This page is about the Greek pipelines. If you are working in a syllabic script,
the choice is different. Linear B and Cypriot are deciphered, so a Greek-reading
bridge is available (`greek_reading`, or `aegean bridge`): see
[Linear B](Linear-B) and [Cypriot](Cypriot). Linear A and Cypro-Minoan are
undeciphered: there is no reading pipeline, only exploratory, clearly labelled
structural analysis. See [Linear A](Linear-A), [Cypro-Minoan](Cypro-Minoan),
and [Analysis](Analysis).

## See also

- [Greek NLP](Greek-NLP) for what each stage and backend does, in full
- [Benchmarks](Benchmarks) for the measured numbers and the evaluation protocol
- [Reading a Parse](Reading-a-Parse) for interpreting a record and its evidence class
- [Using Critical Editions](Using-Critical-Editions) for restored and lost readings
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong) for the export, fix, and re-import review loop
