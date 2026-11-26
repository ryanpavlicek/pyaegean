"""An MCP server exposing pyaegean to agents (Claude Code and other MCP clients).

The ``[mcp]`` extra installs the Model Context Protocol SDK; ``aegean-mcp`` then runs a
stdio MCP server that wraps the toolkit's read/analysis surface as tools, so an agent can
use pyaegean without writing Python:

* corpora & search: ``list_corpora``, ``corpus_info``, ``show_document``,
  ``search_signs``, ``search_text`` (diacritic-insensitive SQLite FTS5 across corpora,
  LXX, NT editions, and Patrologia Graeca), ``balance_accounts``, ``query_corpus``,
  ``cite_corpus``, ``geo_sites``, ``corpus_diagnose``, and ``data_status``;
* library: ``library_status`` (all 39 datasets + 7 packs + disk footprint) and
  ``library_search`` (search corpora, works, commentaries, lexica, and models);
* Greek NLP: ``greek_pipeline``, ``greek_explain``, ``greek_scan``, ``greek_catalog``,
  ``greek_work``, ``greek_gloss``, and ``koine_gloss``;
* Biblical, Septuagint & Patristic Greek: ``biblical_strongs``, ``biblical_word_study``,
  ``biblical_psalm``, ``biblical_nomina_sacra``, ``biblical_catalog``, ``biblical_lxx``,
  ``biblical_compare_editions``, ``biblical_witnesses``, and ``biblical_commentary``.

Two conventions hold across every tool. Corpora and works are addressed by **registry
name or catalogue work id only**: no tool accepts a filesystem path, so the server
never reads or writes arbitrary local files. Domain misses return a structured
``{"error": ...}`` payload carrying a did-you-mean hint instead of raising.

Tool implementations live in domain modules under :mod:`aegean.mcp`; this facade
re-exports the public surface, ``TOOLS``, ``build_server``, and ``main``.
"""

from __future__ import annotations

from typing import Any

from .mcp._bible import (
    biblical_catalog,
    biblical_commentary,
    biblical_compare_editions,
    biblical_lxx,
    biblical_nomina_sacra,
    biblical_psalm,
    biblical_strongs,
    biblical_witnesses,
    biblical_word_study,
)
from .mcp._common import (  # noqa: F401 — test monkeypatch seam
    _dictionary_unavailable as _dictionary_unavailable,
    _did_you_mean as _did_you_mean,
    _find_doc as _find_doc,
    _human_size as _human_size,
    _load_corpus_impl as _load_corpus,
)
from .mcp._corpora import (
    balance_accounts,
    cite_corpus,
    corpus_diagnose,
    corpus_info,
    data_status,
    geo_sites,
    list_corpora,
    query_corpus,
    search_signs,
    search_text,
    show_document,
)
from .mcp._greek import (
    greek_catalog,
    greek_explain,
    greek_gloss,
    greek_pipeline,
    greek_scan,
    greek_work,
    koine_gloss,
)
from .mcp._library import (
    library_search,
    library_status,
)

__all__ = [
    "TOOLS",
    "build_server",
    "main",
    "list_corpora",
    "corpus_info",
    "show_document",
    "search_signs",
    "search_text",
    "balance_accounts",
    "query_corpus",
    "cite_corpus",
    "geo_sites",
    "data_status",
    "library_status",
    "library_search",
    "greek_pipeline",
    "greek_explain",
    "greek_scan",
    "greek_catalog",
    "greek_work",
    "greek_gloss",
    "koine_gloss",
    "corpus_diagnose",
    "biblical_strongs",
    "biblical_word_study",
    "biblical_psalm",
    "biblical_nomina_sacra",
    "biblical_catalog",
    "biblical_lxx",
    "biblical_compare_editions",
    "biblical_witnesses",
    "biblical_commentary",
]

# The tools registered with the server — also the unit-test surface.
TOOLS = (
    list_corpora,
    corpus_info,
    show_document,
    search_signs,
    search_text,
    balance_accounts,
    query_corpus,
    cite_corpus,
    geo_sites,
    data_status,
    library_status,
    library_search,
    greek_pipeline,
    greek_explain,
    greek_scan,
    greek_catalog,
    greek_work,
    greek_gloss,
    koine_gloss,
    corpus_diagnose,
    biblical_strongs,
    biblical_word_study,
    biblical_psalm,
    biblical_nomina_sacra,
    biblical_catalog,
    biblical_lxx,
    biblical_compare_editions,
    biblical_witnesses,
    biblical_commentary,
)


def build_server() -> Any:
    """Build an ``MCPServer`` with every pyaegean tool registered (needs the ``[mcp]`` extra)."""
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("pyaegean")
    for fn in TOOLS:
        server.tool()(fn)
    return server


def main() -> None:
    """Console-script entry point (``aegean-mcp``): serve the tools over stdio."""
    try:
        server = build_server()
    except ModuleNotFoundError as exc:
        import importlib.util
        import sys

        if importlib.util.find_spec("mcp") is not None:
            msg = "aegean-mcp needs a newer MCP SDK — pip install -U 'mcp>=2'"
        else:
            msg = "aegean-mcp needs the [mcp] extra — pip install 'pyaegean[mcp]'"
        print(f"{msg}  ({exc})", file=sys.stderr)
        raise SystemExit(1) from None
    server.run()


if __name__ == "__main__":
    main()
