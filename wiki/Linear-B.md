# Linear B

Linear B is the **deciphered** Aegean syllabary — it writes Mycenaean Greek, the earliest
attested form of the language (roughly 1400–1200 BC, on clay tablets from Knossos, Pylos, Thebes
and elsewhere). pyaegean reads it through the same `Script` plugin model as
[Linear A](Linear-A): a sign inventory, transliteration to phonetics, a bridge straight into the
[Greek track](Greek-NLP), and the script-agnostic accounting check. Because Linear B is *read*,
the work here is verifiable rather than exploratory — when you ask for the Greek behind a
Mycenaean word, you get a real, source-attested equation, not a guess.

Use this page if you want to: turn a transliterated word like `PO-ME` into `ποιμήν` ("shepherd")
and its full LSJ entry; look up any of the 211 signs with its Bennett number and sound value;
load the **whole DAMOS corpus** (~5,900 tablets) and slice it by scribal hand, site, or object
class; or check a tablet's stated total against its items.

```python
import aegean
from aegean.scripts.linearb import word_to_phonetic, greek_reading

aegean.registered_scripts()              # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
word_to_phonetic("QA-SI-RE-U")           # 'kwasireu'  (gʷasileus, the ancestor of βασιλεύς)
greek_reading("PO-ME")                   # ('ποιμήν', 'shepherd')
```

## What you can do at a glance

| Task | Python | CLI |
| --- | --- | --- |
| Look up a sign | `get_script("linearb").sign_inventory` | `aegean sign linearb KA` |
| Transliteration → sound | `word_to_phonetic("WA-NA-KA")` | — (via `bridge`) |
| Read a word as Greek | `greek_reading("PO-ME")` | `aegean bridge linearb po-me` |
| Full dictionary entry | `greek_reading` → `aegean.greek.gloss(lemma)` | see [Greek NLP](Greek-NLP) |
| Load the full corpus | `aegean.load("damos")` | `aegean info damos`, `aegean stats damos` |
| Slice by scribal hand | `corpus.filter(scribe="117")` | `aegean load damos --scribe 117` |
| Profile every hand | `scribal_hands(corpus)` | — |
| Check a tablet's total | `balance_check(doc)` | `aegean balance linearb` |
| Bring your own corpus | `load_epidoc_corpus(path)` | `PYAEGEAN_LINEARB_CORPUS=…` |

## Sign inventory

The inventory is built from the Unicode Character Database — the Linear B Syllabary and Ideograms
blocks — so it is authoritative and freely licensed (see [Data & Provenance](Data-and-Provenance)).
It holds **211 signs**:

| Class (`attrs.signClass`) | Count | What it is |
| --- | --- | --- |
| `syllabogram` | 74 | A sign with a phonetic value (`ka`, `qa`, `za`…) |
| `symbol` | 14 | Still-undeciphered signs (no settled sound) |
| `ideogram` | 117 | Commodity/object pictograms (grain, wine, MAN, EWE…) |
| `monogram` | 6 | Composite ligatures |
| **total** | **211** | 123 of these are ideograms + monograms |

Every sign keeps its **Bennett number** (`B077`, `B131`) and its Unicode name; ideograms (and a
few monograms) also carry a `commodity` tag where one applies — 76 signs in all (70 ideograms +
6 monograms).

```python
from aegean.core.script import get_script

inv = get_script("linearb").sign_inventory
ka = next(s for s in inv if s.label == "KA")
ka.glyph, ka.phonetic, ka.attrs["bennett"]   # ('𐀏', 'ka', 'B077')

# count by class
from collections import Counter
Counter(s.attrs.get("signClass") for s in inv)
# Counter({'ideogram': 117, 'syllabogram': 74, 'symbol': 14, 'monogram': 6})
```

The same lookup is one command from the shell, in a human table or as JSON:

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

You can also pass a single glyph instead of a label — `aegean sign linearb 𐀏` finds `KA`.

### The full syllabary (sound values)

All 74 syllabogram values pyaegean knows, exactly as `word_to_phonetic` emits them:

