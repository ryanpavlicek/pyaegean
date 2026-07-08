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
  tagger** (lemma + POS, instant), the **neural pipeline** (the most accurate tags + a
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
identically to the command line. Long or networked commands run on a worker so the
console stays responsive.

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
