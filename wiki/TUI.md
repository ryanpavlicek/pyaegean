# The terminal UI (`aegean tui`)

`aegean tui` is a full-screen, app-like cockpit for the pyaegean toolkit, running
entirely inside your terminal. Where [the CLI](CLI) is one command at a time and
`aegean repl` is those commands typed one after another, the TUI is a windowed
reader: a scrollable corpus browser, a live Greek workbench, a searchable
catalogue of ~1,800 Greek works you can fetch and open, the local data store, and
a command console with full CLI parity, all switched with a single keystroke.

It is a **focused cockpit over the same library the CLI uses**, not a second
product and not a mirror of every command. Everything it does is offline and needs
no API key: it is a research reader over the bundled and cached data, never the
key-gated, exploratory AI layer.

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

1. Run `aegean tui`. The app opens on **Home**: the undeciphered-script banner
   across the top, the corpus list below it with the first entry (`lineara`)
   already highlighted and focused, and the key legend at the bottom.
2. Press `c`. The **corpus browser** opens: the corpus list on the left (focused),
   an empty document table in the middle, and the reader on the right saying
   "Select a corpus on the left to browse its documents."
3. Press `↓`. The highlight lands on `lineara`, the first entry; `↑`/`↓` move it
   through the list (an entry whose data is not yet on disk carries a `· fetch` tag).
4. Press `Enter`. The corpus loads: the status line reads `lineara: 1721 documents`
   and the middle table fills with one row per document (id, site, period, words,
   structure). The reader now says "Select a document to read it."
5. Press `Tab`. Focus moves to the search box above the table (typing there filters
   by id). Press `Tab` again: focus moves into the document table, with the first
   row under the cursor; `↑`/`↓` move the row highlight.
6. Press `Enter`. The reader shows the highlighted document. For the first Linear A
   tablet that is: the id (`HT1`), a metadata line (`Haghia Triada · LMIB · Tablet ·
   HT Scribe 21`), the counts and structure line, the undeciphered caveat, then the
   numbered token lines with line 1 highlighted. The status line spells out the next
   move: `HT1 — Tab to the reader, then ↑/↓ to pick a line and Enter (or a) to analyze it`.
7. Press `Tab`. The reader gains focus: its border and its "reading" title turn
   accent-colored. `↑`/`↓` now move the highlighted **line cursor** through the
   text (PgUp/PgDn jump ten lines at a time, Home/End go to the first and last line).
8. Press `Enter` (or `a`). The **line-analysis popup** opens over the reader: the
   chosen line at the top, a short list of the analyses that fit its script, and the
   first one already run below (for a Linear A line, the exploratory transliteration
   table with its caveat). `↑`/`↓` and `Enter` in that list run a different analysis.
9. Press `Esc`. The popup closes and you are back in the reader, with the line
   cursor where you left it.
10. Press `?`. The help overlay lists every global key and what the command palette
    can do; `Esc` (or `q`, or `Enter`) closes it. Press `Esc` once more to walk back
    to Home, and `q` to quit.

One habit worth forming: `Esc` always exits a focused text box first and only then
navigates back, so when in doubt press `Esc` and look at where the focus went.

---

## Three everyday tasks

The same key-by-key style, for the three things a new user most often wants.

### Fetch DAMOS and browse it

DAMOS is the full Linear B corpus (~5,900 tablets), fetch-on-demand rather than
bundled. The data store is where it enters the local store.

1. Press `d`. The **data store** opens: the environment report tables first (versions,
   extras, store location, models, cache), then the dataset table listing the
   fetchable datasets with their state, on-disk size, and license.
2. Press `Tab` until the dataset table holds the focus (the report tables come first
   in the Tab order), then `↓` to the `damos-corpus` row.
3. Press `f`. The download runs on a background worker: the status line below the
   table reports `fetching damos-corpus…` and then `stored damos-corpus`, and the
   row flips to `downloaded` with its real size. A second `f` while a fetch is in
   flight is refused rather than starting a duplicate download.
4. Press `c`, move the highlight to `damos` in the corpus list, and press `Enter`.
   The whole corpus loads (allow a moment); the status line reads
   `damos: 5932 documents`.
5. Press `/` and type `KN`. The table narrows to the Knossos tablets and the status
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

### The undeciphered-corpus caveat

For the undeciphered corpora (`lineara`, `sigla`, `cyprominoan`) the reader header
carries, on every document:

> Linear A and Cypro-Minoan are undeciphered; structural analysis is exploratory,
> not a reading.

