# Linear A

Linear A is the script of Bronze-Age Crete, **still undeciphered**. pyaegean ships
the whole corpus offline and gives you tools to *explore* it: load and filter
1,721 inscriptions, look up signs, search for words by their sign shape (with
wildcards), check the accounting tablets' arithmetic, and sort tablets by what
they look like they're for. You'd reach for this page to answer questions like
"which words end in **-RO**?", "does this tablet's **KU-RO** total actually add
up?", or "what does sign **KU** look like?", all without writing much Python,
and with a matching command line for every method.

> **Read this first: it's exploratory material.** Linear A is undeciphered. The
> phonetic transcription here uses **Linear B sound values** as a working
> convention (the two scripts share many signs), and every method on this page
> surfaces *evidence to weigh*, never readings or translations. Numbers, totals,
> and structure labels are heuristics on a damaged, contested corpus. See the
> **[Limitations](Limitations)** page for the honest, full picture, and
> [Analysis](Analysis) for the methods in depth.

Everything below runs on the **dependency-free core** unless a step is explicitly
marked as needing the `[data]` extra (pandas) or a one-time fetch (SigLA).

---

## At a glance

What the bundled corpus contains. The first four counts plus source and license
come straight from `aegean info lineara`; the sound-value, shared-with-Linear-B,
editorial-status, and checkable-`KU-RO` rows are from the Python introspection
shown later on this page:

| Quantity | Value |
| --- | --- |
| Inscriptions (documents) | **1,721** |
| Word tokens (all multi-sign; 995 distinct) | **1,381** |
| Tokens (words, numerals, logograms, separators) | **6,406** |
| Signs in the inventory | **344** (the full Unicode Linear A block) |
| Signs with an assigned sound value | **47** |
| Signs marked shared with Linear B | **67** |
| Documents carrying editorial status | **366** (552 `LOST` + 120 `UNCLEAR` tokens) |
| Tablets with a checkable `KU-RO` total | **35** (39 total lines) |
| Source | GORILA (Godart & Olivier 1976–1985) via `mwenge/lineara.xyz` |
| License | Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed |

```bash
aegean info lineara
# documents          1721
# words              1381
# tokens             6406
# signs_in_inventory 344
# source             GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz
# license            Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed
```

---

## Loading the corpus

The corpus is bundled in the wheel: no download, works offline.

```python
import aegean

corpus = aegean.load("lineara")
len(corpus)                       # 1721

doc = corpus.get("HT13")          # one Document by id (note: no space — "HT13")
```

There is no separate CLI "load the corpus" step: every `aegean` command takes
the corpus id (`lineara`) as its first argument and loads it for you.

### Filtering by metadata

`corpus.filter(...)` AND-combines any [`DocumentMeta`](Architecture) fields. The
period codes are written **un-spaced** (`LMIA`, `LMIB`, `MMII`, …), and
`meta.site` holds the **full** site name:

```python
ht = corpus.filter(site="Haghia Triada")
len(ht)                                       # 1110

ht_lmib = corpus.filter(site="Haghia Triada", period="LMIB")
len(ht_lmib)                                  # 1110
```

The same on the command line, which also lists the matches:

```bash
aegean load lineara --site "Haghia Triada" --period LMIB --limit 5
```

| Filter field | `corpus.filter(...)` keyword | `aegean load` flag |
| --- | --- | --- |
| Find-site (full name) | `site=` | `--site` |
| Period / context code | `period=` | `--period` |
| Scribal hand | `scribe=` | `--scribe` |
| Support (object type) | `support=` | `--support` |
| (export the filtered set) |— | `--output / -o FILE.json` |
| (rows shown) |— | `--limit N` (default 20) |

> **Site codes vs. site names.** `meta.site` is the full name (`"Haghia
> Triada"`, `"Khania"`, …). The familiar two-letter codes (`HT`, `ZA`, `KH`)
> are the prefix of each document's **id**, not a metadata field. To select "all
> HT tablets," query the id with the [query engine](Analysis#query-engine):

