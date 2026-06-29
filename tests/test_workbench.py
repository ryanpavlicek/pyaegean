"""Tests for aegean.cli._workbench — the local workbench server's image-path resolution.

The Linear A imagery is a separate fetchable asset (``aegean data fetch lineara-images``) that
unpacks to ``<cache>/lineara-images/images/<file>``; the server must resolve
``/upstream/images/<file>`` into that inner ``images/`` directory, with a traversal guard."""

from __future__ import annotations

from aegean.cli._workbench import _images_dir, _prepare_images, _resolve_path


def test_images_dir_prefers_inner_images_subdir(tmp_path, monkeypatch) -> None:
    (tmp_path / "lineara-images" / "images").mkdir(parents=True)
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    assert _images_dir() == tmp_path / "lineara-images" / "images"


def test_images_dir_none_when_unfetched(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    assert _images_dir() is None


def test_resolve_path_maps_into_images_and_guards_traversal(tmp_path, monkeypatch) -> None:
    images = tmp_path / "lineara-images" / "images"
    images.mkdir(parents=True)
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    img = _images_dir()
    # a real image request resolves into the inner images/ dir
    assert _resolve_path("/upstream/images/HT1-Facsimile.jpg", tmp_path, img) == str(
        images / "HT1-Facsimile.jpg"
    )
    # directory traversal out of the imagery dir is refused
    assert _resolve_path("/upstream/images/../../etc/passwd", tmp_path, img) is None
    # non-image requests fall through to the static handler
    assert _resolve_path("/index.html", tmp_path, img) is None


def test_prepare_images_fetches_when_flagged(tmp_path, monkeypatch) -> None:
    # --fetch-images downloads the lineara-images asset, then returns the inner images/ dir
    (tmp_path / "lineara-images" / "images").mkdir(parents=True)
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    calls: list[str] = []
    monkeypatch.setattr("aegean.data.fetch", lambda name, **k: calls.append(name))
    out = _prepare_images(fetch_images=True)
    assert calls == ["lineara-images"]
    assert out == tmp_path / "lineara-images" / "images"


def test_prepare_images_skips_fetch_when_not_flagged(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    calls: list[str] = []
    monkeypatch.setattr("aegean.data.fetch", lambda name, **k: calls.append(name))
    out = _prepare_images(fetch_images=False)
    assert calls == []  # no download without the flag
    assert out is None  # nothing cached
