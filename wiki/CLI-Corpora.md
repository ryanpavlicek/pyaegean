# CLI: Corpora, Library, Analysis & Data

Reference for the library manager (`aegean library`), top-level corpus commands
(`info`, `load`, `show`, `find`, `search`, `query`, `stats`, `dispersion`,
`keyness`, `balance`, `cite`, `export`, `combine`, `import`, `geo`, `sign`,
`bridge`, `plot`, `workbench`), research bundles (`aegean bundle`), statistical
analysis (`aegean analyze`), the local data store (`aegean data`), and SQLite
full-text databases (`aegean db`).

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [CLI: Greek NLP & Review](CLI-Greek) · [CLI: Biblical & Koine Greek](CLI-Bible) · [CLI: AI & MCP](CLI-AI)

---

## Library manager (`aegean library …`)

`aegean library` manages all local and downloadable resources in one command
group: 5 bundled corpora, 47 hosted datasets across Aegean scripts, Greek
epigraphy, Biblical, Patristic, Classical, Hellenistic, Imperial, Late Antique,
and Byzantine corpora, 3,844 categorized Greek collection works, ~1,778 Perseus
and First1KGreek works, 112 Greek patristic commentaries, hosted lexica, and
neural models.

```bash
aegean library                              # status overview: installed counts, disk usage, packs
aegean library packs                        # list all 10 packs
aegean library list --installed             # everything currently cached on disk
aegean library list patristics              # filter by category (corpus, bible, patristics, classical, byzantine, work, commentary, lexicon, model, other)
aegean library search Chrysostom            # search across corpora, 3,844 collection works, Perseus works, commentaries, lexica, models
aegean library info chrysostom-corpus       # metadata, license, aliases, status, install commands
aegean library install biblical             # download all 5 Biblical & Koine Greek bundles (~27 MB)
aegean library install church-fathers       # John Chrysostom (155) + Early/Late Fathers (712) + Apostolic Fathers (15)
aegean library install damos Iliad          # install by alias, title, TLG/OGC ID, or author:<name>
aegean library install author:Homer         # download every catalogued work by Homer
aegean library remove damos                 # delete cached files and report reclaimed space
aegean library remove biblical              # remove all datasets in a pack (bundled corpora stay intact)
```

