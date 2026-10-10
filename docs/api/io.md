# aegean.io

`to_review_table(corpus, path, selection="all")` exports annotations for review.
Choose `"flagged"` for rows selected by `needs_review_flag`, or `"unverified"`
for words without an explicit `lemma_verified=true` annotation. The default,
`"all"`, exports every word with a token position.

The unverified selection includes resolved predictions and source annotations
with no verification metadata. Only the string `true` (case-insensitive) excludes
a word; missing, empty, or unrecognized values do not establish verification.
Selection leaves the CSV's `needs_review` values unchanged and does not apply a
confidence threshold. Lemma verification says nothing about POS, morphology, or
dependencies; use `"all"` to review all fields. Applying a changed lemma records
verification, while blank corrections or unchanged values do not.

::: aegean.io
