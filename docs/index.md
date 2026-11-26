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

**Latest PyPI release: v0.70.0 (beta).** See the
[scholarly workflow](scholarly-workflow.md) for source preservation, optional review,
counting choices, and translation evidence.

The core installs with zero third-party dependencies and runs offline. The opt-in neural
pipeline scores **97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.7 LAS** end-to-end on
the UD Ancient Greek (Perseus) test fold ([protocol and tables](benchmarks.md)). Structural
and generative outputs on undeciphered scripts (Linear A, Cypro-Minoan) carry an `exploratory`
flag.

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

This default is a deterministic baseline for a first pass. Its tables and ending
rules can return a wrong POS or lemma even when `review_recommended` is False.
That flag selects identity/unresolved lemma fallbacks, not every error; for higher
accuracy and calibrated risk-ranked review queues, activate the opt-in neural pipeline
with `greek.use_calibration_registry()` (and optionally `greek.use_oov_lemma_reranker(config="weighted")`).

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

Recent releases also add named sentence policies (`prose`, `verse`, `inscription`, `papyrus`),
compact editable review spreadsheets (`layout="editable"`) with calibrated-risk prioritization,
resumable SQLite corpus annotation jobs (`aegean db annotate`), contextual dictionary grounding
and clause-by-clause checking for AI translation, lossless CoNLL-U preservation, and optional
[interoperability adapters](interoperability.md) for spaCy, Stanza, and CLTK. The
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
covers the eight fetchable epigraphic and papyrological corpora (I.Sicily, IIP, IOSPE,
IGCyr/GVCyr, Aphrodisias IAph2007, Cretan Institutional Inscriptions, the EDH Greek subset,
and the DDbDP documentary papyri), per-token reading statuses, and each corpus's
edition-fidelity flag.

**I study Biblical, Second Temple & Patristic Greek.**
[Biblical & Koine Greek](https://github.com/ryanpavlicek/pyaegean/wiki/New-Testament) and the
[`aegean.greek.bible`](api/greek_bible.md) reference cover the `aegean bible` CLI, the `b` screen in
`aegean tui` (with inline downloads for missing bundles), **9 collated Greek NT editions**
(`nestle1904`, `sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`), **13 early
2nd–5th c. CE manuscript witnesses** with *nomina sacra* expansion, 11,142-entry Extended Strong's
with root tracing, the **55-book Swete Septuagint** (`lxx-corpus`), and **86 Greek patristic
commentaries** across 10 Church Fathers/traditions (First1KGreek + *Patrologia Graeca*). Install
packs at once with `aegean bible install` or `aegean library install patristic` (adding Open
Apostolic Fathers, 44 Greek OT Pseudepigrapha, and 33 *Patrologia Graeca* volumes; see
[`aegean.library`](api/library.md)).

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

**I want to reproduce the public evidence or help maintain the project.**
[Independent review](review.md) starts with one offline command, explains exactly what
its receipt does and does not establish, and links the model card, data card,
limitations, discrepancy form, and bounded maintainer tasks.

## Install

For persistent corpora and reviewed annotations, see the
[SQLite reference](api/db.md) and [review workflow](scholarly-workflow.md).

The core is zero-dependency; everything heavier is an opt-in extra:

| Install | What it adds |
|---|---|
| `pip install pyaegean` | Core + Linear A + Greek (zero heavy dependencies) |
| `pip install "pyaegean[cli]"` | The `aegean` command line |
| `pip install "pyaegean[tui]"` | The `aegean tui` full-screen terminal UI |
| `pip install "pyaegean[neural]"` | The neural Greek pipeline and lemmatizer (onnxruntime; no torch) |
| `pip install "pyaegean[interop]"` | spaCy/Stanza adapters plus CLTK on Python 3.13+; Stanza installs PyTorch |
| `pip install "pyaegean[ai]"` | Anthropic / OpenAI / Grok / Gemini / OpenRouter clients, plus a local no-key option |
| `pip install "pyaegean[mcp]"` | The `aegean-mcp` Model Context Protocol server (for agents) |
| `pip install "pyaegean[all]"` | The bundled runtime stack, including neural; excludes Parquet, `viz-interactive`, and the separate framework adapters |

Large assets (corpora, models, lexica) are never bundled: they fetch to a local cache,
sha256-pinned, only when you opt in.

## On this site

- **[API reference](api/index.md)**: the supported facade modules, with their public
  classes and functions generated from the source.
- **[Benchmarks](benchmarks.md)**: the measured accuracy numbers and the evaluation
  protocol behind them.
- **[Independent review](review.md)**: the one-command evidence receipt, its limits,
  and the path from reproduction to a precise discrepancy report.
- The **[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)** holds the guides,
  tutorials, and per-script handbooks linked above.
