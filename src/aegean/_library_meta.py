"""Data classes, static metadata tables, and pack definitions for :mod:`aegean.library`."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

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


# ── Static metadata tables (zero network, derived from aegean.core.catalog) ──

from .core.catalog import CORPORA as _CATALOG_CORPORA  # noqa: E402

_BUNDLED_CORPORA: tuple[dict[str, Any], ...] = tuple(
    {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "license": c.license,
        "aliases": c.aliases,
        "open_spec": c.id,
    }
    for c in _CATALOG_CORPORA
    if c.bundled
)

# Dataset id -> (title, primary_category, extra_tags, aliases, open_spec, default_size_hint)
# Corpus entries are derived from aegean.core.catalog; non-corpus bundles, lexica,
# models, and media live below.
_DATASET_META: dict[str, tuple[str, str, tuple[str, ...], tuple[str, ...], str | None, str]] = {
    **{
        c.asset_name: (c.title, c.category, c.tags, c.aliases, c.id, c.size_hint)
        for c in _CATALOG_CORPORA
        if c.asset_name
    },
    # Non-corpus Biblical & Koine Greek bundles
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


