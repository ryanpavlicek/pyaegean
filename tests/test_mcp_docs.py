"""The wiki's MCP documentation must track the registered tool surface.

``aegean.mcp_server.TOOLS`` is the single source of truth; each wiki page that
describes the MCP server has to name every tool, so a new tool cannot ship
undocumented. The guard reads the pages as text (a tool's ``__name__`` appearing
anywhere on the page counts: prose, a list, or a table)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean import mcp_server as m

_WIKI = Path(__file__).resolve().parents[1] / "wiki"
_PAGES = ("CLI.md", "CLI-Cheatsheet.md", "Data-and-Provenance.md", "Installation.md")


def test_every_mcp_tool_is_named_on_every_mcp_page() -> None:
    if not _WIKI.is_dir():
        pytest.skip("wiki/ is not present in this checkout")
    missing: list[str] = []
    for page in _PAGES:
        text = (_WIKI / page).read_text(encoding="utf-8")
        for fn in m.TOOLS:
            if fn.__name__ not in text:
                missing.append(f"{page}: {fn.__name__}")
    assert missing == [], "undocumented MCP tools: " + ", ".join(missing)
