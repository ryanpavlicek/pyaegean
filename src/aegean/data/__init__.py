"""Bundled-data access + a download-to-cache layer.

Compact text data ships in the wheel (read via importlib.resources). Large or
license-restricted assets — notably the 500 MB Linear A facsimile mirror — are
NOT bundled; they are fetched on demand from upstream into a user cache. This
is how the package stays small (the workbench's 500 MB problem can't recur).
"""

from __future__ import annotations

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
# we fetch (never re-host) it. The exact pinned release URL is wired in a
# follow-up (see roadmap / open question #5); until then fetch() reports clearly.
_REMOTE: dict[str, DataSpec] = {
    "lineara-images": DataSpec(
        name="lineara-images",
        url="",  # TODO: pin a ryanpavlicek/linearaworkbench release asset
        license="© École Française d'Athènes — academic reference only; not redistributed",
        note="~500 MB facsimile/photo mirror; download on demand from the workbench repo.",
    ),
}


def fetch(name: str, *, force: bool = False) -> pathlib.Path:
    """Download a registered remote dataset into the cache and return its path.

    Raises :class:`DataNotAvailableError` for unknown datasets, un-pinned URLs,
    or network failures — never silently, and never blocking ``import``.
    """
    spec = _REMOTE.get(name)
    if spec is None:
        raise DataNotAvailableError(
            f"unknown dataset {name!r}; known: {sorted(_REMOTE)}"
        )
    if not spec.url:
        raise DataNotAvailableError(
            f"dataset {name!r} has no pinned download URL yet "
            f"({spec.note}). License: {spec.license}"
        )
    dest = cache_dir() / name
    if dest.exists() and not force:
        return dest
    try:
        import urllib.request

        urllib.request.urlretrieve(spec.url, dest)  # noqa: S310 (trusted url)
    except Exception as e:  # pragma: no cover - network
        raise DataNotAvailableError(
            f"could not fetch {name!r} from {spec.url}: {e}"
        ) from e
    return dest
