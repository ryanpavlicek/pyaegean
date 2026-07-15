"""Evidence-bound names for coexisting neural Greek runtime artifacts.

The registry is dependency-free and inspection-only.  ``default`` identifies the
release-selected artifact without making an operational claim; ``fast``, ``compact``,
and ``balanced`` remain unavailable until a separately verified variant award binds a
passing artifact qualification. Selection never falls back from an unavailable label.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Literal, Mapping, cast

__all__ = [
    "NeuralRuntimeVariant",
    "NeuralVariantError",
    "NeuralVariantLabel",
    "NeuralVariantUnavailableError",
    "neural_variant",
    "neural_variants",
    "variant_registry_sha256",
]

NeuralVariantLabel = Literal["default", "fast", "compact", "balanced"]
VariantAvailability = Literal["available", "reserved"]

_FORMAT = "pyaegean-neural-runtime-variants/1"
_LABELS: tuple[NeuralVariantLabel, ...] = (
    "default",
    "fast",
    "compact",
    "balanced",
)
_MAX_REGISTRY_BYTES = 64 * 1024
_REGISTRY_RESOURCE = "data/bundled/greek/neural-runtime-variants.json"
_V3_MODEL_ID = "grc-joint-v3"
_V3_DATASET = "grc-joint"
_V3_ASSET_SHA256 = "f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e"
_QUALIFICATION_GATE_SHA256 = "d1d451aa87ce5f9128c325ca60d7a06b4a7dc4b9f28f46701c77c097ab3094e3"
_VARIANT_POLICY_SHA256 = "563ee211e5e0d20acabea515c9d502e3d8173a90c8041134e18e50fa27c1c224"
_AWARD_FORMAT = "pyaegean-runtime-variant-award/1"
_AWARD_STATUS = "artifact-operational-selection-not-task-score"


class NeuralVariantError(ValueError):
    """Raised when the bundled runtime-variant registry is invalid."""


class NeuralVariantUnavailableError(NeuralVariantError):
    """Raised before download when a valid reserved variant has no artifact."""


def _sha256(value: Any, *, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        suffix = " or null" if optional else ""
        raise NeuralVariantError(
            f"runtime variant {field} must be a lowercase SHA-256 string{suffix}"
        )
    return value


def _optional_text(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise NeuralVariantError(
            f"runtime variant {field} must be a non-empty trimmed string or null"
        )
    return value


@dataclass(frozen=True, slots=True)
class NeuralRuntimeVariant:
    """One immutable neural runtime selection and its evidence identities."""

    label: NeuralVariantLabel
    availability: VariantAvailability
    model_id: str | None
    dataset: str | None
    asset_sha256: str | None
    bundle_manifest_sha256: str | None
    award_sha256: str | None
    qualification_sha256: str | None

    def __post_init__(self) -> None:
        if self.label not in _LABELS:
            raise NeuralVariantError(f"unknown neural runtime variant {self.label!r}")
        if self.availability not in ("available", "reserved"):
            raise NeuralVariantError(
                f"invalid availability for neural runtime variant {self.label!r}"
            )
        _optional_text(self.model_id, field="model_id")
        _optional_text(self.dataset, field="dataset")
        _sha256(self.asset_sha256, field="asset_sha256", optional=True)
        _sha256(
            self.bundle_manifest_sha256,
            field="bundle_manifest_sha256",
            optional=True,
        )
        _sha256(self.award_sha256, field="award_sha256", optional=True)
        _sha256(
            self.qualification_sha256,
            field="qualification_sha256",
            optional=True,
        )
        identities = (self.model_id, self.dataset)
        digests = (
            self.asset_sha256,
            self.bundle_manifest_sha256,
            self.award_sha256,
            self.qualification_sha256,
        )
        if self.availability == "reserved":
            if any(value is not None for value in (*identities, *digests)):
                raise NeuralVariantError(
                    f"reserved neural runtime variant {self.label!r} cannot identify an artifact"
                )
            return
        if any(value is None for value in identities[:2]) or any(
            value is None for value in digests[:2]
        ):
            raise NeuralVariantError(
                f"available neural runtime variant {self.label!r} lacks artifact identity"
            )
        if self.label == "default" and self.award_sha256 is None:
            if self.qualification_sha256 is not None:
                raise NeuralVariantError(
                    "the legacy default cannot carry qualification without an award"
                )
            if (
                self.model_id != _V3_MODEL_ID
                or self.dataset != _V3_DATASET
                or self.asset_sha256 != _V3_ASSET_SHA256
            ):
                raise NeuralVariantError(
                    "only the immutable grc-joint-v3 default may omit variant-award evidence"
                )
        elif self.award_sha256 is None or self.qualification_sha256 is None:
            raise NeuralVariantError(
                f"available neural runtime variant {self.label!r} requires award and qualification hashes"
            )

    @property
    def available(self) -> bool:
        """Whether this label currently resolves to an artifact."""

        return self.availability == "available"

    def to_dict(self) -> dict[str, Any]:
        """Return the exact JSON-compatible registry record."""

        return {
            "label": self.label,
            "availability": self.availability,
            "model_id": self.model_id,
            "dataset": self.dataset,
            "asset_sha256": self.asset_sha256,
            "bundle_manifest_sha256": self.bundle_manifest_sha256,
            "award_sha256": self.award_sha256,
            "qualification_sha256": self.qualification_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> NeuralRuntimeVariant:
        """Validate one exact registry record."""

        if not isinstance(value, Mapping):
            raise NeuralVariantError("runtime variant record must be an object")
        expected = {
            "label",
            "availability",
            "model_id",
            "dataset",
            "asset_sha256",
            "bundle_manifest_sha256",
            "award_sha256",
            "qualification_sha256",
        }
        if set(value) != expected:
            raise NeuralVariantError(
                "runtime variant record fields differ: "
                f"missing={sorted(expected - set(value))}, extra={sorted(set(value) - expected)}"
            )
        label = value["label"]
        availability = value["availability"]
        if label not in _LABELS:
            raise NeuralVariantError(f"unknown neural runtime variant {label!r}")
        if availability not in ("available", "reserved"):
            raise NeuralVariantError(f"invalid neural runtime availability {availability!r}")
        return cls(
            label=cast(NeuralVariantLabel, label),
            availability=cast(VariantAvailability, availability),
            model_id=_optional_text(value["model_id"], field="model_id"),
            dataset=_optional_text(value["dataset"], field="dataset"),
            asset_sha256=_sha256(value["asset_sha256"], field="asset_sha256", optional=True),
            bundle_manifest_sha256=_sha256(
                value["bundle_manifest_sha256"],
                field="bundle_manifest_sha256",
                optional=True,
            ),
            award_sha256=_sha256(value["award_sha256"], field="award_sha256", optional=True),
            qualification_sha256=_sha256(
                value["qualification_sha256"],
                field="qualification_sha256",
                optional=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class _VariantRegistry:
    default_variant: NeuralVariantLabel
    variants: tuple[NeuralRuntimeVariant, ...]
    registry_sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NeuralVariantError(f"duplicate runtime variant registry key {key!r}")
        result[key] = value
    return result


def _decode_registry(blob: bytes) -> _VariantRegistry:
    if not 2 <= len(blob) <= _MAX_REGISTRY_BYTES:
        raise NeuralVariantError(
            f"runtime variant registry size is outside 2..{_MAX_REGISTRY_BYTES} bytes"
        )
    try:
        value = json.loads(blob.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NeuralVariantError(f"invalid runtime variant registry JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise NeuralVariantError("runtime variant registry must be an object")
    expected = {"format", "default_variant", "variants", "registry_sha256"}
    if set(value) != expected:
        raise NeuralVariantError(
            "runtime variant registry fields differ: "
            f"missing={sorted(expected - set(value))}, extra={sorted(set(value) - expected)}"
        )
    if value["format"] != _FORMAT or value["default_variant"] != "default":
        raise NeuralVariantError("unknown runtime variant registry format/default")
    raw_variants = value["variants"]
    if not isinstance(raw_variants, list):
        raise NeuralVariantError("runtime variant registry variants must be a list")
    variants = tuple(NeuralRuntimeVariant.from_dict(item) for item in raw_variants)
    if tuple(item.label for item in variants) != _LABELS:
        raise NeuralVariantError(
            f"runtime variant registry labels/order must be {list(_LABELS)!r}"
        )
    by_dataset: dict[str, tuple[str, str, str]] = {}
    for item in variants:
        if not item.available:
            continue
        assert item.dataset is not None
        assert item.model_id is not None
        assert item.asset_sha256 is not None
        assert item.bundle_manifest_sha256 is not None
        identity = (item.model_id, item.asset_sha256, item.bundle_manifest_sha256)
        previous = by_dataset.setdefault(item.dataset, identity)
        if previous != identity:
            raise NeuralVariantError(
                f"dataset {item.dataset!r} is reused for different neural artifact bytes"
            )
    declared = _sha256(value["registry_sha256"], field="registry_sha256")
    unsigned = dict(value)
    unsigned.pop("registry_sha256")
    actual = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
    if actual != declared:
        raise NeuralVariantError(
            f"runtime variant registry digest mismatch: expected {declared}, got {actual}"
        )
    return _VariantRegistry("default", variants, actual)


def _validate_variant_award(
    value: Mapping[str, Any], variant: NeuralRuntimeVariant
) -> None:
    """Validate the public operational award bundled for an available label."""

    if not isinstance(value, Mapping):
        raise NeuralVariantError("runtime variant award must be an object")
    expected = {
        "format",
        "claim_status",
        "label",
        "policy_sha256",
        "qualification_sha256",
        "qualification_gate_sha256",
        "development_manifest_sha256",
        "measurement_profile_id",
        "reference",
        "candidate",
        "measurements",
        "checks",
        "failures",
        "awarded",
        "award_sha256",
    }
    if set(value) != expected:
        raise NeuralVariantError(
            "runtime variant award fields differ: "
            f"missing={sorted(expected - set(value))}, extra={sorted(set(value) - expected)}"
        )
    if value["format"] != _AWARD_FORMAT or value["claim_status"] != _AWARD_STATUS:
        raise NeuralVariantError("unknown runtime variant award format/claim status")
    if value["label"] != variant.label:
        raise NeuralVariantError("runtime variant award label differs from the registry")
    if value["policy_sha256"] != _VARIANT_POLICY_SHA256:
        raise NeuralVariantError("runtime variant award uses a different variant policy")
    if value["qualification_gate_sha256"] != _QUALIFICATION_GATE_SHA256:
        raise NeuralVariantError("runtime variant award uses a different qualification gate")
    if value["qualification_sha256"] != variant.qualification_sha256:
        raise NeuralVariantError("runtime variant award qualification differs from the registry")
    if value["award_sha256"] != variant.award_sha256:
        raise NeuralVariantError("runtime variant award digest differs from the registry")
    if value["measurement_profile_id"] != "pyaegean-cpu-sequential-complete-dev-v1":
        raise NeuralVariantError("runtime variant award uses a different measurement profile")
    candidate = value["candidate"]
    if not isinstance(candidate, Mapping):
        raise NeuralVariantError("runtime variant award candidate must be an object")
    if candidate.get("model_identity") != variant.model_id:
        raise NeuralVariantError("runtime variant award model differs from the registry")
    if candidate.get("bundle_manifest_sha256") != variant.bundle_manifest_sha256:
        raise NeuralVariantError("runtime variant award bundle differs from the registry")
    if value["awarded"] is not True or value["failures"] != []:
        raise NeuralVariantError("runtime variant registry points to a failed award")
    declared = _sha256(value["award_sha256"], field="award_sha256")
    unsigned = dict(value)
    unsigned.pop("award_sha256")
    actual = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
    if actual != declared:
        raise NeuralVariantError(
            f"runtime variant award digest mismatch: expected {declared}, got {actual}"
        )


def _load_variant_award(variant: NeuralRuntimeVariant) -> None:
    assert variant.award_sha256 is not None
    resource = resources.files("aegean").joinpath(
        f"data/bundled/greek/runtime-variant-awards/{variant.award_sha256}.json"
    )
    try:
        blob = resource.read_bytes()
    except OSError as exc:
        raise NeuralVariantError(
            f"available neural runtime variant {variant.label!r} lacks its award receipt"
        ) from exc
    if not 2 <= len(blob) <= _MAX_REGISTRY_BYTES:
        raise NeuralVariantError("runtime variant award exceeds the bounded resource size")
    try:
        value = json.loads(blob.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NeuralVariantError(f"invalid runtime variant award JSON: {exc}") from exc
    _validate_variant_award(value, variant)


@lru_cache(maxsize=1)
def _registry() -> _VariantRegistry:
    resource = resources.files("aegean").joinpath(_REGISTRY_RESOURCE)
    registry = _decode_registry(resource.read_bytes())
    for variant in registry.variants:
        if variant.available and variant.label != "default":
            _load_variant_award(variant)
    return registry


def neural_variants(*, available_only: bool = False) -> tuple[NeuralRuntimeVariant, ...]:
    """List the stable labels, including unavailable reservations by default."""

    variants = _registry().variants
    return tuple(item for item in variants if item.available) if available_only else variants


def neural_variant(label: str = "default") -> NeuralRuntimeVariant:
    """Inspect one label without fetching or activating its artifact."""

    if not isinstance(label, str) or not label:
        raise TypeError("neural runtime variant label must be a non-empty string")
    for item in _registry().variants:
        if item.label == label:
            return item
    raise NeuralVariantError(
        f"unknown neural runtime variant {label!r}; choose one of {list(_LABELS)!r}"
    )


def _resolve_neural_variant(label: str) -> NeuralRuntimeVariant:
    variant = neural_variant(label)
    if not variant.available:
        available = [item.label for item in neural_variants(available_only=True)]
        raise NeuralVariantUnavailableError(
            f"neural runtime variant {label!r} is reserved but has no qualified artifact; "
            f"available: {available}"
        )
    return variant


def variant_registry_sha256() -> str:
    """SHA-256 identity of the complete bundled selection registry."""

    return _registry().registry_sha256
