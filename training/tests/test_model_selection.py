"""Correctness, adversarial, and journey tests for declarative model selection."""

from __future__ import annotations

import copy
import itertools
import json
import sys
from pathlib import Path

import pytest

TRAINING = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(TESTS))

import development_manifest as manifest_mod  # noqa: E402
import development_report as report_mod  # noqa: E402
import model_selection as selection  # noqa: E402
import test_development_report as report_fixtures  # noqa: E402


def _gate(manifest_sha256: str) -> dict[str, object]:
    return selection.stamp_gate(
        {
            "format": selection.GATE_FORMAT,
            "gate_id": "fixture-gate-v1",
            "claim_status": selection.CLAIM_STATUS,
            "development_manifest_sha256": manifest_sha256,
            "decoder": {
                "identity": "fixture-release-mst",
                "mode": "sequential",
                "long_input": "windowed",
            },
            "protected_metrics": [
                {"metric": "lemma", "slice": "source/fixture", "max_regression": 0.0},
                {"metric": "las", "slice": "source/fixture", "max_regression": 0.0},
            ],
            "target_metrics": [
                {"metric": "lemma", "slice": "source/fixture", "weight": 0.5},
                {"metric": "las", "slice": "source/fixture", "weight": 0.5},
            ],
            "operational_limits": {
                "profile_id": "fixture-cpu-v1",
                "max_artifact_size_bytes": 1000,
                "max_latency_ms_per_100_tokens": 100.0,
            },
            "promotion": {
                "minimum_weighted_target_gain": 0.0,
                "require_pareto_non_dominated": True,
            },
            "tie_breaking": [
                {"field": "weighted_target_gain", "direction": "descending"},
                {"field": "worst_protected_delta", "direction": "descending"},
                {"field": "latency_ms_per_100_tokens", "direction": "ascending"},
                {"field": "artifact_size_bytes", "direction": "ascending"},
                {"field": "candidate_id", "direction": "ascending"},
            ],
        }
    )


def _predictions(kind: str) -> dict[str, list[dict[str, object]]]:
    _, predictions = report_fixtures._inputs(4)
    if kind in {"baseline", "lemma-winner", "dominated", "bad"}:
        predictions["src/doc/s0"][0]["lemma"] = "wrong"
    if kind in {"baseline", "syntax-winner", "dominated", "bad"}:
        predictions["src/doc/s1"][0]["deprel"] = "dep"
    if kind == "bad":
        predictions["src/doc/s2"][0]["lemma"] = "also-wrong"
        predictions["src/doc/s2"][0]["deprel"] = "dep"
    return predictions


def _report(
    *, manifest: dict[str, object], candidate_id: str, prediction_kind: str
) -> dict[str, object]:
    gold, _ = report_fixtures._inputs(4)
    predictions = _predictions(prediction_kind)
    run = report_fixtures._run(predictions)
    run["model"]["identity"] = candidate_id
    run["decoder"]["identity"] = "fixture-release-mst"
    return report_mod.build_report(
        manifest=manifest,
        gold_sentences=gold,
        predictions=predictions,
        run=run,
        n_resamples=9,
    )


def _candidate(
    *,
    manifest: dict[str, object],
    gate: dict[str, object],
    candidate_id: str,
    prediction_kind: str,
    size: int,
    latency: float,
) -> dict[str, object]:
    return selection.stamp_candidate(
        {
            "format": selection.CANDIDATE_FORMAT,
            "candidate_id": candidate_id,
            "gate_sha256": gate["gate_sha256"],
            "training_run_receipt_sha256": "e" * 64,
            "report": _report(
                manifest=manifest,
                candidate_id=candidate_id,
                prediction_kind=prediction_kind,
            ),
            "operational": {
                "profile_id": "fixture-cpu-v1",
                "artifact_size_bytes": size,
                "latency_ms_per_100_tokens": latency,
            },
        }
    )


