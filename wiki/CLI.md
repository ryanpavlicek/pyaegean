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

> **Available in v0.45.0.** The CoNLL-U commands and the long-input,
> source-alignment, and analysis-receipt fields shown below are part of the
> current release.

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

## How to read a command

Every `--help` screen (and every example on this page) describes commands in the
same compact notation. Here is one real usage line, exactly as
`aegean stats --help` prints it, decoded piece by piece:

```text
Usage: aegean stats [OPTIONS] CORPUS
```

- **`aegean stats`** is the command itself: the program (`aegean`), then the
  command (`stats`). Grouped commands add one more word: `aegean greek scan`.
- **`CORPUS`** (capitals, no dashes) is an **argument**: a value you supply in
  that position, with nothing in front of it. Here it is the corpus to analyse,
  so the simplest complete command is `aegean stats lineara`. An argument in
  square brackets is optional: `aegean balance [OPTIONS] CORPUS [DOC_ID]` means
  the document id may be given (check one tablet) or left off (sweep the whole
  corpus).
- **`[OPTIONS]`** stands for the command's **options** (also called flags):
  named switches that start with dashes and can go in any order. An option
  either takes a value after it (`--top 5`) or is a plain on/off switch
  (`--signs`). `aegean stats --help` lists them all with one-line descriptions.
- **Short and long spellings.** Some options have a one-letter short form:
  `-o` is the same option as `--output`, `-f` the same as `--format`. This page
  usually writes the long form because it is self-describing; type whichever
  you prefer.

Put together, this command:

```bash
aegean stats lineara --signs --top 5
```

reads as: run `stats` on the corpus `lineara`, count individual signs rather
than whole words, and show the top five rows.

**Quoting.** Wrap anything containing a space, an asterisk, or punctuation in
double quotes: `aegean search lineara "KU-*-RO"`,
`aegean load lineara --site "Haghia Triada"`. Double quotes work in every shell
pyaegean runs in (Windows PowerShell, cmd, macOS/Linux bash and zsh). A single
Greek word needs no quotes (`aegean greek syllabify εἰσφέρω`),
but quoting never hurts, and a multi-word line always needs it:
`aegean greek scan "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"`. On macOS/Linux single
quotes work too; in PowerShell prefer double quotes so the text passes through
unchanged.

## The command map

```bash
aegean --version          # pyaegean 0.45.0
```

| Group | What's in it |
|---|---|
| **(top level)** | `quickstart` `repl` `tui` `info` `load` `show` `search` `query` `stats` `dispersion` `keyness` `cache` `doctor` `balance` `cite` `export` `combine` `import` `geo` `sign` `bridge` `plot` `workbench` |
| **`aegean greek …`** | normalize → `betacode` → `strip` → tokenize → syllabify → accent → `accentuate` → `sandhi` → `quantities` → scan → `ipa` → `profile` → tag → lemmatize → morph → `inflect` → parse, plus `pipeline`, `gloss`/`gloss-nt`/`usage`/`lexica`/`lexicon-link`, `rarity`, `missing-forms`, `conllu inspect`/`export`, `work`/`nt`/`works`/`catalog`/`nt-books`, and `eval` |
| **`aegean analyze …`** | `distance` `align` `compare` `nearest` `assoc` `cooccur` `clusters` `structure` `hands` `hand` `dossiers` `syllabary` `bridge` |
| **`aegean data …`** | `list` `fetch` `remove` `versions` `store` |
| **`aegean db …`** | `build` `add` `search` (SQLite + FTS5) |
| **`aegean review …`** | `export` `merge` `apply` (the human-in-the-loop annotation round-trip, including multi-reviewer agreement) |
| **`aegean ai …`** | `providers` `translate` `gloss` `summarize` `hypotheses` `ask` `extract` `eval` (exploratory, key-gated) |
| **`aegean-mcp`** | a separate console script: serve the tools to AI agents over MCP |

---

## Common tasks

One goal, one command, and what comes back. Every command here was run as
shown; longer outputs are abridged with `…`. Commands marked *(downloads on
first use)* fetch their data once and are offline after that.

**See what is in a corpus** (size, source, license, the ready-to-paste citation):

```bash
aegean info edh
# a small table: 1286 documents, 26937 words, the EDH source line,
# the CC-BY-SA-4.0 license, and the citation
```

**Read one Linear A tablet**, line by line:

```bash
aegean show lineara HT13
# HT13  site=Haghia Triada  period=LMIB  scribe=HT Scribe 8  support=Tablet
#   1: KA-U-DE-TA VIN 𐄁 TE 𐄁
#   2: RE-ZA 5 ¹⁄₂
#   …
```

