"""Round-trip with the Linear A Research Workbench (linearaworkbench).

Three bridges:

- `to_workbench` emits the workbench's inscription-record shape from any
  corpus, ready for the app's bring-your-own-corpus loader — point
  ``?corpus=<url>`` at the file (or run ``aegean workbench --corpus <id-or-path>``)
  and every analysis module runs against your data.
- `from_workbench_export` loads what the workbench produces — the schema-v1
  full-corpus export from its Data Export module / static data API, or a
  plain inscriptions array — into a `Corpus` with the full pyaegean API. For
  Linear A exports (``script_id="lineara"``), tokens are classified with the
  Linear A loader (preserving inline apparatus such as erased ``𐝫`` marks,
  bracketed uncertainty, logograms, and separators) and the Linear A sign
  inventory is attached.
- `load_workbench_backup` / `save_workbench_backup` read and write the
  workbench's single-file workspace backup schema (``linear-a-workbench-backup``
  v1: annotations, collections, findings, notes, saved hypotheses, saved queries,
  tablet categories, custom wordlists, and pins), enabling seamless round-trips
  with ``aegean workbench --state <workspace.json>``.

All functions speak plain JSON; neither tool needs the other installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..core.corpus import _is_readable_file, _shown
from ..core.model import DocumentMeta
from ..core.provenance import Provenance

if TYPE_CHECKING:
    from ..analysis.query import FilterRow
    from ..core.corpus import Corpus

__all__ = [
    "BACKUP_KIND",
    "BACKUP_VERSION",
    "WorkbenchBackup",
    "from_workbench_export",
    "load_workbench_backup",
    "save_workbench_backup",
    "to_workbench",
]

# A decoded UTF-8 BOM: not whitespace, so str.strip() leaves it in place and a BOM'd
# JSON string would neither parse as JSON nor name a readable file.
_BOM = "\ufeff"

BACKUP_KIND = "linear-a-workbench-backup"
BACKUP_VERSION = 1

_KNOWN_BACKUP_KEYS = frozenset(
    {
        "annotations",
        "collections",
        "findings",
        "notes",
        "saved-hypotheses",
        "saved-queries",
        "tablet-categories",
        "custom-languages",
        "pins",
    }
)
_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})


def _read_export_text(path: Path) -> str:
    """Read an export file as ``utf-8-sig``, reporting a path the OS cannot even name
    (a JSON string that reached this branch) instead of raising a bare ``OSError``."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ValueError(
            f"cannot read a workbench export from {_shown(str(path))}: {exc.strerror or exc}. "
            "Pass a path to an export file, a JSON string, or already-parsed JSON"
        ) from None


def _load_json_source(source: str | Path | dict[str, Any] | list[Any]) -> Any:
    if isinstance(source, Path):
        return json.loads(_read_export_text(source))
    if isinstance(source, str):
        probe = source.lstrip(_BOM).lstrip()
        if not probe.startswith(("{", "[")):
            return json.loads(_read_export_text(Path(source)))
        try:
            return json.loads(probe)
        except ValueError:
            path = Path(source)
            if not _is_readable_file(path):
                raise
            return json.loads(_read_export_text(path))
    return source


def to_workbench(corpus: Corpus, path: str | Path | None = None) -> list[dict[str, Any]]:
    """Emit workbench-shaped inscription records (optionally writing JSON).

    Each document becomes one record with the fields the workbench renders:
    ``id``/``site``/``support``/``scribe``/``findspot``/``context`` (its name
    for the dating period)/``name``, the flat ``words`` list, per-line
    ``lines``, ``translations``, ``glyphs``, ``transcription``, and image
    references (plus ``imageRights`` / ``imageRightsURL`` if carried in
    ``doc.meta.notes``). Image *files* are never embedded — the workbench treats
    the references as paths under its own mirror, so corpora without one simply
    show no imagery.

    Content the format does NOT preserve: the workbench schema carries token
    *text* only, so out-of-band `ReadingStatus` overrides on plain tokens and
    `Token.annotations` (lemma, morphology, evidence class, review stamps) are
    not written. Inline Linear A apparatus embedded in token text (e.g. erased
    ``𐝫`` or bracketed ``[?]``) is preserved and re-classified on re-import.
    For a fully lossless archive use `Corpus.to_json` or `aegean.db.to_sqlite`.

    With ``path``, the records are also written as UTF-8 JSON — the file the
    app loads via ``?corpus=<url>``, ``aegean workbench --corpus``, or its
    corpus file picker.
    """
    records: list[dict[str, Any]] = []
    for doc in corpus:
        words = [t.text for t in doc.tokens]
        lines = (
            [[t.text for t in toks] for toks in doc.line_tokens]
            if doc.lines
            else [words]
        )
        image_rights = ""
        image_rights_url = ""
        for note in doc.meta.notes:
            if note.startswith("imageRights: "):
                image_rights = note[len("imageRights: "):]
            elif note.startswith("imageRightsURL: "):
                image_rights_url = note[len("imageRightsURL: "):]
        records.append(
            {
                "id": doc.id,
                "site": doc.meta.site,
                "support": doc.meta.support,
                "scribe": doc.meta.scribe,
                "findspot": doc.meta.findspot,
                "context": doc.meta.period,
                "name": doc.meta.name or doc.id,
                "words": words,
                "translations": list(doc.translations),
                "lines": lines,
                "glyphs": doc.glyphs,
                "transcription": doc.transcription,
                "facsimileImages": [],
                "images": list(doc.meta.images),
                "imageRights": image_rights,
                "imageRightsURL": image_rights_url,
            }
        )
    if path is not None:
        from .._atomic import atomic_path

        with atomic_path(path) as tmp:
            tmp.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return records


