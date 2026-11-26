# CLI: AI, MCP & Troubleshooting

Reference for key-gated AI commands (`aegean ai …`), the MCP server
(`aegean-mcp`), common CLI troubleshooting, and shell recipes.

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [CLI: Corpora, Library, Analysis & Data](CLI-Corpora) · [CLI: Greek NLP & Review](CLI-Greek) · [CLI: Biblical & Koine Greek](CLI-Bible)

---

## AI — `aegean ai …` (exploratory, key-gated)

Every output from `aegean ai` is **exploratory**: a labeled model hypothesis
paired with its grounding evidence, never a citable fact or decipherment. Each
command requires a provider SDK extra (such as
`pip install "pyaegean[anthropic]"`) and, for hosted providers, that provider's
API key in the environment. The `local` provider connects to a local server
(Ollama, LM Studio, llama.cpp) and requires no key. Without a key, hosted
commands exit `1` with an error message and make no network request.

```bash
aegean ai providers
# anthropic
# gemini
# grok
# local
# openai
# openrouter
```

Commands (all take `--provider` and `--model`; most take `--trace`):

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"                      # grounded hybrid translation
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --mode full          # + rare-word glosses in grounding
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --greek-backend neural --verify --trace
aegean ai translate "KU-RO 130" --script lineara              # exploratory (undeciphered)
aegean ai gloss "μῆνιν ἄειδε θεά"                             # interlinear word-by-word gloss
aegean ai summarize "ἐν ἀρχῇ ἦν ὁ λόγος" --corpus nt          # grounded summary
aegean ai hypotheses "A-TA-I-*301-WA-JA" --corpus lineara     # exploratory decipherment hypotheses
aegean ai ask "What is KU-RO?" --corpus lineara --trace       # answer from supplied grounding
aegean ai extract "OLE S 1" --fields commodity,amount         # structured JSON for jq
aegean ai eval --provider anthropic                           # grounding-fidelity eval
```

`--corpus NAME` grounds the prompt on that corpus's frequent words. `--trace`
prints the grounding provenance beneath the answer, grouped by source (local
corpus, lexicon, or analysis facts). `extract` always outputs JSON for piping to
`jq`.

For Greek, `translate` grounds on local, provisional **morphology** by default
(`--mode morphology`): lemma, part of speech, voice, case roles, and clause
structure, with rare words flagged and no auto-selected dictionary senses.
`--mode full` adds concise, rarity-gated glosses from active dictionaries;
`--mode lemma` selects legacy lemma+LSJ grounding; `--mode none` sends the text
ungrounded. Grammatical predictions and dictionary matches can be wrong in
context.

`--verify` runs a two-call check: an ungrounded draft first, then a second call
checking that draft against full grounding. Local analysis cannot bias the
initial draft, though an analysis error can mislead the check. Output remains
model-generated and carries no guarantee of accuracy or independent scholarly
verification.

With Greek `--verify`, `--check-policy clauses` requests checks on roles,
negation, qualifications, and speech acts. JSON and traces preserve exact
quotations, model findings, and local literal alignment/coverage gaps; alignment
does not verify meaning. `--lexical-evidence contextual` supplies bounded
excerpts and alternative senses from active dictionaries with provenance and
omissions (requires Greek `full`/`lemma` mode or `--verify` with glosses
enabled). Defaults remain `--check-policy standard` and
`--lexical-evidence concise`. Pass repeatable `--dictionary ID` flags (for
example `--dictionary middle-liddell --dictionary cunliffe`) to activate hosted
dictionaries for that command (fetching their cache on first use). Pass
`--source-context TEXT` or `--source-context-file PATH` to supply surrounding
lines separately from the target passage, and `--max-tokens N` (default `2048`)
to set the per-call output token limit.

`--greek-backend default|baseline|neural` selects the Greek analysis backend:
`default` uses the module-level facade, `baseline` creates an isolated
zero-dependency analyzer, and `neural` creates an isolated joint-model analyzer
for that run. With `neural`, `--greek-variant default|fast|compact|balanced`
selects the runtime artifact; only `default` is currently available, and
reserved labels exit with an error before contacting the translation provider.
Full runtime configuration appears in `--trace` and JSON provenance; the prompt
receives a compact backend, availability, and coverage summary.
`--greek-long-input strict|partial|windowed` (default `strict`) controls neural
long-input handling. `--grounding-failure best-effort|strict` controls required
local analysis failures: `best-effort` retains available evidence and records
degradation, while `strict` stops before any provider call. Optional
dictionaries and rarity data remain optional. Because `morphology` and `full`
request dependency analysis, pair an isolated `baseline` run with `best-effort`,
or use `neural` for a strict morphology/parse contract.

### Reading styles and audit output

`--style annotated` (default) displays the translation alongside model-reported
uncertainty and change notes. `--style concise` prints the translation and the
note/change counts while retaining full details in JSON and `--trace`. Wording
and notes vary by model and run. The default `--provider` is `anthropic`;
without its API key, the command exits `1` on stderr:

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"
# aegean: no API key for 'anthropic'; set $ANTHROPIC_API_KEY or pass api_key=   [stderr, exit 1]
```

