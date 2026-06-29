# Geography

`aegean.geo` maps a corpus's **find-sites** to coordinates and hands you the corpus back as a
geopandas **GeoDataFrame**, so you can ask *where* things are: where a word clusters, how far a
script reaches, how a corpus spreads across Crete and the wider Aegean. You'd reach for it to draw a
distribution map, run a spatial join, or export your find-sites as GeoJSON for QGIS, a web map, or a
linked-open-data project.

It's an **opt-in** extra (`pip install "pyaegean[geo]"`: geopandas + shapely). `import aegean` stays
instant and dependency-free; geopandas and shapely are imported lazily, only when you call a geo
function, and that call raises a clear error if the extra isn't installed:

```
ImportError: geographic analysis needs the optional dependencies: pip install 'pyaegean[geo]'
```

Everything here is also reachable from the command line with `aegean geo` if you'd rather not write
Python: see [CLI](CLI). The table view (`aegean geo CORPUS`) works with **just the core install**;
only GeoJSON export pulls in the `[geo]` extra.

---

## Quick start (Python)

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")

geo.to_geodataframe(corpus)                 # one row per inscription with a mapped site
geo.to_geodataframe(corpus, level="site")   # one row per site + its inscription count
geo.word_distribution(corpus, "KU-RO")      # the sites where KU-RO is attested, with counts
geo.site_coordinates()                       # the raw site -> coordinate gazetteer (no extra needed)
```

Each of the first three returns a `geopandas.GeoDataFrame` in **EPSG:4326** (WGS84 lat/lon) with a
`geometry` column of points: ready for `.plot()`, spatial joins, or export. Inscriptions whose site
isn't in the gazetteer are silently dropped (see [Coverage](#coverage)).

### What's in the box

| Object | What it gives you | Needs `[geo]`? |
|---|---|---|
| `geo.to_geodataframe(corpus)` | GeoDataFrame, one row per inscription | yes |
| `geo.to_geodataframe(corpus, level="site")` | GeoDataFrame, one row per site + count | yes |
| `geo.word_distribution(corpus, word)` | GeoDataFrame of sites where `word` occurs | yes |
| `geo.site_coordinates()` | `dict[str, SiteCoord]`: the bundled gazetteer | no |
| `geo.SiteCoord` | a single site's coordinates + Pleiades id | no |

---

## Corpus → GeoDataFrame

`to_geodataframe` is the workhorse. It walks the corpus, looks each inscription's `meta.site` up in
the gazetteer, and builds point geometry from the matched coordinates. Two granularities:

### `level="inscription"` — one row per text

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")
gdf = geo.to_geodataframe(corpus)            # level="inscription" is the default

gdf.shape        # (1718, 7)
list(gdf.columns)
# ['id', 'site', 'label', 'region', 'period', 'pleiades', 'geometry']
gdf.crs          # <Geographic 2D CRS: EPSG:4326> ...
gdf.head(3)
#     id           site          label region period  pleiades             geometry
# 0  HT1  Haghia Triada  Haghia Triada  crete   LMIB  589672.0  POINT (24.79 35.06)
# 1  HT2  Haghia Triada  Haghia Triada  crete   LMIB  589672.0  POINT (24.79 35.06)
# 2  HT3  Haghia Triada  Haghia Triada  crete   LMIB  589672.0  POINT (24.79 35.06)
```

(1721 inscriptions in the Linear A corpus, 1718 of them with a site in the gazetteer.)

### `level="site"` — one row per find-site

```python
gdf = geo.to_geodataframe(corpus, level="site")

gdf.shape        # (52, 6)
list(gdf.columns)
# ['site', 'label', 'region', 'pleiades', 'inscriptions', 'geometry']
gdf.head(8)
#             site             label  region     pleiades  inscriptions             geometry
# 0  Haghia Triada     Haghia Triada   crete     589672.0          1110  POINT (24.79 35.06)
# 1         Khania            Khania   crete     589886.0           226  POINT (24.02 35.51)
# 2       Phaistos          Phaistos   crete     589987.0            66  POINT (24.81 35.05)
# 3        Knossos           Knossos   crete  781961476.0            59   POINT (25.16 35.3)
# 4         Zakros            Zakros   crete  650881089.0            53   POINT (26.26 35.1)
# 5    Palaikastro       Palaikastro   crete  213924739.0            25   POINT (26.27 35.2)
# 6          Malia             Malia   crete     589922.0            22  POINT (25.49 35.29)
# 7          Thera  Thera (Akrotiri)  aegean     599478.0            18   POINT (25.4 36.36)
```

