# The terminal UI (`aegean tui`)

`aegean tui` is a full-screen, app-like cockpit for the pyaegean toolkit, running
entirely inside your terminal. Where [the CLI](CLI) is one command at a time and
`aegean repl` is those commands typed one after another, the TUI is a windowed
reader: a scrollable corpus browser (with word cursor, live token inspector, and
inline interlinear gloss toggle), a live Greek workbench (with Beta Code mode,
all 10 meters, and lexicon glosses), a dedicated **Biblical Greek study screen**
(`b`: 5 NT editions, early manuscripts, Strong's word studies, LXX & Catenae), a
searchable catalogue of ~1,800 Greek works you can fetch and open, the local data
store, and a command console with full CLI parity, all switched with a single
keystroke.

It is a **focused cockpit over the same library the CLI uses**, not a second
product and not a mirror of every command. Its default reader and workbench views
work offline over bundled and cached data without an API key. Optional actions can
fetch works or neural models, and the analysis popup offers key-gated translation.

```bash
pip install "pyaegean[tui]"
aegean tui
```

The TUI ships as the `[tui]` extra (it adds [Textual](https://textual.textualize.io/)).
If the extra is not installed, `aegean tui` exits with a single line telling you
exactly that (`the TUI needs the [tui] extra, install it with: pip install
'pyaegean[tui]'`), the same way `aegean plot` guards `[viz]`.

On Windows the Aegean glyph columns render best with the Aegean fonts from
[Installation → Set up your terminal](Installation#set-up-your-terminal); run the
TUI with `PYTHONUTF8=1` so Greek and Linear A display correctly.

---

## Your first five minutes

A key-by-key tour from a cold start to reading and analyzing a real document. Every
step names the key you press and what the screen does in response.

1. Run `aegean tui`. The app opens on **Home** with the corpus list focused on
   `lineara` and the key legend at the bottom.
2. Press `c`. The **corpus browser** opens: the corpus list on the left (focused),
   an empty document table in the middle, and the reader on the right saying
   "Select a corpus on the left to browse its documents."
3. Press `↓`. The highlight moves through the list (an entry whose data is not yet
   on disk carries a `· fetch` tag; selecting it shows an inline **Download** bar
   where `f` downloads and opens it without leaving the browser).
4. Press `Enter` on `lineara`. The corpus loads: the status line reads
   `lineara: 1721 documents` and the middle table fills with one row per document
   (id, site, period, words, structure). The reader now says "Select a document to
   read it."
5. Press `Tab`. Focus moves to the search box above the table (typing there filters
   by id). Press `Tab` again: focus moves into the document table, with the first
   row under the cursor; `↑`/`↓` move the row highlight.
6. Press `Enter`. The reader shows the highlighted document. For the first Linear A
   tablet that is: the id (`HT1`), a metadata line (`Haghia Triada · LMIB · Tablet ·
   HT Scribe 21`), the counts and structure line, and the numbered token lines with
   line 1 highlighted. The status line shows the reader keys:
   `HT1 — Tab to reader: ↑/↓ line · ←/→ word · i interlinear · Enter/a analyze`.
7. Press `Tab`. The reader gains focus: its border and its "reading" title turn
   accent-colored. `↑`/`↓` now move the highlighted **line cursor** through the
   text (PgUp/PgDn jump ten lines at a time, Home/End go to the first and last line).
8. Press `Enter` (or `a`). The **line-analysis popup** opens over the reader: the
   chosen line at the top, a short list of the analyses that fit its script, and the
   first one already run below. `↑`/`↓` and `Enter` in that list run a different analysis.
9. Press `Esc`. The popup closes and you are back in the reader, with the line
   cursor where you left it.
10. Press `?`. The help overlay lists every global key and what the command palette
    can do; `Esc` (or `q`, or `Enter`) closes it. Press `Esc` once more to walk back
    to Home, and `q` to quit.

One habit worth forming: `Esc` always exits a focused text box first and only then
navigates back, so when in doubt press `Esc` and look at where the focus went.

---

## Managing texts, packs, and inline downloads

You never have to leave a screen or remember internal asset IDs to download missing data:

- **Inline downloads in Biblical Greek (`b`)**: selecting an edition (such as Byzantine
  Majority or SBLGNT), manuscript witnesses, full 27-book NT, Extended Strong's, or the
  55-book Septuagint when its bundle is not yet cached reveals a contextual **Download**
  bar right below the passage bar. Click **Download** (or press `f`) to download the exact
  bundle needed, or click **Biblical Pack** to install all 5 Biblical bundles at once; the
  active view reloads automatically when the download finishes.
- **Inline downloads in the Corpus Browser (`c`)**: selecting an uninstalled corpus
  (`damos`, `sigla`, `nt`, `isicily`, `iip`, `iospe`, `igcyr`, `edh`) reveals an inline
  **Download** bar (`f` downloads it in the background and opens it automatically).
- **Unified Library Manager (`l`)**: one tabbed manager across the entire toolkit:
  - **Packs**: one-click install (`f`) or remove (`x`) for `biblical`, `aegean`,
    `epigraphy`, `lexica`, and `neural`.
  - **Installed**: every bundled and downloaded resource currently on disk, with sizes,
    **Open (`o`)**, and **Remove (`x`)**.
  - **Corpora & Biblical**, **Works & Commentaries**, and **Lexica & Models**: filter with
    `/`, download with `f`, open with `o`, or remove with `x`.

---

## Three everyday tasks

The same key-by-key style, for the three things a new user most often wants.

### Fetch DAMOS and browse it

DAMOS is the full Linear B corpus (~5,900 tablets), downloaded on demand.

1. Press `c` to open the **corpus browser**, move the highlight to `damos`, and press
   `Enter`. An inline **Download** bar appears (`DAMOS Linear B Corpus (~3.0 MB)`).
2. Click **Download damos** (or press `f`). The download runs on a background worker and
   automatically opens DAMOS in the document table (`damos: 5932 documents`) when done.
   (Alternatively, press `l` to install the whole `aegean` pack — DAMOS + SigLA — in one
   click from the Library Manager.)
3. Press `/` and type `KN`. The table narrows to the Knossos tablets and the status
   line reads `4228 of 5932 documents match id 'KN'`. Press `Tab` to move into the
   filtered table and `Enter` on a row to read that tablet.

### Find a Greek work, fetch it, read it, remove it

The works library is where a Greek work enters the cache; the corpus browser is
where you read it.

1. Press `w`. The **works library** opens with the search box already focused; before
   you type anything it lists the works you have downloaded, and the status line
   invites a search of the ~1,800-work catalogue.
2. Type `epigrams`. The status line reads `3 matches` and the table shows the
   matching catalogue rows (id, author, title, source, state).
3. Press `Tab`. Focus moves into the results table; `↑`/`↓` pick a row, for example
   `tlg0012.tlg003` (Homer, Epigrams). Leave the search box before pressing an
   action key: while the box is focused, a letter is just text you are typing.
4. Press `f`. The fetch runs on a worker with a progress bar; on completion the
   status line reads `stored tlg0012.tlg003 — open it (o)` and the row's state
   flips to `downloaded`.
5. Press `o` (or `Enter`). The corpus browser opens with the work loaded, one row
   per book or section: `tlg0012.tlg003: 17 documents`. The work is now also a
   permanent entry in the corpus list (`tlg0012.tlg003 — Homer — Epigrams (Greek
   work)`), and reading works exactly as in the first-five-minutes tour: `Tab` to
   the table, `Enter` on a row, `Tab` to the reader, `Enter` on a line to analyze.
6. Press `w` to return to the library, highlight the work in the table, and press
   `x`. The status line reads `removed tlg0012.tlg003 from the cache`. The other
   action keys: `a` fetches every work by the highlighted row's author, `r`
   refreshes the view.

### Run any CLI command from the console

1. Press `:`. The **command console** opens: a scrolling output log on top and an
   `aegean>` prompt below it, already focused. The full command map prints on entry
   (the same menu `aegean repl` shows), so the available commands are visible before
   you type anything.
2. Type `stats lineara --top 5` and press `Enter`. The prompt line echoes into the
   log (`aegean> stats lineara --top 5`) and the command's output renders beneath
   it, styled the same as in the terminal CLI:

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

4. As you type, a completion list opens above the prompt showing the matching
   commands with a short description each: `↑`/`↓` pick one, `Tab` or `Enter`
   complete it, `Esc` closes the list. An inline ghost-text suggestion also
   previews the top match (`→` accepts it). With the list closed, `↑`/`↓` recall
   history. A long or networked command runs on a background worker, so the log
   keeps scrolling and the app stays responsive.
5. Press `Esc` to close the completion list if one is open, then once more to
   leave the prompt (it blurs), and again to go back to the screen you came from.

---

## What the reader shows you

### The editorial markers

Every token line in the reader carries the editorial status of its tokens, taken
from the Leiden apparatus of the source edition. The markers are plain text
appended to the token (not a color), so they read the same under every theme:

| Editorial status | Marker in the reader |
|---|---|
| certain | none (the token as read) |
| unclear | `?` after the token |
| restored | `[ ]` after the token |
| lost | `---` after the token |

A token imported from a token-carrier EpiDoc file
may also have typed form state. When those values differ from the displayed token,
the reader appends plain-text distinctions such as `[dipl. …]`, the selected
regularized or normalized form, and `[model …]` for the exact analyzer input.
These annotations are read-only evidence and input provenance. The model form is
not presented as a new editorial reading. The six currently hosted epigraphy and
papyri assets expose aggregate status only, so their reader lines do not gain this
typed state until their source assets are rebuilt.

### The line-analysis popup, script by script

The popup (`Enter` or `a` on a reader line) offers the analyses supported for the
line's script and runs the first available one immediately:

- **Greek** (`greek` sample, NT, inscription corpora, and fetched Greek works):
  - `offline parser / tagger`: token, POS, and lemma from the zero-dependency pipeline;
  - `neural pipeline`: UPOS, UD FEATS, lemma, and dependency parse (`[neural]` extra;
    downloads ~173 MB model on first run);
  - `neural + OOV reranker (weighted)`: neural pipeline with bundled OOV lemma reranking;
  - `lexicon glosses`: Dodson plus any active fetched dictionaries;
  - `metrical scansion`: automatic meter detection and scansion;
  - `IPA (reconstructed)`: Classical Attic transcription;
  - `translate (BYOAI, optional)`: active when a provider API key is configured.
- **Linear B / Cypriot**: `Greek reading + gloss` (phonetic value, Greek reading,
  and gloss) and `signs (glyph + value)`.
- **Linear A** (`lineara`, `sigla`): `conventional values (Linear B-shared)` and
  `signs (glyph + value)`. Example for a line of HT2:

  ```text
  conventional values (Linear B-shared)

  word   conventional value
  -----  ------------------
  OLE+A  ole+a
  17     17

  Conventional Linear B-shared phonetic values.
  ```

- **Cypro-Minoan**: `signs (glyph only)`.

Slow analyses (neural, translation) run on a background worker behind an
"analyzing…" status line; everything else renders immediately. `Esc` (or `q`) closes
the popup.

---

## Keys

The same global keys work from every screen:

| Key | Action |
|---|---|
| `h` | Home |
| `c` | Corpus browser |
| `g` | Greek workbench |
| `b` | Biblical Greek study screen |
| `w` | Works library |
| `d` | Data store |
| `:` | Command console (run any `aegean` command) |
| `t` | Theme picker (live preview, persists) |
| `?` | Help overlay |
| `Esc` | Back a screen, or exit a focused text box first |
| `ctrl+p` | Command palette (fuzzy: open a corpus, jump, fetch, theme…) |
| `q` | Quit |

`Esc` is two-stage: when a text input is focused it blurs the input and stays on
the screen, and a second `Esc` walks back through screen history. `?` opens a modal
key reference (`Esc`, `q`, or `Enter` dismisses).

---

## Screens

Seven screens over the shared library adapter, matching CLI outputs.

### Home (`h`)

The landing view holds:

1. **The thirteen-corpus overview.** Each registered corpus with a one-line summary
   and on-disk status (read without loading corpus files): `lineara`, `linearb`,
   `cypriot`, `cyprominoan`, `greek`, `nt`, `damos`, `sigla`, `isicily`, `iip`,
   `iospe`, `igcyr`, and `edh`. Selecting a row opens it directly in the corpus
   browser. `ddbdp` (57,000 documentary papyri) is omitted from the in-memory list
   due to size; search it with `aegean db search ddbdp` from the shell or command
   console.
2. **The global-key legend**, listing the single-key shortcuts for every screen.

### Corpus browser (`c`)

Three panes, left to right:

1. **The corpus list**, marking datasets not yet cached on disk.
2. **The document table**, above a search box (`/` focuses). Typing filters by
   document ID (case-insensitive); a sign pattern such as `KU-*-RO` runs a
   corpus-wide search on a background worker and displays matching words in the
   status line.
3. **The document detail (the reader)**: token lines with editorial status markers
   (unclear / restored / lost), word-level cursor (`←`/`→`) with live token
   inspector bar, inline interlinear gloss toggle (`i`), structural classification,
   and `KU-RO` / `to-so` balance checks when a document states a total. `Tab` cycles
   panes; `Enter` on a document row opens its detail.

**Analyze a line while you read.** With the reader focused, `↑`/`↓` (and PgUp/PgDn,
Home/End) move the line cursor, and `Enter` or `a` opens the analysis popup for that
line:

- **Greek** (`greek`, NT, epigraphy corpora, fetched Greek works): offline parser /
  tagger, lexicon glossing, automatic scansion, neural pipeline (with optional
  weighted OOV reranker and calibrated confidence), IPA, and optional BYOAI
  translation (passing neighboring lines and document metadata separately as
  `source_context`). Neural and translation calls run on a background worker.
- **Linear B / Cypriot**: Greek reading + gloss and sign values (glyph + phonetic
  value).
- **Linear A / Cypro-Minoan**: sign glyphs and, for Linear A, Linear B-shared
  conventional phonetic values.

The corpus browser accepts any corpus spec the CLI accepts, including fetched Greek
works by CTS ID (`tlg0012.tlg001`) and saved `.json` / `.db` corpus files.

### Greek workbench (`g`)

A single text box at the top (with a live **Beta Code** input toggle `b`) drives five
tabs that re-render as you type (a short debounce coalesces fast keystrokes; every
backend is zero-dependency, offline, and instant):

- **pipeline** — per-token analysis, each row `sentence:index  text  UPOS  lemma`,
  the sentence number kept so a multi-sentence line stays unambiguous.
- **scansion** — the metrical scan against a meter chosen in a selector covering all
  **10 classical meters** (hexameter, pentameter, trimeter, and the Aeolic lyric
  templates): the foot glyphs and caesura, or a friendly "does not scan" message when
  the line does not fit the chosen meter.
- **syllables** — the syllabification of the first word, hyphenated.
- **IPA** — the reconstructed transcription word by word, with an **Attic / Koine**
  period selector so you can compare the two reconstructions.
- **lexicon** — live offline lexicon glosses (Dodson Koine plus any cached registry
  lexica) for each word in the line.

A bad meter or an unscannable line arrives as a friendly message shown inside the
tab, never as a traceback. `/` focuses the input.

For the full account of what each of these does, see [Greek NLP](Greek-NLP) and
[Meters](Meters).

### Biblical Greek (`b`)

A dedicated five-tab specialist workspace over [`aegean.greek.bible`](New-Testament),
driven by a shared passage bar at the top (`/` focuses the passage box, `r` reloads)
with an edition selector (`Nestle 1904`, `SBLGNT`, `SRGNT`, `Byzantine Majority`,
`Textus Receptus`):

- **Interlinear** — reads any Greek NT passage (or Septuagint passage such as
  `Gen 1.1-5` / `Ps 22.1-6`) with word-by-word surface, lemma, Robinson morphology,
  Strong's number, and Koine gloss (works offline on John 1, Philemon 1, Gen 1:1–5,
  and LXX Ps 22:1–6; full books unlock once cached in the Data store).
- **Editions** — side-by-side comparison of the 5 Greek NT editions with word-level
  textual variant diffs (`nt-editions` asset).
- **Manuscripts** — extant 2nd–5th c. CE uncials and papyri (Sinaiticus `01`,
  Vaticanus `03`, Alexandrinus `02`, Ephraemi `04`, Bezae `05`, `032`, `P45`–`P75`)
  with original/corrected hand selector, diplomatic text, and *nomina sacra* expansions
  (`nt-witnesses` asset).
- **Word Study** — type any Strong's ID (`G3056`) or Greek lemma (`ἀγάπη`, `λόγος`)
  for Strong's / Extended Strong's gloss, etymological root tree, NT book & morphology
  distribution, and concordance verses.
- **LXX & Catenae** — filterable catalogue of all 55 Swete Septuagint books and 48
  Greek patristic commentaries (NT *Catenae* + Origen); typing a Psalm number (e.g.
  `23`) converts MT ↔ LXX inline, typing an LXX passage (e.g. `Gen 1.1-5` or
  `Ps 22.1-6`) renders the Greek verses inline, and typing a Greek word (e.g. `φῶς`)
  runs a live Septuagint concordance search.

### Works library (`w`)

The corpus browser reads works; the Works library is where a work **enters** the
cache. It searches the bundled Greek catalogue of roughly 1,800 works
(case-insensitive, by author or title, for example `plato`, `homer`, or `Ἰλιάς`),
and shows which works are already downloaded. On an empty query it lists your
downloaded library, so you can see what you already have. From here you can:

- **`f` — fetch the selected work** into the cache;
- **`a` — fetch every work by the selected work's author** in one step;
- **`o` (or `Enter`) — open a fetched work** in the corpus browser to read it;
- **`x` — remove a downloaded work** from the cache (the highlighted one);
- **`r` — refresh** the view.

Downloads run on a background worker with a progress indicator, so the UI stays
responsive, and a fetch already in flight is not restarted by a second press. The
catalogue and the addressing scheme are documented in
[Greek Works and Books](Greek-Works-and-Books), which also covers the **Greek New
Testament** (the `nt` corpus, Nestle 1904 with gold lemma, morphology, Strong's
numbers, and glosses).

### Data store (`d`)

Two read-only reports plus one action:

1. **The environment report**, verbatim from `aegean doctor`: the Python and
   pyaegean versions, which optional extras are importable, the local data store's
   location and total size (with any leftover partial-download files flagged), the
   neural model bundles, and the opt-in analysis cache.
2. **The dataset table**, the same per-dataset state `aegean data list` reports:
   every fetchable dataset, its download state, on-disk size, and license.
3. **`f` — fetch the highlighted dataset**, on a worker with a progress line that
   refreshes the row on completion and surfaces any failure as a one-line
   notification (never a crash). `r` refreshes the report and table from disk.

There is no remove action in the TUI by design (a deletion here is a footgun);
`aegean data remove` on the command line handles that.

### Command console (`:`)

A REPL inside the TUI with **full CLI parity**. Type any command **without** the
`aegean` prefix (for example `stats lineara --top 5` or `bible read John 1.1-5`)
and its output renders in a scrolling log. It runs through the same dispatcher
and session corpus cache as bare `aegean` / `aegean repl`, so `use CORPUS` sets
a session corpus, `:examples` works, and every command behaves identically to
the command line. As you type, a floating completion list offers context-aware
predictions across every command (1-, 2-, and 3-level nested subcommands,
including `bible` and `greek interop`/`conllu`/`annotation-profiles`),
deduplicated `--flag` options, and offline domain values (corpora, fetchable
datasets, NT/LXX books, NT editions, manuscript sigla, meters, dictionaries, and
output formats) with a one-line description each (`↑`/`↓` to pick, `Tab`/`Enter`
to accept, `Tab` on a blank argument to reopen, `Esc` to close); inline ghost
text previews the top history or live prediction (`Right`/`End` to accept). Long
or networked commands run on a worker so the console stays responsive.

The console needs the `[cli]` extra (typer + rich). If it is missing, the input is
disabled with a one-line message pointing you at `pip install 'pyaegean[cli]'`.
Press `i` or `/` to focus the input. This is the escape hatch that keeps the whole
command surface reachable from inside the TUI: the full query engine,
keyness/dispersion, plots, export/import, geo maps, `db build`, and the evaluation
reproductions all stay on the command line, and the console runs them in place.

---

## Theme picker (`t`)

Press `t` for a live-preview theme picker. Moving the highlight with `↑` / `↓`
applies each theme immediately, so you can try the whole list before committing.
`Enter` keeps **and persists** the highlighted theme (written to a small
`tui.json` in the config directory and loaded on the next launch); `Esc` closes
keeping whatever is currently previewed for this session, without persisting it. A
theme that no longer exists is ignored on load, so the app always starts on a valid
theme.

---

## Command palette (`ctrl+p`)

`ctrl+p` opens a fuzzy-searchable palette of everything the keys do: open any
corpus by name, jump to any screen, open a work you have already fetched, fetch a
not-yet-downloaded dataset, switch theme, or open the help reference. It is the
discoverability layer over the same navigation the key bindings drive.

---

## Troubleshooting

**`aegean tui` prints an error instead of starting.** Without the `[tui]` extra the
command exits (status 1) with exactly one line:

```text
aegean: the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'
```

`pip install "pyaegean[tui]"` fixes it, and includes the CLI dependencies the
command console uses. If the console screen ever reports `the command console needs
the [cli] extra — pip install 'pyaegean[cli]'` (possible when the TUI was launched
from Python in an environment without the CLI dependencies), that install line
fixes it the same way.

**Boxes or blanks where the Aegean glyphs should be.** The terminal font does not
cover the Linear A / Linear B / Cypriot / Cypro-Minoan Unicode blocks. Install and
select one of the fonts in
[Installation → Set up your terminal](Installation#set-up-your-terminal), and on
Windows run the TUI with `PYTHONUTF8=1` so the glyphs reach the terminal intact.

**Where the theme choice is stored.** `Enter` in the theme picker writes `tui.json`
under your config directory: `$XDG_CONFIG_HOME/pyaegean/tui.json` when
`XDG_CONFIG_HOME` is set, otherwise `~/.config/pyaegean/tui.json` (the same path
convention on Windows, for example `C:\Users\you\.config\pyaegean\tui.json`).
Deleting the file resets the theme; a persisted theme that no longer exists is
ignored on the next launch, so the app always starts on a valid one.

---

## Scope

The TUI covers interactive browsing and reading, the Greek workbench, the Biblical
Greek study screen, the works library, and the data store, with the `:` command
console running the rest of the CLI in place. For scripting and full-pipeline flags,
see [CLI Overview](CLI).

## See also

- [The CLI](CLI) — the full command surface the TUI is a cockpit over.
- [Greek Works and Books](Greek-Works-and-Books) — the ~1,800-work catalogue and
  the Greek New Testament that the Works library fetches and opens.
- [Greek NLP](Greek-NLP) and [Meters](Meters) — what the Greek workbench tabs do.
- [Installation](Installation#set-up-your-terminal) — the Aegean fonts and
  `PYTHONUTF8=1` for correct glyph rendering.