**Read a chapter of the Greek New Testament** (John 1 is bundled, so this works
offline from install):

```bash
aegean greek nt John 1
# John 1  (1 chapter, 828 tokens)
# John 1
#   1: Ἐν ἀρχῇ ἦν ὁ Λόγος, καὶ ὁ Λόγος ἦν πρὸς τὸν Θεόν, καὶ Θεὸς ἦν ὁ Λόγος.
#   …
```

**Read the Iliad, one book at a time** *(downloads on first use)*:

```bash
aegean show tlg0012.tlg001 1
# tlg0012.tlg001:1
#   1: μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος
#   2: οὐλομένην , ἣ μυρίʼ Ἀχαιοῖς ἄλγεʼ ἔθηκε ,
#   …
```

**Count the commonest words in a corpus** *(nt downloads on first use)*:

```bash
aegean stats nt --top 3
# a two-column table: καὶ 8541 · ὁ 2768 · ἐν 2683
```

**Find a word anywhere in 57,000 documentary papyri** *(the DDbDP database
downloads once, ~219 MB)*:

```bash
aegean db search ddbdp "βασιλέως" --limit 3
# a doc/pos/text table: apf.59.84_2 · bgu.10.1910 · bgu.10.1957, each
# holding βασιλέως at the given token position
```

**List the documents that contain a given word**:

```bash
aegean query nt --where "ins-contains-word=ἀγάπη" --limit 3
# Contains exact word: ἀγάπη → 20 inscription(s)
# a table starting Matt 24 · John 17 · Rom 5, then the exact-subset citation
```

**Map where a word was found** (case does not matter):

```bash
aegean geo lineara --word a-du
# lineara: 'a-du' attested at 3 located site(s)
# a site/lat/lon/count table: Haghia Triada ×7, Khania ×2, Tylissos ×1
```

**Check whether a tablet's arithmetic adds up**:

```bash
aegean balance lineara HT9a
# one row: HT9a  KU-RO  stated 31.75  computed 31.0  diff -0.75  balances NO
```

**Read a Linear B word as Greek**:

```bash
aegean bridge linearb qa-si-re-u
# qa-si-re-u → βασιλεύς   (chief, local leader (later: king))
```

**Split a Greek word into syllables**:

```bash
aegean greek syllabify ἄνθρωπος
# ἄνθρωπος → ἄν-θρω-πος
```

**Scan a line of Homer**:

```bash
aegean greek scan "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"
# —⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, spondee, dactyl, dactyl, final; caesura: penthemimeral
```

**Reconstruct a pronunciation** (Attic or Koine):

```bash
aegean greek ipa "Χριστός" --period koine
# xristos
```

**Type Greek without a Greek keyboard** (Beta Code in, polytonic Greek out):

```bash
aegean greek betacode "lo/gos"
# λόγος
```

**Look up an NT word's meaning** (bundled lexicon, no download):

```bash
aegean greek gloss-nt ἀγάπη
# love
```

**Lemmatize a clause**:

```bash
echo "ἐν ἀρχῇ ἦν ὁ λόγος" | aegean greek lemmatize -
# ἐν      ἐν
# ἀρχῇ    ἀρχή
# ἦν      εἰμί
# …
```

**Cite exactly what you used**:

```bash
aegean cite nt
# Nestle, E. (1904). Novum Testamentum Graece (Nestle 1904). Morphology/lemmatization (CC0) via biblicalhumanities/Nestle1904. — https://github.com/biblicalhumanities/Nestle1904
```

**Check the install when something seems off**:

```bash
aegean doctor
# five tables (versions, extras, data store, models, analysis cache), then:
# doctor: all checks passed
```

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
  aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (cypriot, cyprominoan, damos, ddbdp, edh, greek, igcyr, iip, iospe, isicily, lineara, linearb, nt, sigla), a Greek work id like tlg0012.tlg001, or a path to a .json or .db corpus
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

### A worked session

A short, realistic sitting: set a session corpus, read a tablet, run two
analyses on it, ask a Greek question, and leave. The outputs below are from a
real scripted run (the shell reads one command per line when its input is
piped); the `aegean>` prompt lines are added for readability, since a piped
session does not echo them. In an interactive terminal the shell first greets
you with a banner and the full command map (the same map bare `aegean`
prints), not shown here.

