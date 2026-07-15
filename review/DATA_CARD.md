# Data card: Greek neural training and evaluation

## Scope

This card describes the data roles behind the shipped `grc-joint-v3` model and its
published Greek NLP measurements. It does not describe every corpus loadable through
pyaegean. The broader catalogue, provenance, and licensing record is the wiki's
[Data and Provenance](https://github.com/ryanpavlicek/pyaegean/wiki/Data-and-Provenance)
page.

## Data roles

| Role | Sources | Use |
| --- | --- | --- |
| Training | AGDT, Gorman, Pedalion | Joint tags, morphology, dependency parsing, and lemma learning |
| Development | UD Ancient Greek Perseus development material, plus declared successor-gate development sources | Early stopping, model selection, development diagnostics, and permitted calibration |
| Primary locked test | UD Ancient Greek Perseus test | In-family report after candidate freeze |
| Out-of-domain test | UD Ancient Greek PROIEL test | Separate generalization and convention-sensitive report; never a training source |
| Additional evaluation | Greek New Testament, documentary PapyGreek, a small tragedy fold, Byzantine verse, and DBBE where the task is supported | Domain-specific rows reported separately, with their own tasks and caveats |

The exact folds, revisions, checksums, token counts, evaluator identity, and scoring
rules are in [`docs/benchmarks.md`](../docs/benchmarks.md). This summary must not be
used to substitute one fold for another.

## Separation and leakage controls

UD Perseus development and test sentences are removed from training by normalized
form-sequence identity, not only by repository or filename. PapyGreek adds a
source-native work-identity exclusion before sentence-level comparisons. Evaluation
folds are kept separate because genre, register, orthography, available labels, and
annotation scheme differ.

Development evidence may guide candidate choices. Locked test evidence may not. A
future candidate is selected against a predeclared development population and policy,
then evaluated once on the locked matrix after freeze. The shipped v3 evidence remains
immutable while successor work proceeds.

## Annotation and representation

The linguistic targets use the Universal Dependencies family of representations:
universal and treebank-specific part of speech, complete feature bundles, lemmas,
dependency heads, and relations where available. Different treebanks do not always
encode the same distinctions. Exact comparison of XPOS, UFeats, or relation labels can
therefore measure convention mismatch as well as model behavior.

Source text may be diplomatic, regularized, or otherwise normalized. Those forms are
not interchangeable. Domain reports state which representation was evaluated, and
documentary results keep regularized and diplomatic-orthography questions separate.

## Licenses and distribution

| Material | Distribution boundary |
| --- | --- |
| AGDT, Gorman, Pedalion training sources | ShareAlike-compatible training sources; their attribution and license obligations pass to the model |
| UD Perseus and PROIEL evaluation folds | CC BY-NC-SA; fetched for research evaluation, never bundled or used for training |
| Neural model | CC BY-SA 4.0; fetched because of size and kept outside the Apache-2.0 wheel |
| Project-authored offline review fixture | Included under the project's Apache-2.0 license; a regression fixture, not neural gold evidence |
| Other evaluation sources | Governed by their recorded upstream license and task-specific protocol |

The authoritative per-asset notices are [`NOTICE`](../NOTICE), the package data
registry, and the source records named by the benchmark protocol.

## Known coverage limits

- The primary held-out literary folds are prose. The leakage-clean tragedy sample is
  small, and no leakage-clean epic gold fold is currently available.
- Documentary, New Testament, and Byzantine material differ from the training mix in
  register, orthography, or annotation tradition.
- PROIEL feature and dependency-label scores are substantially affected by scheme
  differences.
- Historical corpora reproduce editorial choices and annotation errors as well as
  linguistic evidence.
- Ancient corpora do not provide demographic balance in the sense expected of modern
  person-centered datasets; their surviving genres, authors, periods, and regions are
  uneven.

## Privacy, sensitive content, and foreseeable harm

The sources are historical texts and scholarly annotations rather than private modern
records. The main foreseeable harms are epistemic: presenting a model prediction as a
settled reading, erasing editorial uncertainty, comparing incompatible schemes as if
they were identical, or generalizing a prose score to an unsupported register. Users
should retain source forms and provenance and route consequential readings to expert
review.

## Maintenance and correction

Each changed fact needs an upstream citation, a compatible license, the relevant
provenance or notice update, and a focused test. Evaluation values change only through
the locked benchmark process. Report a data or protocol discrepancy through the
[independent review kit](README.md); contribute a sourced fact through
[`CONTRIBUTING.md`](../CONTRIBUTING.md).
