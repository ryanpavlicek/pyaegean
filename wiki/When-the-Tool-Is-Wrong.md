# When the tool is wrong

Automated Greek analysis makes mistakes. This page explains how to inspect
error patterns beyond a single aggregate score, which error classes recur in
Greek texts, and how to correct annotations locally or report defects upstream.

## Inspecting error patterns with `--drift`

An aggregate score such as 94% lemma accuracy hides whether the remaining 6% is
scattered noise or concentrated on one part of speech or annotation convention.
`aegean greek eval … --drift` runs the active model on a gold fold and outputs
an error breakdown:

```bash
aegean greek eval ud --drift        # UD-Perseus (in-domain Classical)
aegean greek eval nt --drift        # Nestle 1904 New Testament (out-of-domain Koine)
aegean greek eval proiel --drift    # PROIEL treebank (out-of-domain)
```

Each run prints (and `--json` emits):

- a **POS confusion matrix** (gold to predicted, ordered by frequency),
- **per-part-of-speech accuracy** to locate weak categories,
- the most frequent **lemma confusions**,
- a **seen-vs-unseen** split (substantive on held-out AGDT evaluation, where
  forms track whether they appeared in training).

Check the confusion matrix for concentration. A high `top_share` (most POS
errors falling into a few gold-to-predicted pairs) signals a convention mismatch
between treebanks rather than random tagging mistakes. A flat tail of one-off
errors points to genuine model difficulty. The drift report reconciles standard
POS scheme overlaps (`PROPN`/`NOUN`, `SCONJ`/`CCONJ`, `AUX`/`VERB`) on both
sides so remaining counts reflect substantive disagreement.

Accuracy also depends on genre and period. The neural model performs best on
Classical literary prose near its training distribution and drops on Koine,
documentary papyri, inscriptions, verse, and Byzantine orthography. See
[Benchmarks](Benchmarks) for per-domain scores and gaps where no gold fold
exists.

## Recurring error classes

Four failure patterns appear regularly across Greek texts:

- **Unseen forms.** Inflected forms absent from training are the hardest to
  lemmatize. Check `lemma_source`: `rule` handles regular paradigms, whereas
  `identity` and `unresolved` flag forms requiring manual lookup (see
  [Reading a Parse](Reading-a-Parse)).
- **Homographs and proper names.** Identical spellings belonging to distinct
  lemmas and personal or place names parsed as common nouns account for a large
  share of lemma errors. Verify these against a lexicon or commentary.
- **Poetic and dialectal forms.** Contractions, Doric or Ionic vowel shifts,
  epic endings, and non-Attic accentuation fall outside regular prose paradigms
  and produce higher error rates.
- **Restored or damaged text.** Both the Aegean corpora and all eight
  fetch-on-demand epigraphy and papyri corpora carry `ReadingStatus`
  (`CERTAIN`, `UNCLEAR`, `RESTORED`, `LOST`), and direct token-carrier EpiDoc
  imports preserve `TokenFormState`. Any parse of a restored or unclear token
  inherits the uncertainty of the underlying editorial reading; see
  [Using Critical Editions](Using-Critical-Editions) and
  [Data & Provenance](Data-and-Provenance).

## Correcting annotations in your own copy

Export machine annotations to a review CSV, record human decisions, and apply
them back to the corpus:

```bash
aegean review export nt -o review.csv          # one row per token; add --annotate to generate predictions
# Edit decision_lemma / decision_pos / decision_morph and correct_* columns
# (or review interactively with `aegean tui --review review.csv`)
aegean review apply nt review.csv -o nt-reviewed.json --reviewer "Your Name"
```

### Selecting rows and fields

- `needs_review` checks an explicit review flag first, then falls back to
  `identity`/`unresolved` lemma provenance or legacy unresolved metadata.
- `--selection flagged` exports only flagged rows; it applies no confidence
  cutoff and can miss incorrect resolved lemmas, POS tags, or dependency arcs.
  Keep the default `--selection all` for exhaustive review.
- `--selection unverified` exports every token lacking an explicit
  `lemma_verified=true` (case-insensitive), including resolved predictions and
  unverified source annotations, without modifying `needs_review`.
- Repeat `--field pos --field morph` with `--selection unverified` to target
  grammar, or use `--selection sample --sample-size 40 --seed 17` for a
  reproducible sample of unflagged tokens.
- Including `--field head --field deprel` exports full sentence context and
  validates that edited trees remain well-formed.

### Prioritizing limited editorial time

When reviewing a large corpus, generate calibrated neural confidence scores,
export a compact spreadsheet, and rank rows by calibrated risk:

```bash
aegean review export corpus.json -o review.csv \
  --annotate --neural --with-confidence --confidence-domain literary \
  --layout editable --priority calibrated-risk --budget 50
```

Use `--confidence-domain documentary_native` for documentary papyri.
`--layout editable` places decision columns first and stores full provenance in
a SHA-256-bound `.companion.json` sidecar. You can edit the CSV in a
spreadsheet or review and adjudicate multi-reviewer copies directly in the
terminal via `aegean tui --review review.csv` (see
[Validation & Review](Validation-and-Review) and [TUI](TUI)).

### Recording decisions and preserving history

Set `decision_lemma`, `decision_pos`, or `decision_morph` to `accept` (verify
an unchanged prediction), `correct` (replace using the corresponding
`correct_*` column), `defer`, or `reject` (both remain unverified). Use
`reviewer_note` and `reviewer_evidence` to record explanations and citations.
If decision columns are left blank, legacy correction-only rules apply: only a
changed value marks a field verified, and verifying one field never certifies
another.

When `aegean review export` runs with `--annotate`, it saves the annotated
corpus JSON beside the CSV. Pass that exact snapshot to `aegean review merge`
and `aegean review apply`: snapshots bind analysis identity as well as source
tokens, so re-annotating invalidates older snapshots even if predicted words
coincide.

Applying a reviewed CSV preserves prior predictions under `<field>__pred`,
writes per-field decisions, verification flags, reviewer IDs, notes, and
evidence, and appends dated entries to `review_history`. Accepting a prediction
keeps its original source; correcting a lemma records `user` provenance beside
the prior source. Subsequent reanalysis marks affected current decisions stale
while preserving history. See [Recipes](Recipes) and the Review section of
[CLI: Greek NLP & Review](CLI-Greek).

## Reporting upstream errors

If an error lies in pyaegean's established data (a bridge reading, sign value,
curated lemma, or syllabification exception) or in a published benchmark, open
a **Correction** or **Validation** issue citing the published authority; see
[For Specialists](For-Specialists).

## See also

- [Reading a Parse](Reading-a-Parse): token fields, provenance classes, and
  calibrated confidence
- [Validation & Review](Validation-and-Review): interactive TUI adjudication
  and reproducible research bundles
- [Using Critical Editions](Using-Critical-Editions): `ReadingStatus` and
  `TokenFormState` across epigraphy and papyri
- [Benchmarks](Benchmarks) and [Evaluation](Evaluation): measured accuracy and
  protocols
- [Methodology](Methodology) and [Limitations](Limitations): protocol details
  and scope boundaries
- [For Specialists](For-Specialists): evidence registers and upstream
  correction paths
