# aegean.db

SQLite persistence for a `Corpus`: a faithful, queryable round-trip (documents + tokens +
provenance) with an optional FTS5 full-text index, plus lazy streaming. Stdlib `sqlite3`
only. See also `Corpus.to_sql` / `Corpus.from_sql`.

::: aegean.db
