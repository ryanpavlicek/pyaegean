# Catalog: Aegean Scripts, Epigraphy, Papyri & Lexica

[Catalog Overview](Catalog) · [Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) · [Biblical & Second Temple](Catalog-Biblical) · [John Chrysostom](Catalog-Chrysostom) · [Church Fathers & Patristics](Catalog-Church-Fathers) · [Archaic & Classical](Catalog-Classical-Greek) · [Hellenistic](Catalog-Hellenistic-Greek) · [Imperial](Catalog-Imperial-Greek) · [Late Antique & Byzantine](Catalog-Late-Antique-and-Byzantine) · [Perseus & First1KGreek](Catalog-Perseus-and-First1K)

Complete listing of all Aegean syllabic script corpora, the bundled Greek sample, Greek epigraphic corpora, documentary papyri, and Greek dictionaries.

## Aegean syllabic scripts

| Corpus ID | Script | Title | Docs | Tokens | Delivery | Size | License |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `lineara` | `lineara` | Linear A Corpus (GORILA) | 1,721 | 6,406 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `sigla` | `lineara` | SigLA Linear A Corpus (802 documents) | 802 | 2,616 | Hosted (`sigla-corpus`) | ~1.3 MB | CC BY-NC-SA 4.0 |
| `linearb` | `linearb` | Linear B Sample Tablets | 18 | 92 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `damos` | `linearb` | DAMOS Linear B Corpus (~5,900 tablets) | 5,932 | 54,476 | Hosted (`damos-corpus`) | ~3.0 MB | CC BY-NC-SA 4.0 |
| `cypriot` | `cypriot` | Cypriot Syllabary Corpus | 180 | 628 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `cyprominoan` | `cyprominoan` | Cypro-Minoan Corpus | 2 | 4 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |

## Bundled Greek seed sample (`greek`)

Five public-domain passages bundled for offline smoke testing and quickstart examples (`aegean.load("greek")`):

| Document ID | Passage | Period | Tokens |
| --- | --- | --- | ---: |
| `iliad-1.1` | Iliad 1.1 | Archaic (epic) | 5 |
| `john-1.1` | John 1:1 | Koine | 12 |
| `heraclitus-panta-rhei` | Fragment (panta rhei) | Archaic | 2 |
| `herodotus-1.1` | Histories 1.1 | Classical (Ionic) | 5 |
| `sappho-1.1` | Hymn to Aphrodite 1 | Archaic (Aeolic) | 3 |

## Greek epigraphy (7 corpora)

Install all seven at once with `aegean library install epigraphy` (~9.1 MB):

| Corpus ID | Title | Documents | Tokens | Size | License |
| --- | --- | ---: | ---: | --- | --- |
| `isicily` | I.Sicily Greek Inscriptions (2,855 texts) | 2,855 | 28,913 | ~2.5 MB | CC-BY-4.0 |
| `iip` | IIP Greek Inscriptions of Israel/Palestine (2,113 texts) | 2,113 | 14,007 | ~1.5 MB | CC-BY-NC-4.0 |
| `iospe` | IOSPE Northern Black Sea Inscriptions (1,194 texts) | 1,194 | 15,220 | ~1.5 MB | CC-BY-4.0 |
| `igcyr` | IGCyr/GVCyr Inscriptions of Cyrenaica (997 texts) | 997 | 12,963 | ~1.5 MB | CC-BY-NC-SA-4.0 |
| `aphrodisias` | Inscriptions of Aphrodisias (IAph2007, 1,471 texts) | 1,471 | 38,556 | ~0.5 MB | CC BY 2.5 |
| `crete` | Cretan Institutional Inscriptions (600 Archaic–Hellenistic texts) | 600 | 50,995 | ~0.6 MB | CC BY-NC-SA 4.0 |
| `edh` | EDH Greek Inscriptions (1,286 texts) | 1,286 | 26,937 | ~1.0 MB | CC-BY-SA-4.0 |

## Documentary papyri (`ddbdp`)

| Corpus ID | Title | Documents | Tokens | Size | License |
| --- | --- | ---: | ---: | --- | --- |
| `ddbdp` | DDbDP Greek Documentary Papyri (57,331 texts, SQLite) | 57,331 | 4,373,912 | ~219 MB | CC-BY-3.0 |

Query DDbDP through SQLite FTS without loading all texts into RAM: `aegean db search ddbdp "βασιλέως"` or `aegean.db.stream(aegean.scripts.greek.ddbdp_db())`.

## Greek lexica & dictionaries

Install all five hosted dictionary indexes at once with `aegean library install lexica` (~19.3 MB):

| Key / Asset | Dictionary | Scope | Delivery | License |
| --- | --- | --- | --- | --- |
| `dodson` | Dodson Greek-English Lexicon | Koine / New Testament (~5,500 entries) | Bundled (offline) | CC0-1.0 / Public Domain |
| `strongs-greek` | Extended Strong's Greek Lexicon (STEPBible TBESG + OpenScriptures) | NT, LXX, Apocrypha & Apostolic Fathers (11,142 entries + root trees) | Hosted (~1.5 MB) | CC-BY-SA-4.0 |
| `lsj-index` | Liddell-Scott-Jones (LSJ) | Classical, Hellenistic & Imperial Greek (~116k headwords) | Hosted (~15 MB) | CC BY-SA 4.0 |
| `middle-liddell-index` | Middle Liddell (Intermediate Greek-English Lexicon) | General Ancient Greek | Hosted (~2.4 MB) | Public Domain |
| `cunliffe-index` | Cunliffe Lexicon of the Homeric Dialect | Homeric Greek (*Iliad* & *Odyssey*) | Hosted (~1.3 MB) | Public Domain |
| `autenrieth-index` | Autenrieth Homeric Dictionary | Homeric Greek | Hosted (~0.6 MB) | Public Domain |
| `abbott-smith-index` | Abbott-Smith Manual Greek Lexicon of the New Testament | Koine / NT Greek | Hosted (~0.13 MB) | Public Domain |
