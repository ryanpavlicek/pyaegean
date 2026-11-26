# Linear B

Linear B is the deciphered Aegean syllabary used to write Mycenaean Greek
(c. 1400–1200 BC) on clay tablets and vases from Knossos, Pylos, Thebes, Mycenae,
and Tiryns. pyaegean exposes Linear B through the same `Script` plugin interface
as [Linear A](Linear-A): a 211-sign inventory, transliteration to phonetic Latin,
a curated Greek-lemma bridge connecting into [Greek NLP](Greek-NLP), scribal-hand
analysis, and accounting reconciliation.

```python
import aegean
from aegean.scripts.linearb import word_to_phonetic, greek_reading

aegean.registered_scripts()              # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
word_to_phonetic("QA-SI-RE-U")           # 'kwasireu' (gʷasileus, ancestor of βασιλεύς)
greek_reading("PO-ME")                   # ('ποιμήν', 'shepherd')
```

## Summary

| Task | Python | CLI |
| --- | --- | --- |
| Look up a sign | `get_script("linearb").sign_inventory` | `aegean sign linearb KA` |
| Transliteration → sound | `word_to_phonetic("WA-NA-KA")` | via `bridge` or `analyze compare` |
| Read a word as Greek | `greek_reading("PO-ME")` | `aegean bridge linearb po-me` |
| Full dictionary entry | `greek_reading` → `aegean.greek.gloss(lemma)` | see [Greek NLP](Greek-NLP) |
| Load the full DAMOS corpus | `aegean.load("damos")` | `aegean info damos`, `aegean stats damos` |
| Slice by scribal hand | `corpus.filter(scribe="117")` | `aegean load damos --scribe 117` |
| Profile every hand | `scribal_hands(corpus)` | `aegean analyze hands damos` |
| Check a tablet's total | `balance_check(doc)` | `aegean balance linearb` / `aegean balance damos` |
| Open in browser workbench | `aegean.io.to_workbench_bundle(corpus)` | `aegean workbench --corpus damos` |
| Load local EpiDoc files | `load_epidoc_corpus(path)` | `PYAEGEAN_LINEARB_CORPUS=...` |

## Sign inventory

The sign inventory is generated from the Unicode Character Database (Linear B
Syllabary and Linear B Ideograms blocks, Unicode-3.0; see
[Data & Provenance](Data-and-Provenance)). It contains **211 signs**:

| Class (`attrs.signClass`) | Count | Description |
| --- | --- | --- |
| `syllabogram` | 74 | Signs with settled phonetic values (`ka`, `qa`, `za`, ...) |
| `symbol` | 14 | Undeciphered signs without settled sound values |
| `ideogram` | 117 | Commodity and object ideograms (`MAN`, `EWE`, grain, wine, ...) |
| `monogram` | 6 | Composite ligatures |
| **Total** | **211** | 123 ideograms + monograms |

Every sign records its Bennett number (`B077`, `B131`) and Unicode name.
Seventy-six signs (70 ideograms and 6 monograms) also carry a `commodity` tag.

```python
from collections import Counter
from aegean.core.script import get_script

inv = get_script("linearb").sign_inventory
ka = inv.by_label("KA")
ka.glyph, ka.phonetic, ka.attrs["bennett"]   # ('𐀏', 'ka', 'B077')

Counter(s.attrs.get("signClass") for s in inv)
# Counter({'ideogram': 117, 'syllabogram': 74, 'symbol': 14, 'monogram': 6})
```

CLI lookup accepts either a sign label or a single Unicode glyph:

```bash
aegean sign linearb KA
#                  linearb sign KA
# ┌───────────────────┬───────────────────────────┐
# │ field             │ value                     │
# ├───────────────────┼───────────────────────────┤
# │ label             │ KA                        │
# │ glyph             │ 𐀏                         │
# │ codepoint         │ U+1000F                   │
# │ phonetic          │ ka                        │
# │ attrs.bennett     │ B077                      │
# │ attrs.unicodeName │ LINEAR B SYLLABLE B077 KA │
# │ attrs.signClass   │ syllabogram               │
# │ attrs.commodity   │ None                      │
# └───────────────────┴───────────────────────────┘

aegean sign linearb QA --json
# {
#   "label": "QA", "glyph": "𐀣", "codepoint": "U+10023", "phonetic": "kwa",
#   "attrs": { "bennett": "B016", "unicodeName": "LINEAR B SYLLABLE B016 QA",
#              "signClass": "syllabogram", "commodity": null }
# }
```

