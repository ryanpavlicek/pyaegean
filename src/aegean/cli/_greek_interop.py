"""CoNLL-U inspection/export, lossless interoperability bundles, and annotation profiles
for ``aegean greek``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

if TYPE_CHECKING:
    from aegean.greek.ud import UDDocument, UDRow

from ._common import (
    JSON_OPT,
    RESULT_OPT,
    emit_json,
    emit_result,
    fail,
    table,
    to_plain,
)

conllu_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Inspect and losslessly export CoNLL-U gold files (no model inference).",
    no_args_is_help=True,
)

interop_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Move lossless Greek annotations through CoNLL-U, spaCy, Stanza, or CLTK bundles.",
    no_args_is_help=True,
)

annotation_profiles_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Inspect immutable annotation and domain profiles (no model inference).",
    no_args_is_help=True,
)


def register(greek_app: typer.Typer) -> None:
    """Attach the conllu, interop, and annotation-profiles subgroups to ``greek_app``."""
    greek_app.add_typer(conllu_app, name="conllu")
    greek_app.add_typer(interop_app, name="interop")
    greek_app.add_typer(annotation_profiles_app, name="annotation-profiles")


def _profile_payload(profile: Any) -> dict[str, Any]:
    """Return a JSON-ready profile mapping, including its content identity.

    The registry values are immutable typed objects.  Keeping this small adapter in
    the CLI lets the command remain compatible with the public ``to_dict`` contract
    without importing the implementation module at CLI import time.
    """
    if hasattr(profile, "to_dict"):
        raw = profile.to_dict()
    else:  # pragma: no cover - defensive for third-party registry adapters
        raw = to_plain(profile)
    payload = to_plain(raw)
    if not isinstance(payload, dict):
        raise TypeError("profile.to_dict() must return a mapping")
    profile_id = getattr(profile, "profile_id", None)
    if profile_id is not None:
        payload.setdefault("profile_id", str(profile_id))
    sha256 = getattr(profile, "sha256", None)
    if sha256 is not None:
        payload.setdefault("sha256", str(sha256))
    return payload


def _profile_field(payload: dict[str, Any], *names: str) -> str:
    """Choose a concise human-table value from a profile mapping."""
    for name in names:
        value = payload.get(name)
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return str(value)
    return "—"


def _profile_registries() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Load the read-only annotation/domain registries through the facade."""
    from aegean import greek

    annotation_registry = greek.list_annotation_profiles()
    domain_registry = greek.list_domain_profiles()
    annotations = tuple(annotation_registry.values()) if isinstance(annotation_registry, Mapping) else tuple(annotation_registry)
    domains = tuple(domain_registry.values()) if isinstance(domain_registry, Mapping) else tuple(domain_registry)
    return annotations, domains


@annotation_profiles_app.command("list")
def annotation_profiles_list(json_out: bool = JSON_OPT) -> None:
    """List registered annotation conventions and descriptive domain scopes."""
    try:
        annotations, domains = _profile_registries()
    except Exception as exc:
        raise fail(f"could not inspect annotation/domain profiles: {exc}") from None

    annotation_payloads = [_profile_payload(profile) for profile in annotations]
    domain_payloads = [_profile_payload(profile) for profile in domains]
    if json_out:
        emit_json({
            "annotation_profiles": annotation_payloads,
            "domain_profiles": domain_payloads,
        })
        return

    table(
        "annotation profiles",
        ["id", "compatibility", "source convention"],
        [
            [
                _profile_field(payload, "profile_id", "id"),
                _profile_field(payload, "compatibility", "compatibility_class"),
                _profile_field(payload, "source_convention", "source", "convention", "source_revision"),
            ]
            for payload in annotation_payloads
        ],
    )
    table(
        "domain profiles",
        ["id", "source layer"],
        [
            [
                _profile_field(payload, "profile_id", "id"),
                _profile_field(payload, "source_layer", "source_layer_id", "layer", "source"),
            ]
            for payload in domain_payloads
        ],
    )


@annotation_profiles_app.command("show")
def annotation_profiles_show(
    profile_id: str = typer.Argument(..., help="Exact annotation or domain profile id."),
    json_out: bool = JSON_OPT,
) -> None:
    """Show one immutable annotation or domain profile by its exact id."""
    try:
        annotations, domains = _profile_registries()
    except Exception as exc:
        raise fail(f"could not inspect annotation/domain profiles: {exc}") from None

    matches: list[tuple[str, Any]] = []
    for profile in annotations:
        if str(getattr(profile, "profile_id", "")) == profile_id:
            matches.append(("annotation", profile))
    for profile in domains:
        if str(getattr(profile, "profile_id", "")) == profile_id:
            matches.append(("domain", profile))
    if not matches:
        available = [
            str(getattr(profile, "profile_id", ""))
            for profile in (*annotations, *domains)
        ]
        hint = f" Available ids: {', '.join(available)}." if available else ""
        raise fail(f"unknown annotation/domain profile {profile_id!r}.{hint}")
    if len(matches) > 1:
        kinds = ", ".join(kind for kind, _ in matches)
        raise fail(f"profile id {profile_id!r} is ambiguous ({kinds}); use a unique id")

    kind, profile = matches[0]
    payload = _profile_payload(profile)
    if json_out:
        emit_json({"kind": kind, **payload})
        return

    table(
        f"{kind} profile: {profile_id}",
        ["field", "value"],
        [
            [key, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)]
            for key, value in payload.items()
        ],
    )



