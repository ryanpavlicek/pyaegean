# Analysis

`aegean.analysis` provides the statistical, distributional, structural, and
query layer over any loaded corpus: weighted phonetic distance and alignment,
cross-script comparison, association tests, dispersion, keyness, bootstrap
intervals, vocabulary richness, morphology and graphotactics, scribal-hand
profiling, accounting reconciliation, a compound query engine, SQLite
persistence, and matplotlib plotting.

The statistical and structural algorithms mirror the Linear A Research
Workbench and are verified against shared golden fixtures
(`tests/fixtures/golden/algorithms.json`).

> **Scope note.** Linear A and Cypro-Minoan are undeciphered. Statistical,
> distributional, and cross-script methods over those corpora generate
> exploratory leads and rank candidates; they do not establish readings or
> translations. See [Limitations](Limitations).

All examples below were executed against the bundled `lineara` corpus (1,721
inscriptions) and the fetched `damos` Linear B corpus.

---

## Analysis map (Python and CLI)

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
| Paired significance (A vs B) | `mcnemar`, `paired_bootstrap` | — |
| Monte-Carlo null models | `monte_carlo_p` | — |
| Vocabulary richness / entropy | `chao1`, `mattr`, `fit_heaps`, `fit_zipf_mandelbrot_mle`, `shannon_entropy`, `miller_madow_entropy` | — |
| Morphological clusters | `find_morphological_clusters` | `aegean analyze clusters` |
| Morpheme segmentation | `segment`, `candidate_morphs` | — |
| Sign embeddings | `sign_embeddings` | — |
| Brown sign-class induction | `induce_classes` | — |
| Cross-script alignment (measured null) | `align_scripts`, `rank_known_pairs`, `recover_identity` | — |
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

Reporting commands accept `--json`; file-writing commands (`db build`, `plot`)
use `-o`. See [CLI](CLI) for complete flag documentation.

---

## Phonetic distance and classes

`phonetic_distance` computes a weighted Levenshtein distance over phonetic
strings normalized to `[0, 1]`: vowel-to-vowel substitutions cost `0.3`,
same-articulatory-class consonant substitutions cost `0.5`, and all other
substitutions or indels cost `1.0`.

```python
from aegean.analysis import phonetic_distance, extract_root
phonetic_distance("kuro", "kuro")     # 0.0
phonetic_distance("kuro", "karo")     # 0.075 (one vowel swap / 4)
phonetic_distance("kuro", "kulo")     # 0.125 (r↔l, same class / 4)
extract_root("KU-RO")                 # 'kr'  (consonant skeleton)
```

The CLI converts hyphenated transliterations into phonetic strings before
scoring, so CLI and raw-string distances can differ when transliteration expands
a sign:

```bash
aegean analyze distance KU-RO KA-RO
# KU-RO ↔ KA-RO: 0.200

aegean analyze distance kuro kulo --json
# { "word1": "kuro", "word2": "kulo", "distance": 0.125 }
```

Articulatory class membership is configurable via `PhoneticScheme`:

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

Per-phoneme alignment tags each aligned position with one operation:

| `op` | Meaning |
| --- | --- |
| `match` | Identical phoneme |
| `sub-vowel` | Vowel-to-vowel substitution |
| `sub-class` | Consonant substitution within one articulatory class |
| `sub-far` | Cross-class substitution (full cost) |
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

Progressive Needleman–Wunsch (`align_sequences`) aligns multiple word sequences
across inscriptions:

```python
from aegean.analysis import align_sequences
align_sequences([["A-B", "X-Y", "C-D"], ["A-B", "Z-Z", "C-D"]])
# [['A-B','A-B'], ['X-Y','Z-Z'], ['C-D','C-D']]
```

## Cross-script comparison

`aegean.analysis.compare` compares words across scripts by projecting each into
a shared Latin phoneme alphabet (`PHONEME_SCRIPTS == ('greek', 'lineara',
'linearb', 'cypriot')`), using `word_to_phonetic` for syllabaries and
`romanize_greek` for alphabetic Greek.

