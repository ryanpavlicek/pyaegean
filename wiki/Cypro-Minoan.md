# Cypro-Minoan

> **Exploratory material.** Cypro-Minoan is undeciphered: the methods here
> surface *evidence to weigh*, never readings or translations. The full picture
> of what pyaegean can and cannot claim is on the **[Limitations](Limitations)** page.

Cypro-Minoan is the **undeciphered** writing system of Bronze Age Cyprus (c. 1550–1050 BC), found on
clay balls, cylinders, and tablets at sites such as Enkomi and (in a variant) Ugarit. It descends
from Linear A and is structurally a syllabary, but its phonetic values are unknown and the language
behind it is unidentified. pyaegean treats it like [Linear A](Linear-A): a **99-sign inventory** plus
**sign-sequence tokenization** for exploratory work, with **no** transliteration, lexicon, or Greek
bridge; there are no settled sound values to offer.

**Use this page when you want to** browse the distinct signs, decompose Cypro-Minoan "words" into
their component sign numbers, and run the same corpus/statistics tooling you'd use on the deciphered
scripts, while staying honest that everything stops at the sign level.

```python
import aegean
from aegean.core.script import get_script

aegean.__version__                                # '0.10.0'
aegean.registered_scripts()                       # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
len(get_script("cyprominoan").sign_inventory)     # 99
```

---

## What's in scope (and what isn't)

