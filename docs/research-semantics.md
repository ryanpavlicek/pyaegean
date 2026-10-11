# Reproducible word counts and account selection

Corpus counts describe a selected text view and population. They do not establish
that a lemma, restored reading, or accounting interpretation is correct.

```python
frequencies = corpus.word_frequencies(view="normalized")
print(frequencies[:10])             # ordinary (word, count) pairs
print(frequencies.metadata)         # normalization, denominator, exclusions
print(frequencies.cite())           # source plus counting choices

lemmas = corpus.word_frequencies(view="lemma", statuses=["certain"])
documents = corpus.word_frequencies(view="lemma", count_unit="document")
```

The existing methods accept these choices:

| Option | Meaning |
| --- | --- |
| `view="surface"` | Exact `Token.text`; case and canonical Unicode spelling remain distinct. |
| `view="normalized"` | NFC, lowercase, final-sigma folding, then NFC. Accents, breathings, and iota subscript remain distinct. This is a comparison key, not the token's editorial `form_state.normalized`. |
| `view="lemma"` | Apply the same normalization to the existing `annotations["lemma"]`. Missing, null, empty, and nonstring lemmas are excluded. No analyzer runs and no surface-form fallback is invented. |
| `count_unit="token"` | Every qualifying lexical token occurrence. |
| `count_unit="document"` | Each document once per word, irrespective of repetition within it. |
| `statuses=["certain"]` | Include a whole token only if its reading and every typed editorial segment are certain. Omitted means all statuses. Use combinations such as `["certain", "restored"]` for a sensitivity analysis. |

Only `TokenKind.WORD` enters lexical counts. Punctuation, numerals, foreign
`UNKNOWN` tokens, and structured speaker-label tokens are excluded. Selection
does not remove the excluded evidence from the corpus. Legacy datasets that mark
a speaker label as `WORD` still count it; audit the source's classification.

`word_frequencies()` remains a list-compatible result, with the original defaults
of exact surface spelling and token frequency. Its `metadata` states the
denominator: represented word tokens for token frequency, or all documents in the
selected corpus for document frequency (including empty documents and documents
with no lemma-bearing tokens). It separately reports selected and represented
word tokens, status exclusions, missing lemmas, and recorded lemma-source labels.
Source labels are provenance, not accuracy measurements. Treat unspecified
provenance as unknown.

```python
from aegean.analysis import FilterRow

result = corpus.query(
    [FilterRow("site-is", "Athens"), FilterRow("word-prefix", "λόγ")],
    output="words", view="normalized", count_unit="token", statuses=["certain"],
)
print(result.words, result.metadata, result.cite())
```

Compound queries keep their original default of document frequency. Their
denominator covers the population matching the inscription-scope filters, before
word-scope predicates narrow the listed words. `result.metadata` records that
scope. Explicit views share the frequency-table keys and uncertainty rules.
Omitting `view` preserves legacy uppercase text predicates, literal
`ins-contains-word` and cooccurrence predicates, and separate surface keys; the
metadata records that legacy predicate normalization. Script-specific sign-label
and wildcard predicates retain their established rules.
Cooccurrence predicates use the selected lexical view across the source corpus,
before inscription filters; query metadata records this scope when applicable.

SQLite `aegean.db.search(path, text, view="normalized")` shares the explicit
lexical views and status selection. It returns the original surface text in its
hit tuples, including when matching a lemma. Missing lemmas cannot match. Explicit
views scan the token table and need no new database schema. Omitting both view and
status selection retains the existing indexed, case-insensitive search across all
token kinds. This legacy path preserves diacritics but does not equate NFC/NFD
variants. Token search is literal equality; `mode="substring"` is explicit.

CLI examples:

```console
aegean stats corpus.json --view lemma --statuses certain --details --json
aegean stats corpus.json --count-unit document --details --json
aegean query corpus.json --view normalized --output-kind words --count-unit token --json
aegean db search corpus.db λόγος --view lemma --statuses certain --json
aegean balance lineara HT13 --exact --strict --json
```

The default `stats --json` keeps its original row-list shape. `--details` or a
nondefault view/count/status selection emits an envelope containing the rows,
population metadata, and citation. Query JSON and MCP `query_corpus` always
include metadata. MCP accepts the same view, count-unit, and status choices.

## Exact arithmetic and eligibility

`balance_check(document)` retains the legacy arithmetic cutoff of an absolute
floating-point difference below `1e-6`. Every check now also exposes
`exact_difference` as a `fractions.Fraction` and `exact_balances`. Written integer
and fraction values are summed rationally, including subtotal/grand-total sections.
`balance_check(document, exact=True)` uses rational equality for `balances`.
Approximate quantities are still read at the edition's face value; rational
arithmetic does not turn an approximate reading into a certain one.

`is_checkable_account` and `checkable_accounts` retain the exploratory teaching
rule: intact text and **at least one** total within
`max(1, tolerance * abs(stated_total))`. `tolerance=0` therefore retains the legacy
absolute-one allowance. Use `exact=True` for no allowance. Typed noncertain
segments also make a document ineligible, even if its overall token status is
certain.

HT13 has stated 130½, computed 131, and rational discrepancy `1/2`. It remains
tolerance-eligible but is not exactly eligible. The shared CLI/MCP/TUI balance rows
display the discrepancy and expose both eligibility states; account eligibility
does not mean that every total balances. `--strict --exact` exits unsuccessfully
when a checked total lacks rational equality. None of these labels validates
section boundaries, disputed signs, the edition's reading, or metrology.

## Evidence still needed for scholarly validation

The constructed reference corpus in `tests/test_research_semantics.py` is hand
counted to test these contracts: canonical/case/diacritic variants, missing lemmas,
partial uncertain and restored forms, repeated tokens versus document frequency,
empty documents, and exact fractional accounting. It is not ancient-text gold and
does not measure lemma-search precision or philological correctness.

Further research validation requires independent material and specialist labor:

- Statistics: select a small published corpus claim and its editions; annotate
  the relevant lemma hits and omissions; report precision/recall and uncertainty
  sensitivity. Audit duplicate editions and author/work sampling. Existing
  document bootstrap helpers can resample supplied author/work clusters through
  their sequence interface, but no default automatically supplies author balance,
  clustered inference, or a multiple-comparison correction.
- Geography/chronology: the current gazetteer uses approximate WGS84 site points,
  and missing sites are omitted. Audit omitted sites and findspot versus origin
  before interpreting a map. Date ranges, coordinate uncertainty distributions,
  spatial sampling bias, and uncertainty-aware cluster sensitivity require
  curated source data and additional analysis; current maps do not model them.
- Aegean and undeciphered scripts: audit tablet editions for sign readings,
  fractions, subtotal boundaries, and damaged/restored quantities, including
  negative cases and competing readings. Rational arithmetic can test an entered
  interpretation reproducibly; it cannot adjudicate that interpretation. Linear B
  dossiers, Cypriot analyses, allograph assumptions, and phonetic-comparison bias
  need specialists and independent edition-linked annotations.

These are feasible study designs, not completed expert audits or new gold scores.
