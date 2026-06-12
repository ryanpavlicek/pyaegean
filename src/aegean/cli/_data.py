"""The `aegean data` group: the fetch-to-cache layer from the shell."""

from __future__ import annotations

import typer

from ._common import JSON_OPT, emit_json, table

data_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Fetched datasets and the local cache.",
    no_args_is_help=True,
)


@data_app.command("list")
def list_datasets(json_out: bool = JSON_OPT) -> None:
    """List the fetchable datasets (name, size note, license)."""
    from aegean.data import _REMOTE

    rows = [
        {"name": name, "note": spec.note, "license": spec.license, "extract": spec.extract}
        for name, spec in sorted(_REMOTE.items())
    ]
    if json_out:
        emit_json(rows)
        return
    table(
        "fetchable datasets (downloaded to the cache on demand, never bundled)",
        ["name", "note", "license"],
        [[str(r["name"]), str(r["note"]), str(r["license"])] for r in rows],
    )


@data_app.command()
def fetch(
    name: str = typer.Argument(..., help="Dataset name (see `aegean data list`)."),
    force: bool = typer.Option(False, "--force", help="Re-download even if cached."),
) -> None:
    """Fetch a dataset into the cache (sha256-verified); idempotent when cached."""
    from aegean.data import DataNotAvailableError, fetch as _fetch

    try:
        path = _fetch(name, force=force)
    except DataNotAvailableError as exc:
        raise typer.BadParameter(str(exc)) from None
    print(path)


@data_app.command()
def versions(json_out: bool = JSON_OPT) -> None:
    """The reproducibility manifest: every dataset's version + sha256.

    Pin it for a paper: `aegean data versions --json > data-versions.json`."""
    from aegean.data import versions as _versions

    manifest = _versions()
    if json_out:
        emit_json(manifest)
        return
    rows = [["package", str(manifest["package"]), ""]]
    rows += [
        [f"bundled/{name}", str(info["sha256"])[:16] + "…", f"{info['bytes']} B"]
        for name, info in manifest["bundled"].items()
    ]
    rows += [
        [f"fetched/{name}", str(info["sha256"])[:16] + "…" if info["sha256"] else "(unpinned)",
         "cached" if info["cached"] else "not cached"]
        for name, info in manifest["fetched"].items()
    ]
    table("data versions (pin with --json for papers)", ["dataset", "sha256", "status"], rows)


@data_app.command()
def cache(json_out: bool = JSON_OPT) -> None:
    """Show the cache location and its current contents."""
    from aegean.data import cache_dir

    root = cache_dir()
    entries = []
    if root.exists():
        for child in sorted(root.iterdir()):
            size = (
                sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
                if child.is_dir()
                else child.stat().st_size
            )
            entries.append({"name": child.name, "mb": round(size / 1e6, 1)})
    if json_out:
        emit_json({"cache_dir": str(root), "entries": entries})
        return
    table(
        f"cache: {root} (override with PYAEGEAN_CACHE)",
        ["entry", "MB"],
        [[str(e["name"]), str(e["mb"])] for e in entries],
    )
