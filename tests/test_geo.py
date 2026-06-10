"""Tests for aegean.geo — geographic analysis (the [geo] extra).

``site_coordinates()`` needs no extra and is always tested; the GeoDataFrame builders need
geopandas/shapely, so those tests skip when the [geo] extra isn't installed. ``import aegean``
keeping geopandas lazy is covered separately by scripts/check_footprint.py (a clean subprocess)."""

from __future__ import annotations

import pytest

import aegean
from aegean.geo import SiteCoord, site_coordinates


def test_site_coordinates_gazetteer() -> None:
    coords = site_coordinates()
    assert len(coords) >= 50
    ht = coords["Haghia Triada"]
    assert isinstance(ht, SiteCoord)
    assert ht.region == "crete" and 34 < ht.lat < 36 and 24 < ht.lon < 26
    # every corpus's sites resolve — incl. the non-Linear-A sites added for this gazetteer
    for site in ("Knossos", "Phaistos", "Pylos", "Enkomi", "Ugarit", "Cyprus"):
        assert site in coords


def test_to_geodataframe_inscription_level() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    gdf = aegean.geo.to_geodataframe(c)
    assert str(gdf.crs).upper().endswith("4326")
    assert 0 < len(gdf) <= len(c)  # one row per inscription with a mapped site
    assert {"id", "site", "label", "region", "geometry"}.issubset(gdf.columns)
    # all points fall in the Aegean→Near-East bounding box
    assert gdf.geometry.x.between(20, 65).all()
    assert gdf.geometry.y.between(30, 41).all()


def test_to_geodataframe_site_level_counts() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    sites = aegean.geo.to_geodataframe(c, level="site")
    top = sites.iloc[0]  # most_common first
    assert top["site"] == "Haghia Triada" and top["inscriptions"] > 1
    # site-level counts sum to the inscription-level row count (same mapped set)
    assert int(sites["inscriptions"].sum()) == len(aegean.geo.to_geodataframe(c))


def test_word_distribution() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    kuro = aegean.geo.word_distribution(c, "KU-RO")
    assert len(kuro) >= 1 and int(kuro["count"].sum()) > 0
    assert "Haghia Triada" in set(kuro["site"])  # KU-RO is attested there


def test_to_geodataframe_rejects_bad_level() -> None:
    pytest.importorskip("geopandas")
    with pytest.raises(ValueError, match="level must be"):
        aegean.geo.to_geodataframe(aegean.load("lineara"), level="bogus")
