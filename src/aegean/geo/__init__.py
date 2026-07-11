"""Geographic analysis of a corpus's find-sites — the ``[geo]`` extra (geopandas + shapely).

Maps each inscription's find-site to coordinates from a bundled gazetteer and exposes the corpus as
a GeoDataFrame for spatial analysis and plotting. The gazetteer covers the Aegean scripts' find-sites
and the openly-licensed Greek-epigraphy corpora's ancient find-places (I.Sicily, IIP, IOSPE, IGCyr,
EDH). The coordinates are **approximate** (site-level, ~1 km); for the epigraphy find-places they are
the site's Pleiades representative point, verified against the corpus's own coordinate where it
carries one. Where a site aligns to a Pleiades place, its stable id travels with it
(``SiteCoord.pleiades`` / ``pleiades_uri``) for linked-open-data work — the major sites are aligned,
minor findspots/peak sanctuaries mostly are not. Find-site labels are matched with their internal
whitespace collapsed, so a corpus label split across lines (``"Beth\\n  Shearim"``) still resolves.
Sites not in the gazetteer are dropped; see `site_coordinates` for coverage.
A few entries are flagged ``contested`` (Margiana): present because the upstream corpus carries them
but not accepted as Linear A find-spots. The flag (``SiteCoord.contested`` / ``is_contested``, and a
``contested`` column on the GeoDataFrames) travels with the site so it is never silently mapped as a
genuine provenance.

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
    region: str        # crete | aegean | anatolia | levant | mainland | remote |
                       #   sicily | cyrenaica | pontic  (the Greek-epigraphy regions)
    pleiades: int | None = None   # Pleiades place id, if the site aligns to one
    # Set when the find-spot's provenance is disputed: the site is present because
    # the upstream corpus carries it, but it is not an accepted Linear A find-spot.
    # The string is the reason; ``None`` for ordinary sites. Carried through the
    # GeoDataFrames so it is never silently mapped as a genuine provenance.
    contested: str | None = None

    @property
    def pleiades_uri(self) -> str | None:
        """The site's stable Pleiades URI, or ``None`` if it isn't aligned to a place."""
        return f"https://pleiades.stoa.org/places/{self.pleiades}" if self.pleiades else None

    @property
    def is_contested(self) -> bool:
        """Whether this find-spot's provenance is disputed (see :attr:`contested`)."""
        return self.contested is not None


def site_coordinates() -> dict[str, SiteCoord]:
    """The bundled site→coordinate gazetteer, keyed by the corpus's ``meta.site`` label."""
    raw = load_bundled_json("geo", "site_coordinates.json")
    return {key: SiteCoord(**val) for key, val in raw.items()}


def _normalize_site(label: str) -> str:
    """Collapse a find-site label's internal whitespace to single spaces (and strip).

    Some epigraphy corpora carry find-place labels with line breaks / runs of spaces baked in
    (``"Beth\\n     Shearim"``), which are the same place as the clean ``"Beth Shearim"``. Matching
    on the normalized form lets one gazetteer row cover both, and is a no-op for the clean Aegean
    labels."""
    return " ".join(str(label).split())


def _resolve_site(index: dict[str, SiteCoord], label: str) -> SiteCoord | None:
    """Look a corpus find-site label up in a normalized gazetteer index (or ``None``)."""
    return index.get(_normalize_site(label))


def _site_index(coords: dict[str, SiteCoord]) -> dict[str, SiteCoord]:
    """A whitespace-normalized view of the gazetteer for resolution (keys never collide)."""
    return {_normalize_site(key): sc for key, sc in coords.items()}


def _key_index(coords: dict[str, SiteCoord]) -> dict[str, str]:
    """Map a find-site label's normalized form to its canonical gazetteer key.

    Keying aggregations on this canonical key (rather than the raw ``meta.site`` string)
    collapses whitespace/line-split variants of one place into a single row: a corpus that
    carries both ``"Beth Shearim"`` and ``"Beth\\n Shearim"`` counts them as one site."""
    return {_normalize_site(key): key for key in coords}


