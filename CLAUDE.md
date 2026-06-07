# CLAUDE.md — pyaegean working notes (read me first)

This file is auto-loaded as context. It's the handoff from the session that
bootstrapped the package. **Full approved design is in `docs/PLAN.md` — read it.**

## What pyaegean is

The *definitive, specialist* Python toolkit for **Ancient Greek** — alphabetic
Greek (Archaic→Koine) **and** the Aegean syllabic scripts (Linear A/B, Cypriot).
Strategic goal: **match-or-beat CLTK on Greek specifically** (CLTK is a
generalist; we go deep on Greek and add Linear A/B tooling, translation, and
multi-provider AI). CLTK is a **benchmark target, never a dependency.** "No
competing package has better Greek features" is the bar.

## How this repo got here

Built in a sandbox scoped to the *workbench* repo (no push access to pyaegean),
then handed off as a tarball. The first commit is already in `.git` (authored as
Ryan Pavlicek). `commit.gpgsign` is set to `false` in this repo's git config to
avoid the managed signing server — leave it off unless signing works in your env.
**First task in this session: confirm install + tests, then `git push` to
`origin` if it isn't already pushed.**

## Current state — v0.1 *foundation* (first vertical slice; NOT all of v0.1)

DONE and tested (217 passing tests):
- `aegean.core` — script-agnostic model: `Corpus`, `Document`, `Token`/`TokenKind`,
  `Sign`, `SignInventory`, numerals, `Script` plugin registry, `Provenance`.
- `aegean.scripts.lineara` — Linear A fully wired: `aegean.load("lineara")` →
  **1721** docs, **84**-sign inventory, sign→sound map, tokenization.
  `.filter()`, `.word_frequencies()`, `.to_dict()`, `.to_dataframe(level=...)`.
- `aegean.analysis` — ports w/ parity tests: `numerals` + KU-RO/PO-TO-KU-RO
  `balance_check` (accounting reconciliation), wildcard sign-pattern matching,
  weighted phonetic distance + configurable phonetic class schemes,
  phoneme/word-level alignment, collocation statistics (Yates chi-squared, G²
  log-likelihood, chi-squared p-value, two-sided Fisher's exact, Wilson/PMI
  intervals; scipy lazy), and productive-suffix morphological clustering.
  Golden fixtures in `tests/fixtures/golden/algorithms.json`; property tests
  mirror the workbench `*.properties.test.ts`. Plus the **query engine**
  (`queryEngine.ts` → field registry, inscription/word predicates, AND/OR/NOT,
  `eval_query`/`run_query`) and **structure detection** (`TabletStructure.tsx`
  `heuristicKey` → accounting/libation/list/text classifier), both with parity
  tests.
- `aegean.greek` — Greek NLP pipeline (v0.1 start): `normalize` (NFC/NFD +
  Beta Code ↔ Unicode), `tokenize`/`sentences`, `syllabify` (rule-based incl.
  diphthongs + muta-cum-liquida), `accentuation` (oxytone/…/perispomenon),
  `prosody` (syllable quantity heavy/light/common), `phonology` (reconstructed
  IPA, Attic + Koine), baseline `lemmatize` (bundled seed table), baseline `pos`
  (closed-class lexicon + suffix heuristic), and a `benchmark` harness scoring
  the pipeline vs a bundled gold set (CLTK-agnostic comparison hook).
  `aegean.scripts.greek` registers
  the Greek `Script` (+ `nlp` capability) and a bundled sample corpus →
  `aegean.load("greek")` (5 public-domain Archaic→Koine passages).
- `aegean.data` — bundled-JSON access (Linear A + Greek seeds, **no images**) +
  `fetch()` download-to-cache: sha256-verified, atomic, idempotent, with a
  `PYAEGEAN_<NAME>_URL` env override (graceful `DataNotAvailableError`).
- `aegean.ai` — multi-provider AI layer (v0.2): `LLMClient` ABC + adapters
  (Anthropic default, OpenAI, xAI Grok, Gemini; SDKs lazy/optional, keys from
  env, never logged), `get_client()`, a sha256 `ResponseCache`, grounding +
  prompt-injection wrapping, and capabilities (translate/gloss/decipher/
  nlp_assist/ask/summarize) — every output an exploratory-labeled, provenanced
  `ExploratoryResult`. Model is configurable (arg → `<PROVIDER>_MODEL` env →
  default). `aegean.translate` is the hybrid lexicon+LLM front end.

The Linear A analysis ports are **complete** (phonetic distance + alignment,
morphology clustering, collocation, query engine, structure detection). The
Greek track has its first vertical slice (corpus + NLP stages above). The v0.2
AI layer + translation foundation is in (provider adapters, grounding, caching,
exploratory labeling), unit-tested with a fake client (no live keys).

NOT done yet (next steps, priority order):
1. **Deepen Greek NLP** toward "beats CLTK": real lemmatizer/morphology (Morpheus
   / treebank-derived), POS, dependency parse, full meter scansion, LSJ; download
   the full First1KGreek/Perseus corpus and grow the gold set. (DONE so far:
   normalize/betacode, tokenize, syllabify, accent, prosody/quantity, phonology/
   IPA, baseline lemmatize, and the CLTK benchmark harness.)
2. **Pin the `lineara-images` release URL** in `src/aegean/data/__init__.py`
   (still empty — no workbench release exists yet; the imagery isn't
   redistributable, so the owner must publish a mirror first, then pin URL+sha).
   Until then `PYAEGEAN_LINEARA_IMAGES_URL` lets a user fetch from their own.
3. **Deepen the AI layer** (foundation DONE): wire real provider calls against
   recorded/mocked HTTP for an integration test, a tiny live smoke gated behind
   a secret, streaming, and richer grounding (RAG over the corpus/commentary).

## Conventions (do these)

- **Commits/PRs authored as the user**; never put AI/model identity in commit
  messages, code comments, PR text, or any pushed artifact.
- Heavy deps (`numpy`/`pandas`/`scipy`) are **lazy-imported inside functions**;
  `import aegean` stays instant and dep-light. Keep it that way.
- **Never bundle large/binary assets** — that's the whole point of the `fetch()`
  download-to-cache layer. Wheel stays < 3 MB (CI guards it).
- Every **exploratory** method (cross-linguistic distance, morphology clustering,
  accounting reconciliation, decipherment, AI readings) carries its caveat in the
  docstring and is labeled unverified at point of use. The Linear A material is
  undeciphered — never present analysis as ground truth.
- New scripts are **plugins**: subclass `core.Script`, `register()` it, and
  register a corpus loader via `core.corpus.register_loader`. The core never
  imports scripts (no cycles); `aegean/__init__` imports `scripts` to register.
- Port behavior **faithfully** from the workbench and assert against shared
  golden values so the Python port can't silently diverge.

## Run it

```bash
pip install -e ".[dev]"
pytest                                   # 217 passing
python -c "import aegean; print(len(aegean.load('lineara')))"   # 1721
ruff check src tests
mypy                                     # clean (enforced in CI)
python -m build && python -m twine check dist/*   # wheel must be < 3 MB
```

## Layout

`src/aegean/{core,scripts/{lineara,greek},analysis,greek,translate,ai,io,data,
adapters,integrations}`. Bundled data: `src/aegean/data/bundled/lineara/*.json`.
Tests in `tests/`; parity fixtures in `tests/fixtures/golden/`. Design: `docs/PLAN.md`.
