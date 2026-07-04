"""Built-in provider adapters: Anthropic (default), OpenAI, xAI Grok, Google
Gemini, and OpenRouter (an OpenAI-compatible gateway to many models from one key).
Each SDK is an optional extra, imported lazily inside ``_complete`` and surfaced as
`ProviderNotInstalled` if absent. API keys are read from the environment and never
logged.

Default models are configurable (model ids drift): set ``ANTHROPIC_MODEL`` /
``OPENAI_MODEL`` / ``XAI_MODEL`` / ``GEMINI_MODEL`` / ``OPENROUTER_MODEL`` to pin the
current model for each provider. The Anthropic default is a current GA model; point
``ANTHROPIC_MODEL`` at the latest flagship Claude for maximum capability. OpenRouter
model ids are ``vendor/model`` (e.g. ``anthropic/claude-3.5-sonnet``); set
``OPENROUTER_MODEL`` to choose any of its catalogue.
"""

from __future__ import annotations

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