| Pack | Aliases | Contents | Size |
|---|---|---|---|
| `biblical` | `bible`, `koine`, `nt-all` | `nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, `lxx-corpus` | ~27 MB |
| `church-fathers` | `fathers`, `patristics-full`, `saints` | `chrysostom-corpus`, `church-fathers-early-corpus`, `church-fathers-late-corpus`, `apostolic-fathers-corpus` (882 works, 17.98M tokens) | ~61 MB |
| `patristic` | `second-temple` | `apostolic-fathers-corpus`, `pseudepigrapha-corpus`, `patrologia-graeca-corpus` | ~27.2 MB |
| `ancient-greek` | `classical-pack`, `ancient-library` | `classical-greek-corpus`, `hellenistic-greek-corpus`, `imperial-greek-corpus`, `late-antique-greek-corpus` (2,792 works, 35.76M tokens) | ~123 MB |
| `byzantine-pack` | `byzantine-all`, `medieval-greek` | `byzantine-lit-corpus`, `byzantine-corpus` (197 works, 10.87M tokens) | ~41 MB |
| `aegean` | `scripts`, `linear` | `damos-corpus`, `sigla-corpus` | ~4.3 MB |
| `epigraphy` | `inscriptions` | `isicily-corpus`, `iip-corpus`, `iospe-corpus`, `igcyr-corpus`, `aphrodisias-corpus`, `crete-corpus`, `edh-corpus` | ~9.1 MB |
| `literary` | `epic`, `scholia` | `homer-scholia-corpus`, `byzantine-corpus` | ~8.0 MB |
| `lexica` | `dictionaries`, `lexicons` | `lsj-index`, `middle-liddell-index`, `cunliffe-index`, `autenrieth-index`, `abbott-smith-index` | ~19.3 MB |
| `neural` | `models`, `nlp` | `grc-joint`, `grc-paradigms` | ~173 MB |

In Python, `aegean.library` exposes `summary()`, `list_packs()`, `list_items()`,
`search()`, `install()`, and `remove()`. In the TUI (`aegean tui`), press `l`.

---

## Corpus commands (top level)

Every corpus command takes a **corpus** as its first argument. There are 30
registered corpora:

- **5 bundled offline:** `lineara`, `linearb`, `cypriot`, `cyprominoan`,
  `greek`.
- **25 hosted on demand:** `damos` (~5,900 Linear B tablets), `sigla` (Linear A
  dataset), `nt` (Greek New Testament), `lxx` (56-book Septuagint), **8
  categorized Greek library collections** (`chrysostom`, `church-fathers-early`,
  `church-fathers-late`, `classical-greek`, `hellenistic-greek`,
  `imperial-greek`, `late-antique-greek`, `byzantine-lit` — 3,844 works,
  64.35M tokens), `apostolic-fathers` (15 works), `pseudepigrapha` (44 works),
  seven Greek inscription corpora (`isicily`, `iip`, `iospe`, `igcyr`,
  `aphrodisias`, `crete`, `edh`), `byzantine` (12 vernacular Greek works),
  `homer-scholia` (Venetus A Iliad + scholia), `patrologia` (33 *Patrologia
  Graeca* volumes, 6.79M words), and `ddbdp` (57,331 documentary papyri, ~4.4M
  tokens).

Because `ddbdp`, `patrologia`, and the 8 categorized Greek collections are
multi-million-word archives, prefer `aegean db search ddbdp "βασιλέως"`,
`aegean find ἀγάπη chrysostom`, or work-scoped specifiers (`ogc002060`,
`chrysostom:In Matthaeum`, `PG073`) over loading an entire multi-million-token
archive into RAM (`aegean.db.stream(ddbdp_db())` or
`aegean.greek.load_collection_work("ogc002060")` in Python).

Registered ids match case-insensitively (`aegean info LINEARA` loads `lineara`).
Unknown ids fail with the full registered list and nearest suggestions:

```bash
aegean info bogus
# aegean: unknown corpus 'bogus'; expected a registered id (aphrodisias, apostolic-fathers, byzantine, byzantine-lit, chrysostom, church-fathers-early, church-fathers-late, classical-greek, crete, cypriot, cyprominoan, damos, ddbdp, edh, greek, hellenistic-greek, homer-scholia, igcyr, iip, imperial-greek, iospe, isicily, late-antique-greek, lineara, linearb, lxx, nt, patrologia, pseudepigrapha, sigla), a Greek work id like tlg0012.tlg001 or ogc002060, a path to a .json or .db corpus, or '-' for JSON on stdin
aegean load linera
# aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (…), …
```

> **Accepted corpus specifiers:** Anywhere a command accepts a corpus (and in
> Python via `aegean.open()` / `aegean.read_corpus()`), you can pass a
> registered id (`lineara`, `lxx`), an Open Greek Corpus work id (`ogc002060` or
> `chrysostom:In Matthaeum`), a *Patrologia Graeca* volume (`PG073`), a
> Perseus/First1KGreek CTS work id (`tlg0012.tlg001`), a Biblical passage
> (`John 1:1-5`, `Gen 1:1-5`, `MT Ps 23`), a saved corpus path (`.json`,
> `.json.gz`, or `.db`), or `-` for corpus JSON on stdin:
>
> ```bash
> aegean db build tlg0012.tlg001 -o iliad.db        # build a DB from a work id
> aegean stats ogc002060                            # run stats on Chrysostom on Matthew
> aegean stats iliad.json                           # run stats on a saved corpus
> aegean export tlg0012.tlg002 -f csv -o odyssey.csv
> ```

For document ids (`HT13`), OGC collection work ids (`ogc002060`), and CTS work
ids (`tlg0012.tlg001`), see [Greek Works and Books](Greek-Works-and-Books),
[Linear A](Linear-A), and [Linear B](Linear-B).

### `info` — corpus overview

Counts, source, license, and citation.

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

Omit `--json` for a formatted table. Python equivalent:

```python
import aegean
c = aegean.load("lineara")
len(c)                 # 1721
c.provenance.license   # 'Apache-2.0 (corpus JSON); …'
```

### `load` — filter by metadata

Filter on `--site`, `--period`, `--scribe`, and `--support`. Without `-o`,
prints matching documents (capped by `--limit`, default `20`); with `-o`, writes
a round-trippable `.json` or `.db` file.

```bash
aegean load lineara --site "Haghia Triada"               # list first 20 matches
aegean load lineara --site "Haghia Triada" -o ht.json    # → "wrote 1110 documents to ht.json"
```

### `show` — inspect one document

```bash
aegean show lineara HT13
```
```text
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

Document id lookup ignores case and spacing (`ht13`, `py ta 641`). For fetched
Greek works, the book or section number alone resolves:

```bash
aegean greek work tlg0012.tlg001     # fetch the Iliad
aegean show tlg0012.tlg001 1         # read Book 1
aegean show tlg0012.tlg001 2         # read Book 2
```

Ambiguous short ids list candidates instead of guessing; unknown ids suggest
nearest matches.

`--json` returns metadata, nested `lines`, and (when present) `tokens` with
flattened `form_*` fields and nested `form_state`. Text output adds a `form N:`
line beneath a token when diplomatic, regularized, normalized, or model-input
values differ.

### `find` — diacritic-insensitive full-text search

Searches any bundled or hosted corpus, `lxx`, `nt-editions`, `patrologia` (or a
volume such as `PG073`), a Greek work id (`tlg0012.tlg001`), or a local
`.json`/`.json.gz`/`.db` file using lazy SQLite FTS5 sidecar indexes under
`PYAEGEAN_CACHE/fts/`. Diacritics are folded by default unless `--exact` is set.

```bash
aegean find λόγος nt --book John --limit 10
aegean find λόγος patrologia --book PG073
aegean find φῶς lxx --offline
aegean find ἀγάπη nt-editions --edition sblgnt --exact --json
```

