# Glossary

Short definitions of the scripts, linguistic concepts, file formats, and source
projects referenced across the pyaegean wiki, with runnable examples and links
to detailed pages.

> New to pyaegean? Start with [Getting Started](Getting-Started). For commands
> see [CLI](CLI); for Greek functions see [Greek NLP](Greek-NLP).

Examples below use the `aegean` Python package and the `aegean` CLI (`[cli]`
extra).

---

## Supported scripts

pyaegean supports five writing systems: four Aegean syllabic scripts and the
Greek alphabet. List them with:

```python
import aegean
aegean.registered_scripts()
# ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

| Script ID | Name | Status | Documentation |
| --- | --- | --- | --- |
| `lineara` | Linear A | **Undeciphered** | [Linear A](Linear-A) |
| `linearb` | Linear B | Deciphered (Mycenaean Greek) | [Linear B](Linear-B) |
| `cypriot` | Cypriot syllabary | Deciphered (Arcadocypriot Greek) | [Cypriot](Cypriot) |
| `cyprominoan` | Cypro-Minoan | **Undeciphered** | [Cypro-Minoan](Cypro-Minoan) |
| `greek` | Greek alphabet | Attested alphabetic tradition | [Greek NLP](Greek-NLP) |

---

## Scripts and decipherment

### Linear A
Bronze Age script of Minoan Crete (c. 1800–1450 BCE) recording an
**undeciphered** language. pyaegean bundles a GORILA-derived Linear A corpus
offline (1,721 documents, 342-sign inventory). See [Linear A](Linear-A).

```bash
aegean info lineara
# documents: 1721 · words: 1381 · signs_in_inventory: 342
# source: GORILA (Godart & Olivier 1976–1985)
```

### Linear B
Descendant of Linear A used at Knossos, Pylos, Mycenae, and other Bronze Age
palaces to write Mycenaean Greek. Deciphered by Michael Ventris in 1952;
pyaegean provides transliteration and a Greek-reading bridge. See
[Linear B](Linear-B).

### Cypriot syllabary
Iron Age syllabary of Cyprus used primarily for Arcadocypriot Greek, alongside
Eteocypriot and undetermined inscriptions. Deciphered in the 1870s. pyaegean
bundles the 178-inscription IG XV 1 corpus plus two samples (180 documents).
See [Cypriot](Cypriot).

### Cypro-Minoan
Cluster of **undeciphered** Bronze Age scripts from Cyprus related to Linear A.
pyaegean bundles the 99-sign Unicode inventory and an illustrative sample. See
[Cypro-Minoan](Cypro-Minoan) and [Limitations](Limitations).

---

## Writing-system terms

### Syllabary
A writing system in which each phonetic sign represents a syllable (`da`, `ku`,
`pa`) instead of a single consonant or vowel. Linear A, Linear B, Cypriot, and
Cypro-Minoan are syllabaries.

### Syllabogram
A single phonetic sign in a syllabary. Look up signs in any script inventory:

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
A sign standing for a commodity, object, or concept (for example, wine, olive
oil, or livestock on an accounting tablet) rather than a phonetic syllable. The
two terms are used interchangeably in pyaegean. Parsed Aegean documents keep
logograms separate from spelled words:

```python
import aegean
doc = next(d for d in aegean.load("lineara").iter_documents() if d.logograms)
doc.id                                  # 'HT2'
[t.text for t in doc.logograms][:5]     # ['OLE+U', 'OLE+A', 'OLE+E', 'OLE+U', 'OLE+A']
#                                          OLE = olive-oil ideogram
```

### Sign value vs. sound value
A sign's **value** is its inventory identity: label (`DA`, `AB01`), glyph, and
Unicode code point. Its **sound value** (`phonetic` field) is the spoken
syllable assigned to it where established. For undeciphered scripts, sign
identities are established while sound values are conventional (borrowed from
Linear B) or absent; keep the two distinct when analyzing undeciphered texts.
See [Limitations](Limitations).

### Numeral
Numeric quantity on an inscription or tablet. pyaegean stores numerals as their
own token kind so counts remain distinct from words:

```python
doc = next(aegean.load("lineara").iter_documents())   # HT1
[t.text for t in doc.numerals][:4]                    # ['197', '70', '52', '109']
```

---

## Reading deciphered scripts as Greek

### Bridge (Greek-reading bridge)
For the deciphered syllabaries (Linear B and Cypriot), the bridge maps a
transliterated word to its attested Greek reading and gloss:

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)

aegean bridge cypriot pa-si-le-u-se
# pa-si-le-u-se → βασιλεύς   (king)
```

