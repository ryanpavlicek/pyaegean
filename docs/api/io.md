# aegean.io

`to_review_table(corpus, path, selection="all")` exports annotations for review.
Choose `"flagged"` for rows selected by `needs_review_flag`, or `"unverified"`
for words with an unverified requested field (`fields=("lemma",)` by default). The default,
`"all"`, exports every word with a token position.

The unverified selection includes resolved predictions and source annotations
with no verification metadata. Only the string `true` (case-insensitive) excludes
a word; missing, empty, or unrecognized values do not establish verification.
Selection leaves the CSV's `needs_review` values unchanged and does not apply a
confidence threshold. Lemma verification says nothing about POS, morphology, or
dependencies. Use `fields=("pos", "morph")` for a grammar queue, or
`selection="sample", sample_size=40, seed=17` for a reproducible sample of
unflagged rows. Head/relation review (`fields=("head", "deprel")`) includes
complete, explicitly owned sentence context and validates edits as a whole tree.
Explicit `accept` decisions verify
an unchanged value; `correct`, `defer`, and `reject` record the decision for that
field. Blank decisions retain the legacy correction-only behavior. See the
[review guide](../review.md) for field-level audit records and merge conflicts.

Review preserves immutable alignment whitespace through review
merges and binds new snapshots to available source, analysis-generation, and
model/configuration identity. CLI annotation exports save the exact analysis
for later merge/apply and quote its path. CoNLL-U metadata
keys match exactly, preserving extension comments during canonical serialization.

Plain-text imports now default to `token_view="all"`: decoded source text,
punctuation, foreign text, numerals, and aligned offsets are retained. Use
`Document.words` for lexical tokens, or explicitly choose the former lossy import
with `token_view="words"` (`aegean import --token-view words`).
EpiDoc `<num value="…">` preserves the literal source attribute as
`annotations["epidoc:num_value"]`; this does not validate its numeric interpretation.

::: aegean.io
