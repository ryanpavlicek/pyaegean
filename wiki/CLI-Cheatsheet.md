# CLI Cheatsheet

This is the dense, one-page index of **every `aegean` command and its key flags**,
each with a copy-pasteable example. It's the lookup card you keep open while you
work; the [CLI](CLI) page is the guided tour that explains each group with prose.
If you've never used a terminal, start with [Getting Started](Getting-Started).

```bash
pip install "pyaegean[cli]"     # adds typer + rich; the core library stays zero-dependency
aegean --help                   # the command map
aegean --version                # pyaegean 0.24.0
```

If you only ran `pip install pyaegean`, the library works but the `aegean` command
isn't installed until you add the `[cli]` extra.

## Conventions that hold everywhere

| Convention | What it does | Example |
|---|---|---|
| **`--json`** | Print one machine-readable JSON document and nothing else, so results pipe into `jq`, files, or programs. Greek stays readable (`ensure_ascii=False`). Combines with `-o/--output`: the file is written (`wrote <path>` on stderr) and the JSON still prints. | `aegean info lineara --json` |
| **`-` reads stdin** | Anywhere a command takes a `TEXT` argument, `-` reads it from standard input, so commands compose. | `echo "μῆνιν" \| aegean greek lemmatize -` |
| **A corpus arg is flexible** | Every corpus argument resolves the same way: a registered id, a **Greek work id** (`tlg0012.tlg001` → fetched & parsed), a path to a saved **`.json` or `.db`** corpus, or `-` for a `Corpus.to_json()` document on stdin. So `aegean stats iliad.json` and `aegean export tlg0012.tlg002 -f csv -o odyssey.csv` work with no Python. | `aegean stats lineara.json` |
| **`--top` / `--limit`** | Interchangeable spellings of the same cap on every command that caps a ranked table or result list, `plot` included. `0` lifts the cap wherever the help says `0 = all` (the one exception is `greek rarity`, whose cap is a plain slice). | `aegean stats lineara --limit 3` |
| **Exit codes** | `0` success · `1` a domain error (one line on stderr, prefixed `aegean:`) · `2` a usage error. | `aegean greek scan "λόγος"` → exit `1` |

Every command and group answers `-h` / `--help`. The bundled, **offline-from-install**
corpora are `lineara`, `linearb`, `cypriot`, `cyprominoan`, `greek`; three more
download to the cache on first use: `damos`, `sigla`, `nt`, `isicily`, `iip`, `iospe`. The same `read_corpus(spec)`
in Python resolves any of those forms: `aegean.read_corpus("iliad.json")`.

---

## At a glance

| Group | Commands |
|---|---|
| **(top level)** | `quickstart` `repl` `tui` `info` `load` `show` `search` `query` `stats` `dispersion` `keyness` `cache` `doctor` `balance` `cite` `export` `combine` `import` `geo` `sign` `bridge` `plot` `workbench` |
| **`greek`** | `normalize` `betacode` `strip` `tokenize` `syllabify` `accent` `accentuate` `sandhi` `quantities` `scan` `ipa` `tag` `lemmatize` `morph` `inflect` `parse` `gloss` `gloss-nt` `usage` `lexica` `lexicon-link` `rarity` `pipeline` `work` `works` `catalog` `nt-books` `eval` |
| **`analyze`** | `distance` `align` `compare` `nearest` `assoc` `cooccur` `clusters` `structure` `hands` |
| **`data`** | `list` `fetch` `remove` `versions` `store` |
| **`db`** | `build` `add` `search` |
| **`geo`** | (top-level command: coordinates / GeoJSON) |
| **`ai`** | `translate` `gloss` `summarize` `hypotheses` `ask` `extract` `eval` `providers` |
| **`workbench`** | (top-level command: serve the web UI) |
| **`aegean-mcp`** | separate console script: serve the tools to AI agents over MCP |

---

## Corpus & analysis (top level)