Options: `-b/--book`, `-e/--edition`, `-n/--limit/--top` (`25` default; `0` =
all), `--exact`, `--offline`, `--json`.

### `search` — wildcard sign-pattern word search

`*` matches one sign. Prints matching words and token frequencies.

```bash
aegean search lineara "KU-*-RO"
```
```text
'KU-*-RO': 1 word(s)
┌──────────┬───────┐
│ word     │ count │
├──────────┼───────┤
│ KU-MA-RO │ 1     │
└──────────┴───────┘
```

### `query` — compound query engine

Combine repeatable `--where field=value` rows. Rows AND together by default;
prefix a field with `or:` to OR it, or `!` to negate it. `--output-kind` selects
`inscriptions` (default) or `words`. Under `words`, counts default to **document
frequency** (distinct documents containing each word); pass `--count-unit token`
for token frequency. `--view surface|normalized|lemma` sets the lexical key
(default `--view legacy` preserves case-insensitive predicates and separate
surface keys). `--statuses certain,unclear,restored,lost` filters editorial
reading status (omit for all). JSON `metadata` records the view, normalization,
exclusions, and denominator prior to word filters.

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "or:id-contains=ZA" \
       --output-kind words --json
```

Every result includes a query `description` and exact-subset `citation`
(`--json | jq .citation`). List all fields with `aegean query CORPUS --fields`:

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

**Saving matched subsets:** Pass `-o/--output` (`.json` or `.db`) to save
matched inscriptions as a reusable corpus with a `subset: query(…) → N documents`
provenance note (`-o` writes inscriptions only; use `--output-kind words --json`
for word lists):

```bash
aegean query lineara --where "site-is=Zakros" -o zakros.json
# wrote 53 inscriptions to zakros.json
aegean stats zakros.json --top 3
```

> **Truncation:** `--limit` caps both table rows and JSON arrays (`--limit 0`
> returns all rows), while `matched` (`{"inscriptions": …, "words": …}`) always
> preserves the untruncated totals.

#### Worked query examples

Two rows ANDed together:

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "ins-contains-word=KU-RO" --limit 3
```
```text
Site is: Haghia Triada · Contains exact word: KU-RO → 32 inscription(s)
┌───────┬───────────────┬───────┐
│ id    │ site          │ words │
├───────┼───────────────┼───────┤
│ HT9a  │ Haghia Triada │ 9     │
│ HT9b  │ Haghia Triada │ 10    │
│ HT11a │ Haghia Triada │ 6     │
└───────┴───────────────┴───────┘
```

OR prefix (`or:`) and negation (`!`):

```bash
aegean query lineara --where "site-is=Zakros" --where "or:site-is=Phaistos" --limit 3
# Site is: Zakros · Site is: Phaistos → 119 inscription(s)

aegean query lineara --where "site-is=Haghia Triada" --where "!ins-contains-word=KU-RO" --limit 3
# Site is: Haghia Triada · NOT Contains exact word: KU-RO → 1078 inscription(s)
```

Word output with word-scope filtering:

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "word-prefix=KU" --output-kind words --limit 5
```
```text
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

Mistyped field names exit `1` with a suggestion:

```bash
aegean query lineara --where "site=Zakros"
# aegean: unknown field 'site' — did you mean 'site-is'? (`aegean query lineara --fields` lists all)
```

### `stats` — frequency tables

Counts words by default, or signs with `--signs`.

For words, `--view surface` preserves exact strings, `normalized` applies NFC,
lowercasing, and final-sigma folding while retaining diacritics, and `lemma`
applies that normalization to existing lemma annotations (excluding missing
lemmas without running an analyzer). `--count-unit token|document` chooses token
frequency (default) or document frequency. `--statuses` filters editorial
reading status (including typed segments). Word-view options and `--details`
cannot be combined with `--signs`.

Default `--json` returns a list of `{item, count}` objects. Passing `--details`
or a non-default `--view`, `--count-unit`, or `--statuses` returns
`{frequencies, metadata, citation}`.

```bash
aegean stats nt --view lemma --count-unit document --details --json
aegean query nt --view lemma --count-unit token --where "word-prefix=ἀγαπ" --output-kind words --json
```

```bash
aegean stats lineara --signs --top 5
```
```text
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

### `dispersion` — Gries' DP

Measures distribution across documents (`0` = perfectly even, `1` = concentrated
in few documents). Pass one item, or omit it to rank the corpus.

```bash
aegean dispersion lineara --top 5
```
```text
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

### `keyness` — characteristic vocabulary

Compares a metadata subset against the rest of the corpus, or compares two
corpora with `--reference`. Reports log-likelihood (`G2`), `log-ratio`, and `p`.

