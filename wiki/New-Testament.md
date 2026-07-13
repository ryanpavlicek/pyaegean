# New Testament

The Greek New Testament is a first-class, annotated corpus in pyaegean. One call,
`greek.load_nt(...)`, returns the Koine text of the NT (the **Nestle 1904** edition)
as a standard `Corpus` in which **every token already carries gold annotations**: a
dictionary `lemma`, a Robinson-style `morph` parse, a `strongs` number, a reconciled
Universal Dependencies `upos`, the `normalized` form, and a short Koine `gloss`. You
never have to run a tagger to work with it: the analysis is already there, and it is
gold (from the edition), not pyaegean's own prediction.

This page is the reference for that corpus and the `aegean greek nt` command family.
For the wider "load real Greek texts" story (the classical literary works, the
`load_work` / CTS-id path) see [Greek Works and Books](Greek-Works-and-Books); for
everything you can then run on the loaded text (syllabify, scan, tag, parse) see
[Greek NLP](Greek-NLP).

---

## Quick start

```python
from aegean import greek

corpus = greek.load_nt("John", ref="1.1-1.3")   # John 1:1–3, offline (bundled)
doc = corpus.documents[0]
doc.id                                # 'John 1'
doc.meta.name                         # 'John 1'

t = doc.tokens[0]
t.text                                # 'Ἐν'
t.annotations
# {'lemma': 'ἐν', 'morph': 'PREP', 'strongs': '1722', 'normalized': 'Ἐν',
#  'upos': 'ADP', 'ref': 'John.1.1', 'gloss': 'in, on, among'}
```

On the command line, the same read:

```bash
aegean greek nt John 1
```

```
John 1  (1 chapter, 828 tokens)
John 1
  1: Ἐν ἀρχῇ ἦν ὁ Λόγος, καὶ ὁ Λόγος ἦν πρὸς τὸν Θεόν, καὶ Θεὸς ἦν ὁ Λόγος.
  2: Οὗτος ἦν ἐν ἀρχῇ πρὸς τὸν Θεόν.
  3: πάντα δι’ αὐτοῦ ἐγένετο, καὶ χωρὶς αὐτοῦ ἐγένετο οὐδὲ ἕν ὃ γέγονεν.
  …
```

---

## `load_nt(book=None, *, ref=None, force=False)`

The Koine counterpart to `load_work`. It returns a `Corpus` with **one `Document`
per chapter**; each token's annotations live in `Token.annotations`, so
`to_dataframe(level="token")` surfaces them as columns.

| argument | meaning |
|----------|---------|
| `book` | a book name or abbreviation (`"John"`, `"Jn"`, `"1Cor"`, `"Rev"`). Omit it (or pass `None`) to load the whole 27-book NT. |
| `ref` | a chapter, verse, or range within the book (see below). A `ref` **requires** a `book`; you cannot address a verse across all 27 books. |
| `force` | re-fetch the full corpus asset even if it is already cached. |

```python
greek.load_nt("John")                  # the whole Gospel of John
greek.load_nt("John", ref="1.1-18")    # John 1:1–18
greek.load_nt("Rom", ref="8")          # Romans chapter 8
greek.load_nt("Rom", ref="8.28")       # a single verse, Romans 8:28
greek.load_nt()                        # the whole 27-book NT
```

Token text, lemmas, and normalized forms are NFC-normalized at load time (the source
edition mixes precomposed oxia and tonos codepoints, and the rest of the library
emits NFC), so the gold strings compare byte-for-byte with pyaegean's own output.

---

## The CLI: `aegean greek nt BOOK [PASSAGE]`

```
aegean greek nt [BOOK] [PASSAGE] [--ref REF] [-o FILE] [--json]
```

`PASSAGE` is a **positional** chapter or range, so the common reads are short:

```bash
aegean greek nt John 1        # a whole chapter
aegean greek nt Matt 1-3      # a chapter range
aegean greek nt John 1.1-1.18 # a verse range
aegean greek nt Rom 8.28      # a single verse
```

Naming a **book** renders the text (chapter headers, verse-numbered lines):

```bash
aegean greek nt Matt 1-3
```

```
Matt 1-3  (3 chapters, 1220 tokens)
Matthew 1
  1: Βίβλος γενέσεως Ἰησοῦ Χριστοῦ υἱοῦ Δαυεὶδ υἱοῦ Ἀβραάμ.
  2: Ἀβραὰμ ἐγέννησεν τὸν Ἰσαάκ, Ἰσαὰκ δὲ ἐγέννησεν τὸν Ἰακώβ, …
  …
```

`--ref` is an alias for the positional `PASSAGE` (`aegean greek nt John --ref 1.1-1.18`
does the same as `aegean greek nt John 1.1-1.18`). Give the passage one way or the
other, not both.

