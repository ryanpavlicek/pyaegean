# Data model

This page documents pyaegean's core object model: every field on `Corpus`,
`Document`, `Token`, and `TokenRecord`, the reserved keys in
`Token.annotations`, `fingerprint()` and `copy()` semantics, JSON and SQLite
persistence contracts, and the invariants required for custom corpora and
loaders. For module layering and query APIs, see [Architecture](Architecture).

All examples below were run against the installed package and show actual
output.

---

## 1. Object hierarchy

```text
Corpus                          collection of documents + shared context
├── documents: list[Document]   one per inscription / tablet / text
│   ├── tokens: list[Token]     transliterated text stream, in order
│   ├── lines:  list[list[int]] physical lines as indices into tokens
│   ├── source_text: str | None exact source snapshot for aligned documents
│   └── meta:   DocumentMeta    site, period, scribe, support, findspot, name, ...
├── sign_inventory: SignInventory | None    indexed Sign objects for the script
├── provenance: Provenance | None           source, license, citation, notes
└── script_id: str                          "lineara", "greek", "custom", ...
```

Four structural rules govern this hierarchy:

- **`lines` stores token indices, not token copies.** Each entry in
  `document.lines` is a list of indices into `document.tokens`;
  `document.line_tokens` resolves them into token lists.
- **`Token` and `Sign` are frozen dataclasses.** Modify fields via
  `dataclasses.replace`. Each carries one mutable mapping (`Token.annotations`
  and `Sign.attrs`). `Document` is mutable.
- **Source alignment is typed.** An aligned token carries an immutable
  `SourceAlignment`; its owning `Document` stores the exact `source_text` those
  character offsets index.
- **Document IDs are unique within a corpus.** Passing duplicate IDs to
  `Corpus(...)` collapses duplicates (keeping the last) with a warning;
  `Corpus.merge` raises on duplicate IDs by default (`dedupe="error"`).

```python
import aegean

corpus = aegean.load("lineara")          # Corpus
doc = corpus.get("HT13")                 # Document
print(type(corpus).__name__, "of", len(corpus), "documents")
print(doc.id, doc.script_id, "-", len(doc.tokens), "tokens on", len(doc.lines), "lines")
print("lines:", doc.lines)
tok = doc.tokens[0]                      # Token
print("first token:", tok.text, tok.kind, tok.signs)
print("line 2 text:", [t.text for t in doc.line_tokens[1]])
```

```text
Corpus of 1721 documents
HT13 lineara - 22 tokens on 8 lines
lines: [[0, 1, 2, 3, 4], [5, 6, 7], [8, 9], [10, 11, 12], [13, 14], [15, 16], [17, 18], [19, 20, 21]]
first token: KA-U-DE-TA TokenKind.WORD ('KA', 'U', 'DE', 'TA')
line 2 text: ['RE-ZA', '5', '¹⁄₂']
```

---

## 2. `Token`, field by field

| Field | Type | Meaning |
| --- | --- | --- |
| `text` | `str` | Transliteration or surface form, e.g. `KU-RO` or `Λόγος,` |
| `kind` | `TokenKind` | `word`, `logogram`, `numeral`, `separator`, `punct`, or `unknown` |
| `signs` | `tuple[str, ...]` | Decomposed sign labels, e.g. `("KU", "RO")`; empty for alphabetic text |
| `glyphs` | `str \| None` | Unicode glyph form, when known |
| `line_no` | `int \| None` | Physical line number |
| `position` | `int \| None` | Token index within the document's token stream |
| `status` | `ReadingStatus` | Editorial certainty (§3); defaults to `CERTAIN` |
| `alt` | `tuple[str, ...]` | Alternate readings (EpiDoc `<app>`/`<rdg>`); `text` holds the preferred reading |
| `annotations` | `dict[str, str]` | Per-token string annotations (see below) |
| `alignment` | `SourceAlignment \| None` | Exact source identity, character span, whitespace, and normalization record |
| `form_state` | `TokenFormState \| None` | Typed diplomatic, editorial, and model-input forms with ordered apparatus segments |