```python
from aegean.analysis import FilterRow, run_query
res = run_query(corpus, [FilterRow("id-contains", "HT")], output="inscriptions")
len(res.inscriptions)                         # 1110
```

```bash
aegean query lineara --where id-contains=HT
```

### Looking at one document

```bash
aegean show lineara HT13
# HT13  site=Haghia Triada  period=LMIB  scribe=HT Scribe 8  support=Tablet
#   1: KA-U-DE-TA VIN 𐄁 TE 𐄁
#   2: RE-ZA 5 ¹⁄₂
#   3: TE-TU 56
#   4: TE-KI 27 ¹⁄₂
#   5: KU-ZU-NI 18
#   6: DA-SI-*118 19
#   7: I-DU-NE-SI 5
#   8: KU-RO 130 ¹⁄₂
```

Every token carries its **role**, so you can pull just words, numerals, or
commodity signs:

```python
doc = corpus.get("HT13")
[t.text for t in doc.words]
# ['KA-U-DE-TA', 'RE-ZA', 'TE-TU', 'TE-KI', 'KU-ZU-NI', 'DA-SI-*118', 'I-DU-NE-SI', 'KU-RO']
[t.text for t in doc.numerals]
# ['5', '¹⁄₂', '56', '27', '¹⁄₂', '18', '19', '5', '130', '¹⁄₂']
[t.text for t in doc.logograms]
# ['VIN', 'TE']
doc.line_tokens                    # tokens regrouped by physical line
```

### Words, frequencies, DataFrames

```python
corpus.word_frequencies()[:5]
# [('KU-RO', 37), ('SA-RA₂', 20), ('KI-RO', 16), ('*411-VS', 15), ('A-TA-I-*301-WA-JA', 11)]
```

The DataFrame views need pandas, shipped as the optional `[data]` extra
(`pip install 'pyaegean[data]'`); everything else on this page runs on the core.

```python
corpus.to_dataframe()                      # (1721, 10) — one row per document
corpus.to_dataframe(level="word")          # one row per WORD token
corpus.to_dataframe(level="token")         # every token (words, numerals, …)
```

The document-level frame's columns are: `id`, `script_id`, `site`, `support`,
`scribe`, `findspot`, `period`, `name`, `n_tokens`, `n_words`.

---

## The sign inventory

The inventory is the **full Unicode Linear A repertoire**: 344 signs. Of those,
**47** carry an assigned sound value (`phonetic`); the rest are carried from the
Unicode Character Database with `attrs["source"] == "ucd"` and **no** reading,
because Linear A is undeciphered and most of its repertoire has no agreed value.

```python
inv = aegean.get_script("lineara").sign_inventory
len(inv)                           # 344
len([s for s in inv if s.phonetic])               # 47  — the read signs
len([s for s in inv if s.attrs.get("sharedWithLinearB")])  # 67  — shared glyphs

sign = inv.by_label("KU")
sign.phonetic                      # 'ku'
sign.glyph                         # '𐙂'
sign.codepoint                     # 67138  (the int; the CLI/JSON render it as 'U+10642')

inv.to_dataframe()                 # (344, 10) — needs [data]
```

The inventory DataFrame's columns are: `label`, `glyph`, `codepoint`,
`phonetic`, `sharedWithLinearB`, `linearAOnly`, `total`, `confidence`,
`altGlyphs`, `source`.

Look up a single sign from the shell:

```bash
aegean sign lineara KU
#  label                   KU
#  glyph                   𐙂
#  codepoint               U+10642
#  phonetic                ku
#  attrs.sharedWithLinearB True
#  attrs.linearAOnly       False
#  attrs.total             16
#  attrs.confidence        1
```

```bash
aegean sign lineara KU --json
# {"label": "KU", "glyph": "𐙂", "codepoint": "U+10642", "phonetic": "ku",
#  "attrs": {"sharedWithLinearB": true, "linearAOnly": false,
#            "total": 16, "confidence": 1, "altGlyphs": []}}
```