def _import_geo() -> tuple[Any, Any]:
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ModuleNotFoundError as e:  # pragma: no cover - import guard
        raise ImportError(
            "geographic analysis needs the optional dependencies: pip install 'pyaegean[geo]'"
        ) from e
    return gpd, Point


def _as_geodataframe(gpd: Any, rows: list[dict[str, Any]], columns: list[str]):  # type: ignore[no-untyped-def]
    """Build the EPSG:4326 GeoDataFrame, keeping the schema when ``rows`` is empty.

    A bare empty row list would lose the named columns and the geometry column (geopandas
    raises on ``geometry="geometry"`` with no such column), so the zero-match case gets an
    explicit empty frame with the same columns, geometry dtype, and crs as a populated one."""
    if not rows:
        return gpd.GeoDataFrame(columns=columns, geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def to_geodataframe(corpus: Corpus, *, level: str = "inscription"):  # type: ignore[no-untyped-def]
    """A geopandas ``GeoDataFrame`` of the corpus's find-sites (EPSG:4326 point geometry).

    ``level="inscription"`` gives one row per inscription whose site is in the gazetteer (id, site,
    label, region, period, geometry); ``level="site"`` gives one row per gazetteer site with its
    inscription count, keyed on the canonical gazetteer label so whitespace/line-split variants of a
    find-place collapse to one row (its counts summed). Inscriptions whose site isn't mapped are
    dropped; a corpus with no mapped sites yields an empty GeoDataFrame with the same columns and
    crs. Needs the ``[geo]`` extra."""
    gpd, point = _import_geo()
    coords = site_coordinates()
    if level == "inscription":
        index = _site_index(coords)
        cols = ["id", "site", "label", "region", "period", "pleiades", "contested", "geometry"]
        rows = []
        for d in corpus:
            sc = _resolve_site(index, d.meta.site)
            if sc is None:
                continue
            rows.append({
                "id": d.id, "site": d.meta.site, "label": sc.name,
                "region": sc.region, "period": d.meta.period,
                "pleiades": sc.pleiades, "contested": sc.contested,
                "geometry": point(sc.lon, sc.lat),
            })
    elif level == "site":
        keys = _key_index(coords)
        cols = ["site", "label", "region", "pleiades", "inscriptions", "contested", "geometry"]
        counts: Counter[str] = Counter()
        for d in corpus:
            key = keys.get(_normalize_site(d.meta.site))
            if key is not None:
                counts[key] += 1
        rows = []
        for key, n in counts.most_common():
            sc = coords[key]
            rows.append({
                "site": key, "label": sc.name, "region": sc.region,
                "pleiades": sc.pleiades, "inscriptions": n, "contested": sc.contested,
                "geometry": point(sc.lon, sc.lat),
            })
    else:
        raise ValueError(f"level must be 'inscription' or 'site'; got {level!r}")
    return _as_geodataframe(gpd, rows, cols)


def word_distribution(corpus: Corpus, word: str):  # type: ignore[no-untyped-def]
    """A ``GeoDataFrame`` of the find-sites where ``word`` is attested, with per-site counts — i.e.
    *where* a given word shows up across the corpus, ready to map. Matching is case-insensitive
    (``ku-ro`` finds ``KU-RO``). Counts are keyed on the canonical gazetteer label, so a find-place
    written two ways (line-split or extra spaces) contributes to one row, not several. A word
    attested at no mapped site yields an empty GeoDataFrame with the same columns and crs. Needs the
    ``[geo]`` extra."""
    gpd, point = _import_geo()
    coords = site_coordinates()
    keys = _key_index(coords)
    target = word.casefold()
    counts: Counter[str] = Counter()
    for d in corpus:
        key = keys.get(_normalize_site(d.meta.site))
        if key is not None and any(t.text.casefold() == target for t in d.words):
            counts[key] += 1
    rows = []
    for key, n in counts.most_common():
        sc = coords[key]
        rows.append({
            "site": key, "label": sc.name, "region": sc.region,
            "pleiades": sc.pleiades, "count": n, "contested": sc.contested,
            "geometry": point(sc.lon, sc.lat),
        })
    return _as_geodataframe(
        gpd, rows, ["site", "label", "region", "pleiades", "count", "contested", "geometry"]
    )
