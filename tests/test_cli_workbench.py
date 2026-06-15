"""`aegean workbench` — the local server command (aegean.cli._workbench).

The blocking server itself isn't unit-tested; this covers the DataSpec pin, the cached-image
path mapping (incl. the traversal guard), the fetch-to-dir helper, and command wiring."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aegean import data
from aegean.cli import _workbench


def test_workbench_app_spec_registered() -> None:
    spec = data._REMOTE["workbench-app"]
    assert spec.extract is True
    assert len(spec.sha256) == 64
    assert "Apache-2.0" in spec.license
    assert spec.url.endswith("workbench-app.tar.gz")


def test_resolve_path_maps_cached_images(tmp_path: Path) -> None:
    images = tmp_path / "img"
    static = tmp_path / "app"
    assert _workbench._resolve_path("/upstream/images/HT13.jpg", static, images) == os.path.join(
        str(images), "HT13.jpg"
    )
    assert _workbench._resolve_path("/upstream/images/a/b.png", static, images) == os.path.join(
        str(images), "a", "b.png"
    )
    assert _workbench._resolve_path("/upstream/images/HT13.jpg?v=1", static, images) == os.path.join(
        str(images), "HT13.jpg"
    )


def test_resolve_path_defaults_and_guards(tmp_path: Path) -> None:
    images = tmp_path / "img"
    static = tmp_path / "app"
    assert _workbench._resolve_path("/index.html", static, images) is None      # not an image path
    assert _workbench._resolve_path("/upstream/images/x.jpg", static, None) is None  # no image cache
    # directory traversal out of the image cache is refused (falls back to default handling)
    assert _workbench._resolve_path("/upstream/images/../../etc/passwd", static, images) is None


def test_workbench_dir_uses_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "wb"
    d.mkdir()
    (d / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: d if name == "workbench-app" else None)
    assert _workbench._workbench_dir() == d


def test_command_is_wired() -> None:
    import click
    import typer
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()
    # the command exists and its --help renders without error
    result = CliRunner().invoke(app, ["workbench", "--help"])
    assert result.exit_code == 0
    assert "workbench" in result.output.lower()
    # Introspect the command's options rather than grepping the rendered help text:
    # Rich wraps the options table at narrow terminal widths, so the literal "--port"
    # can be absent from the rendered output (it is at the 80-column CI width).
    group = typer.main.get_command(app)
    workbench = group.get_command(click.Context(group), "workbench")
    assert workbench is not None
    options = {opt for param in workbench.params for opt in param.opts}
    assert "--port" in options
