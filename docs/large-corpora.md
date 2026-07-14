# Large corpora — memory model and streaming boundaries

A short design note on how pyaegean handles corpus size today, what's already
memory-friendly, which neural sentence path streams, and which whole-document
operations still collect their results.

## Today: in-memory documents

`Corpus` holds its `Document`s in a list, and each `Document` holds its `Token`s.
This is the right trade-off for everything the package currently ships and
fetches:

| Corpus | Documents | Order of magnitude |
| --- | --- | --- |
| Linear A (bundled) | 1,721 | tens of thousands of tokens |
| DAMOS Linear B (`load("damos")`) | ~5,900 | ~hundreds of thousands of tokens |
| SigLA Linear A (`load("sigla")`) | 802 | sign-level |
| A single Greek work (`greek.load_work`) | 1 work | the Iliad is ~127k tokens |
| Greek inscriptions (`isicily`, `iip`, `iospe`, `igcyr`, `edh`) | ~1,000-2,900 each | tens of thousands of tokens each |
| DDbDP papyri (`load("ddbdp")`) | 57,331 | ~4.4M tokens; SQLite-hosted, streamed via `aegean.db.stream` |

All but DDbDP fit comfortably in memory (DDbDP is the case the streaming section
below handles), and the in-memory model keeps the API simple, random-access
(`corpus.get(id)`), and analysable without a database.

## Building a bigger corpus

Two paths assemble a larger working corpus from these in-memory pieces, both offline once
the source texts are in hand:

- **Discover, then load.** `greek.catalog()` is a bundled, offline index of all 1,778 works
  with a Greek (`-grc`) edition in Perseus canonical-greekLit + First1KGreek: search it by
  author/title/source, then pass any `id` to `greek.load_work`. The index is metadata only;
  the texts stay fetched-on-demand (CC BY-SA), never bundled.
- **Combine into one.** `aegean.combine` (and `Corpus.merge`) concatenates several corpora
  (loaded works, imported texts, or saved `.json`/`.db` files) into a single `Corpus`, with
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
way to stand up a custom multi-work corpus: each file still loads one work at a time, so
the per-document memory profile is unchanged.

## Already memory-friendly

- **Iterator views.** `Corpus.iter_documents()` iterates the already materialized
  document list; `iter_tokens()` and `iter_words()` are true generators, so they
  process that corpus token-by-token without building a second all-tokens list.
  `word_frequencies()` itself streams through `iter_words()` into a `Counter`.
- **Lazy frequency input.** `find_morphological_clusters` accepts any iterable of
  `(word, count)` pairs, so it never needs the corpus materialised twice.
- **The fetch-to-cache data layer** streams downloads to disk (chunked sha256),
  so a 500 MB model asset never lands wholly in memory during fetch.
- **The opt-in analysis cache** (`aegean.cache`) keeps repeated heavy analyses
  off the hot path entirely.

## Streaming analysis: the precise boundary

Two independent streaming seams now ship:

- `aegean.db.stream(path)` yields a SQLite corpus's `Document`s one at a time
  without building a `Corpus`. It retains the ordered document-ID list, but not
  every document and token; this is the recommended storage path for DDbDP.
- `aegean.greek.iter_analyze_sentences(sentences)` consumes an iterable of
  pre-tokenized Greek sentences and yields one `SentenceAnalysis` at a time. Its
  default is canonical sequential inference. `batch_size=N` holds at most one
  N-sentence chunk before yielding it in source order:

  ```python
  from aegean import greek

  greek.use_neural_pipeline()

  def sentence_source():
      yield ["μῆνιν", "ἄειδε", "θεὰ"]
      yield ["ἄνδρα", "μοι", "ἔννεπε", "Μοῦσα"]

  for analysis in greek.iter_analyze_sentences(sentence_source(), batch_size=2):
      print(analysis.lemma, analysis.receipt.sha256 if analysis.receipt else None)
  ```

The iterator is synchronous backpressure: creating it pulls nothing, pausing the
consumer pulls nothing further, and closing it closes a source generator. It
captures one backend/configuration, documentary state, and (when requested)
confidence calibration at construction, copies each sentence before
analysis, preserves order and per-sentence receipts, and never retries. A backend
failure yields nothing from that chunk; already yielded chunks remain valid. A
source failure while a batch is being filled likewise leaves that partial chunk
unyielded. Memory is bounded with respect to the number of corpus sentences by
the batch and the largest individual sentence; it is not a fixed byte ceiling for
an arbitrarily large single sentence. Batched/GPU execution remains a throughput
option; published measurements use canonical sequential CPU inference.

`greek.analyze_sentences(...)` remains the compatibility collector: it uses the
same bounded input engine but returns the complete result list. Use the `iter_`
form for incremental output. An isolated `GreekPipeline` has the matching
`iter_analyze_sentences(...)` method.

From the shell, `aegean greek stream INPUT` reads those tokenized sentences as
JSONL (one JSON string array per line; `-` means stdin) and emits one flushed
`SentenceAnalysis` JSON object per line. It activates the neural backend itself;
`--batch-size`, long-input, and confidence controls mirror the Python iterator.

What is **not** implied by this sentence boundary is a fully streaming raw-text or
`Corpus` pipeline. `greek.pipeline(text)`, `GreekPipeline.analyze(text)`,
`greek.annotate_corpus(...)`, CoNLL-U parsing/serialization/evaluation, and analyses
that require the whole vocabulary still collect. A general document-iterator
pipeline would mean:

- analyses that accept a document **iterator** rather than a `Corpus` (most of
  the per-document statistics already could);
- giving up O(1) random access (`get(id)`) and any analysis that needs two
  passes or the whole vocabulary at once (dispersion, keyness, clustering) unless
  it's restructured to spill to disk.

That's a real cost in API complexity. DDbDP (`aegean.load("ddbdp")`, 57,331
documentary papyri, ~4.4M tokens) is answered at the storage layer: the corpus is
hosted as a SQLite database, `aegean.db.stream(ddbdp_db())` yields its documents
one at a time, and `aegean.db.search()` (CLI:
`aegean db search ddbdp "..."`) gives instant full-text search without loading
anything. `aegean.load("ddbdp")` still returns the whole in-memory `Corpus` for
those with the RAM.

`aegean.db.stream()` plus the sentence iterator are the seams for a future
document-stream analyzer; they do not claim that bridge already exists.
