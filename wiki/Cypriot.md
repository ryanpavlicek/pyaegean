# Cypriot syllabary

The Cypriot syllabary wrote Arcado-Cypriot Greek from roughly the 11th to the
4th century BC, and also recorded **Eteocypriot**, the island's undeciphered
non-Greek language. The bundled *Inscriptiones Graecae* XV 1 corpus contains
both Greek and Eteocypriot inscriptions. Like [Linear B](Linear-B), the sign
values are deciphered: Greek inscriptions read as Greek, while Eteocypriot
inscriptions transliterate cleanly without a known translation.

pyaegean supports Cypriot through the standard `Script` plugin interface: a
55-sign inventory, transliteration to phonetic Latin, a curated Greek-lemma
bridge into [Greek NLP](Greek-NLP), and the bundled 180-document corpus.

```python
import aegean
from aegean.scripts.cypriot import word_to_phonetic, greek_reading, gloss

aegean.registered_scripts()          # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
word_to_phonetic("PA-SI-LE-U-SE")    # 'pasileuse'
greek_reading("PA-SI-LE-U-SE")       # ('βασιλεύς', 'king')
gloss("WA-NA-SA")                    # 'queen, lady (the Paphian goddess)'
```

Every feature below also has a CLI command under `pip install "pyaegean[cli]"`
(see [CLI](CLI) and [Getting Started](Getting-Started)).

---

## Script structure

The Cypriot syllabary is an open syllabary consisting of five bare vowels
(`A E I O U`) and consonant-plus-vowel syllables (`PA`, `SI`, `LE`, ...). It has
no labiovelar series. Two orthographic rules distinguish syllabic spelling from
alphabetic Greek: word-final consonants take a dummy vowel (βασιλεύς →
`PA-SI-LE-U-SE`, romanized `pasileuse`), and consonant clusters split across
syllables. The Greek bridge maps these syllabic spellings to standard Classical
Greek lemmas.

---

## Sign inventory

The sign inventory comes from the Unicode "Cypriot Syllabary" block
(`U+10800–U+1083F`, Unicode-3.0; see [Data & Provenance](Data-and-Provenance)).
It contains **55 syllabograms**, each with its settled phonetic value, glyph,
codepoint, and Unicode name.

```python
from aegean.core.script import get_script

inv = get_script("cypriot").sign_inventory
len(inv)                             # 55

pa = inv.by_label("PA")
pa.glyph, pa.phonetic, pa.codepoint  # ('𐠞', 'pa', 67614)
```

### Single-sign lookup (API and CLI)

```python
from aegean.core.script import get_script

s = get_script("cypriot").sign_inventory.by_label("SI")
s.glyph, s.phonetic, s.attrs["unicodeName"]   # ('𐠪', 'si', 'CYPRIOT SYLLABLE SI')
```

`aegean sign cypriot` accepts either a label (`PA`) or a single glyph (`𐠞`):

```bash
aegean sign cypriot PA
#               cypriot sign PA
# ┌───────────────────┬─────────────────────┐
# │ field             │ value               │
# ├───────────────────┼─────────────────────┤
# │ label             │ PA                  │
# │ glyph             │ 𐠞                   │
# │ codepoint         │ U+1081E             │
# │ phonetic          │ pa                  │
# │ attrs.unicodeName │ CYPRIOT SYLLABLE PA │
# │ attrs.signClass   │ syllabogram         │
# └───────────────────┴─────────────────────┘

aegean sign cypriot PA --json
# {
#   "label": "PA",
#   "glyph": "𐠞",
#   "codepoint": "U+1081E",
#   "phonetic": "pa",
#   "attrs": {"unicodeName": "CYPRIOT SYLLABLE PA", "signClass": "syllabogram"}
# }
```

### Full sign table

All 55 signs (`signClass = "syllabogram"`), grouped by series:

| Series | Signs (label → sound) |
| --- | --- |
| Vowels | A→a (𐠀) · E→e (𐠁) · I→i (𐠂) · O→o (𐠃) · U→u (𐠄) |
| J | JA→ja (𐠅) · JO→jo (𐠈) |
| K | KA→ka (𐠊) · KE→ke (𐠋) · KI→ki (𐠌) · KO→ko (𐠍) · KU→ku (𐠎) |
| L | LA→la (𐠏) · LE→le (𐠐) · LI→li (𐠑) · LO→lo (𐠒) · LU→lu (𐠓) |
| M | MA→ma (𐠔) · ME→me (𐠕) · MI→mi (𐠖) · MO→mo (𐠗) · MU→mu (𐠘) |
| N | NA→na (𐠙) · NE→ne (𐠚) · NI→ni (𐠛) · NO→no (𐠜) · NU→nu (𐠝) |
| P | PA→pa (𐠞) · PE→pe (𐠟) · PI→pi (𐠠) · PO→po (𐠡) · PU→pu (𐠢) |
| R | RA→ra (𐠣) · RE→re (𐠤) · RI→ri (𐠥) · RO→ro (𐠦) · RU→ru (𐠧) |
| S | SA→sa (𐠨) · SE→se (𐠩) · SI→si (𐠪) · SO→so (𐠫) · SU→su (𐠬) |
| T | TA→ta (𐠭) · TE→te (𐠮) · TI→ti (𐠯) · TO→to (𐠰) · TU→tu (𐠱) |
| W | WA→wa (𐠲) · WE→we (𐠳) · WI→wi (𐠴) · WO→wo (𐠵) |
| X | XA→ksa (𐠷) · XE→kse (𐠸) |
| Z | ZA→za (𐠼) · ZO→zo (𐠿) |

The gaps (`JE/JI/JU`, `WU`, `XI/XO/XU`, `ZE/ZI/ZU`) reflect the attested
syllabary. `XA` and `XE` represent the cluster `ks` (`ksa`, `kse`).

```python
from aegean.core.script import get_script

for s in get_script("cypriot").sign_inventory:
    print(s.label, s.glyph, "→", s.phonetic)
# A 𐠀 → a
# E 𐠁 → e
# ...
# ZO 𐠿 → zo
```

---

## Transliteration → phonetics

`word_to_phonetic` joins each sign's phonetic value from a hyphenated
transliteration. Case, editorial markers (`*`, `[`, `]`, `?`), and Leiden
underdots are normalized before lookup; unknown signs fall through lowercased.

```python
from aegean.scripts.cypriot import word_to_phonetic

word_to_phonetic("PA-SI-LE-U-SE")   # 'pasileuse'   (βασιλεύς)
word_to_phonetic("A-PO-LO-NI")      # 'apoloni'     (Ἀπόλλωνι)
word_to_phonetic("WA-NA-SA")        # 'wanasa'      (ϝάνασσα → ἄνασσα)
word_to_phonetic("A-TO-RO-PO-SE")   # 'atoropose'   (ἄνθρωπος)
word_to_phonetic("PA-ZZ-LE")        # 'pazzle'      (unrecognized 'ZZ' passes through)
```

### Overriding sign values

Pass `overrides` to test alternative values without modifying the bundled table:

```python
word_to_phonetic("SA-PO")                          # 'sapo'
word_to_phonetic("SA-PO", overrides={"PO": "pho"}) # 'sapho'
```

On the CLI, romanization runs inside `aegean bridge` and
`aegean analyze compare`.

---

## The Greek bridge (`pa-si-le-u-se` → `βασιλεύς`)

`greek_reading` returns a `(lemma, gloss)` tuple from the bundled Cypriot
lexicon; `gloss` returns the English string alone. For structured provenance,
`lexicon_entry` returns a `CypriotLexEntry` (with `lemma`, `gloss`,
`greek_form`, `attestation`, `site`, `citation`, and `license`) and
`lexicon_entries` lists the full table. Lookups fold case, editorial brackets,
trailing sentence periods, and underdots, returning `None` for unlisted forms.