If a word has no attested entry in the bundled lexicon, the bridge reports that
no reading is attested. See [Linear B](Linear-B) and [Cypriot](Cypriot).

---

## Greek text terms

### Beta Code
ASCII transliteration for polytonic Greek (`lo/gos` → `λόγος`, `mh=nin` →
`μῆνιν`), allowing Greek input without a Greek keyboard. pyaegean converts in
both directions:

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
Converting Greek text into canonical NFC Unicode form so visually identical
strings compare equal, with optional `--lenient` repair of OCR and encoding
artifacts. See [Greek NLP → Normalization](Greek-NLP#normalization--beta-code).

### Diacritics / strip
Accents, breathings, and iota subscripts on Greek letters. Stripping removes
diacritics for accent-insensitive matching:

```python
greek.strip_diacritics("μῆνιν")         # 'μηνιν'
```

### Token
Smallest unit emitted by tokenization: a word, ideogram, or numeral in Aegean
corpora; a word, punctuation mark, numeral, or foreign span in Greek. See
[Greek NLP](Greek-NLP).

### Syllabify / syllabification
Dividing a Greek word into spoken syllables using phonological rules and a
compound-word exception lexicon:

```python
greek.syllabify("ἄνθρωπος")             # ['ἄν', 'θρω', 'πος']
```

### Accentuation
Position and classification of a Greek word's accent (oxytone, paroxytone,
proparoxytone, perispomenon, properispomenon):

```python
greek.accentuation("λόγος").classification    # 'paroxytone'
```

### IPA
International Phonetic Alphabet transcription of reconstructed Ancient Greek
pronunciation (Attic or Koine):

```python
greek.to_ipa("λόγος")                   # 'loɡos'
```

---

## Linguistic annotation

### Lemma
Dictionary headword for an inflected form. `λόγοι` ("words") and `λόγος`
("word") share the lemma `λόγος`.

### Lemmatization
Reducing inflected forms to their dictionary headwords. The offline baseline
combines a bundled seed table with suffix rules for regular paradigms; opt-in
treebank and neural backends substantially increase coverage and accuracy (see
[Greek NLP](Greek-NLP)).

```python
greek.lemmatize("λόγοι")                # 'λόγος'
```

```bash
aegean greek lemmatize "λόγοι"
```

### UPOS (part of speech)
Coarse grammatical category (noun, verb, adjective, etc.) using the **Universal
Dependencies** POS tagset:

```python
greek.pos_tag("θεός")                              # 'NOUN'
greek.pos_tags("θεὸς ἀγαθός")
# [('θεὸς', 'NOUN'), ('ἀγαθός', 'NOUN')]
```

### Morphology
Grammatical feature breakdown of a word form (case, number, gender, tense,
voice, mood, person, degree), returning candidate analyses when a form is
ambiguous:

```python
greek.analyze("λόγοι")[0]
# Analysis(lemma='λόγος', pos='NOUN', case='nom', number='pl', gender='masc', ...)
```

```bash
aegean greek morph "λόγοι"
```

### Treebank / AGDT
A **treebank** is a corpus annotated with sentence-level grammatical trees.
**AGDT** (*Ancient Greek Dependency Treebank*, Perseus) supplies the gold
parses and lexicon used by pyaegean's opt-in treebank and trained backends. See
[Greek NLP](Greek-NLP) and [Data & Provenance](Data-and-Provenance).

### Parse (dependency parse)
Directed syntactic tree linking each token to its head with a grammatical
relation (subject, object, modifier, etc.). pyaegean outputs Universal
Dependencies relations under the neural pipeline and AGDT-style relations under
the pure-Python parser. See [Greek NLP](Greek-NLP).

