# MCP

The **Model Context Protocol** (MCP) lets AI agents invoke external tools over a
standard interface. pyaegean ships `aegean-mcp`, an MCP server exposing the
toolkit's read and analysis surface so an agent (Claude Code or another MCP
client) can browse corpora, run compound queries, reconcile Linear A accounts,
scan Greek verse, gloss words, search Biblical and patristic texts, and load
Greek works without writing Python.

The server exposes **29 read-only tools** backed by the same code paths as the
[CLI](CLI) and [TUI](TUI). No tool accepts a filesystem path or mutates a
corpus, and domain misses return structured JSON errors instead of raw
tracebacks.

> `aegean-mcp` is **not** the generative AI layer. It exposes the deterministic
> analysis surface, calls no model provider, requires no API key, and returns no
> model-generated output. Undeciphered scripts (Linear A, Cypro-Minoan) appear
> as edited transcriptions and counts, never as decipherments. See
> [Limitations](Limitations).

## Install and run

The server lives in the `[mcp]` extra, which installs the Model Context Protocol
SDK (`mcp>=2`):

```bash
pip install "pyaegean[mcp]"
aegean-mcp                     # serve the tools over stdio
```

The server uses the SDK's `MCPServer` API introduced in `mcp` 2.0 (replacing the
removed `FastMCP`). Because no single SDK release ships both APIs, the extra
declares `mcp>=2`; if an environment pins an older SDK, upgrade it
(`pip install -U 'mcp>=2'`). MCP SDK 2.0 supports Python 3.10+, matching
pyaegean.

`aegean-mcp` communicates over stdio and is launched by an MCP client. Run bare
in a terminal, it waits for a client connection.

If `[mcp]` is missing or the installed SDK is below 2.0, `aegean-mcp` exits `1`
with a one-line error showing the fix and the underlying import error:

```text
aegean-mcp needs the [mcp] extra — pip install 'pyaegean[mcp]'  (No module named 'mcp')
aegean-mcp needs a newer MCP SDK — pip install -U 'mcp>=2'  (No module named 'mcp.server.mcpserver')
```

`import aegean` never imports the MCP SDK: tools register with `MCPServer` only
when `aegean-mcp` runs, keeping the core library zero-dependency.

## Connecting a client

Configure your MCP client to spawn `aegean-mcp` over stdio:

```json
{
  "mcpServers": {
    "pyaegean": {
      "command": "aegean-mcp"
    }
  }
}
```

Use the absolute path to `aegean-mcp` inside your virtual environment if the
client does not inherit your shell `PATH`. In Claude Code, register it from the
command line:

```bash
claude mcp add pyaegean -- aegean-mcp
```

Once connected, the client discovers all 29 tools below.

## The tools

Every tool returns JSON. The tools span four groups: corpora/search/accounting,
unified library discovery, Greek NLP/works/lexica, and Biblical/Septuagint/Patristic
Greek.

### Corpora, search, query, and provenance

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `list_corpora` | (none) | List all 21 registered corpora loadable by name (5 bundled offline; 16 hosted on demand). |
| `corpus_info` | `corpus` | Corpus summary: script, document count, source, license, and citation. |
| `show_document` | `corpus`, `doc_id` | One document's metadata and text line by line (`doc_id` matching is case- and space-forgiving: `ht13`, `py ta 641`). |
| `search_signs` | `corpus`, `pattern`, `limit=50`, `offset=0` | Words matching a wildcard sign pattern such as `KU-*-RO`, with frequencies and pagination (`total`, `has_more`, `next_offset`). |
| `search_text` | `query`, `target="nt"`, `book=None`, `edition=None`, `limit=20`, `exact=False` | Diacritic-insensitive SQLite FTS5 full-text search across any cached corpus, `lxx`, `nt-editions`, *Patrologia Graeca* volume (`PG073`), or CTS work ID (names/IDs only, never filesystem paths; offline-only). |
| `balance_accounts` | `corpus`, `doc_id=None`, `exact=False`, `tolerance=0.10` | Accounting reconciliation with optional rational equality and intact-account eligibility tolerance. |
| `query_corpus` | `corpus`, `where`, `output_kind="inscriptions"`, `limit=50`, `offset=0`, `view=None`, `count_unit="document"`, `statuses=None` | Compound query engine with explicit word view, counting population, pagination metadata, and citation. |
| `cite_corpus` | `corpus`, `style="plain"`, `site`, `period`, `scribe`, `support` | Cite a corpus or filtered subset as plain text, BibTeX, or APA. |
| `geo_sites` | `corpus`, `word=None` | Find-site coordinates (WGS84), Pleiades ids, and contested-provenance flags; with `word`, per-site attestation counts. |
| `data_status` | (none) | Local data store status: every fetchable dataset, downloaded state, on-disk size, and license (read-only). |
| `corpus_diagnose` | `corpus`, `deep=False` | Descriptive corpus-health report: reading-status profile (including alternate-reading tokens), provenance and citability, accounting reconciliation, numeral anomalies, review state, and with `deep` a sign scan. |

