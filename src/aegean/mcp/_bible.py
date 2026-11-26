"""Biblical, Septuagint, and Patristic Greek MCP tools."""

from __future__ import annotations

from typing import Any

from ._common import _did_you_mean


def biblical_strongs(
    query: str,
    roots: bool = False,
    search: bool = False,
    limit: int = 15,
) -> dict[str, Any]:
    """Look up or search Strong's & Extended Strong's Greek Lexicon entries (offline Dodson
    or locally cached 11,142-entry Extended Strong's; never fetches over the network)."""
    from ..greek import bible as bib

    q = query.strip()
    if not q:
        return {"error": "query must be a non-empty Strong's ID (e.g. 'G3056'), Greek lemma, or gloss"}
    try:
        if search:
            hits = bib.search_strongs(q, limit=limit, allow_fetch=False)
            return {
                "query": q,
                "count": len(hits),
                "extended_loaded": bib.strongs_loaded(),
                "matches": [h.to_dict() for h in hits],
            }
        entry = bib.strongs_entry(q, allow_fetch=False)
        if entry is None:
            return {
                "error": f"no Strong's Greek entry matched {q!r}; "
                "try search=True or a canonical Strong's ID such as 'G3056'"
            }
        out = entry.to_dict()
        if roots:
            out["root_tree"] = bib.strongs_roots(entry.strongs, allow_fetch=False)
        return out
    except ValueError as exc:
        return {"error": str(exc)}


