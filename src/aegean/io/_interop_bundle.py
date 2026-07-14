"""Portable JSON bundles for pyaegean interoperability adapters.

The bundle is deliberately not an opaque spaCy, Stanza, or CLTK serializer.  It
contains the adapter's documented JSON projection, the integrity-bound pyaegean sidecar,
and the conversion report.  Reading a bundle therefore needs no optional target
library and still validates that the native projection and sidecar belong
together.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, cast

from .._atomic import atomic_path
from .interop import (
    MAX_SIDECAR_BYTES,
    SIDECAR_COMMENT_PREFIX,
    InteropDocument,
    InteropReport,
    InteropResult,
    InteropSchemaError,
    decode_sidecar,
    encode_sidecar,
)

__all__ = [
    "BUNDLE_SCHEMA",
    "InteropBundle",
    "bundle_from_document",
    "bundle_from_result",
    "dumps_interop_bundle",
    "loads_interop_bundle",
    "read_interop_bundle",
    "write_interop_bundle",
]

BUNDLE_SCHEMA = "aegean.interop-bundle/v1"
_TARGETS = frozenset({"conllu", "spacy", "stanza", "cltk"})
_MAX_BUNDLE_BYTES = 2 * MAX_SIDECAR_BYTES + 1024 * 1024
_MAX_JSON_DEPTH = 100


def _reject_constant(value: str) -> Any:
    raise InteropSchemaError(f"non-finite JSON number {value}")


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InteropSchemaError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _expect_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise InteropSchemaError(f"{label} has unknown or missing fields")
    return cast(Mapping[str, Any], value)


def _freeze_json(value: Any, *, path: str = "native", depth: int = 0) -> Any:
    """Validate and deeply freeze one JSON-safe value."""
    if depth > _MAX_JSON_DEPTH:
        raise InteropSchemaError("native projection exceeds maximum nesting depth")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InteropSchemaError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, list | tuple):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        )
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise InteropSchemaError(f"{path} contains a non-string object key")
            frozen[key] = _freeze_json(
                item, path=f"{path}.{key}", depth=depth + 1
            )
        return MappingProxyType(frozen)
    raise InteropSchemaError(
        f"{path} contains non-JSON value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_native(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            _thaw_json(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise InteropSchemaError(f"native projection is not JSON-safe: {exc}") from exc
    if len(encoded.encode("utf-8")) > MAX_SIDECAR_BYTES:
        raise InteropSchemaError("native projection exceeds maximum size")
    return encoded


@dataclass(frozen=True, slots=True)
class InteropBundle:
    """One validated, portable adapter bundle.

    ``native`` is the documented JSON projection of the target object, not a
    promise that pyaegean can reconstruct the target library's private object.
    ``document`` recovers the complete pyaegean envelope from the bound sidecar.
    """

    target: str
    target_version: str | None
    native: Mapping[str, Any]
    sidecar: str
    report: InteropReport
    report_sha256: str | None = None
    schema: str = BUNDLE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != BUNDLE_SCHEMA:
            raise InteropSchemaError(f"unsupported interop bundle schema {self.schema!r}")
        if not isinstance(self.target, str):
            raise InteropSchemaError("bundle target must be a string")
        if self.target not in _TARGETS:
            raise InteropSchemaError(f"unsupported interoperability target {self.target!r}")
        if self.target_version is not None and (
            not isinstance(self.target_version, str) or not self.target_version
        ):
            raise InteropSchemaError("target_version must be a non-empty string or null")
        if not isinstance(self.sidecar, str) or not self.sidecar:
            raise InteropSchemaError("bundle sidecar must be a non-empty string")
        if not isinstance(self.report, InteropReport):
            raise TypeError("report must be InteropReport")
        expected_report_sha256 = hashlib.sha256(
            json.dumps(
                self.report.to_dict(),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if self.report_sha256 is None:
            object.__setattr__(self, "report_sha256", expected_report_sha256)
        elif (
            not isinstance(self.report_sha256, str)
            or self.report_sha256 != expected_report_sha256
        ):
            raise InteropSchemaError("bundle report hash mismatch")
        if self.report.target != self.target:
            raise InteropSchemaError("bundle target disagrees with conversion report")
        if self.report.target_version != self.target_version:
            raise InteropSchemaError("bundle target version disagrees with conversion report")
        if self.report.direction != "export":
            raise InteropSchemaError("portable bundle report direction must be export")
        if self.report.lost_fields:
            raise InteropSchemaError("portable bundles require a lossless adapter result")
        if not isinstance(self.native, Mapping):
            raise InteropSchemaError("bundle native projection must be an object")
        frozen = _freeze_json(self.native)
        object.__setattr__(self, "native", frozen)
        native_signature = _canonical_native(frozen)
        decode_sidecar(
            self.sidecar,
            target=self.target,
            native_signature=native_signature,
        )

    @property
    def document(self) -> InteropDocument:
        """Decode the complete pyaegean document after revalidating the binding."""
        envelope = decode_sidecar(
            self.sidecar,
            target=self.target,
            native_signature=_canonical_native(self.native),
        )
        return InteropDocument.from_dict(envelope["payload"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "target": self.target,
            "target_version": self.target_version,
            "native": _thaw_json(self.native),
            "sidecar": self.sidecar,
            "report": self.report.to_dict(),
            "report_sha256": self.report_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InteropBundle":
        item = _expect_keys(
            value,
            {
                "schema",
                "target",
                "target_version",
                "native",
                "sidecar",
                "report",
                "report_sha256",
            },
            "interop bundle",
        )
        report_value = item["report"]
        if not isinstance(report_value, Mapping):
            raise InteropSchemaError("bundle report must be an object")
        return cls(
            target=item["target"],
            target_version=item["target_version"],
            native=item["native"],
            sidecar=item["sidecar"],
            report=InteropReport.from_dict(report_value),
            report_sha256=item["report_sha256"],
            schema=item["schema"],
        )


def _conllu_native_state(value: str) -> dict[str, Any]:
    lines = value.splitlines(keepends=True)
    native = "".join(
        line for line in lines if not line.startswith(SIDECAR_COMMENT_PREFIX)
    )
    return {"conllu": native}


def _native_state(result: InteropResult[Any]) -> Mapping[str, Any]:
    target = result.report.target
    if target == "conllu":
        if not isinstance(result.value, str):
            raise InteropSchemaError("CoNLL-U adapter result must contain text")
        return _conllu_native_state(result.value)
    if target == "spacy":
        from ._interop_spacy import _spacy_native_state

        return _spacy_native_state(result.value)
    if target == "stanza":
        from ._interop_stanza import _stanza_native_state

        return _stanza_native_state(result.value)
    if target == "cltk":
        from ._interop_cltk import _cltk_native_state

        return _cltk_native_state(result.value)
    raise InteropSchemaError(f"unsupported interoperability target {target!r}")


def bundle_from_result(result: InteropResult[Any]) -> InteropBundle:
    """Create a portable bundle from a lossless adapter result."""
    if not isinstance(result, InteropResult):
        raise TypeError("result must be InteropResult")
    if result.sidecar is None:
        raise InteropSchemaError("adapter result has no sidecar to bundle")
    return InteropBundle(
        target=result.report.target,
        target_version=result.report.target_version,
        native=_native_state(result),
        sidecar=result.sidecar,
        report=result.report,
    )


def bundle_from_document(document: InteropDocument, *, target: str) -> InteropBundle:
    """Run one lazy adapter and return its validated portable bundle."""
    if not isinstance(document, InteropDocument):
        raise TypeError("document must be InteropDocument")
    if not isinstance(target, str):
        raise TypeError("target must be a string")
    target = target.casefold()
    if target == "conllu":
        from .interop import to_conllu

        result: InteropResult[Any] = to_conllu(document)
        if result.sidecar is None:
            native = _conllu_native_state(result.value)
            sidecar = encode_sidecar(
                document,
                target="conllu",
                native_signature=_canonical_native(native),
            )
            result = InteropResult(result.value, sidecar, result.report)
    elif target == "spacy":
        from ._interop_spacy import to_spacy

        result = to_spacy(document)
    elif target == "stanza":
        from ._interop_stanza import to_stanza

        result = to_stanza(document)
    elif target == "cltk":
        from ._interop_cltk import to_cltk

        result = to_cltk(document)
    else:
        raise InteropSchemaError(
            "target must be one of: conllu, spacy, stanza, cltk"
        )
    return bundle_from_result(result)


def dumps_interop_bundle(bundle: InteropBundle) -> str:
    """Serialize a bundle as deterministic UTF-8 JSON text."""
    if not isinstance(bundle, InteropBundle):
        raise TypeError("bundle must be InteropBundle")
    try:
        output = json.dumps(
            bundle.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise InteropSchemaError(f"bundle is not JSON-safe: {exc}") from exc
    if len(output.encode("utf-8")) > _MAX_BUNDLE_BYTES:
        raise InteropSchemaError("interop bundle exceeds maximum size")
    return output


def loads_interop_bundle(value: str) -> InteropBundle:
    """Parse and validate deterministic bundle JSON text."""
    if not isinstance(value, str):
        raise TypeError("bundle JSON must be a string")
    if len(value.encode("utf-8")) > _MAX_BUNDLE_BYTES:
        raise InteropSchemaError("interop bundle exceeds maximum size")
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except InteropSchemaError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise InteropSchemaError("invalid interop bundle JSON") from exc
    if not isinstance(parsed, Mapping):
        raise InteropSchemaError("interop bundle must be a JSON object")
    return InteropBundle.from_dict(parsed)


def read_interop_bundle(path: str | Path) -> InteropBundle:
    """Read a bounded UTF-8 bundle from one local path."""
    source = Path(path)
    try:
        with source.open("rb") as handle:
            raw = handle.read(_MAX_BUNDLE_BYTES + 1)
        if len(raw) > _MAX_BUNDLE_BYTES:
            raise InteropSchemaError("interop bundle exceeds maximum size")
        value = raw.decode("utf-8")
    except InteropSchemaError:
        raise
    except (OSError, UnicodeError) as exc:
        raise InteropSchemaError(f"could not read interop bundle {source}: {exc}") from exc
    return loads_interop_bundle(value)


def write_interop_bundle(bundle: InteropBundle, path: str | Path) -> Path:
    """Atomically write one validated bundle and return its path."""
    target = Path(path)
    output = dumps_interop_bundle(bundle)
    try:
        with atomic_path(target) as temporary:
            temporary.write_text(output, encoding="utf-8", newline="")
    except OSError as exc:
        raise InteropSchemaError(f"could not write interop bundle {target}: {exc}") from exc
    return target