```python
from aegean.analysis import phonetic_compare, nearest, romanize_greek

romanize_greek("βασιλεύς")                       # 'basileus' (accents and breathings stripped)
cmp = phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek", fold_aspiration=True)
cmp.similarity                                   # 0.5625
[(c.a, c.b, c.op) for c in cmp.alignment][:2]    # [('k', '', 'del'), ('w', 'b', 'sub-far')]

nearest("qa-si-re-u", "linearb",
        ["ποιμήν", "βασιλεύς", "πατήρ", "θεός"], "greek", fold_aspiration=True)
# [('βασιλεύς', 0.4375), ('πατήρ', 0.6625), ('ποιμήν', 0.7), ('θεός', 0.7875)]
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

CLI `compare` and `nearest` default to `--script-a linearb` (and `--script-b
greek` for `compare`).

Syllabic orthography omits word-final consonants, simplifies consonant clusters,
and does not mark aspiration or voicing, which inflates absolute edit distance
against alphabetic Greek. Relative ranking (`nearest`) is more informative than
raw distance, and `fold_aspiration=True` (`θ/φ/χ → t/p/k`) partially compensates
for aspiration-blind syllabic spelling.

## Word-pair association

Document-level 2×2 association statistics count documents containing both words,
each alone, and neither. All functions use Python's standard library `math`
module with no third-party dependencies.

```python
from aegean.analysis import (
    chi_squared_2x2, log_likelihood_ratio_2x2, chi_squared_p_value,
    fishers_exact, wilson_interval, pmi_interval,
)
chi_squared_2x2(5, 10, 10, 100)          # 15.123 (Yates-corrected)
log_likelihood_ratio_2x2(5, 10, 10, 100) # 12.533 (G², Dunning 1993)
chi_squared_p_value(3.841)               # 0.05
fishers_exact(5, 5, 5, 10)               # 0.007937 (two-sided)
wilson_interval(5, 10)                   # (0.2366, 0.7634) 95% CI
pmi_interval(5, 10, 10, 100)             # (1.1072, 3.4822)
```

CLI association and co-occurrence commands:

```bash
aegean analyze assoc lineara KU-RO KI-RO
# joint / w1 / w2 / docs    5 / 34 / 12 / 1721
# chi_squared               78.75
# p_value                   7.055e-19
# log_likelihood            23.94
# fisher_p                  1.595e-06
# pmi_interval              [3.1720137984039996, 5.621837690118523]

aegean analyze cooccur lineara KU-RO --top 5
# KI-RO       5 shared docs
# *306-TU     4
# KU-PA₃-NU   4
# SA-RA₂      4
# *324-DI-RA  3
```

## Corpus statistics: dispersion, keyness, bootstrap

These pure-stdlib functions operate over whole corpora, `filter()` subsets, or
plain lists of `Document` objects.

**Dispersion** computes Gries' deviation of proportions (DP; Gries 2008,
normalized per Lijffijt & Gries 2012). Values near 0 indicate distribution
proportional to document lengths; values near 1 indicate concentration in a
small number of documents. `Dispersion` fields are `item`, `frequency`, `range`,
`parts`, `dp`, and `dp_norm`:

```python
import aegean
from aegean.analysis import dispersion, dispersions

c = aegean.load("lineara")
dispersion(c, "KU-RO")
# Dispersion(item='KU-RO', frequency=37, range=34, parts=559, dp=0.8501, dp_norm=0.8507)
[(x.item, round(x.dp_norm, 2)) for x in dispersions(c, top=5)]
# [('KU-RO', 0.85), ('KI-RO', 0.94), ('SA-RA₂', 0.95), ('KU-PA₃-NU', 0.95), ('A-DU', 0.96)]
```

```bash
aegean dispersion lineara --top 5
# item        freq  range/parts  DP     DPnorm
# KU-RO        37    34/559       0.850  0.851
# KI-RO        16    12/559       0.938  0.938
# SA-RA₂       20    20/559       0.948  0.949
# ...
```

A high-frequency word with high `dp_norm` typically reflects formulaic,
genre-specific, or site-bound vocabulary.

**Keyness** identifies items over- or under-represented in a target subcorpus
compared with a reference using Dunning's log-likelihood G² (Rayson & Garside
2000) and Hardie's (2014) log-ratio effect size (each +1.0 represents roughly a
doubling of relative frequency). `KeynessRow` carries `item`, `target_count`,
`target_total`, `reference_count`, `reference_total`, `log_likelihood`,
`log_ratio`, and `p_value`:

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

`aegean keyness` compares either a metadata slice (`--site`, `--period`,
`--scribe`, `--support`) against the remainder of its corpus, or against an
external `--reference` corpus; `--signs` compares signs rather than words.

**Bootstrap confidence intervals** (`bootstrap_ci`) compute percentile intervals
for any corpus statistic by resampling documents with replacement (Efron &
Tibshirani 1993), respecting within-document token dependence. Deterministic by
default (`seed=0`). `BootstrapCI` holds `estimate`, `low`, `high`, `level`, and
`n_resamples`:

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

On small or fragmentary corpora, read G² and p-values alongside log-ratio effect
size and dispersion.

### Explicit word-count populations

`Corpus.word_frequencies()` defaults to exact surface spelling and token counts.
Pass `view="normalized"` for NFC, lowercase, and final-sigma folding while
retaining diacritics and iota subscript, or `view="lemma"` to count existing
lemma annotations (without running an analyzer; tokens lacking lemmas are
excluded and counted in metadata). `count_unit="document"` counts document
frequency rather than token frequency. Filtering by `statuses` requires both the
token status and every typed editorial segment to qualify.

```python
sample = aegean.io.from_text("Λόγος λόγος λόγος.")
counts = sample.word_frequencies(
    view="normalized", count_unit="document", statuses=["certain"],
)
list(counts)                                      # [('λόγοσ', 1)]
tuple(counts.metadata[k] for k in ("view", "count_unit", "denominator"))
# ('normalized', 'document', 1)
sample.word_frequencies(view="lemma").metadata["missing_lemma_tokens"]  # 3
print(counts.cite())                              # source and counting choices
```

The list-compatible result retains its denominator, exclusions, normalization,
status selection, and lemma-source labels in `metadata`. On the CLI,
`aegean stats --view ... --count-unit ... --statuses ... --details --json`
exposes the same controls. `dispersion` and `keyness` continue to operate on
surface words or signs.

## Paired significance tests

To test whether two systems differ on the same aligned item set, use `mcnemar`
or `paired_bootstrap` (both stdlib-only and deterministic by seed).

**McNemar's test** compares binary per-item correctness on discordant items
(`b` = A correct / B wrong, `c` = A wrong / B correct), using the exact
two-sided binomial test for small discordant counts and continuity-corrected
chi-square otherwise:

```python
from aegean.analysis import mcnemar
r = mcnemar([True, True, False, True], [True, False, False, False])
r.b, r.c, r.method, round(r.p_value, 4)     # (2, 0, 'exact', 0.5)
```

**Paired bootstrap** resamples per-item score differences `A − B` for any real
metric (accuracy, per-sentence LAS, similarity) and returns the mean difference,
percentile CI, and resample win fractions:

```python
from aegean.analysis import paired_bootstrap
r = paired_bootstrap([1, 1, 1, 1, 0, 1], [0, 1, 0, 1, 0, 0], seed=1)
round(r.mean_difference, 3), round(r.frac_a, 2)   # (0.5, 0.99)
(round(r.low, 2), round(r.high, 2))               # 95% CI on mean difference
```

`McNemarResult` holds `(b, c, statistic, p_value, method)`;
`PairedBootstrapResult` holds `(mean_difference, low, high, level, n_resamples,
frac_a, frac_b)`. Both assume paired items in matching order and measure
sampling variance only, not dataset representativeness.

## Monte-Carlo null models

`monte_carlo_p` tests any structure statistic
(`Callable[[Sequence[str]], float]` over hyphenated sign-sequence words, larger
= more structured) against a seeded null distribution:

```python
import statistics
import aegean
from aegean.analysis import monte_carlo_p, train_sign_bigram_model, word_surprisal