`document.words`, word-scope queries, review exports, and `annotate_corpus` all
filter on `TokenKind.WORD`; a word token labeled `unknown` is excluded from
word-level analyses. `position` is plain data (it may be `None`, and SQLite
persistence orders by `token_order`, see §6). Review round-tripping joins on
`alignment.source_token_id` when available and falls back to `document.id` plus
`position` for unaligned documents, so keep `position` equal to the token list
index on unaligned corpora.

A gold-annotated token from the New Testament corpus:

```python
import aegean

nt = aegean.load("nt")
doc = nt.get("John 1")
tok = doc.tokens[4]                       # Λόγος, fifth token of John 1:1
print("text      :", tok.text)
print("kind      :", tok.kind)
print("signs     :", tok.signs)
print("glyphs    :", tok.glyphs)
print("line_no   :", tok.line_no)
print("position  :", tok.position)
print("status    :", tok.status)
print("alt       :", tok.alt)
for k, v in sorted(tok.annotations.items()):
    print(f"annotations[{k!r}] = {v!r}")
```

```text
text      : Λόγος,
kind      : TokenKind.WORD
signs     : ()
glyphs    : Λόγος,
line_no   : 1
position  : 4
status    : ReadingStatus.CERTAIN
alt       : ()
annotations['gloss'] = 'a word, speech, divine utterance, analogy'
annotations['lemma'] = 'λόγος'
annotations['morph'] = 'N-NSM'
annotations['normalized'] = 'Λόγος'
annotations['ref'] = 'John.1.1'
annotations['strongs'] = '3056'
annotations['upos'] = 'NOUN'
```

### Keys in `annotations`

`annotations` is a flat `dict[str, str]` (booleans are stored as `"true"` /
`"false"`). It is included in `fingerprint()`, survives JSON and SQLite
round-trips unchanged, and expands into columns in token-level DataFrames.

| Writer | Keys | Meaning |
| --- | --- | --- |
| NT corpus (gold) | `lemma`, `morph`, `strongs`, `gloss`, `normalized`, `upos`, `ref` | Edition-supplied annotations |
| `greek.annotate_corpus` | `lemma`, `upos`, `lemma_source`, `lemma_resolved`, `lemma_verified`, `review_recommended` | Machine analysis, provenance, and review flags (§4) |
| `aegean.io.from_review_table` | `<field>__pred`, `<field>_review_decision`, `<field>_verified`, `<field>_reviewed_by`, `<field>_review_note`, `<field>_review_evidence`, `review_status`, `reviewed_by`, `review_note`, `review_evidence`, `review_history` | Reviewer decisions and dated audit trail (§7.3) |
| User code | Any other string key | Custom per-token metadata |

When a reviewer correction is applied, the corrected value replaces `lemma`,
`upos`, `morph`, or `feats`, and the original machine prediction is preserved
under `<field>__pred` (`lemma__pred`, `upos__pred`, `morph__pred`). Treat any
key ending in `__pred` as reserved. `lemma_source` stores a `LemmaSource` value
(`attested`, `neural_lookup`, `neural_edit`, `neural`, `rule`, `seed`,
`paradigm`, `identity`, `unresolved`, `punct`, or `user`). `lemma_resolved`,
`lemma_verified`, and `review_recommended` separate resolution, human
verification, and review flagging; `lemma_known` is a deprecated compatibility
alias for `lemma_resolved`.

### Lossless source alignment

`SourceAlignment` keeps exact character spans typed outside `annotations`:

| Field | Meaning |
| --- | --- |
| `document_id`, `sentence_id` | Owning document and sentence identities |
| `source_token_id` | Stable token identity for an unchanged source snapshot |
| `original_text` | Exact slice from `Document.source_text` |
| `start_char`, `end_char` | Half-open Python Unicode code-point offsets |
| `whitespace_before` | Exact whitespace preceding this token |
| `normalized_text` | Model-facing normalized string |
| `normalization_ops` | Ordered normalization steps (e.g. `unicode:nfc`) |

Aligned documents set `source_text`; `doc.validate_source_alignment()` verifies
every slice, whitespace gap, ID, order, and non-overlap invariant. Schema-2 and
schema-3 JSON and SQLite preserve alignment; schema-1 corpora load with
`source_text=None` and `alignment=None`.

