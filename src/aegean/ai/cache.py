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

# Mirrors the ``max_tokens`` default of `LLMClient.complete`, so a caller that
# doesn't thread the limit through still keys consistently with default calls.
_DEFAULT_MAX_TOKENS = 1024


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


class ResponseCache:
    """Get/set completions by content hash, optionally persisted to JSON."""

    def __init__(self, path: str | pathlib.Path | None = None) -> None:
        # expanduser so a "~/..." path lands under the user's home, not a literal "./~".
        self.path = pathlib.Path(path).expanduser() if path else None
        self._write_lock = threading.Lock()  # serialize in-process persists
        self._store: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        """Read the persisted store, treating any unreadable/malformed file as empty.

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
        return self._store.get(_key(provider, model, system, prompt, max_tokens))

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
        self._store[_key(provider, model, system, prompt, max_tokens)] = text
        if self.path is not None:
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
        interleave on POSIX), and in-process writers are serialized behind a lock. The
        temp file is cleaned up if the write itself fails.
        """
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock:
            data = json.dumps(self._store)
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

    def __len__(self) -> int:
        return len(self._store)
