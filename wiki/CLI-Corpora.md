# CLI: Corpora, Library, Analysis & Data

Reference for the unified library manager (`aegean library`), top-level corpus commands
(`info`, `load`, `show`, `search`, `query`, `stats`, `dispersion`, `keyness`, `balance`,
`cite`, `export`, `combine`, `import`, `geo`, `sign`, `bridge`, `plot`, `workbench`),
statistical analysis (`aegean analyze`), the low-level data store (`aegean data`), and
SQLite full-text databases (`aegean db`).

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [CLI: Greek NLP & Review](CLI-Greek) · [CLI: Biblical & Koine Greek](CLI-Bible) · [CLI: AI & MCP](CLI-AI)

---

## Unified library manager (`aegean library …`)

`aegean library` manages every resource pyaegean supports in one place: bundled corpora,
downloadable Aegean and Greek epigraphy corpora, Biblical & Koine Greek bundles, ~1,778
Perseus and First1KGreek literary works, 48 Greek patristic commentaries, hosted
dictionaries, and neural NLP models.

```bash
aegean library                              # status overview: installed counts, disk usage, packs
aegean library packs                        # named packs: biblical, aegean, epigraphy, lexica, neural
aegean library list --installed             # everything currently available offline on disk
aegean library list bible                   # filter by category (corpus, bible, work, commentary, lexicon, model, other)
aegean library search Plato                 # search across all corpora, works, commentaries, lexica, models
aegean library info nt-editions             # metadata, license, aliases, status, open/install commands
aegean library install biblical             # download all 5 Biblical & Koine Greek bundles (~25 MB)
aegean library install damos Iliad          # install by friendly alias, title, TLG ID, or author:<name>
aegean library install author:Homer         # download every catalogued work by Homer
aegean library remove damos                 # delete downloaded files and report reclaimed space
aegean library remove biblical              # remove all datasets in a pack (bundled corpora are never removed)
```

| Pack | Aliases | Contents | Size |
|---|---|---|---|
| `biblical` | `bible`, `koine`, `nt-all` | `nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, `lxx-corpus` | ~25 MB |
| `aegean` | `scripts`, `linear` | `damos-corpus`, `sigla-corpus` | ~4.3 MB |
| `epigraphy` | `inscriptions` | `isicily-corpus`, `iip-corpus`, `iospe-corpus`, `igcyr-corpus`, `edh-corpus` | ~8.0 MB |
| `lexica` | `dictionaries`, `lexicons` | `lsj-index`, `middle-liddell-index`, `cunliffe-index`, `autenrieth-index`, `abbott-smith-index` | ~19.3 MB |
| `neural` | `models`, `nlp` | `grc-joint`, `grc-paradigms` | ~173 MB |

In Python, `aegean.library` exposes the same operations (`summary()`, `list_packs()`,
`list_items()`, `search()`, `install()`, `remove()`). In the TUI (`aegean tui`), press `l`
to open the interactive Library Manager.

---

## Corpus commands (top level)

Every corpus command takes a **corpus id** as its first argument. The bundled,
offline-from-install corpora are `lineara`, `linearb`, `cypriot`, `cyprominoan`,
and `greek`. Eight more download to your cache on first use: `damos` (the full
~5,900-tablet DAMOS Linear B corpus), `sigla` (the SigLA Linear A dataset),
`nt` (the Greek New Testament), and five Greek-inscription corpora —
`isicily` (~2,855 texts, ancient Sicily), `iip` (~2,113, Israel/Palestine),
`iospe` (~1,194, the Northern Black Sea), `igcyr` (~997, Cyrenaica: Doric +
verse), and `edh` (~1,286, the Greek subset of the Epigraphic Database
Heidelberg). One more, `ddbdp` (the Duke Databank of Documentary Papyri:
**57,331 Greek papyri, ~4.4M tokens**), is far larger, so it is hosted as a
SQLite database with full-text search: `aegean.load("ddbdp")` materialises the
whole corpus (heavy, several GB of RAM), but the memory-friendly path is
`aegean db search ddbdp "βασιλέως"` (instant FTS) and, in Python,
`aegean.db.stream(ddbdp_db())`. Registered ids also match case-insensitively as a
fallback (`aegean info LINEARA` loads `lineara`). Pass an unknown id and the error
lists the valid ones, and suggests the nearest registered id when your spelling is
close:

```bash
aegean info bogus
# aegean: unknown corpus 'bogus'; expected a registered id (cypriot, cyprominoan, damos, ddbdp, edh, greek, igcyr, iip, iospe, isicily, lineara, linearb, nt, sigla), a Greek work id like tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin
aegean load linera
# aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (…), …
```

> **Any corpus argument is more than just an id now.** Wherever a command takes a
> corpus (and wherever `aegean.read_corpus(spec)` does in Python), you can pass:
> a registered id (`lineara`), a **Greek work id** (`tlg0012.tlg001` → fetches the
> Iliad like `aegean greek work`), a **path to a saved corpus** (`.json` or `.db`
> you wrote earlier), or **`-`** to read corpus JSON from stdin. So these all work
> with no Python:
>
> ```bash
> aegean db build tlg0012.tlg001 -o iliad.db        # build a DB straight from a work id
> aegean stats iliad.json                            # run stats on a corpus file you saved
> aegean export tlg0012.tlg002 -f csv -o odyssey.csv # export a work to CSV
> ```
>
> Work ids and saved files share one resolver, so anything you can `build` or
> `export` you can also `stats`, `query`, `keyness`, and so on.

For the meaning of document ids like `HT13` and work ids like `tlg0012.tlg001`,
see [Greek Works and Books](Greek-Works-and-Books) and the [Linear A](Linear-A) /
[Linear B](Linear-B) pages.

### `info` — what's in a corpus

Size, provenance, license, and the one-line citation.

```bash
aegean info lineara --json
```
```json
{
  "corpus": "lineara",
  "documents": 1721,
  "words": 1381,
  "tokens": 6406,
  "signs_in_inventory": 342,
  "source": "GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz",
  "license": "Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed",
  "citation": "Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz"
}
```

Drop `--json` for a human-readable table. The same in Python:

```python
import aegean
c = aegean.load("lineara")
len(c)                 # 1721
c.provenance.license   # 'Apache-2.0 (corpus JSON); …'
```

### `load` — filter by metadata, list or export

Filter on `--site`, `--period`, `--scribe`, `--support`; without `-o` it lists
the matches (capped by `--limit`, default 20), with `-o` it writes a
round-trippable corpus file (`.json`, or `.db` for the same SQLite database
`aegean db build` makes).

```bash
aegean load lineara --site "Haghia Triada"               # list the first 20 matches
aegean load lineara --site "Haghia Triada" -o ht.json    # → "wrote 1110 documents to ht.json"
```

### `show` — one document, line by line

```bash
aegean show lineara HT13
```
```
HT13  site=Haghia Triada  period=LMIB  scribe=HT Scribe 8  support=Tablet
  1: KA-U-DE-TA VIN 𐄁 TE 𐄁
  2: RE-ZA 5 ¹⁄₂
  3: TE-TU 56
  4: TE-KI 27 ¹⁄₂
  5: KU-ZU-NI 18
  6: DA-SI-*118 19
  7: I-DU-NE-SI 5
  8: KU-RO 130 ¹⁄₂
