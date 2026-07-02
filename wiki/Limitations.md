# Limitations

pyaegean's rule is that it tells you where it's confident and where it's
guessing. This page is the complete picture in one place: what the toolkit
**cannot** do and why, what it **does not yet** do and plans to, and what it
deliberately **won't** do. Use it the way you'd use a methods section: to know
exactly how far a result can be pushed before you reach for a human expert.

It is a **living register**. Found something it gets wrong, or a limit worth
recording? See [For Specialists](For-Specialists) for how to file a correction or
a validation. Three kinds of limits behave very differently, and the rest of this
page is organized around them:

1. **Limits of the evidence**: undeciphered scripts, fragmentary tablets,
   contested readings. No amount of code removes these; the toolkit's job is to
   keep them visible.
2. **Limits of licensing**: data the project may use but not redistribute, so it
   is fetched on demand rather than bundled.
3. **Engineering limits**: things code *can* fix, tracked on the
   [roadmap](Home#roadmap), each paired with the plan.

Then two reference sections: the **measured accuracy boundaries** (the weak
numbers, published alongside the strong ones) and the **by-design trade-offs**
(decisions made on purpose, not bugs and not on the roadmap).

Related pages: [Greek NLP](Greek-NLP) · [Meters](Meters) · [Linear A](Linear-A) ·
[Analysis](Analysis) · [CLI](CLI) · [Data & Provenance](Data-and-Provenance).

---

## Quick map of the limits

| Area | The honest limit | Where it's covered |
| --- | --- | --- |
| Linear A / Cypro-Minoan readings | Undeciphered; results are **exploratory**, never translations | [Evidence](#limits-of-the-evidence-not-fixable-by-code) |
| Linear A accounting | Only ~37 of 1,721 tablets carry a checkable total | [Evidence](#limits-of-the-evidence-not-fixable-by-code) |
| Full Linear B corpus | NonCommercial → fetched, not bundled (`load("damos")`) | [Licensing](#limits-of-licensing-fixable-only-by-permission) |
| SigLA / UD / PROIEL data | NonCommercial → fetched for research/eval only | [Licensing](#limits-of-licensing-fixable-only-by-permission) |
| Offline morphology | Misses irregular/3rd-decl./contract paradigms | [Engineering](#engineering-limits-we-plan-to-lift) |
| Neural model size | ~173 MB quantized download | [Engineering](#engineering-limits-we-plan-to-lift) |
| Out-of-domain NLP | Accuracy drops on held-out treebanks | [Accuracy](#measured-accuracy-boundaries) |
| Zero-dep baselines | Honest floors, not the accuracy story | [Accuracy](#measured-accuracy-boundaries) |
| AI layer | Exploratory by construction: never a reading | [By design](#by-design-documented-trade-offs-not-on-the-roadmap) |

---

## Limits of the evidence (not fixable by code)

These are properties of the material itself. They will not go away with a better
release.

- **Linear A and Cypro-Minoan are undeciphered.** Linear A's phonetic
  transcription uses Linear B sound values as a *working convention*: in the
  bundled inventory **48 of the 342 signs** carry an empirical sound value
  (drawn from the 81 signs shared with the Linear B grid), each with a
  `confidence`; the rest have no agreed reading. Cypro-Minoan goes further: of
  its **99 catalogued signs, none** carries a settled sound value, so pyaegean
  offers no transliteration or lexicon for it. Every analytical or generative
  result over this material is labeled **exploratory**: evidence for a human
  expert to weigh, never a reading or a translation.

  ```python
  import aegean
  inv = aegean.get_script("lineara").sign_inventory
  read = [s for s in inv if s.phonetic]
  print(len(list(inv)), len(read))     # 342 48
  ```

  ```bash
  # The same fact from the CLI — a read sign vs. an unread one:
  aegean sign lineara KU --json
  # {"label": "KU", "glyph": "𐙂", "phonetic": "ku", ...}
  aegean sign cyprominoan CM001 --json
  # {"label": "CM001", "glyph": "𒾐", "phonetic": "", ...}
  ```

- **The corpora are fragmentary.** Only **about 37 of the 1,721** bundled Linear A
  inscriptions carry a stated, checkable accounting total (`KU-RO`/`KU-RA`/`TO-SO`); most
  tablets are too damaged to balance. Stricter still, only a handful are *intact
  and balancing*: `accounting.checkable_accounts(corpus)` returns the clean
  drill set. That is the nature of the evidence, not a parser gap.

  ```python
  import aegean
  from aegean.analysis import accounting
  la = aegean.load("lineara")
  with_total = [d for d in la if accounting.balance_check(d)]
  print(len(with_total))                       # 37
  print(len(accounting.checkable_accounts(la))) # 7  (intact AND balancing)
  ```

- **Damage is recorded, not hidden.** Where the upstream edition marked a sign as
  erased or as a damaged/bracketed reading, pyaegean keeps it as a token status
  rather than dropping it: **552** tokens load as `LOST` (across 326 documents)
  and **120** as `UNCLEAR` (across 91 documents). In total **366 documents**
  carry at least one such mark, so any analysis can choose to trust, weight, or
  exclude them.

  ```python
  import aegean
  from aegean import ReadingStatus
  la = aegean.load("lineara")
  lost = sum(t.status is ReadingStatus.LOST for d in la for t in d.tokens)
  unclear = sum(t.status is ReadingStatus.UNCLEAR for d in la for t in d.tokens)
  print(lost, unclear)                          # 552 120
  ```

- **Linear A metrology and section boundaries are contested.**
  `balance_check`'s line-item sections are heuristic, and the default 10%
  tolerance is a lenient cutoff chosen *because* Aegean fractional metrology is
  imperfectly understood. A reported "discrepancy" is a lead, not a verdict on
  the scribe.

- **Annotation conventions differ across treebanks.** On the out-of-domain PROIEL
  evaluation, morphological-feature scores are capped by convention mismatches
  (PROIEL annotates feature types the Perseus scheme lacks, and the 9-character
  AGDT positional tag doesn't exist there at all): a measurement boundary, not a
  model defect. Protocol notes:
  [`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md).

The four undeciphered/partly-read scripts at a glance:

| Script | `aegean.load(...)` id | Signs | Signs with a sound value | Lexicon | Status |
| --- | --- | --- | --- | --- | --- |
| Linear A | `lineara` | 342 | 48 (working convention) |— | Undeciphered |
| Linear B | `linearb` | (Linear B grid) | full grid | 150 entries | Deciphered |
| Cypriot syllabary | `cypriot` | (ICS grid) | full grid | 17 entries | Deciphered |
| Cypro-Minoan | `cyprominoan` | 99 | 0 |— | Undeciphered |

---

## Limits of licensing (fixable only by permission)

Some of the most useful data is NonCommercial or all-rights-reserved. pyaegean's
wheel is Apache-2.0, so NonCommercial data **can't live in the wheel**: it is
fetched to your local cache on demand, sha256-pinned, with the upstream
obligations passing through to you. The bundled, offline defaults stay small and
license-clean.

- **The full Linear B corpus is NonCommercial, so it is fetched, not bundled.**
  The most complete edition, DAMOS (Oslo), is **CC BY-NC-SA 4.0**: usable and
  redistributable, but NonCommercial. `aegean.load("damos")` fetches it
  (~5,900 tablets: Knossos, Pylos, Thebes, …, with site/chronology, scribal
  hands, find context, and object class) to your cache on demand, and the NC +
  ShareAlike obligations pass to you. The bundled **18-tablet** sample remains the
  offline, zero-network default.

  ```python
  import aegean
  lb = aegean.load("linearb")          # bundled sample, offline
  print(len(lb))                        # 18
  damos = aegean.load("damos")          # fetched on first use (network), ~5,900 tablets
  ```

- **SigLA's sign-level data** (Salgarella & Castellan) is **CC BY-NC-SA 4.0** and
  is integrated on the same fetch-to-cache, research-use, never-bundled pattern.
  `aegean.load("sigla")` fetches the decoded **v2** dataset (**781 documents**)
  with typology, dimensions, periods, **SigLA's own word division** (**1,376
  words** grouped into `WORD` tokens) and commodity ideograms (`LOGOGRAM`
  tokens). SigLA is a *palaeographic* database: it records sign occurrences and
  word division, **not** the cardinal-number quantities of the accounts, so it
  carries no numeral values (use GORILA, the bundled corpus, for accounting), and
  its word division and complex-sign notation differ editorially from GORILA. The
  drawings remain at sigla.phis.me (referenced, never redistributed).

- **The UD and PROIEL treebanks are CC BY-NC-SA**: pyaegean fetches them for
  **evaluation only** and never trains on them. (The models *are* trained on the
  CC BY-SA AGDT / Gorman / Pedalion treebanks, which permit it.)

- **Linear A facsimile imagery** is © École Française d'Athènes and other
  rightsholders: referenced and fetched for academic use, never redistributed
  (~116 MB mirror, opt-in).

The fetched, never-bundled assets, and why:

| `load` id / asset | What it is | License | Why fetched, not bundled |
| --- | --- | --- | --- |
| `damos` | Full Linear B, ~5,900 tablets | CC BY-NC-SA 4.0 | NonCommercial |
| `sigla` | SigLA Linear A palaeography, 781 docs | CC BY-NC-SA 4.0 | NonCommercial |
| `nt` | Greek NT (Nestle 1904), ~137,800 tokens | CC0 / public domain | Size: redistributable, one book bundled offline |
| UD / PROIEL folds | Evaluation treebanks | CC BY-NC-SA | NonCommercial; eval only, never trained on |
| neural model | Joint tagger/parser/lemmatizer | CC BY-SA (from treebanks) | Size (~173 MB); the `[neural]` extra |
| facsimile mirror | Linear A photos/drawings | © rightsholders | Not licensed for redistribution |

Bring-your-own corpora are supported too: point `PYAEGEAN_LINEARB_CORPUS` at a
local edition (e.g. LiBER, which is all-rights-reserved and stays
bring-your-own). See [Data & Provenance](Data-and-Provenance) for the cache layout and
the integrity-check workflow.

---

## Engineering limits we plan to lift

Each of these is something code *can* fix, and each is on the
[roadmap](Home#roadmap).

| Limitation today | Plan |
| --- | --- |
| The bundled Linear A corpus is a *normalized* transcription: the full Leiden apparatus (restorations, dotted readings) was dropped upstream. *What survived is now interpreted* (erased marks → `LOST`, bracketed readings → `UNCLEAR`), and **SigLA is loadable** (`aegean.load("sigla")`: 781 documents with typology, dimensions, periods, SigLA's own word division, and commodity ideograms) | **Largely done.** Remaining by design: SigLA carries no cardinal-numeral *values* (it is a palaeographic sign database): use GORILA for accounting |
| Linear B bundles an 18-tablet illustrative sample and a 150-entry Greek-bridge lexicon: every entry source-attested (curated core + Wiktionary-stated equations). 150 is close to the natural ceiling of *stated* Ancient Greek equations; many Mycenaean words have no alphabetic descendant to bridge to | The full ~5,900-tablet corpus is one call away via `aegean.load("damos")`; lexicon growth is contribution-driven and per-entry verified |
| The Cypriot lexicon is small (17 entries, Idalion-centred) | Grows by verified contribution from published ICS facts |
| Scansion covers dactylic hexameter, elegiac pentameter, **iambic trimeter** (with resolution), and the **aeolic lyric** lines (glyconic, pherecratean, sapphic, alcaic). Synizesis is applied only for words in a curated, test-enforced lexicon: a line needing it on an un-listed word declines rather than guesses | **Done.** Remaining by design: **non-aeolic lyric** (dactylo-epitrite, free astrophic): a research project. See [Meters](Meters) |
| The offline rule morphology misses irregular, third-declension, and contract paradigms, and doesn't restore accents on reconstructed lemmas | **By design**: the treebank and neural tiers cover these forms; a redistributable offline paradigm table would need a license-clean source that isn't currently available |
| 40 of 56 gazetteer find-sites carry Pleiades ids; the rest are mostly minor findspots / peak sanctuaries not yet in Pleiades | The alignment was extended (each coordinate-verified, and re-checked weekly by `scripts/check_gazetteer.py`); the remaining sites are listed as upstream-contribution candidates (`docs/pleiades-candidates.md`) |
| The syllabification exception lexicon lists dictionary forms; inflected compounds fall back to the phonotactic rules | Grows by contribution: adding an entry is a one-line, test-enforced change ([CONTRIBUTING](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md)) |

The discovery helpers above are pure offline metadata: handy when you don't know
the CTS id you need:

```python
from aegean import greek
print(len(greek.popular_works()))   # 25  (Homer, the tragedians, Plato, …)
print(len(greek.nt_books()))        # 27
```

```bash
aegean greek works        # curated catalog with CTS ids
aegean greek nt-books     # the 27 NT books load_nt accepts
```

---

## Measured accuracy boundaries

Every accuracy claim is measured and the protocol published: which means the
*weak* numbers are public too. Two boundaries matter most.

**The zero-dependency baselines are honest floors, not the accuracy story.** They
exist for the zero-install path; the opt-in tiers, ending in the neural pipeline,
are where the accuracy lives.

| Baseline (pure-Python, zero deps) | Roughly | Use it for |
| --- | --- | --- |
| Rule POS tagger | High precision on **closed classes** only | Quick, offline first pass |
| Rule-based lemmatizer | ~66% on the full NT (closed-class table with grave-accent folding + regular 2nd-decl/verb rules; the opt-in backends do far better) | Always-offline default |
| Edit-tree lemmatizer | ~40% on unseen forms | Offline fallback |
| Arc-eager parser | ~0.67 UAS (projective) | Offline structural sketch |

Turn on the neural pipeline (`greek.use_neural_pipeline()`, the `[neural]` extra)
and the same functions consult it instead.

**Out-of-domain performance drops, as it does for every system.** The neural
pipeline's lemma accuracy is **94.29** on the UD Perseus test fold and **90.50**
on UD PROIEL: a treebank none of pyaegean's models train on. Both numbers are
always reported together.

| Metric | UD Perseus (in family) | UD PROIEL (out of domain) |
| --- | --- | --- |
| Lemma | 94.29 | 90.50 |
| UPOS | 97.04 | 86.71 |
| UFeats | 96.04 | 59.43 (convention-capped) |
| UAS | 90.23 | 82.47 |
| LAS | 85.64 | 63.47 (scheme-capped) |

The PROIEL UFeats/LAS figures are *measurement* boundaries, not model failures:
PROIEL's UD conversion uses feature types and a relation scheme the Perseus
training data doesn't share. Full tables and protocol:
[`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md).
See [Greek NLP](Greek-NLP) for how to switch tiers.

---

## By design (documented trade-offs, not on the roadmap)

These are deliberate. They're listed here so you can judge them, not so they get
"fixed."

- **The core stays zero-dependency**: no pydantic, no database backend, instant
  import. Heavy capability lives behind extras and the fetch-to-cache layer.
  Models and corpora are **never bundled** in the wheel. The opt-in extras:

  | Extra | Adds | Powers |
  | --- | --- | --- |
  | `cli` | typer, rich | the `aegean` command |
  | `neural` | onnxruntime, tokenizers, numpy | the joint NLP pipeline (torch-free) |
  | `data` | pandas | tabular export / DataFrames |
  | `parquet` | pyarrow | Parquet export |
  | `epidoc` | lxml | EpiDoc TEI in/out |
  | `geo` | geopandas, shapely | GeoJSON / GeoDataFrames |
  | `viz` | matplotlib | the `plot` figures |
  | `mcp` | mcp | the Model Context Protocol server (e.g. for Claude Code) |
  | `anthropic` / `openai` / `gemini` / `grok` / `openrouter` | one provider SDK | the AI layer |
  | `ai` | all providers | the AI layer, any provider |
  | `all` | `ai,epidoc,geo,data,cli,viz,mcp` | everything except `neural` |

- **`to_dict()` is a lossy summary** on purpose (words + metadata, for quick
  interop); the lossless, reversible path is `Corpus.to_json()` /
  `Corpus.from_json()`. Reach for the latter whenever round-tripping matters.

- **The gazetteer is mapping-grade** (~1 km site-level coordinates), for
  distribution maps: not survey work. One entry is a **contested** find-spot:
  Margiana (Turkmenistan) is kept because the upstream corpus carries it, but no
  Linear A inscription is accepted from Central Asia, so it is flagged
  (`SiteCoord.contested`) and never silently mapped as genuine.

- **The AI layer is exploratory by construction.** Every generative result is a
  labeled, provenanced hypothesis built on local deterministic grounding: by
  policy it is never presented as a reading, whatever the model's confidence. It
  needs your own API key and the matching extra; nothing is sent anywhere unless
  you turn it on.

- **Corpora are held in memory**: fine for everything pyaegean ships and fetches
  (the largest, DAMOS, is ~5,900 documents). `Corpus.iter_documents` /
  `iter_tokens` / `iter_words` stream token-by-token where you need it, and an
  opt-in [analysis cache](Analysis#caching-expensive-analyses-opt-in) reuses
  heavy results; true streaming *load* is deferred until a corpus needs it (design
  note:
  [docs/large-corpora.md](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/large-corpora.md)).

- **Try it without installing anything**: the core pipeline runs client-side via
  Pyodide at [the web demo](https://ryanpavlicek.github.io/pyaegean/demo/); the
  [CLI](CLI) is the full no-Python path; and the
  [linearaworkbench](https://github.com/ryanpavlicek/linearaworkbench) web app
  covers the visual Linear A use case.

---

Spotted a limit that's missing, stale, or wrong? That's exactly what this page is
for: see [For Specialists](For-Specialists) to file it.
