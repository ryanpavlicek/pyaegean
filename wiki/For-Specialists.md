# For specialists

This page is for the people pyaegean most wants to hear from: Aegean
epigraphers, Mycenologists, classical philologists, historical linguists. It
explains the one thing that matters most for trusting a result: **the line
between settled scholarship and machine-generated hypothesis**, and then gives
you the concrete tools to *audit* a result, *cite* it correctly, and *correct or
extend* the toolkit where your judgement says it's wrong. Your corrections are
part of how it stays honest.

If you're brand new to running Python, start with [Getting Started](Getting-Started)
and come back here; nothing below requires you to be a developer, and every
example is copy-pasteable.

---

## 1. What is established vs. exploratory

pyaegean draws a hard line between settled scholarship and machine-generated
hypotheses, and labels every result accordingly. The toolkit will *never* hand
you a Linear A "translation" dressed up as fact, and where it does generate a
reading, the exploratory tag travels with the text.

There are three registers:

| Register | What it covers | How it's marked | If it's wrong, it's a… |
|---|---|---|---|
| **Established** | Facts carried from editions, lexica, and the Unicode standard: Linear B / Cypriot sign values, the Greek lexicon & morphology (Perseus AGDT, LSJ), bundled transliterations, the find-site gazetteer. | Each cites its source: see `info`/`cite`, [Data & Provenance](Data-and-Provenance), and `NOTICE`. | **correction** |
| **Measured** | Model accuracies reported leakage-free on held-out data (the Greek lemmatizer/tagger/parser and the neural pipeline). | Numbers with a reproducible protocol in [Greek NLP](Greek-NLP) / `docs/benchmarks.md`. | **reproduce or challenge** the number |
| **Exploratory** | Anything decipherment-adjacent over the **undeciphered** Linear A material (cross-linguistic distances, morphological clusters, structure heuristics, metrological guesses) and **all** AI-layer output. | An explicit `[EXPLORATORY …]` tag, an `exploratory=True` flag, a red badge in Jupyter, and an auditable `trace()`. | **validation** (confirm or refute) |

The full, candid register of what the toolkit can and cannot claim: by
evidence, licensing, engineering, and design: is the [Limitations](Limitations)
page, kept current as a living document.

### Seeing the boundary in the data model

Every token carries an **editorial certainty** following Leiden / EpiDoc
conventions, so the apparatus of an edition survives into the toolkit. The four
states are exhaustive:

| `ReadingStatus` | Meaning | EpiDoc / Leiden |
|---|---|---|
| `certain` | securely read (the default) |— |
| `unclear` | damaged but read | `<unclear>` / underdot |
| `restored` | editorially supplied | `<supplied>` / `[ ]` |
| `lost` | not preserved / lacuna | `<gap>` / `[---]` |

The bundled corpora are normalized transcriptions (mostly `certain`, with a
real fraction `lost`/`unclear` where the originals are damaged).
If you bring your own EpiDoc, these are populated from the markup and round-trip
back out: see [Linear A](Linear-A) and the I/O notes on [Data & Provenance](Data-and-Provenance).

```python
import aegean
from aegean.core.model import ReadingStatus

corpus = aegean.load("lineara")
# How much of the bundled material is securely read vs. damaged/restored?
from collections import Counter
counts = Counter(t.status.value for d in corpus for t in d.tokens)
print(dict(counts))
# {'certain': 5734, 'lost': 552, 'unclear': 120}   ← ~10.5% lost/unclear
```

---

## 2. Checking provenance before you trust a number

Before any result feeds your work, ask the corpus where it came from. There's a
one-line CLI answer and a programmatic one.

**CLI**

```bash
aegean info lineara
```

```
                            aegean corpus: lineara
 documents          1721
 words              1381
 tokens             6406
 signs_in_inventory 344
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
print(p.cite())    # one-line citation, edition + URL
```

A crucial honesty note that `info` makes explicit: the **Linear B** sample is
*not a corpus*: it's an illustrative excerpt of canonical tablets, with sign
data from the Unicode Character Database. Treat it accordingly:

```bash
aegean info linearb
# … license: Sign data from the Unicode Character Database (Unicode-3.0).
#            Sample transliterations are scholarly facts, bundled as illustrative
#            excerpts — not a corpus.
```

For full-corpus Mycenaean work, bring your own (DAMOS, LiBER): see
[Data & Provenance](Data-and-Provenance) and [Limitations](Limitations).

---

## 3. Looking up an established fact (and finding what to correct)

### Sign values

Every syllabic sign resolves to its glyph, codepoint, sound value, and
script-specific attributes. This is **established** data with a Unicode/edition
source, so a wrong value here is a *correction*, with a path in §6.

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
    "total": 23,
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

Inventory sizes (signs reported by `info`):