```bash
aegean keyness lineara --site "Zakros" --top 5
```
```text
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

> **Writing results to files:** `stats`, `keyness`, `dispersion`, `search`, and
> `balance` accept `--output/-o` (`.json`, `.csv`, or `.txt` by extension),
> printing `wrote <path>` on stderr. Combining `-o` with `--json` writes the
> file and prints JSON to stdout:
>
> ```bash
> aegean stats lineara --top 3 -o freq.csv
> # wrote freq.csv                                  [stderr]
> ```

### `balance` — accounting reconciliation

Compares stated totals (`KU-RO` in Linear A, `TO-SO` in Linear B) against the
sum of line items for one document or the whole corpus.

```bash
aegean balance lineara HT13
```
```text
┌──────┬────────┬────────┬──────────┬──────┬──────────┐
│ doc  │ marker │ stated │ computed │ diff │ balances │
├──────┼────────┼────────┼──────────┼──────┼──────────┤
│ HT13 │ KU-RO  │ 130.5  │ 131.0    │ 0.5  │ NO       │
└──────┴────────┴────────┴──────────┴──────┴──────────┘
```

`--strict` exits `1` whenever any checked total fails to balance. See
[Linear A](Linear-A) for interpretation of `KU-RO` discrepancies.

### `cite` — cite a corpus or subset

```bash
aegean cite lineara --site "Haghia Triada"
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.
#   — https://… [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
```

`--style` accepts `plain` (default), `bibtex`, or `apa`.

### `export` — JSON, CSV, Parquet, EpiDoc, SQLite, Workbench, RDF

```bash
aegean export lineara -f csv -o lineara.csv               # → "wrote 1721 documents to lineara.csv (csv)"
aegean export greek -f epidoc -o greek.xml                # EpiDoc TEI
aegean export lineara -f sqlite -o lineara.db             # same DB as `aegean db build`
aegean export lineara -f workbench -o wb.json             # Linear A Workbench JSON
aegean export edh -f ttl -o edh.ttl                       # Linked Open Data (Turtle)
```

| `--format` | Output | Dependency |
|---|---|---|
| `json` | Lossless, round-trippable corpus | core |
| `csv` | One row per document, token, or word (`--level`) | core |
| `parquet` | Columnar equivalent of CSV | `[parquet]` extra |
| `epidoc` | EpiDoc TEI XML (directory with one file per document) | core |
| `sqlite` | SQLite database with FTS5 | core |
| `workbench` | Linear A Research Workbench JSON (text and surface metadata round-trip; reading statuses, annotations, and typed forms are lossy) | core |
| `ttl` / `jsonld` | Linked Open Data (Turtle / JSON-LD) with authoritative subject URIs (papyri.info for DDbDP with Trismegistos `rdfs:seeAlso`, Trismegistos for EDH, I.Sicily URIs, or `urn:` / `--base-uri`), Dublin Core terms, WGS84 coordinates, and per-document licenses | core |

`--level token` (CSV/Parquet) emits one row per token and expands token
annotations (lemma, morph, Strong's, gloss) into columns. Two optional column
blocks are written only when at least one token uses them: sixteen `form_*`
columns (`form_diplomatic`, `form_regularized`, `form_normalized`,
`form_model_input`, `form_model_input_ops`, `form_model_input_source`,
`form_segments`, and editorial status/damage/uncertainty fields) and nine
`alignment_*` span columns. Filters (`--site`, `--period`, `--scribe`,
`--support`) apply before export.

#### Worked format matrix (Cypriot, 180 documents)

```bash
aegean export cypriot -f json -o cypriot.json         # wrote 180 documents to cypriot.json (json)
aegean export cypriot -f csv -o cypriot.csv           # wrote 180 documents to cypriot.csv (csv)
aegean export cypriot -f parquet -o cypriot.parquet   # wrote 180 documents to cypriot.parquet (parquet)
aegean export cypriot -f epidoc -o cypriot-epidoc/    # wrote 180 documents to cypriot-epidoc (epidoc)
aegean export cypriot -f sqlite -o cypriot.db         # wrote 180 documents to cypriot.db (sqlite)
aegean export lineara -f workbench -o wb.json         # wrote 1721 documents to wb.json (workbench)
```

`epidoc` creates a directory containing one TEI XML file per inscription; all
other formats write a single file. Token-level CSV example on `nt`:

```bash
aegean export nt -f csv --level token -o nt-tokens.csv   # wrote 260 documents to nt-tokens.csv (csv)
head -2 nt-tokens.csv
# doc_id,line_no,position,text,kind,status,site,period,lemma,morph,strongs,normalized,upos,ref,gloss
# Matt 1,1,0,Βίβλος,word,certain,,Koine,βίβλος,N-NSF,976,Βίβλος,NOUN,Matt.1.1,"a written book, roll, or volume"
```

### `greek interop` — portable annotation bundles

Converts a strict CoNLL-U document to and from a portable JSON bundle containing
the target projection, a SHA-256-bound sidecar, and a loss report, without
running any model. Install `[cli,interop]` (or `[cli]` plus `[spacy]`,
`[stanza]`, or `[cltk]`):

```bash
aegean greek interop export treebank.conllu --target spacy -o treebank.spacy.json
aegean greek interop report treebank.spacy.json
aegean greek interop import treebank.spacy.json -o treebank-restored.conllu
```

`report` verifies the bundle and prints target/version, round-trip losslessness,
and per-field transport status. `import` reconstructs the CoNLL-U file. The
output is pyaegean's JSON bundle format, not a spaCy, Stanza, or CLTK binary
serializer.

### `combine` — merge corpora

Merges two or more corpus specifiers (ids, work ids, `.json`/`.db` files, or
`-`) into one `.json` or `.db` file while recording all sources in provenance:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db    # Iliad + Odyssey in one DB
aegean combine lineara cypriot -o aegean-mix.json           # wrote 1901 documents (merged 2 sources)
```

