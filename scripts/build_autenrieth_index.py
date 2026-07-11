"""Build the prebuilt Autenrieth (Homeric) lemma→entry index.

Source: Georg Autenrieth, *A Homeric Dictionary for Schools and Colleges* (Harper,
1891 — public domain), in the Perseus Digital Library digitization (text
``1999.04.0073``, CC BY-SA). The whole dictionary is served as one Beta Code TEI.2
document by the Perseus hopper ``dltext`` endpoint. Each ``<entryFree key="…">`` carries
a Beta Code headword ``key``, an ``<orth>`` display form, inline ``<foreign lang="greek">``
Greek, ``<gloss>`` English senses, and ``<bibl>`` Homer citations.

This produces the same gzipped ``{lemma: {"hw", "def"}}`` index shape as the sibling
Scaife / Abbott-Smith backends (see ``aegean.greek.lexindex``), so
``use_lexicon("autenrieth")`` can fetch and serve it. The lemma key is
``norm(betacode→Unicode(key))`` — identical to the ``norm`` that `IndexLexicon` looks up
with, so a fetched index resolves.

Headword-convention normalization (the real work — Autenrieth's Homeric headwords vs the
project's lemma conventions):

* **Beta Code → Unicode.** The whole document is Beta Code; ``key``/``orth``/``foreign``
  spans are converted with `aegean.greek.normalize.betacode_to_unicode`. English text
  (``gloss``, ``bibl``, prose) is kept verbatim.
* **Digamma.** Perseus Beta Code writes the Homeric digamma ϝ as ``v`` (``*v`` capital),
  which the project's 24-letter converter does not map; this build substitutes ``v→ϝ`` /
  ``*v→Ϝ`` first. Autenrieth's *headwords* are already in the project's bare-vowel
  convention (ἄναξ under ``a)/nac``, not ϝάναξ), so no headword digamma remapping is
  needed; the digamma survives only where Autenrieth prints it — the etymological notes in
  the body (ἄναξ → "(ϝάναξ)", ἀείδω → "(ἀϝείδω)").
* **Vowel-length marks.** Beta Code macron ``_`` and breve ``^`` (Autenrieth's
  quantity notation) have no Unicode Beta Code reading and are dropped from the text.
* **Homograph digits.** Perseus disambiguates homographs with a trailing digit on the
  ``key`` (``ai)no/s2``, ``a)i/w1``); the digit is stripped so the lemma is the bare
  headword, and the (few) entries that then share a lemma are merged, so no sense is lost.

Usage:
    python scripts/build_autenrieth_index.py                 # fetch Perseus, write to cache
    python scripts/build_autenrieth_index.py --source a.xml  # build from a local TEI file
    python scripts/build_autenrieth_index.py --out auten-index.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aegean.greek.lexindex import norm  # noqa: E402
from aegean.greek.normalize import betacode_to_unicode  # noqa: E402

PERSEUS_TEXT_ID = "1999.04.0073"
SOURCE_URL = (
    f"http://www.perseus.tufts.edu/hopper/dltext?doc=Perseus:text:{PERSEUS_TEXT_ID}"
)
LICENSE = "public domain (1891); Perseus digitization CC BY-SA"
ATTRIBUTION = (
    "Georg Autenrieth, A Homeric Dictionary for Schools and Colleges (Harper, 1891); "
    "digital edition, Perseus Digital Library, Tufts University (text 1999.04.0073), "
    "CC BY-SA."
)

_HOMOGRAPH_DIGIT = re.compile(r"[0-9]+$")


def beta_to_unicode(text: str) -> str:
    """Convert an Autenrieth Beta Code span to precomposed Greek.

    Handles the two conventions the project's 24-letter converter does not: the Perseus
    digamma ``v`` (``*v`` capital) → ϝ/Ϝ, and the macron ``_`` / breve ``^`` vowel-length
    marks (dropped — they have no Unicode Beta Code reading)."""
    if not text:
        return ""
    text = text.replace("*v", "Ϝ").replace("v", "ϝ")
    text = text.replace("_", "").replace("^", "")
    return betacode_to_unicode(text)


def _strip_homograph(beta_key: str) -> str:
    """Drop a trailing Perseus homograph digit (``ai)no/s2`` → ``ai)no/s``)."""
    return _HOMOGRAPH_DIGIT.sub("", beta_key)


def lemma_key(beta_key: str) -> str:
    """The normalized lemma index key for a Beta Code ``key`` (matches `lexindex.norm`)."""
    return norm(beta_to_unicode(_strip_homograph(beta_key)))


def headword(beta_key: str) -> str:
    """The Unicode display headword (case preserved: proper nouns stay capitalized)."""
    return beta_to_unicode(_strip_homograph(beta_key))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_greek(elem: ET.Element) -> bool:
    return elem.get("lang") == "greek" or _local(elem.tag) in ("orth", "foreign")


def _render(elem: ET.Element, greek: bool) -> str:
    """Serialize an entry's mixed content: Greek spans → Unicode, English kept verbatim."""
    greek = greek or _is_greek(elem)

    def conv(text: str | None) -> str:
        if not text:
            return ""
        return beta_to_unicode(text) if greek else text

    parts = [conv(elem.text)]
    for child in elem:
        tag = _local(child.tag)
        if tag in ("gloss", "bibl"):
            # English content: keep as printed (citations are ASCII, glosses English).
            parts.append(" ".join("".join(child.itertext()).split()))
        else:
            parts.append(_render(child, greek))
        # A tail belongs to THIS element's language context, not the child's.
        parts.append(conv(child.tail))
    return "".join(parts)


