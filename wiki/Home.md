# pyaegean

**A specialist Python toolkit for Ancient Greek**: alphabetic Greek *and* the
Aegean syllabic scripts (Linear A, Linear B, Cypriot, and Cypro-Minoan). pyaegean focuses narrowly and
deeply on Greek and the Aegean world: a script-agnostic corpus data layer, the
analytical methods from the Linear A Research Workbench, translation, and a
pluggable multi-provider AI layer.

> **Status: v0.27.0 (beta).** The API is close to stable but may still shift before 1.0.
> The script-agnostic core, Linear A, **Linear B** (Mycenaean Greek),
> the **Cypriot syllabary** (Arcado-Cypriot Greek), and the undeciphered **Cypro-Minoan** script
> complete the Aegean set: each deciphered script with a sign inventory, transliteration, and a
> Greek-reading bridge; Cypro-Minoan, undeciphered, ships its sign inventory only. The Greek
> NLP track is a full pipeline: a zero-dependency core (tokenize → scansion → IPA → POS →
> morphology → lemmas), opt-in backends (Perseus AGDT treebank, LSJ glossing, generalizing
> taggers/lemmatizers), and an opt-in **neural pipeline** (`use_neural_pipeline`): one
> jointly-trained torch-free model for tagging, morphology, **UD dependency parsing**, and
> lemmatization that is **state of the art on the UD Ancient Greek (Perseus) benchmark**
> ([measured](Greek-NLP#the-neural-pipeline-opt-in): 97.0 UPOS / 96.0 UFeats / 94.3 lemma /
> 90.2 UAS / 85.6 LAS on the Perseus test fold, end-to-end from raw text): plus real works
> on demand (`load_work("tlg0012.tlg001")` → the Iliad), a benchmark harness, and a neutral
> out-of-AGDT (PROIEL) evaluator. The multi-provider AI layer + hybrid translation are
> implemented, over a corpus data layer with a lossless JSON round-trip (`to_json`/`from_json`)
> and a compound `query()`, plus EpiDoc/CSV/Parquet export. Analytical and generative output on the
> undeciphered Linear A material is **exploratory**: see [Limitations](Limitations) for the full
> picture of what pyaegean can and cannot claim, and [Data & Provenance](Data-and-Provenance) for
> where every dataset comes from.

### New here?

- **Never used Python?** Start with **[Getting Started](Getting-Started)**: it
  walks you from "I have nothing installed" to your first result, no prior
  programming assumed.
- **Prefer the terminal?** `pip install "pyaegean[cli]"`, then **`aegean
  quickstart`** runs the guided first five minutes: seven real commands, live on
  the bundled data, all offline. Want an app-like cockpit? `pip install
  "pyaegean[tui]"` adds **`aegean tui`**, a full-screen terminal UI to browse a
  corpus, run the live Greek workbench, and manage the data store. See [CLI](CLI).
- **Want to learn by doing?** The **[Tutorial](Tutorial)** answers two real
  research questions end to end: one in Linear A, one in Greek.
- **Something not working?** See the **[FAQ & Troubleshooting](FAQ)**.

## Quick start

```python
import aegean

corpus = aegean.load("lineara")          # 1,721 inscriptions, bundled, offline
print(len(corpus))                       # 1721

ht = corpus.filter(site="Haghia Triada") # filter by metadata (site name)
df = corpus.to_dataframe(level="word")   # pandas-native, one row per word

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
| [`aegean.core`](Architecture) | Script-agnostic model: `Corpus`, `Document`, `Token`, `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance, a lossless JSON round-trip, and a compound `query()` |
| [Linear A](Linear-A) | Bundled 1,721-inscription corpus, the full Unicode Linear A repertoire (342 signs; 50 carry conventional sound values), sign→sound map, transliteration |
| [Linear B](Linear-B) | Mycenaean Greek: 211-sign Unicode inventory, transliteration, a Greek-reading bridge (`po-me → ποιμήν`), accounting, the full DAMOS corpus on demand (`aegean.load("damos")`, ~5,900 tablets) |
| [Cypriot](Cypriot) | Arcado-Cypriot Greek: 55-sign Unicode syllabary, transliteration, a Greek-reading bridge (`pa-si-le-u-se → βασιλεύς`), and a bundled **178-inscription corpus** (*Inscriptiones Graecae* XV 1, BBAW, CC BY 4.0) |
| [Cypro-Minoan](Cypro-Minoan) | Undeciphered Bronze Age Cyprus: 99-sign Unicode inventory + sign-sequence tokenization (no phonetics or bridge: the script is undeciphered) |
| [Analysis](Analysis) | Accounting reconciliation, sign-pattern search, phonetic distance/alignment, **cross-script comparison** (Linear B ↔ Greek by sound), morphology clustering, collocation stats, **corpus statistics** (dispersion, keyness, bootstrap), query engine, structure detection, an opt-in analysis cache |
| [Greek NLP](Greek-NLP) | Beta Code↔Unicode, tokenize, syllabify, accent & prosody, **metrical scansion**, reconstructed IPA, POS tagging, **morphological analysis**, lemmatize; **opt-in** Perseus-treebank lemmas/POS (`use_treebank`), a **lexicon registry** (`use_lexicon`: LSJ, Middle Liddell, Cunliffe, Abbott-Smith) with Logeion deep-links, generalizing pure-Python taggers/lemmatizers/parser, and the **neural pipeline** (`use_neural_pipeline`): joint tagging + morphology + **UD parsing** + lemmatization, state of the art on the UD Ancient Greek (Perseus) benchmark (97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.6 LAS, Perseus test): plus real works on demand (`load_work`), an offline **discovery catalogue** of ~1,800 loadable works (`greek.catalog()` / `aegean greek catalog`), a **benchmark** harness, **inflection synthesis** (`inflect` / `paradigm`), **terminology rarity** (`terminology_rarity`), **dialect/register** tags (`usage`), and a **PROIEL convention-drift** breakdown (`proiel_drift`) |
| [`aegean.io`](Architecture) | Import **and** export: bring your own text in (`from_text` / `from_text_file` / `from_text_dir` / `from_csv`, and `aegean import` from the shell) → a real `Corpus`; export to EpiDoc (TEI), CSV, and Parquet |
| [CLI](CLI) | The **`aegean` command line** (`[cli]` extra): the whole toolkit without writing Python: a guided `quickstart` tour, an interactive `repl` (persistent history, session corpus), a full-screen `tui` terminal UI (the `[tui]` extra), corpus commands, the full Greek NLP pipeline, analysis, data fetching, an offline `doctor` environment check, and the (exploratory) AI layer; `--json` everywhere, stdin-pipeable |
| [Geography](Geography) | `aegean.geo`: corpus → geopandas GeoDataFrame (per-inscription or per-site points) from a bundled, Pleiades-aligned Aegean gazetteer, for mapping/spatial analysis |
| `aegean.viz` ([Analysis](Analysis)) | One-line plots (the `[viz]` extra): frequency bars, dispersion/keyness charts, co-occurrence networks, accounting diagonals, scansion grids, and `aegean plot` from the shell |
| [AI Layer](AI-Layer) | Multi-provider clients (Anthropic/OpenAI/Grok/Gemini/OpenRouter), grounding, caching, exploratory-labeled capabilities, hybrid translation |
| [Data & Provenance](Data-and-Provenance) | Bundled data, download-to-cache, citation/licensing |

The **[API reference](https://ryanpavlicek.github.io/pyaegean/)** documents every public module, class,
and function, generated from the docstrings and type hints: complementing the guides above.

## Install

```bash
pip install pyaegean            # core + Linear A + Greek
pip install "pyaegean[cli]"     # + the `aegean` command line
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini / OpenRouter clients
pip install "pyaegean[all]"     # everything
```

See [Installation](Installation) for the full extras matrix, and
[Development](Development) to build from source and run the test suite.

## Roadmap

**Current release: v0.27.0.** pyaegean covers all four Aegean scripts and a deep, zero-dependency
Greek NLP track (opt-in treebank, lexicon, and neural backends, including the state-of-the-art
neural joint pipeline), a structured corpus and provenance data layer, the `aegean` CLI, the
`aegean-mcp` server, and a grounded multi-provider AI layer. The pages in the sidebar cover every
feature in depth; the [CHANGELOG](https://github.com/ryanpavlicek/pyaegean/blob/main/CHANGELOG.md)
has the per-release history.

**On the list next:**

- More public-domain dictionaries in the registry (Autenrieth, Slater), as their open digitizations are confirmed license-clean
- SigLA apparatus decoding; richer `load_work` addressing across more of the Perseus / First1KGreek canon
- Wider gazetteer / Pleiades coverage

## For specialists

Aegean epigrapher, Mycenologist, philologist, or historical linguist? See
**[For Specialists](For-Specialists)** for what's established vs. exploratory and
how to file a correction, validate an exploratory result, or contribute a sourced
fact: your judgement is part of how the toolkit stays trustworthy.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via
mwenge/lineara.xyz; facsimile imagery © École Française d'Athènes (referenced,
not redistributed). See [Data & Provenance](Data-and-Provenance).
