# CLI: AI, MCP & Troubleshooting

Reference for key-gated AI commands (`aegean ai …`), the MCP server (`aegean-mcp`), common CLI
recipes, and troubleshooting.

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [CLI: Corpora, Analysis & Data](CLI-Corpora) · [CLI: Greek NLP & Review](CLI-Greek) · [CLI: Biblical & Koine Greek](CLI-Bible)

---

## AI — `aegean ai …` (exploratory, key-gated)

The generative layer. **Every result here is exploratory**: a labeled model
hypothesis carrying its grounding evidence, never a citable fact, and never a
"decipherment." It needs a provider SDK (an extra such as
`pip install "pyaegean[anthropic]"`) and, for a hosted provider, that provider's
API key in your environment; the `local` provider instead points at a running local
server (Ollama, LM Studio, llama.cpp) and needs no key. Without a key, a
hosted-provider command exits `1` with a clear message: it never
silently calls out.

```bash
aegean ai providers
# anthropic
# gemini
# grok
# local
# openai
# openrouter
```

The commands (each takes `--provider` / `--model`, and most take `--trace`):

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"                      # grounded hybrid translation
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --mode full          # + rare-word glosses in the grounding
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --greek-backend neural --verify --trace
aegean ai translate "KU-RO 130" --script lineara              # exploratory (undeciphered!)
aegean ai gloss "μῆνιν ἄειδε θεά"                             # interlinear word-by-word gloss
aegean ai summarize "ἐν ἀρχῇ ἦν ὁ λόγος" --corpus nt          # short, grounded summary
aegean ai hypotheses "A-TA-I-*301-WA-JA" --corpus lineara     # cautious decipherment hypotheses
aegean ai ask "What is KU-RO?" --corpus lineara --trace       # answer strictly from grounding
aegean ai extract "OLE S 1" --fields commodity,amount         # structured JSON, ready for jq
aegean ai eval --provider anthropic                           # grounding-fidelity eval
```

`--corpus NAME` grounds the answer on that corpus's frequent words. `--trace`
prints the grounding provenance under the answer: the local corpus / lexicon /
analysis facts the model was given, grouped by source, so you can audit exactly
what it was (and wasn't) told. `extract` always prints JSON, so it pipes straight
into `jq`. For Greek, `translate` grounds with local, provisional **morphology** by default
(`--mode morphology`): lemma, part of speech, voice, case roles, and the clause skeleton,
with rare words flagged but no auto-selected dictionary senses. `--mode full` adds concise,
rarity-gated glosses from the available dictionary cascade; `--mode lemma` is the
legacy lemma+LSJ grounding, and `--mode none` sends the
text ungrounded. Grammatical predictions and dictionary matches can be wrong in
context. `--verify` is optional: it generates an ungrounded draft, then asks the
same provider to check it against full grounding in a second call. The analysis
cannot bias the initial draft, but a wrong analysis can mislead the check. This
remains model output, with no guarantee of improvement or independent scholarly
verification.

`--check-policy clauses` with Greek `--verify` requests explicit checks of roles,
negation, qualifications and speech acts. JSON and traces retain exact quotations,
model findings and local literal alignment/coverage issues; alignment does not
verify meaning. `--lexical-evidence contextual` selects bounded excerpts and
alternative senses from already active dictionaries, with provenance and omissions.
It requires Greek full/lemma mode or `--verify`, with glosses enabled. The defaults
remain `--check-policy standard --lexical-evidence concise`.
Use repeatable `--dictionary ID` options to activate hosted dictionaries for this
command, for example `--dictionary middle-liddell --dictionary cunliffe`. Explicit
activation may fetch the cache on first use; grounding itself does not activate it.
Pass `--source-context TEXT` or `--source-context-file PATH` to supply surrounding lines
separately from the target passage, and `--max-tokens N` (default `2048`) to set the
per-call output token allowance.

`--greek-backend default|baseline|neural` makes the Greek analysis owner explicit.
With `neural`, add `--greek-variant default|fast|compact|balanced` to select its runtime
artifact. Only `default` is currently available; a reserved label fails without fallback and
before the translation provider is created.
`default` preserves the module-level facade, `baseline` creates an isolated
zero-dependency analyzer, and `neural` creates an isolated joint-model analyzer for that
run. The complete runtime configuration appears in `--trace` and JSON provenance;
the provider receives a compact backend, availability, and coverage summary as
evidence. `--greek-long-input strict|partial|windowed` controls neural long-input
handling separately; the default is strict. `--grounding-failure best-effort|strict`
controls required local analysis failures: best-effort keeps available evidence and records the degradation;
strict stops before any provider call. Optional dictionaries and rarity data remain
optional. Because morphology/full request a dependency analysis, an isolated baseline is
normally paired with best-effort; use neural for a strict morphology/parse contract.

#### Reading styles and the checking audit

`--style annotated` (default) shows the final translation with model-reported
uncertainty and change notes. `--style concise` keeps the reading short and shows
how many notes and changes were reported; their details remain in JSON and
`--trace`. The provider's wording and notes vary by run and model. The default
`--provider` is `anthropic`; each hosted provider reads its own key from the
environment, and without one the command stops on one line:

```bash
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"
# aegean: no API key for 'anthropic'; set $ANTHROPIC_API_KEY or pass api_key=   [stderr, exit 1]
```

```bash
# Requires the provider extra and its key:
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --provider openrouter --style annotated
aegean ai translate "μῆνιν ἄειδε θεά" --provider openrouter --mode full --style concise
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος" --provider openrouter --verify --style concise --trace
```

For a structured response, `text` contains the translation only, while `data`
retains `translation`, `uncertainties`, and `changes`. Each reported change has
`before`, `after`, `reason`, and `evidence`; those are model reports, not validated
scholarship. `raw_response` keeps the exact response and `format_status` describes
its shape, not linguistic accuracy. A malformed or incomplete response remains
verbatim with an explicit warning that separate audit information is unavailable;
the toolkit makes no extra format-repair calls.

With `--verify`, the original result, notes, and provenance remain in `draft`.
Omitting a draft uncertainty from the final notes does not establish its
resolution. For consistent structured draft/final pairs, `text_changed` compares
exact wording, and `change_report_status` flags a text difference the model did
not report. This comparison assesses neither meaning nor quality. Raw or
inconsistent drafts are `not_comparable`, rather than treating removed commentary
as a changed translation.

Baseline coverage and degraded grounding are reported explicitly. Activating
neural analysis gives contextual predictions and a dependency parse, without
making either authoritative.

**Save the output, label and all.** `translate`, `gloss`, `summarize`, `hypotheses`,
`ask`, and `extract` take `--output/-o`. A `.json` file carries the text plus its provenance
and grounding evidence. Translation JSON also keeps all audit fields and the
checking draft; translation `.txt` files append the full audit trace to the
labeled text, including when concise style is selected. Other `.txt` results
contain labeled text, plus the trace when `--trace` is requested. The exploratory label
stays attached on disk: a saved result never loses the "this is a hypothesis, not
a finding" framing. (`ai eval` takes `--output/-o` too, saving its case table as
`.json`, `.csv`, or `.txt`.)

```bash
aegean ai translate "μῆνιν ἄειδε θεά" --verify --style concise -o translation.json
aegean ai gloss "μῆνιν ἄειδε θεά" -o gloss.json        # text + provenance + grounding
aegean ai ask "What is KU-RO?" --corpus lineara -o answer.txt
```

In Python the same lives on `ExploratoryResult`: `.to_dict()`, `.to_json(path)`,
and `ExploratoryResult.from_dict(data)` round-trip a result through disk with its
label and grounding intact. The full design and the meaning of "grounded" are on
[AI Layer](AI-Layer); the hard limits are on [Limitations](Limitations).

---

## MCP server — `aegean-mcp`

> Full reference: the [MCP server](MCP) page. This section is a quick tour.

A separate console script (the `[mcp]` extra) that exposes the toolkit to AI
agents (Claude Code and other MCP clients) over stdio, so an agent can use
pyaegean without writing Python.

```bash
pip install "pyaegean[mcp]"
aegean-mcp                # serve the read/analysis tools over stdio
```

It offers twenty-three read/analysis tools. Corpora: `list_corpora`, `corpus_info`,
`show_document`, `search_signs` (wildcard sign patterns), `balance_accounts`
(accounting reconciliation), `query_corpus` (the compound query engine),
`cite_corpus` (plain/BibTeX/APA, exact subsets included), `geo_sites` (find-site
coordinates and per-site word attestations), and `data_status` (the local data
store, read-only). Greek: `greek_pipeline`, `greek_scan` (verse scansion),
`greek_catalog` (the ~1,800-work discovery catalogue), `greek_work` (load a
work's text by catalogue id; the first use fetches it into the local data store,
cached and offline after), `greek_gloss` (the registry dictionaries), `greek_explain` (each token's lemma
evidence class in plain language), `corpus_diagnose` (the corpus health report),
and `koine_gloss` (the bundled Dodson NT lexicon). Biblical & Koine: `biblical_strongs`,
`biblical_word_study`, `biblical_psalm`, `biblical_nomina_sacra`, `biblical_catalog`,
and `biblical_lxx`. Corpora and works are addressed
by registry name or catalogue work id only (never a filesystem path), and a
domain miss returns a structured error with a did-you-mean hint.

---

## When something goes wrong

Three error shapes cover most first-week trouble. All of them are one line on
stderr with exit code `1`, and each names its own fix. (The messages below are
real runs.)

**1. A name pyaegean does not recognise.** Corpus ids, dataset names, and
query fields all answer a typo with the nearest real name:

```bash
aegean info linera
# aegean: unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? expected a registered id (cypriot, cyprominoan, damos, ddbdp, edh, greek, igcyr, iip, iospe, isicily, lineara, linearb, nt, sigla), a Greek work id like tlg0012.tlg001, a path to a .json or .db corpus, or '-' for JSON on stdin

