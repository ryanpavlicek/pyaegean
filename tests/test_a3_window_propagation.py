"""A3 windowed-mode propagation through public analysis and grounding journeys."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import aegean
from aegean import translate
from aegean.ai.client import LLMClient, LLMResponse
from aegean.core.model import Document, Token, TokenKind
from aegean.greek import GreekPipeline, GreekPipelineConfig, LemmaSource, joint
from aegean.greek.annotate import annotate_corpus
from aegean.greek.joint import SentenceAnalysis
from aegean.greek.pipeline import TokenRecord


class _RecordingModel:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.failure = failure

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
    ) -> SentenceAnalysis:
        del with_probs
        self.calls.append(long_input)
        if self.failure is not None:
            raise self.failure
        n = len(words)
        return SentenceAnalysis(
            tokens=tuple(words),
            upos=("NOUN",) * n,
            xpos=("n-s---mn-",) * n,
            feats=("Case=Nom|Gender=Masc|Number=Sing",) * n,
            head=(0,) + tuple(range(1, n)),
            deprel=("root",) + ("dep",) * max(0, n - 1),
            lemma=tuple(word.lower() for word in words),
            lemma_resolved=(True,) * n,
            lemma_source=(LemmaSource.NEURAL_EDIT,) * n,
            lemma_verified=(False,) * n,
            analyzed=(True,) * n,
            complete=True,
            truncated=False,
            warnings=("windowed test analysis",),
        )


def test_pipeline_cli_and_corpus_annotation_forward_windowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean import greek
    from aegean.cli import _build_app

    model = _RecordingModel()
    monkeypatch.setattr(joint, "_ACTIVE", model)

    records = greek.pipeline("Λόγος", long_input="windowed")
    assert model.calls == ["windowed"]
    assert records[0].analysis_complete is True
    assert records[0].analysis_warning == "windowed test analysis"

    result = CliRunner().invoke(
        _build_app(), ["greek", "pipeline", "Λόγος", "--windowed", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)[0]["analysis_complete"] is True
    assert model.calls[-1] == "windowed"

    corpus = aegean.Corpus(
        [
            Document(
                id="d",
                script_id="greek",
                tokens=[Token("Λόγος", TokenKind.WORD, line_no=0, position=0)],
                lines=[[0]],
            )
        ],
        script_id="greek",
    )
    annotated = annotate_corpus(corpus, long_input="windowed")
    assert annotated.documents[0].tokens[0].annotations["lemma"] == "λόγος"
    assert model.calls[-1] == "windowed"


def test_pipeline_cli_rejects_conflicting_modes_and_surfaces_window_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.cli import _build_app

    runner = CliRunner()
    app = _build_app()
    conflict = runner.invoke(
        app, ["greek", "pipeline", "λόγος", "--partial", "--windowed"]
    )
    assert conflict.exit_code == 1
    assert "mutually exclusive" in conflict.output
    assert "Traceback" not in conflict.output

    monkeypatch.setattr(
        joint,
        "_ACTIVE",
        _RecordingModel(failure=joint.NeuralWindowingError("cannot reconcile safely")),
    )
    refused = runner.invoke(app, ["greek", "pipeline", "λόγος", "--windowed"])
    assert refused.exit_code == 1
    assert "cannot reconcile safely" in refused.output
    assert "Traceback" not in refused.output


def test_non_strict_modes_are_not_silently_ignored_by_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean import greek

    monkeypatch.setattr(joint, "_ACTIVE", None)
    with pytest.raises(ValueError, match="requires an active neural"):
        greek.pipeline("λόγος", long_input="windowed")
    with pytest.raises(ValueError, match="requires the active neural"):
        annotate_corpus(
            aegean.Corpus(
                [
                    Document(
                        id="d",
                        script_id="greek",
                        tokens=[Token("λόγος", TokenKind.WORD, line_no=0, position=0)],
                        lines=[[0]],
                    )
                ],
                script_id="greek",
            ),
            long_input="partial",
        )
    with pytest.raises(ValueError, match="requires a neural Greek pipeline"):
        translate.grounding_for(
            "λόγος",
            "greek",
            mode="lemma",
            greek_pipeline=GreekPipeline(),
            greek_long_input="windowed",
        )


class _GroundingPipeline(GreekPipeline):
    __slots__ = ("calls",)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[bool, str]] = []
        self._backend = object()
        self._config = GreekPipelineConfig(
            schema_version=1,
            backend="neural",
            model_id="fake-window-model",
            dataset="fake-window-data",
            bundle_manifest_sha256="0" * 64,
            tokenizer_revision="fake-tokenizer",
            annotation_profile="test",
            normalization="NFC",
            segmentation="pretokenized",
            preprocessing_version="test",
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
        del with_confidence
        self.calls.append((parse, long_input))
        return [
            TokenRecord(
                sentence=0,
                index=1,
                text=text,
                upos="NOUN",
                lemma="λόγος",
                lemma_source=LemmaSource.SEED,
                head=0,
                relation="root",
                feats="Case=Nom|Gender=Masc|Number=Sing",
            )
        ]


class _LocalClient(LLMClient):
    provider = "test"

    def __init__(self) -> None:
        super().__init__("test-model")

    def _complete(
        self, *, prompt: str, system: str | None, max_tokens: int
    ) -> LLMResponse:
        del prompt, system, max_tokens
        return LLMResponse("translation", self.provider, self.model)


def test_translation_grounding_forwards_and_records_windowed_without_provider_io() -> None:
    pipeline = _GroundingPipeline()
    items = translate.grounding_for(
        "λόγος",
        "greek",
        mode="lemma",
        greek_pipeline=pipeline,
        greek_long_input="windowed",
    )
    assert items[0].content == "λόγος → lemma λόγος"
    assert pipeline.calls == [(False, "windowed")]

    result = translate.translate(
        "λόγος",
        mode="lemma",
        greek_pipeline=pipeline,
        greek_long_input="windowed",
        client=_LocalClient(),
    )
    assert result.grounding_runtime is not None
    assert result.grounding_runtime["long_input"] == "windowed"
    assert pipeline.calls[-1] == (False, "windowed")


def test_translation_cli_validates_and_forwards_greek_long_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.cli import _ai, _build_app

    seen: dict[str, object] = {}

    def fake_translate(text: str, **kwargs: object) -> SimpleNamespace:
        del text
        seen.update(kwargs)
        return SimpleNamespace(
            text="ok", provider="test", model="test-model", grounding=(), labeled=lambda: "ok"
        )

    monkeypatch.setattr(_ai, "_client", lambda provider, model: object())
    monkeypatch.setattr(translate, "translate", fake_translate)
    runner = CliRunner()
    app = _build_app()

    ok = runner.invoke(
        app, ["ai", "translate", "λόγος", "--greek-long-input", "windowed"]
    )
    assert ok.exit_code == 0, ok.output
    assert seen["greek_long_input"] == "windowed"

    bad = runner.invoke(
        app, ["ai", "translate", "λόγος", "--greek-long-input", "guess"]
    )
    assert bad.exit_code == 1
    assert "strict, partial, or windowed" in bad.output
