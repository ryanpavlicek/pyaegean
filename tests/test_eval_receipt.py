"""Tests for content-addressed evaluation receipts (no network)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aegean.greek.eval_receipt import EvalReceipt, eval_receipt

# A fixed, offline environment so receipts are fully deterministic in tests.
_FIXED: dict[str, Any] = {
    "package_version": "0.10.0",
    "manifest": {"package": "0.10.0", "bundled": {"a.json": {"sha256": "deadbeef"}}},
    "model_id": "grc-joint",
}

_SCORES = {"LAS": 85.6, "UPOS": 97.0}


def _make(**overrides: Any) -> EvalReceipt:
    kwargs: dict[str, Any] = {
        "treebank": "perseus",
        "split": "test",
        "protocol": "conll18-official-evaluator",
        **_FIXED,
    }
    kwargs.update(overrides)
    scores = kwargs.pop("scores", _SCORES)
    return eval_receipt(scores, **kwargs)


def test_deterministic_same_inputs_same_id() -> None:
    a = _make()
    b = _make()
    assert a.id == b.id
    assert a == b
    assert len(a.id) == 16
    assert a.verify()
    assert a.verify(b)


def test_id_is_short_hex_prefix_of_full_sha256() -> None:
    rec = _make()
    full = rec.recompute_id(full=True)
    assert len(full) == 64
    assert all(c in "0123456789abcdef" for c in full)
    assert full.startswith(rec.id)


@pytest.mark.parametrize(
    "field",
    ["treebank", "split", "protocol", "package_version", "model_id"],
)
def test_changing_a_scalar_field_changes_the_id(field: str) -> None:
    base = _make()
    changed = _make(**{field: "MUTATED"})
    assert changed.id != base.id
    assert not base.verify(changed)


def test_changing_a_score_changes_the_id() -> None:
    base = _make()
    changed = _make(scores={"LAS": 85.7, "UPOS": 97.0})
    assert changed.id != base.id


def test_changing_the_manifest_changes_the_id() -> None:
    base = _make()
    other_manifest = {"package": "0.10.0", "bundled": {"a.json": {"sha256": "feedface"}}}
    changed = _make(manifest=other_manifest)
    assert changed.id != base.id


def test_changing_extra_changes_the_id() -> None:
    base = _make(extra=None)
    changed = _make(extra={"seed": 1})
    assert changed.id != base.id
    again = _make(extra={"seed": 2})
    assert again.id != changed.id


def test_model_id_none_differs_from_set() -> None:
    with_model = _make(model_id="grc-joint")
    without = _make(model_id=None)
    assert with_model.id != without.id
    assert without.model_id is None


def test_score_key_order_does_not_matter() -> None:
    a = _make(scores={"LAS": 85.6, "UPOS": 97.0})
    b = _make(scores={"UPOS": 97.0, "LAS": 85.6})
    assert a.id == b.id


def test_as_json_rehashes_to_id() -> None:
    import hashlib

    rec = _make()
    canonical = rec.as_json()
    # as_json() (compact) is exactly the byte basis of the id.
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert digest.startswith(rec.id)
    assert rec.recompute_id(full=True) == digest


def test_as_dict_round_trips_and_verifies() -> None:
    rec = _make(extra={"seed": 7})
    d = rec.as_dict()
    assert d["id"] == rec.id
    restored = EvalReceipt.from_dict(d)
    assert restored == rec
    assert restored.verify()
    # Survives a JSON serialization round-trip.
    restored2 = EvalReceipt.from_dict(json.loads(json.dumps(d)))
    assert restored2.id == rec.id
    assert restored2.verify()


def test_verify_detects_tampering() -> None:
    rec = _make()
    # Forge a receipt whose stored id no longer matches its fields.
    forged = EvalReceipt.from_dict({**rec.as_dict(), "scores": {"LAS": 99.9}})
    assert not forged.verify()


def test_frozen_dataclass_is_immutable() -> None:
    rec = _make()
    with pytest.raises(Exception):
        rec.id = "x"  # type: ignore[misc]


def test_auto_resolution_via_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default path resolves version / manifest / model id from the package,
    stubbed here so the test stays offline."""
    import aegean
    from aegean import data
    from aegean.greek import joint

    monkeypatch.setattr(aegean, "__version__", "9.9.9", raising=False)
    monkeypatch.setattr(data, "versions", lambda: {"package": "9.9.9", "fetched": {}})
    monkeypatch.setattr(joint, "_ACTIVE", None)

    rec_no_model = eval_receipt(
        _SCORES, treebank="perseus", split="test", protocol="p"
    )
    assert rec_no_model.package_version == "9.9.9"
    assert rec_no_model.model_id is None
    assert rec_no_model.manifest == {"package": "9.9.9", "fetched": {}}
    assert rec_no_model.verify()

    # Now simulate an active model (a sentinel is enough; active() != None is the gate).
    monkeypatch.setattr(joint, "_ACTIVE", object())
    rec_model = eval_receipt(_SCORES, treebank="perseus", split="test", protocol="p")
    assert rec_model.model_id == joint._DATASET
    assert rec_model.id != rec_no_model.id


def test_explicit_inputs_match_auto_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passing the environment explicitly yields the same id as letting it resolve."""
    import aegean
    from aegean import data
    from aegean.greek import joint

    monkeypatch.setattr(aegean, "__version__", "1.2.3", raising=False)
    manifest = {"package": "1.2.3", "bundled": {}}
    monkeypatch.setattr(data, "versions", lambda: manifest)
    monkeypatch.setattr(joint, "_ACTIVE", None)

    auto = eval_receipt(_SCORES, treebank="perseus", split="dev", protocol="p")
    explicit = eval_receipt(
        _SCORES,
        treebank="perseus",
        split="dev",
        protocol="p",
        package_version="1.2.3",
        manifest=manifest,
        model_id=None,
    )
    assert auto.id == explicit.id
