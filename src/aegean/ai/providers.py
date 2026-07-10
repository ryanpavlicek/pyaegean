"""Built-in provider adapters: Anthropic (default), OpenAI, xAI Grok, Google
Gemini, OpenRouter (an OpenAI-compatible gateway to many models from one key), and
`local` (a locally hosted OpenAI-compatible endpoint: Ollama, LM Studio, llama.cpp,
vLLM, LocalAI). Each SDK is an optional extra, imported lazily inside ``_complete``
and surfaced as `ProviderNotInstalled` if absent. API keys are read from the
environment and never logged; the `local` provider needs none.

Default models are configurable (model ids drift): set ``ANTHROPIC_MODEL`` /
``OPENAI_MODEL`` / ``XAI_MODEL`` / ``GEMINI_MODEL`` / ``OPENROUTER_MODEL`` to pin the
current model for each provider. The Anthropic default is a current GA model; point
``ANTHROPIC_MODEL`` at the latest flagship Claude for maximum capability. OpenRouter
model ids are ``vendor/model`` (e.g. ``anthropic/claude-3.5-sonnet``); set
``OPENROUTER_MODEL`` to choose any of its catalogue.
"""

from __future__ import annotations

import os

from .client import (
    LLMClient,
    LLMResponse,
    ProviderCallError,
    ProviderNotInstalled,
    register_provider,
)


@register_provider
class AnthropicClient(LLMClient):
    provider = "anthropic"
    env_key = "ANTHROPIC_API_KEY"
    env_model = "ANTHROPIC_MODEL"
    default_model = "claude-sonnet-4-6"  # current GA; set ANTHROPIC_MODEL for the flagship

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - exercised via tests w/o the SDK
            raise ProviderNotInstalled(
                "Anthropic SDK not installed — pip install 'pyaegean[anthropic]'"
            ) from e
        client = anthropic.Anthropic(api_key=self._require_key())
        kwargs: dict[str, object] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            msg = client.messages.create(**kwargs)  # type: ignore[call-overload]
        except anthropic.APIError as e:
            raise ProviderCallError(
                f"anthropic request failed (model {self.model!r}): {e}"
            ) from e
        except Exception as e:  # a transport / non-SDK failure must not leak raw either
            raise ProviderCallError(
                f"anthropic request failed (model {self.model!r}): {e}"
            ) from e
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return LLMResponse(text, self.provider, self.model, raw=msg)


class _OpenAICompatibleClient(LLMClient):
    """Shared implementation for OpenAI and OpenAI-API-compatible providers."""

    base_url: str | None = None

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        try:
            import openai
        except ImportError as e:  # pragma: no cover
            raise ProviderNotInstalled(
                f"OpenAI SDK not installed — pip install 'pyaegean[{self.provider}]'"
            ) from e
        client = openai.OpenAI(api_key=self._require_key(), base_url=self.base_url)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = client.chat.completions.create(
                model=self.model, max_tokens=max_tokens, messages=messages  # type: ignore[arg-type]
            )
        except openai.APIError as e:
            raise ProviderCallError(
                f"{self.provider} request failed (model {self.model!r}): {e}"
            ) from e
        except Exception as e:  # a transport / non-SDK failure must not leak raw either
            raise ProviderCallError(
                f"{self.provider} request failed (model {self.model!r}): {e}"
            ) from e
        # An OpenAI-compatible gateway (notably OpenRouter) can return HTTP 200 with an
        # empty ``choices`` list when the upstream vendor errors or a moderation filter
        # fires — no APIError is raised, so ``resp.choices[0]`` would blow up with a raw
        # IndexError that escapes the ProviderCallError wrapping the 0.19.3 pass established.
        # Surface it as a clean provider error instead (any ``error`` payload appended).
        if not resp.choices:
            detail = getattr(resp, "error", None)
            raise ProviderCallError(
                f"{self.provider} returned no choices (model {self.model!r})"
                + (f": {detail}" if detail else "")
            )
        text = resp.choices[0].message.content or ""
        return LLMResponse(text, self.provider, self.model, raw=resp)


@register_provider
class OpenAIClient(_OpenAICompatibleClient):
    provider = "openai"
    env_key = "OPENAI_API_KEY"
    env_model = "OPENAI_MODEL"
    default_model = "gpt-4o"


@register_provider
class GrokClient(_OpenAICompatibleClient):
    provider = "grok"
    env_key = "XAI_API_KEY"
    env_model = "XAI_MODEL"
    default_model = "grok-2-latest"
    base_url = "https://api.x.ai/v1"  # xAI is OpenAI-API-compatible


