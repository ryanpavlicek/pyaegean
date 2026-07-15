"""Correctness and hostile-input coverage for the PapyGreek fold checker."""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_papygreek_fold_correction as checker  # noqa: E402


def _block(sent_id: str, forms: list[str], *, text: str | None = None, lemma: str = "λόγος") -> str:
    lines = [f"# sent_id = {sent_id}", f"# text = {text if text is not None else ' '.join(forms)}"]
    for index, form in enumerate(forms, 1):
        lines.append(f"{index}\t{form}\t{lemma}\tNOUN\tn-s---mn-\tCase=Nom\t0\troot\t_\t_")
    return "\n".join(lines) + "\n"


def _write_gz(path: Path, blocks: list[str], *, raw: bytes | None = None) -> None:
    payload = raw if raw is not None else "\n".join(blocks).encode("utf-8") + b"\n"
    path.write_bytes(gzip.compress(payload, mtime=0))


def _manifest(path: Path, docs: list[tuple[str, int]]) -> None:
    path.write_text(
        json.dumps(
            {
                "work_disjointness": {
                    "result": "pass",
                    "newly_excluded_document_count": len(docs),
                    "newly_excluded_sentence_count": sum(count for _doc, count in docs),
                    "excluded_documents": [
                        {"document_id": doc, "sentences_newly_excluded": count}
                        for doc, count in docs
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    old_reg, new_reg, old_orig, new_orig, manifest = (
        tmp_path / name
        for name in ("old-reg.gz", "new-reg.gz", "old-orig.gz", "new-orig.gz", "manifest.json")
    )
    removed = _block("papygreek:doc-old@2", ["ἄνθρωπος"])
    kept_reg = _block("papygreek:doc-kept@1", ["λόγος", "."])
    kept_orig = _block("papygreek:doc-kept@1", ["λόγος", "."], text="λόγος .")
    _write_gz(old_reg, [kept_reg, removed])
    _write_gz(new_reg, [kept_reg])
    _write_gz(old_orig, [kept_orig, removed])
    _write_gz(new_orig, [kept_orig])
    _manifest(manifest, [("doc-old", 1)])
    return old_reg, new_reg, old_orig, new_orig, manifest


def test_receipt_proves_exact_removal_and_form_overlay(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    receipt = checker.check_fold_correction(*paths)

    assert receipt["schema"] == 1
    assert receipt["format"] == checker.RECEIPT_FORMAT
    assert receipt["removed_sent_ids"] == ["papygreek:doc-old@2"]
    assert receipt["removed_document_ids"] == ["doc-old"]
    assert receipt["counts"]["removed_sentences"] == 1
    assert receipt["counts"]["removed_tokens"] == 1
    assert receipt["form_difference_count"] == 1
    assert receipt["gold_column_difference_count"] == 0
    assert receipt["retained_byte_identity"] == {"regularized": True, "diplomatic": True}
    assert receipt["artifacts"]["old_regularized"]["sha256"] == hashlib.sha256(
        paths[0].read_bytes()
    ).hexdigest()
    assert checker.receipt_json(receipt) == checker.receipt_json(receipt)
    unstamped = dict(receipt)
    digest = unstamped.pop("receipt_sha256")
    assert digest == hashlib.sha256(checker.receipt_json(unstamped).encode()).hexdigest()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "missing sent_id"),
        ("duplicate", "duplicate sent_id"),
    ],
)
def test_malformed_sentence_identity_fails_closed(
    tmp_path: Path, mutation: str, message: str
) -> None:
    paths = list(_paths(tmp_path))
    malformed = _block("papygreek:doc-kept@1", ["λόγος"])
    if mutation == "missing":
        malformed = malformed.replace("# sent_id = papygreek:doc-kept@1\n", "")
    else:
        malformed = malformed.replace(
            "# text = λόγος\n", "# sent_id = papygreek:doc-kept@1\n# text = λόγος\n"
        )
    target = paths[1]
    _write_gz(target, [malformed])
    with pytest.raises(checker.FoldCorrectionError, match=message):
        checker.check_fold_correction(*paths)


def test_non_utf8_and_oversized_inputs_are_rejected(tmp_path: Path) -> None:
    paths = list(_paths(tmp_path))
    paths[1].write_bytes(gzip.compress(b"# sent_id = x\n1\t\xff\t_\tNOUN\tn\t_\t0\troot\t_\t_\n"))
    with pytest.raises(checker.FoldCorrectionError, match="not UTF-8"):
        checker.check_fold_correction(*paths)

    _write_gz(paths[1], [_block("papygreek:doc-kept@1", ["λόγος"])])
    with pytest.raises(checker.FoldCorrectionError, match="exceeds limit"):
        checker.check_fold_correction(*paths, max_artifact_bytes=10)


def test_noncanonical_rows_and_manifest_values_are_rejected(tmp_path: Path) -> None:
    paths = list(_paths(tmp_path))
    bad_ids = _block("papygreek:doc-kept@1", ["λόγος", "."]).replace(
        "2\t.\t", "1\t.\t"
    )
    _write_gz(paths[1], [bad_ids])
    with pytest.raises(checker.FoldCorrectionError, match="token IDs"):
        checker.check_fold_correction(*paths)

    paths = list(_paths(tmp_path / "again"))
    paths[4].write_text(
        '{"work_disjointness":{"result":"pass","result":"pass"}}',
        encoding="utf-8",
    )
    with pytest.raises(checker.FoldCorrectionError, match="duplicate manifest key"):
        checker.check_fold_correction(*paths)

    paths = list(_paths(tmp_path / "third"))
    payload = gzip.decompress(paths[1].read_bytes()).rstrip(b"\n") + b"\n"
    paths[1].write_bytes(gzip.compress(payload, mtime=0))
    with pytest.raises(checker.FoldCorrectionError, match="does not end with an empty line"):
        checker.check_fold_correction(*paths)


def test_retained_drift_and_unequal_removed_ids_are_rejected(tmp_path: Path) -> None:
    paths = list(_paths(tmp_path))
    drift = _block("papygreek:doc-kept@1", ["λόγος", "!"])
    _write_gz(paths[1], [drift])
    with pytest.raises(checker.FoldCorrectionError, match="retained sentence block drift"):
        checker.check_fold_correction(*paths)

    # Restore the regularized artifact and remove a different diplomatic sentence.
    kept_orig = _block("papygreek:doc-kept@1", ["λόγος", "."], text="λόγος .")
    _write_gz(paths[1], [_block("papygreek:doc-kept@1", ["λόγος", "."])])
    _write_gz(paths[3], [kept_orig, _block("papygreek:doc-old@2", ["ἄνθρωπος"])])
    with pytest.raises(checker.FoldCorrectionError, match="removed sentence IDs differ"):
        checker.check_fold_correction(*paths)


def test_manifest_document_mismatch_and_new_order_fail(tmp_path: Path) -> None:
    paths = list(_paths(tmp_path))
    _manifest(paths[4], [("different-doc", 1)])
    with pytest.raises(checker.FoldCorrectionError, match="removed document counts"):
        checker.check_fold_correction(*paths)

    _manifest(paths[4], [("doc-old", 1)])
    kept = _block("papygreek:doc-kept@1", ["λόγος", "."])
    old_extra = _block("papygreek:doc-extra@1", ["πόλις"])
    _write_gz(paths[0], [kept, old_extra, _block("papygreek:doc-old@2", ["ἄνθρωπος"])])
    _write_gz(paths[2], [kept, old_extra, _block("papygreek:doc-old@2", ["ἄνθρωπος"])])
    _write_gz(paths[1], [kept, old_extra])
    _write_gz(paths[3], [old_extra, kept])
    with pytest.raises(checker.FoldCorrectionError, match="retained sentence order"):
        checker.check_fold_correction(*paths)


def test_gold_difference_beyond_form_fails(tmp_path: Path) -> None:
    paths = list(_paths(tmp_path))
    bad = _block("papygreek:doc-kept@1", ["λόγος", "."], text="λόγος .", lemma="ἄνθρωπος")
    _write_gz(paths[2], [bad, _block("papygreek:doc-old@2", ["ἄνθρωπος"])])
    _write_gz(paths[3], [bad])
    with pytest.raises(checker.FoldCorrectionError, match="gold-column difference beyond FORM"):
        checker.check_fold_correction(*paths)


def test_cli_prints_json_receipt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = _paths(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    assert checker.main(
        [
            "--old-reg", str(paths[0]),
            "--new-reg", str(paths[1]),
            "--old-orig", str(paths[2]),
            "--new-orig", str(paths[3]),
            "--new-reg-manifest", str(paths[4]),
            "--output", str(receipt_path),
        ]
    ) == 0
    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == parsed
    assert parsed["form_difference_count"] == 1
    assert "duration" not in output.lower()
