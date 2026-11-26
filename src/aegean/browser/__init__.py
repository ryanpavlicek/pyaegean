"""Local interactive visual corpus browser for Ancient, Classical, Biblical & Byzantine Greek.

Launches a zero-dependency loopback web application backed directly by PyAegean's live
Greek NLP, Biblical, lexicon, commentary, metrical scansion, search, and library engines.

Usage::

    import aegean
    aegean.browser.serve("John 1:1-18")          # opens in your browser; Ctrl-C to stop
    srv = aegean.browser.create_server("greek")  # non-blocking handle (srv.url, srv.stop())

From the command line::

    aegean browse "John 1:1-18"
    aegean browse "Gen 1:1-5" --neural
"""

from __future__ import annotations

from ._server import BrowserServer, create_server, serve
from ._service import (
    activate_lexicon_payload,
    analyze_text_payload,
    analyze_word_payload,
    bible_commentaries_payload,
    bible_commentary_excerpt_payload,
    bible_editions_payload,
    bible_psalm_payload,
    bible_witnesses_payload,
    catalog_payload,
    collections_payload,
    configure_engine_payload,
    document_payload,
    engine_status_payload,
    export_payload,
    library_fetch_payload,
    library_payload,
    scan_lines_payload,
    search_payload,
    word_study_payload,
)

__all__ = [
    "BrowserServer",
    "activate_lexicon_payload",
    "analyze_text_payload",
    "analyze_word_payload",
    "bible_commentaries_payload",
    "bible_commentary_excerpt_payload",
    "bible_editions_payload",
    "bible_psalm_payload",
    "bible_witnesses_payload",
    "catalog_payload",
    "collections_payload",
    "configure_engine_payload",
    "create_server",
    "document_payload",
    "engine_status_payload",
    "export_payload",
    "library_fetch_payload",
    "library_payload",
    "scan_lines_payload",
    "search_payload",
    "serve",
    "word_study_payload",
]
