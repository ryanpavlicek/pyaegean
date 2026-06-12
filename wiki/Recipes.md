# Recipes

End-to-end scholarly workflows — each one goes from a question to a citable
result, in Python and (where natural) from the [command line](CLI). Every
Python snippet on this page has been run against the shipped corpora; outputs
shown are real. The thread running through all of them: **finish with `cite()`**,
so the exact data you used is in your paper's references.

## 1 · Reconcile the accounting of a whole corpus, export the discrepancies

*Do the stated totals (KU-RO) on the Haghia Triada tablets match the sums of
their entries?* Reconcile every account, keep the failures, and cite the exact
subset:

```python
import json
import aegean
from aegean.analysis import balance_check

ht = aegean.load("lineara").filter(site="Haghia Triada")
discrepancies = []
for doc in ht:
    for chk in balance_check(doc):
        if not chk.balances:
            discrepancies.append({"doc": doc.id, "marker": chk.marker,
                                  "stated": chk.stated_total, "computed": chk.computed_sum})

with open("discrepancies.json", "w", encoding="utf-8") as f:
    json.dump(discrepancies, f, ensure_ascii=False, indent=2)

print(len(discrepancies), "discrepancies")   # 29
print(ht.cite())                             # GORILA … [subset: filter(site='Haghia Triada') …]
```

```bash
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json
aegean plot balance lineara -o balance.png      # the same picture: stated vs computed
```

The reconciliation is heuristic (section boundaries are inferred) — a
discrepancy is a lead to inspect, not a verdict. See
[Linear A → Accounting](Linear-A).

## 2 · Map a word's distribution