```
a   a2  a3  au  da  de  di  do  du  dwe dwo dza dze dzo e
i   ja  je  jo  ju  ka  ke  ki  ko  ku  kwa kwe kwi kwo ma
me  mi  mo  mu  na  ne  ni  no  nu  nwa o   pa  pe  pi  po
pte pu  pu2 ra  ra2 ra3 re  ri  ro  ro2 ru  sa  se  si  so
su  ta  ta2 te  ti  to  tu  twe two u   wa  we  wi  wo
```

Note the two scholarly conventions pyaegean follows: the **labiovelar** series (`qa qe qi qo`)
is written `kwa kwe kwi kwo`, and the **affricate** series (`za ze zo`) is written `dza dze dzo`.
The complex/optional signs keep their digit (`a2`, `a3`, `pu2`, `ra2`, `ra3`, `ta2`, `ro2`) because
they are distinct signs from the plain ones, not just typographic variants.

### Some commodity ideograms

A handful of the 117 ideograms (the `commodity` tag names the thing counted):

| Label | Glyph | Commodity | Unicode name |
| --- | --- | --- | --- |
| `MAN` | 𐂀 | MAN | LINEAR B IDEOGRAM B100 MAN |
| `WOMAN` | 𐂁 | WOMAN | LINEAR B IDEOGRAM B102 WOMAN |
| `EQUID` | 𐂃 | EQUID | LINEAR B IDEOGRAM B105 EQUID |
| `EWE` | 𐂆 | EWE | LINEAR B IDEOGRAM B106F EWE |
| `RAM` | 𐂇 | RAM | LINEAR B IDEOGRAM B106M RAM |
| `BOAR` | 𐂋 | BOAR | LINEAR B IDEOGRAM B108M BOAR |

## Transliteration → phonetics

`word_to_phonetic` converts a hyphenated transliteration to a phonetic Latin form. Editorial
markers (`*`, `[`, `]`, `?`) are stripped, subscripts (`a₂`) are normalised to digits (`a2`), and
any sign it does not recognise simply falls through lowercased.

```python
from aegean.scripts.linearb import word_to_phonetic

word_to_phonetic("WA-NA-KA")    # 'wanaka'   (ϝάναξ, "king")
word_to_phonetic("TI-RI-PO-DE") # 'tiripode' (τρίποδε, "two tripods")
word_to_phonetic("WO-NO")       # 'wono'     (ϝοῖνος → οἶνος, "wine")
word_to_phonetic("E-QE-TA")     # 'ekweta'   (the "Follower", a rank — labiovelar QE → kwe)
word_to_phonetic("RA-WA-KE-TA") # 'rawaketa' (lāwāgetās, "leader of the people")
word_to_phonetic("PU-RO")       # 'puro'     (Πύλος, "Pylos")
```

You can test an alternative sign value without touching the data, by passing `overrides`:

```python
word_to_phonetic("PA-WORD", overrides={"WORD": "x"})  # treats the sign WORD as 'x'
```

## Bridge to Greek — the `PO-ME` → shepherd lookup

Linear B *is* Greek, so a transliterated word resolves to its Classical Greek lemma and meaning.
`greek_reading` returns `(lemma, gloss)`; `gloss` returns just the English. The lookup normalises
case and subscripts for you, so `po-me`, `PO-ME` and `TU-RO₂` all work.

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
gloss("DO-E-RO")            # 'slave, servant (male)'   (δοῦλος)
greek_reading("XX-YY")      # None  — not in the lexicon
```

The same bridge from the shell:

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

The lexicon holds a **150-entry** core of well-established equations — a hand-curated set layered
with entries extracted from Wiktionary's Mycenaean Greek pages (via the kaikki.org dump, CC BY-SA):
only entries whose etymology *states* the Ancient Greek equation are taken, so every bridge is
source-attested rather than reconstructed. A few words resolve to a compound where the Greek is
itself two roots — e.g. `RA-WA-KE-TA` → `λαὸς + ἡγέομαι`.

### From a reading to the full dictionary entry

The bridge stops at the lemma on purpose; for the full entry, hand that lemma to the
[LSJ backend](Greek-NLP#lexicon-lsj-glossing-opt-in):

```python
import aegean
from aegean.scripts.linearb import greek_reading

