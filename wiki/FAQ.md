# FAQ & Troubleshooting

Common questions and troubleshooting steps for installation, corpora, Greek
text, the web demo, offline caching, the AI layer, accuracy, and citation. If
your issue is not covered here,
[open an issue](https://github.com/ryanpavlicek/pyaegean/issues). New to Python
or pyaegean? Start with [Getting Started](Getting-Started).

---

## Installing & running

### Something isn't working — where do I start?

Run **`aegean doctor`** (requires `[cli]`). It checks your environment offline
and prints each detected problem with its fix: missing extras show their
`pip install "pyaegean[…]"` command, leftover partial downloads show the
`aegean data remove NAME` command to clean them up, and an unwritable
`PYAEGEAN_CACHE` directory fails immediately with an explicit message. Exit code
`0` means all checks passed; exit code `1` means at least one issue was found.
Pass `--json` for machine-readable output:

```bash
aegean doctor
# …five tables: versions, optional extras, data store, model bundles, analysis cache…
# doctor: all checks passed
```

Missing extras and un-downloaded datasets are reported as informational, not
failures; the zero-dependency core is a supported configuration.

### `ModuleNotFoundError: No module named 'aegean'`

Python cannot find the package. Check these three causes:

1. **Your virtual environment is not active.** Activate it in each new terminal
   session (`.venv\Scripts\Activate.ps1` on Windows,
   `source .venv/bin/activate` on macOS/Linux). See
   [Getting Started, Step 3](Getting-Started#step-3--make-a-project-folder-with-its-own-environment).
2. **pyaegean is not installed in the active environment.** Run
   `pip install pyaegean`.
3. **Different Python binaries.** Confirm `pip show pyaegean` and
   `python --version` point to the same interpreter.

### `pip` says "permission denied" or wants admin rights

Do not install system-wide or run `sudo pip`. Create and activate a
[virtual environment](Getting-Started#step-3--make-a-project-folder-with-its-own-environment)
and install into it.

### PowerShell won't run the activate script ("execution policy")

Run this once, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `ImportError` mentioning pandas

The core library has zero third-party dependencies. `pandas` is optional and
used only for DataFrame export (`corpus.to_dataframe()`): install it with
`pip install "pyaegean[data]"`.

### How do I update to a newer version with pip?

```bash
pip install --upgrade pyaegean
```

Additional options:

- **Upgrade extras too:** include the bracketed extras so optional dependencies
  update alongside the package, e.g. `pip install --upgrade "pyaegean[cli]"` or
  `pip install --upgrade "pyaegean[all]"`.
- **Check available and installed versions:**

  ```bash
  pip index versions pyaegean      # versions available on PyPI
  pip show pyaegean                # currently installed version
  python -c "import aegean; print(aegean.__version__)"
  ```

- **Pin a release** for reproducibility: `pip install pyaegean==0.73.1`.
- **Cached datasets persist across upgrades.** Downloaded assets live in your
  cache directory (see
  [Where are downloaded/fetched files stored?](#where-are-downloadedfetched-files-stored))
  and are reused as long as their SHA-256 hashes match the current pins. When a
  release updates a pin, the next access downloads the new version.

### How do I install optional features ("extras")?

Optional features are grouped into bracketed extras: `pip install "pyaegean[cli]"`,
`pip install "pyaegean[tui]"`, `pip install "pyaegean[neural,viz]"`, or
`pip install "pyaegean[all]"`. `[all]` installs `neural`, `cli`, `tui`, `mcp`,
`ai`, `data`, `epidoc`, `geo`, and `viz`; it excludes `parquet`,
`viz-interactive`, `interop` (spaCy/Stanza/CLTK), and contributor extras
(`dev`, `docs`).

See [Installation](Installation) for the complete extras matrix. `aegean doctor`
lists which runtime extras are importable and gives the install command for any
missing extra.

### Which Python versions are supported?

**Python 3.10 or newer** for the core library and pure-Python extras
(`python --version`). The `[neural]` and `[all]` extras require
**Python 3.10–3.14** (where PyPI `onnxruntime` wheels are published).

---

## Finding what you can load

### How do I see which corpora are available?

`aegean.load("…")` (or unified `aegean.open("…")`) loads bundled and hosted
corpora by ID:

- **Bundled offline:** `lineara` (1,721 documents), `linearb` (sample), `greek`
  (5 passages), `cypriot` (180 documents: 178 IG XV 1 inscriptions + 2 samples),
  `cyprominoan` (sample), plus bundled NT (`John 1`, `Phlm 1`) and Swete LXX
  (`Gen 1:1–5`, `Ps 22:1–6`) samples.
- **On-demand hosted corpora (SHA-256-pinned):** Aegean (`damos`, `sigla`),
  **8 categorized Ancient, Classical, Patristic, and Byzantine Greek
  collections** (`chrysostom`, `church-fathers-early`, `church-fathers-late`,
  `classical-greek`, `hellenistic-greek`, `imperial-greek`,
  `late-antique-greek`, `byzantine-lit`: 3,844 works across 1,414 authors,
  64.35M tokens), seven Greek epigraphic corpora and documentary papyri
  (`isicily`, `iip`, `iospe`, `igcyr`, `aphrodisias`, `crete`, `edh`, `ddbdp`),
  Biblical & Patristic (`nt`, `lxx`, `apostolic-fathers`, `pseudepigrapha`,
  `patrologia`, plus `aegean.greek.bible` for 9 NT editions, 13 manuscripts, 56
  LXX books including Ecclesiastes, and 112 commentaries), and literary/scholia
  (`byzantine`, `homer-scholia`).

Inspect local status and install named packs with `aegean library` (the primary
resource manager) or inspect the 47 raw remote pins with `aegean data`:

```bash
aegean library status     # installed vs available assets and disk usage
aegean library list       # status of bundled corpora and hosted resources
aegean library packs      # 10 packs: biblical, church-fathers, patristic, ancient-greek, byzantine-pack, …
```

```python
import aegean
corpus = aegean.load("lineara")
len(corpus)        # 1721
aegean.registered_scripts()
# ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

See [Data & Provenance](Data-and-Provenance) for all 47 hosted datasets with
sizes and licenses.

### How do I find which Greek works and books I can load?

Two on-demand loaders cover full Greek literature and Biblical texts, each with
offline discovery helpers. See [Greek Works & Books](Greek-Works-and-Books) for
complete details.

**Classical and literary works** load from Perseus (*canonical-greekLit*) and
*First1KGreek* via `greek.load_work(...)`. Browse the 25-work curated starter
list:

```python
from aegean import greek
ws = greek.popular_works()
len(ws)                  # 25
ws[0]
# {'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'}
```

For the full discoverable canon, `greek.catalog()` searches the bundled offline
index of all 1,778 Greek editions in Perseus and First1KGreek by author, title
(English or Greek), or free text:

```python
len(greek.catalog())                 # 1778
hits = greek.catalog(author="plato")
len(hits)                            # 39
hits[0]
# {'id': 'tlg0059.tlg001', 'author': 'Plato', 'title': 'Euthyphro',
#  'greek_title': 'Εὐθύφρων', 'source': 'perseus'}
```

Pass any returned `id` directly to `greek.load_work`. Coverage reflects the
pinned upstream repositories, so authors absent upstream (such as Sappho) do
not appear in `greek.catalog()`.

From the CLI (`[cli]` extra):

```bash
aegean greek works                   # 25 curated works
aegean greek catalog --author plato  # search all 1,778 works
aegean greek catalog sappho          # reports no matches
```

Sample of the 25 curated works (`load_work` accepts any Perseus
canonical-greekLit or First1KGreek CTS ID; browse the full set at
[scaife.perseus.org](https://scaife.perseus.org)):

| id | author | title |
| --- | --- | --- |
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

Load a work or passage (downloads on first fetch from a pinned commit, then
reuses the cache). `ref` selects a book, `book.chapter`, or verse line range:

```python
iliad = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")   # Iliad, book 1, lines 1–10
len(iliad)                  # 1
iliad.provenance.license    # 'CC BY-SA 4.0 (Perseus Digital Library)'
```

CLI equivalent:

```bash
aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

| `work` flag | Meaning |
| --- | --- |
| `--ref` | section to load: `1` (book), `1.2` (chapter), `1.1-1.50` (lines) |
| `--source` | `auto` (default), `perseus`, or `first1k` |
| `--edition` | specific edition file when multiple exist |
| `--output` / `-o` | write the corpus to `.json` or `.db` (SQLite) |
| `--json` | emit JSON to stdout |

**The Greek New Testament and Septuagint** live under `aegean.greek.bible`.
`bible.load_nt(book, ref=..., edition="nestle1904")` supports 9 NT editions
(defaulting to Nestle 1904 with per-token gold lemma, morphology, Strong's
number, and UD POS). List the 27 NT books and their aliases:

```python
from aegean.greek import bible

books = bible.nt_books()
len(books)               # 27
books[3]
# {'name': 'John', 'aliases': ['john', 'jn', 'jhn']}

john = bible.load_nt("John", ref="1.1-5")
```

```bash
aegean bible books nt
#      New Testament books (Nestle 1904)
# ┌────────┬─────────────────────────────────┐
# │ book   │ accepted names                  │
# ├────────┼─────────────────────────────────┤
# │ Matt   │ matthew, matt, mt               │
# │ John   │ john, jn, jhn                   │
# │ Rev    │ revelation, rev, rv, apocalypse │
# │ …      │ …                               │
# └────────┴─────────────────────────────────┘
# Read one:  aegean bible read John 1.1-18
```

Pass any canonical name or alias as `book`; `ref` accepts `"3"` (chapter),
`"3.16"` (verse), `"3.16-18"` (verse range), or `"3-5"` (chapter range). All 27
books and aliases:

| Book | Accepted names |
| --- | --- |
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

For Koine glosses and Strong's entries (Dodson is bundled offline under CC0;
Extended Strong's fetches on demand with offline Dodson fallback):

```python
from aegean import greek
from aegean.greek import bible

greek.use_lexicon("dodson")
greek.gloss("λόγος")             # 'λόγος: a word, speech, divine utterance, analogy'

entry = bible.strongs_entry("λόγος")
entry.strongs, entry.gloss       # ('G3056', 'word')
```

```bash
aegean greek gloss "λόγος" -d dodson
# λόγος: a word, speech, divine utterance, analogy

aegean bible strongs "λόγος"
# G3056  λόγος  logos  G:N-M
#   Gloss: word
#   Definition: ...
```

### Can I load my own text file?

Yes. `aegean.io` converts a string, a `.txt` file, a folder of `.txt` files, or
a `.csv` into a `Corpus` offline using the standard library:

```python
from aegean import io

io.from_text("λόγος δὲ καὶ ἀριθμός", doc_id="note")  # from a string
io.from_text_file("essay.txt")                        # from one file
io.from_text_dir("poems/")                            # one corpus from a folder
io.from_csv("rows.csv", text_col="line", id_col="id") # one document per non-blank row
```

Greek (and `nt`) imports preserve decoded source text, punctuation, numerals,
foreign text, and aligned character spans by default (`token_view="all"`). Use
`doc.words` for lexical tokens, or pass `token_view="words"` / CLI
`--token-view words` for word-only import. For Aegean scripts, pass
`script_id="lineara"` (etc.). The `split` parameter controls document splitting:
`"whole"` (default), `"paragraph"`, or `"line"`.

From the shell, `aegean import` writes a `.json` or `.db` corpus usable with
any CLI command:

```bash
aegean import myplato.txt -o myplato.json    # wrote 1 document(s) to myplato.json
aegean stats myplato.json --top 5
```

`aegean.load(...)` and CLI corpus arguments require a `.json` or `.db` corpus;
import raw `.txt` or `.csv` files first.

---

## The web demo & local workbench

### How do I try pyaegean without installing anything?

The pure-Python core (Greek text utilities, scansion, baseline NLP, and the
bundled Linear A corpus) runs client-side in your browser via
[Pyodide](https://pyodide.org/) (WebAssembly) at
[the web demo](https://pyaegean.xyz/demo/).

### Why does the web demo pause on first load?

On first visit, the browser downloads and initializes the Pyodide WebAssembly
runtime, loads `micropip` and `sqlite3`, and installs the `pyaegean` wheel.
Once initialized, the status changes from **"loading…"** to **"ready"** and
subsequent loads use the browser cache. If loading fails under a strict content
blocker or unstable connection, reload or install locally with
`pip install pyaegean`.

### What can't the web demo do?

The browser demo runs only the offline core. The `[neural]` pipeline, AI
providers, and large hosted datasets require a local install. For local
multi-script visual exploration of Aegean corpora (Linear A, Linear B, Cypriot,
and Cypro-Minoan), run `aegean workbench --corpus <id-or-path>`, which serves
`workbench-app-v2.1.0` locally (`aegean.io.to_workbench_bundle` exports any
Aegean corpus to the multi-script bundle format).

---

## Greek text

### Greek shows up as boxes, `?`, or mojibake

This is a terminal font or encoding issue; the underlying Unicode text is
intact.

- Use [Jupyter](Getting-Started#option-c--jupyter-recommended-for-research),
  VS Code, or Windows Terminal.
- On Windows, set `PYTHONUTF8=1` (or run `chcp 65001` for a single session) and
  use a font with polytonic Greek coverage. See
  [Installation → Windows UTF-8](Installation#windows-seeing-greek-correctly-utf-8).
- Always open files with `encoding="utf-8"` when writing Greek text from Python.

### I don't have a Greek keyboard

Type ASCII **Beta Code** (TLG/Perseus convention) and convert it:

```python
from aegean import greek
greek.betacode_to_unicode("mh=nin")     # 'μῆνιν'
```

```bash
aegean greek betacode "mh=nin"
# μῆνιν
```

See [Greek NLP → Beta Code](Greek-NLP#normalization--beta-code) for the full
character table.

### My accents/breathings compare as unequal even though they look identical

Unicode allows multiple code-point sequences for the same accented character.
Normalize to NFC before comparing:

```python
greek.normalize("ό")     # canonical NFC form
```

### Can it scan verse and break words into syllables?

Yes, offline with zero extras:

```python
greek.syllabify("ἄνθρωπος")                   # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

Supported metres: dactylic hexameter, elegiac pentameter, iambic trimeter, and
the seven fixed-template Aeolic lines in `greek.AEOLIC_LINES`. See
[Metrical scansion](Greek-NLP#metrical-scansion).

---

## Data, offline use & the AI layer

### Do I need an internet connection?

No. The core library, bundled Linear A and Cypriot corpora, Dodson lexicon, and
baseline Greek pipeline run offline. Opt-in resources download once to your
local cache and work offline thereafter:

- Hosted corpora: `damos` (~3 MB), `sigla` (~1.3 MB), the seven Greek
  epigraphic corpora (`isicily`, `iip`, `iospe`, `igcyr`, `aphrodisias`,
  `crete`, `edh`), `ddbdp` documentary papyri (~219 MB SQLite), Biblical &
  Patristic corpora (`nt`, `patrologia`, `apostolic-fathers`, `pseudepigrapha`,
  plus `bible.load_nt` / `bible.load_lxx` bundles), `byzantine`, and
  `homer-scholia`.
- Literary works fetched via `greek.load_work(...)` (pinned upstream commits).
- Prebuilt Greek backend artifacts: `greek.use_lsj()` (~15 MB index) and
  `greek.use_treebank()` / `use_tagger()` / `use_lemmatizer()` / `use_parser()`
  (one shared ~15 MB AGDT-derived bundle), each falling back to building from
  upstream source if unreachable.
- Neural models under `[neural]`: `greek.use_neural_lemmatizer()` (~232 MB) and
  `greek.use_neural_pipeline()` (~173 MB, quantized, requiring
  `onnxruntime>=1.23`).
- Optional assets: Linear A facsimile imagery (`data.fetch`) and the local
  multi-script browser workbench (`workbench-app-v2.1.0`).

Use `aegean library` (or `aegean data`) to pre-fetch packs or individual
datasets before working offline.

### Do I need an API key?

Only for hosted providers in the [AI Layer](AI-Layer) (translation, glossing,
exploratory hypotheses). Every analysis, scansion, corpus, and neural NLP
feature runs without an API key. To use a hosted provider, install its extra
and set its key (e.g. `pip install "pyaegean[anthropic]"` and
`ANTHROPIC_API_KEY`). To run an LLM locally with no API key, use the `local`
provider (Ollama, LM Studio, llama.cpp, vLLM): `pip install "pyaegean[local]"`
and set `PYAEGEAN_LOCAL_MODEL`. See
[AI Layer → Using a local model](AI-Layer#using-a-local-model-ollama-lm-studio-llamacpp-vllm).

### Where are downloaded/fetched files stored?

```python
from aegean import data
data.cache_dir()      # cache path (override with PYAEGEAN_CACHE)
```

Manage installed packs, datasets, and disk space with `aegean library` and
`aegean data`:

```bash
aegean library status       # installed packs, corpora, works, models, disk usage
aegean library install PACK # download a themed pack (or individual target)
aegean library remove NAME  # delete cached datasets, works, or packs
aegean data store           # cache path and per-entry sizes
aegean data list            # all 47 remote datasets with download state and sizes
aegean data remove NAME     # delete one raw dataset (--all clears all datasets)
aegean data versions        # reproducibility manifest (version + sha256 per dataset)
```

Upgrading pyaegean leaves this cache intact. Unchanged valid assets are reused;
a changed pin or `--force` fetches the updated file. Clear the separate
computed-results cache with `aegean cache --clear`. `aegean doctor` checks
store writability, sizes, and any leftover partial downloads.

---

## Trust & scholarship

### How should Linear A phonetic values be interpreted?

Linear A phonetic values are conventional transcriptions borrowed from
homomorphic Linear B signs. Statistical, distributional, and AI outputs on
Linear A carry an `exploratory` marker on their return objects. See
[Limitations](Limitations).

### How accurate is AI translation and glossing?

LLM outputs return inside `ExploratoryResult` with provider, model, prompt, and
grounding metadata. Verify generated translations and glosses against primary
editions and lexica before citing. See [AI Layer](AI-Layer).

### How accurate is the Greek morphology / POS tagging?

The default rule and seed engines are an offline baseline: high precision on
closed classes (articles, prepositions, pronouns) and regular paradigms, while
irregular, third-declension, contract, and most open-class forms fall back to
`NOUN` or reconstructed lemmas (`lemma_certain=False`).

Opt-in backends raise accuracy above that baseline:

- **Neural pipeline (`greek.use_neural_pipeline()`, `[neural]` extra):** one
  joint model for POS, morphology, UD dependency parsing, and lemmatization,
  measured at 97.0 UPOS / 96.0 UFeats / 94.3 lemma / 90.2 UAS / 85.7 LAS on the
  UD Perseus test fold with gold tokenization (see
  [Benchmarks](Benchmarks) and [Greek NLP](Greek-NLP#the-neural-pipeline-opt-in)).
- **Opt-in neural refinements (bundled with the neural pipeline, zero extra
  download):** `greek.use_oov_lemma_reranker(config="weighted")` recovers unseen
  poetic and documentary lemmas (+0.69 to +3.43 pp across the five locked test
  folds), and `greek.use_calibration_registry()` provides calibrated
  probabilities across literary prose and documentary papyri.
- **Lighter tiers:** `greek.use_treebank()` returns attested, accented lemmas,
  morphology, and gold POS for forms present in AGDT; `greek.use_tagger()`
  reaches ~84% POS accuracy on unseen forms; `greek.use_neural_lemmatizer()`
  (GreTa seq2seq) reaches 76.3% on unseen forms; pure-Python
  `greek.use_lemmatizer()` reaches ~40%; pure-Python `greek.use_parser()`
  reaches ~0.63 UAS / 0.53 LAS on projective AGDT.

Measure any configuration against your own gold set with
`greek.benchmark.compare_modes()`, and review or adjudicate machine annotations
interactively with `aegean tui --review` (`r` in `aegean tui`). For dictionary
definitions, enable `greek.use_lsj()` or another registry lexicon. See
[Greek NLP](Greek-NLP).

### How do I cite pyaegean and its data in a paper?

Every corpus carries its source citation, and the repository includes
`CITATION.cff`:

```python
corpus = aegean.load("lineara")
corpus.cite()           # one line; also corpus.cite("bibtex") / corpus.cite("apa")
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz
```

Citations track filters and queries automatically:

```python
from aegean.analysis import FilterRow

corpus.filter(site="Haghia Triada").cite()
# … — https://github.com/mwenge/lineara.xyz [subset: filter(site='Haghia Triada') → 1110 of 1721 documents]
results = corpus.query([FilterRow("word-prefix", "KU")], output="words")
results.cite()          # … [query: Word starts with: KU → N words]
```

Fetched Greek works record their upstream license and pinned commit:

```python
iliad = greek.load_work("tlg0012.tlg001", ref="1")   # network on first use
iliad.provenance.license       # 'CC BY-SA 4.0 (Perseus Digital Library)'
iliad.provenance.data_version  # pinned commit hash
```

To package a corpus (or retrieval pointer for non-commercial datasets),
`CITATIONS.bib` / `CITATIONS.txt`, review tables, workbench backups, and
evaluation receipts into one SHA-256-verified `.zip` archive for publication or
archival sharing, use `aegean bundle create` (`aegean.bundle`). See
[Data & Provenance](Data-and-Provenance) and
[Citing Computational Assistance](Citing-Computational-Assistance).

---

## Getting help

- **Bugs and feature requests:** [GitHub Issues](https://github.com/ryanpavlicek/pyaegean/issues):
  include your pyaegean version (`python -c "import aegean; print(aegean.__version__)"`).
- **Module references:** [Linear A](Linear-A), [Analysis](Analysis),
  [Greek NLP](Greek-NLP), [Biblical & Koine Greek](New-Testament),
  [AI Layer](AI-Layer), [Greek Works & Books](Greek-Works-and-Books),
  [CLI](CLI), [TUI](TUI).
- **Scope and limits:** [Limitations](Limitations).
- **Contributing:** [Development](Development).
