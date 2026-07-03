# Cypriot syllabary

The Cypriot syllabary wrote Greek (the Arcado-Cypriot dialect) from roughly the 11th to the
4th century BC. Like [Linear B](Linear-B) it is **deciphered**, so reading it is verifiable
rather than guesswork. Use this page when you want to look up a Cypriot sign, turn a transliterated
word into its sound, or read a syllabic word as Greek (the famous **pa-si-le-u-se → basileus**
bridge, "king"). pyaegean handles all of that through the same plugin model as the other Aegean
scripts: a sign inventory, a transliteration step, and a bridge into the [Greek track](Greek-NLP).

```python
import aegean
from aegean.scripts.cypriot import word_to_phonetic, greek_reading, gloss

aegean.registered_scripts()          # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
word_to_phonetic("PA-SI-LE-U-SE")    # 'pasileuse'
greek_reading("PA-SI-LE-U-SE")       # ('βασιλεύς', 'king')
gloss("WA-NA-SA")                    # 'queen, lady (the Paphian goddess)'
```

If you have never run Python before, start with [Getting Started](Getting-Started) and come back:
every snippet here is meant to be copied and pasted as-is. If you prefer the shell, every feature
below also has an `aegean ...` command; install it with `pip install "pyaegean[cli]"` (see the
[CLI](CLI) page).

---

## What the script is

The Cypriot syllabary is an **open** syllabary: most signs spell a consonant-plus-vowel syllable
(`PA`, `SI`, `LE`), with five bare vowels (`A E I O U`). It is more phonetically transparent than
Linear B; there are **no labiovelars**, so a transliterated word already sits very close to the
spoken Greek. The trade-offs are spelling conventions rather than ambiguous signs: word-final
consonants get a "dummy" vowel (βασιλεύ**ς** is written `…-SE`, giving `pasileuse`), and consonant
clusters are split across syllables. Those conventions are exactly why the Greek bridge below is
useful: it maps the syllabic spelling back to the real Greek lemma.

---

## Sign inventory

The inventory is built from the Unicode "Cypriot Syllabary" block (U+10800–U+1083F), generated from
the Unicode Character Database, so the glyph-to-value mapping is authoritative and freely licensed
(see [Data & Provenance](Data-and-Provenance)). It holds **55 syllabograms**, each carrying a
settled phonetic value, its glyph, its codepoint, and its Unicode name.

```python
from aegean.core.script import get_script

inv = get_script("cypriot").sign_inventory
len(list(inv))                       # 55

pa = inv.by_label("PA")
pa.glyph, pa.phonetic, pa.codepoint  # ('𐠞', 'pa', 67614)
```

### One sign at a time (API + CLI)

```python
from aegean.core.script import get_script

s = get_script("cypriot").sign_inventory.by_label("SI")
s.glyph, s.phonetic, s.attrs["unicodeName"]   # ('𐠪', 'si', 'CYPRIOT SYLLABLE SI')
```

The CLI `sign` command takes either a **label** (`PA`) or a single **glyph** (`𐠞`) and prints the
same record. Add `--json` for a machine-readable form.

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

### The full sign table

All 55 signs, grouped by series. Every one is class `syllabogram`.

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

A few series are deliberately short: there is no `JE/JI/JU`, no `WU`, only `XA/XE`, and only
`ZA/ZO`. That reflects the attested sign set, not a gap in pyaegean. The `XA/XE` signs carry the
cluster value `ks` (so `XA` → `ksa`), which is why the romanized forms have two letters.

To list the whole inventory yourself:

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

`word_to_phonetic` converts a **hyphenated** transliteration to a phonetic Latin form by joining
each sign's value. Because Cypriot is transparent, the result is essentially the spoken word
(complete with the dummy final vowel that the spelling adds).

```python
from aegean.scripts.cypriot import word_to_phonetic

word_to_phonetic("PA-SI-LE-U-SE")   # 'pasileuse'   (βασιλεύς)
word_to_phonetic("A-PO-LO-NI")      # 'apoloni'     (Ἀπόλλωνι)
word_to_phonetic("WA-NA-SA")        # 'wanasa'      (ϝάνασσα → ἄνασσα)
word_to_phonetic("A-TO-RO-PO-SE")   # 'atoropose'   (ἄνθρωπος)
```

Editorial markers (`*`, `[`, `]`, `?`) are stripped before lookup, and any sign that is not in the
table falls through **lowercased** rather than raising, so a damaged or unusual reading still
returns something legible:

```python
word_to_phonetic("PA-ZZ-LE")        # 'pazzle'   (the unknown sign 'ZZ' passes through)
```

### Testing an alternative sign value (`overrides`)

The optional `overrides` argument lets you try a different value for one or more signs without
touching the bundled table: handy for "what if this sign were read differently?" experiments.

```python
word_to_phonetic("SA-PO")                          # 'sapo'
word_to_phonetic("SA-PO", overrides={"PO": "pho"}) # 'sapho'
```

> There is no separate CLI command just for romanization: use the `bridge` command below (which
> reads the word as Greek), or the cross-script `analyze compare`, which romanizes both sides for
> you and shows the alignment.

