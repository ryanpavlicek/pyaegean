# Linear B

Linear B is the **deciphered** Aegean syllabary — it writes Mycenaean Greek, the earliest
attested form of the language. pyaegean reads it through the same `Script` plugin model as
Linear A: a sign inventory, transliteration to phonetics, a bridge into the Greek track, and the
accounting reconciliation. Because Linear B is read, the work here is verifiable rather than
exploratory.

```python
import aegean
from aegean.scripts.linearb import word_to_phonetic, greek_reading

aegean.registered_scripts()              # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
word_to_phonetic("QA-SI-RE-U")           # 'kwasireu'  (gʷasileus, the ancestor of βασιλεύς)
greek_reading("PO-ME")                   # ('ποιμήν', 'shepherd')
```

## Sign inventory

The inventory is built from the Unicode Character Database — the Linear B Syllabary and Ideograms
blocks — so it is authoritative and freely licensed (see [Data & Provenance](Data-and-Provenance)).
It holds **211 signs**: 74 syllabograms (each with its phonetic value), 14 still-undeciphered
symbols, and 123 ideograms/monograms for commodities (grain, wine, oil, people, livestock…). Every
sign keeps its **Bennett number** (`B008`, `B131`) and its Unicode name.

```python
from aegean.core.script import get_script

inv = get_script("linearb").sign_inventory
ka = next(s for s in inv if s.label == "KA")
ka.glyph, ka.phonetic, ka.attrs["bennett"]   # ('𐀏', 'ka', 'B077')
```

## Transliteration → phonetics

`word_to_phonetic` converts a hyphenated transliteration to a phonetic Latin form, with the
labiovelar (`qa → kwa`) and affricate (`za → dza`) values. The complex signs `a2`/`a3`/`pu2` are
kept distinct from `a`/`pu`.

```python
word_to_phonetic("WA-NA-KA")   # 'wanaka'   (ϝάναξ, "king")
word_to_phonetic("TI-RI-PO-DE")# 'tiripode' (τρίποδε, "two tripods")
word_to_phonetic("WO-NO")      # 'wono'     (ϝοῖνος → οἶνος, "wine")
```

## Bridge to Greek

Linear B *is* Greek, so a transliterated word resolves to its Classical Greek lemma and meaning.
`greek_reading` returns `(lemma, gloss)` from a curated lexicon of the well-established equations;
pass the lemma on to the [LSJ backend](Greek-NLP#lexicon-lsj-glossing-opt-in) for the full entry.

```python
from aegean.scripts.linearb import greek_reading, gloss

greek_reading("WA-NA-KA")   # ('ἄναξ', 'king, lord (wanax)')
greek_reading("TE-O")       # ('θεός', 'god')
gloss("DO-E-RO")            # 'slave, servant (male)'   (δοῦλος)

# with the LSJ lexicon active, get the full dictionary entry for the reading:
import aegean
aegean.greek.use_lsj()
lemma, _ = greek_reading("PO-ME")
aegean.greek.gloss(lemma)   # 'ποιμήν: herdsman, shepherd …'
```

## Accounting

Linear B tablets are administrative records — names, commodity ideograms, and numerals, often
with a `to-so`/`to-sa` (τόσος, "so much") total. The script-agnostic accounting engine reads them
directly, using Linear B's total markers in place of Linear A's `KU-RO`.

```python
from aegean.analysis import balance_check

corpus = aegean.load("linearb")
for doc in corpus:
    for chk in balance_check(doc):
        print(doc.id, chk.marker, chk.computed_sum, "==", chk.stated_total, chk.balances)
```

The reconciliation is heuristic — section boundaries are inferred — so a balance is evidence, not
proof, exactly as for Linear A.

## The corpus

**No openly-licensed Linear B corpus exists.** The most complete one, DAMOS (Database of Mycenaean
at Oslo), is CC BY-NC-SA, and LiBER is all-rights-reserved — neither can be redistributed in an
Apache-2.0 package. So pyaegean bundles only a **small illustrative sample** (PY Ta 641, the tablet
that confirmed Ventris's decipherment; PY Er 312) and leaves the full corpus **bring-your-own**.

Point pyaegean at your own licensed EpiDoc export (e.g. a DAMOS download) and it parses it locally,
never re-hosting:

```bash
pip install "pyaegean[epidoc]"                 # the EpiDoc reader (lxml)
export PYAEGEAN_LINEARB_CORPUS=/path/to/damos   # a file or directory of EpiDoc XML
```

```python
aegean.load("linearb")                          # now loads your corpus
# or explicitly:
from aegean.scripts.linearb import load_epidoc_corpus
load_epidoc_corpus("/path/to/damos")
```
