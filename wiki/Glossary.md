# Glossary

A plain-language dictionary of the terms you'll meet across this documentation:
the scripts, the linguistics, the file formats, and the source projects. Each
entry is one or two sentences, with a runnable example where pyaegean actually
does the thing, and a link to the page that covers it in depth. If you've ever
hit a word like *lemmatize*, *scansion*, *ideogram*, or *EpiDoc* and weren't sure
what it meant here, this is the page to keep open.

> New to the toolkit entirely? Start with [Getting Started](Getting-Started). For
> the full command reference see the [CLI](CLI) page; for every Greek function see
> [Greek NLP](Greek-NLP).

The examples below were run against pyaegean 0.46.0 (the `aegean` command-line tool
and the `aegean` Python package). Where a feature has both a Python call and a
shell command, both are shown.

---

## The scripts at a glance

pyaegean knows five writing systems. Four are Aegean scripts; the fifth is the
Greek alphabet itself. You can list them at any time:

```python
import aegean
aegean.registered_scripts()
# ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

| Script id | Human name | Status | Where it's covered |
|---|---|---|---|
| `lineara` | Linear A | **Undeciphered** | [Linear A](Linear-A) |
| `linearb` | Linear B | Deciphered (Mycenaean Greek) | [Linear B](Linear-B) |
| `cypriot` | Cypriot syllabary | Deciphered (Arcadocypriot Greek) | [Cypriot](Cypriot) |
| `cyprominoan` | Cypro-Minoan | **Undeciphered** | [Cypro-Minoan](Cypro-Minoan) |
| `greek` | Greek alphabet |— | [Greek NLP](Greek-NLP) |

---

## Scripts and decipherment

### Linear A
The Bronze Age script of Minoan Crete (roughly 1800–1450 BCE), used for the
still-**undeciphered** Minoan language. pyaegean ships the full GORILA-derived
Linear A corpus offline (1,721 documents, a 342-sign inventory). See [Linear A](Linear-A).

```bash
aegean info lineara
# documents: 1721 · words: 1381 · signs_in_inventory: 342
# source: GORILA (Godart & Olivier 1976–1985)
```

### Linear B
The script Linear A evolved into, used at Knossos, Pylos, and elsewhere to write an
early form of **Greek** (Mycenaean). Famously deciphered by Michael Ventris in
1952, which is why pyaegean can *read* Linear B words as Greek (see the **bridge**
entry below). See [Linear B](Linear-B).

### Cypriot syllabary
An Iron Age syllabary used on Cyprus to write a Greek dialect (Arcadocypriot), and
also the unrelated Eteocypriot language. Deciphered in the 1870s. See [Cypriot](Cypriot).

### Cypro-Minoan
A cluster of **undeciphered** scripts used on Bronze Age Cyprus, descended from (or
cousins of) Linear A. pyaegean carries an illustrative sample plus the 99-sign
Unicode inventory, not a full transcribed corpus. See [Cypro-Minoan](Cypro-Minoan)
and [Limitations](Limitations).

---

## How these scripts work (the writing-system terms)

### Syllabary
A writing system where each sign stands for a whole **syllable** (like `da`, `ku`,
`pa`) rather than a single consonant or vowel the way an alphabet does. Linear A,
Linear B, the Cypriot syllabary, and Cypro-Minoan are all syllabaries.

### Syllabogram
A single syllabary sign: one glyph carrying one syllable's worth of sound. You can
look one up in any script's inventory:

```bash
aegean sign linearb DA --json
# { "label": "DA", "glyph": "𐀅", "phonetic": "da",
#   "attrs": { "signClass": "syllabogram", ... } }
```

```bash
aegean sign cypriot PA --json
# { "label": "PA", "glyph": "𐠞", "phonetic": "pa",
#   "attrs": { "signClass": "syllabogram" } }
```

### Ideogram / Logogram
A sign that stands for a **thing or commodity** (a word or idea) rather than a
sound: think of the picture-sign for "wine," "oil," or "sheep" on an accounting
tablet. The two terms are used interchangeably here. In a parsed Linear A document
these are kept separate from the spelled-out words:

```python
import aegean
doc = next(d for d in aegean.load("lineara").iter_documents() if d.logograms)
doc.id                                  # 'HT2'
[t.text for t in doc.logograms][:5]     # ['OLE+U', 'OLE+A', 'OLE+E', 'OLE+U', 'OLE+A']
#                                          OLE = the olive-oil ideogram
```

### Sign value vs. sound value
A sign's **value** is its identity in the inventory: its label (`DA`, `AB01`), its
glyph, and its Unicode codepoint. Its **sound value** (the `phonetic` field above)
is the syllable it's read as *where that's known*. For undeciphered scripts the sign
value is solid but the sound value is provisional or absent; that distinction
matters a lot; see [Limitations](Limitations).

### Numeral
Aegean tablets carry numbers (quantities of a commodity) alongside words and
ideograms. pyaegean keeps these as their own token kind so a count never gets
mistaken for a word:

```python
doc = next(aegean.load("lineara").iter_documents())   # HT1
[t.text for t in doc.numerals][:4]                    # ['197', '70', '52', '109']
```

---

## Reading deciphered scripts as Greek

### Bridge (Greek-reading bridge)
For the **deciphered** syllabaries (Linear B and Cypriot), the bridge takes a
transliterated word and gives you its attested Greek reading and meaning: the
payoff of decipherment, in one call.

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)

aegean bridge cypriot pa-si-le-u-se
# pa-si-le-u-se → βασιλεύς   (king)
```

