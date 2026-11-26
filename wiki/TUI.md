# The terminal UI (`aegean tui`)

`aegean tui` launches a full-screen Textual interface over the pyaegean library.
It provides nine keyboard-driven screens: a corpus overview, a three-pane corpus
browser (with word cursor, live token inspector, and inline interlinear gloss
toggle), a live Greek workbench (with Beta Code input, all 10 meters, and
lexicon glosses), a **Biblical Greek study screen** (`b`: 9 NT editions, 13
early manuscripts, Strong's word studies, and LXX & Patristics), a **Library
Manager** (`l`), an **Annotation Review screen** (`r`: single CSVs,
multi-reviewer conflict adjudication, and live corpus risk queues), a searchable
catalogue of ~1,778 Greek works (`w`), the local data store (`d`), and a command
console (`:`) with CLI parity.

Default reader and workbench views run offline over bundled and cached data with
no API key. Optional actions fetch works, corpora, or neural models, and the
line-analysis popup supports key-gated translation.

```bash
pip install "pyaegean[tui]"
aegean tui
aegean tui --corpus lineara
aegean tui --review review.csv
aegean tui --review alice.csv --review bob.csv --corpus nt
```

The TUI ships in the `[tui]` extra (which installs
[Textual](https://textual.textualize.io/)). Without `[tui]`, `aegean tui` exits
`1` with the exact install command (`the TUI needs the [tui] extra — install it
with: pip install 'pyaegean[tui]'`).

| Option | Effect |
|---|---|
| `--corpus`, `-c CORPUS` | Open directly on a corpus id or local `.json`/`.db` path; also provides corpus context for multi-reviewer `--review` merges. |
| `--review`, `-r PATH` | Open directly in **Annotation review (`r`)** with one or more review CSVs (repeatable; pass twice with `--corpus` to adjudicate reviewer conflicts). |

On Windows, install Aegean fonts from
[Installation → Set up your terminal](Installation#set-up-your-terminal) and run
with `PYTHONUTF8=1` so polytonic Greek and Aegean syllabic glyphs display
correctly.

---

## First five minutes

Key-by-key walkthrough from launch to reading and analyzing a tablet:

1. Run `aegean tui`. The app opens on **Home** with the corpus list focused on
   `lineara` and the key legend at the bottom.
2. Press `c`. The **corpus browser** opens: corpus list on the left (focused),
   document table in the middle, and reader on the right.
3. Press `↓` to move through the corpus list. Uninstalled hosted corpora carry a
   `· fetch` tag; selecting one shows an inline **Download** bar where `f`
   fetches and opens it in place.
4. Press `Enter` on `lineara`. The status line reports `lineara: 1721 documents`
   and the middle table lists each document (id, site, period, words,
   structure).
5. Press `Tab` to focus the search box above the table (typing filters by id),
   then `Tab` again to move into the document table (`↑`/`↓` move rows).
6. Press `Enter` on a row. The reader displays the tablet: id (`HT1`), metadata
   (`Haghia Triada · LMIB · Tablet · HT Scribe 21`), counts and structure, and
   numbered token lines with line 1 highlighted. The status line lists the
   reader keys: `HT1 — Tab to reader: ↑/↓ line · ←/→ word · i interlinear · Enter/a analyze`.
7. Press `Tab` to focus the reader. `↑`/`↓` move the line cursor (`PgUp`/`PgDn`
   jump ten lines; `Home`/`End` jump to the start and end). `←`/`→` move the
   word cursor; `i` toggles inline interlinear glosses.
8. Press `Enter` (or `a`). The **line-analysis popup** opens with the selected
   line at the top, available script analyses listed below, and the first
   analysis already computed. Use `↑`/`↓` and `Enter` to switch analyses.
9. Press `Esc` to close the popup and return to the reader at the same line.
10. Press `?` for the key reference (`Esc`, `q`, or `Enter` closes it). Press
    `Esc` to walk back to Home, or `q` to quit.

`Esc` always blurs a focused text input first, and a second `Esc` walks back
through screen history.

---

## Managing texts, packs, and inline downloads

Missing corpora and bundles can be downloaded directly inside the TUI:

- **Biblical Greek (`b`):** selecting an uncached NT edition, manuscript
  witness, full 27-book NT, Extended Strong's, Septuagint, or *Patrologia
  Graeca* view displays an inline **Download** bar below the passage input.
  Press `f` (or click **Download**) to fetch the required asset, or click
  **Biblical Pack** to install all 5 Biblical bundles; the active tab reloads
  automatically on completion.
- **Corpus Browser (`c`):** selecting an uninstalled browsable corpus (`damos`,
  `sigla`, `nt`, `lxx`, `apostolic-fathers`, `pseudepigrapha`, `isicily`, `iip`,
  `iospe`, `igcyr`, `aphrodisias`, `crete`, `edh`, `byzantine`,
  `homer-scholia`) shows an inline **Download** bar (`f` fetches on a
  background worker and opens it).
- **Library Manager (`l`):** five-tab manager across all resources:
  - **Packs**: install (`f`) or remove (`x`) any of the 10 themed packs
    (`biblical`, `church-fathers`, `patristic`, `ancient-greek`,
    `byzantine-pack`, `aegean`, `epigraphy`, `literary`, `lexica`, `neural`).
  - **Installed**: every bundled and downloaded resource on disk with byte
    sizes, **Open (`o`)**, and **Remove (`x`)** (bundled corpora stay
    protected).
  - **Corpora & Biblical**, **Works & Commentaries**, and **Lexica & Models**:
    filter with `/`, download with `f`, open with `o`, remove with `x`, and
    reload with `r`.

---

## Everyday tasks

### Fetch and browse DAMOS (Linear B)

DAMOS holds ~5,900 Linear B tablets, downloaded on demand:

1. Press `c` to open the **corpus browser**, highlight `damos`, and press
   `Enter`. An inline **Download** bar appears (`DAMOS Linear B Corpus (~3.0 MB)`).
2. Press `f` (or click **Download damos**). The worker fetches the corpus and
   opens it in the document table (`damos: 5932 documents`). To fetch DAMOS and
   SigLA together, install the `aegean` pack from **Library Manager (`l`)**.
3. Press `/` and type `KN`. The table narrows to Knossos tablets
   (`4228 of 5932 documents match id 'KN'`). Press `Tab` into the table and
   `Enter` on any row to read it.

### Fetch, read, and remove a Greek literary work

Works are fetched from **Works library (`w`)** and read in the **Corpus browser (`c`)**:

1. Press `w`. The search box starts focused; an empty query lists downloaded
   works.
2. Type `epigrams`. The table filters to `3 matches` showing id, author, title,
   source, and cache state.
3. Press `Tab` to move focus into the table and highlight `tlg0012.tlg003`
   (Homer, Epigrams). Leave the search box before pressing action keys so
   letters are not typed into the query.
4. Press `f`. A background worker downloads the TEI file; when done, the status
   line reads `stored tlg0012.tlg003 — open it (o)` and the state changes to
   `downloaded`.
5. Press `o` (or `Enter`) to open the work in the corpus browser
   (`tlg0012.tlg003: 17 documents`). It also appears in the corpus list for
   future sessions.
6. Return to `w`, highlight the work, and press `x` to delete it from the cache
   (`removed tlg0012.tlg003 from the cache`). Other keys: `a` fetches all works
   by the highlighted author; `r` refreshes.

### Adjudicate reviewer disagreements (`r`)

```bash
aegean tui --review alice.csv --review bob.csv --corpus analysis.json
```

1. Launch with two (or more) `--review` CSVs and `--corpus` (the saved
   annotated corpus from `aegean review export --annotate`). The app opens
   straight into **Annotation review (`r`)**, merging the CSVs with
   `merge_review_tables(..., on_conflict="report")` and filtering to `conflicts`
   when disagreements exist.
2. Inspect the highlighted token in the right pane: sentence context,
   diplomatic/regularized form state, evidence class and confidence, field
   predictions, numbered reviewer options, and offline lexicon evidence.
3. Press `1`, `2`, or `3` to pick a reviewer's option for the conflicted field,
   or press `e` to enter a custom value in the inline field editor. Press `a`
   to accept predictions, `d` to defer, or `x` to reject.
4. Use `n`/`p` to jump to the next or previous unresolved token, `f` to cycle
   filters (`all` / `unresolved` / `conflicts` / `flagged`), and `s` to save the
   resolved CSV atomically without altering immutable snapshot hashes.
5. Apply the saved CSV back to the corpus with
   `aegean review apply analysis.json merged.csv -o reviewed.json`.

### Run any CLI command from the console (`:`)

1. Press `:` to open the **command console** (scrolling output log above an
   `aegean>` prompt). The command map prints on entry.
2. Type `stats lineara --top 5` and press `Enter`:

   ```text
       lineara: top 5 words
   ┌───────────────────┬───────┐
   │ item              │ count │
   ├───────────────────┼───────┤
   │ KU-RO             │ 37    │
   │ SA-RA₂            │ 20    │
   │ KI-RO             │ 16    │
   │ *411-VS           │ 15    │
   │ A-TA-I-*301-WA-JA │ 11    │
   └───────────────────┴───────┘
   ```

3. Type `greek scan "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"` and press `Enter`:

   ```text
   —⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×
   hexameter: dactyl, dactyl, spondee, dactyl, dactyl, final; caesura: penthemimeral
   ```

4. A completion popup lists matching commands and descriptions as you type
   (`↑`/`↓` select, `Tab`/`Enter` accept, `Esc` dismisses), and inline ghost
   text previews the top match (`→` accepts). When the popup is closed, `↑`/`↓`
   browse command history. Slow or networked commands run on a background
   worker.
5. Press `Esc` to close completions, `Esc` again to blur the input, and `Esc` a
   third time to return to the previous screen.

---

## Reader details

### Editorial markers

Reader lines display each token's Leiden editorial status as plain text so it
stays readable under any theme:

| Editorial status | Marker in reader |
|---|---|
| certain | none |
| unclear | `?` after the token |
| restored | `[ ]` after the token |
| lost | `---` after the token |

Tokens imported from token-carrier EpiDoc files may also carry typed form
state. When those values differ from the displayed token, the reader appends
plain-text markers such as `[dipl. …]`, the regularized/normalized form, and
`[model …]` for the exact analyzer input. These annotations distinguish source
evidence from model input; the model form is never presented as an editorial
reading. Currently hosted epigraphy and papyri assets expose aggregate status
only and do not carry typed form state until rebuilt.

### Line-analysis popup

Pressing `Enter` or `a` on a reader line opens the script-appropriate analysis
popup and runs the first entry immediately:

- **Greek** (`greek`, `nt`, epigraphy corpora, fetched works):
  - `offline parser / tagger`: zero-dependency token, POS, and lemma table;
  - `neural pipeline`: UPOS, UD FEATS, lemma, and dependency parse (`[neural]`
    extra; downloads ~173 MB model on first run);
  - `neural + OOV reranker (weighted)`: neural pipeline with bundled OOV lemma
    reranking;
  - `lexicon glosses`: Dodson plus any active fetched dictionaries;
  - `metrical scansion`: automatic meter detection and scansion;
  - `IPA (reconstructed)`: Classical Attic transcription;
  - `translate (BYOAI, optional)`: active when a provider API key is configured.
- **Linear B / Cypriot**: `Greek reading + gloss` (phonetic value, Greek
  reading, gloss) and `signs (glyph + value)`.
- **Linear A** (`lineara`, `sigla`): `conventional values (Linear B-shared)` and
  `signs (glyph + value)`:

  ```text
  conventional values (Linear B-shared)

  word   conventional value
  -----  ------------------
  OLE+A  ole+a
  17     17

  Conventional Linear B-shared phonetic values.
  ```

- **Cypro-Minoan**: `signs (glyph only)`.

Neural and translation analyses run on a background worker behind an
`analyzing…` indicator; all other analyses render immediately. `Esc` or `q`
closes the popup.

---

## Global keys

These keys work on every screen (when no text input has focus):

| Key | Action |
|---|---|
| `h` | Home |
| `c` | Corpus browser |
| `g` | Greek workbench |
| `b` | Biblical Greek study screen |
| `l` | Library manager (packs, installed items, search, download/remove) |
| `r` | Annotation & conflict review (`ReviewScreen`) |
| `w` | Works library |
| `d` | Data store |
| `:` | Command console (run any `aegean` command) |
| `t` | Theme picker (live preview, persisted on `Enter`) |
| `?` | Help overlay |
| `Esc` | Blur focused input, or return to the previous screen |
| `ctrl+p` | Command palette (open corpus, jump to screen, fetch dataset, theme, help) |
| `q` | Quit |

---

## Screens

All nine screens call the shared library adapter, matching CLI behavior.

### Home (`h`)

1. **19-corpus overview.** Lists every browsable corpus with a one-line summary
   and cached status (read without loading corpus data): `lineara`, `linearb`,
   `cypriot`, `cyprominoan`, `greek`, `nt`, `apostolic-fathers`,
   `pseudepigrapha`, `damos`, `sigla`, `isicily`, `iip`, `iospe`, `igcyr`,
   `aphrodisias`, `crete`, `edh`, `byzantine`, and `homer-scholia`. Selecting a
   row opens it in the corpus browser (showing an inline download bar if
   uncached). `ddbdp` (57,331 papyri) and `patrologia` (33 *Patrologia Graeca*
   volumes, 6.79M words) are excluded from full in-memory browsing because of
   size: search `ddbdp` with `aegean db search ddbdp` and browse `patrologia`
   via the **Biblical Greek (`b`)** `LXX & Patristics` tab, `aegean find`, or
   `aegean bible commentary`.
2. **Global key legend**, showing the single-key shortcuts.

### Corpus browser (`c`)

Three panes from left to right:

1. **Corpus list**, flagging uncached datasets.
2. **Document table**, with a filter box (`/` focuses). Plain text filters by
   case-insensitive document ID; a sign pattern such as `KU-*-RO` runs a
   corpus-wide search on a background worker and reports matches in the status
   line.
3. **Reader**: token lines with editorial markers, word cursor (`←`/`→`) with
   live token inspector, inline interlinear gloss toggle (`i`), structural
   classification, and `KU-RO` / `to-so` balance checks when a total is stated.
   `Tab` cycles panes; `Enter` opens a document or (inside the reader) launches
   the line-analysis popup (`Enter` or `a`).

The browser accepts any corpus spec supported by the CLI, including fetched
Greek works by CTS ID (`tlg0012.tlg001`) and saved `.json` / `.db` files
(`aegean tui --corpus path/to/file.json`).

### Greek workbench (`g`)

A single text input at the top (with a live **Beta Code** toggle `b`; `/`
focuses the input) updates five offline tabs as you type:

- **pipeline** — per-token `sentence:index  text  UPOS  lemma`.
- **lexicon** — offline lexicon glosses (Dodson Koine plus any cached registry
  dictionaries).
- **scansion** — metrical scan with a selector covering all **10 classical
  meters** (hexameter, pentameter, trimeter, and Aeolic templates), printing
  foot glyphs and caesura or the non-scanning reason.
- **syllables** — hyphenated syllabification of the first word.
- **IPA** — reconstructed transcription word by word with an **Attic / Koine**
  period selector.

See [Greek NLP](Greek-NLP) and [Meters](Meters) for backend details.

### Biblical Greek (`b`)

Five-tab workspace over [`aegean.greek.bible`](New-Testament), driven by a
shared passage bar (`/` focuses, `r` reloads) and an edition selector covering
all **9 Greek NT editions** (`Nestle 1904`, `SBLGNT`, `SRGNT`, `BHP`,
`Tischendorf 8th`, `Westcott–Hort`, `Byzantine Majority`, `Antoniades 1904`,
`Textus Receptus`):

- **Interlinear** — reads any NT or Septuagint passage (`John 1.1-5`,
  `Gen 1.1-5`, `Ps 22.1-6`) with surface, lemma, Robinson morphology, Strong's
  number, and Koine gloss. Bundled offline samples cover John 1, Philemon 1,
  Gen 1:1–5, and LXX Ps 22:1–6; full books activate once cached.
- **Editions** — side-by-side collation across the 9 NT editions with word-level
  variant diffs (`nt-editions` asset).
- **Manuscripts** — extant 2nd–5th c. CE uncials and papyri (Sinaiticus `01`,
  Vaticanus `03`, Alexandrinus `02`, Ephraemi `04`, Bezae `05`, `032`,
  `P45`–`P75`) with original/corrected hand selector, diplomatic text, and
  *nomina sacra* expansion (`nt-witnesses` asset).
- **Word Study** — Strong's / Extended Strong's entry, etymological root tree,
  NT + LXX book counts, Robinson morphology distribution, and sample concordance
  for any Strong's ID (`G3056`) or Greek lemma (`ἀγάπη`, `λόγος`).
- **Septuagint (LXX)** — filterable catalogue of all 56 Septuagint books (Swete
  + Ecclesiastes), inline MT ↔ LXX Psalm conversion (`23` or `MT Ps 23`),
  inline passage reading (`Gen 1.1-5`, `Ps 22.1-6`, `Eccl 1:1-4`) with automatic
  offline interlinear glossing, and Greek concordance search.
- **Patristics** — filterable catalogue of 112 Greek patristic commentaries across
  11 Church Fathers and traditions (including 26 John Chrysostom `ogc*` series
  and 9 *Patrologia Graeca* volumes). Entering `ogc002060` or `PG073` reads
  excerpts inline; entering `ogc002060 ἀγάπη` or `PG073 λόγος` runs live search.

### Library manager (`l`)

Five-tab manager covering bundled corpora, 47 hosted datasets, Biblical and
Patristic bundles, 3,844 categorized Greek collection works, ~1,778 Perseus and
First1KGreek works, 112 commentaries, lexica, and neural models:

1. **Packs** — install (`f`) or remove (`x`) all 10 named packs (`biblical`,
   `church-fathers`, `patristic`, `ancient-greek`, `byzantine-pack`, `aegean`,
   `epigraphy`, `literary`, `lexica`, `neural`) with live installed/missing
   counts and sizes.
2. **Installed** — every local offline resource with disk footprint, `o` to
   open, and `x` to delete (bundled corpora cannot be removed).
3. **Corpora & Biblical** — filterable list of corpora, Biblical, Patristic,
   Classical, and Byzantine collections.
4. **Works & Commentaries** — filterable list of categorized Greek collection
   works, Perseus/First1KGreek works, and patristic commentaries.
5. **Lexica & Models** — hosted Greek dictionaries and neural model bundles.

Keys inside Library Manager: `/` focus filter, `f` download, `o` open, `x`
remove, `r` reload.

### Annotation review (`r`)

Split-pane interactive annotation and reviewer-disagreement workspace
(`ReviewScreen`), backed by `ReviewSession`.

**Three entry modes:**

1. **Single review CSV** (`full` schema or `editable` layout with its
   `.companion.json` sidecar): `aegean tui --review review.csv` (or enter the
   path in the top bar and press `Enter` / **Load**).
2. **Multi-reviewer conflict adjudication**: pass two or more CSVs from the same
   export together with `--corpus`:
   `aegean tui --review alice.csv --review bob.csv --corpus analysis.json` (or
   enter `alice.csv,bob.csv` in the top bar after setting a corpus). Runs
   `merge_review_tables(..., on_conflict="report")` and automatically switches
   the filter to `conflicts` when disagreements are present.
3. **Live corpus review queue**: enter a corpus id (for example `nt`) in the top
   bar to generate an on-demand queue via `to_review_table` (using calibrated
   risk ordering when calibrated confidence annotations exist).

**Layout:**

- **Left pane:** filterable token queue (`Status`, `Ref`, `Token`, `Lemma`,
  `Conf`).
- **Right pane:** token header and sentence context, diplomatic/regularized form
  state and damage/uncertainty flags, evidence class and confidence, per-field
  prediction vs. decision status (`lemma`, `pos`, `morph`, `head`, `deprel`),
  numbered reviewer disagreement options when merged, offline lexicon evidence,
  and an inline editor for `lemma`, `pos`, `morph`, `head`, `deprel`, `note`,
  and `evidence`.

**Review screen keys:**

| Key | Action |
|---|---|
| `a` | Accept displayed predictions for active fields on the current token |
| `e` | Focus the inline field editor (`Enter` or **Apply edits** commits) |
| `1` / `2` / `3` | Pick numbered reviewer option 1, 2, or 3 on a conflicted field |
| `d` | Defer active fields on the current token |
| `x` | Reject active fields on the current token |
| `n` / `p` | Jump to next / previous unresolved token |
| `f` | Cycle queue filter: `all` → `unresolved` → `conflicts` → `flagged` |
| `s` | Save review CSV atomically (preserves immutable snapshot hashes for `aegean review apply`) |
| `o` | Focus the top open/load input bar |

### Works library (`w`)

Searches the bundled catalogue of 1,778 Greek works (case-insensitive over
author and title, e.g. `plato`, `homer`, `Ἰλιάς`) and displays cache status. An
empty query lists downloaded works.

- `f` — fetch the highlighted work into the cache;
- `a` — fetch all works by the highlighted work's author;
- `o` (or `Enter`) — open a downloaded work in the corpus browser;
- `x` — remove the highlighted work from the cache;
- `r` — refresh.

Downloads run on a background worker with progress status; duplicate fetches for
an in-flight work are ignored. See [Greek Works and Books](Greek-Works-and-Books)
for citation addressing.

### Data store (`d`)

Displays two live reports plus cache actions:

1. **Environment report** (same checks as `aegean doctor`): Python and pyaegean
   versions, installed extras, data store location/size and partial downloads,
   neural model bundles, and analysis cache state.
2. **Dataset table** (same rows as `aegean data list`): all 47 hosted datasets
   with downloaded state, on-disk size, and license.
3. **Actions**: `f` downloads the highlighted dataset on a background worker,
   `x` deletes it from disk, and `r` refreshes both tables.

### Command console (`:`)

An embedded REPL with CLI parity. Run any command without the `aegean` prefix
(for example `stats lineara --top 5`, `bible compare John 1:18`, or
`bundle verify study.zip`). It shares the dispatcher and session corpus cache
with bare `aegean` / `aegean repl`, supporting `use CORPUS` and `:examples`.

Live completions cover 1-, 2-, and 3-level subcommands, flags, and domain values
(corpora, datasets, NT/LXX books, editions, manuscript sigla, meters,
dictionaries, formats): `↑`/`↓` pick, `Tab`/`Enter` accept, `Esc` closes the
popup, `Right`/`End` accepts inline ghost text. Press `i` or `/` to focus the
input. Long or networked commands run on a worker so the UI stays responsive.

Requires the `[cli]` extra (`typer` + `rich`); if missing (for example when
launching the TUI from Python without `[cli]`), the prompt displays
`pip install 'pyaegean[cli]'`.

---

## Theme picker (`t`)

Press `t` to preview installed Textual themes live with `↑`/`↓`. Press `Enter`
to apply and persist the selection to `tui.json`; press `Esc` to keep the
previewed theme for the current session only. Unknown theme names in `tui.json`
are ignored on startup.

---

## Command palette (`ctrl+p`)

`ctrl+p` opens a fuzzy palette covering screen navigation (including
`Go to Annotation review`), opening any corpus or downloaded work, jumping to
the Library Manager to fetch datasets, switching themes, and opening help.

---

## Troubleshooting

**`aegean tui` exits with a `[tui]` error:**

```text
aegean: the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'
```

Run `pip install "pyaegean[tui]"` (which also brings in the dependencies needed
for the `:` command console).

**Missing Aegean glyphs (boxes or blanks):** Install and select an Aegean-capable
font listed in
[Installation → Set up your terminal](Installation#set-up-your-terminal), and on
Windows set `PYTHONUTF8=1`.

**Theme configuration path:** Saved themes live in
`$XDG_CONFIG_HOME/pyaegean/tui.json` or `~/.config/pyaegean/tui.json`
(`C:\Users\<you>\.config\pyaegean\tui.json` on Windows). Delete the file to
reset to the default theme.

---

## See also

- [The CLI](CLI) — command-line interface and scripting flags.
- [CLI: Greek NLP & Review](CLI-Greek#review--aegean-review-) — exporting, merging, and applying review CSVs.
- [Greek Works and Books](Greek-Works-and-Books) — the ~1,778-work catalogue and citation schemes.
- [Greek NLP](Greek-NLP) and [Meters](Meters) — backends behind the Greek workbench.
- [Installation](Installation#set-up-your-terminal) — Aegean fonts and `PYTHONUTF8=1`.
