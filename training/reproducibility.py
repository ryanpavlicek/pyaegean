"""Offline reproducibility contracts for Greek NLP training runs.

This module is intentionally standard-library only.  It validates the committed
training environment lock, creates content-addressed file records and run receipts,
and performs a clean-machine preflight without downloading data or model weights.

The contracts record what was configured and what files were produced.  They do not
claim that a model is accurate, deterministic across hardware, or release-ready.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import platform
import re
import subprocess
import ctypes
import ctypes.util
from copy import deepcopy
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

ENVIRONMENT_LOCK_FORMAT = "pyaegean-training-environment-lock/1"
LEGACY_RUN_RECEIPT_FORMAT = "pyaegean-training-run-receipt/1"
RUN_RECEIPT_FORMAT = "pyaegean-training-run-receipt/2"
PREFLIGHT_FORMAT = "pyaegean-training-preflight/1"
RESOLVER_MANIFEST_FORMAT = "pyaegean-training-resolver-manifest/1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z.!+_-]*$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_REQUIRED_PACKAGES = frozenset(
    {
        "accelerate",
        "huggingface-hub",
        "numpy",
        "onnx",
        "onnxruntime-gpu",
        "safetensors",
        "tokenizers",
        "torch",
        "transformers",
    }
)


class ContractError(ValueError):
    """A reproducibility document is incomplete, ambiguous, or tampered with."""


def canonical_json(value: Any) -> str:
    """Return the UTF-8 JSON text used as the byte basis for every contract hash."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"value is not canonical JSON: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    """SHA-256 of :func:`canonical_json`, encoded as UTF-8."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def document_sha256(document: Mapping[str, Any], digest_field: str) -> str:
    """Hash a document after removing its top-level self-digest field."""

    payload = dict(document)
    payload.pop(digest_field, None)
    return canonical_sha256(payload)


def stamp_document(document: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    """Return a copy with a content-addressed top-level digest."""

    stamped = dict(document)
    stamped.pop(digest_field, None)
    stamped[digest_field] = canonical_sha256(stamped)
    return stamped


def environment_definition_payload(lock: Mapping[str, Any]) -> dict[str, Any]:
    """The stable frozen payload, excluding verification state and document self-hashes."""

    fields = ("format", "python", "platform", "dependencies", "accelerator", "backbone")
    missing = [field for field in fields if field not in lock]
    if missing:
        raise ContractError(
            "environment definition missing required fields: " + ", ".join(missing)
        )
    return {field: deepcopy(lock[field]) for field in fields}


def environment_definition_sha256(lock: Mapping[str, Any]) -> str:
    """Stable digest to which preflight receipts bind across verification promotion."""

    return canonical_sha256(environment_definition_payload(lock))


def stamp_environment_lock(lock: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute the stable definition digest and then the whole-document lock digest."""

    stamped = deepcopy(dict(lock))
    stamped["environment_definition_sha256"] = environment_definition_sha256(stamped)
    return stamp_document(stamped, "lock_sha256")


