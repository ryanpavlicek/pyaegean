# The `aegean` command line

`aegean` is the whole toolkit from your terminal (corpora, Greek NLP, surface
analysis, the fetch-to-cache data layer, SQLite, plots, and the (exploratory) AI
layer) without writing a line of Python. If you've never used a command line
before, start with [Getting Started](Getting-Started) (it shows you how to open a
terminal); then come back here. Everything below is something you can copy, paste,
and run.

> **In a hurry?** The [CLI Cheatsheet](CLI-Cheatsheet) is the dense one-page index
> of every command and flag. This page is the guided tour: it explains each group
> and shows a worked example with real output.

```bash
pip install "pyaegean[cli]"     # adds typer + rich; the core library stays zero-dependency
aegean --help
```

If you only ran `pip install pyaegean`, the library works but the `aegean`
command isn't installed yet. The `[cli]` extra adds it. (If you run `aegean`
without it, you get one line telling you exactly that.)

## Conventions that hold everywhere

Learn these once and every command behaves predictably.

| Convention | What it does | Example |
|---|---|---|
| **`--json`** | Print one machine-readable JSON document to stdout and nothing else, so results pipe into `jq`, files, or other programs. Greek stays readable (`ensure_ascii=False`). Combines with `--output/-o`: the file is written (a one-line `wrote <path>` confirmation goes to stderr) and the JSON still prints to stdout. | `aegean info lineara --json` |
| **`-` reads stdin** | Anywhere a command takes a `TEXT` argument, passing `-` reads the text from standard input, so commands compose in pipelines. | `echo "μῆνιν" \| aegean greek lemmatize -` |
| **`--top` / `--limit`** | Interchangeable spellings of the same cap: every command that caps a ranked table or result list accepts both, `plot` included. `0` lifts the cap wherever the help says `0 = all` (`greek rarity` is the one exception: its cap is a plain slice, so `0` shows nothing). | `aegean stats lineara --limit 3` |
| **Exit codes** | `0` success · `1` a domain error (one line on stderr, prefixed `aegean:`) · `2` a usage error (typer's default). `balance --strict` exits `1` when any total fails to balance. | see below |

Here are those exit codes, actually demonstrated:

```bash
aegean info lineara --json > /dev/null ; echo "exit=$?"      # exit=0   (success)
aegean info bogus                                            # aegean: unknown corpus 'bogus'; expected a registered id (…)
                                                            # exit=1   (domain error, message on stderr)
aegean info                                                  # exit=2   (usage error: missing argument)
aegean balance lineara HT13 --strict ; echo "exit=$?"        # exit=1   (a total didn't balance)
```

A help summary is one `-h`/`--help` away on every command and group:

```bash
aegean --help
aegean greek --help
aegean greek scan --help
```

> **Windows note:** if polytonic Greek shows up as boxes or `?`, that's the
> terminal font, not pyaegean. Set `PYTHONUTF8=1` and run `chcp 65001` once to
> switch the console to UTF-8, or just use the `--json` output, which is always
> correct, and view it in an editor. See [Getting Started](Getting-Started#seeing-greek-correctly).
> The Linear A/B glyph columns (𐝫, 𐙂) additionally need a font that covers the
> Aegean scripts: see [Installation → Set up your terminal](Installation#set-up-your-terminal).

## The command map

```bash
aegean --version          # pyaegean 0.19.12
```

| Group | What's in it |
|---|---|
| **(top level)** | `quickstart` `repl` `tui` `info` `load` `show` `search` `query` `stats` `dispersion` `keyness` `cache` `doctor` `balance` `cite` `export` `combine` `import` `geo` `sign` `bridge` `plot` `workbench` |
| **`aegean greek …`** | normalize → tokenize → syllabify → accent → `accentuate` → `sandhi` → scan → tag → lemmatize → morph → `inflect` → parse, plus `pipeline`, `gloss`/`gloss-nt`/`usage`/`lexica`/`lexicon-link`, `rarity`, `work`/`nt`/`works`/`catalog`/`nt-books`, and `eval` |
| **`aegean analyze …`** | `distance` `align` `compare` `nearest` `assoc` `cooccur` `clusters` `structure` `hands` |
| **`aegean data …`** | `list` `fetch` `remove` `versions` `store` |
| **`aegean db …`** | `build` `add` `search` (SQLite + FTS5) |
| **`aegean ai …`** | `providers` `translate` `gloss` `summarize` `hypotheses` `ask` `extract` `eval` (exploratory, key-gated) |
| **`aegean-mcp`** | a separate console script: serve the tools to AI agents over MCP |

---

## The guided tour (`aegean quickstart`)

New to the toolkit? `aegean quickstart` runs the first five minutes for you:
eight short steps, each printing one dim line of context; seven of them run a real
command and show its **real output**, live on the bundled data (the last points onward).
All offline, no keys, nothing downloaded. It reads a Linear A tablet, audits its
accounting arithmetic, searches by sign pattern, runs the Greek pipeline, scans
the Iliad's first line as a hexameter, shows the fetchable datasets, and closes
with pointers for where to go next. Two of the eight steps, as they actually
print:

```text
$ aegean quickstart
aegean quickstart: the first five minutes, live on bundled data, all offline.
…
[4/8] Search words by sign pattern: * stands for exactly one sign.
$ aegean search lineara "KU-*-RO"
'KU-*-RO': 1 word(s)
┌──────────┬───────┐
│ word     │ count │
├──────────┼───────┤
│ KU-MA-RO │ 1     │
└──────────┴───────┘
…
[8/8] Where next:
  aegean repl                   every command, interactive, with completion
  aegean doctor                 check the install and cached data
  aegean --install-completion   tab-completion for your shell
  docs:                         https://github.com/ryanpavlicek/pyaegean/wiki

That was 7 real commands in 0.2s, all offline, all bundled data.
```

`--no-run` prints the tour script without executing anything, so you can read
the seven commands first. Because the outputs are live, what you see is exactly
what your install does.

---

## Interactive shell (`aegean repl`)

If you're running several commands in a row, `aegean repl` opens an interactive
shell so you don't retype `aegean` each time. Inside it you type the subcommand
directly, with **Tab-completion** of commands and options and a **history that
persists across sessions**:

```text
$ aegean repl
aegean interactive shell — commands without the 'aegean' prefix.
Tab completes, history persists, :help lists commands, :exit or Ctrl-D quits.
:examples shows starter lines; 'aegean --install-completion' (outside the shell) adds completion to your regular shell.
aegean> info lineara
…the same table aegean info lineara prints…
aegean> greek syllabify Ποσειδῶνι
Ποσειδῶνι → Πο-σει-δῶ-νι
aegean> use lineara
aegean: session corpus: lineara — corpus-first commands (show, stats, search, …) now default to it; 'use off' clears.
aegean> stats --top 3
…the lineara frequency table, no corpus argument needed…
aegean> :exit
```

Every line is dispatched through the same command tree, so a command behaves
exactly as it does on the regular command line: `--json`, `-o`, corpus files and
work ids, all of it. A mistyped command just prints its error and leaves the shell
open. The shell needs the `[cli]` extra (it ships `prompt_toolkit`).

### Shell-only directives

Three things exist only inside the shell (they are session sugar, never
dispatched as commands):

- **`use CORPUS`** sets a **session corpus**: the corpus-first commands (`info`,
  `load`, `show`, `search`, `query`, `stats`, `dispersion`, `keyness`, `balance`,
  `cite`, `export`, `geo`, `sign`, `db build`, and the corpus-taking `analyze`
  subcommands) then default to it whenever a line names no corpus, so
  `show HT13` works after `use lineara`. A line that names its own corpus always
  wins (`info linearb` still reads `linearb`), `use` alone reports the current
  setting, and `use off` clears it. The target is validated when you set it, with
  the standard did-you-mean, and must be re-loadable (a registered id, a Greek
  work id, or a `.json`/`.db` file; not stdin JSON):

  ```text
  aegean> use linera
  aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (cypriot, cyprominoan, damos, greek, lineara, linearb, nt, sigla), a Greek work id like tlg0012.tlg001, or a path to a .json or .db corpus
  ```

  One deliberate limit: with a session corpus set, options written *before* an
  explicit corpus (`stats --top 5 linearb`) fail with a clean usage error rather
  than silently reading the wrong corpus. Put the corpus first, as usual.
- **`:examples`** (or `examples`) prints copyable starter lines spanning the
  command groups: thirteen real commands, each with a one-line description,
  ending with a `use lineara` / `show HT13` pair that demonstrates the directive.
- **`:help`** (or `help`) prints a one-line reminder of these directives and then
  the full command list; `:exit`, `quit`, or **Ctrl-D** leaves.

### History

The arrow-key history **persists across sessions** in
`~/.config/pyaegean/repl_history` (`XDG_CONFIG_HOME` is honored; on Windows that
is `%USERPROFILE%\.config\pyaegean\repl_history`). It works on every platform,
Windows included: `prompt_toolkit` ships with the `[cli]` extra, no readline
needed. The file lives on the config side, deliberately **not** in the
`PYAEGEAN_CACHE` data store, so `aegean data store` keeps listing downloads only;
if the location isn't writable the shell falls back to a session-only history
rather than failing to start. Piped (scripted) sessions are not recorded.

When standard input isn't a terminal, the shell reads one command per line instead
of prompting, so you can script it (the `use` directive works there too):

```bash
printf 'use lineara\nshow HT13\nstats --top 3\n' | aegean repl
```

---

## The terminal UI (`aegean tui`)

Where `repl` is the same commands typed one after another, **`aegean tui`** is a
full-screen, app-like cockpit for the highest-value offline reads: a scrollable
corpus browser, a live Greek workbench, and the local data store, all inside your
terminal. It is built on [Textual](https://textual.textualize.io/) and ships as
the `[tui]` extra:

```bash
pip install "pyaegean[tui]"
aegean tui
```

If the extra isn't installed, `aegean tui` exits with one line telling you exactly
that (`the TUI needs the [tui] extra — install it with: pip install
'pyaegean[tui]'`), the same way `aegean plot` guards `[viz]`. Everything the TUI
does is **offline and needs no API key**: it is a research reader over the bundled
and cached data, never the (key-gated, exploratory) AI layer.

### What's on screen

Four screens, switched with a single key from anywhere:

| Screen | Key | What it shows |
|---|---|---|
| **Home** | `h` | The landing view: the eight corpora at a glance, the global-key legend, and the permanent undeciphered-script honesty banner. |
| **Corpus browser** | `c` | Three panes: the corpus list → a filterable document table (search by id, or by sign pattern like `KU-*-RO`) → an apparatus-aware document detail with its accounting reconciliation (`KU-RO` / `to-so` balance) and structure classification inline. |
| **Greek workbench** | `g` | A text box over live tabs that re-render as you type: the full pipeline (lemma / POS / morphology), metrical scansion (with a hexameter / pentameter / trimeter selector), syllabification, and reconstructed IPA. All zero-dependency and instant. |
| **Data store** | `d` | The `aegean doctor` environment report and the `aegean data list` table in one place: versions, extras, the data store, and the fetchable datasets, with a per-dataset Fetch action that downloads on a background worker with a progress bar. |

The other global keys work on every screen: `q` quits, `?` returns to Home (where
the legend lives), and **`ctrl+p`** opens the command palette, a fuzzy-searchable
list of everything the keys do (open any corpus by name, jump to a screen, fetch a
dataset). Inside the corpus browser, `/` focuses the search box, `enter` on a
document row opens its detail, and `tab` cycles the three panes.

### Undeciphered-script honesty, at point of use

The honesty rule the CLI and docstrings carry travels into the TUI: **Linear A and
Cypro-Minoan are undeciphered, so any structural analysis of them is exploratory,
not a reading.** That caveat is a permanent banner on the Home screen, and it
appears again as a dim line in the document-detail pane whenever the open corpus is
`lineara` or `cyprominoan`, so it is in front of you exactly when you are looking at
undeciphered material. The deciphered corpora (Greek, Linear B, Cypriot) carry no
such caveat.

### A focused cockpit, not a second front end

The TUI covers the three highest-value offline areas (browse and analyze a document,
the Greek workbench, and the data store), which is a deliberate scope: it is a
research cockpit for the reads you do most, **not a mirror of every command**. The
full query engine, keyness/dispersion, plots, export/import, geo maps, `db build`,
the eval reproductions, and the exploratory AI layer stay on the regular command
line (and in `aegean repl`), which remains the complete surface. On Windows the
Aegean glyph columns render best with the Aegean fonts from
[Installation → Set up your terminal](Installation#set-up-your-terminal); run the
TUI with `PYTHONUTF8=1` so Greek and Linear A display correctly.

---

## Corpus commands (top level)

Every corpus command takes a **corpus id** as its first argument. The bundled,
offline-from-install corpora are `lineara`, `linearb`, `cypriot`, `cyprominoan`,
and `greek`. Three more download to your cache on first use: `damos` (the full
~5,900-tablet DAMOS Linear B corpus), `sigla` (the SigLA Linear A dataset), and
`nt` (the Greek New Testament). Registered ids also match case-insensitively as a
fallback (`aegean info LINEARA` loads `lineara`). Pass an unknown id and the error
lists the valid ones, and suggests the nearest registered id when your spelling is
close:

```bash
aegean info bogus
# aegean: unknown corpus 'bogus'; expected a registered id (cypriot, cyprominoan, damos, greek, lineara, linearb, nt, sigla), a Greek work id like tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin
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

`--json` gives the full metadata block plus `lines` as nested token lists.

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
occurs in), not its token count, so it differs from the token-frequency counts
that `search` and `stats` report.

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

### `stats` — frequency tables

Word frequencies by default; `--signs` counts individual signs.

```bash
aegean stats lineara --signs --top 5
```
```
┌──────┬───────┐
│ item │ count │
├──────┼───────┤
│ 𐝫    │ 552   │
│ 𐄁    │ 468   │
│ 1    │ 310   │
│ KU   │ 307   │
│ KA   │ 284   │
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
│ KU-PA₃-NU │ 8    │ 7/559       │ 0.948 │ 0.949  │
│ SA-RA₂    │ 20   │ 20/559      │ 0.948 │ 0.949  │
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

### `export` — JSON, CSV, Parquet, EpiDoc, SQLite

```bash
aegean export lineara -f csv -o lineara.csv               # → "wrote 1721 documents to lineara.csv (csv)"
aegean export greek -f epidoc -o greek.xml                # EpiDoc TEI
aegean export lineara -f sqlite -o lineara.db             # same DB as `aegean db build`
aegean export lineara -f workbench -o wb.json             # Linear A Workbench JSON
```

| `--format` | output | needs |
|---|---|---|
| `json` | lossless, round-trippable corpus | core |
| `csv` | one row per document/token/word (`--level`) | core |
| `parquet` | same, columnar | `[parquet]` extra |
| `epidoc` | EpiDoc TEI XML | core |
| `sqlite` | queryable DB with FTS5 | core |
| `workbench` | Linear A Research Workbench JSON (round-trips via `import --workbench`) | core |

`--level token` (csv/parquet) emits one row per token and spreads per-token
annotations (the Greek NT's lemma / morph / Strong's / gloss) into columns.
Filters (`--site` etc.) apply before export.

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
is accepted. (Greek/Koine text is run through the Greek tokenizer, which strips
punctuation; any other `--script` splits on whitespace.)

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

`--encoding` (default `utf-8`) reads non-UTF-8 files. The same lives on `aegean.io`
in Python: `from_text`, `from_text_file`, `from_text_dir`, and `from_csv` (the CSV
one also takes `meta_cols=` to carry columns into document metadata):

```python
from aegean import io
c = io.from_text("μῆνιν ἄειδε θεά", script_id="nt")           # a raw string
c = io.from_text_file("john.txt", script_id="nt", split="line")
c = io.from_csv("verses.csv", text_col="line", id_col="id", script_id="nt")
```

A **Linear A Workbench export** (the JSON the workbench saves) imports back with
`--workbench`, the inverse of `export -f workbench`:

```bash
aegean export lineara -f workbench -o wb.json   # corpus → Workbench JSON
aegean import wb.json --workbench -o back.json  # Workbench JSON → corpus
```

**EpiDoc TEI** imports back the same way — any EpiDoc edition (a file or a folder of `.xml`),
not just pyaegean's own output — via `--epidoc`, the inverse of `export -f epidoc`:

```bash
aegean export lineara -f epidoc -o ins/                    # corpus → EpiDoc TEI (one file per doc)
aegean import ins/ --epidoc --script lineara -o back.json  # any EpiDoc edition → corpus
```

It recovers the id, find-place, token/line stream, editorial certainty
(`<unclear>`/`<supplied>`), and `<app>` variants, using only the stdlib XML parser.

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
wipes it. Cached values are stored with `pickle` and unpickled on read, so point
it only at a directory **you** control, never a shared or group-writable one, and
don't reuse a cache file from someone else (loading a cache is a code-execution
trust boundary, the same as a pip or pytest cache). The file is created owner-only,
and enabling a cache in an others-writable directory warns.

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
│ OK │ pyaegean │ 0.19.12                    │
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

```bash
pip install "pyaegean[viz]"
aegean plot keyness lineara --site Zakros -o zakros.png      # → "wrote zakros.png"
aegean plot scansion "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ" -o scan.svg --meter hexameter   # → "wrote scan.svg"
```

For `scansion` the second argument is the Greek line itself (`-` reads stdin); for
every other kind it's a corpus name.

### `workbench` — serve the Linear A Research Workbench locally

```bash
aegean workbench                 # fetch the build (~3 MB, first use) and open it in your browser
aegean workbench --fetch-images  # also download the facsimile imagery (~116 MB) so pictures show
aegean workbench --port 9000     # choose a port (1-65535, default 8000); --no-browser to not open one
```

Fetches the sha256-pinned static build to the cache, then serves the browser UI (
the corpus, maps, and analysis modules) at `http://localhost:8000/` until you
press Ctrl+C. The facsimile imagery is a separate ~116 MB asset: pass
`--fetch-images` (or run `aegean data fetch lineara-images`) to download it, after
which the picture browser works. Without it the app runs fine, but image views
show no picture (and the command says so at startup).

---

## Greek NLP — `aegean greek …`

The full Ancient Greek pipeline from the shell. The zero-dependency stages run the
moment you install; the heavier backends are opt-in flags (next section). Full
explanations live on [Greek NLP](Greek-NLP); metre is on [Meters](Meters).

Every text argument accepts `-` for stdin, and every data-producing command takes
`--json` (the plain text transforms `normalize`, `betacode`, `strip`, and `ipa`
just print the converted text, ready for the next pipe).

### The stages that work immediately

```bash
aegean greek betacode "mh=nin a)/eide qea/"      # μῆνιν ἄειδε θεά
aegean greek betacode "μῆνιν" --reverse          # mh=nin   (Unicode → Beta Code)
aegean greek normalize "λόγoς kai" --lenient     # repairs OCR artifacts; warns on stderr
aegean greek strip "μῆνιν"                        # μηνιν   (drop all diacritics)
aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος."       # one token per line (--sentences to split sentences)
aegean greek syllabify εἰσφέρω                    # εἰσ-φέ-ρω
aegean greek accent λόγος                         # acute, paroxytone
aegean greek accentuate λυε --recessive           # predict the accent (recessive verb): λύε
aegean greek sandhi κἀγώ                           # expand crasis: καί ἐγώ
aegean greek quantities πατρός                    # πα:common | τρός:heavy
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, …"     # dactylic hexameter
aegean greek ipa "λόγος" --period koine          # loɣos  (--period attic|koine)
aegean greek gloss-nt λόγος                        # Koine gloss, bundled Dodson lexicon (no download)
aegean greek gloss μῆνις --dict cunliffe           # gloss from a chosen dictionary (LSJ, Middle Liddell, Cunliffe, Abbott-Smith)
aegean greek lexica                                # list the available dictionaries
aegean greek lexicon-link λόγον                    # a Logeion deep-link (→ …/λόγος when the offline lemmatizer resolves the form, else the word as typed)
```

Real runs:

```bash
aegean greek betacode "mh=nin a)/eide qea/"
# μῆνιν ἄειδε θεά

aegean greek syllabify εἰσφέρω
# εἰσφέρω → εἰσ-φέ-ρω

aegean greek quantities πατρός
# πατρός → πα:common | τρός:heavy

aegean greek normalize "λόγoς kai" --lenient
# aegean: lenient normalize: repaired 1 Latin letter(s) in Greek words (o→ο)   [stderr]
# λόγος kai

aegean greek ipa "λόγος" --period koine
# loɣos
```

`accent` prints a small table; the Python equivalent of the same fact:

```python
from aegean import greek
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.betacode_to_unicode("mh=nin")            # 'μῆνιν'
```

### Accent placement (`accentuate`) and sandhi (`sandhi`)

`accentuate` *predicts* a word's accent from the accentuation laws (where `accent`
*reads* an existing one). `--recessive` is the rule for finite verbs, `--persistent
--lemma L` the rule for nominals (the lemma supplies the home syllable). A
*dichronon* (α/ι/υ) whose length the spelling leaves open is flagged uncertain
rather than guessed; `--lemma` or a supplied vowel length resolves it.

```bash
aegean greek accentuate λυε --recessive
# λύε	paroxytone  (uncertain: recessive; penult acute/circumflex undetermined (dichronon))

aegean greek accentuate λογος --persistent --lemma λόγος
# λόγος	paroxytone
```

`sandhi` expands a surface contraction to the underlying word(s): crasis (κἀγώ →
καί ἐγώ), elision, and the movable-ν / οὐκ alternation (οὐκ → οὐ). It is
conservative: an unlisted or ambiguous form is flagged uncertain and left intact,
never over-expanded.

```bash
aegean greek sandhi κἀγώ
# καί ἐγώ	crasis
```

Both take one or more words and `--json`.

### Scansion (`scan`)

`scan` checks a line against a fixed metrical template and prints the pattern,
the feet, and the caesura — or exits `1` with the reason if the line declines.
Synizesis is lexical, not guessed: a line that only scans via synizesis on a word
outside the curated lexicon declines rather than inventing a fit.

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

`--meter` accepts:

| name | metre |
|---|---|
| `hexameter` | dactylic hexameter (Homer): the default |
| `pentameter` | elegiac pentameter (the second line of an elegiac couplet) |
| `trimeter` | iambic trimeter (tragic/comic dialogue) |
| `glyconic` · `pherecratean` · `adonean` | aeolic cola |
| `sapphic_hendecasyllable` | the Sapphic eleven-syllable line |
| `alcaic_hendecasyllable` · `alcaic_enneasyllable` · `alcaic_decasyllable` | the Alcaic stanza lines |

`--json` adds `feet`, `syllables`, `quantities`, `caesura`, and an `ambiguous`
flag. See [Meters](Meters) for what's in scope and what isn't.

### Tagging, lemmatizing, parsing

```bash
echo "μῆνιν ἄειδε θεά" | aegean greek lemmatize -
# μῆνιν	μῆνις
# ἄειδε	ἀείδω
# θεά	θεά

aegean greek morph λόγον
# λόγος [NOUN acc sg masc]
# λόγος [NOUN acc sg fem]
# λόγος [NOUN nom sg neut]
# λόγος [NOUN acc sg neut]
# λόγος [NOUN voc sg neut]

aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."          # UPOS per token
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --json   # per-token records in one call
```

A lemma that the lexicon doesn't know is still returned, marked `(fallback)` (and
`"known": false` in JSON), so you can tell a real hit from a heuristic guess.

### Inflection synthesis (`inflect`)

`inflect` is the inverse of `lemmatize`: give it a lemma plus the features you want
and it returns the attested form(s), read off the same Perseus AGDT the analysis stack
uses. It activates inflection synthesis on first use (a note goes to stderr; the AGDT is
fetched and the inverse index built once, then it's offline). Coverage is what the corpus
attests: an unattested (lemma, features) cell returns nothing rather than a guess.

```bash
aegean greek inflect λόγος --case gen --number sg
# λόγου

aegean greek inflect λόγος --paradigm
# λόγος	case=nom number=sg gender=masc pos=NOUN
# λόγου	case=gen number=sg gender=masc pos=NOUN
# …  (every attested cell, one per line)
```

The feature flags take the analyzer's short codes: `--case` (nom/gen/dat/acc/voc/loc),
`--number` (sg/pl/du), `--gender` (masc/fem/neut), `--tense`
(pres/impf/aor/perf/plup/fut/futperf), `--voice` (act/mid/pass/mp), `--mood`
(ind/subj/opt/inf/imp/part), `--person` (1/2/3), and `--pos` (NOUN/VERB/ADJ/…). Pass
`--paradigm` to list every attested cell instead of filtering, and `--json` for the raw
forms (or the `{features, form}` cells under `--paradigm`). The same in Python:

```python
from aegean import greek
greek.use_inflector()
greek.inflect("λόγος", case="gen", number="sg")   # ('λόγου',)
greek.paradigm("λόγος")                            # ((features, form), …)
```

### Glossing

```bash
aegean greek gloss-nt λόγος
# a word, speech, divine utterance, analogy

aegean greek gloss-nt λόγος --full
# λόγος (G3056): a word, speech, divine utterance, analogy.

aegean greek gloss-nt 3056 --strongs        # look up by Strong's number
```

`gloss-nt` uses the **bundled** CC0 Dodson lexicon: no download. The classical
`gloss` command uses the larger LSJ index instead and activates it on first use
(`~270 MB`, or `~15 MB` if `lsj-index` is fetched). See the backend section below.

### Dialect and register (`usage`)

`usage` reads a word's **dialect** (Doric, Attic, Ionic, Aeolic, Epic, …) and
**register** (poetic, medical, comic, tragic, …) tags off its LSJ entry, which marks
them with standard abbreviations. It activates LSJ on first use (the same fetch as
`greek gloss`). The match is heuristic, so it surfaces the tags LSJ records without
resolving every nuance; a word with no entry or no recognised tags prints dashes:

```bash
aegean greek usage μῆνις
# μῆνις: dialects=doric, aeolic  registers=lyric
```

`--json` returns `{word, dialects, registers}` (each a list). The same in Python is
`greek.usage(word)` (after `greek.use_lsj()`), returning a `UsageInfo` with `.dialects`
and `.registers`.

### Terminology rarity (`rarity`)

`rarity` scores how unusual a text's vocabulary is **relative to a reference corpus**,
a cheap, offline translation-difficulty signal: rare, technical, or documentary terms
are where a translator (human or model) is most likely to stumble. Each content word is
scored by its lemma's frequency in the reference corpus (`absent` / `hapax` / `rare` /
`uncommon` / `common`), and the overall score is the mean. The default reference is the
Greek NT (`--corpus nt`, fetched on first use); pass `--corpus <path>` to score against
a corpus JSON of your own register instead.

```bash
aegean greek rarity "μῆνιν ἄειδε θεά" --corpus nt
# overall rarity 0.98  (vs 5395 lemmas / 137779 tokens)
#   μῆνιν	absent	1.00  (lemma μῆνις, ×0)
#   ἄειδε	absent	1.00  (lemma ἀείδω, ×0)
#   θεά	hapax	0.93  (lemma θεά, ×1)
```

`--top` sets how many of the rarest words to list; `--treebank` activates the AGDT
lemmatizer first (better lemma coverage on oblique forms); `--json` emits the overall
score, the corpus size, and the full per-word breakdown. Because the score is corpus-
relative, it is a difficulty *signal*, not a measured accuracy. The same in Python is
`greek.terminology_rarity(text, corpus)`, whose result carries `.overall` and a
`.hardest(n)` helper.

### Backend flags (download/build on first use)

Each flag stands in for a `use_*()` activation in the Python API. The first time
you use one, it may download a model or build an index to the cache (a note goes
to stderr); after that, everything is offline.

| flag | activates | first-use cost |
|---|---|---|
| `--treebank` | the Perseus AGDT lexicon | ~75 MB fetch |
| `--tagger` | the generalizing POS tagger | trains from the AGDT |
| `--lemmatizer` | the edit-tree lemmatizer | trains from the AGDT |
| `--parser` | the pure-Python arc-eager dependency parser | trains from the AGDT |
| `--neural-lemmatizer` | the GreTa seq2seq lemmatizer (`[neural]`) | ~232 MB model |
| `--neural` | the **joint neural pipeline**: best tagger/parser/lemmatizer (`[neural]`) | ~173 MB model |
| `--lsj` | LSJ glossing (also set by `greek gloss`) | ~270 MB (or ~15 MB index) |

```bash
# heavy — fetches the model on first use, then offline:
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural
aegean greek parse "ἐν ἀρχῇ ἦν ὁ λόγος" --neural          # UD dependency tree
aegean greek tag "…" --treebank --tagger                  # AGDT lookup + perceptron tagger
```

### Loading real Greek works

`work` fetches a real text from Perseus canonical-greekLit / First1KGreek
(CC BY-SA, commit-pinned, cached once) and parses it into a corpus. `works` lists
a curated, verified catalog of 25 ids; `catalog` searches the full ~1,800-work
discovery index (offline metadata); `nt-books` lists the 27 NT books and the names
the loaders accept. The full id reference is on
[Greek Works and Books](Greek-Works-and-Books).

```bash
aegean greek works
# id              author        title
# tlg0012.tlg001  Homer         Iliad
# tlg0012.tlg002  Homer         Odyssey
# tlg0011.tlg002  Sophocles     Antigone
# tlg0059.tlg030  Plato         Republic
# …  (curated subset — the full canon is at https://scaife.perseus.org)

# heavy (network on first use):
aegean greek work tlg0012.tlg001                 # the Iliad: 24 books, ~127k tokens
aegean greek work tlg0012.tlg001 --ref 1.1-1.50  # just book 1, lines 1–50
aegean greek work tlg0012.tlg001 -o iliad.json   # save as a corpus file
```

`--ref` selects a section: `1` (book), `1.2` (chapter), or `1.1-1.50` (line
range). `--source` is `auto`/`perseus`/`first1k`; `--edition` picks a specific
edition file.

**The Greek New Testament** has its own loader, `nt` (Nestle 1904, bundled, offline),
because it carries gold per-token lemma / morph / Strong's plus a Koine gloss:

```bash
aegean greek nt                          # all 27 books
aegean greek nt John --ref 1.1-1.18      # one passage (a chapter.verse range)
aegean greek nt John -o john.json        # save as a corpus (then export --level token)
```

`nt-books` lists the book names it accepts; `gloss-nt` glosses a single NT word.

**`catalog` is the full discovery index behind `works`.** Where `works` lists 25
curated highlights, `catalog` searches the **complete** bundled metadata for every
work with a Greek edition in Perseus canonical-greekLit + First1KGreek: 1,778 works
in all (768 from `perseus`, 1,010 from `first1k`). It's offline and instant: just
metadata, no fetch. Any id it prints goes straight to `aegean greek work`.

```bash
aegean greek catalog --author plato --limit 8
```
```
                       Greek works (39 matches)
┌────────────────┬────────┬────────────┬────────────────────┬─────────┐
│ id             │ author │ title      │ greek              │ src     │
├────────────────┼────────┼────────────┼────────────────────┼─────────┤
│ tlg0059.tlg001 │ Plato  │ Euthyphro  │ Εὐθύφρων           │ perseus │
│ tlg0059.tlg002 │ Plato  │ Apology    │ Ἀπολογία Σωκράτους │ perseus │
│ tlg0059.tlg003 │ Plato  │ Crito      │ Κρίτων             │ perseus │
│ tlg0059.tlg004 │ Plato  │ Phaedo     │ Φαίδων             │ perseus │
│ tlg0059.tlg005 │ Plato  │ Cratylus   │ Κρατύλος           │ perseus │
│ tlg0059.tlg006 │ Plato  │ Theaetetus │ Θεαίτητος          │ perseus │
│ tlg0059.tlg007 │ Plato  │ Sophist    │ Σοφιστής           │ perseus │
│ tlg0059.tlg008 │ Plato  │ Statesman  │ Πολιτικός          │ perseus │
└────────────────┴────────┴────────────┴────────────────────┴─────────┘

… and 31 more — narrow with --author/--title, or --limit 0 to list all (-o to save).
Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

The bare `QUERY` argument is a catch-all substring over id, author, English title,
and Greek title; `--author/-a`, `--title/-t` (matches English **or** Greek), and
`--source perseus|first1k` are the targeted filters (all case-insensitive, all
combine with AND). `--limit/-n` caps the table, the `--json` list, and what
`--output/-o` saves alike (0 = all; the JSON keeps the untruncated total in
`matched`); `-o` picks its format by extension (`.json`/`.csv`/`.txt`):

```bash
aegean greek catalog herodotus --json
```
```json
{
  "matched": 2,
  "works": [
    {
      "id": "tlg0016.tlg001",
      "author": "Herodotus",
      "title": "Histories",
      "greek_title": "Ἱστορίαι",
      "source": "perseus"
    },
    {
      "id": "tlg0062.tlg056",
      "author": "Lucian of Samosata",
      "title": "Herodotus",
      "greek_title": "Ἡρόδοτος ἢ Ἀετίων",
      "source": "perseus"
    }
  ]
}
```

```bash
aegean greek catalog --author aristophanes --source perseus -o aristophanes.csv
# wrote aristophanes.csv     (id,author,title,greek_title,source — one row per work)
```

Coverage is exactly what those open repositories hold at the pinned commit, so some
authors are genuinely absent upstream and therefore here too: `aegean greek catalog
sappho` honestly returns nothing rather than inventing an entry:

```bash
aegean greek catalog sappho
# No works match. Try a looser filter, or browse https://scaife.perseus.org
```

The same in Python is `greek.catalog(query=None, *, author=None, title=None,
source=None)`, returning a list of `{id, author, title, greek_title, source}` dicts;
`greek.popular_works()` stays the curated 25.

### Reproducing the published numbers (`eval`)

`aegean greek eval TARGET` runs the official evaluators against fetched gold data:
heavy, but it reproduces pyaegean's measured accuracy. Targets: `ud`, `proiel`,
`nt`, `tagger`, `lemmatizer`, `parser`.

```bash
# heavy: fetches gold data and the model
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval ud --neural --bootstrap          # percentile CIs over the fold's sentences
aegean greek eval proiel --drift                   # where the out-of-AGDT PROIEL gap comes from
```

`--fold` picks the UD Ancient Greek fold (`perseus` or `proiel`) and `--split` the
split (`dev` or `test`); both are validated before anything is fetched. (The old
`--treebank` spelling for the fold selector is a deprecated alias: it still works
but warns, naming `--fold`.) The measured numbers save with `--output/-o` like any
other result table.
`--bootstrap` (ud only) reports each metric as `estimate [low, high]` instead of a
single point. `--drift` (proiel only) replaces the bare accuracy numbers with a
breakdown of *where* the out-of-AGDT gap comes from: a gold→predicted POS-confusion
table plus sampled lemma mismatches, which separates systematic annotation-convention
divergence from scattered real error (`evaluate_on_proiel` itself is unchanged). The
exact figures and how they were measured are on [Greek NLP](Greek-NLP) and
[Limitations](Limitations#measured-accuracy-boundaries).

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
store. A fetched dataset is a complete one-time local download: nothing is
re-fetched, evicted, or expires; it stays on disk until `aegean data remove`
deletes it (or `fetch --force` replaces it).

```bash
aegean data list                                   # the fetchable datasets + downloaded status/size
aegean data fetch grc-joint                         # one-time download (a no-op when already present)
aegean data remove grc-joint                        # delete a downloaded dataset (--all clears everything)
aegean data versions --json > data-versions.json    # pin every dataset's sha256 for reproducibility
aegean data store                                   # store location + contents (override: PYAEGEAN_CACHE)
```

(`aegean data cache` remains a deprecated alias for `data store` this minor: it
still works but warns, naming the replacement.)

`aegean data list` shows the full registry, with a **downloaded** column giving
each present dataset's actual on-disk size. The fetchable datasets (all
downloaded on demand, never bundled):

| name | what | license |
|---|---|---|
| `agdt-derived` | prebuilt AGDT lexicon + tagger/lemmatizer/parser models | CC BY-SA 3.0 (Perseus AGDT) |
| `grc-joint` | the joint tagger-parser-lemmatizer model (~173 MB; the `[neural]` extra) | CC BY-SA 4.0 |
| `grc-lemma-neural` | the GreTa seq2seq lemmatizer (~232 MB; the `[neural]` extra) | CC BY-SA 4.0 |
| `lsj-index` | prebuilt LSJ lemma→entry index (~15 MB) | CC BY-SA 4.0 (Perseus) |
| `damos-corpus` | DAMOS Linear B corpus (~5,900 tablets): `aegean.load('damos')` | CC BY-NC-SA 4.0 |
| `sigla-corpus` | SigLA Linear A dataset (781 docs): `aegean.load('sigla')` | CC BY-NC-SA 4.0 |
| `nt-corpus` | Greek New Testament (Nestle 1904; ~137,800 tokens): `aegean.load('nt')` | CC0-1.0 |
| `lineara-images` | 3,368 facsimile/photo files (~116 MB) | academic reference only |
| `linearb-corpus` | a bring-your-own Linear B export (no default source) | per your source |
| `workbench-app` | the prebuilt workbench web app (~3 MB): served by `aegean workbench` | Apache-2.0 |

`aegean data versions --json` is the reproducibility manifest: every bundled and
fetched dataset with its sha256. See [Data & Provenance](Data-and-Provenance) for
the licensing details and why nothing non-redistributable is bundled.

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

---

## AI — `aegean ai …` (exploratory, key-gated)

The generative layer. **Every result here is exploratory**: a labeled model
hypothesis carrying its grounding evidence, never a citable fact, and never a
"decipherment." It needs a provider SDK (an extra such as
`pip install "pyaegean[anthropic]"`) and that provider's API key in your
environment. Without a key, the command exits `1` with a clear message: it never
silently calls out.

```bash
aegean ai providers
# anthropic
# gemini
# grok
# openai
# openrouter
```

The commands (each takes `--provider` / `--model`, and most take `--trace`):

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"                      # grounded hybrid translation
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --mode full          # + rare-word glosses in the grounding
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --verify             # draft, then check + repair (2nd call)
aegean ai translate "KU-RO 130" --script lineara              # exploratory (undeciphered!)
aegean ai gloss "μῆνιν ἄειδε θεά"                             # interlinear word-by-word gloss
aegean ai summarize "ἐν ἀρχῇ ἦν ὁ λόγος" --corpus nt          # short, grounded summary
aegean ai hypotheses "A-TA-I-*301-WA-JA" --corpus lineara     # cautious decipherment hypotheses
aegean ai ask "What is KU-RO?" --corpus lineara --trace       # answer strictly from grounding
aegean ai extract "OLE S 1" --fields commodity,amount         # structured JSON, ready for jq
aegean ai eval --provider anthropic                           # grounding-fidelity eval
```

`--corpus NAME` grounds the answer on that corpus's frequent words. `--trace`
prints the grounding provenance under the answer: the local corpus / lexicon /
analysis facts the model was given, grouped by source, so you can audit exactly
what it was (and wasn't) told. `extract` always prints JSON, so it pipes straight
into `jq`. For Greek, `translate` grounds with deterministic **morphology** by default
(`--mode morphology`): lemma, part of speech, voice, case roles, and the clause skeleton,
with rare words flagged but no auto-selected dictionary senses. `--mode full` adds concise,
rarity-gated glosses (a common-sense-first dictionary cascade, best on rare or documentary
vocabulary); `--mode lemma` is the legacy lemma+LSJ grounding, and `--mode none` sends the
text ungrounded. `--verify` translates raw first, then checks and repairs the draft against
the analysis (a second model call: the analysis cannot bias the draft, though a wrong
analysis can still mislead the repair).

**Save the output, label and all.** `translate`, `gloss`, `summarize`, `hypotheses`,
`ask`, and `extract` take `--output/-o`. A `.json` file carries the text plus its provenance
and grounding evidence; a `.txt` file is the labeled text. The exploratory label
stays attached on disk: a saved result never loses the "this is a hypothesis, not
a finding" framing. (`ai eval` takes `--output/-o` too, saving its case table as
`.json`, `.csv`, or `.txt`.)

```bash
aegean ai gloss "μῆνιν ἄειδε θεά" -o gloss.json        # text + provenance + grounding
aegean ai ask "What is KU-RO?" --corpus lineara -o answer.txt
```

In Python the same lives on `ExploratoryResult`: `.to_dict()`, `.to_json(path)`,
and `ExploratoryResult.from_dict(data)` round-trip a result through disk with its
label and grounding intact. The full design and the meaning of "grounded" are on
[AI Layer](AI-Layer); the hard limits are on [Limitations](Limitations).

---

## MCP server — `aegean-mcp`

A separate console script (the `[mcp]` extra) that exposes the toolkit to AI
agents (Claude Code and other MCP clients) over stdio, so an agent can use
pyaegean without writing Python.

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

## Recipes

Reconcile every Linear A account and keep only the failures:

```bash
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json
```

Lemmatize a file of Greek, one lemma per line:

```bash
cat chapter.txt | aegean greek lemmatize - --json | jq -r '.[].lemma'
```

Scan a poem line by line, keeping only the lines that scan:

```bash
while read -r line; do aegean greek scan "$line" --json 2>/dev/null | jq -r .pattern; done < poem.txt
```

Map a word's distribution and cite the subset you used:

```bash
aegean geo lineara --output sites.geojson
aegean cite lineara --site "Zakros" --style bibtex >> paper.bib
```

Build one searchable database of all of Homer straight from work ids, then keep
growing it: no Python anywhere:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db     # Iliad + Odyssey (see Greek Works and Books for ids)
aegean db add tlg0011.tlg002 -o homer.db                     # add Sophocles' Antigone later
aegean db search homer.db μῆνιν --limit 3
```

Save a query subset once, reuse it everywhere:

```bash
aegean query lineara --where "site-is=Zakros" -o zakros.json
aegean keyness zakros.json --reference lineara --top 5 -o zakros-keyness.csv
```

More worked pipelines are on [Recipes](Recipes).

---

## Notes and limits

- **The AI layer is exploratory.** Translations, glosses, and "hypotheses" for
  undeciphered material are labeled model output with grounding, not findings. The
  Aegean scripts remain undeciphered. See [Limitations](Limitations).
- **Heavy commands download on first use.** Anything marked heavy here
  (`--neural`, `greek work`, `greek eval`, `gloss`, the fetched corpora) pulls
  data to the cache the first time, with a note on stderr; afterwards it's offline.
  Pre-fetch with `aegean data fetch` before going offline.
- **`--json` is the contract; the table view is for humans.** Don't parse the
  rich tables: pass `--json` and use `jq`. `--limit`/`--top` cap the JSON lists
  too (`0` lifts the cap); where a payload carries totals (`matched`), they stay
  untruncated.
- **Metre and accuracy are bounded.** Lyric metres beyond the fixed aeolic
  templates are out of scope, and the trainable backends have measured ceilings:
  both documented on [Meters](Meters) and
  [Limitations](Limitations#measured-accuracy-boundaries).

For the terse one-page index of every command and flag, see the
[CLI Cheatsheet](CLI-Cheatsheet).