`--on-conflict` handles duplicate document ids: `error` (default), `first`,
`last`, or `suffix` (`#2`, `#3`, …). Python equivalents: `aegean.combine(...)`,
`Corpus.merge(*others, dedupe=…)`, and `Corpus.subset(ids)`.

### `import` — import plain text, CSV, Workbench, or EpiDoc

Converts local `.txt` files, folders, `.csv` tables, Workbench exports, or
token-carrier EpiDoc XML into a `.json` or `.db` corpus. The default
`--token-view all` preserves decoded source text, whitespace, and aligned tokens
(punctuation, numerals, foreign text) while keeping linguistic word counts
separate. `--token-view words` selects the legacy lossy word-only import
(applies to plain text and CSV only).

```bash
aegean import john.txt -o john.json --script nt         # plain text → corpus
aegean stats john.json --top 5
```

- **`--split`:** `whole` (default, one document), `paragraph` (blank-line
  blocks), or `line` (one per non-empty line). Multi-block ids are numbered
  `<base>:1`, `<base>:2`, … (override `<base>` with `--id`).
- **Directories:** imports matching files (`--glob`, default `*.txt`), using
  file stems as document ids (`#2`, `#3` on collision):
  `aegean import poems/ -o poems.db --split line`.
- **CSV:** one document per row (`--text-col`, default `text`; `--id-col`,
  default `<stem>:<row>`):
  `aegean import verses.csv -o verses.json --script nt --text-col line --id-col id`.
- **`--encoding`:** defaults to `utf-8-sig` (strips UTF-8 BOM).
- **Workbench JSON (`--workbench`):** inverse of `export -f workbench`. Carries
  text and surface metadata only; reading statuses, typed `TokenFormState`, and
  annotations are not preserved by Workbench JSON.
- **EpiDoc TEI (`--epidoc`):** imports any token-carrier EpiDoc file or folder
  of `.xml` files using Python's stdlib XML parser, recovering ids, find-places,
  lines/tokens, editorial certainty (`<unclear>`/`<supplied>`), typed choices,
  and `<app>` variants semantically (arbitrary free-text TEI is not converted to
  typed token state).

```bash
aegean import wb.json --workbench -o back.json
aegean import ins/ --epidoc --script lineara -o back.json
```

`import` is the required entry point for raw `.txt` files: passing a `.txt`
directly to `stats` or `load` exits `1` with the `aegean import` command. Python
equivalents: `aegean.io.from_text`, `from_text_file`, `from_text_dir`, and
`from_csv` (accepting `token_view="all"|"words"` and `meta_cols=`).

### `geo` — find-site coordinates and word maps

```bash
aegean geo lineara
```
```text
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

Add `-o sites.geojson` (`.json`/`.geojson`; requires `[geo]` extra) to export
GeoJSON. `--word` maps case-insensitive per-site attestations (no extra required
for table output):

```bash
aegean geo lineara --word KU-RO
aegean geo damos --word po-ti-ni-ja
```

See [Geography](Geography) for coordinate provenance and Pleiades alignment.

### `sign` — inspect a single sign

Prints glyph, Unicode codepoint, phonetic value, and script attributes:

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

### `bridge` — syllabic word to Greek reading

For deciphered syllabaries (`linearb`, `cypriot`), prints the Greek reading and
gloss:

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)
```

### `cache` — opt-in analysis cache

Inspects or clears the optional analysis memoization cache (distinct from the
download store in `aegean data store`):

```bash
aegean cache
# analysis cache: off — set PYAEGEAN_ANALYSIS_CACHE=1 (or a path) to enable
aegean cache --clear
```

Set `PYAEGEAN_ANALYSIS_CACHE=1` (or a directory path) to cache expensive
analyses (`dispersion`, `keyness`, `clusters`) across runs. Entries are stored
in owner-only SQLite using a typed JSON codec (`AEGEAN-CACHE-V2`, never
`pickle`), so corrupt or stale rows fall back safely to recomputation.

### `doctor` — the offline environment check

Checks Python and pyaegean versions, installed optional extras, data store
location/size/writability and leftover partial downloads, neural model bundles,
and analysis cache status. Never touches the network.

```bash
aegean doctor
```
```text
                  versions
┌────┬──────────┬───────────────────────────┐
│    │ check    │ value                     │
├────┼──────────┼───────────────────────────┤
│ OK │ python   │ 3.14.4                    │
│ OK │ pyaegean │ 0.73.1                    │
│ OK │ platform │ Windows-11-10.0.26200-SP0 │
└────┴──────────┴───────────────────────────┘
…four more tables: optional extras, data store, neural model bundles, analysis cache…
doctor: all checks passed
```

