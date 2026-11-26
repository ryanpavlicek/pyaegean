# CLI: Greek NLP & Review

Reference for the Ancient Greek NLP pipeline (`aegean greek …` — normalization,
tokenization, syllabification, accentuation, sandhi, scansion, IPA,
POS/lemma/morphology/parsing, dictionaries, Perseus & First1KGreek literary
works, CoNLL-U, interoperability bundles, and benchmark reproductions) and
annotation review workflows (`aegean review …`).

For Greek New Testament editions, early manuscripts, Strong's lexicon,
Septuagint (LXX), and patristic commentaries, see
[CLI: Biblical & Koine Greek](CLI-Bible).

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [CLI: Corpora, Library, Analysis & Data](CLI-Corpora) · [CLI: Biblical & Koine Greek](CLI-Bible) · [CLI: AI & MCP](CLI-AI)

---

## Greek NLP — `aegean greek …`

Zero-dependency stages run immediately after installation; heavier backends are
enabled with opt-in flags (see [Backend flags](#backend-flags-downloadbuild-on-first-use)).
Full method notes live on [Greek NLP](Greek-NLP) and [Meters](Meters).

Every `TEXT` argument accepts `-` for stdin, and every data-producing command
accepts `--json`. Plain text transforms (`normalize`, `betacode`, `strip`,
`ipa`) print converted text directly for shell pipelines. `greek stream` is an
exception: it reads a file path or `-` containing one JSON token array per line
and always emits JSONL.

### Offline zero-dependency stages

```bash
aegean greek betacode "mh=nin a)/eide qea/"      # μῆνιν ἄειδε θεά
aegean greek betacode "μῆνιν" --reverse          # mh=nin   (Unicode → Beta Code)
aegean greek normalize "λόγoς kai" --lenient     # repairs OCR artifacts; warns on stderr
aegean greek strip "μῆνιν"                       # μηνιν   (drop all diacritics)
aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος."      # one token per line (--sentences to split sentences)
aegean greek syllabify εἰσφέρω                   # εἰσ-φέ-ρω
aegean greek accent λόγος                        # acute, paroxytone
aegean greek accentuate λυε --recessive          # predict accent (recessive verb): λύε
aegean greek sandhi κἀγώ                         # expand crasis: καί ἐγώ
aegean greek quantities πατρός                   # πα:common | τρός:heavy
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, …"    # dactylic hexameter
aegean greek ipa "λόγος" --period koine          # loɣos  (--period attic|koine)
aegean bible strongs λόγος                       # Koine Strong's/Dodson gloss (bundled, offline)
aegean greek gloss μῆνις --dict cunliffe         # gloss from a registry dictionary (LSJ, Middle Liddell, Cunliffe, Autenrieth, Abbott-Smith)
aegean greek lexica                              # list available dictionaries
aegean greek lexicon-link λόγον                  # Logeion deep-link (→ …/λόγος if lemmatized, else word as typed)
```

### Sentence policies and `--rich` span boundaries

`tokenize --sentences` defaults to the conservative `default` policy. Select a
genre policy with `--sentence-policy {default|prose|verse|inscription|papyrus}`:

```bash
cat poem.txt | aegean greek tokenize --sentences --sentence-policy verse -
aegean greek tokenize --sentences --sentence-policy papyrus "[λόγος.] καί."
```

Add `--rich` (requires `--sentences`) to inspect character spans and boundary
provenance. With `--json`, it outputs a schema-1 object containing `source`,
`policy`, stable `policy_id`, `provenance`, `boundaries` (`start`/`end` and
`start_char`/`end_char`), and `sentences`. Without `--json`, `--rich` prints a
boundary table. Built-in rule policies are deterministic and leave the
confidence column blank. Custom segmenters are supported in Python via
`greek.segment_text(..., segmenter=...)`, which validates returned spans before
use.

Example outputs:

```bash
aegean greek betacode "mh=nin a)/eide qea/"
# μῆνιν ἄειδε θεά

aegean greek syllabify εἰσφέρω
# εἰσφέρω → εἰσ-φέ-ρω

aegean greek quantities πατρός
# πατρός → πα:common | τρός:heavy

aegean greek normalize "λόγoς kai" --lenient
# aegean: lenient normalize: repaired 1 Latin letter(s) in Greek words (o→ο)   [stderr]
# λόγος kai

aegean greek ipa "λόγος" --period koine
# loɣos
```

`accent` prints a table; the Python equivalent:

```python
from aegean import greek
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.betacode_to_unicode("mh=nin")            # 'μῆνιν'
```

### Accent placement (`accentuate`) and sandhi (`sandhi`)

`accentuate` predicts accent position from Greek accentuation rules (whereas
`accent` classifies an existing written accent). `--recessive` applies finite
verb accentuation; `--persistent --lemma L` applies nominal accentuation using
the lemma's home syllable. Ambiguous *dichrona* (α/ι/υ) whose vowel quantity
cannot be deduced from spelling are flagged as uncertain; `--lemma` or an
explicit vowel length resolves them.

```bash
aegean greek accentuate λυε --recessive
# λύε	paroxytone  (uncertain: recessive; penult acute/circumflex undetermined (dichronon))

aegean greek accentuate λογος --persistent --lemma λόγος
# λόγος	paroxytone
```

`sandhi` expands surface contractions to underlying words: crasis (κἀγώ → καί
ἐγώ), elision, and movable-ν / οὐκ alternation (οὐκ → οὐ). Unlisted or ambiguous
forms are flagged as uncertain and left unexpanded.

```bash
aegean greek sandhi κἀγώ
# καί ἐγώ	crasis
```

Both commands accept multiple words and `--json`.

### Scansion (`scan`)

`scan` checks a line against a fixed metrical template and prints the glyph
pattern, feet, and caesura, or exits `1` with the failure reason. Synizesis is
strictly lexical: a line requiring synizesis on a word absent from the curated
lexicon fails to scan.

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
# —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, dactyl, dactyl, dactyl, final; caesura: trochaic

aegean greek scan "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα" --meter trimeter
# ×—⏑—|×—⏑—|×—⏑×
# trimeter: metron, metron, metron; caesura: hephthemimeral

aegean greek scan "λόγος"
# aegean: line does not scan as dactylic hexameter (2 syllables): 'λόγος'   [stderr, exit 1]
```

Supported `--meter` values:

| name | meter |
|---|---|
| `hexameter` | dactylic hexameter (default) |
| `pentameter` | elegiac pentameter |
| `trimeter` | iambic trimeter |
| `glyconic` · `pherecratean` · `adonean` | Aeolic cola |
| `sapphic_hendecasyllable` | Sapphic eleven-syllable line |
| `alcaic_hendecasyllable` · `alcaic_enneasyllable` · `alcaic_decasyllable` | Alcaic stanza lines |

`--json` adds `feet`, `syllables`, `quantities`, `caesura`, and `ambiguous`. See
[Meters](Meters) for scope and limits.

### Tagging, lemmatizing, parsing

```bash
echo "μῆνιν ἄειδε θεά" | aegean greek lemmatize -
# μῆνιν	μῆνις
# ἄειδε	ἀείδω
# θεά	θεά

aegean greek morph λόγον
# λόγος [NOUN acc sg masc]
# λόγος [NOUN acc sg fem]
# λόγος [NOUN nom sg neut]
# λόγος [NOUN acc sg neut]
# λόγος [NOUN voc sg neut]

aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."               # UPOS per token
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --json   # per-token records in one call
aegean greek explain "ἐν ἀρχῇ ἦν ὁ λόγος."           # per-token lemma evidence classes
```

`pipeline` accepts the same `--sentence-policy` options as `tokenize`. The
selected policy sets sentence indexes and writes `boundary_policy`,
`boundary_policy_id`, `boundary_provenance`, optional `boundary_confidence`, and
source span fields onto each sentence's terminal token. This per-call document
policy is independent of the neural model manifest's
`segmentation: pretokenized` contract: the neural model receives pre-split word
lists and does not perform document segmentation.

Pass `--confidence` to attach typed model confidence evidence.
`--confidence-domain TEXT` labels the caller's source/domain scope, and
`--confidence-policy PATH` loads a JSON `AbstentionPolicy` whose task thresholds
produce `accept`, `review`, or `unavailable` decisions. JSON rows include
`token_confidence` and `sentence_confidence`, each carrying a calibration
id/hash and an explicit unavailable reason when evidence is absent or
unsupported. Legacy flat confidence fields remain populated for compatibility.
These flags do not install default thresholds, infer OOD labels, or promote
model estimates into editorial readings. Scoped confidence flags apply to
`pipeline`; `explain --confidence` renders the legacy aggregate confidence note.

### Bounded neural sentence streams (`stream`)

`stream` processes large or streaming inputs that are already tokenized into
sentences. Each non-blank input line is a JSON array of token strings; each
output line is the corresponding `SentenceAnalysis` JSON object including its
per-sentence receipt. `stream` activates the neural pipeline automatically and
flushes after every sentence so downstream consumers control backpressure.

```bash
printf '%s\n' '["μῆνιν","ἄειδε","θεὰ"]' '["ἄνδρα","μοι","ἔννεπε"]' \
  | aegean greek stream - --batch-size 2 > analyses.jsonl
```

Without `--batch-size`, sentences are analyzed one at a time. A positive batch
size buffers at most one chunk and preserves input order.
`--long-input strict|partial|windowed` (or `--partial` / `--windowed`) sets
overlength handling. `--confidence`, `--confidence-domain`, and
`--confidence-policy` match `pipeline`. Blank lines are skipped; malformed JSON,
non-array rows, or non-string tokens report the failing line number and exit
`1`. Records flushed prior to a later error remain valid JSONL. Redirect stdout
to capture JSONL; progress and activation notices write to stderr.

`stream` applies only to pre-tokenized neural sentence streams; raw-text
`pipeline`, `annotate_corpus`, and CoNLL-U commands remain non-streaming.

In `lemmatize`, forms absent from the lexicon return a fallback marked
`(fallback)` (`"known": false` in JSON) to distinguish dictionary hits from
heuristic guesses.

### Inflection synthesis (`inflect`)

`inflect` maps a lemma and morphological features to attested surface forms from
the Perseus AGDT inverse index. First use downloads/builds the AGDT index once
(noted on stderr); subsequent calls run offline. Unattested `(lemma, features)`
combinations return no forms.

```bash
aegean greek inflect λόγος --case gen --number sg
# λόγου

aegean greek inflect λόγος --paradigm
# λόγου	pos=NOUN case=gen number=sg gender=masc
# λόγος	pos=NOUN case=nom number=sg gender=masc
# λόγῳ	pos=NOUN case=dat number=sg gender=masc
# …  (every attested cell, one per line)
```

Feature flags accept short codes: `--case` (`nom`/`gen`/`dat`/`acc`/`voc`/`loc`),
`--number` (`sg`/`pl`/`du`), `--gender` (`masc`/`fem`/`neut`), `--tense`
(`pres`/`impf`/`aor`/`perf`/`plup`/`fut`/`futperf`), `--voice`
(`act`/`mid`/`pass`/`mp`), `--mood` (`ind`/`subj`/`opt`/`inf`/`imp`/`part`),
`--person` (`1`/`2`/`3`), and `--pos` (`NOUN`/`VERB`/`ADJ`/…). Pass `--paradigm`
to print every attested cell, and `--json` for structured output. Python
equivalent:

```python
from aegean import greek
greek.use_inflector()
greek.inflect("λόγος", case="gen", number="sg")   # ('λόγου',)
greek.paradigm("λόγος")                           # ((features, form), …)
```

### Glossing

```bash
aegean greek gloss μῆνις                      # LSJ (prebuilt index ~15 MB on first use)
aegean greek gloss μῆνις --dict cunliffe      # Homeric lexicon
aegean greek gloss λόγος --full               # full definition
```

For Koine / New Testament Strong's glosses and root trees (offline Dodson +
Extended Strong's), use `aegean bible strongs`
([CLI: Biblical & Koine Greek](CLI-Bible)). `greek gloss` downloads the prebuilt
LSJ index (~15 MB) first, falling back to building from upstream TEI (~270 MB)
if needed.

### Dialect and register (`usage`)

`usage` extracts dialect (Doric, Attic, Ionic, Aeolic, Epic, …) and register
(poetic, medical, comic, tragic, …) abbreviations from a word's LSJ entry,
activating LSJ on first use. Extraction is heuristic; words with no entry or no
recognized tags print dashes:

```bash
aegean greek usage μῆνις
# μῆνις: dialects=doric, aeolic  registers=lyric
```

`--json` returns `{word, dialects, registers}`. Python equivalent:
`greek.usage(word)` after `greek.use_lsj()`.

### Terminology rarity (`rarity`)

`rarity` scores vocabulary unfamiliarity relative to a reference corpus as an
offline translation-difficulty signal. Each content word is classified by its
lemma's frequency in the reference (`absent`, `hapax`, `rare`, `uncommon`,
`common`), and `overall` is the mean score. The default reference is the Greek
NT (`--corpus nt`, fetched on first use); pass `--corpus <path>` to score
against a register-matched local corpus instead.

```bash
aegean greek rarity "μῆνιν ἄειδε θεά" --corpus nt
# overall rarity 0.98  (vs 5395 lemmas / 137779 tokens)
#   μῆνιν	absent	1.00  (lemma μῆνις, ×0)
#   ἄειδε	absent	1.00  (lemma ἀείδω, ×0)
#   θεά	hapax	0.93  (lemma θεά, ×1)
```

`--top` sets how many rare words to display; `--treebank` enables the AGDT
lemmatizer for oblique forms; `--json` emits the overall score, reference size,
and per-word breakdown. The score is corpus-relative and measures lexical
scarcity, not translation accuracy. Python equivalent:
`greek.terminology_rarity(text, corpus)` (with `.overall` and `.hardest(n)`).

### Backend flags (download/build on first use)

Each flag mirrors a `use_*()` call in Python. First use downloads a model or
prebuilt index to the local cache (noted on stderr); later runs stay offline.

| flag | activates | first-use cost |
|---|---|---|
| `--treebank` | Perseus AGDT lexicon | shared prebuilt AGDT bundle; ~75 MB source fallback |
| `--tagger` | generalizing POS tagger | shared prebuilt AGDT bundle; source training fallback |
| `--lemmatizer` | edit-tree lemmatizer | shared prebuilt AGDT bundle; source training fallback |
| `--parser` | pure-Python arc-eager dependency parser | shared prebuilt AGDT bundle; source training fallback |
| `--neural-lemmatizer` | GreTa seq2seq lemmatizer (`[neural]`) | ~232 MB model |
| `--neural` | joint neural tagger/parser/lemmatizer (`[neural]`) | ~173 MB model |
| `--neural-variant LABEL` | Runtime artifact for `--neural`: `default`, `fast`, `compact`, `balanced` (only `default` currently exists) | no extra download unless a separate artifact is released |
| `--lsj` | LSJ glossing (implied by `greek gloss`) | ~15 MB prebuilt index; ~270 MB source fallback |

```bash
# downloads the model once, then runs offline:
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural --neural-variant default
aegean greek parse "ἐν ἀρχῇ ἦν ὁ λόγος" --neural          # UD dependency tree
aegean greek tag "…" --treebank --tagger                  # AGDT lookup + perceptron tagger
```

### Loading Greek literary works

`work` downloads a CC BY-SA TEI text from Perseus `canonical-greekLit` or
`First1KGreek` (commit-pinned, cached once) and parses it into a corpus. `works`
lists 25 curated work ids; `catalog` searches the full 1,778-work offline
metadata index. For NT and LXX book lists, use `aegean bible books`. See
[Greek Works and Books](Greek-Works-and-Books) for the full ID reference.

```bash
aegean greek works
# id              author        title
# tlg0012.tlg001  Homer         Iliad
# tlg0012.tlg002  Homer         Odyssey
# tlg0011.tlg002  Sophocles     Antigone
# tlg0059.tlg030  Plato         Republic
# …  (curated subset — full canon at https://scaife.perseus.org)

# fetches on first use:
aegean greek work tlg0012.tlg001                 # Iliad: 24 books, ~127k tokens
aegean greek work tlg0012.tlg001 --ref 1.1-1.50  # book 1, lines 1–50
aegean greek work tlg0012.tlg001 -o iliad.json   # save as a corpus file

# manage cached works:
aegean greek works --downloaded                  # list works in cache
aegean greek works --remove tlg0012.tlg001       # remove one work
aegean greek works --remove-author homer         # remove all cached Homer works
aegean greek works --remove-all                  # clear all cached works
```

#### Worked lifecycle

Find a work id in the offline catalogue:

```bash
aegean greek catalog --title crito
```
```text
                Greek works (1 match)
┌────────────────┬────────┬───────┬────────┬─────────┐
│ id             │ author │ title │ greek  │ src     │
├────────────────┼────────┼───────┼────────┼─────────┤
│ tlg0059.tlg003 │ Plato  │ Crito │ Κρίτων │ perseus │
└────────────────┴────────┴───────┴────────┴─────────┘
Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

Download and cache it:

```bash
aegean greek work tlg0059.tlg003
```
```text
                                tlg0059.tlg003
┌──────────────┬──────────────────────────────────────────────────────────────┐
│ field        │ value                                                        │
├──────────────┼──────────────────────────────────────────────────────────────┤
│ documents    │ 12                                                           │
│ tokens       │ 4635                                                         │
│ first        │ tlg0059.tlg003:43                                            │
│ name         │ Κρίτων — section 43                                          │
│ source       │ PerseusDL/canonical-greekLit                                 │
│              │ (tlg0059.tlg003.perseus-grc2.xml)                            │
│ data_version │ PerseusDL/canonical-greekLit@d4fab69a2c26                    │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

Verify it is cached, read it like any corpus (`aegean show tlg0059.tlg003 43`,
`aegean stats tlg0059.tlg003`), and remove it when finished:

```bash
aegean greek works --downloaded
# │ tlg0059.tlg003 │ Plato              │ Crito             │ perseus │ 64 KB   │

aegean greek works --remove tlg0059.tlg003
# removed tlg0059.tlg003  (Plato — Crito)
#
# removed 1 work from the cache.
```

`--ref` addresses the work's **declared citation scheme**: `1` (book or
Stephanus section), `1.2` (chapter), or `1.1-1.50` (line range). Citation levels
come from the TEI file and vary by genre: verse uses `book.line`, Stephanus
Plato uses `section`, Aristotle uses `chapter.subchapter`, and multi-book prose
uses `book.chapter.section`. An invalid `--ref` reports the work's expected
scheme (e.g. `cited by book.line`). Hyphen ranges must remain inside one
textpart; use a **comma list** (`--ref 1.1,1.5` or `--ref 1,3`) for sibling
sections or cross-textpart selections.

`--ref` also resolves **margin milestones outside the `<div>` scheme**, such as
Stephanus sub-pages (`17a`) or Bekker lines (`1447a10`), extracting the span
from that marker to the next marker of the same kind. Perseus marks every fifth
Bekker line, so `1447a10` returns lines 10–14 and only marked lines resolve.
A whole Bekker page-*column* also works (`1447a` = column `a`; request the whole
physical page with the comma list `1447a,1447b`), as does `17a,17b`. Hyphen
ranges of milestones are not yet supported; pass a comma list of markers
instead. In Python, `greek.citation_scheme("tlg0012.tlg001")` returns the
ordered scheme levels (e.g. `["book", "line"]`). See
[Greek Works and Books](Greek-Works-and-Books#citation-schemes-how-a-work-is-addressed).
`--source` selects `auto`/`perseus`/`first1k`; `--edition` selects a specific
TEI edition file.

For the Greek New Testament (9 editions), early manuscripts, Septuagint (LXX),
and patristic commentaries, use `aegean bible`
([CLI: Biblical & Koine Greek](CLI-Bible)).

**`catalog` searches the full 1,778-work offline index** (768 `perseus` + 1,010
`first1k`), returning metadata with no network access. Every returned work id
passes directly to `aegean greek work`.

```bash
aegean greek catalog --author plato --limit 8
```
```text
                       Greek works (39 matches)
┌────────────────┬────────┬────────────┬────────────────────┬─────────┐
│ id             │ author │ title      │ greek              │ src     │
├────────────────┼────────┼────────────┼────────────────────┼─────────┤
│ tlg0059.tlg001 │ Plato  │ Euthyphro  │ Εὐθύφρων           │ perseus │
│ tlg0059.tlg002 │ Plato  │ Apology    │ Ἀπολογία Σωκράτους │ perseus │
│ tlg0059.tlg003 │ Plato  │ Crito      │ Κρίτων             │ perseus │
│ tlg0059.tlg004 │ Plato  │ Phaedo     │ Φαίδων             │ perseus │
│ tlg0059.tlg005 │ Plato  │ Cratylus   │ Κρατύλος           │ perseus │
│ tlg0059.tlg006 │ Plato  │ Theaetetus │ Θεαίτητος          │ perseus │
│ tlg0059.tlg007 │ Plato  │ Sophist    │ Σοφιστής           │ perseus │
│ tlg0059.tlg008 │ Plato  │ Statesman  │ Πολιτικός          │ perseus │
└────────────────┴────────┴────────────┴────────────────────┴─────────┘

… and 31 more — narrow with --author/--title, or --limit 0 to list all (-o to save).
Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

Positional `QUERY` matches substrings across id, author, English title, and
Greek title; `--author/-a`, `--title/-t` (English or Greek), and
`--source perseus|first1k` filter specifically (case-insensitive, combined with
AND). `--limit/-n` caps the table, `--json` array, and `--output/-o` rows (`0` =
all; JSON preserves the full count in `matched`). `-o` selects `.json`, `.csv`,
or `.txt` by file extension:

```bash
aegean greek catalog herodotus --json
```
```json
{
  "matched": 2,
  "works": [
    {
      "id": "tlg0016.tlg001",
      "author": "Herodotus",
      "title": "Histories",
      "greek_title": "Ἱστορίαι",
      "source": "perseus"
    },
    {
      "id": "tlg0062.tlg056",
      "author": "Lucian of Samosata",
      "title": "Herodotus",
      "greek_title": "Ἡρόδοτος ἢ Ἀετίων",
      "source": "perseus"
    }
  ]
}
```

```bash
aegean greek catalog --author aristophanes --source perseus -o aristophanes.csv
# wrote aristophanes.csv     (id,author,title,greek_title,source — one row per work)
```

Coverage matches the pinned upstream repositories; authors absent upstream
return zero matches:

```bash
aegean greek catalog sappho
# No works match. Try a looser filter, or browse https://scaife.perseus.org
```

Python equivalents: `greek.catalog(query=None, *, author=None, title=None, source=None)`
and `greek.popular_works()`.

### Inspecting and preserving CoNLL-U files

`aegean greek conllu` reads treebank documents without running any model.
`inspect` counts syntactic words, multiword token ranges, empty nodes, enhanced
annotations, and the original-ID projection. `--strict` rejects malformed
columns, IDs, row placement, references, or invalid basic trees. `--json` or
`-o` emits the machine-readable report.

```bash
aegean greek conllu inspect treebank.conllu --strict --json
aegean greek conllu export treebank.conllu -o checked-copy.conllu --strict
```

`export` copies source bytes atomically, preserving comments, all ten columns,
MWT ranges, empty nodes, `DEPS`, `MISC`, and line endings without invoking any
pipeline. `greek eval ud` scores only the integer-ID syntactic-word projection
so gold structural rows are not credited to the model. Typed editorial forms
encode into the `AegeanFormState` MISC field as URL-safe base64 JSON (schema 1);
strict inspection validates schema and size, while lenient inspection preserves
the raw MISC entry undecoded.

### Reproducing published evaluations (`eval`)

`aegean greek eval TARGET` runs the official evaluation scripts against fetched
gold data. Supported targets: `ud`, `proiel`, `nt`, `papygreek`, `verse`,
`dbbe`, `tagger`, `lemmatizer`, `parser`.

```bash
# fetches gold data and the model on first run:
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval ud --neural --bootstrap          # percentile CIs over sentences
aegean greek eval ud --drift                       # POS confusions and per-POS accuracy
aegean greek eval proiel --drift                   # out-of-AGDT PROIEL gold error breakdown
aegean greek eval nt --drift                       # Nestle 1904 NT error breakdown
aegean greek eval ud --by-genre --neural           # slice fold by literary genre
```

`--fold` selects the UD Ancient Greek fold (`perseus` or `proiel`) and `--split`
selects `dev` or `test`; both validate before fetching. (The legacy `--treebank`
alias still works with a deprecation warning pointing to `--fold`.) `--output/-o`
saves results.

- `--bootstrap` (`ud` only): reports percentile confidence intervals as
  `estimate [low, high]`.
- `--drift` (`ud`, `proiel`, `nt`): prints a gold→predicted POS confusion table,
  per-POS accuracy, frequent lemma confusions, and seen-vs-unseen splits to
  separate annotation-convention drift from model error. See
  [When the Tool Is Wrong](When-the-Tool-Is-Wrong).
- `--by-genre` (`ud` only): groups sentences by `sent_id` author into literary
  genres (`epic`, `tragedy`, `prose`). Because the leakage-clean Perseus test
  fold is prose-only, this currently emits a single `prose` bucket; see
  [Benchmarks](Benchmarks).
- `--batch-size N` (`ud`, `nt`, `--by-genre`): evaluates `N` sentences per
  neural call for faster runs; rejected where no batched loop exists (`proiel`,
  `--bootstrap`, `--drift`).

Published figures and protocols live on [Benchmarks](Benchmarks),
[Greek NLP](Greek-NLP), and [Limitations](Limitations#measured-accuracy-boundaries).

#### Worked evaluation run

The pure-Python tagger on the Perseus `dev` split (using the cached
`agdt-derived` bundle):

```bash
aegean greek eval ud --fold perseus --split dev --tagger
# aegean: activating the POS tagger (first use may download/build)…   [stderr]
```
```text
              eval: ud
┌─────────────┬────────────────────┐
│ metric      │ value              │
├─────────────┼────────────────────┤
│ treebank    │ perseus            │
│ split       │ dev                │
│ parsed      │ False              │
│ upos        │ 0.8262480234922069 │
│ xpos        │ 0.0                │
│ ufeats      │ 0.36638807318726   │
│ lemma       │ 0.6045629094194714 │
│ uas         │ None               │
│ las         │ None               │
│ clas        │ None               │
│ n_words     │ 22135              │
│ n_sentences │ 1137               │
└─────────────┴────────────────────┘
```

Only stages active under the chosen backend flag populate metrics: `--tagger`
runs no parser, leaving `parsed=False` and `uas`/`las`/`clas` as `None`,
whereas `--neural` fills dependency metrics too. These `dev`-split numbers are a
local check; official test-split numbers and evaluation protocols are recorded
on [Benchmarks](Benchmarks) and [Greek NLP](Greek-NLP).

---

## Review — `aegean review …`

The review workflow exports machine annotations to CSV for human verification,
merges multi-reviewer sheets, and writes verified corrections back with full
attribution and history. Exported CSVs can be edited in a spreadsheet or
reviewed interactively in the terminal with
`aegean tui --review review.csv` (or
`aegean tui --review alice.csv --review bob.csv --corpus analysis.json`; see
[TUI → Annotation review (`r`)](TUI#annotation-review-r)).

| Command | Purpose | Key flags | Example |
|---|---|---|---|
| `review export` | Export selected rows with predictions, analysis identity, inclusion reasons, and field-decision columns | `-o/--output` `--selection all\|flagged\|unverified\|sample` `--layout full\|editable` `--priority source\|calibrated-risk` `--budget N` repeatable `--field` `--sample-size` `--seed` `--reviewer` `--annotate` `--neural` `--with-confidence` `--confidence-domain` `--annotated-output` | `aegean review export nt -o review.csv --selection unverified --field pos --layout editable` |
| `review merge` | Merge reviewer copies of one export with per-field attribution and conflict reporting | `--corpus/-c` `-o/--output` `--on-conflict error\|report` `--json` | `aegean review merge alice.csv bob.csv -c analysis.json -o merged.csv --on-conflict report` |
| `review apply` | Apply verified decisions and corrections while keeping original predictions and review history | `-o/--output` (`.json`/`.db`) `--reviewer NAME` | `aegean review apply analysis.json review.csv -o reviewed.json --reviewer "A. Scholar"` |

The example below uses the bundled offline `greek` sample. Because that sample
has no built-in annotations, `--annotate` populates lemma and POS first. Already
annotated corpora such as `nt` need no `--annotate`
(`aegean review export nt -o review.csv` writes all 137,779 rows).

`--annotate` writes fresh lemma/POS predictions onto a copy of the corpus,
replacing prior predictions and marking earlier lemma/POS decisions `stale`
while preserving attribution, history, and unchanged morphology reviews. Export
saves the annotated corpus alongside the CSV (or at `--annotated-output PATH`;
existing files are refused). Pass that saved annotated corpus to both `merge`
and `apply`, because re-running annotation mints a new analysis generation even
when predictions match.

Select rows with `--selection`:

| Mode | Rows exported |
|---|---|
| `all` (default) | Every word with a token position, including verified lemmas. |
| `flagged` | Rows with `needs_review=true` (normally identity/unresolved lemmas). |
| `unverified` | Words with an unverified requested field (`--field lemma` by default). |
| `sample` | Seeded random sample of unflagged rows (`--sample-size N --seed N`). |

For `unverified`, only `true` (case-insensitive) excludes a word; empty or other
values stay included. Selection modes do not modify `needs_review` or impose a
confidence cutoff. Repeat `--field` to select `lemma`, `pos`, `morph`, `head`,
or `deprel`. Inclusion reasons are recorded per row.

To focus editorial effort on high-risk predictions, pair
`--neural --with-confidence --confidence-domain literary` (or
`documentary_native` for papyri) with `--priority calibrated-risk --budget 50`.
`review export` loads the matching bundled calibration registry automatically
and prioritizes highest-risk predictions while keeping dependency sentences
intact.

Fill `decision_lemma`, `decision_pos`, or `decision_morph` with one of four
actions:

| Action | Effect |
|---|---|
| `accept` | Keep the nonempty prediction and mark that field verified; leave `correct_*` blank. |
| `correct` | Supply a different, nonempty `correct_*` value and mark that field verified. |
| `defer` / `reject` | Keep the prediction and mark that field unverified; leave `correct_*` blank. |
| blank | Legacy correction-only mode: a changed `correct_*` corrects the field; blank or unchanged cells imply no approval. |

Record `reviewer`, `reviewer_note`, and `reviewer_evidence` for attribution and
citations. Verification is per field: accepting a lemma does not verify POS,
morphology, syntax, or lexical sense. `review apply` writes decisions,
`<field>__pred` snapshots, and `review_history` into `Token.annotations`
(separate from `TokenRecord.lemma_verified`, which reflects pipeline lemma
evidence). New snapshots check model/configuration identity, analysis
generation, source alignment, and original predictions; leave read-only snapshot
columns untouched.

Dependency review uses `decision_head`, `decision_deprel`, `correct_head`, and
`correct_deprel`. Selecting either field includes full sentence context
including parsed punctuation. Heads use 1-based sentence indexes (`0` = root),
not corpus positions or source-token IDs. Edits must maintain one root, valid
head indexes, matching root labels, and no cycles; invalid trees fail atomically
with no partial writes.

```bash
# 1. Export a review CSV (add --layout editable for a compact sheet + .companion.json)
aegean review export greek --annotate --annotated-output analysis.json -o review.csv
#    wrote 27 review rows to review.csv
#    record field decisions or corrections, then apply them to analysis.json

# 2. Triage unresolved/identity lemmas with --selection flagged
aegean review export analysis.json --selection flagged -o triage.csv
#    wrote 7 review rows to triage.csv

# 3. Export a 50-row calibrated-risk neural review queue
aegean review export greek --annotate --neural --with-confidence --confidence-domain literary \
    --layout editable --priority calibrated-risk --budget 50 -o queue.csv

# 4. Review in a spreadsheet or in `aegean tui --review alice.csv --review bob.csv --corpus analysis.json`,
#    then merge and apply against the saved annotated corpus:
aegean review merge alice.csv bob.csv -c analysis.json -o merged.csv --on-conflict report
aegean review apply analysis.json merged.csv -o greek-reviewed.json --reviewer "Review team"
```

Source-aware rows join by stable source-token ID and check alignment and surface
text; legacy rows join by document id and position. Any mismatched source or
token text raises an error instead of applying a correction to the wrong word.
`merge` preserves source whitespace, typed-form cells, and per-reviewer
attribution in `reviewer_records`. See
[When the Tool Is Wrong](When-the-Tool-Is-Wrong) for review guidance.

`--layout full` (default) includes all guarded `alignment_*` and `form_*`
columns plus `form_state_json` inline. `--layout editable` puts decision and
correction columns first and stores immutable snapshot and provenance columns in
a SHA-256-bound `<name>.companion.json` sidecar that `review merge`,
`review apply`, and `aegean tui --review` load automatically. Both layouts
reject rows whose form state no longer matches the corpus; older review CSVs
without form columns remain readable under token-text and identity checks.