@register_provider
class OpenRouterClient(_OpenAICompatibleClient):
    provider = "openrouter"
    env_key = "OPENROUTER_API_KEY"
    env_model = "OPENROUTER_MODEL"
    default_model = "openai/gpt-4o-mini"  # OpenRouter ids are vendor/model; override via OPENROUTER_MODEL
    base_url = "https://openrouter.ai/api/v1"  # OpenAI-API-compatible gateway


@register_provider
class LocalClient(_OpenAICompatibleClient):
    """A locally hosted, OpenAI-API-compatible endpoint: Ollama, LM Studio, llama.cpp's
    server, vLLM, LocalAI, or any server that speaks the OpenAI ``/v1/chat/completions``
    API. Runs the model on your own machine, no API key or network required.

    Configure it with environment variables (or the usual ``model=`` / ``api_key=`` args):

    - ``PYAEGEAN_LOCAL_URL`` — the server's OpenAI-compatible base URL. Defaults to
      Ollama's ``http://localhost:11434/v1``. LM Studio is ``http://localhost:1234/v1``,
      llama.cpp's server ``http://localhost:8080/v1``.
    - ``PYAEGEAN_LOCAL_MODEL`` — the model name to request (e.g. an Ollama model you have
      pulled). Required: there is no universal default.
    - ``PYAEGEAN_LOCAL_API_KEY`` — only if your server enforces one (vLLM's ``--api-key``);
      most local servers ignore it, so a placeholder is sent when it is unset.

    Uses the ``openai`` SDK, so ``pip install 'pyaegean[openai]'`` is all it needs. A local
    model's output is exploratory like any other provider's: labeled, provenanced, grounded.
    """

    provider = "local"
    env_key = "PYAEGEAN_LOCAL_API_KEY"
    env_model = "PYAEGEAN_LOCAL_MODEL"
    default_model = ""  # no universal local default; require model= or PYAEGEAN_LOCAL_MODEL

    _DEFAULT_URL = "http://localhost:11434/v1"  # Ollama

    def __init__(self, model: str | None = None, *, api_key: str | None = None, cache=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(model, api_key=api_key, cache=cache)
        # base_url is per-instance here (it varies by server), unlike the fixed-gateway clients.
        self.base_url = os.environ.get("PYAEGEAN_LOCAL_URL", self._DEFAULT_URL)

    def _require_key(self) -> str:
        # Local servers usually accept any key; send the configured one or a harmless placeholder.
        return self._api_key or "local"

    def _cache_id(self) -> str:
        # Two local servers can host DIFFERENT models under one name (llama3.1 on Ollama vs a
        # custom build on llama.cpp), so the response cache must key on the endpoint too.
        return f"{self.provider}@{self.base_url}"

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        if not self.model:
            raise ProviderCallError(
                "no model set for the 'local' provider; set $PYAEGEAN_LOCAL_MODEL or pass "
                "model= (the name of a model your local server has, e.g. one you pulled in Ollama)"
            )
        return super()._complete(prompt=prompt, system=system, max_tokens=max_tokens)


@register_provider
class GeminiClient(LLMClient):
    provider = "gemini"
    env_key = "GEMINI_API_KEY"
    env_model = "GEMINI_MODEL"
    default_model = "gemini-1.5-pro"

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        try:
            from google import genai
            from google.genai import errors as genai_errors
            from google.genai import types
        except ImportError as e:  # pragma: no cover
            raise ProviderNotInstalled(
                "Google GenAI SDK not installed — pip install 'pyaegean[gemini]'"
            ) from e
        client = genai.Client(api_key=self._require_key())
        config = types.GenerateContentConfig(
            system_instruction=system or None, max_output_tokens=max_tokens
        )
        try:
            resp = client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
            text = resp.text or ""
        except genai_errors.APIError as e:
            raise ProviderCallError(
                f"gemini request failed (model {self.model!r}): {e}"
            ) from e
        except Exception as e:
            # A network-transport failure (httpx ConnectError/Timeout) or a blocked-
            # response access is NOT a genai APIError subclass (unlike Anthropic's and
            # OpenAI's connection errors), so it would leak raw out of the public call.
            # Wrap it like the other adapters (the 0.19.3 ProviderCallError contract).
            raise ProviderCallError(
                f"gemini request failed (model {self.model!r}): {e}"
            ) from e
        return LLMResponse(text, self.provider, self.model, raw=resp)
