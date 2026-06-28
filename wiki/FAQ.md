# FAQ & Troubleshooting

pyaegean is a free Python toolkit for Ancient Greek and the Aegean scripts
(Linear A, Linear B, Cypriot, Cypro-Minoan): you give it Greek text or an
inscription, and it gives back syllables, accents, metre, morphology, statistics,
corpus queries, and more. Use it to explore a corpus, scan verse, tag and
lemmatise Greek, or run honest, citeable analysis over undeciphered scripts.

This is a big Q&A for the snags that come up: install, Greek text, finding works
to load, the web demo, offline use, the AI layer, and citing your results. If your
question isn't here, please
[open an issue](https://github.com/ryanpavlicek/pyaegean/issues). New to all this?
Start with [Getting Started](Getting-Started).

---

## Installing & running

### `ModuleNotFoundError: No module named 'aegean'`

Python can't find the library. Almost always one of:

1. **Your virtual environment isn't active.** Re-activate it (you do this every
   new terminal session): `.venv\Scripts\Activate.ps1` on Windows,
   `source .venv/bin/activate` on macOS/Linux, then try again. See
   [Getting Started, Step 3](Getting-Started#step-3--make-a-project-folder-with-its-own-environment).
2. **It isn't installed in *this* environment.** Run `pip install pyaegean`.
3. You installed with one Python and are running another. Check with
   `pip show pyaegean` and `python --version`.

### `pip` says "permission denied" or wants admin rights

Don't install system-wide or use `sudo`. Make a
[virtual environment](Getting-Started#step-3--make-a-project-folder-with-its-own-environment)
and install into it: no special permissions needed.

### PowerShell won't run the activate script ("execution policy")

Run this once, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `ImportError` mentioning pandas

The core library has no hard third-party dependencies. pandas is an optional extra
for DataFrame output: install it with `pip install "pyaegean[data]"`. It's imported
only when you call a DataFrame feature, which is part of why `import aegean` stays
fast.

### How do I update to a newer version with pip?

```bash
pip install --upgrade pyaegean
```

That fetches the latest release from PyPI and installs it over the old one (no need
to uninstall first). A few tips:

- **Update an extra the same way**: keep the bracket so the optional dependencies
  upgrade too: `pip install --upgrade "pyaegean[cli]"` (or `[neural]`, `[all]`, …).
- **Check what you'll get / what you have:**

  ```bash
  pip index versions pyaegean      # versions available on PyPI
  pip show pyaegean                 # the version currently installed
  python -c "import aegean; print(aegean.__version__)"
  ```

- **Pin a specific version** if you need reproducibility: `pip install pyaegean==0.13.0`.
- **Cached datasets survive an upgrade.** Updating the package never re-downloads the
  corpora or models you've already fetched: they live in a separate cache (see
  [Where are downloaded/fetched files stored?](#where-are-downloadedfetched-files-stored)),
  keyed by an immutable version, so they're reused as-is.

### How do I install the optional features (the "extras")?

Everything past the offline core is opt-in, grouped into extras you add in brackets.
Install one (or several) with, e.g., `pip install "pyaegean[cli]"` or
`pip install "pyaegean[neural,viz]"`.

| Extra | What it adds |
|---|---|
| `data` | pandas, for DataFrame output (`to_dataframe`) |
| `parquet` | Parquet export (`pyarrow`) |
| `epidoc` | EpiDoc TEI import/export |
| `geo` | GeoJSON / geographic output |
| `viz` | plotting (`matplotlib`): figures and the scansion grid |
| `neural` | the neural pipeline + neural lemmatizer (most accurate Greek NLP) |
| `cli` | the `aegean` command-line interface |
| `mcp` | the MCP server, to drive pyaegean from an MCP client (e.g. Claude Code) |
| `anthropic` | the [AI Layer](AI-Layer) via Anthropic |
| `openai` | the AI Layer via OpenAI |
| `gemini` | the AI Layer via Google Gemini |
| `grok` | the AI Layer via xAI Grok |
| `ai` | the AI Layer core (provider-agnostic) |
| `dev` | the test/lint/type toolchain (contributors) |
| `docs` | the documentation toolchain (contributors) |
| `all` | everything above |

See [Installation](Installation) for the full breakdown.

### Which Python versions are supported?

**Python 3.10 or newer.** Check with `python --version`.

---

## Finding what you can load

### How do I see which corpora ship in the box?

`aegean.load("…")` opens a built-in corpus by id. The ids:

```python
import aegean
from aegean.core.corpus import _LOADERS
sorted(_LOADERS)
# ['cypriot', 'cyprominoan', 'damos', 'greek', 'lineara', 'linearb', 'nt', 'sigla']
```

| id | What it is | Offline? |
|---|---|---|
| `lineara` | the full Linear A corpus (1,721 documents) | yes, bundled |
| `linearb` | the bundled Linear B sample | yes, bundled |
| `greek` | a 5-passage Ancient Greek sample | yes, bundled |
| `cypriot` | the Cypriot Syllabary corpus | yes, bundled |
| `cyprominoan` | the Cypro-Minoan corpus | yes, bundled |
| `damos` | the full DAMOS Linear B corpus (~5,900 tablets, ~2 MB) | fetched on first use |
| `sigla` | the SigLA Linear A dataset (~1 MB) | fetched on first use |
| `nt` | the Greek New Testament (Nestle 1904); one book bundled offline, the rest fetched | mostly fetched |

```python
corpus = aegean.load("lineara")
len(corpus)        # 1721
```

`registered_scripts()` lists the writing systems the package understands (each can
have its own corpus loader):

```python
aegean.registered_scripts()
# ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

### How do I find which Greek works/books I can load?

For real Greek literature beyond the bundled sample there are two on-demand loaders,
each with a discovery helper so you never have to guess an id. See
[Greek Works and Books](Greek-Works-and-Books) for the full guide.

**Classical / literary works** come from Perseus (canonical-greekLit) and
First1KGreek via `greek.load_work(...)`. To browse a curated, verified starter list:

```python
from aegean import greek
ws = greek.popular_works()
len(ws)                  # 25
ws[0]
# {'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'}
```

That's a curated short list. For the **whole** reachable canon, `greek.catalog()` is an
offline, instant index of every work with a Greek edition in the open Perseus +
First1KGreek repos: ~1,800 of them: searchable by author, title (English or Greek), or
free text:

```python
len(greek.catalog())                 # 1778
hits = greek.catalog(author="plato")
len(hits)                            # 39
hits[0]
# {'id': 'tlg0059.tlg001', 'author': 'Plato', 'title': 'Euthyphro',
#  'greek_title': 'Εὐθύφρων', 'source': 'perseus'}
```

Each entry's `id` goes straight to `load_work`. The catalogue is honest about coverage:
it lists exactly what the open repos hold at the pinned commit, so some authors that
aren't online upstream (Sappho, for instance) genuinely aren't in it; that's correct, not
a gap in pyaegean.

Same lists from the CLI (`pip install "pyaegean[cli]"`):

```bash
aegean greek works                   # the 25 curated highlights
aegean greek catalog --author plato  # search the full ~1,800-work catalogue
aegean greek catalog sappho          # a no-match is reported plainly
```

The curated 25, as a table:

```bash
aegean greek works
#                         Popular Greek works
# ┌────────────────┬──────────────┬──────────────────────────────────┐
# │ id             │ author       │ title                            │
# ├────────────────┼──────────────┼──────────────────────────────────┤
# │ tlg0012.tlg001 │ Homer        │ Iliad                            │
# │ tlg0012.tlg002 │ Homer        │ Odyssey                          │
# │ tlg0020.tlg001 │ Hesiod       │ Theogony                         │
# │ …              │ …            │ …                                │
# │ tlg0086.tlg010 │ Aristotle    │ Nicomachean Ethics               │
# └────────────────┴──────────────┴──────────────────────────────────┘
# Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
# This is a curated subset — search the full ~1,800-work canon with `aegean greek catalog`
```

A sample of the 25 curated works (the list is a starting point, **not** the whole
canon: `load_work` takes *any* Perseus canonical-greekLit / First1KGreek CTS id;
browse them all at [scaife.perseus.org](https://scaife.perseus.org)):

| id | author | title |
|---|---|---|
| `tlg0012.tlg001` | Homer | Iliad |
| `tlg0012.tlg002` | Homer | Odyssey |
| `tlg0020.tlg002` | Hesiod | Works and Days |
| `tlg0085.tlg005` | Aeschylus | Agamemnon |
| `tlg0011.tlg004` | Sophocles | Oedipus Tyrannus |
| `tlg0006.tlg003` | Euripides | Medea |
| `tlg0016.tlg001` | Herodotus | Histories |
| `tlg0003.tlg001` | Thucydides | History of the Peloponnesian War |
| `tlg0032.tlg006` | Xenophon | Anabasis |
| `tlg0059.tlg030` | Plato | Republic |
| `tlg0086.tlg010` | Aristotle | Nicomachean Ethics |

**Then load one** (network on first fetch only; pinned to a commit, so it's
reproducible). `ref` selects a sub-section: a book number, a `book.chapter`, or a
verse line-range:

```python
# minimal, network on first use — shape shown, not run here:
iliad = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")   # Iliad, book 1, lines 1–10
len(iliad)                  # one Document per addressed textpart
iliad.provenance.license    # 'CC BY-SA 4.0 (Perseus Digital Library)'
```

CLI equivalent:

```bash
aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

| `work` flag | Meaning |
|---|---|
| `--ref` | section to load: `1` (book), `1.2` (chapter), `1.1-1.50` (lines) |
| `--source` | `auto` (default), `perseus`, or `first1k` |
| `--edition` | pick a specific edition file when a work has several |
| `--output` / `-o` | write the corpus to a JSON file |
| `--json` | machine-readable JSON on stdout |

**The Greek New Testament** has its own loader, `greek.load_nt(book, ref=...)`,
which returns a Koine corpus with per-token gold lemma, morph parse, Strong's
number, and UD POS. To list the 27 books and every name each accepts:

```python
books = greek.nt_books()
len(books)               # 27
books[3]
# {'name': 'John', 'aliases': ['john', 'jn', 'jhn']}
```

```bash
aegean greek nt-books
#      New Testament books (Nestle 1904)
# ┌────────┬─────────────────────────────────┐
# │ book   │ accepted names                  │
# ├────────┼─────────────────────────────────┤
# │ Matt   │ matthew, matt, mt               │
# │ John   │ john, jn, jhn                   │
# │ Rev    │ revelation, rev, rv, apocalypse │
# │ …      │ …                               │
# └────────┴─────────────────────────────────┘
# Load one in Python:  greek.load_nt('John', ref='1.1-18')
```

Any name or alias works as the `book` argument; `ref` mirrors `load_work`
(`"3"` = chapter 3, `"3.16"` = a verse, `"3.16-18"` = a verse range, `"3-5"` = a
chapter range). All 27 books and their aliases:

| Book | Accepted names |
|---|---|
| Matt | matthew, matt, mt |
| Mark | mark, mk, mrk |
| Luke | luke, lk, luk |
| John | john, jn, jhn |
| Acts | acts, act |
| Rom | romans, rom, rm |
| 1Cor | 1corinthians, 1cor, 1co |
| 2Cor | 2corinthians, 2cor, 2co |
| Gal | galatians, gal, ga |
| Eph | ephesians, eph |
| Phil | philippians, phil, php |
| Col | colossians, col |
| 1Thess | 1thessalonians, 1thess, 1th |
| 2Thess | 2thessalonians, 2thess, 2th |
| 1Tim | 1timothy, 1tim, 1ti |
| 2Tim | 2timothy, 2tim, 2ti |
| Titus | titus, tit |
| Phlm | philemon, phlm, phm |
| Heb | hebrews, heb |
| Jas | james, jas, jms |
| 1Pet | 1peter, 1pet, 1pe |
| 2Pet | 2peter, 2pet, 2pe |
| 1John | 1john, 1jn, 1jhn |
| 2John | 2john, 2jn, 2jhn |
| 3John | 3john, 3jn, 3jhn |
| Jude | jude, jud |
| Rev | revelation, rev, rv, apocalypse |

For a quick Koine gloss (no download: the bundled Dodson lexicon is CC0):

```python
greek.use_dodson()
greek.gloss_nt("λόγος")     # 'a word, speech, divine utterance, analogy'
```

```bash
aegean greek gloss-nt "λόγος"
# a word, speech, divine utterance, analogy
```

### Can I load my own text file?

Yes. `aegean.io` turns a string, a `.txt`, a folder of `.txt` files, or a `.csv` into a
real `Corpus`: with the full filter / search / analyse / export API: so you don't have
to write any `Corpus` boilerplate. It's all offline stdlib:

```python
from aegean import io

io.from_text("λόγος δὲ καὶ ἀριθμός", doc_id="note")  # from a string
io.from_text_file("essay.txt")                        # from one file
io.from_text_dir("poems/")                            # one corpus from a folder
io.from_csv("rows.csv", text_col="line", id_col="id") # one document per row
```

Greek (and `nt`) text is run through the Greek word tokenizer (punctuation stripped);
other scripts split on whitespace: pass `script_id="lineara"` etc. for those. `split`
controls how a file becomes documents: `"whole"` (default, one doc), `"paragraph"`
(blank-line blocks), or `"line"`.

From the shell, `aegean import` writes the result to a `.json` or `.db` that then works
anywhere a corpus is accepted:

```bash
aegean import myplato.txt -o myplato.json    # wrote 1 document(s) to myplato.json
aegean stats myplato.json --top 5            # …now analyse it like any corpus
```

Note that `aegean.load(...)` and the CLI's corpus argument still take only a `.json`/`.db`
corpus: a raw `.txt`/`.csv` has to be **imported first**, as above. (The error you'd get
from skipping that step says so, and prints the exact `aegean import` line to run.)

---

## The web demo

### How do I try pyaegean without installing anything?

The pure-Python core (the Greek pipeline plus the bundled Linear A corpus) runs
**in your browser**: nothing to install, no server:
[the web demo](https://ryanpavlicek.github.io/pyaegean/demo/). It's
[Pyodide](https://pyodide.org/) (CPython compiled to WebAssembly) running locally
in the page.

### Why does the web demo need a moment to start?

When the page opens it shows **"loading…"** for a few seconds. That's expected: on
first load the browser has to:

1. download and start the Pyodide WebAssembly runtime,
2. load `micropip` and the `sqlite3` stdlib module, then
3. `micropip.install("pyaegean")`: fetch the package wheel and unpack it.

When that finishes the status flips to **"ready"** and the tools respond instantly.
It's slower the very first time because everything is being fetched over the
network; subsequent runs are quicker as the browser caches the pieces. If it gets
stuck on "failed to load," it's usually a flaky network or a strict
content-blocker: reload, or just `pip install pyaegean` locally instead.

### What can't the web demo do?

Only the offline core runs client-side: Beta Code, syllabification, accents,
scansion, and the bundled Linear A corpus. The **neural** and **AI** layers don't
run in the browser: those need a local install (and, for AI, a provider key). For
anything heavy, install locally per [Getting Started](Getting-Started).

---

## Greek text

### Greek shows up as boxes, `?`, or mojibake

That's a display/font issue, not a data problem: the text is correct underneath.

- **Best fix:** use [Jupyter](Getting-Started#option-c--jupyter-recommended-for-research)
  or a modern editor (VS Code), which render polytonic Greek cleanly.
- **In a Windows terminal:** run `chcp 65001` to switch it to UTF-8 first, and use
  a font with Greek coverage.
- If you write Greek to a file, open it as **UTF-8**.

### I don't have a Greek keyboard

You don't need one. Type **Beta Code**: the standard ASCII transliteration used by
the TLG and Perseus — and convert:

```python
from aegean import greek
greek.betacode_to_unicode("mh=nin")     # 'μῆνιν'
```

```bash
aegean greek betacode "mh=nin"
# μῆνιν
```

See [Greek NLP → Beta Code](Greek-NLP#normalization--beta-code) for the full key.

### My accents/breathings compare as unequal even though they look identical

Unicode has more than one way to encode the same accented letter. Normalise first:

```python
greek.normalize("ό")     # canonical NFC form
```

### Can it really scan verse and break words into syllables?

Yes: entirely offline, no extras needed:

```python
greek.syllabify("ἄνθρωπος")                   # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

The scanner covers dactylic hexameter, elegiac pentameter, and iambic trimeter:
see [Metrical scansion](Greek-NLP#metrical-scansion).

---

## Data, offline use & the AI layer

### Do I need an internet connection?

No. The core library, the full Linear A corpus, and the Greek pipeline all work
**offline**. A few **opt-in** things touch the network *on first use*, then cache:
the fetched corpora: `aegean.load("damos")` (the full ~5,900-tablet Linear B corpus,
~2 MB) and `aegean.load("sigla")` (the SigLA Linear A dataset, ~1 MB):
`greek.load_work(...)` / `greek.load_nt(...)` (real Greek texts, pinned to a commit),
`data.fetch(...)` for large extra assets (the facsimile images), the optional AI layer,
and the opt-in Greek backends. The treebank/LSJ/tagger/lemmatizer/parser backends now
fetch small **prebuilt** artifacts: `greek.use_lsj()` a ~15 MB index (not 270 MB of
Perseus TEI), and `greek.use_treebank()` / `use_tagger()` / `use_lemmatizer()` /
`use_parser()` one shared ~15 MB AGDT-derived bundle (no 75 MB download or local
training): falling back to building from source if an asset is unreachable. The
`[neural]` models are larger: `greek.use_neural_lemmatizer()` (~232 MB) and
`greek.use_neural_pipeline()` (~173 MB; quantized and lossless, needs
`onnxruntime>=1.23`). Everything else, including the rule-based pipeline, works
fully offline.

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

From the CLI you can see the location and what's in it, list what's fetchable, and
record exact versions for reproducibility:

```bash
aegean data cache       # cache location + per-entry sizes
aegean data list        # the fetchable datasets (name, size note, license)
aegean data versions    # the reproducibility manifest: each dataset's version + sha256
```

Upgrading the package never wipes this cache, so you don't re-download after a
`pip install --upgrade`. To reclaim space, clear the analysis cache with
`aegean cache --clear` (that's the computed-results cache, separate from the
fetched datasets).

---

## Trust & scholarship

### Is the Linear A "translation" real? Can I trust the analysis?

**No — and the library is built to keep you honest about this.** Linear A is
**undeciphered**. The phonetic values come from Linear B as a working convention,
and every analytical or AI method is labeled **exploratory**: evidence to weigh,
never a translation. Treat results as leads for a human expert, not answers. See
[Limitations](Limitations).

### How accurate is the AI translation/glossing?

It's a hypothesis from a language model, returned as an `ExploratoryResult` with
provenance and an unmistakable exploratory label. Useful for ideas; never citable
as fact. Always verify against primary scholarship. See [AI Layer](AI-Layer) and
[Limitations](Limitations).

### How accurate is the Greek morphology / POS tagging?

The default rule/seed engines are an offline **baseline**: high-precision on closed
classes (article, prepositions, pronouns…) and regular paradigms, but they miss
irregular, third-declension, contract, and most open-class forms — and they tell you
when a result is reconstructed (`lemma_certain=False`).

Several opt-in backends raise accuracy well past that baseline. The strongest is the
**neural pipeline**: `greek.use_neural_pipeline()` (the `[neural]` extra): one joint
model for POS, morphology, UD dependency parsing, and lemmatization, state of the art
on the UD Ancient Greek benchmarks (97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS /
85.6 LAS on the Perseus test fold, measured end-to-end from raw text: see
[the neural pipeline](Greek-NLP#the-neural-pipeline-opt-in)). The lighter tiers:
`greek.use_treebank()` supplies attested, correctly-accented lemmas, full morphology,
and gold POS for forms attested in the AGDT; `greek.use_tagger()` generalizes POS at
~84% on unseen forms; `greek.use_neural_lemmatizer()` (a GreTa seq2seq) reaches 76.3%
on unseen forms, while the zero-dependency `greek.use_lemmatizer()` (edit-trees +
perceptron) reaches ~40%; `greek.use_parser()` is a pure-Python dependency parser
(~0.67 UAS / 0.57 LAS on projective AGDT). Quantify any combination on your own gold
set with `greek.benchmark.compare_modes()`. For meaning, opt into `greek.use_lsj()` (LSJ
glossing). See [Treebank-backed mode](Greek-NLP#treebank-backed-mode-opt-in)
and [Morphological analysis](Greek-NLP#morphological-analysis).

### How do I cite pyaegean and its data in a paper?

Every corpus carries its citation, and the repo ships a `CITATION.cff`:

```python
corpus = aegean.load("lineara")
corpus.cite()           # one line; also corpus.cite("bibtex") / corpus.cite("apa")
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```

The citation follows the **exact subset you used**: a filtered corpus records what
was filtered, and query results record the query:

```python
from aegean.analysis import FilterRow

corpus.filter(site="Haghia Triada").cite()
# … — https://github.com/mwenge/lineara.xyz [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
results = corpus.query([FilterRow("word-prefix", "KU")], output="words")
results.cite()          # … [query: Word starts with: KU → N words]
```

Fetched Greek works carry their own provenance and license, too: `load_work`
pins the source commit and records the upstream CC BY-SA attribution:

```python
iliad = greek.load_work("tlg0012.tlg001", ref="1")   # network on first use
iliad.provenance.license       # 'CC BY-SA 4.0 (Perseus Digital Library)'
iliad.provenance.data_version  # the pinned commit, for reproducibility
```

See [Data & Provenance](Data-and-Provenance) for full licensing and attribution.

---

## Getting help

- **Bugs / feature requests:** [GitHub Issues](https://github.com/ryanpavlicek/pyaegean/issues)
 : please include your pyaegean version (`python -c "import aegean; print(aegean.__version__)"`).
- **How a function behaves:** the per-domain reference pages: [Linear A](Linear-A),
  [Analysis](Analysis), [Greek NLP](Greek-NLP), [AI Layer](AI-Layer),
  [Greek Works and Books](Greek-Works-and-Books), [CLI](CLI).
- **What the tools can and can't do:** [Limitations](Limitations).
- **Contributing a fix or a script plugin:** [Development](Development).