```

Document ids are resolved forgivingly: case and spacing don't matter (`ht13`,
`py ta 641`), and for a fetched Greek work the book or section alone is enough,
no need to repeat the work id:

```bash
aegean greek work tlg0012.tlg001     # fetch the Iliad (prints the summary)
aegean show tlg0012.tlg001 1         # read Book 1
aegean show tlg0012.tlg001 2         # read Book 2
```

An ambiguous short id is never guessed: the candidates are listed, and an
unknown id's error names the closest matches.

`--json` gives the full metadata block plus `lines` as nested token lists and,
when present, a `tokens` array with flattened `form_*` fields and a nested
`form_state`. Human output adds a `form N:` line below a token when its typed
state has diplomatic, regularized, normalized, or model-input distinctions.
These fields describe editorial evidence and analyzer input separately.

### `search` — wildcard sign-pattern word search

`*` matches exactly one sign. Returns matching words with their frequencies.

```bash
aegean search lineara "KU-*-RO"
```
```
'KU-*-RO': 1 word(s)
┌──────────┬───────┐
│ word     │ count │
├──────────┼───────┤
│ KU-MA-RO │ 1     │
└──────────┴───────┘
```

### `query` — the compound-query engine

Build a query from repeated `--where field=value` rows. Rows AND together by
default; prefix the field with `or:` to OR a row, or `!` to negate it.
`--output-kind` is `inscriptions` (default) or `words`. With `words` each
`(word, count)` is the word's **document frequency** (distinct inscriptions it
occurs in) by default, so it differs from the default token-frequency counts
that `search` and `stats` report. Choose `--count-unit token` for token frequency.
`--view surface|normalized|lemma` selects the lexical comparison key; the default
`--view legacy` retains the historical case-insensitive predicates and separate
surface keys. `--statuses certain,unclear,restored,lost` selects editorial reading
statuses (omit it to include all). JSON `metadata` records the selected view,
normalization, exclusions, and population denominator before word filters.

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "or:id-contains=ZA" \
       --output-kind words --json
```

The result carries a `description` of the query and a `citation` for the exact
subset, so the precise result set behind a figure is one `--json | jq .citation`
away. List the queryable fields with `--fields`:

```bash
aegean query lineara --fields
```

| field | scope | kind |
|---|---|---|
| `id-contains` | inscription | text |
| `site-is` | inscription | site |
| `scribe-is` | inscription | scribe |
| `period-is` | inscription | period |
| `support-is` | inscription | support |
| `has-image` | inscription | boolean |
| `has-annotation` | inscription | boolean |
| `ins-contains-word` | inscription | word |
| `word-contains` | word | text |
| `word-prefix` | word | text |
| `word-suffix` | word | text |
| `word-min-syllables` | word | number |
| `word-max-syllables` | word | number |
| `word-contains-sign` | word | sign |
| `word-cooccurs-with` | word | word |
| `word-sign-pattern` | word | text |

**Save the matched subset as a reusable corpus.** Add `--output/-o` (with a
`.json` or `.db` extension) and `query` writes the matching inscriptions out as a
corpus you can feed straight back into any other command:

```bash
aegean query lineara --where "site-is=Zakros" -o zakros.json
# wrote 53 inscriptions to zakros.json
aegean stats zakros.json --top 3                 # then analyse the saved subset
```

The saved file records a `subset: query(…) → N documents` provenance note, so the
exact filter behind it travels with the data. (`-o` only writes inscriptions:
use `--output-kind words --json` if you want the word list instead.)

> **Note:** `--limit` caps the human table and the `--json` lists alike
> (`--limit 0` lifts the cap and emits everything), and the JSON payload always
> carries the untruncated totals in `matched` (`{"inscriptions": …, "words": …}`),
> so a pipeline never silently loses count of the full result set.

#### Worked examples: combining `--where` rows

The grammar in practice, on the bundled Linear A corpus. Two plain rows **AND**
together (both must hold):

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "ins-contains-word=KU-RO" --limit 3
```
```
Site is: Haghia Triada · Contains exact word: KU-RO → 32 inscription(s)
┌───────┬───────────────┬───────┐
│ id    │ site          │ words │
├───────┼───────────────┼───────┤
│ HT9a  │ Haghia Triada │ 9     │
│ HT9b  │ Haghia Triada │ 10    │
│ HT11a │ Haghia Triada │ 6     │
└───────┴───────────────┴───────┘
```

An `or:` prefix ORs its row in (either site qualifies):

```bash
aegean query lineara --where "site-is=Zakros" --where "or:site-is=Phaistos" --limit 3
# Site is: Zakros · Site is: Phaistos → 119 inscription(s)
# (the table starts PH1a, PH1b, PH2 …)
```

A `!` prefix negates its row (Haghia Triada tablets that do NOT mention KU-RO):

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "!ins-contains-word=KU-RO" --limit 3
# Site is: Haghia Triada · NOT Contains exact word: KU-RO → 1078 inscription(s)
```

