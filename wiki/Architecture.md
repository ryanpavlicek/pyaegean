# Architecture

This page covers pyaegean's core data model (the script-agnostic value objects
shared by every script and analysis module) and the five core operations on a
corpus: serialization (lossless JSON, SQLite, and portable research bundles),
tabular export (DataFrames, CSV, Parquet), querying, citation, and external
interchange (EpiDoc, RDF, and the Linear A Research Workbench). For an
introductory walkthrough, start with [Tutorial](Tutorial) and
[Analysis](Analysis).

Examples below were executed against the installed package with real outputs.
Where a feature has both a Python API and a CLI command, both are shown.

Typed source alignment, typed editorial form states, lossless CoNLL-U structure,
and schema-3 JSON/SQLite persistence are built into the core model. Every `aegean`
CLI corpus argument resolves any source through
[`aegean.read_corpus`](#aegeanread_corpus-universal-source-resolver): a
registered corpus id, a Greek work id, a saved `.json` or `.db` path, or `-` for
JSON on stdin. Corpora can be combined, sliced, and persisted from Python or the
shell ([Combining and slicing corpora](#combining-and-slicing-corpora)).

## The layered design

### Interoperability is a projection boundary

The complete `UDDocument` row stream forms the structural core. `aegean.io` wraps
it in an `InteropDocument` carrying exact source alignment, typed form state,
confidence, receipts, profile identity, and provenance when present. Exporters
populate native target fields and store remaining fields in a canonical
`aegean.interop/v1` sidecar. `InteropReport` distinguishes native, sidecar-held,
and genuinely lost fields; strict reimport validates the native projection and
sidecar together. spaCy, Stanza, and CLTK remain optional extras excluded from
`[all]`.

pyaegean groups its modules into seven conceptual layers. Translation combines
Greek analysis and the AI layer; this diagram summarizes module responsibilities
rather than strict import order. The script-agnostic core never imports a script
plugin.

```
L7  interfaces            cli (aegean CLI & REPL) · tui (aegean tui, including
                          tui/screens/review.py + tui/_review_data.py) ·
                          mcp_server (aegean-mcp) · library (aegean.library
                          unified pack/corpus/work/model manager); shared views
                          in aegean._view keep surfaces aligned
L6  ai (aegean.ai)        provider-agnostic LLM clients + grounded capabilities
L5  translate             hybrid: lexicon/morphology grounding -> LLM
L5  greek (aegean.greek)  Greek NLP pipeline + aegean.greek.bible (9 NT editions,
                          13 early witnesses, Strong's, 55 LXX books, 86 commentaries)
L4  io · bundle · geo     aegean.io (text/CSV/EpiDoc/CoNLL-U/interop) ·
    · viz · data · cache  aegean.bundle (zero-dep portable research bundles) ·
    · db                  aegean.geo · aegean.viz · aegean.data (39 pinned remote
                          assets) · aegean.cache · aegean.db (SQLite + resumable jobs)
L3  analysis              distance · align · morphology · collocation · patterns
                          · query · accounting · structure
L2  scripts (plugins)     lineara · linearb · cypriot · cyprominoan · greek
L1  core                  Corpus · Document · Token · Sign · SignInventory ·
                          Numeral · Script(ABC) · Registry · Provenance
```

The Greek layer (L5) hosts the opt-in backends: the AGDT treebank
(`treebank.py`), LSJ and multi-dictionary glossing (`lexicon.py`), dependency
parser (`syntax.py`), POS tagger (`tagger.py`), lemmatizers (`lemmatizer.py`,
`paradigms.py`, and the neural seq2seq backend `neural_lemmatizer.py`), and the
neural joint pipeline (`joint.py`, with `mst.py` arc decoding, `udfeats.py` FEATS
rendering, `lemma_rerank.py` opt-in OOV lemma reranking, and `documentary.py`
post-processing). These backends fetch and build their artifacts through L4
`data`/`cache`, preserving downward layering. See [Greek NLP](Greek-NLP).

`import aegean` loads zero third-party packages. pandas, lxml, provider SDKs,
matplotlib, and Textual are lazy-imported inside the functions that need them
behind optional [extras](Installation), so the core data model works on a bare
Python installation.

### Sentence segmentation is a validated seam

Document sentence segmentation is separate from model inference. `segment_text()`
applies a named rule policy (`default`, `prose`, `verse`, `inscription`, or
`papyrus`) and returns immutable, source-preserving boundaries. `segmenter=`
accepts an edition-specific callback or `SentenceSegmenter` implementation.
Results are normalized and verified for complete non-whitespace coverage,
ordering, bounds, and non-spoofed policy identity. Tokenization rejects spans
that bisect tokens before analysis uses them. Built-in boundaries are
deterministic rules rather than calibrated confidence scores; a custom segmenter
may attach finite confidence metadata.

This seam stays independent of script plugins and model runtimes. Per-call
`sentence_policy` governs how raw or typed text is split. By contrast,
`GreekPipelineConfig.segmentation` records the backend's versioned preprocessing
identity (`pyaegean-punctuation-v1` for baseline; copied from
`ModelBundleManifest`, `pretokenized` for `grc-joint-v3`, for neural instances).
The neural model receives pre-split word lists and never chooses document
boundaries. Configuration schema 2 records the explicit runtime-variant label,
registry digest, and qualification/award digests; restoring a configuration
rejects registry drift or unavailable labels before loading weights, and distinct
variants use separate cache keys.

### Confidence is a separate evidence layer

`aegean.greek.confidence` is a standard-library contract shared by the neural
pipeline, tabular views, and the CLI. `use_calibration_registry()` loads the
bundled schema-2 `CalibrationRegistry` (`calibration_registry_v2.json`), keyed by
model, task, lemma source path, and optional domain (`literary` and
`documentary_native` across all six tasks, fitted on held-out dev data and
qualified on locked test folds). Exact entries take precedence; fallback entries
are marked as fallback instead of exact evidence. `TokenConfidence` and
`SentenceConfidence` carry either a scoped calibrated value (with calibration
hash, sample count, and measured ECE/Brier metrics) or a stable unavailable
reason. Legacy flat confidence fields remain untouched for compatibility.

`AbstentionPolicy` is caller-owned: callers supply thresholds and the policy's
canonical SHA-256 travels with `accept`/`review`/`unavailable` decisions. The
runtime ships no default threshold and infers no OOD warnings. For the canonical
runtime, schema-4 `AnalysisReceipt` records calibration and policy hashes,
runtime variant and registry digests, and composed output/post-processing
identity. Schemas 1 through 3 remain readable for hosted evidence without
fabricating newer fields.

---

## The core model (`aegean.core`)

The core model consists of frozen `@dataclass(slots=True)` value objects. A
Linear A syllabogram and a Greek letter are both `Sign` instances; a `KU-RO`
entry and a Greek word are both `Token` instances. `aegean.core.model` knows
nothing about individual writing systems; script-specific logic lives in
[script plugins](#scripts-are-plugins).

All core types are importable from the top-level package:

```python
import aegean
from aegean import (
    Corpus, Document, DocumentMeta,
    Token, TokenKind, SourceAlignment, Sign, SignInventory,
    Provenance, ReadingStatus, Script,
)
```

### Core objects

| Object | Role | Key fields / methods |
|---|---|---|
| **`Sign`** | one graphic unit (syllabogram, letter, logogram) | `label`, `glyph`, `codepoint`, `phonetic`, `script_id`, `attrs` |
| **`Token`** | one unit in a document's text stream | `text`, `kind`, `signs`, `glyphs`, `line_no`, `position`, `status`, `alt`, `annotations`, optional `alignment` and `form_state` |
| **`TokenFormState`** | typed source, editorial, and model forms for one token | `diplomatic`, optional `regularized` / `normalized` / `model_input`, ordered `segments`, model-input provenance |
| **`FormSegment`** | one ordered span inside a typed form | text, `ReadingStatus`, optional `SourceMarkupRef` |
| **`SourceMarkupRef`** | semantic reference to source markup | source id, path, tag, ordered attributes (never raw XML byte offsets) |
| **`SourceAlignment`** | immutable mapping to exact source text | document/sentence/token IDs, original and normalized text, half-open character span, whitespace, normalization ops |
| **`Document`** | one inscription, tablet, or text | `id`, `script_id`, `tokens`, `lines`, `meta`, optional exact `source_text`; properties `.words`, `.numerals`, `.logograms`, `.line_tokens` |
| **`DocumentMeta`** | bibliographic and archaeological metadata | `site`, `support`, `scribe`, `findspot`, `period`, `name`, `images`, `notes` |
| **`Corpus`** | collection of documents, inventory, and provenance | `.load()`, `.get()`, `.filter()`, `.query()`, `.word_frequencies()`, `.to_dataframe()`, `.to_json()`, `.cite()` |
| **`SignInventory`** | indexed table of a script's signs | `by_label()`, `by_glyph()`, `by_codepoint()`, `to_dataframe()` |
| **`Provenance`** | source, license, and citation metadata | `cite()`, `bibtex()`, `apa()` |

### `Sign`

Represents one graphic unit of a script. `attrs` holds script-specific metadata
without coupling the core to any writing system:

```python
import aegean
inv = aegean.load("lineara").sign_inventory
ku = inv.by_label("KU")
print(ku.label, ku.glyph, hex(ku.codepoint), ku.phonetic)
print(ku.attrs)
# KU 𐙂 0x10642 ku
# {'sharedWithLinearB': True, 'linearAOnly': False, 'total': 29, 'confidence': 1, 'altGlyphs': []}
```

### `Token` and `TokenKind`

A token stores its transliteration (`text`), decomposed `signs`, and document
location (`line_no`, `position`). Its `kind` is a `TokenKind`:

| `TokenKind` | Value | Meaning |
|---|---|---|
| `WORD` | `"word"` | lexical word, including single-sign Aegean and alphabetic Greek words |
| `LOGOGRAM` | `"logogram"` | ideogram or commodity sign |
| `NUMERAL` | `"numeral"` | decimal numeral or metrological fraction |
| `SEPARATOR` | `"separator"` | word or entry divider (such as 𐄁) |
| `PUNCT` | `"punct"` | punctuation in alphabetic scripts |
| `UNKNOWN` | `"unknown"` | unclassified token |

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

Two additional fields store epigraphic and linguistic metadata:

- **`annotations`**: a `dict[str, str]` for arbitrary per-token facts. The Greek
  New Testament stores `lemma`, `morph`, `strongs`, `gloss`, `normalized`,
  `upos`, and `ref` here, which spread automatically into token-level DataFrames
  and CSV/Parquet exports.
- **`status`** and **`alt`**: editorial reading certainty and variant readings.

Linguistic review decisions also live in `annotations`, separate from editorial
`ReadingStatus`. Review tables record per-field `accept`, `correct`, `defer`, and
`reject` decisions for lemma, POS, and morphology (plus head and deprel where
present). Accepting a prediction keeps its prediction source and marks that field
verified; correcting a lemma records `lemma_source=user`. Blank cells never
approve predictions. Reviewer identity, notes, evidence, and `review_history`
persist across JSON and SQLite round-trips, and re-running `annotate_corpus()`
marks superseded lemma/POS decisions stale. Reviewing one field never certifies
another. See [Validation and Review](Validation-and-Review).

### Editorial certainty (`ReadingStatus`) and alternates

`Token.status` preserves Leiden/EpiDoc reading certainty across round-trips.
`CERTAIN` is the default; damaged, restored, and lost states map directly to
EpiDoc markup:

| `ReadingStatus` | Value | EpiDoc | Leiden |
|---|---|---|---|
| `CERTAIN` | `"certain"` | (plain text) | securely read |
| `UNCLEAR` | `"unclear"` | `<unclear>` | underdot |
| `RESTORED` | `"restored"` | `<supplied reason="lost">` | `[ ]` |
| `LOST` | `"lost"` | `<supplied reason="undefined">` (reader also accepts `<gap>`) | `[---]` |

`Token.alt` stores alternate readings (`<app>`/`<rdg>` in EpiDoc), with `text`
holding the lemma. Bundled transcriptions are mostly `CERTAIN`, whereas imported
EpiDoc corpora populate both `status` and `alt`, and the
[EpiDoc writer](#epidoc-tei-xml) serializes them back out.

### Typed editorial forms and model input

A token may carry `TokenFormState`: `diplomatic` holds the diplomatic surface
form, `regularized` holds an editorial regularization or expansion, and
`normalized` holds an optional preprocessing form. `segments` preserve ordered
certain, supplied, unclear, and lost pieces with semantic `SourceMarkupRef`
pointers. `model_input` records the exact string passed to an analyzer along with
`model_input_source` and ordered operations; it documents computation rather than
altering the edition text.

`greek.pipeline_tokens()` selects an explicit `model_input` first, then
`regularized`, `normalized`, `diplomatic`, and finally legacy `Token.text`. The
returned `TokenRecord` retains both the state and the chosen input. Token-carrier
EpiDoc `<choice>` and `<app>` elements populate `TokenFormState`; the six hosted
epigraphy and papyri corpora remain legacy aggregate-status datasets without
populated `TokenFormState`.

### `Document`

Represents one inscription, tablet, or text. `lines` stores physical lines as
lists of indices into `tokens`, and convenience properties filter the token
stream:

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
| `.line_tokens` | tokens grouped by physical line |
| `len(doc)` | total token count |

In Jupyter, `Document`, `Corpus`, and `SignInventory` render as HTML cards
displaying line-by-line tokens, metadata, and token counts.

### `Corpus`

A `Corpus` groups a list of documents with a shared `SignInventory` and
`Provenance`. Load registered corpora with `aegean.load`:

```python
import aegean
c = aegean.load("lineara")            # or Corpus.load("lineara")
print(len(c))                         # 1721
print(c.get("HT13").id)               # HT13
```

Inspect a corpus from the shell with `aegean info`:

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
│ signs_in_inventory │ 342                                                    │
│ source             │ GORILA (Godart & Olivier 1976–1985) via …              │
│ license            │ Apache-2.0 (corpus JSON); facsimile imagery © …        │
│ citation           │ Godart, L. & Olivier, J.-P. (1976–1985). …             │
└────────────────────┴──────────────────────────────────────────────────────┘
```

`filter()` returns a new corpus matching all metadata predicates (AND-combined)
and appends a `subset:` note to provenance so citations identify the exact slice:

```python
c = aegean.load("lineara").filter(site="Haghia Triada")
print(len(c))                          # 1110
```
```bash
aegean load lineara --site "Haghia Triada" --limit 5
```

Lazy iterators avoid building intermediate token lists on large corpora:

```python
c = aegean.load("lineara")
c.word_frequencies()[:3]
# [('KU-RO', 37), ('SA-RA₂', 20), ('KI-RO', 16)]
next(iter(c.iter_words()))             # 'QE-RA₂-U'
# iter_documents() yields a list_iterator over materialized documents;
# iter_tokens() and iter_words() are generators.
```

Neural analysis provides a separate streaming API over pre-tokenized sentences:

```python
from aegean import greek

greek.use_neural_pipeline()
analyses = greek.iter_analyze_sentences(sentence_source(), batch_size=8)
for analysis in analyses:              # ordered, receipt-bearing, bounded memory
    persist(analysis)
```

`iter_analyze_sentences()` holds at most one batch plus the longest sentence in
flight and freezes the backend configuration before reading the input iterator.
`analyze_sentences()` collects the same engine into a list. Raw-text `pipeline()`,
`annotate_corpus()`, and CoNLL-U helpers retain their collecting contracts.

Every corpus computes a deterministic **fingerprint**: a content hash covering
script id, document ids, token text, kind, editorial status, decomposed signs,
glyphs, alternate readings, annotations, and any `subset:` note. The opt-in
[analysis cache](Analysis) uses this fingerprint as its cache key:

```python
c = aegean.load("lineara")
c.fingerprint()[:16]                   # 'f2619ca5089e533a'
c.cache_key() == c.fingerprint()       # True (cache_key is an alias)
```

### `aegean.read_corpus` (universal source resolver)

`aegean.load(id)` resolves registered ids only. `aegean.read_corpus(spec)` is the
general resolver used by every CLI corpus argument. Resolution order:

1. `"-"` reads JSON from stdin; an inline string starting with `{` is parsed as
   `Corpus.to_json` output.
2. Exact registered corpus id (`"lineara"`, `"damos"`, `"nt"`, …); registered ids
   take precedence over same-named files.
3. Greek work id (such as `"tlg0012.tlg001"`), fetched via
   `aegean.greek.load_work` and cached locally.
4. File path: `.json` via `Corpus.from_json`; `.db`, `.sqlite`, or `.sqlite3` via
   `Corpus.from_sql`.

Unmatched inputs raise `CorpusNotFound` (a `ValueError` subclass) listing valid
forms.

```python
import aegean
aegean.read_corpus("lineara")          # registered id -> bundled corpus
aegean.read_corpus("ht.json")          # saved lossless JSON corpus
aegean.read_corpus("homer.db")         # SQLite corpus on disk
# aegean.read_corpus("tlg0012.tlg001") # Iliad, fetched and cached
```

Because every CLI corpus argument calls `read_corpus`, Greek works, saved
subsets, and stdin streams work directly from the shell:

```bash
aegean stats     ht.json                       # saved JSON subset
aegean db build  tlg0012.tlg001 -o iliad.db    # build SQLite straight from a work id
aegean export    tlg0012.tlg002 -f csv -o odyssey.csv
python -c "import aegean; print(aegean.load('lineara').filter(site='Zakros').to_json())" \
  | aegean stats -                             # JSON corpus piped via stdin
```

### Combining and slicing corpora

`merge()` joins corpora and `subset()` selects documents by id. Both preserve
source attribution in provenance.

```python
import aegean
a = aegean.Corpus.from_records([{"id": "A1", "text": "KU-RO 10"},
                                {"id": "A2", "text": "A-DU 5"}], script_id="lineara")
b = aegean.Corpus.from_records([{"id": "B1", "text": "SA-RA2 3"}], script_id="lineara")

m = a.merge(b)                          # documents concatenated in order
print([d.id for d in m])                # ['A1', 'A2', 'B1']
print(m.cite("plain"))
# Merged corpus of: User-supplied corpus (Corpus.from_records); User-supplied corpus (Corpus.from_records) [merged: 2 corpora → 3 documents]

s = m.subset(["A1", "B1"])              # id-based selection
print([d.id for d in s])                # ['A1', 'B1']
```

`Corpus.merge(*others, dedupe=...)` controls duplicate document ids:

| `dedupe` | Behavior on colliding id |
|---|---|
| `"error"` (default) | raise `ValueError` listing collisions |
| `"first"` / `"last"` | keep that occurrence and drop the duplicate |
| `"suffix"` | rename later collisions `id#2`, `id#3`, … |

```python
a = aegean.Corpus.from_records([{"id": "X1", "text": "KU-RO 10"}], script_id="lineara")
b = aegean.Corpus.from_records([{"id": "X1", "text": "A-DU 5"}], script_id="lineara")
a.merge(b)                  # ValueError: duplicate document ids across corpora: X1; …
a.merge(b, dedupe="last")   # keeps b's X1
a.merge(b, dedupe="suffix") # ids become ['X1', 'X1#2']
```

When inputs share a `script_id`, the merged corpus keeps it and the first input's
sign inventory; mixed scripts yield `script_id="mixed"` with no shared inventory.

Document ids inside a single `Corpus` are unique: `Corpus.__init__` collapses
duplicate ids by keeping the last entry (matching `.get()`) and emitting a
warning, ensuring `len()`, iteration, `.documents`, `.get()`, and `.fingerprint()`
remain consistent.

`aegean.combine([...])` accepts a sequence of corpora; on the CLI, `aegean combine`
resolves each source via `read_corpus`, merges them, and writes `.json` or `.db`:

```bash
# merge both Homeric epics into one SQLite database
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db

# merge two saved subsets; --on-conflict mirrors dedupe
aegean combine ht.json zakros.json -o crete.json
# wrote 1163 documents to crete.json (merged 2 sources)
```

`aegean combine` accepts `--on-conflict {error|first|last|suffix}` (default
`error`) and records every input source in provenance.

---

## Building your own corpus

Custom inscriptions support filtering, querying, DataFrames, citation, and export
once wrapped in a `Corpus`.

### `Corpus.from_records`

Each dict record requires `id` and text supplied via one of three keys (in
precedence order): `lines` (list of physical lines, each a list of tokens),
`words` (flat token list forming one line), or `text` (whitespace-tokenized
string forming one line). A token may be a string or a dict `{"text": …}` with
optional `kind`, `status`, and `alt`. Omitted `kind` values are inferred
(parseable numerals become `NUMERAL`, others `WORD`), and hyphenated tokens split
into `signs` automatically.

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

Optional record keys include `meta` (`site`, `support`, `scribe`, `findspot`,
`period`, `name`) and `translations`. Pass custom `provenance=` and
`sign_inventory=` to `from_records` when available. Register a named loader to
expose the corpus through `aegean.load` (see [Scripts are plugins](#scripts-are-plugins)):

```python
aegean.core.corpus.register_loader("myfind", lambda: c)
aegean.load("myfind")
```

---

## Serialization: the JSON round-trip

Two JSON formats exist with distinct fidelity guarantees:

| Method | Fidelity | Use case |
|---|---|---|
| `to_dict()` | lossy summary (per-doc words and metadata) | quick inspection and lightweight interchange |
| `to_json()` / `from_json()` | lossless | archiving, cross-machine transfer, reproducibility |

### `to_dict` (lossy summary)

```python
import aegean, json
d = aegean.load("lineara").filter(site="Haghia Triada").to_dict()
print(list(d["_meta"].keys()))
# ['tool', 'schemaVersion', 'scriptId', 'documentCount', 'source', 'license', 'citation']
print(list(d["documents"][0].keys()))
# ['id', 'script_id', 'words', 'glyphs', 'transcription', 'translations', 'meta']
```

The `_meta` header stamps tool name, schema version, script id, document count,
source, license, and citation onto the summary export.

### `to_json` / `from_json` (lossless)

`to_json` serializes every token (kind, signs, glyphs, line, position, non-default
status/alt/annotations, optional source alignment, and optional typed form state),
exact document `source_text`, physical lines, full metadata, sign inventory, and
provenance. `from_json` reconstructs the exact corpus. Current exports write
schema 3; schema-1 and schema-2 files still load with `form_state=None`.

```python
import aegean
c = aegean.load("lineara")

# JSON string (indent defaults to 2; pass indent=None for compact output)
js = c.to_json()
len(js)                                # 2708119

# verify lossless round-trip
c2 = aegean.Corpus.from_json(js)
print(len(c2))                                         # 1721
print(c.get("HT13").tokens[0] == c2.get("HT13").tokens[0])   # True
print(c.fingerprint() == c2.fingerprint())             # True
```

`from_json` accepts a JSON string, a `Path`, or a path string (anything not
starting with `{`):

```python
c.to_json("lineara.json")              # writes file, returns None
c3 = aegean.Corpus.from_json("lineara.json")
```

From the shell:

```bash
aegean export lineara -f json -o lineara.json
# wrote 1721 documents to lineara.json (json)

aegean export lineara -f json -o ht.json --site "Haghia Triada"
# wrote 1110 documents to ht.json (json)
```

`aegean load CORPUS --output file.json` writes the same lossless JSON for a
metadata-filtered subset.

---

## Tabular views: DataFrames, CSV, Parquet

`Corpus.to_dataframe(level=...)` builds a pandas DataFrame at one of three
granularities:

| `level` | One row per | Columns |
|---|---|---|
| `"document"` (default) | document | `id`, `script_id`, `site`, `support`, `scribe`, `findspot`, `period`, `name`, `n_tokens`, `n_words`, `source_text` |
| `"token"` | token | `doc_id`, `line_no`, `position`, `text`, `kind`, `status`, `site`, `period` (+ spread token `annotations`) |
| `"word"` | `WORD` token | same as `token`, words only |

```python
import aegean
c = aegean.load("lineara")

c.to_dataframe("document").shape       # (1721, 11)
df = c.to_dataframe("token")
list(df.columns)
# ['doc_id', 'line_no', 'position', 'text', 'kind', 'status', 'site', 'period']
df.shape                               # (6406, 8)
```

At `token` and `word` levels, per-token `annotations` spread into columns first
(so NT `lemma`, `morph`, `strongs`, and `gloss` become columns; canonical columns
always win on name collisions).

Two canonical column groups are emitted only when at least one token in the
corpus populates them, avoiding empty padding columns on plain corpora:

- Source-aligned corpora gain nine `alignment_*` columns (`alignment_document_id`,
  `alignment_sentence_id`, `alignment_source_token_id`, `alignment_original_text`,
  `alignment_start_char`, `alignment_end_char`, `alignment_whitespace_before`,
  `alignment_normalized_text`, `alignment_normalization_ops`).
- Corpora with typed form state gain sixteen `form_*` columns (`form_diplomatic`,
  `form_regularized`, `form_normalized`, `form_model_input`,
  `form_model_input_ops`, `form_model_input_source`, `form_segments`, plus
  editorial-status, damage, and uncertainty columns; `form_segments` serializes as
  a JSON string).

pandas is installed via the `[data]` extra:

```bash
pip install "pyaegean[data]"
```

CSV and Parquet exporters wrap `to_dataframe`:

```python
from aegean.io import to_csv, to_parquet
c = aegean.load("lineara").filter(site="Haghia Triada")
to_csv(c, "ht.csv", level="document")        # ~94 kB
to_parquet(c, "ht.parquet", level="token")   # requires [parquet] extra (pyarrow)
```
```bash
aegean export lineara -f csv     -o docs.csv    --level document
aegean export lineara -f parquet -o tok.parquet --level token
```

If pyarrow is missing, Parquet export raises an error pointing to
`pip install "pyaegean[parquet]"`.

`SignInventory.to_dataframe()` produces one row per sign (`label`, `glyph`,
`codepoint`, `phonetic`, plus spread `attrs`).

---

## The query engine

`filter()` matches exact document metadata. The query engine handles text,
prefix, suffix, sign-pattern, and co-occurrence predicates with AND, OR, and NOT,
returning either matched inscriptions or ranked `(word, count)` pairs. Word
counts default to document frequency (distinct inscriptions); pass
`count_unit="token"` for total occurrences. The field registry and legacy
predicates mirror the Linear A Research Workbench, extended with explicit word
views and editorial-status filters for other scripts.

A query is a list of `FilterRow` objects naming a `field`, `value`, optional
`connector` (`"and"` default or `"or"`), and optional `negate`.

### The fields

The registry lives in `aegean.analysis.FIELDS`. Inscription-scope rows filter
documents; word-scope rows filter words within matched documents.

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

# inscriptions from Haghia Triada containing a word starting with KU
res = c.query([
    FilterRow("site-is", "Haghia Triada"),
    FilterRow("word-prefix", "KU"),
], output="inscriptions")

print(len(res.inscriptions))           # 55
print(res.description)                 # Site is: Haghia Triada · Word starts with: KU
```

Set `output="words"` to return ranked `(word, count)` pairs. By default, `count`
is document frequency (distinct inscriptions), so `('KU-RO', 34)` means `KU-RO`
occurs in 34 documents. Pass `count_unit="token"` (or call
`corpus.word_frequencies()`) for token counts.

Word predicates operate on every `TokenKind.WORD` token, including single-sign
Aegean words and alphabetic Greek words. Numerals, logograms, punctuation, and
unknown tokens are excluded. `view="surface"` compares exact token text;
`"normalized"` applies NFC, lowercasing, and final-sigma folding; `"lemma"`
applies that normalization to existing lemma annotations and excludes tokens
lacking lemmas without running an analyzer. Omitting `view` preserves legacy
uppercase predicates and surface keys. `statuses=` filters both token editorial
status and typed form segments. `QueryResults.metadata` records view,
normalization, count unit, exclusions, lemma sources, and denominator before word
filters; citations and saved query subsets preserve these parameters.

```python
res = c.query([FilterRow("word-prefix", "KU")], output="words")
print(len(res.words), res.words[:5])
# 33 [('KU-RO', 34), ('KU-PA₃-NU', 7), ('KU-NI-SU', 5), ('KU-PA', 4), ('KU-MI-NA-QE', 2)]
```

`negate=True` inverts a row; `connector="or"` ORs it with the preceding result
within its scope:

```python
# words with >= 3 signs not containing "PA"
res = c.query([
    FilterRow("word-min-syllables", 3),
    FilterRow("word-contains", "PA", negate=True),
], output="words")
print(len(res.words), res.words[:3])
# 543 [('A-TA-I-*301-WA-JA', 11), ('JA-SA-SA-RA-ME', 7), ('SI-RU-TE', 7)]
print(res.description)
# Word has ≥ N signs: 3 · NOT Word contains text: PA
```

`QueryResults.cite("plain" | "bibtex" | "apa")` cites the corpus with the filter
summary attached.

### Saving a query as a reusable corpus

`QueryResults.to_corpus(source)` converts an `output="inscriptions"` result back
into a `Corpus`, carrying `source`'s sign inventory, script id, and a `subset:`
provenance note naming the query:

```python
import aegean
from aegean.analysis import FilterRow

c = aegean.load("lineara")
res = c.query([FilterRow("site-is", "Haghia Triada"),
               FilterRow("word-prefix", "KU")], output="inscriptions")
sub = res.to_corpus(c)
print(len(sub))                        # 55
sub.to_json("ku_at_ht.json")           # reusable corpus on disk
```

An `output="words"` result contains no inscriptions and yields an empty corpus;
query with `output="inscriptions"` when saving a slice.

From the shell, `aegean query ... -o out.json|.db` writes the matched
inscriptions as a corpus:

```bash
aegean query lineara --where site-is="Haghia Triada" --where word-prefix=KU \
                     -o ku_at_ht.json
# wrote 55 inscriptions to ku_at_ht.json
```

### From the shell

`aegean query` mirrors the Python API. Each `--where field=value` ANDs onto the
previous row; prefix a field with `or:` to OR it or `!` to negate it. List valid
fields with `--fields`.

```bash
aegean query lineara --fields
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

For quick wildcard sign-pattern lookups (`*` matches one sign), use
`aegean search CORPUS "KU-*-RO"`. See [Analysis](Analysis).

---

## SQLite persistence (`aegean.db`)

SQLite persistence uses stdlib `sqlite3` alone. Documents and tokens map to
normalized tables (`documents`, `tokens`) for SQL and full-text search; nested
structures (signs, alternates, annotations, source alignment, typed form state,
line groupings, image refs, notes) live in JSON columns; provenance and sign
inventory live in a `meta` key/value table. Round-trips are lossless.

Overwriting an existing database runs inside an online backup transaction. Active
WAL readers retain their snapshot until their transaction ends, and subsequent
reads see the replacement. Competing writers fail with a bounded timeout, leaving
the existing file intact. External renames or unlinks while connections are open
are outside this contract. New files are created via atomic no-clobber linking.

```python
import aegean, aegean.db as db
c = aegean.load("lineara")

c.to_sql("lineara.db")                 # FTS5 index enabled by default
c2 = aegean.Corpus.from_sql("lineara.db")
print(c.fingerprint() == c2.fingerprint())   # True

# exact whole-token search (KU-RO does not match PO-TO-KU-RO)
db.search("lineara.db", "KU-RO", limit=3)
# [('HT9a', 25, 'KU-RO'), ('HT9b', 20, 'KU-RO'), ('HT11a', 7, 'KU-RO')]
db.search("lineara.db", "KU-RO", mode="substring")   # within-token matches

# stream one document at a time for large databases
for doc in db.stream("lineara.db"):
    ...
```

Schema 3 adds the nullable `tokens.form_state_json` column for typed editorial
forms. Schema-1 and schema-2 databases load with `form_state=None`; appending
(`append=True`) migrates the column and schema version atomically while leaving
existing rows without typed state. Indexes cover `tokens(doc_id)` and
`tokens(text)`, plus a `tokens_fts` FTS5 table (retaining hyphens as token
characters) when SQLite supports FTS5. Exact search verifies whole-token matches
on top of FTS and falls back to `tokens(text)` if FTS5 is absent.

CLI subcommands under `aegean db`:

```bash
aegean db build lineara -o lineara.db          # pass --no-fts to omit FTS5
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

`aegean export CORPUS -f sqlite -o lineara.db` writes the same format.

### Appending to an existing database

`to_sql(..., append=True)` and `db.to_sqlite(..., append=True)` upsert documents
into an existing database: matching document ids are replaced, new ids are
inserted, and affected FTS rows are updated in the same transaction without
rebuilding the database.

```python
import aegean, aegean.db as db
a = aegean.Corpus.from_records([{"id": "A1", "text": "KU-RO 10"}], script_id="lineara")
b = aegean.Corpus.from_records([{"id": "A1", "text": "A-DU 5"},     # replaced
                                {"id": "B1", "text": "SA-RA2 3"}],  # inserted
                               script_id="lineara")

a.to_sql("corpus.db")
db.to_sqlite(b, "corpus.db", append=True)

back = aegean.Corpus.from_sql("corpus.db")
print(sorted(d.id for d in back))      # ['A1', 'B1']
print(back.get("A1").tokens[0].text)   # 'A-DU'
db.search("corpus.db", "A-DU")         # [('A1', 0, 'A-DU')]
```

CLI equivalent (`SRC` is any `read_corpus` spec):

```bash
aegean db build tlg0012.tlg001 -o homer.db   # Iliad
aegean db add   tlg0012.tlg002 -o homer.db   # append Odyssey in place
# added/updated <n> documents in homer.db
```

---

## Portable research bundles (`aegean.bundle`)

`aegean.bundle` packages a reproducible research snapshot into a deterministic
`.zip` archive (`aegean-research-bundle/1`) using only the Python standard
library. A bundle carries `manifest.json` with SHA-256 hashes for every member,
citations (`CITATIONS.bib`, `CITATIONS.txt`, `citations.json`), optional
workbench workspace state, review CSVs (automatically pairing editable
`.companion.json` snapshots), analysis receipts, and corpus data.

License compliance is enforced automatically under `embed_corpus="auto"`
(default): redistributable corpora embed directly as deterministic
`corpus.json.gz`, while corpora with non-commercial (`CC BY-NC*`) or restricted
license strings omit the text and store a `CorpusReference` retrieval pointer
(dataset id, version, URL, SHA-256, license, and filter spec). `hydrate_bundle`
verifies archive safety and checksums, unpacks companion artifacts, and
reconstructs pointer corpora under their upstream license. Pass
`embed_corpus="always"` for a private non-redistributable archive (stamping
`redistributable=False` in `manifest.json`).

Core Python functions: `create_bundle`, `inspect_bundle`, `verify_bundle`,
`extract_bundle`, and `hydrate_bundle`, mirrored on the CLI by `aegean bundle
{create,inspect,verify,extract,hydrate}`. See
[Recipe 28](Recipes#28--package-verify-and-hydrate-a-portable-research-bundle).

---

## Import and export adapters (`aegean.io`)

`aegean.io` converts between external formats and `Corpus`. Importers
(`from_text`, `from_text_file`, `from_text_dir`, `from_csv`) default to
`token_view="all"`, retaining decoded source text, punctuation, non-word tokens,
whitespace, and document-local character spans. Use `Document.words` for lexical
tokens, or pass `token_view="words"` (CLI `--token-view words`) for word-only
import; provenance records exclusions. See
[Greek NLP → Importing your own text](Greek-NLP#importing-your-own-text) and
[Data & Provenance → Your own corpus](Data-and-Provenance#your-own-corpus).

Supported corpus export formats:

| Format | Python | CLI | Fidelity | Extra |
|---|---|---|---|---|
| Lossless JSON | `Corpus.to_json` | `export -f json` | lossless | none |
| CSV | `io.to_csv` | `export -f csv` | tabular view | `[data]` |
| Parquet | `io.to_parquet` | `export -f parquet` | tabular view | `[parquet]` |
| EpiDoc TEI XML | `io.to_epidoc`/`write_epidoc` ↔ `io.from_epidoc`/`read_epidoc` | `export -f epidoc` / `import --epidoc` | token-carrier semantic fields, not arbitrary TEI | none |
| SQLite DB | `Corpus.to_sql` / `db.to_sqlite` | `export -f sqlite` | lossless | none |
| Workbench JSON | `io.to_workbench` / `io.from_workbench_export` | `aegean workbench` (serves the app) | tokenized text + surface forms; statuses, annotations, and typed form state are lossy | none |
| RDF Turtle / JSON-LD | `io.to_rdf` | `export -f ttl` / `export -f jsonld` | graph view (export only) | none |

Single CLI entry point:

```bash
aegean export CORPUS -f {json|csv|parquet|epidoc|sqlite|workbench|ttl|jsonld} -o PATH [--level …] \
              [--site …] [--period …] [--scribe …] [--support …]
```

Metadata filters (`--site`, `--period`, `--scribe`, `--support`) apply before
export and record a `subset:` note in provenance.

### EpiDoc TEI XML

`to_epidoc(document)` serializes one `Document` to EpiDoc TEI XML;
`write_epidoc(obj, path)` writes a single file for a `Document` or a directory of
`{id}.xml` files for a `Corpus`. Transliterations live inside `<div
type="edition">` as `<lb/>`-delimited lines with element names matching
`TokenKind`: `<w>` (words), `<num>` (numerals), `<g>` (logograms), `<pc>`
(punctuation), and `<seg type="separator">` / `<seg type="unknown">`. Non-certain
readings wrap in `<unclear>` or `<supplied>` (`LOST` emits
`<supplied reason="undefined">`; the reader also accepts `<gap>`), and alternates
emit `<app><lem>…</lem><rdg>…</rdg></app>`. Export uses stdlib XML
(lazy-imported) with no extra required.

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

Each script maps to a BCP-47 `xml:lang` on the edition div (`und` for
undeciphered scripts, `grc` for Greek, `gmy` for Mycenaean Greek):

| script id | `xml:lang` |
|---|---|
| `lineara` | `und` |
| `linearb` | `gmy` |
| `cypriot` | `grc` |
| `cyprominoan` | `und` |
| `greek` | `grc` |

Output validates against the official EpiDoc RelaxNG schema and round-trips
semantically through `io.from_epidoc` / `io.read_epidoc` (stdlib-only) for
token-carrier documents: id, find-place, token/line stream, carrier-derived token
kinds, editorial certainty, typed choices and apparatus segments, and `<app>`
variants. It does not guarantee byte-identical XML or parse arbitrary free-text
TEI. For DAMOS-style Linear B EpiDoc, `aegean.scripts.linearb.parse_epidoc` uses
lxml (`[epidoc]` extra) and re-derives Aegean token kinds from transliteration
text.

### The Linear A Research Workbench

pyaegean exchanges corpus and workspace JSON in both directions with the
[Linear A Research Workbench](https://linearaworkbench.xyz/). The CLI command
`aegean workbench` fetches the SHA-256-pinned `workbench-app` `v2.1.0` static
build (~3.3 MB `tar.gz`, with multi-script Aegean fonts) to the local cache and
serves it on loopback with optional local bridges (`--corpus`, `--site`,
`--module`, `--doc`, `--damos`, `--state`).

```python
import aegean
from aegean.io import (
    to_workbench,
    from_workbench_export,
    load_workbench_backup,
    save_workbench_backup,
)

c = aegean.load("lineara").filter(site="Haghia Triada")

# emit workbench-shaped inscription records (optionally write to JSON)
recs = to_workbench(c, "ht.workbench.json")

# load workbench Data Export or plain records array
c2 = from_workbench_export("ht.workbench.json")

# load and run saved workbench research state (annotations, notes, saved queries)
ws = load_workbench_backup("workspace.json")
hits = c.query(ws.to_filter_rows(0))
```

Mount a `to_workbench` file through `?corpus=<url>` or
`aegean workbench --corpus <id-or-path>`. `from_workbench_export` accepts either
a schema-v1 full-corpus export or a plain records array; for
`script_id="lineara"`, tokens are classified via
`aegean.scripts.lineara.loader.classify` (restoring inline erased `𐝫`, bracketed
uncertainty `[?]`, logograms, separators, and fractions) and attached to
`linear_a_inventory()`. Out-of-band `ReadingStatus` overrides on plain tokens and
`Token.annotations` are not carried by the workbench format. Use
`load_workbench_backup` / `save_workbench_backup` (or
`aegean workbench --state workspace.json`) to round-trip annotations, notes,
collections, findings, saved hypotheses, and saved queries between Python and the
browser.

---

## Saving results and AI outputs (`--output`)

Analysis and AI CLI commands share the `--output/-o` convention to write results
to disk using only the standard library. The file extension chooses the format
(`.json`, `.csv`, or `.txt`) where supported by the result shape:

| Command | `-o` writes | Extensions |
|---|---|---|
| `aegean stats` / `keyness` / `dispersion` / `search` | result table | `.json` / `.csv` / `.txt` |
| `aegean analyze {assoc,cooccur,clusters,hands}` | analysis result | `.json` / `.csv` / `.txt` |
| `aegean ai {translate,gloss,summarize,hypotheses,ask,extract}` | AI result | `.json` / `.txt` |

```bash
# write frequency table directly to CSV (stdlib csv, no pandas)
aegean stats lineara --top 3 -o freq.csv
```
```
item,count
KU-RO,37
SA-RA₂,20
KI-RO,16
```

For AI commands, `.json` writes text, provenance, grounding, and `exploratory:
true`; `.txt` writes labeled text. Translation JSON preserves any checking
draft, model-reported uncertainties and changes, raw provider output, and
grounding runtime/coverage metadata. Translation `.txt` exports append the audit
trace automatically in both `--style annotated` and `--style concise`.

```bash
aegean ai translate "ἐν ἀρχῇ" -o reading.json   # text + provenance + grounding
aegean ai gloss     "ἐν ἀρχῇ" -o gloss.txt      # labeled text
```

### `ExploratoryResult` serialization

Every AI capability returns an `ExploratoryResult` (`aegean.ai`) containing
`text`, `provider`, `model`, `prompt_version`, structured `grounding`
(`GroundingItem` objects carrying `source`, `ref`, `status`, and optional
`provenance`), `exploratory=True`, and optional parsed `data`. Hybrid translation
adds `grounding_runtime`; checking adds the original `draft`. All optional fields
survive serialization. Translation `data` keeps `translation`, `uncertainties`,
`changes`, and `raw_response` separate; `format_status="structured"` checks JSON
structure only, while malformed responses stay verbatim as `unstructured`.

| Method | Behavior |
|---|---|
| `to_dict()` | JSON-ready dict carrying `_meta`, `text`, `grounding`, `exploratory`, and optional `data`/`draft`/`grounding_runtime` |
| `to_json(path=None)` | return JSON string or write to `path` |
| `from_dict(data)` *(classmethod)* | reconstruct `ExploratoryResult` from `to_dict` output |

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
d["exploratory"]                       # True

r2 = ExploratoryResult.from_dict(d)
r2.text == r.text                      # True
r2.grounding[0].source                 # 'lexicon'
```

`labeled()` and `trace()` are methods rather than serialized fields.
`GroundingItem.status` distinguishes predictions, source annotations, field-level
human review, reference candidates, and unclassified strings, rendered into
prompts and traces via `render()`. Plain strings remain unclassified.
`ai.annotation_evidence()` formats existing token annotations and current
per-field review decisions without rerunning analyzers.

---

## Provenance and citation

Every bundled and fetched corpus carries a `Provenance` record (source, license,
citation, URL) that stamps exports and propagates through filters, queries, and
merges.

`Corpus.cite(style)` formats citations for the corpus or exact filtered subset:

```python
import aegean
c = aegean.load("lineara")
print(c.cite("plain"))
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz

print(c.cite("bibtex"))
# @misc{lineara-corpus,
#   title = {Godart, L. \& Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.},
#   year = {1976},
#   url = {https://github.com/mwenge/lineara.xyz},
#   note = {License: Apache-2.0 …. Accessed via pyaegean},
# }
```

| `style` | Output |
|---|---|
| `"plain"` | single citation line with any `subset:` or query note in brackets |
| `"bibtex"` | `@misc` entry (`title`, extracted `year`, `url`, `note`) |
| `"apa"` | APA-style reference line (`n.d.` if no year is extracted) |

```bash
aegean cite lineara --style bibtex
aegean cite lineara --site "Haghia Triada"
```

`QueryResults.cite(...)` cites the exact query result set. BibTeX and APA
renderings extract the first plausible year from free-text provenance and place
license and subset notes into `note` or brackets. See
[Data and Provenance](Data-and-Provenance) for dataset origins and licenses.

---

## Scripts are plugins

Each writing system implements the `aegean.core.script.Script` abstract base
class:

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

Corpus loaders register separately with
`aegean.core.corpus.register_loader(script_id, fn)` so `aegean.load(script_id)`
can locate them. Core modules never import script plugins; `aegean/__init__.py`
imports `aegean.scripts` to register the five built-ins (`lineara`, `linearb`,
`cypriot`, `cyprominoan`, `greek`).

```python
import aegean
aegean.registered_scripts()
# ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']

g = aegean.get_script("greek")
print(len(g.sign_inventory))           # 25 (Greek alphabet)
[(t.text, t.kind.value) for t in g.tokenize("ἐν ἀρχῇ")]
# [('ἐν', 'word'), ('ἀρχῇ', 'word')]
```

`SignInventory` indexes signs for O(1) lookup by label, glyph, or codepoint:

```python
inv = aegean.load("lineara").sign_inventory
inv.by_label("KU")        # Sign labelled KU
inv.by_glyph("𐙂")        # same Sign by Unicode glyph
inv.by_codepoint(0x10642) # same Sign by codepoint
len(inv)                  # 342
```

```bash
aegean sign lineara KU
```

---

## Numerals and accounting (`aegean.core.numerals`)

`aegean.core.numerals` parses tablet decimal numerals and metrological fractions
and reconciles `KU-RO` / `PO-TO-KU-RO` totals against summed entries. It is a
parity-tested port of the workbench numeral library verified against shared
golden fixtures.

```python
from aegean.core.numerals import parse_value, format_value
parse_value("10")        # 10
parse_value("¹⁄₂")       # 0.5 (super/subscript fraction)
parse_value("½")         # 0.5 (precomposed glyph)
format_value(130.5)      # '130½'
```

Recognized total and deficit markers:

| Script | Total | Grand total | Deficit |
|---|---|---|---|
| Linear A | `KU-RO` | `PO-TO-KU-RO` | `KI-RO`, `KU-RO₂` |
| Linear B | `TO-SO`, `TO-SA` | — | `O-PE-RO`, `O-PE-RO-SI` |

Reconciliation (`check_balances`, `analysis.balance_check`, `aegean balance`) is
exploratory because section boundaries are inferred heuristically and Minoan
metrology remains contested. See [Analysis](Analysis).

---

## Conventions and design rules

- **Zero core third-party dependencies.** pandas (`[data]`), lxml (`[epidoc]`),
  Textual (`[tui]`), neural runtimes (`[neural]`), and provider SDKs are
  lazy-imported inside the functions that require them; collocation statistics,
  querying, SQLite persistence, and research bundles use only the standard
  library.
- **No bundled binaries.** Large corpora, trained models, and imagery use
  [download-to-cache](Data-and-Provenance). `scripts/check_footprint.py` enforces
  import-clean, import-fast, and a code-and-JSON-only wheel in CI.
- **Schema version 3.** Lossless JSON and SQLite persistence carry schema version
  `3` (adding typed form state while remaining readable for schemas 1 and 2).
  `to_json` omits default fields such as `CERTAIN` status to stay compact.
- **Exploratory labeling.** Cross-linguistic distance, morphological clustering,
  accounting reconciliation, decipherment hypotheses, and AI outputs carry
  explicit unverified caveats. Linear A and Cypro-Minoan are undeciphered.

## Limitations and notes

- `to_dict` is lossy (words and metadata only). Use `to_json`/`from_json`,
  SQLite, or `aegean.bundle` for reproducible persistence.
- EpiDoc export is semantic rather than byte-identical. For token-carrier
  documents it preserves id, find-place, token/line stream, token kinds,
  editorial certainty, typed choices, and apparatus segments. `io.from_epidoc`
  is stdlib-only and reads kinds from carrier elements (falling back to text
  only for untyped `<seg>`); it is not a general free-text TEI importer.
  `scripts.linearb.parse_epidoc` re-derives Aegean kinds from transliterations
  and requires lxml (`[epidoc]`).
- Query word predicates select `TokenKind.WORD` tokens (including single-sign
  Aegean and Greek words) and exclude logograms, numerals, punctuation, and
  unknown tokens.
- Parquet export requires pyarrow (`[parquet]`); CSV and Parquet require pandas
  (`[data]`).
- See [Limitations](Limitations) for project-wide boundaries and
  [Greek NLP](Greek-NLP) / [Meters](Meters) for Greek-specific layers.
