"""Unified corpus, text, lexicon, and model manager for pyaegean.

Provides one consistent interface across Python, the CLI (``aegean library``),
the interactive REPL, and the TUI for discovering, inspecting, downloading, and
removing every resource pyaegean supports:

- **Bundled corpora** (5): Linear A, Linear B sample, Cypriot, Cypro-Minoan,
  Greek sample texts.
- **Downloadable corpora** (9): DAMOS Linear B, SigLA Linear A, Greek New
  Testament (Nestle 1904), I.Sicily, IIP, IOSPE, IGCyr/GVCyr, EDH, DDbDP.
- **Biblical & Koine Greek bundles** (5): ``nt-corpus``, ``nt-editions``
  (SBLGNT, SRGNT, Byzantine Majority, Textus Receptus), ``nt-witnesses``
  (13 early 2nd–5th c. CE uncials and papyri), ``strongs-greek`` (11,142
  Extended Strong's entries), and ``lxx-corpus`` (55 Swete Septuagint books).
- **Greek literary works** (~1,778): Perseus ``canonical-greekLit`` and
  ``First1KGreek`` TEI editions.
- **Greek patristic commentaries** (48): 30 NT *Catenae* volumes and 18 Origen
  biblical commentaries.
- **Lexica** (5): LSJ, Middle Liddell, Cunliffe, Autenrieth, Abbott-Smith.
- **Models & tables** (4): ``grc-joint``, ``grc-lemma-neural``, ``agdt-derived``,
  ``grc-paradigms``.
- **Named packs** (5): ``biblical``, ``aegean``, ``epigraphy``, ``lexica``,
  ``neural`` for one-command installation of related assets.

No non-stdlib dependencies; lazily exported as ``aegean.library``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "CATEGORIES",
    "InstallResult",
    "LibraryItem",
    "LibraryPack",
    "PACKS",
    "PackStatus",
    "RemoveResult",
    "format_size",
    "get_item",
    "get_pack",
    "install",
    "list_items",
    "list_packs",
    "missing_for_bible",
    "missing_for_corpus",
    "remove",
    "resolve_targets",
    "search",
    "summary",
]

CATEGORIES: tuple[str, ...] = (
    "corpus",
    "bible",
    "work",
    "commentary",
    "lexicon",
    "model",
    "other",
)

_SIZE_RE = re.compile(r"(~?\d+(?:\.\d+)?\s*(?:GB|MB|KB|kB|B))")
_TLG_RE = re.compile(r"^tlg\d+\.tlg\d+$", re.IGNORECASE)


def format_size(n: int | None) -> str:
    """Format a byte count as a compact human-readable string."""
    if n is None:
        return ""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


@dataclass(frozen=True, slots=True)
class LibraryItem:
    """One resource managed by :mod:`aegean.library`."""

    id: str
    title: str
    category: str
    kind: str  # "bundled" | "dataset" | "work"
    status: str  # "bundled" | "installed" | "available"
    bytes: int | None
    size_hint: str
    license: str
    description: str
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    asset_name: str | None = None
    work_id: str | None = None
    open_spec: str | None = None
    author: str = ""
    greek_title: str = ""
    source: str = ""

    @property
    def installed(self) -> bool:
        """Whether this item is currently available offline on disk."""
        return self.status in ("bundled", "installed")

    @property
    def removable(self) -> bool:
        """Whether this item can be deleted from the local store."""
        return self.kind != "bundled" and self.status == "installed"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["installed"] = self.installed
        d["removable"] = self.removable
        return d


@dataclass(frozen=True, slots=True)
class LibraryPack:
    """A named collection of related downloadable items."""

    id: str
    title: str
    description: str
    items: tuple[str, ...]
    size_hint: str
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PackStatus:
    """Runtime installation status for a :class:`LibraryPack`."""

    pack: LibraryPack
    installed_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    installed_bytes: int

    @property
    def total_count(self) -> int:
        return len(self.pack.items)

    @property
    def installed_count(self) -> int:
        return len(self.installed_ids)

    @property
    def complete(self) -> bool:
        return len(self.missing_ids) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.pack.to_dict(),
            "installed_ids": list(self.installed_ids),
            "missing_ids": list(self.missing_ids),
            "installed_count": self.installed_count,
            "total_count": self.total_count,
            "installed_bytes": self.installed_bytes,
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Outcome of installing one item."""

    id: str
    title: str
    kind: str
    status: str  # "installed" | "already_installed" | "bundled" | "failed"
    path: str | None = None
    bytes: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RemoveResult:
    """Outcome of removing one item."""

    id: str
    title: str
    kind: str
    status: str  # "removed" | "not_installed" | "bundled" | "failed"
    bytes_reclaimed: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Static metadata tables (zero network, instant offline lookups) ───────────

_BUNDLED_CORPORA: tuple[dict[str, Any], ...] = (
    {
        "id": "lineara",
        "title": "Linear A Corpus (GORILA)",
        "description": "148 Linear A inscriptions (bundled offline).",
        "license": "Apache-2.0 / public academic transcriptions",
        "aliases": ("linear-a", "la"),
        "open_spec": "lineara",
    },
    {
        "id": "linearb",
        "title": "Linear B Sample Tablets",
        "description": "12 Mycenaean Greek Linear B sample tablets (bundled offline).",
        "license": "Apache-2.0 / public academic transcriptions",
        "aliases": ("linear-b", "lb"),
        "open_spec": "linearb",
    },
    {
        "id": "cypriot",
        "title": "Cypriot Syllabary Corpus",
        "description": "6 Classical Cypriot Greek syllabic inscriptions (bundled offline).",
        "license": "Apache-2.0 / public academic transcriptions",
        "aliases": ("cypriot-syllabary",),
        "open_spec": "cypriot",
    },
    {
        "id": "cyprominoan",
        "title": "Cypro-Minoan Corpus",
        "description": "9 Cypro-Minoan inscriptions (bundled offline).",
        "license": "Apache-2.0 / public academic transcriptions",
        "aliases": ("cypro-minoan", "cm"),
        "open_spec": "cyprominoan",
    },
    {
        "id": "greek",
        "title": "Ancient Greek Sample Texts",
        "description": "5 Ancient Greek sample passages (bundled offline).",
        "license": "Apache-2.0 / public domain texts",
        "aliases": ("greek-sample",),
        "open_spec": "greek",
    },
)