The `sign` argument accepts either a label (`KU`, `*301`) or a single glyph
character. The `attrs.confidence` field rates how secure the empirical
sign→sound alignment is: treat it as evidence, not canon.

### Transliteration (sign → sound)

The Linear-B-value convention, with an optional hypothesis override so you can
test "what if `KU` were really `gu`?":

```python
from aegean.scripts.lineara.phonetic import word_to_phonetic
word_to_phonetic("KU-RO")                 # 'kuro'
word_to_phonetic("PA-I-TO")               # 'paito'
word_to_phonetic("KU-RO", {"KU": "gu"})   # 'guro'  (hypothesis override)
```

---

## Sign-pattern search (the `*` wildcard)

This is the workhorse for "find every word shaped like X." A pattern is a
**dash-separated list of sign labels** with two wildcards:

| Wildcard | Meaning |
| --- | --- |
| `*` | **exactly one** sign (any value) |
| `**` | **zero or more** signs |
| (a label, e.g. `KU`) | that exact sign |

Matching is case-insensitive after subscript folding, so `RA₂` and `RA2` are the
same sign. The key thing to internalize: **`*` is one whole sign, not one
letter.** `KU-*-RO` means "KU, then any single sign, then RO": a three-sign
word.

```python
from aegean.analysis import word_matches_sign_pattern
word_matches_sign_pattern("KU-NE-RO", "KU-*-RO")   # True  — three signs, middle is anything
word_matches_sign_pattern("KU-RO",    "KU-*-RO")   # False — only two signs, * needs one in between
word_matches_sign_pattern("KU-RO",    "**-RO")     # True  — ** allows zero-or-more before RO
word_matches_sign_pattern("A-TA-I-*301-WA-JA", "A-**-JA")  # True — A … JA, anything between
```

### `*-RO` — words ending in **-RO** (with one sign before)

```bash
aegean search lineara "*-RO"
# '*-RO': 6 word(s)
#  KU-RO    37
#  KI-RO    16
#  *86-RO    4
#  SA-RO     4
#  NU-RO     2
#  RE-RO     1
```

### `KU-*` — words starting with **KU-** (with one sign after)

```bash
aegean search lineara "KU-*"
# 'KU-*': 12 word(s)
#  KU-RO    37
#  KU-PA     4
#  KU-RA     2
#  KU-RE     2
#  KU-*305   1
#  KU-*321   1
#  KU-DA     1   (… KU-KA, KU-NI, KU-PA₃, KU-PI, KU-TA each 1)
```

### `KU-*-RO` — exactly three signs, KU…RO

```bash
aegean search lineara "KU-*-RO"
# 'KU-*-RO': 1 word(s)
#  KU-MA-RO  1
```

The same searches in Python, ranked by frequency:

```python
[(w, n) for w, n in corpus.word_frequencies()
 if word_matches_sign_pattern(w, "**-RO")]
# [('KU-RO', 37), ('KI-RO', 16), ('*86-RO', 4), ('SA-RO', 4), ('KI-DA-RO', 2), ('NU-RO', 2), ...]  — 18 words
```

If you need the compiled form (e.g. to reuse one pattern over many words):

```python
from aegean.analysis import compile_sign_pattern
from aegean.analysis.patterns import match_sign_pattern
pat = compile_sign_pattern("KU-*-RO")
match_sign_pattern(["KU", "MA", "RO"], pat)   # True
```

