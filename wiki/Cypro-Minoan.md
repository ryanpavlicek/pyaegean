# Cypro-Minoan

Cypro-Minoan is the undeciphered writing system of Bronze Age Cyprus
(c. 1550–1050 BC), attested on clay balls, cylinders, and tablets from sites
including Enkomi and Ugarit. It descends from Linear A and appears structurally
syllabic, but its phonetic values and underlying language remain unknown.

pyaegean provides a **99-sign inventory** from Unicode and sign-sequence
tokenization for structural and distributional work. Because no sound values are
accepted, there is no phonetic transliteration, lexicon, or Greek bridge; all
analysis stops at the sign level. See [Limitations](Limitations) for
project-wide boundaries.

```python
import aegean
from aegean.core.script import get_script

aegean.__version__                                # '0.74.0'
aegean.registered_scripts()                       # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
len(get_script("cyprominoan").sign_inventory)     # 99
```

---

## Scope

| Capability | Cypro-Minoan | Notes |
| --- | --- | --- |
| Sign inventory (glyph, codepoint) | Supported (99 signs) | Unicode Cypro-Minoan block |
| Phonetic values | Always `None` | Undeciphered script |
| Tokenization (sign sequence → signs) | Supported | Splits hyphen-joined sign numbers |
| Phonetic transliteration | Not available | No settled values |
| Greek bridge / lemma mapping | Refused | See [Why no Greek bridge](#why-no-greek-bridge) |
| Bundled corpus | 2 illustrative documents | Edited corpus is not openly redistributable |
| Corpus tools (`info`, `show`, `stats`, `search`, `query`, `export`, `cite`, `workbench`) | Supported | Script-agnostic tooling |

For the deciphered scripts (sound values, lemmas, and Greek), see
[Linear B](Linear-B), [Cypriot](Cypriot), and [Greek NLP](Greek-NLP).

---

## Sign inventory

The sign inventory is built from the Unicode "Cypro-Minoan" block
(`U+12F90–U+12FF2`, Unicode-3.0): **99 signs** identified by conventional sign
number (`CM001`, `CM002`, ...) and glyph. Every sign's `phonetic` attribute is
`None`. Each `Sign` holds `label`, `glyph`, `codepoint`, `phonetic`,
`script_id`, and `attrs` (`unicodeName`, `signClass`).

### Python API

```python
from aegean.core.script import get_script

inv = get_script("cyprominoan").sign_inventory
len(inv)                              # 99
inv_list = list(inv)

inv_list[0].label                     # 'CM001'
inv_list[0].glyph                     # '𒾐' (font fallback may render differently in terminals)
hex(inv_list[0].codepoint)            # '0x12f90'
inv_list[0].attrs                     # {'unicodeName': 'CYPRO-MINOAN SIGN CM001', 'signClass': 'sign'}

all(s.phonetic is None for s in inv_list)   # True
```

Lookup helpers index the inventory by label, codepoint, and glyph:

```python
inv.by_label("CM005").label          # 'CM005'
inv.by_codepoint(0x12F90).label      # 'CM001'
inv.by_glyph("𒾐").label              # 'CM001'
```

With `pandas` (`pip install 'pyaegean[data]'`), export the inventory as a
DataFrame:

```python
df = get_script("cyprominoan").sign_inventory.to_dataframe()
df.shape                              # (99, 6)
df["phonetic"].unique()               # array([None], dtype=object)
df.head(4)
#    label glyph  codepoint phonetic              unicodeName signClass
# 0  CM001     𒾐      77712     None  CYPRO-MINOAN SIGN CM001      sign
# 1  CM002     𒾑      77713     None  CYPRO-MINOAN SIGN CM002      sign
# 2  CM004     𒾒      77714     None  CYPRO-MINOAN SIGN CM004      sign
# 3  CM005     𒾓      77715     None  CYPRO-MINOAN SIGN CM005      sign
```

### CLI

Look up a sign by label or glyph:

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

aegean sign cyprominoan "𒾐"          # resolves to CM001

aegean sign cyprominoan CM005 --json
# {
#   "label": "CM005",
#   "glyph": "𒾓",
#   "codepoint": "U+12F93",
#   "phonetic": "",
#   "attrs": { "unicodeName": "CYPRO-MINOAN SIGN CM005", "signClass": "sign" }
# }
```

In JSON output, `"phonetic": ""` represents the Python `None` value.

### Sign numbering conventions

Labels follow the published Cypro-Minoan sign list rather than a contiguous
1-to-99 sequence:

| Feature | Examples |
| --- | --- |
| Number gaps | `CM003` is absent (`CM001`, `CM002`, `CM004`, `CM005`, ...) |
| Suffixed variants | `CM012B`, `CM075B` |
| High numbers | final two signs are `CM301`, `CM302` |
| Codepoint span | `CM001` = `U+12F90` through `CM302` = `U+12FF2` |

```python
labels = [s.label for s in get_script("cyprominoan").sign_inventory]
labels[:6]            # ['CM001', 'CM002', 'CM004', 'CM005', 'CM006', 'CM007']
labels[-2:]           # ['CM301', 'CM302']
"CM003" in labels     # False
```

---

## Tokenization

Cypro-Minoan sign groups are written as hyphen-joined sign numbers
(`CM005-CM023-CM002`). `tokenize` splits on whitespace and decomposes each
hyphenated group into individual sign labels:

| Input shape | Token kind | `signs` |
| --- | --- | --- |
| Hyphen-joined group (`CM005-CM023-CM002`) | `WORD` | tuple of sign labels |
| Aegean word divider (`𐄀` U+10100 / `𐄁` U+10101) | `SEPARATOR` | divider glyph |
| Single sign or other token (`CM005`) | `UNKNOWN` | raw text |

Single-sign tokens are classified as `UNKNOWN` because without phonetic readings
an isolated sign cannot be distinguished from a mark or logogram.

```python
sc = get_script("cyprominoan")

toks = sc.tokenize("CM005-CM023-CM002 CM008-CM027")
[(t.text, t.kind.value, t.signs) for t in toks]
# [('CM005-CM023-CM002', 'word', ('CM005', 'CM023', 'CM002')),
#  ('CM008-CM027',       'word', ('CM008', 'CM027'))]

[t.kind.value for t in sc.tokenize("CM005")]        # ['unknown']

[(t.text, t.kind.value) for t in sc.tokenize("CM005-CM023 \U00010101 CM008-CM027")]
# [('CM005-CM023', 'word'), ('𐄁', 'separator'), ('CM008-CM027', 'word')]
```

Tokenization runs automatically when loading documents through the Python API or
CLI (`show`, `stats`, `search`).

---

## Bundled sample and custom corpora

Ferrara's edited Cypro-Minoan corpus (*Cypro-Minoan Inscriptions*) is not openly
redistributable, and sign identifications remain debated. pyaegean bundles two
illustrative sign-sequence documents to exercise the corpus model; they are not
transcriptions of specific edited inscriptions. To analyze a local sign-sequence
dataset, import it from text or CSV (`aegean import seqs.csv -o cm.db --script
cyprominoan` or `aegean.io.from_csv`).

| Document id | Site | Support | Period | Sign sequences |
| --- | --- | --- | --- | --- |
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

### CLI

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

`aegean info cyprominoan --json` outputs the same fields as JSON.

---

## Browser workbench

`aegean workbench` opens Cypro-Minoan corpora directly in the multi-script
browser workbench (`v2.1.0`) with self-hosted Noto Sans Aegean fonts (rendering
`U+12F90–U+12FF2` without system font installation) and the 99-sign inventory:

```bash
aegean workbench --corpus cyprominoan
aegean workbench --corpus my-cm-corpus.json --state cm-notes.json
```

From Python, `aegean.io.to_workbench_bundle(corpus, "cm-workbench.json")` writes
the schema-v1 multi-script envelope (`_meta.script = "cyprominoan"` and `signs`).
See [Interoperability](Interoperability) for workspace backup round-tripping.

---

## Frequencies, search, and export

All script-agnostic corpus tools run on `cyprominoan` and on any user-imported
Cypro-Minoan corpus.

### Sign and word frequencies

```bash
aegean stats cyprominoan --signs
# 11 distinct signs in the bundled sample, each with count 1

aegean stats cyprominoan
# CM005-CM023-CM002  1
# CM008-CM027        1
# CM009-CM033-CM017  1
# CM012-CM004-CM025  1

aegean stats cyprominoan --json
```

### Wildcard sign-pattern search

`*` matches one sign and `**` matches zero or more signs:

```bash
aegean search cyprominoan "CM005-*-*"   # matches CM005-CM023-CM002
aegean search cyprominoan "*-CM027"     # matches CM008-CM027
aegean search cyprominoan "CM005-*"     # 0 matches (no 2-sign group starts with CM005)
```

### Export

```bash
aegean export cyprominoan -f csv -o cm.csv
# wrote 2 documents to cm.csv (csv)
```

```csv
id,script_id,site,support,scribe,findspot,period,name,n_tokens,n_words
cm-enkomi-ball,cyprominoan,Enkomi,Clay ball,,,Late Cypriot (CM1),Illustrative Enkomi clay-ball sequence,2,2
cm-ugarit-tablet,cyprominoan,Ugarit,Clay tablet,,,Late Bronze Age (CM3),Illustrative Ugarit tablet sequence,2,2
```

### CLI command summary

| Command | Action |
| --- | --- |
| `aegean info cyprominoan` | Corpus size, provenance, license, citation |
| `aegean show cyprominoan <doc-id>` | One document, line-by-line tokens |
| `aegean stats cyprominoan [--signs]` | Word (default) or sign frequencies |
| `aegean search cyprominoan "<pattern>"` | Wildcard sign-pattern search |
| `aegean query cyprominoan ...` | Compound text, prefix, or sign-pattern queries |
| `aegean workbench --corpus cyprominoan` | Launch multi-script browser workbench (`v2.1.0`) |
| `aegean export cyprominoan -f ... -o ...` | Export JSON / CSV / Parquet / EpiDoc / SQLite / Workbench / RDF Turtle / JSON-LD |
| `aegean cite cyprominoan` | Citation string (Ferrara) |
| `aegean sign cyprominoan <label\|glyph>` | Sign glyph and Unicode codepoint |

---

## Why no Greek bridge

[Linear B](Linear-B) and the [Cypriot syllabary](Cypriot) have deciphered sound
values and attested Greek readings. Cypro-Minoan has no consensus decipherment
and its exact sign count remains debated, so the plugin provides sign structure
only. Calling `aegean bridge` on `cyprominoan` fails immediately:

```bash
aegean bridge cyprominoan CM005-CM023
# aegean: bridge supports the deciphered syllabic scripts: linearb, cypriot
```

---

## Limitations

- **No phonetic values.** Every sign has `phonetic = None`. Sign labels are
  catalogue numbers, not sound values.
- **Illustrative bundled sample.** The two bundled documents exercise the data
  model and are not transcriptions of specific edited inscriptions.
- **Full edited corpus excluded.** The published Cypro-Minoan corpus is not
  openly redistributable.
- **Terminal font support.** Terminals lacking Cypro-Minoan glyphs may display
  placeholder boxes; the codepoints (`U+12F90–U+12FF2`) are preserved, and the
  browser workbench (`v2.1.0`) bundles self-hosted Noto Sans Aegean fonts.
- **No transliteration, lexicon, or Greek bridge.** Cross-script tools treat
  Cypro-Minoan as sign sequences only.

---

## Provenance

Sign data comes from the Unicode Character Database (**Unicode-3.0**). Standard
field reference: Ferrara, S. (2012–2013). *Cypro-Minoan Inscriptions*, vols.
1–2. See [Data & Provenance](Data-and-Provenance) and `NOTICE`.

See also: [Linear A](Linear-A) · [Linear B](Linear-B) · [Cypriot](Cypriot) ·
[Greek NLP](Greek-NLP) · [Limitations](Limitations) · [CLI](CLI)
