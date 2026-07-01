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
import pathlib

# Mirrors the ``max_tokens`` default of `LLMClient.complete`, so a caller that
# doesn't thread the limit through still keys consistently with default calls.
_DEFAULT_MAX_TOKENS = 1024


def _key(
    provider: str, model: str, system: str | None, prompt: str, max_tokens: int
) -> str:
    h = hashlib.sha256()
    for part in (provider, model, system or "", prompt, str(max_tokens)):
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
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._store), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._store)
