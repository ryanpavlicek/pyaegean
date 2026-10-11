"""Offline translation audit contracts; response shape is not linguistic review."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from aegean import ai
from aegean.ai.client import ExploratoryResult, LLMClient, LLMResponse


class AuditClient(LLMClient):
    provider = "audit-stub"
    default_model = "audit-1"

    def __init__(self, response: str) -> None:
        super().__init__()
        self.response = response
        self.calls: list[tuple[str, str | None, int]] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.calls.append((prompt, system, max_tokens))
        return LLMResponse(self.response, self.provider, self.model)


def payload(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "translation": "Valeria and I hope to come to you.",
        "uncertainties": ["The verb may mean hope or pray; context is missing."],
        "changes": [],
    }
    value.update(updates)
    return value


def test_initial_translation_separates_wording_notes_and_exact_response():
    raw = " \n" + json.dumps(payload(), ensure_ascii=False) + "\n "
    client = AuditClient(raw)
    result = ai.translate("εὐχόμεθα", client=client)

    assert result.text == payload()["translation"]
    assert result.data == {
        **payload(), "format_status": "structured", "raw_response": raw, "style": "annotated",
        "text_changed": None, "change_report_status": "not_comparable",
    }
    assert result.draft is None
    assert result.prompt_version == ai.PROMPT_VERSION == "2026.10-v4"
    assert len(client.calls) == 1
    assert client.calls[0][2] == 1024
    assert "ONLY valid JSON" in client.calls[0][1]
    assert "Model-reported uncertainties" in result.labeled()
    assert "context is missing" in result.labeled()


def test_check_retains_exact_draft_provenance_notes_and_model_reported_changes():
    draft_raw = json.dumps(payload(translation="Valeria and I want to come."))
    draft = replace(
        ai.translate("εὐχόμεθα", client=AuditClient(draft_raw)),
        grounding=(ai.GroundingItem("plural first person", source="source:annotation", ref="P1"),),
        grounding_runtime={"mode": "morphology", "pipeline": {"backend": "baseline"}},
    )
    changes = [{
        "before": "Valeria and I want to come.",
        "after": "Valeria and I hope to come to you.",
        "reason": "Attach the coordinated subject to the plural verb.",
        "evidence": ["source εὐχόμεθα", "source:annotation P1"],
    }]
    final_raw = json.dumps(payload(changes=changes))
    client = AuditClient(final_raw)
    result = ai.verify_translation("εὐχόμεθα", draft, client=client)

    assert result.draft is draft
    assert result.data["draft_text"] == draft.text
    assert result.data["changes"] == changes
    assert result.data["raw_response"] == final_raw
    assert result.data["text_changed"] is True
    assert result.data["change_report_status"] == "reported_changes"
    assert len(client.calls) == 1
    prompt = client.calls[0][0]
    assert "<<<DRAFT_NOTES" in prompt and "DRAFT_NOTES>>>" in prompt
    assert "context is missing" in prompt
    assert json.dumps(draft_raw, ensure_ascii=False) in prompt
    assert "removing a note does not establish" in prompt
    labeled = result.labeled()
    assert "not independently verified" in labeled
    assert changes[0]["reason"] in labeled
    assert "source:annotation P1" in labeled
    assert "Retained draft: 1 original uncertainty note" in labeled
    assert result.provenance()["draft"] == draft.provenance()


def test_checked_result_round_trips_with_complete_draft_and_grounding(tmp_path):
    draft = ai.translate("εὐχόμεθα", client=AuditClient(json.dumps(payload())))
    checked = ai.verify_translation(
        "εὐχόμεθα", draft,
        grounding=[ai.GroundingItem("source annotation", source="source:test", ref="R1")],
        client=AuditClient(json.dumps(payload(uncertainties=[], changes=[]))),
    )
    path = tmp_path / "checked.json"
    checked.to_json(path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    restored = ExploratoryResult.from_dict(stored)
    assert restored.to_dict() == checked.to_dict()
    assert restored.draft.to_dict() == draft.to_dict()
    assert restored.exploratory and restored.draft.exploratory
    assert restored.data["uncertainties"] == []
    # A checker omitting a note does not erase the original reported ambiguity.
    assert "context is missing" in restored.labeled()
    assert "does not establish resolution" in restored.labeled()
    trace = restored.trace()
    assert "retained draft (original result and provenance)" in trace
    assert "context is missing" in trace
    assert "audit-stub" in trace and "audit-1" in trace
    assert "source:test" in trace and "R1" in trace
    assert "raw_response" in trace
    assert "format status describes shape only" in trace


@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_string_draft_is_retained_without_inventing_provenance(style):
    draft = "  Sing the wrath.\n\nNotes: uncertain reading.\n "
    result = ai.verify_translation(
        "μῆνιν", draft, style=style, client=AuditClient(json.dumps(payload())),
    )
    assert result.draft is None
    assert result.data["draft_text"] == draft
    assert result.data["text_changed"] is None
    assert result.data["change_report_status"] == "not_comparable"
    assert "draft" not in result.to_dict()
    assert "provenance was not supplied" in result.labeled()
    assert json.dumps(draft)[1:-1] in result.trace()


@pytest.mark.parametrize("raw", [
    "plain translation with a note",
    "",
    '{"translation": "partial translation"}',
    json.dumps(payload(uncertainties=None)),
    json.dumps(payload(uncertainties=["valid", 5])),
    json.dumps(payload(uncertainties=[""])),
    json.dumps(payload(changes="none")),
    json.dumps(payload(changes=[{"before": "a", "after": "b", "reason": "why"}])),
    json.dumps(payload(changes=[{"before": "a", "after": "b", "reason": "", "evidence": []}])),
    json.dumps(payload(changes=[{"before": None, "after": "b", "reason": "why", "evidence": []}])),
    json.dumps(payload(changes=[{"before": "a", "after": "b", "reason": "why", "evidence": "R1"}])),
    json.dumps(payload(changes=[{"before": "a", "after": "b", "reason": "why", "evidence": [""]}])),
    json.dumps(payload(translation=5)),
    json.dumps(payload(translation="  ")),
    json.dumps(payload(extra="unrequested field")),
    json.dumps([payload()]),
    'Prose ' + json.dumps(payload()),
    '{"translation":"first","translation":"second","uncertainties":[],"changes":[]}',
    '{"translation":"text","uncertainties":[],"changes":[],"extra":NaN}',
])
@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_malformed_or_partial_response_preserves_raw_and_marks_missing_notes(raw, style):
    client = AuditClient(raw)
    result = ai.verify_translation("source", "exact draft", style=style, client=client)
    assert len(client.calls) == 1
    assert result.text == raw
    assert result.data["raw_response"] == raw
    assert result.data["translation"] is None
    assert result.data["uncertainties"] is None
    assert result.data["changes"] is None
    assert result.data["format_status"] == "unstructured"
    assert result.data["format_error"]
    assert result.data["draft_text"] == "exact draft"
    assert "Unstructured response" in result.labeled()
    assert "information unavailable" in result.labeled()
    assert "Unstructured response" in result._repr_html_()
    assert ExploratoryResult.from_dict(result.to_dict()).to_dict() == result.to_dict()


@pytest.mark.parametrize(("opening", "newline"), [
    ("```json", "\n"), ("```", "\n"), ("```json ", "\r\n"), ("```\t", "\n"),
])
def test_single_complete_outer_fence_accepts_strict_payload_and_retains_raw(opening, newline):
    raw = " \n" + opening + newline + json.dumps(payload()) + newline + "```\n "
    client = AuditClient(raw)
    result = ai.translate("source", client=client)
    assert len(client.calls) == 1
    assert result.data["format_status"] == "structured"
    assert result.data["raw_response"] == raw
    assert result.text == payload()["translation"]
    assert result.data["uncertainties"] == payload()["uncertainties"]
    assert "Unstructured response" not in result.labeled()


@pytest.mark.parametrize("raw", [
    "Before\n```json\n" + json.dumps(payload()) + "\n```",
    "```json\n" + json.dumps(payload()) + "\n```\nAfter",
    "```json\n" + json.dumps(payload()) + "\n```\n```json\n" + json.dumps(payload()) + "\n```",
    "```json\n" + json.dumps(payload()) + "\n" + json.dumps(payload()) + "\n```",
    '```json\n{"translation":"a","translation":"b","uncertainties":[],"changes":[]}\n```',
    '```json\n{"translation":"a","uncertainties":null,"changes":[]}\n```',
    "```python\n" + json.dumps(payload()) + "\n```",
])
def test_outer_fence_does_not_admit_prose_multiple_objects_blocks_or_invalid_schema(raw):
    client = AuditClient(raw)
    result = ai.translate("source", client=client)
    assert len(client.calls) == 1
    assert result.data["format_status"] == "unstructured"
    assert result.data["raw_response"] == result.text == raw
    assert result.data["changes"] is None


def test_concise_view_signals_retained_notes_and_trace_contains_details():
    draft = ai.translate("source", client=AuditClient(json.dumps(payload())))
    changes = [{"before": "a", "after": "b", "reason": "reported reason", "evidence": []}]
    result = ai.verify_translation(
        "source", draft, style="concise", client=AuditClient(json.dumps(payload(changes=changes))),
    )
    labeled = result.labeled()
    assert "1 uncertainty note(s), 1 change(s)" in labeled
    assert "details retained in trace and JSON" in labeled
    assert "1 original uncertainty note(s)" in labeled
    assert "context is missing" not in labeled
    assert "reported reason" not in labeled
    assert "context is missing" in result.trace()
    assert "reported reason" in result.trace()
    html = result._repr_html_()
    assert "1 uncertainty note(s), 1 change(s)" in html
    assert "Retained original draft" in html


def test_failed_check_still_exposes_retained_original_uncertainty():
    draft = ai.translate("source", client=AuditClient(json.dumps(payload())))
    result = ai.verify_translation("source", draft, client=AuditClient("broken format"))
    assert result.draft is draft
    assert result.data["text_changed"] is None
    assert result.data["change_report_status"] == "not_comparable"
    assert "Unstructured response" in result.labeled()
    assert "context is missing" in result.labeled()
    assert "context is missing" in result.trace()


@pytest.mark.parametrize("style", ["annotated", "concise"])
@pytest.mark.parametrize(("final_text", "changed", "status"), [
    ("Different final wording.", True, "unreported_text_difference"),
    ("Same translation.", False, "no_text_difference"),
    ("Same translation. ", True, "unreported_text_difference"),
])
def test_local_exact_comparison_flags_changes_missing_from_model_report(style, final_text, changed, status):
    draft = ai.translate(
        "source", client=AuditClient(json.dumps(payload(translation="Same translation."))),
    )
    raw = json.dumps(payload(translation=final_text, changes=[]))
    result = ai.verify_translation("source", draft, style=style, client=AuditClient(raw))
    assert result.data["text_changed"] is changed
    assert result.data["change_report_status"] == status
    assert result.data["changes"] == []
    assert result.data["raw_response"] == raw
    assert result.text == final_text
    assert result.draft is draft
    if changed:
        assert "final text differs" in result.labeled()
        assert "model reported no changes" in result.labeled()
        assert "model reported no changes" in result._repr_html_()
        assert "not a quality assessment" in result.labeled()
    else:
        assert "final translation text is identical" in result.labeled()
        assert "model reported no changes" not in result.labeled()
    assert status in result.trace()
    assert ExploratoryResult.from_dict(result.to_dict()).data["text_changed"] is changed


@pytest.mark.parametrize("draft_kind", ["string", "legacy", "unstructured"])
def test_notes_removal_from_raw_or_legacy_draft_is_not_comparable(draft_kind):
    draft_text = "Same translation.\n\nUncertainty: possible alternative sense."
    if draft_kind == "string":
        draft = draft_text
    elif draft_kind == "legacy":
        draft = ExploratoryResult(
            text=draft_text, kind="translate", provider="old", model="old-model", prompt_version="old",
        )
    else:
        draft = ai.translate("source", client=AuditClient(draft_text))
    result = ai.verify_translation(
        "source", draft,
        client=AuditClient(json.dumps(payload(translation="Same translation.", uncertainties=[], changes=[]))),
    )
    assert result.data["text_changed"] is None
    assert result.data["change_report_status"] == "not_comparable"
    assert result.data["changes"] == []
    assert "comparison unavailable" in result.labeled()
    assert "final text differs" not in result.labeled()
    assert result.data["draft_text"] == draft_text


def test_reported_changes_with_identical_text_remain_model_reported():
    draft = ai.translate("source", client=AuditClient(json.dumps(payload())))
    changes = [{"before": "same", "after": "same", "reason": "model claim", "evidence": []}]
    result = ai.verify_translation("source", draft, client=AuditClient(json.dumps(payload(changes=changes))))
    assert result.data["text_changed"] is False
    assert result.data["change_report_status"] == "reported_changes"
    assert result.data["changes"] == changes
    assert "final text is identical" in result.labeled()
    assert "not independently verified" in result.labeled()


@pytest.mark.parametrize("edit_method", ["replace", "saved_json"])
@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_edited_draft_text_inconsistent_with_stored_translation_is_not_comparable(edit_method, style):
    original = ai.translate("source", client=AuditClient(json.dumps(payload())))
    revised_text = "Human revised wording."
    if edit_method == "replace":
        draft = replace(original, text=revised_text)
    else:
        saved = original.to_dict()
        saved["text"] = revised_text
        draft = ExploratoryResult.from_dict(saved)
    client = AuditClient(json.dumps(payload()))
    result = ai.verify_translation("source", draft, style=style, client=client)
    assert result.data["text_changed"] is None
    assert result.data["change_report_status"] == "not_comparable"
    assert "Draft text differs from its stored structured translation" in result.data["comparison_note"]
    assert "comparison is unavailable" in result.labeled()
    assert "final translation text is identical" not in result.labeled()
    assert "final text differs" not in result.labeled()
    assert result.data["draft_text"] == revised_text
    assert result.draft.text == revised_text
    prompt = client.calls[0][0]
    assert revised_text in prompt
    assert "current DRAFT block contains the wording to check" in prompt
    assert "original translation must not override the current DRAFT wording" in prompt
    assert result.data["comparison_note"] in result.trace()
    assert result.data["comparison_note"] in result._repr_html_()


def test_html_escapes_translation_notes_changes_evidence_and_draft():
    unsafe = "<script>alert('x')</script>"
    draft = ai.translate(
        unsafe, client=AuditClient(json.dumps(payload(translation=unsafe, uncertainties=[unsafe]))),
    )
    changes = [{"before": unsafe, "after": unsafe, "reason": unsafe, "evidence": [unsafe]}]
    result = ai.verify_translation(
        unsafe, draft,
        client=AuditClient(json.dumps(payload(translation=unsafe, uncertainties=[unsafe], changes=changes))),
    )
    html = result._repr_html_()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Model-reported uncertainties" in html
    assert "Evidence reported by model" in html


@pytest.mark.parametrize("operation", ["translate", "verify_translation"])
@pytest.mark.parametrize("style", ["", "full", "CONCISE", None])
def test_invalid_style_rejected_before_provider_call(operation, style):
    client = AuditClient(json.dumps(payload()))
    kwargs = {"style": style, "client": client}
    with pytest.raises(ValueError, match="translation style"):
        if operation == "translate":
            ai.translate("source", **kwargs)
        else:
            ai.verify_translation("source", "draft", **kwargs)
    assert client.calls == []


def test_invalid_draft_type_rejected_before_provider_call():
    client = AuditClient(json.dumps(payload()))
    with pytest.raises(TypeError, match="draft must be"):
        ai.verify_translation("source", {"translation": "draft"}, client=client)
    assert client.calls == []


def test_legacy_result_deserialization_and_bad_draft_shape():
    legacy = {
        "text": "a legacy result with inline notes", "kind": "translate",
        "provider": "old", "model": "old-1", "prompt_version": "old",
    }
    result = ExploratoryResult.from_dict(legacy)
    assert result.draft is None
    assert result.data is None
    assert result.text in result.labeled()
    assert "draft" not in result.to_dict()
    assert ExploratoryResult.from_dict({**legacy, "draft": None}).draft is None
    with pytest.raises(ValueError, match="draft must be"):
        ExploratoryResult.from_dict({**legacy, "draft": "unprovenanced text"})


def test_prompt_requires_evidence_for_editorial_and_attribution_claims():
    client = AuditClient(json.dumps(payload()))
    ai.translate("first wording; second wording", client=client)
    prompt, system, _ = client.calls[0]
    assert "do not infer a revision relationship" in prompt
    assert "Without explicit supplied evidence" in system
    assert "bibliographic or scholarly attributions" in system
    assert "identify an unnamed person" in system
    assert "No other fields" in prompt


def test_grounding_generator_retained_once_in_prompt_and_result():
    client = AuditClient(json.dumps(payload()))
    result = ai.translate("source", grounding=(line for line in ["evidence1", "evidence2"]), client=client)
    assert [item.content for item in result.grounding] == ["evidence1", "evidence2"]
    assert "evidence1" in client.calls[0][0] and "evidence2" in client.calls[0][0]
