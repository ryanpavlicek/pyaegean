# Limitations

pyaegean's rule is that it tells you where it's confident and where it's guessing.
This page is the complete picture in one place: what the toolkit **cannot** do and
why, what it **does not yet** do and plans to, and what it deliberately **won't**
do. Three kinds of limits behave very differently:

1. **Limits of the evidence** — undeciphered scripts, fragmentary tablets,
   contested readings. No amount of code removes these; the toolkit's job is to
   keep them visible.
2. **Engineering limits** — things code *can* fix, tracked on the
   [roadmap](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/ROADMAP.md).
3. **Design decisions** — trade-offs made on purpose, documented so you can
   judge them.

## Limits of the evidence (not fixable by code)

- **Linear A and Cypro-Minoan are undeciphered.** Linear A's phonetic
  transcription uses Linear B sound values as a *working convention* — 84 of the
  344 signs carry one; the rest have no agreed reading. Cypro-Minoan has no
  settled sound values at all, so pyaegean offers no transliteration or lexicon
  for it. Every analytical or generative result over this material is labeled
  **exploratory**: evidence for a human expert to weigh, never a reading or a
  translation.
- **The corpora are fragmentary.** Only ≈40 of the 1,721 bundled Linear A
  inscriptions carry a checkable accounting total; most tablets are too damaged.
  That is the nature of the evidence, not a parser gap.
- **Linear A metrology and section boundaries are contested.**
  `balance_check`'s line-item sections are heuristic; a "discrepancy" is a lead,
  not a verdict on the scribe.
- **Annotation conventions differ across treebanks.** On the out-of-domain
  PROIEL evaluation, morphological-feature scores are capped by convention
  mismatches (and the 9-character positional tag doesn't exist there at all) —
  a measurement boundary, not a model defect. The protocol notes are in
  [`docs/benchmarks.md`](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/benchmarks.md).

## Limits of licensing (fixable only by permission)

- **No openly-licensed Linear B corpus exists.** DAMOS (Oslo) is CC BY-NC-SA;
  LiBER (CNR) is all-rights-reserved. pyaegean bundles a small illustrative
  sample and parses *your own* licensed export locally
  (`PYAEGEAN_LINEARB_CORPUS`); licensing inquiries with both projects are a
  roadmap item, and the outcome will be documented either way.
- **The UD and PROIEL treebanks are CC BY-NC-SA** — pyaegean fetches them for
  **evaluation only** and never trains on them.
- **Linear A facsimile imagery** is © École Française d'Athènes and other
  rightsholders: referenced and fetched for academic use, never redistributed.
- **SigLA's apparatus-grade sign data** (Salgarella & Castellan) would lift the
  Linear A corpus to edition grade; a licensing inquiry is on the roadmap.

## Engineering limits we plan to lift

Each of these is on the [roadmap](https://github.com/ryanpavlicek/pyaegean/blob/main/docs/ROADMAP.md);
the pointer says where.

| Limitation today | Plan |
| --- | --- |
| The bundled Linear A corpus is a *normalized* transcription — the upstream digitization dropped the full Leiden apparatus (lacunae, restorations, uncertainty) | WP4: audit the upstream source for recoverable apparatus → populate `ReadingStatus` → a GORILA-faithful corpus v2 (with the SigLA inquiry as the deeper path) |
| Linear B bundles ~2 sample tablets and a ~45-entry Greek-bridge lexicon | WP4: grow to ~25 canonical tablets and 300+ lexicon entries from the standard editions |
| The Cypriot sample is similarly small | WP4: modest sample + lexicon growth from published ICS facts |
| `greek.load_work` reads top-level textparts only, drops `<note>`/`<bibl>` silently, and discovers editions via an unauthenticated GitHub listing (rate-limited at scale) | WP4: loader hardening — cached listings/auth token, deeper textpart addressing |
| Scansion covers dactylic hexameter + elegiac pentameter only, and **synizesis is declined, never inferred** (a line that needs it raises rather than guesses) | Post-0.8.0: iambic trimeter and lyric metres, plus a curated synizesis lexicon on the same pattern as the syllabification exceptions |
| The offline rule morphology misses irregular, third-declension, and contract paradigms, and doesn't restore accents on reconstructed lemmas (the treebank and neural tiers cover these) | Post-0.8.0: Morpheus-backed morphological tables for the offline tier |
| The neural pipeline's model is a 518 MB fp32 download (int8 quantization failed its accuracy gate and was rejected) | Post-0.8.0: selective quantization under the same ≤0.3-point gate, and optional GPU execution providers |
| Only 26 of 56 gazetteer find-sites carry Pleiades ids | WP8: extend the alignment and contribute the missing Bronze Age sites upstream |
| The syllabification exception lexicon lists dictionary forms; inflected compounds fall back to the phonotactic rules | Grows by contribution — adding an entry is a one-line, test-enforced change ([CONTRIBUTING](https://github.com/ryanpavlicek/pyaegean/blob/main/CONTRIBUTING.md)) |

## Measured accuracy boundaries

Every accuracy claim is measured and the protocol published — which also means
the *weak* numbers are public:

- The zero-dependency baselines are honest floors: the rule POS tagger is
  high-precision only on closed classes; the pure-Python edit-tree lemmatizer
  reaches ~40% on unseen forms; the arc-eager parser is a ~0.67 UAS (projective)
  baseline. Each exists for the zero-install path — the opt-in tiers, ending in
  the neural pipeline, are the accuracy story.
- Out-of-domain performance drops, as it does for every system: the neural
  pipeline's lemma accuracy goes from 94.4 (UD Perseus test) to 90.6 on PROIEL,
  a source none of pyaegean's models train on. Both numbers are always reported
  together; `docs/benchmarks.md` holds the full tables.

## By design (documented trade-offs, not on the roadmap)

- **The core stays zero-dependency** — no pydantic, no database backend, instant
  import; heavy capability lives behind extras and the fetch-to-cache layer.
  Models and corpora are **never bundled** in the wheel.
- **`to_dict()` is a lossy summary** on purpose; the lossless path is
  `to_json()`/`from_json()`.
- **The gazetteer is mapping-grade** (~1 km site-level coordinates), for
  distribution maps — not survey work.
- **The AI layer is exploratory by construction.** Every generative result is a
  labeled, provenanced hypothesis built on local deterministic grounding — by
  policy it is never presented as a reading, whatever the model's confidence.
- **A web demo is parked** — the [CLI](CLI) is the no-Python path; the
  [linearaworkbench](https://github.com/ryanpavlicek/linearaworkbench) web app
  covers the visual Linear A use case.