def sha256_file(path: Path | str, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash one file incrementally without loading it into memory."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(path: Path | str, root: Path | str) -> tuple[Path, str]:
    root_path = Path(root).resolve()
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(root_path)
    except ValueError as exc:
        raise ContractError(f"file is outside repository root: {resolved}") from exc
    relative_text = relative.as_posix()
    _validate_relative_path(relative_text, "file.path")
    return resolved, relative_text


def file_record(path: Path | str, *, root: Path | str) -> dict[str, Any]:
    """Create a repository-relative byte-count/SHA-256 record for an existing file."""

    resolved, relative = _relative_path(path, root)
    if not resolved.is_file():
        raise ContractError(f"not a file: {resolved}")
    return {"path": relative, "bytes": resolved.stat().st_size, "sha256": sha256_file(resolved)}


def verify_file_record(record: Mapping[str, Any], *, root: Path | str) -> None:
    """Verify that one recorded repository-relative file still has identical bytes."""

    _validate_file_record(record, "file")
    root_path = Path(root).resolve()
    candidate = (root_path / str(record["path"])).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ContractError(f"recorded file escapes repository root: {record['path']}") from exc
    if not candidate.is_file():
        raise ContractError(f"recorded file is missing: {record['path']}")
    actual_bytes = candidate.stat().st_size
    if actual_bytes != record["bytes"]:
        raise ContractError(
            f"recorded file size mismatch for {record['path']}: "
            f"expected {record['bytes']}, got {actual_bytes}"
        )
    actual_sha = sha256_file(candidate)
    if actual_sha != record["sha256"]:
        raise ContractError(
            f"recorded file SHA-256 mismatch for {record['path']}: "
            f"expected {record['sha256']}, got {actual_sha}"
        )


def _expect_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{context} must be an object")
    return value


def _expect_keys(
    value: Mapping[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
    context: str,
) -> None:
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - set(value))
    extra = sorted(set(value) - allowed)
    if missing:
        raise ContractError(f"{context} missing required fields: {', '.join(missing)}")
    if extra:
        raise ContractError(f"{context} has unknown fields: {', '.join(extra)}")


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError(f"{context} must be a non-empty trimmed string")
    return value


def _version(value: Any, context: str) -> str:
    text = _string(value, context)
    if not _VERSION_RE.fullmatch(text) or any(token in text for token in ("*", "<", ">", "=")):
        raise ContractError(f"{context} must be one exact version, not a range or wildcard")
    return text


def _sha256(value: Any, context: str) -> str:
    text = _string(value, context)
    if not _SHA256_RE.fullmatch(text):
        raise ContractError(f"{context} must be a lowercase 64-hex SHA-256")
    return text


def _commit(value: Any, context: str) -> str:
    text = _string(value, context)
    if not _COMMIT_RE.fullmatch(text):
        raise ContractError(f"{context} must be a lowercase 40-hex Git commit")
    return text


def _integer(value: Any, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError(f"{context} must be an integer >= {minimum}")
    return value


def _validate_relative_path(value: Any, context: str) -> str:
    text = _string(value, context)
    if "\\" in text or re.match(r"^[A-Za-z]:", text):
        raise ContractError(f"{context} must use forward slashes")
    path = PurePosixPath(text)
    if path.is_absolute() or text != path.as_posix() or any(part in ("", ".", "..") for part in path.parts):
        raise ContractError(f"{context} must be a normalized repository-relative path")
    return text


def _validate_file_record(value: Any, context: str) -> None:
    record = _expect_mapping(value, context)
    _expect_keys(record, required={"path", "bytes", "sha256"}, context=context)
    _validate_relative_path(record["path"], f"{context}.path")
    _integer(record["bytes"], f"{context}.bytes")
    _sha256(record["sha256"], f"{context}.sha256")


def _canonical_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _validate_packages(value: Any, context: str, *, require_training_set: bool) -> None:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{context} must be a non-empty array")
    names: list[str] = []
    for index, item in enumerate(value):
        package = _expect_mapping(item, f"{context}[{index}]")
        _expect_keys(package, required={"name", "version"}, context=f"{context}[{index}]")
        name = _canonical_package_name(_string(package["name"], f"{context}[{index}].name"))
        if name != package["name"]:
            raise ContractError(f"{context}[{index}].name must use canonical lowercase spelling")
        _version(package["version"], f"{context}[{index}].version")
        names.append(name)
    if names != sorted(names):
        raise ContractError(f"{context} must be sorted by package name")
    if len(names) != len(set(names)):
        raise ContractError(f"{context} contains duplicate package names")
    if require_training_set:
        missing = sorted(_REQUIRED_PACKAGES - set(names))
        if missing:
            raise ContractError(f"{context} missing training packages: {', '.join(missing)}")


def _validate_dependencies(value: Any, context: str) -> None:
    dependencies = _expect_mapping(value, context)
    _expect_keys(
        dependencies,
        required={"scope", "complete", "direct_roots", "resolver_evidence", "packages"},
        context=context,
    )
    scope = dependencies["scope"]
    if scope not in {
        "direct-requirements",
        "training-dependency-closure",
        "full-environment",
    }:
        raise ContractError(
            f"{context}.scope must be 'direct-requirements', "
            "'training-dependency-closure', or 'full-environment'"
        )
    if not isinstance(dependencies["complete"], bool):
        raise ContractError(f"{context}.complete must be boolean")
    direct_roots = dependencies["direct_roots"]
    if not isinstance(direct_roots, list) or not direct_roots:
        raise ContractError(f"{context}.direct_roots must be a non-empty array")
    normalized_roots = [
        _canonical_package_name(_string(root, f"{context}.direct_roots[{index}]"))
        for index, root in enumerate(direct_roots)
    ]
    if direct_roots != sorted(set(normalized_roots)):
        raise ContractError(f"{context}.direct_roots must be canonical, unique, and sorted")
    if scope == "direct-requirements" and dependencies["complete"]:
        raise ContractError(f"{context} cannot call direct requirements a complete environment")
    evidence = dependencies["resolver_evidence"]
    if scope == "training-dependency-closure" and dependencies["complete"]:
        resolver = _expect_mapping(evidence, f"{context}.resolver_evidence")
        _expect_keys(
            resolver,
            required={"file", "manifest_sha256"},
            context=f"{context}.resolver_evidence",
        )
        _validate_file_record(resolver["file"], f"{context}.resolver_evidence.file")
        _sha256(
            resolver["manifest_sha256"],
            f"{context}.resolver_evidence.manifest_sha256",
        )
    elif evidence is not None:
        raise ContractError(
            f"{context}.resolver_evidence is only valid for a complete training dependency closure"
        )
    _validate_packages(
        dependencies["packages"],
        f"{context}.packages",
        require_training_set=True,
    )
    package_names = {package["name"] for package in dependencies["packages"]}
    missing_roots = sorted(set(direct_roots) - package_names)
    if missing_roots:
        raise ContractError(f"{context}.direct_roots absent from packages: {', '.join(missing_roots)}")


def validate_resolver_manifest(
    manifest: Mapping[str, Any], *, verify_digest: bool = True
) -> None:
    """Validate a normalized complete resolver/install manifest."""

    manifest = _expect_mapping(manifest, "resolver manifest")
    _expect_keys(
        manifest,
        required={
            "format",
            "tool",
            "direct_roots",
            "resolved_packages",
            "manifest_sha256",
        },
        context="resolver manifest",
    )
    if manifest["format"] != RESOLVER_MANIFEST_FORMAT:
        raise ContractError(f"unsupported resolver manifest format: {manifest['format']!r}")
    tool = _expect_mapping(manifest["tool"], "resolver manifest.tool")
    _expect_keys(tool, required={"name", "version"}, context="resolver manifest.tool")
    _string(tool["name"], "resolver manifest.tool.name")
    _version(tool["version"], "resolver manifest.tool.version")
    roots = manifest["direct_roots"]
    if not isinstance(roots, list) or not roots:
        raise ContractError("resolver manifest.direct_roots must be a non-empty array")
    normalized_roots = [
        _canonical_package_name(_string(root, f"resolver manifest.direct_roots[{index}]"))
        for index, root in enumerate(roots)
    ]
    if roots != normalized_roots:
        raise ContractError("resolver manifest.direct_roots must use canonical package names")
    if normalized_roots != sorted(set(normalized_roots)):
        raise ContractError("resolver manifest.direct_roots must be unique and sorted")
    _validate_packages(
        manifest["resolved_packages"],
        "resolver manifest.resolved_packages",
        require_training_set=True,
    )
    resolved_names = {item["name"] for item in manifest["resolved_packages"]}
    missing_roots = sorted(set(normalized_roots) - resolved_names)
    if missing_roots:
        raise ContractError(
            "resolver manifest direct roots absent from resolved packages: "
            + ", ".join(missing_roots)
        )
    recorded = _sha256(manifest["manifest_sha256"], "resolver manifest.manifest_sha256")
    if verify_digest:
        actual = document_sha256(manifest, "manifest_sha256")
        if actual != recorded:
            raise ContractError(
                f"resolver manifest digest mismatch: expected {recorded}, recomputed {actual}"
            )


def build_resolver_manifest(
    *,
    tool_name: str,
    tool_version: str,
    direct_roots: Sequence[str],
    resolved_packages: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Build a content-addressed normalized dependency-closure manifest."""

    roots = sorted({_canonical_package_name(root) for root in direct_roots})
    packages = sorted(
        (
            {
                "name": _canonical_package_name(str(package["name"])),
                "version": str(package["version"]),
            }
            for package in resolved_packages
        ),
        key=lambda package: package["name"],
    )
    manifest = stamp_document(
        {
            "format": RESOLVER_MANIFEST_FORMAT,
            "tool": {"name": tool_name, "version": tool_version},
            "direct_roots": roots,
            "resolved_packages": packages,
        },
        "manifest_sha256",
    )
    validate_resolver_manifest(manifest)
    return manifest


def resolver_manifest_from_pip_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a complete pip ``--report`` document into the closure contract."""

    report = _expect_mapping(report, "pip report")
    pip_version = _version(report.get("pip_version"), "pip report.pip_version")
    installs = report.get("install")
    if not isinstance(installs, list) or not installs:
        raise ContractError("pip report.install must be a non-empty array")
    packages: list[dict[str, str]] = []
    roots: list[str] = []
    for index, item in enumerate(installs):
        entry = _expect_mapping(item, f"pip report.install[{index}]")
        metadata = _expect_mapping(entry.get("metadata"), f"pip report.install[{index}].metadata")
        name = _canonical_package_name(
            _string(metadata.get("name"), f"pip report.install[{index}].metadata.name")
        )
        version = _version(
            metadata.get("version"), f"pip report.install[{index}].metadata.version"
        )
        packages.append({"name": name, "version": version})
        requested = entry.get("requested", False)
        if not isinstance(requested, bool):
            raise ContractError(f"pip report.install[{index}].requested must be boolean")
        if requested:
            roots.append(name)
    if not roots:
        raise ContractError("pip report marks no direct requested roots")
    return build_resolver_manifest(
        tool_name="pip",
        tool_version=pip_version,
        direct_roots=roots,
        resolved_packages=packages,
    )


def load_resolver_manifest(path: Path | str) -> dict[str, Any]:
    manifest = load_json_document(path)
    validate_resolver_manifest(manifest)
    return manifest


def verify_resolver_evidence(
    lock: Mapping[str, Any], *, root: Path | str
) -> dict[str, Any] | None:
    """Verify closure evidence bytes/digest and equality with the locked package list."""

    dependencies = lock["dependencies"]
    if dependencies["scope"] != "training-dependency-closure":
        return None
    evidence = dependencies["resolver_evidence"]
    if evidence is None:
        raise ContractError("training dependency closure is missing resolver evidence")
    verify_file_record(evidence["file"], root=root)
    manifest_path = Path(root).resolve() / evidence["file"]["path"]
    manifest = load_resolver_manifest(manifest_path)
    if manifest["manifest_sha256"] != evidence["manifest_sha256"]:
        raise ContractError("resolver evidence manifest digest differs from environment lock")
    if manifest["resolved_packages"] != dependencies["packages"]:
        raise ContractError("environment lock packages differ from resolver evidence")
    if manifest["direct_roots"] != dependencies["direct_roots"]:
        raise ContractError("environment lock direct roots differ from resolver evidence")
    return manifest


def _validate_backbone(value: Any, context: str) -> None:
    backbone = _expect_mapping(value, context)
    _expect_keys(
        backbone,
        required={"repository", "revision", "tokenizer_revision", "revision_type", "license"},
        context=context,
    )
    _string(backbone["repository"], f"{context}.repository")
    _commit(backbone["revision"], f"{context}.revision")
    _commit(backbone["tokenizer_revision"], f"{context}.tokenizer_revision")
    if backbone["revision_type"] != "git-commit":
        raise ContractError(f"{context}.revision_type must be 'git-commit'")
    _string(backbone["license"], f"{context}.license")


def _validate_accelerator_observation(value: Any, context: str) -> Mapping[str, Any]:
    accelerator = _expect_mapping(value, context)
    _expect_keys(
        accelerator,
        required={
            "kind",
            "gpu_names",
            "gpu_count",
            "gpu_memory_bytes",
            "compute_capabilities",
            "precision",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
            "driver_version",
        },
        context=context,
    )
    if accelerator["kind"] != "cuda":
        raise ContractError(f"{context}.kind must be 'cuda'")
    gpu_names = accelerator["gpu_names"]
    if not isinstance(gpu_names, list) or not gpu_names:
        raise ContractError(f"{context}.gpu_names must be a non-empty array")
    normalized_names = [
        _string(name, f"{context}.gpu_names[{index}]") for index, name in enumerate(gpu_names)
    ]
    gpu_count = _integer(accelerator["gpu_count"], f"{context}.gpu_count", minimum=1)
    if len(normalized_names) != gpu_count:
        raise ContractError(f"{context}.gpu_names length differs from gpu_count")
    memories = accelerator["gpu_memory_bytes"]
    if not isinstance(memories, list) or len(memories) != gpu_count:
        raise ContractError(f"{context}.gpu_memory_bytes must have one value per GPU")
    for index, memory in enumerate(memories):
        _integer(memory, f"{context}.gpu_memory_bytes[{index}]", minimum=1)
    capabilities = accelerator["compute_capabilities"]
    if not isinstance(capabilities, list) or len(capabilities) != gpu_count:
        raise ContractError(f"{context}.compute_capabilities must have one value per GPU")
    for index, capability in enumerate(capabilities):
        _version(capability, f"{context}.compute_capabilities[{index}]")
    precision = accelerator["precision"]
    if precision not in {"bf16", "fp16"}:
        raise ContractError(f"{context}.precision must be 'bf16' or 'fp16'")
    for field in (
        "cuda_runtime_version",
        "torch_cuda_version",
        "cudnn_version",
        "driver_version",
    ):
        _version(accelerator[field], f"{context}.{field}")
    return accelerator


def _validate_accelerator_policy(
    accelerator: Mapping[str, Any], lock: Mapping[str, Any], context: str
) -> None:
    allocation = lock["accelerator"]["allocation"]
    allowed_prefixes = (
        allocation["preferred_gpu_prefix"],
        allocation["fallback_gpu_prefix"],
    )
    if any(not name.startswith(allowed_prefixes) for name in accelerator["gpu_names"]):
        raise ContractError(f"{context}.gpu_names are outside the preferred/fallback policy")


def _validate_preflight_observed_shape(observed: Any, *, successful: bool) -> None:
    observed = _expect_mapping(observed, "preflight report.observed")
    _expect_keys(
        observed,
        required={"python", "platform", "packages", "repository", "accelerator"},
        context="preflight report.observed",
    )

    python = _expect_mapping(observed["python"], "preflight report.observed.python")
    _expect_keys(
        python,
        required={"implementation", "version"},
        context="preflight report.observed.python",
    )
    _string(python["implementation"], "preflight report.observed.python.implementation")
    _version(python["version"], "preflight report.observed.python.version")

    system = _expect_mapping(observed["platform"], "preflight report.observed.platform")
    _expect_keys(
        system,
        required={"system", "release", "machine", "libc"},
        context="preflight report.observed.platform",
    )
    for field in ("system", "release", "machine"):
        _string(system[field], f"preflight report.observed.platform.{field}")
    libc = _expect_mapping(system["libc"], "preflight report.observed.platform.libc")
    _expect_keys(
        libc,
        required={"name", "version"},
        context="preflight report.observed.platform.libc",
    )
    _string(libc["name"], "preflight report.observed.platform.libc.name")
    _version(libc["version"], "preflight report.observed.platform.libc.version")

    packages = observed["packages"]
    if packages:
        _validate_packages(
            packages,
            "preflight report.observed.packages",
            require_training_set=False,
        )
    elif successful or not isinstance(packages, list):
        raise ContractError(
            "successful preflight report.observed.packages must be a non-empty array"
        )

    repository = observed["repository"]
    if repository is None:
        if successful:
            raise ContractError("successful preflight report must observe a repository")
    else:
        repository = _expect_mapping(
            repository, "preflight report.observed.repository"
        )
        _expect_keys(
            repository,
            required={"url", "commit", "dirty"},
            context="preflight report.observed.repository",
        )
        _string(repository["url"], "preflight report.observed.repository.url")
        _commit(repository["commit"], "preflight report.observed.repository.commit")
        if not isinstance(repository["dirty"], bool):
            raise ContractError("preflight report.observed.repository.dirty must be boolean")
        if successful and repository["dirty"]:
            raise ContractError("successful preflight report must observe a clean repository")

    accelerator = observed["accelerator"]
    if accelerator is None:
        if successful:
            raise ContractError("successful preflight report must observe an accelerator")
    else:
        _validate_accelerator_observation(
            accelerator, "preflight report.observed.accelerator"
        )


def _validate_preflight_observed(
    observed: Any, environment_lock: Mapping[str, Any]
) -> None:
    observed = _expect_mapping(observed, "preflight report.observed")
    _expect_keys(
        observed,
        required={"python", "platform", "packages", "repository", "accelerator"},
        context="preflight report.observed",
    )
    if observed["python"] != environment_lock["python"]:
        raise ContractError("preflight observed Python differs from environment definition")
    if observed["platform"] != environment_lock["platform"]:
        raise ContractError("preflight observed platform differs from environment definition")
    _validate_packages(
        observed["packages"],
        "preflight report.observed.packages",
        require_training_set=True,
    )
    if observed["packages"] != environment_lock["dependencies"]["packages"]:
        raise ContractError("preflight observed packages differ from environment definition")

    repository = _expect_mapping(
        observed["repository"], "preflight report.observed.repository"
    )
    _expect_keys(
        repository,
        required={"url", "commit", "dirty"},
        context="preflight report.observed.repository",
    )
    _string(repository["url"], "preflight report.observed.repository.url")
    _commit(repository["commit"], "preflight report.observed.repository.commit")
    if repository["dirty"] is not False:
        raise ContractError("preflight observed repository must be clean")

    accelerator = _validate_accelerator_observation(
        observed["accelerator"], "preflight report.observed.accelerator"
    )
    _validate_accelerator_policy(
        accelerator,
        environment_lock,
        "preflight report.observed.accelerator",
    )
    for field, expected in environment_lock["accelerator"]["frozen"].items():
        if expected is None:
            raise ContractError(
                f"captured environment must freeze accelerator.{field} before preflight"
            )
        if accelerator[field] != expected:
            raise ContractError(
                f"preflight observed accelerator.{field} differs from environment definition"
            )


def validate_environment_lock(
    lock: Mapping[str, Any],
    *,
    verify_digest: bool = True,
    require_validated: bool = False,
) -> None:
    """Validate the exact environment/backbone lock and its content digest."""

    lock = _expect_mapping(lock, "environment lock")
    _expect_keys(
        lock,
        required={
            "format",
            "verification",
            "provenance",
            "python",
            "platform",
            "dependencies",
            "accelerator",
            "backbone",
            "environment_definition_sha256",
            "lock_sha256",
        },
        context="environment lock",
    )
    if lock["format"] != ENVIRONMENT_LOCK_FORMAT:
        raise ContractError(f"unsupported environment lock format: {lock['format']!r}")

    verification = _expect_mapping(lock["verification"], "environment lock.verification")
    _expect_keys(
        verification,
        required={"state", "preflight_receipt_sha256"},
        context="environment lock.verification",
    )
    state = verification["state"]
    if state == "unverified-template":
        if verification["preflight_receipt_sha256"] is not None:
            raise ContractError("unverified template must not name a preflight receipt")
    elif state == "captured-candidate":
        if verification["preflight_receipt_sha256"] is not None:
            raise ContractError("captured candidate must be promoted by the preflight receipt")
    elif state == "validated":
        _sha256(
            verification["preflight_receipt_sha256"],
            "environment lock.verification.preflight_receipt_sha256",
        )
    else:
        raise ContractError(
            "environment lock.verification.state must be 'unverified-template', "
            "'captured-candidate', or 'validated'"
        )
    if require_validated and state != "validated":
        raise ContractError("training requires a clean-machine validated environment lock")

    provenance = _expect_mapping(lock["provenance"], "environment lock.provenance")
    _expect_keys(
        provenance,
        required={
            "reference_evidence",
            "reference_scope",
            "package_pin_source",
            "backbone_revision_source",
        },
        context="environment lock.provenance",
    )
    for field in (
        "reference_evidence",
        "reference_scope",
        "package_pin_source",
        "backbone_revision_source",
    ):
        _string(provenance[field], f"environment lock.provenance.{field}")

    python = _expect_mapping(lock["python"], "environment lock.python")
    _expect_keys(python, required={"implementation", "version"}, context="environment lock.python")
    _string(python["implementation"], "environment lock.python.implementation")
    _version(python["version"], "environment lock.python.version")

    system = _expect_mapping(lock["platform"], "environment lock.platform")
    _expect_keys(
        system,
        required={"system", "release", "machine", "libc"},
        context="environment lock.platform",
    )
    _string(system["system"], "environment lock.platform.system")
    _string(system["release"], "environment lock.platform.release")
    _string(system["machine"], "environment lock.platform.machine")
    libc = _expect_mapping(system["libc"], "environment lock.platform.libc")
    _expect_keys(libc, required={"name", "version"}, context="environment lock.platform.libc")
    _string(libc["name"], "environment lock.platform.libc.name")
    _version(libc["version"], "environment lock.platform.libc.version")

    _validate_dependencies(lock["dependencies"], "environment lock.dependencies")
    if state in {"captured-candidate", "validated"} and (
        lock["dependencies"]["scope"]
        not in {"training-dependency-closure", "full-environment"}
        or not lock["dependencies"]["complete"]
    ):
        raise ContractError(
            "captured/validated lock requires a complete training dependency closure or "
            "full environment"
        )
    if state == "unverified-template" and (
        lock["dependencies"]["scope"] != "direct-requirements"
        or lock["dependencies"]["complete"]
    ):
        raise ContractError("unverified template must contain incomplete direct requirements")

    accelerator = _expect_mapping(lock["accelerator"], "environment lock.accelerator")
    _expect_keys(
        accelerator,
        required={"kind", "allocation", "frozen"},
        context="environment lock.accelerator",
    )
    if accelerator["kind"] != "cuda":
        raise ContractError("environment lock.accelerator.kind must be 'cuda'")
    allocation = _expect_mapping(
        accelerator["allocation"], "environment lock.accelerator.allocation"
    )
    _expect_keys(
        allocation,
        required={"policy", "preferred_gpu_prefix", "fallback_gpu_prefix"},
        context="environment lock.accelerator.allocation",
    )
    if allocation["policy"] != "preferred-then-fallback":
        raise ContractError(
            "environment lock.accelerator.allocation.policy must be 'preferred-then-fallback'"
        )
    preferred = _string(
        allocation["preferred_gpu_prefix"],
        "environment lock.accelerator.allocation.preferred_gpu_prefix",
    )
    fallback = _string(
        allocation["fallback_gpu_prefix"],
        "environment lock.accelerator.allocation.fallback_gpu_prefix",
    )
    if preferred == fallback:
        raise ContractError("preferred and fallback GPU prefixes must differ")
    frozen = _expect_mapping(accelerator["frozen"], "environment lock.accelerator.frozen")
    _expect_keys(
        frozen,
        required={
            "gpu_names",
            "gpu_count",
            "gpu_memory_bytes",
            "compute_capabilities",
            "precision",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
            "driver_version",
        },
        context="environment lock.accelerator.frozen",
    )
    for field in (
        "cuda_runtime_version",
        "torch_cuda_version",
        "cudnn_version",
        "driver_version",
    ):
        if frozen[field] is not None:
            _version(frozen[field], f"environment lock.accelerator.frozen.{field}")
        elif state in {"captured-candidate", "validated"}:
            raise ContractError(
                "captured/validated lock must freeze every accelerator software version"
            )
    hardware_values = (
        frozen["gpu_names"],
        frozen["gpu_count"],
        frozen["gpu_memory_bytes"],
        frozen["compute_capabilities"],
        frozen["precision"],
    )
    if all(value is None for value in hardware_values):
        if state in {"captured-candidate", "validated"}:
            raise ContractError("captured/validated lock must freeze accelerator hardware")
    elif any(value is None for value in hardware_values):
        raise ContractError("accelerator hardware fields must be all null or all frozen")
    else:
        _validate_accelerator_observation(
            {
                "kind": "cuda",
                "gpu_names": frozen["gpu_names"],
                "gpu_count": frozen["gpu_count"],
                "gpu_memory_bytes": frozen["gpu_memory_bytes"],
                "compute_capabilities": frozen["compute_capabilities"],
                "precision": frozen["precision"],
                "cuda_runtime_version": frozen["cuda_runtime_version"],
                "torch_cuda_version": frozen["torch_cuda_version"],
                "cudnn_version": frozen["cudnn_version"],
                "driver_version": frozen["driver_version"],
            },
            "environment lock.accelerator.frozen",
        )

    _validate_backbone(lock["backbone"], "environment lock.backbone")
    definition = _sha256(
        lock["environment_definition_sha256"],
        "environment lock.environment_definition_sha256",
    )
    if verify_digest:
        actual_definition = environment_definition_sha256(lock)
        if actual_definition != definition:
            raise ContractError(
                "environment definition digest mismatch: "
                f"expected {definition}, recomputed {actual_definition}"
            )
    recorded = _sha256(lock["lock_sha256"], "environment lock.lock_sha256")
    if verify_digest:
        actual = document_sha256(lock, "lock_sha256")
        if actual != recorded:
            raise ContractError(
                f"environment lock digest mismatch: expected {recorded}, recomputed {actual}"
            )


def _validate_git_source(value: Any, context: str, *, include_name: bool) -> None:
    source = _expect_mapping(value, context)
    required = {"repository", "commit"} | ({"name"} if include_name else set())
    _expect_keys(source, required=required, context=context)
    if include_name:
        _string(source["name"], f"{context}.name")
    _string(source["repository"], f"{context}.repository")
    _commit(source["commit"], f"{context}.commit")


def _validate_selection_gate_binding(value: Any, context: str) -> None:
    binding = _expect_mapping(value, context)
    _expect_keys(binding, required={"config", "gate_sha256"}, context=context)
    _validate_file_record(binding["config"], f"{context}.config")
    _sha256(binding["gate_sha256"], f"{context}.gate_sha256")


def validate_run_receipt(
    receipt: Mapping[str, Any],
    *,
    environment_lock: Mapping[str, Any] | None = None,
    verify_digest: bool = True,
    require_clean_repository: bool = True,
) -> None:
    """Validate a completed training receipt and optionally bind it to its lock."""

    receipt = _expect_mapping(receipt, "run receipt")
    receipt_format = receipt.get("format")
    if receipt_format not in {LEGACY_RUN_RECEIPT_FORMAT, RUN_RECEIPT_FORMAT}:
        raise ContractError(f"unsupported run receipt format: {receipt_format!r}")
    required_fields = {
        "format",
        "run",
        "repository",
        "environment",
        "backbone",
        "corpora",
        "datasets",
        "outputs",
        "hardware",
        "receipt_sha256",
    }
    if receipt_format == RUN_RECEIPT_FORMAT:
        required_fields.add("selection_gate")
    _expect_keys(
        receipt,
        required=required_fields,
        context="run receipt",
    )
    if receipt_format == RUN_RECEIPT_FORMAT:
        _validate_selection_gate_binding(receipt["selection_gate"], "run receipt.selection_gate")

    run = _expect_mapping(receipt["run"], "run receipt.run")
    _expect_keys(
        run,
        required={"id", "status", "started_utc", "finished_utc", "command", "config", "seed"},
        context="run receipt.run",
    )
    _string(run["id"], "run receipt.run.id")
    if run["status"] != "completed":
        raise ContractError("run receipt.run.status must be 'completed'")
    for field in ("started_utc", "finished_utc"):
        value = _string(run[field], f"run receipt.run.{field}")
        if not _UTC_RE.fullmatch(value):
            raise ContractError(f"run receipt.run.{field} must be an ISO-8601 UTC timestamp")
    started = datetime.fromisoformat(str(run["started_utc"])[:-1] + "+00:00")
    finished = datetime.fromisoformat(str(run["finished_utc"])[:-1] + "+00:00")
    if finished < started:
        raise ContractError("run receipt finished before it started")
    if not isinstance(run["command"], list) or not run["command"]:
        raise ContractError("run receipt.run.command must be a non-empty argv array")
    for index, part in enumerate(run["command"]):
        _string(part, f"run receipt.run.command[{index}]")
    _validate_file_record(run["config"], "run receipt.run.config")
    _integer(run["seed"], "run receipt.run.seed")

    repository = _expect_mapping(receipt["repository"], "run receipt.repository")
    _expect_keys(
        repository,
        required={"url", "commit", "dirty"},
        context="run receipt.repository",
    )
    _string(repository["url"], "run receipt.repository.url")
    _commit(repository["commit"], "run receipt.repository.commit")
    if not isinstance(repository["dirty"], bool):
        raise ContractError("run receipt.repository.dirty must be boolean")
    if require_clean_repository and repository["dirty"]:
        raise ContractError("completed run receipt requires a clean repository")

    environment = _expect_mapping(receipt["environment"], "run receipt.environment")
    _expect_keys(
        environment,
        required={
            "lock",
            "lock_sha256",
            "dependency_scope",
            "dependency_inventory_complete",
            "preflight_receipt_sha256",
            "packages",
        },
        context="run receipt.environment",
    )
    _validate_file_record(environment["lock"], "run receipt.environment.lock")
    _sha256(environment["lock_sha256"], "run receipt.environment.lock_sha256")
    if environment["dependency_scope"] not in {
        "training-dependency-closure",
        "full-environment",
    }:
        raise ContractError(
            "completed run receipt requires a complete training closure or full environment"
        )
    if environment["dependency_inventory_complete"] is not True:
        raise ContractError("completed run receipt requires a complete dependency inventory")
    _sha256(
        environment["preflight_receipt_sha256"],
        "run receipt.environment.preflight_receipt_sha256",
    )
    _validate_packages(
        environment["packages"], "run receipt.environment.packages", require_training_set=True
    )

    _validate_backbone(receipt["backbone"], "run receipt.backbone")

    corpora = receipt["corpora"]
    if not isinstance(corpora, list) or not corpora:
        raise ContractError("run receipt.corpora must be a non-empty array")
    corpus_names: list[str] = []
    for index, corpus in enumerate(corpora):
        _validate_git_source(corpus, f"run receipt.corpora[{index}]", include_name=True)
        corpus_names.append(str(corpus["name"]))
    if corpus_names != sorted(corpus_names) or len(corpus_names) != len(set(corpus_names)):
        raise ContractError("run receipt.corpora must have unique names sorted lexically")

    for field in ("datasets", "outputs"):
        records = receipt[field]
        if not isinstance(records, list) or not records:
            raise ContractError(f"run receipt.{field} must be a non-empty array")
        paths: list[str] = []
        for index, record in enumerate(records):
            _validate_file_record(record, f"run receipt.{field}[{index}]")
            paths.append(str(record["path"]))
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ContractError(f"run receipt.{field} must have unique paths sorted lexically")

    hardware = _expect_mapping(receipt["hardware"], "run receipt.hardware")
    _expect_keys(
        hardware,
        required={
            "platform",
            "machine",
            "cpu",
            "gpu",
            "gpu_count",
            "gpu_memory_bytes",
            "driver_version",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
            "compute_capability",
            "precision",
        },
        context="run receipt.hardware",
    )
    for field in (
        "platform",
        "machine",
        "cpu",
        "gpu",
        "precision",
    ):
        _string(hardware[field], f"run receipt.hardware.{field}")
    for field in (
        "driver_version",
        "cuda_runtime_version",
        "torch_cuda_version",
        "cudnn_version",
        "compute_capability",
    ):
        _version(hardware[field], f"run receipt.hardware.{field}")
    _integer(hardware["gpu_count"], "run receipt.hardware.gpu_count", minimum=1)
    _integer(hardware["gpu_memory_bytes"], "run receipt.hardware.gpu_memory_bytes", minimum=1)

    recorded = _sha256(receipt["receipt_sha256"], "run receipt.receipt_sha256")
    if verify_digest:
        actual = document_sha256(receipt, "receipt_sha256")
        if actual != recorded:
            raise ContractError(
                f"run receipt digest mismatch: expected {recorded}, recomputed {actual}"
            )

    if environment_lock is not None:
        validate_environment_lock(environment_lock, require_validated=True)
        if environment["lock_sha256"] != environment_lock["lock_sha256"]:
            raise ContractError("run receipt references a different environment lock digest")
        if (
            environment["preflight_receipt_sha256"]
            != environment_lock["verification"]["preflight_receipt_sha256"]
        ):
            raise ContractError("run receipt references a different preflight receipt")
        if environment["dependency_scope"] != environment_lock["dependencies"]["scope"]:
            raise ContractError("run receipt dependency scope differs from the environment lock")
        if (
            environment["dependency_inventory_complete"]
            != environment_lock["dependencies"]["complete"]
        ):
            raise ContractError(
                "run receipt dependency completeness differs from the environment lock"
            )
        if environment["packages"] != environment_lock["dependencies"]["packages"]:
            raise ContractError("run receipt package versions differ from the environment lock")
        if receipt["backbone"] != environment_lock["backbone"]:
            raise ContractError("run receipt backbone differs from the environment lock")
        allocation = environment_lock["accelerator"]["allocation"]
        if not receipt["hardware"]["gpu"].startswith(
            (allocation["preferred_gpu_prefix"], allocation["fallback_gpu_prefix"])
        ):
            raise ContractError("run receipt GPU is outside the frozen allocation policy")
        frozen = environment_lock["accelerator"]["frozen"]
        for field in (
            "driver_version",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
        ):
            if frozen[field] is not None and receipt["hardware"][field] != frozen[field]:
                raise ContractError(
                    f"run receipt hardware.{field} differs from the environment lock"
                )
        if len(set(frozen["gpu_names"])) != 1:
            raise ContractError("run receipt schema cannot represent a heterogeneous GPU lock")
        if len(set(frozen["gpu_memory_bytes"])) != 1:
            raise ContractError("run receipt schema cannot represent mixed GPU memory capacities")
        if len(set(frozen["compute_capabilities"])) != 1:
            raise ContractError("run receipt schema cannot represent mixed GPU compute capabilities")
        exact_hardware = {
            "gpu": frozen["gpu_names"][0],
            "gpu_count": frozen["gpu_count"],
            "gpu_memory_bytes": frozen["gpu_memory_bytes"][0],
            "compute_capability": frozen["compute_capabilities"][0],
            "precision": frozen["precision"],
        }
        for field, expected in exact_hardware.items():
            if receipt["hardware"][field] != expected:
                raise ContractError(
                    f"run receipt hardware.{field} differs from the environment lock"
                )


def build_run_receipt(
    *,
    run: Mapping[str, Any],
    repository: Mapping[str, Any],
    environment: Mapping[str, Any],
    backbone: Mapping[str, Any],
    corpora: Sequence[Mapping[str, Any]],
    datasets: Sequence[Mapping[str, Any]],
    outputs: Sequence[Mapping[str, Any]],
    hardware: Mapping[str, Any],
    selection_gate: Mapping[str, Any] | None = None,
    environment_lock: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one immutable receipt.

    Model-training runs supply ``selection_gate`` and emit schema 2.  Omitting it
    emits schema 1 only for the existing A17 inference-free environment fixture.
    """

    payload: dict[str, Any] = {
        "format": RUN_RECEIPT_FORMAT if selection_gate is not None else LEGACY_RUN_RECEIPT_FORMAT,
        "run": dict(run),
        "repository": dict(repository),
        "environment": dict(environment),
        "backbone": dict(backbone),
        "corpora": [dict(item) for item in corpora],
        "datasets": [dict(item) for item in datasets],
        "outputs": [dict(item) for item in outputs],
        "hardware": dict(hardware),
    }
    if selection_gate is not None:
        payload["selection_gate"] = dict(selection_gate)
    receipt = stamp_document(
        payload,
        "receipt_sha256",
    )
    validate_run_receipt(receipt, environment_lock=environment_lock)
    return receipt


def verify_receipt_files(receipt: Mapping[str, Any], *, root: Path | str) -> None:
    """Re-hash every repository-relative lock/config/dataset/output in a receipt."""

    validate_run_receipt(receipt)
    verify_file_record(receipt["environment"]["lock"], root=root)
    verify_file_record(receipt["run"]["config"], root=root)
    if receipt["format"] == RUN_RECEIPT_FORMAT:
        binding = receipt["selection_gate"]
        verify_file_record(binding["config"], root=root)
        gate_path = Path(root).resolve() / PurePosixPath(binding["config"]["path"])
        gate = load_json_document(gate_path)
        if gate.get("format") != "pyaegean-model-selection-gate/1":
            raise ContractError("selection gate file uses an unknown format")
        if gate.get("claim_status") != "development-only-not-published":
            raise ContractError("selection gate file has an invalid claim status")
        embedded = _sha256(gate.get("gate_sha256"), "selection gate file.gate_sha256")
        actual = document_sha256(gate, "gate_sha256")
        if embedded != actual or embedded != binding["gate_sha256"]:
            raise ContractError("run receipt selection gate digest differs from its config")
    for field in ("datasets", "outputs"):
        for record in receipt[field]:
            verify_file_record(record, root=root)


def load_json_document(path: Path | str) -> dict[str, Any]:
    """Load one UTF-8 JSON object with duplicate-key rejection."""

    def reject_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ContractError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load JSON document {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON document must contain an object: {path}")
    return value


def load_environment_lock(path: Path | str) -> dict[str, Any]:
    lock = load_json_document(path)
    validate_environment_lock(lock)
    return lock


def load_run_receipt(
    path: Path | str, *, environment_lock: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    receipt = load_json_document(path)
    validate_run_receipt(receipt, environment_lock=environment_lock)
    return receipt


def capture_packages(names: Iterable[str]) -> list[dict[str, str]]:
    """Read exact installed distribution versions without importing heavy packages."""

    records: list[dict[str, str]] = []
    for raw_name in sorted(set(names)):
        name = _canonical_package_name(raw_name)
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ContractError(f"required package is not installed: {name}") from exc
        records.append({"name": name, "version": version})
    _validate_packages(records, "captured packages", require_training_set=False)
    return records


def capture_all_packages() -> list[dict[str, str]]:
    """Capture every installed distribution for a complete environment inventory."""

    versions: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        try:
            raw_name = distribution.metadata["Name"]
        except KeyError as exc:
            raise ContractError("installed distribution is missing its Name metadata") from exc
        if not raw_name:
            raise ContractError("installed distribution is missing its Name metadata")
        name = _canonical_package_name(str(raw_name))
        version = str(distribution.version)
        if name in versions and versions[name] != version:
            raise ContractError(
                f"installed environment contains conflicting versions for {name}: "
                f"{versions[name]} and {version}"
            )
        versions[name] = version
    records = [{"name": name, "version": versions[name]} for name in sorted(versions)]
    _validate_packages(records, "captured full environment", require_training_set=False)
    return records


def _git(root: Path | str, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=Path(root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode:
        message = process.stderr.strip() or process.stdout.strip() or "git command failed"
        raise ContractError(message)
    return process.stdout.strip()


def capture_repository(root: Path | str) -> dict[str, Any]:
    """Capture the current source commit, origin URL, and dirty state (offline)."""

    return {
        "url": _git(root, "remote", "get-url", "origin"),
        "commit": _git(root, "rev-parse", "HEAD"),
        "dirty": bool(_git(root, "status", "--porcelain")),
    }


def _cudnn_version_text(raw: int | None) -> str:
    if raw is None or raw <= 0:
        raise ContractError("torch did not report a cuDNN version")
    return f"{raw // 10000}.{(raw % 10000) // 100}.{raw % 100}"


def _cuda_version_text(raw: int) -> str:
    if raw <= 0:
        raise ContractError("CUDA runtime returned an invalid version")
    major = raw // 1000
    minor = (raw % 1000) // 10
    patch = raw % 10
    return f"{major}.{minor}.{patch}"


def capture_cuda_runtime_version() -> str:
    """Query the loaded CUDA runtime API, independently of Torch's build version."""

    candidates: list[str] = []

    def add(candidate: object) -> None:
        if candidate is None:
            return
        value = str(candidate)
        if value and value not in candidates:
            candidates.append(value)

    # Prefer the CUDA runtime installed with the active Torch environment. CUDA wheels
    # need not add their private library directories to ldconfig, and a system cudart
    # can be a different version from the runtime Torch actually loads.
    try:
        distribution = importlib.metadata.distribution("nvidia-cuda-runtime-cu12")
    except importlib.metadata.PackageNotFoundError:
        distribution = None
    if distribution is not None:
        for relative in distribution.files or ():
            if relative.name.startswith("libcudart.so"):
                add(distribution.locate_file(relative))

    torch_spec = importlib.util.find_spec("torch")
    if torch_spec is not None and torch_spec.origin:
        torch_root = Path(torch_spec.origin).resolve().parent
        for pattern in ("lib/libcudart.so*", "../nvidia/cuda_runtime/lib/libcudart.so*"):
            for path in sorted(torch_root.glob(pattern)):
                if path.is_file():
                    add(path)

    # Fall back to the process-global/system loader only after wheel-local candidates.
    add(ctypes.util.find_library("cudart"))
    add("libcudart.so")
    add("libcudart.so.12")

    errors: list[str] = []
    for candidate in candidates:
        try:
            runtime = ctypes.CDLL(candidate)
            version = ctypes.c_int()
            function = runtime.cudaRuntimeGetVersion
            function.argtypes = [ctypes.POINTER(ctypes.c_int)]
            function.restype = ctypes.c_int
            status = function(ctypes.byref(version))
            if status != 0:
                errors.append(f"{candidate}: cudaRuntimeGetVersion returned {status}")
                continue
            return _cuda_version_text(version.value)
        except (AttributeError, OSError) as exc:
            errors.append(f"{candidate}: {exc}")
    detail = "; ".join(errors) or "libcudart was not found"
    raise ContractError(f"cannot query the loaded CUDA runtime version: {detail}")


def capture_accelerator() -> dict[str, Any]:
    """Inspect CUDA metadata only; this does not load a model or run inference."""

    try:
        torch = importlib.import_module("torch")
    except ImportError as exc:
        raise ContractError("torch is required for CUDA preflight") from exc
    if not torch.cuda.is_available():
        raise ContractError("CUDA is not available to torch")
    cuda_version = getattr(torch.version, "cuda", None)
    if not cuda_version:
        raise ContractError("torch does not report a CUDA build version")
    process = subprocess.run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode:
        raise ContractError(process.stderr.strip() or "nvidia-smi failed")
    drivers = sorted({line.strip() for line in process.stdout.splitlines() if line.strip()})
    if len(drivers) != 1:
        raise ContractError("all visible GPUs must report the same driver version")
    gpu_count = int(torch.cuda.device_count())
    gpu_names = [str(torch.cuda.get_device_name(index)) for index in range(gpu_count)]
    if not gpu_names:
        raise ContractError("torch did not report any visible CUDA devices")
    return {
        "kind": "cuda",
        "gpu_names": gpu_names,
        "gpu_count": gpu_count,
        "gpu_memory_bytes": [
            int(torch.cuda.get_device_properties(index).total_memory) for index in range(gpu_count)
        ],
        "compute_capabilities": [
            ".".join(str(part) for part in torch.cuda.get_device_capability(index))
            for index in range(gpu_count)
        ],
        "precision": "bf16" if bool(torch.cuda.is_bf16_supported()) else "fp16",
        "cuda_runtime_version": capture_cuda_runtime_version(),
        "torch_cuda_version": str(cuda_version),
        "cudnn_version": _cudnn_version_text(torch.backends.cudnn.version()),
        "driver_version": drivers[0],
    }


def preflight_environment(
    lock: Mapping[str, Any],
    *,
    repository_root: Path | str,
    check_accelerator: bool = True,
    expected_repository_commit: str | None = None,
) -> dict[str, Any]:
    """Compare a clean machine with the lock; never downloads or executes a model."""

    validate_environment_lock(lock)
    issues: list[str] = []
    libc_name, libc_version = platform.libc_ver()
    observed: dict[str, Any] = {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "libc": {"name": libc_name, "version": libc_version},
        },
    }
    dependencies = lock["dependencies"]
    try:
        if dependencies["scope"] == "full-environment":
            observed["packages"] = capture_all_packages()
        else:
            names = [package["name"] for package in dependencies["packages"]]
            observed["packages"] = capture_packages(names)
    except ContractError as exc:
        issues.append(str(exc))
        observed["packages"] = []
    try:
        observed["repository"] = capture_repository(repository_root)
        if observed["repository"]["dirty"]:
            issues.append("repository has uncommitted or untracked files")
        if expected_repository_commit is not None:
            _commit(expected_repository_commit, "expected repository commit")
            if observed["repository"]["commit"] != expected_repository_commit:
                issues.append("repository commit differs from the required candidate commit")
    except ContractError as exc:
        issues.append(f"repository inspection failed: {exc}")
        observed["repository"] = None
    if check_accelerator:
        try:
            observed["accelerator"] = capture_accelerator()
        except ContractError as exc:
            issues.append(str(exc))
            observed["accelerator"] = None
    else:
        observed["accelerator"] = None
        issues.append("accelerator inspection was skipped")

    for section in ("python", "platform"):
        if observed[section] != lock[section]:
            issues.append(f"{section} differs from environment lock")
    if not dependencies["complete"]:
        issues.append("environment lock dependency inventory is incomplete")
    elif dependencies["scope"] == "training-dependency-closure":
        try:
            verify_resolver_evidence(lock, root=repository_root)
        except ContractError as exc:
            issues.append(str(exc))
        if observed["packages"] != dependencies["packages"]:
            issues.append("installed training dependency closure differs from environment lock")
    elif dependencies["scope"] == "full-environment":
        if observed["packages"] != dependencies["packages"]:
            issues.append("complete installed package inventory differs from environment lock")
    else:
        issues.append("complete dependency inventory has an unsupported scope")
    if lock["verification"]["state"] == "unverified-template":
        issues.append("environment lock is an unverified template")
    if check_accelerator and observed["accelerator"] is not None:
        allocation = lock["accelerator"]["allocation"]
        allowed_prefixes = (
            allocation["preferred_gpu_prefix"],
            allocation["fallback_gpu_prefix"],
        )
        if any(
            not gpu_name.startswith(allowed_prefixes)
            for gpu_name in observed["accelerator"]["gpu_names"]
        ):
            issues.append("allocated GPU is outside the preferred/fallback policy")
        for field, expected in lock["accelerator"]["frozen"].items():
            if expected is not None and observed["accelerator"][field] != expected:
                issues.append(f"accelerator {field} differs from environment lock")

    return stamp_document(
        {
            "format": PREFLIGHT_FORMAT,
            "ok": not issues,
            "environment_definition_sha256": lock["environment_definition_sha256"],
            "observed": observed,
            "issues": issues,
        },
        "preflight_sha256",
    )


def validate_preflight_report(
    report: Mapping[str, Any],
    *,
    environment_lock: Mapping[str, Any] | None = None,
    verify_digest: bool = True,
) -> None:
    """Validate one content-addressed preflight receipt and its definition binding."""

    report = _expect_mapping(report, "preflight report")
    _expect_keys(
        report,
        required={
            "format",
            "ok",
            "environment_definition_sha256",
            "observed",
            "issues",
            "preflight_sha256",
        },
        context="preflight report",
    )
    if report["format"] != PREFLIGHT_FORMAT:
        raise ContractError(f"unsupported preflight report format: {report['format']!r}")
    if not isinstance(report["ok"], bool):
        raise ContractError("preflight report.ok must be boolean")
    _sha256(
        report["environment_definition_sha256"],
        "preflight report.environment_definition_sha256",
    )
    issues = report["issues"]
    if not isinstance(issues, list):
        raise ContractError("preflight report.issues must be an array")
    for index, issue in enumerate(issues):
        _string(issue, f"preflight report.issues[{index}]")
    if report["ok"] != (not issues):
        raise ContractError("preflight report.ok disagrees with its issues")
    _validate_preflight_observed_shape(report["observed"], successful=report["ok"])
    recorded = _sha256(report["preflight_sha256"], "preflight report.preflight_sha256")
    if verify_digest:
        actual = document_sha256(report, "preflight_sha256")
        if actual != recorded:
            raise ContractError(
                f"preflight report digest mismatch: expected {recorded}, recomputed {actual}"
            )
    if environment_lock is not None:
        validate_environment_lock(environment_lock)
        if (
            report["environment_definition_sha256"]
            != environment_lock["environment_definition_sha256"]
        ):
            raise ContractError("preflight report binds a different environment definition")
        _validate_preflight_observed(report["observed"], environment_lock)
        verification = environment_lock["verification"]
        if (
            verification["state"] == "validated"
            and verification["preflight_receipt_sha256"] != recorded
        ):
            raise ContractError("validated environment lock binds a different preflight receipt")


def capture_candidate_environment_lock(
    template: Mapping[str, Any],
    *,
    resolver_manifest: Mapping[str, Any],
    resolver_file: Mapping[str, Any],
    accelerator: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture the installed closure and platform into a preflight-ready candidate lock."""

    validate_environment_lock(template)
    if template["verification"]["state"] != "unverified-template":
        raise ContractError("candidate capture requires an unverified template")
    validate_resolver_manifest(resolver_manifest)
    if resolver_manifest["direct_roots"] != template["dependencies"]["direct_roots"]:
        raise ContractError("resolver manifest direct roots differ from the frozen template")
    _validate_file_record(resolver_file, "resolver manifest file")
    packages = resolver_manifest["resolved_packages"]
    installed = capture_packages(package["name"] for package in packages)
    if installed != packages:
        raise ContractError("installed training dependency closure differs from resolver manifest")
    observed_accelerator = capture_accelerator() if accelerator is None else accelerator
    observed_accelerator = _validate_accelerator_observation(
        observed_accelerator, "captured accelerator"
    )
    _validate_accelerator_policy(observed_accelerator, template, "captured accelerator")
    libc_name, libc_version = platform.libc_ver()
    candidate = deepcopy(dict(template))
    candidate["python"] = {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    }
    candidate["platform"] = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "libc": {"name": libc_name, "version": libc_version},
    }
    candidate["dependencies"] = {
        "scope": "training-dependency-closure",
        "complete": True,
        "direct_roots": deepcopy(resolver_manifest["direct_roots"]),
        "resolver_evidence": {
            "file": dict(resolver_file),
            "manifest_sha256": resolver_manifest["manifest_sha256"],
        },
        "packages": deepcopy(packages),
    }
    candidate["accelerator"]["frozen"] = {
        field: observed_accelerator[field]
        for field in (
            "gpu_names",
            "gpu_count",
            "gpu_memory_bytes",
            "compute_capabilities",
            "precision",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
            "driver_version",
        )
    }
    candidate["verification"] = {
        "state": "captured-candidate",
        "preflight_receipt_sha256": None,
    }
    candidate = stamp_environment_lock(candidate)
    validate_environment_lock(candidate)
    return candidate


def promote_environment_lock(
    candidate: Mapping[str, Any], preflight_report: Mapping[str, Any]
) -> dict[str, Any]:
    """Promote a captured candidate after a successful definition-bound preflight."""

    validate_environment_lock(candidate)
    if candidate["verification"]["state"] != "captured-candidate":
        raise ContractError("only a captured candidate can be promoted")
    validate_preflight_report(preflight_report, environment_lock=candidate)
    if not preflight_report["ok"]:
        raise ContractError("cannot promote a failed preflight report")
    promoted = deepcopy(dict(candidate))
    promoted["verification"] = {
        "state": "validated",
        "preflight_receipt_sha256": preflight_report["preflight_sha256"],
    }
    definition = candidate["environment_definition_sha256"]
    promoted = stamp_environment_lock(promoted)
    if promoted["environment_definition_sha256"] != definition:
        raise ContractError("verification promotion changed the frozen environment definition")
    validate_environment_lock(promoted, require_validated=True)
    return promoted


def write_json_document(path: Path | str, document: Mapping[str, Any]) -> None:
    """Write stable, human-readable JSON; hashes remain based on compact canonical JSON."""

    Path(path).write_text(
        json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "ContractError",
    "ENVIRONMENT_LOCK_FORMAT",
    "LEGACY_RUN_RECEIPT_FORMAT",
    "PREFLIGHT_FORMAT",
    "RESOLVER_MANIFEST_FORMAT",
    "RUN_RECEIPT_FORMAT",
    "build_run_receipt",
    "build_resolver_manifest",
    "canonical_json",
    "canonical_sha256",
    "capture_accelerator",
    "capture_all_packages",
    "capture_candidate_environment_lock",
    "capture_cuda_runtime_version",
    "capture_packages",
    "capture_repository",
    "document_sha256",
    "environment_definition_payload",
    "environment_definition_sha256",
    "file_record",
    "load_environment_lock",
    "load_json_document",
    "load_resolver_manifest",
    "load_run_receipt",
    "preflight_environment",
    "promote_environment_lock",
    "resolver_manifest_from_pip_report",
    "sha256_file",
    "stamp_document",
    "stamp_environment_lock",
    "validate_environment_lock",
    "validate_preflight_report",
    "validate_resolver_manifest",
    "validate_run_receipt",
    "verify_file_record",
    "verify_receipt_files",
    "verify_resolver_evidence",
    "write_json_document",
]