Passing a single glyph works identically: `aegean sign linearb 𐀏` resolves to
`KA`.

### Full syllabary (sound values)

All 74 syllabogram values emitted by `word_to_phonetic`:

```text
a   a2  a3  au  da  de  di  do  du  dwe dwo dza dze dzo e
i   ja  je  jo  ju  ka  ke  ki  ko  ku  kwa kwe kwi kwo ma
me  mi  mo  mu  na  ne  ni  no  nu  nwa o   pa  pe  pi  po
pte pu  pu2 ra  ra2 ra3 re  ri  ro  ro2 ru  sa  se  si  so
su  ta  ta2 te  ti  to  tu  twe two u   wa  we  wi  wo
```

The labiovelar series (`qa qe qi qo`) is rendered `kwa kwe kwi kwo`, and the
`z`-series (`za ze zo`) is rendered `dza dze dzo`. Distinct complex or doublet
signs retain their trailing digits (`a2`, `a3`, `pu2`, `ra2`, `ra3`, `ta2`,
`ro2`).

### Selected commodity ideograms

| Label | Glyph | Commodity | Unicode name |
| --- | --- | --- | --- |
| `MAN` | 𐂀 | MAN | LINEAR B IDEOGRAM B100 MAN |
| `WOMAN` | 𐂁 | WOMAN | LINEAR B IDEOGRAM B102 WOMAN |
| `EQUID` | 𐂃 | EQUID | LINEAR B IDEOGRAM B105 EQUID |
| `EWE` | 𐂆 | EWE | LINEAR B IDEOGRAM B106F EWE |
| `RAM` | 𐂇 | RAM | LINEAR B IDEOGRAM B106M RAM |
| `BOAR` | 𐂋 | BOAR | LINEAR B IDEOGRAM B108M BOAR |

## Transliteration → phonetics

`word_to_phonetic` maps hyphenated Linear B transliterations to phonetic Latin.
Editorial markers (`*`, `[`, `]`, `?`) and Leiden underdots are stripped,
subscripts (`a₂`) are folded to ASCII digits (`a2`), and unrecognized signs pass
through lowercased.

```python
from aegean.scripts.linearb import word_to_phonetic

word_to_phonetic("WA-NA-KA")    # 'wanaka'   (ϝάναξ, "king")
word_to_phonetic("TI-RI-PO-DE") # 'tiripode' (τρίποδε, "two tripods")
word_to_phonetic("WO-NO")       # 'wono'     (ϝοῖνος → οἶνος, "wine")
word_to_phonetic("E-QE-TA")     # 'ekweta'   (labiovelar QE → kwe)
word_to_phonetic("RA-WA-KE-TA") # 'rawaketa' (lāwāgetās, "leader of the people")
word_to_phonetic("PU-RO")       # 'puro'     (Πύλος, "Pylos")
```

Pass `overrides` to test alternative sign values without modifying the bundled
table:

```python
word_to_phonetic("PA-WORD", overrides={"WORD": "x"})
```

## Bridge to Greek

`greek_reading` maps a transliterated Mycenaean word to a `(lemma, gloss)` tuple
from the bundled lexicon; `gloss` returns only the English string. Lookups fold
case, subscripts, and underdots, so `po-me`, `PO-ME`, and `TU-RO₂` resolve
identically.

```python
from aegean.scripts.linearb import greek_reading, gloss

greek_reading("PO-ME")      # ('ποιμήν', 'shepherd')
greek_reading("WA-NA-KA")   # ('ἄναξ', 'king, lord (wanax)')
greek_reading("TE-O")       # ('θεός', 'god')
greek_reading("I-JE-RE-JA") # ('ἱέρεια', 'priestess')
greek_reading("KO-WO")      # ('κόρος', 'boy, son')
greek_reading("KO-WA")      # ('κόρη', 'girl, daughter')
greek_reading("WO-NO")      # ('οἶνος', 'wine')
greek_reading("ME-RI")      # ('μέλι', 'honey')
greek_reading("TU-RO2")     # ('τυρός', 'cheese')
gloss("DO-E-RO")            # 'slave, servant (male)'
greek_reading("XX-YY")      # None
```

