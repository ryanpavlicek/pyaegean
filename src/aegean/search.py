"""Unified full-text search with lazy SQLite FTS5 sidecar indexes.

Provides one fast, diacritic-insensitive search surface across every text source
in pyaegean:

- **Registered corpora** (bundled or hosted): ``lineara``, ``damos``, ``isicily``,
  ``aphrodisias``, ``crete``, ``apostolic-fathers``, ``pseudepigrapha``,
  ``byzantine``, ``homer-scholia``, ``nt``, ``ddbdp``, ``patrologia``, ...
- **Biblical & Patristic bundles**: ``lxx`` (all 56 Septuagint books),
  ``nt`` / ``nt-editions`` (any of the 9 Greek NT editions), ``PG073`` (or any
  *Patrologia Graeca* volume), or ``tlg0012.tlg001`` (Perseus / First1KGreek work).
- **Local files**: ``.json``, ``.json.gz``, or ``.db``/``.sqlite`` corpora.

For large on-disk JSON/JSON.gz corpora (such as the 6.79M-word *Patrologia
Graeca* archive, 55-book Swete LXX, 9-edition NT bundle, or epigraphic corpora),
a local SQLite FTS5 sidecar database is built once under
``PYAEGEAN_CACHE/fts/`` and invalidated automatically if the source file's
mtime or size changes. Warm queries typically complete in under 50 ms without
deserializing JSON.

Zero non-stdlib dependencies; lazily exported as ``aegean.search``.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core.corpus import Corpus

__all__ = [
    "SearchHit",
    "clear_fts_cache",
    "fold_greek",
    "fts_index_path",
    "search_corpus",
    "search_text",
]

_SCHEMA_VERSION = "3"
_PG_RE = re.compile(r"^PG\d+(?:_\d+)?$", re.IGNORECASE)
_TLG_RE = re.compile(r"^(?:tlg|stoa)\d+\.(?:tlg|stoa)\d+$", re.IGNORECASE)
_OGC_RE = re.compile(r"^ogc\d{4,}$", re.IGNORECASE)
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked full-text match across any pyaegean corpus or text archive."""

    source: str
    doc_id: str
    ref: str
    snippet: str
    text: str
    score: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fold_greek(text: str) -> str:
    """Lowercase and strip Greek/Unicode combining marks; fold final sigma ``ς -> σ``."""
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return stripped.lower().replace("ς", "σ")


def _extract_snippet(text: str, query: str, *, radius: int = 120) -> str:
    """Build a compact excerpt centered around the first match of ``query``."""
    if len(text) <= radius * 2 + 20:
        return text.strip()
    folded_text = fold_greek(text)
    terms = _WORD_RE.findall(fold_greek(query))
    pos = -1
    for term in terms:
        pos = folded_text.find(term)
        if pos >= 0:
            break
    if pos < 0:
        return text[: radius * 2].strip() + "…"
    # Map approximate folded index back to original string (safe because NFD stripping
    # only removes combining marks, so original index >= folded index).
    orig_pos = min(len(text) - 1, pos)
    if orig_pos < len(text):
        # Refine by scanning a small window forward to locate the matching word.
        needle = terms[0] if terms else ""
        if needle:
            step = 0
            idx = 0
            for i, ch in enumerate(text):
                if unicodedata.category(unicodedata.normalize("NFD", ch)[0]) != "Mn":
                    if step >= pos:
                        idx = i
                        break
                    step += 1
            orig_pos = idx
    lo = max(0, orig_pos - radius)
    hi = min(len(text), orig_pos + radius)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi].strip()}{suffix}"


def _fts_dir() -> Path:
    from .data import cache_dir

    d = cache_dir() / "fts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fts_index_path(source_path: Path | str, *, tag: str = "") -> Path:
    """Return the sidecar SQLite FTS5 path for an on-disk corpus file."""
    path = Path(source_path)
    key_src = f"{path.resolve()}::{tag}::v{_SCHEMA_VERSION}"
    digest = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:16]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.name)[:48]
    return _fts_dir() / f"{stem}.{digest}.fts.db"


def clear_fts_cache() -> int:
    """Delete all cached SQLite FTS5 sidecar files; return bytes reclaimed."""
    d = _fts_dir()
    reclaimed = 0
    for path in d.glob("*.fts.db*"):
        try:
            reclaimed += path.stat().st_size
            path.unlink()
        except OSError:
            pass
    return reclaimed