```python
from aegean import Document, greek

source = "  α\u0301\tλόγος."
tokens = greek.tokenize_aligned(source, document_id="demo")
doc = Document("demo", "greek", tokens, [list(range(len(tokens)))], source_text=source)
doc.validate_source_alignment()

tokens[0].alignment.original_text       # 'ά'
tokens[0].alignment.normalized_text     # 'ά'
source[tokens[0].alignment.start_char:tokens[0].alignment.end_char] == "α\u0301"  # True
```

### Typed editorial forms and model input

`Token.text` holds the display token. When an edition distinguishes diplomatic
and editorial forms, `Token.form_state` records each layer explicitly:

| Field | Meaning |
| --- | --- |
| `diplomatic` | Original or diplomatic spelling from the edition |
| `regularized` | Editorial spelling (corrected or expanded form) |
| `normalized` | Preprocessing-normalized spelling |
| `model_input` | Exact string passed to an analyzer after recorded operations |
| `model_input_source` | Origin of `model_input`: `diplomatic`, `regularized`, `normalized`, or explicit |
| `segments` | Ordered pieces tagged `certain`, `restored`, `unclear`, or `lost`, with optional source references |

`diplomatic`, `regularized`, `normalized`, and `segments` describe source or
editorial text; `model_input` records computational input rather than a new
edition reading. `pipeline_tokens()` selects model input deterministically in
order: explicit `model_input`, `regularized`, `normalized`, `diplomatic`, then
`Token.text`. The resulting `TokenRecord` retains `form_state` and records
operations applied during inference (such as NFC normalization).

Token-carrier EpiDoc choices (`<choice><reg>…</reg><orig>…</orig></choice>`) and
apparatus elements (`<supplied>`, `<unclear>`, `<gap>`) populate `form_state`.
`to_epidoc()` emits semantic choices and apparatus without promising
byte-identical XML.

### Lossless CoNLL-U structural model

Treebank files use a dedicated model (`greek.UDDocument`) rather than forcing
non-word rows into `Corpus.Token`. `UDSentence.rows` and `UDSentence.items`
retain ordered comments, complete ten-column CoNLL-U rows, `UDMultiwordToken`
ranges, `UDEmptyNode` entries, enhanced dependencies, and ordered MISC entries.
Integer-ID syntactic words remain exposed on `UDSentence.tokens`, with the
mapping recorded on `UDSentence.projection`.

`greek.load_conllu_document()` and `greek.write_conllu()` perform lossless
document round-trips. Pass `strict=True` for strict validation; lenient mode
preserves valid structure and opaque malformed rows for inspection. The `v3`
neural pipeline consumes only the syntactic word projection.

---

## 3. `ReadingStatus`

Every token carries a Leiden/EpiDoc editorial certainty state. Unknown values
raise `ValueError` at construction.

| Status | Meaning | Sources |
| --- | --- | --- |
| `certain` | Securely read | Default |
| `unclear` | Damaged but legible | Leiden underdot; EpiDoc `<unclear>`; erasures (`⟦ ⟧`); illegible-sign marks in Cypriot |
| `restored` | Editorially supplied | Leiden `[ ]`; EpiDoc `<supplied>` |
| `lost` | Not preserved / lacuna | Leiden `[---]`; EpiDoc `<gap>` or `<supplied reason="undefined">` |

The bundled Linear A and Cypriot loaders decode their editions' Leiden
apparatus. The eight hosted Greek epigraphy and papyri assets (`isicily`, `iip`,
`iospe`, `igcyr`, `aphrodisias`, `crete`, `edh`, `ddbdp`) expose aggregate
per-token `ReadingStatus` (taking the most severe state when multiple apply);
those prebuilt assets do not carry `TokenFormState`. Token-carrier EpiDoc
imports (`aegean.io.from_epidoc`) populate both `ReadingStatus` and
`TokenFormState`, and `Corpus.from_records` accepts a `"status"` string per
token (§7.1). See [Using Critical Editions](Using-Critical-Editions).

```python
from collections import Counter
import aegean

corpus = aegean.load("lineara")
print(dict(Counter(t.status.value for d in corpus for t in d.tokens)))
print([(t.text, t.status.value) for t in corpus.get("HT23b").tokens][:8])
```