aegean.greek.use_lsj()                 # opt-in; fetches a ~15 MB index to the cache on first use
lemma, _ = greek_reading("PO-ME")      # 'ποιμήν'
aegean.greek.gloss(lemma)
# 'ποιμήν: herdsman, whether of sheep or oxen, Od. 10.82-5, al.; opp. lord or owner (a)/nac), 4.87.'

lemma2, _ = greek_reading("WA-NA-KA")  # 'ἄναξ'
aegean.greek.gloss(lemma2)
# 'ἄναξ: …—lord, master, …'
```

The LSJ source carries some untransliterated beta-code, so a glyph occasionally surfaces raw — here
`(a)/nac)` is the beta-code for `(ἄναξ)`.

## The full DAMOS corpus — `aegean.load("damos")`

The most complete edition of the Mycenaean corpus is **DAMOS** (the Database of Mycenaean at Oslo,
F. Aurora), published under **CC BY-NC-SA 4.0**. pyaegean hosts the DAMOS transliterations and core
metadata as a fetched-on-demand release asset, so the whole corpus is one call away:

```python
import aegean

corpus = aegean.load("damos")        # fetches ~3 MB to the cache on first use, then offline
len(corpus.documents)                # 5932 — Knossos, Pylos, Thebes, Mycenae, Tiryns, vases…

doc = corpus.documents[0]
doc.id                               # 'KN Fp(1) 1 + 31 (138)'
doc.meta.site                        # 'Knossos'
doc.meta.support                     # 'tablet'
doc.meta.scribe                      # '138'
doc.meta.findspot                    # 'KN, A'
doc.meta.period                      # 'LM IIIA2 or LM IIIB'
print(doc.transcription)             # the DAMOS transliteration, verbatim:
# .1           de-u-ki-jo-jo       'me-no'
# .2        di-ka-ta-jo  /  di-we    OLE    S   1
# .3        da-da-re-jo-de     OLE    S   2
# …
```

Each tablet is one `Document`. The transliteration is tokenised into words / numerals / logograms
(using the DAMOS comma-and-slash word dividers and peeling supraliteral `'me-no'` quotes), and the
verbatim text is kept in `Document.transcription`. The DAMOS-curated context rides along in the
metadata, which is what makes scribe- and site-level work one-liners:

| `meta` field | Example | Coverage |
| --- | --- | --- |
| `site` | `"Knossos"` | every document |
| `support` (object class) | `"tablet"`, `"stirrup jar"`, `"label"`, `"nodule, sealed"` | every document |
| `scribe` (scribal hand) | `"117"`, `"138"` | 3,945 of 5,932 documents |
| `findspot` (find context) | `"KN, A"`, `"PY, Room 8"` | where DAMOS records one |
| `period` (chronology) | `"LM IIIA2 or LM IIIB"` | where DAMOS records one |

The sites, busiest first (real counts):

| Site | Tablets |
| --- | --- |
| Knossos | 4,224 |
| Pylos | 1,004 |
| Thebes | 363 |
| Mycenae | 87 |
| Tiryns | 27 |
| (plus inscribed vases: Thebes, Khania, Tiryns, Mycenae…) | |

The whole thing is browsable from the shell too — `aegean` treats `damos` like any fetched corpus:

```bash
aegean info damos              # size, provenance, license, citation
aegean stats damos --top 8     # most frequent words
#  damos: top 8 words
# ┌──────────┬───────┐
# │ item     │ count │
# ├──────────┼───────┤
# │ pa-ro    │ 230   │
# │ ko-wo    │ 188   │
# │ pe-mo    │ 173   │
# │ o-na-to  │ 154   │
# │ e-ke     │ 143   │
# └──────────┴───────┘

aegean search damos "po-*"     # words matching a wildcard sign pattern (po-me ×8, po-si ×5, …)
aegean dispersion damos ku-ta-to   # how concentrated a place-name is (Gries' DP)
```

### Slicing the corpus

`corpus.filter(...)` returns a new `Corpus` of the matching documents — chainable with every
analysis function:

```python
corpus = aegean.load("damos")