CLI equivalent:

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)

aegean bridge linearb qa-si-re-u
# qa-si-re-u → βασιλεύς   (chief, local leader (later: king))

aegean bridge linearb po-me --json
# {
#   "word": "po-me",
#   "greek": "ποιμήν",
#   "gloss": "shepherd"
# }
```

The bundled lexicon contains **149** attested equations combining a curated core
with Wiktionary Mycenaean Greek entries (via `kaikki.org`, CC BY-SA) that
explicitly state an Ancient Greek etymology. Compound titles resolve to their
constituent roots where appropriate (for example, `RA-WA-KE-TA` →
`λαὸς + ἡγέομαι`).

### Full dictionary lookup

Pass any returned lemma to the opt-in
[LSJ backend](Greek-NLP#lexicon-lsj-glossing-opt-in):

```python
import aegean
from aegean.scripts.linearb import greek_reading

aegean.greek.use_lsj()                 # fetches a ~15 MB index to cache on first use
lemma, _ = greek_reading("PO-ME")      # 'ποιμήν'
aegean.greek.gloss(lemma)
# 'ποιμήν: herdsman, whether of sheep or oxen, Od. 10.82-5, al.; opp. lord or owner (a)/nac), 4.87.'
```

LSJ source entries occasionally retain Beta Code snippets such as `(a)/nac)` for
`(ἄναξ)`.

## The full DAMOS corpus (`aegean.load("damos")`)

**DAMOS** (Database of Mycenaean at Oslo, F. Aurora) is published under
**CC BY-NC-SA 4.0**. pyaegean hosts the transliterations and core metadata as a
SHA-256-pinned release asset fetched on demand:

```python
import aegean

corpus = aegean.load("damos")        # fetches ~3 MB on first use, then cached offline
len(corpus.documents)                # 5932

doc = corpus.documents[0]
doc.id                               # 'KN Fp(1) 1 + 31 (138)'
doc.meta.site                        # 'Knossos'
doc.meta.support                     # 'tablet'
doc.meta.scribe                      # '138'
doc.meta.findspot                    # 'KN, A'
doc.meta.period                      # 'LM IIIA2 or LM IIIB'
print(doc.transcription)
# .1           de-u-ki-jo-jo       'me-no'
# .2        di-ka-ta-jo  /  di-we    OLE    S   1
# .3        da-da-re-jo-de     OLE    S   2
```

Each tablet becomes one `Document`. The loader splits words, numerals, and
logograms using DAMOS dividers (`,` and `/`), strips supraliteral quotes such as
`'me-no'`, and retains the verbatim source text in `Document.transcription`.

| `meta` field | Example | Coverage |
| --- | --- | --- |
| `site` | `"Knossos"` | all 5,932 documents |
| `support` | `"tablet"`, `"stirrup jar"`, `"label"`, `"nodule, sealed"` | all 5,932 documents |
| `scribe` | `"117"`, `"138"` | 3,945 of 5,932 documents |
| `findspot` | `"KN, A"`, `"PY, Room 8"` | where recorded in DAMOS |
| `period` | `"LM IIIA2 or LM IIIB"` | where recorded in DAMOS |

Major find-sites in DAMOS:

| Site | Tablets |
| --- | --- |
| Knossos | 4,224 |
| Pylos | 1,004 |
| Thebes | 363 |
| Mycenae | 87 |
| Tiryns | 27 |
| Inscribed vases (Thebes, Khania, Tiryns, Mycenae, others) | remainder |

CLI queries over `damos`:

```bash
aegean info damos
aegean stats damos --top 8
#  damos: top 8 words
# ┌──────────┬───────┐
# │ item     │ count │
# ├──────────┼───────┤
# │ pa-ro    │ 230   │
# │ ko-wo    │ 188   │
# │ pe-mo    │ 173   │
# │ o-na-to  │ 154   │
# │ e-ke     │ 143   │
# │ to-so-de │ 143   │
# │ ko-to-na │ 130   │
# │ ko-wa    │ 113   │
# └──────────┴───────┘

