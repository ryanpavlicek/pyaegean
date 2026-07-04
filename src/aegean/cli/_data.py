"""The `aegean data` group: the fetch-to-store layer from the shell."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import typer

from ._common import JSON_OPT, emit_json, fail, table

data_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help=(
        "Fetched datasets and the local store. A fetched dataset is a complete local "
        "download: nothing is re-fetched, evicted, or expires; it stays until "
        "`aegean data remove` deletes it or `aegean data fetch --force` replaces it."
    ),
    no_args_is_help=True,
)


def _on_disk_bytes(path: Path) -> int:
    """Actual bytes a store entry occupies (recursive for extracted directories)."""
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return path.stat().st_size


def _human_size(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    if n >= 1e3:
        return f"{n / 1e3:.1f} kB"
    return f"{n} B"


def _entry_paths(root: Path, name: str) -> list[Path]:
    """Everything in the store belonging to one dataset: the real artifact(s) plus
    any leftover partial-download or extraction files.

    Uses the same on_disk-aware paths as ``data list`` / ``doctor`` (via
    ``on_disk_paths``), so a dataset a backend writes under a different filename
    (a prebuilt lexicon index -> ``lsj-perseus-index.json.gz``, an ``agdt-derived``
    member) is actually found and removed, not just the empty ``root/name`` probe
    (which left ``list`` reporting it downloaded while ``remove`` refused it)."""
    from aegean.data import _REMOTE, on_disk_paths

    spec = _REMOTE.get(name)
    paths = list(on_disk_paths(spec, root)) if spec is not None else [root / name]
    paths += [
        root / (name + ".part"),
        root / (name + ".part.info"),
        root / (name + ".extract"),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:  # de-dup: on_disk defaults to [root/name], which may repeat
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _unknown_dataset(name: str) -> str:
    """The one-line unknown-name message shared by fetch and remove, with a
    did-you-mean over the registered names and their stems (so a typo of the
    short form still finds it: 'damso' suggests 'damos-corpus')."""
    from aegean.core.resolve import suggest
    from aegean.data import _REMOTE

    stems: dict[str, str] = {}
    for full in _REMOTE:
        stems.setdefault(full, full)
        for suffix in ("-corpus", "-index", "-app"):
            if full.endswith(suffix):
                stems.setdefault(full[: -len(suffix)], full)
    close: list[str] = []
    for m in suggest(name, stems, n=3):
        if stems[m] not in close:
            close.append(stems[m])
    if close:
        maybe = " or ".join(repr(m) for m in close[:2])
        return (
            f"unknown dataset {name!r} — did you mean {maybe}? "
            f"(`aegean data list` shows all {len(_REMOTE)})"
        )
    return f"unknown dataset {name!r}; `aegean data list` shows the registered names"


# The natural next command after a fetch, per asset (stdout keeps the bare path
# for scripting; the hint goes to stderr, the 0.14.3 geo-hint pattern).
_FETCH_HINTS = {
    "damos-corpus": "load it:  aegean info damos",
    "linearb-corpus": "load it:  aegean info linearb",
    "sigla-corpus": "load it:  aegean info sigla",
    "nt-corpus": "load it:  aegean info nt",
    "lineara-images": "serve it:  aegean workbench",
}


@data_app.command("list")
def list_datasets(json_out: bool = JSON_OPT) -> None:
    """List the fetchable datasets and whether each is downloaded.

    Columns: name, downloaded (with the actual on-disk size, directory-recursive
    for extracted datasets), size note, and license."""
    from aegean.data import _REMOTE, cache_dir, downloaded_bytes, is_downloaded

    root = cache_dir()
    rows: list[dict[str, Any]] = []
    display: list[list[str]] = []
    for name, spec in sorted(_REMOTE.items()):
        # The real on-disk footprint, not a bare root/name probe: index datasets
        # land under their built-index filename and agdt-derived members are
        # copied out, so those would read "not downloaded" otherwise.
        downloaded = is_downloaded(spec, root)
        size = downloaded_bytes(spec, root) if downloaded else None
        rows.append(
            {
                "name": name,
                "note": spec.note,
                "license": spec.license,
                "extract": spec.extract,
                "downloaded": downloaded,
                "bytes": size,
            }
        )
        display.append(
            [
                name,
                f"yes ({_human_size(size)})" if size is not None else "no",
                spec.note,
                spec.license,
            ]
        )
    if json_out:
        emit_json(rows)
        return
    table(
        "fetchable datasets (a fetch is a one-time download into the local store)",
        ["name", "downloaded", "note", "license"],
        display,
    )


@data_app.command()
def fetch(
    name: str = typer.Argument(..., help="Dataset name (see `aegean data list`)."),
    force: bool = typer.Option(
        False, "--force", help="Replace the stored copy with a fresh download."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Download a dataset into the local store (sha256-verified).

    A one-time download: when a valid copy is already stored the call is a
    no-op, and an interrupted transfer resumes from its partial file on the
    next attempt instead of restarting. The result stays until `aegean data
    remove` deletes it."""
    from aegean.data import _REMOTE, DataNotAvailableError, fetch as _fetch

    if name not in _REMOTE:
        raise fail(_unknown_dataset(name))
    try:
        path = _fetch(name, force=force)
    except DataNotAvailableError as exc:  # a known name that cannot be fetched (network, …)
        raise fail(str(exc)) from None
    if json_out:
        emit_json({"name": name, "path": str(path), "bytes": _on_disk_bytes(path)})
        return
    print(path)
    hint = _FETCH_HINTS.get(name)
    if hint is not None:
        print(hint, file=sys.stderr)


