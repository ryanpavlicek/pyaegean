# pyaegean

**A specialist Python toolkit for Ancient Greek and the Aegean syllabic scripts**:
alphabetic Greek, Linear A, Linear B, Cypriot, and Cypro-Minoan. It combines a
script-agnostic corpus layer, Greek NLP, research tools, translation grounding,
and an optional multi-provider AI layer.

> **Latest PyPI release: v0.50.0 (beta).** The API may still shift before 1.0.
> This wiki documents the current release. See the
> [changelog](https://github.com/ryanpavlicek/pyaegean/blob/main/CHANGELOG.md)
> for release history.

Analytical and generative output on undeciphered Linear A and Cypro-Minoan is
**exploratory**: it can suggest leads for expert review, never ground truth. The
[Limitations](Limitations), [Benchmarks](Benchmarks), and
[Data & Provenance](Data-and-Provenance) pages state what is measured, what is
not known, and where every dataset comes from.

## Choose where to start

- **New to Python or pyaegean?** [Getting Started](Getting-Started) goes from
  installation to a first result without assuming programming experience.
- **Working on a research question?** [Choosing a Workflow](Choosing-a-Workflow)
  maps tasks to tools, and [Tutorial](Tutorial) plus [Recipes](Recipes) provide
  complete examples.
- **Prefer the terminal?** Install `pyaegean[cli]`, run `aegean quickstart`, and
  use the [CLI guide](CLI) or compact [CLI cheatsheet](CLI-Cheatsheet). The
  `[tui]` extra adds the full-screen terminal UI.
- **Choosing a Greek backend?** [Choosing a Pipeline](Choosing-a-Pipeline)
  explains the deterministic, treebank, pure-Python, and neural options in plain
  language before the full [Greek NLP](Greek-NLP) reference.
- **Something not working?** [FAQ & Troubleshooting](FAQ) starts with the common
  install, data, model, Unicode, and network failures.

## Quick start

```python
import aegean

corpus = aegean.load("lineara")          # 1,721 inscriptions, bundled, offline
print(len(corpus))                       # 1721

ht = corpus.filter(site="Haghia Triada") # filter by metadata (site name)
corpus.word_frequencies()[:5]             # most common words

from aegean.analysis import balance_check, word_matches_sign_pattern
checks = balance_check(corpus.get("HT13"))          # KU-RO accounting reconciliation
hits = [w for w, _ in corpus.word_frequencies()
        if word_matches_sign_pattern(w, "KU-*-RO")] # wildcard sign search
```

```python
from aegean import greek
greek.betacode_to_unicode("mh=nin")          # 'μῆνιν'
greek.syllabify("ἄνθρωπος")                  # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification    # 'paroxytone'
```

## What's here

| Module | What it does |
| --- | --- |
| [`aegean.core`](Architecture) | Script-agnostic model: `Corpus`, `Document`, `Token`, `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance, a lossless JSON round-trip, typed `SourceAlignment` and `TokenFormState`, and a compound `query()` |
| [Linear A](Linear-A) | Bundled 1,721-inscription corpus, the full Unicode Linear A repertoire (342 signs; 50 carry conventional sound values), sign→sound map, transliteration |
| [Linear B](Linear-B) | Mycenaean Greek: 211-sign Unicode inventory, transliteration, a Greek-reading bridge (`po-me → ποιμήν`), accounting, the full DAMOS corpus on demand (`aegean.load("damos")`, ~5,900 tablets) |
| [Cypriot](Cypriot) | Chiefly Arcado-Cypriot Greek (the corpus also carries Eteocypriot and undetermined material): 55-sign Unicode syllabary, transliteration, a Greek-reading bridge (`pa-si-le-u-se → βασιλεύς`), and a bundled **178-inscription corpus** (*Inscriptiones Graecae* XV 1, BBAW, CC BY 4.0) plus two illustrative samples (**180 documents** total) |
| [Cypro-Minoan](Cypro-Minoan) | Undeciphered Bronze Age Cyprus: 99-sign Unicode inventory + sign-sequence tokenization (no phonetics or bridge: the script is undeciphered) |
| [Analysis](Analysis) | Accounting checks, sign-pattern and phonetic search, cross-script comparison, clustering, collocation and corpus statistics, structure detection, and a query engine |
| [Greek NLP](Greek-NLP) | Core text utilities, named source-preserving sentence policies, metre, IPA, tagging, morphology, lemmatization, parsing, dictionaries, and 1,778 discoverable works; optional treebank, pure-Python, and neural backends, with the neural pipeline measured at 97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.6 LAS on the UD Perseus test fold |
| Greek corpora ([Data & Provenance](Data-and-Provenance)) | Beyond the bundled sample: the gold-annotated **Greek New Testament** (`aegean.load("nt")`, Nestle 1904: lemma, morphology, Strong's) and six fetch-on-demand epigraphic/papyrological corpora: **I.Sicily** (2,855), **IIP** (2,113), **IOSPE** (1,194), **IGCyr/GVCyr** (997), **EDH** (1,286), and the **DDbDP documentary papyri** (57,331 texts / ~4.4M tokens as SQLite + full-text search: `aegean db search ddbdp`) |
| [`aegean.io`](Architecture) | Import **and** export: bring your own text in (`from_text` / `from_text_file` / `from_text_dir` / `from_csv`, and `aegean import` from the shell) → a real `Corpus`; export to EpiDoc (TEI), CSV, Parquet, CoNLL-U, Turtle, and JSON-LD, with typed editorial forms; [loss-aware adapters](Interoperability) carry complete analyses through spaCy, Stanza, and CLTK objects |
| [CLI](CLI) | The toolkit from a terminal: guided quickstart, REPL, optional full-screen TUI, corpus and Greek commands, data management, diagnostics, JSON output, and stdin piping |
| [Geography](Geography) | `aegean.geo`: corpus → geopandas GeoDataFrame (per-inscription or per-site points) from a bundled, Pleiades-aligned Aegean gazetteer, for mapping/spatial analysis |
| `aegean.viz` ([Analysis](Analysis)) | One-line plots (the `[viz]` extra): frequency bars, dispersion/keyness charts, co-occurrence networks, accounting diagonals, scansion grids, and `aegean plot` from the shell |
| [AI Layer](AI-Layer) | Multi-provider clients (Anthropic/OpenAI/Grok/Gemini/OpenRouter, plus a local Ollama/LM Studio/llama.cpp option), grounding, caching, exploratory-labeled capabilities, hybrid translation |
| [Data & Provenance](Data-and-Provenance) | Bundled data, download-to-cache, citation/licensing |

The **[API reference](https://pyaegean.xyz/api/)** documents the supported facade modules,
with public classes and functions generated from docstrings and type hints.

## Install

```bash
pip install pyaegean            # core + Linear A + Greek
pip install "pyaegean[cli]"     # + the `aegean` command line
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini / OpenRouter clients (the openai SDK also drives the local Ollama option)
pip install "pyaegean[interop]" # + Python adapters; combine with [cli] for the interop commands
pip install "pyaegean[all]"     # bundled runtime extras, including neural (not Parquet/framework adapters)
```

See [Installation](Installation) for the full extras matrix, and
[Development](Development) to build from source and run the test suite.

## Roadmap

The changelog records what has shipped. Current work is focused on:

- completing empirical source/task calibration and cross-domain development gates on the
  model-independent Greek foundations, alongside explicit annotation and domain profiles;
- comparing deterministic and neural translation grounding on matched passages
  before changing a default;
- training and independently evaluating a separately versioned successor to the
  current Greek model only after those foundations are frozen; and
- adding license-clean dictionaries, conda-forge packaging, and verified
  gazetteer coverage.

## For specialists

Aegean epigrapher, Mycenologist, philologist, or historical linguist? See
**[For Specialists](For-Specialists)** for what's established vs. exploratory and
how to file a correction, validate an exploratory result, or contribute a sourced
fact: your judgement is part of how the toolkit stays trustworthy.

## License

Apache-2.0 (code and the bundled Linear A corpus JSON). The Linear A corpus data
is GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz; facsimile imagery
© École Française d'Athènes (referenced, not redistributed). The other corpora
and datasets, bundled and fetch-on-demand alike, each carry their own license.
See [Data & Provenance](Data-and-Provenance).
