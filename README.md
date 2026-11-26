# pyaegean

**A specialist Python toolkit for Ancient Greek and the Aegean syllabic scripts**: alphabetic
Greek *and* Linear A, Linear B, the Cypriot syllabary, and Cypro-Minoan, through one small,
dependency-light library.

[![PyPI](https://img.shields.io/pypi/v/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![Python](https://img.shields.io/pypi/pyversions/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](https://github.com/ryanpavlicek/pyaegean/blob/main/LICENSE)
[![CI](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml)

> **Latest PyPI release: v0.73.0 (beta).** The API may still shift before 1.0.
> The bundled Linear A corpus is a normalized transcription without full epigraphic
> apparatus; for edition-grade readings consult GORILA or SigLA.

---

## Quick start for researchers

Sixty seconds, offline, no accounts:

```bash
pip install pyaegean
```

```python
import aegean
from aegean import greek

ht13 = aegean.load("lineara").get("HT13")      # a tablet from the bundled 1,721-inscription corpus
[t.text for t in ht13.tokens][:3]
# ['KA-U-DE-TA', 'VIN', '𐄁']

[(r.text, r.upos, r.lemma) for r in greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")]
# [('ἐν','ADP','ἐν'), ('ἀρχῇ','NOUN','ἀρχή'), ('ἦν','VERB','εἰμί'), …]   full analysis, one call

[(t.text, t.status.name) for t in aegean.load("cypriot").get("IG XV 1, 120").tokens]
# [('a-ke-se-to-ro','CERTAIN'), …, ('e-mi','RESTORED')]   editorial apparatus on every word
```

The Greek example uses the default heuristic baseline. Its tags and lemmas can be
wrong even in short, ordinary sentences. Use the opt-in neural pipeline when
accuracy matters, then review its predictions; existing corpus annotations are
source data, not output from this example.

More runnable examples are in [Try it](#try-it) below. Then pick your path:

- **Classicist analyzing texts**: [Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)
  assumes no prior programming; [Choosing a Workflow](https://github.com/ryanpavlicek/pyaegean/wiki/Choosing-a-Workflow)
  matches your task to a working pattern; [Recipes](https://github.com/ryanpavlicek/pyaegean/wiki/Recipes)
  are end-to-end scholarly workflows, each ending in a citation;
  [Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP) is the full pipeline reference.
- **Epigrapher or papyrologist**: [Using Critical Editions](https://github.com/ryanpavlicek/pyaegean/wiki/Using-Critical-Editions)
  covers the six fetchable inscription and papyrus corpora, per-token reading statuses, and
  edition fidelity.
- **Aegean-script researcher**: [Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A)
  is the per-script handbook (Linear B, Cypriot, and Cypro-Minoan have siblings);
  [Limitations](https://github.com/ryanpavlicek/pyaegean/wiki/Limitations) states what the
  undeciphered material can and cannot support.
- **NLP researcher**: [Benchmarks](https://github.com/ryanpavlicek/pyaegean/wiki/Benchmarks)
  has the measured numbers, the evaluation protocol, and cited cross-tool comparisons;
  [docs/benchmarks.md](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md)
  is the canonical source;
  [Choosing a Pipeline](https://github.com/ryanpavlicek/pyaegean/wiki/Choosing-a-Pipeline)
  maps material to the right backend.

The **[documentation site](https://pyaegean.xyz/)** pairs this quick start
with the full API reference.

## What this is

The Greek world wrote in more than one script. **Alphabetic Greek** carries Homer, the tragedians,
and the New Testament. Centuries earlier, the **Aegean syllabic scripts** recorded the Bronze Age:
**Linear B** (Mycenaean Greek, deciphered), the **Cypriot syllabary** (chiefly Arcado-Cypriot
Greek, deciphered; the corpus also carries Eteocypriot and undetermined material), and two scripts
we still *cannot read*: **Linear A** (Minoan) and **Cypro-Minoan**.

**pyaegean** is a narrow, deep toolkit for all of it: a **script-agnostic corpus data layer**, a
full **Greek NLP pipeline**, the analytical methods of the [Linear A Research
Workbench](https://github.com/ryanpavlicek/linearaworkbench) ported to Python, and a
multi-provider **AI layer**. Generative results are labeled exploratory and carry their provider,
model, prompt, and any grounding sources. Neural analyses can opt into calibrated per-field
confidence (literary and documentary Greek) to sort review queues from highest estimated error risk
downward; caller-chosen cutoffs remain explicit, and any uncalibrated scope reports why rather than
falling back to raw model scores.
The core installs with **zero heavy dependencies** and imports instantly; heavier
backends (models, treebanks, lexica) are opt-in and fetched to a local cache, never bundled.

For classicists, computational philologists, linguists, and students: anyone who wants a clean,
citable data layer over Greek and the Aegean scripts. The
[Getting Started guide](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started) assumes no
prior programming.

## Highlights

| | |
|---|---|
| **All four Aegean scripts, one API** | `aegean.load("lineara")` gives the bundled **1,721-inscription** Linear A corpus over the full Unicode Linear A sign repertoire (50 signs carry conventional sound values, the rest are undeciphered); Linear B and Cypro-Minoan add Unicode-built inventories with small *illustrative* text samples (the full DAMOS Linear B corpus is available on demand); the **Cypriot syllabary** bundles a **178-inscription corpus** (*Inscriptiones Graecae* XV 1, BBAW, CC BY 4.0) plus two illustrative samples, for **180 bundled documents** total. The two *deciphered* syllabaries transliterate and bridge into Greek: `po-me → ποιμήν` (Linear B), `pa-si-le-u-se → βασιλεύς` (Cypriot). |
| **A deep Greek NLP pipeline** | Beta Code ↔ Unicode (Beta Code is the plain-ASCII way of typing polytonic Greek), tokenize with named source-preserving sentence policies, syllabify, accent & prosody, **metrical scansion** (scans the *Odyssey*'s opening; supports curated synizesis candidates and reports ambiguity), reconstructed IPA (Attic / Koine), POS, morphology, and lemmatization. Opt-in backends add attested lemmas/POS (Perseus treebank), a **dictionary registry** (LSJ, Middle Liddell, Cunliffe, Autenrieth, Abbott-Smith) with Logeion deep-links, pure-Python generalizing taggers/lemmatizers, **inflection synthesis** (the inverse lemmatizer), **terminology-rarity** scoring, and **dialect/register** tags from LSJ. |
| **Measured neural NLP** | The opt-in **neural pipeline** (`greek.use_neural_pipeline()`; runs without PyTorch): one jointly-trained model for tagging, full morphology, **dependency parsing** (Universal Dependencies trees), and lemmatization; in plain terms, it reads a Greek sentence and tells you each word's part of speech, grammatical form, dictionary headword, and place in the sentence's structure. Its stable `default` runtime label is the current `grc-joint-v3` artifact; `fast`, `compact`, and `balanced` are visible but unavailable until a successor earns each label from recorded size, latency, and memory evidence. Measured end-to-end through this package at **97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.7 LAS** on the UD Ancient Greek (Perseus) test benchmark ([protocol, comparison rows, confidence intervals, and limitations](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md)). Optional add-ons on the same model include an **OOV lemma reranker** (`greek.use_oov_lemma_reranker(config="weighted")`) that improves headword accuracy on unseen Classical, NT, verse, and papyrus forms, and **domain-scoped calibration** (`greek.use_calibration_registry()`) that ranks the riskiest words first for human review. |
| **Real texts on demand** | `greek.load_work("tlg0012.tlg001")` fetches a complete work (the Iliad arrives as 24 books / ~127k tokens) from Perseus canonical-greekLit / First1KGreek (CC BY-SA, commit-pinned, cached) straight into the corpus model. Don't know an id? `greek.catalog(author="Plato")` searches a bundled, offline index of **1,778** Greek works (every `-grc` edition in both repos): author, title (English or Greek), or free text, and every hit's id loads with `load_work`. |
| **Ancient, Classical, Patristic & Byzantine Greek Library (3,844 works)** | **8 categorized open-licensed release collections** spanning 8th c. BCE–1453 CE (3,844 works across 1,414 authors, 64.35M tokens; 100% Public Domain, CC BY, or CC BY-SA 4.0): **John Chrysostom** complete open corpus (155 works, 3.74M tokens), **Early & Nicene Church Fathers** (432 works: Athanasius, Basil, Cappadocians, Origen, Eusebius), **Post-Nicene & Eastern Fathers** (280 works: Cyril, Theodoret, Maximus, John of Damascus, Photius, Palamas), **Archaic & Classical Greek** (684 works), **Hellenistic & DFHG Historians** (740 works), **Imperial Greek** (1,078 works), **Late Antique Greek** (290 works), and **Byzantine Literature through 1453** (185 works). Search all 3,844 works offline via `greek.collections()` / `aegean greek collections`, open any work with `aegean.open("ogc002060")`, or install whole packs (`aegean library install church-fathers ancient-greek byzantine-pack`). |
| **Epigraphic Greek, papyri & literary corpora on demand** | Thirteen openly-licensed corpora fetch straight into the corpus model (47 SHA-256-pinned remote assets total): **I.Sicily** (2,855 Greek inscriptions, CC BY), **IIP** (2,113, CC BY-NC), **IOSPE** (1,194, CC BY), **IGCyr/GVCyr** (997, archaic Doric and verse, CC BY-NC-SA), **Aphrodisias / IAph2007** (1,471, CC BY 2.5), **Cretan Institutional Inscriptions** (600 Archaic–Hellenistic inscriptions, CC BY-NC-SA), **EDH** (1,286, CC BY-SA), **DDbDP** documentary papyri (**57,331 texts / ~4.4M tokens**, CC BY, SQLite FTS), **Patrologia Graeca** (33 CGPG volumes / 6.79M words, CC BY), **Open Apostolic Fathers** (15 works, CC BY-SA), **Online Critical Pseudepigrapha** (44 Second Temple Greek works, CC BY), **Byzantine & Early Modern Vernacular Greek** (12 texts, 189K tokens, PD/CC BY-SA), and **Homer Multitext Venetus A *Iliad* & *Scholia*** (54 docs, 331K tokens, CC BY-NC). For large SQLite corpora, resumable annotation jobs (`aegean db annotate` / `db.annotate_sqlite_job`) save progress document by document. |
| **Bring your own text** | `aegean.io.from_text` / `from_text_file` / `from_text_dir` / `from_csv` turn a passage, a folder of `.txt`, or a CSV into a real `Corpus`: `aegean.io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος.")` gives the full filter / query / analyse / export API over your own material, with Greek run through the Greek tokenizer. |
| **Biblical, Second Temple & Patristic Greek (`aegean.greek.bible` & `aegean bible`)** | Dedicated specialist suite across Python, CLI (`aegean bible`), TUI (`b`, 6 tabs including dedicated Septuagint and Patristics tabs), MCP, and browser demo: **9 Greek NT editions** (`nestle1904` with gold lemma/morphology/Strong's, `sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`) with word-level variant collation (`compare_editions`); **13 early 2nd–5th c. CE manuscripts** (Sinaiticus `01`, Vaticanus `03`, Alexandrinus `02`, Ephraemi `04`, Bezae `05`, `032`, `P45`–`P75`) with diplomatic transcriptions and *nomina sacra* expansion; **Extended Strong's** (11,142 entries + etymological root trees, with offline Dodson fallback); the **complete 56-book Septuagint (LXX)** (`lxx-corpus-v2` incl. Ecclesiastes, `aegean.load("lxx")`, inline refs like `load_lxx("Gen 1:1-5")`, Masoretic Psalm numbering `numbering="mt"`, automatic offline interlinear `interlinear=True`, and unified `search_bible(corpus="both")` / `word_study()` parity); and **112 Greek patristic commentaries** across 11 Church Fathers and traditions (*Catenae*, Origen, **26 John Chrysostom homily series**, Cyril of Alexandria, Methodius, Eusebius, Clement of Alexandria, Procopius of Gaza, Photius, Oecumenius, and Theophylact of Bulgaria). Offline samples bundled (John 1, Philemon 1, Gen 1:1–5, LXX Ps 22:1–6); install packs via `aegean bible install` or `aegean library install church-fathers`. |
| **Unified Library Manager (`aegean.library` & `aegean library`)** | One interface across Python, CLI (`aegean library`), REPL, and TUI (`l`) to inspect bundled vs downloaded assets, search 47 hosted datasets, 3,844 categorized Greek collection works, 1,778 Perseus/First1KGreek works, 112 commentaries, lexica, and models, install **10 named packs** (`biblical`, `church-fathers`, `patristic`, `ancient-greek`, `byzantine-pack`, `aegean`, `epigraphy`, `literary`, `lexica`, `neural`) or individual works by title/ID/author (`aegean library install chrysostom Iliad`), and remove cached files to reclaim disk space. Missing texts in the TUI Biblical (`b`) and Corpus (`c`) screens download inline with one click (`f`). |
| **Accounting reconciliation** | Parses Aegean decimal numerals and metrological fractions, sums each tablet's line items, and checks them against the stated **KU-RO** (Linear A) / **to-so** (Linear B) total, flagging which balance and which don't. (37 of the 1,721 Linear A tablets carry a checkable total; most are too fragmentary due to preservation.) |
| **An analyst's toolkit** | Ported from the Linear A Workbench: wildcard **sign-pattern search** (`KU-*-RO`), weighted **phonetic distance + alignment**, **morphological clustering**, **collocation statistics** (PMI, log-likelihood, Fisher's exact), and a compound **query engine** with AND / OR / NOT. |
| **A clean, citable data layer** | `Corpus` / `Document` / `Token` / `Sign` value objects, a pandas `to_dataframe()`, lossless JSON and SQLite storage (with optional fast lexical indexing), a compound **`query()`**, compact **spreadsheet review workflows** (`layout="editable"`, calibrated-risk queues, multi-reviewer merges), and export to schema-valid EpiDoc plus CSV, Parquet, CoNLL-U, Turtle, and JSON-LD via `aegean.io`. Diplomatic, regularized, and normalized word forms stay distinct; CoNLL-U preserves complete treebank structure (including multiword spans and empty nodes). Every corpus carries provenance and a one-line citation. |
| **Loss-aware NLP interoperability** | Optional `aegean.io` adapters move Greek annotations between pyaegean and spaCy, Stanza, or CLTK while keeping extra philological metadata in a verified companion sidecar; `InteropReport` states plainly which fields transferred natively, which live in the sidecar, and which a format cannot represent. Portable JSON bundles work from Python or `aegean greek interop export\|import\|report`. |
| **A browser UI for any corpus** | `aegean workbench` serves the [Linear A Research Workbench v2.0.0](https://linearaworkbench.xyz/) offline (34 workspaces / 59 views) with `--corpus`, `--site`/`--period`/`--module`/`--doc`, `--damos`, and live `--state workspace.json` auto-sync. `aegean.io.to_workbench()` / `from_workbench_export()` / `load_workbench_backup()` round-trip corpora and researcher workspaces between Python and the browser. |
| **Map the find-sites** | `aegean.geo` turns a corpus into a geopandas **GeoDataFrame**: a point per inscription or per site (EPSG:4326) from a bundled Aegean gazetteer, so you can map where a word clusters or how far a script reaches. `pip install pyaegean[geo]`. |
| **Grounded, multi-provider AI** | `aegean.ai` / `aegean.translate` front Anthropic, OpenAI, Grok, Gemini, and OpenRouter, plus a **local** option that runs a model on your own machine (Ollama, LM Studio, llama.cpp, vLLM) with no key or network. Greek translation supports local grammatical analysis, **contextual dictionary excerpts** (`--dictionary`), separate **surrounding source context**, and optional **clause-by-clause checking** (`check_policy="clauses"`). All generative readings are labeled **exploratory** with their provenance. |
| **Measured accuracy & provenance** | Deciphered Greek uses attested lemmas, gold POS, and measured benchmarks. Structural analyses on undeciphered corpora (Linear A, Cypro-Minoan) carry an explicit `exploratory` flag. |

## Install

For persistent corpora and reviewed annotations, see the
[SQLite reference](https://pyaegean.xyz/api/db/) and
[scholarly workflow](https://pyaegean.xyz/scholarly-workflow/).

```bash
pip install pyaegean              # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[cli]"       # + the `aegean` command line
pip install "pyaegean[tui]"       # + the `aegean tui` full-screen terminal UI (Textual)
pip install "pyaegean[neural]"    # + the neural Greek pipeline & lemmatizer (onnxruntime; no torch)
pip install "pyaegean[ai]"        # + Anthropic / OpenAI / Grok / Gemini / OpenRouter clients (the openai SDK also drives the local option)
pip install "pyaegean[mcp]"       # + the `aegean-mcp` Model Context Protocol server (for agents)
pip install "pyaegean[interop]"   # + Python adapters; combine with [cli] for the interop commands
pip install "pyaegean[all]"       # bundled runtime extras, including neural (excludes Parquet, viz-interactive, and framework adapters)
```

## Try it

**No install required**: run the guided tour in your browser, nothing to set up:
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)

Or try the toolkit **live in your browser**: the core pipeline running client-side via Pyodide,
nothing to install: **[pyaegean.xyz/demo](https://pyaegean.xyz/demo/)**.

```python
import aegean

corpus = aegean.load("lineara")          # 1,721 inscriptions, bundled, offline
ht = corpus.filter(site="Haghia Triada") # filter by metadata (full site name)
df = corpus.to_dataframe(level="word")   # pandas-native, one row per word (requires [data])

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

segmented = greek.segment_text("[λόγος.] καί.", policy="papyrus")
segmented.boundaries[0].to_dict(segmented.source)
# exact source span + policy/provenance metadata (use sentence_policy= on pipeline())

greek.catalog(author="Plato")[0]   # find a work id to load — bundled, offline, instant
# {'id': 'tlg0059.tlg001', 'author': 'Plato', 'title': 'Euthyphro', 'greek_title': 'Εὐθύφρων', 'source': 'perseus'}
```

Or bring your **own** text: a string, a `.txt` file, a folder of texts, or a CSV becomes a full
`Corpus`:

```python
from aegean import io

corpus = io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος.")   # offline; Greek tokenizer
[t.text for t in corpus.get("text").tokens]    # ['ἐν', 'ἀρχῇ', 'ἦν', 'ὁ', 'λόγος', '.']
# now corpus.query(...), corpus.word_frequencies(), aegean.io.to_csv(corpus, …) — the whole API
```

Or skip Python entirely: the **`aegean` CLI** (`[cli]` extra) covers the whole toolkit,
with `--json` on every data-producing command and stdin piping:

```bash
aegean quickstart                              # the guided first five minutes, offline
aegean doctor                                  # check the environment (extras, data store, models)
aegean                                         # interactive shell (on a TTY): live inline ghost-text + dropdown prediction
aegean tui                                     # 8-screen terminal UI: corpora, Greek workbench, Bible (b), Library Manager (l), data store (d)
aegean library packs                           # view all 10 downloadable packs (biblical, church-fathers, ancient-greek, byzantine-pack, …)
aegean library install biblical church-fathers # install Biblical pack + John Chrysostom & Greek Church Fathers (882 works)
aegean greek collections chrysostom            # list all 155 John Chrysostom works offline
aegean show lineara HT13                       # one tablet, line by line
aegean balance lineara --strict                # reconcile every stated total
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural --json
aegean greek catalog --author plato            # search 1,778 Perseus/First1KGreek works (offline)
aegean bible read John 1.1-5 --interlinear     # interlinear Greek NT (or `Gen 1:1-5 --interlinear` / `Ps 23 --mt` for LXX)
aegean bible compare John 1.18 -e sblgnt,tisch,wh,byz,antoniades,tr  # word-level diff across 9 NT editions
aegean bible witnesses John 18.37 --sigla P52,01,03  # 2nd–5th c. CE manuscript readings
aegean bible commentary search ogc002060 ἀγάπη # search John Chrysostom's Homilies on Matthew (or PG073 Cyril on John)
aegean import myplato.txt -o myplato.json      # your own text → a corpus, then `aegean stats myplato.json`
```

The core Greek and bundled-corpus examples run offline without heavy dependencies. All 47
hosted datasets (corpora, 8 categorized Ancient/Patristic/Byzantine Greek collections, Biblical
bundles, lexica, models, and facsimile imagery) are SHA-256-pinned, downloaded on demand into
your local cache via `aegean library` / `aegean data`, and never bundled inside the Apache-2.0
wheel. See [Data & Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)
for the complete catalog, sizes, and licenses.

## Documentation

Full documentation lives in the **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**:

- **[Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)**: for newcomers to Python
- **[Example notebook](https://github.com/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)**: a runnable guided tour ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb))
- **[Tutorial](https://github.com/ryanpavlicek/pyaegean/wiki/Tutorial)**: three guided, end-to-end research walkthroughs
- **[Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A)** · **[Linear B](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-B)** · **[Cypriot](https://github.com/ryanpavlicek/pyaegean/wiki/Cypriot)** · **[Cypro-Minoan](https://github.com/ryanpavlicek/pyaegean/wiki/Cypro-Minoan)**: per-script guides
- **[Recipes](https://github.com/ryanpavlicek/pyaegean/wiki/Recipes)**: end-to-end scholarly workflows, each ending in a citation
- **[Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP)** · **[Biblical & Koine Greek](https://github.com/ryanpavlicek/pyaegean/wiki/New-Testament)** · **[CLI](https://github.com/ryanpavlicek/pyaegean/wiki/CLI)** · **[TUI](https://github.com/ryanpavlicek/pyaegean/wiki/TUI)** · **[Analysis](https://github.com/ryanpavlicek/pyaegean/wiki/Analysis)** · **[AI Layer](https://github.com/ryanpavlicek/pyaegean/wiki/AI-Layer)** · **[Data & Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)**: reference
- **[Interoperability](https://github.com/ryanpavlicek/pyaegean/wiki/Interoperability)**: CoNLL-U, spaCy, Stanza, and CLTK projections, sidecars, reports, and serializer boundaries
- **[Independent review](https://github.com/ryanpavlicek/pyaegean/wiki/Independent-Review)**: one-command evidence verification, model and data cards, limitations, and discrepancy reporting
- **[API reference](https://pyaegean.xyz/api/)**: the supported facade modules, with public classes and functions generated from the source

## Independent review

From a clean source checkout, `python scripts/reproduce_review.py` verifies the
canonical public evidence records by SHA-256 and reproduces one small,
zero-dependency result without network access, model execution, bytecode, or cache
writes. It is a bounded integrity receipt, not a replacement for the neural benchmark
protocol or external scholarly review. The [review kit](review/README.md) includes the
model card, data card, receipt map, limitations, and discrepancy form.

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
   for reproducibility). GitHub's **"Cite this repository"** button (generated from
   [`CITATION.cff`](https://github.com/ryanpavlicek/pyaegean/blob/main/CITATION.cff)) gives APA / BibTeX in one click, or use:

```bibtex
@software{pavlicek_pyaegean,
  author  = {Pavlicek, Ryan},
  title   = {{pyaegean: a Python toolkit for Ancient Greek and the Aegean syllabic scripts}},
  year    = {2026},
  version = {0.73.0},
  url     = {https://github.com/ryanpavlicek/pyaegean}
}
```

No obligation for casual or exploratory use, but if it helped, I'd love to hear about it.

## License

Apache-2.0. Linear A corpus data is GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz; the
Linear B / Cypriot / Cypro-Minoan sign data is from the Unicode Character Database. Facsimile imagery
© École Française d'Athènes (referenced, not redistributed). The opt-in Greek backends fetch small
prebuilt artifacts derived from the Perseus AGDT (CC BY-SA 3.0) and LSJ (CC BY-SA 4.0) to cache,
falling back to building from upstream. The DAMOS and SigLA corpora are CC BY-NC-SA 4.0, hosted as
clearly-labeled release assets and fetched to cache: NC data is never bundled inside the wheel.
The Greek epigraphic and papyrus corpora (I.Sicily CC BY 4.0, IIP CC BY-NC 4.0, IOSPE CC BY,
IGCyr/GVCyr CC BY-NC-SA 4.0, EDH CC BY-SA 4.0, DDbDP CC BY 3.0) are likewise project-hosted
release assets fetched on demand, with attribution in each corpus's provenance.
See [`NOTICE`](https://github.com/ryanpavlicek/pyaegean/blob/main/NOTICE).
