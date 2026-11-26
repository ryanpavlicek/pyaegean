# Greek Works and Books

This page covers loading complete Ancient Greek texts into pyaegean as standard
`Corpus` objects ready for tokenization, scansion, tagging, and frequency
analysis.

Three loaders cover the main Greek collections:

- **`greek.load_work("tlg0012.tlg001")`**: any of 1,778 Greek works in Perseus
  `canonical-greekLit` and `First1KGreek`, addressed by CTS ID
  (`tlgAAAA.tlgBBB`).
- **`aegean.greek.bible` (`bible.load_nt(...)`, `bible.load_lxx(...)`,
  `bible.load_witness(...)`)**: 9 Greek New Testament editions, 55 Swete
  Septuagint books, 13 early manuscript witnesses, and 86 patristic commentaries.
- **`aegean.load(...)`** for dedicated hosted Greek collections:
  `apostolic-fathers` (15 works), `pseudepigrapha` (44 Second Temple Greek
  works), `patrologia` (33 *Patrologia Graeca* volumes, 6.79M words),
  `byzantine` (12 medieval and early-modern vernacular texts), and
  `homer-scholia` (54 documents: 24 books of the Venetus A *Iliad* plus Venetus
  A, Venetus B, and Escorial Homeric scholia). Install them in groups with
  `aegean library install biblical`, `patristic`, or `literary`.

Each path caches fetched files locally for subsequent offline use and returns a
standard `Corpus`. Every analysis stage on [Greek NLP](Greek-NLP) runs directly
on the result.

