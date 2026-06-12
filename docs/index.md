# pyaegean API reference

`pyaegean` is a specialist Python toolkit for Ancient Greek and the Aegean syllabic
scripts — alphabetic Greek and Linear A, Linear B, the Cypriot syllabary, and
Cypro-Minoan. This site is the **API reference**, generated from the source. For guides,
tutorials, and the per-script handbooks, see the
**[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**.

## Where to start

- [`aegean`](api/aegean.md) — the top-level namespace: `load()`, the core value types, and the subpackages.
- [`aegean.core`](api/core.md) — the script-agnostic model (`Corpus`, `Document`, `Token`, `Sign`, …).
- [`aegean.greek`](api/greek.md) — the Greek NLP pipeline (normalize, scan, tag, lemmatize, parse).
- [`aegean.analysis`](api/analysis.md) — accounting reconciliation, sign-pattern search, statistics, comparison.
- [`aegean.io`](api/io.md) — EpiDoc / CSV / Parquet export, plus the Linear A Research Workbench round-trip.

```bash
pip install pyaegean            # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[all]"     # the data, AI, EpiDoc, geo, viz, and CLI extras
```

See the [README](https://github.com/ryanpavlicek/pyaegean#install) for the full extras
matrix and [Benchmarks](benchmarks.md) for the Greek NLP accuracy numbers and protocol.
