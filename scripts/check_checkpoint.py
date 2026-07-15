#!/usr/bin/env python3
"""Run a cheap, risk-profiled checkpoint before an expensive project gate.

The checkpoint is deliberately repository-only and uses only the standard
library.  It fingerprints the public worktree before commands start, aborts on
the first failing command (or a worktree mutation), and writes a small JSON
receipt under ``build/``.  The default location is ignored by this repository's
``.gitignore``.

Examples::

    python scripts/check_checkpoint.py --profile code --test tests/test_fix.py
    python scripts/check_checkpoint.py --profile persistence --full
    python scripts/check_checkpoint.py --verify-receipt

``--full`` is intentionally the final command in a plan and runs the Windows-
safe equivalent of ``pytest -n 4 --dist loadgroup`` through the active Python.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = Path("build") / "checkpoint-receipt.json"
DEFAULT_FULL_LOG = Path("build") / "checkpoint-full-suite.log"
PROFILES = ("docs", "code", "public-api", "persistence")
_SCHEMA = 1


@dataclass(frozen=True)
class CommandSpec:
    """One command in the ordered checkpoint plan."""

    name: str
    argv: tuple[str, ...]

    def as_json(self) -> dict[str, object]:
        return {"name": self.name, "argv": list(self.argv)}


@dataclass(frozen=True)
class CommandResult:
    """Outcome of one command execution."""

    name: str
    argv: tuple[str, ...]
    returncode: int
    duration_ms: int
    output: str = ""

    def as_json(self) -> dict[str, object]:
        # Keep receipts small.  Full output belongs in the optional suite log.
        return {
            "name": self.name,
            "argv": list(self.argv),
            "returncode": self.returncode,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class CheckpointResult:
    """Structured result returned by :func:`run_checkpoint`."""

    status: str
    exit_code: int
    receipt_path: Path
    fingerprint_start: str
    fingerprint_end: str
    tree_mutated: bool
    commands: tuple[CommandResult, ...]


def _utf8_env() -> dict[str, str]:
    """Return a subprocess environment with deterministic UTF-8 output."""

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return env


def _configure_utf8_stream(stream: object) -> None:
    """Make a reconfigurable text stream accept checkpoint Unicode output."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def _configure_console_encoding() -> None:
    """Keep captured Unicode command output printable on legacy Windows shells."""

    _configure_utf8_stream(sys.stdout)
    _configure_utf8_stream(sys.stderr)


def _run_git(root: Path, *args: str) -> bytes:
    """Run git without a shell and return bytes, preserving unusual filenames."""

    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=_utf8_env(),
    )
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail or proc.returncode}")
    return proc.stdout


def _head(root: Path) -> bytes:
    """Return HEAD, using an explicit marker for an unborn repository."""

    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=_utf8_env(),
    )
    if proc.returncode == 0:
        return proc.stdout.strip()
    # A repository with no commit still has a meaningful, stable state.
    probe = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=_utf8_env(),
    )
    if probe.returncode:
        detail = probe.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"not a git worktree: {detail or probe.returncode}")
    return b"<unborn>"


def _status_entries(raw: bytes) -> list[tuple[str, bytes]]:
    """Parse porcelain-v1 ``-z`` output into ``(status, path)`` entries.

    Rename and copy records contain two NUL-delimited paths.  Both paths are
    retained so replacing a file with a rename cannot evade invalidation.
    """

    parts = raw.split(b"\0")
    entries: list[tuple[str, bytes]] = []
    index = 0
    while index < len(parts):
        record = parts[index]
        index += 1
        if not record:
            continue
        if len(record) < 3:
            # Git should never emit this, but hash malformed output instead of
            # silently ignoring it.
            entries.append(("??", record))
            continue
        status = record[:2].decode("ascii", "replace")
        path = record[3:]
        entries.append((status, path))
        if status[0] in "RC" or status[1] in "RC":
            if index < len(parts) and parts[index]:
                entries.append((status, parts[index]))
                index += 1
    return entries


