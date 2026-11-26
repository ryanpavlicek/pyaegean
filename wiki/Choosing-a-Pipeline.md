# Choosing a Pipeline

pyaegean offers several ways to tag, lemmatize, parse, and gloss Ancient Greek,
from a zero-dependency rule baseline to an opt-in neural model. No single
backend fits every task. Choose according to your source material (clean
digital edition, damaged inscription, OCR scan) and your constraints (accuracy,
dependencies, speed, inspectability, or lexical coverage).

This page maps material types to backends, gives the activation calls, and
states the trade-offs. For stage-by-stage API details, see
[Greek NLP](Greek-NLP); for measured scores and the evaluation protocol, see
[Benchmarks](Benchmarks).

## Inspect first: `greek.profile_text`

Before choosing a backend, inspect the input string with `greek.profile_text`:

```python
from aegean import greek

profile = greek.profile_text("ἐν ἀρχῇ ἦν ὁ λόγος.")
```

`profile_text` reports surface features: detected script, presence or absence
of polytonic accents and breathings, Beta Code indicators, and baseline
resolution rate. It is descriptive only and does not switch backends
automatically.

### Keep input description separate from annotation conventions

`TextProfile` describes characters in the input string. The annotation registry
records provenance separately: `AnnotationProfile` names the output label and
relation convention, while `DomainProfile` records the declared source scope
and layer. Pass each profile explicitly; pyaegean does not infer them from
`TextProfile`. The confidence `domain` label separately scopes calibration
evidence.

Inspect the registry from Python or the shell:

```python
greek.list_annotation_profiles()
greek.list_domain_profiles()
greek.canonical_analysis_profile()
```

```bash
aegean greek annotation-profiles list
aegean greek annotation-profiles show pyaegean-canonical-v1 --json
```

The canonical profile is the supported inference and output convention.
UD-PROIEL and Perseus/AGDT profiles exist for comparison and loss diagnostics;
they do not perform automatic tagset conversion, since POS collapse,
tokenization differences, feature gaps, and dependency shifts are not always
invertible. Separately, `evaluate_on_proiel()`'s native-XML projection strips
`#N` homograph suffixes and omits empty tokens; exact UD-fold scoring skips
that cleanup. For PapyGreek, the `orig` profile changes the diplomatic `FORM`
surface while retaining regularized-layer gold analyses and documented
fallbacks. Receipt schema 3 records any composed output profile and ordered
post-processing chain; older receipt schemas remain readable.

## Material to pipeline

| Material | Start with | Activation call | Trade-off |
| --- | --- | --- | --- |
| **Clean digital text** (edited literary passage or `load_work` corpus) | neural pipeline for measured generalization, or treebank lexicon for attested-gold lemmas without heavy dependencies | `greek.use_neural_pipeline()` / `greek.use_treebank()` | neural pipeline carries published in-domain and out-of-domain scores ([Benchmarks](Benchmarks)) and needs `[neural]` plus a model fetch; treebank stays lightweight and covers attested forms only |
| **Damaged inscription or papyrus** (restorations, lacunae, unclear readings) | any Greek backend on certain text, keeping the reading-status apparatus and reviewing editorial tokens | a backend above, `sentence_policy="inscription"` or `"papyrus"`, `greek.needs_review(...)`, and token `ReadingStatus` | analyses of restored or lost characters depend on editorial restoration; check them against the apparatus ([Using Critical Editions](Using-Critical-Editions)) |
| **OCR or noisy text** | lenient normalization first, then a backend, then review | `greek.normalize(text, lenient=True)`, then a backend | repairs common encoding artifacts and emits warnings; surviving OCR errors still corrupt downstream tags and lemmas |
| **Teaching** | offline baseline plus a concise dictionary | default (no backend), with `greek.use_lexicon("dodson")` or `greek.use_lexicon("middle-liddell")` | inspectable rules with zero extra installs; ordinary words can be mistagged, so verify outputs before using them as answers |
| **Verse or line-oriented material** | any backend with explicit physical-line boundaries | `greek.pipeline(text, sentence_policy="verse")` or `greek.segment_text(text, policy="verse")` | every non-empty physical line ends a sentence; confirm this matches the edition's convention |
| **Benchmarking** | evaluation harness on leakage-checked folds | `greek.evaluate_on_ud(...)` / `greek.bootstrap_ud(...)` | measures live outputs against gold, reporting out-of-domain folds alongside in-family scores ([Benchmarks](Benchmarks)) |

Glossing is independent of tagging: the **dictionary registry** (`use_lsj`,
`use_dodson`, `use_lexicon`) supplies definitions and composes with any tier
above.

## Choose sentence segmentation explicitly

Sentence segmentation is configured per call, independently of the tagger,
lemmatizer, parser, or neural model. The default policy is conservative and
protects dotted abbreviations and numerals. Pick a named policy when your
source uses different boundary conventions:

| Policy | Best fit | Boundary behavior |
| --- | --- | --- |
| `default` | mixed or general text | period, semicolon/Greek question mark, ano teleia/middle dot, `!`, `?`, protecting dotted abbreviations and numerals |
| `prose` | literary prose | same conservative punctuation rules under an explicit name |
| `verse` | lineated verse | prose rules plus every non-empty physical line |
| `inscription` | epigraphic text | strong `.`, `!`, `?` only; weak punctuation stays in the current sentence |
| `papyrus` | papyri with editorial brackets | strong `.`, `!`, `?` only; marks inside balanced `[]`, `⟦⟧`, and `<>` are ignored |

```python
from aegean import greek

result = greek.segment_text(text, policy="papyrus")
records = greek.pipeline(text, sentence_policy="papyrus")
```

`segment_text()` returns exact character spans and a stable `policy_id`; the
older `greek.sentences()` helper returns trimmed strings without terminal
punctuation. For custom rules, pass a `SentenceSegmenter`-compatible object or
callable via `segmenter=`. pyaegean checks that plugin spans are ordered,
non-overlapping, in range, and gap-free across non-whitespace characters, and
rejects boundaries that bisect a token. Built-in policies emit no confidence
score; plugin confidence values in `[0, 1]` are metadata only, not calibrated
probabilities.

In `pipeline_tokens()`, complete contiguous `SourceAlignment.sentence_id` runs
take precedence over punctuation, `sentence_policy`, and plugins. Partial or
non-contiguous sentence IDs raise an error so edition sentence boundaries never
mix with heuristic splits in the same document.

## Backends and trade-offs

| Backend | Activation | Accuracy | Dependencies | Speed | Coverage |
| --- | --- | --- | --- | --- | --- |
| Offline baseline | none (default) | rules and seed tables; can mistag ordinary open-class words | stdlib only | instant import, fast | all tokens, offline |
| Treebank lexicon | `greek.use_treebank()` | gold lemmas and features for attested forms | prebuilt index fetch, cached | instant after fetch | attested forms only |
| Pure-Python trained | `greek.use_tagger()`, then `greek.use_lemmatizer()`, `greek.use_parser()` | generalizes to unseen forms ([Greek NLP](Greek-NLP)) | small model fetch, cached | fast | open-class and unseen forms |
| Neural pipeline | `greek.use_neural_pipeline(variant="default")` | highest measured on UD Perseus ([Benchmarks](Benchmarks)); only `default` is currently shipped | `[neural]` extra (`onnxruntime`, no PyTorch) | model fetch once, CPU or GPU inference ([Greek NLP](Greek-NLP)) | UPOS, UD FEATS, dependency trees, and lemmas in one pass |
| Opt-in neural refinements | `greek.use_oov_lemma_reranker(config="weighted")` and `greek.use_calibration_registry()` | improves unseen/poetic/papyrus lemmas (+0.69 to +3.43 pp across locked folds) and provides calibrated probabilities for `literary` and `documentary_native` | bundled with neural pipeline (no extra download) | zero overhead when inactive | neural pipeline outputs; `grc-joint-v3` weights unchanged |
| Dictionary registry | `greek.use_lsj()`, `greek.use_dodson()`, `greek.use_lexicon(id)` | scholarly lexica | index fetch (Dodson is bundled offline) | instant after fetch | glossing only |
| Manual review | `aegean tui --review` (`r` in `aegean tui`), `aegean review export --layout editable` / `apply`, or `greek.annotate_corpus(...)` | reviewer-verified | `[tui]` for interactive review, `[cli]` for CSV export/apply | human-paced (prioritized via `priority="calibrated_risk"`) | any selected tokens or conflicts |

The `use_*` functions configure the module-level default. For isolated
configurations in servers, notebooks, or tests, construct `GreekPipeline()`
(baseline) or `GreekPipeline.neural()` (neural). Each instance exposes an
immutable `config` recording the model, tokenizer, profile, normalization,
segmentation contract (copied from the model manifest for neural instances),
live execution providers, runtime label, and registry digest. The `fast`,
`compact`, and `balanced` variant names remain reserved until candidate models
pass evaluation gates; requesting an unavailable variant raises an error. The
baseline contract is `pyaegean-punctuation-v1`, whereas neural instances copy
`pretokenized` from the model manifest; neither replaces the per-call
`sentence_policy` argument on `analyze()` or `pipeline()`.
`GreekPipeline.from_config(...)` raises an error if the live runtime differs
from the requested configuration.

