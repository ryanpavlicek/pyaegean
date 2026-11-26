# Catalog: Church Fathers & Patristics

[Catalog Overview](Catalog) · [Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) · [Biblical & Second Temple](Catalog-Biblical) · [John Chrysostom](Catalog-Chrysostom) · [Church Fathers & Patristics](Catalog-Church-Fathers) · [Archaic & Classical](Catalog-Classical-Greek) · [Hellenistic](Catalog-Hellenistic-Greek) · [Imperial](Catalog-Imperial-Greek) · [Late Antique & Byzantine](Catalog-Late-Antique-and-Byzantine) · [Perseus & First1KGreek](Catalog-Perseus-and-First1K)

All Greek patristic works outside John Chrysostom's dedicated 155-work catalog ([John Chrysostom](Catalog-Chrysostom)): Open Apostolic Fathers, Early & Nicene Fathers (2nd–4th c. CE), Post-Nicene & Eastern Fathers (5th–15th c. CE), digitized *Patrologia Graeca* volumes, and all 112 indexed Greek patristic biblical commentaries.

```bash
aegean library install church-fathers   # John Chrysostom (155) + Early/Late Fathers (712) + Apostolic Fathers (15)
aegean library install patristic        # Apostolic Fathers (15) + OT Pseudepigrapha (44) + Patrologia Graeca (33 vols)
```

## Open Apostolic Fathers (`apostolic-fathers`: 15 works, 64,944 tokens)

Hosted in `apostolic-fathers-corpus` (~1.0 MB, CC BY-SA 4.0, twice hand-corrected). Load via `aegean.load("apostolic-fathers")`.

| Document ID | Work | Period | Tokens |
| --- | --- | --- | ---: |
| `1Clem` | Clement of Rome: 1 Clement (First Epistle to the Corinthians) | c. 96 CE | 9,831 |
| `2Clem` | Pseudo-Clement: 2 Clement | 2nd c. CE | 3,013 |
| `IgnEph` | Ignatius of Antioch: Epistle to the Ephesians | c. 110 CE | 1,772 |
| `IgnMagn` | Ignatius of Antioch: Epistle to the Magnesians | c. 110 CE | 1,055 |
| `IgnTrall` | Ignatius of Antioch: Epistle to the Trallians | c. 110 CE | 950 |
| `IgnRom` | Ignatius of Antioch: Epistle to the Romans | c. 110 CE | 1,021 |
| `IgnPhld` | Ignatius of Antioch: Epistle to the Philadelphians | c. 110 CE | 1,018 |
| `IgnSmyrn` | Ignatius of Antioch: Epistle to the Smyrnaeans | c. 110 CE | 1,145 |
| `IgnPol` | Ignatius of Antioch: Epistle to Polycarp | c. 110 CE | 785 |
| `PolPhil` | Polycarp of Smyrna: Epistle to the Philippians | c. 110–140 CE | 1,582 |
| `Did` | Anonymous: Didache (Teaching of the Twelve Apostles) | late 1st / early 2nd c. CE | 2,199 |
| `Barn` | Pseudo-Barnabas: Epistle of Barnabas | c. 70–132 CE | 6,714 |
| `Herm` | Hermas: The Shepherd of Hermas | early 2nd c. CE | 28,602 |
| `MartPol` | Anonymous: Martyrdom of Polycarp | c. 155–160 CE | 2,647 |
| `Diogn` | Anonymous: Epistle to Diognetus | 2nd c. CE | 2,610 |

## Early & Nicene Church Fathers (`church-fathers-early`: 432 works, 58 authors, 6,216,570 tokens)

Hosted in `church-fathers-early-corpus` (~21.0 MB, Public Domain / CC BY 4.0 / CC BY-SA 4.0). Open any work directly with `aegean.open("<work_id>")` or `aegean greek work <work_id>`.

