# Data & Provenance

This page is the honest accounting of **where every byte comes from**: what
ships inside the wheel, what gets fetched on demand, the license and size of
each dataset, how the cache works, and how to pin an exact data snapshot so a
paper is reproducible. If you ever need to answer "what edition is this, and may
I redistribute it?", the answer is here.

The short version: **code and tiny text JSON are bundled and work offline; large
or license-restricted assets are never bundled: they download into a local
cache on first use, sha256-verified.** Nothing is re-hosted that the license
forbids re-hosting.

---

## Bundled vs fetched

Compact text data ships **inside the wheel** and works offline with zero
third-party dependencies:

- **Linear A**: `inscriptions.json`, `signs.json`, `phonetic_map.json`, `manifest.json`
- **Linear B**: `signs.json`, `phonetic_map.json`, `lexicon.json`, `sample_inscriptions.json` (Unicode UCD)
- **Cypriot**: `signs.json`, `phonetic_map.json`, `lexicon.json`, `sample_inscriptions.json`, `ig_inscriptions.json` (the bundled 178-inscription IG XV 1 corpus, CC BY 4.0)
- **Cypro-Minoan**: `signs.json`, `sample_inscriptions.json` (undeciphered: no phonetic map or lexicon)
- **Greek**: `sample_texts.json`, `lemmata.json`, `idioms.json` (the bundled idiom/MWE gloss lexicon), `benchmark_gold.json`, `nt_sample.json` (two NT sample chapters: John 1 + Philemon 1), `dodson.json` (Koine lexicon), `works_catalogue.json` (the offline `greek.catalog` discovery index: metadata only, no texts)
- **Geo**: `site_coordinates.json` (approximate find-site lat/long)

Large or license-restricted assets are **never bundled**: they are fetched on
demand into a user cache. The wheel ships only code + tiny JSON (CI's
`scripts/check_footprint.py` enforces that, plus an instant, heavy-dep-free
import).

```python
from aegean.data import load_bundled_json
signs = load_bundled_json("lineara", "signs.json")
len(signs)
# 342
```

### Every bundled JSON file (verified)

This is exactly what `aegean.data.versions()` reports as `bundled`: each file
hashed straight out of the installed wheel. Sizes are bytes.

| File | Bytes | Source |
|---|---|---|
| `cypriot/ig_inscriptions.json` | 75,677 | *Inscriptiones Graecae* XV 1 (BBAW, CC BY 4.0) |
| `cypriot/lexicon.json` | 1,377 | Unicode UCD + scholarly excerpts |
| `cypriot/phonetic_map.json` | 712 | Unicode UCD |
| `cypriot/sample_inscriptions.json` | 465 | scholarly excerpts (Masson; Chadwick) |
| `cypriot/signs.json` | 7,032 | Unicode UCD (Cypriot Syllabary) |
| `cyprominoan/sample_inscriptions.json` | 389 | scholarly excerpts (Ferrara) |
| `cyprominoan/signs.json` | 12,681 | Unicode UCD (Cypro-Minoan block) |
| `geo/site_coordinates.json` | 6,218 | GORILA / Younger / public gazetteers |
| `greek/benchmark_gold.json` | 6,550 | gold benchmark fixtures |
| `greek/dodson.json` | 712,301 | Dodson Greek Lexicon (CC0) |
| `greek/idioms.json` | 6,675 | bundled idiom / MWE gloss lexicon |
| `greek/lemmata.json` | 1,545 | bundled gold lemma seed |
| `greek/nt_sample.json` | 132,814 | Nestle 1904: two sample chapters, John 1 + Philemon 1 (CC0) |
| `greek/sample_texts.json` | 1,054 | public-domain Greek snippets |
| `greek/works_catalogue.json` | 293,563 | Perseus + First1KGreek work index (metadata only; built by `scripts/build_greek_catalogue.py`) |
| `lineara/inscriptions.json` | 720,766 | GORILA via mwenge/lineara.xyz |
| `lineara/manifest.json` | 454 | corpus manifest |
| `lineara/phonetic_map.json` | 648 | Linear A sound values |
| `lineara/signs.json` | 63,272 | Linear A sign inventory |
| `linearb/lexicon.json` | 12,071 | Unicode UCD + Wiktionary/kaikki excerpts |
| `linearb/phonetic_map.json` | 986 | Unicode UCD |
| `linearb/sample_inscriptions.json` | 7,198 | scholarly excerpts (Ventris & Chadwick) |
| `linearb/signs.json` | 36,030 | Unicode UCD (Linear B Syllabary + Ideograms) |

---

## Download-to-cache: `fetch()`

`fetch(name)` downloads a registered remote dataset into the cache and returns
its path. Downloads are **sha256-verified** (when a checksum is pinned),
**atomic** (written to a `.part` file then renamed), **idempotent** (a
present, valid cache entry is a no-op), and **resumable**: an interrupted
download keeps its `.part` file, and the next attempt continues from where it
stopped with an HTTP `Range` request instead of restarting a multi-hundred-MB
asset from zero (a republished asset is detected and restarted cleanly).
Archive datasets (`extract=True`, e.g. `lineara-images`) are **unpacked** into
a cache directory, safely (members that escape the directory are rejected),
and `fetch()` returns that directory.

