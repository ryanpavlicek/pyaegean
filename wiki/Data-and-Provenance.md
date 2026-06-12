# Data & Provenance

## Bundled vs fetched

Compact text data ships **inside the wheel** and works offline:

- Linear A: `inscriptions.json`, `signs.json`, `phonetic_map.json`
- Linear B / Cypriot: `signs.json`, `phonetic_map.json`, `lexicon.json`, `sample_inscriptions.json` (Unicode UCD)
- Cypro-Minoan: `signs.json`, `sample_inscriptions.json` (undeciphered — no phonetic map or lexicon)
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
repo. `fetch` downloads the `tar.gz` and unpacks it
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

`aegean.greek.use_treebank()` activates the lexicon derived from the Perseus
**Ancient Greek Dependency Treebank** (AGDT v2.1, Greek); `use_parser()` /
`use_tagger()` / `use_lemmatizer()` activate the models trained from the same
files. On first use each now fetches the small **prebuilt** artifact from the
project-hosted `agdt-derived` release asset (one ~15 MB bundle: the
form→lemma/morphology lexicon `agdt-greek-lexicon.json` plus the three trained
models; sha256-pinned). If that asset is ever unreachable, the original path
still works: download the AGDT itself (33 `.tb.xml` files, ~75 MB, pinned to a
fixed commit) and build/train locally. The treebank is **CC BY-SA 3.0**: the
source treebank is never re-hosted, the derived artifacts are published under
the same ShareAlike terms (CC BY-SA 3.0, clearly labeled), and everything is
fetched to the cache — never bundled in the Apache-2.0 wheel. Cite the AGDT in
work that relies on it. Network is needed only on the first call. See
[Greek NLP → Treebank-backed mode](Greek-NLP#treebank-backed-mode-opt-in).

### The Greek lexicon (LSJ, `use_lsj`)

`aegean.greek.use_lsj()` activates a lemma→entry index derived from the **Perseus
Liddell-Scott-Jones** lexicon. On first use it now fetches the **prebuilt** index
(`lsj-perseus-index.json.gz`, ~15 MB, sha256-pinned) from the project-hosted
`lsj-index` release asset; if that is unreachable it falls back to the original
path — downloading the TEI *A Greek-English Lexicon* itself (27 files, ~270 MB,
pinned to a fixed commit) and building the index locally. The LSJ is **CC BY-SA
4.0** (Perseus Digital Library, with NEH funding): the source TEI is never
re-hosted, the derived index is published under the same ShareAlike terms
(clearly labeled), and both are fetched to the cache — never bundled in the
Apache-2.0 wheel. Attribute Perseus per the statement in `NOTICE`. Network is
needed only on the first call. See
[Greek NLP → Lexicon (LSJ)](Greek-NLP#lexicon-lsj-glossing-opt-in).

### The Greek neural lemmatizer model (`use_neural_lemmatizer`, `[neural]`)

`aegean.greek.use_neural_lemmatizer()` activates a seq2seq lemmatizer that
generates the lemma for a form, reaching 76.3% on unseen forms. It pairs a
bundled gold lemma lookup (which answers attested forms) with the neural model
(which handles the rest); the model is fetched to the cache (~232 MB), never
bundled, and runs torch-free on numpy + onnxruntime, loaded only on activation.

Model card: the base model is **bowphs/GreTa**, an Ancient-Greek T5 released under
**Apache-2.0**. pyaegean fine-tunes it into a form→lemma seq2seq on the **AGDT**
(CC BY-SA 3.0), **Pedalion** (CC BY-SA 4.0), and **Gorman** (CC BY-SA 4.0) treebanks,
then exports the result to int8 ONNX. The released model is **CC BY-SA 4.0**,
fetched to the user cache and never bundled, so the wheel stays Apache-2.0. See
[Greek NLP → Neural lemmatizer](Greek-NLP#neural-lemmatizer-opt-in).

### The Greek neural joint pipeline model (`use_neural_pipeline`, `[neural]`)

`aegean.greek.use_neural_pipeline()` activates one jointly-trained model serving
POS, full morphology (UD FEATS), UD dependency trees, and lemmas from a single
forward pass — state of the art on the UD Ancient Greek benchmarks (see
[Greek NLP → The neural pipeline](Greek-NLP#the-neural-pipeline-opt-in) for the
measured numbers). The model bundle (fp32 ONNX + tokenizer + label maps + lemma
scripts/lookup, ~518 MB, sha256-pinned) is fetched to the cache, never bundled,
and runs torch-free on numpy + onnxruntime, loaded only on activation.

Model card: the base encoder is **bowphs/GreBerta** (Riemenschneider & Frank,
Apache-2.0). pyaegean fine-tunes it — tagging heads, a biaffine dependency parser,
and an edit-script lemma head — on the **AGDT** (CC BY-SA 3.0), **Gorman**
(CC BY-SA 4.0), and **Pedalion** (CC BY-SA 4.0) treebanks, with every sentence of
the UD-Perseus dev/test folds and all PROIEL evaluation texts **excluded from
training** (the leakage manifest is built by `agdt_ud_overlap()`; the protocol is
documented in
[`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md)).
The released bundle is **CC BY-SA 4.0**, fetched to the user cache and never
bundled, so the wheel stays Apache-2.0.

### The PROIEL evaluation set (`evaluate_on_proiel`)

`aegean.greek.evaluate_on_proiel()` scores the Greek lemmatizer/tagger against the
**PROIEL treebank** (Greek New Testament + Herodotus) — a source none of pyaegean's
models trained on — for a neutral, out-of-AGDT generalization number. PROIEL is
**CC BY-NC-SA 3.0**; it is fetched to the cache for **evaluation only**, read locally,
and never bundled or re-hosted (NonCommercial + ShareAlike). Cite Haug & Jøhndal (2008).
See [Greek NLP → Neutral evaluation](Greek-NLP#neutral-evaluation-out-of-agdt).

### Greek literary works (`greek.load_work`)

`aegean.greek.load_work("tlg0012.tlg001")` fetches one work's Greek TEI edition
from **Perseus canonical-greekLit** or **First1KGreek** (both CC BY-SA; tried in
that order, or pick with `source=`) into the cache and returns a standard
`Corpus` — one `Document` per book/chapter, verse lines or paragraphs as the
physical lines. The `ref=` argument **addresses a sub-section** instead of the
whole work, matching the work's citation structure:

```python
greek.load_work("tlg0012.tlg001", ref="1")          # Iliad book 1
greek.load_work("tlg0012.tlg001", ref="1.1-1.50")   # book 1, lines 1–50
greek.load_work("tlg0016.tlg001", ref="1.2")        # Herodotus book 1, chapter 2
```

Editorial `<note>` and `<bibl>` are excluded from the running text but kept in
`Document.meta.notes` (and they survive the JSON round-trip). The download is
**pinned to an upstream commit** (recorded as `Provenance.data_version`, e.g.
`PerseusDL/canonical-greekLit@d4fab69a2c26`), so a loaded work is reproducible;
override the ref with `PYAEGEAN_GREEKLIT_REF` / `PYAEGEAN_FIRST1K_REF`. Nothing
is re-hosted; cite the Perseus Digital Library / Open Greek and Latin and the
underlying edition (each file's TEI header names it).

### The SigLA corpus (`aegean.load("sigla")`)

The **SigLA** paleographical database (Salgarella & Castellan,
https://sigla.phis.me) publishes its dataset and drawings under
**CC BY-NC-SA 4.0**, and its paper invites use "outside the interface" and
notes copies can be hosted. pyaegean hosts the decoded dataset (the JSON form
the paper describes, reconstructed from the published web-app payload by
`scripts/build_sigla_corpus.py`) as the sha256-pinned `sigla-corpus-v1`
release asset — ~1 MB, fetched on demand, **never bundled** (NonCommercial
data stays out of the Apache-2.0 wheel; the NC + ShareAlike obligations pass
through to you). Attribution, citation, source sha256, and generation date
are inside the file's `_meta`; drawings are **not** included and remain at
sigla.phis.me. Cite SigLA in academic work.

### The DAMOS Linear B corpus (`aegean.load("damos")`)

**DAMOS** — the Database of Mycenaean at Oslo (F. Aurora,
https://damos.hf.uio.no) — is the most complete edition of the Mycenaean
(Linear B) corpus, published under **CC BY-NC-SA 4.0**. pyaegean hosts the
transliterations and core metadata (site, series, chronology, Trismegistos id)
for ~5,900 tablets, decoded from the DAMOS public web API into compact JSON
(`scripts/build_damos_corpus.py`) as the sha256-pinned `damos-corpus-v1`
release asset — fetched on demand, **never bundled** (NonCommercial data stays
out of the Apache-2.0 wheel; the NC + ShareAlike obligations pass through to
you). Attribution, citation, source URL, and generation date are inside the
file's `_meta`; no imagery is included. This is the openly-licensed full corpus
the bundled Linear B sample stands in for. Cite DAMOS (Aurora 2015) in academic
work.

## Data versioning — pinning for papers

Every dataset pyaegean can touch is versioned and hashable:

```python
from aegean import data
manifest = data.versions()
# {"package": "0.8.0",
#  "bundled": {"lineara/inscriptions.json": {"sha256": "…", "bytes": …}, …},
#  "fetched": {"grc-joint": {"url": "…", "sha256": "…", "cached": True}, …}}
```

Bundled data ships inside the wheel, so its version is the package version
(also stamped on every bundled corpus as `Provenance.data_version`); fetched
assets are sha256-pinned release files, verified on download. **To pin an
analysis for a paper**: record `aegean.__version__` and dump the manifest
(`aegean data versions --json > data-versions.json` from the CLI) alongside
your results — matching sha256s mean byte-identical data.

## Your own corpus

A scholar's own inscriptions get the full API (filter, query, DataFrames,
citation, export) without writing a loader:

```python
corpus = aegean.Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="myfind",
   provenance=aegean.Provenance(source="My dig notebook", citation="Me (2026)."))
```

Tokens may be plain strings (kinds inferred: parseable numerals vs words,
hyphenated tokens get their signs split) or dicts carrying `kind`, `status`
(editorial certainty), and `alt` (variant readings). Make it loadable by name
with `aegean.core.corpus.register_loader("myfind", lambda: corpus)`; for
EpiDoc sources, the bring-your-own reader (see [Linear B](Linear-B)) covers
the same model including `<unclear>`/`<supplied>` status and `<app>`/`<rdg>`
variants.

## Variant readings

`Token.alt` carries alternate readings alongside the editorial `status`. The
EpiDoc writer emits them as a critical apparatus —
`<app><lem><w>PO-ME</w></lem><rdg><w>PO-MA</w></rdg></app>` (validated against
the official EpiDoc schema) — and the reader folds them back to one token with
its `alt` tuple, so variants survive the EpiDoc *and* JSON round-trips.

## Provenance & citation

Every `Corpus` carries a `Provenance` that stamps exports and gives a citation:

```python
corpus = aegean.load("lineara")
corpus.provenance.source      # 'GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz'
corpus.provenance.license
corpus.provenance.cite()      # one-line citation for papers/logs

corpus.to_dict()["_meta"]      # tool, schemaVersion, scriptId, documentCount, source, license, citation
```

A note on the Linear A corpus: the bundled transcription is **normalized**, and
the apparatus the upstream data *does* carry is interpreted on load — its
erased-sign marks become `ReadingStatus.LOST` (552 tokens) and damaged or
bracketed-uncertain readings become `UNCLEAR` (120 tokens, across 366
documents). The **full** Leiden apparatus (restorations, dotted readings) was
dropped by the upstream digitization and remains absent; for edition-grade
readings consult **GORILA** and **SigLA**. `aegean.ReadingStatus` round-trips
through JSON and EpiDoc (`<unclear>`/`<supplied>`/`<gap>`), so bring-your-own
corpora keep their apparatus through a load/export cycle.

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
- **Greek neural lemmatizer (opt-in `[neural]`)** — a GreTa seq2seq (Apache-2.0 base)
  fine-tuned on the AGDT (CC BY-SA 3.0), Pedalion (CC BY-SA 4.0), and Gorman (CC BY-SA 4.0)
  treebanks. The model — int8 ONNX weights plus a derived gold lemma lookup — is **CC BY-SA 4.0**,
  fetched to the user cache (~232 MB), never bundled; the wheel stays Apache-2.0.
- **Greek neural joint pipeline (opt-in `[neural]`)** — a GreBerta-based joint model
  (Apache-2.0 base) fine-tuned on the AGDT (CC BY-SA 3.0), Gorman (CC BY-SA 4.0), and
  Pedalion (CC BY-SA 4.0) treebanks, evaluation folds excluded from training. The model
  bundle is **CC BY-SA 4.0**, fetched to the user cache (~518 MB), never bundled; the
  wheel stays Apache-2.0.
- **PROIEL evaluation set (opt-in)** — the PROIEL treebank (Greek NT + Herodotus),
  CC BY-NC-SA 3.0; fetched to the user cache for `evaluate_on_proiel` only, never bundled or
  redistributed (NonCommercial + ShareAlike).

See the repository `NOTICE` and `CITATION.cff` for full attribution.
