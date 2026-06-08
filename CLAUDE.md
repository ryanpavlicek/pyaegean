# CLAUDE.md — pyaegean working notes

Auto-loaded at session start. Strategic design of record: `docs/PLAN.md`.

## What pyaegean is

The *definitive, specialist* Python toolkit for **Ancient Greek** — alphabetic
Greek (Archaic→Koine) and the Aegean syllabic scripts (Linear A/B, Cypriot).
Goal: **match-or-beat CLTK on Greek specifically** (CLTK is a benchmark target,
**never a dependency**). The Linear A material is undeciphered — never present
analysis as ground truth.

## Current state — v0.1 foundation (247 tests passing)

- `aegean.core` — script-agnostic model: `Corpus`/`Document`/`Token`,
  `Sign`/`SignInventory`, numerals, `Script` plugin registry, `Provenance`.
- `aegean.scripts.lineara` — `aegean.load("lineara")` → **1721** docs, **84**-sign
  inventory, sign→sound map, tokenization; `filter`/`word_frequencies`/`to_dataframe`.
- `aegean.analysis` — Linear A ports (**complete**, parity-tested): numerals +
  KU-RO/PO-TO-KU-RO `balance_check`, wildcard sign patterns, weighted phonetic
  distance, phoneme/word alignment, collocation stats, morphology clustering,
  query engine, tablet-structure detection. Golden fixtures in `tests/fixtures/golden/`.
- `aegean.greek` — Greek NLP (v0.1 slice): `normalize` (NFC/NFD + Beta Code),
  `tokenize`/`sentences`, `syllabify`, `accentuation`, `prosody`/quantity,
  `meter` scansion (`scan_hexameter`/`scan_pentameter`/`scan_line`: cross-word
  position, correptio, muta-cum-liquida, caesura; synizesis is *not* inferred),
  `phonology` (IPA, Attic+Koine), baseline `lemmatize`+`pos`, CLTK-agnostic
  `benchmark` harness (scores scansion too). `aegean.load("greek")` → 5 passages.
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

1. **Deepen Greek NLP** toward beating CLTK: real lemmatizer/morphology (Morpheus
   / treebank-derived), POS, dependency parse, LSJ; pull the full
   First1KGreek/Perseus corpus and grow the gold set. (Dactylic meter scansion —
   hexameter + pentameter — landed; iambic/lyric meters and synizesis still TODO.)
2. **Deepen the AI layer**: a live smoke test gated behind a secret, streaming,
   and richer grounding (RAG over the corpus/commentary).

## Conventions (do these)

- **Commits/PRs authored as the user**; never put AI/model identity in commit
  messages, code comments, PR text, or any pushed artifact.
- `commit.gpgsign` is `false` in this repo's git config (avoids the managed
  signing server) — leave it off unless signing works in your env.
- Heavy deps (`numpy`/`pandas`/`scipy`) are **lazy-imported inside functions** so
  `import aegean` stays instant. Wheel stays **< 3 MB** (CI guards it); never
  bundle large/binary assets — use the `fetch()` layer.
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
pytest                 # 230 passing
ruff check src tests
mypy                   # clean (enforced in CI)
python -m build && python -m twine check dist/*   # wheel must be < 3 MB
```

## Layout

`src/aegean/{core,scripts/{lineara,greek},analysis,greek,translate,ai,io,data,
adapters,integrations}`. Bundled data: `src/aegean/data/bundled/`. Tests in
`tests/`; parity fixtures in `tests/fixtures/golden/`. Design: `docs/PLAN.md`.
