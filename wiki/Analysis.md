# Analysis

`aegean.analysis` ports the Linear A Research Workbench's analytical methods to
Python, **faithfully** — each is checked against shared golden fixtures
(`tests/fixtures/golden/algorithms.json`) so the port can't silently diverge,
and property tests mirror the workbench's invariants.

> **Exploratory material.** Linear A is undeciphered: the cross-linguistic and
> decipherment-adjacent methods here surface *evidence to weigh*, never readings
> or translations. The full picture of what pyaegean can and cannot claim is on
> the **[Limitations](Limitations)** page.

## Phonetic distance & classes

A weighted Levenshtein over phonetic strings, normalized to `[0, 1]`. Vowel↔vowel
substitutions are cheap (0.3), same articulatory-class consonants moderate (0.5),
everything else full cost (1).

```python
from aegean.analysis import phonetic_distance, extract_root
phonetic_distance("kuro", "kuro")     # 0.0
phonetic_distance("kuro", "karo")     # 0.075   (one vowel swap / 4)
phonetic_distance("kuro", "kulo")     # 0.125   (r↔l, same class / 4)
extract_root("KU-RO")                 # 'kr'     (consonant skeleton)
```

Which phonemes count as "same class" is a linguistic judgement, exposed as a
configurable scheme:

```python
from aegean.analysis import (
    build_phonetic_classes, DEFAULT_PHONETIC_SCHEME,
    CONSERVATIVE_PHONETIC_SCHEME, describe_phonetic_scheme,
)
describe_phonetic_scheme(DEFAULT_PHONETIC_SCHEME)
# 'interdentals=dental, ḥ=velar, ž=sibilant, strip-notation=on'
cl = build_phonetic_classes(CONSERVATIVE_PHONETIC_SCHEME)
```

## Alignment

Per-phoneme alignment classifies each position as match / vowel-sub / class-sub /
far-sub / insertion / deletion:

```python
from aegean.analysis import align_phonetic
[c.op for c in align_phonetic("ka", "ko")]    # ['match', 'sub-vowel']
[c.op for c in align_phonetic("pa", "ba")]    # ['sub-class', 'match']
```

Word-level multiple-sequence alignment (progressive Needleman–Wunsch) lines up
whole inscriptions:

```python
from aegean.analysis import align_sequences
align_sequences([["A-B", "X-Y", "C-D"], ["A-B", "Z-Z", "C-D"]])
# [['A-B','A-B'], ['X-Y','Z-Z'], ['C-D','C-D']]
```

## Cross-script comparison

The distance and alignment above work on phoneme strings; `aegean.analysis.compare`
feeds them words from *different scripts* by romanizing each to a common Latin
phoneme alphabet. The deciphered syllabaries already do this
(`word_to_phonetic`); the new piece is `romanize_greek`, so a Linear B word and
its alphabetic-Greek descendant — or a Cypriot and a Greek form — can be lined
up by **sound**.

```python
from aegean.analysis import phonetic_compare, nearest, romanize_greek

romanize_greek("βασιλεύς")                       # 'basileus'  (accents/breathings dropped)
cmp = phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek", fold_aspiration=True)
cmp.similarity                                   # ~0.69
[(c.a, c.b, c.op) for c in cmp.alignment][:1]    # [('q', 'b', 'sub-far')] — the qʷ→b reflex

# triage: which Greek words sound closest to a Linear B form?
nearest("qa-si-re-u", "linearb",
        ["ποιμήν", "βασιλεύς", "πατήρ", "θεός"], "greek", fold_aspiration=True)
# [('βασιλεύς', 0.31), ('πατήρ', 0.61), …]   — the true cognate ranks first
```

Two cautions stack here. The distance metric's phoneme classes are already a
linguistic judgement (above); on top of that, **syllabic spelling is defective**
— Linear B and Cypriot drop word-final consonants, omit cluster members, and
don't write aspiration or voicing — so a Greek form looks longer than its
syllabic spelling and the absolute distance is inflated. The reliable signal is
the **ranking** (`nearest`), and an alignment shows a *hypothesised*
correspondence, not a sound law. `fold_aspiration` (θ/φ/χ → t/p/k) meets the
syllabaries' aspiration-blind orthography halfway. From the shell:
`aegean analyze compare po-me ποιμήν` and `aegean analyze nearest qa-si-re-u greek`.

