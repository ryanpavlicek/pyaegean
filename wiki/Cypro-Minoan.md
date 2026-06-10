# Cypro-Minoan

Cypro-Minoan is the **undeciphered** writing system of Bronze Age Cyprus (c. 1550–1050 BC), found on
clay balls, cylinders, and tablets at sites such as Enkomi and (in a variant) Ugarit. It descends
from Linear A and is structurally a syllabary, but its phonetic values are unknown and the language
behind it is unidentified. pyaegean treats it like Linear A: a sign inventory and tokenization for
exploratory work, with **no** transliteration, lexicon, or Greek bridge — there are no settled sound
values to offer.

```python
import aegean
from aegean.core.script import get_script

aegean.registered_scripts()                       # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
len(list(get_script("cyprominoan").sign_inventory))  # 99
```

## Sign inventory

Built from the Unicode "Cypro-Minoan" block (U+12F90–U+12FF2) — **99 signs**, each identified only by
its conventional number (`CM001`, `CM002`, …) and glyph. Because the script is undeciphered, every
sign's `phonetic` value is `None`; the inventory is a catalogue of distinct signs, not a syllabary
with sounds.

```python
inv = list(get_script("cyprominoan").sign_inventory)
inv[0].label                       # 'CM001'
all(s.phonetic is None for s in inv)  # True
```

## Tokenization

A Cypro-Minoan "word" is written as a sequence of sign numbers joined by hyphens
(`CM005-CM023-CM002`). `tokenize` splits the text and decomposes each hyphenated group into its
signs; a lone sign is left `UNKNOWN`, since there is no reading to resolve.

```python
toks = get_script("cyprominoan").tokenize("CM005-CM023-CM002")
toks[0].signs                      # ('CM005', 'CM023', 'CM002')
```

## The corpus

The edited Cypro-Minoan corpus (Enkomi/Ugarit; Ferrara's *Cypro-Minoan Inscriptions*) is not openly
redistributable, and sign readings are contested. Only a small **illustrative sample** of sign
sequences is bundled (`Corpus.load("cyprominoan")`) — chosen to exercise the model, not transcriptions
of specific inscriptions. The sign inventory is the shippable core.

```python
corpus = aegean.load("cyprominoan")
[doc.id for doc in corpus]         # ['cm-enkomi-ball', 'cm-ugarit-tablet']
```

## Why no Greek bridge

Linear B and the Cypriot syllabary are deciphered, so pyaegean can transliterate them and map words to
Greek lemmas. Cypro-Minoan is not — proposed decipherments exist but none is accepted, and even the
total number of distinct signs is debated. Offering phonetic values or "readings" would be
speculation dressed as fact, so the plugin deliberately stops at the sign level. This mirrors how the
toolkit treats [Linear A](Linear-A): structure and signs, clearly labeled exploratory.

## Provenance

The sign data comes from the Unicode Character Database (Unicode-3.0 license) — see
[Data & Provenance](Data-and-Provenance) and `NOTICE`.
