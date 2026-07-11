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


def test_pleiades_alignment() -> None:
    coords = site_coordinates()
    kn = coords["Knossos"]
    assert kn.pleiades == 781961476
    assert kn.pleiades_uri == "https://pleiades.stoa.org/places/781961476"
    assert coords["Mycenae"].pleiades and coords["Troy"].pleiades  # major sites aligned
    # coordinate-verified additions: Tel Haror = Gerar, the Arkalochori cave
    assert coords["Tel Haror"].pleiades == 687907
    assert coords["Arkhalkhori"].pleiades == 220781958
    # ids recovered by the gazetteer trust pass (validated against the Pleiades reprPoint)
    assert coords["Ugarit"].pleiades == 668295        # Ras Shamra / Leukos Limen
    assert coords["Pyrgos"].pleiades == 589949        # Myrtos-Pyrgos (was a 39 km mislocation)
    vry = coords["Vrysinas"]  # a peak sanctuary not in Pleiades → left null, honestly
    assert vry.pleiades is None and vry.pleiades_uri is None
    assert sum(1 for s in coords.values() if s.pleiades) >= 40


def test_gazetteer_well_formed() -> None:
    coords = site_coordinates()
    # the Aegean regions plus the Greek-epigraphy regions (Sicily, Cyrenaica, the Pontic/Black Sea)
    regions = {"crete", "aegean", "anatolia", "levant", "mainland", "remote",
               "sicily", "cyrenaica", "pontic"}
    for name, sc in coords.items():
        assert sc.region in regions, name
        assert 30 < sc.lat < 47, name       # Cyrenaica (~32) up to the N Black Sea coast (~46)
        assert 12 < sc.lon < 63, name       # west Sicily (~12.4) out to the Margiana outlier (~62)
        assert sc.pleiades is None or isinstance(sc.pleiades, int), name
    # exactly the disputed find-spot carries the contested flag
    assert coords["Margiana"].is_contested
    assert [n for n, sc in coords.items() if sc.is_contested] == ["Margiana"]


def test_to_geodataframe_inscription_level() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    gdf = aegean.geo.to_geodataframe(c)
    assert str(gdf.crs).upper().endswith("4326")
    assert 0 < len(gdf) <= len(c)  # one row per inscription with a mapped site
    assert {"id", "site", "label", "region", "pleiades", "geometry"}.issubset(gdf.columns)
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


def test_word_distribution_case_insensitive() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    # Linear A words are stored uppercase (KU-RO); a lowercase query must still match.
    lower = aegean.geo.word_distribution(c, "ku-ro")
    upper = aegean.geo.word_distribution(c, "KU-RO")
    assert int(lower["count"].sum()) == int(upper["count"].sum()) > 0
    assert set(lower["site"]) == set(upper["site"])


def test_to_geodataframe_rejects_bad_level() -> None:
    pytest.importorskip("geopandas")
    with pytest.raises(ValueError, match="level must be"):
        aegean.geo.to_geodataframe(aegean.load("lineara"), level="bogus")


def test_contested_findspot_flagged() -> None:
    coords = site_coordinates()
    marg = coords["Margiana"]
    assert marg.is_contested
    assert marg.contested and "not a genuine find-spot" in marg.contested
    # ordinary sites carry no flag
    ht = coords["Haghia Triada"]
    assert ht.contested is None and not ht.is_contested
    # Margiana is the only disputed entry in the gazetteer
    assert [k for k, v in coords.items() if v.is_contested] == ["Margiana"]


def test_contested_surfaces_in_geodataframe() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    gdf = aegean.geo.to_geodataframe(c)
    assert "contested" in gdf.columns
    # Margiana's inscription is flagged; ordinary rows are not
    marg = gdf[gdf["site"] == "Margiana"]
    assert len(marg) >= 1 and marg["contested"].notna().all()
    assert gdf[gdf["site"] == "Haghia Triada"]["contested"].isna().all()
