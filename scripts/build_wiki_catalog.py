"""Generate the Corpus Catalog section of the pyaegean wiki (`wiki/Catalog*.md`).

Reads live package metadata directly from ``aegean.core.catalog``,
``aegean.greek.collections()``, ``aegean.greek.collection_works()``,
``aegean.greek.catalog()``, ``aegean.greek.bible``, ``aegean.scripts.greek.patrologia``,
``aegean.library``, and ``training/results/corpus-facts.json`` so every count,
identifier, license, and work title stays synchronized with the shipped toolkit.

Usage:
    python scripts/build_wiki_catalog.py [--extra-json /path/to/extra_corpora.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

WIKI_DIR = ROOT / "wiki"

CATALOG_NAV = (
    "[Catalog Overview](Catalog) · "
    "[Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) · "
    "[Biblical & Second Temple](Catalog-Biblical) · "
    "[John Chrysostom](Catalog-Chrysostom) · "
    "[Church Fathers & Patristics](Catalog-Church-Fathers) · "
    "[Archaic & Classical](Catalog-Classical-Greek) · "
    "[Hellenistic](Catalog-Hellenistic-Greek) · "
    "[Imperial](Catalog-Imperial-Greek) · "
    "[Late Antique & Byzantine](Catalog-Late-Antique-and-Byzantine) · "
    "[Perseus & First1KGreek](Catalog-Perseus-and-First1K)"
)


def _esc(val: Any) -> str:
    """Escape cell text for safe GitHub-Flavored Markdown tables."""
    s = str(val if val is not None else "").replace("\r", " ").replace("\n", " ").strip()
    return s.replace("|", "\\|")


def _fmt_int(n: int | None) -> str:
    if n is None:
        return ""
    return f"{int(n):,}"


def _load_corpus_facts() -> dict[str, dict[str, Any]]:
    path = ROOT / "training" / "results" / "corpus-facts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for cid, row in data.get("corpora", {}).items():
        out[cid] = row
    return out


def _load_extra_corpora(extra_json: Path | None) -> dict[str, list[dict[str, Any]]]:
    if extra_json is not None and extra_json.is_file():
        loaded: dict[str, list[dict[str, Any]]] = json.loads(extra_json.read_text(encoding="utf-8"))
        return loaded
    import aegean

    out: dict[str, list[dict[str, Any]]] = {}
    for cid in ("apostolic-fathers", "pseudepigrapha", "byzantine", "homer-scholia", "greek"):
        corp = aegean.load(cid)
        out[cid] = [
            {
                "id": doc.id,
                "name": doc.meta.name or doc.id,
                "period": doc.meta.period or "",
                "tokens": len(doc.tokens),
                "lines": len(doc.lines),
                "notes": list(doc.meta.notes),
            }
            for doc in corp
        ]
    return out


def _short_license(raw: str) -> str:
    """Shorten a verbose asset license string for compact table display."""
    s = raw.strip()
    if not s:
        return ""
    # Preserve dual-part NT corpus license concisely.
    if s.startswith("CC0-1.0") and "base Greek text public domain" in s:
        return "CC0-1.0 / Public Domain"
    head = s.split(" (", 1)[0].strip()
    head = head.split("; fetched, never bundled", 1)[0].strip()
    head = head.split("; derived index, fetched, never bundled", 1)[0].strip()
    if head.lower() == "public domain":
        return "Public Domain"
    return head


def _corpus_license(spec: Any, remote: dict[str, Any]) -> str:
    if spec.license:
        return _short_license(spec.license)
    if spec.asset_name and spec.asset_name in remote:
        return _short_license(remote[spec.asset_name].license)
    return ""


def _render_collection_table(works: list[dict[str, Any]]) -> list[str]:
    """Render a sorted Markdown table of OGC collection works."""
    rows = sorted(
        works, key=lambda w: (w["author"].casefold(), w["title"].casefold(), w["work_id"])
    )
    lines = [
        "| Work ID | Author | Title | TLG | Tokens | License |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for w in rows:
        tlg = f"`{_esc(w['tlg'])}`" if w.get("tlg") else ""
        lines.append(
            f"| `{_esc(w['work_id'])}` | {_esc(w['author'])} | {_esc(w['title'])} | "
            f"{tlg} | {_fmt_int(w['tokens'])} | {_esc(w['license'])} |"
        )
    return lines


def _build_overview(
    facts: dict[str, dict[str, Any]],
    extra: dict[str, list[dict[str, Any]]],
) -> str:
    from aegean import greek, library
    from aegean.core.catalog import CORPORA
    from aegean.data import _REMOTE
    from aegean.greek import bible
    from aegean.scripts.greek.patrologia import PG_VOLUMES

    cols = greek.collections()
    total_ogc_works = sum(c["works"] for c in cols)
    total_ogc_tokens = sum(c["tokens"] for c in cols)
    tei_works = greek.catalog()
    packs = [ps.pack for ps in library.list_packs()]

    lines: list[str] = [
        "# Corpus Catalog",
        "",
        "Directory of every corpus, collection, biblical text, patristic work, inscription set, "
        "papyrus archive, and literary text available in pyaegean, organized by category. "
        "Core Aegean corpora and small Greek/Biblical seed samples ship inside the package; "
        "all large corpora fetch on demand to your local cache with SHA-256 verification.",
        "",
        CATALOG_NAV,
        "",
        "---",
        "",
        "## Browse by category",
        "",
        "| Category | Contents | Catalog page |",
        "| --- | --- | --- |",
        "| **Aegean Scripts, Epigraphy & Papyri** | 6 Aegean script corpora (`lineara`, `sigla`, `linearb`, `damos`, `cypriot`, `cyprominoan`), bundled Greek seed (`greek`), 7 Greek epigraphic corpora, DDbDP documentary papyri (57,331 texts), and 7 Greek lexica | [Aegean, Epigraphy & Papyri](Catalog-Aegean-and-Epigraphy) |",
        f"| **Biblical & Second Temple Greek** | {len(bible.nt_editions())} Greek NT editions, {len(bible.nt_books())} NT books, 13 early manuscript witnesses (`01`–`05`, `032`, `P45`–`P75`), {len(bible.lxx_books())} Septuagint (LXX) books (incl. Ecclesiastes), and {len(extra['pseudepigrapha'])} Greek OT Pseudepigrapha works | [Biblical & Second Temple](Catalog-Biblical) |",
        "| **John Chrysostom** | 155 open-licensed Greek works (3,738,372 tokens): homilies, sermons, 26 biblical commentary series, treatises, and letters | [John Chrysostom](Catalog-Chrysostom) |",
        f"| **Church Fathers & Patristics** | 432 Early & Nicene Fathers works (58 authors), 280 Post-Nicene & Eastern Fathers works (38 authors), {len(extra['apostolic-fathers'])} Open Apostolic Fathers, {len(PG_VOLUMES)} *Patrologia Graeca* volumes, and {len(bible.patristic_commentaries())} indexed patristic biblical commentaries | [Church Fathers & Patristics](Catalog-Church-Fathers) |",
        f"| **Archaic & Classical Greek** | 684 works across 246 authors (8th–4th c. BCE, 5,088,194 tokens) plus {len(extra['homer-scholia'])} Homer Multitext Venetus A *Iliad* & *Scholia* documents | [Archaic & Classical Greek](Catalog-Classical-Greek) |",
        "| **Hellenistic Greek** | 740 works across 587 authors (3rd–1st c. BCE, 4,672,040 tokens), including Jewish-Greek literature and DFHG fragmentary historians | [Hellenistic Greek](Catalog-Hellenistic-Greek) |",
        "| **Imperial Greek** | 1,078 works across 373 authors (1st–3rd c. CE, 14,662,168 tokens): Plutarch, Galen, Lucian, Josephus, Epictetus, Marcus Aurelius, Cassius Dio | [Imperial Greek](Catalog-Imperial-Greek) |",
        f"| **Late Antique & Byzantine Greek** | 290 Late Antique works (82 authors, 4th–6th c. CE), 185 Byzantine literary & historical works through 1453 (94 authors), and {len(extra['byzantine'])} Byzantine & Early Modern vernacular works | [Late Antique & Byzantine Greek](Catalog-Late-Antique-and-Byzantine) |",
        f"| **Perseus & First1KGreek (TEI)** | {len(tei_works):,} on-demand TEI works (768 Perseus `canonical-greekLit` + 1,010 `First1KGreek`) addressable by CTS ID (`tlgAAAA.tlgBBB`) | [Perseus & First1KGreek](Catalog-Perseus-and-First1K) |",
        "",
        "---",
        "",
        f"## All {len(CORPORA)} registered corpora",
        "",
        'Every ID below loads via `aegean.load("<id>")` (or `aegean.open("<id>")`) in Python and '
        "works anywhere the CLI expects a `CORPUS` argument. The 8 categorized Greek library collections "
        f"total **{total_ogc_works:,} works** (**{total_ogc_tokens:,} tokens**) and also support "
        'single-work loading via `aegean.open("ogc002060")` or `aegean greek work ogc002060`.',
        "",
    ]

    category_order = [
        ("corpus", "Aegean scripts, epigraphy, papyri & seed sample"),
        ("bible", "Biblical & Second Temple Greek"),
        ("patristics", "Church Fathers & Patristics"),
        ("classical", "Archaic, Classical, Hellenistic, Imperial & Late Antique Greek"),
        ("byzantine", "Byzantine Greek"),
    ]
    by_cat: dict[str, list[Any]] = defaultdict(list)
    for spec in CORPORA:
        by_cat[spec.category].append(spec)

    for cat_key, cat_heading in category_order:
        specs = by_cat.get(cat_key, [])
        if not specs:
            continue
        lines.append(f"### {cat_heading}")
        lines.append("")
        lines.append("| Corpus ID | Title | Docs | Tokens | Delivery | Size | License |")
        lines.append("| --- | --- | ---: | ---: | --- | --- | --- |")
        for spec in specs:
            delivery = "Bundled (offline)" if spec.bundled else f"Hosted (`{spec.asset_name}`)"
            size = "bundled" if spec.bundled else spec.size_hint
            fact = facts.get(spec.id, {})
            lic = _corpus_license(spec, _REMOTE)
            lines.append(
                f"| `{_esc(spec.id)}` | {_esc(spec.title)} | {_fmt_int(fact.get('documents'))} | "
                f"{_fmt_int(fact.get('tokens'))} | {delivery} | {_esc(size)} | {_esc(lic)} |"
            )
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            f"## Named install packs ({len(packs)} packs)",
            "",
            'Install whole groups at once with `aegean library install <pack>` or `aegean.library.install("<pack>")`:',
            "",
            "| Pack ID | Aliases | Included assets | Approx. size |",
            "| --- | --- | --- | --- |",
        ]
    )
    for p in packs:
        aliases = ", ".join(f"`{a}`" for a in p.aliases)
        items = ", ".join(f"`{i}`" for i in p.items)
        lines.append(f"| `{_esc(p.id)}` | {aliases} | {items} | {_esc(p.size_hint)} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "For dataset checksums, upstream commit pins, and full licensing terms, see "
            "[Data & Provenance](Data-and-Provenance) and [`NOTICE`](https://github.com/ryanpavlicek/pyaegean/blob/main/NOTICE).",
            "",
        ]
    )
    return "\n".join(lines)


def _build_aegean_and_epigraphy(
    facts: dict[str, dict[str, Any]],
    extra: dict[str, list[dict[str, Any]]],
) -> str:
    from aegean.core.catalog import CORPUS_BY_ID
    from aegean.data import _REMOTE

    lines: list[str] = [
        "# Catalog: Aegean Scripts, Epigraphy, Papyri & Lexica",
        "",
        CATALOG_NAV,
        "",
        "Complete listing of all Aegean syllabic script corpora, the bundled Greek sample, "
        "Greek epigraphic corpora, documentary papyri, and Greek dictionaries.",
        "",
        "## Aegean syllabic scripts",
        "",
        "| Corpus ID | Script | Title | Docs | Tokens | Delivery | Size | License |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for cid in ("lineara", "sigla", "linearb", "damos", "cypriot", "cyprominoan"):
        s = CORPUS_BY_ID[cid]
        delivery = "Bundled (offline)" if s.bundled else f"Hosted (`{s.asset_name}`)"
        size = "bundled" if s.bundled else s.size_hint
        fact = facts.get(cid, {})
        lic = _corpus_license(s, _REMOTE)
        lines.append(
            f"| `{cid}` | `{s.script_id}` | {_esc(s.title)} | {_fmt_int(fact.get('documents'))} | "
            f"{_fmt_int(fact.get('tokens'))} | {delivery} | {_esc(size)} | {_esc(lic)} |"
        )

    lines.extend(
        [
            "",
            "## Bundled Greek seed sample (`greek`)",
            "",
            'Five public-domain passages bundled for offline smoke testing and quickstart examples (`aegean.load("greek")`):',
            "",
            "| Document ID | Passage | Period | Tokens |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for row in extra["greek"]:
        lines.append(
            f"| `{_esc(row['id'])}` | {_esc(row['name'])} | {_esc(row['period'])} | {_fmt_int(row['tokens'])} |"
        )

    lines.extend(
        [
            "",
            "## Greek epigraphy (7 corpora)",
            "",
            "Install all seven at once with `aegean library install epigraphy` (~9.1 MB):",
            "",
            "| Corpus ID | Title | Documents | Tokens | Size | License |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for cid in ("isicily", "iip", "iospe", "igcyr", "aphrodisias", "crete", "edh"):
        s = CORPUS_BY_ID[cid]
        fact = facts.get(cid, {})
        lic = _corpus_license(s, _REMOTE)
        lines.append(
            f"| `{cid}` | {_esc(s.title)} | {_fmt_int(fact.get('documents'))} | "
            f"{_fmt_int(fact.get('tokens'))} | {_esc(s.size_hint)} | {_esc(lic)} |"
        )

    ddbdp = CORPUS_BY_ID["ddbdp"]
    ddbdp_fact = facts.get("ddbdp", {})
    ddbdp_lic = _corpus_license(ddbdp, _REMOTE)
    lines.extend(
        [
            "",
            "## Documentary papyri (`ddbdp`)",
            "",
            "| Corpus ID | Title | Documents | Tokens | Size | License |",
            "| --- | --- | ---: | ---: | --- | --- |",
            f"| `ddbdp` | {_esc(ddbdp.title)} | {_fmt_int(ddbdp_fact.get('documents'))} | "
            f"{_fmt_int(ddbdp_fact.get('tokens'))} | {_esc(ddbdp.size_hint)} | {_esc(ddbdp_lic)} |",
            "",
            "Query DDbDP through SQLite FTS without loading all texts into RAM: "
            '`aegean db search ddbdp "βασιλέως"` or `aegean.db.stream(aegean.scripts.greek.ddbdp_db())`.',
            "",
            "## Greek lexica & dictionaries",
            "",
            "Install all five hosted dictionary indexes at once with `aegean library install lexica` (~19.3 MB):",
            "",
            "| Key / Asset | Dictionary | Scope | Delivery | License |",
            "| --- | --- | --- | --- | --- |",
            "| `dodson` | Dodson Greek-English Lexicon | Koine / New Testament (~5,500 entries) | Bundled (offline) | CC0-1.0 / Public Domain |",
            f"| `strongs-greek` | Extended Strong's Greek Lexicon (STEPBible TBESG + OpenScriptures) | NT, LXX, Apocrypha & Apostolic Fathers (11,142 entries + root trees) | Hosted (~1.5 MB) | {_esc(_short_license(_REMOTE['strongs-greek'].license))} |",
            f"| `lsj-index` | Liddell-Scott-Jones (LSJ) | Classical, Hellenistic & Imperial Greek (~116k headwords) | Hosted (~15 MB) | {_esc(_short_license(_REMOTE['lsj-index'].license))} |",
            f"| `middle-liddell-index` | Middle Liddell (Intermediate Greek-English Lexicon) | General Ancient Greek | Hosted (~2.4 MB) | {_esc(_short_license(_REMOTE['middle-liddell-index'].license))} |",
            f"| `cunliffe-index` | Cunliffe Lexicon of the Homeric Dialect | Homeric Greek (*Iliad* & *Odyssey*) | Hosted (~1.3 MB) | {_esc(_short_license(_REMOTE['cunliffe-index'].license))} |",
            f"| `autenrieth-index` | Autenrieth Homeric Dictionary | Homeric Greek | Hosted (~0.6 MB) | {_esc(_short_license(_REMOTE['autenrieth-index'].license))} |",
            f"| `abbott-smith-index` | Abbott-Smith Manual Greek Lexicon of the New Testament | Koine / NT Greek | Hosted (~0.13 MB) | {_esc(_short_license(_REMOTE['abbott-smith-index'].license))} |",
            "",
        ]
    )
    return "\n".join(lines)


def _build_biblical(extra: dict[str, list[dict[str, Any]]]) -> str:
    from aegean.greek import bible
    from aegean.greek.bible._catalogs import NT_EDITIONS, WITNESS_CATALOG

    lxx = bible.lxx_books()
    nt_books = bible.nt_books()
    pseudo = extra["pseudepigrapha"]

    lines: list[str] = [
        "# Catalog: Biblical & Second Temple Greek",
        "",
        CATALOG_NAV,
        "",
        "All Greek New Testament editions, books, early manuscript witnesses, Septuagint (LXX) books, "
        "and Greek Old Testament Pseudepigrapha available through `aegean.greek.bible`, `aegean bible`, "
        '`aegean.load("nt")`, `aegean.load("lxx")`, and `aegean.load("pseudepigrapha")`.',
        "",
        "Install the Biblical pack (`nt-corpus`, `nt-editions`, `nt-witnesses`, `strongs-greek`, "
        "`lxx-corpus`, ~27 MB total) with `aegean bible install` or `aegean library install biblical`.",
        "",
        f"## Greek New Testament editions ({len(NT_EDITIONS)} editions)",
        "",
        "| Edition ID | Name | Editor / Source | Asset | Gold annotations | License |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for ed in NT_EDITIONS:
        ann = "Yes (lemma, morph, Strong's, UPOS, gloss)" if ed["annotated"] else "Greek text"
        lines.append(
            f"| `{_esc(ed['id'])}` | {_esc(ed['name'])} | {_esc(ed['editor'])} | "
            f"`{_esc(ed['asset'])}` | {ann} | {_esc(ed['license'])} |"
        )

    lines.extend(
        [
            "",
            f"## Greek New Testament books ({len(nt_books)} books)",
            "",
            "| # | Canonical ID | Accepted aliases |",
            "| ---: | --- | --- |",
        ]
    )
    for idx, b in enumerate(nt_books, 1):
        aliases = ", ".join(f"`{a}`" for a in b["aliases"])
        lines.append(f"| {idx} | `{_esc(b['name'])}` | {aliases} |")

    lines.extend(
        [
            "",
            f"## Early Greek NT manuscript witnesses ({len(WITNESS_CATALOG)} witnesses, 2nd–5th c. CE)",
            "",
            "Hosted in `nt-witnesses` (~1.5 MB, CC BY-SA 4.0, Center for New Testament Restoration):",
            "",
            "| Siglum | Symbol | Manuscript | Date | Type | Text-type / Coverage |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for w in WITNESS_CATALOG:
        lines.append(
            f"| `{_esc(w['siglum'])}` | {_esc(w['alias'])} | {_esc(w['name'])} | "
            f"{_esc(w['century'])} | {_esc(w['kind'])} | {_esc(w['text_type'])} |"
        )

    lines.extend(
        [
            "",
            f"## Septuagint (LXX) books ({len(lxx)} books, 29,470 verses, 592,436 tokens)",
            "",
            "Hosted in `lxx-corpus` (`lxx-corpus-v2`, ~1.7 MB, CC BY-SA 4.0: Swete 1887–1894 via First1KGreek "
            'plus Greek Wikisource Ecclesiastes `tlg0527.tlg030`). Load via `aegean.load("lxx")`, '
            '`bible.load_lxx("Gen 1:1-5", interlinear=True)`, or `bible.load_lxx("MT Ps 23")`.',
            "",
        ]
    )
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    section_order: list[str] = []
    for b in lxx:
        sec = b["section"]
        if sec not in by_section:
            section_order.append(sec)
        by_section[sec].append(b)

    for sec in section_order:
        items = by_section[sec]
        lines.append(f"### {sec} ({len(items)} books)")
        lines.append("")
        lines.append("| Book ID | Title | TLG Work ID | Aliases |")
        lines.append("| --- | --- | --- | --- |")
        for b in items:
            aliases = ", ".join(f"`{a}`" for a in b["aliases"])
            lines.append(
                f"| `{_esc(b['name'])}` | {_esc(b['title'])} | `{_esc(b['work_id'])}` | {aliases} |"
            )
        lines.append("")

    lines.extend(
        [
            f"## Greek Old Testament Pseudepigrapha ({len(pseudo)} works, {sum(r['tokens'] for r in pseudo):,} tokens)",
            "",
            "Hosted in `pseudepigrapha-corpus` (~2.7 MB, CC BY 4.0, *Online Critical Pseudepigrapha*). "
            'Load via `aegean.load("pseudepigrapha")` or install with `aegean library install patristic`.',
            "",
            "| Document ID | Work | Tokens |",
            "| --- | --- | ---: |",
        ]
    )
    for r in sorted(pseudo, key=lambda x: x["id"].casefold()):
        lines.append(f"| `{_esc(r['id'])}` | {_esc(r['name'])} | {_fmt_int(r['tokens'])} |")
    lines.append("")
    return "\n".join(lines)


def _build_chrysostom() -> str:
    from aegean import greek
    from aegean.greek import bible

    works = greek.collection_works("chrysostom")
    total_tokens = sum(w["tokens"] for w in works)
    comms = bible.patristic_commentaries(kind="chrysostom")

    lines: list[str] = [
        "# Catalog: John Chrysostom (155 Greek Works)",
        "",
        CATALOG_NAV,
        "",
        f"Complete open-licensed Greek corpus of John Chrysostom (and Pseudo-Chrysostom) in "
        f"`chrysostom-corpus` (~12.3 MB, **{len(works)} works**, **{total_tokens:,} tokens**, "
        "100% verified Public Domain, CC BY 4.0, or CC BY-SA 4.0).",
        "",
        "```bash",
        "aegean library install chrysostom-corpus      # install John Chrysostom collection (~12.3 MB)",
        "aegean greek work ogc002060                   # load In Matthaeum (Homiliae 1-90)",
        "aegean bible commentary search ogc002060 ἀγάπη",
        "aegean find ἀγάπη chrysostom                  # FTS5 search across all 155 works",
        "```",
        "",
        f"## Indexed biblical homily & commentary series ({len(comms)} series)",
        "",
        'Accessible directly through `aegean.greek.bible.load_commentary(book, kind="chrysostom")` '
        "and `aegean bible commentary --kind chrysostom`:",
        "",
        "| Work ID | Biblical Book(s) | Series Title |",
        "| --- | --- | --- |",
    ]
    for c in comms:
        books = ", ".join(c.get("books") or [c["book"]])
        lines.append(f"| `{_esc(c['work_id'])}` | {_esc(books)} | {_esc(c['title'])} |")

    lines.extend(
        [
            "",
            f"## Complete listing of all {len(works)} works in `chrysostom`",
            "",
        ]
    )
    lines.extend(_render_collection_table(works))
    lines.append("")
    return "\n".join(lines)


def _build_church_fathers(extra: dict[str, list[dict[str, Any]]]) -> str:
    from aegean import greek
    from aegean.greek import bible
    from aegean.scripts.greek.patrologia import PG_VOLUMES

    early = greek.collection_works("church-fathers-early")
    late = greek.collection_works("church-fathers-late")
    af = extra["apostolic-fathers"]
    comms = bible.patristic_commentaries()

    lines: list[str] = [
        "# Catalog: Church Fathers & Patristics",
        "",
        CATALOG_NAV,
        "",
        "All Greek patristic works outside John Chrysostom's dedicated 155-work catalog "
        "([John Chrysostom](Catalog-Chrysostom)): Open Apostolic Fathers, Early & Nicene Fathers "
        "(2nd–4th c. CE), Post-Nicene & Eastern Fathers (5th–15th c. CE), digitized *Patrologia Graeca* "
        "volumes, and all 112 indexed Greek patristic biblical commentaries.",
        "",
        "```bash",
        "aegean library install church-fathers   # John Chrysostom (155) + Early/Late Fathers (712) + Apostolic Fathers (15)",
        "aegean library install patristic        # Apostolic Fathers (15) + OT Pseudepigrapha (44) + Patrologia Graeca (33 vols)",
        "```",
        "",
        f"## Open Apostolic Fathers (`apostolic-fathers`: {len(af)} works, {sum(r['tokens'] for r in af):,} tokens)",
        "",
        "Hosted in `apostolic-fathers-corpus` (~1.0 MB, CC BY-SA 4.0, twice hand-corrected). "
        'Load via `aegean.load("apostolic-fathers")`.',
        "",
        "| Document ID | Work | Period | Tokens |",
        "| --- | --- | --- | ---: |",
    ]
    for r in af:
        lines.append(
            f"| `{_esc(r['id'])}` | {_esc(r['name'])} | {_esc(r['period'])} | {_fmt_int(r['tokens'])} |"
        )

    lines.extend(
        [
            "",
            f"## Early & Nicene Church Fathers (`church-fathers-early`: {len(early)} works, "
            f"{len({w['author'] for w in early})} authors, {sum(w['tokens'] for w in early):,} tokens)",
            "",
            "Hosted in `church-fathers-early-corpus` (~21.0 MB, Public Domain / CC BY 4.0 / CC BY-SA 4.0). "
            'Open any work directly with `aegean.open("<work_id>")` or `aegean greek work <work_id>`.',
            "",
        ]
    )
    lines.extend(_render_collection_table(early))

    lines.extend(
        [
            "",
            f"## Post-Nicene, Eastern Fathers & Saints (`church-fathers-late`: {len(late)} works, "
            f"{len({w['author'] for w in late})} authors, {sum(w['tokens'] for w in late):,} tokens)",
            "",
            "Hosted in `church-fathers-late-corpus` (~26.7 MB, Public Domain / CC BY 4.0 / CC BY-SA 4.0).",
            "",
        ]
    )
    lines.extend(_render_collection_table(late))

    lines.extend(
        [
            "",
            f"## Patrologia Graeca (`patrologia`: {len(PG_VOLUMES)} Migne volumes, 6,787,292 words)",
            "",
            "Hosted in `patrologia-graeca-corpus` (~23.5 MB, CC BY 4.0, Calfa–GREgORI OCR of 19th-century "
            'Migne prints). Open a single volume with `aegean.open("PG073")` or search with '
            "`aegean find λόγος PG073`.",
            "",
            "| Volume ID | PG # | Author | Title | Period | Biblical books |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for v in PG_VOLUMES:
        bks = ", ".join(v.get("biblical_books") or ())
        lines.append(
            f"| `{_esc(v['id'])}` | {_esc(v['pg'])} | {_esc(v['author'])} | "
            f"{_esc(v['title'])} | {_esc(v['period'])} | {_esc(bks)} |"
        )

    lines.extend(
        [
            "",
            f"## Indexed patristic biblical commentaries ({len(comms)} volumes across 11 Fathers & traditions)",
            "",
            "Discoverable offline via `aegean.greek.bible.patristic_commentaries()` and `aegean bible commentary`:",
            "",
            "| Work ID | Kind | Author | Biblical Book(s) | Title | Source |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for c in comms:
        books = ", ".join(c.get("books") or [c["book"]])
        lines.append(
            f"| `{_esc(c['work_id'])}` | `{_esc(c['kind'])}` | {_esc(c['author'])} | "
            f"{_esc(books)} | {_esc(c['title'])} | `{_esc(c['source'])}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_classical_greek(extra: dict[str, list[dict[str, Any]]]) -> str:
    from aegean import greek

    works = greek.collection_works("classical-greek")
    hmt = extra["homer-scholia"]
    authors = len({w["author"] for w in works})
    tokens = sum(w["tokens"] for w in works)

    lines: list[str] = [
        f"# Catalog: Archaic & Classical Greek ({len(works)} Works + Homer Multitext)",
        "",
        CATALOG_NAV,
        "",
        f"All **{len(works)} works** across **{authors} authors** (**{tokens:,} tokens**, 8th–4th c. BCE) "
        "in `classical-greek-corpus` (~17.3 MB, 100% verified Public Domain, CC BY 4.0, or CC BY-SA 4.0), "
        f"plus all **{len(hmt)} documents** in `homer-scholia-corpus` (~5.5 MB, CC BY-NC 4.0, "
        "Homer Multitext Venetus A *Iliad* and Homeric *scholia*).",
        "",
        "```bash",
        "aegean library install classical-greek-corpus   # install Archaic & Classical Greek (~17.3 MB)",
        "aegean library install ancient-greek            # install all 4 Ancient–Late Antique packs (~123 MB)",
        "aegean library install homer-scholia-corpus     # install Venetus A Iliad & Homeric Scholia (~5.5 MB)",
        "```",
        "",
        f"## Archaic & Classical Greek (`classical-greek`: {len(works)} works)",
        "",
    ]
    lines.extend(_render_collection_table(works))

    lines.extend(
        [
            "",
            f"## Homer Multitext Venetus A Iliad & Scholia (`homer-scholia`: {len(hmt)} documents, "
            f"{sum(r['tokens'] for r in hmt):,} tokens)",
            "",
            "Hosted in `homer-scholia-corpus` (~5.5 MB, CC BY-NC 4.0, Homer Multitext Project `hmt-2026a`).",
            "",
            "| Document ID | Title | Period | Passages | Tokens |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for r in hmt:
        lines.append(
            f"| `{_esc(r['id'])}` | {_esc(r['name'])} | {_esc(r['period'])} | "
            f"{_fmt_int(r['lines'])} | {_fmt_int(r['tokens'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_single_collection_page(
    cid: str,
    heading: str,
    intro: str,
    install_cmd: str,
) -> str:
    from aegean import greek

    works = greek.collection_works(cid)
    authors = len({w["author"] for w in works})
    tokens = sum(w["tokens"] for w in works)

    lines: list[str] = [
        f"# Catalog: {heading} ({len(works):,} Works)",
        "",
        CATALOG_NAV,
        "",
        f"{intro} Contains **{len(works):,} works** across **{authors} authors** "
        f"(**{tokens:,} tokens**, 100% verified Public Domain, CC BY 4.0, or CC BY-SA 4.0).",
        "",
        "```bash",
        install_cmd,
        f"aegean greek collections {cid} --limit 25",
        "```",
        "",
    ]
    lines.extend(_render_collection_table(works))
    lines.append("")
    return "\n".join(lines)


def _build_late_antique_and_byzantine(extra: dict[str, list[dict[str, Any]]]) -> str:
    from aegean import greek

    late_ant = greek.collection_works("late-antique-greek")
    byz_lit = greek.collection_works("byzantine-lit")
    byz_vern = extra["byzantine"]

    lines: list[str] = [
        "# Catalog: Late Antique & Byzantine Greek",
        "",
        CATALOG_NAV,
        "",
        "Greek literature, philosophy, rhetoric, scholia, historiography, lexicography, and vernacular "
        "texts from the 4th century CE through the Fall of Constantinople (1453) and Early Modern "
        "vernacular continuations.",
        "",
        "```bash",
        "aegean library install late-antique-greek-corpus  # 290 Late Antique works (~38.9 MB)",
        "aegean library install byzantine-pack             # 185 Byzantine literary works + 12 vernacular works (~41 MB)",
        "```",
        "",
        f"## Late Antique Greek (`late-antique-greek`: {len(late_ant)} works, "
        f"{len({w['author'] for w in late_ant})} authors, {sum(w['tokens'] for w in late_ant):,} tokens, 4th–6th c. CE)",
        "",
        "Hosted in `late-antique-greek-corpus` (~38.9 MB, Public Domain / CC BY 4.0 / CC BY-SA 4.0).",
        "",
    ]
    lines.extend(_render_collection_table(late_ant))

    lines.extend(
        [
            "",
            f"## Byzantine History, Literature & Lexicography (`byzantine-lit`: {len(byz_lit)} works, "
            f"{len({w['author'] for w in byz_lit})} authors, {sum(w['tokens'] for w in byz_lit):,} tokens, 6th–15th c. CE through 1453)",
            "",
            "Hosted in `byzantine-lit-corpus` (~38.3 MB, Public Domain / CC BY 4.0 / CC BY-SA 4.0).",
            "",
        ]
    )
    lines.extend(_render_collection_table(byz_lit))

    lines.extend(
        [
            "",
            f"## Byzantine & Early Modern Vernacular Greek (`byzantine`: {len(byz_vern)} works, "
            f"{sum(r['tokens'] for r in byz_vern):,} tokens, 12th–17th c. CE)",
            "",
            'Hosted in `byzantine-corpus` (~2.5 MB, Public Domain / CC BY-SA 3.0). Load via `aegean.load("byzantine")`.',
            "",
            "| Document ID | Title | Period | Lines | Tokens |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for r in byz_vern:
        lines.append(
            f"| `{_esc(r['id'])}` | {_esc(r['name'])} | {_esc(r['period'])} | "
            f"{_fmt_int(r['lines'])} | {_fmt_int(r['tokens'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_perseus_and_first1k() -> str:
    from aegean import greek

    works = greek.catalog()
    perseus_n = sum(1 for w in works if w["source"] == "perseus")
    first1k_n = sum(1 for w in works if w["source"] == "first1k")
    rows = sorted(
        works,
        key=lambda w: (
            (w.get("author") or "").casefold(),
            (w.get("title") or "").casefold(),
            w["id"],
        ),
    )

    lines: list[str] = [
        f"# Catalog: Perseus & First1KGreek TEI Works ({len(works):,} Works)",
        "",
        CATALOG_NAV,
        "",
        f"Complete offline catalogue (`aegean.greek.catalog()`) of **{len(works):,} TEI/XML Greek editions** "
        f"(**{perseus_n:,}** from Perseus `canonical-greekLit` and **{first1k_n:,}** from `First1KGreek`, "
        "CC BY-SA 4.0, commit-pinned and cached on first load).",
        "",
        'Load any work by its CTS ID with `aegean.greek.load_work("<id>")`, `aegean.open("<id>")`, '
        "or `aegean greek work <id>` (supports section slices like `--ref 1.1-1.50` and Stephanus/Bekker "
        "milestones). See [Greek Works & Books](Greek-Works-and-Books) for citation addressing.",
        "",
        "| CTS ID | Author | Title | Greek Title | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for w in rows:
        gtitle = _esc(w.get("greek_title", ""))
        if gtitle == _esc(w.get("title", "")):
            gtitle = ""
        lines.append(
            f"| `{_esc(w['id'])}` | {_esc(w.get('author', ''))} | {_esc(w.get('title', ''))} | "
            f"{gtitle} | `{_esc(w['source'])}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extra-json",
        type=Path,
        default=None,
        help="Optional pre-extracted extra_corpora.json (avoids fetching hosted corpora)",
    )
    args = parser.parse_args()

    facts = _load_corpus_facts()
    extra = _load_extra_corpora(args.extra_json)

    pages: dict[str, str] = {
        "Catalog.md": _build_overview(facts, extra),
        "Catalog-Aegean-and-Epigraphy.md": _build_aegean_and_epigraphy(facts, extra),
        "Catalog-Biblical.md": _build_biblical(extra),
        "Catalog-Chrysostom.md": _build_chrysostom(),
        "Catalog-Church-Fathers.md": _build_church_fathers(extra),
        "Catalog-Classical-Greek.md": _build_classical_greek(extra),
        "Catalog-Hellenistic-Greek.md": _build_single_collection_page(
            "hellenistic-greek",
            "Hellenistic Greek & Fragmentary Historians",
            "Hosted in `hellenistic-greek-corpus` (~16.3 MB, 3rd–1st c. BCE): Hellenistic poetry, "
            "historiography, mathematics and science, Jewish-Greek literature (Philo, Aristeas), "
            "and Digital Fragmenta Historicorum Graecorum (DFHG).",
            "aegean library install hellenistic-greek-corpus",
        ),
        "Catalog-Imperial-Greek.md": _build_single_collection_page(
            "imperial-greek",
            "Imperial Greek Literature, Philosophy & Medicine",
            "Hosted in `imperial-greek-corpus` (~50.2 MB, 1st–3rd c. CE): Imperial literature, "
            "biographies, philosophy, medicine, rhetoric, and geography (Plutarch, Galen, Lucian, "
            "Josephus, Epictetus, Marcus Aurelius, Cassius Dio, Pausanias, Athenaeus, Sextus Empiricus).",
            "aegean library install imperial-greek-corpus",
        ),
        "Catalog-Late-Antique-and-Byzantine.md": _build_late_antique_and_byzantine(extra),
        "Catalog-Perseus-and-First1K.md": _build_perseus_and_first1k(),
    }

    for fname, content in pages.items():
        out = WIKI_DIR / fname
        out.write_text(content, encoding="utf-8", newline="\n")
        kb = out.stat().st_size / 1024.0
        print(f"Wrote wiki/{fname:40s} ({kb:6.1f} KB, {content.count(chr(10)):5d} lines)")


if __name__ == "__main__":
    main()