| Script | Signs in inventory | Notes |
|---|---|---|
| `lineara` | 344 | GORILA-derived; `attrs` carry `sharedWithLinearB`, `total`, `confidence` |
| `linearb` | 211 | sign data from the Unicode Character Database |
| `cypriot` | (inventory bundled) | classical Cypriot syllabary |
| `cyprominoan` | (inventory bundled) | undeciphered; treat readings as exploratory |

### Reading a *deciphered* syllabic word as Greek

For the deciphered scripts (Linear B, Cypriot) there's a **Greek-reading
bridge**: established because Linear B *is* Greek. This is one of the few places
a syllabic word maps to a real Greek lemma:

```bash
aegean bridge linearb ko-no-so
# ko-no-so → Κνωσός   (Knossos (place in north-central Crete))
```

The bridge only accepts `linearb` or `cypriot`. There is deliberately **no
bridge for Linear A**: it is undeciphered, and anything in that direction lives
in the exploratory AI layer (§5), never here. See [Linear A](Linear-A) and
[Cypriot](Cypriot) for the script-by-script story.

### Greek established facts

The Greek side carries the established lexicon and morphology. The rule-based
pieces (syllabification, accent class, scansion) are deterministic and citable to
Smyth/standard editions; the *neural* tagger/parser/lemmatizer is **measured**,
not established (its accuracy is a reproducible number, not a fact). Full
coverage is on [Greek NLP](Greek-NLP) and [Meters](Meters); a taste:

```python
from aegean import greek
greek.syllabify("εἰσφέρω")                    # ['εἰσ', 'φέ', 'ρω']  (compound, Smyth §140)
greek.accentuation("λόγος").classification    # 'paroxytone'
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

That `εἰσφέρω` split is exactly the kind of curated exception you can contribute
to (§6.3): pure phonotactics would give `εἰ-σφέ-ρω`; the correct division
`εἰσ-φέ-ρω` is a hand-entered, sourced fact.

---

## 4. Citing correctly — cite the edition, not the convenience layer

When a result feeds academic work, cite the **underlying edition**, not
pyaegean's wrapper. Three call sites produce a ready reference, and all of them
record the *exact subset* you used.

| What you used | Call | Styles |
|---|---|---|
| A whole corpus | `Corpus.cite(style=…)` / `aegean cite <id>` | `plain`, `bibtex`, `apa` |
| A filtered subset | `corpus.filter(...).cite()` / `aegean cite <id> --site …` | same: note records the filter |
| A query result set | `QueryResults.cite(style=…)` | same: note records the query |
| The raw provenance | `corpus.provenance.cite()` / `.bibtex()` / `.apa()` |— |

**CLI: plain, BibTeX, and a subset**

```bash
aegean cite lineara
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz

aegean cite lineara --style bibtex
# @misc{lineara-corpus,
#   title = {Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.},
#   year = {1976},
#   url = {https://github.com/mwenge/lineara.xyz},
#   note = {License: Apache-2.0 (corpus JSON); … . Accessed via pyaegean},
# }

aegean cite lineara --site "Haghia Triada"
# … Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
#   [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
```

The subset note is the point: a reviewer can see you cited *1110 Haghia Triada
documents*, not "the corpus." The `aegean cite` filter flags are `--site`,
`--period`, `--scribe`, `--support`.

**Python: a query result set cites itself**

```python
import aegean
from aegean.analysis import FilterRow

