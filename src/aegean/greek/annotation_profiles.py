"""Typed annotation, domain, and composed-analysis profiles.

The profile records in this module describe *conventions* and post-processing
identity.  They do not select a model, infer a domain from text, or turn a
convention comparison into a model claim.  Every record is immutable and has a
stable compact JSON representation whose SHA-256 digest can travel with an
analysis receipt.

The module deliberately has no imports from the neural runtime.  The built-in
registry is therefore safe to inspect in a zero-dependency process and remains
read-only for callers.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Mapping, cast

__all__ = [
    "AmbiguityDisclosure",
    "AnalysisProfile",
    "AnnotationProfile",
    "DomainProfile",
    "LabelMapping",
    "PostprocessingStep",
    "ProfileError",
    "ProfileEvidence",
    "ProfileMappingError",
    "ProfileSchemaError",
    "list_annotation_profiles",
    "canonical_analysis_profile",
    "list_domain_profiles",
    "get_annotation_profile",
    "get_domain_profile",
]


class ProfileError(ValueError):
    """Base error for invalid profile values or registry lookups."""


class ProfileSchemaError(ProfileError):
    """Raised when a profile value has an invalid or unknown schema field."""


class ProfileMappingError(ProfileError):
    """Raised when a mapping is lossy, ambiguous, or missing source context."""


_COMPATIBILITIES = frozenset({"canonical", "source-compatible", "diagnostic-only"})
_SHA256_HEX = frozenset("0123456789abcdef")
_MAX_PROFILE_JSON_BYTES = 1024 * 1024


def _canonical_json(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (RecursionError, TypeError, ValueError) as exc:
        raise ProfileSchemaError(f"value is not canonically JSON-serialisable: {exc}") from exc
    if len(encoded.encode("utf-8")) > _MAX_PROFILE_JSON_BYTES:
        raise ProfileSchemaError("profile JSON exceeds the 1 MiB size limit")
    return encoded


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProfileSchemaError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileSchemaError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileSchemaError(f"{field} must be a boolean")
    return value


def _schema_version(value: Any, field: str = "schema_version") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != 1:
        raise ProfileSchemaError(f"{field} must be schema version 1")
    return value


def _string_tuple(value: Any, field: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ProfileSchemaError(f"{field} must be an array of non-empty strings")
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _text(item, f"{field}[]")
        if text in seen:
            raise ProfileSchemaError(f"{field} contains duplicate value {text!r}")
        seen.add(text)
        values.append(text)
    if not allow_empty and not values:
        raise ProfileSchemaError(f"{field} must not be empty")
    return tuple(values)


def _string_or_tuple(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (_text(value, field),)
    return _string_tuple(value, field)


def _sequence(value: Any, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ProfileSchemaError(f"{field} must be an array")
    return tuple(value)


def _pairs(value: Any, field: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, (list, tuple)):
        raise ProfileSchemaError(f"{field} must be an array of two-item pairs")
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ProfileSchemaError(f"{field}[{index}] must be a two-item pair")
        source = _text(item[0], f"{field}[{index}][0]")
        target = _text(item[1], f"{field}[{index}][1]")
        if source in seen:
            raise ProfileMappingError(f"{field} contains duplicate source label {source!r}")
        seen.add(source)
        normalized.append((source, target))
    return tuple(sorted(normalized))


def _json_scalar(value: Any, field: str) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProfileSchemaError(f"{field} must not contain NaN or infinity")
        return value
    raise ProfileSchemaError(f"{field} must contain only JSON scalar values")


def _parameter_pairs(value: Any, field: str) -> tuple[tuple[str, str | int | float | bool | None], ...]:
    if isinstance(value, Mapping):
        items = list(value.items())
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        raise ProfileSchemaError(f"{field} must be an object or array of pairs")
    normalized: list[tuple[str, str | int | float | bool | None]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ProfileSchemaError(f"{field}[{index}] must be a two-item pair")
        key = _text(item[0], f"{field}[{index}][0]")
        if key in seen:
            raise ProfileSchemaError(f"{field} contains duplicate key {key!r}")
        seen.add(key)
        normalized.append((key, _json_scalar(item[1], f"{field}[{key!r}]")))
    return tuple(sorted(normalized))


def _hash(value: Any, field: str) -> str | None:
    if value is None:
        return None
    text = _text(value, field)
    if len(text) != 64 or any(char not in _SHA256_HEX for char in text):
        raise ProfileSchemaError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _expect_object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProfileSchemaError(f"{field} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ProfileSchemaError(f"{field} keys must be strings")
    return value


def _expect_keys(
    value: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    field: str,
) -> None:
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing or unknown:
        raise ProfileSchemaError(
            f"{field} fields mismatch: missing={sorted(missing)!r}, unknown={sorted(unknown)!r}"
        )


def _decode_json(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, str):
        raise ProfileSchemaError(f"{field} JSON must be a string")
    if len(value.encode("utf-8")) > _MAX_PROFILE_JSON_BYTES:
        raise ProfileSchemaError(f"{field} JSON exceeds the 1 MiB size limit")
    try:
        raw = json.loads(value, object_pairs_hook=_reject_duplicate_pairs)
    except ProfileError:
        raise
    except (RecursionError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProfileSchemaError(f"invalid {field} JSON: {exc}") from exc
    return _expect_object(raw, field)


def _nested(value: Any, cls: Any, field: str) -> Any:
    if isinstance(value, cls):
        return value
    try:
        return cls.from_dict(_expect_object(value, field))
    except ProfileError:
        raise
    except (TypeError, ValueError) as exc:
        raise ProfileSchemaError(f"invalid {field}") from exc


@dataclass(frozen=True, slots=True)
class ProfileEvidence:
    evidence_id: str
    kind: str
    source: str
    scope: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        for field in ("evidence_id", "kind", "source", "scope"):
            object.__setattr__(self, field, _text(getattr(self, field), field))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "source": self.source,
            "scope": self.scope,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProfileEvidence":
        raw = _expect_object(value, "profile evidence")
        _expect_keys(
            raw,
            {"evidence_id", "kind", "source", "scope", "schema_version"},
            set(),
            "profile evidence",
        )
        return cls(
            raw["evidence_id"],
            raw["kind"],
            raw["source"],
            raw["scope"],
            raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "ProfileEvidence":
        return cls.from_dict(_decode_json(value, "profile evidence"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class AmbiguityDisclosure:
    code: str
    field: str
    description: str
    behavior: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        for field in ("code", "field", "description", "behavior"):
            object.__setattr__(self, field, _text(getattr(self, field), field))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "field": self.field,
            "description": self.description,
            "behavior": self.behavior,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AmbiguityDisclosure":
        raw = _expect_object(value, "ambiguity disclosure")
        _expect_keys(
            raw,
            {"code", "field", "description", "behavior", "schema_version"},
            set(),
            "ambiguity disclosure",
        )
        return cls(
            raw["code"],
            raw["field"],
            raw["description"],
            raw["behavior"],
            raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "AmbiguityDisclosure":
        return cls.from_dict(_decode_json(value, "ambiguity disclosure"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class LabelMapping:
    """A directional source-label mapping.

    ``pairs`` always point from ``source_profile`` to ``target_profile``.  An
    inverse is available only for an explicitly validated bijection; a mapping
    that collapses labels must carry a loss disclosure and refuses inversion.
    """

    field: str
    source_profile: str
    target_profile: str
    pairs: tuple[tuple[str, str], ...]
    reversible: bool
    unmapped: tuple[str, ...] = ()
    context: str | None = None
    losses: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        object.__setattr__(self, "field", _text(self.field, "field"))
        object.__setattr__(self, "source_profile", _text(self.source_profile, "source_profile"))
        object.__setattr__(self, "target_profile", _text(self.target_profile, "target_profile"))
        normalized_pairs = _pairs(self.pairs, "pairs")
        object.__setattr__(self, "pairs", normalized_pairs)
        object.__setattr__(self, "reversible", _bool(self.reversible, "reversible"))
        object.__setattr__(self, "unmapped", _string_tuple(self.unmapped, "unmapped"))
        object.__setattr__(self, "context", _optional_text(self.context, "context"))
        object.__setattr__(self, "losses", _string_tuple(self.losses, "losses"))
        targets = [target for _source, target in normalized_pairs]
        if self.reversible:
            if not normalized_pairs:
                raise ProfileMappingError("a reversible mapping must contain at least one pair")
            if len(set(targets)) != len(targets):
                raise ProfileMappingError("a reversible mapping must be bijective")
            if self.unmapped or self.context is not None or self.losses:
                raise ProfileMappingError(
                    "a reversible mapping cannot declare unmapped labels, context, or losses"
                )
        elif len(set(targets)) != len(targets) and not self.losses:
            raise ProfileMappingError(
                "a many-to-one mapping requires an explicit loss disclosure"
            )
        elif not self.losses and not self.unmapped and self.context is None:
            raise ProfileMappingError(
                "a non-reversible mapping requires a loss, unmapped-label, or context disclosure"
            )

    @property
    def mapping(self) -> Mapping[str, str]:
        """Read-only source-to-target mapping view."""

        return MappingProxyType(dict(self.pairs))

    def _lookup(
        self,
        value: str,
        *,
        direction: Literal["forward", "inverse"],
        context: str | None,
        strict: bool,
    ) -> str | None:
        value = _text(value, "value")
        if self.context is not None and context is None:
            raise ProfileMappingError(
                f"{self.field} mapping requires source context {self.context!r}"
            )
        if context is not None:
            _text(context, "context")
        if direction == "inverse" and not self.reversible:
            raise ProfileMappingError(f"{self.field} mapping is not reversible")
        if direction == "forward":
            if value in self.unmapped:
                message = f"{self.field} label {value!r} is explicitly unmapped"
                if strict:
                    raise ProfileMappingError(message)
                return None
            lookup = dict(self.pairs)
        else:
            lookup = {target: source for source, target in self.pairs}
        if value not in lookup:
            if strict:
                raise ProfileMappingError(f"{self.field} has no mapping for label {value!r}")
            return None
        return lookup[value]

    def forward(
        self, value: str, *, context: str | None = None, strict: bool = True
    ) -> str | None:
        return self._lookup(value, direction="forward", context=context, strict=strict)

    def inverse(
        self, value: str, *, context: str | None = None, strict: bool = True
    ) -> str | None:
        return self._lookup(value, direction="inverse", context=context, strict=strict)

    def project(
        self,
        value: str,
        *,
        direction: Literal["forward", "inverse"] = "forward",
        context: str | None = None,
        strict: bool = True,
    ) -> str | None:
        if direction not in {"forward", "inverse"}:
            raise ProfileMappingError("mapping direction must be 'forward' or 'inverse'")
        return self._lookup(value, direction=direction, context=context, strict=strict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "source_profile": self.source_profile,
            "target_profile": self.target_profile,
            "pairs": [[source, target] for source, target in self.pairs],
            "reversible": self.reversible,
            "unmapped": list(self.unmapped),
            "context": self.context,
            "losses": list(self.losses),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LabelMapping":
        raw = _expect_object(value, "label mapping")
        _expect_keys(
            raw,
            {
                "field",
                "source_profile",
                "target_profile",
                "pairs",
                "reversible",
                "schema_version",
            },
            {"unmapped", "context", "losses"},
            "label mapping",
        )
        return cls(
            field=raw["field"],
            source_profile=raw["source_profile"],
            target_profile=raw["target_profile"],
            pairs=raw["pairs"],
            reversible=raw["reversible"],
            unmapped=raw.get("unmapped", ()),
            context=raw.get("context"),
            losses=raw.get("losses", ()),
            schema_version=raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "LabelMapping":
        return cls.from_dict(_decode_json(value, "label mapping"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _nested_tuple(value: Any, cls: Any, field: str) -> tuple[Any, ...]:
    values = _sequence(value, field)
    result = tuple(_nested(item, cls, f"{field}[]") for item in values)
    return result


def _unique_nested(values: tuple[Any, ...], attr: str, field: str) -> tuple[Any, ...]:
    seen: set[str] = set()
    for item in values:
        key = getattr(item, attr)
        if key in seen:
            raise ProfileSchemaError(f"{field} contains duplicate {attr} {key!r}")
        seen.add(key)
    return values


@dataclass(frozen=True, slots=True)
class AnnotationProfile:
    profile_id: str
    source_convention: str
    source_revision: str
    source_license: str
    compatibility: Literal["canonical", "source-compatible", "diagnostic-only"]
    output_fields: tuple[str, ...]
    relation_scheme: str
    normalization: tuple[str, ...]
    model_segmentation: str
    document_segmentation: str
    mappings: tuple[LabelMapping, ...]
    supported_domains: tuple[str, ...]
    raw_requirements: tuple[str, ...]
    ambiguities: tuple[AmbiguityDisclosure, ...]
    evidence: tuple[ProfileEvidence, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile_id"))
        object.__setattr__(self, "source_convention", _text(self.source_convention, "source_convention"))
        object.__setattr__(self, "source_revision", _text(self.source_revision, "source_revision"))
        object.__setattr__(self, "source_license", _text(self.source_license, "source_license"))
        compatibility = _text(self.compatibility, "compatibility")
        if compatibility not in _COMPATIBILITIES:
            raise ProfileSchemaError(
                "compatibility must be 'canonical', 'source-compatible', or 'diagnostic-only'"
            )
        object.__setattr__(self, "compatibility", compatibility)
        object.__setattr__(self, "output_fields", _string_tuple(self.output_fields, "output_fields", allow_empty=False))
        object.__setattr__(self, "relation_scheme", _text(self.relation_scheme, "relation_scheme"))
        object.__setattr__(self, "normalization", _string_or_tuple(self.normalization, "normalization"))
        object.__setattr__(self, "model_segmentation", _text(self.model_segmentation, "model_segmentation"))
        object.__setattr__(self, "document_segmentation", _text(self.document_segmentation, "document_segmentation"))
        mappings = _nested_tuple(self.mappings, LabelMapping, "mappings")
        object.__setattr__(self, "mappings", _unique_nested(mappings, "field", "mappings"))
        object.__setattr__(self, "supported_domains", _string_tuple(self.supported_domains, "supported_domains"))
        object.__setattr__(self, "raw_requirements", _string_tuple(self.raw_requirements, "raw_requirements"))
        ambiguities = _nested_tuple(self.ambiguities, AmbiguityDisclosure, "ambiguities")
        object.__setattr__(self, "ambiguities", _unique_nested(ambiguities, "code", "ambiguities"))
        evidence = _nested_tuple(self.evidence, ProfileEvidence, "evidence")
        object.__setattr__(self, "evidence", _unique_nested(evidence, "evidence_id", "evidence"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "source_convention": self.source_convention,
            "source_revision": self.source_revision,
            "source_license": self.source_license,
            "compatibility": self.compatibility,
            "output_fields": list(self.output_fields),
            "relation_scheme": self.relation_scheme,
            "normalization": list(self.normalization),
            "model_segmentation": self.model_segmentation,
            "document_segmentation": self.document_segmentation,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
            "supported_domains": list(self.supported_domains),
            "raw_requirements": list(self.raw_requirements),
            "ambiguities": [item.to_dict() for item in self.ambiguities],
            "evidence": [item.to_dict() for item in self.evidence],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnnotationProfile":
        raw = _expect_object(value, "annotation profile")
        required = {
            "profile_id",
            "source_convention",
            "source_revision",
            "source_license",
            "compatibility",
            "output_fields",
            "relation_scheme",
            "normalization",
            "model_segmentation",
            "document_segmentation",
            "mappings",
            "supported_domains",
            "raw_requirements",
            "ambiguities",
            "evidence",
        }
        _expect_keys(raw, required | {"schema_version"}, set(), "annotation profile")
        return cls(
            profile_id=raw["profile_id"],
            source_convention=raw["source_convention"],
            source_revision=raw["source_revision"],
            source_license=raw["source_license"],
            compatibility=raw["compatibility"],
            output_fields=raw["output_fields"],
            relation_scheme=raw["relation_scheme"],
            normalization=raw["normalization"],
            model_segmentation=raw["model_segmentation"],
            document_segmentation=raw["document_segmentation"],
            mappings=raw["mappings"],
            supported_domains=raw["supported_domains"],
            raw_requirements=raw["raw_requirements"],
            ambiguities=raw["ambiguities"],
            evidence=raw["evidence"],
            schema_version=raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "AnnotationProfile":
        return cls.from_dict(_decode_json(value, "annotation profile"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class DomainProfile:
    profile_id: str
    domains: tuple[str, ...]
    source_layer: str
    annotation_profile_id: str
    normalization: tuple[str, ...]
    segmentation: tuple[str, ...]
    evidence: tuple[ProfileEvidence, ...]
    limitations: tuple[str, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile_id"))
        object.__setattr__(self, "domains", _string_tuple(self.domains, "domains", allow_empty=False))
        object.__setattr__(self, "source_layer", _text(self.source_layer, "source_layer"))
        object.__setattr__(self, "annotation_profile_id", _text(self.annotation_profile_id, "annotation_profile_id"))
        object.__setattr__(self, "normalization", _string_or_tuple(self.normalization, "normalization"))
        object.__setattr__(self, "segmentation", _string_or_tuple(self.segmentation, "segmentation"))
        evidence = _nested_tuple(self.evidence, ProfileEvidence, "evidence")
        object.__setattr__(self, "evidence", _unique_nested(evidence, "evidence_id", "evidence"))
        object.__setattr__(self, "limitations", _string_tuple(self.limitations, "limitations"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "domains": list(self.domains),
            "source_layer": self.source_layer,
            "annotation_profile_id": self.annotation_profile_id,
            "normalization": list(self.normalization),
            "segmentation": list(self.segmentation),
            "evidence": [item.to_dict() for item in self.evidence],
            "limitations": list(self.limitations),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DomainProfile":
        raw = _expect_object(value, "domain profile")
        required = {
            "profile_id",
            "domains",
            "source_layer",
            "annotation_profile_id",
            "normalization",
            "segmentation",
            "evidence",
            "limitations",
        }
        _expect_keys(raw, required | {"schema_version"}, set(), "domain profile")
        return cls(
            profile_id=raw["profile_id"],
            domains=raw["domains"],
            source_layer=raw["source_layer"],
            annotation_profile_id=raw["annotation_profile_id"],
            normalization=raw["normalization"],
            segmentation=raw["segmentation"],
            evidence=raw["evidence"],
            limitations=raw["limitations"],
            schema_version=raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "DomainProfile":
        return cls.from_dict(_decode_json(value, "domain profile"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PostprocessingStep:
    step_id: str
    parameters: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    resource_id: str | None = None
    resource_sha256: str | None = None
    evidence: tuple[ProfileEvidence, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        object.__setattr__(self, "step_id", _text(self.step_id, "step_id"))
        object.__setattr__(self, "parameters", _parameter_pairs(self.parameters, "parameters"))
        object.__setattr__(self, "resource_id", _optional_text(self.resource_id, "resource_id"))
        object.__setattr__(self, "resource_sha256", _hash(self.resource_sha256, "resource_sha256"))
        if self.resource_sha256 is not None and self.resource_id is None:
            raise ProfileSchemaError("resource_sha256 requires resource_id")
        evidence = _nested_tuple(self.evidence, ProfileEvidence, "evidence")
        object.__setattr__(self, "evidence", _unique_nested(evidence, "evidence_id", "evidence"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "parameters": {key: value for key, value in self.parameters},
            "resource_id": self.resource_id,
            "resource_sha256": self.resource_sha256,
            "evidence": [item.to_dict() for item in self.evidence],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PostprocessingStep":
        raw = _expect_object(value, "postprocessing step")
        _expect_keys(
            raw,
            {"step_id", "schema_version"},
            {"parameters", "resource_id", "resource_sha256", "evidence"},
            "postprocessing step",
        )
        return cls(
            step_id=raw["step_id"],
            parameters=raw.get("parameters", {}),
            resource_id=raw.get("resource_id"),
            resource_sha256=raw.get("resource_sha256"),
            evidence=raw.get("evidence", ()),
            schema_version=raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "PostprocessingStep":
        return cls.from_dict(_decode_json(value, "postprocessing step"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class AnalysisProfile:
    profile_id: str
    inference_annotation_profile: str
    output_annotation_profile: str
    domain_profile: str | None = None
    postprocessing: tuple[PostprocessingStep, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", _schema_version(self.schema_version))
        object.__setattr__(self, "profile_id", _text(self.profile_id, "profile_id"))
        object.__setattr__(self, "inference_annotation_profile", _text(self.inference_annotation_profile, "inference_annotation_profile"))
        object.__setattr__(self, "output_annotation_profile", _text(self.output_annotation_profile, "output_annotation_profile"))
        object.__setattr__(self, "domain_profile", _optional_text(self.domain_profile, "domain_profile"))
        steps = _nested_tuple(self.postprocessing, PostprocessingStep, "postprocessing")
        object.__setattr__(self, "postprocessing", _unique_nested(steps, "step_id", "postprocessing"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "inference_annotation_profile": self.inference_annotation_profile,
            "output_annotation_profile": self.output_annotation_profile,
            "domain_profile": self.domain_profile,
            "postprocessing": [item.to_dict() for item in self.postprocessing],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnalysisProfile":
        raw = _expect_object(value, "analysis profile")
        _expect_keys(
            raw,
            {"profile_id", "inference_annotation_profile", "output_annotation_profile", "schema_version"},
            {"domain_profile", "postprocessing"},
            "analysis profile",
        )
        return cls(
            profile_id=raw["profile_id"],
            inference_annotation_profile=raw["inference_annotation_profile"],
            output_annotation_profile=raw["output_annotation_profile"],
            domain_profile=raw.get("domain_profile"),
            postprocessing=raw.get("postprocessing", ()),
            schema_version=raw["schema_version"],
        )

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "AnalysisProfile":
        return cls.from_dict(_decode_json(value, "analysis profile"))

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _evidence(evidence_id: str, source: str, scope: str, *, kind: str = "claims-registry") -> ProfileEvidence:
    return ProfileEvidence(evidence_id=evidence_id, kind=kind, source=source, scope=scope)


_CANONICAL = AnnotationProfile(
    profile_id="pyaegean-canonical-v1",
    source_convention="pyaegean canonical AGDT-derived UD convention",
    source_revision="grc-joint-v3",
    source_license="Apache-2.0",
    compatibility="canonical",
    output_fields=("FORM", "LEMMA", "UPOS", "XPOS", "FEATS", "HEAD", "DEPREL"),
    relation_scheme="UD basic dependencies rendered from the AGDT-derived scheme",
    normalization=("NFC",),
    model_segmentation="pretokenized complete-word model input with validated special-token policy",
    document_segmentation="caller-provided sentences or observed punctuation boundaries; no inferred offsets",
    mappings=(),
    supported_domains=(),
    raw_requirements=("retain XPOS, source alignment, TokenFormState, and complete segmentation when reconstruction is needed",),
    ambiguities=(),
    evidence=(_evidence("neural_ud_perseus_test", "training/results/lemma-remeasure-2026-07-09.json", "canonical AGDT/UD held-out evaluation"),),
)

_AGDT = AnnotationProfile(
    profile_id="perseus-agdt-v1",
    source_convention="Perseus/Ancient Greek Dependency Treebank (AGDT) convention",
    source_revision="UD_Ancient_Greek-Perseus@331ddef91411d0e6549744ee889e05549e6da77d",
    source_license="CC BY-NC-SA 2.5",
    compatibility="diagnostic-only",
    output_fields=("FORM", "LEMMA", "UPOS", "XPOS", "FEATS", "HEAD", "DEPREL"),
    relation_scheme="AGDT dependencies with the published AGDT-to-UD relation projection",
    normalization=("NFC", "preserve accents and editorial source forms"),
    model_segmentation="source treebank tokenization; multiword and empty-node rows require retained source rows",
    document_segmentation="source treebank sentence boundaries",
    mappings=(
        LabelMapping(
            field="xpos",
            source_profile="perseus-agdt-v1",
            target_profile="pyaegean-canonical-v1",
            pairs=(),
            reversible=False,
            unmapped=("unknown",),
            losses=("AGDT nine-position morphology can collapse tense/voice and omit unknown codes in UD features",),
            context="AGDT XPOS width and source tagset",
        ),
        LabelMapping(
            field="deprel",
            source_profile="perseus-agdt-v1",
            target_profile="pyaegean-canonical-v1",
            pairs=(),
            reversible=False,
            losses=("AGDT-to-UD dependency conversion can restructure heads and relation labels",),
            context="source dependency tree",
        ),
    ),
    supported_domains=("literary prose", "poetry", "Perseus treebank"),
    raw_requirements=("retain original AGDT XPOS width and codes", "retain source sentence and dependency identifiers"),
    ambiguities=(
        AmbiguityDisclosure("lexical-upos-context", "UPOS", "Conjunction and auxiliary splits require lexical or tree context.", "refuse a context-free inverse"),
        AmbiguityDisclosure("xpos-width", "XPOS", "Malformed or non-nine-position AGDT tags are not safely padded or truncated.", "report or refuse the value"),
    ),
    evidence=(_evidence("neural_ud_perseus_test", "training/results/lemma-remeasure-2026-07-09.json", "Perseus/AGDT held-out convention"),),
)

_PROIEL = AnnotationProfile(
    profile_id="proiel-diagnostic-v1",
    source_convention="UD PROIEL convention",
    source_revision="UD_Ancient_Greek-PROIEL@a4ab8d436de97d4598d410d91ea20b4127d04a5f",
    source_license="CC BY-NC-SA 3.0",
    compatibility="diagnostic-only",
    output_fields=("FORM", "LEMMA", "UPOS", "XPOS", "FEATS", "HEAD", "DEPREL"),
    relation_scheme="UD PROIEL basic dependencies",
    normalization=("NFC",),
    model_segmentation="PROIEL tokenization including punctuation and empty-node conventions",
    document_segmentation="PROIEL sentence boundaries",
    mappings=(
        LabelMapping(
            field="upos",
            source_profile="proiel-diagnostic-v1",
            target_profile="pyaegean-canonical-v1",
            pairs=(),
            reversible=False,
            losses=("PROIEL POS distinctions absent from the AGDT scheme collapse and cannot be inverted",),
            context="PROIEL POS inventory and source sentence",
        ),
        LabelMapping(
            field="feats",
            source_profile="proiel-diagnostic-v1",
            target_profile="pyaegean-canonical-v1",
            pairs=(),
            reversible=False,
            losses=("PROIEL subtype and scheme-absent features are not emitted by the AGDT renderer",),
        ),
        LabelMapping(
            field="deprel",
            source_profile="proiel-diagnostic-v1",
            target_profile="pyaegean-canonical-v1",
            pairs=(),
            reversible=False,
            losses=("PROIEL dependency labels and heads differ from the AGDT-derived scheme",),
        ),
    ),
    supported_domains=("New Testament", "documentary Koine", "PROIEL treebank"),
    raw_requirements=("retain PROIEL punctuation and empty-token rows for any comparison", "retain source sentence IDs"),
    ambiguities=(
        AmbiguityDisclosure("pos-collapse", "UPOS", "PROIEL POS categories collapse into the AGDT-trained output space.", "diagnostic only; do not claim source-compatible conversion"),
        AmbiguityDisclosure("scheme-absent-features", "FEATS", "Some PROIEL universal features are absent from the AGDT scheme.", "report the missing feature rather than synthesize it"),
        AmbiguityDisclosure("dependency-difference", "DEPREL", "Dependency heads and relation inventories differ across conventions.", "compare diagnostically; refuse an inverse"),
        AmbiguityDisclosure(
            "native-xml-evaluation-projection",
            "FORM/LEMMA",
            "The separate native-PROIEL XML evaluation projection strips #N homograph suffixes, omits empty tokens, and receives presentation punctuation outside token rows; exact UD-fold scoring does none of that cleanup.",
            "keep native-XML projection behavior separate from the UD-PROIEL profile",
        ),
    ),
    evidence=(_evidence("proiel_convention_decomposition", "training/results/proiel-convention-decomp-2026-07-11.json", "PROIEL convention decomposition; measurement only"),),
)

_PAPYGREEK = AnnotationProfile(
    profile_id="papygreek-agdt-v1",
    source_convention="PapyGreek documentary Koine regularized AGDT-compatible convention",
    source_revision="papygreek-fold-v4",
    source_license="CC BY-SA 4.0",
    compatibility="source-compatible",
    output_fields=("FORM", "LEMMA", "UPOS", "XPOS", "FEATS", "HEAD", "DEPREL"),
    relation_scheme="AGDT-derived UD scheme used by the PapyGreek regularized fold",
    normalization=("NFC", "regularized FORM layer"),
    model_segmentation="PapyGreek fold sentence and word segmentation",
    document_segmentation="PapyGreek sentence boundaries with source alignment where retained",
    mappings=(
        LabelMapping(
            field="xpos",
            source_profile="papygreek-agdt-v1",
            target_profile="pyaegean-canonical-v1",
            pairs=(),
            reversible=False,
            losses=("Documentary coordinator, common-gender, and underscore encodings can differ from AGDT",),
            context="PapyGreek regularized source layer",
        ),
    ),
    supported_domains=("documentary Koine", "PapyGreek regularized layer"),
    raw_requirements=("retain the regularized FORM and its relation to any diplomatic source",),
    ambiguities=(
        AmbiguityDisclosure("documentary-convention", "XPOS", "PapyGreek documentary choices include convention-level coordinator and morphology differences.", "report convention drift separately from model error"),
    ),
    evidence=(
        _evidence("neural_papygreek_test", "training/results/papygreek-eval-v3-2026-07-11.json", "PapyGreek regularized fold"),
        _evidence("papygreek_convention_decomposition", "training/results/papygreek-convention-decomp-2026-07-11.json", "PapyGreek convention decomposition; measurement only"),
    ),
)

def _registry(values: tuple[Any, ...], field: str) -> Mapping[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        profile_id = getattr(value, "profile_id", None)
        if not isinstance(profile_id, str) or not profile_id:
            raise ProfileSchemaError(f"{field} contains a value without a profile_id")
        if profile_id in result:
            raise ProfileSchemaError(f"{field} contains duplicate profile_id {profile_id!r}")
        result[profile_id] = value
    return MappingProxyType(result)


_ANNOTATION_REGISTRY = _registry(
    (_CANONICAL, _AGDT, _PROIEL, _PAPYGREEK), "annotation profile registry"
)

_PAPYGREEK_REG = DomainProfile(
    profile_id="papygreek-regularized-v1",
    domains=("documentary Koine", "papyri"),
    source_layer="reg",
    annotation_profile_id="papygreek-agdt-v1",
    normalization=("NFC", "regularized FORM layer"),
    segmentation=("PapyGreek fold sentence boundaries", "PapyGreek word segmentation"),
    evidence=(
        _evidence("neural_papygreek_test", "training/results/papygreek-eval-v3-2026-07-11.json", "PapyGreek regularized fold"),
        _evidence("papygreek_convention_decomposition", "training/results/papygreek-convention-decomp-2026-07-11.json", "PapyGreek convention decomposition; measurement only"),
    ),
    limitations=("scope is descriptive and does not detect documentary domain", "published rows do not establish a universal domain accuracy claim"),
)

_PAPYGREEK_ORIG = DomainProfile(
    profile_id="papygreek-diplomatic-surface-v1",
    domains=("documentary Koine", "papyri"),
    source_layer="orig",
    annotation_profile_id="papygreek-agdt-v1",
    normalization=("NFC", "preserve diplomatic FORM surface"),
    segmentation=("PapyGreek fold sentence boundaries", "PapyGreek word segmentation"),
    evidence=(
        _evidence("neural_papygreek_test", "training/results/papygreek-orig-eval-v2-2026-07-11.json", "PapyGreek regularized and orig rows"),
        _evidence("papygreek_convention_decomposition", "training/results/papygreek-convention-decomp-2026-07-11.json", "PapyGreek convention decomposition; measurement only"),
    ),
    limitations=(
        "orig changes the diplomatic FORM surface only while retaining regularized-layer gold analyses",
        "documented fallback and apparatus behavior remain explicit; no inferred regularization is claimed",
    ),
)

_DOMAIN_REGISTRY = _registry(
    (_PAPYGREEK_REG, _PAPYGREEK_ORIG), "domain profile registry"
)


def list_annotation_profiles() -> tuple[AnnotationProfile, ...]:
    """Return the built-in annotation profiles in stable ID order.

    The returned tuple is immutable; lookup by ID is available through
    :func:`get_annotation_profile`.
    """

    return tuple(_ANNOTATION_REGISTRY.values())


def list_domain_profiles() -> tuple[DomainProfile, ...]:
    """Return the built-in domain profiles in stable ID order."""

    return tuple(_DOMAIN_REGISTRY.values())


def get_annotation_profile(profile_id: str) -> AnnotationProfile:
    """Look up a built-in annotation profile by its exact stable ID."""

    profile_id = _text(profile_id, "profile_id")
    try:
        return cast(AnnotationProfile, _ANNOTATION_REGISTRY[profile_id])
    except KeyError as exc:
        raise ProfileError(f"unknown annotation profile {profile_id!r}") from exc


def get_domain_profile(profile_id: str) -> DomainProfile:
    """Look up a built-in domain profile by its exact stable ID."""

    profile_id = _text(profile_id, "profile_id")
    try:
        return cast(DomainProfile, _DOMAIN_REGISTRY[profile_id])
    except KeyError as exc:
        raise ProfileError(f"unknown domain profile {profile_id!r}") from exc


def canonical_analysis_profile() -> AnalysisProfile:
    """Return the canonical no-postprocessing composed analysis profile."""

    return AnalysisProfile(
        profile_id="pyaegean-canonical-analysis-v1",
        inference_annotation_profile="pyaegean-canonical-v1",
        output_annotation_profile="pyaegean-canonical-v1",
    )
