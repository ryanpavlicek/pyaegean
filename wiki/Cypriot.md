# Cypriot syllabary

The Cypriot syllabary wrote Greek — the Arcado-Cypriot dialect — from roughly the 11th to the 4th
century BC. Like Linear B it is **deciphered**, and pyaegean reads it through the same plugin
model: a sign inventory, transliteration to phonetics, and a bridge into the Greek track.

```python
import aegean
from aegean.scripts.cypriot import word_to_phonetic, greek_reading

aegean.registered_scripts()          # ['cypriot', 'greek', 'lineara', 'linearb']
word_to_phonetic("PA-SI-LE-U-SE")    # 'pasileuse'  (βασιλεύς, "king")
greek_reading("WA-NA-SA")            # ('ἄνασσα', 'queen, lady (the Paphian goddess)')
```

## Sign inventory

Built from the Unicode "Cypriot Syllabary" block (U+10800–U+1083F) — **55 syllabograms**, each with
its settled phonetic value. The script is more phonetically transparent than Linear B: it has no
labiovelars, and the transliteration already sits close to the spoken Greek.

```python
from aegean.core.script import get_script

len(list(get_script("cypriot").sign_inventory))   # 55
```

## Transliteration and the Greek bridge

`greek_reading` returns `(lemma, gloss)` from a curated lexicon of well-established Cypriot
equations; pass the lemma to the [LSJ backend](Greek-NLP#lexicon-lsj-glossing-opt-in) for the full
dictionary entry.

```python
word_to_phonetic("A-PO-LO-NI")   # 'apoloni'  (Ἀπόλλωνι, "to Apollo")
greek_reading("KA-SE")           # ('καί', 'and (Arcado-Cypriot κάς)')
greek_reading("TU-KA")           # ('τύχη', 'fortune (Cypriot τύχα)')
```

## The corpus

The Cypriot epigraphic corpus (ICS, Masson) is not openly redistributable, so only a small
**illustrative sample** is bundled (`Corpus.load("cypriot")`). The sign inventory and
transliteration are the shippable core; a fuller corpus is a future bring-your-own addition.

## Provenance

The sign data comes from the Unicode Character Database (Unicode-3.0 license) — see
[Data & Provenance](Data-and-Provenance) and `NOTICE`.
