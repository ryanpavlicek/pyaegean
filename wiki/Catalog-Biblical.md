# Catalog: Biblical & Second Temple Greek

[Catalog Overview](Catalog) · [Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) · [Biblical & Second Temple](Catalog-Biblical) · [John Chrysostom](Catalog-Chrysostom) · [Church Fathers & Patristics](Catalog-Church-Fathers) · [Archaic & Classical](Catalog-Classical-Greek) · [Hellenistic](Catalog-Hellenistic-Greek) · [Imperial](Catalog-Imperial-Greek) · [Late Antique & Byzantine](Catalog-Late-Antique-and-Byzantine) · [Perseus & First1KGreek](Catalog-Perseus-and-First1K)

All Greek New Testament editions, books, early manuscript witnesses, Septuagint (LXX) books, and Greek Old Testament Pseudepigrapha available through `aegean.greek.bible`, `aegean bible`, `aegean.load("nt")`, `aegean.load("lxx")`, and `aegean.load("pseudepigrapha")`.

Install the Biblical pack (`nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, `lxx-corpus`, ~27 MB total) with `aegean bible install` or `aegean library install biblical`.

## Greek New Testament editions (9 editions)

| Edition ID | Name | Editor / Source | Asset | Gold annotations | License |
| --- | --- | --- | --- | --- | --- |
| `nestle1904` | Nestle 1904 Greek New Testament | Eberhard Nestle (digital text Diego Santos; morph Ulrik Sandborg-Petersen) | `nt-corpus` | Yes (lemma, morph, Strong's, UPOS, gloss) | CC0-1.0 (morphology, lemmas, Strong's); base text public domain |
| `sblgnt` | SBL Greek New Testament (2010) | Michael W. Holmes (SBL / Logos) | `nt-editions` | Greek text | CC BY 4.0 (SBLGNT text); CC BY-SA 3.0 (MorphGNT) |
| `srgnt` | Statistical Restoration Greek New Testament | Alan Bunning (Center for New Testament Restoration) | `nt-editions` | Greek text | CC BY 4.0 |
| `bhp` | Bunning Heuristic Prototype Greek New Testament | Alan Bunning (Center for New Testament Restoration) | `nt-editions` | Greek text | CC BY 4.0 |
| `tisch` | Tischendorf 8th Edition (Editio Octava Critica Maior, 1869–1872) | Constantin von Tischendorf (digital text G. Clint Yale & Ulrik Sandborg-Petersen) | `nt-editions` | Greek text | Public Domain |
| `wh` | Westcott–Hort Greek New Testament (1881, unaccented Unicode) | Brooke Foss Westcott & Fenton John Anthony Hort (digital text Maurice A. Robinson) | `nt-editions` | Greek text | Public Domain |
| `byz` | Robinson–Pierpont Byzantine Majority Textform | Maurice A. Robinson & William G. Pierpont | `nt-editions` | Greek text | Public Domain |
| `antoniades` | Antoniades 1904 Patriarchal Edition (Ecumenical Patriarchate, unaccented Unicode) | Basileios Antoniades (digital text Maurice A. Robinson et al.) | `nt-editions` | Greek text | Public Domain |
| `tr` | Textus Receptus (King James Greek Underlying Text) | Center for New Testament Restoration (KJTR) | `nt-editions` | Greek text | CC BY 4.0 |

## Greek New Testament books (27 books)

| # | Canonical ID | Accepted aliases |
| ---: | --- | --- |
| 1 | `Matt` | `matthew`, `matt`, `mt` |
| 2 | `Mark` | `mark`, `mk`, `mrk` |
| 3 | `Luke` | `luke`, `lk`, `luk` |
| 4 | `John` | `john`, `jn`, `jhn` |
| 5 | `Acts` | `acts`, `act` |
| 6 | `Rom` | `romans`, `rom`, `rm` |
| 7 | `1Cor` | `1corinthians`, `1cor`, `1co` |
| 8 | `2Cor` | `2corinthians`, `2cor`, `2co` |
| 9 | `Gal` | `galatians`, `gal`, `ga` |
| 10 | `Eph` | `ephesians`, `eph` |
| 11 | `Phil` | `philippians`, `phil`, `php` |
| 12 | `Col` | `colossians`, `col` |
| 13 | `1Thess` | `1thessalonians`, `1thess`, `1th` |
| 14 | `2Thess` | `2thessalonians`, `2thess`, `2th` |
| 15 | `1Tim` | `1timothy`, `1tim`, `1ti` |
| 16 | `2Tim` | `2timothy`, `2tim`, `2ti` |
| 17 | `Titus` | `titus`, `tit` |
| 18 | `Phlm` | `philemon`, `phlm`, `phm` |
| 19 | `Heb` | `hebrews`, `heb` |
| 20 | `Jas` | `james`, `jas`, `jms` |
| 21 | `1Pet` | `1peter`, `1pet`, `1pe` |
| 22 | `2Pet` | `2peter`, `2pet`, `2pe` |
| 23 | `1John` | `1john`, `1jn`, `1jhn` |
| 24 | `2John` | `2john`, `2jn`, `2jhn` |
| 25 | `3John` | `3john`, `3jn`, `3jhn` |
| 26 | `Jude` | `jude`, `jud` |
| 27 | `Rev` | `revelation`, `rev`, `rv`, `apocalypse` |

## Early Greek NT manuscript witnesses (13 witnesses, 2nd–5th c. CE)

Hosted in `nt-witnesses` (~1.5 MB, CC BY-SA 4.0, Center for New Testament Restoration):

| Siglum | Symbol | Manuscript | Date | Type | Text-type / Coverage |
| --- | --- | --- | --- | --- | --- |
| `01` | ℵ | Codex Sinaiticus | 4th c. CE | uncial | Alexandrian (Western in John 1:1–8:38) |
| `02` | A | Codex Alexandrinus | 5th c. CE | uncial | Byzantine in Gospels; Alexandrian in Acts–Revelation |
| `03` | B | Codex Vaticanus | 4th c. CE | uncial | Alexandrian |
| `04` | C | Codex Ephraemi Rescriptus | 5th c. CE | uncial | Mixed / Alexandrian–Byzantine palimpsest |
| `05` | D | Codex Bezae Cantabrigiensis | 5th c. CE | uncial | Western (Greek–Latin bilingual) |
| `032` | W | Codex Washingtonianus (Freer Gospels) | 4th/5th c. CE | uncial | Block-mixed (Alexandrian, Western, Byzantine, Caesarean) |
| `P45` | 𝔓45 | Papyrus 45 (Chester Beatty I) | 3rd c. CE | papyrus | Early Alexandrian / Caesarean-leaning (Gospels & Acts) |
| `P46` | 𝔓46 | Papyrus 46 (Chester Beatty II) | c. 200 CE | papyrus | Early Alexandrian (Pauline Epistles & Hebrews) |
| `P47` | 𝔓47 | Papyrus 47 (Chester Beatty III) | 3rd c. CE | papyrus | Early Alexandrian (Revelation 9–17) |
| `P52` | 𝔓52 | Papyrus 52 (Rylands Library Papyrus P52) | 2nd c. CE | papyrus | Earliest extant NT fragment (John 18:31–33, 37–38) |
| `P66` | 𝔓66 | Papyrus 66 (Bodmer II) | c. 200 CE | papyrus | Early Alexandrian with Western readings (Gospel of John) |
| `P72` | 𝔓72 | Papyrus 72 (Bodmer VII–VIII) | 3rd/4th c. CE | papyrus | Early Alexandrian (1–2 Peter & Jude) |
| `P75` | 𝔓75 | Papyrus 75 (Bodmer XIV–XV) | early 3rd c. CE | papyrus | Strict Alexandrian, close to Codex Vaticanus (Luke & John) |

## Septuagint (LXX) books (56 books, 29,470 verses, 592,436 tokens)

Hosted in `lxx-corpus` (`lxx-corpus-v2`, ~1.7 MB, CC BY-SA 4.0: Swete 1887–1894 via First1KGreek plus Greek Wikisource Ecclesiastes `tlg0527.tlg030`). Load via `aegean.load("lxx")`, `bible.load_lxx("Gen 1:1-5", interlinear=True)`, or `bible.load_lxx("MT Ps 23")`.

### Pentateuch (5 books)

| Book ID | Title | TLG Work ID | Aliases |
| --- | --- | --- | --- |
| `Gen` | Genesis | `tlg0527.tlg001` | `genesis`, `gen`, `gn`, `ge` |
| `Exod` | Exodus | `tlg0527.tlg002` | `exodus`, `exod`, `ex`, `exo` |
| `Lev` | Leviticus | `tlg0527.tlg003` | `leviticus`, `lev`, `lv` |
| `Num` | Numbers | `tlg0527.tlg004` | `numbers`, `num`, `nm`, `numeri` |
| `Deut` | Deuteronomy | `tlg0527.tlg005` | `deuteronomy`, `deut`, `dt`, `deu` |

### History (12 books)

| Book ID | Title | TLG Work ID | Aliases |
| --- | --- | --- | --- |
| `Josh` | Joshua | `tlg0527.tlg006` | `joshua`, `josh`, `josue`, `jos` |
| `Judg` | Judges | `tlg0527.tlg008` | `judges`, `judg`, `judices`, `jdg` |
| `Ruth` | Ruth | `tlg0527.tlg010` | `ruth`, `ru`, `rut` |
| `1Kgdms` | 1 Kingdoms (1 Samuel) | `tlg0527.tlg011` | `1kingdoms`, `1kgdms`, `1samuel`, `1sam`, `1sa`, `1reg`, `regnorum1` |
| `2Kgdms` | 2 Kingdoms (2 Samuel) | `tlg0527.tlg012` | `2kingdoms`, `2kgdms`, `2samuel`, `2sam`, `2sa`, `2reg`, `regnorum2` |
| `3Kgdms` | 3 Kingdoms (1 Kings) | `tlg0527.tlg013` | `3kingdoms`, `3kgdms`, `1kings`, `1kgs`, `1ki`, `3reg`, `regnorum3` |
| `4Kgdms` | 4 Kingdoms (2 Kings) | `tlg0527.tlg014` | `4kingdoms`, `4kgdms`, `2kings`, `2kgs`, `2ki`, `4reg`, `regnorum4` |
| `1Chr` | 1 Chronicles (1 Paralipomenon) | `tlg0527.tlg015` | `1chronicles`, `1chr`, `1ch`, `1par`, `1paralipomenon` |
| `2Chr` | 2 Chronicles (2 Paralipomenon) | `tlg0527.tlg016` | `2chronicles`, `2chr`, `2ch`, `2par`, `2paralipomenon` |
| `1Esdr` | 1 Esdras | `tlg0527.tlg017` | `1esdras`, `1esdr`, `esdras1` |
| `2Esdr` | 2 Esdras (Ezra–Nehemiah) | `tlg0527.tlg018` | `2esdras`, `2esdr`, `esdras2`, `ezra`, `ezr`, `nehemiah`, `neh` |
| `Esth` | Esther | `tlg0527.tlg019` | `esther`, `esth`, `est` |

### Deuterocanonical (15 books)

| Book ID | Title | TLG Work ID | Aliases |
| --- | --- | --- | --- |
| `Jdt` | Judith | `tlg0527.tlg020` | `judith`, `jdt` |
| `Tob` | Tobit | `tlg0527.tlg021` | `tobit`, `tob`, `tobias` |
| `1Macc` | 1 Maccabees | `tlg0527.tlg023` | `1maccabees`, `1macc`, `1mac` |
| `2Macc` | 2 Maccabees | `tlg0527.tlg024` | `2maccabees`, `2macc`, `2mac` |
| `3Macc` | 3 Maccabees | `tlg0527.tlg025` | `3maccabees`, `3macc`, `3mac` |
| `4Macc` | 4 Maccabees | `tlg0527.tlg026` | `4maccabees`, `4macc`, `4mac` |
| `Wis` | Wisdom of Solomon | `tlg0527.tlg033` | `wisdom`, `wisdomofsolomon`, `wis`, `sapientia` |
| `Sir` | Sirach (Ecclesiasticus) | `tlg0527.tlg034` | `sirach`, `sir`, `ecclesiasticus`, `ecclus`, `bensira` |
| `PssSol` | Psalms of Solomon | `tlg0527.tlg035` | `psalmsofsolomon`, `psssol`, `pssol` |
| `Bar` | Baruch | `tlg0527.tlg050` | `baruch`, `bar` |
| `EpJer` | Epistle of Jeremiah | `tlg0527.tlg052` | `epistleofjeremiah`, `epjer`, `letterofjeremiah` |
| `Sus-OG` | Susanna (Old Greek) | `tlg0527.tlg054` | `susanna-og`, `sus-og`, `susannaog` |
| `Sus-Th` | Susanna (Theodotion) | `tlg0527.tlg055` | `susanna`, `sus`, `susanna-th`, `sus-th` |
| `Bel-OG` | Bel and the Dragon (Old Greek) | `tlg0527.tlg058` | `bel-og`, `belog` |
| `Bel-Th` | Bel and the Dragon (Theodotion) | `tlg0527.tlg059` | `bel`, `belandthedragon`, `bel-th` |

### Wisdom (6 books)

| Book ID | Title | TLG Work ID | Aliases |
| --- | --- | --- | --- |
| `Ps` | Psalms | `tlg0527.tlg027` | `psalms`, `psalm`, `ps`, `psa`, `pss`, `psalmi` |
| `Odes` | Odes | `tlg0527.tlg028` | `odes`, `odae`, `ode` |
| `Prov` | Proverbs | `tlg0527.tlg029` | `proverbs`, `prov`, `pr`, `pro`, `proverbia` |
| `Eccl` | Ecclesiastes (Qoheleth) | `tlg0527.tlg030` | `ecclesiastes`, `eccl`, `ecc`, `qoh`, `qoheleth`, `kohelet` |
| `Song` | Song of Songs (Canticum) | `tlg0527.tlg031` | `song`, `songofsongs`, `songofsolomon`, `sos`, `cant`, `canticum`, `canticles` |
| `Job` | Job | `tlg0527.tlg032` | `job`, `jb` |

### Minor Prophets (12 books)

| Book ID | Title | TLG Work ID | Aliases |
| --- | --- | --- | --- |
| `Hos` | Hosea | `tlg0527.tlg036` | `hosea`, `hos`, `osee` |
| `Amos` | Amos | `tlg0527.tlg037` | `amos`, `am`, `amo` |
| `Mic` | Micah | `tlg0527.tlg038` | `micah`, `mic`, `michaeas` |
| `Joel` | Joel | `tlg0527.tlg039` | `joel`, `jl`, `joe` |
| `Obad` | Obadiah | `tlg0527.tlg040` | `obadiah`, `obad`, `ob`, `oba`, `abdias` |
| `Jonah` | Jonah | `tlg0527.tlg041` | `jonah`, `jon`, `jonas` |
| `Nah` | Nahum | `tlg0527.tlg042` | `nahum`, `nah`, `na` |
| `Hab` | Habakkuk | `tlg0527.tlg043` | `habakkuk`, `hab`, `habacuc` |
| `Zeph` | Zephaniah | `tlg0527.tlg044` | `zephaniah`, `zeph`, `zep`, `sophonias` |
| `Hag` | Haggai | `tlg0527.tlg045` | `haggai`, `hag`, `hg`, `aggaeus` |
| `Zech` | Zechariah | `tlg0527.tlg046` | `zechariah`, `zech`, `zec`, `zacharias` |
| `Mal` | Malachi | `tlg0527.tlg047` | `malachi`, `mal`, `malachias` |

### Major Prophets (6 books)

| Book ID | Title | TLG Work ID | Aliases |
| --- | --- | --- | --- |
| `Isa` | Isaiah | `tlg0527.tlg048` | `isaiah`, `isa`, `is`, `isaias` |
| `Jer` | Jeremiah | `tlg0527.tlg049` | `jeremiah`, `jer`, `jr`, `jeremias` |
| `Lam` | Lamentations | `tlg0527.tlg051` | `lamentations`, `lam`, `threni` |
| `Ezek` | Ezekiel | `tlg0527.tlg053` | `ezekiel`, `ezek`, `ez`, `eze`, `ezechiel` |
| `Dan-OG` | Daniel (Old Greek) | `tlg0527.tlg056` | `daniel-og`, `dan-og`, `danielog` |
| `Dan-Th` | Daniel (Theodotion) | `tlg0527.tlg057` | `daniel`, `dan`, `dn`, `daniel-th`, `dan-th` |

## Greek Old Testament Pseudepigrapha (44 works, 171,306 tokens)

Hosted in `pseudepigrapha-corpus` (~2.7 MB, CC BY 4.0, *Online Critical Pseudepigrapha*). Load via `aegean.load("pseudepigrapha")` or install with `aegean library install patristic`.

| Document ID | Work | Tokens |
| --- | --- | ---: |
| `1En` | 1 Enoch | 8,665 |
| `2Bar` | 2 (Syriac Apocalypse of) Baruch | 212 |
| `3Bar` | 3 (Greek Apocalypse of) Baruch | 3,141 |
| `3Macc` | 3 Maccabees | 5,112 |
| `4Bar` | Paraleipomena Ieremiou (4 Baruch) | 4,186 |
| `4Macc` | 4 Maccabees | 7,859 |
| `AdamEve` | Life of Adam and Eve | 4,460 |
| `ApDan` | Apocalypse of Daniel | 2,152 |
| `ApEzra` | Greek Apocalypse of Ezra | 2,854 |
| `ApocrEzek` | Apocryphon of Ezekiel | 1,157 |
| `ArisEx` | Aristeas the Exegete | 209 |
| `Aristob` | Aristobulus | 3,153 |
| `Artap` | Artapanus | 1,872 |
| `ClMal` | Cleodemus Malchus | 286 |
| `Demetr` | Demetrius the Chronographer | 1,418 |
| `ElMod` | Eldad and Modad | 18 |
| `Eup` | Eupolemus | 1,847 |
| `EzekTrag` | Ezekiel the Tragedian | 1,645 |
| `HistRech` | The History of the Rechabites | 3,573 |
| `JosAsen` | Joseph and Aseneth | 8,184 |
| `Jub` | Jubilees | 2,287 |
| `Justus` | Justus of Tiberias | 232 |
| `LetAris` | Letter of Aristeas to Philocrates | 12,933 |
| `LivPro` | Lives of the Prophets | 2,713 |
| `NarrMois` | Narratio de Moyse et Josue | 2,507 |
| `OrJos` | Prayer of Joseph | 228 |
| `OrMan` | Prayer of Manasseh | 317 |
| `PhEPoet` | Philo the Epic Poet | 272 |
| `Ps-Eup` | Pseudo-Eupolemus | 450 |
| `PsHecat` | Fragments of Pseudo-Hecataeus | 903 |
| `PsOrph` | Testament of Orpheus (Hieroi Logoi) | 512 |
| `PsPhoc` | Sentences of Pseudo-Phocylides | 1,565 |
| `PssSol` | The Psalms of Solomon | 5,112 |
| `Sedrach` | Apocalypse of Sedrach | 2,350 |
| `SibOr` | Sibylline Oracles | 29,228 |
| `T12P` | Testaments of the Twelve Patriarchs | 20,072 |
| `TAbA` | Testament of Abraham Recension A | 6,954 |
| `TAbB` | Testament of Abraham Recension B | 3,213 |
| `TAdam` | Testament of Adam | 396 |
| `Thallus` | Fragments of Thallus the Chronographer | 178 |
| `Theod` | Theodotus | 709 |
| `Theoph` | Fragments of Theophilus | 25 |
| `TJob` | Testament of Job | 8,010 |
| `TSol` | Testament of Solomon | 8,137 |