def _fixture() -> tuple[dict[str, object], dict[str, object], dict[str, object], list[dict[str, object]]]:
    manifest = report_fixtures._manifest(4)
    gate = _gate(str(manifest["manifest_sha256"]))
    baseline = _candidate(
        manifest=manifest,
        gate=gate,
        candidate_id="baseline",
        prediction_kind="baseline",
        size=900,
        latency=90.0,
    )
    candidates = [
        _candidate(
            manifest=manifest,
            gate=gate,
            candidate_id="lemma-winner",
            prediction_kind="lemma-winner",
            size=850,
            latency=80.0,
        ),
        _candidate(
            manifest=manifest,
            gate=gate,
            candidate_id="syntax-winner",
            prediction_kind="syntax-winner",
            size=875,
            latency=70.0,
        ),
        _candidate(
            manifest=manifest,
            gate=gate,
            candidate_id="dominated",
            prediction_kind="dominated",
            size=700,
            latency=60.0,
        ),
    ]
    return manifest, gate, baseline, candidates


def test_frozen_reference_gate_is_hashed_and_balances_both_sources() -> None:
    gate = selection.load_gate(TRAINING / "model-selection-gate-v1.json")
    schema = json.loads(
        (TRAINING / "contracts" / "model-selection-gate.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["format"]["const"] == selection.GATE_FORMAT
    assert gate["gate_sha256"] == manifest_mod.document_sha256(gate, "gate_sha256")
    protected = {(entry["metric"], entry["slice"]) for entry in gate["protected_metrics"]}
    for metric in selection.METRICS:
        assert (metric, "aggregate") in protected
        assert (metric, "source:perseus") in protected
        assert (metric, "source:papygreek") in protected
    target_weight = {"source:perseus": 0.0, "source:papygreek": 0.0}
    for entry in gate["target_metrics"]:
        target_weight[entry["slice"]] += entry["weight"]
    assert target_weight["source:perseus"] == pytest.approx(0.5)
    assert target_weight["source:papygreek"] == pytest.approx(0.5)
    assert gate["decoder"]["identity"] == "pyaegean-release-single-root-mst-v1"
    assert all(
        entry["max_regression"] == pytest.approx(0.0001)
        for entry in gate["protected_metrics"]
    )


def test_pareto_selection_is_deterministic_for_every_input_order() -> None:
    manifest, gate, baseline, candidates = _fixture()
    results = [
        selection.select_candidates(
            gate=gate,
            manifest=manifest,
            baseline=baseline,
            candidates=list(order),
        )
        for order in itertools.permutations(candidates)
    ]
    assert all(result == results[0] for result in results[1:])
    result = results[0]
    assert result["selected_candidate_id"] == "syntax-winner"
    assert result["ranking"] == ["syntax-winner", "lemma-winner", "dominated"]
    by_id = {entry["candidate_id"]: entry for entry in result["candidates"]}
    assert by_id["syntax-winner"]["pareto_front"] == 0
    assert by_id["lemma-winner"]["pareto_front"] == 0
    assert by_id["dominated"]["pareto_front"] == 1
    assert result["result_sha256"] == manifest_mod.document_sha256(
        result, "result_sha256"
    )


def test_protected_regression_and_operational_limits_fail_closed() -> None:
    manifest, gate, baseline, _ = _fixture()
    bad = _candidate(
        manifest=manifest,
        gate=gate,
        candidate_id="bad",
        prediction_kind="bad",
        size=1001,
        latency=101.0,
    )
    result = selection.select_candidates(
        gate=gate, manifest=manifest, baseline=baseline, candidates=[bad]
    )
    assert result["selected_candidate_id"] is None
    assert result["ranking"] == []
    failures = result["candidates"][0]["failures"]
    assert failures == [
        "artifact size exceeds gate limit",
        "latency exceeds gate limit",
        "protected regression las@source/fixture",
        "protected regression lemma@source/fixture",
        "weighted target gain is below the promotion floor",
    ]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda gate: gate["target_metrics"][0].__setitem__("weight", float("nan")), "finite"),
        (lambda gate: gate["target_metrics"].append(copy.deepcopy(gate["target_metrics"][0])), "duplicate"),
        (lambda gate: gate["tie_breaking"].reverse(), "candidate_id"),
        (lambda gate: gate["decoder"].__setitem__("mode", "batched"), "sequential"),
    ],
)
def test_gate_rejects_nonfinite_duplicate_or_implicit_policy(
    mutation: object, message: str
) -> None:
    _, gate, _, _ = _fixture()
    gate = copy.deepcopy(gate)
    assert callable(mutation)
    mutation(gate)
    if message != "finite":
        gate = manifest_mod.stamp_document(gate, "gate_sha256")
    with pytest.raises(selection.GateError, match=message):
        selection.validate_gate(gate)


