# Data model

This page makes the internal structure transparent so you can extend it with
confidence: every field of every core object, what may live in a token's
`annotations` dict, how the pipeline's records relate to corpus tokens, what
`fingerprint()` and `copy()` actually guarantee, the persistence contracts, and
the invariants your own corpus or loader must hold (including exactly where a
wrong extension breaks a round-trip). [Architecture](Architecture) is the
companion tour of the layering and the serialization/query surface; come here
when you are building on the objects themselves.

Every example below was run against the installed package; the output shown is
the real output.

---

## 1. The object hierarchy

```
Corpus                          a collection of documents + shared context
├── documents: list[Document]   one per inscription / tablet / text
│   ├── tokens: list[Token]     the transliterated text stream, in order
│   ├── lines:  list[list[int]] each physical line = a list of indices into tokens
│   ├── source_text: str | None exact source snapshot for aligned documents
│   └── meta:   DocumentMeta    site, period, scribe, support, findspot, name, …
├── sign_inventory: SignInventory | None    the script's Sign objects, indexed
├── provenance: Provenance | None           source, license, citation, notes
└── script_id: str                          "lineara", "greek", "custom", …
```

Three things to internalize:

- **`lines` holds indices, not tokens.** A line is a list of positions into
  `document.tokens`; `document.line_tokens` resolves them for you. This is what
  lets a token belong to the physical layout without being stored twice.
- **`Token` and `Sign` are frozen dataclasses** (edit one with
  `dataclasses.replace`), each with a single mutable escape hatch: the
  per-token `annotations` dict and the per-sign `attrs` dict. `Document` is
  mutable.
- **Source alignment is typed, not an annotation convention.** An aligned token
  carries an immutable `SourceAlignment`; its document retains the exact
  `source_text` those offsets address.
- **Document ids are unique within a corpus.** Constructing a `Corpus` with
  duplicate ids collapses them (keeping the last) with a warning; `merge`
  refuses duplicates by default (`dedupe="error"`).

```python
import aegean

corpus = aegean.load("lineara")          # Corpus
doc = corpus.get("HT13")                 # Document
print(type(corpus).__name__, "of", len(corpus), "documents")
print(doc.id, doc.script_id, "-", len(doc.tokens), "tokens on", len(doc.lines), "lines")
print("lines:", doc.lines)               # each line = a list of indices into doc.tokens
tok = doc.tokens[0]                      # Token
print("first token:", tok.text, tok.kind, tok.signs)
print("line 2 text:", [t.text for t in doc.line_tokens[1]])
```

```
Corpus of 1721 documents
HT13 lineara - 22 tokens on 8 lines
lines: [[0, 1, 2, 3, 4], [5, 6, 7], [8, 9], [10, 11, 12], [13, 14], [15, 16], [17, 18], [19, 20, 21]]
first token: KA-U-DE-TA TokenKind.WORD ('KA', 'U', 'DE', 'TA')
line 2 text: ['RE-ZA', '5', '¹⁄₂']
```

---

## 2. `Token`, field by field

| Field | Type | Meaning |
|---|---|---|
| `text` | `str` | the transliteration as written, e.g. `KU-RO` or `Λόγος,` |
| `kind` | `TokenKind` | `word` / `logogram` / `numeral` / `separator` / `punct` / `unknown` |
| `signs` | `tuple[str, ...]` | decomposed sign labels, e.g. `("KU", "RO")`; empty for alphabetic text |
| `glyphs` | `str \| None` | the Unicode form, when known |
| `line_no` | `int \| None` | which physical line the token sits on |
| `position` | `int \| None` | the token's index within the document's token stream |
| `status` | `ReadingStatus` | editorial certainty (§3); defaults to `CERTAIN` |
| `alt` | `tuple[str, ...]` | alternate readings (EpiDoc `<app>`/`<rdg>`); `text` is the preferred reading |
| `annotations` | `dict[str, str]` | script-specific per-token facts; the extension surface (below) |
| `alignment` | `SourceAlignment \| None` | exact source identity, span, whitespace, and normalization provenance |
| `form_state` | `TokenFormState \| None` | typed diplomatic, editorial, and model-input forms with ordered apparatus segments |

