# aegean.db

SQLite persistence for a `Corpus`: a faithful, queryable round-trip (documents + tokens +
provenance) with an optional FTS5 full-text index, plus lazy streaming. Stdlib `sqlite3`
only. See also `Corpus.to_sql` / `Corpus.from_sql`.

Replacing an existing database uses SQLite's online backup transaction.
Existing WAL readers retain their snapshot until their transaction ends;
subsequent reads see the replacement. A competing writer can cause a bounded
timeout, leaving the previous database intact. External file renames/unlinks
while connections are open remain outside this contract.

Creating a new database uses an atomic, no-clobber hard link on the destination
filesystem, falling back to an exclusive `O_CREAT|O_EXCL` placeholder and SQLite
online backup on filesystems without hard-link support (such as FAT, exFAT, or
some network mounts). Non-SQLite destinations and orphaned journal sidecars are
refused.

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

## Durable resumable annotation jobs

For large corpora stored in SQLite, `annotate_sqlite_job()` annotates one
document at a time and checkpoints progress inside the same SQLite transaction,
so an interrupted run can resume without starting over:

```python
from aegean import db

status = db.annotate_sqlite_job(
    "corpus.db",
    "annotated.db",
    job_dir="./job-state",
    with_dependencies=True,
)
print(status.state, status.completed_documents, status.total_documents)
```

Each job freezes a WAL-safe snapshot of the source database, reads documents
forward in bounded keyset order, holds an exclusive file lock while active, and
publishes the finished output database atomically only when every document
completes. On resume (`resume=True`), the job verifies that the source snapshot,
options, and backend identity still match so partial runs cannot mix incompatible
analyses. Inspect progress at any time with `db.job_status("./job-state")` or
the CLI commands `aegean db annotate` and `aegean db job-status`.

::: aegean.db