### Pipeline
Single call running normalization, tokenization, POS tagging, lemmatization,
morphology, and (when enabled) dependency parsing, returning one `TokenRecord`
per token. See [Greek NLP](Greek-NLP).

### Gloss
Short dictionary definition for a Greek lemma. pyaegean bundles the Koine
Dodson lexicon offline and fetches five additional prebuilt dictionary indexes
on demand (LSJ, Middle Liddell, Cunliffe, Autenrieth, and Abbott-Smith) via the
dictionary registry, alongside Extended Strong's in `aegean.greek.bible`:

```bash
aegean greek gloss λόγος -d dodson
# λόγος: a word, speech, divine utterance, analogy

aegean bible strongs λόγος
# G3056  λόγος  logos  G:N-M
#   Gloss: word
#   Definition: ...
```

---

## Metre (scansion)

### Scansion / metre
Determining the rhythmic pattern of a verse line by marking each syllable
**heavy** (long, `—`) or **light** (short, `⏑`) and matching it to a metrical
scheme:

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
Metrical weight of an individual syllable: **heavy** (long), **light** (short),
or **common** (scanning as either):

```bash
aegean greek quantities "μῆνιν"
# μῆνιν → μῆ:heavy | νιν:heavy
```

Metres accepted by `--meter` on `aegean greek scan`:

| Meter name | Description |
| --- | --- |
| `hexameter` | Dactylic hexameter (Homer, Hesiod) |
| `pentameter` | Elegiac pentameter |
| `trimeter` | Iambic trimeter (tragedy and comedy) |
| `glyconic` | Fixed-template Aeolic lyric line |
| `pherecratean` | Fixed-template Aeolic lyric line |
| `sapphic_hendecasyllable` | Fixed-template Aeolic lyric line |
| `adonean` | Fixed-template Aeolic lyric line |
| `alcaic_hendecasyllable` | Fixed-template Aeolic lyric line |
| `alcaic_enneasyllable` | Fixed-template Aeolic lyric line |
| `alcaic_decasyllable` | Fixed-template Aeolic lyric line |

> Scansion applies synizesis (two vowels scanned as one syllable) only for
> entries in its curated lexicon; lines requiring unlisted synizesis are
> reported as unscanned. See [Greek NLP](Greek-NLP) and
> [Limitations](Limitations).

---

## Corpus structure

### Corpus
Collection of documents in one script returned by `aegean.load(...)` or
`aegean.open(...)`, carrying document count, provenance, filtering, querying,
and export methods:

```python
corpus = aegean.load("lineara")
len(corpus)                             # 1721
```

### Document
Single inscription, tablet, or literary passage inside a corpus, holding an ID,
metadata, lines, and typed tokens (words, ideograms, numerals, punctuation):

```python
doc = next(aegean.load("lineara").iter_documents())
doc.id                                  # 'HT1'
doc.words[0].text                       # 'QE-RA₂-U'
```

### Catalogue (Greek works)
Bundled offline metadata index of all 1,778 Greek editions available from
Perseus *canonical-greekLit* and *First1KGreek*, searchable by `id`, author,
English or Greek title, and source. Every returned ID loads with
`greek.load_work`. Distinct from `popular_works()`, which lists 25 curated
titles.

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