---

## The Greek bridge: pa-si-le-u-se → basileus

Because the syllabary writes Greek, a transliterated word resolves to a Greek **lemma**.
`greek_reading` returns a `(lemma, gloss)` pair from a curated lexicon of well-established
equations; `gloss` returns just the English meaning. Both return `None` for a word that is not in
the bundled lexicon.

```python
from aegean.scripts.cypriot import greek_reading, gloss

greek_reading("PA-SI-LE-U-SE")   # ('βασιλεύς', 'king')
greek_reading("KA-SE")           # ('καί', 'and (Arcado-Cypriot κάς)')
greek_reading("TU-KA")           # ('τύχη', 'fortune (Cypriot τύχα)')
gloss("WA-NA-SA")                # 'queen, lady (the Paphian goddess)'
greek_reading("NOT-A-WORD")      # None
```

The same thing from the shell, with the `bridge` command (`linearb` or `cypriot`):

```bash
aegean bridge cypriot PA-SI-LE-U-SE
# PA-SI-LE-U-SE → βασιλεύς   (king)

aegean bridge cypriot WA-NA-SA --json
# {
#   "word": "WA-NA-SA",
#   "greek": "ἄνασσα",
#   "gloss": "queen, lady (the Paphian goddess)"
# }
```

A word with no attested reading fails cleanly rather than guessing:

```bash
aegean bridge cypriot ZO-ZO
# aegean: 'ZO-ZO' has no attested Greek reading in the bundled cypriot lexicon
```

### The bundled lexicon

The lexicon is a small, curated set of **17 well-established equations**, largely the Idalion Bronze
vocabulary, after Masson's ICS and Chadwick. It is meant to demonstrate the bridge and to seed your
own work, not to be a dictionary. Lookups are case-insensitive and tolerate `[ ] ?` markers.

| Cypriot word | Greek lemma | Gloss |
| --- | --- | --- |
| `A-KA-TA` | ἀγαθός | good |
| `A-NE-U` | ἄνευ | without |
| `A-PO-LO-NI` | Ἀπόλλων | to Apollo (dative) |
| `A-RA-KU-RO` | ἄργυρος | silver |
| `A-TO-RO-PO-SE` | ἄνθρωπος | human, man |
| `E-MI` | εἰμί | I am |
| `I-JA-SA-TA-I` | ἰάομαι | to heal (infinitive ἰᾶσθαι) |
| `KA-SE` | καί | and (Arcado-Cypriot κάς) |
| `KA-SI-KE-NE-TO-SE` | κασίγνητος | brother |
| `MA-KA-I` | μάχη | battle (dative: in the battle) |
| `O-NA-SI-LO-SE` | Ὀνάσιλος | Onasilos (personal name, Idalion tablet) |
| `PA-I-SE` | παῖς | child |
| `PA-SI-LE-U-SE` | βασιλεύς | king |
| `TE-O-SE` | θεός | god |
| `TO-I` | ὁ | the (dative τῷ) |
| `TU-KA` | τύχη | fortune (Cypriot τύχα) |
| `WA-NA-SA` | ἄνασσα | queen, lady (the Paphian goddess) |

### From the bridge into the dictionary

The lexicon gives you a short gloss. For the full LSJ entry, hand the returned **lemma** to the
Greek track's dictionary backend (opt-in: it fetches a local cache the first time you turn it on):

```python
import aegean
from aegean.scripts.cypriot import greek_reading

lemma, _ = greek_reading("PA-SI-LE-U-SE")   # 'βασιλεύς'

aegean.greek.use_lsj()                       # turn on the LSJ backend (one-time fetch)
aegean.greek.gloss(lemma)                    # full LSJ dictionary entry for βασιλεύς
```