c = aegean.load("lineara")
words = [t.text for d in c.documents for t in d.tokens if t.kind.name == "WORD" and "-" in t.text]
model = train_sign_bigram_model(c.word_frequencies())
stat = lambda ws: statistics.mean(word_surprisal(model, w).mean for w in ws)

res = monte_carlo_p(stat(words), stat, words, null="within_word", n=999, seed=0)
res.observed, round(res.p_value, 4), res.null    # (..., ..., 'within_word')
```

`MonteCarloResult` holds `(observed, p_value, null_mean, null_low, null_high,
level, n, null)`. The upper-tail p-value is `(1 + #{null ≥ observed}) / (1 + n)`.

| `null` | Preserves | Destroys |
| --- | --- | --- |
| `within_word` | Per-word length and corpus-wide unigram sign counts | Sign order and within-word co-occurrence |
| `reshuffle` | Every word intact and per-length word counts | Word position in the list |

Report the null model, seed, and `n` alongside the p-value. A small p-value
shows departure from the stated null, not confirmation of a morpheme or reading.

## Vocabulary richness and information

Pure-stdlib estimators over type-count vectors:

| Function | Quantity |
| --- | --- |
| `shannon_entropy(counts)` | Bits per token under the observed distribution |
| `miller_madow_entropy(counts)` | Entropy with Miller–Madow small-sample correction |
| `chao1(s_obs, f1, f2)` | Lower-bound estimate of total vocabulary including unseen types |
| `mattr(tokens, window)` | Moving-average type–token ratio (independent of text length) |
| `fit_heaps(points)` | Heaps' law fit (vocabulary growth vs tokens) |
| `fit_zipf_mandelbrot_mle(freqs)` | Zipf–Mandelbrot rank–frequency MLE fit |
| `spearman_rho(xs, ys)` | Spearman rank correlation |

```python
from aegean.analysis import (
    shannon_entropy, miller_madow_entropy, chao1, mattr,
    fit_zipf_mandelbrot_mle, spearman_rho,
)
shannon_entropy([10, 5, 5, 1, 1])                 # 1.894
miller_madow_entropy([10, 5, 5, 1, 1])            # 2.0252
spearman_rho([1, 2, 3, 4, 5], [2, 1, 4, 3, 5])    # 0.8
```

`chao1` on Linear A words (995 observed types, 835 hapaxes, 91 dis-legomena):

```python
from collections import Counter
cnt = Counter(t.text for d in c.documents for t in d.tokens if t.kind.name == "WORD")
vals = list(cnt.values())
chao1(len(vals), sum(v == 1 for v in vals), sum(v == 2 for v in vals))
# Chao1Result(estimate=4825.9, ci_low=3986.7, ci_high=5900.5, unseen=3830.9)
```

`fit_zipf_mandelbrot_mle` returns `ZipfMandelbrotFit(s, beta, ks, r2_log,
log_z)`; `fit_heaps` returns `HeapsFit(k, beta, r2)`. All fitted parameters
describe the surviving sample.

## Morphological clustering

`find_morphological_clusters` identifies suffixes occurring across multiple
distinct words and groups words sharing a stem:

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

## Morpheme segmentation (Harris)

`segment` cuts each word at local peaks of forward successor variety and
backward predecessor variety (Harris's distributional boundary criterion),
taking the union of both cut sets across the vocabulary:

```python
from aegean.analysis import segment, candidate_morphs
wf = [w for w, _ in c.word_frequencies()]

seg = segment(["A-TA-NA-JE", "A-TA-DE"])[0]
seg.word, seg.cuts, seg.pieces

candidate_morphs(wf, min_count=5)[:5]
# [('TE', 37), ('NA', 36), ('JA', 34), ('RE', 34), ('TI', 29)]
```

`Segmentation` holds `(word, units, cuts, pieces)`. `candidate_morphs(words, *,
min_count=2)` counts distinct word types ending in each word-final morph so
high-frequency words do not inflate the score. On hapax-heavy corpora the
variety signal is sparse; high-count morphs are candidate suffixes to inspect.

## Sign embeddings

`sign_embeddings` builds a dense distributional vector per sign from
within-word adjacency: a sign-by-context co-occurrence matrix, PPMI-weighted,
reduced by deterministic truncated SVD, and L2-normalized (no `numpy` or
`scipy`).

```python
from aegean.analysis import sign_embeddings
emb = sign_embeddings(c)                    # dim=50, window=1 by default
emb.dim, len(emb.vocab)                     # (50, 162)
[s for s, _ in emb.neighbours("KU", k=3)]
```

`SignEmbeddings` exposes `vocab`, `vectors`, `dim`, `window`, and
`neighbours(sign, k=...)` ranked by cosine similarity. Vectors capture
distributional context rather than phonetic or semantic identity, and small
corpora produce noisy neighborhoods.

## Brown sign-class induction

`induce_classes` partitions signs into `n_classes` distributional clusters via
Brown clustering (Brown et al. 1992), greedily merging the class pair with the
smallest loss in average bigram mutual information:

```python
from aegean.analysis import induce_classes
sc = induce_classes(c, n_classes=8)
len(sc)                  # 8
sc.classes()[0][:5]      # members of class 0, sorted
sc.class_of("KU")        # integer class id (-1 if unattested)
sc.report                # mutual information, perplexity, and corpus size
```

`SignClasses` exposes `class_of(sign)`, `classes()`, and `report`. Shared class
membership reflects shared adjacency contexts rather than phonetic identity, and
sparse bigram counts on small corpora can overfit.

## Cross-script alignment, and the null it measured

`align_scripts` computes the orthogonal Procrustes rotation mapping one script's
[sign embeddings](#sign-embeddings) onto another's using shared-label anchors,
and ranks candidate target signs for each source sign.

Calibrated by leave-one-out over the 53 signs shared between Linear A and Linear
B (measured 2026-07-11 on bundled `lineara` vs syllabogram-restricted DAMOS
Linear B; protocol and full rank distribution in
`training/results/procrustes-null-2026-07-11.json`), the method recovers **no
signal**:

- Top-1 recovery: `0.000`
- Top-5 recovery: `0.094` (chance `5/73 = 0.068`)
- Median rank: `26` of `73` (chance median `37`)
- Self-alignment sanity check (`recover_identity` on Linear A): `90.1%` top-1
  recovery (the remaining 16 signs are hapax `*NNN` signs sharing identical
  contexts)

Distributional embedding alignment carries no recoverable Linear A to Linear B
correspondence at this corpus scale. The calibration functions
(`recover_identity`, `rank_known_pairs`) and ranked-hypothesis API
(`align_scripts(...).hypotheses()`) remain available to re-test the method on
alternative embeddings, larger corpora, or different seed anchors.

```python
import aegean
from aegean.analysis import (
    recover_identity, rank_known_pairs, shared_label_anchors, sign_embeddings,
)

la = sign_embeddings(aegean.load("lineara"))
recover_identity(la, anchor_fraction=1.0).top1_recovery      # 0.90 on Linear A

# lb is the syllabogram-restricted DAMOS Linear B embedding (see evidence JSON)
rep = rank_known_pairs(la, lb, shared_label_anchors(la, lb))
rep.top1, rep.median_rank, rep.chance_median                 # 0.0, 26.0, 37.0
```

## Affix productivity, edge bias, and successor variety

Low-level morphological statistics over `(word, count)` frequency lists:

```python
from aegean.analysis import affix_edge_bias, baayen_productivity, successor_variety

wf = c.word_frequencies()

# Final signs over-represented at word edge vs interior (G²)
[(r.affix, r.edge_count, round(r.g2, 1)) for r in affix_edge_bias(wf, affix_len=1, mode="suffix")[:5]]
# [('RO', 78, 103.1), ('VS', 30, 43.5), ('RA₂', 39, 43.0), ('NE', 35, 26.9), ('TE', 56, 22.0)]

# Baayen's P (hapaxes / total) for two-sign suffixes
[(p.affix, p.count, p.distinct, p.hapax, round(p.productivity, 3))
 for p in baayen_productivity(wf, affix_len=2, mode="suffix")[:3]]
# [('DA-RA', 5, 5, 5, 1.0), ('NA-TE', 4, 4, 4, 1.0), ('RI-JA', 4, 4, 4, 1.0)]

# Stems whose next-sign branching exceeds their parent stem's branching
sv = successor_variety([w for w, _ in wf])
sv.total                                                     # 33
[(r.stem, r.variety, r.parent_variety, round(r.ratio, 2)) for r in sv.rows[:3]]
# [('TA-NA', 6, 19, 4.38), ('A-RA', 5, 40, 3.65), ('A-RE', 5, 40, 3.65)]
```

Result records: `EdgeBiasRow(affix, edge_count, interior, g2)`,
`Productivity(affix, count, distinct, hapax, productivity)`, and
`SuccessorRow(stem, variety, parent_variety, ratio)`. Pass `mode="prefix"` for
word-initial affixes.

## Positional bias

`positional_bias` scores whether each word appears preferentially in initial,
medial, or final inscription position using G² against the corpus positional
distribution. `PositionalRow` holds `(word, count, initial, medial, final,
dominant, g2)`:

```python
from aegean.analysis import positional_bias
seqs = [[t.text for t in d.tokens if t.kind.name == "WORD"] for d in c.documents]
rows = positional_bias(seqs, min_count=2)
[(r.word, r.count, r.dominant, round(r.g2, 1)) for r in rows[:5]]
```

## Sign-bigram PMI

Pointwise mutual information for adjacent sign pairs:

```python
from aegean.analysis import sign_bigram_pmi, sign_bigram_pmis
sign_bigram_pmi(5, 10, 10, 100)
pmis = sign_bigram_pmis(c.word_frequencies())   # {(left, right): pmi}
sorted(pmis.items(), key=lambda kv: -kv[1])[:3]
# [(('*307+*387', 'GRA+QE'), 11.38), (('CYP+D', '*304+PA'), 11.38), (('HIDE+[?]', '*328'), 11.38)]
```

## Graphotactic surprisal

A Witten–Bell smoothed sign-bigram model with leave-one-out scoring measures
each sign transition in bits. High total surprisal flags spellings that depart
from common corpus transitions:

```python
from aegean.analysis import train_sign_bigram_model, word_surprisal
model = train_sign_bigram_model(c.word_frequencies())
ws = word_surprisal(model, "KU-RO")
round(ws.mean, 3)                                  # 2.158 bits/step
[(s.from_, s.to, round(s.bits, 2)) for s in ws.steps]
# [('^', 'KU', 4.03), ('KU', 'RO', 2.06), ('RO', '$', 0.39)]
```

`^` and `$` mark word start and word end. `WordSurprisal` holds `(mean, steps)`;
each `SurprisalStep` holds `(from_, to, bits)`.

## Multivariate methods

Three pure-Python (no `numpy`/`scipy`) multivariate methods, all deterministic
for a given seed:

**Correspondence analysis** projects rows and columns of a contingency table
into 2-D coordinates (`CAResult(rows, cols, inertia, total_inertia)`, each point
`CAPoint(label, x, y, mass)`):

```python
from aegean.analysis import correspondence_analysis
ca = correspondence_analysis(
    ["HT1", "HT2", "ZA1"], ["GRA", "VIN", "OLE"],
    [[10, 2, 0], [8, 1, 1], [0, 5, 9]],
)
round(ca.total_inertia, 4)                              # 0.6845
[(p.label, round(p.x, 3)) for p in ca.rows]             # [('HT1', -0.711), ('HT2', -0.589), ('ZA1', 1.03)]
[(p.label, round(p.x, 3)) for p in ca.cols]             # [('GRA', -0.798), ('VIN', 0.477), ('OLE', 1.055)]
```

**UPGMA clustering with bootstrap support** constructs a dendrogram over
feature-map items with branch support from resampling (`DendroResult(labels,
merges, order)`; `DendroMerge(a, b, height, members, support)`):

```python
from aegean.analysis import upgma_with_bootstrap
items = [("A", {"x": 1.0, "y": 0.0}), ("B", {"x": 0.9, "y": 0.1}),
         ("C", {"x": 0.0, "y": 1.0}), ("D", {"x": 0.1, "y": 0.9})]
d = upgma_with_bootstrap(items, iters=50, seed=42)
[(m.a, m.b, round(m.height, 3), round(m.support, 2)) for m in d.merges]
# [(0, 1, 0.006, 0.78), (2, 3, 0.006, 0.56), (4, 5, 0.89, 1.0)]
```

**Label propagation** detects communities on a weighted graph and returns
`{node: community_id}`:

```python
from aegean.analysis import label_propagation
label_propagation(["a", "b", "c", "d"], [("a", "b", 1.0), ("c", "d", 1.0)])
# {'a': 0, 'b': 0, 'c': 1, 'd': 1}
```

## Linear A vs Linear B sign-frequency divergence

Assuming the conventional Linear B sound values for Linear A signs,
`build_lb_divergence` compares relative sign frequencies between Linear A and
DAMOS Linear B (including `kwa/kwe/dza/dze/dzo` alignment).
`linear_a_sign_value_counts` tallies Linear A lexical words (retaining `NI` as a
syllabogram inside hyphenated words), and `parse_damos_frequencies` parses a
DAMOS frequency payload:

```python
from aegean.analysis import (
    linear_a_sign_value_counts, parse_damos_frequencies, build_lb_divergence,
)
la = linear_a_sign_value_counts(aegean.load("lineara").word_frequencies())
la.total_signs                          # 3746
la.by_value["ku"]                       # LaValueCount(count=135, labels=['KU'])

# lb = parse_damos_frequencies(damos_frequency_payload)
# rows = build_lb_divergence(la, lb)
# DivergenceRow(value, labels, la_count, lb_count, la_per_1000, lb_per_1000, log_ratio)
```

> **Circularity caveat.** The join assumes the conventional Linear B sign
> values. Rates use add-half smoothing before the log₂ ratio, and only values
> attested in both scripts are returned.

## Tablet-structure classification

Heuristic classification by token-stream shape over five fixed categories
(`CATEGORIES`):

| Key | Label | Rule |
| --- | --- | --- |
| `accounting` | Accounting | Total marker (`KU-RO`, `KU-RA`, `PO-TO-KU-RO`), or numerals/fractions with > 2 multi-sign words |
| `libation` | Libation | Any of the 14 attested libation-formula words |
| `list` | Lists | More than 3 separator marks and no numerals |
| `text` | Text / Other | More than 4 multi-sign words and no numerals |
| `other` | Unclassified | Short or ambiguous inscriptions |

```python
from aegean.analysis import classify_structure, classify_corpus
classify_structure(c.get("HT13"))         # 'accounting'
{k: len(v) for k, v in classify_corpus(c).items()}
# {'accounting': 137, 'libation': 25, 'list': 5, 'text': 1, 'other': 1553}
```

```bash
aegean analyze structure lineara
# accounting  137
# libation     25
# list          5
# text          1
# other      1553

aegean analyze structure lineara HT13      # one document → 'accounting'
```

## Scribal-hand analysis

For any corpus populating `meta.scribe` (such as DAMOS or the bundled Linear A
corpus), `scribal_hands` builds a `HandProfile(hand, doc_count, token_count,
word_count, sites, periods, top_words)` per hand, and `hand_keyness` computes
one hand's log-likelihood keyness against the remainder of the corpus:

```python
from aegean.analysis import scribal_hands, hand_keyness
d = aegean.load("damos")

for h in scribal_hands(d, min_docs=10)[:3]:
    print(h.hand, h.doc_count, list(h.sites)[:2], [w for w, _ in h.top_words[:3]])
# 117 684 ['Knossos'] ['ku-ta-to', 'ru-ki-to', 'pa-i-to']
# 1   227 ['Pylos']   ['pe-mo', 'e-ke', 'pa-ro']
# 103 212 ['Knossos'] ['ko-wo', 'ko-wa', 'o-pi']

[r.item for r in hand_keyness(d, "117")[:6]]
# ['ku-ta-to', 'ru-ki-to', 'ra-to', 'u-ta-jo-jo', 'u-ta-jo', 'pa-i-to']
```

```bash
aegean analyze hands damos --min-docs 50 --top 5
# hand  tablets  tokens  top words
# 117   684      5152    ku-ta-to, ru-ki-to, pa-i-to, da-wo, e-ko-so
# 1     227      6068    pe-mo, e-ke, pa-ro, ko-to-na, o-na-to
# 103   212      2741    ko-wo, ko-wa, o-pi, tu-na-no, pa-we-a
# ...

aegean analyze hands damos --hand 117          # keyness for one hand (--signs for signs)
```

Compute per-hand dispersion on a filtered slice:
`dispersion(d.filter(scribe="117"), "ku-ta-to")`.

## Corpus profiling: document types, dossiers, metrology

**Document types** summarizes support counts and token shape
(`DocumentTypeProfile(type, count, share_pct, words_per_doc, numerals_pct,
top_sites)`):

```python
from aegean.analysis import document_type_profile
[(p.type, p.count, round(p.share_pct, 1)) for p in document_type_profile(c)[:5]]
# [('Nodule', 886, 51.5), ('Tablet', 393, 22.8), ('Roundel', 151, 8.8),
#  ('Stone vessel', 107, 6.2), ('Clay vessel', 76, 4.4)]
```

**Account dossiers** aggregates every entry headed by a given lexical word, its
values, commodities, sites, and co-listed words (`Dossier(word, entries,
entry_count, tablet_count, total_value, commodities, sites, co_listed)`):

```python
from aegean.analysis import account_dossiers
doss = account_dossiers(c)
len(doss)                                                    # 448
[(x.word, x.tablet_count, x.total_value) for x in doss[:3]]
# [('SA-RA₂', 15, 1354.75), ('KU-PA₃-NU', 7, 118.0), ('DA-RE', 6, 97.5)]
```

**Metrology profile** summarizes integer numerals, fractions, and per-commodity
entries (`MetrologyProfile(fraction_rows, commodity_profiles, numeral_tokens,
fraction_tokens, integer_tokens, distinct_fraction_values)`):

```python
from aegean.analysis import metrology_profile
mp = metrology_profile(c)
mp.numeral_tokens, mp.fraction_tokens, mp.distinct_fraction_values    # (1621, 324, 11)
[(r.display, r.count) for r in mp.fraction_rows[:5]]
# [('1/2', 121), ('1/4', 57), ('1/6', 28), ('3/4', 27), ('1/16', 26)]
[(cm.head, cm.gloss, cm.entries) for cm in mp.commodity_profiles[:3]]
# [('OLE', 'olive oil', 106), ('GRA', 'grain / wheat', 86), ('CYP', 'cyperus (sedge / spice)', 61)]
```

## Commodity and ideogram line statistics

Line-level association and exclusivity over accounting tablet lines
(`account_lines(doc)`):

```python
from aegean.analysis import account_lines, line_cooccurrence_pmi, ideogram_group_exclusivity
lines = [ln for doc in c.documents for ln in account_lines(doc)]

line_cooccurrence_pmi(lines, "GRA", min_joint=2)[:3]
# [('I-QA-*118', 5.168), ('DA-ME', 4.168), ('KU-PA', 4.168)]

# ExclusivityRow(group, gloss, word, count, word_total, exclusivity)
ex = ideogram_group_exclusivity(lines)
[(r.group, r.word, round(r.exclusivity, 2)) for r in ex[:3]]
# [('GRA', 'DA-ME', 1.0), ('GRA', 'I-QA-*118', 1.0), ('GRA', 'KU-NI-SU', 1.0)]
```

## Accounting reconciliation (`KU-RO` / `TO-SO` balance)

`balance_check` compares a tablet's stated total (`KU-RO`, `KU-RA`,
`PO-TO-KU-RO`, `TO-SO`, `TO-SA`, `TO-SO-DE`) against the sum of preceding line
items, returning one `BalanceCheck(stated_total, computed_sum, item_count,
difference, balances, marker, total_line_index, exact_difference)` per total
line plus an `exact_balances` property. `checkable_accounts` filters for intact
tablets with at least one qualifying total.

```python
from aegean.analysis import balance_check, checkable_accounts
balance_check(c.get("HT13"))
# [BalanceCheck(stated_total=130.5, computed_sum=131.0, item_count=6,
#               difference=0.5, balances=False, marker='KU-RO', total_line_index=7,
#               exact_difference=Fraction(1, 2))]
[d.id for d in checkable_accounts(c)[:5]]
# ['HT9a', 'HT9b', 'HT11b', 'HT13', 'HT89']
```

```bash
aegean balance lineara
# doc    marker  stated  computed  diff    balances  eligible (tolerance)
# HT9a   KU-RO   31.75   31.0      -0.75   NO        yes
# HT9b   KU-RO   24.0    24.0      0.0     yes       yes
# HT11a  KU-RO   10.0    6.0       -4.0    NO        NO
# HT11b  KU-RO   180.0   180.0     0.0     yes       yes
# HT13   KU-RO   130.5   131.0     0.5     NO        yes
# ...
```

`balance_check(..., exact=True)` and `aegean balance --exact` compare exact
rational written quantities; the default `balances` uses a `1e-6` float cutoff.
Eligibility (`checkable_accounts`) requires intact text and at least one total
within `max(1, tolerance * abs(stated_total))` (default `tolerance=0.10`; pass
`exact=True` for exact eligibility). CLI JSON includes `exact_difference`,
`exact_balances`, `within_tolerance`, and the active eligibility policy. Because
section splitting on undeciphered tablets is heuristic, a non-zero difference
can reflect line damage or mis-segmentation.

## Sign-pattern search

Wildcard matching over hyphenated sign sequences (`*` = one sign, `**` = zero or
more signs; syntax summary in `SIGN_PATTERN_HELP`):

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

`corpus.query(filters, output=...)` and `run_query(corpus, filters)` combine
inscription- and word-level predicates with `and`, `or`, and negation. With
`output="words"`, the default `count_unit="document"` counts distinct
inscriptions containing each word; pass `count_unit="token"` for token
frequency. Passing `view` or `statuses` applies the same lexical population
rules as `corpus.word_frequencies()`; omitting `view` keeps legacy
case-insensitive matching and distinct surface keys. `result.metadata` records
the comparison policy, denominator, and exclusions.

```python
from aegean.analysis import FilterRow, run_query, summarize_filters
filters = [
    FilterRow("id-contains", "HT"),
    FilterRow("word-suffix", "RO", connector="and"),
]
res = run_query(c, filters, output="inscriptions")
summarize_filters(filters)             # 'Inscription ID contains: HT · Word ends with: RO'
len(res.inscriptions)                  # 49
[d.id for d in res.inscriptions][:5]   # ['HT1', 'HT9a', 'HT9b', 'HT11a', 'HT11b']

run_query(c, [FilterRow("word-sign-pattern", "KU-*-RO")], output="words").words
# [('KU-MA-RO', 1)]
run_query(c, [FilterRow("word-sign-pattern", "KU-RO")],
          output="words", count_unit="token").words
# [('KU-RO', 37)]
```

```bash
aegean query lineara --where id-contains=HT --where word-suffix=RO --limit 5
# id     site           words
# HT1    Haghia Triada  6
# HT9a   Haghia Triada  9
# ...
# Prefix a field with ! to negate or or: to OR; --output-kind words for word counts
aegean query lineara --fields
# Optional lexical controls: --view surface|normalized|lemma,
# --count-unit document|token, --statuses certain,uncertain,...
```

Field registry (`FIELDS`):

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

`FilterRow(field, value, connector="and"|"or", negate=False)` defines one
predicate; `summarize_filters(...)` formats a single-line summary.

## Visualization (`aegean.viz`, the `[viz]` extra)

Matplotlib helpers (`pip install 'pyaegean[viz]'`, imported lazily) return a
matplotlib `Axes` object (compose with `ax=`, save via `.figure.savefig(...)`):

```python
import aegean
from aegean import viz

c = aegean.load("damos")
viz.plot_sign_frequencies(c, top=20)
viz.plot_dispersion(c)
viz.plot_keyness(c.filter(site="Pylos"),
                 [d for d in c.documents if d.meta.site != "Pylos"])
viz.plot_collocation_network(aegean.load("lineara"), "KU-RO")
viz.plot_balance(aegean.load("lineara"))
viz.plot_scansion("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")

la = aegean.load("lineara")
viz.plot_findspots(la)                            # uses bundled gazetteer; no [geo] needed
viz.plot_timeline(la, bin_width=100)              # documents per century from meta.period
viz.plot_sign_network(la, scope="document")       # sign/word co-occurrence graph
```

`plot_scansion` renders syllable quantities (`— ˘ ×`), foot boundaries, and the
caesura (`‖`). `plot_balance` plots stated totals against computed sums on the
diagonal. `plot_findspots` reads the bundled gazetteer directly without `[geo]`.
`plot_timeline` reports on the figure the share of documents whose dates could
not be parsed.

CLI equivalent:
`aegean plot freq|dispersion|keyness|network|balance|scansion|findspots|timeline|signnet ... -o out.png`
(`viz.plot_correspondence_analysis` is Python-only).

## Caching expensive analyses (opt-in)

`aegean.cache` is an off-by-default persistent SQLite cache (`sqlite3` +
typed JSON codec `AEGEAN-CACHE-V2`, zero external dependencies) keyed on input
content fingerprints. When disabled, calls pass straight through.

```python
import aegean

aegean.cache.enable()                              # or set PYAEGEAN_ANALYSIS_CACHE=1
aegean.cache.stats()                               # {'enabled': True, 'path': ..., 'entries': 0}
aegean.analysis.find_morphological_clusters(
    aegean.load("lineara").word_frequencies())
aegean.cache.stats()                               # {'enabled': True, 'entries': 1, 'path': ...}
aegean.cache.clear()                               # resets entries to 0
```

Cache keys embed format and per-function versions so upgrades invalidate stale
entries automatically, and corrupt or schema-changed entries recompute as misses
without executing code. CLI inspection: `aegean cache` and
`aegean cache --clear`.

`Corpus.fingerprint()` computes the underlying SHA-256 content hash:

```python
aegean.load("lineara").fingerprint()[:16]          # 'f2619ca5089e533a'
```

## SQLite persistence and full-text search (`aegean.db`)

`aegean.db` persists any corpus losslessly to a stdlib `sqlite3` database with
FTS5 search. Overwrites run in a single SQLite transaction; WAL readers keep
their previous snapshot until their transaction completes, and failed writes
leave the prior database intact.

```python
from aegean import db, Corpus

db.to_sqlite(c, "corpus.db")                # documents + tokens + FTS5 index
again = Corpus.from_sql("corpus.db")        # len(again) == 1721
db.search("corpus.db", "KU-RO")             # whole-token search → 37 hits; first ('HT9a', 25, 'KU-RO')
# db.search("corpus.db", "KU-RO", mode="substring") -> 39 hits (includes PO-TO-KU-RO)
db.build_lexical_index("corpus.db")         # optional index for fast exact surface/normalized/lemma search
for doc in db.stream("corpus.db"):          # iterate without loading full corpus into RAM
    ...
```

For large Greek SQLite corpora,
`db.annotate_sqlite_job("corpus.db", "annotated.db", job_dir="./job-state")`
annotates one document per transaction with lease protection and resumable
checkpoints (`db.job_status("./job-state")`, CLI `aegean db annotate` and
`aegean db job-status`).

`Corpus.to_sql` and `Corpus.from_sql` wrap these calls. CLI commands:

```bash
aegean db build lineara -o la.db            # --no-fts skips FTS5
aegean db index la.db                       # optional lexical index
aegean db search la.db KU-RO --limit 3
# doc    pos  text
# HT9a   25   KU-RO
# HT9b   20   KU-RO
# HT11a  7    KU-RO
```

---

## Limitations

- **Undeciphered scripts.** Methods over Linear A and Cypro-Minoan rank patterns
  and candidates; cross-script and Linear A/B divergence methods assume
  conventional sign values as their working input.
- **Small and fragmentary corpora.** Read G² and p-values together with
  log-ratio, dispersion, and raw counts (`chao1` estimates ≈ 3,831 unseen word
  types in the bundled Linear A corpus).
- **Heuristic accounting.** Section boundaries on administrative tablets are
  inferred, so arithmetic discrepancies can stem from damage or layout.

See [Limitations](Limitations), [Greek NLP](Greek-NLP), [Meters](Meters),
[Linear A](Linear-A), [CLI](CLI), and [Getting Started](Getting-Started).
