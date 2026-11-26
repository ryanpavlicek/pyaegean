"""Consistency checks for the conda-forge v1 packaging recipe."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parent.parent
_RECIPE = _ROOT / "packaging" / "conda-forge" / "recipe.yaml"
_PYPROJECT = _ROOT / "pyproject.toml"


def _pyproject_field(text: str, key: str) -> str:
    match = re.search(rf'^{re.escape(key)}\s*=\s*"([^"]+)"$', text, re.MULTILINE)
    assert match is not None, f"missing {key!r} in pyproject.toml"
    return match.group(1)


def _semver(ver: str) -> tuple[int, int, int]:
    parts = ver.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), f"invalid semver: {ver!r}"
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def test_conda_forge_recipe_matches_pyproject() -> None:
    recipe = yaml.safe_load(_RECIPE.read_text(encoding="utf-8"))
    pyproject_text = _PYPROJECT.read_text(encoding="utf-8")

    assert recipe["schema_version"] == 1
    assert recipe["context"]["name"] == _pyproject_field(pyproject_text, "name")
    # Recipe pins a published PyPI sdist + real SHA-256, so it tracks <= current source version.
    assert _semver(recipe["context"]["version"]) <= _semver(_pyproject_field(pyproject_text, "version"))
    assert recipe["context"]["python_min"] == "3.10"

    assert recipe["build"]["noarch"] == "python"
    entry_points = recipe["build"]["python"]["entry_points"]
    assert "aegean = aegean.cli:main" in entry_points
    assert "aegean-mcp = aegean.mcp_server:main" in entry_points
    assert 'aegean = "aegean.cli:main"' in pyproject_text
    assert 'aegean-mcp = "aegean.mcp_server:main"' in pyproject_text

    assert recipe["about"]["license"] == _pyproject_field(pyproject_text, "license")
    for lf in recipe["about"]["license_file"]:
        assert (_ROOT / lf).is_file(), f"missing license_file {lf}"

    sha = recipe["source"]["sha256"]
    assert isinstance(sha, str) and len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)

    # Zero-dependency core: only python in run requirements.
    run_reqs = recipe["requirements"]["run"]
    assert len(run_reqs) == 1
    assert run_reqs[0].startswith("python ")
