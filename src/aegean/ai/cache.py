"""A tiny response cache keyed on (provider, model, system, prompt, max_tokens).

Controls cost and makes repeated calls deterministic. In-memory by default;
pass a path to persist across runs. Keys are sha256 digests so prompts of any
size hash to a fixed-length key and raw text never lands in the index.

``max_tokens`` is part of the key because it shapes the response: the same
prompt completed under a smaller token limit is a different (possibly truncated)
answer, and serving it for a longer request would silently cut the reply short.
It is the only response-shaping parameter `LLMClient.complete` takes, so the key
covers everything that determines the response text.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import threading
import uuid
from typing import Any, Literal

from .._locking import FileLock

# Mirrors the ``max_tokens`` default of `LLMClient.complete`, so a caller that
# doesn't thread the limit through still keys consistently with default calls.
_DEFAULT_MAX_TOKENS = 1024
_SQLITE_SUFFIXES = frozenset({".sqlite", ".sqlite3", ".db"})


def _key(
    provider: str, model: str, system: str | None, prompt: str, max_tokens: int
) -> str:
    h = hashlib.sha256()
    for part in (provider, model, system or "", prompt, str(max_tokens)):
        # Length-prefix every field so the serialization is injective. A bare separator
        # byte collides when the text itself contains that byte: a NUL ending the system
        # prompt is indistinguishable from one beginning the prompt, so two logically
        # distinct requests would hash alike and one would be served the other's cached
        # completion. Source text and grounding content can carry control chars, so this
        # is reachable; it is the same fix Corpus.fingerprint uses (core/corpus.py).
        b = part.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def _resolve_backend(
    path: pathlib.Path | None, backend: Literal["auto", "json", "sqlite"]
) -> Literal["memory", "json", "sqlite"]:
    if backend not in ("auto", "json", "sqlite"):
        raise ValueError("backend must be 'auto', 'json', or 'sqlite'")
    if path is None:
        return "memory"
    if backend == "auto":
        return "sqlite" if path.suffix.lower() in _SQLITE_SUFFIXES else "json"
    return backend


class ResponseCache:
    """Get/set completions by content hash, optionally persisted to JSON or SQLite.

    Passing a ``.sqlite`` / ``.sqlite3`` / ``.db`` path (or ``backend="sqlite"``) uses
    a keyed transactional SQLite backend (O(1) per-key reads/writes, WAL concurrency,
    lazy ``sqlite3`` import). Passing a ``.json`` path keeps the atomic JSON file format
    for full backward compatibility.
    """

    def __init__(
        self,
        path: str | pathlib.Path | None = None,
        *,
        backend: Literal["auto", "json", "sqlite"] = "auto",
    ) -> None:
        # expanduser so a "~/..." path lands under the user's home, not a literal "./~".
        self.path = pathlib.Path(path).expanduser() if path else None
        self.backend: Literal["memory", "json", "sqlite"] = _resolve_backend(self.path, backend)
        self._write_lock = threading.Lock()  # serialize in-process persists
        self._sqlite_conn: Any = None
        self._sqlite3: Any = None
        if self.backend == "sqlite":
            self._init_sqlite()
            self._store: dict[str, str] = {}
        else:
            self._store = self._load()
        # Only keys changed by THIS instance are merged over the latest disk state.
        # Writing the whole snapshot would let a stale second instance roll back keys
        # another process updated after both instances were constructed.
        self._dirty: dict[str, str] = {}

    def _init_sqlite(self) -> None:
        """Open a keyed transactional SQLite store, degrading to memory-only on corruption."""
        assert self.path is not None
        import sqlite3

        self._sqlite3 = sqlite3
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if os.name == "posix":
                try:
                    fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o600)
                    os.close(fd)
                    os.chmod(self.path, 0o600)
                except OSError:
                    pass
            conn = sqlite3.connect(str(self.path), timeout=30.0, check_same_thread=False)
            conn.execute("PRAGMA busy_timeout = 30000")
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.execute(
                "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            conn.commit()
            self._sqlite_conn = conn
        except (OSError, sqlite3.Error):
            self._sqlite_conn = None

    def close(self) -> None:
        """Close the underlying SQLite connection, if open."""
        with self._write_lock:
            conn = self._sqlite_conn
            self._sqlite_conn = None
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _load(self) -> dict[str, str]:
        """Read the persisted JSON store, treating any unreadable/malformed file as empty.

        A cache file can be truncated or corrupt (a process killed mid-write, a full
        disk, a stale concurrent writer). Such a file must degrade to a cold cache, not
        an exception: a cache is an optimization, and the model recomputes on a miss. So
        a missing file, an OS read error, or non-JSON / non-object content all yield an
        empty store rather than propagating, and only a well-formed JSON object of string
        values is trusted (a malformed entry cannot masquerade as a cached completion).
        """
        if not self.path or not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}

    def get(
        self,
        provider: str,
        model: str,
        system: str | None,
        prompt: str,
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> str | None:
        key = _key(provider, model, system, prompt, max_tokens)
        if self.backend == "sqlite":
            with self._write_lock:
                if key in self._store:
                    return self._store[key]
                conn = self._sqlite_conn
                if conn is None:
                    return None
                try:
                    row = conn.execute(
                        "SELECT value FROM responses WHERE key = ?", (key,)
                    ).fetchone()
                except Exception:
                    return None
                if row is not None and isinstance(row[0], str):
                    self._store[key] = row[0]
                    return row[0]
                return None
        if self.path is not None:
            # os.replace makes this lock-free read see either complete generation.
            # Refreshing here also lets two live clients share newly cached responses,
            # instead of both paying for a completion because their startup snapshots differ.
            with self._write_lock:
                self._store.update(self._load())
                self._store.update(self._dirty)  # an unpersisted paid response wins locally
                return self._store.get(key)
        return self._store.get(key)

    def set(
        self,
        provider: str,
        model: str,
        system: str | None,
        prompt: str,
        text: str,
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        key = _key(provider, model, system, prompt, max_tokens)
        if self.path is None:
            self._store[key] = text
            return
        if self.backend == "sqlite":
            with self._write_lock:
                self._store[key] = text
                conn = self._sqlite_conn
                if conn is None:
                    return
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO responses (key, value) VALUES (?, ?)",
                        (key, text),
                    )
                    conn.commit()
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            return
        with self._write_lock:
            self._store[key] = text
            self._dirty[key] = text
            # A failed persist must not lose the response the caller just paid a
            # provider call for: the entry is already in the in-memory store, and a
            # cache is an optimization (the same philosophy _load applies to a corrupt
            # file), so a disk error here degrades to memory-only instead of raising.
            try:
                self._write_atomic()
            except OSError:
                pass

    def _write_atomic(self) -> None:
        """Persist the store so a reader never sees a half-written file.

        The store is serialized to a sibling temp file in the same directory (so
        ``os.replace`` is an atomic same-filesystem rename), then swapped into place. A
        process killed during the write leaves either the old complete file or the
        untouched target, never a truncated one, so a concurrent or later ``_load`` always
        reads a whole JSON document. The temp name is unique per write (not shared by the
        process's threads — a shared name let concurrent writers collide on Windows and
        interleave on POSIX), and in-process writers are serialized behind a lock. A
        cross-process lock reloads and merges only this instance's dirty keys over the
        latest complete file before replacement, so independent clients cannot erase one
        another's entries. The temp file is cleaned up if the write itself fails.
        """
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        with FileLock(
            lock_path,
            stale_after=300.0,
            poll_every=0.05,
            heartbeat_every=5.0,
        ):
            updates = dict(self._dirty)
            merged = self._load()
            merged.update(updates)
            data = json.dumps(merged)
            tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
            try:
                tmp.write_text(data, encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            self._store = merged
            for key, value in updates.items():
                if self._dirty.get(key) == value:
                    del self._dirty[key]

    def __len__(self) -> int:
        if self.backend == "sqlite":
            with self._write_lock:
                conn = self._sqlite_conn
                if conn is not None:
                    try:
                        return int(conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0])
                    except Exception:
                        pass
                return len(self._store)
        return len(self._store)
