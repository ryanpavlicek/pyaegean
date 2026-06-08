# FAQ & Troubleshooting

Common questions and the small snags that trip people up — especially if Python is
new to you. If your problem isn't here, please
[open an issue](https://github.com/ryanpavlicek/pyaegean/issues).

## Installing & running

### `ModuleNotFoundError: No module named 'aegean'`

Python can't find the library. Almost always one of:

1. **Your virtual environment isn't active.** Re-activate it (you do this every
   new terminal session) — `.venv\Scripts\Activate.ps1` on Windows,
   `source .venv/bin/activate` on macOS/Linux — then try again. See
   [Getting Started, Step 3](Getting-Started#step-3--make-a-project-folder-with-its-own-environment).
2. **It isn't installed in *this* environment.** Run `pip install pyaegean`.
3. You installed with one Python and are running another. Check with
   `pip show pyaegean` and `python --version`.

### `pip` says "permission denied" or wants admin rights

Don't install system-wide or use `sudo`. Make a
[virtual environment](Getting-Started#step-3--make-a-project-folder-with-its-own-environment)
and install into it — no special permissions needed.

### PowerShell won't run the activate script ("execution policy")

Run this once, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `ImportError` mentioning pandas, numpy, or scipy

These ship as dependencies and install automatically. If one is missing, your
environment is incomplete — reinstall with `pip install --force-reinstall pyaegean`.
(They're imported only when you call DataFrame or statistics features, which is why
`import aegean` itself stays fast.)

### How do I update to a newer version?

```bash
pip install --upgrade pyaegean
```

### Which Python versions are supported?

**Python 3.10 or newer.** Check with `python --version`.

## Greek text

### Greek shows up as boxes, `?`, or mojibake

That's a display/font issue, not a data problem — the text is correct underneath.

- **Best fix:** use [Jupyter](Getting-Started#option-c--jupyter-recommended-for-research)
  or a modern editor (VS Code), which render polytonic Greek cleanly.
- **In a Windows terminal:** run `chcp 65001` to switch it to UTF-8 first, and use
  a font with Greek coverage.
- If you write Greek to a file, open it as **UTF-8**.

### I don't have a Greek keyboard

You don't need one. Type **Beta Code** — the standard ASCII transliteration used by
the TLG and Perseus — and convert:

```python
from aegean import greek
greek.betacode_to_unicode("mh=nin")     # 'μῆνιν'
```

See [Greek NLP → Beta Code](Greek-NLP#normalization--beta-code) for the full key.

### My accents/breathings compare as unequal even though they look identical

Unicode has more than one way to encode the same accented letter. Normalise first:

```python
greek.normalize("ό")     # canonical NFC form
```

## Data, offline use & the AI layer

### Do I need an internet connection?

No. The core library, the full Linear A corpus, and the Greek pipeline all work
**offline**. Only two things touch the network: `data.fetch(...)` for large extra
assets (like the facsimile images), and the optional AI layer.

### Do I need an API key?

Only for the **[AI Layer](AI-Layer)** (translation, glossing, decipherment
hypotheses). Everything else — analysis, scansion, morphology, statistics — needs
no key and no account. To use AI, install a provider extra and set its key, e.g.
`pip install "pyaegean[anthropic]"` and `ANTHROPIC_API_KEY`.

### Where are downloaded/fetched files stored?

```python
from aegean import data
data.cache_dir()      # the cache location (override with the PYAEGEAN_CACHE env var)
```

## Trust & scholarship

### Is the Linear A "translation" real? Can I trust the analysis?

**No — and the library is built to keep you honest about this.** Linear A is
**undeciphered**. The phonetic values come from Linear B as a working convention,
and every analytical or AI method is labeled **exploratory**: evidence to weigh,
never a translation. Treat results as leads for a human expert, not answers.

### How accurate is the AI translation/glossing?

It's a hypothesis from a language model, returned as an `ExploratoryResult` with
provenance and an unmistakable exploratory label. Useful for ideas; never citable
as fact. Always verify against primary scholarship.

### How accurate is the Greek morphology / POS tagging?

The v0.1 engines are **baseline**: high-precision on closed classes (article,
prepositions, pronouns…) and regular paradigms, but they miss irregular,
third-declension, contract, and most open-class forms — and they tell you when a
result is reconstructed (`lemma_certain=False`). A treebank-trained upgrade is on
the [roadmap](Home#roadmap). See [Greek NLP](Greek-NLP#morphological-analysis).

### How do I cite pyaegean and its data in a paper?

Every corpus carries its citation, and the repo ships a `CITATION.cff`:

```python
corpus = aegean.load("lineara")
corpus.provenance.cite()
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```

See [Data & Provenance](Data-and-Provenance) for full licensing and attribution.

## Getting help

- **Bugs / feature requests:** [GitHub Issues](https://github.com/ryanpavlicek/pyaegean/issues).
- **How a function behaves:** the per-domain reference pages — [Linear A](Linear-A),
  [Analysis](Analysis), [Greek NLP](Greek-NLP), [AI Layer](AI-Layer).
- **Contributing a fix or a script plugin:** [Development](Development).
