"""Evidence-scoped confidence records, metrics, and review policies.

This module is deliberately independent of NumPy and of the neural runtime.  It
contains the small, serialisable pieces needed to *describe* a confidence value and
the evidence that supports it; producing a value from model logits remains the job of
``aegean.greek.calibrate``.  In particular, a missing value is never silently changed
to zero and a calibration with a broader scope is never treated as an exact match.

The classes in this module are additive.  The older :class:`Calibration` record in
``calibrate.py`` keeps its original constructor and JSON representation unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "AbstentionPolicy",
    "CalibrationEntry",
    "CalibrationRegistry",
    "CalibrationResolution",
    "ConfidenceResult",
    "TokenConfidence",
    "SentenceConfidence",
    "CoverageRiskPoint",
    "PolicyDecision",
    "brier_score",
    "canonical_json",
    "canonical_sha256",
    "coverage_risk_curve",
]


# Stable reason strings are intentionally plain strings so receipts and JSON remain
# forward-compatible with callers that do not import this module.
UNAVAILABLE_MISSING_CALIBRATION = "missing_calibration"
UNAVAILABLE_UNSUPPORTED_TASK = "unsupported_task"
UNAVAILABLE_UNSUPPORTED_SOURCE = "unsupported_source"
UNAVAILABLE_UNSUPPORTED_DOMAIN = "unsupported_domain"
UNAVAILABLE_NO_THRESHOLD = "no_threshold_for_task"
UNAVAILABLE_CONFIDENCE = "confidence_unavailable"


def canonical_json(value: Any) -> str:
    """Return the canonical JSON encoding used for confidence hashes.

    Canonical encodings are UTF-8, compact, key-sorted, and reject non-finite JSON
    numbers.  Rejecting NaN/Infinity here matters: the standard ``json`` encoder
    otherwise emits non-standard tokens that could hash differently across readers.
    """

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not canonically JSON-serialisable: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    """Return the SHA-256 of :func:`canonical_json` encoded as UTF-8."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_no_duplicate_keys(pairs: list[tuple[Any, Any]]) -> dict[Any, Any]:
    """Decode one JSON object while rejecting ambiguous duplicate member names."""

    result: dict[Any, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _text(value: Any, field: str, *, allow_none: bool = True) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _number(value: Any, field: str, *, low: float | None = None, high: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be a finite number")
    if low is not None and out < low:
        raise ValueError(f"{field} must be >= {low}")
    if high is not None and out > high:
        raise ValueError(f"{field} must be <= {high}")
    return out


def _count(value: Any, field: str, *, allow_none: bool = True) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return int(value)


@dataclass(frozen=True, slots=True)
class CalibrationEntry:
    """One task/model/source/domain calibration record.

    ``source`` and ``domain`` set to ``None`` mean a broader entry only when
    ``fallback=True`` is explicitly set.  They are not wildcards when resolving an
    entry with a missing query scope; a caller must ask for an unscoped value
    explicitly.  ``temperature`` is required for the legacy temperature calibrator;
    a logit-affine calibrator instead carries explicit finite ``slope`` and
    ``intercept`` parameters.  The record still validates all evidence fields.
    """

    model: str
    task: str
    source: str | None = None
    domain: str | None = None
    fallback: bool = False
    temperature: float | None = None
    n: int | None = None
    ece: float | None = None
    brier: float | None = None
    schema_version: int = 2
    notes: str = ""
    calibrator: str = "temperature"
    parameters: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise ValueError("schema_version must be an integer")
        if self.schema_version not in (1, 2):
            raise ValueError("unsupported calibration schema_version")
        object.__setattr__(self, "model", _text(self.model, "model", allow_none=False))
        object.__setattr__(self, "task", _text(self.task, "task", allow_none=False))
        object.__setattr__(self, "source", _text(self.source, "source"))
        object.__setattr__(self, "domain", _text(self.domain, "domain"))
        if not isinstance(self.fallback, bool):
            raise ValueError("fallback must be a boolean")
        if self.fallback and self.source is not None and self.domain is not None:
            raise ValueError("a fallback entry must leave source or domain unscoped")
        if self.temperature is not None:
            _number(self.temperature, "temperature", low=0.0)
            if float(self.temperature) == 0.0:
                raise ValueError("temperature must be > 0")
        _count(self.n, "n")
        if self.ece is not None:
            _number(self.ece, "ece", low=0.0, high=1.0)
        if self.brier is not None:
            _number(self.brier, "brier", low=0.0, high=1.0)
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        object.__setattr__(self, "notes", self.notes.strip())
        if not isinstance(self.calibrator, str):
            raise ValueError("calibrator must be 'temperature' or 'logit_affine'")
        object.__setattr__(self, "calibrator", self.calibrator.strip())
        if self.calibrator not in {"temperature", "logit_affine"}:
            raise ValueError("calibrator must be 'temperature' or 'logit_affine'")
        if self.schema_version == 1 and self.calibrator != "temperature":
            raise ValueError("schema_version 1 supports only the temperature calibrator")
        raw_parameters: Any = self.parameters
        if isinstance(raw_parameters, Mapping):
            raw_items = list(raw_parameters.items())
        else:
            try:
                raw_items = list(raw_parameters)
            except TypeError as exc:
                raise ValueError("parameters must be a mapping or key/value sequence") from exc
        normalized: list[tuple[str, float]] = []
        seen: set[str] = set()
        for item in raw_items:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError("parameters must contain (name, value) pairs")
            name = item[0]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("parameter names must be unique, non-empty strings")
            name = name.strip()
            if name in seen:
                raise ValueError("parameter names must be unique, non-empty strings")
            seen.add(name)
            normalized.append((name, _number(item[1], f"parameters[{name}]")))
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "parameters", tuple(normalized))
        values = dict(normalized)
        if self.calibrator == "temperature":
            if self.temperature is None:
                raise ValueError("temperature calibrator requires temperature")
            if values and set(values) != {"temperature"}:
                raise ValueError("temperature calibrator parameters may only name temperature")
            if "temperature" in values and values["temperature"] != float(self.temperature):
                raise ValueError("temperature parameter disagrees with temperature")
        else:
            if set(values) != {"intercept", "slope"}:
                raise ValueError("logit_affine calibrator requires slope and intercept parameters")
            if values["slope"] <= 0.0:
                raise ValueError("logit_affine slope must be > 0 for monotonicity")
            if self.temperature is not None:
                raise ValueError("logit_affine calibrator cannot also set temperature")

    @property
    def decision_path(self) -> str | None:
        """Alias for ``source`` used by lemma calibration callers."""

        return self.source

    @property
    def calibration_id(self) -> str:
        """Stable identity of this entry's canonical payload."""

        return canonical_sha256(self.to_dict(include_id=False))

    @property
    def sha256(self) -> str:
        """Alias for :attr:`calibration_id` suitable for receipts."""

        return self.calibration_id

    def to_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        """Return a JSON-ready, deterministic mapping for this entry."""

        out: dict[str, Any] = {
            "schema_version": int(self.schema_version),
            "model": self.model,
            "task": self.task,
            "source": self.source,
            "domain": self.domain,
            "fallback": self.fallback,
            "temperature": None if self.temperature is None else float(self.temperature),
            "n": self.n,
            "ece": None if self.ece is None else float(self.ece),
            "brier": None if self.brier is None else float(self.brier),
            "notes": self.notes,
            "calibrator": self.calibrator,
            "parameters": {key: float(value) for key, value in self.parameters},
        }
        if include_id:
            out["calibration_id"] = self.calibration_id
        return out

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CalibrationEntry":
        if not isinstance(value, Mapping):
            raise TypeError("calibration entry must be a JSON object")
        allowed = {
            "schema_version",
            "model",
            "task",
            "source",
            "decision_path",
            "domain",
            "fallback",
            "temperature",
            "n",
            "ece",
            "brier",
            "notes",
            "calibrator",
            "parameters",
            "calibration_id",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"calibration entry has unknown field(s): {sorted(unknown)!r}")
        if "source" in value and "decision_path" in value and value["source"] != value["decision_path"]:
            raise ValueError("source and decision_path disagree")
        source = value.get("source", value.get("decision_path"))
        model = _text(value.get("model"), "model", allow_none=False)
        task = _text(value.get("task"), "task", allow_none=False)
        assert model is not None and task is not None
        entry = cls(
            model=model,
            task=task,
            source=source,
            domain=value.get("domain"),
            fallback=value.get("fallback", False),
            temperature=value.get("temperature"),
            n=value.get("n"),
            ece=value.get("ece"),
            brier=value.get("brier"),
            schema_version=value.get("schema_version", 2),
            notes=value.get("notes", ""),
            calibrator=value.get("calibrator", "temperature"),
            parameters=value.get("parameters", {}),
        )
        supplied = value.get("calibration_id")
        if supplied is not None and (not isinstance(supplied, str) or supplied != entry.calibration_id):
            raise ValueError("calibration_id does not match the canonical entry")
        return entry

    @property
    def canonical(self) -> str:
        """Canonical parameter payload used to derive :attr:`calibration_id`."""

        return canonical_json(self.to_dict(include_id=False))

    def calibrate(self, raw: Any) -> Any:
        """Apply this entry's explicitly fitted monotone calibrator.

        Temperature scaling accepts one class-logit vector and delegates to the
        existing lazy NumPy implementation.  Logit-affine calibration accepts one raw
        probability, transforms its logit, and returns a probability.  The distinct
        input contracts prevent a scalar probability from being mistaken for a raw
        logit; exact 0 and 1 are handled without taking ``log(0)``.
        """

        if self.calibrator == "temperature":
            if isinstance(raw, (str, bytes)) or isinstance(raw, (int, float, bool)):
                raise ValueError("temperature calibration requires a class-logit vector")
            try:
                values = tuple(raw)
            except TypeError as exc:
                raise ValueError("temperature calibration requires a class-logit vector") from exc
            if len(values) < 2:
                raise ValueError("temperature calibration requires a class-logit vector")
            for index, item in enumerate(values):
                _number(item, f"logit[{index}]")
            from .calibrate import temperature_softmax

            assert self.temperature is not None
            calibrated = temperature_softmax(values, self.temperature)
            if getattr(calibrated, "ndim", 1) != 1:
                raise ValueError("temperature calibration requires one class-logit vector")
            return calibrated

        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError("logit_affine calibration requires one raw probability")
        probability = _number(raw, "raw probability", low=0.0, high=1.0)
        if probability == 0.0:
            return 0.0
        if probability == 1.0:
            return 1.0
        params = dict(self.parameters)
        logit = math.log(probability / (1.0 - probability))
        transformed = params["slope"] * logit + params["intercept"]
        if transformed >= 0:
            z = math.exp(-transformed)
            return 1.0 / (1.0 + z)
        z = math.exp(transformed)
        return z / (1.0 + z)


@dataclass(frozen=True, slots=True)
class CalibrationResolution:
    """Result of deterministic calibration lookup.

    ``entry`` is ``None`` on failure; ``reason`` is then always a stable explicit
    reason string.  ``fallback`` is true only when a broader (``None`` source/domain)
    entry was selected instead of an exact scope match.
    """

    entry: CalibrationEntry | None
    model: str
    task: str
    source: str | None
    domain: str | None
    scope: str
    fallback: bool = False
    reason: str | None = None

    @property
    def available(self) -> bool:
        return self.entry is not None

    @property
    def unavailable_reason(self) -> str | None:
        return self.reason if self.entry is None else None


    @property
    def calibration(self) -> CalibrationEntry | None:
        return self.entry


@dataclass(frozen=True, slots=True)
class CalibrationRegistry:
    """Versioned collection of calibration entries with scope-aware resolution."""

    entries: tuple[CalibrationEntry, ...] = ()
    schema_version: int = 2

    def __post_init__(self) -> None:
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise ValueError("schema_version must be an integer")
        if self.schema_version != 2:
            raise ValueError("calibration registry schema_version must be 2")
        values = tuple(self.entries)
        if any(not isinstance(item, CalibrationEntry) for item in values):
            raise TypeError("entries must contain CalibrationEntry values")
        keys = [(x.model, x.task, x.source, x.domain) for x in values]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate calibration scope")
        values = tuple(
            sorted(
                values,
                key=lambda item: (
                    item.model,
                    item.task,
                    item.source is None,
                    item.source or "",
                    item.domain is None,
                    item.domain or "",
                    item.fallback,
                    item.calibration_id,
                ),
            )
        )
        object.__setattr__(self, "entries", values)

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.to_dict(include_hash=False))

    @property
    def canonical(self) -> str:
        return canonical_json(self.to_dict(include_hash=False))

    @property
    def calibration_id(self) -> str:
        return self.sha256

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": 2,
            "entries": [
                item.to_dict()
                for item in sorted(
                    self.entries,
                    key=lambda item: (
                        item.model,
                        item.task,
                        item.source is None,
                        item.source or "",
                        item.domain is None,
                        item.domain or "",
                        item.fallback,
                        item.calibration_id,
                    ),
                )
            ],
        }
        if include_hash:
            out["sha256"] = self.sha256
        return out

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CalibrationRegistry":
        if not isinstance(value, Mapping):
            raise TypeError("calibration registry must be a JSON object")
        # A v2 registry is intentionally strict.  A schema-1 aggregate Calibration
        # remains readable through ``from_legacy`` below without relabelling it.
        if "schema_version" not in value:
            if "temperature" in value:
                return cls.from_legacy(value)
            raise ValueError("calibration registry requires schema_version")
        if value.get("schema_version") != 2:
            raise ValueError("unsupported calibration registry schema_version")
        unknown = set(value) - {"schema_version", "entries", "sha256"}
        if unknown:
            raise ValueError(f"calibration registry has unknown field(s): {sorted(unknown)!r}")
        entries = value.get("entries")
        if not isinstance(entries, list):
            raise TypeError("calibration registry entries must be a JSON array")
        registry = cls(tuple(CalibrationEntry.from_dict(item) for item in entries))
        supplied = value.get("sha256")
        if supplied is not None and (not isinstance(supplied, str) or supplied != registry.sha256):
            raise ValueError("calibration registry sha256 does not match canonical JSON")
        return registry

    @classmethod
    def from_legacy(cls, value: Mapping[str, Any]) -> "CalibrationRegistry":
        """Read schema-1 ``Calibration.to_dict`` as unscoped aggregate evidence.

        The legacy JSON has no model/source/domain fields.  Only the known published
        ``grc-joint-v3`` identity is attached when it is present in ``fitted_on``;
        source and domain intentionally remain ``None`` so the record cannot be
        mistaken for source- or domain-specific evidence.
        """

        from .calibrate import Calibration  # local import avoids module cycle at import time

        try:
            legacy = Calibration.from_dict(dict(value))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid legacy calibration: {exc}") from exc
        fitted = legacy.fitted_on.lower().replace(" ", "-")
        model = "grc-joint-v3" if "grc-joint-v3" in fitted else "legacy"
        entries = tuple(
            CalibrationEntry(
                model=model,
                task=head,
                source=None,
                domain=None,
                fallback=True,
                temperature=legacy.temperature[head],
                n=legacy.n.get(head),
                ece=legacy.ece_after.get(head),
                schema_version=1,
                notes="schema-1 aggregate calibration; not source- or domain-specific",
            )
            for head in ("upos", "lemma")
        )
        return cls(entries)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(canonical_json(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationRegistry":
        try:
            raw = json.loads(
                Path(path).read_text(encoding="utf-8"),
                object_pairs_hook=_json_no_duplicate_keys,
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid calibration registry JSON: {exc}") from exc
        return cls.from_dict(raw)

    def resolve(
        self,
        model: str,
        task: str,
        source: str | None = None,
        domain: str | None = None,
        *,
        decision_path: str | None = None,
    ) -> CalibrationResolution:
        """Resolve exact scope first, then an explicitly broader fallback.

        Rank order is exact source+domain, exact source with unscoped domain,
        unscoped source with exact domain, then fully unscoped.  A missing query scope
        never borrows a narrower entry.  Duplicate scopes are rejected at construction,
        so the result is deterministic regardless of JSON entry order.
        """

        normalized_model = _text(model, "model", allow_none=False)
        normalized_task = _text(task, "task", allow_none=False)
        assert normalized_model is not None and normalized_task is not None
        source = _text(source, "source")
        if decision_path is not None:
            normalized_path = _text(decision_path, "decision_path", allow_none=False)
            assert normalized_path is not None
            if source is not None and source != normalized_path:
                raise ValueError("source and decision_path disagree")
            source = normalized_path
        domain = _text(domain, "domain")
        model = normalized_model
        task = normalized_task
        candidates = [x for x in self.entries if x.model == model and x.task == task]
        if not candidates:
            return CalibrationResolution(
                None, model, task, source, domain, "unavailable", reason=UNAVAILABLE_UNSUPPORTED_TASK
            )

        ranked: list[tuple[int, CalibrationEntry]] = []
        for entry in candidates:
            source_match = entry.source == source
            domain_match = entry.domain == domain
            # An unscoped entry is a fallback only when the query supplied that scope.
            source_fallback = entry.fallback and entry.source is None and source is not None
            domain_fallback = entry.fallback and entry.domain is None and domain is not None
            if not source_match and not source_fallback:
                continue
            if not domain_match and not domain_fallback:
                continue
            rank = (2 if source_match else 0) + (1 if domain_match else 0)
            ranked.append((rank, entry))
        if not ranked:
            source_supported = source is None or any(
                item.source == source or (item.fallback and item.source is None)
                for item in candidates
            )
            reason = (
                UNAVAILABLE_UNSUPPORTED_SOURCE
                if source is not None and not source_supported
                else UNAVAILABLE_UNSUPPORTED_DOMAIN
                if domain is not None
                else UNAVAILABLE_MISSING_CALIBRATION
            )
            return CalibrationResolution(None, model, task, source, domain, "unavailable", reason=reason)

        # Duplicate scope was rejected; this tie-break only makes order independent
        # when two distinct broad entries have the same rank.
        rank, entry = sorted(
            ranked,
            key=lambda item: (
                -item[0],
                item[1].source is None,
                item[1].domain is None,
                item[1].calibration_id,
            ),
        )[0]
        exact = rank == 3 and not entry.fallback
        scope = "exact" if exact else ("source_fallback" if entry.source is None else "domain_fallback")
        if entry.source is None and entry.domain is None and not exact:
            scope = "global_fallback"
        return CalibrationResolution(
            entry,
            model,
            task,
            source,
            domain,
            scope,
            fallback=not exact,
        )

@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    """A confidence value or an explicit unavailable reason."""

    task: str
    value: float | None
    reason: str | None = None
    calibration_id: str | None = None
    scope: str | None = None
    model: str | None = None
    source: str | None = None
    domain: str | None = None
    n: int | None = None
    ece: float | None = None
    brier: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task", _text(self.task, "task", allow_none=False))
        if self.value is None:
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("an unavailable confidence requires an explicit reason")
            object.__setattr__(self, "reason", self.reason.strip())
        else:
            _number(self.value, "confidence", low=0.0, high=1.0)
            if self.reason is not None:
                raise ValueError("an available confidence cannot have an unavailable reason")
            if not isinstance(self.model, str) or not self.model.strip():
                raise ValueError("an available confidence requires its model")
            if not isinstance(self.scope, str) or not self.scope.strip():
                raise ValueError("an available confidence requires its evidence scope")
            if self.calibration_id is None:
                raise ValueError("an available confidence requires calibration_id")
            if self.ece is None and self.brier is None:
                raise ValueError("an available confidence requires a measured calibration metric")
        object.__setattr__(self, "model", _text(self.model, "model"))
        object.__setattr__(self, "source", _text(self.source, "source"))
        object.__setattr__(self, "domain", _text(self.domain, "domain"))
        if self.calibration_id is not None and (
            not isinstance(self.calibration_id, str)
            or len(self.calibration_id) != 64
            or any(char not in "0123456789abcdef" for char in self.calibration_id)
        ):
            raise ValueError("calibration_id must be a lowercase SHA-256 digest or None")
        if self.scope is not None:
            if not isinstance(self.scope, str) or not self.scope.strip():
                raise ValueError("scope must be a non-empty string or None")
            object.__setattr__(self, "scope", self.scope.strip())
        _count(self.n, "n")
        if self.value is not None and (self.n is None or self.n <= 0):
            raise ValueError("an available confidence requires n > 0")
        if self.ece is not None:
            _number(self.ece, "ece", low=0.0, high=1.0)
        if self.brier is not None:
            _number(self.brier, "brier", low=0.0, high=1.0)

    @property
    def available(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        value = self._payload()
        value["sha256"] = self.sha256
        return value

    def _payload(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "value": None if self.value is None else float(self.value),
            "reason": self.reason,
            "calibration_id": self.calibration_id,
            "scope": self.scope,
            "model": self.model,
            "source": self.source,
            "domain": self.domain,
            "n": self.n,
            "ece": None if self.ece is None else float(self.ece),
            "brier": None if self.brier is None else float(self.brier),
        }

    @property
    def canonical(self) -> str:
        return canonical_json(self._payload())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConfidenceResult":
        if not isinstance(value, Mapping):
            raise TypeError("confidence result must be a JSON object")
        expected = {
            "task",
            "value",
            "reason",
            "calibration_id",
            "scope",
            "model",
            "source",
            "domain",
            "n",
            "ece",
            "brier",
            "sha256",
        }
        if set(value) != expected:
            missing = expected - set(value)
            unknown = set(value) - expected
            detail = f"missing {sorted(missing)!r}" if missing else f"unknown {sorted(unknown)!r}"
            raise ValueError(f"confidence result has invalid fields ({detail})")
        result = cls(
            task=value["task"],
            value=value["value"],
            reason=value["reason"],
            calibration_id=value["calibration_id"],
            scope=value["scope"],
            model=value["model"],
            source=value["source"],
            domain=value["domain"],
            n=value["n"],
            ece=value["ece"],
            brier=value["brier"],
        )
        if not isinstance(value["sha256"], str) or value["sha256"] != result.sha256:
            raise ValueError("confidence result sha256 does not match canonical JSON")
        return result


@dataclass(frozen=True, slots=True)
class TokenConfidence:
    """Immutable per-token confidence values and optional review decisions."""

    index: int
    upos: ConfidenceResult | None = None
    xpos: ConfidenceResult | None = None
    feats: ConfidenceResult | None = None
    lemma: ConfidenceResult | None = None
    head: ConfidenceResult | None = None
    relation: ConfidenceResult | None = None
    policy: tuple["PolicyDecision", ...] = ()

    def __post_init__(self) -> None:
        _count(self.index, "index", allow_none=False)
        if self.index is None:
            raise ValueError("index is required")
        fields = ("upos", "xpos", "feats", "lemma", "head", "relation")
        for field_name in fields:
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, ConfidenceResult):
                    raise TypeError(f"{field_name} must be a ConfidenceResult or None")
                if value.task != field_name:
                    raise ValueError(f"{field_name} confidence task mismatch: {value.task!r}")
        decisions = tuple(self.policy)
        if any(not isinstance(item, PolicyDecision) for item in decisions):
            raise TypeError("policy must contain PolicyDecision values")
        decision_tasks = [item.task for item in decisions]
        if len(set(decision_tasks)) != len(decision_tasks):
            raise ValueError("token confidence policy tasks must be unique")
        if any(task not in fields for task in decision_tasks):
            raise ValueError("token confidence policy task must name a token confidence")
        if any(getattr(self, task) is None for task in decision_tasks):
            raise ValueError("token confidence policy task requires its confidence result")
        policy_hashes = {item.policy_sha256 for item in decisions}
        if len(policy_hashes) > 1:
            raise ValueError("token confidence policy decisions must share one policy hash")
        for item in decisions:
            result = getattr(self, item.task)
            assert isinstance(result, ConfidenceResult)
            if item.confidence != result.value:
                raise ValueError("token confidence policy confidence disagrees with its result")
        object.__setattr__(self, "policy", decisions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "upos": None if self.upos is None else self.upos.to_dict(),
            "xpos": None if self.xpos is None else self.xpos.to_dict(),
            "feats": None if self.feats is None else self.feats.to_dict(),
            "lemma": None if self.lemma is None else self.lemma.to_dict(),
            "head": None if self.head is None else self.head.to_dict(),
            "relation": None if self.relation is None else self.relation.to_dict(),
            "policy": [item.to_dict() for item in self.policy],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TokenConfidence":
        if not isinstance(value, Mapping):
            raise TypeError("token confidence must be a JSON object")
        expected = {"index", "upos", "xpos", "feats", "lemma", "head", "relation", "policy"}
        if set(value) != expected:
            raise ValueError("token confidence has invalid fields")
        kwargs: dict[str, Any] = {"index": value["index"]}
        for field_name in ("upos", "xpos", "feats", "lemma", "head", "relation"):
            raw = value[field_name]
            kwargs[field_name] = None if raw is None else ConfidenceResult.from_dict(raw)
        policies = value["policy"]
        if not isinstance(policies, list):
            raise TypeError("token confidence policy must be a JSON array")
        kwargs["policy"] = tuple(_policy_from_dict(item) for item in policies)
        return cls(**kwargs)


@dataclass(frozen=True, slots=True)
class SentenceConfidence:
    """Immutable sentence-level confidence and optional review decision."""

    result: ConfidenceResult
    components: tuple[str, ...] = ()
    policy: "PolicyDecision | None" = None

    def __post_init__(self) -> None:
        if not isinstance(self.result, ConfidenceResult) or self.result.task != "sentence":
            raise ValueError("sentence result must be a sentence ConfidenceResult")
        components = tuple(self.components)
        if any(not isinstance(item, str) or not item.strip() for item in components):
            raise ValueError("sentence components must be non-empty strings")
        object.__setattr__(self, "components", tuple(item.strip() for item in components))
        if self.policy is not None and not isinstance(self.policy, PolicyDecision):
            raise TypeError("sentence policy must be a PolicyDecision or None")
        if self.policy is not None and self.policy.task != "sentence":
            raise ValueError("sentence policy decision must target sentence")
        if self.policy is not None:
            if self.policy.confidence != self.result.value:
                raise ValueError("sentence policy confidence disagrees with its result")

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.to_dict(),
            "components": list(self.components),
            "policy": None if self.policy is None else self.policy.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SentenceConfidence":
        if not isinstance(value, Mapping) or set(value) != {"result", "components", "policy"}:
            raise ValueError("sentence confidence has invalid fields")
        components = value["components"]
        if not isinstance(components, list):
            raise TypeError("sentence confidence components must be a JSON array")
        policy = value["policy"]
        return cls(
            result=ConfidenceResult.from_dict(value["result"]),
            components=tuple(components),
            policy=None if policy is None else _policy_from_dict(policy),
        )


def _policy_from_dict(value: Mapping[str, Any]) -> "PolicyDecision":
    if not isinstance(value, Mapping):
        raise TypeError("policy decision must be a JSON object")
    expected = {"task", "action", "confidence", "threshold", "reason", "policy_sha256"}
    if set(value) != expected:
        raise ValueError("policy decision has invalid fields")
    try:
        return PolicyDecision(
            task=value["task"],
            action=value["action"],
            confidence=value["confidence"],
            threshold=value["threshold"],
            reason=value["reason"],
            policy_sha256=value["policy_sha256"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid policy decision: {exc}") from exc


def _validated_vectors(probs: Iterable[Any], correct: Iterable[Any]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if isinstance(probs, (str, bytes)) or isinstance(correct, (str, bytes)):
        raise ValueError("probs and correct must be numeric sequences")
    try:
        p = tuple(probs)
        y_raw = tuple(correct)
    except TypeError as exc:
        raise ValueError("probs and correct must be iterable") from exc
    if len(p) != len(y_raw):
        raise ValueError("probs and correct must have the same length")
    y: list[float] = []
    out: list[float] = []
    for i, value in enumerate(p):
        out.append(_number(value, f"probs[{i}]", low=0.0, high=1.0))
    for i, value in enumerate(y_raw):
        if isinstance(value, bool):
            y.append(float(value))
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and float(value) in (0.0, 1.0):
            y.append(float(value))
        else:
            raise ValueError(f"correct[{i}] must be 0 or 1")
    return tuple(out), tuple(y)


def brier_score(probs: Iterable[Any], correct: Iterable[Any]) -> float:
    """Return the binary Brier score (mean squared probability error).

    Empty vectors return ``0.0`` for consistency with :func:`calibrate.ece`; callers
    that need an empirical support count should retain it separately.
    """

    p, y = _validated_vectors(probs, correct)
    if not p:
        return 0.0
    return sum((a - b) ** 2 for a, b in zip(p, y)) / len(p)


@dataclass(frozen=True, slots=True)
class CoverageRiskPoint:
    """One point in an explicit threshold coverage-risk curve."""

    threshold: float
    coverage: float
    risk: float | None
    n_accepted: int
    n_total: int

    def __post_init__(self) -> None:
        _number(self.threshold, "threshold", low=0.0, high=1.0)
        _number(self.coverage, "coverage", low=0.0, high=1.0)
        if self.risk is not None:
            _number(self.risk, "risk", low=0.0, high=1.0)
        _count(self.n_accepted, "n_accepted", allow_none=False)
        _count(self.n_total, "n_total", allow_none=False)
        if self.n_accepted > self.n_total:
            raise ValueError("n_accepted cannot exceed n_total")
        expected = self.n_accepted / self.n_total if self.n_total else 0.0
        if abs(self.coverage - expected) > 1e-12:
            raise ValueError("coverage does not match n_accepted / n_total")
        if self.n_accepted == 0 and self.risk is not None:
            raise ValueError("risk must be None when no item is accepted")

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold": float(self.threshold),
            "coverage": float(self.coverage),
            "risk": None if self.risk is None else float(self.risk),
            "n_accepted": self.n_accepted,
            "n_total": self.n_total,
        }


def coverage_risk_curve(
    probs: Iterable[Any], correct: Iterable[Any], thresholds: Sequence[Any]
) -> tuple[CoverageRiskPoint, ...]:
    """Return deterministic coverage-risk points for caller-supplied thresholds.

    Thresholds are deduplicated and sorted ascending; acceptance uses ``p >= t``.
    No thresholds are invented by this function.  Risk is ``None`` (not zero) when a
    threshold accepts no item, preserving the distinction between no evidence and no
    observed errors.
    """

    if thresholds is None or isinstance(thresholds, (str, bytes)):
        raise ValueError("thresholds must be an explicit sequence")
    try:
        ts = sorted({_number(t, "threshold", low=0.0, high=1.0) for t in thresholds})
    except TypeError as exc:
        raise ValueError("thresholds must be an explicit sequence") from exc
    if not ts:
        raise ValueError("thresholds must not be empty")
    p, y = _validated_vectors(probs, correct)
    if not p:
        raise ValueError("coverage-risk metrics require at least one item")
    n_total = len(p)
    points: list[CoverageRiskPoint] = []
    for threshold in ts:
        accepted = [i for i, value in enumerate(p) if value >= threshold]
        n = len(accepted)
        coverage = n / n_total
        risk = None if n == 0 else sum(1.0 - y[i] for i in accepted) / n
        points.append(CoverageRiskPoint(threshold, coverage, risk, n, n_total))
    return tuple(points)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of applying an :class:`AbstentionPolicy` to one value."""

    task: str
    action: str
    confidence: float | None
    threshold: float | None
    reason: str | None
    policy_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "task", _text(self.task, "task", allow_none=False))
        if not isinstance(self.action, str) or self.action not in {"accept", "review", "unavailable"}:
            raise ValueError("policy decision action must be accept, review, or unavailable")
        if self.confidence is not None:
            _number(self.confidence, "confidence", low=0.0, high=1.0)
        if self.threshold is not None:
            _number(self.threshold, "threshold", low=0.0, high=1.0)
        if self.action == "unavailable":
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("unavailable policy decisions require a reason")
            object.__setattr__(self, "reason", self.reason.strip())
        else:
            if self.confidence is None:
                raise ValueError("available policy decisions require confidence")
            if self.threshold is None:
                raise ValueError("available policy decisions require threshold")
            if self.action == "accept" and self.confidence < self.threshold:
                raise ValueError("accept policy decisions require confidence >= threshold")
            if self.action == "review" and self.confidence >= self.threshold:
                raise ValueError("review policy decisions require confidence < threshold")
            if self.reason is not None:
                raise ValueError("available policy decisions cannot carry an unavailable reason")
        if (
            not isinstance(self.policy_sha256, str)
            or len(self.policy_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.policy_sha256)
        ):
            raise ValueError("policy_sha256 must be a lowercase SHA-256 digest")

    @property
    def status(self) -> str:
        return self.action

    @property
    def available(self) -> bool:
        return self.action != "unavailable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "action": self.action,
            "confidence": self.confidence,
            "threshold": self.threshold,
            "reason": self.reason,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True, slots=True, init=False)
class AbstentionPolicy:
    """Immutable, explicitly configured accept/review policy.

    ``thresholds`` is required from the caller and has no bundled defaults.  A task
    without a threshold, or a confidence of ``None``, produces ``unavailable`` rather
    than accepting, reviewing by an invented threshold, or converting ``None`` to
    ``0``.  The canonical payload and SHA-256 travel with every decision.
    """

    thresholds: tuple[tuple[str, float], ...]
    schema_version: int
    name: str

    def __init__(
        self,
        thresholds: Mapping[str, Any] | Iterable[tuple[str, Any]],
        *,
        name: str = "",
        schema_version: int = 1,
    ) -> None:
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
            raise ValueError("policy schema_version must be 1")
        if not isinstance(name, str):
            raise ValueError("policy name must be a string")
        name = name.strip()
        if isinstance(thresholds, Mapping):
            items = list(thresholds.items())
        elif isinstance(thresholds, (str, bytes)):
            raise ValueError("thresholds must be a mapping or key/value sequence")
        else:
            try:
                items = list(thresholds)
            except TypeError as exc:
                raise ValueError("thresholds must be a mapping or key/value sequence") from exc
        normalized: list[tuple[str, float]] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError("thresholds must contain (task, threshold) pairs")
            task = _text(item[0], "task", allow_none=False)
            assert task is not None
            if task in seen:
                raise ValueError(f"duplicate threshold for task {task!r}")
            seen.add(task)
            normalized.append((task, _number(item[1], f"threshold[{task}]", low=0.0, high=1.0)))
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "thresholds", tuple(normalized))
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "name", name)

    @property
    def threshold_map(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.thresholds))

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "name": self.name,
            "thresholds": {task: float(value) for task, value in self.thresholds},
        }
        if include_hash:
            out["sha256"] = self.sha256
        return out

    @property
    def canonical(self) -> str:
        return canonical_json(self.to_dict(include_hash=False))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical.encode("utf-8")).hexdigest()

    @property
    def policy_id(self) -> str:
        return self.sha256

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AbstentionPolicy":
        if not isinstance(value, Mapping):
            raise TypeError("abstention policy must be a JSON object")
        unknown = set(value) - {"schema_version", "name", "thresholds", "sha256"}
        if unknown:
            raise ValueError(f"abstention policy has unknown field(s): {sorted(unknown)!r}")
        if value.get("schema_version") != 1:
            raise ValueError("unsupported policy schema_version")
        thresholds = value.get("thresholds")
        if not isinstance(thresholds, Mapping):
            raise TypeError("abstention policy thresholds must be a JSON object")
        policy = cls(thresholds, name=value.get("name", ""), schema_version=1)
        supplied = value.get("sha256")
        if supplied is not None and (not isinstance(supplied, str) or supplied != policy.sha256):
            raise ValueError("abstention policy sha256 does not match canonical JSON")
        return policy

    def save(self, path: str | Path) -> None:
        Path(path).write_text(canonical_json(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "AbstentionPolicy":
        try:
            raw = json.loads(
                Path(path).read_text(encoding="utf-8"),
                object_pairs_hook=_json_no_duplicate_keys,
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid abstention policy JSON: {exc}") from exc
        return cls.from_dict(raw)

    def to_json(self) -> str:
        """Return the canonical JSON payload including its content hash."""

        return canonical_json(self.to_dict())

    @classmethod
    def from_json(cls, value: str) -> "AbstentionPolicy":
        try:
            raw = json.loads(value, object_pairs_hook=_json_no_duplicate_keys)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid abstention policy JSON: {exc}") from exc
        return cls.from_dict(raw)

    def decide(self, task: str, confidence: float | None) -> PolicyDecision:
        normalized_task = _text(task, "task", allow_none=False)
        assert normalized_task is not None
        threshold = self.threshold_map.get(normalized_task)
        if confidence is None:
            return PolicyDecision(
                normalized_task,
                "unavailable",
                None,
                threshold,
                UNAVAILABLE_CONFIDENCE,
                self.sha256,
            )
        value = _number(confidence, "confidence", low=0.0, high=1.0)
        if threshold is None:
            return PolicyDecision(
                normalized_task,
                "unavailable",
                value,
                None,
                UNAVAILABLE_NO_THRESHOLD,
                self.sha256,
            )
        action = "accept" if value >= threshold else "review"
        return PolicyDecision(normalized_task, action, value, threshold, None, self.sha256)
