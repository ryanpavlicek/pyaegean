# Data & Provenance

## Bundled vs fetched

Compact text data ships **inside the wheel** and works offline:

- Linear A: `inscriptions.json`, `signs.json`, `phonetic_map.json`
- Greek: `sample_texts.json`, `lemmata.json`, `benchmark_gold.json`

Large or license-restricted assets are **never bundled** — they are fetched on
demand into a user cache. The wheel ships only code + tiny JSON (CI's
`scripts/check_footprint.py` enforces that, plus an instant, heavy-dep-free import).

```python
from aegean.data import load_bundled_json
load_bundled_json("lineara", "signs.json")
```

## Download-to-cache: `fetch()`

`fetch(name)` downloads a registered remote dataset into the cache and returns
its path. Downloads are **sha256-verified** (when a checksum is pinned),
**atomic** (written to a `.part` file then renamed), and **idempotent** (a
present, valid cache entry is a no-op). Archive datasets (`extract=True`, e.g.
`lineara-images`) are **unpacked** into a cache directory — safely (members that
escape the directory are rejected) — and `fetch()` returns that directory.

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

The facsimile/photo set (3,368 files, ~116 MB download, ~125 MB unpacked) is
**fetched (never re-hosted)** from a release on the `ryanpavlicek/linearaworkbench`
repo, where it is already hosted. `fetch` downloads the `tar.gz` and unpacks it
into a cache directory of images. Its copyright is a patchwork — most images are
**© École Française d'Athènes** (the GORILA volumes), others are held by named
scholars, publications, and photographers (see the corpus's per-image
`imageRights`); that attribution is unaffected by fetching, and pyaegean does not
redistribute the images itself.

The release asset's URL and sha256 are **pinned** (and verified), so a plain call
just works and is integrity-checked:

```python
data.fetch("lineara-images")     # downloads the pinned asset, sha256-verified, unpacks, caches
```

To fetch from your own mirror instead, set an env override (the pinned sha256 is
not enforced against an override):

```bash
export PYAEGEAN_LINEARA_IMAGES_URL="https://example.org/lineara-images.tar.gz"
```

The override pattern is general: `PYAEGEAN_<NAME>_URL` (uppercased, `-`→`_`)
overrides any dataset's URL.

### The Greek treebank lexicon (`use_treebank`)

`aegean.greek.use_treebank()` downloads the Perseus **Ancient Greek Dependency
Treebank** (AGDT v2.1, Greek) — 33 `.tb.xml` files, ~75 MB, pinned to a fixed
commit — into the cache, then builds a derived form→lemma/morphology lexicon there
(`agdt-greek-lexicon.json`); `use_parser()` trains a dependency-parser model
(`agdt-parser-model.json.gz`), `use_tagger()` trains a POS-tagger model
(`agdt-postagger.json.gz`), and `use_lemmatizer()` trains an edit-tree lemmatizer model
(`agdt-lemmatizer.json.gz`) from the same files. The treebank is **CC BY-SA 3.0**; it is fetched (never
re-hosted), and the derived lexicon stays in the local cache — pyaegean neither
bundles nor redistributes it, so the ShareAlike terms don't reach the Apache-2.0
package. Cite the AGDT in work that relies on it. Network is needed only on the
first call; the build is idempotent thereafter. See
[Greek NLP → Treebank-backed mode](Greek-NLP#treebank-backed-mode-opt-in).

### The Greek lexicon (LSJ, `use_lsj`)

`aegean.greek.use_lsj()` downloads the **Perseus Liddell-Scott-Jones** lexicon (the
TEI *A Greek-English Lexicon* — 27 files, ~270 MB, pinned to a fixed commit) into the
cache and builds a derived, gzipped lemma→entry index there (`lsj-perseus-index.json.gz`,
~15 MB). The LSJ is **CC BY-SA 4.0** (Perseus Digital Library, with NEH funding); it is
fetched (never re-hosted) and the index stays in the local cache — pyaegean neither
bundles nor redistributes it. Attribute Perseus per the statement in `NOTICE`. Network
is needed only on the first call. See
[Greek NLP → Lexicon (LSJ)](Greek-NLP#lexicon-lsj-glossing-opt-in).

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
- **Greek treebank lexicon (opt-in)** — Perseus AGDT v2.1, CC BY-SA 3.0; fetched
  and built in the user cache, never bundled or redistributed.
- **Greek lexicon / LSJ (opt-in)** — Perseus Liddell-Scott-Jones, CC BY-SA 4.0;
  fetched and indexed in the user cache, never bundled or redistributed.

See the repository `NOTICE` and `CITATION.cff` for full attribution.