@data_app.command()
def remove(
    name: str | None = typer.Argument(
        None, help="Downloaded dataset to delete (see `aegean data list`)."
    ),
    remove_all: bool = typer.Option(False, "--all", help="Delete every downloaded dataset."),
    json_out: bool = JSON_OPT,
) -> None:
    """Delete downloaded dataset(s) from the local store, reclaiming the space.

    This is the only way stored data leaves disk (nothing is evicted or expires
    on its own); `aegean data fetch NAME` downloads a removed dataset again."""
    import shutil

    from aegean.data import _REMOTE, cache_dir

    if name is None and not remove_all:
        raise fail("name a dataset to remove, or pass --all (see `aegean data list`)")
    if name is not None and name not in _REMOTE:
        raise fail(_unknown_dataset(name))

    root = cache_dir()
    names = sorted(_REMOTE) if remove_all else [name or ""]
    removed: list[dict[str, Any]] = []
    for n in names:
        if (root / (n + ".lock")).exists():
            # a fetch of this dataset is running (its per-dataset lock is held);
            # removing under it would corrupt the transfer or be silently undone
            raise fail(
                f"a fetch of {n!r} appears to be in progress — let it finish "
                f"(or delete {n}.lock in the store if it is stale) and retry"
            )
        # Gate on the full target set, not the main entry: an interrupted
        # first fetch leaves only .part/.part.info orphans, and those must be
        # removable too.
        targets = [p for p in _entry_paths(root, n) if p.exists()]
        if not targets:
            continue
        entry = targets[0]  # the real artifact removed (root/name for most; the index file otherwise)
        size = sum(_on_disk_bytes(p) for p in targets)
        try:
            for p in targets:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
        except OSError as exc:
            # a file held open by another process (a concurrent fetch, an open reader):
            # one clean line, not a traceback, and no false "removed" claim
            raise fail(
                f"could not remove {n!r}: a file is in use ({exc}); "
                "if a fetch is running, retry after it finishes"
            ) from None
        removed.append({"name": n, "path": str(entry), "bytes": size})

    if not remove_all and not removed:
        raise fail(
            f"dataset {name!r} is not downloaded; `aegean data list` shows what is"
        )
    total = sum(int(r["bytes"]) for r in removed)
    if json_out:
        emit_json({"removed": removed, "reclaimed_bytes": total})
        return
    if not removed:
        print("nothing to remove: no datasets are downloaded")
        return
    for r in removed:
        print(f"removed {r['name']}: {r['path']} ({_human_size(int(r['bytes']))} reclaimed)")
    if len(removed) > 1:
        print(f"reclaimed {_human_size(total)} across {len(removed)} datasets")


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
    for name, info in manifest["fetched"].items():
        if info["sha256"]:
            sha = str(info["sha256"])[:16] + "…"
        elif info.get("url_overridden"):
            # A pinned sha exists but fetch skips it for the env-override URL.
            sha = "(overridden: sha not enforced)"
        else:
            sha = "(unpinned)"
        rows.append(
            [f"fetched/{name}", sha, "cached" if info["cached"] else "not cached"]
        )
    table("data versions (pin with --json for papers)", ["dataset", "sha256", "status"], rows)


@data_app.command()
def store(json_out: bool = JSON_OPT) -> None:
    """Show the local store: its location and every downloaded entry.

    The store is permanent: entries are complete downloads that are never
    re-fetched, evicted, or expired; they stay until `aegean data remove`
    deletes them or `aegean data fetch --force` replaces one. (Not the opt-in
    analysis cache: that is the top-level `aegean cache`.)"""
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
        emit_json({"store": str(root), "cache_dir": str(root), "entries": entries})
        return
    table(
        f"local data store: {root} (override with PYAEGEAN_CACHE)",
        ["entry", "MB"],
        [[str(e["name"]), str(e["mb"])] for e in entries],
    )
    print(
        "entries are permanent local downloads: nothing is re-fetched, evicted, or "
        "expires; delete with `aegean data remove NAME` (or --all)."
    )


@data_app.command(deprecated=True)
def cache(json_out: bool = JSON_OPT) -> None:
    """Deprecated alias for `aegean data store` (this is the permanent data store,
    not the opt-in analysis cache at `aegean cache`); removal no sooner than the
    next minor."""
    print(
        "aegean: `aegean data cache` is deprecated; use `aegean data store`",
        file=sys.stderr,
    )
    store(json_out=json_out)