def _read_json_any(path: Path) -> Any:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8-sig"))


def _sigla_attestation_text(attestations: list[Any]) -> str:
    """Reconstruct hyphen-joined words and standalone signs from SigLA v1/v2 attestations."""
    words: list[str] = []
    pending: list[str] = []
    pending_word: int | None = None

    def flush() -> None:
        nonlocal pending, pending_word
        if pending:
            words.append("-".join(pending))
            pending = []
            pending_word = None

    for att in attestations:
        if not isinstance(att, dict):
            continue
        sign = str(att.get("sign") or "").strip()
        kind = att.get("kind")
        word = att.get("word")
        if kind is None:
            if sign:
                words.append(sign)
            continue
        if word is not None and kind in ("syllable", "blank"):
            if pending_word is not None and word != pending_word:
                flush()
            pending_word = word
            pending.append(sign or "*?")
            continue
        flush()
        if kind == "logogram" and sign:
            words.append(sign)
    flush()
    return " ".join(words).strip()


def _iter_json_rows(
    source_path: Path,
    *,
    source_label: str,
    edition: str | None = None,
) -> Iterable[tuple[str, str, str, str, str]]:
    """Yield ``(doc_id, ref, scope, raw_text, meta_json)`` rows from any pyaegean JSON asset."""
    data = _read_json_any(source_path)

    # 1. Patrologia Graeca archive:
    #    - Hosted v1 schema: {"volumes": {"PG073": {"_info": {"vol_id", "author", "title"}, "pages": [{"page", "text"}]}}}
    #    - Legacy list schema: {"volumes": [{"id", "author", "title", "pages": [{"page", "text"}]}]}
    if isinstance(data, dict) and isinstance(data.get("volumes"), (dict, list)):
        vols = data["volumes"]
        vol_iter: Iterable[tuple[str, dict[str, Any]]]
        if isinstance(vols, dict):
            vol_iter = ((str(k), v) for k, v in vols.items() if isinstance(v, dict))
        else:
            vol_iter = ((str(v.get("id", "")), v) for v in vols if isinstance(v, dict))
        for default_vid, vol in vol_iter:
            raw_info = vol.get("_info")
            info: dict[str, Any] = raw_info if isinstance(raw_info, dict) else vol
            vid = str(info.get("vol_id") or info.get("id") or default_vid)
            author = str(info.get("author", ""))
            title = str(info.get("title", ""))
            meta_base = json.dumps({"author": author, "title": title, "volume": vid}, ensure_ascii=False)
            for pg in vol.get("pages", ()):
                if not isinstance(pg, dict):
                    continue
                pnum = pg.get("page", "")
                text = str(pg.get("text", "")).strip()
                if text:
                    yield (vid, f"{vid} p.{pnum}", vid.lower(), text, meta_base)
        return

    # 1b. Work-indexed Greek library collection:
    #     {"works": {work_id: {"_info": {...}, "passages": [[locus, text], ...]}}}
    if isinstance(data, dict) and isinstance(data.get("works"), dict):
        col_id = str((data.get("_meta") or {}).get("collection", source_label))
        for wid, entry in data["works"].items():
            if not isinstance(entry, dict):
                continue
            info = entry.get("_info") or {}
            author = str(info.get("author", ""))
            title = str(info.get("title", wid))
            tlg = str(info.get("tlg", ""))
            meta_base = json.dumps(
                {
                    "work_id": wid,
                    "author": author,
                    "title": title,
                    "collection": col_id,
                    "tlg": tlg,
                    "license": str(info.get("license", "")),
                    "correction": str(info.get("correction", "")),
                },
                ensure_ascii=False,
            )
            scope = wid.lower()
            for pair in entry.get("passages", ()):
                if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                    continue
                locus = str(pair[0] or "").strip()
                text = str(pair[1] or "").strip()
                if text:
                    ref = f"{wid} {locus}".strip() if locus else wid
                    yield (wid, ref, scope, text, meta_base)
        return

    # 2. Swete Septuagint bundle:
    #    - Hosted v1/v2 schema: {"books": {book_code: {"_info": {...}, "verses": {verse_ref: text}}}}
    #    - Flat schema: {"books": {book_code: {verse_ref: text}}}
    if isinstance(data, dict) and isinstance(data.get("books"), dict) and "editions" not in data:
        for book, book_obj in data["books"].items():
            if not isinstance(book_obj, dict):
                continue
            if isinstance(book_obj.get("verses"), dict):
                raw_book_info = book_obj.get("_info")
                book_info: dict[str, Any] = raw_book_info if isinstance(raw_book_info, dict) else {}
                verses = book_obj["verses"]
                meta_info: dict[str, Any] = {"book": book}
                if book_info.get("title"):
                    meta_info["title"] = str(book_info["title"])
                if book_info.get("section"):
                    meta_info["section"] = str(book_info["section"])
                meta_j = json.dumps(meta_info, ensure_ascii=False)
            else:
                verses = book_obj
                meta_j = json.dumps({"book": book}, ensure_ascii=False)
            for vref, text in verses.items():
                if not isinstance(text, str):
                    continue
                t = text.strip()
                if t:
                    yield (book, f"{book} {vref}", book.lower(), t, meta_j)
        return

    # 3. Multi-edition Greek NT bundle: {"editions": {ed: {"books": {book: {vref: text}}}}}
    if isinstance(data, dict) and isinstance(data.get("editions"), dict):
        eds = data["editions"]
        chosen = [edition] if edition and edition in eds else list(eds.keys())
        for ed in chosen:
            ed_obj = eds.get(ed)
            if not isinstance(ed_obj, dict):
                continue
            for book, verses in (ed_obj.get("books") or {}).items():
                if not isinstance(verses, dict):
                    continue
                meta_j = json.dumps({"book": book, "edition": ed}, ensure_ascii=False)
                for vref, text in verses.items():
                    t = str(text).strip()
                    if t:
                        yield (f"{ed}:{book}", f"{book} {vref} ({ed})", f"{ed.lower()}:{book.lower()}", t, meta_j)
        return

    # 4. Standard pyaegean Corpus JSON, compact NT corpus JSON, DAMOS, and SigLA:
    #    {"documents": [{"id", "tokens" | "content" | "attestations", ...}]}
    if isinstance(data, dict) and isinstance(data.get("documents"), list):
        for doc in data["documents"]:
            if not isinstance(doc, dict):
                continue
            did = str(doc.get("id", ""))
            raw_meta = doc.get("meta")
            meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
            doc_book = str(doc.get("book") or (did.split()[0] if did else ""))
            doc_chapter = doc.get("chapter")
            tokens = doc.get("tokens") or []
            if tokens:
                # If tokens carry verse refs (either standard annotations["ref"] or compact
                # nt-corpus {"t": ..., "v": ...}), group per verse for crisp verse-level hits.
                grouped: dict[str, list[str]] = {}
                has_refs = False
                for tok in tokens:
                    if isinstance(tok, dict):
                        ann = tok.get("annotations")
                        txt = str(tok.get("text") if "text" in tok else tok.get("t", ""))
                        vref = ann.get("ref") if isinstance(ann, dict) else None
                        if not vref and "v" in tok and doc_book and doc_chapter is not None:
                            vref = f"{doc_book}.{doc_chapter}.{tok['v']}"
                    else:
                        txt = str(tok)
                        vref = None
                    if vref:
                        has_refs = True
                        grouped.setdefault(str(vref), []).append(txt)
                if has_refs:
                    meta_j = json.dumps({"book": doc_book, "doc_id": did}, ensure_ascii=False)
                    for vref, words in grouped.items():
                        yield (did, vref, doc_book.lower(), " ".join(w for w in words if w), meta_j)
                else:
                    words = [
                        str(tok.get("text") if "text" in tok else tok.get("t", ""))
                        if isinstance(tok, dict)
                        else str(tok)
                        for tok in tokens
                    ]
                    raw_text = " ".join(w for w in words if w).strip()
                    if raw_text:
                        meta_info = {
                            k: v
                            for k, v in (
                                ("site", meta.get("site")),
                                ("period", meta.get("period")),
                                ("name", meta.get("name")),
                            )
                            if v
                        }
                        yield (
                            did,
                            did,
                            did.lower(),
                            raw_text,
                            json.dumps(meta_info, ensure_ascii=False),
                        )
            elif isinstance(doc.get("content"), str):
                # DAMOS Linear B corpus: {"id", "heading_short", "site", "scribe", "content"}
                raw_text = doc["content"].strip()
                if raw_text:
                    ref = str(doc.get("heading_short") or doc.get("heading") or did)
                    meta_info = {
                        k: v
                        for k, v in (
                            ("site", doc.get("site")),
                            ("scribe", doc.get("scribe")),
                            ("period", doc.get("chronology")),
                            ("heading", doc.get("heading")),
                        )
                        if v
                    }
                    yield (
                        did,
                        ref,
                        did.lower(),
                        raw_text,
                        json.dumps(meta_info, ensure_ascii=False),
                    )
            elif isinstance(doc.get("attestations"), list):
                # SigLA Linear A corpus: {"id", "site", "period", "typology", "attestations": [...]}
                raw_text = _sigla_attestation_text(doc["attestations"])
                if raw_text:
                    meta_info = {
                        k: v
                        for k, v in (
                            ("site", doc.get("site")),
                            ("period", doc.get("period")),
                            ("support", doc.get("typology")),
                        )
                        if v
                    }
                    yield (
                        did,
                        did,
                        did.lower(),
                        raw_text,
                        json.dumps(meta_info, ensure_ascii=False),
                    )
        return


