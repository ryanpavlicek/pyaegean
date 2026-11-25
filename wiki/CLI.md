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

> **Available in v0.66.0.** The annotation-profile and interoperability commands, the
> CoNLL-U, long-input, source-alignment, and analysis-receipt commands and fields, and the
> runtime-variant selectors described below are all part of the current release.

```bash
pip install "pyaegean[cli]"     # adds typer + rich; the core library stays zero-dependency
aegean --help
```

The `aegean` entry point is installed with the core package; install the `[cli]`
extra to run the commands. Without it, the entry point prints an installation hint.

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
aegean --version          # pyaegean 0.66.0
```

| Group | What's in it |
|---|---|
| **(top level)** | `quickstart` `repl` `tui` `info` `load` `show` `search` `query` `stats` `dispersion` `keyness` `cache` `doctor` `balance` `cite` `export` `combine` `import` `geo` `sign` `bridge` `plot` `workbench` |
| **`aegean greek …`** | normalize → `betacode` → `strip` → tokenize → syllabify → accent → `accentuate` → `sandhi` → `quantities` → scan → `ipa` → `profile` → tag → lemmatize → morph → `inflect` → parse, plus `pipeline`, `explain`, bounded neural `stream`, `annotation-profiles list`/`show`, `interop export`/`import`/`report`, `gloss`/`usage`/`lexica`/`lexicon-link`, `rarity`, `missing-forms`, `conllu inspect`/`export`, `work`/`works`/`catalog`, and `eval` |
| **`aegean bible …`** | `read` `compare` `witnesses` `strongs` `word-study` `search` `commentary` `books` `psalm` (5 Greek NT editions, 13 early 2nd–5th c. CE manuscripts, Extended Strong's + roots, 55 LXX books, 48 patristic commentaries) |
| **`aegean analyze …`** | `distance` `align` `compare` `nearest` `assoc` `cooccur` `clusters` `structure` `hands` `hand` `dossiers` `syllabary` `bridge` |
| **`aegean data …`** | `list` `fetch` `remove` `versions` `store` |
| **`aegean db …`** | `build` `add` `index` `search` `annotate` `job-status` (SQLite + FTS5 + resumable annotation jobs) |
| **`aegean review …`** | `export` `merge` `apply` (the human-in-the-loop annotation round-trip, editable & risk-prioritized spreadsheets) |
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
aegean bible read John 1
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
aegean bible strongs ἀγάπη
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
  aegean                        interactive shell with live predictive completion
  aegean doctor                 check the install and cached data
  aegean --install-completion   tab-completion for your shell
  docs:                         https://github.com/ryanpavlicek/pyaegean/wiki

That was 7 real commands in 0.2s, all offline, all bundled data.
```

`--no-run` prints the tour script without executing anything, so you can read
the seven commands first. Because the outputs are live, what you see is exactly
what your install does.

---

## Interactive shell (`aegean` / `aegean repl`)

Running bare **`aegean`** in an interactive terminal opens the interactive shell
directly so you don't retype `aegean` for every command (`aegean repl` stays
available explicitly and also handles piped scripts; `aegean --help` or a
non-TTY/piped `aegean` still prints the command map). Inside the shell you get
**live predictive completion** (fish-style inline ghost text — press **Right**
or **End** to accept — plus a live dropdown on **Tab** or while typing) across
every command, subcommand, `--flag`, and domain value (corpora, fetchable
datasets, NT/LXX books, editions, manuscript sigla, meters, dictionaries, and
output formats), together with a **history that persists across sessions** and a
read-only per-session corpus cache so repeated `show`/`stats`/`search` runs skip
re-parsing the same corpus:

```text
$ aegean
aegean interactive shell — commands without the 'aegean' prefix.
Type for live suggestions (Right/End accepts, Tab completes), history persists, :help lists commands, :exit or Ctrl-D quits.
:examples shows starter lines; 'aegean --install-completion' (outside the shell) adds completion to your regular shell.
aegean> info lineara
…the same table aegean info lineara prints…
aegean> bible read John 1.1-5
…interlinear Greek NT with morphology, Strong's numbers, and glosses…
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
open. The shell needs the `[cli]` extra (it ships `prompt_toolkit`). The same
completion and inline-prediction engine powers the TUI command console (`:`) and
native shell tab completion (`aegean --install-completion`).

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
  command groups (including `bible` and `greek`), each with a one-line
  description, ending with a `use lineara` / `show HT13` pair that demonstrates
  the directive.
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

When standard input isn't a terminal, `aegean repl` reads one command per line instead
of prompting, so you can script it (the `use` directive works there too):

```bash
printf 'use lineara\nshow HT13\nstats --top 3\n' | aegean repl
```

### A worked session

A short, realistic sitting: set a session corpus, read a tablet, run two
analyses on it, ask a Greek question, and leave. The outputs below are from a
real scripted run (the shell reads one command per line when its input is
piped); the `aegean>` prompt lines are added for readability, since a piped
session does not echo them. In an interactive terminal bare `aegean` (or
`aegean repl`) greets you with a banner and the full command map (`aegean --help`),
not shown here.

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
'pyaegean[tui]'`), the same way `aegean plot` guards `[viz]`. The default corpus
views and baseline Greek workbench run offline without API keys. Fetch actions,
optional neural analysis, and key-gated translation can access the network;
the command console can run the regular CLI commands.

### What's on screen

Seven screens, switched with a single key from anywhere:

| Screen | Key | What it shows |
|---|---|---|
| **Home** | `h` | Corpus overview (13 corpora with on-disk status) and global key legend. |
| **Corpus browser** | `c` | Corpus list, filterable document table, and apparatus-aware reader with word cursor, live token inspector, inline interlinear toggle (`i`), `KU-RO` / `to-so` balance check, and line-analysis popup (`Enter`/`a`). |
| **Greek workbench** | `g` | Live text box (with Beta Code toggle `b`) over Pipeline, Scansion (10 meters), Syllables, IPA, and Lexicon tabs. |
| **Biblical Greek** | `b` | Interlinear NT & LXX reader, 5-edition collation, 13 early manuscript witnesses, Strong's + root trees, word study, and LXX search/Psalm converter. |
| **Works library** | `w` | Search the 1,778-work Greek catalogue, fetch works or whole authors, open or remove cached texts. |
| **Data store** | `d` | Environment report and fetchable datasets table with background download progress. |
| **Command console** | `:` | Full-parity `aegean>` console with live context-aware dropdown, inline ghost-text suggestions, and persistent session cache. |

Global keys on every screen: `q` quit, `?` help, `t` theme picker, `Esc` back, `ctrl+p` command palette. See [TUI](TUI) for full documentation.

---

## Command reference pages

Each major command group has its own dedicated page under **Command Line (CLI)** in the sidebar:

| Page | Covers |
|---|---|
| [CLI Cheatsheet](CLI-Cheatsheet) | Dense one-page index of every command and flag |
| [CLI: Corpora, Analysis & Data](CLI-Corpora) | Top-level corpus commands (`info`, `load`, `show`, `search`, `query`, `stats`, `balance`, `export`, `import`, `geo`, `plot`, `workbench`), `aegean analyze`, `aegean data`, and `aegean db` |
| [CLI: Greek NLP & Review](CLI-Greek) | `aegean greek` (normalization, scansion, tagging, lemmatization, parsing, dictionaries, Perseus/First1KGreek works, CoNLL-U, interop, eval) and `aegean review` |
| [CLI: Biblical & Koine Greek](CLI-Bible) | `aegean bible` (`read`, `compare`, `witnesses`, `strongs`, `word-study`, `search`, `commentary`, `books`, `psalm`) |
| [CLI: AI & MCP](CLI-AI) | `aegean ai`, `aegean-mcp`, troubleshooting, and recipes |
