# Corpus Catalog

Directory of every corpus, collection, biblical text, patristic work, inscription set, papyrus archive, and literary text available in pyaegean, organized by category. Core Aegean corpora and small Greek/Biblical seed samples ship inside the package; all large corpora fetch on demand to your local cache with SHA-256 verification.

[Catalog Overview](Catalog) · [Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) · [Biblical & Second Temple](Catalog-Biblical) · [John Chrysostom](Catalog-Chrysostom) · [Church Fathers & Patristics](Catalog-Church-Fathers) · [Archaic & Classical](Catalog-Classical-Greek) · [Hellenistic](Catalog-Hellenistic-Greek) · [Imperial](Catalog-Imperial-Greek) · [Late Antique & Byzantine](Catalog-Late-Antique-and-Byzantine) · [Perseus & First1KGreek](Catalog-Perseus-and-First1K)

---

## Browse by category

| Category | Contents | Catalog page |
| --- | --- | --- |
| **Aegean Scripts, Epigraphy & Papyri** | 6 Aegean script corpora (`lineara`, `sigla`, `linearb`, `damos`, `cypriot`, `cyprominoan`), bundled Greek seed (`greek`), 7 Greek epigraphic corpora, DDbDP documentary papyri (57,331 texts), and 7 Greek lexica | [Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) |
| **Biblical & Second Temple Greek** | 9 Greek NT editions, 27 NT books, 13 early manuscript witnesses (`01`–`05`, `032`, `P45`–`P75`), 56 Septuagint (LXX) books (incl. Ecclesiastes), and 44 Greek OT Pseudepigrapha works | [Biblical & Second Temple](Catalog-Biblical) |
| **John Chrysostom** | 155 open-licensed Greek works (3,738,372 tokens): homilies, sermons, 26 biblical commentary series, treatises, and letters | [John Chrysostom](Catalog-Chrysostom) |
| **Church Fathers & Patristics** | 432 Early & Nicene Fathers works (58 authors), 280 Post-Nicene & Eastern Fathers works (38 authors), 15 Open Apostolic Fathers, 33 *Patrologia Graeca* volumes, and 112 indexed patristic biblical commentaries | [Church Fathers & Patristics](Catalog-Church-Fathers) |
| **Archaic & Classical Greek** | 684 works across 246 authors (8th–4th c. BCE, 5,088,194 tokens) plus 54 Homer Multitext Venetus A *Iliad* & *Scholia* documents | [Archaic & Classical Greek](Catalog-Classical-Greek) |
| **Hellenistic Greek** | 740 works across 587 authors (3rd–1st c. BCE, 4,672,040 tokens), including Jewish-Greek literature and DFHG fragmentary historians | [Hellenistic Greek](Catalog-Hellenistic-Greek) |
| **Imperial Greek** | 1,078 works across 373 authors (1st–3rd c. CE, 14,662,168 tokens): Plutarch, Galen, Lucian, Josephus, Epictetus, Marcus Aurelius, Cassius Dio | [Imperial Greek](Catalog-Imperial-Greek) |
| **Late Antique & Byzantine Greek** | 290 Late Antique works (82 authors, 4th–6th c. CE), 185 Byzantine literary & historical works through 1453 (94 authors), and 12 Byzantine & Early Modern vernacular works | [Late Antique & Byzantine Greek](Catalog-Late-Antique-and-Byzantine) |
| **Perseus & First1KGreek (TEI)** | 1,778 on-demand TEI works (768 Perseus `canonical-greekLit` + 1,010 `First1KGreek`) addressable by CTS ID (`tlgAAAA.tlgBBB`) | [Perseus & First1KGreek](Catalog-Perseus-and-First1K) |

---

## All 30 registered corpora

Every ID below loads via `aegean.load("<id>")` (or `aegean.open("<id>")`) in Python and works anywhere the CLI expects a `CORPUS` argument. The 8 categorized Greek library collections total **3,844 works** (**64,350,370 tokens**) and also support single-work loading via `aegean.open("ogc002060")` or `aegean greek work ogc002060`.

### Aegean scripts, epigraphy, papyri & seed sample

