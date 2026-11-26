"""``aegean bundle`` — create, inspect, verify, extract, and hydrate research bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import typer

from ._common import emit_json, fail

bundle_app = typer.Typer(
    help="Portable, SHA-256-verified, license-clean reproducible research bundles (.zip).",
    no_args_is_help=True,
)


def _load_corpus_arg(corpus_arg: str) -> tuple[Any, str | None]:
    """Load a corpus by dataset id or local file path; return ``(corpus, dataset_id_or_None)``."""
    from .. import load
    from ..core.corpus import Corpus

    p = Path(corpus_arg)
    if p.is_file():
        if p.suffix.lower() == ".db":
            from ..db import from_sqlite

            return from_sqlite(p), None
        return Corpus.from_json(p), None
    return load(corpus_arg), corpus_arg


@bundle_app.command("create")
def bundle_create(
    output: Annotated[Path, typer.Argument(help="Destination .zip bundle path.")],
    corpus: Annotated[
        str | None,
        typer.Option("--corpus", "-c", help="Corpus dataset id or local JSON/SQLite path."),
    ] = None,
    dataset: Annotated[
        str | None,
        typer.Option("--dataset", help="Registered dataset id for license-clean retrieval pointer."),
    ] = None,
    title: Annotated[str, typer.Option("--title", help="Human-readable bundle title.")] = "",
    description: Annotated[str, typer.Option("--description", help="Short bundle description.")] = "",
    site: Annotated[str | None, typer.Option("--site", help="Optional site filter to record/apply.")] = None,
    period: Annotated[str | None, typer.Option("--period", help="Optional period filter to record/apply.")] = None,
    workbench_state: Annotated[
        Path | None,
        typer.Option("--state", help="Workbench workspace backup JSON (from `aegean workbench --state`)."),
    ] = None,
    review: Annotated[
        list[Path] | None,
        typer.Option("--review", "-r", help="Review CSV path to include (repeatable; editable companions auto-included)."),
    ] = None,
    receipt: Annotated[
        list[Path] | None,
        typer.Option("--receipt", help="Analysis or evaluation receipt JSON path (repeatable)."),
    ] = None,
    embed_corpus: Annotated[
        str,
        typer.Option("--embed-corpus", help="Corpus embedding policy: auto (default, NC-safe), always, or never."),
    ] = "auto",
    as_json: Annotated[bool, typer.Option("--json", help="Emit manifest as JSON.")] = False,
) -> None:
    """Create a deterministic, SHA-256-verified research bundle (.zip)."""
    from ..bundle import create_bundle

    if embed_corpus not in ("auto", "always", "never"):
        raise fail("--embed-corpus must be one of: auto, always, never")

    corpus_obj = None
    resolved_dataset = dataset
    filter_spec: dict[str, str] = {}
    if site:
        filter_spec["site"] = site
    if period:
        filter_spec["period"] = period

    if corpus:
        try:
            corpus_obj, inferred_ds = _load_corpus_arg(corpus)
        except Exception as exc:
            raise fail(f"could not load corpus {corpus!r}: {exc}") from None
        if resolved_dataset is None:
            resolved_dataset = inferred_ds
        if filter_spec:
            corpus_obj = corpus_obj.filter(**filter_spec)

    policy: Literal["auto", "always", "never"] = embed_corpus  # type: ignore[assignment]
    try:
        manifest = create_bundle(
            output,
            corpus=corpus_obj,
            dataset=resolved_dataset,
            filter_spec=filter_spec or None,
            title=title,
            description=description,
            workbench_state=workbench_state,
            review_paths=tuple(review or ()),
            receipts=tuple(receipt or ()),
            embed_corpus=policy,
        )
    except Exception as exc:
        raise fail(str(exc)) from None

    if as_json:
        emit_json(manifest.to_dict())
        return

    typer.echo(
        f"Created {output} ({manifest.format}, {len(manifest.members)} members, "
        f"corpus={'embedded' if manifest.corpus_embedded else 'pointer' if manifest.corpus_ref else 'none'}, "
        f"redistributable={'yes' if manifest.redistributable else 'no'})"
    )


@bundle_app.command("inspect")
def bundle_inspect(
    bundle: Annotated[Path, typer.Argument(help="Path to the .zip research bundle.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit manifest as JSON.")] = False,
) -> None:
    """Inspect a research bundle's manifest, provenance, and members."""
    from ..bundle import inspect_bundle

    try:
        manifest = inspect_bundle(bundle)
    except Exception as exc:
        raise fail(str(exc)) from None

    if as_json:
        emit_json(manifest.to_dict())
        return

    typer.echo(f"Bundle: {bundle}  [{manifest.format}]")
    if manifest.title:
        typer.echo(f"Title:  {manifest.title}")
    typer.echo(
        f"Built:  pyaegean {manifest.pyaegean_version} · {manifest.created_at} · "
        f"redistributable={'yes' if manifest.redistributable else 'no'}"
    )
    if manifest.corpus_embedded:
        typer.echo("Corpus: embedded (corpus.json.gz)")
    elif manifest.corpus_ref is not None:
        ref = manifest.corpus_ref
        typer.echo(
            f"Corpus: pointer → dataset={ref.dataset or '(custom)'} "
            f"license={ref.license or 'upstream'}"
        )
    for note in manifest.license_notes:
        typer.echo(f"Note:   {note}")
    typer.echo(f"Members ({len(manifest.members)}):")
    for m in manifest.members:
        typer.echo(f"  {m.path:<36} {m.kind:<16} {m.size:>8} B  {m.sha256[:12]}")