def biblical_word_study(
    query: str,
    book: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Unified Koine Greek word study (Strong's entry, roots, NT distribution, morphology,
    and verse concordance) over the cached full NT or bundled offline Nestle 1904 sample."""
    from ..greek import bible as bib

    q = query.strip()
    if not q:
        return {"error": "query must be a non-empty Strong's ID (e.g. 'G3056') or Greek lemma"}
    try:
        ws = bib.word_study(q, book=book, limit=limit, offline=True)
        return ws.to_dict()
    except ValueError as exc:
        return {"error": str(exc)}


def biblical_psalm(psalm: int, system: str = "mt") -> dict[str, Any]:
    """Convert a Psalm number between Masoretic (Hebrew/English, 'mt') and Septuagint ('lxx')
    numbering, including the First1KGreek Swete LXX work ID (tlg0527.tlg027)."""
    from ..greek import bible as bib

    try:
        return bib.convert_psalm(psalm, system=system)
    except ValueError as exc:
        return {"error": str(exc)}


def biblical_nomina_sacra(text: str) -> dict[str, Any]:
    """Expand early Greek NT manuscript nomina sacra contractions (e.g. θς → θεός, ις → ἰησοῦς,
    χς → χριστός, πνα → πνεῦμα) with an explicit list of expanded tokens."""
    from ..greek import bible as bib

    if not text.strip():
        return {"error": "text must be non-empty Greek manuscript text (e.g. 'εν αρχη ην ο λογος προς τον θν')"}
    expanded, notes = bib.expand_nomina_sacra(text)
    return {
        "input": text,
        "expanded": expanded,
        "expansions": notes,
        "count": len(notes),
    }


def biblical_catalog(
    kind: str = "editions",
    book: str | None = None,
    section: str | None = None,
) -> dict[str, Any]:
    """Offline catalogue of Biblical & Koine Greek resources: 'editions' (9 Greek NT editions),
    'witnesses' (13 2nd–5th c. CE manuscripts), 'lxx' (56 Septuagint books including
    Ecclesiastes), or 'commentaries' (112 Greek patristic volumes across 11 Church Fathers
    / traditions including 26 John Chrysostom commentary series)."""
    from ..greek import bible as bib

    k = kind.strip().lower()
    valid = ("editions", "witnesses", "lxx", "commentaries")
    if k not in valid:
        return {
            "error": f"unknown biblical catalog kind {kind!r}{_did_you_mean(k, valid)}; "
            f"choose from {', '.join(valid)}"
        }
    try:
        if k == "editions":
            rows = bib.nt_editions()
        elif k == "witnesses":
            rows = bib.witnesses()
        elif k == "lxx":
            rows = bib.lxx_books(section=section)
        else:
            rows = bib.patristic_commentaries(book=book)
        return {"kind": k, "count": len(rows), "items": rows}
    except ValueError as exc:
        return {"error": str(exc)}


def biblical_lxx(
    book: str = "Gen",
    ref: str | None = "1.1-5",
    query: str | None = None,
    numbering: str = "lxx",
    interlinear: bool = False,
    limit: int = 15,
) -> dict[str, Any]:
    """Read or search the Greek Septuagint (Swete LXX + Ecclesiastes, 56 books) offline.

    Uses cached 56-book ``lxx-corpus`` when present, or the bundled Genesis 1 +
    Psalm 22 LXX sample. Supports Masoretic Psalm numbering (``numbering='mt'``)
    and automatic offline interlinear enrichment (``interlinear=True``).
    """
    from ..data import DataNotAvailableError
    from ..greek import bible as bib

    try:
        if query is not None and query.strip():
            hits = bib.search_lxx(query.strip(), book=book or None, limit=limit, offline=True)
            return {
                "mode": "search",
                "query": query.strip(),
                "full_corpus_cached": bib.lxx_loaded(),
                "count": len(hits),
                "matches": [h.to_dict() for h in hits],
            }
        corp = bib.load_lxx(
            book,
            ref=ref,
            numbering=numbering,
            interlinear=interlinear,
            offline=True,
        )
        verses: list[dict[str, Any]] = []
        for doc in corp:
            by_ref: dict[str, list[Any]] = {}
            for tok in doc.tokens:
                rkey = str(tok.annotations.get("ref", f"{doc.id}.{tok.line_no or 0}"))
                by_ref.setdefault(rkey, []).append(tok)
            for rkey, toks in by_ref.items():
                row: dict[str, Any] = {
                    "ref": rkey,
                    "text": " ".join(t.text for t in toks),
                }
                if toks and toks[0].annotations.get("mt_ref"):
                    row["mt_ref"] = toks[0].annotations["mt_ref"]
                if interlinear:
                    row["tokens"] = [
                        {"text": t.text, **t.annotations} for t in toks
                    ]
                verses.append(row)
        return {
            "mode": "read",
            "book": book,
            "ref": ref,
            "numbering": numbering,
            "full_corpus_cached": bib.lxx_loaded(),
            "verses": verses,
        }
    except (ValueError, DataNotAvailableError) as exc:
        return {"error": str(exc)}


def biblical_compare_editions(
    book: str,
    ref: str = "1.18",
    editions: list[str] | None = None,
) -> dict[str, Any]:
    """Compare up to 9 Greek New Testament critical editions (nestle1904, sblgnt, srgnt,
    bhp, tisch, wh, byz, antoniades, tr) with word-level textual diffs (uses cached
    nt-editions locally; never downloads unexpectedly)."""
    from ..data import DataNotAvailableError
    from ..greek import bible as bib

    try:
        cmp = bib.compare_editions(book, ref, editions=editions, offline=True)
        return cmp.to_dict()
    except (ValueError, DataNotAvailableError) as exc:
        return {"error": str(exc)}


def biblical_witnesses(
    book: str,
    ref: str = "1.18",
    sigla: list[str] | None = None,
    hand: str = "original",
) -> dict[str, Any]:
    """Compare extant 2nd–5th c. CE Greek NT manuscript witnesses (Sinaiticus 01,
    Vaticanus 03, Alexandrinus 02, Bezae 05, P45–P75) with nomina sacra expansions
    and scribal corrections (uses cached nt-witnesses locally)."""
    from ..data import DataNotAvailableError
    from ..greek import bible as bib

    try:
        rows = bib.compare_witnesses(book, ref, sigla=sigla, hand=hand, offline=True)
        return {
            "book": book,
            "ref": ref,
            "hand": hand,
            "verses": [vc.to_dict() for vc in rows],
        }
    except (ValueError, DataNotAvailableError) as exc:
        return {"error": str(exc)}


def biblical_commentary(
    book: str = "John",
    work_id: str | None = None,
    kind: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Read or search Greek patristic biblical commentaries across 112 indexed works
    (NT Catenae, Origen, 26 John Chrysostom commentary/homily series, Cyril of Alexandria,
    Methodius, Eusebius, Clement of Alexandria, Procopius of Gaza, Photius, Oecumenius,
    and Theophylact of Bulgaria). Fetches the requested work or collection on first use."""
    from ..data import DataNotAvailableError
    from ..greek import bible as bib

    try:
        rows = bib.commentary_excerpt(
            book,
            work_id=work_id,
            kind=kind,
            query=query,
            limit=limit,
        )
        return {
            "book": book,
            "work_id": work_id,
            "query": query,
            "count": len(rows),
            "excerpts": [r.to_dict() for r in rows],
        }
    except (ValueError, DataNotAvailableError) as exc:
        return {"error": str(exc)}
