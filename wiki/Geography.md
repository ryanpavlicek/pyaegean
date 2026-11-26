# Geography

`aegean.geo` maps corpus find-sites to coordinates and returns a `geopandas`
`GeoDataFrame` for spatial analysis, plotting, or GeoJSON export to QGIS,
Leaflet, or linked-open-data workflows.

`geopandas` and `shapely` are optional (`pip install "pyaegean[geo]"`). They are
imported lazily on call; if missing, the call raises:

```text
ImportError: geographic analysis needs the optional dependencies: pip install 'pyaegean[geo]'
```

The CLI command `aegean geo CORPUS` prints a located-sites table on the
zero-dependency core install; only GeoJSON output (`-o`) requires `[geo]`. See
[CLI](CLI).

---

## Quick start (Python)

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")

geo.to_geodataframe(corpus)                 # one row per inscription with a mapped site
geo.to_geodataframe(corpus, level="site")   # one row per site with inscription count
geo.word_distribution(corpus, "KU-RO")      # sites where KU-RO is attested, with counts
geo.site_coordinates()                      # bundled site -> coordinate gazetteer (core only)
```

The first three functions return a `geopandas.GeoDataFrame` in **EPSG:4326**
(WGS84 latitude/longitude) with a `geometry` column of `Point` objects.
Inscriptions whose `meta.site` is absent from the gazetteer are omitted (see
[Coverage](#coverage)).

### API summary

| Object | Description | Requires `[geo]`? |
| --- | --- | --- |
| `geo.to_geodataframe(corpus)` | GeoDataFrame, one row per inscription | yes |
| `geo.to_geodataframe(corpus, level="site")` | GeoDataFrame, one row per site with count | yes |
| `geo.word_distribution(corpus, word)` | GeoDataFrame of sites where `word` occurs | yes |
| `geo.site_coordinates()` | `dict[str, SiteCoord]` bundled gazetteer | no |
| `geo.SiteCoord` | Frozen dataclass for one site's coordinates and Pleiades id | no |

---

## Corpus → GeoDataFrame

`to_geodataframe` resolves each inscription's `meta.site` against the gazetteer
and constructs point geometry at either inscription or site granularity.

### `level="inscription"` — one row per text

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")
gdf = geo.to_geodataframe(corpus)            # level="inscription" is the default

gdf.shape        # (1718, 8)
list(gdf.columns)
# ['id', 'site', 'label', 'region', 'period', 'pleiades', 'contested', 'geometry']
gdf.crs          # <Geographic 2D CRS: EPSG:4326> ...
gdf.head(3)
#     id           site          label region period  pleiades contested             geometry
# 0  HT1  Haghia Triada  Haghia Triada  crete   LMIB  589672.0       NaN  POINT (24.79 35.06)
# 1  HT2  Haghia Triada  Haghia Triada  crete   LMIB  589672.0       NaN  POINT (24.79 35.06)
# 2  HT3  Haghia Triada  Haghia Triada  crete   LMIB  589672.0       NaN  POINT (24.79 35.06)
```

Of the 1,721 Linear A inscriptions, 1,718 carry a site present in the gazetteer.

### `level="site"` — one row per find-site

```python
gdf = geo.to_geodataframe(corpus, level="site")

gdf.shape        # (52, 7)
list(gdf.columns)
# ['site', 'label', 'region', 'pleiades', 'inscriptions', 'contested', 'geometry']
gdf.head(8)
#             site             label  region     pleiades  inscriptions contested             geometry
# 0  Haghia Triada     Haghia Triada   crete     589672.0          1110       NaN  POINT (24.79 35.06)
# 1         Khania            Khania   crete     589886.0           226       NaN  POINT (24.02 35.51)
# 2       Phaistos          Phaistos   crete     589987.0            66       NaN  POINT (24.81 35.05)
# 3        Knossos           Knossos   crete  781961476.0            59       NaN  POINT (25.16 35.3)
# 4         Zakros            Zakros   crete  650881089.0            53       NaN  POINT (26.26 35.1)
# 5    Palaikastro       Palaikastro   crete  213924739.0            25       NaN  POINT (26.27 35.2)
# 6          Malia             Malia   crete     589922.0            22       NaN  POINT (25.49 35.29)
# 7          Thera  Thera (Akrotiri)  aegean     599478.0            18       NaN  POINT (25.4 36.36)
```