```text
$ aegean repl
aegean> use lineara
aegean: session corpus: lineara — corpus-first commands (show, stats, search, …) now default to it; 'use off' clears.
aegean> show HT13
HT13  site=Haghia Triada  period=LMIB  scribe=HT Scribe 8  support=Tablet
  1: KA-U-DE-TA VIN 𐄁 TE 𐄁
  2: RE-ZA 5 ¹⁄₂
  …
  8: KU-RO 130 ¹⁄₂
aegean> stats --top 3
  lineara: top 3
      words
┌────────┬───────┐
│ item   │ count │
├────────┼───────┤
│ KU-RO  │ 37    │
│ SA-RA₂ │ 20    │
│ KI-RO  │ 16    │
└────────┴───────┘
aegean> search "KU-*-RO"
'KU-*-RO': 1 word(s)
┌──────────┬───────┐
│ word     │ count │
├──────────┼───────┤
│ KU-MA-RO │ 1     │
└──────────┴───────┘
aegean> greek syllabify Ποσειδῶνι
Ποσειδῶνι → Πο-σει-δῶ-νι
aegean> use off
aegean: session corpus cleared.
aegean> :examples
  info lineara                      corpus overview: size, provenance, license
  show lineara HT13                 one document, metadata and line-by-line tokens
  …  (thirteen starter lines in all)
aegean> :exit
```

Note what the session corpus did: after `use lineara`, `show HT13`,
`stats --top 3`, and `search "KU-*-RO"` all ran against Linear A with no corpus
argument, while `greek syllabify` (not a corpus command) was untouched by it.

---

## The terminal UI (`aegean tui`)

> Full reference: the [TUI](TUI) page. This section is a quick tour.

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

Six screens, switched with a single key from anywhere:

| Screen | Key | What it shows |
|---|---|---|
| **Home** | `h` | The landing view: the thirteen corpora at a glance, the global-key legend, and the permanent undeciphered-script honesty banner. |
| **Corpus browser** | `c` | Three panes: the corpus list → a filterable document table (search by id, or by sign pattern like `KU-*-RO`) → an apparatus-aware document detail with its accounting reconciliation (`KU-RO` / `to-so` balance) and structure classification inline. |
| **Greek workbench** | `g` | A text box over live tabs that re-render as you type: the full pipeline (lemma / POS / morphology), metrical scansion (with a hexameter / pentameter / trimeter selector), syllabification, and reconstructed IPA. All zero-dependency and instant. |
| **Data store** | `d` | The `aegean doctor` environment report and the `aegean data list` table in one place: versions, extras, the data store, and the fetchable datasets, with a per-dataset Fetch action that downloads on a background worker with a progress bar. |
| **Works library** | `w` | Search the ~1,800-work Greek catalogue, fetch a work (or a whole author) on a background worker, open or delete downloaded works. |
| **Command console** | `:` | A shell-style `aegean>` prompt that runs any CLI command inside the TUI, with ghost-text completion and history. |

The other global keys work on every screen: `q` quits, `?` opens the help overlay,
`t` opens the live-preview theme picker, `Esc` goes back a screen (blurring a
focused input first), and **`ctrl+p`** opens the command palette, a fuzzy-searchable
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

The TUI covers the highest-value offline areas (browse and analyze a document,
the works library, the command console, the Greek workbench, and the data store),
which is a deliberate scope: it is a
research cockpit for the reads you do most, **not a mirror of every command**. The
full query engine, keyness/dispersion, plots, export/import, geo maps, `db build`,
the eval reproductions, and the exploratory AI layer stay on the regular command
line (and in `aegean repl`); the command console (`:`) can run any of them from
inside the TUI, but they have no dedicated screens. On Windows the
Aegean glyph columns render best with the free Noto Sans Aegean fonts from
[Installation → Set up your terminal](Installation#set-up-your-terminal); run the
TUI with `PYTHONUTF8=1` so Greek and Linear A display correctly.

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
matched subset). Word-scope fields such as `word-prefix` only bite in this
mode:

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
On `main`, typed form states add canonical `form_diplomatic`,
`form_regularized`, `form_normalized`, `form_model_input`,
`form_model_input_ops`, `form_model_input_source`, `form_segments`, editorial
status, damage, and uncertainty columns. `form_segments` is JSON in the table;
tokens without a state have empty or null values. Filters (`--site` etc.) apply
before export.

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
spreadsheet:

```bash
aegean export nt -f csv --level token -o nt-tokens.csv   # wrote 260 documents to nt-tokens.csv (csv)
head -2 nt-tokens.csv
# lemma,morph,strongs,normalized,upos,ref,gloss,form_diplomatic,form_regularized,form_normalized,form_model_input,doc_id,line_no,position,text,kind,site,period
# βίβλος,N-NSF,976,Βίβλος,NOUN,Matt.1.1,"a written book, roll, or volume",Matt 1,1,0,Βίβλος,word,,Koine
```

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
│ OK │ pyaegean │ 0.45.0                    │
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
aegean greek gloss μῆνις --dict cunliffe           # gloss from a chosen dictionary (LSJ, Middle Liddell, Cunliffe, Autenrieth, Abbott-Smith)
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
aegean greek explain "ἐν ἀρχῇ ἦν ὁ λόγος."           # what each stage did, in plain language
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

