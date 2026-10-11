# aegean.db

SQLite persistence for a `Corpus`: a faithful, queryable round-trip (documents + tokens +
provenance) with an optional FTS5 full-text index, plus lazy streaming. Stdlib `sqlite3`
only. See also `Corpus.to_sql` / `Corpus.from_sql`.

Since 0.61.0, replacing an existing database uses SQLite's online
backup transaction. Existing WAL readers retain their snapshot until their
transaction ends; subsequent reads see the replacement. A competing writer can
cause a bounded timeout, leaving the previous database intact. External file
renames/unlinks while connections are open remain outside this contract.

Creating a new database uses an atomic, no-clobber hard link on the destination
filesystem. Filesystems without hard-link support fail explicitly. Non-SQLite
destinations and orphaned journal sidecars are refused. Users of 0.60.0 should close all connections before replacing a WAL database.

::: aegean.db
