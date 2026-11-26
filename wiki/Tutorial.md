# Tutorial

Three runnable walkthroughs covering **Linear A** accounting, **Homeric Greek**
analysis, and fetching a full **Perseus** text on demand. Every snippet runs
against the current release. If you have not installed pyaegean yet, complete
[Getting Started](Getting-Started) first.

Run the snippets cell by cell in a
[Jupyter notebook](Getting-Started#option-c--jupyter-recommended-for-research)
or at the interactive `python` prompt. Where a step has both a Python call and
a shell command, both appear below. Shell commands require the CLI extra
(`pip install "pyaegean[cli]"`); see [CLI](CLI) for the full command reference.

> **Runnable notebook.** [The getting-started notebook](https://github.com/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)
> can be run locally or in the cloud
> ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)).
> It covers its own examples independently of these walkthroughs.

**The three walkthroughs:**

| # | Question | Track | Network needed? |
| --- | --- | --- | --- |
| [1](#tutorial-1--does-a-3500-year-old-ledger-add-up) | Does a 3,500-year-old ledger add up? | Linear A | No: bundled corpus, offline |
| [2](#tutorial-2--reading-the-first-line-of-the-odyssey) | Reading the first line of the *Odyssey* | Greek | No (treebank step is opt-in) |
| [3](#tutorial-3--pulling-a-real-work-off-the-shelf) | Pulling a real work off the shelf | Greek | Yes: fetches one work to cache once |

---

## Tutorial 1 — Does a 3,500-year-old ledger add up?

Many Linear A tablets are accounts: a list of entries followed by the totaling
word **KU-RO**. This walkthrough loads one tablet, checks its arithmetic, and
queries how `KU-RO` appears across the corpus.

### Load the corpus and inspect one tablet

```python
import aegean

corpus = aegean.load("lineara")     # 1,721 inscriptions, bundled, offline
doc = corpus.get("HT13")            # an accounting tablet from Haghia Triada

[t.text for t in doc.words]
# ['KA-U-DE-TA', 'RE-ZA', 'TE-TU', 'TE-KI', 'KU-ZU-NI', 'DA-SI-*118', 'I-DU-NE-SI', 'KU-RO']

[t.text for t in doc.numerals]
# ['5', '¹⁄₂', '56', '27', '¹⁄₂', '18', '19', '5', '130', '¹⁄₂']
```

The tablet ends with **KU-RO** ("total"), and the numerals include metrological
fractions (`¹⁄₂`).

From the shell, print the same tablet line by line:

```bash
aegean show lineara HT13
```

`aegean info lineara` shows corpus size, source, license, and citation:

```bash
aegean info lineara
# documents          1721
# words              1381
# tokens             6406
# signs_in_inventory 342
# source             GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz
# license            Apache-2.0 (corpus JSON); facsimile imagery © École
#                    Française d'Athènes, not redistributed
# citation           Godart, L. & Olivier, J.-P. (1976–1985). Recueil des
#                    inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```

### Check the arithmetic

`balance_check` sums the line items before a total marker and compares that sum
against the stated total:

```python
from aegean.analysis import balance_check

for chk in balance_check(doc):
    print(chk)
# BalanceCheck(stated_total=130.5, computed_sum=131.0, item_count=6,
#              difference=0.5, balances=False, marker='KU-RO', total_line_index=7,
#              exact_difference=Fraction(1, 2))
```

Each result is a `BalanceCheck` with attributes such as `chk.stated_total`,
`chk.computed_sum`, and `chk.balances`.

From the shell (`--json` emits machine-readable output):

```bash
aegean balance lineara HT13
# ┌──────┬────────┬────────┬──────────┬──────┬──────────┐
# │ doc  │ marker │ stated │ computed │ diff │ balances │
# ├──────┼────────┼────────┼──────────┼──────┼──────────┤
# │ HT13 │ KU-RO  │ 130.5  │ 131.0    │ 0.5  │ NO       │
# └──────┴────────┴────────┴──────────┴──────┴──────────┘

aegean balance lineara HT13 --json
# [{"doc": "HT13", "marker": "KU-RO", "stated": 130.5, "computed": 131.0,
#   "difference": 0.5, "items": 6, "balances": false}]
```

Under this reading the line items sum to **131.0** while the scribe wrote
**130.5**, a difference of ½. That discrepancy could reflect a scribal error, a
contested reading, or a section-boundary mismatch.

> **Exploratory check.** Section boundaries are heuristic and Linear A metrology
> is contested. Use `balance_check` to locate candidate discrepancies for manual
> inspection. See [Linear A](Linear-A#accounting-reconciliation-ku-ro--po-to-ku-ro).

Omit the document ID to check the entire corpus (`aegean balance lineara`), and
pass `--strict` to exit non-zero when any checked total fails to balance.

### Search for related sign patterns

Search for words matching `KU-*-RO`, where `*` matches **exactly one sign**:

```python
from aegean.analysis import word_matches_sign_pattern

[(w, c) for w, c in corpus.word_frequencies()
 if word_matches_sign_pattern(w, "KU-*-RO")]
# [('KU-MA-RO', 1)]
```

```bash
aegean search lineara "KU-*-RO"
# 'KU-*-RO': 1 word(s)
# ┌──────────┬───────┐
# │ word     │ count │
# ├──────────┼───────┤
# │ KU-MA-RO │ 1     │
# └──────────┴───────┘
```

Only **KU-MA-RO** matches. `KU-RO` itself does not match because `*` requires
one sign between `KU` and `RO`. See the
[pattern language](Linear-A#sign-pattern-search-the--wildcard) reference.

Wildcard patterns:

| Pattern | Meaning | Example | Matches |
| --- | --- | --- | --- |
| `KU` | exact sign | `KU-RO` | only `KU-RO` |
| `*` | exactly **one** sign | `KU-*-RO` | `KU-MA-RO` (not `KU-RO`) |
| `*-RO` | one sign, then `RO` | `*-RO` | any two-sign word ending `-RO` |
| `KU-*` | `KU`, then one sign | `KU-*` | any two-sign word starting `KU-` |

### Query tablets containing KU-RO

The [query engine](Analysis#query-engine) combines inscription and word filters.
Below we select tablets whose ID contains `HT` and that contain `KU-RO`:

```python
from aegean.analysis import FilterRow, run_query

res = run_query(corpus, [
    FilterRow("id-contains", "HT"),
    FilterRow("ins-contains-word", "KU-RO", connector="and"),
], output="inscriptions")

len(res.inscriptions)                         # 32
[d.id for d in res.inscriptions][:8]
# ['HT9a', 'HT9b', 'HT11a', 'HT11b', 'HT13', 'HT25b', 'HT27a', 'HT39']
```

From the shell, repeated `--where` clauses combine with AND:

```bash
aegean query lineara --where id-contains=HT --where ins-contains-word=KU-RO
#   Inscription ID contains: HT ·   Contains exact word: KU-RO → 32 inscription(s)
# ┌────────┬───────────────┬───────┐
# │ id     │ site          │ words │
# ├────────┼───────────────┼───────┤
# │ HT9a   │ Haghia Triada │ 9     │
# │ HT9b   │ Haghia Triada │ 10    │
# │ ...    │ ...           │ ...   │
```

List all supported query fields with `aegean query lineara --fields`:

| Field | What it matches | Scope |
| --- | --- | --- |
| `id-contains` | substring of the inscription ID | inscription |
| `site-is` | find-site | inscription |
| `scribe-is` | scribal hand | inscription |
| `period-is` | period | inscription |
| `support-is` | support (tablet, roundel, …) | inscription |
| `has-image` | has a facsimile image | inscription |
| `has-annotation` | has an annotation | inscription |
| `ins-contains-word` | contains this exact word | inscription |
| `word-contains` | word contains this text | word |
| `word-prefix` | word starts with | word |
| `word-suffix` | word ends with | word |
| `word-min-syllables` | word has ≥ N signs | word |
| `word-max-syllables` | word has ≤ N signs | word |
| `word-contains-sign` | word contains this sign | word |
| `word-cooccurs-with` | word co-occurs with another | word |
| `word-sign-pattern` | word matches a `*` pattern | word |

In Python, `FilterRow(field, value, connector=...)` mirrors `--where`, with
`connector` set to `"and"` or `"or"` on subsequent rows. Pass `output="words"`
(or `--output-kind words`) to return matching word types instead of
inscriptions.

### Classify document structures

```python
from aegean.analysis import classify_corpus

buckets = classify_corpus(corpus)
{k: len(v) for k, v in buckets.items()}
# {'accounting': 137, 'libation': 25, 'list': 5, 'text': 1, 'other': 1553}
```

To inspect `HT13` or any Aegean corpus (Linear A, Linear B, Cypriot, or
Cypro-Minoan) in the local browser workbench (`workbench-app-v2.1.0`), run
`aegean workbench --corpus lineara --doc HT13` (or export a multi-script bundle
with `aegean.io.to_workbench_bundle`).

**Where next:** [Analysis](Analysis) covers phonetic distance, alignment,
morphological clustering, collocation statistics, and multivariate methods;
[Linear A](Linear-A) documents the script module in full.

---

## Tutorial 2 — Reading the first line of the Odyssey

This walkthrough runs Homer's opening line through tokenization,
syllabification, accentuation, metrical scansion, morphological analysis, and
POS tagging.

```python
from aegean import greek

line = "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
```

> Without a Greek keyboard, type **Beta Code** and convert it:
> `greek.betacode_to_unicode("a)/ndra moi e)/nnepe ...")` (see
> [Greek NLP → Beta Code](Greek-NLP#normalization--beta-code)). From the shell:
> `aegean greek betacode "mh=nin"` prints `μῆνιν`.

### Split into words and syllables

```python
words = greek.tokenize_words(line)
# ['ἄνδρα', 'μοι', 'ἔννεπε', 'Μοῦσα', 'πολύτροπον', 'ὃς', 'μάλα', 'πολλὰ']

greek.syllabify("ἄνδρα")                       # ['ἄν', 'δρα']
greek.accentuation("ἄνδρα").classification     # 'paroxytone'  (acute on the penult)
```

From the shell:

```bash
aegean greek syllabify "ἄνδρα"
# ἄνδρα → ἄν-δρα

aegean greek accent "ἄνδρα"
# ┌───────┬────────┬─────┬────────────────┐
# │ word  │ accent │ pos │ classification │
# ├───────┼────────┼─────┼────────────────┤
# │ ἄνδρα │ acute  │ 2   │ paroxytone     │
# └───────┴────────┴─────┴────────────────┘
```

The `AccentInfo` object returned by `accentuation()` has four fields:
`accent_type` (`'acute'`), `position_from_end` (`2`), `classification`
(`'paroxytone'`), and `syllables`.

### Scan the metre

The *Odyssey* is in dactylic hexameter. `scan_hexameter` resolves syllable
quantities in context and returns the feet and main caesura:

```python
sc = greek.scan_hexameter(line)
sc.pattern        # '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'   (five dactyls, then — ×)
sc.caesura        # 'trochaic'
sc.meter          # 'hexameter'
[f.name for f in sc.feet]  # ['dactyl','dactyl','dactyl','dactyl','dactyl','final']
```

From the shell (`--json` outputs the full feet and quantities structure):

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic
```

Scansion symbols:

| Glyph | Meaning |
| --- | --- |
| `—` | heavy (long) syllable |
| `⏑` | light (short) syllable |
| `×` | *anceps* (final syllable, either quantity) |
| `\|` | foot boundary |

Supported metre functions and `--meter` values for `aegean greek scan`:

| Function | `--meter` value | Verse form |
| --- | --- | --- |
| `scan_hexameter` | `hexameter` (default) | dactylic hexameter (epic) |
| `scan_pentameter` | `pentameter` | elegiac pentameter |
| `scan_trimeter` | `trimeter` | iambic trimeter (drama) |
| `scan_aeolic` | Aeolic line name | fixed-template lyric lines |
| `scan_line` | — | dispatches by metre name |

`greek.AEOLIC_LINES` lists the seven fixed-template lyric lines: `glyconic`,
`pherecratean`, `sapphic_hendecasyllable`, `adonean`, `alcaic_hendecasyllable`,
`alcaic_enneasyllable`, and `alcaic_decasyllable`. See
[Metrical scansion](Greek-NLP#metrical-scansion) for spondees, caesura rules,
synizesis handling, and scanner limits.

### Analyze morphology

`analyze` returns candidate morphological readings implied by a word's ending.
On a regular second-declension form:

```python
for a in greek.analyze("λόγον"):
    print(a)
# λόγος [NOUN acc sg masc]
# λόγος [NOUN acc sg fem]
# λόγος [NOUN nom sg neut]
# λόγος [NOUN acc sg neut]
# λόγος [NOUN voc sg neut]
```

```bash
aegean greek morph "λόγον"
# λόγος [NOUN acc sg masc]
# λόγος [NOUN acc sg fem]
# λόγος [NOUN nom sg neut]
# λόγος [NOUN acc sg neut]
# λόγος [NOUN voc sg neut]
```

Multiple readings appear because `-ον` is morphologically ambiguous and requires
context to disambiguate.

Now run the baseline analyzer on `ἄνδρα`:

```python
for a in greek.analyze("ἄνδρα"):
    print(a)
# ανδρα [NOUN nom sg fem]
# ανδρα [NOUN voc sg fem]
# ανδρα [NOUN nom pl neut]
# ανδρα [NOUN acc pl neut]
```

Those four readings are wrong: `ἄνδρα` is the accusative singular of `ἀνήρ`, an
irregular third-declension noun. The unaccented lemma (`ανδρα`) and
`lemma_certain=False` flag that the baseline reconstructed the lemma instead of
matching a known stem. Enabling the
[treebank backend](Greek-NLP#treebank-backed-mode-opt-in) below recovers
`ἀνήρ [NOUN acc sg masc]` (`lemma_certain=True`) as the primary reading. (The
source treebank also includes a spurious second entry `ὁ [DET acc sg masc]`, an
annotation artifact in the upstream data; use the first reading.) See
[Morphological analysis](Greek-NLP#morphological-analysis).

### Tag parts of speech

```python
greek.pos_tags(line)
# [('ἄνδρα', 'NOUN'), ('μοι', 'NOUN'), ('ἔννεπε', 'NOUN'), (',', 'PUNCT'),
#  ('Μοῦσα', 'NOUN'), (',', 'PUNCT'), ('πολύτροπον', 'NOUN'), (',', 'PUNCT'),
#  ('ὃς', 'PRON'), ('μάλα', 'NOUN'), ('πολλὰ', 'NOUN')]
```

```bash
aegean greek tag "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# ἄνδρα	NOUN
# μοι	NOUN
# ἔννεπε	NOUN
# ,	PUNCT
# ...
```

The baseline tags closed-class words such as `ὃς` (`PRON`) accurately, while
open-class words such as `ἔννεπε` (verb) and `μάλα` (adverb) fall back to
`NOUN`.

For attested forms, enable the
[treebank backend](Greek-NLP#treebank-backed-mode-opt-in), which uses gold tags
from the Perseus treebank (fetched once to cache, then offline):

```python
greek.use_treebank()        # one-time fetch to cache, then offline
greek.pos_tags(line)
# [('ἄνδρα','NOUN'), ('μοι','PRON'), ('ἔννεπε','VERB'), (',','PUNCT'),
#  ('Μοῦσα','NOUN'), (',','PUNCT'), ('πολύτροπον','ADJ'), (',','PUNCT'),
#  ('ὃς','PRON'), ('μάλα','ADV'), ('πολλὰ','ADJ')]
```

With the treebank enabled, every token in this line is tagged accurately, and
`analyze("ἄνδρα")` returns its attested reading. Unattested forms still fall
back to the baseline, so check which backend is active when interpreting
results. For unseen forms and full dependency trees, install `[neural]` and
enable the **neural pipeline** (`greek.use_neural_pipeline()`); see
[Greek NLP → neural pipeline](Greek-NLP#the-neural-pipeline-opt-in).

### Run all stages in one call

`pipeline` runs tokenization, tagging, lemmatization, morphology, and (when a
parser or the neural backend is active) dependency parsing in one call,
returning one `TokenRecord` per token:

```python
for r in greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")[:3]:
    print(r)
# TokenRecord(sentence=0, index=1, text='ἐν', upos='ADP', lemma='ἐν', lemma_source=<LemmaSource.SEED: 'seed'>, ...)
# TokenRecord(sentence=0, index=2, text='ἀρχῇ', upos='NOUN', lemma='ἀρχή', lemma_source=<LemmaSource.SEED: 'seed'>, ...)
# TokenRecord(sentence=0, index=3, text='ἦν', upos='VERB', lemma='εἰμί', lemma_source=<LemmaSource.SEED: 'seed'>, ...)
```

`pipeline` uses whichever backends are active (`use_treebank()`,
`use_neural_pipeline()`, etc.). The shell command is
`aegean greek pipeline "<text>"`.

### Summary

Each Greek stage runs independently or through `pipeline()`, recording the
evidence source (`lemma_source`) for every token. **Where next:**
[Greek NLP](Greek-NLP) covers IPA phonology, prosody, benchmarking,
[treebank mode](Greek-NLP#treebank-backed-mode-opt-in),
[dictionaries](Greek-NLP#more-dictionaries-the-lexicon-registry), the
[neural pipeline](Greek-NLP#the-neural-pipeline-opt-in), and
[dependency parsing](Greek-NLP#dependency-parsing-opt-in-baseline). The
[AI Layer](AI-Layer) adds exploratory grounded translation.

---

## Tutorial 3 — Pulling a real work off the shelf

The bundled `aegean.load("greek")` corpus contains five short passages. For
complete texts, pyaegean fetches individual works on demand from the open
Perseus *canonical-greekLit* and *First1KGreek* repositories (both
**CC BY-SA 4.0**) into your local cache. This walkthrough finds a work ID,
loads the opening lines of the *Iliad*, and compares their scansion with the
*Odyssey* opening from Tutorial 2.

> **Network access on first fetch only.** Each TEI file downloads once to your
> local cache from a pinned upstream commit and is reused offline afterward.

### Find a work

`popular_works()` returns a bundled 25-work starter table (no download):

```python
from aegean import greek

works = greek.popular_works()
len(works)            # 25
works[:3]
# [{'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'},
#  {'id': 'tlg0012.tlg002', 'author': 'Homer', 'title': 'Odyssey'},
#  {'id': 'tlg0020.tlg001', 'author': 'Hesiod', 'title': 'Theogony'}]
```

From the shell:

```bash
aegean greek works
# ┌────────────────┬──────────────┬──────────────────────┐
# │ id             │ author       │ title                │
# ├────────────────┼──────────────┼──────────────────────┤
# │ tlg0012.tlg001 │ Homer        │ Iliad                │
# │ tlg0012.tlg002 │ Homer        │ Odyssey              │
# │ tlg0020.tlg001 │ Hesiod       │ Theogony             │
# │ ...            │ ...          │ ...                  │
```

The 25 curated entries (`load_work` accepts any Perseus canonical-greekLit or
First1KGreek CTS ID):

| Author | Works (id → title) |
| --- | --- |
| Homer | `tlg0012.tlg001` Iliad · `tlg0012.tlg002` Odyssey |
| Hesiod | `tlg0020.tlg001` Theogony · `tlg0020.tlg002` Works and Days |
| Aeschylus | `tlg0085.tlg004` Seven Against Thebes · `tlg0085.tlg005` Agamemnon · `tlg0085.tlg006` Libation Bearers |
| Sophocles | `tlg0011.tlg001` Trachiniae · `tlg0011.tlg002` Antigone · `tlg0011.tlg003` Ajax · `tlg0011.tlg004` Oedipus Tyrannus |
| Euripides | `tlg0006.tlg001` Cyclops · `tlg0006.tlg002` Alcestis · `tlg0006.tlg003` Medea |
| Aristophanes | `tlg0019.tlg002` Knights · `tlg0019.tlg003` Clouds |
| Herodotus | `tlg0016.tlg001` Histories |
| Thucydides | `tlg0003.tlg001` History of the Peloponnesian War |
| Xenophon | `tlg0032.tlg002` Memorabilia · `tlg0032.tlg006` Anabasis |
| Plato | `tlg0059.tlg002` Apology · `tlg0059.tlg003` Crito · `tlg0059.tlg004` Phaedo · `tlg0059.tlg030` Republic |
| Aristotle | `tlg0086.tlg010` Nicomachean Ethics |

To search beyond those 25 entries, query the bundled offline discovery
catalogue (`greek.catalog()`), which indexes all 1,778 Greek editions across
Perseus and First1KGreek by `author=`, `title=`, `source=`, or free text:

```python
greek.catalog(author="Plato")[:3]
# [{'id': 'tlg0059.tlg001', 'author': 'Plato', 'title': 'Euthyphro',
#   'greek_title': 'Εὐθύφρων', 'source': 'perseus'},
#  {'id': 'tlg0059.tlg002', 'author': 'Plato', 'title': 'Apology',
#   'greek_title': 'Ἀπολογία Σωκράτους', 'source': 'perseus'},
#  {'id': 'tlg0059.tlg003', 'author': 'Plato', 'title': 'Crito',
#   'greek_title': 'Κρίτων', 'source': 'perseus'}]

len(greek.catalog())          # 1778   (768 perseus + 1010 first1k)
```

```bash
aegean greek catalog --author plato --limit 3
# ┌────────────────┬────────┬───────────┬────────────────────┬─────────┐
# │ id             │ author │ title     │ greek              │ src     │
# ├────────────────┼────────┼───────────┼────────────────────┼─────────┤
# │ tlg0059.tlg001 │ Plato  │ Euthyphro │ Εὐθύφρων           │ perseus │
# │ tlg0059.tlg002 │ Plato  │ Apology   │ Ἀπολογία Σωκράτους │ perseus │
# │ tlg0059.tlg003 │ Plato  │ Crito     │ Κρίτων             │ perseus │
# └────────────────┴────────┴───────────┴────────────────────┴─────────┘
# … and 36 more — narrow with --author/--title, or --limit 0 to list all (-o to save).
```

Coverage matches the pinned upstream commits. Authors not digitized in those
repositories are absent: `greek.catalog("Sappho")` returns `[]`. See
[Greek Works & Books](Greek-Works-and-Books#3-finding-any-other-work) for all
catalogue filters, or browse CTS IDs at the
[Scaife Viewer](https://scaife.perseus.org).

### Load a passage

`load_work` returns a standard `Corpus`. The `ref` argument selects a section
such as a book (`"1"`), a chapter (`"1.2"`), or a verse range (`"1.1-1.7"`):

```python
corpus = greek.load_work("tlg0012.tlg001", ref="1.1-1.7")   # fetches once, then cached
len(corpus)                          # 1   (one Document for the selected range)

doc = corpus.documents[0]
doc.id                               # 'tlg0012.tlg001:1.1-1.7'
doc.meta.name                        # 'Ἰλιάς — 1.1-1.7'
len(doc.lines)                       # 7

# First line
" ".join(t.text for t in doc.tokens if t.line_no == 0)
# 'μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος'
```

Every fetched corpus records its license and pinned source commit:

```python
corpus.provenance.license         # 'CC BY-SA 4.0 (Perseus Digital Library)'
corpus.provenance.data_version    # 'PerseusDL/canonical-greekLit@d4fab69a2c26'
```

From the shell:

```bash
aegean greek work tlg0012.tlg001 --ref 1.1-1.5
# ┌──────────────┬───────────────────────────────────────────┐
# │ field        │ value                                     │
# ├──────────────┼───────────────────────────────────────────┤
# │ documents    │ 1                                         │
# │ tokens       │ 35                                        │
# │ first        │ tlg0012.tlg001:1.1-1.5                    │
# │ name         │ Ἰλιάς — 1.1-1.5                           │
# │ source       │ PerseusDL/canonical-greekLit (...grc2.xml)│
# │ data_version │ PerseusDL/canonical-greekLit@d4fab69a2c26 │
# └──────────────┴───────────────────────────────────────────┘
```

Parameters shared by `load_work` and `aegean greek work`:

| Argument (API → CLI) | Purpose | Default |
| --- | --- | --- |
| `work` → `WORK_ID` | CTS ID (`tlg0012.tlg001` = *Iliad*) | required |
| `ref=` → `--ref` | section: `"1"`, `"1.2"`, or line range `"1.1-1.7"` | whole work |
| `source=` → `--source` | `"perseus"`, `"first1k"`, or `"auto"` | `auto` (try both) |
| `edition=` → `--edition` | select a specific edition file | highest `-grc*` edition |
| `force=` (API only) | re-download even when cached | `False` |

`doc.tokens` includes punctuation, foreign text, and numerals; `doc.source_text`
retains the whitespace-normalized TEI reading. Use `doc.words` for lexical
tokens. Speaker labels in drama retain their TEI context and are excluded from
word counts.

### Run the Greek pipeline on the fetched line

Every Tutorial 2 step runs unchanged on the fetched text:

```python
line0 = " ".join(t.text for t in doc.tokens if t.line_no == 0)

sc = greek.scan_hexameter(line0)
sc.pattern        # '—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×'
sc.caesura        # 'penthemimeral'
```

Compared with the *Odyssey* opening, *Iliad* 1.1 puts a **spondee** (`——`) in
the third foot instead of a dactyl and places its main pause at the
**penthemimeral** caesura (after the fifth half-foot) instead of the trochaic
caesura.

Run `pipeline()` on the line (shown below in a fresh baseline session; if
`use_treebank()` from Tutorial 2 is still active in the same process, `ἄειδε`
will already tag as `VERB`):

```python
for r in greek.pipeline(line0)[:3]:
    print(r.text, r.upos, r.lemma, r.review_recommended)
# μῆνιν NOUN μῆνις False
# ἄειδε NOUN ἀείδω False
# θεὰ NOUN θεά False
```

The baseline mistags `ἄειδε` as `NOUN`; enable `use_treebank()` or the
[neural pipeline](Greek-NLP#the-neural-pipeline-opt-in) for accurate POS tags.
`review_recommended` is `False` on these three tokens because each lemma came
from the seed table: the flag marks only identity fall-throughs and unresolved
lemmas (such as `Πηληϊάδεω` and `Ἀχιλῆος` later in the same line). A `False`
flag does not guarantee that a POS tag or contextual lemma is right.

### Summary

`popular_works()` / `greek.catalog()` find work IDs; `load_work()` /
`aegean greek work` fetch pinned, citable corpora to the local cache; and the
Greek pipeline runs on the loaded documents. To review machine annotations
interactively, launch `aegean tui --review` (`r` in `aegean tui`); to archive a
reproducible snapshot with citations and SHA-256 checksums, use
`aegean bundle create` (`aegean.bundle`).

**Where next:** [Greek NLP](Greek-NLP) for every pipeline stage,
[Recipes](Recipes) for end-to-end research tasks, and
[Data & Provenance](Data-and-Provenance) for cache management and resource
packs (`aegean library`).

---

## Notes & limitations

- **Linear A is undeciphered.** Balance checks, structure classification, and
  sign-pattern queries surface structural patterns for manual inspection; they
  do not establish readings or meanings. Section boundaries are heuristic and
  Linear A metrology is contested.
- **The Greek baseline is heuristic.** With no extra backend enabled,
  open-class words fall back to `NOUN` and irregular forms produce unaccented
  reconstructed lemmas. Enable the treebank or neural backend when accuracy
  matters, and check which backend is active.
- **Scansion is rule-based.** Synizesis is handled lexically; a line requiring
  an out-of-lexicon synizesis is reported as unscanned.
- **`load_work` requires network access on first fetch** per work and depends
  on well-formed upstream TEI for the requested citation address.

For the full list of scope limits, see [Limitations](Limitations).