Every corpus command takes a **corpus** as its first argument (an id, a Greek work id,
a `.json`/`.db` file, or `-`) and accepts `--json`. The analysis commands (`stats`,
`dispersion`, `keyness`, `search`, `balance`) also take **`-o/--output`** to write the
result to a file: `.json` / `.csv` (stdlib, no pandas) / `.txt` by extension, with a
one-line `wrote <path>` confirmation on stderr; `-o` combines with `--json`.

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `quickstart` | The guided first five minutes: 8 steps run live on bundled data, all offline | `--no-run` (print the script, execute nothing) | `aegean quickstart` |
| `repl` | Interactive shell: run commands without the `aegean` prefix (Tab-completion + a history that persists across sessions). Shell-only directives: `use CORPUS` sets a session corpus for corpus-first commands (`use off` clears) · `:examples` prints starter lines · `:help` · `:exit` |— | `aegean repl` |
| `tui` | Full-screen terminal UI (`[tui]` extra, Textual): a corpus browser, the Greek workbench, the data store, a **works library** (`w`, fetch + read Greek works), and a **command console** (`:`, any command); keys `h`/`c`/`g`/`d`/`w`, `:` console, `t` theme, `?` help, `Esc` back, `ctrl+p` palette. See the [TUI](TUI) page | — | `aegean tui` |
| `doctor` | Offline environment check: versions, extras, data store, model bundles, analysis cache; issues print their fix; exit `1` when any is found | `--json -o/--output` | `aegean doctor` |
| `info` | Corpus overview: size, provenance, license, citation | `--json` | `aegean info lineara` |
| `load` | Filter by metadata; list matches or export them | `--site --period --scribe --support -o/--output --limit` | `aegean load lineara --site "Haghia Triada"` |
| `show` | One document: metadata + line-by-line tokens | `--json` | `aegean show lineara HT13` |
| `search` | Words matching a wildcard sign pattern (`*` = one sign) | `-o/--output --json` | `aegean search lineara "KU-*-RO"` |
| `query` | Compound-query engine (AND/OR/NOT predicates) | `--where --output-kind --fields -o/--output --limit` | `aegean query lineara --where "site-is=Zakros"` |
| `stats` | Frequency table of words (or `--signs`) | `--signs --top -o/--output` | `aegean stats lineara --signs --top 5` |
| `dispersion` | How evenly an item spreads (Gries' DP) | `--signs --top --min-frequency -o/--output` | `aegean dispersion lineara KU-RO` |
| `keyness` | Characteristic items vs a reference (G² + log-ratio) | `--reference --site/... --signs --top --min-target -o/--output` | `aegean keyness lineara --site Zakros` |
| `balance` | Accounting reconciliation (KU-RO / TO-SO vs items) | `--strict -o/--output --json` | `aegean balance lineara HT13` |
| `cite` | Cite the corpus, or the exact filtered subset | `--style --site/... --json` | `aegean cite lineara --site Zakros --style bibtex` |
| `export` | Export to JSON / CSV / Parquet / EpiDoc / SQLite / Workbench | `-f/--format -o/--output --level --site/...` | `aegean export lineara -f csv -o lineara.csv` |
| `combine` | Merge several corpora into one and save it | `-o/--output --on-conflict --json` | `aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db` |
| `import` | Import your **own** text (`.txt` / folder / `.csv`), a Workbench export, or EpiDoc TEI | `-o/--output --script --split --id --glob --text-col --id-col --encoding --workbench --epidoc --json` | `aegean import john.txt -o john.json --script nt` |
| `geo` | Find-site coordinates, or `--word`'s per-site map (case-insensitive); GeoJSON with `-o` (`.json`/`.geojson` only) | `--word --level --site --period --scribe --support -o/--output --json` | `aegean geo lineara --word KU-RO` |
| `sign` | Look up one sign: glyph, codepoint, sound value | `--json` | `aegean sign lineara KU --json` |
| `bridge` | Read a deciphered syllabic word as Greek | `--json` | `aegean bridge linearb po-me` |
| `cache` | Inspect (or `--clear`) the opt-in **analysis** cache | `--clear --json` | `aegean cache` |
| `plot` | Draw one figure to a file (`[viz]` extra) | `-o/--output --signs --top --word --meter --dpi …` | `aegean plot keyness lineara --site Zakros -o k.png` |
| `workbench` | Serve the Linear A Research Workbench locally | `-p/--port --no-browser --force --fetch-images` | `aegean workbench` |

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

Same fact in Python (every corpus command has an API equivalent):

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
# 𐝫 552 · 𐄁 468 · 1 310 · KU 307 · KA 284

aegean dispersion lineara --top 3
# KU-RO  freq 37  range 34/559  DP 0.850 DPnorm 0.851
# KI-RO  freq 16  range 12/559  DP 0.938 DPnorm 0.938

aegean keyness lineara --site Zakros --top 3
# *28B-NU-MA-RE  3/132 vs 0/1249  G2 14.15  log-ratio +6.05  p 0.00017
# (or compare two corpora: aegean keyness nt --reference greek)

aegean balance lineara HT13
# HT13  KU-RO  stated 130.5  computed 131.0  diff 0.5  balances NO

aegean cite lineara --site "Haghia Triada"
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil… [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]

aegean sign lineara KU --json
# {"label":"KU","glyph":"𐙂","codepoint":"U+10642","phonetic":"ku","attrs":{…}}

aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)
```

Add `-o FILE` to `stats`, `dispersion`, `keyness`, `search`, or `balance` to write
the result straight to disk. The format follows the extension, a `wrote <path>`
confirmation goes to stderr (stdout stays clean), and adding `--json` prints the
JSON to stdout as well as writing the file:

```bash
aegean stats lineara --top 3 -o counts.csv        # item,count
aegean keyness lineara --site Zakros -o key.json  # full result set, as JSON
aegean dispersion lineara --top 5 -o dp.txt       # tab-separated rows
```

### `query` — queryable fields

Build a query from repeated `--where field=value` rows. Rows **AND** by default;
prefix the field with `or:` to OR a row, or `!` to negate it. List the fields with
`aegean query CORPUS --fields`. `--limit` caps the human table and the `--json`
lists alike (`--limit 0` emits everything); the JSON payload keeps the untruncated
totals in `matched`, so a pipeline never loses count of the full result set.

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "or:word-prefix=KU" \
       --output-kind words --json
```

`query -o out.json` (or `.db`) saves the **matched inscriptions** as a reusable corpus:
a `subset:` provenance note records that it's a slice. (`-o` works on the inscription
output only.) So a query becomes the input to anything else:

```bash
aegean query lineara --where "site-is=Zakros" -o zakros.json
#   → wrote 53 inscriptions to zakros.json
aegean stats zakros.json --top 3            # …then analyse just that subset
```

In Python: `QueryResults.to_corpus(source)`.

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

