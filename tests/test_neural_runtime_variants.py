"""Public runtime-variant registry, selection, cache, and receipt contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from aegean import greek
from aegean.cli import _build_app
from aegean.greek import joint
from aegean.greek.model_variants import (
    NeuralRuntimeVariant,
    NeuralVariantError,
    NeuralVariantUnavailableError,
    _decode_registry,
    neural_variant,
    neural_variants,
    variant_registry_sha256,
)
from aegean.greek.neural_contract import AnalysisReceipt, ReceiptMismatchError
from aegean.greek.runtime import GreekPipelineConfig


def _variant(
    label: str,
    dataset: str,
    *,
    model_id: str,
    asset: str,
    manifest: str,
) -> NeuralRuntimeVariant:
    return NeuralRuntimeVariant(
        label=label,  # type: ignore[arg-type]
        availability="available",
        model_id=model_id,
        dataset=dataset,
        asset_sha256=asset,
        bundle_manifest_sha256=manifest,
        award_sha256="c" * 64,
        qualification_sha256="d" * 64,
    )


def _manifest() -> SimpleNamespace:
    return SimpleNamespace(
        schema_version=1,
        source_schema_version=1,
        model_id="grc-joint-v3",
        dataset="grc-joint",
        asset_sha256="f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e",
        asset_sha256_enforced=True,
        manifest_sha256="db17b79df0a88d927870a708ecd666f3afdfd5cd890302854cab700b581ade5b",
        tokenizer_revision="a" * 64,
        max_subwords=512,
        annotation_profile="pyaegean-canonical-v1",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="grc-joint-v3",
        special_token_policy="roberta:<s>:0:</s>:2",
    )


def test_registry_reserves_labels_without_claiming_artifacts() -> None:
    records = neural_variants()
    assert [(item.label, item.availability) for item in records] == [
        ("default", "available"),
        ("fast", "reserved"),
        ("compact", "reserved"),
        ("balanced", "reserved"),
    ]
    assert neural_variants(available_only=True) == (records[0],)
    assert neural_variant().model_id == "grc-joint-v3"
    assert len(variant_registry_sha256()) == 64
    assert greek.neural_variant is neural_variant
    assert greek.neural_variants is neural_variants


def test_default_registry_pin_is_the_unchanged_data_asset() -> None:
    from aegean.data import _REMOTE

    default = neural_variant()
    spec = _REMOTE[default.dataset]
    assert default.asset_sha256 == spec.sha256
    assert spec.url.endswith("grc-joint-v3/grc-joint.tar.gz")
    assert default.award_sha256 is None
    assert default.qualification_sha256 is None
    evidence = json.loads(
        (
            __import__("pathlib").Path(__file__).parents[1]
            / "training"
            / "results"
            / "decoder-v2-papygreek-remeasure-2026-07-18.json"
        ).read_text(encoding="utf-8")
    )
    assert default.model_id == evidence["model"]["model_id"]
    assert default.asset_sha256 == evidence["model"]["asset_sha256"]
    assert default.bundle_manifest_sha256 == evidence["model"]["bundle_manifest_sha256"]


def test_registry_rejects_tamper_duplicates_and_cross_artifact_dataset_reuse() -> None:
    path = (
        __import__("pathlib").Path(greek.__file__).parents[1]
        / "data"
        / "bundled"
        / "greek"
        / "neural-runtime-variants.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["variants"][0]["model_id"] = "forged"
    with pytest.raises(NeuralVariantError, match="digest mismatch|immutable"):
        _decode_registry(json.dumps(raw).encode())
    with pytest.raises(NeuralVariantError, match="duplicate"):
        _decode_registry(b'{"format":"a","format":"b"}')

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["variants"][1] = {
        **raw["variants"][0],
        "label": "fast",
        "model_id": "other-model",
        "award_sha256": "c" * 64,
        "qualification_sha256": "d" * 64,
    }
    unsigned = dict(raw)
    unsigned.pop("registry_sha256")
    import hashlib

    raw["registry_sha256"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(NeuralVariantError, match="reused"):
        _decode_registry(json.dumps(raw).encode())


def test_unavailable_variant_fails_before_extra_probe_fetch_or_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []
    monkeypatch.setattr(joint, "_require_neural_extra", lambda: called.append("extra"))
    monkeypatch.setattr(joint, "fetch", lambda *_a, **_k: called.append("fetch"))
    with pytest.raises(NeuralVariantUnavailableError, match="reserved"):
        joint._load_neural_backend(variant="fast")
    assert called == []


def test_default_selection_and_force_target_only_the_selected_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compact = _variant(
        "compact",
        "grc-joint-v4-compact",
        model_id="grc-joint-v4-compact",
        asset="2" * 64,
        manifest="3" * 64,
    )
    default = neural_variant()
    by_label = {"default": default, "compact": compact}
    fetched: list[tuple[str, bool]] = []
    constructed: list[tuple[str, str | None]] = []

    monkeypatch.setattr(joint, "_resolve_neural_variant", by_label.__getitem__)
    monkeypatch.setattr(joint, "_require_neural_extra", lambda: None)
    monkeypatch.setattr(
        joint,
        "versions",
        lambda: {
            "fetched": {
                "grc-joint": {
                    "sha256": default.asset_sha256,
                    "sha256_enforced": True,
                },
                "grc-joint-v4-compact": {
                    "sha256": compact.asset_sha256,
                    "sha256_enforced": True,
                },
            }
        },
    )
    monkeypatch.setattr(
        joint,
        "fetch",
        lambda dataset, *, force=False: (
            fetched.append((dataset, force)) or __import__("pathlib").Path(dataset)
        ),
    )

    class Candidate:
        def __init__(self, selected: NeuralRuntimeVariant) -> None:
            self.runtime_variant = selected

    def construct(path: Any, **kwargs: Any) -> Candidate:
        selected = kwargs["runtime_variant"]
        constructed.append((str(path), selected.label))
        return Candidate(selected)

    monkeypatch.setattr(joint, "_JointModel", construct)
    assert joint._load_neural_backend().runtime_variant is default
    assert joint._load_neural_backend(variant="compact", force=True).runtime_variant is compact
    assert fetched == [("grc-joint", False), ("grc-joint-v4-compact", True)]
    assert constructed == [
        ("grc-joint", "default"),
        ("grc-joint-v4-compact", "compact"),
    ]


def test_runtime_selection_rejects_an_unenforced_data_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = neural_variant()
    monkeypatch.setattr(joint, "_require_neural_extra", lambda: None)
    monkeypatch.setattr(
        joint,
        "versions",
        lambda: {
            "fetched": {
                "grc-joint": {
                    "sha256": selected.asset_sha256,
                    "sha256_enforced": False,
                }
            }
        },
    )
    monkeypatch.setattr(
        joint,
        "fetch",
        lambda *_args, **_kwargs: pytest.fail("an unpinned asset must not be fetched"),
    )
    with pytest.raises(NeuralVariantError, match="exact enforced"):
        joint._load_neural_backend()


def test_config_schema2_binds_variant_and_round_trips() -> None:
    config = GreekPipelineConfig(
        schema_version=2,
        backend="neural",
        model_id="grc-joint-v3",
        dataset="grc-joint",
        runtime_variant="default",
        variant_registry_sha256=variant_registry_sha256(),
        variant_award_sha256=None,
        qualification_sha256=None,
        bundle_manifest_sha256="db17b79df0a88d927870a708ecd666f3afdfd5cd890302854cab700b581ade5b",
        tokenizer_revision="a" * 64,
        annotation_profile="pyaegean-canonical-v1",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="grc-joint-v3",
        execution_providers=("CPUExecutionProvider",),
    )
    assert GreekPipelineConfig.from_json(config.to_json()) == config
    assert config.to_dict()["runtime_variant"] == "default"
    with pytest.raises(ValueError, match="award evidence"):
        replace(config, runtime_variant="compact")
    with pytest.raises(ValueError, match="appear together"):
        replace(config, variant_award_sha256="c" * 64)

    reserved = replace(
        config,
        model_id="future-model",
        dataset="future-dataset",
        runtime_variant="compact",
        variant_award_sha256="c" * 64,
        qualification_sha256="d" * 64,
    )
    with pytest.raises(NeuralVariantUnavailableError, match="reserved"):
        greek.GreekPipeline.from_config(reserved)


def test_receipt_schema4_binds_variant_and_survives_output_profile() -> None:
    receipt = AnalysisReceipt.create(
        _manifest(),
        execution_providers=("CPUExecutionProvider",),
        input_tokens=3,
        analyzed_tokens=3,
        truncated=False,
        runtime_variant="default",
        variant_registry_sha256=variant_registry_sha256(),
    )
    assert receipt.schema_version == 4
    assert AnalysisReceipt.from_json(receipt.to_json()) == receipt
    assert receipt.to_dict()["variant_award_sha256"] is None
    profiled = receipt.with_analysis_profile(greek.canonical_analysis_profile())
    assert profiled.schema_version == 4
    assert profiled.runtime_variant == "default"
    assert profiled.output_profile_id == "pyaegean-canonical-analysis-v1"

    wrong = replace(profiled, variant_registry_sha256="0" * 64)
    with pytest.raises(ReceiptMismatchError, match="variant_registry_sha256"):
        profiled.assert_same_runtime(wrong)
    with pytest.raises(ValueError, match="award evidence"):
        replace(profiled, runtime_variant="fast")


def test_greek_cli_propagates_variant_and_rejects_orphan_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        greek,
        "use_neural_pipeline",
        lambda *, variant="default": seen.append(variant),
    )
    runner = CliRunner()
    result = runner.invoke(
        _build_app(),
        ["greek", "tag", "λόγος", "--neural", "--neural-variant", "compact"],
    )
    assert result.exit_code == 0, result.output
    assert seen == ["compact"]

    orphan = runner.invoke(
        _build_app(),
        ["greek", "tag", "λόγος", "--neural-variant", "compact"],
    )
    assert orphan.exit_code == 1
    assert "requires --neural" in orphan.output
