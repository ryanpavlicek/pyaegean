"""Content-addressed evaluation receipts: one tamper-evident record per result.

A *receipt* ties a single evaluation result to the exact inputs that produced it,
so a number in a paper or the methods write-up can be reproduced and checked. It
composes pieces pyaegean already tracks, the package version
(``aegean.__version__``), the data manifest (``aegean.data.versions()``), and the
active neural model id (``aegean.greek.joint.active()``), with the caller-supplied
``{treebank, split, protocol, scores}`` (and any ``extra``), then hashes the
canonical (sorted-key) JSON of that object into a short sha256 receipt id.

The id is **content-addressed**: identical inputs give the identical id, and any
change to any field, a different score, a bumped package version, a different data
sha256, a swapped model, yields a different id. So a receipt is *tamper-evident*:
re-deriving it from the recorded inputs (``EvalReceipt.recompute_id`` /
``verify``) detects after-the-fact edits.

This records *what was run*; it does not certify that the protocol is sound or that
the scores are correct. It pins inputs, not conclusions.

Usage::

    rec = eval_receipt(
        scores={"LAS": 85.6, "UPOS": 97.0},
        treebank="perseus", split="test",
        protocol="conll18-official-evaluator",
    )
    rec.id            # e.g. "a1b2c3d4e5f6a7b8"
    rec.as_json()     # the canonical JSON that was hashed (re-derives rec.id)
    rec.verify()      # True iff the stored fields still hash to rec.id

For an offline / deterministic receipt (tests, fixed snapshots) pass the three
environment inputs explicitly, ``package_version``, ``manifest``, ``model_id``,
and nothing in this module touches the network or the filesystem.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

__all__ = [
    "EvalReceipt",
    "eval_receipt",
]

# Bumped only if the canonical payload layout changes (so old ids stay interpretable).
_RECEIPT_FORMAT = "pyaegean-eval-receipt/1"
# Length of the short hex id; full sha256 is recoverable via recompute_id(full=True).
_ID_LEN = 16


def _resolve_package_version() -> str:
    """``aegean.__version__`` (no network)."""
    import aegean

    return str(aegean.__version__)


def _resolve_manifest() -> dict[str, Any]:
    """The data reproducibility manifest (``aegean.data.versions()``)."""
    from .. import data

    return data.versions()


def _resolve_model_id() -> str | None:
    """A stable id for the active neural model, or ``None`` if none is active.

    ``joint.active()`` returns an opaque loaded-model handle with no public id, so
    the dataset asset name (the thing that is pinned, fetched, and versioned) is the
    stable identifier; ``None`` is itself meaningful (the non-neural cascade)."""
    from . import joint

    if joint.active() is None:
        return None
    return str(joint._DATASET)


def _canonical_payload(
    *,
    scores: dict[str, float],
    treebank: str,
    split: str,
    protocol: str,
    extra: dict[str, Any] | None,
    package_version: str,
    manifest: dict[str, Any],
    model_id: str | None,
) -> dict[str, Any]:
    """The exact object that gets hashed, before canonicalization."""
    return {
        "format": _RECEIPT_FORMAT,
        "package_version": package_version,
        "manifest": manifest,
        "model_id": model_id,
        "treebank": treebank,
        "split": split,
        "protocol": protocol,
        "scores": scores,
        "extra": extra,
    }


def _canonical_json(payload: dict[str, Any]) -> str:
    """Canonical (sorted-key, compact, UTF-8) JSON: the byte basis of the id."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_id(payload: dict[str, Any], *, full: bool = False) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return digest if full else digest[:_ID_LEN]


