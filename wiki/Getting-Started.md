# Getting Started

This guide assumes no prior experience with Python or a terminal. If you are a
linguist, philologist, or epigrapher who wants to use pyaegean for research,
follow the steps below in order from a clean machine to your first result.

> Already comfortable with Python and `pip`? Skip ahead to
> [Installation](Installation) and the [Tutorial](Tutorial).

> **Other ways to start without writing local Python first**
>
> - **In your browser.** The core pipeline runs client-side in
>   [the web demo](https://pyaegean.xyz/demo/) (Pyodide) with nothing installed.
> - **In a notebook.** [The getting-started notebook](https://github.com/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)
>   is a runnable guided tour you can step through locally or in the cloud
>   ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)).
> - **In the terminal.** After Steps 1–4, `pip install "pyaegean[cli]"` adds
>   **`aegean quickstart`**, an eight-step offline walkthrough that runs seven
>   live commands on the bundled data (see
>   [CLI → quickstart](CLI#guided-tour-aegean-quickstart)). Adding
>   `pip install "pyaegean[tui]"` installs **`aegean tui`**, a 9-screen terminal
>   UI for browsing corpora, running the Greek and Biblical workbenches,
>   reviewing annotations (`aegean tui --review`), and managing local resources
>   ([TUI](TUI)).

## What pyaegean does

pyaegean is a Python toolkit for Ancient Greek and the Aegean syllabic scripts
(Linear A, Linear B, Cypriot, and Cypro-Minoan). You pass it Greek text or an
Aegean inscription; it returns syllables, accents, scansion, morphology,
lemmatization, accounting checks, corpus queries, and statistics. Most common
tasks take one or two lines of Python or a single shell command.

## Step 1 — Install Python

pyaegean requires **Python 3.10 or newer**.

- **Windows / macOS:** download and run the installer from
  [python.org/downloads](https://www.python.org/downloads/).
  - **Windows:** check **"Add Python to PATH"** on the first installer screen.
- **Linux:** Python is usually preinstalled. On Debian/Ubuntu, install the
  packaging tools if missing:
  `sudo apt install python3 python3-pip python3-venv`.

Verify the install in a terminal (Step 2) with `python --version` (or
`python3 --version` on macOS/Linux). You should see a version such as
`Python 3.12.4`.

## Step 2 — Open a terminal

A terminal is a window where you run text commands directly.

- **Windows:** press Start, type **Windows Terminal** (or **Terminal**), and
  open it to start a PowerShell tab. It is the default on Windows 11 and free
  from the Microsoft Store on Windows 10, with much better Unicode support for
  Greek and Aegean scripts than the legacy console window.
- **macOS:** press ⌘+Space, type **Terminal**, and open it.
- **Linux:** open your **Terminal** app.

When you later install the CLI,
[Installation → Set up your terminal](Installation#set-up-your-terminal) covers
Aegean glyph fonts and shell tab-completion.

## Step 3 — Make a project folder with its own environment

A **virtual environment** isolates one project's packages from the rest of your
system. It is optional, strongly recommended, and takes two commands:

```bash
# Create and enter a project folder
mkdir greek-work
cd greek-work

# Create a virtual environment named ".venv"
python -m venv .venv
```

Activate it each time you open a new terminal for this project:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Your prompt now begins with `(.venv)`.

> **Windows note:** if PowerShell blocks the activation script with an
> execution-policy error, run this once and activate again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Step 4 — Install pyaegean

With the virtual environment active:

```bash
pip install pyaegean
```

This installs the core library and the full Linear A corpus with zero
third-party dependencies, ready for offline use. Optional Greek NLP backends
(treebank lookup, dictionaries, and the neural pipeline via
`greek.use_neural_pipeline()`) and downloadable corpora fetch on demand into a
local cache. Manage them with `aegean library` (or `aegean data`) after
installing the CLI extra (`pip install "pyaegean[cli]"`), or see
[Greek NLP](Greek-NLP) and [Data & Provenance](Data-and-Provenance).

Check the installation:

```bash
python -c "import aegean; print(aegean.__version__, aegean.registered_scripts())"
# 0.73.0 ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

## Step 5 — Run your first code

You can run Python in three ways. Jupyter (Option C) works well for research
notes and corpus exploration.

### Option A — the interactive prompt (quickest)

Run `python` (or `python3`) to open the `>>>` prompt and enter lines directly:

```python
>>> import aegean
>>> corpus = aegean.load("lineara")
>>> len(corpus)
1721
```

Type `exit()` to leave.

### Option B — a script file

Save the following lines to `first.py` and run `python first.py`:

```python
import aegean
corpus = aegean.load("lineara")
print("Linear A inscriptions:", len(corpus))
```

### Option C — Jupyter (recommended for research)

Jupyter runs a notebook in your browser where code, tables, Greek text, and
notes stay together:

```bash
pip install jupyterlab
jupyter lab
```

Create a **Python 3** notebook in the browser, paste code into a cell, and press
**Shift+Enter** to run it.

You can also open the ready-made
[getting-started notebook](https://github.com/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)
locally or in the cloud
([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)).
It is an independent tour and does not mirror this page step for step.

## Step 6 — Your first real result

Run these lines in Python or a notebook cell:

```python
from aegean import greek

# Type Greek in plain ASCII Beta Code:
greek.betacode_to_unicode("mh=nin")          # 'μῆνιν'

# Syllabify a word and inspect its accent:
greek.syllabify("ἄνθρωπος")                  # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification    # 'paroxytone'

# Scan the opening line of the Odyssey:
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

If that scansion pattern prints, the core library is working.

## Step 7 — Find a real Greek work to read

The bundled `aegean.load("greek")` corpus is a five-passage sample. For full
literary texts, pyaegean bundles an **offline discovery catalogue** of 1,778
works covering every Greek edition in the open Perseus and First1KGreek
repositories:

```python
from aegean import greek

len(greek.catalog())                 # 1778
hits = greek.catalog(author="euripides")
len(hits)                            # 21
hits[0]
# {'id': 'tlg0006.tlg001', 'author': 'Euripides', 'title': 'Cyclops',
#  'greek_title': 'Κύκλωψ', 'source': 'perseus'}
```

From the shell (with `[cli]` installed):

```bash
aegean greek catalog --author plato --limit 5
#                        Greek works (39 matches)
# ┌────────────────┬────────┬───────────┬────────────────────┬─────────┐
# │ id             │ author │ title     │ greek              │ src     │
# ├────────────────┼────────┼───────────┼────────────────────┼─────────┤
# │ tlg0059.tlg001 │ Plato  │ Euthyphro │ Εὐθύφρων           │ perseus │
# │ tlg0059.tlg002 │ Plato  │ Apology   │ Ἀπολογία Σωκράτους │ perseus │
# │ …              │ …      │ …         │ …                  │ …       │
# └────────────────┴────────┴───────────┴────────────────────┴─────────┘
```

Pass any `id` to `greek.load_work("tlg0059.tlg002", ref="1")` to fetch the text
to your local cache on first use. Coverage matches the pinned upstream
repositories, so authors absent upstream (such as Sappho) do not appear in the
catalogue. See [Greek Works & Books](Greek-Works-and-Books) for full loading
options.

## Step 8 — Bring your own text

Convert your own Greek string, text file, directory, or CSV into a `Corpus` with
`aegean.io`:

```python
from aegean import io

corpus = io.from_text("λόγος δὲ καὶ ἀριθμός", doc_id="note")
len(corpus)                                         # 1
[t.text for t in corpus.get("note").words]          # ['λόγος', 'δὲ', 'καὶ', 'ἀριθμός']
```

`io.from_text_file("essay.txt")`, `io.from_text_dir("poems/")`, and
`io.from_csv("rows.csv")` load files, folders, and spreadsheets in the same way.
From the shell, `aegean import` converts raw text or CSV into a `.json` or `.db`
corpus for other CLI commands:

```bash
aegean import myplato.txt -o myplato.json
aegean stats myplato.json --top 5
```

`aegean.load(...)` and CLI corpus arguments expect a `.json` or `.db` corpus, so
import raw `.txt` or `.csv` files first.

## Seeing Greek correctly

Polytonic Greek renders cleanly in Jupyter, modern editors such as VS Code, and
Windows Terminal. If accents appear as boxes or question marks in a legacy
Windows console, switch to Windows Terminal, set `PYTHONUTF8=1`, or run
`chcp 65001`. Aegean syllabic glyphs (`𐙂`, `𐀀`) require fonts covering those
Unicode blocks; [Installation → Set up your terminal](Installation#set-up-your-terminal)
lists the free Noto Sans fonts. You do not need a Greek keyboard: type ASCII
[Beta Code](Greek-NLP#normalization--beta-code) and convert it with
`greek.betacode_to_unicode(...)`.

## Where to go next

- **[Tutorial](Tutorial)**: three guided walkthroughs covering Linear A
  accounting, Homeric Greek analysis, and loading Perseus texts.
- **[Greek NLP](Greek-NLP)**: full reference for Greek functions and backends.
- **[Linear A](Linear-A)** and **[Analysis](Analysis)**: Aegean scripts and
  quantitative tools.
- **[FAQ & Troubleshooting](FAQ)**: answers to common install, Unicode, and data
  issues.