| Work ID | Author | Title | TLG | Tokens | License |
| --- | --- | --- | --- | ---: | --- |
| `ogc000008` | Acta Barnabae | Acta Barnabae | `tlg2949.tlg001` | 2,152 | CC-BY-SA-4.0 |
| `ogc000009` | Acta Joannis | Acta Joannis | `tlg0317.tlg001` | 12,397 | CC-BY-SA-4.0 |
| `ogc000010` | Acta Joannis | Acta Joannis (Recensio) | `tlg0317.tlg002` | 2,484 | CC-BY-SA-4.0 |
| `ogc003677` | Acta Justini Et Septem Sodalium | Acta Justini Et Septem Sodalium (Recensio B) | `tlg0384.tlg002` | 653 | CC-BY-4.0 |
| `ogc000011` | Acta Philippi | Acta Philippi | `tlg2948.tlg001` | 16,065 | CC-BY-SA-4.0 |
| `ogc000012` | Acta Thomae | Acta Thomae | `tlg2038.tlg001` | 28,852 | CC-BY-SA-4.0 |
| `ogc000193` | Amphilochius | Epistula Synodalis | `tlg2112.tlg015` | 776 | CC-BY-SA-4.0 |
| `ogc000503` | Athanasius | Contra Gentes | `tlg2035.tlg001` | 18,009 | CC-BY-SA-4.0 |
| `ogc000504` | Athanasius | De Azymis [Sp.] | `tlg2035.tlg058` | 1,728 | CC-BY-SA-4.0 |
| `ogc000505` | Athanasius | De Corpore Et Anima [Sp.] | `tlg2035.tlg103` | 642 | PD |
| `ogc000506` | Athanasius | De Decretis Nicaenae Synodi | `tlg2035.tlg003` | 20,068 | CC-BY-SA-4.0 |
| `ogc000507` | Athanasius | De Incarnatione Contra Apollinarium Libri Ii [Sp.] | `tlg2035.tlg124` | 14,352 | PD |
| `ogc000508` | Athanasius | De Incarnatione Verbi | `tlg2035.tlg002` | 19,800 | CC-BY-SA-4.0 |
| `ogc000509` | Athanasius | De Sabbatis Et Circumcisione [Sp.] | `tlg2035.tlg068` | 1,600 | PD |
| `ogc000510` | Athanasius | De Sancta Trinitate (Dialogi 1, 3, 5) [Sp.] | `tlg2035.tlg109` | 24,009 | PD |
| `ogc000511` | Athanasius | De Sancta Trinitate (Dialogi 2 And 4) [Sp.] | `tlg2035.tlg027` | 7,560 | PD |
| `ogc000512` | Athanasius | De Sententia Dionysii | `tlg2035.tlg004` | 7,126 | CC-BY-SA-4.0 |
| `ogc000513` | Athanasius | De Synodis Arimini In Italia Et Seleuciae In Isauria | `tlg2035.tlg010` | 21,193 | PD |
| `ogc000514` | Athanasius | De Virginitate [Sp.] | `tlg2035.tlg029` | 6,095 | PD |
| `ogc000515` | Athanasius | Dialogi Duo Contra Macedonianos [Sp.] | `tlg2035.tlg099` | 19,828 | PD |
| `ogc000516` | Athanasius | Disputatio Contra Arium [Sp.] | `tlg2035.tlg072` | 12,666 | PD |
| `ogc000517` | Athanasius | Doctrina Ad Antiochum Ducem [Sp.] | `tlg2035.tlg026` | 5,628 | PD |
| `ogc000518` | Athanasius | Doctrina Ad Monachos [Sp.] | `tlg2035.tlg102` | 1,128 | PD |
| `ogc000519` | Athanasius | Epistula Ad Adelphium | `tlg2035.tlg050` | 2,106 | PD |
| `ogc000520` | Athanasius | Epistula Ad Afros Episcopos | `tlg2035.tlg049` | 3,600 | PD |
| `ogc000521` | Athanasius | Epistula Ad Epictetum | `tlg2035.tlg110` | 3,204 | PD |
| `ogc000522` | Athanasius | Epistula Ad Jovianum | `tlg2035.tlg119` | 1,935 | PD |
| `ogc000523` | Athanasius | Epistula Ad Marcellinum De Interpretatione Psalmorum | `tlg2035.tlg059` | 7,824 | PD |
| `ogc000524` | Athanasius | Epistula Ad Maximum | `tlg2035.tlg051` | 959 | PD |
| `ogc000525` | Athanasius | Epistula Ad Monachos | `tlg2035.tlg055` | 1,422 | PD |
| `ogc000526` | Athanasius | Epistula Ad Rufinianum | `tlg2035.tlg015` | 316 | PD |
| `ogc000527` | Athanasius | Epistula Catholica [Sp.] | `tlg2035.tlg065` | 438 | PD |
| `ogc000528` | Athanasius | Epistula Festalis Xxxix (Fragmentum In Collectione Canonum) | `tlg2035.tlg014` | 667 | PD |
| `ogc000529` | Athanasius | Epistulae Ad Castorem [Sp.] | `tlg2035.tlg085` | 9,872 | PD |
| `ogc000530` | Athanasius | Epistulae Festales (Ap. Cosmam Indicopleustem) | `tlg2035.tlgX01` | 295 | PD |
| `ogc000531` | Athanasius | Epistulae Quattuor Ad Serapionem | `tlg2035.tlg043` | 22,684 | PD |
| `ogc000532` | Athanasius | Expositiones In Psalmos | `tlg2035.tlg061` | 203,414 | PD |
| `ogc000533` | Athanasius | Fragmenta Varia | `tlg2035.tlg054` | 10,425 | PD |
| `ogc000534` | Athanasius | Homilia De Passione Et Cruce Domini (Additamenta) | `tlg2035.tlg125` | 357 | PD |
| `ogc000535` | Athanasius | Homilia De Passione Et Cruce Domini [Sp.] | `tlg2035.tlg070` | 11,362 | PD |
| `ogc000536` | Athanasius | Homilia De Semente [Sp.] | `tlg2035.tlg069` | 5,035 | PD |
| `ogc000537` | Athanasius | Homilia In Occursum Domini [Sp.] | `tlg2035.tlg090` | 4,947 | PD |
| `ogc000538` | Athanasius | Homilia In Passionem Domini Et In Parasceve [Sp.] | `tlg2035.tlgX08` | 1,365 | PD |
| `ogc000539` | Athanasius | Homilia In Sanctum Andream [Sp.] | `tlg2035.tlgX12` | 1,038 | PD |
| `ogc000541` | Athanasius | Homilia In Sanctum Pascha [Sp.] | `tlg2035.tlgX09` | 946 | PD |
| `ogc000540` | Athanasius | Homilia In Sanctum Pascha Et In Recens Illuminatos [Sp.] | `tlg2035.tlgX10` | 2,962 | PD |
| `ogc000542` | Athanasius | In Caecum A Nativitate [Sp.] | `tlg2035.tlg091` | 9,516 | PD |
| `ogc003947` | Athanasius | In Illud: Omnia Mihi Tradita Sunt | `tlg2035.tlg039` | 2,157 | PD (ancient Greek text; public-domain Gutenberg edition) |
| `ogc000543` | Athanasius | In Illud: Profecti In Pagum Invenietis Pullum Alligatum [Sp.] | `tlg2035.tlg017` | 2,692 | PD |
| `ogc000544` | Athanasius | In Nativitatem Praecursoris [Sp.] | `tlg2035.tlg086` | 1,461 | PD |
| `ogc000545` | Athanasius | Interpretatio In Symbolum [Sp.] | `tlg2035.tlgX06` | 311 | PD |
| `ogc000546` | Athanasius | Liber De Definitionibus [Sp.] | `tlg2035.tlg075` | 4,144 | PD |
| `ogc000547` | Athanasius | Narratio De Cruce Seu Imagine Berytensi [Sp.] | `tlg2035.tlg082` | 1,980 | PD |
| `ogc000548` | Athanasius | Oratio I contra Arianos | `tlg2035.tlg130` | 23,223 | CC-BY-SA-4.0 |
| `ogc000549` | Athanasius | Oratio II contra Arianos | `tlg2035.tlg131` | 29,813 | CC-BY-SA-4.0 |
| `ogc000550` | Athanasius | Oratio III contra Arianos | `tlg2035.tlg132` | 24,017 | CC-BY-SA-4.0 |
| `ogc000551` | Athanasius | Oratio In Resurrectionem Et In Recens Baptizatos [Sp.] | `tlg2035.tlg036` | 1,889 | PD |
| `ogc000552` | Athanasius | Oratio Quarta Contra Arianos [Sp.] | `tlg2035.tlg117` | 10,986 | CC-BY-SA-4.0 |
| `ogc000553` | Athanasius | Orationes Tres Contra Arianos | `tlg2035.tlg042` | 74,999 | PD |
| `ogc002585` | Athanasius | Patrologia Graeca 26 (unsplit pages) |  | 7,758 | PD |
| `ogc000554` | Athanasius | Quaestiones Ad Antiochum Ducem [Sp.] | `tlg2035.tlg077` | 20,463 | PD |
| `ogc000555` | Athanasius | Quaestiones Aliae [Sp.] | `tlg2035.tlg081` | 4,322 | PD |
| `ogc000556` | Athanasius | Quaestiones In Evangelia [Sp.] | `tlg2035.tlg078` | 3,493 | PD |
| `ogc000557` | Athanasius | Quaestiones In Scripturam Sacram [Sp.] | `tlg2035.tlg080` | 7,128 | PD |
| `ogc000558` | Athanasius | Refutatio Hypocriseos Meletii Et Eusebii [Sp.] | `tlg2035.tlg066` | 604 | PD |
| `ogc000559` | Athanasius | Scholia In Acta (Fort. Ex Libris Contra Novatianos) | `tlg2035.tlg057` | 520 | PD |
| `ogc000560` | Athanasius | Sermo Ad Antiochum Ducem [Sp.] | `tlg2035.tlg076` | 1,682 | PD |
| `ogc000561` | Athanasius | Sermo Contra Latinos [Sp.] | `tlg2035.tlg083` | 2,853 | PD |
| `ogc000562` | Athanasius | Sermo Contra Omnes Haereses [Sp.] | `tlg2035.tlg073` | 5,185 | PD |
| `ogc000563` | Athanasius | Sermo De Descriptione Deiparae [Sp.] | `tlg2035.tlg088` | 2,641 | PD |
| `ogc000564` | Athanasius | Sermo De Patientia [Sp.] | `tlg2035.tlg056` | 3,078 | PD |
| `ogc000565` | Athanasius | Sermo Exhortatorius [Sp.] (E Cod. Paris. Gr. 769) | `tlg2035.tlg038` | 1,290 | PD |
| `ogc000566` | Athanasius | Sermo In Annuntiationem Deiparae [Sp.] | `tlg2035.tlg087` | 4,105 | PD |
| `ogc000567` | Athanasius | Sermo In Nativitatem Christi [Sp.] | `tlg2035.tlg089` | 2,627 | PD |
| `ogc000568` | Athanasius | Sermo Pro Iis Qui Saeculo Renuntiarunt [Sp.] | `tlg2035.tlg101` | 1,836 | PD |
| `ogc000569` | Athanasius | Symbolum "Quicumque" [Sp.] | `tlg2035.tlg106` | 2,921 | PD |
| `ogc000570` | Athanasius | Synopsis Scripturae Sacrae [Sp.] | `tlg2035.tlg071` | 30,194 | PD |
| `ogc000571` | Athanasius | Syntagma Ad Monachos (E Cod. Vossiano Gr., Fol. 46) [Sp.] | `tlg2035.tlg118` | 1,633 | PD |
| `ogc000572` | Athanasius | Syntagma Ad Quendam Politicum [Sp.] | `tlg2035.tlg100` | 2,903 | PD |
| `ogc000573` | Athanasius | Testimonia E Scriptura (De Communi Essentia Patris Et Filii Et Spiritus Sancti) [Sp.] | `tlg2035.tlg064` | 9,702 | PD |
| `ogc000574` | Athanasius | Vita Antonii | `tlg2035.tlg047` | 17,358 | PD |
| `ogc000575` | Athanasius | Vita Sanctae Syncleticae [Sp.] | `tlg2035.tlg104` | 12,749 | PD |
| `ogc000576` | Athanasius | Vitae Monasticae Institutio [Sp.] | `tlg2035.tlg084` | 726 | PD |
| `ogc000495` | athanasius-of-alexandria | Apologia ad Constantium | `tlg2035.tlg134` | 8,465 | CC-BY-SA-4.0 |
| `ogc000496` | athanasius-of-alexandria | Epistula ad Afros | `tlg2035.tlg138` | 3,489 | CC-BY-SA-4.0 |
| `ogc000497` | athanasius-of-alexandria | Epistula ad Dracontium | `tlg2035.tlg137` | 1,880 | CC-BY-SA-4.0 |
| `ogc000498` | athanasius-of-alexandria | Epistula ad Ioannem et Antiochum | `tlg2035.tlg135` | 183 | CC-BY-SA-4.0 |
| `ogc000499` | athanasius-of-alexandria | Epistula ad Jovianum | `tlg2035.tlg140` | 816 | CC-BY-SA-4.0 |
| `ogc000500` | athanasius-of-alexandria | Epistula ad Palladium | `tlg2035.tlg136` | 245 | CC-BY-SA-4.0 |
| `ogc000501` | athanasius-of-alexandria | Petitiones Arianorum | `tlg2035.tlg141` | 708 | CC-BY-SA-4.0 |
| `ogc000502` | athanasius-of-alexandria | Tomus ad Antiochenos | `tlg2035.tlg139` | 2,234 | CC-BY-SA-4.0 |
| `ogc000580` | Athenagoras | De Resurrectione | `tlg1205.tlg002` | 8,915 | CC-BY-SA-4.0 |
| `ogc000581` | Athenagoras | Legatio Sive Supplicatio Pro Christianis | `tlg1205.tlg001` | 11,308 | CC-BY-SA-4.0 |
| `ogc000605` | Basilius | Adversus Eunomium (Libri 5) | `tlg2040.tlg019` | 43,363 | PD |
| `ogc000606` | Basilius | Asceticon Magnum Sive Quaestiones (Regulae Brevius Tractatae) | `tlg2040.tlg050` | 33,798 | PD |
| `ogc000607` | Basilius | Asceticon Magnum Sive Quaestiones (Regulae Fusius Tractatae) | `tlg2040.tlg048` | 27,219 | PD |
| `ogc000608` | Basilius | Consolatoria Ad Aegrotum [Sp.] (Sub Auctore Proclo) | `tlg2040.tlg068` | 4,800 | PD |
| `ogc000609` | Basilius | Constitutiones Asceticae [Sp.] | `tlg2040.tlg074` | 17,870 | PD |
| `ogc000610` | Basilius | Contra Sabellianos Et Arium Et Anomoeos | `tlg2040.tlg039` | 2,681 | PD |
| `ogc000611` | Basilius | De Baptismo Libri Duo | `tlg2040.tlg052` | 19,636 | PD |
| `ogc000612` | Basilius | De Fide | `tlg2040.tlg031` | 1,017 | PD |
| `ogc000613` | Basilius | De Humilitate | `tlg2040.tlg036` | 2,097 | PD |
| `ogc000614` | Basilius | De Jejunio (Homilia 1) | `tlg2040.tlg020` | 2,866 | PD |
| `ogc000615` | Basilius | De Jejunio (Homilia 2) | `tlg2040.tlg021` | 12,460 | PD |
| `ogc000616` | Basilius | De Jejunio (Homilia 3) [Sp.] | `tlg2040.tlg063` | 1,049 | PD |
| `ogc000617` | Basilius | De Legendis Gentilium Libris | `tlg2040.tlg002` | 4,685 | CC-BY-SA-4.0 |
| `ogc000618` | Basilius | De Spiritu Sancto | `tlg2040.tlg003` | 23,765 | PD |
| `ogc000603` | Basilius | De Vita Et Miraculis Sanctae Theclae Libri Ii [Sp.] | `tlg2800.tlg018` | 28,432 | PD |
| `ogc000619` | Basilius | Enarratio In Prophetam Isaiam [Dub.] | `tlg2040.tlg009` | 91,460 | PD |
| `ogc000620` | Basilius | Epistulae | `tlg2040.tlg004` | 133,871 | CC-BY-SA-4.0 |
| `ogc000621` | Basilius | Epitimia In Canonicas (Epitimia 25) [Dub.] | `tlg2040.tlg066` | 814 | PD |
| `ogc000622` | Basilius | Homilia Adversus Eos Qui Irascuntur | `tlg2040.tlg026` | 3,221 | PD |
| `ogc000623` | Basilius | Homilia De Invidia | `tlg2040.tlg027` | 2,581 | PD |
| `ogc000624` | Basilius | Homilia De Misericordia Et Judicio [Sp.] | `tlg2040.tlg069` | 1,043 | PD |
| `ogc000625` | Basilius | Homilia De Spiritu Sancto [Sp.] | `tlg2040.tlg057` | 1,534 | PD |
| `ogc000626` | Basilius | Homilia Dicta In Lacisis | `tlg2040.tlg058` | 3,185 | PD |
| `ogc000627` | Basilius | Homilia Dicta Tempore Famis Et Siccitatis | `tlg2040.tlg024` | 4,164 | PD |
| `ogc000628` | Basilius | Homilia Exhortatoria Ad Sanctum Baptisma | `tlg2040.tlg029` | 2,426 | PD |
| `ogc000629` | Basilius | Homilia In Divites | `tlg2040.tlg008` | 4,383 | PD |
| `ogc000630` | Basilius | Homilia In Illud: Destruam Horrea Mea | `tlg2040.tlg007` | 2,594 | PD |
| `ogc000631` | Basilius | Homilia In Illud: Ne Dederis Somnum Oculis Tuis [Sp.] | `tlg2040.tlg062` | 1,560 | PD |
| `ogc000632` | Basilius | Homilia In Principium Proverbiorum | `tlg2040.tlg028` | 6,994 | PD |
| `ogc000633` | Basilius | Homilia In Psalmum 37 [Sp.] | `tlg2040.tlg054` | 6,380 | PD |
| `ogc000634` | Basilius | Homiliae In Hexaemeron | `tlg2040.tlg001` | 33,670 | PD |
| `ogc000635` | Basilius | Homiliae Super Psalmos | `tlg2040.tlg018` | 49,935 | PD |
| `ogc000636` | Basilius | In Barlaam Martyrem [Sp.] | `tlg2040.tlg033` | 670 | PD |
| `ogc000637` | Basilius | In Ebriosos | `tlg2040.tlg030` | 3,427 | PD |
| `ogc000638` | Basilius | In Gordium Martyrem | `tlg2040.tlg034` | 3,483 | PD |
| `ogc000639` | Basilius | In Illud: In Principio Erat Verbum | `tlg2040.tlg032` | 2,277 | PD |
| `ogc000640` | Basilius | In Mamantem Martyrem | `tlg2040.tlg038` | 1,698 | PD |
| `ogc000641` | Basilius | In Quadraginta Martyres Sebastenses | `tlg2040.tlg035` | 2,160 | PD |
| `ogc000642` | Basilius | In Sanctam Christi Generationem | `tlg2040.tlg059` | 5,806 | PD |
| `ogc000643` | Basilius | Liturgia (Recensio Brevior Vetusta) | `tlg2040.tlg071` | 4,761 | PD |
| `ogc000644` | Basilius | Orationes Sive Exorcismi [Sp.] | `tlg2040.tlg064` | 1,318 | PD |
| `ogc002586` | Basilius | Patrologia Graeca 31 (unsplit pages) |  | 592 | PD |
| `ogc000645` | Basilius | Poenae In Monachos Delinquentes (Epitimia 24) [Dub.] | `tlg2040.tlg065` | 268 | PD |
| `ogc000646` | Basilius | Prologus 3 (Prooemium In Regulas Brevius Tractatas) | `tlg2040.tlg049` | 588 | PD |
| `ogc000647` | Basilius | Prologus 4 (Prooemium In Asceticum Magnum) | `tlg2040.tlg047` | 1,941 | PD |
| `ogc000648` | Basilius | Prologus 5 (Sermo Asceticus) [Dub.] | `tlg2040.tlg046` | 2,259 | PD |
| `ogc000649` | Basilius | Prologus 7 (De Judicio Dei) | `tlg2040.tlg043` | 3,190 | PD |
| `ogc000650` | Basilius | Prologus 8 (De Fide) | `tlg2040.tlg045` | 3,867 | PD |
| `ogc000651` | Basilius | Quod Deus Non Est Auctor Malorum | `tlg2040.tlg025` | 3,805 | PD |
| `ogc000652` | Basilius | Quod Rebus Mundanis Adhaerendum Non Sit | `tlg2040.tlg037` | 3,946 | PD |
| `ogc000653` | Basilius | Regulae Morales | `tlg2040.tlg051` | 26,701 | PD |
| `ogc000654` | Basilius | Sermo 10 (Praevia Institutio Ascetica) [Dub.] | `tlg2040.tlg040` | 848 | PD |
| `ogc000655` | Basilius | Sermo 11 (Sermo Asceticus Et Exhortatio De Renuntiatione Mundi) [Dub.] | `tlg2040.tlg041` | 9,710 | PD |
| `ogc000656` | Basilius | Sermo Ob Sacerdotum Instructionem (Recensio Brevior) [Sp.] | `tlg2040.tlg070` | 598 | PD |
| `ogc000657` | Basilius | Sermones De Moribus A Symeone Metaphrasta Collecti | `tlg2040.tlg075` | 47,923 | PD |
| `ogc000604` | Basilius | Sermones Xli | `tlg2800.tlg002` | 67,488 | PD |
| `ogc003682` | Claudius Apollinarius | Fragmenta | `tlg1163.tlg001` | 346 | CC-BY-4.0 |
| `ogc000796` | Clemens Alexandrinus | Eclogae Propheticae | `tlg0555.tlg005` | 4,978 | CC-BY-SA-4.0 |
| `ogc000797` | Clemens Alexandrinus | Excerpta Ex Theodoto | `tlg0555.tlg007` | 7,533 | CC-BY-SA-4.0 |
| `ogc000798` | Clemens Alexandrinus | Fragmenta | `tlg0555.tlg008` | 678 | CC-BY-SA-4.0 |
| `ogc000799` | Clemens Alexandrinus | Paedagogus | `tlg0555.tlg002` | 56,945 | CC-BY-SA-4.0 |
| `ogc000800` | Clemens Alexandrinus | Protrepticus | `tlg0555.tlg001` | 23,338 | CC-BY-SA-4.0 |
| `ogc000801` | Clemens Alexandrinus | Quis Dives Salvetur | `tlg0555.tlg006` | 9,189 | CC-BY-SA-4.0 |
| `ogc000802` | Clemens Alexandrinus | Stromata | `tlg0555.tlg004` | 161,892 | CC-BY-SA-4.0 |
| `ogc000803` | Clemens Romanus Et Clementina | Contestatio [Sp.] | `tlg1271.tlg004` | 660 | CC-BY-SA-4.0 |
| `ogc000804` | Clemens Romanus Et Clementina | Epistula Clementis Ad Jacobum [Sp.] | `tlg1271.tlg005` | 2,474 | CC-BY-SA-4.0 |
| `ogc000805` | Clemens Romanus Et Clementina | Epistula I Ad Corinthios | `tlg1271.tlg001` | 9,830 | CC-BY-SA-4.0 |
| `ogc000806` | Clemens Romanus Et Clementina | Epistula Ii Ad Corinthios [Sp.] | `tlg1271.tlg002` | 3,013 | CC-BY-SA-4.0 |
| `ogc000807` | Clemens Romanus Et Clementina | Epistula Petri Ad Jacobum [Sp.] | `tlg1271.tlg003` | 470 | CC-BY-SA-4.0 |
| `ogc000808` | Clemens Romanus Et Clementina | Epistulae De Virginitate [Sp.] | `tlg1271.tlg010` | 2,050 | CC-BY-SA-4.0 |
| `ogc000809` | Clemens Romanus Et Clementina | Homiliae [Sp.] | `tlg1271.tlg006` | 64,045 | CC-BY-SA-4.0 |
| `ogc000810` | Clemens Romanus Et Clementina | Pseudo-Clementina (Epitome Altera Auctore Symeone Metaphrasta) [Sp.] | `tlg1271.tlg011` | 25,239 | CC-BY-SA-4.0 |
| `ogc000811` | Clemens Romanus Et Clementina | Pseudo-Clementina (Epitome De Gestis Petri Praemetaphrastica) [Sp.] | `tlg1271.tlg012` | 25,961 | CC-BY-SA-4.0 |
| `ogc001084` | Didache XII Apostolorum | Διδαχαὶ τῶν ἀποστολῶν | `tlg1311.tlg001` | 2,191 | CC-BY-SA-4.0 |
| `ogc001154` | Dionysius | Fragmenta | `tlg1329.tlg001` | 546 | CC-BY-SA-4.0 |
| `ogc001174` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 10: Fragmente eines Briefes des Eusebius von Caesarea an Euphration von Balaneae |  | 373 | CC-BY-4.0 |
| `ogc001173` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 1: Theologische Erklärung alexandrinischer Kleriker an Alexander von Alexandrien |  | 439 | CC-BY-4.0 |
| `ogc001175` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 2: Briefe des Alexander von Alexandrien |  | 1,581 | CC-BY-4.0 |
| `ogc001176` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 3: Regest eines Rundbriefes einer Synode in Bithynien |  | 23 | CC-BY-4.0 |
| `ogc001177` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 4: Brief des Eusebius von Nikomedien an Paulinus von Tyrus |  | 487 | CC-BY-4.0 |
| `ogc001178` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 5: Referate eines |  | 169 | CC-BY-4.0 |
| `ogc001179` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 6: Fragment eines Briefes des Presbyters Georgius an Alexander von Alexandrien |  | 65 | CC-BY-4.0 |
| `ogc001180` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 7: Fragment eines Briefes des Presbyters Georgius an die »Arianer« in Alexandrien |  | 76 | CC-BY-4.0 |
| `ogc001181` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 8: Regeste eines Briefes |  | 112 | CC-BY-4.0 |
| `ogc001182` | dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii | Dok. 9: Fragment eines Briefes des Eusebius von Caesarea an Alexander von Alexandrien |  | 308 | CC-BY-4.0 |
| `ogc001227` | Epiphanius | Anacephalaeosis [Sp.] | `tlg2021.tlg003` | 3,333 | CC-BY-SA-4.0 |
| `ogc001228` | Epiphanius | Ancoratus | `tlg2021.tlg001` | 39,150 | CC-BY-SA-4.0 |
| `ogc001229` | Epiphanius | Panarion (= Adversus Haereses) | `tlg2021.tlg002` | 190,141 | CC-BY-SA-4.0 |
| `ogc003686` | Epistula Ecclesiarum Apud Lugdunum Et Viennam | Epistula Ecclesiarum Apud Lugdunum Et Viennam | `tlg1352.tlg001` | 3,668 | CC-BY-4.0 |
| `ogc001304` | Eusebius | Antiquorum Martyriorum Collectio (Fragmenta) | `tlg2018.tlg025` | 4,698 | PD |
| `ogc001305` | Eusebius | Commentaria In Psalmos | `tlg2018.tlg034` | 332,561 | CC-BY-SA-4.0 |
| `ogc001306` | Eusebius | Commentarius In Isaiam | `tlg2018.tlg019` | 158,793 | CC-BY-SA-4.0 |
| `ogc001307` | Eusebius | Constantini Imperatoris Oratio Ad Coetum Sanctorum | `tlg2018.tlg021` | 11,590 | CC-BY-SA-4.0 |
| `ogc001308` | Eusebius | Contra Marcellum | `tlg2018.tlg007` | 17,858 | CC-BY-SA-4.0 |
| `ogc001309` | Eusebius | De Ecclesiastica Theologia | `tlg2018.tlg009` | 41,496 | CC-BY-SA-4.0 |
| `ogc001310` | Eusebius | De Laudibus Constantini | `tlg2018.tlg022` | 19,439 | CC-BY-SA-4.0 |
| `ogc001311` | Eusebius | De Martyribus Palaestinae (Recensio Brevior) | `tlg2018.tlg003` | 7,855 | CC-BY-SA-4.0 |
| `ogc001312` | Eusebius | De Solemnitate Paschali | `tlg2018.tlg039` | 1,629 | PD |
| `ogc001313` | Eusebius | De Theophania (Fragmenta) | `tlg2018.tlg010` | 8,131 | CC-BY-SA-4.0 |
| `ogc001314` | Eusebius | De Vitis Prophetarum (Fragmenta) | `tlg2018.tlg033` | 1,496 | PD |
| `ogc001315` | Eusebius | Demonstratio Evangelica | `tlg2018.tlg005` | 155,917 | CC-BY-SA-4.0 |
| `ogc001316` | Eusebius | Epistula Ad Carpianum Ad Canones Evangeliorum Praemissa | `tlg2018.tlg013` | 1,084 | PD |
| `ogc001317` | Eusebius | Epistula Ad Flacillum | `tlg2018.tlg008` | 174 | CC-BY-SA-4.0 |
| `ogc001303` | Eusebius | Fragmenta | `tlg2640.tlg001` | 3,077 | CC-BY-SA-4.0 |
| `ogc001327` | eusebius | Fragmenta |  | 88 | CC-BY-SA-4.0 |
| `ogc001328` | eusebius | Fragmenta |  | 541 | CC-BY-SA-4.0 |
| `ogc001318` | Eusebius | Fragmenta In Lucam | `tlg2018.tlg037` | 15,432 | PD |
| `ogc001319` | Eusebius | Generalis Elementaria Introductio (= Eclogae Propheticae) | `tlg2018.tlg023` | 51,290 | CC-BY-SA-4.0 |
| `ogc001320` | Eusebius | Historia Ecclesiastica | `tlg2018.tlg002` | 100,551 | CC-BY-SA-4.0 |
| `ogc001321` | Eusebius | Onomasticon | `tlg2018.tlg011` | 14,389 | CC-BY-SA-4.0 |
| `ogc001322` | Eusebius | Praeparatio Evangelica | `tlg2018.tlg001` | 229,242 | CC-BY-SA-4.0 |
| `ogc001323` | Eusebius | Quaestiones Evangelicae Ad Marinum | `tlg2018.tlg029` | 4,142 | PD |
| `ogc001324` | Eusebius | Quaestiones Evangelicae Ad Stephanum | `tlg2018.tlg028` | 10,796 | PD |
| `ogc001325` | Eusebius | Supplementa Ad Quaestiones Ad Marinum | `tlg2018.tlg031` | 10,492 | PD |
| `ogc001326` | Eusebius | Vita Constantini | `tlg2018.tlg020` | 38,512 | CC-BY-SA-4.0 |
| `ogc001300` | eusebius-alexandrinus | De die dominica |  | 1,707 | CC-BY-4.0 |
| `ogc001301` | eusebius-of-caesarea | Hypomnema de Psalmis |  | 3,345 | CC-BY-SA-4.0 |
| `ogc001302` | eusebius-of-caesarea | Prologi varii |  | 1,800 | CC-BY-SA-4.0 |
| `ogc003688` | Fragmentum Synodicae Epistulae Concilii Caesariensis | Fragmentum Epistulae | `tlg1381.tlg001` | 54 | CC-BY-4.0 |
| `ogc001552` | Gregorius Nazianzenus | Ad Eos Qui Ipsum Acciverant Nec Occurrerant (Orat. 3) | `tlg2022.tlg017` | 785 | PD |
| `ogc001553` | Gregorius Nazianzenus | Ad Gregorium Nyssenum (Orat. 11) | `tlg2022.tlg024` | 1,542 | PD |
| `ogc001554` | Gregorius Nazianzenus | Ad Julianum Tributorum Exaequatorem (Orat. 19) | `tlg2022.tlg032` | 2,992 | PD |
| `ogc001555` | Gregorius Nazianzenus | Ad Patrem (Orat. 12) | `tlg2022.tlg025` | 1,198 | PD |
| `ogc001556` | Gregorius Nazianzenus | Adversus Eunomianos (Orat. 27) | `tlg2022.tlg007` | 2,060 | CC-BY-SA-4.0 |
| `ogc001557` | Gregorius Nazianzenus | Apologetica (Orat. 2) | `tlg2022.tlg016` | 13,634 | PD |
| `ogc001558` | Gregorius Nazianzenus | Apologeticus Ad Patrem (Orat. 9) | `tlg2022.tlg022` | 1,207 | PD |
| `ogc001559` | Gregorius Nazianzenus | Carmina De Se Ipso | `tlg2022.tlg061` | 43,523 | PD |
| `ogc001560` | Gregorius Nazianzenus | Carmina Dogmatica | `tlg2022.tlg059` | 51,967 | PD |
| `ogc001561` | Gregorius Nazianzenus | Carmina Moralia | `tlg2022.tlg060` | 144 | CC-BY-SA-4.0 |
| `ogc001562` | Gregorius Nazianzenus | Carmina Quae Spectant Ad Alios | `tlg2022.tlg062` | 14,109 | PD |
| `ogc001563` | Gregorius Nazianzenus | Christus Patiens [Dub.] (Fort. Auctore Constantino Manasse) | `tlg2022.tlg003` | 15,696 | CC-BY-SA-4.0 |
| `ogc001564` | Gregorius Nazianzenus | Contra Arianos Et De Seipso (Orat. 33) | `tlg2022.tlg041` | 3,177 | PD |
| `ogc001565` | Gregorius Nazianzenus | Contra Julianum Imperatorem 1 (Orat. 4) | `tlg2022.tlg018` | 25,381 | PD |
| `ogc001566` | Gregorius Nazianzenus | De Dogmate Et Constitutione Episcoporum (Orat. 20) | `tlg2022.tlg033` | 1,474 | PD |
| `ogc001567` | Gregorius Nazianzenus | De Filio (Orat. 29) | `tlg2022.tlg009` | 4,823 | CC-BY-SA-4.0 |
| `ogc001568` | Gregorius Nazianzenus | De Filio (Orat. 30) | `tlg2022.tlg010` | 4,872 | CC-BY-SA-4.0 |
| `ogc001569` | Gregorius Nazianzenus | De Martyribus Et Adversus Arianos (Orat. 35) [Sp.] | `tlg2022.tlg043` | 1,043 | PD |
| `ogc001570` | Gregorius Nazianzenus | De Moderatione In Disputando (Orat. 32) | `tlg2022.tlg040` | 5,899 | PD |
| `ogc001571` | Gregorius Nazianzenus | De Pace 1 (Orat. 6) | `tlg2022.tlg020` | 4,473 | PD |
| `ogc001572` | Gregorius Nazianzenus | De Pauperum Amore (Orat. 14) | `tlg2022.tlg027` | 8,221 | PD |
| `ogc001573` | Gregorius Nazianzenus | De Seipso Et Ad Eos Qui Ipsum Cathedram Constantinopolitanam Affectare Dicebant (Orat. 36) | `tlg2022.tlg044` | 2,403 | PD |
| `ogc001574` | Gregorius Nazianzenus | De Spiritu Sancto (Orat. 31) | `tlg2022.tlg011` | 6,147 | CC-BY-SA-4.0 |
| `ogc001575` | Gregorius Nazianzenus | De Theologia (Orat. 28) | `tlg2022.tlg008` | 7,336 | CC-BY-SA-4.0 |
| `ogc001576` | Gregorius Nazianzenus | Epistulae | `tlg2022.tlg001` | 39,912 | PD |
| `ogc001577` | Gregorius Nazianzenus | Epistulae Theologicae | `tlg2022.tlg002` | 17,040 | PD |
| `ogc001578` | Gregorius Nazianzenus | Fragmentum Ex Oratione Contra Astronomos [Sp.] | `tlg2022.tlg054` | 883 | PD |
| `ogc001579` | Gregorius Nazianzenus | Funebris In Laudem Caesarii Fratris Oratio (Orat. 7) | `tlg2022.tlg005` | 4,608 | PD |
| `ogc001580` | Gregorius Nazianzenus | Funebris Oratio In Laudem Basilii Magni Caesareae In Cappadocia Episcopi (Orat. 43) | `tlg2022.tlg006` | 17,189 | PD |
| `ogc001581` | Gregorius Nazianzenus | Funebris Oratio In Patrem (Orat. 18) | `tlg2022.tlg031` | 8,324 | PD |
| `ogc001582` | Gregorius Nazianzenus | In Aegyptiorum Adventum (Orat. 34) | `tlg2022.tlg042` | 1,709 | PD |
| `ogc001583` | Gregorius Nazianzenus | In Consecratione Eulalii Doarensium Episcopi (Orat. 13) | `tlg2022.tlg026` | 332 | PD |
| `ogc001584` | Gregorius Nazianzenus | In Dictum Evangelii: Cum Consummasset Jesus Hos Sermones (Orat. 37) | `tlg2022.tlg045` | 4,112 | PD |
| `ogc001585` | Gregorius Nazianzenus | In Laudem Athanasii (Orat. 21) | `tlg2022.tlg034` | 15,351 | PD |
| `ogc001586` | Gregorius Nazianzenus | In Laudem Heronis Philosophi (Orat. 25) | `tlg2022.tlg038` | 4,086 | PD |
| `ogc001587` | Gregorius Nazianzenus | In Laudem Sororis Gorgoniae (Orat. 8) | `tlg2022.tlg021` | 4,365 | PD |
| `ogc001588` | Gregorius Nazianzenus | In Machabaeorum Laudem (Orat. 15) | `tlg2022.tlg028` | 2,833 | PD |
| `ogc001589` | Gregorius Nazianzenus | In Novam Dominicam (Orat. 44) | `tlg2022.tlg051` | 2,177 | PD |
| `ogc001590` | Gregorius Nazianzenus | In Patrem Tacentem (Orat. 16) | `tlg2022.tlg029` | 7,364 | PD |
| `ogc001591` | Gregorius Nazianzenus | In Sancta Lumina (Orat. 39) | `tlg2022.tlg047` | 4,102 | PD |
| `ogc001592` | Gregorius Nazianzenus | In Sanctum Baptisma (Orat. 40) | `tlg2022.tlg048` | 13,429 | PD |
| `ogc001594` | Gregorius Nazianzenus | In Sanctum Pascha (Orat. 45) | `tlg2022.tlg052` | 4,560 | PD |
| `ogc001593` | Gregorius Nazianzenus | In Sanctum Pascha Et In Tarditatem (Orat. 1) | `tlg2022.tlg015` | 882 | PD |
| `ogc001595` | Gregorius Nazianzenus | In Seipsum Ad Patrem Et Basilium Magnum (Orat. 10) | `tlg2022.tlg023` | 662 | PD |
| `ogc001596` | Gregorius Nazianzenus | In Seipsum, Cum Rure Rediisset, Post Ea Quae A Maximo Perpetrata Fuerant (Orat. 26) | `tlg2022.tlg039` | 3,896 | PD |
| `ogc001597` | Gregorius Nazianzenus | In Theophania (Orat. 38) | `tlg2022.tlg046` | 3,425 | PD |
| `ogc001598` | Gregorius Nazianzenus | Liturgia Sancti Gregorii [Sp.] | `tlg2022.tlg055` | 6,674 | PD |
| `ogc002587` | Gregorius Nazianzenus | Patrologia Graeca 36 (unsplit pages) |  | 82,275 | PD |
| `ogc001599` | Gregorius Nazianzenus | Significatio In Ezechielem [Sp.] | `tlg2022.tlg053` | 521 | PD |
| `ogc001600` | Gregorius Nazianzenus | Supremum Vale (Orat. 42) | `tlg2022.tlg050` | 4,831 | PD |
| `ogc001601` | Gregorius Nazianzenus | Testamentum | `tlg2022.tlg058` | 1,014 | PD |
| `ogc001602` | Gregorius Nyssenus | Ad Ablabium Quod Non Sint Tres Dei | `tlg2017.tlg003` | 5,131 | PD |
| `ogc001603` | Gregorius Nyssenus | Ad Graecos Ex Communibus Notionibus | `tlg2017.tlg002` | 2,123 | PD |
| `ogc001604` | Gregorius Nyssenus | Ad Imaginem Dei Et Ad Similitudinem [Sp.] | `tlg2017.tlg055` | 8,252 | PD |
| `ogc001605` | Gregorius Nyssenus | Ad Theophilum Adversus Apollinaristas | `tlg2017.tlg007` | 1,689 | PD |
| `ogc001606` | Gregorius Nyssenus | Adversus Arium Et Sabellium De Patre Et Filio | `tlg2017.tlg005` | 3,432 | PD |
| `ogc001607` | Gregorius Nyssenus | Adversus Eos Qui Castigationes Aegre Ferunt | `tlg2017.tlg059` | 1,137 | PD |
| `ogc001608` | Gregorius Nyssenus | Adversus Macedonianos De Spiritu Sancto | `tlg2017.tlg006` | 8,007 | PD |
| `ogc001609` | Gregorius Nyssenus | Antirrheticus Adversus Apollinarium | `tlg2017.tlg008` | 25,023 | PD |
| `ogc001610` | Gregorius Nyssenus | Apologia In Hexaemeron | `tlg2017.tlg078` | 14,190 | PD |
| `ogc001611` | Gregorius Nyssenus | Contra Eunomium | `tlg2017.tlg030` | 178,664 | PD |
| `ogc001612` | Gregorius Nyssenus | Contra Fatum | `tlg2017.tlg082` | 6,711 | PD |
| `ogc001613` | Gregorius Nyssenus | Contra Fornicarios | `tlg2017.tlg013` | 918 | PD |
| `ogc001614` | Gregorius Nyssenus | Contra Usurarios | `tlg2017.tlg012` | 2,712 | PD |
| `ogc001615` | Gregorius Nyssenus | De Anima [Sp.] | `tlg2017.tlgX02` | 6,730 | PD |
| `ogc001616` | Gregorius Nyssenus | De Beneficentia (Vulgo De Pauperibus Amandis I) | `tlg2017.tlg010` | 2,724 | PD |
| `ogc001617` | Gregorius Nyssenus | De Creatione Hominis Sermo Alter [Sp.] | `tlg2017.tlg035` | 4,294 | PD |
| `ogc001618` | Gregorius Nyssenus | De Creatione Hominis Sermo Primus [Sp.] | `tlg2017.tlg034` | 3,698 | PD |
| `ogc001619` | Gregorius Nyssenus | De Deitate Adversus Evagrium (Vulgo In Suam Ordinationem) | `tlg2017.tlg020` | 1,863 | PD |
| `ogc001620` | Gregorius Nyssenus | De Deitate Filii Et Spiritus Sancti | `tlg2017.tlg062` | 14,744 | PD |
| `ogc001621` | Gregorius Nyssenus | De Infantibus Praemature Abreptis | `tlg2017.tlg083` | 5,740 | PD |
| `ogc001622` | Gregorius Nyssenus | De Instituto Christiano | `tlg2017.tlg024` | 3,682 | PD |
| `ogc001623` | Gregorius Nyssenus | De Mortuis Non Esse Dolendum | `tlg2017.tlg009` | 9,028 | PD |
| `ogc001624` | Gregorius Nyssenus | De Occursu Domini [Sp.] | `tlg2017.tlg073` | 8,443 | PD |
| `ogc001625` | Gregorius Nyssenus | De Opificio Hominis | `tlg2017.tlg079` | 23,801 | PD |
| `ogc001626` | Gregorius Nyssenus | De Oratione Dominica Orationes V | `tlg2017.tlg047` | 14,096 | PD |
| `ogc001627` | Gregorius Nyssenus | De Perfectione Christiana Ad Olympium Monachum | `tlg2017.tlg026` | 7,079 | PD |
| `ogc001628` | Gregorius Nyssenus | De Professione Christiana Ad Harmonium | `tlg2017.tlg025` | 2,120 | PD |
| `ogc001629` | Gregorius Nyssenus | De Pythonissa Ad Theodosium Episcopum | `tlg2017.tlg084` | 672 | PD |
| `ogc001630` | Gregorius Nyssenus | De Sancto Theodoro | `tlg2017.tlg065` | 2,212 | PD |
| `ogc001631` | Gregorius Nyssenus | De Spiritu Sancto Sive In Pentecosten | `tlg2017.tlg063` | 1,061 | PD |
| `ogc001632` | Gregorius Nyssenus | De Virginitate | `tlg2017.tlg043` | 22,318 | PD |
| `ogc001633` | Gregorius Nyssenus | De Vita Gregorii Thaumaturgi | `tlg2017.tlg069` | 13,024 | PD |
| `ogc001634` | Gregorius Nyssenus | De Vita Mosis | `tlg2017.tlg042` | 28,111 | PD |
| `ogc001635` | Gregorius Nyssenus | Decem Syllogismi Contra Manichaeos [Sp.] | `tlg2017.tlg061` | 229 | PD |
| `ogc001636` | Gregorius Nyssenus | Dialogus De Anima Et Resurrectione | `tlg2017.tlg056` | 24,845 | PD |
| `ogc001637` | Gregorius Nyssenus | Encomium In Sanctum Stephanum Protomartyrem I | `tlg2017.tlg040` | 6,030 | PD |
| `ogc001638` | Gregorius Nyssenus | Encomium In Xl Martyres I | `tlg2017.tlg066` | 4,611 | PD |
| `ogc001639` | Gregorius Nyssenus | Encomium In Xl Martyres Ii | `tlg2017.tlg067` | 2,691 | PD |
| `ogc001640` | Gregorius Nyssenus | Epistula Canonica Ad Letoium | `tlg2017.tlg076` | 3,070 | PD |
| `ogc001641` | Gregorius Nyssenus | Epistulae | `tlg2017.tlg033` | 11,181 | PD |
| `ogc001642` | Gregorius Nyssenus | In Ascensionem Christi | `tlg2017.tlg019` | 1,028 | PD |
| `ogc001643` | Gregorius Nyssenus | In Basilium Fratrem | `tlg2017.tlg048` | 6,111 | PD |
| `ogc001644` | Gregorius Nyssenus | In Canticum Canticorum (Homiliae 15) | `tlg2017.tlg032` | 75,184 | PD |
| `ogc001645` | Gregorius Nyssenus | In Ecclesiasten (Homiliae 8) | `tlg2017.tlg029` | 29,424 | PD |
| `ogc001646` | Gregorius Nyssenus | In Illud: Quatenus Uni Ex His Fecistis Mihi Fecistis (Vulgo De Pauperibus Amandis Ii) | `tlg2017.tlg011` | 3,550 | PD |
| `ogc001647` | Gregorius Nyssenus | In Illud: Tunc Et Ipse Filius | `tlg2017.tlg081` | 4,800 | PD |
| `ogc001648` | Gregorius Nyssenus | In Inscriptiones Psalmorum | `tlg2017.tlg027` | 36,095 | PD |
| `ogc001649` | Gregorius Nyssenus | In Luciferam Sanctam Domini Resurrectionem (Vulgo In Christi Resurrectionem Oratio V) [Sp.] | `tlg2017.tlg018` | 1,229 | PD |
| `ogc001650` | Gregorius Nyssenus | In Sanctum Ephraim | `tlg2017.tlg068` | 5,458 | PD |
| `ogc001651` | Gregorius Nyssenus | In Sanctum Et Salutare Pascha (Vulgo In Christi Resurrectionem Oratio Iv) | `tlg2017.tlg017` | 389 | PD |
| `ogc001652` | Gregorius Nyssenus | In Sanctum Pascha (Vulgo In Christi Resurrectionem Oratio Iii) | `tlg2017.tlg015` | 10,794 | PD |
| `ogc001653` | Gregorius Nyssenus | Oratio Catechetica Magna | `tlg2017.tlg046` | 20,638 | PD |
| `ogc001654` | Gregorius Nyssenus | Oratio Consolatoria In Pulcheriam | `tlg2017.tlg022` | 2,800 | PD |
| `ogc001655` | Gregorius Nyssenus | Oratio Funebris In Flacillam Imperatricem | `tlg2017.tlg023` | 2,868 | PD |
| `ogc001656` | Gregorius Nyssenus | Oratio Funebris In Meletium Episcopum | `tlg2017.tlg021` | 2,344 | PD |
| `ogc001657` | Gregorius Nyssenus | Oratio In Diem Natalem Christi | `tlg2017.tlg049` | 4,809 | PD |
| `ogc001658` | Gregorius Nyssenus | Orationes Viii De Beatitudinibus | `tlg2017.tlg053` | 21,630 | PD |
| `ogc001659` | Gregorius Nyssenus | Testimonia Adversus Judaeos [Sp.] | `tlg2017.tlg058` | 6,087 | PD |
| `ogc001660` | Gregorius Nyssenus | Vita Sanctae Macrinae | `tlg2017.tlg041` | 14,592 | PD |
| `ogc001676` | hegesippus | Fragmenta | `tlg0464.tlg001` | 164 | PD |
| `ogc003690` | Hegesippus | Fragmenta (Ex Incerto Libro) | `tlg1398.tlg001` | 1,511 | CC-BY-4.0 |
| `ogc001701` | Hermas | Pastor | `tlg1419.tlg001` | 27,284 | CC-BY-SA-4.0 |
| `ogc001705` | Hermias | Fragmenta | `tlg2384.tlg003` | 515 | PD |
| `ogc001706` | hermias | Fragmenta | `tlg2384.tlg001` | 267 | CC-BY-SA-4.0 |
| `ogc003691` | Hermias | Irrisio Gentilium Philosophorum | `tlg0531.tlg001` | 1,818 | CC-BY-4.0 |
| `ogc001817` | Hippolytus | Refutatio Omnium Haeresium (= Philosophumena) | `tlg2115.tlg060` | 69,956 | CC-BY-SA-4.0 |
| `ogc001816` | hippolytus-of-rome | Commentarii in Danielem |  | 36,847 | CC-BY-4.0 |
| `ogc001882` | Ignatius | Epistulae Interpolatae Et Epistulae Suppositiciae (Recensio Longior) [Sp.] | `tlg1443.tlg002` | 19,276 | CC-BY-SA-4.0 |
| `ogc001883` | Ignatius | Epistulae Vii Genuinae (Recensio Media) | `tlg1443.tlg001` | 7,748 | CC-BY-SA-4.0 |
| `ogc003693` | Ignatius | Fragmenta ex epistolis (excerpts quoted in later writers; PG 5 fragment section) |  | 1,281 | CC-BY-4.0 |
| `ogc001890` | Irenaeus | Adversus Haereses (Libri 1-2) | `tlg1447.tlg001` | 20,907 | CC-BY-SA-4.0 |
| `ogc001891` | Irenaeus | Fragmenta Synodicae Epistulae. | `tlg1447.tlg009` | 328 | CC-BY-SA-4.0 |
| `ogc002136` | Justinus Martyr | Apologia | `tlg0645.tlg001` | 14,437 | CC-BY-SA-4.0 |
| `ogc002137` | Justinus Martyr | Apologia Secunda | `tlg0645.tlg002` | 3,293 | CC-BY-SA-4.0 |
| `ogc002138` | Justinus Martyr | Dialogus Cum Tryphone | `tlg0645.tlg003` | 52,030 | CC-BY-SA-4.0 |
| `ogc003704` | Justinus Martyr | Fragmenta Operum Deperditorum | `tlg0645.tlg004` | 338 | CC-BY-4.0 |
| `ogc003949` | Marcellus | Expositio Fidei | `tlg2041.tlg004` | 1,060 | PD (ancient Greek text; public-domain Gutenberg edition) |
| `ogc002400` | Marcellus | Fragmenta | `tlg2041.tlg001` | 11,050 | CC-BY-SA-4.0 |
| `ogc002401` | marcellus | Fragmenta | `tlg2458.tlg002` | 134 | CC-BY-SA-4.0 |
| `ogc002407` | Marcus Diaconus | Vita Porphyrii Episcopi Gazensis | `tlg2806.tlg001` | 22,308 | CC-BY-SA-4.0 |
| `ogc003714` | Martyrium Ignatii | Martyrium Ignatii Antiocheni (Martyrium Antiochenum) | `tlg2657.tlg001` | 1,280 | CC-BY-4.0 |
| `ogc002411` | Martyrium Polycarpi | Epistula Ecclesiae Smyrnensis De Martyrio Sancti Polycarpi | `tlg1484.tlg001` | 2,641 | CC-BY-SA-4.0 |
| `ogc002427` | melito | Fragmenta |  | 23 | CC-BY-SA-4.0 |
| `ogc003716` | Melito | Fragmenta | `tlg1495.tlg003` | 931 | CC-BY-4.0 |
| `ogc002451` | methodius | Adversus Porphyrium (Fragmenta) | `tlg2959.tlg006` | 1,218 | CC-BY-SA-4.0 |
| `ogc002452` | methodius | De Creatis (Fragmenta Ap. Photium, Bibl. Cod. 235) | `tlg2959.tlg005` | 1,858 | CC-BY-SA-4.0 |
| `ogc002453` | methodius | De Libero Arbitrio | `tlg2959.tlg002` | 7,259 | CC-BY-SA-4.0 |
| `ogc002454` | methodius | De Martyribus (Fragmenta) | `tlg2959.tlg008` | 57 | CC-BY-SA-4.0 |
| `ogc002455` | methodius | Fragmenta In Job (In Catenis) | `tlg2959.tlg007` | 1,505 | CC-BY-SA-4.0 |
| `ogc002456` | methodius | Fragmenta Incerta [Sp.] | `tlg2959.tlg010` | 142 | CC-BY-SA-4.0 |
| `ogc002457` | methodius | Symposium Sive Convivium Decem Virginum | `tlg2959.tlg001` | 28,441 | CC-BY-SA-4.0 |
| `ogc002619` | origen | Catholica in Psalmos |  | 1,351 | CC-BY-SA-4.0 |
| `ogc002620` | origen | Prologi varii in Psalmos |  | 1,702 | CC-BY-SA-4.0 |
| `ogc002621` | Origenes | Adnotationes In Deuteronomium (Fragmenta E Catenis) | `tlg2042.tlg070` | 1,848 | CC-BY-SA-4.0 |
| `ogc002622` | Origenes | Adnotationes In Exodum | `tlg2042.tlg067` | 246 | CC-BY-SA-4.0 |
| `ogc002623` | Origenes | Adnotationes In Genesim | `tlg2042.tlg066` | 635 | CC-BY-SA-4.0 |
| `ogc002624` | Origenes | Adnotationes In Jesu Filium Nave (Fragmenta E Catenis) | `tlg2042.tlg071` | 171 | CC-BY-SA-4.0 |
| `ogc002625` | Origenes | Adnotationes In Judices | `tlg2042.tlg072` | 136 | CC-BY-SA-4.0 |
| `ogc002626` | Origenes | Adnotationes In Leviticum (Fragmenta E Catenis) | `tlg2042.tlg068` | 475 | CC-BY-SA-4.0 |
| `ogc002627` | Origenes | Adnotationes In Numeros | `tlg2042.tlg069` | 209 | CC-BY-SA-4.0 |
| `ogc002628` | Origenes | Commentarii In Evangelium Joannis (Lib. 1, 2, 4, 5, 6, 10, 13) | `tlg2042.tlg005` | 153,896 | CC-BY-SA-4.0 |
| `ogc002629` | Origenes | Commentarii In Evangelium Joannis (Lib. 19, 20, 28, 32) | `tlg2042.tlg079` | 58,809 | CC-BY-SA-4.0 |
| `ogc002630` | Origenes | Commentarium In Evangelium Matthaei (Lib. 10-11) | `tlg2042.tlg029` | 21,994 | CC-BY-SA-4.0 |
| `ogc002631` | Origenes | Commentarium In Evangelium Matthaei (Lib. 12-17) | `tlg2042.tlg030` | 90,101 | CC-BY-SA-4.0 |
| `ogc002632` | Origenes | Contra Celsum | `tlg2042.tlg001` | 164,880 | CC-BY-SA-4.0 |
| `ogc002633` | Origenes | De Engastrimytho (= Homilia In I Reg. [I Sam.] 28.3-25) | `tlg2042.tlg013` | 3,572 | CC-BY-SA-4.0 |
| `ogc002634` | Origenes | De Oratione | `tlg2042.tlg008` | 27,950 | CC-BY-SA-4.0 |
| `ogc002635` | Origenes | Epistula Ad Africanum | `tlg2042.tlg045` | 4,611 | CC-BY-SA-4.0 |
| `ogc002636` | Origenes | Excerpta In Psalmos [Dub.] | `tlg2042.tlg074` | 8,658 | CC-BY-SA-4.0 |
| `ogc002637` | Origenes | Exhortatio Ad Martyrium | `tlg2042.tlg007` | 12,332 | CC-BY-SA-4.0 |
| `ogc002638` | Origenes | Expositio In Proverbia (Fragmenta E Catenis) | `tlg2042.tlg075` | 17,479 | CC-BY-SA-4.0 |
| `ogc002639` | Origenes | Fragmenta Ex Commentariis In Ezechielem | `tlg2042.tlg061` | 328 | CC-BY-SA-4.0 |
| `ogc002640` | Origenes | Fragmenta In Evangelium Joannis (In Catenis) | `tlg2042.tlg006` | 21,986 | CC-BY-SA-4.0 |
| `ogc002641` | Origenes | Fragmenta In Jeremiam (E Philocalia) | `tlg2042.tlg084` | 743 | CC-BY-SA-4.0 |
| `ogc002642` | Origenes | Fragmenta In Jeremiam (In Catenis) | `tlg2042.tlg010` | 8,240 | CC-BY-SA-4.0 |
| `ogc002643` | Origenes | Fragmenta In Lamentationes (In Catenis) | `tlg2042.tlg011` | 10,249 | CC-BY-SA-4.0 |
| `ogc002644` | Origenes | Fragmenta In Librum Primum Regnorum (In Catenis) | `tlg2042.tlg014` | 1,906 | CC-BY-SA-4.0 |
| `ogc002645` | Origenes | Fragmenta In Lucam (In Catenis) | `tlg2042.tlg017` | 13,918 | CC-BY-SA-4.0 |
| `ogc002646` | Origenes | Fragmenta In Psalmos 1-150 [Dub.] | `tlg2042.tlg044` | 7,826 | CC-BY-SA-4.0 |
| `ogc002647` | Origenes | Fragmentum In Lamentationes (In Catenis) | `tlg2042.tlg012` | 166 | CC-BY-SA-4.0 |
| `ogc002648` | Origenes | Fragmentum In Librum Primum Regnorum (In Catenis) | `tlg2042.tlg015` | 83 | CC-BY-SA-4.0 |
| `ogc002649` | Origenes | Homiliae In Job (Fragmenta In Catenis, Typus I) (E Codd. Paris.) | `tlg2042.tlg057` | 3,028 | CC-BY-SA-4.0 |
| `ogc002651` | Origenes | Homiliae In Job (Fragmenta In Catenis, Typus I+II) (E Codd. Vat.) | `tlg2042.tlg086` | 6,070 | CC-BY-SA-4.0 |
| `ogc002650` | Origenes | Homiliae In Job (Fragmenta In Catenis, Typus II) (E Codd. Marc. Gr. 21, 538) | `tlg2042.tlg073` | 8,470 | CC-BY-SA-4.0 |
| `ogc002652` | Origenes | Homiliae In Lucam | `tlg2042.tlg016` | 17,232 | CC-BY-SA-4.0 |
| `ogc002653` | Origenes | In Jeremiam (Homiliae 1-11) | `tlg2042.tlg009` | 24,058 | CC-BY-SA-4.0 |
| `ogc002654` | Origenes | In Jeremiam (Homiliae 12-20) | `tlg2042.tlg021` | 30,552 | CC-BY-SA-4.0 |
| `ogc002655` | Origenes | Philocalia Sive Ecloga De Operibus Origenis A Basilio Et Gregorio Nazianzeno Facta (Cap. 1-27) | `tlg2042.tlg019` | 63,387 | CC-BY-SA-4.0 |
| `ogc002656` | Origenes | Scholia In Canticum Canticorum | `tlg2042.tlg076` | 6,960 | CC-BY-SA-4.0 |
| `ogc002657` | Origenes | Scholia In Lucam (Fragmenta E Cod. Venet. 28) | `tlg2042.tlg078` | 10,760 | CC-BY-SA-4.0 |
| `ogc002658` | Origenes | Scholia In Matthaeum | `tlg2042.tlg077` | 4,212 | CC-BY-SA-4.0 |
| `ogc002659` | Origenes | Selecta In Deuteronomium (Fragmenta E Catenis) | `tlg2042.tlg053` | 2,397 | CC-BY-SA-4.0 |
| `ogc002660` | Origenes | Selecta In Exodum (Fragmenta E Catenis) | `tlg2042.tlg050` | 3,154 | CC-BY-SA-4.0 |
| `ogc002661` | Origenes | Selecta In Genesim (Fragmenta E Catenis) | `tlg2042.tlg048` | 9,699 | CC-BY-SA-4.0 |
| `ogc002662` | Origenes | Selecta In Jesu Nave (Fragmenta E Catenis) | `tlg2042.tlg054` | 928 | CC-BY-SA-4.0 |
| `ogc002663` | Origenes | Selecta In Judices (Fragmenta E Catenis) | `tlg2042.tlg055` | 265 | CC-BY-SA-4.0 |
| `ogc002664` | Origenes | Selecta In Leviticum (Fragmenta E Catenis) | `tlg2042.tlg051` | 1,469 | CC-BY-SA-4.0 |
| `ogc002665` | Origenes | Selecta In Numeros | `tlg2042.tlg052` | 1,687 | CC-BY-SA-4.0 |
| `ogc002666` | Origenes | Selecta In Psalmos [Dub.] (Fragmenta E Catenis) | `tlg2042.tlg058` | 98,327 | CC-BY-SA-4.0 |
| `ogc003745` | pantaenus | Fragmenta |  | 225 | CC-BY-4.0 |
| `ogc003746` | Papias | Fragmenta | `tlg1558.tlg001` | 708 | CC-BY-4.0 |
| `ogc003011` | Polycarpus | Epistula Ad Philippenses | `tlg1622.tlg001` | 1,131 | CC-BY-SA-4.0 |
| `ogc003763` | Pseudo-Justinus Martyr | Cohortatio Ad Gentiles | `tlg0646.tlg002` | 10,716 | CC-BY-4.0 |
| `ogc003764` | Pseudo-Justinus Martyr | Confutatio Dogmatum Quorundam Aristotelicorum | `tlg0646.tlg008` | 15,140 | CC-BY-4.0 |
| `ogc003765` | Pseudo-Justinus Martyr | De Monarchia | `tlg0646.tlg003` | 1,825 | CC-BY-4.0 |
| `ogc003766` | Pseudo-Justinus Martyr | De Resurrectione | `tlg0646.tlg005` | 3,434 | CC-BY-4.0 |
| `ogc003092` | Pseudo-Justinus Martyr | Epistula Ad Diognetum | `tlg0646.tlg004` | 2,612 | CC-BY-SA-4.0 |
| `ogc003767` | Pseudo-Justinus Martyr | Epistula Ad Zenam Et Serenum | `tlg0646.tlg007` | 3,479 | CC-BY-4.0 |
| `ogc003768` | Pseudo-Justinus Martyr | Expositio Rectae Fidei | `tlg0646.tlg006` | 5,806 | CC-BY-4.0 |
| `ogc003769` | Pseudo-Justinus Martyr | Fragmenta | `tlg0646.tlg012` | 852 | CC-BY-4.0 |
| `ogc003770` | Pseudo-Justinus Martyr | Oratio Ad Gentiles | `tlg0646.tlg001` | 1,047 | CC-BY-4.0 |
| `ogc003771` | Pseudo-Justinus Martyr | Quaestiones Christianorum Ad Gentiles | `tlg0646.tlg010` | 13,131 | CC-BY-4.0 |
| `ogc003772` | Pseudo-Justinus Martyr | Quaestiones Et Responsiones Ad Orthodoxos | `tlg0646.tlg009` | 28,135 | CC-BY-4.0 |
| `ogc003773` | Pseudo-Justinus Martyr | Quaestiones Gentilium Ad Christianos | `tlg0646.tlg011` | 5,292 | CC-BY-4.0 |
| `ogc003775` | quadratus-apologeta | Fragmentum apologiae (apud Eusebium, HE 4.3) |  | 48 | CC-BY-4.0 |
| `ogc003187` | Seniores Apud Irenaeum | Reliquiae Plurium Anonymorum | `tlg1665.tlg001` | 348 | CC-BY-SA-4.0 |
| `ogc003244` | serapion | Fragmenta | `tlg1669.tlg004` | 1,935 | CC-BY-SA-4.0 |
| `ogc003777` | Serapion | Fragmenta | `tlg1670.tlg001` | 194 | CC-BY-4.0 |
| `ogc003794` | Tatianus | Fragmenta (Tatiani fragmenta, PG 6, 1601-1608) |  | 290 | CC-BY-4.0 |
| `ogc003388` | Tatianus | Oratio Ad Graecos | `tlg1766.tlg001` | 10,227 | CC-BY-SA-4.0 |
| `ogc003406` | Testamentum Abrahae | Testamentum Abrahae (Recensio A) (Olim Partim Sub Auctore Hesychio Hierosolymitano) | `tlg1701.tlg001` | 6,910 | CC-BY-SA-4.0 |
| `ogc003405` | Testamentum Abrahae | Testamentum Abrahae (Recensio B) | `tlg1701.tlg002` | 3,225 | CC-BY-SA-4.0 |
| `ogc003470` | Theophilus | Ad Autolycum | `tlg1725.tlg001` | 21,605 | CC-BY-SA-4.0 |
| `ogc003471` | Theophilus | Fragmenta | `tlg0512.tlg001` | 414 | PD |
| `ogc003472` | theophilus | Fragmenta | `tlg2203.tlg002` | 401 | CC-BY-SA-4.0 |
| `ogc003574` | Vitae Prophetarum | De Prophetarum Vita Et Obitu (Dorothei Recensio) | `tlg1750.tlg001` | 5,390 | CC-BY-SA-4.0 |
| `ogc003575` | Vitae Prophetarum | De Prophetarum Vita Et Obitu (Recensio Anonyma) | `tlg1750.tlg002` | 4,083 | CC-BY-SA-4.0 |
| `ogc003576` | Vitae Prophetarum | De Prophetarum Vita Et Obitu (Recensio Scholiis Hesychii Aliorumque Patrum In Prophetas Adjecta) | `tlg1750.tlg003` | 1,166 | CC-BY-SA-4.0 |
| `ogc003577` | Vitae Prophetarum | Index Apostolorum Discipulorumque Domini (Textus Pseudo-Dorothei) | `tlg1750.tlg004` | 3,616 | CC-BY-SA-4.0 |

