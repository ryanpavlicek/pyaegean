# pyaegean

**A Python toolkit for Ancient Greek and the Aegean syllabic scripts**:
alphabetic Greek, Linear A, Linear B, Cypriot, and Cypro-Minoan. It combines a
script-agnostic corpus layer, Greek NLP, quantitative analysis tools, grounded
translation, and an optional multi-provider AI layer.

> **Latest PyPI release: v0.74.0 (beta).** The API may still shift before 1.0.
> This wiki documents the current release. See the
> [changelog](https://github.com/ryanpavlicek/pyaegean/blob/main/CHANGELOG.md)
> for release history.

See [Benchmarks](Benchmarks), [Data & Provenance](Data-and-Provenance), and
[Limitations](Limitations) for evaluation figures, dataset sources, and scope.

## Choose where to start

- **New to Python or pyaegean?** [Getting Started](Getting-Started) goes from
  installation to a first result without assuming programming experience.
- **Working on a research question?** [Choosing a Workflow](Choosing-a-Workflow)
  maps tasks to tools, and [Tutorial](Tutorial) plus [Recipes](Recipes) provide
  complete examples.
- **Prefer the terminal?** Install `pyaegean[cli]`, run `aegean quickstart`, and
  use the [CLI guide](CLI) or [CLI cheatsheet](CLI-Cheatsheet). The `[tui]`
  extra adds the 9-screen terminal UI (`aegean tui`), including interactive
  annotation and conflict review (`aegean tui --review`).
- **Browsing available texts and corpora?** [Corpus Catalog](Catalog) lists every
  registered corpus, Greek library collection (3,844 works), biblical book, manuscript
  witness, patristic commentary, inscription archive, lexicon, and Perseus/First1KGreek
  TEI edition by category.
- **Choosing a Greek backend?** [Choosing a Pipeline](Choosing-a-Pipeline)
  compares the deterministic, treebank, pure-Python, and neural options before
  the full [Greek NLP](Greek-NLP) reference.
- **Reviewing evidence or considering maintenance?** [Independent Review](Independent-Review)
  begins with one offline verification command and links the model card, data
  card, receipts, discrepancy form, and bounded ownership tasks.
- **Something not working?** [FAQ & Troubleshooting](FAQ) covers common
  install, data, model, Unicode, and network failures.

## Quick start

```python
import aegean

corpus = aegean.load("lineara")          # 1,721 inscriptions, bundled, offline
print(len(corpus))                       # 1721

ht = corpus.filter(site="Haghia Triada") # filter by metadata (site name)
corpus.word_frequencies()[:5]            # most common words

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
| [`aegean.core`](Architecture) | Script-agnostic model: `Corpus`, `Document`, `Token`, `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance, lossless JSON and SQLite storage, typed `SourceAlignment` and `TokenFormState`, unified `aegean.open()`, and a compound `query()` |
| [Linear A](Linear-A) | Bundled 1,721-inscription corpus, 342-sign Unicode inventory (50 carry conventional sound values), sign-to-sound map, transliteration |
| [Linear B](Linear-B) | Mycenaean Greek: 211-sign Unicode inventory, transliteration, Greek-reading bridge (`po-me → ποιμήν`), accounting checks, and the full DAMOS corpus on demand (`aegean.load("damos")`, ~5,900 tablets) |
| [Cypriot](Cypriot) | Chiefly Arcado-Cypriot Greek (with Eteocypriot and undetermined material): 55-sign Unicode syllabary, transliteration, Greek-reading bridge (`pa-si-le-u-se → βασιλεύς`), and a bundled **178-inscription corpus** (*Inscriptiones Graecae* XV 1, BBAW, CC BY 4.0) plus two illustrative samples (**180 documents** total) |
| [Cypro-Minoan](Cypro-Minoan) | Undeciphered Bronze Age Cyprus: 99-sign Unicode inventory and sign-sequence tokenization (no phonetics or Greek bridge) |
| [Analysis](Analysis) | Accounting checks, sign-pattern and phonetic search, cross-script comparison, clustering, collocation and corpus statistics, structure detection, FTS5 Greek search (`aegean.search`), and a compound query engine |
| [Greek NLP](Greek-NLP) | Text utilities, named source-preserving sentence policies, metre, IPA, tagging, morphology, lemmatization, parsing, dictionaries, 1,778 Perseus/First1KGreek works, and 3,844 categorized Greek collection works; optional treebank, pure-Python, and neural backends, with the neural pipeline measured at 97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.7 LAS on the UD Perseus test fold |
| [Biblical & Koine Greek](New-Testament) | `aegean.greek.bible`, `aegean bible`, `aegean tui` (`b`), and MCP tools: **9 Greek NT editions** (`nestle1904`, `sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`) with word-level collation, **13 early 2nd–5th c. CE manuscripts** (`01`–`05`, `032`, `P45`–`P75`) with *nomina sacra* expansion, **Extended Strong's** (11,142 entries + root trees), the **complete 56-book Septuagint (LXX)** (`lxx-corpus-v2`, incl. Ecclesiastes, inline refs, Masoretic Psalm numbering, and automatic offline interlinear), and **112 Greek patristic commentaries** across 11 Church Fathers/traditions (First1KGreek, 26 John Chrysostom homily series, and *Patrologia Graeca*) |
| Greek corpora ([Data & Provenance](Data-and-Provenance)) | Beyond the bundled sample: **8 categorized Greek library collections** (3,844 open-licensed works, 1,414 authors, 64.35M tokens, 8th c. BCE–1453 CE: John Chrysostom, Early & Nicene Fathers, Post-Nicene & Eastern Fathers, Classical, Hellenistic, Imperial, Late Antique, and Byzantine Literature), gold-annotated **Greek New Testament** (`nt`), **Septuagint** (`lxx`, 56 books), **Patrologia Graeca** (33 volumes, 6.79M words), **Open Apostolic Fathers** (15 works), **Greek OT Pseudepigrapha** (44 works), seven epigraphic corpora (**I.Sicily**, **IIP**, **IOSPE**, **IGCyr/GVCyr**, **Aphrodisias**, **Crete**, **EDH**), **DDbDP documentary papyri** (57,331 texts / ~4.4M tokens, SQLite FTS), **Byzantine Vernacular Greek** (12 works), and **Homer Multitext Venetus A *Iliad* & *Scholia*** (54 docs) |
| [`aegean.io`](Architecture) | Import and export: load plain text or CSV (`from_text` / `from_text_file` / `from_text_dir` / `from_csv`, `aegean import`); export to EpiDoc (TEI), CSV, Parquet, CoNLL-U, Turtle, JSON-LD, and multi-script browser workbench bundles (`to_workbench_bundle`, `to_workbench`, `from_workbench_export`, `load_workbench_backup`); [loss-aware adapters](Interoperability) preserve analyses across spaCy, Stanza, and CLTK |
| [`aegean.bundle`](Data-and-Provenance) | Portable, SHA-256-verified, license-clean research bundles (`aegean.bundle` / `aegean bundle create\|inspect\|verify\|extract\|hydrate`) packaging redistributable corpora (or retrieval pointers for NC-licensed datasets), citations, workbench state, editable review tables, and analysis receipts into one `.zip` archive |
| [CLI & TUI](CLI) | Interactive shell (bare `aegean`) with predictive completion, `aegean quickstart`, 9-screen TUI (`aegean tui`) with interactive annotation and conflict review (`r` / `aegean tui --review`) and browser launch (`v`), local multi-script browser workbench (`aegean workbench --corpus`, `workbench-app-v2.1.0` for Linear A, Linear B, Cypriot, and Cypro-Minoan), unified resource manager (`aegean library`), search (`aegean find`), bundles (`aegean bundle`), diagnostics (`aegean doctor`), JSON output, and stdin piping |
| [Greek Visual Browser](Greek-Browser) | `aegean.browser` / `aegean browse`: zero-dependency loopback web reader for Greek texts with interlinear glosses, parallel translations, hover dependency highlighting, grammar/lexicon/Strong's/commentary inspectors, metrical scansion, live NLP engine toggles, and a visual Library Manager |
| [`aegean.library`](Data-and-Provenance) | Primary resource manager across Python, CLI (`aegean library`), TUI (`l`), and browser (`aegean browse`), alongside low-level `aegean data`: inspect bundled vs downloaded items, search hosted datasets, 3,844 Greek collection works, 1,778 Perseus/First1KGreek works, 112 commentaries, lexica, and models, install **10 named packs** (`biblical`, `church-fathers`, `patristic`, `ancient-greek`, `byzantine-pack`, `aegean`, `epigraphy`, `literary`, `lexica`, `neural`), and remove cached files |
| [Geography](Geography) | `aegean.geo`: convert a corpus into a geopandas GeoDataFrame (per-inscription or per-site points) from a bundled, Pleiades-aligned Mediterranean and Aegean gazetteer (`144` sites, `unmapped_sites()` coverage audit) |
| `aegean.viz` ([Analysis](Analysis)) | One-line plots (`[viz]` extra): frequency bars, dispersion/keyness charts, co-occurrence networks, accounting diagonals, scansion grids, and `aegean plot` |
| [AI Layer](AI-Layer) | Multi-provider clients (Anthropic, OpenAI, Grok, Gemini, OpenRouter, and a local Ollama/LM Studio/llama.cpp option), grounding, caching, exploratory-labeled outputs, and hybrid translation |
| [Data & Provenance](Data-and-Provenance) | Bundled data, 47 SHA-256-pinned remote assets, citation and licensing |

The **[API reference](https://pyaegean.xyz/api/)** documents the supported facade modules,
with public classes and functions generated from docstrings and type hints.

## Install

```bash
pip install pyaegean            # core + Linear A + Greek
pip install "pyaegean[cli]"     # + the `aegean` command line
pip install "pyaegean[tui]"     # + the `aegean tui` terminal UI (including annotation review)
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini / OpenRouter clients (openai also drives local Ollama)
pip install "pyaegean[interop]" # + Python adapters; combine with [cli] for interop CLI commands
pip install "pyaegean[all]"     # bundled runtime extras, including neural (excludes Parquet, viz-interactive, and framework adapters)
```

See [Installation](Installation) for the full extras matrix, and
[Development](Development) to build from source and run the test suite.

## Roadmap

The [changelog](https://github.com/ryanpavlicek/pyaegean/blob/main/CHANGELOG.md) records released
changes and completed work awaiting release. The priorities below distinguish outstanding work
from proposed follow-ons; their order reflects dependencies rather than release dates.

### Current priorities

- [ ] **Expand adjudicated Greek gold:** adjudicate passages from the two archived full
  tragedy treebanks (*Philoctetes* and *Iphigenia in Tauris*) to broaden held-out verse
  evaluation beyond Euripides' *Bacchae*.
  [Greek development sources](https://github.com/ryanpavlicek/pyaegean/tree/main/training/sources/greek-development-v1)
- [ ] **Evaluate translation fidelity:** compare grounding and clause-checking options on
  unseen passages, measuring both corrections and regressions in meaning, roles, negation,
  qualifications, speaker context, and lexical sense before changing defaults.

### Following those foundations

- [ ] **Expanded lexical, spatial, and packaging resources:** add license-clean
  dictionaries, source-cited Cypriot lexical entries, verified gazetteer/Pleiades
  coverage, and conda-forge packaging.
- [ ] **Independently evaluated models and runtime variants:** evaluate a separately
  versioned Greek-model successor when a new supervised dataset or stronger backbone
  passes predeclared cross-domain development gates; offer calibrated `fast`, `compact`,
  and `balanced` ONNX variants only when candidate artifacts pass cross-domain accuracy
  and measured size, latency, and memory requirements.

## For specialists

Aegean epigrapher, Mycenologist, philologist, or historical linguist? See
**[For Specialists](For-Specialists)** for established vs. exploratory surfaces
and how to file a correction, validate an exploratory result, or contribute a
sourced fact.

## License

Apache-2.0 (code and the bundled Linear A corpus JSON). The Linear A corpus data
is GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz; facsimile imagery
© École Française d'Athènes (referenced, not redistributed). Other corpora and
datasets, bundled and fetch-on-demand alike, each carry their own license. See
[Data & Provenance](Data-and-Provenance).
