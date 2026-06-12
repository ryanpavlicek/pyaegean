"""A tiny response cache keyed on (provider, model, system, prompt).

Controls cost and makes repeated calls deterministic. In-memory by default;
pass a path to persist across runs. Keys are sha256 digests so prompts of any
size hash to a fixed-length key and raw text never lands in the index.
"""

from __future__ import annotations

import hashlib
import json
import pathlib


def _key(provider: str, model: str, system: str | None, prompt: str) -> str:
    h = hashlib.sha256()
    for part in (provider, model, system or "", prompt):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class ResponseCache:
    """Get/set completions by content hash, optionally persisted to JSON."""

    def __init__(self, path: str | pathlib.Path | None = None) -> None:
        self.path = pathlib.Path(path) if path else None
        self._store: dict[str, str] = {}
        if self.path and self.path.exists():
            self._store = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, provider: str, model: str, system: str | None, prompt: str) -> str | None:
        return self._store.get(_key(provider, model, system, prompt))

    def set(
        self, provider: str, model: str, system: str | None, prompt: str, text: str
    ) -> None:
        self._store[_key(provider, model, system, prompt)] = text
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._store), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._store)