# manage what you have downloaded:
aegean greek works --downloaded                  # list the works in your cache
aegean greek works --remove tlg0012.tlg001       # delete one downloaded work
aegean greek works --remove-author homer         # delete every downloaded Homer work
aegean greek works --remove-all                  # clear the whole downloaded library
```

#### The whole lifecycle, worked

Find a work, fetch it, confirm it is on disk, delete it. Every step below ran
as shown (the fetch touches the network once; everything after is local).

Find the id (`catalog` is offline metadata, instant):

```bash
aegean greek catalog --title crito
```
```
                Greek works (1 match)
┌────────────────┬────────┬───────┬────────┬─────────┐
│ id             │ author │ title │ greek  │ src     │
├────────────────┼────────┼───────┼────────┼─────────┤
│ tlg0059.tlg003 │ Plato  │ Crito │ Κρίτων │ perseus │
└────────────────┴────────┴───────┴────────┴─────────┘
Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

Fetch it (downloads once, then it is cached):

```bash
aegean greek work tlg0059.tlg003
```
```
                                tlg0059.tlg003
┌──────────────┬──────────────────────────────────────────────────────────────┐
│ field        │ value                                                        │
├──────────────┼──────────────────────────────────────────────────────────────┤
│ documents    │ 12                                                           │
│ tokens       │ 4635                                                         │
│ first        │ tlg0059.tlg003:43                                            │
│ name         │ Κρίτων — section 43                                          │
│ source       │ PerseusDL/canonical-greekLit                                 │
│              │ (tlg0059.tlg003.perseus-grc2.xml)                            │
│ data_version │ PerseusDL/canonical-greekLit@d4fab69a2c26                    │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

Confirm it is in the downloaded library (its row of the table):

```bash
aegean greek works --downloaded
# │ tlg0059.tlg003 │ Plato              │ Crito             │ perseus │ 64 KB   │
```

Read it like any corpus (`aegean show tlg0059.tlg003 43`, `aegean stats
tlg0059.tlg003`), and when you are done with it:

```bash
aegean greek works --remove tlg0059.tlg003
# removed tlg0059.tlg003  (Plato — Crito)
#
# removed 1 work from the cache.
```

`--ref` selects a section by the work's **declared citation scheme**: `1` (a book,
or a Stephanus section), `1.2` (a chapter), or `1.1-1.50` (a line range). The scheme is
read from the edition's TEI structure and varies by genre — verse is `book.line`, a
Stephanus-paged Plato dialogue is a single `section`, Aristotle is `chapter.subchapter`,
multi-book prose is `book.chapter.section` — so a **wrong `--ref` names the work's own
scheme** (e.g. `cited by book.line`) instead of only reporting a miss. A hyphen range must
stay within one textpart; for sibling sections, or a range that would cross textparts, use
a **comma list** (`--ref 1.1,1.5` or `--ref 1,3`), one document per entry. `--ref` also
addresses **margin milestones outside the `<div>` scheme** — a Stephanus sub-page (`17a`)
or a Bekker line (`1447a10`) an edition prints in the margin — by extracting the span
between that marker and the next marker of its kind. Perseus marks only every fifth Bekker
line, so `1447a10` returns lines 10-14 and only marked line numbers resolve; a whole Bekker
page-*column* works too (`1447a` = column `a`, the whole page being the comma list
`1447a,1447b`), as does `17a,17b`. A hyphen **range** of milestones is not yet supported
(use a comma list of the markers). To discover the
scheme before loading, call `greek.citation_scheme("tlg0012.tlg001")` (it returns the
ordered levels, e.g. `["book", "line"]`); the per-genre table is on
[Greek Works and Books](Greek-Works-and-Books#citation-schemes-how-a-work-is-addressed).
`--source` is `auto`/`perseus`/`first1k`; `--edition` picks a specific edition file.

**The Greek New Testament** has its own loader, `nt` (Nestle 1904; fetched on
first use, with a bundled John 1 + Philemon sample for offline use),
because it carries gold per-token lemma / morph / Strong's plus a Koine gloss:

```bash
aegean greek nt                          # all 27 books
aegean greek nt John --ref 1.1-1.18      # one passage (a chapter.verse range)
aegean greek nt John 1                   # a chapter, positional (same as --ref 1)
aegean greek nt Matt 1-3                 # a chapter range (also: aegean show nt "Matt 1-3")
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

