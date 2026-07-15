"""Focused contract and leakage tests for development source manifests."""

from __future__ import annotations

import json
import hashlib
import unicodedata
import sys
from pathlib import Path

import pytest

TRAINING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING))
import development_manifest as manifest  # noqa: E402

_REVISIONS = {"ud_perseus": "fixture-1", "papygreek": "fixture-1", "pedalion": "fixture-1"}


def _sentence(sent_id: str, forms: tuple[str, ...], *, newdoc: str | None = None) -> str:
    comments = [f"# sent_id = {sent_id}", f"# text = {' '.join(forms)}"]
    if newdoc:
        comments.insert(0, f"# newdoc id = {newdoc}")
    rows = []
    for index, form in enumerate(forms, 1):
        head = 0 if index == 1 else 1
        relation = "root" if index == 1 else "dep"
        rows.append(f"{index}\t{form}\t{form}\tNOUN\t_\t_\t{head}\t{relation}\t_\t_")
    return "\n".join(comments + rows) + "\n\n"


def _fixture(tmp_path: Path, *, audit_docs: list[str] | None = None) -> tuple[Path, ...]:
    perseus = tmp_path / "perseus-dev.conllu"
    perseus.write_text(
        _sentence("tlg0001.tlg001.fixture.xml@1", ("ἄλφα", "βῆτα"))
        + _sentence("tlg0002.tlg001.fixture.xml@1", ("γ",)),
        encoding="utf-8",
    )
    locked = tmp_path / "perseus-test.conllu"
    locked.write_text(
        _sentence("tlg0002.tlg001.other.xml@9", ("δ",)), encoding="utf-8"
    )
    tagging = tmp_path / "papy-tagging.conllu"
    tagging.write_text(
        _sentence("papygreek-dev:doc-1@1", ("λόγος", "καί"), newdoc="doc-1")
        + _sentence("papygreek-dev:doc-2@1", ("ἄλφα",)),
        encoding="utf-8",
    )
    parse = tmp_path / "papy-parse.conllu"
    parse.write_text(
        _sentence("papygreek-dev:doc-1@1", ("λόγος", "καί"), newdoc="doc-1").replace(
            "\tdep\t", "\tobj\t"
        ),
        encoding="utf-8",
    )
    locked_manifest = tmp_path / "papy-locked.json"
    locked_manifest.write_text(json.dumps({"doc_ids": ["locked-papy"]}, indent=2), encoding="utf-8")
    audit = tmp_path / "papy-audit.json"
    audit.write_text(json.dumps({"excluded_document_ids": audit_docs or ["training-only"]}, indent=2), encoding="utf-8")
    training = tmp_path / "training"
    training.mkdir()
    (training / "full-train.jsonl").write_text(json.dumps({"tokens": ["seen"]}) + "\n", encoding="utf-8")
    (training / "full-dev.jsonl").write_text(
        json.dumps({"tokens": ["heldout"]}) + "\n",
        encoding="utf-8",
    )
    return perseus, locked, tagging, parse, locked_manifest, training, audit


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pinned(args: tuple[Path, ...]) -> dict[str, str]:
    result = {
        "perseus_dev": _sha(args[0]),
        "perseus_locked": _sha(args[1]),
        "papygreek_tagging": _sha(args[2]),
        "papygreek_parse": _sha(args[3]),
        "papygreek_locked_manifest": _sha(args[4]),
        "papygreek_training_work_audit": _sha(args[6]),
    }
    for name in ("full-train.jsonl", "full-dev.jsonl"):
        path = args[5] / name
        if path.is_file():
            result[f"training:{name}"] = _sha(path)
    return result


def _build(args: tuple[Path, ...], **overrides):
    kwargs = {
        "perseus_dev": args[0],
        "perseus_locked": args[1],
        "papygreek_tagging": args[2],
        "papygreek_parse": args[3],
        "papygreek_locked_manifest": args[4],
        "training_dir": args[5],
        "papygreek_training_work_audit": args[6],
        "expected_source_hashes": _pinned(args),
        "source_revisions": _REVISIONS,
    }
    kwargs.update(overrides)
    return manifest.build_manifest(**kwargs)


