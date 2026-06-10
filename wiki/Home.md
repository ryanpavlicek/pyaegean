# pyaegean

**A specialist Python toolkit for Ancient Greek** — alphabetic Greek *and* the
Aegean syllabic scripts (Linear A / Linear B). pyaegean focuses narrowly and
deeply on Greek and the Aegean world: a script-agnostic corpus data layer, the
analytical methods from the Linear A Research Workbench, translation, and a
pluggable multi-provider AI layer. The excellent [CLTK](https://cltk.org) serves
many ancient languages broadly; pyaegean is intentionally narrow and deep for Greek
and the Aegean scripts.

> **Status: v0.4.0 (alpha).** The script-agnostic core, Linear A, **Linear B** (Mycenaean Greek),
> and the **Cypriot syllabary** (Arcado-Cypriot Greek) are implemented — each with a sign
> inventory, transliteration, and (for the deciphered scripts) a Greek-reading bridge; the Greek
> NLP track is a full pipeline — including an opt-in Perseus
> AGDT treebank backend (attested lemmas + gold POS/morphology), a generalizing
> averaged-perceptron POS tagger (`use_tagger`; ~84% on unseen forms), a generalizing
> lemmatizer (`use_lemmatizer`; edit-trees) plus a neural seq2seq lemmatizer
> (`use_neural_lemmatizer`; 76.3% on unseen forms), LSJ glossing, a dependency parser,
> and a CLTK benchmark harness — and the multi-provider AI
> layer + hybrid translation are implemented. Analytical and generative output on the
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
| [`aegean.core`](Architecture) | Script-agnostic model: `Corpus`, `Document`, `Token`, `Sign`, `SignInventory`, `Numeral`, the `Script` plugin registry, provenance |
| [Linear A](Linear-A) | Bundled 1,721-inscription corpus, 84-sign inventory, sign→sound map, transliteration |
| [Linear B](Linear-B) | Mycenaean Greek: 211-sign Unicode inventory, transliteration, a Greek-reading bridge (`po-me → ποιμήν`), accounting, bring-your-own EpiDoc corpus |
| [Cypriot](Cypriot) | Arcado-Cypriot Greek: 55-sign Unicode syllabary, transliteration, a Greek-reading bridge (`pa-si-le-u-se → βασιλεύς`) |
| [Analysis](Analysis) | Accounting reconciliation, sign-pattern search, phonetic distance/alignment, morphology clustering, collocation stats, query engine, structure detection |
| [Greek NLP](Greek-NLP) | Beta Code↔Unicode, tokenize, syllabify, accent & prosody, **metrical scansion**, reconstructed IPA, POS tagging, **morphological analysis**, lemmatize; **opt-in** Perseus-treebank lemmas/POS (`use_treebank`), a **generalizing POS tagger** (`use_tagger`; ~84% on unseen forms) and **lemmatizer** (`use_lemmatizer`; edit-trees), a **neural seq2seq lemmatizer** (`use_neural_lemmatizer`; 76.3% on unseen forms), **LSJ glossing** (`use_lsj`), a **dependency parser** (`use_parser`), and a **CLTK benchmark** harness |
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

**Shipped (through v0.3):** the script-agnostic core and bundled Linear A corpus; the
multi-provider AI layer and hybrid translation; and a deep Greek NLP pipeline — treebank
lemmas/POS, LSJ glossing, a dependency parser, generalizing perceptron POS tagging
(~84% on unseen forms), edit-tree and neural seq2seq lemmatization (76.3% on unseen
forms), and a CLTK benchmark harness. **v0.4** adds **Linear B** (Mycenaean Greek: a
Unicode-built sign inventory, transliteration, a Greek-reading bridge, and accounting) and the
**Cypriot syllabary** (Arcado-Cypriot Greek). **Next:** Cypro-Minoan → v1.0 stable.

## License

Apache-2.0. Corpus data is GORILA (Godart & Olivier 1976–1985) via
mwenge/lineara.xyz; facsimile imagery © École Française d'Athènes (referenced,
not redistributed). See [Data & Provenance](Data-and-Provenance).
