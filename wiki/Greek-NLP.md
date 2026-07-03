# Greek NLP

`aegean.greek` is the Ancient Greek NLP pipeline: a chain of small, independent
steps that take you from raw text to syllables, metre, morphology, parses, and
glosses. You would reach for it to type Greek without a Greek keyboard (Beta
Code), break words into syllables, scan a line of verse, tag and lemmatize a
passage, look words up in a dictionary, or load and analyse a real Greek work or
the Greek New Testament.

Each stage is a plain function you can call on its own, and you can chain them
into your own pipeline, **or** call `pipeline()` once and get every field at
once. The core runs **fully offline with no API key and zero third-party
dependencies**; the opt-in treebank, LSJ, tagger, lemmatizer, parser, and
neural-pipeline backends fetch their data over the network on first use, then
cache it.

Everything below is available **two ways**: a Python function and an
`aegean greek …` CLI subcommand. Every example here is real, runnable output.
Import the module once for the Python side:

```python
from aegean import greek
```

The CLI lives behind one extra (`pip install "pyaegean[cli]"`) and every command
takes `--json` for machine-readable output. See the [CLI](CLI) page for the rest
of the shell tooling, [Getting Started](Getting-Started) if you are new to
Python, [Meters](Meters) for the metrical scansion in depth, and
[Greek Works and Books](Greek-Works-and-Books) for the corpus loaders.