```text
{'certain': 5734, 'lost': 552, 'unclear': 120}
[('NI-RA', 'certain'), ('CYP', 'certain'), ('¹⁄₃', 'certain'), ('OLE', 'certain'), ('¹⁄₃', 'certain'), ('MI+JA+RU', 'certain'), ('MU', 'certain'), ('QA2+[?]+PU', 'unclear')]
```

---

## 4. `TokenRecord` vs `Token`

`Token` holds persistent corpus data stored in documents and cited with the
corpus. `greek.TokenRecord` holds ephemeral analysis output returned by
`greek.pipeline()`. Both can carry the same immutable `SourceAlignment`, but
their linguistic fields are separate.

`greek.annotate_corpus()` bridges them by returning a copy of the corpus with
pipeline predictions written into `Token.annotations`. Re-annotation replaces
`lemma` and `upos` and clears prior lemma evidence and neural warnings (custom
taggers or `with_evidence=False` leave evidence fields unset); unrelated source
annotations and historical review records remain. `review_recommended=False`
does not certify correctness; only `lemma_verified="true"` records an imported
human decision (`user`).

| `TokenRecord` field | Meaning |
| --- | --- |
| `sentence` | 0-based sentence index in input |
| `index` | 1-based token index within the sentence |
| `text` | Token surface form |
| `upos` | Universal POS tag |
| `lemma` | Predicted or resolved lemma |
| `lemma_source` | `LemmaSource` evidence class |
| `lemma_resolved` | `True` when a lemma decision exists rather than a surface fallback |
| `lemma_verified` | `True` only for an imported human lemma correction (`user`) |
| `review_recommended` | `True` when `lemma_source` is `identity` or `unresolved` |
| `head` | `index` of syntactic head (`0` = root, `None` = unparsed) |
| `relation` | Dependency relation label (named `relation`, not `deprel`) |
| `xpos`, `feats` | 9-character positional tag and UD FEATS (neural pipeline only) |
| `lemma_known` | Deprecated alias for `lemma_resolved` |
| `lemma_source_path` | Neural lemma composition route (`lookup_form_upos`, `lookup_form`, `edit_script`, `lookup_lower_fallback`, or `identity_fallback`) |
| `upos_confidence`, `lemma_confidence` | Legacy flat confidence floats without source/domain scope |
| `token_confidence` | Typed per-task `ConfidenceResult` values or explicit unavailable reasons |
| `sentence_confidence` | Typed sentence confidence, required component names, and optional abstention decision |
| `alignment` | Exact source identity, original/normalized text, span, and whitespace |
| `form_state` | Typed editorial forms and exact model input (when called via `pipeline_tokens()`) |
| `boundary_policy`, `boundary_policy_id` | Sentence segmentation policy name and ID on each sentence's terminal record |
| `boundary_provenance`, `boundary_confidence` | Boundary evidence class (`None` confidence for built-in rules; `[0, 1]` optional for plugins) |
| `boundary_start_char`, `boundary_end_char` | Half-open source span for the sentence when provable from alignments; else `None` |

```python
from aegean import greek

records = greek.pipeline("ὁ λόγος σὰρξ ἐγένετο καὶ ἐσκήνωσεν ἐν ἡμῖν.")
for r in records:
    print(f"{r.sentence} {r.index} {r.text:10} {r.upos:6} {r.lemma:10} "
          f"{r.lemma_source.value:14} resolved={r.lemma_resolved!s:5} "
          f"verified={r.lemma_verified!s:5} review={r.review_recommended!s:5} "
          f"head={r.head} relation={r.relation} xpos={r.xpos} feats={r.feats}")
```