`--output-kind words` switches the result from matching inscriptions to the
matching **words** (each count is the word's document frequency within the
matched subset by default). Word-scope fields such as `word-prefix` select word
keys; with inscription output, they retain documents containing a matching word:

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "word-prefix=KU" --output-kind words --limit 5
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
```

Every result ends with the exact-subset citation (elided above): the filter
you ran travels with the numbers. A mistyped field is a one-line error with a
suggestion, never a silent empty match:

```bash
aegean query lineara --where "site=Zakros"
# aegean: unknown field 'site' — did you mean 'site-is'? (`aegean query lineara --fields` lists all)
```

### `stats` — frequency tables

Word frequencies by default; `--signs` counts individual signs.

For words, `--view surface` keeps exact text; `normalized` applies NFC, lowercase,
and final-sigma folding while preserving diacritics; `lemma` applies the same
normalization to existing lemma annotations. Missing lemmas are excluded and
reported, without running an analyzer. `--count-unit token|document` chooses token
frequency (default) or the number of documents containing each key. `--statuses`
selects editorial reading statuses, including each typed segment's status. These
options and `--details` apply to word counts, so combining them with `--signs` is
an error.

The ordinary `--json` output remains a list of `{item, count}` rows. Add
`--details`, or select a nondefault word view, count unit, or status selection, for
an object containing `frequencies`, `metadata`, and `citation`. The metadata
records normalization, exclusions, and the denominator; a lemma source describes
its annotation provenance, not verified accuracy.

```bash
aegean stats nt --view lemma --count-unit document --details --json
aegean query nt --view lemma --count-unit token --where "word-prefix=ἀγαπ" --output-kind words --json
```

```bash
aegean stats lineara --signs --top 5
```
```
┌──────┬───────┐
│ item │ count │
├──────┼───────┤
│ KU   │ 307   │
│ KA   │ 284   │
│ *301 │ 274   │
│ SI   │ 240   │
│ A    │ 202   │
└──────┴───────┘
```

### `dispersion` — how evenly an item is spread

Gries' DP: `0` = perfectly even across documents, `1` = concentrated in a few.
Give one item, or omit it to rank the corpus.

```bash
aegean dispersion lineara --top 5
```
```
┌───────────┬──────┬─────────────┬───────┬────────┐
│ item      │ freq │ range/parts │ DP    │ DPnorm │
├───────────┼──────┼─────────────┼───────┼────────┤
│ KU-RO     │ 37   │ 34/559      │ 0.850 │ 0.851  │
│ KI-RO     │ 16   │ 12/559      │ 0.938 │ 0.938  │
│ SA-RA₂    │ 20   │ 20/559      │ 0.948 │ 0.949  │
│ KU-PA₃-NU │ 8    │ 7/559       │ 0.948 │ 0.949  │
│ A-DU      │ 10   │ 10/559      │ 0.963 │ 0.964  │
└───────────┴──────┴─────────────┴───────┴────────┘
```

### `keyness` — characteristic vocabulary of a subset

Compares either a metadata subset against the rest of the same corpus, or one
corpus against another (`--reference`). Reports log-likelihood (G²) and log-ratio
with a p-value.

```bash
aegean keyness lineara --site "Zakros" --top 5
```
```
┌────────────────────┬────────┬───────────┬───────┬───────────┬─────────┐
│ item               │ target │ reference │ G2    │ log-ratio │ p       │
├────────────────────┼────────┼───────────┼───────┼───────────┼─────────┤
│ *28B-NU-MA-RE      │ 3/132  │ 0/1249    │ 14.15 │ +6.05     │ 0.00017 │
│ DU-RE-ZA-SE        │ 3/132  │ 0/1249    │ 14.15 │ +6.05     │ 0.00017 │
│ SI-PI-KI           │ 3/132  │ 0/1249    │ 14.15 │ +6.05     │ 0.00017 │
│ A-TI-KA-A-DU-KO-MI │ 2/132  │ 0/1249    │ 9.42  │ +5.56     │ 0.0021  │
│ DA-I-PI-TA         │ 2/132  │ 0/1249    │ 9.42  │ +5.56     │ 0.0021  │
└────────────────────┴────────┴───────────┴───────┴───────────┴─────────┘
```

> **Save a result straight to a file.** `stats`, `keyness`, `dispersion`,
> `search`, and `balance` all take `--output/-o`, and the format follows the
> extension: `.json` (the same document as `--json`), `.csv` (a plain table:
> stdlib only, no pandas), or `.txt` (the human view). A one-line `wrote <path>`
> confirmation goes to stderr (stdout stays clean), and `-o` combines with
> `--json`: the file is written and the JSON still prints to stdout:
>
> ```bash
> aegean stats lineara --top 3 -o freq.csv
> # wrote freq.csv                                  [stderr]
> # freq.csv:
> # item,count
> # KU-RO,37
> # SA-RA₂,20
> # KI-RO,16
> ```

### `balance` — accounting reconciliation

Checks stated totals (`KU-RO` in Linear A, `TO-SO` in Linear B) against the sum
of the listed items. Give one document, or omit it to sweep the whole corpus.

```bash
aegean balance lineara HT13
```
```
┌──────┬────────┬────────┬──────────┬──────┬──────────┐
│ doc  │ marker │ stated │ computed │ diff │ balances │
├──────┼────────┼────────┼──────────┼──────┼──────────┤
│ HT13 │ KU-RO  │ 130.5  │ 131.0    │ 0.5  │ NO       │
└──────┴────────┴────────┴──────────┴──────┴──────────┘
```

`--strict` makes the command exit `1` whenever any checked total fails, handy in
a script. See [Linear A](Linear-A) for what KU-RO discrepancies actually mean.

### `cite` — cite a corpus or the exact subset

```bash
aegean cite lineara --site "Haghia Triada"
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.
#   — https://… [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
```

`--style` is `plain` (default), `bibtex`, or `apa`. Append a BibTeX entry to your
bibliography with `aegean cite lineara --site Zakros --style bibtex >> paper.bib`.

### `export` — JSON, CSV, Parquet, EpiDoc, SQLite, RDF

```bash
aegean export lineara -f csv -o lineara.csv               # → "wrote 1721 documents to lineara.csv (csv)"
aegean export greek -f epidoc -o greek.xml                # EpiDoc TEI
aegean export lineara -f sqlite -o lineara.db             # same DB as `aegean db build`
aegean export lineara -f workbench -o wb.json             # Linear A Workbench JSON
aegean export edh -f ttl -o edh.ttl                       # Linked Open Data (Turtle)
```

| `--format` | output | needs |
|---|---|---|
| `json` | lossless, round-trippable corpus | core |
| `csv` | one row per document/token/word (`--level`) | core |
| `parquet` | same, columnar | `[parquet]` extra |
| `epidoc` | EpiDoc TEI XML | core |
| `sqlite` | queryable DB with FTS5 | core |
| `workbench` | Linear A Research Workbench JSON; text and surface metadata round-trip, while statuses, annotations, and typed forms are lossy | core |
| `ttl` / `jsonld` | Linked Open Data (Turtle / JSON-LD): stable subject URIs from the authoritative identifiers in the data (papyri.info document URIs for DDbDP, with Trismegistos as `rdfs:seeAlso` and the offline fallback; Trismegistos ids for EDH; the I.Sicily URI; else a documented `urn:` fallback or `--base-uri`), Dublin Core terms, WGS84 coordinates, and the corpus license attached to every document | core |

`--level token` (csv/parquet) emits one row per token and spreads per-token
annotations (the Greek NT's lemma / morph / Strong's / gloss) into columns.

Two further blocks of columns are reserved for typed state, and each is written
only when at least one exported token actually carries it: the sixteen `form_*`
columns (`form_diplomatic`, `form_regularized`, `form_normalized`,
`form_model_input`, `form_model_input_ops`, `form_model_input_source`,
`form_segments`, and the editorial status, damage, and uncertainty fields) and
the nine `alignment_*` source-span columns. `form_segments` is JSON in the
table. A corpus that records neither keeps just its own columns rather than
25 empty ones. Filters (`--site` etc.) apply before export.

#### The whole matrix, run once

Each format, on the compact bundled Cypriot corpus (180 documents), with the
confirmation each one prints. Files land exactly where `-o` says: a bare
filename goes to the directory you ran the command from.

```bash
aegean export cypriot -f json -o cypriot.json         # wrote 180 documents to cypriot.json (json)
aegean export cypriot -f csv -o cypriot.csv           # wrote 180 documents to cypriot.csv (csv)
aegean export cypriot -f parquet -o cypriot.parquet   # wrote 180 documents to cypriot.parquet (parquet)
aegean export cypriot -f epidoc -o cypriot-epidoc/    # wrote 180 documents to cypriot-epidoc (epidoc)
aegean export cypriot -f sqlite -o cypriot.db         # wrote 180 documents to cypriot.db (sqlite)
aegean export lineara -f workbench -o wb.json         # wrote 1721 documents to wb.json (workbench)
```

Two shapes to know about. `epidoc` writes a **folder**, one TEI XML file per
document (here `cypriot-epidoc/IG_XV_1__1.xml` and 179 siblings), because an
EpiDoc edition is per-inscription. Everything else writes the single file you
named. `parquet` is the one format needing an extra (`pip install
"pyaegean[parquet]"`); without it the command exits with a one-line install
hint.

At `--level document` (the default) the CSV has one row per document with its
metadata. `--level token` explodes to one row per token; on an annotated corpus
the annotations become columns, so the NT export is analysis-ready as a
spreadsheet. The NT records no typed form state or source alignment, so neither
optional block appears and the table is fifteen columns wide:

```bash
aegean export nt -f csv --level token -o nt-tokens.csv   # wrote 260 documents to nt-tokens.csv (csv)
head -2 nt-tokens.csv
# doc_id,line_no,position,text,kind,status,site,period,lemma,morph,strongs,normalized,upos,ref,gloss
# Matt 1,1,0,Βίβλος,word,certain,,Koine,βίβλος,N-NSF,976,Βίβλος,NOUN,Matt.1.1,"a written book, roll, or volume"
```

### `greek interop` — portable annotation bundles

These commands move a strict CoNLL-U document through one optional target adapter and
write an inspectable JSON bundle containing the target projection, SHA-256-bound sidecar, and
loss report. They do not run a model. Install the CLI plus the target extra first
(`pip install "pyaegean[cli,interop]"`, or combine `[cli]` with one of `[spacy]`,
`[stanza]`, or `[cltk]`).

```bash
aegean greek interop export treebank.conllu --target spacy -o treebank.spacy.json
aegean greek interop report treebank.spacy.json
aegean greek interop import treebank.spacy.json -o treebank-restored.conllu
```

`report` validates the bundle without loading a model, printing the target and version,
whether the round trip is lossless, and which fields travel natively, in the sidecar, or
not at all; `import` recovers the complete CoNLL-U document. The bundle is pyaegean's
portable JSON format, not a claim to write a spaCy, Stanza, or CLTK binary serializer.

### `combine` — merge several corpora into one file

Give two or more sources and one `--output/-o` (a `.json` or `.db`) and `combine`
merges them into a single saved corpus. Each source is resolved like any corpus
argument: an id, a saved `.json`/`.db`, a Greek work id, or `-`, so you can
stitch works, subsets, and bundled corpora together in one go:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db    # all of Homer in one database
# wrote … documents to homer.db (merged 2 sources)
```

