# Golden parity fixtures

Language-neutral expected-value JSON shared with the TypeScript workbench
(`linearaworkbench`). Both implementations assert against the SAME values so
the Python port can never silently diverge from the original.

Status: v0.1 ports (numerals, sign-patterns) are tested inline in
`tests/test_numerals.py` / `tests/test_patterns.py` against the hand-computed
values from the workbench's `*.test.ts`. When the distance/alignment/morphology
ports land, extract their golden values here as JSON and assert both repos
against them. See docs/PLAN.md §"Parity, benchmarking & correctness".
