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
    extract: bool = False  # when True, the download is a tar archive to unpack


# Remote datasets. pyaegean never re-hosts data; it fetches from the upstream
# host. The Linear A facsimile imagery is fetched (not copied) from a release on
# the ryanpavlicek/linearaworkbench repo, where the owner already hosts it. The
# images remain © École Française d'Athènes plus other rightsholders (the
# corpus's per-image `imageRights` are a patchwork — GORILA/EFA, named scholars,
# photographers); that attribution is unaffected by fetching. The URL/sha256 are
# pinned once the owner publishes the release asset; until then,
# PYAEGEAN_LINEARA_IMAGES_URL points the fetcher at any licensed copy.
_REMOTE: dict[str, DataSpec] = {
    "lineara-images": DataSpec(
        name="lineara-images",
        url=(
            "https://github.com/ryanpavlicek/linearaworkbench/releases/download/"
            "lineara-images-v1/lineara-images.tar.gz"
        ),
        sha256="d79e262857177bd22effba97baafdb4a31db06168f1ca1ce94b65266bcdf038d",
        license="© École Française d'Athènes and other rightsholders — academic reference only",
        note="3,368 facsimile/photo files (tar.gz) under images/; fetched from the linearaworkbench release.",
        extract=True,
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


def _download(url: str, dest_part: pathlib.Path, name: str) -> None:
    try:
        import urllib.request

        urllib.request.urlretrieve(url, dest_part)  # noqa: S310 (registered/overridable url)
    except Exception as e:  # pragma: no cover - network
        dest_part.unlink(missing_ok=True)
        raise DataNotAvailableError(f"could not fetch {name!r} from {url}: {e}") from e


def _verify(path: pathlib.Path, sha256: str, name: str) -> None:
    if sha256:
        got = sha256_file(path)
        if got != sha256:
            path.unlink(missing_ok=True)
            raise DataNotAvailableError(
                f"checksum mismatch for {name!r}: expected {sha256}, got {got}"
            )


def _safe_extract_tar(archive: pathlib.Path, dest: pathlib.Path) -> None:
    """Extract a tar archive, refusing any member that escapes ``dest``."""
    import tarfile

    root = dest.resolve()
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise DataNotAvailableError(f"unsafe path in archive: {member.name!r}")
        try:
            tf.extractall(root, filter="data")  # py3.12+ hardening
        except TypeError:  # pragma: no cover - older Python
            tf.extractall(root)


def fetch(name: str, *, force: bool = False) -> pathlib.Path:
    """Download a registered remote dataset into the cache and return its path.

    Verifies the sha256 when one is pinned, downloads atomically, and is a no-op
    when the cache already holds it. For ``extract`` datasets the download is a
    tar archive that is unpacked into a cache directory (returned); otherwise the
    downloaded file path is returned. Raises :class:`DataNotAvailableError` for
    unknown datasets, un-pinned URLs, checksum mismatches, unsafe archives, or
    network failures — never silently, and never blocking ``import``.
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
    # The pinned sha256 describes the pinned URL only. When the URL is overridden
    # via the env var (a user's own licensed copy), don't enforce it.
    sha256 = "" if os.environ.get(_env_url_var(name)) else spec.sha256

    if spec.extract:
        return _fetch_and_extract(url, name, force, sha256)

    dest = cache_dir() / name
    if dest.exists() and not force:
        if not sha256 or sha256_file(dest) == sha256:
            return dest  # present and valid → idempotent no-op
    tmp = dest.with_name(dest.name + ".part")
    _download(url, tmp, name)
    _verify(tmp, sha256, name)
    tmp.replace(dest)  # atomic within the cache dir
    return dest


def _fetch_and_extract(
    url: str, name: str, force: bool, sha256: str
) -> pathlib.Path:
    import shutil

    target = cache_dir() / name  # a directory of unpacked files
    if target.exists() and not force:
        return target  # already unpacked → idempotent no-op

    archive = cache_dir() / (name + ".part")
    _download(url, archive, name)
    _verify(archive, sha256, name)  # removes the archive on mismatch + raises

    staging = cache_dir() / (name + ".extract")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        _safe_extract_tar(archive, staging)
    finally:
        archive.unlink(missing_ok=True)
    if target.exists():
        shutil.rmtree(target)
    staging.replace(target)  # atomic within the cache dir
    return target