| Capability | Cypro-Minoan | Why |
|---|---|---|
| Sign inventory (glyph, codepoint) | ✅ 99 signs | From the Unicode block |
| Phonetic / sound values | ❌ always `None` | Undeciphered: no settled values |
| Tokenization (sign-sequence → signs) | ✅ | Splits hyphen-joined groups |
| Transliteration to sounds | ❌ | Nothing to transliterate to |
| Greek bridge / lemma mapping | ❌ | See [`bridge` refuses it](#why-no-greek-bridge) |
| Bundled corpus | small illustrative sample (2 docs) | Edited corpus isn't openly redistributable |
| Corpus tooling (`info`, `show`, `stats`, `search`, `query`, `export`, `cite`) | ✅ | Script-agnostic, works on the sample |

For the deciphered side of the toolkit (sound values, lemmas, Greek), see [Linear B](Linear-B),
[Cypriot](Cypriot), and [Greek NLP](Greek-NLP).

---

## Sign inventory

Built from the Unicode **"Cypro-Minoan"** block (U+12F90–U+12FF2): **99 signs**, each identified only
by its conventional number (`CM001`, `CM002`, …) and glyph. Because the script is undeciphered, every
sign's `phonetic` value is `None`; the inventory is a catalogue of distinct signs, **not** a syllabary
with sounds.

Each `Sign` carries: `label`, `glyph`, `codepoint`, `phonetic` (`None`), `script_id`, and an `attrs`
dict with `unicodeName` and `signClass`.

### Python API

```python
from aegean.core.script import get_script

inv = get_script("cyprominoan").sign_inventory
len(inv)                              # 99
inv_list = list(inv)

inv_list[0].label                     # 'CM001'
inv_list[0].glyph                     # '𒾐'  (font fallback may render it as cuneiform)
hex(inv_list[0].codepoint)            # '0x12f90'
inv_list[0].attrs                     # {'unicodeName': 'CYPRO-MINOAN SIGN CM001', 'signClass': 'sign'}

all(s.phonetic is None for s in inv_list)   # True  — the whole point: no sounds
```

Three lookup helpers index the same set by label, glyph, and codepoint:

```python
inv.by_label("CM005").label          # 'CM005'
inv.by_codepoint(0x12F90).label      # 'CM001'
inv.by_glyph("𒾐").label              # 'CM001'
```

If you have pandas (the `[data]` extra), the whole inventory drops straight into a DataFrame: handy
for sorting or exporting the sign table:

```python
df = get_script("cyprominoan").sign_inventory.to_dataframe()
df.shape                              # (99, 6)
df["phonetic"].unique()              # array([None], dtype=object)
df.head(4)
#    label glyph  codepoint phonetic              unicodeName signClass
# 0  CM001     𒾐      77712     None  CYPRO-MINOAN SIGN CM001      sign
# 1  CM002     𒾑      77713     None  CYPRO-MINOAN SIGN CM002      sign
# 2  CM004     𒾒      77714     None  CYPRO-MINOAN SIGN CM004      sign
# 3  CM005     𒾓      77715     None  CYPRO-MINOAN SIGN CM005      sign
```

### CLI

Look up a single sign by **label** or by **glyph**:

```bash
aegean sign cyprominoan CM005
#             cyprominoan sign CM005
# ┌───────────────────┬─────────────────────────┐
# │ field             │ value                   │
# ├───────────────────┼─────────────────────────┤
# │ label             │ CM005                   │
# │ glyph             │ 𒾓                       │
# │ codepoint         │ U+12F93                 │
# │ attrs.unicodeName │ CYPRO-MINOAN SIGN CM005 │
# │ attrs.signClass   │ sign                    │
# └───────────────────┴─────────────────────────┘

# by glyph instead of label:
aegean sign cyprominoan "𒾐"          # resolves to CM001

# machine-readable:
aegean sign cyprominoan CM005 --json
# {
#   "label": "CM005",
#   "glyph": "𒾓",
#   "codepoint": "U+12F93",
#   "phonetic": "",
#   "attrs": { "unicodeName": "CYPRO-MINOAN SIGN CM005", "signClass": "sign" }
# }
```

> Note: in JSON the empty `"phonetic": ""` is just how "no value" serializes; it is **not** a sound
> value. In Python the same field is `None`.

### A note on the numbering

The labels follow the established Cypro-Minoan sign list, not a clean 1-to-99 run. Expect:

| Feature | Examples |
|---|---|
| Gaps in the numbers | `CM003` is absent; `CM001, CM002, CM004, CM005, …` |
| Letter-suffixed variants | `CM012B`, `CM075B` |
| High "special" numbers | the last two signs are `CM301`, `CM302` |
| First / last codepoints | `CM001` = U+12F90 · `CM302` = U+12FF2 |

```python
labels = [s.label for s in get_script("cyprominoan").sign_inventory]
labels[:6]      # ['CM001', 'CM002', 'CM004', 'CM005', 'CM006', 'CM007']
labels[-2:]     # ['CM301', 'CM302']
"CM003" in labels   # False
```

---

## Tokenization

A Cypro-Minoan "word" is written as a sequence of sign numbers joined by hyphens
(`CM005-CM023-CM002`). `tokenize` splits the text on whitespace and decomposes each hyphenated group
into its signs. The rules are deliberately minimal because there are no readings to resolve:

| Input shape | Token kind | `signs` |
|---|---|---|
| Hyphen-joined group (`CM005-CM023-CM002`) | `WORD` | one entry per sign |
| Aegean word divider (`𐄀` U+10100 / `𐄁` U+10101) | `SEPARATOR` | the divider glyph |
| A lone sign or anything else (`CM005`) | `UNKNOWN` | the raw text |

A lone sign is `UNKNOWN` (not `WORD`) on purpose: with one sign and no phonetics, there is nothing to
read into a word.

### Python API

```python
sc = get_script("cyprominoan")

toks = sc.tokenize("CM005-CM023-CM002 CM008-CM027")
[(t.text, t.kind.value, t.signs) for t in toks]
# [('CM005-CM023-CM002', 'word', ('CM005', 'CM023', 'CM002')),
#  ('CM008-CM027',       'word', ('CM008', 'CM027'))]

# a lone sign stays UNKNOWN
[t.kind.value for t in sc.tokenize("CM005")]        # ['unknown']

# Aegean word divider (U+10101) is tagged SEPARATOR
[(t.text, t.kind.value) for t in sc.tokenize("CM005-CM023 \U00010101 CM008-CM027")]
# [('CM005-CM023', 'word'), ('𐄁', 'separator'), ('CM008-CM027', 'word')]
```

There is no CLI subcommand that calls `tokenize` directly: tokenization happens automatically when a
document is loaded, so you see its results through `show`, `stats`, and `search` below.

---

## The corpus

The edited Cypro-Minoan corpus (Enkomi/Ugarit; Ferrara's *Cypro-Minoan Inscriptions*) is not openly
redistributable, and sign readings are contested. Only a small **illustrative sample** of sign
sequences is bundled: chosen to **exercise the model**, not to transcribe specific inscriptions. The
sign inventory is the shippable core; the sample is just enough to demonstrate the tooling. To work
on a larger sign-sequence set you've assembled yourself, import it from a `.txt` file or a CSV
(`aegean import seqs.csv -o cm.db --script cyprominoan`, or `aegean.io.from_csv`) and the whole
corpus API applies: the sign sequences are split on whitespace, same as the bundled sample.

### What's bundled

| Document id | Site | Support | Period | Words (sign sequences) |
|---|---|---|---|---|
| `cm-enkomi-ball` | Enkomi | Clay ball | Late Cypriot (CM1) | `CM005-CM023-CM002`, `CM008-CM027` |
| `cm-ugarit-tablet` | Ugarit | Clay tablet | Late Bronze Age (CM3) | `CM012-CM004-CM025`, `CM009-CM033-CM017` |

### Python API

```python
import aegean

corpus = aegean.load("cyprominoan")
len(corpus)                           # 2
[doc.id for doc in corpus]            # ['cm-enkomi-ball', 'cm-ugarit-tablet']

doc = next(iter(corpus))
doc.id                                # 'cm-enkomi-ball'
[w.text for w in doc.words]           # ['CM005-CM023-CM002', 'CM008-CM027']
doc.meta.site, doc.meta.support, doc.meta.period
# ('Enkomi', 'Clay ball', 'Late Cypriot (CM1)')
```

### CLI — overview, document, citation

```bash
aegean info cyprominoan
#                           aegean corpus: cyprominoan
# ┌────────────────────┬────────────────────────────────────────────────────────┐
# │ field              │ value                                                  │
# ├────────────────────┼────────────────────────────────────────────────────────┤
# │ documents          │ 2                                                      │
# │ words              │ 4                                                      │
# │ tokens             │ 4                                                      │
# │ signs_in_inventory │ 99                                                     │
# │ source             │ Illustrative sample of Cypro-Minoan sign sequences     │
# │ license            │ Sign data from the Unicode Character Database          │
# │                    │ (Unicode-3.0). Sample sequences are illustrative —     │
# │                    │ chosen to exercise the model, not transcriptions of    │
# │                    │ specific edited inscriptions.                          │
# │ citation           │ Ferrara, S. (2012–2013). Cypro-Minoan Inscriptions,    │
# │                    │ vols. 1–2.                                             │
# └────────────────────┴────────────────────────────────────────────────────────┘

aegean show cyprominoan cm-enkomi-ball
# cm-enkomi-ball  site=Enkomi  period=Late Cypriot (CM1)  support=Clay ball
#   1: CM005-CM023-CM002 CM008-CM027

aegean cite cyprominoan
# Ferrara, S. (2012–2013). Cypro-Minoan Inscriptions, vols. 1–2.
```

`aegean info cyprominoan --json` returns the same fields as a JSON object (`corpus`, `documents`,
`words`, `tokens`, `signs_in_inventory`, `source`, `license`, `citation`).

---

## Frequencies, search, and export

Because everything is the script-agnostic model, the general corpus tooling works on the sample. With
only four short words the counts are tiny, but the **commands and output shape are real**: they scale
to any larger sign-sequence corpus you bring in.

### Sign and word frequencies

```bash
aegean stats cyprominoan --signs
# cyprominoan: top 11 signs   →  each of CM005, CM023, CM002, CM008, CM027, CM012,
#                                CM004, CM025, CM009, CM033, CM017 appears once

aegean stats cyprominoan          # words (default)
# CM005-CM023-CM002  1
# CM008-CM027        1
# CM009-CM033-CM017  1
# CM012-CM004-CM025  1

aegean stats cyprominoan --json   # [{"item": "...", "count": 1}, …]
```

### Wildcard sign-pattern search

`*` matches **exactly one** sign, so the pattern's wildcard count must match the word's sign count:

```bash
aegean search cyprominoan "CM005-*-*"
#  'CM005-*-*': 1 word(s)  →  CM005-CM023-CM002

aegean search cyprominoan "*-CM027"
#  '*-CM027': 1 word(s)    →  CM008-CM027

aegean search cyprominoan "CM005-*"
#  'CM005-*': 0 word(s)    →  no 2-sign word starts with CM005
```

### Export

The corpus exports through the same paths as every other script: lossless JSON, tabular CSV/Parquet,
EpiDoc TEI, or SQLite:

```bash
aegean export cyprominoan -f csv -o cm.csv
# wrote 2 documents to cm.csv (csv)
```

```csv
id,script_id,site,support,scribe,findspot,period,name,n_tokens,n_words
cm-enkomi-ball,cyprominoan,Enkomi,Clay ball,,,Late Cypriot (CM1),Illustrative Enkomi clay-ball sequence,2,2
cm-ugarit-tablet,cyprominoan,Ugarit,Clay tablet,,,Late Bronze Age (CM3),Illustrative Ugarit tablet sequence,2,2
```

### Commands that accept `cyprominoan`

| Command | What it gives you here |
|---|---|
| `aegean info cyprominoan` | Size, provenance, license, citation |
| `aegean show cyprominoan <doc-id>` | One document, line-by-line tokens |
| `aegean stats cyprominoan [--signs]` | Word (default) or sign frequencies |
| `aegean search cyprominoan "<pattern>"` | Wildcard sign-pattern matches (`*` = one sign) |
| `aegean query cyprominoan …` | Compound text / prefix / sign-pattern queries |
| `aegean export cyprominoan -f … -o …` | JSON / CSV / Parquet / EpiDoc / SQLite |
| `aegean cite cyprominoan` | One-line citation (Ferrara) |
| `aegean sign cyprominoan <label\|glyph>` | One sign's glyph + codepoint |

Most commands also take `--json` for machine-readable output. Run any with `-h` for its full options.

---

## Why no Greek bridge

[Linear B](Linear-B) and the [Cypriot syllabary](Cypriot) are deciphered, so pyaegean can transliterate
them and map words to Greek lemmas via the **bridge**. Cypro-Minoan is **not**: proposed
decipherments exist but none is accepted, and even the total number of distinct signs is debated.
Offering phonetic values or "readings" would be speculation dressed as fact, so the plugin
deliberately stops at the sign level. The `bridge` command refuses it outright:

```bash
aegean bridge cyprominoan CM005-CM023
# aegean: bridge supports the deciphered syllabic scripts: linearb, cypriot
```

This mirrors how the toolkit treats [Linear A](Linear-A): structure and signs, clearly labeled
exploratory. For the scripts where a Greek reading **is** possible, see [Linear B](Linear-B) and
[Cypriot](Cypriot); for the Greek side itself, [Greek NLP](Greek-NLP).

---

## Limitations & honest notes

- **No phonetics, ever.** Every sign's `phonetic` is `None`. Do not read the sign numbers as sounds.
- **The bundled corpus is illustrative, not evidentiary.** Two short documents exist to exercise the
  model; they are **not** transcriptions of specific edited inscriptions, and the frequency/search
  numbers reflect that tiny sample.
- **The full edited corpus isn't bundled** (licensing) and sign readings are contested.
- **Glyphs may render as boxes or as cuneiform** if your font lacks the Cypro-Minoan block: the
  codepoints (U+12F90–U+12FF2) are correct regardless of what your terminal draws.
- **No transliteration, lexicon, alignment-to-Greek, or `bridge`.** Cross-script comparison tooling
  treats Cypro-Minoan as sign sequences only.

The complete, candid account of what pyaegean can and cannot claim (for this script and all the
others) lives on the **[Limitations](Limitations)** page.

---

## Provenance

The sign data comes from the **Unicode Character Database** (Unicode-3.0 license). The sample sign
sequences are illustrative, chosen to exercise the model. Citation for the field:
*Ferrara, S. (2012–2013). Cypro-Minoan Inscriptions, vols. 1–2.* See
[Data & Provenance](Data-and-Provenance) and the repository `NOTICE` file.

See also: [Linear A](Linear-A) · [Linear B](Linear-B) · [Cypriot](Cypriot) · [Greek NLP](Greek-NLP) ·
[Limitations](Limitations) · [CLI](CLI)
