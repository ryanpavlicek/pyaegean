# The `aegean` command line

`aegean` exposes the pyaegean toolkit from the terminal: corpora, Greek NLP,
Biblical and Koine Greek, surface analysis, research bundles, the local data
store, SQLite full-text search, plots, and the exploratory AI layer. If you are
new to the command line, start with [Getting Started](Getting-Started) to set up
a terminal, then return here.

> **Quick lookup:** [CLI Cheatsheet](CLI-Cheatsheet) lists every command and
> flag on one page. This page walks through each command group with worked
> examples.

> **Available in v0.72.0.** All commands, flags, research bundle workflows,
> multi-script workbench controls, and TUI review options on this page match the
> current release.

```bash
pip install "pyaegean[cli]"     # adds typer + rich; core library stays zero-dependency
aegean --help
```

The core package installs the `aegean` entry point. Running commands requires
the `[cli]` extra; without it, `aegean` prints the `pip install` command and
exits.

## Global conventions

These four behaviors apply across the command tree:

| Convention | Behavior | Example |
|---|---|---|
| **`--json`** | Prints one JSON document to stdout with readable Greek (`ensure_ascii=False`), suitable for `jq` or scripts. When combined with `--output/-o`, writes the file (`wrote <path>` on stderr) and still prints JSON to stdout. | `aegean info lineara --json` |
| **`-` reads stdin** | Any command accepting a `TEXT` argument reads from stdin when given `-`. | `echo "μῆνιν" \| aegean greek lemmatize -` |
| **`--top` / `--limit`** | Aliases for the same row cap on ranked tables and result lists, including `plot`. Passing `0` removes the cap wherever `--help` says `0 = all` (`greek rarity` is the exception: its cap slices directly, so `0` prints nothing). | `aegean stats lineara --limit 3` |
| **Exit codes** | `0` success · `1` domain error (one line on stderr prefixed `aegean:`) · `2` usage error (missing/invalid arguments). `balance --strict` exits `1` if any checked total fails. | see below |

Exit code examples:

```bash
aegean info lineara --json > /dev/null ; echo "exit=$?"      # exit=0   (success)
aegean info bogus                                            # aegean: unknown corpus 'bogus'; expected a registered id (…)
                                                             # exit=1   (domain error on stderr)
aegean info                                                  # exit=2   (usage error: missing argument)
aegean balance lineara HT13 --strict ; echo "exit=$?"        # exit=1   (total did not balance)
```

Every command and group supports `-h` and `--help`:

```bash
aegean --help
aegean greek --help
aegean greek scan --help
```

