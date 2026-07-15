"""Explicit Greek translation-pipeline selection, failures, and provenance."""

from __future__ import annotations

import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest
from click import unstyle
from typer.testing import CliRunner

from aegean import translate
from aegean.ai.client import LLMClient, LLMResponse
from aegean.greek import GreekPipeline, GreekPipelineConfig
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import TokenRecord


class _CapturingClient(LLMClient):
    provider = "capture"

    def __init__(self) -> None:
        super().__init__("capture-1")
        self.prompts: list[str] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.prompts.append(prompt)
        return LLMResponse(f"answer {len(self.prompts)}", self.provider, self.model)


def _record(surface: str, lemma: str) -> TokenRecord:
    return TokenRecord(
        sentence=0,
        index=1,
        text=surface,
        upos="NOUN",
        lemma=lemma,
        lemma_source=LemmaSource.SEED,
        head=0,
        relation="root",
        feats="Case=Nom|Number=Sing",
    )


class _StubPipeline(GreekPipeline):
    __slots__ = ("calls", "records", "raised")

    def __init__(
        self,
        records: list[TokenRecord],
        *,
        raised: Exception | None = None,
        neural: bool = False,
    ) -> None:
        super().__init__()
        self.records = records
        self.raised = raised
        self.calls: list[bool] = []
        if neural:
            self._backend = object()
            self._config = GreekPipelineConfig(
                schema_version=2,
                backend="neural",
                model_id="test-joint",
                dataset="test-data",
                runtime_variant="default",
                variant_registry_sha256="9" * 64,
                variant_award_sha256="8" * 64,
                qualification_sha256="7" * 64,
                bundle_manifest_sha256="a" * 64,
                tokenizer_revision="test-tokenizer",
                annotation_profile="test-ud",
                normalization="NFC",
                segmentation="test-segmentation",
                preprocessing_version="test-preprocessing",
                execution_providers=("CPUExecutionProvider",),
            )

    def analyze(
        self,
        text: str,
        *,
        parse: bool = False,
        with_confidence: bool = False,
        long_input: str = "strict",
    ) -> list[TokenRecord]:
        self.calls.append(parse)
        if self.raised is not None:
            raise self.raised
        return list(self.records)


def test_explicit_pipeline_owns_grounding_and_runtime_not_prompt() -> None:
    pipeline = _StubPipeline([_record("λόγος", "explicit-lemma")], neural=True)
    client = _CapturingClient()

    result = translate.translate(
        "λόγος", greek_pipeline=pipeline, client=client
    )

    assert any("explicit-lemma" in item.content for item in result.grounding)
    assert pipeline.calls == [True]
    assert result.grounding_runtime is not None
    runtime_pipeline = result.grounding_runtime["pipeline"]
    assert runtime_pipeline["selection"] == "explicit"
    assert runtime_pipeline["backend"] == "neural"
    assert runtime_pipeline["config"]["model_id"] == "test-joint"
    assert "Greek pipeline: explicit (neural)" in result.trace()
    # Runtime provenance is attached after completion and never becomes prompt evidence.
    assert "test-joint" not in client.prompts[0]
    assert "failure_policy" not in client.prompts[0]
    assert "schema_version" not in client.prompts[0]


def test_explicit_pipeline_isolation_survives_concurrent_translation() -> None:
    first = _StubPipeline([_record("λόγος", "first-lemma")], neural=True)
    second = _StubPipeline([_record("λόγος", "second-lemma")], neural=True)

    def run(pipeline: _StubPipeline) -> tuple[str, str]:
        client = _CapturingClient()
        result = translate.translate("λόγος", greek_pipeline=pipeline, client=client)
        return client.prompts[0], result.grounding[0].content

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = pool.map(run, (first, second))

    assert "first-lemma" in left[0] and "first-lemma" in left[1]
    assert "second-lemma" in right[0] and "second-lemma" in right[1]
    assert "second-lemma" not in left[0]
    assert "first-lemma" not in right[0]


