"""Integration tests for the real provider adapters' code paths.

Each provider SDK is faked by installing a stand-in module into ``sys.modules``,
so the adapters' actual ``_complete`` methods run in CI — building the request
and parsing the response — without the SDKs installed or any API key being live.
This closes the gap left by the fake-LLMClient unit tests (which bypass
``_complete`` entirely).
"""

from __future__ import annotations

import sys
import types

import pytest

from aegean import ai


def _install(monkeypatch, name: str, module: types.ModuleType) -> None:
    monkeypatch.setitem(sys.modules, name, module)


# ── Anthropic ────────────────────────────────────────────────────────────────
def _fake_anthropic() -> tuple[types.ModuleType, dict]:
    mod = types.ModuleType("anthropic")
    rec: dict = {}

    class _Block:
        def __init__(self, type_: str, text: str) -> None:
            self.type = type_
            self.text = text

    class _Msg:
        # one text block + one non-text block (must be filtered out)
        content = [_Block("text", "the answer"), _Block("thinking", "ignored")]

    class _Messages:
        def create(self, **kwargs):
            rec["kwargs"] = kwargs
            return _Msg()

    class Anthropic:
        def __init__(self, api_key=None):
            rec["api_key"] = api_key
            self.messages = _Messages()

    mod.Anthropic = Anthropic  # type: ignore[attr-defined]
    return mod, rec


def test_anthropic_adapter_request_and_response(monkeypatch):
    mod, rec = _fake_anthropic()
    _install(monkeypatch, "anthropic", mod)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    client = ai.get_client("anthropic", model="claude-test")
    resp = client.complete("hello", system="be terse", max_tokens=123)

    assert resp.text == "the answer"            # only the text block, joined
    assert resp.provider == "anthropic" and resp.model == "claude-test"
    assert resp.raw is not None
    assert rec["api_key"] == "sk-test"
    assert rec["kwargs"]["model"] == "claude-test"
    assert rec["kwargs"]["max_tokens"] == 123
    assert rec["kwargs"]["messages"] == [{"role": "user", "content": "hello"}]
    assert rec["kwargs"]["system"] == "be terse"


def test_anthropic_omits_system_when_absent(monkeypatch):
    mod, rec = _fake_anthropic()
    _install(monkeypatch, "anthropic", mod)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    ai.get_client("anthropic", model="m").complete("hi")
    assert "system" not in rec["kwargs"]  # only added when truthy


# ── OpenAI / Grok (OpenAI-compatible) ────────────────────────────────────────
def _fake_openai() -> tuple[types.ModuleType, dict]:
    mod = types.ModuleType("openai")
    rec: dict = {}

    class _MsgOut:
        content = "oai answer"

    class _Choice:
        message = _MsgOut()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            rec["kwargs"] = kwargs
            return _Resp()

    class _Chat:
        def __init__(self) -> None:
            self.completions = _Completions()

    class OpenAI:
        def __init__(self, api_key=None, base_url=None):
            rec["api_key"] = api_key
            rec["base_url"] = base_url
            self.chat = _Chat()

    mod.OpenAI = OpenAI  # type: ignore[attr-defined]
    return mod, rec


def test_openai_adapter(monkeypatch):
    mod, rec = _fake_openai()
    _install(monkeypatch, "openai", mod)
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")

    resp = ai.get_client("openai", model="gpt-x").complete("q", system="sys", max_tokens=50)
    assert resp.text == "oai answer" and resp.provider == "openai"
    assert rec["base_url"] is None  # plain OpenAI
    assert rec["kwargs"]["model"] == "gpt-x"
    assert rec["kwargs"]["max_tokens"] == 50
    assert rec["kwargs"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q"},
    ]


def test_grok_uses_xai_base_url(monkeypatch):
    mod, rec = _fake_openai()
    _install(monkeypatch, "openai", mod)
    monkeypatch.setenv("XAI_API_KEY", "xai-key")

    resp = ai.get_client("grok").complete("q")
    assert resp.provider == "grok"
    assert rec["api_key"] == "xai-key"
    assert rec["base_url"] == "https://api.x.ai/v1"
    # no system → only the user message
    assert rec["kwargs"]["messages"] == [{"role": "user", "content": "q"}]


# ── local (Ollama / LM Studio / llama.cpp / vLLM, OpenAI-compatible) ──────────
def test_local_defaults_to_ollama_and_placeholder_key(monkeypatch):
    mod, rec = _fake_openai()
    _install(monkeypatch, "openai", mod)
    for var in ("PYAEGEAN_LOCAL_URL", "PYAEGEAN_LOCAL_API_KEY", "PYAEGEAN_LOCAL_MODEL"):
        monkeypatch.delenv(var, raising=False)

    resp = ai.get_client("local", model="llama3.1").complete("q")
    assert resp.provider == "local" and resp.text == "oai answer"
    assert rec["base_url"] == "http://localhost:11434/v1"  # Ollama default
    assert rec["api_key"] == "local"                       # placeholder when none is set
    assert rec["kwargs"]["model"] == "llama3.1"


def test_local_honors_url_and_key_env(monkeypatch):
    mod, rec = _fake_openai()
    _install(monkeypatch, "openai", mod)
    monkeypatch.setenv("PYAEGEAN_LOCAL_URL", "http://localhost:1234/v1")  # LM Studio
    monkeypatch.setenv("PYAEGEAN_LOCAL_API_KEY", "vllm-secret")
    monkeypatch.setenv("PYAEGEAN_LOCAL_MODEL", "mistral")

    ai.get_client("local").complete("q")
    assert rec["base_url"] == "http://localhost:1234/v1"
    assert rec["api_key"] == "vllm-secret"
    assert rec["kwargs"]["model"] == "mistral"