aegean search damos "po-*"         # po-me (8), po-si (5), ...
aegean dispersion damos ku-ta-to   # Gries' DP
```

### Filtering

`corpus.filter(...)` returns a new `Corpus` compatible with every analysis
function:

```python
corpus = aegean.load("damos")

corpus.filter(scribe="117")            # 684 tablets
corpus.filter(support="stirrup jar")   # 196 documents
corpus.filter(site="Pylos")            # 1,004 tablets
```

### Scribal-hand analysis

`aegean.analysis.scribal` profiles attributed hands and computes per-hand
keyness. `scribal_hands` returns one `HandProfile` per distinct attribution
string, sorted by document count; `hand_keyness` computes log-likelihood keyness
for one hand against the rest of the corpus. Each hand key represents one
distinct edition string (including qualified marks such as `117?` or sub-hand
tags): DAMOS contains 291 such strings, which `aegean.analysis.hands` groups
into 212 site-and-series dossiers.

```python
from aegean.analysis import scribal_hands, hand_keyness

profiles = scribal_hands(corpus)             # 291 attribution strings
for h in profiles[:5]:
    print(h.hand, h.doc_count, list(h.sites)[:1], [w for w, _ in h.top_words[:3]])
# 117 684 ['Knossos'] ['ku-ta-to', 'ru-ki-to', 'pa-i-to']
# 1   227 ['Pylos']   ['pe-mo', 'e-ke', 'pa-ro']
# 103 212 ['Knossos'] ['ko-wo', 'ko-wa', 'o-pi']
# 124 171 ['Knossos'] ['o-u-te-mi', 'ko-no-si-jo', 'a-mi-ni-so']
# 141 106 ['Knossos'] ['zo-a', 'ku-pi-ri-jo', 'o-no']

rows = hand_keyness(corpus, "117")
[r.item for r in rows[:6]]
# ['ku-ta-to', 'ru-ki-to', 'ra-to', 'u-ta-jo-jo', 'u-ta-jo', 'pa-i-to']
```

`HandProfile` exposes `hand`, `doc_count`, `token_count`, `word_count`, `sites`
(`{site: count}`), `periods`, and `top_words`. `scribal_hands` accepts `top_n`
and `min_docs`. Per-hand dispersion runs directly on a filtered slice:
`dispersion(corpus.filter(scribe="117"), "ku-ta-to")`. The same functions work
on any corpus that populates `meta.scribe`, including the bundled Linear A
corpus (592 of 1,721 inscriptions carry GORILA hand identifications).

### Licensing and citation

DAMOS is licensed **CC BY-NC-SA 4.0**; those NonCommercial and ShareAlike
obligations apply to downstream use. pyaegean fetches the asset on demand and
never bundles it in the Apache-2.0 wheel. Cite DAMOS (Aurora 2015) in published
work (`corpus.provenance.cite()`), and record the pinned asset hash via
`aegean data versions`. `scripts/build_damos_corpus.py` documents the build from
the DAMOS public API.

## Browser workbench

`aegean workbench` opens Linear B corpora directly in the multi-script browser
workbench (`v2.1.0`) with self-hosted Noto Sans Aegean fonts, the 211-sign
inventory, phonetic values, and Linear B `to-so`/`o-pe-ro` accounting
reconciliation:

```bash
aegean workbench --corpus damos                         # full DAMOS corpus
aegean workbench --corpus damos --site Pylos --scribe 1 # scoped view
aegean workbench --corpus linearb --state lb-notes.json # bundled sample + local workspace backup
```

From Python, `aegean.io.to_workbench_bundle(corpus, "damos-workbench.json")`
writes the schema-v1 multi-script envelope (inscriptions, `signs`,
`phoneticMap`, and `_meta.script = "linearb"`). See
[Interoperability](Interoperability) for workspace backup round-tripping.

## Accounting

Linear B administrative tablets record commodities and quantities, frequently
closing with a `to-so`/`to-sa` (τόσος, "so much") total or an `o-pe-ro`
(ὄφελος, "deficit / owed") line. The script-agnostic accounting engine
recognizes Linear B markers automatically:

| Role | Linear B markers | Meaning |
| --- | --- | --- |
| total | `TO-SO`, `TO-SA`, `TO-SO-DE` | stated total |
| deficit | `O-PE-RO`, `O-PE-RO-SI` | amount owed or outstanding |

`balance_check(doc)` sums item lines above each total line and returns one
`BalanceCheck` per total (`stated_total`, `computed_sum`, `item_count`,
`difference`, `balances`, `marker`, `total_line_index`, `exact_difference`, and
the `exact_balances` property). Pass `exact=True` (CLI `--exact`) to require
exact rational equality instead of the default `1e-6` float cutoff.

```python
from aegean.analysis import balance_check
from aegean.scripts.linearb.loader import classify
from aegean.core.model import Document, DocumentMeta