For large pre-tokenized sources, call `greek.iter_analyze_sentences(source)`
(or the instance method) to stream results in source order while keeping at
most one `batch_size`-sentence chunk plus the largest sentence in memory.
`analyze_sentences(..., length_bucket=True)` returns a full list while bucketing
similar-length sentences to reduce padding overhead. For large SQLite corpora
requiring crash-safe pause and resume, use `aegean.db.annotate_sqlite_job()`
(`aegean db annotate`).

Key distinctions across tiers:

- **Offline baseline.** Zero third-party dependencies, instant import, and
  explicit rules. Useful for inspecting rule mechanics and teaching the API;
  verify outputs against an edition or stronger backend before citing them.
- **Treebank lexicon.** `use_treebank()` downloads one prebuilt index once and
  serves attested, properly accented lemmas and morphology with no heavy
  dependencies. Unattested forms require the trained or neural backends.
- **Trained pure-Python tiers.** `use_lemmatizer()` depends on POS predictions,
  so call `use_tagger()` first. These generalize to unseen forms without
  requiring ONNX Runtime.
- **Neural pipeline.** One forward pass predicts UPOS, morphology, dependency
  trees, and lemmas. It requires `[neural]` and a one-time model fetch, and runs
  more slowly on CPU than lookup tables. Use it when accuracy is the priority.
- **Token provenance.** Every `TokenRecord` carries `lemma_source` (`attested`,
  `neural_lookup`, `neural_edit`, generic `neural`, `rule`, `seed`, `paradigm`,
  `identity`, `unresolved`, `punct`, or `user`) and `review_recommended` for
  identity/unresolved lemmas. Resolved lemmas and other fields can still be
  wrong; `review_recommended` is not a confidence threshold. `lemma_verified`
  separately marks human-reviewed tokens, and `lemma_source_path` records the
  neural composition path when available. Opt-in `token_confidence` and
  `sentence_confidence` add task, source, and domain scope plus explicit
  unavailability reasons without supplying automatic cutoffs or out-of-domain
  labels. See [Reading a Parse](Reading-a-Parse).

## Material details

**Clean digital text.** Well-edited literary texts benefit most from
`greek.use_neural_pipeline()` for morphology, lemmatization, and syntax. If you
want no heavy dependencies, `greek.use_treebank()` supplies attested lemmas and
features. Add `greek.use_lsj()` or another registry lexicon for definitions.

**Damaged inscriptions and papyri.** The seven epigraphic corpora (`isicily`,
`iip`, `iospe`, `igcyr`, `aphrodisias`, `crete`, `edh`) and `ddbdp` documentary
papyri attach a per-token `ReadingStatus` (`certain`, `unclear`, `restored`,
`lost`) and `Provenance.edition_fidelity`. Run your chosen Greek backend, check
the apparatus, and mark analyses over restored or lost characters as editorial
reconstructions before publishing. See
[Using Critical Editions](Using-Critical-Editions). Search or stream `ddbdp`
with `aegean find` or `aegean.db` instead of loading it all into memory.

**OCR and noisy text.** Run `greek.normalize(text, lenient=True)` first to
repair common OCR and half-converted encoding artifacts (Latin homoglyphs in
Greek words, stray Beta Code marks, orphaned combining diacritics) with a
warning per repair. Surviving OCR errors still degrade downstream predictions,
so review outputs before citing them.

**Teaching.** The offline baseline installs with zero extras, runs identically
across machines, and exposes explicit syllabification, accent, prosody, and
morphology rules so students can inspect each step. Pair it with
`greek.use_lexicon("dodson")` (Koine/NT, bundled offline) or
`greek.use_lexicon("middle-liddell")` (Classical Greek).

**Benchmarking.** Use `greek.evaluate_on_ud(...)` (official CoNLL 2018 scorer
on leakage-checked folds) and `greek.bootstrap_ud(...)` for confidence
intervals, reporting out-of-domain folds (UD-PROIEL, NT) alongside in-family
scores. See [Benchmarks](Benchmarks).

## Aegean syllabic scripts

Linear B and Cypriot are deciphered and provide a Greek-reading bridge
(`greek_reading` / `aegean bridge`); see [Linear B](Linear-B) and
[Cypriot](Cypriot). Linear A and Cypro-Minoan are undeciphered and have no
reading pipeline, only exploratory structural analysis; see
[Linear A](Linear-A), [Cypro-Minoan](Cypro-Minoan), and [Analysis](Analysis).
All four Aegean scripts can be explored visually in the local browser workbench
(`workbench-app-v2.1.0`) via `aegean workbench --corpus <id-or-path>` or
exported with `aegean.io.to_workbench_bundle`.

## See also

- [Greek NLP](Greek-NLP): stage-by-stage API reference
- [Benchmarks](Benchmarks): measured scores and evaluation protocol
- [Reading a Parse](Reading-a-Parse): token fields and `LemmaSource` values
- [Using Critical Editions](Using-Critical-Editions): handling restored and lost
  readings
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): error classes and the
  review loop