`kind` is load-bearing: `document.words`, word-scope queries, the review
export, and `annotate_corpus` all gate on `TokenKind.WORD`, so a token
mislabeled `unknown` silently disappears from every word-level analysis.
`position` is pure data (it may be `None`, and persistence never reorders by
it, see §6). The review loop prefers `alignment.source_token_id` when present
and retains `document.id` + `position` as the compatibility join for older
tables, so keep `position` equal to the token's list index in unaligned documents.

A gold-annotated token from the New Testament corpus shows a full set of
fields in the wild:

```python
import aegean

nt = aegean.load("nt")
doc = nt.get("John 1")
tok = doc.tokens[4]                       # λόγος, the fifth token of John 1:1
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

```
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

### What lives in `annotations`

`annotations` is a flat `dict[str, str]` (keep the values strings; the
built-in writers do, including the booleans, stored as `"true"`/`"false"`). It
is covered by `fingerprint()`, survives the JSON and SQLite round-trips
unchanged, and spreads into token-level DataFrames. The keys in use, by who
writes them:

| Written by | Keys | Meaning |
|---|---|---|
| the NT corpus (gold) | `lemma`, `morph`, `strongs`, `gloss`, `normalized`, `upos`, `ref` | edition-supplied annotation |
| `greek.annotate_corpus` | `lemma`, `upos`, `lemma_source`, `lemma_resolved`, `lemma_verified`, `review_recommended` | machine analysis, exact provenance, and separate resolution/review state (§4) |
| `aegean.io.from_review_table` | `<field>__pred`, `review_status`, `reviewed_by`, `review_note` | the human-correction audit trail (§7.3) |
| you | anything else | your own per-token facts |

The `<field>__pred` convention is the audit trail: when a reviewer's
correction is applied, the corrected value replaces the machine value under
its normal key (`lemma`, `upos`, `morph` or `feats`) and the machine value the
reviewer saw is preserved under `lemma__pred` / `upos__pred` / `morph__pred`.
Nothing is overwritten silently; treat any key ending in `__pred` as reserved
for that convention. `lemma_source` holds a `LemmaSource` evidence-class value
(`attested` / `neural_lookup` / `neural_edit` / generic `neural` / `rule` / `seed` /
`paradigm` / `identity` / `unresolved` / `punct` / `user`). `lemma_resolved`,
`lemma_verified`, and `review_recommended` keep distinct questions separate; the
review export uses the explicit review signal. The legacy `lemma_known` key is a
deprecated compatibility alias for `lemma_resolved`.

### Lossless source alignment

`SourceAlignment` keeps source mapping out of the free-form annotations dict:

| Field | Meaning |
|---|---|
| `document_id`, `sentence_id` | owning source and sentence identities |
| `source_token_id` | stable identity for an unchanged exact source snapshot |
| `original_text` | exact source slice |
| `start_char`, `end_char` | half-open Python Unicode code-point offsets |
| `whitespace_before` | exact Unicode whitespace since the preceding token |
| `normalized_text` | model-facing normalized form |
| `normalization_ops` | ordered operations, currently `unicode:nfc` when NFC changes text |

An aligned `Document` sets `source_text`; `validate_source_alignment()` checks
every slice, gap, document ID, source-token ID, order, and overlap. Schema-2 JSON
and SQLite preserve the value. A schema-1 corpus still loads with
`source_text=None` and `alignment=None`.

```python
from aegean import Document
from aegean import greek

source = "  α\u0301\tλόγος."
tokens = greek.tokenize_aligned(source, document_id="demo")
doc = Document("demo", "greek", tokens, [list(range(len(tokens)))], source_text=source)
doc.validate_source_alignment()

tokens[0].alignment.original_text       # 'ά'
tokens[0].alignment.normalized_text     # 'ά'
source[tokens[0].alignment.start_char:tokens[0].alignment.end_char] == "α\u0301"  # True
```

### Typed editorial forms and model input

`Token.text` is the preferred/display token used by corpus views. When an edition
exposes more than one spelling, `Token.form_state` keeps the distinctions explicit:

| Field | Meaning |
|---|---|
| `diplomatic` | the original or diplomatic form supplied by the edition |
| `regularized` | an optional editorial spelling, such as a corrected or expanded form |
| `normalized` | an optional normalized form used by a preprocessing convention |
| `model_input` | the exact string handed to an analyzer, after the selected form and any recorded operations |
| `model_input_source` | whether that input came from `diplomatic`, `regularized`, `normalized`, or an explicit value |
| `segments` | ordered pieces with `certain`, `restored`, `unclear`, or `lost` status and optional semantic source references |