| `--format` | output | needs |
|---|---|---|
| `json` | lossless, round-trippable corpus | core |
| `csv` | one row per document / token / word (`--level`) | core |
| `parquet` | same, columnar | `[parquet]` extra |
| `epidoc` | EpiDoc TEI XML | core |
| `sqlite` | queryable DB with FTS5 | core |
| `workbench` | Linear A Workbench JSON (round-trips via `import --workbench`) | core |

`--level token` (csv/parquet) emits one row per token and spreads per-token
annotations (the Greek NT's lemma / morph / Strong's / gloss) into columns.

### `combine` — merge corpora into one

`combine SRC... -o out.json|.db` stitches two or more corpora into a single saved
corpus. Each source resolves like any corpus argument (id, work id, `.json`/`.db` file,
or `-`), so you can fold fetched Greek works and your own files together. The merged
provenance names every source.

```bash
aegean combine lineara linearb -o aegean.json
#   → wrote 1739 documents to aegean.json (merged 2 sources)

# all of Homer in one queryable database, no Python:
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db
#   → wrote … documents to homer.db (merged 2 sources)
```

`--on-conflict` decides what happens when an id appears in more than one source:

| `--on-conflict` | duplicate id behaviour |
|---|---|
| `error` (default) | stop with a clear message: nothing is written |
| `first` | keep the first source's document |
| `last` | keep the last source's document |
| `suffix` | keep both, suffixing the later id so it stays unique |

In Python: `aegean.combine([c1, c2], dedupe="error")`, `Corpus.merge(*others,
dedupe="first")`, and `Corpus.subset(ids)` for the inverse (pull a named slice out).

### `import` — your own text → a corpus

`import SRC -o out.json|.db` turns a plain-text file, a folder of text files, or a CSV
into a real corpus you can then `stats`/`search`/`query`/`export`. Greek/Koine text
goes through the Greek tokenizer (punctuation stripped); other `--script`s split on
whitespace. End to end:

```bash
aegean import john.txt -o john.json --script nt   # → wrote 1 document(s) to john.json
aegean stats john.json --top 3                    # ἦν 4 · λόγος 3 · ὁ 3
```

| input | command | notes |
|---|---|---|
| one `.txt` | `aegean import john.txt -o john.json --script nt` | id = file stem (override with `--id`) |
| a folder | `aegean import poems/ -o poems.db --glob "*.txt"` | one corpus from many files; ids = stems (`#2` on clash) |
| a `.csv` | `aegean import rows.csv -o rows.json --text-col line --id-col id` | one document per row |

`--split` controls how a text becomes documents: `whole` (default, one doc),
`paragraph` (blank-line blocks), or `line` (one per line); multi-block ids are
numbered `<base>:1`, `<base>:2`, …. `--encoding` (default `utf-8`) reads non-UTF-8
files. `import` is the **only** door for plain text: `read_corpus` and every corpus
argument still load only `.json`/`.db` (and work ids), so a bare `.txt` fed to a
command exits `1` and tells you to import it first.

In Python: `aegean.io.from_text(s)`, `from_text_file(path)`, `from_text_dir(path)`,
`from_csv(path, text_col=…, id_col=…, meta_cols=…)`: each takes `script_id=` and
(for text) `split=`.

### `plot` — figure kinds (`[viz]` extra)

```bash
pip install "pyaegean[viz]"
aegean plot keyness lineara --site Zakros -o zakros.png
aegean plot scansion "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ" -o scan.svg --meter hexameter
```

| `KIND` | what it draws | relevant flags |
|---|---|---|
| `freq` | top-N sign or word frequencies | `--signs --top` |
| `dispersion` | DP scatter (annotate top N) | `--signs --top` |
| `keyness` | keyness bars (subset vs rest, or `--reference`) | `--reference --site/... --signs --top` |
| `network` | co-occurrence network | `--word` (ego network) `--min-count` |
| `balance` | accounting reconciliation chart |— |
| `scansion` | metrical scansion grid for one Greek line | `--meter` (second arg is the line; `-` = stdin) |

`--output -o` (required) takes `.png` / `.svg` / `.pdf`; `--dpi` sets raster
resolution for PNG (default 150).

---

## Greek NLP — `aegean greek …`