def test_best_effort_records_failure_but_strict_prevents_provider_call() -> None:
    pipeline = _StubPipeline([], raised=RuntimeError("local diagnostic detail"), neural=True)
    best_effort_client = _CapturingClient()
    result = translate.translate(
        "λόγος",
        greek_pipeline=pipeline,
        grounding_failure="best-effort",
        client=best_effort_client,
    )
    assert len(best_effort_client.prompts) == 1
    assert result.grounding_runtime is not None
    failures = result.grounding_runtime["failures"]
    assert failures == [
        {"stage": "morphology and dependency analysis", "error_type": "RuntimeError"},
        {"stage": "morphology fallback analysis", "error_type": "RuntimeError"},
    ]
    assert "local diagnostic detail" not in json.dumps(result.to_dict())

    strict_client = _CapturingClient()
    with pytest.raises(translate.GroundingError) as caught:
        translate.translate(
            "λόγος",
            greek_pipeline=pipeline,
            grounding_failure="strict",
            client=strict_client,
        )
    assert caught.value.stage == "morphology and dependency analysis"
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert strict_client.prompts == []
    with pytest.raises(translate.GroundingError):
        translate.grounding_for(
            "λόγος",
            "greek",
            greek_pipeline=pipeline,
            grounding_failure="strict",
        )


def test_strict_verify_preflights_grounding_before_raw_draft() -> None:
    pipeline = _StubPipeline([], raised=RuntimeError("boom"), neural=True)
    client = _CapturingClient()
    with pytest.raises(translate.GroundingError):
        translate.translate(
            "λόγος",
            verify=True,
            greek_pipeline=pipeline,
            grounding_failure="strict",
            client=client,
        )
    assert client.prompts == []


def test_incomplete_analysis_is_traced_or_rejected_by_policy() -> None:
    incomplete = replace(
        _record("λόγος", "partial-lemma"),
        neural_analyzed=False,
        analysis_complete=False,
        analysis_warning="partial placeholder",
    )
    pipeline = _StubPipeline([incomplete], neural=True)
    result = translate.translate(
        "λόγος", greek_pipeline=pipeline, client=_CapturingClient()
    )
    assert result.grounding_runtime is not None
    assert result.grounding_runtime["failures"] == [
        {"stage": "analysis coverage", "error_type": "IncompleteAnalysis"}
    ]

    client = _CapturingClient()
    with pytest.raises(translate.GroundingError, match="analysis coverage"):
        translate.translate(
            "λόγος",
            greek_pipeline=pipeline,
            grounding_failure="strict",
            client=client,
        )
    assert client.prompts == []


def test_none_mode_does_not_run_selected_pipeline_or_warn() -> None:
    pipeline = _StubPipeline([], raised=AssertionError("must not analyze"))
    client = _CapturingClient()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = translate.translate(
            "λόγος", mode="none", greek_pipeline=pipeline, client=client
        )
    assert pipeline.calls == []
    assert result.grounding == ()
    assert result.grounding_runtime is not None
    assert result.grounding_runtime["mode"] == "none"
    assert not caught


def test_explicit_pipeline_validation_and_lemma_mode() -> None:
    pipeline = _StubPipeline([_record("λόγος", "chosen-lemma")], neural=True)
    items = translate.grounding_for(
        "λόγος", "greek", mode="lemma", greek_pipeline=pipeline
    )
    assert [item.content for item in items] == ["λόγος → lemma chosen-lemma"]
    assert pipeline.calls == [False]

    with pytest.raises(ValueError, match="only valid when script='greek'"):
        translate.grounding_for("KU-RO", "lineara", greek_pipeline=pipeline)
    with pytest.raises(ValueError, match="valid policies"):
        translate.grounding_for("λόγος", "greek", grounding_failure="quiet")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="GreekPipeline"):
        translate.grounding_for("λόγος", "greek", greek_pipeline=object())  # type: ignore[arg-type]


def test_translation_runtime_metadata_round_trips() -> None:
    pipeline = _StubPipeline([_record("λόγος", "chosen-lemma")], neural=True)
    result = translate.translate("λόγος", greek_pipeline=pipeline, client=_CapturingClient())
    restored = type(result).from_dict(result.to_dict())
    assert restored == result
    assert restored.grounding_runtime == result.grounding_runtime

    # A schema-1 artifact written before runtime metadata existed still loads.
    legacy_payload = result.to_dict()
    legacy_payload.pop("grounding_runtime")
    legacy = type(result).from_dict(legacy_payload)
    assert legacy.grounding_runtime is None
    assert legacy.text == result.text and legacy.grounding == result.grounding

    malformed = result.to_dict()
    malformed["grounding_runtime"] = []
    with pytest.raises(ValueError, match="grounding_runtime must be an object"):
        type(result).from_dict(malformed)


