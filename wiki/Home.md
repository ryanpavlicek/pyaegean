# pyaegean

**The definitive Python toolkit for Ancient Greek** — alphabetic Greek *and* the
Aegean syllabic scripts (Linear A / Linear B). A specialist library: where
generalist tools (CLTK) cover many ancient languages broadly, pyaegean goes deep
on Greek, with a script-agnostic corpus data layer, the analytical methods from
the Linear A Research Workbench, translation, and pluggable multi-provider AI.

> **Status: v0.1 → v0.2 (alpha).** The script-agnostic core and Linear A are
> fully implemented; the Greek NLP track has its first vertical slice; the
> multi-provider AI layer and hybrid translation are in foundation form.
> Analytical and generative output on the undeciphered Linear A material is
> **exploratory** — see [Data & Provenance](Data-and-Provenance).

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
| [`aegean.core`](Architecture) | Script-agnostic model: `Corpus`, `Document`, `Token`, `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance |
| [Linear A](Linear-A) | Bundled 1,721-inscription corpus, 84-sign inventory, sign→sound map, transliteration |
| [Analysis](Analysis) | Accounting reconciliation, sign-pattern search, phonetic distance/alignment, morphology clustering, collocation stats, query engine, structure detection |
| [Greek NLP](Greek-NLP) | Beta Code↔Unicode, tokenize, syllabify, accent analysis, baseline lemmatize + a sample corpus |
| [AI Layer](AI-Layer) | Multi-provider clients (Anthropic/OpenAI/Grok/Gemini), grounding, caching, exploratory-labeled capabilities, hybrid translation |
| [Data & Provenance](Data-and-Provenance) | Bundled data, download-to-cache, citation/licensing |

## Install

```bash
pip install pyaegean            # core + Linear A + Greek
pip install "pyaegean[ai]"      # + Anthropic / OpenAI / Grok / Gemini clients
pip install "pyaegean[all]"     # everything
```

See [Installation](Installation) for the full extras matrix, and
[Development](Development) to build from source and run the test suite.

## Roadmap

v0.1 core + Linear A + Greek start → **v0.2 AI layer + translation** → v0.3 deep
Greek NLP (benchmarked ≥ CLTK) → v0.4 Linear B (DAMOS/LiBER) → v0.5
Cypriot/Cypro-Minoan → v1.0 definitive.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via
mwenge/lineara.xyz; facsimile imagery © École Française d'Athènes (referenced,
not redistributed). See [Data & Provenance](Data-and-Provenance).
