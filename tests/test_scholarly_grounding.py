"""Payload/provenance contracts; canned completions do not evaluate translation quality."""

from __future__ import annotations

import json
import warnings
from dataclasses import replace

import pytest

from aegean import ai, translate
from aegean.ai.client import ExploratoryResult, LLMClient, LLMResponse
from aegean.core.model import ReadingStatus, Token, TokenKind
from aegean.greek import GreekPipeline
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import TokenRecord


class RecordingClient(LLMClient):
    provider = "recording"

    def __init__(self) -> None:
        super().__init__("deterministic-test")
        self.requests: list[tuple[str | None, str]] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.requests.append((system, prompt))
        return LLMResponse("canned completion", self.provider, self.model)


def test_all_evidence_statuses_reach_model_trace_and_json() -> None:
    items = [
        ai.GroundingItem("ἀκούει = ἀκούω (verb)", "analysis:morphology", "1:5", "predicted",
                         {"lemma_source": "neural_edit", "fields": ["lemma", "upos"]}),
        ai.GroundingItem("λόγος: source lemma", "edition:Nestle1904", "John.1.1", "source-annotated"),
        ai.GroundingItem("λόγος: lemma accepted", "review", "John.1.1", "human-reviewed",
                         {"field": "lemma", "reviewed_by": "reviewer A", "review_decision": "accept"}),
        "legacy custom evidence",
    ]
    client = RecordingClient()
    result = ai.translate("λόγος ἀκούει", grounding=(item for item in items), client=client)
    system, prompt = client.requests[0]
    assert system is not None and "may be wrong" in system and "stated field" in system
    for item in result.grounding:
        assert item.render() in prompt
        assert item.render() in result.trace()
        assert prompt.index("<<<EVIDENCE") < prompt.index(item.render()) < prompt.index("EVIDENCE>>>")
    assert result.grounding[-1].status == "unclassified"
    assert ExploratoryResult.from_dict(json.loads(result.to_json())) == result
    assert result.provenance()["grounding"][2]["provenance"]["field"] == "lemma"


def test_legacy_grounding_artifact_stays_unclassified() -> None:
    restored = ExploratoryResult.from_dict({
        "text": "old", "grounding": [{"content": "old analysis", "source": "lemmatizer", "ref": "word"}],
    })
    assert restored.grounding[0].status == "unclassified"
    assert restored.grounding[0].provenance is None
    with pytest.raises(ValueError, match="provenance must be an object"):
        ai.GroundingItem.from_dict({"content": "x", "provenance": []})


def test_annotation_evidence_does_not_extend_lemma_review_to_pos_or_source_morphology() -> None:
    token = Token("λόγος", TokenKind.WORD, position=0, annotations={
        "lemma": "λόγος", "upos": "NOUN", "morph": "N-NSM", "lemma_source": "neural_lookup",
        "lemma_review_decision": "accept", "lemma_verified": "true", "lemma_reviewed_by": "classicist",
        "lemma_review_note": "checked source", "lemma_review_evidence": "edition p. 1",
        "lemma__pred": "λόγος", "ref": "John.1.1", "review_status": "verified",
    })
    items = ai.annotation_evidence([token], source="edition:Nestle1904", source_annotated=True)
    assert {item.provenance["field"]: item.status for item in items} == {
        "lemma": "human-reviewed", "upos": "predicted", "morph": "source-annotated",
    }
    lemma = items[0]
    assert lemma.provenance["reviewed_by"] == "classicist"
    assert lemma.provenance["original_prediction"] == "λόγος"
    assert lemma.provenance["position"] == 0
    client = RecordingClient()
    result = translate.translate("λόγος", mode="none", grounding=iter(items), client=client)
    assert result.grounding == tuple(items)
    assert "classicist" in client.requests[0][1]
    assert '"field": "morph"' in client.requests[0][1]


@pytest.mark.parametrize("decision", ["defer", "reject", "stale", ""])
def test_unapproved_or_stale_decisions_never_claim_human_review(decision: str) -> None:
    token = Token("λόγος", TokenKind.WORD, annotations={
        "lemma": "λόγος", "lemma_source": "neural", "lemma_review_decision": decision,
        "lemma_verified": "true", "lemma_reviewed_by": "old reviewer",
    })
    item = ai.annotation_evidence([token])[0]
    assert item.status == "predicted"
    if decision:
        assert item.provenance["review_decision"] == decision
        assert decision in item.render()


def test_source_uncertainty_and_missing_origin_remain_visible() -> None:
    token = Token("λόγος", TokenKind.WORD, status=ReadingStatus.UNCLEAR,
                  alt=("βίος",), annotations={"lemma": "λόγος"})
    unknown = ai.annotation_evidence([token])[0]
    source = ai.annotation_evidence([token], source="edition:fixture", source_annotated=True)[0]
    assert unknown.status == "unclassified"
    assert source.status == "source-annotated"
    assert source.provenance["reading_status"] == "unclear"
    assert source.provenance["alternative_readings"] == ["βίος"]