> **A fetched dataset is permanent until you delete it.** The "cache" is a
> permanent local store, not an evicting one: `fetch()` performs a complete
> one-time download, and nothing ever re-fetches, evicts, or expires the
> result. An entry stays on disk until you remove it (`aegean data remove
> NAME`, or `aegean data remove --all` to clear every downloaded dataset) or
> replace it with `fetch(name, force=True)`.

```python
from aegean import data

data.cache_dir()                 # where datasets are cached (override: PYAEGEAN_CACHE)
path = data.fetch("nt-corpus")   # returns the cached file path; no-op if already valid
path.exists(), path.is_file()
# (True, True)
```

Errors are explicit and never block `import`:

| Situation | Raised | Message detail |
|---|---|---|
| unknown dataset | `DataNotAvailableError` | `unknown dataset 'nope'; known: [...]` |
| no pinned URL | `DataNotAvailableError` | names the `PYAEGEAN_<NAME>_URL` to set |
| checksum mismatch | `DataNotAvailableError` | expected vs got; the bad download is removed |
| unsafe archive member | `DataNotAvailableError` | `unsafe path in archive: ...` |
| network failure | `DataNotAvailableError` | `could not fetch '<name>' from <url>: ...` |

```python
from aegean import data
try:
    data.fetch("linearb-corpus")             # has no default URL
except data.DataNotAvailableError as e:
    print(str(e)[:70])
# dataset 'linearb-corpus' has no pinned download URL yet (A user-suppli...
```

`fetch(name, force=True)` re-downloads even when a valid copy is cached.

---

## The fetchable datasets — every one, with license, provenance, size

These are the registered remote datasets (`aegean data list`). Every one is
**fetched to the user cache on demand and never bundled** in the Apache-2.0
wheel. Each URL and sha256 is pinned in the code; an env override
(`PYAEGEAN_<NAME>_URL`, see below) points any of them at your own licensed copy.

| Dataset (`name`) | What it is | Size | License | Provenance |
|---|---|---|---|---|
| `lineara-images` | 3,368 facsimile/photo files (archive) | ~116 MB tar.gz, ~119 MB unpacked | © École Française d'Athènes + other rightsholders: academic reference only | Fetched from the `ryanpavlicek/linearaworkbench` release; never re-hosted |
| `agdt-derived` | Prebuilt AGDT lexicon + tagger/lemmatizer/parser models | ~15 MB | CC BY-SA 3.0 (derived from Perseus AGDT) | Project-hosted derivative of the AGDT |
| `lsj-index` | Prebuilt LSJ lemma→entry index | ~15 MB | CC BY-SA 4.0 (Perseus Digital Library) | Project-hosted derivative of the Perseus LSJ |
| `middle-liddell-index` | Prebuilt Middle Liddell lemma→entry index | ~2.3 MB | public domain (1889); Perseus / Scaife digitization | Project-hosted; `use_lexicon("middle-liddell")` |
| `cunliffe-index` | Prebuilt Cunliffe (Homeric) lemma→entry index | ~1.3 MB | public domain (1924); Scaife data MIT | Project-hosted; `use_lexicon("cunliffe")` |
| `abbott-smith-index` | Prebuilt Abbott-Smith (NT) lemma→entry index | ~130 KB | public domain (1922) | Project-hosted; `use_lexicon("abbott-smith")` |
| `grc-lemma-neural` | GreTa seq2seq lemmatizer (int8 ONNX + tokenizer + gold lookup) | ~232 MB tar.gz | CC BY-SA 4.0: derived from AGDT (3.0) + Pedalion (4.0) + Gorman (4.0) | `[neural]` extra; fine-tuned from bowphs/GreTa (Apache-2.0 base) |
| `grc-joint` | Joint tagger-parser-lemmatizer (quantized ONNX + tokenizer + label maps + lemma scripts/lookup) | ~173 MB tar.gz | CC BY-SA 4.0: derived from AGDT (3.0) + Gorman (4.0) + Pedalion (4.0) | `[neural]` extra; GreBerta-based (Apache-2.0 base), eval folds excluded |
| `sigla-corpus` | SigLA-derived Linear A dataset v2: 781 docs, 1,376 word-division groups (SigLA's own division; these plus standalone single signs load as ~1,868 WORD tokens) + commodity ideograms | ~1.2 MB JSON | CC BY-NC-SA 4.0 (SigLA: Salgarella & Castellan) | Decoded from the SigLA web-app payload; drawings stay at sigla.phis.me |
| `damos-corpus` | DAMOS Linear B corpus v2: ~5,900 tablets, transliterations + metadata | ~3 MB JSON | CC BY-NC-SA 4.0 (DAMOS: F. Aurora) | Decoded from the DAMOS public API; no imagery |
| `nt-corpus` | Greek NT (Nestle 1904): 260 chapters / ~137,800 tokens, gold lemma + Robinson morph + Strong's + UD UPOS | ~16 MB JSON | CC0-1.0 (morphology/lemmas/Strong's); base text public domain | From biblicalhumanities/Nestle1904; **may be redistributed** (CC0) |
| `workbench-app` | Prebuilt Linear A Research Workbench static web app (archive) | ~3 MB tar.gz | Apache-2.0 (build); embedded Linear A data is GORILA-derived | Served locally by `aegean workbench` |
| `linearb-corpus` | A user-supplied Linear B export (bring-your-own) |: (no default source) | bring-your-own; DAMOS is CC BY-NC-SA 4.0, LiBER all-rights-reserved | Set `PYAEGEAN_LINEARB_CORPUS_URL` to your own licensed copy |

