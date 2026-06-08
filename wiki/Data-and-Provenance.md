# Data & Provenance

## Bundled vs fetched

Compact text data ships **inside the wheel** and works offline:

- Linear A: `inscriptions.json`, `signs.json`, `phonetic_map.json`
- Greek: `sample_texts.json`, `lemmata.json`

Large or license-restricted assets are **never bundled** — they are fetched on
demand into a user cache. This keeps the wheel < 3 MB (CI guards it).

```python
from aegean.data import load_bundled_json
load_bundled_json("lineara", "signs.json")
```

## Download-to-cache: `fetch()`

`fetch(name)` downloads a registered remote dataset into the cache and returns
its path. Downloads are **sha256-verified** (when a checksum is pinned),
**atomic** (written to a `.part` file then renamed), and **idempotent** (a
present, valid cache file is a no-op).

```python
from aegean import data
data.cache_dir()                 # where datasets are cached (override: PYAEGEAN_CACHE)
path = data.fetch("lineara-images")
```

Errors are explicit and never block `import`:

- unknown dataset → `DataNotAvailableError`
- no pinned URL → `DataNotAvailableError` naming the env override to set
- checksum mismatch → `DataNotAvailableError` (the bad download is removed)

### The Linear A imagery (`lineara-images`)

The ~500 MB facsimile/photo set is **not redistributable** and is therefore
**intentionally left unpinned**. Its copyright is a patchwork — most images are
**© École Française d'Athènes** (the GORILA volumes), and others are held by
named scholars, publications, and photographers (see the corpus's per-image
`imageRights`). None carry a redistribution license, so pyaegean does not host or
pin them. Point the fetcher at a copy **you are licensed to use** with an env
override:

```bash
export PYAEGEAN_LINEARA_IMAGES_URL="https://example.org/lineara-images.tar"
```

```python
data.fetch("lineara-images")     # downloads from the override, sha-checked if pinned
```

The override pattern is general: `PYAEGEAN_<NAME>_URL` (uppercased, `-`→`_`)
overrides any dataset's URL.

## Provenance & citation

Every `Corpus` carries a `Provenance` that stamps exports and gives a citation:

```python
corpus = aegean.load("lineara")
corpus.provenance.source      # 'GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz'
corpus.provenance.license
corpus.provenance.cite()      # one-line citation for papers/logs

corpus.to_dict()["_meta"]      # tool, schemaVersion, scriptId, source, license, citation
```

## Licensing summary

- **Code** — Apache-2.0.
- **Linear A corpus JSON** — GORILA via mwenge/lineara.xyz (Apache-2.0).
- **Linear A facsimile imagery** — © École Française d'Athènes; referenced, not
  redistributed.
- **Greek sample corpus** — public-domain ancient texts (seed only).

See the repository `NOTICE` and `CITATION.cff` for full attribution.