These fields have different evidential roles. `diplomatic`, `regularized`,
`normalized`, and the segment statuses describe the source or an editorial
representation. `model_input` describes a computation. It must not be read as a
new edition reading. For `pipeline_tokens()`, selection is deterministic:
explicit `model_input`, then `regularized`, then `normalized`, then `diplomatic`,
then the legacy `Token.text` fallback. The returned `TokenRecord` retains the
state and records the exact input and ordered operations, including an NFC
operation when a neural backend changes the string's Unicode normalization.

Token-carrier EpiDoc choices such as
`<choice><reg>…</reg><orig>…</orig></choice>` and apparatus elements such as
`<supplied>`, `<unclear>`, and `<gap>` populate this typed value. The generic
EpiDoc writer emits semantic choices and apparatus, but does not promise
byte-identical XML. A state with no apparatus can still be constructed directly
with `TokenFormState` for a controlled preprocessing step.

### CoNLL-U uses a separate lossless structural model

Treebank rows are not forced into `Corpus.Token`. `greek.UDDocument` preserves ordered
comments and complete ten-column CoNLL-U rows through `UDSentence.rows` and
`UDSentence.items`. Integer-ID words remain available through `UDSentence.tokens`, while
`UDMultiwordToken`, `UDEmptyNode`, typed enhanced dependencies, and ordered MISC entries
retain structures that are not syntactic words. `UDSentence.projection` makes the mapping
between those two views explicit.

`greek.load_conllu_document()` plus `greek.write_conllu()` is the exact document
round-trip. Use `strict=True` when validation is required; the lenient default retains
valid structure and opaque malformed rows for inspection while keeping the legacy word
projection stable. The v3 neural model consumes only that word projection, so structural
gold rows are never presented as its predictions.

---

## 3. `ReadingStatus`: where each status comes from

Every token carries an editorial certainty following Leiden / EpiDoc
conventions. The four states are exhaustive, and unknown values are rejected
at construction, so the enum is a real invariant:

| Status | Meaning | Set by |
|---|---|---|
| `certain` | securely read | the default |
| `unclear` | damaged but read | Leiden underdot; EpiDoc `<unclear>`; erasures (`⟦ ⟧`); illegible-sign marks in the Cypriot apparatus |
| `restored` | editorially supplied | Leiden `[ ]`; EpiDoc `<supplied>` |
| `lost` | not preserved / lacuna | Leiden `[---]`; EpiDoc `<gap>` or `<supplied reason="undefined">` |

Concretely: the bundled Linear A and Cypriot loaders decode their editions'
Leiden apparatus; the six currently hosted epigraphy and papyri assets
(`isicily`, `iip`, `iospe`, `igcyr`, `edh`, `ddbdp`) expose aggregate
`ReadingStatus` values, and a word touched by more than one state carries the
most severe one. Their legacy assets do not carry the newer typed
`TokenFormState`. A token-carrier EpiDoc import can populate both the aggregate
status and the typed state from the same elements, and the EpiDoc writer emits
them semantically; `Corpus.from_records` takes a `"status"` string per token (§7.1). See
[Using Critical Editions](Using-Critical-Editions) for working with them.

```python
import aegean
from collections import Counter

corpus = aegean.load("lineara")
print(dict(Counter(t.status.value for d in corpus for t in d.tokens)))
print([(t.text, t.status.value) for t in corpus.get("HT23b").tokens][:8])
```

```
{'certain': 5734, 'lost': 552, 'unclear': 120}
[('NI-RA', 'certain'), ('CYP', 'certain'), ('¹⁄₃', 'certain'), ('OLE', 'certain'), ('¹⁄₃', 'certain'), ('MI+JA+RU', 'certain'), ('MU', 'certain'), ('QA2+[?]+PU', 'unclear')]
```

---

## 4. `TokenRecord` is not a `Token`

A common confusion. `Token` is **corpus data**: what an edition says, stored
in documents, persisted and cited. `greek.TokenRecord` is **pipeline output**:
one token's analysis from `greek.pipeline()`, ephemeral, never stored in a
corpus. Both may carry the same immutable `SourceAlignment`, but their linguistic
fields and persistence roles are otherwise separate.