The full Ancient Greek pipeline from the shell. Zero-dependency stages run the
moment you install; the heavier backends are opt-in flags (below). Every text
argument accepts `-` for stdin, and every data-producing command takes `--json`
(the plain text transforms `normalize`/`betacode`/`strip`/`ipa` just print the
converted text). Full prose lives on [Greek NLP](Greek-NLP).

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `normalize` | Unicode-normalize; `--lenient` repairs OCR/Beta-Code | `--form --lenient` | `aegean greek normalize "λόγoς" --lenient` |
| `betacode` | Beta Code → polytonic Greek (`--reverse` for back) | `--reverse` | `aegean greek betacode "mh=nin"` |
| `strip` | Strip all diacritics |— | `aegean greek strip "μῆνιν"` |
| `tokenize` | Words + punctuation (or `--sentences`) | `--sentences --json` | `aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος."` |
| `syllabify` | Split word(s) into syllables | `--json` | `aegean greek syllabify εἰσφέρω` |
| `accent` | Accent type, position, classification | `--json` | `aegean greek accent λόγος` |
| `accentuate` | **Predict** the accent from the accentuation laws (dichrona flagged) | `--recessive/--persistent --lemma --json` | `aegean greek accentuate λυε --recessive` |
| `sandhi` | Expand crasis / elision / movable-ν to the underlying word(s) | `--json` | `aegean greek sandhi κἀγώ` |
| `quantities` | Per-syllable metrical quantity | `--json` | `aegean greek quantities πατρός` |
| `scan` | Metrical scansion against a fixed template | `--meter --json` | `aegean greek scan "…" --meter hexameter` |
| `ipa` | Reconstructed IPA pronunciation | `--period` | `aegean greek ipa "λόγος" --period koine` |
| `tag` | POS-tag (UD coarse tags) | `--treebank --tagger --neural --json` | `aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."` |
| `lemmatize` | Lemmatize every word | `--treebank --lemmatizer --neural-lemmatizer --neural --json` | `aegean greek lemmatize "μῆνιν ἄειδε θεά"` |
| `morph` | Candidate morphological parses | `--treebank --json` | `aegean greek morph λόγον` |
| `inflect` | Inflection synthesis (inverse lemmatizer): attested form(s) of a lemma | `--case --number --gender --tense --voice --mood --person --pos --paradigm --json` | `aegean greek inflect λόγος --case gen --number sg` |
| `parse` | Dependency-parse a sentence | `--neural --parser --json` | `aegean greek parse "…" --neural` |
| `gloss` | Gloss from a registry dictionary (LSJ by default) | `--dict/-d --full --json` | `aegean greek gloss μῆνις --dict cunliffe` |
| `gloss-nt` | Koine gloss from bundled Dodson lexicon (no download) | `--strongs --full --json` | `aegean greek gloss-nt λόγος --full` |
| `lexica` | List the available dictionaries (hosted + deep-link) | `--json` | `aegean greek lexica` |
| `lexicon-link` | A Logeion / Perseus deep-link for a word | `--service --no-lemmatize --json` | `aegean greek lexicon-link μήνιδος` |
| `usage` | Dialect + register tags for a word, mined from its LSJ entry (LSJ fetch on first use) | `--json` | `aegean greek usage μῆνις` |
| `rarity` | Terminology rarity of a text vs a reference corpus: a translation-difficulty signal | `--corpus --top --treebank --json` | `aegean greek rarity "μῆνιν ἄειδε θεά" --corpus nt` |
| `pipeline` | The one-call pipeline: per-token records | `--parse --parser --treebank --tagger --lemmatizer --neural-lemmatizer --neural -o/--output --json` | `aegean greek pipeline "ἐν ἀρχῇ" --json` |
| `work` | Fetch a real Greek work (Perseus / First1KGreek); `all AUTHOR` bulk-fetches a whole author | `--ref --source --edition --limit --dry-run --yes -o --json` | `aegean greek work tlg0012.tlg001 --ref 1.1-1.50` · `aegean greek work all homer` |
| `nt` | Read the Greek NT (Nestle 1904): a book, and a chapter or range, rendered as text | `--ref -o --json` | `aegean greek nt John 1` · `aegean greek nt Matt 1-3` |
| `works` | List the curated catalog of 25 well-known works; `--downloaded` lists what is in the cache; `--remove`/`--remove-author`/`--remove-all` delete downloaded works | `--downloaded --remove --remove-author --remove-all --json` | `aegean greek works --remove tlg0012.tlg001` |
| `catalog` | Search the full ~1,800-work discovery index (offline metadata); `--limit` caps `--json`/`-o` too, with the total kept in `matched` | `--author/-a --title/-t --source --limit/-n -o/--output --json` | `aegean greek catalog --author plato` |
| `nt-books` | List the 27 NT books + names the loaders accept | `--json` | `aegean greek nt-books` |
| `eval` | Reproduce the published numbers (heavy) | `--fold --split --bootstrap --drift --neural --tagger --lemmatizer --neural-lemmatizer -o/--output --json` | `aegean greek eval ud --neural` |

### Stages that work immediately

```bash
aegean greek betacode "mh=nin a)/eide qea/"      # μῆνιν ἄειδε θεά
aegean greek betacode "μῆνιν" --reverse          # mh=nin
aegean greek strip "μῆνιν"                        # μηνιν
aegean greek syllabify εἰσφέρω                    # εἰσφέρω → εἰσ-φέ-ρω
aegean greek accentuate λυε --recessive          # predicted accent (recessive verb): λύε
aegean greek sandhi κἀγώ                           # crasis expanded: καί ἐγώ
aegean greek quantities πατρός                    # πατρός → πα:common | τρός:heavy
aegean greek ipa "λόγος" --period koine          # loɣos

aegean greek normalize "λόγoς kai" --lenient
# aegean: lenient normalize: repaired 1 Latin letter(s) in Greek words (o→ο)   [stderr]
# λόγος kai

aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος."
# ἐν / ἀρχῇ / ἦν / ὁ / λόγος / .   (one token per line)
```

`accent` prints a small table; the same fact in Python:

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

Synizesis is lexical, not guessed: a line that only fits via synizesis on a word
outside the curated lexicon exits `1` with the reason rather than inventing a fit.
`--meter` accepts:

| name | metre |
|---|---|
| `hexameter` | dactylic hexameter (Homer): the default |
| `pentameter` | elegiac pentameter (second line of the couplet) |
| `trimeter` | iambic trimeter (tragic/comic dialogue) |
| `glyconic` · `pherecratean` · `adonean` | aeolic cola |
| `sapphic_hendecasyllable` | the Sapphic eleven-syllable line |
| `alcaic_hendecasyllable` · `alcaic_enneasyllable` · `alcaic_decasyllable` | the Alcaic stanza lines |