| Corpus ID | Title | Docs | Tokens | Delivery | Size | License |
| --- | --- | ---: | ---: | --- | --- | --- |
| `lineara` | Linear A Corpus (GORILA) | 1,721 | 6,406 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `linearb` | Linear B Sample Tablets | 18 | 92 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `cypriot` | Cypriot Syllabary Corpus | 180 | 628 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `cyprominoan` | Cypro-Minoan Corpus | 2 | 4 | Bundled (offline) | bundled | Apache-2.0 / public academic transcriptions |
| `greek` | Ancient Greek Sample Texts | 5 | 27 | Bundled (offline) | bundled | Apache-2.0 / public domain texts |
| `damos` | DAMOS Linear B Corpus (~5,900 tablets) | 5,932 | 54,476 | Hosted (`damos-corpus`) | ~3.0 MB | CC BY-NC-SA 4.0 |
| `sigla` | SigLA Linear A Corpus (802 documents) | 802 | 2,616 | Hosted (`sigla-corpus`) | ~1.3 MB | CC BY-NC-SA 4.0 |
| `isicily` | I.Sicily Greek Inscriptions (2,855 texts) | 2,855 | 28,913 | Hosted (`isicily-corpus`) | ~2.5 MB | CC-BY-4.0 |
| `iip` | IIP Greek Inscriptions of Israel/Palestine (2,113 texts) | 2,113 | 14,007 | Hosted (`iip-corpus`) | ~1.5 MB | CC-BY-NC-4.0 |
| `iospe` | IOSPE Northern Black Sea Inscriptions (1,194 texts) | 1,194 | 15,220 | Hosted (`iospe-corpus`) | ~1.5 MB | CC-BY-4.0 |
| `igcyr` | IGCyr/GVCyr Inscriptions of Cyrenaica (997 texts) | 997 | 12,963 | Hosted (`igcyr-corpus`) | ~1.5 MB | CC-BY-NC-SA-4.0 |
| `aphrodisias` | Inscriptions of Aphrodisias (IAph2007, 1,471 texts) | 1,471 | 38,556 | Hosted (`aphrodisias-corpus`) | ~0.5 MB | CC BY 2.5 |
| `crete` | Cretan Institutional Inscriptions (600 Archaic–Hellenistic texts) | 600 | 50,995 | Hosted (`crete-corpus`) | ~0.6 MB | CC BY-NC-SA 4.0 |
| `edh` | EDH Greek Inscriptions (1,286 texts) | 1,286 | 26,937 | Hosted (`edh-corpus`) | ~1.0 MB | CC-BY-SA-4.0 |
| `ddbdp` | DDbDP Greek Documentary Papyri (57,331 texts, SQLite) | 57,331 | 4,373,912 | Hosted (`ddbdp-corpus`) | ~219 MB | CC-BY-3.0 |

### Biblical & Second Temple Greek

| Corpus ID | Title | Docs | Tokens | Delivery | Size | License |
| --- | --- | ---: | ---: | --- | --- | --- |
| `nt` | Greek New Testament (Nestle 1904, 27 books) | 260 | 137,779 | Hosted (`nt-corpus`) | ~18 MB | CC0-1.0 / Public Domain |
| `lxx` | Septuagint / LXX (Swete + Ecclesiastes, 56 books) | 1,149 | 592,436 | Hosted (`lxx-corpus`) | ~1.7 MB | CC BY-SA 4.0 |
| `pseudepigrapha` | Greek Old Testament Pseudepigrapha (44 OCP Second Temple works) | 44 | 171,306 | Hosted (`pseudepigrapha-corpus`) | ~2.7 MB | CC BY 4.0 |

### Church Fathers & Patristics

| Corpus ID | Title | Docs | Tokens | Delivery | Size | License |
| --- | --- | ---: | ---: | --- | --- | --- |
| `apostolic-fathers` | Open Apostolic Fathers (15 hand-corrected Greek works) | 15 | 64,944 | Hosted (`apostolic-fathers-corpus`) | ~1.0 MB | CC BY-SA 4.0 |
| `chrysostom` | John Chrysostom Complete Open Greek Corpus (155 works, 3.74M tokens) | 155 | 3,738,372 | Hosted (`chrysostom-corpus`) | ~12.3 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `church-fathers-early` | Early & Nicene Church Fathers (432 works, 58 authors, 6.22M tokens) | 432 | 6,216,570 | Hosted (`church-fathers-early-corpus`) | ~21.0 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `church-fathers-late` | Post-Nicene, Eastern Fathers, Saints & Councils (280 works, 38 authors, 7.96M tokens) | 280 | 7,962,722 | Hosted (`church-fathers-late-corpus`) | ~26.7 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `patrologia` | Patrologia Graeca (33 CGPG volumes, 6.79M words; 9 commentary vols) | 33 | 6,787,292 | Hosted (`patrologia-graeca-corpus`) | ~23.5 MB | CC BY 4.0 |