# Dataset id -> (title, primary_category, extra_tags, aliases, open_spec, default_size_hint)
_DATASET_META: dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...], str | None, str]] = {
    # Biblical & Koine Greek
    "nt-corpus": (
        "Greek New Testament (Nestle 1904, 27 books)",
        "bible",
        ("bible", "corpus"),
        ("nt", "nestle1904", "gnt", "new-testament"),
        "nt",
        "~18 MB",
    ),
    "nt-editions": (
        "Greek NT Multi-Edition Bundle (8 editions: SBLGNT, SRGNT, BHP, Tisch, WH, BYZ, Antoniades, TR)",
        "bible",
        ("bible",),
        ("editions", "sblgnt", "srgnt", "bhp", "tisch", "tischendorf", "wh", "byz", "antoniades", "tr"),
        None,
        "~3.3 MB",
    ),
    "nt-witnesses": (
        "Early Greek NT Manuscripts (13 uncials & papyri)",
        "bible",
        ("bible",),
        ("witnesses", "manuscripts", "mss", "papyri", "sinaiticus", "vaticanus"),
        None,
        "~2.0 MB",
    ),
    "strongs-greek": (
        "Extended Strong's Greek Lexicon (11,142 entries)",
        "bible",
        ("bible", "lexicon"),
        ("strongs", "strong", "tbesg"),
        None,
        "~1.5 MB",
    ),
    "lxx-corpus": (
        "Swete Septuagint / LXX (55 Greek OT books)",
        "bible",
        ("bible", "corpus"),
        ("lxx", "septuagint", "swete"),
        None,
        "~1.7 MB",
    ),
    "apostolic-fathers-corpus": (
        "Open Apostolic Fathers (15 hand-corrected Greek works)",
        "bible",
        ("bible", "corpus", "commentary"),
        ("apostolic-fathers", "af", "didache", "clement", "ignatius"),
        "apostolic-fathers",
        "~1.0 MB",
    ),
    "pseudepigrapha-corpus": (
        "Greek Old Testament Pseudepigrapha (44 OCP Second Temple works)",
        "bible",
        ("bible", "corpus"),
        ("pseudepigrapha", "ocp", "enoch", "sibylline"),
        "pseudepigrapha",
        "~2.7 MB",
    ),
    "patrologia-graeca-corpus": (
        "Patrologia Graeca (33 CGPG volumes, 6.79M words; 9 commentary vols)",
        "commentary",
        ("commentary", "bible", "corpus"),
        ("patrologia", "pg", "church-fathers", "cyril", "theophylact"),
        "patrologia",
        "~23.5 MB",
    ),
    # Aegean & Epigraphy / Papyri / Literary corpora
    "damos-corpus": (
        "DAMOS Linear B Corpus (~5,900 tablets)",
        "corpus",
        ("corpus",),
        ("damos",),
        "damos",
        "~3.0 MB",
    ),
    "sigla-corpus": (
        "SigLA Linear A Corpus (802 documents)",
        "corpus",
        ("corpus",),
        ("sigla",),
        "sigla",
        "~1.3 MB",
    ),
    "isicily-corpus": (
        "I.Sicily Greek Inscriptions (2,855 texts)",
        "corpus",
        ("corpus",),
        ("isicily", "sicily"),
        "isicily",
        "~2.5 MB",
    ),
    "iip-corpus": (
        "IIP Greek Inscriptions of Israel/Palestine (2,113 texts)",
        "corpus",
        ("corpus",),
        ("iip",),
        "iip",
        "~1.5 MB",
    ),
    "iospe-corpus": (
        "IOSPE Northern Black Sea Inscriptions (1,194 texts)",
        "corpus",
        ("corpus",),
        ("iospe",),
        "iospe",
        "~1.5 MB",
    ),
    "igcyr-corpus": (
        "IGCyr/GVCyr Inscriptions of Cyrenaica (997 texts)",
        "corpus",
        ("corpus",),
        ("igcyr", "cyrenaica"),
        "igcyr",
        "~1.5 MB",
    ),
    "aphrodisias-corpus": (
        "Inscriptions of Aphrodisias (IAph2007, 1,471 texts)",
        "corpus",
        ("corpus",),
        ("aphrodisias", "iaph", "iaph2007"),
        "aphrodisias",
        "~0.5 MB",
    ),
    "crete-corpus": (
        "Cretan Institutional Inscriptions (600 Archaic–Hellenistic texts)",
        "corpus",
        ("corpus",),
        ("crete", "cretan"),
        "crete",
        "~0.6 MB",
    ),
    "edh-corpus": (
        "EDH Greek Inscriptions (1,286 texts)",
        "corpus",
        ("corpus",),
        ("edh",),
        "edh",
        "~1.0 MB",
    ),
    "ddbdp-corpus": (
        "DDbDP Greek Documentary Papyri (57,331 texts, SQLite)",
        "corpus",
        ("corpus",),
        ("ddbdp", "papyri-db"),
        "ddbdp",
        "~219 MB",
    ),
    "byzantine-corpus": (
        "Byzantine & Early Modern Vernacular Greek (12 works, 189K tokens)",
        "corpus",
        ("corpus",),
        ("byzantine", "byz-vernacular", "digenes", "erotokritos"),
        "byzantine",
        "~2.5 MB",
    ),
    "homer-scholia-corpus": (
        "Homer Multitext Venetus A Iliad & Scholia (54 docs, 331K tokens)",
        "corpus",
        ("corpus", "commentary"),
        ("homer-scholia", "hmt", "venetus-a", "scholia"),
        "homer-scholia",
        "~5.5 MB",
    ),
    # Lexica
    "lsj-index": (
        "Liddell-Scott-Jones (LSJ) Greek Lexicon",
        "lexicon",
        ("lexicon",),
        ("lsj",),
        None,
        "~15 MB",
    ),
    "middle-liddell-index": (
        "Middle Liddell Greek Lexicon",
        "lexicon",
        ("lexicon",),
        ("middle-liddell", "ml"),
        None,
        "~2.3 MB",
    ),
    "cunliffe-index": (
        "Cunliffe Homeric Greek Lexicon",
        "lexicon",
        ("lexicon",),
        ("cunliffe",),
        None,
        "~1.3 MB",
    ),
    "autenrieth-index": (
        "Autenrieth Homeric Greek Lexicon",
        "lexicon",
        ("lexicon",),
        ("autenrieth",),
        None,
        "~0.6 MB",
    ),
    "abbott-smith-index": (
        "Abbott-Smith Manual Greek Lexicon of the NT",
        "lexicon",
        ("lexicon", "bible"),
        ("abbott-smith",),
        None,
        "~130 KB",
    ),
    # Models & linguistic tables
    "grc-joint": (
        "Joint Neural Greek Tagger/Parser/Lemmatizer (grc-joint-v3)",
        "model",
        ("model",),
        ("joint", "neural-joint"),
        None,
        "~173 MB",
    ),
    "grc-lemma-neural": (
        "Neural Greek Seq2Seq Lemmatizer (GreTa ONNX)",
        "model",
        ("model",),
        ("lemma-neural", "greta"),
        None,
        "~232 MB",
    ),
    "agdt-derived": (
        "AGDT Prebuilt Lexicon, Tagger, Lemmatizer & Parser",
        "model",
        ("model",),
        ("agdt",),
        None,
        "~10 MB",
    ),
    "grc-paradigms": (
        "UniMorph Ancient Greek Paradigm Table",
        "model",
        ("model",),
        ("paradigms", "unimorph"),
        None,
        "~234 KB",
    ),
    # Other / media / eval folds
    "lineara-images": (
        "Linear A Facsimile & Photo Archive (3,368 files)",
        "other",
        ("other",),
        ("images", "facsimiles"),
        None,
        "~116 MB",
    ),
    "workbench-app": (
        "Linear A Research Workbench Web App",
        "other",
        ("other",),
        ("workbench",),
        None,
        "~3 MB",
    ),
    "ddbdp-uris": (
        "DDbDP Document-URI Map (for RDF export)",
        "other",
        ("other",),
        (),
        None,
        "~337 KB",
    ),
    "linearb-corpus": (
        "Bring-Your-Own Linear B Export Slot",
        "other",
        ("other",),
        (),
        None,
        "BYO",
    ),
}

