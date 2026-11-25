# Installation

pyaegean is a free Python toolkit for Ancient Greek and the Aegean syllabic
scripts (Linear A, Linear B, Cypriot, Cypro-Minoan). This page gets it onto your
machine on any platform, explains the optional add-ons, and shows you how to
confirm it works.

**The core install is one command and has zero
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

- **Python 3.10 or newer.** Core `pyaegean` and all pure-Python / data / interop
  extras are tested on Python 3.10, 3.11, 3.12, 3.13, 3.14, and 3.15. The
  `[neural]` and `[all]` extras currently require **Python 3.10–3.14** until
  upstream `onnxruntime` publishes Python 3.15 wheels on PyPI. Check your
  version with `python --version` (you may need `python3` on macOS/Linux).
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
pip install "pyaegean[interop]"   # spaCy/Stanza, plus CLTK when Python is 3.13+
pip install "pyaegean[cli,interop]" # adapters plus the interop CLI commands
pip install "pyaegean[cli,viz]"   # combine extras with a comma
pip install "pyaegean[all]"       # bundled runtime extras; excludes [parquet], [viz-interactive], and framework adapters
```

The complete matrix:

| Extra | Pulls in | What it adds |
| --- | --- | --- |
| `pyaegean[data]` | `pandas>=2.2.2` | DataFrame interop (`corpus.to_dataframe()`) |
| `pyaegean[neural]` | `onnxruntime>=1.23`, `tokenizers>=0.20`, `numpy` | the neural Greek pipeline (`greek.use_neural_pipeline()`) and lemmatizer (`greek.use_neural_lemmatizer()`): torch-free |
| `pyaegean[spacy]` | `spacy>=3.8.13` | loss-aware spaCy `Doc` import/export |
| `pyaegean[stanza]` | `stanza>=1.13.0` | loss-aware Stanza `Document` import/export; Stanza installs its own PyTorch runtime |
| `pyaegean[cltk]` | `cltk>=2.5.1` | current CLTK `Doc` import/export and explicit `Process` integration; Python 3.13+ |
| `pyaegean[interop]` | `spacy`, `stanza`, and, on Python 3.13+, `cltk` | all available document adapters for the running Python |
| `pyaegean[anthropic]` | `anthropic>=0.40` | Anthropic (the default) AI provider |
| `pyaegean[openai]` | `openai>=1.55.3` | OpenAI provider |
| `pyaegean[grok]` | `openai>=1.55.3` | xAI Grok (OpenAI-API-compatible) |
| `pyaegean[openrouter]` | `openai>=1.55.3` | OpenRouter (OpenAI-API-compatible gateway to many models) |
| `pyaegean[local]` | `openai>=1.55.3` | local OpenAI-compatible server (Ollama, LM Studio, llama.cpp, vLLM); no API key |
| `pyaegean[gemini]` | `google-genai>=0.3` | Google Gemini provider |
| `pyaegean[ai]` | `anthropic`, `openai`, `google-genai` | the full AI layer (all providers) |
| `pyaegean[epidoc]` | `lxml>=5.0` | the Linear B DAMOS EpiDoc reader + schema validation (writing, and the generic `io.from_epidoc` reader, use the stdlib) |
| `pyaegean[geo]` | `geopandas>=0.14`, `shapely>=2.0.4` | geographic analysis / GeoJSON |
| `pyaegean[viz]` | `matplotlib>=3.8` | one-line plots (`aegean.viz`, `aegean plot`) |
| `pyaegean[viz-interactive]` | `plotly>=5` | interactive versions of the findspot/timeline/sign-network plots (`backend="plotly"`) |
| `pyaegean[parquet]` | `pyarrow>=16.1` | Parquet export (`io.to_parquet`) |
| `pyaegean[cli]` | `typer>=0.16`, `rich>=13`, `prompt_toolkit>=3.0` | the [`aegean` command line](CLI), including `aegean repl` |
| `pyaegean[tui]` | `textual>=8.0` + the `cli` deps (`aegean tui` is a CLI subcommand) | the [`aegean tui`](TUI) 8-screen terminal UI (corpus browser, Greek workbench, Biblical Greek, Library manager, works, data store, command console) |
| `pyaegean[mcp]` | `mcp>=2` | the `aegean-mcp` Model Context Protocol server (for AI agents) |
| `pyaegean[all]` | `ai`, `epidoc`, `geo`, `data`, `cli`, `viz`, `mcp`, `tui`, `neural` | the bundled runtime stack; excludes `parquet`, `viz-interactive`, and the separate framework adapters |

- **`[all]` includes `[neural]` but omits `[parquet]`, `[viz-interactive]`, and `[interop]`.** It installs ONNX Runtime,
  Tokenizers, and NumPy, but neural model bundles still download lazily on first use and
  remain SHA-256 verified. Parquet remains separate because it adds `pyarrow`, interactive
  plots remain separate because they add `plotly`, and the interoperability frameworks
  remain separate because Stanza adds a second PyTorch runtime.
  See [Interoperability](Interoperability) for target-specific installs and field support.
- **The neural pipeline uses a GPU automatically when one is available.** Replace
  the CPU wheel with a GPU build (`pip uninstall onnxruntime`, then
  `pip install onnxruntime-gpu` for NVIDIA or `onnxruntime-directml` on Windows)
  and provider selection picks it up, with the CPU kept as fallback. Match the
  wheel to your CUDA version: PyPI's current `onnxruntime-gpu` targets CUDA 13; on
  a CUDA 12 system install `onnxruntime-gpu==1.25.*`. `PYAEGEAN_ORT_PROVIDERS`
  overrides the selection; see [Greek NLP](Greek-NLP#gpu-execution-and-batching).
- **`[grok]`, `[openrouter]`, `[local]`, and `[openai]` install the same SDK**:
  all four speak the OpenAI chat-completions API, so they reuse the `openai` package
  with different endpoints and keys (none needed for `local`).
- **The AI layer is exploratory and key-gated.** Installing `[ai]` only adds the
  SDKs; you still supply your own API key at runtime, unless you run a model locally
  with the `local` provider (Ollama, LM Studio, llama.cpp), which needs no key.
  See [AI Layer](AI-Layer).

### Two extras that add command-line tools

Installing `[cli]` puts an `aegean` command on your PATH; installing `[mcp]` puts
an `aegean-mcp` command on your PATH (the MCP server an agent like Claude Code can
talk to; 23 tools documented in [MCP Server](MCP)). Both are declared as console
scripts, so after a fresh install they are ready to type:

```bash
pip install "pyaegean[cli]"
aegean --version
# pyaegean 0.68.0
```

## Verify

A 30-second check that the core and the Greek engine are working. None of this
touches the network: it all runs on the bundled, offline data:

```python
import aegean
print(aegean.__version__)                 # 0.68.0
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
# pyaegean 0.68.0

