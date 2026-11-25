# CLI: Greek NLP & Review

Reference for the Ancient Greek NLP pipeline (`aegean greek …` — normalization, tokenization,
syllabification, accentuation, sandhi, scansion, IPA, POS/lemma/morphology/parsing, dictionaries,
Perseus & First1KGreek literary works, CoNLL-U, interoperability bundles, and benchmark
reproductions) and annotation review workflows (`aegean review …`).

For Greek New Testament editions, early manuscripts, Strong’s lexicon, Septuagint (LXX), and
patristic commentaries, see [CLI: Biblical & Koine Greek](CLI-Bible).

Back to [CLI Overview](CLI) · [CLI Cheatsheet](CLI-Cheatsheet) · [CLI: Corpora, Analysis & Data](CLI-Corpora) · [CLI: Biblical & Koine Greek](CLI-Bible) · [CLI: AI & MCP](CLI-AI)

---

## Greek NLP — `aegean greek …`

The full Ancient Greek pipeline from the shell. The zero-dependency stages run the
moment you install; the heavier backends are opt-in flags (next section). Full
explanations live on [Greek NLP](Greek-NLP); metre is on [Meters](Meters).

Every text argument accepts `-` for stdin, and every data-producing command takes
`--json` (the plain text transforms `normalize`, `betacode`, `strip`, and `ipa`
just print the converted text, ready for the next pipe).
`greek stream` is the deliberate exception to the text-argument shape: it accepts
a path or `-` containing one JSON token array per line and always emits JSONL.

### The stages that work immediately

```bash
aegean greek betacode "mh=nin a)/eide qea/"      # μῆνιν ἄειδε θεά
aegean greek betacode "μῆνιν" --reverse          # mh=nin   (Unicode → Beta Code)
aegean greek normalize "λόγoς kai" --lenient     # repairs OCR artifacts; warns on stderr
aegean greek strip "μῆνιν"                        # μηνιν   (drop all diacritics)
aegean greek tokenize "ἐν ἀρχῇ ἦν ὁ λόγος."       # one token per line (--sentences to split sentences)
aegean greek syllabify εἰσφέρω                    # εἰσ-φέ-ρω
aegean greek accent λόγος                         # acute, paroxytone
aegean greek accentuate λυε --recessive           # predict the accent (recessive verb): λύε
aegean greek sandhi κἀγώ                           # expand crasis: καί ἐγώ
aegean greek quantities πατρός                    # πα:common | τρός:heavy
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, …"     # dactylic hexameter
aegean greek ipa "λόγος" --period koine          # loɣos  (--period attic|koine)
aegean bible strongs λόγος                         # Koine Strong’s/Dodson gloss (bundled, offline)
aegean greek gloss μῆνις --dict cunliffe           # gloss from a chosen dictionary (LSJ, Middle Liddell, Cunliffe, Autenrieth, Abbott-Smith)
aegean greek lexica                                # list the available dictionaries
aegean greek lexicon-link λόγον                    # a Logeion deep-link (→ …/λόγος when the offline lemmatizer resolves the form, else the word as typed)
```

### Sentence policies and rich boundaries

`tokenize --sentences` uses the conservative `default` policy. Choose a named
policy with `--sentence-policy {default|prose|verse|inscription|papyrus}`:

```bash
cat poem.txt | aegean greek tokenize --sentences --sentence-policy verse -
aegean greek tokenize --sentences --sentence-policy papyrus "[λόγος.] καί."
```

Add `--rich` to inspect source spans and boundary provenance. It requires
`--sentences`; with `--json` the result is a schema-1 object containing the exact
`source`, `policy`, stable `policy_id`, `provenance`, `boundaries` (`start`/`end`
and `start_char`/`end_char`), and the historical `sentences` projection. Without
`--json`, `--rich` renders a boundary table. Built-in rules are deterministic and
report an empty confidence cell. A caller-supplied segmenter is available in Python
(`greek.segment_text(..., segmenter=...)`), where output is validated before use.

Real runs:

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

`accent` prints a small table; the Python equivalent of the same fact:

```python
from aegean import greek
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.betacode_to_unicode("mh=nin")            # 'μῆνιν'
```

### Accent placement (`accentuate`) and sandhi (`sandhi`)

`accentuate` *predicts* a word's accent from the accentuation laws (where `accent`
*reads* an existing one). `--recessive` is the rule for finite verbs, `--persistent
--lemma L` the rule for nominals (the lemma supplies the home syllable). A
*dichronon* (α/ι/υ) whose length the spelling leaves open is flagged uncertain
rather than guessed; `--lemma` or a supplied vowel length resolves it.

```bash
aegean greek accentuate λυε --recessive
# λύε	paroxytone  (uncertain: recessive; penult acute/circumflex undetermined (dichronon))

aegean greek accentuate λογος --persistent --lemma λόγος
# λόγος	paroxytone
```

`sandhi` expands a surface contraction to the underlying word(s): crasis (κἀγώ →
καί ἐγώ), elision, and the movable-ν / οὐκ alternation (οὐκ → οὐ). It is
conservative: an unlisted or ambiguous form is flagged uncertain and left intact,
never over-expanded.

```bash
aegean greek sandhi κἀγώ
# καί ἐγώ	crasis
```

Both take one or more words and `--json`.

### Scansion (`scan`)

`scan` checks a line against a fixed metrical template and prints the pattern,
the feet, and the caesura — or exits `1` with the reason if the line declines.
Synizesis is lexical, not guessed: a line that only scans via synizesis on a word
outside the curated lexicon declines rather than inventing a fit.

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

`--meter` accepts:

| name | metre |
|---|---|
| `hexameter` | dactylic hexameter (Homer): the default |
| `pentameter` | elegiac pentameter (the second line of an elegiac couplet) |
| `trimeter` | iambic trimeter (tragic/comic dialogue) |
| `glyconic` · `pherecratean` · `adonean` | aeolic cola |
| `sapphic_hendecasyllable` | the Sapphic eleven-syllable line |
| `alcaic_hendecasyllable` · `alcaic_enneasyllable` · `alcaic_decasyllable` | the Alcaic stanza lines |

`--json` adds `feet`, `syllables`, `quantities`, `caesura`, and an `ambiguous`
flag. See [Meters](Meters) for what's in scope and what isn't.

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

aegean greek tag "ἐν ἀρχῇ ἦν ὁ λόγος."          # UPOS per token
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --json   # per-token records in one call
aegean greek explain "ἐν ἀρχῇ ἦν ὁ λόγος."           # what each stage did, in plain language
```

`pipeline` accepts the same `--sentence-policy` values as `tokenize`. The
selected policy determines sentence indexes and is recorded on the terminal
token of each sentence as `boundary_policy`, `boundary_policy_id`,
`boundary_provenance`, optional `boundary_confidence`, and source span fields.
This per-call document policy is separate from the neural model manifest's
`segmentation: pretokenized` contract: the model receives the already split word
lists and does not choose document boundaries.

Pass `--confidence` to request optional typed model evidence. `--confidence-domain TEXT`
labels the caller's source/domain scope, and `--confidence-policy PATH` loads a JSON
`AbstentionPolicy` whose task thresholds produce `accept`, `review`, or `unavailable`
decisions. The JSON rows expose `token_confidence` and `sentence_confidence`; each value
has a calibration id/hash and an explicit unavailable reason when evidence is missing or
unsupported. Existing flat confidence fields remain compatibility output. These options do
not install thresholds, infer an OOD label, or turn a model estimate into a reading. The
scoped options apply to `pipeline`; `explain --confidence` continues to render the legacy
aggregate confidence note rather than the typed row structure.

### Bounded neural sentence streams (`stream`)

`stream` is for a large or one-shot source that already supplies tokenized
sentences. Each nonblank input line is a JSON array of strings; each output line is
the matching complete `SentenceAnalysis`, including its per-sentence receipt. The
command activates the neural pipeline automatically and flushes every result, so a
downstream process receives incremental output and controls backpressure.

```bash
printf '%s\n' '["μῆνιν","ἄειδε","θεὰ"]' '["ἄνδρα","μοι","ἔννεπε"]' \
  | aegean greek stream - --batch-size 2 > analyses.jsonl
