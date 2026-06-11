# Linear A

Linear A is fully wired as a [script plugin](Architecture). The bundled corpus is
**1,721 inscriptions** with the full Unicode Linear A sign repertoire — **344
signs**, of which **84** carry the conventional sound values Linear A shares with
the deciphered Linear B (the rest have no agreed reading).

> **Exploratory material.** Linear A is **undeciphered**: the phonetic
> transcription uses Linear B sound values as a working convention, and every
> analytical method here surfaces *evidence to weigh*, never readings or
> translations. See [Analysis](Analysis) for the methods and the
> **[Limitations](Limitations)** page for the full picture.
>
> The bundled corpus is a **normalized** transcription, but the apparatus it
> *does* carry is now interpreted: the upstream's erased-sign marks load as
> `ReadingStatus.LOST` (552 tokens), damaged-at-break words and bracketed
> uncertain readings as `UNCLEAR` (120 tokens) — 366 of the 1,721 documents
> carry editorial status. The **full** Leiden apparatus (restorations, dotted
> readings) is still absent — the upstream digitization dropped it — so for
> edition-grade work consult **GORILA** and **SigLA** (see below). The EpiDoc
> reader/writer round-trip status as `<unclear>`/`<supplied>`/`<gap>`.

## The SigLA corpus (opt-in, fetched)

A second, independent Linear A corpus: **SigLA**, the paleographical database of
Salgarella & Castellan (dataset published **CC BY-NC-SA 4.0**; its paper invites
use outside the interface). pyaegean hosts the decoded dataset as a sha256-pinned
release asset and loads it on demand — the NonCommercial obligation passes to
you, and nothing ships in the wheel:

```python
sigla = aegean.load("sigla")        # ~1 MB fetch on first use, then cached
len(sigla)                          # 781 documents
doc = sigla.get("HT 13")
doc.meta.name                       # 'HT 13 (6.1×10.5×0.8 cm)' — physical dimensions!
" ".join(t.text for t in doc.tokens)
# 'KA U DE TA *164 TE RE ZA *707 TE TU TE KI … KU RO *707'
```

What it adds over the bundled corpus: document **typology**, find-site,
**physical dimensions**, period, and EFA plate references — and a fully
independent reading of each tablet, useful for cross-checking (the two corpora
agree on 84% of shared documents at ≥60% sign overlap once notation differences
like `*120`↔`GRA` are normalized; the rest is genuine scholarly variation).
**Granularity caveat:** this is a *sign-level* corpus — one token per sign
attestation, in tablet order, with no word boundaries — so word-level analyses
belong on the bundled corpus. Cite SigLA in academic work
([Limitations](Limitations) · [Data & Provenance](Data-and-Provenance)).

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
