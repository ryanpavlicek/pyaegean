"""Instance ownership and compatibility tests for the Greek pipeline runtime."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from aegean.greek import joint
from aegean.greek.joint import SentenceAnalysis
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import pipeline
from aegean.greek.runtime import (
    GreekPipeline,
    GreekPipelineConfig,
    _set_default_pipeline,
    default_pipeline,
)


def _config(*, provider: str = "CPUExecutionProvider") -> GreekPipelineConfig:
    return GreekPipelineConfig(
        schema_version=1,
        backend="neural",
        model_id="test-model",
        dataset="test-dataset",
        bundle_manifest_sha256="a" * 64,
        tokenizer_revision="b" * 64,
        annotation_profile="test-profile",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="test-preprocessing-v1",
        execution_providers=(provider,),
    )


class _Backend:
    """Small backend seam with a deterministic identity distinct per instance."""

    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.manifest = SimpleNamespace(
            model_id="test-model",
            dataset="test-dataset",
            manifest_sha256="a" * 64,
            tokenizer_revision="b" * 64,
            annotation_profile="test-profile",
            normalization="NFC",
            segmentation="pretokenized",
            preprocessing_version="test-preprocessing-v1",
        )
        self._sess = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
    ) -> SentenceAnalysis:
        del with_probs, long_input
        n = len(words)
        return SentenceAnalysis(
            tokens=tuple(words),
            upos=("NOUN",) * n,
            xpos=("n-s---nom".ljust(9, "-"),) * n,
            feats=("_",) * n,
            head=(0,) * n,
            deprel=("root",) * n,
            lemma=tuple(f"{self.marker}:{word}" for word in words),
            lemma_resolved=(True,) * n,
            lemma_source=(LemmaSource.NEURAL_EDIT,) * n,
            lemma_verified=(False,) * n,
            analyzed=(True,) * n,
        )


def _instance(marker: str) -> GreekPipeline:
    return GreekPipeline._from_backend(_Backend(marker), config=_config())


def test_config_is_frozen_and_canonical_round_trip() -> None:
    config = _config()
    assert GreekPipelineConfig.from_json(config.to_json()) == config
    assert config.to_dict()["execution_providers"] == ["CPUExecutionProvider"]
    with pytest.raises(FrozenInstanceError):
        config.backend = "baseline"  # type: ignore[misc]


def test_config_rejects_unknown_schema_and_malformed_keys() -> None:
    raw = _config().to_dict()
    raw["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported.*schema"):
        GreekPipelineConfig.from_dict(raw)
    raw = _config().to_dict()
    raw["unexpected"] = True
    with pytest.raises(ValueError, match="invalid.*keys"):
        GreekPipelineConfig.from_dict(raw)
    with pytest.raises(TypeError, match="GreekPipelineConfig"):
        GreekPipeline.from_config(raw)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="invalid.*JSON"):
        GreekPipelineConfig.from_json("{not-json")
    with pytest.raises(ValueError, match="expected an object"):
        GreekPipelineConfig.from_json("[]")
    raw = _config().to_dict()
    raw["execution_providers"] = [""]
    with pytest.raises(ValueError, match="execution_providers"):
        GreekPipelineConfig.from_dict(raw)


def test_from_config_recreates_exact_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _Backend("same")
    monkeypatch.setattr(joint, "_load_neural_backend", lambda **_: backend)
    config = _config()
    recreated = GreekPipeline.from_config(config)
    assert recreated.config == config
    assert recreated._backend is backend  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="configuration mismatch"):
        GreekPipeline.from_config(replace(config, annotation_profile="other"))


def test_saved_config_recreates_analyzing_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _Backend("restored")
    monkeypatch.setattr(joint, "_load_neural_backend", lambda **_: backend)
    path = tmp_path / "greek-pipeline.json"
    path.write_text(_config().to_json(), encoding="utf-8")

    restored_config = GreekPipelineConfig.from_json(path.read_text(encoding="utf-8"))
    restored = GreekPipeline.from_config(restored_config)

    assert restored.analyze("λόγος")[0].lemma == "restored:λόγος"
    assert restored.config.to_json() == path.read_text(encoding="utf-8")


def test_neural_instance_does_not_replace_default(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _Backend("isolated")
    monkeypatch.setattr(joint, "_load_neural_backend", lambda **_: backend)
    before = default_pipeline()
    instance = GreekPipeline.neural()
    assert instance is not before
    assert default_pipeline() is before


def test_explicit_baseline_stays_baseline_when_facade_is_neural(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", joint._UNSET)
    before = default_pipeline()
    try:
        _set_default_pipeline(_instance("facade"))
        explicit = GreekPipeline()
        assert explicit.config.backend == "baseline"
        assert pipeline("λόγος")[0].lemma == "facade:λόγος"
        assert not explicit.analyze("λόγος")[0].lemma.startswith("facade:")
    finally:
        _set_default_pipeline(before)


def test_concurrent_instances_keep_backend_identity() -> None:
    left = _instance("left")
    right = _instance("right")

    def run(instance: GreekPipeline) -> list[str]:
        return [instance.analyze("λόγος")[0].lemma for _ in range(12)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        left_result, right_result = pool.map(run, (left, right))
    assert set(left_result) == {"left:λόγος"}
    assert set(right_result) == {"right:λόγος"}


def test_explicit_instance_wins_over_legacy_active_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", _Backend("legacy"))
    explicit = _instance("explicit")
    assert explicit.analyze("λόγος")[0].lemma == "explicit:λόγος"


def test_explicit_baseline_does_not_borrow_legacy_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A baseline instance remains the built-in cascade, even if all globals are populated."""
    from aegean.greek import lemmatizer, neural_lemmatizer, paradigms, syntax, tagger, treebank

    class FakeTreebank:
        def lemmatize(self, word: str) -> str:
            return "TREEBANK-LEAK"

        def pos(self, word: str) -> str:
            return "TREEBANK-LEAK"

    class FakeTagger:
        def tag_pos(self, forms: list[str]) -> list[str]:
            return ["TAGGER-LEAK"] * len(forms)

    class FakeLemmatizer:
        def predict(self, word: str) -> str:
            return "LEMMATIZER-LEAK"

    class FakeParadigms:
        def lemma_options(self, word: str) -> list[str]:
            return ["PARADIGM-LEAK"]

        def lemmatize(self, word: str) -> str:
            return "PARADIGM-LEAK"

    monkeypatch.setattr(treebank, "_ACTIVE", FakeTreebank())
    monkeypatch.setattr(tagger, "_ACTIVE", FakeTagger())
    monkeypatch.setattr(lemmatizer, "_ACTIVE", FakeLemmatizer())
    monkeypatch.setattr(neural_lemmatizer, "_ACTIVE", FakeLemmatizer())
    monkeypatch.setattr(paradigms, "_ACTIVE", FakeParadigms())
    monkeypatch.setattr(syntax, "_ACTIVE", {"weights": {}, "relations": {}})

    explicit = GreekPipeline()
    records = explicit.analyze("ἦν λόγος")
    assert explicit.config.backend == "baseline"
    assert all("LEAK" not in record.lemma and "LEAK" not in record.upos for record in records)
    with pytest.raises(syntax.ParserNotLoadedError):
        explicit.analyze("ἦν λόγος", parse=True)


def test_default_facade_still_uses_legacy_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    """The compatibility facade keeps its historical global cascade."""
    from aegean.greek import treebank

    class FakeTreebank:
        def lemmatize(self, word: str) -> str:
            return "FACADE-LEMMA"

        def pos(self, word: str) -> str:
            return "FACADE-POS"

    monkeypatch.setattr(joint, "_ACTIVE", joint._UNSET)
    monkeypatch.setattr(treebank, "_ACTIVE", FakeTreebank())
    records = pipeline("λόγος")
    assert records[0].lemma == "FACADE-LEMMA"
    assert records[0].upos == "FACADE-POS"