rows = [["A-KO-RA-JA", "3"], ["WO-NO", "4"], ["TO-SO", "7"]]
tokens, lines, pos = [], [], 0
for li, row in enumerate(rows):
    idxs = []
    for w in row:
        tokens.append(classify(w, li, pos))
        idxs.append(pos)
        pos += 1
    lines.append(idxs)
doc = Document(id="demo", script_id="linearb", tokens=tokens, lines=lines, meta=DocumentMeta())

for chk in balance_check(doc):
    print(chk.marker, chk.computed_sum, "==", chk.stated_total, "→", chk.balances)
# TO-SO 7.0 == 7.0 → True
```

CLI usage:

```bash
aegean balance linearb
aegean balance damos "KN Fp(1) 1 + 31 (138)"
aegean balance linearb --json --strict
```

`is_checkable_account(doc)` and `checkable_accounts(corpus)` select intact
tablets whose tokens are all securely read and whose total falls within
`max(1, tolerance * abs(stated_total))` (default `tolerance=0.10`; pass
`exact=True` for exact rational equality). Section boundaries are heuristic, so
a non-zero difference can reflect line damage or multi-section layout.

## Bundled sample (`aegean.load("linearb")`)

For offline use without fetching DAMOS, pyaegean bundles an **18-tablet sample**:
PY Ta 641 and PY Er 312 plus 16 single-line excerpts from Pylos, Knossos, and
Mycenae drawn from sourced Wiktionary Mycenaean quotations (CC BY-SA). These are
illustrative excerpts, not full critical editions; load `damos` for corpus-scale
work.

```python
import aegean
corpus = aegean.load("linearb")
len(corpus.documents)                 # 18
corpus.documents[0].id                # 'PY Ta 641'
```

```bash
aegean show linearb "PY Ta 641"
# PY Ta 641  site=Pylos  period=LH IIIB  scribe=Hand 2  support=Tablet
#   1: TI-RI-PO-DE AI-KE-U KE-RE-SI-JO WE-KE *201 2

aegean cite linearb
# Ventris, M. & Chadwick, J. (1973). Documents in Mycenaean Greek (2nd ed.). Cambridge University Press.
```

> **Case folding.** The bundled sample and EpiDoc reader use uppercase tokens,
> while DAMOS preserves lowercase transliterations (`to-so`). Marker matching
> folds case, so `balance_check` handles both conventions: across DAMOS it finds
> 130 tablets with stated totals (255 checks, 52 balancing exactly).

## Importing external Linear B corpora

### From CSV (e.g. a LiBER selection)

Selections exported from LiBER via clipboard and saved to CSV (for example,
columns `id,site,text`) can be loaded locally under LiBER's own terms without
re-hosting:

```python
from aegean.io import from_csv

corpus = from_csv(
    "my-liber-selection.csv",
    script_id="linearb",          # whitespace tokenizer preserves TI-RI-PO-DE
    id_col="id", text_col="text", meta_cols=["site"],
)
```

CLI equivalent: `aegean import sel.csv -o liber.db --script linearb`.

To record explicit license and citation metadata rather than `from_csv`'s
generic user-supplied provenance, construct the corpus through
`Corpus.from_records`:

```python
import csv
import aegean

with open("my-liber-selection.csv", encoding="utf-8") as f:
    records = [
        {"id": r["id"], "text": r["text"], "meta": {"site": r.get("site", "")}}
        for r in csv.DictReader(f)
    ]
