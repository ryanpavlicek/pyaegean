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
