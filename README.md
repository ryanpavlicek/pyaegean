# pyaegean

**A specialist Python toolkit for Ancient Greek and the Aegean syllabic scripts** — alphabetic
Greek *and* Linear A, Linear B, the Cypriot syllabary, and Cypro-Minoan, through one small,
dependency-light library.

[![PyPI](https://img.shields.io/pypi/v/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![Python](https://img.shields.io/pypi/pyversions/pyaegean.svg)](https://pypi.org/project/pyaegean/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanpavlicek/pyaegean/actions/workflows/ci.yml)

> **Status: v0.7.0 (alpha).** Stable enough to use; the API may still shift before 1.0. Analytical
> and generative output on the *undeciphered* material (Linear A, Cypro-Minoan) is **exploratory** —
> leads for a human expert, never ground truth.

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
| **All four Aegean scripts, one API** | `aegean.load("lineara")` gives the bundled **1,721-inscription** Linear A corpus with an 84-sign inventory; Linear B, the Cypriot syllabary, and Cypro-Minoan come from Unicode-built inventories. The two *deciphered* syllabaries transliterate and bridge into Greek — `po-me → ποιμήν` (Linear B), `pa-si-le-u-se → βασιλεύς` (Cypriot). |
| **A deep Greek NLP pipeline** | Beta Code ↔ Unicode, tokenize, syllabify, accent & prosody, **metrical scansion** (it scans the *Odyssey*'s opening — and honestly *declines* a line that only fits via synizesis), reconstructed IPA (Attic / Koine), POS, morphology, and lemmatization. Opt-in backends add attested lemmas/POS (Perseus treebank), **LSJ glossing**, a dependency parser, a generalizing POS tagger (**~84%** on unseen forms), and a **neural lemmatizer** that reaches **76.3% on unseen forms** (a GreTa seq2seq served as torch-free ONNX). |
| **Accounting reconciliation** | Parses Aegean decimal numerals and metrological fractions, sums each tablet's line items, and checks them against the stated **KU-RO** (Linear A) / **to-so** (Linear B) total — flagging which balance and which don't. |
| **An analyst's toolkit** | Ported from the Linear A Workbench: wildcard **sign-pattern search** (`KU-*-RO`), weighted **phonetic distance + alignment**, **morphological clustering**, **collocation statistics** (PMI, log-likelihood, Fisher's exact), and a compound **query engine** with AND / OR / NOT. |
| **A clean, citable data layer** | `Corpus` / `Document` / `Token` / `Sign` value objects, a pandas `to_dataframe()`, a **lossless JSON round-trip** (`to_json` / `from_json`), a first-class **`query()`**, and **EpiDoc / CSV / Parquet** export via `aegean.io`. Every corpus carries provenance and a one-line citation. |
| **Grounded, multi-provider AI** | `aegean.ai` / `aegean.translate` front Anthropic, OpenAI, Grok, and Gemini. Every generative reading is built on a **local, deterministic grounding** step from the tools above, and is labeled **exploratory** with its provenance — a hypothesis, never an assertion. |
| **Honest by construction** | Deciphered Greek gets real scholarship (attested lemmas, gold POS, measured accuracy). The *undeciphered* material — Linear A, Cypro-Minoan — is labeled **EXPLORATORY** everywhere: the tools surface *leads*, never answers. |

## Install

```bash
pip install pyaegean              # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[neural]"    # + the neural Greek lemmatizer (onnxruntime; no torch)
pip install "pyaegean[ai]"        # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"       # the data, AI, EpiDoc, and geo extras
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
```

Everything above runs **offline with zero heavy dependencies**. Large assets are fetched to a local
cache only when you opt in (and never re-hosted): the Linear A facsimile mirror
(`aegean.data.fetch("lineara-images")`), the Perseus AGDT treebank (`greek.use_treebank()`), the
full LSJ lexicon (`greek.use_lsj()`), and the neural lemmatizer model
(`greek.use_neural_lemmatizer()`).

## Documentation

Full documentation lives in the **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**:

- **[Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)** — for newcomers to Python
- **[Example notebook](notebooks/getting-started.ipynb)** — a runnable guided tour ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb))
- **[Tutorial](https://github.com/ryanpavlicek/pyaegean/wiki/Tutorial)** — two guided, end-to-end research walkthroughs
- **[Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A)** · **[Linear B](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-B)** · **[Cypriot](https://github.com/ryanpavlicek/pyaegean/wiki/Cypriot)** · **[Cypro-Minoan](https://github.com/ryanpavlicek/pyaegean/wiki/Cypro-Minoan)** — per-script guides
- **[Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP)** · **[Analysis](https://github.com/ryanpavlicek/pyaegean/wiki/Analysis)** · **[AI Layer](https://github.com/ryanpavlicek/pyaegean/wiki/AI-Layer)** · **[Data & Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)** — reference

## Roadmap

Shipped through **v0.7**: the script-agnostic core and all four Aegean scripts; the full Greek NLP
track (treebank, LSJ, dependency parser, generalizing tagger + lemmatizer, the neural lemmatizer, a
benchmark harness, and a neutral out-of-AGDT evaluation); the multi-provider AI + translation layer;
and a complete data layer — lossless JSON round-trip, a compound `query()`, and EpiDoc / CSV /
Parquet export. **Next:** a stable **v1.0** (API + docs freeze). The
[wiki](https://github.com/ryanpavlicek/pyaegean/wiki) has the full roadmap.

## About the author

Ryan Pavlicek — a software engineer in Cincinnati, Ohio. My classical-languages credentials start
and end at amateur Koine Greek: proficient enough (~85–90%) to read the Greek New Testament, no
further. I'm not a classicist or a Bronze Age epigrapher, and I have no illusions about becoming
one. But I live in the shadow of the University of Cincinnati's world-class Classics and Greek
Bronze Age Archaeology department, and building serious, honest infrastructure for languages this
hard — one of them undeciphered by definition — struck me as an unusually fun engineering problem.
pyaegean is an outsider's library that the actual specialists are free to pick up, ignore, or
correct. If something here is wrong, please open an issue — I'd rather ship something honest than
something flattering.

## License

Apache-2.0. Linear A corpus data is GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz; the
Linear B / Cypriot / Cypro-Minoan sign data is from the Unicode Character Database. Facsimile imagery
© École Française d'Athènes (referenced, not redistributed). The opt-in Greek backends fetch the
Perseus AGDT treebank (CC BY-SA 3.0) and LSJ (CC BY-SA 4.0) to cache — built locally, never bundled
or re-hosted. See [`NOTICE`](NOTICE).
