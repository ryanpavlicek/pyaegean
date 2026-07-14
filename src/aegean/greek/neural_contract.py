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
import os
import platform
import tempfile
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Mapping

from ..data import sha256_file
from .neural_preprocessing import (
    ANNOTATION_PROFILE,
    NORMALIZATION,
    PREPROCESSING_VERSION,
    SEGMENTATION,
    SPECIAL_TOKEN_POLICY,
    TAG_HEADS,
    tokenizer_json_contract,
)

__all__ = [
    "AnalysisReceipt",
    "build_schema1_manifest",
    "ModelBundleError",
    "ModelBundleManifest",
    "prepare_schema1_artifact_dir",
    "ReceiptMismatchError",
    "write_schema1_manifest",
]

_SCHEMA_VERSION = 1
_RECEIPT_SCHEMA_VERSION = 2
_DATASET = "grc-joint"
_V3_MODEL_ID = "grc-joint-v3"
_V3_ASSET_SHA256 = "f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e"
_TAG_HEADS = TAG_HEADS
_OUTPUT_HEADS = (*_TAG_HEADS, "arc", "rel", "lemma")
_REQUIRED_FILES = frozenset(
    {"labels.json", "lemma-lookup.json", "lemma-scripts.json", "model.onnx", "tokenizer.json"}
)
_ARTIFACT_FILES = frozenset(
    {
        *_REQUIRED_FILES,
        "model.fp32.onnx",
        "model.int8.onnx",
        "manifest.json",
    }
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
    try:
        max_subwords, special_policy = tokenizer_json_contract(tokenizer)
    except ValueError as exc:
        raise ModelBundleError(f"invalid tokenizer.json contract: {exc}") from exc
    revision = sha256_file(model_dir / "tokenizer.json")
    return max_subwords, revision, special_policy


def validate_joint_checkpoint_sidecars(
    model_dir: str | Path, metadata: Mapping[str, Any]
) -> None:
    """Validate joint labels, lemma data, and tokenizer before ONNX export."""
    root = Path(model_dir)
    _validate_labels(root)
    max_subwords, _revision, special_policy = _tokenizer_contract(root)
    if metadata.get("max_subwords") != max_subwords:
        raise ModelBundleError(
            f"checkpoint max_subwords {metadata.get('max_subwords')!r} disagrees with "
            f"tokenizer max_length {max_subwords}"
        )
    if metadata.get("special_token_policy") != special_policy:
        raise ModelBundleError(
            "checkpoint special_token_policy disagrees with tokenizer.json"
        )


def prepare_schema1_artifact_dir(out: str | Path, artifact_name: str) -> Path:
    """Create a clean named artifact directory without deleting stale user data."""
    root = Path(out)
    if (
        not artifact_name
        or Path(artifact_name).name != artifact_name
        or artifact_name in {".", ".."}
    ):
        raise ModelBundleError("artifact name must be one non-empty path-safe component")
    root.mkdir(parents=True, exist_ok=True)
    artifact = root / artifact_name
    if artifact.exists():
        if not artifact.is_dir():
            raise ModelBundleError(
                f"refusing stale export path that is not a directory: {artifact}"
            )
        entries = sorted(path.name for path in artifact.iterdir())
        if entries:
            unknown = sorted(set(entries) - _ARTIFACT_FILES)
            if unknown:
                raise ModelBundleError(
                    f"refusing export: artifact directory contains foreign entries {unknown}"
                )
            raise ModelBundleError(
                f"refusing export: artifact directory is not empty ({entries}); "
                "choose a new --out or remove the stale generated artifact"
            )
    else:
        artifact.mkdir()
    return artifact


def _manifest_metadata_value(
    metadata: Mapping[str, Any] | None,
    explicit: str | None,
    field: str,
    *aliases: str,
) -> str:
    """Return one required exporter metadata value.

    Checkpoint metadata has had a couple of useful names during development.  The
    writer accepts the canonical field and a small set of aliases, but always emits
    the canonical schema-1 name.  Missing metadata is an error: silently filling in a
    preprocessing value would make a bundle look reproducible when it is not.
    """
    value: Any = explicit
    if value is None and metadata is not None:
        for key in (field, *aliases):
            if key in metadata:
                value = metadata[key]
                break
    return _string(value, field)


def validate_artifact_metadata(
    artifact_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate optional model provenance before an expensive export starts."""
    if artifact_metadata is None:
        return {}
    allowed = {
        "model_name",
        "model_revision",
        "epochs",
        "license",
        "training_receipt_sha256",
    }
    unknown = set(artifact_metadata) - allowed
    if unknown:
        raise ModelBundleError(f"unsupported artifact metadata fields: {sorted(unknown)}")
    result: dict[str, Any] = {}
    for field in ("model_name", "model_revision", "license"):
        if field in artifact_metadata:
            result[field] = _string(artifact_metadata[field], field)
    if "epochs" in artifact_metadata:
        result["epochs"] = _positive_int(artifact_metadata["epochs"], "epochs")
    if "training_receipt_sha256" in artifact_metadata:
        digest = _string(
            artifact_metadata["training_receipt_sha256"],
            "training_receipt_sha256",
        ).lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ModelBundleError(
                "training_receipt_sha256 must be a 64-character hexadecimal digest"
            )
        result["training_receipt_sha256"] = digest
    return result


def build_schema1_manifest(
    model_dir: str | Path,
    *,
    model_id: str,
    annotation_profile: str | None = None,
    normalization: str | None = None,
    segmentation: str | None = None,
    preprocessing_version: str | None = None,
    dataset: str = _DATASET,
    variant: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    artifact_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a validated schema-1 bundle manifest without neural dependencies.

    The helper intentionally hashes only the five files required by the runtime
    contract.  Temporary ONNX variants (``model.fp32.onnx`` and
    ``model.int8.onnx``) may therefore coexist during an export without becoming
    stale manifest entries.  ``manifest.json`` itself is not self-hashed; its
    content-addressed identity is computed by :meth:`ModelBundleManifest.load`.
    """
    root = Path(model_dir)
    model_id = _string(model_id, "model_id")
    if model_id in {_DATASET, _V3_MODEL_ID}:
        raise ModelBundleError(
            "schema-1 manifests cannot reuse the grc-joint data key or immutable "
            "grc-joint-v3 model ID"
        )
    dataset = _string(dataset, "dataset")
    profile = _manifest_metadata_value(metadata, annotation_profile, "annotation_profile")
    norm = _manifest_metadata_value(
        metadata, normalization, "normalization", "normalization_form"
    )
    segmentation_value = _manifest_metadata_value(
        metadata, segmentation, "segmentation", "input_segmentation"
    )
    preprocessing = _manifest_metadata_value(
        metadata, preprocessing_version, "preprocessing_version", "shared_preprocessing_version"
    )
    if profile != ANNOTATION_PROFILE:
        raise ModelBundleError(
            f"schema-1 neural bundles require annotation profile {ANNOTATION_PROFILE!r}; "
            f"got {profile!r}"
        )
    if norm != NORMALIZATION:
        raise ModelBundleError(
            f"schema-1 neural bundles require NFC normalization; got {norm!r}"
        )
    if segmentation_value != SEGMENTATION:
        raise ModelBundleError(
            "schema-1 neural bundles require pretokenized segmentation; "
            f"got {segmentation_value!r}"
        )
    if preprocessing != PREPROCESSING_VERSION:
        raise ModelBundleError(
            f"schema-1 neural bundles require preprocessing version "
            f"{PREPROCESSING_VERSION!r}; got {preprocessing!r}"
        )
    if variant is not None:
        variant = _string(variant, "variant")

    # Validate all sidecars and derive the tokenizer fields before hashing.  This
    # gives callers a clean ModelBundleError for malformed synthetic/checkpoint data.
    label_heads, _n_scripts = _validate_labels(root)
    max_subwords, tokenizer_revision, special_policy = _tokenizer_contract(root)
    if special_policy != SPECIAL_TOKEN_POLICY:
        raise ModelBundleError(
            f"tokenizer special-token policy must be {SPECIAL_TOKEN_POLICY!r}"
        )
    if metadata is not None:
        declared_max = metadata.get("max_subwords")
        if declared_max != max_subwords:
            raise ModelBundleError(
                f"checkpoint max_subwords {declared_max!r} disagrees with tokenizer "
                f"max_length {max_subwords}"
            )
        declared_policy = metadata.get("special_token_policy")
        if declared_policy != special_policy:
            raise ModelBundleError(
                "checkpoint special_token_policy disagrees with tokenizer.json"
            )
    files: dict[str, dict[str, Any]] = {}
    for name in sorted(_REQUIRED_FILES):
        path = root / name
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ModelBundleError(f"model bundle is missing {name!r}") from exc
        files[name] = {"bytes": size, "sha256": sha256_file(path)}

    manifest: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "model_id": model_id,
        "dataset": dataset,
        "annotation_profile": profile,
        "normalization": norm,
        "segmentation": segmentation_value,
        "preprocessing_version": preprocessing,
        "output_heads": list(_OUTPUT_HEADS),
        "label_heads": list(label_heads),
        "max_subwords": max_subwords,
        "tokenizer_revision": tokenizer_revision,
        "special_token_policy": special_policy,
        "files": files,
    }
    if variant is not None:
        manifest["variant"] = variant
    manifest.update(validate_artifact_metadata(artifact_metadata))
    return manifest


def write_schema1_manifest(
    model_dir: str | Path,
    *,
    model_id: str,
    annotation_profile: str | None = None,
    normalization: str | None = None,
    segmentation: str | None = None,
    preprocessing_version: str | None = None,
    dataset: str = _DATASET,
    variant: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    artifact_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically write and return a schema-1 manifest for ``model_dir``."""
    root = Path(model_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest = build_schema1_manifest(
        root,
        model_id=model_id,
        annotation_profile=annotation_profile,
        normalization=normalization,
        segmentation=segmentation,
        preprocessing_version=preprocessing_version,
        dataset=dataset,
        variant=variant,
        metadata=metadata,
        artifact_metadata=artifact_metadata,
    )
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=root,
            prefix=".manifest-",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_name = temp.name
            json.dump(manifest, temp, ensure_ascii=False, indent=1)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, root / "manifest.json")
        temp_name = None
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
    return manifest


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
            if model_id in {_DATASET, _V3_MODEL_ID}:
                raise ModelBundleError(
                    "schema-1 manifests cannot reuse the grc-joint data key or immutable "
                    "grc-joint-v3 model ID"
                )
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

            # ``label_heads`` was absent from the first schema-1 fixture, so it is
            # optional for migration compatibility.  New manifests emit it and any
            # supplied value is checked against labels.json rather than trusted.
            declared_labels = raw.get("label_heads")
            if declared_labels is not None:
                if not isinstance(declared_labels, list) or any(
                    not isinstance(v, str) or not v for v in declared_labels
                ):
                    raise ModelBundleError("invalid model manifest field label_heads")
                if tuple(declared_labels) != label_heads:
                    raise ModelBundleError(
                        "manifest label_heads disagrees with labels.json"
                    )

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
