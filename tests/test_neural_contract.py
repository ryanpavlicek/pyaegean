"""Authoritative neural bundle metadata and exact runtime receipt contracts."""

from __future__ import annotations

import hashlib
import json
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest

from aegean.greek import AnalysisReceipt, ModelBundleError, ModelBundleManifest
from aegean.greek import neural_contract as contract

FIXTURE = Path(__file__).parent / "fixtures" / "neural" / "grc-joint-v3-manifest.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_schema1_bundle(root: Path) -> None:
    tag_heads = ["upos", *(f"x{i}" for i in range(9))]
    maps = {head: {"-": 0} for head in tag_heads}
    maps["deprel"] = {"root": 0}
    (root / "labels.json").write_text(
        json.dumps({"tag_heads": tag_heads, "maps": maps, "n_scripts": 1}),
        encoding="utf-8",
    )
    (root / "lemma-scripts.json").write_text(json.dumps(["[]"]), encoding="utf-8")
    (root / "lemma-lookup.json").write_text(
        json.dumps({"form": {}, "form_upos": {}, "form_lower": {}}), encoding="utf-8"
    )
    tokenizer = {
        "truncation": {
            "direction": "Right",
            "max_length": 8,
            "strategy": "LongestFirst",
            "stride": 0,
        },
        "post_processor": {
            "type": "RobertaProcessing",
            "sep": ["</s>", 2],
            "cls": ["<s>", 0],
        },
    }
    (root / "tokenizer.json").write_text(json.dumps(tokenizer), encoding="utf-8")
    (root / "model.onnx").write_bytes(b"fixture-onnx")
    files = {
        name: {"bytes": (root / name).stat().st_size, "sha256": _sha(root / name)}
        for name in (
            "labels.json",
            "lemma-lookup.json",
            "lemma-scripts.json",
            "model.onnx",
            "tokenizer.json",
        )
    }
    manifest = {
        "schema_version": 1,
        "model_id": "fixture-v1",
        "dataset": "fixture",
        "annotation_profile": "fixture-profile",
        "normalization": "NFC",
        "segmentation": "pretokenized",
        "preprocessing_version": "fixture-v1",
        "output_heads": [*tag_heads, "arc", "rel", "lemma"],
        "max_subwords": 8,
        "tokenizer_revision": files["tokenizer.json"]["sha256"],
        "special_token_policy": "roberta:<s>:0:</s>:2",
        "files": files,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_all_extra_recursively_includes_neural_but_not_parquet() -> None:
    requirements = metadata.requires("pyaegean") or []
    all_requires = [req for req in requirements if 'extra == "all"' in req]
    assert len(all_requires) == 1
    recursive = all_requires[0].split(";", 1)[0].strip()
    assert recursive.startswith("pyaegean[") and recursive.endswith("]")
    extras = set(recursive.removeprefix("pyaegean[").removesuffix("]").split(","))
    assert extras == {"ai", "epidoc", "geo", "data", "cli", "viz", "mcp", "tui", "neural"}
    assert "parquet" not in extras


def test_v3_legacy_fixture_is_pinned_to_the_exact_published_file_table() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert contract._file_table(raw) == contract._V3_FILES
    assert raw["name"] == "grc-joint" and raw["model_name"] == "bowphs/GreBerta"


def test_schema1_manifest_validates_and_drives_runtime_fields(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(
        tmp_path, asset_sha256="a" * 64, asset_sha256_enforced=True
    )
    assert manifest.model_id == "fixture-v1"
    assert manifest.max_subwords == 8
    assert manifest.tokenizer_revision == _sha(tmp_path / "tokenizer.json")
    assert manifest.output_heads[-3:] == ("arc", "rel", "lemma")
    assert manifest.to_dict()["special_token_policy"] == "roberta:<s>:0:</s>:2"


def test_manifest_rejects_corruption_before_activation(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    (tmp_path / "labels.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelBundleError, match="bytes|SHA-256"):
        ModelBundleManifest.load(tmp_path)


def test_manifest_rejects_incompatible_schema_and_tokenizer_policy(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    path = tmp_path / "manifest.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["schema_version"] = 999
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ModelBundleError, match="unsupported model bundle schema"):
        ModelBundleManifest.load(tmp_path)


def test_receipt_round_trip_and_content_address_are_stable(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(tmp_path)
    receipt = AnalysisReceipt.create(
        manifest,
        execution_providers=("CPUExecutionProvider",),
        input_tokens=3,
        analyzed_tokens=3,
        truncated=False,
    )
    restored = AnalysisReceipt.from_json(receipt.to_json())
    assert restored == receipt
    assert restored.sha256 == hashlib.sha256(restored.to_json().encode("utf-8")).hexdigest()
    assert restored.to_dict()["runtime_versions"]["onnxruntime"] != ""
    assert restored.schema_version == 1
    assert "calibration_sha256" not in restored.to_dict()
    assert "confidence_policy_sha256" not in restored.to_dict()


def test_receipt_schema2_records_confidence_inputs_without_changing_schema1(
    tmp_path: Path,
) -> None:
    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(tmp_path)
    calibration_sha256 = "a" * 64
    policy_sha256 = "b" * 64
    receipt = AnalysisReceipt.create(
        manifest,
        execution_providers=("CPUExecutionProvider",),
        input_tokens=3,
        analyzed_tokens=3,
        truncated=False,
        calibration_sha256=calibration_sha256,
        confidence_policy_sha256=policy_sha256,
    )

    assert receipt.schema_version == 2
    assert receipt.calibration_sha256 == calibration_sha256
    assert receipt.confidence_policy_sha256 == policy_sha256
    assert receipt.to_dict()["calibration_sha256"] == calibration_sha256
    assert AnalysisReceipt.from_json(receipt.to_json()) == receipt

    plain = AnalysisReceipt.create(
        manifest,
        execution_providers=("CPUExecutionProvider",),
        input_tokens=3,
        analyzed_tokens=3,
        truncated=False,
    )
    # Calibration and application policy are analysis inputs, not properties of the
    # loaded ONNX runtime.  They remain exact in schema 2 without preventing the prior
    # receipt from validating the same model/runtime during activation.
    receipt.assert_same_runtime(plain)


def test_receipt_rejects_malformed_confidence_hashes(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(tmp_path)
    with pytest.raises(ValueError, match="calibration_sha256"):
        AnalysisReceipt.create(
            manifest,
            execution_providers=("CPUExecutionProvider",),
            input_tokens=1,
            analyzed_tokens=1,
            truncated=False,
            calibration_sha256="not-a-hash",
        )
    with pytest.raises(ValueError, match="lowercase"):
        AnalysisReceipt.create(
            manifest,
            execution_providers=("CPUExecutionProvider",),
            input_tokens=1,
            analyzed_tokens=1,
            truncated=False,
            calibration_sha256="A" * 64,
        )


def test_receipt_schema_and_confidence_fields_cannot_disagree(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(tmp_path)
    plain = AnalysisReceipt.create(
        manifest,
        execution_providers=("CPUExecutionProvider",),
        input_tokens=1,
        analyzed_tokens=1,
        truncated=False,
    ).to_dict()
    plain["calibration_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="schema 1"):
        AnalysisReceipt.from_dict(plain)

    schema2 = dict(plain)
    schema2["schema_version"] = 2
    schema2["source_schema_version"] = 2
    schema2.pop("confidence_policy_sha256", None)
    with pytest.raises(ValueError, match="missing confidence"):
        AnalysisReceipt.from_dict(schema2)

    for invalid_schema in (True, 1.0, "1"):
        invalid = dict(plain)
        invalid.pop("calibration_sha256")
        invalid["schema_version"] = invalid_schema
        with pytest.raises(ValueError, match="must be an integer"):
            AnalysisReceipt.from_dict(invalid)


def test_receipt_reads_the_previous_coarse_backend_info_shape() -> None:
    legacy = AnalysisReceipt.from_dict(
        {
            "model": "grc-joint",
            "available_providers": ["CPUExecutionProvider"],
            "active_providers": ["CPUExecutionProvider"],
        }
    )
    assert legacy.source_schema_version == 0
    assert legacy.model_id == "grc-joint"
    assert legacy.execution_providers == ("CPUExecutionProvider",)
    assert legacy.asset_sha256 is None and legacy.tokenizer_revision is None


def test_receipt_runtime_comparison_reports_exact_mismatch(tmp_path: Path) -> None:
    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(tmp_path)
    expected = AnalysisReceipt.create(
        manifest,
        execution_providers=("CPUExecutionProvider",),
        input_tokens=1,
        analyzed_tokens=1,
        truncated=False,
    )
    actual = AnalysisReceipt.create(
        manifest,
        execution_providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
        input_tokens=0,
        analyzed_tokens=0,
        truncated=False,
    )
    with pytest.raises(contract.ReceiptMismatchError, match="execution_providers"):
        expected.assert_same_runtime(actual)


def test_activation_can_recreate_the_exact_runtime_from_a_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.greek import joint, runtime

    _write_schema1_bundle(tmp_path)
    manifest = ModelBundleManifest.load(tmp_path)
    expected = AnalysisReceipt.create(
        manifest,
        execution_providers=("CPUExecutionProvider",),
        input_tokens=3,
        analyzed_tokens=3,
        truncated=False,
        calibration_sha256="a" * 64,
        confidence_policy_sha256="b" * 64,
    )

    class Candidate:
        def __init__(self) -> None:
            self.manifest = manifest
            self._sess = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])
            self.runtime_variant = SimpleNamespace(
                label="default",
                award_sha256="c" * 64,
                qualification_sha256="d" * 64,
            )

        def _receipt(self, **_status: object) -> AnalysisReceipt:
            return AnalysisReceipt.create(
                manifest,
                execution_providers=("CPUExecutionProvider",),
                input_tokens=0,
                analyzed_tokens=0,
                truncated=False,
            )

    candidate = Candidate()
    selected = joint._resolve_neural_variant("default")
    monkeypatch.setattr(joint, "_require_neural_extra", lambda: None)
    monkeypatch.setattr(
        joint,
        "versions",
        lambda: {
            "fetched": {
                "grc-joint": {
                    "sha256": selected.asset_sha256,
                    "sha256_enforced": True,
                }
            }
        },
    )
    monkeypatch.setattr(joint, "fetch", lambda *_args, **_kwargs: tmp_path)
    monkeypatch.setattr(joint, "_JointModel", lambda *_args, **_kwargs: candidate)
    monkeypatch.setattr(joint, "_ACTIVE", None)
    # Register the facade state with monkeypatch as well: activation replaces the
    # default instance, while this test historically restored only joint._ACTIVE.
    monkeypatch.setattr(runtime, "_DEFAULT", runtime.default_pipeline())

    joint.use_neural_pipeline(expected_receipt=expected)
    assert joint.active() is candidate


def test_model_encode_uses_manifest_limit_not_a_runtime_constant() -> None:
    model = object.__new__(__import__("aegean.greek.joint", fromlist=["_JointModel"])._JointModel)
    model.manifest = SimpleNamespace(max_subwords=4)
    seen: list[str] = []

    class Tok:
        def encode(self, words: list[str], *, is_pretokenized: bool) -> SimpleNamespace:
            assert is_pretokenized is True
            seen.extend(words)
            return SimpleNamespace(ids=[0, 10, 11, 2], word_ids=[None, 0, 1, None])

    model._tok = Tok()
    ids, positions, kept = model._encode([str(i) for i in range(100_000)])
    assert seen == ["0", "1", "2", "3"]
    assert ids == [0, 10, 11, 2]
    assert positions == [1, 2] and kept == [0, 1]