### Unified library discovery

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `library_status` | (none) | Read-only summary of all 5 bundled corpora, 39 hosted datasets, 7 themed packs (`biblical`, `patristic`, `aegean`, `epigraphy`, `literary`, `lexica`, `neural`), cached works, and disk footprint. |
| `library_search` | `query`, `category=None`, `installed_only=False`, `limit=25` | Offline read-only search across all corpora, Biblical bundles, 1,778 Greek literary works, 86 patristic commentaries, lexica, and neural models. |

`query_corpus` accepts a list of `where` rows. Each row is
`{"field": ..., "value": ...}` with optional `"connector"` (`and`/`or`, default
`and`) and `"negate"` (default `false`); rows chain in order, and an empty list
matches the whole corpus. Inscription-scope fields are `id-contains`, `site-is`,
`scribe-is`, `period-is`, `support-is`, `has-image`, `has-annotation`, and
`ins-contains-word`. Word-scope fields are `word-contains`, `word-prefix`,
`word-suffix`, `word-min-syllables`, `word-max-syllables`, `word-contains-sign`,
`word-cooccurs-with`, and `word-sign-pattern`. `output_kind` is `inscriptions`
or `words`; `count_unit` defaults to `document` (distinct documents containing a
word) or takes `token` for token occurrences. Omit `view` for legacy predicates,
or choose `surface`, `normalized`, or `lemma`; `statuses` filters editorial
reading status. Normalization derives comparison keys while preserving
diacritics; missing lemmas are excluded and never replaced by surface forms.
Results include population, exclusion, denominator, view, and count-unit
metadata. See [Analysis](Analysis) for the full query engine specification.

### Greek

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `greek_pipeline` | `text` | Baseline offline Greek NLP pipeline: one row per token (`text`, `upos`, `lemma`, position, and parser fields). |
| `greek_scan` | `text`, `meter="hexameter"` | Scan a Greek verse line, reporting glyph pattern, feet, and caesura, or `scans: false` with the reason. |
| `greek_catalog` | `query`, `author`, `title`, `source`, `limit=40`, `offset=0` | Search the bundled catalogue of 1,778 loadable Greek works (Perseus + First1KGreek) with bounded pagination (`total`, `has_more`, `next_offset`). |
| `greek_work` | `work_id`, `ref=None`, `preview_lines=10` | Load a Greek work by catalogue id (for example `tlg0012.tlg001`, the Iliad), whole or one section, with a preview. |
| `greek_gloss` | `word`, `dictionary="lsj"`, `full=False` | Gloss a Greek word from a registry dictionary (`lsj`, `middle-liddell`, `cunliffe`, `autenrieth`, `abbott-smith`, `dodson`). |
| `koine_gloss` | `word` | Koine (NT) gloss via the bundled Dodson lexicon (offline, CC0). |
| `greek_explain` | `text` | Plain-language explanation of each token's lemma evidence class (class-based, no confidence scores). |

