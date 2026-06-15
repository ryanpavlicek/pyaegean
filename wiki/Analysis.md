# Analysis

`aegean.analysis` is the toolkit's "what can I learn from this corpus?" layer:
weighted phonetic distance and alignment, cross-script sound comparison,
association and corpus statistics (dispersion, keyness, bootstrap), vocabulary
richness, morphology and graphotactics, scribal-hand profiling, accounting and
metrology, a compound query engine, SQLite persistence, and more. Every method
is **exploratory evidence to weigh** — you'd use it to find patterns worth a
closer look, rank candidates, or sanity-check a claim, not to produce a reading.

These are ported faithfully from the Linear A Research Workbench's analytical
code and checked against shared golden fixtures
(`tests/fixtures/golden/algorithms.json`) so the Python port can't silently
diverge, with property tests mirroring the workbench's invariants.

> **Exploratory material.** Linear A is undeciphered: the cross-linguistic and
> decipherment-adjacent methods here surface *evidence to weigh*, never readings
> or translations. The full picture of what pyaegean can and cannot claim is on
> the **[Limitations](Limitations)** page.

Everything below is runnable. The examples were executed against the installed
package on the real bundled corpora (`lineara`, 1,721 inscriptions; `damos`,
the fetched Linear B corpus) and show the **actual** output.

---

## Which analysis → which command

Most analyses have both a Python function and a `aegean ...` shell command.
A few of the newer/lower-level ones are Python-only. This table is the map.