```text
0 1 ὁ          DET    ὁ          seed           resolved=True  verified=False review=False head=None relation=None xpos=None feats=None
0 2 λόγος      NOUN   λόγος      seed           resolved=True  verified=False review=False head=None relation=None xpos=None feats=None
0 3 σὰρξ       NOUN   σὰρξ       unresolved     resolved=False verified=False review=True  head=None relation=None xpos=None feats=None
0 4 ἐγένετο    NOUN   ἐγένετο    unresolved     resolved=False verified=False review=True  head=None relation=None xpos=None feats=None
0 5 καὶ        CCONJ  καί        seed           resolved=True  verified=False review=False head=None relation=None xpos=None feats=None
0 6 ἐσκήνωσεν  NOUN   ἐσκήνωσεν  unresolved     resolved=False verified=False review=True  head=None relation=None xpos=None feats=None
0 7 ἐν         ADP    ἐν         seed           resolved=True  verified=False review=False head=None relation=None xpos=None feats=None
0 8 ἡμῖν       NOUN   ἐγώ        seed           resolved=True  verified=False review=False head=None relation=None xpos=None feats=None
0 9 .          PUNCT  .          punct          resolved=True  verified=False review=False head=None relation=None xpos=None feats=None
```

### Typed confidence and abstention policy

`token_confidence` holds one `ConfidenceResult` per task (UPOS, XPOS, FEATS,
lemma, head, relation), and `sentence_confidence` lists its required components.
Each entry is either available (carrying model, source, domain, calibration ID,
sample size, and measured ECE/Brier score) or unavailable with a reason code
(`missing_calibration`, `unsupported_task`, `unsupported_source`,
`unsupported_domain`, or `confidence_unavailable`). An unavailable entry means
no calibrated estimate exists, not a probability of zero.

`confidence_domain=` is an explicit caller-supplied label, not an automatic
domain classifier. `greek.use_calibration_registry()` activates the bundled
Schema-2 `CalibrationRegistry` covering all six tasks across `literary` and
`documentary_native` domains; lookup prefers exact source/domain entries and
uses a broader entry only if explicitly marked as a fallback. Passing a
caller-defined `AbstentionPolicy` via `confidence_policy=` yields `accept`,
`review`, or `unavailable` along with `policy_sha256`. Schema-4
`AnalysisReceipt` records calibration/policy hashes, runtime-variant evidence,
and composed output/post-processing identity (schemas 1–3 remain readable
without synthesizing missing fields).

### Sentence boundaries and precedence

`greek.segment_text()` returns a `SegmentationResult` containing the exact
source string, ordered `SentenceBoundary` entries (half-open `start`/`end` or
`start_char`/`end_char` code-point offsets retaining punctuation), policy name,
`policy_id`, and `provenance` (`rule`, `explicit`, or `plugin`).
`greek.sentences()` remains a trimmed string projection with terminal marks
removed. `SegmentationResult.to_json()` and `.from_json()` validate that
boundary slices, spans, policy, and IDs agree.

For `pipeline()`, `sentence_policy` runs before tokenization. For
`pipeline_tokens()`, complete contiguous runs of `Token.alignment.sentence_id`
take precedence over punctuation, named policies, and custom segmenters
(partial, non-contiguous, or cross-document IDs raise `ValueError`). Without
explicit IDs, the selected policy runs on the token stream, and editorial
punctuation marked `UNCLEAR`, `RESTORED`, or `LOST` does not create a boundary.
Only each sentence's terminal record carries `boundary_*` fields.

### Single-form lemmatization evidence

```python
from aegean import greek

for form in ['ἀνθρώπου', 'δούλου', 'γράφομεν', 'ἐσκήνωσεν']:
    lemma, source = greek.lemmatize_sourced(form)
    print(f'{form:12} -> {lemma:12} {source.value:12} needs_review={greek.needs_review(source)}')
```

```text
ἀνθρώπου     -> ἄνθρωπος     seed         needs_review=False
δούλου       -> δούλος       rule         needs_review=False
γράφομεν     -> γράφω        rule         needs_review=False
ἐσκήνωσεν    -> ἐσκήνωσεν    unresolved   needs_review=True
```

See [Reading a Parse](Reading-a-Parse) and [Greek NLP](Greek-NLP) for full
parsing and neural runtime details.

---

## 5. `fingerprint()` and `copy()`

`corpus.fingerprint()` computes a length-prefixed SHA-256 over all token-level
analysable content: `script_id`, data identity (`provenance.data_version` when
it names the dataset rather than a package release), document IDs, every token's
`text`, `kind`, `status`, `signs`, `glyphs`, `alt`, `annotations`, optional
`alignment` and `form_state`, and `subset:`/`merged:`/`appended:` provenance
notes. It excludes document metadata (`site`, `period`, ...), `lines`,
`line_no`, `position`, translations, transcriptions, and the installed package
version. Two corpora with the same fingerprint have identical analysable token
streams, so `aegean.cache` uses it as its cache key.