PACKS: tuple[LibraryPack, ...] = (
    LibraryPack(
        id="biblical",
        title="Biblical & Koine Greek Pack",
        description=(
            "Full 27-book Greek NT (Nestle 1904), 8 additional editions (SBLGNT, SRGNT, BHP, "
            "Tischendorf 8th, Westcott-Hort, Byzantine Majority, Antoniades 1904, TR), 13 early "
            "manuscripts, Extended Strong's (11,142 entries), and all 55 Swete Septuagint books."
        ),
        items=("nt-corpus", "nt-editions", "nt-witnesses", "strongs-greek", "lxx-corpus"),
        size_hint="~27 MB",
        aliases=("bible", "koine", "nt-all"),
    ),
    LibraryPack(
        id="patristic",
        title="Patristic & Second Temple Pack",
        description=(
            "Open Apostolic Fathers (15 works), Greek Old Testament Pseudepigrapha (44 works), "
            "and Patrologia Graeca (33 volumes, 6.79M words, incl. 9 biblical commentary vols)."
        ),
        items=(
            "apostolic-fathers-corpus",
            "pseudepigrapha-corpus",
            "patrologia-graeca-corpus",
        ),
        size_hint="~27.2 MB",
        aliases=("fathers", "church-fathers", "second-temple"),
    ),
    LibraryPack(
        id="aegean",
        title="Aegean Scripts Pack",
        description="Full DAMOS Linear B (~5,900 tablets) and SigLA Linear A (802 documents).",
        items=("damos-corpus", "sigla-corpus"),
        size_hint="~4.3 MB",
        aliases=("scripts", "linear"),
    ),
    LibraryPack(
        id="epigraphy",
        title="Greek Epigraphy Pack",
        description=(
            "All 7 Greek inscription corpora: I.Sicily, IIP, IOSPE, IGCyr/GVCyr, "
            "Aphrodisias (IAph2007), Crete (Cretan Institutional Inscriptions), and EDH."
        ),
        items=(
            "isicily-corpus",
            "iip-corpus",
            "iospe-corpus",
            "igcyr-corpus",
            "aphrodisias-corpus",
            "crete-corpus",
            "edh-corpus",
        ),
        size_hint="~9.1 MB",
        aliases=("inscriptions",),
    ),
    LibraryPack(
        id="literary",
        title="Greek Literary & Scholia Pack",
        description=(
            "Homer Multitext Venetus A Iliad & Homeric Scholia (54 docs, 331K tokens) and "
            "Byzantine & Early Modern Vernacular Greek (12 works, 189K tokens)."
        ),
        items=("homer-scholia-corpus", "byzantine-corpus"),
        size_hint="~8.0 MB",
        aliases=("epic", "scholia", "byzantine-lit"),
    ),
    LibraryPack(
        id="lexica",
        title="Greek Dictionaries Pack",
        description="All 5 hosted Greek lexica: LSJ, Middle Liddell, Cunliffe, Autenrieth, Abbott-Smith.",
        items=(
            "lsj-index",
            "middle-liddell-index",
            "cunliffe-index",
            "autenrieth-index",
            "abbott-smith-index",
        ),
        size_hint="~19.3 MB",
        aliases=("dictionaries", "lexicons"),
    ),
    LibraryPack(
        id="neural",
        title="Greek Neural NLP Pack",
        description="Joint neural tagger/parser/lemmatizer (grc-joint-v3) + UniMorph paradigms.",
        items=("grc-joint", "grc-paradigms"),
        size_hint="~173 MB",
        aliases=("models", "nlp"),
    ),
)


