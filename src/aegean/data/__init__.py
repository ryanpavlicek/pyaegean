"""Bundled-data access + a download-to-cache layer.

Compact text data ships in the wheel (read via importlib.resources). Large or
license-restricted assets — notably the Linear A facsimile mirror (~116 MB) — are
NOT bundled; they are fetched on demand from upstream into a user cache. This
is how the package stays small regardless of how large the source corpora are.
The "cache" is a permanent local store, not an evicting one: a fetched dataset
is downloaded once in full and stays on disk (never re-fetched, evicted, or
expired) until you remove it (``aegean data remove``).

Downloads are sha256-verified (when a checksum is pinned), atomic (written to a
``.part`` file then renamed), idempotent (a present, valid cache file is a
no-op), and resumable: a transfer cut off by a network failure keeps its
``.part`` file, and the next attempt (an in-call retry, or a later ``fetch``)
continues from the bytes already on disk via an HTTP Range request rather than
restarting a multi-hundred-MB asset from zero. A dataset's URL can be
overridden without a code change via
``PYAEGEAN_<NAME>_URL`` (e.g. ``PYAEGEAN_LINEARA_IMAGES_URL``), so a researcher
can point at their own mirror before an official release is pinned.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files
from typing import IO, Any


class DataNotAvailableError(RuntimeError):
    """Raised when a non-bundled dataset has not been fetched (or can't be)."""


def _bundled_bytes(*parts: str) -> bytes:
    return files("aegean.data").joinpath("bundled", *parts).read_bytes()


def load_bundled_json(*parts: str) -> Any:
    """Load a JSON file shipped inside the wheel, e.g.
    ``load_bundled_json("lineara", "signs.json")``."""
    return json.loads(_bundled_bytes(*parts).decode("utf-8"))


def cache_dir() -> pathlib.Path:
    """Where fetched datasets are stored (override with ``PYAEGEAN_CACHE``).

    A permanent local store, not an evicting cache: entries stay until
    explicitly removed (``aegean data remove``, or deleting this directory)."""
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
    # The cache-relative name(s) a present copy of this dataset actually occupies
    # on disk. Empty means the default: one entry at ``cache_dir()/name`` (a file,
    # or a directory for ``extract`` datasets). Some datasets land elsewhere: the
    # prebuilt lexicon indexes are fetched then written under their built-index
    # filename (``lsj-perseus-index.json.gz``, not ``lsj-index``), and the
    # ``agdt-derived`` bundle's members are copied out to their own filenames
    # (``agdt-postagger.json.gz`` etc.). Listing those real names here is what lets
    # ``aegean data list`` / ``aegean doctor`` see a dataset that a backend fetched.
    on_disk: tuple[str, ...] = ()


# Remote datasets, all fetched to the user cache on demand — never bundled in the
# Apache-2.0 wheel. Two hosting patterns:
#   * upstream-fetched: pulled straight from where the rights-holder publishes it
#     (the Linear A facsimile imagery comes from the ryanpavlicek/linearaworkbench
#     release; the images remain © École Française d'Athènes plus other
#     rightsholders, unaffected by fetching);
#   * project-hosted: datasets/artifacts this project derived or decoded under the
#     source license and republishes as clearly-labeled pyaegean release assets —
#     the DAMOS and SigLA corpora (CC BY-NC-SA 4.0; the NC+SA obligations pass to
#     the user) and the prebuilt LSJ index / AGDT-derived models (CC BY-SA).
# Every URL + sha256 is pinned below; each PYAEGEAN_<NAME>_URL env var overrides a
# source with your own licensed copy.
_REMOTE: dict[str, DataSpec] = {
    "lineara-images": DataSpec(
        name="lineara-images",
        url=(
            "https://github.com/ryanpavlicek/linearaworkbench/releases/download/"
            "lineara-images-v1/lineara-images.tar.gz"
        ),
        sha256="1afddcd0fc8ce4f3058e8f84d5589e7fb34f56ea615bf0c228d1b2c92722e396",
        license="© École Française d'Athènes and other rightsholders — academic reference only",
        note="3,368 facsimile/photo files (~116 MB tar.gz, ~119 MB unpacked); fetched from the linearaworkbench release.",
        extract=True,
    ),
    # The opt-in [neural] Greek lemmatizer model: GreTa seq2seq exported to ONNX, plus its
    # tokenizer and a gold form->lemma lookup, packed as a tar.gz. Derived from CC BY-SA
    # corpora, so the *model* is CC BY-SA; it is fetched (never bundled), so the wheel stays
    # Apache-2.0. URL is pinned to the grc-lemma-neural-v1 release asset; set
    # PYAEGEAN_GRC_LEMMA_NEURAL_URL to fetch from your own mirror instead.
    "grc-lemma-neural": DataSpec(
        name="grc-lemma-neural",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lemma-neural-v1/grc-lemma-neural.tar.gz"
        ),
        sha256="38126872e7a5be6389054062d4789ce5b6fc7e84327b07c2b93649a6f0f1a228",
        license="CC BY-SA 4.0 — derived from AGDT (CC BY-SA 3.0), Pedalion (CC BY-SA 4.0), Gorman (CC BY-SA 4.0)",
        note="GreTa seq2seq lemmatizer (int8 ONNX encoder/decoder + tokenizer + gold lookup), ~232 MB tar.gz; the [neural] extra.",
        extract=True,
    ),
    # The opt-in [neural] joint Greek pipeline: one GreBerta-based model for UPOS, the
    # 9-position AGDT morphology (rendered as UD FEATS), UD dependency trees (biaffine +
    # MST), and lemmas (edit-script head + train-only lookup). Trained leakage-clean on
    # AGDT + Gorman + Pedalion; the best published result on every UD Ancient Greek (Perseus) test metric
    # (docs/benchmarks.md). URL is pinned to the grc-joint-v3 release asset; set
    # PYAEGEAN_GRC_JOINT_URL to fetch from your own mirror instead.
    "grc-joint": DataSpec(
        name="grc-joint",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-joint-v3/grc-joint.tar.gz"
        ),
        sha256="f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e",
        license="CC BY-SA 4.0 — derived from AGDT (CC BY-SA 3.0), Gorman (CC BY-SA 4.0), Pedalion (CC BY-SA 4.0)",
        note="joint tagger-parser-lemmatizer (int8-weight + fp16 ONNX + tokenizer + label maps + lemma scripts/lookup), ~173 MB tar.gz; the [neural] extra (onnxruntime>=1.23).",
        extract=True,
    ),
    # Prebuilt Perseus LSJ lemma index (built by greek.lexicon.build_index from
    # PerseusDL/lexica). Hosting the ~15 MB built index lets use_lsj() skip the
    # ~270 MB TEI download + local build. CC BY-SA 4.0 (Perseus); never bundled.
    "lsj-index": DataSpec(
        name="lsj-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "lsj-index-v1/lsj-perseus-index.json.gz"
        ),
        sha256="12b7fdb741e98d63fd29c9a0e2a1a56c774bfac2f6c81139f113ffb96aaebee5",
        license="CC BY-SA 4.0 (Perseus Digital Library); derived index, fetched, never bundled",
        note="prebuilt LSJ lemma→entry index (~15 MB); use_lsj() prefers it over the 270 MB build.",
        extract=False,
        # use_lsj() writes the fetched index under greek.lexicon's built-index name.
        on_disk=("lsj-perseus-index.json.gz",),
    ),
    "middle-liddell-index": DataSpec(
        name="middle-liddell-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lexica-v1/middle-liddell-index.json.gz"
        ),
        sha256="8c4481f5b4252ac1cfdc4d11087e52be35408a720cfe72ae9815adecc74cde4f",
        license="public domain (1889); Perseus digitization CC BY-SA, Scaife data MIT; derived index, fetched, never bundled",
        note="prebuilt Middle Liddell lemma→entry index (~2.3 MB); use_lexicon('middle-liddell') prefers it.",
        extract=False,
        on_disk=("middle-liddell-index.json.gz",),
    ),
    "cunliffe-index": DataSpec(
        name="cunliffe-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lexica-v1/cunliffe-index.json.gz"
        ),
        sha256="3e3f0d9d9bfd89e609090aafff833041feb0e4421485e1fada14e1f338974608",
        license="public domain (1924); Scaife structured data MIT; derived index, fetched, never bundled",
        note="prebuilt Cunliffe (Homeric) lemma→entry index (~1.3 MB); use_lexicon('cunliffe') prefers it.",
        extract=False,
        on_disk=("cunliffe-index.json.gz",),
    ),
    "abbott-smith-index": DataSpec(
        name="abbott-smith-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lexica-v1/abbott-smith-index.json.gz"
        ),
        sha256="abfa896ecb196e7cae840bc8fd1f549271849dc36e6d140df236ffeec9297507",
        license="public domain (1922); derived index, fetched, never bundled",
        note="prebuilt Abbott-Smith (NT) lemma→entry index (~130 KB); use_lexicon('abbott-smith') prefers it.",
        extract=False,
        on_disk=("abbott-smith-index.json.gz",),
    ),
    # Prebuilt AGDT-derived artifacts: the treebank lexicon + the trained POS
    # tagger / lemmatizer / arc-eager parser. Hosting them lets the use_treebank/
    # use_tagger/use_lemmatizer/use_parser backends skip the 75 MB AGDT download
    # and minutes of training. CC BY-SA 3.0-derived (Perseus AGDT); never bundled.
    "agdt-derived": DataSpec(
        name="agdt-derived",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "agdt-derived-v1/agdt-derived.tar.gz"
        ),
        sha256="fb559b77a15146a51e34df5e9e2e5952347af086253282a25e8efcf65f8ba363",
        license="CC BY-SA 3.0 (derived from the Perseus AGDT); fetched, never bundled",
        note="prebuilt AGDT lexicon + tagger/lemmatizer/parser models; the opt-in "
             "Greek backends prefer these over downloading the AGDT and training.",
        extract=True,
        # fetch() unpacks the bundle to cache_dir()/agdt-derived, but the
        # use_treebank/use_tagger/use_lemmatizer/use_parser backends copy each
        # member out to its own working filename; any of these means the bundle
        # is present. (agdt-greek/ is the raw-AGDT build subdir, kept separate.)
        on_disk=(
            "agdt-derived",
            "agdt-greek-lexicon.json",
            "agdt-postagger.json.gz",
            "agdt-lemmatizer.json.gz",
            "agdt-parser-model.json.gz",
        ),
    ),
    # The SigLA-derived Linear A dataset (Salgarella & Castellan, sigla.phis.me):
    # decoded from the published web-app payload into the JSON the SigLA paper
    # describes (scripts/build_sigla_corpus.py). CC BY-NC-SA 4.0 as published by
    # SigLA — NonCommercial data is fetched on demand and never bundled in the
    # Apache-2.0 wheel; attribution/citation live in the file's _meta and NOTICE.
    "sigla-corpus": DataSpec(
        name="sigla-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "sigla-corpus-v2/sigla-corpus.json"
        ),
        sha256="c334a9431aa985afa9655268e018efc7513c2d3aea0541ca96afffe61e29b133",
        license="CC BY-NC-SA 4.0 (SigLA — Salgarella & Castellan; NonCommercial, never bundled)",
        note="SigLA-derived Linear A dataset v2: 781 documents with SigLA's own word "
             "division (1,376 words) and commodity ideograms (~1.2 MB JSON). Drawings "
             "stay at sigla.phis.me.",
        extract=False,
    ),
    # The DAMOS Linear B corpus (Aurora, damos.hf.uio.no): transliterations + core
    # metadata for ~5,900 Mycenaean tablets, decoded from the DAMOS public API into
    # compact JSON (scripts/build_damos_corpus.py). CC BY-NC-SA 4.0 as published by
    # DAMOS — NonCommercial data fetched on demand, never bundled in the Apache-2.0
    # wheel; attribution/citation in the file's _meta and NOTICE.
    "damos-corpus": DataSpec(
        name="damos-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "damos-corpus-v2/damos-corpus.json"
        ),
        sha256="eab9ccdfc4324b62f015bccd5e3f917f256cab8c058840842127eadecfbca2d2",
        license="CC BY-NC-SA 4.0 (DAMOS — F. Aurora; NonCommercial, never bundled)",
        note="DAMOS-derived Linear B corpus v2: ~5,900 tablets (Knossos, Pylos, Thebes, …) "
             "with transliterations, site/chronology, scribal hands, find context, and "
             "object class. Loadable via aegean.load('damos').",
        extract=False,
    ),
    # The Greek New Testament (Nestle 1904) with per-token lemma / Robinson morph /
    # Strong's, built from biblicalhumanities/Nestle1904 (scripts/build_nt_corpus.py).
    # The morphology, lemmas, and Strong's numbers are CC0 and the base text is public
    # domain, so — unlike DAMOS/SigLA — this asset MAY be redistributed; the full 27 books
    # fetch on demand while one book is bundled as an offline sample (load_nt). sha256 is
    # set PYAEGEAN_NT_CORPUS_URL to a local build to override the hosted asset, or use
    # the bundled sample offline.
    "nt-corpus": DataSpec(
        name="nt-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "nt-corpus-v1/nt-corpus.json"
        ),
        sha256="e7aa5dcad729eb91f77018abbef71304d13e200f29dabe1260b79fa37b153949",
        license="CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain",
        note="Greek New Testament (Nestle 1904): 260 chapters / ~137,800 tokens with gold "
             "lemma, Robinson morph, Strong's, and reconciled UD UPOS. Loadable via "
             "aegean.load('nt') / greek.load_nt(book, ref=...).",
        extract=False,
    ),
    # The prebuilt Linear A Research Workbench static web app (the browser UI), hosted as a
    # release asset on the workbench repo and served locally by `aegean workbench`. The app
    # build is Apache-2.0; the Linear A corpus data baked into it is GORILA-derived (via
    # lineara.xyz). Fetched + extracted to the cache on demand, never bundled.
    "workbench-app": DataSpec(
        name="workbench-app",
        url=(
            "https://github.com/ryanpavlicek/linearaworkbench/releases/download/"
            "workbench-app-v1.6.1/workbench-app.tar.gz"
        ),
        sha256="19a27feb47a9b49a4095c571e7f1e01c68f011a119691712438273d289c19870",
        license="Apache-2.0 (Linear A Research Workbench build); embedded Linear A data is GORILA-derived",
        note="prebuilt linearaworkbench static web app (~3 MB tar.gz); served locally by `aegean workbench`.",
        extract=True,
    ),
    # A user-supplied Linear B corpus override (bring-your-own). DAMOS is now loadable
    # directly via aegean.load("damos"); this remains for a local licensed export (e.g.
    # a LiBER selection or a DAMOS EpiDoc download) via PYAEGEAN_LINEARB_CORPUS.
    "linearb-corpus": DataSpec(
        name="linearb-corpus",
        url="",
        sha256="",
        license="bring-your-own; DAMOS is CC BY-NC-SA 4.0 and LiBER all-rights-reserved — neither redistributed",
        note="A user-supplied Linear B corpus export (e.g. a DAMOS EpiDoc download). No default source.",
        extract=False,
    ),
}


