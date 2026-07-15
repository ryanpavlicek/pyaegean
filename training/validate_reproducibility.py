"""Validate A17 training locks and receipts without downloads, training, or inference."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reproducibility import (
    ContractError,
    capture_candidate_environment_lock,
    file_record,
    load_environment_lock,
    load_json_document,
    load_resolver_manifest,
    load_run_receipt,
    preflight_environment,
    promote_environment_lock,
    resolver_manifest_from_pip_report,
    verify_resolver_evidence,
    verify_receipt_files,
    write_json_document,
)

_TRAINING = Path(__file__).resolve().parent
_ROOT = _TRAINING.parent
_DEFAULT_LOCK = _TRAINING / "environment-lock.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline validation for pyaegean training reproducibility contracts."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    lock = commands.add_parser("lock", help="validate the committed environment lock")
    lock.add_argument("--lock", type=Path, default=_DEFAULT_LOCK)
    lock.add_argument("--repository-root", type=Path, default=_ROOT)

    resolver = commands.add_parser(
        "resolver-manifest",
        help="normalize a complete pip --report into content-addressed closure evidence",
    )
    resolver.add_argument("--pip-report", type=Path, required=True)
    resolver.add_argument("--output", type=Path, required=True)

    capture = commands.add_parser(
        "capture",
        help=(
            "capture installed closure, platform, and approved CUDA allocation into a "
            "preflight-ready candidate lock"
        ),
    )
    capture.add_argument("--template", type=Path, default=_DEFAULT_LOCK)
    capture.add_argument("--resolver-manifest", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--repository-root", type=Path, default=_ROOT)

    preflight = commands.add_parser(
        "preflight",
        help="compare this clean machine with the exact lock; never downloads or runs a model",
    )
    preflight.add_argument("--lock", type=Path, default=_DEFAULT_LOCK)
    preflight.add_argument("--repository-root", type=Path, default=_ROOT)
    preflight.add_argument("--output", type=Path)
    preflight.add_argument(
        "--expected-commit",
        help="require the clean checkout to match this exact 40-character candidate commit",
    )
    preflight.add_argument(
        "--skip-accelerator",
        action="store_true",
        help="skip CUDA/driver/cuDNN inspection (the report cannot pass an accelerator lock)",
    )

    promote = commands.add_parser(
        "promote",
        help="bind a successful preflight receipt and promote a captured candidate",
    )
    promote.add_argument("--lock", type=Path, required=True)
    promote.add_argument("--preflight", type=Path, required=True)
    promote.add_argument("--output", type=Path, required=True)
    promote.add_argument("--repository-root", type=Path, default=_ROOT)
    promote.add_argument(
        "--expected-commit",
        required=True,
        help="re-run live preflight at this exact candidate commit before promotion",
    )

    receipt = commands.add_parser("receipt", help="validate a completed run receipt and files")
    receipt.add_argument("receipt", type=Path)
    receipt.add_argument("--lock", type=Path, default=_DEFAULT_LOCK)
    receipt.add_argument("--repository-root", type=Path, default=_ROOT)
    receipt.add_argument(
        "--structure-only",
        action="store_true",
        help="validate schema/digests but do not re-hash referenced files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "resolver-manifest":
            manifest = resolver_manifest_from_pip_report(load_json_document(args.pip_report))
            write_json_document(args.output, manifest)
            result = {
                "ok": True,
                "output": args.output.as_posix(),
                "manifest_sha256": manifest["manifest_sha256"],
            }
        elif args.command == "capture":
            template = load_environment_lock(args.template)
            manifest = load_resolver_manifest(args.resolver_manifest)
            evidence_file = file_record(args.resolver_manifest, root=args.repository_root)
            lock = capture_candidate_environment_lock(
                template,
                resolver_manifest=manifest,
                resolver_file=evidence_file,
            )
            write_json_document(args.output, lock)
            result = {
                "ok": True,
                "output": args.output.as_posix(),
                "environment_definition_sha256": lock["environment_definition_sha256"],
                "lock_sha256": lock["lock_sha256"],
                "state": lock["verification"]["state"],
            }
        elif args.command == "promote":
            candidate = load_environment_lock(args.lock)
            report = load_json_document(args.preflight)
            live_report = preflight_environment(
                candidate,
                repository_root=args.repository_root,
                expected_repository_commit=args.expected_commit,
            )
            if live_report != report:
                raise ContractError(
                    "saved preflight differs from a fresh live observation; refusing promotion"
                )
            lock = promote_environment_lock(candidate, report)
            write_json_document(args.output, lock)
            result = {
                "ok": True,
                "output": args.output.as_posix(),
                "environment_definition_sha256": lock["environment_definition_sha256"],
                "lock_sha256": lock["lock_sha256"],
                "state": lock["verification"]["state"],
            }
        else:
            lock = load_environment_lock(args.lock)
            if args.command == "lock":
                if lock["dependencies"]["scope"] == "training-dependency-closure":
                    verify_resolver_evidence(lock, root=args.repository_root)
                result = {
                    "ok": True,
                    "lock": args.lock.as_posix(),
                    "lock_sha256": lock["lock_sha256"],
                    "environment_definition_sha256": lock["environment_definition_sha256"],
                    "verification": lock["verification"],
                    "dependency_scope": lock["dependencies"]["scope"],
                    "dependency_inventory_complete": lock["dependencies"]["complete"],
                    "ready_for_training": (
                        lock["verification"]["state"] == "validated"
                        and lock["dependencies"]["scope"]
                        in {"training-dependency-closure", "full-environment"}
                        and lock["dependencies"]["complete"]
                    ),
                }
            elif args.command == "preflight":
                result = preflight_environment(
                    lock,
                    repository_root=args.repository_root,
                    check_accelerator=not args.skip_accelerator,
                    expected_repository_commit=args.expected_commit,
                )
                if args.output is not None:
                    write_json_document(args.output, result)
            else:
                if lock["dependencies"]["scope"] == "training-dependency-closure":
                    verify_resolver_evidence(lock, root=args.repository_root)
                receipt = load_run_receipt(args.receipt, environment_lock=lock)
                if not args.structure_only:
                    verify_receipt_files(receipt, root=args.repository_root)
                result = {
                    "ok": True,
                    "receipt": args.receipt.as_posix(),
                    "receipt_sha256": receipt["receipt_sha256"],
                    "files_verified": not args.structure_only,
                }
    except ContractError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