`corpus.copy()` returns an independent copy with fresh document, token, line,
translation, `Token.annotations`, and `Sign.attrs` containers while sharing
immutable `DocumentMeta` and `Provenance` instances. `aegean.load()` returns a
copy so caller edits never mutate the cached corpus.

```python
import aegean

a = aegean.load("lineara")
b = a.copy()
print("same fingerprint after copy:", a.fingerprint() == b.fingerprint())
# Stable across releases unless the corpus content or data_version changes.

b.get("HT13").tokens[0].annotations["my_note"] = "checked against GORILA"
print("original untouched:", a.get("HT13").tokens[0].annotations)
print("fingerprints now differ:", a.fingerprint() != b.fingerprint())

c = aegean.load("lineara")
print("fresh load clean:", c.get("HT13").tokens[0].annotations == {})
```

```text
same fingerprint after copy: True
original untouched: {}
fingerprints now differ: True
fresh load clean: True
```

---

## 6. Persistence contracts

- **JSON (`Corpus.to_json` / `Corpus.from_json`) is lossless.** All token
  fields, optional `alignment`, `source_text`, and `form_state`, `lines`,
  `DocumentMeta`, `sign_inventory`, and `provenance` round-trip exactly.
  (`Corpus.to_dict()` is a lossy summary dictionary and not a round-trip
  format.)
- **SQLite (`Corpus.to_sql` / `Corpus.from_sql`, `aegean.db`) is lossless and
  supports FTS5.** The `tokens` table stores an explicit `token_order` column so
  tokens with `position=None` or non-monotonic positions reload in list order.
  Pre-0.19.4 databases fall back to `position` on read and migrate on the first
  `append=True` write; schema-1 and schema-2 databases load with absent
  alignment/form-state values and migrate atomically to schema 3 on append. For
  large corpora, `aegean.db.annotate_sqlite_job` (`aegean db annotate`) runs
  resumable document-by-document annotation with lease protection, inspected via
  `aegean.db.job_status`.
- **Schema versions guard forward compatibility.** `SCHEMA_VERSION` (currently
  `3`; stored as `_meta.schemaVersion` in JSON and `schema_version` in SQLite)
  increments only for changes an older reader would misread. Loading a newer
  schema version raises `ValueError`; older or missing versions load cleanly
  without interpreting unrecognized keys as schema-3 fields.

```python
import pathlib
import tempfile
from aegean import Corpus

corpus = Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="lineara")

back = Corpus.from_json(corpus.to_json())
print("JSON round-trip lossless:", back.fingerprint() == corpus.fingerprint())
print("status survived:", back.get("X2").tokens[1].status)

db_path = pathlib.Path(tempfile.mkdtemp()) / "myfind.db"
corpus.to_sql(db_path)
again = Corpus.from_sql(db_path)
print("SQLite round-trip lossless:", again.fingerprint() == corpus.fingerprint())
```

```text
JSON round-trip lossless: True
status survived: ReadingStatus.UNCLEAR
SQLite round-trip lossless: True
```

Token list order is preserved even when `position` is `None`:

```python
import pathlib
import tempfile
from aegean import Corpus, Document, Provenance, Token, TokenKind

doc = Document(
    id="D1", script_id="custom",
    tokens=[
        Token(text="alpha", kind=TokenKind.WORD, position=0),
        Token(text="beta", kind=TokenKind.WORD, position=None),
        Token(text="gamma", kind=TokenKind.WORD, position=1),
    ],
    lines=[[0, 1, 2]],
)
corpus = Corpus([doc], provenance=Provenance(source="demo"), script_id="custom")

db_path = pathlib.Path(tempfile.mkdtemp()) / "order.db"
corpus.to_sql(db_path)
back = Corpus.from_sql(db_path)
print([(t.text, t.position) for t in back.get("D1").tokens])
print("list order preserved:", back.fingerprint() == corpus.fingerprint())
```

```text
[('alpha', 0), ('beta', None), ('gamma', 1)]
list order preserved: True
```