| `TokenRecord` field | Meaning |
|---|---|
| `sentence` | 0-based sentence number within the input text |
| `index` | 1-based token position within its sentence |
| `text` | the token |
| `upos` | universal POS tag |
| `lemma` | the lemma |
| `lemma_source` | the lemma's evidence class (`LemmaSource`) |
| `lemma_resolved` | whether a real lemma decision exists rather than a surface fallback |
| `lemma_verified` | whether a human reviewer explicitly verified or corrected the lemma |
| `review_recommended` | whether the lemma should be routed to human review |
| `head` | `index` of the head record in the same sentence; `0` = root, `None` = no parse |
| `relation` | dependency relation. Note the name: it is `relation`, **not** `deprel` |
| `xpos`, `feats` | 9-char positional tag / UD FEATS; filled by the neural pipeline only |
| `lemma_known` | deprecated compatibility alias for `lemma_resolved` |
| `alignment` | exact source identity, original/normalized text, span, and whitespace |
| `form_state` | typed editorial forms and exact model input when records came from `pipeline_tokens()` |
| `boundary_policy`, `boundary_policy_id` | named sentence policy and stable policy identity on the sentence's terminal record |
| `boundary_provenance`, `boundary_confidence` | boundary evidence class; built-in rules have `None` confidence, while plugins may supply `[0, 1]` metadata |
| `boundary_start_char`, `boundary_end_char` | half-open source span for that sentence when all token alignments prove it; otherwise `None` |

```python
from aegean import greek

records = greek.pipeline("ὁ λόγος σὰρξ ἐγένετο καὶ ἐσκήνωσεν ἐν ἡμῖν.")
for r in records:
    print(f"{r.sentence} {r.index} {r.text:10} {r.upos:6} {r.lemma:10} "
          f"{r.lemma_source.value:14} resolved={r.lemma_resolved!s:5} "
          f"verified={r.lemma_verified!s:5} review={r.review_recommended!s:5} "
          f"head={r.head} relation={r.relation} xpos={r.xpos} feats={r.feats}")
```

```
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

### Sentence boundaries and precedence

`greek.segment_text()` returns a `SegmentationResult` containing the exact source,
ordered `SentenceBoundary` values, a named policy, a stable `policy_id`, and a
`provenance` value (`rule`, `explicit`, or `plugin`). Boundary `start`/`end` (also
exposed as `start_char`/`end_char`) are half-open Python code-point offsets. The
rich result retains punctuation in each source slice; `greek.sentences()` remains
the compatibility projection with trimmed strings and terminal marks removed.
`SegmentationResult.to_json()` and `.from_json()` use a strict schema and verify
that boundary text, spans, policy, and IDs agree.

For raw `pipeline()` input, `sentence_policy` selects the named rules before
tokenization. For `pipeline_tokens()` input, complete contiguous runs of
`Token.alignment.sentence_id` are explicit sentence metadata and take precedence
over punctuation, the named policy, and any segmenter callback. Partial,
non-contiguous, or cross-document IDs are rejected. If explicit IDs are absent,
the selected policy is applied to the typed token stream; editorial punctuation
whose status is `UNCLEAR`, `RESTORED`, or `LOST` does not create an observed boundary.
Only the terminal record receives `boundary_*` metadata. A missing source span means
the alignments did not prove one, not that an approximate offset was invented.

This is the zero-dependency baseline being honest: the forms it cannot ground
come back `unresolved` with the surface form as the lemma, never a fabricated
citation form. With the neural pipeline active (`greek.use_neural_pipeline()`)
every field fills and grounded lemmas read `neural`. The evidence classes are
visible one form at a time too:

```python
from aegean import greek

for form in ['ἀνθρώπου', 'δούλου', 'γράφομεν', 'ἐσκήνωσεν']:
    lemma, source = greek.lemmatize_sourced(form)
    print(f'{form:12} -> {lemma:12} {source.value:12} needs_review={greek.needs_review(source)}')
