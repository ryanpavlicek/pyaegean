# MCP

The **Model Context Protocol** (MCP) is an open standard that lets an AI agent
call external tools. pyaegean ships an MCP server, `aegean-mcp`, that exposes the
toolkit's read and analysis surface as a set of tools, so an agent (Claude Code
or any other MCP client) can browse the corpora, run the compound query engine,
reconcile Linear A accounts, scan Greek verse, gloss words, and load real Greek
works, all **without writing a line of Python**.

The server is deliberately narrow. It offers fifteen read-only tools over the
same code paths the [CLI](CLI) and the terminal UI use, so the three surfaces
cannot disagree. It never accepts a filesystem path and never mutates a corpus,
and every miss comes back as a structured error rather than a raw traceback.
Both of those are invariants, covered below.

> The AI layer is exploratory, but this server is not the AI layer. `aegean-mcp`
> exposes the deterministic, offline analysis surface. It does not call any model
> provider, needs no API key, and returns no model output. The undeciphered
> scripts (Linear A, Cypro-Minoan) are surfaced as edited transcriptions and
> counts, never as decipherments. See [Limitations](Limitations).

## Install and run

The server lives behind the `[mcp]` extra, which pulls in the Model Context
Protocol SDK:

```bash
pip install "pyaegean[mcp]"
aegean-mcp                     # serve the tools over stdio
```

`aegean-mcp` is a stdio server: it speaks MCP on standard input and output and is
meant to be launched by a client, not used interactively. Run bare in a terminal
it will simply wait for a client to connect.

If the extra is missing, or the installed SDK is too old for the server, the
command exits with a one-line fix instead of a traceback:

```
aegean-mcp needs the [mcp] extra — pip install 'pyaegean[mcp]'
aegean-mcp needs a newer MCP SDK — pip install -U 'mcp>=1.2'
```

The core `import aegean` never pulls the MCP SDK: the server registers its tools
with FastMCP only when `aegean-mcp` starts, so the zero-dependency core is
unaffected by installing the extra.

## Connecting a client

An MCP client launches the server as a subprocess and talks to it over stdio.
Point the client at the `aegean-mcp` console script. The standard stdio-server
configuration looks like this:

```json
{
  "mcpServers": {
    "pyaegean": {
      "command": "aegean-mcp"
    }
  }
}
```

Use the absolute path to `aegean-mcp` (the one inside your virtual environment)
if the client does not inherit your shell's `PATH`. On Claude Code you can add it
from the command line instead:

```bash
claude mcp add pyaegean -- aegean-mcp
```

Once connected, the client lists the fifteen tools below and can call them by
name.

## The tools

Every tool returns JSON. The two groups mirror the toolkit: corpus and
accounting tools that work across all four Aegean scripts and the Greek corpora,
and Greek-language tools for the pipeline, scansion, catalogue, works, and
dictionaries.

### Corpora, query, and provenance

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `list_corpora` | (none) | List the corpora loadable by name (bundled ones load offline; `damos`, `nt`, `sigla` download on first use). |
| `corpus_info` | `corpus` | Overview of a corpus: script, document count, source, license, and a ready-to-use citation. |
| `show_document` | `corpus`, `doc_id` | One document's metadata and text, line by line (`doc_id` is forgiving: `ht13`, `py ta 641` resolve). |
| `search_signs` | `corpus`, `pattern`, `limit=50` | Words matching a wildcard sign pattern such as `KU-*-RO`, with frequencies. |
| `balance_accounts` | `corpus`, `doc_id=None` | Accounting reconciliation: each stated total (KU-RO / TO-SO) against the summed items, with the difference. |
| `query_corpus` | `corpus`, `where`, `output_kind="inscriptions"`, `limit=50` | Run the compound query engine over a corpus and cite the exact result set. |
| `cite_corpus` | `corpus`, `style="plain"`, `site`, `period`, `scribe`, `support` | Cite a corpus, or with metadata filters the exact subset, as plain text, BibTeX, or APA. |
| `geo_sites` | `corpus`, `word=None` | Find-site coordinates (WGS84), Pleiades ids, and the contested-provenance flag; with `word`, per-site attestation counts. |
| `data_status` | (none) | The local data store: every fetchable dataset with its downloaded state, on-disk size, and license (read-only). |

`query_corpus` takes a list of `where` rows. Each row is
`{"field": ..., "value": ...}` plus an optional `"connector"` (`and`/`or`,
default `and`) and `"negate"` (default `false`); rows chain in order, and an
empty list matches the whole corpus. The inscription-scope fields are
`id-contains`, `site-is`, `scribe-is`, `period-is`, `support-is`, `has-image`,
`has-annotation`, and `ins-contains-word`; the word-scope fields are
`word-contains`, `word-prefix`, `word-suffix`, `word-min-syllables`,
`word-max-syllables`, `word-contains-sign`, `word-cooccurs-with`, and
`word-sign-pattern`. `output_kind` is `inscriptions` or `words`, and a word's
count is its document frequency (how many distinct inscriptions carry it). The
same engine and fields are documented on [Analysis](Analysis).

