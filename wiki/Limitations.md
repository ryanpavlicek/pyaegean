# Limitations

pyaegean records prediction provenance and review flags, but an unflagged
prediction can still be wrong. This page documents what the toolkit cannot do,
what remains open on the [roadmap](Home#roadmap), and which constraints are
deliberate trade-offs.

Report missing or outdated entries via [For Specialists](For-Specialists).
Limits fall into three distinct categories, followed by accuracy boundaries and
architectural trade-offs:

1. **Limits of the evidence:** undeciphered scripts, fragmentary tablets, and
   divergent treebank conventions.
2. **Limits of licensing:** datasets that cannot be bundled in an Apache-2.0
   wheel and must be fetched on demand under upstream licenses.
3. **Engineering scope:** capabilities still incomplete or scoped to opt-in
   tiers.

Related pages: [Greek NLP](Greek-NLP) · [Meters](Meters) · [Linear A](Linear-A) ·
[Analysis](Analysis) · [CLI](CLI) · [Data & Provenance](Data-and-Provenance).

---

## Summary of limits

| Area | Limit | Section |
| --- | --- | --- |
| Linear A / Cypro-Minoan | Undeciphered; analytical and AI outputs are exploratory hypotheses, never translations | [Evidence](#limits-of-the-evidence-not-fixable-by-code) |
| Linear A accounting | Only 37 of 1,721 bundled tablets carry a checkable total | [Evidence](#limits-of-the-evidence-not-fixable-by-code) |
| Full Linear B corpus | NonCommercial (CC BY-NC-SA 4.0); fetched on demand (`load("damos")`), not bundled | [Licensing](#limits-of-licensing-fixable-only-by-permission) |
| SigLA / UD / PROIEL | NonCommercial; fetched for research or evaluation only | [Licensing](#limits-of-licensing-fixable-only-by-permission) |
| Offline rule morphology | Misses irregular, third-declension, and contract paradigms | [Engineering](#engineering-status-and-remaining-limits) |
| Neural model download | ~173 MB quantized download (`[neural]` extra) | [Engineering](#engineering-status-and-remaining-limits) |
| Out-of-domain Greek NLP | Accuracy drops on held-out genres and treebanks | [Accuracy](#measured-accuracy-boundaries) |
| Zero-dependency baselines | Fast offline floors; accuracy claims rest on the neural pipeline | [Accuracy](#measured-accuracy-boundaries) |
| AI layer | Exploratory hypotheses only, never attested readings | [Trade-offs](#documented-trade-offs-not-on-the-roadmap) |

---

## Limits of the evidence (not fixable by code)

These constraints come from the ancient material and external annotation
schemes.

- **Linear A and Cypro-Minoan are undeciphered.** Linear A phonetic
  transcription applies Linear B sound values strictly as a working convention:
  **50 of the 342** bundled signs carry an empirical sound value (from the 81
  signs shared with Linear B), each tagged with a `confidence`. Cypro-Minoan has
  **99 catalogued signs** and **0** settled sound values, so pyaegean provides
  no transliteration or lexicon for it. All analytical and AI outputs over these
  scripts are marked exploratory.

  ```python
  import aegean

  inv = aegean.get_script("lineara").sign_inventory
  read = [s for s in inv if s.phonetic]
  print(len(list(inv)), len(read))     # 342 50
  ```

  ```bash
  aegean sign lineara KU --json
  # {"label": "KU", "glyph": "𐙂", "phonetic": "ku", ...}
  aegean sign cyprominoan CM001 --json
  # {"label": "CM001", "glyph": "𒾐", "phonetic": "", ...}
  ```

- **Linear A tablets are fragmentary.** Only **37 of 1,721** bundled
  inscriptions contain a checkable accounting total (`KU-RO`/`KU-RA`/`TO-SO`),
  and only **7** are both intact and numerically balancing
  (`accounting.checkable_accounts(corpus)`). Most tablets are too damaged to
  check totals.

  ```python
  import aegean
  from aegean.analysis import accounting

  la = aegean.load("lineara")
  with_total = [d for d in la if accounting.balance_check(d)]
  print(len(with_total))                        # 37
  print(len(accounting.checkable_accounts(la))) # 7  (intact and balancing)
  ```

- **Damage is preserved on tokens.** Where upstream editions mark erased or
  bracketed signs, pyaegean retains them via `ReadingStatus`: **552** tokens in
  the bundled Linear A corpus load as `LOST` (326 documents) and **120** as
  `UNCLEAR` (91 documents), touching **366 documents** in total.

  ```python
  import aegean
  from aegean import ReadingStatus

  la = aegean.load("lineara")
  lost = sum(t.status is ReadingStatus.LOST for d in la for t in d.tokens)
  unclear = sum(t.status is ReadingStatus.UNCLEAR for d in la for t in d.tokens)
  print(lost, unclear)                          # 552 120
  ```

- **Linear A metrology and section boundaries remain contested.**
  `balance_check` identifies line-item sections heuristically and applies a
  default 10% tolerance because Aegean fractional values are not fully settled.
  A flagged discrepancy warrants manual inspection rather than a firm verdict.

- **Treebank conventions diverge.** On out-of-domain UD PROIEL, UFeats and LAS
  scores reflect annotation differences alongside model errors: PROIEL annotates
  morphological features absent from Perseus, and Perseus's 9-character XPOS
  tagset does not exist in PROIEL. See [Benchmarks](Benchmarks) for the
  convention decomposition.

- **Held-out verse evidence is small.** The shipped verse test contains 36
  sentences and 735 tokens from Euripides' *Bacchae* 1–169, producing wide
  confidence intervals specific to that passage. UD-Perseus dev and test folds
  contain prose only. A subsequent source audit identified a 20-token passage
  from Euripides' *Suppliants* and two full plays undergoing editorial review
  (Sophocles' *Philoctetes* and Euripides' *Iphigenia in Tauris*), while 14
  other native treebanks overlap works seen in v3 training. A broader verse
  benchmark requires adjudicated held-out plays or a training split that
  withholds whole dramas. Held-out epic gold remains open. See
  [Benchmarks](Benchmarks) and
  [source audit records](https://github.com/ryanpavlicek/pyaegean/tree/main/training/sources/greek-development-v1).

Summary of the four Aegean syllabic scripts:

| Script | `aegean.load(...)` id | Signs | Signs with a sound value | Lexicon | Status |
| --- | --- | --- | --- | --- | --- |
| Linear A | `lineara` | 342 | 50 (working convention) | — | Undeciphered |
| Linear B | `linearb` | 211 | 74 syllabograms (full grid) | 149 entries | Deciphered |
| Cypriot syllabary | `cypriot` | 55 | 55 (full grid) | 52 entries | Deciphered |
| Cypro-Minoan | `cyprominoan` | 99 | 0 | — | Undeciphered |

---

## Limits of licensing (fixable only by permission)

pyaegean's Python wheel is Apache-2.0. NonCommercial, ShareAlike, and
all-rights-reserved corpora are never bundled in the wheel; they are fetched on
demand into the local cache with SHA-256 verification, and upstream license
obligations pass through to the user.

- **Full Linear B corpus (DAMOS).** DAMOS (University of Oslo) is licensed
  **CC BY-NC-SA 4.0**. `aegean.load("damos")` fetches 5,932 tablets (Knossos,
  Pylos, Thebes, and other sites, with scribal hands, find contexts, and
  chronology) to the cache on demand. The bundled offline `linearb` dataset
  remains an 18-tablet sample.

  ```python
  import aegean

  lb = aegean.load("linearb")          # bundled 18-tablet sample, offline
  print(len(lb))                       # 18
  damos = aegean.load("damos")         # fetched on first use, 5,932 tablets
  ```

- **SigLA (Linear A palaeography).** Salgarella & Castellan's SigLA v4 dataset
  (**CC BY-NC-SA 4.0**) fetches via `aegean.load("sigla")` (802 documents,
  1,895 words grouped into `WORD` tokens, commodity ideograms as `LOGOGRAM`
  tokens, typology, dimensions, and periods). As a palaeographic sign database,
  SigLA omits cardinal-numeral accounting quantities (use bundled GORILA for
  accounting), and its word division and complex-sign notation differ from
  GORILA. Sign drawings remain hosted at `sigla.phis.me` and are not
  redistributed.

- **Evaluation treebanks (UD and PROIEL).** Both are **CC BY-NC-SA** and are
  fetched strictly for evaluation, never for model training. Models train only
  on CC BY-SA treebanks (AGDT, Gorman, Pedalion).

- **Linear A facsimile imagery.** Facsimile plates are © École Française
  d'Athènes and other rightsholders. They are referenced and available through
  an opt-in academic mirror (~116 MB), never bundled.

- **Un-hosted classical Greek lexica.** Hesychius, Photius' *Lexicon*, the
  *Etymologicum Magnum*, and Sophocles' *Greek Lexicon of the Roman and
  Byzantine Periods* have public-domain print editions, but existing clean
  digital texts derive from copyrighted modern critical editions (such as
  Latte's Hesychius) or the licensed TLG CD-ROM and cannot be re-hosted. Clean
  open digitization requires polytonic Greek HTR/OCR directly from public-domain
  scans, with Sophocles' single-column edition the clearest first candidate.
  Until such texts exist, these works remain deep-links alongside the Suda On
  Line; see [Greek NLP](Greek-NLP#more-dictionaries-the-lexicon-registry).

Fetched assets and why they stay outside the wheel:

| `load` id / asset | Contents | License | Reason not bundled |
| --- | --- | --- | --- |
| `damos` | Full Linear B (5,932 tablets) | CC BY-NC-SA 4.0 | NonCommercial |
| `sigla` | SigLA Linear A palaeography (802 docs) | CC BY-NC-SA 4.0 | NonCommercial |
| `isicily` / `iospe` / `edh` / `aphrodisias` | Greek inscriptions (2,855 / 1,194 / 1,286 / 1,471 docs) | CC BY 4.0 / CC BY 4.0 / CC BY-SA 4.0 / CC BY 2.5 | Size |
| `iip` / `igcyr` / `crete` | Greek inscriptions (2,113 / 997 / 600 docs) | CC BY-NC 4.0 / CC BY-NC-SA 4.0 / CC BY-NC-SA 4.0 | NonCommercial |
| `homer-scholia` | Homer Multitext Venetus A *Iliad* and *Scholia* (54 docs) | CC BY-NC 4.0 | NonCommercial |
| `ddbdp` | Documentary papyri (57,331 docs, SQLite + FTS) | CC BY 3.0 | Size (~219 MB download) |
| `nt` | Greek NT (Nestle 1904, 137,779 tokens) | CC0 / Public Domain | Size (John 1 and Philemon bundled offline) |
| UD / PROIEL folds | Evaluation treebanks | CC BY-NC-SA | NonCommercial; evaluation only |
| Neural model (`grc-joint-v3`) | Joint tagger, parser, lemmatizer | CC BY-SA 4.0 | Size (~173 MB); `[neural]` extra |
| Facsimile mirror | Linear A photos and drawings | © rightsholders | Redistribution restricted |

Local bring-your-own editions are also supported: point
`PYAEGEAN_LINEARB_CORPUS` at a local edition (for example LiBER, which is
all-rights-reserved). See [Data & Provenance](Data-and-Provenance) for cache
layout and verification commands.

---

## Engineering status and remaining limits

Open work is tracked on the [roadmap](Home#roadmap).

| Current scope / limit | Status |
| --- | --- |
| Bundled Linear A is a normalized transcription whose full Leiden apparatus was dropped upstream. Surviving erased marks load as `LOST` and bracketed readings as `UNCLEAR`; SigLA (`aegean.load("sigla")`) adds 802 palaeographic documents with typology, dimensions, periods, word division, and ideograms. | SigLA integration complete. Remaining limit: SigLA omits cardinal-numeral values; use bundled GORILA for accounting. |
| Bundled Linear B has 18 sample tablets and 149 source-attested Greek bridge entries (curated core plus Wiktionary equations). Many Mycenaean forms lack a clear alphabetic Greek descendant. | Full 5,932-tablet corpus available via `aegean.load("damos")`; bridge entries expand via verified contributions. |
| Bundled Cypriot lexicon has 52 source-cited entries (Idalion, Kurion, and Marion; Eteocypriot Amathus stays at 0/193 false positives). | Expands via verified contributions from published ICS/IG XV 1 readings. |
| Scansion covers dactylic hexameter, elegiac pentameter, iambic trimeter (with resolution), and aeolic lyric (glyconic, pherecratean, sapphic, alcaic). Synizesis fires only on words in a curated lexicon; unlisted lines decline instead of guessing. | Remaining limit: non-aeolic lyric (dactylo-epitrite, free astrophic). See [Meters](Meters). |
| Offline rule morphology misses irregular, third-declension, and contract paradigms and does not restore accents on reconstructed lemmas. | Covered by treebank and neural tiers; opt-in UniMorph paradigms (`greek.use_paradigms()`, CC BY-SA) cover irregular and third-declension nominals (NT lemma 66.98% → 71.21%, leaving ambiguous and capitalized forms unguessed); offline verbs remain rule-based. |
| 128 of 144 gazetteer find-sites carry Pleiades IDs; the remaining 16 are mostly minor findspots, peak sanctuaries, or modern place-names absent from Pleiades. | Coordinates checked weekly by `scripts/check_gazetteer.py`; unaligned sites listed in `docs/pleiades-candidates.md`. |
| Syllabification exceptions list dictionary headwords; inflected compounds fall back to phonotactic rules. | One-line, test-enforced additions via [CONTRIBUTING](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md). |

Offline catalog helpers list curated literary works and NT books without network
access:

```python
from aegean import greek
from aegean.greek import bible

print(len(greek.popular_works()))   # 25  (Homer, tragedians, Plato, …)
print(len(bible.nt_books()))        # 27
```

```bash
aegean greek works        # curated literary catalog with CTS IDs
aegean bible books nt     # the 27 NT books bible.load_nt accepts
```

---

## Measured accuracy boundaries

### Zero-dependency baselines

Pure-Python defaults run offline with zero third-party packages and provide
baseline floors. Enable `greek.use_neural_pipeline()` (`[neural]` extra) for
production accuracy.

| Zero-dependency baseline | Approximate performance | Typical use |
| --- | --- | --- |
| Rule POS tagger | High precision on closed classes only | Fast offline pass |
| Rule-based lemmatizer | ~67% on the full NT (closed-class table with grave-accent folding plus regular 2nd-declension and verb rules; opt-in `use_paradigms()` lifts this to 71.21%) | Zero-dependency default |
| Edit-tree lemmatizer | ~40% on unseen forms | Offline fallback |
| Arc-eager parser | ~0.63 UAS (projective) | Offline structural sketch |

### Out-of-domain drop

Like any statistical parser, the neural pipeline scores highest on Classical
literary prose near its training distribution and drops on held-out domains
such as UD PROIEL (which never enters training). Both folds are always reported
together:

| Metric | UD Perseus (in family) | UD PROIEL (out of domain) |
| --- | --- | --- |
| Lemma | 94.27 | 90.51 |
| UPOS | 97.02 | 86.68 |
| UFeats | 96.03 | 59.43 (convention-capped) |
| UAS | 90.24 | 82.47 |
| LAS | 85.65 | 63.50 (scheme-capped) |

PROIEL UFeats and LAS limits reflect scheme differences between the Perseus and
PROIEL UD conversions in addition to domain shift. Full tables, bootstrap CIs,
and documentary/verse/Byzantine rows appear on [Benchmarks](Benchmarks). Tier
activation is documented on [Greek NLP](Greek-NLP).

### Known training artifact: bare apposition labeled `cc`

The AGDT→UD converter used to generate `grc-joint-v3`'s training labels mapped
leaf `APOS` relations (an appositive attached directly under its antecedent) to
`cc`. The converter and AGDT-derived evaluation folds now emit `appos`, but the
shipped `grc-joint-v3` weights still predict `cc` on bare appositives. This
confusion is already priced into the published LAS figures; until a retrained
checkpoint ships, inspect `cc` labels attached to nouns as probable apposition.

---

## Documented trade-offs (not on the roadmap)

These choices are intentional architectural boundaries:

- **Zero-dependency core.** `import aegean` requires only the Python standard
  library. Heavy packages install behind opt-in extras, and large models or
  corpora fetch to cache rather than shipping in the wheel:

  | Extra | Dependencies | Enables |
  | --- | --- | --- |
  | `cli` | `typer`, `rich`, `prompt_toolkit` | `aegean` CLI and REPL |
  | `neural` | `onnxruntime`, `tokenizers`, `numpy` | Joint neural Greek pipeline (torch-free) |
  | `data` | `pandas` | DataFrame interop |
  | `parquet` | `pyarrow` | Parquet export |
  | `epidoc` | `lxml` | DAMOS-style Linear B EpiDoc import and schema validation (generic token-carrier EpiDoc I/O is stdlib-only) |
  | `geo` | `geopandas`, `shapely` | GeoJSON and GeoDataFrames |
  | `viz` | `matplotlib` | `aegean plot` / `aegean.viz` figures |
  | `viz-interactive` | `plotly` | Interactive findspot, timeline, and sign-network plots |
  | `mcp` | `mcp` | Model Context Protocol server |
  | `tui` | `textual` | `aegean tui` terminal interface |
  | `anthropic` / `openai` / `gemini` / `grok` / `openrouter` / `local` | Provider SDK | Single AI provider |
  | `ai` | All provider SDKs | All AI providers |
  | `spacy` / `stanza` / `cltk` / `interop` | Target framework(s) | Loss-aware document adapters (Stanza pulls PyTorch; CLTK requires Python 3.13+) |
  | `all` | `ai,epidoc,geo,data,cli,viz,mcp,tui,neural` | Combined runtime stack (excludes `parquet`, `viz-interactive`, and framework adapters) |

- **Lossy vs. lossless serialization.** `to_dict()` emits a compact summary for
  quick inspection. Use `Corpus.to_json()` and `Corpus.from_json()` whenever
  full round-tripping of statuses, typed form state, and annotations matters.

- **Mapping-grade gazetteer.** Coordinates are ~1 km site centroids for
  distribution maps, not archaeological survey points. One entry, Margiana
  (Turkmenistan), is preserved because it appears in upstream metadata, flagged
  with `SiteCoord.contested`, and excluded from uncontested distribution maps.

- **Exploratory AI policy.** Every generative output carries an exploratory
  label and provenance trace. Grounding may contain source annotations,
  provisional predictions, human review decisions, or nothing on low-level
  calls; outputs are never elevated to attested readings regardless of model
  confidence. Hosted providers require API keys; `local` runs against a local
  server (Ollama, LM Studio, llama.cpp, vLLM) without network egress.

- **In-memory corpora and streaming boundaries.** Most corpora fit comfortably
  in memory (DAMOS is 5,932 documents). The exception is DDbDP (57,331 papyri),
  which ships as SQLite: query it with `aegean db search ddbdp` or stream it
  document-by-document with `aegean.db.stream(ddbdp_db())` instead of calling
  `aegean.load("ddbdp")`. For large workflows, `Corpus.iter_documents` /
  `iter_tokens` / `iter_words` stream tokens, `greek.iter_analyze_sentences`
  streams pre-tokenized sentences through the neural pipeline, and
  `aegean.db.annotate_sqlite_job` (`aegean db annotate`) writes durable,
  resumable document-by-document SQLite annotations (design note:
  [docs/large-corpora.md](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/large-corpora.md)).
  Raw-text pipelines, in-memory corpus annotation, and CoNLL-U serialization
  collect full results in memory. `SentenceAnalysis.receipt` (schema 4) records
  model identity, runtime variant, opt-in post-processing (documentary
  reconciliation/rescue or weighted OOV lemma reranker), and calibration hashes.

- **Browser and no-Python options.** Core functionality runs client-side in
  Pyodide at [the web demo](https://pyaegean.xyz/demo/). Locally,
  [`aegean browse`](Greek-Browser) (`aegean.browser`) serves a zero-dependency
  visual corpus browser for Greek texts (interlinear, translations, morphology,
  lexica, commentaries, and Library Manager),
  [linearaworkbench](https://github.com/ryanpavlicek/linearaworkbench)
  (`aegean workbench`) provides the visual workbench for the Aegean syllabic
  scripts, and the [CLI](CLI) and [TUI](TUI) cover terminal workflows without
  writing Python.

---

Found an undocumented or outdated limit? Report it via
[For Specialists](For-Specialists).
