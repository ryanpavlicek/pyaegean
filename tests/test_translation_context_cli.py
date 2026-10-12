"""CLI source context reaches drafting/checking and survives saved-result replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegean import ai, translate
from aegean.ai.client import ExploratoryResult, LLMClient, LLMResponse
from aegean.cli import _ai, _build_app


_TEXT = "εὐχόμεθα"
_CONTEXT = " \r\nSpeaker: messenger.\r\nSurrounding text: μετὰ τῶν φίλων.\r\n "


class _ContextClient(LLMClient):
    provider = "context-fixture"

    def __init__(self) -> None:
        super().__init__("context-fixture-model")
        self.prompts: list[str] = []
        self.token_limits: list[int] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.prompts.append(prompt)
        self.token_limits.append(max_tokens)
        return LLMResponse(json.dumps({
            "translation": "We pray.", "uncertainties": [], "changes": [],
        }), self.provider, self.model)


@pytest.mark.parametrize("verify", [False, True])
@pytest.mark.parametrize("file_input", [False, True])
def test_context_options_forward_exact_decoded_text_without_changing_provider_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verify: bool, file_input: bool,
) -> None:
    seen: list[tuple[str, dict]] = []
    clients: list[tuple[str, str | None]] = []
    client = object()

    def fake_client(provider: str, model: str | None) -> object:
        clients.append((provider, model))
        return client

    def fake_translate(text: str, **kwargs) -> ExploratoryResult:
        seen.append((text, kwargs))
        return ExploratoryResult("fixture", "translate", "fixture", "fixture-model", "fixture")

    monkeypatch.setattr(_ai, "_client", fake_client)
    monkeypatch.setattr(translate, "translate", fake_translate)
    arguments = ["ai", "translate", "-", "--provider", "fixture", "--model", "selected", "--json"]
    if file_input:
        context = tmp_path / "source context.txt"
        context.write_bytes(b"\xef\xbb\xbf" + _CONTEXT.encode("utf-8"))
        arguments.extend(["--source-context-file", str(context)])
    else:
        arguments.extend(["--source-context", _CONTEXT])
    if verify:
        arguments.append("--verify")
    result = CliRunner().invoke(_build_app(), arguments, input=_TEXT)
    assert result.exit_code == 0, result.output
    assert len(seen) == 1 and seen[0][0] == _TEXT
    assert seen[0][1]["source_context"] == _CONTEXT
    assert seen[0][1]["verify"] is verify
    assert seen[0][1]["client"] is client
    assert clients == [("fixture", "selected")]


@pytest.mark.parametrize("context", ["", " \t\r\n"])
@pytest.mark.parametrize("file_input", [False, True])
def test_explicit_empty_context_remains_distinct_from_omitted_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, context: str, file_input: bool,
) -> None:
    seen: dict[str, object] = {}

    def fake_translate(text: str, **kwargs) -> ExploratoryResult:
        seen.update(kwargs)
        return ExploratoryResult("fixture", "translate", "fixture", "fixture-model", "fixture")

    monkeypatch.setattr(_ai, "_client", lambda provider, model: object())
    monkeypatch.setattr(translate, "translate", fake_translate)
    arguments = ["ai", "translate", _TEXT, "--json"]
    if file_input:
        path = tmp_path / "empty.txt"
        path.write_bytes(context.encode("utf-8"))
        arguments.extend(["--source-context-file", str(path)])
    else:
        arguments.extend(["--source-context", context])
    result = CliRunner().invoke(_build_app(), arguments)
    assert result.exit_code == 0, result.output
    assert seen["source_context"] == context
    seen.clear()
    omitted = CliRunner().invoke(_build_app(), ["ai", "translate", _TEXT, "--json"])
    assert omitted.exit_code == 0, omitted.output
    assert "source_context" not in seen


@pytest.mark.parametrize("file_kind,diagnostic", [
    ("missing", "could not read source context file"),
    ("directory", "could not read source context file"),
    ("bad-encoding", "must be UTF-8"),
])
def test_invalid_context_file_fails_before_backend_client_or_output_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, file_kind: str, diagnostic: str,
) -> None:
    from aegean.greek import GreekPipeline

    def forbidden(*args, **kwargs):
        pytest.fail("invalid source context must fail before analysis or client construction")

    monkeypatch.setattr(_ai, "_client", forbidden)
    monkeypatch.setattr(_ai, "read_text", forbidden)
    monkeypatch.setattr(GreekPipeline, "neural", classmethod(forbidden))
    monkeypatch.setattr(translate, "translate", forbidden)
    path = tmp_path / "context.txt"
    if file_kind == "directory":
        path.mkdir()
    elif file_kind == "bad-encoding":
        path.write_bytes(b"\xff\xfeinvalid")
    output = tmp_path / "existing.json"
    original = b"existing output\x00\xff"
    output.write_bytes(original)
    result = CliRunner().invoke(_build_app(), [
        "ai", "translate", "-", "--source-context-file", str(path),
        "--greek-backend", "neural", "--output", str(output),
    ])
    assert result.exit_code == 1, result.output
    assert diagnostic in result.output and "Traceback" not in result.output
    assert isinstance(result.exception, SystemExit)
    assert output.read_bytes() == original


@pytest.mark.parametrize("inline", ["", "inline source note"])
def test_mutually_exclusive_context_options_fail_before_reading_or_calling_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inline: str,
) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("conflicting source context must not create a provider")

    monkeypatch.setattr(_ai, "_client", forbidden)
    missing = tmp_path / "missing.txt"
    result = CliRunner().invoke(_build_app(), [
        "ai", "translate", _TEXT, "--source-context", inline,
        "--source-context-file", str(missing), "--json",
    ])
    assert result.exit_code == 1, result.output
    assert "mutually exclusive" in result.output
    assert "could not read" not in result.output
    assert "Traceback" not in result.output
    assert not missing.exists()


@pytest.fixture
def local_grounding(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    texts: list[str] = []

    def build_grounding(text: str, script: str, **kwargs):
        texts.append(text)
        return translate._GroundingOutcome([], {"mode": kwargs["mode"]})

    monkeypatch.setattr(translate, "_build_grounding", build_grounding)
    monkeypatch.setattr(translate, "_rich_lemmatizer_active", lambda pipeline: True)
    return texts


@pytest.mark.parametrize("verify", [False, True])
@pytest.mark.parametrize("file_output", [False, True])
def test_real_cli_orchestration_keeps_context_in_every_prompt_and_saved_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_grounding: list[str],
    verify: bool, file_output: bool,
) -> None:
    client = _ContextClient()
    monkeypatch.setattr(_ai, "_client", lambda provider, model: client)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-secret-not-context")
    source = tmp_path / "context.txt"
    source.write_bytes(b"\xef\xbb\xbf" + _CONTEXT.encode("utf-8"))
    output = tmp_path / "translation.json"
    arguments = [
        "ai", "translate", _TEXT, "--source-context-file", str(source), "--style", "concise",
    ]
    if verify:
        arguments.append("--verify")
    arguments.extend(["--output", str(output)] if file_output else ["--json"])
    result = CliRunner().invoke(_build_app(), arguments)
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8") if file_output else result.stdout)
    assert payload["data"]["source_context"] == _CONTEXT
    assert len(client.prompts) == (2 if verify else 1)
    assert all("SOURCE_CONTEXT" in prompt and "messenger" in prompt
               and "μετὰ τῶν φίλων" in prompt for prompt in client.prompts)
    assert local_grounding == [_TEXT]
    assert "fixture-secret-not-context" not in json.dumps(payload)
    assert all("fixture-secret-not-context" not in prompt for prompt in client.prompts)
    restored = ExploratoryResult.from_dict(payload)
    if file_output:
        assert restored.to_dict() == payload
    else:
        from aegean.cli._common import to_plain

        assert to_plain(restored) == payload
    if verify:
        assert restored.draft is not None
        assert restored.draft.data["source_context"] == _CONTEXT
        assert restored.draft.text == "We pray."
    else:
        assert restored.draft is None


def test_cli_saved_draft_inherits_exact_context_in_api_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_grounding: list[str],
) -> None:
    initial = _ContextClient()
    monkeypatch.setattr(_ai, "_client", lambda provider, model: initial)
    output = tmp_path / "saved-draft.json"
    result = CliRunner().invoke(_build_app(), [
        "ai", "translate", _TEXT, "--source-context", _CONTEXT, "--output", str(output),
    ])
    assert result.exit_code == 0, result.output
    saved_bytes = output.read_bytes()
    draft = ExploratoryResult.from_dict(json.loads(saved_bytes))
    checker = _ContextClient()
    checked = ai.verify_translation(_TEXT, draft, client=checker)
    assert checked.draft is draft
    assert checked.data["source_context"] == _CONTEXT
    assert draft.data["source_context"] == _CONTEXT
    assert len(checker.prompts) == 1
    assert "SOURCE_CONTEXT" in checker.prompts[0] and "messenger" in checker.prompts[0]
    assert output.read_bytes() == saved_bytes
    checked_path = tmp_path / "checked.json"
    checked.to_json(checked_path)
    reopened = ExploratoryResult.from_dict(json.loads(checked_path.read_text(encoding="utf-8")))
    assert reopened.to_dict() == checked.to_dict()
    assert reopened.draft is not None and reopened.draft.data["source_context"] == _CONTEXT


def test_explicit_context_conflict_after_cli_save_fails_without_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_grounding: list[str],
) -> None:
    initial = _ContextClient()
    monkeypatch.setattr(_ai, "_client", lambda provider, model: initial)
    path = tmp_path / "draft.json"
    result = CliRunner().invoke(_build_app(), [
        "ai", "translate", _TEXT, "--source-context", _CONTEXT, "--output", str(path),
    ])
    assert result.exit_code == 0, result.output
    saved = path.read_bytes()
    draft = ExploratoryResult.from_dict(json.loads(saved))
    checker = _ContextClient()
    with pytest.raises(ValueError, match="context"):
        ai.verify_translation(_TEXT, draft, source_context="different source", client=checker)
    assert checker.prompts == []
    assert path.read_bytes() == saved


def test_context_options_are_visible_in_translate_help() -> None:
    from rich.text import Text

    result = CliRunner().invoke(
        _build_app(), ["ai", "translate", "--help"], env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    rendered = "".join(Text.from_ansi(result.output).plain.split())
    assert "--source-context" in rendered and "--source-context-file" in rendered
    assert "--max-tokens" in rendered


@pytest.mark.parametrize("verify", [False, True])
@pytest.mark.parametrize("explicit_limit", [None, 3072])
def test_cli_output_token_limit_reaches_every_translation_call(
    monkeypatch: pytest.MonkeyPatch, local_grounding: list[str],
    verify: bool, explicit_limit: int | None,
) -> None:
    client = _ContextClient()
    monkeypatch.setattr(_ai, "_client", lambda provider, model: client)
    arguments = ["ai", "translate", _TEXT, "--source-context", _CONTEXT, "--json"]
    if verify:
        arguments.append("--verify")
    if explicit_limit is not None:
        arguments.extend(["--max-tokens", str(explicit_limit)])
    result = CliRunner().invoke(_build_app(), arguments)
    assert result.exit_code == 0, result.output
    assert client.token_limits == [explicit_limit or 2048] * (2 if verify else 1)
    assert local_grounding == [_TEXT]
    assert json.loads(result.stdout)["data"]["source_context"] == _CONTEXT


@pytest.mark.parametrize("invalid_limit", ["0", "-1", "1.5", "True"])
def test_cli_invalid_output_limit_fails_before_backend_client_or_output_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_limit: str,
) -> None:
    from aegean.greek import GreekPipeline
    from rich.text import Text

    def forbidden(*args, **kwargs):
        pytest.fail("invalid output limit must fail before analysis or client construction")

    monkeypatch.setattr(_ai, "_client", forbidden)
    monkeypatch.setattr(GreekPipeline, "neural", classmethod(forbidden))
    monkeypatch.setattr(translate, "translate", forbidden)
    destination = tmp_path / "existing.json"
    destination.write_bytes(b"previous output")
    result = CliRunner().invoke(_build_app(), [
        "ai", "translate", _TEXT, "--max-tokens", invalid_limit,
        "--greek-backend", "neural", "--output", str(destination),
    ])
    assert result.exit_code == 2, result.output
    rendered = Text.from_ansi(result.output).plain
    assert "Invalid value" in rendered and "--max-tokens" in "".join(rendered.split())
    assert "Traceback" not in result.output
    assert destination.read_bytes() == b"previous output"