Missing extras and uncached datasets are reported as informational rows with
their install/fetch commands. Actual errors (Python < 3.10, unwritable cache,
leftover partial downloads) exit `1` and print the remediation. Supports
`--json` (`{ok, issues, versions, extras, data_store, models, analysis_cache}`)
and `-o`.

### `plot` — generate static figures (`[viz]` extra)

Writes one `.png`, `.svg`, or `.pdf` figure to `--output/-o`.

| `KIND` | Figure |
|---|---|
| `freq` | Top-N sign or word frequencies |
| `dispersion` | DP scatter plot (annotates top N) |
| `keyness` | Keyness bars (subset vs rest, or vs `--reference`) |
| `network` | Co-occurrence network (`--word` for ego network) |
| `balance` | Accounting reconciliation chart |
| `scansion` | Metrical scansion grid for one Greek line (`-` reads stdin) |
| `findspots` | Find-site map |
| `timeline` | Date histogram (`--bin-width` in years) |
| `signnet` | Sign/word co-occurrence network (`--scope document\|line`) |

```bash
pip install "pyaegean[viz]"
aegean plot keyness lineara --site Zakros -o zakros.png
aegean plot scansion "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ" -o scan.svg --meter hexameter
```

### `workbench` — serve the multi-script Aegean Research Workbench locally

```bash
aegean workbench                                            # fetch v2.1.0 build (~3.3 MB) & open in browser
aegean workbench --fetch-images                             # also download Linear A facsimile imagery (~116 MB)
aegean workbench --site "Haghia Triada" --module arith      # open pre-scoped to a site and module
aegean workbench --doc HT13                                 # jump straight to an inscription detail view
aegean workbench --corpus damos                             # Linear B (auto-sets ?script=linearb, to-so/o-pe-ro accounting)
aegean workbench --corpus cypriot                           # Cypriot Syllabic (auto-sets ?script=cypriot)
aegean workbench --corpus cyprominoan                       # Cypro-Minoan (auto-sets ?script=cyprominoan)
aegean workbench --damos                                    # auto-mount DAMOS Linear B frequencies for Sign Inventory
aegean workbench --state workspace.json                     # auto-load & persist annotations/notes/collections locally
aegean workbench --dir ../linearaworkbench/dist --auto-port # serve a local build on an OS-assigned port
```

Fetches the SHA-256-pinned **`workbench-app-v2.1.0`** static build (~3.3 MB,
bundling self-hosted SIL OFL 1.1 **Noto Sans Aegean fonts** for Linear A,
Linear B, Cypriot Syllabic, and Cypro-Minoan, plus Linear B `to-so` / `o-pe-ro`
accounting reconciliation) and serves the browser UI (corpus, maps, commentary,
and all 34 workspaces / 59 views) on loopback (`127.0.0.1`) until `Ctrl+C`.

**Multi-script `--corpus` bridge:** Passing `--corpus <id-or-path>` (such as
`damos`, `cypriot`, `cyprominoan`, or a local JSON export) serializes the
corpus with `aegean.io.to_workbench_bundle()` (preserving `_meta.script`,
`inscriptions`, `signs`, and `phoneticMap`), mounts it at
`/api/local/corpus.json`, and automatically appends `?script=<script_id>` to
the launch URL whenever the corpus is not Linear A.

Pass `--fetch-images` (or `aegean data fetch lineara-images`) to mount the
~116 MB Linear A facsimile archive at `/upstream/images/`. Pass
`--state workspace.json` to enable loopback-only `GET`/`PUT` workspace
persistence at `/api/local/backup` (readable in Python via
`aegean.io.load_workbench_backup()`).

---

## Research bundles — `aegean bundle …`

Packages corpora, citations, workbench workspace backups, review CSVs (including
editable `.companion.json` sidecars), and analysis/evaluation receipts into
deterministic, SHA-256-verified `.zip` archives (`aegean-research-bundle/1`).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `bundle create` | Build a deterministic `.zip` research bundle with `manifest.json` and citations | `-c/--corpus` `--dataset` `--title` `--description` `--site` `--period` `--state` `-r/--review` `--receipt` `--embed-corpus auto\|always\|never` `--json` | `aegean bundle create study.zip -c lineara --site Zakros --state ws.json -r review.csv` |
| `bundle inspect` | Show bundle format, version, redistributable status, corpus mode, license notes, and member checksums | `--json` | `aegean bundle inspect study.zip` |
| `bundle verify` | Validate archive path safety and SHA-256 checksums for every member (exits `1` on failure) | `--json` | `aegean bundle verify study.zip` |
| `bundle extract` | Verify and unpack bundle members safely into a target directory | `--json` | `aegean bundle extract study.zip ./unpacked` |
| `bundle hydrate` | Verify, unpack, and reconstruct the bundle, including pointer corpora | `--fetch` `--json` | `aegean bundle hydrate study.zip ./hydrated --fetch` |

**NC-safe license policy (`--embed-corpus`):**

