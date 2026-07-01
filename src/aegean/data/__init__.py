"""Bundled-data access + a download-to-cache layer.

Compact text data ships in the wheel (read via importlib.resources). Large or
license-restricted assets — notably the Linear A facsimile mirror (~116 MB) — are
NOT bundled; they are fetched on demand from upstream into a user cache. This
is how the package stays small regardless of how large the source corpora are.

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
            "workbench-app-v1.5.4/workbench-app.tar.gz"
        ),
        sha256="3b18a14127d4b057394832a4fe29b0caaf3b5ac2df2a8fa39930c3416725e838",
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
    matching pin in this manifest *is* the byte-level guarantee."""
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
    fetched = {
        name: {
            "url": _resolve_url(spec),
            "sha256": spec.sha256,
            "license": spec.license,
            "cached": (cache_dir() / name).exists(),
        }
        for name, spec in sorted(_REMOTE.items())
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


def _download(url: str, dest_part: pathlib.Path, name: str) -> None:
    try:
        import shutil
        import urllib.request

        # A timeout so a stalled connection raises instead of hanging fetch() forever,
        # and a chunked copy so a 500 MB asset never sits in memory.
        resp = urllib.request.urlopen(url, timeout=30)  # noqa: S310 (registered/overridable url)
        with resp, open(dest_part, "wb") as out:
            shutil.copyfileobj(resp, out, length=1 << 20)
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


def download_file(url: str, dest: pathlib.Path, *, sha256: str = "") -> pathlib.Path:
    """Download a single URL to ``dest`` atomically (a ``.part`` temp then rename),
    optionally sha256-verified. Returns ``dest``; raises `DataNotAvailableError`
    on a network failure or checksum mismatch. Shared by `fetch` and the
    on-demand dataset downloaders (e.g. the Greek treebank)."""
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


def fetch(name: str, *, force: bool = False) -> pathlib.Path:
    """Download a registered remote dataset into the cache and return its path.

    Verifies the sha256 when one is pinned, downloads atomically, and is a no-op
    when the cache already holds it. For ``extract`` datasets the download is a
    tar archive that is unpacked into a cache directory (returned); otherwise the
    downloaded file path is returned. Raises `DataNotAvailableError` for
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
