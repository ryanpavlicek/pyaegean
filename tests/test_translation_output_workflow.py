"""Public translation and CLI preserve both stages of an optional model check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegean import ai, translate
from aegean.ai.client import LLMClient, LLMResponse


class TranslationClient(LLMClient):
    provider = "fixture"

    def __init__(self) -> None:
        super().__init__("translation-fixture")
        self.calls: list[str] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.calls.append(prompt)
        payload = {
            "translation": "The child sees the man.",
            "uncertainties": ["The child's social status needs context."],
            "changes": [],
        }
        if len(self.calls) == 2:
            payload["translation"] = "The boy sees the man."
            payload["changes"] = [{
                "before": "child", "after": "boy",
                "reason": "The masculine article favors a male referent.",
                "evidence": ["ὁ παῖς"],
            }]
        return LLMResponse(json.dumps(payload), self.provider, self.model)


@pytest.fixture
def local_grounding(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exercise the public orchestration without an optional model or lexicon.
    monkeypatch.setattr(
        translate, "_build_grounding",
        lambda *args, **kwargs: translate._GroundingOutcome([], {"mode": kwargs["mode"]}),
    )
    monkeypatch.setattr(translate, "_rich_lemmatizer_active", lambda pipeline: True)


@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_check_keeps_draft_notes_and_reasons(local_grounding: None, style: str) -> None:
    client = TranslationClient()
    result = translate.translate("ὁ παῖς τὸν ἄνδρα ὁρᾷ.", verify=True, style=style, client=client)
    assert len(client.calls) == 2
    assert result.text == "The boy sees the man."
    assert result.draft is not None
    assert result.draft.text == "The child sees the man."
    assert result.draft.data["uncertainties"] == result.data["uncertainties"]
    assert "social status" in client.calls[1]
    assert result.data["changes"][0]["evidence"] == ["ὁ παῖς"]
    assert result.exploratory and result.draft.exploratory
    restored = ai.ExploratoryResult.from_dict(json.loads(result.to_json()))
    assert restored == result
    assert "The child sees the man." in result.trace()
    assert "social status" in result.trace()


def test_default_translation_has_one_call_and_no_draft(local_grounding: None) -> None:
    client = TranslationClient()
    result = translate.translate("ὁ παῖς τὸν ἄνδρα ὁρᾷ.", client=client)
    assert len(client.calls) == 1
    assert result.draft is None
    assert result.data["uncertainties"]


def test_invalid_style_fails_before_analysis_or_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("analysis must not run")

    monkeypatch.setattr(translate, "_build_grounding", forbidden)
    client = TranslationClient()
    with pytest.raises(ValueError, match="style"):
        translate.translate("λόγος", style="invisible", client=client)
    assert not client.calls


@pytest.mark.parametrize("file_output", [False, True])
def test_cli_json_keeps_complete_check(
    local_grounding: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, file_output: bool,
) -> None:
    from aegean.cli import _ai, _build_app

    client = TranslationClient()
    monkeypatch.setattr(_ai, "_client", lambda provider, model: client)
    destination = tmp_path / "translation.json"
    args = ["ai", "translate", "ὁ παῖς τὸν ἄνδρα ὁρᾷ.", "--verify", "--style", "concise"]
    args.extend(["--output", str(destination)] if file_output else ["--json"])
    outcome = CliRunner().invoke(_build_app(), args)
    assert outcome.exit_code == 0, outcome.output
    payload = json.loads(destination.read_text() if file_output else outcome.output)
    assert payload["draft"]["text"] == "The child sees the man."
    assert payload["data"]["changes"][0]["before"] == "child"
    assert payload["data"]["uncertainties"] == payload["draft"]["data"]["uncertainties"]


@pytest.mark.parametrize("trace", [False, True])
def test_cli_text_file_includes_draft_and_uncertainty(
    local_grounding: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, trace: bool,
) -> None:
    from aegean.cli import _ai, _build_app

    monkeypatch.setattr(_ai, "_client", lambda provider, model: TranslationClient())
    destination = tmp_path / "translation.txt"
    args = [
        "ai", "translate", "ὁ παῖς τὸν ἄνδρα ὁρᾷ.", "--verify", "--style", "concise",
        "--output", str(destination),
    ]
    if trace:
        args.append("--trace")
    outcome = CliRunner().invoke(_build_app(), args)
    assert outcome.exit_code == 0, outcome.output
    saved = destination.read_text()
    assert "EXPLORATORY" in saved
    assert "The boy sees the man." in saved and "The child sees the man." in saved
    assert "social status" in saved and "masculine article" in saved


def test_cli_rejects_bad_style_before_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegean.cli import _ai, _build_app

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("client must not be constructed")

    monkeypatch.setattr(_ai, "_client", forbidden)
    outcome = CliRunner().invoke(_build_app(), ["ai", "translate", "λόγος", "--style", "hidden"])
    assert outcome.exit_code != 0
    assert "--style must be annotated or concise" in outcome.output
