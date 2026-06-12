# For specialists

This page is for the people pyaegean most wants to hear from: Aegean
epigraphers, Mycenologists, classical philologists, historical linguists. The
toolkit is built to be **honest about what it knows** and easy to correct where
it's wrong — your judgement is part of how it stays trustworthy.

## What is established vs. exploratory

pyaegean draws a hard line between settled scholarship and machine-generated
hypotheses, and labels every result accordingly.

- **Established** — facts carried from editions, lexica, and the Unicode
  standard: the Linear B / Cypriot sign values, the Greek morphology and lexicon
  (Perseus AGDT, LSJ), the bundled transliterations, the find-site gazetteer.
  These cite their source (see [Data & Provenance](Data-and-Provenance) and
  `NOTICE`); if one is wrong, it's a **correction**.
- **Measured** — model accuracies reported leakage-free on held-out data (the
  Greek lemmatizer/tagger/parser and the neural pipeline). The protocol and the
  numbers are in [Greek NLP](Greek-NLP); reproduce or challenge them.
- **Exploratory** — anything decipherment-adjacent over the **undeciphered**
  Linear A material (cross-linguistic distances, morphological clusters,
  structure heuristics) and **all** AI-layer output. These are labeled
  hypotheses with provenance, never claims. The AI layer additionally shows its
  grounding: `result.trace()` (or `--trace` on the CLI) lists the local,
  non-generative facts an answer rested on, and `aegean.ai.run_eval` measures how
  faithfully the model used that evidence. See [AI Layer](AI-Layer).

The full, candid register of what the toolkit can and cannot claim — by evidence,
licensing, engineering, and design — lives on the [Limitations](Limitations)
page and is kept current as a living document.

## How to help

Three lightweight paths, each a GitHub issue form (New issue → pick a template):

- **Correction** — a reading, gloss, lemma, sign value, or translation is wrong.
  Point to the exact value and give a source; it becomes a verifiable fix.
- **Validation** — confirm or refute an exploratory result. A refutation is as
  valuable as a confirmation; pasting the AI `trace()` helps others see the
  evidence it used.
- **Data contribution** — a single sourced fact: a Linear B → Greek equation, a
  sign value, a Pleiades ID, a benchmark item. (A pull request is welcome too —
  see the [contribution menu](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#good-first-contributions-a-menu),
  where each kind has an obvious home and an automatic test.)

Corrections and validations are triaged into the codebase or the limitations
register; data contributions land in a bundled lexicon/JSON with their citation
and a test. Either way, **attribution is first-class** — contributed facts keep
their source.

## A note on citation

When a result feeds academic work, cite the underlying edition, not pyaegean's
convenience layer: `corpus.provenance.cite()`, `Corpus.cite(style=…)`, and the
per-subset `QueryResults.cite()` produce the right reference (BibTeX or APA). The
package's own structured-data layer is Apache-2.0; the scholarly editions and
imagery remain under their own rights.
