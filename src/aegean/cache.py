"""An **opt-in, off-by-default** persistent cache for expensive analyses.

Some analyses are pure but slow — morphological clustering over the whole
vocabulary, dispersion/keyness across a large corpus, big queries. When you opt
in, their results are memoised to a local sqlite file keyed on a content
fingerprint of the inputs, so re-running the same analysis on the same corpus is
instant across runs. Disabled, `@memoize` is a transparent passthrough — zero
overhead and identical behaviour, so the cache never changes a result, only how
fast it arrives.

No new dependency: sqlite3 and json are stdlib, and the cache lives under the
same user cache dir as the fetched data (``PYAEGEAN_CACHE`` to relocate).

    import aegean
    aegean.cache.enable()                 # opt in (or set PYAEGEAN_ANALYSIS_CACHE=1)
    aegean.analysis.dispersions(corpus)   # computed once, then served from disk
    aegean.cache.stats()                  # {'enabled': True, 'entries': 1, 'path': …}
    aegean.cache.clear()                  # wipe it

**Security note.** Values are encoded with a versioned, typed JSON codec limited
to plain containers and an explicit static allowlist of frozen analysis-result
dataclasses — never ``pickle``. Legacy pre-v2 pickle entries and corrupt rows
are treated as cold cache misses without deserialization. As defense in depth,
the cache file is created ``0600`` (owner-only), and enabling a cache whose
directory is writable by other users emits a warning.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import math
import os
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
_CACHE_FORMAT = "2"
_PAYLOAD_MAGIC = b"AEGEAN-CACHE-V2\n"
_ENV = "PYAEGEAN_ANALYSIS_CACHE"

_MISS = object()  # sentinel distinct from a cached ``None``
F = TypeVar("F", bound=Callable[..., Any])

_warned_dirs: set[str] = set()

# Static allowlist of frozen result dataclasses permitted in the typed disk cache.
# Resolved lazily so importing `aegean.cache` never pulls `aegean.analysis`.
_ALLOWED_DATACLASS_TAGS = frozenset({
    "aegean.analysis.morphology.ClusterMember",
    "aegean.analysis.morphology.MorphCluster",
    "aegean.analysis.stats.Dispersion",
    "aegean.analysis.stats.KeynessRow",
})


def _resolve_allowed_dataclass(tag: str) -> type[Any] | None:
    if tag not in _ALLOWED_DATACLASS_TAGS:
        return None
    if tag == "aegean.analysis.morphology.ClusterMember":
        from .analysis.morphology import ClusterMember

        return ClusterMember
    if tag == "aegean.analysis.morphology.MorphCluster":
        from .analysis.morphology import MorphCluster

        return MorphCluster
    if tag == "aegean.analysis.stats.Dispersion":
        from .analysis.stats import Dispersion

        return Dispersion
    if tag == "aegean.analysis.stats.KeynessRow":
        from .analysis.stats import KeynessRow

        return KeynessRow
    return None


def _encode_typed(obj: Any) -> Any:
    """Convert ``obj`` to a typed JSON-serializable structure or raise ``TypeError``."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        if math.isfinite(obj):
            return obj
        if math.isnan(obj):
            return {"__aegean_t__": "float", "v": "nan"}
        return {"__aegean_t__": "float", "v": "inf" if obj > 0 else "-inf"}
    if isinstance(obj, list):
        return [_encode_typed(x) for x in obj]
    if isinstance(obj, tuple):
        return {"__aegean_t__": "tuple", "v": [_encode_typed(x) for x in obj]}
    if isinstance(obj, set):
        return {"__aegean_t__": "set", "v": [_encode_typed(x) for x in obj]}
    if isinstance(obj, frozenset):
        return {"__aegean_t__": "frozenset", "v": [_encode_typed(x) for x in obj]}
    if isinstance(obj, dict):
        if all(isinstance(k, str) for k in obj) and "__aegean_t__" not in obj:
            return {k: _encode_typed(v) for k, v in obj.items()}
        return {
            "__aegean_t__": "dict",
            "v": [[_encode_typed(k), _encode_typed(v)] for k, v in obj.items()],
        }
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        tag = f"{type(obj).__module__}.{type(obj).__qualname__}"
        if tag in _ALLOWED_DATACLASS_TAGS:
            return {
                "__aegean_t__": "dc",
                "tag": tag,
                "v": {
                    f.name: _encode_typed(getattr(obj, f.name))
                    for f in dataclasses.fields(obj)
                },
            }
    raise TypeError(f"unsupported cache value type: {type(obj).__name__}")


