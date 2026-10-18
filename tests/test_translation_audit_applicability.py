"""Translation displays distinguish edited wording from retained response audits."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from aegean import ai
from aegean.ai.client import ExploratoryResult, LLMClient, LLMResponse


_SOURCE = "λέγω καὶ μένω"
_ENGLISH = "I speak and I stay."
_EDITED = "I speak."
_WARNING = "Displayed text differs from the stored structured translation."
_COMPARISON_WARNING = "Retained draft text differs from the recorded checking input."
_ORIGINAL_NOTE = "The second verb may have another sense; source context is insufficient."


def _response(*, translation=_ENGLISH, uncertainties=(), changes=(), clauses=False):
    payload = {
        "translation": translation,
        "uncertainties": list(uncertainties),
        "changes": list(changes),
    }
    if clauses:
        payload["clause_checks"] = [{
            "source": {"text": _SOURCE, "occurrence": 1},
            "translation": {"text": translation, "occurrence": 1},
            "checks": dict.fromkeys(
                ("roles", "negation", "qualifications", "speech_act"), "preserved",
            ),
            "finding": "Both actions are retained.",
            "evidence_refs": [],
        }]
    return json.dumps(payload, ensure_ascii=False)


class _Client(LLMClient):
    provider = "audit-fixture"

    def __init__(self, *responses):
        super().__init__("audit-fixture-model")
        self.responses = responses
        self.calls = []

    def _complete(self, *, prompt, system, max_tokens):
        index = len(self.calls)
        assert index < len(self.responses), "unexpected provider call"
        self.calls.append(prompt)
        return LLMResponse(self.responses[index], self.provider, self.model)


def _checked(*, style="annotated", policy="clauses", report="no_text_difference"):
    initial_text = "I speak and remain." if report == "unreported_text_difference" else _ENGLISH
    changes = []
    if report == "reported_changes":
        changes = [{"before": "stay", "after": "stay", "reason": "Model report.", "evidence": []}]
    client = _Client(
        _response(translation=initial_text),
        _response(clauses=policy == "clauses", changes=changes),
    )
    initial = ai.translate(_SOURCE, style=style, client=client)
    result = ai.verify_translation(_SOURCE, initial, style=style, check_policy=policy, client=client)
    assert len(client.calls) == 2
    assert result.data["change_report_status"] == report
    return result


def _edit(result, method):
    if method == "replace":
        return replace(result, text=_EDITED)
    saved = json.loads(result.to_json())
    saved["text"] = _EDITED
    return ExploratoryResult.from_dict(saved)


def _edit_retained_draft(result, method):
    if method == "replace":
        return replace(result, draft=replace(result.draft, text=_EDITED))
    saved = json.loads(result.to_json())
    saved["draft"]["text"] = _EDITED
    return ExploratoryResult.from_dict(saved)


@pytest.mark.parametrize("style", ["annotated", "concise"])
@pytest.mark.parametrize("method", ["replace", "saved_json"])
@pytest.mark.parametrize("policy", ["standard", "clauses"])
@pytest.mark.parametrize("report", [
    "no_text_difference", "reported_changes", "unreported_text_difference",
])
def test_edited_wording_has_historical_notes_without_current_validation_claims(
    style, method, policy, report,
):
    original = _checked(style=style, policy=policy, report=report)
    before = copy.deepcopy(original.to_dict())
    revised = _edit(original, method)
    revised_before = copy.deepcopy(revised.to_dict())

    for rendered in (revised.labeled(), revised._repr_html_()):
        assert _EDITED in rendered
        assert _WARNING in rendered
        assert "validation of the displayed wording is unavailable" in rendered
        assert "[Exact text comparison:" not in rendered
        assert "[Clause check: aligned" not in rendered
        assert "Historical model-reported" in rendered
        if policy == "clauses":
            assert "Historical clause check: aligned for the stored response" in rendered

    trace = revised.trace()
    assert _WARNING in trace
    assert "current displayed translation:\n      I speak." in trace
    assert "historical translation audit for the stored response" in trace
    assert _ENGLISH in trace
    assert original.to_dict() == before
    assert revised.to_dict() == revised_before
    restored = ExploratoryResult.from_dict(json.loads(revised.to_json()))
    assert restored.to_dict() == revised_before
    assert _WARNING in restored.labeled()
    assert _WARNING in restored._repr_html_()


@pytest.mark.parametrize("style", ["annotated", "concise"])
@pytest.mark.parametrize("method", ["replace", "saved_json"])
def test_edited_clause_result_text_export_preserves_both_wordings_and_history(
    tmp_path: Path, style, method,
):
    from aegean.cli._ai import _write_ai_result

    revised = _edit(_checked(style=style), method)
    before = copy.deepcopy(revised.to_dict())
    destination = tmp_path / "edited.txt"
    _write_ai_result(revised, destination)
    saved = destination.read_text(encoding="utf-8")
    assert _EDITED in saved
    assert _ENGLISH in saved
    assert _WARNING in saved
    assert "Historical clause check: aligned for the stored response" in saved
    assert "[Clause check: aligned" not in saved
    assert "[Exact text comparison:" not in saved
    assert revised.to_dict() == before


@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_unmodified_and_rechecked_results_have_applicable_current_audits(style):
    checked = _checked(style=style)
    assert "[Clause check: aligned;" in checked.labeled()
    assert "[Exact text comparison: final translation text is identical" in checked.labeled()
    assert _WARNING not in checked.labeled()
    assert "historical translation audit" not in checked.trace()

    revised = replace(checked, text=_EDITED)
    before = copy.deepcopy(revised.to_dict())
    client = _Client(_response(clauses=True))
    rechecked = ai.verify_translation(
        _SOURCE, revised, style=style, check_policy="clauses", client=client,
    )
    assert len(client.calls) == 1
    assert rechecked.draft is revised
    assert rechecked.text == rechecked.data["translation"] == _ENGLISH
    assert rechecked.data["clause_check_status"] == "aligned"
    assert "[Clause check: aligned;" in rechecked.labeled()
    assert _WARNING not in rechecked.labeled()
    assert "Draft text differs from its stored structured translation" in rechecked.labeled()
    assert revised.to_dict() == before


@pytest.mark.parametrize("style", ["annotated", "concise"])
@pytest.mark.parametrize("method", ["replace", "saved_json"])
@pytest.mark.parametrize("policy", ["standard", "clauses"])
@pytest.mark.parametrize("report", [
    "no_text_difference", "reported_changes", "unreported_text_difference",
])
def test_edited_retained_draft_invalidates_only_its_exact_comparison(
    style, method, policy, report,
):
    original = _checked(style=style, policy=policy, report=report)
    original_before = copy.deepcopy(original.to_dict())
    edited = _edit_retained_draft(original, method)
    before = copy.deepcopy(edited.to_dict())
    assert edited.text == edited.data["translation"] == _ENGLISH
    assert edited.draft.text != edited.data["draft_text"]
    notes = edited._translation_notes()
    assert _COMPARISON_WARNING in notes
    assert _WARNING not in notes
    assert "[Exact text comparison:" not in notes
    if policy == "clauses":
        assert "[Clause check: aligned;" in notes
        assert "Historical clause check" not in notes
    for rendered in (edited.labeled(), edited._repr_html_()):
        assert _COMPARISON_WARNING in rendered
        assert "[Exact text comparison:" not in rendered
    trace = edited.trace()
    assert _COMPARISON_WARNING in trace
    assert "historical translation audit for the stored response" not in trace
    assert original.to_dict() == original_before
    assert edited.to_dict() == before
    restored = ExploratoryResult.from_dict(json.loads(edited.to_json()))
    assert restored.to_dict() == before
    assert _COMPARISON_WARNING in restored.labeled()


@pytest.mark.parametrize("method", ["replace", "saved_json"])
def test_new_check_uses_an_agreeing_draft_snapshot_after_a_retained_draft_edit(method):
    edited = _edit_retained_draft(_checked(), method)
    before = copy.deepcopy(edited.to_dict())
    client = _Client(_response(clauses=True))
    checked = ai.verify_translation(_SOURCE, edited, check_policy="clauses", client=client)
    assert len(client.calls) == 1
    assert checked.draft is edited
    assert checked.draft.text == checked.data["draft_text"] == _ENGLISH
    assert checked.data["change_report_status"] == "no_text_difference"
    assert "[Exact text comparison: final translation text is identical" in checked.labeled()
    assert "[Clause check: aligned;" in checked.labeled()
    assert _COMPARISON_WARNING not in checked.labeled()
    assert _WARNING not in checked.labeled()
    assert edited.to_dict() == before


@pytest.mark.parametrize("stored_translation", [None, False, 4, [], {}])
def test_malformed_saved_translation_cannot_claim_current_clause_alignment(stored_translation):
    saved = json.loads(_checked().to_json())
    saved["data"]["translation"] = stored_translation
    restored = ExploratoryResult.from_dict(saved)
    before = copy.deepcopy(restored.to_dict())
    for rendered in (restored.labeled(), restored._repr_html_(), restored.trace()):
        assert _WARNING in rendered
        assert "[Clause check: aligned" not in rendered
        assert "[Exact text comparison:" not in rendered
    assert restored.to_dict() == before


def test_edited_html_escapes_current_wording_and_retained_notes():
    unsafe = "<script>edited wording</script>"
    checked = _checked()
    revised = replace(checked, text=unsafe)
    html = revised._repr_html_()
    assert "<script>" not in html
    assert "&lt;script&gt;edited wording&lt;/script&gt;" in html
    assert _WARNING in html


@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_repeated_check_displays_earlier_uncertainty_after_json_roundtrip(style):
    client = _Client(_response(uncertainties=[_ORIGINAL_NOTE]), _response(), _response())
    original = ai.translate(_SOURCE, style=style, client=client)
    checked = ai.verify_translation(_SOURCE, original, style=style, client=client)
    restored = ExploratoryResult.from_dict(json.loads(checked.to_json()))
    before = copy.deepcopy(restored.to_dict())
    rechecked = ai.verify_translation(_SOURCE, restored, style=style, client=client)
    assert len(client.calls) == 3
    assert rechecked.data["uncertainties"] == []
    for rendered in (rechecked.labeled(), rechecked._repr_html_()):
        assert "Retained earlier draft (2 steps back): 1 original uncertainty note(s)" in rendered
        assert "their omission from the final notes does not establish resolution" in rendered
        assert (_ORIGINAL_NOTE in rendered) is (style == "annotated")
    assert _ORIGINAL_NOTE in rechecked.trace()
    assert restored.to_dict() == before
    assert rechecked.draft.draft.to_dict() == original.to_dict()


@pytest.mark.parametrize("style", ["annotated", "concise"])
def test_unstructured_ancestor_notes_stay_unavailable_and_raw_response_is_preserved(style):
    raw = "Unstructured response with an uncertain second action."
    client = _Client(raw, _response(), _response())
    original = ai.translate(_SOURCE, style=style, client=client)
    checked = ai.verify_translation(_SOURCE, original, style=style, client=client)
    rechecked = ai.verify_translation(_SOURCE, checked, style=style, client=client)
    for rendered in (rechecked.labeled(), rechecked._repr_html_()):
        assert "Retained earlier draft (2 steps back): separate uncertainty notes unavailable" in rendered
        assert "the original response is retained in trace and JSON" in rendered
    assert raw in rechecked.trace()
    assert rechecked.draft.draft.data["uncertainties"] is None
    assert rechecked.draft.draft.data["raw_response"] == raw


@pytest.mark.parametrize("style", ["annotated", "concise"])
@pytest.mark.parametrize("raw_draft", ["", "Raw draft.\nUncertainty: <script>possible other sense</script>"])
def test_terminal_string_draft_retains_exact_text_without_inventing_separate_notes(
    style, raw_draft,
):
    client = _Client(_response(), _response())
    first = ai.verify_translation(_SOURCE, raw_draft, style=style, client=client)
    assert first.draft is None
    assert first.data["draft_text"] == raw_draft
    restored = ExploratoryResult.from_dict(json.loads(first.to_json()))
    before = copy.deepcopy(restored.to_dict())
    checked = ai.verify_translation(_SOURCE, restored, style=style, client=client)
    assert len(client.calls) == 2
    for rendered in (checked.labeled(), checked._repr_html_()):
        assert "Retained original string draft (2 steps back): separate uncertainty notes unavailable" in rendered
        assert "exact wording is retained in trace and JSON; provenance was not supplied" in rendered
        assert "<script>" not in rendered
    assert checked.data["uncertainties"] == []
    assert checked.draft.data["draft_text"] == raw_draft
    assert restored.to_dict() == before
    final = ExploratoryResult.from_dict(json.loads(checked.to_json()))
    assert "draft_text" in final.draft.data
    assert final.draft.data["draft_text"] == raw_draft