A run you can try offline, against the bundled corpora:

```bash
aegean combine lineara cypriot -o aegean-mix.json
# wrote 1901 documents to aegean-mix.json (merged 2 sources)
```

The merged corpus keeps a provenance that **names every source**: its citation
reads `Merged corpus of: …` listing each one. If two sources share a document id,
`--on-conflict` decides what happens: `error` (the default, stop and tell you),
`first` (keep the earliest), `last` (keep the latest), or `suffix` (keep both,
appending `#2`, `#3`, … to the later ids). The same in Python:

```python
import aegean
merged = aegean.combine([aegean.load("lineara"), aegean.load("cypriot")])
# or from an existing corpus:
both = aegean.load("lineara").merge(aegean.load("cypriot"), dedupe="suffix")
just_a_few = aegean.load("lineara").subset(["HT13", "HT9a", "HT11a"])
```

`Corpus.merge(*others, dedupe=…)` takes the same four `dedupe` values as
`--on-conflict`; `Corpus.subset(ids)` pulls out a named slice. See
[Greek Works and Books](Greek-Works-and-Books) for the work ids you can combine.

### `import` — bring your own text into a corpus

Everything above analyses corpora that pyaegean already knows about. `import` turns
**your own** material (a plain-text file, a folder of text files, or a CSV) into a
real corpus you can then `stats`, `search`, `query`, `export`, and so on. It always
writes to `--output/-o` (a `.json` or `.db`), and the result works anywhere a corpus
is accepted. The default `--token-view all` preserves decoded source content,
whitespace, and aligned tokens, including punctuation, numerals, and foreign text.
Greek/Koine linguistic words remain separate from those other token kinds, so
`stats` counts the word view without deleting source material. `--token-view words`
explicitly opts into the former lossy import, which discards source text and
spans and reports its exclusions in provenance. This option applies to plain
text and CSV, not Workbench or EpiDoc imports.

