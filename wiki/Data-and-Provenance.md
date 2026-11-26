# Data & Provenance

This page documents dataset origins, wheel contents versus on-demand downloads,
asset sizes and licenses, local store behavior, and snapshot pinning for
reproducible research. For a categorized work-by-work listing of every corpus
and text, see [Corpus Catalog](Catalog).

Code and compact JSON ship in the wheel and work offline. Larger or
license-restricted assets download on demand into a permanent local store
(`PYAEGEAN_CACHE`) with SHA-256 verification.

> **Managing downloads:** Manage packs, corpora, works, and models with
> `aegean library` (`aegean library status`, `aegean library install biblical`,
> `aegean library search Plato`, `aegean library remove damos`),
> `aegean.library` in Python, or press `l` in `aegean tui`. Missing Biblical
> texts and uninstalled corpora also provide one-click downloads in the TUI
> screens (`b` and `c`).

---

## Bundled vs fetched

Compact JSON data ships inside the wheel and runs offline with zero third-party
dependencies:

- **Linear A**: `inscriptions.json`, `signs.json`, `phonetic_map.json`, `manifest.json`
- **Linear B**: `signs.json`, `phonetic_map.json`, `lexicon.json`, `sample_inscriptions.json` (Unicode UCD)
- **Cypriot**: `signs.json`, `phonetic_map.json`, `lexicon.json`, `sample_inscriptions.json`, `ig_inscriptions.json` (178-inscription IG XV 1 corpus, CC BY 4.0)
- **Cypro-Minoan**: `signs.json`, `sample_inscriptions.json` (undeciphered; no phonetic map or lexicon)
- **Greek**: `sample_texts.json`, `lemmata.json`, `idioms.json` (idiom/MWE gloss lexicon), `benchmark_gold.json`, `nt_sample.json` (John 1 + Philemon 1 sample), `dodson.json` (Koine lexicon), `works_catalogue.json` (offline `greek.catalog` metadata index), `calibration.json` (legacy Schema-1 scalar temperature), `calibration_registry_v2.json` (Schema-2 logit-affine calibration registry), `oov_lemma_reranker_v1.json` (opt-in OOV lemma reranker weights), `neural-runtime-variants.json` (runtime-variant registry)
- **Geo**: `site_coordinates.json` (approximate find-site coordinates)

Large and license-restricted assets stay outside the wheel and download on demand
to the user cache. CI enforces a code-and-JSON-only wheel and fast core import
via `scripts/check_footprint.py`.

```python
from aegean.data import load_bundled_json
signs = load_bundled_json("lineara", "signs.json")
len(signs)
# 342
```

### Every bundled JSON file (verified)

`aegean.data.versions()` hashes these files directly from the installed wheel
under its `bundled` key (sizes in bytes):

| File | Bytes | Source |
|---|---|---|
| `cypriot/ig_inscriptions.json` | 71,928 | *Inscriptiones Graecae* XV 1 (BBAW, CC BY 4.0) |
| `cypriot/lexicon.json` | 1,307 | Unicode UCD + scholarly excerpts |
| `cypriot/phonetic_map.json` | 655 | Unicode UCD |
| `cypriot/sample_inscriptions.json` | 461 | scholarly excerpts (Masson; Chadwick) |
| `cypriot/signs.json` | 6,975 | Unicode UCD (Cypriot Syllabary) |
| `cyprominoan/sample_inscriptions.json` | 385 | scholarly excerpts (Ferrara) |
| `cyprominoan/signs.json` | 12,580 | Unicode UCD (Cypro-Minoan block) |
| `geo/site_coordinates.json` | 10,748 | GORILA / Younger / public gazetteers |
| `greek/benchmark_gold.json` | 6,451 | gold benchmark fixtures |
| `greek/calibration.json` | 694 | legacy Schema-1 dev-fitted scalar temperature (`grc-joint-v3`) |
| `greek/calibration_registry_v2.json` | 9,846 | locked-test-qualified Schema-2 calibration registry (`grc-joint-v3`) |
| `greek/dodson.json` | 712,301 | Dodson Greek Lexicon (CC0) |
| `greek/idioms.json` | 6,445 | bundled idiom / MWE gloss lexicon |
| `greek/lemmata.json` | 1,494 | bundled gold lemma seed |
| `greek/neural-runtime-variants.json` | 1,330 | stable neural runtime-variant registry |
| `greek/nt_sample.json` | 132,814 | Nestle 1904: John 1 + Philemon 1 sample (CC0) |
| `greek/oov_lemma_reranker_v1.json` | 824 | frozen dev-fitted weights for opt-in OOV lemma reranker (`grc-joint-v3`) |
| `greek/sample_texts.json` | 1,017 | public-domain Greek snippets |
| `greek/works_catalogue.json` | 281,097 | Perseus + First1KGreek work index (metadata only; built by `scripts/build_greek_catalogue.py`) |
| `lineara/inscriptions.json` | 720,766 | GORILA via mwenge/lineara.xyz |
| `lineara/manifest.json` | 434 | corpus manifest |
| `lineara/phonetic_map.json` | 621 | Linear A sound values |
| `lineara/signs.json` | 63,272 | Linear A sign inventory |
| `linearb/lexicon.json` | 11,473 | Unicode UCD + Wiktionary/kaikki excerpts |
| `linearb/phonetic_map.json` | 910 | Unicode UCD |
| `linearb/sample_inscriptions.json` | 6,870 | scholarly excerpts (Ventris & Chadwick) |
| `linearb/signs.json` | 35,817 | Unicode UCD (Linear B Syllabary + Ideograms) |

---

## Download-to-cache: `fetch()`

`fetch(name)` downloads a registered remote asset into the local store and
returns its path. Downloads are SHA-256-verified (when a checksum is pinned),
atomic (written to `.part` then renamed), idempotent (a valid cached entry is a
no-op), and resumable (interrupted downloads keep `.part` and resume via HTTP
`Range`; republished upstream assets restart cleanly). Archive datasets
(`extract=True`, such as `lineara-images`) unpack safely into a cache directory
with path-traversal rejection, and `fetch()` returns that directory.

> **Permanent local store:** Fetched datasets remain on disk with no automatic
> eviction or expiry. A cached copy that fails integrity verification is
> re-fetched; otherwise it stays until removed via `aegean data remove NAME` (or
> `aegean data remove --all`) or replaced with `fetch(name, force=True)`.

```python
from aegean import data

data.cache_dir()                 # local store directory (override: PYAEGEAN_CACHE)
path = data.fetch("nt-corpus")   # returns cached path; no-op once valid
path.exists(), path.is_file()
# (True, True)
```

Errors are raised lazily on fetch and never block `import aegean`:

| Condition | Exception | Message detail |
|---|---|---|
| unknown dataset | `DataNotAvailableError` | `unknown dataset 'nope'; known: [...]` |
| no pinned URL | `DataNotAvailableError` | names the `PYAEGEAN_<NAME>_URL` variable to set |
| checksum mismatch | `DataNotAvailableError` | expected vs actual digest; corrupted download removed |
| unsafe archive member | `DataNotAvailableError` | `unsafe path in archive: ...` |
| network failure | `DataNotAvailableError` | `could not fetch '<name>' from <url>: ...` |

```python
from aegean import data
try:
    data.fetch("linearb-corpus")             # bring-your-own slot; no default URL
except data.DataNotAvailableError as e:
    print(str(e)[:70])
# dataset 'linearb-corpus' has no pinned download URL yet (Your own licen...
```

Pass `fetch(name, force=True)` to re-download over an existing valid cache entry.

---

## The fetchable datasets

