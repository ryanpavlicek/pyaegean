# The `aegean` CLI

The whole toolkit from the command line — corpora, Greek NLP, analysis, data,
and the (exploratory) AI layer — without writing Python.

```bash
pip install "pyaegean[cli]"     # typer + rich; the core stays zero-dependency
aegean --help
```

Three conventions hold everywhere:

- **`--json` on every command** prints one machine-readable JSON document, so
  results pipe into `jq`, files, or other tools.
- **`-` reads stdin** wherever a command takes a TEXT argument, so commands
  compose in shell pipelines.
- **Exit codes script cleanly**: 0 success, 1 domain error (one line on
  stderr), 2 usage error. `balance --strict` exits 1 on any unbalanced total.

On Windows, set `PYTHONUTF8=1` (and a UTF-8 console) so Greek renders correctly.

## Corpus commands

```bash
aegean info lineara                         # size, provenance, license, citation
aegean load lineara --site "Haghia Triada" -o ht.json   # filter → lossless JSON
aegean show lineara HT13                    # one document, line by line
aegean search lineara "KU-*-RO"             # wildcard sign-pattern word search
aegean stats lineara --top 10               # word frequencies (--signs for signs)
aegean balance lineara HT13                 # KU-RO reconciliation (--strict exits 1)
aegean cite lineara --site "Haghia Triada"  # cite the exact subset (--style bibtex|apa)
aegean export lineara -f csv -o lineara.csv # json | csv | parquet | epidoc
aegean geo lineara                          # located find-sites (+ --output sites.geojson)
aegean sign lineara KU                      # one sign: glyph, codepoint, sound value
aegean bridge linearb po-me                 # po-me → ποιμήν (shepherd)
```

Every command takes a corpus name: the bundled `lineara` / `linearb` / `cypriot` /
`cyprominoan` / `greek`, or the fetched-on-demand `damos` (the full ~5,900-tablet
Linear B corpus) and `sigla` (the SigLA Linear A dataset) — both CC BY-NC-SA,
downloaded to your cache on first use. `aegean stats damos --top 10` works exactly
like its `lineara` counterpart.

The compound query engine takes repeated `--where field=value` rows (prefix
`or:` to OR a row, `!` to negate it; `--fields` lists the field registry):

```bash
aegean query lineara --where "site-is=Haghia Triada" --where "or:id-contains=ZA" \
       --output-kind words --json
```

Query results and filtered subsets print their citation, so the exact result
set used in a paper is one `--json | jq .citation` away.

## Greek NLP (`aegean greek …`)

The zero-dependency stages work immediately:

```bash
aegean greek betacode "mh=nin a)/eide qea/"          # μῆνιν ἄειδε θεά
aegean greek normalize "λόγoς kai μh=νιν" --lenient  # repairs OCR artifacts, warns on stderr
aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος." [--sentences]
aegean greek syllabify εἰσφέρω                       # εἰσ-φέ-ρω (compound exception)
aegean greek accent λόγος                            # paroxytone
aegean greek quantities πατρός                       # syllable quantities
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
aegean greek ipa "λόγος" --period koine              # reconstructed pronunciation
aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."               # UPOS per token
aegean greek lemmatize "μῆνιν ἄειδε θεά"             # lemma per word
aegean greek morph λόγον                             # candidate morphological parses
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --json   # per-token records, one call
```

Backend flags stand in for the `use_*()` activations — each may download/build
to the cache on first use (a note goes to stderr), then everything is offline:

```bash
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural   # the joint neural pipeline
aegean greek parse "ἐν ἀρχῇ ἦν ὁ λόγος" --neural       # UD dependency tree
aegean greek tag "…" --treebank --tagger               # AGDT lookup + perceptron tagger
aegean greek gloss λόγος                               # LSJ gloss (~270 MB first use)
```

Real Greek works load on demand (Perseus canonical-greekLit / First1KGreek,
CC BY-SA, commit-pinned, cached):

```bash
aegean greek work tlg0012.tlg001                 # the Iliad: 24 books, ~127k tokens
aegean greek work tlg0012.tlg001 -o iliad.json   # as a round-trippable corpus file
```

`aegean greek eval ud --treebank perseus --split test --neural` reproduces the
published numbers through the official CoNLL 2018 evaluator (heavy: fetches
gold data and the model); `eval proiel|tagger|lemmatizer|parser` cover the
other measured evaluations.

## Analysis (`aegean analyze …`)

Exploratory surface analyses over the undeciphered material — evidence to
weigh, not conclusions:

```bash
aegean analyze distance KU-RO KI-RO          # weighted phonetic distance
aegean analyze align KU-RO KI-RO             # per-position alignment
aegean analyze assoc lineara KU-RO KI-RO     # χ², G², Fisher, PMI over shared documents
aegean analyze cooccur lineara KU-RO         # what shares a tablet with KU-RO
aegean analyze clusters lineara              # stem + productive-suffix clusters
aegean analyze structure lineara [HT13]      # accounting/libation/list/text census
```

## Data (`aegean data …`)

```bash
aegean data list      # the fetchable datasets (sizes, licenses)
aegean data fetch grc-joint    # pre-fetch (e.g. before going offline); sha256-verified
aegean data cache     # cache location + contents (override with PYAEGEAN_CACHE)
aegean data versions --json > data-versions.json   # pin every dataset's sha256 for a paper
```

## AI (`aegean ai …`) — exploratory, key-gated

Generative commands need a provider extra (`pip install "pyaegean[anthropic]"`)
and its API key in the environment; every result is labeled exploratory and
carries its grounding:

```bash
aegean ai providers
aegean ai translate "ἐν ἀρχῇ ἦν ὁ λόγος"             # grounded hybrid translation
aegean ai translate "KU-RO 130" --script lineara      # exploratory (undeciphered!)
aegean ai gloss "μῆνιν ἄειδε θεά"                     # interlinear gloss
aegean ai hypotheses "A-TA-I-*301-WA-JA" --corpus lineara   # cautious decipherment hypotheses
aegean ai ask "What is KU-RO?" --corpus lineara
```

## Recipes

Reconcile every Haghia Triada account and keep the failures:

```bash
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json
```

Lemmatize a file of Greek, one lemma per line:

```bash
cat chapter.txt | aegean greek lemmatize - --json | jq -r '.[].lemma'
```

Scan a poem line-by-line, keeping only the lines that scan:

```bash
while read -r line; do aegean greek scan "$line" --json 2>/dev/null | jq -r .pattern; done < poem.txt
```

Map a word's distribution and cite the subset you used:

```bash
aegean geo lineara --output sites.geojson
aegean cite lineara --site "Zakros" --style bibtex >> paper.bib
```
