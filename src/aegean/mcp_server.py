"""An MCP server exposing pyaegean to agents (Claude Code and other MCP clients).

The ``[mcp]`` extra installs the Model Context Protocol SDK; ``aegean-mcp`` then runs a
stdio MCP server that wraps the toolkit's read/analysis surface as tools — load and inspect
corpora, wildcard sign search, accounting reconciliation, the Greek pipeline, verse scansion,
and Koine glossing — so an agent can use pyaegean without writing Python.

The tool functions are plain, JSON-returning callables (independently testable); ``build_server``
registers them with FastMCP, imported lazily so ``import aegean`` never pulls the MCP SDK.
"""

from __future__ import annotations

import dataclasses
from typing import Any

__all__ = ["build_server", "main"]


def list_corpora() -> list[str]:
    """List the corpora that can be loaded by name (bundled, or fetched on demand)."""
    from .core.corpus import _LOADERS

    return sorted(_LOADERS)


def corpus_info(corpus: str) -> dict[str, Any]:
    """Overview of a corpus: script, document count, source, license, and a citation.

    ``corpus`` is a name from ``list_corpora`` (e.g. 'lineara', 'damos', 'nt')."""
    import aegean

    c = aegean.load(corpus)
    prov = c.provenance
    return {
        "corpus": corpus,
        "script_id": c.script_id,
        "documents": len(c),
        "source": prov.source if prov else "",
        "license": prov.license if prov else "",
        "citation": prov.cite() if prov else "",
    }


def show_document(corpus: str, doc_id: str) -> dict[str, Any]:
    """One document's metadata and text, line by line. ``doc_id`` is e.g. 'HT13'."""
    import aegean

    c = aegean.load(corpus)
    doc = c.get(doc_id)
    if doc is None:
        return {"error": f"no document {doc_id!r} in {corpus!r}"}
    return {
        "id": doc.id,
        "site": doc.meta.site,
        "period": doc.meta.period,
        "support": doc.meta.support,
        "scribe": doc.meta.scribe,
        "lines": [[t.text for t in line] for line in doc.line_tokens],
        "transcription": doc.transcription,
    }


def search_signs(corpus: str, pattern: str, limit: int = 50) -> list[dict[str, Any]]:
    """Words matching a wildcard sign pattern (e.g. 'KU-*-RO'), with frequencies."""
    import aegean

    from .analysis import word_matches_sign_pattern

    c = aegean.load(corpus)
    out: list[dict[str, Any]] = []
    for word, count in c.word_frequencies():
        if word_matches_sign_pattern(word, pattern):
            out.append({"word": word, "count": count})
            if len(out) >= limit:
                break
    return out


def balance_accounts(corpus: str, doc_id: str | None = None) -> list[dict[str, Any]]:
    """Accounting reconciliation: each stated total (KU-RO / TO-SO) vs the summed items.

    Returns one row per total marker (whole corpus, or one ``doc_id``), each with the stated
    total, computed sum, difference, and whether it balances."""
    import aegean

    from .analysis import balance_check

    c = aegean.load(corpus)
    docs = [c.get(doc_id)] if doc_id is not None else list(c.documents)
    rows: list[dict[str, Any]] = []
    for doc in docs:
        if doc is None:
            continue
        for bc in balance_check(doc):
            row = dataclasses.asdict(bc)
            row["doc_id"] = doc.id
            rows.append(row)
    return rows


def greek_pipeline(text: str) -> list[dict[str, Any]]:
    """Run the (baseline, offline) Greek NLP pipeline: per-token text, UPOS, and lemma."""
    from . import greek

    return [
        {"text": r.text, "upos": r.upos, "lemma": r.lemma, "relation": r.relation}
        for r in greek.pipeline(text)
    ]


def greek_scan(text: str, meter: str = "hexameter") -> dict[str, Any]:
    """Scan a Greek verse line. ``meter`` is 'hexameter' / 'pentameter' / 'trimeter' or an
    aeolic line type ('sapphic_hendecasyllable', 'glyconic', …). Reports the glyph pattern,
    or ``scans: false`` with the reason if the line does not fit."""
    from . import greek

    try:
        sc = greek.scan_line(text, meter)
    except greek.ScansionError as exc:
        return {"meter": meter, "scans": False, "error": str(exc)}
    return {
        "meter": sc.meter,
        "scans": True,
        "pattern": sc.pattern,
        "feet": [f.name for f in sc.feet],
        "caesura": sc.caesura,
    }


def koine_gloss(word: str) -> dict[str, Any] | None:
    """Koine (NT) gloss for a Greek word via the bundled Dodson lexicon, or ``None``."""
    from . import greek

    greek.use_dodson()
    entry = greek.lookup_nt(word)
    if entry is None:
        return None
    return {
        "word": word,
        "lemma": entry.lemma,
        "strongs": entry.strongs,
        "gloss": entry.gloss,
        "definition": entry.definition,
    }


# The tools registered with the server — also the unit-test surface.
TOOLS = (
    list_corpora,
    corpus_info,
    show_document,
    search_signs,
    balance_accounts,
    greek_pipeline,
    greek_scan,
    koine_gloss,
)


def build_server() -> Any:
    """Build a FastMCP server with every pyaegean tool registered (needs the ``[mcp]`` extra)."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("pyaegean")
    for fn in TOOLS:
        server.tool()(fn)
    return server


def main() -> None:
    """Console-script entry point (``aegean-mcp``): serve the tools over stdio."""
    try:
        server = build_server()
    except ModuleNotFoundError as exc:
        import sys

        print(
            f"aegean-mcp needs the [mcp] extra — pip install 'pyaegean[mcp]'  ({exc})",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    server.run()


if __name__ == "__main__":
    main()
