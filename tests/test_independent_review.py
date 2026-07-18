"""Focused tests for the bounded public independent-review path."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reproduce_review.py"
MANIFEST = ROOT / "review" / "review-manifest-v1.json"

_SPEC = importlib.util.spec_from_file_location("independent_review_under_test", SCRIPT)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - repository layout guard
    raise RuntimeError(f"cannot load {SCRIPT}")
review = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = review
_SPEC.loader.exec_module(review)


def _write_canonical(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _copy_review_tree(destination: Path) -> Path:
    root = destination / "source"
    shutil.copytree(
        ROOT / "src",
        root / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    manifest = _manifest()
    for relative in [review.MANIFEST_PATH, *(record["path"] for record in manifest["records"])]:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _run(
    root: Path,
    *arguments: str,
    cache: Path | None = None,
    legacy_encoding: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "0" if legacy_encoding else "1"
    if legacy_encoding:
        environment["PYTHONIOENCODING"] = "cp1252"
    environment["PYTHONDONTWRITEBYTECODE"] = "0"
    if cache is not None:
        environment["PYAEGEAN_CACHE"] = str(cache)
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "reproduce_review.py"), *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
        env=environment,
    )


def test_manifest_and_current_offline_result_verify_exactly() -> None:
    manifest, raw = review.load_manifest(ROOT)
    report = review.verify_review(ROOT, require_clean=False)

    assert raw == review.canonical_json(manifest).encode("utf-8") + b"\n"
    assert report["ok"] is True
    assert report["manifest"]["record_count"] == len(manifest["records"])
    assert report["deterministic_result"]["benchmark"] == {
        "accent": {"correct": 6, "total": 6},
        "betacode": {"correct": 9, "total": 9},
        "lemma": {"correct": 5, "total": 18},
        "morphology": {"correct": 8, "total": 11},
        "pos": {"correct": 10, "total": 20},
        "scansion": {"correct": 5, "total": 5},
        "syllabify": {"correct": 6, "total": 6},
        "tokenize": {"correct": 5, "total": 5},
    }
    assert len(report["deterministic_result"]["sha256"]) == 64


def test_manifest_covers_claim_sources_and_reviewer_entry_points() -> None:
    manifest = _manifest()
    records = {record["path"]: record for record in manifest["records"]}
    claims = (ROOT / "training" / "results" / "published-claims.json").read_text(
        encoding="utf-8"
    )
    claim_sources = set(
        re.findall(r"training/results/[A-Za-z0-9_./-]+(?:\.json|\.txt)", claims)
    )
    assert claim_sources <= set(records)
    assert records["training/results/published-claims.json"]["role"] == "claims-registry"
    assert records["review/expected-results-v1.json"]["role"] == "expected-results"
    assert records["src/aegean/data/bundled/greek/benchmark_gold.json"]["role"] == (
        "benchmark-fixture"
    )
    for path in (
        "review/README.md",
        "review/MODEL_CARD.md",
        "review/DATA_CARD.md",
        "scripts/reproduce_review.py",
        ".github/ISSUE_TEMPLATE/reproduction_discrepancy.yml",
        ".github/ISSUE_TEMPLATE/maintainer_task.yml",
    ):
        assert path in records


@pytest.mark.parametrize(
    ("rewrite", "match"),
    [
        (lambda raw: b" " + raw, "canonical UTF-8 JSON"),
        (
            lambda raw: raw.replace(
                b'{"expected_results_path"',
                b'{"format":"duplicate","expected_results_path"',
                1,
            ),
            "duplicate JSON key",
        ),
        (
            lambda raw: raw.replace(b'"package_version":"0.57.1"', b'"package_version":NaN', 1),
            "non-finite JSON value",
        ),
    ],
)
def test_manifest_rejects_hostile_json_encodings(
    tmp_path: Path,
    rewrite: Callable[[bytes], bytes],
    match: str,
) -> None:
    candidate = tmp_path / "manifest.json"
    candidate.write_bytes(rewrite(MANIFEST.read_bytes()))
    with pytest.raises(review.ReviewVerificationError, match=match):
        review.load_manifest(tmp_path, candidate)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value["records"][0].__setitem__("path", "../outside"), "normalized"),
        (lambda value: value["records"][0].__setitem__("path", "a//b"), "normalized"),
        (lambda value: value["records"][0].__setitem__("role", "unknown"), "role is unknown"),
        (
            lambda value: value["records"][0].__setitem__("hash_mode", "unknown"),
            "hash_mode is unknown",
        ),
        (
            lambda value: value["records"][0].__setitem__("provenance", "unknown"),
            "provenance is unknown",
        ),
        (lambda value: value["records"].reverse(), "unique and sorted"),
        (lambda value: value["records"].append(value["records"][0]), "unique and sorted"),
    ],
)
def test_manifest_rejects_hostile_record_structure(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], Any],
    match: str,
) -> None:
    value = _manifest()
    mutate(value)
    candidate = tmp_path / "manifest.json"
    _write_canonical(candidate, value)
    with pytest.raises(review.ReviewVerificationError, match=match):
        review.load_manifest(tmp_path, candidate)


def test_manifest_rejects_case_colliding_paths(tmp_path: Path) -> None:
    value = _manifest()
    collision = dict(value["records"][0])
    collision["path"] = collision["path"].upper()
    value["records"].append(collision)
    value["records"].sort(key=lambda record: record["path"])
    candidate = tmp_path / "manifest.json"
    _write_canonical(candidate, value)

    with pytest.raises(review.ReviewVerificationError, match="unique and sorted"):
        review.load_manifest(tmp_path, candidate)


def test_checked_paths_refuse_symlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    link = root / "record.txt"
    link.write_text("record\n", encoding="utf-8")
    original = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == link or original(path),
    )
    with pytest.raises(review.ReviewVerificationError, match="must not traverse a symlink"):
        review._checked_path(root, "record.txt", where="record")


def test_text_hash_is_cross_platform_but_byte_hash_is_exact(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"alpha\nbeta\n")
    crlf.write_bytes(b"alpha\r\nbeta\r\n")

    assert review._sha256_file(lf, "text-lf") == review._sha256_file(crlf, "text-lf")
    assert review._sha256_file(lf, "bytes") != review._sha256_file(crlf, "bytes")


def test_text_records_verify_after_checkout_line_ending_conversion(tmp_path: Path) -> None:
    root = _copy_review_tree(tmp_path)
    target = root / "CONTRIBUTING.md"
    raw = target.read_bytes()
    converted = raw.replace(b"\r\n", b"\n") if b"\r\n" in raw else raw.replace(b"\n", b"\r\n")
    assert converted != raw
    target.write_bytes(converted)

    completed = _run(root, "--json")

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_byte_exact_evidence_records_are_lf_pinned() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "training/results/** text eol=lf" in attributes
    byte_records = [record for record in _manifest()["records"] if record["hash_mode"] == "bytes"]
    assert byte_records
    for record in byte_records:
        assert record["path"].startswith("training/results/")
        assert b"\r" not in (ROOT / record["path"]).read_bytes()


def test_network_guard_blocks_socket_creation() -> None:
    with review._network_forbidden():
        candidate = socket.socket()
        try:
            with pytest.raises(review.ReviewVerificationError, match="network access"):
                candidate.connect(("127.0.0.1", 9))
        finally:
            candidate.close()
        with pytest.raises(review.ReviewVerificationError, match="network access"):
            socket.create_connection(("127.0.0.1", 9))


def test_clean_source_archive_run_is_read_only_and_cache_free(tmp_path: Path) -> None:
    root = _copy_review_tree(tmp_path)
    cache = tmp_path / "cache-must-not-exist"
    before = _snapshot(root)

    completed = _run(root, "--json", cache=cache)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["repository"]["available"] is False
    assert report["repository"]["clean"] is None
    assert report["repository"]["head"] is None
    assert report["repository"]["reason"] in {"CalledProcessError", "FileNotFoundError"}
    assert _snapshot(root) == before
    assert not cache.exists()
    assert not list(root.rglob("__pycache__"))
    assert not list(root.rglob("*.pyc"))


def test_git_checkout_must_be_clean_unless_diagnosis_is_explicit(tmp_path: Path) -> None:
    root = _copy_review_tree(tmp_path)
    (root / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    for arguments in (
        ("init",),
        ("config", "user.email", "review@example.invalid"),
        ("config", "user.name", "Review Tests"),
        ("add", ".gitignore"),
        ("commit", "-m", "review fixture"),
    ):
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
    assert _run(root, "--json").returncode == 0

    (root / ".gitignore").write_text("*\n!.gitignore\n# dirty\n", encoding="utf-8")
    rejected = _run(root, "--json")
    accepted_for_diagnosis = _run(root, "--json", "--allow-dirty")

    assert rejected.returncode == 1
    assert "Git worktree is not clean" in json.loads(rejected.stdout)["error"]
    assert accepted_for_diagnosis.returncode == 0
    assert json.loads(accepted_for_diagnosis.stdout)["repository"]["clean"] is False


def test_tampered_record_fails_before_a_result_is_accepted(tmp_path: Path) -> None:
    root = _copy_review_tree(tmp_path)
    target = root / "docs" / "benchmarks.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nmodified\n", encoding="utf-8")

    completed = _run(root, "--json")

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["ok"] is False
    assert "SHA-256 mismatch for docs/benchmarks.md" in report["error"]


def test_json_report_forces_utf8_on_a_legacy_windows_console() -> None:
    completed = _run(ROOT, "--allow-dirty", "--json", legacy_encoding=True)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["deterministic_result"]["pipeline"][0]["text"] == "ἐν"


def test_oversized_record_is_rejected_before_hashing(tmp_path: Path) -> None:
    root = _copy_review_tree(tmp_path)
    target = root / "docs" / "benchmarks.md"
    with target.open("wb") as handle:
        handle.truncate(review.MAX_RECORD_BYTES + 1)

    completed = _run(root, "--json")

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["ok"] is False
    assert "size" in report["error"] and "outside" in report["error"]


def test_issue_forms_have_unique_required_fields() -> None:
    for name in ("reproduction_discrepancy.yml", "maintainer_task.yml"):
        text = (ROOT / ".github" / "ISSUE_TEMPLATE" / name).read_text("utf-8")
        for field in ("name", "description", "title"):
            assert re.search(rf"(?m)^{field}:\s+\S", text)
        assert re.search(r"(?m)^body:\s*$", text)
        assert re.search(r"(?m)^  - type:\s+\S", text)
        ids = re.findall(r"(?m)^    id:\s+([a-z][a-z0-9_]*)\s*$", text)
        assert ids
        assert len(ids) == len(set(ids))
        assert re.search(r"(?m)^      required:\s+true\s*$", text)


def test_reviewer_surfaces_preserve_scope_and_discrepancy_path() -> None:
    for relative in ("review/README.md", "docs/review.md", "wiki/Independent-Review.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "python scripts/reproduce_review.py" in text
        assert "reproduction_discrepancy.yml" in text
        assert "neural" in text.lower() and "does not" in text.lower()
    canonical = (ROOT / "review" / "README.md").read_text(encoding="utf-8")
    assert "MODEL_CARD.md" in canonical
    assert "DATA_CARD.md" in canonical
    assert "review-manifest-v1.json" in canonical
