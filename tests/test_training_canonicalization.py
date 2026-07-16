"""Focused contracts for the canonical Greek joint-training dataset builder."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).parent.parent / "training"
sys.path.insert(0, str(_DIR))
spec = importlib.util.spec_from_file_location(
    "build_full_dataset_canonical", _DIR / "build_full_dataset.py"
)
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_builder_help_is_safe_for_default_console_encoding() -> None:
    result = subprocess.run(
        [sys.executable, str(_DIR / "build_full_dataset.py"), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--with-extras" in result.stdout


def _word(
    token_id: int,
    head: int,
    relation: str,
    *,
    form: str = "λόγος",
    lemma: str = "λόγος",
    xpos: str = "n-s---mn-",
) -> dict[str, str]:
    return {
        "id": str(token_id),
        "head": str(head),
        "relation": relation,
        "form": form,
        "lemma": lemma,
        "xpos": xpos,
        "source_head": str(head),
        "source_relation": relation,
        "source_xpos": xpos,
        "source_lemma": lemma,
    }


def test_policy_is_bound_to_all_three_source_revisions() -> None:
    policy = builder.load_label_policy()
    assert policy["policy_id"] == "greek-joint-canonical-v1"
    assert set(policy["sources"]) == {"agdt", "gorman", "pedalion"}
    assert all(len(source["revision"]) == 40 for source in policy["sources"].values())


def test_leaf_apos_is_appos_and_original_labels_remain_addressable() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "APOS", form="Σωκράτης", lemma="Σωκράτης"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["deprel"] == ["root", "appos"]
    assert row["source"] == "agdt"
    assert row["source_token_ids"] == ["1", "2"]
    assert len(row["source_label_sha256"]) == 64
    assert row["source_label_sha256"] == builder._source_label_sha256(attrs)
    attrs[1]["source_relation"] = "ATR"
    assert row["source_label_sha256"] != builder._source_label_sha256(attrs)


def test_structurally_confirmed_coordinator_normalizes_pedalion_b_to_cconj() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "COORD", form="δὲ", lemma="δέ", xpos="b--------"),
    ]
    audit: dict[str, object] = {}
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion", audit=audit)
    assert row["deprel"][1] == "cc"
    assert row["xpos"][1] == "c--------"
    assert row["upos"][1] == "CCONJ"
    summary = builder._finalize_audit(audit)
    assert summary["pedalion"]["upos_changes"] == {"X->CCONJ": 1}
    assert summary["pedalion"]["xpos_changes"] == {"b--------->c--------": 1}


def test_ambiguous_auxy_use_is_not_flattened_into_coordination() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "AuxY", form="δὲ", lemma="δέ", xpos="b--------"),
    ]
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion")
    assert row["deprel"][1] == "advmod"
    assert row["xpos"][1] == "b--------"
    assert row["upos"][1] == "X"


def test_coordinator_pos_is_unchanged_when_surface_is_outside_closed_lexicon() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "COORD", form="λόγος", lemma="λόγος", xpos="b--------"),
    ]
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion")
    assert row["deprel"][1] == "cc"
    assert row["xpos"][1] == "b--------"
    assert row["upos"][1] == "X"


def test_agdt_loader_skips_protected_identity_before_emission() -> None:
    fixture = Path(__file__).parent / "fixtures" / "ud"
    audit: dict[str, object] = {}
    rows = builder.load_agdt_full(
        fixture,
        skip_ids={("sample.tb.xml", "1")},
        audit=audit,
    )
    assert [(row["file"], row["sid"]) for row in rows] == [("sample.tb.xml", "2")]
    assert builder._finalize_audit(audit)["agdt"]["sentences"] == 1


def test_split_validation_rejects_protected_training_identity() -> None:
    train = [{"file": "source.xml", "sid": "2", "source": "agdt"}]
    dev = [{"file": "source.xml", "sid": "1", "source": "agdt"}]
    builder.validate_split_separation(
        train,
        dev,
        dev_ids={("source.xml", "1")},
        test_ids={("source.xml", "3")},
    )
    train[0]["sid"] = "3"
    with pytest.raises(ValueError, match="protected AGDT"):
        builder.validate_split_separation(
            train,
            dev,
            dev_ids={("source.xml", "1")},
            test_ids={("source.xml", "3")},
        )


def test_manifest_binds_policy_sources_outputs_and_detects_tampering(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text("<treebank/>", encoding="utf-8")
    for name in (
        "full-train.jsonl",
        "full-dev.jsonl",
        "lemma-scripts.json",
        "lemma-lookup.json",
        "full-stats.json",
    ):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    train = [{"file": "train.xml", "sid": "1", "source": "agdt"}]
    dev = [{"file": "dev.xml", "sid": "1", "source": "agdt"}]
    manifest = builder.build_training_manifest(
        output_dir=tmp_path,
        source_paths={"agdt": [source]},
        train=train,
        dev=dev,
        dev_ids={("dev.xml", "1")},
        test_ids={("test.xml", "1")},
        extras_audit=None,
        transform_audit={},
    )
    path = tmp_path / "training-data-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    checked = builder.verify_training_manifest(path)
    assert checked["policy"]["policy_id"] == "greek-joint-canonical-v1"
    assert checked["policy"]["hash_mode"] == "canonical-json"
    assert checked["policy"]["sha256"] == builder.canonical_sha256(builder.LABEL_POLICY)
    assert checked["sources"]["agdt"]["files"][0]["sha256"] == builder._sha256_file(source)

    (tmp_path / "full-train.jsonl").write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="generated-output record mismatch"):
        builder.verify_training_manifest(path)

    hostile = dict(manifest)
    hostile["outputs"] = [dict(record) for record in manifest["outputs"]]
    hostile["outputs"][0]["path"] = "../full-train.jsonl"
    hostile = builder.stamp_document(hostile, "manifest_sha256")
    path.write_text(json.dumps(hostile, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid generated-output path"):
        builder.verify_training_manifest(path)
