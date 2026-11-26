# Recipes

Copy-pasteable workflows from question to citable result, in Python and on the
[command line](CLI). Every snippet and output below was executed against the
shipped library and corpora.

Most workflows end with `cite()` so the exact dataset and subset reach your
bibliography. For installation and terminal setup, see
[Getting Started](Getting-Started); for the full command surface, see [CLI](CLI).

## What's on this page

| # | Recipe | Corpus / track | Needs a fetch? |
|---|--------|----------------|----------------|
| 1 | [Reconcile the accounting of a whole corpus, export the discrepancies](#1--reconcile-the-accounting-of-a-whole-corpus-export-the-discrepancies) | Linear A | no |
| 2 | [Map a word's distribution](#2--map-a-words-distribution) | Linear A | no (GeoJSON needs `[geo]`) |
| 3 | [Lemmatize and cite a chapter](#3--lemmatize-and-cite-a-chapter) | Greek | yes (the work) |
| 4 | [What vocabulary distinguishes a site? (keyness)](#4--what-vocabulary-distinguishes-a-site-keyness) | Linear B / DAMOS | yes (DAMOS) |
| 5 | [Sound-match a syllabic word against Greek](#5--sound-match-a-syllabic-word-against-greek) | cross-script | no |
| 6 | [Mine word-families from an undeciphered corpus (and cache it)](#6--mine-word-families-from-an-undeciphered-corpus-and-cache-it) | Linear A | no |
| 7 | [Ask a grounded question and audit the answer](#7--ask-a-grounded-question-and-audit-the-answer) | any | API key |
| 8 | [Scan a line of verse](#8--scan-a-line-of-verse) | Greek | no |
| 9 | [Type Greek without a Greek keyboard, then syllabify](#9--type-greek-without-a-greek-keyboard-then-syllabify) | Greek | no |
| 10 | [Read a deciphered syllabic word as Greek (the bridge)](#10--read-a-deciphered-syllabic-word-as-greek-the-bridge) | Linear B / Cypriot | no |
| 11 | [Find words by sign pattern](#11--find-words-by-sign-pattern) | any syllabic | no |
| 12 | [Build a compound query and pipe the JSON](#12--build-a-compound-query-and-pipe-the-json) | any | no |
| 13 | [Where does a word concentrate? (dispersion)](#13--where-does-a-word-concentrate-dispersion) | any | no |
| 14 | [Are two words associated? (collocation stats)](#14--are-two-words-associated-collocation-stats) | any | no |
| 15 | [Which signs are surprising inside a word?](#15--which-signs-are-surprising-inside-a-word) | Linear A | no |
| 16 | [Classify documents by structure](#16--classify-documents-by-structure) | Linear A | no |
| 17 | [Export the Greek NT as an annotated table](#17--export-the-greek-nt-as-an-annotated-table) | Greek NT | yes (NT) |
| 18 | [Gloss Koine vocabulary offline](#18--gloss-koine-vocabulary-offline) | Greek NT | no |
| 19 | [Build a SQLite database and full-text search it](#19--build-a-sqlite-database-and-full-text-search-it) | any | no |
| 20 | [Look up one sign in the inventory](#20--look-up-one-sign-in-the-inventory) | any syllabic | no |
| 21 | [Lock down reproducibility (versions + sha256)](#21--lock-down-reproducibility-versions--sha256) | datasets | no |
| 22 | [Put all of Homer in one searchable database](#22--put-all-of-homer-in-one-searchable-database) | Greek | yes (the works) |
| 23 | [Save a stats or keyness table to CSV](#23--save-a-stats-or-keyness-table-to-csv) | any | no |
| 24 | [Save a query as a reusable corpus, then reload it](#24--save-a-query-as-a-reusable-corpus-then-reload-it) | any | no |
| 25 | [Find a work in the catalogue, or bring in your own text](#25--find-a-work-in-the-catalogue-or-bring-in-your-own-text) | Greek | no |
| 26 | [Choose a Greek AI translation workflow](#26--choose-a-greek-ai-translation-workflow) | Greek | API key (generation only) |
| 27 | [Search 57,000 papyri without loading them (DDbDP)](#27--search-57000-papyri-without-loading-them-ddbdp) | Greek papyri / DDbDP | yes (DDbDP, ~219 MB) |
| 28 | [Package, verify, and hydrate a portable research bundle](#28--package-verify-and-hydrate-a-portable-research-bundle) | any | no (pointer corpora optional) |
| 29 | [Review annotations and adjudicate conflicts in the TUI](#29--review-annotations-and-adjudicate-conflicts-in-the-tui) | any | no (`[tui]` extra) |

For multi-step projects, [Workflows: end to end](#workflows-end-to-end) chains
these recipes into eight role-based walkthroughs:
[the epigraphist](#a--the-epigraphist-from-a-site-filter-to-a-citable-subset),
[the papyrologist](#b--the-papyrologist-ddbdp-without-loading-it),
[the literary classicist](#c--the-literary-classicist-catalogue-metre-gloss-citation),
[the New Testament scholar](#d--the-new-testament-scholar-gold-morphology-to-concordance),
[the corpus linguist](#e--the-corpus-linguist-numbers-with-a-receipt),
[the Aegean-scripts researcher](#f--the-aegean-scripts-researcher-exploratory-and-labeled-as-such),
[the AI-assisted translator](#g--the-ai-assisted-translator-key-gated), and
[the toolsmith](#h--the-toolsmith-one-database-and-tools-for-agents).

Reporting commands accept `--json` for piping into
[`jq`](https://jqlang.github.io/jq/) or Python/pandas. Commands whose primary job
is file output take `-o` (`export`, `db build`, `db add`, `review export`/`review
apply`, `plot`), and interactive entry points (`repl`, `tui`, `workbench`,
`quickstart`) have no JSON mode.

Every CLI corpus argument resolves through `aegean.read_corpus(spec)`: a
registered id (`lineara`), a Greek work id (`tlg0012.tlg001`), a saved `.json` or
`.db` file, or `-` for JSON on stdin. That lets commands chain directly (for
example, `aegean db build tlg0012.tlg001 -o iliad.db`, `aegean stats iliad.json`,
or `aegean export tlg0012.tlg002 -f csv -o odyssey.csv`).

---

## Workflows: end to end

Eight complete sessions chaining individual recipes from question to citable
output. Steps requiring a first-time download or an API key are marked. For help
matching a goal to a workflow, see [Choosing a Workflow](Choosing-a-Workflow).

### A · The epigraphist: from a site filter to a citable subset

*Extract the Greek inscriptions of Kamarina from I.Sicily, inspect a text, compute
characteristic vocabulary, and save a citable subset.* Add `--period` to narrow
by the editors' date strings.

```bash
aegean load isicily --site Kamarina --limit 3
# isicily: 174 matching document(s) (showing 3)
#  id           site       period                               words
#  ISic001075   Kamarina   Chrestos; age in years (?)           5
#  ISic001479   Kamarina   Second half of the 6th century BCE   1
#  ISic001480   Kamarina   4th or 2nd century BCE               6

aegean show isicily ISic003022                # verse epitaph for Hippo
# ISic003022  site=Kamarina  period=350 BCE — early 3rd century BCE
#   1: σωφροσύνην τιμῶσα
#   2: δικαιοσύνην τε σέβουσα
#   3: Ἱππὼ ἐν ἡλικίαι πνεῦμ’ ἔλιπεν βιότου

aegean keyness isicily --site Kamarina --top 5
#  item      target    reference   G2       log-ratio   p
#  τετάρτα   16/1107   0/27806     104.63   +9.70       1.5e-24
#  φράτρα    14/1107   0/27806     91.52    +9.51       1.1e-21
#  τα        17/1107   10/27806    76.36    +5.42       2.4e-18
#  ευτέρα    10/1107   0/27806     65.34    +9.04       6.3e-16
#  δεκάτα    9/1107    0/27806     58.80    +8.90       1.7e-14

aegean load isicily --site Kamarina -o kamarina.json
# wrote 174 documents to kamarina.json
aegean cite kamarina.json
# I.Sicily (ISicily/ISicily, CC BY 4.0), primary-Greek inscriptions
#   — https://github.com/ISicily/ISicily [subset: filter(site='Kamarina') → 174 of 2855 documents]
```

The top keyness terms reflect Kamarina's lead phratry tablets (`φράτρα` and Doric
feminine ordinals `τετάρτα`, `δεκάτα`). Tokens remain as inscribed, so fragments
(`τα`, `ευτέρα`) rank alongside complete words and must be inspected before
drawing conclusions.

**Bring your own EpiDoc.** Any token-carrier EpiDoc XML file (`<w>`, `<num>`,
`<g>`, `<pc>`, `<seg>`) imports directly into the same workflow:

```xml
<div type="edition" xml:lang="grc">
  <ab>
    <lb n="1"/><w>Ἀρτεμιδώρα</w> <w>χρηστὰ</w>
    <lb n="2"/><w>χαῖρε</w>
  </ab>
</div>
```

```bash
aegean import myinscription.xml --epidoc -o mine.json
# wrote 1 document(s) to mine.json
aegean show mine.json "MyColl 1"
# MyColl 1  site=Kamarina
#   1: Ἀρτεμιδώρα χρηστὰ
#   2: χαῖρε
```

The saved JSON accepts `stats`, `keyness`, `export`, and `cite`, with provenance
recording a local EpiDoc import.

**Task recipes used:**
[4 · keyness](#4--what-vocabulary-distinguishes-a-site-keyness) ·
[24 · save a subset](#24--save-a-query-as-a-reusable-corpus-then-reload-it) ·
[25 · bring in your own text](#25--find-a-work-in-the-catalogue-or-bring-in-your-own-text) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

### B · The papyrologist: DDbDP without loading it

*Find every papyrus addressed `στρατηγῷ` ("to the strategos").* `ddbdp` (57,331
papyri, ~4.4M tokens) ships as a SQLite database with FTS5. Search and stream it
instead of calling `aegean.load("ddbdp")`. First use fetches ~219 MB; queries
after that are instant:

```bash
aegean db search ddbdp "στρατηγῷ" --limit 5
#  doc              pos   text
#  aegyptus.96.10   13    στρατηγῷ
#  apf.67.374       218   στρατηγῷ
#  arctos.13.15     2     στρατηγῷ
#  bacps.27.18_2    1     στρατηγῷ
#  bgu.1.125        1     στρατηγῷ
```

In Python, gather all hits and stream matching documents in constant memory into
a reusable sub-database:

```python
import aegean
from aegean import db
from aegean.scripts.greek import ddbdp_db

path = ddbdp_db()                              # cached SQLite file
hits = db.search(path, "στρατηγῷ", limit=0)    # limit=0 returns all matches
print(len(hits), "attestations in", len({h[0] for h in hits}), "papyri")
# 1398 attestations in 1092 papyri

wanted = {doc_id for doc_id, pos, text in hits}
picked = [d for d in db.stream(path) if d.id in wanted]   # constant-memory scan

subset = aegean.Corpus(picked, script_id="greek", provenance=aegean.Provenance(
    source="DDbDP, Duke Databank of Documentary Papyri (papyri.info): papyri attesting στρατηγῷ",
    license="CC-BY-3.0 (DDbDP / Duke Collaboratory for Classics Computing, papyri.info)",
    url="https://github.com/papyri/idp.data",
))
db.to_sqlite(subset, "strategos.db")
print(subset.cite())
# DDbDP, Duke Databank of Documentary Papyri (papyri.info): papyri attesting στρατηγῷ
#   — https://github.com/papyri/idp.data
```

Inspect and analyze `strategos.db` directly:

```bash
aegean show strategos.db bgu.1.125
# bgu.1.125  site=Arsinoite  period=II/III spc
#   1: ι στρατηγῷ Ἀρσινοΐτου Ἡρακλείδου μερίδος
#   2: παρὰ Αὐρηλίου
#   3: ἀπογεγραμμένου διʼ ἑτέρου ὑπομνήτος. ὑπάρχει μοι ἐπʼ ἀμφόδου Θεσμοφορείου ἥμισυ μέρος
#   4: μερους οἰκίας, ἐν ᾧ ἀπογράφομαι

aegean stats strategos.db --top 5
#  item    count
#  καὶ     10087
#  τοῦ     5216
#  τῆς     2681
#  τῶν     2544
#  ἔτους   2196
```

**Task recipes used:**
[27 · DDbDP search](#27--search-57000-papyri-without-loading-them-ddbdp) ·
[19 · SQLite + FTS](#19--build-a-sqlite-database-and-full-text-search-it) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

### C · The literary classicist: catalogue, metre, gloss, citation

*Locate a passage of Homer, scan it, gloss it with Cunliffe, and cite the
commit-pinned edition.* Catalogue lookup is offline; fetching the TEI work
touches the network once and caches locally:

```python
from aegean import greek
greek.catalog("iliad")[0]
# {'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad', 'greek_title': 'Ἰλιάς', 'source': 'perseus'}
```

```bash
aegean greek work tlg0012.tlg001         # fetches once; cached after
#  documents      24
#  tokens         127339
#  first          tlg0012.tlg001:1
#  name           Ἰλιάς — Book 1
#  source         PerseusDL/canonical-greekLit (tlg0012.tlg001.perseus-grc2.xml)
#  data_version   PerseusDL/canonical-greekLit@d4fab69a2c26
```

Load lines 1.1–1.7, gloss with Cunliffe's Homeric lexicon (small one-time index
fetch), and cite:

```python
from aegean import greek

iliad = greek.load_work("tlg0012.tlg001", ref="1.1-1.7")
doc = iliad.documents[0]
print(" ".join(doc.tokens[i].text for i in doc.lines[0]))
# μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος

greek.use_lexicon("cunliffe")
for r in greek.pipeline("μῆνιν ἄειδε θεὰ"):
    print(r.text, "→", r.lemma, "·", greek.gloss(r.lemma, dictionary="cunliffe")[:38])
# μῆνιν → μῆνις · μῆνις: μῆνις ἡ. 1 Wrath, ire : μῆνιν ἄ
# ἄειδε → ἀείδω · ἀείδω: ἀείδω Fut. pple. in mid. form ἀ
# θεὰ → θεά · θεά: θεά -ᾶς, ἡ [fem. of θεός.] Dat. p

print(iliad.cite())
# Homer, Ἰλιάς 1.1-1.7. Digitized by the Perseus Digital Library / Open Greek and Latin.
#   — https://github.com/PerseusDL/canonical-greekLit/blob/d4fab69a2c26…/data/tlg0012/tlg001/tlg0012.tlg001.perseus-grc2.xml
```

```bash
aegean greek scan "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"
# —⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, spondee, dactyl, dactyl, final; caesura: penthemimeral
```

The citation pins the exact upstream commit. The offline lemmatizer is the
zero-download baseline; activate the treebank or neural backends for higher
measured accuracy ([Greek NLP](Greek-NLP)).

**Task recipes used:**
[25 · find a work in the catalogue](#25--find-a-work-in-the-catalogue-or-bring-in-your-own-text) ·
[3 · lemmatize and cite](#3--lemmatize-and-cite-a-chapter) ·
[8 · scan a line of verse](#8--scan-a-line-of-verse) ·
[18 · gloss offline](#18--gloss-koine-vocabulary-offline)

### D · The New Testament scholar: gold morphology to concordance

*Trace `ἀγάπη` through 1 John using Nestle 1904 gold annotations.* Nestle 1904
(CC0) carries curated lemma, Robinson morphology, Strong's number, and gloss per
token (fetched once on first use; pass `offline=True` for the bundled John 1 and
Philemon 1 sample):

```python
from aegean.greek import bible

jn = bible.load_nt("1 John")
verse = [t for t in jn.documents[3].tokens if t.annotations.get("ref") == "1John.4.8"]
for t in verse[-4:]:
    a = t.annotations
    print(f"{t.text:8} {a['lemma']:6} {a['morph']:9} Strong's {a['strongs']:>4}  {a['gloss']}")
# ὁ        ὁ      T-NSM     Strong's 3588  the
# Θεὸς     θεός   N-NSM     Strong's 2316  God, a god
# ἀγάπη    ἀγάπη  N-NSF     Strong's   26  love
# ἐστίν.   εἰμί   V-PAI-3S  Strong's 1510  I am, exist
```

Build a KWIC concordance with the query engine (and gloss any Koine word offline
with `bible.strongs_entry("ἀγάπη").gloss`, returning `'love'`, or
`greek.use_lexicon("dodson")` + `greek.gloss("ἀγάπη", dictionary="dodson")`):

```python
from aegean.analysis import FilterRow

sub = jn.query([FilterRow("ins-contains-word", "ἀγάπη")]).to_corpus(jn)
print(len(sub.documents), "of", len(jn.documents), "chapters attest ἀγάπη")
# 4 of 5 chapters attest ἀγάπη

rows = []
for doc in sub.documents:
    toks = doc.tokens
    for i, t in enumerate(toks):
        if t.text == "ἀγάπη":
            left = " ".join(x.text for x in toks[max(0, i - 3):i])
            right = " ".join(x.text for x in toks[i + 1:i + 4])
            rows.append(f"{t.annotations['ref']:12} {left:>28}  ἀγάπη  {right}")
print(len(rows), "attestations; the first three:")
for row in rows[:3]:
    print(row)
# 11 attestations; the first three:
# 1John.2.5                      ἐν τούτῳ ἡ  ἀγάπη  τοῦ Θεοῦ τετελείωται.
# 1John.2.15                    οὐκ ἔστιν ἡ  ἀγάπη  τοῦ Πατρὸς ἐν
# 1John.3.17                   αὐτοῦ, πῶς ἡ  ἀγάπη  τοῦ Θεοῦ μένει
```

Save and export the token table from the shell (recipe 17 lists all columns):

```bash
aegean query nt --where ins-contains-word=ἀγάπη -o agape.json
# wrote 20 inscriptions to agape.json
aegean export agape.json -f csv --level token -o agape.csv
# wrote 20 documents to agape.csv (csv)
aegean cite agape.json
# Nestle, E. (1904). Novum Testamentum Graece (Nestle 1904). Morphology/lemmatization (CC0)
#   via biblicalhumanities/Nestle1904. — https://github.com/biblicalhumanities/Nestle1904
#   [subset: query(Contains exact word: ἀγάπη) → 20 documents]
```

**Task recipes used:**
[17 · export the NT](#17--export-the-greek-nt-as-an-annotated-table) ·
[18 · gloss offline](#18--gloss-koine-vocabulary-offline) ·
[12 · compound query](#12--build-a-compound-query-and-pipe-the-json) ·
[24 · save a subset](#24--save-a-query-as-a-reusable-corpus-then-reload-it) ·
[23 · tables to CSV](#23--save-a-stats-or-keyness-table-to-csv)

### E · The corpus linguist: numbers with a receipt

*Run frequency, dispersion, keyness, and collocation over the DAMOS Linear B
corpus (~5,900 tablets, CC BY-NC-SA, ~3 MB one-time fetch) and record exact
provenance.*

```bash
aegean stats damos --top 5
#  item      count
#  pa-ro     230
#  ko-wo     188
#  pe-mo     173
#  o-na-to   154
#  e-ke      143

aegean dispersion damos o-na-to
#  item      freq   range/parts   DP      DPnorm
#  o-na-to   154    81/4135       0.873   0.873

aegean analyze assoc damos o-na-to ko-to-na
#  joint / w1 / w2 / docs   49 / 81 / 71 / 5932
#  chi_squared              2391
#  p_value                  0
#  log_likelihood           371.3
#  fisher_p                 3.856e-82
#  pmi_interval             [5.258022054925833, 6.059875157574912]

aegean keyness damos --site Thebes --top 5 -o thebes_key.csv
# wrote thebes_key.csv
```

```csv
item,target_count,target_total,reference_count,reference_total,log_likelihood,log_ratio,p_value
*63-te-ra-de,9,811,0,13680,51.9889272376043,8.324150018999573,5.581449320930576e-13
a-ko-da-mo,9,811,0,13680,51.9889272376043,8.324150018999573,5.581449320930576e-13
```

*o-na-to* ("lease plot") is frequent (154 tokens), concentrated (DP 0.873,
reflecting the Pylos land-tenure series), and tightly co-occurring with
*ko-to-na* (49 shared tablets, Fisher's p ≈ 3.9e-82); the Thebes top keys come
from the Fq series. Record the version, corpus fingerprint, and citation:

```python
import aegean

damos = aegean.load("damos")
print(aegean.__version__)          # 0.73.1
print(damos.fingerprint()[:16])    # ca93e51fd26a8f6c
print(damos.cite())
# Aurora, F. (2015). DAMOS (Database of Mycenaean at Oslo). Annotating a fragmentarily
#   attested language. Procedia - Social and Behavioral Sciences, 198, 21-31. — https://damos.hf.uio.no
```

Run `aegean data versions` to add the pinned SHA-256 (`fetched/damos-corpus
eab9ccdfc4324b62… cached`) to your methods section.

**Task recipes used:**
[4 · keyness](#4--what-vocabulary-distinguishes-a-site-keyness) ·
[13 · dispersion](#13--where-does-a-word-concentrate-dispersion) ·
[14 · collocation stats](#14--are-two-words-associated-collocation-stats) ·
[23 · tables to CSV](#23--save-a-stats-or-keyness-table-to-csv) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

### F · The Aegean-scripts researcher: exploratory, and labeled as such

*Analyze structure in undeciphered Linear A, test a structural hypothesis against
a null model, and map find-sites.* All exploratory commands label their output as
unverified leads:

```bash
aegean balance lineara HT13
#  doc    marker   stated   computed   diff   balances   eligible (tolerance)
#  HT13   KU-RO    130.5    131.0      0.5    NO         yes

aegean stats lineara --signs --top 5
#  item   count
#  KU     307
#  KA     284
#  *301   274
#  SI     240
#  A      202

aegean analyze clusters lineara --top 3       # exploratory word families
#  JA-SA → JA-SA-SA-RA-ME, JA-SA, JA-SA-JA, JA-SA-MU, JA-SA-SA, JA-SA-SA-RA
#  A-TA  → A-TA, A-TA-DE, A-TA-NA, A-TA-NA-JE, A-TA-NA-TE, A-TA-RE
#  I-DA  → I-DA, I-DA-A, I-DA-DA, I-DA-MI
```

Test pattern hypotheses against a null model. Are adjacent repeated signs (as in
`JA-SA-SA-RA-ME`) more common in Linear A words than expected by chance?

```python
import aegean
from aegean.analysis import monte_carlo_p

words = [t.text for d in aegean.load("lineara") for t in d.words if "-" in t.text]

def repeat_rate(ws):
    n = 0
    for w in ws:
        signs = w.split("-")
        n += sum(1 for a, b in zip(signs, signs[1:]) if a == b)
    return n / len(ws)

res = monte_carlo_p(repeat_rate(words), repeat_rate, words, null="within_word", n=999)
print(f"observed {res.observed:.4f}  null mean {res.null_mean:.4f}  p = {res.p_value}")
# observed 0.0384  null mean 0.0424  p = 0.782
```

The observed rate falls well within the null distribution (p = 0.782). For the
deciphered Linear B script, the Greek-reading bridge applies directly, and any
word's attestations map geographically:

```bash
aegean bridge linearb ko-wo
# ko-wo → κόρος   (boy, son)

aegean geo lineara --word KU-RO
# lineara: 'KU-RO' attested at 3 located site(s)
#  site            lat     lon     count
#  Haghia Triada   35.06   24.79   32
#  Phaistos        35.05   24.81   1
#  Zakros          35.1    26.26   1
```

**Task recipes used:**
[1 · reconcile the accounting](#1--reconcile-the-accounting-of-a-whole-corpus-export-the-discrepancies) ·
[6 · word families](#6--mine-word-families-from-an-undeciphered-corpus-and-cache-it) ·
[10 · the Greek-reading bridge](#10--read-a-deciphered-syllabic-word-as-greek-the-bridge) ·
[2 · map a word](#2--map-a-words-distribution) ·
[5 · sound-matching](#5--sound-match-a-syllabic-word-against-greek)

### G · The AI-assisted translator (key-gated)

*(Grounding runs locally once its model and dictionary assets are cached;
generation requires a hosted provider key or a local server.)* Inspect the local
provisional analysis before sending any request:

```python
from aegean import greek, translate

neural = greek.GreekPipeline.neural()  # [neural]: contextual predictions + UD parse
for item in translate.grounding_for(
    "ὁ δὲ θεὸς ἐγείρει τοὺς νεκρούς.", "greek",
    mode="morphology", greek_pipeline=neural,
):
    print(item.render())  # content, evidence status, source, and provenance
```

The opening item reports backend availability and coverage. Token lines retain
raw UD features; clause evidence preserves dependency links, including
subordinate predicates and explicit coordination. All items remain predictions,
and omitted or erroneous attachments are passed as predicted without hidden
rewrites.

With a provider configured (recipe 7), run grounded translation and optional
post-hoc checking:

```bash
aegean ai translate "ὁ δὲ θεὸς ἐγείρει τοὺς νεκρούς." --greek-backend neural
aegean ai translate "ὁ δὲ θεὸς ἐγείρει τοὺς νεκρούς." --greek-backend neural --verify --trace
# Output depends on provider and model; every response carries the
# [EXPLORATORY · translate · <provider>/<model>] header. Translation .txt
# exports append the audit trace; .json retains audit data and checking draft.
```

`result.trace()` separates prompted provisional evidence from post-hoc runtime
configuration. See recipe 26 for selecting grounding modes, backends, and
failure policies.

**Task recipes used:**
[26 · choose a Greek AI translation workflow](#26--choose-a-greek-ai-translation-workflow) ·
[7 · ask a grounded question](#7--ask-a-grounded-question-and-audit-the-answer)

### H · The toolsmith: one database, and tools for agents

*Combine multiple corpora into one FTS-indexed SQLite file and expose the
toolkit over MCP.* `combine` resolves every source through `read_corpus`,
merges provenance across all inputs, and builds an FTS5 index when saving `.db`:

```bash
aegean combine isicily igcyr -o west.db     # Sicily + Cyrenaica in one database
# wrote 3852 documents to west.db (merged 2 sources)

aegean db search west.db "Δάματρι" --limit 4
#  doc           pos   text
#  ISic003009    0     Δάματρι
#  ISic003109    0     Δάματρι
#  ISic003427    0     Δάματρι
#  igcyr003400   1     Δάματρι

aegean cite west.db
# Merged corpus of: I.Sicily (ISicily/ISicily, CC BY 4.0), primary-Greek inscriptions;
#   IGCyr²/GVCyr² — Greek inscriptions of Cyrenaica (incl. Doric and verse)
#   [merged: 2 corpora → 3852 documents]
```

One search queries both Doric regions (`Δάματρι`, dative of Demeter, across
Sicily and Cyrenaica). To expose the toolkit to AI agents over MCP, install
`pip install "pyaegean[mcp]"` and configure your client to run `aegean-mcp`:

```python
from aegean.mcp_server import TOOLS
print(len(TOOLS), "tools:", ", ".join(t.__name__ for t in TOOLS[:6]), "…")
# 29 tools: list_corpora, corpus_info, show_document, search_signs, search_text, balance_accounts, query_corpus …
```

MCP tools accept registry and catalogue ids only (never arbitrary filesystem
paths) and return structured error dicts. See [MCP](MCP).

**Task recipes used:**
[22 · all of Homer in one database](#22--put-all-of-homer-in-one-searchable-database) ·
[19 · SQLite + FTS](#19--build-a-sqlite-database-and-full-text-search-it) ·
[24 · save a subset](#24--save-a-query-as-a-reusable-corpus-then-reload-it) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

---

## 1 · Reconcile the accounting of a whole corpus, export the discrepancies

*Check whether stated `KU-RO` totals on Haghia Triada tablets match the sums of
their line items, export discrepancies, and cite the subset:*

```python
import json
import aegean
from aegean.analysis import balance_check

ht = aegean.load("lineara").filter(site="Haghia Triada")
discrepancies = []
for doc in ht:
    for chk in balance_check(doc):
        if not chk.balances:
            discrepancies.append({"doc": doc.id, "marker": chk.marker,
                                  "stated": chk.stated_total, "computed": chk.computed_sum})

with open("discrepancies.json", "w", encoding="utf-8") as f:
    json.dump(discrepancies, f, ensure_ascii=False, indent=2)

print(len(discrepancies), "discrepancies")   # 29
print(ht.cite())
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.
#   — https://github.com/mwenge/lineara.xyz [subset: filter(site='Haghia Triada') …]
```

```bash
aegean balance lineara --json | jq '[.[] | select(.balances | not)]' > discrepancies.json
aegean plot balance lineara -o balance.png      # stated vs computed scatter plot
```

Reconciliation infers section boundaries heuristically; inspect discrepancies
against the editions. See [Linear A](Linear-A).

For exact rational equality, pass `balance_check(doc, exact=True)` or
`aegean balance lineara --exact --json` (default `balances` uses a `1e-6` float
tolerance). `account_eligible` selects intact documents with at least one
qualifying total using default allowance `max(1, 0.10 * abs(stated_total))`;
`--tolerance 0` retains the absolute-one floor, while `--exact` removes the
allowance. JSON output records rational `exact_difference`, `exact_balances`, and
the eligibility policy.

## 2 · Map a word's distribution

*Count `KU-RO` attestations by find-site and look up Pleiades-aligned
coordinates:*

```python
from collections import Counter
import aegean
from aegean import geo

corpus = aegean.load("lineara")
sites = Counter(d.meta.site for d in corpus
                if any(t.text == "KU-RO" for t in d.words))
print(sites.most_common(3))   # [('Haghia Triada', 32), ('Phaistos', 1), ('Zakros', 1)]

coord = geo.site_coordinates()["Haghia Triada"]
print(coord.lat, coord.lon, coord.pleiades_uri)
# 35.06 24.79 https://pleiades.stoa.org/places/589672
```

With `[geo]` installed (`pip install "pyaegean[geo]"`),
`geo.word_distribution(corpus, "KU-RO")` returns an EPSG:4326 GeoDataFrame, and
`aegean geo lineara --output sites.geojson` writes GeoJSON. See
[Geography](Geography).

## 3 · Lemmatize and cite a chapter

*Fetch the Iliad (commit-pinned, cached after first download), lemmatize the
opening tokens, and cite the edition:*

```python
import aegean

iliad = aegean.greek.load_work("tlg0012.tlg001")     # Iliad, Perseus edition
doc = iliad.documents[0]                             # Book 1
text = " ".join(t.text for t in doc.tokens[:40])

for r in aegean.greek.pipeline(text)[:3]:
    print(r.text, "→", r.lemma)
# μῆνιν → μῆνις · ἄειδε → ἀείδω · θεὰ → θεά

print(iliad.cite())
# Homer, Ἰλιάς. Digitized by the Perseus Digital Library / Open Greek and Latin. — …
```

```bash
aegean greek work tlg0012.tlg001 -o iliad.json       # save work as Corpus JSON
aegean greek pipeline "μῆνιν ἄειδε θεά" --json       # per-token analysis records
```

Selected well-known works (`aegean greek works` prints all 25):

| id | author | title |
|----|--------|-------|
| `tlg0012.tlg001` | Homer | Iliad |
| `tlg0012.tlg002` | Homer | Odyssey |
| `tlg0020.tlg001` | Hesiod | Theogony |
| `tlg0020.tlg002` | Hesiod | Works and Days |
| `tlg0085.tlg005` | Aeschylus | Agamemnon |
| `tlg0011.tlg004` | Sophocles | Oedipus Tyrannus |
| `tlg0006.tlg003` | Euripides | Medea |
| `tlg0016.tlg001` | Herodotus | Histories |
| `tlg0003.tlg001` | Thucydides | History of the Peloponnesian War |
| `tlg0059.tlg002` | Plato | Apology |
| `tlg0086.tlg010` | Aristotle | Nicomachean Ethics |

Restrict a fetch with `--ref`, such as
`aegean greek work tlg0012.tlg001 --ref 1.1-1.10`. The full canon is indexed at
[Scaife](https://scaife.perseus.org) and offline in `greek.catalog()` (recipe 25).

The offline pipeline is the baseline tier; pass `--treebank` or `--neural`
(`[neural]` extra) for higher measured accuracy ([Greek NLP](Greek-NLP)).

## 4 · What vocabulary distinguishes a site? (keyness)

*Compare Pylos against the rest of the DAMOS Linear B corpus (~5,900 tablets, ~3
MB fetch):*

```python
import aegean
from aegean.analysis import keyness

damos = aegean.load("damos")
pylos = damos.filter(site="Pylos")
rest = [d for d in damos.documents if d.meta.site != "Pylos"]

for r in keyness(pylos, rest)[:3]:
    print(f"{r.item:10} G²={r.log_likelihood:.0f}  log-ratio={r.log_ratio:+.1f}")
# pe-mo      G²=254  log-ratio=+8.5     ('seed' — land-tenure series)
# o-na-to    G²=226  log-ratio=+8.4     ('lease plot')
# to-so-de   G²=210  log-ratio=+8.3

print(pylos.cite())   # Aurora (2015), DAMOS … [subset: filter(site='Pylos') …]
```

```bash
aegean keyness damos --site Pylos --top 5
#  item     target     reference   G2       log-ratio   p
#  pe-mo    173/6998   0/7493      254.09   +8.54       3.3e-57
#  o-na-to  154/6998   0/7493      225.97   +8.37       4.5e-51
#  to-so-de 143/6998   0/7493      209.71   +8.26       1.6e-47
#  ko-to-na 130/6998   0/7493      190.52   +8.13       2.5e-43
#  e-ke     141/6998   2/7493      188.30   +6.24       7.5e-43
aegean plot keyness damos --site Pylos -o pylos.png
```

Interpret G² (significance) together with log-ratio (effect size) and
`aegean dispersion` ([Analysis](Analysis)).

Keyness also splits by scribal hand (`meta.scribe` in DAMOS v2):

```python
h117 = damos.filter(scribe="117")
rest117 = [d for d in damos.documents if d.meta.scribe != "117"]
keyness(h117, rest117)[:5]
```

```bash
aegean keyness damos --scribe 117 --top 10
aegean analyze hands damos                    # rank every recorded hand
```

DAMOS carries CC BY-NC-SA 4.0 (NonCommercial) and is fetched on demand. See
[Linear B](Linear-B) and [Data & Provenance](Data-and-Provenance).

## 5 · Sound-match a syllabic word against Greek

*Compare Linear B `qa-si-re-u` phonetically against Greek candidates:*

```python
from aegean.analysis import nearest, phonetic_compare

cmp = phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek")
print(round(cmp.similarity, 2))                       # 0.56
print([(c.a, c.b, c.op) for c in cmp.alignment][:2])  # [('k', '', 'del'), ('w', 'b', 'sub-far')] — qʷ→b reflex

candidates = ["ποιμήν", "βασιλεύς", "πατήρ", "θεός", "δοῦλος"]
print(nearest("qa-si-re-u", "linearb", candidates, "greek", top=2, fold_aspiration=True))
# [('βασιλεύς', 0.4375), ('πατήρ', 0.6625)]
```

```bash
aegean analyze compare qa-si-re-u βασιλεύς
aegean analyze nearest po-me greek --top 5
aegean analyze distance qa-si-re-u pa-si-re-u        # 0.100 (already romanized)
```

Use the relative ranking rather than absolute distances, because defective
syllabic spelling inflates raw edit distance ([Analysis](Analysis)). Choose a
candidate lexicon matched to your research question. `compare` and `nearest`
take script ids and romanize automatically; `distance` compares already-romanized
strings directly.

## 6 · Mine word-families from an undeciphered corpus (and cache it)

*Group Linear A words sharing stems and productive suffixes, enabling the opt-in
analysis cache for repeated runs:*

```python
import aegean
from aegean.analysis import find_morphological_clusters

aegean.cache.enable()      # optional; or set PYAEGEAN_ANALYSIS_CACHE=1

clusters = find_morphological_clusters(aegean.load("lineara").word_frequencies())
print(len(clusters), "clusters")          # 81
print(clusters[0].stem, "→", [m.word for m in clusters[0].members[:4]])
# JA-SA → ['JA-SA-SA-RA-ME', 'JA-SA', 'JA-SA-JA', 'JA-SA-MU']
```

```bash
aegean analyze clusters lineara --top 10
aegean cache                              # inspect cache; --clear wipes it
```

## 7 · Ask a grounded question and audit the answer

*(Hosted providers require an extra such as `pip install "pyaegean[anthropic]"`
and an API key; `local` requires an OpenAI-compatible local server and no key.)*
Supply local corpus evidence, then inspect the provenance trace:

```python
import aegean
from aegean import ai

corpus = aegean.load("lineara")
grounding = ai.corpus_context(corpus, limit=10) + ai.cooccurrence_evidence(corpus, "KU-RO")

r = ai.ask("What can be said about the function of KU-RO?", grounding=grounding)
print(r.labeled())     # [EXPLORATORY · ask · …]
print(r.trace())       # grounding facts grouped by source
```

```bash
aegean ai ask "What is KU-RO?" --corpus lineara --trace
aegean ai providers             # anthropic · gemini · grok · local · openai · openrouter
aegean ai eval                  # grounding-fidelity eval
```

Registered providers and extras:

| provider | extra | example model family |
|----------|-------|----------------------|
| `anthropic` | `pip install "pyaegean[anthropic]"` | Claude |
| `openai` | `pip install "pyaegean[openai]"` | GPT |
| `gemini` | `pip install "pyaegean[gemini]"` | Gemini |
| `grok` | `pip install "pyaegean[grok]"` | Grok |
| `openrouter` | `pip install "pyaegean[openrouter]"` | multiple vendors via `vendor/model` ids |
| `local` | `pip install "pyaegean[local]"` | Ollama / LM Studio / llama.cpp (OpenAI SDK), no key |

Every generative output is an exploratory hypothesis. See [AI Layer](AI-Layer)
and the
[validation issue form](https://github.com/ryanpavlicek/pyaegean/issues/new/choose).

## 8 · Scan a line of verse

*Scan dactylic hexameter and iambic trimeter using fixed metrical templates and
curated lexical synizesis:*

```python
from aegean import greek

s = greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
print(s.pattern)   # —⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×
for foot in s.feet[:2]:
    print(foot.name, foot.syllables, foot.quantities)
# dactyl ('ἄν', 'δρα', 'μοι') ('heavy', 'light', 'light')
# dactyl ('ἔν', 'νε', 'πε') ('heavy', 'light', 'light')

print(greek.scan_trimeter("τί δ᾽ ἔστι; λέξον· εἰ φρενῶν ἐτήτυμον").pattern)
# ×—⏑—|×—⏑—|×—⏑×
```

```bash
aegean greek scan "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
aegean greek scan "τί δ᾽ ἔστι; λέξον· εἰ φρενῶν ἐτήτυμον" --meter trimeter
#  ×—⏑—|×—⏑—|×—⏑×
#  trimeter: metron, metron, metron; caesura: penthemimeral
aegean greek scan "$(cat line.txt)" --json | jq '.feet[].name'
aegean greek quantities "μῆνιν"        # per-syllable heavy/light/common
```

Supported `--meter` values:

| meter | line | note |
|-------|------|------|
| `hexameter` | dactylic hexameter | epic (default) |
| `pentameter` | elegiac pentameter | second line of elegiac couplet |
| `trimeter` | iambic trimeter | spoken tragedy/comedy |
| `glyconic` | glyconic | aeolic lyric (fixed template) |
| `pherecratean` | pherecratean | aeolic |
| `sapphic_hendecasyllable` | sapphic hendecasyllable | aeolic |
| `adonean` | adonean | aeolic |
| `alcaic_hendecasyllable` | alcaic hendecasyllable | aeolic |
| `alcaic_enneasyllable` | alcaic enneasyllable | aeolic |
| `alcaic_decasyllable` | alcaic decasyllable | aeolic |

Lines requiring unlisted synizesis exit non-zero with a diagnostic instead of
guessing. See [Meters](Meters).

## 9 · Type Greek without a Greek keyboard, then syllabify

*Convert ASCII Beta Code to polytonic Unicode, syllabify, inspect accentuation,
transcribe to IPA, and list candidate morphological parses:*

```python
from aegean import greek

greek.betacode_to_unicode("mh=nin")            # 'μῆνιν'
greek.syllabify("ἄνθρωπος")                    # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.strip_diacritics("μῆνιν")                # 'μηνιν'
greek.to_ipa("λόγος")                          # 'loɡos' (reconstructed)

# offline candidate morphological analyses (ambiguity retained):
for cand in greek.analyze("λόγος"):
    print(cand.lemma, cand.pos, cand.case, cand.number, cand.gender)
# λόγος NOUN nom sg masc
# λόγος NOUN nom sg fem
```

```bash
aegean greek betacode "mh=nin"           # μῆνιν (--reverse converts back to Beta Code)
aegean greek syllabify "ἄνθρωπος"
aegean greek accent "λόγος"
aegean greek strip "μῆνιν"
aegean greek ipa "λόγος"
aegean greek morph "λόγος"               # λόγος [NOUN nom sg masc] / [NOUN nom sg fem]
```

If polytonic accents render as boxes on Windows, configure a polytonic terminal
font ([Getting Started → Seeing Greek correctly](Getting-Started#seeing-greek-correctly)).

## 10 · Read a deciphered syllabic word as Greek (the bridge)

*Map Linear B or Cypriot words to Greek using known phonetic values and spelling
rules:*

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)

aegean bridge cypriot pa-si-le-u-se
# pa-si-le-u-se → βασιλεύς   (king)

aegean bridge linearb qa-si-re-u --json | jq '.greek'
```

Available only for deciphered scripts (`linearb`, `cypriot`). For undeciphered
Linear A and Cypro-Minoan, use recipe 5 for exploratory phonetic comparison. See
[Linear B](Linear-B) and [Cypriot](Cypriot).

## 11 · Find words by sign pattern

*Match fixed-length sign templates where each `*` matches one sign:*

```bash
aegean search lineara "KU-*" --json | jq '.matches[] | "\(.word)\t\(.count)"'
# "KU-RO"   37
# "KU-PA"   4
# "KU-RA"   2
# "KU-RE"   2
# ...

aegean search lineara "KU-*-RO"          # three-sign words KU-?-RO
```

```python
import aegean
from aegean.analysis import word_matches_sign_pattern

corpus = aegean.load("lineara")
freqs = corpus.word_frequencies()
hits = [(w, c) for w, c in freqs if word_matches_sign_pattern(w, "KU-*")]
print(sorted(hits, key=lambda x: -x[1])[:3])
# [('KU-RO', 37), ('KU-PA', 4), ('KU-RA', 2)]
```

Works on any syllabic corpus (`lineara`, `linearb`, `cypriot`, `cyprominoan`,
`damos`, `sigla`). For variable-length prefixes (such as `KU-PA₃-NU`), use the
query engine in recipe 12.

## 12 · Build a compound query and pipe the JSON

*Query Linear A words starting with `KU` with AND/OR/NOT filters and JSON
output:*

```bash
aegean query lineara --fields                 # list queryable fields
aegean query lineara --where word-prefix=KU --output-kind words --limit 6
#  word           count
#  KU-RO          34
#  KU-PA₃-NU      7
#  KU-NI-SU       5
#  KU-PA          4
#  KU-MI-NA-QE    2
#  KU-PA₃-NA-TU   2

# AND by default; prefix with "or:" to OR, "!" to negate:
aegean query lineara --where site-is="Haghia Triada" --where or:word-prefix=KU --json \
  | jq '.matched.inscriptions'         # 55
```

`--json` truncates the `inscriptions` array at `--limit` (default 25) while
`.matched.inscriptions` holds the full count; pass `--limit 0` for all matches.
Available fields depend on the corpus (`aegean query CORPUS --fields`). Python
equivalent: `aegean.analysis.run_query`. See [Analysis](Analysis).

Word query tables default to **document frequency** (`KU-RO` appears in 34
inscriptions); pass `--count-unit token` to count all 37 tokens.
`--view surface|normalized|lemma` controls comparison keys (normalized keeps
diacritics and iota subscript; missing lemmas are excluded without running an
analyzer). `--statuses` filters both token status and typed editorial segments.
Query JSON includes denominator, exclusions, normalization, and count unit in
`metadata`; `aegean stats ... --details --json` emits the corresponding receipt
for token frequency tables.

## 13 · Where does a word concentrate? (dispersion)

*Measure whether `KU-RO` is evenly distributed or concentrated using Gries' DP
(0 = even, 1 = concentrated):*

```bash
aegean dispersion lineara KU-RO
#  item    freq   range/parts   DP      DPnorm
#  KU-RO   37     34/559        0.850   0.851

aegean dispersion lineara --top 5            # rank corpus
aegean dispersion lineara --signs --top 5    # by sign instead of word
```

```python
import aegean
from aegean.analysis import dispersion

corpus = aegean.load("lineara")
d = dispersion(corpus, "KU-RO")
print(round(d.dp, 3), d.range, "of", d.parts)   # 0.85 34 of 559
```

Pair DP with keyness G² to distinguish broad subcorpus vocabulary from terms
clumped in a handful of documents ([Analysis](Analysis)).

## 14 · Are two words associated? (collocation stats)

*Test whether `KU-RO` and `KI-RO` co-occur across documents above chance using
χ², log-likelihood, Fisher's exact test, and a PMI confidence interval:*

```bash
aegean analyze assoc lineara KU-RO KI-RO
#  joint / w1 / w2 / docs   5 / 34 / 12 / 1721
#  chi_squared              78.75
#  p_value                  7.055e-19
#  log_likelihood           23.94
#  fisher_p                 1.595e-06
#  pmi_interval             [3.1720137984039996, 5.621837690118523]

aegean analyze cooccur lineara KU-RO --top 5     # top co-occurring words
#  KI-RO        5
#  *306-TU      4
#  KU-PA₃-NU    4
#  SA-RA₂       4
#  *324-DI-RA   3
```

```python
import aegean
from aegean.analysis import log_likelihood_ratio_2x2, fishers_exact

corpus = aegean.load("lineara")
docs = [{t.text for t in d.words} for d in corpus]
total = len(docs)
joint = sum(1 for s in docs if "KU-RO" in s and "KI-RO" in s)   # 5
n1    = sum(1 for s in docs if "KU-RO" in s)                     # 34
n2    = sum(1 for s in docs if "KI-RO" in s)                     # 12

print(round(log_likelihood_ratio_2x2(joint, n1, n2, total), 2))  # 23.94
print(fishers_exact(joint, n1, n2, total))                       # 1.60e-06
```

Prefer Fisher's exact test when joint counts are small. See [Analysis](Analysis).

## 15 · Which signs are surprising inside a word?

*Score per-transition surprisal (in bits) with a token-weighted sign-bigram
model to flag unusual spellings:*

```python
import aegean
from aegean.analysis import train_sign_bigram_model, word_surprisal

corpus = aegean.load("lineara")
model = train_sign_bigram_model(corpus.word_frequencies())

ws = word_surprisal(model, "KU-RO")
print("mean bits/transition:", round(ws.mean, 2))    # 2.16
print([(s.from_, s.to, round(s.bits, 2)) for s in ws.steps])
# [('^', 'KU', 4.03), ('KU', 'RO', 2.06), ('RO', '$', 0.39)]
```

`^` and `$` mark word boundaries. High surprisal on a hapax flags possible
foreign names, abbreviations, or transcription errors for manual inspection. See
[Analysis](Analysis) and [Limitations](Limitations).

## 16 · Classify documents by structure

*Triage Linear A documents into `accounting`, `libation`, `list`, `text`, or
`other` using rule-based structural features:*

```bash
aegean analyze structure lineara --json | jq 'to_entries | sort_by(-.value)'
# accounting 134 · libation 18 · list 6 · text 1 · other (the rest)
```

```python
import aegean
from collections import Counter
from aegean.analysis import classify_structure

corpus = aegean.load("lineara")
counts = Counter(classify_structure(d) for d in corpus.documents)
print(counts.most_common())
```

These labels use heuristic cues (numeral density, libation vocabulary, line
shape) for sampling and triage, never as a formal epigraphic typology. See
[Linear A](Linear-A).

## 17 · Export the Greek NT as an annotated table

*Export Nestle 1904 with gold lemma, Robinson morphology, Strong's number, and
gloss as one row per token:*

```bash
aegean export nt -f csv -o nt_tokens.csv --level token
# wrote 260 documents to nt_tokens.csv (csv)
```

This writes 137,779 token rows across 260 chapters with columns:

| column | example | meaning |
|--------|---------|---------|
| `doc_id`, `line_no`, `position` | `Matt 1`, `1`, `0` | location |
| `text` | `Βίβλος` | surface token |
| `kind` | `word` | token kind (`word`, `logogram`, `numeral`, `separator`, `punct`, `unknown`) |
| `status` | `certain` | editorial reading status |
| `site` | (empty) | find-site (blank for literary texts) |
| `period` | `Koine` | document period label |
| `lemma` | `βίβλος` | gold dictionary headword |
| `morph` | `N-NSF` | Robinson morphology tag |
| `strongs` | `976` | Strong's number |
| `normalized` | `Βίβλος` | NFC-normalized form |
| `upos` | `NOUN` | reconciled UD part of speech |
| `ref` | `Matt.1.1` | canonical reference |
| `gloss` | `a written book, roll, or volume` | short gloss |

Only columns populated by the corpus are emitted (`aegean export lineara -f csv
--level token` writes only `doc_id,line_no,position,text,kind,status,site,period`).

```python
import aegean
from aegean.greek import bible

nt = aegean.load("nt")                     # full NT corpus
print(len(nt.documents), "chapters")       # 260
t = nt.documents[0].tokens[0]
print(t.text, t.annotations["lemma"], t.annotations["upos"], t.annotations["strongs"])
# Βίβλος βίβλος NOUN 976

# or load one passage (pass offline=True for the bundled John 1 / Philemon 1 sample):
john = bible.load_nt("John", ref="1.1-1.5")
print(len(john.documents[0].tokens), "tokens")   # 61
print(len(bible.nt_books()), "books")            # 27
```

`--level token` works with `csv` and `parquet`; other formats are `json`,
`epidoc`, and `sqlite`. The NT dataset is CC0 (Nestle 1904 base + CC0
annotations). Run `aegean bible books nt` to list all 27 books and accepted
aliases (`matthew`/`matt`/`mt`). See [New Testament](New-Testament) and
[Greek NLP](Greek-NLP).

## 18 · Gloss Koine vocabulary offline

*Look up Koine glosses and Strong's entries offline using the bundled Dodson
lexicon (CC0):*

```python
from aegean import greek
from aegean.greek import bible

greek.use_lexicon("dodson")
print(greek.gloss("λόγος", dictionary="dodson"))
# λόγος: a word, speech, divine utterance, analogy
print(greek.gloss("ἀρχή", dictionary="dodson"))
# ἀρχή: ruler, beginning
print(bible.strongs_entry("G3056").gloss)
# word
```

```bash
aegean bible strongs λόγος        # Strong's / Dodson Koine gloss
```

**Additional hosted dictionaries.** `greek.use_lexicon(id)` also activates
`middle-liddell` (concise classical), `cunliffe` (Homeric), `autenrieth`
(Homeric), `abbott-smith` (New Testament), or `lsj`, fetching a 0.1–15 MB index
on first use:

```python
greek.use_lexicon("cunliffe")
print(greek.gloss("μῆνις", dictionary="cunliffe"))       # μῆνις: μῆνις ἡ. 1 Wrath, ire …

greek.use_lexicon("abbott-smith")
print(greek.gloss("πίστις", dictionary="abbott-smith"))  # πίστις: faith; belief; trust; …
```

For non-redistributable dictionaries (Slater, Montanari, DGE, Bailly), generate
a Logeion deep-link offline:

```python
greek.lexicon_link("μήνιδος")
# 'https://logeion.uchicago.edu/%CE%BC%CE%AE%CE%BD%CE%B9%CE%B4%CE%BF%CF%82'
```

`lexicon_link` targets the lemma when the active lemmatizer resolves one, and
falls back to the surface form otherwise (pass `lemmatize=False` to force the
surface form). Shell commands: `aegean greek lexica`,
`aegean greek gloss μῆνις --dict cunliffe`, and
`aegean greek lexicon-link μήνιδος`. See
[Greek NLP → the lexicon registry](Greek-NLP#more-dictionaries-the-lexicon-registry).

## 19 · Build a SQLite database and full-text search it

*Store any corpus in SQLite with FTS5 indexing for SQL access and fast token
search:*

```bash
aegean db build lineara -o la.sqlite
# wrote 1721 documents to la.sqlite

aegean db search la.sqlite "KU-RO"
#  doc     pos   text
#  HT9a    25    KU-RO
#  HT9b    20    KU-RO
#  HT11a   7     KU-RO
#  ...
```

The schema holds `documents`, `tokens`, and `tokens_fts` tables readable by any
SQLite client (`aegean export CORPUS -f sqlite -o …` writes the same format).
Overwriting an existing database runs inside a SQLite online-backup transaction
so active WAL readers keep their snapshot; a busy writer raises a lock error
without corrupting existing data. For resumable, document-by-document annotation
of large databases, run `aegean db annotate la.sqlite --neural` (or
`aegean.db.annotate_sqlite_job`). See [CLI](CLI).

## 20 · Look up one sign in the inventory

*Inspect glyph, codepoint, phonetic value, and script attributes for any
syllabic sign:*

```bash
aegean sign linearb pa
#  label              PA
#  glyph              𐀞
#  codepoint          U+1001E
#  phonetic           pa
#  attrs.bennett      B003
#  attrs.unicodeName  LINEAR B SYLLABLE B003 PA
#  attrs.signClass    syllabogram
#  attrs.commodity    None
```

```python
import aegean
inv = aegean.get_script("linearb").sign_inventory
sign = inv.by_label("PA")
print(sign.glyph, hex(sign.codepoint), sign.phonetic)   # 𐀞 0x1001e pa
```

Bundled corpus sizes included inside the wheel:

| corpus id | `aegean.load(...)` | contents |
|-----------|--------------------|----------|
| `lineara` | 1721 documents | full GORILA Linear A (Apache-2.0) |
| `linearb` | 18 documents | bundled Linear B sample (fetch `damos` for full corpus) |
| `cypriot` | 180 documents | bundled Cypriot syllabic corpus |
| `cyprominoan` | 2 documents | bundled Cypro-Minoan sample |
| `greek` | 5 documents | bundled Greek sample passages (use `greek.load_work` / `bible.load_nt` for full works) |

Fetched corpora (`damos`, `nt`, `sigla`, `isicily`, `iip`, `iospe`, `igcyr`,
`aphrodisias`, `crete`, `edh`, `ddbdp`, `patrologia`, `apostolic-fathers`,
`pseudepigrapha`, `byzantine`, `homer-scholia`) download on first use. See
[Data & Provenance](Data-and-Provenance).

## 21 · Lock down reproducibility (versions + sha256)

*Record exact package and dataset hashes for a methods section:*

```bash
aegean data list                  # fetchable datasets with downloaded status and sizes
aegean data versions              # reproducibility manifest (version + SHA-256)
aegean data store                 # local store path and contents
aegean data fetch damos-corpus    # one-time download (no-op once cached)
aegean data remove damos-corpus   # delete one dataset (--all clears all)
```

```python
import aegean
print(aegean.__version__, aegean.registered_scripts())
# 0.73.1 ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

Include `aegean --version` and the relevant rows from `aegean data versions` (or
package everything into a portable research bundle in recipe 28). Set
`PYAEGEAN_CACHE` to relocate the store. See
[Data & Provenance](Data-and-Provenance) and [Installation](Installation).

## 22 · Put all of Homer in one searchable database

*Fetch both Homeric epics, combine them into one FTS-indexed SQLite file, and
search across all 48 books:*

```bash
aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db
# wrote 48 documents to homer.db (merged 2 sources)

aegean db search homer.db "μῆνιν" --limit 4
#  doc                 pos    text
#  tlg0012.tlg001:1    0      μῆνιν
#  tlg0012.tlg001:1    613    μῆνιν
#  tlg0012.tlg001:5    270    μῆνιν
#  tlg0012.tlg001:5    3629   μῆνιν
```

The Iliad and Odyssey contribute 24 books each with distinct ids (`<work>:<book>`).
On colliding ids, `--on-conflict first|last|suffix` sets resolution (default
`error`). `aegean cite homer.db` credits both editions.

To append additional works to an existing database without rebuilding, use
`aegean db add` (upserts by document id and updates affected FTS rows):

```bash
aegean db build tlg0012.tlg001 -o homer.db      # Iliad
aegean db add   tlg0012.tlg002 -o homer.db      # append Odyssey
# added/updated 24 documents in homer.db
```

Python equivalent:

```python
import aegean

homer = aegean.combine([
    aegean.read_corpus("tlg0012.tlg001"),       # Iliad
    aegean.read_corpus("tlg0012.tlg002"),       # Odyssey
])
print(len(homer.documents), "books")            # 48
homer.to_sql("homer.db")
print("merged" in homer.cite())                 # True

# Corpus.merge(*others, dedupe=...) is the method form; Corpus.subset(ids)
# extracts selected document ids back out.
```

First-time work fetches use the network; combining, merging, and `db add` run
offline on cached corpora. See [CLI](CLI) and [Greek NLP](Greek-NLP).

## 23 · Save a stats or keyness table to CSV

*Write frequency, keyness, dispersion, search, or `analyze` outputs directly to
`.csv`, `.json`, or `.txt` using stdlib writers (no pandas required):*

```bash
aegean stats lineara --top 5 -o freq.csv
```

```csv
item,count
KU-RO,37
SA-RA₂,20
KI-RO,16
*411-VS,15
A-TA-I-*301-WA-JA,11
```

Keyness writes counts, totals, G², log-ratio, and p-value per row:

```bash
aegean keyness lineara --site "Haghia Triada" --top 5 -o key.csv
```

```csv
item,target_count,target_total,reference_count,reference_total,log_likelihood,log_ratio,p_value
KU-RO,35,704,2,677,35.23079267167269,4.072863421882666,2.928562076939772e-09
SA-RA₂,20,704,0,677,27.23397833629945,5.301132409555783,1.802626974304909e-07
KI-RO,16,704,0,677,21.741443442187872,4.987974524296153,3.119782173367935e-06
*411-VS,0,704,15,677,21.55806861667444,-5.010615905449176,3.432754272946782e-06
A-TA-I-*301-WA-JA,0,704,11,677,15.775475780295547,-4.579981551119314,7.13210199579011e-05
```

Use `.json` for structured records or `.txt` for formatted tables. The same `-o`
option works on `aegean ai` commands (`aegean ai translate … -o out.json`),
preserving `exploratory`, provenance, structured audit data, and any checking
draft; translation `.txt` exports append the full trace automatically. See
[AI Layer](AI-Layer), [Analysis](Analysis), and [CLI](CLI).

## 24 · Save a query as a reusable corpus, then reload it

*Save matched inscriptions from a [compound query](#12--build-a-compound-query-and-pipe-the-json)
to `.json` or `.db` with the query recorded in provenance:*

```bash
aegean query lineara --where word-prefix=KU -o ku.json
# wrote 69 inscriptions to ku.json
```

Pass the saved file to any corpus command:

```bash
aegean stats ku.json --top 5
#  item        count
#  KU-RO       37
#  KI-RO       10
#  KU-PA₃-NU   8
#  SA-RU       6
#  KU-NI-SU    5

aegean cite ku.json
# Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.
#   — https://github.com/mwenge/lineara.xyz [subset: query(Word starts with: KU) → 69 documents]
```

Write directly to `.db` to include an FTS5 index:

```bash
aegean query lineara --where word-prefix=KU -o ku.db
aegean db search ku.db "KU-RO" --limit 3
#  doc     pos   text
#  HT9a    25    KU-RO
#  HT9b    20    KU-RO
#  HT11a   7     KU-RO
```

Python equivalent:

```python
import aegean
from aegean.analysis import FilterRow

la = aegean.load("lineara")
res = la.query([FilterRow("word-prefix", "KU")])
subset = res.to_corpus(la)                          # Corpus with subset: note
print(len(subset.documents))                        # 69

subset.to_json("ku.json")
again = aegean.read_corpus("ku.json")
print(again.cite().split("[")[-1])
# subset: query(Word starts with: KU) → 69 documents]
```

See [Analysis](Analysis) and [Data & Provenance](Data-and-Provenance).

## 25 · Find a work in the catalogue, or bring in your own text

*Search the bundled 1,778-work Greek catalogue offline, or import local `.txt`,
directory, or `.csv` texts into a standard `Corpus`.*

**Search the catalogue.** `greek.catalog()` indexes all `-grc` works across
Perseus and First1KGreek at the pinned commits (beyond the 25 curated works in
recipe 3):

```python
from aegean import greek

len(greek.catalog())                 # 1778 (768 perseus + 1010 first1k)
greek.catalog("odyssey")
# [{'id': 'tlg0012.tlg002', 'author': 'Homer', 'title': 'Odyssey',
#   'greek_title': 'Ὀδύσσεια', 'source': 'perseus'}]
```

```bash
aegean greek catalog --author plato --limit 3
# ┌────────────────┬────────┬───────────┬────────────────────┬─────────┐
# │ id             │ author │ title     │ greek              │ src     │
# ├────────────────┼────────┼───────────┼────────────────────┼─────────┤
# │ tlg0059.tlg001 │ Plato  │ Euthyphro │ Εὐθύφρων           │ perseus │
# │ tlg0059.tlg002 │ Plato  │ Apology   │ Ἀπολογία Σωκράτους │ perseus │
# │ tlg0059.tlg003 │ Plato  │ Crito     │ Κρίτων             │ perseus │
# └────────────────┴────────┴───────────┴────────────────────┴─────────┘
# … and 36 more — narrow with --author/--title, or --limit 0 to list all (-o to save).
```

Pass the discovered id (`tlg0012.tlg002`) to `greek.load_work` or
`aegean greek work` (the only networked step; recipe 3). Coverage reflects the
pinned commits, so authors absent upstream return empty lists
(`greek.catalog("Sappho")` → `[]`).

**Import local text.** `aegean import` converts `.txt`, folders, or `.csv` into
`.json` or `.db` corpora usable with every command. Imports default to
`token_view="all"`, preserving decoded source text, punctuation, numerals,
foreign text, and character spans while keeping lexical words in `Document.words`:

```bash
# john1.txt: ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.
aegean import john1.txt -o john1.json
# wrote 1 document(s) to john1.json

aegean stats john1.json --top 4
#  item    count
#  λόγος   3
#  ἦν      3
#  ὁ       3
#  καὶ     2
```

Python equivalent (`from_text`, `from_text_file`, `from_csv`, `from_text_dir`):

```python
from aegean import io, greek

text = "ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος."
corpus = io.from_text(text, script_id="greek", doc_id="john1.1")
print(len(corpus.documents[0].words))           # 17
print(len(corpus.documents[0].tokens))          # 20 (includes commas and period)
print(corpus.documents[0].source_text == text)  # True
print(corpus.word_frequencies()[:3])            # [('λόγος', 3), ('ἦν', 3), ('ὁ', 3)]

for r in greek.pipeline(text)[:3]:
    print(r.text, r.upos, r.lemma)
# ἐν ADP ἐν
# ἀρχῇ NOUN ἀρχή
# ἦν VERB εἰμί
```

Imported corpora set `license="user-supplied"` so `cite()` records local input
instead of fabricating an edition. CLI `CORPUS` arguments accept `.json` and
`.db` only; import `.txt`/`.csv` first (pass `--split paragraph|line` to split
documents). Pass `token_view="words"` (`--token-view words`) only if you want
word-only import without source text or spans. See
[Your own corpus](Data-and-Provenance#from-a-file-you-already-have-aegean-import)
and [Finding any other work](Greek-Works-and-Books#3-finding-any-other-work).

**Review one field at a time.** Export source annotations directly or add
`--annotate` to generate predictions before exporting:

```bash
aegean review export john1.json --annotate --annotated-output john1-analysis.json --selection unverified -o review.csv
# Edit review.csv (or triage interactively with `aegean tui --review review.csv`; see recipe 29):
aegean review apply john1-analysis.json review.csv -o reviewed.json
```

Set `decision_lemma`, `decision_pos`, or `decision_morph` to `accept`, `correct`,
`defer`, or `reject`. `accept` verifies an unchanged prediction; `correct`
requires a differing `correct_*` value. Record `reviewer`, `reviewer_note`, and
`reviewer_evidence`. Blank cells never approve predictions. Stable token ids and
source alignment bind the table to the corpus; reanalysis marks superseded
decisions stale. See [Greek NLP](Greek-NLP) and recipe 29.

---

## 26 · Choose a Greek AI translation workflow

*(Grounding runs locally once model and dictionary assets are cached; generation
requires a hosted API key or a local server.)* Select `mode` based on the passage
and backend accuracy; erroneous parses or glosses can mislead the model.

```python
from aegean import greek, translate

neural = greek.GreekPipeline.neural()  # contextual morphology + UD parse

text = "καὶ ἡγοῦμαι σκύβαλα εἶναι, ἵνα Χριστὸν κερδήσω."   # Philippians 3:8
result = translate.translate(text, mode="morphology", greek_pipeline=neural)
print(result.labeled())        # [EXPLORATORY · translate · <provider>/<model>] + notes
```

`style="annotated"` (default) displays model-reported uncertainty and change
notes; `style="concise"` prints the translation concisely while keeping audit
details in `data`, JSON, and `trace()`. On structured responses, `result.text`
holds only the translation and `result.data` holds `uncertainties`, `changes`
(before/after, reason, evidence), and `raw_response`. Check `format_status`
before reading structured fields: malformed responses stay verbatim with
unavailable fields set to `None` and trigger no repair call.

`verify=True` runs an ungrounded draft call followed by a checking call against
full grounding. The original draft stays in `result.draft`. Exact wording
comparison flags edits absent from the model's change list without scoring
linguistic accuracy. Save `result.to_json("translation.json")` or inspect
`result.trace()` to preserve both stages; CLI `--style concise --verify -o
out.json` preserves identical audit fields, and translation `.txt` exports append
the full trace.

Grounding defaults to `best-effort` (failures logged in `grounding_runtime` and
`trace()`). Use `grounding_failure="strict"` (`--grounding-failure strict`) to
abort before generation when required analysis fails. See
[AI Layer → Hybrid translation](AI-Layer#hybrid-translation).

Four grounding modes:

| mode | prompt evidence | use when |
|------|-----------------|----------|
| `"morphology"` *(default)* | token analyses, raw UD features, clause links, optional rare-word flags, idiom glosses | general Greek passages |
| `"full"` | morphology plus optional concise rare-word dictionary candidates | obscure, technical, or documentary vocabulary |
| `"lemma"` | legacy lemmas + gated LSJ glosses | reproducing earlier behavior |
| `"none"` | no automatic grounding; explicit `grounding=` items retained | bare-text baseline or custom evidence only |

Inspect grounding locally without an API key:

```python
greek.use_lsj(); greek.use_lexicon("abbott-smith")   # common-sense-first NT lexicon

for item in translate.grounding_for(
    text, "greek", mode="full", greek_pipeline=neural
):
    print(item.render())
```

`"full"` glosses come from common-sense-first dictionaries (Middle Liddell,
Cunliffe, Abbott-Smith) gated to rare words, excluding LSJ's etymologically
ordered lead sense (where καιρός opens with "a row of thrums in the loom" before
"the right time").

Dictionary matches are candidate glosses, not disambiguated senses. Raw tense
and aspect tags preserve their source convention (`Tense=Past` does not imply
past event time in subjunctives, infinitives, or participles, and missing aspect
is not filled in as aorist).

Pass `grounding=ai.annotation_evidence(corpus)` to supplement automatic
predictions with edition annotations and current field-level review decisions
without certifying or replacing unreviewed predictions.

Morphology grounding can reduce grammatical mistakes (voice, subject/object,
case), and `"full"` glosses can help on rare vocabulary, bounded by local
analysis accuracy and model capability. Every result remains a labeled
exploratory hypothesis. `ai.grounding_regime(text, corpus=...)` provides an
exploratory `help`/`neutral`/`hurt` pre-call signal. See [AI Layer](AI-Layer).

## 27 · Search 57,000 papyri without loading them (DDbDP)

`ddbdp` (57,331 papyri, ~4.4M tokens) ships as an FTS5 SQLite database. Search
and stream it instead of calling `aegean.load("ddbdp")`:

```bash
aegean db search ddbdp "βασιλέως" --limit 3   # fetches ~219 MB on first use; instant after
```

```python
from aegean.scripts.greek import ddbdp_db
from aegean import db

for doc in db.stream(ddbdp_db()):   # one document at a time, constant memory
    ...
```

`aegean.load("ddbdp")` materializes the full corpus for whole-corpus statistics
at the cost of a couple of minutes and >1 GB RAM.

## 28 · Package, verify, and hydrate a portable research bundle

*Package a corpus (or filtered subset), review tables, analysis receipts,
workbench state, and citations into one deterministic, SHA-256-verified `.zip`
archive (`aegean-research-bundle/1`), with zero extra dependencies:*

```bash
# 1. Create a bundle (add --review, --receipt, or --state to include companion files)
aegean bundle create ht_study.zip --corpus lineara --site "Haghia Triada" \
  --title "Haghia Triada Linear A study"
# Created ht_study.zip (aegean-research-bundle/1, 3 members, corpus=pointer, redistributable=yes)

# 2. Inspect manifest and verify archive safety + SHA-256 member checksums
aegean bundle inspect ht_study.zip
aegean bundle verify ht_study.zip
# PASS: ht_study.zip (3 members verified, redistributable=yes)

# 3. Verify, unpack, and reconstruct the corpus (add --fetch for uncached remote corpora)
aegean bundle hydrate ht_study.zip ./hydrated_study
# Hydrated ht_study.zip → ./hydrated_study (docs=1110, reviews=0, receipts=0)
```

Under the default `--embed-corpus auto` policy, redistributable corpora (such as
`cypriot` or user-supplied JSON) embed directly as deterministic `corpus.json.gz`,
whereas corpora carrying non-commercial (`CC BY-NC*`) or restricted license
clauses (such as `damos` or `lineara`'s image rights string) omit the text and
store a `CorpusReference` pointer with dataset id, version, URL, SHA-256,
license, and filter spec so the bundle stays redistributable. Pass
`--embed-corpus always` for a private non-redistributable snapshot
(`redistributable=no`).

Python equivalent:

```python
import aegean
from aegean.bundle import create_bundle, verify_bundle, hydrate_bundle

cypriot = aegean.load("cypriot")
manifest = create_bundle(
    "cypriot_study.zip",
    corpus=cypriot,
    dataset="cypriot",
    title="Cypriot syllabic study",
)
report = verify_bundle("cypriot_study.zip")
assert report.ok

hydrated = hydrate_bundle("cypriot_study.zip", dest="./hydrated_cypriot")
print(len(hydrated.corpus), "documents")   # 180 documents
```

## 29 · Review annotations and adjudicate conflicts in the TUI

*Triage low-confidence predictions or resolve disagreements between two
reviewers interactively in the terminal UI (`pip install "pyaegean[tui]"`):*

```bash
# 1. Export an editable review table from an analyzed corpus
aegean review export john1.json --annotate --annotated-output john1-analysis.json \
  --selection unverified -o review.csv

# 2. Open the review table directly in the TUI
aegean tui --review review.csv

# Or pass --review twice to merge two reviewers' copies and adjudicate conflicts:
aegean tui --review alice.csv --review bob.csv --corpus john1-analysis.json
```

Inside the Review screen (`ReviewScreen`), sentence context, morphological
predictions, offline lexicon glosses, and conflict options display beside the
token queue:

| Key | Action |
|-----|--------|
| `a` | accept current prediction |
| `e` | edit correction, note, or evidence |
| `1` / `2` / `3` | select numbered reviewer option on a conflicted field |
| `d` / `x` | defer or reject prediction |
| `n` / `p` | jump to next or previous unresolved token |
| `f` | cycle filter (`all`, `unresolved`, `conflicts`, `flagged`) |
| `s` | save back to CSV (preserving immutable snapshot hashes and `.companion.json`) |

After saving (`s`), apply the adjudicated CSV back to the saved analysis:

```bash
aegean review apply john1-analysis.json review.csv -o reviewed.json
```

See [TUI](TUI) and [Validation and Review](Validation-and-Review).

---

## Notes & limitations

- **Outputs depend on dataset versions.** Counts above reflect the shipped
  datasets and can shift on upstream updates; pin versions with `cite()`,
  `aegean data versions`, or `aegean bundle create`.
- **Heuristic analyses are exploratory leads.** Accounting reconciliation
  (recipe 1), structure classification (16), morphological clusters (6), and
  sign surprisal (15) infer structure absent from the editions. Verify against
  the source documents.
- **Cross-script phonetic matching is a ranking signal**, not an absolute score
  (recipe 5), because defective syllabic spelling inflates edit distances.
- **AI outputs are exploratory** (recipes 7 and 26). Hosted providers require
  credentials; `local` requires a running local server. Every result carries an
  exploratory label and provenance trace and must never be cited as an attested
  reading.

See [Limitations](Limitations) for project-wide caveats and
[For Specialists](For-Specialists) for methodological details.
