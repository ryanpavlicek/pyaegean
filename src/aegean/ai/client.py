"""Provider-agnostic LLM client contract + result/labeling types.

The AI layer is **multi-provider** (Anthropic default, plus OpenAI, xAI Grok,
Google Gemini, OpenRouter, and `local` for a locally hosted OpenAI-compatible endpoint) and
**optional**: provider SDKs are extras, imported lazily inside
each adapter, so ``import aegean`` never requires them. Every generative output
is wrapped in an `ExploratoryResult` carrying provenance (provider, model,
prompt version) and an ``exploratory`` flag — generative readings of this
material are hypotheses, never ground truth.

Model selection is **configurable and current** by design (model ids drift):
each provider resolves its model from an explicit ``model=`` argument, then a
``<PROVIDER>_MODEL`` environment variable, then a default constant. Point
``ANTHROPIC_MODEL`` at the latest flagship Claude for maximum capability.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AIError(RuntimeError):
    """Base class for AI-layer errors."""


class ProviderNotInstalled(AIError):
    """Raised when a provider's optional SDK isn't installed."""


class MissingAPIKey(AIError):
    """Raised when no API key is available for a provider."""


class UnknownProvider(AIError):
    """Raised for an unregistered provider id."""


class ProviderCallError(AIError):
    """Raised when a provider's API call fails (bad model id, authentication, rate
    limit, network). Wraps the SDK's exception so callers see one `AIError` type
    instead of a provider-specific traceback; the underlying error is the ``__cause__``."""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """A raw completion from a provider."""

    text: str
    provider: str
    model: str
    raw: Any = None  # provider-native object; never serialized into exports


@dataclass(frozen=True, slots=True)
class ExploratoryResult:
    """A generative result, explicitly labeled exploratory and provenanced.

    ``grounding`` is the structured corpus/lexicon/analysis evidence fed to the
    model (each a `GroundingItem` with a source and a ref). Use `labeled` when
    surfacing to a user so the caveat travels with the text, `trace` to audit
    which local facts grounded the output, and `data` (when set by a structured
    capability) for the parsed JSON payload.
    """

    text: str
    kind: str            # "translate" | "gloss" | "decipher" | "nlp_assist" | "ask" | "summarize" | "extract"
    provider: str
    model: str
    prompt_version: str
    grounding: tuple[GroundingItem, ...] = ()
    exploratory: bool = True
    data: Any = None     # parsed structured output, when a capability requested JSON

    def labeled(self) -> str:
        """The text prefixed with an unmistakable exploratory provenance tag."""
        tag = f"[EXPLORATORY · {self.kind} · {self.provider}/{self.model}]"
        return f"{tag}\n{self.text}"

    def trace(self) -> str:
        """A human-readable provenance trace: the generative step and the local,
        non-generative evidence that grounded it, grouped by source.

        Makes the exploratory result auditable — every grounding line names the
        source (corpus, lexicon, analysis step) and the ref it came from, so a
        reader can check the output against the facts it was given rather than
        taking it on trust."""
        from collections import defaultdict

        lines = [
            f"EXPLORATORY {self.kind} via {self.provider}/{self.model} "
            f"(prompt {self.prompt_version})",
        ]
        if not self.grounding:
            lines.append("  grounding: none (ungrounded generation — weigh accordingly)")
            return "\n".join(lines)
        by_source: dict[str, list[GroundingItem]] = defaultdict(list)
        for item in self.grounding:
            by_source[item.source].append(item)
        lines.append(f"  grounded in {len(self.grounding)} item(s) from {len(by_source)} source(s):")
        for source in sorted(by_source):
            items = by_source[source]
            lines.append(f"  • {source} ({len(items)}):")
            lines.extend(f"      - {item.content}" for item in items)
        return "\n".join(lines)

    def provenance(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "kind": self.kind,
            "exploratory": self.exploratory,
            "grounding": [
                {"content": g.content, "source": g.source, "ref": g.ref} for g in self.grounding
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """A stable, JSON-ready serialization. Keeps the ``exploratory`` flag, the text, the
        grounding, and any structured ``data`` — so a saved AI result can never be mistaken
        for ground truth when read back."""
        return {
            "_meta": {"tool": "pyaegean", "type": "ExploratoryResult", "schemaVersion": 1},
            "kind": self.kind,
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "exploratory": self.exploratory,
            "grounding": [
                {"content": g.content, "source": g.source, "ref": g.ref} for g in self.grounding
            ],
            "data": self.data,
        }

    def to_json(self, path: str | Path | None = None, *, indent: int | None = 2) -> str | None:
        """Serialize to JSON: returns the string, or writes it to ``path`` and returns ``None``."""
        import json

        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
        if path is None:
            return text
        from .._atomic import atomic_path

        with atomic_path(path) as tmp:
            tmp.write_text(text, encoding="utf-8")
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExploratoryResult":
        """Reconstruct an `ExploratoryResult` from `to_dict` output."""
        return cls(
            text=data["text"],
            kind=data.get("kind", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            prompt_version=data.get("prompt_version", ""),
            grounding=tuple(
                GroundingItem(
                    content=g["content"], source=g.get("source", "custom"), ref=g.get("ref", "")
                )
                for g in data.get("grounding", ())
            ),
            exploratory=data.get("exploratory", True),
            data=data.get("data"),
        )

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab — the exploratory tag is unmissable."""
        from ..core._html import badge, card, esc

        tag = badge(f"EXPLORATORY · {self.kind}", color="#b00")
        body = (
            f"<div style='margin:4px 0'>{tag} "
            f"<span style='color:#888;font-size:0.85em'>{esc(self.provider)}/{esc(self.model)}"
            "</span></div>"
            f"<div style='white-space:pre-wrap'>{esc(self.text)}</div>"
        )
        if self.grounding:
            items = "".join(
                f"<li>{esc(g.content)} "
                f"<span style='color:#aaa'>[{esc(g.source)}]</span></li>"
                for g in self.grounding
            )
            body += (
                "<div style='color:#666;font-size:0.85em;margin-top:6px'>grounding:"
                f"<ul style='margin:2px 0'>{items}</ul></div>"
            )
        return card("AI result", body)


