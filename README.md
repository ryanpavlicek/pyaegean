# pyaegean

**The definitive Python toolkit for Ancient Greek** — alphabetic Greek *and* the
Aegean syllabic scripts (Linear A / Linear B). A specialist library: where
generalist tools (CLTK) cover many ancient languages broadly, pyaegean goes deep
on Greek, with a script-agnostic corpus data layer, the analytical methods from
the Linear A Research Workbench, translation, and pluggable multi-provider AI.

> **Status: v0.1 (alpha).** Script-agnostic core + Linear A fully implemented;
> the Greek NLP track and the AI layer are landing across v0.1–v0.2. See the
> roadmap. Analytical output on the undeciphered Linear A material is
> **exploratory** — see the methodology/limitations.

## Install

```bash
pip install pyaegean            # core + Linear A
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"     # everything
```

## Quick start

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

The full Linear A facsimile mirror (~500 MB) is **not** bundled; fetch it on
demand: `aegean.data.fetch("lineara-images")` (downloaded from the workbench
repo, cached locally — never re-hosted).

## What's here (v0.1)

- **`aegean.core`** — script-agnostic model: `Corpus`, `Document`, `Token`,
  `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance.
- **`aegean.scripts.lineara`** — Linear A: bundled corpus + 84-sign inventory +
  sign→sound map + transliteration.
- **`aegean.analysis`** — ported from the workbench: accounting reconciliation,
  wildcard sign-pattern search, weighted phonetic distance + alignment,
  morphology clustering, collocation statistics, a compound-query engine, and
  heuristic tablet-structure classification (all with golden-fixture parity).
- **`aegean.greek`** — the Greek NLP track (v0.1 start): Unicode/Beta Code
  normalization, word/sentence tokenization, syllabification, accent analysis,
  and baseline lemmatization. `aegean.load("greek")` loads a small bundled
  sample corpus (Archaic→Koine).
- **`aegean.data`** — bundled-data access + download-to-cache for large assets.
- **`aegean.ai`** (v0.2) — multi-provider AI layer: a provider-agnostic
  `LLMClient` (Anthropic default, plus OpenAI, xAI Grok, Gemini — SDKs optional),
  response caching, corpus grounding, and capabilities (translate, gloss,
  decipherment hypotheses, NLP-assist, ask/summarize). Every generative result is
  labeled **exploratory** with provenance. `aegean.translate` is the hybrid
  lexicon+LLM front end.

## Roadmap

v0.1 core + Linear A (+ Greek start) → v0.2 AI layer (multi-provider) +
translation → v0.3 deep Greek NLP (benchmarked ≥ CLTK) → v0.4 Linear B
(DAMOS/LiBER) → v0.5 Cypriot/Cypro-Minoan → v1.0 definitive.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via
mwenge/lineara.xyz; facsimile imagery © École Française d'Athènes (referenced,
not redistributed). See `NOTICE`.
