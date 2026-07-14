"""Focused tests for the public checkpoint gate.

These tests exercise planning, git-state invalidation, receipts, and command
short-circuiting.  They never launch the project-wide suite.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_checkpoint.py"
_SPEC = importlib.util.spec_from_file_location("check_checkpoint_under_test", _SCRIPT)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - repository layout guard
    raise RuntimeError(f"cannot load {_SCRIPT}")
check_checkpoint = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = check_checkpoint
_SPEC.loader.exec_module(check_checkpoint)

PROFILES = check_checkpoint.PROFILES
build_commands = check_checkpoint.build_commands
run_checkpoint = check_checkpoint.run_checkpoint
verify_receipt = check_checkpoint.verify_receipt
worktree_fingerprint = check_checkpoint.worktree_fingerprint


def _git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0


def _git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "checkpoint@example.invalid")
    _git(tmp_path, "config", "user.name", "Checkpoint Tests")
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def test_worktree_fingerprint_tracks_content_status_and_ignores_build_like_files(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path)
    clean = worktree_fingerprint(root)

    (root / "tracked.txt").write_text("two\n", encoding="utf-8")
    unstaged = worktree_fingerprint(root)
    assert unstaged != clean

    _git(root, "add", "tracked.txt")
    staged = worktree_fingerprint(root)
    assert staged != unstaged

    (root / "untracked.txt").write_text("new\n", encoding="utf-8")
    with_untracked = worktree_fingerprint(root)
    assert with_untracked != staged

    ignored = root / "ignored"
    ignored.mkdir()
    (ignored / "state.txt").write_text("ignored-one\n", encoding="utf-8")
    before_ignored_edit = worktree_fingerprint(root)
    (ignored / "state.txt").write_text("ignored-two\n", encoding="utf-8")
    assert worktree_fingerprint(root) == before_ignored_edit


def test_worktree_fingerprint_tracks_staged_blob_when_mm_state_is_unchanged(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    tracked = root / "tracked.txt"
    tracked.write_text("staged-a\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    tracked.write_text("working\n", encoding="utf-8")
    first = worktree_fingerprint(root)

    tracked.write_text("staged-b\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    tracked.write_text("working\n", encoding="utf-8")
    second = worktree_fingerprint(root)
    assert second != first


def test_worktree_fingerprint_detects_assume_unchanged_and_skip_worktree_edits(
    tmp_path: Path,
) -> None:
    root = _git_repo(tmp_path)
    tracked = root / "tracked.txt"
    clean = worktree_fingerprint(root)

    _git(root, "update-index", "--assume-unchanged", "tracked.txt")
    try:
        tracked.write_text("hidden-assume\n", encoding="utf-8")
        assert worktree_fingerprint(root) != clean
    finally:
        _git(root, "update-index", "--no-assume-unchanged", "tracked.txt")
        tracked.write_text("one\n", encoding="utf-8")

    clean = worktree_fingerprint(root)
    _git(root, "update-index", "--skip-worktree", "tracked.txt")
    try:
        tracked.write_text("hidden-skip\n", encoding="utf-8")
        assert worktree_fingerprint(root) != clean
    finally:
        _git(root, "update-index", "--no-skip-worktree", "tracked.txt")
        tracked.write_text("one\n", encoding="utf-8")


def test_worktree_fingerprint_recurses_into_submodule_worktrees(tmp_path: Path) -> None:
    submodule = tmp_path / "submodule"
    submodule.mkdir()
    _git(submodule, "init")
    _git(submodule, "config", "user.email", "checkpoint@example.invalid")
    _git(submodule, "config", "user.name", "Checkpoint Tests")
    (submodule / "payload.txt").write_text("one\n", encoding="utf-8")
    _git(submodule, "add", "payload.txt")
    _git(submodule, "commit", "-m", "submodule initial")

    root = tmp_path / "parent"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "checkpoint@example.invalid")
    _git(root, "config", "user.name", "Checkpoint Tests")
    _git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(submodule),
        "nested",
    )
    _git(root, "commit", "-m", "add submodule")
    clean = worktree_fingerprint(root)

    nested = root / "nested"
    _git(nested, "config", "user.email", "checkpoint@example.invalid")
    _git(nested, "config", "user.name", "Checkpoint Tests")
    (nested / "payload.txt").write_text("two\n", encoding="utf-8")
    _git(nested, "add", "payload.txt")
    _git(nested, "commit", "-m", "submodule update")
    changed_commit = worktree_fingerprint(root)
    assert changed_commit != clean

    (nested / "payload.txt").write_text("dirty\n", encoding="utf-8")
    assert worktree_fingerprint(root) != changed_commit


def test_build_commands_is_ordered_and_full_is_last() -> None:
    commands = build_commands(
        "code",
        tests=("tests/first.py", "tests/second.py"),
        full=True,
        python_executable="python-test",
    )
    assert commands[0].name == "diff-check"
    assert commands[1].name == "compile-checkpoint"
    assert [command.argv[-1] for command in commands[2:4]] == [
        "tests/first.py",
        "tests/second.py",
    ]
    assert commands[-1].name == "full-suite"
    assert commands[-1].argv[-4:] == ("-n", "4", "--dist", "loadgroup")
    assert commands[0].argv == ("git", "diff", "--check", "HEAD")
    assert "scripts/check_checkpoint.py" in commands[4].argv
    assert commands[5].name == "mypy" and commands[5].argv[-1] != "src"
    assert commands[6].name == "public-api"
    assert commands[7].name == "footprint"
    assert set(PROFILES) == {"docs", "code", "public-api", "persistence"}


def test_common_gates_precede_profile_specific_gates() -> None:
    for profile in ("code", "public-api", "persistence"):
        names = [command.name for command in build_commands(profile, python_executable="python-test")]
        assert names[:3] == ["diff-check", "compile-checkpoint", "ruff"]
        assert names.index("mypy") > names.index("ruff")
        assert names.index("public-api") > names.index("mypy")
        assert names.index("footprint") > names.index("mypy")
    public_names = [command.name for command in build_commands("public-api")]
    assert public_names[-1] == "profile-public-api"
    persistence_names = [command.name for command in build_commands("persistence")]
    assert persistence_names[-1] == "profile-persistence"
    assert [command.name for command in build_commands("docs", python_executable="python-test")][-2:] == [
        "profile-docs",
        "docs-build",
    ]


def test_failing_command_short_circuits_later_gates(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    environments: list[dict[str, str]] = []

    monkeypatch.setattr(check_checkpoint, "worktree_fingerprint", lambda root: "a" * 64)

    def runner(argv, **kwargs):
        calls.append(tuple(argv))
        environments.append(kwargs["env"])
        code = 1 if len(calls) == 3 else 0
        return subprocess.CompletedProcess(argv, code, "", "failure\n" if code else "")

    receipt = tmp_path / "build" / "receipt.json"
    result = run_checkpoint(
        tmp_path,
        profile="code",
        tests=("tests/focused.py",),
        full=True,
        receipt_path=receipt,
        command_runner=runner,
    )
    assert result.status == "failed"
    assert result.exit_code == 1
    assert len(calls) == 3
    assert all(environment["PYTHONUTF8"] == "1" for environment in environments)
    assert result.commands[-1].name == "focused-test-1"
    assert receipt.exists()


def test_tree_mutation_stops_later_gates(tmp_path: Path, monkeypatch) -> None:
    fingerprints = iter(("a" * 64, "b" * 64, "b" * 64))
    monkeypatch.setattr(check_checkpoint, "worktree_fingerprint", lambda root: next(fingerprints))
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    receipt = tmp_path / "receipt.json"
    result = run_checkpoint(tmp_path, receipt_path=receipt, command_runner=runner, full=True)
    assert result.status == "mutated"
    assert result.tree_mutated is True
    assert len(calls) == 1
    assert json.loads(receipt.read_text(encoding="utf-8"))["tree_mutated"] is True


def test_receipt_verification_requires_current_fingerprint(tmp_path: Path, monkeypatch) -> None:
    fingerprint = "c" * 64
    monkeypatch.setattr(check_checkpoint, "worktree_fingerprint", lambda root: fingerprint)

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, "", "")

    receipt = tmp_path / "build" / "receipt.json"
    result = run_checkpoint(tmp_path, receipt_path=receipt, command_runner=runner)
    assert result.status == "passed"
    assert verify_receipt(receipt, tmp_path) is True

    monkeypatch.setattr(check_checkpoint, "worktree_fingerprint", lambda root: "d" * 64)
    assert verify_receipt(receipt, tmp_path) is False

    monkeypatch.setattr(check_checkpoint, "worktree_fingerprint", lambda root: fingerprint)
    result = run_checkpoint(tmp_path, receipt_path=receipt, command_runner=runner)
    assert result.status == "passed"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["commands"][0]["returncode"] = 1e999
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_receipt(receipt, tmp_path) is False

    result = run_checkpoint(tmp_path, receipt_path=receipt, command_runner=runner)
    assert result.status == "passed"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["commands"] = payload["commands"][:-1]
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_receipt(receipt, tmp_path) is False

    receipt.write_text("not-json", encoding="utf-8")
    assert verify_receipt(receipt, tmp_path) is False