Registered remote datasets (`aegean data list`, 39 entries). All are fetched to
the user store on demand and never bundled in the Apache-2.0 wheel. Each pinned
URL and SHA-256 lives in `aegean.data._REMOTE`; set `PYAEGEAN_<NAME>_URL` to
point any dataset at a custom mirror or local licensed copy.

| Dataset (`name`) | Contents | Size | License | Provenance |
|---|---|---|---|---|
| `lineara-images` | 3,368 facsimile/photo files (archive) | ~116 MB tar.gz, ~119 MB unpacked | © École Française d'Athènes + other rightsholders: academic reference only | Fetched from `ryanpavlicek/linearaworkbench`; never re-hosted |
| `agdt-derived` | Prebuilt AGDT lexicon + tagger/lemmatizer/parser models | ~15 MB | CC BY-SA 3.0 (derived from Perseus AGDT) | Project-hosted derivative of AGDT |
| `lsj-index` | Prebuilt LSJ lemma→entry index | ~15 MB | CC BY-SA 4.0 (Perseus Digital Library) | Project-hosted derivative of Perseus LSJ |
| `middle-liddell-index` | Prebuilt Middle Liddell lemma→entry index | ~2.3 MB | public domain (1889); Perseus / Scaife digitization | Project-hosted; `use_lexicon("middle-liddell")` |
| `cunliffe-index` | Prebuilt Cunliffe (Homeric) lemma→entry index | ~1.3 MB | public domain (1924); Scaife data MIT | Project-hosted; `use_lexicon("cunliffe")` |
| `abbott-smith-index` | Prebuilt Abbott-Smith (NT) lemma→entry index | ~130 KB | public domain (1922) | Project-hosted; `use_lexicon("abbott-smith")` |
| `autenrieth-index` | Prebuilt Autenrieth (Homeric) lemma→entry index | ~0.6 MB | public domain (1891); Perseus digitization CC BY-SA | Project-hosted; `use_lexicon("autenrieth")` |
| `papygreek-fold` | Work-disjoint documentary-Koine dependency eval fold (1,551 sentences / 22,227 tokens) | ~306 KB | CC BY-SA 4.0 (PapyGreek Treebanks) | Project-hosted derivative; evaluation only; Trismegistos work exclusion + sentence-form guards; rebuild: `scripts/build_papygreek_fold.py` |
| `papygreek-fold-orig` | ORIG diplomatic surface layer of `papygreek-fold` (same 1,551 sentences and gold; raw scribal spellings, 1,453 forms differ) | ~309 KB | CC BY-SA 4.0 (PapyGreek Treebanks) | Project-hosted derivative; evaluation only; rebuild: `scripts/build_papygreek_fold.py --layer orig` |
| `verse-fold` | Ancient Greek verse dependency eval fold, tragedy-only (36 sentences / 735 tokens: Euripides *Bacchae* 1–169); small-sample, never a headline figure | ~12 KB | CC BY-SA 4.0 (unesp-trees, Perseids/Arethusa, UNESP) | Project-hosted derivative; evaluation only; rebuild: `scripts/build_verse_fold.py` |
| `dbbe-lingann-fold` | Byzantine book-epigram tagging fold (825 sentences / 9,191 tokens, gold POS + lemma, no trees; scribal orthography) | ~120 KB | CC BY 4.0 (DBBE gold standard, Ghent) | Project-hosted derivative; evaluation only; rebuild: `scripts/build_dbbe_fold.py` |
| `papygreek-dev-tagging` | Work-disjoint documentary-Koine DEV tagging track (323 sentences / 6,319 tokens), document-disjoint from `papygreek-fold` | ~92 KB | CC BY-SA 4.0 (PapyGreek Treebanks) | Development only; never a published headline figure; rebuild: `scripts/build_papygreek_dev.py` |
| `papygreek-dev-parse` | Work-disjoint documentary-Koine DEV parse track (125 sentences / 1,262 tokens, directional only) | ~17 KB | CC BY-SA 4.0 (PapyGreek Treebanks) | Development only; never a published headline figure; rebuild: `scripts/build_papygreek_dev.py` |
| `grc-paradigms` | Nominal paradigm table (form→lemma+features) for `use_paradigms()` | ~233 KB | CC BY-SA 3.0 (derived from UniMorph grc) | Project-hosted derivative; rebuild: `scripts/build_paradigm_table.py` |
| `ddbdp-uris` | DDbDP document-identifier map (file stem→ddb-hybrid) for papyri.info URIs in RDF export | ~337 KB | CC BY 3.0 (derived from papyri.info idp.data) | Project-hosted derivative; rebuild: `scripts/build_ddbdp_uri_map.py` |
| `grc-lemma-neural` | GreTa seq2seq lemmatizer (int8 ONNX + tokenizer + gold lookup) | ~232 MB tar.gz | CC BY-SA 4.0: derived from AGDT (3.0) + Pedalion (4.0) + Gorman (4.0) | `[neural]` extra; fine-tuned from `bowphs/GreTa` (Apache-2.0 base) |
| `grc-joint` | Joint tagger-parser-lemmatizer (quantized ONNX + tokenizer + label maps + lemma scripts/lookup) | ~173 MB tar.gz | CC BY-SA 4.0: derived from AGDT (3.0) + Gorman (4.0) + Pedalion (4.0) | `[neural]` extra; GreBerta-based (Apache-2.0 base), eval folds excluded |
| `sigla-corpus` | SigLA Linear A dataset v4: 802 docs, 1,895 word-division groups (plus standalone single signs as `WORD` tokens) + commodity ideograms | ~1.3 MB JSON | CC BY-NC-SA 4.0 (SigLA: Salgarella & Castellan) | Decoded from SigLA web-app payload; drawings remain at sigla.phis.me |
| `damos-corpus` | DAMOS Linear B corpus v2: ~5,900 tablets, transliterations + metadata | ~3 MB JSON | CC BY-NC-SA 4.0 (DAMOS: F. Aurora) | Decoded from DAMOS public API; no imagery |
| `nt-corpus` | Greek NT (Nestle 1904): 260 chapters / ~137,800 tokens, gold lemma + Robinson morph + Strong's + UD UPOS | ~16 MB JSON | CC0-1.0 (morphology/lemmas/Strong's); base text public domain | From `biblicalhumanities/Nestle1904`; redistributable (CC0) |
| `strongs-greek` | Extended Strong's Greek Lexicon: 11,142 Strong's & STEPBible extended entries with definitions, derivations, Hebrew equivalents, KJV usage, and root links | ~1.5 MB JSON.gz | CC BY 4.0 (STEPBible TBESG) + Public Domain (OpenScriptures Strong's) | Project-hosted derivative; rebuild: `scripts/build_strongs_greek.py` |
| `nt-editions` | Eight Greek New Testament critical & traditional editions (`sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`; 27 books each) for word-level variant collation | ~3.3 MB JSON.gz | CC BY-SA 3.0 / CC BY 4.0 / Public Domain (SBLGNT/MorphGNT; CNTR SR, BHP & KJTR; Tischendorf 8th, Westcott–Hort, Robinson–Pierpont BYZ, Antoniades 1904) | Project-hosted derivative; rebuild: `scripts/build_nt_editions.py` |
| `nt-witnesses` | Thirteen 2nd–5th c. CE Greek NT manuscript transcriptions (`01`/ℵ, `02`/A, `03`/B, `04`/C, `05`/D, `032`/W, `P45`–`P75`) with original and corrector hands | ~1.5 MB JSON.gz | CC BY-SA 4.0 (Center for New Testament Restoration Class 1 transcriptions) | Project-hosted derivative; rebuild: `scripts/build_nt_witnesses.py` |
| `lxx-corpus` | Septuagint (LXX) v2: all 56 Greek Old Testament & Deuterocanonical books (`tlg0527.*`, incl. Ecclesiastes; 29,470 verses, 592,436 tokens) | ~1.7 MB JSON.gz | CC BY-SA 4.0 (OpenGreekAndLatin / First1KGreek Swete 1887–1894 + Greek Wikisource Ecclesiastes) | Project-hosted derivative (`lxx-corpus-v2`; `v1` kept in `_REMOTE_HISTORY`); rebuild: `scripts/build_lxx_corpus.py` |
| `chrysostom-corpus` | John Chrysostom Complete Open Greek Corpus: 155 works across 3 authors (3,738,372 tokens: homilies, sermons, biblical commentaries, treatises, letters) | ~12.3 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, Calfa PG, First1KGreek, PTA) | Project-hosted collection; `aegean.load("chrysostom")` or `aegean.open("ogc002060")`; rebuild: `scripts/build_greek_collections.py` |
| `church-fathers-early-corpus` | Early & Nicene Church Fathers (2nd–4th c. CE): 432 works across 58 authors (6,216,570 tokens: Athanasius, Basil, Gregory of Nazianzus, Gregory of Nyssa, Origen, Eusebius, Clement, Irenaeus, Justin) | ~21.0 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, First1KGreek, PTA, Calfa PG) | Project-hosted collection; `aegean.load("church-fathers-early")`; rebuild: `scripts/build_greek_collections.py` |
| `church-fathers-late-corpus` | Post-Nicene, Eastern & Byzantine Church Fathers & Saints (5th–15th c. CE): 280 works across 38 authors (7,962,722 tokens: Cyril of Alexandria, Theodoret, Maximus, John of Damascus, Photius, Symeon, Palamas) | ~26.7 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, Calfa PG, First1KGreek, PTA) | Project-hosted collection; `aegean.load("church-fathers-late")`; rebuild: `scripts/build_greek_collections.py` |
| `classical-greek-corpus` | Archaic & Classical Greek (8th–4th c. BCE): 684 works across 246 authors (5,088,194 tokens: Homer, Hesiod, tragedians, Aristophanes, Herodotus, Thucydides, Xenophon, Plato, Aristotle, orators, Hippocrates) | ~17.3 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, Perseus, First1KGreek, GLAUx) | Project-hosted collection; `aegean.load("classical-greek")`; rebuild: `scripts/build_greek_collections.py` |
| `hellenistic-greek-corpus` | Hellenistic Greek & DFHG Fragmentary Historians (3rd–1st c. BCE): 740 works across 587 authors (4,672,040 tokens: Polybius, Callimachus, Apollonius, Theocritus, Euclid, Archimedes, Diodorus, Philo, Strabo) | ~16.3 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, Perseus, First1KGreek, DFHG) | Project-hosted collection; `aegean.load("hellenistic-greek")`; rebuild: `scripts/build_greek_collections.py` |
| `imperial-greek-corpus` | Imperial Greek Literature, Philosophy, Medicine & Rhetoric (1st–3rd c. CE): 1,078 works across 373 authors (14,662,168 tokens: Plutarch, Galen, Lucian, Josephus, Epictetus, Marcus Aurelius, Cassius Dio, Pausanias) | ~50.2 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, Perseus, First1KGreek, Galenus Verbatim) | Project-hosted collection; `aegean.load("imperial-greek")`; rebuild: `scripts/build_greek_collections.py` |
| `late-antique-greek-corpus` | Late Antique Philosophy, Rhetoric, Poetry & Scholia (4th–6th c. CE): 290 works across 82 authors (11,333,916 tokens: Plotinus, Porphyry, Proclus, Libanius, Julian, Nonnus, Simplicius, Philoponus) | ~38.9 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, First1KGreek, Calfa, Perseus) | Project-hosted collection; `aegean.load("late-antique-greek")`; rebuild: `scripts/build_greek_collections.py` |
| `byzantine-lit-corpus` | Byzantine Greek History, Literature & Lexicography (6th–15th c. CE, through 1453): 185 works across 94 authors (10,676,388 tokens: Procopius, Anna Comnena, Psellus, Eustathius, Suda, Photius, Choniates, Sphrantzes) | ~38.3 MB JSON.gz | Public Domain / CC BY 4.0 / CC BY-SA 4.0 (Open Greek Corpus, Calfa, First1KGreek, Wikisource) | Project-hosted collection; `aegean.load("byzantine-lit")`; rebuild: `scripts/build_greek_collections.py` |
| `patrologia-graeca-corpus` | Calfa–GREgORI Patrologia Graeca: 33 digitized Migne PG volumes (6.79M Greek words, OCR of 19th-century prints), including 9 biblical commentary volumes (Cyril of Alexandria, Procopius of Gaza, Photius, Oecumenius, Theophylact of Bulgaria) | ~23.5 MB JSON.gz | CC BY 4.0 (CGPG — UCLouvain GREgORI & Calfa, Vidal-Gorène & Kindt, LREC 2026) | Project-hosted derivative; `aegean.load("patrologia")` or `aegean.greek.bible.load_commentary()`; rebuild: `scripts/build_patrologia_graeca_corpus.py` |
| `apostolic-fathers-corpus` | Open Apostolic Fathers: 15 twice-hand-corrected Greek works (64,944 tokens: 1–2 Clement, Ignatius's 7 epistles, Polycarp, Didache, Barnabas, Hermas, Martyrdom of Polycarp, Diognetus) | ~1.0 MB JSON.gz | CC BY-SA 4.0 (Open Apostolic Fathers — James Tauber & Seumas Macdonald, Zenodo 10.5281/zenodo.2555673) | Project-hosted derivative; `aegean.load("apostolic-fathers")`; rebuild: `scripts/build_apostolic_fathers_corpus.py` |
| `pseudepigrapha-corpus` | Online Critical Pseudepigrapha (Greek): 44 Second Temple & Old Testament Pseudepigrapha works (171,306 tokens: 1 Enoch, Psalms of Solomon, Testaments of the 12 Patriarchs, Testament of Job/Solomon/Abraham, Aristeas, Joseph & Aseneth, Sibylline Oracles, etc.) | ~2.7 MB JSON.gz | CC BY 4.0 (Online Critical Pseudepigrapha — Ken M. Penner et al., pseudepigrapha.org) | Project-hosted derivative; `aegean.load("pseudepigrapha")`; rebuild: `scripts/build_pseudepigrapha_corpus.py` |
| `isicily-corpus` | I.Sicily Greek inscriptions: 2,855 primary-Greek texts from ancient Sicily with find-place, date, coordinates | ~7 MB JSON | CC BY 4.0 (I.Sicily: J. Prag et al., Oxford) | From `ISicily/ISicily` EpiDoc corpus; redistributable (CC BY) with attribution |
| `iip-corpus` | IIP Greek inscriptions: 2,113 primary-Greek texts from Israel/Palestine with find-place, coordinates | ~4 MB JSON | CC BY-NC 4.0 (IIP: M. L. Satlow, Brown) | From `Brown-University-Library/iip-texts`; attribution + NonCommercial |
| `iospe-corpus` | IOSPE Greek inscriptions: 1,194 Greek texts of the Northern Black Sea (Tyras, Olbia, Chersonesos, Byzantine) with find-place, date | ~4 MB JSON | CC BY (IOSPE, King's College London; repo code MIT) | From `kingsdigitallab/iospe`; attribution required |
| `igcyr-corpus` | IGCyr/GVCyr Greek inscriptions of Cyrenaica: 997 texts (archaic Doric + verse) with title, find-place, date | ~3 MB JSON | CC BY-NC-SA 4.0 (IGCyr2/GVCyr2, Dobias-Lalou et al., Bologna) | From AMS Acta 7796; attribution + NonCommercial + ShareAlike; epichoric (non-normalized) Greek |
| `aphrodisias-corpus` | Inscriptions of Aphrodisias (IAph2007): 1,471 Greek EpiDoc inscriptions (38,556 tokens) from Aphrodisias in Caria (2nd c. BCE–Byzantine) | ~0.5 MB JSON.gz | CC BY 2.5 (Reynolds, Roueché & Bodard, King's College London, http://insaph.kcl.ac.uk/) | Project-hosted EpiDoc extraction; `aegean.load("aphrodisias")`; rebuild: `scripts/build_aphrodisias_corpus.py` |
| `crete-corpus` | Cretan Institutional Inscriptions: 600 Archaic–Hellenistic Greek EpiDoc inscriptions from Crete (50,995 tokens, 7th–1st c. BCE) | ~0.6 MB JSON.gz | CC BY-NC-SA 4.0 (Irene Vagionakis, Università Ca' Foscari Venezia, 2016–2019) | Project-hosted EpiDoc extraction; `aegean.load("crete")`; NonCommercial + ShareAlike pass to user; rebuild: `scripts/build_crete_corpus.py` |
| `edh-corpus` | EDH Greek inscriptions: 1,286 pure-Greek texts (Imperial Koine, largely onomastic) with ancient place, date, find-place, Trismegistos id | ~6 MB JSON | CC BY-SA 4.0 (EDH, Heidelberg Academy of Sciences and Humanities) | Pure-`grc` subset of frozen 2021 EDH dump; attribution + ShareAlike |
| `ddbdp-corpus` | DDbDP documentary papyri: 57,331 Greek texts / ~4.4M tokens as a SQLite database with FTS (citation, date, place, TM/HGV ids) | ~219 MB tar.gz, ~757 MB unpacked | CC BY 3.0 (DDbDP / papyri.info) | From `papyri/idp.data`; attribution required. Use `aegean db search ddbdp` or `aegean.db.stream(ddbdp_db())` instead of materializing all 4.4M tokens via `aegean.load("ddbdp")` |
| `byzantine-corpus` | Byzantine & Early Modern Vernacular Greek: 12 literary texts (189,375 tokens, 12th–17th c.: *Digenes Akritas*, *Chronicle of Moreas*, *Ptochoprodromika*, *Poulologos*, *Apokopos*, *Erotokritos*) | ~2.5 MB JSON.gz | Public Domain / CC BY-SA 3.0 (Wikisource & Kalonaros 1940; `open-greek/byzantine-early-modern-corpus`) | Project-hosted derivative; `aegean.load("byzantine")`; rebuild: `scripts/build_byzantine_corpus.py` |
| `homer-scholia-corpus` | Homer Multitext Project (`hmt-2026a`): normalized Venetus A *Iliad* (24 books) and Homeric *scholia* (Venetus A, Venetus B, Escorial Upsilon 1.1; 54 documents, 331,365 tokens) | ~5.5 MB JSON.gz | CC BY-NC 4.0 (Homer Multitext Project, Center for Hellenic Studies) | Project-hosted CEX extraction; `aegean.load("homer-scholia")`; NonCommercial passes to user; rebuild: `scripts/build_homer_scholia_corpus.py` |
| `workbench-app` | Prebuilt Linear A Research Workbench `v2.1.0` static web app (archive, multi-script Aegean fonts) | ~3.3 MB tar.gz | Apache-2.0 (build); embedded Linear A data is GORILA-derived | Pinned to `workbench-app-v2.1.0`; served locally by `aegean workbench` |
| `linearb-corpus` | Slot for a user-supplied licensed Linear B export (no default source) | — | bring-your-own; fetch DAMOS for an open corpus (LiBER is browse-only) | Fetch DAMOS via `aegean data fetch damos`. LiBER (liber.cnr.it) offers no public download or API. Import local EpiDoc via `aegean import x.xml --epidoc --script linearb`, or set `PYAEGEAN_LINEARB_CORPUS_URL` |

> **License propagation:** Project-hosted derivatives keep their upstream
> ShareAlike license and stay outside the Apache-2.0 wheel. NonCommercial terms
> (DAMOS, SigLA, PROIEL, IIP, IGCyr/GVCyr, Crete, Homer Multitext) apply to end
> users. CC0 assets (Nestle 1904 NT annotations and Dodson) carry no attribution
> or ShareAlike requirement, permitting two NT sample chapters and Dodson to
> ship inside the wheel.

### Per-dataset notes

#### The Linear A imagery (`lineara-images`)

The facsimile/photo archive (3,368 files, ~116 MB compressed, ~119 MB unpacked)
is fetched from a release on `ryanpavlicek/linearaworkbench` and never re-hosted
by pyaegean. `fetch()` downloads and extracts the archive into a local image
directory. Rights vary per file: most images are © École Française d'Athènes
([GORILA volumes](https://cefael.efa.gr/result.php?serie_title_operator=con&volume_number_operator=%3D&issue_year_operator=%3D&section_title=Recueil+des+inscriptions+en+lin%C3%A9aire+A&section_title_operator=con&author_lastname_operator=con&publisher_name_operator=con&site_id=1&actionID=advanced&operator=AND)
in CEFAEL), and others are held by named scholars, publications, and
photographers (recorded in each document's `imageRights`).

The release URL and SHA-256 are pinned:

```python
from aegean import data
data.fetch("lineara-images")     # downloads, verifies SHA-256, unpacks, returns directory
```

Override with a local mirror via environment variable (checksum verification is
skipped for override URLs):

```bash
export PYAEGEAN_LINEARA_IMAGES_URL="https://example.org/lineara-images.tar.gz"
```

#### The Greek treebank lexicon & models (`agdt-derived`, `use_treebank`)

`aegean.greek.use_treebank()` activates the lexicon derived from Perseus Ancient
Greek Dependency Treebank (AGDT v2.1); `use_parser()`, `use_tagger()`, and
`use_lemmatizer()` load the statistical models built from the same source. On
first call, they fetch the prebuilt `agdt-derived` bundle (~15 MB,
`agdt-greek-lexicon.json` plus the three models, SHA-256-pinned). If the hosted
bundle is unreachable, pyaegean falls back to downloading the 33 AGDT `.tb.xml`
files (~75 MB, commit-pinned) and building locally. AGDT is CC BY-SA 3.0; derived
artifacts carry the same ShareAlike license, stay out of the Apache-2.0 wheel,
and require attribution to Perseus AGDT. Network access is needed only on first
use. See [Greek NLP → Treebank-backed mode](Greek-NLP#treebank-backed-mode-opt-in).

#### The Greek lexicon (LSJ, `lsj-index`, `use_lsj`)

`aegean.greek.use_lsj()` activates a lemma-to-entry index derived from Perseus
Liddell-Scott-Jones. On first use it fetches the prebuilt
`lsj-perseus-index.json.gz` (~15 MB, SHA-256-pinned) from `lsj-index`; if
unreachable, it falls back to downloading the 27 TEI files (~270 MB,
commit-pinned) and building the index locally. LSJ is CC BY-SA 4.0 (Perseus
Digital Library, NEH-funded); the derived index carries the same ShareAlike
terms and stays outside the wheel. Attribute Perseus per `NOTICE`. See
[Greek NLP → Lexicon (LSJ)](Greek-NLP#lexicon-lsj-glossing-opt-in).

#### More dictionaries (the lexicon registry)

Beyond LSJ and bundled Dodson, `greek.use_lexicon(id)` activates four hosted
dictionaries (`middle-liddell-index`, `cunliffe-index`, `autenrieth-index`,
`abbott-smith-index`), each fetching a prebuilt lemma index on first use. Middle
Liddell, Cunliffe, and Abbott-Smith fall back to building from commit-pinned
upstream sources if the prebuilt index is unreachable; Autenrieth uses its
prebuilt index. None is bundled in the wheel:

- **Middle Liddell** (*An Intermediate Greek-English Lexicon*, 1889) and
  **Cunliffe** (*A Lexicon of the Homeric Dialect*, 1924): built from
  `scaife-viewer/atlas-data-prep` (commit-pinned, MIT). Underlying texts are
  public domain, digitized by Perseus and Scaife Viewer; attribute both.
- **Abbott-Smith** (*A Manual Greek Lexicon of the New Testament*, 1922): built
  from TEI in `translatable-exegetical-tools/Abbott-Smith` (commit-pinned,
  public domain).
- **Autenrieth** (*A Homeric Dictionary*, 1891): public-domain text with Perseus
  CC BY-SA digitization.

Non-redistributable dictionaries (Slater, Montanari, DGE, Bailly) are never
hosted; `greek.lexicon_link(word)` generates Logeion deep-links instead. See
[Greek NLP → the lexicon registry](Greek-NLP#more-dictionaries-the-lexicon-registry).

The registry also records **Suda On Line** (`id="suda"`) as a deep-link-only
entry addressed by Adler number (for example,
`http://www.stoa.org/sol-entries/alpha/1`). Adler's 1928–1938 Greek text is
public domain; Suda On Line translations and commentary are CC BY-NC-SA.

#### The Greek neural lemmatizer model (`grc-lemma-neural`, `use_neural_lemmatizer`, `[neural]`)

`aegean.greek.use_neural_lemmatizer()` activates a seq2seq lemmatizer reaching
76.3% on unseen forms. It pairs a model-bundle gold lemma lookup for attested
forms with an int8 ONNX encoder/decoder (~232 MB tar.gz, fetched to cache)
running torch-free on numpy and onnxruntime.

Base model: `bowphs/GreTa` (Ancient Greek T5, Apache-2.0), fine-tuned on AGDT
(CC BY-SA 3.0), Pedalion (CC BY-SA 4.0), and Gorman (CC BY-SA 4.0). The exported
model carries CC BY-SA 4.0 and stays outside the Apache-2.0 wheel. See
[Greek NLP → Neural lemmatizer](Greek-NLP#neural-lemmatizer-opt-in).

#### The Greek neural joint pipeline model (`grc-joint`, `use_neural_pipeline`, `[neural]`)

`aegean.greek.use_neural_pipeline()` loads one joint model predicting UPOS, full
morphology (UD FEATS), UD dependency trees, and lemmas in a single forward pass
(see [Greek NLP → The neural pipeline](Greek-NLP#the-neural-pipeline-opt-in) and
[Benchmarks](Benchmarks)). The ~173 MB SHA-256-pinned tar.gz contains the
quantized ONNX graph, tokenizer, label maps, and lemma scripts/lookup, running
torch-free on numpy and `onnxruntime>=1.23`. Weights use int8 weight-only MatMul
and fp16 elsewhere with fp32 activations, scoring within ±0.02 of fp32 on UD
Ancient Greek. The fp32 build remains hosted under `grc-joint-v2` for
reproducibility.

The bundled `neural-runtime-variants.json` registry maps the stable `default`
label to the pinned release asset and manifest without bundling weights. `fast`,
`compact`, and `balanced` are reserved labels with no artifact identity until a
qualified successor earns the corresponding operational award. Any future
non-default label must bind:

- a distinct cache key when bytes differ;
- the release-asset SHA-256;
- the bundle-manifest SHA-256;
- artifact qualification;
- a runtime-variant award.

The public registry and award summaries exclude private development scores and
raw timing traces.

Base encoder: `bowphs/GreBerta` (Riemenschneider & Frank, Apache-2.0), fine-tuned
with tagging heads, a biaffine dependency parser, and an edit-script lemma head
on AGDT (CC BY-SA 3.0), Gorman (CC BY-SA 4.0), and Pedalion (CC BY-SA 4.0).
Every UD-Perseus dev/test sentence and all PROIEL evaluation texts are excluded
from training (`agdt_ud_overlap()`; protocol in [Benchmarks](Benchmarks)). The
released bundle is CC BY-SA 4.0 and stays outside the wheel.

#### The PROIEL evaluation set (`evaluate_on_proiel`)

`aegean.greek.evaluate_on_proiel()` scores lemmatization and tagging against the
PROIEL treebank (Greek New Testament and Herodotus), which none of pyaegean's
models train on. PROIEL is CC BY-NC-SA 3.0; it is fetched to cache strictly for
local evaluation and never bundled or re-hosted. Cite Haug & Jøhndal (2008). See
[Greek NLP → Neutral evaluation](Greek-NLP#neutral-evaluation-out-of-agdt).

> Universal Dependencies Ancient Greek treebanks (UD-Perseus, CC BY-NC-SA 2.5;
> UD-PROIEL, CC BY-NC-SA 3.0) and the CoNLL-2018 evaluator (MPL-2.0) are also
> fetched solely for `evaluate_on_ud()`, never bundled or trained on. See `NOTICE`.

#### The SigLA corpus (`sigla-corpus`, `aegean.load("sigla")`)

SigLA (Salgarella & Castellan, https://sigla.phis.me) publishes its Linear A
paleographical database under CC BY-NC-SA 4.0. pyaegean hosts the decoded JSON
dataset (reconstructed from the public web-app payload via
`scripts/build_sigla_corpus.py`) as the SHA-256-pinned `sigla-corpus` asset: 802
documents, 1,895 word-division groups, and commodity ideograms (~1.3 MB), fetched
on demand and never bundled. NonCommercial and ShareAlike obligations pass to the
user; attribution, source SHA-256, and build date live in `_meta`. Drawings
remain at sigla.phis.me.

```python
import aegean
s = aegean.load("sigla")
len(s)                       # 802
s.provenance.license         # 'CC BY-NC-SA 4.0 (as published by SigLA; ...)'
```

#### The DAMOS Linear B corpus (`damos-corpus`, `aegean.load("damos")`)

DAMOS (Database of Mycenaean at Oslo, F. Aurora, https://damos.hf.uio.no) is
published under CC BY-NC-SA 4.0. pyaegean hosts transliterations and metadata
(site, series, chronology, Trismegistos id, scribal hands, find context, object
class) for ~5,900 tablets built via `scripts/build_damos_corpus.py` as the
SHA-256-pinned `damos-corpus` asset (~3 MB), fetched on demand and never bundled.
NonCommercial and ShareAlike terms pass to the user; no imagery is included. Cite
Aurora (2015).

```python
import aegean
d = aegean.load("damos")
len(d)                       # 5932 documents
d.provenance.source          # 'DAMOS — Database of Mycenaean at Oslo (F. Aurora), ...'
```

#### Reading status on the epigraphy and papyri corpora

Six fetched inscription and papyrus corpora (`isicily`, `iip`, `iospe`, `igcyr`,
`edh`, `ddbdp`) preserve editorial apparatus on every token as `Token.status`
(`CERTAIN`, `UNCLEAR`, `RESTORED`, or `LOST`) and stamp `edition_fidelity` in
corpus provenance (`apparatus-preserved,normalized`, or
`apparatus-preserved,epichoric` for IGCyr's archaic Cyrenaean orthography). See
[Using Critical Editions](Using-Critical-Editions).

#### The I.Sicily Greek inscriptions (`isicily-corpus`, `aegean.load("isicily")`)

I.Sicily (https://github.com/ISicily/ISicily, https://sicily.classics.ox.ac.uk)
publishes ~5,120 Sicilian EpiDoc inscriptions under CC BY 4.0. pyaegean hosts
the 2,855 primary-Greek texts extracted by `scripts/build_isicily_corpus.py`
(line breaks resolved, abbreviations expanded, restored/uncertain letters marked,
lost gaps and editorial symbols stripped) with ancient find-place (`meta.site`),
date (`meta.period`), and coordinates (`meta.findspot`), fetched on demand as
`isicily-corpus`. Attribution travels in provenance and `NOTICE`. Cite Prag et
al.

```python
import aegean
s = aegean.load("isicily")
len(s)                       # 2855 documents
s.documents[0].meta.site     # e.g. 'Syracusae'
```

#### The DDbDP documentary papyri (`ddbdp-corpus`, `aegean.load("ddbdp")`)

The Duke Databank of Documentary Papyri (papyri.info, CC BY 3.0) ships as a
SQLite database with FTS5: 57,331 Greek papyri (~4.4M tokens) with citation,
date, place, and TM/HGV ids (~219 MB download, ~757 MB unpacked).
`aegean.load("ddbdp")` materializes all tokens into RAM (over a minute and >1 GB
memory); prefer `aegean db search ddbdp "..."` or `aegean.db.stream(ddbdp_db())`
(`from aegean.scripts.greek import ddbdp_db`) for streaming access.

#### The Greek New Testament + Dodson lexicon (`nt-corpus`, `bible.load_nt`, `use_lexicon("dodson")`)

The Nestle 1904 Greek NT base text is public domain, and its per-token
morphology, lemmas, and Strong's numbers (`biblicalhumanities/Nestle1904`) are
CC0. Two sample chapters ship in the wheel (`greek/nt_sample.json`, ~130 KB:
John 1 and Philemon 1) for offline use, and the full 27-book corpus (260 chapters,
~137,800 tokens) downloads on demand as `nt-corpus` via
`aegean.greek.bible.load_nt` or `aegean.load("nt")`. The Dodson Greek Lexicon
(J. J. Dodson, CC0, ~712 KB) is bundled in the wheel for offline Koine glossing
via `greek.use_lexicon("dodson")` and `bible.strongs_entry(...)`. Cite Nestle
1904 and Dodson in academic work.

```python
import aegean
from aegean import greek
from aegean.greek import bible

nt = aegean.load("nt")                     # full corpus (fetched on first use; cached after)
len(nt)                                    # 260 chapters
len(bible.nt_books())                      # 27 books

bible.strongs_entry("G3056").gloss         # 'word' (offline Dodson; upgrades with strongs-greek)
greek.use_lexicon("dodson")                # activate bundled Koine lexicon (offline)
greek.gloss("λόγος", dictionary="dodson")
# 'λόγος: a word, speech, divine utterance, analogy'
```

`bible.load_nt(book=None, ref=None, *, edition="nestle1904", offline=False, force=False)`
loads a single book, reference, or alternate critical edition (`sblgnt`, `srgnt`,
`bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`). Pass `offline=True` to read
the bundled John 1 / Philemon 1 sample without fetching.

#### Greek literary works (`greek.load_work`)

`aegean.greek.load_work("tlg0012.tlg001")` downloads a work's Greek TEI edition
from Perseus `canonical-greekLit` or `First1KGreek` (both CC BY-SA, tried in
that order or chosen via `source=`), caches it, and returns a `Corpus` (one
`Document` per book/chapter; verse lines or paragraphs as physical lines).
Signature: `load_work(work, *, ref=None, source="auto", edition=None, force=False)`.
`ref=` restricts loading to a citation span:

```python
from aegean import greek
greek.load_work("tlg0012.tlg001", ref="1")          # Iliad book 1
greek.load_work("tlg0012.tlg001", ref="1.1-1.50")   # book 1, lines 1–50
greek.load_work("tlg0016.tlg001", ref="1.2")        # Herodotus book 1, chapter 2
```

> Each first call fetches TEI over the network and parses it; cached works load
> offline thereafter.

Use the bundled metadata index `greek.catalog()` (`works_catalogue.json`) to
search available works offline (1,778 Greek `-grc` works at the pinned upstream
commits: 768 Perseus + 1,010 First1KGreek):

```python
from aegean import greek
len(greek.catalog())                       # 1778
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

`--limit` caps the `works` array while `matched` holds the total match count.

Coverage reflects the pinned upstream commits, so authors absent upstream (such
as Sappho, `tlg0009`) do not appear in the catalogue. `greek.popular_works()`
returns 25 frequently studied works. See
[Greek Works & Books](Greek-Works-and-Books).

Editorial `<note>` and `<bibl>` elements stay out of running text and are stored
in `Document.meta.notes` across JSON round-trips. Upstream downloads pin to a
fixed commit recorded in `Provenance.data_version` (such as
`PerseusDL/canonical-greekLit@d4fab69a2c26`), overridable via
`PYAEGEAN_GREEKLIT_REF` and `PYAEGEAN_FIRST1K_REF`. Cite Perseus / Open Greek
and Latin and the underlying edition named in the TEI header.

#### The Linear A Workbench app (`workbench-app`) and bring-your-own Linear B (`linearb-corpus`)

`workbench-app` is the prebuilt Linear A Research Workbench `v2.1.0` static web
app (~3.3 MB `tar.gz`, Apache-2.0 build, multi-script Aegean fonts, GORILA-derived
embedded Linear A data), pinned to `workbench-app-v2.1.0`, fetched on demand,
and served locally by `aegean workbench`.

`linearb-corpus` is a bring-your-own slot with no default URL for pointing
pyaegean at a local licensed Linear B export (such as a DAMOS EpiDoc archive or
private LiBER selection). DAMOS itself loads directly via `aegean.load("damos")`;
LiBER is © CNR Edizioni (all rights reserved) and is never redistributed. Set
`PYAEGEAN_LINEARB_CORPUS_URL` (or `PYAEGEAN_LINEARB_CORPUS`) before calling
`fetch("linearb-corpus")`.

---

## The CLI: `aegean data`

Data commands require `pip install "pyaegean[cli]"`:

| Command | Action | Flags |
|---|---|---|
| `aegean data list` | List fetchable datasets (name, size, license, on-disk status and byte footprint including kept `--version` entries) | `--json` (adds `versioned_bytes` / `versioned`), `-h/--help` |
| `aegean data fetch NAME` | One-time SHA-256-verified download into the local store (resumes interrupted transfers; no-op once valid) | `--force`, `--json`, `-h/--help` |
| `aegean data remove NAME` | Delete a stored dataset and print reclaimed bytes | `--all`, `--version v1` (remove one kept release only), `--json`, `-h/--help` |
| `aegean data versions` | Print reproducibility manifest (version and SHA-256 per dataset) | `--json`, `-h/--help` |
| `aegean data store` | Show local store path and contents (`aegean data cache` warns and points here) | `--json`, `-h/--help` |

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
aegean data fetch nt-corpus                # download and verify; no-op once cached
aegean data fetch lineara-images --force   # force re-download
aegean data remove nt-corpus               # remove one dataset
aegean data remove --all                   # clear all downloaded datasets
```

The same local store is accessible over MCP (`aegean-mcp`, `[mcp]` extra), which
exposes 29 read and analysis tools: `list_corpora`, `corpus_info`,
`show_document`, `search_signs`, `search_text`, `balance_accounts`,
`query_corpus`, `cite_corpus`, `geo_sites`, `data_status`, `library_status`,
`library_search`, `corpus_diagnose`, `greek_pipeline`, `greek_scan`,
`greek_catalog`, `greek_work`, `greek_gloss`, `greek_explain`, `koine_gloss`,
`biblical_strongs`, `biblical_word_study`, `biblical_psalm`,
`biblical_nomina_sacra`, `biblical_catalog`, `biblical_lxx`,
`biblical_compare_editions`, `biblical_witnesses`, and `biblical_commentary`.
`data_status` and `library_status` report downloaded state, disk usage, and
licenses read-only before an agent triggers a fetch; `cite_corpus` and
`query_corpus` emit exact-subset citations; `greek_work` and hosted `greek_gloss`
dictionaries download into this store on first call. MCP tools address corpora
and works only by registry id or catalogue id, never by local filesystem path.

---

## Environment overrides

Three environment variables control cache location and upstream sources:

| Variable | Effect |
|---|---|
| `PYAEGEAN_CACHE` | Store root. Falls back to `XDG_CACHE_HOME`, then `~/.cache`; files live under `<base>/pyaegean`. |
| `PYAEGEAN_<NAME>_URL` | Override a dataset's URL (uppercase name, `-` → `_`). Pinned SHA-256 verification is skipped for override URLs. |
| `PYAEGEAN_GREEKLIT_REF` / `PYAEGEAN_FIRST1K_REF` | Override upstream commit refs pinned by `load_work`. |

Examples of `PYAEGEAN_<NAME>_URL`:

| Dataset | Override variable |
|---|---|
| `lineara-images` | `PYAEGEAN_LINEARA_IMAGES_URL` |
| `agdt-derived` | `PYAEGEAN_AGDT_DERIVED_URL` |
| `lsj-index` | `PYAEGEAN_LSJ_INDEX_URL` |
| `middle-liddell-index` | `PYAEGEAN_MIDDLE_LIDDELL_INDEX_URL` |
| `cunliffe-index` | `PYAEGEAN_CUNLIFFE_INDEX_URL` |
| `abbott-smith-index` | `PYAEGEAN_ABBOTT_SMITH_INDEX_URL` |
| `grc-lemma-neural` | `PYAEGEAN_GRC_LEMMA_NEURAL_URL` |
| `grc-joint` | `PYAEGEAN_GRC_JOINT_URL` |
| `sigla-corpus` | `PYAEGEAN_SIGLA_CORPUS_URL` |
| `damos-corpus` | `PYAEGEAN_DAMOS_CORPUS_URL` |
| `isicily-corpus` | `PYAEGEAN_ISICILY_CORPUS_URL` |
| `iip-corpus` | `PYAEGEAN_IIP_CORPUS_URL` |
| `iospe-corpus` | `PYAEGEAN_IOSPE_CORPUS_URL` |
| `igcyr-corpus` | `PYAEGEAN_IGCYR_CORPUS_URL` |
| `edh-corpus` | `PYAEGEAN_EDH_CORPUS_URL` |
| `ddbdp-corpus` | `PYAEGEAN_DDBDP_CORPUS_URL` |
| `nt-corpus` | `PYAEGEAN_NT_CORPUS_URL` |
| `workbench-app` | `PYAEGEAN_WORKBENCH_APP_URL` |
| `linearb-corpus` | `PYAEGEAN_LINEARB_CORPUS_URL` |

```bash
# mirror override (SHA-256 not enforced on overrides)
export PYAEGEAN_LINEARA_IMAGES_URL="https://example.org/lineara-images.tar.gz"

# move local store to another volume
export PYAEGEAN_CACHE="/mnt/data/pyaegean-cache"
```

Inspect the resolved store path from Python:

```python
from aegean import data
data.cache_dir()    # e.g. WindowsPath('C:/Users/you/.cache/pyaegean')
```

---

## Data versioning — pinning for papers

`data.versions()` returns a reproducibility manifest with three keys: `package`,
`bundled`, and `fetched`:

```python
from aegean import data
v = data.versions()

v["package"]                                  # '0.74.0'  (installed version)
v["bundled"]["lineara/inscriptions.json"]     # {'sha256': '4705b2b2…', 'bytes': 720766}
v["fetched"]["nt-corpus"]
# {'url': 'https://github.com/ryanpavlicek/pyaegean/releases/download/nt-corpus-v1/nt-corpus.json',
#  'sha256': 'e7aa5dcad729eb91f77018abbef71304d13e200f29dabe1260b79fa37b153949',
#  'license': "CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain",
#  'cached': True}
```

Each `bundled` entry hashes a JSON file directly from the installed wheel (its
version equals `aegean.__version__`, stamped onto bundled corpora as
`Provenance.data_version`). Each `fetched` entry lists the pinned URL, SHA-256,
license, and cache state.

Save `aegean.__version__` and the manifest alongside published results so matching
SHA-256 digests guarantee identical input bytes:

```bash
aegean data versions --json > data-versions.json
```

```python
import json, aegean
from aegean import data
with open("data-versions.json", "w", encoding="utf-8") as f:
    json.dump({"package": aegean.__version__, "data": data.versions()}, f, indent=2)
```

Running `aegean data versions` without `--json` prints a readable table of
package version, bundled file hashes and sizes, and fetched asset statuses
(`cached`, `not cached`, or `(unpinned)`).

---

## Linked Open Data export

`aegean export <corpus> -f ttl` (Turtle) and `-f jsonld` (JSON-LD) serialize a
corpus as Linked Open Data (`io.to_rdf` in Python). Subject URIs come directly
from authoritative upstream identifiers: DDbDP documents use `papyri.info` URIs
(`http://papyri.info/ddbdp/<hybrid>` with Trismegistos id as `rdfs:seeAlso`,
falling back to Trismegistos when `ddbdp-uris` is uncached); EDH documents use
Trismegistos URIs (`https://www.trismegistos.org/text/<id>`); I.Sicily documents
use I.Sicily URIs; documents without an external URI use a non-resolvable
`urn:aegean:` URI (or caller `--base-uri`). Documents carry Dublin Core metadata
(title, identifier, source, language), WGS84 coordinates, Pleiades links where
available, and the corpus license as a machine-readable triple so NonCommercial
terms travel with exported triples. Editorial reading statuses are not flattened
into RDF; use JSON or SQLite for lossless persistence.

## Provenance & citation

Every `Corpus` carries a `Provenance` record stamped onto exports and formatted
by `.cite()`:

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
# '0.74.0'

corpus.to_dict()["_meta"]
# tool, schemaVersion, scriptId, documentCount, source, license, citation
```

On Linear A, the bundled transcription is normalized while preserving upstream
erased and damaged marks: erased signs map to `ReadingStatus.LOST` (552 tokens)
and damaged/bracketed-uncertain signs map to `UNCLEAR` (120 tokens across 91
documents; 366 documents carry at least one non-certain token). Full Leiden
restorations and dotted letters were removed in the upstream digitization;
consult GORILA and SigLA for edition-grade readings. `ReadingStatus` round-trips
through lossless JSON and token-carrier EpiDoc (`<unclear>`, `<supplied>`,
`<gap>`, emitting `LOST` as `<supplied reason="undefined">`).

---

## Your own corpus

### From a file you already have (`aegean import`)

Import a plain `.txt` file, directory of text files, or CSV in one command:

```bash
aegean import myplato.txt -o myplato.json     # then: aegean stats myplato.json
aegean import poems/ -o corpus.db --split line          # folder, one doc per line
aegean import rows.csv -o corpus.json --text-col line --id-col id
```

`--split` controls document boundaries: `whole` (default; one document preserving
line breaks), `paragraph` (blank-line blocks), or `line` (one document per line).
Imports default to `token_view="all"` (`--token-view all`), keeping decoded
source text, punctuation, foreign text, numerals, and aligned character spans.
Greek text (`--script greek`, default) uses the Greek tokenizer; other scripts
tokenize on whitespace. `doc.words` filters to lexical words. Pass
`token_view="words"` (`--token-view words`) for word-only import without source
text or spans. Python equivalents:

```python
from aegean import io
io.from_text_file("myplato.txt")                 # -> Corpus
io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος", doc_id="john")
io.from_text_dir("poems/", split="line")
io.from_csv("rows.csv", text_col="line", id_col="id", meta_cols=["period"])
```

> `read_corpus` and CLI `CORPUS` arguments load only pyaegean `.json` and `.db`
> files. Import `.txt` or `.csv` files first via `aegean import … -o corpus.json`.

### From structured records (`Corpus.from_records`)

Build from dict records for explicit token kinds, editorial status, and alternate
readings:

```python
import aegean
corpus = aegean.Corpus.from_records([
    {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
    {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
], script_id="myfind",
   provenance=aegean.Provenance(source="My dig notebook", citation="Me (2026)."))
```

Tokens can be plain strings (numerals inferred, hyphenated signs split) or dicts
with `kind`, `status`, and `alt`. Register by name with
`aegean.core.corpus.register_loader("myfind", lambda: corpus)`. For EpiDoc TEI,
`aegean.io.from_epidoc` and `aegean import --epidoc` parse token-carrier elements
(`<w>`, `<num>`, `<g>`, `<pc>`, `<seg>`) using stdlib XML (no extra required),
preserving id, find-place, lines, `<unclear>`/`<supplied>` status, and
`<app>`/`<rdg>` variants. `<num value="…">` preserves its raw attribute in
`Token.annotations["epidoc:num_value"]` as source evidence (not a computed value).
Other arbitrary token annotations require JSON or SQLite for lossless retention.
Free-text TEI requires a source-specific extractor.

### Variant readings

`Token.alt` stores alternate readings alongside `Token.status`. The EpiDoc writer
emits `<app><lem><w>PO-ME</w></lem><rdg><w>PO-MA</w></rdg></app>` (valid against
the official EpiDoc schema), and `from_epidoc` reconstructs the single token with
its `alt` tuple so variants survive both EpiDoc and JSON round-trips.

---

## Licensing summary

- **Code**: Apache-2.0.
- **Linear A corpus JSON**: GORILA via mwenge/lineara.xyz (Apache-2.0).
- **Linear A facsimile imagery (`lineara-images`)**: © École Française d'Athènes
  and other rightsholders; referenced, never redistributed.
- **Aegean sign data (Linear B / Cypriot / Cypro-Minoan, bundled)**: Unicode
  Character Database, Unicode License v3 (retain notice).
- **Greek sample corpus**: public-domain ancient texts (seed only).
- **Greek treebank lexicon + models (`agdt-derived`)**: Perseus AGDT v2.1, CC
  BY-SA 3.0; derived bundle hosted under CC BY-SA 3.0, fetched to cache.
- **Greek lexicon / LSJ (`lsj-index`)**: Perseus LSJ, CC BY-SA 4.0; derived index
  hosted under CC BY-SA 4.0, fetched to cache.
- **Greek neural lemmatizer (`grc-lemma-neural`, `[neural]`)**: GreTa seq2seq
  (Apache-2.0 base) fine-tuned on AGDT (CC BY-SA 3.0), Pedalion (CC BY-SA 4.0),
  and Gorman (CC BY-SA 4.0); released under CC BY-SA 4.0 (~232 MB), fetched.
- **Greek neural joint pipeline (`grc-joint`, `[neural]`)**: GreBerta-based joint
  model (Apache-2.0 base) fine-tuned on AGDT (CC BY-SA 3.0), Gorman (CC BY-SA
  4.0), and Pedalion (CC BY-SA 4.0) with eval folds excluded; released under CC
  BY-SA 4.0 (~173 MB), fetched.
- **PROIEL / UD evaluation sets**: UD-Perseus (CC BY-NC-SA 2.5), PROIEL and
  UD-PROIEL (CC BY-NC-SA 3.0); fetched for evaluation only, never bundled or
  trained on.
- **SigLA (`sigla-corpus`) and DAMOS (`damos-corpus`)**: CC BY-NC-SA 4.0;
  fetched, never bundled; NC + ShareAlike pass to end users.
- **Greek inscription corpora (`isicily-corpus`, `iip-corpus`, `iospe-corpus`,
  `igcyr-corpus`, `aphrodisias-corpus`, `crete-corpus`, `edh-corpus`)**:
  I.Sicily CC BY 4.0; IIP CC BY-NC 4.0; IOSPE CC BY; IGCyr/GVCyr CC BY-NC-SA 4.0;
  Aphrodisias CC BY 2.5; Crete CC BY-NC-SA 4.0; EDH CC BY-SA 4.0. All fetched;
  NonCommercial and ShareAlike terms pass through where applicable.
- **DDbDP papyri (`ddbdp-corpus`)**: DDbDP / papyri.info, CC BY 3.0; fetched;
  attribution required.
- **Greek New Testament (`nt-corpus`) + Dodson lexicon (bundled)**: Nestle 1904
  base text public domain; morphology, lemmas, Strong's, and Dodson are CC0.
- **Biblical, Patristic & Vernacular corpora (`strongs-greek`, `nt-editions`,
  `nt-witnesses`, `lxx-corpus`, `patrologia-graeca-corpus`,
  `apostolic-fathers-corpus`, `pseudepigrapha-corpus`, `byzantine-corpus`,
  `homer-scholia-corpus`)**: fetched under their respective upstream CC BY, CC
  BY-SA, Public Domain, or CC BY-NC 4.0 (`homer-scholia-corpus`) licenses as
  listed in the table above.
- **Linear A Workbench app (`workbench-app`, `v2.1.0`)**: Apache-2.0 build;
  embedded Linear A data is GORILA-derived.
- **Linear B bring-your-own (`linearb-corpus`)**: no default source; DAMOS is
  hosted under CC BY-NC-SA 4.0, while LiBER (© CNR Edizioni) is all rights
  reserved and never redistributed.

See `NOTICE` and `CITATION.cff` in the repository for complete attribution.

---

## Limitations

- **Full Linear A apparatus is not bundled.** Restorations and dotted letters were
  dropped upstream; only `LOST` and `UNCLEAR` survive. Consult GORILA and SigLA
  for edition-grade readings.
- **NonCommercial terms pass to users.** DAMOS, SigLA, PROIEL, UD treebanks,
  IGCyr/GVCyr, and Crete carry CC BY-NC-SA obligations (no commercial use;
  ShareAlike required). IIP and Homer Multitext carry CC BY-NC 4.0 (no commercial
  use).
- **Override URLs skip SHA-256 verification.** Setting `PYAEGEAN_<NAME>_URL`
  bypasses the pinned release checksum; verify custom mirrors independently.
- **Imagery is fetched, never re-hosted.** Check each file's `imageRights` in
  `lineara-images` before reuse.
- **First download of remote models, lexica, or works requires network access**;
  cached assets run offline thereafter.

See [Limitations](Limitations) for project-wide boundaries, and
[Greek NLP](Greek-NLP), [Linear A](Linear-A), [Linear B](Linear-B),
[Analysis](Analysis), and [Cypriot](Cypriot) for feature documentation.