If a word has no attested reading in the bundled lexicon, the bridge says so
plainly rather than guessing. Covered on [Linear B](Linear-B) and [Cypriot](Cypriot).

---

## Greek text terms

### Beta Code
A way to type polytonic Greek using only plain ASCII keys: `lo/gos` for `λόγος`,
`mh=nin` for `μῆνιν`: so you never need a Greek keyboard. pyaegean converts both
directions.

```python
from aegean import greek
greek.betacode_to_unicode("mh=nin")     # 'μῆνιν'
greek.unicode_to_betacode("μῆνιν")      # 'mh=nin'
```

```bash
aegean greek betacode "mh=nin"          # μῆνιν
aegean greek betacode "μῆνιν" --reverse # mh=nin
```

### Normalization
Putting Greek text into one canonical Unicode form (so two visually identical words
compare equal), optionally repairing OCR/Beta-Code artifacts with `--lenient`. See
[Greek NLP](Greek-NLP#normalization--beta-code).

### Diacritics / strip
Diacritics are the accents, breathings, and subscripts on Greek letters. "Stripping"
removes them, useful for loose matching:

```python
greek.strip_diacritics("μῆνιν")         # 'μηνιν'
```

### Token
The smallest unit a text is cut into: usually a word or a punctuation mark. In a
syllabic corpus a token is one word, ideogram, or numeral; in Greek it's a word or
mark. (See **tokenize** on the [Greek NLP](Greek-NLP) page.)

### Syllabify / syllabification
Splitting a Greek word into its spoken syllables, using rules plus a curated
exception lexicon for compounds.

```python
greek.syllabify("ἄνθρωπος")             # ['ἄν', 'θρω', 'πος']
```

### Accentuation
Where a Greek word's accent falls and what that pattern is called (oxytone,
paroxytone, proparoxytone, and so on).

```python
greek.accentuation("λόγος").classification    # 'paroxytone'
```

### IPA
The International Phonetic Alphabet: a reconstructed pronunciation written in
standard phonetic symbols.

```python
greek.to_ipa("λόγος")                   # 'loɡos'
```

---

## Linguistic annotation

### Lemma
The dictionary headword for an inflected form: the entry you'd look up. `λόγοι`
("words") and `λόγος` ("word") share the lemma `λόγος`.

### Lemmatization
The act of reducing each word to its lemma. With no extra backends installed
pyaegean uses a bundled seed table plus a generalizing rule layer that strips the
regular second-declension and thematic-verb endings back to the citation form;
the opt-in neural pipeline is far more accurate (see [Greek NLP](Greek-NLP)).

```python
greek.lemmatize("λόγοι")                # 'λόγος'
```

```bash
aegean greek lemmatize "λόγοι"
```

### UPOS (part of speech)
A word's grammatical category: noun, verb, adjective, tagged with the
**Universal Dependencies** coarse tag set (UPOS = Universal POS).

```python
greek.pos_tag("θεός")                              # 'NOUN'
greek.pos_tags("θεὸς ἀγαθός")
# [('θεὸς', 'NOUN'), ('ἀγαθός', 'NOUN')]
```

