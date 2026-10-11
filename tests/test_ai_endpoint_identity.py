"""SDK request routing and cache separation, without remote calls or credentials."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from aegean import ai


@pytest.fixture
def routed_sdks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def served(kind: str, route: str) -> str:
        calls.append((kind, route))
        return f"{kind}: {route}"

    openai = ModuleType("openai")
    openai.APIError = type("APIError", (Exception,), {})

    class OpenAI:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            def create(**kwargs: object) -> SimpleNamespace:
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=served("openai", base_url)))])
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    openai.OpenAI = OpenAI
    anthropic = ModuleType("anthropic")
    anthropic.APIError = type("APIError", (Exception,), {})

    class Anthropic:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            def create(**kwargs: object) -> SimpleNamespace:
                return SimpleNamespace(content=[SimpleNamespace(type="text", text=served("anthropic", base_url))])
            self.messages = SimpleNamespace(create=create)

    anthropic.Anthropic = Anthropic
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    genai_types = ModuleType("google.genai.types")
    genai_errors = ModuleType("google.genai.errors")
    genai_errors.APIError = type("APIError", (Exception,), {})
    genai_types.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
    genai_types.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)

    class Gemini:
        def __init__(self, *, api_key: str, http_options: SimpleNamespace, vertexai: bool) -> None:
            assert vertexai is False
            def generate_content(**kwargs: object) -> SimpleNamespace:
                return SimpleNamespace(text=served("gemini", http_options.base_url))
            self.models = SimpleNamespace(generate_content=generate_content)

    genai.Client = Gemini
    genai.types = genai_types
    genai.errors = genai_errors
    google.genai = genai
    for name, module in {
        "openai": openai, "anthropic": anthropic, "google": google,
        "google.genai": genai, "google.genai.types": genai_types,
        "google.genai.errors": genai_errors,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    return calls


@pytest.mark.parametrize("provider,variable", [
    ("openai", "OPENAI_BASE_URL"), ("local", "PYAEGEAN_LOCAL_URL"),
    ("anthropic", "ANTHROPIC_BASE_URL"), ("gemini", "GOOGLE_GEMINI_BASE_URL"),
])
def test_endpoint_change_never_reuses_other_route_response(
    provider: str, variable: str, monkeypatch: pytest.MonkeyPatch, tmp_path, routed_sdks,
) -> None:
    cache_path = tmp_path / "responses.json"
    monkeypatch.setenv(variable, "https://first.example/v1")
    first = ai.get_client(provider, model="same-model", api_key="test", cache=ai.ResponseCache(cache_path))
    first_reply = first.complete("same prompt").text
    monkeypatch.setenv(variable, "https://second.example/v1")
    second = ai.get_client(provider, model="same-model", api_key="test", cache=ai.ResponseCache(cache_path))
    second_reply = second.complete("same prompt").text
    assert "first.example" in first_reply and "second.example" in second_reply
    assert first_reply != second_reply and len(routed_sdks) == 2
    assert first._cache_id() != second._cache_id()
    # The original client keeps the route it keyed on, even for a cache miss.
    assert "first.example" in first.complete("new prompt").text
    assert len(routed_sdks) == 3
    monkeypatch.setenv(variable, "https://first.example/v1")
    repeated = ai.get_client(provider, model="same-model", api_key="test", cache=ai.ResponseCache(cache_path))
    assert repeated.complete("same prompt").text == first_reply
    assert len(routed_sdks) == 3


def test_supported_provider_routes_do_not_cross_contaminate(monkeypatch, routed_sdks) -> None:
    # Same endpoint and model can be selected through different provider contracts.
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("PYAEGEAN_LOCAL_URL", "http://localhost:1234/v1")
    cache = ai.ResponseCache()
    clients = [ai.get_client(provider, model="same-model", api_key="test", cache=cache)
               for provider in ("openai", "local", "grok", "openrouter")]
    for client in clients:
        client.complete("same prompt")
    assert len({client._cache_id() for client in clients}) == len(clients)
    assert len(routed_sdks) == 4
    assert clients[2].base_url == "https://api.x.ai/v1"
    assert clients[3].base_url == "https://openrouter.ai/api/v1"
    for client in clients:
        client.complete("same prompt")
    assert len(routed_sdks) == 4


def test_ambiguous_legacy_provider_only_cache_is_not_used(monkeypatch, routed_sdks) -> None:
    cache = ai.ResponseCache()
    cache.set("openai", "same-model", None, "same prompt", "old unknown endpoint")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://new.example/v1")
    result = ai.get_client("openai", model="same-model", api_key="test", cache=cache).complete("same prompt")
    assert "new.example" in result.text and len(routed_sdks) == 1


def test_endpoint_identity_does_not_expose_url_credentials(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://user:password@example.test/v1?token=secret")
    identity = ai.get_client("openai", api_key="test")._cache_id()
    assert identity.startswith("openai@")
    assert "password" not in identity and "secret" not in identity