### Inspecting and preserving CoNLL-U files

The `conllu` group reads complete treebank documents without running a model. `inspect`
reports syntactic words, multiword ranges, empty nodes, enhanced-annotation presence,
and the explicit original-ID projection. Add `--strict` to reject malformed columns,
identifiers, row placement, references, and basic trees. `--json` or `-o` gives the
machine-readable summary.

```bash
aegean greek conllu inspect treebank.conllu --strict --json
aegean greek conllu export treebank.conllu -o checked-copy.conllu --strict
```

`export` copies the source bytes atomically, including comments, all ten columns, MWT
ranges, empty nodes, `DEPS`, `MISC`, and line endings. It never invokes the baseline or
neural pipeline. The separate `greek eval ud` path still predicts and scores only the
integer-ID syntactic-word projection, so gold structural annotations are not credited to
the model. A typed editorial form on a word row is encoded in the reserved
`AegeanFormState` MISC entry as URL-safe base64 JSON (schema 1); strict inspection
rejects malformed, duplicate, unknown-schema, or oversized entries, while lenient
inspection preserves the raw MISC value without decoding it.

### Reproducing the published numbers (`eval`)

`aegean greek eval TARGET` runs the official evaluators against fetched gold data:
heavy, but it reproduces pyaegean's measured accuracy. Targets: `ud`, `proiel`,
`nt`, `tagger`, `lemmatizer`, `parser`.

```bash
# heavy: fetches gold data and the model
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval ud --neural --bootstrap          # percentile CIs over the fold's sentences
aegean greek eval ud --drift                       # error analysis: POS confusions, per-POS accuracy
aegean greek eval proiel --drift                   # the same, for the out-of-AGDT PROIEL gold
aegean greek eval nt --drift                       # the same, for the Nestle 1904 New Testament
aegean greek eval ud --by-genre --neural           # score the fold sliced by literary genre
```