### Morphology
The full grammatical breakdown of a word form: case, number, gender, tense, voice,
mood, person, degree, often with more than one candidate parse:

```python
greek.analyze("λόγοι")[0]
# Analysis(lemma='λόγος', pos='NOUN', case='nom', number='pl', gender='masc', ...)
```

```bash
aegean greek morph "λόγοι"
```

### Treebank / AGDT
A **treebank** is a corpus where every sentence is annotated with its grammatical
**tree** (which word depends on which). **AGDT** is the *Ancient Greek Dependency
Treebank* (from the Perseus project), pyaegean's main source of gold parses,
glosses, and the lexicon that the opt-in Greek backends are trained from. See
[Greek NLP](Greek-NLP) and [Data & Provenance](Data-and-Provenance).

### Parse (dependency parse)
Working out the grammatical structure of a sentence: which word is the subject,
which the object, and so on, as a tree of relations. pyaegean can emit UD relations
(with the neural parser) or AGDT-style relations. See [Greek NLP](Greek-NLP).

### Pipeline
The one-call convenience that runs normalize → tokenize → tag → lemmatize → morph in
sequence and hands you one record per token. See [Greek NLP](Greek-NLP).

### Gloss
A short dictionary meaning for a word. pyaegean has two sources: a Koine (New
Testament) gloss from the bundled Dodson lexicon that works **offline**, and a fuller
LSJ gloss that fetches a prebuilt ~15 MB index on first use.

```bash
aegean greek gloss-nt λόγος
# a word, speech, divine utterance, analogy
```

---

## Metre (scansion)

### Scansion / metre
Working out the rhythm of a line of verse: marking each syllable **heavy** (long,
`—`) or **light** (short, `⏑`) and matching the pattern to a known metre.

```python
greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic
```

### Quantity (heavy / light / common)
The "weight" of a single syllable: **heavy** (long), **light** (short), or
**common** (can be either). This is the raw material scansion is built from.

```bash
aegean greek quantities "μῆνιν"
# μῆνιν → μῆ:heavy | νιν:heavy
```

The metres pyaegean can scan (the `--meter` option of `aegean greek scan`):

| Meter name | What it is |
|---|---|
| `hexameter` | Dactylic hexameter (epic verse: Homer, Hesiod) |
| `pentameter` | Elegiac pentameter (paired with hexameter in elegiac couplets) |
| `trimeter` | Iambic trimeter (the spoken line of drama) |
| `glyconic` | Aeolic lyric line (fixed template) |
| `pherecratean` | Aeolic lyric line |
| `sapphic_hendecasyllable` | Aeolic lyric line |
| `adonean` | Aeolic lyric line |
| `alcaic_hendecasyllable` | Aeolic lyric line |
| `alcaic_enneasyllable` | Aeolic lyric line |
| `alcaic_decasyllable` | Aeolic lyric line |

> Scansion is conservative: a line that only scans via *synizesis* (two vowels read as
> one) on a word outside the curated lexicon is reported as not scanning, rather than
> the tool guessing. See [Greek NLP](Greek-NLP) and [Limitations](Limitations).

---

## Corpus structure

### Corpus
A whole collection of documents in one script: what you get back from
`aegean.load(...)`. It knows its size, its provenance, and how to filter and export.

```python
corpus = aegean.load("lineara")
len(corpus)                             # 1721
```

### Document
One inscription, tablet, or text within a corpus — with an id, its lines, and its
tokens (words, ideograms, numerals).

```python
doc = next(aegean.load("lineara").iter_documents())
doc.id                                  # 'HT1'
doc.words[0].text                       # 'QE-RA₂-U'
```

### Catalogue (Greek works)
The bundled, offline discovery index of every Greek work pyaegean can fetch: 1,778
works that have a Greek edition in the Perseus canonical-greekLit and First1KGreek
collections, each with its `id`, author, English and Greek title, and source. It is
pure metadata, so searching it needs no network; anything it lists, `load_work` can
load. (Distinct from `popular_works()`, the curated 25-work short list.)

```python
from aegean import greek
len(greek.catalog())                    # 1778
greek.catalog(title="Ἰλιάς")            # search by Greek title
# [{'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad',
#   'greek_title': 'Ἰλιάς', 'source': 'perseus'}]
```