def test_strict_hash_round_trip_and_duplicate_json(tmp_path: Path) -> None:
    document = manifest.stamp_document({"format": "fixture", "items": [1, 2]})
    path = tmp_path / "document.json"
    manifest.write_document(document, path)
    assert manifest.load_document(path) == document
    assert manifest.verify_document(document)["manifest_sha256"] == document["manifest_sha256"]
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(manifest.ManifestError, match="duplicate"):
        manifest.load_document(path, verify=False)


def test_manifest_cli_writes_a_verified_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _fixture(tmp_path)
    pins = tmp_path / "pins.json"
    pins.write_text(
        json.dumps(
            {
                "format": "pyaegean-development-source-pins/1",
                "expected_source_hashes": _pinned(args),
                "source_revisions": _REVISIONS,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "manifest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "development_manifest.py",
            "--perseus-dev",
            str(args[0]),
            "--perseus-locked",
            str(args[1]),
            "--papygreek-tagging",
            str(args[2]),
            "--papygreek-parse",
            str(args[3]),
            "--papygreek-locked-manifest",
            str(args[4]),
            "--training-dir",
            str(args[5]),
            "--papygreek-training-work-audit",
            str(args[6]),
            "--pins",
            str(pins),
            "--output",
            str(output),
        ],
    )
    manifest.main()
    loaded = manifest.load_document(output)
    manifest.verify_manifest(loaded)


def test_strict_json_rejects_nonfinite_oversized_and_tampered_documents(tmp_path: Path) -> None:
    with pytest.raises(manifest.ManifestError, match="non-finite"):
        manifest.canonical_json({"value": float("nan")})
    document = manifest.stamp_document({"format": "fixture", "items": []})
    tampered = dict(document, items=[1])
    with pytest.raises(manifest.ManifestError, match="mismatch"):
        manifest.verify_document(tampered)
    path = tmp_path / "oversized.json"
    path.write_bytes(b"{" + b"\"x\":\"" + b"a" * manifest.MAX_DOCUMENT_BYTES + b"\"}")
    with pytest.raises(manifest.ManifestError, match="exceeds"):
        manifest.load_document(path, verify=False)


def test_manifest_excludes_locked_work_and_merges_papy_tracks(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    result = _build(args)
    ids = [item["item_id"] for item in result["items"]]
    assert all("tlg0002.tlg001" not in item for item in ids)
    merged = next(
        item
        for item in result["items"]
        if item["sentence_id"] == "papygreek-dev:doc-1@1"
    )
    assert merged["document_id"] == "doc-1"
    assert merged["tracks"] == ["parse", "tagging"]
    assert merged["tasks"] == ["parse", "tagging"]
    assert result["audit"]["excluded_counts"]["perseus_locked_work"] == 1
    assert set(("tragedy", "nt_koine", "byzantine", "diplomatic")) <= set(result["slices"])


@pytest.mark.parametrize(
    "payload,missing",
    [
        (b'{"tokens":["a"],"tokens":["b"]}\n', False),
        (b'{"tokens":["a"],"junk":NaN}\n', False),
        (b'{"tokens":["a\xff"]}\n', False),
        (b"", True),
    ],
)
def test_training_jsonl_is_strict_utf8_and_both_files_are_required(
    tmp_path: Path,
    payload: bytes,
    missing: bool,
) -> None:
    args = _fixture(tmp_path)
    target = args[5] / "full-dev.jsonl"
    if missing:
        target.unlink()
    else:
        target.write_bytes(payload)
    with pytest.raises(manifest.ManifestError):
        _build(args)


@pytest.mark.parametrize(
    "sent_id",
    ["papygreekevil:doc-1@1", "papygreek-dev:doc-1@y", "papygreek-dev:doc-1@0"],
)
def test_papygreek_identity_requires_exact_namespace_and_positive_ordinal(
    tmp_path: Path,
    sent_id: str,
) -> None:
    args = _fixture(tmp_path)
    args[2].write_text(_sentence(sent_id, ("λόγος",)), encoding="utf-8")
    with pytest.raises(manifest.ManifestError):
        _build(args)


def test_manifest_is_input_order_deterministic_and_detects_training_overlap(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    first = _build(args)
    args[2].write_text(
        _sentence("papygreek-dev:doc-2@1", ("ἄλφα",))
        + _sentence("papygreek-dev:doc-1@1", ("λόγος", "καί"), newdoc="doc-1"),
        encoding="utf-8",
    )
    second = _build(args)
    assert [item["item_id"] for item in first["items"]] == [item["item_id"] for item in second["items"]]
    assert [item["content_sha256"] for item in first["items"]] == [item["content_sha256"] for item in second["items"]]
    (args[5] / "full-train.jsonl").write_text(json.dumps({"tokens": ["ἄλφα"]}) + "\n", encoding="utf-8")
    with pytest.raises(manifest.ManifestError, match="overlaps training"):
        _build(args)


def test_manifest_requires_training_work_audit(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    with pytest.raises(manifest.ManifestError, match="training_work_audit"):
        _build(args, papygreek_training_work_audit=None)


def test_real_papygreek_namespace_is_checked_against_locked_and_training_docs(
    tmp_path: Path,
) -> None:
    args = _fixture(tmp_path, audit_docs=["doc-2"])
    result = _build(args)
    assert not any(item["document_id"] == "doc-2" for item in result["items"])
    assert result["audit"]["excluded_counts"]["papygreek_training_work"] == 1

    args[2].write_text(
        args[2].read_text(encoding="utf-8")
        + _sentence("papygreek-dev:locked-papy@1", ("ἄνθρωπος",)),
        encoding="utf-8",
    )
    with pytest.raises(manifest.ManifestError, match="overlaps locked test"):
        _build(args)


def test_source_hash_drift_is_rejected_before_manifest_creation(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    pinned = _pinned(args)
    args[2].write_text(
        args[2].read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(manifest.ManifestError, match="source hash drift"):
        _build(args, expected_source_hashes=pinned)


def test_nfd_and_punctuation_stripped_training_overlap_fail_closed(tmp_path: Path) -> None:
    args = _fixture(tmp_path)
    decomposed = unicodedata.normalize("NFD", "λόγος")
    args[2].write_text(
        _sentence("papygreek-dev:doc-3@1", (decomposed, ".")), encoding="utf-8"
    )
    (args[5] / "full-train.jsonl").write_text(
        json.dumps({"tokens": ["λόγος"]}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(manifest.ManifestError, match="overlaps training"):
        _build(args)


def test_train_frequency_counts_do_not_read_selection_dev_rows(tmp_path: Path) -> None:
    args = _fixture(tmp_path, audit_docs=["doc-2"])
    (args[5] / "full-dev.jsonl").write_text(
        json.dumps({"tokens": ["ἄλφα"]}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result = _build(args)
    perseus = next(item for item in result["items"] if item["source"] == "perseus")
    assert perseus["train_token_frequencies"][0] == 0


def test_duplicate_development_content_is_deweighted_deterministically(
    tmp_path: Path,
) -> None:
    args = _fixture(tmp_path)
    args[2].write_text(
        args[2].read_text(encoding="utf-8")
        + _sentence("papygreek-dev:doc-3@1", ("λόγος", "καί")),
        encoding="utf-8",
    )
    result = _build(args)
    duplicate_rows = result["audit"]["duplicate_content_exclusions"]
    assert len(duplicate_rows) == 1
    assert duplicate_rows[0]["kept_item_id"].endswith("papygreek-dev:doc-1@1")
    assert duplicate_rows[0]["excluded_item_id"].endswith("papygreek-dev:doc-3@1")


def test_slice_boundaries_and_unavailable_domains_are_explicit() -> None:
    lengths = (5, 6, 10, 11, 20, 21, 40, 41)
    items = []
    for index, length in enumerate(lengths):
        items.append(
            {
                "item_id": f"fixture:{index}",
                "source": "perseus",
                "document_id": f"d{index}",
                "work_id": f"w{index}",
                "scored_token_count": length,
                "train_token_frequencies": [1] * length,
                "domain_ids": ["literary"],
                "annotation_conventions": ["agdt"],
            }
        )
    slices = manifest._build_slices(items)
    assert slices["length:1-5"]["item_count"] == 1
    assert slices["length:6-10"]["item_count"] == 2
    assert slices["length:11-20"]["item_count"] == 2
    assert slices["length:21-40"]["item_count"] == 2
    assert slices["length:41+"]["item_count"] == 1
    for name in ("tragedy", "nt_koine", "byzantine", "diplomatic"):
        assert slices[name]["available"] is False
        assert slices[name]["item_ids"] == []
        assert slices[name]["reason"]
