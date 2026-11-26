# Using critical editions

Epigraphic and papyrological texts rarely survive intact. Editors mark which
letters are legible on the stone or papyrus, which are damaged, which are
supplied by conjecture, and which are lost. pyaegean's epigraphy and papyri
corpora carry those editorial distinctions on every token so restored or
damaged words stay distinguishable from securely preserved text.

This page explains token reading statuses, typed form states, the
`edition_fidelity` provenance flag, and how the epigraphic and papyrological
corpora represent editorial choices.

## Reading status on every token

Every token in an epigraphic or papyrological corpus carries a `ReadingStatus`:

| Status | Meaning | EpiDoc source |
| --- | --- | --- |
| `CERTAIN` | Securely read on the object | Plain edition text |
| `UNCLEAR` | Legible but damaged or ambiguous | `<unclear>` |
| `RESTORED` | Supplied by the editor (conjecture or parallels) | `<supplied>` |
| `LOST` | Marked as not recoverable | `<supplied reason="undefined">`, lacunae |

Editorial apparatuses mark damage letter by letter, whereas a pyaegean `Token`
stores one aggregate status per word. A partially damaged token takes the most
severe status affecting any of its letters, so a word with even one supplied
letter carries `RESTORED`.

```python
import aegean
from aegean.core.model import ReadingStatus

corpus = aegean.load("isicily")            # funerary inscription from Roman Sicily
doc = corpus.get("ISic000643")
for tok in doc.tokens:
    print(f"{tok.text:12} {tok.status.name}")
# ᾶρκος        CERTAIN
# Βαλήρις      CERTAIN
# Μαρκαρίων    UNCLEAR      damaged name
# ἔζησε        RESTORED     "lived", editorially supplied
# ἔτη          CERTAIN
# νʹ           CERTAIN      50 (numeral)
# μῆνες        RESTORED
# ηʹ           CERTAIN      8
```

`ReadingStatus` sits beside `token.text` without altering it:
`" ".join(t.text for t in doc.tokens)` reproduces the plain reading text of the
edition.

### Diplomatic, regularized, and model-input forms

While `ReadingStatus` summarizes a token as a single value, direct token-carrier
EpiDoc imports also preserve fine-grained layers in `Token.form_state`:

- `diplomatic`: original or diplomatic spelling on the artifact.
- `regularized`: editorial spelling (correction or expansion).
- `normalized`: optional normalized preprocessing form.
- `model_input`: exact string handed to an analyzer, paired with
  `model_input_source` and ordered operations recording how it was derived.
- `segments`: ordered spans carrying per-segment status (`certain`, `supplied`,
  `unclear`, `lost`) and source markup references when present.

The first three fields and `segments` represent documentary or editorial
evidence; `model_input` records computational input and makes no claim that the
source contained that spelling. `pipeline_tokens()` selects an explicit
`model_input` first, then `regularized`, `normalized`, or `diplomatic`, and
records the chosen string on the resulting `TokenRecord`.

The generic EpiDoc reader populates `TokenFormState` from token carriers
(`<w>`, `<num>`, `<g>`, `<pc>`, `<seg>`), including `<choice>` and apparatus
elements. It does not parse arbitrary free-text TEI into structured token
states. The eight hosted epigraphy and papyri assets retain aggregate
`ReadingStatus` values and do not yet populate `TokenFormState`.

### Filtering and counting by status

Filter to securely read words or count how much of a corpus relies on
restoration:

```python
from collections import Counter
from aegean.core.model import ReadingStatus

secure = [t.text for t in doc.tokens if t.status is ReadingStatus.CERTAIN]

dist = Counter(t.status.name for d in corpus.documents for t in d.tokens)
# {'CERTAIN': 22139, 'RESTORED': 5328, 'UNCLEAR': 1134, 'LOST': 312}
```

Roughly 23% of I.Sicily tokens (6,774 of 28,913) are restored, unclear, or lost.
Accounting for that share is standard practice in quantitative epigraphy.