- `auto` (default): embeds corpora with open/redistributable licenses as
  `corpus.json.gz`. Corpora carrying non-commercial (`CC BY-NC*`) or restricted
  licenses (such as `damos`) are **not** embedded; instead, `manifest.json`
  records a `CorpusReference` retrieval pointer (dataset id, version, upstream
  URL, license, SHA-256, and `--site`/`--period` filters) so public bundles stay
  redistributable (`redistributable=yes`).
- `never`: always store a retrieval pointer without embedding corpus data.
- `always`: embed the corpus even when non-commercial or restricted, stamping
  `redistributable=no` with an explicit license note for private archival use.

```bash
# Redistributable bundle over DAMOS (stores a pointer instead of NC data):
aegean bundle create pylos-study.zip --corpus damos --site Pylos \
    --title "Pylos Linear B study" --review pylos-review.csv --receipt eval.json
aegean bundle inspect pylos-study.zip
aegean bundle verify pylos-study.zip

# Reconstruct on another machine (fetches DAMOS under its upstream license):
aegean bundle hydrate pylos-study.zip ./repro --fetch
```

Inside the archive: `manifest.json`, `citations.json`, `CITATIONS.bib`,
`CITATIONS.txt`, optional `corpus.json.gz`, optional `workbench-state.json`,
`review/*`, and `receipts/*`. In Python, `aegean.bundle` provides
`create_bundle`, `inspect_bundle`, `verify_bundle`, `extract_bundle`,
`hydrate_bundle`, and `is_redistributable_license`.

---

## Analysis — `aegean analyze …`

Exploratory surface analyses over Aegean and Greek corpora. See
[Analysis](Analysis) for method details.

### Phonetic distance and alignment

```bash
aegean analyze distance KU-RO KI-RO
# KU-RO ↔ KI-RO: 0.200

aegean analyze align KU-RO KI-RO        # per-position match / vowel / same-class / far / gap
```

### Cross-script comparison

`compare` romanizes two words across scripts and aligns them by sound; `nearest`
ranks a corpus's words by phonetic distance to a query word.

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

aegean analyze nearest qa-si-re-u greek --top 5 --json
```

`--script-a` and `--script-b` accept `greek`, `lineara`, `linearb`, and
`cypriot`. `--fold-aspiration` folds θ/φ/χ → t/p/k for comparison against
defective syllabic spelling. Treat alignments and rankings as exploratory
evidence, not etymological proof.

### Association and co-occurrence

```bash
aegean analyze assoc lineara KU-RO KI-RO    # χ², log-likelihood, Fisher, PMI
aegean analyze cooccur lineara KU-RO        # words co-occurring on the same tablet, ranked
```

### Morphology, structure, scribal hands

```bash
aegean analyze clusters lineara             # stem + productive-suffix clusters
aegean analyze structure lineara            # accounting / libation / list / text / other census
aegean analyze structure lineara HT13       # classify one document
aegean analyze hands damos                  # scribal-hand profiles (requires scribe metadata)
aegean analyze hands damos --hand 103       # one hand's characteristic vocabulary
```

> **Saving analysis outputs:** `assoc`, `cooccur`, `clusters`, `structure`,
> `hands`, and `nearest` accept `--output/-o` (`.json`, `.csv`, or `.txt`) and
> `--top 0`. `structure` and `hands` also accept `--site`, `--period`,
> `--scribe`, and `--support`:
>
> ```bash
> aegean analyze cooccur lineara KU-RO -o ku-ro-neighbours.json
> aegean analyze clusters lineara -o clusters.csv
> ```

---

## Data — `aegean data …`

Manages the persistent, SHA-256-verified download store. Cached datasets do not
expire automatically: valid entries matching the current pin are reused; a
changed pin, stale integrity stamp, or `fetch --force` triggers a replacement
download, and `remove` deletes entries explicitly.

```bash
aegean data list                                   # all fetchable datasets + status/size
aegean data fetch grc-joint                        # download or reuse cached pin
aegean data fetch damos                            # stem alias for damos-corpus
aegean data remove grc-joint                       # delete one dataset (--all clears all)
aegean data versions --json > data-versions.json   # SHA-256 manifest for reproducibility
aegean data store                                  # store path + contents (override: PYAEGEAN_CACHE)
```

For Linear B, fetch DAMOS (`aegean data fetch damos`, ~5,900 tablets, CC
BY-NC-SA 4.0). LiBER (`liber.cnr.it`) is rights-restricted and browse-only. To
load your own licensed Linear B export, use
`aegean import x.xml --epidoc --script linearb` or set
`PYAEGEAN_LINEARB_CORPUS_URL`.

(`aegean data cache` is a deprecated alias for `aegean data store`.)

### Worked store round trip

```bash
aegean data remove nt-corpus
# removed nt-corpus: C:\Users\you\.cache\pyaegean\nt-corpus (15.8 MB reclaimed)

aegean data list        # nt-corpus row now reads:
# │ nt-corpus         │ no             │ Greek New          │ CC0-1.0           │

aegean data fetch nt    # stems resolve: nt = nt-corpus (also damos, sigla)
# C:\Users\you\.cache\pyaegean\nt-corpus
# load it:  aegean info nt        [stderr]

