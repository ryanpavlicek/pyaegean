"""Abbott-Smith — A Manual Greek Lexicon of the New Testament (opt-in).

G. Abbott-Smith's NT lexicon (Scribner's, 1922; public domain), TEI-marked by
``translatable-exegetical-tools/Abbott-Smith``: ``<entry n="λόγος|G3056">`` with an
``<orth>`` headword, ``<gloss>`` senses, and Strong's keys. A richer NT option beside
the bundled Dodson glossary.

``use_lexicon("abbott-smith")`` builds a lemma→entry index in the cache on first use
(preferring a hosted prebuilt index, else fetching the TEI), then ``gloss`` / ``entry``
resolve a word, lemmatizing on a miss. Never bundled; the data is public domain and the
wheel stays Apache-2.0.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..data import cache_dir, download_file, fetch_prebuilt
from .lexicons import LexiconInfo, register_lexicon
from .lexindex import IndexLexicon, load_index, norm, write_index

_COMMIT = "8c00cb244761aa23659421a8cbbbf7a3b27b7d59"
_URL = (
    "https://raw.githubusercontent.com/translatable-exegetical-tools/Abbott-Smith/"
    f"{_COMMIT}/abbott-smith.tei.xml"
)
_CACHE_FILE = "abbott-smith/abbott-smith.tei.xml"
_INDEX_NAME = "abbott-smith-index.json.gz"
_PREBUILT = "abbott-smith-index"

_INFO = LexiconInfo(
    id="abbott-smith",
    name="Abbott-Smith, A Manual Greek Lexicon of the New Testament",
    scope="NT",
    license="public domain (1922); TEI markup public domain",
    source="translatable-exegetical-tools/Abbott-Smith",
    hosted=True,
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(elem: ET.Element) -> str:
    return " ".join("".join(elem.itertext()).split())


def index_from_tei(path: Path) -> dict[str, dict[str, str]]:
    """Parse the Abbott-Smith TEI into a normalized lemma→entry index.

    The concise definition is the entry's ``<gloss>`` senses (e.g. "a word; a saying");
    entries without an explicit gloss fall back to their first ``<sense>`` text.
    """
    index: dict[str, dict[str, str]] = {}
    for _event, elem in ET.iterparse(str(path), events=("end",)):
        if _local(elem.tag) != "entry":
            continue
        lemma = (elem.get("n") or "").split("|", 1)[0].strip()
        glosses = [g for g in (_text(e) for e in elem.iter() if _local(e.tag) == "gloss") if g]
        if glosses:
            body = "; ".join(dict.fromkeys(glosses))
        else:
            senses = [_text(e) for e in elem.iter() if _local(e.tag) == "sense"]
            body = senses[0] if senses else ""
        key = norm(lemma)
        if key and body and key not in index:
            index[key] = {"hw": lemma, "def": body}
        elem.clear()
    return index


def build_index(*, source: Path | str | None = None, force: bool = False) -> Path:
    """Build (and cache, gzipped) the Abbott-Smith lemma→entry index."""
    out = cache_dir() / _INDEX_NAME
    if out.exists() and not force and source is None:
        return out
    if source is None:
        if fetch_prebuilt(_PREBUILT, out):
            return out
        src = cache_dir() / _CACHE_FILE
        if not src.exists():
            download_file(_URL, src)
    else:
        src = Path(source)
    write_index(out, index_from_tei(src))
    return out


def load_abbott_smith(*, build: bool = True, force: bool = False) -> IndexLexicon:
    """Load Abbott-Smith (building/fetching its index on first use)."""
    out = cache_dir() / _INDEX_NAME
    if build and (force or not out.exists()):
        build_index(force=force)
    return IndexLexicon(_INFO, load_index(out))


register_lexicon(_INFO, lambda **kw: load_abbott_smith(**kw))
