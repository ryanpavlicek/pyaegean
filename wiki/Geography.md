# Geography

`aegean.geo` maps a corpus's **find-sites** to coordinates and exposes it as a geopandas
**GeoDataFrame**, so you can do spatial analysis and plotting — where a word clusters, how far a
script reaches, how a corpus is distributed across Crete and the Aegean.

It's an **opt-in** extra (`pip install pyaegean[geo]` — geopandas + shapely). `import aegean` stays
instant and dependency-free; the geo functions raise a clear error if the extra isn't installed.

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")

geo.to_geodataframe(corpus)                 # one row per inscription with a mapped site
geo.to_geodataframe(corpus, level="site")   # one row per site + its inscription count
geo.word_distribution(corpus, "KU-RO")      # the sites where KU-RO is attested, with counts
```

Each call returns a `geopandas.GeoDataFrame` in **EPSG:4326** with a `geometry` column of points —
ready for `.plot()`, spatial joins, or export. Inscriptions whose site isn't in the gazetteer are
dropped (see coverage below).

## The gazetteer

`geo.site_coordinates()` returns the bundled site→coordinate table — a `dict[str, SiteCoord]` keyed
by the corpus's `meta.site` label. Coordinates are **approximate** (site-level, ~1 km), drawn from
standard archaeological references — fine for mapping, not survey work.

```python
geo.site_coordinates()["Haghia Triada"]
# SiteCoord(name='Haghia Triada', lat=35.06, lon=24.79, region='crete')
```

The gazetteer covers the find-sites in all four corpora — the Cretan and Aegean Linear A sites, plus
Pylos (Linear B), Cyprus, and the Cypro-Minoan sites Enkomi and Ugarit.

## Pleiades alignment

33 of the 56 find-sites are aligned to a [Pleiades](https://pleiades.stoa.org/) place id, for
linked-open-data work. Every id is **verified by coordinate** — the Pleiades representative point is
within a few km of ours and its description matches the site — so a match is confirmed, never
guessed. It's on `SiteCoord.pleiades` (an `int`), with `SiteCoord.pleiades_uri` giving the full
`https://pleiades.stoa.org/places/<id>` URI, and surfaces as a `pleiades` column in the GeoDataFrames
from `to_geodataframe` / `word_distribution`. The remaining sites are mostly minor findspots, peak
sanctuaries, and caves not yet in Pleiades — left null, and listed as upstream-contribution candidates
in [docs/pleiades-candidates.md](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/pleiades-candidates.md).

```python
geo.site_coordinates()["Haghia Triada"].pleiades_uri
# 'https://pleiades.stoa.org/places/589672'
```

## Plotting

A GeoDataFrame plots in one line (with `matplotlib` installed):

```python
gdf = geo.to_geodataframe(corpus, level="site")
gdf.plot()        # the find-sites as points; overlay on a basemap of your choice
```

## Provenance

Coordinates are compiled from standard archaeological references (GORILA, Younger, public gazetteers)
via the [Linear A Research Workbench](https://github.com/ryanpavlicek/linearaworkbench) (Apache-2.0).
See [Data & Provenance](Data-and-Provenance) and `NOTICE`.