```

```
ἀνθρώπου     -> ἄνθρωπος     seed         needs_review=False
δούλου       -> δούλος       rule         needs_review=False
γράφομεν     -> γράφω        rule         needs_review=False
ἐσκήνωσεν    -> ἐσκήνωσεν    unresolved   needs_review=True
```

The bridge between the two worlds is `greek.annotate_corpus` (§7.3): it runs
the active pipeline over a corpus's existing word tokens and writes `lemma`,
`upos`, and the evidence class into `Token.annotations`, so pipeline output
becomes corpus data you can export, review, and persist. For reading parses
themselves, see [Reading a Parse](Reading-a-Parse) and [Greek NLP](Greek-NLP).

---

## 5. What `fingerprint()` covers and what `copy()` guarantees

`corpus.fingerprint()` is a stable sha256 over everything a **token-level
analysis** can see: the script id, the provenance `data_version`, each
document's id, and every token's `text`, `kind`, `status`, `signs`, `glyphs`,
`alt`, and `annotations` (plus source alignment and typed form state when
present, and any `subset:` / `merged:` / `appended:` provenance note). Fields
are length-prefixed, so no crafted value can collide
two corpora. It deliberately **excludes** document metadata (site, period, …),
`lines`, `line_no`, `position`, translations, and transcriptions: two corpora
with equal fingerprints have the same analysable content in the same token
order, which is why it is the cache key for `aegean.cache`-memoised analyses.
It is not a byte-equality check on the whole object.

`corpus.copy()` returns a structurally independent corpus: fresh document,
token, line, and translation containers, and (the part that matters) a fresh
`annotations` dict per token and `attrs` dict per sign. Mutating a copy never
leaks into the original, a sibling copy, or a later `load()` of the same
cached corpus; `load()` itself hands out a copy for exactly this reason. The
frozen scalars, `DocumentMeta`, and `Provenance` are shared, which is safe
because they are immutable.

```python
import aegean

a = aegean.load("lineara")
b = a.copy()
print("same fingerprint after copy:", a.fingerprint() == b.fingerprint())
# the hash folds provenance.data_version, so it is stable within a release but
# changes across releases — compare fingerprints, never hard-code the hex value

# annotations is the one mutable slot on a (frozen) Token — and the copy owns its own dicts
b.get("HT13").tokens[0].annotations["my_note"] = "checked against GORILA"
print("original untouched:", a.get("HT13").tokens[0].annotations)
print("fingerprints now differ:", a.fingerprint() != b.fingerprint())

# a fresh load is unaffected too: load() itself hands out a copy
c = aegean.load("lineara")
print("fresh load clean:", c.get("HT13").tokens[0].annotations == {})
```

```
same fingerprint after copy: True
original untouched: {}
fingerprints now differ: True
fresh load clean: True
```

---

## 6. Persistence contracts

Three formats, three different promises:

- **JSON (`to_json` / `from_json`) is lossless.** Every token field, optional
  source alignment and exact source text, optional typed form state, the lines,
  full document metadata, the sign inventory, and provenance survive exactly.
  (`to_dict` is the *lossy* quick-interop summary; don't round-trip through it.)
- **SQLite (`to_sql` / `from_sql`, `aegean.db`) is lossless and adds FTS
  search.** The tokens table carries an explicit `token_order` column: the
  token's index in the document's list, written at save time. Reload order
  comes from `token_order`, never from `position`, so a `position=None` token
  (SQL `NULL`, which would otherwise sort first) or out-of-order positions
  survive in place. Databases written before 0.19.4 lack the column; they are
  read via a `position` fallback and migrated in place on the first
  `append=True` write. Schema-1 databases also lack A4 source/alignment columns;
  they load with absent values and migrate to schema 2 on append. Schema-1 and
  schema-2 databases have no A6 form-state column; an append migrates them to
  schema 3 atomically, and old rows keep `form_state=None`.
- **Schema versions gate forward-compatibility only.** `SCHEMA_VERSION`
  (stored as `_meta.schemaVersion` in JSON, `schema_version` in the SQLite
  `meta` table and on `Provenance`) is bumped only for changes an older reader
  would *misread*. Loading a file with a **newer** version raises a
  `ValueError` naming the fix; an older or missing version loads normally.
  Additive optional fields (e.g. `edition_fidelity`) deliberately do not bump
  it. A schema-1 or schema-2 JSON corpus loads with no typed form state even if
  unrelated future-looking keys are present; it is not silently interpreted as
  schema 3.

```python
import aegean
from aegean import Corpus

corpus = Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="lineara")

# JSON: lossless both ways
back = Corpus.from_json(corpus.to_json())
print("JSON round-trip lossless:", back.fingerprint() == corpus.fingerprint())
print("status survived:", back.get("X2").tokens[1].status)

