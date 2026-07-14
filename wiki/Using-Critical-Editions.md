# Using critical editions

Epigraphic and papyrological texts are rarely whole. Stone breaks, ink fades, and a scribe's hand is
sometimes hard to read, so an editor marks which letters are certain, which are damaged but legible,
which are restored by conjecture, and which are lost. pyaegean's epigraphy and papyri corpora carry
that editorial judgement through to every token, so a restored or damaged reading is never presented
to you as if it were securely on the stone.

This page explains the reading-status marks, the `edition_fidelity` provenance flag, and how to work
with both.

## Reading status on every token

Each token of an inscription or papyrus carries a `ReadingStatus`:

| Status | Meaning | From the EpiDoc apparatus |
| --- | --- | --- |
| `CERTAIN` | Securely read on the object | plain edition text |
| `UNCLEAR` | Legible but damaged or ambiguous | `<unclear>` |
| `RESTORED` | Supplied by the editor (conjecture, parallels) | `<supplied>` |
| `LOST` | Editorially marked as not recoverable | `<supplied reason="undefined">`, lost gaps |

A word that is only partly damaged takes the most severe status touching any of its letters. The
editorial apparatus marks damage at the level of individual letters; a pyaegean `Token` holds one
status per word, so a word with even one restored letter is reported as `RESTORED`. This rounds
toward caution: it never understates how much of a word was reconstructed.

```python
import aegean
from aegean.core.model import ReadingStatus

corpus = aegean.load("isicily")            # a funerary text from Roman Sicily
doc = corpus.get("ISic000643")
for tok in doc.tokens:
    print(f"{tok.text:12} {tok.status.name}")
# ᾶρκος        CERTAIN
# Βαλήρις      CERTAIN
# Μαρκαρίων    UNCLEAR      the name is damaged
# ἔζησε        RESTORED     "lived", supplied by the editor
# ἔτη          CERTAIN
# νʹ           CERTAIN      50 (numeral)
# μῆνες        RESTORED
# ηʹ           CERTAIN      8
```

The plain reading text is unchanged from before status tracking: `" ".join(t.text for t in
doc.tokens)` reads exactly as the edition does. Status is additional information, not a rewrite of
the text.

### Diplomatic, regularized, and model-input forms

`ReadingStatus` is an aggregate word-level signal. A token-carrier EpiDoc import
can also preserve the pieces behind that signal in `Token.form_state`:

- `diplomatic` is the original or diplomatic spelling.
- `regularized` is an editorial spelling, for example a correction or expansion.
- `normalized` is an optional normalized preprocessing form.
- `model_input` is the exact string later handed to an analyzer, with
  `model_input_source` and ordered operations recording how it was selected.
- `segments` retain the order and status of certain, supplied, unclear, and lost
  pieces, plus semantic references to source markup when available.

These are not interchangeable. The first three fields and the segments describe
the evidence or an editorial representation. `model_input` describes a computation
and is not a claim that the source contained that spelling. `pipeline_tokens()`
selects an explicit model input first, then regularized, normalized, or diplomatic
text, and returns the selected value in the `TokenRecord` state.

The generic reader recognizes these states when they occur on token carriers such
as `<w>`, `<num>`, `<g>`, or `<seg>`, including `<choice>` and apparatus markup.
It does not turn arbitrary free-text TEI into a structured token state. The six
currently hosted epigraphy and papyri assets retain their legacy aggregate
`ReadingStatus` values and do not yet carry `TokenFormState`.

### Working with status

Filter to the securely-read text, or measure how much of a corpus is reconstruction:

```python
from collections import Counter

secure = [t.text for t in doc.tokens if t.status is ReadingStatus.CERTAIN]

dist = Counter(t.status.name for d in corpus.documents for t in d.tokens)
# {'CERTAIN': 22124, 'RESTORED': 5340, 'UNCLEAR': 1143, 'LOST': 312}
```

Roughly a fifth of the I.Sicily tokens are not securely read. That is normal for an epigraphic
corpus, and it is exactly the information a study should account for rather than discover too late.