```bash
aegean import john.txt -o john.json --script nt        # one plain-text file → a corpus
# wrote 1 document(s) to john.json
# explore it:  aegean stats john.json                   [stderr hint]
aegean stats john.json --top 5                          # then analyse it like any corpus
```
```
 john.json: top 5
      words
┌───────┬───────┐
│ item  │ count │
├───────┼───────┤
│ ἦν    │ 4     │
│ λόγος │ 3     │
│ ὁ     │ 3     │
│ θεόν  │ 2     │
│ καὶ   │ 2     │
└───────┴───────┘
```

**`--split` decides how a text becomes documents**: `whole` (the default, one
document for the whole file), `paragraph` (one per blank-line-separated block), or
`line` (one per non-empty line). With more than one block the ids are numbered
`<base>:1`, `<base>:2`, …; the base id is the file's stem unless you override it with
`--id`:

```bash
aegean import john.txt -o john-lines.json --script nt --split line
# wrote 2 document(s) to john-lines.json
```

**A folder** imports every matching file into one corpus (each file's stem becomes a
document id, de-duplicated with a `#2`, `#3`, … suffix on collision). `--glob`
chooses which files; `--split` applies per file:

```bash
aegean import poems/ -o poems.db --split line          # a directory of *.txt → a database
# wrote 2 document(s) to poems.db
aegean db search poems.db θεά
```

**A CSV** treats each row as a document: `--text-col` names the column holding the
text (default `text`), and `--id-col` names the column holding the id (otherwise ids
are `<stem>:<row>`):

```bash
aegean import verses.csv -o verses.json --script nt --text-col line --id-col id
# wrote 2 document(s) to verses.json
aegean show verses.json v2
# v2
#   1: καὶ ὁ λόγος ἦν πρὸς τὸν θεόν
```

`--encoding` (default `utf-8-sig`, which removes a leading UTF-8 BOM) reads
non-UTF-8 files. The same lives on `aegean.io` in Python: `from_text`,
`from_text_file`, `from_text_dir`, and `from_csv` (the CSV
one also takes `meta_cols=` to carry columns into document metadata):

```python
from aegean import io
c = io.from_text("μῆνιν ἄειδε θεά", script_id="nt")           # a raw string
c = io.from_text_file("john.txt", script_id="nt", split="line")
c = io.from_csv("verses.csv", text_col="line", id_col="id", script_id="nt")
# Explicitly request the former lossy word-only import:
words_only = io.from_text("μῆνιν, ἄειδε θεά.", script_id="nt", token_view="words")
```

With the default import, `Document.source_text` retains the decoded content and
`Document.words` / `Corpus.iter_words()` provide the linguistic word view.
JSON and SQLite retain that source and its alignment; a word-only import cannot
recover discarded content later.

A **Linear A Workbench export** (the JSON the workbench saves) imports back with
`--workbench`, the inverse of `export -f workbench`:

```bash
aegean export lineara -f workbench -o wb.json   # corpus → Workbench JSON
aegean import wb.json --workbench -o back.json  # Workbench JSON → corpus
```

Workbench JSON carries token text and surface metadata only. It drops
`ReadingStatus`, typed `TokenFormState`, and token annotations, so an imported
Workbench file returns CERTAIN, unannotated tokens. Use JSON or SQLite when the
editorial and analysis layers must survive.

**EpiDoc TEI** imports back the same way, for a token-carrier EpiDoc edition (a file or a
folder of `.xml`), not just pyaegean's own output, via `--epidoc`, the inverse of
`export -f epidoc`:

```bash
aegean export lineara -f epidoc -o ins/                    # corpus → EpiDoc TEI (one file per doc)
aegean import ins/ --epidoc --script lineara -o back.json  # token-carrier EpiDoc → corpus
```

It recovers the id, find-place, token/line stream, editorial certainty
(`<unclear>`/`<supplied>`), typed choices and apparatus segments, and `<app>` variants,
using only the stdlib XML parser. The mapping is semantic, not byte-identical, and
arbitrary free-text TEI is not converted into typed token state.

`import` is the **only** way plain text enters a corpus: `read_corpus` and every
corpus argument still load only `.json`/`.db` files (and work ids), so feeding a raw
`.txt` straight to a command fails with a message telling you to import it first:

```bash
aegean stats john.txt --top 3
# aegean: unknown corpus 'john.txt'; expected a registered id (…), a Greek work id …,
#   a path to a .json or .db corpus, or '-' …. To load plain text, import it first:
#   `aegean import john.txt -o corpus.json` (or aegean.io.from_text_file / from_csv …)
#   [stderr, exit 1]
```

### `geo` — find-site coordinates, or a word's map

```bash
aegean geo lineara
```
```
             lineara: 52 located site(s) of 52
┌──────────────────┬───────┬───────┬───────────┬───────────┐
│ site             │ lat   │ lon   │ pleiades  │ contested │
├──────────────────┼───────┼───────┼───────────┼───────────┤
│ Apodoulou        │ 35.16 │ 24.73 │ 119143959 │           │
│ Arkhalkhori      │ 35.15 │ 25.27 │ 220781958 │           │
│ Armenoi          │ 35.3  │ 24.5  │           │           │
│ …                │       │       │           │           │
└──────────────────┴───────┴───────┴───────────┴───────────┘
```