aegean info lineara
```

> The bundled Greek corpus is a five-document public-domain sample (Homer,
> Herodotus, Heraclitus, Sappho, Gospel of John). To work with full texts, fetch
> them by id or pack: see [Greek Works and Books](Greek-Works-and-Books) and
> `aegean library packs`.

### One-command check: `aegean doctor`

With `[cli]` installed, `aegean doctor` verifies the whole environment in one
run, entirely offline (no network, nothing downloaded): Python and pyaegean
versions, which optional extras are importable, the data store (location, size,
per-dataset state, leftover partial downloads, writability), the neural model
bundles, and the analysis cache. Exit code `0` means healthy; any issue prints
with its fix and the command exits `1`. `--json` emits the whole report as
machine-readable JSON. See
[CLI: Corpora, Analysis & Data → doctor](CLI-Corpora#doctor--the-offline-environment-check).

## Offline & data

**Bundled inside the wheel (offline immediately):** the Linear A corpus and sign
inventories, the Linear B / Cypriot / Cypro-Minoan / Greek seed samples, the
~1,778-work Greek discovery catalogue (`greek.catalog()`), the Dodson Koine
lexicon, and all phonology, metre, and analysis code.

**Fetched on demand into a user cache** (never bundled in the Apache-2.0 wheel;
SHA-256-verified on download and cached offline thereafter): the 39 hosted
datasets covering Biblical & Koine Greek (9 NT editions, 13 early manuscripts,
55 LXX books, Extended Strong's), Patristic & Second Temple texts (*Patrologia
Graeca*, Open Apostolic Fathers, Old Testament Pseudepigrapha), Greek epigraphy
and papyri (I.Sicily, IIP, IOSPE, IGCyr/GVCyr, Aphrodisias, Crete, EDH, DDbDP),
Byzantine vernacular Greek, Homer Multitext *Iliad* & *scholia*, DAMOS Linear B,
SigLA Linear A, five prebuilt lexica, AGDT/neural models, and facsimile imagery.

Manage them from the CLI (`aegean library`) or the TUI Library Manager (`l`):

```bash
aegean library status                 # summary of installed vs available assets
aegean library packs                  # 7 one-command packs: biblical, patristic, aegean, epigraphy, literary, lexica, neural
aegean library install biblical       # download a whole pack at once
aegean data list                      # live table of all 39 remote datasets
```

For the full dataset catalog, sizes, SHA-256 hosting policy, and exact licenses,
see [Data and Provenance](Data-and-Provenance).

For speed, the Greek backends prefer small **prebuilt** artifacts over building
from source: `greek.use_lsj()` fetches the ~15 MB index instead of downloading
~270 MB of Perseus TEI, and `greek.use_treebank()` / `use_tagger()` /
`use_lemmatizer()` / `use_parser()` share one ~15 MB AGDT-derived bundle instead
of a 75 MB download and minutes of training. If a prebuilt asset is ever
unreachable, each falls back to building from the upstream source. The two neural
models are only used by the `[neural]` extra's `greek.use_neural_lemmatizer()`
and `greek.use_neural_pipeline()`.

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

- **Noto Sans Linear A** and **Noto Sans Linear B**: the Aegean syllabaries,
- **Noto Sans Cypriot**: the Cypriot syllabary (the `cypriot` corpus),
- **Noto Sans Cypro-Minoan**: the undeciphered Cypro-Minoan signs.

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
`aegean gre<Tab>`, `aegean greek syl<Tab>`, and `aegean bible read J<Tab>`
complete (including NT/LXX books, editions, and manuscript sigla).
`aegean --show-completion` prints the completion script instead, to inspect or
wire in yourself. One line per supported shell family:

- **bash**: writes `~/.bash_completions/aegean.sh` and sources it from `~/.bashrc`
- **zsh**: writes `~/.zfunc/_aegean` and wires it into `~/.zshrc`
- **fish**: writes `~/.config/fish/completions/aegean.fish`
- **PowerShell / pwsh**: appends the completer to your PowerShell `$PROFILE`

(Running bare `aegean` in an interactive terminal opens the interactive shell
directly with live inline ghost-text suggestions and dropdown completion across
every command, `--flag`, and domain value — no shell setup required.)

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
  dataset is fetched until you call something that needs it (e.g.
  `greek.use_treebank()` or `aegean.load("damos")`).
- **Some datasets are NonCommercial (CC BY-NC-SA).** DAMOS (Linear B) and SigLA
  (Linear A) are not redistributed inside the package precisely because of their
  licenses: you fetch them yourself, under their terms. The facsimile imagery is
  for academic reference only. Mind the license column before reusing data.
- **The AI layer needs your own API key** (or a no-key local server via the `local`
  provider) and is explicitly exploratory; it does not ship a model. See
  [AI Layer](AI-Layer).
- **`aegean.__version__` is the package release identity.** The release gate checks it
  against `pyproject.toml`, and the bundled-data manifest uses the same value.

For anything that didn't go to plan, see [FAQ & Troubleshooting](FAQ) and the
project-wide [Limitations](Limitations) page. To start using it, head to
[Getting Started](Getting-Started), the [Tutorial](Tutorial), or
[Greek NLP](Greek-NLP) and [Linear A](Linear-A).
