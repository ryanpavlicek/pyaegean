# Recipes

Short, copy-pasteable end-to-end workflows: each one goes from a question to a
citable result, in Python and (where natural) from the [command line](CLI).
Every snippet on this page has been **run against the shipped library and
corpora; the outputs shown are real.** Treat this as a cookbook: skim the table
below, jump to the recipe you need, copy it, change the corpus or the word.

A thread runs through most of them: **finish with `cite()`**, so the exact data
you used lands in your paper's references. If you're brand new, start with
[Getting Started](Getting-Started); for the full command reference see [CLI](CLI).

## What's on this page

| # | Recipe | Corpus / track | Needs a fetch? |
|---|--------|----------------|----------------|
| 1 | [Reconcile a corpus' accounting, export the discrepancies](#1--reconcile-the-accounting-of-a-whole-corpus-export-the-discrepancies) | Linear A | no |
| 2 | [Map a word's distribution](#2--map-a-words-distribution) | Linear A | no (GeoJSON needs `[geo]`) |
| 3 | [Lemmatize and cite a chapter](#3--lemmatize-and-cite-a-chapter) | Greek | yes (the work) |
| 4 | [What vocabulary distinguishes a site? (keyness)](#4--what-vocabulary-distinguishes-a-site-keyness) | Linear B / DAMOS | yes (DAMOS) |
| 5 | [Sound-match a syllabic word against Greek](#5--sound-match-a-syllabic-word-against-greek) | cross-script | no |
| 6 | [Mine word-families from an undeciphered corpus](#6--mine-word-families-from-an-undeciphered-corpus-and-cache-it) | Linear A | no |
| 7 | [Ask a grounded question — and audit the answer](#7--ask-a-grounded-question--and-audit-the-answer) | any | API key |
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

Those are the single moves. For whole projects there is a second index:
[Workflows: end to end](#workflows-end-to-end), just below, chains the recipes
into eight walkthroughs, one per kind of reader:
[the epigraphist](#a--the-epigraphist-from-a-site-filter-to-a-citable-subset),
[the papyrologist](#b--the-papyrologist-ddbdp-without-loading-it),
[the literary classicist](#c--the-literary-classicist-catalogue-metre-gloss-citation),
[the New Testament scholar](#d--the-new-testament-scholar-gold-morphology-to-concordance),
[the corpus linguist](#e--the-corpus-linguist-numbers-with-a-receipt),
[the Aegean-scripts researcher](#f--the-aegean-scripts-researcher-exploratory-and-labeled-as-such),
[the AI-assisted translator](#g--the-ai-assisted-translator-key-gated), and
[the toolsmith](#h--the-toolsmith-one-database-and-tools-for-agents).

Throughout, the `--json` flag is your friend: every CLI command emits clean JSON
on stdout, so you can pipe into [`jq`](https://jqlang.github.io/jq/) or load it
straight into Python/pandas.

One thing worth knowing before you start, because the last few recipes lean on
it: **anywhere a command takes a corpus, it takes more than an id.** A registered
id (`lineara`), a Greek work id (`tlg0012.tlg001`), a path to a saved `.json` or
`.db` corpus, or `-` for JSON on stdin all work the same way, so you can build a
database straight from a work (`aegean db build tlg0012.tlg001 -o iliad.db`), run
`aegean stats iliad.json`, or `aegean export tlg0012.tlg002 -f csv -o odyssey.csv`
without writing any Python. In Python the equivalent is
`aegean.read_corpus(spec)`. That one rule is what lets recipes 22–24 chain
commands together.

---

## Workflows: end to end

The numbered recipes below are single moves; this section chains them into
whole working sessions. Eight walkthroughs, one per kind of reader, each
running from a research question to a citable result, in the CLI and in Python
as each step is most natural. Every output shown is real, produced against the
shipped corpora; the steps that touch the network (a first-time fetch) or need
an API key are marked. Each walkthrough ends with links back to the task
recipes it builds on. To match your audience or goal (teaching, research,
exploratory, benchmarking) to a workflow, see [Choosing a Workflow](Choosing-a-Workflow).

### A · The epigraphist: from a site filter to a citable subset

*You work on Sicilian epigraphy and want the Greek of one city: Kamarina.*
Filter the I.Sicily corpus by find-site, read an inscription, ask what
vocabulary sets the site apart, and leave with a citable subset. (Add
`--period` to any of these commands to narrow by date as well; the period
strings are the editors' own.)

```bash
aegean load isicily --site Kamarina --limit 3
# isicily: 174 matching document(s) (showing 3)
#  id           site       period                               words
#  ISic001075   Kamarina   Chrestos; age in years (?)           5
#  ISic001479   Kamarina   Second half of the 6th century BCE   1
#  ISic001480   Kamarina   4th or 2nd century BCE               6

aegean show isicily ISic003022                # a verse epitaph for Hippo
# ISic003022  site=Kamarina  period=350 BCE — early 3rd century BCE
#   1: σωφροσύνην τιμῶσα
#   2: δικαιοσύνην τε σέβουσα
#   3: Ἱππὼ ἐν ἡλικίαι πνεῦμ’ ἔλιπεν βιότου

aegean keyness isicily --site Kamarina --top 5
#  item      target    reference   G2       log-ratio   p
#  τετάρτα   16/1107   0/27812     104.63   +9.70       1.5e-24
#  φράτρα    14/1107   0/27812     91.53    +9.51       1.1e-21
#  τα        17/1107   10/27812    76.36    +5.42       2.4e-18
#  ευτέρα    10/1107   0/27812     65.34    +9.04       6.3e-16
#  δεκάτα    9/1107    0/27812     58.80    +8.90       1.7e-14

aegean load isicily --site Kamarina -o kamarina.json
# wrote 174 documents to kamarina.json
aegean cite kamarina.json
# I.Sicily (ISicily/ISicily, CC BY 4.0), primary-Greek inscriptions
#   — https://github.com/ISicily/ISicily [subset: filter(site='Kamarina') → 174 of 2855 documents]
```

The keyness table is the city's lead phratry tablets speaking: φράτρα itself
and the Doric feminine ordinals that number the phratries (τετάρτα, δεκάτα).
Text is kept as inscribed, so fragmentary tokens (τα, ευτέρα) rank alongside
whole words: inspect before you interpret.

**Bring your own EpiDoc.** The same path works for editions pyaegean does not
ship. Any EpiDoc TEI file whose tokens are carried by `<w>`/`<num>`/`<g>`/`<seg>`
elements imports directly; this is the edition div of `myinscription.xml`
(its TEI header carries the `<idno>` and `<origPlace>`):

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

The imported corpus takes every command above (`stats`, `keyness`, `export`,
`cite`), and its provenance honestly records a local EpiDoc import.

**Task recipes used:**
[4 · keyness](#4--what-vocabulary-distinguishes-a-site-keyness) ·
[24 · save a subset](#24--save-a-query-as-a-reusable-corpus-then-reload-it) ·
[25 · bring in your own text](#25--find-a-work-in-the-catalogue-or-bring-in-your-own-text) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

### B · The papyrologist: DDbDP without loading it

*You want every papyrus addressed στρατηγῷ, "to the strategos".* The Duke
Databank (`ddbdp`, 57,331 papyri) ships as a SQLite database, so the working
method is search and stream, never `aegean.load("ddbdp")` (which materialises
~4.4M tokens in RAM). Search is instant (the first use fetches the database,
~219 MB):

```bash
aegean db search ddbdp "στρατηγῷ" --limit 5
#  doc              pos   text
#  aegyptus.96.10   13    στρατηγῷ
#  apf.67.374       218   στρατηγῷ
#  arctos.13.15     2     στρατηγῷ
#  bacps.27.18_2    1     στρατηγῷ
#  bgu.1.125        1     στρατηγῷ
```

In Python, collect every hit, then stream the matched documents into a corpus
of their own. The stream is one pass over all 57,331 papyri (a minute or two;
memory stays flat), and the subset you save is small and instant ever after:

```python
import aegean
from aegean import db
from aegean.scripts.greek import ddbdp_db

path = ddbdp_db()                              # the fetched SQLite file
hits = db.search(path, "στρατηγῷ", limit=0)    # limit 0 = every hit
print(len(hits), "attestations in", len({h[0] for h in hits}), "papyri")
# 1398 attestations in 1092 papyri

wanted = {doc_id for doc_id, pos, text in hits}
picked = [d for d in db.stream(path) if d.id in wanted]   # flat-memory pass

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

Now `strategos.db` is an ordinary corpus: read a house-share declaration to the
strategos of the Arsinoite nome, or run any statistic, without touching the big
database again:

```bash
aegean show strategos.db bgu.1.125
# bgu.1.125  site=Arsinoite  period=II/III spc
#   1: ι στρατηγῷ Ἀρσινοΐτου Ἡρακλείδου μερίδος
#   2: παρὰ Αὐρηλίου
#   3: ἀπογεγραμμένου διʼ ἑτέρου ὑπομνήτος. ὑπάρχει μοι ἐπʼ ἀμφόδου Θεσμοφορείου ἥμισυ μέρος
#   4: μερους οἰκίας, ἐν ᾧ ἀπογράφομαι

aegean stats strategos.db --top 5
#  item    count
#  καὶ     10082
#  τοῦ     5214
#  τῆς     2682
#  τῶν     2544
#  ἔτους   2196
```

**Task recipes used:**
[27 · DDbDP search](#27--search-57000-papyri-without-loading-them-ddbdp) ·
[19 · SQLite + FTS](#19--build-a-sqlite-database-and-full-text-search-it) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

### C · The literary classicist: catalogue, metre, gloss, citation

*You want a passage of Homer: read it, scan it, gloss it, cite the edition.*
Finding the work is offline (the catalogue is bundled metadata); fetching its
text is the one networked step, done once and then cached, commit-pinned:

```python
from aegean import greek
greek.catalog("iliad")[0]
# {'id': 'tlg0012.tlg001', 'author': 'Homer', 'title': 'Iliad', 'greek_title': 'Ἰλιάς', 'source': 'perseus'}
```

```bash
aegean greek work tlg0012.tlg001         # network on first use; cached after
#  documents      24
#  tokens         127339
#  first          tlg0012.tlg001:1
#  name           Ἰλιάς — Book 1
#  source         PerseusDL/canonical-greekLit (tlg0012.tlg001.perseus-grc2.xml)
#  data_version   PerseusDL/canonical-greekLit@d4fab69a2c26
```

Read the opening, gloss the first words from Cunliffe's Homeric lexicon (a
small one-time index fetch), and cite the edition:

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
# Homer. Ἰλιάς. Digitized by the Perseus Digital Library / Open Greek and Latin.
#   — https://github.com/PerseusDL/canonical-greekLit/blob/d4fab69a2c26…
```

```bash
aegean greek scan "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"
# —⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×
# hexameter: dactyl, dactyl, spondee, dactyl, dactyl, final; caesura: penthemimeral
```

The citation pins the exact source commit, so the text you quote is the text
anyone else will get. The offline lemmatizer is the honest baseline tier;
activate the treebank or neural tiers for higher measured accuracy
([Greek NLP](Greek-NLP)).

**Task recipes used:**
[25 · find a work in the catalogue](#25--find-a-work-in-the-catalogue-or-bring-in-your-own-text) ·
[3 · lemmatize and cite](#3--lemmatize-and-cite-a-chapter) ·
[8 · scan a line of verse](#8--scan-a-line-of-verse) ·
[18 · gloss offline](#18--gloss-koine-vocabulary-offline)

### D · The New Testament scholar: gold morphology to concordance

*Trace ἀγάπη through 1 John with the gold annotations.* The NT (Nestle 1904,
CC0) carries curated lemma, Robinson morphology, Strong's number, and a gloss
on every token; it is a small fetch on first use (fully offline, the bundled
sample covers John 1 and Philemon). Start from the verse every scholar checks
first:

```python
import aegean

jn = aegean.greek.load_nt("1 John")
verse = [t for t in jn.documents[3].tokens if t.annotations.get("ref") == "1John.4.8"]
for t in verse[-4:]:
    a = t.annotations
    print(f"{t.text:8} {a['lemma']:6} {a['morph']:9} Strong's {a['strongs']:>4}  {a['gloss']}")
# ὁ        ὁ      T-NSM     Strong's 3588  the
# Θεὸς     θεός   N-NSM     Strong's 2316  God, a god
# ἀγάπη    ἀγάπη  N-NSF     Strong's   26  love
# ἐστίν.   εἰμί   V-PAI-3S  Strong's 1510  I am, exist
```

A concordance is the query engine plus a context window (and the bundled Dodson
lexicon glosses any Koine word offline: `greek.use_dodson()`, then
`greek.gloss_nt("ἀγάπη")` returns `love`):

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

From the shell, the same subset saves and exports as a one-row-per-token table
(lemma, morphology, Strong's, gloss, reference; recipe 17 shows the columns):

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

*Frequency, dispersion, keyness, and collocation on the full Mycenaean corpus,
with a reproducibility trail.* DAMOS (~5,900 tablets, CC BY-NC-SA) is a
one-time ~3 MB fetch:

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

The numbers tell one story three ways: *o-na-to* ("lease plot") is frequent
(154), clumped (DP 0.873, the Pylos land-tenure series), and locked to
*ko-to-na* (joint count 49, Fisher's p ≈ 3.9e-82); the Thebes keys are the
Fq-series vocabulary. The receipt that makes the table citable:

```python
import aegean

damos = aegean.load("damos")
print(aegean.__version__)          # 0.55.0
print(damos.fingerprint()[:16])    # 3b0ae8aaa4a9e706
print(damos.cite())
# Aurora, F. (2015). DAMOS (Database of Mycenaean at Oslo). Annotating a fragmentarily
#   attested language. Procedia - Social and Behavioral Sciences, 198, 21-31. — https://damos.hf.uio.no
```

`aegean data versions` adds the dataset's own pin (the row
`fetched/damos-corpus  eab9ccdfc4324b62…  cached`): paste those lines into your
methods section and the analysis is reconstructible.

**Task recipes used:**
[4 · keyness](#4--what-vocabulary-distinguishes-a-site-keyness) ·
[13 · dispersion](#13--where-does-a-word-concentrate-dispersion) ·
[14 · collocation stats](#14--are-two-words-associated-collocation-stats) ·
[23 · tables to CSV](#23--save-a-stats-or-keyness-table-to-csv) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

### F · The Aegean-scripts researcher: exploratory, and labeled as such

*Structure-hunting in Linear A without pretending it reads.* Linear A is
undeciphered: everything here is a lead, and the tools label their own output
exploratory. Start from what is secure (the accounting shape), mine structure,
then test a hunch against a null model:

```bash
aegean balance lineara HT13
#  doc    marker   stated   computed   diff   balances
#  HT13   KU-RO    130.5    131.0      0.5    NO

aegean stats lineara --signs --top 5
#  item   count
#  𐝫      552
#  𐄁      468
#  1      310
#  KU     307
#  KA     284

aegean analyze clusters lineara --top 3       # exploratory word families
#  JA-SA → JA-SA-SA-RA-ME, JA-SA, JA-SA-JA, JA-SA-MU, JA-SA-SA, JA-SA-SA-RA
#  A-TA  → A-TA, A-TA-DE, A-TA-NA, A-TA-NA-JE, A-TA-NA-TE, A-TA-RE
#  I-DA  → I-DA, I-DA-A, I-DA-DA, I-DA-MI
```

A null model keeps the pattern-hunting honest. Are doubled adjacent signs (the
SA-SA of JA-SA-SA-RA-ME) more common in real Linear A words than chance would
make them?

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

No: the observed rate sits inside the null band, and a negative is a result
too. For the deciphered contrast, Linear B reads as Greek (Linear A has no such
bridge), and any word maps geographically:

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

*(Generation needs a provider key; the grounding below is offline and
deterministic.)* The discipline: derive the grammar locally, hand the model
facts, keep the label. The grounding is fully inspectable before any key is
involved:

```python
from aegean import greek, translate

neural = greek.GreekPipeline.neural()  # [neural]: contextual model predictions + UD parse
for item in translate.grounding_for(
    "ὁ δὲ θεὸς ἐγείρει τοὺς νεκρούς.", "greek",
    mode="morphology", greek_pipeline=neural,
):
    print(item)
# Clause skeleton: main predicate 'ἐγείρει' (ἐγείρω, active pres sg 3rd); subject θεὸς; object νεκρούς
# ὁ = ὁ (det, nom sg m)
# δὲ = δέ (adv)
# θεὸς = θεός (noun, nom sg m)
# ἐγείρει = ἐγείρω (verb, sg active pres ind 3rd)
# τοὺς = ὁ (det, acc pl m)
# νεκρούς = νεκρός (noun, acc pl m)
```

With a key configured (recipe 7 lists the providers), translate with that
grounding, then again with the post-hoc check that drafts first and repairs
against the analysis:

```bash
aegean ai translate "ὁ δὲ θεὸς ἐγείρει τοὺς νεκρούς." --greek-backend neural
aegean ai translate "ὁ δὲ θεὸς ἐγείρει τοὺς νεκρούς." --greek-backend neural --verify --trace
# output is provider- and model-dependent, so none is shown here; every result
# arrives labeled [EXPLORATORY · translate · <provider>], and -o keeps the
# label and the grounding trace alongside the text
```

Every answer is a labeled hypothesis, never a reading; `result.trace()` separates
the locally derived facts the model received from the backend configuration it did
not receive. Mode, backend, failure-policy choice, and what grounding can and cannot
fix are covered in recipe 26.

**Task recipes used:**
[26 · choose a Greek AI translation workflow](#26--choose-a-greek-ai-translation-workflow) ·
[7 · ask a grounded question](#7--ask-a-grounded-question--and-audit-the-answer)

### H · The toolsmith: one database, and tools for agents

*Build one searchable database out of several corpora, then expose the toolkit
to an AI agent.* `combine` resolves each source like any corpus argument and
merges provenance honestly; full-text search comes free with the `.db`
extension:

```bash
aegean combine isicily igcyr -o west.db     # Sicily + Cyrenaica, one database
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

One query, two Doric provinces: the dative Δάματρι (to Demeter) surfaces in
Sicilian and Cyrenaican dedications alike. The same corpus surface is available
to AI agents as an MCP server (`pip install "pyaegean[mcp]"`, then point your
client at the `aegean-mcp` command):

```python
from aegean.mcp_server import TOOLS
print(len(TOOLS), "tools:", ", ".join(t.__name__ for t in TOOLS[:6]), "…")
# 17 tools: list_corpora, corpus_info, show_document, search_signs, balance_accounts, query_corpus …
```

The tools address corpora by registry name only (never by filesystem path) and
return structured errors an agent can act on; setup and the full tool table are
on [MCP](MCP).

**Task recipes used:**
[22 · all of Homer in one database](#22--put-all-of-homer-in-one-searchable-database) ·
[19 · SQLite + FTS](#19--build-a-sqlite-database-and-full-text-search-it) ·
[24 · save a subset](#24--save-a-query-as-a-reusable-corpus-then-reload-it) ·
[21 · reproducibility](#21--lock-down-reproducibility-versions--sha256)

---

## 1 · Reconcile the accounting of a whole corpus, export the discrepancies

*Do the stated totals (KU-RO) on the Haghia Triada tablets match the sums of
their entries?* Reconcile every account, keep the failures, and cite the exact
subset:

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
aegean plot balance lineara -o balance.png      # the same picture: stated vs computed
```

The reconciliation is heuristic (section boundaries are inferred); a
discrepancy is a lead to inspect, not a verdict. See
[Linear A → Accounting](Linear-A).

## 2 · Map a word's distribution

*Where does KU-RO occur?* Count attestations by find-site, then place them:
every aligned site carries a [Pleiades](https://pleiades.stoa.org/) id:

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

With the `[geo]` extra (`pip install "pyaegean[geo]"`), `geo.word_distribution(corpus,
"KU-RO")` returns the same thing as a GeoDataFrame (EPSG:4326) ready for any
mapping stack, and `aegean geo lineara --output sites.geojson` writes GeoJSON
from the shell. See [Geography](Geography).

## 3 · Lemmatize and cite a chapter

*Lemmatize a passage of the Iliad and cite the edition.* `load_work` fetches the
complete work (commit-pinned, cached after the first fetch), `pipeline` runs the
whole stack per token:

```python
import aegean

iliad = aegean.greek.load_work("tlg0012.tlg001")     # the Iliad, Perseus edition
doc = iliad.documents[0]                              # Book 1
text = " ".join(t.text for t in doc.tokens[:40])

for r in aegean.greek.pipeline(text)[:3]:
    print(r.text, "→", r.lemma)
# μῆνιν → μῆνις · ἄειδε → ἀείδω · θεὰ → θεά

print(iliad.cite())
# Homer. Ἰλιάς. Digitized by the Perseus Digital Library / Open Greek and Latin. — …
```

```bash
aegean greek work tlg0012.tlg001 -o iliad.json       # the work as a corpus file
aegean greek pipeline "μῆνιν ἄειδε θεά" --json       # per-token records
```

The catalog of well-known works you can pass to `load_work` / `aegean greek work`
(`aegean greek works` prints it):

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

That's a curated subset (25 works in all); the full canon is at
[Scaife](https://scaife.perseus.org). Narrow a fetch with `--ref`, e.g.
`aegean greek work tlg0012.tlg001 --ref 1.1-1.10`.

The offline pipeline is the honest baseline; activate `--treebank` or
`--neural` (the `[neural]` extra) for attested-gold or measured neural lemmas:
see [Greek NLP](Greek-NLP) for the measured accuracy of each tier.

## 4 · What vocabulary distinguishes a site? (keyness)

*What makes the Pylos tablets different from the rest of the Mycenaean corpus?*
Load the full Linear B corpus (DAMOS, ~5,900 tablets, fetched ~3 MB), split
Pylos against everything else, and ask:

```python
import aegean
from aegean.analysis import keyness

damos = aegean.load("damos")
pylos = damos.filter(site="Pylos")
rest = [d for d in damos.documents if d.meta.site != "Pylos"]

for r in keyness(pylos, rest)[:3]:
    print(f"{r.item:10} G²={r.log_likelihood:.0f}  log-ratio={r.log_ratio:+.1f}")
# pe-mo      G²=254  log-ratio=+8.5     ('seed' — the land-tenure series)
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

The textbook Ventris & Chadwick land-tenure result surfaces immediately. Read
G² (significance) together with the log-ratio (effect size) and
`aegean dispersion`: see [Analysis → Corpus statistics](Analysis).

The same split works **by scribal hand** (DAMOS v2 carries the curated hand on
`meta.scribe`): *what does the most prolific Knossos scribe write about?*

```python
h117 = damos.filter(scribe="117")            # Hand 117
rest117 = [d for d in damos.documents if d.meta.scribe != "117"]
keyness(h117, rest117)[:5]                    # the hand's characteristic vocabulary
```

```bash
aegean keyness damos --scribe 117 --top 10
aegean analyze hands damos                    # rank every recorded hand
```

DAMOS is **CC BY-NC-SA 4.0 (NonCommercial)** and is fetched, never bundled: see
[Linear B](Linear-B) and [Data & Provenance](Data-and-Provenance).

## 5 · Sound-match a syllabic word against Greek

*Which Greek word does Linear B `qa-si-re-u` sound like?* Cross-script
comparison romanizes both sides to one phoneme alphabet and ranks by weighted
distance:

```python
from aegean.analysis import nearest, phonetic_compare

cmp = phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek")
print(round(cmp.similarity, 2))                    # 0.56
print([(c.a, c.b, c.op) for c in cmp.alignment][:2])  # [('k', '', 'del'), ('w', 'b', 'sub-far')] — the qʷ→b reflex

candidates = ["ποιμήν", "βασιλεύς", "πατήρ", "θεός", "δοῦλος"]
print(nearest("qa-si-re-u", "linearb", candidates, "greek", top=2, fold_aspiration=True))
# [('βασιλεύς', 0.4375), ('πατήρ', 0.6625)] — the true cognate first, by a clear margin
```

```bash
aegean analyze compare qa-si-re-u βασιλεύς
aegean analyze nearest po-me greek --top 5
aegean analyze distance qa-si-re-u βασιλεύς          # just the [0,1] distance
```

The **ranking** is the signal: defective syllabic spelling inflates absolute
distances (see the caution in [Analysis → Cross-script comparison](Analysis)).
The candidate list matters: rank against a lexicon or wordlist relevant to your
question, not just whatever corpus is at hand.

## 6 · Mine word-families from an undeciphered corpus (and cache it)

*Which Linear A words share a stem with a productive suffix?* Morphological
clustering is exploratory (no known grammar) but a strong lead-generator, and
the slowest analysis here, so switch on the opt-in cache if you'll rerun it:

```python
import aegean
from aegean.analysis import find_morphological_clusters

aegean.cache.enable()      # optional; or PYAEGEAN_ANALYSIS_CACHE=1

clusters = find_morphological_clusters(aegean.load("lineara").word_frequencies())
print(len(clusters), "clusters")          # 81
print(clusters[0].stem, "→", [m.word for m in clusters[0].members[:4]])
# JA-SA → ['JA-SA-SA-RA-ME', 'JA-SA', 'JA-SA-JA', 'JA-SA-MU']
```

```bash
aegean analyze clusters lineara --top 10
aegean cache                              # see what's cached; --clear to wipe
```

## 7 · Ask a grounded question — and audit the answer

*(Key-gated: needs a provider extra, e.g. `pip install "pyaegean[anthropic]"`,
and its API key.)* Ground the model in corpus facts, then **audit** what it was
given with the provenance trace:

```python
import aegean
from aegean import ai

corpus = aegean.load("lineara")
grounding = ai.corpus_context(corpus, limit=10) + ai.cooccurrence_evidence(corpus, "KU-RO")

r = ai.ask("What can be said about the function of KU-RO?", grounding=grounding)
print(r.labeled())     # [EXPLORATORY · ask · …] — the unmissable tag
print(r.trace())       # every corpus/analysis fact the answer rested on, by source
```

```bash
aegean ai ask "What is KU-RO?" --corpus lineara --trace
aegean ai providers             # anthropic · gemini · grok · local · openai · openrouter
aegean ai eval                  # grounding-fidelity scores for your provider
```

The registered providers and the extra that activates each:

| provider | extra | example model family |
|----------|-------|----------------------|
| `anthropic` | `pip install "pyaegean[anthropic]"` | Claude |
| `openai` | `pip install "pyaegean[openai]"` | GPT |
| `gemini` | `pip install "pyaegean[gemini]"` | Gemini |
| `grok` | `pip install "pyaegean[grok]"` | Grok |
| `openrouter` | `pip install "pyaegean[openrouter]"` | many vendors via one key (`vendor/model` ids) |
| `local` | `pip install "pyaegean[openai]"` | a local server (Ollama/LM Studio/llama.cpp), no key |

Every generative result is a labeled hypothesis, never a reading: see
[AI Layer](AI-Layer) and, if you can judge the answer, the
[validation issue form](https://github.com/ryanpavlicek/pyaegean/issues/new/choose).

## 8 · Scan a line of verse

*Scan the first line of the Odyssey, foot by foot.* The scanner uses fixed
quantity templates per metre; synizesis is lexical, not guessed:

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

The metres `--meter` accepts:

| meter | line | note |
|-------|------|------|
| `hexameter` | dactylic hexameter | epic; the default |
| `pentameter` | elegiac pentameter | the elegiac couplet's second line |
| `trimeter` | iambic trimeter | spoken tragedy/comedy |
| `glyconic` | glyconic | aeolic lyric (fixed template) |
| `pherecratean` | pherecratean | aeolic |
| `sapphic_hendecasyllable` | sapphic hendecasyllable | aeolic |
| `adonean` | adonean | aeolic |
| `alcaic_hendecasyllable` | alcaic hendecasyllable | aeolic |
| `alcaic_enneasyllable` | alcaic enneasyllable | aeolic |
| `alcaic_decasyllable` | alcaic decasyllable | aeolic |

A line that only fits via synizesis on a word outside the curated lexicon exits
non-zero with the reason rather than guessing. See [Meters](Meters).

## 9 · Type Greek without a Greek keyboard, then syllabify

*Enter polytonic Greek from plain ASCII, then break it into syllables with its
accent.* No Greek keyboard needed: use [Beta Code](Greek-NLP#normalization--beta-code):

```python
from aegean import greek

greek.betacode_to_unicode("mh=nin")            # 'μῆνιν'
greek.syllabify("ἄνθρωπος")                    # ['ἄν', 'θρω', 'πος']
greek.accentuation("λόγος").classification     # 'paroxytone'
greek.strip_diacritics("μῆνιν")                # 'μηνιν'
greek.to_ipa("λόγος")                          # 'loɡos' (reconstructed)

# candidate morphological parses (offline, ambiguity preserved):
for cand in greek.analyze("λόγος"):
    print(cand.lemma, cand.pos, cand.case, cand.number, cand.gender)
# λόγος NOUN nom sg masc
# λόγος NOUN nom sg fem
```

```bash
aegean greek betacode "mh=nin"           # μῆνιν   (--reverse goes back to Beta Code)
aegean greek syllabify "ἄνθρωπος"
aegean greek accent "λόγος"
aegean greek strip "μῆνιν"
aegean greek ipa "λόγος"
aegean greek morph "λόγος"               # λόγος [NOUN nom sg masc] / [NOUN nom sg fem]
```

If accents look like boxes in a bare Windows terminal that's the terminal font,
not pyaegean: see the note in [Getting Started](Getting-Started#seeing-greek-correctly).

## 10 · Read a deciphered syllabic word as Greek (the bridge)

*Spell out a Linear B or Cypriot word as the Greek it stands for.* The
Greek-reading bridge applies the script's known sound values plus the spelling
conventions (final consonants, clusters):

```bash
aegean bridge linearb po-me
# po-me → ποιμήν   (shepherd)

aegean bridge cypriot pa-si-le-u-se
# pa-si-le-u-se → βασιλεύς   (king)

aegean bridge linearb qa-si-re-u --json | jq '.greek'
```

This is only for the **deciphered** scripts (`linearb`, `cypriot`); Linear A and
Cypro-Minoan are undeciphered, so there is no bridge for them: use recipe 5
(sound-matching) as the exploratory analogue. See [Linear B](Linear-B) and
[Cypriot](Cypriot).

## 11 · Find words by sign pattern

*List every two-sign Linear A word that starts with KU, or every three-sign word
KU-?-RO.* Each `*` matches **exactly one** sign (use the query engine in the next
recipe for an open-ended prefix):

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
freqs = corpus.word_frequencies()          # list of (word, count) pairs
hits = [(w, c) for w, c in freqs if word_matches_sign_pattern(w, "KU-*")]
print(sorted(hits, key=lambda x: -x[1])[:3])
# [('KU-RO', 37), ('KU-PA', 4), ('KU-RA', 2)]
```

Works on any syllabic corpus (`lineara`, `linearb`, `cypriot`, `cyprominoan`,
and the fetched `damos` / `sigla`). For an open-ended prefix (e.g. *everything*
starting KU, including longer words like `KU-PA₃-NU`) use the query engine
(next recipe).

## 12 · Build a compound query and pipe the JSON

*Find Linear A words that start with KU, ranked by frequency: as data.* The
query engine ANDs/ORs/negates rows; `--fields` lists what you can filter on:

```bash
aegean query lineara --fields                 # the queryable fields for this corpus
aegean query lineara --where word-prefix=KU --output-kind words --limit 6
#  word           count
#  KU-RO          34
#  KU-PA₃-NU      7
#  KU-NI-SU       5
#  KU-PA          4
#  KU-MI-NA-QE    2
#  KU-PA₃-NA-TU   2

# AND two rows; OR with the "or:" prefix; negate with "!":
aegean query lineara --where site-is="Haghia Triada" --where or:word-prefix=KU --json \
  | jq '.matched.inscriptions'         # 55
```

`--json` respects `--limit` for the listed `inscriptions` array (default 25), so
read the full match count from `.matched.inscriptions`; pass `--limit 0` to list
every matched inscription.

The fields available depend on the corpus (`aegean query CORPUS --fields`); for
Linear A they include `site-is`, `scribe-is`, `period-is`, `support-is`,
`has-image`, `word-prefix`, `word-suffix`, `word-contains-sign`,
`word-cooccurs-with`, `word-sign-pattern`, and more. The same engine is
available in Python via `aegean.analysis.run_query`. See [Analysis](Analysis).

## 13 · Where does a word concentrate? (dispersion)

*Is KU-RO spread evenly across the corpus, or clumped?* Gries' DP runs 0 (even)
to 1 (concentrated):

```bash
aegean dispersion lineara KU-RO
#  item    freq   range/parts   DP      DPnorm
#  KU-RO   37     34/559        0.850   0.851

aegean dispersion lineara --top 5            # rank the whole corpus
aegean dispersion lineara --signs --top 5    # by individual sign instead of word
```

```python
import aegean
from aegean.analysis import dispersion

corpus = aegean.load("lineara")
d = dispersion(corpus, "KU-RO")
print(round(d.dp, 3), d.range, "of", d.parts)   # 0.85 34 of 559
```

A high DP next to a high keyness G² is the interesting case: a word that is both
*characteristic* of a subcorpus and *clumped* within it. See
[Analysis → Corpus statistics](Analysis).

## 14 · Are two words associated? (collocation stats)

*Do KU-RO and KI-RO turn up in the same documents more than chance?* Four
measures at once over the whole corpus: χ², log-likelihood, Fisher's exact, and
a PMI confidence interval:

```bash
aegean analyze assoc lineara KU-RO KI-RO
#  joint / w1 / w2 / docs   5 / 34 / 12 / 1721
#  chi_squared              78.75
#  p_value                  7.055e-19
#  log_likelihood           23.94
#  fisher_p                 1.595e-06
#  pmi_interval             [3.1720137984039996, 5.621837690118523]

aegean analyze cooccur lineara KU-RO --top 5     # what shares a document with KU-RO
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
docs = [{t.text for t in d.words} for d in corpus]   # one set of words per document
total = len(docs)
joint = sum(1 for s in docs if "KU-RO" in s and "KI-RO" in s)   # 5
n1    = sum(1 for s in docs if "KU-RO" in s)                     # 34
n2    = sum(1 for s in docs if "KI-RO" in s)                     # 12

print(round(log_likelihood_ratio_2x2(joint, n1, n2, total), 2))  # 23.94
print(fishers_exact(joint, n1, n2, total))                       # 1.60e-06
```

Fisher's exact is the one to trust on the small joint counts typical of these
corpora. See [Analysis → Association](Analysis).

## 15 · Which signs are surprising inside a word?

*Where is KU-RO improbable, sign by sign?* A token-weighted sign-bigram model
gives per-transition surprisal in bits: a way to flag spellings that don't look
like the rest of the corpus:

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

`^` and `$` are the word-boundary symbols, so the model also scores how typical a
sign is at the start or end of a word. High mean surprisal on a hapax is a hint
that it may be a foreign name, an abbreviation, or a misreading: a lead, not a
verdict. See [Analysis](Analysis) and [Limitations](Limitations).

## 16 · Classify documents by structure

*How many Linear A documents read as accounts vs libation formulae vs lists?*
A heuristic classifier sorts each document into one of five categories:

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

The categories are `accounting`, `libation`, `list`, `text`, `other`. These are
rule-based labels (numeral density, known libation words, line shape), useful for
sampling and triage, not a typology to cite as fact. See [Linear A](Linear-A).

## 17 · Export the Greek NT as an annotated table

*Get the whole Greek New Testament as one row per token, with gold lemma,
morphology, Strong's number, and a gloss: ready for pandas or a spreadsheet.*

```bash
aegean export nt -f csv -o nt_tokens.csv --level token
# wrote 260 documents to nt_tokens.csv (csv)
```

This writes the 260 NT chapters as 137,779 token rows (one per token). The
token-level columns are:

| column | example | meaning |
|--------|---------|---------|
| `text` | `Βίβλος` | the surface token |
| `normalized` | `Βίβλος` | NFC-normalized form |
| `lemma` | `βίβλος` | gold dictionary headword |
| `upos` | `NOUN` | reconciled UD part of speech |
| `morph` | `N-NSF` | Robinson morphology tag |
| `strongs` | `976` | Strong's number |
| `gloss` | `a written book, roll, or volume` | short gloss |
| `ref` | `Matt.1.1` | canonical reference |
| `doc_id`, `line_no`, `position` | `Matt 1`, `1`, `0` | location |

```python
import aegean
nt = aegean.load("nt")                 # the whole NT as a corpus
print(len(nt.documents), "chapters")   # 260
t = nt.documents[0].tokens[0]
print(t.text, t.annotations["lemma"], t.annotations["upos"], t.annotations["strongs"])
# Βίβλος βίβλος NOUN 976

# or just one passage:
john = aegean.greek.load_nt("John", ref="1.1-1.5")
print(len(john.documents[0].tokens), "tokens")     # 61
```

`--level token` works for `csv` and `parquet`; other formats are `json` (lossless),
`epidoc` (TEI), and `sqlite`. The NT text is **CC0** (Nestle 1904 base + CC0
morphology/lemmas/Strong's). `aegean greek nt-books` lists all 27 books and the
names `load_nt` accepts (e.g. `matthew`/`matt`/`mt`). See [Greek NLP](Greek-NLP).

## 18 · Gloss Koine vocabulary offline

*Get a quick English gloss for a Koine word with no download.* The bundled
Dodson lexicon (CC0) ships in the package: turn it on, then look words up:

```python
from aegean import greek

greek.use_dodson()
print(greek.gloss_nt("λόγος"))   # a word, speech, divine utterance, analogy
print(greek.gloss_nt("ἀρχή"))    # ruler, beginning
```

```bash
aegean greek gloss-nt λόγος       # a word, speech, divine utterance, analogy
```

**More dictionaries.** Dodson and LSJ are two backends in a **lexicon registry**.
`greek.use_lexicon(id)` activates **Middle Liddell** (concise classical), **Cunliffe**
(Homeric), **Autenrieth** (Homeric), **Abbott-Smith** (New Testament), or **LSJ**, and `greek.gloss(word,
dictionary=id)` glosses from the one you choose (each fetches a small index on first use,
0.1–15 MB):

```python
greek.use_lexicon("cunliffe")                            # Cunliffe's Homeric lexicon
print(greek.gloss("μῆνις", dictionary="cunliffe"))       # μῆνις: μῆνις ἡ. 1 Wrath, ire …

greek.use_lexicon("abbott-smith")                        # Abbott-Smith's NT lexicon
print(greek.gloss("πίστις", dictionary="abbott-smith"))  # πίστις: faith; belief; trust; …
```

For dictionaries pyaegean cannot host (Slater, Montanari, …), build a
**Logeion deep-link** instead, which runs offline:

```python
greek.lexicon_link("μήνιδος")   # → a logeion.uchicago.edu link to the lemma μῆνις
```

From the shell: `aegean greek lexica` lists the dictionaries, `aegean greek gloss μῆνις
--dict cunliffe` glosses from one, and `aegean greek lexicon-link μήνιδος` builds the link.
Dodson is still the zero-download path. See
[Greek NLP → the lexicon registry](Greek-NLP#more-dictionaries-the-lexicon-registry).

## 19 · Build a SQLite database and full-text search it

*Put a whole corpus in a queryable SQLite file with FTS5, then search the
tokens.* Good for big corpora and for handing data to non-Python tools:

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

The database has `documents` and `tokens` tables plus an FTS5 index, so you can
also open it in any SQLite client and run ordinary SQL. The same file is what
`aegean export CORPUS -f sqlite -o …` produces. See [CLI → db](CLI).

## 20 · Look up one sign in the inventory

*What is the sign PA in Linear B: glyph, Unicode codepoint, sound value?*

```bash
aegean sign linearb pa
#  label              PA
#  glyph              𐀞
#  codepoint          U+1001E
#  phonetic           pa
#  attrs.bennett      B003
#  attrs.unicodeName  LINEAR B SYLLABLE B003 PA
#  attrs.signClass    syllabogram
```

```python
import aegean
inv = aegean.get_script("linearb").sign_inventory
sign = inv.by_label("PA")
print(sign.glyph, hex(sign.codepoint), sign.phonetic)   # 𐀞 0x1001e pa
```

Works for every syllabic script (`lineara`, `linearb`, `cypriot`, `cyprominoan`).
The corpus sizes that ship in the wheel, for reference:

| corpus id | `aegean.load(...)` | what it is |
|-----------|--------------------|-----------|
| `lineara` | 1721 documents | full GORILA Linear A (bundled, Apache-2.0) |
| `linearb` | 18 documents | a small bundled Linear B sample; load `damos` for the full corpus |
| `cypriot` | 180 documents | bundled Cypriot syllabic corpus |
| `cyprominoan` | 2 documents | bundled Cypro-Minoan sample |
| `greek` | 5 documents | bundled Greek sample passages; use `load_work` / `load_nt` for whole works |

Fetched corpora (`damos`, `nt`, `sigla`, the Greek epigraphic corpora `isicily`,
`iip`, `iospe`, `igcyr`, `edh`, and the `ddbdp` papyri database) are larger and
pulled on first use: see
the next recipe and [Data & Provenance](Data-and-Provenance).

## 21 · Lock down reproducibility (versions + sha256)

*Record exactly which datasets your paper used.* Every fetchable dataset is
sha256-verified; the manifest is one command:

```bash
aegean data list                  # everything fetchable, with a downloaded column + sizes
aegean data versions              # the reproducibility manifest: version + sha256 each
aegean data store                 # where the local store lives and what's in it now
aegean data fetch damos-corpus    # one-time download (a no-op once stored)
aegean data remove damos-corpus   # delete a downloaded dataset (--all clears everything)
```

```python
import aegean
print(aegean.__version__, aegean.registered_scripts())
# 0.55.0 ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
```

Paste `aegean --version` and the relevant lines of `aegean data versions` into
your methods section and anyone can reconstruct the exact inputs. The cache
location is overridable with `PYAEGEAN_CACHE`. See
[Data & Provenance](Data-and-Provenance) and [Installation](Installation).

## 22 · Put all of Homer in one searchable database

*Both Homeric epics, fetched once, in a single SQLite file you can full-text
search.* `combine` resolves each source like any corpus argument (here two Greek
work ids), merges them, and writes one database; then `db search` runs over the
whole thing:

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

(The Iliad and Odyssey are 24 books each, so the merged database holds 48
documents; the doc id is the work id plus the book number.)

The two works keep distinct document ids, so nothing collides; if they ever did,
`--on-conflict first|last|suffix` decides what wins (the default is `error`, so a
clash is loud rather than silent). The merged corpus records a provenance note
that names **every** source, so `aegean cite homer.db` still credits both
editions.

Already built the database and want to fold in a third work later? `db add`
upserts by document id: matching ids are replaced, new ones appended, the FTS5
index refreshed: without rebuilding:

```bash
aegean db build tlg0012.tlg001 -o homer.db      # start with the Iliad
aegean db add tlg0012.tlg002 -o homer.db        # then add the Odyssey
# added/updated 24 documents in homer.db
```

The same moves in Python: `read_corpus` does the fetching, `combine` (or
`Corpus.merge`) does the joining:

```python
import aegean

homer = aegean.combine([
    aegean.read_corpus("tlg0012.tlg001"),       # Iliad
    aegean.read_corpus("tlg0012.tlg002"),       # Odyssey
])
print(len(homer.documents), "books")            # 48
homer.to_sql("homer.db")                         # one searchable database
print("merged" in homer.cite())                  # True — both sources named

# Corpus.merge(*others, dedupe=...) is the method form; Corpus.subset(ids) is
# the inverse, carving a named subset back out by document id.
```

The Greek-work fetch needs the network the first time (then it's cached); the
`combine` / `merge` / `db add` mechanics themselves are offline. See
[CLI → db](CLI) and [Greek NLP](Greek-NLP).

## 23 · Save a stats or keyness table to CSV

*Get a frequency or keyness table straight onto disk as a spreadsheet: no
pandas, no jq, no copy-paste.* `stats`, `keyness`, `dispersion`, `search`, and
the `analyze` family all take `--output/-o`; the extension decides the format
(`.csv`, `.json`, or `.txt`):

```bash
aegean stats lineara --top 5 -o freq.csv
```

That writes a plain, stdlib CSV:

```csv
item,count
KU-RO,37
SA-RA₂,20
KI-RO,16
*411-VS,15
A-TA-I-*301-WA-JA,11
```

Keyness writes the full table (counts, totals, G², log-ratio, p), one row per
item, ready to sort in any spreadsheet:

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

Swap the extension for `.json` to get the same data as records, or `.txt` for the
human-readable table you'd see on screen. The same `-o` is on the `ai` commands
too (`aegean ai translate … -o out.json`), where the file keeps the exploratory
label and grounding trace alongside the text: see [AI Layer](AI-Layer). See
[Analysis](Analysis) and [CLI](CLI).

## 24 · Save a query as a reusable corpus, then reload it

*Run the [compound query](#12--build-a-compound-query-and-pipe-the-json) once,
keep the matched inscriptions as their own corpus, and feed it to any later
command.* `query --output` writes the hits as a `.json` or `.db` corpus:
inscriptions only, and stamps a `subset:` provenance note so the saved file
still cites the exact query that built it:

```bash
aegean query lineara --where word-prefix=KU -o ku.json
# wrote 69 inscriptions to ku.json
```

Now `ku.json` *is* a corpus: every command that takes a corpus takes it
(recall the rule at the top of the page):

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

Save to a `.db` instead and you get a full-text index in the same step, so the
subset is searchable on its own:

```bash
aegean query lineara --where word-prefix=KU -o ku.db
aegean db search ku.db "KU-RO" --limit 3
#  doc     pos   text
#  HT9a    25    KU-RO
#  HT9b    20    KU-RO
#  HT11a   7     KU-RO
```

In Python it's `QueryResults.to_corpus(source)` to build the subset and
`read_corpus(path)` to reload it later:

```python
import aegean
from aegean.analysis import FilterRow

la = aegean.load("lineara")
res = la.query([FilterRow("word-prefix", "KU")])   # QueryResults
subset = res.to_corpus(la)                          # a real Corpus, with the subset: note
print(len(subset.documents))                        # 69

subset.to_json("ku.json")                          # ... later, in a fresh session ...
again = aegean.read_corpus("ku.json")              # back as a Corpus
print(again.cite().split("[")[-1])
# subset: query(Word starts with: KU) → 69 documents]
```

Because the note travels with the file, a saved subset stays as citable as the
full corpus it came from: exactly the reproducibility habit recipe 21 is built
around. See [Analysis](Analysis) and [Data & Provenance](Data-and-Provenance).

## 25 · Find a work in the catalogue, or bring in your own text

*Two ways to get to a corpus you can analyse: discover an id in the bundled
catalogue and fetch it, or import a passage you already have.* Both start fully
offline: the catalogue is bundled metadata and `import` reads local files; only
the optional `load_work` step at the end touches the network.

**Discover an id.** `catalog()` searches every work with a Greek edition in the
two open repos (~1,800 of them), not just the 25 in recipe 3: substring filters
(`author=`, `title=`, `source=`) or a free-text `query`, instant and offline:

```python
from aegean import greek

len(greek.catalog())                 # 1778   (768 perseus + 1010 first1k)
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

The id you find (`tlg0012.tlg002`) is exactly what `load_work` /
`aegean greek work` takes: that fetch is the only networked step (see recipe 3).
Coverage is what the repos hold at the pinned commit, so an author the upstream
data lacks is honestly absent: `greek.catalog("Sappho")` returns `[]`.

**Or bring your own text.** Have a passage on disk already? `import` turns a
`.txt`/folder/`.csv` into a real corpus that then works anywhere a corpus is
accepted (recall the rule at the top of the page): `stats`, `query`, `export`,
the Greek pipeline, all of it. Greek text goes through the Greek tokenizer
(punctuation stripped, elision handled):

```bash
# john1.txt holds: ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.
aegean import john1.txt -o john1.json
# wrote 1 document(s) to john1.json

aegean stats john1.json --top 4
#  item    count
#  λόγος   3
#  ἦν      3
#  ὁ       3
#  καὶ     2
```

In Python the same thing is `aegean.io.from_text` (a string) or `from_text_file`
(a path); `from_csv` / `from_text_dir` handle a spreadsheet or a folder. The
result is a `Corpus`, so every analysis applies: here, frequency counts and the
one-call pipeline over your own line:

```python
from aegean import io, greek

text = "ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος."
corpus = io.from_text(text, script_id="greek", doc_id="john1.1")
print(len(corpus.documents[0].words))     # 17
print(corpus.word_frequencies()[:3])      # [('λόγος', 3), ('ἦν', 3), ('ὁ', 3)]

for r in greek.pipeline(text)[:3]:
    print(r.text, r.upos, r.lemma)
# ἐν ADP ἐν
# ἀρχῇ NOUN ἀρχή
# ἦν VERB εἰμί
```

Two things worth knowing: an imported corpus is `license="user-supplied"` in its
provenance: it's *your* text, so `cite()` records that rather than fabricating an
edition. And `read_corpus` / the bare `CORPUS` argument still load only `.json`
and `.db`; a `.txt`/`.csv` must be imported first (the error message says so).
`--split paragraph|line` makes one document per block or per line instead of one
for the whole file. See
[Your own corpus](Data-and-Provenance#from-a-file-you-already-have-aegean-import)
for the import paths and
[Finding any other work](Greek-Works-and-Books#3-finding-any-other-work) for the
full catalogue.

---

## 26 · Choose a Greek AI translation workflow

*(The grounding is offline and deterministic; only the final generation needs a
provider key.)* A specialist toolkit should make a general model translate
Ancient Greek **better**, not worse. The lever is `translate(..., mode=...)`: how
much locally-derived analysis you hand the model. Pick the mode by how hard the
passage is.

```python
from aegean import greek, translate

neural = greek.GreekPipeline.neural()  # model-predicted morphology + UD parse

text = "καὶ ἡγοῦμαι σκύβαλα εἶναι, ἵνα Χριστὸν κερδήσω."   # Philippians 3:8
result = translate.translate(text, mode="morphology", greek_pipeline=neural)
print(result.labeled())        # [EXPLORATORY · translate · <provider>] <translation>
```

Four modes, by difficulty:

| mode | what the model is told | reach for it when |
|------|------------------------|-------------------|
| `"morphology"` *(default)* | lemma, part of speech, **voice**, case-role, clause skeleton, rare-word flags | always: the safe floor; it fixes wrong voice, swapped subject/object, and case errors |
| `"full"` | morphology **plus concise dictionary glosses** on the rare words | rare, technical, poetic, or documentary vocabulary the model will not know |
| `"lemma"` | lemmas + gated glosses (legacy) | reproducing older behaviour |
| `"none"` | the bare text | a top-tier model on a famous, easy passage |

The grounding is fully inspectable offline, with no key and no network beyond the
one-time dictionary fetch:

```python
greek.use_lsj(); greek.use_lexicon("abbott-smith")   # a concise, common-sense-first dictionary

for item in translate.grounding_for(
    text, "greek", mode="full", greek_pipeline=neural
):
    print(item)
# Clause skeleton: main predicate 'ἡγοῦμαι' (ἡγέομαι, middle pres sg 1st); object σκύβαλα
# σκύβαλα = σκύβαλον (noun, acc pl n)
# Rare / easily-mistranslated words: κερδήσω, σκύβαλα
# σκύβαλα (σκύβαλον): refuse                       ← the meaning a weak model misses
```

That last line is the point: without it a small model renders σκύβαλα as
"scourges"; with it, "refuse." The glosses in `"full"` come from **concise,
common-sense-first** dictionaries (Middle Liddell, Cunliffe for Homer,
Abbott-Smith for the New Testament), rarity-gated to the words that matter. They
are deliberately *not* the first sense of LSJ, a historical lexicon whose opening
sense is frequently the archaic one (καιρός "a row of thrums in the loom" comes
before "the right time").

**What grounding does, and what it does not.** The morphology reliably removes
grammatical errors (voice, subject/object, case); the `"full"` glosses remove
rare-word errors. Both help **weaker models and rarer text the most**: a frontier
model on a canonical line has little to gain. Grounding will not make a weak model
an expert, and Ancient Greek translation has genuine interpretive range (no two
published Homers agree), so every result is a **labeled, provenanced hypothesis**,
never a verdict. `ai.grounding_regime(text, corpus=...)` gives an exploratory
help/neutral/hurt signal, but the simple rule holds: morphology always, glosses
when the vocabulary is rare. See [AI Layer](AI-Layer).

## 27 · Search 57,000 papyri without loading them (DDbDP)

The Duke Databank of Documentary Papyri (`ddbdp`, 57,331 papyri, ~4.4M tokens) is
delivered as a SQLite database with a full-text index, so the right way in is
search and streaming, not `load`:

```bash
aegean db search ddbdp "βασιλέως" --limit 3   # fetches the database on first use (~219 MB), then instant
```

```python
from aegean.scripts.greek import ddbdp_db
from aegean import db
for doc in db.stream(ddbdp_db()):   # one document at a time, flat memory
    ...
```

`aegean.load("ddbdp")` still materialises the whole corpus for corpus-wide
statistics, but it costs a couple of minutes and several GB of RAM; prefer the
search and stream paths above.

---

## Notes & limitations

- **Outputs are real but corpus-version-bound.** The numbers above were produced
  against the shipped data; a future corpus update can shift counts. The
  `cite()` / `aegean data versions` habit in these recipes is exactly what pins
  them.
- **Heuristic analyses are leads, not verdicts.** Accounting reconciliation
  (recipe 1), structure classification (16), morphological clusters (6), and
  sign surprisal (15) all infer structure the corpora don't mark explicitly.
  Inspect the documents they point you at.
- **Cross-script sound-matching reads as a ranking,** not an absolute score
  (recipe 5); defective syllabic spelling inflates distances.
- **The AI layer is exploratory and key-gated** (recipe 7). Every answer is a
  labeled hypothesis with a provenance trace; never quote it as a reading.

See [Limitations](Limitations) for the full, honest list, and
[For Specialists](For-Specialists) for the methodological fine print.
