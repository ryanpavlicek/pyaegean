# Linear A

Linear A is fully wired as a [script plugin](Architecture). The bundled corpus is
**1,721 inscriptions** with the full Unicode Linear A sign repertoire — **344
signs**, of which **84** carry the conventional sound values Linear A shares with
the deciphered Linear B (the rest have no agreed reading).

> Linear A is **undeciphered**. The phonetic transcription uses Linear B sound
> values as a working convention, and every analytical method here is
> **exploratory** — evidence to weigh, not translation. See [Analysis](Analysis).
>
> The bundled corpus is a **normalized** transcription: it does not carry the
> full Leiden apparatus (lacunae, restorations, uncertain readings). For
> edition-grade work consult **GORILA** and **SigLA**. The data model can still
> record editorial status via `aegean.ReadingStatus` (CERTAIN / UNCLEAR /
> RESTORED / LOST), and the EpiDoc reader/writer preserve it
> (`<unclear>`/`<supplied>`/`<gap>`) for bring-your-own corpora.

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

The `to_dataframe()` views need pandas, which ships as the optional `[data]`
extra (`pip install 'pyaegean[data]'`); everything else here runs on the
dependency-free core.

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
len(inv)                           # 344 — the full Unicode Linear A repertoire
[s for s in inv if s.phonetic]     # the 84 signs with assigned sound values
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
heuristic and the metrology is contested. Only about **40** of the 1,721 tablets
(precisely 39) carry a stated `KU-RO` total and are checkable at all; most are
too fragmentary — the nature of the corpus, not a tool limit.

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