`scan --json` adds `feet`, `syllables`, `quantities`, `caesura`, `meter`, and an
`ambiguous` flag. The same in Python: `greek.scan_hexameter(line).pattern`.

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
# [{"sentence":0,"index":1,"text":"ἐν","upos":"ADP","lemma":"ἐν","lemma_known":true,…}, …]
```

A lemma the lexicon doesn't know is still returned, marked `(fallback)` (and
`"known": false` in JSON), so you can tell a real hit from a heuristic guess.

### Glossing

```bash
aegean greek gloss-nt λόγος               # a word, speech, divine utterance, analogy
aegean greek gloss-nt λόγος --full        # λόγος (G3056): a word, speech, divine utterance, analogy.
aegean greek gloss-nt 3056 --strongs      # look up by Strong's number → same gloss
```

`gloss-nt` uses the **bundled** CC0 Dodson lexicon (no download). The classical
`gloss` command uses the larger LSJ index, activated on first use (~270 MB, or
~15 MB if the `lsj-index` dataset is fetched).

### Backend flags (download/build on first use)

Each flag stands in for a `use_*()` activation in the Python API. The first time
you use one it may download a model or build an index to the cache (a note goes to
stderr); after that it's offline.

| flag | activates | first-use cost |
|---|---|---|
| `--treebank` | the Perseus AGDT lexicon | ~75 MB fetch |
| `--tagger` | the generalizing POS tagger | trains from the AGDT |
| `--lemmatizer` | the edit-tree lemmatizer | trains from the AGDT |
| `--parser` | the pure-Python arc-eager dependency parser | trains from the AGDT |
| `--neural-lemmatizer` | the GreTa seq2seq lemmatizer (`[neural]`) | ~232 MB model |
| `--neural` | the **joint neural pipeline**: best tagger/parser/lemmatizer (`[neural]`) | ~173 MB model |

```bash
# heavy — fetches on first use, then offline:
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural
aegean greek parse "ἐν ἀρχῇ ἦν ὁ λόγος" --neural     # UD dependency tree
aegean greek tag "…" --treebank --tagger             # AGDT lookup + perceptron tagger
```

### Loading real Greek works

`work` fetches a CC BY-SA text from Perseus canonical-greekLit / First1KGreek
(commit-pinned, cached once) and parses it into a corpus. `--ref` selects a
section: `1` (book), `1.2` (chapter), `1.1-1.50` (line range); `--source` is
`auto` / `perseus` / `first1k`; `--edition` picks a specific edition file. Browse
ids at scaife.perseus.org. Full reference: [Greek Works and Books](Greek-Works-and-Books).

```bash
aegean greek works                                # 25 curated highlights (table below)
aegean greek catalog --author plato               # search the full ~1,800-work index (offline)
aegean greek work tlg0012.tlg001                  # heavy: the Iliad, one doc per book
aegean greek work tlg0012.tlg001 --ref 1.1-1.50   # just book 1, lines 1–50
aegean greek work tlg0012.tlg001 -o iliad.json    # save as a corpus file
aegean greek nt John --ref 1.1-1.18               # the Greek NT (bundled): gold lemma/morph/gloss
```

The curated catalog (`aegean greek works`):

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

This is a starting point, not the whole canon: `work` accepts any valid Perseus /
First1KGreek id.

### `catalog` — the full discovery index

`catalog` searches the **complete** bundled metadata behind `works`: 1,778 works
(768 `perseus` + 1,010 `first1k`), every text with a Greek edition in the two pinned
repos. Offline, instant, no fetch; any id it returns goes straight to `aegean greek
work`. The bare `QUERY` is a catch-all over id/author/English-title/Greek-title;
`--author/-a`, `--title/-t`, and `--source perseus|first1k` are targeted filters
(case-insensitive, AND). `--limit/-n` caps the table, `--json`, and `--output/-o`
alike (`0` = all), with the untruncated total kept in the JSON's `matched`;
`-o` saves by extension (`.json`/`.csv`/`.txt`).

```bash
aegean greek catalog --author plato --limit 8
#   → 39 matches: tlg0059.tlg001 Euthyphro · tlg0059.tlg002 Apology · … (table)

aegean greek catalog herodotus --json
# {"matched": 2, "works": [{"id":"tlg0016.tlg001","author":"Herodotus",
#   "title":"Histories","greek_title":"Ἱστορίαι","source":"perseus"}, … ]}

