# CLI Cheatsheet

One-page index of every `aegean` command and its key flags with runnable
examples. For guided explanations and worked outputs, see [CLI](CLI). If you are
new to the terminal, start with [Getting Started](Getting-Started).

> **Available in v0.72.0.** All commands, research bundles, multi-script
> workbench flags, TUI review options, and Greek pipeline controls below match
> the current release.

```bash
pip install "pyaegean[cli]"     # adds typer + rich; core library stays zero-dependency
aegean --help                   # command map
aegean --version                # pyaegean 0.72.0
```

The core package installs the `aegean` entry point; executing commands requires
the `[cli]` extra.

## Global conventions

| Convention | Behavior | Example |
|---|---|---|
| **`--json`** | Prints one JSON document to stdout with readable Greek (`ensure_ascii=False`). Combines with `-o/--output`: writes the file (`wrote <path>` on stderr) and still prints JSON to stdout. | `aegean info lineara --json` |
| **`-` reads stdin** | Any command accepting a `TEXT` argument reads from stdin when given `-`. | `echo "μῆνιν" \| aegean greek lemmatize -` |
| **Flexible corpus specifiers** | Every corpus argument accepts a registered id, a *Patrologia Graeca* volume (`PG073`), a Greek work id (`tlg0012.tlg001`), a saved `.json`/`.json.gz`/`.db` file, or `-` for corpus JSON on stdin. | `aegean stats lineara.json` |
| **`--top` / `--limit`** | Interchangeable aliases for row caps, including `plot`. `0` lifts the cap wherever `--help` says `0 = all` (except `greek rarity`, which slices directly). | `aegean stats lineara --limit 3` |
| **Exit codes** | `0` success · `1` domain error (one stderr line prefixed `aegean:`) · `2` usage error. | `aegean greek scan "λόγος"` → exit `1` |

