"""Versioned contracts for neural model bundles and runtime analysis receipts.

This module is deliberately free of neural runtime imports. It validates a fetched
bundle before ONNX Runtime is asked to activate it, and it gives every joint analysis a
stable, content-addressed description of the software and artifact that produced it.

The released ``grc-joint-v3`` archive predates the versioned bundle schema. Its immutable
legacy manifest is accepted only when every listed file matches the known v3 file table;
the missing runtime fields are then derived from the bundle's tokenizer and label files.
New bundles must carry schema version 1 directly.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping

from ..data import sha256_file

__all__ = [
    "AnalysisReceipt",
    "ModelBundleError",
    "ModelBundleManifest",
    "ReceiptMismatchError",
]

_SCHEMA_VERSION = 1
_RECEIPT_SCHEMA_VERSION = 2
_DATASET = "grc-joint"
_V3_MODEL_ID = "grc-joint-v3"
_V3_ASSET_SHA256 = "f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e"
_TAG_HEADS = ("upos", *(f"x{i}" for i in range(9)))
_OUTPUT_HEADS = (*_TAG_HEADS, "arc", "rel", "lemma")
_REQUIRED_FILES = frozenset(
    {"labels.json", "lemma-lookup.json", "lemma-scripts.json", "model.onnx", "tokenizer.json"}
)

# The root archive SHA in aegean.data authenticates a normal fetch. This table also pins
# the identity of a directly supplied or mirror-served legacy extraction: a different set
# of bytes cannot silently inherit the grc-joint-v3 name merely by copying manifest fields.
_V3_FILES: dict[str, tuple[int, str]] = {
    "labels.json": (
        1317,
        "cd8c6bbca07b4330327c8cd366edeea4e46ce60c8490635a5863f77d2ac96712",
    ),
    "lemma-lookup.json": (
        17583957,
        "ba9638ece954a19aa8b7c8971c45c5ad65227830b1ccad1645b48c8c5b5391a7",
    ),
    "lemma-scripts.json": (
        1338849,
        "3bd2479fbbab5721f67bf58175ac48431d8305ff3e74be5f744ddd560db91f0d",
    ),
    "model.onnx": (
        182121265,
        "e3a191e778780c1bebfb9c924601dddd965922322f1e71022d4314614c5ef510",
    ),
    "tokenizer.json": (
        5415240,
        "6fdc5abfedb05942a3a59c327e96647f591ebda254eb0ec64d0dfd743cd330b9",
    ),
}


class ModelBundleError(RuntimeError):
    """Raised when a neural model bundle is incomplete, corrupt, or incompatible."""


class ReceiptMismatchError(RuntimeError):
    """Raised when a requested analysis receipt does not match the active runtime."""


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelBundleError(f"invalid {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelBundleError(f"invalid {path.name}: expected a JSON object")
    return value


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ModelBundleError(f"invalid model manifest field {field}: expected a positive integer")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ModelBundleError(f"invalid model manifest field {field}: expected a non-empty string")
    return value


def _file_table(raw: Mapping[str, Any]) -> dict[str, tuple[int, str]]:
    files = raw.get("files")
    if not isinstance(files, dict):
        raise ModelBundleError("invalid model manifest field files: expected an object")
    result: dict[str, tuple[int, str]] = {}
    for name, entry in files.items():
        if not isinstance(name, str) or Path(name).name != name:
            raise ModelBundleError(f"invalid model manifest file name: {name!r}")
        if not isinstance(entry, dict):
            raise ModelBundleError(f"invalid model manifest file record for {name!r}")
        size = _positive_int(entry.get("bytes"), f"files.{name}.bytes")
        digest = _string(entry.get("sha256"), f"files.{name}.sha256").lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ModelBundleError(f"invalid model manifest sha256 for {name!r}")
        result[name] = (size, digest)
    missing = _REQUIRED_FILES - result.keys()
    if missing:
        raise ModelBundleError(f"model manifest omits required files: {sorted(missing)}")
    return result


def _validate_files(model_dir: Path, files: Mapping[str, tuple[int, str]]) -> None:
    for name, (expected_size, expected_sha) in sorted(files.items()):
        path = model_dir / name
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ModelBundleError(f"model bundle is missing {name!r}") from exc
        if size != expected_size:
            raise ModelBundleError(
                f"model bundle file {name!r} has {size} bytes; expected {expected_size}"
            )
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            raise ModelBundleError(
                f"model bundle file {name!r} failed SHA-256 validation: "
                f"expected {expected_sha}, got {actual_sha}"
            )


def _validate_labels(model_dir: Path) -> tuple[tuple[str, ...], int]:
    labels = _json_object(model_dir / "labels.json")
    heads = labels.get("tag_heads")
    if not isinstance(heads, list) or tuple(heads) != _TAG_HEADS:
        raise ModelBundleError(
            f"labels.json tag_heads must be {list(_TAG_HEADS)!r}; got {heads!r}"
        )
    maps = labels.get("maps")
    if not isinstance(maps, dict):
        raise ModelBundleError("labels.json maps must be an object")
    required = {*_TAG_HEADS, "deprel"}
    if not required.issubset(maps):
        raise ModelBundleError(f"labels.json omits label maps: {sorted(required - maps.keys())}")
    for head in sorted(required):
        mapping = maps[head]
        if not isinstance(mapping, dict) or not mapping:
            raise ModelBundleError(f"labels.json map {head!r} must be a non-empty object")
        values = list(mapping.values())
        if any(not isinstance(v, int) or isinstance(v, bool) for v in values):
            raise ModelBundleError(f"labels.json map {head!r} contains a non-integer id")
        if sorted(values) != list(range(len(values))):
            raise ModelBundleError(f"labels.json map {head!r} ids must be contiguous from zero")
    n_scripts = _positive_int(labels.get("n_scripts"), "labels.n_scripts")
    try:
        scripts = json.loads((model_dir / "lemma-scripts.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelBundleError(f"invalid lemma-scripts.json: {exc}") from exc
    if not isinstance(scripts, list) or len(scripts) != n_scripts:
        actual = len(scripts) if isinstance(scripts, list) else "non-list"
        raise ModelBundleError(
            f"lemma-scripts.json count {actual} does not match labels.json n_scripts {n_scripts}"
        )
    lookup = _json_object(model_dir / "lemma-lookup.json")
    lookup_keys = {"form", "form_upos", "form_lower"}
    if not lookup_keys.issubset(lookup) or any(not isinstance(lookup[k], dict) for k in lookup_keys):
        raise ModelBundleError("lemma-lookup.json must contain object maps form/form_upos/form_lower")
    return tuple(heads), n_scripts


def _tokenizer_contract(model_dir: Path) -> tuple[int, str, str]:
    tokenizer = _json_object(model_dir / "tokenizer.json")
    truncation = tokenizer.get("truncation")
    if not isinstance(truncation, dict):
        raise ModelBundleError("tokenizer.json must declare a truncation policy")
    max_subwords = _positive_int(truncation.get("max_length"), "tokenizer.truncation.max_length")
    if (
        truncation.get("direction") != "Right"
        or truncation.get("strategy") != "LongestFirst"
        or truncation.get("stride") != 0
    ):
        raise ModelBundleError(
            "tokenizer.json uses an unsupported truncation policy; expected right/longest-first/stride-0"
        )
    post = tokenizer.get("post_processor")
    if not isinstance(post, dict) or post.get("type") != "RobertaProcessing":
        raise ModelBundleError("tokenizer.json must use the declared Roberta special-token policy")
    cls = post.get("cls")
    sep = post.get("sep")
    if cls != ["<s>", 0] or sep != ["</s>", 2]:
        raise ModelBundleError(
            "tokenizer.json has incompatible special tokens; expected <s>:0 and </s>:2"
        )
    revision = sha256_file(model_dir / "tokenizer.json")
    return max_subwords, revision, "roberta:<s>:0:</s>:2"


@dataclass(frozen=True, slots=True)
class ModelBundleManifest:
    """Validated, runtime-authoritative description of one neural bundle."""

    schema_version: int
    source_schema_version: int
    model_id: str
    dataset: str
    asset_sha256: str | None
    asset_sha256_enforced: bool
    manifest_sha256: str
    tokenizer_revision: str
    max_subwords: int
    annotation_profile: str
    normalization: str
    segmentation: str
    preprocessing_version: str
    special_token_policy: str
    output_heads: tuple[str, ...]
    label_heads: tuple[str, ...]
    files: tuple[tuple[str, int, str], ...]

    @classmethod
    def load(
        cls,
        model_dir: str | Path,
        *,
        asset_sha256: str | None = None,
        asset_sha256_enforced: bool = False,
    ) -> "ModelBundleManifest":
        """Load and fully validate a model directory before runtime activation.

        Schema-1 bundles provide the runtime fields directly. The immutable legacy v3
        bundle is migrated only after its exact published file table is recognized.
        """
        root = Path(model_dir)
        path = root / "manifest.json"
        try:
            manifest_blob = path.read_bytes()
        except OSError as exc:
            raise ModelBundleError("model bundle is missing 'manifest.json'") from exc
        try:
            raw_value = json.loads(manifest_blob)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ModelBundleError(f"invalid manifest.json: {exc}") from exc
        if not isinstance(raw_value, dict):
            raise ModelBundleError("invalid manifest.json: expected a JSON object")
        raw: dict[str, Any] = raw_value
        files = _file_table(raw)
        source_schema = raw.get("schema_version", 0)
        if not isinstance(source_schema, int) or isinstance(source_schema, bool):
            raise ModelBundleError("invalid model manifest field schema_version")

        if source_schema == 0:
            if raw.get("name") != _DATASET or raw.get("model_name") != "bowphs/GreBerta":
                raise ModelBundleError(
                    "unversioned model manifest is not the recognized grc-joint-v3 bundle"
                )
            if files != _V3_FILES:
                raise ModelBundleError(
                    "unversioned grc-joint bundle differs from immutable v3; publish it under "
                    "a new model ID with a schema-versioned manifest"
                )
            model_id = _V3_MODEL_ID
            dataset = _DATASET
            profile = "pyaegean-canonical-v1"
            normalization = "NFC"
            segmentation = "pretokenized"
            preprocessing = "grc-joint-v3"
            output_heads = _OUTPUT_HEADS
        elif source_schema == _SCHEMA_VERSION:
            model_id = _string(raw.get("model_id"), "model_id")
            dataset = _string(raw.get("dataset"), "dataset")
            profile = _string(raw.get("annotation_profile"), "annotation_profile")
            normalization = _string(raw.get("normalization"), "normalization")
            segmentation = _string(raw.get("segmentation"), "segmentation")
            preprocessing = _string(raw.get("preprocessing_version"), "preprocessing_version")
            declared_outputs = raw.get("output_heads")
            if not isinstance(declared_outputs, list) or any(
                not isinstance(v, str) or not v for v in declared_outputs
            ):
                raise ModelBundleError("invalid model manifest field output_heads")
            output_heads = tuple(declared_outputs)
            if output_heads != _OUTPUT_HEADS:
                raise ModelBundleError(
                    f"unsupported model output heads: expected {list(_OUTPUT_HEADS)!r}, "
                    f"got {list(output_heads)!r}"
                )
        else:
            raise ModelBundleError(
                f"unsupported model bundle schema {source_schema!r}; runtime supports "
                f"schema {_SCHEMA_VERSION} and the immutable legacy v3 bundle"
            )

        _validate_files(root, files)
        label_heads, _n_scripts = _validate_labels(root)
        max_subwords, tokenizer_revision, special_policy = _tokenizer_contract(root)
        if source_schema == _SCHEMA_VERSION:
            declared_max = _positive_int(raw.get("max_subwords"), "max_subwords")
            if declared_max != max_subwords:
                raise ModelBundleError(
                    f"manifest max_subwords {declared_max} disagrees with tokenizer {max_subwords}"
                )
            if raw.get("tokenizer_revision") != tokenizer_revision:
                raise ModelBundleError("manifest tokenizer_revision disagrees with tokenizer.json")
            if raw.get("special_token_policy") != special_policy:
                raise ModelBundleError("manifest special_token_policy disagrees with tokenizer.json")

        if asset_sha256 is not None:
            asset_sha256 = asset_sha256.lower()
            if len(asset_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in asset_sha256
            ):
                raise ModelBundleError("asset_sha256 must be a 64-character hexadecimal digest")
        if source_schema == 0 and asset_sha256_enforced and asset_sha256 != _V3_ASSET_SHA256:
            raise ModelBundleError(
                "the enforced archive SHA-256 does not match the immutable grc-joint-v3 asset"
            )
        return cls(
            schema_version=_SCHEMA_VERSION,
            source_schema_version=source_schema,
            model_id=model_id,
            dataset=dataset,
            asset_sha256=asset_sha256,
            asset_sha256_enforced=asset_sha256_enforced,
            manifest_sha256=hashlib.sha256(manifest_blob).hexdigest(),
            tokenizer_revision=tokenizer_revision,
            max_subwords=max_subwords,
            annotation_profile=profile,
            normalization=normalization,
            segmentation=segmentation,
            preprocessing_version=preprocessing,
            special_token_policy=special_policy,
            output_heads=output_heads,
            label_heads=label_heads,
            files=tuple((name, size, digest) for name, (size, digest) in sorted(files.items())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the validated contract as JSON-compatible values."""
        return {
            "schema_version": self.schema_version,
            "source_schema_version": self.source_schema_version,
            "model_id": self.model_id,
            "dataset": self.dataset,
            "asset_sha256": self.asset_sha256,
            "asset_sha256_enforced": self.asset_sha256_enforced,
            "manifest_sha256": self.manifest_sha256,
            "tokenizer_revision": self.tokenizer_revision,
            "max_subwords": self.max_subwords,
            "annotation_profile": self.annotation_profile,
            "normalization": self.normalization,
            "segmentation": self.segmentation,
            "preprocessing_version": self.preprocessing_version,
            "special_token_policy": self.special_token_policy,
            "output_heads": list(self.output_heads),
            "label_heads": list(self.label_heads),
            "files": [
                {"name": name, "bytes": size, "sha256": digest}
                for name, size, digest in self.files
            ],
        }


