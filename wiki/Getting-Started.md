# Getting Started

This guide is for people who have **never written a line of Python**, and maybe
never opened a "terminal." If you're a working linguist, philologist, or
epigrapher who wants to *use* pyaegean rather than develop it, you're in the right
place. We'll go from nothing installed to your first real result. Take it one step
at a time; nothing here can break your computer.

> Already comfortable with Python and `pip`? Skip ahead to
> [Installation](Installation) and the [Tutorial](Tutorial).

> **Just want to try it first?** The core pipeline runs **in your browser**, nothing to
> install: [the web demo](https://ryanpavlicek.github.io/pyaegean/demo/) (Pyodide).

> **Prefer the terminal to Python?** Once you're installed (Steps 1–4), add the
> command line with `pip install "pyaegean[cli]"` and run **`aegean quickstart`**:
> a guided first five minutes (eight short steps, seven of them running a real
> command live on the bundled data, all offline). See [the CLI page](CLI#the-guided-tour-aegean-quickstart)
> for what it covers. For an app-like way in, `pip install "pyaegean[tui]"` adds
> **`aegean tui`**, a full-screen terminal cockpit to browse a corpus, run the live
> Greek workbench, and manage the data store, all offline and mouse-or-keyboard
> driven ([the TUI page](TUI)).

## What pyaegean is (in one breath)

It's a free toolkit, written in the Python language, for working with Ancient
Greek and the Aegean scripts (Linear A, Linear B, Cypriot, Cypro-Minoan). You give it Greek text or a Linear A
inscription; it gives you back syllables, accents, metre, morphology, statistics,
and more. You drive it by writing very short snippets of Python: usually one or
two lines: which this documentation gives you ready to copy.

## Step 1 — Install Python

pyaegean needs **Python 3.10 or newer**.

- **Windows / macOS:** go to [python.org/downloads](https://www.python.org/downloads/),
  download the latest installer, and run it.
  - **On Windows, tick the box "Add Python to PATH"** on the first screen of the
    installer. This one checkbox saves a lot of grief later.
- **Linux:** Python is almost certainly already installed. If not,
  `sudo apt install python3 python3-pip python3-venv` (Debian/Ubuntu).

To confirm it worked, open a terminal (next step) and type `python --version`
(on macOS/Linux you may need `python3 --version`). You should see something like
`Python 3.12.4`.

## Step 2 — Open a terminal

A "terminal" is just a window where you type commands instead of clicking.

- **Windows:** press the Start key, type **Windows Terminal** (or just
  **Terminal**), and open it; a PowerShell tab appears. It's the default on
  Windows 11 and free from the Microsoft Store on Windows 10, and it renders
  Greek (and the Aegean scripts) far better than the legacy console window.
- **macOS:** press ⌘+Space, type **Terminal**, and open it.
- **Linux:** open your **Terminal** app.

You'll see a prompt waiting for input. That's all a terminal is. (Later, when
you install the command line, [Installation → Set up your terminal](Installation#set-up-your-terminal)
has three small upgrades: Windows Terminal, fonts for the Linear A/B glyphs, and
Tab-completion.)

## Step 3 — Make a project folder with its own environment

A **virtual environment** is a private sandbox for one project's packages, so
pyaegean and its dependencies don't collide with anything else on your machine.
It's optional but strongly recommended, and it's two commands.

```bash
# make and enter a folder for your Greek work (call it whatever you like)
mkdir greek-work
cd greek-work

# create a virtual environment named ".venv"
python -m venv .venv
```

Now **activate** it (you do this each time you come back to the project):

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Your prompt will now show `(.venv)` at the start: that means the sandbox is on.

> **Windows note:** if PowerShell refuses to run the activate script with a
> message about "execution policy," run this once, then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Step 4 — Install pyaegean

With the environment active:

```bash
pip install pyaegean
```

That's it: you now have the core library and the full Linear A corpus, working
**offline** with zero third-party dependencies. The heavier Greek NLP backends:
treebank lookup, dictionary glossing, and the **neural pipeline** (the most accurate
tagger/parser/lemmatizer, one `greek.use_neural_pipeline()` call away): are opt-in:
each is fetched to a local cache the first time you turn it on, never bundled. See the
[Greek NLP](Greek-NLP) page when you want them. If you'd rather not write Python at
all, there's also a [command-line interface](CLI): `pip install "pyaegean[cli]"`,
and `aegean quickstart` then gives you the guided terminal-side tour (seven real
commands across eight steps, live on the bundled data, all offline).

Check it:

```bash
python -c "import aegean; print(aegean.__version__, aegean.registered_scripts())"
# 0.20.1 ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

## Step 5 — Run your first code

There are three ways to actually run Python. For research and exploration, we
**recommend Jupyter** (the third option), but here are all three.

### Option A — the interactive prompt (quickest)

Type `python` (or `python3`) and press Enter. You'll get a `>>>` prompt where you
can type one line at a time:

```python
>>> import aegean
>>> corpus = aegean.load("lineara")
>>> len(corpus)
1721
```

Type `exit()` to leave.

### Option B — a script file

Save the lines below into a file called `first.py`, then run `python first.py`:

```python
import aegean
corpus = aegean.load("lineara")
print("Linear A inscriptions:", len(corpus))
```

### Option C — Jupyter (recommended for research)

Jupyter gives you a notebook in your web browser where code, results, tables, and
your own notes live together: ideal for exploring a corpus and keeping a record.

```bash
pip install jupyterlab
jupyter lab
```

Your browser opens; click **Python 3** to make a new notebook, type a snippet into
a cell, and press **Shift+Enter** to run it. Results (including Greek text and
tables) appear right below the cell.

## Step 6 — Your first real result

Paste this anywhere you can run Python (a notebook cell is nicest):

```python
from aegean import greek

# Type Greek without a Greek keyboard, using plain ASCII "Beta Code":
greek.betacode_to_unicode("mh=nin")          # 'μῆνιν'

# Break a word into syllables and find its accent:
greek.syllabify("ἄνθρωπος")                  # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification    # 'paroxytone'

# Scan the first line of the Odyssey:
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

If you saw that pattern print out, **everything is working.**

## Step 7 — Find a real Greek work to read

The five-line `aegean.load("greek")` sample is just a taster. For the actual canon,
pyaegean ships an **offline discovery catalogue** of ~1,800 works: every text with a
Greek edition in the open Perseus and First1KGreek repositories, so you can look up an
id without leaving Python or going online:

```python
from aegean import greek

len(greek.catalog())                 # 1778  — the whole bundled index
hits = greek.catalog(author="euripides")
len(hits)                            # 21
hits[0]
# {'id': 'tlg0006.tlg001', 'author': 'Euripides', 'title': 'Cyclops',
#  'greek_title': 'Κύκλωψ', 'source': 'perseus'}
```

The same search from the shell (with `[cli]` installed), as a tidy table:

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

Pass any `id` you find straight to `greek.load_work("tlg0059.tlg002", ref="1")`, which
fetches the text (network on first use only, then cached). The catalogue is honest about
coverage: it lists exactly what the open repos hold, so a few authors that aren't online
upstream: Sappho, for one: simply aren't in it. See
[Greek Works and Books](Greek-Works-and-Books) for the full guide to loading works.

## Step 8 — Bring your own text

Have your own passage of Greek? Turn it into a real corpus — with the full
filter / search / analyse / export toolkit: in one call. No `Corpus` boilerplate:

```python
from aegean import io

corpus = io.from_text("λόγος δὲ καὶ ἀριθμός", doc_id="note")
len(corpus)                                         # 1
[t.text for t in corpus.get("note").words]          # ['λόγος', 'δὲ', 'καὶ', 'ἀριθμός']
```

`io.from_text_file("essay.txt")`, `io.from_text_dir("poems/")`, and
`io.from_csv("rows.csv")` do the same from a file, a folder, or a spreadsheet. From the
shell, `aegean import` writes the corpus to a `.json` or `.db` you can then feed to any
other command:

```bash
aegean import myplato.txt -o myplato.json
aegean stats myplato.json --top 5
```

(`aegean.load(...)` and the CLI corpus argument still expect a `.json`/`.db` corpus:
import a raw `.txt`/`.csv` first, as above.)

## Seeing Greek correctly

Polytonic Greek (with breathings and accents) displays fine in Jupyter and in
modern editors like VS Code. If accents look like boxes or question marks in a
plain Windows terminal, that's just the terminal font: use Jupyter or an editor,
or run `chcp 65001` first to switch the terminal to UTF-8. The Linear A/B
*glyphs* (𐙂, 𐀀) are a separate matter: they need a font that covers the Aegean
scripts, which [Installation → Set up your terminal](Installation#set-up-your-terminal)
walks through. You never need a Greek keyboard: type in
[Beta Code](Greek-NLP#normalization--beta-code) and convert.

## Where to go next

- **[Tutorial](Tutorial)**: two complete, guided walkthroughs that answer a real
  research question, one in Linear A and one in Greek.
- **[Greek NLP](Greek-NLP)**: every Greek function with runnable examples.
- **[Linear A](Linear-A)** and **[Analysis](Analysis)**: the Aegean side.
- **[FAQ & Troubleshooting](FAQ)**: if something didn't go to plan.
