# For specialists

This page is for Aegean epigraphers, Mycenologists, classical philologists, and
historical linguists. It defines the boundary between established scholarship,
measured model performance, and machine-generated hypotheses, and documents how
to audit outputs, cite underlying editions, and submit corrections or sourced
facts.

If you are new to Python, start with [Getting Started](Getting-Started). Every
example below runs as written.

---

## 1. Established facts, measured scores, and exploratory output

pyaegean separates settled scholarship from machine-generated hypotheses and
tags every output with its evidence tier. Linear A material is never presented
as a translation; when the AI layer generates a hypothesis, an exploratory label
travels with the text.

| Register | Scope | Marking | What a wrong result means |
|---|---|---|---|
| **Established** | Facts carried from editions, lexica, and Unicode: Linear B and Cypriot sign values, Greek lexicon and morphology (Perseus AGDT, LSJ), bundled transliterations, and the find-site gazetteer. | Source citations via `info`/`cite`, [Data & Provenance](Data-and-Provenance), and `NOTICE`. | A **correction** against the source. |
| **Measured** | Model accuracies evaluated on held-out folds without training leakage (Greek lemmatizer, tagger, parser, and joint neural pipeline). | Reproducible protocol and figures in [Benchmarks](Benchmarks) and [Methodology](Methodology). | A **reproduction or challenge** to the measurement. |
| **Exploratory** | Analytical output over undeciphered scripts (cross-linguistic distances, morphological clusters, structure heuristics, metrological estimates) and all AI-layer output. | `[EXPLORATORY …]` prefix, `exploratory=True` flag, red Jupyter badge, and auditable `trace()`. | A **validation** (confirmation or refutation). |

Limits imposed by evidence, licensing, engineering scope, and deliberate
trade-offs are catalogued on [Limitations](Limitations).

### Editorial certainty in the data model

Every token carries a `ReadingStatus` following Leiden and EpiDoc conventions so
editorial apparatus survives into analysis:

| `ReadingStatus` | Meaning | EpiDoc / Leiden |
|---|---|---|
| `certain` | Securely read (default) | — |
| `unclear` | Damaged but legible | `<unclear>` / underdot |
| `restored` | Editorially supplied | `<supplied>` / `[ ]` |
| `lost` | Not preserved / lacuna | `<gap>` or `<supplied reason="undefined">` / `[---]` |

Bundled corpora are normalized transcriptions: most tokens are `certain`, with
`lost` and `unclear` preserved where upstream editions retain damage markers.
Token-carrier EpiDoc imports populate these statuses from XML markup and
round-trip them back out; see [Linear A](Linear-A) and
[Data & Provenance](Data-and-Provenance). Arbitrary free-text TEI requires a
source-specific extractor. Object fields and extension invariants are documented
on [Data Model](Data-Model).

```python
from collections import Counter
import aegean

corpus = aegean.load("lineara")
counts = Counter(t.status.value for d in corpus for t in d.tokens)
print(dict(counts))
# {'certain': 5734, 'lost': 552, 'unclear': 120}   (~10.5% lost or unclear)
```

---

## 2. Checking provenance before using a corpus

Inspect a corpus's source, license, and citation before incorporating its output
into research.

**CLI**

```bash
aegean info lineara
```

```
                            aegean corpus: lineara
 documents          1721
 words              1381
 tokens             6406
 signs_in_inventory 342
 source             GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz
 license            Apache-2.0 (corpus JSON); facsimile imagery © École
                    Française d'Athènes, not redistributed
 citation           Godart, L. & Olivier, J.-P. (1976–1985). Recueil des
                    inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```

**Python**

```python
import aegean

corpus = aegean.load("lineara")
p = corpus.provenance
print(p.source)    # 'GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz'
print(p.license)   # 'Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed'
print(p.cite())    # one-line citation with edition and URL
```

The bundled `linearb` dataset is an 18-tablet illustrative sample for offline
use, not a full corpus; `aegean info linearb` states this explicitly:

```bash
aegean info linearb
# … license: Sign data from the Unicode Character Database (Unicode-3.0).
#            Sample transliterations are scholarly facts, bundled as illustrative
#            excerpts — not a corpus.
```

