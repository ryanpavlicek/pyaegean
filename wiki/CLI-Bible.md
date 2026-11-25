# CLI: Biblical & Koine Greek (`aegean bible …`)

Complete command reference for `aegean bible`: multi-edition Greek New Testament reading
and variant comparison, 2nd–5th century CE manuscript witnesses, Strong's and Extended
Strong's Greek lexicon with root trees, unified word studies, NT and Septuagint (LXX)
concordance search, Masoretic ↔ LXX Psalm conversion, and Greek patristic commentaries
(*Catenae* and Origen).

Every command works directly in your terminal (`aegean bible …`), inside the bare
`aegean` interactive shell (`bible …` with live book, edition, manuscript, and work-ID
prediction), and inside the TUI `:` console. Every command supports `--json`.

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [Biblical & Koine Greek (Python API)](New-Testament) · [TUI (`b`)](TUI)

---

## At a glance

| Command | Purpose | Common example |
|---|---|---|
| `bible read` | Read Greek NT (5 editions) or Septuagint (LXX auto-detected); interlinear or `.json`/`.db` export | `aegean bible read John 1:1-5 -i` |
| `bible compare` | Side-by-side collation across 5 NT editions with word-level variant diffs | `aegean bible compare John 1:18` |
| `bible witnesses` | Compare extant 2nd–5th c. CE manuscripts (P45–P75, 01, 02, 03, 05) | `aegean bible witnesses John 18:37 -s P52,01,03` |
| `bible strongs` | Strong's / Extended Strong's lookup, etymological root trees, and gloss search | `aegean bible strongs G3056 --roots` |
| `bible word-study` | Unified Strong's entry, root family, book & morphology distribution, concordance | `aegean bible word-study ἀγάπη` |
| `bible search` | Greek NT (lemma/text/Strong's/morph/gloss) and Septuagint concordance | `aegean bible search V-AAI --by morph -b John` |
| `bible commentary` | List, read, or search 48 Greek patristic commentaries (NT Catenae & Origen) | `aegean bible commentary read Matt` |
| `bible books` | List NT books (27), LXX books (55), NT editions (5), witnesses (13), or all | `aegean bible books lxx` |
| `bible psalm` | Convert Masoretic (Hebrew/English) ↔ Septuagint Psalm numbers | `aegean bible psalm 23 --from mt` |
| `bible status` | Show which Biblical bundles and patristic commentaries are installed on disk | `aegean bible status` |
| `bible install` | Download all 5 Biblical bundles (or specific items like `editions`, `lxx`, `witnesses`) | `aegean bible install` |

Passage references accept both dot and colon notation (`1.1-5`, `1:1-5`, `3.16`, `3:16`,
`1-3`). Septuagint books (`Gen`, `Exod`, `Ps`, `Isa`, `Wis`, …) auto-detect in
`bible read` and `bible search`.

### Downloading Biblical texts

Bundled offline samples cover `John 1`, `Phlm 1`, `Gen 1:1-5`, and `LXX Ps 22:1-6`. To
install the full 27-book NT, all 5 editions (Nestle 1904, SBLGNT, SRGNT, Byzantine
Majority, TR), 13 early manuscripts, 11,142 Extended Strong's entries, and all 55 Swete
Septuagint books (~25 MB total):

```bash
aegean bible status                         # see what is already installed
aegean bible install                        # download all 5 Biblical bundles at once
aegean bible install editions lxx           # or pick individual bundles by friendly name
aegean bible install commentary:John        # download patristic commentaries on John
```

In the TUI (`aegean tui`, press `b`), any tab or edition requiring an uninstalled bundle
displays an inline **Download** bar right inside the screen (`f` downloads it and reloads
automatically). See also `aegean library` in [CLI: Corpora, Analysis & Data](CLI-Corpora).

---

## `bible read` — Read Greek NT or Septuagint passages

```text
aegean bible read BOOK [PASSAGE] [--ref REF] [-e EDITION] [--lxx] [-i/--interlinear] [-o FILE] [--offline] [--json]
```

Reads a chapter, verse, or range from any of the 5 Greek NT editions (`nestle1904`
default, `sblgnt`, `srgnt`, `byz`, `tr`) or the 55-book Swete Septuagint (`lxx-corpus`).

```bash
aegean bible read John 1:1-5                     # Nestle 1904 verse text
aegean bible read John 1:1-5 --interlinear       # surface, lemma, morph, Strong's, gloss
aegean bible read John 1.18 -e sblgnt            # Society of Biblical Literature GNT
aegean bible read Gen 1:1-5                      # Swete Septuagint (LXX auto-detected)
aegean bible read Ps 22:1-6 --offline            # bundled offline LXX sample (MT Ps 23)
aegean bible read John 1 -o john1.json           # save as a Corpus (.json or .db)
aegean export john1.json -f csv --level token -o john1.csv
```

| Option | Effect |
|---|---|
| `PASSAGE` / `--ref` | Chapter (`1`), chapter range (`1-3`), single verse (`3:16` / `3.16`), or verse range (`1:1-18`). |
| `-e`, `--edition` | NT edition: `nestle1904` (gold morphology/Strong's/gloss), `sblgnt`, `srgnt`, `byz`, `tr`. |
| `--lxx` | Force Septuagint (optional for unambiguously LXX books such as `Gen`, `Ps`, `Isa`). |
| `-i`, `--interlinear` | Print a word-by-word table (Ref, Surface, Lemma, Morph, Strong's, Gloss). |
| `-o`, `--output` | Write the loaded `Corpus` to `.json` or `.db`/`.sqlite` (dispatched by extension). |
| `--offline` | Use local cache / bundled samples (`John 1`, `Phlm 1`, `Gen 1:1-5`, `LXX Ps 22:1-6`) without network access. |
| `--json` | Emit structured JSON (`book`, `ref`, `source`, `citation`, `verses[]` with token annotations). |

---

## `bible compare` — Multi-edition Greek NT collation

```text
aegean bible compare BOOK REF [-e EDITIONS] [--offline] [--json]
```

Aligns a passage across up to 5 Greek NT editions (`nestle1904`, `sblgnt`, `srgnt`,
`byz`, `tr`) and reports word-level substitutions, insertions, and omissions. Requires
the `nt-editions` asset (~1.7 MB, fetched automatically on first use unless `--offline`).

```bash
aegean bible compare John 1:18
aegean bible compare Matt 6:13 -e sblgnt,byz,tr
aegean bible compare Mark 16:9-12 -e nestle1904,sblgnt,byz --json
```

| Option | Effect |
|---|---|
| `-e`, `--editions` | Comma-separated subset of `nestle1904`, `sblgnt`, `srgnt`, `byz`, `tr` (default: all 5). |
| `--offline` | Use cached bundle only; fail cleanly if not yet fetched. |
| `--json` | Emit verse texts and structured diff operations. |

---

## `bible witnesses` — Early 2nd–5th c. CE manuscript witnesses

```text
aegean bible witnesses BOOK REF [-s SIGLA] [--hand original|corrected] [-d/--diplomatic] [--no-expand] [--offline] [--json]
```

Displays extant readings from 13 early Greek NT manuscripts (P45, P46, P47, P52, P66,
P72, P75, Sinaiticus `01`/`א`, Alexandrinus `02`/`A`, Vaticanus `03`/`B`, Ephraemi
`04`/`C`, Bezae `05`/`D`, Washingtonianus `032`/`W`), with automatic *nomina sacra*
expansion and scribal correction tracking. Uses the `nt-witnesses` asset (~2.0 MB).

```bash
aegean bible witnesses John 1:18
aegean bible witnesses John 18:37 -s P52,01,03
aegean bible witnesses John 1:18 -s P66,P75,01,03 --hand corrected
aegean bible witnesses John 1:1 -s P66,01 --diplomatic
aegean bible witnesses John 1:1 -s P66 --no-expand
```

| Option | Effect |
|---|---|
| `-s`, `--sigla` | Comma-separated sigla or names (`P52`, `P66`, `P75`, `01`, `03`, `A`, `B`, `D`, `Sinaiticus`, `Vaticanus`). |
| `--hand` | `original` (first-hand scribal reading, default) or `corrected` (later corrector's hand). |
| `-d`, `--diplomatic` | Print raw CNTR MES diplomatic transcription instead of readable Greek. |
| `--no-expand` | Keep *nomina sacra* contractions unexpanded (`θς`, `ις`, `χς`). |
| `--offline` / `--json` | Offline cache-only mode / structured JSON output. |

---

## `bible strongs` — Strong's & Extended Strong's lexicon

```text
aegean bible strongs QUERY [-r/--roots] [-s/--search] [--fetch] [--offline] [-n/--limit N] [--json]
```

Looks up a Strong's ID (`G3056`, `3056`), Greek lemma (`λόγος`), or searches glosses
and definitions. Works offline immediately over the bundled Dodson lexicon, and
automatically upgrades to all 11,142 STEPBible Extended Strong's entries (with Hebrew
equivalents and full derivations) once `strongs-greek` is cached or `--fetch` is passed.

```bash
aegean bible strongs G3056
aegean bible strongs λόγος --roots               # recursive etymological root tree
aegean bible strongs covenant --search -n 10     # English gloss search
aegean bible strongs G26 --fetch --roots         # fetch Extended Strong's if not cached
```

| Option | Effect |
|---|---|
| `-r`, `--roots` | Print the recursive etymological root family tree. |
| `-s`, `--search` | Search across Greek headwords, transliterations, and English glosses. |
| `--fetch` | Download the 11,142-entry `strongs-greek` bundle if not cached. |
| `--offline` | Never fetch over the network (default unless `--fetch` is set). |
| `-n`, `--limit`, `--top` | Maximum search hits (`0` = all). |
| `--json` | Emit JSON (`strongs`, `lemma`, `gloss`, `definition`, `derivation`, `hebrew`, `root_tree`). |

---

## `bible word-study` — Unified Koine word study

```text
aegean bible word-study QUERY [-b BOOK] [-n/--limit N] [--offline] [--json]
```

Combines Strong's lexicon metadata, etymological root family, book-by-book occurrence
counts, Robinson morphology breakdown, and sample verse concordance into one report.

```bash
aegean bible word-study G3056
aegean bible word-study ἀγάπη --book John
aegean bible word-study G5485 --limit 20 --json
```

---

## `bible search` — Greek NT & Septuagint concordance

```text
aegean bible search QUERY [--by FIELD] [-b BOOK] [--section SECTION] [-e EDITION] [--lxx] [-n/--limit N] [--offline] [--json]
```

Searches the Greek New Testament by lemma, surface form, Strong's number, Robinson
morphology prefix, or English gloss — or searches the 55-book Swete Septuagint
(accent- and case-insensitive). Passing an LXX book (`-b Gen`, `-b Ps`) or `--section`
auto-selects Septuagint search.

```bash
aegean bible search λόγος                              # NT lemma concordance
aegean bible search V-AAI --by morph --book John       # aorist active indicatives in John
aegean bible search G26 --by strongs                   # every NT occurrence of G26
aegean bible search grace --by gloss -n 15             # English gloss concordance
aegean bible search φῶς --lxx                          # all 55 Swete LXX books
aegean bible search κύριος --section Pentateuch        # LXX restricted to Pentateuch
aegean bible search φῶς -b Gen --offline               # auto-detects LXX offline sample
```

| Option | Effect |
|---|---|
| `--by` | NT match field: `lemma` (default), `text`, `strongs`, `morph`, or `gloss`. |
| `-b`, `--book` | Restrict to one NT or LXX book (LXX books auto-select Septuagint search). |
| `--section` | Restrict LXX search to a section (`Pentateuch`, `Historical`, `Wisdom`, `Prophets`, …). |
| `-e`, `--edition` | NT edition (`nestle1904` default). |
| `--lxx` | Force Septuagint search. |
| `-n`, `--limit`, `--top` | Maximum hits (`0` = all). |

---

## `bible commentary` — Greek patristic commentaries (Catenae & Origen)

```text
aegean bible commentary [BOOK | WORK_ID | read TARGET | search TARGET TERM] [-k catena|origen] [--ref REF] [-n/--limit N] [--json]
```

Browse, read, and search 48 Greek patristic biblical commentary volumes from
First1KGreek (30 Greek NT *Catenae* `tlg4102.*` covering Matthew–Jude and 18 Origen
commentaries/homilies `tlg2042.*`).

```bash
aegean bible commentary                          # list all 48 volumes
aegean bible commentary Matt                     # list volumes covering Matthew
aegean bible commentary --kind origen            # list Origen's 18 volumes

# Read commentary sections (all equivalent natural forms):
aegean bible commentary read Matt                # read the Matthew catena
aegean bible commentary tlg4102.tlg001           # read a specific TLG volume directly
aegean bible commentary read tlg4102.tlg001      # same, explicit verb
aegean bible commentary read Matt --limit 15     # show 15 sections (0 = all)

# Search Greek terms inside a commentary:
aegean bible commentary search John λόγος
aegean bible commentary search tlg4102.tlg001 βασιλεία --limit 10
```

| Option | Effect |
|---|---|
| `-k`, `--kind` | Filter by `catena` (NT Catenae) or `origen` (Origen commentaries/homilies). |
| `--ref` | Optional TEI section reference when reading. |
| `-n`, `--limit`, `--top` | Maximum sections/excerpts to print (`5` default; `0` = all). |
| `--read` / `--search` / `--work-id` | Flag equivalents to the positional `read` / `search` / `WORK_ID` forms. |
| `--json` | Emit structured JSON (`book`, `work_id`, `author`, `title`, `kind`, `section_id`, `text`, `matched_words`). |

---

## `bible books` — Catalogs of books, editions, and witnesses

```text
aegean bible books [nt|lxx|editions|witnesses|all] [--section SECTION] [--json]
```

```bash
aegean bible books                   # 27 NT books and accepted aliases (default: nt)
aegean bible books lxx               # 55 Swete Septuagint books + TLG IDs
aegean bible books lxx --section Wisdom
aegean bible books editions          # 5 Greek NT editions + licenses
aegean bible books witnesses         # 13 2nd–5th c. CE manuscripts + dates
aegean bible books all               # summary of all 4 catalogs
```

---

## `bible psalm` — Masoretic ↔ Septuagint Psalm numbering

```text
aegean bible psalm NUMBER [--from mt|lxx] [--json]
```

Converts between Hebrew/English (Masoretic, `1–150`) and Greek Septuagint (`1–151`)
Psalm numbers (including split/merged Psalms 9–10, 114–116, 146–147, and Psalm 151).

```bash
aegean bible psalm 23 --from mt      # MT Psalm 23 ↔ LXX Psalm 22
aegean bible psalm 115 --from lxx    # LXX Psalm 115 ↔ MT Psalm 116
aegean bible psalm 151 --from lxx    # extra-canonical in MT
```

---

## Interactive shell & TUI workflows

Inside bare `aegean` (interactive shell) or the TUI `:` console, drop the `aegean`
prefix and use `Tab` or `Right`/`End` for live completion of books, editions,
manuscript sigla, commentary verbs, and TLG work IDs:

```text
aegean> bible read John 1:1-5 -i
aegean> bible compare John 1:18 -e sblgnt,byz,tr
aegean> bible witnesses John 18:37 -s P52,01,03
aegean> bible commentary read Matt
aegean> bible commentary search John λόγος
```

For a full-screen study view (interlinear reader, 5-edition collation, early
manuscripts, Strong's word study, and inline LXX search/reader), launch `aegean tui`
and press **`b`**.
