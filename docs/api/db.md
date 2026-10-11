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

## Index lexical searches

Build an optional lexical index on a writable local database to accelerate exact
surface, normalized, and lemma searches:

```python
from aegean import db

db.build_lexical_index("corpus.db")
print(db.lexical_index_status("corpus.db"))
hits = db.search("corpus.db", "λόγος", view="lemma", statuses=["certain"])
```

Index keys use the same normalization and reading-status rules as corpus queries.
Missing lemmas remain excluded, and hits preserve their original text and order.
Building again refreshes the index transactionally. Token edits, including direct
SQL edits, invalidate the index; searches use the scan path until it is rebuilt.
Search and index-status inspection open the database read-only. Substring searches
retain their scan behavior. Existing databases need no index to remain usable.

The CLI equivalents are `aegean db index corpus.db` and
`aegean db index corpus.db --status --json`. Index creation takes a local path,
not a hosted corpus identifier; make a writable working copy of a fetched corpus
before indexing it.

::: aegean.db