@bundle_app.command("verify")
def bundle_verify(
    bundle: Annotated[Path, typer.Argument(help="Path to the .zip research bundle.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit verification report as JSON.")] = False,
) -> None:
    """Verify archive safety and SHA-256 checksums for every member."""
    from ..bundle import verify_bundle

    report = verify_bundle(bundle)
    if as_json:
        emit_json(report.to_dict())
        if not report.ok:
            raise typer.Exit(code=1)
        return

    if report.ok:
        typer.echo(
            f"PASS: {bundle} ({report.checked_members} members verified, "
            f"redistributable={'yes' if report.redistributable else 'no'})"
        )
        for warn in report.warnings:
            typer.echo(f"  warning: {warn}")
    else:
        for err in report.errors:
            typer.echo(f"FAIL: {err}", err=True)
        raise typer.Exit(code=1)


@bundle_app.command("extract")
def bundle_extract(
    bundle: Annotated[Path, typer.Argument(help="Path to the .zip research bundle.")],
    dest: Annotated[Path, typer.Argument(help="Target directory to extract verified files into.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit manifest as JSON.")] = False,
) -> None:
    """Verify and unpack a research bundle safely into a directory."""
    from ..bundle import extract_bundle

    try:
        manifest = extract_bundle(bundle, dest)
    except Exception as exc:
        raise fail(str(exc)) from None

    if as_json:
        emit_json({"dest": str(dest), "manifest": manifest.to_dict()})
        return
    typer.echo(f"Extracted {len(manifest.members)} verified members to {dest}")


@bundle_app.command("hydrate")
def bundle_hydrate(
    bundle: Annotated[Path, typer.Argument(help="Path to the .zip research bundle.")],
    dest: Annotated[Path, typer.Argument(help="Target directory for unpacked workspace + corpus.")],
    fetch: Annotated[
        bool,
        typer.Option("--fetch", help="Allow fetching non-embedded remote corpora under their upstream license."),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit hydration summary as JSON.")] = False,
) -> None:
    """Verify, unpack, and reconstruct a research bundle (including pointer corpora)."""
    from ..bundle import hydrate_bundle

    try:
        hydrated = hydrate_bundle(bundle, dest=dest, allow_fetch=fetch)
    except Exception as exc:
        raise fail(str(exc)) from None

    corpus_out: str | None = None
    if hydrated.corpus is not None:
        target_corpus = Path(dest) / "hydrated-corpus.json"
        hydrated.corpus.to_json(target_corpus)
        corpus_out = str(target_corpus)

    summary = {
        "dest": str(dest),
        "format": hydrated.manifest.format,
        "redistributable": hydrated.manifest.redistributable,
        "documents": len(hydrated.corpus) if hydrated.corpus is not None else 0,
        "corpus_path": corpus_out,
        "has_workbench_state": hydrated.workbench_state is not None,
        "review_files": {k: str(v) for k, v in hydrated.review_files.items()},
        "receipts": sorted(hydrated.receipts),
    }
    if as_json:
        emit_json(summary)
        return

    typer.echo(
        f"Hydrated {bundle} → {dest} "
        f"(docs={summary['documents']}, reviews={len(hydrated.review_files)}, "
        f"receipts={len(hydrated.receipts)})"
    )
