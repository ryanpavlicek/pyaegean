# API reference

The supported facade modules are listed below, with their public classes and
functions generated from the source. These facades are the intended entry points
for new code. Lower-level modules may remain importable, but a lower-level path
does not become supported merely because Python can import it. The release guard
validates the reviewed current facade. For guides, tutorials, and
the per-script handbooks, see the
**[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**; for what pyaegean is
and where to begin, see the [home page](../index.md).

## Where to start

- [`aegean`](aegean.md): the top-level namespace: `load()`, `read_corpus()`, `combine()`, the core value types, and the subpackages.
- [`aegean.core`](core.md): the script-agnostic model (`Corpus`, `Document`, `Token`, `TokenFormState`, `FormSegment`, `SourceMarkupRef`, `Sign`, …); build your own with `Corpus.from_records`, slice with `subset`, merge with `merge`.
- [`aegean.greek`](greek.md): the Greek NLP pipeline (normalize, tokenize, named sentence policies, scan, tag, lemmatize, parse), `segment_text()` / `segment_sentences()` with validated plugin results and exact boundary spans, `pipeline_tokens()` for typed editorial forms, isolated `GreekPipeline` instances with serializable configuration, bounded `iter_analyze_sentences()` neural sentence streams, explicit long-input policies, optional typed `TokenConfidence`/`SentenceConfidence` evidence through `confidence_domain` and `confidence_policy`, immutable annotation/domain registries through `list_annotation_profiles()` / `list_domain_profiles()`, exact `AnalysisReceipt` provenance (including schema-3 composed output, post-processing, and optional calibration/policy hashes), manifest-validated neural bundles, lossless CoNLL-U document I/O, plus work discovery: `catalog()` (the full ~1,800-work index), `popular_works()`, and `nt_books()`.
- [`aegean.analysis`](analysis.md): accounting reconciliation, sign-pattern search, statistics, comparison.
- [`aegean.scripts`](scripts.md): the built-in writing-system plugins and their public facades for [Linear A](scripts-lineara.md), [Linear B](scripts-linearb.md), [Cypriot](scripts-cypriot.md), [Cypro-Minoan](scripts-cyprominoan.md), and [alphabetic Greek](scripts-greek.md).
- [`aegean.io`](io.md): import your own text or token-carrier EpiDoc; export to EpiDoc, CSV, Parquet, RDF Turtle/JSON-LD, review tables, and the intentionally lossy Linear A Research Workbench format. It also exposes complete CoNLL-U envelopes, loss-aware spaCy/Stanza/CLTK adapters, and portable SHA-256-bound interoperability bundles. JSON and SQLite remain the full-fidelity corpus archives.

### `aegean.io` interoperability facade

The reviewed public entry points are the typed core envelope (`InteropDocument`,
`InteropTokenMetadata`, `InteropSentenceMetadata`, `InteropResult`, and
`InteropReport`), CoNLL-U conversion (`from_conllu`, `to_conllu`,
`from_token_records`, `from_ud_document`), optional framework adapters
(`to_spacy`/`from_spacy`, `to_stanza`/`from_stanza`, `to_cltk`/`from_cltk`), and
portable `InteropBundle` helpers (`bundle_from_document`, `dumps_interop_bundle`,
`loads_interop_bundle`, `read_interop_bundle`, `write_interop_bundle`), and the
explicit CLTK seam (`make_cltk_process`). `bundle_from_result`, sidecar codecs,
schema constants, and typed interoperability errors support advanced integrations
and are listed in the generated [`aegean.io` reference](io.md). The adapter dependencies
are lazy and remain outside the core import path.
- [`aegean.db`](db.md): SQLite round-trip persistence for a `Corpus` (stdlib-only, queryable rows + FTS5 search).
- [`aegean.mcp_server`](mcp.md): the `aegean-mcp` Model Context Protocol server (the `[mcp]` extra).

### API policy

The facade modules listed here are the supported entry points for new code. The
reviewed list of facade modules and explicitly selected symbols is kept in
`scripts/api-manifest.json`. Importability alone does not add a new implementation
module to the supported API. `python scripts/check_api.py` statically verifies
that the reviewed modules and symbols resolve. During pre-1.0 development through
the v4 Greek NLP segment, the facade may change directly when the design improves;
the CHANGELOG, manifest, docs, and tests must describe the resulting current API.

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
pip install "pyaegean[all]"     # bundled runtime extras, including neural (not Parquet/framework adapters)
```

See the [README](https://github.com/ryanpavlicek/pyaegean#install) for the full extras
matrix and [Benchmarks](../benchmarks.md) for the Greek NLP accuracy numbers and protocol.
