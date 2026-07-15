"""Whole-journey and hostile-output tests for the development runner."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from aegean.greek.ud import loads_conllu

TRAINING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING))

import development_manifest as manifest_mod  # noqa: E402
import run_development_evaluation as runner  # noqa: E402


_CONLLU = """# sent_id = tlg0001.tlg0001.s1@1
# text = λόγος
1\tλόγος\tλόγος\tNOUN\tn--------\tCase=Nom|Gender=Masc|Number=Sing\t0\troot\t_\t_

"""
_PAPY_CONLLU = """# sent_id = papygreek-dev:papydoc@1
# text = λόγος
1\tλόγος\tλόγος\tNOUN\tn--------\tCase=Nom|Gender=Masc|Number=Sing\t0\troot\t_\t_

"""


def test_papygreek_development_namespace_matches_manifest_identity() -> None:
    sentence = loads_conllu(
        _PAPY_CONLLU.replace("papygreek-dev:papydoc@1", "papygreek-dev:bgu.12.2147@1"),
        strict=True,
    )[0]
    assert runner._item_id(sentence, source="papygreek") == (
        "papygreek:bgu.12.2147:papygreek-dev:bgu.12.2147@1"
    )


@pytest.mark.parametrize("sent_id", ["papygreekevil:x@1", "papygreek-dev:x@y"])
def test_papygreek_malformed_identity_is_rejected(sent_id: str) -> None:
    sentence = loads_conllu(
        _PAPY_CONLLU.replace("papygreek-dev:papydoc@1", sent_id),
        strict=True,
    )[0]
    with pytest.raises(runner.RunnerError):
        runner._item_id(sentence, source="papygreek")


def _fixture(tmp_path: Path) -> tuple[dict[str, object], Path, Path, Path, str]:
    perseus = tmp_path / "perseus.conllu"
    tagging = tmp_path / "tagging.conllu"
    parsing = tmp_path / "parse.conllu"
    perseus.write_text(_CONLLU, encoding="utf-8", newline="")
    tagging.write_text(_PAPY_CONLLU, encoding="utf-8", newline="")
    parsing.write_text(_PAPY_CONLLU, encoding="utf-8", newline="")
    hashes = {
        "perseus_dev": hashlib.sha256(perseus.read_bytes()).hexdigest(),
        "papygreek_tagging": hashlib.sha256(tagging.read_bytes()).hexdigest(),
        "papygreek_parse": hashlib.sha256(parsing.read_bytes()).hexdigest(),
    }
    item_id = "perseus:tlg0001.tlg0001.s1:tlg0001.tlg0001.s1@1"
    forms = ("λόγος",)
    binding = {"perseus-dev": hashes["perseus_dev"]}
    item = {
        "item_id": item_id,
        "source": "perseus",
        "asset_sha256": hashlib.sha256(
            manifest_mod.canonical_json(binding).encode("utf-8")
        ).hexdigest(),
        "asset_sha256_by_track": binding,
        "document_id": "tlg0001.tlg0001.s1",
        "work_id": "tlg0001.tlg0001",
        "sentence_id": "tlg0001.tlg0001.s1@1",
        "tasks": ["parse", "tagging"],
        "tracks": ["perseus-dev"],
        "profile_ids": ["prose"],
        "domain_ids": ["literary"],
        "annotation_conventions": ["agdt"],
        "token_count": 1,
        "scored_token_count": 1,
        "content_sha256": hashlib.sha256(
            manifest_mod.canonical_json({"forms": forms}).encode("utf-8")
        ).hexdigest(),
        "form_tuple_sha256": hashlib.sha256(
            manifest_mod.canonical_json(forms).encode("utf-8")
        ).hexdigest(),
        "v3_exposure": "unknown",
        "train_token_frequencies": [0],
        "oov_token_count": 1,
        "train_frequency_min": 0,
    }
    manifest = manifest_mod.stamp_document(
        {
            "format": manifest_mod.MANIFEST_FORMAT,
            "kind": "development-source-manifest",
            "policy": {
                "eligible_sources": ["perseus-dev"],
                "normalization": "NFC",
                "training_overlap": "forms",
                "locked_work_exclusion": True,
                "selection_claim_status": "development-only-not-published",
            },
            "sources": {
                "perseus_dev": {"path": perseus.name, "bytes": perseus.stat().st_size, "sha256": hashes["perseus_dev"]},
                "perseus_locked": {"path": "locked", "bytes": 0, "sha256": "1" * 64},
                "papygreek_tagging": {"path": tagging.name, "bytes": tagging.stat().st_size, "sha256": hashes["papygreek_tagging"]},
                "papygreek_parse": {"path": parsing.name, "bytes": parsing.stat().st_size, "sha256": hashes["papygreek_parse"]},
                "revisions": {"fixture": "1"},
                "training_files": [],
                "papygreek_locked_manifest": {"doc_ids": ["locked"], "asset_sha256": "2" * 64, "file": None},
                "papygreek_training_work_audit": {"excluded_document_ids": []},
            },
            "source_hashes": {**hashes, "perseus_locked": "1" * 64},
            "locked_file_hashes": {"perseus_locked": "1" * 64, "papygreek_locked_manifest": None},
            "items": [item],
            "slices": {},
            "audit": {},
        }
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_mod.write_document(manifest, manifest_path)
    environment = tmp_path / "environment.json"
    environment.write_text('{"python":"test"}\n', encoding="utf-8", newline="")
    return manifest, perseus, tagging, parsing, str(environment)


def test_fake_pipeline_whole_journey_writes_and_reloads_artifacts(tmp_path: Path) -> None:
    manifest, perseus, tagging, parsing, environment = _fixture(tmp_path)
    calls: list[tuple[object, bool, object, str]] = []

    def fake_pipeline(
        sentences: list[object],
        *,
        parse: bool,
        batch_size: object,
        long_input: str,
    ) -> list[object]:
        calls.append((sentences, parse, batch_size, long_input))
        return list(sentences)

    result = runner.run_development_evaluation(
        manifest=manifest,
        perseus_dev=perseus,
        papygreek_tagging=tagging,
        papygreek_parse=parsing,
        environment_receipt=environment,
        output_dir=tmp_path / "out",
        git_revision="a" * 40,
        pipeline=fake_pipeline,
    )
    assert len(calls) == 1
    assert calls[0][1:] == (True, None, "windowed")
    report_path = Path(result["paths"]["report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_sha256"] == result["report"]["report_sha256"]
    assert report["item_ids"] == ["perseus:tlg0001.tlg0001.s1:tlg0001.tlg0001.s1@1"]
    assert Path(result["paths"]["gold"]).name.startswith("gold-")
    assert Path(result["paths"]["predictions"]).name.startswith("predictions-")


@pytest.mark.parametrize("kind", ["missing", "extra", "form", "short", "long"])
def test_pipeline_output_adversarial_shapes_are_rejected(tmp_path: Path, kind: str) -> None:
    manifest, perseus, tagging, parsing, environment = _fixture(tmp_path)
    item_id = "perseus:tlg0001.tlg0001.s1:tlg0001.tlg0001.s1@1"

    def fake_pipeline(
        sentences: list[object],
        *,
        parse: bool,
        batch_size: object,
        long_input: str,
    ) -> object:
        del parse, batch_size, long_input
        if kind == "missing":
            return {}
        if kind == "extra":
            return {item_id: list(sentences), "extra": list(sentences)}
        if kind == "short":
            return []
        if kind == "long":
            return [*sentences, *sentences]
        assert kind == "form"
        tokens = [{
            "id": 1, "form": "ἄλλο", "lemma": "λόγος", "upos": "NOUN",
            "xpos": "n--------", "feats": "_", "head": 0, "deprel": "root",
        }]
        return {item_id: tokens}

    with pytest.raises(runner.RunnerError):
        runner.run_development_evaluation(
            manifest=manifest,
            perseus_dev=perseus,
            papygreek_tagging=tagging,
            papygreek_parse=parsing,
            environment_receipt=environment,
            output_dir=tmp_path / "out",
            git_revision="b" * 40,
            pipeline=fake_pipeline,
        )


def test_supplied_source_hash_drift_is_rejected(tmp_path: Path) -> None:
    manifest, perseus, tagging, parsing, environment = _fixture(tmp_path)
    perseus.write_text(_CONLLU.replace("λόγος", "ἄλλος"), encoding="utf-8", newline="")

    with pytest.raises(runner.RunnerError, match="source hash mismatch"):
        runner.run_development_evaluation(
            manifest=manifest,
            perseus_dev=perseus,
            papygreek_tagging=tagging,
            papygreek_parse=parsing,
            environment_receipt=environment,
            output_dir=tmp_path / "out",
            git_revision="c" * 40,
            pipeline=lambda sentences, **kwargs: list(sentences),
        )


def test_manifest_identity_metadata_must_match_source(tmp_path: Path) -> None:
    manifest, perseus, tagging, parsing, environment = _fixture(tmp_path)
    manifest["items"][0]["document_id"] = "evil"  # type: ignore[index]
    manifest = manifest_mod.stamp_document(manifest)
    with pytest.raises(runner.RunnerError, match="document_id differs"):
        runner.run_development_evaluation(
            manifest=manifest,
            perseus_dev=perseus,
            papygreek_tagging=tagging,
            papygreek_parse=parsing,
            environment_receipt=environment,
            output_dir=tmp_path / "out",
            git_revision="d" * 40,
            pipeline=lambda sentences, **kwargs: list(sentences),
        )


@pytest.mark.parametrize(
    "field,value",
    [("id", "1"), ("id", True), ("head", "0"), ("head", False)],
)
def test_pipeline_token_ids_and_heads_must_be_strict_integers(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    manifest, perseus, tagging, parsing, environment = _fixture(tmp_path)
    item_id = "perseus:tlg0001.tlg0001.s1:tlg0001.tlg0001.s1@1"
    token: dict[str, object] = {
        "id": 1,
        "form": "λόγος",
        "lemma": "λόγος",
        "upos": "NOUN",
        "xpos": "n--------",
        "feats": "Case=Nom|Gender=Masc|Number=Sing",
        "head": 0,
        "deprel": "root",
    }
    token[field] = value
    with pytest.raises(runner.RunnerError):
        runner.run_development_evaluation(
            manifest=manifest,
            perseus_dev=perseus,
            papygreek_tagging=tagging,
            papygreek_parse=parsing,
            environment_receipt=environment,
            output_dir=tmp_path / "out",
            git_revision="e" * 40,
            pipeline=lambda sentences, **kwargs: {item_id: [token]},
        )