`--fold` picks the UD Ancient Greek fold (`perseus` or `proiel`) and `--split` the
split (`dev` or `test`); both are validated before anything is fetched. (The old
`--treebank` spelling for the fold selector is a deprecated alias: it still works
but warns, naming `--fold`.) The measured numbers save with `--output/-o` like any
other result table.
`--bootstrap` (ud only) reports each metric as `estimate [low, high]` instead of a
single point. `--drift` (ud, proiel, or nt) replaces the bare accuracy numbers with an
error analysis: a gold→predicted POS-confusion table, per-part-of-speech accuracy, the
common lemma confusions, and a seen-vs-unseen split, which separates systematic
annotation-convention divergence from scattered real error (the aggregate `evaluate_*`
numbers are unchanged). See [When the Tool Is Wrong](When-the-Tool-Is-Wrong) for how to
read the breakdown. `--by-genre` (ud only) buckets the fold by its `sent_id` author into
literary genres (epic, tragedy, prose) and scores each bucket separately. Note that the
leakage-clean Perseus test fold is prose-only, so today this returns a single `prose`
bucket; the machinery is in place for a future held-out epic/tragedy slice (see
[Benchmarks](Benchmarks)). `--batch-size N` (ud, nt, and `--by-genre`) runs the neural
model over N sentences per call: identical results, several times faster; it is
rejected where no batched loop exists (`proiel`, `--bootstrap`, `--drift`). The exact
figures and how they were measured are on
[Greek NLP](Greek-NLP) and [Limitations](Limitations#measured-accuracy-boundaries).

#### A worked run

The lightest useful combination: the pure-Python tagger (prebuilt models fetch
once with `agdt-derived`; here already cached, so the whole run took about two
seconds) on the Perseus **dev** split. Real output:

```bash
aegean greek eval ud --fold perseus --split dev --tagger
# aegean: activating the POS tagger (first use may download/build)…   [stderr]
```
```
              eval: ud
┌─────────────┬────────────────────┐
│ metric      │ value              │
├─────────────┼────────────────────┤
│ treebank    │ perseus            │
│ split       │ dev                │
│ parsed      │ False              │
│ upos        │ 0.8262480234922069 │
│ xpos        │ 0.0                │
│ ufeats      │ 0.36638807318726   │
│ lemma       │ 0.6045629094194714 │
│ uas         │ None               │
│ las         │ None               │
│ clas        │ None               │
│ n_words     │ 22135              │
│ n_sentences │ 1137               │
└─────────────┴────────────────────┘
```

How to read it: the backend flag decides which stack is scored, and only the
stages that ran are meaningful. With just `--tagger` no parser was activated,
so `parsed` is `False` and `uas`/`las`/`clas` read `None`; swap in `--neural`
and the same table fills in the dependency metrics (and takes much longer, as
the model fetches and then runs on every sentence). These dev-split numbers
are a working check, not the published figures: the published (test-split)
results and their protocol live in `docs/benchmarks.md` and on
[Greek NLP](Greek-NLP).

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
aegean data fetch damos                             # the DAMOS Linear B corpus (a stem: = damos-corpus)
aegean data remove grc-joint                        # delete a downloaded dataset (--all clears everything)
aegean data versions --json > data-versions.json    # pin every dataset's sha256 for reproducibility
aegean data store                                   # store location + contents (override: PYAEGEAN_CACHE)
```

For a **Linear B corpus**, fetch **DAMOS** directly (`aegean data fetch damos`, ~5,900 tablets,
CC BY-NC-SA 4.0). **LiBER** (liber.cnr.it) is browse-only: it has no public download or API and is
rights-restricted, so it cannot be fetched. To use your own licensed Linear B export, import it
(`aegean import x.xml --epidoc --script linearb`) or set `PYAEGEAN_LINEARB_CORPUS_URL`.

(`aegean data cache` remains a deprecated alias for `data store` this minor: it
still works but warns, naming the replacement.)

### A worked round trip

Delete and re-download a dataset, watching the store at each step (run here on
the NT corpus; the fetch is the one networked step). `remove` frees the space
and says how much; `list` flips its **downloaded** column; `fetch` prints the
destination path (plus a "load it" hint on stderr), and re-running a fetch of
something already present is a no-op:

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

`aegean data list` shows the full live registry (currently 28 entries), with a **downloaded** column giving
each present dataset's actual on-disk size. The fetchable datasets (all
downloaded on demand, never bundled):

The table below lists the common runtime and corpus assets. The live command is
authoritative and also shows evaluation folds and supporting indexes used by the
benchmark commands.

| name | what | license |
|---|---|---|
| `agdt-derived` | prebuilt AGDT lexicon + tagger/lemmatizer/parser models | CC BY-SA 3.0 (Perseus AGDT) |
| `grc-joint` | the joint tagger-parser-lemmatizer model (~173 MB; the `[neural]` extra) | CC BY-SA 4.0 |
| `grc-lemma-neural` | the GreTa seq2seq lemmatizer (~232 MB; the `[neural]` extra) | CC BY-SA 4.0 |
| `lsj-index` | prebuilt LSJ lemma→entry index (~15 MB) | CC BY-SA 4.0 (Perseus) |
| `middle-liddell-index` | prebuilt Middle Liddell lemma→entry index (~2.3 MB) | public domain (1889) |
| `cunliffe-index` | prebuilt Cunliffe (Homeric) lemma→entry index (~1.3 MB) | public domain (1924) |
| `autenrieth-index` | prebuilt Autenrieth (Homeric) lemma→entry index | public domain (1891) |
| `abbott-smith-index` | prebuilt Abbott-Smith (NT) lemma→entry index (~130 KB) | public domain (1922) |
| `grc-paradigms` | Ancient Greek inflection paradigms used by `greek.inflect` | CC BY-SA 4.0 (derived) |
| `damos-corpus` | DAMOS Linear B corpus (~5,900 tablets): `aegean.load('damos')` | CC BY-NC-SA 4.0 |
| `sigla-corpus` | SigLA Linear A dataset (802 docs): `aegean.load('sigla')` | CC BY-NC-SA 4.0 |
| `nt-corpus` | Greek New Testament (Nestle 1904; ~137,800 tokens): `aegean.load('nt')` | CC0-1.0 |
| `isicily-corpus` | I.Sicily Greek inscriptions (2,855 texts): `aegean.load('isicily')` | CC BY 4.0 |
| `iip-corpus` | IIP Greek inscriptions of Israel/Palestine (2,113 texts): `aegean.load('iip')` | CC BY-NC 4.0 |
| `iospe-corpus` | IOSPE Greek inscriptions of the Northern Black Sea (1,194 texts): `aegean.load('iospe')` | CC BY 4.0 |
| `igcyr-corpus` | IGCyr/GVCyr Greek inscriptions of Cyrenaica (997 texts): `aegean.load('igcyr')` | CC BY-NC-SA 4.0 |
| `edh-corpus` | EDH Greek inscriptions (1,286 texts, frozen 2021 dump): `aegean.load('edh')` | CC BY-SA 4.0 |
| `ddbdp-corpus` | DDbDP documentary papyri as SQLite + FTS (57,331 texts, ~219 MB): `aegean db search ddbdp` | CC BY 3.0 |
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

## Review — `aegean review …`

The review commands close the loop between machine analysis and human judgement: export
the toolkit's annotations to a spreadsheet, correct them, and read the corrections back.
Automation does not end the workflow; this is how a scholar keeps the final say and a
record of it.

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `review export` | Write one reviewable CSV row per word: the machine lemma / POS / morphology, its evidence class, a `needs_review` flag, and blank correction columns | `-o/--output` (a `.csv`) `--only-needs-review` `--annotate` (+ `--neural`/`--tagger`/… to fill a corpus that has no annotations yet) | `aegean review export nt -o review.csv` |
| `review merge` | Combine two or more corrected copies of the same export; agreed or single-reviewer corrections are kept, while genuine disagreements are reported or rejected | `--corpus/-c` `-o/--output` `--on-conflict error\|report` `--json` | `aegean review merge alice.csv bob.csv -c nt -o merged.csv --on-conflict report` |
| `review apply` | Read a reviewed CSV back onto the corpus and save the corrected result, keeping each machine value under `<field>__pred` and stamping the reviewer | `-o/--output` (a `.json`/`.db`) `--reviewer NAME` `--annotate` (+ backend flags — repeat whatever the export used, so accepted predictions persist too) | `aegean review apply nt review.csv -o nt-fixed.json --reviewer "A. Scholar"` |

```bash
# 1. export a reviewable table (the NT already carries gold annotations; for your own
#    imported text add --annotate to fill lemma/POS from the pipeline first)
aegean review export nt -o review.csv
#    wrote 137779 review rows to review.csv     (illustrative count)

# 2. open review.csv in a spreadsheet, fill correct_lemma / correct_pos / correct_morph /
#    reviewer_note on the rows you want to change (the needs_review column flags the shaky ones;
#    --only-needs-review exports just those). If several people review copies of the same export,
#    merge them first:
aegean review merge alice.csv bob.csv -c nt -o merged.csv --on-conflict report

aegean review apply nt merged.csv -o nt-reviewed.json --reviewer "Review team"
#    wrote nt-reviewed.json  (review: 12 tokens corrected by Review team (2026-…))
```

The join is by document id and token position, and each row's exported token text is
verified against the corpus on apply: a mismatch (a different corpus, or one that changed
since the export) is an error, never a silent wrong-word correction. When the export used
`--annotate`, pass `--annotate` (and the same backend flags) to `apply` too, so the accepted
machine predictions land in the corrected corpus alongside the reviewer's changes — the
export's printed next-step command includes it. See
[When the Tool Is Wrong](When-the-Tool-Is-Wrong) for the review workflow in context and
[Data & Provenance](Data-and-Provenance) for the table columns.

Review exports also include guarded `form_*` columns and `form_state_json` when
typed editorial forms are present. Applying a correction refuses a row whose
form state no longer matches the exported corpus. Review files written before
these columns remain readable and use the existing identity and token-text checks.

---

## AI — `aegean ai …` (exploratory, key-gated)

The generative layer. **Every result here is exploratory**: a labeled model
hypothesis carrying its grounding evidence, never a citable fact, and never a
"decipherment." It needs a provider SDK (an extra such as
`pip install "pyaegean[anthropic]"`) and, for a hosted provider, that provider's
API key in your environment; the `local` provider instead points at a running local
server (Ollama, LM Studio, llama.cpp) and needs no key. Without a key, a
hosted-provider command exits `1` with a clear message: it never
silently calls out.

```bash
aegean ai providers
# anthropic
# gemini
# grok
# local
# openai
# openrouter
```

The commands (each takes `--provider` / `--model`, and most take `--trace`):

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"                      # grounded hybrid translation
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --mode full          # + rare-word glosses in the grounding
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --greek-backend neural --verify --trace
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
rarity-gated glosses from the available dictionary cascade; `--mode lemma` is the
legacy lemma+LSJ grounding, and `--mode none` sends the
text ungrounded. `--verify` translates raw first, then checks and repairs the draft against
the analysis (a second model call: the analysis cannot bias the draft, though a wrong
analysis can still mislead the repair).

`--greek-backend default|baseline|neural` makes the Greek analysis owner explicit.
`default` preserves the module-level facade, `baseline` creates an isolated
zero-dependency analyzer, and `neural` creates an isolated joint-model analyzer for that
run. The choice and exact configuration appear in `--trace` and JSON provenance, but not
in the provider prompt. `--grounding-failure best-effort|strict` controls required local
analysis failures: best-effort keeps available evidence and records the degradation;
strict stops before any provider call. Optional dictionaries and rarity data remain
optional. Because morphology/full request a dependency analysis, an isolated baseline is
normally paired with best-effort; use neural for a strict morphology/parse contract.

#### Worked runs (provider-dependent)

Three real runs, `--provider openrouter` with its default model. **Generative
output varies** run to run and model to model, so read the wording as
illustrative of the shape, never as expected output. The default `--provider`
is `anthropic`; each provider reads its own key from the environment, and
without one the command stops on one line rather than silently calling out:

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"
# aegean: no API key for 'anthropic'; set $ANTHROPIC_API_KEY or pass api_key=   [stderr, exit 1]
```

The default grounding (`--mode morphology`) attaches the local analysis and
flags ambiguities; the answer arrives labeled at both ends:

```text
$ aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --provider openrouter
[EXPLORATORY · translate · openrouter/openai/gpt-4o-mini]
Translation: "In the beginning was the Word."

Note: The phrase "ἐν ἀρχῇ" is commonly translated as "In the beginning," …
…a short discussion of the ambiguity of λόγος follows…
exploratory · openrouter:openai/gpt-4o-mini · grounded on 5 item(s) (--trace to audit them)
```

`--mode full` adds rarity-gated dictionary glosses to that grounding (most
useful on rare or documentary vocabulary):

```text
$ aegean ai translate "μῆνιν ἄειδε θεά" --provider openrouter --mode full
[EXPLORATORY · translate · openrouter/openai/gpt-4o-mini]
Translation: "Sing of the wrath, O goddess."

Notes on Ambiguities:
1. **μῆνιν**: Typically translated as "wrath," …
```

`--verify` drafts first, then checks and repairs the draft against the
analysis in a second call; the surviving text is what prints:

```text
$ aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --provider openrouter --verify
[EXPLORATORY · translate · openrouter/openai/gpt-4o-mini]
"In the beginning was the Word."
exploratory · openrouter:openai/gpt-4o-mini · grounded on 5 item(s) (--trace to audit them)
```

The default-facade examples also printed a stderr note that the grounding came from the
baseline lemmatizer, recommending `--greek-backend neural` (or the Python
module-level `use_treebank()` / `use_neural_pipeline()` selectors) for fuller grounding; that note is about the
*grounding* quality, not an error.

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

> Full reference: the [MCP server](MCP) page. This section is a quick tour.

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
cached and offline after), `greek_gloss` (the registry dictionaries), `greek_explain` (each token's lemma
evidence class in plain language), `corpus_diagnose` (the corpus health report),
and `koine_gloss` (the bundled Dodson NT lexicon). Corpora and works are addressed
by registry name or catalogue work id only (never a filesystem path), and a
domain miss returns a structured error with a did-you-mean hint.