```

With no `--batch-size`, the canonical path pulls and analyzes one sentence at a
time. A positive size holds at most one transactional chunk and preserves source
order. `--long-input strict|partial|windowed` (or `--partial` / `--windowed`)
controls overlength sentences. `--confidence`, `--confidence-domain`, and
`--confidence-policy` match the pipeline evidence controls. Blank lines are
ignored; malformed JSON, a non-array row, or a non-string token names its input
line and exits cleanly. Results emitted before a later source/backend error remain
valid. Redirect stdout to keep the JSONL; progress and activation notes use stderr.

This is a pre-tokenized neural sentence stream. It does not turn raw-text
`pipeline`, `annotate_corpus`, or CoNLL-U serialization into streaming commands.

A lemma that the lexicon doesn't know is still returned, marked `(fallback)` (and
`"known": false` in JSON), so you can tell a real hit from a heuristic guess.

### Inflection synthesis (`inflect`)

`inflect` is the inverse of `lemmatize`: give it a lemma plus the features you want
and it returns the attested form(s), read off the same Perseus AGDT the analysis stack
uses. It activates inflection synthesis on first use (a note goes to stderr; the AGDT is
fetched and the inverse index built once, then it's offline). Coverage is what the corpus
attests: an unattested (lemma, features) cell returns nothing rather than a guess.

```bash
aegean greek inflect λόγος --case gen --number sg
# λόγου