Site rows come back sorted by inscription count (most prolific first). The total here (52) is the
number of distinct **located** sites in the Linear A corpus.

### Columns

| Column | Levels | Type | Meaning |
|---|---|---|---|
| `id` | inscription | str | the inscription id (e.g. `HT1`) |
| `site` | both | str | the corpus's `meta.site` label (the gazetteer key) |
| `label` | both | str | the gazetteer's display name (may be fuller, e.g. `Iouktas (Mt Juktas)`) |
| `region` | both | str | one of the six [region codes](#regions) |
| `period` | inscription | str | the inscription's `meta.period` (e.g. `LMIB`) |
| `pleiades` | both | int / null | the [Pleiades](#pleiades-alignment) place id, if aligned |
| `contested` | both | str / null | reason string if the find-spot's provenance is disputed (e.g. Margiana), else null; see [Contested find-spots](#contested-find-spots) |
| `inscriptions` | site | int | number of inscriptions from this site |
| `count` | (word_distribution) | int | number of inscriptions at this site that contain the word |
| `geometry` | all | Point | EPSG:4326 point, `POINT (lon lat)` |

> Note: `pleiades` arrives as a float in the GeoDataFrame (e.g. `589672.0`) because the column holds
> nulls for unaligned sites and pandas promotes integer-with-nulls to float. The underlying value is
> still the integer place id; `SiteCoord.pleiades` gives you the clean `int`.

`level` only accepts `"inscription"` or `"site"`; anything else is a `ValueError`:

```python
geo.to_geodataframe(corpus, level="county")
# ValueError: level must be 'inscription' or 'site'; got 'county'
```

### CLI equivalent

`aegean geo` prints a located-sites table by default (no `[geo]` extra needed) and writes GeoJSON
with `--output`. The CLI defaults to `--level site`.

```bash
aegean geo lineara
#        lineara: 52 located site(s) of 52
# ┌──────────────────┬───────┬───────┬───────────┬───────────┐
# │ site             │ lat   │ lon   │ pleiades  │ contested │
# ├──────────────────┼───────┼───────┼───────────┼───────────┤
# │ Apodoulou        │ 35.16 │ 24.73 │ 119143959 │           │
# │ Arkhalkhori      │ 35.15 │ 25.27 │ 220781958 │           │
# │ Armenoi          │ 35.3  │ 24.5  │           │           │
# │ ...              │       │       │           │           │
# └──────────────────┴───────┴───────┴───────────┴───────────┘
# (Margiana's row shows "disputed" in the contested column.)

aegean geo linearb
#     linearb: 3 located site(s) of 3
# ┌─────────┬───────┬───────┬───────────┬───────────┐
# │ site    │ lat   │ lon   │ pleiades  │ contested │
# ├─────────┼───────┼───────┼───────────┼───────────┤
# │ Knossos │ 35.3  │ 25.16 │ 781961476 │           │
# │ Mycenae │ 37.73 │ 22.75 │ 570491    │           │
# │ Pylos   │ 37.03 │ 21.7  │ 570640    │           │
# └─────────┴───────┴───────┴───────────┴───────────┘
```

Machine-readable rows with `--json`:

```bash
aegean geo lineara --json
# [{"site": "Apodoulou", "lat": 35.16, "lon": 24.73, "pleiades": 119143959, "contested": ""}, ... ]
# one object per located site; pleiades is "" when unaligned, and contested is "" unless the
# provenance is disputed (e.g. Margiana carries its reason string)
```

### `aegean geo` flags

| Flag | Default | What it does |
|---|---|---|
| `CORPUS` (argument) |— | corpus id: `lineara`, `linearb`, `cypriot`, `cyprominoan`, `greek`, or a fetched corpus (`nt`, `damos`, `sigla`) |
| `--level` | `site` | `site` or `inscription` (only affects GeoJSON export) |
| `--output`, `-o` |— | write GeoJSON to this path instead of printing the table (needs `[geo]`) |
| `--json` | off | machine-readable JSON rows on stdout (table mode) |
| `--help`, `-h` |— | show usage and exit |

---

## Where a word shows up — `word_distribution`

`word_distribution` answers "where, across the corpus, does this word turn up?" It returns a
site-level GeoDataFrame with a per-site `count`, sorted most-frequent first: exactly what you want
to map a single term.

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")
wd = geo.word_distribution(corpus, "KU-RO")      # the LA "total" word

wd.shape         # (3, 6)
list(wd.columns) # ['site', 'label', 'region', 'pleiades', 'count', 'geometry']
wd
#             site          label region   pleiades  count             geometry
# 0  Haghia Triada  Haghia Triada  crete     589672     32  POINT (24.79 35.06)
# 1       Phaistos       Phaistos  crete     589987      1  POINT (24.81 35.05)
# 2         Zakros         Zakros  crete  650881089      1   POINT (26.26 35.1)
```

The match is exact on the word token's surface form (`t.text == word`), so use the corpus's own
transliteration (here, dash-joined sign sequences like `KU-RO`). See [Linear A](Linear-A) and
[Analysis](Analysis) for how to find the words worth mapping.

> Edge case: if a word has **zero** hits the result has no rows, and geopandas can't infer the
> geometry column on an empty frame, so the call raises rather than returning an empty GeoDataFrame.
> Check that the word is attested first (e.g. with the corpus's concordance / counts).

There's no dedicated CLI subcommand for `word_distribution`: it's a Python-only helper.

---

## The gazetteer

`geo.site_coordinates()` returns the bundled site → coordinate table: a `dict[str, SiteCoord]`
keyed by the corpus's `meta.site` label. This is the one geo function that needs **no extra**; it's
plain data. Coordinates are **approximate** (site-level, ~1 km), drawn from standard archaeological
references: fine for mapping, not survey work.

```python
from aegean import geo

coords = geo.site_coordinates()
len(coords)                       # 56
coords["Haghia Triada"]
# SiteCoord(name='Haghia Triada', lat=35.06, lon=24.79, region='crete', pleiades=589672)
```

### `SiteCoord`

A frozen dataclass. Fields:

| Field | Type | Meaning |
|---|---|---|
| `name` | str | display name (may be fuller than the corpus's site label) |
| `lat` | float | latitude, WGS84 |
| `lon` | float | longitude, WGS84 |
| `region` | str | one of the six region codes below |
| `pleiades` | int / None | Pleiades place id, if aligned (default `None`) |
| `pleiades_uri` | property → str / None | full `https://pleiades.stoa.org/places/<id>` URI, or `None` |
| `contested` | str / None | reason string if the find-spot's provenance is disputed; `None` for ordinary sites (default `None`); see [Contested find-spots](#contested-find-spots) |
| `is_contested` | property → bool | whether `contested` is set |

```python
sc = coords["Haghia Triada"]
sc.lat, sc.lon            # (35.06, 24.79)
sc.region                 # 'crete'
sc.pleiades               # 589672
sc.pleiades_uri           # 'https://pleiades.stoa.org/places/589672'

coords["Pyrgos"].pleiades_uri   # None  (not aligned)
coords["Margiana"].is_contested # True  (disputed provenance)
```

The gazetteer covers the find-sites in all four Aegean-script corpora: the Cretan and Aegean Linear
A sites, plus Pylos (Linear B), Cyprus, and the Cypro-Minoan sites Enkomi and Ugarit, and a few
outliers like Tel Haror (Negev) and Margiana (Turkmenistan), the last of which is flagged
[contested](#contested-find-spots).

### Regions

`region` is a controlled vocabulary of six values. The breakdown of the 56 gazetteer sites:

| Region | Sites | What it covers |
|---|---|---|
| `crete` | 40 | the island of Crete (the bulk of Linear A) |
| `aegean` | 5 | the Aegean islands (Thera, Kea, Milos, Kythera, Samothrace) |
| `mainland` | 4 | the Greek mainland (Mycenae, Tiryns, Pylos, Hagios Stefanos) |
| `anatolia` | 2 | the Anatolian coast (Miletus, Troy) |
| `levant` | 4 | Cyprus and the Levantine coast (Enkomi, Ugarit, Tel Haror, Cyprus) |
| `remote` | 1 | far-flung outliers (Margiana, Turkmenistan, a [contested](#contested-find-spots) find-spot) |

### Contested find-spots

A find-spot can be present in the upstream corpus yet not be an accepted provenance. Such a site
keeps its inscription (so the bundled corpus stays faithful to upstream and matches the workbench's
parity checksum) but is flagged: `SiteCoord.contested` holds the reason, `is_contested` is `True`,
and the GeoDataFrames and the `aegean geo` table carry a `contested` column. The one current case
is **Margiana** (Turkmenistan): no Linear A inscription is accepted from Central Asia (the "1427 in
Margiana" figure misreads the GORILA corpus total, and the only link is the fringe "Cretan
Protolinear" theory), so it is never silently mapped as a genuine find-spot.

```python
m = coords["Margiana"]
m.is_contested            # True
m.contested               # 'Disputed: no Linear A inscription is accepted from Central Asia; ...'
```

---

## Pleiades alignment

**33 of the 56** find-sites are aligned to a [Pleiades](https://pleiades.stoa.org/) place id, for
linked-open-data work. Every id is **verified by coordinate** (the Pleiades representative point is
within a few km of ours and its description matches the site), so a match is confirmed, never
guessed. It lives on `SiteCoord.pleiades` (an `int`), with `SiteCoord.pleiades_uri` giving the full
`https://pleiades.stoa.org/places/<id>` URI, and surfaces as a `pleiades` column in the GeoDataFrames
from `to_geodataframe` / `word_distribution`.

```python
geo.site_coordinates()["Haghia Triada"].pleiades_uri
# 'https://pleiades.stoa.org/places/589672'
```

The remaining 23 sites are mostly minor findspots, peak sanctuaries, and caves not yet in Pleiades,
left null, and listed as upstream-contribution candidates in
[docs/pleiades-candidates.md](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/pleiades-candidates.md).

A few of the major aligned sites:

| Site | Region | Pleiades id |
|---|---|---|
| Haghia Triada | crete | 589672 |
| Khania | crete | 589886 |
| Phaistos | crete | 589987 |
| Knossos | crete | 781961476 |
| Zakros | crete | 650881089 |
| Malia | crete | 589922 |
| Thera (Akrotiri) | aegean | 599478 |
| Pylos (Palace of Nestor) | mainland | 570640 |
| Mycenae | mainland | 570491 |
| Miletus | anatolia | 599799 |
| Enkomi | levant | 13818291 |

Pull the full machine-readable list straight from the CLI:

```bash
aegean geo lineara --json
# every located site, with "pleiades" set to the id (or "" if unaligned)
```

---

## GeoJSON export

A GeoDataFrame serialises to GeoJSON the standard geopandas way: both from Python and the CLI. The
output is a `FeatureCollection` in EPSG:4326; the GeoDataFrame columns become each feature's
`properties`, and `geometry` becomes a GeoJSON `Point`.

### From the CLI

```bash
aegean geo lineara --level site -o la_sites.geojson
# wrote 52 features to la_sites.geojson

aegean geo lineara --level inscription -o la_inscriptions.geojson
# wrote 1718 features to la_inscriptions.geojson
```

The first feature of the site-level export:

```json
{
  "id": "0",
  "type": "Feature",
  "properties": {
    "site": "Haghia Triada",
    "label": "Haghia Triada",
    "region": "crete",
    "pleiades": 589672.0,
    "inscriptions": 1110,
    "contested": null
  },
  "geometry": { "type": "Point", "coordinates": [24.79, 35.06] }
}
```

### From Python

```python
gdf = geo.to_geodataframe(corpus, level="site")

# (a) a GeoJSON string in memory:
gdf.to_json()[:60]
# '{"type": "FeatureCollection", "features": [{"id": "0", "type'

# (b) straight to a file (any geopandas-supported driver):
gdf.to_file("la_sites.geojson", driver="GeoJSON")
```

From there it drops straight into QGIS, a web map (Leaflet/Mapbox), or any GeoJSON-aware tool. Other
tabular exports (CSV, Parquet, EpiDoc, SQLite) for the corpus itself live under
[`aegean export`](CLI); the geo path is specifically for spatial GeoJSON.

---

## Plotting

A GeoDataFrame plots in one line (with `matplotlib` installed: that's the separate `[viz]` extra):

```python
gdf = geo.to_geodataframe(corpus, level="site")
ax = gdf.plot()        # the find-sites as points
# overlay on a basemap of your choice, or size points by `inscriptions`:
gdf.plot(markersize="inscriptions" and gdf["inscriptions"] / 5)
```

For a quick word map, plot a `word_distribution` frame and scale by `count`:

```python
wd = geo.word_distribution(corpus, "KU-RO")
wd.plot(markersize=wd["count"] * 10)
```

pyaegean doesn't ship its own basemap: bring your own (contextily, a shapefile of Crete, etc.).
For non-spatial plots (sign frequencies, period histograms) see `aegean.viz` / [CLI](CLI)'s
`aegean plot`.

---

## Coverage

`to_geodataframe` and `word_distribution` only emit rows for sites that are in the gazetteer;
anything else is dropped. Per corpus:

| Corpus | Docs | Located sites | Notes |
|---|---|---|---|
| `lineara` | 1721 | 52 of 52 site labels | 1718 docs have a mapped site; the rest have no/unknown site |
| `linearb` | 18 | 3 of 3 (Knossos, Mycenae, Pylos) | the bundled Linear B sample |
| `cypriot` | 2 | 1 of 1 | small bundled sample |
| `cyprominoan` | 2 | 2 of 2 (Enkomi, Ugarit) | small bundled sample |

The gazetteer holds 56 sites total — more than any single corpus uses — so it already covers
find-sites across all four scripts. The few Linear A inscriptions with no row simply carry no usable
`meta.site` value.

---

## Notes & limitations

- **Coordinates are approximate (~1 km, site-level).** They're for mapping and distribution analysis,
  not for survey work or anything that needs trench-level precision. Don't measure distances and
  report metres.
- **Unmapped inscriptions are dropped silently** in `to_geodataframe` / `word_distribution`. Compare
  `len(corpus)` against the GeoDataFrame's row count if you need to know how many were excluded; the
  CLI table prints "*N* located site(s) of *M*" so you can see the gap directly.
- **`word_distribution` raises on a zero-hit word** rather than returning an empty frame (geopandas
  can't infer geometry on no rows). Check the word is attested first.
- **`pleiades` shows as a float in the GeoDataFrame** because the column mixes ids with nulls; the id
  is still integral. Use `SiteCoord.pleiades` for the clean `int`.
- **23 sites have no Pleiades id**: mostly minor findspots, peak sanctuaries, and caves. They're
  tracked as upstream-contribution candidates, not errors.
- **`word_distribution` matches the exact surface form.** It won't normalise or fuzzy-match; pass the
  word as the corpus transliterates it.

See [Limitations](Limitations) for the project-wide caveats.

---

## Provenance

Coordinates are compiled from standard archaeological references (GORILA, Younger, public gazetteers)
via the [Linear A Research Workbench](https://github.com/ryanpavlicek/linearaworkbench) (Apache-2.0).
See [Data & Provenance](Data-and-Provenance) and `NOTICE`.

## See also

- [Installation](Installation): the `[geo]` and `[viz]` extras
- [Linear A](Linear-A) / [Linear B](Linear-B) / [Cypriot](Cypriot) / [Cypro-Minoan](Cypro-Minoan): the corpora you map
- [Analysis](Analysis): finding the words and patterns worth mapping
- [CLI](CLI): `aegean geo` and the other corpus commands
- [Data & Provenance](Data-and-Provenance): where the coordinates come from