corpus = aegean.Corpus.from_records(
    records,
    script_id="linearb",
    provenance=aegean.Provenance(
        source="Personal LiBER selection (manual export)",
        license="© CNR Edizioni — all rights reserved; personal research use",
        citation="LiBER — Linear B Electronic Resources (Del Freo & Di Filippo, CNR).",
    ),
)
```

### From local EpiDoc XML (DAMOS-style files)

Install the `[epidoc]` extra (`lxml`) for the Linear B DAMOS-style EpiDoc
reader (the generic `aegean.io.from_epidoc` uses only the stdlib XML parser):

```bash
pip install "pyaegean[epidoc]"
export PYAEGEAN_LINEARB_CORPUS=/path/to/damos
```

```python
import aegean
aegean.load("linearb")                          # loads PYAEGEAN_LINEARB_CORPUS instead of the sample

from aegean.scripts.linearb import load_epidoc_corpus, parse_epidoc
load_epidoc_corpus("/path/to/damos")            # Corpus
parse_epidoc("/path/to/one-file.xml")           # list[Document]
```

The reader extracts the tablet id and provenance from the TEI header, splits
lines at `<lb>`, maps `<supplied>`, `<unclear>`, `<gap>`, and `<app>` onto
`ReadingStatus`, and uppercases transliterations to match pyaegean's Linear B
token convention.

## CLI command reference

Data commands accept `--json` for machine-readable output. `CORPUS` may be
`linearb` (bundled sample) or `damos` (full fetched corpus).

| Command | Action |
| --- | --- |
| `aegean sign linearb LABEL` | Look up one sign (glyph, codepoint, sound, Bennett number) |
| `aegean bridge linearb WORD` | Look up a transliterated word's Greek lemma and gloss |
| `aegean info CORPUS` | Corpus size, provenance, license, and citation |
| `aegean cite CORPUS` | Citation string (with filter flags for exact subsets) |
| `aegean show CORPUS DOC_ID` | Document metadata and line-by-line tokens |
| `aegean load CORPUS` | Filter by metadata (`--scribe`, `--site`, `--support`) |
| `aegean search CORPUS PATTERN` | Wildcard sign-pattern matches with counts |
| `aegean stats CORPUS` | Word or sign (`--signs`) frequency table |
| `aegean dispersion CORPUS ITEM` | Gries' DP dispersion |
| `aegean keyness CORPUS ...` | Log-likelihood G² keyness against a reference |
| `aegean analyze hands CORPUS` | Scribal-hand profiles and per-hand keyness |
| `aegean balance CORPUS [DOC_ID]` | Accounting check (`--strict` exits 1 on failure) |
| `aegean workbench --corpus CORPUS` | Launch multi-script browser workbench (`v2.1.0`) |
| `aegean export CORPUS ...` | Export JSON / CSV / Parquet / EpiDoc / SQLite / Workbench / RDF Turtle / JSON-LD |
| `aegean data list` / `fetch` / `versions` | Manage fetchable datasets and pinned SHA-256 versions |

## Limitations

- **Curated bridge lexicon.** The 149-entry lexicon covers attested equations
  and returns `None` for unlisted words; it does not parse arbitrary Mycenaean
  forms.
- **Heuristic accounting.** Section boundaries are inferred and Aegean metrology
  is contested. Over DAMOS, 130 tablets carry checkable totals and 52 balance
  exactly.
- **DAMOS license.** DAMOS carries CC BY-NC-SA 4.0 terms and is never bundled in
  the wheel. Cite Aurora (2015).
- **Fragmentary tablets.** Damaged readings in DAMOS are flagged via
  `ReadingStatus`, but incomplete text limits statistical and accounting analyses.

See [Limitations](Limitations) for project-wide boundaries.

## Related pages

- [Greek NLP](Greek-NLP): dictionary lookup, morphology, and parsing for Greek lemmas
- [Linear A](Linear-A): undeciphered sibling script under the same plugin model
- [Cypriot](Cypriot): deciphered Cypriot syllabary and Greek bridge
- [Analysis](Analysis): dispersion, keyness, collocation, scribal hands, and query engine
- [Data & Provenance](Data-and-Provenance): dataset sources and licensing
- [CLI](CLI), [Meters](Meters), and [Limitations](Limitations)