# SQLite: same contract, via a file
import tempfile, pathlib
db = pathlib.Path(tempfile.mkdtemp()) / "myfind.db"
corpus.to_sql(db)
again = Corpus.from_sql(db)
print("SQLite round-trip lossless:", again.fingerprint() == corpus.fingerprint())
```

```
JSON round-trip lossless: True
status survived: ReadingStatus.UNCLEAR
SQLite round-trip lossless: True
```

And the `token_order` contract under stress: a hand-built document whose
middle token has no position at all.

```python
import pathlib, tempfile
from aegean import Corpus, Document, Provenance, Token, TokenKind

# a document whose SECOND token has no position (e.g. an editorial insertion)
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

db = pathlib.Path(tempfile.mkdtemp()) / "order.db"
corpus.to_sql(db)
back = Corpus.from_sql(db)
print([ (t.text, t.position) for t in back.get("D1").tokens ])
print("list order preserved:", back.fingerprint() == corpus.fingerprint())
```

```
[('alpha', 0), ('beta', None), ('gamma', 1)]
list order preserved: True
```

---

## 7. Extension points

### 7.1 Build a corpus from your own records

`Corpus.from_records` turns plain dicts into first-class corpus data: each
record needs an `"id"` and its text as `"lines"` (list of lines, each a list
of tokens), `"words"` (one flat line), or `"text"` (whitespace-tokenized). A
token is a string or a dict `{"text": …, "kind": …, "status": …, "alt": …}`;
kind is inferred when omitted (numerals by parseability, the rest words), and
hyphenated tokens get their `signs` split. It maintains the invariants of §7.4
for you: positions are assigned sequentially and lines index correctly. The
`corpus` built in §6 is exactly this. If your material is a text file or CSV,
the `aegean.io` importers and `aegean import` build the same structure.

### 7.2 Register a loader

A loader makes your corpus loadable by name everywhere a registered id works
(Python, CLI, TUI, MCP). Attach a real `Provenance` so citations stay honest:

```python
import aegean
from aegean import Corpus, Provenance
from aegean.core.corpus import register_loader