aegean data fetch grc-jiont
# aegean: unknown dataset 'grc-jiont' — did you mean 'grc-joint'? (`aegean data list` shows all 32)
```

The fix is in the message: take the suggestion, or list the valid names
(`aegean data list`, `aegean query CORPUS --fields`).

**2. A missing optional extra.** The zero-dependency core is a supported
install, so features with heavier needs live behind extras, and reaching one
you have not installed stops with the exact `pip install` line:

```bash
aegean tui
# aegean: the TUI needs the [tui] extra — install it with: pip install 'pyaegean[tui]'
```

`plot` (`[viz]`), `export -f parquet` (`[parquet]`), the neural flags
(`[neural]`), and the AI providers (`[anthropic]` and friends) all guard the
same way. Run the printed install line and re-run your command;
`aegean doctor` lists every extra's state with its install line.

**3. Data (or a key) that is not on this machine.** Most fetched corpora
download themselves on first use, so the messages you actually see are about
the store's state, or a missing credential, each naming the next step:

```bash
aegean data remove linearb-corpus
# aegean: dataset 'linearb-corpus' is not downloaded; `aegean data list` shows what is

aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"
# aegean: no API key for 'anthropic'; set $ANTHROPIC_API_KEY or pass api_key=
```

One dataset is special: `linearb-corpus` has no generic download, so
`aegean data fetch linearb` prints a short option list instead of fetching
(fetch DAMOS, browse LiBER online, or import your own licensed export). If a
download was interrupted, `aegean doctor` spots the leftover partial file and
names the `aegean data remove` that reclaims it.

---

## Recipes

Reconcile every Linear A account and keep only the failures:

```bash
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json
```

Lemmatize a file of Greek, one lemma per line:

```bash
cat chapter.txt | aegean greek lemmatize - --json | jq -r '.[].lemma'
```

Scan a poem line by line, keeping only the lines that scan:

```bash
while read -r line; do aegean greek scan "$line" --json 2>/dev/null | jq -r .pattern; done < poem.txt
```

Map a word's distribution and cite the subset you used:

```bash
aegean geo lineara --output sites.geojson
aegean cite lineara --site "Zakros" --style bibtex >> paper.bib
```

Build one searchable database of all of Homer straight from work ids, then keep
growing it: no Python anywhere:

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db     # Iliad + Odyssey (see Greek Works and Books for ids)
aegean db add tlg0011.tlg002 -o homer.db                     # add Sophocles' Antigone later
aegean db search homer.db μῆνιν --limit 3
```

