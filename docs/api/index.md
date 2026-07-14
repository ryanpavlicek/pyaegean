# API reference

The supported facade modules are listed below, with their public classes and
functions generated from the source. These facades are the stable entry points
for new code. Lower-level modules remain importable, and paths that already formed
part of a released API remain compatibility-protected, but a new lower-level path
does not become supported merely because Python can import it. The release guard
enforces both the reviewed facade list and those grandfathered paths. For guides, tutorials, and
the per-script handbooks, see the
**[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**; for what pyaegean is
and where to begin, see the [home page](../index.md).

## Where to start

- [`aegean`](aegean.md): the top-level namespace: `load()`, `read_corpus()`, `combine()`, the core value types, and the subpackages.
- [`aegean.core`](core.md): the script-agnostic model (`Corpus`, `Document`, `Token`, `TokenFormState`, `FormSegment`, `SourceMarkupRef`, `Sign`, …); build your own with `Corpus.from_records`, slice with `subset`, merge with `merge`.
- [`aegean.greek`](greek.md): the Greek NLP pipeline (normalize, tokenize, named sentence policies, scan, tag, lemmatize, parse), `segment_text()` / `segment_sentences()` with validated plugin results and exact boundary spans, `pipeline_tokens()` for typed editorial forms, isolated `GreekPipeline` instances with serializable configuration, bounded `iter_analyze_sentences()` neural sentence streams, explicit long-input policies, optional typed `TokenConfidence`/`SentenceConfidence` evidence through `confidence_domain` and `confidence_policy`, exact `AnalysisReceipt` provenance (including schema-2 calibration/policy hashes), manifest-validated neural bundles, lossless CoNLL-U document I/O, plus work discovery: `catalog()` (the full ~1,800-work index), `popular_works()`, and `nt_books()`.
- [`aegean.analysis`](analysis.md): accounting reconciliation, sign-pattern search, statistics, comparison.
- [`aegean.scripts`](scripts.md): the built-in writing-system plugins and their public facades for [Linear A](scripts-lineara.md), [Linear B](scripts-linearb.md), [Cypriot](scripts-cypriot.md), [Cypro-Minoan](scripts-cyprominoan.md), and [alphabetic Greek](scripts-greek.md).
- [`aegean.io`](io.md): import your own text or token-carrier EpiDoc; export to EpiDoc, CSV, Parquet, RDF Turtle/JSON-LD, review tables, and the intentionally lossy Linear A Research Workbench format. JSON and SQLite are the full-fidelity archives.
- [`aegean.db`](db.md): SQLite round-trip persistence for a `Corpus` (stdlib-only, queryable rows + FTS5 search).
- [`aegean.mcp_server`](mcp.md): the `aegean-mcp` Model Context Protocol server (the `[mcp]` extra).

### API contract and retirement

The facade modules listed here are the supported entry points for new code. The
reviewed list of facade modules and explicitly selected symbols is kept in
`scripts/api-manifest.json`; `scripts/api-baseline.json` retains every released
name, including older lower-level paths that are still compatibility-protected.
Importability alone does not add a new implementation module to the supported
API. `python scripts/check_api.py` checks both the current source and the
grandfathered baseline. A new facade name is added by reviewing the manifest and
then taking a release snapshot. To retire a name, deprecate it in a minor release,
keep the replacement and warning through the next minor release, and only then
refresh the baseline with `--snapshot --accept-breaking-snapshot` after the
removal has been explicitly reviewed. A normal snapshot refuses legacy removals.

## Build a corpus from your own text

`aegean.io` also reads: turn a string, a `.txt` file, a folder of texts, or a CSV into a
real `Corpus` with the full filter/query/analyse/export API. Greek text is run through the
Greek tokenizer; other scripts split on whitespace. Everything here is offline and
stdlib-only.

```python
from aegean import io

corpus = io.from_text("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος", doc_id="iliad")
print(len(corpus), "document(s),", sum(len(d.words) for d in corpus), "words")
# 1 document(s), 5 words
```

From the CLI, `aegean import` writes a corpus you can then analyse like any other:

```console
$ aegean import myplato.txt -o myplato.json   # --split whole|paragraph|line
wrote 1 document(s) to myplato.json
$ aegean stats myplato.json --top 5           # …then any corpus command works
```

## Find a work to load

`greek.catalog()` is a bundled, offline index of **every** work with a Greek (`-grc`)
edition in Perseus canonical-greekLit + First1KGreek: 1,778 works, far beyond the 25
curated `popular_works()`. Each entry's `id` loads directly with `greek.load_work`
(metadata only: the texts stay fetched-on-demand, never bundled).

```python
from aegean import greek

for w in greek.catalog(author="plato", source="perseus")[:2]:
    print(w["id"], "—", w["title"])
# tlg0059.tlg001 — Euthyphro
# tlg0059.tlg002 — Apology
```

```console
$ aegean greek catalog --author plato --source perseus -n 2
                       Greek works (36 matches)
┌────────────────┬────────┬───────────┬────────────────────┬─────────┐
│ id             │ author │ title     │ greek              │ src     │
├────────────────┼────────┼───────────┼────────────────────┼─────────┤
│ tlg0059.tlg001 │ Plato  │ Euthyphro │ Εὐθύφρων           │ perseus │
│ tlg0059.tlg002 │ Plato  │ Apology   │ Ἀπολογία Σωκράτους │ perseus │
└────────────────┴────────┴───────────┴────────────────────┴─────────┘
… and 34 more — narrow with --author/--title, or --limit 0 to list all (-o to save).
```

```bash
pip install pyaegean            # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[all]"     # all supported runtime extras, including neural (except Parquet)
```

See the [README](https://github.com/ryanpavlicek/pyaegean#install) for the full extras
matrix and [Benchmarks](../benchmarks.md) for the Greek NLP accuracy numbers and protocol.
