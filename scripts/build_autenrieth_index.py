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
``norm(betacode→Unicode(headword))`` — identical to the ``norm`` that `IndexLexicon`
looks up with (NFC + lowercase), so a fetched index resolves.

Headword-convention normalization (the real work — Autenrieth's Homeric headwords vs the
project's lemma conventions):

* **Lemma + headword come from ``<orth>``, not the ``key`` attribute.** The Perseus
  ``key`` is unreliable: 26 entries in the δη- run carry a ``D.H.``-prefixed
  data-entry artifact (``key="D.H.=mos1"`` for δῆμος), and a handful carry a stray
  period or a misplaced mark (``e)u/.cestos``, ``nuc/s``, ``kartu=)nw``). Where the
  ``key`` is malformed the entry's own ``<orth>`` is well-formed (``<orth>dh=mos</orth>``),
  so the build derives both the lemma key and the display headword from the first
  ``<orth>`` form, using the ``key`` only when ``<orth>`` is absent or unusable. A
  well-formed-Greek gate rejects any lemma that is not Greek letters + combining marks;
  an entry that fails through both paths is skipped and reported.
* **Beta Code → Unicode.** The whole document is Beta Code; ``key``/``orth``/``foreign``
  spans are converted with `aegean.greek.normalize.betacode_to_unicode`. English text
  (``gloss``, prose) is kept verbatim; ``<bibl>`` is English except for the Homeric
  book-letter citations (``*a 278`` = Iliad Α 278), whose Greek letters are converted.
* **Digamma.** Perseus Beta Code writes the Homeric digamma ϝ as ``v`` (``*v`` capital),
  which the project's 24-letter converter does not map. The digamma is applied only to
  the etymological **body** spans, where Autenrieth prints it (ἄναξ → "(ϝάναξ)", ἀείδω →
  "(ἀϝείδω)"). It is NOT applied to lemma/headword derivation: Autenrieth's headwords are
  in the bare-vowel convention, and the one ``v`` that reaches a headword form is the
  spurious ``de/vw`` byform of δέω 'lack' (the 1891 print reads plain "1. δέω (δεύω)",
  no digamma; LSJ/Cunliffe lemmatize δέω), so the ``v`` is dropped there and the two δέω
  homographs merge under one δέω lemma carrying both senses.
* **Quantity / placeholder marks.** Beta Code macron ``_`` and breve ``^`` (Autenrieth's
  vowel-length notation) have no Unicode Beta Code reading and are dropped. The source
  also uses ``<*>`` (99×) as a quantity/placeholder mark that sits between a letter and
  its breathing or accent; left in place it detaches the diacritic (ἀάω → "α<>ἀ<>ώ"), so
  it is stripped before conversion, along with a stray ``*`` before a non-letter.
* **Homograph digits.** Perseus disambiguates homographs with a trailing digit on the
  ``key`` (``ai)no/s2``, ``a)i/w1``); the digit is stripped so the lemma is the bare
  headword, and entries that share a lemma after digit-stripping and case-folding —
  proper-noun/common-noun pairs, true homographs — are merged in document order so no
  sense is lost.

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
import unicodedata
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
# A ``*`` (Beta Code capital marker) is stray unless it precedes a letter or a Beta Code
# mark (breathings/accents/subscript may sit between ``*`` and the capital letter).
_STRAY_STAR = re.compile(r"\*(?![A-Za-z)(/\\=+|])")

# Greek and Coptic (U+0370–U+03FF, includes digamma ϝ) plus Greek Extended
# (U+1F00–U+1FFF, the precomposed polytonic letters).
_GREEK_LO, _GREEK_HI = 0x0370, 0x03FF
_GREEKEXT_LO, _GREEKEXT_HI = 0x1F00, 0x1FFF


def _strip_markers(text: str) -> str:
    """Drop the quantity/placeholder marks common to every span: the ``<*>`` marker, a
    stray capital marker, and the macron ``_`` / breve ``^`` vowel-length notation."""
    text = text.replace("<*>", "")
    text = _STRAY_STAR.sub("", text)
    return text.replace("_", "").replace("^", "")


def beta_to_unicode(text: str) -> str:
    """Convert an Autenrieth **body** Beta Code span to precomposed Greek.

    Body spans keep the etymological digamma: Perseus writes it ``v`` (``*v`` capital),
    which the project's 24-letter converter does not map, so it is substituted ϝ / Ϝ
    here (ἄναξ → "(ϝάναξ)"). The ``<*>`` placeholder and the macron ``_`` / breve ``^``
    vowel-length marks (no Unicode Beta Code reading) are stripped first."""
    if not text:
        return ""
    text = _strip_markers(text)
    text = text.replace("*v", "Ϝ").replace("v", "ϝ")
    return betacode_to_unicode(text)


def _beta_headword(text: str) -> str:
    """Convert a Beta Code lemma/headword form to precomposed Greek.

    Unlike `beta_to_unicode`, this does NOT remap ``v`` to digamma: Autenrieth's
    headwords use the bare-vowel convention, and the only ``v`` that reaches a headword
    form is the spurious ``de/vw`` byform of δέω (dropped so it merges with δέω). A stray
    period from a malformed key (``e)u/.cestos`` → ἐύξεστος) is also dropped."""
    if not text:
        return ""
    text = _strip_markers(text)
    text = text.replace("*v", "").replace("*V", "").replace("v", "")
    text = text.replace(".", "")
    return betacode_to_unicode(text)


def _strip_homograph(beta_key: str) -> str:
    """Drop a trailing Perseus homograph digit (``ai)no/s2`` → ``ai)no/s``)."""
    return _HOMOGRAPH_DIGIT.sub("", beta_key)