## Morphological clustering

Heuristic lemmatization for an undeciphered script: find suffixes productive
across many words, then group words sharing a stem via a productive suffix.

```python
from aegean.analysis import find_morphological_clusters
clusters = find_morphological_clusters(
    corpus.word_frequencies(),
    min_suffix_productivity=5, min_cluster_size=2, max_suffix_len=2,
)
c = clusters[0]
c.stem, c.total_count, c.suffixes
[(m.word, m.count, m.suffix) for m in c.members]
```

## Collocation statistics

For a word pair across N documents (joint, countA, countB, total). The exact
special functions come from the standard-library `math` module, so there are no
third-party dependencies.

```python
from aegean.analysis import (
    chi_squared_2x2, log_likelihood_ratio_2x2, chi_squared_p_value,
    fishers_exact, wilson_interval, pmi_interval,
)
chi_squared_2x2(5, 10, 10, 100)          # ≈ 15.123  (Yates-corrected)
log_likelihood_ratio_2x2(5, 10, 10, 100) # ≈ 12.533  (G², Dunning 1993)
chi_squared_p_value(3.841)               # ≈ 0.05
fishers_exact(5, 5, 5, 10)               # ≈ 0.007937 (two-sided)
wilson_interval(5, 10)                    # (low, high) 95% CI
```

## Corpus statistics: dispersion, keyness, bootstrap

Where collocation scores one word *pair*, these compare **whole corpora and
subsets** — pure stdlib, working over any loadable corpus (`lineara`, `damos`,
a `filter()` subset, or a plain document list). In plain terms: *dispersion*
asks "is this word everywhere, or does it live in a few documents?"; *keyness*
asks "what vocabulary makes this group of texts different from that one?"; the
*bootstrap* asks "how sure can I be of this number, given how few documents
there are?"

**Dispersion** — Gries' deviation of proportions (DP; Gries 2008, normalized
per Lijffijt & Gries 2012). 0 = spread exactly as document sizes predict;
toward 1 = concentrated in few documents:

```python
from aegean.analysis import dispersion, dispersions
import aegean

c = aegean.load("damos")
dispersion(c, "pa-ro")          # Dispersion(item='pa-ro', frequency=230, range=97, …, dp_norm=0.87)
dispersions(c, top=10)          # the most evenly-spread words first
```

A frequent word with *high* `dp_norm` is the interesting case on Aegean
material — formulaic or genre/site-bound vocabulary rather than corpus-wide
language.

**Keyness** — which items are characteristic of a target (sub)corpus against a
reference: Dunning's log-likelihood **G²** for significance (Rayson & Garside
2000) plus Hardie's (2014) **log-ratio** for effect size (each point ≈ one
doubling of relative frequency; positive = overused in the target):

```python
from aegean.analysis import keyness

pylos = c.filter(site="Pylos")
rest = [d for d in c.documents if d.meta.site != "Pylos"]
rows = keyness(pylos, rest)
rows[0]    # KeynessRow(item='pe-mo', …, log_likelihood=254.1, log_ratio=+8.5, p=3e-57)
# the Pylos land-tenure series surfaces immediately: pe-mo, o-na-to, ko-to-na, e-ke …
```

**Bootstrap confidence intervals** — a percentile interval for *any* corpus
statistic, resampling documents with replacement (Efron & Tibshirani 1993);
documents are the resampling unit because tokens within a tablet are not
independent. Deterministic by default (`seed=0`) for reproducibility:

```python
from aegean.analysis import bootstrap_ci
from aegean.core.model import TokenKind

mean_words = lambda docs: sum(
    sum(1 for t in d.tokens if t.kind is TokenKind.WORD) for d in docs
) / len(docs)
bootstrap_ci(c, mean_words)     # BootstrapCI(estimate=…, low=…, high=…, level=0.95)
```

A scholarly caution: on small or fragmentary corpora a significant G² flags an
imbalance worth *inspecting*, not a proven fact about the language — read
significance (G², p) together with effect size (log-ratio) and dispersion.
From the shell: `aegean dispersion damos --top 10` and
`aegean keyness damos --site Pylos` (see [CLI](CLI)).

## Visualization (`aegean.viz`, the `[viz]` extra)