aegean data list        # downloaded again with on-disk size:
# │ nt-corpus         │ yes (15.8 MB)  │ Greek New          │ CC0-1.0           │
```

`aegean data list` shows the full live registry (currently 47 entries), with
on-disk sizes for cached datasets. Datasets download on demand and are never
bundled in the Apache-2.0 wheel.

To install groups by research area, use `aegean library`:

```bash
aegean library packs                  # biblical, patristic, aegean, epigraphy, literary, lexica, neural
aegean library install epigraphy      # all 7 Greek inscription corpora
aegean library install patristic      # Apostolic Fathers, OT Pseudepigrapha, Patrologia Graeca
```

`aegean data versions --json` writes a SHA-256 reproducibility manifest covering
bundled and fetched datasets. See [Data & Provenance](Data-and-Provenance) for
the full 39-dataset table of sizes, build scripts, and licenses.

---

## SQLite — `aegean db …`

Builds and searches SQLite corpus databases (documents, tokens, and an FTS5
full-text index).

```bash
aegean db build lineara -o lineara.db        # → "wrote 1721 documents to lineara.db"
aegean db search lineara.db KU-RO --limit 3
```
```text
   'KU-RO' in lineara.db
┌───────┬─────┬───────┐
│ doc   │ pos │ text  │
├───────┼─────┼───────┤
│ HT9a  │ 25  │ KU-RO │
│ HT9b  │ 20  │ KU-RO │
│ HT11a │ 7   │ KU-RO │
└───────┴─────┴───────┘
```

`db search` matches whole tokens by default (`KU-RO` will not match
`PO-TO-KU-RO`). Pass `--substring` to match substrings instead. The database
argument also accepts DB-backed corpus ids directly:
`aegean db search ddbdp "βασιλέως"`.

`db search` opens databases read-only (a missing path exits `1` pointing to
`aegean db build`). `--limit 0` returns every match, and `--output/-o` writes
`.json`, `.csv`, or `.txt`. Whole-token searches with zero hits suggest
`--substring`:

```bash
aegean db search lineara.db KU-RO-ZZ
# no matches (whole-token) — pass --substring to match within tokens
```

`db build` accepts any corpus specifier (including work ids like
`tlg0012.tlg001`). `--no-fts` omits the FTS5 index.
`aegean export CORPUS -f sqlite -o file.db` produces the same schema. In Python,
read back with `Corpus.from_sql(path)` or stream with `aegean.db.stream(path)`.

### `db index` — exact lexical indexes

Builds an optional lexical index to speed up exact `surface`, `normalized`, and
`lemma` searches while keeping reading-status filters and hit order identical:

```bash
aegean db index corpus.db
aegean db index corpus.db --status --json
aegean db search corpus.db λόγος --view lemma --statuses certain --json
```

`db index` requires a writable local path (copy fetched databases before
indexing). Subsequent token edits invalidate the index and fall back to table
scans until `db index` is re-run. Search and status checks stay read-only;
substring searches continue using table scans.

### `db annotate` & `db job-status` — resumable annotation jobs

Annotates large SQLite Greek corpora one document at a time with transactional
checkpoints so interrupted runs resume safely:

```bash
aegean db annotate corpus.db -o annotated.db --job-dir ./job-state --neural --with-dependencies
aegean db job-status ./job-state --json
# Resume after interruption (verifies source snapshot, options, and backend):
aegean db annotate corpus.db -o annotated.db --job-dir ./job-state --neural --with-dependencies --resume
```

Each job freezes a WAL-safe source snapshot, processes documents in bounded
keyset order under an exclusive file lock, and publishes the finished database
atomically on completion.

### `db add` — upsert into an existing database

Upserts documents into an existing `.db` file: matching document ids are
replaced, new ids are inserted, and FTS5 rows are refreshed.

```bash
aegean db build lineara -o aegean.db         # → "wrote 1721 documents to aegean.db"
aegean db add cypriot -o aegean.db           # → "added/updated 180 documents in aegean.db"
```

Appending a second script updates the database's `script_id` to `mixed` and
prints a stderr notice. Python equivalents:
`corpus.to_sql("aegean.db", append=True)` or
`aegean.db.to_sqlite(corpus, "aegean.db", append=True)`.

### Worked SQLite chain

```bash
aegean db build lineara -o aegean.db
# wrote 1721 documents to aegean.db
# search it:  aegean db search aegean.db KU-RO

aegean db add cypriot -o aegean.db
# aegean: appended a 'cypriot' corpus into a 'lineara' database; the database's script id is now 'mixed'   [stderr]
# added/updated 180 documents in aegean.db

aegean db search aegean.db KU-RO --limit 3
```
```text
 'KU-RO' in aegean.db
┌───────┬─────┬───────┐
│ doc   │ pos │ text  │
├───────┼─────┼───────┤
│ HT9a  │ 25  │ KU-RO │
│ HT9b  │ 20  │ KU-RO │
│ HT11a │ 7   │ KU-RO │
└───────┴─────┴───────┘
```

The combined database serves searches and stats across both scripts.