| Analysis | Python | CLI |
| --- | --- | --- |
| Phonetic distance | `phonetic_distance`, `extract_root` | `aegean analyze distance` |
| Per-position alignment | `align_phonetic` | `aegean analyze align` |
| Word-sequence alignment | `align_sequences` | — |
| Cross-script compare | `phonetic_compare`, `romanize_greek` | `aegean analyze compare` |
| Cross-script ranking | `nearest` | `aegean analyze nearest` |
| Word-pair association | `chi_squared_2x2`, `log_likelihood_ratio_2x2`, `fishers_exact`, `pmi_interval` | `aegean analyze assoc` |
| Co-occurring words | `build_cooccurrence_map` | `aegean analyze cooccur` |
| Dispersion (Gries' DP) | `dispersion`, `dispersions` | `aegean dispersion` |
| Keyness (G² + log-ratio) | `keyness` | `aegean keyness` |
| Bootstrap CI | `bootstrap_ci`, `bootstrap_counts_ci` | — |
| Vocabulary richness / info | `chao1`, `mattr`, `fit_heaps`, `fit_zipf_mandelbrot_mle`, `shannon_entropy`, `miller_madow_entropy` | — |
| Morphological clusters | `find_morphological_clusters` | `aegean analyze clusters` |
| Affix productivity / edge bias | `baayen_productivity`, `affix_edge_bias`, `successor_variety` | — |
| Positional bias | `positional_bias` | — |
| Sign-bigram PMI | `sign_bigram_pmi`, `sign_bigram_pmis` | — |
| Graphotactic surprisal | `train_sign_bigram_model`, `word_surprisal` | — |
| Multivariate (CA / UPGMA / communities) | `correspondence_analysis`, `upgma_with_bootstrap`, `label_propagation` | — |
| Linear A vs Linear B divergence | `build_lb_divergence`, `spearman_rho` | — |
| Tablet structure | `classify_structure`, `classify_corpus` | `aegean analyze structure` |
| Scribal hands | `scribal_hands`, `hand_keyness` | `aegean analyze hands` |
| Document-type / dossier / metrology profile | `document_type_profile`, `account_dossiers`, `metrology_profile` | — |
| Commodity / ideogram line stats | `line_cooccurrence_pmi`, `ideogram_group_exclusivity` | — |
| Accounting balance | `balance_check`, `checkable_accounts` | `aegean balance` |
| Sign-pattern search | `word_matches_sign_pattern` | `aegean search` |
| Compound query | `run_query`, `FilterRow` | `aegean query` |
| SQLite persistence + FTS | `db.to_sqlite`, `db.search`, `Corpus.from_sql` | `aegean db build` / `aegean db search` |
| Figures | `aegean.viz.*` | `aegean plot` |

Every CLI command also takes `--json` for machine-readable output. The full CLI
reference is on the **[CLI](CLI)** page.

---

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

From the shell (note: the CLI takes transliterations with hyphens, which it
expands to phonemes — the number can differ from the raw-string call above):

```bash
aegean analyze distance KU-RO KA-RO
# KU-RO ↔ KA-RO: 0.200

aegean analyze distance kuro kulo --json
# { "word1": "kuro", "word2": "kulo", "distance": 0.125 }
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

Per-phoneme alignment classifies each position as one of these operations:

| `op` | Meaning |
| --- | --- |
| `match` | Same phoneme |
| `sub-vowel` | Vowel substituted for a vowel |
| `sub-class` | Consonant substituted within the same articulatory class |
| `sub-far` | Substitution across classes (full cost) |
| `ins` | Insertion (gap in word A) |
| `del` | Deletion (gap in word B) |

```python
from aegean.analysis import align_phonetic
[c.op for c in align_phonetic("ka", "ko")]    # ['match', 'sub-vowel']
[c.op for c in align_phonetic("pa", "ba")]    # ['sub-class', 'match']
```

```bash
aegean analyze align ka ko
#  k  k  match
#  a  o  sub-vowel
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
up by **sound**. The scripts that can be put on the common alphabet are
`PHONEME_SCRIPTS == ('greek', 'lineara', 'linearb', 'cypriot')`.

```python
from aegean.analysis import phonetic_compare, nearest, romanize_greek

romanize_greek("βασιλεύς")                       # 'basileus'  (accents/breathings dropped)
cmp = phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek", fold_aspiration=True)
cmp.similarity                                   # 0.688
[(c.a, c.b, c.op) for c in cmp.alignment][:1]    # [('q', 'b', 'sub-far')] — the qʷ→b reflex

# triage: which Greek words sound closest to a Linear B form?
nearest("qa-si-re-u", "linearb",
        ["ποιμήν", "βασιλεύς", "πατήρ", "θεός"], "greek", fold_aspiration=True)
# [('βασιλεύς', 0.3125), ('πατήρ', 0.614), ('ποιμήν', 0.657), ('θεός', 0.8)]
#  → the true cognate ranks first
```

```bash
aegean analyze compare po-me ποιμήν --fold-aspiration
# po-me [linearb] → pome    ποιμήν [greek] → poimēn
# similarity 0.62  (distance 0.383)
#  p  p  match
#  o  o  match
#  ·  i  ins
#  m  m  match
#  e  ē  sub-vowel
#  ·  n  ins

aegean analyze nearest qa-si-re-u greek --fold-aspiration --top 5
```

The `compare`/`nearest` commands default to `--script-a linearb` and (for
`compare`) `--script-b greek`; pass `--script-a`/`--script-b` to change them.

Two cautions stack here. The distance metric's phoneme classes are already a
linguistic judgement (above); on top of that, **syllabic spelling is defective**
— Linear B and Cypriot drop word-final consonants, omit cluster members, and
don't write aspiration or voicing — so a Greek form looks longer than its
syllabic spelling and the absolute distance is inflated. The reliable signal is
the **ranking** (`nearest`), and an alignment shows a *hypothesised*
correspondence, not a sound law. `fold_aspiration` (θ/φ/χ → t/p/k) meets the
syllabaries' aspiration-blind orthography halfway. See [Limitations](Limitations).

## Word-pair association

Document-level association between two words across N documents (the 2×2 table
counts documents containing both, each alone, and neither). The exact special
functions come from the standard-library `math` module, so there are no
third-party dependencies.

```python
from aegean.analysis import (
    chi_squared_2x2, log_likelihood_ratio_2x2, chi_squared_p_value,
    fishers_exact, wilson_interval, pmi_interval,
)
chi_squared_2x2(5, 10, 10, 100)          # 15.123  (Yates-corrected)
log_likelihood_ratio_2x2(5, 10, 10, 100) # 12.533  (G², Dunning 1993)
chi_squared_p_value(3.841)               # 0.05
fishers_exact(5, 5, 5, 10)               # 0.007937 (two-sided)
wilson_interval(5, 10)                    # (0.2366, 0.7634) 95% CI
pmi_interval(5, 10, 10, 100)             # (1.1072, 3.4822)
```

On a real corpus, the `assoc` command builds the table for you:

```bash
aegean analyze assoc lineara KU-RO KI-RO
# joint / w1 / w2 / docs    5 / 34 / 12 / 1721
# chi_squared               78.75
# p_value                   7.055e-19
# log_likelihood            23.94
# fisher_p                  1.595e-06
# pmi_interval              [3.172, 5.622]
```

To see *what* a word keeps company with, ranked by shared documents:

```bash
aegean analyze cooccur lineara KU-RO --top 5
# KI-RO       5 shared docs
# *306-TU     4
# KU-PA₃-NU   4
# SA-RA₂      4
# *324-DI-RA  3
```

## Corpus statistics: dispersion, keyness, bootstrap

Where association scores one word *pair*, these compare **whole corpora and
subsets** — pure stdlib, working over any loadable corpus (`lineara`, `damos`,
a `filter()` subset, or a plain document list). In plain terms: *dispersion*
asks "is this word everywhere, or does it live in a few documents?"; *keyness*
asks "what vocabulary makes this group of texts different from that one?"; the
*bootstrap* asks "how sure can I be of this number, given how few documents
there are?"

**Dispersion** — Gries' deviation of proportions (DP; Gries 2008, normalized
per Lijffijt & Gries 2012). 0 = spread exactly as document sizes predict;
toward 1 = concentrated in few documents. The `Dispersion` record carries
`item, frequency, range, parts, dp, dp_norm`:

```python
from aegean.analysis import dispersion, dispersions
import aegean

c = aegean.load("lineara")
dispersion(c, "KU-RO")
# Dispersion(item='KU-RO', frequency=37, range=34, parts=559, dp=0.8501, dp_norm=0.8507)
[(x.item, round(x.dp_norm, 2)) for x in dispersions(c, top=5)]
# [('KU-RO', 0.85), ('KI-RO', 0.94), ('KU-PA₃-NU', 0.95), ('SA-RA₂', 0.95), ('A-DU', 0.96)]
```

```bash
aegean dispersion lineara --top 5
# item        freq  range/parts  DP     DPnorm
# KU-RO        37    34/559       0.850  0.851
# KI-RO        16    12/559       0.938  0.938
# KU-PA₃-NU    8     7/559        0.948  0.949
# ...
```

A frequent word with *high* `dp_norm` is the interesting case on Aegean
material — formulaic or genre/site-bound vocabulary rather than corpus-wide
language.

**Keyness** — which items are characteristic of a target (sub)corpus against a
reference: Dunning's log-likelihood **G²** for significance (Rayson & Garside
2000) plus Hardie's (2014) **log-ratio** for effect size (each point ≈ one
doubling of relative frequency; positive = overused in the target). The
`KeynessRow` carries `item, target_count, target_total, reference_count,
reference_total, log_likelihood, log_ratio, p_value`:

```python
from aegean.analysis import keyness

ht = c.filter(site="Haghia Triada")
rest = [d for d in c.documents if d.meta.site != "Haghia Triada"]
for r in keyness(ht, rest)[:3]:
    print(r.item, round(r.log_likelihood, 1), round(r.log_ratio, 2), r.p_value)
# KU-RO   35.2  +4.07  2.9e-09
# SA-RA₂  27.2  +5.30  1.8e-07
# KI-RO   21.7  +4.99  3.1e-06
```

```bash
aegean keyness lineara --site "Haghia Triada" --top 5
# item               target   reference  G2     log-ratio  p
# KU-RO              35/704   2/677      35.23  +4.07      2.9e-09
# SA-RA₂             20/704   0/677      27.23  +5.30      1.8e-07
# KI-RO              16/704   0/677      21.74  +4.99      3.1e-06
# *411-VS            0/704    15/677     21.56  -5.01      3.4e-06
# A-TA-I-*301-WA-JA  0/704    11/677     15.78  -4.58      7.1e-05
```

`aegean keyness` can compare a subset to the rest of its own corpus
(`--site/--period/--scribe/--support`) or to a second corpus (`--reference`),
and `--signs` keys individual signs instead of words.

**Bootstrap confidence intervals** — a percentile interval for *any* corpus
statistic, resampling documents with replacement (Efron & Tibshirani 1993);
documents are the resampling unit because tokens within a tablet are not
independent. Deterministic by default (`seed=0`). The `BootstrapCI` carries
`estimate, low, high, level, n_resamples`:

```python
from aegean.analysis import bootstrap_ci
from aegean.core.model import TokenKind

mean_words = lambda docs: sum(
    sum(1 for t in d.tokens if t.kind is TokenKind.WORD) for d in docs
) / len(docs)
ci = bootstrap_ci(c, mean_words)
(round(ci.estimate, 3), round(ci.low, 3), round(ci.high, 3), ci.level, ci.n_resamples)
# (0.802, 0.718, 0.891, 0.95, 999)
```

A scholarly caution: on small or fragmentary corpora a significant G² flags an
imbalance worth *inspecting*, not a proven fact about the language — read
significance (G², p) together with effect size (log-ratio) and dispersion.
See [Limitations](Limitations).

## Vocabulary richness & information

Estimators that work over a **count vector** (token counts per type), so they
apply to any corpus or subset. All pure stdlib.

| Function | What it answers |
| --- | --- |
| `shannon_entropy(counts)` | Bits per token under the observed distribution |
| `miller_madow_entropy(counts)` | Entropy with the small-sample (Miller–Madow) correction |
| `chao1(s_obs, f1, f2)` | How many types exist *including unseen ones* (lower-bound) |
| `mattr(tokens, window)` | Moving-average type–token ratio (length-robust) |
| `fit_heaps(points)` | Heaps' law fit (vocabulary growth vs tokens) |
| `fit_zipf_mandelbrot_mle(freqs)` | Zipf–Mandelbrot rank–frequency fit |
| `spearman_rho(xs, ys)` | Rank correlation between two series |

