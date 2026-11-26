# New Testament

`aegean.greek.bible` (CLI: `aegean bible`, TUI shortcut: `b`) provides pyaegean's
tooling for Biblical and Koine Greek: nine New Testament editions with word-level
variant comparison, thirteen 2nd–5th century CE manuscript witnesses, an Extended
Strong's lexicon with root trees, the 56-book Septuagint (including Ecclesiastes)
with LXX/Masoretic Psalm conversion and automatic offline interlinear, and 112
indexed Greek patristic commentaries (including 26 John Chrysostom series).

The default New Testament edition, **Nestle 1904**, ships as a pre-annotated
`Corpus` in which every token carries gold annotations from the edition: a
dictionary `lemma`, a Robinson-style `morph` tag, a `strongs` number, a reconciled
Universal Dependencies `upos`, a `normalized` form, and a brief English `gloss`.
Those annotations come from the edition itself rather than from pyaegean's taggers.

Running `greek.pipeline()` on the text (with or without the neural backend)
produces fresh predictions without reading the edition's annotations.
`greek.annotate_corpus()` returns a new corpus, replaces existing lemma and POS
values, and clears prior lemma evidence and neural coverage or warnings before
writing fresh predictions. Other keys, such as source morphology and prior review
records, remain intact; keep the source-annotated corpus separate if you plan to
compare predictions against gold.

For the full CLI reference, see [CLI: Biblical & Koine Greek](CLI-Bible). For
classical literary works (`greek.load_work` and CTS IDs), see
[Greek Works and Books](Greek-Works-and-Books); for general Greek NLP (scansion,
tagging, parsing), see [Greek NLP](Greek-NLP).

---

## Quick start

```python
from aegean.greek import bible

corpus = bible.load_nt("John", ref="1.1-1.3")   # John 1:1-3, offline (bundled Nestle 1904)
doc = corpus.documents[0]
doc.id                                # 'John 1'
doc.meta.name                         # 'John 1'

t = doc.tokens[0]
t.text                                # 'Ἐν'
t.annotations
# {'lemma': 'ἐν', 'morph': 'PREP', 'strongs': '1722', 'normalized': 'Ἐν',
#  'upos': 'ADP', 'ref': 'John.1.1', 'gloss': 'in, on, among'}
```

From the command line:

```bash
aegean bible read John 1
aegean bible status         # check which Biblical bundles are cached locally
aegean bible install        # download all 5 Biblical bundles (~25 MB) at once
```