Add `-o sites.geojson` to write GeoJSON instead of printing a table (that path
needs the `[geo]` extra; the extension must be `.json` or `.geojson`). The shared
metadata filters (`--site`, `--period`, `--scribe`, `--support`) narrow the corpus
before mapping. More on the map data in [Geography](Geography).

`--word` maps where a single word is attested, with per-site counts (the table needs
no extra; `-o` writes GeoJSON):

```bash
aegean geo lineara --word KU-RO          # sites where KU-RO occurs, most-attested first
```
```
       lineara: 'KU-RO' attested at 3 located site(s)
┌───────────────┬───────┬───────┬───────┐
│ site          │ lat   │ lon   │ count │
├───────────────┼───────┼───────┼───────┤
│ Haghia Triada │ 35.06 │ 24.79 │ 32    │
│ Phaistos      │ 35.05 │ 24.81 │ 1     │
│ Zakros        │ 35.1  │ 26.26 │ 1     │
└───────────────┴───────┴───────┴───────┘
```

The word is matched case-insensitively (`--word a-du` finds A-DU), and the
same works on any corpus that records find-sites. On the fetched DAMOS Linear B
corpus, for instance, the distribution of *po-ti-ni-ja* (Potnia, "the
Mistress") across the Mycenaean archives:

```bash
aegean geo damos --word po-ti-ni-ja
```
```
 damos: 'po-ti-ni-ja' attested at 3
          located site(s)
┌─────────┬────────┬───────┬───────┐
│ site    │ lat    │ lon   │ count │
├─────────┼────────┼───────┼───────┤
│ Pylos   │ 36.952 │ 21.66 │ 8     │
│ Knossos │ 35.3   │ 25.16 │ 1     │
│ Mycenae │ 37.73  │ 22.75 │ 1     │
└─────────┴────────┴───────┴───────┘
```

### `sign` — look up one sign

Glyph, Unicode codepoint, sound value, and the raw attributes for a single sign
in a script's inventory.

```bash
aegean sign lineara KU --json
```
```json
{
  "label": "KU",
  "glyph": "𐙂",
  "codepoint": "U+10642",
  "phonetic": "ku",
  "attrs": { "sharedWithLinearB": true, "linearAOnly": false, "total": 29, "confidence": 1, "altGlyphs": [] }
}
```

### `bridge` — read a deciphered syllabic word as Greek

For the deciphered scripts (`linearb`, `cypriot`): the attested Greek reading plus
a gloss.

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)
```

### `cache` — the opt-in analysis cache

This is the *analysis* memoization cache (distinct from the permanent *data*
store under `aegean data store`). It's off unless you enable it for the shell:

```bash
aegean cache
# analysis cache: off — set PYAEGEAN_ANALYSIS_CACHE=1 (or a path) to enable
```

Set `PYAEGEAN_ANALYSIS_CACHE=1` (or a directory path) and expensive analyses
(dispersion, keyness, clustering) are reused across runs; `aegean cache --clear`
wipes it. Cached values are stored in SQLite using a typed JSON codec
(`AEGEAN-CACHE-V2`, never Python `pickle`), so stale or malformed entries are
treated as a safe miss and recomputed without running arbitrary code. The file
is created owner-only, and enabling a cache in an others-writable directory warns.

### `doctor` — the offline environment check

One command that answers "why doesn't X work": Python and pyaegean versions,
which optional extras are importable, the state of the data store (location,
live size, per-dataset downloaded state, leftover partial downloads,
writability), whether the neural model bundles are downloaded, and the analysis
cache. Entirely offline: no network is touched, nothing is downloaded, and every
value is measured live from your machine.

```bash
aegean doctor
```
```
                  versions
┌────┬──────────┬───────────────────────────┐
│    │ check    │ value                     │
├────┼──────────┼───────────────────────────┤
│ OK │ python   │ 3.14.4                    │
│ OK │ pyaegean │ 0.67.0                    │
│ OK │ platform │ Windows-11-10.0.26200-SP0 │
└────┴──────────┴───────────────────────────┘
…four more tables: optional extras, data store, neural model bundles, analysis cache…
doctor: all checks passed
```

A missing extra or an un-downloaded dataset is **informational**, never an issue
(the zero-dependency core is a supported configuration): those rows carry their
`pip install "pyaegean[…]"` or `aegean data fetch` line. Issues are things that
break an advertised behavior, each printed with its fix: a Python below the 3.10
floor, an unusable or unwritable store (the fix names `PYAEGEAN_CACHE`), or a
leftover partial download from an interrupted fetch (the fix names
`aegean data remove NAME`). Exit `0` when healthy, `1` when any issue is found,
in both the human and `--json` views; `--json` emits the whole report as one
stable document (`{ok, issues, versions, extras, data_store, models,
analysis_cache}`), and `-o` saves it like any other result.

### `plot` — one figure to a file

Draws a single figure and writes it to `--output` (`.png`/`.svg`/`.pdf`). Needs
the `[viz]` extra. The first argument is the figure kind:

| kind | what it draws |
|---|---|
| `freq` | top-N sign or word frequencies |
| `dispersion` | DP scatter (annotate the top N) |
| `keyness` | keyness bars (subset vs rest, or vs `--reference`) |
| `network` | co-occurrence network (`--word` for one word's ego network) |
| `balance` | accounting reconciliation chart |
| `scansion` | a metrical scansion grid for one Greek line |
| `findspots` | a map of the corpus's find-sites |
| `timeline` | a date histogram (`--bin-width` sets the bin size in years) |
| `signnet` | a sign/word co-occurrence network (`--scope document\|line`) |

```bash
pip install "pyaegean[viz]"
aegean plot keyness lineara --site Zakros -o zakros.png      # → "wrote zakros.png"
aegean plot scansion "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ" -o scan.svg --meter hexameter   # → "wrote scan.svg"
```

For `scansion` the second argument is the Greek line itself (`-` reads stdin); for
every other kind it's a corpus name.

### `workbench` — serve the Linear A Research Workbench locally

```bash
aegean workbench                                         # fetch v2.0.0 build (~3.1 MB) & open in browser
aegean workbench --fetch-images                          # also download facsimile imagery (~116 MB)
aegean workbench --site "Haghia Triada" --module arith   # open pre-scoped to a site and module
aegean workbench --doc HT13                              # jump straight to an inscription detail view
aegean workbench --corpus damos                          # inspect any pyaegean corpus or local JSON export
aegean workbench --damos                                 # auto-mount DAMOS Linear B frequencies for Sign Inventory
aegean workbench --state workspace.json                  # auto-load & save annotations/notes/collections locally
aegean workbench --dir ../linearaworkbench/dist --port 0 # serve a local build on an auto-picked free port
```

Fetches the sha256-pinned `workbench-app-v2.0.0` static build to the cache, then serves the browser UI (corpus, maps, commentary, and all 34 workspaces / 59 views) on loopback (`127.0.0.1`) until you press Ctrl+C. Pass `--fetch-images` (or `aegean data fetch lineara-images`) to mount the ~116 MB facsimile archive at `/upstream/images/`. Pass `--state workspace.json` to enable bidirectional loopback persistence at `/api/local/backup` (readable in Python via `aegean.io.load_workbench_backup()`).

---


## Analysis — `aegean analyze …`

Exploratory **surface** analyses over the (largely undeciphered) Aegean material:
evidence to weigh, not conclusions. Full method notes are on [Analysis](Analysis).

### Phonetic distance and alignment

```bash
aegean analyze distance KU-RO KI-RO
# KU-RO ↔ KI-RO: 0.200

