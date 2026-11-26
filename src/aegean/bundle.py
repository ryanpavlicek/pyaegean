"""Portable, verifiable research bundles (``aegean-research-bundle/1``).

Packages a reproducible research snapshot into a single deterministic ``.zip``
archive with SHA-256 member verification, license-clean corpus handling,
citations, optional workbench workspace state, review tables (with editable
companion snapshots), and analysis receipts.

License-clean by construction: corpora carrying non-commercial (CC BY-NC*) or
restricted licenses are never embedded in redistributable bundles by default.
Instead, `create_bundle` records a retrieval pointer (`CorpusReference`) with
the dataset id, version, upstream URL, license, SHA-256, and filter spec so
`hydrate_bundle` can reconstruct the exact corpus under its upstream license.
Pass ``embed_corpus="always"`` for a private, non-redistributable archive
(which stamps ``redistributable=False`` in ``manifest.json``).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import posixpath
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ._atomic import atomic_path

if TYPE_CHECKING:
    from .core.corpus import Corpus
    from .io.workbench import WorkbenchBackup

__all__ = [
    "BUNDLE_FORMAT",
    "BundleManifest",
    "BundleMember",
    "BundleVerification",
    "CorpusReference",
    "ResearchBundle",
    "create_bundle",
    "extract_bundle",
    "hydrate_bundle",
    "inspect_bundle",
    "is_redistributable_license",
    "verify_bundle",
]

BUNDLE_FORMAT = "aegean-research-bundle/1"
_FIXED_ZIP_TIME: tuple[int, int, int, int, int, int] = (2026, 1, 1, 0, 0, 0)

_NON_REDISTRIBUTABLE_MARKERS: tuple[str, ...] = (
    "by-nc",
    "noncommercial",
    "non-commercial",
    "academic reference only",
    "all rights reserved",
    "restricted",
    "proprietary",
    "©",
)


def is_redistributable_license(license_text: str) -> bool:
    """Return ``False`` if ``license_text`` indicates NC or restricted terms."""
    low = (license_text or "").strip().lower()
    if not low:
        return True
    return not any(marker in low for marker in _NON_REDISTRIBUTABLE_MARKERS)


@dataclass(frozen=True, slots=True)
class CorpusReference:
    """Retrieval pointer for a non-embedded (or NC-licensed) corpus."""

    dataset: str
    version: str = ""
    script_id: str = ""
    sha256: str = ""
    url: str = ""
    license: str = ""
    filter_spec: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "version": self.version,
            "script_id": self.script_id,
            "sha256": self.sha256,
            "url": self.url,
            "license": self.license,
            "filter_spec": dict(self.filter_spec),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CorpusReference":
        raw_filter = data.get("filter_spec")
        return cls(
            dataset=str(data.get("dataset") or ""),
            version=str(data.get("version") or ""),
            script_id=str(data.get("script_id") or ""),
            sha256=str(data.get("sha256") or ""),
            url=str(data.get("url") or ""),
            license=str(data.get("license") or ""),
            filter_spec=dict(raw_filter) if isinstance(raw_filter, Mapping) else {},
        )


@dataclass(frozen=True, slots=True)
class BundleMember:
    """Manifest record for one file stored inside the zip bundle."""

    path: str
    sha256: str
    size: int
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BundleMember":
        return cls(
            path=str(data["path"]),
            sha256=str(data["sha256"]),
            size=int(data["size"]),
            kind=str(data.get("kind") or "file"),
        )


@dataclass(frozen=True, slots=True)
class BundleManifest:
    """Top-level manifest stored at ``manifest.json`` inside a research bundle."""

    format: str
    pyaegean_version: str
    created_at: str
    title: str
    description: str
    redistributable: bool
    license_notes: tuple[str, ...]
    corpus_embedded: bool
    corpus_ref: CorpusReference | None
    pipeline_config: dict[str, Any] | None
    members: tuple[BundleMember, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "pyaegean_version": self.pyaegean_version,
            "created_at": self.created_at,
            "title": self.title,
            "description": self.description,
            "redistributable": self.redistributable,
            "license_notes": list(self.license_notes),
            "corpus_embedded": self.corpus_embedded,
            "corpus_ref": self.corpus_ref.to_dict() if self.corpus_ref is not None else None,
            "pipeline_config": self.pipeline_config,
            "members": [m.to_dict() for m in self.members],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BundleManifest":
        fmt = str(data.get("format") or "")
        if fmt != BUNDLE_FORMAT:
            raise ValueError(f"unsupported bundle format {fmt!r}; expected {BUNDLE_FORMAT!r}")
        raw_ref = data.get("corpus_ref")
        corpus_ref = (
            CorpusReference.from_dict(raw_ref)
            if isinstance(raw_ref, Mapping)
            else None
        )
        raw_members = data.get("members")
        if not isinstance(raw_members, list):
            raise ValueError("bundle manifest is missing a 'members' list")
        members = tuple(
            BundleMember.from_dict(m) for m in raw_members if isinstance(m, Mapping)
        )
        raw_notes = data.get("license_notes")
        notes = (
            tuple(str(n) for n in raw_notes)
            if isinstance(raw_notes, list)
            else ()
        )
        raw_pipe = data.get("pipeline_config")
        return cls(
            format=fmt,
            pyaegean_version=str(data.get("pyaegean_version") or ""),
            created_at=str(data.get("created_at") or ""),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            redistributable=bool(data.get("redistributable", True)),
            license_notes=notes,
            corpus_embedded=bool(data.get("corpus_embedded", False)),
            corpus_ref=corpus_ref,
            pipeline_config=dict(raw_pipe) if isinstance(raw_pipe, Mapping) else None,
            members=members,
        )


@dataclass(frozen=True, slots=True)
class BundleVerification:
    """Result of verifying a research bundle archive's integrity and safety."""

    ok: bool
    path: str
    format: str
    redistributable: bool
    checked_members: int
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResearchBundle:
    """Hydrated in-memory representation of a research bundle."""

    manifest: BundleManifest
    corpus: "Corpus | None" = None
    workbench_state: "WorkbenchBackup | None" = None
    review_files: dict[str, Path] = field(default_factory=dict)
    receipts: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _canonical_json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_safe_member_path(name: str) -> bool:
    if not name or "\x00" in name:
        return False
    if name.startswith(("/", "\\")) or ":" in name:
        return False
    if "\\" in name:
        return False
    norm = posixpath.normpath(name)
    if norm in (".", "..") or norm.startswith("../") or "/../" in f"/{norm}/":
        return False
    return norm == name


