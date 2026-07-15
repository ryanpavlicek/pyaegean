"""Focused offline contract tests for development reports and comparisons."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

TRAINING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING))

import development_manifest as manifest_mod  # noqa: E402
import development_report as report  # noqa: E402


def _token(form: str, *, upos: str = "NOUN", lemma: str | None = None,
           head: int = 0, deprel: str = "root", xpos: str = "n--------",
           feats: str = "_") -> dict[str, object]:
    return {"form": form, "lemma": lemma or form, "upos": upos, "xpos": xpos,
            "feats": feats, "head": head, "deprel": deprel}


def _manifest(n: int = 2) -> dict[str, object]:
    items = []
    binding = {"fixture": "a" * 64}
    asset_binding_sha = __import__("hashlib").sha256(
        manifest_mod.canonical_json(binding).encode("utf-8")
    ).hexdigest()
    for i in range(n):
        item_id = f"src/doc/s{i}"
        items.append({
            "item_id": item_id, "source": "fixture", "asset_sha256": asset_binding_sha,
            "asset_sha256_by_track": binding,
            "document_id": "doc", "work_id": "work", "sentence_id": f"s{i}",
            "profile_ids": ["prose"], "domain_ids": ["literary"],
            "annotation_conventions": ["fixture"],
            "tasks": ["parse", "tagging"], "tracks": ["fixture"],
            "token_count": 1, "scored_token_count": 1,
            "content_sha256": __import__("hashlib").sha256(f"content-{i}".encode()).hexdigest(),
            "form_tuple_sha256": __import__("hashlib").sha256(
                manifest_mod.canonical_json(["a"]).encode("utf-8")
            ).hexdigest(),
            "v3_exposure": "fixture", "train_token_frequencies": [1],
            "oov_token_count": 0, "train_frequency_min": 1,
        })
    source_slice = {
        "rule": "source == fixture", "available": True, "item_count": n,
        "token_count": n, "document_count": 1 if n else 0,
        "work_count": 1 if n else 0, "coverage": 1.0 if n else 0.0,
        "minimum_sample": 2, "thin": n < 2,
        "item_ids": [item["item_id"] for item in items],
    }
    return manifest_mod.stamp_document({
        "format": manifest_mod.MANIFEST_FORMAT,
        "kind": "development-source-manifest",
        "policy": {
            "eligible_sources": ["fixture"], "normalization": "NFC",
            "training_overlap": "fixture", "locked_work_exclusion": True,
            "selection_claim_status": "development-only-not-published",
        },
        "sources": {
            "perseus_dev": {"path": "p", "bytes": 1, "sha256": "1" * 64},
            "perseus_locked": {"path": "p", "bytes": 1, "sha256": "2" * 64},
            "papygreek_tagging": {"path": "p", "bytes": 1, "sha256": "3" * 64},
            "papygreek_parse": {"path": "p", "bytes": 1, "sha256": "4" * 64},
            "revisions": {"fixture": "1"}, "training_files": [],
            "papygreek_locked_manifest": {"doc_ids": ["locked"], "asset_sha256": "5" * 64, "file": None},
            "papygreek_training_work_audit": {"excluded_document_ids": []},
        },
        "source_hashes": {
            "perseus_dev": "1" * 64,
            "perseus_locked": "2" * 64,
            "papygreek_tagging": "3" * 64,
            "papygreek_parse": "4" * 64,
            "papygreek_locked_manifest": "5" * 64,
            "papygreek_training_work_audit": "6" * 64,
        },
        "locked_file_hashes": {
            "perseus_locked": "2" * 64,
            "papygreek_locked_manifest": "5" * 64,
        },
        "items": items, "slices": {"source/fixture": source_slice},
        "audit": {"fixture": True},
    }, "manifest_sha256")


def _inputs(n: int = 2):
    ids = [f"src/doc/s{i}" for i in range(n)]
    gold = {item_id: [_token("a", head=0)] for item_id in ids}
    pred = copy.deepcopy(gold)
    return gold, pred


def _run(predictions, *, tasks=("parsing", "tagging")):
    prediction_sha = __import__("hashlib").sha256(
        manifest_mod.canonical_json(predictions).encode("utf-8")
    ).hexdigest()
    return {
        "model": {"identity": "fixture", "asset_sha256": "a" * 64},
        "preprocessing": {"identity": "fixture", "config_sha256": "b" * 64},
        "output_profile": {"identity": "fixture", "tasks": sorted(tasks)},
        "decoder": {
            "identity": "fixture",
            "mode": "sequential",
            "long_input": "windowed",
        },
        "environment_receipt_sha256": "c" * 64,
        "git_revision": "d" * 40,
        "prediction_sha256": prediction_sha,
    }


def _build(n: int = 2, *, pred=None, run=None):
    m = _manifest(n)
    gold, expected = _inputs(n)
    predictions = pred or expected
    return report.build_report(manifest=m, gold_sentences=gold, predictions=predictions,
                               run=run or _run(predictions),
                               n_resamples=9)


def test_perfect_report_has_exact_counts_and_is_stamped() -> None:
    result = _build()
    assert result["metrics"]["upos"]["numerator"] == 2
    assert result["metrics"]["upos"]["denominator"] == 2
    assert result["metrics"]["upos"]["value"] == 1.0
    assert result["metrics"]["uas"]["denominator"] == 2
    assert result["metrics"]["uas"]["value"] == 1.0
    assert result["report_sha256"] == manifest_mod.document_sha256(result, "report_sha256")
    report.verify_report(result, _manifest())


def test_mixed_task_items_use_metric_specific_subsets() -> None:
    manifest = _manifest(2)
    manifest["items"][0]["tasks"] = ["tagging"]  # type: ignore[index]
    manifest["items"][1]["tasks"] = ["parse"]  # type: ignore[index]
    manifest = manifest_mod.stamp_document(manifest, "manifest_sha256")
    gold, predictions = _inputs()
    result = report.build_report(
        manifest=manifest,
        gold_sentences=gold,
        predictions=predictions,
        run=_run(predictions),
        n_resamples=9,
    )
    assert result["metrics"]["upos"]["denominator"] == 1
    assert result["metrics"]["uas"]["denominator"] == 1
    assert result["items"][0]["metrics"]["uas"]["reason"] == "parser-not-requested"
    assert result["items"][1]["metrics"]["upos"]["reason"] == "tagger-not-requested"
    assert result["error_anatomy"]["by_task"]["tagging"]["denominators"]["upos"] == 1
    assert result["error_anatomy"]["by_task"]["tagging"]["denominators"]["uas"] == 0
    assert result["error_anatomy"]["by_task"]["parse"]["denominators"]["upos"] == 0
    assert result["error_anatomy"]["by_task"]["parse"]["denominators"]["uas"] == 1


def test_lemma_wildcard_is_consistent_in_error_anatomy() -> None:
    manifest = _manifest(2)
    gold, predictions = _inputs()
    gold["src/doc/s0"][0]["lemma"] = "_"
    predictions["src/doc/s0"][0]["lemma"] = "not-scored"
    result = report.build_report(
        manifest=manifest,
        gold_sentences=gold,
        predictions=predictions,
        run=_run(predictions),
        n_resamples=9,
    )
    assert result["metrics"]["lemma"]["numerator"] == 2
    assert result["error_anatomy"]["overall"]["lemma_confusions"] == []
    assert result["error_anatomy"]["overall"]["frequency_bands"]["1"]["lemma_correct"] == 2


def test_zero_denominator_items_do_not_depress_bootstrap_interval() -> None:
    manifest = _manifest(2)
    gold, predictions = _inputs()
    gold["src/doc/s1"][0]["deprel"] = "punct"
    predictions["src/doc/s1"][0]["deprel"] = "punct"
    result = report.build_report(
        manifest=manifest,
        gold_sentences=gold,
        predictions=predictions,
        run=_run(predictions),
        n_resamples=9,
    )
    assert result["metrics"]["clas"]["value"] == 1.0
    assert result["items"][1]["metrics"]["clas"]["reason"] == "no-scored-tokens"
    assert result["metrics"]["clas"]["ci"] == {
        "low": None,
        "high": None,
        "level": 0.95,
        "n_resamples": 9,
        "reason": "fewer-than-two-items",
    }


def test_verify_report_rejects_restamped_nested_metric_corruption() -> None:
    valid = _build()
    bad_global = copy.deepcopy(valid)
    bad_global["metrics"]["upos"]["denominator"] = -99
    bad_global = manifest_mod.stamp_document(bad_global, "report_sha256")
    with pytest.raises(report.ReportError):
        report.verify_report(bad_global, _manifest())

    bad_item = copy.deepcopy(valid)
    bad_item["items"][0]["metrics"]["upos"] = {"value": 42}
    bad_item = manifest_mod.stamp_document(bad_item, "report_sha256")
    with pytest.raises(report.ReportError):
        report.verify_report(bad_item, _manifest())


def test_mixed_report_uses_official_all_word_denominators() -> None:
    m = _manifest(1)
    gold = {"src/doc/s0": [
        _token("a"),
        _token(".", upos="PUNCT", head=1, deprel="punct"),
        _token("1", upos="NUM", head=1, deprel="nummod"),
    ]}
    pred = {"src/doc/s0": [
        _token("a", upos="VERB"),
        _token(".", upos="NOUN", head=1, deprel="punct"),
        _token("1", upos="NOUN", head=1, deprel="nummod"),
    ]}
    m["items"][0]["token_count"] = 3  # type: ignore[index]
    m["items"][0]["scored_token_count"] = 3  # type: ignore[index]
    m["items"][0]["train_token_frequencies"] = [1, 1, 1]  # type: ignore[index]
    m["items"][0]["form_tuple_sha256"] = __import__("hashlib").sha256(  # type: ignore[index]
        manifest_mod.canonical_json(["a", ".", "1"]).encode("utf-8")
    ).hexdigest()
    m["slices"]["source/fixture"]["token_count"] = 3  # type: ignore[index]
    m = manifest_mod.stamp_document(m, "manifest_sha256")
    result = report.build_report(manifest=m, gold_sentences=gold, predictions=pred,
                                 run=_run(pred, tasks=("tagging",)), n_resamples=9)
    assert result["metrics"]["upos"]["numerator"] == 0
    assert result["metrics"]["upos"]["denominator"] == 3
    assert result["metrics"]["uas"]["value"] is None
    assert result["metrics"]["uas"]["reason"] == "parser-not-requested"


def test_clas_uses_official_content_relation_f1_counts() -> None:
    manifest = _manifest(1)
    gold = {
        "src/doc/s0": [
            _token("a", head=0, deprel="root"),
            _token("the", upos="DET", head=1, deprel="det"),
        ]
    }
    predictions = {
        "src/doc/s0": [
            _token("a", head=0, deprel="root"),
            _token("the", upos="DET", head=1, deprel="dep"),
        ]
    }
    item = manifest["items"][0]  # type: ignore[index]
    item["token_count"] = 2
    item["scored_token_count"] = 2
    item["train_token_frequencies"] = [1, 1]
    item["form_tuple_sha256"] = __import__("hashlib").sha256(
        manifest_mod.canonical_json(["a", "the"]).encode("utf-8")
    ).hexdigest()
    manifest["slices"]["source/fixture"]["token_count"] = 2  # type: ignore[index]
    manifest = manifest_mod.stamp_document(manifest, "manifest_sha256")

    result = report.build_report(
        manifest=manifest,
        gold_sentences=gold,
        predictions=predictions,
        run=_run(predictions),
        n_resamples=9,
    )
    clas = result["metrics"]["clas"]
    assert clas["numerator"] == 2  # 2 * one correctly attached gold content word
    assert clas["denominator"] == 3  # one gold + two predicted content words
    assert clas["value"] == pytest.approx(2 / 3)
    assert clas["official_value"] == pytest.approx(2 / 3)


def test_manifest_slice_and_frequency_metadata_reach_error_anatomy() -> None:
    m = _manifest(2)
    m["slices"]["rare"] = {  # type: ignore[index]
        "rule": "frequency == 1", "available": True, "item_count": 1,
        "token_count": 1, "document_count": 1, "work_count": 1,
        "coverage": 0.5, "minimum_sample": 2, "thin": True,
        "item_ids": ["src/doc/s0"],
    }
    for item in m["items"]:  # type: ignore[union-attr]
        item["train_token_frequencies"] = [1 if item["item_id"].endswith("s0") else 51]  # type: ignore[index]
    m = manifest_mod.stamp_document(m, "manifest_sha256")
    gold, pred = _inputs()
    pred["src/doc/s0"] = [_token("a", lemma="wrong")]
    result = report.build_report(manifest=m, gold_sentences=gold, predictions=pred,
                                 run=_run(pred, tasks=("tagging",)), n_resamples=9)
    assert result["items"][0]["slice_ids"] == ["rare", "source/fixture"]
    anatomy = result["error_anatomy"]["by_slice"]["rare"]
    assert anatomy["frequency_bands"]["1"]["tokens"] == 1


def test_wrong_report_and_reordered_input_are_deterministic() -> None:
    m = _manifest(2)
    gold, pred = _inputs()
    pred["src/doc/s1"] = [_token("a", upos="VERB")]
    first = report.build_report(manifest=m, gold_sentences=gold, predictions=pred,
                                run=_run(pred, tasks=("tagging",)), n_resamples=9)
    second = report.build_report(manifest=m, gold_sentences=dict(reversed(list(gold.items()))),
                                 predictions=dict(reversed(list(pred.items()))),
                                 run=_run(dict(reversed(list(pred.items()))), tasks=("tagging",)), n_resamples=9)
    assert first == second
    assert first["metrics"]["upos"]["numerator"] == 1


def test_shape_and_nonfinite_errors_are_fail_closed() -> None:
    m = _manifest()
    gold, pred = _inputs()
    with pytest.raises(report.ReportError, match="missing"):
        short = {"src/doc/s0": pred["src/doc/s0"]}
        report.build_report(manifest=m, gold_sentences=gold, predictions=short, run=_run(short))
    bad = copy.deepcopy(pred)
    bad["src/doc/s0"][0]["head"] = True
    with pytest.raises(report.ReportError, match="head"):
        report.build_report(manifest=m, gold_sentences=gold, predictions=bad, run=_run(bad))
    with pytest.raises(report.ReportError, match="n_resamples"):
        report.build_report(manifest=m, gold_sentences=gold, predictions=pred, run=_run(pred), n_resamples=0)
    wrong_form = copy.deepcopy(pred)
    wrong_form["src/doc/s0"][0]["form"] = "b"
    with pytest.raises(report.ReportError, match="FORM values differ"):
        report.build_report(
            manifest=m,
            gold_sentences=gold,
            predictions=wrong_form,
            run=_run(wrong_form),
        )
    bad_run = _run(pred)
    bad_run["prediction_sha256"] = "0" * 64
    with pytest.raises(report.ReportError, match="prediction artifact"):
        report.build_report(
            manifest=m, gold_sentences=gold, predictions=pred, run=bad_run
        )


def test_paired_comparison_is_exact_and_rejects_manifest_mismatch() -> None:
    baseline = _build()
    candidate_pred = {item_id: [_token("a", upos="VERB")] for item_id in baseline["item_ids"]}
    gold, _ = _inputs()
    candidate = report.build_report(manifest=_manifest(), gold_sentences=gold,
                                    predictions=candidate_pred,
                                    run=_run(candidate_pred), n_resamples=9)
    comparison = report.compare_reports(candidate, baseline, n_resamples=9)
    assert comparison["metrics"]["upos"]["difference"] == -1.0
    assert comparison["metrics"]["upos"]["mcnemar"]["b"] == 0
    assert comparison["metrics"]["upos"]["mcnemar"]["c"] == 2
    assert comparison["comparison_sha256"] == manifest_mod.document_sha256(comparison, "comparison_sha256")
    altered = _manifest()
    altered["items"][0]["source"] = "other"  # type: ignore[index]
    altered = manifest_mod.stamp_document(altered, "manifest_sha256")
    other = report.build_report(manifest=altered, gold_sentences=gold, predictions=candidate_pred,
                                run=_run(candidate_pred), n_resamples=9)
    with pytest.raises(report.ReportError, match="different manifests"):
        report.compare_reports(candidate, other, n_resamples=9)


def test_paired_comparison_needs_two_items() -> None:
    one = _build(1)
    with pytest.raises(report.ReportError, match="at least two"):
        report.compare_reports(one, one)


def test_report_write_read_verify_journey(tmp_path: Path) -> None:
    result = _build()
    path = tmp_path / "report.json"
    manifest_mod.write_document(result, path, digest_field="report_sha256")
    loaded = manifest_mod.load_document(path, digest_field="report_sha256")
    report.verify_report(loaded, _manifest())
    assert loaded == result


def test_empty_manifest_produces_explicit_null_metrics() -> None:
    result = _build(0)
    assert result["item_ids"] == []
    for metric in ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas"):
        assert result["metrics"][metric]["value"] is None
        assert result["metrics"][metric]["reason"] in {
            "no-scored-tokens",
            "parser-not-requested",
        }


def test_report_verifier_rejects_unknown_schema_fields() -> None:
    result = _build()
    tampered = dict(result)
    tampered["unexpected"] = True
    tampered = manifest_mod.stamp_document(tampered, "report_sha256")
    with pytest.raises(report.ReportError, match="fields differ"):
        report.verify_report(tampered)