```bash
aegean greek catalog --author plato     # 39 matches
```

See [Greek Works and Books](Greek-Works-and-Books#3-finding-any-other-work).

---

## File formats and source projects

| Term | What it is | More |
|---|---|---|
| **GORILA** | *Recueil des inscriptions en linéaire A* (Godart & Olivier 1976–1985): the standard Linear A edition; pyaegean's bundled Linear A corpus is derived from it. | [Linear A](Linear-A), [Data & Provenance](Data-and-Provenance) |
| **DAMOS** | *Database of Mycenaean at Oslo*: a Linear B corpus (~5,900 tablets) with scribal hands, find context, and object class; fetched on demand. | [Linear B](Linear-B), [Data & Provenance](Data-and-Provenance) |
| **SigLA** | The *Signs of Linear A* database (Salgarella & Castellan): a Linear A dataset (802 documents) with its own word division and commodity ideograms; fetched on demand. | [Linear A](Linear-A), [Data & Provenance](Data-and-Provenance) |
| **Greek inscription corpora** | I.Sicily, IIP, IOSPE, IGCyr/GVCyr, and the EDH Greek subset: openly-licensed EpiDoc databases of Greek inscriptions (2,855 / 2,113 / 1,194 / 997 / 1,286 texts), each fetched on demand with per-token editorial reading status. | [Data & Provenance](Data-and-Provenance), [Using Critical Editions](Using-Critical-Editions) |
| **DDbDP** | The *Duke Databank of Documentary Papyri* (papyri.info): 57,331 Greek documentary papyri, hosted as a SQLite database with full-text search; fetched on demand. | [Data & Provenance](Data-and-Provenance) |
| **AGDT** | *Ancient Greek Dependency Treebank* (Perseus): gold grammatical annotation behind the Greek backends. | [Greek NLP](Greek-NLP) |
| **EpiDoc** | A community standard (a flavour of TEI XML) for encoding ancient inscriptions; pyaegean can **export** a corpus to EpiDoc TEI. | [CLI](CLI), [Data & Provenance](Data-and-Provenance) |
| **Pleiades** | The open gazetteer of ancient places; pyaegean tags located sites with their Pleiades id where one exists. | [Geography](Geography) |

```bash
aegean geo lineara
# site            lat    lon    pleiades
# Apodoulou       35.16  24.73  119143959
# Gournia         35.11  25.79  771100776
# Haghia Triada   35.06  24.79  589672
# ...  (52 located sites)
```

You can export to EpiDoc TEI (and other formats) from the [CLI](CLI). EpiDoc export
writes one TEI file per document, so point `--output` at a directory:

```bash
aegean export lineara --format epidoc --output lineara_tei/   # one file per doc
```

---

## Stance and method

### Exploratory
A label this project uses for anything generative or speculative, most of all the
[AI Layer](AI-Layer). An exploratory result is **evidence for a human expert to
weigh, never a reading or a translation presented as fact**. Every AI command is
marked exploratory for exactly this reason:

```bash
aegean ai --help
# Generative (exploratory, key-gated): translate, gloss, summarize, hypotheses, ask, ...
```

### Grounding
The factual material a generative answer is tied to: the local lexicon, the
transliteration, the corpus context, so the model is reasoning *from the evidence*
rather than free-associating. The `aegean ai ask` command answers **strictly from
the provided grounding**; the AI layer translates by grounding first, then calling a
model. See [AI Layer](AI-Layer).

---

## Notes and limitations

- **Undeciphered means undeciphered.** Linear A and Cypro-Minoan have solid *sign*
  values but no agreed *language*; nothing here "translates" them, and the AI layer's
  hypotheses are explicitly speculative.
- **Sound values are provisional** for undeciphered scripts, and even for deciphered
  ones the bridge only returns *attested* readings: it won't invent one.
- **Cypriot ships the 178-inscription IG XV 1 corpus** (CC BY 4.0) plus a couple of
  illustrative samples; **Cypro-Minoan is an illustrative sample only** (undeciphered).
  Neither is the complete transcribed corpus, but both sign inventories are full.
- **The richer Greek backends and gold datasets are opt-in downloads**, not bundled:
  the core install works offline.

For the full, honest list of what pyaegean does and does not claim, read
[Limitations](Limitations).
