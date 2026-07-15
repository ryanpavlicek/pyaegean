"""Work-level PapyGreek/Pedalion leakage guards."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_papygreek_dev as bpd  # noqa: E402
import build_papygreek_fold as bpf  # noqa: E402


def _document(*, tm_id: str, artificial: bool = False) -> str:
    artificial_row = (
        '<word id="2" form_reg="[0]" lemma_reg="" postag_reg="" '
        'relation_reg="PRED" head_reg="0" artificial="elliptic" '
        'insertion_id="e1" orig_form="[0]"/>'
        if artificial
        else ""
    )
    head = "2" if artificial else "0"
    return (
        f'<treebank text_id="{tm_id}">'
        f'<document_meta name="x.xml" tm_id="{tm_id}"/>'
        '<sentence id="1">'
        f'<word id="1" form_reg="λόγος" lemma_reg="λόγος" postag_reg="n-s---mn-" '
        f'relation_reg="SBJ" head_reg="{head}" orig_form="λόγος"/>'
        f"{artificial_row}"
        "</sentence></treebank>"
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "papy"
    documentary = repo / "documentary" / "x"
    documentary.mkdir(parents=True)
    (documentary / "training.xml").write_text(
        _document(tm_id="100"), encoding="utf-8"
    )
    (documentary / "fold.xml").write_text(_document(tm_id="200"), encoding="utf-8")
    (documentary / "dev.xml").write_text(
        _document(tm_id="300", artificial=True), encoding="utf-8"
    )
    return repo


def test_pedalion_reference_binds_work_ids_and_bytes(tmp_path: Path) -> None:
    source = tmp_path / "papyri.xml"
    source.write_text(
        '<treebank><sentence id="1" document_id="100"/>'
        '<sentence id="2" document_id="200"/></treebank>',
        encoding="utf-8",
    )
    work_ids, record = bpf.pedalion_training_work_reference(source)
    assert work_ids == {"100", "200"}
    assert record["sentences"] == 2 and record["work_ids"] == 2
    assert len(record["source_sha256"]) == 64
    assert record["source_bytes"] == source.stat().st_size


def test_fold_excludes_an_entire_training_work_in_both_layers(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    training = tmp_path / "training"
    training.mkdir()

    reg, reg_manifest = bpf.build(
        repo, training, layer="reg", training_work_ids={"100"}
    )
    orig, orig_manifest = bpf.build(
        repo, training, layer="orig", training_work_ids={"100"}
    )

    assert "papygreek:fold@1" in reg and "papygreek:training@1" not in reg
    assert "papygreek:fold@1" in orig and "papygreek:training@1" not in orig
    for manifest in (reg_manifest, orig_manifest):
        assert manifest["work_disjointness"]["result"] == "pass"
        assert manifest["work_disjointness"]["excluded_documents"] == [
            {
                "document_id": "training",
                "work_id": "100",
                "status_ok_sentences": 1,
                "sentences_already_form_excluded": 0,
                "sentences_newly_excluded": 1,
            }
        ]
        assert manifest["work_disjointness"]["newly_excluded_document_count"] == 1
        assert manifest["excluded"]["training_work_overlap"] == 1


def test_dev_pool_excludes_training_documents_instead_of_reclassifying_them(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    training = tmp_path / "training"
    training.mkdir()
    fold, _manifest = bpf.build(
        repo, training, layer="reg", training_work_ids={"100"}
    )
    fold_path = tmp_path / "fold.conllu"
    fold_path.write_text(fold, encoding="utf-8")

    tagging, _parse, manifest = bpd.build(
        repo,
        training,
        fold_path,
        training_work_ids={"100"},
    )

    assert "papygreek-dev:dev@1" in tagging
    assert "papygreek-dev:training@1" not in tagging
    document_sets = manifest["document_sets"]
    assert document_sets["fold_documents"] == 1
    assert document_sets["nonfold_documents"] == 1
    assert document_sets["training_overlap_document_ids"] == ["training"]


def test_missing_source_work_identity_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "papy"
    documentary = repo / "documentary"
    documentary.mkdir(parents=True)
    (documentary / "unknown.xml").write_text(
        '<treebank><document_meta name="unknown.xml"/><sentence id="1"/></treebank>',
        encoding="utf-8",
    )
    training = tmp_path / "training"
    training.mkdir()

    try:
        bpf.build(repo, training, training_work_ids=set())
    except ValueError as exc:
        assert "tm_id" in str(exc)
    else:  # pragma: no cover - the fail-closed invariant
        raise AssertionError("missing work identity was accepted")