def _is_symlink_zipinfo(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return (mode & 0o170000) == 0o120000


def _dataset_spec_metadata(dataset: str) -> tuple[str, str, str]:
    """Return ``(url, sha256, license)`` for a known remote dataset, or blanks."""
    from .data import _REMOTE

    spec = _REMOTE.get(dataset)
    if spec is None:
        return ("", "", "")
    return (spec.url, spec.sha256, spec.license)


def _build_citations(
    *,
    corpus: "Corpus | None",
    corpus_ref: CorpusReference | None,
    extra_citations: Sequence[Mapping[str, Any] | str],
) -> tuple[list[dict[str, Any]], str, str]:
    from . import __version__

    entries: list[dict[str, Any]] = [
        {
            "id": "pyaegean",
            "title": f"pyaegean v{__version__}",
            "url": "https://github.com/ryanpavlicek/pyaegean",
            "license": "Apache-2.0",
            "bibtex": (
                f"@software{{pyaegean,\n"
                f"  author  = {{Pavlicek, Ryan}},\n"
                f"  title   = {{pyaegean}},\n"
                f"  version = {{{__version__}}},\n"
                f"  url     = {{https://github.com/ryanpavlicek/pyaegean}},\n"
                f"}}"
            ),
            "text": f"Pavlicek, R. pyaegean (v{__version__}). https://github.com/ryanpavlicek/pyaegean",
        }
    ]

    if corpus is not None and corpus.provenance is not None:
        prov = corpus.provenance
        entries.append(
            {
                "id": "corpus-source",
                "title": prov.citation or prov.source,
                "url": prov.url,
                "license": prov.license,
                "bibtex": prov.bibtex(key="aegean-corpus"),
                "text": prov.apa(),
            }
        )
    elif corpus_ref is not None and corpus_ref.dataset:
        entries.append(
            {
                "id": f"dataset-{corpus_ref.dataset}",
                "title": f"pyaegean dataset {corpus_ref.dataset}"
                + (f" ({corpus_ref.version})" if corpus_ref.version else ""),
                "url": corpus_ref.url,
                "license": corpus_ref.license,
                "bibtex": (
                    f"@misc{{aegean-{corpus_ref.dataset},\n"
                    f"  title = {{{corpus_ref.dataset}}},\n"
                    f"  url   = {{{corpus_ref.url}}},\n"
                    f"  note  = {{License: {corpus_ref.license or 'see upstream'}}},\n"
                    f"}}"
                ),
                "text": f"{corpus_ref.dataset} — {corpus_ref.url} ({corpus_ref.license or 'see upstream'})",
            }
        )

    for idx, item in enumerate(extra_citations, 1):
        if isinstance(item, str):
            entries.append({"id": f"ref-{idx}", "text": item, "bibtex": ""})
        else:
            entries.append(dict(item))

    bib_chunks = [str(e["bibtex"]).strip() for e in entries if e.get("bibtex")]
    txt_chunks = [str(e.get("text") or e.get("title") or "").strip() for e in entries]
    bib = ("\n\n".join(c for c in bib_chunks if c) + "\n") if bib_chunks else ""
    txt = ("\n".join(c for c in txt_chunks if c) + "\n") if txt_chunks else ""
    return entries, bib, txt


def _serialize_pipeline_config(config: Any) -> dict[str, Any] | None:
    if config is None:
        return None
    if isinstance(config, Mapping):
        return dict(config)
    to_dict = getattr(config, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, Mapping):
            return dict(result)
    raise TypeError("pipeline_config must be a mapping or an object with .to_dict()")


def create_bundle(
    output: str | Path,
    *,
    corpus: "Corpus | None" = None,
    dataset: str | None = None,
    dataset_version: str = "",
    filter_spec: Mapping[str, Any] | None = None,
    title: str = "",
    description: str = "",
    pipeline_config: Any = None,
    workbench_state: "WorkbenchBackup | str | Path | None" = None,
    review_paths: Sequence[str | Path] = (),
    receipts: Sequence[str | Path | Mapping[str, Any] | Any] = (),
    citations: Sequence[Mapping[str, Any] | str] = (),
    metadata: Mapping[str, Any] | None = None,
    embed_corpus: Literal["auto", "always", "never"] = "auto",
    created_at: str | None = None,
) -> BundleManifest:
    """Create a deterministic, SHA-256-verified ``.zip`` research bundle.

    ``embed_corpus`` controls whether the corpus text is packed as
    ``corpus.json.gz``:

    - ``"auto"`` (default): embeds the corpus when its license is
      redistributable; switches to a license-clean `CorpusReference` retrieval
      pointer when the corpus carries a non-commercial (CC BY-NC*) or
      restricted license.
    - ``"never"``: always emits a retrieval pointer without embedding corpus
      text.
    - ``"always"``: embeds the corpus even under non-commercial terms and marks
      ``manifest.redistributable = False`` with an explicit license notice.
    """
    if embed_corpus not in ("auto", "always", "never"):
        raise ValueError("embed_corpus must be 'auto', 'always', or 'never'")

    from . import __version__
    from .io.review import review_companion_path
    from .io.workbench import WorkbenchBackup, load_workbench_backup

    spec_url, spec_sha, spec_license = _dataset_spec_metadata(dataset or "")
    corpus_license = (
        (corpus.provenance.license if corpus is not None and corpus.provenance is not None else "")
        or spec_license
    )
    corpus_url = (
        (corpus.provenance.url if corpus is not None and corpus.provenance is not None else "")
        or spec_url
    )
    corpus_script = corpus.script_id if corpus is not None else ""
    corpus_version = (
        dataset_version
        or (corpus.provenance.data_version if corpus is not None and corpus.provenance is not None else "")
    )

    license_is_redistributable = is_redistributable_license(corpus_license)
    should_embed = False
    redistributable = True
    license_notes: list[str] = []

    if embed_corpus == "always":
        if corpus is None:
            raise ValueError("embed_corpus='always' requires a corpus object")
        should_embed = True
        if not license_is_redistributable:
            redistributable = False
            license_notes.append(
                f"Embedded corpus carries non-redistributable/NC license ({corpus_license}); "
                "do not redistribute this bundle publicly."
            )
    elif embed_corpus == "auto" and corpus is not None:
        if license_is_redistributable:
            should_embed = True
        else:
            should_embed = False
            if not dataset and not corpus_url:
                raise ValueError(
                    f"corpus carries non-commercial/restricted license ({corpus_license!r}) and "
                    "cannot be embedded in a redistributable bundle without a retrieval pointer; "
                    "pass dataset='<id>' for a license-clean reference or embed_corpus='always' "
                    "for a private non-redistributable archive"
                )
            license_notes.append(
                f"Corpus omitted to keep bundle redistributable (upstream license: {corpus_license}); "
                "hydrate retrieves it directly from the upstream source."
            )
    elif embed_corpus == "never":
        should_embed = False
        if corpus_license:
            license_notes.append(
                f"Corpus referenced by pointer rather than embedded (upstream license: {corpus_license})."
            )

    corpus_ref: CorpusReference | None = None
    if not should_embed and (dataset or corpus_url):
        corpus_ref = CorpusReference(
            dataset=dataset or "",
            version=corpus_version,
            script_id=corpus_script,
            sha256=spec_sha,
            url=corpus_url,
            license=corpus_license,
            filter_spec=dict(filter_spec) if filter_spec else {},
        )

    files: dict[str, tuple[bytes, str]] = {}

    # 1. Optional embedded corpus (deterministic gzip with mtime=0)
    if should_embed and corpus is not None:
        raw_corpus = _canonical_json_bytes(corpus.to_dict())
        gz_corpus = gzip.compress(raw_corpus, compresslevel=6, mtime=0)
        files["corpus.json.gz"] = (gz_corpus, "corpus")

    stamp = created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # 2. Optional workbench state backup
    if workbench_state is not None:
        if isinstance(workbench_state, WorkbenchBackup):
            wb_obj = workbench_state
        else:
            wb_obj = load_workbench_backup(workbench_state)
        wb_dict = wb_obj.to_dict()
        if not wb_obj.exported_at:
            wb_dict["exportedAt"] = stamp
        files["workbench-state.json"] = (_canonical_json_bytes(wb_dict), "workbench_state")

    # 3. Review tables (automatically pairing editable `.companion.json` snapshots)
    seen_review_names: set[str] = set()
    for rpath in review_paths:
        p = Path(rpath)
        if not p.is_file():
            raise FileNotFoundError(f"review file not found: {p}")
        base_name = p.name
        if base_name in seen_review_names:
            raise ValueError(f"duplicate review filename in bundle: {base_name!r}")
        seen_review_names.add(base_name)
        files[f"review/{base_name}"] = (p.read_bytes(), "review")
        companion = review_companion_path(p)
        if companion.is_file():
            files[f"review/{companion.name}"] = (companion.read_bytes(), "review")

    # 4. Analysis / evaluation receipts
    for idx, rec in enumerate(receipts, 1):
        if isinstance(rec, (str, Path)):
            rp = Path(rec)
            if not rp.is_file():
                raise FileNotFoundError(f"receipt file not found: {rp}")
            name = f"receipts/{rp.name}"
            if name in files:
                name = f"receipts/{idx:02d}-{rp.name}"
            files[name] = (rp.read_bytes(), "receipt")
        else:
            serialized = _serialize_pipeline_config(rec)
            files[f"receipts/receipt-{idx:02d}.json"] = (
                _canonical_json_bytes(serialized),
                "receipt",
            )

    # 5. Citations (JSON + BibTeX + plain text)
    citation_entries, bib_text, plain_text = _build_citations(
        corpus=corpus,
        corpus_ref=corpus_ref,
        extra_citations=citations,
    )
    files["citations.json"] = (_canonical_json_bytes(citation_entries), "citations")
    files["CITATIONS.bib"] = (bib_text.encode("utf-8"), "citations")
    files["CITATIONS.txt"] = (plain_text.encode("utf-8"), "citations")

    # 6. Optional free-form study metadata
    if metadata:
        files["metadata.json"] = (_canonical_json_bytes(dict(metadata)), "metadata")

    members = tuple(
        BundleMember(
            path=member_path,
            sha256=_sha256_bytes(payload),
            size=len(payload),
            kind=kind,
        )
        for member_path, (payload, kind) in sorted(files.items())
    )

    manifest = BundleManifest(
        format=BUNDLE_FORMAT,
        pyaegean_version=__version__,
        created_at=stamp,
        title=title,
        description=description,
        redistributable=redistributable,
        license_notes=tuple(license_notes),
        corpus_embedded=should_embed,
        corpus_ref=corpus_ref,
        pipeline_config=_serialize_pipeline_config(pipeline_config),
        members=members,
    )

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(out_path) as tmp_zip:
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            def _write_member(arcname: str, data: bytes) -> None:
                info = zipfile.ZipInfo(filename=arcname, date_time=_FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, data)

            _write_member("manifest.json", _canonical_json_bytes(manifest.to_dict()))
            for member_path, (payload, _kind) in sorted(files.items()):
                _write_member(member_path, payload)

    return manifest


def inspect_bundle(path: str | Path) -> BundleManifest:
    """Read and parse ``manifest.json`` from a research bundle without extracting."""
    bundle_path = Path(path)
    if not bundle_path.is_file():
        raise FileNotFoundError(f"bundle not found: {bundle_path}")
    with zipfile.ZipFile(bundle_path, "r") as zf:
        if "manifest.json" not in zf.namelist():
            raise ValueError(f"{bundle_path} is not an aegean research bundle (missing manifest.json)")
        raw = json.loads(zf.read("manifest.json").decode("utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("invalid bundle manifest: expected JSON object")
    return BundleManifest.from_dict(raw)


def verify_bundle(path: str | Path) -> BundleVerification:
    """Verify bundle structure, path safety, and SHA-256 digests of every member."""
    bundle_path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    fmt = ""
    redistributable = True
    checked = 0

    if not bundle_path.is_file():
        return BundleVerification(
            ok=False,
            path=str(bundle_path),
            format="",
            redistributable=False,
            checked_members=0,
            errors=(f"bundle file not found: {bundle_path}",),
        )

    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            infos = zf.infolist()
            names: list[str] = []
            for info in infos:
                if _is_symlink_zipinfo(info):
                    errors.append(f"unsafe symlink member rejected: {info.filename!r}")
                if not _is_safe_member_path(info.filename):
                    errors.append(f"unsafe member path rejected: {info.filename!r}")
                names.append(info.filename)

            if len(names) != len(set(names)):
                errors.append("archive contains duplicate member paths")

            if "manifest.json" not in names:
                errors.append("missing manifest.json")
                return BundleVerification(
                    ok=False,
                    path=str(bundle_path),
                    format="",
                    redistributable=False,
                    checked_members=0,
                    errors=tuple(errors),
                )

            try:
                raw_manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                manifest = BundleManifest.from_dict(raw_manifest)
                fmt = manifest.format
                redistributable = manifest.redistributable
            except Exception as exc:
                errors.append(f"invalid manifest.json: {exc}")
                return BundleVerification(
                    ok=False,
                    path=str(bundle_path),
                    format="",
                    redistributable=False,
                    checked_members=0,
                    errors=tuple(errors),
                )

            if not manifest.redistributable:
                warnings.append(
                    "bundle is marked non-redistributable (contains non-commercial/restricted corpus data)"
                )

            declared = {m.path: m for m in manifest.members}
            actual = set(names) - {"manifest.json"}
            extra = sorted(actual - set(declared))
            if extra:
                errors.append(f"unmanifested member(s) present: {', '.join(extra)}")

            for member in manifest.members:
                if not _is_safe_member_path(member.path):
                    errors.append(f"unsafe manifest member path: {member.path!r}")
                    continue
                if member.path not in actual:
                    errors.append(f"missing declared member: {member.path}")
                    continue
                payload = zf.read(member.path)
                if len(payload) != member.size:
                    errors.append(
                        f"size mismatch for {member.path}: expected {member.size}, got {len(payload)}"
                    )
                actual_sha = _sha256_bytes(payload)
                if actual_sha != member.sha256:
                    errors.append(
                        f"SHA-256 mismatch for {member.path}: expected {member.sha256[:12]}…, "
                        f"got {actual_sha[:12]}…"
                    )
                checked += 1
    except zipfile.BadZipFile as exc:
        errors.append(f"corrupt zip archive: {exc}")

    return BundleVerification(
        ok=not errors,
        path=str(bundle_path),
        format=fmt,
        redistributable=redistributable,
        checked_members=checked,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def extract_bundle(
    path: str | Path,
    dest: str | Path,
    *,
    verify: bool = True,
) -> BundleManifest:
    """Safely verify and unpack all members of a research bundle into ``dest``."""
    bundle_path = Path(path)
    if verify:
        report = verify_bundle(bundle_path)
        if not report.ok:
            raise ValueError("bundle verification failed: " + "; ".join(report.errors))

    dest_dir = Path(dest).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = inspect_bundle(bundle_path)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        for info in zf.infolist():
            if _is_symlink_zipinfo(info) or not _is_safe_member_path(info.filename):
                raise ValueError(f"refusing to extract unsafe archive member: {info.filename!r}")
            target = (dest_dir / info.filename).resolve()
            if not target.is_relative_to(dest_dir):
                raise ValueError(f"path traversal blocked during extraction: {info.filename!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info.filename))

    return manifest


def _apply_filter_spec(corpus: "Corpus", spec: Mapping[str, Any]) -> "Corpus":
    if not spec:
        return corpus
    doc_ids = spec.get("doc_ids")
    if isinstance(doc_ids, list) and doc_ids:
        corpus = corpus.subset([str(d) for d in doc_ids])
    meta_kwargs = {
        k: v
        for k, v in spec.items()
        if k in ("site", "period", "scribe", "support") and isinstance(v, str) and v
    }
    if meta_kwargs:
        corpus = corpus.filter(**meta_kwargs)
    return corpus


def _load_referenced_corpus(ref: CorpusReference, *, allow_fetch: bool) -> "Corpus":
    from . import load
    from .data import _REMOTE, _VERSIONED_CORPORA, cache_dir, is_downloaded

    if not ref.dataset:
        raise ValueError("corpus reference has no dataset id; fetch manually from " + (ref.url or "upstream"))

    spec = _REMOTE.get(ref.dataset)
    if spec is not None and not is_downloaded(spec, cache_dir()) and not allow_fetch:
        raise RuntimeError(
            f"bundle references remote dataset {ref.dataset!r} (license: {ref.license or spec.license}) "
            "which is not cached locally; pass allow_fetch=True (or `aegean bundle hydrate --fetch`) "
            "to download it directly from its upstream source"
        )
    if ref.version and ref.dataset in _VERSIONED_CORPORA:
        corpus = load(ref.dataset, version=ref.version)
    else:
        corpus = load(ref.dataset)
    return _apply_filter_spec(corpus, ref.filter_spec)


def hydrate_bundle(
    path: str | Path,
    *,
    dest: str | Path | None = None,
    allow_fetch: bool = False,
    verify: bool = True,
) -> ResearchBundle:
    """Verify and load a research bundle back into live ``pyaegean`` objects.

    Loads the embedded corpus (or reconstructs a pointer-referenced corpus via
    `aegean.load`, fetching only when ``allow_fetch=True``), workbench workspace
    backup, citations, receipts, and metadata. When ``dest`` is provided,
    all archive files (including editable review CSVs and ``.companion.json``
    snapshots) are unpacked there and indexed in ``ResearchBundle.review_files``.
    """
    from .core.corpus import Corpus
    from .io.workbench import load_workbench_backup

    bundle_path = Path(path)
    if verify:
        report = verify_bundle(bundle_path)
        if not report.ok:
            raise ValueError("bundle verification failed: " + "; ".join(report.errors))

    manifest = extract_bundle(bundle_path, dest, verify=False) if dest is not None else inspect_bundle(bundle_path)

    corpus: Corpus | None = None
    workbench_state = None
    receipts: dict[str, Any] = {}
    citations: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    review_files: dict[str, Path] = {}

    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = set(zf.namelist())
        if "corpus.json.gz" in names:
            raw = gzip.decompress(zf.read("corpus.json.gz")).decode("utf-8")
            corpus = Corpus.from_dict(json.loads(raw))
        elif manifest.corpus_ref is not None:
            corpus = _load_referenced_corpus(manifest.corpus_ref, allow_fetch=allow_fetch)

        if "workbench-state.json" in names:
            wb_data = json.loads(zf.read("workbench-state.json").decode("utf-8"))
            workbench_state = load_workbench_backup(wb_data)

        if "citations.json" in names:
            raw_cit = json.loads(zf.read("citations.json").decode("utf-8"))
            if isinstance(raw_cit, list):
                citations = [dict(c) for c in raw_cit if isinstance(c, Mapping)]

        if "metadata.json" in names:
            raw_meta = json.loads(zf.read("metadata.json").decode("utf-8"))
            if isinstance(raw_meta, Mapping):
                metadata = dict(raw_meta)

        for member in manifest.members:
            if member.kind == "receipt":
                raw_bytes = zf.read(member.path)
                try:
                    receipts[member.path] = json.loads(raw_bytes.decode("utf-8"))
                except Exception:
                    receipts[member.path] = raw_bytes.decode("utf-8", errors="replace")

    if dest is not None:
        dest_root = Path(dest).resolve()
        for member in manifest.members:
            if member.kind == "review" and not member.path.endswith(".companion.json"):
                review_files[Path(member.path).name] = dest_root / member.path

    return ResearchBundle(
        manifest=manifest,
        corpus=corpus,
        workbench_state=workbench_state,
        review_files=review_files,
        receipts=receipts,
        citations=citations,
        metadata=metadata,
    )