```bash
# Requires the provider extra and its API key:
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --provider openrouter --style annotated
aegean ai translate "μῆνιν ἄειδε θεά" --provider openrouter --mode full --style concise
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --provider openrouter --verify --style concise --trace
```

For structured responses, `text` holds the translation alone, while `data` keeps
`translation`, `uncertainties`, and `changes` (`before`, `after`, `reason`,
`evidence`, all model-reported). `raw_response` preserves the exact response and
`format_status` reports its schema status, not linguistic accuracy. Malformed or
incomplete responses are kept verbatim with an explicit warning that structured
audit fields are unavailable; no extra format-repair calls are made.

With `--verify`, `draft` stores the initial result, notes, and provenance.
Omitting a draft uncertainty from final notes does not mean it was resolved. For
consistent structured draft/final pairs, `text_changed` compares exact wording
and `change_report_status` flags unreported text differences without assessing
meaning or quality. Raw or inconsistent drafts are marked `not_comparable`.

Baseline coverage and degraded grounding are recorded explicitly. Activating
neural analysis provides contextual predictions and a dependency parse, though
neither is authoritative.

**Saving outputs with provenance.** `translate`, `gloss`, `summarize`,
`hypotheses`, `ask`, and `extract` accept `--output/-o`. `.json` files store the
text, provenance, grounding evidence, and (for `translate`) all audit fields and
checking drafts. Translation `.txt` files append the full audit trace to the
labeled text even under `--style concise`; other `.txt` exports append the trace
when `--trace` is passed. Saved files retain the exploratory label on disk.
(`ai eval -o` writes `.json`, `.csv`, or `.txt`.)

```bash
aegean ai translate "μῆνιν ἄειδε θεά" --verify --style concise -o translation.json
aegean ai gloss "μῆνιν ἄειδε θεά" -o gloss.json        # text + provenance + grounding
aegean ai ask "What is KU-RO?" --corpus lineara -o answer.txt
```

In Python, `ExploratoryResult.to_dict()`, `.to_json(path)`, and
`ExploratoryResult.from_dict(data)` round-trip results with label and grounding
intact. See [AI Layer](AI-Layer) for the grounding design and
[Limitations](Limitations) for scope boundaries.

---

## MCP server — `aegean-mcp`

> Full reference: [MCP](MCP).

`aegean-mcp` (installed by the `[mcp]` extra) exposes pyaegean's read and
analysis surface to AI agents (Claude Code and other MCP clients) over stdio.

```bash
pip install "pyaegean[mcp]"
aegean-mcp                # serve the read/analysis tools over stdio
```

It exposes **29 read/analysis tools** across corpora, unified library discovery,
Greek NLP, and Biblical, Septuagint, and Patristic Greek (see [MCP](MCP) for the
complete tool table). Corpora and works are addressed by registry name or
catalogue work id only, never by filesystem path, and domain misses return a
structured JSON error with a did-you-mean hint.

