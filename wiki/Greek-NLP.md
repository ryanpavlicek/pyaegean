# Greek NLP

`aegean.greek` is the Ancient Greek NLP pipeline. It's a set of small, independent
steps: each one is a plain function you can call on its own, and you can chain
them into your own pipeline. Nothing here requires an internet connection or an
API key.

v0.1 ships normalization, tokenization, syllabification, accent and prosody
analysis, reconstructed IPA, **metrical scansion** (dactylic hexameter and elegiac
pentameter), POS tagging, a baseline lemmatizer, and a rule-based **morphological
analyzer**. Deeper stages — a treebank-derived lemmatizer/morphology, dependency
parsing, and LSJ glossing — land in later versions (see the [roadmap](Home#roadmap)).

Every example below is real, runnable output. Import the module once:

```python
from aegean import greek
```

## Normalization & Beta Code

Beta Code is the ASCII transliteration of polytonic Greek used by the TLG and
Perseus. Conversion is round-trip-safe and emits precomposed NFC.

```python
greek.betacode_to_unicode("mh=nin")      # 'μῆνιν'
greek.betacode_to_unicode("lo/gos")      # 'λόγος'   (context-sensitive final ς)
greek.betacode_to_unicode("tw=|")        # 'τῷ'      (iota subscript)
greek.unicode_to_betacode("Ἀχιλῆος")     # '*a)xilh=os'

greek.normalize("ό")               # 'ό'   (NFC by default)
greek.strip_diacritics("ἄνθρωπος")       # 'ανθρωπος'
```

Supported Beta Code: the 24 letters (`*` marks capitals, `s1/s2/s3` sigma
variants) and the diacritics — smooth `)` / rough `(` breathings, acute `/`,
grave `\`, circumflex `=`, diaeresis `+`, iota subscript `|`.

## Tokenization

```python
greek.tokenize_words("ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός.")
# ['ἐν', 'ἀρχῇ', 'ἦν', 'ὁ', 'λόγος', 'καὶ', 'θεός']

greek.tokenize("λόγος, καί")     # [Token('λόγος', WORD), Token(',', PUNCT), Token('καί', WORD)]
greek.sentences("ἐν ἀρχῇ ἦν ὁ λόγος. καὶ θεός ἦν;")
# ['ἐν ἀρχῇ ἦν ὁ λόγος', 'καὶ θεός ἦν']
```

Elision apostrophes are kept inside a single token (`ποικιλόθρον’`).

## Syllabification

Rule-based: diphthong nuclei, "muta cum liquida" clusters that stay together,
doubled-consonant splits, and valid Greek onsets.

```python
greek.syllabify("λόγος")        # ['λό', 'γος']
greek.syllabify("ἄνθρωπος")     # ['ἄν', 'θρω', 'πος']
greek.syllabify("θάλασσα")      # ['θά', 'λασ', 'σα']
greek.syllabify("ποικιλόθρον")  # ['ποι', 'κι', 'λό', 'θρον']
```

## Accent analysis

```python
info = greek.accentuation("λόγος")
info.accent_type          # 'acute'
info.position_from_end    # 2   (1=ultima, 2=penult, 3=antepenult)
info.classification       # 'paroxytone'
info.syllables            # ('λό', 'γος')
```

Classifications: `oxytone` / `paroxytone` / `proparoxytone` (acute) ·
`perispomenon` / `properispomenon` (circumflex) · `barytone` (grave).

## Prosody (syllable quantity)

Classifies each syllable as **heavy** / **light** / **common** — the metrical
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

Baseline scope: these quantities are computed within a single word. To resolve a
syllable's quantity *in metrical context* — across word boundaries, with the
caesura and the ambiguities a verse line allows — use the **[metrical
scansion](#metrical-scansion)** below, which builds on this word-level view.

## Metrical scansion

Scan a line of verse into its feet. v0.1 covers the two dactylic meters of epic
and elegy: **dactylic hexameter** (the metre of Homer) and **elegiac pentameter**
(the second line of an elegiac couplet). The scanner resolves each syllable's
quantity *in context* — applying *correptio* (a long vowel shortened before
another vowel), treating muta-cum-liquida clusters as the ambiguity they are, and
counting position across word boundaries.

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

A line with spondees, and its caesura located by syllable index:

```python
sc = greek.scan_hexameter("πλάγχθη, ἐπεὶ Τροίης ἱερὸν πτολίεθρον ἔπερσεν")
sc.pattern                       # '—⏑⏑|——|—⏑⏑|—⏑⏑|—⏑⏑|—×'   (Odyssey 1.2)
sc.caesura                       # 'penthemimeral'
sc.syllables[sc.caesura_index]   # 'ἱ'   (the line breaks just before this syllable)
```

Elegiac pentameter (here Simonides' epitaph for the Spartan dead):

```python
sc = greek.scan_pentameter("κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι.")
sc.pattern        # '—⏑⏑|——|—|—⏑⏑|—⏑⏑|×'
[f.name for f in sc.feet]
# ['dactyl', 'spondee', 'longum', 'dactyl', 'dactyl', 'longum']
```

`scan_line(line, meter)` dispatches by name (`"hexameter"` / `"pentameter"`), and
a `LineScansion` carries `.line`, `.meter`, `.feet`, `.syllables`, `.quantities`,
`.caesura`, `.caesura_index`, and `.ambiguous` (whether more than one scansion fit).

To inspect the *possible* quantities of each syllable before a metre is imposed —
useful for seeing where a line is genuinely ambiguous — use `syllable_options`:

```python
greek.syllable_options("πατρός")
# [('πα', ['heavy', 'light']), ('τρός', ['light'])]   ← πα is muta-cum-liquida: either
```

**An honest limitation: synizesis is not inferred.** When a line only scans if two
written vowels are read as one syllable (e.g. *Iliad* 1.1, where `Πηληϊάδεω` must
contract to `-δεω`), the scanner *declines* rather than guessing — it raises
`ScansionError` instead of forcing a fit:

```python
greek.scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")
# ScansionError: line does not scan as dactylic hexameter (17 syllables): ...
```

Iambic and lyric metres, and automatic synizesis, are planned for later versions.

## Phonology (reconstructed IPA)

Transcribe Greek to IPA for two periods — `"attic"` (Classical, default) and
`"koine"` (Hellenistic/Imperial).

```python
greek.to_ipa("θεός")               # 'tʰeos'   (Attic: aspirated θ)
greek.to_ipa("ὁ")                  # 'ho'      (rough breathing → /h/)
greek.to_ipa("ἄγγελος")            # 'aŋɡelos' (γγ → velar nasal)
greek.to_ipa("θεός", "koine")      # 'θeos'    (Koine: θ is a fricative)
greek.to_ipa("καί", "koine")       # 'ke'      (iotacism: αι → /e/)
```

Attic uses aspirated φ θ χ = /pʰ tʰ kʰ/, voiced stops β γ δ = /b ɡ d/, ζ = /zd/,
υ = /y/, distinctive vowel length, and rough breathing = /h/. Koine fricativizes
(φ θ χ = /f θ x/; β γ δ = /v ɣ ð/), is mid-iotacism (η, ει → /i/; αι → /e/), and
drops length and the breathings.

**Reconstructed and approximate** — several values (ε/η quality, the long
diphthongs, the date of iotacism) are scholarly judgement calls.

## POS tagging (baseline)

Coarse part-of-speech tags (Universal Dependencies inventory). Closed classes —
article, prepositions, conjunctions, particles, pronouns, and the εἰμί copula —
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

**Baseline scope:** closed classes are reliable; open-class precision is limited
(an open-class verb like ἄειδε falls back to NOUN). To fix this for attested forms,
switch on the [treebank backend](#treebank-backed-mode-opt-in) — with
`greek.use_treebank()` active, `pos_tag`/`pos_tags` return the gold AGDT tag for a
known form (e.g. ἔφη → VERB) before falling back to the heuristic. Tags:
`DET ADP CCONJ SCONJ PART PRON ADV NUM NOUN VERB ADJ PUNCT X` (treebank mode may
also emit `INTJ`).

## Morphological analysis

Given an inflected form, `analyze` returns the morphological readings its ending
implies — part of speech plus the relevant features (case/number/gender for
nouns; tense/voice/mood/person/number for verbs) — each with a reconstructed
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

Each reading is an `Analysis` with the lemma, the POS, and the individual feature
fields; `.features()` gives just the ones that apply:

```python
a = greek.analyze("λύεις")[0]
a.lemma, a.pos        # ('λυω', 'VERB')
a.features()          # {'number': 'sg', 'tense': 'pres', 'voice': 'act', 'mood': 'ind', 'person': '2'}
a.lemma_certain       # False  ← see "the lemma is honest about itself" below
```

Closed-class words (the article, prepositions, conjunctions, particles, pronouns)
come back as a single, confident reading:

```python
greek.analyze("ὁ")       # (Analysis(lemma='ὁ', pos='DET'),)
greek.analyze("καί")[0]  # κaí → CCONJ
```

Two convenience shortcuts when you don't need the full feature set:

```python
greek.lemmas("ἀνθρώπων")   # ['ἄνθρωπος']   (the distinct lemmas a form could belong to)
greek.best_pos("λύεις")    # 'VERB'         (the single most likely part of speech)
```

### The lemma is honest about itself

`Analysis.lemma_certain` tells you how much to trust the lemma. When the bundled
seed lexicon knows the form, you get the correctly **accented** lemma and
`lemma_certain=True`. When the form is regular but out-of-vocabulary, the lemma is
*reconstructed* from the ending — **unaccented** (accent recession can't be
derived from the ending alone) and flagged `lemma_certain=False`:

```python
[a for a in greek.analyze("ἀνθρώπων") if a.pos == "NOUN"][0].lemma   # 'ἄνθρωπος' (seed, certain)
[a for a in greek.analyze("ἵππον")   if a.pos == "NOUN"][0].lemma    # 'ιππος'   (reconstructed, uncertain)
```

### Scope and caveats

This is a **baseline** engine — high-precision on the *regular* paradigms it
encodes (the article and pronouns, the first and second declensions and common
third-declension endings, and **thematic** verbs in the present, imperfect, future
and sigmatic aorist indicative, plus common infinitives and the mediopassive
participle). Past tenses are augment-gated, and a dative singular is detected from
its iota subscript. Athematic, contract, irregular and suppletive forms (`εἶπον` →
`λέγω`) are beyond a purely rule-based reach and await the treebank-derived
lexicon. For ambiguous forms the feature analyses are **exploratory**: trust the
closed classes and the feature set; treat a single auto-picked reading with care.

### Treebank-backed mode (opt-in)

The baseline above is rule-based and fully offline. For *attested* forms you can
switch on a **treebank-derived lexicon** built from the Perseus Ancient Greek
Dependency Treebank (AGDT v2.1). It supplies correctly-**accented** lemmas and full
features — including the irregular, contract, athematic and third-declension forms
the rule engine can't reach:

```python
greek.use_treebank()         # one-time download (~75 MB) + build, cached; then instant

greek.lemmatize("ἄνδρα")      # 'ἀνήρ'      (3rd declension; the rule engine gives a bare stem)
greek.lemmatize("ἔφη")        # 'φημί'      (suppletive athematic verb)
greek.lemmatize("γυναικός")   # 'γυνή'
greek.lemmatize("πόλεως")     # 'πόλις'
greek.analyze("ἀνθρώπων")[0]  # ἄνθρωπος [NOUN gen pl masc]   (lemma_certain=True)
```

Once active, `lemmatize`/`analyze` prefer the treebank for known forms and fall
back to the rule/seed engine for the rest; `greek.disable_treebank()` restores the
default. Network is needed only on the first call. The treebank is **CC BY-SA 3.0**,
fetched to your cache and never bundled — see
[Data & Provenance](Data-and-Provenance#the-greek-treebank-lexicon-use_treebank).

## Benchmark harness

`aegean.greek.benchmark` scores the pipeline against a small bundled gold set, so
you can track how its Greek coverage is doing over time. The gold is **hand-authored
and independent** — correct answers stated from scholarship, never read off any
engine — which is what makes the comparison below fair.

```python
from aegean.greek import benchmark
for stage, s in benchmark.run_benchmark().items():
    print(s)
# tokenize:   100% (5/5)
# syllabify:  100% (6/6)
# accent:     100% (6/6)
# scansion:   100% (5/5)
# lemma:       28% (5/18)    ← seed table only; misses irregular / 3rd-declension forms
# pos:         50% (10/20)   ← suffix heuristic misses open-class words
# morphology:  73% (8/11)
```

### The treebank backend's lift

`compare_modes()` scores lemma + POS with the
[treebank backend](#treebank-backed-mode-opt-in) **off vs on** (it activates
`use_treebank()` for you, building the lexicon on first use):

```python
benchmark.compare_modes()
# baseline : lemma  28% (5/18)   · pos  50% (10/20)
# treebank : lemma 100% (18/18)  · pos 100% (20/20)
```

On this gold set the treebank lifts lemma **28% → 100%** and POS **50% → 100%**
(morphology recall **73% → 100%**). The set is deliberately weighted toward the
irregular, third-declension and open-class forms that separate the engines, and
each item is attested in the AGDT — so it measures the win *where it applies*; on
genuinely unattested forms the treebank falls back to the baseline.

### Comparing against CLTK

pyaegean doesn't depend on [CLTK](https://cltk.org) — the comparison takes a
lemmatize (or POS) callable that *you* supply. CLTK 2.x runs Ancient Greek through a
`stanza` (or LLM) backend, so a real run needs that installed:

```python
# pip install cltk stanza      # stanza pulls torch + downloads grc models on first run
from cltk import NLP
nlp = NLP(language_code="grc", suppress_banner=True)   # 2.x uses language_code=
def cltk_lemma(w): return nlp.analyze(text=w).words[0].lemma

benchmark.compare_lemmatizers(cltk_lemma)
benchmark.compare_pos_taggers(lambda w: nlp.analyze(text=w).words[0].upos)
```

Pass your own gold (same schema as the bundled `benchmark_gold.json`) to any
scorer — `score_lemmatizer`, `score_pos`, `compare_lemmatizers`,
`compare_pos_taggers`, or `compare_modes`.

## Lemmatization (baseline)

A small bundled form→lemma seed table with an identity fallback. This is a
**baseline** placeholder for v0.1; a real morphological analyzer lands later.

```python
greek.lemmatize("λόγου")          # 'λόγος'
greek.lemmatize("ἦν")             # 'εἰμί'
greek.lemmatize_verbose("ξενικον")  # ('ξενικον', False)  ← not in the seed table
```

## The sample corpus

`aegean.load("greek")` loads a handful of public-domain Archaic→Koine passages
(Homer, Herodotus, Heraclitus, Sappho, John 1:1) to exercise the pipeline.

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
