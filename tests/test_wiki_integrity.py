"""Wiki structural integrity: every page is navigable and no stale benchmark blob-links remain.

The wiki publishes flat files with a hand-maintained ``_Sidebar.md``; a new page is invisible until
it is added there. These checks keep the sidebar complete (no orphan pages) and keep the benchmark
references pointing at the in-wiki [Benchmarks](Benchmarks) page rather than a repo blob URL.
"""

from __future__ import annotations

from pathlib import Path

WIKI = Path(__file__).resolve().parents[1] / "wiki"


def test_every_wiki_page_is_linked_from_the_sidebar() -> None:
    sidebar = (WIKI / "_Sidebar.md").read_text(encoding="utf-8")
    for page in sorted(WIKI.glob("*.md")):
        if page.name.startswith("_"):
            continue
        slug = page.stem  # GitHub wiki links by the hyphenated basename, no .md
        assert f"({slug})" in sidebar, f"{page.name} is orphaned (not in _Sidebar.md)"


def test_the_new_reference_pages_exist() -> None:
    for name in ("Benchmarks", "Methodology", "TUI", "MCP", "New-Testament", "Evaluation", "Translation"):
        assert (WIKI / f"{name}.md").exists(), f"wiki/{name}.md is missing"


def test_no_wiki_page_links_benchmarks_by_repo_blob_url() -> None:
    """Benchmark references resolve to the in-wiki page, not a github blob URL."""
    for page in WIKI.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        assert "blob/main/docs/benchmarks.md" not in text, (
            f"{page.name} still links docs/benchmarks.md by blob URL; use [Benchmarks](Benchmarks)"
        )