def _dir_bytes(path: pathlib.Path) -> int:
    """Recursive size of a store path (a file's own size, or a directory's files).

    A file that vanishes between the directory walk and its ``stat`` (a racing
    fetch/remove) is skipped rather than raising, so the other files still count."""
    try:
        is_dir = path.is_dir()
    except OSError:
        return 0
    if is_dir:
        total = 0
        try:
            children = list(path.rglob("*"))
        except OSError:
            return 0
        for f in children:
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue  # vanished mid-walk
        return total
    try:
        return path.stat().st_size
    except OSError:
        return 0


def on_disk_paths(spec: DataSpec, root: pathlib.Path) -> list[pathlib.Path]:
    """The cache paths that would exist if ``spec`` is present, whether or not
    they do. Defaults to a single ``root/name`` entry (the ``fetch`` path); a
    ``spec.on_disk`` override lists the real artifact names for datasets a
    backend writes under a different filename (the prebuilt lexicon indexes,
    the ``agdt-derived`` members). See `DataSpec.on_disk`."""
    names = spec.on_disk or (spec.name,)
    return [root / n for n in names]


def present_paths(spec: DataSpec, root: pathlib.Path) -> list[pathlib.Path]:
    """Which of ``spec``'s on-disk artifacts actually exist under ``root``."""
    return [p for p in on_disk_paths(spec, root) if p.exists()]