## Post-Nicene, Eastern Fathers & Saints (`church-fathers-late`: 280 works, 38 authors, 7,962,722 tokens)

Hosted in `church-fathers-late-corpus` (~26.7 MB, Public Domain / CC BY 4.0 / CC BY-SA 4.0).

| Work ID | Author | Title | TLG | Tokens | License |
| --- | --- | --- | --- | ---: | --- |
| `ogc003919` | anonymi-de-essentia-et-operatione-dei | De essentia et operatione Dei |  | 10,989 | CC-BY-4.0 |
| `ogc003941` | anonymi-in-acta-apostolorum | Κεφάλαια τῶν Πράξεων τῶν ἀποστόλων |  | 1,198 | CC-BY-4.0 |
| `ogc003944` | anonymi-in-acta-apostolorum | Ἡ τῶν ἐπιστολῶν ὑπόθεσις διὰ ἰάμβων |  | 1,071 | CC-BY-4.0 |
| `ogc003942` | anonymi-in-acta-apostolorum | Ὑπόθεσις τῆς βίβλου τῶν Πράξεων |  | 521 | CC-BY-4.0 |
| `ogc003943` | anonymi-in-acta-apostolorum | Ὑπόθεσις τῶν Πράξεων τῶν ἀποστόλων (καὶ ἄλλως) |  | 340 | CC-BY-4.0 |
| `ogc000242` | anonymus-author-of-vita-cononis | Vita sancti Cononis Bidanae |  | 6,869 | CC-BY-SA-4.0 |
| `ogc000720` | Catenae (Novum Testamentum) | Catena In Acta (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg008` | 118,263 | CC-BY-SA-4.0 |
| `ogc000721` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Colossenses (Typus Parisinus) (E Cod. Coislin. 204) | `tlg4102.tlg022` | 13,684 | CC-BY-SA-4.0 |
| `ogc000722` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Ephesios (Typus Parisinus) (E Cod. Coislin. 204) | `tlg4102.tlg020` | 38,527 | CC-BY-SA-4.0 |
| `ogc000723` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Galatas (Typus Parisinus) (E Cod. Coislin. 204) | `tlg4102.tlg019` | 27,093 | CC-BY-SA-4.0 |
| `ogc000724` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Hebraeos (E Cod. Paris. Coislin. 204) | `tlg4102.tlg038` | 152,852 | CC-BY-SA-4.0 |
| `ogc000725` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Philemonem (E Cod. Paris. Coislin. 204) | `tlg4102.tlg037` | 2,157 | CC-BY-SA-4.0 |
| `ogc000726` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Philippenses (Typus Parisinus) (E Cod. Coislin. 204) | `tlg4102.tlg021` | 18,520 | CC-BY-SA-4.0 |
| `ogc000727` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Romanos (Typus Monacensis) (E Cod. Monac. Gr. 412) | `tlg4102.tlg011` | 114,231 | CC-BY-SA-4.0 |
| `ogc000728` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Romanos (Typus Vaticanus) (E Cod. Oxon. Bodl. Auct. E.2.20 [= Misc. 48]) | `tlg4102.tlg010` | 48,731 | CC-BY-SA-4.0 |
| `ogc000729` | Catenae (Novum Testamentum) | Catena In Epistulam Ad Titum (E Cod. Paris. Coislin. 204) | `tlg4102.tlg036` | 4,495 | CC-BY-SA-4.0 |
| `ogc000730` | Catenae (Novum Testamentum) | Catena In Epistulam I Ad Corinthios (Typus Vaticanus) (E Cod. Paris. Gr. 227) | `tlg4102.tlg012` | 104,898 | CC-BY-SA-4.0 |
| `ogc000731` | Catenae (Novum Testamentum) | Catena In Epistulam I Ad Thessalonicenses (Typus Parisinus) (E Cod. Coislin. 204) | `tlg4102.tlg023` | 9,607 | CC-BY-SA-4.0 |
| `ogc000732` | Catenae (Novum Testamentum) | Catena In Epistulam I Ad Timotheum (E Cod. Paris. Coislin. 204) | `tlg4102.tlg034` | 13,854 | CC-BY-SA-4.0 |
| `ogc000733` | Catenae (Novum Testamentum) | Catena In Epistulam Ii Ad Corinthios (Catena Pseudo-Oecumenii) (E Cod. Paris. Gr. 223) | `tlg4102.tlg013` | 33,413 | CC-BY-SA-4.0 |
| `ogc000734` | Catenae (Novum Testamentum) | Catena In Epistulam Ii Ad Thessalonicenses (Typus Parisinus) (E Cod. Coislin. 204) | `tlg4102.tlg024` | 8,936 | CC-BY-SA-4.0 |
| `ogc000735` | Catenae (Novum Testamentum) | Catena In Epistulam Ii Ad Timotheum (E Cod. Paris. Coislin. 204) | `tlg4102.tlg035` | 7,844 | CC-BY-SA-4.0 |
| `ogc000736` | Catenae (Novum Testamentum) | Catena In Epistulam Jacobi (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg040` | 10,732 | CC-BY-SA-4.0 |
| `ogc000737` | Catenae (Novum Testamentum) | Catena In Epistulam Joannis I (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg043` | 11,545 | CC-BY-SA-4.0 |
| `ogc000738` | Catenae (Novum Testamentum) | Catena In Epistulam Joannis Ii (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg044` | 650 | CC-BY-SA-4.0 |
| `ogc000739` | Catenae (Novum Testamentum) | Catena In Epistulam Joannis Iii (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg045` | 901 | CC-BY-SA-4.0 |
| `ogc000740` | Catenae (Novum Testamentum) | Catena In Epistulam Juda (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg046` | 4,417 | CC-BY-SA-4.0 |
| `ogc000741` | Catenae (Novum Testamentum) | Catena In Epistulam Petri I (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg041` | 11,420 | CC-BY-SA-4.0 |
| `ogc000742` | Catenae (Novum Testamentum) | Catena In Epistulam Petri Ii (Catena Andreae) (E Cod. Oxon. Coll. Nov. 58) | `tlg4102.tlg042` | 5,194 | CC-BY-SA-4.0 |
| `ogc000743` | Catenae (Novum Testamentum) | Catena In Joannem (Catena Integra) (E Codd. Paris. Coislin. 23 + Oxon. Bodl. Auct. T.1.4) | `tlg4102.tlg005` | 74,203 | CC-BY-SA-4.0 |
| `ogc000744` | Catenae (Novum Testamentum) | Catena In Lucam (Typus B) (E Codd. Paris. Coislin. 23 + Oxon. Bodl. Misc. 182) | `tlg4102.tlg004` | 50,045 | CC-BY-SA-4.0 |
| `ogc000745` | Catenae (Novum Testamentum) | Catena In Marcum (Recensio Ii) (E Codd. Oxon. Bodl. Laud. 33 Paris. Coislin. 23 Paris. Gr. 178) | `tlg4102.tlg002` | 51,747 | CC-BY-SA-4.0 |
| `ogc000746` | Catenae (Novum Testamentum) | Catena In Matthaeum (Catena Integra) (E Cod. Paris. Coislin. Gr. 23) | `tlg4102.tlg001` | 77,061 | CC-BY-SA-4.0 |
| `ogc000748` | Catenae (Novum Testamentum) | Supplementum Et Varietas Lectionis Ad Catenam In Evangelium Sancti Joannis (E Cod. Bodl. B.) | `tlg4102.tlg007` | 3,536 | CC-BY-SA-4.0 |
| `ogc000747` | Catenae (Novum Testamentum) | Supplementum Et Varietas Lectionis Ad Catenam In Evangelium Sancti Lucae (E Cod. Oxon. Bodl. Laud. 33) | `tlg4102.tlg006` | 3,333 | CC-BY-SA-4.0 |
| `ogc000749` | Catenae (Novum Testamentum) | Supplementum Et Varietas Lectionis Ad Commentarium Chrysostomi In Evangelium Sancti Matthaei (E Cod. Oxon. Bodl. Auct. T.1.4) | `tlg4102.tlg003` | 12,723 | CC-BY-SA-4.0 |
| `ogc002580` | Concilium Ephesenum | Acta concilii Ephesini (Mansi t. 4) |  | 129,336 | PD |
| `ogc002581` | Concilium Ephesenum | Acta concilii Ephesini (Mansi t. 5) |  | 62,697 | PD |
| `ogc000934` | Cyrillus | Ad Calosyrium (Epist. 83) | `tlg4090.tlg022` | 70 | PD |
| `ogc000935` | Cyrillus | Ad Euoptium Episcopum Ptolemaidis (Epist. 84) | `tlg4090.tlgX48` | 822 | PD |
| `ogc000936` | Cyrillus | Apologeticus Ad Theodosium Imperatorem | `tlg4090.tlgX30` | 4,309 | PD |
| `ogc000937` | Cyrillus | Apologia Xii Anathematismorum Contra Theodoretum | `tlg4090.tlgX49` | 11,193 | PD |
| `ogc000938` | Cyrillus | Apologia Xii Capitulorum Contra Orientales | `tlg4090.tlgX53` | 12,272 | PD |
| `ogc000929` | Cyrillus | Catecheses Ad Illuminandos 1-18 | `tlg2110.tlg003` | 72,357 | PD |
| `ogc000939` | Cyrillus | Collectio Dictorum Veteris Testamenti [Sp.] | `tlg4090.tlg124` | 2,510 | PD |
| `ogc000940` | Cyrillus | Commentarii In Joannem | `tlg4090.tlg002` | 390,380 | CC-BY-4.0 |
| `ogc000941` | Cyrillus | Commentarii In Lucam (In Catenis) | `tlg4090.tlg108` | 86,971 | PD |
| `ogc000942` | Cyrillus | Commentarius In Isaiam Prophetam | `tlg4090.tlg103` | 293,829 | PD |
| `ogc000943` | Cyrillus | Commentarius In Xii Prophetas Minores | `tlg4090.tlg001` | 303,643 | CC-BY-SA-4.0 |
| `ogc000944` | Cyrillus | Contra Julianum (Lib. 1-2) | `tlg4090.tlg176` | 121,011 | PD |
| `ogc000945` | Cyrillus | De Adoratione Et Cultu In Spiritu Et Veritate | `tlg4090.tlg096` | 204,010 | CC-BY-SA-4.0 |
| `ogc000946` | Cyrillus | De Incarnatione Dei Verbi (Homilia Diversa 15) | `tlg4090.tlgX78` | 1,122 | PD |
| `ogc000947` | Cyrillus | De Incarnatione Unigeniti | `tlg4090.tlg026` | 9,085 | PD |
| `ogc000949` | Cyrillus | De Sancta Trinitate [Sp.] | `tlg4090.tlg123` | 16,997 | PD |
| `ogc000948` | Cyrillus | De Sancta Trinitate Dialogi I-Vii | `tlg4090.tlg023` | 77,962 | PD |
| `ogc000950` | Cyrillus | Dialogus Cum Nestorio [Sp.] | `tlg4090.tlg110` | 8,252 | PD |
| `ogc000930` | Cyrillus | Epistula Ad Constantium Imperatorem | `tlg2110.tlg013` | 1,737 | PD |
| `ogc000951` | Cyrillus | Epistulae Paschales Sive Homiliae Paschales (Epist. 1-30) | `tlg4090.tlg032` | 118,204 | PD |
| `ogc000952` | Cyrillus | Explanatio Xii Capitulorum | `tlg4090.tlgX44` | 3,016 | PD |
| `ogc000953` | Cyrillus | Expositio In Psalmos | `tlg4090.tlg100` | 95,186 | PD |
| `ogc000954` | Cyrillus | Expositio In Psalmos (Prooemium) | `tlg4090.tlg125` | 367 | PD |
| `ogc000955` | Cyrillus | Fragmenta In Canticum Canticorum | `tlg4090.tlg102` | 5,267 | PD |
| `ogc000956` | Cyrillus | Fragmenta In Libros Regum | `tlg4090.tlg099` | 5,753 | PD |
| `ogc000957` | Cyrillus | Fragmenta In Sancti Pauli Epistulam Ad Hebraeos | `tlg4090.tlg006` | 1,244 | PD |
| `ogc000958` | Cyrillus | Fragmenta In Sancti Pauli Epistulam Ad Romanos | `tlg4090.tlg003` | 28,008 | PD |
| `ogc000959` | Cyrillus | Fragmenta In Sancti Pauli Epistulam Ii Ad Corinthios | `tlg4090.tlg005` | 4,107 | PD |
| `ogc000960` | Cyrillus | Glaphyra In Pentateuchum | `tlg4090.tlg097` | 145,283 | CC-BY-SA-4.0 |
| `ogc000931` | Cyrillus | Homilia In Occursum Domini [Sp.] | `tlg2110.tlg007` | 6,251 | PD |
| `ogc000961` | Cyrillus | Libri V Contra Nestorium | `tlg4090.tlgX47` | 50,043 | PD |
| `ogc000932` | Cyrillus | Mystagogiae 1-5 [Sp.] | `tlg2110.tlg002` | 7,718 | PD |
| `ogc000962` | Cyrillus | Oratio Ad Arcadiam Et Marinam Augustas De Fide | `tlg4090.tlgX46` | 21,398 | PD |
| `ogc000963` | Cyrillus | Oratio Ad Pulcheriam Et Eudociam Augustas De Fide | `tlg4090.tlgX45` | 15,879 | PD |
| `ogc000964` | Cyrillus | Oratio Ad Theodosium Imperatorem De Recta Fide | `tlg4090.tlgX06` | 11,351 | PD |
| `ogc000933` | Cyrillus | Procatechesis | `tlg2110.tlg001` | 2,577 | PD |
| `ogc000965` | Cyrillus | Quod Unus Sit Christus | `tlg4090.tlg027` | 18,345 | PD |
| `ogc000966` | Cyrillus | Responsiones Ad Tiberium Diaconum Sociosque Suos | `tlg4090.tlg021` | 7,229 | PD |
| `ogc000967` | Cyrillus | Scholia De Incarnatione Unigeniti (Fragmenta) | `tlg4090.tlgX62` | 2,439 | PD |
| `ogc000968` | Cyrillus | Sermo De Obitu Sanctorum Trium Puerorum (Fragmenta) [Sp.] | `tlg4090.tlg122` | 1,178 | PD |
| `ogc000969` | Cyrillus | Thesaurus De Sancta Consubstantiali Trinitate | `tlg4090.tlg109` | 131,280 | PD |
| `ogc003684` | demetrius-cydones | Occisorum Thessalonicae monodia |  | 2,526 | CC-BY-4.0 |
| `ogc001196` | elias-cretensis | Commentarii in sancti Gregorii Nazianzeni orationes xix | `tlg4520.tlg001` | 38,707 | PD |
| `ogc003687` | esaias-cyprius | Epistola (anti-Latin, on the procession of the Holy Spirit) |  | 707 | CC-BY-4.0 |
| `ogc003927` | Euthalius Diaconus | Apodemiae Pauli |  | 1,027 | CC-BY-4.0 |
| `ogc003928` | Euthalius Diaconus | Martyrium Pauli |  | 67 | CC-BY-4.0 |
| `ogc003929` | Euthalius Diaconus | Prologus in epistulas Pauli |  | 643 | CC-BY-4.0 |
| `ogc001338` | Evagrius Scholasticus | Historia Ecclesiastica | `tlg2733.tlg001` | 54,357 | CC-BY-SA-4.0 |
| `ogc003931` | gregorius-palamas | Confessio fidei |  | 1,547 | CC-BY-4.0 |
| `ogc003911` | gregorius-palamas | Homiliae |  | 117,841 | CC-BY-4.0 |
| `ogc001741` | hesychius-of-jerusalem | Commentarius magnus in Psalmos |  | 61,762 | CC-BY-SA-4.0 |
| `ogc003692` | hilarion-monachus | Logos dialektikos / Oratio dialectica de pane mystico Graecorum et azymo Latinorum |  | 1,414 | CC-BY-4.0 |
| `ogc002095` | Joannes Damascenus | Adversus Iconoclastas [Sp.] | `tlg2934.tlgX03` | 3,599 | PD |
| `ogc002096` | Joannes Damascenus | Commentarii In Epistulas Pauli [Dub.] | `tlg2934.tlg053` | 96,420 | PD |
| `ogc002097` | Joannes Damascenus | Contra Nestorianos | `tlg2934.tlg010` | 8,878 | PD |
| `ogc002098` | Joannes Damascenus | De Azymis (Fragmenta Duo) [Sp.] | `tlg2934.tlg051` | 453 | PD |
| `ogc002099` | Joannes Damascenus | De Duabus In Christo Voluntatibus | `tlg2934.tlg008` | 11,652 | PD |
| `ogc002100` | Joannes Damascenus | De Immaculato Corpore [Sp.] | `tlg2934.tlg052` | 1,283 | PD |
| `ogc002101` | Joannes Damascenus | De Natura Composita Sive Contra Acephalos | `tlg2934.tlg013` | 2,298 | PD |
| `ogc002102` | Joannes Damascenus | De Octo Spiritibus Nequitiae (Fragmentum) [Sp.] | `tlg2934.tlg036` | 2,340 | PD |
| `ogc002103` | Joannes Damascenus | De Sacris Imaginibus Contra Constantinum Cabalinum [Sp.] | `tlg2934.tlgX02` | 12,955 | PD |
| `ogc002104` | Joannes Damascenus | De Sacris Jejuniis | `tlg2934.tlg021` | 2,468 | PD |
| `ogc002105` | Joannes Damascenus | De Sancta Trinitate (Fragmentum) [Dub.] | `tlg2934.tlg035` | 1,057 | PD |
| `ogc002106` | Joannes Damascenus | Disputatio Christiani Et Saraceni [Dub.] | `tlg2934.tlg014` | 1,432 | PD |
| `ogc002107` | Joannes Damascenus | Epistula De Hymno Trisagio | `tlg2934.tlg011` | 4,286 | PD |
| `ogc002108` | Joannes Damascenus | Institutio Elementaris | `tlg2934.tlg001` | 1,838 | PD |
| `ogc002109` | Joannes Damascenus | Oratio De His Qui In Fide Dormierunt [Sp.] | `tlg2934.tlg048` | 4,980 | PD |
| `ogc002110` | Joannes Damascenus | Passio Sancti Artemii [Dub.] | `tlg2934.tlg062` | 10,393 | PD |
| `ogc002111` | Joannes Damascenus | Quid Est Homo? (Fragmentum) [Dub.] | `tlg2934.tlg047` | 1,094 | PD |
| `ogc002112` | Joannes Damascenus | Sacra Parallela (Recensiones Secundum Alphabeti Litteras Dispositae, Quae Tres Libros Conflant) (Fragmenta E Cod. Vat. Gr. 1236) | `tlg2934.tlg018` | 109,531 | PD |
| `ogc002113` | Joannes Damascenus | Vita Barlaam Et Joasaph [Sp.] | `tlg2934.tlg066` | 64,531 | CC-BY-SA-4.0 |
| `ogc003701` | job-monachus | Prooemium (to an exposition of the Psalms) |  | 340 | CC-BY-4.0 |
| `ogc003703` | josephus-ii-patriarcha | Confessio fidei ('He teleutaia gnome tou patriarchou', Florence, 9 June 1439) |  | 237 | CC-BY-4.0 |
| `ogc003705` | laudatio-sancti-demetrii | Ex laudatione martyris Demetrii narratio (on the 904 capture of Thessalonica) |  | 624 | CC-BY-4.0 |
| `ogc002417` | Maximus | Dialexeis | `tlg0563.tlg001` | 65,940 | CC-BY-SA-4.0 |
| `ogc003715` | Maximus | Fragmentum Ex Libro De Materia | `tlg1488.tlg001` | 3,066 | CC-BY-4.0 |
| `ogc002414` | Maximus | Περὶ καταρχῶν | `tlg1487.tlg001` | 3,983 | CC-BY-SA-4.0 |
| `ogc002415` | Maximus | Περὶ καταρχῶν (Epitome) | `tlg1487.tlg002` | 2,155 | CC-BY-SA-4.0 |
| `ogc002416` | Maximus | Περὶ τῶν ἀλύτων ἀντιθέσεων (Fort. Auctore Maximo Byzantio) | `tlg2025.tlg002` | 2,999 | PD |
| `ogc003737` | Nicephorus Callistus Xanthopulus | Historia ecclesiastica, libri VIII-XIV (PG 146; books 1-7 and 15-18 are in PG 145/147, not served) |  | 239,129 | CC-BY-4.0 |
| `ogc002523` | nicetas-heracleensis | Fragmenta commentariorum XVI orationum Gregorii Nazianzeni | `tlg3096.tlg002` | 4,363 | PD |
| `ogc003918` | nicetas-maroniensis | Dialogi de processione Spiritus Sancti |  | 9,885 | CC-BY-4.0 |
| `ogc003738` | Oecumenius | Commentarius in Acta apostolorum (catena-derived commentary printed under Oecumenius' name, CPG C151 sphere) |  | 52,897 | CC-BY-4.0 |
| `ogc003739` | Oecumenius | Fragmenta In Epistulam Ad Ephesios (In Catenis) | `tlg2866.tlg006` | 18,393 | CC-BY-4.0 |
| `ogc003740` | Oecumenius | Fragmenta In Epistulam Ad Galatas (In Catenis) | `tlg2866.tlg005` | 15,415 | CC-BY-4.0 |
| `ogc003741` | Oecumenius | Fragmenta In Epistulam Ad Philippenses (In Catenis) | `tlg2866.tlg007` | 14,427 | CC-BY-4.0 |
| `ogc003742` | Oecumenius | Fragmenta in epistulam ad Romanos (in catenis) [served text = full ps.-Oecumenius catena commentary on Romans] | `tlg2866.tlg002` | 66,155 | CC-BY-4.0 |
| `ogc003743` | Oecumenius | Fragmenta In Epistulam I Ad Corinthios (In Catenis) | `tlg2866.tlg003` | 55,233 | CC-BY-4.0 |
| `ogc003744` | Oecumenius | Fragmenta In Epistulam Ii Ad Corinthios (In Catenis) | `tlg2866.tlg004` | 36,971 | CC-BY-4.0 |
| `ogc002797` | Philostorgius | Historia Ecclesiastica (Fragmenta Ap. Photium) | `tlg2058.tlg001` | 32,270 | CC-BY-SA-4.0 |
| `ogc003912` | philotheus-constantinopolitanus | Antirrhetici contra Gregoram |  | 160,979 | CC-BY-4.0 |
| `ogc003913` | philotheus-constantinopolitanus | Encomium Gregorii Palamae |  | 54,429 | CC-BY-4.0 |
| `ogc003935` | Pseudo-Dionysius Areopagita | De Caelesti Hierarchia | `tlg2798.tlg001` | 10,742 | CC-BY-4.0 |
| `ogc003936` | Pseudo-Dionysius Areopagita | De Divinis Nominibus | `tlg2798.tlg004` | 23,780 | CC-BY-4.0 |
| `ogc003937` | Pseudo-Dionysius Areopagita | De Ecclesiastica Hierarchia | `tlg2798.tlg002` | 15,981 | CC-BY-4.0 |
| `ogc003938` | Pseudo-Dionysius Areopagita | De Mystica Theologia | `tlg2798.tlg005` | 1,313 | CC-BY-4.0 |
| `ogc003939` | Pseudo-Dionysius Areopagita | Epistulae | `tlg2798.tlg006` | 6,569 | CC-BY-4.0 |
| `ogc003246` | severian-of-gabala | Contra Iudaeos in serpentem aeneum |  | 5,395 | CC-BY-SA-4.0 |
| `ogc003247` | severian-of-gabala | De centurione et contra Manichaeos et Apolinaristas | `tlg4139.tlg053` | 5,422 | CC-BY-4.0 |
| `ogc003248` | severian-of-gabala | De Christo pastore et ove | `tlg4139.tlg002` | 4,468 | CC-BY-SA-4.0 |
| `ogc003249` | severian-of-gabala | De cruce et latrone |  | 1,565 | CC-BY-SA-4.0 |
| `ogc003250` | severian-of-gabala | De fide |  | 2,540 | CC-BY-SA-4.0 |
| `ogc003251` | severian-of-gabala | De fide et lege naturae | `tlg4139.tlg001` | 3,791 | CC-BY-SA-4.0 |
| `ogc003252` | severian-of-gabala | De paenitentia et compunctione |  | 5,856 | CC-BY-SA-4.0 |
| `ogc003253` | severian-of-gabala | De sacrificiis Caini |  | 4,377 | CC-BY-4.0 |
| `ogc003254` | severian-of-gabala | De serpente homilia | `tlg4139.tlg009` | 7,625 | CC-BY-SA-4.0 |
| `ogc003255` | severian-of-gabala | De sigillis sermo |  | 5,293 | CC-BY-SA-4.0 |
| `ogc003256` | severian-of-gabala | De spiritu sancto | `tlg4139.tlg010` | 7,288 | CC-BY-SA-4.0 |
| `ogc003257` | severian-of-gabala | Encomium in sanctos martyres |  | 3,363 | CC-BY-4.0 |
| `ogc003258` | severian-of-gabala | Fragmenta in epistulas Pauli |  | 35,395 | CC-BY-SA-4.0 |
| `ogc003259` | severian-of-gabala | Homilia de legislatore | `tlg4139.tlg007` | 4,800 | CC-BY-SA-4.0 |
| `ogc003260` | severian-of-gabala | Homilia de lotione pedum |  | 1,584 | CC-BY-4.0 |
| `ogc003261` | severian-of-gabala | Homilia de Noe et de arca |  | 2,174 | CC-BY-4.0 |
| `ogc003262` | severian-of-gabala | Homilia de pace | `tlg4139.tlg018` | 2,344 | CC-BY-SA-4.0 |
| `ogc003263` | severian-of-gabala | Homilia de quinque aetatibus mundi |  | 515 | CC-BY-SA-4.0 |
| `ogc003264` | severian-of-gabala | Homilia in caecum natum |  | 1,153 | CC-BY-4.0 |
| `ogc003265` | severian-of-gabala | In ascensionem domini |  | 3,242 | CC-BY-4.0 |
| `ogc003266` | severian-of-gabala | In ascensionem domini nostri Iesu Christi et in principium Actorum | `tlg4139.tlg089` | 9,984 | CC-BY-4.0 |
| `ogc003267` | severian-of-gabala | In Chananaeam et Pharaonem | `tlg4139.tlg013` | 6,311 | CC-BY-SA-4.0 |
| `ogc003268` | severian-of-gabala | In cosmogoniam homilia 1 |  | 3,912 | CC-BY-SA-4.0 |
| `ogc003269` | severian-of-gabala | In cosmogoniam homilia 2 |  | 3,741 | CC-BY-SA-4.0 |
| `ogc003270` | severian-of-gabala | In cosmogoniam homilia 3 |  | 4,449 | CC-BY-SA-4.0 |
| `ogc003271` | severian-of-gabala | In cosmogoniam homilia 4 |  | 6,282 | CC-BY-SA-4.0 |
| `ogc003272` | severian-of-gabala | In cosmogoniam homilia 5 |  | 5,755 | CC-BY-SA-4.0 |
| `ogc003273` | severian-of-gabala | In cosmogoniam homilia 6 |  | 7,246 | CC-BY-SA-4.0 |
| `ogc003274` | severian-of-gabala | In dictum apostoli: Non quod volo facio | `tlg4139.tlg014` | 5,666 | CC-BY-SA-4.0 |
| `ogc003275` | severian-of-gabala | In filium prodigum | `tlg4139.tlg006` | 4,495 | CC-BY-SA-4.0 |
| `ogc003276` | severian-of-gabala | In Genesim sermo 2 | `tlg4139.tlg005` | 1,737 | CC-BY-SA-4.0 |
| `ogc003277` | severian-of-gabala | In illud: Genimina viperarum |  | 8,150 | CC-BY-4.0 |
| `ogc003278` | severian-of-gabala | In illud: in principium erat verbum | `tlg4139.tlg016` | 2,820 | CC-BY-SA-4.0 |
| `ogc003279` | severian-of-gabala | In illud: In qua potestate haec facis |  | 6,980 | CC-BY-SA-4.0 |
| `ogc003280` | severian-of-gabala | In illud: Pater, transeat a me calix iste |  | 6,508 | CC-BY-4.0 |
| `ogc003281` | severian-of-gabala | In illud: Pone manum tuam |  | 6,137 | CC-BY-4.0 |
| `ogc003282` | severian-of-gabala | In illud: Quomodo scit litteras | `tlg4139.tlg012` | 5,384 | CC-BY-SA-4.0 |
| `ogc003283` | severian-of-gabala | In illud: Secundum imaginem et similitudinem |  | 3,643 | CC-BY-4.0 |
| `ogc003284` | severian-of-gabala | In incarnationem domini | `tlg4139.tlg020` | 7,771 | CC-BY-4.0 |
| `ogc003285` | severian-of-gabala | In Iob sermo 1 |  | 2,258 | CC-BY-SA-4.0 |
| `ogc003286` | severian-of-gabala | In Iob sermo 2 |  | 1,790 | CC-BY-SA-4.0 |
| `ogc003287` | severian-of-gabala | In Iob sermo 3 |  | 3,669 | CC-BY-SA-4.0 |
| `ogc003288` | severian-of-gabala | In Iob sermo 4 |  | 3,903 | CC-BY-SA-4.0 |
| `ogc003289` | severian-of-gabala | In Iudaeos et Graecos |  | 5,141 | CC-BY-4.0 |
| `ogc003290` | severian-of-gabala | In meretricem et pharisaeum |  | 2,013 | CC-BY-SA-4.0 |
| `ogc003291` | severian-of-gabala | In Noe et filios eius, de cherubim et in propthetam Oseam |  | 3,730 | CC-BY-4.0 |
| `ogc003292` | severian-of-gabala | In postremum iudicium |  | 2,478 | CC-BY-4.0 |
| `ogc003293` | severian-of-gabala | In pretiosam et vivificam crucem |  | 4,881 | CC-BY-SA-4.0 |
| `ogc003294` | severian-of-gabala | In proditionem servatoris | `tlg4139.tlg015` | 2,869 | CC-BY-SA-4.0 |
| `ogc003295` | severian-of-gabala | In psalmum 95 | `tlg4139.tlg008` | 4,841 | CC-BY-SA-4.0 |
| `ogc003296` | severian-of-gabala | In psalmum 96 | `tlg4139.tlg003` | 5,387 | CC-BY-SA-4.0 |
| `ogc003297` | severian-of-gabala | In sanctam pentecosten |  | 2,383 | CC-BY-SA-4.0 |
| `ogc003298` | severian-of-gabala | In Temptationem Domini Nostri Iesu Christi | `tlg4139.tlg088` | 1,783 | CC-BY-4.0 |
| `ogc003299` | severian-of-gabala | In theophaniam | `tlg4139.tlg017` | 2,391 | CC-BY-SA-4.0 |
| `ogc003300` | severian-of-gabala | Oratio de exaltatione Crucis |  | 2,606 | CC-BY-SA-4.0 |
| `ogc003301` | severian-of-gabala | Oratio in dedicationem pretiosae et uiuificae crucis |  | 3,042 | CC-BY-SA-4.0 |
| `ogc003302` | severian-of-gabala | Quomodo animam acceperit Adamus | `tlg4139.tlg004` | 2,600 | CC-BY-SA-4.0 |
| `ogc003303` | Severianus | De Caeco Et Zacchaeo (Olim Sub Auctore Joanne Chrysostomo) | `tlg4139.tlg081` | 5,183 | CC-BY-SA-4.0 |
| `ogc003304` | Severianus | De Caeco Nato (Olim Sub Auctore Joanne Chrysostomo) | `tlg4139.tlg072` | 6,108 | CC-BY-SA-4.0 |
| `ogc003305` | Severianus | De Tribus Pueris (Olim Sub Auctore Joanne Chrysostomo) | `tlg4139.tlg067` | 2,871 | CC-BY-SA-4.0 |
| `ogc003306` | Severianus | In Genesim (Sermo 1) (Olim Sub Auctore Joanne Chrysostomo) | `tlg4139.tlg034` | 1,674 | CC-BY-SA-4.0 |
| `ogc003307` | Severianus | In Illud: Quando Ipsi Subiciet Omnia (Olim Sub Auctore Joanne Chrysostomo) | `tlg4139.tlg087` | 3,962 | CC-BY-SA-4.0 |
| `ogc003328` | Socrates Scholasticus | Historica Ecclesiastica | `tlg2057.tlg002` | 101,946 | CC-BY-SA-4.0 |
| `ogc003344` | Sophonias | In Aristotelis Libros De Anima Paraphrasis | `tlg4030.tlg001` | 69,632 | CC-BY-SA-4.0 |
| `ogc003779` | Symeon Thessalonicensis | De fine et exsequiarum ordine (De ordine sepulturae; chs. ~359-373 of the dialogue) |  | 5,652 | CC-BY-4.0 |
| `ogc003778` | Symeon Thessalonicensis | De honesto et legitimo matrimonio (chs. 276-281 of the dialogue) |  | 2,049 | CC-BY-4.0 |
| `ogc003780` | Symeon Thessalonicensis | De poenitentia (chs. 251-275 of the dialogue) |  | 6,992 | CC-BY-4.0 |
| `ogc003781` | Symeon Thessalonicensis | De sacerdotio (epistle to a devout monk) |  | 4,486 | CC-BY-4.0 |
| `ogc003782` | Symeon Thessalonicensis | De sacra liturgia (chs. ~78-100 of the dialogue) |  | 11,486 | CC-BY-4.0 |
| `ogc003783` | Symeon Thessalonicensis | De sacra precatione (on the divine office; chs. 296-ca.358 of the dialogue) |  | 30,193 | CC-BY-4.0 |
| `ogc003784` | Symeon Thessalonicensis | De sacramentis (chs. 33-70 of the dialogue) |  | 13,518 | CC-BY-4.0 |
| `ogc003785` | Symeon Thessalonicensis | De sacris ordinationibus (chs. 156-250 of the dialogue) |  | 22,031 | CC-BY-4.0 |
| `ogc003786` | Symeon Thessalonicensis | De sacro templo et eius consecratione (chs. 101-155 of the dialogue) |  | 11,848 | CC-BY-4.0 |
| `ogc003787` | Symeon Thessalonicensis | De sancto chrismate (chs. 71-77 of the dialogue) |  | 3,106 | CC-BY-4.0 |
| `ogc003788` | Symeon Thessalonicensis | De sancto oleo / euchelaeo (chs. ~282-295 of the dialogue) |  | 4,654 | CC-BY-4.0 |
| `ogc003789` | Symeon Thessalonicensis | Dialogus in Christo adversus omnes haereses (chs. 1-32 of the great dialogue) |  | 32,146 | CC-BY-4.0 |
| `ogc003790` | Symeon Thessalonicensis | Expositio de divino templo (sent to the pious in Crete) |  | 10,460 | CC-BY-4.0 |
| `ogc003792` | Symeon Thessalonicensis | Expositio de sacro symbolo (exposition of the Creed) |  | 11,426 | CC-BY-4.0 |
| `ogc003791` | Symeon Thessalonicensis | Expositio necessaria de sacri symboli dictionibus |  | 4,386 | CC-BY-4.0 |
| `ogc003793` | Symeon Thessalonicensis | Responsa ad Gabrielem Pentapolitanum (questions and answers on liturgical and canonical matters) |  | 25,609 | CC-BY-4.0 |
| `ogc003432` | Theodoretus | Commentaria In Isaiam | `tlg4089.tlg008` | 44,729 | PD |
| `ogc003433` | Theodoretus | De Providentia Orationes Decem | `tlg4089.tlg032` | 45,057 | PD |
| `ogc003434` | Theodoretus | Epistulae: Collectio Sirmondiana (Epistulae 1-95) | `tlg4089.tlg006` | 53,742 | PD |
| `ogc003435` | Theodoretus | Eranistes | `tlg4089.tlg002` | 52,474 | PD |
| `ogc003436` | Theodoretus | Explanatio In Canticum Canticorum | `tlg4089.tlg025` | 32,520 | PD |
| `ogc003437` | Theodoretus | Graecarum Affectionum Curatio | `tlg4089.tlg001` | 70,304 | PD |
| `ogc003438` | Theodoretus | Haereticarum Fabularum Compendium | `tlg4089.tlg031` | 36,699 | PD |
| `ogc003439` | Theodoretus | Historia Ecclesiastica | `tlg4089.tlg003` | 68,518 | CC-BY-SA-4.0 |
| `ogc003440` | Theodoretus | Historia Religiosa (= Philotheus) | `tlg4089.tlg004` | 44,572 | CC-BY-SA-4.0 |
| `ogc003441` | Theodoretus | Interpretatio In Danielem | `tlg4089.tlg028` | 52,719 | CC-BY-SA-4.0 |
| `ogc003442` | Theodoretus | Interpretatio In Ezechielem | `tlg4089.tlg027` | 130,017 | PD |
| `ogc003443` | Theodoretus | Interpretatio In Jeremiam | `tlg4089.tlg026` | 47,139 | PD |
| `ogc003444` | Theodoretus | Interpretatio In Psalmos | `tlg4089.tlg024` | 178,942 | PD |
| `ogc003445` | Theodoretus | Interpretatio In Xii Prophetas Minores | `tlg4089.tlg029` | 74,748 | PD |
| `ogc003446` | Theodoretus | Interpretatio In Xiv Epistulas Sancti Pauli | `tlg4089.tlg030` | 145,829 | PD |
| `ogc003447` | Theodoretus | Libellus Contra Nestorium Ad Sporacium [Sp.] | `tlg4089.tlg033` | 1,224 | PD |
| `ogc003448` | Theodoretus | Quaestiones In Libros Regnorum Et Paralipomenon | `tlg4089.tlg023` | 58,253 | PD |
| `ogc003449` | Theodoretus | Quaestiones In Octateuchum | `tlg4089.tlg022` | 66,412 | PD |
| `ogc003795` | theodorus-agallianus | Refutatio (dialogus) contra Ioannem Argyropulum |  | 16,597 | CC-BY-4.0 |
| `ogc003837` | Theophylactus Achridensis | Conclusion-fragment of a commentary on the Gospel of John (Jo 21:22-25 with account of John's death; supplement to the In Joannem) |  | 867 | CC-BY-4.0 |
| `ogc003797` | Theophylactus Achridensis | De iis quorum Latini incusantur (Allocutio cuidam ex suis familiaribus) |  | 5,352 | CC-BY-4.0 |
| `ogc003798` | Theophylactus Achridensis | Enarratio in Evangelium Joannis (complete across two volumes: PG123 John 1-7 + PG124 John 7:52-21:25) |  | 117,346 | CC-BY-4.0 |
| `ogc003799` | Theophylactus Achridensis | Enarratio in Evangelium Lucae (with prefatory vitae, hypothesis and kephalaia) |  | 97,447 | CC-BY-4.0 |
| `ogc003800` | Theophylactus Achridensis | Enarratio in Evangelium Marci (with prefatory vitae and kephalaia) |  | 38,996 | CC-BY-4.0 |
| `ogc003801` | Theophylactus Achridensis | Enarratio in Evangelium Matthaei (with prefatory Ps.-Sophronius vita and kephalaia) |  | 71,475 | CC-BY-4.0 |
| `ogc003802` | Theophylactus Achridensis | Epistulae (collected letters, ca. 75 in the PG numbering) |  | 45,441 | CC-BY-4.0 |
| `ogc003803` | Theophylactus Achridensis | Expositio in Acta apostolorum (third, compendious text: brief scholia) |  | 29,243 | CC-BY-4.0 |
| `ogc003804` | Theophylactus Achridensis | Expositio in Epistolam ad Colossenses (with prefixed hypothesis) |  | 13,841 | CC-BY-4.0 |
| `ogc003805` | Theophylactus Achridensis | Expositio in Epistolam ad Ephesios (with prefixed hypothesis, its opening words lost in the OCR) |  | 20,495 | CC-BY-4.0 |
| `ogc003806` | Theophylactus Achridensis | Expositio in Epistolam ad Galatas (with prefixed hypothesis) |  | 15,170 | CC-BY-4.0 |
| `ogc003807` | Theophylactus Achridensis | Expositio in epistolam ad Hebraeos |  | 42,985 | CC-BY-4.0 |
| `ogc003808` | Theophylactus Achridensis | Expositio in epistolam ad Philemonem |  | 2,298 | CC-BY-4.0 |
| `ogc003809` | Theophylactus Achridensis | Expositio in Epistolam ad Philippenses (with prefixed hypothesis) |  | 12,018 | CC-BY-4.0 |
| `ogc003810` | Theophylactus Achridensis | Expositio in Epistolam ad Romanos (with prefixed hypothesis) |  | 43,313 | CC-BY-4.0 |
| `ogc003811` | Theophylactus Achridensis | Expositio in epistolam ad Titum |  | 5,116 | CC-BY-4.0 |
| `ogc003812` | Theophylactus Achridensis | Expositio in epistolam catholicam S. Jacobi |  | 10,189 | CC-BY-4.0 |
| `ogc003813` | Theophylactus Achridensis | Expositio in Epistolam I ad Corinthios (with prefixed hypothesis) |  | 44,314 | CC-BY-4.0 |
| `ogc003814` | Theophylactus Achridensis | Expositio in Epistolam I ad Thessalonicenses |  | 8,530 | CC-BY-4.0 |
| `ogc003815` | Theophylactus Achridensis | Expositio in epistolam I ad Timotheum |  | 13,974 | CC-BY-4.0 |
| `ogc003816` | Theophylactus Achridensis | Expositio in epistolam I Joannis |  | 12,372 | CC-BY-4.0 |
| `ogc003817` | Theophylactus Achridensis | Expositio in epistolam I S. Petri |  | 12,115 | CC-BY-4.0 |
| `ogc003818` | Theophylactus Achridensis | Expositio in Epistolam II ad Corinthios (with prefixed hypothesis) |  | 28,922 | CC-BY-4.0 |
| `ogc003819` | Theophylactus Achridensis | Expositio in Epistolam II ad Thessalonicenses (with prefixed hypothesis) |  | 5,925 | CC-BY-4.0 |
| `ogc003820` | Theophylactus Achridensis | Expositio in epistolam II ad Timotheum |  | 9,606 | CC-BY-4.0 |
| `ogc003821` | Theophylactus Achridensis | Expositio in epistolam II Joannis |  | 2,169 | CC-BY-4.0 |
| `ogc003822` | Theophylactus Achridensis | Expositio in epistolam II S. Petri |  | 6,563 | CC-BY-4.0 |
| `ogc003823` | Theophylactus Achridensis | Expositio in epistolam III Joannis |  | 829 | CC-BY-4.0 |
| `ogc003824` | Theophylactus Achridensis | Expositio in epistolam Judae |  | 3,492 | CC-BY-4.0 |
| `ogc003825` | Theophylactus Achridensis | Expositio in prophetam Habacuc |  | 15,641 | CC-BY-4.0 |
| `ogc003826` | Theophylactus Achridensis | Expositio in prophetam Jonam |  | 11,936 | CC-BY-4.0 |
| `ogc003827` | Theophylactus Achridensis | Expositio in prophetam Michaeam |  | 25,424 | CC-BY-4.0 |
| `ogc003828` | Theophylactus Achridensis | Expositio in prophetam Nahum |  | 14,641 | CC-BY-4.0 |
| `ogc003829` | Theophylactus Achridensis | Expositio in prophetam Oseam (with dedicatory prologue and Prooemium in prophetas) |  | 46,997 | CC-BY-4.0 |
| `ogc003830` | Theophylactus Achridensis | Historia martyrii XV martyrum Tiberiopolitanorum (BHG 1199) |  | 12,879 | CC-BY-4.0 |
| `ogc003832` | Theophylactus Achridensis | In Acta apostolorum commentarius (first, longer text; catena compiled largely from Chrysostom; Theophylact attribution rejected) |  | 63,165 | CC-BY-4.0 |
| `ogc003831` | Theophylactus Achridensis | In Acta apostolorum commentarius alter (second text, with ΠΡΟΛΟΓΟΣ ΘΕΟΦΥΛΑΚΤΟΥ; TEXTUS/ΕΡΜΗΝΕΙΑ alternation) |  | 40,312 | CC-BY-4.0 |
| `ogc003833` | Theophylactus Achridensis | Institutio regia (Paideia basilike, ad Constantinum Ducam porphyrogenitum) |  | 5,019 | CC-BY-4.0 |
| `ogc003834` | Theophylactus Achridensis | Oratio in imperatorem Alexium I Comnenum |  | 3,639 | CC-BY-4.0 |
| `ogc003835` | Theophylactus Achridensis | Oratio in praesentationem Deiparae |  | 2,639 | CC-BY-4.0 |
| `ogc003836` | Theophylactus Achridensis | Oratio in venerationem crucis (mid-Lent sermon; conventional title) |  | 4,289 | CC-BY-4.0 |
| `ogc003838` | Theophylactus Achridensis | Vita Clementis Ohridensis (the long life, BHG 355) |  | 10,012 | CC-BY-4.0 |
| `ogc003922` | tomus-synodalis-anni-1351 | Tomus synodalis anni 1351 |  | 15,194 | CC-BY-4.0 |
| `ogc003923` | tomus-synodalis-contra-prochorum-cydonem | Tomus synodalis contra Prochorum Cydonem |  | 9,938 | CC-BY-4.0 |
| `ogc003925` | tomus-synodicus-contra-barlaam-et-acindynum | Tomus synodicus contra Barlaam et Acindynum |  | 5,379 | CC-BY-4.0 |
| `ogc003840` | vita-basilii-iunioris | Excerpta e Vita S. Basilii iunioris (BHG 263) |  | 1,727 | CC-BY-4.0 |

## Patrologia Graeca (`patrologia`: 33 Migne volumes, 6,787,292 words)

Hosted in `patrologia-graeca-corpus` (~23.5 MB, CC BY 4.0, Calfa–GREgORI OCR of 19th-century Migne prints). Open a single volume with `aegean.open("PG073")` or search with `aegean find λόγος PG073`.

| Volume ID | PG # | Author | Title | Period | Biblical books |
| --- | ---: | --- | --- | --- | --- |
| `PG003` | 3 | Pseudo-Dionysius the Areopagite | Opera Omnia (vol. 1) | 5th–6th c. |  |
| `PG005` | 5 | Ignatius, Polycarp, Melito et al. | Apostolic & 2nd-Century Fathers | 2nd c. |  |
| `PG006` | 6 | Justin Martyr, Tatian, Athenagoras, Theophilus | 2nd-Century Apologists | 2nd c. |  |
| `PG008` | 8 | Clement of Alexandria | Protrepticus, Paedagogus, Stromata (vol. 1) | 2nd–3rd c. |  |
| `PG009` | 9 | Clement of Alexandria | Stromata (cont.), Quis dives, Excerpta, Eclogae (vol. 2) | 2nd–3rd c. |  |
| `PG016_3` | 16.3 | Origen & Hippolytus | Origen Hexapla (cont.); Hippolytus Philosophumena | 3rd c. |  |
| `PG021` | 21 | Eusebius of Caesarea | Praeparatio Evangelica (vol. 3) | 4th c. |  |
| `PG042` | 42 | Epiphanius of Salamis | Panarion (cont.), Expositio fidei (vol. 2) | 4th c. |  |
| `PG067` | 67 | Socrates Scholasticus & Sozomen | Historia Ecclesiastica | 5th c. |  |
| `PG071` | 71 | Cyril of Alexandria | Commentaries on the Twelve Minor Prophets (vol. 4) | 5th c. | Hos, Joel, Amos, Obad, Jonah, Mic, Nah, Hab, Zeph, Hag, Zech, Mal |
| `PG073` | 73 | Cyril of Alexandria | Commentary on the Gospel of John (vol. 6) | 5th c. | John |
| `PG087_1` | 87.1 | Procopius of Gaza | Old Testament Commentaries (Octateuch & Catenae, vol. 1) | 6th c. | Gen, Exod, Lev, Num, Deut, Josh, Judg, Ruth |
| `PG101` | 101 | Photius of Constantinople | Quaestiones Amphilochianae & NT Commentary (vol. 1) | 9th c. | Matt, Mark, Luke, John, Acts, Rom, 1Cor, 2Cor, Gal, Eph, Phil, Col, Heb |
| `PG107` | 107 | Leo VI the Wise | Homilies, Panegyrics, Tactica & Juridical Works | 10th c. |  |
| `PG109` | 109 | Theophanes Continuatus, Constantine VII et al. | Byzantine Historical Works | 10th c. |  |
| `PG112` | 112 | Constantine VII Porphyrogenitus | De ceremoniis (vol. 1) | 10th c. |  |
| `PG113` | 113 | Constantine VII Porphyrogenitus & Theodosius | De thematibus, De administrando imperio (vol. 2) | 10th c. |  |
| `PG118` | 118 | Oecumenius (Pseudo-Oecumenius) | Commentaries on Acts, Pauline & Catholic Epistles (vol. 1) | 10th c. | Acts, Rom, 1Cor, 2Cor, Gal, Eph, Phil, Col, 1Thess, 2Thess, 1Tim, 2Tim, Titus, Phlm, Heb, Jas, 1Pet, 2Pet, 1John, 2John, 3John, Jude |
| `PG121` | 121 | George Cedrenus | Compendium Historiarum (vol. 1) | 11th c. |  |
| `PG122` | 122 | George Cedrenus, John Scylitzes & Michael Psellus | Compendium Historiarum (vol. 2) & Psellus Opera | 11th c. |  |
| `PG123` | 123 | Theophylact of Bulgaria | Enarratio in Evangelia Matthaei, Marci, Lucae & Joannis (vol. 1) | 11th c. | Matt, Mark, Luke, John |
| `PG124` | 124 | Theophylact of Bulgaria | Commentarius in Joannem (cont.) & Pauline Epistles (vol. 2) | 11th c. | John, Rom, 1Cor, 2Cor, Gal, Eph, Phil, Col |
| `PG125` | 125 | Theophylact of Bulgaria | Commentaries on Pauline Epistles (cont.) & 1–2 Peter (vol. 3) | 11th c. | 1Thess, 2Thess, 1Tim, 2Tim, Titus, Phlm, Heb, 1Pet, 2Pet |
| `PG126` | 126 | Theophylact of Bulgaria | Commentaries on NT & Minor Prophets; Orations & Letters (vol. 4) | 11th c. | Acts, Jas, 1John, 2John, 3John, Jude, Hos, Hab, Jonah, Nah, Mic |
| `PG134` | 134 | John Zonaras | Annales (vol. 1) | 12th c. |  |
| `PG139` | 139 | Nicetas Choniates, Isidore of Thessalonica et al. | Historia Byzantina & Thesaurus | 13th c. |  |
| `PG146` | 146 | Nicephorus Callistus | Ecclesiastical History, Books 8–14 (vol. 2) | 14th c. |  |
| `PG148` | 148 | Nicephorus Gregoras | Historia Byzantina, Books 1–24 (vol. 1) | 14th c. |  |
| `PG151` | 151 | Gregory Palamas, Acindynus & Barlaam | Hesychast Theological Works (vol. 2) | 14th c. |  |
| `PG153` | 153 | John VI Cantacuzene | Historia Byzantina, Books 1–4 (vol. 1) | 14th c. |  |
| `PG155` | 155 | Symeon of Thessalonica | Liturgical & Theological Works | 15th c. |  |
| `PG157` | 157 | George Codinus & Ducas | De officiis, Historia Byzantina (1341–1462) | 15th c. |  |
| `PG158` | 158 | Michael Glycas | Annales & Letters | 15th c. |  |

## Indexed patristic biblical commentaries (112 volumes across 11 Fathers & traditions)

Discoverable offline via `aegean.greek.bible.patristic_commentaries()` and `aegean bible commentary`:

| Work ID | Kind | Author | Biblical Book(s) | Title | Source |
| --- | --- | --- | --- | --- | --- |
| `tlg4102.tlg001` | `catena` | Catenae (NT) | Matt | Catena in Matthaeum (Catena Integra) | `first1k` |
| `tlg4102.tlg003` | `catena` | Catenae (NT) | Matt | Supplementum ad commentarium Chrysostomi in Matthaeum | `first1k` |
| `tlg4102.tlg002` | `catena` | Catenae (NT) | Mark | Catena in Marcum (Recensio II) | `first1k` |
| `tlg4102.tlg004` | `catena` | Catenae (NT) | Luke | Catena in Lucam (Typus B) | `first1k` |
| `tlg4102.tlg006` | `catena` | Catenae (NT) | Luke | Supplementum ad catenam in Lucam | `first1k` |
| `tlg4102.tlg005` | `catena` | Catenae (NT) | John | Catena in Joannem (Catena Integra) | `first1k` |
| `tlg4102.tlg007` | `catena` | Catenae (NT) | John | Supplementum ad catenam in Joannem | `first1k` |
| `tlg4102.tlg008` | `catena` | Catenae (NT) | Acts | Catena in Acta (Catena Andreae) | `first1k` |
| `tlg4102.tlg010` | `catena` | Catenae (NT) | Rom | Catena in Epistulam ad Romanos (Typus Vaticanus) | `first1k` |
| `tlg4102.tlg011` | `catena` | Catenae (NT) | Rom | Catena in Epistulam ad Romanos (Typus Monacensis) | `first1k` |
| `tlg4102.tlg012` | `catena` | Catenae (NT) | 1Cor | Catena in 1 Corinthios (Typus Vaticanus) | `first1k` |
| `tlg4102.tlg013` | `catena` | Catenae (NT) | 2Cor | Catena in 2 Corinthios (Pseudo-Oecumenius) | `first1k` |
| `tlg4102.tlg019` | `catena` | Catenae (NT) | Gal | Catena in Galatas (Typus Parisinus) | `first1k` |
| `tlg4102.tlg020` | `catena` | Catenae (NT) | Eph | Catena in Ephesios (Typus Parisinus) | `first1k` |
| `tlg4102.tlg021` | `catena` | Catenae (NT) | Phil | Catena in Philippenses (Typus Parisinus) | `first1k` |
| `tlg4102.tlg022` | `catena` | Catenae (NT) | Col | Catena in Colossenses (Typus Parisinus) | `first1k` |
| `tlg4102.tlg023` | `catena` | Catenae (NT) | 1Thess | Catena in 1 Thessalonicenses (Typus Parisinus) | `first1k` |
| `tlg4102.tlg024` | `catena` | Catenae (NT) | 2Thess | Catena in 2 Thessalonicenses (Typus Parisinus) | `first1k` |
| `tlg4102.tlg034` | `catena` | Catenae (NT) | 1Tim | Catena in 1 Timotheum (Cod. Coislin. 204) | `first1k` |
| `tlg4102.tlg035` | `catena` | Catenae (NT) | 2Tim | Catena in 2 Timotheum (Cod. Coislin. 204) | `first1k` |
| `tlg4102.tlg036` | `catena` | Catenae (NT) | Titus | Catena in Titum (Cod. Coislin. 204) | `first1k` |
| `tlg4102.tlg037` | `catena` | Catenae (NT) | Phlm | Catena in Philemonem (Cod. Coislin. 204) | `first1k` |
| `tlg4102.tlg038` | `catena` | Catenae (NT) | Heb | Catena in Hebraeos (Cod. Coislin. 204) | `first1k` |
| `tlg4102.tlg040` | `catena` | Catenae (NT) | Jas | Catena in Epistulam Jacobi (Catena Andreae) | `first1k` |
| `tlg4102.tlg041` | `catena` | Catenae (NT) | 1Pet | Catena in 1 Petri (Catena Andreae) | `first1k` |
| `tlg4102.tlg042` | `catena` | Catenae (NT) | 2Pet | Catena in 2 Petri (Catena Andreae) | `first1k` |
| `tlg4102.tlg043` | `catena` | Catenae (NT) | 1John | Catena in 1 Joannis (Catena Andreae) | `first1k` |
| `tlg4102.tlg044` | `catena` | Catenae (NT) | 2John | Catena in 2 Joannis (Catena Andreae) | `first1k` |
| `tlg4102.tlg045` | `catena` | Catenae (NT) | 3John | Catena in 3 Joannis (Catena Andreae) | `first1k` |
| `tlg4102.tlg046` | `catena` | Catenae (NT) | Jude | Catena in Epistulam Judae (Catena Andreae) | `first1k` |
| `tlg2042.tlg029` | `origen` | Origen | Matt | Commentarium in Evangelium Matthaei (Books 10–11) | `first1k` |
| `tlg2042.tlg030` | `origen` | Origen | Matt | Commentarium in Evangelium Matthaei (Books 12–17) | `first1k` |
| `tlg2042.tlg077` | `origen` | Origen | Matt | Scholia in Matthaeum | `first1k` |
| `tlg2042.tlg016` | `origen` | Origen | Luke | Homiliae in Lucam | `first1k` |
| `tlg2042.tlg017` | `origen` | Origen | Luke | Fragmenta in Lucam (in Catenis) | `first1k` |
| `tlg2042.tlg078` | `origen` | Origen | Luke | Scholia in Lucam (e cod. Venet. 28) | `first1k` |
| `tlg2042.tlg005` | `origen` | Origen | John | Commentarii in Evangelium Joannis (Books 1–13) | `first1k` |
| `tlg2042.tlg079` | `origen` | Origen | John | Commentarii in Evangelium Joannis (Books 19, 20, 28, 32) | `first1k` |
| `tlg2042.tlg006` | `origen` | Origen | John | Fragmenta in Evangelium Joannis (in Catenis) | `first1k` |
| `tlg2042.tlg048` | `origen` | Origen | Gen | Selecta in Genesim | `first1k` |
| `tlg2042.tlg066` | `origen` | Origen | Gen | Adnotationes in Genesim | `first1k` |
| `tlg2042.tlg050` | `origen` | Origen | Exod | Selecta in Exodum | `first1k` |
| `tlg2042.tlg067` | `origen` | Origen | Exod | Adnotationes in Exodum | `first1k` |
| `tlg2042.tlg051` | `origen` | Origen | Lev | Selecta in Leviticum | `first1k` |
| `tlg2042.tlg068` | `origen` | Origen | Lev | Adnotationes in Leviticum (fragmenta e catenis) | `first1k` |
| `tlg2042.tlg052` | `origen` | Origen | Num | Selecta in Numeros | `first1k` |
| `tlg2042.tlg069` | `origen` | Origen | Num | Adnotationes in Numeros | `first1k` |
| `tlg2042.tlg053` | `origen` | Origen | Deut | Selecta in Deuteronomium | `first1k` |
| `tlg2042.tlg070` | `origen` | Origen | Deut | Adnotationes in Deuteronomium (fragmenta e catenis) | `first1k` |
| `tlg2042.tlg054` | `origen` | Origen | Josh | Selecta in Jesum Nave | `first1k` |
| `tlg2042.tlg071` | `origen` | Origen | Josh | Adnotationes in Jesu filium Nave (fragmenta e catenis) | `first1k` |
| `tlg2042.tlg055` | `origen` | Origen | Judg | Selecta in Judices | `first1k` |
| `tlg2042.tlg072` | `origen` | Origen | Judg | Adnotationes in Judices | `first1k` |
| `tlg2042.tlg013` | `origen` | Origen | 1Kgdms | De Engastrimytho (Homilia in 1 Sam 28:3–25) | `first1k` |
| `tlg2042.tlg014` | `origen` | Origen | 1Kgdms | Fragmenta in Librum Primum Regnorum (in Catenis) | `first1k` |
| `tlg2042.tlg015` | `origen` | Origen | 1Kgdms | Fragmentum in Librum Primum Regnorum | `first1k` |
| `tlg2042.tlg057` | `origen` | Origen | Job | Selecta in Job | `first1k` |
| `tlg2042.tlg073` | `origen` | Origen | Job | Homiliae in Job (fragmenta in catenis, typus II) | `first1k` |
| `tlg2042.tlg086` | `origen` | Origen | Job | Homiliae in Job (fragmenta in catenis, typus I+II) | `first1k` |
| `tlg2042.tlg044` | `origen` | Origen | Ps | Fragmenta in Psalmos 1–150 [Dub.] | `first1k` |
| `tlg2042.tlg058` | `origen` | Origen | Ps | Selecta in Psalmos [Dub.] | `first1k` |
| `tlg2042.tlg074` | `origen` | Origen | Ps | Excerpta in Psalmos [Dub.] | `first1k` |
| `tlg2042.tlg075` | `origen` | Origen | Prov | Expositio in Proverbia (fragmenta e catenis) | `first1k` |
| `tlg2042.tlg076` | `origen` | Origen | Song | Scholia in Canticum Canticorum | `first1k` |
| `tlg2042.tlg009` | `origen` | Origen | Jer | Homiliae in Jeremiam (1–11) | `first1k` |
| `tlg2042.tlg021` | `origen` | Origen | Jer | Homiliae in Jeremiam (12–20) | `first1k` |
| `tlg2042.tlg010` | `origen` | Origen | Jer | Fragmenta in Jeremiam (in Catenis) | `first1k` |
| `tlg2042.tlg084` | `origen` | Origen | Jer | Fragmenta in Jeremiam (e Philocalia) | `first1k` |
| `tlg2042.tlg011` | `origen` | Origen | Lam | Fragmenta in Lamentationes (in Catenis de Prophetis) | `first1k` |
| `tlg2042.tlg012` | `origen` | Origen | Lam | Fragmentum in Lamentationes (in Catenis de Octateucho) | `first1k` |
| `tlg2042.tlg061` | `origen` | Origen | Ezek | Fragmenta ex commentariis in Ezechielem | `first1k` |
| `tlg4090.tlg001` | `patristic` | Cyril of Alexandria | Hos, Joel, Amos, Obad, Jonah, Mic, Nah, Hab, Zeph, Hag, Zech, Mal | Commentarius in XII Prophetas Minores (Hosea–Malachi) | `first1k` |
| `tlg2959.tlg007` | `patristic` | Methodius of Olympus | Job | Fragmenta in Job (in Catenis) | `first1k` |
| `tlg2018.tlg011` | `patristic` | Eusebius of Caesarea | Gen, Exod, Num, Deut, Josh, Judg, 1Kgdms, 2Kgdms, 3Kgdms, 4Kgdms | Onomasticon (Biblical Place-Names Gazetteer) | `first1k` |
| `tlg2018.tlg023` | `patristic` | Eusebius of Caesarea | Ps, Isa, Jer, Ezek, Dan-Th, Hos, Mic, Zech | Eclogae Propheticae (Generalis Elementaria Introductio) | `first1k` |
| `tlg0555.tlg005` | `patristic` | Clement of Alexandria | Gen, Ps, Isa, Matt, Luke | Eclogae Propheticae | `first1k` |
| `tlg1750.tlg003` | `patristic` | Vitae Prophetarum (Hesychius Scholia) | Isa, Jer, Ezek, Dan-Th, Hos, Joel, Amos, Obad, Jonah, Mic, Nah, Hab, Zeph, Hag, Zech, Mal | De Prophetarum Vita et Obitu (with Scholia of Hesychius) | `first1k` |
| `PG071` | `patrologia` | Cyril of Alexandria | Hos, Joel, Amos, Obad, Jonah, Mic, Nah, Hab, Zeph, Hag, Zech, Mal | PG 71: Commentaries on the Twelve Minor Prophets (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG073` | `patrologia` | Cyril of Alexandria | John | PG 73: Commentary on the Gospel of John (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG087_1` | `patrologia` | Procopius of Gaza | Gen, Exod, Lev, Num, Deut, Josh, Judg, Ruth | PG 87.1: Old Testament Commentaries & Octateuch Catenae (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG101` | `patrologia` | Photius of Constantinople | Matt, Mark, Luke, John, Acts, Rom, 1Cor, 2Cor, Gal, Eph, Phil, Col, Heb | PG 101: Quaestiones Amphilochianae & Commentary on the NT (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG118` | `patrologia` | Oecumenius (Pseudo-Oecumenius) | Acts, Rom, 1Cor, 2Cor, Gal, Eph, Phil, Col, 1Thess, 2Thess, 1Tim, 2Tim, Titus, Phlm, Heb, Jas, 1Pet, 2Pet, 1John, 2John, 3John, Jude | PG 118: Commentaries on Acts, Pauline Epistles & Catholic Epistles (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG123` | `patrologia` | Theophylact of Bulgaria | Matt, Mark, Luke, John | PG 123: Enarratio in Evangelia Matthaei, Marci, Lucae & Joannis (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG124` | `patrologia` | Theophylact of Bulgaria | John, Rom, 1Cor, 2Cor, Gal, Eph, Phil, Col | PG 124: Commentarius in Joannem (cont.) & Pauline Epistles (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG125` | `patrologia` | Theophylact of Bulgaria | 1Thess, 2Thess, 1Tim, 2Tim, Titus, Phlm, Heb, 1Pet, 2Pet | PG 125: Commentaries on Pauline Epistles (cont.) & 1–2 Peter (CGPG OCR) | `patrologia-graeca-corpus` |
| `PG126` | `patrologia` | Theophylact of Bulgaria | Acts, Jas, 1John, 2John, 3John, Jude, Hos, Hab, Jonah, Nah, Mic | PG 126: Commentaries on NT & Minor Prophets (CGPG OCR) | `patrologia-graeca-corpus` |
| `ogc002040` | `chrysostom` | John Chrysostom | Gen | In Genesim (Homiliae 1–67) | `chrysostom-corpus` |
| `ogc002041` | `chrysostom` | John Chrysostom | Gen | In Genesim (Sermones 1–9) | `chrysostom-corpus` |
| `ogc001958` | `chrysostom` | John Chrysostom | Job | Commentarius in Job | `chrysostom-corpus` |
| `ogc002009` | `chrysostom` | John Chrysostom | Ps | Expositiones in Psalmos | `chrysostom-corpus` |
| `ogc002012` | `chrysostom` | John Chrysostom | Prov | Fragmenta in Proverbia (in Catenis) | `chrysostom-corpus` |
| `ogc002057` | `chrysostom` | John Chrysostom | Isa | In Isaiam | `chrysostom-corpus` |
| `ogc002011` | `chrysostom` | John Chrysostom | Jer | Fragmenta in Jeremiam (in Catenis) | `chrysostom-corpus` |
| `ogc002082` | `chrysostom` | John Chrysostom | Dan-OG, Dan-Th | Interpretatio in Danielem Prophetam [Sp.] | `chrysostom-corpus` |
| `ogc002060` | `chrysostom` | John Chrysostom | Matt | In Matthaeum (Homiliae 1–90) | `chrysostom-corpus` |
| `ogc002058` | `chrysostom` | John Chrysostom | John | In Joannem (Homiliae 1–88) | `chrysostom-corpus` |
| `ogc002017` | `chrysostom` | John Chrysostom | Acts | In Acta Apostolorum (Homiliae 1–55) | `chrysostom-corpus` |
| `ogc002065` | `chrysostom` | John Chrysostom | Acts | In Principium Actorum (Homiliae 1–4) | `chrysostom-corpus` |
| `ogc002031` | `chrysostom` | John Chrysostom | Rom | In Epistulam ad Romanos (Homiliae 1–32) | `chrysostom-corpus` |
| `ogc002033` | `chrysostom` | John Chrysostom | 1Cor | In Epistulam I ad Corinthios (Homiliae 1–44) | `chrysostom-corpus` |
| `ogc002036` | `chrysostom` | John Chrysostom | 2Cor | In Epistulam II ad Corinthios (Homiliae 1–30) | `chrysostom-corpus` |
| `ogc002027` | `chrysostom` | John Chrysostom | Gal | In Epistulam ad Galatas Commentarius | `chrysostom-corpus` |
| `ogc002026` | `chrysostom` | John Chrysostom | Eph | In Epistulam ad Ephesios (Homiliae 1–24) | `chrysostom-corpus` |
| `ogc002030` | `chrysostom` | John Chrysostom | Phil | In Epistulam ad Philippenses (Homiliae 1–15) | `chrysostom-corpus` |
| `ogc002025` | `chrysostom` | John Chrysostom | Col | In Epistulam ad Colossenses (Homiliae 1–12) | `chrysostom-corpus` |
| `ogc002034` | `chrysostom` | John Chrysostom | 1Thess | In Epistulam I ad Thessalonicenses (Homiliae 1–11) | `chrysostom-corpus` |
| `ogc002037` | `chrysostom` | John Chrysostom | 2Thess | In Epistulam II ad Thessalonicenses (Homiliae 1–5) | `chrysostom-corpus` |
| `ogc002035` | `chrysostom` | John Chrysostom | 1Tim | In Epistulam I ad Timotheum (Homiliae 1–18) | `chrysostom-corpus` |
| `ogc002038` | `chrysostom` | John Chrysostom | 2Tim | In Epistulam II ad Timotheum (Homiliae 1–10) | `chrysostom-corpus` |
| `ogc002032` | `chrysostom` | John Chrysostom | Titus | In Epistulam ad Titum (Homiliae 1–6) | `chrysostom-corpus` |
| `ogc002029` | `chrysostom` | John Chrysostom | Phlm | In Epistulam ad Philemonem (Homiliae 1–3) | `chrysostom-corpus` |
| `ogc002028` | `chrysostom` | John Chrysostom | Heb | In Epistulam ad Hebraeos (Homiliae 1–34) | `chrysostom-corpus` |