See [Greek Works & Books](Greek-Works-and-Books#3-finding-any-other-work).

---

## File formats, archives, and source projects

| Term | Definition | Reference |
| --- | --- | --- |
| **GORILA** | *Recueil des inscriptions en linéaire A* (Godart & Olivier 1976–1985): standard Linear A edition behind pyaegean's bundled Linear A corpus. | [Linear A](Linear-A), [Data & Provenance](Data-and-Provenance) |
| **DAMOS** | *Database of Mycenaean at Oslo*: ~5,900 Linear B tablets with scribal hands, find contexts, and object classes; fetched on demand. | [Linear B](Linear-B), [Data & Provenance](Data-and-Provenance) |
| **SigLA** | *Signs of Linear A* database (Salgarella & Castellan): 802 Linear A documents with sign-level annotations and commodity ideograms; fetched on demand. | [Linear A](Linear-A), [Data & Provenance](Data-and-Provenance) |
| **Greek inscription corpora** | Seven openly licensed EpiDoc databases fetched on demand with per-token editorial reading status: I.Sicily (2,855), IIP (2,113), IOSPE (1,194), IGCyr/GVCyr (997), Aphrodisias / IAph2007 (1,471), Crete (600), and EDH Greek subset (1,286). | [Data & Provenance](Data-and-Provenance), [Using Critical Editions](Using-Critical-Editions) |
| **DDbDP** | *Duke Databank of Documentary Papyri* (papyri.info): 57,331 Greek documentary papyri in an on-demand SQLite FTS database. | [Data & Provenance](Data-and-Provenance) |
| **AGDT** | *Ancient Greek Dependency Treebank* (Perseus): gold grammatical annotations behind the Greek treebank and trained backends. | [Greek NLP](Greek-NLP) |
| **EpiDoc** | TEI XML schema for ancient inscriptions; pyaegean imports and exports EpiDoc TEI while preserving supported editorial reading statuses and typed forms. | [CLI](CLI), [Data & Provenance](Data-and-Provenance) |
| **Research bundle (`aegean.bundle`)** | Deterministic, SHA-256-verified `.zip` archive (`aegean bundle create\|inspect\|verify\|extract\|hydrate`) packaging redistributable corpora (or retrieval pointers for NC-licensed datasets), citations, workbench state, editable review tables, and analysis receipts. | [Data & Provenance](Data-and-Provenance), [CLI](CLI) |
| **Workbench (`workbench-app-v2.1.0`)** | Local multi-script browser UI for Linear A, Linear B, Cypriot, and Cypro-Minoan served via `aegean workbench --corpus` and interoperable with `aegean.io.to_workbench_bundle`. | [CLI](CLI), [Linear A](Linear-A) |
| **Pleiades** | Open gazetteer of ancient places; pyaegean attaches Pleiades IDs to aligned Aegean sites where available. | [Geography](Geography) |

```bash
aegean geo lineara
# lineara: 52 located site(s) of 52
# site            lat    lon    pleiades   contested
# Apodoulou       35.16  24.73  119143959
# Arkhalkhori     35.15  25.3   220781958
# Gournia         35.11  25.79  771100776
# Haghia Triada   35.06  24.79  589672
# ...
```

Sites without a Pleiades ID leave that cell blank. The `contested` column reads
`disputed` for find-spots carried in the record but not accepted as genuine
(here Margiana) and is blank elsewhere.

EpiDoc export writes one TEI XML file per document, so pass a directory path to
`--output`:

```bash
aegean export lineara --format epidoc --output lineara_tei/   # one file per doc
```

---

## Stance and method

### Exploratory
Marker attached to generative or speculative outputs, including all [AI Layer](AI-Layer)
commands and undeciphered-script hypotheses. Exploratory outputs require human
evaluation and are distinct from attested readings or verified translations:

```bash
aegean ai --help
# Generative (exploratory; API key per hosted provider, none for local):
# translate, gloss, summarize, hypotheses, ask, extract, eval, providers.
```

### Grounding
Local evidence supplied alongside a generative prompt (lexicon entries,
transliteration, corpus context) so model output is tied to verifiable inputs.
`aegean ai ask` answers strictly from the provided grounding; translation
commands build local grounding before calling a model. See [AI Layer](AI-Layer).

---

## Notes and limitations

- **Linear A and Cypro-Minoan are undeciphered.** Sign identities are
  established, while the underlying languages are unknown; pyaegean does not
  translate them, and AI hypotheses are explicitly speculative.
- **Sound values are provisional** for undeciphered scripts. Even for
  deciphered scripts (Linear B, Cypriot), the bridge returns only attested
  readings.
- **Cypriot bundles 178 IG XV 1 inscriptions** (CC BY 4.0) plus two samples;
  **Cypro-Minoan bundles an illustrative sample only**. Both scripts include
  complete Unicode sign inventories.
- **Opt-in Greek backends and hosted datasets download on demand** into the
  local cache (`aegean library` / `aegean data`); the core install runs
  offline.

For the full scope and limits of each module, read [Limitations](Limitations).
