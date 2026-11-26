"""Tests for portable, verifiable, license-clean research bundles (`aegean.bundle`)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import aegean
from aegean.bundle import (
    BUNDLE_FORMAT,
    create_bundle,
    extract_bundle,
    hydrate_bundle,
    inspect_bundle,
    is_redistributable_license,
    verify_bundle,
)
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io.review import from_review_table, to_review_table
from aegean.io.workbench import WorkbenchBackup


def _greek_corpus(*, license_str: str = "CC BY-SA 4.0") -> Corpus:
    doc = Document(
        id="doc1",
        script_id="greek",
        tokens=(
            Token(
                text="λόγος",
                kind=TokenKind.WORD,
                position=0,
                line_no=1,
                annotations={"lemma": "λόγος", "upos": "NOUN", "lemma_source": "lexicon"},
            ),
        ),
        lines=((0,),),
    )
    return Corpus(
        documents=(doc,),
        script_id="greek",
        provenance=Provenance(
            source="Test edition",
            license=license_str,
            citation="Test Edition (2026)",
            url="https://example.org/corpus",
        ),
    )


def test_license_redistribution_guard() -> None:
    assert is_redistributable_license("Apache-2.0") is True
    assert is_redistributable_license("CC BY-SA 4.0") is True
    assert is_redistributable_license("CC0 1.0") is True
    assert is_redistributable_license("CC BY-NC-SA 4.0") is False
    assert is_redistributable_license("Non-Commercial Academic Use Only") is False
    assert is_redistributable_license("© École Française d'Athènes") is False


def test_create_verify_extract_and_hydrate_full_bundle(tmp_path: Path) -> None:
    corpus = _greek_corpus()
    review_csv = tmp_path / "review.csv"
    to_review_table(corpus, review_csv, fields=("lemma",), layout="editable", reviewer="alice")
    wb_state = WorkbenchBackup(
        annotations=[{"id": "a1", "target": {"kind": "word", "value": "KU-RO"}}]
    )
    receipt = {"schema": "test-receipt/1", "model_id": "grc-joint-v3"}

    b1 = tmp_path / "study1.zip"
    b2 = tmp_path / "study2.zip"
    fixed_ts = "2026-11-26T00:00:00+00:00"
    m1 = create_bundle(
        b1,
        corpus=corpus,
        title="Haghia Triada study",
        description="Reproducible bundle test",
        workbench_state=wb_state,
        review_paths=[review_csv],
        receipts=[receipt],
        metadata={"author": "researcher"},
        created_at=fixed_ts,
    )
    create_bundle(
        b2,
        corpus=corpus,
        title="Haghia Triada study",
        description="Reproducible bundle test",
        workbench_state=wb_state,
        review_paths=[review_csv],
        receipts=[receipt],
        metadata={"author": "researcher"},
        created_at=fixed_ts,
    )

    # Byte-for-byte deterministic zip output
    assert hashlib.sha256(b1.read_bytes()).hexdigest() == hashlib.sha256(b2.read_bytes()).hexdigest()
    assert m1.format == BUNDLE_FORMAT
    assert m1.redistributable is True
    assert m1.corpus_embedded is True

    # Editable review companion must be bundled automatically
    member_paths = {m.path for m in m1.members}
    assert "corpus.json.gz" in member_paths
    assert "workbench-state.json" in member_paths
    assert "review/review.csv" in member_paths
    assert "review/review.csv.companion.json" in member_paths
    assert "CITATIONS.bib" in member_paths

    # Inspect + verify
    inspected = inspect_bundle(b1)
    assert inspected.title == "Haghia Triada study"
    report = verify_bundle(b1)
    assert report.ok is True
    assert report.checked_members == len(m1.members)

    # Hydrate into a fresh directory and confirm review companion validates cleanly
    out_dir = tmp_path / "hydrated"
    hydrated = hydrate_bundle(b1, dest=out_dir)
    assert hydrated.corpus is not None
    assert len(hydrated.corpus) == 1
    assert hydrated.workbench_state is not None
    assert len(hydrated.workbench_state.annotations) == 1
    assert "review.csv" in hydrated.review_files
    assert hydrated.metadata == {"author": "researcher"}
    # Re-applying the unpacked editable CSV verifies companion integrity
    reapplied = from_review_table(hydrated.review_files["review.csv"], hydrated.corpus)
    assert len(reapplied) == 1


def test_nc_corpus_defaults_to_pointer_and_blocks_accidental_redistribution(tmp_path: Path) -> None:
    nc_corpus = _greek_corpus(license_str="CC BY-NC-SA 4.0")

    # With a dataset id, auto mode emits a redistributable pointer bundle without embedding NC text
    pointer_zip = tmp_path / "nc_pointer.zip"
    manifest = create_bundle(
        pointer_zip,
        corpus=nc_corpus,
        dataset="damos",
        filter_spec={"site": "Pylos"},
    )
    assert manifest.redistributable is True
    assert manifest.corpus_embedded is False
    assert manifest.corpus_ref is not None
    assert manifest.corpus_ref.dataset == "damos"
    assert manifest.corpus_ref.filter_spec == {"site": "Pylos"}
    assert "corpus.json.gz" not in {m.path for m in manifest.members}

    # Without dataset or URL, auto mode refuses to silently embed NC text
    no_ptr = Corpus(
        documents=nc_corpus.documents,
        script_id="greek",
        provenance=Provenance(source="Private NC", license="CC BY-NC 4.0"),
    )
    with pytest.raises(ValueError, match="non-commercial/restricted"):
        create_bundle(tmp_path / "blocked.zip", corpus=no_ptr)

    # Explicit embed_corpus="always" works for private use and flags redistributable=False
    private_zip = tmp_path / "nc_private.zip"
    priv_manifest = create_bundle(
        private_zip,
        corpus=no_ptr,
        embed_corpus="always",
    )
    assert priv_manifest.corpus_embedded is True
    assert priv_manifest.redistributable is False
    report = verify_bundle(private_zip)
    assert report.ok is True
    assert report.redistributable is False
    assert report.warnings


def test_pointer_hydration_for_bundled_corpus_offline(tmp_path: Path) -> None:
    la = aegean.load("lineara")
    ptr_zip = tmp_path / "la_pointer.zip"
    manifest = create_bundle(
        ptr_zip,
        corpus=la,
        dataset="lineara",
        filter_spec={"site": "Haghia Triada"},
        embed_corpus="never",
    )
    assert manifest.corpus_embedded is False
    assert manifest.corpus_ref is not None

    hydrated = hydrate_bundle(ptr_zip)
    assert hydrated.corpus is not None
    assert len(hydrated.corpus) > 0
    assert all(d.meta.site == "Haghia Triada" for d in hydrated.corpus)


def test_verify_rejects_tampered_member_and_zip_slip(tmp_path: Path) -> None:
    corpus = _greek_corpus()
    good_zip = tmp_path / "good.zip"
    create_bundle(good_zip, corpus=corpus)

    # Tamper with citations.json without updating manifest.json
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(good_zip, "r") as zin, zipfile.ZipFile(tampered, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "CITATIONS.txt":
                data = b"tampered citation\n"
            zout.writestr(info, data)
    rep = verify_bundle(tampered)
    assert rep.ok is False
    assert any("SHA-256 mismatch" in e for e in rep.errors)
    with pytest.raises(ValueError, match="bundle verification failed"):
        extract_bundle(tampered, tmp_path / "out_bad")

    # Zip-slip traversal member rejected
    slip_zip = tmp_path / "slip.zip"
    with zipfile.ZipFile(good_zip, "r") as zin, zipfile.ZipFile(slip_zip, "w") as zout:
        for info in zin.infolist():
            zout.writestr(info, zin.read(info.filename))
        zout.writestr("../evil.txt", b"escape")
    slip_rep = verify_bundle(slip_zip)
    assert slip_rep.ok is False
    assert any("unsafe member path" in e for e in slip_rep.errors)


def test_bundle_cli_end_to_end(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    runner = CliRunner()
    app = _build_app()
    out_zip = tmp_path / "cli_bundle.zip"
    hydrate_dir = tmp_path / "cli_hydrated"

    r_create = runner.invoke(
        app,
        [
            "bundle",
            "create",
            str(out_zip),
            "--corpus",
            "lineara",
            "--site",
            "Haghia Triada",
            "--title",
            "HT CLI Bundle",
            "--json",
        ],
    )
    assert r_create.exit_code == 0, r_create.output
    created_meta = json.loads(r_create.output)
    assert created_meta["title"] == "HT CLI Bundle"

    r_inspect = runner.invoke(app, ["bundle", "inspect", str(out_zip), "--json"])
    assert r_inspect.exit_code == 0, r_inspect.output
    assert json.loads(r_inspect.output)["format"] == BUNDLE_FORMAT

    r_verify = runner.invoke(app, ["bundle", "verify", str(out_zip), "--json"])
    assert r_verify.exit_code == 0, r_verify.output
    assert json.loads(r_verify.output)["ok"] is True

    r_hydrate = runner.invoke(app, ["bundle", "hydrate", str(out_zip), str(hydrate_dir), "--json"])
    assert r_hydrate.exit_code == 0, r_hydrate.output
    hdata = json.loads(r_hydrate.output)
    assert hdata["documents"] > 0
    assert Path(hdata["corpus_path"]).is_file()
