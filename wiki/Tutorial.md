# Tutorial

Two short, complete walkthroughs that each answer a real research question — one
in **Linear A**, one in **Greek**. Every snippet is runnable and every result
shown here is real output. If you haven't installed pyaegean yet, do
[Getting Started](Getting-Started) first.

Paste the snippets into a [Jupyter notebook](Getting-Started#option-c--jupyter-recommended-for-research)
cell by cell, or into the interactive `python` prompt. Each builds on the last.

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

(Each result is a `BalanceCheck` — a small Python object whose fields you can read
directly: `chk.stated_total`, `chk.balances`, and so on.)

Interesting: under this reading the items sum to **131.0** but the scribe wrote
**130.5** — a discrepancy of ½. Is that an ancient error, a misread sign, or an
artefact of how *we* drew the section boundary?

> **This is exploratory.** Section boundaries are heuristic and Linear A
> metrology is genuinely contested. `balance_check` is a tool for *finding* lines
> worth a human's attention — not a verdict. See [Linear A](Linear-A#accounting-reconciliation-ku-ro--po-to-ku-ro).

### How does the total-word behave elsewhere?

Search for words shaped like `KU-?-RO` (the `*` wildcard means **exactly one
sign** in between):

```python
from aegean.analysis import word_matches_sign_pattern

[(w, c) for w, c in corpus.word_frequencies()
 if word_matches_sign_pattern(w, "KU-*-RO")]
# [('KU-MA-RO', 1)]
```

Only **KU-MA-RO** matches — and notice `KU-RO` itself does *not*, because `*`
requires exactly one sign between KU and RO (KU-RO has none). That's the kind of
precise, testable query the [pattern language](Linear-A#sign-pattern-search) is for.

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

### Zoom out: what kinds of documents are these?

```python
from aegean.analysis import classify_corpus

buckets = classify_corpus(corpus)
{k: len(v) for k, v in buckets.items()}
# {'accounting': 134, 'libation': 15, 'list': 7, 'text': 2, 'other': 1563}
```

You've now gone from one tablet's arithmetic to a corpus-wide structural view — in
a dozen lines. **Where next:** the [Analysis](Analysis) page has phonetic distance,
alignment, morphological clustering, and collocation statistics.

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
> [Greek NLP](Greek-NLP#normalization--beta-code).

### Split it into words and syllables

```python
words = greek.tokenize_words(line)
# ['ἄνδρα', 'μοι', 'ἔννεπε', 'Μοῦσα', 'πολύτροπον', 'ὃς', 'μάλα', 'πολλὰ']

greek.syllabify("ἄνδρα")                       # ['ἄν', 'δρα']
greek.accentuation("ἄνδρα").classification     # 'paroxytone'  (acute on the penult)
```

### Scan the metre

The *Odyssey* is in dactylic hexameter. The scanner resolves each syllable's
quantity in context and reports the feet and the caesura (the line's main pause):

```python
sc = greek.scan_hexameter(line)
sc.pattern        # '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'   (five dactyls, then — ×)
sc.caesura        # 'trochaic'
```

`—` is heavy, `⏑` light, `×` the *anceps* final syllable. See
[Metrical scansion](Greek-NLP#metrical-scansion) for spondees, the penthemimeral
caesura, and the (deliberate) limits.

### Tag parts of speech

```python
greek.pos_tags(line)
# [('ἄνδρα', 'NOUN'), ('μοι', 'NOUN'), ('ἔννεπε', 'NOUN'), (',', 'PUNCT'),
#  ('Μοῦσα', 'NOUN'), (',', 'PUNCT'), ('πολύτροπον', 'NOUN'), (',', 'PUNCT'),
#  ('ὃς', 'PRON'), ('μάλα', 'NOUN'), ('πολλὰ', 'NOUN')]
```

The closed-class word `ὃς` is correctly tagged **PRON**. But notice `ἔννεπε` (a
verb) and `μάλα` (an adverb) both come back as **NOUN**. The baseline is reliable
on closed classes; open-class words fall back to NOUN.

You can fix this for *attested* forms by switching on the
[treebank backend](Greek-NLP#treebank-backed-mode-opt-in) — it uses gold tags from
the Perseus treebank:

```python
greek.use_treebank()        # one-time download + build, then cached
greek.pos_tags(line)
# [('ἄνδρα','NOUN'), ('μοι','PRON'), ('ἔννεπε','VERB'), (',','PUNCT'),
#  ('Μοῦσα','NOUN'), (',','PUNCT'), ('πολύτροπον','ADJ'), (',','PUNCT'),
#  ('ὃς','PRON'), ('μάλα','ADV'), ('πολλὰ','ADJ')]
```

Now every word is tagged correctly. The treebank covers known forms; unattested
ones still use the baseline, so it's always worth knowing which mode you're in.

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

Several readings come back because the `-ον` ending is genuinely ambiguous — that
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
(`ανδρα`) — the engine's signal that it **reconstructed** the form rather than
recognising it (`lemma_certain` is `False`). Irregular and third-declension forms
are exactly what the rule-based baseline can't resolve — but switch on the
[treebank backend](Greek-NLP#treebank-backed-mode-opt-in) (`greek.use_treebank()`) and
`analyze("ἄνδρα")` correctly returns `ἀνήρ [NOUN acc sg masc]` (`lemma_certain=True`).
See [Morphological analysis](Greek-NLP#morphological-analysis) for the full scope.

### What you learned

The Greek pipeline is a set of independent steps you can mix and match, each
reporting where its answer is solid and where it has fallen back to a guess.
**Where next:**
the [Greek NLP](Greek-NLP) reference covers IPA phonology, prosody, the benchmark
harness, the opt-in [treebank lemmas/morphology](Greek-NLP#treebank-backed-mode-opt-in),
[LSJ glossing](Greek-NLP#lexicon-lsj-glossing-opt-in), and the baseline
[dependency parser](Greek-NLP#dependency-parsing-opt-in-baseline); the
[AI Layer](AI-Layer) adds (clearly-labeled, exploratory) translation on top.