corpus = aegean.load("lineara")
results = corpus.query([FilterRow(field="site-is", value="Haghia Triada")])
print(results.cite())          # plain, with a "query: … → N inscriptions" note
print(results.cite("bibtex"))  # the same, as a @misc{aegean-query, …}
```

The package's own structured-data layer is **Apache-2.0**; the scholarly
editions and imagery remain under their own rights. Facsimile imagery (e.g. the
GORILA plates, © École Française d'Athènes) is **referenced, never
redistributed**. See [Data & Provenance](Data-and-Provenance) and `NOTICE` for
the full per-source rights table.

---

## 5. Validating an exploratory result

Exploratory output is only as good as the evidence under it, so the toolkit
makes that evidence *visible*. Every AI capability returns an `ExploratoryResult`
you can audit three ways.

### The AI capabilities (all exploratory, all grounded)

| Capability | Python | CLI | Purpose |
|---|---|---|---|
| Translate | `ai.translate(text, …)` | `aegean ai translate` | hybrid local-grounding → LLM translation |
| Gloss | `ai.gloss(text, …)` | `aegean ai gloss` | interlinear word-by-word gloss |
| Decipher | `ai.decipher_hypotheses(seq, …)` | `aegean ai hypotheses` | cautious Linear A hypotheses, each tied to evidence |
| NLP assist | `ai.nlp_assist(text, …)` |— | disambiguate lemma/POS where the rules are unsure |
| Ask | `ai.ask(q, grounding=…)` | `aegean ai ask` | answer **only** from supplied grounding |
| Summarize | `ai.summarize(text, …)` |— | faithful summary of an excerpt |
| Extract | `ai.extract(text, schema=…)` | `aegean ai extract` | structured JSON into `result.data` |

Providers are optional extras, key-gated; the registered set is fixed:

```bash
aegean ai providers
# anthropic   (default)
# gemini
# grok
# openai
# openrouter
```

Pick one with `--provider`; the model is `--model` or a `<PROVIDER>_MODEL` env
var (point `ANTHROPIC_MODEL` at the latest flagship). See [AI Layer](AI-Layer)
for keys and the [anthropic] / [openai] / [grok] / [gemini] / [openrouter] extras.

### Audit #1 — the exploratory label travels with the text

```python
from aegean import ai
# (any client; a real one needs pyaegean[anthropic] + a key)
client = ai.get_client("anthropic")              # exploratory result below
r = ai.decipher_hypotheses("KU-RO", client=client)
print(r.labeled())
# [EXPLORATORY · decipher · anthropic/<model>]
# <the hypotheses>
```

In Jupyter the same result renders with an unmissable red **EXPLORATORY** badge
and its grounding listed beneath.

### Audit #2 — `trace()` shows the exact local facts it rested on

This is the heart of validation: a refutation is only fair if you can see what
the model was *given*. `trace()` groups the grounding by source and ref. (Shown
here driven by a deterministic stub so the output is reproducible: a real
provider produces the same trace structure.)

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
EXPLORATORY decipher via stub/stub-1 (prompt 2026.06-v1)
  grounded in 2 item(s) from 2 source(s):
  • analysis:balance (1):
      - the preceding entries sum to that numeral
  • analysis:position (1):
      - KU-RO appears before a numeral at line end
```

On the CLI, add `--trace`:

```bash
aegean ai hypotheses "KU-RO" --corpus lineara --trace
# <hypotheses>
# EXPLORATORY decipher via … — grounded in N item(s) from M source(s): …
```

If a trace says **`grounding: none (ungrounded generation — weigh accordingly)`**,
the answer rested on the model's parametric knowledge alone: discount it
heavily. The grounding helpers that *fill* a trace, all local and
non-generative:

| Helper | Source tag | What it grounds on |
|---|---|---|
| `ai.corpus_context(corpus)` | `corpus:<id>` | the corpus's most frequent words |
| `ai.lexicon_evidence(words)` | `lexicon:LSJ` | a short LSJ gloss per word (needs `greek.use_lsj()`) |
| `ai.cooccurrence_evidence(corpus, word)` | `analysis:cooccurrence` | words that share a document with `word` |

`wrap_untrusted()` is applied to all source text automatically, so directives
hidden inside an inscription you're analysing can't steer the model
(prompt-injection awareness).

### Audit #3 — measure grounding fidelity like an accuracy number