def test_local_requires_a_model(monkeypatch):
    mod, _rec = _fake_openai()
    _install(monkeypatch, "openai", mod)
    for var in ("PYAEGEAN_LOCAL_MODEL", "PYAEGEAN_LOCAL_API_KEY", "PYAEGEAN_LOCAL_URL"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ai.ProviderCallError, match="no model set for the 'local' provider"):
        ai.get_client("local").complete("q")


# ── Gemini ───────────────────────────────────────────────────────────────────
def _fake_google() -> tuple[dict[str, types.ModuleType], dict]:
    rec: dict = {}
    google = types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    types_mod = types.ModuleType("google.genai.types")

    class GenerateContentConfig:
        def __init__(self, system_instruction=None, max_output_tokens=None):
            rec["system_instruction"] = system_instruction
            rec["max_output_tokens"] = max_output_tokens

    class _Resp:
        text = "gemini answer"

    class _Models:
        def generate_content(self, model=None, contents=None, config=None):
            rec["model"] = model
            rec["contents"] = contents
            return _Resp()

    class Client:
        def __init__(self, api_key=None):
            rec["api_key"] = api_key
            self.models = _Models()

    errors_mod = types.ModuleType("google.genai.errors")

    class APIError(Exception):
        pass

    errors_mod.APIError = APIError  # type: ignore[attr-defined]
    types_mod.GenerateContentConfig = GenerateContentConfig  # type: ignore[attr-defined]
    genai.Client = Client  # type: ignore[attr-defined]
    genai.types = types_mod  # type: ignore[attr-defined]
    genai.errors = errors_mod  # type: ignore[attr-defined]
    google.genai = genai  # type: ignore[attr-defined]
    return {
        "google": google,
        "google.genai": genai,
        "google.genai.types": types_mod,
        "google.genai.errors": errors_mod,
    }, rec


def test_gemini_adapter(monkeypatch):
    mods, rec = _fake_google()
    for name, mod in mods.items():
        _install(monkeypatch, name, mod)
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")

    resp = ai.get_client("gemini", model="gemini-x").complete("ask", system="sys", max_tokens=77)
    assert resp.text == "gemini answer" and resp.provider == "gemini"
    assert rec["api_key"] == "gem-key"
    assert rec["model"] == "gemini-x"
    assert rec["contents"] == "ask"
    assert rec["system_instruction"] == "sys"
    assert rec["max_output_tokens"] == 77


# ── error path still holds with the SDK genuinely absent ─────────────────────
def test_missing_sdk_raises_provider_not_installed(monkeypatch):
    # Simulate the absent SDK regardless of the local env (None in sys.modules
    # makes the import fail clearly, as in CI's base env).
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(ai.ProviderNotInstalled):
        ai.get_client("openai", api_key="x").complete("hi")


# ── a provider's SDK API error surfaces as the clean ProviderCallError ────────
# (a bad model id, authentication failure, rate limit, or network error at call
# time must not leak the SDK's own exception as a raw traceback).


def test_openai_compatible_call_error_becomes_provider_call_error(monkeypatch):
    mod = types.ModuleType("openai")

    class APIError(Exception):
        pass

    class _Completions:
        def create(self, **kwargs):
            raise APIError("Error code: 400 - not a valid model ID")

    class _Chat:
        def __init__(self) -> None:
            self.completions = _Completions()

    class OpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _Chat()

    mod.OpenAI = OpenAI  # type: ignore[attr-defined]
    mod.APIError = APIError  # type: ignore[attr-defined]
    _install(monkeypatch, "openai", mod)

    client = ai.get_client("openrouter", api_key="sk-test", model="bad/model")
    with pytest.raises(ai.ProviderCallError) as exc:
        client.complete("hi")
    assert isinstance(exc.value, ai.AIError)
    assert isinstance(exc.value.__cause__, APIError)  # the SDK error is preserved as the cause
    # the clean message names the provider and model, not a raw SDK traceback
    assert "openrouter" in str(exc.value) and "bad/model" in str(exc.value)


def test_anthropic_call_error_becomes_provider_call_error(monkeypatch):
    mod = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class _Messages:
        def create(self, **kwargs):
            raise APIError("overloaded")

    class Anthropic:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    mod.Anthropic = Anthropic  # type: ignore[attr-defined]
    mod.APIError = APIError  # type: ignore[attr-defined]
    _install(monkeypatch, "anthropic", mod)

    client = ai.get_client("anthropic", api_key="sk-test", model="claude-x")
    with pytest.raises(ai.ProviderCallError) as exc:
        client.complete("hi")
    assert isinstance(exc.value.__cause__, APIError)
    assert "anthropic" in str(exc.value)


def test_gemini_call_error_becomes_provider_call_error(monkeypatch):
    mods, _rec = _fake_google()
    api_error = mods["google.genai.errors"].APIError

    class _Models:
        def generate_content(self, **kwargs):
            raise api_error("quota exceeded")

    mods["google.genai"].Client = lambda api_key=None: types.SimpleNamespace(models=_Models())
    for name, mod in mods.items():
        _install(monkeypatch, name, mod)

    client = ai.get_client("gemini", api_key="gem-key", model="gemini-x")
    with pytest.raises(ai.ProviderCallError) as exc:
        client.complete("hi")
    assert isinstance(exc.value.__cause__, api_error)
    assert "gemini" in str(exc.value)