corpus.filter(scribe="117")            # the most prolific Knossos hand: 684 tablets
corpus.filter(support="stirrup jar")   # the painted-vase inscriptions: 196 documents
corpus.filter(site="Pylos")            # 1,004 Pylos tablets
```

### Scribal-hand analysis

The `aegean.analysis.scribal` layer profiles every hand and finds what is characteristic of each
one. `scribal_hands` returns one `HandProfile` per hand (busiest first); `hand_keyness` runs the
standard log-likelihood keyness of one hand against all the others.

```python
from aegean.analysis import scribal_hands, hand_keyness

profiles = scribal_hands(corpus)             # 291 hands in DAMOS
for h in profiles[:5]:
    print(h.hand, h.doc_count, list(h.sites)[:1], [w for w, _ in h.top_words[:3]])
# 117 684 ['Knossos'] ['ku-ta-to', 'ru-ki-to', 'pa-i-to']
# 1   227 ['Pylos']   ['pe-mo', 'e-ke', 'pa-ro']
# 103 212 ['Knossos'] ['ko-wo', 'ko-wa', 'o-pi']
# 124 171 ['Knossos'] ['o-u-te-mi', 'ko-no-si-jo', 'a-mi-ni-so']
# 141 106 ['Knossos'] ['zo-a', 'ku-pi-ri-jo', 'o-no']

rows = hand_keyness(corpus, "117")           # what does Hand 117 write more than the rest?
[r.item for r in rows[:6]]
# ['ku-ta-to', 'ru-ki-to', 'ra-to', 'u-ta-jo-jo', 'u-ta-jo', 'pa-i-to']  (mostly place-names)
```

`HandProfile` carries: `hand`, `doc_count`, `token_count`, `word_count`, `sites` (a `{site: tablets}`
map), `periods`, and `top_words`. `scribal_hands` takes `top_n=` (how many top words) and
`min_docs=` (drop hands below a threshold). Per-hand **dispersion** is just the standard helper over
the hand's slice — `dispersion(corpus.filter(scribe="117"), "ku-ta-to")`.

The hand layer is script-agnostic: any corpus whose documents set `meta.scribe` works. DAMOS is the
one that ships with hands today.

### Licensing and citation (read this)

The DAMOS data is **NonCommercial + ShareAlike** — those obligations pass through to you. The corpus
is hosted as a clearly-labeled CC BY-NC-SA 4.0 release asset, fetched to your cache on demand, and
**never bundled inside the Apache-2.0 wheel**. **Cite DAMOS** (Aurora 2015) in academic work — the
`Provenance` on the loaded corpus carries the citation, and `aegean data versions` pins the exact
asset sha256 for reproducible papers. `scripts/build_damos_corpus.py` documents exactly how the
asset is built from the DAMOS public API (joins, museum location and inventory numbers are also in
the JSON for those who read it directly).

## Accounting

Linear B tablets are administrative records — names, commodity ideograms, and numerals, often
with a `to-so`/`to-sa` (τόσος, "so much") total. The script-agnostic accounting engine reads them
directly, using Linear B's own markers in place of Linear A's `KU-RO`:

| Role | Linear B markers | Meaning |
| --- | --- | --- |
| total | `TO-SO`, `TO-SA` | "so much / so many" — the stated total |
| deficit | `O-PE-RO`, `O-PE-RO-SI` | what is owed / outstanding |

`balance_check(doc)` sums the item lines above each total line and compares. Each result is a
`BalanceCheck` with `stated_total`, `computed_sum`, `item_count`, `difference`, `balances`,
`marker`, and `total_line_index`.

```python
from aegean.analysis import balance_check
from aegean.scripts.linearb.loader import classify
from aegean.core.model import Document, DocumentMeta