def from_workbench_export(
    source: str | Path | dict[str, Any] | list[Any], *, script_id: str = "lineara"
) -> Corpus:
    """Load a workbench corpus export into a `Corpus`.

    ``source`` is a path to a JSON file, a JSON string, or already-parsed
    JSON. Both forms the workbench produces are accepted: the schema-v1
    export object (records under ``"inscriptions"``, provenance under
    ``"_meta"``, per-record ``"derived"`` analyses — ignored here) and a
    plain array of inscription records. ``script_id`` defaults to ``lineara``
    (the workbench's own corpus); pass the real script when re-importing an
    export of some other corpus, so the documents are not rebranded.

    When ``script_id == "lineara"``, tokens are classified through the Linear A
    loader (`aegean.scripts.lineara.loader.classify`) so inline apparatus
    (erased ``𐝫`` → ``ReadingStatus.LOST`` / ``UNCLEAR``, bracketed ``[?]`` →
    ``UNCLEAR``, logograms, separators, and metrological fractions) is faithfully
    restored, and `linear_a_inventory()` is attached to ``corpus.inventory``.
    Out-of-band `ReadingStatus` overrides on plain text tokens and
    `Token.annotations` are not represented in the workbench format (see
    `to_workbench`).

    Both field spellings the workbench has used are read: the schema-v1
    export writes the dating period as ``period`` and nests imagery under an
    ``images`` object (``facsimile``/``photograph``/``rights``/``rightsUrl``),
    while the plain-array shape (and `to_workbench`) uses ``context`` and the
    flat ``facsimileImages``/``images``/``imageRights``/``imageRightsURL`` fields.
    """
    from ..core.corpus import Corpus

    data = _load_json_source(source)

    meta: dict[str, Any] = {}
    if isinstance(data, dict):
        meta = data.get("_meta") or {}
        raw = data.get("inscriptions")
        if not isinstance(raw, list):
            raise ValueError(
                "not a workbench corpus export: no 'inscriptions' array"
            )
    elif isinstance(data, list):
        raw = data
    else:
        raise ValueError("expected a workbench export object or an array of records")

    records: list[dict[str, Any]] = []
    # Keyed by id, NOT positional: from_records collapses duplicate ids to one
    # document (last wins), so a positional zip would shift every later document's
    # extras onto the wrong id and drop the tail. Last-wins here matches that.
    extras: dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...]]] = {}
    for rec in raw:
        if not isinstance(rec, dict) or not rec.get("id"):
            raise ValueError(f"inscription record without an id: {_shown(rec)}")
        body: dict[str, Any] = {"id": rec["id"]}
        if rec.get("lines"):
            body["lines"] = rec["lines"]
        elif rec.get("words"):
            body["words"] = rec["words"]
        else:
            body["words"] = []
        if rec.get("translations"):
            body["translations"] = rec["translations"]
        body["meta"] = {
            "site": rec.get("site", ""),
            "support": rec.get("support", ""),
            "scribe": rec.get("scribe", ""),
            "findspot": rec.get("findspot", ""),
            # The schema-v1 export calls the dating period "period"; the
            # plain-array shape (and the bundled corpus) calls it "context".
            "period": rec.get("context") or rec.get("period") or "",
            "name": rec.get("name", ""),
        }
        records.append(body)
        img = rec.get("images")
        rights = ""
        rights_url = ""
        if isinstance(img, dict):
            # The schema-v1 export nests imagery under an "images" object
            # (facsimile/photograph/rights/rightsUrl).
            images = tuple(img.get("facsimile") or ()) + tuple(img.get("photograph") or ())
            rights = str(img.get("rights") or "")
            rights_url = str(img.get("rightsUrl") or "")
        else:
            images = tuple(rec.get("facsimileImages") or ()) + tuple(img or ())
            rights = str(rec.get("imageRights") or "")
            rights_url = str(rec.get("imageRightsURL") or "")
        note_items: list[str] = []
        if rights:
            note_items.append(f"imageRights: {rights}")
        if rights_url:
            note_items.append(f"imageRightsURL: {rights_url}")
        extras[rec["id"]] = (
            rec.get("glyphs", ""),
            rec.get("transcription", ""),
            images,
            tuple(note_items),
        )

    source_bits = [str(meta.get("tool") or "linearaworkbench corpus export")]
    if meta.get("schemaVersion"):
        source_bits.append(f"schema v{meta['schemaVersion']}")
    if meta.get("exportedAt"):
        source_bits.append(f"exported {meta['exportedAt']}")
    if meta.get("scopeSummary") and meta["scopeSummary"] != "whole corpus":
        source_bits.append(f"scope: {meta['scopeSummary']}")

    sign_inventory: Any = None
    classify_fn: Any = None
    if script_id == "lineara":
        from ..scripts.lineara.inventory import linear_a_inventory
        from ..scripts.lineara.loader import classify as _classify_la

        sign_inventory = linear_a_inventory()
        classify_fn = _classify_la

    corpus = Corpus.from_records(
        records,
        script_id=script_id,
        provenance=Provenance(
            source=" · ".join(source_bits),
            license="see the workbench's data sources",
            url="https://linearaworkbench.xyz/",
        ),
    )
    if sign_inventory is not None:
        corpus.sign_inventory = sign_inventory
    # from_records covers the tokenized text; carry the workbench's extra
    # surface forms onto the documents it built (DocumentMeta is frozen, so
    # images and rights notes go on via replacement). For Linear A, re-classify
    # tokens so inline apparatus (erased 𐝫, brackets, logograms, separators)
    # matches Corpus.load("lineara").
    for doc in corpus:
        if classify_fn is not None:
            doc.tokens = [
                classify_fn(t.text, t.line_no, t.position) for t in doc.tokens
            ]
        extra = extras.get(doc.id)
        if extra is None:
            continue
        glyphs, transcription, images, rights_notes = extra
        doc.glyphs = glyphs
        doc.transcription = transcription
        if images or rights_notes:
            m = doc.meta
            merged_notes = tuple(m.notes) + tuple(
                n for n in rights_notes if n not in m.notes
            )
            doc.meta = DocumentMeta(
                site=m.site, support=m.support, scribe=m.scribe,
                findspot=m.findspot, period=m.period, name=m.name,
                images=images or m.images, notes=merged_notes,
            )
    return corpus