def _ensure_fts_index(
    source_path: Path,
    *,
    source_label: str,
    edition: str | None = None,
) -> Path:
    """Return a valid, up-to-date SQLite FTS5 sidecar path, building it lazily if needed."""
    st = source_path.stat()
    tag = edition or ""
    idx_path = fts_index_path(source_path, tag=tag)

    if idx_path.exists():
        try:
            con = sqlite3.connect(f"file:{idx_path}?mode=ro", uri=True)
            try:
                meta = dict(con.execute("SELECT k, v FROM _meta").fetchall())
                if (
                    meta.get("schema_version") == _SCHEMA_VERSION
                    and meta.get("mtime_ns") == str(st.st_mtime_ns)
                    and meta.get("size") == str(st.st_size)
                ):
                    return idx_path
            finally:
                con.close()
        except sqlite3.Error:
            pass

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".fts-build-", suffix=".db", dir=str(idx_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        con = sqlite3.connect(str(tmp_path))
        try:
            con.execute("PRAGMA journal_mode=OFF")
            con.execute("PRAGMA synchronous=OFF")
            con.execute("CREATE TABLE _meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            con.execute(
                "CREATE TABLE docs ("
                "id INTEGER PRIMARY KEY, "
                "doc_id TEXT NOT NULL, "
                "ref TEXT NOT NULL, "
                "scope TEXT NOT NULL, "
                "raw_text TEXT NOT NULL, "
                "meta_json TEXT NOT NULL)"
            )
            con.execute(
                "CREATE VIRTUAL TABLE docs_fts USING fts5("
                "folded_text, raw_text, content='', tokenize='unicode61')"
            )
            batch_docs: list[tuple[int, str, str, str, str, str]] = []
            batch_fts: list[tuple[int, str, str]] = []
            row_id = 0
            for doc_id, ref, scope, raw_text, meta_json in _iter_json_rows(
                source_path, source_label=source_label, edition=edition
            ):
                row_id += 1
                batch_docs.append((row_id, doc_id, ref, scope, raw_text, meta_json))
                batch_fts.append((row_id, fold_greek(raw_text), raw_text))
                if len(batch_docs) >= 2000:
                    con.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", batch_docs)
                    con.executemany(
                        "INSERT INTO docs_fts(rowid, folded_text, raw_text) VALUES (?,?,?)",
                        batch_fts,
                    )
                    batch_docs.clear()
                    batch_fts.clear()
            if batch_docs:
                con.executemany("INSERT INTO docs VALUES (?,?,?,?,?,?)", batch_docs)
                con.executemany(
                    "INSERT INTO docs_fts(rowid, folded_text, raw_text) VALUES (?,?,?)",
                    batch_fts,
                )
            con.executemany(
                "INSERT INTO _meta VALUES (?, ?)",
                [
                    ("schema_version", _SCHEMA_VERSION),
                    ("source_path", str(source_path.resolve())),
                    ("mtime_ns", str(st.st_mtime_ns)),
                    ("size", str(st.st_size)),
                    ("source_label", source_label),
                    ("rows", str(row_id)),
                ],
            )
            con.commit()
        finally:
            con.close()
        os.replace(tmp_path, idx_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return idx_path


def _fts_query_expr(query: str, *, exact: bool) -> tuple[str, list[str]]:
    """Build a safe FTS5 MATCH query string and normalized token list."""
    raw = query.strip()
    if not raw:
        return "", []
    tokens = _WORD_RE.findall(raw if exact else fold_greek(raw))
    if not tokens:
        return "", []
    col = "raw_text" if exact else "folded_text"
    if len(tokens) == 1:
        tok = tokens[0].replace('"', '""')
        return f'{col}:"{tok}"', tokens
    phrase = " ".join(t.replace('"', '""') for t in tokens)
    return f'{col}:"{phrase}"', tokens


def _query_fts_sidecar(
    idx_path: Path,
    query: str,
    *,
    source_label: str,
    limit: int = 25,
    exact: bool = False,
    scope_filter: str | None = None,
) -> list[SearchHit]:
    match_expr, _tokens = _fts_query_expr(query, exact=exact)
    if not match_expr:
        return []
    con = sqlite3.connect(f"file:{idx_path}?mode=ro", uri=True)
    try:
        params: list[Any] = [match_expr]
        where_extra = ""
        if scope_filter:
            sf = scope_filter.strip().lower()
            where_extra = " AND (d.scope = ? OR d.scope LIKE ? OR lower(d.doc_id) = ?)"
            params.extend([sf, f"%:{sf}", sf])
        params.append(-1 if int(limit) <= 0 else int(limit))
        sql = (
            "SELECT d.doc_id, d.ref, d.raw_text, d.meta_json, -bm25(docs_fts) AS rank "
            "FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid "
            f"WHERE docs_fts MATCH ?{where_extra} "
            "ORDER BY rank DESC LIMIT ?"
        )
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    hits: list[SearchHit] = []
    for doc_id, ref, raw_text, meta_json, rank in rows:
        meta = json.loads(meta_json) if meta_json else {}
        hits.append(
            SearchHit(
                source=source_label,
                doc_id=doc_id,
                ref=ref,
                snippet=_extract_snippet(raw_text, query),
                text=raw_text[:2000],
                score=round(float(rank), 4),
                meta=meta,
            )
        )
    return hits


def search_corpus(
    corpus: "Corpus",
    query: str,
    *,
    source: str = "",
    limit: int = 25,
    exact: bool = False,
) -> list[SearchHit]:
    """Search an already-loaded in-memory :class:`~aegean.core.corpus.Corpus`."""
    q = query.strip()
    if not q:
        return []
    needle = q if exact else fold_greek(q)
    label = source or getattr(corpus, "script_id", None) or "corpus"
    hits: list[SearchHit] = []
    for doc in corpus:
        # Group by verse ref when present (e.g. NT/LXX corpora).
        grouped: dict[str, list[str]] = {}
        has_refs = False
        for tok in doc.tokens:
            vref = tok.annotations.get("ref")
            if vref:
                has_refs = True
                grouped.setdefault(str(vref), []).append(tok.text)
        units: list[tuple[str, str]]
        if has_refs:
            units = [(vref, " ".join(ws)) for vref, ws in grouped.items()]
        else:
            units = [(doc.id, " ".join(t.text for t in doc.tokens))]

        for ref, raw_text in units:
            hay = raw_text if exact else fold_greek(raw_text)
            if needle in hay:
                count = hay.count(needle)
                meta: dict[str, Any] = {}
                if doc.meta.site:
                    meta["site"] = doc.meta.site
                if doc.meta.period:
                    meta["period"] = doc.meta.period
                if doc.meta.name:
                    meta["name"] = doc.meta.name
                hits.append(
                    SearchHit(
                        source=label,
                        doc_id=doc.id,
                        ref=ref,
                        snippet=_extract_snippet(raw_text, q),
                        text=raw_text[:2000],
                        score=float(count),
                        meta=meta,
                    )
                )
                if limit > 0 and len(hits) >= limit:
                    return hits
    return hits


def _resolve_cached_asset(asset_name: str, *, offline: bool) -> Path:
    from .data import _REMOTE, DataNotAvailableError, cache_dir, fetch, present_paths

    if asset_name not in _REMOTE:
        raise ValueError(f"unknown dataset asset {asset_name!r}")
    spec = _REMOTE[asset_name]
    if offline:
        paths = present_paths(spec, cache_dir())
        if not paths:
            raise DataNotAvailableError(
                f"{asset_name} is not installed locally — run `aegean library install {asset_name}` "
                "or omit offline=True."
            )
        return paths[0]
    return fetch(asset_name)


def search_text(
    query: str,
    target: str = "nt",
    *,
    limit: int = 25,
    exact: bool = False,
    book: str | None = None,
    edition: str | None = None,
    offline: bool = False,
) -> list[SearchHit]:
    """Search any corpus, Bible edition, Septuagint, Patrologia Graeca, work, or local file.

    Uses lazy SQLite FTS5 sidecar indexes for on-disk JSON/JSON.gz corpora so repeated
    searches over multi-million-word archives return in milliseconds.
    """
    q = query.strip()
    if not q:
        return []
    t = target.strip()
    tl = t.lower()

    # 1. Local file path (.db/.sqlite/.json/.json.gz)
    p = Path(t)
    if p.exists() and p.is_file():
        suf = "".join(p.suffixes).lower()
        if p.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
            from . import db as aegean_db

            rows = aegean_db.search(p, q, limit=limit, mode="substring" if not exact else "token")
            return [
                SearchHit(
                    source=p.name,
                    doc_id=doc_id,
                    ref=f"{doc_id}#{pos}" if pos is not None else doc_id,
                    snippet=tok_text,
                    text=tok_text,
                    score=1.0,
                )
                for doc_id, pos, tok_text in rows
            ]
        if suf.endswith(".json") or suf.endswith(".json.gz"):
            idx = _ensure_fts_index(p, source_label=p.name, edition=edition)
            return _query_fts_sidecar(
                idx, q, source_label=p.name, limit=limit, exact=exact, scope_filter=book
            )

    # 2. Patrologia Graeca volume ID (e.g. "PG073") or "patrologia" / "pg"
    if _PG_RE.match(t) or tl in ("patrologia", "pg", "patrologia-graeca", "patrologia-graeca-corpus"):
        scope = t.upper() if _PG_RE.match(t) else (book.upper() if book else None)
        asset_path = _resolve_cached_asset("patrologia-graeca-corpus", offline=offline)
        idx = _ensure_fts_index(asset_path, source_label="patrologia")
        return _query_fts_sidecar(
            idx, q, source_label="patrologia", limit=limit, exact=exact, scope_filter=scope
        )

    # 3. Septuagint ("lxx", "septuagint", "lxx-corpus")
    if tl in ("lxx", "septuagint", "lxx-corpus"):
        from .greek.bible import lxx_loaded, search_lxx

        if offline and not lxx_loaded():
            hits_lxx = search_lxx(q, book=book, limit=limit, offline=True)
            return [
                SearchHit(
                    source="lxx",
                    doc_id=h.book,
                    ref=h.ref,
                    snippet=_extract_snippet(h.verse_text, q),
                    text=h.verse_text,
                    score=1.0,
                    meta={"book": h.book},
                )
                for h in hits_lxx
            ]
        asset_path = _resolve_cached_asset("lxx-corpus", offline=offline)
        idx = _ensure_fts_index(asset_path, source_label="lxx")
        scope = None
        if book:
            from .greek.bible import resolve_lxx_book

            scope = resolve_lxx_book(book).name.lower()
        return _query_fts_sidecar(
            idx, q, source_label="lxx", limit=limit, exact=exact, scope_filter=scope
        )

    # 4. NT editions ("nt-editions" or target="nt" with non-nestle1904 edition)
    if tl in ("nt-editions", "editions") or (tl == "nt" and edition and edition.lower() != "nestle1904"):
        ed = (edition or "sblgnt").lower()
        asset_path = _resolve_cached_asset("nt-editions", offline=offline)
        idx = _ensure_fts_index(asset_path, source_label=f"nt:{ed}", edition=ed)
        scope = None
        if book:
            from .scripts.greek.nt import _resolve_book

            scope = f"{ed}:{_resolve_book(book).lower()}"
        return _query_fts_sidecar(
            idx, q, source_label=f"nt:{ed}", limit=limit, exact=exact, scope_filter=scope
        )

    # 5. DDbDP SQLite papyri
    if tl in ("ddbdp", "ddbdp-corpus"):
        from . import db as aegean_db
        from .scripts.greek.ddbdp import ddbdp_db

        db_path = ddbdp_db()
        rows = aegean_db.search(db_path, q, limit=limit, mode="substring" if not exact else "token")
        return [
            SearchHit(
                source="ddbdp",
                doc_id=doc_id,
                ref=f"{doc_id}#{pos}" if pos is not None else doc_id,
                snippet=tok_text,
                text=tok_text,
                score=1.0,
            )
            for doc_id, pos, tok_text in rows
        ]

    # 5b. Open Greek Corpus work ID (e.g. "ogc002060") or <collection>:<work>
    if _OGC_RE.match(t) or (":" in t and t.partition(":")[0].strip().lower().removesuffix("-corpus") in {
        "chrysostom",
        "church-fathers-early",
        "church-fathers-late",
        "classical-greek",
        "hellenistic-greek",
        "imperial-greek",
        "late-antique-greek",
        "byzantine-lit",
    }):
        from .scripts.greek._collections import resolve_collection_work

        resolved = resolve_collection_work(t)
        cid = resolved["collection"]
        wid = resolved["work_id"]
        asset_path = _resolve_cached_asset(f"{cid}-corpus", offline=offline)
        idx = _ensure_fts_index(asset_path, source_label=cid)
        return _query_fts_sidecar(
            idx, q, source_label=cid, limit=limit, exact=exact, scope_filter=wid.lower()
        )

    # 6. Registered corpus via declarative catalog (FTS5 sidecar for hosted JSON, in-memory for bundled)
    from .core.catalog import CORPORA, CORPUS_BY_ID

    spec = CORPUS_BY_ID.get(tl) or CORPUS_BY_ID.get(tl.removesuffix("-corpus"))
    if spec is None:
        for cand in CORPORA:
            if tl in (a.lower() for a in cand.aliases):
                spec = cand
                break
    if spec is not None:
        if spec.bundled:
            import aegean

            return search_corpus(aegean.load(spec.id), q, source=spec.id, limit=limit, exact=exact)
        if spec.id == "nt" and offline:
            from .data import _REMOTE, cache_dir, is_downloaded

            if not is_downloaded(_REMOTE["nt-corpus"], cache_dir()):
                from .greek.bible import load_nt

                corp = load_nt(book or "John", offline=True)
                return search_corpus(corp, q, source="nt", limit=limit, exact=exact)
        if spec.asset_name:
            asset_path = _resolve_cached_asset(spec.asset_name, offline=offline)
            idx = _ensure_fts_index(asset_path, source_label=spec.id)
            scope = book.lower() if book else None
            return _query_fts_sidecar(
                idx, q, source_label=spec.id, limit=limit, exact=exact, scope_filter=scope
            )

    # 7. Perseus / First1KGreek CTS work ID (e.g. "tlg0012.tlg001")
    if _TLG_RE.match(t):
        from .greek import load_work

        corp = load_work(t)
        return search_corpus(corp, q, source=t, limit=limit, exact=exact)

    # 8. Fallback: try NT/LXX book name directly (e.g. target="John" or target="Gen")
    try:
        from .scripts.greek.nt import _resolve_book

        osis = _resolve_book(t)
        return search_text(q, "nt", limit=limit, exact=exact, book=osis, edition=edition, offline=offline)
    except ValueError:
        pass
    try:
        from .greek.bible import resolve_lxx_book

        lxx_book = resolve_lxx_book(t)
        return search_text(q, "lxx", limit=limit, exact=exact, book=lxx_book.name, offline=offline)
    except ValueError:
        pass

    from .core.resolve import CorpusNotFound, suggest

    candidates = sorted(set(CORPUS_BY_ID) | {"lxx", "nt-editions"})
    close = suggest(t, candidates, n=2)
    hint = f" — did you mean {' or '.join(repr(c) for c in close)}?" if close else ""
    raise CorpusNotFound(
        f"unknown search target {target!r}{hint}; pass a corpus id (nt, lxx, chrysostom, "
        "classical-greek, church-fathers-early, byzantine-lit, patrologia, isicily, ...), "
        "a PG volume (PG073), a work id (ogc002060, tlg0012.tlg001), or a .json/.db path"
    )