@dataclass(frozen=True, slots=True)
class EvalReceipt:
    """A tamper-evident record tying one evaluation result to its inputs.

    Frozen and content-addressed: ``id`` is the short sha256 of the canonical JSON of
    every other field. Construct via `eval_receipt`. ``scores``/``manifest``/``extra``
    are stored as-is; treat them as read-only (the dataclass is frozen, but their
    contents are plain dicts).
    """

    id: str
    package_version: str
    manifest: dict[str, Any]
    model_id: str | None
    treebank: str
    split: str
    protocol: str
    scores: dict[str, float]
    extra: dict[str, Any] | None

    def _payload(self) -> dict[str, Any]:
        return _canonical_payload(
            scores=self.scores,
            treebank=self.treebank,
            split=self.split,
            protocol=self.protocol,
            extra=self.extra,
            package_version=self.package_version,
            manifest=self.manifest,
            model_id=self.model_id,
        )

    def recompute_id(self, *, full: bool = False) -> str:
        """Re-derive the id from the stored fields (``full=True`` for the 64-char sha256)."""
        return _hash_id(self._payload(), full=full)

    def verify(self, other: "EvalReceipt | None" = None) -> bool:
        """Tamper check. With no argument, re-hash this receipt's fields and confirm
        they still produce ``self.id``. With ``other``, confirm both receipts describe
        the byte-identical evaluation (same content-addressed id)."""
        if other is not None:
            return self.id == other.id and self.recompute_id() == other.recompute_id()
        return self.recompute_id() == self.id

    def as_json(self, *, indent: int | None = None) -> str:
        """Serialize the full receipt (id + every field) to JSON.

        With ``indent=None`` (the default) this is the canonical form whose bytes the
        id hashes, minus the id itself; ``as_dict()`` includes the id for storage."""
        if indent is None:
            return _canonical_json(self._payload())
        return json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=False, indent=indent)

    def as_dict(self) -> dict[str, Any]:
        """A plain dict of every field, including ``id`` (round-trips via `from_dict`)."""
        payload = self._payload()
        payload["id"] = self.id
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalReceipt":
        """Reconstruct a receipt from `as_dict` output (does not re-verify; call `verify`)."""
        return cls(
            id=str(data["id"]),
            package_version=str(data["package_version"]),
            manifest=dict(data["manifest"]),
            model_id=None if data["model_id"] is None else str(data["model_id"]),
            treebank=str(data["treebank"]),
            split=str(data["split"]),
            protocol=str(data["protocol"]),
            scores=dict(data["scores"]),
            extra=None if data["extra"] is None else dict(data["extra"]),
        )


def eval_receipt(
    scores: dict[str, float],
    *,
    treebank: str,
    split: str,
    protocol: str,
    extra: dict[str, Any] | None = None,
    package_version: str | None = None,
    manifest: dict[str, Any] | None = None,
    model_id: str | None = None,
) -> EvalReceipt:
    """Compose a content-addressed `EvalReceipt` for one evaluation result.

    ``scores`` is the metric → value mapping (e.g. the dict from
    ``greek.evaluate_on_ud``); ``treebank`` / ``split`` / ``protocol`` name what was
    evaluated and how; ``extra`` carries any further reproducibility metadata (seed,
    evaluator sha, fold manifest, …). The package version, data manifest, and active
    model id are resolved automatically and folded into the hashed payload.

    Pass ``package_version`` / ``manifest`` / ``model_id`` to override the resolved
    environment, for a fully deterministic, offline receipt (the entire call then
    touches neither the network nor the filesystem). The resulting ``id`` is stable:
    identical inputs always give the identical id, and changing any field changes it.
    """
    resolved_version = _resolve_package_version() if package_version is None else package_version
    resolved_manifest = _resolve_manifest() if manifest is None else manifest
    resolved_model = _resolve_model_id() if model_id is None else model_id
    payload = _canonical_payload(
        scores=scores,
        treebank=treebank,
        split=split,
        protocol=protocol,
        extra=extra,
        package_version=resolved_version,
        manifest=resolved_manifest,
        model_id=resolved_model,
    )
    return EvalReceipt(
        id=_hash_id(payload),
        package_version=resolved_version,
        manifest=resolved_manifest,
        model_id=resolved_model,
        treebank=treebank,
        split=split,
        protocol=protocol,
        scores=scores,
        extra=extra,
    )