aegean analyze align KU-RO KI-RO        # per-position match / vowel / same-class / far / gap
```

### Cross-script comparison

`compare` romanizes two words from possibly different scripts and aligns them by
sound; `nearest` ranks a corpus's words by closeness to a query word.

```bash
aegean analyze compare po-me ποιμήν
# po-me [linearb] → pome    ποιμήν [greek] → poimēn
# similarity 0.62  (distance 0.383)
#   a  b  op
#   p  p  match
#   o  o  match
#   ·  i  ins
#   m  m  match
#   e  ē  sub-vowel
#   ·  n  ins
```

```bash
aegean analyze nearest qa-si-re-u greek --top 5 --json
# [{"candidate": "Ἡροδότου", "distance": 0.612}, {"candidate": "καὶ", "distance": 0.625}, {"candidate": "ἄειδε", "distance": 0.625}, …]
```

`--script-a`/`--script-b` choose the scripts (`greek` · `lineara` · `linearb` ·
`cypriot`); `--fold-aspiration` maps θ/φ/χ → t/p/k, which is fairer against
defective syllabic spelling. These numbers are exploratory: read the alignment
and the *ranking*, not the absolute distance.

### Association and co-occurrence

```bash
aegean analyze assoc lineara KU-RO KI-RO    # χ², log-likelihood, Fisher, PMI over shared documents
aegean analyze cooccur lineara KU-RO        # what shares a tablet with KU-RO, ranked
```

### Morphology, structure, scribal hands

```bash
aegean analyze clusters lineara             # stem + productive-suffix clusters (exploratory)
aegean analyze structure lineara            # accounting / libation / list / text / other census
aegean analyze structure lineara HT13       # classify one document
aegean analyze hands damos                  # scribal-hand profiles (needs a hand per document)
aegean analyze hands damos --hand 103             # one hand's characteristic vocabulary (keyness)
```

`hands` needs a corpus that records a scribe per document: DAMOS does, so it
fetches on first use; the bundled `lineara` records HT scribes too.

> **Save any of these to a file.** `assoc`, `cooccur`, `clusters`, `structure`,
> `hands`, and `nearest` all take `--output/-o`, with the format set by the
> extension: `.json`, `.csv` (stdlib, no pandas), or `.txt`; each prints a
> one-line `wrote <path>` confirmation to stderr and combines with `--json`.
> `structure` and `hands` also take the shared metadata filters (`--site`,
> `--period`, `--scribe`, `--support`), and `--top 0` lifts the cap on the
> ranked tables:
>
> ```bash
> aegean analyze cooccur lineara KU-RO -o ku-ro-neighbours.json
> aegean analyze clusters lineara -o clusters.csv
> ```

---

## Data — `aegean data …`

The fetch-to-store layer: list what can be downloaded (and what already is),
fetch it (sha256-verified), delete it, pin versions for a paper, and inspect the
store. Fetched datasets have no time-based expiry or automatic eviction. A cache
matching the current pin is reused; a changed pin or stale integrity stamp can
trigger a replacement download. `aegean data remove` deletes the selected entry,
and `fetch --force` replaces it.

```bash
aegean data list                                   # the fetchable datasets + downloaded status/size
aegean data fetch grc-joint                         # download or reuse a cache matching the current pin
aegean data fetch damos                             # the DAMOS Linear B corpus (a stem: = damos-corpus)
aegean data remove grc-joint                        # delete a downloaded dataset (--all clears everything)
aegean data versions --json > data-versions.json    # pin every dataset's sha256 for reproducibility
aegean data store                                   # store location + contents (override: PYAEGEAN_CACHE)
```

For a **Linear B corpus**, fetch **DAMOS** directly (`aegean data fetch damos`, ~5,900 tablets,
CC BY-NC-SA 4.0). **LiBER** (liber.cnr.it) is browse-only: it has no public download or API and is
rights-restricted, so it cannot be fetched. To use your own licensed Linear B export, import it
(`aegean import x.xml --epidoc --script linearb`) or set `PYAEGEAN_LINEARB_CORPUS_URL`.

(`aegean data cache` is an older deprecated alias for `data store`: it
still works but warns, naming the replacement.)

### A worked round trip

Delete and re-download a dataset, watching the store at each step (run here on
the NT corpus; the fetch is the one networked step). `remove` frees the space
and says how much; `list` flips its **downloaded** column; `fetch` prints the
destination path (plus a "load it" hint on stderr), and re-running a fetch of
something already present and matching the current pin is a no-op:

```bash
aegean data remove nt-corpus
# removed nt-corpus: C:\Users\you\.cache\pyaegean\nt-corpus (15.8 MB reclaimed)