def test_gate_loader_rejects_duplicate_json_keys_and_oversized_input(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"format":"a","format":"b"}', encoding="utf-8")
    with pytest.raises(selection.GateError, match="duplicate JSON key"):
        selection.load_gate(duplicate)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b" " * (1024 * 1024) + b"}")
    with pytest.raises(selection.GateError, match="input limit"):
        selection.load_gate(oversized)


def test_candidate_rejects_gate_manifest_decoder_and_digest_drift() -> None:
    manifest, gate, baseline, _ = _fixture()
    for field, value, message in (
        ("gate_sha256", "f" * 64, "different selection gate"),
        ("candidate_sha256", "f" * 64, "digest mismatch"),
    ):
        changed = copy.deepcopy(baseline)
        changed[field] = value
        if field != "candidate_sha256":
            changed = manifest_mod.stamp_document(changed, "candidate_sha256")
        with pytest.raises(selection.GateError, match=message):
            selection.validate_candidate(changed, gate=gate, manifest=manifest)

    changed = copy.deepcopy(baseline)
    changed["report"]["run"]["decoder"]["identity"] = "greedy"
    changed["report"] = manifest_mod.stamp_document(changed["report"], "report_sha256")
    changed = manifest_mod.stamp_document(changed, "candidate_sha256")
    with pytest.raises(selection.GateError, match="decoder"):
        selection.validate_candidate(changed, gate=gate, manifest=manifest)


def test_cli_journey_writes_a_verifiable_selection_result(tmp_path: Path) -> None:
    manifest, gate, baseline, candidates = _fixture()
    paths = []
    for name, value in (
        ("gate.json", gate),
        ("manifest.json", manifest),
        ("baseline.json", baseline),
        ("candidate-a.json", candidates[0]),
        ("candidate-b.json", candidates[1]),
    ):
        path = tmp_path / name
        path.write_bytes(manifest_mod.canonical_json(value).encode("utf-8") + b"\n")
        paths.append(path)
    output = tmp_path / "result.json"
    assert selection.main(
        [
            "--gate",
            str(paths[0]),
            "--manifest",
            str(paths[1]),
            "--baseline",
            str(paths[2]),
            "--candidate",
            str(paths[3]),
            "--candidate",
            str(paths[4]),
            "--output",
            str(output),
        ]
    ) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    selection.verify_selection_result(result, gate=gate)
    assert result["selected_candidate_id"] == "syntax-winner"


def test_result_verifier_rejects_nested_tampering_fail_closed() -> None:
    manifest, gate, baseline, candidates = _fixture()
    result = selection.select_candidates(
        gate=gate,
        manifest=manifest,
        baseline=baseline,
        candidates=candidates,
    )

    no_selection = copy.deepcopy(result)
    no_selection["selected_candidate_id"] = None
    no_selection = manifest_mod.stamp_document(no_selection, "result_sha256")
    with pytest.raises(selection.GateError, match="selected candidate"):
        selection.verify_selection_result(no_selection, gate=gate)

    malformed_failure = copy.deepcopy(result)
    malformed_failure["candidates"][-1]["failures"] = [{"not": "a string"}]
    malformed_failure = manifest_mod.stamp_document(
        malformed_failure, "result_sha256"
    )
    with pytest.raises(selection.GateError, match="failures"):
        selection.verify_selection_result(malformed_failure, gate=gate)

    changed_weight = copy.deepcopy(result)
    changed_weight["candidates"][0]["target_values"][0]["weight"] = 0.25
    changed_weight = manifest_mod.stamp_document(changed_weight, "result_sha256")
    with pytest.raises(selection.GateError, match="target"):
        selection.verify_selection_result(changed_weight, gate=gate)
