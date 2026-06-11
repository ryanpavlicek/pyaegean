# Linear B

Linear B is the **deciphered** Aegean syllabary — it writes Mycenaean Greek, the earliest
attested form of the language. pyaegean reads it through the same `Script` plugin model as
Linear A: a sign inventory, transliteration to phonetics, a bridge into the Greek track, and the
accounting reconciliation. Because Linear B is read, the work here is verifiable rather than
exploratory.

```python
import aegean
from aegean.scripts.linearb import word_to_phonetic, greek_reading

aegean.registered_scripts()              # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
word_to_phonetic("QA-SI-RE-U")           # 'kwasireu'  (gʷasileus, the ancestor of βασιλεύς)
greek_reading("PO-ME")                   # ('ποιμήν', 'shepherd')
```

## Sign inventory

The inventory is built from the Unicode Character Database — the Linear B Syllabary and Ideograms
blocks — so it is authoritative and freely licensed (see [Data & Provenance](Data-and-Provenance)).
It holds **211 signs**: 74 syllabograms (each with its phonetic value), 14 still-undeciphered
symbols, and 123 ideograms/monograms for commodities (grain, wine, oil, people, livestock…). Every
sign keeps its **Bennett number** (`B008`, `B131`) and its Unicode name.

```python
from aegean.core.script import get_script

inv = get_script("linearb").sign_inventory
ka = next(s for s in inv if s.label == "KA")
ka.glyph, ka.phonetic, ka.attrs["bennett"]   # ('𐀏', 'ka', 'B077')
```

## Transliteration → phonetics

`word_to_phonetic` converts a hyphenated transliteration to a phonetic Latin form, with the
labiovelar (`qa → kwa`) and affricate (`za → dza`) values. The complex signs `a2`/`a3`/`pu2` are
kept distinct from `a`/`pu`.

```python
word_to_phonetic("WA-NA-KA")   # 'wanaka'   (ϝάναξ, "king")
word_to_phonetic("TI-RI-PO-DE")# 'tiripode' (τρίποδε, "two tripods")
word_to_phonetic("WO-NO")      # 'wono'     (ϝοῖνος → οἶνος, "wine")
```

## Bridge to Greek

Linear B *is* Greek, so a transliterated word resolves to its Classical Greek lemma and meaning.
`greek_reading` returns `(lemma, gloss)` from a **150-entry** lexicon of well-established
equations — a hand-curated core layered with entries extracted from Wiktionary's Mycenaean
Greek pages (via the kaikki.org dump, CC BY-SA): only entries whose etymology *states* the
Ancient Greek equation are taken, so every bridge is source-attested rather than reconstructed.
Pass the lemma on to the [LSJ backend](Greek-NLP#lexicon-lsj-glossing-opt-in) for the full entry.

```python
from aegean.scripts.linearb import greek_reading, gloss

greek_reading("WA-NA-KA")   # ('ἄναξ', 'king, lord (wanax)')
greek_reading("TE-O")       # ('θεός', 'god')
gloss("DO-E-RO")            # 'slave, servant (male)'   (δοῦλος)

# with the LSJ lexicon active, get the full dictionary entry for the reading:
import aegean
aegean.greek.use_lsj()
lemma, _ = greek_reading("PO-ME")
aegean.greek.gloss(lemma)   # 'ποιμήν: herdsman, shepherd …'
```

## Accounting

Linear B tablets are administrative records — names, commodity ideograms, and numerals, often
with a `to-so`/`to-sa` (τόσος, "so much") total. The script-agnostic accounting engine reads them
directly, using Linear B's total markers in place of Linear A's `KU-RO`.

```python
from aegean.analysis import balance_check

corpus = aegean.load("linearb")
for doc in corpus:
    for chk in balance_check(doc):
        print(doc.id, chk.marker, chk.computed_sum, "==", chk.stated_total, chk.balances)
```

The reconciliation is heuristic — section boundaries are inferred — so a balance is evidence, not
proof, exactly as for Linear A.

## The corpus

### The full DAMOS corpus — `aegean.load("damos")`

The most complete edition of the Mycenaean corpus is **DAMOS** (the Database of Mycenaean at Oslo,
F. Aurora), published under **CC BY-NC-SA 4.0**. pyaegean hosts the DAMOS transliterations and core
metadata as a fetched-on-demand release asset, so the whole corpus is one call away:

```python
import aegean

corpus = aegean.load("damos")        # fetches ~a few MB to the cache on first use, then offline
len(corpus.documents)                # ~5,900 tablets: Knossos, Pylos, Thebes, Mycenae, Tiryns, …
doc = corpus.documents[0]
print(doc.id, "—", doc.meta.site)    # 'KN Fp(1) 1 + 31 (138) — Knossos'
print(doc.transcription)             # the DAMOS transliteration, verbatim
```

Each tablet is one `Document`: the transliteration is tokenised into words / numerals / logograms
(using the DAMOS comma-and-slash word dividers), and the verbatim transliteration is kept in
`Document.transcription`. The data is **NonCommercial + ShareAlike** — those obligations pass
through to you, the corpus is fetched to your cache and **never bundled or re-hosted**, and you
should **cite DAMOS** (Aurora 2015) in academic work. `scripts/build_damos_corpus.py` documents
exactly how the asset is built from the DAMOS public API.

### The bundled sample — `aegean.load("linearb")`

For a zero-network default, pyaegean also bundles an **18-tablet illustrative sample** — PY Ta 641
(the tablet that confirmed Ventris's decipherment) and PY Er 312 hand-curated, plus sixteen one-line
excerpts from Pylos, Knossos, and Mycenae tablets taken from *sourced quotations* in Wiktionary's
Mycenaean entries (each cites its tablet and carries a translation; CC BY-SA). These are excerpts to
exercise the tools, **not editions** — use `aegean.load("damos")` above for the full corpus, or
bring your own below.

**From a LiBER selection (interim recipe).** LiBER's interface exports a selection by
copy-to-clipboard ("e.g., to be pasted into an *Excel* spreadsheet"). Your own copied
selection — your use, under LiBER's terms; pyaegean fetches and re-hosts nothing — can be
loaded through `Corpus.from_records`: save the paste as CSV with columns like
`id,site,text`, then:

```python
import csv

import aegean

with open("my-liber-selection.csv", encoding="utf-8") as f:
    records = [
        {"id": r["id"], "text": r["text"], "meta": {"site": r.get("site", "")}}
        for r in csv.DictReader(f)
    ]
corpus = aegean.Corpus.from_records(
    records, script_id="linearb",
    provenance=aegean.Provenance(
        source="My LiBER selection (manual export)",
        license="© CNR Edizioni — all rights reserved; personal research use",
        citation="LiBER — Linear B Electronic Resources (Del Freo & Di Filippo, CNR).",
    ),
)
```

Point pyaegean at your own licensed EpiDoc export (e.g. a DAMOS download) and it parses it locally,
never re-hosting:

```bash
pip install "pyaegean[epidoc]"                 # the EpiDoc reader (lxml)
export PYAEGEAN_LINEARB_CORPUS=/path/to/damos   # a file or directory of EpiDoc XML
```

```python
aegean.load("linearb")                          # now loads your corpus
# or explicitly:
from aegean.scripts.linearb import load_epidoc_corpus
load_epidoc_corpus("/path/to/damos")
```