aegean greek catalog --author aristophanes --source perseus -o aristophanes.csv
#   → wrote aristophanes.csv   (id,author,title,greek_title,source)
```

Coverage is exactly what the upstream repos hold, so genuinely-absent authors return
nothing rather than a fabricated row:

```bash
aegean greek catalog sappho
# No works match. Try a looser filter, or browse https://scaife.perseus.org
```

In Python: `greek.catalog(query=None, *, author=None, title=None, source=None)` →
`{id, author, title, greek_title, source}` dicts; `greek.popular_works()` stays the
curated 25.

The 27 NT books (`aegean greek nt-books`) and the names `gloss-nt` / `load_nt`
accept:

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

In Python: `from aegean import greek; greek.load_nt("John", ref="1.1-18")` and
`greek.load_work("tlg0012.tlg001", ref="1.1-1.50")`.

### Reproducing the published numbers (`eval`)

`aegean greek eval TARGET` runs the official evaluators against fetched gold data
(heavy). Targets: `ud`, `proiel`, `nt`, `tagger`, `lemmatizer`, `parser`. For `ud`,
`--fold` is `perseus` / `proiel` and `--split` is `dev` / `test` (both validated
before anything is fetched; the old `--treebank` spelling for the fold selector is
a deprecated alias that warns, naming `--fold`). For `proiel`, `--drift` prints a
POS-confusion / lemma convention-drift breakdown (which separates systematic
annotation-convention divergence from real error) instead of the bare accuracy
numbers. `-o/--output` saves the measured numbers like any result table.

```bash
aegean greek eval ud --fold perseus --split test --neural   # heavy
aegean greek eval proiel --drift                            # where the PROIEL gap comes from
```

The exact figures and how they were measured are on [Greek NLP](Greek-NLP) and
[Limitations](Limitations).

---

## Analysis — `aegean analyze …`

Exploratory **surface** analyses over the (largely undeciphered) Aegean material:
evidence to weigh, not conclusions. Method notes are on [Analysis](Analysis).

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `distance` | Weighted phonetic distance in [0,1] (0 = identical) | `--json` | `aegean analyze distance KU-RO KI-RO` |
| `align` | Per-position phonetic alignment | `--json` | `aegean analyze align KU-RO KI-RO` |
| `compare` | Compare two words **across** scripts by sound | `--script-a --script-b --fold-aspiration --json` | `aegean analyze compare po-me ποιμήν` |
| `nearest` | Rank a corpus's words by closeness to WORD | `--script-a --fold-aspiration --top -o/--output --json` | `aegean analyze nearest qa-si-re-u greek` |
| `assoc` | Doc-level association: χ², G², Fisher, PMI | `-o/--output --json` | `aegean analyze assoc lineara KU-RO KI-RO` |
| `cooccur` | Words sharing a document with WORD, ranked | `--top -o/--output --json` | `aegean analyze cooccur lineara KU-RO` |
| `clusters` | Stems with productive-suffix derivations | `--min-size --top -o/--output --json` | `aegean analyze clusters lineara` |
| `structure` | Heuristic doc categories (accounting/libation/…) | `--site --period --scribe --support -o/--output --json` | `aegean analyze structure lineara` |
| `hands` | Scribal-hand profiles / keyness (e.g. DAMOS) | `--hand --top --min-docs --signs --site --period --scribe --support -o/--output --json` | `aegean analyze hands damos` |

### Verified examples

```bash
aegean analyze distance KU-RO KI-RO
# KU-RO ↔ KI-RO: 0.200

aegean analyze align KU-RO KI-RO
# K K match · U I sub-far · - - match · R R match · O O match

aegean analyze compare po-me ποιμήν
# po-me [linearb] → pome    ποιμήν [greek] → poimēn
# similarity 0.62  (distance 0.383)   [+ a per-position alignment table]

aegean analyze nearest qa-si-re-u greek --top 3 --json
# [{"candidate":"Ἡροδότου","distance":0.612},{"candidate":"καὶ","distance":0.625},
#  {"candidate":"ἄειδε","distance":0.625}]

aegean analyze assoc lineara KU-RO KI-RO
# joint/w1/w2/docs 5/34/12/1721 · chi_squared 78.75 · log_likelihood 23.94 · fisher_p 1.6e-06

aegean analyze cooccur lineara KU-RO --top 5
# KI-RO 5 · *306-TU 4 · KU-PA₃-NU 4 · SA-RA₂ 4 · *324-DI-RA 3

aegean analyze structure lineara
# accounting 134 · libation 18 · list 6 · text 1 · other 1562   (heuristic census)

