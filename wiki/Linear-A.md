# Linear A

Linear A is the undeciphered writing system of Bronze Age Crete. pyaegean ships
the full corpus offline for exploratory work: loading and filtering 1,721
inscriptions, inspecting the 342-sign Unicode inventory, searching words by
wildcard sign patterns, checking accounting tablet arithmetic, and classifying
tablet structures. Every Python method below has a matching CLI command.

> **Transcription convention.** Linear A transliterations use Linear B sound
> values by scholarly convention because the two scripts share many sign forms.
> Numbers, totals, and structure categories are heuristic classifications over a
> damaged corpus. See [Limitations](Limitations) for scope and
> [Analysis](Analysis) for the underlying methods.

All operations below run on the zero-dependency core unless marked as needing
the `[data]` extra (`pandas`) or a one-time fetch (SigLA or the browser
workbench).

---

## Corpus summary

The first four counts, source, and license come from `aegean info lineara`; the
remaining rows come from the Python queries shown below:

| Quantity | Value |
| --- | --- |
| Inscriptions (documents) | **1,721** |
| Word tokens (all multi-sign; 995 distinct) | **1,381** |
| Tokens (words, numerals, logograms, separators) | **6,406** |
| Signs in the inventory | **342** (full Unicode Linear A block) |
| Signs with an assigned sound value | **50** |
| Signs marked shared with Linear B | **81** |
| Documents carrying editorial status | **366** (552 `LOST` + 120 `UNCLEAR` tokens) |
| Tablets with a checkable `KU-RO`/`KU-RA` total | **37** (41 total lines) |
| Source | GORILA (Godart & Olivier 1976–1985) via `mwenge/lineara.xyz` |
| License | Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed |

```bash
aegean info lineara
# documents          1721
# words              1381
# tokens             6406
# signs_in_inventory 342
# source             GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz
# license            Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed
```

---

## Loading the corpus

The corpus ships inside the wheel and loads offline with no network call:

```python
import aegean

corpus = aegean.load("lineara")
len(corpus)                       # 1721

doc = corpus.get("HT13")          # one Document by id (unspaced: "HT13")
```

On the command line, pass `lineara` directly as the corpus argument to any
`aegean` command.

### Filtering by metadata

`corpus.filter(...)` combines [`DocumentMeta`](Architecture) fields with logical
AND. Period codes have no spaces (`LMIA`, `LMIB`, `MMII`), and `meta.site`
stores the full site name:

```python
ht = corpus.filter(site="Haghia Triada")
len(ht)                                       # 1110

ht_lmib = corpus.filter(site="Haghia Triada", period="LMIB")
len(ht_lmib)                                  # 1110
```

CLI equivalent:

```bash
aegean load lineara --site "Haghia Triada" --period LMIB --limit 5
```

| Filter field | `corpus.filter(...)` keyword | `aegean load` flag |
| --- | --- | --- |
| Find-site (full name) | `site=` | `--site` |
| Period / context code | `period=` | `--period` |
| Scribal hand | `scribe=` | `--scribe` |
| Support (object type) | `support=` | `--support` |
| Export filtered subset | — | `--output / -o FILE.json` |
| Rows displayed | — | `--limit N` (default 20) |