aegean greek inflect λόγος --paradigm
# λόγου	pos=NOUN case=gen number=sg gender=masc
# λόγος	pos=NOUN case=nom number=sg gender=masc
# λόγῳ	pos=NOUN case=dat number=sg gender=masc
# …  (every attested cell, one per line)
```

The feature flags take the analyzer's short codes: `--case` (nom/gen/dat/acc/voc/loc),
`--number` (sg/pl/du), `--gender` (masc/fem/neut), `--tense`
(pres/impf/aor/perf/plup/fut/futperf), `--voice` (act/mid/pass/mp), `--mood`
(ind/subj/opt/inf/imp/part), `--person` (1/2/3), and `--pos` (NOUN/VERB/ADJ/…). Pass
`--paradigm` to list every attested cell instead of filtering, and `--json` for the raw
forms (or the `{features, form}` cells under `--paradigm`). The same in Python:

```python
from aegean import greek
greek.use_inflector()
greek.inflect("λόγος", case="gen", number="sg")   # ('λόγου',)
greek.paradigm("λόγος")                            # ((features, form), …)
```

### Glossing

```bash
aegean greek gloss μῆνις                      # LSJ (prebuilt index ~15 MB on first use)
aegean greek gloss μῆνις --dict cunliffe      # Homeric lexicon
aegean greek gloss λόγος --full               # full definition
```

For Koine / New Testament Strong's glosses and root trees (offline Dodson +
Extended Strong's), use `aegean bible strongs` ([CLI: Biblical & Koine Greek](CLI-Bible)).
The classical `gloss` command tries the prebuilt LSJ index first (`~15 MB`), falling
back to the upstream TEI (`~270 MB`) if unavailable.

### Dialect and register (`usage`)

`usage` reads a word's **dialect** (Doric, Attic, Ionic, Aeolic, Epic, …) and
**register** (poetic, medical, comic, tragic, …) tags off its LSJ entry, which marks
them with standard abbreviations. It activates LSJ on first use (the same fetch as
`greek gloss`). The match is heuristic, so it surfaces the tags LSJ records without
resolving every nuance; a word with no entry or no recognised tags prints dashes:

```bash
aegean greek usage μῆνις
# μῆνις: dialects=doric, aeolic  registers=lyric
```

`--json` returns `{word, dialects, registers}` (each a list). The same in Python is
`greek.usage(word)` (after `greek.use_lsj()`), returning a `UsageInfo` with `.dialects`
and `.registers`.

### Terminology rarity (`rarity`)

`rarity` scores how unusual a text's vocabulary is **relative to a reference corpus**,
a cheap, offline translation-difficulty signal: rare, technical, or documentary terms
are where a translator (human or model) is most likely to stumble. Each content word is
scored by its lemma's frequency in the reference corpus (`absent` / `hapax` / `rare` /
`uncommon` / `common`), and the overall score is the mean. The default reference is the
Greek NT (`--corpus nt`, fetched on first use); pass `--corpus <path>` to score against
a corpus JSON of your own register instead.

```bash
aegean greek rarity "μῆνιν ἄειδε θεά" --corpus nt
# overall rarity 0.98  (vs 5395 lemmas / 137779 tokens)
#   μῆνιν	absent	1.00  (lemma μῆνις, ×0)
#   ἄειδε	absent	1.00  (lemma ἀείδω, ×0)
#   θεά	hapax	0.93  (lemma θεά, ×1)
```

`--top` sets how many of the rarest words to list; `--treebank` activates the AGDT
lemmatizer first (better lemma coverage on oblique forms); `--json` emits the overall
score, the corpus size, and the full per-word breakdown. Because the score is corpus-
relative, it is a difficulty *signal*, not a measured accuracy. The same in Python is
`greek.terminology_rarity(text, corpus)`, whose result carries `.overall` and a
`.hardest(n)` helper.

### Backend flags (download/build on first use)

Each flag stands in for a `use_*()` activation in the Python API. The first time
you use one, it may download a model or build an index to the cache (a note goes
to stderr); after that, everything is offline.

| flag | activates | first-use cost |
|---|---|---|
| `--treebank` | the Perseus AGDT lexicon | shared prebuilt AGDT bundle; ~75 MB source fallback |
| `--tagger` | the generalizing POS tagger | shared prebuilt AGDT bundle; source training fallback |
| `--lemmatizer` | the edit-tree lemmatizer | shared prebuilt AGDT bundle; source training fallback |
| `--parser` | the pure-Python arc-eager dependency parser | shared prebuilt AGDT bundle; source training fallback |
| `--neural-lemmatizer` | the GreTa seq2seq lemmatizer (`[neural]`) | ~232 MB model |
| `--neural` | the **joint neural pipeline**: best tagger/parser/lemmatizer (`[neural]`) | ~173 MB model |
| `--neural-variant LABEL` | Runtime artifact for `--neural`: `default`, `fast`, `compact`, or `balanced`; only `default` is currently available | no additional download unless that label identifies a different released artifact |
| `--lsj` | LSJ glossing (also set by `greek gloss`) | ~15 MB prebuilt index; ~270 MB source fallback |

```bash
# heavy — fetches the model on first use, then offline:
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural
aegean greek pipeline "ἐν ἀρχῇ ἦν ὁ λόγος." --neural --neural-variant default
aegean greek parse "ἐν ἀρχῇ ἦν ὁ λόγος" --neural          # UD dependency tree
aegean greek tag "…" --treebank --tagger                  # AGDT lookup + perceptron tagger
```

### Loading real Greek works

`work` fetches a real text from Perseus canonical-greekLit / First1KGreek
(CC BY-SA, commit-pinned, cached once) and parses it into a corpus. `works` lists
a curated, verified catalog of 25 ids; `catalog` searches the full ~1,800-work
discovery index (offline metadata); for NT and LXX books see `aegean bible books`.
the loaders accept. The full id reference is on
[Greek Works and Books](Greek-Works-and-Books).

```bash
aegean greek works
# id              author        title
# tlg0012.tlg001  Homer         Iliad
# tlg0012.tlg002  Homer         Odyssey
# tlg0011.tlg002  Sophocles     Antigone
# tlg0059.tlg030  Plato         Republic
# …  (curated subset — the full canon is at https://scaife.perseus.org)

# heavy (network on first use):
aegean greek work tlg0012.tlg001                 # the Iliad: 24 books, ~127k tokens
aegean greek work tlg0012.tlg001 --ref 1.1-1.50  # just book 1, lines 1–50
aegean greek work tlg0012.tlg001 -o iliad.json   # save as a corpus file