# ── Internal catalog builders ────────────────────────────────────────────────


def _extract_size_hint(note: str, fallback: str) -> str:
    m = _SIZE_RE.search(note or "")
    return m.group(1) if m else fallback


def _bundled_items() -> list[LibraryItem]:
    return [
        LibraryItem(
            id=row["id"],
            title=row["title"],
            category="corpus",
            kind="bundled",
            status="bundled",
            bytes=None,
            size_hint="bundled",
            license=row["license"],
            description=row["description"],
            aliases=tuple(row["aliases"]),
            tags=("corpus",),
            open_spec=row["open_spec"],
            source="bundled",
        )
        for row in _BUNDLED_CORPORA
    ]


def _dataset_items(*, root: Path | None = None) -> list[LibraryItem]:
    from .data import _REMOTE, cache_dir, downloaded_bytes, is_downloaded

    store_root = cache_dir() if root is None else root
    out: list[LibraryItem] = []
    for name, spec in sorted(_REMOTE.items()):
        meta = _DATASET_META.get(name)
        if meta is not None:
            title, category, tags, aliases, open_spec, default_hint = meta
        else:
            title = name
            category = "other"
            tags = ("other",)
            aliases = ()
            open_spec = None
            default_hint = "remote"
        downloaded = is_downloaded(spec, store_root)
        nbytes = downloaded_bytes(spec, store_root) if downloaded else None
        out.append(
            LibraryItem(
                id=name,
                title=title,
                category=category,
                kind="dataset",
                status="installed" if downloaded else "available",
                bytes=nbytes,
                size_hint=_extract_size_hint(spec.note, default_hint),
                license=spec.license,
                description=spec.note,
                aliases=aliases,
                tags=tags,
                asset_name=name,
                open_spec=open_spec,
                source="pyaegean-release",
            )
        )
    return out


def _work_items(*, installed_only: bool = False) -> list[LibraryItem]:
    from .greek.bible._catalogs import patristic_commentaries
    from .scripts.greek.perseus import POPULAR_WORKS, catalog, list_fetched_works

    fetched = {w["id"]: w for w in list_fetched_works()}
    commentaries = {c["work_id"]: c for c in patristic_commentaries()}
    popular_titles = {w["id"]: w["title"] for w in POPULAR_WORKS}

    out: list[LibraryItem] = []
    seen: set[str] = set()
    for w in catalog():
        wid = w["id"]
        hit = fetched.get(wid)
        if installed_only and hit is None:
            continue
        seen.add(wid)
        comm = commentaries.get(wid)
        author = w.get("author", "")
        title = w.get("title", "")
        gtitle = w.get("greek_title", "")
        src = w.get("source", "")
        aliases: list[str] = []
        if wid in popular_titles:
            aliases.append(popular_titles[wid])
        if comm is not None:
            category = "commentary"
            tags: tuple[str, ...] = ("commentary", "work", "bible")
            display = f"{comm['author']} — {comm['title']}"
            desc = f"Greek patristic commentary on {comm['book']} ({comm['kind']}; {src})."
            aliases.append(f"commentary:{comm['book']}")
        else:
            category = "work"
            tags = ("work",)
            display = f"{author} — {title}".strip(" —") or wid
            desc = f"Greek literary edition ({src}; CTS {wid})."
        lic = (
            "CC BY-SA 4.0 (Perseus Digital Library)"
            if src == "perseus"
            else "CC BY-SA 4.0 (Open Greek and Latin, First1KGreek)"
        )
        out.append(
            LibraryItem(
                id=wid,
                title=display,
                category=category,
                kind="work",
                status="installed" if hit is not None else "available",
                bytes=int(hit["bytes"]) if hit is not None else None,
                size_hint="TEI XML",
                license=lic,
                description=desc,
                aliases=tuple(aliases),
                tags=tags,
                work_id=wid,
                open_spec=wid,
                author=author,
                greek_title=gtitle,
                source=src,
            )
        )

    # Also include any commentary IDs not in the bundled catalogue (defensive)
    if not installed_only:
        for wid, comm in commentaries.items():
            if wid in seen:
                continue
            hit = fetched.get(wid)
            out.append(
                LibraryItem(
                    id=wid,
                    title=f"{comm['author']} — {comm['title']}",
                    category="commentary",
                    kind="work",
                    status="installed" if hit is not None else "available",
                    bytes=int(hit["bytes"]) if hit is not None else None,
                    size_hint="TEI XML",
                    license="CC BY-SA 4.0 (Open Greek and Latin, First1KGreek)",
                    description=f"Greek patristic commentary on {comm['book']} ({comm['kind']}).",
                    aliases=(f"commentary:{comm['book']}",),
                    tags=("commentary", "work", "bible"),
                    work_id=wid,
                    open_spec=wid,
                    author=comm["author"],
                    source="first1k",
                )
            )
    return out


