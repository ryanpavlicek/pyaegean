# Greek NLP

`aegean.greek` is the Ancient Greek NLP pipeline — a set of composable,
individually-callable stages. v0.1 ships the foundation; deeper stages (full
morphology, POS, dependency parsing, prosody, LSJ) land across later versions.

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

Baseline scope: quantities are computed within a single word — *correptio Attica*
(short vowel before mute+liquid) is always counted heavy-by-position, and
word-final length in context isn't resolved. These are leads for full metrical
scansion, not a finished scanner.

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
