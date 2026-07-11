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


def _entry_paths(root: Path, name: str, *, version: str | None = None) -> list[Path]:
    """Everything in the store belonging to one dataset: the real artifact(s) plus
    any leftover partial-download or extraction files.

    Uses the same on_disk-aware paths as ``data list`` / ``doctor`` (via
    ``on_disk_paths``), so a dataset a backend writes under a different filename
    (a prebuilt lexicon index -> ``lsj-perseus-index.json.gz``, an ``agdt-derived``
    member) is actually found and removed, not just the empty ``root/name`` probe
    (which left ``list`` reporting it downloaded while ``remove`` refused it). Kept
    versioned entries (``<name>@<version>`` from ``fetch(name, version=...)``) are
    folded in too, so ``data remove NAME`` reclaims them instead of orphaning
    unreclaimable disk. ``.lock`` files are excluded from removal targets (a held
    lock signals an in-progress fetch; the caller guards on it).

    ``version`` restricts the result to one kept release's entries
    (``<name>@<version>`` and its siblings), for surgical removal that leaves the
    current copy and the other versions in place."""
    from aegean.data import _REMOTE, on_disk_paths, versioned_entry_paths

    if version is not None:
        # Surgical, single-version removal: only that kept release's entries.
        return [p for p in versioned_entry_paths(name, root, version=version)
                if not p.name.endswith(".lock")]

    spec = _REMOTE.get(name)
    paths = list(on_disk_paths(spec, root)) if spec is not None else [root / name]
    paths += [
        # the raw dataset-named copy an older fetch may have left (before fetch()
        # normalized single-file datasets to their on_disk name) plus the
        # partial-download / extraction leftovers, all in the dataset's namespace
        root / name,
        root / (name + ".part"),
        root / (name + ".part.info"),
        root / (name + ".extract"),
        root / (name + ".old"),     # a superseded extraction awaiting cleanup (re-pin swap)
        root / (name + ".sha256"),  # the extract-dataset stamp (sha of the unpacked archive)
    ]
    # Every kept-version entry (``<name>@<version>`` plus its download/extraction
    # siblings), so a full remove reclaims the versioned footprint; the ``.lock`` of
    # an in-progress versioned fetch is left for the caller's in-progress guard.
    paths += [p for p in versioned_entry_paths(name, root) if not p.name.endswith(".lock")]
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:  # de-dup: on_disk defaults to [root/name], which may repeat
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _resolve_name(name: str) -> str:
    """Map a friendly stem to its registered dataset name (``damos`` -> ``damos-corpus``,
    ``nt`` -> ``nt-corpus``), passing an exact name through unchanged. So ``data fetch damos``
    works, not only ``data fetch damos-corpus``."""
    from aegean.data import _REMOTE

    if name in _REMOTE:
        return name
    for full in _REMOTE:
        for suffix in ("-corpus", "-index", "-app"):
            if full.endswith(suffix) and full[: -len(suffix)] == name:
                return full
    return name


# Friendly guidance for the Linear B corpus, replacing the raw "no pinned URL" wall: DAMOS is a
# ready, directly-fetchable corpus; LiBER has no public download/API and is rights-restricted, so
# it is browse-only — a licensed LiBER/EpiDoc export is imported, not fetched.
_LINEARB_GUIDANCE = (
    "No generic 'linearb-corpus' download exists. Your options for a Linear B corpus:\n"
    "  • DAMOS (recommended, ready to fetch — ~5,900 tablets, CC BY-NC-SA 4.0):\n"
    "        aegean data fetch damos\n"
    "        aegean info damos\n"
    "  • LiBER (liber.cnr.it): browse-only — no public download or API, and rights-restricted,\n"
    "    so it cannot be fetched. Study it online at https://liber.cnr.it/\n"
    "  • Your own licensed export (a LiBER selection, a DAMOS EpiDoc download): import it —\n"
    "        aegean import your-export.xml --epidoc --script linearb\n"
    "    or point the fetch at a copy you host:  set PYAEGEAN_LINEARB_CORPUS_URL"
)


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
    "isicily-corpus": "load it:  aegean info isicily",
    "iip-corpus": "load it:  aegean info iip",
    "iospe-corpus": "load it:  aegean info iospe",
    "igcyr-corpus": "load it:  aegean info igcyr",
    "edh-corpus": "load it:  aegean info edh",
    "ddbdp-corpus": "search it (memory-friendly):  aegean db search ddbdp \"βασιλέως\"",
    "linearb-corpus": "load it:  aegean info linearb",
    "sigla-corpus": "load it:  aegean info sigla",
    "nt-corpus": "load it:  aegean info nt",
    "lineara-images": "serve it:  aegean workbench",
}


