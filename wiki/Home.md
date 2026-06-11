# pyaegean

**A specialist Python toolkit for Ancient Greek** — alphabetic Greek *and* the
Aegean syllabic scripts (Linear A, Linear B, Cypriot, and Cypro-Minoan). pyaegean focuses narrowly and
deeply on Greek and the Aegean world: a script-agnostic corpus data layer, the
analytical methods from the Linear A Research Workbench, translation, and a
pluggable multi-provider AI layer.

> **Status: v0.8.0 (beta).** A young, beta-stage project — the API is close to stable, but a 1.0
> awaits external use and a methods write-up. The script-agnostic core, Linear A, **Linear B** (Mycenaean Greek),
> the **Cypriot syllabary** (Arcado-Cypriot Greek), and the undeciphered **Cypro-Minoan** script
> complete the Aegean set — each deciphered script with a sign inventory, transliteration, and a
> Greek-reading bridge; Cypro-Minoan, undeciphered, ships its sign inventory only. The Greek
> NLP track is a full pipeline: a zero-dependency core (tokenize → scansion → IPA → POS →
> morphology → lemmas), opt-in backends (Perseus AGDT treebank, LSJ glossing, generalizing
> taggers/lemmatizers), and an opt-in **neural pipeline** (`use_neural_pipeline`) — one
> jointly-trained torch-free model for tagging, morphology, **UD dependency parsing**, and
> lemmatization that is **state of the art on the UD Ancient Greek benchmarks**
> ([measured](Greek-NLP#the-neural-pipeline-opt-in): 96.9 UPOS / 94.4 lemma / 89.2 UAS on the
> Perseus test fold, end-to-end from raw text) — plus a benchmark harness and a neutral
> out-of-AGDT (PROIEL) evaluator. The multi-provider AI layer + hybrid translation are
> implemented, over a corpus data layer with a lossless JSON round-trip (`to_json`/`from_json`)
> and a compound `query()`, plus EpiDoc/CSV/Parquet export. Analytical and generative output on the
> undeciphered Linear A material is **exploratory** — see [Data & Provenance](Data-and-Provenance).

### New here?

- **Never used Python?** Start with **[Getting Started](Getting-Started)** — it
  walks you from "I have nothing installed" to your first result, no prior
  programming assumed.
- **Want to learn by doing?** The **[Tutorial](Tutorial)** answers two real
  research questions end to end — one in Linear A, one in Greek.
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
| [Linear A](Linear-A) | Bundled 1,721-inscription corpus, the full Unicode Linear A repertoire (~344 signs; 84 carry conventional sound values), sign→sound map, transliteration |
| [Linear B](Linear-B) | Mycenaean Greek: 211-sign Unicode inventory, transliteration, a Greek-reading bridge (`po-me → ποιμήν`), accounting, bring-your-own EpiDoc corpus |
| [Cypriot](Cypriot) | Arcado-Cypriot Greek: 55-sign Unicode syllabary, transliteration, a Greek-reading bridge (`pa-si-le-u-se → βασιλεύς`) |
| [Cypro-Minoan](Cypro-Minoan) | Undeciphered Bronze Age Cyprus: 99-sign Unicode inventory + sign-sequence tokenization (no phonetics or bridge — the script is undeciphered) |
| [Analysis](Analysis) | Accounting reconciliation, sign-pattern search, phonetic distance/alignment, morphology clustering, collocation stats, query engine, structure detection |
| [Greek NLP](Greek-NLP) | Beta Code↔Unicode, tokenize, syllabify, accent & prosody, **metrical scansion**, reconstructed IPA, POS tagging, **morphological analysis**, lemmatize; **opt-in** Perseus-treebank lemmas/POS (`use_treebank`), **LSJ glossing** (`use_lsj`), generalizing pure-Python taggers/lemmatizers/parser, and the **neural pipeline** (`use_neural_pipeline`) — joint tagging + morphology + **UD parsing** + lemmatization, state of the art on the UD Ancient Greek benchmarks (96.9 UPOS / 94.4 lemma / 89.2 UAS, Perseus test) — plus a **benchmark** harness |
| [`aegean.io`](Architecture) | Export adapters: EpiDoc (TEI) write — the inverse of the bring-your-own reader — plus CSV and Parquet |
| [CLI](CLI) | The **`aegean` command line** (`[cli]` extra): the whole toolkit without writing Python — corpus commands, the full Greek NLP pipeline, analysis, data fetching, and the (exploratory) AI layer; `--json` everywhere, stdin-pipeable |
| [Geography](Geography) | `aegean.geo`: corpus → geopandas GeoDataFrame (per-inscription or per-site points) from a bundled Aegean gazetteer, for mapping/spatial analysis |
| [AI Layer](AI-Layer) | Multi-provider clients (Anthropic/OpenAI/Grok/Gemini), grounding, caching, exploratory-labeled capabilities, hybrid translation |
| [Data & Provenance](Data-and-Provenance) | Bundled data, download-to-cache, citation/licensing |

The **[API reference](https://ryanpavlicek.github.io/pyaegean/)** documents every public module, class,
and function, generated from the docstrings and type hints — complementing the guides above.

## Install

```bash
pip install pyaegean            # core + Linear A + Greek
pip install "pyaegean[cli]"     # + the `aegean` command line
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"     # everything
```

See [Installation](Installation) for the full extras matrix, and
[Development](Development) to build from source and run the test suite.

## Roadmap

**Shipped (through v0.8):** all four Aegean scripts (Linear A, Linear B, Cypriot, Cypro-Minoan);
a deep Greek NLP track — treebank lemmas/POS, LSJ glossing, generalizing pure-Python
taggers/lemmatizers/parser, the **neural joint pipeline** (state of the art on the UD Ancient
Greek benchmarks: 96.9 UPOS / 96.1 UFeats / 94.4 lemma / 89.2 UAS / 84.4 LAS, Perseus test,
end-to-end from raw text), and a benchmark harness; the multi-provider AI layer and hybrid
translation; the corpus data layer with a lossless JSON round-trip (`to_json`/`from_json`),
a compound `query()`, and schema-valid EpiDoc/CSV/Parquet export; geographic analysis with
Pleiades alignment; editorial-status round-trip (`ReadingStatus` ↔ EpiDoc `<unclear>`/`<supplied>`/`<gap>`);
and the full Unicode Linear A sign repertoire. **Next:** hardening toward a **1.0 stable** once
there's external use and a methods write-up.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via
mwenge/lineara.xyz; facsimile imagery © École Française d'Athènes (referenced,
not redistributed). See [Data & Provenance](Data-and-Provenance).
