"""Read-only Library Manager MCP tools (status, packs, and resource discovery)."""

from __future__ import annotations

from typing import Any


def library_status() -> dict[str, Any]:
    """Inspect the unified pyaegean library: bundled vs installed corpora, 10 themed packs
    (biblical, church-fathers, patristic, ancient-greek, byzantine-pack, aegean, epigraphy,
    literary, lexica, neural), 3,844 categorized Greek collection works, cached Perseus/
    First1KGreek works, and total disk footprint. Strictly read-only, never downloads."""
    from .. import library as lib

    return {
        "summary": lib.summary(),
        "packs": [ps.to_dict() for ps in lib.list_packs()],
    }


def library_search(
    query: str,
    category: str | None = None,
    installed_only: bool = False,
    limit: int = 25,
) -> dict[str, Any]:
    """Search across all 47 hosted datasets, 5 bundled corpora, 3,844 categorized Greek
    collection works, 1,778 Perseus/First1KGreek works, 112 patristic commentaries,
    5 lexica, and neural models by ID, author, title, or alias. Offline, strictly read-only."""
    from .. import library as lib

    q = query.strip()
    if not q:
        return {"error": "query must be non-empty (e.g. 'patrologia', 'Iliad', 'Cyril', 'damos')"}
    try:
        hits = lib.search(
            q,
            category=category,
            status="installed" if installed_only else None,
            limit=limit,
        )
        return {
            "query": q,
            "category": category,
            "count": len(hits),
            "items": [it.to_dict() for it in hits],
        }
    except ValueError as exc:
        return {"error": str(exc)}
