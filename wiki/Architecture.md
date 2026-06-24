# Architecture

This page is the developer's tour of pyaegean's **core data model** (the
script-agnostic value objects every script and analysis is built on) and the
five things you actually do with a corpus once you have it: serialize it
(lossless JSON, SQLite), turn it into tables (DataFrames, CSV, Parquet), query
it, cite it, and hand it to other tools (EpiDoc, the Linear A Research
Workbench). If you only want to *use* the corpus, the [Tutorial](Tutorial) and
[Analysis](Analysis) pages are friendlier; come here when you want to know how
the pieces fit, build your own corpus, or wire pyaegean into another system.

Every example below was run against the installed package; the output shown is
the real output. Where a feature has both a Python API and a CLI command, you
get both.

As of 0.8.2 the CLI is a first-class way in: **every `aegean` corpus argument
accepts any source**: a registered id, a Greek work id, a path to a saved
`.json` or `.db` corpus, or `-` for JSON on stdin, and you can **combine**,
**slice**, and **save** corpora and results without writing a line of Python.
The universal resolver is [`aegean.read_corpus`](#aegeanread_corpus--one-resolver-for-any-source);
combining/slicing is [`merge`/`subset`/`combine`](#combining-and-slicing-corpora).

## The layered design

pyaegean is built in **strict, downward-only layers**. Higher layers import
lower ones; the core never imports a script.

```
L6  ai (aegean.ai)        provider-agnostic LLM clients + grounded capabilities
L5  translate             hybrid: lexicon/morphology grounding → LLM
L5  greek (aegean.greek)  Greek NLP pipeline (normalize/tokenize/syllabify/…)
L4  io · geo · data · db  aegean.io (text/CSV import · EpiDoc/CSV/Parquet export)
                          · aegean.geo (GeoDataFrame) · bundled registry + cache
                          · aegean.db (SQLite)
L3  analysis              distance · align · morphology · collocation · patterns
                          · query · accounting · structure
L2  scripts (plugins)     lineara · linearb · cypriot · cyprominoan · greek
L1  core                  Corpus · Document · Token · Sign · SignInventory ·
                          Numeral · Script(ABC) · Registry · Provenance
```

The Greek layer (L5) also hosts the **opt-in** backends: the AGDT treebank
(`treebank.py`), LSJ glossing (`lexicon.py`), the dependency parser (`syntax.py`),
the POS tagger (`tagger.py`), the lemmatizers (`lemmatizer.py` and the neural
seq2seq backend `neural_lemmatizer.py`), and the neural joint pipeline (`joint.py`,
with `mst.py` arc decoding and `udfeats.py` FEATS rendering), which fetch and build
their artifacts through the L4 **data/cache** layer (a `greek → data` edge); the
strict downward-only layering still holds. See [Greek NLP](Greek-NLP) for that
track.

Why this matters in practice: **`import aegean` is instant and pulls zero
third-party packages.** pandas, lxml, the provider SDKs, matplotlib: all of
them are lazy-imported inside the functions that need them, and each lives behind
an [extra](Installation) you opt into. So the data model below is always
available, even on a bare Python install.

---

## The core model (`aegean.core`)

The model is a handful of frozen `@dataclass(slots=True)` value objects. A Linear
A syllabogram and a Greek letter are both a `Sign`; a `KU-RO` entry and a Greek
word are both a `Token`. Nothing in `aegean.core.model` knows about any
particular writing system: per-script behaviour lives in the
[script plugins](#scripts-are-plugins).

Everything in the core is importable from the top level:

```python
import aegean
from aegean import (
    Corpus, Document, DocumentMeta,
    Token, TokenKind, Sign, SignInventory,
    Provenance, ReadingStatus, Script,
)
```

### The objects at a glance

| Object | What it is | Key fields / methods |
|---|---|---|
| **`Sign`** | one graphic unit (syllabogram, letter, logogram) | `label`, `glyph`, `codepoint`, `phonetic`, `script_id`, `attrs` |
| **`Token`** | one unit in a document's text stream | `text`, `kind`, `signs`, `glyphs`, `line_no`, `position`, `status`, `alt`, `annotations` |
| **`Document`** | one inscription / tablet / text | `id`, `script_id`, `tokens`, `lines`, `meta`; props `.words`, `.numerals`, `.logograms`, `.line_tokens` |
| **`DocumentMeta`** | bibliographic / archaeological metadata | `site`, `support`, `scribe`, `findspot`, `period`, `name`, `images`, `notes` |
| **`Corpus`** | a collection of documents + inventory + provenance | `.load()`, `.get()`, `.filter()`, `.query()`, `.word_frequencies()`, `.to_dataframe()`, `.to_json()`, `.cite()`, … |
| **`SignInventory`** | a script's signs, indexed | `by_label()`, `by_glyph()`, `by_codepoint()`, `to_dataframe()` |
| **`Provenance`** | source / license / citation that travels with a corpus | `cite()`, `bibtex()`, `apa()` |

### `Sign`

One graphic unit of a script. `attrs` is a free dict for script-specific facts so
the core stays generic:

```python
import aegean
inv = aegean.load("lineara").sign_inventory
ku = inv.by_label("KU")
print(ku.label, ku.glyph, hex(ku.codepoint), ku.phonetic)
print(ku.attrs)
# KU 𐙂 0x10642 ku
# {'sharedWithLinearB': True, 'linearAOnly': False, 'total': 16, 'confidence': 1, 'altGlyphs': []}
```

### `Token` and `TokenKind`

A token carries its transliteration (`text`), its decomposed `signs`, and where
it sits in the document (`line_no`, `position`). Its `kind` is a `TokenKind`:

| `TokenKind` | Value | Meaning |
|---|---|---|
| `WORD` | `"word"` | a (multi-sign) lexical word |
| `LOGOGRAM` | `"logogram"` | ideogram / commodity sign |
| `NUMERAL` | `"numeral"` | a number or metrological fraction |
| `SEPARATOR` | `"separator"` | word/entry divider (e.g. 𐄁) |
| `PUNCT` | `"punct"` | punctuation (alphabetic scripts) |
| `UNKNOWN` | `"unknown"` | unclassified |

```python
import aegean
d = aegean.load("lineara").get("HT13")
for t in d.tokens[:5]:
    print(repr(t.text), t.kind.value, "signs=", t.signs, "line=", t.line_no, "pos=", t.position)
# 'KA-U-DE-TA' word signs= ('KA', 'U', 'DE', 'TA') line= 0 pos= 0
# 'VIN' logogram signs= ('VIN',) line= 0 pos= 1
# '𐄁' separator signs= ('𐄁',) line= 0 pos= 2
# 'TE' logogram signs= ('TE',) line= 0 pos= 3
# '𐄁' separator signs= ('𐄁',) line= 0 pos= 4
```

Two more fields handle the cases real epigraphy throws at you:

- **`annotations`**: a free `dict[str, str]` for per-token facts that don't fit
  the fixed columns. The bundled Greek New Testament carries `lemma`, `morph`,
  `strongs`, `gloss`, `normalized`, `upos`, and `ref` here, and they flow
  straight into the token-level DataFrame and the CSV/Parquet exporters.
- **`status`** and **`alt`**: see editorial certainty below.

### Editorial certainty (`ReadingStatus`) and alternates

Tokens carry a `ReadingStatus` so an edition's apparatus survives round-trips
through EpiDoc. `CERTAIN` is the default; the others map to the Leiden / EpiDoc
conventions for damaged, restored, and lost text.

| `ReadingStatus` | Value | EpiDoc | Leiden |
|---|---|---|---|
| `CERTAIN` | `"certain"` | (plain text) | securely read |
| `UNCLEAR` | `"unclear"` | `<unclear>` | underdot |
| `RESTORED` | `"restored"` | `<supplied>` | `[ ]` |
| `LOST` | `"lost"` | `<gap>` / `<supplied reason="lost">` | `[---]` |

A token's `alt` tuple holds alternate readings (EpiDoc `<app>`/`<rdg>`); `text`
is the lemma. The bundled corpora are normalized transcriptions (almost entirely
`CERTAIN`), but a bring-your-own EpiDoc corpus populates these from the markup,
and the [EpiDoc writer](#epidoc-tei-xml) emits them back out.

### `Document`

One inscription/tablet/text. Its physical layout lives in `lines` (a list where
each line is a list of indices into `tokens`) and convenience properties slice
the token stream for you:

```python
import aegean
d = aegean.load("lineara").get("HT13")
print(d.id, "| script", d.script_id)
print("words", len(d.words), "numerals", len(d.numerals),
      "logograms", len(d.logograms), "tokens", len(d.tokens))
print("meta:", d.meta.site, "|", d.meta.period, "|", d.meta.support)
print("physical lines:", len(d.line_tokens))
# HT13 | script lineara
# words 8 numerals 10 logograms 2 tokens 22
# meta: Haghia Triada | LMIB | Tablet
# physical lines: 8
```

| Property | Returns |
|---|---|
| `.words` | tokens with `kind == WORD` |
| `.numerals` | tokens with `kind == NUMERAL` |
| `.logograms` | tokens with `kind == LOGOGRAM` |
| `.line_tokens` | tokens regrouped into physical lines |
| `len(doc)` | total token count |

In Jupyter, a `Document` (and a `Corpus`, and a `SignInventory`) renders as a
tidy HTML card (line-by-line tokens, metadata, counts) so exploring a corpus in
a notebook is pleasant out of the box.

### `Corpus` — the hub

A `Corpus` is a list of documents plus a shared `SignInventory` and
`Provenance`. You rarely build one by hand; you `load` a bundled one:

```python
import aegean
c = aegean.load("lineara")            # or Corpus.load("lineara")
print(len(c))                          # 1721
print(c.get("HT13").id)                # HT13
```

The CLI equivalent of a quick look is `aegean info`:

```bash
aegean info lineara
```
```
                            aegean corpus: lineara
┌────────────────────┬──────────────────────────────────────────────────────┐
│ field              │ value                                                  │
├────────────────────┼──────────────────────────────────────────────────────┤
│ documents          │ 1721                                                   │
│ words              │ 1381                                                   │
│ tokens             │ 6406                                                   │
│ signs_in_inventory │ 344                                                    │
│ source             │ GORILA (Godart & Olivier 1976–1985) via …              │
│ license            │ Apache-2.0 (corpus JSON); facsimile imagery © …        │
│ citation           │ Godart, L. & Olivier, J.-P. (1976–1985). …             │
└────────────────────┴──────────────────────────────────────────────────────┘
```

**Filtering** returns a new corpus whose documents match all the metadata fields
(AND-combined), and, importantly, records a `subset:` note in the provenance so
a later citation states exactly what was used:

```python
c = aegean.load("lineara").filter(site="Haghia Triada")
print(len(c))                          # 1110
```
```bash
aegean load lineara --site "Haghia Triada" --limit 5
```

**Streaming views** never materialize a giant list, handy on a large corpus:

```python
c = aegean.load("lineara")
c.word_frequencies()[:3]
# [('KU-RO', 37), ('SA-RA₂', 20), ('KI-RO', 16)]
next(iter(c.iter_words()))             # 'QE-RA₂-U'
# c.iter_documents(), c.iter_tokens(), c.iter_words() are all lazy iterators
# (iter_documents() yields a list_iterator over the materialized documents;
#  only iter_tokens() and iter_words() are true generators)
```

A corpus has a cheap, stable **fingerprint**: a content hash over its script,
document ids, and token text (plus any `subset:` note). It's one pass over the
tokens with no model build, which makes it the cache key for the opt-in
[analysis cache](Analysis):

```python
c = aegean.load("lineara")
c.fingerprint()[:16]                   # '288e80c493eb478b'
c.cache_key() == c.fingerprint()       # True (cache_key is an alias)
```

### `aegean.read_corpus` — one resolver for any source

`aegean.load(id)` takes a registered id. `aegean.read_corpus(spec)` is the
generalization: it figures out what `spec` *is* and loads it. It's the same
resolver every `aegean` CLI command uses for its corpus argument, so anything
that works on the command line works here, and vice versa. The precedence is:

1. `"-"` reads a JSON corpus from **stdin**; an inline string starting with `{`
   is parsed directly (the output of `Corpus.to_json`).
2. an exact **registered id** (`"lineara"`, `"damos"`, `"nt"`, …): a registered
   id always wins over a same-named file.
3. a **Greek work id** like `"tlg0012.tlg001"` → fetched via
   `aegean.greek.load_work` (network on first use, then cached).
4. a **file path**: `.json` → `Corpus.from_json`; `.db` / `.sqlite` /
   `.sqlite3` → `Corpus.from_sql`.

Nothing matched raises `CorpusNotFound` (a `ValueError`) that lists the accepted
forms.

```python
import aegean
aegean.read_corpus("lineara")          # registered id → the bundled corpus
aegean.read_corpus("ht.json")          # a saved lossless JSON corpus
aegean.read_corpus("homer.db")         # a SQLite corpus on disk
# aegean.read_corpus("tlg0012.tlg001") # the Iliad, fetched then cached
```

The practical payoff is on the CLI: every command's corpus argument is a
`read_corpus` spec, so the Greek works, your saved subsets, and stdin pipes are
all in scope with no Python:

```bash
aegean stats     ht.json                       # a saved JSON subset
aegean db build  tlg0012.tlg001 -o iliad.db    # build a DB straight from a work id
aegean export    tlg0012.tlg002 -f csv -o odyssey.csv
python -c "import aegean; print(aegean.load('lineara').filter(site='Zakros').to_json())" \
  | aegean stats -                             # JSON corpus piped on stdin
```

### Combining and slicing corpora

Two corpora become one with `merge`; pick out documents by id with `subset`.
Both keep the provenance honest: the result cites every source (and names the
slice).

```python
import aegean
a = aegean.Corpus.from_records([{"id": "A1", "text": "KU-RO 10"},
                                {"id": "A2", "text": "A-DU 5"}], script_id="lineara")
b = aegean.Corpus.from_records([{"id": "B1", "text": "SA-RA2 3"}], script_id="lineara")

m = a.merge(b)                          # documents concatenated, in order
print([d.id for d in m])               # ['A1', 'A2', 'B1']
print(m.cite("plain"))
# Merged corpus of: User-supplied corpus (Corpus.from_records); User-supplied corpus (Corpus.from_records) [merged: 2 corpora → 3 documents]

s = m.subset(["A1", "B1"])             # id-based counterpart to filter()
print([d.id for d in s])               # ['A1', 'B1']
```

`Corpus.merge(*others, dedupe=...)` controls duplicate ids across the inputs:

| `dedupe` | Behaviour on a colliding id |
|---|---|
| `"error"` (default) | raise, listing the collisions: the safe default |
| `"first"` / `"last"` | keep that occurrence, drop the other |
| `"suffix"` | rename later collisions `id#2`, `id#3`, … |

```python
a = aegean.Corpus.from_records([{"id": "X1", "text": "KU-RO 10"}], script_id="lineara")
b = aegean.Corpus.from_records([{"id": "X1", "text": "A-DU 5"}], script_id="lineara")
a.merge(b)                  # ValueError: duplicate document ids across corpora: X1; …
a.merge(b, dedupe="last")   # keeps b's X1
a.merge(b, dedupe="suffix") # ids become ['X1', 'X1#2']
```

When the inputs share a `script_id` the merged corpus keeps it and the first
input's sign inventory; mixed scripts give `script_id="mixed"` and no inventory.

A `Corpus` is **self-consistent on document ids**: a corpus can't hold two
documents with the same id, so `Corpus.__init__` collapses duplicates, keeping
the last (which is what `.get()` already returns) and emitting a warning rather
than dropping silently, and after that `len()`, iteration, `.documents`, the id
lookup, and the fingerprint all agree. (`merge`'s `dedupe` modes above are the
*explicit* control across inputs; the collapse is the safety net for a single
list that happens to repeat an id.)

`aegean.combine([...])` is the module-level form (a list instead of `self` +
varargs), and the CLI `aegean combine` resolves each source with `read_corpus`,
merges, and saves to `.json` or `.db` in one step:

```bash
# all of Homer in one database, straight from two work ids
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db

# merge two saved subsets; --on-conflict mirrors the dedupe modes
aegean combine ht.json zakros.json -o crete.json
# wrote 1163 documents to crete.json (merged 2 sources)
```

`aegean combine` takes `--on-conflict {error|first|last|suffix}` (default
`error`) for duplicate ids, and the merged provenance names every source.

---

## Building your own corpus

You don't have to use a bundled corpus; your own inscriptions get the whole API
(filter, query, DataFrames, citation, export) the moment you wrap them in a
`Corpus`.

### `Corpus.from_records` — from plain dicts

Each record needs an `id` and its text as one of three keys, in order of
precedence: `lines` (a list of physical lines, each a list of tokens), `words`
(a flat token list = one line), or `text` (a whitespace-tokenized string = one
line). A token is a string, or a dict `{"text": …}` with optional `kind`,
`status`, and `alt`. When `kind` is omitted it's inferred: numerals by
parseability, everything else a word; hyphenated tokens get their `signs` split
automatically.

```python
import aegean
c = aegean.Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="lineara")

for d in c:
    print(d.id, [(t.text, t.kind.value, t.status.value) for t in d.tokens])
# X1 [('KU-RO', 'word', 'certain'), ('10', 'numeral', 'certain')]
# X2 [('A-DU', 'word', 'certain'), ('5', 'numeral', 'unclear')]
print(c.cite())
# User-supplied corpus (Corpus.from_records)
```

Optional record keys: `meta` (any of `site`/`support`/`scribe`/`findspot`/
`period`/`name`) and `translations`. Pass your own `provenance=` and
`sign_inventory=` to `from_records` if you have them. To make your corpus
loadable by name, register a loader (see [below](#scripts-are-plugins)):

```python
aegean.core.corpus.register_loader("myfind", lambda: c)
aegean.load("myfind")                  # now works
```

---

## Serialization: the JSON round-trip

There are two JSON exports, and the difference matters.

| Method | Fidelity | Use it for |
|---|---|---|
| `to_dict()` | **lossy** summary (per-doc words + metadata) | quick interop, a glance at the data |
| `to_json()` / `from_json()` | **lossless** | archiving, moving a corpus between machines, reproducibility |

### `to_dict` — the compact summary

```python
import aegean, json
d = aegean.load("lineara").filter(site="Haghia Triada").to_dict()
print(list(d["_meta"].keys()))
# ['tool', 'schemaVersion', 'scriptId', 'documentCount', 'source', 'license', 'citation']
print(list(d["documents"][0].keys()))
# ['id', 'script_id', 'words', 'glyphs', 'transcription', 'translations', 'meta']
```

The `_meta` block stamps the tool name, schema version, script id, document
count, and the provenance source/license/citation onto the export — so even the
lossy form carries its attribution.

### `to_json` / `from_json` — lossless

`to_json` serializes *everything*: every token (with its kind, signs, glyphs,
line/position, and any non-default status/alt/annotations), the physical lines,
full document metadata, the sign inventory, and the provenance. `from_json`
reverses it exactly.

```python
import aegean
c = aegean.load("lineara")

# in-memory string (indent defaults to 2; pass indent=None for compact)
js = c.to_json()
len(js)                                # 2661490

# round-trip and verify it's lossless
c2 = aegean.Corpus.from_json(js)
print(len(c2))                                         # 1721
print(c.get("HT13").tokens[0] == c2.get("HT13").tokens[0])   # True
print(c.fingerprint() == c2.fingerprint())             # True
```

`from_json` accepts a JSON **string**, a `Path`, or a path-like string (anything
not starting with `{`):

```python
c.to_json("lineara.json")              # writes the file, returns None
c3 = aegean.Corpus.from_json("lineara.json")
```

From the shell:

```bash
aegean export lineara -f json -o lineara.json
# wrote 1721 documents to lineara.json (json)

aegean export lineara -f json -o ht.json --site "Haghia Triada"
# wrote 1110 documents to ht.json (json)
```

(`aegean load CORPUS --output file.json` writes the same lossless JSON, which is
handy when you only want a metadata-filtered subset.)

---

## Tabular views: DataFrames, CSV, Parquet

`Corpus.to_dataframe(level=...)` is the bridge to pandas. Three levels:

| `level` | One row per | Columns |
|---|---|---|
| `"document"` (default) | document | `id`, `script_id`, `site`, `support`, `scribe`, `findspot`, `period`, `name`, `n_tokens`, `n_words` |
| `"token"` | token | `doc_id`, `line_no`, `position`, `text`, `kind`, `site`, `period` (+ any token `annotations` spread into columns) |
| `"word"` | `WORD` token | same as `token`, words only |

```python
import aegean
c = aegean.load("lineara")

c.to_dataframe("document").shape       # (1721, 10)
df = c.to_dataframe("token")
list(df.columns)
# ['doc_id', 'line_no', 'position', 'text', 'kind', 'site', 'period']
df.shape                               # (6406, 7)
```

At `token`/`word` level, any per-token `annotations` are **spread first**, so the
Greek NT's `lemma` / `morph` / `strongs` / `gloss` become their own columns
(canonical columns always win on a name clash). pandas is the `[data]` extra:

```bash
pip install "pyaegean[data]"
```

The CSV and Parquet exporters are thin wrappers over that DataFrame:

```python
from aegean.io import to_csv, to_parquet
c = aegean.load("lineara").filter(site="Haghia Triada")
to_csv(c, "ht.csv", level="document")        # ~93 KB
to_parquet(c, "ht.parquet", level="token")   # needs the [parquet] extra (pyarrow)
```
```bash
aegean export lineara -f csv     -o docs.csv  --level document
aegean export lineara -f parquet -o tok.parquet --level token
```

Parquet additionally needs a parquet engine; if it's missing you get a clear
message pointing at `pip install "pyaegean[parquet]"`.

The `SignInventory` has its own `to_dataframe()` too: one row per sign with
`label`, `glyph`, `codepoint`, `phonetic`, and each sign's `attrs` spread into
columns.

---

## The query engine

`filter()` does exact metadata matching; the **query engine** does everything
else: text/prefix/suffix/sign-pattern/co-occurrence predicates with AND / OR /
NOT, returning either inscriptions or `(word, count)` pairs. It's a faithful port
of the Linear A Research Workbench's query engine, so results match the browser
tool.

A query is a list of `FilterRow`s. Each row names a `field`, a `value`, an
optional `connector` (`"and"` default, or `"or"`), and an optional `negate`.

### The fields

The full registry is `aegean.analysis.FIELDS`. Inscription-scope rows select
documents; word-scope rows select words within them.

| Field id | Label | Scope | Value kind |
|---|---|---|---|
| `id-contains` | Inscription ID contains | inscription | text |
| `site-is` | Site is | inscription | site |
| `scribe-is` | Scribe is | inscription | scribe |
| `period-is` | Period is | inscription | period |
| `support-is` | Support is | inscription | support |
| `has-image` | Has facsimile image | inscription | boolean |
| `has-annotation` | Has annotation | inscription | boolean |
| `ins-contains-word` | Contains exact word | inscription | word |
| `word-contains` | Word contains text | word | text |
| `word-prefix` | Word starts with | word | text |
| `word-suffix` | Word ends with | word | text |
| `word-min-syllables` | Word has ≥ N signs | word | number |
| `word-max-syllables` | Word has ≤ N signs | word | number |
| `word-contains-sign` | Word contains sign | word | sign |
| `word-cooccurs-with` | Word co-occurs with | word | word |
| `word-sign-pattern` | Word matches sign pattern | word | text |

### Running a query

```python
import aegean
from aegean.analysis import FilterRow

c = aegean.load("lineara")

# inscriptions from Haghia Triada that contain a word starting with KU
res = c.query([
    FilterRow("site-is", "Haghia Triada"),
    FilterRow("word-prefix", "KU"),
], output="inscriptions")

print(len(res.inscriptions))           # 55
print(res.description)                 # Site is: Haghia Triada · Word starts with: KU
```

Switch `output="words"` to get ranked `(word, count)` pairs instead:

```python
res = c.query([FilterRow("word-prefix", "KU")], output="words")
print(len(res.words), res.words[:5])
# 33 [('KU-RO', 34), ('KU-PA₃-NU', 7), ('KU-NI-SU', 5), ('KU-PA', 4), ('KU-MI-NA-QE', 2)]
```

`negate=True` flips a row; `connector="or"` ORs it with the running result
within its scope:

```python
# words with ≥ 3 signs that do NOT contain "PA"
res = c.query([
    FilterRow("word-min-syllables", 3),
    FilterRow("word-contains", "PA", negate=True),
], output="words")
print(len(res.words), res.words[:3])
# 543 [('A-TA-I-*301-WA-JA', 11), ('JA-SA-SA-RA-ME', 7), ('SI-RU-TE', 7)]
print(res.description)
# Word has ≥ N signs: 3 · NOT Word contains text: PA
```

A `QueryResults` carries the corpus's provenance and a one-line filter summary,
so it cites the **exact result set**: `res.cite("plain" | "bibtex" | "apa")`.

### Saving a query as a reusable corpus

`QueryResults.to_corpus(source)` turns an `output="inscriptions"` result back
into a `Corpus`: the matched inscriptions, carrying `source`'s sign inventory
and script id, with a `subset:` provenance note that names the query. From there
it's an ordinary corpus: serialize it, query it again, hand it to any tool.

```python
import aegean
from aegean.analysis import FilterRow

c = aegean.load("lineara")
res = c.query([FilterRow("site-is", "Haghia Triada"),
               FilterRow("word-prefix", "KU")], output="inscriptions")
sub = res.to_corpus(c)
print(len(sub))                        # 55
sub.to_json("ku_at_ht.json")           # now a reusable corpus on disk
```

(A `words`-only result has no inscriptions, so it yields an empty corpus: query
with `output="inscriptions"` if you want to save the slice.)

From the shell, `aegean query ... -o out.json|.db` does the same: it writes the
matched inscriptions as a corpus (inscriptions output only):

```bash
aegean query lineara --where site-is="Haghia Triada" --where word-prefix=KU \
                     -o ku_at_ht.json
# wrote 55 inscriptions to ku_at_ht.json
```

### From the shell

`aegean query` mirrors all of this. Each `--where field=value` is ANDed with the
previous row; prefix the field with `or:` to OR it, or `!` to negate it. List the
fields with `--fields`.

```bash
aegean query lineara --fields                       # the table above
aegean query lineara --where site-is="Haghia Triada" \
                     --where word-prefix=KU \
                     --output-kind words --limit 5
```
```
Site is: Haghia Triada · Word starts with: KU → 25 word(s)
┌──────────────┬───────┐
│ word         │ count │
├──────────────┼───────┤
│ KU-RO        │ 32    │
│ KU-PA₃-NU    │ 6     │
│ KU-NI-SU     │ 5     │
│ KU-MI-NA-QE  │ 2     │
│ KU-PA₃-NA-TU │ 2     │
└──────────────┴───────┘
Godart, L. & Olivier, J.-P. (1976–1985). … [query: Site is: Haghia Triada · …]
```

(There's also a simpler `aegean search CORPUS "KU-*-RO"` for one-off wildcard
sign-pattern lookups, where `*` matches any one sign: see
[Analysis](Analysis).)

---

## SQLite persistence (`aegean.db`)

For a queryable, on-disk corpus, write it to SQLite: stdlib `sqlite3` only, no
extra dependency. Documents and tokens become normalized rows (so SQL and
full-text search work over them); the nested structure (signs, alternate
readings, annotations, line groupings, image refs, notes) is kept in JSON
columns; provenance and the sign inventory live in a small key/value `meta`
table. It's a lossless round-trip.

```python
import aegean, aegean.db as db
c = aegean.load("lineara")

c.to_sql("lineara.db")                 # FTS5 text index by default
c2 = aegean.Corpus.from_sql("lineara.db")
print(c.fingerprint() == c2.fingerprint())   # True

# full-text search (matches a literal token/phrase — hyphens are fine)
db.search("lineara.db", "KU-RO", limit=3)
# [('HT9a', 25, 'KU-RO'), ('HT9b', 20, 'KU-RO'), ('HT11a', 7, 'KU-RO')]

# stream documents one at a time for a huge DB, without loading the whole corpus
for doc in db.stream("lineara.db"):
    ...
```

The schema is two main tables (`documents`, `tokens`) with indices on
`tokens(doc_id)` and `tokens(text)`, plus a `tokens_fts` FTS5 virtual table when
the local SQLite build supports it (search falls back to `LIKE` if it doesn't).

From the shell, `aegean db` is its own subcommand group:

```bash
aegean db build lineara -o lineara.db          # add --no-fts to skip the index
# wrote 1721 documents to lineara.db

aegean db search lineara.db KU-RO --limit 3
```
```
   'KU-RO' in lineara.db
┌───────┬─────┬───────┐
│ doc   │ pos │ text  │
├───────┼─────┼───────┤
│ HT9a  │ 25  │ KU-RO │
│ HT9b  │ 20  │ KU-RO │
│ HT11a │ 7   │ KU-RO │
└───────┴─────┴───────┘
```

You can also reach SQLite through the unified exporter: `aegean export CORPUS -f
sqlite -o lineara.db`.

### Appending to an existing database

`to_sql(..., append=True)` (and `db.to_sqlite(..., append=True)`) **upserts**
documents into a database that already exists: a document whose id is already
present is replaced, new ids are added, and the FTS index is refreshed so search
sees the change. It's how you grow a database incrementally without rebuilding.

```python
import aegean, aegean.db as db
a = aegean.Corpus.from_records([{"id": "A1", "text": "KU-RO 10"}], script_id="lineara")
b = aegean.Corpus.from_records([{"id": "A1", "text": "A-DU 5"},     # same id → replaced
                                {"id": "B1", "text": "SA-RA2 3"}],  # new id  → added
                               script_id="lineara")

a.to_sql("corpus.db")                  # build
db.to_sqlite(b, "corpus.db", append=True)   # or b.to_sql("corpus.db", append=True)

back = aegean.Corpus.from_sql("corpus.db")
print(sorted(d.id for d in back))      # ['A1', 'B1']
print(back.get("A1").tokens[0].text)   # 'A-DU'  (the appended copy won)
db.search("corpus.db", "A-DU")         # [('A1', 0, 'A-DU')]  (FTS refreshed)
```

The CLI mirror is `aegean db add SRC -o existing.db`, where `SRC` is any
`read_corpus` spec:

```bash
aegean db build  tlg0012.tlg001 -o homer.db   # the Iliad
aegean db add    tlg0012.tlg002 -o homer.db   # add the Odyssey, in place
# added/updated <n> documents in homer.db
```

(The local-only version of the same operation, on bundled subsets, prints e.g.
`added/updated 53 documents in homer.db`.)

---

## Import and export adapters (`aegean.io`)

`aegean.io` is the corpus model's two-way bridge to outside formats. The
**import** side builds a `Corpus` from your own plain material:
`from_text` / `from_text_file` / `from_text_dir` / `from_csv` (a string, a
`.txt` file, a folder of text files, or a CSV), so you get the full
filter/query/analyse/export API without writing `Corpus.from_records` by hand.
The **export** side turns a `Corpus` back into interchange formats other tools
speak. See [Your own corpus](Data-and-Provenance#your-own-corpus) for the import
walkthrough (and the `aegean import` CLI); the export set, and how to reach each
one:

| Format | Python | CLI | Lossless? | Extra needed |
|---|---|---|---|---|
| Lossless JSON | `Corpus.to_json` | `export -f json` | yes | none |
| CSV | `io.to_csv` | `export -f csv` | tabular view | `[data]` |
| Parquet | `io.to_parquet` | `export -f parquet` | tabular view | `[parquet]` |
| EpiDoc TEI XML | `io.to_epidoc` / `io.write_epidoc` | `export -f epidoc` | content EpiDoc preserves | none (writing) |
| SQLite DB | `Corpus.to_sql` / `db.to_sqlite` | `export -f sqlite` | yes | none |
| Workbench JSON | `io.to_workbench` / `io.from_workbench_export` | `aegean workbench` (serves the app) | tokenized text + surface forms | none |

The one command that covers the file formats:

```bash
aegean export CORPUS -f {json|csv|parquet|epidoc|sqlite|workbench} -o PATH [--level …] \
              [--site …] [--period …] [--scribe …] [--support …]
```

The `--site/--period/--scribe/--support` filters apply before export, so you can
export exactly the subset you want, and the provenance records the filter.

### EpiDoc TEI XML

`to_epidoc(document)` serializes one `Document` to an EpiDoc TEI XML string;
`write_epidoc(obj, path)` writes a `Document` to a file or a whole `Corpus` to a
directory of `{id}.xml` files. The transliteration lives in a TEI `<div
type="edition">` as `<lb/>`-delimited lines of `<w>` (words), `<num>`
(numerals), and `<g>` (logograms); a token whose `ReadingStatus` isn't `CERTAIN`
is wrapped in the matching apparatus element (`<unclear>` / `<supplied>`), and
alternates become `<app><lem>…</lem><rdg>…</rdg></app>`. The writer uses the
stdlib XML module (lazy-imported), so **EpiDoc export needs no extra**.

```python
import aegean
from aegean.io import to_epidoc
xml = to_epidoc(aegean.load("lineara").get("HT13"))
print(xml[:300])
# <?xml version='1.0' encoding='UTF-8'?>
# <TEI xmlns="http://www.tei-c.org/ns/1.0">
#   <teiHeader>
#     <fileDesc>
#       <titleStmt>
#         <title>HT13</title>
#       ...
```

The edition div is tagged with a BCP-47 `xml:lang` per script (`und`
undetermined for the undeciphered scripts, `grc` Greek, `gmy` Mycenaean Greek):

| script id | `xml:lang` |
|---|---|
| `lineara` | `und` |
| `linearb` | `gmy` |
| `cypriot` | `grc` |
| `cyprominoan` | `und` |
| `greek` | `grc` |

The output validates against the EpiDoc RelaxNG schema and round-trips through the
EpiDoc *reader* (which lives in `aegean.scripts.linearb.parse_epidoc` and needs
the `[epidoc]` extra / lxml) for the content EpiDoc preserves: id, find-place,
and the token/line stream. The reader re-derives token kinds from the text, so a
written corpus reloads with the same words, numerals, logograms, separators, and
lines.

### The Linear A Research Workbench

The corpus model round-trips with the [Linear A Research
Workbench](https://linearaworkbench.xyz/) (the browser UI) in both directions,
over plain JSON; neither tool needs the other installed.

```python
import aegean
from aegean.io import to_workbench, from_workbench_export

c = aegean.load("lineara").filter(site="Haghia Triada")

# emit workbench-shaped inscription records (optionally write a JSON file)
recs = to_workbench(c, "ht.workbench.json")
sorted(recs[0].keys())
# ['context', 'facsimileImages', 'findspot', 'glyphs', 'id', 'imageRights',
#  'imageRightsURL', 'images', 'lines', 'name', 'scribe', 'site', 'support',
#  'transcription', 'translations', 'words']

# load what the workbench produces (its Data Export, or a plain records array)
c2 = from_workbench_export("ht.workbench.json")
print(len(c2), "|", c2.provenance.source)
# 1110 | linearaworkbench corpus export
```

Point the app's `?corpus=<url>` (or its *Data Export → Bring your own corpus*
picker) at a `to_workbench` file and every analysis module runs against your
data. `from_workbench_export` accepts the schema-v1 full-corpus export object
(records under `"inscriptions"`, provenance under `"_meta"`, per-record
`"derived"` analyses: ignored) or a plain array of records; image *files* are
never embedded, only references. The `aegean workbench` CLI command fetches the
app's static build to your cache and serves it locally so you can run the whole
UI offline; see the [CLI](CLI) page.

---

## Saving results and AI outputs (`--output`)

The corpus exporters above turn a *corpus* into a file. 0.8.2 adds the same
`--output/-o` convenience to the **analysis and AI commands**, so a result
(not just the data behind it) lands on disk. The format is chosen by the file
extension, all on the stdlib (no pandas needed): `.json` (structured), `.csv`
(tabular), or `.txt` (plain text). Which extensions a command accepts depends on
the shape of its result.

| Command | `-o` writes | Extensions |
|---|---|---|
| `aegean stats` / `keyness` / `dispersion` / `search` | the result table | `.json` / `.csv` / `.txt` |
| `aegean analyze {assoc,cooccur,clusters,hands}` | the analysis result | `.json` / `.csv` / `.txt` |
| `aegean ai {translate,gloss,summarize,hypotheses,ask,extract}` | the AI result | `.json` / `.txt` |

```bash
# a frequency table straight to CSV (stdlib csv, no pandas)
aegean stats lineara --top 3 -o freq.csv
```
```
item,count
KU-RO,37
SA-RA₂,20
KI-RO,16
```

For the AI commands, `.json` keeps the **whole** result: the generated text,
its provenance, and the local grounding that fed the model, while `.txt` writes
the labeled text. The exploratory label travels onto disk either way, so a saved
reading can never be mistaken for ground truth:

```bash
aegean ai translate "ἐν ἀρχῇ" -o reading.json   # text + provenance + grounding
aegean ai gloss     "ἐν ἀρχῇ" -o gloss.txt       # labeled text
```

### `ExploratoryResult` — the serialized AI result

Under the hood every AI capability returns an `ExploratoryResult` (in
`aegean.ai`): the generated `text`, the `provider` / `model` / `prompt_version`
that produced it, the structured `grounding` it was given (each a `GroundingItem`
with a `source` and `ref`), an always-explicit `exploratory` flag, and an
optional parsed `data` payload for the structured capabilities. Three methods
move it to and from disk:

| Method | Does |
|---|---|
| `to_dict()` | a stable, JSON-ready dict: keeps `text`, `grounding`, `exploratory`, and any `data`, plus a `_meta` stamp |
| `to_json(path=None)` | the dict as a JSON string, or written to `path` |
| `from_dict(data)` *(classmethod)* | reconstruct an `ExploratoryResult` from `to_dict` output |

```python
from aegean.ai import ExploratoryResult, GroundingItem

r = ExploratoryResult(
    text="A possible reading of KU-RO as a total.",
    kind="translate", provider="anthropic", model="claude-x", prompt_version="v1",
    grounding=(GroundingItem("KU-RO = total marker", source="lexicon", ref="lineara"),),
)
d = r.to_dict()
sorted(d.keys())
# ['_meta', 'data', 'exploratory', 'grounding', 'kind', 'model', 'prompt_version', 'provider', 'text']
d["_meta"]
# {'tool': 'pyaegean', 'type': 'ExploratoryResult', 'schemaVersion': 1}
d["exploratory"]                       # True — the caveat is part of the data

r2 = ExploratoryResult.from_dict(d)    # round-trips
r2.text == r.text                      # True
r2.grounding[0].source                 # 'lexicon'
```

`labeled()` returns the text with its exploratory caveat prefixed (use it when
surfacing to a user), and `trace()` renders the grounding provenance: both are
methods, not fields. The point of the round-trip is that the `exploratory` flag
and the grounding **persist**: read a saved AI output back and it still knows it
was generative and still names the local facts that grounded it.

---

## Provenance and citation

Every bundled corpus carries a `Provenance` (source, license, citation, URL)
that travels with it and is stamped into exports. This is the structural backbone
of pyaegean's "single source of truth" promise: an analysis can always say where
its data came from.

`Corpus.cite(style)` cites the corpus, or (after a `filter`) the exact subset,
since `filter` records a `subset:` note that all three styles include:

```python
import aegean
c = aegean.load("lineara")
print(c.cite("plain"))
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz

print(c.cite("bibtex"))
# @misc{lineara-corpus,
#   title = {Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.},
#   year = {1976},
#   url = {https://github.com/mwenge/lineara.xyz},
#   note = {License: Apache-2.0 …. Accessed via pyaegean},
# }
```

| `style` | Produces |
|---|---|
| `"plain"` | one citation line (with any `subset:` / query note in brackets) |
| `"bibtex"` | a `@misc` entry (`title`, `year` if recoverable, `url`, `note`) |
| `"apa"` | an APA-style reference line (`n.d.` when no year is found) |

```bash
aegean cite lineara --style bibtex
aegean cite lineara --site "Haghia Triada"     # cites the subset
```

`QueryResults.cite(...)` does the same for a query's exact result set. The BibTeX
and APA forms are best-effort renderings of the recorded free-text provenance:
the first plausible year in the citation string becomes `year`, and the license
plus any notes go into `note`/brackets. See
[Data and Provenance](Data-and-Provenance) for where each corpus comes from and
its license.

---

## Scripts are plugins

A writing system is a plugin the core knows only by interface (`aegean.core.script.Script`):

```python
from aegean.core.script import Script, register

class MyScript(Script):
    id = "myscript"
    name = "My Script"

    @property
    def sign_inventory(self): ...
    def tokenize(self, raw: str): ...

register(MyScript())
```

A corpus loader is registered separately via
`aegean.core.corpus.register_loader(script_id, fn)` so `aegean.load(script_id)`
works. The core never imports scripts (no cycles); `aegean/__init__` imports
`scripts` to register the built-ins (Linear A, Linear B, Cypriot, Cypro-Minoan,
Greek).

Access registered scripts and their behaviour:

```python
import aegean
aegean.registered_scripts()
# ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']

g = aegean.get_script("greek")
print(len(g.sign_inventory))           # 25  (the Greek alphabet)
[(t.text, t.kind.value) for t in g.tokenize("ἐν ἀρχῇ")]
# [('ἐν', 'word'), ('ἀρχῇ', 'word')]
```

`SignInventory` indexes a script's signs three ways for O(1) lookup:

```python
inv = aegean.load("lineara").sign_inventory
inv.by_label("KU")        # the Sign labelled KU
inv.by_glyph("𐙂")        # the same Sign by its Unicode glyph
inv.by_codepoint(0x10642) # …or by codepoint
len(inv)                  # 344
```

```bash
aegean sign lineara KU       # look one sign up: glyph, codepoint, sound value, attrs
```

---

## Numerals and accounting (`aegean.core.numerals`)

The numeral layer parses the decimal numerals and metrological fractions that
appear on tablets, and reconciles `KU-RO` / `PO-TO-KU-RO` totals against summed
line items. It's a verbatim port of the workbench's numeral library, so results
match the TypeScript tool against shared golden fixtures.

```python
from aegean.core.numerals import parse_value, format_value
parse_value("10")        # 10
parse_value("¹⁄₂")       # 0.5  (super/subscript fraction)
parse_value("½")         # 0.5  (precomposed glyph)
format_value(130.5)      # '130½'
```

Total-marker recognition is among the most secure lexical identifications in
Aegean accounting:

| Script | Total | Grand total | Deficit |
|---|---|---|---|
| Linear A | `KU-RO` | `PO-TO-KU-RO` | `KI-RO`, `KU-RO₂` |
| Linear B | `TO-SO`, `TO-SA` |— | `O-PE-RO`, `O-PE-RO-SI` |

The reconciliation (`check_balances`, and `analysis.balance_check` /
`aegean balance`) is an **exploratory** reading: section boundaries are
heuristic and the metrology is scholarly-contested. It's labeled as such wherever
it surfaces. See [Analysis](Analysis) for the full accounting walkthrough.

---

## Conventions and design rules

- **The core has zero hard third-party deps.** pandas (the `[data]` extra) and
  the provider SDKs are lazy-imported inside functions; collocation stats are
  pure stdlib. So `import aegean` is instant and loads nothing heavy, and the
  whole data model above works on a bare install.
- **No large/binary assets are bundled**: that's what the
  [download-to-cache](Data-and-Provenance) layer is for. CI's
  `scripts/check_footprint.py` enforces import-clean, import-fast, and a
  code+JSON-only wheel.
- **One schema version.** Exports stamp `schemaVersion` (currently `1`) so
  consumers can tell what they're reading; `to_json` omits default fields (e.g.
  a `CERTAIN` status) to stay compact and back-compatible.
- **Every exploratory method carries its caveat.** Cross-linguistic distance,
  morphology clustering, accounting reconciliation, decipherment, and AI readings
  are labeled unverified at point of use. The Linear A material is undeciphered:
  analysis is never presented as ground truth.

## Limitations and notes

- `to_dict` is deliberately **lossy** (words + metadata only); for anything you
  need to reconstruct, use `to_json`/`from_json` or the SQLite round-trip.
- EpiDoc export is lossless only for **what EpiDoc preserves**: the id,
  find-place, token/line stream, and editorial certainty. The *reader* re-derives
  token kinds from text and needs lxml (the `[epidoc]` extra).
- The query engine's word predicates operate on **multi-sign words** (tokens
  containing a `-`); single-sign tokens and logograms are matched by the
  inscription-scope predicates, not the word-scope ones.
- Parquet needs a parquet engine; CSV/Parquet need pandas (`[data]`).
- See [Limitations](Limitations) for the honest, project-wide list of what
  pyaegean does and doesn't claim, and [Greek NLP](Greek-NLP) /
  [Meters](Meters) for the layers above the core.