> **Windows terminals:** If polytonic Greek appears as boxes or `?`, check the
> terminal font and encoding. Set `PYTHONUTF8=1` and run `chcp 65001` once for
> UTF-8 console output, or write `--json` output and inspect it in an editor.
> See [Getting Started](Getting-Started#seeing-greek-correctly). Linear A/B
> glyph columns (𐝫, 𐙂) also require a font with Aegean script coverage: see
> [Installation → Set up your terminal](Installation#set-up-your-terminal).

## Reading usage lines

`--help` output and this wiki use standard CLI notation. Take `aegean stats --help`:

```text
Usage: aegean stats [OPTIONS] CORPUS
```

- **`aegean stats`** is the command (`aegean` plus subcommand `stats`). Grouped
  commands add one more word, such as `aegean greek scan`.
- **`CORPUS`** (uppercase, no dashes) is a positional **argument**, so the
  shortest valid invocation is `aegean stats lineara`. Square brackets mark
  optional arguments: `aegean balance [OPTIONS] CORPUS [DOC_ID]` checks one
  tablet when `DOC_ID` is given, or the whole corpus when omitted.
- **`[OPTIONS]`** are named flags starting with `-` or `--` that can appear in
  any order. Options either take a value (`--top 5`) or act as boolean switches
  (`--signs`). Run `aegean stats --help` to see all options for a command.
- **Short and long flags.** Common options have one-letter aliases: `-o` equals
  `--output`, `-f` equals `--format`. The docs prefer long names for clarity.

For example:

```bash
aegean stats lineara --signs --top 5
```

runs `stats` on `lineara`, counts individual signs instead of words, and limits
output to five rows.

**Quoting.** Wrap values containing spaces, wildcards (`*`), or punctuation in
double quotes: `aegean search lineara "KU-*-RO"`,
`aegean load lineara --site "Haghia Triada"`. Double quotes work in PowerShell,
cmd, bash, and zsh. Single Greek words need no quotes
(`aegean greek syllabify εἰσφέρω`), while multi-word lines require them
(`aegean greek scan "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"`). On macOS and Linux,
single quotes work too; on PowerShell, prefer double quotes.

## Command map

```bash
aegean --version          # pyaegean 0.72.0
```

| Group | Commands |
|---|---|
| **(top level)** | `quickstart` `repl` `tui` `info` `load` `show` `find` `search` `query` `stats` `dispersion` `keyness` `cache` `doctor` `balance` `cite` `export` `combine` `import` `geo` `sign` `bridge` `plot` `workbench` |
| **`aegean library …`** | `status` `packs` `list` `search` `info` `install` `remove` (all corpora, Biblical bundles, ~1,778 Greek works, 86 patristic commentaries, lexica, models, and 7 named packs) |
| **`aegean greek …`** | `normalize` `betacode` `strip` `tokenize` `syllabify` `accent` `accentuate` `sandhi` `quantities` `scan` `ipa` `profile` `tag` `lemmatize` `morph` `inflect` `parse`, plus `pipeline`, `explain`, `stream`, `annotation-profiles list`/`show`, `interop export`/`import`/`report`, `gloss`/`usage`/`lexica`/`lexicon-link`, `rarity`, `missing-forms`, `conllu inspect`/`export`, `work`/`works`/`catalog`, and `eval` |
| **`aegean bible …`** | `read` `compare` `witnesses` `strongs` `word-study` `search` `commentary` `books` `psalm` `status` `install` (9 Greek NT editions, 13 early 2nd–5th c. CE manuscripts, Extended Strong's + roots, 55 LXX books, 86 patristic commentaries) |
| **`aegean analyze …`** | `distance` `align` `compare` `nearest` `assoc` `cooccur` `clusters` `structure` `hands` `hand` `dossiers` `syllabary` `bridge` |
| **`aegean bundle …`** | `create` `inspect` `verify` `extract` `hydrate` (deterministic, SHA-256-verified, NC-safe research bundles `.zip`) |
| **`aegean data …`** | `list` `fetch` `remove` `versions` `store` |
| **`aegean db …`** | `build` `add` `index` `search` `annotate` `job-status` (SQLite + FTS5 + resumable annotation jobs) |
| **`aegean review …`** | `export` `merge` `apply` (human-in-the-loop annotation review, editable & calibrated-risk queues) |
| **`aegean ai …`** | `providers` `translate` `gloss` `summarize` `hypotheses` `ask` `extract` `eval` (exploratory, key-gated) |
| **`aegean-mcp`** | Separate console script exposing 29 read/analysis tools to AI agents over MCP stdio |

---

## Common tasks

Each example below matches live command output (long listings abridged with
`…`). Commands marked *(downloads on first use)* cache their data once and run
offline afterward.

**Inspect a corpus** (size, source, license, citation):

```bash
aegean info edh
# 1286 documents, 26937 words, EDH source line, CC-BY-SA-4.0 license, and citation
```

**Read a Linear A tablet line by line**:

```bash
aegean show lineara HT13
# HT13  site=Haghia Triada  period=LMIB  scribe=HT Scribe 8  support=Tablet
#   1: KA-U-DE-TA VIN 𐄁 TE 𐄁
#   2: RE-ZA 5 ¹⁄₂
#   …
```

**Read a chapter of the Greek New Testament** (John 1 is bundled offline):

```bash
aegean bible read John 1
# John 1  (1 chapter, 828 tokens)
# John 1
#   1: Ἐν ἀρχῇ ἦν ὁ Λόγος, καὶ ὁ Λόγος ἦν πρὸς τὸν Θεόν, καὶ Θεὸς ἦν ὁ Λόγος.
#   …
```

**Read the Iliad by book** *(downloads on first use)*:

```bash
aegean show tlg0012.tlg001 1
# tlg0012.tlg001:1
#   1: μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος
#   2: οὐλομένην , ἣ μυρίʼ Ἀχαιοῖς ἄλγεʼ ἔθηκε ,
#   …
```

**Count the most frequent words** *(downloads `nt` on first use)*:

```bash
aegean stats nt --top 3
# καὶ 8541 · ὁ 2768 · ἐν 2683
```

**Search 57,000 documentary papyri** *(downloads the ~219 MB DDbDP database once)*:

```bash
aegean db search ddbdp "βασιλέως" --limit 3
# doc/pos/text table: apf.59.84_2 · bgu.10.1910 · bgu.10.1957
```

**Query documents containing a word**:

```bash
aegean query nt --where "ins-contains-word=ἀγάπη" --limit 3
# Contains exact word: ἀγάπη → 20 inscription(s)
# table starting Matt 24 · John 17 · Rom 5, followed by the exact-subset citation
```

**Map where a word is attested** (case-insensitive):

```bash
aegean geo lineara --word a-du
# lineara: 'a-du' attested at 3 located site(s)
# Haghia Triada ×7, Khania ×2, Tylissos ×1
```

**Check tablet arithmetic**:

```bash
aegean balance lineara HT9a
# HT9a  KU-RO  stated 31.75  computed 31.0  diff -0.75  balances NO
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

**Reconstruct pronunciation** (Attic or Koine):

```bash
aegean greek ipa "Χριστός" --period koine
# xristos
```

**Convert Beta Code to polytonic Greek**:

```bash
aegean greek betacode "lo/gos"
# λόγος
```

**Look up an NT word's gloss** (bundled offline Dodson lexicon):

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

**Cite a corpus**:

```bash
aegean cite nt
# Nestle, E. (1904). Novum Testamentum Graece (Nestle 1904). Morphology/lemmatization (CC0) via biblicalhumanities/Nestle1904. — https://github.com/biblicalhumanities/Nestle1904
```

**Check the local installation**:

```bash
aegean doctor
# five tables (versions, extras, data store, models, analysis cache), then:
# doctor: all checks passed
```

---

## Guided tour (`aegean quickstart`)

`aegean quickstart` runs an eight-step offline walkthrough on bundled data with
no network calls or API keys. Seven steps execute live commands (reading a
Linear A tablet, checking accounting totals, searching sign patterns, running
the Greek pipeline, scanning Iliad 1.1, and listing fetchable datasets) and the
eighth lists next steps:

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

Pass `--no-run` to print the commands without executing them.

---

## Interactive shell (`aegean` / `aegean repl`)

Running bare `aegean` in an interactive terminal launches the shell so you can
type commands without the `aegean` prefix. `aegean repl` invokes the same shell
explicitly and also accepts piped command scripts. Calling `aegean --help` or
piping non-interactive stdin to bare `aegean` prints the help text instead.

Inside the shell you get inline ghost-text predictions (**Right** or **End** to
accept), a live completion dropdown (**Tab** or while typing) covering commands,
subcommands, flags, and domain values (corpora, datasets, NT/LXX books,
editions, manuscript sigla, meters, dictionaries, and formats), persistent
command history, and a read-only session corpus cache so repeated queries avoid
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

Every line dispatches through the regular CLI parser (`--json`, `-o`, corpus
files, work ids). Syntax or domain errors print a message and keep the shell
open. The shell requires the `[cli]` extra (which includes `prompt_toolkit`).
The same completion engine powers the TUI command console (`:`) and shell
tab-completion (`aegean --install-completion`).

### Shell directives

Three directives work only inside the shell:

- **`use CORPUS`** sets a session corpus for corpus-first commands (`info`,
  `load`, `show`, `search`, `query`, `stats`, `dispersion`, `keyness`,
  `balance`, `cite`, `export`, `geo`, `sign`, `db build`, and corpus-taking
  `analyze` subcommands). After `use lineara`, `show HT13` targets `lineara`.
  Naming a corpus explicitly overrides the session default (`info linearb` still
  reads `linearb`). `use` alone shows the active corpus; `use off` clears it.
  The target is validated on assignment and must be re-loadable (registered id,
  Greek work id, or `.json`/`.db` file; stdin JSON is not allowed):

  ```text
  aegean> use linera
  aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (aphrodisias, apostolic-fathers, …, sigla), a Greek work id like tlg0012.tlg001, or a path to a .json or .db corpus
  ```

  When a session corpus is active, placing options *before* an explicit corpus
  argument (`stats --top 5 linearb`) fails with a usage error so the command
  does not read the wrong corpus. Put the corpus argument first.
- **`:examples`** (or `examples`) prints starter commands across the main groups
  with one-line descriptions, ending with a `use lineara` / `show HT13` example.
- **`:help`** (or `help`) prints the directive summary and full command list.
  `:exit`, `quit`, or **Ctrl-D** exits.

### History and scripting

Command history persists in `~/.config/pyaegean/repl_history`
(`XDG_CONFIG_HOME` is respected; on Windows,
`%USERPROFILE%\.config\pyaegean\repl_history`). History is stored in the config
directory instead of `PYAEGEAN_CACHE` so `aegean data store` tracks downloads
only. If the config path is unwritable, the shell falls back to session-only
history. Piped scripts are not saved to history.

When stdin is not a terminal, `aegean repl` reads and runs one command per line
(including `use`):

```bash
printf 'use lineara\nshow HT13\nstats --top 3\n' | aegean repl
```

### Worked shell session

The following output comes from a scripted run (`aegean>` prompts added for
clarity):

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
  …  (fifteen starter lines in all)
aegean> :exit
```

After `use lineara`, `show HT13`, `stats --top 3`, and `search "KU-*-RO"` all
defaulted to Linear A, while `greek syllabify` ran unchanged.

---

## Research bundles (`aegean bundle`)

`aegean bundle` packages corpora, citations, workbench workspace backups,
review CSVs (with editable `.companion.json` sidecars), and analysis receipts
into deterministic, SHA-256-verified `.zip` archives (`aegean-research-bundle/1`):

```bash
aegean bundle create study.zip --corpus lineara --site "Haghia Triada" \
    --state workspace.json --review review.csv --receipt eval.json
aegean bundle inspect study.zip
aegean bundle verify study.zip
aegean bundle extract study.zip ./unpacked
aegean bundle hydrate study.zip ./hydrated --fetch
```

By default (`--embed-corpus auto`), CC BY-NC* and restricted corpora (such as
`damos`) are stored as retrieval pointers instead of embedded payloads so public
bundles stay redistributable. Pass `--fetch` to `bundle hydrate` to reconstruct
pointer corpora under their upstream licenses. See
[CLI: Corpora, Library, Analysis & Data](CLI-Corpora#research-bundles--aegean-bundle-)
for every option.

---

## Terminal UI (`aegean tui`)

```bash
pip install "pyaegean[tui]"
aegean tui
aegean tui --corpus lineara
aegean tui --review a.csv --review b.csv --corpus nt
```

Full-screen Textual interface with nine screens:

- `h` Home (19 browsable corpora)
- `c` Corpus browser (inline downloads, reader with word cursor and line analysis)
- `g` Greek workbench (Beta Code toggle, 10 meters, live pipeline/lexicon/IPA)
- `b` Biblical Greek (9 NT editions, 13 manuscripts, Strong's word study, LXX & Patristics)
- `l` Library manager (7 packs, installed resources, filterable catalogue)
- `r` Annotation review (`ReviewScreen`: single CSVs, multi-reviewer conflict adjudication with `a`/`e`/`1`/`2`/`3`/`d`/`x`/`n`/`p`/`f`/`s`, or live corpus risk queues)
- `w` Works library (~1,778 Greek works)
- `d` Data store (`aegean doctor` + dataset fetch/remove)
- `:` Command console (CLI parity with live completion)

Launch straight into annotation or conflict review with
`aegean tui --review a.csv [--review b.csv] --corpus <id>`. See [TUI](TUI) for
keybindings, screen walkthroughs, and theme persistence.

---

## Command reference pages

Each command group has a dedicated reference page:

| Page | Covers |
|---|---|
| [CLI Cheatsheet](CLI-Cheatsheet) | One-page index of every command and flag |
| [CLI: Corpora, Library, Analysis & Data](CLI-Corpora) | `aegean library`, top-level corpus commands (`info`, `load`, `show`, `find`, `search`, `query`, `stats`, `balance`, `export`, `import`, `geo`, `plot`, `workbench`), `aegean bundle`, `aegean analyze`, `aegean data`, and `aegean db` |
| [CLI: Greek NLP & Review](CLI-Greek) | `aegean greek` (normalization, scansion, tagging, lemmatization, parsing, dictionaries, Perseus/First1KGreek works, CoNLL-U, interop, eval) and `aegean review` |
| [CLI: Biblical & Koine Greek](CLI-Bible) | `aegean bible` (`read`, `compare`, `witnesses`, `strongs`, `word-study`, `search`, `commentary`, `books`, `psalm`, `status`, `install`) |
| [CLI: AI & MCP](CLI-AI) | `aegean ai`, `aegean-mcp`, troubleshooting, and recipes |