In Python, `aegean.library.install("biblical")` installs the same five bundles
(`nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, `lxx-corpus`). In
the TUI (`aegean tui`, press `b`), any missing bundle displays an inline download
bar (`f` downloads and reloads in place).

---

## Loading the New Testament: `bible.load_nt()`

`bible.load_nt(book=None, ref=None, *, edition="nestle1904", offline=False, force=False)`
returns a `Corpus` with **one `Document` per chapter**. Token annotations live in
`Token.annotations`, so `to_dataframe(level="token")` exposes them directly as
columns.

| Argument | Meaning |
|----------|---------|
| `book` | Book name or abbreviation (`"John"`, `"Jn"`, `"1Cor"`, `"Rev"`). Omit or pass `None` for all 27 books. |
| `ref` | Chapter, verse, or range within the book (e.g. `"1"`, `"1.1-18"`, `"8.28"`). Requires `book`. |
| `edition` | `"nestle1904"` (default; gold lemma, morph, Strong's), `"sblgnt"`, `"srgnt"`, `"bhp"`, `"tisch"`, `"wh"`, `"byz"`, `"antoniades"`, or `"tr"`. |
| `offline` | Read only from local cache and bundled offline samples without network access. |
| `force` | Re-fetch the corpus asset even if already cached. |

```python
from aegean.greek import bible

bible.load_nt("John")                          # Gospel of John (Nestle 1904)
bible.load_nt("John", ref="1.1-18")            # John 1:1-18
bible.load_nt("John", ref="1.18", edition="sblgnt")
bible.load_nt("John", ref="1.18", edition="tisch")
bible.load_nt("Rom", ref="8.28")               # Romans 8:28
bible.load_nt()                                # all 27 books
```

Token text, lemmas, and normalized forms are NFC-normalized at load time so gold
strings compare directly with the rest of `aegean.greek`.

---

## Command-line overview (`aegean bible`)

All Biblical and Koine Greek CLI commands live under `aegean bible` (full
reference: [CLI: Biblical & Koine Greek](CLI-Bible)):

```bash
aegean bible read John 1                    # whole chapter (Nestle 1904)
aegean bible read John 1:1-5 --interlinear  # word-by-word interlinear table
aegean bible read John 1.1-18 -e sblgnt     # read SBLGNT (or srgnt, bhp, tisch, wh, byz, antoniades, tr)
aegean bible read Gen 1:1-5                 # Septuagint (LXX books auto-detect)
aegean bible read John 1 -o john1.json      # save as a Corpus (.json or .db)
aegean export john1.json -f csv --level token -o john1.csv
```

The same commands run inside the bare `aegean` / `aegean repl` shell and the TUI
`:` console, with inline completion for NT and LXX book names, edition IDs, and
manuscript sigla.

---

## Addressing a passage with `ref`

`ref` uses **chapter.verse** notation, parallel to `greek.load_work`:

| `ref` | Selects |
|-------|---------|
| `"3"` | chapter 3 |
| `"3.16"` | chapter 3, verse 16 |
| `"3.16-3.18"` | verses 3:16–3:18 |
| `"3.16-18"` | verses 3:16–3:18 (shorthand: the upper end inherits the chapter) |
| `"3-5"` | chapters 3 through 5 |

A malformed reference raises a `ValueError` listing the accepted formats.
Unavailable chapters or range endpoints also raise an error instead of returning a
truncated passage. `corpus.cite()` records the canonical book and selected
chapter/verse range, including the actual extent of an offline sample.

---

## Book names and aliases

`bible.load_nt()` and the `aegean bible` CLI accept any book by its canonical name
or common abbreviation, case-insensitively and ignoring spaces and periods:
`"Matthew"`, `"Matt"`, `"mt"`, `"1 Cor"`, `"1cor"`, and `"1Cor."` all resolve.
Document IDs always use the canonical `name` (`John 1`, `Phlm 1`).

`bible.nt_books()` returns all 27 books in canonical order (bundled metadata, no
network call):

```python
from aegean.greek import bible

books = bible.nt_books()
len(books)         # 27
books[3]           # {'name': 'John', 'aliases': ['john', 'jn', 'jhn']}
```

From the shell:

```bash
aegean bible books nt          # 27 NT books and accepted aliases
aegean bible books lxx         # 56 Septuagint books (Swete + Ecclesiastes)
aegean bible books nt --json   # JSON output
```

| Book | Accepted names |
|------|----------------|
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

Passing an unrecognized name prints a close-match suggestion. Septuagint books
such as `Gen` or `Ps` are auto-detected by `aegean bible read`, and loaded in
Python with `bible.load_lxx()`.

---

## Per-token annotation fields (Nestle 1904)

Every token loaded from the default `nestle1904` edition carries these keys in
`Token.annotations` (the other eight editions populate `ref` and `edition`):

| Field | Meaning |
|-------|---------|
| `lemma` | Dictionary headword (gold, from Nestle 1904) |
| `morph` | Robinson-style morphology tag, e.g. `N-NSM`, `V-PAI-3S` |
| `strongs` | Strong's number (e.g. `3972` = Paul) |
| `upos` | Coarse Universal Dependencies POS, reconciled from `morph` |
| `normalized` | Accent/diacritic-normalized form |
| `ref` | Canonical token address, e.g. `John.1.1` |
| `gloss` | Brief English gloss (bundled Dodson lexicon, when available) |

Converting a chapter into a tabular dataframe puts each field in its own column:

```python
import pandas as pd
from aegean.greek import bible

corpus = bible.load_nt("Philemon", ref="1.1")
rows = [{"text": t.text, **t.annotations} for t in corpus.documents[0].tokens]
pd.DataFrame(rows)[["text", "lemma", "morph", "upos", "strongs", "gloss"]].head()
#      text    lemma morph  upos strongs                             gloss
#    Παῦλος   Παῦλος N-NSM  NOUN    3972                              Paul
#   δέσμιος  δέσμιος N-NSM  NOUN    1198             one bound, a prisoner
#   Χριστοῦ  Χριστός N-GSM  NOUN    5547 anointed, the Messiah, the Christ
#     Ἰησοῦ   Ἰησοῦς N-GSM  NOUN    2424                             Jesus
#       καὶ      καί  CONJ CCONJ    2532           and, even, also, namely
```

The Robinson-to-UPOS mapping function is importable directly:

```python
from aegean.scripts.greek.nt import robinson_to_upos
robinson_to_upos("N-NSM")     # 'NOUN'
robinson_to_upos("V-PAI-3S")  # 'VERB'
robinson_to_upos("T-NSM")     # 'DET'
robinson_to_upos("CONJ")      # 'CCONJ'
robinson_to_upos("N-PRI")     # 'PROPN'  (proper noun)
robinson_to_upos("A-NUI")     # 'NUM'    (indeclinable numeral)
```

---

## Offline sample vs. full corpus

pyaegean bundles **two annotated Nestle 1904 chapters** inside the package for
offline use: **John 1** and **Philemon 1**.

```python
from aegean.greek import bible

bible.load_nt("John", ref="1", offline=True)        # bundled offline sample
bible.load_nt("Philemon", ref="1", offline=True)    # bundled offline sample (Phlm 1)
```

All other books, chapters, and whole-NT reads (`bible.load_nt()`) fetch the pinned
`nt-corpus` asset to your local cache on first use and read offline afterward. If
network access is unavailable and you request a book outside the bundled sample,
`bible.load_nt()` raises a `ValueError` naming the offline books and the
`PYAEGEAN_NT_CORPUS_URL` override:

```python
bible.load_nt("Romans")
# ValueError: 'Romans' is not in the bundled offline sample (only John, Phlm is
# available offline); the full 27-book corpus could not be fetched. Retry with
# network access, or set PYAEGEAN_NT_CORPUS_URL to a local copy.
```

Loaded corpora record which path was used; offline fallback loads note that status
in `corpus.provenance`.

---

## Multi-edition comparison, witnesses, Strong's, LXX, and commentaries

`aegean.greek.bible` integrates six groups of Koine, Septuagint, and patristic
resources, each fetched on demand to your local cache so the core package stays
small:

1. **Nine Greek New Testament editions and word-level variant diffs**
   (`bible.nt_editions()`, `bible.load_nt(..., edition=...)`,
   `bible.compare_editions()`; asset `nt-editions`, 3.29 MB gzip):
   - `nestle1904` — Nestle 1904 (gold lemma, Robinson morphology, Strong's, UD UPOS; CC0)
   - `sblgnt` — SBL Greek New Testament (Holmes 2010; CC BY 4.0 / MorphGNT CC BY-SA 3.0)
   - `srgnt` — CNTR Statistical Restoration GNT (CC BY 4.0)
   - `bhp` — CNTR Bunning Heuristic Prototype GNT (CC BY 4.0)
   - `tisch` — Tischendorf 8th Critical Edition (1869–1872; Public Domain)
   - `wh` — Westcott–Hort (1881, unaccented Unicode; Public Domain)
   - `byz` — Robinson–Pierpont Byzantine Majority Textform (Public Domain)
   - `antoniades` — Antoniades 1904 Patriarchal Edition (unaccented Unicode; Public Domain)
   - `tr` — CNTR Textus Receptus / KJTR (CC BY 4.0)

2. **Thirteen 2nd–5th century CE Greek NT manuscript witnesses**
   (`bible.witnesses()`, `bible.load_witness()`, `bible.compare_witnesses()`,
   `bible.parse_mes()`, `bible.expand_nomina_sacra()`; asset `nt-witnesses`, ~2.0 MB
   gzip; CNTR Class 1, CC BY-SA 4.0):
   - Major uncials: Sinaiticus (`01`/ℵ), Alexandrinus (`02`/A), Vaticanus (`03`/B),
     Ephraemi (`04`/C), Bezae (`05`/D), Washingtonianus (`032`/W).
   - Early papyri: `P45`, `P46`, `P47`, `P52` (Rylands), `P66`, `P72`, `P75`.
   - Preserves diplomatic CNTR MES transcriptions (original vs. corrector hands,
     lacunae, line breaks) and expands *nomina sacra* (`=θσ` → `Θεός`, `=ιυ` →
     `Ἰησοῦ`, `=πνα` → `Πνεῦμα`).

3. **Extended Strong's Greek Lexicon and etymological root trees**
   (`bible.use_strongs()`, `bible.strongs_entry()`, `bible.strongs_roots()`,
   `bible.search_strongs()`; asset `strongs-greek`, ~1.5 MB gzip; STEPBible TBESG
   CC BY 4.0 + OpenScriptures Strong's CC BY-SA):
   - 11,142 entries covering the NT, Septuagint (LXX), Apocrypha, and Apostolic
     Fathers, with recursive root chains and Hebrew equivalents.
   - Falls back offline to the bundled Dodson lexicon (CC0) without downloading.

4. **Septuagint (LXX) corpus, interlinear, concordance, and Psalm numbering**
   (`bible.lxx_books()`, `bible.load_lxx()`, `bible.enrich_lxx_interlinear()`,
   `bible.search_lxx()`, `bible.convert_psalm()`, `bible.psalm_mt_to_lxx()`,
   `bible.psalm_lxx_to_mt()`, plus `aegean.load("lxx")` and `aegean.open("Gen 1:1-5")`;
   asset `lxx-corpus-v2`, ~1.7 MB gzip; Swete 1887–1894 + Greek Wikisource Ecclesiastes,
   CC BY-SA 4.0):
   - Verse-indexed reading and Greek concordance search across all **56 Septuagint
     books** (29,470 verses, 592,436 tokens, including **Ecclesiastes**
     `tlg0527.tlg030`, LXX-plus sub-verses, and prologues).
   - Accepts inline references (`bible.load_lxx("Gen 1:1-5")`,
     `bible.load_lxx("MT Ps 23")`), Masoretic Psalm numbering (`numbering="mt"`),
     and automatic offline interlinear annotation (`interlinear=True`, tagged
     `annotation_source="auto-lexicon"` via the offline lemmatizer, Strong's/Dodson
     lexicon, and morphology).
   - Ships with an offline Swete sample (`Gen 1:1–5` and LXX `Ps 22:1–6` [MT Psalm
     23]), plus bidirectional LXX ↔ Masoretic Psalm conversion
     (`bible.psalm_mt_to_lxx(23) == (22,)`).

5. **Greek patristic commentaries, word studies, and cross-Testament concordance**
   (`bible.patristic_commentaries()`, `bible.load_commentary()`,
   `bible.commentary_excerpt()`, `bible.word_study()`, `bible.search_bible()`):
   - **112 indexed commentary works** across 11 Church Fathers and traditions: **30
     Greek NT *Catenae* volumes** (`tlg4102.*`), **41 Origen** commentaries and
     homilies (`tlg2042.*`), **26 John Chrysostom** biblical homily and commentary
     series (`ogc*`, Genesis through Hebrews, `kind="chrysostom"`), **6 First1KGreek
     Fathers** (Cyril of Alexandria, Methodius, Eusebius, Clement of Alexandria,
     *Vitae Prophetarum* / Hesychius), and **9 *Patrologia Graeca* commentary
     volumes** (`PG071`, `PG073` Cyril on John; `PG087_1` Procopius of Gaza;
     `PG101` Photius; `PG118` Oecumenius; `PG123`–`PG126` Theophylact of Bulgaria).
   - `bible.word_study()` combines lexicon lookup, root tree, NT occurrence counts,
     morphological distribution, and Septuagint occurrences (`lxx_total`,
     `lxx_by_book`, `lxx_occurrences`); `bible.search_bible(..., corpus="auto"|"nt"|"lxx"|"both")`
     searches either or both Testaments by lemma, text, morphology, gloss, or Strong's.

6. **Related Church Fathers, Early Christian, and Second Temple corpora**
   (`aegean library install church-fathers` and `aegean library install patristic`):
   - `aegean.load("chrysostom")` (155 works, 3.74M tokens), `aegean.load("church-fathers-early")`
     (432 works, 58 authors), and `aegean.load("church-fathers-late")` (280 works, 38 authors)
     provide 867 open-licensed patristic works across John Chrysostom, the Cappadocians,
     Athanasius, Cyril, Maximus the Confessor, John of Damascus, Photius, and Palamas.
   - `aegean.load("apostolic-fathers")`: 15 Apostolic Fathers works (64,944 tokens:
     1–2 Clement, Ignatius, Polycarp, Didache, Barnabas, Hermas, Diognetus).
   - `aegean.load("pseudepigrapha")`: 44 Greek OT Pseudepigrapha works (171,306
     tokens: 1 Enoch, Psalms of Solomon, Testaments of the 12 Patriarchs, Aristeas,
     Sibylline Oracles, 3–4 Baruch, 3–4 Maccabees, and others).
   - `aegean.load("patrologia")` or `bible.load_commentary("PG073")` (or
     `aegean.scripts.greek.load_patrologia("PG073")`): 33 *Patrologia Graeca*
     volumes (6.79M words, automated OCR).

### Python examples

```python
from aegean.greek import bible

# List all 9 NT editions and compare variants word by word
editions = bible.nt_editions()
cmp = bible.compare_editions("John", "1.18")
for v in cmp.verses[0].variants:
    print(v.edition, v.kind, v.base_words, "->", v.edition_words)

# Load a single manuscript witness or compare witnesses with expanded nomina sacra
p66 = bible.load_witness("P66", "John", "1.1-5")
for w in bible.compare_witnesses("John", "1.18")[0].witnesses:
    print(f"{w.siglum} ({w.alias}, {w.century}): {w.reading.readable}")
print(bible.expand_nomina_sacra("εν αρχη ην ο λογος προς τον θν")[0])

# Extended Strong's lookup, root tree, and unified word study
bible.use_strongs()
entry = bible.strongs_entry("G3056")       # StrongsEntry(lemma='λόγος', gloss='word', ...)
roots = bible.strongs_roots("G3056")
study = bible.word_study("G3056")          # gloss, roots, NT distribution, morphology
print(study.total_occurrences, study.by_morph)

# Septuagint reading, concordance search, Psalm conversion, and patristic commentaries
bible.convert_psalm(23)                    # {'system': 'mt', 'input': 23, 'mt': [23], 'lxx': [22], ...}
lxx_gen = bible.load_lxx("Gen", ref="1.1-5", offline=True)
lxx_hits = bible.search_lxx("φῶς", offline=True)
catena_excerpts = bible.commentary_excerpt("John", query="λόγος", limit=3)
cyril_excerpts = bible.commentary_excerpt("John", work_id="PG073", query="λόγος", limit=3)
```

### Shell examples

```bash
aegean bible read John 1.1 --interlinear
aegean bible read Gen 1.1-5 --lxx --offline
aegean bible compare John 1.18
aegean bible witnesses John 18.37 --sigla P52,01,03
aegean bible strongs G3056 --roots
aegean bible strongs "ἀγάπη"
aegean bible word-study ἀγάπη
aegean bible search V-AAI --by morph --book John
aegean bible search φῶς --lxx --offline
aegean bible books lxx
aegean bible psalm 23 --from mt
aegean bible commentary John --search λόγος --limit 3
aegean bible commentary PG073 --search λόγος --limit 3
aegean library install patristic
```

In `aegean tui`, press `b` to open the Biblical Greek study screen (Interlinear
Reader, 9-Edition Comparison, Early Manuscripts, Strong's Word Study, LXX
reader/search, and Patristic Commentaries). Nine biblical tools are also exposed
on the [MCP server](MCP): `biblical_strongs`, `biblical_word_study`,
`biblical_psalm`, `biblical_nomina_sacra`, `biblical_catalog`, `biblical_lxx`,
`biblical_compare_editions`, `biblical_witnesses`, and `biblical_commentary`.

---

## Source, licence, and provenance

The default annotated NT text is **Nestle 1904** (*Novum Testamentum Graece*, ed.
Eberhard Nestle). Per-token morphology, lemmas, and Strong's numbers come from
`biblicalhumanities/Nestle1904` under **CC0**; the base Greek text is public
domain. Because of that CC0 dedication, pyaegean can both redistribute the full
corpus asset and bundle the two-chapter offline sample without downstream
attribution requirements. Provenance travels on every loaded `Corpus`:

```python
from aegean.greek import bible

corpus = bible.load_nt("John", ref="1")
corpus.provenance.source
# 'Nestle 1904 Greek NT — morphology/lemmas (biblicalhumanities/Nestle1904)'
corpus.provenance.license
# "CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain"
corpus.provenance.data_version
# 'nt-corpus-v1@713f28a3b7d4d66132f5aa809fa223fe79762e5d'
```

The full corpus is a SHA-256-pinned release asset. Set `PYAEGEAN_NT_CORPUS_URL` to
point `bible.load_nt()` at a local or alternate copy. See
[Data and Provenance](Data-and-Provenance) for caches, pins, and licences across
all datasets.

---

## Measuring a tagger on the NT

Because the Nestle 1904 annotations are gold and independent of pyaegean's
predictions, the NT also functions as an out-of-domain benchmark.
`greek.evaluate_on_nt()` (CLI: `aegean greek eval nt`) scores the neural pipeline
against Nestle 1904 gold lemmas and reconciled UPOS. The shipped models train on
AGDT, Gorman, and Pedalion, not on the NT. Measured figures and lemma-convention
notes are in [Benchmarks](Benchmarks).

Evaluation requires the fetched, pinned **full 27-book corpus**. The bundled John 1
and Philemon sample works for offline reading and examples, but it is too small
for a benchmark; `evaluate_on_nt()` and `eval nt` stop with a fetch instruction
if only the offline sample is present.

---

## Notes and limitations

- **Nestle 1904 annotations are gold and fixed** (Robinson morphology), independent
  of pyaegean's taggers, which makes the corpus usable as an evaluation benchmark.
- **One `Document` per chapter.** Loading a whole book returns one document per
  chapter; passing `ref` filters the verses within the selected chapters.
- **A `ref` requires a `book`.** Verse ranges cannot span across all 27 books at
  once.
- **Unannotated editions, LXX, and commentaries.** The eight non-Nestle NT
  editions (`nt-editions`), the Septuagint (`lxx-corpus`), and patristic
  commentaries (First1KGreek and `patrologia-graeca-corpus`) do not carry Nestle
  1904 Robinson tags; run `greek.pipeline()` or `greek.annotate_corpus()` to
  analyze them. *Patrologia Graeca* (`PG*`) volumes are automated OCR
  transcriptions (`edition_fidelity="ocr"`).

---

## See also

- [CLI: Biblical & Koine Greek](CLI-Bible): command-by-command reference for `aegean bible`
- [Greek Works and Books](Greek-Works-and-Books): classical literary works (`greek.load_work` and CTS IDs)
- [Greek NLP](Greek-NLP): syllabification, scansion, tagging, lemmatization, and parsing
- [Data and Provenance](Data-and-Provenance): caches, pinned commits, and licences
- [Getting Started](Getting-Started) and the [Tutorial](Tutorial): introductory guides
- [Limitations](Limitations): scope and known gaps
