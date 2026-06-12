# pyaegean

**A specialist Python toolkit for Ancient Greek and the Aegean syllabic scripts** — alphabetic
Greek *and* Linear A, Linear B, the Cypriot syllabary, and Cypro-Minoan, through one small,
dependency-light library.

[![PyPI](https://img.shields.io/pypi/v/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![Python](https://img.shields.io/pypi/pyversions/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml)

> **Status: v0.8.0 (beta).** Usable and tested, but the API may still shift, and a **1.0** waits
> on outside use and a short methods write-up. Analytical and generative output on the
> *undeciphered* material (Linear A, Cypro-Minoan) is **exploratory** — leads for a human expert,
> never ground truth. The bundled Linear A corpus is a *normalized* transcription (no full
> epigraphic apparatus); for edition-grade readings consult GORILA / SigLA.

---

## What this is

The Greek world wrote in more than one script. **Alphabetic Greek** carries Homer, the tragedians,
and the New Testament. Centuries earlier, the **Aegean syllabic scripts** recorded the Bronze Age:
**Linear B** (Mycenaean Greek, deciphered), the **Cypriot syllabary** (Arcado-Cypriot Greek,
deciphered), and two scripts we still *cannot read* — **Linear A** (Minoan) and **Cypro-Minoan**.

**pyaegean** is a narrow, deep toolkit for all of it: a **script-agnostic corpus data layer**, a
full **Greek NLP pipeline**, the analytical methods of the [Linear A Research
Workbench](https://github.com/ryanpavlicek/linearaworkbench) ported to Python, and a grounded,
multi-provider **AI layer** — under a hard rule that it tells you where it's confident and where
it's guessing. The core installs with **zero heavy dependencies** and imports instantly; heavier
backends (models, treebanks, lexica) are opt-in and fetched to a local cache, never bundled.

**Who it's for:** classicists and computational philologists who want a clean, citable data layer;
students; and the Python-curious — the
[Getting Started guide](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started) assumes no
prior programming.

## Highlights

| | |
|---|---|
| **All four Aegean scripts, one API** | `aegean.load("lineara")` gives the bundled **1,721-inscription** Linear A corpus over the full Unicode Linear A sign repertoire (84 signs carry conventional sound values, the rest are undeciphered); Linear B, the Cypriot syllabary, and Cypro-Minoan add Unicode-built inventories with small *illustrative* text samples (bring your own corpus for Linear B — see below). The two *deciphered* syllabaries transliterate and bridge into Greek — `po-me → ποιμήν` (Linear B), `pa-si-le-u-se → βασιλεύς` (Cypriot). |
| **A deep Greek NLP pipeline** | Beta Code ↔ Unicode (Beta Code is the plain-ASCII way of typing polytonic Greek), tokenize, syllabify, accent & prosody, **metrical scansion** (it scans the *Odyssey*'s opening — and honestly *declines* a line that only fits via synizesis), reconstructed IPA (Attic / Koine), POS, morphology, and lemmatization. Opt-in backends add attested lemmas/POS (Perseus treebank), **LSJ glossing**, and pure-Python generalizing taggers/lemmatizers. |
| **State-of-the-art neural NLP** | The opt-in **neural pipeline** (`greek.use_neural_pipeline()`; runs without PyTorch): one jointly-trained model for tagging, full morphology, **dependency parsing** (Universal Dependencies trees), and lemmatization — in plain terms, it reads a Greek sentence and tells you each word's part of speech, grammatical form, dictionary headword, and place in the sentence's structure. Measured end-to-end through this package at **96.9 UPOS / 96.1 UFeats / 94.4 lemma / 89.2 UAS / 84.4 LAS** on the UD Ancient Greek (Perseus) test benchmark — the strongest published results we know of ([protocol & tables](docs/benchmarks.md)). |
| **Real texts on demand** | `greek.load_work("tlg0012.tlg001")` fetches a complete work — the Iliad arrives as 24 books / ~127k tokens — from Perseus canonical-greekLit / First1KGreek (CC BY-SA, commit-pinned, cached) straight into the corpus model. |
| **Accounting reconciliation** | Parses Aegean decimal numerals and metrological fractions, sums each tablet's line items, and checks them against the stated **KU-RO** (Linear A) / **to-so** (Linear B) total — flagging which balance and which don't. (≈40 of the 1,721 Linear A tablets carry a checkable total; most are too fragmentary — that's the nature of the corpus, not a limit of the tool.) |
| **An analyst's toolkit** | Ported from the Linear A Workbench: wildcard **sign-pattern search** (`KU-*-RO`), weighted **phonetic distance + alignment**, **morphological clustering**, **collocation statistics** (PMI, log-likelihood, Fisher's exact), and a compound **query engine** with AND / OR / NOT. |
| **A clean, citable data layer** | `Corpus` / `Document` / `Token` / `Sign` value objects, a pandas `to_dataframe()`, a **lossless JSON round-trip** (`to_json` / `from_json`), a first-class **`query()`**, and **schema-valid EpiDoc / CSV / Parquet** export via `aegean.io` (the EpiDoc validates against the official EpiDoc RelaxNG and round-trips editorial status). Every corpus carries provenance and a one-line citation. |
| **Map the find-sites** | `aegean.geo` turns a corpus into a geopandas **GeoDataFrame** — a point per inscription or per site (EPSG:4326) from a bundled Aegean gazetteer — so you can map where a word clusters or how far a script reaches. `pip install pyaegean[geo]`. |
| **Grounded, multi-provider AI** | `aegean.ai` / `aegean.translate` front Anthropic, OpenAI, Grok, and Gemini. Every generative reading is built on a **local, deterministic grounding** step from the tools above, and is labeled **exploratory** with its provenance — a hypothesis, never an assertion. |
| **Honest about what's known** | Deciphered Greek gets real scholarship (attested lemmas, gold POS, measured accuracy). The *undeciphered* material — Linear A, Cypro-Minoan — is labeled **EXPLORATORY** everywhere: the tools surface *leads*, never answers. |

## Install

```bash
pip install pyaegean              # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[cli]"       # + the `aegean` command line
pip install "pyaegean[neural]"    # + the neural Greek pipeline & lemmatizer (onnxruntime; no torch)
pip install "pyaegean[ai]"        # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"       # the data, AI, EpiDoc, geo, and CLI extras
```

## Try it

**No install required** — run the guided tour in your browser, nothing to set up:
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)

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
```

Or skip Python entirely — the **`aegean` CLI** (`[cli]` extra) covers the whole toolkit,
with `--json` on every command and stdin piping:

```bash
aegean show lineara HT13                       # one tablet, line by line
aegean balance lineara --strict                # reconcile every stated total
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural --json
```

Everything above runs **offline with zero heavy dependencies**. Large assets are fetched to a local
cache only when you opt in (and never bundled inside the wheel): the full Linear B corpus
(`aegean.load("damos")`), the SigLA Linear A dataset (`aegean.load("sigla")`), the Linear A
facsimile mirror (`aegean.data.fetch("lineara-images")`), the AGDT-derived lexicon and models
(`greek.use_treebank()` and friends — small prebuilt artifacts, with build-from-source as the
fallback), the LSJ index (`greek.use_lsj()`), and the neural models
(`greek.use_neural_lemmatizer()` / `use_neural_pipeline()`).

## Documentation

Full documentation lives in the **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**:

- **[Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)** — for newcomers to Python
- **[Example notebook](notebooks/getting-started.ipynb)** — a runnable guided tour ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb))
- **[Tutorial](https://github.com/ryanpavlicek/pyaegean/wiki/Tutorial)** — two guided, end-to-end research walkthroughs
- **[Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A)** · **[Linear B](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-B)** · **[Cypriot](https://github.com/ryanpavlicek/pyaegean/wiki/Cypriot)** · **[Cypro-Minoan](https://github.com/ryanpavlicek/pyaegean/wiki/Cypro-Minoan)** — per-script guides
- **[Recipes](https://github.com/ryanpavlicek/pyaegean/wiki/Recipes)** — end-to-end scholarly workflows, each ending in a citation
- **[Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP)** · **[CLI](https://github.com/ryanpavlicek/pyaegean/wiki/CLI)** · **[Analysis](https://github.com/ryanpavlicek/pyaegean/wiki/Analysis)** · **[AI Layer](https://github.com/ryanpavlicek/pyaegean/wiki/AI-Layer)** · **[Data & Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)** — reference
- **[API reference](https://ryanpavlicek.github.io/pyaegean/)** — every public module, class, and function, generated from the source

## Roadmap

Shipped through **v0.8**: the script-agnostic core and all four Aegean scripts; the full Greek NLP
track (treebank, LSJ, dependency parser, generalizing tagger + lemmatizer, the neural joint
pipeline, a benchmark harness, and a neutral out-of-AGDT evaluation); the full **DAMOS Linear B**
and **SigLA Linear A** corpora fetched on demand; corpus statistics (dispersion, keyness,
bootstrap), one-line plots, and cross-script phonetic comparison; the multi-provider AI layer with
traceable, measurable grounding; and a complete data layer — lossless JSON round-trip, a compound
`query()`, schema-valid EpiDoc / CSV / Parquet export, an opt-in analysis cache, and
Pleiades-aligned find-sites.

On the list next:

- DAMOS scribal-hand analysis and SigLA apparatus decoding
- Richer `load_work` addressing across more of the Perseus / First1KGreek canon
- A smaller neural model (selective quantization, optional GPU execution), held to the same accuracy gate
- Morpheus-backed tables for the offline morphology tier
- Wider gazetteer / Pleiades coverage

A **1.0** waits on outside use and a short methods write-up.


## About the author

Ryan Pavlicek. I'm a software engineer in Cincinnati, Ohio. My classical-languages credentials start
and end at amateur Koine Greek: proficient enough (maybe ~85–90%) to read the Greek New Testament, no
further. I'm not a classicist or a Bronze Age epigrapher, and I have no illusions about becoming
one. But building serious, honest software tooling for working with ancient languages this
hard (one of them undeciphered by definition), struck me as an unusually fun engineering problem.

pyaegean is an outsider's library that the actual specialists are free to pick up, ignore, or
correct. If something here is wrong, please open an issue or contact me directly.
All feedback is welcome.

**Email**: 'ryan [dot] pavlicek [dot] github [at] gmail [dot] com'

*(Replace `[at]` with `@` and `[dot]` with `.`)*


## Citation

If pyaegean helped with work you publish, a citation is genuinely appreciated — it's how a small
open project justifies the time. In the scholarly spirit, two layers:

1. **Always cite the underlying scholarship** pyaegean stands on — GORILA (Godart & Olivier
   1976–1985) for Linear A; the Perseus AGDT treebank, LSJ, and (for fetched works) the Perseus
   Digital Library / Open Greek and Latin for Greek; the Unicode Character Database for the
   Linear B / Cypriot / Cypro-Minoan sign data; and GreBerta/GreTa plus the AGDT, Gorman, and
   Pedalion treebanks behind the neural models. The editions are listed in [`NOTICE`](NOTICE),
   and every corpus emits its own source citation via `corpus.cite()`.
2. **Also cite pyaegean** if you used its analysis, methods, or outputs (pin the version you ran,
   for reproducibility). GitHub's **"Cite this repository"** button — generated from
   [`CITATION.cff`](CITATION.cff) — gives APA / BibTeX in one click, or use:

```bibtex
@software{pavlicek_pyaegean,
  author  = {Pavlicek, Ryan},
  title   = {{pyaegean: a Python toolkit for Ancient Greek and the Aegean syllabic scripts}},
  year    = {2026},
  version = {0.8.0},
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
clearly-labeled release assets and fetched to cache — NC data is never bundled inside the wheel.
See [`NOTICE`](NOTICE).
