# Linear A

Linear A is fully wired as a [script plugin](Architecture). The bundled corpus is
**1,721 inscriptions** with an **84-sign inventory** and a sign→sound map (the
syllabic values Linear A shares with the deciphered Linear B).

> Linear A is **undeciphered**. The phonetic transcription uses Linear B sound
> values as a working convention, and every analytical method here is
> **exploratory** — evidence to weigh, not translation. See [Analysis](Analysis).

## Loading & filtering

```python
import aegean

corpus = aegean.load("lineara")
len(corpus)                       # 1721

doc = corpus.get("HT13")                    # one Document by id
ht = corpus.filter(site="Haghia Triada")    # AND-combine any DocumentMeta fields
ht_lmib = corpus.filter(site="Haghia Triada", period="LMIB")  # period codes are un-spaced (LMIA/LMIB/MMII…)
```

`meta.site` holds the **full site name** (`"Haghia Triada"`, `"Khania"`, …); the
familiar two-letter site codes (`HT`, `ZA`, `KH`) are the prefix of each
document's `id`. To select "all HT tablets", query the id (see the
[query engine](Analysis#query-engine)):

```python
from aegean.analysis import FilterRow, run_query
res = run_query(corpus, [FilterRow("id-contains", "HT")], output="inscriptions")
len(res.inscriptions)
```

## Words, tokens, DataFrames

```python
corpus.word_frequencies()[:5]     # [(word, count), ...] desc by count

corpus.to_dataframe()                      # one row per document
corpus.to_dataframe(level="word")          # one row per WORD token
corpus.to_dataframe(level="token")         # every token (words, numerals, …)
```

A document's tokens carry their role:

```python
doc = corpus.get("HT13")
[t.text for t in doc.words]        # multi-sign lexical words
[t.text for t in doc.numerals]     # numerals / metrological fractions
[t.text for t in doc.logograms]    # commodity / ideogram signs
doc.line_tokens                    # tokens regrouped by physical line
```

## The sign inventory

```python
inv = aegean.get_script("lineara").sign_inventory
len(inv)                           # 84
sign = inv.by_label("KU")
sign.phonetic                      # 'ku'
inv.to_dataframe()                 # pandas view of the inventory
```

## Transliteration (sign → sound)

```python
from aegean.scripts.lineara.phonetic import word_to_phonetic
word_to_phonetic("KU-RO")          # 'kuro'
word_to_phonetic("PA-I-TO")        # 'paito'
word_to_phonetic("KU-RO", {"KU": "gu"})   # 'guro'  (hypothesis override)
```

## Accounting reconciliation (KU-RO / PO-TO-KU-RO)

`KU-RO` ("total") and `PO-TO-KU-RO` ("grand total") let you check a tablet's
arithmetic against its line items. **Exploratory**: section boundaries are
heuristic and the metrology is contested.

```python
from aegean.analysis import balance_check
for chk in balance_check(corpus.get("HT13")):
    print(chk)        # each total line vs the summed items it governs
```

## Sign-pattern search

Dash-separated sign labels with wildcards: `*` = exactly one sign, `**` = zero
or more. Case-insensitive after subscript folding (`RA₂` ≡ `RA2`).

```python
from aegean.analysis import word_matches_sign_pattern
word_matches_sign_pattern("KU-NE-RO", "KU-*-RO")    # True
word_matches_sign_pattern("KU-RO", "KU-*-RO")        # False
[w for w, _ in corpus.word_frequencies()
 if word_matches_sign_pattern(w, "KU-*-RO")]
```

## More

The full analytical toolkit — phonetic distance, alignment, morphology
clustering, collocation statistics, the query engine, and tablet-structure
classification — is on the [Analysis](Analysis) page.

## Provenance

```python
print(corpus.provenance.cite())
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```
