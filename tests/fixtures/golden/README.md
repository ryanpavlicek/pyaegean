# Golden parity fixtures

Language-neutral expected-value JSON shared with the TypeScript workbench
(`linearaworkbench`). Both implementations assert against the SAME values so
the Python port can never silently diverge from the original.

- `algorithms.json` — phonetic distance, phoneme/word alignment, collocation
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
