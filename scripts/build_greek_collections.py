"""Build 8 categorized, work-indexed Ancient, Classical, Patristic & Byzantine Greek release assets.

Sources all ~3,844 open-licensed Greek literary, classical, patristic, and Byzantine
works (~64.3M tokens across 1,400+ authors, Homer through the 15th c. / Fall of
Constantinople) from a commit-pinned snapshot of ``open-greek/open-greek-corpus``
(CC BY-SA 4.0 aggregate; component texts verified Public Domain, CC BY 4.0, or
CC BY-SA 4.0 — zero CC BY-NC or proprietary TLG editions).

Excludes works already carried by dedicated pyaegean bundles:
- New Testament (``tlg0031`` — carried by ``nt-corpus`` / ``nt-editions``)
- Septuagint (``tlg0527`` — carried by ``lxx-corpus`` v2, all 56 books incl. Ecclesiastes)
- Byzantine vernacular (``byzantine_vernacular`` — carried by ``byzantine-corpus``)

Produces 8 deterministic, gzip-compressed (``mtime=0``), work-indexed JSON bundles:
1. ``chrysostom-corpus.json.gz``           (John Chrysostom & Ps.-Chrysostom)
2. ``church-fathers-early-corpus.json.gz`` (Pre-Nicene & 4th c. Nicene Fathers)
3. ``church-fathers-late-corpus.json.gz``  (Post-Nicene, Eastern Fathers, Saints & Councils)
4. ``classical-greek-corpus.json.gz``      (Archaic & Classical Greek, 8th–4th c. BCE)
5. ``hellenistic-greek-corpus.json.gz``    (Hellenistic, Jewish-Greek & DFHG Fragments)
6. ``imperial-greek-corpus.json.gz``       (Imperial Greek Literature, Philosophy & Medicine)
7. ``late-antique-greek-corpus.json.gz``   (Late Antique Philosophy, Rhetoric & Scholia)
8. ``byzantine-lit-corpus.json.gz``        (Byzantine History, Literature & Lexicography)

Also writes a compact (~110 KB) offline discovery index to
``src/aegean/data/bundled/greek/collections_index.json.gz`` when ``--index-out`` is given.

Usage:
    python scripts/build_greek_collections.py /tmp/ogc-src --out-dir /tmp/greek-assets \\
        --index-out src/aegean/data/bundled/greek/collections_index.json.gz
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OGC_REPO = "open-greek/open-greek-corpus"
OGC_RELEASE = "corpus-2026-11-26"
OGC_COMMIT = "ea39ee6024e1a68b4dfd285f06c5863523fcb686"

LICENSE_SUMMARY = (
    "CC BY-SA 4.0 / CC BY 4.0 / Public Domain (Open Greek Corpus aggregate; "
    "per-work license, edition, and OCR status recorded on every work; "
    "zero NonCommercial or proprietary texts)"
)
ATTRIBUTION_SUMMARY = (
    "Open Greek Corpus (https://github.com/open-greek/open-greek-corpus, release "
    f"{OGC_RELEASE}), aggregating verified open editions from Open Greek and Latin "
    "First1KGreek (CC BY-SA 4.0), Perseus canonical-greekLit (CC BY-SA 4.0), "
    "Patristic Text Archive / BBAW (CC BY / CC BY-SA 4.0), Calfa-GREgORI Patrologia "
    "Graeca (CC BY 4.0), DFHG Leipzig (CC BY-SA 4.0), Galenus Verbatim (CC BY-SA 4.0), "
    "SAWS (CC BY 4.0), GLAUx (CC BY-SA 4.0), Greek Wikisource (CC BY-SA 4.0), and "
    "public-domain OCR editions (PD / CC BY 4.0)."
)


@dataclass(frozen=True)
class CollectionMeta:
    id: str
    asset_file: str
    title: str
    category: str
    period: str
    description: str


COLLECTIONS: tuple[CollectionMeta, ...] = (
    CollectionMeta(
        id="chrysostom",
        asset_file="chrysostom-corpus.json.gz",
        title="John Chrysostom Complete Open Greek Corpus",
        category="patristics",
        period="4th–5th c. CE",
        description=(
            "John Chrysostom (& Pseudo-Chrysostom): Homilies on Matthew (1–90), Genesis (1–67), "
            "John (1–88), Psalms, Romans, 1–2 Corinthians, Acts, Galatians, Hebrews, Ephesians, "
            "Philippians, Colossians, 1–2 Timothy, Philemon, On the Statues, On the Priesthood, "
            "Letters to Olympias, Catecheses, and treatises."
        ),
    ),
    CollectionMeta(
        id="church-fathers-early",
        asset_file="church-fathers-early-corpus.json.gz",
        title="Early & Nicene Church Fathers Greek Corpus (2nd–4th c. CE)",
        category="patristics",
        period="2nd–4th c. CE",
        description=(
            "Pre-Nicene and 4th-century Nicene Greek Fathers: Justin Martyr, Irenaeus, Clement of "
            "Alexandria, Hippolytus, Origen, Eusebius of Caesarea, Athanasius of Alexandria, "
            "Basil of Caesarea, Gregory of Nyssa, Gregory of Nazianzus, Epiphanius, Methodius, "
            "Macarius, and early Christian acts and apologies."
        ),
    ),
    CollectionMeta(
        id="church-fathers-late",
        asset_file="church-fathers-late-corpus.json.gz",
        title="Post-Nicene, Eastern Fathers & Saints Greek Corpus (5th–15th c. CE)",
        category="patristics",
        period="5th–15th c. CE",
        description=(
            "Post-Nicene and Byzantine Church Fathers, Saints, and Councils: Cyril of Alexandria, "
            "Theodoret of Cyrrhus, Severian of Gabala, Socrates, Sozomen, Pseudo-Dionysius, "
            "Maximus the Confessor, John of Damascus, Romanos the Melodist, NT Catenae, "
            "Oecumenius, Theophylact of Ochrid, Symeon of Thessalonica, Gregory Palamas, "
            "Philotheus of Constantinople, and Acts of the Council of Ephesus."
        ),
    ),
    CollectionMeta(
        id="classical-greek",
        asset_file="classical-greek-corpus.json.gz",
        title="Archaic & Classical Greek Literature (8th–4th c. BCE)",
        category="classical",
        period="8th–4th c. BCE",
        description=(
            "Archaic and Classical Greek canon: Homer, Hesiod, Homeric Hymns, Lyric Poets, "
            "Aeschylus, Sophocles, Euripides, Aristophanes, Herodotus, Thucydides, Xenophon, "
            "Plato, Aristotle & Corpus Aristotelicum, Attic Orators (Demosthenes, Isocrates, "
            "Lysias, Aeschines), Hippocratic Corpus, Theophrastus, and Presocratics."
        ),
    ),
    CollectionMeta(
        id="hellenistic-greek",
        asset_file="hellenistic-greek-corpus.json.gz",
        title="Hellenistic & Jewish-Greek Literature & Fragmentary Historians (3rd c. BCE–1st c. CE)",
        category="classical",
        period="3rd c. BCE–1st c. CE",
        description=(
            "Hellenistic and early Roman-era Greek works: Polybius, Philo of Alexandria, "
            "Diodorus Siculus, Strabo, Dionysius of Halicarnassus, Euclid, Archimedes, "
            "Apollonius of Rhodes, Callimachus, Theocritus, Menander, Philodemus, Chrysippus, "
            "and 528 works from Digital Fragmenta Historicorum Graecorum (DFHG)."
        ),
    ),
    CollectionMeta(
        id="imperial-greek",
        asset_file="imperial-greek-corpus.json.gz",
        title="Imperial Greek Literature, Philosophy & Medicine (1st–3rd c. CE)",
        category="classical",
        period="1st–3rd c. CE",
        description=(
            "Imperial-era Greek literature, science, and philosophy: Galen & Pseudo-Galen, "
            "Plutarch, Alexander of Aphrodisias, Flavius Josephus, Cassius Dio, Lucian, "
            "Pausanias, Appian, Arrian, Athenaeus, Aelius Aristides, Herodian, Dio Chrysostom, "
            "Epictetus, Marcus Aurelius, Sextus Empiricus, Diogenes Laertius, Plotinus, Porphyry, "
            "Greek Anthology, and Greek Novels."
        ),
    ),
    CollectionMeta(
        id="late-antique-greek",
        asset_file="late-antique-greek-corpus.json.gz",
        title="Late Antique Philosophy, Rhetoric & Classical Scholia (4th–6th c. CE)",
        category="classical",
        period="4th–6th c. CE",
        description=(
            "Late Antique Neoplatonic commentaries, rhetoric, and ancient scholia: John Philoponus, "
            "Simplicius, Proclus, Ammonius, Damascius, Olympiodorus, Iamblichus, Libanius, Julian, "
            "Themistius, Stobaeus, Oribasius, Nonnus, Quintus Smyrnaeus, and ancient Scholia on "
            "Homer, Euripides, Aristophanes, Plato, Hesiod, Pindar, Aeschylus, and Demosthenes."
        ),
    ),
    CollectionMeta(
        id="byzantine-lit",
        asset_file="byzantine-lit-corpus.json.gz",
        title="Byzantine History, Literature & Lexicography (6th–15th c. CE)",
        category="byzantine",
        period="6th–15th c. CE",
        description=(
            "Byzantine Greek history, scholarship, and lexicography through the Fall of "
            "Constantinople: Procopius of Caesarea, Agathias, Theophylact Simocatta, Chronicon "
            "Paschale, Photius, Constantine VII Porphyrogenitus, Leo VI, Suda Lexicon, "
            "Etymologicum Gudianum, Geoponica, Michael Psellos, Anna Komnene (Alexiad), "
            "Eustathius of Thessalonica, John Zonaras, Niketas Choniates, George Pachymeres, "
            "Nicephorus Gregoras, John VI Kantakouzenos, George Sphrantzes, and Chalkokondyles."
        ),
    ),
)

COLLECTION_BY_ID: dict[str, CollectionMeta] = {c.id: c for c in COLLECTIONS}

_CHRYSOSTOM_AUTHORS = frozenset(
    {
        "joannes chrysostomus",
        "anonymus-pseudo-john-chrysostom",
        "anonymus-pseudo-john-chrysostom-pseudo-basil-of-caesarea",
    }
)

# Verified author -> collection overrides so major classical, patristic, and Byzantine
# figures are never misplaced by ambiguous Wikidata bio terms or epitome dates.
_FORCE_COLLECTION: dict[str, str] = {
    # Classical (8th-4th c. BCE)
    "homerus": "classical-greek",
    "hymni homerici": "classical-greek",
    "hesiodus": "classical-greek",
    "plato": "classical-greek",
    "aristoteles et corpus aristotelicum": "classical-greek",
    "hippocrates et corpus hippocraticum": "classical-greek",
    "herodotus": "classical-greek",
    "thucydides": "classical-greek",
    "xenophon": "classical-greek",
    "xenophanes": "classical-greek",
    "musaeus": "classical-greek",
    "demosthenes": "classical-greek",
    "aeschylus": "classical-greek",
    "sophocles": "classical-greek",
    "euripides": "classical-greek",
    "aristophanes": "classical-greek",
    "pindarus": "classical-greek",
    "theophrastus": "classical-greek",
    "theognis": "classical-greek",
    "isocrates": "classical-greek",
    "lysias": "classical-greek",
    "aeschines": "classical-greek",
    # Hellenistic & Jewish-Greek (3rd c. BCE-1st c. CE)
    "philo judaeus": "hellenistic-greek",
    "polybius": "hellenistic-greek",
    "diodorus siculus": "hellenistic-greek",
    "strabo": "hellenistic-greek",
    "dionysius halicarnassensis": "hellenistic-greek",
    "euclides": "hellenistic-greek",
    "archimedes": "hellenistic-greek",
    "apollonius rhodius": "hellenistic-greek",
    "callimachus": "hellenistic-greek",
    "theocritus": "hellenistic-greek",
    "menander": "hellenistic-greek",
    "philodemus": "hellenistic-greek",
    "chrysippus": "hellenistic-greek",
    "limenius": "hellenistic-greek",
    # Imperial Greek (1st-3rd c. CE)
    "galenus": "imperial-greek",
    "pseudo-galenus": "imperial-greek",
    "plutarchus": "imperial-greek",
    "pseudo-plutarchus": "imperial-greek",
    "flavius josephus": "imperial-greek",
    "cassius dio": "imperial-greek",
    "lucianus": "imperial-greek",
    "pausanias": "imperial-greek",
    "appianus": "imperial-greek",
    "arrianus": "imperial-greek",
    "athenaeus": "imperial-greek",
    "aelius aristides": "imperial-greek",
    "aelius herodianus et pseudo-herodianus": "imperial-greek",
    "dio chrysostomus": "imperial-greek",
    "diogenes laertius": "imperial-greek",
    "sextus empiricus": "imperial-greek",
    "alexander": "imperial-greek",
    "epictetus": "imperial-greek",
    "marcus aurelius antoninus": "imperial-greek",
    "plotinus": "imperial-greek",
    "porphyrius": "imperial-greek",
    "claudius ptolemaeus": "imperial-greek",
    "hermogenes": "imperial-greek",
    "achilles tatius": "imperial-greek",
    "antonius diogenes": "imperial-greek",
    "heliodorus": "imperial-greek",
    "longus": "imperial-greek",
    "chariton": "imperial-greek",
    "anthologia graeca": "imperial-greek",
    "apollonius dyscolus": "imperial-greek",
    "dionysius thrax": "imperial-greek",
    "hierocles": "imperial-greek",
    "adamantius judaeus": "imperial-greek",
    # Late Antique Philosophy, Rhetoric & Scholia (4th-6th c. CE)
    "proclus": "late-antique-greek",
    "simplicius": "late-antique-greek",
    "joannes philoponus": "late-antique-greek",
    "ammonius": "late-antique-greek",
    "ammonius (bracketed printed attribution)": "late-antique-greek",
    "damascius": "late-antique-greek",
    "olympiodorus": "late-antique-greek",
    "iamblichus": "late-antique-greek",
    "libanius": "late-antique-greek",
    "julianus imperator": "late-antique-greek",
    "themistius": "late-antique-greek",
    "joannes stobaeus anthologus": "late-antique-greek",
    "oribasius": "late-antique-greek",
    "nonnus": "late-antique-greek",
    "quintus smyrnaeus": "late-antique-greek",
    "aetius": "late-antique-greek",
    "paulus aegineta": "late-antique-greek",
    "stephanus byzantius": "late-antique-greek",
    "hesychius": "late-antique-greek",
    "timotheus": "late-antique-greek",
    # Early & Nicene Church Fathers (2nd-4th c. CE)
    "eusebius": "church-fathers-early",
    "eusebius-of-caesarea": "church-fathers-early",
    "eusebius-alexandrinus": "church-fathers-early",
    "origenes": "church-fathers-early",
    "origen": "church-fathers-early",
    "athanasius": "church-fathers-early",
    "athanasius-of-alexandria": "church-fathers-early",
    "ps-athanasius-of-alexandria": "church-fathers-early",
    "basilius": "church-fathers-early",
    "gregorius nyssenus": "church-fathers-early",
    "gregorius nazianzenus": "church-fathers-early",
    "clemens alexandrinus": "church-fathers-early",
    "clemens romanus et clementina": "church-fathers-early",
    "epiphanius": "church-fathers-early",
    "justinus martyr": "church-fathers-early",
    "pseudo-justinus martyr": "church-fathers-early",
    "irenaeus": "church-fathers-early",
    "seniores apud irenaeum": "church-fathers-early",
    "hippolytus": "church-fathers-early",
    "hippolytus-of-rome": "church-fathers-early",
    "ignatius": "church-fathers-early",
    "martyrium ignatii": "church-fathers-early",
    "polycarpus": "church-fathers-early",
    "melito": "church-fathers-early",
    "papias": "church-fathers-early",
    "quadratus-apologeta": "church-fathers-early",
    "pantaenus": "church-fathers-early",
    "hegesippus": "church-fathers-early",
    "hermias": "church-fathers-early",
    "serapion": "church-fathers-early",
    "claudius apollinarius": "church-fathers-early",
    "amphilochius": "church-fathers-early",
    "marcellus": "church-fathers-early",
    "marcellus-of-ancyra": "church-fathers-early",
    "methodius": "church-fathers-early",
    "didymus caecus": "church-fathers-early",
    "macarius": "church-fathers-early",
    "evagrius ponticus": "church-fathers-early",
    "tatianus": "church-fathers-early",
    "athenagoras": "church-fathers-early",
    "theophilus": "church-fathers-early",
    "apollinares": "church-fathers-early",
    "dokumente-zur-geschichte-des-arianischen-streites-athanasius-werke-iii": "church-fathers-early",
    "epistula ecclesiarum apud lugdunum et viennam": "church-fathers-early",
    "vitae prophetarum": "church-fathers-early",
    "acta justini et septem sodalium": "church-fathers-early",
    "acta barnabae": "church-fathers-early",
    # Post-Nicene, Eastern Fathers, Saints & Councils (5th-15th c. CE)
    "cyrillus": "church-fathers-late",
    "cyrill-of-alexandria": "church-fathers-late",
    "theodoretus": "church-fathers-late",
    "theodoret-of-cyrrhus": "church-fathers-late",
    "severianus": "church-fathers-late",
    "severian-of-gabala": "church-fathers-late",
    "catenae (novum testamentum)": "church-fathers-late",
    "catenae": "church-fathers-late",
    "theophylactus achridensis": "church-fathers-late",
    "oecumenius": "church-fathers-late",
    "joannes damascenus": "church-fathers-late",
    "maximus": "church-fathers-late",
    "pseudo-dionysius areopagita": "church-fathers-late",
    "dionysius areopagita": "church-fathers-late",
    "socrates scholasticus": "church-fathers-late",
    "sozomenus": "church-fathers-late",
    "sozomen": "church-fathers-late",
    "evagrius scholasticus": "church-fathers-late",
    "concilium ephesenum": "church-fathers-late",
    "gregorius-palamas": "church-fathers-late",
    "philotheus-constantinopolitanus": "church-fathers-late",
    "symeon thessalonicensis": "church-fathers-late",
    "symeon novus theologus": "church-fathers-late",
    "procopius gazaeus": "church-fathers-late",
    "romanus melodus": "church-fathers-late",
    "joannes climacus": "church-fathers-late",
    "nicephorus callistus xanthopulus": "church-fathers-late",
    "hesychius-of-jerusalem": "church-fathers-late",
    "isidorus pelusiota": "church-fathers-late",
    "palladius": "church-fathers-late",
    "theodorus studita": "church-fathers-late",
    "anastasius sinaita": "church-fathers-late",
    "andreas cretensis": "church-fathers-late",
    "sophronius": "church-fathers-late",
    "leontius": "church-fathers-late",
    "nilus": "church-fathers-late",
    "nicetas-heracleensis": "church-fathers-late",
    "nicetas-maroniensis": "church-fathers-late",
    "elias-cretensis": "church-fathers-late",
    "euthalius diaconus": "church-fathers-late",
    "tomus-synodalis-anni-1351": "church-fathers-late",
    "tomus-synodalis-contra-prochorum-cydonem": "church-fathers-late",
    "tomus-synodicus-contra-barlaam-et-acindynum": "church-fathers-late",
    "anonymi-in-acta-apostolorum": "church-fathers-late",
    "anonymi-de-essentia-et-operatione-dei": "church-fathers-late",
    "anonymus-author-of-vita-cononis": "church-fathers-late",
    "laudatio-sancti-demetrii": "church-fathers-late",
    "vita-basilii-iunioris": "church-fathers-late",
    "hilarion-monachus": "church-fathers-late",
    "job-monachus": "church-fathers-late",
    "josephus-ii-patriarcha": "church-fathers-late",
    "demetrius-cydones": "church-fathers-late",
    "theodorus-agallianus": "church-fathers-late",
    "esaias-cyprius": "church-fathers-late",
    # Byzantine History, Literature & Lexicography (6th-15th c. CE)
    "eustathius": "byzantine-lit",
    "procopius": "byzantine-lit",
    "agathias": "byzantine-lit",
    "theophylactus simocatta": "byzantine-lit",
    "photius": "byzantine-lit",
    "suda": "byzantine-lit",
    "etymologicum gudianum": "byzantine-lit",
    "geoponica": "byzantine-lit",
    "chronicon paschale": "byzantine-lit",
    "constantinus vii porphyrogenitus imperator": "byzantine-lit",
    "leo vi sapiens": "byzantine-lit",
    "basilius-i-macedo": "byzantine-lit",
    "michael psellus": "byzantine-lit",
    "anna comnena": "byzantine-lit",
    "joannes zonaras": "byzantine-lit",
    "pseudo-zonaras": "byzantine-lit",
    "nicetas choniates": "byzantine-lit",
    "georgius pachymeres": "byzantine-lit",
    "nicephorus gregoras": "byzantine-lit",
    "joannes vi cantacuzenus": "byzantine-lit",
    "georgius sphrantzes": "byzantine-lit",
    "laonicus chalcocondyles": "byzantine-lit",
    "michael glycas": "byzantine-lit",
    "georgius monachus": "byzantine-lit",
    "georgius cedrenus": "byzantine-lit",
    "joannes scylitzes": "byzantine-lit",
    "joannes antiochenus": "byzantine-lit",
    "eustratius": "byzantine-lit",
    "theophanes confessor": "byzantine-lit",
    "joannes malalas": "byzantine-lit",
    "joannes-doxopatres": "byzantine-lit",
    "joannes-siceliota": "byzantine-lit",
    "georgius codinus": "byzantine-lit",
    "ducas": "byzantine-lit",
    "joel": "byzantine-lit",
    "patria constantinopoleos": "byzantine-lit",
    "maximus-planudes": "byzantine-lit",
    "joannes tzetzes": "byzantine-lit",
    "michael attaleiates": "byzantine-lit",
    "georgius acropolites": "byzantine-lit",
    "joannes cinnamus": "byzantine-lit",
    "joannes argyropulus": "byzantine-lit",
    "pseudo-symeon": "byzantine-lit",
    "hierocles-grammaticus": "byzantine-lit",
}

_PATRISTIC_BIO_TERMS = (
    "church father",
    "christian theologian",
    "christian bishop",
    "christian apologist",
    "christian writer",
    "christian author",
    "church historian",
    "patriarch",
    "archbishop",
    "heresiologist",
    "hagiographer",
    "hymnographer",
    "christian martyr",
    "christian saint",
    "desert father",
    "monk",
    "abbot",
    "presbyter",
    "bishop of",
)


def _derive_year(
    row: dict[str, str],
    authors: dict[str, Any],
    dating: dict[str, Any],
) -> tuple[int | None, str]:
    tlg = row.get("tlg", "")
    tlg_a = tlg.split(".")[0] if tlg else ""
    ainfo = authors.get(tlg_a, {})
    yr: int | None = ainfo.get("death") if ainfo.get("death") is not None else ainfo.get("birth")
    oga = dating.get(tlg) or dating.get(row.get("slug", "").lower()) or {}
    oga_era = str(oga.get("era") or "").lower()
    if yr is None and isinstance(oga.get("century"), int):
        c = int(oga["century"])
        yr = (c * 100 - 50) if c > 0 else (c * 100 + 50)
    return yr, oga_era


def _period_label(collection_id: str, yr: int | None) -> str:
    if yr is not None:
        if yr < 0:
            cent = (-yr - 1) // 100 + 1
            return f"{cent}th c. BCE" if cent >= 4 else f"{cent}{'st' if cent == 1 else 'nd' if cent == 2 else 'rd'} c. BCE"
        cent = max(1, (yr - 1) // 100 + 1)
        suf = "st" if cent == 1 else "nd" if cent == 2 else "rd" if cent == 3 else "th"
        return f"{cent}{suf} c. CE"
    return COLLECTION_BY_ID[collection_id].period


def classify_work(
    row: dict[str, str],
    authors: dict[str, Any],
    bios: dict[str, Any],
    dating: dict[str, Any],
) -> str | None:
    """Return one of the 8 collection IDs, or ``None`` if covered by dedicated corpora."""
    auth_l = row["author"].strip().lower()
    tlg = row.get("tlg", "")
    src = row.get("source", "")

    if tlg.startswith("tlg0031") or auth_l == "novum testamentum":
        return None
    if tlg.startswith("tlg0527") or "septuagint" in auth_l:
        return None
    if src == "byzantine_vernacular":
        return None

    if auth_l in _CHRYSOSTOM_AUTHORS:
        return "chrysostom"
    if auth_l in _FORCE_COLLECTION:
        return _FORCE_COLLECTION[auth_l]

    yr, oga_era = _derive_year(row, authors, dating)
    tlg_a = tlg.split(".")[0] if tlg else ""
    ainfo = authors.get(tlg_a, {})
    qid = ainfo.get("wikidata") or row.get("wikidata", "")
    bio_l = str(bios.get(qid, {}).get("bio", "") if qid else "").lower()

    if auth_l.startswith(("scholia ", "commentaria in ", "anonymi in ")):
        return "late-antique-greek"

    if src == "pta":
        return "church-fathers-late" if (yr is not None and yr > 410) else "church-fathers-early"

    if any(
        k in auth_l
        for k in (
            "acta ",
            "martyrium",
            "apocalypsis",
            "testamentum",
            "evangelium",
            "protevangelium",
            "didache",
            "barnabas",
            "hermas",
            "polycarp",
            "diognet",
            "concilium",
            "synod",
        )
    ):
        return "church-fathers-early" if (yr is None or yr <= 410) else "church-fathers-late"

    if (yr is None or yr >= 50) and any(k in bio_l for k in _PATRISTIC_BIO_TERMS):
        if "emperor" not in bio_l and "grammarian" not in bio_l and "philologist" not in bio_l:
            return "church-fathers-late" if (yr is not None and yr > 410) else "church-fathers-early"

    if src in ("byzantium_gr", "cgpg") or oga_era == "byzantine" or "byzantine" in bio_l or (yr is not None and yr >= 550):
        return "byzantine-lit"

    if oga_era in ("archaic", "classical") or (yr is not None and yr <= -320):
        return "classical-greek"

    if src == "dfhg" or oga_era == "hellenistic" or (yr is not None and -320 < yr <= 50):
        return "hellenistic-greek"

    if oga_era in ("late-antique", "late_antique") or (yr is not None and yr >= 300):
        return "late-antique-greek"

    return "imperial-greek"


def _write_deterministic_gz(path: Path, payload: dict[str, Any], inner_name: str) -> str:
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        with gzip.GzipFile(filename=inner_name, mode="wb", fileobj=fh, compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_all(ogc_dir: Path, out_dir: Path, index_out: Path | None = None) -> dict[str, Any]:
    data_dir = ogc_dir / "data"
    corpus_dir = data_dir / "corpus"
    with open(data_dir / "corpus_catalog.tsv", encoding="utf-8") as fh:
        catalog_rows = list(csv.DictReader(fh, delimiter="\t"))

    authors = json.loads((data_dir / "author_authority.json").read_text(encoding="utf-8"))
    bios = json.loads((data_dir / "author_bios.json").read_text(encoding="utf-8"))
    dating = json.loads((data_dir / "oga_dating.json").read_text(encoding="utf-8")).get("works", {})

    grouped: dict[str, list[dict[str, str]]] = {c.id: [] for c in COLLECTIONS}
    for row in catalog_rows:
        cid = classify_work(row, authors, bios, dating)
        if cid is not None:
            grouped[cid].append(row)

    summary_manifest: dict[str, Any] = {}
    index_collections: dict[str, Any] = {}
    index_works: list[list[Any]] = []
    grand_works = 0
    grand_tokens = 0
    grand_authors: set[str] = set()

    for meta in COLLECTIONS:
        rows = sorted(grouped[meta.id], key=lambda r: r["work_id"])
        works_payload: dict[str, Any] = {}
        col_authors: set[str] = set()
        col_passages = 0
        col_tokens = 0

        for row in rows:
            wid = row["work_id"]
            slug = row["slug"]
            jsonl_path = corpus_dir / f"{slug}.jsonl"
            if not jsonl_path.is_file():
                raise FileNotFoundError(f"missing OGC work file: {jsonl_path}")

            passages: list[list[str]] = []
            with open(jsonl_path, encoding="utf-8") as jfh:
                for line in jfh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    txt = unicodedata.normalize("NFC", str(rec.get("text", "")).strip())
                    if not txt:
                        continue
                    locus = str(rec.get("locus", "") or "")
                    passages.append([locus, txt])

            if not passages:
                continue

            yr, _ = _derive_year(row, authors, dating)
            period = _period_label(meta.id, yr)
            tok_count = int(row.get("tokens") or 0) or sum(len(p[1].split()) for p in passages)
            author = row["author"].strip()
            title = row["title"].strip()
            tlg = row.get("tlg", "").strip()
            cts_urn = row.get("cts_urn", "").strip()
            edition = row.get("edition", "").strip()
            source = row.get("source", "").strip()
            lic = row.get("license", "").strip() or "CC-BY-SA-4.0"
            correction = row.get("correction", "").strip() or "not-ocr"

            col_authors.add(author)
            grand_authors.add(author)
            col_passages += len(passages)
            col_tokens += tok_count

            works_payload[wid] = {
                "_info": {
                    "work_id": wid,
                    "slug": slug,
                    "author": author,
                    "title": title,
                    "tlg": tlg,
                    "cts_urn": cts_urn,
                    "period": period,
                    "edition": edition,
                    "source": source,
                    "license": lic,
                    "correction": correction,
                    "tokens": tok_count,
                    "passages": len(passages),
                },
                "passages": passages,
            }
            index_works.append(
                [wid, meta.id, author, title, tlg, tok_count, source, lic, correction, period]
            )

        payload = {
            "_meta": {
                "format": "aegean-greek-collection/1",
                "collection_id": meta.id,
                "title": meta.title,
                "category": meta.category,
                "period": meta.period,
                "description": meta.description,
                "source_repo": f"https://github.com/{OGC_REPO}",
                "source_release": OGC_RELEASE,
                "source_commit": OGC_COMMIT,
                "license": LICENSE_SUMMARY,
                "attribution": ATTRIBUTION_SUMMARY,
                "works_count": len(works_payload),
                "authors_count": len(col_authors),
                "passages_count": col_passages,
                "tokens_count": col_tokens,
            },
            "works": works_payload,
        }

        out_path = out_dir / meta.asset_file
        inner_name = meta.asset_file.removesuffix(".gz")
        sha = _write_deterministic_gz(out_path, payload, inner_name)
        size_bytes = out_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        grand_works += len(works_payload)
        grand_tokens += col_tokens

        summary_manifest[meta.id] = {
            "asset_file": meta.asset_file,
            "tag": f"{meta.id}-corpus-v1",
            "title": meta.title,
            "category": meta.category,
            "works": len(works_payload),
            "authors": len(col_authors),
            "passages": col_passages,
            "tokens": col_tokens,
            "bytes": size_bytes,
            "sha256": sha,
        }
        index_collections[meta.id] = {
            "title": meta.title,
            "category": meta.category,
            "period": meta.period,
            "works": len(works_payload),
            "authors": len(col_authors),
            "tokens": col_tokens,
        }
        print(
            f"  {meta.id:22s}: {len(works_payload):4d} works | {len(col_authors):3d} authors | "
            f"{col_tokens:>10,d} tok | {size_mb:5.2f} MB | sha256={sha[:12]}..."
        )

    if index_out is not None:
        index_works.sort(key=lambda r: r[0])
        index_payload = {
            "_meta": {
                "format": "aegean-greek-collections-index/1",
                "source_repo": f"https://github.com/{OGC_REPO}",
                "source_release": OGC_RELEASE,
                "source_commit": OGC_COMMIT,
                "works_count": grand_works,
                "authors_count": len(grand_authors),
                "tokens_count": grand_tokens,
            },
            "collections": index_collections,
            "works": index_works,
        }
        idx_sha = _write_deterministic_gz(index_out, index_payload, "collections_index.json")
        idx_kb = index_out.stat().st_size / 1024.0
        print(
            f"Wrote offline index {index_out} ({grand_works} works, {len(grand_authors)} authors, "
            f"{idx_kb:.1f} KB, sha256={idx_sha[:12]}...)"
        )

    manifest_path = out_dir / "greek-collections-manifest.json"
    manifest_path.write_text(
        json.dumps(summary_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"TOTAL: {grand_works:,d} works, {len(grand_authors):,d} authors, {grand_tokens:,d} tokens")
    return summary_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ogc_dir", type=Path, help="Path to extracted open-greek-corpus directory")
    parser.add_argument("--out-dir", type=Path, default=Path("dist-greek-collections"))
    parser.add_argument("--index-out", type=Path, default=None)
    args = parser.parse_args()
    build_all(args.ogc_dir, args.out_dir, args.index_out)


if __name__ == "__main__":
    main()
