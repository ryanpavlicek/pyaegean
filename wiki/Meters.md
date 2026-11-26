# Meters

pyaegean's metrical scanner fits a line of Ancient Greek verse to a specified
metre's quantity template, returning the foot division, the resolved long/short
sequence, and (for spoken metres) the main caesura. Use it to test whether a line
scans, inspect how quantities resolve across word boundaries, or extract metrical
patterns across a verse corpus.

Scansion runs offline with no third-party dependencies, building on pyaegean's
syllabifier and word-level quantity rules. If you need only the heavy/light weight
of syllables inside a single word without fitting a line to a metre, use the
[word-level prosody](Greek-NLP#prosody-syllable-quantity) functions instead.

> New to pyaegean? Start with [Getting Started](Getting-Started). For the rest of
> the Greek pipeline, see [Greek NLP](Greek-NLP); for spoken-versus-written-language
> caveats, see [Limitations](Limitations).

## Quick start

```python
from aegean import greek

greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ").pattern
# '—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×'
```

From the terminal (`pip install "pyaegean[cli]"`):

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic
```

## Notation

Every pattern uses three glyphs:

| Glyph | Name | Meaning |
|---|---|---|
| `—` | heavy (longum) | long or closed syllable |
| `⏑` | light (breve) | short open syllable |
| `×` | anceps | position allowing either long or short (including line-final *brevis in longo*) |

Feet are separated by `|` in the printed pattern. Aeolic cola are printed as a
single unbroken sequence without foot dividers.

## Supported metres

Each example below was run through `aegean greek scan ... --meter <name>` (or the
corresponding Python call):

| `--meter` value | Template (`—` heavy · `⏑` light · `×` anceps) | Verified example line |
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

> The `alcaic_enneasyllable` and `alcaic_decasyllable` examples are constructed
> cola matching the templates exactly; the remaining eight are verse openings from
> Homer, Simonides, Sophocles, Euripides, Sappho, and Alcaeus.

The supported aeolic names are exported in `greek.AEOLIC_LINES`:

```python
from aegean import greek
greek.AEOLIC_LINES
# ('glyconic', 'pherecratean', 'sapphic_hendecasyllable', 'adonean',
#  'alcaic_hendecasyllable', 'alcaic_enneasyllable', 'alcaic_decasyllable')
```

## Functions and CLI mapping

Each metre family has a dedicated Python function alongside the `scan_line`
dispatcher. The CLI selects the metre with `--meter`.

| Python | Scans | CLI equivalent |
|---|---|---|
| `greek.scan_hexameter(line)` | dactylic hexameter | `aegean greek scan LINE` (default) |
| `greek.scan_pentameter(line)` | elegiac pentameter | `aegean greek scan LINE --meter pentameter` |
| `greek.scan_trimeter(line)` | iambic trimeter (with resolution) | `aegean greek scan LINE --meter trimeter` |
| `greek.scan_aeolic(line, line_type)` | one named aeolic colon | `aegean greek scan LINE --meter <line_type>` |
| `greek.scan_line(line, meter)` | any supported metre by name | `aegean greek scan LINE --meter <meter>` |
| `greek.score_scansion(line, meter)` | non-raising diagnostic `ScansionScore` (fit, caesura, dactyl ratio, resolution, lexical overrides) | — |
| `greek.syllable_options(line)` | pre-metrical syllable quantities | — |

`scan_line` and `score_scansion` accept `"hexameter"`, `"pentameter"`, `"trimeter"`,
or any name in `AEOLIC_LINES`. Unlike `scan_line`, `score_scansion` returns
`ScansionScore(scans=False, error=...)` on non-fitting lines instead of raising
`ScansionError`, and reports which curated synizesis or long-by-nature entries
were used:

```python
sc = greek.score_scansion("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος", meter="hexameter")
sc.scans, sc.dactyl_ratio, sc.synizesis_used
# (True, 0.75, ('Πηληϊάδεω',))
```

### Dactylic hexameter

Six feet: feet 1–5 are each a **dactyl** (`—⏑⏑`) or **spondee** (`——`), and the
sixth is `—×`. Quantities resolve across word boundaries, including *correptio
epica* (a word-final long vowel or diphthong in hiatus may scan short).

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

The second line of the elegiac couplet consists of two dactyl-or-spondee feet, a
longum, the central diaeresis (`‖`), two obligatory dactyls, and a final longum.

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

Because the central diaeresis is structural rather than a variable word-break,
`sc.caesura` is `None`.

### Iambic trimeter

Tragic and comic dialogue consists of three metra of `× — ⏑ —` (final element
anceps). Resolvable long elements may split into two shorts, so lines with 13 or
more syllables can still scan cleanly.

```python
from aegean import greek

# Antigone 1 (no resolution)
greek.scan_trimeter("ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα").pattern
# '×—⏑—|×—⏑—|×—⏑×'

# Bacchae 2 (Διό- resolves to ⏑⏑, 13 syllables)
sc = greek.scan_trimeter("Διόνυσον, ὃν τίκτει ποθ' ἡ Κάδμου κόρη")
sc.pattern              # '×⏑⏑⏑—|×—⏑—|×—⏑×'
len(sc.syllables)       # 13
```

```bash
aegean greek scan "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα" --meter trimeter
# ×—⏑—|×—⏑—|×—⏑×
# trimeter: metron, metron, metron; caesura: hephthemimeral
```

Trimeter reports a `penthemimeral` or `hephthemimeral` caesura when a word
boundary falls at the corresponding element.

### Aeolic lyric lines

Aeolic cola use fixed quantity templates without resolution in the choriambic
nucleus. Interior `×` positions represent the *aeolic base*; the final `×` is
*brevis in longo*. Call `scan_aeolic(line, line_type)` or
`scan_line(line, line_type)`.

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

All seven aeolic templates:

| `line_type` | Template | Notes |
|---|---|---|
| `glyconic` | `× × — ⏑ ⏑ — ⏑ ×` | base aeolic colon |
| `pherecratean` | `× × — ⏑ ⏑ — ×` | catalectic glyconic |
| `sapphic_hendecasyllable` | `— ⏑ — × — ⏑ ⏑ — ⏑ — ×` | Sapphic stanza line |
| `adonean` | `— ⏑ ⏑ — ×` | Sapphic stanza close |
| `alcaic_hendecasyllable` | `× — ⏑ — × — ⏑ ⏑ — ⏑ ×` | Alcaic stanza opening line |
| `alcaic_enneasyllable` | `× — ⏑ — × — ⏑ — ×` | 9-syllable Alcaic colon |
| `alcaic_decasyllable` | `— ⏑ ⏑ — ⏑ ⏑ — ⏑ — ×` | 10-syllable Alcaic colon |

## Return object: `LineScansion`

Both `scan_*` and `scan_line` return a `LineScansion`:

| Field / property | Type | Meaning |
|---|---|---|
| `.line` | `str` | input line |
| `.meter` | `str` | matched metre name |
| `.pattern` | `str` | glyph pattern (`—⏑⏑\|…`), feet joined by `\|` |
| `.feet` | tuple of `Foot` | each foot's `name`, `syllables`, and `quantities` |
| `.syllables` | tuple of `str` | line syllables in order |
| `.quantities` | tuple of `str` | resolved quantity per syllable (`"heavy"`, `"light"`, or `"anceps"`) |
| `.caesura` | `str` or `None` | `"penthemimeral"`, `"trochaic"`, `"hephthemimeral"`, or `None` |
| `.caesura_index` | `int` or `None` | syllable index preceded by the caesura |
| `.ambiguous` | `bool` | `True` if more than one valid scansion fit the template |

Each `Foot` carries:

| `Foot` field | Meaning |
|---|---|
| `.name` | `dactyl`, `spondee`, `longum`, `final`, `metron`, or the aeolic colon name |
| `.syllables` | syllables spanned by the foot |
| `.quantities` | resolved quantities for those syllables |

```python
from aegean import greek

sc = greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
sc.feet[0].name           # 'dactyl'
sc.feet[0].syllables      # ('ἄν', 'δρα', 'μοι')
sc.feet[0].quantities     # ('heavy', 'light', 'light')
sc.quantities[2]          # 'light' (μοι shortened by correptio before ἔννεπε)
```

In Jupyter or Colab, `LineScansion` renders as an HTML card showing the line,
glyph pattern, metre, and foot table; elsewhere `str(sc)` returns `sc.pattern`.

### JSON output from the CLI

`--json` emits the full analysis (feet, per-syllable quantities, caesura, and
ambiguity flag):

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

Pass `-` as the line argument to read from stdin.

## Strict failure on non-matching lines

The scanner returns a result only when the line satisfies the template. If a line
fails to fit, Python raises `ScansionError` and the CLI exits with status 1 and a
diagnostic message:

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

An unknown metre name fails in the same way and lists the valid options:

```bash
aegean greek scan "φαίνεταί μοι κῆνος ἴσος θέοισιν" --meter not_a_metre
# aegean: unknown meter 'not_a_metre'; available: adonean, alcaic_decasyllable,
#   alcaic_enneasyllable, alcaic_hendecasyllable, glyconic, hexameter,
#   pentameter, pherecratean, sapphic_hendecasyllable, trimeter
# (exit code 1)
```

## Syllable-quantity rules

Before template matching, each syllable is assigned the set of quantities allowed
by its phonology and context; the metre then resolves open choices:

| Context | Allowed quantities |
|---|---|
| closed by position (two or more consonants, or double `ζ`/`ξ`/`ψ`, before the next nucleus) | heavy |
| short vowel before *muta cum liquida* (stop + liquid/nasal) | **common** (heavy or light) |
| open syllable with long nucleus (`η`, `ω`, circumflex, iota subscript, or diphthong) | heavy |
| open syllable with short nucleus (`ε`, `ο`) | light |
| open *dichronon* (`α`, `ι`, `υ`, length not determined by spelling) | **common** (heavy or light) |
| word-final long vowel or diphthong in hiatus (*correptio epica*) | heavy or light |

Inspect this pre-metrical layer directly with `syllable_options`, which is useful
when diagnosing why a line fails to scan:

```python
from aegean import greek

greek.syllable_options("πατρός")
# [('πα', ['heavy', 'light']), ('τρός', ['light'])]
# πα is common: short α before stop+liquid τρ (muta cum liquida)
```

`syllable_options` applies cross-word position and correptio across the full line.
For isolated single-word syllable weights, use
[`greek.scan`](Greek-NLP#prosody-syllable-quantity), which returns `heavy`,
`light`, or `common` per syllable without fitting a metre.

## Resolution

In iambic trimeter, a resolvable long element may split into two shorts (adding
one syllable). The scanner permits resolution only on resolvable long positions,
never on breves or the line-final element.

```python
from aegean import greek

sc = greek.scan_trimeter("Διόνυσον, ὃν τίκτει ποθ' ἡ Κάδμου κόρη")  # Bacchae 2
len(sc.syllables)   # 13 (one element resolved: Διό- = ⏑⏑)
sc.pattern          # '×⏑⏑⏑—|×—⏑—|×—⏑×'
```

Aeolic templates do not resolve. A line must match the template's exact syllable
count and quantity constraints, or `ScansionError` is raised.

## Synizesis

**Synizesis** merges two (or three) written vowels into a single metrical
syllable, such as the `-εω` of `Πηληϊάδεω` in *Iliad* 1.1. Because synizesis is
lexical rather than predictable from spelling, pyaegean never infers it. Only
words in a curated synizesis lexicon allow coalescence; any line requiring
synizesis on an unlisted word raises `ScansionError`.

| Word | Coalescing vowels | Basis |
|---|---|---|
| `Πηληϊάδεω` | `εω` | genitive `-εω` scanned as one syllable (*Iliad* 1.1) |
| `πόλεως` | `εω` | Attic genitive, frequent in tragic trimeter |
| `χρυσέῳ` etc. | `εω` | adjectival `-εω` / `-εῳ` |
| `θεούς` | `εου` | three written vowels coalescing into one syllable |
| `θεοί` | `εοι` | optional hexameter reading (*Iliad* 1.18); two syllables in other contexts |

`θεοί` belongs to a separate optional hexameter list. The scanner tests the
uncoalesced reading first, then curated coalescences independently per occurrence,
setting `ambiguous=True` if multiple fits succeed. Search is capped at eight
optional occurrences (256 combinations); lines exceeding that cap raise
`ScansionError` instead of reporting a fit from a truncated search. General
syllabification and non-hexameter metres retain the uncoalesced reading of
optional entries.

```python
from aegean import greek

greek.scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος").meter
# 'hexameter' (Πηληϊάδεω is in the lexicon, so Iliad 1.1 scans)

# πόλεως counts as two syllables (πό + λεως) in trimeter
sc = greek.scan_trimeter("πόλεως ἄνακτα τόνδε δεσπότην ἐμόν")
sc.syllables[:2]    # ('πό', 'λεως')
sc.pattern          # '×—⏑—|×—⏑—|×—⏑×'
```

A diaeresis blocks coalescence. In `Πηληϊάδεω`, the `ϊ` remains its own syllable:

```python
greek.syllable_options("Πηληϊάδεω")
# [('Πη', ['heavy']), ('λη', ['heavy']), ('ϊ', ['heavy', 'light']),
#  ('ά', ['heavy', 'light']), ('δεω', ['heavy'])]
```

Every lexicon entry is test-enforced: it must be required by an attested verse
line that fails without it. Optional entries also require evidence that their
uncoalesced reading remains valid in other lines.

## Notes and limitations

- **Synizesis is strictly lexical.** Lines requiring synizesis on unlisted words
  raise `ScansionError`.
- **Resolution** is implemented for iambic trimeter only; aeolic templates are
  fixed.
- **Supported metres:** dactylic hexameter, elegiac pentameter, iambic trimeter,
  and the seven aeolic cola listed above. Dactylo-epitrite and free astrophic
  lyric are out of scope.
- **No textual emendation.** The scanner reads the supplied text as written
  (polytonic Unicode, or [Beta Code](Greek-NLP#normalization--beta-code) converted
  beforehand) and does not edit or restore lines.
- **Ambiguity.** When multiple valid scansions fit, the first match is returned
  with `.ambiguous = True`.

For full prosody and scansion limitations, see [Limitations](Limitations).

## See also

- [Greek NLP](Greek-NLP): syllabification, accents, prosody, IPA, morphology, and lemmatization
- [Greek NLP · Prosody](Greek-NLP#prosody-syllable-quantity): single-word syllable weights
- [Greek NLP · Metrical scansion](Greek-NLP#metrical-scansion): scansion within the wider pipeline
- [CLI](CLI): `aegean` commands and flags
- [Tutorial](Tutorial): guided walkthroughs, including scansion
- [Limitations](Limitations): scope and known gaps
