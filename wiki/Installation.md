# Installation

pyaegean is a Python toolkit for Ancient Greek and the Aegean syllabic scripts
(Linear A, Linear B, Cypriot, and Cypro-Minoan). This page covers installing the
core package and optional extras, verifying the setup, managing local data, and
configuring your terminal.

**The core install requires one command and zero third-party dependencies.** The
wheel contains Python code and bundled JSON only, so `import aegean` starts fast
and runs offline. Heavier tools (`pandas`, the neural Greek pipeline, AI
provider SDKs, plotting, the CLI, and the TUI) are optional extras installed
only when requested. Datasets and model bundles download only when you invoke a
command or function that uses them.

> New to Python or the command line? Start with
> **[Getting Started](Getting-Started)** for Python setup and virtual
> environments. To try the core pipeline without installing anything, open
> [the web demo](https://pyaegean.xyz/demo/).

## Requirements

- **Python 3.10 or newer.** Core `pyaegean` and all pure-Python, data, and
  interop extras are tested on Python 3.10–3.15. The `[neural]` and `[all]`
  extras currently require **Python 3.10–3.14** until upstream `onnxruntime`
  publishes Python 3.15 wheels on PyPI. Check your version with
  `python --version` (or `python3 --version` on macOS/Linux).
- Internet access is needed only for `pip install` and for downloading opt-in
  datasets or models on first use. Cached assets remain available offline.

## Install in one line

```bash
pip install pyaegean            # core: Linear A + Greek, zero hard deps
```

This installs the bundled Linear A corpus, the four Aegean script modules, the
Greek phonology and metre engine, and the analysis tools for offline use.

### Platform notes

| Platform | Recommended command |
| --- | --- |
| **Windows** | Open **PowerShell** and run `pip install pyaegean`. With multiple Pythons installed, use `py -m pip install pyaegean`. |
| **macOS** | Open **Terminal**. If `pip` is unavailable, use `python3 -m pip install pyaegean`. |
| **Linux** | On Debian/Ubuntu, install `sudo apt install python3-venv` first if needed, then `python3 -m pip install pyaegean`. |

> **Use a virtual environment** to isolate pyaegean and its extras from other
> projects:
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
> See [Getting Started](Getting-Started) for a step-by-step walkthrough,
> including the Windows PowerShell execution-policy fix.

## Optional extras

Install extras using `pyaegean[name]`. Quote the specifier so shells such as zsh
on macOS do not expand the square brackets:

```bash
pip install "pyaegean[ai]"          # generative AI provider SDKs
pip install "pyaegean[neural]"      # neural Greek pipeline and lemmatizer
pip install "pyaegean[interop]"     # spaCy/Stanza, plus CLTK on Python 3.13+
pip install "pyaegean[cli,interop]" # adapters plus interop CLI commands
pip install "pyaegean[cli,viz]"     # combine extras with commas
pip install "pyaegean[all]"         # bundled runtime extras; excludes [parquet], [viz-interactive], and framework adapters
```

Complete extras matrix:

| Extra | Pulls in | What it adds |
| --- | --- | --- |
| `pyaegean[data]` | `pandas>=2.2.2` | DataFrame interop (`corpus.to_dataframe()`) |
| `pyaegean[neural]` | `onnxruntime>=1.23`, `tokenizers>=0.20`, `numpy>=1.24` | neural Greek pipeline (`greek.use_neural_pipeline()`) and lemmatizer (`greek.use_neural_lemmatizer()`), without PyTorch |
| `pyaegean[spacy]` | `spacy>=3.8.13` | loss-aware spaCy `Doc` import/export |
| `pyaegean[stanza]` | `stanza>=1.13.0` | loss-aware Stanza `Document` import/export (installs Stanza's PyTorch runtime) |
| `pyaegean[cltk]` | `cltk>=2.5.1` | CLTK `Doc` import/export and explicit `Process` integration (Python 3.13+) |
| `pyaegean[interop]` | `spacy`, `stanza`, and (Python 3.13+) `cltk` | all available framework document adapters for the active Python version |
| `pyaegean[anthropic]` | `anthropic>=0.40` | Anthropic (default) AI provider |
| `pyaegean[openai]` | `openai>=1.55.3` | OpenAI provider |
| `pyaegean[grok]` | `openai>=1.55.3` | xAI Grok (OpenAI-API-compatible) |
| `pyaegean[openrouter]` | `openai>=1.55.3` | OpenRouter gateway (OpenAI-API-compatible) |
| `pyaegean[local]` | `openai>=1.55.3` | local OpenAI-compatible server (Ollama, LM Studio, llama.cpp, vLLM; no API key) |
| `pyaegean[gemini]` | `google-genai>=0.3` | Google Gemini provider |
| `pyaegean[ai]` | `anthropic`, `openai`, `google-genai` | all AI providers |
| `pyaegean[epidoc]` | `lxml>=5.0` | Linear B DAMOS EpiDoc reader and schema validation (writing and generic `io.from_epidoc` use the stdlib) |
| `pyaegean[geo]` | `geopandas>=0.14`, `shapely>=2.0.4` | geographic analysis and GeoJSON |
| `pyaegean[viz]` | `matplotlib>=3.8` | static plots (`aegean.viz`, `aegean plot`) |
| `pyaegean[viz-interactive]` | `plotly>=5` | interactive plots (`backend="plotly"`) |
| `pyaegean[parquet]` | `pyarrow>=16.1` | Parquet export (`io.to_parquet`) |
| `pyaegean[cli]` | `typer>=0.16`, `rich>=13`, `prompt_toolkit>=3.0` | [`aegean` command line](CLI), including interactive shell (`aegean` / `aegean repl`) |
| `pyaegean[tui]` | `textual>=8.0` + `cli` deps | [`aegean tui`](TUI) 9-screen terminal UI (home, corpus browser, Greek workbench, Biblical Greek, library manager, interactive annotation & conflict review, data store, works, command console) |
| `pyaegean[mcp]` | `mcp>=2` | `aegean-mcp` Model Context Protocol server for AI agents |
| `pyaegean[all]` | `ai`, `epidoc`, `geo`, `data`, `cli`, `viz`, `mcp`, `tui`, `neural` | full runtime stack; excludes `parquet`, `viz-interactive`, and framework adapters |

- **`[all]` includes `[neural]` and omits `[parquet]`, `[viz-interactive]`, and `[interop]`.**
  It installs ONNX Runtime, Tokenizers, and NumPy, while neural model weights
  still download on first use with SHA-256 verification. Parquet (`pyarrow`),
  interactive plots (`plotly`), and framework adapters (Stanza brings PyTorch)
  remain separate extras. See [Interoperability](Interoperability) for
  target-specific installs.
- **GPU inference for `[neural]`.** Replace the CPU wheel with a GPU wheel
  (`pip uninstall onnxruntime`, then `pip install onnxruntime-gpu` for NVIDIA or
  `onnxruntime-directml` on Windows). Provider selection detects the GPU and
  keeps CPU as fallback. Match the wheel to your CUDA version: PyPI's current
  `onnxruntime-gpu` targets CUDA 13; on CUDA 12, install
  `onnxruntime-gpu==1.25.*`. Override provider order with
  `PYAEGEAN_ORT_PROVIDERS`; see [Greek NLP](Greek-NLP#gpu-execution-and-batching).
- **`[grok]`, `[openrouter]`, `[local]`, and `[openai]` share the `openai` SDK**
  because all four use the OpenAI chat-completions API with different endpoints
  and keys (no key for `local`).
- **The AI layer is key-gated and exploratory.** Installing `[ai]` provides the
  client SDKs; you supply your own API key at runtime unless you use `local`
  (Ollama, LM Studio, llama.cpp). See [AI Layer](AI-Layer).

### Extras that add console commands

Installing `[cli]` adds `aegean` to your PATH; installing `[mcp]` adds
`aegean-mcp` (29 tools documented in [MCP Server](MCP)). Check immediately after
installation:

```bash
pip install "pyaegean[cli]"
aegean --version
# pyaegean 0.73.1
```

## Verify

Run this offline check against the bundled data:

```python
import aegean
print(aegean.__version__)                 # 0.73.1
print(aegean.registered_scripts())        # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
print(len(aegean.load("lineara")))        # 1721
print(len(aegean.load("greek")))          # 5  (bundled offline sample; full works
                                          #     via greek.load_work("tlg0012.tlg001"))

from aegean import greek
print(greek.betacode_to_unicode("mh=nin"))           # μῆνιν
print(greek.syllabify("ἄνθρωπος"))                    # ['ἄν', 'θρω', 'πος']
print(greek.scan_hexameter(
    "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος").pattern)     # —⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×
```

With `[cli]` installed:

```bash
aegean --version
# pyaegean 0.73.1

aegean info lineara
```

> The bundled Greek corpus is a five-document public-domain sample (Homer,
> Herodotus, Heraclitus, Sappho, Gospel of John). Fetch full texts by ID or pack;
> see [Greek Works & Books](Greek-Works-and-Books) and `aegean library packs`.

### Offline environment check: `aegean doctor`

With `[cli]` installed, `aegean doctor` inspects your local setup without making
network requests. It checks Python and pyaegean versions, importable optional
extras, data store location and writability, leftover partial downloads, neural
model bundles, and the analysis cache. Exit code `0` indicates a healthy setup;
exit code `1` prints each detected issue with its fix. Pass `--json` for
machine-readable output. See
[CLI: Corpora, Analysis & Data → doctor](CLI-Corpora#doctor--the-offline-environment-check).

## Offline & data

**Bundled inside the wheel (offline immediately):** the Linear A corpus and sign
inventories, the Cypriot IG XV 1 corpus (178 inscriptions + 2 samples), the
Linear B / Cypro-Minoan / Greek seed samples, bundled NT and Swete LXX samples,
the 1,778-work Perseus/First1KGreek catalogue (`greek.catalog()`), the 3,844-work
Greek library collections index (`greek.collections()`), the Dodson Koine
lexicon, and all phonology, metre, and analysis code.

**Fetched on demand into a user cache** (never bundled in the Apache-2.0 wheel;
SHA-256-verified on download and cached for offline reuse): 47 hosted assets
covering **8 categorized Ancient, Classical, Patristic, and Byzantine Greek
collections** (3,844 works across 1,414 authors, 64.35M tokens, including the
complete open Greek corpus of John Chrysostom), Biblical & Koine Greek (9 NT
editions, 13 early manuscripts, 56 LXX books including Ecclesiastes, Extended
Strong's), Patristic & Second Temple texts (*Patrologia Graeca*, Open Apostolic
Fathers, Old Testament Pseudepigrapha), seven Greek epigraphic corpora and DDbDP
documentary papyri (I.Sicily, IIP, IOSPE, IGCyr/GVCyr, Aphrodisias, Crete, EDH,
DDbDP), Byzantine vernacular Greek, Homer Multitext *Iliad* & *scholia*, DAMOS
Linear B, SigLA Linear A, five prebuilt lexica, AGDT/neural models, facsimile
imagery, and the local multi-script browser workbench (`workbench-app-v2.1.0`).

Use `aegean library` (or the TUI Library Manager via `l`) as the primary
resource manager, with `aegean data` available for low-level dataset cache
operations:

```bash
aegean library status                 # installed vs available assets and disk usage
aegean library packs                  # 10 named packs: biblical, church-fathers, patristic, ancient-greek, byzantine-pack, …
aegean library install biblical       # download a pack in one command
aegean library remove <name>          # remove cached datasets, works, or packs
aegean data list                      # live table of all 47 remote datasets
```

To package corpora (or retrieval pointers for non-commercial datasets),
citations, review tables, and receipts for transfer to another machine or
archive, use `aegean bundle create` (`aegean.bundle`). See
[Data & Provenance](Data-and-Provenance) for sizes, licenses, and the SHA-256
hosting policy.

Greek backends fetch small prebuilt artifacts instead of building from upstream
source: `greek.use_lsj()` fetches a ~15 MB index rather than ~270 MB of Perseus
TEI, and `greek.use_treebank()` / `use_tagger()` / `use_lemmatizer()` /
`use_parser()` share one ~15 MB AGDT-derived bundle instead of a 75 MB download
and local training. Each falls back to building from upstream source if a
prebuilt artifact is unavailable. The neural models are fetched only when you
call `greek.use_neural_lemmatizer()` or `greek.use_neural_pipeline()` under
`[neural]`.

### Cache location and overrides

`aegean data store` prints the cache directory and its contents:

```bash
aegean data store
#          local data store:
# C:\Users\<you>\.cache\pyaegean
#  (override with PYAEGEAN_CACHE)
```

By default, pyaegean uses your OS user-cache directory (`~/.cache/pyaegean` on
Linux/macOS, `%USERPROFILE%\.cache\pyaegean` on Windows). Set `PYAEGEAN_CACHE`
to relocate it to another disk, shared directory, or offline staging location:

```bash
# Windows (PowerShell)
$env:PYAEGEAN_CACHE = "D:\aegean-cache"

# macOS / Linux
export PYAEGEAN_CACHE=/data/aegean-cache
```

Pre-download packs with `aegean library install <pack>` or individual remote
datasets with `aegean data fetch <name>` (both skip already-cached valid files).
`aegean data versions` prints the reproducibility manifest (version and SHA-256
per dataset). See [Data & Provenance](Data-and-Provenance) for full source,
license, and citation details.

## Set up your terminal

Three adjustments improve terminal output, especially on Windows. (UTF-8
encoding for the legacy Windows console is covered in the next section.)

### Use Windows Terminal, not the legacy console

On Windows, run the CLI in **Windows Terminal** (default on Windows 11; free
from the Microsoft Store on Windows 10) instead of the legacy `conhost.exe`
console. Windows Terminal supports Unicode rendering, automatic font fallback,
and polytonic Greek with no extra configuration. Stock terminals on macOS
(Terminal, iTerm2) and Linux need no changes.

### Fonts for the Aegean scripts

Polytonic Greek (`μῆνιν ἄειδε θεά`) displays in default fonts on modern
terminals. Aegean glyphs such as `𐘇` (Linear A) and `𐀀` (Linear B) live in
Unicode's Supplementary Multilingual Plane, which most monospace fonts omit, so
glyph columns (`aegean stats lineara --signs`, `aegean sign lineara KU`) can
display empty boxes. Install the SIL Open Font License **Noto Sans** fonts from
[Google's Noto fonts](https://fonts.google.com/noto):

- **Noto Sans Linear A** and **Noto Sans Linear B**
- **Noto Sans Cypriot**
- **Noto Sans Cypro-Minoan**

Windows Terminal usually picks up these glyphs via automatic fallback; otherwise
set the font per profile under **Settings → your profile → Appearance → Font
face**. Some guides recommend George Douros's "Aegean" font, which covers all
four scripts in one file, but its 2024 license restricts free use to personal
purposes and requires a paid license for educational or commercial use. Without
Aegean glyph fonts installed, transliterations (`KU-RO`, `po-me`) still display
normally.

These fonts are especially helpful in [`aegean tui`](TUI), which displays
columns of Linear A and Linear B glyphs together. Run `aegean tui` with
`PYTHONUTF8=1` on Windows to keep Greek and Aegean glyphs displaying cleanly.

**Polytonic and epigraphic Greek.** Ordinary polytonic Greek requires no extra
font. For complete diacritic combinations and epigraphic/papyrological brackets
and underdots (used in corpora such as `isicily`), free classicist fonts include
**New Athena Unicode**, **Gentium Plus**, **Cardo**, and the **Greek Font
Society (GFS)** families, linked from the
[Digital Classicist Greek-fonts list](https://wiki.digitalclassicist.org/Greek_Fonts_(Unicode)).

### Shell completion

`aegean --install-completion` installs Tab-completion for the active shell. Open
a new shell afterward to complete commands and arguments such as
`aegean gre<Tab>`, `aegean greek syl<Tab>`, and `aegean bible read J<Tab>`
(including NT/LXX books, editions, and manuscript sigla).
`aegean --show-completion` prints the generated completion script for inspection:

- **bash**: writes `~/.bash_completions/aegean.sh` and sources it from `~/.bashrc`
- **zsh**: writes `~/.zfunc/_aegean` and wires it into `~/.zshrc`
- **fish**: writes `~/.config/fish/completions/aegean.fish`
- **PowerShell / pwsh**: appends the completer to `$PROFILE`

Running bare `aegean` in an interactive terminal launches the interactive shell
directly with inline ghost-text suggestions and dropdown completion across every
command, `--flag`, and domain value, with no shell setup required.

## Windows: seeing Greek correctly (UTF-8)

Polytonic Greek renders cleanly in Jupyter, VS Code, and Windows Terminal. In
the legacy Windows console, accents can render as boxes or `?`, and writing
Greek to a file or piping output can raise a `UnicodeEncodeError` under a legacy
code page.

Enable Python UTF-8 mode globally for your user account:

```powershell
# PowerShell — persist PYTHONUTF8 for your user account
setx PYTHONUTF8 1
# Open a new terminal afterward for the variable to take effect
```

Or enable it for the current session only:

```powershell
$env:PYTHONUTF8 = "1"
```

Running `chcp 65001` switches console display to UTF-8 for one session, while
`PYTHONUTF8=1` fixes file writes, subprocess pipes, and terminal output
together. macOS and Linux default to UTF-8 and do not need this step.

## Upgrading and uninstalling

```bash
pip install --upgrade pyaegean          # upgrade to the latest release
pip install --upgrade "pyaegean[all]"   # upgrade with extras
pip uninstall pyaegean                  # remove the package
```

Uninstalling leaves downloaded datasets intact in your local cache so reinstalls
do not re-download them. To reclaim disk space, run `aegean library remove` /
`aegean data remove --all` (or `aegean data remove NAME`), or delete the
directory shown by `aegean data store`.

## From source

To modify pyaegean or run the test suite, install an editable checkout with
`[dev]` (pytest, mypy, ruff, and build tools). Full contributor instructions are
on the [Development](Development) page:

```bash
git clone https://github.com/ryanpavlicek/pyaegean
cd pyaegean
pip install -e ".[dev]"
```

## Notes & limitations

- **Core install never downloads models or datasets.** Nothing is fetched until
  you call an opt-in backend or loader (such as `greek.use_treebank()` or
  `aegean.load("damos")`).
- **NonCommercial datasets stay outside the wheel.** DAMOS (Linear B), SigLA
  (Linear A), and NonCommercial Greek epigraphy/scholia corpora are fetched on
  demand under their own licenses. Facsimile imagery is for academic reference
  only. `aegean.bundle` keeps non-commercial datasets out of redistributable
  bundles by default, storing a retrieval pointer instead.
- **The AI layer requires your own API key** (or a local OpenAI-compatible
  server via the `local` provider) and labels all outputs exploratory. See
  [AI Layer](AI-Layer).
- **`aegean.__version__` matches the package release.** The release gate checks
  it against `pyproject.toml`, and the bundled-data manifest uses the same
  version string.

See [FAQ & Troubleshooting](FAQ) for common issues and
[Limitations](Limitations) for scope limits. Next steps:
[Getting Started](Getting-Started), [Tutorial](Tutorial),
[Greek NLP](Greek-NLP), or [Linear A](Linear-A).