def _read_conllu_document(source: Path, *, strict: bool) -> UDDocument:
    """Load one local CoNLL-U document with the CLI's one-line error contract."""
    from aegean.greek.ud import load_conllu_document

    try:
        return load_conllu_document(source, strict=strict)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise fail(f"could not read CoNLL-U {source}: {exc}") from None


def _conllu_row_counts(rows: Sequence[UDRow]) -> dict[str, int]:
    """Count structural row kinds without coupling the CLI to private row classes."""
    counts = {"n_syntactic_tokens": 0, "n_multiword_ranges": 0,
              "n_empty_nodes": 0, "n_opaque_rows": 0}
    for row in rows:
        name = type(row).__name__
        if name == "UDToken":
            counts["n_syntactic_tokens"] += 1
        elif name == "UDMultiwordToken":
            counts["n_multiword_ranges"] += 1
        elif name == "UDEmptyNode":
            counts["n_empty_nodes"] += 1
        elif name == "UDOpaqueRow":
            counts["n_opaque_rows"] += 1
    return counts


def _conllu_summary(source: Path, document: UDDocument) -> dict[str, object]:
    """Build deterministic, prediction-free inspect output for a CoNLL-U document."""
    sentences = document.sentences
    sentence_rows: list[dict[str, object]] = []
    try:
        # utf-8-sig, matching the loader that produced ``document``: read as plain utf-8,
        # a leading BOM would stay glued to the first '#' and drop that comment from this
        # count alone, so one payload would report two different comment totals.
        total_comments = sum(
            line.startswith("#")
            for line in source.read_text(encoding="utf-8-sig").splitlines()
        )
    except (OSError, UnicodeError) as exc:
        raise fail(f"could not read CoNLL-U {source}: {exc}") from None
    total_rows = 0
    total_counts = {"n_syntactic_tokens": 0, "n_multiword_ranges": 0,
                    "n_empty_nodes": 0, "n_opaque_rows": 0}
    enhanced = False
    for index, sentence in enumerate(sentences, start=1):
        rows = sentence.rows or sentence.tokens
        counts = _conllu_row_counts(rows)
        total_rows += len(rows)
        for key in total_counts:
            total_counts[key] += counts[key]
        projection = sentence.projection
        enhanced = enhanced or projection.enhanced_dependencies_present
        sentence_rows.append(
            {
                "index": index,
                "sent_id": sentence.sent_id,
                "text": sentence.text,
                "n_comments": len(sentence.comments),
                "n_data_rows": len(rows),
                **counts,
                "projection": {
                    "ordinal_to_id": [list(pair) for pair in projection.ordinal_to_id],
                    "omitted_multiword_ranges": list(projection.omitted_ranges),
                    "omitted_empty_nodes": list(projection.omitted_empty_nodes),
                    "enhanced_dependencies_present": projection.enhanced_dependencies_present,
                },
            }
        )
    omitted = total_counts["n_multiword_ranges"] + total_counts["n_empty_nodes"]
    return {
        "format": "CoNLL-U",
        "source": str(source),
        "n_sentences": len(sentences),
        "n_comments": total_comments,
        "n_data_rows": total_rows,
        **total_counts,
        "projection": {
            "policy": "syntactic_words_v1",
            "kind": "syntactic_words",
            "model_tokens": total_counts["n_syntactic_tokens"],
            "structural_rows_omitted": omitted,
            "omitted_multiword_ranges": total_counts["n_multiword_ranges"],
            "omitted_empty_nodes": total_counts["n_empty_nodes"],
            "enhanced_dependencies_present": enhanced,
        },
        "sentences": sentence_rows,
    }