```python
from aegean.analysis import (
    shannon_entropy, miller_madow_entropy, chao1, mattr,
    fit_zipf_mandelbrot_mle, spearman_rho,
)
shannon_entropy([10, 5, 5, 1, 1])         # 1.894
miller_madow_entropy([10, 5, 5, 1, 1])    # 2.0252
spearman_rho([1, 2, 3, 4, 5], [2, 1, 4, 3, 5])   # 0.8
```

`chao1` on the real Linear A word vocabulary (995 observed types, 835 hapaxes,
91 dis-legomena) estimates how much vocabulary the corpus has *not yet shown* —
a stark reminder of how fragmentary the material is:

```python
from collections import Counter
cnt = Counter(t.text for d in c.documents for t in d.tokens if t.kind.name == "WORD")
vals = list(cnt.values())
chao1(len(vals), sum(v == 1 for v in vals), sum(v == 2 for v in vals))
# Chao1Result(estimate=4825.9, ci_low=3986.7, ci_high=5900.5, unseen=3830.9)
```

`fit_zipf_mandelbrot_mle` returns `ZipfMandelbrotFit(s, beta, ks, r2_log,
log_z)`; `fit_heaps` returns `HeapsFit(k, beta, r2)`. Treat `unseen` and the
fitted exponents as descriptive of *this surviving sample*, not the lost whole.

## Morphological clustering

Heuristic lemmatization for an undeciphered script: find suffixes productive
across many words, then group words sharing a stem via a productive suffix.

```python
from aegean.analysis import find_morphological_clusters
clusters = find_morphological_clusters(
    c.word_frequencies(),
    min_suffix_productivity=5, min_cluster_size=2, max_suffix_len=2,
)
cl = clusters[0]
cl.stem, cl.total_count, cl.suffixes
# ('JA-SA', 16, ('SA-RA-ME', 'JA', 'MU', 'SA', 'SA-RA', 'SA-RA-MA'))
[(m.word, m.count, m.suffix) for m in cl.members]
# [('JA-SA-SA-RA-ME', 7, 'SA-RA-ME'), ('JA-SA', 4, ''), ('JA-SA-JA', 1, 'JA'), ...]
```

```bash
aegean analyze clusters lineara --top 4
# stem    members                                       suffixes
# JA-SA   JA-SA-SA-RA-ME, JA-SA, JA-SA-JA, JA-SA-MU…    SA-RA-ME, JA, MU, SA, SA-RA, SA-RA-MA
# A-TA    A-TA, A-TA-DE, A-TA-NA, A-TA-NA-JE…           DE, NA, NA-JE, NA-TE, RE
# I-DA    I-DA, I-DA-A, I-DA-DA, I-DA-MI                A, DA, MI
# KU-PA   KU-PA, KU-PA-JA, KU-PA-RI, KU-PA-ZU           JA, RI, ZU
```

## Affix productivity, edge bias & successor variety

Lower-level morphology helpers that take a `(word, count)` frequency list. They
quantify *where* and *how productively* substrings attach — without committing
to any morpheme being "real."

```python
from aegean.analysis import affix_edge_bias, baayen_productivity, successor_variety

wf = c.word_frequencies()

# Which final signs are over-represented at the word edge vs the interior (G²)?
[(r.affix, r.edge_count, round(r.g2, 1)) for r in affix_edge_bias(wf, affix_len=1, mode="suffix")[:5]]
# [('RO', 78, 103.1), ('VS', 30, 43.5), ('RA₂', 39, 43.0), ('NE', 35, 26.9), ('TE', 56, 22.0)]

# Baayen's P (productivity = hapaxes / total) for two-sign suffixes:
[(p.affix, p.count, p.distinct, p.hapax, round(p.productivity, 3))
 for p in baayen_productivity(wf, affix_len=2, mode="suffix")[:3]]
# [('DA-RA', 5, 5, 5, 1.0), ('NA-TE', 4, 4, 4, 1.0), ('RI-JA', 4, 4, 4, 1.0)]

# Successor variety: stems whose next-sign choices branch much more than their parent's
sv = successor_variety([w for w, _ in wf])
sv.total                                                     # 33
[(r.stem, r.variety, r.parent_variety, round(r.ratio, 2)) for r in sv.rows[:3]]
# [('TA-NA', 6, 19, 4.38), ('A-RA', 5, 40, 3.65), ('A-RE', 5, 40, 3.65)]
```

`EdgeBiasRow` = `(affix, edge_count, interior, g2)`; `Productivity` =
`(affix, count, distinct, hapax, productivity)`; `SuccessorRow` =
`(stem, variety, parent_variety, ratio)`. Pass `mode="prefix"` to look at the
front of the word instead.

## Positional bias