# ── Public query & discovery API ─────────────────────────────────────────────


def get_pack(name: str) -> LibraryPack | None:
    """Look up a named pack by id or alias (case-insensitive)."""
    needle = name.strip().lower()
    if not needle:
        return None
    for pack in PACKS:
        if pack.id == needle or needle in (a.lower() for a in pack.aliases):
            return pack
    return None


def list_packs(*, root: Path | None = None) -> list[PackStatus]:
    """Return runtime installation status for every named pack."""
    by_id = {item.id: item for item in _dataset_items(root=root)}
    out: list[PackStatus] = []
    for pack in PACKS:
        installed: list[str] = []
        missing: list[str] = []
        total_bytes = 0
        for iid in pack.items:
            item = by_id.get(iid)
            if item is not None and item.installed:
                installed.append(iid)
                total_bytes += item.bytes or 0
            else:
                missing.append(iid)
        out.append(
            PackStatus(
                pack=pack,
                installed_ids=tuple(installed),
                missing_ids=tuple(missing),
                installed_bytes=total_bytes,
            )
        )
    return out


def list_items(
    *,
    category: str | None = None,
    status: str | None = None,
    query: str | None = None,
    include_works: bool = False,
    limit: int | None = None,
    root: Path | None = None,
) -> list[LibraryItem]:
    """List library items with optional category, status, and substring filters.

    Parameters
    ----------
    category:
        One of ``"corpus"``, ``"bible"``, ``"work"``, ``"commentary"``,
        ``"lexicon"``, ``"model"``, ``"other"`` (or ``None`` for all).
    status:
        ``"installed"`` (includes bundled + downloaded), ``"downloaded"``
        (downloaded only, excluding bundled), ``"bundled"``, or ``"available"``
        (not yet downloaded).
    query:
        Case-insensitive substring filter across id, title, author, Greek title,
        aliases, and description. Passing a query searches across all 1,778+
        literary works and commentaries automatically.
    include_works:
        When ``False`` (default) and ``category`` is ``None`` and ``query`` is
        empty, includes all corpora, biblical bundles, lexica, models, other
        datasets, and *installed* works/commentaries without dumping 1,778
        uninstalled works. Set ``True`` or pass ``category="work"`` to include
        the full catalogue.
    limit:
        Optional maximum number of items to return.
    """
    cat = category.strip().lower() if category else None
    if cat is not None and cat not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}; choose from {', '.join(CATEGORIES)}")

    st = status.strip().lower() if status else None
    if st is not None and st not in ("installed", "downloaded", "bundled", "available"):
        raise ValueError(
            f"unknown status {status!r}; choose from 'installed', 'downloaded', 'bundled', 'available'"
        )

    need_all_works = (
        include_works
        or bool(query and query.strip())
        or cat in ("work", "commentary")
    )

    items: list[LibraryItem] = []
    if cat in (None, "corpus"):
        items.extend(_bundled_items())
    if cat not in ("work", "commentary"):
        items.extend(_dataset_items(root=root))
    if need_all_works:
        items.extend(_work_items(installed_only=False))
    elif cat in (None, "bible"):
        items.extend(_work_items(installed_only=True))

    if cat is not None:
        items = [it for it in items if it.category == cat or cat in it.tags]

    if st == "installed":
        items = [it for it in items if it.installed]
    elif st == "downloaded":
        items = [it for it in items if it.status == "installed"]
    elif st == "bundled":
        items = [it for it in items if it.status == "bundled"]
    elif st == "available":
        items = [it for it in items if it.status == "available"]

    if query and query.strip():
        needle = query.strip().lower()
        scored: list[tuple[int, LibraryItem]] = []
        for it in items:
            score = _match_score(it, needle)
            if score > 0:
                scored.append((score, it))
        scored.sort(key=lambda pair: (-pair[0], pair[1].category, pair[1].id))
        items = [it for _, it in scored]

    if limit is not None and limit > 0:
        return items[:limit]
    return items


def _match_score(item: LibraryItem, needle: str) -> int:
    """Rank relevance for search queries (higher is better; 0 = no match)."""
    if item.id.lower() == needle:
        return 100
    if any(a.lower() == needle for a in item.aliases):
        return 95
    if item.id.lower().startswith(needle):
        return 85
    if item.title.lower().startswith(needle) or item.author.lower().startswith(needle):
        return 75
    if any(a.lower().startswith(needle) for a in item.aliases):
        return 70
    if needle in item.title.lower() or needle in item.author.lower():
        return 60
    if item.greek_title and needle in item.greek_title.lower():
        return 55
    if needle in item.id.lower():
        return 50
    if needle in item.description.lower():
        return 30
    return 0


def search(
    query: str,
    *,
    category: str | None = None,
    status: str | None = None,
    limit: int = 50,
    root: Path | None = None,
) -> list[LibraryItem]:
    """Search across all corpora, biblical bundles, literary works, commentaries,
    lexica, and models."""
    q = query.strip()
    if not q:
        return list_items(category=category, status=status, limit=limit, root=root)
    return list_items(
        category=category,
        status=status,
        query=q,
        include_works=True,
        limit=limit,
        root=root,
    )


