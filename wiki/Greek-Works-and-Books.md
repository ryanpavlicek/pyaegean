# Greek Works and Books

This page is the reference for **loading real Greek texts** into pyaegean: the
classical literary corpus (Homer, Plato, Herodotus…) and the Greek New Testament.
You'd come here when you want to stop typing Greek by hand and instead pull a whole
work (or a single book, chapter, or line-range) straight into a `Corpus` you can
tokenize, scan, tag, and count.

Two doors lead in:

- **`greek.load_work("tlg0012.tlg001")`**: any work in the Perseus
  canonical-greekLit / First1KGreek collections, addressed by a **CTS id** (the
  `tlgAAAA.tlgBBB` scheme explained below).
- **`greek.load_nt("John")`**: the Greek New Testament (Nestle 1904), with a gold
  lemma, morphology, Strong's number, and a gloss already attached to every word.

Both fetch their text once to a local cache and then work offline, and both return
the same standard `Corpus` object you get everywhere else in pyaegean. Once a work
is loaded, everything on [Greek NLP](Greek-NLP) applies to it.

> **A work id works everywhere now.** As of 0.8.2 you can hand a Greek work id
> straight to almost any `aegean` command: no Python required. `aegean stats
> tlg0012.tlg001`, `aegean export tlg0012.tlg002 -f csv -o odyssey.csv`, and
> `aegean db build tlg0012.tlg001 -o iliad.db` all resolve the id through
> `load_work` for you. Anywhere a command takes a `CORPUS` argument it now accepts
> a registered id (`lineara`, `nt`, …), a Greek work id (`tlg0012.tlg001`), a path
> to a saved `.json`/`.db` corpus, or `-` for JSON on stdin. [§5](#5-put-works-into-a-database)
> below puts that to work.

> New to all this? Start with [Getting Started](Getting-Started), then the
> [Tutorial](Tutorial): it walks through loading the Iliad end to end. For the
> command-line forms, see [CLI](CLI); for the licences and cache details, see
> [Data & Provenance](Data-and-Provenance).

---

## 1. The `tlgAAAA.tlgBBB` work-id scheme, in plain language

Every classical Greek work has a stable catalogue address. pyaegean uses the same
one the scholarly world uses: the **CTS** ("Canonical Text Services") id, so the
id you find in a citation or in the Scaife Viewer is exactly the id you paste here.

A work id has two halves joined by a dot:

```
tlg0012 . tlg001
└──┬──┘   └──┬──┘
 author     work
 group     within
           that author
```

- The **first half** (`tlg0012`) names the **author / text group**: Homer.
- The **second half** (`tlg001`) names **one work** by that author: `tlg001` is
  the Iliad, `tlg002` is the Odyssey.

So `tlg0012.tlg001` is read as "Homer, work 1 = the Iliad." The numbers are
arbitrary catalogue numbers, not anything you'd guess: you look them up. The
`tlg` prefix comes from the *Thesaurus Linguae Graecae*, whose numbering this
scheme inherits. (A few First1KGreek works use a `stoa` prefix instead of `tlg`;
the dotted shape is the same.)

You never have to memorise these. The next two sections show how to **list the
common ones** (built in) and **find any other** (one website).

> The dot matters. `load_work` splits on it: the part before the dot is the author
> directory, the part after is the work file. Pass something without a dot and you
> get a clear error telling you the expected shape (`tlgGROUP.tlgWORK`).

---

## 2. The built-in catalogue — `popular_works()`

pyaegean ships a small, **hand-verified** catalogue of well-known works so you can
discover ids without leaving Python. Every id below was confirmed to resolve
against the live source. It's a *starting point*, not the whole canon (see
[§3](#3-finding-any-other-work) for everything else).

### Python

```python
from aegean import greek

works = greek.popular_works()
len(works)            # 25
works[0]              # {'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'}
```

`popular_works()` is **pure metadata: no download**, so it works offline and is
instant. Each entry is a plain dict with `id`, `author`, and `title`.

### CLI

```bash
aegean greek works
```

…prints the same catalogue as a table and a copy-paste hint:

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

Add `--json` for machine-readable output: `aegean greek works --json`.

### The full catalogue (id → author → title)

This is the complete list, pulled from the live `popular_works()` function:

| id | author | title |
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

Notice the pattern: works by one author share the first half of the id. All four
Sophocles plays are `tlg0011.tlg00x`; all four Plato dialogues here are
`tlg0059.tlg0xx`. That's the `tlgAAAA` group at work.

This is the curated short list. To search the **full** 1,778-work discovery index
in-package, use `catalog()` / `aegean greek catalog`: see
[§3](#3-finding-any-other-work).

---

## 3. Finding any other work

`load_work` accepts **any** Perseus canonical-greekLit / First1KGreek CTS id, not
just the 25 above. There are two ways to find an id: a built-in search, and the
official web browser.

### The built-in catalogue — `catalog()` / `aegean greek catalog`

pyaegean bundles a **complete discovery index** of every work that has a Greek
(`-grc`) edition in those two collections: **1,778 works** (768 from Perseus
canonical-greekLit, 1,010 from First1KGreek), far more than the 25 highlights in
`popular_works()`. It is pure bundled metadata (id, author, English title, Greek
title, source), so searching it needs **no network** and is instant. Anything it
lists, `load_work` can fetch.

`catalog(query=None, *, author=None, title=None, source=None)` returns a list of
dicts, each with `id`, `author`, `title`, `greek_title`, and `source`. The filters
combine (all must match); `query` is free-text across id, author, and either title.

```python
from aegean import greek

len(greek.catalog())                       # 1778   (768 perseus + 1010 first1k)
len(greek.catalog(author="plato"))         # 39     — every Plato work in the open repos
greek.catalog(title="Ἀντιγόνη")            # search by Greek title too
# → [{'id': 'tlg0011.tlg002', 'author': 'Sophocles', 'title': 'Antigone',
#     'greek_title': 'Ἀντιγόνη', 'source': 'perseus'}]
len(greek.catalog("herodotus"))            # 2      — free-text across id/author/title
len(greek.catalog(source="first1k"))       # 1010   — limit to one collection

greek.catalog()[0]
# → {'id': 'tlg0001.tlg001', 'author': 'Apollonius Rhodius',
#    'title': 'Argonautica', 'greek_title': 'Argonautica', 'source': 'perseus'}
```

From the shell, `aegean greek catalog [QUERY]` mirrors it (`--author`/`-a`,
`--title`/`-t`, `--source`, `--limit`/`-n` rows to show, `--output`/`-o` to save,
`--json`):

```bash
aegean greek catalog --author plato        # filter by author (39 matches)
aegean greek catalog sappho                # free-text query (a no-match is reported plainly)
aegean greek catalog --author homer -o homer_works.csv   # wrote 49 works to homer_works.csv
```

A query with no matches reports it plainly rather than printing an empty table:

```bash
aegean greek catalog sappho
# No works match. Try a looser filter, or browse https://scaife.perseus.org
```

(`sappho` returns nothing because Sappho's Greek text isn't openly digitized in
either collection: see the coverage note below.)

> **The catalogue is honest about coverage.** It lists exactly what these open
> repositories actually hold at the pinned commit, not the entire theoretical
> canon. Some authors whose Greek text isn't openly digitized there (e.g. Sappho)
> simply won't appear; that's the same set `load_work` can reach, no surprises.

### The Scaife Viewer (the web browser for these collections)

For the canonical web view (or to confirm an edition) use Scaife:

1. Go to the **Scaife Viewer**: **<https://scaife.perseus.org>**. This is the
   official browser for these exact collections.
2. Search for your author or work and open it.
3. Read the CTS id out of the URL or the work's citation. A Scaife URN looks like
   `urn:cts:greekLit:tlg0012.tlg001.perseus-grc2`: the `tlg0012.tlg001` middle is
   the id you pass to `load_work` (drop the `urn:cts:greekLit:` prefix and the
   trailing edition label).

That's it: there's no separate registry to install. If you pass an id that can't
be found in either collection, you get an actionable error rather than a silent
empty result:

```python
greek.load_work("tlg9999.tlg999")
# aegean.data.DataNotAvailableError: could not fetch 'tlg9999.tlg999' (...).
# Works are addressed as 'tlgGROUP.tlgWORK', e.g. tlg0012.tlg001 (Iliad).
```

### Picking the edition and the source

Some works exist in more than one digital edition, and a few exist in both
collections. Two optional arguments let you steer:

| argument | values | what it does |
|----------|--------|--------------|
| `source` | `"auto"` (default), `"perseus"`, `"first1k"` | which collection to search. `"auto"` tries Perseus first, then First1KGreek. |
| `edition` | a full filename, or a fragment like `"perseus-grc2"` | pin a specific edition file when a work has several; otherwise the highest-numbered `-grc*` Greek edition wins. |

```python
# force the First1KGreek copy, and a specific edition file fragment
greek.load_work("tlg0086.tlg005", source="first1k", edition="1st1K-grc1")
```

---

## 4. Loading a work and addressing parts of it (`ref`)

### Whole work

With no `ref`, you get the whole work as **one `Document` per top-level part**: a
book of the Iliad, a chapter run of a prose work.

```python
from aegean import greek

corpus = greek.load_work("tlg0012.tlg001")   # network on first use, then cached
len(corpus)                                   # 24   (the 24 books of the Iliad)
corpus.documents[0].id                        # 'tlg0012.tlg001:1'
corpus.documents[0].meta.name                 # 'Ἰλιάς — Book 1'
sum(len(d.tokens) for d in corpus)            # 127339
```

### Selecting a section with `ref`

`ref` is a **citation address** that matches the work's own structure. The shape
mirrors how classicists cite: book, then chapter or line, separated by dots, with
an optional range after a hyphen.

| `ref` | meaning | example work |
|-------|---------|--------------|
| `"1"` | one top-level part (a book) | Iliad book 1 |
| `"1.2"` | a nested division (book 1, chapter 2) | Herodotus 1.2 |
| `"1.1-1.50"` | a verse line-range across two full addresses | Iliad book 1, lines 1–50 |
| `"1.1-50"` | the same range, shorthand (the hi end inherits the lo prefix) | Iliad book 1, lines 1–50 |

A worked, **verified** example (the opening of the Iliad):

```python
from aegean import greek

corpus = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")
len(corpus)                          # 1   (one Document for the selected range)
doc = corpus.documents[0]
doc.id                               # 'tlg0012.tlg001:1.1-1.10'
doc.meta.name                        # 'Ἰλιάς — 1.1-1.10'
len(doc.lines)                       # 10
# first verse, joined back to text:
" ".join(t.text for t in doc.tokens if t.line_no == 0)
# 'μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος'
```

For a prose work, the middle component is a chapter rather than a verse line:

```python
greek.load_work("tlg0016.tlg001", ref="1.2")   # Herodotus, book 1, chapter 2
```

### Citation schemes: how a work is addressed

A `ref` is only meaningful against the work's **declared citation scheme** — the ordered
levels the edition names in its TEI `<refsDecl>`. pyaegean reads that scheme straight from
each edition (no author-specific guessing), so the shape of a `ref` differs by genre. The
patterns below are typical; the authority is always the edition's own structure, which is
why the levels are read, not assumed:

| genre | scheme (levels) | a `ref` looks like | verified example |
|-------|-----------------|--------------------|------------------|
| epic / elegy (verse) | `book.line` | `1`, `1.1`, `1.1-1.50` | Iliad → `['book', 'line']` |
| drama | `line` | `1`, `1-50` | Antigone, Medea → `['line']` |
| Plato (Stephanus-paged) | `section` | `17` | Apology, Crito → `['section']` |
| Aristotle | `chapter.subchapter` | `1`, `1.2` | Poetics → `['chapter', 'subchapter']` (Aristotle varies: the Nicomachean Ethics is `['book', 'section']`) |
| multi-book prose | `book.chapter.section` | `1`, `1.2`, `1.2.3` | Herodotus, Xenophon's Anabasis → `['book', 'chapter', 'section']` |

Discover a work's scheme before loading with `greek.citation_scheme(id)`, which returns the
ordered levels exactly as the edition declares them (fetches the TEI once, like `load_work`):

```python
greek.citation_scheme("tlg0012.tlg001")   # ['book', 'line']   (Homer, Iliad)
greek.citation_scheme("tlg0059.tlg002")   # ['section']        (Plato, Apology)
greek.citation_scheme("tlg0032.tlg006")   # ['book', 'chapter', 'section']  (Xenophon, Anabasis)
```

Because the scheme is read from the edition, a `ref` that resolves nowhere reports the
work's **own** scheme rather than only that the ref missed (`… cited by book.line`), so the
error tells you how to address the work. Two rules follow from the scheme: a hyphen
**range** must stay inside one top-level part (`1.1-1.50` is fine; `1.1-2.50`, which crosses
from book 1 into book 2, is rejected — load each book and `Corpus.merge`, or use a comma
list), and a **comma list** (`1.1,1.5` or `1,3`) selects siblings, or ranges that would
cross a textpart, as one `Document` each, in source order.

Some editions print finer references in the margin, in TEI `<milestone>` markers that live
**outside** the CTS `<div>` scheme — a Stephanus sub-page (`17a`) or a Bekker line (`1447a10`,
column `a` of page `1447`, line `10`). `--ref` now addresses these too: it extracts the span
between the named marker and the next marker of its kind, so `aegean greek work tlg0086.tlg034
--ref 1447a10` (the *Poetics*) returns the run from line 10 up to the next marked line.
Perseus marks only every fifth Bekker line, so `1447a10` yields lines 10-14 and only the
marked line numbers are addressable: `1447a11`-`1447a14` resolve to nothing. A whole Bekker
page-*column* resolves the same way (`1447a` = column `a` of page 1447); the whole physical
page is its two columns as a **comma list** (`1447a,1447b`), and milestone refs may appear
in any comma list (`17a,17b`), one `Document` each. A hyphen **range** of milestones is
**not yet** supported — only a single milestone ref is addressable; a range falls through to
the scheme-naming error, so use a comma list of the individual markers instead.

### The same thing on the command line

```bash
# list the well-known ids first if you need one
aegean greek works

# then load a section
aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

Output (verified, from cache):

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

`aegean greek work` flags:

| flag | meaning | default |
|------|---------|---------|
| `WORK_ID` (argument) | the CTS id, e.g. `tlg0012.tlg001` | required |
| `--ref` | section to select: `1`, `1.2`, `1.1-1.50` | whole work |
| `--source` | `auto`, `perseus`, or `first1k` | `auto` |
| `--edition` | pick a specific edition file | best `-grc*` |
| `--output` / `-o` | write the corpus to a JSON file | print summary |
| `--json` | machine-readable summary on stdout | table |

Save a whole work to disk to reuse without re-fetching:

```bash
aegean greek work tlg0012.tlg001 -o iliad.json   # wrote 24 documents to iliad.json
```

### Fetch a whole author, and manage the downloads

`all` in place of a work id bulk-fetches every catalogued work by an author
(case-insensitive), skipping anything already cached, so an interrupted run
resumes where it stopped:

```bash
aegean greek work all homer --dry-run    # preview what would be fetched
aegean greek work all homer --yes        # fetch it; --limit N caps new downloads
```

`aegean greek works --downloaded` lists the works already fetched to your local
cache, and `--remove <id>`, `--remove-author <name>`, or `--remove-all` delete
downloaded works you no longer need. The Python equivalents are
`greek.fetch_works`, `greek.list_fetched_works()`, and
`greek.remove_fetched_works(...)`.

### Notes carried along

Editorial `<note>` and `<bibl>` material is **not dropped and not mixed into the
running text**: it rides along in `doc.meta.notes` so the text you analyse is clean
while the apparatus stays available.

---

## 5. Put works into a database

Loading a work re-parses its cached TEI every run. For anything you'll come back
to (searching it, joining it with another work, sharing it) write it once into a
**SQLite database** and read from that. The database carries the documents and their
tokens, plus an FTS5 full-text index, so searches are instant and need no network.

The key change in 0.8.2 is that `aegean db build` (and `combine`, `stats`, `export`,
…: anything taking a `CORPUS`) accepts a **Greek work id directly**, so you can do
all of this without writing a line of Python.

### One work → one database

```bash
aegean db build tlg0012.tlg001 -o iliad.db
# fetches/parses the Iliad once, then:  wrote 24 documents to iliad.db
```

`tlg0012.tlg001` is resolved through `load_work` for you (network on first use, then
the cache). Add `--no-fts` to skip the full-text index if you only want the raw
tables.

The Python equivalent: load it yourself, then save:

```python
from aegean import greek
greek.load_work("tlg0012.tlg001").to_sql("iliad.db")   # fts=True by default
```

### All of Homer in one database — `combine`

`aegean combine` merges several corpora into a single saved corpus. Each source is
resolved like any other corpus argument, so two work ids become one database:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db
# wrote 48 documents to homer.db (merged 2 sources)
```

That's the Iliad (24 books) and the Odyssey (24 books), all of Homer, in one
file. Write `-o homer.json` instead for a portable JSON corpus rather than a
database. The merged corpus's provenance names **every** source it was built from,
so the trail back to Perseus stays intact.

If two sources share a document id, `--on-conflict` decides what happens:
`error` (the default, refuse and tell you), `first`, `last`, or `suffix` (keep both,
disambiguating the later id):

```bash
aegean combine a.json b.json -o merged.db --on-conflict last
```

The same thing in Python: `combine([...])`, or `Corpus.merge(*others)`:

```python
from aegean import greek, combine

iliad   = greek.load_work("tlg0012.tlg001")
odyssey = greek.load_work("tlg0012.tlg002")

homer = combine([iliad, odyssey])          # dedupe="error" by default
len(homer)                                  # 48
homer.provenance.source                     # 'Merged corpus (aegean.combine)'
homer.to_sql("homer.db")

# equivalently, from one corpus:
homer = iliad.merge(odyssey, dedupe="error")
```

### Search the database — `db search`

Once it's a database, full-text search is one command and needs no network. It
prints the document, the token position, and the matched text:

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

`μῆνιν`: "wrath", the very first word of the Iliad. Add `--limit N` to cap hits
(default 50) or `--json` for machine-readable output. The query matches a whole token
literally (so `KU-RO` finds the token `KU-RO`, never `PO-TO-KU-RO`); pass `--substring`
to match within tokens instead.

(Here it is on a small offline corpus, so you can run it yourself end to end:)

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

### Grow an existing database — `db add`

To extend a database you've already built (say you started with the Iliad and now
want the Odyssey in the same file) `db add` **upserts** the new source: documents
whose id already exists are replaced, new ids are added, and the FTS index is
refreshed.

```bash
aegean db build tlg0012.tlg001 -o homer.db   # start with the Iliad
aegean db add  tlg0012.tlg002 -o homer.db    # added/updated 24 documents in homer.db
```

The source can be a work id, a registered corpus id, a `.json`/`.db` file, or `-`.
In Python it's the `append=True` flag on either saver:

```python
from aegean import greek

greek.load_work("tlg0012.tlg001").to_sql("homer.db")              # build
greek.load_work("tlg0012.tlg002").to_sql("homer.db", append=True) # upsert in
```

### Taking just part of a corpus — `subset`

`Corpus.subset(ids)` returns a new corpus with only the documents you name: handy
before saving or combining. It records a `subset: N of M documents by id` note in
the provenance so the slice stays honest:

```python
from aegean import greek

iliad = greek.load_work("tlg0012.tlg001")
books_1_3 = iliad.subset([f"tlg0012.tlg001:{n}" for n in (1, 2, 3)])
len(books_1_3)                       # 3
books_1_3.provenance.notes[-1]       # '...subset: 3 of 24 documents by id'
books_1_3.to_sql("iliad_opening.db")
```

> **The reverse direction, too.** A `query` over the inscription corpora can save
> its matches as a reusable corpus: `aegean query lineara --where word-prefix=KU
> -o ku_words.db` writes the matched inscriptions as a `.json`/`.db` you can then
> `db search` or `combine`. See [CLI](CLI) for the full query language.

---

## 6. The Greek New Testament — `load_nt()`

> See the dedicated [New Testament](New-Testament) page for the full NT tooling.

`greek.load_nt(...)` is the Koine counterpart to `load_work`. It returns a `Corpus`
of the Greek NT (Nestle 1904) where **every token already carries gold
annotations**: a `lemma`, a Robinson-style `morph` parse, a `strongs` number, a
reconciled UD `upos`, the `normalized` form, and (where available) a short `gloss`.
You don't have to run a tagger: it's all there.

The offline sample ships **inside the package** (John 1 and the one-chapter
Philemon), so `load_nt("Philemon")` and `load_nt("John", ref="1")` work
**fully offline**; everything else fetches to cache on first use.

### Loading a book, chapter, verse, or range

`ref` works just like `load_work`'s, but reads as **chapter.verse**:

| `ref` | selects |
|-------|---------|
| `"3"` | chapter 3 |
| `"3.16"` | chapter 3, verse 16 |
| `"3.16-3.18"` | verses 3:16–3:18 |
| `"3.16-18"` | the same range, shorthand |
| `"3-5"` | chapters 3 through 5 |

A complete, **verified, offline** example (Philemon is part of the bundled sample):

```python
from aegean import greek

corpus = greek.load_nt("Philemon", ref="1.1-1.3")   # no network: bundled book
len(corpus)                          # 1   (one Document per chapter)
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

Turn the per-token annotations into a table (every field becomes a column):

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

Other forms:

```python
greek.load_nt("John")                 # whole Gospel of John  (fetches on first use)
greek.load_nt("John", ref="1.1-18")   # John 1:1–18
greek.load_nt("Rom", ref="8")         # Romans chapter 8
greek.load_nt()                       # the whole 27-book NT
```

`load_nt(book=None, *, ref=None, force=False)`: `force=True` re-fetches even if
cached; passing a `ref` without a `book` raises (you can't address a verse across
all 27 books).

### Per-token annotation fields

| field | what it is |
|-------|------------|
| `lemma` | dictionary headword (gold, from Nestle 1904) |
| `morph` | Robinson-style morphology tag, e.g. `N-NSM`, `V-PAI-3S` |
| `strongs` | Strong's number (e.g. `3972` = Paul) |
| `upos` | coarse Universal Dependencies POS, reconciled from `morph` |
| `normalized` | accent/diacritic-normalized form |
| `ref` | canonical address of the token, e.g. `Phlm.1.1` |
| `gloss` | brief English gloss (bundled Dodson lexicon, when available) |

The Robinson→UPOS mapping that fills `upos` is exposed if you want it directly:

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

## 7. The 27 books and the names you can use

`nt_books()` lists every book in canonical order together with the abbreviations
`load_nt` (and `gloss-nt`) will accept for it. It's **pure metadata: no download**.

```python
from aegean import greek
books = greek.nt_books()
len(books)         # 27
books[3]           # {'name': 'John', 'aliases': ['john', 'jn', 'jhn']}
```

Any of the canonical `name` **or** any alias is accepted (case-insensitive; spaces
and dots are ignored: `"1 Cor"`, `"1cor"`, `"1Cor."` all resolve to `1Cor`). The
`name` is what shows up in document ids.

On the command line:

```bash
aegean greek nt-books          # the table below
aegean greek nt-books --json   # same data as JSON
```

### The full book table

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

An unrecognised name gives a helpful error:

```python
greek.load_nt("Genesis")
# ValueError: unknown NT book 'Genesis' — did you mean 'Eph'? (greek.nt_books()
# lists all 27)
```

(Genesis is in the Hebrew Bible, not the Greek NT: `load_nt` covers the 27 NT
books only.)

> Looking up a single word's Koine gloss without loading a book? That's
> `aegean greek gloss-nt` / `greek.lookup_nt(...)`, documented on
> [Greek NLP](Greek-NLP): it uses the bundled Dodson lexicon and needs no download.

---

## 8. What you can do once a work is loaded

Both loaders return a standard `Corpus`, so the rest of the toolkit just works:

```python
from aegean import greek

corpus = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")
line = " ".join(t.text for t in corpus.documents[0].tokens if t.line_no == 0)
line                                  # 'μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος'

greek.scan_hexameter(line).pattern    # scan it as dactylic hexameter
greek.syllabify("Ἀχιλῆος")            # syllabify a word from it
```

See [Greek NLP](Greek-NLP) for syllabification, accentuation, metrical scansion,
tagging, lemmatization, and parsing; every one of those applies to a loaded work.

---

## 9. Reproducibility and provenance

Each fetched work is **pinned to a specific upstream commit**, so the same id gives
you the same text tomorrow. The commit is recorded on the corpus:

```python
corpus = greek.load_work("tlg0012.tlg001", ref="1")
corpus.provenance.data_version   # 'PerseusDL/canonical-greekLit@d4fab69a2c26'
corpus.provenance.license        # 'CC BY-SA 4.0 (Perseus Digital Library)'
```

| collection | repository | licence |
|------------|-----------|---------|
| canonical-greekLit | `PerseusDL/canonical-greekLit` | CC BY-SA 4.0 (Perseus Digital Library) |
| First1KGreek | `OpenGreekAndLatin/First1KGreek` | CC BY-SA 4.0 (Open Greek and Latin) |
| New Testament | `biblicalhumanities/Nestle1904` | CC0 (morphology/lemmas/Strong's); base text public domain |

Environment variables let you track a newer upstream state or authenticate
large-scale discovery:

| variable | effect |
|----------|--------|
| `PYAEGEAN_GREEKLIT_REF` | override the pinned canonical-greekLit commit |
| `PYAEGEAN_FIRST1K_REF` | override the pinned First1KGreek commit |
| `PYAEGEAN_NT_CORPUS_URL` | point `load_nt` at an alternate NT corpus asset |
| `PYAEGEAN_GITHUB_TOKEN` / `GITHUB_TOKEN` | authenticate first-time work discovery (the GitHub contents API is rate-limited to 60 req/hour unauthenticated) |

Files are fetched to your cache, **never bundled or re-hosted** (except the offline
NT sample: John 1 and Philemon). Full details are on [Data & Provenance](Data-and-Provenance).

---

## 10. Limitations and honest notes

- **First use of a non-cached work needs the network.** After that it's read from
  the local cache and works offline. The one exception that's offline from the
  start is the bundled NT sample (John 1 and Philemon).
- **TEI structures vary.** `ref` follows each work's own `<div>` nesting and `<l>`
  line numbering. A `ref` that doesn't match the work's structure raises a clear
  `ValueError` rather than guessing.
- **`popular_works()` is a curated subset, not the canon.** 25 entries for quick
  discovery; the full 1,778-work discovery index is `catalog()` / `aegean greek
  catalog` ([§3](#3-finding-any-other-work)), the web browser is the
  [Scaife Viewer](https://scaife.perseus.org), and any valid id loads.
- **Line numbering is the edition's, not invented.** Verse `<l>` lines are filtered
  by their numeric `n`; non-numeric or unnumbered lines won't match a numeric range.
- **NT annotations are gold and fixed** (Nestle 1904 morphology), independent of
  pyaegean's own taggers: useful as a benchmark as well as a corpus.

For the broader picture of what is and isn't in scope, see [Limitations](Limitations).

---

## See also

- [Greek NLP](Greek-NLP): everything you can run on a loaded work
- [CLI](CLI): the `aegean greek work` / `works` / `nt-books` commands
- [Tutorial](Tutorial): a guided, end-to-end load of the Iliad
- [Data & Provenance](Data-and-Provenance): caches, licences, pinned commits
- [Limitations](Limitations): scope and known gaps