Site rows are sorted by inscription count descending (52 located sites in
`lineara`).

### Columns

| Column | Levels | Type | Meaning |
| --- | --- | --- | --- |
| `id` | inscription | str | Inscription id (e.g. `HT1`) |
| `site` | both | str | Raw `meta.site` at inscription level; canonical gazetteer label at site and `word_distribution` level (collapsing whitespace variants) |
| `label` | both | str | Gazetteer display name (e.g. `Iouktas (Mt Juktas)`) |
| `region` | both | str | One of the nine [region codes](#regions) |
| `period` | inscription | str | Inscription's `meta.period` (e.g. `LMIB`) |
| `pleiades` | both | int / null | [Pleiades](#pleiades-alignment) place id, when aligned |
| `contested` | both | str / null | Reason string if provenance is disputed (e.g. Margiana), else null; see [Contested find-spots](#contested-find-spots) |
| `inscriptions` | site | int | Number of inscriptions from this site |
| `count` | `word_distribution` | int | Number of inscriptions at this site containing the word |
| `geometry` | all | Point | EPSG:4326 point, `POINT (lon lat)` |

Because `pleiades` contains nulls for unaligned sites, pandas displays the
column as float (e.g. `589672.0`). `SiteCoord.pleiades` stores the integer id.

`level` accepts only `"inscription"` or `"site"`:

```python
geo.to_geodataframe(corpus, level="county")
# ValueError: level must be 'inscription' or 'site'; got 'county'
```

### CLI equivalent

`aegean geo` prints a located-sites table by default (no `[geo]` extra required)
and writes GeoJSON when given `-o`/`--output`. The CLI defaults to
`--level site`.

```bash
aegean geo lineara
#               lineara: 52 located site(s) of 52
# ┌──────────────────┬────────┬────────┬───────────┬───────────┐
# │ site             │ lat    │ lon    │ pleiades  │ contested │
# ├──────────────────┼────────┼────────┼───────────┼───────────┤
# │ Apodoulou        │ 35.16  │ 24.73  │ 119143959 │           │
# │ Arkhalkhori      │ 35.15  │ 25.3   │ 220781958 │           │
# │ Armenoi          │ 35.3   │ 24.5   │           │           │
# │ ...              │        │        │           │           │
# └──────────────────┴────────┴────────┴───────────┴───────────┘
# (Margiana shows "disputed" in the contested column.)

aegean geo linearb
#               linearb: 3 located site(s) of 3
# ┌─────────┬───────────┬───────────┬───────────┬───────────┐
# │ site    │ lat       │ lon       │ pleiades  │ contested │
# ├─────────┼───────────┼───────────┼───────────┼───────────┤
# │ Knossos │ 35.3      │ 25.16     │ 781961476 │           │
# │ Mycenae │ 37.73     │ 22.75     │ 570491    │           │
# │ Pylos   │ 37.027138 │ 21.694962 │ 156116232 │           │
# └─────────┴───────────┴───────────┴───────────┴───────────┘
```

JSON output:

```bash
aegean geo lineara --json
# [{"site": "Apodoulou", "lat": 35.16, "lon": 24.73, "pleiades": 119143959, "contested": ""}, ...]
```

### `aegean geo` flags

| Flag | Default | Action |
| --- | --- | --- |
| `CORPUS` (argument) | — | Corpus id (`lineara`, `linearb`, `cypriot`, `cyprominoan`, `greek`, or fetched corpora such as `damos`, `sigla`, `isicily`, `iip`, `iospe`, `igcyr`, `aphrodisias`, `crete`, `edh`, `ddbdp`) |
| `--word` | — | Map per-site attestations of one word (case-insensitive) |
| `--level` | `site` | `site` or `inscription` (applies to GeoJSON export) |
| `--output`, `-o` | — | Write GeoJSON to this path instead of printing a table (requires `[geo]`) |
| `--json` | off | Emit JSON rows on stdout (table mode) |
| `--help`, `-h` | — | Print usage and exit |

Only provenanced inscription corpora yield rows. Aegean-script corpora
(`lineara`, `linearb`, `cypriot`, `cyprominoan`, `sigla`, `damos`) map most
fully; Greek epigraphic and papyrological corpora resolve the subset of their
find-places present in the Aegean-focused gazetteer:

| Corpus | Located sites |
| --- | --- |
| `isicily` | 13 of 121 |
| `iip` | 10 of 144 |
| `edh` | 6 of 292 |
| `iospe` | 5 of 81 |
| `igcyr` | 5 of 19 |
| `ddbdp` | 3 of 798 |

Literary corpora (`greek`, `nt`, and CTS literary works) carry no find-spot
metadata; `aegean geo` prints a one-line notice for them.

---

## Word distribution (`word_distribution`)

`word_distribution` returns a site-level GeoDataFrame sorted by `count`
descending, counting how many inscriptions at each mapped site contain the word:

```python
import aegean
from aegean import geo

corpus = aegean.load("lineara")
wd = geo.word_distribution(corpus, "KU-RO")

wd.shape         # (3, 7)
list(wd.columns) # ['site', 'label', 'region', 'pleiades', 'count', 'contested', 'geometry']
wd
#             site          label region   pleiades  count contested             geometry
# 0  Haghia Triada  Haghia Triada  crete     589672     32      None  POINT (24.79 35.06)
# 1       Phaistos       Phaistos  crete     589987      1      None  POINT (24.81 35.05)
# 2         Zakros         Zakros  crete  650881089      1      None   POINT (26.26 35.1)
```

Matching is case-insensitive on token surface text (`ku-ro` matches `KU-RO`).
Pass the transliteration convention used by the target corpus. If a word has no
hits, `word_distribution` returns an empty 0-row GeoDataFrame with shape
`(0, 7)` and the same column schema; check `wd.empty`.

CLI equivalent: `aegean geo CORPUS --word WORD`.

---

## The gazetteer

`geo.site_coordinates()` returns the bundled `dict[str, SiteCoord]` keyed by
`meta.site` label without requiring `[geo]`. Coordinates are approximate
site-level points (~1 km) drawn from standard archaeological references.

```python
from aegean import geo

coords = geo.site_coordinates()
len(coords)                       # 144
coords["Haghia Triada"]
# SiteCoord(name='Haghia Triada', lat=35.06, lon=24.79, region='crete', pleiades=589672, contested=None, precision='site', location_role='findspot')
```

### `SiteCoord`

`SiteCoord` is a frozen dataclass with the following fields and properties:

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | str | Display name |
| `lat` | float | WGS84 latitude |
| `lon` | float | WGS84 longitude |
| `region` | str | One of the nine region codes below |
| `pleiades` | int \| None | Aligned Pleiades place id (default `None`) |
| `pleiades_uri` | property → str \| None | `https://pleiades.stoa.org/places/<id>`, or `None` |
| `contested` | str \| None | Reason string if provenance is disputed (default `None`); see [Contested find-spots](#contested-find-spots) |
| `is_contested` | property → bool | `True` when `contested` is set |
| `precision` | str | Spatial granularity (`"monument"`, `"site"`, or `"region"`, default `"site"`) |
| `location_role` | str | Archaeological role (`"findspot"` or `"origin"`, default `"findspot"`) |

Use `geo.unmapped_sites(corpus)` (no `[geo]` extra required) to list any `(site_label, count)` pairs omitted from the gazetteer.

```python
sc = coords["Haghia Triada"]
sc.lat, sc.lon                   # (35.06, 24.79)
sc.region                        # 'crete'
sc.pleiades                      # 589672
sc.pleiades_uri                  # 'https://pleiades.stoa.org/places/589672'

coords["Vrysinas"].pleiades_uri  # None (peak sanctuary, not in Pleiades)
coords["Margiana"].is_contested  # True (disputed provenance)
```

### Regions

`region` is a controlled vocabulary of nine values. The breakdown of the 144 gazetteer sites:

| Region | Sites | Coverage |
| --- | --- | --- |
| `crete` | 62 | Crete (Linear A, DAMOS/SigLA, and Cretan Institutional Inscriptions) |
| `sicily` | 22 | Sicily (I.Sicily) |
| `mainland` | 18 | Greek mainland and Balkans (Linear B, EDH) |
| `levant` | 17 | Cyprus (IG XV 1, Enkomi) and the Levantine coast (IIP, Ugarit, Tel Haror) |
| `anatolia` | 7 | Anatolia (Aphrodisias, Miletus, Troy, Sardis, Heraclea Pontica, Teos, Mylasa) |
| `aegean` | 6 | Aegean islands (Thera, Kea, Milos/Melos, Kythera, Samothrace) |
| `cyrenaica` | 6 | Cyrenaica (IGCyr) |
| `pontic` | 5 | Northern Black Sea (IOSPE) |
| `remote` | 1 | Outliers (Margiana, Turkmenistan; [contested](#contested-find-spots)) |

### Contested find-spots

Sites that appear in an upstream corpus but lack accepted provenance remain in
the dataset so upstream parity is preserved, while `SiteCoord.contested` stores
the reason and `is_contested` returns `True`. GeoDataFrames and `aegean geo`
expose this in the `contested` column. The single current case is **Margiana**
(Turkmenistan): no Linear A inscription is accepted from Central Asia (the "1427
in Margiana" figure misreads the GORILA corpus total, and the sole connection is
the fringe "Cretan Protolinear" proposal).

```python
m = coords["Margiana"]
m.is_contested            # True
m.contested               # 'Disputed: no Linear A inscription is accepted from Central Asia; ...'
```

---

## Pleiades alignment

**128 of the 144** find-sites are aligned to [Pleiades](https://pleiades.stoa.org/)
place IDs. Each match is verified against the Pleiades representative
coordinates and place description, and `scripts/check_gazetteer.py` re-verifies
every link against live Pleiades data weekly. Aligned IDs live on
`SiteCoord.pleiades` (and `SiteCoord.pleiades_uri`) and appear in the `pleiades`
column of `to_geodataframe` and `word_distribution`.

```python
geo.site_coordinates()["Haghia Triada"].pleiades_uri
# 'https://pleiades.stoa.org/places/589672'
```

The remaining 16 entries (minor findspots, peak sanctuaries, caves, and the
generic `Crete` placeholder) have `pleiades=None` and are listed as upstream
contribution candidates in
[docs/pleiades-candidates.md](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/pleiades-candidates.md).

Selected aligned sites:

| Site | Region | Pleiades id |
| --- | --- | --- |
| Haghia Triada | crete | 589672 |
| Khania | crete | 589886 |
| Phaistos | crete | 589987 |
| Knossos | crete | 781961476 |
| Zakros | crete | 650881089 |
| Malia | crete | 589922 |
| Thera (Akrotiri) | aegean | 599478 |
| Pylos (Palace of Nestor) | mainland | 156116232 |
| Mycenae | mainland | 570491 |
| Miletus | anatolia | 599799 |
| Enkomi | levant | 13818291 |

Export the full list from the shell with `aegean geo lineara --json`.

---

## GeoJSON export

GeoDataFrames serialize as an EPSG:4326 GeoJSON `FeatureCollection` where each
column becomes a feature property and `geometry` becomes a GeoJSON `Point`.

### From the CLI

```bash
aegean geo lineara --level site -o la_sites.geojson
# wrote 52 features to la_sites.geojson

aegean geo lineara --level inscription -o la_inscriptions.geojson
# wrote 1718 features to la_inscriptions.geojson
```

First feature of the site-level export:

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

gdf.to_json()[:60]                               # GeoJSON string in memory
gdf.to_file("la_sites.geojson", driver="GeoJSON") # write to disk (any geopandas driver)
```

For non-spatial corpus exports (CSV, Parquet, EpiDoc, SQLite, RDF), see
[`aegean export`](CLI) and [Interoperability](Interoperability).

---

## Plotting

With `matplotlib` (`pip install 'pyaegean[viz]'`), plot a GeoDataFrame directly:

```python
gdf = geo.to_geodataframe(corpus, level="site")
ax = gdf.plot(markersize=gdf["inscriptions"] / 5)

wd = geo.word_distribution(corpus, "KU-RO")
wd.plot(markersize=wd["count"] * 10)
```

pyaegean does not bundle basemaps; overlay points onto `contextily` tiles or a
local coastline shapefile as needed. For non-spatial plots and a zero-`[geo]`
findspot scatter, see `aegean.viz` / `aegean plot` in [Analysis](Analysis).

---

## Coverage

`to_geodataframe` and `word_distribution` emit rows only for sites present in
the gazetteer:

| Corpus | Docs | Located sites | Notes |
| --- | --- | --- | --- |
| `lineara` | 1,721 | 52 of 52 site labels | 1,718 docs have a mapped site; 3 lack a site label |
| `linearb` | 18 | 3 of 3 (Knossos, Mycenae, Pylos) | Bundled sample |
| `cypriot` | 180 | 1 of 5 | Bundled *IG* XV 1 + samples (only generic Cyprus label mapped) |
| `cyprominoan` | 2 | 2 of 2 (Enkomi, Ugarit) | Bundled sample |

The gazetteer holds 94 entries total, covering all 52 named Linear A sites, the
other three Aegean scripts, and selected Greek epigraphic and papyrological
find-places (listed under [`aegean geo` flags](#aegean-geo-flags)).

---

## Limitations

- **Site-level precision (~1 km).** Coordinates are approximate points suitable
  for regional distribution mapping, not archaeological survey or metre-scale
  distances.
- **Unmapped inscriptions omitted.** Compare `len(corpus)` against `len(gdf)` to
  count excluded documents; the CLI prints `*N* located site(s) of *M*`.
- **Zero-hit `word_distribution` returns an empty GeoDataFrame.** Check
  `wd.empty` to distinguish zero attestations from unmapped sites.
- **Float display of `pleiades`.** Mixed int/null columns render as float in
  pandas; read `SiteCoord.pleiades` for the integer id.
- **16 unaligned entries.** Minor findspots, peak sanctuaries, caves, and the
  region-level `Crete` entry have `pleiades=None`.
- **Exact surface matching.** `word_distribution` folds case only; pass the
  corpus's transliteration spelling.

See [Limitations](Limitations) for project-wide boundaries.

---

## Provenance

Coordinates are compiled from standard archaeological references (GORILA,
Younger, public gazetteers) via the
[Linear A Research Workbench](https://github.com/ryanpavlicek/linearaworkbench)
(Apache-2.0). See [Data & Provenance](Data-and-Provenance) and `NOTICE`.

## See also

- [Installation](Installation): `[geo]` and `[viz]` extras
- [Linear A](Linear-A), [Linear B](Linear-B), [Cypriot](Cypriot), [Cypro-Minoan](Cypro-Minoan)
- [Analysis](Analysis)
- [CLI](CLI)
- [Data & Provenance](Data-and-Provenance)
