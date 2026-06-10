# pyaegean

**A specialist Python toolkit for Ancient Greek** — alphabetic Greek *and* the
Aegean syllabic scripts (Linear A / Linear B). pyaegean focuses narrowly and
deeply on Greek and the Aegean world: a script-agnostic corpus data layer, the
analytical methods from the Linear A Research Workbench, translation, and a
pluggable multi-provider AI layer. The excellent [CLTK](https://cltk.org) already
serves many ancient languages broadly; pyaegean is intentionally narrower, and
uses CLTK as a friendly benchmark to measure its Greek coverage against.

> **Status: v0.4.0 (alpha).** The script-agnostic core, Linear A, Linear B (Mycenaean Greek),
> the Cypriot syllabary (Arcado-Cypriot Greek),
> the full Greek NLP track (opt-in Perseus-treebank lemmas/POS, a generalizing tagger and
> lemmatizer, a neural lemmatizer for unseen forms, LSJ glossing, a baseline dependency parser,
> and a CLTK benchmark harness), and the multi-provider AI layer are all implemented.
> Analytical output on the undeciphered Linear A material is **exploratory** — see the
> methodology and limitations.

## Install

```bash
pip install pyaegean              # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[neural]"    # + the neural Greek lemmatizer (onnxruntime; no torch)
pip install "pyaegean[ai]"        # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"       # the data, AI, EpiDoc, and geo extras
```

> **New to Python, or not a programmer?** You're exactly who this tool is for.
> The **[Getting Started guide](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)**
> walks you from "I have nothing installed" to your first result — no prior coding
> assumed.

## Quick start

Prefer to learn by doing? Run the guided tour in your browser — nothing to install:
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)

```python
import aegean

corpus = aegean.load("lineara")          # 1,721 inscriptions, bundled, offline
print(len(corpus))                       # 1721

ht = corpus.filter(site="Haghia Triada") # filter by metadata (full site name)
df = corpus.to_dataframe(level="word")   # pandas-native, one row per word

from aegean.analysis import balance_check, word_matches_sign_pattern
checks = balance_check(corpus.get("HT13"))          # KU-RO accounting reconciliation
hits = [w for w, _ in corpus.word_frequencies()
        if word_matches_sign_pattern(w, "KU-*-RO")] # wildcard sign search
```

And a taste of the Greek pipeline:

```python
from aegean import greek

greek.betacode_to_unicode("mh=nin")     # 'μῆνιν'   (type Greek in plain ASCII)
greek.syllabify("ἄνθρωπος")             # ['ἄν', 'θρω', 'πος']
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'             (Odyssey 1.1)
[str(a) for a in greek.analyze("λόγον")][:2]
# ['λόγος [NOUN acc sg masc]', 'λόγος [NOUN acc sg fem]']
```

The full Linear A facsimile mirror (3,368 images, ~116 MB) is **not** bundled;
fetch it on demand: `aegean.data.fetch("lineara-images")` (downloaded from the
workbench repo, sha256-verified, cached locally — never re-hosted). The opt-in Greek
backends likewise fetch large CC BY-SA assets to cache on first use (never bundled):
the Perseus AGDT treebank (~75 MB, `greek.use_treebank()`) and the full Perseus LSJ
(~270 MB, `greek.use_lsj()`).

## What's here

- **`aegean.core`** — script-agnostic model: `Corpus`, `Document`, `Token`,
  `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance.
- **`aegean.scripts.lineara`** — Linear A: bundled corpus + 84-sign inventory +
  sign→sound map + transliteration.
- **`aegean.scripts.linearb`** — Linear B (Mycenaean Greek): 211-sign Unicode inventory +
  transliteration + a Greek-reading bridge (`po-me → ποιμήν`) + accounting; bring-your-own corpus.
- **`aegean.scripts.cypriot`** — Cypriot syllabary (Arcado-Cypriot Greek): 55-sign Unicode
  inventory + transliteration + a Greek-reading bridge (`pa-si-le-u-se → βασιλεύς`).
- **`aegean.analysis`** — ported from the workbench: accounting reconciliation,
  wildcard sign-pattern search, weighted phonetic distance + alignment,
  morphology clustering, collocation statistics, a compound-query engine, and
  heuristic tablet-structure classification (all with golden-fixture parity).
- **`aegean.greek`** — the Greek NLP track: Unicode/Beta Code normalization,
  word/sentence tokenization, syllabification, accent and prosody analysis,
  metrical scansion (dactylic hexameter + elegiac pentameter), reconstructed IPA,
  POS tagging, a rule-based morphological analyzer (with an optional
  Perseus-treebank–backed lexicon for attested, accented lemmas), and lemmatization from a
  rule-based baseline up to an opt-in **neural lemmatizer** (`use_neural_lemmatizer`; a GreTa
  seq2seq that reaches 76.3% on *unseen* forms), with a pure-Python edit-tree generalizer
  (`use_lemmatizer`) as the zero-dependency option. Also an opt-in
  **generalizing POS tagger** (`use_tagger`; ~84% on *unseen* forms), **LSJ glossing**
  (`use_lsj` → `gloss`/`lookup`), a baseline **dependency parser** (`use_parser` → `parse`;
  ~0.67 UAS / 0.57 LAS on projective AGDT), and a **CLTK benchmark harness**.
  `aegean.load("greek")` loads a small bundled sample corpus (Archaic→Koine).
- **`aegean.data`** — bundled-data access + download-to-cache for large assets.
- **`aegean.ai`** — multi-provider AI layer: a provider-agnostic
  `LLMClient` (Anthropic default, plus OpenAI, xAI Grok, Gemini — SDKs optional),
  response caching, corpus grounding, and capabilities (translate, gloss,
  decipherment hypotheses, NLP-assist, ask/summarize). Every generative result is
  labeled **exploratory** with provenance. `aegean.translate` is the hybrid
  lexicon+LLM front end.

## Documentation

Full documentation lives in the **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**:

- **[Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)** — for newcomers to Python
- **[Example notebook](notebooks/getting-started.ipynb)** — a runnable guided tour ([open in Colab](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb))
- **[Tutorial](https://github.com/ryanpavlicek/pyaegean/wiki/Tutorial)** — two guided, end-to-end research walkthroughs
- **[Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A)** · **[Analysis](https://github.com/ryanpavlicek/pyaegean/wiki/Analysis)** · **[Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP)** · **[AI Layer](https://github.com/ryanpavlicek/pyaegean/wiki/AI-Layer)** — reference per domain
- **[Data & Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)** · **[FAQ](https://github.com/ryanpavlicek/pyaegean/wiki/FAQ)**

## Roadmap

**Shipped (through v0.3):** the script-agnostic core and Linear A; the multi-provider AI layer
and translation; and the deep Greek NLP track — Perseus-treebank lemmas/POS, a generalizing
tagger and lemmatizer, the neural lemmatizer, LSJ glossing, a baseline dependency parser, and a
CLTK benchmark harness. **v0.4** adds **Linear B** (Mycenaean Greek: a Unicode-built sign
inventory, transliteration, a Greek-reading bridge, and accounting; the full corpus is
bring-your-own) and the **Cypriot syllabary** (Arcado-Cypriot Greek). **Next:** a hand-checked
out-of-AGDT gold set, Cypro-Minoan, and a stable v1.0.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz;
facsimile imagery © École Française d'Athènes (referenced, not redistributed). The
opt-in Greek backends fetch the Perseus AGDT treebank (CC BY-SA 3.0) and Perseus LSJ
(CC BY-SA 4.0) to cache — built locally, never bundled or re-hosted. See `NOTICE`.