# manage what you have downloaded:
aegean greek works --downloaded                  # list the works in your cache
aegean greek works --remove tlg0012.tlg001       # delete one downloaded work
aegean greek works --remove-author homer         # delete every downloaded Homer work
aegean greek works --remove-all                  # clear the whole downloaded library
```

#### The whole lifecycle, worked

Find a work, fetch it, confirm it is on disk, delete it. Every step below ran
as shown (the fetch touches the network once; everything after is local).

Find the id (`catalog` is offline metadata, instant):

```bash
aegean greek catalog --title crito
```
```
                Greek works (1 match)
┌────────────────┬────────┬───────┬────────┬─────────┐
│ id             │ author │ title │ greek  │ src     │
├────────────────┼────────┼───────┼────────┼─────────┤
│ tlg0059.tlg003 │ Plato  │ Crito │ Κρίτων │ perseus │
└────────────────┴────────┴───────┴────────┴─────────┘
Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10
```

Fetch it (downloads once, then it is cached):

```bash
aegean greek work tlg0059.tlg003
```
```
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

Confirm it is in the downloaded library (its row of the table):

```bash
aegean greek works --downloaded
# │ tlg0059.tlg003 │ Plato              │ Crito             │ perseus │ 64 KB   │
```

Read it like any corpus (`aegean show tlg0059.tlg003 43`, `aegean stats
tlg0059.tlg003`), and when you are done with it:

```bash
aegean greek works --remove tlg0059.tlg003
# removed tlg0059.tlg003  (Plato — Crito)
#
# removed 1 work from the cache.
```

