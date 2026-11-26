"""Declarative corpus catalog — single source of truth for registered corpora.

Every built-in and fetch-on-demand corpus registered with ``aegean.load()`` is
described once here. The TUI corpus browser (``aegean.tui.data``), the unified
Library Manager (``aegean.library``), the CLI fetch-hint table
(``aegean.cli._data``), and the JSON corpus loaders (``aegean.scripts.greek``)
all derive their metadata from this module so adding a new corpus never drifts
across surfaces.

Zero non-stdlib dependencies; safe to import during package startup.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CORPORA",
    "CORPUS_BY_ASSET",
    "CORPUS_BY_ID",
    "CorpusSpec",
    "UNDECIPHERED_IDS",
    "cli_fetch_hints",
    "make_json_corpus_loader",
    "tui_asset_map",
    "tui_blurbs",
    "tui_browsable_ids",
]


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    """Declarative metadata for one registered ``aegean.load(id)`` corpus."""

    id: str
    script_id: str
    title: str
    blurb: str
    description: str
    bundled: bool
    asset_name: str | None = None
    category: str = "corpus"
    tags: tuple[str, ...] = ("corpus",)
    aliases: tuple[str, ...] = ()
    size_hint: str = ""
    license: str = ""
    tui_browsable: bool = True
    undeciphered: bool = False
    fetch_hint: str | None = None


# Canonical presentation order: bundled corpora first, then Biblical/Patristic,
# Aegean, Epigraphy/Papyri, and Literary/Scholia corpora.
CORPORA: tuple[CorpusSpec, ...] = (
    # ── Bundled offline corpora (5) ──────────────────────────────────────────
    CorpusSpec(
        id="lineara",
        script_id="lineara",
        title="Linear A Corpus (GORILA)",
        blurb="Linear A inscriptions (undeciphered)",
        description="1,721 Linear A inscriptions (bundled offline).",
        bundled=True,
        license="Apache-2.0 / public academic transcriptions",
        aliases=("linear-a", "la"),
        undeciphered=True,
    ),
    CorpusSpec(
        id="linearb",
        script_id="linearb",
        title="Linear B Sample Tablets",
        blurb="Linear B sample tablets (Mycenaean Greek)",
        description="18 Mycenaean Greek Linear B sample tablets (bundled offline).",
        bundled=True,
        license="Apache-2.0 / public academic transcriptions",
        aliases=("linear-b", "lb"),
    ),
    CorpusSpec(
        id="cypriot",
        script_id="cypriot",
        title="Cypriot Syllabary Corpus",
        blurb="Cypriot syllabary texts (Greek)",
        description="149 Classical Cypriot Greek syllabic inscriptions (bundled offline).",
        bundled=True,
        license="Apache-2.0 / public academic transcriptions",
        aliases=("cypriot-syllabary",),
    ),
    CorpusSpec(
        id="cyprominoan",
        script_id="cyprominoan",
        title="Cypro-Minoan Corpus",
        blurb="Cypro-Minoan signs (undeciphered)",
        description="2 Cypro-Minoan sample inscriptions (bundled offline).",
        bundled=True,
        license="Apache-2.0 / public academic transcriptions",
        aliases=("cypro-minoan", "cm"),
        undeciphered=True,
    ),
    CorpusSpec(
        id="greek",
        script_id="greek",
        title="Ancient Greek Sample Texts",
        blurb="alphabetic Greek sample texts",
        description="5 Ancient Greek sample passages (bundled offline).",
        bundled=True,
        license="Apache-2.0 / public domain texts",
        aliases=("greek-sample",),
    ),
    # ── Fetch-on-demand Biblical & Patristic corpora ─────────────────────────
    CorpusSpec(
        id="nt",
        script_id="greek",
        title="Greek New Testament (Nestle 1904, 27 books)",
        blurb="Greek New Testament (Nestle 1904)",
        description="Full 27-book Nestle 1904 Greek NT with gold lemma, Robinson morphology, and Strong's.",
        bundled=False,
        asset_name="nt-corpus",
        category="bible",
        tags=("bible", "corpus"),
        aliases=("nt", "nestle1904", "gnt", "new-testament"),
        size_hint="~18 MB",
        fetch_hint="load it:  aegean info nt",
    ),
    CorpusSpec(
        id="lxx",
        script_id="greek",
        title="Septuagint / LXX (Swete + Ecclesiastes, 56 books)",
        blurb="Greek Septuagint (Swete + Ecclesiastes, 56 books)",
        description="All 56 Greek Septuagint (LXX) books (29,470 verses, NFC-normalized; Swete 1887–1894 + Wikisource Ecclesiastes).",
        bundled=False,
        asset_name="lxx-corpus",
        category="bible",
        tags=("bible", "corpus"),
        aliases=("lxx", "septuagint", "swete", "ot"),
        size_hint="~1.7 MB",
        fetch_hint="read it:  aegean bible read Gen 1:1-5",
    ),
    CorpusSpec(
        id="apostolic-fathers",
        script_id="greek",
        title="Open Apostolic Fathers (15 hand-corrected Greek works)",
        blurb="Open Apostolic Fathers (15 early Christian texts)",
        description="15 early Christian Greek works (1–2 Clement, Ignatius, Polycarp, Didache, Barnabas, Hermas, Diognetus).",
        bundled=False,
        asset_name="apostolic-fathers-corpus",
        category="patristics",
        tags=("patristics", "bible", "corpus", "commentary"),
        aliases=("apostolic-fathers", "af", "didache", "clement", "ignatius"),
        size_hint="~1.0 MB",
        fetch_hint="load it:  aegean info apostolic-fathers",
    ),
    CorpusSpec(
        id="pseudepigrapha",
        script_id="greek",
        title="Greek Old Testament Pseudepigrapha (44 OCP Second Temple works)",
        blurb="Greek Old Testament Pseudepigrapha (44 OCP works)",
        description="44 Greek Second Temple / OT Pseudepigrapha works (1 Enoch, Psalms of Solomon, Testaments, Sibylline Oracles, 3–4 Baruch, 3–4 Maccabees).",
        bundled=False,
        asset_name="pseudepigrapha-corpus",
        category="bible",
        tags=("bible", "corpus"),
        aliases=("pseudepigrapha", "ocp", "enoch", "sibylline"),
        size_hint="~2.7 MB",
        fetch_hint="load it:  aegean info pseudepigrapha",
    ),
    CorpusSpec(
        id="chrysostom",
        script_id="greek",
        title="John Chrysostom Complete Open Greek Corpus (155 works, 3.74M tokens)",
        blurb="John Chrysostom (& Ps.-Chrysostom) homilies, sermons, letters & commentaries",
        description="155 Greek works, homilies, sermons, treatises, letters, and biblical commentaries by John Chrysostom (and Ps.-Chrysostom; 3,738,372 tokens, PD/CC BY/CC BY-SA).",
        bundled=False,
        asset_name="chrysostom-corpus",
        category="patristics",
        tags=("patristics", "commentary", "bible", "corpus"),
        aliases=("chrysostom", "john-chrysostom", "ioannes-chrysostomus"),
        size_hint="~12.3 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "ἀγάπη" chrysostom',
    ),
    CorpusSpec(
        id="church-fathers-early",
        script_id="greek",
        title="Early & Nicene Church Fathers (432 works, 58 authors, 6.22M tokens)",
        blurb="Pre-Nicene & 4th c. Nicene Greek Church Fathers (2nd–4th c. CE)",
        description="432 Greek works by 58 Pre-Nicene and Nicene Church Fathers (Athanasius, Basil, Gregory of Nazianzus, Gregory of Nyssa, Eusebius, Origen, Clement of Alexandria, Justin, Irenaeus; 6,216,570 tokens).",
        bundled=False,
        asset_name="church-fathers-early-corpus",
        category="patristics",
        tags=("patristics", "corpus"),
        aliases=("church-fathers-early", "early-fathers", "nicene-fathers"),
        size_hint="~21.0 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "ὁμοούσιος" church-fathers-early',
    ),
    CorpusSpec(
        id="church-fathers-late",
        script_id="greek",
        title="Post-Nicene, Eastern Fathers, Saints & Councils (280 works, 38 authors, 7.96M tokens)",
        blurb="Post-Nicene & Byzantine Church Fathers, Saints & Councils (5th–15th c. CE)",
        description="280 Greek works by 38 Post-Nicene and Eastern Fathers, Saints, and Councils (Cyril of Alexandria, Theodoret, John of Damascus, Maximus the Confessor, Pseudo-Dionysius, Romanos, Photius, Symeon, Gregory Palamas; 7,962,722 tokens).",
        bundled=False,
        asset_name="church-fathers-late-corpus",
        category="patristics",
        tags=("patristics", "corpus"),
        aliases=("church-fathers-late", "late-fathers", "eastern-fathers", "byzantine-fathers"),
        size_hint="~26.7 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "θέωσις" church-fathers-late',
    ),
    CorpusSpec(
        id="patrologia",
        script_id="greek",
        title="Patrologia Graeca (33 CGPG volumes, 6.79M words; 9 commentary vols)",
        blurb="Patrologia Graeca (33 Migne PG volumes, OCR)",
        description="33 Migne Patrologia Graeca volumes (6,787,292 words, CGPG automated OCR), including 9 biblical commentary volumes.",
        bundled=False,
        asset_name="patrologia-graeca-corpus",
        category="patristics",
        tags=("patristics", "commentary", "bible", "corpus"),
        aliases=("patrologia", "pg", "cyril", "theophylact"),
        size_hint="~23.5 MB",
        tui_browsable=False,
        fetch_hint="read a volume:  aegean bible commentary PG073",
    ),
    # ── Fetch-on-demand Aegean corpora ───────────────────────────────────────
    CorpusSpec(
        id="damos",
        script_id="linearb",
        title="DAMOS Linear B Corpus (~5,900 tablets)",
        blurb="DAMOS full Linear B corpus",
        description="Full DAMOS Mycenaean Greek Linear B tablet corpus.",
        bundled=False,
        asset_name="damos-corpus",
        aliases=("damos",),
        size_hint="~3.0 MB",
        fetch_hint="load it:  aegean info damos",
    ),
    CorpusSpec(
        id="sigla",
        script_id="lineara",
        title="SigLA Linear A Corpus (802 documents)",
        blurb="SigLA Linear A corpus",
        description="SigLA palaeographic Linear A dataset (802 documents).",
        bundled=False,
        asset_name="sigla-corpus",
        aliases=("sigla",),
        size_hint="~1.3 MB",
        undeciphered=True,
        fetch_hint="load it:  aegean info sigla",
    ),
    # ── Fetch-on-demand Greek Epigraphy & Papyri corpora ─────────────────────
    CorpusSpec(
        id="isicily",
        script_id="greek",
        title="I.Sicily Greek Inscriptions (2,855 texts)",
        blurb="I.Sicily Greek inscriptions (Sicily)",
        description="2,855 primary-Greek EpiDoc inscriptions of ancient Sicily.",
        bundled=False,
        asset_name="isicily-corpus",
        aliases=("isicily", "sicily"),
        size_hint="~2.5 MB",
        fetch_hint="load it:  aegean info isicily",
    ),
    CorpusSpec(
        id="iip",
        script_id="greek",
        title="IIP Greek Inscriptions of Israel/Palestine (2,113 texts)",
        blurb="IIP Greek inscriptions (Israel/Palestine)",
        description="2,113 Greek EpiDoc inscriptions from Israel/Palestine.",
        bundled=False,
        asset_name="iip-corpus",
        aliases=("iip",),
        size_hint="~1.5 MB",
        fetch_hint="load it:  aegean info iip",
    ),
    CorpusSpec(
        id="iospe",
        script_id="greek",
        title="IOSPE Northern Black Sea Inscriptions (1,194 texts)",
        blurb="IOSPE Greek inscriptions (Black Sea)",
        description="1,194 Greek inscriptions of the Northern Black Sea.",
        bundled=False,
        asset_name="iospe-corpus",
        aliases=("iospe",),
        size_hint="~1.5 MB",
        fetch_hint="load it:  aegean info iospe",
    ),
    CorpusSpec(
        id="igcyr",
        script_id="greek",
        title="IGCyr/GVCyr Inscriptions of Cyrenaica (997 texts)",
        blurb="IGCyr/GVCyr Greek inscriptions (Cyrenaica)",
        description="997 archaic Doric and verse inscriptions of Cyrenaica.",
        bundled=False,
        asset_name="igcyr-corpus",
        aliases=("igcyr", "cyrenaica"),
        size_hint="~1.5 MB",
        fetch_hint="load it:  aegean info igcyr",
    ),
    CorpusSpec(
        id="aphrodisias",
        script_id="greek",
        title="Inscriptions of Aphrodisias (IAph2007, 1,471 texts)",
        blurb="IAph2007 Greek inscriptions (Aphrodisias, Asia Minor)",
        description="1,471 Greek EpiDoc inscriptions from Aphrodisias in Caria (IAph2007).",
        bundled=False,
        asset_name="aphrodisias-corpus",
        aliases=("aphrodisias", "iaph", "iaph2007"),
        size_hint="~0.5 MB",
        fetch_hint="load it:  aegean info aphrodisias",
    ),
    CorpusSpec(
        id="crete",
        script_id="greek",
        title="Cretan Institutional Inscriptions (600 Archaic–Hellenistic texts)",
        blurb="Cretan Institutional Inscriptions (Archaic–Hellenistic Crete)",
        description="600 Archaic–Hellenistic Greek EpiDoc inscriptions of Crete.",
        bundled=False,
        asset_name="crete-corpus",
        aliases=("crete", "cretan"),
        size_hint="~0.6 MB",
        fetch_hint="load it:  aegean info crete",
    ),
    CorpusSpec(
        id="edh",
        script_id="greek",
        title="EDH Greek Inscriptions (1,286 texts)",
        blurb="EDH Greek inscriptions (Heidelberg)",
        description="1,286 pure-Greek inscriptions from Epigraphic Database Heidelberg.",
        bundled=False,
        asset_name="edh-corpus",
        aliases=("edh",),
        size_hint="~1.0 MB",
        fetch_hint="load it:  aegean info edh",
    ),
    CorpusSpec(
        id="ddbdp",
        script_id="greek",
        title="DDbDP Greek Documentary Papyri (57,331 texts, SQLite)",
        blurb="DDbDP Greek documentary papyri (57,331 texts, SQLite)",
        description="57,331 Greek documentary papyri from Duke Databank (~4.4M tokens, SQLite FTS).",
        bundled=False,
        asset_name="ddbdp-corpus",
        aliases=("ddbdp", "papyri-db"),
        size_hint="~219 MB",
        tui_browsable=False,
        fetch_hint='search it (memory-friendly):  aegean db search ddbdp "βασιλέως"',
    ),
    # ── Fetch-on-demand Ancient, Classical, Late Antique & Byzantine Literary corpora ──
    CorpusSpec(
        id="classical-greek",
        script_id="greek",
        title="Archaic & Classical Greek Literature (684 works, 246 authors, 5.09M tokens)",
        blurb="Archaic & Classical Greek literature (8th–4th c. BCE)",
        description="684 Archaic & Classical Greek works (Homer, Hesiod, Pindar, Aeschylus, Sophocles, Euripides, Aristophanes, Herodotus, Thucydides, Xenophon, Plato, Aristotle, Hippocrates, Attic Orators; 5,088,194 tokens).",
        bundled=False,
        asset_name="classical-greek-corpus",
        category="classical",
        tags=("classical", "corpus"),
        aliases=("classical-greek", "archaic-greek"),
        size_hint="~17.3 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "ἀρετή" classical-greek',
    ),
    CorpusSpec(
        id="hellenistic-greek",
        script_id="greek",
        title="Hellenistic, Jewish-Greek & Fragmentary Historians (740 works, 587 authors, 4.67M tokens)",
        blurb="Hellenistic, Jewish-Greek & DFHG fragmentary historians (3rd–1st c. BCE)",
        description="740 Hellenistic Greek works (Polybius, Diodorus Siculus, Strabo, Dionysius of Halicarnassus, Philo of Alexandria, Euclid, Archimedes, Callimachus, Theocritus, Menander, DFHG historians; 4,672,040 tokens).",
        bundled=False,
        asset_name="hellenistic-greek-corpus",
        category="classical",
        tags=("classical", "corpus"),
        aliases=("hellenistic-greek", "hellenistic", "dfhg"),
        size_hint="~16.3 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "τύχη" hellenistic-greek',
    ),
    CorpusSpec(
        id="imperial-greek",
        script_id="greek",
        title="Imperial Greek Literature, Philosophy & Medicine (1,078 works, 373 authors, 14.66M tokens)",
        blurb="Imperial Greek literature, philosophy & medicine (1st–3rd c. CE)",
        description="1,078 Imperial-era Greek works (Plutarch, Galen, Lucian, Josephus, Epictetus, Marcus Aurelius, Cassius Dio, Athenaeus, Pausanias, Ptolemy, Sextus Empiricus, Plotinus, Porphyry, Diogenes Laertius; 14,662,168 tokens).",
        bundled=False,
        asset_name="imperial-greek-corpus",
        category="classical",
        tags=("classical", "corpus"),
        aliases=("imperial-greek", "imperial"),
        size_hint="~50.2 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "φύσις" imperial-greek',
    ),
    CorpusSpec(
        id="late-antique-greek",
        script_id="greek",
        title="Late Antique Philosophy, Rhetoric & Scholia (290 works, 82 authors, 11.33M tokens)",
        blurb="Late Antique philosophy, rhetoric & classical scholia (4th–6th c. CE)",
        description="290 Late Antique Greek works (Proclus, Simplicius, John Philoponus, Libanius, Julian, Themistius, Iamblichus, Nonnus, Quintus Smyrnaeus, Stobaeus, classical scholiasts; 11,333,916 tokens).",
        bundled=False,
        asset_name="late-antique-greek-corpus",
        category="classical",
        tags=("classical", "corpus"),
        aliases=("late-antique-greek", "late-antique"),
        size_hint="~38.9 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "ψυχή" late-antique-greek',
    ),
    CorpusSpec(
        id="byzantine-lit",
        script_id="greek",
        title="Byzantine History, Literature & Lexicography (185 works, 94 authors, 10.68M tokens)",
        blurb="Byzantine history, literature & lexicography (6th–15th c. CE, up to 1453)",
        description="185 Byzantine Greek works (Procopius, Anna Comnena, Michael Psellus, Eustathius of Thessalonica, Photius Bibliotheca, Suda, Hesychius, John Malalas, Theophanes, Constantine VII, Choniates, Pachymeres, Gregoras, Sphrantzes; 10,676,388 tokens).",
        bundled=False,
        asset_name="byzantine-lit-corpus",
        category="byzantine",
        tags=("byzantine", "corpus"),
        aliases=("byzantine-lit", "byzantine-history", "suda"),
        size_hint="~38.3 MB",
        tui_browsable=False,
        fetch_hint='search it:  aegean find "βασιλεύς" byzantine-lit',
    ),
    CorpusSpec(
        id="byzantine",
        script_id="greek",
        title="Byzantine & Early Modern Vernacular Greek (12 works, 189K tokens)",
        blurb="Byzantine & Early Modern Vernacular Greek (12th–17th c.)",
        description="12 medieval and early-modern vernacular Greek literary works (Digenes Akritas, Chronicle of Moreas, Ptochoprodromika, Erotokritos, etc.).",
        bundled=False,
        asset_name="byzantine-corpus",
        category="byzantine",
        tags=("byzantine", "corpus"),
        aliases=("byzantine", "byz-vernacular", "digenes", "erotokritos"),
        size_hint="~2.5 MB",
        fetch_hint="load it:  aegean info byzantine",
    ),
    CorpusSpec(
        id="homer-scholia",
        script_id="greek",
        title="Homer Multitext Venetus A Iliad & Scholia (54 docs, 331K tokens)",
        blurb="Homer Multitext Venetus A Iliad & Homeric Scholia",
        description="24 books normalized Venetus A Iliad plus 30 Homeric scholia documents (Main, interlinear, Venetus B, Escorial Upsilon 1.1).",
        bundled=False,
        asset_name="homer-scholia-corpus",
        category="classical",
        tags=("classical", "corpus", "commentary"),
        aliases=("homer-scholia", "hmt", "venetus-a", "scholia"),
        size_hint="~5.5 MB",
        fetch_hint="load it:  aegean info homer-scholia",
    ),
)

CORPUS_BY_ID: dict[str, CorpusSpec] = {c.id: c for c in CORPORA}
CORPUS_BY_ASSET: dict[str, CorpusSpec] = {c.asset_name: c for c in CORPORA if c.asset_name}
UNDECIPHERED_IDS: frozenset[str] = frozenset(c.id for c in CORPORA if c.undeciphered)


def tui_browsable_ids() -> tuple[str, ...]:
    """Return browsable corpus IDs in canonical presentation order."""
    return tuple(c.id for c in CORPORA if c.tui_browsable)


def tui_blurbs() -> dict[str, str]:
    """Return ``{corpus_id: one_line_blurb}`` for every TUI-browsable corpus."""
    return {c.id: c.blurb for c in CORPORA if c.tui_browsable}


def tui_asset_map() -> dict[str, str]:
    """Return ``{corpus_id: remote_asset_name}`` for fetch-on-demand corpora."""
    return {c.id: c.asset_name for c in CORPORA if c.asset_name}


def cli_fetch_hints() -> dict[str, str]:
    """Return ``{asset_name: next_step_hint}`` for ``aegean data fetch``."""
    hints: dict[str, str] = {
        c.asset_name: c.fetch_hint
        for c in CORPORA
        if c.asset_name and c.fetch_hint
    }
    hints["linearb-corpus"] = "load it:  aegean info linearb"
    hints["lineara-images"] = "serve it:  aegean workbench"
    return hints


def make_json_corpus_loader(
    asset_name: str,
    *,
    name: str | None = None,
    doc: str = "",
) -> Callable[[], Any]:
    """Build a standard fetch-and-load callable for a hosted JSON/JSON.gz corpus."""

    def _loader() -> Any:
        from ..data import fetch
        from .corpus import Corpus

        return Corpus.from_json(fetch(asset_name))

    if name:
        _loader.__name__ = name
    if doc:
        _loader.__doc__ = doc
    return _loader
