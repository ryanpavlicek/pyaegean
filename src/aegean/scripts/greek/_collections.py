"""Work-indexed Ancient, Classical, Patristic & Byzantine Greek corpus collections.

Provides fast offline discovery (via the compact bundled ``collections_index.json``)
and fetch-on-demand loading for all 8 categorized open-licensed Greek literary,
patristic, and Byzantine release collections (~3,844 works, ~64.3M tokens from
Homer through the 15th c. / Fall of Constantinople, sourced from commit-pinned
``open-greek/open-greek-corpus`` under verified Public Domain / CC BY 4.0 /
CC BY-SA 4.0 licenses — zero NonCommercial or proprietary texts):

- ``chrysostom``           — John Chrysostom (& Ps.-Chrysostom) complete open corpus
- ``church-fathers-early`` — Pre-Nicene & 4th c. Nicene Church Fathers
- ``church-fathers-late``  — Post-Nicene, Eastern Fathers, Saints & Councils (5th–15th c.)
- ``classical-greek``      — Archaic & Classical Greek literature (8th–4th c. BCE)
- ``hellenistic-greek``    — Hellenistic, Jewish-Greek & DFHG fragmentary historians
- ``imperial-greek``       — Imperial Greek literature, philosophy & medicine (1st–3rd c. CE)
- ``late-antique-greek``   — Late Antique philosophy, rhetoric & classical scholia (4th–6th c. CE)
- ``byzantine-lit``        — Byzantine history, literature & lexicography (6th–15th c. CE)

Every work carries its exact per-work license, edition, source, and OCR correction
status (``not-ocr``, ``manual``, ``auto-corrected``, or ``raw-ocr``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ...core.corpus import register_loader

__all__ = [
    "COLLECTION_IDS",
    "collection_works",
    "collections",
    "load_collection",
    "load_collection_work",
    "resolve_collection_work",
]

COLLECTION_IDS: tuple[str, ...] = (
    "chrysostom",
    "church-fathers-early",
    "church-fathers-late",
    "classical-greek",
    "hellenistic-greek",
    "imperial-greek",
    "late-antique-greek",
    "byzantine-lit",
)

_OGC_ID_RE = re.compile(r"^ogc\d{4,}$", re.IGNORECASE)

_INDEX_CACHE: dict[str, Any] | None = None
_BUNDLE_CACHE: dict[str, dict[str, Any]] = {}


def _fold(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return stripped.lower().replace("ς", "σ")


def _load_index() -> dict[str, Any]:
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    from ...data import load_bundled_json

    raw = load_bundled_json("greek", "collections_index.json")
    tables = raw.get("tables")
    if isinstance(tables, dict):
        t_col = tables["collection"]
        t_auth = tables["author"]
        t_src = tables["source"]
        t_lic = tables["license"]
        t_corr = tables["correction"]
        t_per = tables["period"]
        expanded: list[list[Any]] = []
        for r in raw.get("works", ()):
            wid = f"ogc{r[0]:06d}" if isinstance(r[0], int) else str(r[0])
            expanded.append(
                [
                    wid,
                    t_col[r[1]],
                    t_auth[r[2]],
                    r[3],
                    r[4],
                    r[5],
                    t_src[r[6]],
                    t_lic[r[7]],
                    t_corr[r[8]],
                    t_per[r[9]],
                ]
            )
        _INDEX_CACHE = {
            "_meta": raw.get("_meta", {}),
            "collections": raw.get("collections", {}),
            "works": expanded,
        }
    else:
        _INDEX_CACHE = raw
    return _INDEX_CACHE


def _row_to_dict(row: list[Any]) -> dict[str, Any]:
    return {
        "work_id": str(row[0]),
        "collection": str(row[1]),
        "author": str(row[2]),
        "title": str(row[3]),
        "tlg": str(row[4]),
        "tokens": int(row[5]),
        "source": str(row[6]),
        "license": str(row[7]),
        "correction": str(row[8]),
        "period": str(row[9]),
    }


def collections() -> list[dict[str, Any]]:
    """List metadata and install status for all 8 categorized Greek collections (offline)."""
    from ...data import _REMOTE, cache_dir, is_downloaded

    idx = _load_index()
    col_map = idx.get("collections", {})
    root = cache_dir()
    out: list[dict[str, Any]] = []
    for cid in COLLECTION_IDS:
        info = dict(col_map.get(cid, {}))
        asset = f"{cid}-corpus"
        spec = _REMOTE.get(asset)
        out.append(
            {
                "id": cid,
                "asset_name": asset,
                "title": info.get("title", cid),
                "category": info.get("category", "classical"),
                "period": info.get("period", ""),
                "works": int(info.get("works", 0)),
                "authors": int(info.get("authors", 0)),
                "tokens": int(info.get("tokens", 0)),
                "installed": bool(spec and is_downloaded(spec, root)),
            }
        )
    return out


def collection_works(
    collection_id: str | None = None,
    *,
    author: str | None = None,
    query: str | None = None,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """Search or list works across the 8 categorized Greek collections (100% offline).

    Parameters
    ----------
    collection_id:
        Optional collection filter (e.g. ``'chrysostom'``, ``'church-fathers-early'``,
        ``'classical-greek'``, ``'byzantine-lit'``).
    author:
        Optional author substring filter (case- and diacritic-insensitive, e.g.
        ``'Chrysostom'``, ``'Basilius'``, ``'Anna Comnena'``).
    query:
        Optional multi-term search across ``work_id``, ``author``, ``title``, and ``tlg``.
    limit:
        Maximum results to return (``0`` returns all matches).
    """
    idx = _load_index()
    want_col: str | None = None
    if collection_id is not None:
        want_col = collection_id.strip().lower().removesuffix("-corpus")
        if want_col not in COLLECTION_IDS:
            raise ValueError(
                f"unknown Greek collection {collection_id!r}; expected one of: "
                + ", ".join(COLLECTION_IDS)
            )
    auth_q = _fold(author.strip()) if author and author.strip() else ""
    terms = [_fold(t) for t in query.strip().split() if t.strip()] if query and query.strip() else []

    out: list[dict[str, Any]] = []
    for row in idx.get("works", ()):
        if want_col is not None and row[1] != want_col:
            continue
        if auth_q and auth_q not in _fold(str(row[2])):
            continue
        if terms:
            hay = _fold(f"{row[0]} {row[1]} {row[2]} {row[3]} {row[4]}")
            if not all(t in hay for t in terms):
                continue
        out.append(_row_to_dict(row))
        if limit > 0 and len(out) >= limit:
            break
    return out


def resolve_collection_work(
    spec: str,
    *,
    collection_id: str | None = None,
) -> dict[str, Any]:
    """Resolve an ``ogc...`` ID, TLG ID, or title/slug query to one catalogued work."""
    raw = spec.strip()
    if not raw:
        raise ValueError("work specifier must be non-empty")

    col_filter = collection_id
    if ":" in raw and col_filter is None:
        head, _, tail = raw.partition(":")
        h_clean = head.strip().lower().removesuffix("-corpus")
        if h_clean in COLLECTION_IDS:
            col_filter = h_clean
            raw = tail.strip()

    idx = _load_index()
    works = idx.get("works", ())
    raw_low = raw.lower()
    raw_fold = _fold(raw)

    # 1. Exact work_id (ogc002060) or TLG ID (tlg2062.tlg152)
    for row in works:
        if col_filter and row[1] != col_filter:
            continue
        if str(row[0]).lower() == raw_low or (row[4] and str(row[4]).lower() == raw_low):
            return _row_to_dict(row)

    # 2. Exact title match
    exact_title = [
        row
        for row in works
        if (not col_filter or row[1] == col_filter) and _fold(str(row[3])) == raw_fold
    ]
    if len(exact_title) == 1:
        return _row_to_dict(exact_title[0])

    # 3. Substring / multi-term match across author + title + work_id + tlg
    hits = collection_works(col_filter, query=raw)
    if len(hits) == 1:
        return hits[0]
    if hits:
        # Prefer the largest matching work when unambiguous prefix/series title is requested
        # only if caller asked via exact substring of a single title; otherwise pick best score
        title_hits = [h for h in hits if raw_fold in _fold(h["title"])]
        if len(title_hits) == 1:
            return title_hits[0]
        ranked = sorted(title_hits or hits, key=lambda h: (-h["tokens"], h["work_id"]))
        sample = ", ".join(f"{h['work_id']} ({h['author']}: {h['title'][:40]})" for h in ranked[:5])
        raise ValueError(
            f"ambiguous Greek work {spec!r} matched {len(hits)} works; "
            f"pass an explicit work_id such as: {sample}"
        )

    scope = f" in {col_filter!r}" if col_filter else ""
    raise ValueError(
        f"no Greek collection work matched {spec!r}{scope}; "
        "use aegean.greek.collection_works(query=...) or `aegean library search` to browse."
    )


def _load_bundle(collection_id: str, *, allow_fetch: bool = True, force: bool = False) -> dict[str, Any]:
    cid = collection_id.strip().lower().removesuffix("-corpus")
    if cid not in COLLECTION_IDS:
        raise ValueError(
            f"unknown Greek collection {collection_id!r}; expected one of: " + ", ".join(COLLECTION_IDS)
        )
    if cid in _BUNDLE_CACHE and not force:
        return _BUNDLE_CACHE[cid]

    from ...data import _REMOTE, DataNotAvailableError, cache_dir, fetch, load_gzip_json, present_paths

    asset = f"{cid}-corpus"
    spec = _REMOTE[asset]
    paths = [] if force else present_paths(spec, cache_dir())
    if not paths:
        if not allow_fetch:
            raise DataNotAvailableError(
                f"{asset} is not cached — run `aegean library install {asset}` or pass offline=False"
            )
        path = fetch(asset, force=force)
    else:
        path = paths[0]
    data: dict[str, Any] = load_gzip_json(path)
    _BUNDLE_CACHE[cid] = data
    return data


def _work_entry_to_doc(wid: str, entry: dict[str, Any]) -> Any:
    from ...core.model import Document, DocumentMeta, Token, TokenKind
    from ...greek.tokenize import tokenize

    info = entry.get("_info", {})
    tokens: list[Token] = []
    lines: list[list[int]] = []
    for pair in entry.get("passages", ()):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        locus = str(pair[0] or "")
        text = str(pair[1] or "")
        line_no = len(lines)
        idxs: list[int] = []
        for tok in tokenize(text):
            if not any(ch.isalpha() for ch in tok.text):
                continue
            word = unicodedata.normalize("NFC", tok.text)
            pos = len(tokens)
            tokens.append(
                Token(
                    text=word,
                    kind=TokenKind.WORD,
                    glyphs=word,
                    line_no=line_no,
                    position=pos,
                    annotations={"ref": locus} if locus else {},
                )
            )
            idxs.append(pos)
        if idxs:
            lines.append(idxs)

    author = str(info.get("author", "") or "")
    title = str(info.get("title", wid) or wid)
    tlg = str(info.get("tlg", "") or "")
    src = str(info.get("source", "") or "")
    lic = str(info.get("license", "") or "")
    corr = str(info.get("correction", "") or "")
    ed = str(info.get("edition", "") or "")
    notes_list = [f"work_id={wid}"]
    if tlg:
        notes_list.append(f"tlg={tlg}")
    if ed:
        notes_list.append(f"edition={ed}")
    if src:
        notes_list.append(f"source={src}")
    if corr:
        notes_list.append(f"correction={corr}")
    if lic:
        notes_list.append(f"license={lic}")

    return Document(
        id=wid,
        script_id="greek",
        tokens=tokens,
        lines=lines,
        meta=DocumentMeta(
            name=f"{author}: {title}" if author else title,
            period=str(info.get("period", "") or ""),
            notes=tuple(notes_list),
        ),
    )


def load_collection(
    collection_id: str,
    *,
    work: str | None = None,
    author: str | None = None,
    offline: bool = False,
    force: bool = False,
) -> Any:
    """Load a categorized Greek corpus collection, one author, or a single work.

    Examples
    --------
    >>> load_collection("chrysostom", work="In Matthaeum")
    >>> load_collection("church-fathers-early", author="Basilius")
    >>> load_collection("byzantine-lit", work="Alexias")
    """
    from ...core.corpus import Corpus
    from ...core.provenance import Provenance

    cid = collection_id.strip().lower().removesuffix("-corpus")
    bundle = _load_bundle(cid, allow_fetch=not offline, force=force)
    meta = bundle.get("_meta", {})
    works_map: dict[str, Any] = bundle.get("works", {})

    if work is not None:
        resolved = resolve_collection_work(work, collection_id=cid)
        wid = resolved["work_id"]
        entry = works_map.get(wid)
        if entry is None:
            raise ValueError(f"work {wid!r} not found in {cid}-corpus bundle")
        selected = [(wid, entry)]
        scope_label = f"{resolved['author']}: {resolved['title']} ({wid})"
    elif author is not None:
        auth_fold = _fold(author.strip())
        selected = [
            (wid, entry)
            for wid, entry in sorted(works_map.items())
            if auth_fold in _fold(str(entry.get("_info", {}).get("author", "")))
        ]
        if not selected:
            raise ValueError(f"no works by author {author!r} in {cid!r}")
        scope_label = f"{author} in {meta.get('title', cid)} ({len(selected)} works)"
    else:
        selected = sorted(works_map.items())
        scope_label = f"{meta.get('title', cid)} ({len(selected)} works)"

    docs = [_work_entry_to_doc(wid, entry) for wid, entry in selected]
    prov = Provenance(
        source=scope_label,
        license=meta.get("license", "CC BY-SA 4.0 / CC BY 4.0 / Public Domain"),
        url=meta.get("source_repo", "https://github.com/open-greek/open-greek-corpus"),
        data_version=meta.get("source_release", meta.get("source_commit")),
        notes=(
            f"Loaded from SHA-256-pinned {cid}-corpus release asset; "
            "per-work license, edition, and OCR correction status are preserved in Document.meta.notes.",
        ),
    )
    return Corpus(docs, script_id="greek", provenance=prov)


def load_collection_work(
    work_spec: str,
    *,
    collection_id: str | None = None,
    offline: bool = False,
    force: bool = False,
) -> Any:
    """Resolve and load a single Greek work from any of the 8 collections."""
    resolved = resolve_collection_work(work_spec, collection_id=collection_id)
    return load_collection(
        resolved["collection"],
        work=resolved["work_id"],
        offline=offline,
        force=force,
    )


def _make_collection_loader(cid: str) -> Any:
    def _loader() -> Any:
        return load_collection(cid)

    _loader.__name__ = f"load_{cid.replace('-', '_')}"
    _loader.__doc__ = f"Load the {cid} Greek corpus collection as a `Corpus` (opt-in, fetched)."
    return _loader


for _cid in COLLECTION_IDS:
    register_loader(_cid, _make_collection_loader(_cid), fresh=True)