One-line matplotlib figures over the corpus model and the analysis layer —
conveniences, not a plotting framework. Each returns the `Axes` (compose with
`ax=`, save with `.figure.savefig(...)`); `import aegean` stays
dependency-free (matplotlib loads only inside the calls; install with
`pip install 'pyaegean[viz]'`).

```python
import aegean
from aegean import viz

c = aegean.load("damos")
viz.plot_sign_frequencies(c, top=20)              # frequency bars (words or signs)
viz.plot_dispersion(c)                            # frequency vs Gries' DP scatter
viz.plot_keyness(c.filter(site="Pylos"),          # diverging log-ratio bars, G² labels
                 [d for d in c.documents if d.meta.site != "Pylos"])
viz.plot_collocation_network(aegean.load("lineara"), "KU-RO")   # ego network (exploratory)
viz.plot_balance(aegean.load("lineara"))          # stated totals vs computed sums
viz.plot_scansion("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
```

The scansion grid draws each syllable with its quantity (— ˘ ×), foot
boundaries, and the caesura (‖); the balance view puts every checked KU-RO /
TO-SO total on a stated-vs-computed diagonal so discrepancies stand out (with
the same heuristic-sections caveat as `balance_check`). From the shell:
`aegean plot freq|dispersion|keyness|network|balance|scansion … -o out.png`.

## Caching expensive analyses (opt-in)

Some analyses are pure but slow — morphological clustering over the whole
vocabulary, repeated dispersion/keyness sweeps, large queries. `aegean.cache` is
an **off-by-default** persistent cache that memoises them to a local sqlite file,
keyed on a content fingerprint of the inputs, so re-running the same analysis on
the same corpus is served from disk. Disabled (the default), it's a transparent
passthrough — it never changes a result, only how fast it arrives. No new
dependency: sqlite3 and pickle are stdlib.

```python
import aegean

aegean.cache.enable()                              # opt in (or PYAEGEAN_ANALYSIS_CACHE=1)
aegean.analysis.find_morphological_clusters(
    aegean.load("lineara").word_frequencies())     # computed once, then from disk
aegean.cache.stats()                               # {'enabled': True, 'entries': 1, 'path': …}
aegean.cache.clear()                               # wipe it
```

It pays off when recompute costs much more than a pass over the corpus (the
fingerprint) — clustering, or the same sweep repeated across a session. The
cache key embeds a format + per-function version, so a library upgrade never
returns a stale result; a corrupt or class-changed entry is treated as a miss
and recomputed. From the shell, `aegean cache` shows the state and `aegean cache
--clear` wipes it (enable it per shell with `PYAEGEAN_ANALYSIS_CACHE=1`). Stored
with pickle in your own cache dir — enable it only for caches you control.

`Corpus.fingerprint()` is the content hash the cache keys on (also useful on its
own to tell whether two corpora — or a corpus and a filtered subset — have the
same analysable content).

## Query engine

A compound predicate engine over the corpus: an inscription/word field registry,
AND/OR/NOT combination, and inscription- or word-output modes. Call it as the
`corpus.query(filters, output=...)` method or the standalone `run_query(corpus, filters)`.

```python
from aegean.analysis import FilterRow, run_query
res = run_query(corpus, [
    FilterRow("id-contains", "HT"),                      # HT tablets (site code is the id prefix)
    FilterRow("word-suffix", "RO", connector="and"),     # …with a word ending in -RO
], output="inscriptions")
[d.id for d in res.inscriptions][:5]                      # ['HT1', 'HT9a', 'HT9b', ...]

words = run_query(corpus, [FilterRow("word-sign-pattern", "KU-*-RO")],
                  output="words").words   # [(word, count), ...]
```

Fields include `site-is`, `scribe-is`, `period-is`, `support-is`, `id-contains`,
`has-image`, `has-annotation`, `ins-contains-word`, and word-scope `word-contains`/`-prefix`/
`-suffix`/`-min-syllables`/`-max-syllables`/`-contains-sign`/`-cooccurs-with`/
`-sign-pattern`. `summarize_filters(...)` renders a one-line label.

## Tablet-structure classification

Heuristic genre classification by content shape — accounting / libation / list /
text / other.

```python
from aegean.analysis import classify_structure, classify_corpus
classify_structure(corpus.get("HT13"))   # e.g. 'accounting'
buckets = classify_corpus(corpus)         # {category: [doc_id, ...]}
{k: len(v) for k, v in buckets.items()}
```