---

## 7. Extension points

### 7.1 Building a corpus from records

`Corpus.from_records` converts plain dictionaries into a `Corpus`. Each record
requires `"id"` plus `"lines"` (list of token lists), `"words"` (flat list), or
`"text"` (whitespace-tokenized string). Individual tokens may be strings or
dicts (`{"text": ..., "kind": ..., "status": ..., "alt": ...}`). Omitted `kind`
is inferred (numerals by parseability, others as words), hyphenated tokens split
into `signs`, positions are assigned sequentially, and `lines` indices are built
automatically. For files and CSVs, use `aegean.io.from_text`,
`aegean.io.from_csv`, or `aegean import`.

### 7.2 Registering a custom loader

Registering a loader exposes a custom corpus to `aegean.load(...)` across
Python, CLI, TUI, and MCP:

```python
import aegean
from aegean import Corpus, Provenance
from aegean.core.corpus import register_loader

prov = Provenance(
    source="Field notebook 2026",
    license="CC BY 4.0",
    citation="Pavlicek, R. (2026). Inscriptions from My Site.",
)
mine = Corpus.from_records(
    [{"id": "MS1", "text": "KU-RO 10", "meta": {"site": "My site"}}],
    script_id="lineara", provenance=prov,
)
register_loader("myfind", lambda: mine)

loaded = aegean.load("myfind")
print(len(loaded), "document(s):", loaded.get("MS1").words[0].text)
print(loaded.cite())

loaded.get("MS1").tokens[0].annotations["scratch"] = "x"
print("registered instance clean:", aegean.load("myfind").get("MS1").tokens[0].annotations == {})
```

```text
1 document(s): KU-RO
Pavlicek, R. (2026). Inscriptions from My Site.
registered instance clean: True
```

To add a new script rather than a new corpus, subclass `aegean.core.Script`,
call `register()`, and register a loader (see [Architecture](Architecture)).

### 7.3 Adding annotations and review round-tripping

Custom keys in `Token.annotations` survive JSON and SQLite round-trips
untouched; built-in writers never strip unknown keys.

Review CSVs (`to_review_table` / `from_review_table`) support:

- `selection="all"` (default), `"flagged"` (existing review flag), or
  `"unverified"` (words lacking `lemma_verified="true"`), plus
  `priority="calibrated_risk"` and `budget=N` when calibrated confidence is
  present.
- Per-field decisions (`decision_lemma`, `decision_pos`, `decision_morph`):
  `accept`, `correct`, `defer`, or `reject`. Accepting verifies the unchanged
  displayed prediction; correcting requires a nonempty different `correct_*`
  value and records `lemma_source="user"` while preserving `<field>__pred`;
  `defer` and `reject` leave the field unverified. Explicit decisions fail if
  the target prediction changed since export. Blank decisions keep legacy
  behavior (blank or unchanged cells do nothing).
- Guarded `form_*` and `form_state_json` columns when typed editorial forms are
  present (refusing mismatched typed state on apply while remaining compatible
  with older CSVs).
- `reviewer_evidence` and dated `review_history` (including per-field
  attribution after merged multi-reviewer tables).
- Re-annotation marks existing lemma/POS decisions `stale` without transferring
  prior approvals to new predictions or invalidating unchanged source-morphology
  reviews.

```python
import csv
import pathlib
import tempfile
from aegean import Corpus, greek
from aegean.io import to_review_table, from_review_table

corpus = Corpus.from_records(
    [{"id": "frag1", "text": "ὁ λόγος σὰρξ ἐγένετο"}], script_id="greek"
)
annotated = greek.annotate_corpus(corpus)
tok = annotated.get("frag1").tokens[3]
fields = ("lemma", "lemma_source", "lemma_verified", "upos")
print("after annotate:", {key: tok.annotations[key] for key in fields})

work = pathlib.Path(tempfile.mkdtemp())
n = to_review_table(annotated, work / "review.csv", selection="flagged")
print("rows exported:", n)

with open(work / "review.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    if row["token"] == "ἐγένετο":
        row["correct_lemma"] = "γίγνομαι"
        row["correct_pos"] = "VERB"
        row["reviewer_note"] = "aor. mid. of γίγνομαι"
with open(work / "review.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

fixed = from_review_table(work / "review.csv", annotated, reviewer="RP")
tok = fixed.get("frag1").tokens[3]
print("after apply:", {key: tok.annotations[key] for key in fields})
print("original prediction:", tok.annotations["lemma__pred"])
print("provenance note:", fixed.provenance.notes[-1].split(" (")[0])
```