---

## Troubleshooting

Three error shapes account for most CLI failures. Each prints one line on stderr
with exit code `1` and names the fix.

**1. Unknown name.** Corpus ids, dataset names, and query fields suggest the
nearest valid name:

```bash
aegean info linera
# aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (…), a Greek work id like tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin

aegean data fetch grc-jiont
# aegean: unknown dataset 'grc-jiont' — did you mean 'grc-joint'? (`aegean data list` shows all 47)
```

Use the suggested name or inspect valid names with `aegean data list` or
`aegean query CORPUS --fields`.

**2. Missing optional extra.** Features with third-party dependencies live
behind extras and print the exact `pip install` command when missing:

```bash
aegean tui
# aegean: the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'
```

`plot` (`[viz]`), `export -f parquet` (`[parquet]`), neural flags (`[neural]`),
and AI providers (`[anthropic]`, `[openai]`, `[gemini]`) behave the same way.
`aegean doctor` lists every extra's status and install command.

**3. Missing local data or API key.** Commands that expect cached data or a
credential state the exact remediation:

```bash
aegean data remove linearb-corpus
# aegean: dataset 'linearb-corpus' is not downloaded; `aegean data list` shows what is

aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"
# aegean: no API key for 'anthropic'; set $ANTHROPIC_API_KEY or pass api_key=
```

`linearb-corpus` has no default remote source: `aegean data fetch linearb`
prints the available options (fetch DAMOS, browse LiBER online, or import a
licensed export). If an interrupted download leaves a partial file,
`aegean doctor` flags it and prints the `aegean data remove` command to clear
it.

---

## Recipes

Reconcile Linear A accounts and filter for discrepancies:

```bash
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json
```

Lemmatize a file of Greek, one lemma per line:

```bash
cat chapter.txt | aegean greek lemmatize - --json | jq -r '.[].lemma'
```

Scan a poem line by line, printing only lines that scan:

```bash
while read -r line; do aegean greek scan "$line" --json 2>/dev/null | jq -r .pattern; done < poem.txt
```

Map find-sites and cite the filtered subset:

```bash
aegean geo lineara --output sites.geojson
aegean cite lineara --site "Zakros" --style bibtex >> paper.bib
```

Build one searchable SQLite database from Greek work ids and append another work
later:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db     # Iliad + Odyssey (see Greek Works and Books for ids)
aegean db add tlg0011.tlg002 -o homer.db                     # add Sophocles' Antigone later
aegean db search homer.db μῆνιν --limit 3
```

Save a query subset once and reuse it in downstream commands:

```bash
aegean query lineara --where "site-is=Zakros" -o zakros.json
aegean keyness zakros.json --reference lineara --top 5 -o zakros-keyness.csv
```

More pipelines appear on [Recipes](Recipes).

---

## Notes and limits

- **The AI layer is exploratory.** Translations, glosses, and hypotheses for
  undeciphered material are labeled model output with grounding, not findings.
  Linear A and Cypro-Minoan remain undeciphered. See [Limitations](Limitations).
- **Heavy commands download on first use.** `--neural`, `greek work`,
  `greek eval`, `gloss`, and hosted corpora fetch data into the local cache on
  first use (with a stderr notice) and run offline afterward. Pre-fetch with
  `aegean library install` or `aegean data fetch` before going offline.
- **`--json` is the scripting contract.** Parse `--json` output with `jq`, not
  formatted terminal tables. `--limit`/`--top` cap JSON lists too (`0` lifts the
  cap); payloads carrying totals (`matched`) keep the untruncated total.
- **Meter and accuracy bounds.** Lyric meters beyond the fixed Aeolic templates
  are out of scope, and trainable backends have measured accuracy limits: see
  [Meters](Meters) and [Limitations](Limitations#measured-accuracy-boundaries).

For the one-page index of every command and flag, see
[CLI Cheatsheet](CLI-Cheatsheet).