prov = Provenance(
    source="My 2026 field notebook",
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

# load() returns a copy, so a caller's edits never reach the registered instance
loaded.get("MS1").tokens[0].annotations["scratch"] = "x"
print("registered instance clean:", aegean.load("myfind").get("MS1").tokens[0].annotations == {})
```

```
1 document(s): KU-RO
Pavlicek, R. (2026). Inscriptions from My Site.
registered instance clean: True
```

(A new *script*, as opposed to a new corpus, is a plugin: subclass
`aegean.core.Script`, `register()` it, and register a loader; the core never
imports scripts. See [Architecture](Architecture).)

### 7.3 Add annotations without breaking round-trips

Adding keys to `Token.annotations` is always round-trip-safe through JSON and
SQLite; the built-in machinery only ever adds keys, never strips unknown ones.
The review CSV also carries guarded `form_*` columns and a `form_state_json`
column when a token has typed editorial forms. Applying corrections refuses a
row whose typed state no longer matches the exported corpus, while an older
review file without those columns remains compatible.
The full annotate → export → correct → apply loop, showing the `<field>__pred`
audit trail land on the token:

```python
import csv, pathlib, tempfile
from aegean import Corpus, greek
from aegean.io import to_review_table, from_review_table

corpus = Corpus.from_records(
    [{"id": "frag1", "text": "ὁ λόγος σὰρξ ἐγένετο"}], script_id="greek"
)
annotated = greek.annotate_corpus(corpus)          # fills lemma/upos + evidence class
tok = annotated.get("frag1").tokens[3]             # ἐγένετο — the baseline can't resolve it
print("after annotate:", dict(sorted(tok.annotations.items())))

work = pathlib.Path(tempfile.mkdtemp())
n = to_review_table(annotated, work / "review.csv", only_needs_review=True)
print("rows exported:", n)

# simulate the reviewer: fill correct_lemma on the ἐγένετο row
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
print("after apply:", dict(sorted(tok.annotations.items())))
print("provenance note:", fixed.provenance.notes[-1])
```

```
after annotate: {'lemma': 'ἐγένετο', 'lemma_known': 'false', 'lemma_resolved': 'false', 'lemma_source': 'unresolved', 'lemma_verified': 'false', 'review_recommended': 'true', 'upos': 'NOUN'}
rows exported: 2
after apply: {'lemma': 'γίγνομαι', 'lemma__pred': 'ἐγένετο', 'lemma_known': 'true', 'lemma_resolved': 'true', 'lemma_source': 'user', 'lemma_source__pred': 'unresolved', 'lemma_verified': 'true', 'review_note': 'aor. mid. of γίγνομαι', 'review_recommended': 'false', 'review_status': 'corrected', 'reviewed_by': 'RP', 'upos': 'VERB', 'upos__pred': 'NOUN'}
provenance note: review: 1 tokens corrected by RP (2026-07-10)
```

Note what the loop relies on: an aligned token has a stable source-token ID and
its exported source span is verified on apply. Older unaligned tables fall back
to `doc_id` + `position`; a token without a position is excluded, and the
applied-to corpus must still have the same token text (a mismatch raises rather
than landing a correction on the wrong word). The full workflow, including the CLI form, is on
[When the Tool Is Wrong](When-the-Tool-Is-Wrong).

### 7.4 Invariants your extension must hold

If you construct `Document`/`Token` objects yourself (rather than through
`from_records` or the importers), these are the contracts the rest of the
toolkit assumes:

- **Every `lines` index is a valid token index** (`0 ≤ i < len(tokens)`). The
  JSON and SQLite readers validate this and refuse a malformed file by name;
  an in-memory violation surfaces later as an `IndexError` from `line_tokens`
  or an export.
- **`position` should be the token's index in the document's list, unique per
  document.** Persistence tolerates `None` and disorder (§6). Source-aware
  review prefers `source_token_id`; older tables use `doc_id` + `position`, so
  a `None` drops the token from review export and a duplicated position can
  land one legacy correction on more than one token.
- **`status` must be one of the four `ReadingStatus` values** and `kind` one
  of the six `TokenKind` values; unknown strings raise at construction, so
  invent nothing here.
- **`kind` must be honest**: word-level analysis, review export, and
  annotation all gate on `TokenKind.WORD`.
- **Keep `annotations` values strings**, and stay off the reserved
  conventions (`<field>__pred`, `lemma_source`, `lemma_resolved`,
  `lemma_verified`, `review_recommended`, `lemma_known`,
  `review_status`, `reviewed_by`, `review_note`) unless you mean them.
- **Document ids must be unique** within a corpus (duplicates collapse with a
  warning, keeping the last).

The failure modes are deliberately loud rather than silent:

```python
import json
from aegean import Corpus, Document, Token, TokenKind

# (a) a lines entry pointing past the token list: caught at load, named by document
bad = Corpus([Document(id="D1", script_id="custom",
                       tokens=[Token(text="alpha", kind=TokenKind.WORD, position=0)],
                       lines=[[0, 7]])], script_id="custom")
blob = json.loads(bad.to_json())          # serializes fine — the writer doesn't validate
try:
    Corpus.from_dict(blob)
except ValueError as e:
    print("ValueError:", e)

# (b) an unknown status value: rejected before a Token is ever built
try:
    Corpus.from_records([{"id": "X", "lines": [[{"text": "A", "status": "probable"}]]}])
except ValueError as e:
    print("ValueError:", e)

# (c) a corpus file from a future pyaegean: refused with the fix named
blob["_meta"]["schemaVersion"] = 99
try:
    Corpus.from_dict(blob)
except ValueError as e:
    print("ValueError:", e)
```

```
ValueError: document 'D1': line 0 references token index 7, but the document has 1 token(s); the source is malformed
ValueError: 'probable' is not a valid ReadingStatus
ValueError: this corpus file uses schema version 99, but this pyaegean understands up to 3 — upgrade pyaegean to read it
```

The one sharp edge that is *not* loud, worth restating: an invalid `lines`
list on an in-memory corpus you built by hand serializes without complaint
(example (a) above writes fine and only fails on read). Validate by
round-tripping once (`Corpus.from_json(corpus.to_json())`) before you ship a
corpus file to anyone else.

---

**See also:** [Architecture](Architecture) · [For Specialists](For-Specialists) ·
[Using Critical Editions](Using-Critical-Editions) ·
[When the Tool Is Wrong](When-the-Tool-Is-Wrong) · [Reading a Parse](Reading-a-Parse) ·
[Data & Provenance](Data-and-Provenance) · [Greek NLP](Greek-NLP)
