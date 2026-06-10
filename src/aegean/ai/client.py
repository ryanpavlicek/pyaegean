"""Provider-agnostic LLM client contract + result/labeling types.

The AI layer is **multi-provider** (Anthropic default, plus OpenAI, xAI Grok,
Google Gemini) and **optional**: provider SDKs are extras, imported lazily inside
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
from typing import Any


class AIError(RuntimeError):
    """Base class for AI-layer errors."""


class ProviderNotInstalled(AIError):
    """Raised when a provider's optional SDK isn't installed."""


class MissingAPIKey(AIError):
    """Raised when no API key is available for a provider."""


class UnknownProvider(AIError):
    """Raised for an unregistered provider id."""


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

    ``grounding`` lists the corpus/lexicon evidence fed to the model. Use
    `labeled` when surfacing to a user so the caveat travels with the text.
    """

    text: str
    kind: str            # "translate" | "gloss" | "decipher" | "nlp_assist" | "ask" | "summarize"
    provider: str
    model: str
    prompt_version: str
    grounding: tuple[str, ...] = ()
    exploratory: bool = True

    def labeled(self) -> str:
        """The text prefixed with an unmistakable exploratory provenance tag."""
        tag = f"[EXPLORATORY · {self.kind} · {self.provider}/{self.model}]"
        return f"{tag}\n{self.text}"

    def provenance(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "kind": self.kind,
            "exploratory": self.exploratory,
            "grounding": list(self.grounding),
        }

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
            items = "".join(f"<li>{esc(g)}</li>" for g in self.grounding)
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

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """A cached single-turn completion (cache is keyed on provider/model/
        system/prompt so re-asking is free and deterministic)."""
        if self.cache is not None:
            hit = self.cache.get(self.provider, self.model, system, prompt)
            if hit is not None:
                return LLMResponse(hit, self.provider, self.model)
        resp = self._complete(prompt=prompt, system=system, max_tokens=max_tokens)
        if self.cache is not None:
            self.cache.set(self.provider, self.model, system, prompt, resp.text)
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
    """The sorted names of registered providers, e.g. ``['anthropic', 'gemini', 'grok', 'openai']``."""
    return sorted(_PROVIDERS)


# Imported here to avoid a circular import at module top (cache imports nothing
# from this module, but keep the public type available for annotations above).
from .cache import ResponseCache  # noqa: E402