aegean analyze cooccur lineara KU-RO --top 5 -o cooccur.csv   # save the ranking
```

`assoc`, `cooccur`, `clusters`, `structure`, `hands`, and `nearest` take the same
`-o FILE` (`.json` / `.csv` / `.txt`) as the top-level analysis commands, printing
the same `wrote <path>` confirmation and combining with `--json`. `structure` and
`hands` also take the shared metadata filters (`--site --period --scribe
--support`), and `--top 0` lifts the cap on the ranked tables.

`compare` / `nearest` script options (`--script-a` / `--script-b`): `greek`,
`lineara`, `linearb`, `cypriot`. `--fold-aspiration` maps θ/φ/χ → t/p/k, which is
fairer against defective syllabic spelling. These numbers are exploratory: read
the **alignment and the ranking**, not the absolute distance. The Python
equivalent of `distance`:

```python
from aegean import analysis
analysis.phonetic_distance("KU-RO", "KI-RO")    # 0.2
```

`hands` needs a corpus that records a scribe per document (DAMOS does; the bundled
`lineara` records HT scribes too):

```bash
aegean analyze hands damos                       # profile every hand
aegean analyze hands damos --hand 103            # one hand's characteristic words (keyness)
```

---

## Data — `aegean data …`

The fetch-to-store layer. Nothing here is bundled; everything downloads on demand,
sha256-verified, into a permanent local store: a fetched dataset is never
re-fetched, evicted, or expired, and stays until `remove` deletes it.

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `list` | The fetchable datasets + downloaded status and on-disk size | `--json` | `aegean data list` |
| `fetch` | One-time download into the store (idempotent; resumes) | `--force` | `aegean data fetch grc-joint` |
| `remove` | Delete downloaded dataset(s), reclaiming the space | `--all` `--json` | `aegean data remove nt-corpus` |
| `versions` | Reproducibility manifest: version + sha256 | `--json` | `aegean data versions --json > data-versions.json` |
| `store` | Store location + current contents | `--json` | `aegean data store` |

The fetchable datasets (`aegean data list`):

| name | what | license |
|---|---|---|
| `agdt-derived` | prebuilt AGDT lexicon + tagger/lemmatizer/parser models | CC BY-SA 3.0 (Perseus AGDT) |
| `grc-joint` | joint tagger-parser-lemmatizer, ~173 MB (the `[neural]` extra) | CC BY-SA 4.0 |
| `grc-lemma-neural` | GreTa seq2seq lemmatizer, ~232 MB (the `[neural]` extra) | CC BY-SA 4.0 |
| `lsj-index` | prebuilt LSJ lemma→entry index (~15 MB) | CC BY-SA 4.0 (Perseus) |
| `damos-corpus` | DAMOS Linear B corpus, ~5,900 tablets: `load('damos')` | CC BY-NC-SA 4.0 |
| `sigla-corpus` | SigLA Linear A dataset, 781 docs: `load('sigla')` | CC BY-NC-SA 4.0 |
| `nt-corpus` | Greek NT (Nestle 1904), 260 chapters / ~137,800 tokens: `load('nt')` | CC0-1.0 |
| `lineara-images` | 3,368 facsimile/photo files (~116 MB) | academic reference only |
| `linearb-corpus` | bring-your-own Linear B export (no default source) | per your source |
| `workbench-app` | prebuilt workbench web app (~3 MB): served by `aegean workbench` | Apache-2.0 |

```bash
aegean data fetch grc-joint                       # pre-fetch before going offline
aegean data remove lineara-images                 # delete a downloaded dataset (--all clears all)
aegean data versions --json > data-versions.json  # pin every dataset's sha256 for a paper
aegean data store                                 # store path + contents (override: PYAEGEAN_CACHE)
```

There are **two** caches: this **data** download store (`aegean data store`,
permanent until `aegean data remove`, override with `PYAEGEAN_CACHE`; `aegean data
cache` remains a deprecated alias this minor) and the opt-in **analysis**
memoization cache
(`aegean cache`, enabled with `PYAEGEAN_ANALYSIS_CACHE=1`). Licensing details are
on [Data & Provenance](Data-and-Provenance).

---

## SQLite — `aegean db …`

Build a queryable SQLite database from any corpus (documents + tokens + an FTS5
full-text index) and search it.

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `build` | Write a corpus to a SQLite DB | `-o/--output --no-fts` | `aegean db build lineara -o lineara.db` |
| `add` | Upsert another corpus into an existing DB | `-o/--output` | `aegean db add cypriot -o lineara.db` |
| `search` | Search a corpus DB's tokens (whole-token by default; --substring to match within tokens; opens the DB read-only) | `--limit (0 = all) --substring -o/--output --json` | `aegean db search lineara.db KU-RO` |

```bash
aegean db build lineara -o lineara.db        # → "wrote 1721 documents to lineara.db"
                                             #    search it:  aegean db search lineara.db KU-RO
aegean db search lineara.db KU-RO --limit 3
#   doc    pos  text
#   HT9a   25   KU-RO
#   HT9b   20   KU-RO
#   HT11a  7    KU-RO
aegean db search lineara.db KU-RO-ZZ
# no matches (whole-token) — pass --substring to match within tokens
```

`db search` never creates or modifies a file (the database opens read-only; a
missing path is a one-line error naming `aegean db build`), `--limit 0` returns
every match, and `-o` saves the hits (`.json`/`.csv`/`.txt`).

`build`'s corpus argument is any of the usual forms (id, work id, `.json`/`.db` file,
`-`), so `aegean db build tlg0012.tlg001 -o iliad.db` builds straight from a Greek work.

`db add SRC -o existing.db` grows a database in place: it **upserts by document id**: a
matching id is replaced, new ids are added, and the FTS index is refreshed. It's the
incremental sibling of `combine`:

```bash
aegean db build lineara -o aegean.db    # start the database
aegean db add cypriot   -o aegean.db    # → "added/updated 180 documents in aegean.db"
```

`--no-fts` skips the full-text index. `aegean export CORPUS -f sqlite -o file.db`
writes the same database. In Python the same upsert is `corpus.to_sql(path,
append=True)` (or `aegean.db.to_sqlite(corpus, path, append=True)`); load a DB back with
`Corpus.from_sql(path)`.

---

## AI — `aegean ai …` (exploratory, key-gated)

The generative layer. **Every result is exploratory**: a labeled model hypothesis
carrying its grounding, never a citable fact and never a "decipherment." It needs a
provider SDK (an extra such as `pip install "pyaegean[anthropic]"`) and that
provider's API key in your environment. Without a key the command exits `1` with a
clear message: it never silently calls out. Design notes: [AI Layer](AI-Layer);
hard limits: [Limitations](Limitations).

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `providers` | List the registered AI providers | `--json` | `aegean ai providers` |
| `translate` | Hybrid translation (local grounding → LLM) | `--script --target --glosses/--no-glosses --provider --model --trace -o/--output --json` | `aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"` |
| `gloss` | Interlinear word-by-word gloss | `--source --provider --model --trace -o/--output --json` | `aegean ai gloss "μῆνιν ἄειδε θεά"` |
| `summarize` | Short, grounded summary of a passage | `--corpus --provider --model --trace -o/--output --json` | `aegean ai summarize "ἐν ἀρχῇ ἦν ὁ λόγος" --corpus nt` |
| `hypotheses` | Cautious decipherment hypotheses (strictly exploratory) | `--corpus --provider --model --trace -o/--output --json` | `aegean ai hypotheses "A-TA-I-*301-WA-JA" --corpus lineara` |
| `ask` | Answer strictly from the supplied grounding | `--corpus --provider --model --trace -o/--output --json` | `aegean ai ask "What is KU-RO?" --corpus lineara` |
| `extract` | Structured (JSON) extraction, ready to pipe | `--fields --instruction --corpus --provider --model -o/--output --json` | `aegean ai extract "OLE S 1" --fields commodity,amount` |
| `eval` | Grounded-generation fidelity eval | `--provider --model -o/--output --json` | `aegean ai eval --provider anthropic` |

