"""Geographic analysis of a corpus's find-sites — the ``[geo]`` extra (geopandas + shapely).

Maps each inscription's find-site to coordinates from a bundled Aegean gazetteer and exposes the
corpus as a GeoDataFrame for spatial analysis and plotting. The coordinates are **approximate**
(site-level, ~1 km), drawn from standard archaeological references — fine for mapping, not survey
work. Sites not in the gazetteer are dropped; see :func:`site_coordinates` for coverage.

geopandas/shapely are imported lazily, so ``import aegean`` stays instant and dependency-free; the
geo functions raise a clear error if the extra isn't installed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..data import load_bundled_json

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["SiteCoord", "site_coordinates", "to_geodataframe", "word_distribution"]


@dataclass(frozen=True, slots=True)
class SiteCoord:
    """Approximate site-level coordinates for a find-site (WGS84 / EPSG:4326)."""

    name: str          # display name (may differ from the corpus's site label)
    lat: float
    lon: float
    region: str        # one of: crete | aegean | anatolia | levant | mainland | remote


def site_coordinates() -> dict[str, SiteCoord]:
    """The bundled site→coordinate gazetteer, keyed by the corpus's ``meta.site`` label."""
    raw = load_bundled_json("geo", "site_coordinates.json")
    return {key: SiteCoord(**val) for key, val in raw.items()}


def _import_geo() -> tuple[Any, Any]:
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ModuleNotFoundError as e:  # pragma: no cover - import guard
        raise ImportError(
            "geographic analysis needs the optional dependencies: pip install 'pyaegean[geo]'"
        ) from e
    return gpd, Point


def to_geodataframe(corpus: Corpus, *, level: str = "inscription"):  # type: ignore[no-untyped-def]
    """A geopandas ``GeoDataFrame`` of the corpus's find-sites (EPSG:4326 point geometry).

    ``level="inscription"`` gives one row per inscription whose site is in the gazetteer (id, site,
    label, region, period, geometry); ``level="site"`` gives one row per site with its inscription
    count. Inscriptions whose site isn't mapped are dropped. Needs the ``[geo]`` extra."""
    gpd, point = _import_geo()
    coords = site_coordinates()
    if level == "inscription":
        rows = [
            {
                "id": d.id, "site": d.meta.site, "label": coords[d.meta.site].name,
                "region": coords[d.meta.site].region, "period": d.meta.period,
                "geometry": point(coords[d.meta.site].lon, coords[d.meta.site].lat),
            }
            for d in corpus
            if d.meta.site in coords
        ]
    elif level == "site":
        counts = Counter(d.meta.site for d in corpus if d.meta.site in coords)
        rows = [
            {
                "site": site, "label": coords[site].name, "region": coords[site].region,
                "inscriptions": n, "geometry": point(coords[site].lon, coords[site].lat),
            }
            for site, n in counts.most_common()
        ]
    else:
        raise ValueError(f"level must be 'inscription' or 'site'; got {level!r}")
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def word_distribution(corpus: Corpus, word: str):  # type: ignore[no-untyped-def]
    """A ``GeoDataFrame`` of the find-sites where ``word`` is attested, with per-site counts — i.e.
    *where* a given word shows up across the corpus, ready to map. Needs the ``[geo]`` extra."""
    gpd, point = _import_geo()
    coords = site_coordinates()
    counts: Counter[str] = Counter()
    for d in corpus:
        site = d.meta.site
        if site in coords and any(t.text == word for t in d.words):
            counts[site] += 1
    rows = [
        {
            "site": site, "label": coords[site].name, "region": coords[site].region,
            "count": n, "geometry": point(coords[site].lon, coords[site].lat),
        }
        for site, n in counts.most_common()
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