def test_cli_translation_backend_and_failure_options(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegean.cli import _ai, _build_app

    seen: dict[str, object] = {}

    def fake_translate(text: str, **kwargs: object) -> SimpleNamespace:
        seen.update(kwargs)
        return SimpleNamespace(
            text="ok",
            provider="fake",
            model="fake-1",
            grounding=(),
            labeled=lambda: "ok",
        )

    monkeypatch.setattr(_ai, "_client", lambda provider, model: object())
    monkeypatch.setattr(translate, "translate", fake_translate)
    runner = CliRunner()
    app = _build_app()

    help_result = runner.invoke(app, ["ai", "translate", "--help"])
    assert help_result.exit_code == 0
    # Rich may inject ANSI spans inside an option or wrap at a hyphen depending on
    # terminal/Python version. Assert the rendered help after removing those layout
    # artifacts, not against one terminal's byte sequence.
    compact_help = "".join(unstyle(help_result.output).split())
    assert "--greek-backend" in compact_help
    assert "--greek-variant" in compact_help
    assert "--grounding-failure" in compact_help

    result = runner.invoke(
        app,
        [
            "ai", "translate", "λόγος", "--greek-backend", "baseline",
            "--grounding-failure", "best-effort",
        ],
    )
    assert result.exit_code == 0, result.output
    assert isinstance(seen["greek_pipeline"], GreekPipeline)
    assert seen["grounding_failure"] == "best-effort"

    selected: list[str] = []

    def fake_neural(
        cls: type[GreekPipeline], *, variant: str = "default", **_kwargs: object
    ) -> GreekPipeline:
        selected.append(variant)
        return cls()

    monkeypatch.setattr(GreekPipeline, "neural", classmethod(fake_neural))
    seen.clear()
    neural_result = runner.invoke(
        app,
        [
            "ai", "translate", "λόγος", "--greek-backend", "neural",
            "--greek-variant", "compact",
        ],
    )
    assert neural_result.exit_code == 0, neural_result.output
    assert selected == ["compact"]

    seen.clear()
    default_result = runner.invoke(app, ["ai", "translate", "λόγος"])
    assert default_result.exit_code == 0, default_result.output
    assert seen["greek_pipeline"] is None
    assert seen["grounding_failure"] == "best-effort"


def test_cli_rejects_invalid_grounding_options_before_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.cli import _ai, _build_app

    calls = 0

    def forbidden_client(provider: str, model: str | None) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("client must not be constructed")

    monkeypatch.setattr(_ai, "_client", forbidden_client)
    runner = CliRunner()
    app = _build_app()

    bad_backend = runner.invoke(
        app, ["ai", "translate", "λόγος", "--greek-backend", "magic"]
    )
    bad_failure = runner.invoke(
        app, ["ai", "translate", "λόγος", "--grounding-failure", "quiet"]
    )
    wrong_script = runner.invoke(
        app,
        ["ai", "translate", "KU-RO", "--script", "lineara", "--greek-backend", "neural"],
    )
    orphan_variant = runner.invoke(
        app,
        ["ai", "translate", "λόγος", "--greek-variant", "compact"],
    )

    def unavailable_neural(
        cls: type[GreekPipeline], **_kwargs: object
    ) -> GreekPipeline:
        raise RuntimeError("test asset unavailable")

    monkeypatch.setattr(GreekPipeline, "neural", classmethod(unavailable_neural))
    unavailable = runner.invoke(
        app, ["ai", "translate", "λόγος", "--greek-backend", "neural"]
    )

    assert (
        bad_backend.exit_code
        == bad_failure.exit_code
        == wrong_script.exit_code
        == orphan_variant.exit_code
        == unavailable.exit_code
        == 1
    )
    assert "must be default, baseline, or neural" in bad_backend.output
    assert "must be best-effort or strict" in bad_failure.output
    assert "applies only to --script greek" in wrong_script.output
    assert "requires --greek-backend neural" in orphan_variant.output
    assert "could not activate the neural Greek pipeline" in unavailable.output
    assert calls == 0


def test_cli_surfaces_strict_grounding_error_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.cli import _ai, _build_app

    def strict_failure(text: str, **kwargs: object) -> object:
        raise translate.GroundingError(
            stage="morphology and dependency analysis",
            script="greek",
            backend="neural",
            config=None,
        )

    monkeypatch.setattr(_ai, "_client", lambda provider, model: object())
    monkeypatch.setattr(translate, "translate", strict_failure)
    result = CliRunner().invoke(
        _build_app(),
        ["ai", "translate", "λόγος", "--grounding-failure", "strict"],
    )
    assert result.exit_code == 1
    assert "grounding failed during morphology and dependency analysis" in result.output
    assert "Traceback" not in result.output