`--ref` selects a section by the work's **declared citation scheme**: `1` (a book,
or a Stephanus section), `1.2` (a chapter), or `1.1-1.50` (a line range). The scheme is
read from the edition's TEI structure and varies by genre — verse is `book.line`, a
Stephanus-paged Plato dialogue is a single `section`, Aristotle is `chapter.subchapter`,
multi-book prose is `book.chapter.section` — so a **wrong `--ref` names the work's own
scheme** (e.g. `cited by book.line`) instead of only reporting a miss. A hyphen range must
stay within one textpart; for sibling sections, or a range that would cross textparts, use
a **comma list** (`--ref 1.1,1.5` or `--ref 1,3`), one document per entry. `--ref` also
addresses **margin milestones outside the `<div>` scheme** — a Stephanus sub-page (`17a`)
or a Bekker line (`1447a10`) an edition prints in the margin — by extracting the span
between that marker and the next marker of its kind. Perseus marks only every fifth Bekker
line, so `1447a10` returns lines 10-14 and only marked line numbers resolve; a whole Bekker
page-*column* works too (`1447a` = column `a`, the whole page being the comma list
`1447a,1447b`), as does `17a,17b`. A hyphen **range** of milestones is not yet supported
(use a comma list of the markers). To discover the
scheme before loading, call `greek.citation_scheme("tlg0012.tlg001")` (it returns the
ordered levels, e.g. `["book", "line"]`); the per-genre table is on
[Greek Works and Books](Greek-Works-and-Books#citation-schemes-how-a-work-is-addressed).
`--source` is `auto`/`perseus`/`first1k`; `--edition` picks a specific edition file.

For the Greek New Testament (5 editions), early manuscripts, Septuagint (LXX), and
patristic commentaries, use `aegean bible` ([CLI: Biblical & Koine Greek](CLI-Bible)).

**`catalog` is the full discovery index behind `works`.** Where `works` lists 25
curated highlights, `catalog` searches the **complete** bundled metadata for every
work with a Greek edition in Perseus canonical-greekLit + First1KGreek: 1,778 works
in all (768 from `perseus`, 1,010 from `first1k`). It's offline and instant: just
metadata, no fetch. Any id it prints goes straight to `aegean greek work`.

```bash
aegean greek catalog --author plato --limit 8
```
```
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

The bare `QUERY` argument is a catch-all substring over id, author, English title,
and Greek title; `--author/-a`, `--title/-t` (matches English **or** Greek), and
`--source perseus|first1k` are the targeted filters (all case-insensitive, all
combine with AND). `--limit/-n` caps the table, the `--json` list, and what
`--output/-o` saves alike (0 = all; the JSON keeps the untruncated total in
`matched`); `-o` picks its format by extension (`.json`/`.csv`/`.txt`):

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

Coverage is exactly what those open repositories hold at the pinned commit, so some
authors are genuinely absent upstream and therefore here too: `aegean greek catalog
sappho` honestly returns nothing rather than inventing an entry:

```bash
aegean greek catalog sappho
# No works match. Try a looser filter, or browse https://scaife.perseus.org
```

The same in Python is `greek.catalog(query=None, *, author=None, title=None,
source=None)`, returning a list of `{id, author, title, greek_title, source}` dicts;
`greek.popular_works()` stays the curated 25.

### Inspecting and preserving CoNLL-U files

The `conllu` group reads complete treebank documents without running a model. `inspect`
reports syntactic words, multiword ranges, empty nodes, enhanced-annotation presence,
and the explicit original-ID projection. Add `--strict` to reject malformed columns,
identifiers, row placement, references, and basic trees. `--json` or `-o` gives the
machine-readable summary.

```bash
aegean greek conllu inspect treebank.conllu --strict --json
aegean greek conllu export treebank.conllu -o checked-copy.conllu --strict
```

`export` copies the source bytes atomically, including comments, all ten columns, MWT
ranges, empty nodes, `DEPS`, `MISC`, and line endings. It never invokes the baseline or
neural pipeline. The separate `greek eval ud` path still predicts and scores only the
integer-ID syntactic-word projection, so gold structural annotations are not credited to
the model. A typed editorial form on a word row is encoded in the reserved
`AegeanFormState` MISC entry as URL-safe base64 JSON (schema 1); strict inspection
rejects malformed, duplicate, unknown-schema, or oversized entries, while lenient
inspection preserves the raw MISC value without decoding it.

### Reproducing the published numbers (`eval`)

`aegean greek eval TARGET` runs the official evaluators against fetched gold data:
heavy, but it reproduces pyaegean's measured accuracy. Targets: `ud`, `proiel`,
`nt`, `papygreek`, `verse`, `dbbe`, `tagger`, `lemmatizer`, `parser`.

```bash
# heavy: fetches gold data and the model
aegean greek eval ud --fold perseus --split test --neural
aegean greek eval ud --neural --bootstrap          # percentile CIs over the fold's sentences
aegean greek eval ud --drift                       # error analysis: POS confusions, per-POS accuracy
aegean greek eval proiel --drift                   # the same, for the out-of-AGDT PROIEL gold
aegean greek eval nt --drift                       # the same, for the Nestle 1904 New Testament
aegean greek eval ud --by-genre --neural           # score the fold sliced by literary genre
```

`--fold` picks the UD Ancient Greek fold (`perseus` or `proiel`) and `--split` the
split (`dev` or `test`); both are validated before anything is fetched. (The old
`--treebank` spelling for the fold selector is a deprecated alias: it still works
but warns, naming `--fold`.) The measured numbers save with `--output/-o` like any
other result table.
`--bootstrap` (ud only) reports each metric as `estimate [low, high]` instead of a
single point. `--drift` (ud, proiel, or nt) replaces the bare accuracy numbers with an
error analysis: a gold→predicted POS-confusion table, per-part-of-speech accuracy, the
common lemma confusions, and a seen-vs-unseen split, which separates systematic
annotation-convention divergence from scattered real error (the aggregate `evaluate_*`
numbers are unchanged). See [When the Tool Is Wrong](When-the-Tool-Is-Wrong) for how to
read the breakdown. `--by-genre` (ud only) buckets the fold by its `sent_id` author into
literary genres (epic, tragedy, prose) and scores each bucket separately. Note that the
leakage-clean Perseus test fold is prose-only, so today this returns a single `prose`
bucket; the machinery is in place for a future held-out epic/tragedy slice (see
[Benchmarks](Benchmarks)). `--batch-size N` (ud, nt, and `--by-genre`) runs the neural
model over N sentences per call: identical results, several times faster; it is
rejected where no batched loop exists (`proiel`, `--bootstrap`, `--drift`). The exact
figures and how they were measured are on
[Greek NLP](Greek-NLP) and [Limitations](Limitations#measured-accuracy-boundaries).

#### A worked run

The lightest useful combination: the pure-Python tagger (prebuilt models fetch
once with `agdt-derived`; here already cached, so the whole run took about two
seconds) on the Perseus **dev** split. Real output:

```bash
aegean greek eval ud --fold perseus --split dev --tagger
# aegean: activating the POS tagger (first use may download/build)…   [stderr]
```
```
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

How to read it: the backend flag decides which stack is scored, and only the
stages that ran are meaningful. With just `--tagger` no parser was activated,
so `parsed` is `False` and `uas`/`las`/`clas` read `None`; swap in `--neural`
and the same table fills in the dependency metrics (and takes much longer, as
the model fetches and then runs on every sentence). These dev-split numbers
are a working check, not the published figures: the published (test-split)
results and their protocol live in `docs/benchmarks.md` and on
[Greek NLP](Greek-NLP).

---


## Review — `aegean review …`

The review commands close the loop between machine analysis and human judgement: export
the toolkit's annotations to a spreadsheet, correct them, and read the corrections back.
Automation does not end the workflow; this is how a scholar keeps the final say and a
record of it.

| Command | What it does | Key flags | One-line example |
|---|---|---|---|
| `review export` | Write selected rows with predictions, analysis identity, inclusion reasons, and field-decision columns | `-o/--output` `--selection all\|flagged\|unverified\|sample` `--layout full\|editable` `--priority source\|calibrated-risk` `--budget N` repeatable `--field` `--sample-size` `--seed` `--reviewer` `--annotate` `--neural` `--with-confidence` `--confidence-domain` `--annotated-output` | `aegean review export nt -o review.csv --selection unverified --field pos --layout editable` |
| `review merge` | Combine copies of one export; retain field attribution and report disagreements | `--corpus/-c` `-o/--output` `--on-conflict error\|report` `--json` | `aegean review merge alice.csv bob.csv -c analysis.json -o merged.csv --on-conflict report` |
| `review apply` | Apply field decisions or corrections, preserving original predictions and review history | `-o/--output` (a `.json`/`.db`) `--reviewer NAME` | `aegean review apply analysis.json review.csv -o reviewed.json --reviewer "A. Scholar"` |

The run below uses the bundled `greek` sample, so you can follow it offline. It carries no
annotations of its own, so `--annotate` fills lemma and POS from the pipeline first; a corpus
that already has gold annotations (the Greek NT) needs no `--annotate`, and
`aegean review export nt -o review.csv` writes all 137,779 of its rows.

`--annotate` generates fresh lemma/POS predictions in the loaded copy, replacing existing
values and clearing prior lemma evidence and neural coverage. Previous lemma/POS
decisions become `stale`; their attribution and history survive, while reviews of
unchanged source morphology remain current. Keep the original corpus separately
when reviewing source annotations. Export saves the annotated copy beside the CSV;
use `--annotated-output analysis.json` to choose its path. Existing destinations
are refused. Merge and apply against this saved copy: running annotation again
creates a new analysis generation even if the displayed predictions agree.

Choose which rows to export with `--selection`:

| Mode | Rows exported |
|---|---|
| `all` (default) | Every word with a token position, including verified lemmas. |
| `flagged` | Rows whose existing review flag is true, normally identity/unresolved lemmas. |
| `unverified` | Words with an unverified requested field; `--field lemma` is the default. |
| `sample` | A seeded sample of unflagged rows, using `--sample-size N --seed N`. |

For `unverified`, only the string `true` (case-insensitive) excludes a word; empty
or unrecognized values remain included. None of these modes changes the CSV's
`needs_review` flag or applies a confidence threshold. Repeat `--field` to request
`lemma`, `pos`, `morph`, `head`, or `deprel`. Inclusion reasons are recorded in the
table. A sample of unflagged rows helps test what the existing flag misses.

When you want to spend limited editorial time on the predictions most likely to need a
human eye, combine `--neural --with-confidence --confidence-domain literary` (or
`documentary_native` for papyri) with `--priority calibrated-risk --budget 50`: `review export`
automatically loads the matching bundled calibration registry when none is active and orders
the highest-risk predictions first while keeping dependency sentences intact.

Fill `decision_lemma`, `decision_pos`, or `decision_morph` with a field action:

| Action | Effect |
|---|---|
| `accept` | Keep the displayed nonempty prediction and mark that field verified; leave its `correct_*` cell blank. |
| `correct` | Supply a different, nonempty `correct_*` value and mark that field verified. |
| `defer` / `reject` | Retain the prediction and mark that field unverified; leave its `correct_*` cell blank. |
| blank | Preserve correction-only behavior: a changed `correct_*` value corrects the field; blank or unchanged cells imply no approval. |

Add `reviewer`, `reviewer_note`, and `reviewer_evidence` for attribution and a
citation or link. Review is field-specific: accepting a lemma does not verify
POS, morphology, a dependency tree, or a lexical sense. The saved corpus records
verification and decisions in `Token.annotations`, alongside original
`<field>__pred` values and `review_history`. This is distinct from the pipeline's
`TokenRecord.lemma_verified` property, which derives from lemma-source evidence.
New snapshots also check available model/configuration identity, analysis generation,
source alignment, and predictions. Unavailable external/custom model identity is
explicitly unknown. Keep the read-only snapshot columns intact.

Dependency review uses `decision_head` / `decision_deprel` and the corresponding
correction columns. Selecting either field includes complete sentence context,
including parsed punctuation. Heads are 1-based indexes within that sentence;
0 means root. Corpus positions and source-token IDs are not head indexes. Missing
sentence ownership is refused. Edits must leave one root, valid head indexes,
matching root labels, and no cycles; invalid edits produce no partial changes.

```bash
# 1. export a reviewable table (add --layout editable for a compact spreadsheet + .companion.json)
aegean review export greek --annotate --annotated-output analysis.json -o review.csv
#    wrote 27 review rows to review.csv
#    record field decisions or corrections, then apply them to analysis.json

# 2. triage. The needs_review column flags identity/unresolved lemmas by default, and
#    --selection flagged exports only those: here the 7 forms the offline lemmatizer left
#    unresolved (Πηληϊάδεω, Ἀχιλῆος, Ἁλικαρνησσέος, …), each with evidence_class=unresolved.
aegean review export analysis.json --selection flagged -o triage.csv
#    wrote 7 review rows to triage.csv
#    This filter is not a confidence threshold; omit it to review all rows.

# 3. With the neural pipeline, export a compact 50-row calibrated-risk queue:
aegean review export greek --annotate --neural --with-confidence --confidence-domain literary \
    --layout editable --priority calibrated-risk --budget 50 -o queue.csv

# 4. Fill decision_* and, for corrections, correct_*; add reviewer identity, note, and evidence.
#    If several people review copies of the same export, merge them against its saved source:
aegean review merge alice.csv bob.csv -c analysis.json -o merged.csv --on-conflict report

aegean review apply analysis.json merged.csv -o greek-reviewed.json --reviewer "Review team"
```

Source-aware rows join by stable source-token ID and verify alignment and token
text; legacy rows use document id and position. A changed source or token is an
error, never a silent wrong-word correction. When export used `--annotate`, use
the saved annotated artifact for both `merge` and `apply`. Printed next-step
commands name that artifact and quote paths containing spaces. Merge also
preserves source whitespace and typed-form cells and retains individual reviewer
attribution in `reviewer_records`. See
[When the Tool Is Wrong](When-the-Tool-Is-Wrong) for the review workflow in context.

The default `--layout full` table carries all guarded `alignment_*` and `form_*` columns plus
`form_state_json` inline (they stay empty when a token has no typed editorial form). For a
cleaner spreadsheet view, pass `--layout editable`: it puts your decision and correction
columns first and moves the immutable snapshot and provenance columns into a SHA-256-bound
`<name>.companion.json` sidecar that `review merge` and `review apply` detect automatically.
In either layout, applying a correction refuses a row whose form state no longer matches the
exported corpus. Review files written before these columns remain readable and use the
existing identity and token-text checks.

---

