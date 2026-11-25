"""Build the Online Critical Pseudepigrapha (OCP) Greek corpus (``pseudepigrapha-corpus.json.gz``).

Extracts all Greek Second Temple and Old Testament Pseudepigrapha texts from the
*Online Critical Pseudepigrapha* TEI/XML critical editions
(``OnlineCriticalPseudepigrapha/Online-Critical-Pseudepigrapha``, ``static/docs/*.xml``;
**CC BY 4.0** for all text editions):

Includes Greek witnesses/critical texts for *Psalms of Solomon*, *Testament of Solomon*,
*Testaments of the Twelve Patriarchs*, *1 Enoch*, *3 Baruch*, *4 Baruch*, *Life of Adam and Eve*
(*Apocalypse of Moses*), *Testament of Job*, *Testament of Abraham* (Recensions A & B),
*Letter of Aristeas*, *Joseph and Aseneth*, *Sibylline Oracles*, *3–4 Maccabees*, *Jubilees*
(Greek fragments), *Lives of the Prophets*, *History of the Rechabites*, *Sentences of
Pseudo-Phocylides*, *Apocalypse of Sedrach*, *Testament of Adam*, *Prayer of Manasseh*,
*Ezekiel the Tragedian*, *Aristobulus*, *Artapanus*, *Demetrius the Chronographer*,
*Eupolemus*, *Philo the Epic Poet*, *Theodotus*, *Pseudo-Hecataeus*, and *Testament of Orpheus*.

Usage:
    python scripts/build_pseudepigrapha_corpus.py <path-to-ocp/static/docs> -o pseudepigrapha-corpus.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

REPO = "OnlineCriticalPseudepigrapha/Online-Critical-Pseudepigrapha"
COMMIT = "954a1f057c2426ad2f049b135600712812516242"

_GREEK_CHAR_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
# Skip redundant wrapper files whose recensions are separate files (TAbr duplicates TAbA + TAbB)
_SKIP_STEMS = {"TAbr"}


def _has_greek(text: str) -> bool:
    return bool(_GREEK_CHAR_RE.search(text))


def _is_mostly_greek(text: str) -> bool:
    greek = len(_GREEK_CHAR_RE.findall(text))
    latin = sum(1 for ch in text if "A" <= ch <= "Z" or "a" <= ch <= "z")
    return greek > 0 and greek >= latin


def _extract_version_lines(ver: ET.Element) -> list[tuple[str, str]]:
    """Extract ``(ref, greek_text)`` lines from one ``<version>`` element."""
    text_el = ver.find("text")
    if text_el is None:
        return []

    out: list[tuple[str, str]] = []

    def walk_divs(el: ET.Element, path: list[str]) -> None:
        child_divs = [c for c in el if c.tag == "div"]
        if child_divs:
            for d in child_divs:
                num = d.get("number") or d.get("name") or ""
                walk_divs(d, path + ([num] if num else []))
            return
        units = list(el.iter("unit"))
        if not units:
            return
        pieces: list[str] = []
        for u in units:
            # Pick option="0" (critical base reading) when present and Greek;
            # otherwise fall back to first reading containing Greek text.
            chosen = ""
            readings = u.findall("reading")
            r0 = u.find("reading[@option='0']")
            if r0 is not None:
                cand = " ".join("".join(r0.itertext()).split())
                if cand and _is_mostly_greek(cand):
                    chosen = cand
            if not chosen:
                for r in readings:
                    cand = " ".join("".join(r.itertext()).split())
                    if cand and _is_mostly_greek(cand):
                        chosen = cand
                        break
            if chosen:
                pieces.append(chosen)
        joined = " ".join(pieces).strip()
        if joined and _has_greek(joined):
            ref = ".".join(path) if path else "1"
            out.append((ref, joined))

    walk_divs(text_el, [])
    return out


def build(docs_dir: Path) -> object:
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.core.provenance import Provenance
    from aegean.greek.tokenize import tokenize

    docs: list[Document] = []
    for xml_path in sorted(docs_dir.glob("*.xml")):
        if xml_path.name.startswith(".") or xml_path.name.endswith("_TEI.xml"):
            continue
        if xml_path.stem in _SKIP_STEMS:
            continue
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue
        if root.tag != "book":
            continue

        title = (root.get("title") or xml_path.stem).strip()
        greek_lines: list[tuple[str, str]] = []
        for vi, ver in enumerate(root.findall("version")):
            lang = (ver.get("language") or "").lower()
            ms_langs = {(m.get("language") or "").lower() for m in ver.findall("./manuscripts/ms")}
            if lang and "greek" not in lang:
                continue
            if not lang and ms_langs and not any("greek" in ml for ml in ms_langs):
                continue
            v_lines = _extract_version_lines(ver)
            if not v_lines:
                continue
            vtitle = (ver.get("title") or "").strip()
            prefix = f"v{vi + 1}." if len(root.findall("version")) > 1 and vtitle else ""
            for ref, line_txt in v_lines:
                greek_lines.append((f"{prefix}{ref}", line_txt))

        if not greek_lines:
            continue

        tokens: list[Token] = []
        lines: list[list[int]] = []
        for ref, text in greek_lines:
            line_no = len(lines)
            idxs: list[int] = []
            for tok in tokenize(text):
                if not any(ch.isalpha() for ch in tok.text):
                    continue
                if not _has_greek(tok.text):
                    continue
                word = unicodedata.normalize("NFC", tok.text)
                pos = len(tokens)
                tokens.append(
                    Token(
                        text=word,
                        kind=TokenKind.WORD,
                        glyphs=word,
                        line_no=line_no,
                        position=pos,
                        annotations={"ref": f"{xml_path.stem}.{ref}"},
                    )
                )
                idxs.append(pos)
            if idxs:
                lines.append(idxs)

        if len(tokens) < 5:
            continue

        docs.append(
            Document(
                id=xml_path.stem,
                script_id="greek",
                tokens=tokens,
                lines=lines,
                meta=DocumentMeta(
                    name=title,
                    period="Second Temple / Hellenistic–Roman Jewish",
                    notes=(f"Source: OCP static/docs/{xml_path.name}",),
                ),
            )
        )
        print(f"  {xml_path.stem:14s} {len(lines):4d} units/verses, {len(tokens):6d} tokens  ({title})")

    prov = Provenance(
        source="Online Critical Pseudepigrapha (Greek Second Temple & OT Pseudepigrapha editions)",
        license="CC BY 4.0 (Online Critical Pseudepigrapha, Ken M. Penner et al., pseudepigrapha.org)",
        url=f"https://github.com/{REPO}/tree/{COMMIT}/static/docs",
        citation=(
            "Penner, K. M., et al. Online Critical Pseudepigrapha (pseudepigrapha.org). "
            "CC BY 4.0."
        ),
        edition_fidelity="normalized",
    )
    return Corpus(docs, provenance=prov, script_id="greek")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build pseudepigrapha-corpus.json.gz from OCP XML.")
    ap.add_argument("source", type=Path, help="path to Online-Critical-Pseudepigrapha/static/docs")
    ap.add_argument("-o", "--output", type=Path, default=Path("pseudepigrapha-corpus.json.gz"))
    args = ap.parse_args()
    corpus = build(args.source)
    payload = corpus.to_json().encode("utf-8")  # type: ignore[attr-defined]
    with args.output.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as gz:
            gz.write(payload)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