def _path_for(root: Path, git_path: bytes) -> Path:
    # Git's -z format uses slash separators even on Windows.  ``os.fsdecode``
    # keeps undecodable bytes lossless via surrogateescape on POSIX.
    text = os.fsdecode(git_path)
    return root.joinpath(*text.replace("\\", "/").split("/"))


def _contents(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return b"<deleted>"
    except OSError as exc:
        return f"<unreadable:{type(exc).__name__}>".encode("ascii")


def _gitlink_paths(index: bytes) -> set[bytes]:
    """Return tracked paths whose index mode is a submodule gitlink."""

    paths: set[bytes] = set()
    for record in index.split(b"\0"):
        if not record or b"\t" not in record:
            continue
        header, path = record.split(b"\t", 1)
        if header.split(b" ", 1)[0] == b"160000":
            paths.add(path)
    return paths


def _tracked_contents(root: Path, git_path: bytes, gitlinks: set[bytes]) -> bytes:
    """Read a tracked path, recursing into initialized submodule worktrees."""

    path = _path_for(root, git_path)
    if git_path in gitlinks and path.is_dir() and (path / ".git").exists():
        return b"<git-worktree>" + worktree_fingerprint(path).encode("ascii")
    return _contents(path)


def _put(hasher: "hashlib._Hash", value: bytes) -> None:
    hasher.update(len(value).to_bytes(8, "big"))
    hasher.update(value)


def worktree_fingerprint(root: Path = ROOT) -> str:
    """Return a stable SHA-256 fingerprint of the public worktree state.

    The hash includes the current ``HEAD`` and raw staged index entries (blob
    ids and modes), plus every tracked path's working-tree bytes and every
    tracked modified/deleted or untracked non-ignored status entry.  Each
    status entry includes its porcelain kind (which distinguishes staged from
    unstaged work), path, and working-tree bytes.  Ignored files, including
    ``build/``, are intentionally omitted.
    """

    root = Path(root).resolve()
    head = _head(root)
    index = _run_git(root, "ls-files", "--stage", "-z")
    tracked = _run_git(root, "ls-files", "-z")
    gitlinks = _gitlink_paths(index)
    status = _run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = sorted(set(_status_entries(status)), key=lambda item: (item[0], item[1]))
    tracked_paths = sorted(set(path for path in tracked.split(b"\0") if path))

    hasher = hashlib.sha256()
    _put(hasher, b"pyaegean-public-worktree-v1")
    _put(hasher, head)
    _put(hasher, index)
    # Porcelain can intentionally hide edits when assume-unchanged or
    # skip-worktree is set.  Read every tracked working-tree path directly so
    # those flags cannot make a mutation invisible to the gate.
    _put(hasher, b"tracked-working-tree-v1")
    for git_path in tracked_paths:
        _put(hasher, git_path)
        _put(hasher, _tracked_contents(root, git_path, gitlinks))
    for kind, git_path in entries:
        _put(hasher, kind.encode("ascii", "replace"))
        _put(hasher, git_path)
        _put(hasher, _contents(_path_for(root, git_path)))
    return hasher.hexdigest()


def _python(python_executable: str | None) -> str:
    return python_executable or sys.executable


def _pytest(name: str, paths: Sequence[str], python_executable: str) -> CommandSpec:
    return CommandSpec(
        name,
        (python_executable, "-m", "pytest", "-q", "--disable-warnings", *paths),
    )


def build_commands(
    profile: str = "code",
    tests: Iterable[str] = (),
    full: bool = False,
    *,
    python_executable: str | None = None,
) -> list[CommandSpec]:
    """Build an ordered cheap-to-expensive plan for ``profile``.

    ``tests`` is an iterable because the CLI's ``--test`` option is repeatable;
    each requested path becomes its own command, preserving the user's order so
    a failing focused test prevents later checks from running.
    """

    if profile not in PROFILES:
        raise ValueError(f"unknown risk profile {profile!r}; choose one of {', '.join(PROFILES)}")
    py = _python(python_executable)
    plan = [CommandSpec("diff-check", ("git", "diff", "--check", "HEAD"))]
    plan.append(CommandSpec("compile-checkpoint", (py, "-m", "compileall", "-q", "scripts/check_checkpoint.py")))
    for number, test_path in enumerate(tests, 1):
        plan.append(_pytest(f"focused-test-{number}", (str(test_path),), py))

    profile_tests: dict[str, tuple[str, ...]] = {
        "docs": (
            "tests/test_docs_staleness.py",
            "tests/test_wiki_integrity.py",
            "tests/test_cli_ux_docs.py",
            "tests/test_mcp_docs.py",
            "tests/test_surface_parity.py",
            "tests/test_benchmark_claims.py",
            "tests/test_corpus_facts.py",
        ),
        "code": (),
        "public-api": ("tests/test_check_api.py", "tests/test_surface_parity.py"),
        "persistence": (
            "tests/test_cache.py",
            "tests/test_corpus_framework.py",
            "tests/test_db.py",
            "tests/test_db_append.py",
        ),
    }
    if profile == "docs":
        if profile_tests[profile]:
            plan.append(_pytest(f"profile-{profile}", profile_tests[profile], py))
        plan.append(
            CommandSpec(
                "docs-build",
                (py, "-m", "mkdocs", "build", "--strict", "--site-dir", "build/checkpoint-site"),
            )
        )
    else:
        plan.extend(
            [
                CommandSpec(
                    "ruff",
                    (
                        py,
                        "-m",
                        "ruff",
                        "check",
                        "src",
                        "tests",
                        "scripts/check_checkpoint.py",
                        "training/reproducibility.py",
                        "training/validate_reproducibility.py",
                        "training/artifact_command.py",
                        "training/artifact_qualification.py",
                        "training/artifact_runtime.py",
                        "training/export_onnx.py",
                        "training/quantize_grc_joint.py",
                        "training/run_development_evaluation.py",
                        "training/runtime_variant_award.py",
                        "training/tests",
                    ),
                ),
                CommandSpec("mypy", (py, "-m", "mypy")),
                CommandSpec("public-api", (py, "scripts/check_api.py")),
                CommandSpec("footprint", (py, "scripts/check_footprint.py")),
            ]
        )
        if profile in ("public-api", "persistence"):
            plan.append(_pytest(f"profile-{profile}", profile_tests[profile], py))

    if full:
        plan.append(CommandSpec("full-suite", (py, "-m", "pytest", "-n", "4", "--dist", "loadgroup")))
    return plan


def _decode_output(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value or "")


def _receipt_path(root: Path, path: Path | str | None) -> Path:
    if path is None or str(path) == "":
        return root / DEFAULT_RECEIPT
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def run_checkpoint(
    root: Path = ROOT,
    profile: str = "code",
    tests: Iterable[str] = (),
    full: bool = False,
    *,
    receipt_path: Path | str | None = None,
    full_log_path: Path | str | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> CheckpointResult:
    """Execute a checkpoint plan, write its receipt, and return its result."""

    root = Path(root).resolve()
    receipt = _receipt_path(root, receipt_path)
    log = _receipt_path(root, full_log_path or DEFAULT_FULL_LOG)
    test_paths = tuple(str(item) for item in tests)
    commands = build_commands(profile, test_paths, full)
    start = worktree_fingerprint(root)
    results: list[CommandResult] = []
    tree_mutated = False
    runner = command_runner or subprocess.run

    for command in commands:
        started = time.monotonic()
        try:
            completed = runner(
                list(command.argv),
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                env=_utf8_env(),
            )
            returncode = int(getattr(completed, "returncode", 1))
            output = _decode_output(getattr(completed, "stdout", "")) + _decode_output(
                getattr(completed, "stderr", "")
            )
        except OSError as exc:
            returncode = 127
            output = f"{type(exc).__name__}: {exc}\n"
        duration_ms = int((time.monotonic() - started) * 1000)
        result = CommandResult(command.name, command.argv, returncode, duration_ms, output)
        results.append(result)
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        print(f"[{('OK' if returncode == 0 else 'FAIL')}] {command.name}")

        if command.name == "full-suite":
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(output, encoding="utf-8")
        changed = worktree_fingerprint(root) != start
        if changed:
            tree_mutated = True
            print("[FAIL] public worktree changed during the checkpoint; later gates were skipped")
        if returncode != 0 or changed:
            break

    end = worktree_fingerprint(root)
    failed = any(item.returncode != 0 for item in results)
    status = "mutated" if tree_mutated else "failed" if failed else "passed"
    payload: dict[str, object] = {
        "schema": _SCHEMA,
        "status": status,
        "profile": profile,
        "tests": list(test_paths),
        "full": full,
        "fingerprint": end,
        "fingerprint_start": start,
        "fingerprint_end": end,
        "tree_mutated": tree_mutated,
        "commands": [item.as_json() for item in results],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_receipt(receipt, payload)
    exit_code = 0 if status == "passed" else 1
    return CheckpointResult(status, exit_code, receipt, start, end, tree_mutated, tuple(results))


def verify_receipt(receipt_path: Path | str | None = None, root: Path = ROOT) -> bool:
    """Return whether a successful receipt still matches the current worktree."""

    root = Path(root).resolve()
    path = _receipt_path(root, receipt_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False
        if type(payload.get("schema")) is not int or payload["schema"] != _SCHEMA:
            return False
        if payload.get("status") != "passed":
            return False
        if payload.get("tree_mutated") is not False:
            return False
        profile = payload.get("profile")
        if not isinstance(profile, str) or profile not in PROFILES:
            return False
        recorded_tests = payload.get("tests")
        if not isinstance(recorded_tests, list) or any(
            not isinstance(item, str) for item in recorded_tests
        ):
            return False
        full = payload.get("full")
        if type(full) is not bool:
            return False
        expected = payload.get("fingerprint")
        if not isinstance(expected, str) or len(expected) != 64:
            return False
        if any(character not in "0123456789abcdef" for character in expected):
            return False
        if payload.get("fingerprint_start") != expected or payload.get("fingerprint_end") != expected:
            return False
        commands = payload.get("commands")
        if not isinstance(commands, list) or not commands:
            return False
        plan = build_commands(profile, tuple(recorded_tests), full)
        if len(commands) != len(plan):
            return False
        recorded_specs: list[tuple[str, tuple[str, ...]]] = []
        for item in commands:
            if not isinstance(item, dict):
                return False
            returncode = item.get("returncode")
            name = item.get("name")
            argv = item.get("argv")
            if type(returncode) is not int or returncode != 0:
                return False
            if not isinstance(name, str) or not isinstance(argv, list):
                return False
            if any(not isinstance(argument, str) for argument in argv):
                return False
            recorded_specs.append((name, tuple(argv)))
        expected_specs = [(item.name, item.argv) for item in plan]
        if recorded_specs != expected_specs:
            return False
        return worktree_fingerprint(root) == expected
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def _print_plan(commands: Sequence[CommandSpec]) -> None:
    for command in commands:
        print(f"- {command.name}: {subprocess.list2cmdline(list(command.argv))}")


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console_encoding()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=PROFILES, default="code", help="risk profile to run")
    parser.add_argument("--test", dest="tests", action="append", metavar="PATH", help="focused pytest path; repeatable")
    parser.add_argument("--full", action="store_true", help="run the final parallel full suite")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without executing commands")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verify-receipt", nargs="?", const="", metavar="PATH", help="verify a receipt (default: build/checkpoint-receipt.json)")
    args = parser.parse_args(argv)

    if args.verify_receipt is not None:
        if args.profile != "code" or args.tests or args.full or args.dry_run:
            parser.error("--verify-receipt cannot be combined with a run option")
        ok = verify_receipt(args.verify_receipt or None)
        print("receipt valid" if ok else "receipt invalid")
        return 0 if ok else 1

    tests = tuple(args.tests or ())
    commands = build_commands(args.profile, tests, args.full)
    if args.dry_run:
        print(f"profile: {args.profile}")
        print(f"fingerprint: {worktree_fingerprint(ROOT)}")
        _print_plan(commands)
        return 0
    result = run_checkpoint(ROOT, args.profile, tests, args.full)
    print(f"checkpoint {result.status}; receipt: {result.receipt_path}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
