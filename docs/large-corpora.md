# Large corpora — memory model and the path to streaming

A short design note on how pyaegean handles corpus size today, what's already
memory-friendly, and what is deferred until a corpus that needs it exists.

## Today: in-memory documents

`Corpus` holds its `Document`s in a list, and each `Document` holds its `Token`s.
This is the right trade-off for everything the package currently ships and
fetches:

| Corpus | Documents | Order of magnitude |
| --- | --- | --- |
| Linear A (bundled) | 1,721 | tens of thousands of tokens |
| DAMOS Linear B (`load("damos")`) | ~5,900 | ~hundreds of thousands of tokens |
| SigLA Linear A (`load("sigla")`) | ~780 | sign-level |
| A single Greek work (`greek.load_work`) | 1 work | the Iliad is ~127k tokens |

All of these fit comfortably in memory, and the in-memory model keeps the API
simple, random-access (`corpus.get(id)`), and analysable without a database.

## Building a bigger corpus

Two paths assemble a larger working corpus from these in-memory pieces, both offline once
the source texts are in hand:

- **Discover, then load.** `greek.catalog()` is a bundled, offline index of all 1,778 works
  with a Greek (`-grc`) edition in Perseus canonical-greekLit + First1KGreek — search it by
  author/title/source, then pass any `id` to `greek.load_work`. The index is metadata only;
  the texts stay fetched-on-demand (CC BY-SA), never bundled.
- **Combine into one.** `aegean.combine` (and `Corpus.merge`) concatenates several corpora —
  loaded works, imported texts, or saved `.json`/`.db` files — into a single `Corpus`, with
  explicit duplicate-id handling (`dedupe="error"|"first"|"last"|"suffix"`) and a merged
  provenance that names every source. From the CLI:

  ```console
  $ aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db   # all of Homer in one db
  ```

  The result is still held in memory when loaded; combining many large works hits the same
  ceiling discussed below, which is the case streaming would eventually address.

### Import your own text

Material that isn't in the bundled scripts or the Greek loaders comes in through
`aegean.io`'s import side: `from_text` / `from_text_file` / `from_text_dir` / `from_csv`
(CLI: `aegean import`) turn a string, a `.txt` file, a folder of texts, or a CSV into a
`Corpus` with the full analyse/query/export API. Greek text is tokenized with the Greek
tokenizer, other scripts by whitespace; `--split whole|paragraph|line` chooses how a text
becomes documents. A folder of per-work text files plus `aegean combine` is the simplest
way to stand up a custom multi-work corpus — each file still loads one work at a time, so
the per-document memory profile is unchanged.

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
