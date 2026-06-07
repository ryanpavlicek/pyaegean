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

DONE and tested (18 passing tests):
- `aegean.core` — script-agnostic model: `Corpus`, `Document`, `Token`/`TokenKind`,
  `Sign`, `SignInventory`, numerals, `Script` plugin registry, `Provenance`.
- `aegean.scripts.lineara` — Linear A fully wired: `aegean.load("lineara")` →
  **1721** docs, **84**-sign inventory, sign→sound map, tokenization.
  `.filter()`, `.word_frequencies()`, `.to_dict()`, `.to_dataframe(level=...)`.
- `aegean.analysis` — ports w/ parity tests: `numerals` + KU-RO/PO-TO-KU-RO
  `balance_check` (accounting reconciliation), wildcard sign-pattern matching.
- `aegean.data` — bundled-JSON access (≈590 KB in-wheel, **no images**) +
  `fetch()` download-to-cache (graceful `DataNotAvailableError`).

NOT done yet (next steps, priority order):
1. **Greek start** (`aegean.greek` + `aegean.scripts.greek`): corpus loader
   (First1KGreek/Perseus subset) + first NLP stages — normalize/betacode,
   tokenize, syllabify, accentuation, baseline lemmatize (open-data seed).
2. **Remaining Linear A analysis ports** with golden-fixture parity:
   phonetic distance + alignment, morphology clustering, collocation (scipy),
   query engine, structure detection. Source: workbench `src/lib/*.ts` + its
   `*.test.ts` (extract golden JSON into `tests/fixtures/golden/`).
3. **Pin the `lineara-images` release URL** in `src/aegean/data/__init__.py`
   (currently empty → `fetch` reports "no pinned URL"). Pin a
   `ryanpavlicek/linearaworkbench` release tag for the ~500 MB facsimile mirror.
4. **Make CI green**: `ruff`, `mypy --strict` (NOT yet run — pandas lazy imports
   may need fixes; mypy step is `continue-on-error` until clean — then flip it),
   `pytest`, build + wheel-size guard.
5. **v0.2**: AI layer (`aegean.ai`, multi-provider: Anthropic default/latest
   Claude, OpenAI, Grok, Gemini) — translate/gloss/decipher/nlp-assist/ask —
   grounded, all output labeled exploratory; + `aegean.translate`.

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
pytest                                   # 18 passing
python -c "import aegean; print(len(aegean.load('lineara')))"   # 1721
ruff check src tests
mypy                                     # not yet verified clean — expect to fix
python -m build && python -m twine check dist/*   # wheel must be < 3 MB
```

## Layout

`src/aegean/{core,scripts/{lineara,greek},analysis,greek,translate,ai,io,data,
adapters,integrations}`. Bundled data: `src/aegean/data/bundled/lineara/*.json`.
Tests in `tests/`; parity fixtures in `tests/fixtures/golden/`. Design: `docs/PLAN.md`.