### Biblical, Septuagint & Patristic Greek

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `biblical_strongs` | `query`, `roots=False`, `search=False`, `limit=15` | Look up or search Strong's & Extended Strong's Greek Lexicon entries (offline Dodson fallback or cached 11,142-entry `strongs-greek`, with optional recursive root tree). |
| `biblical_word_study` | `query`, `book=None`, `limit=15` | Koine Greek word study (Strong's entry, roots, NT distribution, Robinson morphology, and verse concordance over cached `nt-corpus` or bundled sample). |
| `biblical_psalm` | `psalm`, `system="mt"` | Convert Psalm numbers between Masoretic (`mt`, 1–150) and Septuagint (`lxx`, 1–151). |
| `biblical_nomina_sacra` | `text` | Expand early Greek NT manuscript *nomina sacra* contractions (`θς` → `Θεός`, `ις` → `Ἰησοῦς`, `χς` → `Χριστός`, `πνα` → `Πνεῦμα`) with expansion notes. |
| `biblical_catalog` | `kind="editions"`, `book=None`, `section=None` | Offline catalogues of `editions` (9 Greek NT editions), `witnesses` (13 2nd–5th c. CE manuscripts), `lxx` (55 Septuagint books), and `commentaries` (86 Greek patristic volumes across 10 Church Fathers/traditions). |
| `biblical_lxx` | `book="Gen"`, `ref="1.1-5"`, `query=None`, `limit=15` | Read or search the Swete Greek Septuagint offline (uses cached 55-book `lxx-corpus` when present, or the bundled Genesis 1 + LXX Psalm 22 sample). |
| `biblical_compare_editions` | `book`, `ref="1.18"`, `editions=None` | Collate up to 9 Greek NT editions (`nestle1904`, `sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`) with word-level textual diffs (uses cached `nt-editions`). |
| `biblical_witnesses` | `book`, `ref="1.18"`, `sigla=None`, `hand="original"` | Compare extant 2nd–5th c. CE Greek NT manuscript witnesses (`01`, `02`, `03`, `04`, `05`, `032`, `P45`–`P75`) with *nomina sacra* expansions and scribal corrections (uses cached `nt-witnesses`). |
| `biblical_commentary` | `book="John"`, `work_id=None`, `query=None`, `limit=5` | Read or search Greek patristic biblical commentaries across 86 indexed works (*Catenae*, Origen, First1KGreek Fathers, and *Patrologia Graeca* `PG071`–`PG126`). |

`greek_pipeline` and `balance_accounts` return the shared row mappings from
`aegean._view` used by `aegean greek pipeline` and `aegean balance`.
`greek_explain` runs the same pipeline independently over its input text, so
calling both `greek_pipeline` and `greek_explain` analyzes the text twice.
`greek_scan` accepts the same meters as the CLI (`hexameter`, `pentameter`,
`trimeter`, and the Aeolic templates; see [Meters](Meters)). Work ids for
`greek_work` come from `greek_catalog`, and citation references (`1`, `1.2`,
`1.1-1.50`, margin milestones `17a` and `1447a10`, comma lists) are documented
on [Greek Works and Books](Greek-Works-and-Books). Dictionaries and pipeline
stages are covered on [Greek NLP](Greek-NLP).

## Server invariants

### Structured errors

Domain misses (unknown corpus, document, work, dictionary, style, output kind,
or query field) return a JSON object with an `error` key and a recovery hint
instead of raising an uncaught exception:

```json
{ "error": "unknown corpus 'linar' (did you mean 'linearb' or 'lineara'?); available: aphrodisias, apostolic-fathers, byzantine, crete, cypriot, cyprominoan, damos, ddbdp, edh, greek, homer-scholia, igcyr, iip, iospe, isicily, lineara, linearb, nt, patrologia, pseudepigrapha, sigla" }
```

Hints include did-you-mean suggestions or point to the discovery tool
(`greek_catalog` for unknown work ids, or the hosted dictionary list for unknown
lexica). Cold-cache fetch failures (offline state, HTTP errors, checksum
mismatches) also return structured `error` payloads.

### Registry names only, no file paths

Every corpus is addressed by its **registry name** (`lineara`, `damos`, `nt`, …)
and every Greek work by its **catalogue work id** (`tlg0012.tlg001`). No tool
accepts a filesystem path, preventing arbitrary local file reads or writes.
`greek_work` rejects path-like arguments (containing `/` or `\`, or ending in
`.json`, `.db`, `.sqlite`, or `.xml`) and points back to `greek_catalog`.
`data_status` and `library_status` inspect the local store read-only without
downloading or deleting files.

## Download behavior

Five corpora (`lineara`, `linearb`, `cypriot`, `cyprominoan`, `greek`) are
bundled offline. Larger datasets download to the local data store on first use
and stay offline afterward:

- **Corpora:** `damos`, `nt`, `sigla`, `isicily`, `iip`, `iospe`, `igcyr`,
  `edh`, `aphrodisias`, `crete`, `apostolic-fathers`, `pseudepigrapha`,
  `byzantine`, `homer-scholia`, `patrologia`, and `ddbdp` download on first
  load. `ddbdp` and `patrologia` are multi-million-word archives; prefer
  `search_text`, `aegean db search ddbdp`, or volume-scoped
  `load_patrologia("PG073")` over full in-memory loads.
- **Biblical & Koine tools:** `biblical_strongs`, `biblical_word_study`,
  `biblical_psalm`, `biblical_nomina_sacra`, `biblical_catalog`, and
  `biblical_lxx` work offline on the bundled Dodson lexicon, John 1 / Philemon 1
  NT sample, and Swete LXX sample (`Gen 1:1–5`, `Ps 22:1–6`), and use cached
  `nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, and `lxx-corpus`
  bundles automatically when installed.
- **`greek_work`:** downloads a work's commit-pinned TEI source once on first
  request.
- **`greek_gloss`:** downloads a dictionary index once on first use and blocks
  until ready (0.13 MB for `abbott-smith`, 0.6 MB for `autenrieth`, 1.3 MB for
  `cunliffe`, 2.3 MB for `middle-liddell`, 15.4 MB for `lsj`). The first `lsj`
  lookup in a session loads a 60 MB, 116,414-entry table into memory (a few
  seconds); smaller lexica load in under a second, and `koine_gloss` uses the
  bundled Dodson lexicon with no download.

All downloads are SHA-256 verified. Pre-fetch datasets or packs from the shell
with `aegean library install PACK` or `aegean data fetch NAME` (see
[Data & Provenance](Data-and-Provenance) and
[CLI: Corpora, Library, Analysis & Data](CLI-Corpora)).

## See also

- **[CLI](CLI)** — command-line interface, including write/export commands not exposed over MCP.
- **[CLI Cheatsheet](CLI-Cheatsheet)** — one-page command reference.
- **[Analysis](Analysis)** — compound query engine behind `query_corpus`.
- **[Greek NLP](Greek-NLP)** — pipeline, scansion, and dictionaries behind the Greek tools.
- **[Greek Works and Books](Greek-Works-and-Books)** — work ids and citation schemes for `greek_catalog` and `greek_work`.
- **[Data & Provenance](Data-and-Provenance)** — local data store, licenses, and citations.
- **[Installation](Installation)** — optional extras, including `[mcp]`.
