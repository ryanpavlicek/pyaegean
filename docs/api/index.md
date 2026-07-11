# API reference

Every public module, class, and function, generated from the source. For guides,
tutorials, and the per-script handbooks, see the
**[project wiki](https://github.com/ryanpavlicek/pyaegean/wiki)**; for what pyaegean is
and where to begin, see the [home page](../index.md).

## Where to start

- [`aegean`](aegean.md): the top-level namespace: `load()`, `read_corpus()`, `combine()`, the core value types, and the subpackages.
- [`aegean.core`](core.md): the script-agnostic model (`Corpus`, `Document`, `Token`, `Sign`, …); build your own with `Corpus.from_records`, slice with `subset`, merge with `merge`.
- [`aegean.greek`](greek.md): the Greek NLP pipeline (normalize, scan, tag, lemmatize, parse), plus work discovery: `catalog()` (the full ~1,800-work index), `popular_works()`, and `nt_books()`.
- [`aegean.analysis`](analysis.md): accounting reconciliation, sign-pattern search, statistics, comparison.
- [`aegean.io`](io.md): import your own text (`from_text`, `from_text_file`, `from_text_dir`, `from_csv`) and export to EpiDoc / CSV / Parquet, plus the Linear A Research Workbench round-trip.
- [`aegean.db`](db.md): SQLite round-trip persistence for a `Corpus` (stdlib-only, queryable rows + FTS5 search).
- [`aegean.mcp_server`](mcp.md): the `aegean-mcp` Model Context Protocol server (the `[mcp]` extra).

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
```

```bash
pip install pyaegean            # core + Linear A + Greek (zero heavy dependencies)
pip install "pyaegean[all]"     # the data, AI, EpiDoc, geo, viz, CLI, TUI, and MCP extras
```

See the [README](https://github.com/ryanpavlicek/pyaegean#install) for the full extras
matrix and [Benchmarks](../benchmarks.md) for the Greek NLP accuracy numbers and protocol.