aegean data list        # its row now reads:
# │ nt-corpus         │ no             │ Greek New          │ CC0-1.0           │

aegean data fetch nt    # stems resolve: nt = nt-corpus (so do damos, sigla)
# C:\Users\you\.cache\pyaegean\nt-corpus
# load it:  aegean info nt        [stderr]

aegean data list        # downloaded again, with its real on-disk size:
# │ nt-corpus         │ yes (15.8 MB)  │ Greek New          │ CC0-1.0           │
```

`aegean data store` shows the same thing from the disk's point of view: the
store's location and a name/MB table of everything in it.

`aegean data list` shows the full live registry (currently 39 entries), with a **downloaded** column giving
each present dataset's actual on-disk size. Every dataset downloads on demand and is never bundled in the Apache-2.0 wheel.

For one-command installation by research area, use the [unified library manager](CLI#library-manager-aegean-library-):

```bash
aegean library packs                  # biblical, patristic, aegean, epigraphy, literary, lexica, neural
aegean library install epigraphy      # all 7 Greek inscription corpora (I.Sicily, IIP, IOSPE, IGCyr, Aphrodisias, Crete, EDH)
aegean library install patristic      # Apostolic Fathers, Old Testament Pseudepigrapha, Patrologia Graeca
```

`aegean data versions --json` is the reproducibility manifest: every bundled and
fetched dataset with its sha256. See [Data & Provenance](Data-and-Provenance) for
the full 39-dataset table of sizes, build scripts, and licenses.

---

## SQLite — `aegean db …`

Build a queryable SQLite database from any corpus (documents + tokens + an FTS5
full-text index) and search it.

```bash
aegean db build lineara -o lineara.db        # → "wrote 1721 documents to lineara.db"
                                             #    search it:  aegean db search lineara.db KU-RO
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

`db search` matches a whole token by default: `KU-RO` matches only `KU-RO`, never
`PO-TO-KU-RO`. Pass `--substring` to match within tokens instead:

```bash
aegean db search lineara.db KU-RO --substring   # also matches PO-TO-KU-RO, etc.
```

The database argument also accepts a DB-backed corpus id: `aegean db search
ddbdp "βασιλέως"` searches the fetched DDbDP papyri database directly, no path
needed.

`db search` opens the database **read-only**, so a typoed path can never create
or modify a file: a missing path is a one-line error naming `aegean db build`.
`--limit 0` returns every match, `--output/-o` saves the hits (`.json`, `.csv`,
or `.txt` by extension), and a whole-token search that finds nothing says so
with the fix:

```bash
aegean db search lineara.db KU-RO-ZZ
# no matches (whole-token) — pass --substring to match within tokens
```

`db build` resolves its corpus like anything else — so `aegean db build
tlg0012.tlg001 -o iliad.db` builds a database straight from a Greek work id.
`--no-fts` skips the full-text index. `aegean export CORPUS -f sqlite -o file.db`
writes the same database. Load it back in Python with `Corpus.from_sql(path)`, or
stream it with `aegean.db.stream(path)`.

### `db index` — accelerate exact lexical searches

An optional lexical index accelerates exact surface, normalized, and lemma
searches while preserving the existing reading-status filters and hit order:

```bash
aegean db index corpus.db
aegean db index corpus.db --status --json
aegean db search corpus.db λόγος --view lemma --statuses certain --json
```

Index building takes an existing writable local path. Copy a fetched database to
a working file before indexing it. Token edits invalidate the index; search falls
back to the original scan until `db index` refreshes it. Search and status checks
remain read-only, and substring searches retain their scan behavior. Indexing
does not generate lemmas or change which tokens qualify for a query.

### `db annotate` & `db job-status` — resumable SQLite annotation jobs

For large Greek corpora stored in SQLite, `db annotate` annotates one document at
a time and checkpoints progress inside the same SQLite transaction, so an
interrupted run can resume without starting over:

```bash
aegean db annotate corpus.db -o annotated.db --job-dir ./job-state --neural --with-dependencies
aegean db job-status ./job-state --json
# If interrupted, run again with --resume (verifies source snapshot, options, and backend):
aegean db annotate corpus.db -o annotated.db --job-dir ./job-state --neural --with-dependencies --resume
```

Each job freezes a WAL-safe snapshot of the source database, reads documents
forward in bounded keyset order, holds an exclusive file lock while active, and
publishes the finished output database atomically only when all documents complete.

### `db add` — grow an existing database

`db add` upserts documents into a database you already built: a document whose id
already exists is replaced, new ids are added, and the FTS5 index is refreshed.
The source resolves like any corpus argument (id, `.json`/`.db`, work id, or `-`):

```bash
aegean db build lineara -o aegean.db         # → "wrote 1721 documents to aegean.db"
aegean db add cypriot -o aegean.db           # → "added/updated 180 documents in aegean.db"
```

Mixing scripts is allowed and noted on stderr (the database's script id becomes
`mixed`). The Python equivalents take an `append=True` flag:

```python
corpus.to_sql("aegean.db", append=True)      # or aegean.db.to_sqlite(corpus, "aegean.db", append=True)
```

### The chain, worked end to end

Build, grow, search, in one sitting (all offline, on the bundled corpora).
Note the stderr line when the second script goes in:

```bash
aegean db build lineara -o aegean.db
# wrote 1721 documents to aegean.db
# search it:  aegean db search aegean.db KU-RO

aegean db add cypriot -o aegean.db
# aegean: appended a 'cypriot' corpus into a 'lineara' database; the database's script id is now 'mixed'   [stderr]
# added/updated 180 documents in aegean.db

aegean db search aegean.db KU-RO --limit 3
```
```
 'KU-RO' in aegean.db
┌───────┬─────┬───────┐
│ doc   │ pos │ text  │
├───────┼─────┼───────┤
│ HT9a  │ 25  │ KU-RO │
│ HT9b  │ 20  │ KU-RO │
│ HT11a │ 7   │ KU-RO │
└───────┴─────┴───────┘
```

The grown database now answers for both scripts: the same search with a
Cypriot token finds the Cypriot documents, and `aegean stats aegean.db` treats
the whole file as one corpus.

---

