"""The hybrid workflow keeps target analysis separate from source context."""

from __future__ import annotations

import json

import pytest

from aegean import ai, translate
from aegean.ai.client import LLMClient, LLMResponse


class ContextClient(LLMClient):
    provider = "fixture"

    def __init__(self) -> None:
        super().__init__("context-fixture")
        self.calls: list[str] = []
        self.limits: list[int] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.calls.append(prompt)
        self.limits.append(max_tokens)
        return LLMResponse(json.dumps({
            "translation": "He gave it to her.", "uncertainties": [], "changes": [],
        }), self.provider, self.model)


@pytest.mark.parametrize("verify", [False, True])
def test_context_reaches_all_stages_without_becoming_analysis_input(monkeypatch, verify):
    target = "ὃ δὲ τῇ δῶκεν."
    context = "Source context: speaker identification.\r\nὁ Ἑρμῆς· ἡ δὲ Κόρη.\n"
    analyzed = []

    def grounding(text, script, **kwargs):
        analyzed.append(text)
        return translate._GroundingOutcome([], {"mode": kwargs["mode"]})

    monkeypatch.setattr(translate, "_build_grounding", grounding)
    monkeypatch.setattr(translate, "_rich_lemmatizer_active", lambda pipeline: True)
    client = ContextClient()
    result = translate.translate(target, source_context=context, verify=verify, client=client,
                                 max_tokens=3072)
    assert analyzed == [target]
    assert len(client.calls) == (2 if verify else 1)
    assert client.limits == [3072] * len(client.calls)
    assert all(context in prompt and target in prompt for prompt in client.calls)
    assert result.data["source_context"] == context
    if verify:
        assert result.draft.data["source_context"] == context
    restored = ai.ExploratoryResult.from_dict(json.loads(result.to_json()))
    assert restored == result
    checker = ContextClient()
    checked = ai.verify_translation(target, restored, client=checker)
    assert checked.data["source_context"] == context
    assert context in checker.calls[0]
    assert checked.draft == restored


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2048"])
def test_invalid_limit_stops_before_analysis(monkeypatch, limit):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid output limit reached analysis")
    monkeypatch.setattr(translate, "_build_grounding", forbidden)
    with pytest.raises((TypeError, ValueError), match="max_tokens"):
        translate.translate("λόγος", max_tokens=limit, client=ContextClient())


@pytest.mark.parametrize("context", [1, {}, [], False])
def test_bad_context_fails_before_analysis_or_provider(monkeypatch, context):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid context reached analysis")

    monkeypatch.setattr(translate, "_build_grounding", forbidden)
    client = ContextClient()
    with pytest.raises(TypeError, match="source_context"):
        translate.translate("λόγος", source_context=context, client=client)
    assert not client.calls