**With no `BOOK`** the command prints a summary of the whole NT rather than dumping
137,779 tokens to your terminal:

```bash
aegean greek nt
```

```
                                   Greek NT
┌──────────────┬──────────────────────────────────────────────────────┐
│ field        │ value                                                  │
├──────────────┼──────────────────────────────────────────────────────┤
│ scope        │ whole NT                                                │
│ ref          │                                                        │
│ documents    │ 260                                                    │
│ tokens       │ 137779                                                 │
│ first        │ Matt 1                                                 │
│ source       │ Nestle 1904 Greek NT — morphology/lemmas …            │
│ data_version │ nt-corpus-v1@713f28a3b7d4d66132f5aa809fa223fe79762e5d │
└──────────────┴──────────────────────────────────────────────────────┘
read a book:  aegean greek nt John 1   (a chapter or range, e.g. Matt 1-3)
```

Two more flags:

| flag | meaning |
|------|---------|
| `-o` / `--output` | save the selected corpus to a `.json` or `.db`/`.sqlite` file (chosen by extension) instead of printing. |
| `--json` | print a machine-readable summary (`scope`, `ref`, `documents`, `tokens`, `first`, `source`, `data_version`). |

Because the per-token annotations ride in each token, exporting at token level spreads
them into columns:

```bash
aegean greek nt John 1 -o john1.json
aegean export john1.json -f csv --level token -o john1.csv   # lemma, morph, strongs, upos, … as columns
```

---

## Addressing a passage with `ref`

`ref` mirrors `load_work`, read as **chapter.verse**:

| `ref` | selects |
|-------|---------|
| `"3"` | chapter 3 |
| `"3.16"` | chapter 3, verse 16 |
| `"3.16-3.18"` | verses 3:16–3:18 |
| `"3.16-18"` | the same range, shorthand (the high end inherits the low end's chapter) |
| `"3-5"` | chapters 3 through 5 |

A malformed reference is rejected with a message that names the accepted shapes,
never a raw `int()` traceback.

---

## Book names and aliases

`load_nt` (and the CLI) accept any book by its canonical name **or** by a common
abbreviation, case-insensitively, ignoring spaces and dots: `"Matthew"`, `"Matt"`,
`"mt"`, `"1 Cor"`, `"1cor"`, and `"1Cor."` all resolve. The canonical `name` is what
appears in document ids (`John 1`, `Phlm 1`).

`greek.nt_books()` lists all 27 in canonical order (pure metadata, no download):

```python
from aegean import greek
books = greek.nt_books()
len(books)         # 27
books[3]           # {'name': 'John', 'aliases': ['john', 'jn', 'jhn']}
```

From the shell:

```bash
aegean greek nt-books          # a table of the 27 books and the names load_nt accepts
aegean greek nt-books --json   # the same data as JSON
```

| book | accepted names |
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

An unrecognised name gives a helpful suggestion:

```bash
aegean greek nt Genesis
# aegean: unknown NT book 'Genesis' — did you mean 'Eph'?
# (`aegean greek nt-books` lists all 27)
```

(Genesis is in the Hebrew Bible, not the Greek NT: `load_nt` covers the 27 NT books
only.)

---

## Per-token annotation fields

Every token in a loaded NT corpus carries these in `Token.annotations`:

| field | what it is |
|-------|------------|
| `lemma` | dictionary headword (gold, from Nestle 1904) |
| `morph` | Robinson-style morphology tag, e.g. `N-NSM`, `V-PAI-3S` |
| `strongs` | Strong's number (e.g. `3972` = Paul) |
| `upos` | coarse Universal Dependencies part of speech, reconciled from `morph` |
| `normalized` | accent/diacritic-normalized form |
| `ref` | canonical address of the token, e.g. `John.1.1` |
| `gloss` | brief English gloss (bundled Dodson lexicon, when available) |

Turn a chapter into a table where each field is its own column:

```python
import pandas as pd
from aegean import greek

corpus = greek.load_nt("Philemon", ref="1.1")
rows = [{"text": t.text, **t.annotations} for t in corpus.documents[0].tokens]
pd.DataFrame(rows)[["text", "lemma", "morph", "upos", "strongs", "gloss"]].head()
#      text    lemma morph  upos strongs                             gloss
#    Παῦλος   Παῦλος N-NSM  NOUN    3972                              Paul
#   δέσμιος  δέσμιος N-NSM  NOUN    1198             one bound, a prisoner
#   Χριστοῦ  Χριστός N-GSM  NOUN    5547 anointed, the Messiah, the Christ
#     Ἰησοῦ   Ἰησοῦς N-GSM  NOUN    2424                             Jesus
#       καὶ      καί  CONJ CCONJ    2532           and, even, also, namely
```

The Robinson-to-UPOS mapping that fills `upos` is exposed if you want it directly:

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

## Source, licence, and provenance

The text is the **Nestle 1904** edition (*Novum Testamentum Graece*, ed. Eberhard
Nestle). The per-token morphology, lemmas, and Strong's numbers come from the
`biblicalhumanities/Nestle1904` digital edition and are dedicated to the public
domain under **CC0**; the base Greek text is itself public domain. That CC0 status is
what lets pyaegean both fetch the full corpus and bundle an offline sample without any
attribution burden on you. The provenance travels with the corpus:

```python
corpus = greek.load_nt("John", ref="1")
corpus.provenance.source
# 'Nestle 1904 Greek NT — morphology/lemmas (biblicalhumanities/Nestle1904)'
corpus.provenance.license
# "CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain"
corpus.provenance.data_version
# 'nt-corpus-v1@713f28a3b7d4d66132f5aa809fa223fe79762e5d'
```

The full corpus is a sha256-pinned release asset, so the same request gives you the
same text tomorrow. Set `PYAEGEAN_NT_CORPUS_URL` to point `load_nt` at a local or
alternate copy. See [Data and Provenance](Data-and-Provenance) for how the cache,
pins, and licences work across the whole toolkit.

---

## Offline sample vs. the full corpus

pyaegean bundles **two fully annotated chapters inside the package as an offline
sample: John 1 and Philemon 1**. Those two reads work with no network at all:

```python
greek.load_nt("John", ref="1")        # offline
greek.load_nt("Philemon", ref="1")    # offline  (Phlm 1)
```

Everything else (the rest of John, all the other books, or the whole NT with
`load_nt()`) is fetched to your local cache on first use and then read offline
thereafter. When the full asset cannot be fetched and you ask for a book outside the
bundled sample, the error says so plainly rather than failing obscurely:

```python
greek.load_nt("Romans")
# ValueError: 'Romans' is not in the bundled offline sample (only John, Phlm is
# available offline); the full 27-book corpus could not be fetched. Retry with
# network access, or set PYAEGEAN_NT_CORPUS_URL to a local copy.
```

Loaded corpora record which path was taken: the bundled sample notes in its
provenance that it is the offline fallback.

---

## Glossing without loading a book

To look up a single Koine word's gloss without loading any chapter, use the bundled
Dodson lexicon (CC0, no download): `greek.gloss_nt(...)` / `greek.lookup_nt(...)` /
`greek.gloss_strongs(...)`, or the CLI `aegean greek gloss-nt`. This is the same
lexicon the corpus self-glosses from, so a token's `gloss` annotation and a
`gloss-nt` lookup agree. Full details are on [Greek NLP](Greek-NLP).

```bash
aegean greek gloss-nt "ἀγάπη"            # love
aegean greek gloss-nt --strongs "3056"   # a word, speech, divine utterance, analogy
```

---

## Measuring a tagger on the NT

Because the annotations are gold and independent of pyaegean's own predictions, the
NT doubles as an out-of-domain benchmark. `greek.evaluate_on_nt()` (CLI
`aegean greek eval nt`) scores the neural pipeline against the Nestle 1904 gold
(lemma and reconciled UPOS), a Nestle-own-gold complement to the PROIEL check. Both
are genuinely out-of-domain: the shipped models train on AGDT, Gorman, and Pedalion,
never on the NT. The measured numbers and the honesty notes (lemma-convention
differences, why finer features are not cross-comparable) are in
[Benchmarks](Benchmarks).

Evaluation requires the fetched, pinned **full 27-book corpus**. The bundled John 1
and Philemon sample remains useful for offline reading and API examples, but it is too
small to produce a representative benchmark; `evaluate_on_nt()` and `eval nt` stop
with a fetch instruction instead of reporting a sample-derived score.

---

## Notes and limitations

- **Annotations are gold and fixed** (Nestle 1904 morphology), not pyaegean's own
  prediction, which is exactly what makes the corpus useful as a benchmark.
- **One `Document` per chapter.** A whole-book load is a corpus of chapters; a `ref`
  range trims the verses within the affected chapters.
- **A `ref` needs a book.** You cannot address a verse across all 27 books at once.
- **Scope is the 27-book Greek NT only.** Old Testament / Septuagint books are not
  covered here.

---

## See also

- [Greek Works and Books](Greek-Works-and-Books): the classical literary corpus and
  the `load_work` / CTS-id path, alongside this NT section
- [Greek NLP](Greek-NLP): syllabify, scan, tag, lemmatize, and parse a loaded corpus,
  plus the Dodson glossing details
- [Data and Provenance](Data-and-Provenance): caches, pinned commits, and licences
- [Getting Started](Getting-Started) and the [Tutorial](Tutorial): first steps
- [Limitations](Limitations): overall scope and known gaps