Where in the inscription does a word tend to sit — initial, medial, or final?
Takes inscriptions as sign/word sequences and scores each word's positional
skew with a G² against the overall distribution. `PositionalRow` =
`(word, count, initial, medial, final, dominant, g2)`.

```python
from aegean.analysis import positional_bias
seqs = [[t.text for t in d.tokens if t.kind.name == "WORD"] for d in c.documents]
rows = positional_bias(seqs, min_count=2)
[(r.word, r.count, r.dominant, round(r.g2, 1)) for r in rows[:5]]
```

## Sign-bigram PMI

Pointwise mutual information for adjacent sign pairs — which signs "want" to sit
next to each other, beyond chance.

```python
from aegean.analysis import sign_bigram_pmi, sign_bigram_pmis
sign_bigram_pmi(5, 10, 10, 100)          # one pair, from raw counts
pmis = sign_bigram_pmis(c.word_frequencies())   # {(left, right): pmi} over the whole corpus
sorted(pmis.items(), key=lambda kv: -kv[1])[:3]
# [(('*307+*387', 'GRA+QE'), 11.38), (('CYP+D', '*304+PA'), 11.38), ...]
```

## Graphotactic surprisal

A Witten–Bell smoothed sign-bigram model with leave-one-out scoring: how
*surprising* is each sign given the one before it, in bits. High total surprisal
flags a spelling that doesn't fit the corpus's usual sign sequencing.

```python
from aegean.analysis import train_sign_bigram_model, word_surprisal
model = train_sign_bigram_model(c.word_frequencies())
ws = word_surprisal(model, "KU-RO")
round(ws.mean, 3)                                  # 2.158  (mean bits/step)
[(s.from_, s.to, round(s.bits, 2)) for s in ws.steps]
# [('^', 'KU', 4.03), ('KU', 'RO', 2.06), ('RO', '$', 0.39)]
```

`^` and `$` are word-start and word-end. `WordSurprisal` = `(mean, steps)`;
each `SurprisalStep` = `(from_, to, bits)`.

## Multivariate methods

Three from-scratch (no numpy/scipy) multivariate tools for grouping inscriptions
or signs. All deterministic given a seed.

**Correspondence analysis** — a 2-D map of rows (e.g. tablets) and columns
(e.g. commodities) from a contingency table, so associated items land near each
other. Returns `CAResult(rows, cols, inertia, total_inertia)` with each point a
`CAPoint(label, x, y, mass)`:

```python
from aegean.analysis import correspondence_analysis
ca = correspondence_analysis(
    ["HT1", "HT2", "ZA1"], ["GRA", "VIN", "OLE"],
    [[10, 2, 0], [8, 1, 1], [0, 5, 9]],
)
round(ca.total_inertia, 4)                              # 0.6845
[(p.label, round(p.x, 3)) for p in ca.rows]            # [('HT1', -0.711), ('HT2', -0.589), ('ZA1', 1.03)]
[(p.label, round(p.x, 3)) for p in ca.cols]            # [('GRA', -0.798), ('VIN', 0.477), ('OLE', 1.055)]
```

**UPGMA clustering with bootstrap support** — a dendrogram over items described
by feature maps, with branch-support values from resampling. Returns
`DendroResult(labels, merges, order)`; each `DendroMerge` =
`(a, b, height, members, support)`:

```python
from aegean.analysis import upgma_with_bootstrap
items = [("A", {"x": 1.0, "y": 0.0}), ("B", {"x": 0.9, "y": 0.1}),
         ("C", {"x": 0.0, "y": 1.0}), ("D", {"x": 0.1, "y": 0.9})]
d = upgma_with_bootstrap(items, iters=50, seed=42)
[(m.a, m.b, round(m.height, 3), round(m.support, 2)) for m in d.merges]
# [(0, 1, 0.006, 0.78), (2, 3, 0.006, 0.56), (4, 5, 0.89, 1.0)]
#  → {A,B} and {C,D} cluster first, then join; the final split has full support
```

**Label propagation** — community detection on a weighted graph of nodes/edges,
returning a `{node: community_id}` map:

```python
from aegean.analysis import label_propagation
label_propagation(["a", "b", "c", "d"], [("a", "b", 1.0), ("c", "d", 1.0)])
# {'a': 0, 'b': 0, 'c': 1, 'd': 1}
```

## Linear A vs Linear B sign-frequency divergence

A speculative diagnostic: assuming the conventional sign values, which sound
values are written far more (or less) often in Linear A than in deciphered
Linear B? `linear_a_sign_value_counts` tallies sign values on the Linear A side;
`parse_damos_frequencies` builds the Linear B side from a DAMOS frequency
payload; `build_lb_divergence` joins them on shared values, most divergent first.