Save a query subset once, reuse it everywhere:

```bash
aegean query lineara --where "site-is=Zakros" -o zakros.json
aegean keyness zakros.json --reference lineara --top 5 -o zakros-keyness.csv
```

More worked pipelines are on [Recipes](Recipes).

---

## Notes and limits

- **The AI layer is exploratory.** Translations, glosses, and "hypotheses" for
  undeciphered material are labeled model output with grounding, not findings. The
  Linear A and Cypro-Minoan remain undeciphered. See [Limitations](Limitations).
- **Heavy commands download on first use.** Anything marked heavy here
  (`--neural`, `greek work`, `greek eval`, `gloss`, the fetched corpora) pulls
  data to the cache the first time, with a note on stderr; afterwards it's offline.
  Pre-fetch with `aegean data fetch` before going offline.
- **`--json` is the contract; the table view is for humans.** Don't parse the
  rich tables: pass `--json` and use `jq`. `--limit`/`--top` cap the JSON lists
  too (`0` lifts the cap); where a payload carries totals (`matched`), they stay
  untruncated.
- **Metre and accuracy are bounded.** Lyric metres beyond the fixed aeolic
  templates are out of scope, and the trainable backends have measured ceilings:
  both documented on [Meters](Meters) and
  [Limitations](Limitations#measured-accuracy-boundaries).

For the terse one-page index of every command and flag, see the
[CLI Cheatsheet](CLI-Cheatsheet).
