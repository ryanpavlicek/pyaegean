# Large corpora — memory model and the path to streaming

A short design note on how pyaegean handles corpus size today, what's already
memory-friendly, and what is deliberately deferred until a corpus that needs it
exists. (Roadmap: WP7.)

## Today: in-memory documents

`Corpus` holds its `Document`s in a list, and each `Document` holds its `Token`s.
This is the right trade-off for everything the package currently ships and
fetches:

| Corpus | Documents | Order of magnitude |
| --- | --- | --- |
| Linear A (bundled) | ~1,720 | tens of thousands of tokens |
| DAMOS Linear B (`load("damos")`) | ~5,900 | ~hundreds of thousands of tokens |
| SigLA Linear A (`load("sigla")`) | ~780 | sign-level |
| A single Greek work (`greek.load_work`) | 1 work | the Iliad is ~127k tokens |

All of these fit comfortably in memory, and the in-memory model keeps the API
simple, random-access (`corpus.get(id)`), and analysable without a database.

## Already memory-friendly

- **Streaming iterators.** `Corpus.iter_documents()`, `iter_tokens()`, and
  `iter_words()` are generators — process a corpus token-by-token without
  building an all-tokens list. `word_frequencies()` itself streams through
  `iter_words()` into a `Counter`.
- **Lazy frequency input.** `find_morphological_clusters` accepts any iterable of
  `(word, count)` pairs, so it never needs the corpus materialised twice.
- **The fetch-to-cache data layer** streams downloads to disk (chunked sha256),
  so a 500 MB model asset never lands wholly in memory during fetch.
- **The opt-in analysis cache** (`aegean.cache`) keeps repeated heavy analyses
  off the hot path entirely.

## Deferred: streaming load (and why)

True streaming — *not* holding all `Document`s in memory at once — is **not**
implemented, on purpose. It would mean:

- a loader that **yields** `Document`s instead of returning a `Corpus` (so a
  multi-GB corpus is processed in a single pass without materialising);
- analyses that accept a document **iterator** rather than a `Corpus` (most of
  the per-document statistics already could);
- giving up O(1) random access (`get(id)`) and any analysis that needs two
  passes or the whole vocabulary at once (dispersion, keyness, clustering) unless
  it's restructured to spill to disk.

That's a real cost in API complexity, and **no corpus pyaegean targets needs it
yet** — the largest openly-licensed Greek corpus, the full First1KGreek, is read
one work at a time via `greek.load_work`, and each work fits in memory. The test
case for streaming would be loading *all* of First1KGreek (or a comparable
multi-million-token corpus) at once, which the package does not currently do.

When that need arrives, the iterator-first views above are the seam to build on:
add a `Corpus.stream(script_id)` classmethod yielding `Document`s, and an
analysis path that consumes the iterator. Until then, adding the machinery would
be speculative complexity against the project's zero-ceremony, dependency-free
principles.