```python
from aegean.analysis import (
    linear_a_sign_value_counts, parse_damos_frequencies, build_lb_divergence,
)
la = linear_a_sign_value_counts(aegean.load("lineara").word_frequencies())
la.total_signs                          # 3553
la.by_value["ku"]                       # LaValueCount(count=124, labels=['KU'])

# lb = parse_damos_frequencies(damos_frequency_payload)   # a damos-corpus.json frequency dict
# rows = build_lb_divergence(la, lb)
# each row: DivergenceRow(value, labels, la_count, lb_count, la_per_1000, lb_per_1000, log_ratio)
```

> The join **assumes the conventional sign values — that is the hypothesis, not a
> result.** Rates are add-half smoothed before the log₂ ratio, and only values
> attested on both sides are returned. See [Limitations](Limitations).

## Tablet-structure classification

Heuristic genre classification by content shape. The five categories are fixed
(`CATEGORIES`):

| key | label | rule of thumb |
| --- | --- | --- |
| `accounting` | Accounting | Numerals and/or KU-RO total markers |
| `libation` | Libation | Known libation-formula words |
| `list` | Lists | Multiple separators, no numerals |
| `text` | Text / Other | Extended text without numerals |
| `other` | Unclassified | Short or ambiguous inscriptions |

```python
from aegean.analysis import classify_structure, classify_corpus
classify_structure(c.get("HT13"))         # 'accounting'
{k: len(v) for k, v in classify_corpus(c).items()}
# {'accounting': 134, 'libation': 15, 'list': 7, 'text': 2, 'other': 1563}
```

```bash
aegean analyze structure lineara
# accounting  134
# libation     15
# list          7
# text          2
# other      1563

aegean analyze structure lineara HT13      # one document → 'accounting'
```

## Scribal-hand analysis