> **Work IDs work anywhere a corpus is accepted.** Commands taking a `CORPUS`
> argument accept a registered corpus ID (`lineara`, `nt`, …), a Greek CTS work
> ID (`tlg0012.tlg001`), a path to a saved `.json` or `.db` corpus, or `-` for
> JSON on stdin. For example, `aegean stats tlg0012.tlg001`, `aegean export
> tlg0012.tlg002 -f csv -o odyssey.csv`, and `aegean db build tlg0012.tlg001 -o
> iliad.db` all resolve the work ID automatically through `load_work`. See
> [§5](#5-put-works-into-a-database).

> New to pyaegean? Start with [Getting Started](Getting-Started) and the
> [Tutorial](Tutorial), which walks through loading the *Iliad*. For CLI options
> see [CLI](CLI); for licences and cache layout see
> [Data & Provenance](Data-and-Provenance).

---

## 1. The `tlgAAAA.tlgBBB` work-id scheme

Classical Greek works are addressed by their **CTS** (Canonical Text Services)
ID, the same identifier used in citations and the Scaife Viewer.

A work ID consists of two parts separated by a dot:

```
tlg0012 . tlg001
└──┬──┘   └──┬──┘
 author     work
 group     within
           that author
```

- The first half (`tlg0012`) identifies the author or text group (Homer).
- The second half (`tlg001`) identifies a specific work (`tlg001` = *Iliad*,
  `tlg002` = *Odyssey*).

The `tlg` prefix derives from the *Thesaurus Linguae Graecae* numbering scheme;
a few First1KGreek works use a `stoa` prefix with the same dotted structure.

> The dot is required: `load_work` uses the prefix as the author directory and
> the suffix as the work file. Passing an ID without a dot raises a clear error
> specifying the `tlgGROUP.tlgWORK` format.

---

## 2. The curated shortlist: `popular_works()`

pyaegean ships a hand-verified shortlist of 25 common works so you can look up
their IDs offline. Every entry resolves against the live collections; for the
full 1,778-work index, see [§3](#3-finding-any-other-work).

### Python

```python
from aegean import greek

works = greek.popular_works()
len(works)            # 25
works[0]              # {'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'}
```

`popular_works()` reads bundled metadata with no network access and returns a
list of dicts with `id`, `author`, and `title`.

### CLI

```bash
aegean greek works
```

Output:

```
                        Popular Greek works
┌────────────────┬──────────────┬──────────────────────────────────┐
│ id             │ author       │ title                            │
├────────────────┼──────────────┼──────────────────────────────────┤
│ tlg0012.tlg001 │ Homer        │ Iliad                            │
│ tlg0012.tlg002 │ Homer        │ Odyssey                          │
│ …              │ …            │ …                                │
└────────────────┴──────────────┴──────────────────────────────────┘

Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
This is a curated subset — the full canon is at https://scaife.perseus.org
```

Pass `--json` for machine-readable output (`aegean greek works --json`).

### All 25 curated entries

| ID | Author | Title |
|----|--------|-------|
| `tlg0012.tlg001` | Homer | Iliad |
| `tlg0012.tlg002` | Homer | Odyssey |
| `tlg0020.tlg001` | Hesiod | Theogony |
| `tlg0020.tlg002` | Hesiod | Works and Days |
| `tlg0085.tlg004` | Aeschylus | Seven Against Thebes |
| `tlg0085.tlg005` | Aeschylus | Agamemnon |
| `tlg0085.tlg006` | Aeschylus | Libation Bearers |
| `tlg0011.tlg001` | Sophocles | Trachiniae |
| `tlg0011.tlg002` | Sophocles | Antigone |
| `tlg0011.tlg003` | Sophocles | Ajax |
| `tlg0011.tlg004` | Sophocles | Oedipus Tyrannus |
| `tlg0006.tlg001` | Euripides | Cyclops |
| `tlg0006.tlg002` | Euripides | Alcestis |
| `tlg0006.tlg003` | Euripides | Medea |
| `tlg0019.tlg002` | Aristophanes | Knights |
| `tlg0019.tlg003` | Aristophanes | Clouds |
| `tlg0016.tlg001` | Herodotus | Histories |
| `tlg0003.tlg001` | Thucydides | History of the Peloponnesian War |
| `tlg0032.tlg002` | Xenophon | Memorabilia |
| `tlg0032.tlg006` | Xenophon | Anabasis |
| `tlg0059.tlg002` | Plato | Apology |
| `tlg0059.tlg003` | Plato | Crito |
| `tlg0059.tlg004` | Plato | Phaedo |
| `tlg0059.tlg030` | Plato | Republic |
| `tlg0086.tlg010` | Aristotle | Nicomachean Ethics |

Works by the same author share the first prefix: all four Sophocles plays start
with `tlg0011`, and all four Plato dialogues start with `tlg0059`. To search all
1,778 loadable works offline, use `catalog()` / `aegean greek catalog` below.

---

## 3. Finding any other work

`load_work` accepts any CTS ID present in Perseus `canonical-greekLit` or
`First1KGreek`, beyond the 25 shortlisted works above. You can find IDs offline
with `catalog()` or online in the Scaife Viewer.

### Full discovery index: `catalog()` / `aegean greek catalog`

pyaegean bundles a complete index of every Greek (`-grc`) edition in both
repositories: **1,778 works** (768 from Perseus `canonical-greekLit`, 1,010 from
`First1KGreek`). Because it is bundled metadata (`id`, `author`, English
`title`, `greek_title`, `source`), searching requires no network connection.
Every indexed work is fetchable by `load_work`.

`catalog(query=None, *, author=None, title=None, source=None)` returns matching
dicts; all supplied filters combine via AND, and `query` matches across ID,
author, and both titles:

```python
from aegean import greek

len(greek.catalog())                       # 1778   (768 perseus + 1010 first1k)
len(greek.catalog(author="plato"))         # 39     (all Plato works in the open repos)
greek.catalog(title="Ἀντιγόνη")            # search by Greek title
# [{'id': 'tlg0011.tlg002', 'author': 'Sophocles', 'title': 'Antigone',
#   'greek_title': 'Ἀντιγόνη', 'source': 'perseus'}]
len(greek.catalog("herodotus"))            # 2      (free-text across id/author/title)
len(greek.catalog(source="first1k"))       # 1010   (limit to one collection)

greek.catalog()[0]
# {'id': 'tlg0001.tlg001', 'author': 'Apollonius Rhodius',
#  'title': 'Argonautica', 'greek_title': 'Argonautica', 'source': 'perseus'}
```

From the shell, `aegean greek catalog [QUERY]` supports `--author`/`-a`,
`--title`/`-t`, `--source`, `--limit`/`-n`, `--output`/`-o`, and `--json`:

```bash
aegean greek catalog --author plato                      # filter by author (39 matches)
aegean greek catalog sappho                              # free-text query
aegean greek catalog --author homer -o homer_works.csv   # wrote 49 works to homer_works.csv
```

Queries with zero matches print an explicit message:

```bash
aegean greek catalog sappho
# No works match. Try a looser filter, or browse https://scaife.perseus.org
```

> **Catalogue scope.** The index reflects exactly what the two open repositories
> hold at their pinned commits, not the entire surviving Greek corpus. Authors
> whose Greek texts are not openly digitized in those repos (such as Sappho) are
> absent.

### Scaife Viewer

To browse texts or confirm an edition on the web:

1. Open the [Scaife Viewer](https://scaife.perseus.org).
2. Navigate to the author and work.
3. Extract the CTS ID from the URN or URL: in
   `urn:cts:greekLit:tlg0012.tlg001.perseus-grc2`, pass `tlg0012.tlg001` to
   `load_work` (omitting `urn:cts:greekLit:` and the edition suffix).

Passing an unresolvable ID raises `DataNotAvailableError`:

```python
greek.load_work("tlg9999.tlg999")
# aegean.data.DataNotAvailableError: could not fetch 'tlg9999.tlg999' (...).
# Works are addressed as 'tlgGROUP.tlgWORK', e.g. tlg0012.tlg001 (Iliad).
```

### Selecting an edition and source

When a work appears in multiple digital editions or both collections, use
`source` and `edition` to disambiguate:

| Argument | Values | Behavior |
|----------|--------|----------|
| `source` | `"auto"` (default), `"perseus"`, `"first1k"` | Collection search order (`"auto"` tries Perseus, then First1KGreek). |
| `edition` | Full filename or substring such as `"perseus-grc2"` | Pin a specific edition file; otherwise the highest-numbered `-grc*` edition is selected. |

```python
# select the First1KGreek copy and a specific edition file
greek.load_work("tlg0086.tlg005", source="first1k", edition="1st1K-grc1")
```

---

## 4. Loading a work and addressing parts of it (`ref`)

### Whole work

Calling `load_work` without `ref` returns the full work with **one `Document`
per top-level division** (such as a book of the *Iliad* or a prose book/chapter
group):

```python
from aegean import greek

corpus = greek.load_work("tlg0012.tlg001")   # fetched on first use, then cached
len(corpus)                                  # 24 (the 24 books of the Iliad)
corpus.documents[0].id                       # 'tlg0012.tlg001:1'
corpus.documents[0].meta.name                # 'Ἰλιάς — Book 1'
sum(len(d.tokens) for d in corpus)           # 127339
```

### Selecting a section with `ref`

`ref` uses dot-separated citation coordinates matching the work's structure,
with an optional hyphenated range:

| `ref` | Meaning | Example |
|-------|---------|---------|
| `"1"` | single top-level division | *Iliad* Book 1 |
| `"1.2"` | nested division (book 1, chapter 2) | Herodotus 1.2 |
| `"1.1-1.50"` | full line range | *Iliad* 1.1–50 |
| `"1.1-50"` | shorthand line range (upper end inherits prefix) | *Iliad* 1.1–50 |

Opening lines of the *Iliad*:

```python
from aegean import greek

corpus = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")
len(corpus)                          # 1 (single Document for the range)
doc = corpus.documents[0]
doc.id                               # 'tlg0012.tlg001:1.1-1.10'
doc.meta.name                        # 'Ἰλιάς — 1.1-1.10'
len(doc.lines)                       # 10
" ".join(t.text for t in doc.tokens if t.line_no == 0)
# 'μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος'
```

In prose works, the second coordinate is typically a chapter:

```python
greek.load_work("tlg0016.tlg001", ref="1.2")   # Herodotus, Book 1, Chapter 2
```

### Citation schemes: how a work is addressed

Every `ref` resolves against the work's declared TEI `<refsDecl>` citation
scheme. pyaegean reads the hierarchy directly from each edition's XML header
rather than guessing by author:

| Genre | Typical levels | Example `ref` | Verified work |
|-------|----------------|---------------|---------------|
| Epic / elegy (verse) | `book.line` | `1`, `1.1`, `1.1-1.50` | *Iliad* → `['book', 'line']` |
| Drama | `line` | `1`, `1-50` | *Antigone*, *Medea* → `['line']` |
| Plato (Stephanus-paged) | `section` | `17` | *Apology*, *Crito* → `['section']` |
| Aristotle | `chapter.subchapter` | `1`, `1.2` | *Poetics* → `['chapter', 'subchapter']` (*Nicomachean Ethics* uses `['book', 'section']`) |
| Multi-book prose | `book.chapter.section` | `1`, `1.2`, `1.2.3` | Herodotus, Xenophon's *Anabasis* → `['book', 'chapter', 'section']` |

Inspect a work's exact levels with `greek.citation_scheme(id)` (fetches the TEI
once, like `load_work`):

```python
greek.citation_scheme("tlg0012.tlg001")   # ['book', 'line']   (Homer, Iliad)
greek.citation_scheme("tlg0059.tlg002")   # ['section']        (Plato, Apology)
greek.citation_scheme("tlg0032.tlg006")   # ['book', 'chapter', 'section'] (Xenophon, Anabasis)
```

When a `ref` misses, the error names the work's actual citation scheme (such as
`… cited by book.line`). Two structural rules apply:

- Hyphen ranges must stay within one top-level division (`1.1-1.50` works;
  `1.1-2.50` across books is rejected; load each book separately and call
  `Corpus.merge`, or use a comma list).
- Comma lists (`1.1,1.5` or `1,3`) select multiple siblings or cross-division
  segments as separate `Document` objects in source order.

Editions also place finer references in TEI `<milestone>` markers outside the
`<div>` hierarchy, such as Stephanus sub-pages (`17a`) or Bekker lines
(`1447a10`, column `a` of page `1447`, line `10`). `--ref` addresses these
milestones directly by extracting the span from the named marker up to the next
marker of the same kind. For example,
`aegean greek work tlg0086.tlg034 --ref 1447a10` (Aristotle's *Poetics*) returns
the span from line 10 to the next marked line. Because Perseus marks every fifth
Bekker line, `1447a10` yields lines 10–14 and unmarked lines (`1447a11`–`1447a14`)
resolve to nothing. A Bekker page-column resolves the same way (`1447a` = column
`a` of page 1447); request a full physical page as a comma list of both columns
(`1447a,1447b`). Milestone refs can be combined in comma lists (`17a,17b`),
returning one `Document` per marker. Hyphen ranges of milestones are not yet
supported; use a comma list of individual markers instead.

### Command-line usage

```bash
aegean greek works                               # list the 25 curated works
aegean greek work tlg0012.tlg001 --ref 1.1-1.10  # load a section
```

Output:

```
                          tlg0012.tlg001
┌──────────────┬───────────────────────────────────────────┐
│ field        │ value                                     │
├──────────────┼───────────────────────────────────────────┤
│ documents    │ 1                                         │
│ tokens       │ 78                                        │
│ first        │ tlg0012.tlg001:1.1-1.10                   │
│ name         │ Ἰλιάς — 1.1-1.10                          │
│ source       │ PerseusDL/canonical-greekLit (…grc2.xml)  │
│ data_version │ PerseusDL/canonical-greekLit@d4fab69a2c26 │
└──────────────┴───────────────────────────────────────────┘
```

`aegean greek work` options:

| Option | Meaning | Default |
|--------|---------|---------|
| `WORK_ID` | CTS ID, e.g. `tlg0012.tlg001` | required |
| `--ref` | Citation selection (`1`, `1.2`, `1.1-1.50`, `1447a,1447b`) | whole work |
| `--source` | `auto`, `perseus`, or `first1k` | `auto` |
| `--edition` | Specific edition file fragment | best `-grc*` |
| `--output` / `-o` | Write corpus to a JSON file | print summary |
| `--json` | Machine-readable summary on stdout | table |

Save a work to disk to avoid re-parsing TEI on subsequent commands:

```bash
aegean greek work tlg0012.tlg001 -o iliad.json   # wrote 24 documents to iliad.json
```

### Bulk-fetching an author and managing cached works

Pass `all` as the work ID to fetch every catalogued work by an author
(case-insensitive). Already-cached files are skipped, so interrupted fetches
resume cleanly:

```bash
aegean greek work all homer --dry-run    # preview works to fetch
aegean greek work all homer --yes        # fetch them (--limit N caps new downloads)
```

List cached works with `aegean greek works --downloaded`, and clear them with
`--remove <id>`, `--remove-author <name>`, or `--remove-all`. The Python
equivalents are `greek.fetch_works`, `greek.list_fetched_works()`, and
`greek.remove_fetched_works(...)`.

### Editorial notes, source text, and speaker labels

TEI `<note>` and `<bibl>` elements are kept out of the running token stream and
stored in `doc.meta.notes`, preserving apparatus information without polluting
lexical counts.

`Document.source_text` holds the whitespace-normalized selected TEI reading
(rather than raw XML bytes), and tokens retain aligned source spans,
punctuation, foreign text, and numerals. Use `doc.words` for lexical analysis.
Dramatic speaker labels are preserved as `UNKNOWN` tokens excluded from word
counts, with `who`, `speaker_label`, and `speech_id` annotations retaining their
context.

---

## 5. Put works into a database

Loading via `load_work` re-parses cached TEI XML each run. For repeated queries,
multi-work analysis, or sharing, materialize the corpus into a **SQLite
database** with an FTS5 full-text index. Because `aegean db build`, `combine`,
`stats`, and `export` accept Greek CTS work IDs directly, no Python script is
required.

### One work to one database

```bash
aegean db build tlg0012.tlg001 -o iliad.db
# wrote 24 documents to iliad.db
```

Pass `--no-fts` to omit the full-text index when only raw tables are needed.
In Python:

```python
from aegean import greek
greek.load_work("tlg0012.tlg001").to_sql("iliad.db")   # fts=True by default
```

### Merging multiple works: `combine`

`aegean combine` merges multiple corpora (work IDs, registered corpora, or saved
`.json`/`.db` files) into one `.db` or `.json` file while recording every input
source in provenance:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db
# wrote 48 documents to homer.db (merged 2 sources)
```

Control duplicate document IDs with `--on-conflict`: `error` (default), `first`,
`last`, or `suffix` (retain both with disambiguated IDs):

```bash
aegean combine a.json b.json -o merged.db --on-conflict last
```

In Python, use `aegean.combine([...])` or `Corpus.merge(*others)`:

```python
from aegean import greek, combine

iliad   = greek.load_work("tlg0012.tlg001")
odyssey = greek.load_work("tlg0012.tlg002")

homer = combine([iliad, odyssey])          # dedupe="error" by default
len(homer)                                 # 48
homer.provenance.source                    # 'Merged corpus (aegean.combine)'
homer.to_sql("homer.db")

# equivalent method form:
homer = iliad.merge(odyssey, dedupe="error")
```

### Full-text search: `db search`

Once built, `aegean db search` runs offline against the FTS5 index, reporting
document ID, token position, and matched token:

```bash
aegean db search homer.db μῆνιν
```

```
 'μῆνιν' in homer.db
┌────────────────┬─────┬───────┐
│ doc            │ pos │ text  │
├────────────────┼─────┼───────┤
│ tlg0012.tlg001:1 │ 0 │ μῆνιν │
└────────────────┴─────┴───────┘
```

Pass `--limit N` (default 50) or `--json` for structured output. Queries match
whole tokens literally (`KU-RO` matches `KU-RO`, not `PO-TO-KU-RO`); pass
`--substring` to match within tokens.

Offline runnable example using the bundled Linear A corpus:

```bash
aegean db build lineara -o lineara.db        # wrote 1721 documents to lineara.db
aegean db search lineara.db KU-RO --limit 3
#  'KU-RO' in lineara.db
#  ┌───────┬─────┬───────┐
#  │ doc   │ pos │ text  │
#  ├───────┼─────┼───────┤
#  │ HT9a  │ 25  │ KU-RO │
#  │ HT9b  │ 20  │ KU-RO │
#  │ HT11a │ 7   │ KU-RO │
#  └───────┴─────┴───────┘
```

### Appending to an existing database: `db add`

`aegean db add` upserts additional documents into an existing `.db` file
(replacing matching IDs, inserting new ones, and updating FTS rows):

```bash
aegean db build tlg0012.tlg001 -o homer.db   # start with the Iliad
aegean db add  tlg0012.tlg002 -o homer.db    # added/updated 24 documents in homer.db
```

In Python, pass `append=True` to `to_sql()`:

```python
from aegean import greek

greek.load_work("tlg0012.tlg001").to_sql("homer.db")
greek.load_work("tlg0012.tlg002").to_sql("homer.db", append=True)
```

### Subsetting a corpus: `Corpus.subset()`

`Corpus.subset(ids)` creates a smaller `Corpus` containing only the requested
document IDs and appends a `subset: N of M documents by id` note to provenance:

```python
from aegean import greek

iliad = greek.load_work("tlg0012.tlg001")
books_1_3 = iliad.subset([f"tlg0012.tlg001:{n}" for n in (1, 2, 3)])
len(books_1_3)                       # 3
books_1_3.provenance.notes[-1]       # '...subset: 3 of 24 documents by id'
books_1_3.to_sql("iliad_opening.db")
```

> Query results can also be saved directly as corpora:
> `aegean query lineara --where word-prefix=KU -o ku_words.db` writes matching
> documents to a `.json` or `.db` file ready for `db search` or `combine`. See
> [CLI](CLI).

---

## 6. The Greek New Testament and Biblical texts: `aegean.greek.bible`

> For multi-edition comparison, early manuscript witnesses, Extended Strong's
> root trees, Septuagint (LXX) search, Psalm conversion, and patristic
> commentaries, see [New Testament](New-Testament) and
> [CLI: Biblical & Koine Greek](CLI-Bible).

`bible.load_nt(...)` loads the Greek New Testament as a standard `Corpus` with
one `Document` per chapter. The default edition (`nestle1904`) carries gold
annotations on every token: `lemma`, Robinson `morph`, `strongs`, reconciled UD
`upos`, `normalized`, `ref`, and a brief `gloss`. Eight additional critical and
traditional editions (`sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`,
`antoniades`, `tr`) are selectable via `edition=`.

John 1 and Philemon 1 (Nestle 1904) are bundled inside the package for offline
use; all other books and editions fetch to cache on first use.

### Loading a book, chapter, verse, or range

`ref` uses **chapter.verse** notation:

| `ref` | Selects |
|-------|---------|
| `"3"` | chapter 3 |
| `"3.16"` | chapter 3, verse 16 |
| `"3.16-3.18"` | verses 3:16–3:18 |
| `"3.16-18"` | verses 3:16–3:18 (shorthand) |
| `"3-5"` | chapters 3 through 5 |

Offline example using bundled Philemon:

```python
from aegean.greek import bible

corpus = bible.load_nt("Philemon", ref="1.1-1.3")   # offline: bundled book
len(corpus)                          # 1 (one Document per chapter)
doc = corpus.documents[0]
doc.id                               # 'Phlm 1'
doc.meta.name                        # 'Philemon 1'
len(doc.tokens)                      # 41

t = doc.tokens[0]
t.text                               # 'Παῦλος'
t.annotations
# {'lemma': 'Παῦλος', 'morph': 'N-NSM', 'strongs': '3972',
#  'normalized': 'Παῦλος', 'upos': 'NOUN', 'ref': 'Phlm.1.1', 'gloss': 'Paul'}
```

Tabular view in pandas:

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

Additional forms:

```python
from aegean.greek import bible

bible.load_nt("John")                          # whole Gospel of John (Nestle 1904)
bible.load_nt("John", ref="1.1-18")            # John 1:1-18
bible.load_nt("John", ref="1.18", edition="sblgnt")  # SBLGNT edition
bible.load_nt("Rom", ref="8")                  # Romans chapter 8
bible.load_nt()                                # all 27 NT books
bible.load_lxx("Gen", ref="1.1-5", offline=True)     # Swete Septuagint (LXX)
bible.load_witness("P66", "John", "1.1-5")     # early NT manuscript witness
```

Signature: `bible.load_nt(book=None, ref=None, *, edition="nestle1904",
offline=False, force=False)`. Passing `ref` without `book` raises `ValueError`.
Unavailable chapters or out-of-range endpoints raise an error instead of
returning a truncated passage, and `corpus.cite()` records the canonical book
and exact loaded extent.

### Per-token annotation fields (Nestle 1904)

| Field | Meaning |
|-------|---------|
| `lemma` | Dictionary headword (gold, from Nestle 1904) |
| `morph` | Robinson morphology tag, e.g. `N-NSM`, `V-PAI-3S` |
| `strongs` | Strong's number (e.g. `3972` = Paul) |
| `upos` | Coarse UD POS reconciled from `morph` |
| `normalized` | Accent/diacritic-normalized form |
| `ref` | Canonical token address, e.g. `Phlm.1.1` |
| `gloss` | Brief English gloss (bundled Dodson lexicon, when available) |

The Robinson-to-UPOS converter can be called directly:

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

## 7. NT and LXX book names

`bible.nt_books()` returns all 27 New Testament books in canonical order with
the aliases accepted by `bible.load_nt()` and `aegean bible read` (bundled
metadata, no network call):

```python
from aegean.greek import bible

books = bible.nt_books()
len(books)         # 27
books[3]           # {'name': 'John', 'aliases': ['john', 'jn', 'jhn']}
```

Matching is case-insensitive and ignores spaces and periods (`"1 Cor"`, `"1cor"`,
`"1Cor."` all resolve to `1Cor`). Document IDs always use the canonical `name`.

From the shell:

```bash
aegean bible books nt          # 27 NT books and accepted aliases
aegean bible books lxx         # 55 Swete Septuagint books
aegean bible books nt --json   # JSON output
```

### New Testament book table

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

Passing a non-NT book name to `bible.load_nt()` raises `ValueError` with a
suggestion; for Septuagint books such as Genesis or Psalms, call
`bible.load_lxx("Gen")` (or `aegean bible read Gen 1:1-5`, which auto-detects
LXX books).

> For standalone Strong's lookups and word studies, use
> `aegean bible strongs ἀγάπη` / `bible.strongs_entry(...)` and
> `bible.word_study(...)`, documented in
> [CLI: Biblical & Koine Greek](CLI-Bible) and [New Testament](New-Testament).

---

## 8. Analyzing loaded works

Because `greek.load_work()` and `bible.load_nt()` return standard `Corpus`
objects, all Greek NLP functions apply directly:

```python
from aegean import greek

corpus = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")
line = " ".join(t.text for t in corpus.documents[0].tokens if t.line_no == 0)
line                                  # 'μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος'

greek.scan_hexameter(line).pattern    # scan as dactylic hexameter
greek.syllabify("Ἀχιλῆος")            # syllabify an individual word
```

See [Greek NLP](Greek-NLP) for syllabification, accentuation, metrical scansion,
tagging, lemmatization, and dependency parsing.

---

## 9. Reproducibility and provenance

Fetched works are pinned to fixed upstream commits or SHA-256-verified release
assets, recorded on `corpus.provenance`:

```python
corpus = greek.load_work("tlg0012.tlg001", ref="1")
corpus.provenance.data_version   # 'PerseusDL/canonical-greekLit@d4fab69a2c26'
corpus.provenance.license        # 'CC BY-SA 4.0 (Perseus Digital Library)'
```

| Collection | Repository / asset | Licence |
|------------|--------------------|---------|
| canonical-greekLit | `PerseusDL/canonical-greekLit` | CC BY-SA 4.0 (Perseus Digital Library) |
| First1KGreek | `OpenGreekAndLatin/First1KGreek` | CC BY-SA 4.0 (Open Greek and Latin) |
| New Testament (Nestle 1904) | `biblicalhumanities/Nestle1904` | CC0 (morphology/lemmas/Strong's); base text public domain |

Environment variables override upstream pins or authenticate GitHub API
requests during large-scale discovery:

| Variable | Effect |
|----------|--------|
| `PYAEGEAN_GREEKLIT_REF` | Override the pinned `canonical-greekLit` commit |
| `PYAEGEAN_FIRST1K_REF` | Override the pinned `First1KGreek` commit |
| `PYAEGEAN_NT_CORPUS_URL` | Point `bible.load_nt()` at an alternate NT corpus asset |
| `PYAEGEAN_GITHUB_TOKEN` / `GITHUB_TOKEN` | Authenticate first-time work discovery (unauthenticated GitHub API limit is 60 req/hour) |

Classical TEI files are fetched directly from upstream into the local cache
rather than bundled or re-hosted. The full NT is a separately hosted asset, with
John 1 and Philemon 1 bundled offline. See
[Data & Provenance](Data-and-Provenance) for full details.

---

## 10. Limitations and notes

- **Network on first fetch.** Uncached works require network access once and
  read from cache offline afterward. The bundled NT sample (John 1 and Philemon
  1) and LXX sample (Genesis 1:1–5 and LXX Psalm 22:1–6) work offline
  immediately.
- **Varying TEI hierarchies.** `ref` follows each edition's declared `<div>` and
  `<l>` structure. A `ref` incompatible with the edition's scheme raises a
  `ValueError` naming that scheme.
- **Shortlist vs. full catalogue.** `popular_works()` lists 25 entries; search
  all 1,778 loadable works via `catalog()` / `aegean greek catalog`
  ([§3](#3-finding-any-other-work)), or browse the
  [Scaife Viewer](https://scaife.perseus.org).
- **Edition line numbering.** Verse `<l>` lines filter on numeric `n`
  attributes; unnumbered or non-numeric lines do not match numeric ranges.
- **Gold Nestle 1904 annotations.** Nestle 1904 annotations are fixed edition
  gold (Robinson morphology), independent of pyaegean's taggers.

For broader scope notes, see [Limitations](Limitations).

---

## See also

- [Greek NLP](Greek-NLP): NLP stages applicable to any loaded work
- [New Testament](New-Testament): full `aegean.greek.bible` guide (9 editions, witnesses, Strong's, LXX, commentaries)
- [CLI: Greek NLP & Review](CLI-Greek) and [CLI: Biblical & Koine Greek](CLI-Bible)
- [Tutorial](Tutorial): guided end-to-end walkthrough loading the *Iliad*
- [Data & Provenance](Data-and-Provenance): caches, licences, and pinned commits
- [Limitations](Limitations): scope and known gaps
