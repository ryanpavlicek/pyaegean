"""Bundled-data access + a download-to-cache layer.

Compact text data ships in the wheel (read via importlib.resources). Large or
license-restricted assets — notably the 500 MB Linear A facsimile mirror — are
NOT bundled; they are fetched on demand from upstream into a user cache. This
is how the package stays small (the workbench's 500 MB problem can't recur).

Downloads are sha256-verified (when a checksum is pinned), atomic (written to a
``.part`` file then renamed), and idempotent (a present, valid cache file is a
no-op). A dataset's URL can be overridden without a code change via
``PYAEGEAN_<NAME>_URL`` (e.g. ``PYAEGEAN_LINEARA_IMAGES_URL``), so a researcher
can point at their own mirror before an official release is pinned.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


class DataNotAvailableError(RuntimeError):
    """Raised when a non-bundled dataset has not been fetched (or can't be)."""


def _bundled_bytes(*parts: str) -> bytes:
    return files("aegean.data").joinpath("bundled", *parts).read_bytes()


def load_bundled_json(*parts: str) -> Any:
    """Load a JSON file shipped inside the wheel, e.g.
    ``load_bundled_json("lineara", "signs.json")``."""
    return json.loads(_bundled_bytes(*parts).decode("utf-8"))


def cache_dir() -> pathlib.Path:
    """Where fetched datasets are cached (override with ``PYAEGEAN_CACHE``)."""
    base = (
        os.environ.get("PYAEGEAN_CACHE")
        or os.environ.get("XDG_CACHE_HOME")
        or os.path.join(os.path.expanduser("~"), ".cache")
    )
    p = pathlib.Path(base) / "pyaegean"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True, slots=True)
class DataSpec:
    name: str
    url: str
    license: str
    sha256: str = ""
    note: str = ""


# Remote datasets. The Linear A facsimile imagery lives in the workbench repo;
# we fetch (never re-host) it. No official release is pinned yet (the imagery is
# © École Française d'Athènes and the owner must publish the mirror first); set
# PYAEGEAN_LINEARA_IMAGES_URL to fetch from your own mirror in the meantime.
_REMOTE: dict[str, DataSpec] = {
    "lineara-images": DataSpec(
        name="lineara-images",
        url="",  # pin a ryanpavlicek/linearaworkbench release asset once published
        license="© École Française d'Athènes — academic reference only; not redistributed",
        note="~500 MB facsimile/photo mirror; download on demand from the workbench repo.",
    ),
}


def _env_url_var(name: str) -> str:
    return "PYAEGEAN_" + name.upper().replace("-", "_") + "_URL"


def _resolve_url(spec: DataSpec) -> str:
    """The effective download URL: an env override wins over the pinned URL."""
    return os.environ.get(_env_url_var(spec.name)) or spec.url


def sha256_file(path: pathlib.Path, *, chunk: int = 1 << 20) -> str:
    """Streaming sha256 of a file (won't load a 500 MB asset into memory)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def fetch(name: str, *, force: bool = False) -> pathlib.Path:
    """Download a registered remote dataset into the cache and return its path.

    Verifies the sha256 when one is pinned, downloads atomically, and is a
    no-op when a valid cache file already exists. Raises
    :class:`DataNotAvailableError` for unknown datasets, un-pinned URLs,
    checksum mismatches, or network failures — never silently, and never
    blocking ``import``.
    """
    spec = _REMOTE.get(name)
    if spec is None:
        raise DataNotAvailableError(f"unknown dataset {name!r}; known: {sorted(_REMOTE)}")
    url = _resolve_url(spec)
    if not url:
        raise DataNotAvailableError(
            f"dataset {name!r} has no pinned download URL yet ({spec.note}). "
            f"Set {_env_url_var(name)} to fetch from a mirror. License: {spec.license}"
        )

    dest = cache_dir() / name
    if dest.exists() and not force:
        if not spec.sha256 or sha256_file(dest) == spec.sha256:
            return dest  # present and valid → idempotent no-op

    tmp = dest.with_name(dest.name + ".part")
    try:
        import urllib.request

        urllib.request.urlretrieve(url, tmp)  # noqa: S310 (registered/overridable url)
    except Exception as e:  # pragma: no cover - network
        tmp.unlink(missing_ok=True)
        raise DataNotAvailableError(f"could not fetch {name!r} from {url}: {e}") from e

    if spec.sha256:
        got = sha256_file(tmp)
        if got != spec.sha256:
            tmp.unlink(missing_ok=True)
            raise DataNotAvailableError(
                f"checksum mismatch for {name!r}: expected {spec.sha256}, got {got}"
            )
    tmp.replace(dest)  # atomic within the cache dir
    return dest