def _decode_typed(raw: Any) -> Any:
    """Reconstruct a value produced by `_encode_typed`, raising ``ValueError`` on unknown tags."""
    if raw is None or isinstance(raw, (bool, int, float, str)):
        return raw
    if isinstance(raw, list):
        return [_decode_typed(x) for x in raw]
    if isinstance(raw, dict):
        kind = raw.get("__aegean_t__")
        if kind is None:
            return {k: _decode_typed(v) for k, v in raw.items()}
        if kind == "float":
            val = raw.get("v")
            if val == "nan":
                return float("nan")
            if val == "inf":
                return float("inf")
            if val == "-inf":
                return float("-inf")
            raise ValueError("invalid float tag")
        if kind == "tuple":
            items = raw.get("v")
            if not isinstance(items, list):
                raise ValueError("invalid tuple tag")
            return tuple(_decode_typed(x) for x in items)
        if kind == "set":
            items = raw.get("v")
            if not isinstance(items, list):
                raise ValueError("invalid set tag")
            return {_decode_typed(x) for x in items}
        if kind == "frozenset":
            items = raw.get("v")
            if not isinstance(items, list):
                raise ValueError("invalid frozenset tag")
            return frozenset(_decode_typed(x) for x in items)
        if kind == "dict":
            pairs = raw.get("v")
            if not isinstance(pairs, list):
                raise ValueError("invalid dict tag")
            return {_decode_typed(k): _decode_typed(v) for k, v in pairs}
        if kind == "dc":
            tag = raw.get("tag")
            fields = raw.get("v")
            if not isinstance(tag, str) or not isinstance(fields, dict):
                raise ValueError("invalid dataclass tag")
            cls = _resolve_allowed_dataclass(tag)
            if cls is None:
                raise ValueError(f"disallowed dataclass tag {tag!r}")
            expected = {f.name for f in dataclasses.fields(cls)}
            if set(fields) != expected:
                raise ValueError(f"field mismatch for {tag!r}")
            return cls(**{name: _decode_typed(val) for name, val in fields.items()})
        raise ValueError(f"unknown cache type tag {kind!r}")
    raise ValueError("invalid JSON node")