Notation summary (full guide: [CLI → Reading usage lines](CLI#reading-usage-lines)):

| Notation | Meaning |
|---|---|
| `CORPUS` (uppercase, no dashes) | Required positional argument: `aegean stats lineara` |
| `--top 5` / `--signs` / `-o` | Named options in any order (`-o` = `--output`, `-f` = `--format`) |
| `"KU-*-RO"` (double quotes) | Quote values containing spaces, `*`, or punctuation (double quotes work across all shells) |

Every command and group supports `-h` / `--help`. Five corpora are bundled
offline (`lineara`, `linearb`, `cypriot`, `cyprominoan`, `greek`) and 16 more
download to the local cache on first use (`damos`, `sigla`, `nt`,
`apostolic-fathers`, `pseudepigrapha`, `isicily`, `iip`, `iospe`, `igcyr`,
`aphrodisias`, `crete`, `edh`, `byzantine`, `homer-scholia`, `patrologia`,
`ddbdp`). In Python, `aegean.open(spec)` and `aegean.read_corpus(spec)` resolve
the same specifiers. For multi-million-word archives, use
`aegean db search ddbdp "βασιλέως"` and `aegean find λόγος patrologia`.

---

## Command overview

| Group | Commands |
|---|---|
| **(top level)** | `quickstart` `repl` `tui` `info` `load` `show` `find` `search` `query` `stats` `dispersion` `keyness` `cache` `doctor` `balance` `cite` `export` `combine` `import` `geo` `sign` `bridge` `plot` `workbench` |
| **`library`** | `status` `packs` `list` `search` `info` `install` `remove` (7 packs, 21 corpora, Biblical bundles, ~1,778 works, 86 commentaries, lexica, models) |
| **`bundle`** | `create` `inspect` `verify` `extract` `hydrate` (deterministic, SHA-256-verified, NC-safe `.zip` research bundles) |
| **`greek`** | `normalize` `betacode` `strip` `tokenize` `syllabify` `accent` `accentuate` `sandhi` `quantities` `scan` `ipa` `profile` `tag` `lemmatize` `morph` `inflect` `parse` `gloss` `usage` `lexica` `lexicon-link` `rarity` `missing-forms` `pipeline` `stream` `explain` `annotation-profiles list` `annotation-profiles show` `interop export` `interop import` `interop report` `conllu inspect` `conllu export` `work` `works` `catalog` `eval` |
| **`bible`** | `read` `compare` `witnesses` `strongs` `word-study` `search` `commentary` `books` `psalm` `status` `install` |
| **`analyze`** | `distance` `align` `compare` `nearest` `assoc` `cooccur` `clusters` `structure` `hands` `hand` `dossiers` `syllabary` `bridge` |
| **`data`** | `list` `fetch` `remove` `versions` `store` |
| **`db`** | `build` `add` `search` `index` `annotate` `job-status` |
| **`review`** | `export` `apply` `merge` (annotation review round-trip, multi-reviewer merge) |
| **`ai`** | `translate` `gloss` `summarize` `hypotheses` `ask` `extract` `eval` `providers` |
| **`aegean-mcp`** | Separate console script serving 29 read/analysis tools over MCP stdio |

---

## Corpus & analysis (top level)

Every corpus command accepts a registered id, Greek work id, *Patrologia
Graeca* volume (`PG073`), `.json`/`.json.gz`/`.db` path, or `-`, plus `--json`.
`stats`, `dispersion`, `keyness`, `search`, and `balance` also take
`-o/--output` (`.json`, `.csv`, or `.txt` by extension), printing
`wrote <path>` on stderr and combining cleanly with `--json`.

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `quickstart` | Offline 8-step tour on bundled data | `--no-run` | `aegean quickstart` |
| `repl` | Interactive shell (also launched by bare `aegean` on a TTY): live inline ghost-text + dropdown prediction, persistent history, session corpus cache. Directives: `use CORPUS` (`use off`), `:examples`, `:help`, `:exit` | — | `aegean` (or `aegean repl`) |
| `tui` | Full-screen Textual UI (`[tui]` extra): 9 screens — Home (`h`), Corpus browser (`c`), Greek workbench (`g`), Biblical Greek (`b`), Library manager (`l`), Annotation review (`r`), Works (`w`), Data store (`d`), Command console (`:`). See [TUI](TUI) | `-r/--review` `-c/--corpus` | `aegean tui --review a.csv --review b.csv --corpus nt` |
| `library` | Manage 39 hosted datasets, 5 bundled corpora, ~1,778 Greek works, 86 patristic commentaries, lexica, models, and 7 packs (`biblical`, `patristic`, `aegean`, `epigraphy`, `literary`, `lexica`, `neural`) | `status` `packs` `list` `search` `info` `install` `remove` `--installed` `--available` `--all` `--json` | `aegean library install biblical` |
| `doctor` | Offline environment check (versions, extras, data store, model bundles, analysis cache); exits `1` on issues | `--json -o/--output` | `aegean doctor` |
| `info` | Corpus counts, provenance, license, citation | `--json` | `aegean info lineara` |
| `load` | Filter by metadata; list matches or export | `--site --period --scribe --support -o/--output --limit` | `aegean load lineara --site "Haghia Triada"` |
| `show` | One document's metadata and line-by-line tokens | `--json` | `aegean show lineara HT13` |
| `find` | Diacritic-insensitive SQLite FTS5 search across any corpus, `lxx`, `nt-editions`, `patrologia` / `PG073`, TLG work, or local `.json`/`.db` | `-b/--book -e/--edition -n/--limit --exact --offline --json` | `aegean find λόγος patrologia` |
| `search` | Words matching a wildcard sign pattern (`*` = one sign) | `-o/--output --json` | `aegean search lineara "KU-*-RO"` |
| `query` | Compound query engine (AND/OR/NOT) with explicit word views and count units | `--where --output-kind --view --count-unit --statuses --fields -o/--output --limit` | `aegean query lineara --where "site-is=Zakros"` |
| `stats` | Word or sign frequency table | `--view --count-unit --statuses --details --signs --top -o/--output` | `aegean stats lineara --signs --top 5` |
| `dispersion` | Item dispersion across documents (Gries' DP) | `--signs --top --min-frequency -o/--output` | `aegean dispersion lineara KU-RO` |
| `keyness` | Characteristic vocabulary vs rest or `--reference` (`G2` + log-ratio) | `--reference --site/... --signs --top --min-target -o/--output` | `aegean keyness lineara --site Zakros` |
| `balance` | Accounting reconciliation (`KU-RO` / `TO-SO` vs listed items) | `--strict -o/--output --json` | `aegean balance lineara HT13` |
| `cite` | Cite a corpus or filtered subset | `--style --site/... --json` | `aegean cite lineara --site Zakros --style bibtex` |
| `export` | Export to JSON / CSV / Parquet / EpiDoc / SQLite / Workbench / RDF (Turtle, JSON-LD) | `-f/--format -o/--output --level --base-uri --site/...` | `aegean export lineara -f csv -o lineara.csv` |
| `combine` | Merge multiple corpora into one `.json` or `.db` | `-o/--output --on-conflict --json` | `aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db` |
| `import` | Import plain text (`.txt` / folder / `.csv`), Workbench JSON, or token-carrier EpiDoc TEI | `-o/--output --script --split --token-view all\|words --id --glob --text-col --id-col --encoding --workbench --epidoc --json` | `aegean import john.txt -o john.json --script nt` |
| `geo` | Find-site coordinates or `--word` attestation map; GeoJSON via `-o` (`.json`/`.geojson`) | `--word --level --site --period --scribe --support -o/--output --json` | `aegean geo lineara --word KU-RO` |
| `sign` | Look up one sign: glyph, codepoint, phonetic value | `--json` | `aegean sign lineara KU --json` |
| `bridge` | Read a Linear B or Cypriot syllabic word as Greek | `--json` | `aegean bridge linearb po-me` |
| `cache` | Inspect or `--clear` the opt-in analysis cache | `--clear --json` | `aegean cache` |
| `plot` | Write one figure to disk (`[viz]` extra) | `-o/--output --signs --top --word --meter --scope --bin-width --min-count --dpi …` | `aegean plot findspots lineara -o sites.png` |
| `workbench` | Serve `workbench-app-v2.1.0` locally (multi-script `--corpus` with automatic `?script=` and self-hosted Noto Sans Aegean fonts) | `-p/--port --auto-port --no-browser --force --fetch-images --corpus --site --period --scribe --support -m/--module --doc --damos --state --dir` | `aegean workbench --corpus damos --state workspace.json` |

### Verified examples

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

Python equivalent:

```python
import aegean
c = aegean.load("lineara")
len(c)                  # 1721
c.provenance.license    # 'Apache-2.0 (corpus JSON); …'
```

```bash
aegean search lineara "KU-*-RO"
# 'KU-*-RO': 1 word(s)   →   KU-MA-RO  (count 1)

aegean stats lineara --signs --top 5
# KU 307 · KA 284 · *301 274 · SI 240 · A 202

aegean dispersion lineara --top 3
# KU-RO  freq 37  range 34/559  DP 0.850 DPnorm 0.851
# KI-RO  freq 16  range 12/559  DP 0.938 DPnorm 0.938

aegean keyness lineara --site Zakros --top 3
# *28B-NU-MA-RE  3/132 vs 0/1249  G2 14.15  log-ratio +6.05  p 0.00017

aegean balance lineara HT13
# HT13  KU-RO  stated 130.5  computed 131.0  diff 0.5  balances NO

aegean cite lineara --site "Haghia Triada"
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil… [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]

aegean sign lineara KU --json
# {"label":"KU","glyph":"𐙂","codepoint":"U+10642","phonetic":"ku","attrs":{…}}

aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)
```

Save outputs directly with `-o FILE` (format by extension; combines with `--json`):

```bash
aegean stats lineara --top 3 -o counts.csv        # item,count
aegean keyness lineara --site Zakros -o key.json  # JSON result set
aegean dispersion lineara --top 5 -o dp.txt       # tab-separated rows
```

Word stats default to `--view surface` and `--count-unit token`. `--view normalized`
applies NFC, lowercasing, and final-sigma folding while preserving diacritics;
`lemma` uses existing lemma annotations and reports missing lemmas without
running an analyzer. `--count-unit document` counts documents per key.
`--statuses certain,unclear,restored,lost` filters editorial readings. These
options and `--details` cannot combine with `--signs`. Default `stats --json`
returns a list; passing `--details` or a non-default word option returns
`{frequencies, metadata, citation}`.

```bash
aegean stats nt --view lemma --count-unit document --details --json
```

### `query` — queryable fields

Combine repeatable `--where field=value` rows (AND default; prefix `or:` to OR,
`!` to negate). List fields via `aegean query CORPUS --fields`. `--limit` caps
tables and JSON lists (`--limit 0` = all) while keeping untruncated totals in
`matched`.

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "or:word-prefix=KU" \
       --output-kind words --json
aegean query lineara --where "site-is=Zakros" -o zakros.json   # save matched inscriptions
aegean stats zakros.json --top 3
```

In Python: `QueryResults.to_corpus(source)`. Word output defaults to document
frequency (`--count-unit token` for token frequency); `--view surface|normalized|lemma`
uses the same lexical keys as `stats`, while default `--view legacy` keeps
case-insensitive predicates and separate surface keys.

```bash
aegean query nt --view lemma --count-unit token --where "word-prefix=ἀγαπ" --output-kind words --json
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

### `export` — formats

```bash
aegean export lineara -f csv -o lineara.csv       # → "wrote 1721 documents to lineara.csv (csv)"
aegean export greek   -f epidoc -o greek.xml      # EpiDoc TEI XML
aegean export lineara -f sqlite -o lineara.db     # same DB as `aegean db build`
aegean export lineara -f workbench -o wb.json     # Linear A Workbench JSON
```

| `--format` | Output | Dependency |
|---|---|---|
| `json` | Lossless, round-trippable corpus | core |
| `csv` | One row per document / token / word (`--level`) | core |
| `parquet` | Columnar equivalent of CSV | `[parquet]` extra |
| `epidoc` | EpiDoc TEI XML (directory, one file per document) | core |
| `sqlite` | Queryable DB with FTS5 | core |
| `workbench` | Linear A Workbench JSON (text/surface round-trip; statuses, annotations, and typed forms are lossy) | core |
| `ttl` | RDF Turtle (export only; `--base-uri` for minted subjects) | core |
| `jsonld` | RDF JSON-LD (export only; same graph as `ttl`) | core |

`--level token` (CSV/Parquet) emits one row per token and expands per-token
annotations (lemma, morph, Strong's, gloss) into columns.

### Interoperability bundles

```bash
aegean greek interop export treebank.conllu --target spacy -o treebank.spacy.json
aegean greek interop report treebank.spacy.json
aegean greek interop import treebank.spacy.json -o treebank-restored.conllu
```

Requires `[cli,interop]` (or `[cli]` plus a specific adapter extra). Produces
pyaegean's portable JSON bundle (projection + SHA-256 sidecar + loss report),
not a framework binary serializer.

### `combine` — merge corpora

`combine SRC... -o out.json|.db` merges two or more corpus specifiers and lists
every source in provenance:

```bash
aegean combine lineara linearb -o aegean.json
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db
```

| `--on-conflict` | Duplicate id behavior |
|---|---|
| `error` (default) | Exit `1` without writing |
| `first` | Keep the first source's document |
| `last` | Keep the last source's document |
| `suffix` | Keep both, appending `#2`, `#3`, … to later ids |

Python: `aegean.combine([c1, c2], dedupe="error")`,
`Corpus.merge(*others, dedupe="first")`, `Corpus.subset(ids)`.

### `import` — import local text

`import SRC -o out.json|.db` converts `.txt`, directories, or `.csv` into a
corpus. Default `--token-view all` preserves decoded source text, whitespace,
and aligned tokens; `--token-view words` selects the legacy lossy word-only
import (plain text/CSV only).

```bash
aegean import john.txt -o john.json --script nt   # → wrote 1 document(s) to john.json
aegean stats john.json --top 3                    # ἦν 4 · λόγος 3 · ὁ 3
```

| Input | Command | Notes |
|---|---|---|
| One `.txt` | `aegean import john.txt -o john.json --script nt` | id = file stem (override with `--id`) |
| Directory | `aegean import poems/ -o poems.db --glob "*.txt"` | ids = file stems (`#2` on collision) |
| `.csv` | `aegean import rows.csv -o rows.json --text-col line --id-col id` | one document per row |

`--split` accepts `whole` (default), `paragraph`, or `line` (multi-block ids
`<base>:1`, `<base>:2`, …). `--encoding` defaults to `utf-8-sig`. Raw `.txt`
files must go through `import` before other commands accept them. Python:
`aegean.io.from_text`, `from_text_file`, `from_text_dir`, `from_csv`
(`token_view="all"|"words"`, `script_id=`, `split=`, `meta_cols=`).

### `plot` — figure kinds (`[viz]` extra)

```bash
pip install "pyaegean[viz]"
aegean plot keyness lineara --site Zakros -o zakros.png
aegean plot scansion "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ" -o scan.svg --meter hexameter
```

| `KIND` | Figure | Relevant flags |
|---|---|---|
| `freq` | Top-N sign or word frequencies | `--signs --top` |
| `dispersion` | DP scatter (annotate top N) | `--signs --top` |
| `keyness` | Keyness bars (subset vs rest or `--reference`) | `--reference --site/... --signs --top` |
| `network` | Co-occurrence network | `--word` (ego network) `--min-count` |
| `balance` | Accounting reconciliation chart | — |
| `scansion` | Metrical scansion grid for one Greek line | `--meter` (second arg is the line; `-` = stdin) |
| `findspots` | Find-site map | `--site/...` |
| `timeline` | Date histogram | `--bin-width` |
| `signnet` | Sign/word co-occurrence network | `--scope --min-count` |

`-o/--output` accepts `.png`, `.svg`, or `.pdf`; `--dpi` sets PNG resolution
(default `150`).

---

## Research bundles — `aegean bundle …`

Deterministic, SHA-256-verified `.zip` research archives
(`aegean-research-bundle/1`) packaging corpora (or NC-safe retrieval pointers),
citations, workbench workspace backups, review CSVs (auto-bundling editable
`.companion.json` sidecars), and analysis receipts. Full details:
[CLI: Corpora, Library, Analysis & Data](CLI-Corpora#research-bundles--aegean-bundle-).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `create` | Build a deterministic `.zip` research bundle | `-c/--corpus --dataset --title --description --site --period --state -r/--review --receipt --embed-corpus auto\|always\|never --json` | `aegean bundle create study.zip -c lineara --state ws.json -r review.csv` |
| `inspect` | Display manifest metadata, corpus mode, license notes, and member hashes | `--json` | `aegean bundle inspect study.zip` |
| `verify` | Check archive safety and SHA-256 checksums for all members (exits `1` on failure) | `--json` | `aegean bundle verify study.zip` |
| `extract` | Verify and unpack bundle files safely into a directory | `--json` | `aegean bundle extract study.zip ./unpacked` |
| `hydrate` | Verify, unpack, and reconstruct corpus (including pointer corpora with `--fetch`) | `--fetch --json` | `aegean bundle hydrate study.zip ./hydrated --fetch` |

`--embed-corpus auto` (default) embeds open corpora and stores a
`CorpusReference` pointer for CC BY-NC* or restricted datasets (`damos`) so
archives stay redistributable (`redistributable=yes`); `always` embeds privately
(`redistributable=no`); `never` always stores a pointer.

---

## Review annotations — `aegean review …`

```bash
aegean review export corpus.json --selection all -o review.csv
aegean review export corpus.json --selection flagged --layout editable -o flagged.csv
aegean review export corpus.json --selection unverified --field pos --field morph -o grammar.csv
aegean review export corpus.json --selection sample --sample-size 40 --seed 17 -o sample.csv
aegean review export corpus.json --annotate --neural --with-confidence --confidence-domain literary \
    --layout editable --priority calibrated-risk --budget 50 -o queue.csv

# Review interactively in the terminal (or in a spreadsheet):
aegean tui --review queue.csv --corpus analysis.json
aegean tui --review alice.csv --review bob.csv --corpus analysis.json

# Merge reviewer sheets and apply verified decisions back:
aegean review merge alice.csv bob.csv -c analysis.json -o merged.csv --on-conflict report
aegean review apply analysis.json merged.csv -o reviewed.json --reviewer "Reviewer"
```

- **Interactive TUI review (`ReviewScreen`, key `r`):** launch with
  `aegean tui --review a.csv [--review b.csv] --corpus <id>`. Keys: `a` accept ·
  `e` edit fields · `1`/`2`/`3` pick conflict option · `d` defer · `x` reject ·
  `n`/`p` next/prev unresolved · `f` cycle filter (`all`/`unresolved`/`conflicts`/`flagged`) ·
  `s` save CSV atomically.
- **Export options:** `--selection all|flagged|unverified|sample`,
  `--layout full|editable` (editable moves immutable snapshot columns to a
  SHA-256-bound `.companion.json` sidecar auto-loaded on merge/apply/TUI),
  `--priority calibrated-risk --budget N`, repeatable `--field`
  (`lemma`, `pos`, `morph`, `head`, `deprel`), `--annotate`,
  `--annotated-output PATH`.
- **Field actions:** `decision_*` accepts `accept`, `correct` (with nonempty
  changed `correct_*`), `defer`, `reject`, or blank (correction-only legacy
  mode). Verification is per field, stored in `Token.annotations` with
  `<field>__pred` snapshots and `review_history`.
- **Snapshot integrity:** Merge and apply against the saved annotated corpus
  when export used `--annotate`; changed source tokens, form state, or analysis
  generations fail instead of applying stale edits. Python equivalent:
  `io.to_review_table(corpus, path, selection="all")`.

---

## Greek NLP — `aegean greek …`

Zero-dependency stages run offline on install; heavier backends activate via
flags below. Every `TEXT` argument accepts `-` for stdin; every data-producing
command accepts `--json`. Full prose: [Greek NLP](Greek-NLP).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `normalize` | Unicode-normalize; `--lenient` repairs OCR/Beta Code | `--form --lenient` | `aegean greek normalize "λόγoς" --lenient` |
| `betacode` | Beta Code → polytonic Greek (`--reverse` for reverse) | `--reverse` | `aegean greek betacode "mh=nin"` |
| `strip` | Strip all diacritics | — | `aegean greek strip "μῆνιν"` |
| `tokenize` | Words + punctuation, or named-policy sentences | `--sentences --sentence-policy {default\|prose\|verse\|inscription\|papyrus} --rich --json` | `aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος." --sentences --sentence-policy prose` |
| `syllabify` | Split word(s) into syllables | `--json` | `aegean greek syllabify εἰσφέρω` |
| `accent` | Accent type, position, classification | `--json` | `aegean greek accent λόγος` |
| `accentuate` | Predict accent from Greek accentuation rules (flags dichrona) | `--recessive/--persistent --lemma --json` | `aegean greek accentuate λυε --recessive` |
| `sandhi` | Expand crasis / elision / movable-ν | `--json` | `aegean greek sandhi κἀγώ` |
| `quantities` | Per-syllable metrical quantity | `--json` | `aegean greek quantities πατρός` |
| `scan` | Metrical scansion against a fixed template | `--meter --json` | `aegean greek scan "…" --meter hexameter` |
| `ipa` | Reconstructed IPA pronunciation | `--period` | `aegean greek ipa "λόγος" --period koine` |
| `profile` | Observable text features (script, polytonic, Beta Code, editorial marks) | `--json` | `aegean greek profile "μῆνιν ἄειδε θεά"` |
| `annotation-profiles list` / `show` | Inspect immutable annotation conventions and descriptive domain scopes | `--json` | `aegean greek annotation-profiles show pyaegean-canonical-v1 --json` |
| `tag` | POS-tag (UD coarse tags) | `--treebank --tagger --neural --neural-variant --json` | `aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."` |
| `lemmatize` | Lemmatize every word | `--treebank --lemmatizer --neural-lemmatizer --neural --neural-variant --json` | `aegean greek lemmatize "μῆνιν ἄειδε θεά"` |
| `morph` | Candidate morphological parses | `--treebank --json` | `aegean greek morph λόγον` |
| `inflect` | Inflection synthesis (attested form(s) of a lemma from AGDT) | `--case --number --gender --tense --voice --mood --person --pos --paradigm --json` | `aegean greek inflect λόγος --case gen --number sg` |
| `parse` | Dependency-parse a sentence | `--neural --neural-variant --parser --json` | `aegean greek parse "…" --neural` |
| `gloss` | Gloss from a registry dictionary (`lsj` default) | `--dict/-d --full --json` | `aegean greek gloss μῆνις --dict cunliffe` |
| `lexica` | List available dictionaries (hosted + deep-link) | `--json` | `aegean greek lexica` |
| `lexicon-link` | Logeion / Perseus deep-link for a word | `--service --no-lemmatize --json` | `aegean greek lexicon-link μήνιδος` |
| `usage` | Dialect + register tags extracted from LSJ | `--json` | `aegean greek usage μῆνις` |
| `rarity` | Vocabulary rarity vs a reference corpus | `--corpus --top --treebank --json` | `aegean greek rarity "μῆνιν ἄειδε θεά" --corpus nt` |
| `missing-forms` | Word forms unresolved by active lemmatizer, ranked by frequency | `--limit --treebank --tagger --lemmatizer --neural-lemmatizer --neural --neural-variant --json` | `aegean greek missing-forms mytext.json` |
| `pipeline` | Single-call pipeline with per-token records and sentence policy | `--parse --parser --treebank --tagger --lemmatizer --neural-lemmatizer --neural --neural-variant --confidence --confidence-domain --confidence-policy --partial --windowed --sentence-policy {default\|prose\|verse\|inscription\|papyrus} -o/--output --json` | `aegean greek pipeline "ἐν ἀρχῇ" --sentence-policy prose --json` |
| `stream [INPUT]` | Neural JSONL token arrays → ordered JSONL `SentenceAnalysis`; `-` reads stdin | `--batch-size N --long-input {strict\|partial\|windowed} --partial --windowed --confidence --confidence-domain --confidence-policy --json` | `printf '%s\n' '["μῆνιν","ἄειδε"]' \| aegean greek stream - --batch-size 2` |
| `explain` | Plain-language lemma evidence classes per token | `--treebank --tagger --lemmatizer --neural-lemmatizer --neural --neural-variant --confidence -o/--output --json` | `aegean greek explain "ἐν ἀρχῇ ἦν ὁ λόγος."` |
| `interop export` / `import` / `report` | CoNLL-U ↔ portable JSON bundle (projection + SHA-256 sidecar + loss report) | `--target {conllu\|spacy\|stanza\|cltk}` `-o/--output` (`export`/`import`); `--json` | `aegean greek interop export treebank.conllu --target spacy -o treebank.spacy.json` |
| `conllu inspect` / `export` | Inspect complete CoNLL-U structure or copy bytes atomically | `--strict --json -o/--output` | `aegean greek conllu inspect treebank.conllu --json` |
| `work` | Fetch a Greek work (Perseus / First1KGreek); `all AUTHOR` bulk-fetches | `--ref --source --edition --limit --dry-run --yes -o --json` | `aegean greek work tlg0012.tlg001 --ref 1.1-1.50` · `aegean greek work all homer` |
| `works` | List 25 curated works; `--downloaded` lists cache; `--remove*` deletes cached works | `--downloaded --remove --remove-author --remove-all --json` | `aegean greek works --remove tlg0012.tlg001` |
| `catalog` | Search the 1,778-work offline discovery index | `--author/-a --title/-t --source --limit/-n -o/--output --json` | `aegean greek catalog --author plato` |
| `eval` | Reproduce official benchmarks (`ud` `proiel` `nt` `papygreek` `verse` `dbbe` `tagger` `lemmatizer` `parser`) | `--fold --split --track --layer --bootstrap --drift --by-genre --batch-size --neural --tagger --lemmatizer --neural-lemmatizer -o/--output --json` | `aegean greek eval papygreek` |

`greek profile TEXT` reports observable text features. `annotation-profiles`
inspects immutable output conventions and descriptive domain scopes without
altering model predictions. Receipt schema 4 binds output profile, documentary
post-processing identity, and runtime-variant evidence (schemas 1–3 remain
readable).

`tokenize --sentences` defaults to `default`; `--sentence-policy` selects
`prose`, `verse`, `inscription`, or `papyrus`. `--rich` (with `--sentences`)
reports character spans, `policy_id`, and provenance (`--json --rich` emits
schema 1). `pipeline` accepts `--sentence-policy`, `--confidence`,
`--confidence-domain`, and `--confidence-policy`. `explain --confidence` renders
the legacy aggregate note.

### Offline zero-dependency stages

```bash
aegean greek betacode "mh=nin a)/eide qea/"      # μῆνιν ἄειδε θεά
aegean greek betacode "μῆνιν" --reverse          # mh=nin
aegean greek strip "μῆνιν"                       # μηνιν
aegean greek syllabify εἰσφέρω                   # εἰσφέρω → εἰσ-φέ-ρω
aegean greek accentuate λυε --recessive          # λύε
aegean greek sandhi κἀγώ                         # καί ἐγώ
aegean greek quantities πατρός                   # πατρός → πα:common | τρός:heavy
aegean greek ipa "λόγος" --period koine          # loɣos
aegean greek normalize "λόγoς kai" --lenient     # λόγος kai (warning on stderr)
aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος."      # one token per line
```

Python equivalents:

```python
from aegean import greek
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.betacode_to_unicode("mh=nin")            # 'μῆνιν'
```

### Scansion (`scan`)

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic

aegean greek scan "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα" --meter trimeter
# ×—⏑—|×—⏑—|×—⏑×
# trimeter: metron, metron, metron; caesura: hephthemimeral

aegean greek scan "λόγος"
# aegean: line does not scan as dactylic hexameter (2 syllables): 'λόγος'   [stderr, exit 1]
```

Synizesis is strictly lexical: lines requiring unattested synizesis exit `1`.
Supported `--meter` values:

| name | meter |
|---|---|
| `hexameter` | dactylic hexameter (default) |
| `pentameter` | elegiac pentameter |
| `trimeter` | iambic trimeter |
| `glyconic` · `pherecratean` · `adonean` | Aeolic cola |
| `sapphic_hendecasyllable` | Sapphic eleven-syllable line |
| `alcaic_hendecasyllable` · `alcaic_enneasyllable` · `alcaic_decasyllable` | Alcaic stanza lines |

`scan --json` adds `feet`, `syllables`, `quantities`, `caesura`, `meter`, and
`ambiguous`. Python: `greek.scan_hexameter(line).pattern`.

### Tagging, lemmatizing, parsing, morphology

```bash
echo "μῆνιν ἄειδε θεά" | aegean greek lemmatize -
# μῆνιν   μῆνις
# ἄειδε   ἀείδω
# θεά     θεά

aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."
# ἐν ADP · ἀρχῇ NOUN · ἦν VERB · ὁ DET · λόγος NOUN · . PUNCT

aegean greek morph λόγον
# λόγος [NOUN acc sg masc]   λόγος [NOUN acc sg fem]   λόγος [NOUN nom sg neut]   …

aegean greek pipeline "ἐν ἀρχῇ" --json
# [{"sentence":0,"index":1,"text":"ἐν","upos":"ADP","lemma":"ἐν","lemma_source":"seed","lemma_resolved":true,"lemma_verified":false,"review_recommended":false,…}, …]
```

Unrecognized forms return a fallback marked `(fallback)` (`"known": false` in
JSON).

### Glossing

```bash
aegean bible strongs λόγος                # a word, speech, divine utterance, analogy
aegean bible strongs G3056 --roots        # Strong's entry + recursive root tree
```

`bible strongs` uses the bundled CC0 Dodson lexicon offline (and Extended
Strong's with `--fetch`). `greek gloss` uses the prebuilt LSJ index (~15 MB),
falling back to building from upstream TEI if needed.

### Backend flags (download/build on first use)

Each flag corresponds to a `use_*()` activation in Python:

| flag | activates | first-use cost |
|---|---|---|
| `--treebank` | Perseus AGDT lexicon | shared prebuilt AGDT bundle; source build fallback |
| `--tagger` | generalizing POS tagger | shared prebuilt AGDT bundle; source training fallback |
| `--lemmatizer` | edit-tree lemmatizer | shared prebuilt AGDT bundle; source training fallback |
| `--parser` | pure-Python arc-eager dependency parser | shared prebuilt AGDT bundle; source training fallback |
| `--neural-lemmatizer` | GreTa seq2seq lemmatizer (`[neural]`) | ~232 MB model |
| `--neural` | joint neural tagger/parser/lemmatizer (`[neural]`) | ~173 MB model |
| `--neural-variant LABEL` | Runtime artifact for `--neural` (only `default` currently exists) | no extra download unless a new artifact is released |

```bash
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural
aegean greek parse "ἐν ἀρχῇ ἦν ὁ λόγος" --neural
aegean greek tag "…" --treebank --tagger
```

### Loading Greek literary works

`work` fetches a commit-pinned CC BY-SA TEI text from Perseus or First1KGreek.
`--ref` follows the work's declared citation scheme (`1`, `1.2`, `1.1-1.50` —
verse is `book.line`, Stephanus Plato is `section`, Aristotle is
`chapter.subchapter`, prose is `book.chapter.section`), and invalid refs report
the expected scheme. Use comma lists (`--ref 1.1,1.5`) for siblings or
cross-textpart selections; `greek.citation_scheme(id)` lists levels. `--ref`
also addresses margin milestones outside `<div>`: Stephanus sub-pages (`17a`),
Bekker lines (`1447a10` = span to the next marked line), and whole Bekker
page-columns (`1447a`; whole page as comma list `1447a,1447b`), singly or as
comma lists (`17a,17b`, not hyphen ranges). `--source` selects
`auto`/`perseus`/`first1k`; `--edition` picks a specific TEI file. Full guide:
[Greek Works and Books](Greek-Works-and-Books).

```bash
aegean greek works                                # 25 curated highlights (table below)
aegean greek catalog --author plato               # search the 1,778-work offline index
aegean greek work tlg0012.tlg001                  # Iliad, one doc per book
aegean greek work tlg0012.tlg001 --ref 1.1-1.50   # book 1, lines 1–50
aegean greek work tlg0012.tlg001 -o iliad.json    # save as corpus JSON
aegean bible read John 1:1-18                     # Greek NT (John 1 bundled offline)
```

Curated 25 highlights (`aegean greek works`):

| id | author | title |
|---|---|---|
| `tlg0012.tlg001` | Homer | Iliad |
| `tlg0012.tlg002` | Homer | Odyssey |
| `tlg0020.tlg001` | Hesiod | Theogony |
| `tlg0020.tlg002` | Hesiod | Works and Days |
| `tlg0085.tlg004` | Aeschylus | Seven Against Thebes |
| `tlg0085.tlg005` | Aeschylus | Agamemnon |
| `tlg0085.tlg006` | Aeschylus | Libation Bearers |
| `tlg0011.tlg001` | Sophocles | Trachiniae |
| `tlg0011.tlg002` | Sophocles | Antigone |
| `tlg0011.tlg003` | Sophocles | Ajax |
| `tlg0011.tlg004` | Sophocles | Oedipus Tyrannus |
| `tlg0006.tlg001` | Euripides | Cyclops |
| `tlg0006.tlg002` | Euripides | Alcestis |
| `tlg0006.tlg003` | Euripides | Medea |
| `tlg0019.tlg002` | Aristophanes | Knights |
| `tlg0019.tlg003` | Aristophanes | Clouds |
| `tlg0016.tlg001` | Herodotus | Histories |
| `tlg0003.tlg001` | Thucydides | History of the Peloponnesian War |
| `tlg0032.tlg002` | Xenophon | Memorabilia |
| `tlg0032.tlg006` | Xenophon | Anabasis |
| `tlg0059.tlg002` | Plato | Apology |
| `tlg0059.tlg003` | Plato | Crito |
| `tlg0059.tlg004` | Plato | Phaedo |
| `tlg0059.tlg030` | Plato | Republic |
| `tlg0086.tlg010` | Aristotle | Nicomachean Ethics |

### `catalog` — full 1,778-work offline index

Searches all 1,778 works (768 `perseus` + 1,010 `first1k`) offline. Positional
`QUERY` matches id, author, English title, or Greek title; `--author/-a`,
`--title/-t`, and `--source perseus|first1k` combine with AND. `--limit/-n` caps
tables, `--json`, and `-o` (`0` = all; JSON retains the total in `matched`).

```bash
aegean greek catalog --author plato --limit 8
aegean greek catalog herodotus --json
aegean greek catalog --author aristophanes --source perseus -o aristophanes.csv
```

Python: `greek.catalog(query=None, *, author=None, title=None, source=None)` and
`greek.popular_works()`.

The 27 NT books (`aegean bible books nt` / `bible.nt_books()`) and accepted
names for `aegean bible read` and `bible.load_nt()`:

| book | accepted names | book | accepted names |
|---|---|---|---|
| Matt | matthew, matt, mt | 1Tim | 1timothy, 1tim, 1ti |
| Mark | mark, mk, mrk | 2Tim | 2timothy, 2tim, 2ti |
| Luke | luke, lk, luk | Titus | titus, tit |
| John | john, jn, jhn | Phlm | philemon, phlm, phm |
| Acts | acts, act | Heb | hebrews, heb |
| Rom | romans, rom, rm | Jas | james, jas, jms |
| 1Cor | 1corinthians, 1cor, 1co | 1Pet | 1peter, 1pet, 1pe |
| 2Cor | 2corinthians, 2cor, 2co | 2Pet | 2peter, 2pet, 2pe |
| Gal | galatians, gal, ga | 1John | 1john, 1jn, 1jhn |
| Eph | ephesians, eph | 2John | 2john, 2jn, 2jhn |
| Phil | philippians, phil, php | 3John | 3john, 3jn, 3jhn |
| Col | colossians, col | Jude | jude, jud |
| 1Thess | 1thessalonians, 1thess, 1th | Rev | revelation, rev, rv, apocalypse |
| 2Thess | 2thessalonians, 2thess, 2th | | |

Python equivalents:

```python
from aegean import greek
from aegean.greek import bible

bible.load_nt("John", ref="1.1-18")
bible.nt_books()
greek.load_work("tlg0012.tlg001", ref="1.1-1.50")
```

### Lossless CoNLL-U files

`conllu inspect` reports sentence, comment, syntactic-word, MWT-range,
empty-node, and opaque-row counts alongside the syntactic projection policy and
original-ID mapping. `conllu export` copies UTF-8 source bytes atomically
without running any model.

```bash
aegean greek conllu inspect treebank.conllu --strict --json
aegean greek conllu export treebank.conllu -o checked-copy.conllu --strict
```

### Reproducing published benchmarks (`eval`)

`aegean greek eval TARGET` evaluates fetched gold folds (`ud`, `proiel`, `nt`,
`papygreek`, `verse`, `dbbe`, `tagger`, `lemmatizer`, `parser`). For `ud`,
`--fold` selects `perseus` or `proiel` and `--split` selects `dev` or `test`
(legacy `--treebank` warns and maps to `--fold`). `--drift` reports POS and
lemma confusion breakdowns; `-o/--output` saves results.

```bash
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval proiel --drift
```

Published numbers and protocols live on [Benchmarks](Benchmarks),
[Greek NLP](Greek-NLP), and [Limitations](Limitations).

---

## Biblical & Koine Greek — `aegean bible …`

9 Greek NT editions, 13 early 2nd–5th c. CE manuscripts, Extended Strong's +
root trees, 55-book Swete Septuagint (LXX), and 86 Greek patristic commentaries
across 10 Church Fathers and traditions. Full reference:
[CLI: Biblical & Koine Greek](CLI-Bible).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `read` | Read NT or LXX passage (LXX auto-detected; plain, interlinear, or `-o` export) | `--ref -e/--edition --lxx -i/--interlinear -o/--output --offline --json` | `aegean bible read John 1:1-5 -i` · `aegean bible read Gen 1:1-5` |
| `compare` | Word-level variant diff across up to 9 NT editions (`nestle1904`, `sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`) | `-e/--editions --offline --json` | `aegean bible compare John 1:18` |
| `witnesses` | Compare 13 early NT manuscripts (*nomina sacra* expanded by default) | `-s/--sigla --hand -d/--diplomatic --no-expand --offline --json` | `aegean bible witnesses John 18:37 -s P52,01,03` |
| `strongs` | Strong's / Extended Strong's lookup, search, or root tree | `-r/--roots -s/--search --fetch --offline -n/--limit/--top --json` | `aegean bible strongs G3056 --roots` |
| `word-study` | Combined Strong's + root + morphology + NT concordance report | `-b/--book -n/--limit/--top --offline --json` | `aegean bible word-study ἀγάπη` |
| `search` | NT concordance (`--by lemma\|text\|strongs\|morph\|gloss`) or LXX (auto-detected / `--lxx`) | `--by -b/--book --section -e/--edition --lxx -n/--limit/--top --offline --json` | `aegean bible search φῶς --lxx --offline` |
| `commentary` | List, read (`read TARGET` or TLG/`PG*` ID), or search (`search TARGET TERM`) 86 patristic commentaries | `-k/--kind --ref -n/--limit/--top --json` | `aegean bible commentary read Matt` · `aegean bible commentary search PG073 λόγος` |
| `books` | Offline catalogues: `nt`, `lxx`, `editions` (9), `witnesses` (13), `all` | `--section --json` | `aegean bible books editions` |
| `psalm` | Masoretic (`mt`) ↔ Septuagint (`lxx`) Psalm numbering | `--from --json` | `aegean bible psalm 23 --from mt` |
| `status` | Show installed vs available Biblical bundles | `--json` | `aegean bible status` |
| `install` | Download Biblical assets (`all` installs the full `biblical` pack) | `--force --json` | `aegean bible install all` |

---

## Analysis — `aegean analyze …`

Surface analyses over syllabic and alphabetic corpora. Method notes:
[Analysis](Analysis).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `distance` | Weighted phonetic distance in `[0, 1]` (`0` = identical) | `--json` | `aegean analyze distance KU-RO KI-RO` |
| `align` | Per-position phonetic alignment | `--json` | `aegean analyze align KU-RO KI-RO` |
| `compare` | Compare two words across scripts by sound | `--script-a --script-b --fold-aspiration --json` | `aegean analyze compare po-me ποιμήν` |
| `nearest` | Rank a corpus's words by phonetic closeness to `WORD` | `--script-a --fold-aspiration --top -o/--output --json` | `aegean analyze nearest qa-si-re-u greek` |
| `assoc` | Document-level association: χ², G², Fisher, PMI | `-o/--output --json` | `aegean analyze assoc lineara KU-RO KI-RO` |
| `cooccur` | Words co-occurring in documents with `WORD`, ranked | `--top -o/--output --json` | `aegean analyze cooccur lineara KU-RO` |
| `clusters` | Stems with productive-suffix derivations | `--min-size --top -o/--output --json` | `aegean analyze clusters lineara` |
| `structure` | Heuristic document categories (accounting/libation/…) | `--site --period --scribe --support -o/--output --json` | `aegean analyze structure lineara` |
| `hands` | Scribal-hand profiles and keyness (e.g. DAMOS) | `--hand --top --min-docs --signs --site --period --scribe --support -o/--output --json` | `aegean analyze hands damos` |

`assoc`, `cooccur`, `clusters`, `structure`, `hands`, and `nearest` accept
`-o FILE` (`.json`, `.csv`, `.txt`) and `--top 0`. Full examples:
[CLI: Corpora, Library, Analysis & Data](CLI-Corpora).

---

## Data — `aegean data …`

Manages the SHA-256-verified local download store. Valid cached assets are
reused without expiry; a changed pin or `--force` fetches a replacement, and
`remove` deletes entries.

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `list` | Fetchable datasets with downloaded state and on-disk size (including kept `--version` pins) | `--json` | `aegean data list` |
| `fetch` | Download into the store (idempotent); `--version v1` fetches a historical pin | `--force --version` | `aegean data fetch grc-joint` |
| `remove` | Delete cached dataset(s); `--version v1` removes only one historical pin | `--all --version --json` | `aegean data remove nt-corpus` |
| `versions` | Reproducibility manifest (version + SHA-256) | `--json` | `aegean data versions --json > data-versions.json` |
| `store` | Store location and contents | `--json` | `aegean data store` |

`aegean data list` shows the live registry (currently 39 entries). Use
`aegean library packs` to install themed packs (`biblical`, `patristic`,
`aegean`, `epigraphy`, `literary`, `lexica`, `neural`), and see
[Data & Provenance](Data-and-Provenance) for sizes, SHA-256 pins, and licenses.

```bash
aegean data fetch grc-joint                       # pre-fetch before going offline
aegean data remove lineara-images                 # delete one dataset (--all clears all)
aegean data versions --json > data-versions.json  # pin dataset hashes
aegean data store                                 # store path (override: PYAEGEAN_CACHE)
```

Two separate caches exist: the persistent **data store** (`aegean data store`,
`PYAEGEAN_CACHE`; deprecated alias `aegean data cache`) and the opt-in
**analysis cache** (`aegean cache`, `PYAEGEAN_ANALYSIS_CACHE=1`).

---

## SQLite — `aegean db …`

Builds and searches SQLite corpus databases (documents, tokens, FTS5).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `build` | Write a corpus to SQLite | `-o/--output --no-fts` | `aegean db build lineara -o lineara.db` |
| `add` | Upsert another corpus into an existing DB | `-o/--output` | `aegean db add cypriot -o lineara.db` |
| `index` | Build, refresh, or inspect optional exact lexical index (`surface`/`normalized`/`lemma`) | `--status --json` | `aegean db index corpus.db` |
| `search` | Read-only token search (whole-token default; `--substring` for within-token match) | `--limit (0 = all) --view --statuses --substring -o/--output --json` | `aegean db search lineara.db KU-RO` |
| `annotate` | Resumable document-by-document SQLite annotation job | `-o/--output --job-dir --neural --with-dependencies --long-input --resume --json` | `aegean db annotate corpus.db -o annotated.db --job-dir ./job --neural --resume` |
| `job-status` | Inspect checkpoint progress of an annotation job directory | `--json` | `aegean db job-status ./job --json` |

```bash
aegean db build lineara -o lineara.db
aegean db search lineara.db KU-RO --limit 3
aegean db search ddbdp "βασιλέως" --limit 5        # DB-backed corpus id directly
aegean db add cypriot -o lineara.db               # upsert by document id
```

`db search` opens databases read-only, accepts `--limit 0`, and writes `.json`,
`.csv`, or `.txt` via `-o`. Python: `corpus.to_sql(path, append=True)`,
`Corpus.from_sql(path)`, `aegean.db.stream(path)`.

---

## AI — `aegean ai …` (exploratory, key-gated)

All outputs are labeled model hypotheses with grounding provenance, never
citable findings or decipherments. Requires a provider extra (e.g.
`pip install "pyaegean[anthropic]"`) and API key for hosted providers (`local`
uses Ollama/LM Studio/llama.cpp with no key). Without a key, hosted commands
exit `1` without making a network request. See [AI Layer](AI-Layer) and
[Limitations](Limitations).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `providers` | List registered AI providers | `--json` | `aegean ai providers` |
| `translate` | Grounded translation with uncertainty, checking draft, and reported changes | `--script --target --style annotated\|concise --mode --greek-backend --greek-variant --greek-long-input --grounding-failure --glosses/--no-glosses --verify --check-policy --lexical-evidence --dictionary --source-context --source-context-file --max-tokens --provider --model --trace -o/--output --json` | `aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --style concise` |
| `gloss` | Interlinear word-by-word gloss | `--source --provider --model --trace -o/--output --json` | `aegean ai gloss "μῆνιν ἄειδε θεά"` |
| `summarize` | Short grounded passage summary | `--corpus --provider --model --trace -o/--output --json` | `aegean ai summarize "ἐν ἀρχῇ ἦν ὁ λόγος" --corpus nt` |
| `hypotheses` | Exploratory decipherment hypotheses | `--corpus --provider --model --trace -o/--output --json` | `aegean ai hypotheses "A-TA-I-*301-WA-JA" --corpus lineara` |
| `ask` | Answer from supplied grounding | `--corpus --provider --model --trace -o/--output --json` | `aegean ai ask "What is KU-RO?" --corpus lineara` |
| `extract` | Structured JSON extraction | `--fields --instruction --corpus --provider --model -o/--output --json` | `aegean ai extract "OLE S 1" --fields commodity,amount` |
| `eval` | Grounded-generation fidelity evaluation | `--provider --model -o/--output --json` | `aegean ai eval --provider anthropic` |

```bash
aegean ai providers                                      # anthropic / gemini / grok / local / openai / openrouter
aegean ai translate "KU-RO 130" --script lineara         # exploratory (undeciphered)
aegean ai ask "What is KU-RO?" --corpus lineara --trace  # answer + grounding provenance
aegean ai extract "OLE S 1" --fields commodity,amount    # → {"commodity":"OLE","amount":…}
```

- `--provider` accepts `anthropic` (default), `openai`, `grok`, `gemini`,
  `openrouter`, or `local`; `--model` overrides the model name.
- For Greek `translate`, `--mode` defaults to `morphology` (`full` adds
  rarity-gated glosses; `lemma` / `none` select legacy or ungrounded calls).
- `--verify` drafts ungrounded first, then checks against full grounding in a
  second call (`--check-policy clauses` adds clause-level checks;
  `--lexical-evidence contextual` supplies bounded dictionary excerpts; repeat
  `--dictionary ID` to activate hosted lexica).
- `--greek-backend default|baseline|neural` (`--greek-variant`,
  `--greek-long-input strict|partial|windowed`,
  `--grounding-failure best-effort|strict`) controls local analysis ownership
  and failure handling.
- `--style annotated` (default) displays model-reported uncertainties and
  changes; `--style concise` prints counts while keeping details in JSON and
  `--trace`. Structured responses populate `text`, `data`, `raw_response`,
  `format_status`, and (with `--verify`) `draft`, `text_changed`, and
  `change_report_status`.
- `-o FILE` preserves text, provenance, grounding, and the exploratory label on
  disk (Python: `ExploratoryResult.to_dict()` / `to_json()` / `from_dict()`).

```bash
aegean ai ask "What is KU-RO?" --corpus lineara -o answer.json
aegean ai translate "μῆνιν ἄειδε θεά" --verify --style concise --trace -o checked.json
```

---

## MCP server — `aegean-mcp`

Separate console script (`[mcp]` extra) serving **29 read/analysis tools** over
stdio across corpora, library discovery, Greek NLP, and Biblical/Septuagint/Patristic
Greek. Corpora and works are addressed by registry name or catalogue work id
only, never by filesystem path. Full reference: [MCP](MCP).

```bash
pip install "pyaegean[mcp]"
aegean-mcp
```

---

## Quick recipes

```bash
# Keep only Linear A accounts that fail to balance
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json

# Lemmatize a Greek file, one lemma per line
cat chapter.txt | aegean greek lemmatize - --json | jq -r '.[].lemma'

# Pin dataset hashes for a reproducibility appendix
aegean data versions --json > data-versions.json

# Map find-sites and cite the filtered subset
aegean geo lineara --output sites.geojson
aegean cite lineara --site "Zakros" --style bibtex >> paper.bib

# Package a verifiable research bundle
aegean bundle create zakros-study.zip --corpus lineara --site Zakros --state workspace.json

# Save a query subset and run downstream stats
aegean query lineara --where "site-is=Zakros" -o zakros.json
aegean stats zakros.json --top 10 -o zakros-counts.csv

# Build a multi-script SQLite database
aegean combine lineara linearb -o aegean.db
aegean db add cypriot -o aegean.db
```

More workflows appear on [Recipes](Recipes).

---

## Notes and limits

- **`--json` is the scripting contract.** Parse `--json` output with `jq`, not
  formatted terminal tables. `--limit`/`--top` cap JSON arrays (`0` lifts the
  cap); payloads with `matched` retain untruncated totals.
- **Heavy commands fetch on first use.** `--neural`, `greek work`, `greek eval`,
  `gloss`, and hosted corpora cache downloads on first run (with a stderr
  notice) and run offline afterward. Pre-fetch with `aegean library install` or
  `aegean data fetch`.
- **The AI layer is exploratory.** Translations, glosses, and hypotheses for
  undeciphered scripts are labeled model output with grounding, not findings.
  Linear A and Cypro-Minoan remain undeciphered.
- **Meter and accuracy limits.** Lyric meters beyond fixed Aeolic templates are
  out of scope, and trainable backends have measured ceilings documented on
  [Benchmarks](Benchmarks) and [Limitations](Limitations).

For the guided tour with worked outputs, see [CLI](CLI).