Sign-pattern search is also one predicate inside the larger
[query engine](Analysis#query-engine) (`word-sign-pattern`), which lets you
combine it with site/period/co-occurrence filters.

> Single-sign words never match a pattern (there's no dash to split), and an
> empty pattern matches nothing.

---

## Accounting reconciliation (KU-RO / PO-TO-KU-RO)

`KU-RO` means "total" and `PO-TO-KU-RO` "grand total." On an accounting tablet
you can check the stated total against the line items above it: a concrete,
falsifiable thing to do with an undeciphered script.

> **Exploratory.** Section boundaries are heuristic and Aegean metrology is
> contested, so a "balance" is evidence, not proof. Only **35** of the 1,721
> tablets carry a `KU-RO` total that's checkable at all (39 total lines, since a
> few tablets state more than one); the rest are too fragmentary: that's the
> nature of the corpus, not a tool limit. Of the 39 checked lines, **8** balance
> exactly.

Check one tablet:

```bash
aegean balance lineara HT13
#  doc   marker  stated  computed  diff  balances
#  HT13  KU-RO   130.5   131.0     0.5   NO
```

The stated total is 130½ but the six items above it sum to 131: off by ½. The
Python form gives you the full record per total line:

```python
from aegean.analysis import balance_check
for chk in balance_check(corpus.get("HT13")):
    print(chk)
# BalanceCheck(stated_total=130.5, computed_sum=131.0, item_count=6,
#              difference=0.5, balances=False, marker='KU-RO', total_line_index=7)
```

`BalanceCheck` fields: `stated_total`, `computed_sum`, `item_count`,
`difference`, `balances`, `marker`, `total_line_index`.

### Sweep the whole corpus

Omit the document id to check every total line at once:

```bash
aegean balance lineara
# lineara: 39 total line(s) checked
#  HT9a   KU-RO   31.75   31.0    -0.75   NO
#  HT9b   KU-RO   24.0    24.0     0.0    yes
#  HT11b  KU-RO   180.0   180.0    0.0    yes
#  HT13   KU-RO   130.5   131.0    0.5    NO
#  HT25b  KU-RO   52.0    52.0     0.0    yes
#  ... (39 lines across 35 documents)
```

Add `--strict` to exit non-zero if any checked total fails to balance: handy in
a script or CI step. `--json` emits the rows as machine-readable JSON.

### Intact, balancing accounts

A stricter filter than "balances": **every** token securely read (no lacuna, no
bracketed restoration) *and* the arithmetic holds within a tolerance. These are
the clean teaching/drill candidates.

```python
from aegean.analysis.accounting import checkable_accounts, is_checkable_account
clean = checkable_accounts(corpus)            # default tolerance 10%
[d.id for d in clean]                          # ['HT9a', 'HT9b', 'HT11b', 'HT13', 'HT89', ...]
is_checkable_account(corpus.get("HT11b"))      # True
```

The default `tolerance=0.10` is lenient on purpose, because Aegean metrology is
imperfectly understood; raise or lower it to taste.

---

## Tablet-structure detection

Sort inscriptions by what their token stream *looks* like: a quick way to find
the accounts, the libation formulas, or the running text. These are
**content-shape heuristics, not genre attributions**; you're expected to
override individual calls.

| Category key | Label | Signal |
| --- | --- | --- |
| `accounting` | Accounting | Has `KU-RO`, or numerals plus several multi-sign words |
| `libation` | Libation | Contains a known libation-formula word |
| `list` | Lists | Many separator marks, no numerals |
| `text` | Text / Other | Extended hyphenated text, no numerals |
| `other` | Unclassified | Short or ambiguous |

The known libation-formula words are `A-TA-I-*301-WA-JA`, `JA-SA-SA-RA-ME`, and
`A-DI-KI-TE-TE-DU`. The precedence is exactly the order above (accounting wins
over libation, etc.).

Census the whole corpus:

```bash
aegean analyze structure lineara
# lineara: structure census (heuristic)
#  accounting   134
#  libation      15
#  list           7
#  text           2
#  other       1563
```

Classify one document:

```bash
aegean analyze structure lineara HT13
# HT13: accounting
```

In Python:

```python
from aegean.analysis.structure import classify_structure, classify_corpus
classify_structure(corpus.get("HT13"))         # 'accounting'
buckets = classify_corpus(corpus)              # {'accounting': [...ids...], 'libation': [...], ...}
len(buckets["accounting"])                      # 134
```

---

## Commodity logograms

The accounting tablets count commodities marked by **ideograms** (grain, oil,
sheep, people …). pyaegean ships a curated catalog of **21** commodity heads with
their standard GORILA/Younger glosses and a broad category, plus helpers to
identify them in a token stream. (The glosses are standard; the *syllabic*
values of the underlying signs are a separate, open question, and the numbered
`*NNN` logograms are genuinely undeciphered as to referent.)

```python
from aegean.scripts.lineara.commodities import COMMODITIES, commodity_head, is_lexical_word
len(COMMODITIES)                  # 21
commodity_head("GRA")             # 'GRA'
commodity_head("OLE+U")           # 'OLE'   — strips the ligature modifier
commodity_head("OVISm")           # 'OVIS'  — strips the sex marker
commodity_head("KU-RO")           # None    — hyphenated → a syllabic word, never a logogram
is_lexical_word("KU-RO")          # True    — a real syllabic word, not a logogram chain
```

The most frequent commodities across the corpus (oil, grain, cyperus, figs,
wine, people):

```python
from collections import Counter
from aegean.scripts.lineara.commodities import commodity_head
counts = Counter(commodity_head(t.text)
                 for d in corpus for t in d.tokens
                 if commodity_head(t.text))
counts.most_common(6)
# [('OLE', 128), ('GRA', 108), ('CYP', 85), ('NI', 76), ('VIN', 62), ('VIR', 48)]
```

| Category | Heads |
| --- | --- |
| agricultural | `GRA`, `HORD`, `OLE`, `OLIV`, `VIN`, `FIC`, `NI`, `CYP`, `AROM`, `GRA_PA` |
| livestock | `OVIS`, `CAP`, `SUS`, `BOS` |
| people | `VIR`, `MUL` |
| material | `TELA`, `LANA`, `AES`, `AUR`, `ARG` |

---

## Editorial status (what's preserved)

The bundled corpus is a **normalized** transcription, but the apparatus it does
carry is interpreted on load. The upstream's erased-sign marks become
`ReadingStatus.LOST` (where the text isn't preserved), and damaged-at-a-break
words plus bracketed uncertain readings become `UNCLEAR`:

```python
from aegean.core.model import ReadingStatus
lost    = sum(1 for d in corpus for t in d.tokens if t.status is ReadingStatus.LOST)
unclear = sum(1 for d in corpus for t in d.tokens if t.status is ReadingStatus.UNCLEAR)
docs    = sum(1 for d in corpus if any(t.status is not ReadingStatus.CERTAIN for t in d.tokens))
lost, unclear, docs            # (552, 120, 366)
```

So **366 of 1,721** documents carry editorial status (552 `LOST` tokens, 120
`UNCLEAR`). The **full** Leiden apparatus (restorations, dotted readings) is
still absent (the upstream digitization dropped it), so for edition-grade work
consult **GORILA** and **SigLA** (below). The EpiDoc reader/writer round-trips
these as `<unclear>` / `<supplied>` / `<gap>`.

---

## The SigLA corpus (opt-in, fetched)

A second, independent Linear A corpus: **SigLA**, the paleographical database of
Salgarella & Castellan (dataset published **CC BY-NC-SA 4.0**; its paper invites
use outside the interface). pyaegean hosts the decoded dataset as a sha256-pinned
release asset and loads it on demand; the NonCommercial obligation passes to
**you**, and nothing ships in the wheel.

```python
sigla = aegean.load("sigla")        # ~1.2 MB fetch on first use, then cached
len(sigla)                          # 781
doc = sigla.get("HT 13")            # note the space — SigLA ids are spaced
doc.meta.name                       # 'HT 13 (6.1×10.5×0.8 cm)'  — physical dimensions!
" ".join(t.text for t in doc.tokens)
# 'KA-U-DE-TA VIN TE RE-ZA TE-TU TE-KI KU-*79-NI DA-SI-*118 I-DU-NE-SI KU-RO'
```

What SigLA adds over the bundled corpus: document **typology**, find-site,
**physical dimensions**, period, EFA plate references, SigLA's own word
division, and a fully independent reading of each tablet (note `KU-*79-NI` where
GORILA reads `KU-ZU-NI`), useful for cross-checking. The two corpora broadly
agree on shared documents once notation differences (like `*120`↔`GRA`) are
normalized; where they diverge it's genuine scholarly variation.

One honest limit: SigLA is a *palaeographic sign* database, so it records sign
occurrences and word division but **not** the cardinal-number quantities of the
accounts; there are **no numeral values** here. Use the bundled GORILA corpus
for accounting. Cite SigLA in academic work.

All the same commands work on it (`aegean info sigla`, `aegean search sigla
"*-RO"`, `aegean stats sigla`, …). See [Data & Provenance](Data-and-Provenance).

---

## Frequencies and the wider toolkit

Word and sign frequency tables straight from the shell:

```bash
aegean stats lineara --top 5
#  KU-RO              37
#  SA-RA₂             20
#  KI-RO              16
#  *411-VS            15
#  A-TA-I-*301-WA-JA  11

aegean stats lineara --signs --top 5
#  𐝫     552   (the erased-sign marker)
#  𐄁     468   (the word divider)
#  1     310
#  KU    307
#  KA    284
```

The full analytical toolkit: phonetic distance and alignment, cross-script
nearest-neighbour, association statistics (χ², log-likelihood, Fisher, PMI),
collocation, morphology clustering, the compound [query engine](Analysis#query-engine),
keyness, and dispersion: is documented on the [Analysis](Analysis) page. The
[Linear B](Linear-B) and [Cypriot](Cypriot) corpora use the same model and the
same commands, and the Greek side lives under [Greek NLP](Greek-NLP) /
[Meters](Meters).

### Command reference (Linear A)

| Command | What it does | Key flags |
| --- | --- | --- |
| `aegean info lineara` | Corpus size, provenance, license | `--json` |
| `aegean load lineara` | Filter by metadata; list or export | `--site --period --scribe --support -o --limit --json` |
| `aegean show lineara HT13` | One document, line by line | `--json` |
| `aegean search lineara "KU-*-RO"` | Wildcard sign-pattern search | `--json` |
| `aegean query lineara` | Compound query engine | `--where --output-kind --fields --limit --json` |
| `aegean stats lineara` | Word / sign frequency table | `--signs --top --json` |
| `aegean sign lineara KU` | Look up one sign | `--json` |
| `aegean balance lineara [HT13]` | KU-RO reconciliation | `--strict --json` |
| `aegean analyze structure lineara [HT13]` | Heuristic categories | `--json` |
| `aegean cite lineara` | Cite the corpus (or a subset) | `--style --site --period --scribe --support` |
| `aegean export lineara` | Export JSON / CSV / Parquet / EpiDoc / SQLite | (see [CLI](CLI)) |

---

## Provenance & citation

```python
print(corpus.provenance.cite())
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```

```bash
aegean cite lineara --style bibtex          # or plain / apa
aegean cite lineara --site "Haghia Triada"  # cite the exact filtered subset
# … [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
```

---

## Honest limitations

- **Undeciphered.** Sound values are a Linear B *convention*; transliterations,
  "totals," structure labels, and commodity glosses are evidence to weigh, never
  ground truth.
- **Damaged corpus.** Only 35 tablets carry a checkable total; section
  boundaries for reconciliation are heuristic; the full Leiden apparatus isn't in
  the bundled data.
- **Heuristic structure.** The accounting/libation/list/text labels are
  content-shape rules, not genre attributions; override them freely.
- **SigLA carries no quantities** and is NonCommercial; the obligation passes to
  you.

The full picture, with citations and caveats, is on the
**[Limitations](Limitations)** page. For the methods behind the numbers, see
[Analysis](Analysis); to get from nothing installed to your first result, see
[Getting Started](Getting-Started).