def test_edition_metadata_is_not_mistaken_for_prediction_provenance() -> None:
    token = Token("λόγος", TokenKind.WORD, annotations={
        "morph": "N-NSM", "morph_source": "Nestle1904 edition",
    })
    item = ai.annotation_evidence([token], source="edition:Nestle1904", source_annotated=True)[0]
    assert item.status == "source-annotated"
    assert item.provenance["source"] == "Nestle1904 edition"


def test_baseline_grounding_reports_missing_stages_without_activating_neural() -> None:
    pipeline = GreekPipeline()
    client = RecordingClient()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = translate.translate("ὁ παῖς τὸν λόγον ἀκούει.", greek_pipeline=pipeline, client=client)
    runtime = result.grounding_runtime
    assert runtime["pipeline"]["backend"] == "baseline"
    assert runtime["required_stages"] == ["morphology", "dependencies"]
    assert runtime["missing_stages"] == ["morphological features", "dependencies"]
    assert runtime["coverage"]["tokens"] == 5
    assert runtime["coverage"]["analyzed_tokens"] == 5
    assert runtime["coverage"]["feature_tokens"] == runtime["coverage"]["dependency_tokens"] == 0
    assert runtime["degraded"] is True
    assert pipeline.config.backend == "baseline" and not pipeline.neural_active
    prompt = client.requests[0][1]
    assert "Greek analysis backend: baseline (explicit)" in prompt
    assert "missing stages: morphological features, dependencies" in prompt
    assert '"status": "predicted"' in prompt
    assert "provisional" in prompt
    assert "baseline" in result.labeled() and "degraded" in result.labeled()
    assert any("degraded" in str(warning.message) for warning in caught)
    assert "5/5 tokens analyzed" in result.trace()
    strict_client = RecordingClient()
    with pytest.raises(translate.GroundingError):
        translate.translate("λόγος", greek_pipeline=pipeline, grounding_failure="strict", client=strict_client)
    assert strict_client.requests == []


class SilentUnparsedPipeline(GreekPipeline):
    def analyze(self, text: str, *, parse: bool = False, with_confidence: bool = False,
                long_input: str = "strict") -> list[TokenRecord]:
        return [TokenRecord(0, 1, "λόγος", "NOUN", "λόγος", LemmaSource.NEURAL)]


def test_strict_policy_rejects_silently_missing_required_dependency_fields() -> None:
    with pytest.raises(translate.GroundingError, match="dependency analysis"):
        translate.grounding_for("λόγος", "greek", greek_pipeline=SilentUnparsedPipeline(),
                                grounding_failure="strict")


def test_partial_placeholder_is_not_presented_as_morphology() -> None:
    class PartialPipeline(SilentUnparsedPipeline):
        def analyze(self, text: str, **kwargs: object) -> list[TokenRecord]:
            return [replace(super().analyze(text)[0], neural_analyzed=False, analysis_complete=False)]

    items = translate.grounding_for("λόγος", "greek", greek_pipeline=PartialPipeline())
    assert not any(item.source in {"analysis:morphology", "analysis:syntax"} for item in items)
    assert "coverage: 0/1" in items[0].content
    assert "complete analysis coverage" in items[0].content


def test_verifier_receives_scoped_provenance_and_remains_exploratory() -> None:
    client = RecordingClient()
    source_item = ai.GroundingItem("ambiguous lemma", "edition:fixture", "1", "source-annotated")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = translate.translate("λόγος", verify=True, grounding=[source_item], client=client)
    assert len(client.requests) == 2
    assert "ambiguous lemma" not in client.requests[0][1]
    assert source_item.render() in client.requests[1][1]
    assert "not independent scholarly verification" in client.requests[1][1]
    assert result.exploratory is True


def test_clause_skeleton_keeps_dependents_in_their_own_sentence() -> None:
    # Both sentences reuse UD token indexes; a subject in one must not replace
    # the other's subject or add a copula to an unrelated predicate.
    records = [
        TokenRecord(0, 1, "παῖς", "NOUN", "παῖς", LemmaSource.NEURAL, 2, "nsubj"),
        TokenRecord(0, 2, "ἀκούει", "VERB", "ἀκούω", LemmaSource.NEURAL, 0, "root"),
        TokenRecord(1, 1, "θεός", "NOUN", "θεός", LemmaSource.NEURAL, 2, "nsubj"),
        TokenRecord(1, 2, "ἀγαθός", "ADJ", "ἀγαθός", LemmaSource.NEURAL, 0, "root"),
        TokenRecord(1, 3, "ἐστιν", "AUX", "εἰμί", LemmaSource.NEURAL, 2, "cop"),
    ]
    skeleton = translate._clause_skeleton(records)
    first, second = skeleton.split(" | ")
    assert first == "main predicate 'ἀκούει' (ἀκούω); subject παῖς"
    assert second == "predicate ἐστιν + ἀγαθός (predicate adjective); subject θεός"
