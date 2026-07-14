# Installation

pyaegean is a free Python toolkit for Ancient Greek and the Aegean syllabic
scripts (Linear A, Linear B, Cypriot, Cypro-Minoan). This page gets it onto your
machine on any platform, explains the optional add-ons, and shows you how to
confirm it works.

The good news for newcomers: **the core install is one command and has zero
third-party dependencies.** The wheel ships code and JSON only, so `import aegean`
is instant and works fully offline. Everything heavier (`pandas`, the Greek NLP
backends, the AI provider SDKs, plotting, the command line) is an *optional
extra* that you pull in only when you ask for it. Nothing is downloaded behind
your back.

> Brand new to Python and terminals? Start with **[Getting Started](Getting-Started)**,
> which walks you through installing Python, opening a terminal, and making a
> virtual environment before you run anything here. Want to try it with nothing
> installed at all? The core pipeline runs in your browser:
> [the web demo](https://pyaegean.xyz/demo/).

## Requirements

- **Python 3.10 or newer.** pyaegean is tested on 3.10, 3.11, 3.12, 3.13, and
  3.14. Check yours with `python --version` (you may need `python3` on
  macOS/Linux).
- An internet connection **only** for `pip install` and for the opt-in datasets
  the first time you turn them on. After that, everything you've fetched stays
  on disk and works offline.

## Install in one line

```bash
pip install pyaegean            # core: Linear A + Greek, zero hard deps
```

That gives you the full Linear A corpus, the Aegean scripts, the Greek phonology
and metre engine, and the analysis tools: all offline. The heavier Greek
backends and the AI layer are extras, described below.

### Platform notes

The command is the same everywhere; only the surrounding setup differs slightly.

| Platform | Recommended way to run it |
| --- | --- |
| **Windows** | Open **PowerShell**, then `pip install pyaegean`. If you have several Pythons, `py -m pip install pyaegean` targets your default. |
| **macOS** | Open **Terminal**. If `pip` isn't found, use `python3 -m pip install pyaegean`. |
| **Linux** | Most distros need the venv package first: `sudo apt install python3-venv` (Debian/Ubuntu), then `python3 -m pip install pyaegean`. |

> **Always prefer a virtual environment.** It keeps pyaegean and its add-ons in a
> private sandbox so they can't collide with other projects:
>
> ```bash
> python -m venv .venv
> # Windows (PowerShell):
> .venv\Scripts\Activate.ps1
> # macOS / Linux:
> source .venv/bin/activate
> pip install pyaegean
> ```
>
> See [Getting Started](Getting-Started) for the full beginner version, including
> the Windows execution-policy fix.

## Optional extras

Extras are installed with the `pyaegean[name]` syntax. Quote the whole thing:
some shells (notably zsh on macOS) treat square brackets specially:

```bash
pip install "pyaegean[ai]"        # the full generative AI layer
pip install "pyaegean[neural]"    # the measured neural Greek pipeline
pip install "pyaegean[cli,viz]"   # combine extras with a comma
pip install "pyaegean[all]"       # every runtime extra except [parquet]
```

The complete matrix:

| Extra | Pulls in | What it adds |
| --- | --- | --- |
| `pyaegean[data]` | `pandas>=2.2.2` | DataFrame interop (`corpus.to_dataframe()`) |
| `pyaegean[neural]` | `onnxruntime>=1.23`, `tokenizers>=0.20`, `numpy` | the neural Greek pipeline (`greek.use_neural_pipeline()`) and lemmatizer (`greek.use_neural_lemmatizer()`): torch-free |
| `pyaegean[anthropic]` | `anthropic>=0.40` | Anthropic (the default) AI provider |
| `pyaegean[openai]` | `openai>=1.55.3` | OpenAI provider |
| `pyaegean[grok]` | `openai>=1.55.3` | xAI Grok (OpenAI-API-compatible) |
| `pyaegean[openrouter]` | `openai>=1.55.3` | OpenRouter (OpenAI-API-compatible gateway to many models) |
| `pyaegean[gemini]` | `google-genai>=0.3` | Google Gemini provider |
| `pyaegean[ai]` | `anthropic`, `openai`, `google-genai` | the full AI layer (all providers) |
| `pyaegean[epidoc]` | `lxml>=5.0` | the Linear B DAMOS EpiDoc reader + schema validation (writing, and the generic `io.from_epidoc` reader, use the stdlib) |
| `pyaegean[geo]` | `geopandas>=0.14`, `shapely>=2.0.4` | geographic analysis / GeoJSON |
| `pyaegean[viz]` | `matplotlib>=3.8` | one-line plots (`aegean.viz`, `aegean plot`) |
| `pyaegean[viz-interactive]` | `plotly>=5` | interactive versions of the findspot/timeline/sign-network plots (`backend="plotly"`) |
| `pyaegean[parquet]` | `pyarrow>=16.1` | Parquet export (`io.to_parquet`) |
| `pyaegean[cli]` | `typer>=0.16`, `rich>=13`, `prompt_toolkit>=3.0` | the [`aegean` command line](CLI), including `aegean repl` |
| `pyaegean[tui]` | `textual>=8.0` + the `cli` deps (`aegean tui` is a CLI subcommand) | the [`aegean tui`](TUI) full-screen terminal UI (browse a corpus, the live Greek workbench, the data store) |
| `pyaegean[mcp]` | `mcp>=1.2` | the `aegean-mcp` Model Context Protocol server (for AI agents) |
| `pyaegean[all]` | `ai`, `epidoc`, `geo`, `data`, `cli`, `viz`, `mcp`, `tui`, `neural` | every runtime extra **except** `parquet` |

A few things worth knowing:

- **`[all]` includes `[neural]` but omits `[parquet]`.** It installs ONNX Runtime,
  Tokenizers, and NumPy, but neural model bundles still download lazily on first use and
  remain SHA-256 verified. Parquet remains a separate opt-in because it adds `pyarrow`.
- **The neural pipeline uses a GPU automatically when one is available.** Replace
  the CPU wheel with a GPU build (`pip uninstall onnxruntime`, then
  `pip install onnxruntime-gpu` for NVIDIA or `onnxruntime-directml` on Windows)
  and provider selection picks it up, with the CPU kept as fallback. Match the
  wheel to your CUDA version: PyPI's current `onnxruntime-gpu` targets CUDA 13; on
  a CUDA 12 system install `onnxruntime-gpu==1.25.*`. `PYAEGEAN_ORT_PROVIDERS`
  overrides the selection; see [Greek NLP](Greek-NLP#gpu-execution-and-batching).
- **`[grok]` and `[openai]` install the same SDK**: Grok speaks the OpenAI API,
  so it reuses the `openai` package with a different endpoint and key.
- **The AI layer is exploratory and key-gated.** Installing `[ai]` only adds the
  SDKs; you still supply your own API key at runtime, unless you run a model locally
  with the `local` provider (Ollama, LM Studio, llama.cpp), which needs no key.
  See [AI Layer](AI-Layer).

### Two extras that add command-line tools

Installing `[cli]` puts an `aegean` command on your PATH; installing `[mcp]` puts
an `aegean-mcp` command on your PATH (the MCP server an agent like Claude Code can
talk to). Both are declared as console scripts, so after a fresh install they're
ready to type:

```bash
pip install "pyaegean[cli]"
aegean --version
# pyaegean 0.47.0
```

The MCP server currently exposes these tools to a connected agent: `list_corpora`,
`corpus_info`, `show_document`, `search_signs`, `balance_accounts`, `query_corpus`,
`cite_corpus`, `geo_sites`, `data_status`, `greek_pipeline`, `greek_scan`,
`greek_catalog`, `greek_work`, `greek_gloss`, `greek_explain`, `corpus_diagnose`,
and `koine_gloss`.

## Verify

A 30-second check that the core and the Greek engine are working. None of this
touches the network: it all runs on the bundled, offline data:

```python
import aegean
print(aegean.__version__)                 # 0.47.0
print(aegean.registered_scripts())        # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
print(len(aegean.load("lineara")))        # 1721
print(len(aegean.load("greek")))          # 5  (bundled offline sample; real works
                                          #     via greek.load_work("tlg0012.tlg001"))

from aegean import greek
print(greek.betacode_to_unicode("mh=nin"))           # μῆνιν
print(greek.syllabify("ἄνθρωπος"))                    # ['ἄν', 'θρω', 'πος']
print(greek.scan_hexameter(
    "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος").pattern)     # —⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×
```

If you installed `[cli]`, the same checks from the shell:

```bash
aegean --version
# pyaegean 0.47.0

aegean info lineara
#                             aegean corpus: lineara
# ┌────────────────────┬───────────────────────────────────────────────────┐
# │ field              │ value                                             │
# ├────────────────────┼───────────────────────────────────────────────────┤
# │ documents          │ 1721                                              │
# │ words              │ 1381                                              │
# │ tokens             │ 6406                                              │
# │ signs_in_inventory │ 342                                              │
# │ source             │ GORILA (Godart & Olivier 1976–1985) …            │
# │ license            │ Apache-2.0 (corpus JSON); facsimile imagery …    │
# └────────────────────┴───────────────────────────────────────────────────┘
```

> The bundled Greek corpus is a tiny five-document public-domain sample (Homer,
> Herodotus, Heraclitus, Sappho, Gospel of John). To work with full texts, fetch
> them by id: see [Greek NLP](Greek-NLP).

### One-command check: `aegean doctor`

With `[cli]` installed, `aegean doctor` verifies the whole environment in one
run, entirely offline (no network, nothing downloaded): Python and pyaegean
versions, which optional extras are importable, the data store (location, size,
per-dataset state, leftover partial downloads, writability), the neural model
bundles, and the analysis cache. Exit code `0` means healthy; any issue prints
with its fix and the command exits `1`:

```bash
aegean doctor
```
```
                  versions
┌────┬──────────┬───────────────────────────┐
│    │ check    │ value                     │
├────┼──────────┼───────────────────────────┤
│ OK │ python   │ 3.14.4                    │
│ OK │ pyaegean │ 0.47.0                    │
│ OK │ platform │ Windows-11-10.0.26200-SP0 │
└────┴──────────┴───────────────────────────┘
…four more tables: optional extras, data store, neural model bundles, analysis cache…
doctor: all checks passed
```

A missing extra is informational (its row shows the `pip install` line), never
an issue: the zero-dependency core is a supported configuration. `--json` emits
the whole report as one machine-readable document. See
[CLI → doctor](CLI#doctor--the-offline-environment-check).

## Offline & data

Here's how the offline promise works in practice.

**What ships inside the wheel and works fully offline:** the Linear A
inscriptions and signs, the Aegean script inventories, the small Greek seed
sample, the ~1,800-work Greek discovery catalogue (`greek.catalog()`:
metadata only, not the texts), and all the phonology / metre / analysis code.
Nothing in that list ever needs the network.

**What is fetched on demand into a user cache** (never bundled, and only when you
explicitly ask for it): the fetchable corpora (the Greek inscription and papyri
collections, DAMOS, SigLA, the New Testament), the trained Greek backends, the
prebuilt dictionary indexes, and the facsimile imagery. Each download is `sha256`-verified and,
once on disk, stays offline forever after.

You can see the full catalogue from the shell (the `note` and `license` columns
are abridged here):

```bash
aegean data list
```

| name | what it is | size | license |
| --- | --- | --- | --- |
| `agdt-derived` | prebuilt AGDT lexicon + tagger/lemmatizer/parser models | ~25 MB | CC BY-SA 3.0 (from Perseus AGDT) |
| `lsj-index` | prebuilt LSJ lemma→entry index (`use_lsj()` prefers it over the 270 MB build) | ~15 MB | CC BY-SA 4.0 (Perseus) |
| `middle-liddell-index` | prebuilt Middle Liddell lemma→entry index (`use_lexicon("middle-liddell")` prefers it) | ~2.3 MB | public domain (1889); Perseus/Scaife digitization |
| `cunliffe-index` | prebuilt Cunliffe (Homeric) lemma→entry index | ~1.3 MB | public domain (1924); Scaife data MIT |
| `abbott-smith-index` | prebuilt Abbott-Smith (NT) lemma→entry index | ~130 KB | public domain (1922) |
| `damos-corpus` | DAMOS-derived Linear B corpus v2: ~5,900 tablets: `load("damos")` | ~3 MB | CC BY-NC-SA 4.0 (DAMOS, F. Aurora) |
| `sigla-corpus` | SigLA-derived Linear A dataset v4: 802 docs / 1,401 words: `load("sigla")` | ~1.2 MB | CC BY-NC-SA 4.0 (SigLA) |
| `nt-corpus` | Greek New Testament (Nestle 1904): 260 chapters / ~137,800 tokens: `load("nt")` | ~16 MB | CC0-1.0 (text public domain) |
| `isicily-corpus` | I.Sicily Greek inscriptions: 2,855 primary-Greek texts from ancient Sicily: `load("isicily")` | ~7 MB | CC BY 4.0 (I.Sicily: Prag et al., Oxford) |
| `iip-corpus` | IIP Greek inscriptions: 2,113 primary-Greek texts from Israel/Palestine: `load("iip")` | ~4 MB | CC BY-NC 4.0 (IIP: M. L. Satlow, Brown) |
| `iospe-corpus` | IOSPE Greek inscriptions: 1,194 texts of the Northern Black Sea: `load("iospe")` | ~4 MB | CC BY (IOSPE III, King's College London) |
| `igcyr-corpus` | IGCyr/GVCyr Greek inscriptions of Cyrenaica: 997 texts (Doric + verse): `load("igcyr")` | ~3 MB | CC BY-NC-SA 4.0 (IGCyr²/GVCyr², Bologna) |
| `edh-corpus` | EDH Greek inscriptions: 1,286 pure-Greek texts of the frozen (2021) Heidelberg dump: `load("edh")` | ~6 MB | CC BY-SA 4.0 (EDH, Heidelberg Academy) |
| `ddbdp-corpus` | DDbDP documentary papyri: 57,331 texts / ~4.4M tokens as SQLite + full-text search: `aegean db search ddbdp` (heavy: `load("ddbdp")`) | ~219 MB (~757 MB unpacked) | CC BY 3.0 (DDbDP / papyri.info) |
| `grc-lemma-neural` | GreTa seq2seq lemmatizer (int8 ONNX): the `[neural]` extra | ~232 MB | CC BY-SA 4.0 (derived) |
| `grc-joint` | joint tagger-parser-lemmatizer (quantized ONNX bundle): the `[neural]` extra | ~173 MB | CC BY-SA 4.0 (derived) |
| `lineara-images` | 3,368 facsimile/photo files | ~116 MB | © École Française d'Athènes & others: academic reference only |
| `workbench-app` | prebuilt Linear A Research Workbench web app: served by `aegean workbench` | ~3 MB | Apache-2.0 |
| `linearb-corpus` | a slot for a user-supplied Linear B export |— | bring-your-own |

For speed, the Greek backends prefer small **prebuilt** artifacts over building
from source: `greek.use_lsj()` fetches the ~15 MB index instead of downloading
~270 MB of Perseus TEI, and `greek.use_treebank()` / `use_tagger()` /
`use_lemmatizer()` / `use_parser()` share one ~15 MB AGDT-derived bundle instead
of a 75 MB download and minutes of training. If a prebuilt asset is ever
unreachable, each falls back to building from the upstream source. The two neural
models above are only used by the `[neural]` extra's
`greek.use_neural_lemmatizer()` and `greek.use_neural_pipeline()`.

### Where the cache lives, and how to move it

`aegean data store` prints the location and what's currently in it:

```bash
aegean data store
#          local data store:
# C:\Users\<you>\.cache\pyaegean
#  (override with PYAEGEAN_CACHE)
```

The default is your OS user-cache directory (e.g. `~/.cache/pyaegean` on
Linux/macOS, `%USERPROFILE%\.cache\pyaegean` on Windows). **Set the
`PYAEGEAN_CACHE` environment variable** to put it elsewhere: handy for a shared
drive, a larger disk, or a reproducible/offline machine:

```bash
# Windows (PowerShell)
$env:PYAEGEAN_CACHE = "D:\aegean-cache"

# macOS / Linux
export PYAEGEAN_CACHE=/data/aegean-cache
```

To pre-download a dataset (for example, before going offline) use
`aegean data fetch <name>`; it's idempotent and skips anything already cached.
`aegean data versions` prints the reproducibility manifest (every dataset's
version + sha256). See [Data & Provenance](Data-and-Provenance) for the full
story on sources, licenses, and citation.

## Set up your terminal

Three small upgrades make the command line noticeably nicer, especially on
Windows. (This is about the terminal *application*; the UTF-8 *encoding* fix for
classic-console Greek is the next section.)

### Use Windows Terminal, not the legacy console

On Windows, run the CLI in **Windows Terminal** (the default terminal on
Windows 11; free from the Microsoft Store on Windows 10) rather than the legacy
console host, the bare `conhost.exe` window older setups open. Windows Terminal
renders Unicode properly, falls back across installed fonts for glyphs the
selected font lacks, and defaults to fonts with polytonic Greek coverage; the
legacy console predates all of that. On macOS (Terminal, iTerm2) and Linux the
stock terminals are fine as they are.

### A font for the Aegean scripts

Polytonic Greek (μῆνιν ἄειδε θεά) displays correctly in the default fonts of
every modern terminal: nothing to install. The Aegean **glyphs** are different:
signs like 𐘇 (Linear A) or 𐀀 (Linear B) live in Unicode's Supplementary
Multilingual Plane, which most monospace fonts don't cover, so commands that
print glyph columns (`aegean stats lineara --signs`, `aegean sign lineara KU`)
can show boxes where the signs should be. Install the free **Noto Sans** fonts
for the scripts you use, from [Google's Noto fonts](https://fonts.google.com/noto)
(all are under the SIL Open Font License, so free for any use):

- **Noto Sans Linear A** and **Noto Sans Linear B** — the Aegean syllabaries,
- **Noto Sans Cypriot** — the Cypriot syllabary (the `cypriot` corpus),
- **Noto Sans Cypro-Minoan** — the undeciphered Cypro-Minoan signs.

Those four cover every script pyaegean renders. Windows Terminal then usually
finds the glyphs by automatic font fallback, and if not you can select a font
explicitly per profile under **Settings → your profile → Appearance → Font
face**. (You may see the "Aegean" font by George Douros recommended elsewhere;
it covers all four scripts in one file, but its license changed in 2024 to
personal-use only, with educational and commercial use now requiring a paid licence,
so the Noto fonts above are the free choice.) Nothing breaks without the fonts:
the transliterations (`KU-RO`, `po-me`) are plain text and always display; you
only miss the glyph rendering.

The fonts matter most in the **[`aegean tui`](TUI)**
full-screen terminal UI (`pip install "pyaegean[tui]"`), where whole columns of
Linear A and Linear B glyphs are on screen at once; the same Windows Terminal +
Noto Aegean fonts advice applies, and running the TUI with `PYTHONUTF8=1` keeps
Greek and Linear A displaying correctly.

**Polytonic and epigraphic Greek.** Ordinary polytonic Greek needs no special font. For the
fullest coverage (every accent combination, plus the brackets and underdots of the epigraphic /
papyrological texts that the inscription corpora such as `isicily` use), the
best **free** classicist fonts are **New Athena Unicode** (the de-facto scholarly standard, the most
complete), and the SIL Open Font License families **Gentium Plus** and **Cardo**, plus the **Greek
Font Society (GFS)** fonts. All are free for any use; New Athena Unicode and the GFS/OFL fonts are
downloadable from the [Digital Classicist Greek-fonts list](https://wiki.digitalclassicist.org/Greek_Fonts_(Unicode)).

### Shell completion

`aegean --install-completion` installs Tab-completion for the shell you run it
from (detected automatically); open a new shell afterward and
`aegean gre<Tab>`, `aegean greek syl<Tab>` complete. `aegean --show-completion`
prints the completion script instead, to inspect or wire in yourself. One line
per supported shell family:

- **bash**: writes `~/.bash_completions/aegean.sh` and sources it from `~/.bashrc`
- **zsh**: writes `~/.zfunc/_aegean` and wires it into `~/.zshrc`
- **fish**: writes `~/.config/fish/completions/aegean.fish`
- **PowerShell / pwsh**: appends the completer to your PowerShell `$PROFILE`

(Inside `aegean repl` you get Tab-completion of commands and options with no
setup at all: it's built into the shell.)

## Windows: seeing Greek correctly (UTF-8)

Polytonic Greek displays perfectly in Jupyter and in editors like VS Code. The
only place it can look wrong is the **classic Windows console**, where accents may
render as boxes or `?`, and, more importantly, writing Greek to a file or piping
output can raise a `UnicodeEncodeError` if the console is on a legacy code page.

The clean fix is to tell Python to use UTF-8 everywhere. Set this once and it
applies to every Python process:

```powershell
# PowerShell — persist PYTHONUTF8 for your user account
setx PYTHONUTF8 1
# open a NEW terminal afterward so the change takes effect
```

Or just for the current session:

```powershell
$env:PYTHONUTF8 = "1"
```

A lighter touch for a single terminal is `chcp 65001` (switch the console to
UTF-8), but `PYTHONUTF8=1` is more robust because it also fixes file writes and
subprocess output, not just the display. None of this is needed on macOS or
Linux, which are UTF-8 by default.

## Upgrading and uninstalling

```bash
pip install --upgrade pyaegean          # to the latest release
pip install --upgrade "pyaegean[all]"   # keep your extras when upgrading
pip uninstall pyaegean                  # remove the package
```

Uninstalling does **not** delete the downloaded datasets (they are permanent
local copies, kept so a reinstall never re-downloads). To reclaim that space,
run `aegean data remove --all` first (or `aegean data remove NAME` for one
dataset), or delete the directory shown by `aegean data store` yourself.

## From source

If you want to hack on pyaegean or run the test suite, install it editable from a
clone. The development extra (`[dev]`) pulls in pytest, mypy, ruff, and the rest
of the toolchain. Full instructions, including the typecheck/test gate, live on
the [Development](Development) page:

```bash
git clone https://github.com/ryanpavlicek/pyaegean
cd pyaegean
pip install -e ".[dev]"
```

## Notes & limitations

- **Core install never downloads models.** If you only `pip install pyaegean`, no
  dataset is ever fetched until you call something that needs it (e.g.
  `greek.use_treebank()` or `aegean.load("damos")`). That's by design.
- **Some datasets are NonCommercial (CC BY-NC-SA).** DAMOS (Linear B) and SigLA
  (Linear A) are not redistributed inside the package precisely because of their
  licenses: you fetch them yourself, under their terms. The facsimile imagery is
  for academic reference only. Mind the license column before reusing data.
- **The AI layer needs your own API key** (or a no-key local server via the `local`
  provider) and is explicitly exploratory; it does not ship a model. See
  [AI Layer](AI-Layer).
- **`aegean.__version__` reads installed package metadata.** If it ever prints
  `0.0.0+unknown`, the package metadata wasn't found (an unusual editable/zip
  setup): reinstall normally and it resolves.

For anything that didn't go to plan, see [FAQ & Troubleshooting](FAQ) and the
project-wide [Limitations](Limitations) page. To start using it, head to
[Getting Started](Getting-Started), the [Tutorial](Tutorial), or
[Greek NLP](Greek-NLP) and [Linear A](Linear-A).
