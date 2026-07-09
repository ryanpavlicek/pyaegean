# When the tool is wrong

Automated Greek analysis is wrong some of the time, and a research or teaching tool earns
trust by making those errors visible and correctable rather than hiding them. This page shows
how to see *what kinds* of mistakes to expect (not just an accuracy percentage), and how to
correct them and feed the correction back.

## Aggregate accuracy hides the shape of the error

A single number ("94% lemma accuracy") does not tell you whether the 6% is scattered noise or
a systematic disagreement concentrated on one part of speech. `aegean greek eval … --drift`
answers that: it runs the model over a gold set and reports an error analysis instead of a
score.

```bash
aegean greek eval ud --drift        # UD-Perseus (in-domain, Classical)
aegean greek eval nt --drift        # Nestle 1904 New Testament (out-of-domain Koine)
aegean greek eval proiel --drift    # PROIEL treebank (out-of-domain)
```

Each prints (and `--json` emits) a breakdown:

- a **POS confusion matrix**, gold to predicted, most frequent first;
- **per-part-of-speech accuracy**, so you can see which categories are weak;
- the most common **lemma confusions**;
- a **seen-vs-unseen** split (substantive on the held-out AGDT eval, where forms carry a real
  "seen in training" flag).

Read the confusion matrix for *concentration*. If a few gold-to-predicted pairs carry most of
the POS errors (a high `top_share`), that points to an annotation-convention difference rather
than random error: two projects labelling the same word differently, not a mistake you should
"fix" in your reading. A long flat tail of one-off confusions is the opposite. The drift view
already reconciles the well-known convention gaps (PROPN with NOUN, SCONJ with CCONJ, AUX with
VERB) on both sides, so what remains is closer to genuine disagreement.

The numbers you get depend on the material: the model is strongest on text close to its
training distribution (Classical literary Greek) and weaker on Koine, inscriptions, papyri,
poetry, and dialect. [Benchmarks](Benchmarks) reports the measured accuracy by text type where
gold data exists, and is honest about where it does not.

## Common traps for a reader

Independent of any one run, a few error classes recur and are worth teaching:

- **Unseen forms.** A form the model has never seen is where lemmatization is hardest; the
  `lemma_source` will often be `rule` (a good guess for regular paradigms) or `unresolved`
  (the tool could not do it). See [Reading a Parse](Reading-a-Parse) for the evidence classes.
- **Homographs and proper names.** The same spelling with two lemmas, or a name mistaken for a
  common word, are frequent lemma confusions. A dictionary or commentary settles these.
- **Poetic and dialectal forms.** Contraction, unusual accentuation, and dialect spellings sit
  outside the regular paradigms and are more error-prone; poetry differs from prose here.
- **Restored or damaged text.** Where a corpus records editorial status (the Aegean scripts do
  today: certain / unclear / restored / lost), a supplied or damaged reading is flagged on the
  token, and an analysis built on a restoration inherits that uncertainty. See
  [Data & Provenance](Data-and-Provenance) for how status and edition metadata are carried.

## Correcting what you find

pyaegean supports the human-in-the-loop step directly. Export the machine annotations to a
spreadsheet, correct them, and read the corrections back:

```bash
aegean review export nt -o review.csv          # one row per word; --annotate for an un-annotated corpus
# open review.csv, fill the correct_lemma / correct_pos / correct_morph / reviewer_note columns
aegean review apply nt review.csv -o nt-reviewed.json --reviewer "Your Name"
```

The table flags the low-confidence tokens (the `needs_review` column) so you can triage; pass
`--only-needs-review` to export just those. Applying the corrections keeps each machine value
under a `<field>__pred` key and stamps who reviewed it and a provenance note, so the corrected
corpus records exactly what a human changed. See the workflow in [Recipes](Recipes) and the
table format in [Data & Provenance](Data-and-Provenance).

If the error is in pyaegean itself (a wrong bridge reading, a curated lemma, a benchmark
number), it belongs in the project, not just your copy: open a **correction** or **validation**
issue with the source you checked against (see [For Specialists](For-Specialists) and the issue
templates). Corrections that carry a citation are exactly what the project wants.

## See also

- [Reading a Parse](Reading-a-Parse): the evidence classes and what each field means.
- [Benchmarks](Benchmarks) and [Evaluation](Evaluation): the measured accuracy and the protocol.
- [Methodology](Methodology) and [Limitations](Limitations): what the numbers do and do not cover.
- [For Specialists](For-Specialists): the register model and how to submit a correction.
