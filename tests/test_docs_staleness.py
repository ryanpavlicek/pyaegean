"""Regression guards for public documentation facts and front-door clarity."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from aegean import data, geo
from aegean.mcp_server import TOOLS


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_home_is_an_evergreen_front_door() -> None:
    home = _read("wiki/Home.md")

    assert "### New in v" not in home
    assert "## Choose where to start" in home
    assert "Latest PyPI release: v0.44.2" in home
    assert "main-branch previews" in home


def test_geography_counts_follow_the_live_gazetteer() -> None:
    coordinates = geo.site_coordinates()
    total = len(coordinates)
    aligned = sum(site.pleiades is not None for site in coordinates.values())
    regions = Counter(site.region for site in coordinates.values())
    geography = _read("wiki/Geography.md")
    candidates = _read("docs/pleiades-candidates.md")

    assert f"len(coords)                       # {total}" in geography
    assert f"**{aligned} of the {total}**" in geography
    assert f"**{aligned} of {total}**" in candidates
    assert f"nine values. The breakdown of the {total}" in geography
    for region, count in regions.items():
        assert f"| `{region}` | {count} |" in geography


def test_registry_and_mcp_counts_are_not_stale() -> None:
    dataset_count = len(data._REMOTE)
    cli = _read("wiki/CLI.md")
    cheatsheet = _read("wiki/CLI-Cheatsheet.md")
    recipes = _read("wiki/Recipes.md")

    assert f"shows all {dataset_count})" in cli
    assert f"currently {dataset_count} entries" in cli
    assert f"currently {dataset_count} entries" in cheatsheet
    assert f"# {len(TOOLS)} tools:" in recipes


def test_main_only_features_are_not_attributed_to_the_latest_release() -> None:
    readme = _read("README.md")
    home = _read("wiki/Home.md")
    greek_nlp = _read("wiki/Greek-NLP.md")

    assert "Latest PyPI release: v0.44.2" in readme
    assert "Main-branch preview:" in readme
    assert "not in PyPI v0.44.2" in greek_nlp
    assert "for **180 bundled documents** total" in readme
    assert "(**180 documents** total)" in home


def test_front_door_prose_avoids_competitive_hype() -> None:
    paths = [
        "README.md",
        "docs/index.md",
        "wiki/Home.md",
        "wiki/Greek-NLP.md",
        "wiki/Benchmarks.md",
        "wiki/FAQ.md",
    ]
    prose = "\n".join(_read(path).lower() for path in paths)

    assert "state of the art on" not in prose
    assert "best published number" not in prose
    assert "first honest" not in prose


def test_mkdocs_excludes_local_planning_documents_generically() -> None:
    config = _read("mkdocs.yml")

    assert "*ROADMAP*.md" in config
    assert "*PLAN*.md" in config