> **Where this fits.** The zero-dependency core optimizes for portability, an instant
> import, transparent leakage-free evaluation, metrical scansion, and a scriptable data
> layer. For maximum accuracy, the opt-in **[neural pipeline](#the-neural-pipeline-opt-in)**
> (`use_neural_pipeline`, the `[neural]` extra) is **state of the art on the UD Ancient
> Greek (Perseus) benchmark**: measured end-to-end through this package (the full protocol and
> comparison tables live in
> [`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md)).

## The stages at a glance

Every stage is callable on its own; the CLI mirrors each one. The opt-in
backends layer in extra accuracy without changing the call you make.

| Stage | Python | CLI | Network? |
| --- | --- | --- | --- |
| Beta Code ↔ Unicode | `betacode_to_unicode` / `unicode_to_betacode` | `aegean greek betacode` | no |
| Normalize (NFC, OCR repair) | `normalize` | `aegean greek normalize` | no |
| Strip diacritics | `strip_diacritics` | `aegean greek strip` | no |
| Tokenize / sentences | `tokenize` / `tokenize_words` / `sentences` | `aegean greek tokenize` | no |
| Syllabify | `syllabify` | `aegean greek syllabify` | no |
| Accent analysis | `accentuation` | `aegean greek accent` | no |
| Accent placement | `place_accent` / `recessive_accent` / `persistent_accent` | `aegean greek accentuate` | no |
| Resolve sandhi | `resolve_sandhi` / `resolve_sentence` | `aegean greek sandhi` | no |
| Prosody (quantities) | `syllable_quantities` / `scan` | `aegean greek quantities` | no |
| Metrical scansion | `scan_hexameter` / `scan_line` / … | `aegean greek scan` | no |
| Reconstructed IPA | `to_ipa` | `aegean greek ipa` | no |
| POS tag | `pos_tag` / `pos_tags` | `aegean greek tag` | opt-in backends |
| Lemmatize | `lemmatize` | `aegean greek lemmatize` | opt-in backends |
| Morphology | `analyze` / `lemmas` / `best_pos` | `aegean greek morph` | opt-in treebank |
| Inflection synthesis | `inflect` / `paradigm` | `aegean greek inflect` | opt-in treebank |
| Dependency parse | `parse` | `aegean greek parse` | opt-in backends |
| LSJ gloss | `gloss` / `lookup` | `aegean greek gloss` | yes (first use) |
| Dialect / register | `usage` | `aegean greek usage` | yes (LSJ) |
| Terminology rarity | `terminology_rarity` | `aegean greek rarity` | reference corpus |
| Koine (NT) gloss | `gloss_nt` / `gloss_strongs` / `lookup_nt` | `aegean greek gloss-nt` | no (bundled) |
| One-call pipeline | `pipeline` | `aegean greek pipeline` | opt-in backends |
| Load a real work | `load_work` | `aegean greek work` | yes (first use) |
| Load the Greek NT | `load_nt` |— | no for one book; yes for the rest |
| Discover works / books | `popular_works` / `catalog` / `nt_books` | `aegean greek works` / `catalog` / `nt-books` | no |
| Import your own text | `io.from_text` / `from_text_file` / `from_csv` / … | `aegean import` | no |
| Reproduce the numbers | `evaluate_on_ud` / `evaluate_on_proiel` / … | `aegean greek eval` | yes (gold data) |

## One call: `pipeline()`

Every stage below is independently callable, but you don't have to compose them:
`pipeline` runs tokenize → sentence split → POS-tag → lemmatize (→ parse) over a
text and returns one record per token (punctuation included: nothing is dropped):

```python
records = greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")
[(r.text, r.upos, r.lemma) for r in records]
# [('ἐν','ADP','ἐν'), ('ἀρχῇ','NOUN','ἀρχή'), ('ἦν','VERB','εἰμί'),
#  ('ὁ','DET','ὁ'), ('λόγος','NOUN','λόγος'), ('.','PUNCT','.')]
```

The same from the shell renders a table (and `--json` gives the records):

```bash
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος."
#  s   i   token   upos    lemma   head   rel   feats
#  0   1   ἐν      ADP     ἐν
#  0   2   ἀρχῇ    NOUN    ἀρχή
#  0   3   ἦν      VERB    εἰμί
#  0   4   ὁ       DET     ὁ
#  0   5   λόγος   NOUN    λόγος
#  0   6   .       PUNCT   .
```

Each `TokenRecord` is a dataclass with these fields:

| Field | Meaning |
| --- | --- |
| `sentence` | 0-based sentence index |
| `index` | 1-based token index within the sentence |
| `text` | the surface token (punctuation included) |
| `upos` | UD coarse part of speech |
| `lemma` | the lemma |
| `lemma_known` | whether the lemma was a real lookup vs an identity fallback |
| `head` | head token index (only when parsed) |
| `relation` | dependency relation (only when parsed) |
| `xpos` | language-specific tag (neural pipeline only) |
| `feats` | UD FEATS string (neural pipeline only) |

`pipeline` uses whatever backends are **active**: with none, the zero-dependency
baseline; after `use_treebank()`/`use_tagger()` etc., their better answers; after
`use_neural_pipeline()`, one model pass fills every field of every record.
`parse=True` (CLI `--parse`) without the neural pipeline requires `use_parser()`
(CLI `--parser`). The CLI flags `--treebank`, `--tagger`, `--lemmatizer`,
`--neural-lemmatizer`, and `--neural` turn the matching backend on for that run.

## The neural pipeline (opt-in)

One jointly-trained model: a GreBerta encoder with tagging heads, a biaffine dependency
parser decoded by a single-root MST (non-projectivity handled natively), and an
edit-script lemmatizer: serving **UPOS, full morphology (UD FEATS), UD dependency
trees, and lemmas** from a single forward pass. Trained leakage-clean on the AGDT +
Gorman + Pedalion treebanks (1.41M tokens, with the evaluation folds' sentences excluded
from training).

```bash
pip install "pyaegean[neural]"     # onnxruntime + tokenizers + numpy; no torch
```

```python
greek.use_neural_pipeline()        # fetches the model bundle (~173 MB, one-time) to the cache

ana = greek.analyze_sentence(["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"])
list(zip(ana.tokens, ana.upos, ana.deprel, ana.lemma))
# [('ἐν','ADP','case','ἐν'), ('ἀρχῇ','NOUN','root','ἀρχή'), ('ἦν','VERB','cop','εἰμί'),
#  ('ὁ','DET','det','ὁ'), ('λόγος','NOUN','nsubj','λόγος')]
ana.feats[1]                       # 'Case=Dat|Gender=Fem|Number=Sing'
```

Once active, the standard functions use it: `pos_tags`/`pos_tag`, `lemmatize`, and
`parse`: which then returns **UD relations** (`nsubj`, `obj`, `advcl`, …) with the
predicted 9-character morphological tag on each token. `disable_neural_pipeline()`
restores the cascades above. From the shell, add `--neural` to `tag`, `lemmatize`,
`parse`, `pipeline`, or `eval` to use it for that command (the `[neural]` extra is
required either way).

**Measured: UD Ancient Greek test folds, official CoNLL 2018 evaluator, through the
shipped package, end-to-end from raw text** (tokens F1 99.97):

| UD Perseus test | UPOS | UFeats | Lemma | UAS | LAS |
| --- | --- | --- | --- | --- | --- |
| neural pipeline | **97.0** | **96.0** | **94.3** | **90.2** | **85.6** |

Out-of-domain (UD PROIEL test, a source no pyaegean model trains on): lemma 90.50,
UAS 82.47, UPOS 86.71. Inference is torch-free, at roughly 20–70 words/second on a plain
CPU for the shipped quantized bundle (sentence-length dependent; the full-precision
`grc-joint-v2` asset is several times faster where throughput matters more than download
size). The bundle ships **quantized** at about 173 MB (down from 518 MB) with **no loss of
accuracy**: the scores above are unchanged from the full-precision model. The recipe is
weight-only int8 (onnxruntime MatMulNBits) plus fp16, keeping activations at full
precision; it needs **onnxruntime>=1.23** (the `[neural]` floor), and the full-precision
model stays available at the `grc-joint-v2` release for reproducibility. The
model bundle is CC BY-SA 4.0, fetched to the cache, never bundled; training data,
leakage controls, and the comparison tables are documented in
[`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md).

## Normalization & Beta Code

Beta Code is the ASCII transliteration of polytonic Greek used by the TLG and
Perseus: it lets you type Greek without a Greek keyboard. Conversion is
round-trip-safe and emits precomposed NFC.

```python
greek.betacode_to_unicode("mh=nin")      # 'μῆνιν'
greek.betacode_to_unicode("lo/gos")      # 'λόγος'   (context-sensitive final ς)
greek.betacode_to_unicode("tw=|")        # 'τῷ'      (iota subscript)
greek.unicode_to_betacode("Ἀχιλῆος")     # '*a)xilh=os'

greek.normalize("ό")                     # 'ό'   (NFC by default)
greek.strip_diacritics("ἄνθρωπος")       # 'ανθρωπος'
```

The same three from the shell:

```bash
aegean greek betacode "mh=nin"               # μῆνιν
aegean greek betacode --reverse "Ἀχιλῆος"    # *a)xilh=os
aegean greek strip "ἄνθρωπος"                # ανθρωπος
aegean greek normalize "ό"                   # ό
```

Supported Beta Code: the 24 letters (`*` marks capitals, `s1/s2/s3` sigma
variants) and the diacritics:

| Beta Code mark | Diacritic |
| --- | --- |
| `)` | smooth breathing |
| `(` | rough breathing |
| `/` | acute |
| `\` | grave |
| `=` | circumflex |
| `+` | diaeresis |
| `|` | iota subscript |
| `*` | (prefix) capital letter |
| `s1` / `s2` / `s3` | medial σ / final ς / lunate ϲ |

**Lenient mode for OCR'd or messy text.** `normalize(..., lenient=True)` (CLI
`--lenient`) repairs, and *warns about* (a `NormalizationWarning` per repair
class; on the CLI the warnings go to stderr), the common artifacts of scanned
editions and half-converted files, instead of letting them silently break
tokenization downstream:

```python
greek.normalize("λόγoς", lenient=True)    # 'λόγος'  (Latin o inside a Greek word)
greek.normalize("μη=νιν", lenient=True)   # 'μῆνιν'  (Beta-Code remnant diacritic)
```

```bash
aegean greek normalize --lenient "λόγoς"
# aegean: lenient normalize: repaired 1 Latin letter(s) in Greek words (o→ο)   [stderr]
# λόγος
```

Three repair classes: Latin letters embedded in Greek-containing words (only letters
where the visual lookalike and the Beta-Code letter agree: ambiguous ones like `p`
are reported but left alone), Beta-Code diacritics still attached to Greek letters
(converted only where the mark is phonologically possible: breathings on vowels/ρ,
diaeresis on ι/υ, …), and stray combining marks with no base letter (dropped).
Pure-Latin words pass through untouched, and the default strict mode is unchanged.
`normalize`'s `form`/`--form` flag selects the Unicode normal form (`NFC` default,
or `NFD`/`NFKC`/`NFKD`).

## Tokenization

```python
greek.tokenize_words("ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός.")
# ['ἐν', 'ἀρχῇ', 'ἦν', 'ὁ', 'λόγος', 'καὶ', 'θεός']

greek.tokenize("λόγος, καί")     # [Token('λόγος', WORD), Token(',', PUNCT), Token('καί', WORD)]
greek.sentences("ἐν ἀρχῇ ἦν ὁ λόγος. καὶ θεός ἦν;")
# ['ἐν ἀρχῇ ἦν ὁ λόγος', 'καὶ θεός ἦν']
```

From the shell, one token per line (punctuation included), or `--sentences` to
split sentences instead:

```bash
aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός."
# ἐν / ἀρχῇ / ἦν / ὁ / λόγος / , / καὶ / θεός / .   (one per line)

aegean greek tokenize --sentences "ἐν ἀρχῇ ἦν ὁ λόγος. καὶ θεός ἦν;"
# ἐν ἀρχῇ ἦν ὁ λόγος
# καὶ θεός ἦν

aegean greek tokenize --json "λόγος, καί"     # ["λόγος", ",", "καί"]
```

Elision apostrophes are kept inside a single token (`ποικιλόθρον’`).

## Syllabification

Rule-based: diphthong nuclei, "muta cum liquida" clusters that stay together,
doubled-consonant splits, and valid Greek onsets, plus a curated **exception
lexicon** for lexicalised compounds, which divide at the point of union
(Smyth §140) where pure phonotactics would missplit.

```python
greek.syllabify("λόγος")        # ['λό', 'γος']
greek.syllabify("ἄνθρωπος")     # ['ἄν', 'θρω', 'πος']
greek.syllabify("θάλασσα")      # ['θά', 'λασ', 'σα']
greek.syllabify("ποικιλόθρον")  # ['ποι', 'κι', 'λό', 'θρον']
greek.syllabify("εἰσφέρω")      # ['εἰσ', 'φέ', 'ρω']   (compound: εἰσ + φέρω,
                                #  where the rules alone would give εἰ-σφέ-ρω)
```

The CLI takes one or more words and shows each split with a hyphen:

```bash
aegean greek syllabify "λόγος" "ἄνθρωπος" "εἰσφέρω"
# λόγος → λό-γος
# ἄνθρωπος → ἄν-θρω-πος
# εἰσφέρω → εἰσ-φέ-ρω
```

The lexicon lists dictionary forms (inflected variants fall back to the rules);
adding an entry is a welcome one-line contribution: see `CONTRIBUTING.md`, which
also explains the test that makes every entry prove it differs from the rules.

## Accent analysis

```python
info = greek.accentuation("λόγος")
info.accent_type          # 'acute'
info.position_from_end    # 2   (1=ultima, 2=penult, 3=antepenult)
info.classification       # 'paroxytone'
info.syllables            # ('λό', 'γος')
```

The CLI accepts one or more words and prints a table (`--json` for the records):

```bash
aegean greek accent "λόγος"
#  word    accent   pos   classification
#  λόγος   acute    2     paroxytone
```

Classifications:

| Accent | Position | Classification |
| --- | --- | --- |
| acute | ultima | oxytone |
| acute | penult | paroxytone |
| acute | antepenult | proparoxytone |
| circumflex | ultima | perispomenon |
| circumflex | penult | properispomenon |
| grave | ultima | barytone |

## Accent placement

Where `accentuation` *reads* the accent off a word that already carries one,
`place_accent` *predicts* where the accent belongs, from the Greek accentuation
laws: the law of limitation (an accent falls no further back than the antepenult,
and not on the antepenult when the ultima is long), the **recessive** rule for
finite verbs (the accent retreats as far toward the antepenult as the laws allow),
the **persistent** rule for nominals (the accent stays on the lemma's syllable
unless a long ultima forces it forward), and the properispomenon rule (a long
penult before a short ultima takes the circumflex).

```python
greek.place_accent("λυε", recessive=True).form              # 'λύε'   (finite verb: recessive)
greek.place_accent("λογος", recessive=False, lemma="λόγος").form   # 'λόγος' (nominal: persistent)

acc = greek.place_accent("λογος", recessive=False, lemma="λόγος")
acc.accent_type, acc.position_from_end, acc.classification   # ('acute', 2, 'paroxytone')
acc.certain, acc.note                                        # (True, 'persistent')
```

`recessive_accent(word, …)` and `persistent_accent(form, lemma, …)` are the two
rules directly; `place_accent(word, *, recessive, lemma=None, ultima_length=None,
penult_length=None)` dispatches between them (`recessive=True`, or persistent with
a `lemma`). Each returns an `AccentPlacement` with `form`, `accent_type`,
`position_from_end` (1=ultima, 2=penult, 3=antepenult), `classification`,
`certain`, and `note`.

**Dichrona are flagged, not guessed.** Whether α, ι, or υ is long or short cannot
be read off the spelling, and that length is sometimes what decides the accent (a
circumflex vs an acute on the penult, or whether the antepenult is even allowed).
When a *dichronon* is the deciding factor the placement is returned with
`certain=False` and a `note` saying what was undetermined, rather than a silent
guess. Supplying the missing length via `ultima_length=` / `penult_length=`
(`"long"` / `"short"`), or a `lemma` whose own accent resolves it, makes the
answer `certain`:

```python
greek.place_accent("λυε", recessive=True).certain                       # False — penult dichronon
greek.place_accent("λυε", recessive=True, penult_length="short").certain  # True  — length supplied
```

The CLI `accentuate` takes one or more words and prints each placement (`--json`
for the records); `--recessive` / `--persistent` choose the rule and `--lemma`
supplies the persistent home syllable:

```bash
aegean greek accentuate λυε --recessive
# λύε	paroxytone  (uncertain: recessive; penult acute/circumflex undetermined (dichronon))

aegean greek accentuate λογος --persistent --lemma λόγος
# λόγος	paroxytone
```

This is a rule engine over the accentuation laws, not a corpus lookup: it predicts
the regular placement and is honest about the cases the spelling leaves
undetermined.

## Resolving crasis, elision, and movable nu

Surface contractions otherwise pass through the pipeline opaquely.
`resolve_sandhi` expands one token to the underlying word(s), so downstream stages
(lemmatize, gloss, parse) see real words rather than a clipped or fused form:

```python
greek.resolve_sandhi("κἀγώ").words      # ('καί', 'ἐγώ')   (crasis)
greek.resolve_sandhi("τἀμά").words      # ('τὰ', 'ἐμά')    (crasis)
greek.resolve_sandhi("οὐκ").words       # ('οὐ',)          (movable-nu / οὐκ alternation)
greek.resolve_sandhi("λόγος").words     # ('λόγος',)       (no sandhi: passes through)
```

A `ResolvedForm` carries `surface`, `words` (the underlying sequence), `kind`
(`"crasis"` / `"elision"` / `"movable-nu"` / `None`), `uncertain`, `note`, and
`alternatives`. `resolve_sentence(text)` maps it over every word of a sentence;
flatten with `[w for r in result for w in r.words]` to get the expanded word
stream the rest of the pipeline should index against.

```python
greek.resolve_sandhi("κἀγώ").kind       # 'crasis'
greek.resolve_sandhi("κἀγώ").note       # 'crasis κἀγώ = καί + ἐγώ'
```

The CLI `sandhi` takes one or more words and prints the expansion (`--json` for
the records):

```bash
aegean greek sandhi κἀγώ
# καί ἐγώ	crasis
```

**Conservative by design.** Crasis is expanded only from a small curated,
contribution-friendly lexicon (a one-line addition; see `CONTRIBUTING.md`); a
coronis form not in it is flagged `uncertain` and left intact. Elision is restored
only where the elided vowel is unambiguous (a listed proclitic/particle or a clear
inflectional ending); otherwise the clipped stem is kept and flagged. The
movable-ν and οὐκ/οὐχ/οὐ rules are purely contextual and need no lexicon. The
resolver never over-expands: an ambiguous form comes back unchanged with
`uncertain=True` and a note.

## Prosody (syllable quantity)

Classifies each syllable as **heavy** / **light** / **common**: the metrical
foundation of meter. A syllable is heavy if it's closed (long by position) or has
a long nucleus (η, ω, a circumflex, an iota-subscript vowel, or a diphthong);
light if open with a short nucleus (ε, ο); common if open with a *dichronon*
(α, ι, υ), whose length isn't determinable from spelling.

```python
greek.syllable_quantities("λόγος")      # ['light', 'heavy']
greek.syllable_quantities("ἄνθρωπος")   # ['heavy', 'heavy', 'heavy']
greek.syllable_quantities("μῆνιν")      # ['heavy', 'heavy']
greek.scan("θάλασσα")                   # [('θά','common'), ('λασ','heavy'), ('σα','common')]
```

```bash
aegean greek quantities "ἄνθρωπος" "μῆνιν"
# ἄνθρωπος → ἄν:heavy | θρω:heavy | πος:heavy
# μῆνιν → μῆ:heavy | νιν:heavy
```

Baseline scope: these quantities are computed within a single word. To resolve a
syllable's quantity *in metrical context* (across word boundaries, with the
caesura and the ambiguities a verse line allows) use the **[metrical
scansion](#metrical-scansion)** below, which builds on this word-level view.

## Metrical scansion

Scan a line of verse into its feet. It covers **dactylic hexameter** (the metre
of Homer), **elegiac pentameter** (the second line of an elegiac couplet),
**iambic trimeter** (the metre of tragic and comic dialogue), and the **aeolic
lyric** lines. The scanner resolves each syllable's quantity *in context*:
applying *correptio* (a long vowel shortened before another vowel), treating
muta-cum-liquida clusters as the ambiguity they are, and counting position across
word boundaries. The deep dive (caesura conventions, resolution, synizesis, the
full template list) lives on the [Meters](Meters) page.

The result is glyph notation you'll recognise from any commentary: **—** heavy
(long), **⏑** light (short), **×** *anceps* (the "either" final syllable).

```python
sc = greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
sc.pattern        # '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'   (Odyssey 1.1 — five dactyls)
sc.meter          # 'hexameter'
[f.name for f in sc.feet]
# ['dactyl', 'dactyl', 'dactyl', 'dactyl', 'dactyl', 'final']
sc.caesura        # 'trochaic'   (the main word-break in the third foot)
```

The CLI `scan` defaults to hexameter; `--meter` picks any of the metres below.
It prints the glyph pattern, the feet, and the caesura (`--json` gives the full
`LineScansion`):

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic

aegean greek scan --meter trimeter "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα"
# ×—⏑—|×—⏑—|×—⏑×
# trimeter: metron, metron, metron; caesura: hephthemimeral

aegean greek scan --meter pentameter "κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι."
# —⏑⏑|——|—|—⏑⏑|—⏑⏑|×
# pentameter: dactyl, spondee, longum, dactyl, dactyl, longum; caesura: —
```

Iambic trimeter is three metra of `× — ⏑ —`, with **resolution** of a long
element into two shorts:

```python
greek.scan_trimeter("Διόνυσον, ὃν τίκτει ποθ' ἡ Κάδμου κόρη").pattern  # Bacchae 2
# '×⏑⏑⏑—|×—⏑—|×—⏑×'   — the first long is resolved (Διό- = ⏑⏑)
```

**Aeolic lyric lines** are matched against fixed quantity templates (the choriambic
nucleus doesn't resolve), so a line scans-or-declines just like the metres above.
`greek.AEOLIC_LINES` lists the supported types:

| Aeolic line | Example |
| --- | --- |
| `glyconic` | the workhorse aeolic colon |
| `pherecratean` | catalectic glyconic |
| `sapphic_hendecasyllable` | Sappho's stanza line |
| `adonean` | the short close of the Sapphic stanza |
| `alcaic_hendecasyllable` | Alcaeus's stanza line |
| `alcaic_enneasyllable` | the 9-syllable Alcaic colon |
| `alcaic_decasyllable` | the 10-syllable Alcaic colon |

```python
greek.scan_aeolic("φαίνεταί μοι κῆνος ἴσος θέοισιν", "sapphic_hendecasyllable").pattern
# '—⏑—×—⏑⏑—⏑—×'   (Sappho 31.1)
greek.scan_aeolic("ἀσυννέτημμι τὼν ἀνέμων στάσιν", "alcaic_hendecasyllable").pattern
# '×—⏑—×—⏑⏑—⏑×'   (Alcaeus 326.1)
```

`scan_line(line, meter)` dispatches by name (`"hexameter"` / `"pentameter"` /
`"trimeter"` / any aeolic line), and a `LineScansion` carries these fields:

| Field | Meaning |
| --- | --- |
| `.line` | the input line |
| `.meter` | the metre that matched |
| `.feet` | a list of `Foot(name, syllables, quantities)` |
| `.syllables` | every syllable, flat |
| `.quantities` | the resolved quantity of each syllable |
| `.caesura` | the caesura name (e.g. `trochaic`, `penthemimeral`) |
| `.caesura_index` | the syllable index the line breaks before |
| `.ambiguous` | whether more than one scansion fit |

To inspect the *possible* quantities of each syllable before a metre is imposed
(useful for seeing where a line is genuinely ambiguous) use `syllable_options`:

```python
greek.syllable_options("πατρός")
# [('πα', ['heavy', 'light']), ('τρός', ['light'])]   ← πα is muta-cum-liquida: either
```

**Synizesis is lexical, never inferred.** When a line only scans if two written
vowels are read as one syllable (e.g. *Iliad* 1.1, where `Πηληϊάδεω` reads its
final `-εω` as one syllable), the scanner applies it **only** for words in a
curated lexicon: each entry test-enforced to be required by a real line that
otherwise fails:

```python
greek.scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος").pattern
# '—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×'   — Πηληϊάδεω is in the lexicon, so the line scans
```

A line needing synizesis on a word **not** in the lexicon raises `ScansionError`
(the CLI exits 1 with the reason) rather than guessing. The aeolic lyric lines
are supported (above); other lyric metres (dactylo-epitrite, free astrophic)
remain out of scope for now: see [Limitations](Limitations).

## Phonology (reconstructed IPA)

Transcribe Greek to IPA for two periods: `"attic"` (Classical, default) and
`"koine"` (Hellenistic/Imperial).

```python
greek.to_ipa("θεός")               # 'tʰeos'   (Attic: aspirated θ)
greek.to_ipa("ὁ")                  # 'ho'      (rough breathing → /h/)
greek.to_ipa("ἄγγελος")            # 'aŋɡelos' (γγ → velar nasal)
greek.to_ipa("θεός", "koine")      # 'θeos'    (Koine: θ is a fricative)
greek.to_ipa("καί", "koine")       # 'ke'      (iotacism: αι → /e/)
```

```bash
aegean greek ipa "θεός"                  # tʰeos
aegean greek ipa --period koine "θεός"   # θeos
```

Attic uses aspirated φ θ χ = /pʰ tʰ kʰ/, voiced stops β γ δ = /b ɡ d/, ζ = /zd/,
υ = /y/, distinctive vowel length, and rough breathing = /h/. Koine fricativizes
(φ θ χ = /f θ x/; β γ δ = /v ɣ ð/), is mid-iotacism (η, ει → /i/; αι → /e/; οι → /y/), and
drops length and the breathings.

**Reconstructed and approximate**: several values (ε/η quality, the long
diphthongs, the date of iotacism) are scholarly judgement calls; see
[Limitations](Limitations).

## POS tagging (baseline)

Coarse part-of-speech tags (Universal Dependencies inventory). Closed classes
(article, prepositions, conjunctions, particles, pronouns, and the εἰμί copula)
are tagged reliably from a lexicon; open-class words get a light suffix heuristic
(a few verb endings, else NOUN).

```python
greek.pos_tag("ὁ")          # 'DET'
greek.pos_tag("πρὸς")       # 'ADP'   (grave folded to acute for lookup)
greek.pos_tag("ἦν")         # 'VERB'  (copula)
greek.pos_tag("λόγος")      # 'NOUN'

greek.pos_tags("ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός.")
# [('ἐν','ADP'), ('ἀρχῇ','NOUN'), ('ἦν','VERB'), ('ὁ','DET'),
#  ('λόγος','NOUN'), (',','PUNCT'), ('καὶ','CCONJ'), ('θεός','NOUN'), ('.','PUNCT')]
```

The CLI tags one token per line (and `--treebank` / `--tagger` / `--neural` turn
on the backends below for that run; `--json` gives the records):

```bash
aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός."
# ἐν	ADP
# ἀρχῇ	NOUN
# ἦν	VERB
# ὁ	DET
# λόγος	NOUN
# ,	PUNCT
# καὶ	CCONJ
# θεός	NOUN
# .	PUNCT
```

Tags emitted: `DET ADP CCONJ SCONJ PART PRON ADV NUM NOUN VERB ADJ PUNCT X`
(treebank mode may also emit `INTJ`).

**Baseline scope:** closed classes are reliable; open-class precision is limited
(an open-class verb like ἄειδε falls back to NOUN). To fix this for *attested*
forms, switch on the [treebank backend](#treebank-backed-mode-opt-in): with
`greek.use_treebank()` active, `pos_tag`/`pos_tags` return the gold AGDT tag for a
known form (e.g. ἔφη → VERB) before falling back to the heuristic. The treebank
only covers attested forms, though: to tag an **unseen** form well, switch on the
[generalizing tagger](#generalizing-pos-tagger-opt-in) below.

## Generalizing POS tagger (opt-in)

The baseline heuristic and the treebank lookup both fall down on an *unseen* open-class
form: the heuristic just guesses NOUN, and the lookup has no entry for it. `use_tagger()`
switches on a trained **averaged-perceptron** sequence tagger (pure Python, no heavy deps)
that predicts a tag from suffix/prefix/shape/accent features plus left-to-right sentence
context, so it **generalizes** to forms it has never seen.

```python
greek.use_tagger()        # one-time fetch of the prebuilt model (or local train as fallback), then cached
greek.pos_tags("ἐν ἀρχῇ ἦν ὁ λόγος")   # every token tagged, in context
greek.disable_tagger()    # back to the lookup/heuristic
```

```bash
aegean greek tag --tagger "ἐν ἀρχῇ ἦν ὁ λόγος"   # tagged in context
```

It composes with the cascade: the closed-class lexicon and (when active) the treebank
lookup still take precedence per token for the forms they cover; the tagger fills in
everything else, including words neither has seen.

**Measured: held-out AGDT, leakage-free.** Trained on a 90% sentence split and scored on
the disjoint 10% (≈54k tokens, via `greek.evaluate_tagger()`), it reaches **84.4% POS
overall and 83.6% on unseen forms**: forms absent from the training split. For contrast,
on the same tokens the lookup scores 0% on unseen (no entry) and the suffix heuristic only
~50%. The cached model is ~2.2 MB and `import aegean` stays instant: the model arrives on
first `use_tagger()` (prebuilt fetch, or trained locally as the fallback), never bundled.

```python
greek.evaluate_tagger(holdout=0.1)
# {'pos_all': 0.844, 'pos_unseen': 0.836, 'n_all': 54036, 'n_seen': 45138, 'n_unseen': 8898}
```

This is a generalizing tagger with **zero heavy dependencies, an instant import, and a
~2 MB model**: a deliberate point on the trade-off curve, favouring pure-Python portability
over the absolute accuracy of a full neural pipeline.

## Morphological analysis

Given an inflected form, `analyze` returns the morphological readings its ending
implies: part of speech plus the relevant features (case/number/gender for
nouns; tense/voice/mood/person/number for verbs), each with a reconstructed
lemma. Greek inflection is richly ambiguous, so a single form legitimately yields
several candidate readings; you disambiguate with context.

```python
for a in greek.analyze("λόγον"):
    print(a)
# λόγος [NOUN acc sg masc]
# λόγος [NOUN acc sg fem]
# λόγος [NOUN nom sg neut]
# λόγος [NOUN acc sg neut]
# λόγος [NOUN voc sg neut]
```

The CLI `morph` takes one word and lists the candidate parses (`--treebank` to
add the AGDT lexicon; `--json` for the structured readings):

```bash
aegean greek morph "λόγον"
# λόγος [NOUN acc sg masc]
# λόγος [NOUN acc sg fem]
# λόγος [NOUN nom sg neut]
# λόγος [NOUN acc sg neut]
# λόγος [NOUN voc sg neut]
```

Each reading is an `Analysis` with the lemma, the POS, and the individual feature
fields; `.features()` gives just the ones that apply:

```python
a = greek.analyze("λύεις")[0]
a.lemma, a.pos        # ('λυω', 'VERB')
a.features()          # {'number': 'sg', 'tense': 'pres', 'voice': 'act', 'mood': 'ind', 'person': '2'}
a.lemma_certain       # False  ← see "how far to trust the lemma" below
```

The `--json` output exposes every field of each reading: `lemma`, `pos`, `case`,
`number`, `gender`, `tense`, `voice`, `mood`, `person`, `degree`, and
`lemma_certain` (inapplicable fields are `null`).

Closed-class words (the article, prepositions, conjunctions, particles, pronouns)
come back as a single, confident reading:

```python
greek.analyze("ὁ")       # (Analysis(lemma='ὁ', pos='DET'),)
greek.analyze("καί")[0]  # καί → CCONJ
```

The closed-class coverage is wide. The indefinite and interrogative τις / τίς
(distinguished by the written accent), the relative ὅς / ἥ / ὅ paradigm, the
determiners ἄλλος / ἕκαστος / πᾶς, the low cardinals and ordinals, and a longer
particle list now tag and analyse with their case/number/gender (or their part of
speech), where the bare rule engine previously returned nothing:

```python
[str(a) for a in greek.analyze("τις")]   # ['τις [PRON nom sg masc]', 'τις [PRON nom sg fem]']
greek.analyze("τίς")[0]                   # τίς → PRON (interrogative: the acute distinguishes it)
greek.analyze("ὅς")[0]                    # ὅς  → PRON (relative)
greek.analyze("ἕκαστος")[0]              # ἕκαστος → DET
```

Two convenience shortcuts when you don't need the full feature set:

```python
greek.lemmas("ἀνθρώπων")   # ['ἄνθρωπος']   (the distinct lemmas a form could belong to)
greek.best_pos("λύεις")    # 'VERB'         (the single most likely part of speech)
```

### How far to trust the lemma

`Analysis.lemma_certain` tells you how much to trust the lemma. When the bundled
seed lexicon knows the form, you get the correctly **accented** lemma and
`lemma_certain=True`. When the form is regular but out-of-vocabulary, the lemma is
*reconstructed* from the ending: **unaccented** (accent recession can't be
derived from the ending alone) and flagged `lemma_certain=False`:

```python
[a for a in greek.analyze("ἀνθρώπων") if a.pos == "NOUN"][0].lemma   # 'ἄνθρωπος' (seed, certain)
[a for a in greek.analyze("ἵππον")   if a.pos == "NOUN"][0].lemma    # 'ιππος'   (reconstructed, uncertain)
```

### Scope and caveats

This is a **baseline** engine: high-precision on the *regular* paradigms it
encodes (the article and pronouns, the first and second declensions and common
third-declension endings, and **thematic** verbs in the present, imperfect, future
and sigmatic aorist indicative, plus common infinitives and the mediopassive
participle). Past tenses are augment-gated, and a dative singular is detected from
its iota subscript. Athematic, contract, irregular and suppletive forms (`εἶπον` →
`λέγω`) are beyond a purely rule-based reach; for those, switch on the
[treebank-derived lexicon](#treebank-backed-mode-opt-in) below. For ambiguous forms the
feature analyses are **exploratory**: trust the closed classes and the feature
set; treat a single auto-picked reading with care.

### Treebank-backed mode (opt-in)

The baseline above is rule-based and fully offline. For *attested* forms you can
switch on a **treebank-derived lexicon** built from the Perseus Ancient Greek
Dependency Treebank (AGDT v2.1). It supplies correctly-**accented** lemmas and full
features: including the irregular, contract, athematic and third-declension forms
the rule engine can't reach:

```python
greek.use_treebank()         # one-time fetch of the ~15 MB prebuilt lexicon, cached; then instant

greek.lemmatize("ἄνδρα")      # 'ἀνήρ'      (3rd declension; the rule engine gives a bare stem)
greek.lemmatize("ἔφη")        # 'φημί'      (suppletive athematic verb)
greek.lemmatize("γυναικός")   # 'γυνή'
greek.lemmatize("πόλεως")     # 'πόλις'
greek.analyze("ἀνθρώπων")[0]  # ἄνθρωπος [NOUN gen pl masc]   (lemma_certain=True)
```

Once active, `lemmatize`/`analyze` prefer the treebank for known forms and fall
back to the rule/seed engine for the rest; `greek.disable_treebank()` restores the
default. (On the CLI, pass `--treebank` to `tag`, `lemmatize`, `morph`, or
`pipeline`.) Network is needed only on the first call: it fetches the prebuilt
AGDT-derived lexicon (part of one shared ~15 MB bundle), falling back to
downloading the treebank itself (~75 MB) and building locally if the asset is
unreachable. The data is **CC BY-SA 3.0** (derived from the AGDT), fetched to your
cache and never bundled: see
[Data & Provenance](Data-and-Provenance#the-greek-treebank-lexicon--models-agdt-derived-use_treebank).

## Inflection synthesis (opt-in)

The inverse of analysis: where `analyze`/`lemmatize` map a *form* to its lemma and
features, `inflect` maps a **lemma plus a feature spec** back to the attested form(s).
`use_inflector()` builds (and caches) an inverse index over the same AGDT treebank lexicon
the analysis stack uses, then `inflect` / `paradigm` resolve against it. Coverage is what
the corpus attests: every `(lemma, features)` cell seen in the AGDT is generated exactly,
most-attested first; an unattested lemma or cell comes back empty.

```python
greek.use_inflector()                          # one-time AGDT lexicon build, then cached
greek.inflect("λόγος", case="gen", number="sg")   # ('λόγου',)
greek.inflect("λόγος", case="gen", number="pl")   # ('λόγων',)
greek.inflect("λύω", tense="pres", voice="act", mood="ind", person="1", number="sg")  # ('λύω',)
```

`inflect` returns a **tuple** because one cell can have several attested spellings: the AGDT
records Homeric and dialectal datives such as `λόγοισι(ν)` beside Attic `λόγοις`, and treebank
annotation noise occasionally leaves a stray form, so treat low-frequency extras as candidates,
not certainties. A call before `use_inflector()` raises `InflectorNotLoadedError`. `paradigm`
returns every attested cell of a lemma as `(features, form)` pairs:

```python
cells = greek.paradigm("λόγος")
[(f, form) for f, form in cells][:3]
# [({'pos': 'NOUN', 'case': 'nom', 'number': 'sg', 'gender': 'masc'}, 'λόγος'),
#  ({'pos': 'NOUN', 'case': 'gen', 'number': 'sg', 'gender': 'masc'}, 'λόγου'), …]
```

The feature keys are the analyzer's short codes: `pos` (NOUN/VERB/ADJ/…), `case`
(nom/gen/dat/acc/voc/loc), `number` (sg/pl/du), `gender` (masc/fem/neut), `tense`
(pres/impf/aor/perf/plup/fut/futperf), `voice` (act/mid/pass/mp), `mood`
(ind/subj/opt/inf/imp/part), `person` (1/2/3), and `degree` (comp/sup). Pass any partial
subset; the unspecified keys are left free.

The CLI `inflect` takes the lemma plus a flag per feature, and `--paradigm` lists the whole
table (`--json` for the structured cells):

```bash
aegean greek inflect "λόγος" --case gen --number sg     # λόγου
aegean greek inflect "λόγος" --paradigm                 # every attested cell
```

Built from the AGDT (CC BY-SA 3.0), fetched to your cache and never bundled (the same
shared lexicon as the [treebank backend](#treebank-backed-mode-opt-in));
`greek.disable_inflector()` turns it off.

## Lemmatization (baseline)

Two always-offline tiers, tried in order: a small bundled form→lemma **seed table** (for
irregular and high-frequency forms), then a **generalizing rule layer** that strips the
regular second-declension and thematic-verb endings back to the citation form by
accent-preserving substitution (`-ου/-ῳ/-ον/-οι/-οις → -ος`, the first-declension `-αν → -α`,
and the thematic active `-εις/-ει/-ομεν/-ετε/-ουσι(ν)` plus the infinitive `-ειν` → `-ω`).
Conservative guards skip contracted/perispomenon forms (`Ἰησοῦς`, `ζῇ`), common neuter `-ον`
nouns, and indeclinables; the ambiguous `-η` series is left to the seed table and the backends.
The rules keep the surface stem intact, so an unseen `νόμου` lemmatizes to `νόμος` without a
lookup. For attested forms the [treebank backend](#treebank-backed-mode-opt-in) supplies
real, accented lemmas, and the rule-based [morphological analyzer](#morphological-analysis)
is documented above.

```python
greek.lemmatize("λόγου")             # 'λόγος'   (seed table)
greek.lemmatize("ἦν")                # 'εἰμί'    (seed table; irregular)
greek.lemmatize("νόμου")             # 'νόμος'   (rule layer; not in the table)
greek.lemmatize_verbose("πατρός")    # ('πατρός', False)  ← 3rd-declension, not rule-recoverable
```

The CLI lemmatizes every word, form→lemma per line (backend flags `--treebank`,
`--lemmatizer`, `--neural-lemmatizer`, `--neural`; `--json` for records carrying
`form`/`lemma`/`known`):

```bash
aegean greek lemmatize "λόγου ἦν"
# λόγου	λόγος
# ἦν	εἰμί
```

The rule layer covers the *regular* paradigms only; it cannot restore an accent that recedes
between the inflected form and the lemma (`κυρίῳ → κύριος`), and third-declension stems,
indeclinables, and irregular/suppletive forms come back unchanged. For those, switch on the
[generalizing lemmatizer](#generalizing-lemmatizer-opt-in) below.

## Generalizing lemmatizer (opt-in)

The seed table and the treebank lookup only lemmatize *attested* forms, and the baseline rule
layer only the *regular* paradigms; an irregular unseen form comes back unchanged.
`use_lemmatizer()` switches on a trained lemmatizer that **generalizes** more broadly: from
each (form, lemma) pair it learns a Chrupała-style **edit tree**: a recursive transform that
keeps the shared stem and rewrites the differing prefix/suffix, so a rule learned from one
word (`-ου → -ος`) applies to unseen words (`νόμου → νόμος`), and edit trees capture accent
shifts and capitalization too. An averaged-perceptron reranker, conditioned on POS, picks the
right tree for each form.

```python
greek.use_tagger()        # recommended — the lemmatizer conditions on the tagger's POS
greek.use_lemmatizer()    # one-time fetch of the prebuilt model (or local train as fallback), then cached
greek.lemmatize("ἀνθρώπων")   # 'ἄνθρωπος', even if the form was never attested
greek.disable_lemmatizer()
```

```bash
aegean greek lemmatize --lemmatizer "ἀνθρώπων νόμου"   # generalizes to unseen forms
```

It slots into the cascade after the treebank lookup: an attested form still gets its gold
lemma; everything else goes to the model.

**Measured: held-out AGDT, leakage-free.** Trained on a 90% sentence split and scored on the
disjoint 10% (via `greek.evaluate_lemmatizer()`, with *predicted* POS), it reaches **84.5%
overall and 40.3% on unseen forms**, versus the lookup's 0% on unseen. The cached model is
~7 MB (fetched prebuilt on first use, or trained locally if the asset is unreachable, never
bundled).

This is real generalization from a zero-dependency model (0% → 40% on unseen, competitive
on attested forms). Recovering an unseen Greek lemma often means an internal stem/accent
change rather than a suffix swap, which is where a pure-Python edit-tree reranker reaches
its limit. For higher unseen accuracy, switch on the
**[neural backend](#neural-lemmatizer-opt-in)** below, which reaches 76.3% on unseen forms.

## Neural lemmatizer (opt-in)

The `[neural]` backend **generates** the lemma with a fine-tuned **GreTa** (Ancient-Greek
T5) seq2seq, composing novel stem and accent changes rather than classifying a form into a
known transformation. On unseen forms it reaches **76.3%**.

```bash
pip install "pyaegean[neural]"      # onnxruntime + tokenizers; no torch
```

```python
greek.use_neural_lemmatizer()       # fetches the model (~232 MB, one-time) to the cache
greek.lemmatize("θήσονται")         # 'τίθημι'   — generated, never attested in this form
greek.lemmatize("λάθωσι")           # 'λανθάνω'
greek.disable_neural_lemmatizer()
```

```bash
aegean greek lemmatize --neural-lemmatizer "θήσονται λάθωσι"
```

It is a **hybrid**: a bundled gold lookup answers attested (seen) forms exactly, so the model
only generates for genuinely unseen forms, and it slots into the cascade just after the
treebank lookup, ahead of the edit-tree reranker. Inference is **torch-free** (a numpy greedy
decode over the int8 ONNX encoder/decoder via onnxruntime); the model is fetched to the cache,
never bundled, so `import aegean` stays instant. The weights derive from CC BY-SA treebanks
(see [Data & Provenance](Data-and-Provenance)); the wheel stays Apache-2.0 because the model is
fetched, not bundled.

## Dependency parsing (opt-in, baseline)

`use_parser()` activates (on first use it fetches the prebuilt model from the shared
AGDT-derived bundle; if that's unreachable it downloads the AGDT and trains locally:
a few minutes) a transition-based **arc-eager** parser with an **averaged-perceptron**
classifier (pure Python, no heavy deps); then `parse()` turns a sentence into a
dependency tree with the gold **AGDT/Prague** labels (SBJ, OBJ, ATR, ADV, PRED, Aux*…).

```python
greek.use_treebank()     # optional — improves the POS/lemmas the parser feeds on
greek.use_parser()       # one-time train (~2–3 min) from the cached AGDT, then cached

tree = greek.parse("ἐν ἀρχῇ ἦν ὁ λόγος")
print(tree)
# 1  ἐν     ADP   AuxP  ->3(ἦν)
# 2  ἀρχῇ   NOUN  ADV   ->1(ἐν)
# 3  ἦν     VERB  PRED  ->0(ROOT)
# 4  ὁ      DET   ATR   ->5(λόγος)
# 5  λόγος  NOUN  SBJ   ->3(ἦν)

tree.root().form                      # 'ἦν'
[t.form for t in tree.children(3)]    # ['ἐν', 'λόγος']
```

```bash
aegean greek parse --parser "ἐν ἀρχῇ ἦν ὁ λόγος"     # AGDT/Prague labels
aegean greek parse --neural "ἐν ἀρχῇ ἦν ὁ λόγος"     # UD relations (needs the [neural] extra)
```

A `DepTree` is a tuple of `DepToken(id, form, lemma, upos, head, relation)` with
`root()`, `head_of(id)`, `children(id)`, and `is_projective()`. You can also read the
treebank's **gold** trees directly: `from aegean.greek.syntax import load_gold_trees`.

**This is an honest baseline.** Ancient Greek is richly **non-projective** (only ~31%
of AGDT sentences are projective), and arc-eager can build only projective trees, so
non-projective gold structures are out of reach and are skipped in training (a known
limitation, not a bug). Measured on held-out AGDT with gold POS:
**~0.67 UAS / 0.57 LAS on projective sentences, ~0.51 / 0.42 across all text**
(`greek.evaluate_parser()` reproduces these). It produces clean, correct trees for
main-clause syntax (as above), but it is not a research-grade parser. For research-grade
dependency trees, use the [neural pipeline](#the-neural-pipeline-opt-in)'s `--neural`
parse, which decodes a full (non-projective) UD tree. The baseline model is derived from
the AGDT (CC BY-SA 3.0), cached locally (~4 MB), never bundled; `greek.disable_parser()`
turns it off. See [Limitations](Limitations).

## Lexicon (LSJ glossing, opt-in)

What does a word *mean*? `use_lsj()` switches on the full **Perseus Liddell-Scott-Jones**
lexicon: it fetches the prebuilt ~15 MB index (one-time; or, if that asset is
unreachable, downloads the ~270 MB TEI and builds the index locally), then
`gloss`/`lookup` resolve a Greek word to its dictionary entry. Looking up an inflected
form works: it tries the form, then lemmatizes (using the [treebank backend](#treebank-backed-mode-opt-in)
if active) and retries, so it composes with everything above.

```python
greek.use_treebank()         # optional, but lets inflected/irregular forms resolve
greek.use_lsj()              # one-time fetch of the ~15 MB prebuilt index, cached; then instant

greek.gloss("ἀνδρός")         # 'ἀνήρ: man, opp. god, …'        (lemmatized ἀνδρός → ἀνήρ)
greek.gloss("γυναικός")       # 'γυνή: wife, spouse, …'
greek.gloss("βάλλω")          # 'βάλλω: Act. , throw:'

entry = greek.lookup("λόγος")  # the full structured entry
entry.headword               # 'λόγος'
len(entry.senses)            # 64
entry.senses[0].marker, entry.senses[0].text[:40]   # ('I', 'computation, reckoning …')
```

The CLI `gloss` activates the index automatically (so it triggers the fetch) and
prints the one-liner; pass a form and it is lemmatized first:

```bash
aegean greek gloss "λόγου"      # λόγος: computation, reckoning (cf. λέγω (B) II).
```

`lookup` returns an `LSJEntry` (`headword`, `senses` of `Sense(marker, level, text)`,
`lead`, `short`); `gloss` is the concise one-liner (`headword: <first English sense>`).
Beta Code in the source is converted to Unicode, and citations are compacted into the
sense text. The short gloss is best-effort: for a few entries (e.g. cross-reference
headwords) it can still lead with a variant; use `lookup` for the full picture.

The LSJ is **CC BY-SA 4.0** (Perseus Digital Library), fetched to your cache and never
bundled: see [Data & Provenance](Data-and-Provenance#the-greek-lexicon-lsj-lsj-index-use_lsj).
`greek.disable_lsj()` turns it back off.

### More dictionaries: the lexicon registry

`use_lsj` and `use_dodson` are two backends in a small **registry** of dictionaries.
`greek.lexica()` lists what is available; `greek.use_lexicon(id)` activates a hosted one;
and `greek.gloss(word, dictionary=id)` / `greek.entry(word, dictionary=id)` resolve a word
against a chosen dictionary (with no `dictionary=`, the first active one). Inflected forms
lemmatize on a miss, exactly as with LSJ.

```python
greek.lexica()                       # every dictionary: id, scope, license, hosted vs link

greek.use_lexicon("middle-liddell")  # the concise Intermediate Lexicon (classical)
greek.gloss("λόγος", dictionary="middle-liddell")
# 'λόγος: λόγος, ὁ, λέγω (A) the word or that by which the inward thought is expressed, …'

greek.use_lexicon("cunliffe")        # Cunliffe, A Lexicon of the Homeric Dialect
greek.gloss("μῆνις", dictionary="cunliffe")
# 'μῆνις: μῆνις ἡ. 1 Wrath, ire : μῆνιν ἄειδε Ἀχιλῆος Il. 1.1. …'

greek.use_lexicon("abbott-smith")    # Abbott-Smith, A Manual Greek Lexicon of the NT
greek.gloss("πίστις", dictionary="abbott-smith")
# 'πίστις: faith; belief; trust; confidence; the faith; fidelity; …'

greek.entry("λόγος", dictionary="cunliffe").body   # the full entry text
```

The hosted dictionaries:

| id | dictionary | scope |
| --- | --- | --- |
| `lsj` | Liddell-Scott-Jones | classical (full) |
| `middle-liddell` | An Intermediate Greek-English Lexicon | classical (concise) |
| `cunliffe` | A Lexicon of the Homeric Dialect | Homeric |
| `abbott-smith` | A Manual Greek Lexicon of the New Testament | Koine / NT |
| `dodson` | Dodson Greek Lexicon | Koine / NT (bundled) |

Each (except the bundled Dodson) is fetched to your cache on first use and built into a
lemma→entry index, never bundled: sources and licenses are in
[Data & Provenance](Data-and-Provenance).

**Dictionaries pyaegean cannot host** (Autenrieth, Slater, Montanari, DGE, Bailly, …) are
reachable as deep-links. `greek.lexicon_link(word)` builds a
[Logeion](https://logeion.uchicago.edu/) URL (or Perseus, with `service="perseus"`),
lemmatizing the word first; Logeion aggregates all of those dictionaries.

```python
greek.lexicon_link("λόγος")   # 'https://logeion.uchicago.edu/λόγος'  (percent-encoded for the browser)
```

From the shell:

```bash
aegean greek lexica                          # list the dictionaries
aegean greek gloss μῆνις --dict cunliffe     # gloss from a chosen dictionary
aegean greek lexicon-link μήνιδος            # a Logeion deep-link to the lemma
```

### Dialect and register tags

LSJ marks a word's **dialect** (Doric, Attic, Ionic, Aeolic, Epic, …) and its **register**
(poetic, medical, comic, tragic, …) with standard abbreviations in the entry text.
`greek.usage(word)` reads those off the active LSJ entry against a curated abbreviation map
and returns a `UsageInfo` with `dialects` and `registers` tuples (so it requires
`greek.use_lsj()`):

```python
greek.use_lsj()

u = greek.usage("θάλασσα")
u.dialects, u.registers       # the dialect/register tags LSJ records for the entry
bool(greek.usage("xyz"))      # False — empty UsageInfo when there is no entry or no tag
```

A `UsageInfo` is falsy when both tuples are empty, so `if greek.usage(word):` tests whether
LSJ recorded anything. From the shell:

```bash
aegean greek usage "θάλασσα"        # the dialect/register tags (--json for the record)
```

This is a **heuristic**: it matches the abbreviation tokens in the flattened entry text, so
it surfaces what LSJ records without resolving every nuance (an abbreviation that doubles as
a citation marker can occasionally slip through).

## The Greek New Testament (Koine)

`greek.load_nt` loads the **Nestle 1904** Greek NT as an annotated `Corpus`: the Koine
counterpart to `load_work`. Every token carries a gold **lemma**, a Robinson **morph**
parse, a **Strong's** number, a reconciled UD **upos**, the **normalized** form, and a
**gloss** in `Token.annotations` (so `to_dataframe(level="token")` surfaces them as columns):

```python
from aegean import greek

nt = greek.load_nt("John", ref="1.1-1.5")     # a name/abbrev + load_work-style ref
tok = nt.documents[0].tokens[1]
tok.text, tok.annotations["lemma"], tok.annotations["morph"], tok.annotations["strongs"]
# ('ἀρχῇ', 'ἀρχή', 'N-DSF', '746')

greek.load_nt("Romans", ref="8")               # a whole chapter; ref="8.28" a verse
greek.load_nt()                                # the whole 27-book NT
```

`load_nt(book, *, ref=None, force=False)`. `book` accepts names or abbreviations
(`John`/`Jn`, `1Cor`, `Rev`); `ref` mirrors `load_work` (`"3"` chapter, `"3.16"`
verse, `"3.16-18"` range). The base text is public domain and the
morphology/lemmas/Strong's are CC0, so **one book is bundled** (works offline) and
the full corpus fetches to cache on demand.

A token-level dataframe puts every annotation in its own column:

```python
nt = greek.load_nt("John", ref="1.1-1.2")
nt.to_dataframe(level="token").columns.tolist()
# ['lemma','morph','strongs','normalized','upos','ref','gloss','doc_id','line_no','position','text','kind','site','period']
```

**Koine glossing** comes from the bundled Dodson lexicon (CC0): the Koine
counterpart to `use_lsj`, and **no download** (it is CC0 and bundled):

```python
greek.use_dodson()
greek.gloss_strongs("3056")   # 'a word, speech, divine utterance, analogy'
greek.gloss_nt("ἀγάπη")       # 'love'  (lemmatizes + accent-folds on a miss)

entry = greek.lookup_nt("λόγος")
entry.strongs, entry.lemma, entry.gloss
# ('3056', 'λόγος', 'a word, speech, divine utterance, analogy')
```

A `DodsonEntry` has four fields: `strongs`, `lemma`, `gloss` (the one-liner), and
`definition` (the fuller text). The CLI `gloss-nt` activates Dodson for you:

```bash
aegean greek gloss-nt "ἀγάπη"                 # love
aegean greek gloss-nt --strongs "3056"        # a word, speech, divine utterance, analogy
aegean greek gloss-nt --full "λόγος"          # λόγος (G3056): a word, speech, divine utterance, analogy.
```

The NT corpus self-glosses from the same lexicon, so each token already carries a
`gloss` annotation offline.

**Measuring the model on the NT.** `greek.evaluate_on_nt()` (CLI `aegean greek eval nt`)
scores the neural pipeline against the Nestle 1904 gold (lemma + reconciled UPOS): a
Nestle-own-gold complement to the PROIEL out-of-AGDT check, and both are genuinely
out-of-domain (the models train on AGDT + Gorman + Pedalion). The measured numbers and
the honesty notes (lemma-convention differences; why finer features aren't
cross-comparable) are in
[`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md).

## Terminology rarity

How unusual is a text's vocabulary, measured against a reference corpus? Rare, technical,
or documentary terms are where a translator (human or model) is most likely to stumble, so
`greek.terminology_rarity(text, corpus)` is a cheap, offline, deterministic
*translation-difficulty* signal: it scores each content word by its lemma's frequency in
the reference corpus on a log scale, and averages.

Rarity is always **relative to the corpus you pass**. Score against the Greek NT and a
word's rarity reflects how unusual it is in Koine; score against a tragedy and it reflects
that register. Pass any `Corpus` (or `QueryResults`); the NT is a natural reference, and its
gold lemma annotations are used directly:

```python
nt = greek.load_nt()                      # the reference corpus
r = greek.terminology_rarity("ἐν ἀρχῇ ἦν ὁ λόγος", nt)

r.overall                                 # mean word rarity, 0 (easy) .. 1 (all-rare)
r.corpus_lemmas, r.corpus_tokens          # the size of the frequency basis
[(w.word, w.label) for w in r.hardest(3)] # the three rarest words, rarest first
```

Each `WordRarity` carries the surface `word`, its `lemma`, the lemma's `count` in the
reference corpus, a `rarity` (0 = as common as the corpus's most frequent lemma, 1 =
absent), and a `label` (`absent` / `hapax` / `rare` / `uncommon` / `common`).
`RarityResult.hardest(n)` returns the `n` rarest words, most rare first, to surface the
terms worth grounding. From the shell (`--corpus nt` uses the NT, or pass a corpus path):

```bash
aegean greek rarity "ἐν ἀρχῇ ἦν ὁ λόγος" --corpus nt --top 3
```

This is **exploratory**: a rarity score is a difficulty signal, not a measured accuracy,
and it only means as much as the corpus you score against is representative.

## Loading real works

`greek.load_work` fetches a real Greek work from Perseus (canonical-greekLit /
First1KGreek), parses the TEI into one document per book/chapter, or, with `ref`,
just the section you ask for. The full corpus story (refs, editions, sources,
export) is on [Greek Works and Books](Greek-Works-and-Books); here is the shape:

```python
# heavy / network on first use — fetches the TEI to the cache (pinned, reproducible)
work = greek.load_work("tlg0012.tlg001", ref="1.1-1.10")   # Iliad, first ten lines
```

`load_work(work, *, ref=None, source="auto", edition=None, force=False)`:

| Parameter | Meaning |
| --- | --- |
| `work` | CTS-style id, e.g. `tlg0012.tlg001` (the Iliad) |
| `ref` | `"1"` book, `"1.2"` chapter, `"1.1-1.50"` line range |
| `source` | `"auto"` (try both), `"perseus"`, or `"first1k"` |
| `edition` | pick a specific edition file when a work has several |
| `force` | re-fetch even if cached |

From the shell, `aegean greek work` mirrors it (with `--ref`, `--source`,
`--edition`, `--output`/`-o`, `--json`):

```bash
aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

The texts are **CC BY-SA**, fetched to the cache and never bundled.

## Discovering works and books

You don't have to memorise ids. Three helpers list a verified, loadable catalogue:
fully offline, no network.

```python
greek.popular_works()   # list of {'id','author','title'} — 25 well-known works
# [{'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad'}, …]

greek.catalog()         # the FULL discovery index — 1778 works, with Greek titles
# [{'id': 'tlg0001.tlg001', 'author': 'Apollonius Rhodius', 'title': 'Argonautica',
#   'greek_title': 'Argonautica', 'source': 'perseus'}, …]
len(greek.catalog(author="plato"))     # 39   — filter by author/title/source/free-text

greek.nt_books()        # list of {'name','aliases'} — all 27 NT books
# [{'name': 'Matt', 'aliases': ['matthew','matt','mt']}, …]
```

```bash
aegean greek works              # a table of the 25 works + how to load one (--json for the list)
aegean greek catalog --author plato   # search the full 1778-work index (--json for the list)
aegean greek nt-books           # a table of the 27 books and the names load_nt accepts
```

`works` is a curated starting point; `catalog` is the full 1,778-work discovery
index (768 Perseus + 1,010 First1KGreek). Either way `load_work` /
`aegean greek work` take **any** Perseus canonical-greekLit / First1KGreek id
(browse them at scaife.perseus.org). The full work catalogue and every NT book
alias are tabulated on [Greek Works and Books](Greek-Works-and-Books).

## The sample corpus

`aegean.load("greek")` loads a handful of public-domain Archaic→Koine passages
(Homer, Herodotus, Heraclitus, Sappho, John 1:1) to exercise the pipeline: no
network needed.

```python
import aegean
g = aegean.load("greek")
len(g)                                  # 5
iliad = g.get("iliad-1.1")
[t.text for t in iliad.words]
iliad.meta.scribe, iliad.meta.period    # ('Homer', 'Archaic (epic)')
dict(g.word_frequencies())["λόγος"]     # 2  (John 1:1 sample)
```

The Greek `Script` also exposes the pipeline as a capability:

```python
script = aegean.get_script("greek")
script.nlp.syllabify("ἄνθρωπος")        # ['ἄν', 'θρω', 'πος']
```

## Importing your own text

`load_work` and `load_nt` pull *published* corpora; to run the pipeline over your
**own** Greek (a passage you typed, a folder of `.txt` files, a CSV of lines)
turn it into a `Corpus` first with `aegean.io`. A Greek/NT `script_id` routes the
text through the Greek tokenizer (so punctuation is stripped); any other script
falls back to whitespace splitting.

```python
from aegean.io import from_text

corpus = from_text("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος", doc_id="iliad-1.1")
[t.text for t in corpus.documents[0].words]
# ['μῆνιν', 'ἄειδε', 'θεὰ', 'Πηληϊάδεω', 'Ἀχιλῆος']  ← ready for the whole pipeline
```

`split` (`"whole"` / `"paragraph"` / `"line"`) controls how a longer text is cut
into documents. The siblings read from disk: `from_text_file(path, …)`,
`from_text_dir(path, glob="*.txt", …)`, and `from_csv(path, text_col="text",
id_col=None, …)`. All are **offline**.

From the shell, `aegean import` does the same and writes a reusable corpus, which
every other command then accepts:

```bash
aegean import myplato.txt -o myplato.json   # then: aegean stats myplato.json
aegean import poems/ -o corpus.db --split line
aegean import rows.csv -o corpus.json --text-col line --id-col id
```

A `.txt` or `.csv` can't be handed straight to a corpus command: import it first.
(`aegean stats foo.txt` says exactly that, and names the importer.) Full details
are on [Greek Works and Books](Greek-Works-and-Books) and [CLI](CLI).

## Benchmark harness

`aegean.greek.benchmark` scores the pipeline against a small bundled gold set, so
you can track how its Greek coverage is doing over time. The gold is **hand-authored
and independent**: correct answers stated from scholarship, never read off any
engine, which is what makes the comparison below fair.

```python
from aegean.greek import benchmark
for stage, s in benchmark.run_benchmark().items():
    print(s)
# betacode:   100% (9/9)
# tokenize:   100% (5/5)
# syllabify:  100% (6/6)
# accent:     100% (6/6)
# lemma:       28% (5/18)    ← seed table only; misses irregular / 3rd-declension forms
# pos:         50% (10/20)   ← suffix heuristic misses open-class words
# scansion:   100% (5/5)
# morphology:  73% (8/11)
```

### The treebank backend's lift

`compare_modes()` scores lemma + POS with the
[treebank backend](#treebank-backed-mode-opt-in) **off vs on** (it activates
`use_treebank()` for you, fetching the prebuilt lexicon on first use):

```python
benchmark.compare_modes()
# baseline : lemma  28% (5/18)   · pos  50% (10/20)
# treebank : lemma 100% (18/18)  · pos 100% (20/20)
```

On this gold set the treebank lifts lemma **28% → 100%** and POS **50% → 100%**
(morphology recall **73% → 100%**). The set is deliberately weighted toward the
irregular, third-declension and open-class forms that separate the engines, and
each item is attested in the AGDT, so it measures the win *where it applies*; on
genuinely unattested forms the treebank falls back to the baseline.

### Benchmark your own pipeline

`compare_lemmatizers` and `compare_pos_taggers` take **any** lemma-or-POS callable you supply
and score it on the same bundled gold set, so you can measure an external pipeline on identical
items. The gold set is small (18 lemma / 20 POS items) and weighted toward *attested* forms, so
it measures lexical coverage, **not** generalization to unseen text, for which the held-out
evaluations below are the relevant measure.

### Held-out generalization

The [generalizing tagger](#generalizing-pos-tagger-opt-in) is measured on a leakage-free 90/10
AGDT sentence split, scored *in context* on ≈54k tokens, with the **unseen-form** subset (forms
absent from training) called out separately:

| POS: held-out AGDT | overall | unseen forms |
| --- | --- | --- |
| pyaegean tagger (pure Python) | 84.4% | 83.6% |

The AGDT is the tagger's own training source, so the **unseen-form** column is the honest
generalization measure: **83.6%** from a zero-dependency, pure-Python model. A fully neutral
check, on text pyaegean never trained on, is the
[out-of-AGDT evaluation](#neutral-evaluation-out-of-agdt) below.

The same evaluation for **lemmatization** (the
[generalizing lemmatizer](#generalizing-lemmatizer-opt-in), scored with predicted POS):

| lemma: held-out AGDT | overall | unseen forms |
| --- | --- | --- |
| pyaegean lemmatizer (pure Python, edit-tree) | 84.5% | 40.3% |
| **pyaegean `[neural]` (GreTa seq2seq, opt-in)** | **~92%** | **76.3%** |

The pure-Python lemmatizer is solid overall but trails on **unseen** forms, where recovering a
lemma (often an accent/stem change, not just a suffix swap) is hardest. The opt-in
**[neural] backend** reaches **76.3% on unseen forms** with a GreTa seq2seq that *generates* the
lemma, and ships as a hybrid (the gold lookup answers seen forms, the seq2seq the rest), so
overall lemma accuracy lands around **92%**. It is a fetched-to-cache ONNX model behind the
`[neural]` extra (onnxruntime, no torch); the pure-Python edit-tree stays the zero-dependency
default. See [Neural lemmatizer (opt-in)](#neural-lemmatizer-opt-in) above.

### Neutral evaluation (out-of-AGDT)

The held-out numbers above are leakage-free *within* the AGDT, but pyaegean's backends are
all built from the AGDT, so they don't show how the system fares on text from a different
source. `greek.evaluate_on_proiel()` (CLI `aegean greek eval proiel`) scores the active
pipeline (`lemmatize` + `pos_tag`) against the **PROIEL treebank** (the Greek New Testament
and Herodotus) which none of pyaegean's models have ever seen, so every form is a genuine
generalization test.

```python
from aegean import greek
greek.use_treebank(); greek.use_neural_lemmatizer()   # measure the full pipeline
greek.evaluate_on_proiel()        # {'lemma': …, 'pos': …, 'n': …} over the PROIEL gold
```

PROIEL is fetched to the cache on first use (CC BY-NC-SA 3.0: **evaluation only, never
bundled**, like the AGDT). Lemma accuracy is the clean metric (lemmas compared after Unicode
normalization and dropping PROIEL's `#N` homograph suffix); POS is compared under a reconciled
tagset (PROIEL's PROPN/SCONJ collapse to pyaegean's NOUN/CCONJ, so the figure reflects real
errors, not convention gaps). This is a neutral test **for pyaegean specifically**: PROIEL is
in-training for some other systems, so it is not a level field for cross-tool comparison; it
answers "how well does pyaegean read Greek it never trained on."

**Where the gap comes from.** The model is trained on the AGDT convention, so scoring it on
the differently-annotated PROIEL conflates real mistakes with convention differences.
`greek.proiel_drift()` (CLI `aegean greek eval proiel --drift`) re-tags the same gold and
returns a `DriftReport` that separates the two: the gold→predicted POS confusion matrix
(most-frequent first), a sample of lemma mismatches, and the scored counts.

```python
report = greek.proiel_drift()
print(report.summary())     # the top POS confusions, gold → predicted, with their share
report.top_share            # fraction of POS errors in the single most common pair
```

`.summary()` prints a short, readable breakdown; a high `top_share` (most POS errors
concentrated in a few pairs) points to a systematic convention difference rather than
scattered real error. `evaluate_on_proiel` is unchanged: `proiel_drift` only explains its
gap.

Pass your own gold (same schema as the bundled `benchmark_gold.json`) to any
scorer: `score_lemmatizer`, `score_pos`, `compare_lemmatizers`,
`compare_pos_taggers`, or `compare_modes`.

### Standard-benchmark evaluation (Universal Dependencies)

`greek.evaluate_on_ud(treebank, split)` scores the active pipeline on the **Universal
Dependencies** Ancient Greek test folds (Perseus / PROIEL) with the **official CoNLL 2018
evaluator**: the protocol the field's published numbers use. The folds are CC BY-NC-SA,
fetched to the cache for *evaluation only* (never trained on); `greek.agdt_ud_overlap()`
builds the manifest of AGDT sentences that appear in the UD folds, which pyaegean's model
training excludes. The full protocol, leakage controls, and measured numbers live in
[`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md).

```python
greek.use_treebank(); greek.use_tagger(); greek.use_lemmatizer(); greek.use_parser()
greek.evaluate_on_ud("proiel", "test")   # {'upos': …, 'lemma': …, 'uas': …, …}
```

### Evaluation receipts

A score is only reproducible if you know what produced it. `greek.eval_receipt`
wraps a scores dict in a **content-addressed, tamper-evident** record that ties the
result to its inputs: the package version, the data manifest, the active model id,
the treebank, the split, and the protocol. The `id` is a short sha256 over the
canonical JSON of every field, so identical inputs always give the identical id and
changing any field changes it.

```python
scores = greek.evaluate_on_ud("perseus", "test")   # or any metric → value mapping
r = greek.eval_receipt(scores, treebank="perseus", split="test", protocol="conll18")

r.id                       # e.g. 'a15940ec010157d0' — the content hash of the whole record
r.verify()                 # True — re-hashes the stored fields and confirms they still produce r.id
r.package_version, r.model_id   # resolved automatically from the environment
```

An `EvalReceipt` is frozen and serializes both ways: `r.as_dict()` / `r.as_json()`
write the full record (id included), and `EvalReceipt.from_dict(data)` reads it
back. `r.verify(other)` confirms two receipts describe the byte-identical
evaluation (same content-addressed id), so a number quoted in a paper can be
checked against the receipt that produced it. Pass `package_version=` /
`manifest=` / `model_id=` to override the resolved environment for a fully
deterministic, offline receipt; `extra=` carries any further reproducibility
metadata (a seed, the evaluator sha, a fold manifest).

### Reproduce the numbers from the shell

`aegean greek eval TARGET` reproduces any of the measured figures with the official
evaluators and the fetched gold data. The targets:

| `eval` target | What it measures |
| --- | --- |
| `ud` | active pipeline on a UD fold (CoNLL 2018 evaluator); `--fold perseus|proiel`, `--split dev|test` |
| `proiel` | the neutral out-of-AGDT check (lemma + POS); `--drift` for the convention-vs-error breakdown |
| `nt` | the neural pipeline against the Nestle 1904 gold |
| `tagger` | the held-out AGDT POS evaluation |
| `lemmatizer` | the held-out AGDT lemma evaluation |
| `parser` | the held-out AGDT dependency evaluation |

The backend flags (`--neural`, `--tagger`, `--lemmatizer`, `--neural-lemmatizer`)
choose which pipeline is scored. These are **heavy** (they fetch gold data and may
train), so run them only when you want to reproduce a number.

## Limitations & notes

The honest scope: the rule-based morphology is a high-precision baseline over the
*regular* paradigms (athematic/contract/irregular forms need the treebank); the
arc-eager parser is projective-only (Greek is ~31% projective; use the neural
parse for research); the IPA is a reconstruction with judgement calls; scansion
covers dactylic/elegiac/iambic and the aeolic lyric lines but not dactylo-epitrite
or free astrophic lyric, and synizesis is lexical, never guessed. The full list,
with the reasoning, is on [Limitations](Limitations). For the data licences and
provenance of every fetched backend, see
[Data & Provenance](Data-and-Provenance).