```python
from aegean.scripts.cypriot import greek_reading, gloss, lexicon_entry

greek_reading("PA-SI-LE-U-SE")   # ('βασιλεύς', 'king')
greek_reading("KA-SE")           # ('καί', 'and (Arcado-Cypriot κάς)')
greek_reading("TU-KA")           # ('τύχη', 'fortune (Cypriot τύχα)')
gloss("WA-NA-SA")                # 'queen, lady (the Paphian goddess)'
lexicon_entry("KA-TE-TI-SA-NE")  # CypriotLexEntry(lemma='κατατίθημι', ..., attestation='IG XV 1, 227')
greek_reading("NOT-A-WORD")      # None
```

CLI equivalent:

```bash
aegean bridge cypriot PA-SI-LE-U-SE
# PA-SI-LE-U-SE → βασιλεύς   (king)

aegean bridge cypriot WA-NA-SA --json
# {
#   "word": "WA-NA-SA",
#   "greek": "ἄνασσα",
#   "gloss": "queen, lady (the Paphian goddess)"
# }

aegean bridge cypriot ZO-ZO
# aegean: 'ZO-ZO' has no attested Greek reading in the bundled cypriot lexicon
```

### Bundled lexicon

The bundled lexicon holds **52** source-cited equations drawn from Masson's
*ICS* / Idalion Bronze vocabulary and verified attestations in the bundled
*Inscriptiones Graecae* XV 1 (Kurion and Marion, CC BY 4.0). Across the
bundled corpus, `bridge_coverage(aegean.load("cypriot"))` reads **100 of 572
word tokens (17.5%, 45 distinct forms)** while keeping Eteocypriot Amathus
inscriptions at **0/193** (single-syllabogram words such as `O`, `A`, and `TO`
are deliberately excluded to avoid false positives on undeciphered text).

Representative entries (call `lexicon_entries()` for all 52 with citations):

| Cypriot word | Greek lemma | Gloss | Attestation |
| --- | --- | --- | --- |
| `A-KA-TA` | ἀγαθός | good | Idalion / formula |
| `A-NE-TE-KE` | ἀνατίθημι | dedicated (aor. ἀνέθηκε) | *IG* XV 1, 95 |
| `A-PO-LO-NI` | Ἀπόλλων | to Apollo (dative) | *IG* XV 1, 102 |
| `E-MI` | εἰμί | I am | *IG* XV 1, 120 / Marion |
| `KA-SE` | καί | and (Arcado-Cypriot κάς) | *IG* XV 1, 95 |
| `KA-TE-TI-SA-NE` | κατατίθημι | placed, buried (aor. 3pl. κατέθισαν) | *IG* XV 1, 227 |
| `KO-RA-I` | Κόρη | to Kore (Persephone) | *IG* XV 1, 95 |
| `PA-I-SE` | παῖς | child | *IG* XV 1, 179 |
| `PA-SI-LE-U-SE` | βασιλεύς | king | *IG* XV 1, 120 |
| `PA-SI-LE-WO-SE` | βασιλεύς | of the king (genitive) | *IG* XV 1, 120 |
| `TA-MA-TE-RI` | Δημήτηρ | to Demeter (dative) | *IG* XV 1, 95 |
| `TE-O-I` | θεός | to the god (dative) | *IG* XV 1, 113 |
| `TO-I` | ὁ | the (dative τῷ) | *IG* XV 1, 102 |
| `TU-KA-I` | τύχη | with fortune (dative) | *IG* XV 1, 95 |
| `WA-NA-SA` | ἄνασσα | queen, lady (the Paphian goddess) | Masson *ICS* |

### Full dictionary lookup