### Archaic, Classical, Hellenistic, Imperial & Late Antique Greek

| Corpus ID | Title | Docs | Tokens | Delivery | Size | License |
| --- | --- | ---: | ---: | --- | --- | --- |
| `classical-greek` | Archaic & Classical Greek Literature (684 works, 246 authors, 5.09M tokens) | 684 | 5,088,194 | Hosted (`classical-greek-corpus`) | ~17.3 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `hellenistic-greek` | Hellenistic, Jewish-Greek & Fragmentary Historians (740 works, 587 authors, 4.67M tokens) | 740 | 4,672,040 | Hosted (`hellenistic-greek-corpus`) | ~16.3 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `imperial-greek` | Imperial Greek Literature, Philosophy & Medicine (1,078 works, 373 authors, 14.66M tokens) | 1,078 | 14,662,168 | Hosted (`imperial-greek-corpus`) | ~50.2 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `late-antique-greek` | Late Antique Philosophy, Rhetoric & Scholia (290 works, 82 authors, 11.33M tokens) | 290 | 11,333,916 | Hosted (`late-antique-greek-corpus`) | ~38.9 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `homer-scholia` | Homer Multitext Venetus A Iliad & Scholia (54 docs, 331K tokens) | 54 | 331,365 | Hosted (`homer-scholia-corpus`) | ~5.5 MB | CC BY-NC 4.0 |

### Byzantine Greek

| Corpus ID | Title | Docs | Tokens | Delivery | Size | License |
| --- | --- | ---: | ---: | --- | --- | --- |
| `byzantine-lit` | Byzantine History, Literature & Lexicography (185 works, 94 authors, 10.68M tokens) | 185 | 10,676,388 | Hosted (`byzantine-lit-corpus`) | ~38.3 MB | CC BY-SA 4.0 / CC BY 4.0 / Public Domain |
| `byzantine` | Byzantine & Early Modern Vernacular Greek (12 works, 189K tokens) | 12 | 189,375 | Hosted (`byzantine-corpus`) | ~2.5 MB | Public Domain / CC BY-SA 3.0 |

---

## Named install packs (10 packs)

Install whole groups at once with `aegean library install <pack>` or `aegean.library.install("<pack>")`:

| Pack ID | Aliases | Included assets | Approx. size |
| --- | --- | --- | --- |
| `biblical` | `bible`, `koine`, `nt-all` | `nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, `lxx-corpus` | ~27 MB |
| `church-fathers` | `fathers`, `patristics-full`, `saints` | `chrysostom-corpus`, `church-fathers-early-corpus`, `church-fathers-late-corpus`, `apostolic-fathers-corpus` | ~61 MB |
| `patristic` | `second-temple` | `apostolic-fathers-corpus`, `pseudepigrapha-corpus`, `patrologia-graeca-corpus` | ~27.2 MB |
| `ancient-greek` | `classical-pack`, `ancient-library` | `classical-greek-corpus`, `hellenistic-greek-corpus`, `imperial-greek-corpus`, `late-antique-greek-corpus` | ~123 MB |
| `byzantine-pack` | `byzantine-all`, `medieval-greek` | `byzantine-lit-corpus`, `byzantine-corpus` | ~41 MB |
| `aegean` | `scripts`, `linear` | `damos-corpus`, `sigla-corpus` | ~4.3 MB |
| `epigraphy` | `inscriptions` | `isicily-corpus`, `iip-corpus`, `iospe-corpus`, `igcyr-corpus`, `aphrodisias-corpus`, `crete-corpus`, `edh-corpus` | ~9.1 MB |
| `literary` | `epic`, `scholia` | `homer-scholia-corpus`, `byzantine-corpus` | ~8.0 MB |
| `lexica` | `dictionaries`, `lexicons` | `lsj-index`, `middle-liddell-index`, `cunliffe-index`, `autenrieth-index`, `abbott-smith-index` | ~19.3 MB |
| `neural` | `models`, `nlp` | `grc-joint`, `grc-paradigms` | ~173 MB |

---

For dataset checksums, upstream commit pins, and full licensing terms, see [Data & Provenance](Data-and-Provenance) and [`NOTICE`](https://github.com/ryanpavlicek/pyaegean/blob/main/NOTICE).
