# Meters

This is the reference for **metrical scansion** in pyaegean: you hand it a line of
Ancient Greek verse and a metre, and it fits the whole line to that metre's
quantity template: recovering the feet, the long/short sequence, and (for the
spoken metres) the main caesura. Use it to check whether a line scans, to see
*how* it scans, or to pull the metre out of a corpus line by line.

It works **offline**, with no third-party dependencies, on the syllables and
quantities pyaegean already computes. If you only want the heavy/light weight of
the syllables in a single word (not a fitted line), that's the simpler
[per-syllable prosody](Greek-NLP#prosody-syllable-quantity) tool, not this page.

> New here? Start with [Getting Started](Getting-Started). For the wider Greek
> toolkit see [Greek NLP](Greek-NLP); for the spoken-vs-written-language caveats
> see [Limitations](Limitations).

## The one-line version

```python
from aegean import greek

greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

Or from the terminal (needs `pip install "pyaegean[cli]"`):

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic
```

## Notation (the three glyphs)

Every pattern is written with three symbols. There is nothing else to learn.

| Glyph | Name | Means |
|---|---|---|
| `—` | heavy (longum) | a long/heavy syllable |
| `⏑` | light (breve) | a short/light syllable |
| `×` | anceps | "either": a position the metre lets be long *or* short (also the line-final *brevis in longo*) |

Feet are separated by `|` in the printed pattern. The aeolic lines are printed as
one unbroken run (they aren't divided into feet).

## The metres at a glance

Every supported metre, its quantity template, and a real line that scans. Each
example below was run through `aegean greek scan ... --meter <name>` (or the
matching Python call) and shows its **actual** output.

| `--meter` value | Template (— heavy · ⏑ light · × anceps) | Example line that scans |
|---|---|---|
| `hexameter` | five dactyl-or-spondee feet + `—×` | `ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ` |
| `pentameter` | `— ⏑⏑ — ⏑⏑ — ‖ — ⏑⏑ — ⏑⏑ —` | `κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι.` |
| `trimeter` | `× — ⏑ —` × 3 (final element anceps), with resolution | `ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα` |
| `glyconic` | `× × — ⏑ ⏑ — ⏑ ×` | `Ἀφροδίτα δολόπλοκε` |
| `pherecratean` | `× × — ⏑ ⏑ — ×` (catalectic glyconic) | `δεῦρο Μοῦσα λίγεια` |
| `sapphic_hendecasyllable` | `— ⏑ — × — ⏑ ⏑ — ⏑ — ×` | `φαίνεταί μοι κῆνος ἴσος θέοισιν` |
| `adonean` | `— ⏑ ⏑ — ×` (close of the Sapphic stanza) | `ἰμερόεν δὲ` |
| `alcaic_hendecasyllable` | `× — ⏑ — × — ⏑ ⏑ — ⏑ ×` | `ἀσυννέτημμι τὼν ἀνέμων στάσιν` |
| `alcaic_enneasyllable` | `× — ⏑ — × — ⏑ — ×` | `κρόνωι βασιλεῦσι δῶτορ` (illustrative) |
| `alcaic_decasyllable` | `— ⏑ ⏑ — ⏑ ⏑ — ⏑ — ×` | `δέξατο νυμφίον ἐς θαλάμους` (illustrative) |

> The `alcaic_enneasyllable` and `alcaic_decasyllable` examples are short
> illustrative cola chosen to land exactly on the template; the rest are genuine
> verse openings (Homer, Simonides, Sophocles, Euripides, Sappho, Alcaeus). All
> ten were verified against the running scanner.

The list of aeolic line names is also available in code:

```python
from aegean import greek
greek.AEOLIC_LINES
# ('glyconic', 'pherecratean', 'sapphic_hendecasyllable', 'adonean',
#  'alcaic_hendecasyllable', 'alcaic_enneasyllable', 'alcaic_decasyllable')
```

## The functions

There is one function per metre family plus a dispatcher. The CLI mirrors them
through a single `--meter` flag.

| Python | What it scans | CLI equivalent |
|---|---|---|
| `greek.scan_hexameter(line)` | dactylic hexameter | `aegean greek scan LINE` (default) |
| `greek.scan_pentameter(line)` | elegiac pentameter | `aegean greek scan LINE --meter pentameter` |
| `greek.scan_trimeter(line)` | iambic trimeter (with resolution) | `aegean greek scan LINE --meter trimeter` |
| `greek.scan_aeolic(line, line_type)` | one named aeolic line | `aegean greek scan LINE --meter <line_type>` |
| `greek.scan_line(line, meter)` | any of the above, by name | `aegean greek scan LINE --meter <meter>` |
| `greek.syllable_options(line)` | the raw pre-metrical analysis |— |

`scan_line` is the general entry point: pass `"hexameter"`, `"pentameter"`,
`"trimeter"`, or any aeolic line name. The named functions are just convenient
shortcuts.

### Dactylic hexameter

Six feet: feet 1–5 each a **dactyl** (`—⏑⏑`) or **spondee** (`——`), the sixth
always `—×`. Quantities are resolved across word boundaries, including
*correptio epica* (a word-final long vowel in hiatus may scan short).

```python
from aegean import greek

sc = greek.scan_hexameter("πλάγχθη, ἐπεὶ Τροίης ἱερὸν πτολίεθρον ἔπερσεν")
sc.pattern        # '—⏑⏑|——|—⏑⏑|—⏑⏑|—⏑⏑|—×'
sc.caesura        # 'penthemimeral'
[f.name for f in sc.feet]
# ['dactyl', 'spondee', 'dactyl', 'dactyl', 'dactyl', 'final']
```

```bash
aegean greek scan "πλάγχθη, ἐπεὶ Τροίης ἱερὸν πτολίεθρον ἔπερσεν"
# —⏑⏑|——|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, spondee, dactyl, dactyl, dactyl, final; caesura: penthemimeral
```

### Elegiac pentameter

The second line of the elegiac couplet: two dactyl-or-spondee feet, a longum, the
central diaeresis (`‖`), then **two obligatory dactyls** and a final longum.

```python
from aegean import greek

# Simonides' Thermopylae epitaph
greek.scan_pentameter("κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι.").pattern
# '—⏑⏑|——|—|—⏑⏑|—⏑⏑|×'
```

```bash
aegean greek scan "κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι." --meter pentameter
# —⏑⏑|——|—|—⏑⏑|—⏑⏑|×
# pentameter: dactyl, spondee, longum, dactyl, dactyl, longum; caesura: —
```

No caesura is reported for the pentameter (its central break is structural, not a
detected word-break), so the `caesura` field is `None`.

### Iambic trimeter

The spoken metre of tragedy and comedy: three metra of `× — ⏑ —` (the final
element anceps). Long elements may be **resolved** into two shorts, so a
13-syllable line can still be a clean trimeter.

```python
from aegean import greek

# Antigone 1 — no resolution
greek.scan_trimeter("ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα").pattern
# '×—⏑—|×—⏑—|×—⏑×'

# Bacchae 1 — Διό- resolves to ⏑⏑, giving 13 syllables
sc = greek.scan_trimeter("Διόνυσον, ὃν τίκτει ποθ' ἡ Κάδμου κόρη")
sc.pattern              # '×⏑⏑⏑—|×—⏑—|×—⏑×'
len(sc.syllables)       # 13
```

```bash
aegean greek scan "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα" --meter trimeter
# ×—⏑—|×—⏑—|×—⏑×
# trimeter: metron, metron, metron; caesura: hephthemimeral
```

The trimeter reports a **penthemimeral** or **hephthemimeral** caesura when a
word-break falls at the right element.

### Aeolic lyric lines

These are **fixed quantity templates**: the choriambic nucleus does not resolve,
so the line either matches the template exactly or it doesn't. Interior `×`
positions are the *aeolic base*; the final `×` is *brevis in longo*. Use
`scan_aeolic(line, line_type)` (or `scan_line(line, line_type)`).

```python
from aegean import greek

greek.scan_aeolic("φαίνεταί μοι κῆνος ἴσος θέοισιν", "sapphic_hendecasyllable").pattern
# '—⏑—×—⏑⏑—⏑—×'   (Sappho 31.1)

greek.scan_aeolic("ἀσυννέτημμι τὼν ἀνέμων στάσιν", "alcaic_hendecasyllable").pattern
# '×—⏑—×—⏑⏑—⏑×'   (Alcaeus 326.1)

greek.scan_aeolic("Ἀφροδίτα δολόπλοκε", "glyconic").pattern
# '××—⏑⏑—⏑×'
```

```bash
aegean greek scan "φαίνεταί μοι κῆνος ἴσος θέοισιν" --meter sapphic_hendecasyllable
# —⏑—×—⏑⏑—⏑—×
# sapphic_hendecasyllable: sapphic_hendecasyllable; caesura: —
```

The full set of aeolic templates:

| `line_type` | Template | Note |
|---|---|---|
| `glyconic` | `× × — ⏑ ⏑ — ⏑ ×` | the base aeolic colon |
| `pherecratean` | `× × — ⏑ ⏑ — ×` | catalectic glyconic |
| `sapphic_hendecasyllable` | `— ⏑ — × — ⏑ ⏑ — ⏑ — ×` | the line of the Sapphic stanza |
| `adonean` | `— ⏑ ⏑ — ×` | the short close of the Sapphic stanza |
| `alcaic_hendecasyllable` | `× — ⏑ — × — ⏑ ⏑ — ⏑ ×` | the line of the Alcaic stanza |
| `alcaic_enneasyllable` | `× — ⏑ — × — ⏑ — ×` | the 9-syllable Alcaic colon |
| `alcaic_decasyllable` | `— ⏑ ⏑ — ⏑ ⏑ — ⏑ — ×` | the 10-syllable Alcaic colon |

## What a scansion gives you back

Both `scan_*` and `scan_line` return a `LineScansion`. Its fields:

| Field / property | Type | What it is |
|---|---|---|
| `.line` | `str` | the input line |
| `.meter` | `str` | the metre it was fit to |
| `.pattern` | `str` | the glyph pattern (`—⏑⏑\|…`), feet joined by `\|` |
| `.feet` | tuple of `Foot` | each foot's `name`, `syllables`, `quantities` |
| `.syllables` | tuple of `str` | the line's syllables, in order |
| `.quantities` | tuple of `str` | the resolved quantity per syllable (`"heavy"` / `"light"` / `"anceps"`) |
| `.caesura` | `str` or `None` | `"penthemimeral"`, `"trochaic"`, `"hephthemimeral"`, or `None` |
| `.caesura_index` | `int` or `None` | the syllable index the caesura precedes |
| `.ambiguous` | `bool` | `True` if more than one scansion fit the template |

Each `Foot` carries:

| `Foot` field | What it is |
|---|---|
| `.name` | `dactyl`, `spondee`, `longum`, `final`, `metron`, or the aeolic line name |
| `.syllables` | the syllables spanned by this foot |
| `.quantities` | the resolved quantities for those syllables |

```python
from aegean import greek

sc = greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
sc.feet[0].name           # 'dactyl'
sc.feet[0].syllables      # ('ἄν', 'δρα', 'μοι')
sc.feet[0].quantities     # ('heavy', 'light', 'light')
sc.quantities[2]          # 'light'  — μοι, shortened by correptio before ἔννεπε
```

In Jupyter or Colab a `LineScansion` renders as a small card with the line, the
glyph pattern, the metre, and a foot-by-foot table; everywhere else it prints as
the pattern string (`str(sc) == sc.pattern`).

### JSON from the CLI

`--json` emits the whole analysis as machine-readable JSON (feet, per-syllable
quantities, caesura, the ambiguity flag):

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ" --json
```

```json
{
  "meter": "hexameter",
  "pattern": "—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×",
  "feet": [ { "name": "dactyl", "syllables": ["ἄν","δρα","μοι"],
              "quantities": ["heavy","light","light"] }, … ],
  "syllables": ["ἄν","δρα","μοι", … ,"πολ","λὰ"],
  "quantities": ["heavy","light","light", … ,"heavy","anceps"],
  "caesura": "trochaic",
  "ambiguous": false
}
```

The CLI also reads a line from **stdin** when you pass `-` as the argument, so you
can pipe a corpus through it.

## Scans-or-declines (it never fudges)

The scanner only returns a scansion that genuinely fits the template. A line that
does **not** fit raises `ScansionError` from Python and exits non-zero (with the
reason) from the CLI: it does not silently produce a wrong reading.

```python
from aegean import greek

try:
    greek.scan_hexameter("ἄνθρωπος")
except greek.ScansionError as exc:
    print(exc)
# line does not scan as dactylic hexameter (3 syllables): 'ἄνθρωπος'
```

```bash
aegean greek scan "ἄνθρωπος"
# aegean: line does not scan as dactylic hexameter (3 syllables): 'ἄνθρωπος'
# (exit code 1)
```

An unknown metre name is reported the same way, with the list of valid names:

```bash
aegean greek scan "φαίνεταί μοι κῆνος ἴσος θέοισιν" --meter not_a_metre
# aegean: unknown meter 'not_a_metre'; available: adonean, alcaic_decasyllable,
#   alcaic_enneasyllable, alcaic_hendecasyllable, glyconic, hexameter,
#   pentameter, pherecratean, sapphic_hendecasyllable, trimeter
# (exit code 1)
```

## How the quantities are decided

Before fitting, every vowel nucleus is given the **set of quantities it could
carry**, not a single value: the metre then resolves the open choices. The rules:

| Situation | Quantity |
|---|---|
| closed by position (two+ consonants, or a double ζ/ξ/ψ, before the next nucleus) | heavy |
| short vowel before *muta cum liquida* (stop + liquid/nasal) | **common**: heavy **or** light |
| open, long nucleus (η, ω, circumflex, iota-subscript, or a diphthong) | heavy |
| open, short nucleus (ε, ο) | light |
| open *dichronon* (α, ι, υ: length not fixed by spelling) | **common**: heavy **or** light |
| word-final long vowel/diphthong in hiatus (*correptio epica*) | also allowed to shorten |

You can see this raw, pre-metrical layer directly: useful for debugging why a
line does or doesn't scan:

```python
from aegean import greek

greek.syllable_options("πατρός")
# [('πα', ['heavy', 'light']), ('τρός', ['light'])]
#   πα is common: short α before the stop+liquid cluster τρ (muta cum liquida)
```

This is the line-level analysis (cross-word position and correptio applied). For
the simpler within-a-word weight of each syllable, use
[`greek.scan`](Greek-NLP#prosody-syllable-quantity), which returns `heavy` /
`light` / `common` per syllable without fitting any metre.

## Resolution

In iambic trimeter, a long element may be **resolved** into two shorts (one extra
syllable). The scanner allows this where the practice does: on the resolvable
long elements only, never on the breves or the line-final element.

```python
from aegean import greek

sc = greek.scan_trimeter("Διόνυσον, ὃν τίκτει ποθ' ἡ Κάδμου κόρη")  # Bacchae 1
len(sc.syllables)   # 13 — one element resolved (Διό- = ⏑⏑)
sc.pattern          # '×⏑⏑⏑—|×—⏑—|×—⏑×'
```

The aeolic lines do **not** resolve (their choriambic nucleus is fixed), so for
them a line is a straight template match: right syllable count and every
position's quantity available, or it declines.

## Synizesis (curated, never guessed)

**Synizesis** is two (or three) written vowels read as a *single* metrical
syllable: e.g. the `-εω` of `Πηληϊάδεω` in *Iliad* 1.1. This is **lexical**, not
predictable from spelling, so pyaegean never *infers* it. A small curated lexicon
lists the words where it is standard; a line that only fits via synizesis on a
word **outside** that lexicon still declines rather than guessing.

| Word | Coalescing vowels | Why it's in the lexicon |
|---|---|---|
| Πηληϊάδεω | `εω` | the genitive ending `-εω` is one syllable (*Iliad* 1.1) |
| πόλεως | `εω` | Attic genitive, frequent in tragic trimeter |
| χρυσέῳ etc. | `εω` | adjectival `-εω` / `-εῳ` |
| θεούς | `εου` | three written vowels collapse to one syllable |

With the entry present, the line scans:

```python
from aegean import greek

greek.scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος").meter
# 'hexameter'   — Πηληϊάδεω is in the lexicon, so Iliad 1.1 scans

# πόλεως counts as two metrical syllables (πό + λεως) inside a trimeter
sc = greek.scan_trimeter("πόλεως ἄνακτα τόνδε δεσπότην ἐμόν")
sc.syllables[:2]    # ('πό', 'λεως')
sc.pattern          # '×—⏑—|×—⏑—|×—⏑×'
```

A diaeresis blocks the coalescence: in `Πηληϊάδεω` the `ϊ` (with diaeresis) is its
own syllable, exactly as the metre requires:

```python
greek.syllable_options("Πηληϊάδεω")
# [('Πη', ['heavy']), ('λη', ['heavy']), ('ϊ', ['heavy', 'light']),
#  ('ά', ['heavy', 'light']), ('δεω', ['heavy'])]
```

The lexicon is contribution-friendly and test-enforced: each entry must be
required by a real verse line that otherwise fails to scan. Three-vowel
coalescences beyond the listed `θεούς`-type case are out of the current model.

## Notes and limitations

- **Synizesis is not inferred.** A line needing it on an un-listed word declines.
  See the lexicon above; new entries are welcome.
- **Resolution** is supported in the iambic trimeter; the aeolic lines are fixed
  templates and do not resolve.
- **Metres in scope:** dactylic hexameter, elegiac pentameter, iambic trimeter,
  and the seven aeolic lines above. **Dactylo-epitrite** and **free astrophic
  lyric** are not yet covered.
- The scanner reads the text as written (Unicode polytonic or
  [Beta Code](Greek-NLP#normalization--beta-code) converted first); it does not
  edit, emend, or restore the text for you.
- When more than one valid scansion fits, the first is returned and
  `.ambiguous` is set to `True`: inspect it before trusting a single reading.

For the full picture of what the Greek prosody/scansion tools can and can't do,
see [Limitations](Limitations).

## See also

- [Greek NLP](Greek-NLP): the rest of the Greek toolkit (syllables, accents,
  prosody, IPA, morphology, lemmatisation).
- [Greek NLP · Prosody](Greek-NLP#prosody-syllable-quantity): per-syllable
  heavy/light/common weight for a single word.
- [Greek NLP · Metrical scansion](Greek-NLP#metrical-scansion): the same
  scanner in the context of the wider pipeline.
- [CLI](CLI): every `aegean` command and flag.
- [Tutorial](Tutorial): guided walkthroughs, including scanning a passage.
- [Limitations](Limitations): honest scope notes.