def headword(beta: str) -> str:
    """The Unicode display headword for a Beta Code form (case preserved: proper nouns
    stay capitalized). Digamma is not applied (see `_beta_headword`)."""
    return _beta_headword(_strip_homograph(beta))


def lemma_key(beta: str) -> str:
    """The normalized lemma index key for a Beta Code form (matches `lexindex.norm`:
    NFC + lowercase)."""
    return norm(headword(beta))


def first_orth_form(orth_text: str) -> str:
    """The first Beta Code form from an ``<orth>`` element, ready for `headword`.

    An ``<orth>`` may list several comma-separated forms (``dhqa/, dh/q)``) — the first is
    the headword. Autenrieth marks morpheme/compound boundaries with a hyphen
    (``a)-a_/a_tos``, ``dhmo - bo/ros``); those hyphens and any surrounding whitespace
    (including line-wrap newlines) are removed so the form is the joined headword."""
    first = orth_text.split(",")[0].replace("-", "")
    return "".join(first.split())


def is_greek_lemma(text: str) -> bool:
    """True when every character is a Greek/Greek-Extended letter or a combining mark.

    The build's well-formed gate: a lemma key must contain only Greek letters and their
    diacritics, so a malformed key (a ``D.H.`` prefix, a stray period, a leaked ``<``/``>``
    or Latin letter) never enters the index."""
    if not text:
        return False
    for ch in text:
        cat = unicodedata.category(ch)
        o = ord(ch)
        if cat[0] == "L" and (_GREEK_LO <= o <= _GREEK_HI or _GREEKEXT_LO <= o <= _GREEKEXT_HI):
            continue
        if cat[0] == "M":  # combining diacritics (NFC leaves macron/breve stacks decomposed)
            continue
        return False
    return True


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_greek(elem: ET.Element) -> bool:
    return elem.get("lang") == "greek" or _local(elem.tag) in ("orth", "foreign")


def _render_bibl(text: str) -> str:
    """Render a ``<bibl>`` citation: English kept verbatim, but a Homeric book-letter
    reference in Beta Code (``*a 278`` = Iliad Α 278, ``*h 80``, ``*i 122``) is converted.

    The book letter is the only Greek in these citations and always carries the ``*``
    capital marker, so a whitespace token containing ``*`` is converted and everything
    else (``Il.``, ``Od.``, line numbers) is left as printed."""
    tokens = text.split()
    return " ".join(beta_to_unicode(tok) if "*" in tok else tok for tok in tokens)


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
        if tag == "gloss":
            # English content: keep as printed.
            parts.append(" ".join("".join(child.itertext()).split()))
        elif tag == "bibl":
            # English citations, except Homeric book-letter references in Beta Code.
            parts.append(_render_bibl("".join(child.itertext())))
        else:
            parts.append(_render(child, greek))
        # A tail belongs to THIS element's language context, not the child's.
        parts.append(conv(child.tail))
    return "".join(parts)


def entry_body(elem: ET.Element) -> str:
    """The full rendered definition of one ``<entryFree>`` (whitespace-collapsed)."""
    return " ".join(_render(elem, greek=False).split())


def _derive_lemma(ef: ET.Element, beta_key: str) -> tuple[str, str] | None:
    """The ``(lemma_key, headword)`` for an entry, from ``<orth>`` first then ``key``.

    Returns ``None`` when neither the first ``<orth>`` form nor the ``key`` produces a
    well-formed Greek lemma (the entry is then skipped and reported)."""
    orth = ef.find("orth")
    orth_text = "".join(orth.itertext()) if orth is not None else ""
    candidates = (first_orth_form(orth_text), _strip_homograph(beta_key))
    for beta in candidates:
        if not beta:
            continue
        hw = _beta_headword(beta)
        lk = norm(hw)
        if is_greek_lemma(lk):
            return lk, hw
    return None


def index_from_tei(
    path: Path | str, *, report: list[str] | None = None
) -> dict[str, dict[str, str]]:
    """Parse the Autenrieth Perseus TEI into a normalized lemma→entry index.

    Every ``<entryFree>`` with a ``key`` becomes a ``{lemma: {"hw", "def"}}`` record whose
    lemma + headword are derived from ``<orth>`` (the ``key`` only as a fallback). Entries
    whose keys collapse to the same lemma after digit-stripping and case-folding —
    proper-noun/common-noun pairs, true homographs — are merged in document order so no
    sense is dropped (unlike the siblings' first-sense-wins, but the same index shape).
    An entry that yields no well-formed Greek lemma is skipped; if ``report`` is given,
    its ``key`` is appended for the caller to surface."""
    root = ET.parse(str(path)).getroot()
    index: dict[str, dict[str, str]] = {}
    for ef in root.iter("entryFree"):
        beta_key = (ef.get("key") or "").strip()
        if not beta_key:
            continue
        derived = _derive_lemma(ef, beta_key)
        if derived is None:
            if report is not None:
                report.append(beta_key)
            continue
        key, hw = derived
        body = entry_body(ef)
        if not body:
            continue
        existing = index.get(key)
        if existing is None:
            index[key] = {"hw": hw, "def": body}
        elif body not in existing["def"]:
            existing["def"] = f"{existing['def']} | {body}"
    violators = [k for k in index if not is_greek_lemma(k)]
    if violators:
        raise SystemExit(
            f"well-formed-Greek gate: {len(violators)} lemma(s) are not Greek "
            f"letters + marks (e.g. {violators[:5]}) — build aborted"
        )
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

    skipped: list[str] = []
    index = index_from_tei(src, report=skipped)
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
    if skipped:
        print(f"skipped {len(skipped)} entr(y/ies) with no well-formed Greek lemma: {skipped}")
    print(f"sha256: {sha}")


if __name__ == "__main__":
    main()