For a corpus that records a hand per document (DAMOS's `meta.scribe`, and the
Linear A corpus's ~100 attributed hands), `scribal_hands` profiles each one and
`hand_keyness` finds what is characteristic of a hand versus all the others.
`HandProfile` = `(hand, doc_count, token_count, word_count, sites, periods,
top_words)`.

```python
from aegean.analysis import scribal_hands, hand_keyness
d = aegean.load("damos")

for h in scribal_hands(d, min_docs=10)[:3]:        # busiest hands first
    print(h.hand, h.doc_count, list(h.sites)[:2], [w for w, _ in h.top_words[:3]])
# 117 684 ['Knossos'] ['ku-ta-to', 'ru-ki-to', 'pa-i-to']
# 1   227 ['Pylos']   ['pe-mo', 'e-ke', 'pa-ro']
# 103 212 ['Knossos'] ['ko-wo', 'ko-wa', 'o-pi']

[r.item for r in hand_keyness(d, "117")[:6]]       # what hand 117 writes more than the rest
# ['ku-ta-to', 'ru-ki-to', 'ra-to', 'u-ta-jo-jo', 'u-ta-jo', 'pa-i-to']  (Knossos place-names)
```

```bash
aegean analyze hands damos --min-docs 50 --top 5
# hand  tablets  tokens  top words
# 117   684      5152    ku-ta-to, ru-ki-to, pa-i-to, da-wo, e-ko-so
# 1     227      6068    pe-mo, e-ke, pa-ro, ko-to-na, o-na-to
# 103   212      2741    ko-wo, ko-wa, o-pi, tu-na-no, pa-we-a
# ...

aegean analyze hands damos --hand 117          # keyness for one hand (add --signs to key signs)
```

Per-hand dispersion is just the standard helper over the hand's slice —
`dispersion(d.filter(scribe="117"), "some-word")`.

## Corpus profiling: document types, dossiers, metrology

Three higher-level "describe this corpus" profilers, all taking a loaded corpus.

**Document types** — counts and shape per support/object type
(`DocumentTypeProfile(type, count, share_pct, words_per_doc, numerals_pct,
top_sites)`):

```python
from aegean.analysis import document_type_profile
[(p.type, p.count, round(p.share_pct, 1)) for p in document_type_profile(c)[:5]]
# [('Nodule', 886, 51.5), ('Tablet', 393, 22.8), ('Roundel', 151, 8.8),
#  ('Stone vessel', 107, 6.2), ('Clay vessel', 76, 4.4)]
```

**Account dossiers** — for each word that heads accounting entries, gather every
entry, its value, commodity, site, and co-listed words (`Dossier(word, entries,
entry_count, tablet_count, total_value, commodities, sites, co_listed)`):

```python
from aegean.analysis import account_dossiers
doss = account_dossiers(c)
len(doss)                                                    # 425
[(x.word, x.tablet_count, x.total_value) for x in doss[:3]]
# [('SA-RA₂', 15, 1354.75), ('KU-PA₃-NU', 7, 118.0), ('DA-RE', 6, 97.5)]
```

**Metrology profile** — the numeral/fraction system in use: how many numerals
and fractions, which fraction values appear and how often, and a per-commodity
breakdown (`MetrologyProfile(fraction_rows, commodity_profiles, numeral_tokens,
fraction_tokens, integer_tokens, distinct_fraction_values)`):

```python
from aegean.analysis import metrology_profile
mp = metrology_profile(c)
mp.numeral_tokens, mp.fraction_tokens, mp.distinct_fraction_values    # (1592, 295, 10)
[(r.display, r.count) for r in mp.fraction_rows[:5]]
# [('1/2', 121), ('1/4', 56), ('3/4', 27), ('1/16', 26), ('1/3', 24)]
[(cm.head, cm.gloss, cm.entries) for cm in mp.commodity_profiles[:3]]
# [('OLE', 'olive oil', 99), ('GRA', 'grain / wheat', 86), ('CYP', 'cyperus (sedge / spice)', 60)]
```

## Commodity & ideogram line statistics

Statistics over the *lines* of accounting tablets (use `account_lines(doc)` to
get a tablet's line-token sequences).

```python
from aegean.analysis import account_lines, line_cooccurrence_pmi, ideogram_group_exclusivity
lines = [ln for doc in c.documents for ln in account_lines(doc)]

# Which words share a line with the GRA ideogram more than chance (PMI)?
line_cooccurrence_pmi(lines, "GRA", min_joint=2)[:3]
# [('I-QA-*118', 5.168), ('DA-ME', 4.168), ('KU-PA', 4.168)]

# Which words appear (almost) exclusively under one commodity group?
# ExclusivityRow(group, gloss, word, count, word_total, exclusivity)
ex = ideogram_group_exclusivity(lines)
[(r.group, r.word, round(r.exclusivity, 2)) for r in ex[:3]]
# [('GRA', 'DA-ME', 1.0), ('GRA', 'I-QA-*118', 1.0), ('GRA', 'KU-NI-SU', 1.0)]
```

## Accounting reconciliation (KU-RO / TO-SO balance)

Does a tablet's stated total (KU-RO / TO-SO) match the sum of its listed items?
`balance_check` returns one `BalanceCheck` per total marker
(`stated_total, computed_sum, item_count, difference, balances, marker,
total_line_index`); `checkable_accounts` lists the documents worth checking.

```python
from aegean.analysis import balance_check, checkable_accounts
balance_check(c.get("HT13"))
# [BalanceCheck(stated_total=130.5, computed_sum=131.0, item_count=6,
#               difference=0.5, balances=False, marker='KU-RO', total_line_index=7)]
[d.id for d in checkable_accounts(c)[:5]]
# ['HT9a', 'HT9b', 'HT11b', 'HT13', 'HT89']
```

```bash
aegean balance lineara
# doc    marker  stated  computed  diff    balances
# HT9a   KU-RO   31.75   31.0      -0.75   NO
# HT9b   KU-RO   24.0    24.0      0.0     yes
# HT11b  KU-RO   180.0   180.0     0.0     yes
# HT13   KU-RO   130.5   131.0     0.5     NO
# ...
```

> Section-splitting on undeciphered tablets is heuristic, so a non-zero `diff`
> can be a damaged line or a mis-segmented item, not an ancient scribal error.
> Read these as leads, not verdicts. See [Limitations](Limitations).

## Sign-pattern search

Wildcard matching over a word's sign sequence (`*` = exactly one sign, `**` =
zero or more). `SIGN_PATTERN_HELP` carries the live syntax string.

```python
from aegean.analysis import word_matches_sign_pattern, SIGN_PATTERN_HELP
SIGN_PATTERN_HELP
# 'Dash-separated sign labels. Use * for one sign (any value), ** for zero or
#  more. Examples: KU-*-RO · **-RE · JA-SA-** · *-KU-*'
word_matches_sign_pattern("KU-MA-RO", "KU-*-RO")     # True
```

```bash
aegean search lineara "KU-*-RO"
# 'KU-*-RO': 1 word(s)
# KU-MA-RO   1
```

## Query engine

A compound predicate engine over the corpus: an inscription/word field registry,
AND/OR/NOT combination, and inscription- or word-output modes. Call it as the
`corpus.query(filters, output=...)` method or the standalone
`run_query(corpus, filters)`.

```python
from aegean.analysis import FilterRow, run_query, summarize_filters
filters = [
    FilterRow("id-contains", "HT"),                      # HT tablets (site code is the id prefix)
    FilterRow("word-suffix", "RO", connector="and"),     # …with a word ending in -RO
]
res = run_query(c, filters, output="inscriptions")
summarize_filters(filters)        # 'Inscription ID contains: HT · Word ends with: RO'
len(res.inscriptions)             # 49
[d.id for d in res.inscriptions][:5]   # ['HT1', 'HT9a', 'HT9b', 'HT11a', 'HT11b']

run_query(c, [FilterRow("word-sign-pattern", "KU-*-RO")], output="words").words
# [('KU-MA-RO', 1)]
```

```bash
aegean query lineara --where id-contains=HT --where word-suffix=RO --limit 5
# id     site           words
# HT1    Haghia Triada  6
# HT9a   Haghia Triada  9
# ...
# (prefix a field with ! to negate, or or: to OR it; --output-kind words for word output)
aegean query lineara --fields          # list the queryable fields and exit
```

The full field registry (`FIELDS`):

| Field | Scope | Kind |
| --- | --- | --- |
| `id-contains` | inscription | text |
| `site-is` | inscription | site |
| `scribe-is` | inscription | scribe |
| `period-is` | inscription | period |
| `support-is` | inscription | support |
| `has-image` | inscription | boolean |
| `has-annotation` | inscription | boolean |
| `ins-contains-word` | inscription | word |
| `word-contains` | word | text |
| `word-prefix` | word | text |
| `word-suffix` | word | text |
| `word-min-syllables` | word | number (≥ N signs) |
| `word-max-syllables` | word | number (≤ N signs) |
| `word-contains-sign` | word | sign |
| `word-cooccurs-with` | word | word |
| `word-sign-pattern` | word | text (wildcard sign pattern) |

`FilterRow(field, value, connector=...)` where `connector` is `"and"` / `"or"`;
prefix nothing for the default. `summarize_filters(...)` renders a one-line label.

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
aegean.cache.stats()                               # {'enabled': True, 'path': …, 'entries': 0}
aegean.analysis.find_morphological_clusters(
    aegean.load("lineara").word_frequencies())     # computed once, then from disk
aegean.cache.stats()                               # {'enabled': True, 'entries': 1, 'path': …}
aegean.cache.clear()                               # wipe it → entries back to 0
```

It pays off when recompute costs much more than a pass over the corpus (the
fingerprint) — clustering, or the same sweep repeated across a session. The
cache key embeds a format + per-function version, so a library upgrade never
returns a stale result; a corrupt or class-changed entry is treated as a miss
and recomputed. From the shell, `aegean cache` shows the state and
`aegean cache --clear` wipes it (enable it per shell with
`PYAEGEAN_ANALYSIS_CACHE=1`). Stored with pickle in your own cache dir — enable
it only for caches you control.

```bash
aegean cache
# analysis cache: off — set PYAEGEAN_ANALYSIS_CACHE=1 (or a path) to enable
```

`Corpus.fingerprint()` is the content hash the cache keys on (also useful on its
own to tell whether two corpora — or a corpus and a filtered subset — have the
same analysable content):

```python
aegean.load("lineara").fingerprint()[:16]          # '288e80c493eb478b'
```

## SQLite persistence & full-text search (`aegean.db`)

A corpus can be persisted to a queryable SQLite database — stdlib `sqlite3`
only, no new dependency — and reloaded losslessly:

```python
from aegean import db, Corpus

db.to_sqlite(c, "corpus.db")                # documents + tokens as rows, with an FTS5 index
again = Corpus.from_sql("corpus.db")        # round-trips: len(again) == 1721
db.search("corpus.db", "KU-RO")             # full-text search → [(doc_id, position, text), ...]
# first hit: ('HT9a', 25, 'KU-RO')   — 39 hits across the corpus
for doc in db.stream("corpus.db"):          # iterate without loading the whole corpus
    ...
```

`Corpus.to_sql` / `Corpus.from_sql` are the thin method wrappers; on the CLI,
`aegean db build` / `aegean db search` (and `aegean export -f sqlite`):

```bash
aegean db build lineara -o la.db            # wrote 1721 documents to la.db  (--no-fts to skip FTS5)
aegean db search la.db KU-RO --limit 3
# doc    pos  text
# HT9a   25   KU-RO
# HT9b   20   KU-RO
# HT11a  7    KU-RO
```

---

## Notes & limitations

- Everything over Linear A is **exploratory**: it surfaces patterns and ranks
  candidates, never readings. The cross-script and Linear A↔B methods *assume*
  the conventional sign values — that assumption is the hypothesis under test,
  not a result.
- Statistics on a fragmentary corpus are fragile: read significance (G², p)
  alongside effect size (log-ratio), dispersion, and raw counts; the `chao1`
  estimate above (≈3,800 unseen types) is a blunt reminder of how much is
  missing.
- Accounting/metrology results inherit the heuristic line-segmentation of
  undeciphered tablets, so a non-balancing total may be damage or
  mis-segmentation rather than an ancient error.

The honest, consolidated account of what pyaegean can and cannot claim is on the
**[Limitations](Limitations)** page. Related: [Greek NLP](Greek-NLP),
[Meters](Meters), [Linear A](Linear-A), [CLI](CLI),
[Getting Started](Getting-Started).