```bash
aegean ai providers
# anthropic / gemini / grok / openai / openrouter

# heavy (needs the provider extra + API key in your environment):
aegean ai translate "KU-RO 130" --script lineara          # exploratory (undeciphered!)
aegean ai ask "What is KU-RO?" --corpus lineara --trace   # answer + grounding provenance
aegean ai extract "OLE S 1" --fields commodity,amount     # → {"commodity":"OLE","amount":…}
```

`--provider` is `anthropic` (default) / `openai` / `grok` / `gemini` / `openrouter`; `--model`
overrides the model. `--corpus NAME` grounds the answer on that corpus's frequent
words. `--trace` prints the grounding provenance under the answer, so you can audit
exactly what the model was (and wasn't) told. `extract` always prints JSON. For Greek,
`translate` grounds with deterministic morphology by default; `--mode full` adds
rarity-gated concise glosses, `--mode lemma` / `--mode none` select the legacy or bare
paths, and `--verify` drafts then checks + repairs against the analysis (a second call).

`-o FILE` saves the run for later: `.json` keeps the text **plus its provenance and
grounding** (and the exploratory label is preserved on disk), while `.txt` writes the
labeled text. In Python the same record round-trips via
`ExploratoryResult.to_dict()` / `to_json()` / `from_dict()`.

```bash
# heavy (needs a provider + key); save the audit trail next to the answer:
aegean ai ask "What is KU-RO?" --corpus lineara -o answer.json   # text + grounding
aegean ai translate "KU-RO 130" --script lineara -o draft.txt    # labeled text
```

---

## MCP server — `aegean-mcp`

A separate console script (the `[mcp]` extra) that exposes the toolkit to AI agents
(Claude Code and other MCP clients) over stdio, so an agent can use pyaegean
without writing Python.

```bash
pip install "pyaegean[mcp]"
aegean-mcp                # serve the read/analysis tools over stdio
```

It offers fifteen read/analysis tools. Corpora: `list_corpora`, `corpus_info`,
`show_document`, `search_signs` (wildcard sign patterns), `balance_accounts`
(accounting reconciliation), `query_corpus` (the compound query engine),
`cite_corpus` (plain/BibTeX/APA, exact subsets included), `geo_sites` (find-site
coordinates and per-site word attestations), and `data_status` (the local data
store, read-only). Greek: `greek_pipeline`, `greek_scan` (verse scansion),
`greek_catalog` (the ~1,800-work discovery catalogue), `greek_work` (load a
work's text by catalogue id; the first use fetches it into the local data store,
cached and offline after), `greek_gloss` (the registry dictionaries), and
`koine_gloss` (the bundled Dodson NT lexicon). Corpora and works are addressed
by registry name or catalogue work id only (never a filesystem path), and a
domain miss returns a structured error with a did-you-mean hint.

---

## Quick recipes

```bash
# Keep only the Linear A accounts that DON'T balance
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json

# Lemmatize a file, one lemma per line
cat chapter.txt | aegean greek lemmatize - --json | jq -r '.[].lemma'

# Pin every dataset's sha256 for a paper's reproducibility appendix
aegean data versions --json > data-versions.json

# Map a word's distribution and cite the exact subset you used
aegean geo lineara --output sites.geojson
aegean cite lineara --site "Zakros" --style bibtex >> paper.bib

# Save a query subset, then analyse just that slice — no Python in between
aegean query lineara --where "site-is=Zakros" -o zakros.json
aegean stats zakros.json --top 10 -o zakros-counts.csv

# Build one database from several sources, growing it as you go
aegean combine lineara linearb -o aegean.db   # both scripts in one DB
aegean db add cypriot -o aegean.db            # add a third later (upsert by id)
```

More worked pipelines are on [Recipes](Recipes).

---

## Notes & limits

- **`--json` is the contract; the rich tables are for humans.** Don't parse the
  tables: pass `--json` and use `jq`. `--limit`/`--top` cap the JSON lists too
  (`0` lifts the cap); where a payload carries totals (`matched`), they stay
  untruncated.
- **Heavy commands download on first use.** `--neural`, `greek work`, `greek eval`,
  `gloss`, and the fetched corpora pull data to the cache the first time, with a
  note on stderr; afterwards they're offline. Pre-fetch with `aegean data fetch`.
- **The AI layer is exploratory.** Translations, glosses, and "hypotheses" for
  undeciphered material are labeled model output with grounding, not findings. The
  Aegean scripts remain undeciphered.
- **Metre and accuracy are bounded.** Lyric metres beyond the fixed aeolic
  templates are out of scope, and the trainable backends have measured ceilings:
  both documented on [Limitations](Limitations).

For the guided tour with full prose and more worked output, see [CLI](CLI).