@data_app.command("list")
def list_datasets(json_out: bool = JSON_OPT) -> None:
    """List the fetchable datasets and whether each is downloaded.

    Columns: name, downloaded (with the actual on-disk size, directory-recursive
    for extracted datasets, and including any kept ``--version`` entries), size
    note, and license."""
    from aegean.data import (
        _REMOTE,
        available_versions,
        cache_dir,
        downloaded_bytes,
        is_downloaded,
        versioned_bytes,
    )

    root = cache_dir()
    rows: list[dict[str, Any]] = []
    display: list[list[str]] = []
    for name, spec in sorted(_REMOTE.items()):
        # The real on-disk footprint, not a bare root/name probe: index datasets
        # land under their built-index filename and agdt-derived members are
        # copied out, so those would read "not downloaded" otherwise.
        downloaded = is_downloaded(spec, root)
        ver_bytes = versioned_bytes(name, root)
        # downloaded_bytes already folds in the versioned footprint; when the
        # current pin is absent but a kept version is present, surface that alone.
        size = downloaded_bytes(spec, root) if downloaded else (ver_bytes or None)
        # Per-version breakdown (only versions actually on disk), for surgical removal.
        per_version = [
            {"version": v["version"], "bytes": vb}
            for v in available_versions(name)
            if (vb := versioned_bytes(name, root, version=v["version"])) > 0
        ]
        rows.append(
            {
                "name": name,
                "note": spec.note,
                "license": spec.license,
                "extract": spec.extract,
                "downloaded": downloaded,
                "bytes": size,
                # additive keys: the kept-version footprint, split out from ``bytes``
                "versioned_bytes": ver_bytes,
                "versioned": per_version,
            }
        )
        display.append(
            [
                name,
                _downloaded_cell(downloaded, size, ver_bytes),
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


def _downloaded_cell(downloaded: bool, size: int | None, ver_bytes: int) -> str:
    """The `data list` downloaded-column text, surfacing any versioned footprint so a
    kept ``--version`` entry's reclaimable disk is visible where it was invisible before."""
    if downloaded:
        if ver_bytes:
            return f"yes ({_human_size(size or 0)}, incl. {_human_size(ver_bytes)} versioned)"
        return f"yes ({_human_size(size or 0)})"
    if ver_bytes:
        return f"versioned only ({_human_size(ver_bytes)})"
    return "no"


class _FetchProgress:
    """A TTY-only live line for `aegean data fetch`'s ``progress=`` hook, in the
    repainted-stderr-line style of ``_db.live_progress``. One repainted line: the
    download phase reports bytes (rendered as MB, with a percent when the size is
    known), then an ``extract`` dataset's unpacking reports tar members (rendered as
    files). The two phases are told apart by ``total`` switching value (a byte size,
    or -1 when unknown, to a member count). Piped / captured / ``--json`` runs stay
    clean via the isatty gate; ``close()`` ends a still-open line so a following
    message starts fresh."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._phase = -1  # -1 = nothing yet; 0 = download (bytes); >=1 = extraction (members)
        self._last_total: int | None = None
        self._open = False  # the current line lacks its closing newline

    def __call__(self, done: int, total: int) -> None:
        if not sys.stderr.isatty():  # piped / captured / --json: stay silent
            return
        if self._last_total is None:
            self._phase = 0
        elif total != self._last_total:
            # a phase boundary (bytes -> members): close any dangling line first
            if self._open:
                print(file=sys.stderr)
                self._open = False
            self._phase += 1
        self._last_total = total
        if self._phase == 0:
            self._paint(f"fetching {self._name}", done, total, unit="MB", scale=1e6)
        else:
            self._paint(f"extracting {self._name}", done, total, unit="files", scale=1)

    def _paint(self, label: str, done: int, total: int, *, unit: str, scale: float) -> None:
        if total > 0:
            end = "\n" if done >= total else ""
            if scale == 1:  # counts (tar members): plain integers
                body = f"{done:,}/{total:,} {unit} ({100 * done // total}%)"
            else:  # bytes -> MB
                body = f"{done / scale:.1f}/{total / scale:.1f} {unit} ({100 * done // total}%)"
            print(f"\r  {label}: {body}", file=sys.stderr, end=end, flush=True)
            self._open = end == ""
        elif scale != 1:  # unknown byte total (-1): bytes only, no percent
            print(f"\r  {label}: {done / scale:.1f} {unit}", file=sys.stderr, end="", flush=True)
            self._open = True

    def close(self) -> None:
        if self._open and sys.stderr.isatty():
            print(file=sys.stderr)  # close the dangling line before the next message
            self._open = False


@data_app.command()
def fetch(
    name: str = typer.Argument(..., help="Dataset name (see `aegean data list`)."),
    version: str | None = typer.Option(
        None, "--version",
        help="Fetch a kept historical release (e.g. v1) into a version-suffixed store "
        "entry, for reproducing an earlier analysis (see `aegean data versions`).",
    ),
    force: bool = typer.Option(
        False, "--force", help="Replace the stored copy with a fresh download."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Download a dataset into the local store (sha256-verified).

    A one-time download: when a valid copy is already stored the call is a
    no-op, and an interrupted transfer resumes from its partial file on the
    next attempt instead of restarting. The result stays until `aegean data
    remove` deletes it. `--version v1` fetches a kept prior release (the project
    still hosts the superseded epigraphy corpora) into a separate
    ``<name>@<version>`` store entry, leaving the current copy untouched."""
    from aegean.data import _REMOTE, DataNotAvailableError, fetch as _fetch

    name = _resolve_name(name)
    if name not in _REMOTE:
        raise fail(_unknown_dataset(name))
    # A live byte/member line on a real terminal; --json (and piped) runs stay silent.
    painter = None if json_out else _FetchProgress(name)
    try:
        path = _fetch(name, version=version, force=force, progress=painter)
    except DataNotAvailableError as exc:  # a known name that cannot be fetched (network, …)
        if name == "linearb-corpus" and version is None:  # BYO slot: guide to DAMOS, not a raw wall
            raise fail(_LINEARB_GUIDANCE) from None
        raise fail(str(exc)) from None
    finally:
        if painter is not None:
            painter.close()  # end any open line before the path / hint prints
    if json_out:
        emit_json(
            {"name": name, "version": version, "path": str(path), "bytes": _on_disk_bytes(path)}
        )
        return
    print(path)
    if version is not None:
        # The current-copy load hint would load the CURRENT data, not this release; point
        # at the versioned loader instead (only the *-corpus datasets have a load path).
        stem = name[: -len("-corpus")] if name.endswith("-corpus") else name
        print(
            f"historical pin — load it:  python -c \"import aegean; "
            f"aegean.load('{stem}', version='{version}')\"",
            file=sys.stderr,
        )
        return
    hint = _FETCH_HINTS.get(name)
    if hint is not None:
        print(hint, file=sys.stderr)


@data_app.command()
def remove(
    name: str | None = typer.Argument(
        None, help="Downloaded dataset to delete (see `aegean data list`)."
    ),
    remove_all: bool = typer.Option(False, "--all", help="Delete every downloaded dataset."),
    version: str | None = typer.Option(
        None, "--version",
        help="Delete only this kept ``--version`` entry (e.g. v1), leaving the current "
        "copy and other versions in place (see `aegean data versions`).",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Delete downloaded dataset(s) from the local store, reclaiming the space.

    This is the only way stored data leaves disk (nothing is evicted or expires
    on its own); `aegean data fetch NAME` downloads a removed dataset again.
    Removing a dataset also reclaims any kept ``--version`` entries it holds;
    `--version v1` removes only that one pinned release."""
    import shutil

    from aegean.data import _REMOTE, cache_dir, versioned_entry_paths

    if version is not None and remove_all:
        raise fail("--version deletes one dataset's kept release; it cannot combine with --all")
    if version is not None and name is None:
        raise fail("name a dataset to remove a --version of (see `aegean data versions`)")
    if name is None and not remove_all:
        raise fail("name a dataset to remove, or pass --all (see `aegean data list`)")
    if name is not None:
        name = _resolve_name(name)  # so `data remove damos` works, not only `damos-corpus`
        if name not in _REMOTE:
            raise fail(_unknown_dataset(name))

    root = cache_dir()
    names = sorted(_REMOTE) if remove_all else [name or ""]
    removed: list[dict[str, Any]] = []
    for n in names:
        # A held lock means a fetch is in progress; removing under it would corrupt the
        # transfer or be silently undone. The current-pin fetch holds ``<n>.lock``; a
        # versioned fetch holds ``<n>@<version>.lock``. Check the locks in scope.
        locked = []
        if version is None and (root / (n + ".lock")).exists():
            locked.append(n)
        locked += [
            p.name for p in versioned_entry_paths(n, root, version=version)
            if p.name.endswith(".lock")
        ]
        if locked:
            scope = f"{n}@{version}" if version is not None else n
            raise fail(
                f"a fetch of {scope!r} appears to be in progress — let it finish "
                f"(or delete {locked[0]} in the store if it is stale) and retry"
            )
        # Gate on the full target set, not the main entry: an interrupted
        # first fetch leaves only .part/.part.info orphans, and those must be
        # removable too.
        targets = [p for p in _entry_paths(root, n, version=version) if p.exists()]
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
        label = f"{n}@{version}" if version is not None else n
        removed.append({"name": label, "path": str(entry), "bytes": size})

    if not remove_all and not removed:
        if version is not None:
            raise fail(
                f"version {version!r} of {name!r} is not downloaded; "
                "`aegean data versions` shows the kept releases"
            )
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

    Kept prior release pins (the project still hosts the superseded epigraphy
    corpora) are listed as ``fetched/<name>@<version>`` rows — fetch one with
    `aegean data fetch <name> --version <v>`. Pin the whole manifest for a paper:
    `aegean data versions --json > data-versions.json`."""
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
        # Kept historical pins, one indented row each (reproducibility of an earlier release).
        for pin in info.get("history", []):
            status = "cached" if pin.get("cached") else "not cached"
            note = f"{status} (superseded by {pin['superseded']})" if pin.get("superseded") else status
            rows.append(
                [f"fetched/{name}@{pin['version']}", str(pin["sha256"])[:16] + "…", note]
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
