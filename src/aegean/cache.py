"""An **opt-in, off-by-default** persistent cache for expensive analyses.

Some analyses are pure but slow — morphological clustering over the whole
vocabulary, dispersion/keyness across a large corpus, big queries. When you opt
in, their results are memoised to a local sqlite file keyed on a content
fingerprint of the inputs, so re-running the same analysis on the same corpus is
instant across runs. Disabled, `@memoize` is a transparent passthrough — zero
overhead and identical behaviour, so the cache never changes a result, only how
fast it arrives.

No new dependency: sqlite3 and pickle are stdlib, and the cache lives under the
same user cache dir as the fetched data (``PYAEGEAN_CACHE`` to relocate).

    import aegean
    aegean.cache.enable()                 # opt in (or set PYAEGEAN_ANALYSIS_CACHE=1)
    aegean.analysis.dispersions(corpus)   # computed once, then served from disk
    aegean.cache.stats()                  # {'enabled': True, 'entries': 1, 'path': …}
    aegean.cache.clear()                  # wipe it

**Security note.** Values are stored with ``pickle`` in *your own* cache
directory (same trust boundary as pip/mypy/pytest caches); a stale or corrupt
entry is treated as a miss and recomputed, and the cache key embeds a format +
per-function version so a code change never deserialises against a changed class.
Only enable it for caches you control.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import pickle
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

__all__ = [
    "enable",
    "disable",
    "is_enabled",
    "clear",
    "stats",
    "memoize",
    "DiskCache",
]

# Bump if the key construction or value encoding changes (invalidates every entry).
_CACHE_FORMAT = "1"
_ENV = "PYAEGEAN_ANALYSIS_CACHE"

_MISS = object()  # sentinel distinct from a cached ``None``
F = TypeVar("F", bound=Callable[..., Any])


class DiskCache:
    """A sqlite-backed key→value store. Values are pickled; unpicklable values
    are silently not cached, and unreadable rows are treated as misses.

    Thread-safe: memoized analyses are routinely called from worker threads (a
    ThreadPoolExecutor mapping over corpora, the TUI's workers), so the single
    connection is opened with ``check_same_thread=False`` and every use of it is
    serialized behind a lock — otherwise enabling the cache would turn working
    multithreaded code into a crash, which the never-changes-a-result contract
    forbids."""

    def __init__(self, path: str | Path) -> None:
        # Lazy import: the cache is opt-in, so only require sqlite3 once it's actually
        # used. This keeps `import aegean` working where sqlite3 is unvendored from the
        # stdlib (e.g. Pyodide / the in-browser demo) or a Python built without it.
        import sqlite3
        import threading

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sqlite3 = sqlite3  # kept so the ops can catch a concurrent-close error
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB)"
            )
            self._conn.commit()

    def get(self, key: str) -> Any:
        try:
            with self._lock:
                row = self._conn.execute(
                    "SELECT value FROM cache WHERE key = ?", (key,)
                ).fetchone()
        except self._sqlite3.ProgrammingError:
            # The connection was closed under us (enable()/disable() from another
            # thread while this worker held the cache): a miss, not a crash. A cache
            # is an optimization, so the caller recomputes — the never-changes-a-
            # result contract holds.
            return _MISS
        if row is None:
            return _MISS
        try:
            return pickle.loads(row[0])  # noqa: S301 — user's own cache dir; miss on failure
        except Exception:  # corrupt or class-changed → recompute
            return _MISS

    def set(self, key: str, value: Any) -> None:
        try:
            blob = pickle.dumps(value)
        except Exception:  # unpicklable result → just don't cache it
            return
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)", (key, blob)
                )
                self._conn.commit()
        except self._sqlite3.ProgrammingError:  # closed concurrently: skip persisting
            return

    def clear(self) -> None:
        try:
            with self._lock:
                self._conn.execute("DELETE FROM cache")
                self._conn.commit()
        except self._sqlite3.ProgrammingError:  # closed concurrently: nothing to clear
            return

    def __len__(self) -> int:
        try:
            with self._lock:
                return int(self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0])
        except self._sqlite3.ProgrammingError:  # closed concurrently
            return 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ── module-global opt-in state ───────────────────────────────────────────────
_active: DiskCache | None = None
_env_checked = False


def _default_path() -> Path:
    from .data import cache_dir

    return cache_dir() / "analysis-cache.sqlite"


def enable(path: str | Path | None = None) -> DiskCache:
    """Turn the cache on (idempotent), at ``path`` or the default cache file."""
    global _active
    if _active is not None and path is None:
        return _active
    if _active is not None:
        _active.close()
    _active = DiskCache(path or _default_path())
    return _active


def disable() -> None:
    """Turn the cache off; subsequent memoised calls compute directly."""
    global _active
    if _active is not None:
        _active.close()
    _active = None


def _current() -> DiskCache | None:
    """The active cache, consulting ``PYAEGEAN_ANALYSIS_CACHE`` once (lazily, so
    importing aegean stays side-effect-free). The env value may be ``1`` (default
    path) or a path."""
    global _env_checked
    if _active is None and not _env_checked:
        _env_checked = True
        val = os.environ.get(_ENV)
        if val and val != "0":
            enable(None if val == "1" else val)
    return _active


def is_enabled() -> bool:
    """Whether the analysis cache is currently active."""
    return _current() is not None


def clear() -> None:
    """Remove every cached entry (no-op if the cache is disabled)."""
    c = _current()
    if c is not None:
        c.clear()


def stats() -> dict[str, Any]:
    """``{'enabled', 'path', 'entries'}`` for the active cache."""
    c = _current()
    if c is None:
        return {"enabled": False, "path": None, "entries": 0}
    return {"enabled": True, "path": str(c.path), "entries": len(c)}


# ── keying ───────────────────────────────────────────────────────────────────
def _keyify(obj: Any) -> Any:
    """A JSON-stable representation of an argument, or ``_MISS`` if it can't be
    keyed (then the call isn't cached). Objects with a ``cache_key()`` method —
    e.g. `Corpus` — key by that content fingerprint."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    ck = getattr(obj, "cache_key", None)
    if callable(ck):
        return ["K", ck()]
    if isinstance(obj, (list, tuple)):
        out = []
        for x in obj:
            k = _keyify(x)
            if k is _MISS:
                return _MISS
            out.append(k)
        return ["L", out]
    if isinstance(obj, dict):
        items = []
        for key in sorted(obj):
            k = _keyify(obj[key])
            if k is _MISS:
                return _MISS
            items.append([key, k])
        return ["D", items]
    return _MISS


def _make_key(
    fn: Callable[..., Any], version: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str | None:
    parts = _keyify([list(args), kwargs])
    if parts is _MISS:
        return None
    payload = json.dumps(
        [_CACHE_FORMAT, version, f"{fn.__module__}.{fn.__qualname__}", parts],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def memoize(*, version: str = "1") -> Callable[[F], F]:
    """Decorator: persist a pure function's result when the cache is enabled.

    A transparent passthrough while disabled. When enabled, the result is keyed
    on the function identity, ``version``, and a content fingerprint of the
    arguments; arguments that can't be fingerprinted (no ``cache_key()`` and not
    a JSON scalar/list/dict) make the call compute directly rather than error.
    Bump ``version`` when the function's logic changes."""

    def deco(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = _current()
            if cache is None:
                return fn(*args, **kwargs)
            key = _make_key(fn, version, args, kwargs)
            if key is None:
                return fn(*args, **kwargs)
            hit = cache.get(key)
            if hit is not _MISS:
                return hit
            result = fn(*args, **kwargs)
            cache.set(key, result)
            return result

        return wrapper  # type: ignore[return-value]

    return deco