`ReadingStatus` round-trips through `Corpus.to_json` / `from_json`, SQLite
(`aegean.db`), and EpiDoc export, and appears as a `status` column in `to_csv`,
`to_parquet`, and `to_dataframe`. Schema-3 JSON and SQLite also preserve
`TokenFormState`, while CSV and Parquet expose `form_*` columns and a JSON
`form_segments` cell. Two exceptions apply: the Workbench export format stores
token text only (so round-tripping through Workbench resets statuses to
`CERTAIN` and drops form states and annotations), and merging corpora preserves
`edition_fidelity` only when all inputs share the same value.

## The `edition_fidelity` provenance flag

`corpus.provenance.edition_fidelity` records how the text relates to its
printed edition:

```python
aegean.load("isicily").provenance.edition_fidelity
# 'apparatus-preserved,normalized'
aegean.load("igcyr").provenance.edition_fidelity
# 'apparatus-preserved,epichoric'
```

Vocabulary (comma-separated):

- **`apparatus-preserved`:** editorial apparatus is carried on tokens via
  `ReadingStatus` (all eight epigraphy and papyri corpora).
- **`normalized`:** Greek appears in standard polytonic orthography as printed
  by the edition.
- **`epichoric`:** local, pre-standard letterforms are preserved rather than
  normalized. Only IGCyr/GVCyr carries `epichoric` (archaic Cyrenaean
  orthography, such as single letters for long *e* and *o*); do not expect
  standard literary-Greek accuracy when passing epichoric tokens to the
  normalized pipeline.
- **`ocr`:** automated OCR transcription (*Patrologia Graeca* CGPG volumes via
  `aegean.load("patrologia")`), where optical character errors occur.

Corpora without these flags (bundled samples, literary works, New Testament)
leave `edition_fidelity` as an empty string.

## Corpora with apparatus status

All eight fetch-on-demand epigraphy and papyri corpora carry `ReadingStatus`:

| Corpus | `edition_fidelity` | Scope |
| --- | --- | --- |
| `isicily` | `apparatus-preserved,normalized` | Greek inscriptions of Sicily |
| `iip` | `apparatus-preserved,normalized` | Inscriptions of Israel/Palestine |
| `iospe` | `apparatus-preserved,normalized` | Inscriptions of the Northern Black Sea |
| `igcyr` | `apparatus-preserved,epichoric` | Cyrenaica (archaic Doric and verse) |
| `edh` | `apparatus-preserved,normalized` | Epigraphic Database Heidelberg (Greek subset) |
| `aphrodisias` | `apparatus-preserved,normalized` | Inscriptions of Aphrodisias (IAph2007, Caria) |
| `crete` | `apparatus-preserved,normalized` | Cretan Institutional Inscriptions (Archaic–Hellenistic Crete) |
| `ddbdp` | `apparatus-preserved,normalized` | Duke Databank of Documentary Papyri |

Transmitted literary corpora (`greek`, Perseus/First1KGreek works, `nt`) do not
carry stone/papyrus reading status.

## Documentary papyri (DDbDP)

Where a papyrus editor regularized a spelling, corrected a scribal error, or
expanded an abbreviation, DDbDP EpiDoc encodes both original and edited forms.
The hosted DDbDP asset exposes the editor's preferred reading and aggregate
`ReadingStatus` (importing token-carrier EpiDoc directly retains both layers in
`TokenFormState`):

- regularized spelling (`<reg>`) over original spelling (`<orig>`),
- corrected or lemmatized reading (`<lem>`) over rejected variant (`<rdg>`),
- editorial addition (`<add>`) over deletion (`<del>`),
- expanded abbreviations in full.

If the preferred reading itself is supplied or unclear, that status carries
through. Because DDbDP holds 57,331 texts, query the SQLite full-text index
directly or stream with `aegean.db.stream` instead of loading the entire corpus
into memory:

```bash
aegean db search ddbdp "ὁμολογῶ"
```

## Citing editorial choices

Filtered subsets and query results retain `edition_fidelity` and upstream
license metadata in their provenance; see
[Citing Computational Assistance](Citing-Computational-Assistance). In published
counts, state explicitly whether restored and unclear tokens were included or
filtered to `ReadingStatus.CERTAIN`.

## See also

- [Data & Provenance](Data-and-Provenance): dataset catalog, licenses, and sources
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): error analysis and review workflows
- [Reading a Parse](Reading-a-Parse): per-token provenance and calibrated confidence