Pass the returned Greek lemma to the opt-in
[LSJ backend](Greek-NLP#lexicon-lsj-glossing-opt-in):

```python
import aegean
from aegean.scripts.cypriot import greek_reading

lemma, _ = greek_reading("PA-SI-LE-U-SE")   # 'βασιλεύς'

aegean.greek.use_lsj()                       # fetches ~15 MB index on first use
aegean.greek.gloss(lemma)                    # full LSJ entry for βασιλεύς
```

Calling `aegean.greek.gloss(...)` before `use_lsj()` raises
`LexiconNotLoadedError`.

---

## Phonetic comparison with alphabetic Greek

`phonetic_compare` romanizes both sides and aligns them phoneme by phoneme. For
`PA-SI-LE-U-SE` vs `βασιλεύς`, the only differences are the `p/b` onset
(same-class substitution) and the dummy final vowel (deletion):

```bash
aegean analyze compare PA-SI-LE-U-SE βασιλεύς --script-a cypriot --script-b greek
# PA-SI-LE-U-SE [cypriot] → pasileuse    βασιλεύς [greek] → basileus
# similarity 0.83  (distance 0.167)
#       alignment
# ┌───┬───┬───────────┐
# │ a │ b │ op        │
# ├───┼───┼───────────┤
# │ p │ b │ sub-class │
# │ a │ a │ match     │
# │ s │ s │ match     │
# │ i │ i │ match     │
# │ l │ l │ match     │
# │ e │ e │ match     │
# │ u │ u │ match     │
# │ s │ s │ match     │
# │ e │ · │ del       │
# └───┴───┴───────────┘
```

Python API:

```python
from aegean.analysis import phonetic_compare

cmp = phonetic_compare("PA-SI-LE-U-SE", "cypriot", "βασιλεύς", "greek")
cmp.phonemes_a, cmp.phonemes_b   # ('pasileuse', 'basileus')
round(cmp.similarity, 2)         # 0.83
```

Pass `--fold-aspiration` (`fold_aspiration=True`) to map `θ/φ/χ` to `t/p/k`,
matching the syllabary's aspiration-neutral orthography. See
[Analysis](Analysis) for distance metrics and nearest-neighbor search.

---

## Bundled corpus

pyaegean bundles a point-in-time snapshot of **178** Cypriot syllabic
inscriptions from the Berlin-Brandenburg Academy of Sciences and Humanities
digital edition of *Inscriptiones Graecae* XV 1
([telota.bbaw.de/ig](https://telota.bbaw.de/ig), **CC BY 4.0**), plus 2
illustrative samples (**180 documents** total). Each inscription carries its
transliteration, editorial status, find-place, date, material, translation where
provided, source URL in `doc.meta.notes`, and the Greek text of bilinguals when
present. The repo-only script `scripts/build_cypriot_ig.py` rebuilds the
snapshot from upstream. Additional transliterations can be imported from text or
CSV via `aegean.io.from_csv`.

```python
import aegean

c = aegean.load("cypriot")
len(c)                                # 180 (178 IG XV 1 + 2 illustrative samples)
d = c.get("IG XV 1, 1")
print(d.id, d.meta.site, [t.text for t in d.tokens][:4])
# IG XV 1, 1 Amathus ['i-te-o-..-..-..-ja']
```

The loader strips Leiden underdots from token strings and records the editorial
uncertainty on `token.status` (`ReadingStatus.UNCLEAR` above), so token text
stays clean for lookup while apparatus status remains queryable.

```bash
aegean info cypriot
# documents          180
# signs_in_inventory 55
# source             Inscriptiones Graecae XV 1: Cypriot syllabic inscriptions
#                    (BBAW digital edition), plus illustrative samples
# license            Inscriptiones Graecae XV 1: CC BY 4.0 (Berlin-Brandenburg
#                    Academy of Sciences and Humanities). Sign data: Unicode-3.0.
# citation           Inscriptiones Graecae XV 1 (Cypriot syllabic inscriptions),
#                    digital edition, https://telota.bbaw.de/ig (CC BY 4.0).

aegean show cypriot "IG XV 1, 1"
# IG XV 1, 1  site=Amathus  period=330-310  support=Basis (Marmor)
#   1: i-te-o-..-..-..-ja
```

### Sample documents

Two illustrative documents accompany the *IG* XV 1 snapshot:

| Document id | Words | Reading |
| --- | --- | --- |
| `cypriot-dedication` | `O-NA-SI-LO-SE TO-I A-PO-LO-NI` | "Onasilos, to Apollo" |
| `cypriot-formula` | `A-KA-TA TU-KA` | ἀγαθᾷ τύχᾳ, "with good fortune" |

All standard corpus commands (`aegean search`, `aegean stats`, `aegean export`,
`aegean geo`) operate directly on `cypriot`.

---

## Browser workbench

`aegean workbench` opens the Cypriot corpus directly in the multi-script browser
workbench (`v2.1.0`) with self-hosted Noto Sans Aegean fonts (rendering
`U+10800–U+1083F` without system font setup), the 55-sign inventory, and
phonetic values:

```bash
aegean workbench --corpus cypriot
aegean workbench --corpus cypriot --state cypriot-notes.json
```

From Python, `aegean.io.to_workbench_bundle(corpus, "cypriot-workbench.json")`
writes the schema-v1 multi-script bundle (`_meta.script = "cypriot"`, `signs`,
and `phoneticMap`). See [Interoperability](Interoperability) for workspace
backup round-trips.

---

## Command and API summary

| Capability | Python (`aegean.scripts.cypriot` unless noted) | CLI |
| --- | --- | --- |
| List registered scripts | `aegean.registered_scripts()` | `aegean info` (per corpus) |
| Sign inventory | `aegean.get_script("cypriot").sign_inventory` | — |
| Look up one sign | `inv.by_label("PA")` | `aegean sign cypriot PA` |
| Transliteration → sound | `word_to_phonetic("PA-SI-LE-U-SE")` | via `bridge` / `analyze compare` |
| Override sign values | `word_to_phonetic(w, overrides={...})` | — |
| Greek reading (lemma + gloss) | `greek_reading("PA-SI-LE-U-SE")` | `aegean bridge cypriot PA-SI-LE-U-SE` |
| Source-cited lexicon entry | `lexicon_entry("KA-TE-TI-SA-NE")` / `lexicon_entries()` | — |
| English gloss only | `gloss("WA-NA-SA")` | shown in `bridge` output |
| Full dictionary entry | `aegean.greek.use_lsj()`, `greek.gloss(lemma)` | `aegean greek gloss <lemma>` |
| Compare with Greek by sound | `aegean.analysis.phonetic_compare(w, "cypriot", g, "greek")` | `aegean analyze compare ... --script-a cypriot` |
| Load bundled corpus | `aegean.load("cypriot")` | `aegean info cypriot` / `aegean show cypriot <id>` |
| Open in browser workbench | `aegean.io.to_workbench_bundle(corpus)` | `aegean workbench --corpus cypriot` |

---

## Provenance and licensing

Sign inventory data comes from the Unicode Character Database (**Unicode-3.0**).
The bundled 178-inscription corpus comes from the BBAW digital edition of
*Inscriptiones Graecae* XV 1 (**CC BY 4.0**), accompanied by 2 illustrative
samples. See [Data & Provenance](Data-and-Provenance) and `NOTICE`.

---

## Limitations

- **Corpus scope.** The bundled corpus is *IG* XV 1 (178 texts + 2 samples), not
  Masson's full *ICS*, which is not openly redistributable. It includes
  Eteocypriot inscriptions whose language is undeciphered.
- **Lexicon size.** The bundled bridge lexicon holds 52 source-cited entries
  and returns `None` for unlisted words (single-syllabogram forms are omitted
  to keep Eteocypriot Amathus texts at zero false positives).
- **Orthographic distance.** Dummy final vowels (`…-SE`) and split clusters make
  romanized strings longer than standard Classical Greek spellings.
- **Terminal fonts.** Displaying Cypriot codepoints (`U+10800–U+1083F`) in a
  terminal requires a supporting font (see [Getting Started](Getting-Started));
  the browser workbench (`v2.1.0`) bundles self-hosted Noto Sans Aegean fonts.

See [Limitations](Limitations), [Linear B](Linear-B), [Greek NLP](Greek-NLP),
and [Analysis](Analysis).
