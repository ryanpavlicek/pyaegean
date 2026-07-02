"""Round-trip with the Linear A Research Workbench (linearaworkbench).

Two directions:

- `to_workbench` emits the workbench's inscription-record shape from any
  corpus, ready for the app's bring-your-own-corpus loader — point
  ``?corpus=<url>`` at the file (or pick it in *Data Export → Bring your own
  corpus*) and every analysis module runs against your data.
- `from_workbench_export` loads what the workbench produces — the schema-v1
  full-corpus export from its Data Export module / static data API, or a
  plain inscriptions array — into a `Corpus` with the full pyaegean API.

Both speak plain JSON; neither needs the other tool installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core.model import DocumentMeta
from ..core.provenance import Provenance

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["from_workbench_export", "to_workbench"]


def to_workbench(corpus: Corpus, path: str | Path | None = None) -> list[dict[str, Any]]:
    """Emit workbench-shaped inscription records (optionally writing JSON).

    Each document becomes one record with the fields the workbench renders:
    ``id``/``site``/``support``/``scribe``/``findspot``/``context`` (its name
    for the dating period)/``name``, the flat ``words`` list, per-line
    ``lines``, ``translations``, ``glyphs``, ``transcription``, and image
    references. Image *files* are never embedded — the workbench treats the
    references as paths under its own mirror, so corpora without one simply
    show no imagery.

    With ``path``, the records are also written as UTF-8 JSON — the file the
    app loads via ``?corpus=<url>`` or its corpus file picker.
    """
    records: list[dict[str, Any]] = []
    for doc in corpus:
        words = [t.text for t in doc.tokens]
        lines = (
            [[t.text for t in toks] for toks in doc.line_tokens]
            if doc.lines
            else [words]
        )
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
                "imageRights": "",
                "imageRightsURL": "",
            }
        )
    if path is not None:
        Path(path).write_text(
            json.dumps(records, ensure_ascii=False), encoding="utf-8"
        )
    return records


def from_workbench_export(source: str | Path | dict[str, Any] | list[Any]) -> Corpus:
    """Load a workbench corpus export into a `Corpus`.

    ``source`` is a path to a JSON file, a JSON string, or already-parsed
    JSON. Both forms the workbench produces are accepted: the schema-v1
    export object (records under ``"inscriptions"``, provenance under
    ``"_meta"``, per-record ``"derived"`` analyses — ignored here) and a
    plain array of inscription records.

    Token kinds are inferred the `Corpus.from_records` way (numerals by
    parseability, everything else a word); glyphs, transcription, and image
    references are carried onto the documents. The export's own metadata
    (app version, generation time, scope) lands in the corpus provenance.

    Both field spellings the workbench has used are read: the schema-v1
    export writes the dating period as ``period`` and nests imagery under an
    ``images`` object (``facsimile``/``photograph``/``rights``/``rightsUrl``),
    while the plain-array shape (and `to_workbench`) uses ``context`` and the
    flat ``facsimileImages``/``images`` lists.
    """
    from ..core.corpus import Corpus

    if isinstance(source, (str, Path)):
        text = (
            str(source)
            if isinstance(source, str) and source.lstrip().startswith(("{", "["))
            else Path(source).read_text(encoding="utf-8")
        )
        data: Any = json.loads(text)
    else:
        data = source

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
    extras: list[tuple[str, str, tuple[str, ...]]] = []  # glyphs, transcription, images
    for rec in raw:
        if not isinstance(rec, dict) or not rec.get("id"):
            raise ValueError(f"inscription record without an id: {rec!r}")
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
        if isinstance(img, dict):
            # The schema-v1 export nests imagery under an "images" object
            # (facsimile/photograph/rights/rightsUrl).
            images = tuple(img.get("facsimile") or ()) + tuple(img.get("photograph") or ())
        else:
            images = tuple(rec.get("facsimileImages") or ()) + tuple(img or ())
        extras.append((rec.get("glyphs", ""), rec.get("transcription", ""), images))

    source_bits = [str(meta.get("tool") or "linearaworkbench corpus export")]
    if meta.get("schemaVersion"):
        source_bits.append(f"schema v{meta['schemaVersion']}")
    if meta.get("exportedAt"):
        source_bits.append(f"exported {meta['exportedAt']}")
    if meta.get("scopeSummary") and meta["scopeSummary"] != "whole corpus":
        source_bits.append(f"scope: {meta['scopeSummary']}")
    corpus = Corpus.from_records(
        records,
        script_id="lineara",
        provenance=Provenance(
            source=" · ".join(source_bits),
            license="see the workbench's data sources",
            url="https://linearaworkbench.xyz/",
        ),
    )
    # from_records covers the tokenized text; carry the workbench's extra
    # surface forms onto the documents it built (DocumentMeta is frozen, so
    # images go on via replacement).
    for doc, (glyphs, transcription, images) in zip(corpus, extras):
        doc.glyphs = glyphs
        doc.transcription = transcription
        if images:
            m = doc.meta
            doc.meta = DocumentMeta(
                site=m.site, support=m.support, scribe=m.scribe,
                findspot=m.findspot, period=m.period, name=m.name,
                images=images, notes=m.notes,
            )
    return corpus