def entry_body(elem: ET.Element) -> str:
    """The full rendered definition of one ``<entryFree>`` (whitespace-collapsed)."""
    return " ".join(_render(elem, greek=False).split())


def index_from_tei(path: Path | str) -> dict[str, dict[str, str]]:
    """Parse the Autenrieth Perseus TEI into a normalized lemma→entry index.

    Every ``<entryFree>`` with a ``key`` becomes a ``{lemma: {"hw", "def"}}`` record.
    The (few) entries whose keys collapse to the same lemma after digit-stripping and
    case-folding — proper-noun/common-noun pairs, true homographs — are merged in
    document order so no sense is dropped (unlike the siblings' first-sense-wins, but
    the same index shape)."""
    root = ET.parse(str(path)).getroot()
    index: dict[str, dict[str, str]] = {}
    for ef in root.iter("entryFree"):
        beta_key = (ef.get("key") or "").strip()
        if not beta_key:
            continue
        key = lemma_key(beta_key)
        body = entry_body(ef)
        if not key or not body:
            continue
        existing = index.get(key)
        if existing is None:
            index[key] = {"hw": headword(beta_key), "def": body}
        elif body not in existing["def"]:
            existing["def"] = f"{existing['def']} | {body}"
    return index


def write_index_deterministic(out: Path, index: dict[str, dict[str, str]]) -> None:
    """Write the gzipped ``{lemma: {"hw","def"}}`` index with a fixed gzip header.

    Same decompressed content as `aegean.greek.lexindex.write_index` (so `load_index`
    reads it identically), but with ``mtime=0`` and an empty filename field so a rebuild
    from the same source yields byte-identical output — the sha256 the hosted asset pins
    stays reproducible."""
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(index, ensure_ascii=False).encode("utf-8")
    with open(out, "wb") as fh, gzip.GzipFile(filename="", fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(raw)


def _fetch_source(dest: Path) -> Path:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 (trusted host)
        data = resp.read()
    if not data.rstrip().endswith(b"</TEI.2>"):
        raise SystemExit(
            "Perseus returned a truncated document (no closing </TEI.2>); retry, or "
            "download it and pass --source"
        )
    dest.write_bytes(data)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the Autenrieth Homeric-dictionary index.")
    ap.add_argument("--source", type=Path, help="local Perseus TEI (else fetch from Perseus)")
    ap.add_argument("--out", type=Path, default=Path("autenrieth-index.json.gz"))
    args = ap.parse_args()

    if args.source is not None:
        src = args.source
    else:
        src = args.out.parent / "autenrieth.perseus.xml"
        print(f"fetching {SOURCE_URL}")
        _fetch_source(src)

    index = index_from_tei(src)
    if len(index) < 4000:
        raise SystemExit(
            f"{src}: only {len(index)} lemmas — the source looks truncated "
            "(expected ~9,600 for the full Autenrieth)"
        )
    write_index_deterministic(args.out, index)

    raw = args.out.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    print(f"source:  Perseus text {PERSEUS_TEXT_ID} ({LICENSE})")
    print(f"wrote {args.out}  ({len(index)} lemmas, {len(raw) / 1_000_000:.2f} MB gzipped)")
    print(f"sha256: {sha}")


if __name__ == "__main__":
    main()