def _dumps_value(value: Any) -> bytes:
    encoded = json.dumps(
        _encode_typed(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _PAYLOAD_MAGIC + encoded


def _loads_value(blob: Any) -> Any:
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        return _MISS
    raw = bytes(blob)
    if not raw.startswith(_PAYLOAD_MAGIC):
        # Legacy pickle blob or corrupt bytes: treat as cold miss without deserializing.
        return _MISS
    try:
        parsed = json.loads(raw[len(_PAYLOAD_MAGIC) :].decode("utf-8"))
        return _decode_typed(parsed)
    except Exception:
        return _MISS


def _warn_if_dir_writable_by_others(directory: Path) -> None:
    """Warn once if the cache directory is group/other-writable (POSIX only).

    A shared/world-writable cache directory allows other users to tamper with cached
    analysis outputs. We warn rather than refuse, since a same-user shared setup can be
    legitimate, but the risk should be visible. POSIX only: on Windows the mode bits are
    synthetic (access is governed by ACLs), so the check would spuriously fire on ordinary
    directories."""
    import stat

    if os.name != "posix":
        return
    key = str(directory)
    if key in _warned_dirs:
        return
    try:
        mode = os.stat(directory).st_mode
    except OSError:
        return
    if mode & (stat.S_IWGRP | stat.S_IWOTH):
        import warnings

        _warned_dirs.add(key)
        warnings.warn(
            f"analysis cache directory {key!r} is writable by other users; another user could "
            "tamper with cached analysis results. Point PYAEGEAN_ANALYSIS_CACHE at a directory "
            "only you can write.",
            stacklevel=3,
        )


def _ensure_private_file(path: Path) -> None:
    """Create ``path`` with 0o600 permissions on POSIX before opening it."""
    if os.name != "posix":
        return
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
    except OSError:
        pass
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class DiskCache:
    """A sqlite-backed key→value store using a versioned, typed JSON codec (no pickle).

    Unsupported value types are silently not cached, and legacy pickle rows or unreadable
    rows are treated as cold misses.

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
        _warn_if_dir_writable_by_others(self.path.parent)
        _ensure_private_file(self.path)
        self._lock = threading.Lock()
        self._sqlite3 = sqlite3  # kept so the ops can catch a concurrent-close error
        self._conn = sqlite3.connect(
            str(self.path), timeout=30.0, check_same_thread=False
        )
        with self._lock:
            self._conn.execute("PRAGMA busy_timeout = 30000")
            # WAL lets independent processes read while another appends.  It is a
            # performance hint only: a filesystem that cannot enable it must not
            # make the optional cache change a program's result.
            try:
                self._conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
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
        except (self._sqlite3.ProgrammingError, self._sqlite3.OperationalError):
            # The connection was closed under us (enable()/disable() from another
            # thread while this worker held the cache): a miss, not a crash. A cache
            # is an optimization, so the caller recomputes — the never-changes-a-
            # result contract holds.
            return _MISS
        if row is None:
            return _MISS
        return _loads_value(row[0])

    def set(self, key: str, value: Any) -> None:
        try:
            blob = _dumps_value(value)
        except Exception:  # unsupported value type → just don't cache it
            return
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)", (key, blob)
                )
                self._conn.commit()
        except (self._sqlite3.ProgrammingError, self._sqlite3.OperationalError):
            # Closed concurrently, or another process held SQLite's writer lock
            # for longer than the busy timeout: skip persisting.  This cache is an
            # optimization and may never turn a successful analysis into an error.
            self._rollback_quietly()
            return

    def clear(self) -> None:
        try:
            with self._lock:
                self._conn.execute("DELETE FROM cache")
                self._conn.commit()
        except (self._sqlite3.ProgrammingError, self._sqlite3.OperationalError):
            self._rollback_quietly()
            return

    def _rollback_quietly(self) -> None:
        """End a failed write transaction without surfacing cache maintenance."""
        try:
            with self._lock:
                self._conn.rollback()
        except (self._sqlite3.ProgrammingError, self._sqlite3.OperationalError):
            pass

    def __len__(self) -> int:
        try:
            with self._lock:
                return int(self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0])
        except (self._sqlite3.ProgrammingError, self._sqlite3.OperationalError):
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
        try:
            keyed = _keyify(ck())
        except Exception:
            return _MISS
        return _MISS if keyed is _MISS else ["K", keyed]
    if isinstance(obj, (list, tuple)):
        out = []
        for x in obj:
            k = _keyify(x)
            if k is _MISS:
                return _MISS
            out.append(k)
        return ["L" if isinstance(obj, list) else "T", out]
    if isinstance(obj, dict):
        items = []
        for key, value in obj.items():
            kk = _keyify(key)
            k = _keyify(value)
            if kk is _MISS or k is _MISS:
                return _MISS
            items.append([kk, k])
        # Sort canonical JSON encodings, not the original keys: unlike Python's
        # ordering this works for heterogeneous key types and preserves their
        # identity (1 and "1" remain different).
        items.sort(key=lambda item: json.dumps(item[0], sort_keys=True, ensure_ascii=False))
        return ["D", items]
    return _MISS


def _make_key(
    fn: Callable[..., Any], version: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str | None:
    parts = _keyify([list(args), kwargs])
    if parts is _MISS:
        return None
    try:
        payload = json.dumps(
            [_CACHE_FORMAT, version, f"{fn.__module__}.{fn.__qualname__}", parts],
            sort_keys=True,
            ensure_ascii=False,
        )
    except (TypeError, ValueError):
        return None
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