def get_item(identifier: str, *, root: Path | None = None) -> LibraryItem | None:
    """Look up a single library item by canonical id or unambiguous alias."""
    raw = identifier.strip()
    if not raw:
        return None
    needle = raw.lower()

    # Fast path: bundled & datasets (~37 items, zero catalogue load)
    for it in _bundled_items() + _dataset_items(root=root):
        if it.id.lower() == needle or needle in (a.lower() for a in it.aliases):
            return it

    # TLG work id or unique popular-work title
    if _TLG_RE.match(raw):
        for it in _work_items(installed_only=False):
            if it.id.lower() == needle:
                return it
        return None

    # Check exact popular work title or unique catalogue work title
    works = _work_items(installed_only=False)
    for it in works:
        if any(a.lower() == needle for a in it.aliases):
            return it
    exact_title = [
        it
        for it in works
        if it.title.lower() == needle or it.title.split(" — ", 1)[-1].lower() == needle
    ]
    if len(exact_title) == 1:
        return exact_title[0]
    return None


def resolve_targets(
    targets: str | Sequence[str],
    *,
    root: Path | None = None,
) -> list[LibraryItem]:
    """Resolve one or more user-friendly target strings to canonical :class:`LibraryItem`s.

    Accepts:
    - pack names/aliases (``"biblical"``, ``"bible"``, ``"epigraphy"``, ``"aegean"``,
      ``"lexica"``, ``"neural"``);
    - canonical dataset or corpus IDs (``"nt-editions"``, ``"damos-corpus"``, ``"lineara"``);
    - friendly aliases/stems (``"editions"``, ``"byz"``, ``"lxx"``, ``"strongs"``,
      ``"witnesses"``, ``"damos"``, ``"isicily"``, ``"lsj"``);
    - CTS TLG work IDs (``"tlg0012.tlg001"``, ``"tlg4102.tlg001"``);
    - popular or unique work titles (``"Iliad"``, ``"Odyssey"``, ``"Republic"``);
    - ``"author:<name>"`` to select all works by an author (e.g. ``"author:Homer"``);
    - ``"commentary:<book>"`` to select all patristic commentary volumes for a book.

    Raises ``LookupError`` with close suggestions when a target cannot be resolved
    or is ambiguous.
    """
    raw_list = [targets] if isinstance(targets, str) else list(targets)
    if not raw_list:
        raise LookupError("specify at least one pack, corpus, dataset, or work to target")

    datasets_by_id = {it.id: it for it in _dataset_items(root=root)}
    resolved: list[LibraryItem] = []
    seen_ids: set[str] = set()

    def _add(item: LibraryItem) -> None:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            resolved.append(item)

    for raw in raw_list:
        token = raw.strip()
        if not token:
            continue
        lower = token.lower()

        # 1. Named pack
        pack = get_pack(lower)
        if pack is not None:
            for iid in pack.items:
                if iid in datasets_by_id:
                    _add(datasets_by_id[iid])
            continue

        # 2. author:<name>
        if lower.startswith("author:"):
            author_q = token.split(":", 1)[1].strip().lower()
            if not author_q:
                raise LookupError("specify an author name after 'author:', e.g. 'author:Homer'")
            matches = [
                it for it in _work_items(installed_only=False) if author_q in it.author.lower()
            ]
            if not matches:
                raise LookupError(f"no Greek works found for author {author_q!r}")
            for it in matches:
                _add(it)
            continue

        # 3. commentary:<book> or catena:<book>
        if lower.startswith(("commentary:", "catena:")):
            bk_q = token.split(":", 1)[1].strip()
            from .greek.bible._catalogs import patristic_commentaries

            try:
                comms = patristic_commentaries(bk_q) if bk_q else patristic_commentaries()
            except ValueError as exc:
                raise LookupError(str(exc)) from None
            wanted = {c["work_id"] for c in comms}
            for it in _work_items(installed_only=False):
                if it.id in wanted:
                    _add(it)
            continue

        # 4. Exact / alias / unique title item lookup
        item = get_item(token, root=root)
        if item is not None:
            _add(item)
            continue

        # 5. Did-you-mean suggestions (packs + items + works search)
        hints = _suggest_targets(token, root=root)
        if hints:
            raise LookupError(
                f"unknown or ambiguous target {token!r} — did you mean: {', '.join(hints)}? "
                "(run `aegean library search <query>` to browse)"
            )
        raise LookupError(
            f"unknown target {token!r}; run `aegean library list` or `aegean library search <query>`"
        )

    return resolved


def _suggest_targets(token: str, *, root: Path | None = None) -> list[str]:
    from .core.resolve import suggest

    candidates: dict[str, str] = {}
    for p in PACKS:
        candidates[p.id] = f"{p.id} (pack)"
        for a in p.aliases:
            candidates.setdefault(a, f"{p.id} (pack)")
    for it in _bundled_items() + _dataset_items(root=root):
        candidates[it.id] = it.id
        for a in it.aliases:
            candidates.setdefault(a, it.id)
    out: list[str] = []
    for m in suggest(token.lower(), candidates, n=4):
        label = candidates[m]
        if label not in out:
            out.append(label)
    if len(out) < 4:
        for it in search(token, limit=4, root=root):
            label = f"{it.id} ({it.title})"
            if label not in out:
                out.append(label)
            if len(out) >= 4:
                break
    return out


# ── Install / Remove operations ──────────────────────────────────────────────