For full Mycenaean corpus work, fetch DAMOS on demand (`aegean.load("damos")`,
5,932 tablets, CC BY-NC-SA 4.0) or load a local edition such as LiBER; see
[Data & Provenance](Data-and-Provenance) and [Limitations](Limitations).

---

## 3. Inspecting established data

### Sign inventories

Each syllabic sign resolves to its glyph, Unicode codepoint, conventional sound
value (when known), and script-specific attributes. Because these tables derive
from Unicode and standard editions, any error is a correction (§6.1).

**CLI**

```bash
aegean sign linearb KU
```

```
                 linearb sign KU
 label             KU
 glyph             𐀓
 codepoint         U+10013
 phonetic          ku
 attrs.bennett     B081
 attrs.unicodeName LINEAR B SYLLABLE B081 KU
 attrs.signClass   syllabogram
 attrs.commodity   None
```

```bash
aegean sign lineara DA --json
```

```json
{
  "label": "DA",
  "glyph": "𐘀",
  "codepoint": "U+10600",
  "phonetic": "da",
  "attrs": {
    "sharedWithLinearB": true,
    "linearAOnly": false,
    "total": 40,
    "confidence": 1,
    "altGlyphs": []
  }
}
```

**Python**

```python
import aegean

inv = aegean.load("linearb").sign_inventory
sign = inv.by_label("KU")
print(sign.glyph, sign.codepoint, sign.phonetic)   # 𐀓 65555 ku
# also: inv.by_glyph("𐀓"), inv.by_codepoint(0x10013)
```

Bundled sign inventory counts:

| Script | Signs | Notes |
|---|---|---|
| `lineara` | 342 | GORILA-derived; 50 carry working sound values with `confidence` and `sharedWithLinearB` attributes |
| `linearb` | 211 | Unicode Character Database (74 syllabograms plus ideograms) |
| `cypriot` | 55 | Classical Cypriot syllabary (all 55 carry sound values) |
| `cyprominoan` | 99 | Undeciphered; 0 sound values |

### Reading deciphered syllabic words as Greek

For deciphered Greek scripts (`linearb` and `cypriot`), the bridge maps attested
syllabic forms to alphabetic Greek lemmas:

```bash
aegean bridge linearb ko-no-so
# ko-no-so → Κνωσός   (Knossos (place in north-central Crete))
```

The bridge accepts only `linearb` and `cypriot`. Linear A has no Greek bridge
because the script is undeciphered; speculative comparisons live strictly in the
exploratory AI layer (§5). See [Linear A](Linear-A) and [Cypriot](Cypriot).

### Deterministic Greek rules

Rule-based Greek utilities (syllabification, accent classification, scansion)
implement standard grammar and metrical rules (Smyth and standard editions).
Statistical and neural taggers, lemmatizers, and parsers belong to the measured
tier; their held-out accuracy is reported on [Benchmarks](Benchmarks). See
[Greek NLP](Greek-NLP) and [Meters](Meters) for full coverage.

```python
from aegean import greek

greek.syllabify("εἰσφέρω")                    # ['εἰσ', 'φέ', 'ρω']  (compound, Smyth §140)
greek.accentuation("λόγος").classification    # 'paroxytone'
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

Pure phonotactics would divide `εἰσφέρω` as `εἰ-σφέ-ρω`; the etymological split
`εἰσ-φέ-ρω` comes from the curated compound exception list (§6.3).

---

## 4. Citing editions and subsets

In published work, cite the underlying scholarly edition alongside the tool
version. Three entry points format citations and automatically record active
filters or queries:

| Target | Call | Formats |
|---|---|---|
| Full corpus | `Corpus.cite(style=…)` / `aegean cite <id>` | `plain`, `bibtex`, `apa` |
| Filtered subset | `corpus.filter(...).cite()` / `aegean cite <id> --site …` | Same; note records the filter |
| Query results | `QueryResults.cite(style=…)` | Same; note records the query |
| Raw provenance | `corpus.provenance.cite()` / `.bibtex()` / `.apa()` | — |

**CLI**

```bash
aegean cite lineara
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz

aegean cite lineara --style bibtex
# @misc{lineara-corpus,
#   title = {Godart, L. \& Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.},
#   year = {1976},
#   url = {https://github.com/mwenge/lineara.xyz},
#   note = {License: Apache-2.0 (corpus JSON); … . Accessed via pyaegean},
# }

aegean cite lineara --site "Haghia Triada"
# … Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
#   [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
```

The subset note lets a reviewer verify that a count rests on 1,110 Haghia Triada
tablets rather than all 1,721 inscriptions. `aegean cite` accepts `--site`,
`--period`, `--scribe`, and `--support`.

**Python**

```python
import aegean
from aegean.analysis import FilterRow

corpus = aegean.load("lineara")
results = corpus.query([FilterRow(field="site-is", value="Haghia Triada")])
print(results.cite())          # plain text with query and document count
print(results.cite("bibtex"))  # BibTeX @misc{aegean-query, …}
```

pyaegean's own code and structured-data wrappers are Apache-2.0. Underlying
editions and facsimile imagery retain their upstream rights. Facsimile plates
(such as GORILA, © École Française d'Athènes) are never bundled in the wheel;
the optional image mirror is fetched for academic reference under rightsholder
terms. See [Data & Provenance](Data-and-Provenance) and `NOTICE`.

---

## 5. Auditing exploratory output

Every generative call returns an `ExploratoryResult` carrying its label,
prompt provenance, and supplied local evidence.

### AI capabilities

| Capability | Python | CLI | Function |
|---|---|---|---|
| Translate | `ai.translate(text, …)` | `aegean ai translate` | Locally grounded LLM translation |
| Gloss | `ai.gloss(text, …)` | `aegean ai gloss` | Interlinear word-by-word gloss |
| Decipher | `ai.decipher_hypotheses(seq, …)` | `aegean ai hypotheses` | Evidence-linked Linear A hypotheses |
| NLP assist | `ai.nlp_assist(text, …)` | — | Context disambiguation for ambiguous lemmas/POS |
| Ask | `ai.ask(q, grounding=…)` | `aegean ai ask` | Answer constrained to supplied grounding |
| Summarize | `ai.summarize(text, …)` | `aegean ai summarize` | Excerpt summary |
| Extract | `ai.extract(text, schema=…)` | `aegean ai extract` | Structured JSON extraction into `result.data` |

Providers install as optional extras; hosted providers require API keys, while
`local` connects to a local OpenAI-compatible server without a key:

```bash
aegean ai providers
# anthropic
# gemini
# grok
# local
# openai
# openrouter
```

Select a provider with `--provider` (default `anthropic`) and a model with
`--model` or `<PROVIDER>_MODEL`. See [AI Layer](AI-Layer) for installation and
configuration.

### Audit 1: Exploratory labels

```python
from aegean import ai

client = ai.get_client("anthropic")
r = ai.decipher_hypotheses("KU-RO", client=client)
print(r.labeled())
# [EXPLORATORY · decipher · anthropic/<model>]
# <hypotheses>
```

In Jupyter notebooks, `ExploratoryResult` renders with a red **EXPLORATORY**
badge above the output and its grounding items listed below.

### Audit 2: Inspecting grounding with `trace()`

`trace()` groups every local fact passed to the model by source and reference so
a reviewer can check whether the output follows from the supplied evidence. The
example below uses a deterministic stub client; hosted providers emit the same
trace structure.

```python
from aegean import ai

g = [
    ai.GroundingItem("KU-RO appears before a numeral at line end",
                     source="analysis:position", ref="KU-RO"),
    ai.GroundingItem("the preceding entries sum to that numeral",
                     source="analysis:balance", ref="KU-RO"),
]
r = ai.decipher_hypotheses("KU-RO", grounding=g, client=client)
print(r.trace())
```

```
EXPLORATORY decipher via stub/stub-1 (prompt 2026.10-v5)
  grounded in 2 item(s) from 2 source(s):
  • analysis:balance (1):
      - the preceding entries sum to that numeral [evidence: {"ref": "KU-RO", "source": "analysis:balance", "status": "unclassified"}]
  • analysis:position (1):
      - KU-RO appears before a numeral at line end [evidence: {"ref": "KU-RO", "source": "analysis:position", "status": "unclassified"}]
