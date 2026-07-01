# Golden parity fixtures

Language-neutral expected-value JSON shared with the TypeScript workbench
(`linearaworkbench`). Both implementations assert against the SAME values so
neither can silently diverge from the other. When a value is found to be wrong,
the correction lands here (pyaegean) first and the workbench mirrors it, code
and fixture together, in its next release (e.g. the `RA₂-RO` phonetic
expectation: subscripted signs are distinct signs, so the old shared value
`raro` was corrected to `ra₂ro`).

- `algorithms.json`: phonetic distance, phoneme/word alignment, collocation
  statistics, sequence distance, and morphological clustering. Extracted from
  the workbench `src/lib/algorithms.test.ts` and `compareAlign.test.ts`.
  Numeric tolerances mirror the TS `toBeCloseTo(value, digits)`
  (`tol = 0.5 * 10**-digits`). Asserted by `tests/test_algorithms.py`;
  invariants in `tests/test_algorithms_properties.py` mirror the workbench
  `*.properties.test.ts`.

The numerals and sign-pattern ports are tested inline in
`tests/test_numerals.py` / `tests/test_patterns.py` against the hand-computed
values from the workbench's `*.test.ts`. The query-engine and
structure-detection ports are likewise tested inline, in
`tests/test_query.py` (mirroring `queryEngine.test.ts`) and
`tests/test_structure.py` (asserting the documented precedence over the real
corpus).

Two deliberate, documented differences from the TypeScript query engine
(edge cases, not golden-fixture material): equal-count words in the
words-output sort alphabetically here, where the TS engine stable-sorts by
insertion order; and an empty string for a numeric field raises
`ValueError` here, where TS `Number("")` is `0` and matches everything.