@dataclass
class WorkbenchBackup:
    """In-memory representation of a ``linear-a-workbench-backup`` v1 file.

    Exposes the researcher's structured workspace artifacts (annotations,
    collections, findings, notes, saved hypotheses, saved queries, tablet
    category overrides, custom wordlists, and pins) while preserving any
    additional namespaced keys in ``extra`` for lossless round-tripping.
    """

    annotations: list[dict[str, Any]] = field(default_factory=list)
    collections: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    saved_queries: list[dict[str, Any]] = field(default_factory=list)
    tablet_categories: dict[str, str] = field(default_factory=dict)
    custom_languages: dict[str, Any] = field(default_factory=dict)
    pins: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    version: int = BACKUP_VERSION
    exported_at: str = ""
    app: dict[str, Any] = field(
        default_factory=lambda: {"name": "Linear A Research Workbench"}
    )

    def to_filter_rows(self, query: str | int = 0) -> list[FilterRow]:
        """Convert one of ``saved_queries`` (by name or index) into `FilterRow`
        objects ready for ``corpus.query(...)``."""
        from ..analysis.query import FilterRow

        target: dict[str, Any] | None = None
        if isinstance(query, int):
            if 0 <= query < len(self.saved_queries):
                target = self.saved_queries[query]
        else:
            for q in self.saved_queries:
                if q.get("name") == query:
                    target = q
                    break
        if target is None:
            raise KeyError(f"saved query not found: {query!r}")
        rows_raw = target.get("rows") or target.get("filters") or []
        out: list[FilterRow] = []
        for r in rows_raw:
            if not isinstance(r, dict) or not r.get("field"):
                continue
            conn: Literal["and", "or"] = "or" if r.get("connector") == "or" else "and"
            out.append(
                FilterRow(
                    field=str(r["field"]),
                    value=str(r.get("value", "")),
                    negate=bool(r.get("negate", False)),
                    connector=conn,
                )
            )
        return out

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the canonical ``linear-a-workbench-backup`` v1 JSON dict."""
        data: dict[str, Any] = {}
        for k, v in self.extra.items():
            if k not in _FORBIDDEN_KEYS and k not in _KNOWN_BACKUP_KEYS:
                data[k] = v
        if self.annotations:
            data["annotations"] = self.annotations
        if self.collections:
            data["collections"] = self.collections
        if self.findings:
            data["findings"] = self.findings
        if self.notes:
            data["notes"] = self.notes
        if self.hypotheses:
            data["saved-hypotheses"] = self.hypotheses
        if self.saved_queries:
            data["saved-queries"] = self.saved_queries
        if self.tablet_categories:
            data["tablet-categories"] = self.tablet_categories
        if self.custom_languages:
            data["custom-languages"] = self.custom_languages
        if self.pins:
            data["pins"] = self.pins
        exported_at = self.exported_at or datetime.now(timezone.utc).isoformat()
        return {
            "kind": BACKUP_KIND,
            "version": self.version,
            "exportedAt": exported_at,
            "app": dict(self.app) if self.app else {"name": "Linear A Research Workbench"},
            "data": data,
        }


def load_workbench_backup(
    source: str | Path | dict[str, Any],
) -> WorkbenchBackup:
    """Load a ``linear-a-workbench-backup`` v1 file (path, JSON string, or dict).

    Validates ``kind == "linear-a-workbench-backup"``, ``version`` (integer
    ``1 .. BACKUP_VERSION``), and ``data`` (mapping), ignoring prototype-pollution
    keys. Preserves unmodeled workbench keys (``settings``, ``report-layout``,
    ``lb-sign-frequencies``, etc.) in ``backup.extra`` so `save_workbench_backup`
    round-trips losslessly.
    """
    raw = _load_json_source(source)
    if not isinstance(raw, dict):
        raise ValueError("not a workbench backup: expected a JSON object")
    if raw.get("kind") != BACKUP_KIND:
        raise ValueError(
            f"not a workbench backup: expected kind={BACKUP_KIND!r}, got {raw.get('kind')!r}"
        )
    version = raw.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not (1 <= version <= BACKUP_VERSION)
    ):
        raise ValueError(f"unsupported workbench backup version: {version!r}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("not a workbench backup: 'data' must be an object")

    def _as_list(key: str) -> list[dict[str, Any]]:
        val = data.get(key)
        return list(val) if isinstance(val, list) else []

    def _as_dict(key: str) -> dict[str, Any]:
        val = data.get(key)
        return dict(val) if isinstance(val, dict) else {}

    extra = {
        k: v
        for k, v in data.items()
        if isinstance(k, str) and k and k not in _KNOWN_BACKUP_KEYS and k not in _FORBIDDEN_KEYS
    }
    return WorkbenchBackup(
        annotations=_as_list("annotations"),
        collections=_as_list("collections"),
        findings=_as_list("findings"),
        notes=_as_list("notes"),
        hypotheses=_as_list("saved-hypotheses"),
        saved_queries=_as_list("saved-queries"),
        tablet_categories={
            str(k): str(v) for k, v in _as_dict("tablet-categories").items()
        },
        custom_languages=_as_dict("custom-languages"),
        pins=_as_list("pins"),
        extra=extra,
        version=version,
        exported_at=str(raw.get("exportedAt") or ""),
        app=dict(raw["app"]) if isinstance(raw.get("app"), dict) else {"name": "Linear A Research Workbench"},
    )


def save_workbench_backup(
    backup: WorkbenchBackup | dict[str, Any],
    path: str | Path,
) -> dict[str, Any]:
    """Write a `WorkbenchBackup` (or validated backup dict) atomically as UTF-8 JSON.

    Returns the serialized backup dictionary. The resulting file can be restored
    directly in the workbench (*Data Export → Restore from file*) or mounted live
    via ``aegean workbench --state <path>``.
    """
    from .._atomic import atomic_path

    if isinstance(backup, WorkbenchBackup):
        payload = backup.to_dict()
    else:
        payload = load_workbench_backup(backup).to_dict()

    with atomic_path(path) as tmp:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