class LLMClient(ABC):
    """Abstract provider client. Subclasses implement `_complete`."""

    provider: str = ""
    env_key: str = ""        # API-key environment variable
    env_model: str = ""      # model-override environment variable
    default_model: str = ""  # fallback when neither arg nor env is set

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.model = model or os.environ.get(self.env_model) or self.default_model
        self._api_key = api_key or os.environ.get(self.env_key)
        self.cache = cache

    def _require_key(self) -> str:
        if not self._api_key:
            raise MissingAPIKey(
                f"no API key for {self.provider!r}; set ${self.env_key} or pass api_key="
            )
        return self._api_key

    @abstractmethod
    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        """Provider-specific single-turn completion."""

    def _cache_id(self) -> str:
        """The provider identity the response cache keys on. A provider whose responses
        depend on per-instance routing state (the ``local`` provider's endpoint URL: two
        servers can host different models under one name) must fold that state in here,
        or one endpoint's cached completion would be served for the other's."""
        return self.provider

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """A cached single-turn completion (cache is keyed on provider identity/model/
        system/prompt/max_tokens so re-asking is free and deterministic)."""
        if self.cache is not None:
            hit = self.cache.get(self._cache_id(), self.model, system, prompt, max_tokens=max_tokens)
            if hit is not None:
                return LLMResponse(hit, self.provider, self.model)
        resp = self._complete(prompt=prompt, system=system, max_tokens=max_tokens)
        if self.cache is not None:
            self.cache.set(self._cache_id(), self.model, system, prompt, resp.text, max_tokens=max_tokens)
        return resp


# Provider registry — adapters register themselves on import.
_PROVIDERS: dict[str, type[LLMClient]] = {}


def register_provider(cls: type[LLMClient]) -> type[LLMClient]:
    """Register an ``LLMClient`` subclass under its ``provider`` name (each adapter calls this)."""
    _PROVIDERS[cls.provider] = cls
    return cls


def get_client(
    provider: str = "anthropic",
    *,
    model: str | None = None,
    api_key: str | None = None,
    cache: ResponseCache | None = None,
) -> LLMClient:
    """Construct a client for ``provider`` (default Anthropic). Importing
    `aegean.ai` registers all built-in providers."""
    try:
        cls = _PROVIDERS[provider]
    except KeyError:
        raise UnknownProvider(
            f"unknown provider {provider!r}; available: {sorted(_PROVIDERS)}"
        ) from None
    return cls(model, api_key=api_key, cache=cache)


def providers() -> list[str]:
    """Sorted names of registered providers, e.g. ``['anthropic', 'gemini', 'grok', 'local', 'openai', 'openrouter']``."""
    return sorted(_PROVIDERS)


# Imported here to avoid a circular import at module top (cache imports nothing
# from this module, but keep the public type available for annotations above).
from .cache import ResponseCache  # noqa: E402
from .grounding import GroundingItem  # noqa: E402
