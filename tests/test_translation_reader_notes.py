"""Reader translations retain the shared uncertainty and response-format labels."""

from __future__ import annotations

import asyncio
import json

import pytest

from aegean import ai, translate
from aegean.ai.client import LLMClient, LLMResponse
from aegean.tui import data as adapter


class _ReaderClient(LLMClient):
    provider = "reader-fixture"
    default_model = "reader-model"

    def __init__(self, response: str) -> None:
        super().__init__()
        self.response = response
        self.calls: list[str] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.calls.append(prompt)
        return LLMResponse(self.response, self.provider, self.model)


def _configure_reader(monkeypatch: pytest.MonkeyPatch, raw: str) -> _ReaderClient:
    client = _ReaderClient(raw)
    monkeypatch.setattr(adapter, "_usable_providers", lambda: [client.provider])
    monkeypatch.setattr(ai, "get_client", lambda provider: client)
    monkeypatch.setattr(
        translate, "_build_grounding",
        lambda *args, **kwargs: translate._GroundingOutcome([], {"mode": kwargs["mode"]}),
    )
    monkeypatch.setattr(translate, "_rich_lemmatizer_active", lambda pipeline: True)
    return client


def test_reader_retains_translation_uncertainty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configure_reader(monkeypatch, json.dumps({
        "translation": "I speak.", "uncertainties": ["The addressee remains uncertain."],
        "changes": [],
    }))
    result = adapter.translate_line("λέγω", source_context="Speaker unidentified.")
    assert result.ok and result.text == "I speak."
    assert "The addressee remains uncertain." in result.note
    assert "Model-reported uncertainties" in result.note
    assert "exploratory · reader-fixture/reader-model" in result.note
    assert len(client.calls) == 1
    assert "Speaker unidentified." in client.calls[0]


@pytest.mark.parametrize("raw", [
    "A translation with [bold]literal brackets[/bold] and no structured notes.",
    '{"translation":"partial response"}',
])
def test_reader_marks_unavailable_notes_without_altering_raw_output(
    monkeypatch: pytest.MonkeyPatch, raw: str,
) -> None:
    client = _configure_reader(monkeypatch, raw)
    result = adapter.translate_line("λέγω")
    assert result.ok and result.text == raw
    assert "Unstructured response" in result.note
    assert "information unavailable; raw response retained" in result.note
    assert "None listed by the model" not in result.note
    assert len(client.calls) == 1


def test_reader_uses_shared_concise_audit_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _configure_reader(monkeypatch, json.dumps({
        "translation": "I speak.", "uncertainties": ["Unresolved reading."], "changes": [],
    }))
    # The reader currently requests the default annotated style. A concise result
    # supplied by the translation layer must still expose its retained-note count.
    concise = ai.translate("λέγω", style="concise", client=client)
    monkeypatch.setattr(translate, "translate", lambda *args, **kwargs: concise)
    result = adapter.translate_line("λέγω")
    assert result.text == "I speak."
    assert concise._translation_notes() in result.note
    assert "1 uncertainty note(s)" in result.note
    assert "Unresolved reading." not in result.note
    assert result.note.count("exploratory ·") == 1


@pytest.mark.xdist_group("tui")
def test_reader_modal_shows_uncertainty_and_brackets_as_literal_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("textual")
    from textual.app import App
    from textual.widgets import Static

    from aegean.tui.screens.analysis import LineAnalysisScreen, format_result

    translation = "[bold]I speak.[/bold]"
    uncertainty = "The [red]addressee[/red] remains uncertain."
    client = _configure_reader(monkeypatch, json.dumps({
        "translation": translation, "uncertainties": [uncertainty], "changes": [],
    }))
    monkeypatch.setattr(adapter, "line_analyses", lambda script_id: [
        adapter.AnalysisOption("translate", "translation", True),
    ])

    async def journey() -> None:
        app = App()
        async with app.run_test(size=(120, 40)) as pilot:
            modal = LineAnalysisScreen(
                script_id="greek", line_number=1,
                line_text="[bold]λέγω[/bold]", token_texts=("λέγω",),
                source_context="An unidentified speaker.",
            )
            app.push_screen(modal)
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            output = modal.query_one("#analysis-output", Static)
            rendered = str(output.render())
            assert translation in rendered and uncertainty in rendered
            assert "Model-reported uncertainties" in rendered
            assert rendered.count("exploratory · reader-fixture/reader-model") == 1
            source_line = modal.query_one("#analysis-line", Static)
            assert "[bold]λέγω[/bold]" in str(source_line.render())
            assert rendered == format_result(adapter.AnalysisResult(
                ok=True, title="translation", text=translation,
                note="exploratory · reader-fixture/reader-model\n\n"
                "Model-reported uncertainties:\n- " + uncertainty,
            ))

    asyncio.run(journey())
    assert len(client.calls) == 1
    assert "An unidentified speaker." in client.calls[0]
