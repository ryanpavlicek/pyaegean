# pyaegean

**A specialist Python toolkit for Ancient Greek and the Aegean syllabic scripts**: alphabetic
Greek (Archaic through Koine) and Linear A, Linear B, the Cypriot syllabary, and Cypro-Minoan,
in one small, dependency-light library.

[Source on GitHub](https://github.com/ryanpavlicek/pyaegean){ .md-button .md-button--primary }
[API reference](api/index.md){ .md-button }
[User guide (wiki)](https://github.com/ryanpavlicek/pyaegean/wiki){ .md-button }
[Try it in your browser](https://pyaegean.xyz/demo/){ .md-button }
[Benchmarks](benchmarks.md){ .md-button }
[PyPI](https://pypi.org/project/pyaegean/){ .md-button }

**Latest PyPI release: v0.45.0 (beta).** This site documents the current release.

The core installs with zero heavy dependencies and runs offline. Claims are measured, not
asserted: the opt-in neural pipeline is measured end-to-end on the UD Ancient Greek (Perseus)
benchmark through the shipped package at
**97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.6 LAS** on the test fold
([protocol and tables](benchmarks.md)). Analytical output on the *undeciphered* material
(Linear A, Cypro-Minoan) is always labeled **exploratory**: leads for a human expert, never
ground truth.

## Quick start (60 seconds)

```bash
pip install pyaegean
```

Load a bundled corpus: 1,721 Linear A inscriptions, offline, no downloads:

```python
import aegean

corpus = aegean.load("lineara")
ht13 = corpus.get("HT13")
[t.text for t in ht13.tokens][:6]
# ['KA-U-DE-TA', 'VIN', '𐄁', 'TE', '𐄁', 'RE-ZA']
```

Analyze a Greek sentence, one call, per-token records:

```python
from aegean import greek

[(r.text, r.upos, r.lemma) for r in greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")]
# [('ἐν', 'ADP', 'ἐν'), ('ἀρχῇ', 'NOUN', 'ἀρχή'), ('ἦν', 'VERB', 'εἰμί'),
#  ('ὁ', 'DET', 'ὁ'), ('λόγος', 'NOUN', 'λόγος'), ('.', 'PUNCT', '.')]
```

Read an inscription's editorial apparatus: the bundled Cypriot-syllabary corpus
(*Inscriptiones Graecae* XV 1) carries a reading status on every word:

```python
doc = aegean.load("cypriot").get("IG XV 1, 120")
[(t.text, t.status.name) for t in doc.tokens]
# [('a-ke-se-to-ro', 'CERTAIN'), ('to', 'CERTAIN'), ('pa-po', 'CERTAIN'),
#  ('pa-si-le-wo-se', 'RESTORED'), ('ti-mo-ke-re-to-se', 'RESTORED'), ('e-mi', 'RESTORED')]
```

Everything above runs offline with zero heavy dependencies. Prefer not to install anything?
The [getting-started notebook](https://colab.research.google.com/github/ryanpavlicek/pyaegean/blob/main/notebooks/getting-started.ipynb)
runs in Colab, and the [in-browser demo](https://pyaegean.xyz/demo/) runs
the core pipeline client-side.

The current release includes isolated `GreekPipeline` instances, explicit safe policies for
overlength neural input, exact analysis receipts, source alignment, typed editorial form states,
and lossless CoNLL-U structure. The
[Greek NLP guide](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP#one-call-pipeline)
shows runnable examples.

## Find your path

**I'm a classicist analyzing texts.**
Start with [Getting Started](https://github.com/ryanpavlicek/pyaegean/wiki/Getting-Started)
(it assumes no prior programming), then
[Choosing a Workflow](https://github.com/ryanpavlicek/pyaegean/wiki/Choosing-a-Workflow) to
match your task to a working pattern, and
[Recipes](https://github.com/ryanpavlicek/pyaegean/wiki/Recipes) for end-to-end scholarly
workflows, each ending in a citation.
[Greek NLP](https://github.com/ryanpavlicek/pyaegean/wiki/Greek-NLP) is the full reference
for the pipeline (scansion, accentuation, IPA, tagging, lemmatization, parsing).

**I work with inscriptions or papyri.**
[Using Critical Editions](https://github.com/ryanpavlicek/pyaegean/wiki/Using-Critical-Editions)
covers the six fetchable epigraphic and papyrological corpora (I.Sicily, IIP, IOSPE,
IGCyr/GVCyr, the EDH Greek subset, and the DDbDP documentary papyri), per-token reading
statuses, and each corpus's edition-fidelity flag.

**I study the Aegean scripts.**
[Linear A](https://github.com/ryanpavlicek/pyaegean/wiki/Linear-A) is the per-script
handbook (Linear B, Cypriot, and Cypro-Minoan have siblings), and
[Limitations](https://github.com/ryanpavlicek/pyaegean/wiki/Limitations) states plainly what
the undeciphered material can and cannot support.

**I'm an NLP researcher and want the benchmark protocol.**
[Benchmarks](benchmarks.md) on this site is the canonical evaluation protocol and every
published number; the wiki
[Benchmarks](https://github.com/ryanpavlicek/pyaegean/wiki/Benchmarks) page adds the cited
cross-tool comparison tables, and
[Choosing a Pipeline](https://github.com/ryanpavlicek/pyaegean/wiki/Choosing-a-Pipeline)
maps material to the right backend. [Methodology](methodology.md) explains the evidence
registers, provenance, leakage controls, Aegean-script methods, and grounded-AI boundary.

## Install

The core is zero-dependency; everything heavier is an opt-in extra:

| Install | What it adds |
|---|---|
| `pip install pyaegean` | Core + Linear A + Greek (zero heavy dependencies) |
| `pip install "pyaegean[cli]"` | The `aegean` command line |
| `pip install "pyaegean[tui]"` | The `aegean tui` full-screen terminal UI |
| `pip install "pyaegean[neural]"` | The neural Greek pipeline and lemmatizer (onnxruntime; no torch) |
| `pip install "pyaegean[ai]"` | Anthropic / OpenAI / Grok / Gemini / OpenRouter clients, plus a local no-key option |
| `pip install "pyaegean[mcp]"` | The `aegean-mcp` Model Context Protocol server (for agents) |
| `pip install "pyaegean[all]"` | All supported runtime extras, including neural (except Parquet) |

Large assets (corpora, models, lexica) are never bundled: they fetch to a local cache,
sha256-pinned, only when you opt in.

## On this site

- **[API reference](api/index.md)**: the supported facade modules, with their public
  classes and functions generated from the source.
- **[Benchmarks](benchmarks.md)**: the measured accuracy numbers and the evaluation
  protocol behind them.
- The **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)** holds the guides,
  tutorials, and per-script handbooks linked above.
