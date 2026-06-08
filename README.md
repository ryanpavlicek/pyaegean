# pyaegean

**A specialist Python toolkit for Ancient Greek** — alphabetic Greek *and* the
Aegean syllabic scripts (Linear A / Linear B). pyaegean focuses narrowly and
deeply on Greek and the Aegean world: a script-agnostic corpus data layer, the
analytical methods from the Linear A Research Workbench, translation, and a
pluggable multi-provider AI layer. The excellent [CLTK](https://cltk.org) already
serves many ancient languages broadly; pyaegean is intentionally narrower, and
uses CLTK as a friendly benchmark to measure its Greek coverage against.

> **Status: v0.1 (alpha).** Script-agnostic core + Linear A fully implemented;
> the Greek NLP track and the AI layer are landing across v0.1–v0.2. See the
> roadmap. Analytical output on the undeciphered Linear A material is
> **exploratory** — see the methodology/limitations.

## Install

```bash
pip install pyaegean            # core + Linear A + Greek
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"     # everything
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
workbench repo, sha256-verified, cached locally — never re-hosted).

## What's here (v0.1)

- **`aegean.core`** — script-agnostic model: `Corpus`, `Document`, `Token`,
  `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance.
- **`aegean.scripts.lineara`** — Linear A: bundled corpus + 84-sign inventory +
  sign→sound map + transliteration.
- **`aegean.analysis`** — ported from the workbench: accounting reconciliation,
  wildcard sign-pattern search, weighted phonetic distance + alignment,
  morphology clustering, collocation statistics, a compound-query engine, and
  heuristic tablet-structure classification (all with golden-fixture parity).
- **`aegean.greek`** — the Greek NLP track: Unicode/Beta Code normalization,
  word/sentence tokenization, syllabification, accent and prosody analysis,
  metrical scansion (dactylic hexameter + elegiac pentameter), reconstructed IPA,
  POS tagging, a rule-based morphological analyzer (with an optional
  Perseus-treebank–backed lexicon for attested, accented lemmas), baseline
  lemmatization, and opt-in **LSJ glossing** (`use_lsj` → `gloss`/`lookup`).
  `aegean.load("greek")` loads a small bundled sample corpus (Archaic→Koine).
- **`aegean.data`** — bundled-data access + download-to-cache for large assets.
- **`aegean.ai`** (v0.2) — multi-provider AI layer: a provider-agnostic
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

v0.1 core + Linear A (+ Greek start) → v0.2 AI layer (multi-provider) +
translation → v0.3 deep Greek NLP (benchmarked against CLTK) → v0.4 Linear B
(DAMOS/LiBER) → v0.5 Cypriot/Cypro-Minoan → v1.0 stable.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via
mwenge/lineara.xyz; facsimile imagery © École Française d'Athènes (referenced,
not redistributed). See `NOTICE`.
