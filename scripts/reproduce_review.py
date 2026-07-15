"""Verify the public independent-review kit without network or model execution.

Run from a pyaegean source checkout::

    python scripts/reproduce_review.py

The verifier reads only repository files, imports the zero-dependency package source,
scores the project-authored offline fixture, and compares one ordinary baseline-pipeline
journey with reviewed expected output. It never downloads data, opens a model, or writes a
cache. The optional Git probe is read-only and reports the exact commit and worktree state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import socket
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

FORMAT = "pyaegean-independent-review/1"
EXPECTED_FORMAT = "pyaegean-independent-review-expected/1"
REPORT_FORMAT = "pyaegean-independent-review-report/1"
MANIFEST_PATH = "review/review-manifest-v1.json"
MAX_JSON_BYTES = 1024 * 1024
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 128
MAX_TEXT = 512

_MANIFEST_FIELDS = {
    "expected_results_path",
    "format",
    "package_version",
    "records",
    "review_command",
}
_RECORD_FIELDS = {"hash_mode", "path", "provenance", "role", "sha256"}
_HASH_MODES = {"bytes", "text-lf"}
_ROLES = {
    "benchmark-fixture",
    "claims-registry",
    "expected-results",
    "model-evidence",
    "review-document",
    "runtime-contract",
    "training-environment",
}
_PROVENANCE = {
    "mixed-public-evidence",
    "project-apache-2.0",
    "third-party-license-metadata",
}
_REQUIRED_ROLES = {
    "benchmark-fixture",
    "claims-registry",
    "expected-results",
    "model-evidence",
    "review-document",
    "runtime-contract",
    "training-environment",
}
_EXPECTED_STAGES = {
    "accent",
    "betacode",
    "lemma",
    "morphology",
    "pos",
    "scansion",
    "syllabify",
    "tokenize",
}
_PIPELINE_RECORD_FIELDS = {
    "index",
    "lemma",
    "lemma_source",
    "review_recommended",
    "sentence",
    "text",
    "upos",
}


class ReviewVerificationError(ValueError):
    """Raised when the reviewer contract or its checked result is invalid."""


def canonical_json(value: Any) -> str:
    """Return the exact canonical JSON representation used for reviewer digests."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path, hash_mode: str) -> str:
    if hash_mode == "text-lf":
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        return _sha256_bytes(canonical)
    if hash_mode != "bytes":  # defensive; manifest validation rejects this first
        raise ReviewVerificationError(f"unknown record hash mode {hash_mode!r}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewVerificationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ReviewVerificationError(f"non-finite JSON value {value!r} is not allowed")


def _load_canonical_json(path: Path, *, maximum_bytes: int, where: str) -> tuple[dict[str, Any], bytes]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ReviewVerificationError(f"cannot inspect {where}: {exc}") from exc
    if not 2 <= size <= maximum_bytes:
        raise ReviewVerificationError(
            f"{where} size {size} is outside 2..{maximum_bytes} bytes"
        )
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewVerificationError(f"invalid {where}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewVerificationError(f"{where} must be a JSON object")
    expected = canonical_json(value).encode("utf-8") + b"\n"
    if raw != expected:
        raise ReviewVerificationError(f"{where} must use canonical UTF-8 JSON plus one LF")
    return value, raw


def _exact_fields(value: Mapping[str, Any], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ReviewVerificationError(
            f"{where} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _text(value: Any, *, where: str, maximum: int = MAX_TEXT) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ReviewVerificationError(
            f"{where} must be a non-empty trimmed string of at most {maximum} characters"
        )
    return value


def _sha256(value: Any, *, where: str) -> str:
    text = _text(value, where=where, maximum=64)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ReviewVerificationError(f"{where} must be a lowercase SHA-256 string")
    return text


def _relative_path(value: Any, *, where: str) -> str:
    text = _text(value, where=where, maximum=240)
    if "\\" in text:
        raise ReviewVerificationError(f"{where} must use forward slashes")
    pure = PurePosixPath(text)
    if (
        pure.is_absolute()
        or text != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ReviewVerificationError(f"{where} must be a normalized repository-relative path")
    return pure.as_posix()


def _checked_path(root: Path, relative: str, *, where: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ReviewVerificationError(f"{where} must not traverse a symlink: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ReviewVerificationError(f"{where} is missing or leaves the repository: {relative}") from exc
    if not resolved.is_file():
        raise ReviewVerificationError(f"{where} is not a regular file: {relative}")
    return resolved


def load_manifest(root: Path, path: Path | None = None) -> tuple[dict[str, Any], bytes]:
    """Load and validate the exact bounded reviewer manifest."""

    root = root.resolve(strict=True)
    manifest_path = path or root.joinpath(*PurePosixPath(MANIFEST_PATH).parts)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    try:
        manifest_relative = manifest_path.absolute().relative_to(root).as_posix()
    except ValueError as exc:
        raise ReviewVerificationError("review manifest path leaves the repository") from exc
    manifest_path = _checked_path(root, manifest_relative, where="review manifest path")
    value, raw = _load_canonical_json(
        manifest_path,
        maximum_bytes=MAX_JSON_BYTES,
        where="review manifest",
    )
    _exact_fields(value, _MANIFEST_FIELDS, where="review manifest")
    if value["format"] != FORMAT:
        raise ReviewVerificationError(f"unknown review manifest format {value['format']!r}")
    version = _text(value["package_version"], where="review manifest package_version", maximum=32)
    if not all(part.isdigit() for part in version.split(".")) or len(version.split(".")) != 3:
        raise ReviewVerificationError("review manifest package_version must be X.Y.Z")
    if value["review_command"] != "python scripts/reproduce_review.py":
        raise ReviewVerificationError("review manifest command is not the stable one-command entry point")
    expected_path = _relative_path(
        value["expected_results_path"],
        where="review manifest expected_results_path",
    )
    raw_records = value["records"]
    if not isinstance(raw_records, list) or not 1 <= len(raw_records) <= MAX_RECORDS:
        raise ReviewVerificationError(
            f"review manifest records must contain 1..{MAX_RECORDS} entries"
        )
    paths: list[str] = []
    roles: set[str] = set()
    for index, record in enumerate(raw_records):
        where = f"review manifest records[{index}]"
        if not isinstance(record, dict):
            raise ReviewVerificationError(f"{where} must be an object")
        _exact_fields(record, _RECORD_FIELDS, where=where)
        relative = _relative_path(record["path"], where=f"{where}.path")
        role = _text(record["role"], where=f"{where}.role", maximum=64)
        provenance = _text(
            record["provenance"], where=f"{where}.provenance", maximum=64
        )
        hash_mode = _text(record["hash_mode"], where=f"{where}.hash_mode", maximum=32)
        _sha256(record["sha256"], where=f"{where}.sha256")
        if role not in _ROLES:
            raise ReviewVerificationError(f"{where}.role is unknown: {role!r}")
        if provenance not in _PROVENANCE:
            raise ReviewVerificationError(
                f"{where}.provenance is unknown: {provenance!r}"
            )
        if hash_mode not in _HASH_MODES:
            raise ReviewVerificationError(f"{where}.hash_mode is unknown: {hash_mode!r}")
        paths.append(relative)
        roles.add(role)
    if (
        paths != sorted(paths)
        or len(paths) != len(set(paths))
        or len(paths) != len({item.casefold() for item in paths})
    ):
        raise ReviewVerificationError("review manifest record paths must be unique and sorted")
    if not _REQUIRED_ROLES <= roles:
        raise ReviewVerificationError(
            f"review manifest lacks roles {sorted(_REQUIRED_ROLES - roles)}"
        )
    expected_matches = [
        record
        for record in raw_records
        if record["path"] == expected_path and record["role"] == "expected-results"
    ]
    if len(expected_matches) != 1:
        raise ReviewVerificationError(
            "expected_results_path must identify exactly one expected-results record"
        )
    return value, raw


def _validate_expected(value: Mapping[str, Any]) -> None:
    _exact_fields(value, {"benchmark", "format", "pipeline"}, where="expected results")
    if value["format"] != EXPECTED_FORMAT:
        raise ReviewVerificationError(f"unknown expected-results format {value['format']!r}")
    benchmark = value["benchmark"]
    if not isinstance(benchmark, dict) or set(benchmark) != _EXPECTED_STAGES:
        raise ReviewVerificationError("expected benchmark stages differ from the reviewed set")
    for stage, score in benchmark.items():
        if not isinstance(score, dict):
            raise ReviewVerificationError(f"expected benchmark {stage} must be an object")
        _exact_fields(score, {"correct", "total"}, where=f"expected benchmark {stage}")
        correct = score["correct"]
        total = score["total"]
        if (
            isinstance(correct, bool)
            or isinstance(total, bool)
            or not isinstance(correct, int)
            or not isinstance(total, int)
            or total < 1
            or not 0 <= correct <= total
        ):
            raise ReviewVerificationError(f"expected benchmark {stage} has invalid counts")
    pipeline = value["pipeline"]
    if not isinstance(pipeline, dict):
        raise ReviewVerificationError("expected pipeline must be an object")
    _exact_fields(pipeline, {"document_id", "input", "records"}, where="expected pipeline")
    _text(pipeline["input"], where="expected pipeline input", maximum=4096)
    _text(pipeline["document_id"], where="expected pipeline document_id", maximum=128)
    records = pipeline["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= 256:
        raise ReviewVerificationError("expected pipeline records must contain 1..256 entries")
    for index, record in enumerate(records):
        where = f"expected pipeline records[{index}]"
        if not isinstance(record, dict):
            raise ReviewVerificationError(f"{where} must be an object")
        _exact_fields(record, _PIPELINE_RECORD_FIELDS, where=where)
        if (
            isinstance(record["sentence"], bool)
            or isinstance(record["index"], bool)
            or not isinstance(record["sentence"], int)
            or not isinstance(record["index"], int)
            or record["sentence"] < 0
            or record["index"] < 1
            or not isinstance(record["review_recommended"], bool)
        ):
            raise ReviewVerificationError(f"{where} has invalid numeric/boolean fields")
        for field in ("text", "upos", "lemma", "lemma_source"):
            _text(record[field], where=f"{where}.{field}", maximum=256)


@contextmanager
def _network_forbidden() -> Iterator[None]:
    original_socket = socket.socket
    original_create_connection = socket.create_connection

    def blocked(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise ReviewVerificationError("review workflow attempted network access")

    class BlockedSocket(original_socket):
        def connect(self, *args: Any, **kwargs: Any) -> Any:
            return blocked(*args, **kwargs)

        def connect_ex(self, *args: Any, **kwargs: Any) -> Any:
            return blocked(*args, **kwargs)

        def bind(self, *args: Any, **kwargs: Any) -> Any:
            return blocked(*args, **kwargs)

        def sendto(self, *args: Any, **kwargs: Any) -> Any:
            return blocked(*args, **kwargs)

        def sendmsg(self, *args: Any, **kwargs: Any) -> Any:
            return blocked(*args, **kwargs)

    socket.socket = BlockedSocket
    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


def _package_results(
    root: Path,
    expected: Mapping[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    source_root = (root / "src").resolve(strict=True)
    sys.path.insert(0, str(source_root))
    try:
        with _network_forbidden():
            import aegean
            from aegean.greek import GreekPipeline, benchmark

            origin = Path(aegean.__file__).resolve(strict=True)
            package_version = str(aegean.__version__)
            try:
                origin.relative_to(source_root)
            except ValueError as exc:
                raise ReviewVerificationError(
                    f"review imported pyaegean outside the checkout: {origin}"
                ) from exc
            scores = benchmark.run_benchmark()
            benchmark_result = {
                stage: {"correct": score.correct, "total": score.total}
                for stage, score in sorted(scores.items())
            }
            expected_pipeline = expected["pipeline"]
            records = GreekPipeline().analyze(
                expected_pipeline["input"],
                document_id=expected_pipeline["document_id"],
            )
            pipeline_result = [
                {
                    "index": record.index,
                    "lemma": record.lemma,
                    "lemma_source": record.lemma_source.value,
                    "review_recommended": record.review_recommended,
                    "sentence": record.sentence,
                    "text": record.text,
                    "upos": record.upos,
                }
                for record in records
            ]
    finally:
        if sys.path and sys.path[0] == str(source_root):
            sys.path.pop(0)
    actual = {"benchmark": benchmark_result, "pipeline": pipeline_result}
    wanted = {
        "benchmark": expected["benchmark"],
        "pipeline": expected["pipeline"]["records"],
    }
    if actual != wanted:
        raise ReviewVerificationError("offline representative result differs from reviewed expectation")
    return package_version, str(origin), actual


def _git_state(root: Path) -> dict[str, Any]:
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "clean": None, "head": None, "reason": type(exc).__name__}
    if len(head) != 40 or any(char not in "0123456789abcdef" for char in head):
        return {"available": False, "clean": None, "head": None, "reason": "invalid-git-head"}
    return {"available": True, "clean": not bool(status), "head": head, "reason": None}


def verify_review(root: Path, *, require_clean: bool = True) -> dict[str, Any]:
    """Verify the reviewer manifest and offline result, returning a JSON-compatible report."""

    root = root.resolve(strict=True)
    manifest, manifest_raw = load_manifest(root)
    checks: list[dict[str, Any]] = []
    expected_value: dict[str, Any] | None = None
    for index, record in enumerate(manifest["records"]):
        relative = record["path"]
        path = _checked_path(root, relative, where=f"review manifest records[{index}].path")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ReviewVerificationError(
                f"cannot inspect reviewed record {relative}: {exc}"
            ) from exc
        if not 1 <= size <= MAX_RECORD_BYTES:
            raise ReviewVerificationError(
                f"reviewed record {relative} size {size} is outside 1..{MAX_RECORD_BYTES} bytes"
            )
        try:
            digest = _sha256_file(path, record["hash_mode"])
        except (OSError, UnicodeError) as exc:
            raise ReviewVerificationError(
                f"cannot hash reviewed record {relative}: {exc}"
            ) from exc
        if digest != record["sha256"]:
            raise ReviewVerificationError(
                f"reviewed record SHA-256 mismatch for {relative}: {digest} != {record['sha256']}"
            )
        checks.append(
            {
                "hash_mode": record["hash_mode"],
                "path": relative,
                "provenance": record["provenance"],
                "role": record["role"],
                "sha256": digest,
            }
        )
        if relative == manifest["expected_results_path"]:
            expected_value, _ = _load_canonical_json(
                path,
                maximum_bytes=MAX_JSON_BYTES,
                where="expected results",
            )
    if expected_value is None:
        raise ReviewVerificationError("review manifest did not load expected results")
    _validate_expected(expected_value)
    try:
        package_version, package_origin, deterministic = _package_results(root, expected_value)
    except ReviewVerificationError:
        raise
    except Exception as exc:
        raise ReviewVerificationError(
            f"offline representative execution failed: {type(exc).__name__}: {exc}"
        ) from exc
    if manifest["package_version"] != package_version:
        raise ReviewVerificationError(
            "review manifest package_version differs from the checked-out package"
        )
    git = _git_state(root)
    if require_clean and git["available"] and not git["clean"]:
        raise ReviewVerificationError(
            "Git worktree is not clean; commit/stash changes or use --allow-dirty for diagnosis"
        )
    deterministic_sha256 = _sha256_bytes(canonical_json(deterministic).encode("utf-8"))
    report = {
        "checks": checks,
        "deterministic_result": {
            "benchmark": deterministic["benchmark"],
            "pipeline": deterministic["pipeline"],
            "sha256": deterministic_sha256,
        },
        "environment": {
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "format": REPORT_FORMAT,
        "manifest": {
            "path": MANIFEST_PATH,
            "record_count": len(checks),
            "sha256": _sha256_bytes(manifest_raw),
        },
        "ok": True,
        "package": {
            "origin": package_origin,
            "version": package_version,
        },
        "repository": git,
    }
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify pyaegean's public evidence hashes and deterministic offline reviewer fixture "
            "without network or model execution."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the complete canonical JSON report",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="report but do not reject an otherwise valid dirty Git worktree",
    )
    return parser


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def main(argv: Sequence[str] | None = None) -> int:
    _configure_utf8_output()
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    try:
        report = verify_review(root, require_clean=not args.allow_dirty)
    except ReviewVerificationError as exc:
        if args.json:
            print(canonical_json({"error": str(exc), "format": REPORT_FORMAT, "ok": False}))
        else:
            print(f"review verification failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(canonical_json(report))
    else:
        git = report["repository"]
        git_summary = git["head"] if git["available"] else "unavailable (source archive)"
        print("pyaegean independent-review verification: PASS")
        print(f"package: {report['package']['version']} from {report['package']['origin']}")
        print(f"repository: {git_summary}")
        print(
            f"records: {report['manifest']['record_count']} "
            f"(manifest {report['manifest']['sha256']})"
        )
        print(f"deterministic result: {report['deterministic_result']['sha256']}")
        print("network/model/cache writes: not used")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