def install(
    targets: str | Sequence[str],
    *,
    force: bool = False,
    progress: Callable[[str], None] | None = None,
    byte_progress: Callable[[int, int], None] | None = None,
    abort: Callable[[], bool] | None = None,
    root: Path | None = None,
) -> list[InstallResult]:
    """Install one or more packs, datasets, corpora, literary works, or commentaries.

    Accepts any target string recognized by :func:`resolve_targets`. Bundled
    items and already-installed items (when ``force=False``) are skipped
    cleanly without hitting the network.
    """
    from .data import DataNotAvailableError, FetchAborted, fetch
    from .scripts.greek.perseus import list_fetched_works, load_work

    items = resolve_targets(targets, root=root)
    results: list[InstallResult] = []
    total = len(items)

    for idx, item in enumerate(items, start=1):
        if abort is not None and abort():
            raise FetchAborted("install canceled")

        prefix = f"[{idx}/{total}] " if total > 1 else ""
        if item.kind == "bundled":
            results.append(
                InstallResult(
                    id=item.id,
                    title=item.title,
                    kind=item.kind,
                    status="bundled",
                )
            )
            continue

        if item.installed and not force:
            results.append(
                InstallResult(
                    id=item.id,
                    title=item.title,
                    kind=item.kind,
                    status="already_installed",
                    bytes=item.bytes,
                )
            )
            continue

        if progress is not None:
            progress(f"{prefix}downloading {item.id} ({item.size_hint})…")

        if item.kind == "dataset" and item.asset_name is not None:
            try:
                path = fetch(
                    item.asset_name,
                    force=force,
                    abort=abort,
                    progress=byte_progress,
                )
            except FetchAborted:
                raise
            except (DataNotAvailableError, Exception) as exc:
                results.append(
                    InstallResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="failed",
                        error=str(exc),
                    )
                )
                continue
            from .data import _REMOTE, cache_dir, downloaded_bytes

            spec = _REMOTE.get(item.asset_name)
            nbytes = downloaded_bytes(spec, cache_dir()) if spec is not None else None
            results.append(
                InstallResult(
                    id=item.id,
                    title=item.title,
                    kind=item.kind,
                    status="installed",
                    path=str(path),
                    bytes=nbytes,
                )
            )
            if progress is not None:
                progress(f"{prefix}installed {item.id} ({format_size(nbytes)})")
            continue

        if item.kind == "work" and item.work_id is not None:
            try:
                load_work(item.work_id, force=force)
            except FetchAborted:
                raise
            except Exception as exc:
                results.append(
                    InstallResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="failed",
                        error=str(exc),
                    )
                )
                continue
            hit = next((w for w in list_fetched_works() if w["id"] == item.work_id), None)
            nbytes = int(hit["bytes"]) if hit is not None else None
            path_str = str(hit["path"]) if hit is not None else None
            results.append(
                InstallResult(
                    id=item.id,
                    title=item.title,
                    kind=item.kind,
                    status="installed",
                    path=path_str,
                    bytes=nbytes,
                )
            )
            if progress is not None:
                progress(f"{prefix}installed {item.id} ({format_size(nbytes)})")
            continue

    return results


def remove(
    targets: str | Sequence[str] | None = None,
    *,
    remove_all: bool = False,
    root: Path | None = None,
) -> list[RemoveResult]:
    """Remove downloaded datasets, corpora, works, commentaries, or packs from disk.

    Bundled items are never deleted and report ``status="bundled"``. When
    ``remove_all=True``, removes every downloaded dataset and downloaded Greek
    work/commentary from the local store.
    """
    from .data import DataNotAvailableError, remove_dataset
    from .scripts.greek.perseus import remove_fetched_works

    if remove_all:
        items = [it for it in list_items(status="downloaded", include_works=True, root=root)]
    elif targets is not None:
        items = resolve_targets(targets, root=root)
    else:
        raise ValueError("specify at least one target to remove, or pass remove_all=True")

    results: list[RemoveResult] = []
    for item in items:
        if item.kind == "bundled":
            results.append(
                RemoveResult(
                    id=item.id,
                    title=item.title,
                    kind=item.kind,
                    status="bundled",
                    error="bundled in package wheel; cannot be removed",
                )
            )
            continue

        if item.kind == "dataset" and item.asset_name is not None:
            try:
                res = remove_dataset(item.asset_name, root=root)
            except DataNotAvailableError as exc:
                results.append(
                    RemoveResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="failed",
                        error=str(exc),
                    )
                )
                continue
            if res is None:
                results.append(
                    RemoveResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="not_installed",
                    )
                )
            else:
                results.append(
                    RemoveResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="removed",
                        bytes_reclaimed=int(res["bytes"]),
                    )
                )
            continue

        if item.kind == "work" and item.work_id is not None:
            prev_bytes = item.bytes or 0
            removed_ids = remove_fetched_works([item.work_id])
            if item.work_id in removed_ids:
                results.append(
                    RemoveResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="removed",
                        bytes_reclaimed=prev_bytes,
                    )
                )
            else:
                results.append(
                    RemoveResult(
                        id=item.id,
                        title=item.title,
                        kind=item.kind,
                        status="not_installed",
                    )
                )
            continue

    return results


# ── Context-aware missing-asset helpers for Bible & Corpus tools ─────────────


def missing_for_corpus(corpus_id: str, *, root: Path | None = None) -> LibraryItem | None:
    """Return the missing :class:`LibraryItem` required by ``corpus_id``, or ``None``
    when the corpus is bundled or already downloaded."""
    from .data import _corpus_dataset_name

    bundled_ids = {row["id"] for row in _BUNDLED_CORPORA}
    if corpus_id in bundled_ids:
        return None
    asset = _corpus_dataset_name(corpus_id)
    if asset is None:
        return None
    item = get_item(asset, root=root)
    if item is not None and not item.installed:
        return item
    return None