### Greek

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `greek_pipeline` | `text` | Run the baseline offline Greek NLP pipeline: one row per token (`text`, `upos`, `lemma`, position, and the parser fields). |
| `greek_scan` | `text`, `meter="hexameter"` | Scan a Greek verse line, reporting the glyph pattern, feet, and caesura, or `scans: false` with the reason. |
| `greek_catalog` | `query`, `author`, `title`, `source`, `limit=40` | Search the bundled catalogue of roughly 1,800 loadable Greek works (Perseus + First1KGreek). |
| `greek_work` | `work_id`, `ref=None`, `preview_lines=10` | Load a real Greek work by its catalogue id (e.g. `tlg0012.tlg001`, the Iliad), whole or one section, with a short preview. |
| `greek_gloss` | `word`, `dictionary="lsj"`, `full=False` | Gloss a Greek word from a registry dictionary (`lsj`, `middle-liddell`, `cunliffe`, `abbott-smith`, `dodson`). |
| `koine_gloss` | `word` | Koine (NT) gloss for a Greek word via the bundled Dodson lexicon (offline, CC0). |

`greek_pipeline` and `balance_accounts` return the shared row mappings from
`aegean._view`, the same rows the `aegean greek pipeline` and `aegean balance`
commands emit, so the tools cannot drift from the CLI. `greek_scan` accepts the
same meters as the CLI: `hexameter`, `pentameter`, `trimeter`, and the aeolic
line types (see [Meters](Meters)). Work ids for `greek_work` come from
`greek_catalog`; the citation-address forms (`1`, `1.2`, `1.1-1.50`) are
described on [Greek Works & Books](Greek-Works-and-Books). The glossing
dictionaries and the pipeline itself are covered on [Greek NLP](Greek-NLP).

## Two conventions that hold for every tool

### Structured errors, never a raw traceback

A domain miss (an unknown corpus, document, work, dictionary, style, output kind,
or query field) returns a JSON object with an `error` key and a recovery hint,
rather than raising an exception the client would surface as a stack trace:

```json
{ "error": "unknown corpus 'linar'; available: cypriot, cyprominoan, damos, greek, lineara, linearb, nt, sigla" }
```

Where it can, the hint is a did-you-mean suggestion, or a pointer to the tool
that answers the question (an unknown work id points at `greek_catalog`, an
unknown dictionary lists the hosted ones). This lets an agent recover in a single
follow-up call. Raised exceptions are reserved for genuine faults, not for the
ordinary case of a name that does not exist. Even a cold-cache fetch failure for
a downloadable corpus, work, or dictionary (offline, an HTTP error, or a checksum
mismatch) comes back as the structured `error` payload.

### Names only, never file paths

Every corpus is addressed by its **registry name** (`lineara`, `damos`, `nt`, …)
and every Greek work by its **catalogue work id** (`tlg0012.tlg001`). No tool
accepts a filesystem path, so the server cannot be steered into reading or
writing arbitrary local files. `greek_work` actively rejects an argument that
looks like a path (one containing a slash, or ending in `.json`, `.db`,
`.sqlite`, or `.xml`) and points the caller back at the catalogue. This is a
deliberate safety property: the server's whole surface is read and analysis over
the toolkit's own corpora, and `data_status` reports the local store without
downloading or deleting anything.

## What downloads, and when

Most corpora are bundled and everything runs offline. The exceptions are the
larger datasets, which fetch into the local data store on first use and are
offline afterward:

- **Corpora** `damos`, `nt`, and `sigla` download the first time a tool loads
  them by name.
- **`greek_work`** downloads a work's TEI source the first time that work is
  requested (a one-time, commit-pinned fetch).
- **`greek_gloss`** downloads and builds a dictionary index the first time that
  dictionary is used (roughly 0.1 to 15 MB depending on the dictionary);
  `koine_gloss` uses the bundled Dodson lexicon and never downloads.

Each fetch is sha256-verified. `data_status` shows what is already stored and
where. To pre-fetch a dataset from the shell instead of on first call, use
`aegean data fetch NAME` (see [Data & Provenance](Data-and-Provenance) and the
data commands on [CLI](CLI)).

## See also

- **[CLI](CLI)** — the same read and analysis surface as a command-line tool,
  plus the writing commands (`combine`, `db`, export) the MCP server does not
  expose.
- **[CLI Cheatsheet](CLI-Cheatsheet)** — one-line command reference.
- **[Analysis](Analysis)** — the compound query engine and its fields, behind
  `query_corpus`.
- **[Greek NLP](Greek-NLP)** — the pipeline, scansion, and dictionaries behind
  the Greek tools.
- **[Greek Works & Books](Greek-Works-and-Books)** — work ids and citation
  addressing for `greek_catalog` and `greek_work`.
- **[Data & Provenance](Data-and-Provenance)** — the local data store, licenses,
  and citation.
- **[Installation](Installation)** — the extras, including `[mcp]`.