def is_downloaded(spec: DataSpec, root: pathlib.Path) -> bool:
    """Whether any real on-disk artifact of ``spec`` is present under ``root``.

    This is the corrected downloaded-probe: a dataset a backend fetched under a
    different filename (``lsj-index`` -> ``lsj-perseus-index.json.gz``, an
    ``agdt-derived`` member) counts as downloaded, where a bare
    ``(root/name).exists()`` check missed it."""
    return bool(present_paths(spec, root))


def downloaded_bytes(spec: DataSpec, root: pathlib.Path) -> int:
    """Total real on-disk size of ``spec``'s present artifacts (0 if none)."""
    return sum(_dir_bytes(p) for p in present_paths(spec, root))


def bundled_data_version() -> str:
    """The version of the bundled datasets.

    Bundled data ships inside the wheel and is immutable for a given release, so
    its version *is* the package version; `versions` gives per-file sha256s."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("pyaegean")
    except PackageNotFoundError:  # pragma: no cover — running from an uninstalled tree
        return "0.0.0+unknown"


def versions() -> dict[str, Any]:
    """A reproducibility manifest of every dataset pyaegean can touch.

    Returns ``{"package": …, "bundled": {…}, "fetched": {…}}``: each bundled
    JSON file with its sha256 + size (hashed from the installed wheel contents),
    and each registered fetchable asset with its pinned URL/sha256, license, and
    whether it is present in the local cache.

    **Pinning for papers**: record ``aegean.__version__`` and this manifest
    (e.g. ``json.dump(aegean.data.versions(), f)``) alongside your results;
    anyone with the same package version and matching sha256s is analyzing
    byte-identical data. Fetched assets are sha256-verified on download, so a
    matching pin in this manifest *is* the byte-level guarantee.

    When a dataset's URL is env-overridden (``PYAEGEAN_<NAME>_URL``, a user's own
    mirror), ``fetch`` does not enforce the pinned sha256 against that other
    source, so the manifest reports ``sha256_enforced: false`` and blanks the
    ``sha256`` for that entry: it would be dishonest to advertise a checksum the
    download did not verify."""
    import hashlib

    bundled: dict[str, dict[str, Any]] = {}
    root = files("aegean.data").joinpath("bundled")
    for sub in sorted(root.iterdir(), key=lambda t: t.name):
        if not sub.is_dir():
            continue
        for f in sorted(sub.iterdir(), key=lambda t: t.name):
            if f.name.endswith(".json"):
                blob = f.read_bytes()
                bundled[f"{sub.name}/{f.name}"] = {
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "bytes": len(blob),
                }
    root = cache_dir()
    fetched: dict[str, dict[str, Any]] = {}
    for name, spec in sorted(_REMOTE.items()):
        # fetch() disables sha256 verification when the URL is env-overridden, so
        # the pinned sha describes the pinned URL only. Report it as unenforced
        # (and blank the value) rather than advertise a sha the download skipped.
        overridden = bool(os.environ.get(_env_url_var(name)))
        enforced = bool(spec.sha256) and not overridden
        fetched[name] = {
            "url": _resolve_url(spec),
            "sha256": spec.sha256 if enforced else "",
            "sha256_enforced": enforced,
            "url_overridden": overridden,
            "license": spec.license,
            "cached": is_downloaded(spec, root),
        }
    return {"package": bundled_data_version(), "bundled": bundled, "fetched": fetched}


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


_DOWNLOAD_TIMEOUT = 30  # seconds per socket operation: a stall raises instead of hanging
_DOWNLOAD_ATTEMPTS = 3  # one initial transfer plus two in-call resume retries


def _part_info_path(dest_part: pathlib.Path) -> pathlib.Path:
    """The sidecar recording what a resume needs to validate a kept ``.part``."""
    return dest_part.with_name(dest_part.name + ".info")


def _read_part_info(dest_part: pathlib.Path) -> dict[str, Any]:
    try:
        raw = json.loads(_part_info_path(dest_part).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _record_part_info(dest_part: pathlib.Path, headers: Any, *, total: int | None) -> None:
    """Persist the remote's full byte length and validators next to the ``.part``,
    so a later resume can tell a continuable download from a stale one (the
    remote was republished under the same URL)."""
    info = {
        "length": total,
        "etag": headers.get("ETag") if headers is not None else None,
        "last_modified": headers.get("Last-Modified") if headers is not None else None,
    }
    try:
        if all(v is None for v in info.values()):
            # Nothing to validate a resume against: drop any sidecar from an
            # earlier transfer so it can never describe bytes it did not watch
            # being written.
            _part_info_path(dest_part).unlink(missing_ok=True)
            return
        _part_info_path(dest_part).write_text(json.dumps(info), encoding="utf-8")
    except OSError:  # the sidecar is best-effort; never fail a download over it
        pass


def _discard_part(dest_part: pathlib.Path) -> None:
    dest_part.unlink(missing_ok=True)
    _part_info_path(dest_part).unlink(missing_ok=True)


def _parse_content_range(value: str | None) -> tuple[int | None, int | None]:
    """``(start, total)`` from a Content-Range header, e.g. ``bytes 500-999/1000``
    or ``bytes */1000``; ``None`` where absent or unknown (``*``)."""
    if not value:
        return None, None
    parts = value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bytes":
        return None, None
    range_part, _, total_part = parts[1].partition("/")
    total = int(total_part) if total_part.strip().isdigit() else None
    start_str = range_part.strip().partition("-")[0].strip()
    start = int(start_str) if start_str.isdigit() else None
    return start, total


def _expected_length(headers: Any) -> int | None:
    value = headers.get("Content-Length") if headers is not None else None
    try:
        return int(str(value).strip()) if value is not None else None
    except ValueError:
        return None


class FetchAborted(DataNotAvailableError):
    """Raised when a fetch is canceled through its ``abort`` hook (e.g. the TUI's
    download worker being cancelled). The ``.part`` file is kept, so a later fetch
    resumes instead of restarting."""


def _stream_body(resp: Any, out: IO[bytes], abort: Callable[[], bool] | None = None) -> None:
    """Chunked copy (a 500 MB asset never sits in memory) that raises when the
    body ends short of its declared Content-Length. ``read(amt)`` returns short
    silently when the connection drops, so without this check a truncated
    transfer would look complete and be thrown away at sha256 verification
    instead of kept for resume. ``abort`` is polled between chunks; when it goes
    true the transfer stops with `FetchAborted` (the ``.part`` stays resumable)."""
    import http.client

    expected = _expected_length(getattr(resp, "headers", None))
    written = 0
    while True:
        if abort is not None and abort():
            raise FetchAborted("fetch canceled")
        chunk = resp.read(1 << 20)
        if not chunk:
            break
        out.write(chunk)
        written += len(chunk)
    if expected is not None and written < expected:
        raise http.client.IncompleteRead(b"", expected - written)


def _write_from_zero(
    resp: Any, dest_part: pathlib.Path, abort: Callable[[], bool] | None = None
) -> None:
    """Stream a full-body response into a fresh ``.part``, recording resume
    metadata first so a mid-stream failure leaves a continuable file behind."""
    headers = getattr(resp, "headers", None)
    _record_part_info(dest_part, headers, total=_expected_length(headers))
    with open(dest_part, "wb") as out:
        _stream_body(resp, out, abort)


def _download_full(
    url: str, dest_part: pathlib.Path, abort: Callable[[], bool] | None = None
) -> None:
    import urllib.request

    resp = urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT)  # noqa: S310 (registered/overridable url)
    with resp:
        _write_from_zero(resp, dest_part, abort)


def _download_once(
    url: str, dest_part: pathlib.Path, abort: Callable[[], bool] | None = None
) -> None:
    """One transfer attempt: resume an existing ``.part`` with an HTTP Range
    request when the scheme supports it (GitHub's release CDN does), falling
    back to a clean restart from byte zero on any staleness signal: the server
    ignored Range, the offset is not satisfiable, or the remote's size or
    validators no longer match what the ``.part`` was downloaded from."""
    import urllib.error
    import urllib.parse
    import urllib.request

    offset = 0
    if urllib.parse.urlsplit(url).scheme.lower() in ("http", "https") and dest_part.exists():
        offset = dest_part.stat().st_size
    if offset <= 0:
        # Nothing to resume, or a file:// URL (the env-override / test path),
        # where Range is not meaningful and a restart is cheap.
        _download_full(url, dest_part, abort)
        return

    info = _read_part_info(dest_part)
    req_headers = {"Range": f"bytes={offset}-"}
    validator = info.get("etag") or info.get("last_modified")
    if isinstance(validator, str) and validator and not validator.startswith("W/"):
        # If the remote changed since the .part was written, If-Range makes the
        # server answer 200 with the full new body instead of a mismatched 206.
        req_headers["If-Range"] = validator
    req = urllib.request.Request(url, headers=req_headers)  # noqa: S310 (registered/overridable url)
    try:
        resp = urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT)  # noqa: S310
    except urllib.error.HTTPError as e:
        if e.code != 416:
            raise
        # 416 Range Not Satisfiable: the .part is either already complete or
        # stale (a remote that shrank). Complete means our offset equals the
        # total the server reports; anything else restarts from zero.
        hdrs = getattr(e, "headers", None)
        _, total = _parse_content_range(hdrs.get("Content-Range") if hdrs is not None else None)
        if total is not None and total == offset:
            return  # fully downloaded; sha256 verification has the final word
        _discard_part(dest_part)
        _download_full(url, dest_part, abort)
        return

    with resp:
        if getattr(resp, "status", None) == 206:
            start, total = _parse_content_range(resp.headers.get("Content-Range"))
            recorded = info.get("length")
            consistent = (
                start == offset
                and not (total is not None and total < offset)
                and not (isinstance(recorded, int) and total is not None and recorded != total)
            )
            if consistent:
                _record_part_info(dest_part, resp.headers, total=total)
                with open(dest_part, "ab") as out:
                    _stream_body(resp, out, abort)
                return
            # The remote changed under the .part (its total drifted from what
            # was recorded, or the server answered a different offset): fall
            # through to a clean restart from byte zero.
        else:
            # 200: the server ignored Range, or If-Range flagged a changed
            # remote, and it is sending the whole file. Write from byte zero.
            _write_from_zero(resp, dest_part, abort)
            return
    _discard_part(dest_part)
    _download_full(url, dest_part, abort)


def _download(
    url: str,
    dest_part: pathlib.Path,
    name: str,
    abort: Callable[[], bool] | None = None,
) -> None:
    """Download ``url`` to ``dest_part``, resuming interrupted transfers.

    A transient network failure (a stall past the timeout, a dropped or
    truncated connection) keeps the ``.part`` file and is retried up to two
    more times within this call, each retry resuming from the bytes already on
    disk; a ``.part`` left behind by an exhausted call is picked up the same
    way by the next `fetch`. Failures that mean the content itself is wrong
    (an HTTP status error here, a checksum mismatch downstream) discard the
    ``.part`` instead. The caller verifies the assembled file's sha256 and
    performs the atomic rename, so nothing partial is ever visible at the
    final path.
    """
    import http.client
    import urllib.error

    last_exc: Exception | None = None
    for _ in range(_DOWNLOAD_ATTEMPTS):
        try:
            _download_once(url, dest_part, abort)
        except FetchAborted:
            raise  # deliberate cancel: keep the .part so a later fetch resumes it
        except urllib.error.HTTPError as e:
            # A status error (403, 404, ...) means the resource is wrong or
            # gone; no kept .part could assemble into the right file.
            _discard_part(dest_part)
            raise DataNotAvailableError(f"could not fetch {name!r} from {url}: {e}") from e
        except (http.client.HTTPException, OSError) as e:
            last_exc = e  # network-class: keep the .part and resume
        except Exception as e:
            _discard_part(dest_part)
            raise DataNotAvailableError(f"could not fetch {name!r} from {url}: {e}") from e
        else:
            _part_info_path(dest_part).unlink(missing_ok=True)
            return
    raise DataNotAvailableError(
        f"could not fetch {name!r} from {url} after {_DOWNLOAD_ATTEMPTS} attempts "
        f"(partial download kept; retrying will resume it): {last_exc}"
    ) from last_exc


def _verify(path: pathlib.Path, sha256: str, name: str) -> None:
    if sha256:
        got = sha256_file(path)
        if got != sha256:
            path.unlink(missing_ok=True)
            raise DataNotAvailableError(
                f"checksum mismatch for {name!r}: expected {sha256}, got {got}"
            )


def download_file(url: str, dest: pathlib.Path, *, sha256: str = "") -> pathlib.Path:
    """Download a single URL to ``dest`` atomically (a ``.part`` temp then rename),
    optionally sha256-verified. A transfer cut off by a network failure keeps
    its ``.part``, and the next call resumes it with an HTTP Range request.
    Returns ``dest``; raises `DataNotAvailableError` on a network failure or
    checksum mismatch. Shared by `fetch` and the on-demand dataset downloaders
    (e.g. the Greek treebank)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    _download(url, tmp, dest.name)
    _verify(tmp, sha256, dest.name)
    tmp.replace(dest)  # atomic within the directory
    return dest


def _safe_extract_tar(archive: pathlib.Path, dest: pathlib.Path) -> None:
    """Extract a tar archive, refusing any member (or link target) that escapes ``dest``."""
    import tarfile

    root = dest.resolve()
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise DataNotAvailableError(f"unsafe path in archive: {member.name!r}")
            if member.issym() or member.islnk():
                # A symlink target is relative to the link's own directory; a hard link
                # (or an absolute target) resolves from the extraction root.
                base = target.parent if member.issym() else root
                linked = (base / member.linkname).resolve()
                if linked != root and root not in linked.parents:
                    raise DataNotAvailableError(
                        f"unsafe link target in archive: {member.name!r} -> {member.linkname!r}"
                    )
        try:
            tf.extractall(root, filter="data")  # py3.12+ hardening
        except TypeError:  # pragma: no cover - older Python
            tf.extractall(root)


# Concurrent fetches of the SAME dataset (two threads, two processes, a doctor/TUI
# poll racing a CLI fetch) must not share the .part file or the .extract staging dir:
# a second writer appending at a moving EOF corrupts the transfer, and a second
# extractor rmtree-ing the staging mid-extraction breaks the first. One advisory
# lock file per dataset serializes them; the loser waits, then finds the winner's
# artifact via the normal idempotence check.
_LOCK_STALE_S = 3600.0  # a holder that has been silent this long is presumed dead
_LOCK_POLL_S = 0.5


class _DatasetLock:
    def __init__(self, name: str) -> None:
        self._path = cache_dir() / (name + ".lock")

    def __enter__(self) -> "_DatasetLock":
        import time

        while True:
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self._path.stat().st_mtime
                except OSError:
                    continue  # the holder released between exists and stat: retry
                if age > _LOCK_STALE_S:
                    # the holder died without releasing: break the stale lock
                    self._path.unlink(missing_ok=True)
                    continue
                time.sleep(_LOCK_POLL_S)
                continue
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            os.close(fd)
            return self

    def __exit__(self, *exc: object) -> None:
        self._path.unlink(missing_ok=True)


def fetch(
    name: str, *, force: bool = False, abort: Callable[[], bool] | None = None
) -> pathlib.Path:
    """Download a registered remote dataset into the cache and return its path.

    Verifies the sha256 when one is pinned, downloads atomically, and is a no-op
    when the cache already holds it. An interrupted download keeps its ``.part``
    file and the next call resumes from it (an HTTP Range request) instead of
    restarting from zero. For ``extract`` datasets the download is a
    tar archive that is unpacked into a cache directory (returned); otherwise the
    downloaded file path is returned. Concurrent fetches of the same dataset
    (other threads or processes) are serialized on a per-dataset lock: the later
    caller waits, then returns the completed artifact. ``abort`` is an optional
    zero-argument callable polled during the transfer; when it returns true the
    fetch stops with `FetchAborted`, keeping the partial file resumable (how the
    TUI cancels a download worker). Raises `DataNotAvailableError` for
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

    with _DatasetLock(name):
        if spec.extract:
            return _fetch_and_extract(url, name, force, sha256, abort)

        dest = cache_dir() / name
        if dest.exists() and not force:
            if not sha256 or sha256_file(dest) == sha256:
                return dest  # present and valid → idempotent no-op
        tmp = dest.with_name(dest.name + ".part")
        _download(url, tmp, name, abort)
        _verify(tmp, sha256, name)
        tmp.replace(dest)  # atomic within the cache dir
        return dest


def fetch_prebuilt(name: str, dest: pathlib.Path, *, member: str | None = None) -> bool:
    """Place a hosted prebuilt artifact at ``dest``; return ``True`` on success.

    Lets an opt-in backend prefer a small hosted index/model over a slow local
    build (a ~270 MB download, or minutes of training), while keeping
    build-from-source as the fallback: any failure — no pinned URL, network
    error, checksum mismatch — returns ``False`` instead of raising, so the
    caller proceeds to build. ``member`` names a file inside an ``extract``
    dataset's unpacked directory.
    """
    import shutil

    try:
        got = fetch(name)
    except DataNotAvailableError:
        return False
    src = got / member if member is not None else got
    if not src.exists():
        return False
    if src.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return True


def _fetch_and_extract(
    url: str, name: str, force: bool, sha256: str, abort: Callable[[], bool] | None = None
) -> pathlib.Path:
    import shutil

    target = cache_dir() / name  # a directory of unpacked files
    if target.exists() and not force:
        return target  # already unpacked → idempotent no-op

    archive = cache_dir() / (name + ".part")
    _download(url, archive, name, abort)
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