```

On the CLI, pass `--trace`:

```bash
aegean ai hypotheses "KU-RO" --corpus lineara --trace
```

If a trace prints **`grounding: none (ungrounded generation — weigh accordingly)`**,
the model answered solely from its training weights without local evidence.
Three local, non-generative helpers build grounding lists:

| Helper | Source tag | Local evidence |
|---|---|---|
| `ai.corpus_context(corpus)` | `corpus:<id>` | Most frequent words in `corpus` |
| `ai.lexicon_evidence(words)` | `lexicon:LSJ` | Short LSJ gloss per word (requires `greek.use_lsj()`) |
| `ai.cooccurrence_evidence(corpus, word)` | `analysis:cooccurrence` | Words sharing documents with `word` |

`wrap_untrusted()` delimits external source text as data and instructs the model
to ignore instructions inside it. Prompt delimiters cannot guarantee resistance
to prompt injection; always verify outputs against the supplied evidence.

### Audit 3: Measuring grounding fidelity

The AI evaluation harness tests providers on fixed cases with known grounding,
measuring **groundedness** (use of supplied evidence) and **fabrication rate**
(unsupported claims):

```bash
aegean ai eval --provider anthropic
# grounded-generation eval: 3 case(s) · groundedness 1.00 · fabrication rate 0.00
```

```python
from aegean import ai

report = ai.run_eval(ai.DEFAULT_CASES, client)
print(report.summary())
# grounded-generation eval: 3 case(s) · groundedness 1.00 · fabrication rate 0.00
for c in report.cases:
    print(c.name, c.groundedness, c.clean, c.missing, c.fabricated)
```

Built-in cases:

| Case | Check |
|---|---|
| `lsj-gloss-recall` | Reports the supplied LSJ gloss without inventing an unrelated meaning |
| `linear-a-total-context` | Hypothesizes "total" from accounting evidence while avoiding certainty language (`deciphered`, `certainly means`) |
| `declines-without-evidence` | Reports insufficient evidence when given no grounding instead of inventing an etymology |

Custom `GroundingCase` objects (`must_use` / `must_avoid` strings) can be passed
to `ai.run_eval`. Scoring uses case-insensitive substring matching: it screens
for overt failures and does not evaluate semantic nuance. See
[AI Layer](AI-Layer).

---

## 6. Corrections, validations, contributions, and reproduction

To correct automated annotations in your own working copy first, see
[When the Tool Is Wrong](When-the-Tool-Is-Wrong). For citing
computationally assisted results, see
[Citing Computational Assistance](Citing-Computational-Assistance). To report
findings upstream, use one of the four GitHub issue forms (New issue → pick a
template). Contributed facts retain their source attribution.

| Path | When to use | Required details | Outcome |
|---|---|---|---|
| **Correction** | A reading, gloss, lemma, sign value, or bridge entry is wrong | Exact value and published source | Verified fix in code or bundled JSON with a regression test |
| **Validation** | Confirming or refuting an exploratory output | Result and (if AI) its `trace()` | Recorded in [Limitations](Limitations) or a benchmark case |
| **Data contribution** | Adding a single sourced fact | Fact and citation | Added to bundled lexicon/JSON with citation and test |
| **Reproduction discrepancy** | Public receipt, digest, or benchmark protocol fails to match | Exact versions, hashes, environment, expected/observed output, and local edits | Investigation of the evidence or implementation |

Pull requests are also welcome; see the
[contribution menu](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#good-first-contributions-a-menu)
for target files and test requirements.

### 6.1 Filing a correction

An error in established data (sign value, gloss, lemma, coordinate) is a bug.
Provide the corrected value and its published authority. Common target files:

| Correction type | File |
|---|---|
| Sign sound value, variant glyph, or attribute | `src/aegean/data/bundled/<script>/signs.json` |
| Missing Pleiades ID for a find-site | `src/aegean/data/bundled/geo/site_coordinates.json` (include Pleiades URI) |
| Missing closed-class Greek form (article, particle, pronoun) | `src/aegean/greek/pos.py` |

### 6.2 Filing a validation

Refutations of exploratory outputs carry the same weight as confirmations.
Include `trace()` so reviewers can inspect the exact local evidence supplied to
the model. Validated findings are logged on [Limitations](Limitations) or folded
into evaluation cases where reusable.

### 6.3 Contributing a sourced fact

Single sourced facts can be added directly with automated checks. For example,
tests for `_EXCEPTIONS` in `src/aegean/greek/syllabify.py` reject any entry that
the rule engine already divides identically:

```python
from aegean import greek