---

## When something goes wrong

Three error shapes cover most first-week trouble. All of them are one line on
stderr with exit code `1`, and each names its own fix. (The messages below are
real runs.)

**1. A name pyaegean does not recognise.** Corpus ids, dataset names, and
query fields all answer a typo with the nearest real name:

```bash
aegean info linera
# aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (cypriot, cyprominoan, damos, ddbdp, edh, greek, igcyr, iip, iospe, isicily, lineara, linearb, nt, sigla), a Greek work id like tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin

aegean data fetch grc-jiont
# aegean: unknown dataset 'grc-jiont' — did you mean 'grc-joint'? (`aegean data list` shows all 28)
```

The fix is in the message: take the suggestion, or list the valid names
(`aegean data list`, `aegean query CORPUS --fields`).

**2. A missing optional extra.** The zero-dependency core is a supported
install, so features with heavier needs live behind extras, and reaching one
you have not installed stops with the exact `pip install` line:

```bash
aegean tui
# aegean: the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'
```

`plot` (`[viz]`), `export -f parquet` (`[parquet]`), the neural flags
(`[neural]`), and the AI providers (`[anthropic]` and friends) all guard the
same way. Run the printed install line and re-run your command;
`aegean doctor` lists every extra's state with its install line.

**3. Data (or a key) that is not on this machine.** Most fetched corpora
download themselves on first use, so the messages you actually see are about
the store's state, or a missing credential, each naming the next step:

```bash
aegean data remove linearb-corpus
# aegean: dataset 'linearb-corpus' is not downloaded; `aegean data list` shows what is

aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"
# aegean: no API key for 'anthropic'; set $ANTHROPIC_API_KEY or pass api_key=
```

One dataset is special: `linearb-corpus` has no generic download, so
`aegean data fetch linearb` prints a short option list instead of fetching
(fetch DAMOS, browse LiBER online, or import your own licensed export). If a
download was interrupted, `aegean doctor` spots the leftover partial file and
names the `aegean data remove` that reclaims it.

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