# a tiny worked account: two items, then the stated total
rows = [["A-KO-RA-JA", "3"], ["WO-NO", "4"], ["TO-SO", "7"]]
tokens, lines, pos = [], [], 0
for li, row in enumerate(rows):
    idxs = []
    for w in row:
        tokens.append(classify(w, li, pos)); idxs.append(pos); pos += 1
    lines.append(idxs)
doc = Document(id="demo", script_id="linearb", tokens=tokens, lines=lines, meta=DocumentMeta())

for chk in balance_check(doc):
    print(chk.marker, chk.computed_sum, "==", chk.stated_total, "→", chk.balances)
# TO-SO 7.0 == 7.0 → True
```

From the shell, `aegean balance` sweeps a whole corpus (or one document) and can fail a CI run with
`--strict`:

```bash
aegean balance linearb            # sweep the bundled sample
aegean balance damos "KN Fp(1) 1 + 31 (138)"   # one tablet
aegean balance linearb --json --strict          # machine-readable; exit 1 if any total fails
```

`is_checkable_account(doc)` and `checkable_accounts(corpus)` pick out the *intact, balancing*
accounts — every token securely read, at least one total within tolerance (10% by default, because
Aegean metrology is imperfectly understood). They're a good "trust the arithmetic" filter for a
drill set.

The reconciliation is heuristic — section boundaries are inferred — so a balance is **evidence, not
proof**, exactly as for Linear A. See [Limitations](Limitations).

## The bundled sample — `aegean.load("linearb")`

For a zero-network default, pyaegean also bundles an **18-tablet illustrative sample** — PY Ta 641
(the tablet that confirmed Ventris's decipherment) and PY Er 312 hand-curated, plus sixteen one-line
excerpts from Pylos, Knossos and Mycenae tablets taken from *sourced quotations* in Wiktionary's
Mycenaean entries (each cites its tablet and carries a translation; CC BY-SA). These are excerpts to
exercise the tools, **not editions** — use `aegean.load("damos")` above for the full corpus, or
bring your own below.

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

> **A note on case.** The bundled sample and the EpiDoc reader use pyaegean's uppercase token
> convention, so the accounting markers (`TO-SO`) match and `balance_check` fires. The DAMOS
> asset preserves DAMOS's own **lowercase** transliterations (`to-so`), which the bridge and the
> lexicon handle (they normalise case) but the accounting markers do not — so `balance_check` over
> the raw DAMOS corpus will report nothing. To run the accounting over DAMOS, uppercase the relevant
> tokens first, or import your own copy through the EpiDoc path below (which uppercases on import).

## Bring your own corpus

### From a CSV (e.g. a LiBER selection)

LiBER's interface exports a selection by copy-to-clipboard ("e.g., to be pasted into an *Excel*
spreadsheet"). Your own copied selection — your use, under LiBER's terms; pyaegean fetches and
re-hosts nothing — saves as a CSV with columns like `id,site,text`. The one-step path is the
`from_csv` importer (or `aegean import sel.csv -o liber.db --script linearb` with no Python):

```python
from aegean.io import from_csv

corpus = from_csv(
    "my-liber-selection.csv",
    script_id="linearb",          # whitespace tokenizer (keeps TI-RI-PO-DE as one token)
    id_col="id", text_col="text", meta_cols=["site"],
)
```

`from_csv` stamps a generic *user-supplied* provenance. When you want the licensing recorded
explicitly — the right move for LiBER material — build through `Corpus.from_records` instead, which
takes your own `provenance=`:

```python
import csv
import aegean

with open("my-liber-selection.csv", encoding="utf-8") as f:
    records = [
        {"id": r["id"], "text": r["text"], "meta": {"site": r.get("site", "")}}
        for r in csv.DictReader(f)
    ]
corpus = aegean.Corpus.from_records(
    records, script_id="linearb",
    provenance=aegean.Provenance(
        source="My LiBER selection (manual export)",
        license="© CNR Edizioni — all rights reserved; personal research use",
        citation="LiBER — Linear B Electronic Resources (Del Freo & Di Filippo, CNR).",
    ),
)
```

### From an EpiDoc export (e.g. your own DAMOS download)

Point pyaegean at a licensed EpiDoc file or directory and it parses it locally, never re-hosting:

```bash
pip install "pyaegean[epidoc]"                  # the EpiDoc reader (lxml)
export PYAEGEAN_LINEARB_CORPUS=/path/to/damos   # a file or directory of EpiDoc XML
```

```python
import aegean
aegean.load("linearb")                          # now loads your corpus instead of the sample