Status round-trips through every persistence format: `Corpus.to_json` / `from_json`, the SQLite store
(`aegean.db`), and EpiDoc export all preserve it, and the token-level tabular exports (`to_csv`,
`to_parquet`, `to_dataframe`) carry it as a `status` column, so a spreadsheet can filter restored
readings out. On the current `main` branch, schema-3 JSON and SQLite also preserve typed form
states, while CSV and Parquet expose them as `form_*` columns and a JSON `form_segments` cell. A
corpus you load, filter, and re-save keeps the apparatus. Two caveats: the Workbench export format
carries token text only, so a Workbench round-trip drops statuses, typed form state, and
annotations and returns every token as
`CERTAIN`), and merging corpora keeps `edition_fidelity` only when every input agrees on one value
(a mixed merge reports it unknown).

## The `edition_fidelity` flag

Each corpus records, in its provenance, how faithful the shipped text is to the printed critical
edition:

```python
aegean.load("isicily").provenance.edition_fidelity
# 'apparatus-preserved,normalized'
aegean.load("igcyr").provenance.edition_fidelity
# 'apparatus-preserved,epichoric'
```

The comma-separated vocabulary:

- **`apparatus-preserved`** — the editorial apparatus is carried through as `ReadingStatus` (all six
  epigraphy and papyri corpora).
- **`normalized`** — the Greek is standard polytonic orthography, as the edition prints it.
- **`epichoric`** — the text keeps local, pre-standard letterforms rather than normalizing them. Only
  IGCyr/GVCyr is `epichoric`: it preserves the archaic Cyrenaean forms (for example a single letter
  for long *o*/*e*), so its tokens are deliberately not standard Koine spelling. Do not feed epichoric
  text to the normalized-Greek pipeline expecting standard results.

The flag is optional and additive: corpora without it (the bundled sample, the literary works, the
New Testament) report an empty string.

## Which corpora carry an apparatus

All six fetch-on-demand epigraphy and papyri corpora:

| Corpus | `edition_fidelity` | Notes |
| --- | --- | --- |
| `isicily` | `apparatus-preserved,normalized` | Greek inscriptions of Sicily |
| `iip` | `apparatus-preserved,normalized` | Israel/Palestine |
| `iospe` | `apparatus-preserved,normalized` | Northern Black Sea |
| `igcyr` | `apparatus-preserved,epichoric` | Cyrenaica: archaic Doric and verse |
| `edh` | `apparatus-preserved,normalized` | Epigraphic Database Heidelberg (Greek subset) |
| `ddbdp` | `apparatus-preserved,normalized` | Duke Databank documentary papyri |

The literary corpora (`greek`, the fetched Perseus/First1KGreek works, `nt`) are transmitted texts,
not editorial reconstructions of a damaged object, so they do not use reading status.

## The papyrological apparatus (DDbDP)

Documentary papyri record editorial choices differently from stone inscriptions. Where an editor
regularized a spelling, corrected a scribal error, or expanded an abbreviation, the DDbDP EpiDoc
encodes both the raw and the edited form. The currently hosted DDbDP asset exposes the preferred
reading and aggregate status, not a typed `TokenFormState`; a token-carrier EpiDoc file imported
directly can retain both forms. pyaegean takes the editor's preferred reading:

- a regularized spelling (`<reg>`) over the raw one (`<orig>`),
- the lemmatized/corrected reading (`<lem>`) over a rejected variant (`<rdg>`),
- an editorial addition (`<add>`) over a deletion (`<del>`),
- and abbreviation expansions in full.

Reading status is threaded through this the same way: a preferred reading that is itself supplied or
unclear keeps that status. Because DDbDP is large (57,331 texts), the memory-friendly path is the
full-text search index rather than materializing the whole corpus:

```bash
aegean db search ddbdp "ὁμολογῶ"     # instant FTS over the papyri
```

## Citing with fidelity

When you cite a subset or a query result, the provenance travels with it, including
`edition_fidelity` and the corpus licence. See [Citing Computational Assistance](Citing-Computational-Assistance)
for the full citation workflow. State in your own write-up whether your analysis included restored
readings or was restricted to securely-read text; the status marks make either choice reproducible.

## See also

- [Data & Provenance](Data-and-Provenance) — the corpora, licences, and sources
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong) — reading the tool's output critically
- [Reading a Parse](Reading-a-Parse) — evidence and uncertainty in the Greek NLP output