```text
after annotate: {'lemma': 'ἐγένετο', 'lemma_source': 'unresolved', 'lemma_verified': 'false', 'upos': 'NOUN'}
rows exported: 2
after apply: {'lemma': 'γίγνομαι', 'lemma_source': 'user', 'lemma_verified': 'true', 'upos': 'VERB'}
original prediction: ἐγένετο
provenance note: review: 1 tokens corrected by RP
```

Aligned tokens join on `source_token_id` and verify source spans on apply;
unaligned tables join on `doc_id` plus `position` and raise `ValueError` on
token text mismatch. See [When the Tool Is Wrong](When-the-Tool-Is-Wrong).

### 7.4 Invariants for hand-constructed corpora

When building `Document` and `Token` objects directly instead of via
`from_records`:

- **Valid `lines` indices.** Every index must satisfy `0 ≤ i < len(tokens)`.
  JSON and SQLite readers reject out-of-range indices on load; in-memory
  violations raise `IndexError` in `line_tokens` or exporters.
- **Unique sequential `position` values.** Persistence tolerates `None` and
  out-of-order positions (§6), but unaligned review export skips `position=None`
  tokens and relies on unique `(doc_id, position)` keys.
- **Valid enum members.** `status` must be a `ReadingStatus` member and `kind` a
  `TokenKind` member; invalid strings raise `ValueError`.
- **Accurate `TokenKind`.** Word-level analysis, review export, and annotation
  select `TokenKind.WORD` tokens.
- **String values in `annotations`.** Avoid writing reserved keys
  (`<field>__pred`, `lemma_source`, `lemma_resolved`, `lemma_verified`,
  `review_recommended`, `lemma_known`, `review_status`, `reviewed_by`,
  `review_note`, `review_evidence`, `review_history`, and per-field review keys)
  unless following their contract.
- **Unique document IDs.** Duplicate IDs within one `Corpus` collapse with a
  warning, keeping the last.

Invalid structures raise `ValueError`:

```python
import json
from aegean import Corpus, Document, Token, TokenKind

# (a) Out-of-range line index rejected on read
bad = Corpus([Document(id="D1", script_id="custom",
                       tokens=[Token(text="alpha", kind=TokenKind.WORD, position=0)],
                       lines=[[0, 7]])], script_id="custom")
blob = json.loads(bad.to_json())
try:
    Corpus.from_dict(blob)
except ValueError as e:
    print("ValueError:", e)

# (b) Unknown ReadingStatus rejected at construction
try:
    Corpus.from_records([{"id": "X", "lines": [[{"text": "A", "status": "probable"}]]}])
except ValueError as e:
    print("ValueError:", e)

# (c) Future schema version rejected with upgrade message
blob["_meta"]["schemaVersion"] = 99
try:
    Corpus.from_dict(blob)
except ValueError as e:
    print("ValueError:", e)
```

```text
ValueError: document 'D1': line 0 references token index 7, but the document has 1 token(s); the source is malformed
ValueError: 'probable' is not a valid ReadingStatus
ValueError: this corpus file uses schema version 99, but this pyaegean understands up to 3 — upgrade pyaegean to read it
```

One validation gap to check before publishing a hand-built corpus: `to_json()`
does not validate `lines` indices on write (example (a) fails on read). Run a
single `Corpus.from_json(corpus.to_json())` round-trip check before distributing
custom corpus files.

---

**See also:** [Architecture](Architecture) · [For Specialists](For-Specialists) ·
[Using Critical Editions](Using-Critical-Editions) ·
[When the Tool Is Wrong](When-the-Tool-Is-Wrong) · [Reading a Parse](Reading-a-Parse) ·
[Data & Provenance](Data-and-Provenance) · [Greek NLP](Greek-NLP) ·
[Interoperability](Interoperability)
