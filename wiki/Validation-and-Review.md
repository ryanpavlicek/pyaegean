# Validation and review

This page is an honest record of how pyaegean's quality is checked, and, just as
important, how it is not. It is a transparency record, not a methods paper and
not a claim of external certification. The goal is that you can calibrate how far
to trust a result before you rely on it: what the toolkit checks against itself,
what rests on externally peer-reviewed scholarship, and what has had no outside
review at all.

pyaegean already documents its methodology in one place
([Methodology](Methodology)), its measured numbers and protocol in another
([Benchmarks](Benchmarks)), and its data and licences in a third
([Data & Provenance](Data-and-Provenance)). This page sits alongside them and
answers a narrower question: who and what has actually reviewed this, and how you
add your own review to the record.

---

## At a glance

| The question | The honest answer | Where to look |
| --- | --- | --- |
| Are the accuracy numbers reproducible? | Yes, from a recorded protocol on held-out data, with the commands to re-run them. | [Benchmarks](Benchmarks), [Methodology](Methodology) |
| Is the test set kept out of training? | Yes, by an exclusion manifest and a licence split. | [Methodology](Methodology#3-leakage-control) |
| Does each public function have a test that checks its output? | Yes, that is a project rule, not an aspiration. | [CONTRIBUTING](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#tests) |
| Are the numbers guarded against silent drift? | Yes, every published number is pinned to a registry that a test enforces per commit. | [The claims registry](#the-claims-registry) |
| Has the software had external scholarly peer review? | No. | [What has had outside review](#what-has-had-outside-review-and-what-has-not) |
| Has it had a formal external software audit? | No. | [What has had outside review](#what-has-had-outside-review-and-what-has-not) |
| How do I report an error or challenge a result? | Use the Correction, Validation, Data-contribution, or Reproduction-discrepancy form that matches it. | [How to submit a finding](#how-to-submit-a-finding-or-a-correction) |

---

## What runs against the codebase

Several checks run against pyaegean itself. They are internal (part of the
project, not commissioned from outside), and together they are what "checked"
means when the toolkit says a result is measured or established. The full test
suite, linting, and type-checking run in continuous integration on every
supported Python version before a release.

### The correctness-test rule

Every public function ships with a test that verifies its actual output: against
gold data, a hand-computed answer, or a property that must hold (a round-trip, a
range bound, a symmetry). A test that only confirms the call runs without error
does not count. The rule applies to the existing surface as well as new code, so
a function is not considered done until it has one. This is the difference
between "it runs" and "it is right": two shipped defects (a dead elision entry
and a wrong dative-plural accent) both passed a run-without-error check before
this rule caught the class.

### The benchmark protocol and leakage controls

The Greek NLP accuracy figures are measured, not asserted. The UD-Perseus and
UD-PROIEL test folds are scored with the official CoNLL 2018 evaluator (fetched
sha256-pinned), over each fold's gold tokenization, with bootstrap confidence
intervals. The Nestle 1904 New Testament is a separate out-of-domain check, scored
against its own gold lemmas and a reconciled part of speech as plain accuracy (it
carries no dependency trees, so no UAS/LAS and no bootstrap there). Out-of-domain
results are always reported next to in-family ones, so the generalization gap is
visible rather than hidden.

The numbers are kept honest against leakage two ways: an exclusion manifest
(`greek.agdt_ud_overlap()`) resolves every evaluation sentence to its training
source and removes it from training, and the treebanks the models train on are
separated by licence from the treebanks used only for evaluation, so the
evaluation folds are never trained on. The full protocol, the metric definitions,
and the leakage controls are on [Methodology](Methodology) and
[Benchmarks](Benchmarks); this page does not restate the figures.

### The claims registry

Every published number lives in a single registry
(`training/results/published-claims.json`). A test
(`tests/test_benchmark_claims.py`) pins the documentation to that registry on
every commit, so a number cannot change in the docs without changing the
registry, and a re-measurement script (`scripts/check_benchmarks.py`) re-derives
the offline-stack rows from it. A legitimate re-measurement updates the registry,
the docs, and the evidence together. This is what prevents a figure from drifting
quietly as the model or data underneath it changes.

### Adversarial internal audits

Periodically the whole project is audited adversarially: the audit tries to break
the toolkit rather than confirm it, from several angles at once. These include
correctness, regressions introduced by recent changes, whether a fix reached
every place the same class of bug occurs, behaviour on hostile or malformed
input, whether the documented example outputs still match the live code, and
scholarly correctness against standard authorities (Smyth, LSJ, the editions).
Each candidate finding is independently reproduced before it is accepted, so a
mistaken finding is refuted rather than acted on (a false report of a Greek error
is treated as worse than a miss). Confirmed findings land as fixes, each with a
regression test that pins the corrected behaviour.

---

## What these internal checks are, and are not

These checks are automated and adversarial, and they are assisted by large
language models. They are not external scholarly peer review, and they are not a
substitute for it. An adversarial internal audit can find a fabricated lemma, a
stale documented number, or an unhandled input; it cannot confer the authority
that comes from an independent expert in the field examining the work. Where this
page says a result is "checked," it means checked by the process above, not
endorsed by an outside reviewer.

---

## What has had outside review, and what has not

The distinction that matters for trust is between pyaegean's own software and the
scholarship it carries.

**Rests on externally peer-reviewed scholarship.** The established-tier data is
not pyaegean's own judgement: the sign values, the Greek lexicon and morphology,
the bundled transliterations, the treebank annotations, and the gold evaluation
data all come from editions, lexica, and datasets produced and reviewed by their
authors and editors (for example GORILA, the Perseus AGDT, LSJ, Nestle 1904,
DAMOS, and the epigraphic corpora). Each cites its source, and a wrong value
there is a correction against that source. The evaluation datasets and the scorer
are community-standard resources maintained outside this project.

**Has not had external review.** pyaegean's own code, the way it wires those
sources together, its measured numbers, and its exploratory output have not been
through external scholarly peer review or a formal external software audit. The
measured numbers are reproducible, but reproducible is not the same as externally
certified: nobody outside the project has been commissioned to re-run or sign off
on them. The undeciphered-script analyses (Linear A and Cypro-Minoan) and all
AI-layer output are exploratory by construction, labeled unverified at the point
of use, and are hypotheses rather than validated readings. See
[For Specialists](For-Specialists) and [Limitations](Limitations) for the
register model in full.

This is a plain statement of the current position, not a gap waiting on a
publication. The methodology is already written down and reproducible
([Methodology](Methodology), [Benchmarks](Benchmarks),
[Data & Provenance](Data-and-Provenance), and the training evidence linked from
Methodology), so the way to add external review is to reproduce a number,
challenge it, confirm or refute a hypothesis, or file a correction. Those are the
paths below.

---

## One-command evidence check

An independent reviewer can begin from a clean source checkout with:

```bash
python scripts/reproduce_review.py
```

The command verifies the canonical public evidence records by SHA-256 and reproduces
one small, project-authored offline result without network access, model execution,
bytecode, or cache writes. It reports exact manifest and result digests. A pass is a
bounded integrity and regression receipt, not external certification and not a rerun
of the neural benchmark. [Independent Review](Independent-Review) explains the output,
model and data cards, limitations, and discrepancy path.

---

## How to submit a finding or a correction

External review is welcome and is treated as first-class: a contributed fact
keeps its source, and a refutation is as valuable as a confirmation. There are
four lightweight paths, each a GitHub issue form (New issue, then pick a
template):

| Path | Use it when | What to include |
| --- | --- | --- |
| **Correction** | an established fact is wrong (a sign value, gloss, lemma, bridge reading, or a benchmark item) | the exact value and a source or authority |
| **Validation** | you have confirmed or refuted an exploratory result | the result, your verdict, and your reasoning and sources |
| **Data contribution** | you have a single, sourced, openly-licensed fact to add | the fact and its citation |
| **Reproduction discrepancy** | the review command, a benchmark protocol, or a recorded digest does not match | exact identities, environment, expected and observed output, and every local modification |

Before filing, [Limitations](Limitations) records what is already known not to
work, and [For Specialists](For-Specialists) (section 6) walks through each path
with the file each kind of fact lives in and the test that guards it. To correct
automated output in your own copy first (export, fix, re-import), and to see the
*shape* of the errors to expect rather than a single accuracy number, see
[When the Tool Is Wrong](When-the-Tool-Is-Wrong). When a computationally-assisted
result feeds your own work, cite it with its register named, so a reader can tell
an established fact from a measured number from an exploratory reading: see
[Citing Computational Assistance](Citing-Computational-Assistance).

Start the appropriate form from the
[issue chooser](https://github.com/ryanpavlicek/pyaegean/issues/new/choose); the
[contribution menu](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md#good-first-contributions-a-menu)
in CONTRIBUTING gives each kind of fact an obvious home and the test it must pass.

---

## See also

- [For Specialists](For-Specialists): the established / measured / exploratory
  register and the community review and contribution paths in full.
- [Benchmarks](Benchmarks) and [Methodology](Methodology): the measured numbers,
  the protocol, the leakage controls, and the claims registry.
- [Independent Review](Independent-Review): the bounded reproduction command, model
  and data cards, receipt map, and discrepancy form.
- [When the Tool Is Wrong](When-the-Tool-Is-Wrong): the error-shape view and the
  human-in-the-loop review loop.
- [Citing Computational Assistance](Citing-Computational-Assistance): naming the
  register when you cite a result.
- [Data & Provenance](Data-and-Provenance) and [Limitations](Limitations): where
  every source comes from, and the candid register of what the toolkit can and
  cannot claim.
