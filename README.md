# pyaegean

**A specialist Python toolkit for Ancient Greek and the Aegean syllabic scripts**: alphabetic
Greek *and* Linear A, Linear B, the Cypriot syllabary, and Cypro-Minoan, through one small,
dependency-light library.

[![PyPI](https://img.shields.io/pypi/v/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![Python](https://img.shields.io/pypi/pyversions/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](https://github.com/ryanpavlicek/pyaegean/blob/main/LICENSE)
[![CI](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml)

> **Status: v0.19.16 (beta).** Usable and tested, but the API may still shift before 1.0.
> Analytical and generative output on the
> *undeciphered* material (Linear A, Cypro-Minoan) is **exploratory**: leads for a human expert,
> never ground truth. The bundled Linear A corpus is a *normalized* transcription (no full
> epigraphic apparatus); for edition-grade readings consult GORILA / SigLA.

---

## What this is

The Greek world wrote in more than one script. **Alphabetic Greek** carries Homer, the tragedians,
and the New Testament. Centuries earlier, the **Aegean syllabic scripts** recorded the Bronze Age:
**Linear B** (Mycenaean Greek, deciphered), the **Cypriot syllabary** (Arcado-Cypriot Greek,
deciphered), and two scripts we still *cannot read*: **Linear A** (Minoan) and **Cypro-Minoan**.

**pyaegean** is a narrow, deep toolkit for all of it: a **script-agnostic corpus data layer**, a
full **Greek NLP pipeline**, the analytical methods of the [Linear A Research
Workbench](https://github.com/ryanpavlicek/linearaworkbench) ported to Python, and a grounded,
multi-provider **AI layer**: every result is labeled with its confidence level and source data.
The core installs with **zero heavy dependencies** and imports instantly; heavier
backends (models, treebanks, lexica) are opt-in and fetched to a local cache, never bundled.

For classicists, computational philologists, linguists, and students: anyone who wants a clean,
citable data layer over Greek and the Aegean scripts. The
[Getting Started guide](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started) assumes no
prior programming.

## Highlights

| | |
|---|---|
| **All four Aegean scripts, one API** | `aegean.load("lineara")` gives the bundled **1,721-inscription** Linear A corpus over the full Unicode Linear A sign repertoire (50 signs carry conventional sound values, the rest are undeciphered); Linear B and Cypro-Minoan add Unicode-built inventories with small *illustrative* text samples (bring your own corpus for Linear B: see below); the **Cypriot syllabary** bundles a **178-inscription corpus** (*Inscriptiones Graecae* XV 1, BBAW, CC BY 4.0). The two *deciphered* syllabaries transliterate and bridge into Greek: `po-me → ποιμήν` (Linear B), `pa-si-le-u-se → βασιλεύς` (Cypriot). |
| **A deep Greek NLP pipeline** | Beta Code ↔ Unicode (Beta Code is the plain-ASCII way of typing polytonic Greek), tokenize, syllabify, accent & prosody, **metrical scansion** (scans the *Odyssey*'s opening; rejects lines that require synizesis), reconstructed IPA (Attic / Koine), POS, morphology, and lemmatization. Opt-in backends add attested lemmas/POS (Perseus treebank), a **dictionary registry** (LSJ, Middle Liddell, Cunliffe, Abbott-Smith) with Logeion deep-links, pure-Python generalizing taggers/lemmatizers, **inflection synthesis** (the inverse lemmatizer), **terminology-rarity** scoring, and **dialect/register** tags from LSJ. |
| **State-of-the-art neural NLP** | The opt-in **neural pipeline** (`greek.use_neural_pipeline()`; runs without PyTorch): one jointly-trained model for tagging, full morphology, **dependency parsing** (Universal Dependencies trees), and lemmatization; in plain terms, it reads a Greek sentence and tells you each word's part of speech, grammatical form, dictionary headword, and place in the sentence's structure. Measured end-to-end through this package at **97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.6 LAS** on the UD Ancient Greek (Perseus) test benchmark, to our knowledge the best published results on every metric and robust across five training seeds (LAS 85.6 ± 0.1) ([protocol & tables](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md)). |
| **Real texts on demand** | `greek.load_work("tlg0012.tlg001")` fetches a complete work (the Iliad arrives as 24 books / ~127k tokens) from Perseus canonical-greekLit / First1KGreek (CC BY-SA, commit-pinned, cached) straight into the corpus model. Don't know an id? `greek.catalog(author="Plato")` searches a bundled, offline index of **1,778** Greek works (every `-grc` edition in both repos): author, title (English or Greek), or free text, and every hit's id loads with `load_work`. |
| **Bring your own text** | `aegean.io.from_text` / `from_text_file` / `from_text_dir` / `from_csv` turn a passage, a folder of `.txt`, or a CSV into a real `Corpus`: `aegean.io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος.")` gives the full filter / query / analyse / export API over your own material, with Greek run through the Greek tokenizer. |
| **The Greek New Testament, annotated** | `greek.load_nt("John", ref="1.1-18")` loads the Nestle 1904 NT with a gold **lemma**, **morphology**, and **Strong's number** on every token; `greek.use_dodson()` adds Koine glosses (`gloss_strongs("3056") → "a word, speech…"`). So you can lemmatize, gloss, and cite a chapter, offline. Public-domain text + CC0 annotations; one book is bundled, the full 27 fetch on demand. |
| **Accounting reconciliation** | Parses Aegean decimal numerals and metrological fractions, sums each tablet's line items, and checks them against the stated **KU-RO** (Linear A) / **to-so** (Linear B) total, flagging which balance and which don't. (37 of the 1,721 Linear A tablets carry a checkable total; most are too fragmentary due to preservation.) |
| **An analyst's toolkit** | Ported from the Linear A Workbench: wildcard **sign-pattern search** (`KU-*-RO`), weighted **phonetic distance + alignment**, **morphological clustering**, **collocation statistics** (PMI, log-likelihood, Fisher's exact), and a compound **query engine** with AND / OR / NOT. |
| **A clean, citable data layer** | `Corpus` / `Document` / `Token` / `Sign` value objects, a pandas `to_dataframe()`, a **lossless JSON round-trip** (`to_json` / `from_json`), a first-class **`query()`**, and **schema-valid EpiDoc / CSV / Parquet** export via `aegean.io` (the EpiDoc validates against the official EpiDoc RelaxNG and round-trips editorial status, and any EpiDoc edition **reads back in** with `from_epidoc`). Every corpus carries provenance and a one-line citation. |
| **A browser UI for any corpus** | `aegean.io.to_workbench(corpus, "my.json")` emits a file the [Linear A Research Workbench](https://linearaworkbench.xyz/) opens via `?corpus=`: your own inscriptions get its 50 analysis modules, maps, and imagery browser with zero setup. `from_workbench_export()` loads the workbench's corpus exports (and its static data API) back into Python. |
| **Map the find-sites** | `aegean.geo` turns a corpus into a geopandas **GeoDataFrame**: a point per inscription or per site (EPSG:4326) from a bundled Aegean gazetteer, so you can map where a word clusters or how far a script reaches. `pip install pyaegean[geo]`. |
| **Grounded, multi-provider AI** | `aegean.ai` / `aegean.translate` front Anthropic, OpenAI, Grok, Gemini, and OpenRouter. Every generative reading is built on a **local, deterministic grounding** step from the tools above, and is labeled **exploratory** with its provenance: a hypothesis, never an assertion. |
| **Measured accuracy** | Deciphered Greek uses real scholarship (attested lemmas, gold POS, measured accuracy). The *undeciphered* material (Linear A, Cypro-Minoan) is labeled **EXPLORATORY** everywhere: the tools surface *leads*, never answers. |

## Install

```bash
pip install pyaegean              # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[cli]"       # + the `aegean` command line
pip install "pyaegean[tui]"       # + the `aegean tui` full-screen terminal UI (Textual)
pip install "pyaegean[neural]"    # + the neural Greek pipeline & lemmatizer (onnxruntime; no torch)
pip install "pyaegean[ai]"        # + Anthropic / OpenAI / Grok / Gemini / OpenRouter clients
pip install "pyaegean[mcp]"       # + the `aegean-mcp` Model Context Protocol server (for agents)
pip install "pyaegean[all]"       # the data, AI, EpiDoc, geo, viz, CLI, TUI, and MCP extras
```

## Try it

**No install required**: run the guided tour in your browser, nothing to set up:
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)

Or try the toolkit **live in your browser**: the core pipeline running client-side via Pyodide,
nothing to install: **[ryanpavlicek.github.io/pyaegean/demo](https://ryanpavlicek.github.io/pyaegean/demo/)**.

```python
import aegean

corpus = aegean.load("lineara")          # 1,721 inscriptions, bundled, offline
ht = corpus.filter(site="Haghia Triada") # filter by metadata (full site name)
df = corpus.to_dataframe(level="word")   # pandas-native, one row per word

from aegean.analysis import balance_check, word_matches_sign_pattern
balance_check(corpus.get("HT13"))                       # KU-RO accounting reconciliation
[w for w, _ in corpus.word_frequencies()
 if word_matches_sign_pattern(w, "KU-*-RO")]            # wildcard sign search → ['KU-MA-RO']
```

```python
from aegean import greek

greek.betacode_to_unicode("mh=nin")     # 'μῆνιν'   (type Greek in plain ASCII)
greek.syllabify("ἄνθρωπος")             # ['ἄν', 'θρω', 'πος']
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'             (Odyssey 1.1)

[(r.text, r.upos, r.lemma) for r in greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")]
# [('ἐν','ADP','ἐν'), ('ἀρχῇ','NOUN','ἀρχή'), ('ἦν','VERB','εἰμί'), …]   one call, per-token records

greek.catalog(author="Plato")[0]   # find a work id to load — bundled, offline, instant
# {'id': 'tlg0059.tlg001', 'author': 'Plato', 'title': 'Euthyphro', 'greek_title': 'Εὐθύφρων', 'source': 'perseus'}
```

Or bring your **own** text: a string, a `.txt` file, a folder of texts, or a CSV becomes a full
`Corpus`:

```python
from aegean import io

corpus = io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος.")   # offline; Greek tokenizer
[t.text for t in corpus.get("text").tokens]    # ['ἐν', 'ἀρχῇ', 'ἦν', 'ὁ', 'λόγος']
# now corpus.query(...), corpus.word_frequencies(), aegean.io.to_csv(corpus, …) — the whole API
```

Or skip Python entirely: the **`aegean` CLI** (`[cli]` extra) covers the whole toolkit,
with `--json` on every data-producing command and stdin piping:

```bash
aegean quickstart                              # the guided first five minutes, offline
aegean doctor                                  # check the environment (extras, data store, models)
aegean repl                                    # interactive shell: run commands without the `aegean` prefix
aegean tui                                     # full-screen terminal UI: browse a corpus, the Greek workbench, the data store (`[tui]` extra)
aegean show lineara HT13                       # one tablet, line by line
aegean balance lineara --strict                # reconcile every stated total
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural --json
aegean greek catalog --author plato            # search 1,778 loadable works (offline)
aegean import myplato.txt -o myplato.json      # your own text → a corpus, then `aegean stats myplato.json`
```

Everything above runs **offline with zero heavy dependencies**. Large assets are fetched to a local
cache only when you opt in (and never bundled inside the wheel): the full Linear B corpus
(`aegean.load("damos")`), the SigLA Linear A dataset (`aegean.load("sigla")`), the Linear A
facsimile mirror (`aegean.data.fetch("lineara-images")`), the AGDT-derived lexicon and models
(`greek.use_treebank()` and friends: small prebuilt artifacts, with build-from-source as the
fallback), the LSJ index (`greek.use_lsj()`), and the neural models
(`greek.use_neural_lemmatizer()` / `use_neural_pipeline()`).

## Documentation

Full documentation lives in the **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**:

- **[Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)**: for newcomers to Python
- **[Example notebook](https://github.com/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)**: a runnable guided tour ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb))
- **[Tutorial](https://github.com/ryanpavlicek/pyaegean/wiki/Tutorial)**: two guided, end-to-end research walkthroughs
- **[Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A)** · **[Linear B](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-B)** · **[Cypriot](https://github.com/ryanpavlicek/pyaegean/wiki/Cypriot)** · **[Cypro-Minoan](https://github.com/ryanpavlicek/pyaegean/wiki/Cypro-Minoan)**: per-script guides
- **[Recipes](https://github.com/ryanpavlicek/pyaegean/wiki/Recipes)**: end-to-end scholarly workflows, each ending in a citation
- **[Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP)** · **[CLI](https://github.com/ryanpavlicek/pyaegean/wiki/CLI)** · **[Analysis](https://github.com/ryanpavlicek/pyaegean/wiki/Analysis)** · **[AI Layer](https://github.com/ryanpavlicek/pyaegean/wiki/AI-Layer)** · **[Data & Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)**: reference
- **[API reference](https://ryanpavlicek.github.io/pyaegean/)**: every public module, class, and function, generated from the source

## Roadmap

Shipped through **v0.19.16**: the script-agnostic core and all four Aegean scripts; the full Greek
NLP track (treebank, dependency parser, generalizing tagger and lemmatizer, the neural joint
pipeline, inflection synthesis, terminology-rarity scoring, dialect/register tags, a benchmark
harness, and a neutral out-of-AGDT evaluation with a convention-drift breakdown); a **pluggable lexicon
registry** with Middle Liddell, Cunliffe, Abbott-Smith, LSJ, and Dodson, plus Logeion deep-links;
the annotated **Greek New Testament** with Koine glossing; the full **DAMOS Linear B** and
**SigLA Linear A** corpora on demand; corpus statistics (dispersion, keyness, bootstrap), one-line
plots, and cross-script phonetic comparison; a complete data layer (lossless JSON round-trip, a
compound `query()`, schema-valid EpiDoc / CSV / Parquet export, **SQLite persistence** with
full-text search, an opt-in analysis cache, and Pleiades-aligned find-sites); a **multi-provider
AI layer** (Anthropic, OpenAI, Grok, Gemini, OpenRouter) with grounded, exploratory-labeled
translation and optional gated LSJ gloss grounding; the **`aegean`** command line mirroring the Python API and the **`aegean-mcp`**
server; and an in-browser demo.

On the list next:

- More public-domain dictionaries in the registry (Autenrieth, Slater), as their open
  digitizations are confirmed license-clean
- SigLA editorial-apparatus decoding, richer `load_work` addressing, and wider Pleiades /
  gazetteer coverage, as the upstream apparatus data and verified coordinates become available


## About the author

Ryan Pavlicek

I'm a software engineer that likes creating useful tools for exploring interesting problems.

Contact: email or create an issue on the GitHub repo.

**Email:** 'ryan [dot] pavlicek [dot] github [at] gmail [dot] com'

*(Replace `[at]` with `@` and `[dot]` with `.`)*


## Citation

If pyaegean helped with work you publish, please cite it. In the scholarly spirit, two layers:

1. **Always cite the underlying scholarship** pyaegean stands on:
   [GORILA](https://cefael.efa.gr/result.php?serie_title_operator=con&volume_number_operator=%3D&issue_year_operator=%3D&section_title=Recueil+des+inscriptions+en+lin%C3%A9aire+A&section_title_operator=con&author_lastname_operator=con&publisher_name_operator=con&site_id=1&actionID=advanced&operator=AND)
   (Godart & Olivier 1976–1985; all five volumes are digitized in the École française
   d'Athènes' CEFAEL library at that link) for Linear A; the Perseus AGDT treebank, LSJ, and (for fetched works) the Perseus
   Digital Library / Open Greek and Latin for Greek; the Unicode Character Database for the
   Linear B / Cypriot / Cypro-Minoan sign data; and GreBerta/GreTa plus the AGDT, Gorman, and
   Pedalion treebanks behind the neural models. The editions are listed in [`NOTICE`](https://github.com/ryanpavlicek/pyaegean/blob/main/NOTICE),
   and every corpus emits its own source citation via `corpus.cite()`.
2. **Also cite pyaegean** if you used its analysis, methods, or outputs (pin the version you ran,
   for reproducibility). GitHub's **"Cite this repository"** button: generated from
   [`CITATION.cff`](https://github.com/ryanpavlicek/pyaegean/blob/main/CITATION.cff): gives APA / BibTeX in one click, or use:

```bibtex
@software{pavlicek_pyaegean,
  author  = {Pavlicek, Ryan},
  title   = {{pyaegean: a Python toolkit for Ancient Greek and the Aegean syllabic scripts}},
  year    = {2026},
  version = {0.19.16},
  url     = {https://github.com/ryanpavlicek/pyaegean}
}
```

No obligation for casual or exploratory use — but if it helped, I'd love to hear about it.

## License

Apache-2.0. Linear A corpus data is GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz; the
Linear B / Cypriot / Cypro-Minoan sign data is from the Unicode Character Database. Facsimile imagery
© École Française d'Athènes (referenced, not redistributed). The opt-in Greek backends fetch small
prebuilt artifacts derived from the Perseus AGDT (CC BY-SA 3.0) and LSJ (CC BY-SA 4.0) to cache,
falling back to building from upstream. The DAMOS and SigLA corpora are CC BY-NC-SA 4.0, hosted as
clearly-labeled release assets and fetched to cache: NC data is never bundled inside the wheel.
See [`NOTICE`](https://github.com/ryanpavlicek/pyaegean/blob/main/NOTICE).
