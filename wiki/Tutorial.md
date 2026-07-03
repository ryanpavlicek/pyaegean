# Tutorial

Three complete, run-along walkthroughs that each answer a real question. The
first two stand on their own: one in **Linear A**, one in **Greek**, and the
third shows how to pull a real Greek work off the shelf and run the pipeline over
it. Every snippet here is runnable, and every result shown is **real output** from
the version you just installed; nothing is invented. If you haven't installed
pyaegean yet, do [Getting Started](Getting-Started) first.

Paste the snippets into a [Jupyter notebook](Getting-Started#option-c--jupyter-recommended-for-research)
cell by cell, or into the interactive `python` prompt; each tutorial builds up
step by step. Where a step has **both** a Python API and a shell command, both are
shown; pick whichever fits how you work. The shell side assumes you installed the
CLI (`pip install "pyaegean[cli]"`); see the [CLI](CLI) page for the full command
list.

**The three walkthroughs:**

| # | Question | Track | Network needed? |
|---|----------|-------|-----------------|
| [1](#tutorial-1--does-a-3500-year-old-ledger-add-up) | Does a 3,500-year-old ledger add up? | Linear A | No: bundled corpus, fully offline |
| [2](#tutorial-2--reading-the-first-line-of-the-odyssey) | Reading the first line of the *Odyssey* | Greek | No (treebank step is opt-in) |
| [3](#tutorial-3--pulling-a-real-work-off-the-shelf) | Pulling a real work off the shelf | Greek | Yes: fetches one work to cache, once |

---

## Tutorial 1 — Does a 3,500-year-old ledger add up?

Many Linear A tablets are accounts: a list of entries followed by a "total" word,
**KU-RO**. We'll pick one tablet, check its arithmetic, and then look at how the
total-word behaves across the corpus.

### Load the corpus and look at one tablet

```python
import aegean

corpus = aegean.load("lineara")     # 1,721 inscriptions, bundled, offline
doc = corpus.get("HT13")            # a well-known account from Haghia Triada

[t.text for t in doc.words]
# ['KA-U-DE-TA', 'RE-ZA', 'TE-TU', 'TE-KI', 'KU-ZU-NI', 'DA-SI-*118', 'I-DU-NE-SI', 'KU-RO']

[t.text for t in doc.numerals]
# ['5', '¹⁄₂', '56', '27', '¹⁄₂', '18', '19', '5', '130', '¹⁄₂']
```

Notice the tablet ends with **KU-RO** ("total"), and the numerals include
metrological **fractions** (¹⁄₂).

**From the shell**, the same tablet, laid out line by line:

```bash
aegean show lineara HT13
```

`aegean info lineara` gives the corpus-level view: size, source, license, and the
citation you should use, before you go further:

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

`balance_check` sums the line items that a total governs and compares them to the
stated total:

```python
from aegean.analysis import balance_check

for chk in balance_check(doc):
    print(chk)
# BalanceCheck(stated_total=130.5, computed_sum=131.0, item_count=6,
#              difference=0.5, balances=False, marker='KU-RO', total_line_index=7)
```

(Each result is a `BalanceCheck`: a small Python object whose fields you can read
directly: `chk.stated_total`, `chk.balances`, and so on.)

The same check from the shell prints a table; add `--json` for machine-readable
output:

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

Interesting: under this reading the items sum to **131.0** but the scribe wrote
**130.5**: a discrepancy of ½. Is that an ancient error, a misread sign, or an
artefact of how *we* drew the section boundary?

> **This is exploratory.** Section boundaries are heuristic and Linear A
> metrology is genuinely contested. `balance_check` is a tool for *finding* lines
> worth a human's attention, not a verdict. See [Linear A](Linear-A#accounting-reconciliation-ku-ro--po-to-ku-ro).

Omit the document id to sweep the whole corpus at once (`aegean balance lineara`),
and add `--strict` to make the command exit non-zero if any checked total fails:
handy in a script that should flag discrepancies.

### How does the total-word behave elsewhere?

Search for words shaped like `KU-?-RO` (the `*` wildcard means **exactly one
sign** in between):

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

Only **KU-MA-RO** matches, and notice `KU-RO` itself does *not*, because `*`
requires exactly one sign between KU and RO (KU-RO has none). That's the kind of
precise, testable query the [pattern language](Linear-A#sign-pattern-search-the--wildcard) is for.

The wildcard pieces you can combine:

| Pattern piece | Means | Example | Matches |
|---|---|---|---|
| `KU` | that exact sign | `KU-RO` | only KU-RO |
| `*` | exactly **one** sign | `KU-*-RO` | KU-MA-RO (not KU-RO) |
| `*-RO` | one sign, then RO | `*-RO` | any two-sign word ending -RO |
| `KU-*` | KU, then one sign | `KU-*` | any two-sign word starting KU- |

### Which tablets actually use KU-RO?

The [query engine](Analysis#query-engine) combines conditions. Here: tablets whose
id starts with HT **and** that contain the word KU-RO.

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

The same query from the shell: each `--where` is ANDed with the one before it:

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

The query engine has many more fields than these two. List them with
`aegean query lineara --fields`; the full set:

| Field | What it matches | Scope |
|---|---|---|
| `id-contains` | substring of the inscription id | inscription |
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

In the API, `FilterRow(field, value, connector=...)` mirrors a `--where` row;
`connector` is `"and"` or `"or"` (the first row needs none). Set `output="words"`
(or `--output-kind words`) to get matching word types back instead of inscriptions.

### Zoom out: what kinds of documents are these?

```python
from aegean.analysis import classify_corpus

buckets = classify_corpus(corpus)
{k: len(v) for k, v in buckets.items()}
# {'accounting': 134, 'libation': 18, 'list': 6, 'text': 1, 'other': 1562}
```

You've now gone from one tablet's arithmetic to a corpus-wide structural view, in
a dozen lines. **Where next:** the [Analysis](Analysis) page has phonetic distance,
alignment, morphological clustering, collocation statistics, and the multivariate
methods; [Linear A](Linear-A) is the full reference for the script itself.

---

## Tutorial 2 — Reading the first line of the Odyssey

We'll take Homer's opening line and run it through the Greek pipeline: syllables,
accent, **metre**, part of speech, and morphology.

```python
from aegean import greek

line = "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
```

> Don't have a Greek keyboard? Write it in **Beta Code** and convert:
> `greek.betacode_to_unicode("a)/ndra moi e)/nnepe ...")`. See
> [Greek NLP](Greek-NLP#normalization--beta-code). From the shell:
> `aegean greek betacode "mh=nin"` prints `μῆνιν`.

### Split it into words and syllables

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

The `AccentInfo` object behind `accentuation()` carries four fields you can read:
`accent_type` (`'acute'`), `position_from_end` (`2`), `classification`
(`'paroxytone'`), and `syllables`.

### Scan the metre

The *Odyssey* is in dactylic hexameter. The scanner resolves each syllable's
quantity in context and reports the feet and the caesura (the line's main pause):

```python
sc = greek.scan_hexameter(line)
sc.pattern        # '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'   (five dactyls, then — ×)
sc.caesura        # 'trochaic'
sc.meter          # 'hexameter'
[f.name for f in sc.feet]  # ['dactyl','dactyl','dactyl','dactyl','dactyl','final']
```

The same line from the shell, with the per-foot breakdown printed below the
pattern (and a full feet/quantities tree under `--json`):

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic
```

The scansion glyphs:

| Glyph | Meaning |
|---|---|
| `—` | heavy (long) syllable |
| `⏑` | light (short) syllable |
| `×` | *anceps*: the final syllable, either quantity |
| `\|` | foot boundary |

`scan_hexameter` is one of several metre functions. Each is a plain function, and
each has a `--meter` value for `aegean greek scan`:

| Function | `--meter` value | Verse form |
|---|---|---|
| `scan_hexameter` | `hexameter` (default) | dactylic hexameter (epic) |
| `scan_pentameter` | `pentameter` | elegiac pentameter |
| `scan_trimeter` | `trimeter` | iambic trimeter (drama) |
| `scan_aeolic` | one of the aeolic line names | fixed-template lyric lines |
| `scan_line` |— | dispatches by name |

The aeolic line templates available to `scan_aeolic` / `--meter` are in
`greek.AEOLIC_LINES`: `glyconic`, `pherecratean`, `sapphic_hendecasyllable`,
`adonean`, `alcaic_hendecasyllable`, `alcaic_enneasyllable`, and
`alcaic_decasyllable`. See [Metrical scansion](Greek-NLP#metrical-scansion) for
spondees, the penthemimeral caesura, synizesis handling, and the (deliberate)
limits.

### Analyse morphology

`analyze` returns the candidate readings an ending implies. On a **regular** form
it's strong:

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

Several readings come back because the `-ον` ending is genuinely ambiguous; that
ambiguity is the linguistic reality, and you disambiguate with context.

Now try it on `ἄνδρα` from our line:

```python
for a in greek.analyze("ἄνδρα"):
    print(a)
# ανδρα [NOUN nom sg fem]
# ανδρα [NOUN voc sg fem]
# ανδρα [NOUN nom pl neut]
# ανδρα [NOUN acc pl neut]
```

These are all *wrong*: `ἄνδρα` is the accusative singular of `ἀνήρ` (a third-
declension noun with an irregular stem). The lemma even comes back unaccented
(`ανδρα`): the engine's signal that it **reconstructed** the form rather than
recognising it (`lemma_certain` is `False`). Irregular and third-declension forms
are exactly what the rule-based baseline can't resolve. Switching on the
[treebank backend](Greek-NLP#treebank-backed-mode-opt-in) (below) recovers the
gold reading: with the treebank on, `analyze("ἄνδρα")` leads with
`ἀνήρ [NOUN acc sg masc]` (`lemma_certain=True`), the correct one. It also carries
along a second gold-derived reading, `ὁ [DET acc sg masc]`, an annotation artefact
from the source treebank rather than a real parse of `ἄνδρα`, so treat the first
reading as the answer. See [Morphological analysis](Greek-NLP#morphological-analysis)
for the full scope.

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

The closed-class word `ὃς` is correctly tagged **PRON**. But notice `ἔννεπε` (a
verb) and `μάλα` (an adverb) both come back as **NOUN**. The baseline is reliable
on closed classes; open-class words fall back to NOUN.

You can fix this for *attested* forms by switching on the
[treebank backend](Greek-NLP#treebank-backed-mode-opt-in): it uses gold tags from
the Perseus treebank (a one-time fetch to cache, then offline):

```python
greek.use_treebank()        # one-time download + build, then cached
greek.pos_tags(line)
# [('ἄνδρα','NOUN'), ('μοι','PRON'), ('ἔννεπε','VERB'), (',','PUNCT'),
#  ('Μοῦσα','NOUN'), (',','PUNCT'), ('πολύτροπον','ADJ'), (',','PUNCT'),
#  ('ὃς','PRON'), ('μάλα','ADV'), ('πολλὰ','ADJ')]
```

Now every word is tagged correctly. The treebank covers known forms, and it is
also what turns the earlier `analyze("ἄνδρα")` into its gold reading; unattested
forms still use the baseline, so it's always worth knowing which mode you're in.
The most accurate option is the **neural pipeline** (`greek.use_neural_pipeline()`,
the `[neural]` extra), which tags, lemmatizes, and parses in one pass and
generalizes to unseen forms; see [the neural pipeline](Greek-NLP#the-neural-pipeline-opt-in).

### The whole stack in one call

When you want every stage at once rather than calling them one by one, `pipeline`
returns one record per token:

```python
for r in greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")[:3]:
    print(r)
# TokenRecord(sentence=0, index=1, text='ἐν', upos='ADP', lemma='ἐν', lemma_known=True, ...)
# TokenRecord(sentence=0, index=2, text='ἀρχῇ', upos='NOUN', lemma='ἀρχή', lemma_known=True, ...)
# TokenRecord(sentence=0, index=3, text='ἦν', upos='VERB', lemma='εἰμί', lemma_known=True, ...)
```

`pipeline` honours whichever backends you've turned on; turn on the treebank or
neural pipeline first and the `upos`/`lemma`/`head`/`relation` fields fill out
accordingly. The shell equivalent is `aegean greek pipeline "<text>"`.

### What you learned

The Greek pipeline is a set of independent steps you can mix and match, each
reporting where its answer is solid and where it has fallen back to a guess.
**Where next:**
the [Greek NLP](Greek-NLP) reference covers IPA phonology, prosody, the benchmark
harness, the opt-in [treebank lemmas/morphology](Greek-NLP#treebank-backed-mode-opt-in),
[dictionary glossing](Greek-NLP#more-dictionaries-the-lexicon-registry), the
[neural pipeline](Greek-NLP#the-neural-pipeline-opt-in), and the baseline
[dependency parser](Greek-NLP#dependency-parsing-opt-in-baseline); the
[AI Layer](AI-Layer) adds (clearly-labeled, exploratory) translation on top.

---

## Tutorial 3 — Pulling a real work off the shelf

The bundled Greek corpus (`aegean.load("greek")`) is just five short sample
passages: enough to exercise the pipeline, not enough to do research on. For the
real texts, pyaegean fetches one work at a time from the open Perseus
*canonical-greekLit* and *First1KGreek* corpora (both **CC BY-SA 4.0**) into a
local cache. This walkthrough uses the **discovery helpers** to find a work, then
loads its first lines and scans them, and shows how the *Iliad*'s opening differs,
metrically, from the *Odyssey*'s in Tutorial 2.

> **This step uses the network**, but only the first time per work: the TEI file
> is fetched once to your cache (pinned to a fixed commit, so it's reproducible)
> and reused afterward. Everything else on this page is fully offline.

### Find a work

`popular_works()` is a curated, verified catalog of well-known works: pure
metadata, no download — so you can look up the id `load_work` needs:

```python
from aegean import greek

works = greek.popular_works()
len(works)            # 25
works[:3]
# [{'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'},
#  {'id': 'tlg0012.tlg002', 'author': 'Homer', 'title': 'Odyssey'},
#  {'id': 'tlg0020.tlg001', 'author': 'Hesiod', 'title': 'Theogony'}]
```

From the shell, `aegean greek works` prints the same catalog as a table:

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

This catalog is a **starting point, not the full canon**: `load_work` accepts any
Perseus canonical-greekLit / First1KGreek CTS id. The 25 curated entries:

| Author | Works (id → title) |
|---|---|
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

To go beyond those 25 curated highlights without leaving the toolkit, search the
**full** discovery catalogue: every work with a Greek edition in the two open
repos, ~1,800 in all. It's bundled metadata (no download), so it's offline and
instant; `catalog()` takes substring filters (`author=`, `title=`, `source=`) or a
free-text `query`, and every `id` it returns is one you can hand straight to
`load_work`:

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

The coverage is exactly what those open repos hold at the pinned commit, so a few
authors that aren't in the upstream data are honestly absent here too:
`greek.catalog("Sappho")` returns `[]` rather than inventing an id. The full
treatment, with every filter, is in
[Finding any other work](Greek-Works-and-Books#3-finding-any-other-work); for
anything beyond even the catalogue, browse the complete corpus at the
[Scaife Viewer](https://scaife.perseus.org) and pass any CTS id you find.

### Load just the lines you want

`load_work` returns a standard `Corpus`. The `ref` argument selects a section
instead of the whole work — a citation address matching the text's structure: a
book number (`"1"`), a nested chapter (`"1.2"`), or a verse **line-range**
(`"1.1-1.7"` = book 1, lines 1–7). Here we take the famous first seven lines of the
*Iliad*:

```python
corpus = greek.load_work("tlg0012.tlg001", ref="1.1-1.7")   # fetches once, then cached
len(corpus)                          # 1   (one Document for the selected range)

doc = corpus.documents[0]
doc.id                               # 'tlg0012.tlg001:1.1-1.7'
doc.meta.name                        # 'Ἰλιάς — 1.1-1.7'
len(doc.lines)                       # 7

# the opening line
" ".join(t.text for t in doc.tokens if t.line_no == 0)
# 'μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος'
```

Every fetched corpus carries its provenance: exactly what you'd cite, and the
pinned commit that makes it reproducible:

```python
corpus.provenance.license         # 'CC BY-SA 4.0 (Perseus Digital Library)'
corpus.provenance.data_version    # 'PerseusDL/canonical-greekLit@d4fab69a2c26'
```

The shell mirror is `aegean greek work`, with `--ref` for the same selection:

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

The arguments that shape what you get back:

| Argument (API → CLI) | What it does | Default |
|---|---|---|
| `work` → `WORK_ID` | the CTS id (`tlg0012.tlg001` = Iliad) | required |
| `ref=` → `--ref` | section: `"1"`, `"1.2"`, or line-range `"1.1-1.7"` | whole work |
| `source=` → `--source` | `"perseus"`, `"first1k"`, or `"auto"` | `auto` (try both) |
| `edition=` → `--edition` | pick a specific edition file | highest `-grc*` edition |
| `force=` (API only) | re-download even if cached | `False` |

### Run the pipeline over the real line

The line you loaded is ordinary Greek text, so every Tutorial 2 step works on it
unchanged. Scan its metre, and watch the contrast with the *Odyssey*:

```python
line0 = " ".join(t.text for t in doc.tokens if t.line_no == 0)

sc = greek.scan_hexameter(line0)
sc.pattern        # '—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×'
sc.caesura        # 'penthemimeral'
```

Two real differences from the *Odyssey*'s opening: the *Iliad*'s third foot is a
**spondee** (`——`, two heavies) rather than a dactyl, and its main pause is the
**penthemimeral** caesura (after the fifth half-foot) instead of the trochaic one.
Same metre, different texture: exactly the kind of comparison this loader makes
easy.

And the one-call pipeline tags and lemmatizes it (the output below is the baseline,
i.e. a fresh session; if you enabled the treebank back in Tutorial 2 it's still
active and you'll already see `ἄειδε VERB` here):

```python
for r in greek.pipeline(line0)[:3]:
    print(r.text, r.upos, r.lemma, r.lemma_known)
# μῆνιν NOUN μῆνις True
# ἄειδε NOUN ἀείδω True
# θεὰ NOUN θεά True
```

(`ἄειδε` is a verb the baseline mis-tags NOUN; turn on the treebank or
[neural pipeline](Greek-NLP#the-neural-pipeline-opt-in) for the correct tag, as in
Tutorial 2.)

### What you learned

`popular_works()` / `aegean greek works` finds an id; `load_work(...)` /
`aegean greek work ...` fetches the text (once) into a reproducible, properly-cited
`Corpus`; and from there the whole Greek pipeline applies. **Where next:**
[Greek NLP](Greek-NLP) for every pipeline stage, and
[Data & Provenance](Data-and-Provenance) for how the cache and pinned commits work.

---

## Notes & limitations

These tutorials are honest about where the tools are firm and where they are
exploratory:

- **Linear A is undeciphered.** Tutorial 1's balance checks, structure buckets,
  and pattern searches are tools for *finding* lines worth a human's attention,
  not verdicts about meaning. Section boundaries are heuristic and the metrology is
  contested.
- **The Greek baseline falls back.** Out of the box, open-class words tag as NOUN
  and irregular forms get reconstructed (unaccented) lemmas. The opt-in treebank
  and neural backends fix this for the forms they cover; always know which mode
  you're in.
- **Scansion is rule-based**, with synizesis treated lexically rather than guessed;
  a line that only fits via an out-of-lexicon synizesis is reported as unscanned
  rather than forced.
- **`load_work` needs the network the first time** per work, and depends on the
  upstream TEI being well-formed for the section you request.

The full, frank accounting of what each tool can and can't do is on the
[Limitations](Limitations) page.