def missing_for_bible(
    *,
    tab: str = "interlinear",
    edition: str = "nestle1904",
    book: str | None = None,
    ref: str | None = None,
    root: Path | None = None,
) -> list[LibraryItem]:
    """Return the missing :class:`LibraryItem`(s) needed for a Biblical Greek action.

    Used by the TUI ``BiblicalScreen`` and CLI ``aegean bible`` commands to offer
    one-click / one-command downloads right where a missing text is encountered.
    """
    by_id = {it.id: it for it in _dataset_items(root=root)}
    needed: list[str] = []

    def _need(asset: str) -> None:
        it = by_id.get(asset)
        if it is not None and not it.installed and asset not in needed:
            needed.append(asset)

    tab_l = tab.strip().lower()
    ed_l = edition.strip().lower()

    if tab_l == "editions":
        _need("nt-editions")
        if book and not _is_bundled_nt_passage(book, ref):
            _need("nt-corpus")
    elif tab_l == "witnesses":
        _need("nt-witnesses")
    elif tab_l == "study":
        _need("strongs-greek")
        _need("nt-corpus")
    elif tab_l == "lxx":
        _need("lxx-corpus")
    else:  # interlinear / read
        if book and _looks_like_lxx_book(book):
            if not _is_bundled_lxx_passage(book, ref):
                _need("lxx-corpus")
        else:
            if ed_l not in ("nestle1904", "n1904", ""):
                _need("nt-editions")
            elif book and not _is_bundled_nt_passage(book, ref):
                _need("nt-corpus")

    return [by_id[aid] for aid in needed if aid in by_id]


def _is_bundled_nt_passage(book: str, ref: str | None) -> bool:
    """Whether ``book`` + ``ref`` is covered by the bundled NT sample (John 1, Philemon 1)."""
    from .scripts.greek.nt import _resolve_book

    try:
        canon = _resolve_book(book)
    except ValueError:
        return False
    if canon == "Phlm":
        return True
    if canon == "John":
        if not ref:
            return False
        chap = ref.strip().replace(":", ".").split(".", 1)[0].split("-", 1)[0]
        return chap == "1"
    return False


def _looks_like_lxx_book(book: str) -> bool:
    from .greek.bible._catalogs import resolve_lxx_book
    from .scripts.greek.nt import _resolve_book

    try:
        _resolve_book(book)
        return False
    except ValueError:
        pass
    try:
        resolve_lxx_book(book)
        return True
    except ValueError:
        return False


def _is_bundled_lxx_passage(book: str, ref: str | None) -> bool:
    from .greek.bible._catalogs import resolve_lxx_book

    try:
        canon = resolve_lxx_book(book)
    except ValueError:
        return False
    chap = (ref or "").strip().replace(":", ".").split(".", 1)[0].split("-", 1)[0]
    if canon.name == "Gen" and chap == "1":
        return True
    if canon.name == "Ps" and chap == "22":
        return True
    return False


# ── Unified status summary ───────────────────────────────────────────────────


def summary(*, root: Path | None = None) -> dict[str, Any]:
    """Return a unified overview of the local library across all categories and packs."""
    from .data import cache_dir
    from .greek.bible._catalogs import patristic_commentaries
    from .scripts.greek.perseus import catalog, list_fetched_works

    store_root = cache_dir() if root is None else root
    bundled = _bundled_items()
    datasets = _dataset_items(root=store_root)
    fetched_works = list_fetched_works()
    commentary_ids = {c["work_id"] for c in patristic_commentaries()}
    total_works_catalog = len(catalog())
    total_commentaries = len(commentary_ids)

    fetched_commentaries = [w for w in fetched_works if w["id"] in commentary_ids]
    fetched_literary = [w for w in fetched_works if w["id"] not in commentary_ids]

    categories: dict[str, dict[str, Any]] = {}
    for cat in ("corpus", "bible", "lexicon", "model", "other"):
        b_items = [it for it in bundled if it.category == cat]
        d_items = [it for it in datasets if it.category == cat]
        dl = [it for it in d_items if it.installed]
        categories[cat] = {
            "bundled": len(b_items),
            "downloaded": len(dl),
            "available": len(d_items) - len(dl),
            "total": len(b_items) + len(d_items),
            "bytes": sum(it.bytes or 0 for it in dl),
        }

    categories["work"] = {
        "bundled": 0,
        "downloaded": len(fetched_literary),
        "available": max(0, (total_works_catalog - total_commentaries) - len(fetched_literary)),
        "total": max(0, total_works_catalog - total_commentaries),
        "bytes": sum(int(w["bytes"]) for w in fetched_literary),
    }
    categories["commentary"] = {
        "bundled": 0,
        "downloaded": len(fetched_commentaries),
        "available": max(0, total_commentaries - len(fetched_commentaries)),
        "total": total_commentaries,
        "bytes": sum(int(w["bytes"]) for w in fetched_commentaries),
    }

    total_downloaded = sum(c["downloaded"] for c in categories.values())
    total_bundled = sum(c["bundled"] for c in categories.values())
    total_bytes = sum(c["bytes"] for c in categories.values())

    return {
        "store_path": str(store_root),
        "bundled_count": total_bundled,
        "downloaded_count": total_downloaded,
        "installed_bytes": total_bytes,
        "installed_size": format_size(total_bytes),
        "categories": categories,
        "packs": [p.to_dict() for p in list_packs(root=store_root)],
    }