# or explicitly:
from aegean.scripts.linearb import load_epidoc_corpus, parse_epidoc
load_epidoc_corpus("/path/to/damos")            # a Corpus
parse_epidoc("/path/to/one-file.xml")           # a list of Documents
```

The reader is tolerant of EpiDoc variation: it takes the tablet id and provenance from the header,
reads the transliteration line by line (splitting at `<lb>`), and maps the EpiDoc apparatus
(`<supplied>`, `<unclear>`, `<gap>`, `<app>`) to pyaegean's `ReadingStatus` so restored and uncertain
readings are flagged. EpiDoc transliterations are lowercase; the reader uppercases on import to match
pyaegean's token convention.

## Reference: Linear B CLI commands

Every command takes `--json` for machine-readable output. `corpus` accepts `linearb` (the sample) or
`damos` (the full fetched corpus), among others.

| Command | What it does |
| --- | --- |
| `aegean sign linearb LABEL` | Look up one sign (glyph, codepoint, sound, Bennett no.) |
| `aegean bridge linearb WORD` | Read a transliterated word as Greek |
| `aegean info CORPUS` | Corpus overview: size, provenance, license, citation |
| `aegean cite CORPUS` | One-line citation (filters cite the exact subset) |
| `aegean show CORPUS DOC_ID` | One document: metadata + line-by-line tokens |
| `aegean load CORPUS` | Filter by metadata (`--scribe`, `--site`, `--support`…); list or `--json` |
| `aegean search CORPUS PATTERN` | Words matching a wildcard sign pattern, with counts |
| `aegean stats CORPUS` | Frequency table of words (`--signs` for signs) |
| `aegean dispersion CORPUS ITEM` | How evenly an item spreads (Gries' DP) |
| `aegean keyness CORPUS …` | Key items vs a reference (log-likelihood G²) |
| `aegean balance CORPUS [DOC_ID]` | Accounting check (`--strict` exits 1 on a fail) |
| `aegean export CORPUS …` | Export to JSON / CSV / Parquet / EpiDoc / SQLite |
| `aegean data list` / `fetch` / `versions` | The fetchable datasets and the cache manifest |

## Limitations and honest notes

- **The bridge is a curated lexicon, not a parser.** 150 well-attested equations — it will not read
  an arbitrary unattested word. Words outside the lexicon return `None`. That's by design: every
  reading is source-attested.
- **Accounting is heuristic.** Section boundaries are inferred and Aegean metrology is contested; a
  balance is evidence, not proof. And it expects uppercase markers, so it doesn't fire over the raw
  (lowercase) DAMOS corpus — see the case note above.
- **DAMOS is NonCommercial.** The CC BY-NC-SA 4.0 obligations pass through to you, and the asset is
  never bundled in the wheel. Cite Aurora 2015.
- **Some tablets are fragmentary.** Many DAMOS transliterations carry brackets and damage markers
  (`[`, `]`, `?`); tokens are flagged with their editorial `ReadingStatus`, but a fragment is a
  fragment.

See the full [Limitations](Limitations) page for the project-wide caveats.

## Related pages

- [Greek NLP](Greek-NLP) — what to do with the lemma once the bridge hands it to you (glossing,
  morphology, treebank lookup).
- [Linear A](Linear-A) — the undeciphered sibling script, same plugin model.
- [Cypriot](Cypriot) — the other deciphered syllabary with a Greek-reading `bridge`.
- [Analysis](Analysis) — dispersion, keyness, collocation, structure, and the rest of the toolkit
  that works over the DAMOS corpus.
- [Data & Provenance](Data-and-Provenance) — where every dataset comes from and how it is licensed.
- [CLI](CLI) — the full command reference.
- [Meters](Meters) and [Limitations](Limitations).
