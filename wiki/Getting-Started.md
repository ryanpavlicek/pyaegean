# Getting Started

This guide is for people who have **never written a line of Python** — and maybe
never opened a "terminal." If you're a working linguist, philologist, or
epigrapher who wants to *use* pyaegean rather than develop it, you're in the right
place. We'll go from nothing installed to your first real result. Take it one step
at a time; nothing here can break your computer.

> Already comfortable with Python and `pip`? Skip ahead to
> [Installation](Installation) and the [Tutorial](Tutorial).

## What pyaegean is (in one breath)

It's a free toolkit, written in the Python language, for working with Ancient
Greek and the Aegean scripts (Linear A and B). You give it Greek text or a Linear A
inscription; it gives you back syllables, accents, metre, morphology, statistics,
and more. You drive it by writing very short snippets of Python — usually one or
two lines — which this documentation gives you ready to copy.

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

- **Windows:** press the Start key, type **PowerShell**, and open it.
- **macOS:** press ⌘+Space, type **Terminal**, and open it.
- **Linux:** open your **Terminal** app.

You'll see a prompt waiting for input. That's all a terminal is.

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

Your prompt will now show `(.venv)` at the start — that means the sandbox is on.

> **Windows note:** if PowerShell refuses to run the activate script with a
> message about "execution policy," run this once, then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Step 4 — Install pyaegean

With the environment active:

```bash
pip install pyaegean
```

> **Heads up:** pyaegean isn't on PyPI yet, so that exact command won't work until
> the first release. Until then, install from GitHub instead — same result:
> `pip install git+https://github.com/ryanpavlicek/pyaegean`

That's it — you now have the core library, the full Linear A corpus, and the Greek
NLP pipeline, all working **offline**. (The optional AI features need an extra
install and an API key; see the [AI Layer](AI-Layer) page when you want them.)

Check it:

```bash
python -c "import aegean; print(aegean.__version__, aegean.registered_scripts())"
# 0.1.0.dev0 ['greek', 'lineara']
```

## Step 5 — Run your first code

There are three ways to actually run Python. For research and exploration, we
**recommend Jupyter** (the third option) — but here are all three.

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
your own notes live together — ideal for exploring a corpus and keeping a record.

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

## Seeing Greek correctly

Polytonic Greek (with breathings and accents) displays fine in Jupyter and in
modern editors like VS Code. If accents look like boxes or question marks in a
plain Windows terminal, that's just the terminal font — use Jupyter or an editor,
or run `chcp 65001` first to switch the terminal to UTF-8. You never need a Greek
keyboard: type in [Beta Code](Greek-NLP#normalization--beta-code) and convert.

## Where to go next

- **[Tutorial](Tutorial)** — two complete, guided walkthroughs that answer a real
  research question, one in Linear A and one in Greek.
- **[Greek NLP](Greek-NLP)** — every Greek function with runnable examples.
- **[Linear A](Linear-A)** and **[Analysis](Analysis)** — the Aegean side.
- **[FAQ & Troubleshooting](FAQ)** — if something didn't go to plan.
