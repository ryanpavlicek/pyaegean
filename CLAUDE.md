# CLAUDE.md — pyaegean working notes

Auto-loaded at session start. Strategic design of record: `docs/PLAN.md`.

## What pyaegean is

A *specialist* Python toolkit for **Ancient Greek** — alphabetic
Greek (Archaic→Koine) and the Aegean syllabic scripts (Linear A today; Linear B /
Cypriot planned). Goal: **deep, high-quality Greek coverage**, using CLTK as a friendly
benchmark to measure against — never a dependency. The Linear A material is
undeciphered — never present analysis as ground truth.

## Current state — v0.2.0 (288 tests passing, 1 skipped)

- `aegean.core` — script-agnostic model: `Corpus`/`Document`/`Token`,
  `Sign`/`SignInventory`, numerals, `Script` plugin registry, `Provenance`.
- `aegean.scripts.lineara` — `aegean.load("lineara")` → **1721** docs, **84**-sign
  inventory, sign→sound map, tokenization; `filter`/`word_frequencies`/`to_dataframe`.
- `aegean.analysis` — Linear A ports (**complete**, parity-tested): numerals +
  KU-RO/PO-TO-KU-RO `balance_check`, wildcard sign patterns, weighted phonetic
  distance, phoneme/word alignment, collocation stats, morphology clustering,
  query engine, tablet-structure detection. Golden fixtures in `tests/fixtures/golden/`.
- `aegean.greek` — Greek NLP: `normalize` (NFC/NFD + Beta Code),
  `tokenize`/`sentences`, `syllabify`, `accentuation`, `prosody`/quantity,
  `meter` scansion (`scan_hexameter`/`scan_pentameter`/`scan_line`: cross-word
  position, correptio, muta-cum-liquida, caesura; synizesis is *not* inferred),
  `phonology` (IPA, Attic+Koine), `lemmatize` (curated accented seed) + `pos`,
  rule-based `morphology` (`analyze`→candidate `Analysis` with case/number/gender
  + tense/voice/mood/person; 1st/2nd decl + common 3rd, thematic verbs; iota-
  subscript dative detection; augment-gated past tenses; accent *not* restored on
  reconstructed lemmas — treebank lexicon is the next step), CLTK-agnostic
  `benchmark` harness (also scores scansion + morphology). `load("greek")` → 5 passages.
- `aegean.ai` / `aegean.translate` — multi-provider LLM layer (Anthropic default,
  OpenAI, xAI, Gemini; SDKs lazy/optional, keys from env, never logged), response
  cache, grounding + prompt-injection wrapping; every output a provenanced,
  exploratory-labeled `ExploratoryResult`. Tested with a fake client + mocked-SDK
  per-provider integration tests.
- `aegean.data` — bundled JSON (Linear A + Greek seeds, **no images**) + `fetch()`
  download-to-cache (sha256-verified, atomic, idempotent, unpacks `extract` tars;
  `PYAEGEAN_<NAME>_URL` override). `fetch("lineara-images")` → **3368** facsimiles
  from the linearaworkbench `lineara-images-v1` release (fetched, never re-hosted;
  © EFA + other rightsholders).

## Next steps (priority order)