The generative layer's value rests on **grounding fidelity**, not authority, so
it's measured the way the lemmatizer is: fixed cases, known evidence, scored for
two things: **groundedness** (did the answer use the evidence it should?) and
**fabrication** (did it assert anything the evidence doesn't support?).

```bash
aegean ai eval --provider anthropic
# grounded-generation eval: 3 case(s) · groundedness 1.00 · fabrication rate 0.00
# (a table of per-case grounded / clean / missing / fabricated follows)
```

Programmatically, the same harness with the built-in cases (here against a
faithful stub, reproducible offline):

```python
from aegean import ai
report = ai.run_eval(ai.DEFAULT_CASES, client)
print(report.summary())
# grounded-generation eval: 3 case(s) · groundedness 1.00 · fabrication rate 0.00
for c in report.cases:
    print(c.name, c.groundedness, c.clean, c.missing, c.fabricated)
```

The three built-in cases are themselves instructive: they encode what *faithful*
looks like:

| Case | What it checks |
|---|---|
| `lsj-gloss-recall` | reports the supplied LSJ gloss, doesn't invent an unrelated meaning |
| `linear-a-total-context` | hypothesises "total" from accounting evidence **and stays tentative** (must avoid "deciphered", "certainly means") |
| `declines-without-evidence` | with no grounding, says the evidence is "insufficient" rather than inventing an etymology |

Write your own `GroundingCase` objects (with `must_use` / `must_avoid` strings)
and pass them to `run_eval` to hold a provider to *your* standard before you
trust its output. Scoring is deliberately transparent (case-insensitive
substring containment): a screen for gross failure, not a semantic judge. More
on [AI Layer](AI-Layer).

---

## 6. How to help — corrections, validations, contributions

Three lightweight paths, each a GitHub issue form (New issue → pick a template).
Attribution is **first-class**: contributed facts keep their source.

| Path | When | What to include | Where it lands |
|---|---|---|---|
| **Correction** | a reading, gloss, lemma, sign value, or translation is wrong | the exact value + a source | a verifiable fix in the codebase or a bundled JSON, with a test |
| **Validation** | confirm or refute an exploratory result | the result and (ideally) its `trace()` | the limitations register or a benchmark item |
| **Data contribution** | a single sourced fact | the fact + its citation | a bundled lexicon/JSON with the citation and an automatic test |

A pull request is welcome too: the [contribution menu](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#good-first-contributions-a-menu)
gives each kind of fact an obvious home and an automatic test.

### 6.1 File a correction

A wrong **established** fact (a sign value, a gloss, a lemma) is a correction.
Point to the exact value and give a source; it becomes a one-line fix plus a
test. The relevant homes:

| Kind of correction | File |
|---|---|
| Sign sound value / variant glyph / attribute | `src/aegean/data/bundled/<script>/signs.json` |
| Find-site missing a Pleiades ID | `src/aegean/data/bundled/geo/site_coordinates.json` (cite the Pleiades URI) |
| Missing closed-class Greek form (article/particle/pronoun) | `src/aegean/greek/pos.py` |

### 6.2 File a validation

Pick an exploratory result and try to break it. A **refutation is as valuable as
a confirmation**: pasting the `trace()` lets others see the same evidence and
agree or disagree. Confirmed/refuted results are triaged into the
[Limitations](Limitations) register or, where they become reusable, into a
benchmark item.

### 6.3 Contribute a sourced fact

A single, well-scoped fact that improves coverage without touching the
architecture. Each has an obvious home **and an automatic test**: for example,
the syllabification exception lexicon rejects any entry the rules already get
right (so you can only add real exceptions):

```python
# a compound that pure phonotactics would missplit (Smyth §140):
from aegean import greek
greek.syllabify("προσφέρω")     # ['προσ', 'φέ', 'ρω']  — a curated exception
# add new ones to _EXCEPTIONS in src/aegean/greek/syllabify.py with the division
```

The menu of one-fact contributions:

| Contribution | Home | Test that guards it |
|---|---|---|
| Syllabification exception | `_EXCEPTIONS` in `greek/syllabify.py` | must rejoin to the form **and** differ from the rule engine |
| Sign-inventory fact (value/glyph/attr) | `data/bundled/<script>/signs.json` | inventory round-trips; value sourced |
| Gazetteer alignment (Pleiades ID) | `data/bundled/geo/site_coordinates.json` | coordinate/ID validity |
| Association / statistics measure | `analysis/collocation.py` | golden-value test + literature reference |
| Closed-class Greek form | `greek/pos.py` | lexicon coverage |
| Benchmark sentence (gold lemma/POS) | `aegean.greek.benchmark` | scored against the harness; cite the edition |

For anything larger than a single fact, open an issue first so the design can be
agreed before code is written.

### A word on bringing your own corpus

You don't have to wait for a contribution to land to use your own material with
the full API. `Corpus.from_records(...)` turns plain dict records (with `id`,
text as `lines`/`words`/`text`, optional per-token `status`/`alt`, and `meta`)
into a `Corpus` that filters, queries, exports, and cites like the bundled ones:
and you can attach your own `Provenance` so citations stay honest. If your
material is already plain text or a CSV, the `aegean.io.from_text*` / `from_csv`
importers (and the `aegean import` CLI) build the same `Corpus` for you in one
step, without the `from_records` boilerplate. See [Tutorial](Tutorial) and
[Data & Provenance](Data-and-Provenance).

---

## Honest limitations

- **Linear A is undeciphered.** Nothing in the toolkit reads it; the AI layer
  offers *hypotheses* with traces, never translations. The accounting/structure
  analyses are pattern observations, not meanings.
- **The bundled Linear B is a sample, not a corpus** (see §2). Full Mycenaean
  work is bring-your-own (DAMOS, LiBER), which carry their own licences.
- **Measured ≠ established.** The neural Greek pipeline's accuracy is a number on
  held-out data, reproducible but not a guarantee on your text: check
  [Greek NLP](Greek-NLP).
- **AI output is exploratory by construction** and depends on a third-party
  provider and your key; the eval harness measures fidelity, not correctness.
- **Imagery and several corpora are referenced, not redistributed**, under their
  rightsholders' licences.

The complete, candid version of all of this is the [Limitations](Limitations)
page. If you find a gap there, that itself is a welcome correction.

---

**See also:** [Getting Started](Getting-Started) · [Greek NLP](Greek-NLP) ·
[Meters](Meters) · [Linear A](Linear-A) · [Analysis](Analysis) ·
[AI Layer](AI-Layer) · [Data & Provenance](Data-and-Provenance) ·
[Limitations](Limitations) · [CLI](CLI)