def _installed_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "not-installed"


def _receipt_sha256(value: Any, field: str) -> str | None:
    """Validate an optional lowercase content hash carried by a receipt."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"analysis receipt {field} must be a SHA-256 string or null")
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(
            f"analysis receipt {field} must be a lowercase 64-character hexadecimal digest"
        )
    return value


@dataclass(frozen=True, slots=True)
class AnalysisReceipt:
    """Stable, content-addressed provenance for one joint sentence analysis."""

    schema_version: int
    source_schema_version: int
    model_id: str
    dataset: str
    asset_sha256: str | None
    asset_sha256_enforced: bool
    bundle_manifest_sha256: str | None
    bundle_schema_version: int | None
    tokenizer_revision: str | None
    package_version: str
    python_version: str
    runtime_versions: tuple[tuple[str, str], ...]
    execution_providers: tuple[str, ...]
    annotation_profile: str
    normalization: str
    segmentation: str
    preprocessing_version: str
    special_token_policy: str | None
    max_subwords: int | None
    input_tokens: int
    analyzed_tokens: int
    truncated: bool
    windowed: bool
    calibration_sha256: str | None = None
    confidence_policy_sha256: str | None = None

    def __post_init__(self) -> None:
        calibration = _receipt_sha256(self.calibration_sha256, "calibration_sha256")
        policy = _receipt_sha256(
            self.confidence_policy_sha256, "confidence_policy_sha256"
        )
        if self.schema_version == _SCHEMA_VERSION:
            if calibration is not None or policy is not None:
                raise ValueError("analysis receipt schema 1 cannot carry confidence hashes")
        elif self.schema_version == _RECEIPT_SCHEMA_VERSION:
            if calibration is None and policy is None:
                raise ValueError("analysis receipt schema 2 requires a confidence hash")
        else:
            raise ValueError(f"unsupported analysis receipt schema {self.schema_version!r}")

    @classmethod
    def create(
        cls,
        manifest: ModelBundleManifest,
        *,
        execution_providers: tuple[str, ...],
        input_tokens: int,
        analyzed_tokens: int,
        truncated: bool,
        windowed: bool = False,
        calibration_sha256: str | None = None,
        confidence_policy_sha256: str | None = None,
    ) -> "AnalysisReceipt":
        """Build a receipt from a validated bundle and the live execution session."""
        calibration_sha256 = _receipt_sha256(calibration_sha256, "calibration_sha256")
        confidence_policy_sha256 = _receipt_sha256(
            confidence_policy_sha256, "confidence_policy_sha256"
        )
        receipt_schema = (
            _RECEIPT_SCHEMA_VERSION
            if calibration_sha256 is not None or confidence_policy_sha256 is not None
            else _SCHEMA_VERSION
        )
        return cls(
            schema_version=receipt_schema,
            source_schema_version=receipt_schema,
            model_id=manifest.model_id,
            dataset=manifest.dataset,
            asset_sha256=manifest.asset_sha256,
            asset_sha256_enforced=manifest.asset_sha256_enforced,
            bundle_manifest_sha256=manifest.manifest_sha256,
            bundle_schema_version=manifest.schema_version,
            tokenizer_revision=manifest.tokenizer_revision,
            package_version=_installed_version("pyaegean"),
            python_version=platform.python_version(),
            runtime_versions=tuple(
                (name, _installed_version(dist))
                for name, dist in (
                    ("numpy", "numpy"),
                    ("onnxruntime", "onnxruntime"),
                    ("tokenizers", "tokenizers"),
                )
            ),
            execution_providers=execution_providers,
            annotation_profile=manifest.annotation_profile,
            normalization=manifest.normalization,
            segmentation=manifest.segmentation,
            preprocessing_version=manifest.preprocessing_version,
            special_token_policy=manifest.special_token_policy,
            max_subwords=manifest.max_subwords,
            input_tokens=input_tokens,
            analyzed_tokens=analyzed_tokens,
            truncated=truncated,
            windowed=windowed,
            calibration_sha256=calibration_sha256,
            confidence_policy_sha256=confidence_policy_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the receipt as JSON-compatible values in a stable schema."""
        value: dict[str, Any] = {
            "schema_version": self.schema_version,
            "source_schema_version": self.source_schema_version,
            "model_id": self.model_id,
            "dataset": self.dataset,
            "asset_sha256": self.asset_sha256,
            "asset_sha256_enforced": self.asset_sha256_enforced,
            "bundle_manifest_sha256": self.bundle_manifest_sha256,
            "bundle_schema_version": self.bundle_schema_version,
            "tokenizer_revision": self.tokenizer_revision,
            "package_version": self.package_version,
            "python_version": self.python_version,
            "runtime_versions": dict(self.runtime_versions),
            "execution_providers": list(self.execution_providers),
            "annotation_profile": self.annotation_profile,
            "normalization": self.normalization,
            "segmentation": self.segmentation,
            "preprocessing_version": self.preprocessing_version,
            "special_token_policy": self.special_token_policy,
            "max_subwords": self.max_subwords,
            "input_tokens": self.input_tokens,
            "analyzed_tokens": self.analyzed_tokens,
            "truncated": self.truncated,
            "windowed": self.windowed,
        }
        if self.schema_version >= _RECEIPT_SCHEMA_VERSION:
            value["calibration_sha256"] = self.calibration_sha256
            value["confidence_policy_sha256"] = self.confidence_policy_sha256
        return value

    def to_json(self) -> str:
        """Serialize canonically for storage, comparison, or hashing."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def sha256(self) -> str:
        """SHA-256 of the canonical receipt JSON."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnalysisReceipt":
        """Read schema 1 or the pre-receipt ``neural_backend_info`` shape.

        The legacy shape preserves only ``model`` and active providers. Unknown fields
        are represented honestly as empty or ``None`` rather than guessed.
        """
        schema = value.get("schema_version")
        if schema is None and "model" in value:
            providers = value.get("active_providers")
            provider_tuple = (
                tuple(str(v) for v in providers) if isinstance(providers, list) else ()
            )
            return cls(
                schema_version=_SCHEMA_VERSION,
                source_schema_version=0,
                model_id=str(value["model"]),
                dataset=str(value["model"]),
                asset_sha256=None,
                asset_sha256_enforced=False,
                bundle_manifest_sha256=None,
                bundle_schema_version=None,
                tokenizer_revision=None,
                package_version="unknown",
                python_version="unknown",
                runtime_versions=(),
                execution_providers=provider_tuple,
                annotation_profile="unknown",
                normalization="unknown",
                segmentation="unknown",
                preprocessing_version="unknown",
                special_token_policy=None,
                max_subwords=None,
                input_tokens=0,
                analyzed_tokens=0,
                truncated=False,
                windowed=False,
            )
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise ValueError("analysis receipt schema_version must be an integer")
        if schema not in (_SCHEMA_VERSION, _RECEIPT_SCHEMA_VERSION):
            raise ValueError(
                "unsupported analysis receipt schema "
                f"{schema!r}; expected {_SCHEMA_VERSION} or {_RECEIPT_SCHEMA_VERSION}"
            )
        confidence_fields = {"calibration_sha256", "confidence_policy_sha256"}
        if schema == _SCHEMA_VERSION and confidence_fields.intersection(value):
            raise ValueError("analysis receipt schema 1 cannot carry confidence hash fields")
        if schema == _RECEIPT_SCHEMA_VERSION:
            missing = confidence_fields - set(value)
            if missing:
                raise ValueError(
                    "analysis receipt schema 2 missing confidence field(s): "
                    + ", ".join(sorted(missing))
                )
        runtimes = value.get("runtime_versions")
        if not isinstance(runtimes, Mapping):
            raise ValueError("analysis receipt runtime_versions must be an object")
        providers = value.get("execution_providers")
        if not isinstance(providers, list):
            raise ValueError("analysis receipt execution_providers must be a list")
        try:
            return cls(
                schema_version=int(schema),
                source_schema_version=int(value.get("source_schema_version", schema)),
                model_id=str(value["model_id"]),
                dataset=str(value["dataset"]),
                asset_sha256=(
                    str(value["asset_sha256"]) if value.get("asset_sha256") is not None else None
                ),
                asset_sha256_enforced=bool(value["asset_sha256_enforced"]),
                bundle_manifest_sha256=(
                    str(value["bundle_manifest_sha256"])
                    if value.get("bundle_manifest_sha256") is not None
                    else None
                ),
                bundle_schema_version=(
                    int(value["bundle_schema_version"])
                    if value.get("bundle_schema_version") is not None
                    else None
                ),
                tokenizer_revision=(
                    str(value["tokenizer_revision"])
                    if value.get("tokenizer_revision") is not None
                    else None
                ),
                package_version=str(value["package_version"]),
                python_version=str(value["python_version"]),
                runtime_versions=tuple(sorted((str(k), str(v)) for k, v in runtimes.items())),
                execution_providers=tuple(str(v) for v in providers),
                annotation_profile=str(value["annotation_profile"]),
                normalization=str(value["normalization"]),
                segmentation=str(value["segmentation"]),
                preprocessing_version=str(value["preprocessing_version"]),
                special_token_policy=(
                    str(value["special_token_policy"])
                    if value.get("special_token_policy") is not None
                    else None
                ),
                max_subwords=(
                    int(value["max_subwords"]) if value.get("max_subwords") is not None else None
                ),
                input_tokens=int(value["input_tokens"]),
                analyzed_tokens=int(value["analyzed_tokens"]),
                truncated=bool(value["truncated"]),
                windowed=bool(value["windowed"]),
                calibration_sha256=(
                    _receipt_sha256(value.get("calibration_sha256"), "calibration_sha256")
                    if schema == _RECEIPT_SCHEMA_VERSION
                    else None
                ),
                confidence_policy_sha256=(
                    _receipt_sha256(
                        value.get("confidence_policy_sha256"),
                        "confidence_policy_sha256",
                    )
                    if schema == _RECEIPT_SCHEMA_VERSION
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid analysis receipt: {exc}") from exc

    @classmethod
    def from_json(cls, value: str) -> "AnalysisReceipt":
        """Deserialize a receipt from JSON."""
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid analysis receipt JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("invalid analysis receipt JSON: expected an object")
        return cls.from_dict(raw)

    def assert_same_runtime(self, actual: "AnalysisReceipt") -> None:
        """Require the artifact and software identity needed to reproduce this result."""
        fields = (
            "model_id",
            "dataset",
            "asset_sha256",
            "asset_sha256_enforced",
            "bundle_manifest_sha256",
            "bundle_schema_version",
            "tokenizer_revision",
            "package_version",
            "python_version",
            "runtime_versions",
            "execution_providers",
            "annotation_profile",
            "normalization",
            "segmentation",
            "preprocessing_version",
            "special_token_policy",
            "max_subwords",
        )
        mismatches = [
            f"{field}: expected {getattr(self, field)!r}, got {getattr(actual, field)!r}"
            for field in fields
            if getattr(self, field) != getattr(actual, field)
        ]
        if mismatches:
            raise ReceiptMismatchError(
                "analysis receipt does not match this runtime: " + "; ".join(mismatches)
            )