greek.syllabify("προσφέρω")   # ['προσ', 'φέ', 'ρω']  (curated compound exception, Smyth §140)
```

| Contribution | File | Automated guard |
|---|---|---|
| Syllabification exception | `_EXCEPTIONS` in `src/aegean/greek/syllabify.py` | Rejoins to the original word and differs from phonotactic rules |
| Sign-inventory entry | `src/aegean/data/bundled/<script>/signs.json` | Inventory round-trips; sourced value |
| Gazetteer alignment (Pleiades ID) | `src/aegean/data/bundled/geo/site_coordinates.json` | Valid coordinates and URI |
| Association / collocation measure | `src/aegean/analysis/collocation.py` | Golden-value test and literature citation |
| Closed-class Greek form | `src/aegean/greek/pos.py` | Lexicon coverage test |
| Benchmark sentence (gold lemma/POS) | `aegean.greek.benchmark` | Scored in harness; edition cited |

Open an issue first for architectural or multi-file changes.

### 6.4 Reporting a reproduction discrepancy

Start with the bounded verification script on
[Independent Review](Independent-Review). If a receipt, digest, or benchmark
protocol disagrees with the published record, open the reproduction-discrepancy
issue form with the package version, commit or source-archive hash, manifest and
result digests, environment details, expected and observed output, and any local
modifications. The bounded script does not execute the neural model; neural
discrepancies must specify the full model asset, dataset, and scorer protocol.

### Bringing your own corpus

You can use local texts immediately without waiting for upstream inclusion.
`Corpus.from_records(...)` builds a `Corpus` from plain dictionaries (`id`, text
as `lines`/`words`/`text`, optional per-token `status`/`alt`, and `meta`) and
accepts a `Provenance` object so exports and citations carry your edition
metadata. For plain text or CSV inputs, `aegean.io.from_text*`, `from_csv`, and
`aegean import` construct the same `Corpus` directly. See [Tutorial](Tutorial)
and [Data & Provenance](Data-and-Provenance).

---

## Limitations

- **Linear A and Cypro-Minoan are undeciphered.** The toolkit does not read
  them. AI outputs are labeled hypotheses with traces, and accounting or
  structural analyses report sign patterns rather than meanings.
- **Bundled Linear B is an 18-tablet sample.** Full Mycenaean work uses fetched
  DAMOS (`aegean.load("damos")`) or a local edition such as LiBER, each under
  its own license.
- **Measured accuracy is not a guarantee on new texts.** Neural Greek scores
  come from held-out folds under a fixed protocol; see [Benchmarks](Benchmarks)
  and [Greek NLP](Greek-NLP).
- **AI output is exploratory.** Hosted providers require an API key; `local`
  runs without one. The eval harness checks grounding fidelity, not scholarly
  truth.
- **Imagery and large or restricted corpora are fetched on demand** under their
  rightsholders' licenses rather than bundled in the wheel.

See [Limitations](Limitations) for the full register.

---

**See also:** [Getting Started](Getting-Started) · [Greek NLP](Greek-NLP) ·
[Meters](Meters) · [Linear A](Linear-A) · [Analysis](Analysis) ·
[AI Layer](AI-Layer) · [Data & Provenance](Data-and-Provenance) ·
[Limitations](Limitations) · [CLI](CLI)