*Where does KU-RO occur?* Count attestations by find-site, then place them —
every aligned site carries a [Pleiades](https://pleiades.stoa.org/) id:

```python
from collections import Counter
import aegean
from aegean import geo

corpus = aegean.load("lineara")
sites = Counter(d.meta.site for d in corpus
                if any(t.text == "KU-RO" for t in d.words))
print(sites.most_common(3))   # [('Haghia Triada', 32), ('Phaistos', 1), ('Zakros', 1)]

coord = geo.site_coordinates()["Haghia Triada"]
print(coord.lat, coord.lon, coord.pleiades_uri)
# 35.06 24.79 https://pleiades.stoa.org/places/589672
```

With the `[geo]` extra (`pip install "pyaegean[geo]"`), `geo.word_distribution(corpus,
"KU-RO")` returns the same thing as a GeoDataFrame (EPSG:4326) ready for any
mapping stack, and `aegean geo lineara --output sites.geojson` writes GeoJSON
from the shell. See [Geography](Geography).

## 3 · Lemmatize and cite a chapter

*Lemmatize a passage of the Iliad and cite the edition.* `load_work` fetches the
complete work (commit-pinned, cached after the first fetch), `pipeline` runs the
whole stack per token:

```python
import aegean

iliad = aegean.greek.load_work("tlg0012.tlg001")     # the Iliad, Perseus edition
doc = iliad.documents[0]                              # Book 1
text = " ".join(t.text for t in doc.tokens[:40])

for r in aegean.greek.pipeline(text)[:3]:
    print(r.text, "→", r.lemma)
# μῆνιν → μῆνις · ἄειδε → ἀείδω · θεὰ → θεά

print(iliad.cite())
# Homer. Ἰλιάς. Digitized by the Perseus Digital Library / Open Greek and Latin. — …
```

```bash
aegean greek work tlg0012.tlg001 -o iliad.json       # the work as a corpus file
aegean greek pipeline "μῆνιν ἄειδε θεά" --json       # per-token records
```

The offline pipeline is the honest baseline; activate `--treebank` or
`--neural` (the `[neural]` extra) for attested-gold or state-of-the-art lemmas —
see [Greek NLP](Greek-NLP) for the measured accuracy of each tier.

## 4 · What vocabulary distinguishes a site? (keyness)

*What makes the Pylos tablets different from the rest of the Mycenaean corpus?*
Load the full Linear B corpus (DAMOS, ~5,900 tablets, fetched ~2 MB), split
Pylos against everything else, and ask:

```python
import aegean
from aegean.analysis import keyness

damos = aegean.load("damos")
pylos = damos.filter(site="Pylos")
rest = [d for d in damos.documents if d.meta.site != "Pylos"]

for r in keyness(pylos, rest)[:3]:
    print(f"{r.item:10} G²={r.log_likelihood:.0f}  log-ratio={r.log_ratio:+.1f}")
# pe-mo      G²=254  log-ratio=+8.5     ('seed' — the land-tenure series)
# o-na-to    G²=226  log-ratio=+8.4     ('lease plot')
# to-so-de   G²=210  log-ratio=+8.3

print(pylos.cite())   # Aurora (2015), DAMOS … [subset: filter(site='Pylos') …]
```

```bash
aegean keyness damos --site Pylos --top 10
aegean plot keyness damos --site Pylos -o pylos.png
```

The textbook Ventris & Chadwick land-tenure result surfaces immediately. Read
G² (significance) together with the log-ratio (effect size) and
`aegean dispersion` — see [Analysis → Corpus statistics](Analysis).

The same split works **by scribal hand** (v2 of the corpus carries the
DAMOS-curated hand on `meta.scribe` — 3,945 documents have one): *what does the
most prolific Knossos scribe write about?*

```python
h117 = damos.filter(scribe="117")            # Hand 117: 684 tablets
rest117 = [d for d in damos.documents if d.meta.scribe != "117"]
keyness(h117, rest117)[:5]                   # the hand's characteristic vocabulary
```

```bash
aegean keyness damos --scribe 117 --top 10
```

## 5 · Sound-match a syllabic word against Greek

*Which Greek word does Linear B `qa-si-re-u` sound like?* Cross-script
comparison romanizes both sides to one phoneme alphabet and ranks by weighted
distance:

```python
from aegean.analysis import nearest, phonetic_compare

cmp = phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek")
print(round(cmp.similarity, 2))                    # 0.69
print([(c.a, c.b, c.op) for c in cmp.alignment][0])  # ('q', 'b', 'sub-far') — the qʷ→b reflex

candidates = ["ποιμήν", "βασιλεύς", "πατήρ", "θεός", "δοῦλος"]
print(nearest("qa-si-re-u", "linearb", candidates, "greek", top=2, fold_aspiration=True))
# [('βασιλεύς', 0.31), ('πατήρ', 0.61)] — the true cognate first, by a clear margin
```

```bash
aegean analyze compare qa-si-re-u βασιλεύς
aegean analyze nearest po-me greek --top 5
```

The **ranking** is the signal — defective syllabic spelling inflates absolute
distances (see the caution in [Analysis → Cross-script comparison](Analysis)).
The candidate list matters: rank against a lexicon or wordlist relevant to your
question, not just whatever corpus is at hand.

## 6 · Mine word-families from an undeciphered corpus (and cache it)

*Which Linear A words share a stem with a productive suffix?* Morphological
clustering is exploratory (no known grammar) but a strong lead-generator — and
the slowest analysis here, so switch on the opt-in cache if you'll rerun it:

```python
import aegean
from aegean.analysis import find_morphological_clusters

aegean.cache.enable()      # optional; or PYAEGEAN_ANALYSIS_CACHE=1

clusters = find_morphological_clusters(aegean.load("lineara").word_frequencies())
print(len(clusters), "clusters")          # 81
print(clusters[0].stem, "→", [m.word for m in clusters[0].members[:4]])
```

```bash
aegean analyze clusters lineara --top 10
aegean cache                              # see what's cached; --clear to wipe
```

## 7 · Ask a grounded question — and audit the answer

*(Key-gated: needs a provider extra, e.g. `pip install "pyaegean[anthropic]"`,
and its API key.)* Ground the model in corpus facts, then **audit** what it was
given with the provenance trace:

```python
import aegean
from aegean import ai

corpus = aegean.load("lineara")
grounding = ai.corpus_context(corpus, limit=10) + ai.cooccurrence_evidence(corpus, "KU-RO")

r = ai.ask("What can be said about the function of KU-RO?", grounding=grounding)
print(r.labeled())     # [EXPLORATORY · ask · …] — the unmissable tag
print(r.trace())       # every corpus/analysis fact the answer rested on, by source
```

```bash
aegean ai ask "What is KU-RO?" --corpus lineara --trace
aegean ai eval                  # grounding-fidelity scores for your provider
```

Every generative result is a labeled hypothesis, never a reading — see
[AI Layer](AI-Layer) and, if you can judge the answer, the
[validation issue form](https://github.com/ryanpavlicek/pyaegean/issues/new/choose).