The Home banner states the same thing the moment the app opens. The deciphered
corpora (Greek, Linear B, Cypriot) carry no caveat.

### The line-analysis popup, script by script

The popup (`Enter` or `a` on a reader line) offers only the analyses that fit the
line's script, and runs the first available one immediately:

- **Greek** (the `greek` sample corpus, the NT, the inscription corpora, and
  fetched Greek works all read as script `greek`):
  - `offline parser / tagger`: an instant table of token, POS, and lemma from the
    zero-dependency pipeline;
  - `neural pipeline`: measured neural tags plus morphological features and a
    dependency parse; needs the `[neural]` extra, and downloads the model
    (~170 MB) on first run;
  - `IPA (reconstructed)`: the Attic transcription, word by word;
  - `translate (BYOAI, optional)`: only when a provider API key is configured.
    Without one the option is listed as
    `translate (BYOAI, optional)  ·  unavailable: set a provider API key (BYOAI) to enable — e.g. OPENAI_API_KEY`,
    and choosing it explains that instead of failing.
- **Linear B / Cypriot** (deciphered): `Greek reading + gloss` (each word, its
  sound value, the Greek word it writes, and a gloss) and `signs (glyph + value)`
  (each sign's glyph and phonetic value).
- **Linear A** (the bundled corpus and SigLA): `transliteration (exploratory)` and
  `signs (glyph + value)`, both carrying the caveat that Linear A is undeciphered.
  The values shown are the conventional, Linear-B-shared ones, and the output says
  so. The transliteration of a line of HT2, exactly as the popup renders it:

  ```text
  transliteration (exploratory)

  word   conventional value
  -----  ------------------
  OLE+A  ole+a
  17     17

  Linear A is undeciphered — these are hypothetical, shared-with-Linear-B values, not an established reading
  ```

- **Cypro-Minoan**: `signs (glyph only)`, with the note that Cypro-Minoan is
  undeciphered (no sound values are pretended).

The slow analyses (neural, translate) run on a background worker behind an
"analyzing…" line; everything else renders instantly. `Esc` (or `q`) closes the
popup.

---

## Keys

The same global keys work from every screen:

| Key | Action |
|---|---|
| `h` | Home |
| `c` | Corpus browser |
| `g` | Greek workbench |
| `w` | Works library |
| `d` | Data store |
| `:` | Command console (run any `aegean` command) |
| `t` | Theme picker (live preview, persists) |
| `?` | Help overlay |
| `Esc` | Back a screen, or exit a focused text box first |
| `ctrl+p` | Command palette (fuzzy: open a corpus, jump, fetch, theme…) |
| `q` | Quit |

`Esc` is two-stage: when a text input is focused it blurs the input and stays on
the screen, and a second `Esc` (nothing focused) walks back through the screens you
visited. At Home with no history it is a safe no-op. `?` opens a modal reference of
every key and everything the command palette can do; it dismisses on `Esc`, `q`, or
`Enter`.

---

## Screens

Six screens, each a pure view over the shared library adapter, so their numbers
(structure, accounting balances, pipeline output) match the CLI by construction.

### Home (`h`)

The landing view holds three things permanently:

1. **The undeciphered-script honesty banner.** Linear A and Cypro-Minoan are
   undeciphered, so any structural analysis of them is exploratory, not a reading.
   The banner states this the moment the app opens.
2. **The thirteen-corpus overview.** Each of the thirteen registered corpora with a
   one-line blurb and whether its data is already on disk, read without loading
   anything: `lineara`, `linearb`, `cypriot`, `cyprominoan`, `greek`, `nt`,
   `damos`, `sigla`, `isicily`, `iip`, `iospe`, `igcyr`, and `edh`. Selecting a
   corpus here jumps straight into the corpus browser with it open. The
   fourteenth loadable corpus, `ddbdp` (57,000 documentary papyri), is
   deliberately not listed: loading it whole is far too heavy for an interactive
   browser. Search it with `aegean db search ddbdp` from the command line or the
   command console instead.
3. **The global-key legend**, so navigation is discoverable without the palette.

### Corpus browser (`c`)

Three panes, left to right:

1. **The corpus list**, each corpus marked when its data is not yet on disk.
2. **The document table**, above a search box. Press `/` to focus the box. Typing
   filters the table by document id (case-insensitive); typing a sign pattern such
   as `KU-*-RO` also runs a corpus-wide word search and surfaces the matching words
   in the status line. That corpus-wide search runs on a background worker, so a
   keystroke never blocks the UI and a fresh keystroke supersedes the previous
   still-running search.
3. **The document detail (the reader)**: the token lines with their editorial status
   marked (unclear / restored / lost from the Leiden apparatus), the heuristic structure
   classification, and an accounting-balance analysis (the `KU-RO` / `to-so`
   reconciliation) whenever the document states a total. `Tab` cycles the panes; `Enter`
   on a document row opens its detail. The reader carries a "reading" border title that
   lights up when it holds focus, so it is obvious which pane is active.

**Analyze a line while you read.** With the reader focused, `↑`/`↓` (and PgUp/PgDn,
Home/End) move a highlighted **line cursor**, and `Enter` or `a` opens an **analysis
popup** for that line. What it offers depends on the script:

- **Greek** (alphabetic Greek, the NT, fetched Greek works): the **offline parser /
  tagger** (lemma + POS, instant), the **neural pipeline** (measured neural tags + a
  dependency parse; needs the `[neural]` extra, and downloads the model on first use),
  **IPA**, and **translation**. Translation is **optional** and requires a configured
  BYOAI provider (an API key such as `OPENAI_API_KEY`); when none is set the popup says
  so rather than pretending to translate. The neural and translation runs happen on a
  background worker, so the UI never blocks.
- **Linear B / Cypriot** (deciphered): the **Greek reading + gloss** of each word and
  the **sign values** (glyph + phonetic value).
- **Linear A / Cypro-Minoan** (undeciphered): the **sign glyphs** and, for Linear A, an
  **exploratory transliteration** — both plainly labelled as not a reading.

The corpus browser is not limited to the thirteen registered corpora. It resolves any
corpus spec the CLI accepts, so it also opens a **fetched Greek work** by its CTS
id (for example `tlg0012.tlg001`) or a saved `.json` / `.db` corpus **file**. This
is how a work fetched in the Works library (below) comes up for reading.

**Undeciphered-script honesty, at point of use.** For an undeciphered corpus
(`lineara`, `sigla`, `cyprominoan`) the detail pane shows the exploratory caveat
right where the analysis is read, matching the CLI and the docstrings. The
deciphered corpora (Greek, Linear B, Cypriot) carry no such caveat.

### Greek workbench (`g`)

A single text box at the top drives four tabs that re-render as you type (a short
debounce coalesces fast keystrokes; every backend is zero-dependency, offline, and
instant):

- **pipeline** — per-token analysis, each row `sentence:index  text  UPOS  lemma`,
  the sentence number kept so a multi-sentence line stays unambiguous.
- **scansion** — the metrical scan against a meter chosen in a small selector
  (**hexameter / pentameter / trimeter**): the foot glyphs and caesura, or a
  friendly "does not scan" message when the line does not fit the chosen meter.
- **syllables** — the syllabification of the first word, hyphenated.
- **IPA** — the reconstructed transcription word by word, with an **Attic / Koine**
  period selector so you can compare the two reconstructions.

A bad meter or an unscannable line arrives as a friendly message shown inside the
tab, never as a traceback. `/` focuses the input.

For the full account of what each of these does, see [Greek NLP](Greek-NLP) and
[Meters](Meters).

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
`aegean` prefix (for example `stats lineara --top 5`) and its output renders in a
scrolling log. It runs through the same dispatcher `aegean repl` uses, so `use
CORPUS` sets a session corpus, `:examples` works, and every command behaves
identically to the command line. As you type, a floating completion list offers
the matching command paths with a one-line description each (`↑`/`↓` to pick,
`Tab`/`Enter` to complete, `Esc` to close); the inline ghost-text still previews
the best match. Long or networked commands run on a worker so the console stays
responsive.

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

The TUI deliberately covers the highest-value offline reads, browsing and analyzing
a document, the Greek workbench, fetching and reading works, and the data store,
with the command console as a full-parity escape hatch for everything else. It is a
research cockpit, not a replacement for the command line: [the CLI](CLI) (and
`aegean repl`) remain the complete surface, and the exploratory, key-gated AI layer
stays there, off the TUI entirely.

## See also

- [The CLI](CLI) — the full command surface the TUI is a cockpit over.
- [Greek Works and Books](Greek-Works-and-Books) — the ~1,800-work catalogue and
  the Greek New Testament that the Works library fetches and opens.
- [Greek NLP](Greek-NLP) and [Meters](Meters) — what the Greek workbench tabs do.
- [Installation](Installation#set-up-your-terminal) — the Aegean fonts and
  `PYTHONUTF8=1` for correct glyph rendering.