> **Site codes vs. site names.** `meta.site` holds the full name (`"Haghia
> Triada"`, `"Khania"`). The two-letter prefixes (`HT`, `ZA`, `KH`) live on the
> document `id`. To match by id prefix, use the
> [query engine](Analysis#query-engine):

```python
from aegean.analysis import FilterRow, run_query
res = run_query(corpus, [FilterRow("id-contains", "HT")], output="inscriptions")
len(res.inscriptions)                         # 1110
```

```bash
aegean query lineara --where id-contains=HT
```

### Inspecting one document

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

Each token carries its `TokenKind`, so words, numerals, and logograms can be
read separately:

```python
doc = corpus.get("HT13")
[t.text for t in doc.words]
# ['KA-U-DE-TA', 'RE-ZA', 'TE-TU', 'TE-KI', 'KU-ZU-NI', 'DA-SI-*118', 'I-DU-NE-SI', 'KU-RO']
[t.text for t in doc.numerals]
# ['5', '¹⁄₂', '56', '27', '¹⁄₂', '18', '19', '5', '130', '¹⁄₂']
[t.text for t in doc.logograms]
# ['VIN', 'TE']
doc.line_tokens                    # tokens grouped by physical line
```

### Words, frequencies, and DataFrames

```python
corpus.word_frequencies()[:5]
# [('KU-RO', 37), ('SA-RA₂', 20), ('KI-RO', 16), ('*411-VS', 15), ('A-TA-I-*301-WA-JA', 11)]
```

DataFrame conversion requires `pandas` via `pip install 'pyaegean[data]'`:

```python
corpus.to_dataframe()                      # (1721, 11) — one row per document
corpus.to_dataframe(level="word")          # (1381, 8) — one row per WORD token
corpus.to_dataframe(level="token")         # (6406, 8) — every token (words, numerals, ...)
```

The document-level frame has columns `id`, `script_id`, `site`, `support`,
`scribe`, `findspot`, `period`, `name`, `n_tokens`, `n_words`, and
`source_text`. Token- and word-level frames carry `doc_id`, `line_no`,
`position`, `text`, `kind`, `status`, `site`, and `period`.

---

## The sign inventory

The inventory contains the full 342-sign Unicode Linear A block. Of these, 97
appear in the corpus-aligned sign table, 50 with a conventional Linear B sound
value (`phonetic`) and 81 marked as shared with Linear B. The remaining 245 come
from the Unicode Character Database with `attrs["source"] == "ucd"` and no sound
value.

```python
inv = aegean.get_script("lineara").sign_inventory
len(inv)                                                   # 342
len([s for s in inv if s.phonetic])                        # 50
len([s for s in inv if s.attrs.get("sharedWithLinearB")])  # 81

sign = inv.by_label("KU")
sign.phonetic                      # 'ku'
sign.glyph                         # '𐙂'
sign.codepoint                     # 67138 (rendered as 'U+10642' by CLI/JSON)

inv.to_dataframe()                 # (342, 10) — requires [data]
```

The inventory DataFrame has columns `label`, `glyph`, `codepoint`, `phonetic`,
`sharedWithLinearB`, `linearAOnly`, `total`, `confidence`, `altGlyphs`, and
`source`.

Single-sign lookup from the CLI accepts a label (`KU`, `*301`) or a single
Unicode glyph:

```bash
aegean sign lineara KU
#  label                   KU
#  glyph                   𐙂
#  codepoint               U+10642
#  phonetic                ku
#  attrs.sharedWithLinearB True
#  attrs.linearAOnly       False
#  attrs.total             29
#  attrs.confidence        1

aegean sign lineara KU --json
# {"label": "KU", "glyph": "𐙂", "codepoint": "U+10642", "phonetic": "ku",
#  "attrs": {"sharedWithLinearB": true, "linearAOnly": false,
#            "total": 29, "confidence": 1, "altGlyphs": []}}
```

`attrs.confidence` rates how established the empirical sign-to-sound alignment
is under the Linear B convention.

### Transliteration (sign → sound)

`word_to_phonetic` applies the conventional Linear B values and accepts an
override dictionary to test alternative sign values:

```python
from aegean.scripts.lineara.phonetic import word_to_phonetic
word_to_phonetic("KU-RO")                 # 'kuro'
word_to_phonetic("PA-I-TO")               # 'paito'
word_to_phonetic("KU-RO", {"KU": "gu"})   # 'guro'
```

---

## Sign-pattern search (the `*` wildcard)

A pattern is a dash-separated list of sign labels with two wildcards:

| Wildcard | Meaning |
| --- | --- |
| `*` | exactly one sign (any value) |
| `**` | zero or more signs |
| label (e.g. `KU`) | that exact sign |

Matching is case-insensitive after subscript folding (`RA₂` matches `RA2`). Each
`*` matches one whole sign, so `KU-*-RO` matches three-sign words beginning with
`KU` and ending with `RO`.

```python
from aegean.analysis import word_matches_sign_pattern
word_matches_sign_pattern("KU-NE-RO", "KU-*-RO")           # True
word_matches_sign_pattern("KU-RO",    "KU-*-RO")           # False
word_matches_sign_pattern("KU-RO",    "**-RO")             # True
word_matches_sign_pattern("A-TA-I-*301-WA-JA", "A-**-JA")  # True
```

### `*-RO` — two-sign words ending in `-RO`

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

### `KU-*` — two-sign words starting with `KU-`

```bash
aegean search lineara "KU-*"
# 'KU-*': 12 word(s)
#  KU-RO    37
#  KU-PA     4
#  KU-RA     2
#  KU-RE     2
#  KU-*305   1
#  KU-*321   1
#  KU-DA     1   (plus KU-KA, KU-NI, KU-PA₃, KU-PI, KU-TA, each 1)
```

### `KU-*-RO` — three-sign words from `KU` to `RO`

```bash
aegean search lineara "KU-*-RO"
# 'KU-*-RO': 1 word(s)
#  KU-MA-RO  1
```

Python frequency ranking:

```python
[(w, n) for w, n in corpus.word_frequencies()
 if word_matches_sign_pattern(w, "**-RO")]
# [('KU-RO', 37), ('KI-RO', 16), ('*86-RO', 4), ('SA-RO', 4), ('KI-DA-RO', 2), ('NU-RO', 2), ...]  # 18 words
```

To precompile a pattern for reuse across many words:

```python
from aegean.analysis import compile_sign_pattern
from aegean.analysis.patterns import match_sign_pattern
pat = compile_sign_pattern("KU-*-RO")
match_sign_pattern(["KU", "MA", "RO"], pat)   # True
```

Sign patterns also work as the `word-sign-pattern` predicate inside the
[query engine](Analysis#query-engine). Single-sign words have no hyphen to split
and never match a pattern; an empty pattern matches nothing.

---

## Accounting reconciliation (KU-RO / PO-TO-KU-RO)

`KU-RO` marks a total (variant `KU-RA`) and `PO-TO-KU-RO` marks a grand total.
`balance_check` sums the line items preceding each total line and compares the
sum against the stated amount.

> **Scope note.** Section boundaries are inferred heuristically and Aegean
> fraction metrology remains debated. Only **37** of the 1,721 tablets carry a
> checkable `KU-RO` or `KU-RA` total (41 total lines across those 37 documents);
> the remaining tablets are too fragmentary or lack totals. Of the 41 checked
> lines, **8** balance exactly.

Check a single tablet:

```bash
aegean balance lineara HT13
#  doc   marker  stated  computed  diff  balances
#  HT13  KU-RO   130.5   131.0     0.5   NO
```

HT13 states 130½ while the six entries above it sum to 131, a difference of ½.
In Python:

```python
from aegean.analysis import balance_check
for chk in balance_check(corpus.get("HT13")):
    print(chk)
# BalanceCheck(stated_total=130.5, computed_sum=131.0, item_count=6,
#              difference=0.5, balances=False, marker='KU-RO', total_line_index=7,
#              exact_difference=Fraction(1, 2))
```

`BalanceCheck` fields are `stated_total`, `computed_sum`, `item_count`,
`difference`, `balances`, `marker`, `total_line_index`, and the rational
`exact_difference`; the `exact_balances` property reports exact written-quantity
equality. Pass `balance_check(doc, exact=True)` or CLI `--exact` to use rational
equality for `balances`; the default uses a floating-point cutoff (`1e-6`). Exact
arithmetic does not confirm the reading, section boundary, or metrology.

### Corpus sweep

Omit the document id to check every total line in the corpus:

```bash
aegean balance lineara
# lineara: 41 total line(s) checked
#  HT9a   KU-RO   31.75   31.0    -0.75   NO
#  HT9b   KU-RO   24.0    24.0     0.0    yes
#  HT11b  KU-RO   180.0   180.0    0.0    yes
#  HT13   KU-RO   130.5   131.0    0.5    NO
#  HT25b  KU-RO   52.0    52.0     0.0    yes
#  ... (41 lines across 37 documents)
```

Pass `--strict` to exit non-zero if any checked total fails to balance, or
`--json` for JSON output.

### Intact balancing accounts

`checkable_accounts(corpus)` selects documents where every token is securely
read (no `LOST` or `UNCLEAR` status) and at least one stated total falls within
tolerance:

```python
from aegean.analysis.accounting import checkable_accounts, is_checkable_account
clean = checkable_accounts(corpus)            # 7 tablets at default tolerance=0.10
[d.id for d in clean]                         # ['HT9a', 'HT9b', 'HT11b', 'HT13', 'HT89', ...]
is_checkable_account(corpus.get("HT11b"))     # True
```

The default tolerance admits a difference within
`max(1, tolerance * abs(stated_total))` with `tolerance=0.10`. Even
`tolerance=0` retains the absolute allowance of 1; pass `exact=True` to require
exact rational equality.

---

## Tablet-structure detection

`classify_structure` groups inscriptions by token-stream shape. These are
content-shape heuristics rather than genre attributions, and individual
assignments can be overridden.

| Category key | Label | Rule |
| --- | --- | --- |
| `accounting` | Accounting | Total marker (`KU-RO`, `KU-RA`, `PO-TO-KU-RO`), or numerals/fractions with more than two multi-sign words |
| `libation` | Libation | Any of the 14 attested libation-formula words |
| `list` | Lists | More than three separator marks and no numerals |
| `text` | Text / Other | More than four multi-sign words and no numerals |
| `other` | Unclassified | Short or ambiguous inscriptions |

The 14 libation-formula forms (`aegean.analysis.structure.LIBATION_WORDS`) are
`A-TA-I-*301-WA-JA`, `JA-SA-SA-RA-ME`, `A-SA-SA-RA-ME`, `A-DI-KI-TE`,
`A-DI-KI-TE-TE`, `JA-DI-KI-TE-TE-DU-PU₂-RE`, `JA-DI-KI-TE-TE-*307-PU₂-RE`,
`TA-NA-TE`, `I-DA-MA-TE`, `SI-RU-TE`, `DI-KI-SE`, `PI-TE-RI`, `U-NA-KA-NA-SI`,
and `I-PI-NA-MA`. Rules are evaluated in the order shown above.

Census the corpus or classify one tablet:

```bash
aegean analyze structure lineara
# lineara: structure census (heuristic)
#  accounting   137
#  libation      25
#  list           5
#  text           1
#  other       1553

aegean analyze structure lineara HT13
# HT13: accounting
```

Python API:

```python
from aegean.analysis.structure import classify_structure, classify_corpus
classify_structure(corpus.get("HT13"))         # 'accounting'
buckets = classify_corpus(corpus)              # {'accounting': [...ids...], ...}
len(buckets["accounting"])                     # 137
```

---

## Commodity logograms

`aegean.scripts.lineara.commodities` provides 21 commodity heads with standard
GORILA/Younger glosses and broad categories, along with helpers to distinguish
commodity ideograms from syllabic words. Glosses follow standard typological
identifications; the syllabic values of the signs are separate, and numbered
`*NNN` logograms have no settled referent.

```python
from aegean.scripts.lineara.commodities import COMMODITIES, commodity_head, is_lexical_word
len(COMMODITIES)                  # 21
commodity_head("GRA")             # 'GRA'
commodity_head("OLE+U")           # 'OLE'  (strips ligature modifier)
commodity_head("OVISm")           # 'OVIS' (strips sex marker)
commodity_head("KU-RO")           # None   (hyphenated syllabic word)
is_lexical_word("KU-RO")          # True
is_lexical_word("KU-NI-SU")       # True   (NI is a syllabogram inside words; standalone NI is figs)
```

Most frequent commodities in the bundled corpus:

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

## Editorial status

The bundled corpus is a normalized transcription, and the apparatus it retains is
mapped onto `ReadingStatus` at load time: erased-sign marks become
`ReadingStatus.LOST`, and break-damaged words or bracketed uncertain readings
become `ReadingStatus.UNCLEAR`:

```python
from aegean.core.model import ReadingStatus
lost    = sum(1 for d in corpus for t in d.tokens if t.status is ReadingStatus.LOST)
unclear = sum(1 for d in corpus for t in d.tokens if t.status is ReadingStatus.UNCLEAR)
docs    = sum(1 for d in corpus if any(t.status is not ReadingStatus.CERTAIN for t in d.tokens))
lost, unclear, docs            # (552, 120, 366)
```

In total, 366 of 1,721 documents carry editorial status (552 `LOST` tokens, 120
`UNCLEAR`). The upstream digitization omits full Leiden apparatus (restorations
and dotted signs); consult GORILA and SigLA for critical-edition readings. The
EpiDoc reader ingests `<unclear>`, `<supplied>`, and `<gap>`, and the writer
emits `LOST` as `<supplied reason="undefined">`.

---

## The SigLA corpus (opt-in, fetched)

SigLA (Salgarella & Castellan) is an independent palaeographic database of
Linear A, published under **CC BY-NC-SA 4.0**. pyaegean hosts the decoded
dataset as a SHA-256-pinned release asset fetched on demand; it is never bundled
in the Apache-2.0 wheel, and the NonCommercial/ShareAlike terms apply to
downstream use.

```python
sigla = aegean.load("sigla")        # ~1.3 MB fetch on first use, then cached
len(sigla)                          # 802
doc = sigla.get("HT 13")            # SigLA ids include a space
doc.meta.name                       # 'HT 13 (6.1×10.5×0.8 cm)'
" ".join(t.text for t in doc.tokens)
# 'KA-U-DE-TA VIN TE RE-ZA TE-TU TE-KI KU-*79-NI DA-SI-*118 I-DU-NE-SI KU-RO'
```

SigLA supplies document typology, find-site, physical dimensions, period, EFA
plate references, its own word division, and independent sign readings (e.g.,
`KU-*79-NI` where GORILA reads `KU-ZU-NI`). Because SigLA is a palaeographic
sign database, it does not record cardinal-number quantities; use the bundled
GORILA corpus for accounting reconciliation. All corpus commands work on
`sigla` (`aegean info sigla`, `aegean search sigla "*-RO"`,
`aegean stats sigla`). See [Data & Provenance](Data-and-Provenance).

---

## Browser workbench

`aegean workbench` fetches and serves the multi-script browser workbench
(`v2.1.0`) locally with self-hosted Noto Sans Aegean fonts:

```bash
aegean workbench --corpus lineara
aegean workbench --corpus lineara --damos --state workspace.json   # with Linear B divergence + local state sync
aegean workbench --corpus sigla                                    # open SigLA in the browser UI
```

Add `--fetch-images` once to cache the ~116 MB Linear A facsimile imagery for
local viewing. From Python, `aegean.io.to_workbench_bundle(corpus, "lineara.json")`
writes the multi-script schema-v1 bundle (inscriptions, sign inventory, and
phonetic map) for direct import into the workbench; see
[Interoperability](Interoperability) for workspace backup round-tripping with
`load_workbench_backup` and `save_workbench_backup`.

---

## Frequencies and analytical toolkit

Word and sign frequencies from the shell:

```bash
aegean stats lineara --top 5
#  KU-RO              37
#  SA-RA₂             20
#  KI-RO              16
#  *411-VS            15
#  A-TA-I-*301-WA-JA  11

aegean stats lineara --signs --top 5
#  KU     307
#  KA     284
#  *301   274
#  SI     240
#  A      202
```

Phonetic distance, alignment, association tests (χ², log-likelihood,
Fisher, PMI), collocation, morphological clustering, the compound
[query engine](Analysis#query-engine), keyness, and dispersion are documented on
[Analysis](Analysis).

One negative empirical result applies directly to Linear A: a cross-script
Procrustes alignment calibrated by leave-one-out over the 53 signs shared with
Linear B recovered no signal (top-1 `0.000`, median rank 26 of 73 against a
chance median of 37), whereas aligning a script to itself recovers 90.1% of
signs at rank 1. Distributional embedding alignment carries no recoverable
Linear A to Linear B correspondence at this corpus scale; see
[Cross-script alignment, and the null it measured](Analysis#cross-script-alignment-and-the-null-it-measured).

### Command reference (Linear A)

| Command | Action | Key flags |
| --- | --- | --- |
| `aegean info lineara` | Corpus size, provenance, license | `--json` |
| `aegean load lineara` | Filter by metadata; list or export | `--site --period --scribe --support -o --limit --json` |
| `aegean show lineara HT13` | One document, line by line | `--json` |
| `aegean search lineara "KU-*-RO"` | Wildcard sign-pattern search | `--json` |
| `aegean query lineara` | Compound query engine | `--where --output-kind --fields --limit --json` |
| `aegean stats lineara` | Word or sign frequency table | `--signs --top --view --count-unit --statuses --details --json` |
| `aegean sign lineara KU` | Look up one sign | `--json` |
| `aegean balance lineara [HT13]` | `KU-RO` reconciliation | `--strict --exact --tolerance --json` |
| `aegean analyze structure lineara [HT13]` | Heuristic categories | `--json` |
| `aegean workbench --corpus lineara` | Launch local browser workbench (`v2.1.0`) | `--damos --state --fetch-images --site --doc` |
| `aegean cite lineara` | Cite the corpus or filtered subset | `--style --site --period --scribe --support` |
| `aegean export lineara` | Export JSON / CSV / Parquet / EpiDoc / SQLite / Workbench / RDF Turtle / JSON-LD | see [CLI](CLI) |

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

## Limitations

- **Undeciphered script.** Sound values follow a Linear B convention;
  transliterations, totals, structure labels, and commodity glosses are
  analytical hypotheses.
- **Fragmentary corpus.** Only 37 tablets carry a checkable total, section
  boundaries for accounting reconciliation are heuristic, and full Leiden
  apparatus is absent from the bundled digitization.
- **Heuristic structure labels.** `accounting`, `libation`, `list`, and `text`
  reflect surface token rules, not editorial genre classifications.
- **SigLA terms and coverage.** SigLA omits numerical quantities and is licensed
  CC BY-NC-SA 4.0.

See [Limitations](Limitations) for project-wide boundaries, [Analysis](Analysis)
for statistical methods, and [Getting Started](Getting-Started) for setup.