> **Why two licenses keep appearing.** "Project-hosted" derivatives (DAMOS,
> SigLA, the LSJ index, the AGDT-derived models, the neural models) are republished
> under the **same ShareAlike terms** as their source, clearly labeled, and kept
> out of the Apache-2.0 wheel. NonCommercial obligations (DAMOS, SigLA, PROIEL)
> **pass through to you**. CC0 assets (the NT corpus, the Dodson lexicon) carry no
> such obligation, which is exactly why two NT sample chapters can be bundled.

### Per-dataset notes

#### The Linear A imagery (`lineara-images`)

The facsimile/photo set (3,368 files, ~116 MB download, ~119 MB unpacked) is
**fetched (never re-hosted)** from a release on the `ryanpavlicek/linearaworkbench`
repo. `fetch` downloads the `tar.gz` and unpacks it into a cache directory of
images. Its copyright is a patchwork: most images are **© École Française
d'Athènes** (the
[GORILA volumes](https://cefael.efa.gr/result.php?serie_title_operator=con&volume_number_operator=%3D&issue_year_operator=%3D&section_title=Recueil+des+inscriptions+en+lin%C3%A9aire+A&section_title_operator=con&author_lastname_operator=con&publisher_name_operator=con&site_id=1&actionID=advanced&operator=AND),
digitized in the École's CEFAEL library at that link), others are held by named
scholars, publications, and photographers (see the corpus's per-image
`imageRights`); that attribution is unaffected by fetching, and pyaegean does not
redistribute the images itself.

The release asset's URL and sha256 are **pinned** (and verified), so a plain call
just works and is integrity-checked:

```python
from aegean import data
data.fetch("lineara-images")     # downloads the pinned asset, sha256-verified, unpacks, caches → a directory
```

To fetch from your own mirror instead, set an env override (the pinned sha256 is
not enforced against an override):

```bash
export PYAEGEAN_LINEARA_IMAGES_URL="https://example.org/lineara-images.tar.gz"
```

#### The Greek treebank lexicon & models (`agdt-derived`, `use_treebank`)

`aegean.greek.use_treebank()` activates the lexicon derived from the Perseus
**Ancient Greek Dependency Treebank** (AGDT v2.1, Greek); `use_parser()` /
`use_tagger()` / `use_lemmatizer()` activate the models trained from the same
files. On first use each fetches the small **prebuilt** artifact from the
project-hosted `agdt-derived` release asset (one ~15 MB bundle: the
form→lemma/morphology lexicon `agdt-greek-lexicon.json` plus the three trained
models; sha256-pinned). If that asset is ever unreachable, the original path
still works: download the AGDT itself (33 `.tb.xml` files, ~75 MB, pinned to a
fixed commit) and build/train locally. The treebank is **CC BY-SA 3.0**: the
source treebank is never re-hosted, the derived artifacts are published under the
same ShareAlike terms (clearly labeled), and everything is fetched to the cache:
never bundled in the Apache-2.0 wheel. Cite the AGDT in work that relies on it.
Network is needed only on the first call. See
[Greek NLP → Treebank-backed mode](Greek-NLP#treebank-backed-mode-opt-in).

#### The Greek lexicon (LSJ, `lsj-index`, `use_lsj`)

`aegean.greek.use_lsj()` activates a lemma→entry index derived from the **Perseus
Liddell-Scott-Jones** lexicon. On first use it fetches the **prebuilt** index
(`lsj-perseus-index.json.gz`, ~15 MB, sha256-pinned) from the project-hosted
`lsj-index` release asset; if that is unreachable it falls back to the original
path: downloading the TEI *A Greek-English Lexicon* itself (27 files, ~270 MB,
pinned to a fixed commit) and building the index locally. The LSJ is **CC BY-SA
4.0** (Perseus Digital Library, with NEH funding): the source TEI is never
re-hosted, the derived index is published under the same ShareAlike terms (clearly
labeled), and both are fetched to the cache: never bundled in the Apache-2.0
wheel. Attribute Perseus per the statement in `NOTICE`. Network is needed only on
the first call. See [Greek NLP → Lexicon (LSJ)](Greek-NLP#lexicon-lsj-glossing-opt-in).

#### More dictionaries (the lexicon registry)

Beyond LSJ and the bundled Dodson, `greek.use_lexicon(id)` activates three more
dictionaries. Each fetches a small prebuilt lemma→entry index (the `middle-liddell-index` /
`cunliffe-index` / `abbott-smith-index` assets above) to the cache on first use; if that is
unreachable it builds the index from the upstream source instead. Never bundled:

- **Middle Liddell** (*An Intermediate Greek-English Lexicon*) and **Cunliffe** (*A Lexicon
  of the Homeric Dialect*) are built from the structured JSONL in
  `scaife-viewer/atlas-data-prep` (pinned to a commit; the repository is MIT-licensed). The
  underlying lexica are public domain (1889 / 1924), digitized by Perseus and the Scaife
  Viewer; attribute both.
- **Abbott-Smith** (*A Manual Greek Lexicon of the New Testament*, 1922) is built from the TEI
  in `translatable-exegetical-tools/Abbott-Smith` (pinned to a commit); text and markup are
  public domain.

Dictionaries that are not openly redistributable (Autenrieth, Slater, Montanari, DGE, Bailly)
are not hosted; `greek.lexicon_link(word)` builds a Logeion deep-link to them instead. None of
these is bundled in the Apache-2.0 wheel. See [Greek NLP → the lexicon registry](Greek-NLP#more-dictionaries-the-lexicon-registry).

#### The Greek neural lemmatizer model (`grc-lemma-neural`, `use_neural_lemmatizer`, `[neural]`)

`aegean.greek.use_neural_lemmatizer()` activates a seq2seq lemmatizer that
generates the lemma for a form, reaching 76.3% on unseen forms. It pairs a
bundled gold lemma lookup (which answers attested forms) with the neural model
(which handles the rest); the model is fetched to the cache (~232 MB), never
bundled, and runs torch-free on numpy + onnxruntime, loaded only on activation.

Model card: the base model is **bowphs/GreTa**, an Ancient-Greek T5 released under
**Apache-2.0**. pyaegean fine-tunes it into a form→lemma seq2seq on the **AGDT**
(CC BY-SA 3.0), **Pedalion** (CC BY-SA 4.0), and **Gorman** (CC BY-SA 4.0)
treebanks, then exports the result to int8 ONNX. The released model is **CC BY-SA
4.0**, fetched to the user cache and never bundled, so the wheel stays Apache-2.0.
See [Greek NLP → Neural lemmatizer](Greek-NLP#neural-lemmatizer-opt-in).

#### The Greek neural joint pipeline model (`grc-joint`, `use_neural_pipeline`, `[neural]`)

`aegean.greek.use_neural_pipeline()` activates one jointly-trained model serving
POS, full morphology (UD FEATS), UD dependency trees, and lemmas from a single
forward pass: state of the art on the UD Ancient Greek (Perseus) benchmark (see
[Greek NLP → The neural pipeline](Greek-NLP#the-neural-pipeline-opt-in) for the
measured numbers). The model bundle (quantized ONNX + tokenizer + label maps + lemma
scripts/lookup, ~173 MB tar.gz, sha256-pinned) is fetched to the cache, never bundled,
and runs torch-free on numpy + onnxruntime, loaded only on activation. The released
model is quantized and lossless (weight-only int8 on the MatMul weights plus fp16
elsewhere, activations kept fp32), so the UD Ancient Greek scores are unchanged from
the full-precision model; it needs `onnxruntime>=1.23` for the 8-bit kernel. The
full-precision (fp32) model stays available at the `grc-joint-v2` release for
reproducibility.

Model card: the base encoder is **bowphs/GreBerta** (Riemenschneider & Frank,
Apache-2.0). pyaegean fine-tunes it: tagging heads, a biaffine dependency parser,
and an edit-script lemma head: on the **AGDT** (CC BY-SA 3.0), **Gorman**
(CC BY-SA 4.0), and **Pedalion** (CC BY-SA 4.0) treebanks, with every sentence of
the UD-Perseus dev/test folds and all PROIEL evaluation texts **excluded from
training** (the leakage manifest is built by `agdt_ud_overlap()`; the protocol is
documented in
[Benchmarks](Benchmarks)).
The released bundle is **CC BY-SA 4.0**, fetched to the user cache and never
bundled, so the wheel stays Apache-2.0.

#### The PROIEL evaluation set (`evaluate_on_proiel`)

`aegean.greek.evaluate_on_proiel()` scores the Greek lemmatizer/tagger against the
**PROIEL treebank** (Greek New Testament + Herodotus): a source none of pyaegean's
models trained on: for a neutral, out-of-AGDT generalization number. PROIEL is
**CC BY-NC-SA 3.0**; it is fetched to the cache for **evaluation only**, read
locally, and never bundled or re-hosted (NonCommercial + ShareAlike). Cite Haug &
Jøhndal (2008). See [Greek NLP → Neutral evaluation](Greek-NLP#neutral-evaluation-out-of-agdt).

> The Universal Dependencies Ancient Greek treebanks (Perseus, CC BY-NC-SA 2.5;
> PROIEL, CC BY-NC-SA 3.0) and the CoNLL-2018 evaluator (MPL-2.0) are likewise fetched
> for `evaluate_on_ud()` only, never bundled, never trained on. See `NOTICE`.

#### The SigLA corpus (`sigla-corpus`, `aegean.load("sigla")`)

The **SigLA** paleographical database (Salgarella & Castellan,
https://sigla.phis.me) publishes its dataset and drawings under
**CC BY-NC-SA 4.0**, and its paper invites use "outside the interface" and notes
copies can be hosted. pyaegean hosts the decoded dataset (the JSON form the paper
describes, reconstructed from the published web-app payload by
`scripts/build_sigla_corpus.py`) as the sha256-pinned `sigla-corpus` release
asset: **781 documents** with SigLA's own word division (1,376 words) and
commodity ideograms (~1.2 MB), fetched on demand, **never bundled** (NonCommercial
data stays out of the Apache-2.0 wheel; the NC + ShareAlike obligations pass
through to you). Attribution, citation, source sha256, and generation date are
inside the file's `_meta`; drawings are **not** included and remain at
sigla.phis.me. Cite SigLA in academic work.

```python
import aegean
s = aegean.load("sigla")
len(s)                       # 781
s.provenance.license         # 'CC BY-NC-SA 4.0 (as published by SigLA; ...)'
```

#### The DAMOS Linear B corpus (`damos-corpus`, `aegean.load("damos")`)

**DAMOS**: the Database of Mycenaean at Oslo (F. Aurora, https://damos.hf.uio.no),
the most complete edition of the Mycenaean (Linear B) corpus, published under
**CC BY-NC-SA 4.0**. pyaegean hosts the transliterations and core metadata (site,
series, chronology, Trismegistos id, scribal hands, find context, object class)
for **~5,900 tablets**, decoded from the DAMOS public web API into compact JSON
(`scripts/build_damos_corpus.py`) as the sha256-pinned `damos-corpus` release
asset: fetched on demand, **never bundled** (NonCommercial data stays out of the
Apache-2.0 wheel; the NC + ShareAlike obligations pass through to you).
Attribution, citation, source URL, and generation date are inside the file's
`_meta`; no imagery is included. This is the openly-licensed full corpus the
bundled Linear B sample stands in for. Cite DAMOS (Aurora 2015) in academic work.

```python
import aegean
d = aegean.load("damos")
len(d)                       # 5932 documents
d.provenance.source          # 'DAMOS — Database of Mycenaean at Oslo (F. Aurora), ...'
```

#### The Greek New Testament + Dodson lexicon (`nt-corpus`, `greek.load_nt`, `use_dodson`)

The **Nestle 1904** Greek NT base text is public domain; its per-token morphology,
lemmas, and Strong's numbers (from biblicalhumanities/Nestle1904) are dedicated to
the public domain under **CC0**. Because CC0 imposes no restriction, **two sample chapters are
bundled** in the wheel (`greek/nt_sample.json`, ~130 KB: John 1 + Philemon 1) as an offline sample, and
the full **27-book corpus** (260 chapters / ~137,800 tokens) is hosted as the
`nt-corpus` release asset, fetched on demand by `greek.load_nt` /
`aegean.load("nt")`. Koine glossing uses the **Dodson Greek Lexicon** (J. J.
Dodson; **CC0**), which is small enough to bundle in the wheel (~712 KB,
`greek.use_dodson`). Cite the Nestle 1904 edition and Dodson in academic work.

```python
import aegean
from aegean import greek

nt = aegean.load("nt")           # full corpus (fetched on first use; cached after)
len(nt)                          # 260 chapters

greek.use_dodson()               # activate the bundled Koine lexicon (offline)
greek.gloss_strongs("G3056")     # 'a word, speech, divine utterance, ...'  (λόγος)
```

`greek.load_nt(book, ref=...)` loads one book or a sub-reference rather than the
whole corpus: its signature is `load_nt(book=None, *, ref=None, force=False)`.

#### Greek literary works (`greek.load_work`)

`aegean.greek.load_work("tlg0012.tlg001")` fetches one work's Greek TEI edition
from **Perseus canonical-greekLit** or **First1KGreek** (both CC BY-SA; tried in
that order, or pick with `source=`) into the cache and returns a standard
`Corpus`: one `Document` per book/chapter, verse lines or paragraphs as the
physical lines. Its signature is
`load_work(work, *, ref=None, source="auto", edition=None, force=False)`. The
`ref=` argument **addresses a sub-section** instead of the whole work, matching
the work's citation structure:

```python
from aegean import greek
greek.load_work("tlg0012.tlg001", ref="1")          # Iliad book 1
greek.load_work("tlg0012.tlg001", ref="1.1-1.50")   # book 1, lines 1–50
greek.load_work("tlg0016.tlg001", ref="1.2")        # Herodotus book 1, chapter 2
```

> These three are real work/ref ids but each first call hits the network and
> parses TEI: run them when you actually need the text, not as a smoke test.

To **discover** which work ids exist without any download, use the bundled
discovery index `greek.catalog()` (the `works_catalogue.json` listed above):
metadata only (id, author, English + Greek title, source), so it works **offline
and instantly**. It covers every work with a Greek (`-grc`) edition in the two
upstream repos at the pinned commits: **1,778 works** (768 Perseus + 1,010
First1KGreek). The texts themselves are still fetched on demand; only the index
is bundled.

```python
from aegean import greek
len(greek.catalog())                       # 1778  (all works)
len(greek.catalog(source="perseus"))       # 768
greek.catalog(author="plato")[1]
# {'id': 'tlg0059.tlg002', 'author': 'Plato', 'title': 'Apology',
#  'greek_title': 'Ἀπολογία Σωκράτους', 'source': 'perseus'}
```

```bash
aegean greek catalog --author homer --source perseus --limit 2 --json
# {"matched": 36, "works": [
#   {"id": "tlg0012.tlg001", "author": "Homer", "title": "Iliad",
#    "greek_title": "Ἰλιάς", "source": "perseus"}, ...]}
```

(`--limit` caps the `works` list in `--json` and `-o` output too; the untruncated
match count is always in `matched`.)

Coverage is exactly what the open repos hold at the pinned commit, so some
authors are genuinely absent upstream (e.g. Sappho, `tlg0009`) and thus absent
here: that is honest, not a gap in pyaegean. The curated `greek.popular_works()`
(25 well-known works) is the small hand-picked counterpart. See
[Greek Works & Books](Greek-Works-and-Books).

Editorial `<note>` and `<bibl>` are excluded from the running text but kept in
`Document.meta.notes` (and they survive the JSON round-trip). The download is
**pinned to an upstream commit** (recorded as `Provenance.data_version`, e.g.
`PerseusDL/canonical-greekLit@d4fab69a2c26`), so a loaded work is reproducible;
override the ref with `PYAEGEAN_GREEKLIT_REF` / `PYAEGEAN_FIRST1K_REF`. Nothing is
re-hosted; cite the Perseus Digital Library / Open Greek and Latin and the
underlying edition (each file's TEI header names it).

#### The Linear A Workbench app (`workbench-app`) and bring-your-own Linear B (`linearb-corpus`)

`workbench-app` is the prebuilt Linear A Research Workbench static web app (~3 MB
tar.gz, Apache-2.0 build; the embedded Linear A data is GORILA-derived). It is
fetched and unpacked on demand and served locally by `aegean workbench`.

`linearb-corpus` is a **bring-your-own** slot with **no default source**: it
exists so you can point pyaegean at a local licensed Linear B export (e.g. a DAMOS
EpiDoc download, or a LiBER selection) without a code change. DAMOS itself is now
loadable directly via `aegean.load("damos")`; LiBER is © CNR Edizioni, all rights
reserved, and is neither bundled nor fetched. Set
`PYAEGEAN_LINEARB_CORPUS_URL` (or `PYAEGEAN_LINEARB_CORPUS`) to your own copy;
calling `fetch("linearb-corpus")` with nothing set raises a clear error.

---

## The CLI: `aegean data`

Every data operation has a CLI mirror (`pip install "pyaegean[cli]"`). The
subcommands:

| Command | What it does | Flags |
|---|---|---|
| `aegean data list` | List the fetchable datasets (name, size note, license) with a **downloaded** column: whether each is in the local store, and its actual on-disk size | `--json` (machine-readable on stdout), `-h/--help` |
| `aegean data fetch NAME` | One-time download into the local store (sha256-verified); a no-op when already present; an interrupted transfer resumes | `--force` (replace the stored copy), `-h/--help` |
| `aegean data remove NAME` | Delete a downloaded dataset from the store, printing what was removed and the space reclaimed | `--all` (delete every downloaded dataset), `--json`, `-h/--help` |
| `aegean data versions` | The reproducibility manifest: every dataset's version + sha256 | `--json` (machine-readable on stdout), `-h/--help` |
| `aegean data store` | Show the store location and its current contents (entries are permanent until removed). `aegean data cache` remains a deprecated alias this minor: it warns, naming the replacement | `--json` (machine-readable on stdout), `-h/--help` |

```bash
aegean data store
#          local data store:
# C:\Users\you\.cache\pyaegean
#  (override with PYAEGEAN_CACHE)
# ┌───────────────────────────┬───────┐
# │ entry                     │ MB    │
# ├───────────────────────────┼───────┤
# │ damos-corpus              │ 3.1   │
# │ nt-corpus                 │ 15.8  │
# │ ...                       │ ...   │
# └───────────────────────────┴───────┘
```

```bash
aegean data fetch nt-corpus            # downloads + verifies; a no-op if already cached
aegean data fetch lineara-images --force   # re-download even if cached
aegean data remove nt-corpus           # delete one downloaded dataset (prints what + how much)
aegean data remove --all               # clear every downloaded dataset
```

The same store is visible to AI agents over MCP (`aegean-mcp`, the `[mcp]`
extra), which exposes fifteen read/analysis tools: `list_corpora`, `corpus_info`,
`show_document`, `search_signs`, `balance_accounts`, `query_corpus`,
`cite_corpus`, `geo_sites`, `data_status`, `greek_pipeline`, `greek_scan`,
`greek_catalog`, `greek_work`, `greek_gloss`, and `koine_gloss`. Three of them
touch the story this page tells: `data_status` exposes this listing read-only
(downloaded state, on-disk size, license note), so an agent can see what a
corpus load would fetch before triggering it; `cite_corpus` / `query_corpus`
carry the exact-subset citation (below) over MCP; and the tools that may fetch
(`greek_work` texts and the non-bundled `greek_gloss` dictionaries) download
into this same store on first use and are offline after. Corpora and works are
addressed by registry name or catalogue work id only, never a filesystem path.

---

## Environment overrides

Three environment variables control where data lives and where it comes from.

| Variable | Effect |
|---|---|
| `PYAEGEAN_CACHE` | The cache root. Falls back to `XDG_CACHE_HOME`, then `~/.cache`. The package always writes under `<base>/pyaegean`. |
| `PYAEGEAN_<NAME>_URL` | Override one dataset's download URL with your own mirror/licensed copy. Uppercase the name and turn `-` into `_`. When set, the pinned sha256 is **not** enforced (it described the pinned URL only). |
| `PYAEGEAN_GREEKLIT_REF` / `PYAEGEAN_FIRST1K_REF` | Override the upstream commit `load_work` pins to. |

The `PYAEGEAN_<NAME>_URL` pattern is mechanical: here is the exact name for each
dataset (verified):

| Dataset | Override variable |
|---|---|
| `lineara-images` | `PYAEGEAN_LINEARA_IMAGES_URL` |
| `agdt-derived` | `PYAEGEAN_AGDT_DERIVED_URL` |
| `lsj-index` | `PYAEGEAN_LSJ_INDEX_URL` |
| `grc-lemma-neural` | `PYAEGEAN_GRC_LEMMA_NEURAL_URL` |
| `grc-joint` | `PYAEGEAN_GRC_JOINT_URL` |
| `sigla-corpus` | `PYAEGEAN_SIGLA_CORPUS_URL` |
| `damos-corpus` | `PYAEGEAN_DAMOS_CORPUS_URL` |
| `nt-corpus` | `PYAEGEAN_NT_CORPUS_URL` |
| `workbench-app` | `PYAEGEAN_WORKBENCH_APP_URL` |
| `linearb-corpus` | `PYAEGEAN_LINEARB_CORPUS_URL` |

```bash
# point a dataset at your own mirror (sha256 not enforced against an override)
export PYAEGEAN_LINEARA_IMAGES_URL="https://example.org/lineara-images.tar.gz"

# keep all cached data on a big external drive
export PYAEGEAN_CACHE="/mnt/data/pyaegean-cache"
```

Find the cache from code or the CLI at any time:

```python
from aegean import data
data.cache_dir()    # e.g. WindowsPath('C:/Users/you/.cache/pyaegean')
```

---

## Data versioning — pinning for papers

Every dataset pyaegean can touch is versioned and hashable. `data.versions()`
returns a reproducibility manifest with three keys: `package`, `bundled`,
`fetched`:

```python
from aegean import data
v = data.versions()

v["package"]                                  # '0.20.0'  (your installed version)
v["bundled"]["lineara/inscriptions.json"]     # {'sha256': '4705b2b2…', 'bytes': 720766}
v["fetched"]["nt-corpus"]
# {'url': 'https://github.com/ryanpavlicek/pyaegean/releases/download/nt-corpus-v1/nt-corpus.json',
#  'sha256': 'e7aa5dcad729eb91f77018abbef71304d13e200f29dabe1260b79fa37b153949',
#  'license': "CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain",
#  'cached': True}
```

Each `bundled` entry is a JSON file hashed straight from the installed wheel; each
`fetched` entry carries the pinned URL, the pinned sha256, the license, and whether
it is present in your local cache. Bundled data ships inside the wheel, so its
version *is* the package version (also stamped on every bundled corpus as
`Provenance.data_version`); fetched assets are sha256-pinned release files,
verified on download.

**To pin an analysis for a paper**: record `aegean.__version__` and dump the
manifest alongside your results: matching sha256s mean byte-identical data.

```bash
aegean data versions --json > data-versions.json
```

```python
import json, aegean
from aegean import data
with open("data-versions.json", "w", encoding="utf-8") as f:
    json.dump({"package": aegean.__version__, "data": data.versions()}, f, indent=2)
```

The human-readable `aegean data versions` (no `--json`) prints the same content as
a table: `package`, every `bundled/...` file with its sha256 and byte size, then
every `fetched/...` asset with its sha256 and `cached` / `not cached` / `(unpinned)`
status.

---

## Provenance & citation

Every `Corpus` carries a `Provenance` that stamps exports and gives a citation:

```python
import aegean
corpus = aegean.load("lineara")

corpus.provenance.source
# 'GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz'
corpus.provenance.license
# 'Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed'
corpus.provenance.cite()
# 'Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A. — https://github.com/mwenge/lineara.xyz'
corpus.provenance.data_version
# '0.20.0'

corpus.to_dict()["_meta"]
# tool, schemaVersion, scriptId, documentCount, source, license, citation
```

A note on the Linear A corpus: the bundled transcription is **normalized**, and
the apparatus the upstream data *does* carry is interpreted on load: its
erased-sign marks become `ReadingStatus.LOST` (552 tokens) and damaged or
bracketed-uncertain readings become `UNCLEAR` (120 tokens, across 91 documents);
the two statuses together touch 366 documents.
The **full** Leiden apparatus (restorations, dotted readings) was dropped by the
upstream digitization and remains absent; for edition-grade readings consult
**GORILA** and **SigLA**. `aegean.ReadingStatus` round-trips through JSON and
EpiDoc (`<unclear>`/`<supplied>`/`<gap>`), so bring-your-own corpora keep their
apparatus through a load/export cycle.

---

## Your own corpus

### From a file you already have (`aegean import`)

If your text is in a **plain `.txt` file, a folder of text files, or a CSV**, import it
in one step (no Python required) and the result works with every corpus command:

```bash
aegean import myplato.txt -o myplato.json     # then: aegean stats myplato.json
aegean import poems/ -o corpus.db --split line          # a folder, one doc per line
aegean import rows.csv -o corpus.json --text-col line --id-col id
```

`--split` controls how a text file becomes documents: `whole` (default, one document,
line breaks preserved), `paragraph` (one per blank-line block), or `line` (one per line).
Greek/Koine text (`--script greek`, the default) is run through the Greek word tokenizer;
other scripts split on whitespace. The same paths exist in Python:

```python
from aegean import io
io.from_text_file("myplato.txt")                 # → Corpus
io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος", doc_id="john")
io.from_text_dir("poems/", split="line")
io.from_csv("rows.csv", text_col="line", id_col="id", meta_cols=["period"])
```

> `read_corpus` / the `CORPUS` argument deliberately load only pyaegean's own `.json`/`.db`
> formats. A `.txt`/`.csv` is *imported* into that format first (the error message says so);
> after `aegean import … -o corpus.json`, `corpus.json` is a first-class corpus everywhere.

### From structured records (`Corpus.from_records`)

For full control (explicit token kinds, editorial status, variant readings) build from
dict records:

```python
import aegean
corpus = aegean.Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="myfind",
   provenance=aegean.Provenance(source="My dig notebook", citation="Me (2026)."))
```

Tokens may be plain strings (kinds inferred: parseable numerals vs words,
hyphenated tokens get their signs split) or dicts carrying `kind`, `status`
(editorial certainty), and `alt` (variant readings). Make it loadable by name with
`aegean.core.corpus.register_loader("myfind", lambda: corpus)`; for EpiDoc
sources, `aegean.io.from_epidoc` (and `aegean import --epidoc`) reads any EpiDoc TEI
edition into the same model — id, find-place, token/line stream, `<unclear>`/`<supplied>`
status, and `<app>`/`<rdg>` variants — on the stdlib XML parser, no extra needed.

### Variant readings

`Token.alt` carries alternate readings alongside the editorial `status`. The
EpiDoc writer emits them as a critical apparatus:
`<app><lem><w>PO-ME</w></lem><rdg><w>PO-MA</w></rdg></app>` (validated against the
official EpiDoc schema), and `from_epidoc` folds them back to one token with its
`alt` tuple, so variants survive the EpiDoc *and* JSON round-trips.

---

## Licensing summary

- **Code**: Apache-2.0.
- **Linear A corpus JSON**: GORILA via mwenge/lineara.xyz (Apache-2.0).
- **Linear A facsimile imagery (`lineara-images`)**: © École Française d'Athènes
  and other rightsholders; referenced, not redistributed.
- **Aegean sign data (Linear B / Cypriot / Cypro-Minoan, bundled)**: Unicode
  Character Database, Unicode License v3 (retain the notice).
- **Greek sample corpus**: public-domain ancient texts (seed only).
- **Greek treebank lexicon + models (opt-in, `agdt-derived`)**: Perseus AGDT
  v2.1, CC BY-SA 3.0; fetched and built/used in the user cache, never bundled or
  redistributed.
- **Greek lexicon / LSJ (opt-in, `lsj-index`)**: Perseus Liddell-Scott-Jones,
  CC BY-SA 4.0; fetched and indexed in the user cache, never bundled or
  redistributed.
- **Greek neural lemmatizer (opt-in `[neural]`, `grc-lemma-neural`)**: a GreTa
  seq2seq (Apache-2.0 base) fine-tuned on the AGDT (CC BY-SA 3.0), Pedalion
  (CC BY-SA 4.0), and Gorman (CC BY-SA 4.0) treebanks. The model: int8 ONNX
  weights plus a derived gold lemma lookup: is **CC BY-SA 4.0**, fetched to the
  user cache (~232 MB), never bundled; the wheel stays Apache-2.0.
- **Greek neural joint pipeline (opt-in `[neural]`, `grc-joint`)**: a
  GreBerta-based joint model (Apache-2.0 base) fine-tuned on the AGDT (CC BY-SA
  3.0), Gorman (CC BY-SA 4.0), and Pedalion (CC BY-SA 4.0) treebanks, evaluation
  folds excluded from training. The model bundle is **CC BY-SA 4.0**, fetched to
  the user cache (~173 MB), never bundled; the wheel stays Apache-2.0.
- **PROIEL / UD evaluation sets (opt-in)**: the PROIEL treebank and the UD Ancient
  Greek treebanks (UD-Perseus CC BY-NC-SA 2.5; PROIEL and UD-PROIEL CC BY-NC-SA 3.0);
  fetched to the user cache for evaluation only, never bundled, never trained on
  (NonCommercial + ShareAlike).
- **SigLA corpus (`sigla-corpus`)**: Salgarella & Castellan, CC BY-NC-SA 4.0;
  fetched, never bundled; NC + ShareAlike pass through to you.
- **DAMOS corpus (`damos-corpus`)**: F. Aurora, CC BY-NC-SA 4.0; fetched, never
  bundled; NC + ShareAlike pass through to you.
- **Greek New Testament (`nt-corpus`) + Dodson lexicon (bundled)**: Nestle 1904
  base text public domain; morphology/lemmas/Strong's and the Dodson glosses are
  **CC0**, so two NT sample chapters and the Dodson lexicon are bundled and the full NT
  corpus may be redistributed.
- **Linear A Workbench app (`workbench-app`)**: Apache-2.0 build; embedded data
  is GORILA-derived.
- **Linear B bring-your-own (`linearb-corpus`)**: no default source; DAMOS is
  CC BY-NC-SA 4.0 and LiBER is all-rights-reserved (© CNR Edizioni); neither
  redistributed.

See the repository `NOTICE` and `CITATION.cff` for full attribution.

---

## Limitations & honest notes

- **The full Linear A apparatus is not bundled.** Restorations and dotted
  readings were dropped upstream; only `LOST`/`UNCLEAR` survive. For edition-grade
  readings, go to GORILA and SigLA.
- **NonCommercial data is NonCommercial for you too.** DAMOS, SigLA, PROIEL, and
  the UD treebanks carry CC BY-NC-SA obligations that pass through: you may not
  use them commercially, and you must ShareAlike.
- **Override URLs skip checksum verification.** Setting `PYAEGEAN_<NAME>_URL`
  means *you* vouch for the bytes; the pinned sha256 only describes the pinned
  release asset.
- **Imagery is fetched, never re-hosted.** `lineara-images` copyright is a
  patchwork; check each file's `imageRights` before reuse.
- **First neural/treebank/LSJ/work call needs the network**; everything is cached
  afterward and runs offline.

See [Limitations](Limitations) for the project-wide caveats, and
[Greek NLP](Greek-NLP), [Linear A](Linear-A), [Linear B](Linear-B),
[Analysis](Analysis), and [Cypriot](Cypriot) for the features that consume this
data.