Without that call, `aegean.greek.gloss(...)` raises `LexiconNotLoadedError` telling you to run
`use_lsj()` first. See [Greek NLP → LSJ glossing](Greek-NLP#lexicon-lsj-glossing-opt-in).

---

## Comparing a Cypriot word with its Greek by sound

The cross-script comparator romanizes each side and aligns them position by position: a vivid way
to *see* the bridge. `pa-si-le-u-se` vs `βασιλεύς` lines up almost perfectly; the only differences
are the `p/b` onset (a sub-class substitution) and the dummy final vowel (a deletion).

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

The same comparison from Python:

```python
from aegean.analysis import phonetic_compare

cmp = phonetic_compare("PA-SI-LE-U-SE", "cypriot", "βασιλεύς", "greek")
cmp.phonemes_a, cmp.phonemes_b   # ('pasileuse', 'basileus')
round(cmp.similarity, 2)         # 0.83
```

`--fold-aspiration` (map θ/φ/χ → t/p/k) makes the comparison fairer against syllabic spelling,
which cannot write aspiration. More on these tools (distance, alignment, nearest-neighbour search)
is on the [Analysis](Analysis) page.

---

## The bundled corpus

pyaegean bundles the **Cypriot syllabic inscriptions of *Inscriptiones Graecae* XV 1** — the
Berlin-Brandenburg Academy of Sciences and Humanities digital edition
([telota.bbaw.de/ig](https://telota.bbaw.de/ig)), licensed **CC BY 4.0**. A point-in-time snapshot
of **178 inscriptions** ships with the package, so the readable corpus is always available offline
and never depends on the source staying online. Each inscription carries its transliteration (with
the editorial apparatus), find-place, date, material, a translation where the edition gives one,
and its own source URL for the CC-BY link-back; two illustrative samples round it out. To refresh
the snapshot from the source, run `scripts/build_cypriot_ig.py` (a repo-only build tool). Have your
own transliterations as well? Import a `.txt` or CSV in one step (`aegean.io.from_csv`) and they get
the whole corpus API too.

```python
import aegean

c = aegean.load("cypriot")
len(c)                                # 180 (178 IG XV 1 + 2 illustrative samples)
d = next(x for x in c if x.id == "IG XV 1, 1")
print(d.id, d.meta.site, [t.text for t in d.tokens][:4])
# IG XV 1, 1 Amathus ['i-te-o-..-..-..-ja']
```

The token text reads plainly, without the edition's underdots: the loader lifts a
Leiden underdot out of the letters and records it as the token's editorial status
(`d.tokens[0].status` is `ReadingStatus.UNCLEAR` here), so the uncertainty is
queryable rather than buried in the string.

From the shell:

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

Each IG XV 1 document keeps its source URL (`doc.meta.notes`) for the CC-BY link-back, and the
Greek side of a bilingual where present.

### Sample documents

Alongside the IG XV 1 corpus, two illustrative samples show the syllabary→Greek bridge:

| Document id | Words | Reading |
| --- | --- | --- |
| `cypriot-dedication` | `O-NA-SI-LO-SE TO-I A-PO-LO-NI` | "Onasilos, to Apollo": an illustrative dedicatory fragment |
| `cypriot-formula` | `A-KA-TA TU-KA` | ἀγαθᾷ τύχᾳ, "with good fortune": an illustrative formula |

Because it is a real corpus object, the rest of the toolkit works on it: `aegean search`,
`aegean stats`, `aegean export`, `aegean geo`, and so on (see [CLI](CLI) and [Analysis](Analysis)).

---

## Commands and functions at a glance

| Capability | Python | CLI |
| --- | --- | --- |
| List registered scripts | `aegean.registered_scripts()` | `aegean info` (per corpus) |
| Sign inventory | `get_script("cypriot").sign_inventory` |— |
| Look up one sign | `inv.by_label("PA")` | `aegean sign cypriot PA` |
| Transliteration → sound | `word_to_phonetic("PA-SI-LE-U-SE")` | (via `bridge` / `analyze compare`) |
| Try an alternate sign value | `word_to_phonetic(w, overrides={...})` |— |
| Greek reading (lemma + gloss) | `greek_reading("PA-SI-LE-U-SE")` | `aegean bridge cypriot PA-SI-LE-U-SE` |
| English gloss only | `gloss("WA-NA-SA")` | (the `()` in `bridge` output) |
| Full dictionary entry | `aegean.greek.use_lsj()` then `greek.gloss(lemma)` | `aegean greek …` |
| Compare with Greek by sound | `phonetic_compare(w, "cypriot", g, "greek")` | `aegean analyze compare … --script-a cypriot` |
| Load the sample corpus | `aegean.load("cypriot")` | `aegean info cypriot` / `aegean show cypriot <id>` |

`word_to_phonetic`, `greek_reading`, and `gloss` are all importable from `aegean.scripts.cypriot`.

---

## Provenance and licensing

The sign data comes from the Unicode Character Database (**Unicode-3.0** license). The sample
transliterations are scholarly facts, bundled as illustrative excerpts, not a corpus. The bundled
corpus cites Masson, O. (1983), *Les inscriptions chypriotes syllabiques* (2nd ed.). See
[Data & Provenance](Data-and-Provenance) and the repository `NOTICE` file.

---

## Limitations and notes

- **The bundled corpus is IG XV 1, not the full ICS.** The 178-inscription *Inscriptiones
  Graecae* XV 1 corpus (BBAW, CC BY 4.0) ships bundled, plus two illustrative samples (180
  documents in all); the larger ICS/Masson corpus is not openly redistributable. The sign
  inventory and the Greek-reading bridge are the durable parts.
- **The lexicon is small and curated** (17 entries). A word outside it returns `None`
  (`greek_reading`) or fails the `bridge` command; that is by design, not a bug. It seeds your
  own work; it is not a Cypriot dictionary.
- **Spelling conventions are real.** The dummy final vowel (`…-SE` for final ς) and split clusters
  mean a romanized form like `pasileuse` is not literally the Greek word; that gap is exactly what
  the Greek bridge closes.
- **Glyphs need a font.** Cypriot characters (U+10800–U+1083F) display in Jupyter and modern
  editors; a plain terminal may show boxes. See the font note in [Getting Started](Getting-Started).

For the project-wide picture of what is and is not in scope, see [Limitations](Limitations). Related
pages: [Linear B](Linear-B) (the other deciphered syllabary and its bridge),
[Greek NLP](Greek-NLP), and [Analysis](Analysis) for the Greek and cross-script side.
