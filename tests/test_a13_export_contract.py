"""Torch-free A13 exporter/manifest contract tests."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from aegean.greek.neural_contract import (
    ModelBundleError,
    ModelBundleManifest,
    build_schema1_manifest,
    prepare_schema1_artifact_dir,
    validate_artifact_metadata,
    validate_joint_checkpoint_sidecars,
    write_schema1_manifest,
)
from aegean.greek.neural_preprocessing import contract_metadata


_REPO = Path(__file__).resolve().parents[1]
_V3_FIXTURE = Path(__file__).parent / "fixtures" / "neural" / "grc-joint-v3-manifest.json"


def _write_legal_bundle(root: Path) -> None:
    heads = ["upos", *(f"x{i}" for i in range(9))]
    maps = {head: {"-": 0} for head in heads}
    maps["deprel"] = {"root": 0}
    (root / "labels.json").write_text(
        json.dumps({"tag_heads": heads, "maps": maps, "n_scripts": 1}),
        encoding="utf-8",
    )
    (root / "lemma-scripts.json").write_text("[\"[]\"]", encoding="utf-8")
    (root / "lemma-lookup.json").write_text(
        json.dumps({"form": {}, "form_upos": {}, "form_lower": {}}),
        encoding="utf-8",
    )
    (root / "tokenizer.json").write_text(
        json.dumps(
            {
                "truncation": {
                    "direction": "Right",
                    "max_length": 12,
                    "strategy": "LongestFirst",
                    "stride": 0,
                },
                "post_processor": {
                    "type": "RobertaProcessing",
                    "cls": ["<s>", 0],
                    "sep": ["</s>", 2],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "model.onnx").write_bytes(b"synthetic-onnx")


def test_schema1_writer_derives_runtime_fields_and_loads(tmp_path: Path) -> None:
    _write_legal_bundle(tmp_path)
    raw = write_schema1_manifest(
        tmp_path,
        model_id="grc-joint-v4-dev1",
        metadata=contract_metadata(12),
        artifact_metadata={
            "model_name": "bowphs/GreBerta",
            "model_revision": "a" * 40,
            "epochs": 4,
            "license": "fixture license",
        },
        variant="fp32",
    )
    assert raw["schema_version"] == 1
    assert raw["max_subwords"] == 12
    assert raw["tokenizer_revision"] == hashlib.sha256(
        (tmp_path / "tokenizer.json").read_bytes()
    ).hexdigest()
    assert raw["special_token_policy"] == "roberta:<s>:0:</s>:2"
    assert raw["output_heads"][-3:] == ["arc", "rel", "lemma"]
    assert raw["label_heads"] == ["upos", *(f"x{i}" for i in range(9))]
    assert raw["model_revision"] == "a" * 40
    assert raw["license"] == "fixture license"

    loaded = ModelBundleManifest.load(tmp_path)
    assert loaded.schema_version == 1
    assert loaded.model_id == "grc-joint-v4-dev1"
    assert loaded.max_subwords == 12
    assert loaded.preprocessing_version == "pyaegean-neural-preprocessing-v1"


def test_artifact_metadata_is_validated_before_export() -> None:
    with pytest.raises(ModelBundleError, match="epochs"):
        validate_artifact_metadata({"epochs": 0})
    with pytest.raises(ModelBundleError, match="64-character"):
        validate_artifact_metadata({"training_receipt_sha256": "not-a-digest"})


def test_checkpoint_sidecars_are_validated_before_export(tmp_path: Path) -> None:
    _write_legal_bundle(tmp_path)
    validate_joint_checkpoint_sidecars(tmp_path, contract_metadata(12))
    with pytest.raises(ModelBundleError, match="max_subwords"):
        validate_joint_checkpoint_sidecars(tmp_path, contract_metadata(13))

    (tmp_path / "lemma-scripts.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ModelBundleError, match="count"):
        validate_joint_checkpoint_sidecars(tmp_path, contract_metadata(12))


def test_schema1_writer_rejects_v3_and_tampering(tmp_path: Path) -> None:
    _write_legal_bundle(tmp_path)
    with pytest.raises(ModelBundleError, match="immutable grc-joint-v3"):
        build_schema1_manifest(
            tmp_path,
            model_id="grc-joint-v3",
            annotation_profile="pyaegean-canonical-v1",
            normalization="NFC",
            segmentation="pretokenized",
            preprocessing_version="pyaegean-neural-preprocessing-v1",
        )
    write_schema1_manifest(
        tmp_path,
        model_id="grc-joint-v4-dev1",
        annotation_profile="pyaegean-canonical-v1",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="pyaegean-neural-preprocessing-v1",
    )
    (tmp_path / "model.onnx").write_bytes(b"tampered")
    with pytest.raises(ModelBundleError, match="SHA-256|bytes"):
        ModelBundleManifest.load(tmp_path)


def test_schema1_loader_rejects_manifest_that_claims_v3_identity(tmp_path: Path) -> None:
    _write_legal_bundle(tmp_path)
    write_schema1_manifest(
        tmp_path,
        model_id="grc-joint-v4-dev1",
        annotation_profile="pyaegean-canonical-v1",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="pyaegean-neural-preprocessing-v1",
    )
    manifest_path = tmp_path / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["model_id"] = "grc-joint-v3"
    manifest_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="immutable grc-joint-v3"):
        ModelBundleManifest.load(tmp_path)


def test_artifact_directory_uses_new_identity_and_refuses_stale_content(
    tmp_path: Path,
) -> None:
    artifact = prepare_schema1_artifact_dir(tmp_path, "grc-joint-v4-dev1")
    assert artifact == tmp_path / "grc-joint-v4-dev1"
    assert artifact.is_dir()
    (artifact / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelBundleError, match="not empty"):
        prepare_schema1_artifact_dir(tmp_path, "grc-joint-v4-dev1")

    foreign = tmp_path / "grc-joint-v4-dev2"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("user data", encoding="utf-8")
    with pytest.raises(ModelBundleError, match="foreign entries"):
        prepare_schema1_artifact_dir(tmp_path, "grc-joint-v4-dev2")
    with pytest.raises(ModelBundleError, match="path-safe"):
        prepare_schema1_artifact_dir(tmp_path, "../grc-joint-v4")


def test_immutable_v3_fixture_is_not_rewritten() -> None:
    before = _V3_FIXTURE.read_bytes()
    raw = json.loads(before)
    assert raw["name"] == "grc-joint"
    assert raw["model_name"] == "bowphs/GreBerta"
    assert _V3_FIXTURE.read_bytes() == before


def test_export_stages_manifest_then_qualifies_before_promotion() -> None:
    source = (_REPO / "training" / "export_onnx.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    qualification_lines = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_qualification"
    ]
    write_lines = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "write_schema1_manifest"
    ]
    promotion_lines = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "promote_artifact"
    ]
    assert qualification_lines and write_lines and promotion_lines
    assert min(write_lines) < min(qualification_lines) < min(promotion_lines)
    assert '"--model-id"' in source and "required=True" in source
    assert "add_qualification_arguments(parser" in source
    assert 'profile="export"' in source
    assert 'variant="fp32"' in source
    assert "prep.validate_joint_checkpoint_spec(spec)" in source
    assert "parser_features=checkpoint_spec.parser_features" in source
    assert "validate_artifact_metadata(artifact_metadata)" in source
    assert "validate_joint_checkpoint_sidecars(args.checkpoint, export_metadata)" in source
    assert '"candidate_heads"' in source
    assert "quantize_dynamic" not in source


def test_quantization_uses_the_optimization_gate_before_promotion() -> None:
    source = (_REPO / "training" / "quantize_grc_joint.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = {
        node.func.id: node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {"write_schema1_manifest", "run_qualification", "promote_artifact"}
    }
    assert calls["write_schema1_manifest"] < calls["run_qualification"] < calls["promote_artifact"]
    assert 'profile="optimization"' in source
    assert "require_reference_operational=True" in source
    assert "tf.extractall" not in source and ".extractall(" not in source
    assert 'variant="int8-weight+fp16"' in source
    assert '"--model-id"' in source and "required=True" in source
