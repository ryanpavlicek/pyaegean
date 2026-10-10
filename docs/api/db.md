# aegean.db

SQLite persistence for a `Corpus`: a faithful, queryable round-trip (documents + tokens +
provenance) with an optional FTS5 full-text index, plus lazy streaming. Stdlib `sqlite3`
only. See also `Corpus.to_sql` / `Corpus.from_sql`.

Close every existing SQLite connection before replacing a database opened in WAL
mode. A live connection with old, uncheckpointed WAL pages can interfere with the
replacement. See the [known workflow defects](https://github.com/ryanpavlicek/pyaegean/wiki/Limitations#known-workflow-defects).

::: aegean.db