1. **Deepen Greek NLP** (measured against the CLTK benchmark): the rule-based
   `morphology` engine and the **Perseus AGDT v2.1 treebank lexicon** are in (opt-in
   `greek.use_treebank()` — downloaded + built in the user cache, CC-BY-SA, **not**
   bundled; gives attested, accented lemmas + full features, rule engine as fallback).
   `pos_tag`/`pos_tags` also use the treebank for attested forms (gold open-class
   tags) when it's active. The benchmark gold set is grown and the harness measures
   the lift (`compare_modes`/`score_pos`/`compare_pos_taggers`): on the gold,
   treebank takes lemma 28%→100% and POS 50%→100% over the baseline. **CLTK
   head-to-head run** (CLTK 2.5.1 + stanza grc Perseus models): on the gold set the
   treebank ties CLTK on lemma (100%/100%) and edges POS (100%/90%) — but the gold is
   small + attested-weighted, so this is coverage, not generalization (a fair,
   in-context, held-out eval would likely favor CLTK on unseen forms). **LSJ glossing landed**: opt-in
   `greek.use_lsj()` fetches the full Perseus LSJ (CC BY-SA 4.0, ~270 MB, cache-only),
   builds a gzipped lemma→entry index, and exposes `gloss`/`lookup` (composes with the
   lemmatizer). **Dependency parsing landed** (baseline): opt-in `greek.use_parser()`
   trains an arc-eager + averaged-perceptron parser (pure Python) on the AGDT and
   exposes `greek.parse()` → `DepTree`; measured ~0.67 UAS / 0.57 LAS on projective
   AGDT, ~0.51 / 0.42 all-text (`greek.evaluate()`); arc-eager is projective-only
   (~31% of AGDT) — honest baseline. **Generalizing POS tagger landed**: opt-in
   `greek.use_tagger()` trains an averaged-perceptron sequence tagger (pure Python) on the
   AGDT that tags *unseen* forms from suffix/shape/accent + context; `greek.evaluate_tagger()`
   reports leakage-free held-out accuracy via the new `aegean.greek.heldout` split/scorer
   (84.4% all / 83.6% unseen on a 90/10 split, vs stanza's 89.1% unseen — within ~5–6 pts,
   and the AGDT is in-training for stanza so it flatters stanza). **Generalizing lemmatizer
   landed**: opt-in `greek.use_lemmatizer()` trains an edit-tree + averaged-perceptron model
   (pure Python, POS-conditioned via the tagger) that lemmatizes *unseen* forms;
   `greek.evaluate_lemmatizer()` reports 84.5% all / 40.3% unseen (vs stanza 62.8% unseen —
   neural lemma still leads on unseen; pyaegean lifts it from the lookup's 0%). Both reuse
   the leakage-free `aegean.greek.heldout` split/scorer. Next: a hand-checked out-of-AGDT
   gold set (the neutral beat-CLTK test the AGDT can't give) and a stronger lemma model.
   (Dactylic meter scansion —
   hexameter + pentameter — landed;
   iambic/lyric meters and synizesis still TODO.)
2. **Deepen the AI layer**: a live smoke test gated behind a secret, streaming,
   and richer grounding (RAG over the corpus/commentary).

## Conventions (do these)

- **Commits/PRs authored as the user**; never put AI/model identity in commit
  messages, code comments, PR text, or any pushed artifact.
- `commit.gpgsign` is `false` in this repo's git config (avoids the managed
  signing server) — leave it off unless signing works in your env.
- **Core has zero hard third-party deps.** `import aegean` is instant and loads
  nothing heavy; `pandas` is the optional `[data]` extra (lazy-imported only inside
  `to_dataframe`), and collocation stats are pure stdlib. The guard is the invariant,
  not a byte count: `scripts/check_footprint.py` enforces import-clean (no heavy
  module in `sys.modules` after import), import-fast, and a code+JSON-only wheel.
  Never bundle large/binary assets — corpora and trained models fetch to cache via
  the `fetch()` layer.
- Every **exploratory** method (cross-linguistic distance, morphology clustering,
  accounting reconciliation, decipherment, AI readings) carries its caveat in the
  docstring and is labeled unverified at point of use.
- New scripts are **plugins**: subclass `core.Script`, `register()` it, and
  register a loader via `core.corpus.register_loader`. The core never imports
  scripts (no cycles); `aegean/__init__` imports `scripts` to register.
- Port behavior **faithfully** from the workbench and assert against shared golden
  values so the Python port can't silently diverge.

## Run it

```bash
pip install -e ".[dev]"
pytest                 # 306 passing (1 skipped)
ruff check src tests
mypy                   # clean (enforced in CI)
python -m build && python -m twine check dist/*
python scripts/check_footprint.py --wheel "dist/*.whl"   # wheel = code + JSON only
python scripts/check_footprint.py                        # import-clean + import-fast
```

## Layout

`src/aegean/{core,scripts/{lineara,greek},analysis,greek,translate,ai,io,data,
adapters,integrations}`. Bundled data: `src/aegean/data/bundled/`. Tests in
`tests/`; parity fixtures in `tests/fixtures/golden/`. Design: `docs/PLAN.md`.