@conllu_app.command()
def inspect(
    source: Path = typer.Argument(..., metavar="INPUT", help="CoNLL-U file to inspect."),
    strict: bool = typer.Option(
        False, "--strict", help="Reject malformed rows, IDs, dependencies, and references."
    ),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Inspect lossless CoNLL-U structure and its explicit model projection."""
    document = _read_conllu_document(source, strict=strict)
    summary = _conllu_summary(source, document)
    if emit_result(summary, json_output=json_out, output=output):
        return
    table(
        f"CoNLL-U: {source}",
        ["measure", "value"],
        [
            [label, str(summary[key])]
            for key, label in (
                ("n_sentences", "sentences"),
                ("n_comments", "comments"),
                ("n_data_rows", "data rows"),
                ("n_syntactic_tokens", "syntactic words"),
                ("n_multiword_ranges", "multiword ranges"),
                ("n_empty_nodes", "empty nodes"),
                ("n_opaque_rows", "opaque rows"),
            )
        ],
    )


@conllu_app.command()
def export(
    source: Path = typer.Argument(..., metavar="INPUT", help="CoNLL-U file to copy."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination path; omit to write CoNLL-U to stdout."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Validate structure before exporting the original bytes."
    ),
) -> None:
    """Export a CoNLL-U file byte-for-byte, without invoking any pipeline model."""
    if strict:
        _read_conllu_document(source, strict=True)
    try:
        raw = source.read_bytes()
    except (OSError, UnicodeError) as exc:
        raise fail(f"could not read CoNLL-U {source}: {exc}") from None
    if output is None:
        stream = getattr(sys.stdout, "buffer", None)
        try:
            if stream is not None:
                stream.write(raw)
                stream.flush()
            else:
                sys.stdout.write(raw.decode("utf-8"))
                sys.stdout.flush()
        except (OSError, UnicodeError) as exc:
            raise fail(f"could not write CoNLL-U to stdout: {exc}") from None
        return
    from aegean._atomic import atomic_path

    try:
        with atomic_path(output) as temporary:
            temporary.write_bytes(raw)
    except OSError as exc:
        raise fail(f"cannot write {output}: {exc}") from None
    print(f"wrote {output}", file=sys.stderr)


def _interop_report_payload(bundle: Any, source: Path) -> dict[str, Any]:
    report = bundle.report
    return {
        "schema": bundle.schema,
        "report_schema": report.schema,
        "source": str(source),
        "target": bundle.target,
        "target_version": bundle.target_version,
        "direction": report.direction,
        "lossless": report.lossless,
        "native_fields": list(report.native_fields),
        "sidecar_fields": list(report.sidecar_fields),
        "lost_fields": list(report.lost_fields),
        "warnings": list(report.warnings),
        "omitted_ids": list(report.omitted_ids),
    }


@interop_app.command("export")
def interop_export(
    source: Path = typer.Argument(..., metavar="INPUT", help="Strict CoNLL-U input file."),
    target: str = typer.Option(
        ...,
        "--target",
        help="Target projection: conllu, spacy, stanza, or cltk.",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Destination .json interoperability bundle.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Export strict CoNLL-U through one adapter into a portable JSON bundle."""
    from aegean.io._interop_bundle import bundle_from_document, write_interop_bundle
    from aegean.io.interop import InteropError, from_conllu

    target = target.casefold()
    if target not in {"conllu", "spacy", "stanza", "cltk"}:
        raise fail(
            "could not export interoperability bundle: target must be one of "
            "conllu, spacy, stanza, or cltk"
        )
    try:
        imported = from_conllu(source, strict=True)
        bundle = bundle_from_document(imported.value, target=target)
        write_interop_bundle(bundle, output)
    except (OSError, UnicodeError, TypeError, ValueError, InteropError) as exc:
        raise fail(f"could not export interoperability bundle: {exc}") from None
    print(f"wrote {output}", file=sys.stderr)
    if json_out:
        emit_json(_interop_report_payload(bundle, source))


@interop_app.command("import")
def interop_import(
    source: Path = typer.Argument(..., metavar="BUNDLE", help="Interoperability bundle."),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Destination lossless CoNLL-U file.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Validate a portable bundle and recover its complete CoNLL-U document."""
    from aegean._atomic import atomic_path
    from aegean.io._interop_bundle import read_interop_bundle
    from aegean.io.interop import InteropError, to_conllu

    try:
        bundle = read_interop_bundle(source)
        exported = to_conllu(bundle.document)
        with atomic_path(output) as temporary:
            temporary.write_text(exported.value, encoding="utf-8", newline="")
    except (OSError, UnicodeError, TypeError, ValueError, InteropError) as exc:
        raise fail(f"could not import interoperability bundle: {exc}") from None
    print(f"wrote {output}", file=sys.stderr)
    if json_out:
        payload = _interop_report_payload(bundle, source)
        payload["output"] = str(output)
        emit_json(payload)


@interop_app.command("report")
def interop_report(
    source: Path = typer.Argument(..., metavar="BUNDLE", help="Interoperability bundle."),
    json_out: bool = JSON_OPT,
) -> None:
    """Validate a bundle and show exactly what is native, sidecar-held, or lost."""
    from aegean.io._interop_bundle import read_interop_bundle
    from aegean.io.interop import InteropError

    try:
        bundle = read_interop_bundle(source)
        payload = _interop_report_payload(bundle, source)
    except (OSError, UnicodeError, TypeError, ValueError, InteropError) as exc:
        raise fail(f"could not read interoperability bundle: {exc}") from None
    if json_out:
        emit_json(payload)
        return
    table(
        f"Interoperability: {source}",
        ["measure", "value"],
        [
            ["target", f"{bundle.target} {bundle.target_version or '(unknown version)'}"],
            ["lossless", "yes" if bundle.report.lossless else "no"],
            ["native", ", ".join(bundle.report.native_fields) or "(none)"],
            ["sidecar", ", ".join(bundle.report.sidecar_fields) or "(none)"],
            ["lost", ", ".join(bundle.report.lost_fields) or "(none)"],
            ["warnings", "; ".join(bundle.report.warnings) or "(none)"],
            ["omitted IDs", ", ".join(bundle.report.omitted_ids) or "(none)"],
        ],
    )


