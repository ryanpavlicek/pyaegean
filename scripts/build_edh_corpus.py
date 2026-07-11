"""Build the EDH Greek corpus (repo-only; not shipped).

EDH — Epigraphic Database Heidelberg (Heidelberg Academy of Sciences and Humanities;
github.com/epigraphic-database-heidelberg/data). The data dump is CC BY-SA 4.0 and frozen (the
project ended in 2021), so mirroring it as a self-licensed release asset both adds a distinct
epigraphic database and preserves a corpus that will not be republished. EDH is overwhelmingly
Latin; this filters the pure Ancient-Greek inscriptions (the edition div is ``xml:lang="grc"`` —
bilingual ``la,grc`` files are skipped, being almost entirely Latin with at most a name in Greek),
extracts each edition's Greek reading, and writes a compact ``Corpus`` JSON hosted as ``edh-corpus``
and fetched via ``aegean.load("edh")``. This is Imperial-period Koine (dedications, boundary and
funerary texts), largely onomastic; it carries Trismegistos ids for cross-referencing.

EDH ships ~79k loose XML files (one per inscription), only ~1% of which are Greek. Opening every one
is pathologically slow on some filesystems (real-time AV scanning), so this reads directly from the
clone's git packfile: ``git grep`` narrows to the files whose edition is ``xml:lang="grc"`` and
``git cat-file --batch`` streams those blobs in a single process — no per-file filesystem opens.

Usage:  python scripts/build_edh_corpus.py <path-to-edh-data-clone> -o edh-corpus.json
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from _epidoc import (  # noqa: E402
    edition_tokens,
    first_text,
    local,
    primary_edition,
    resolve_inline_variants,
)

_XML = "http://www.w3.org/XML/1998/namespace"
_GREEK_EDITION = 'type="edition" xml:lang="grc"'


def _is_greek(root: ET.Element) -> bool:
    edition = primary_edition(root)
    return edition is not None and edition.get(f"{{{_XML}}}lang") == "grc"


def _idno(root: ET.Element, typ: str) -> str:
    for el in root.iter():
        if local(el.tag) == "idno" and el.get("type") == typ and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _place_join(root: ET.Element, parent: str) -> str:
    """Join the non-empty ``<placeName>`` texts under the first ``<parent>`` (order-preserving,
    deduped): ``<origPlace>`` gives the ancient place, ``<provenance>`` the modern find-place."""
    for el in root.iter():
        if local(el.tag) == parent:
            parts = [
                c.text.strip()
                for c in el.iter()
                if local(c.tag) == "placeName" and c.text and c.text.strip()
            ]
            return ", ".join(dict.fromkeys(parts))
    return ""


def _keyword(root: ET.Element) -> str:
    for el in root.iter():
        if local(el.tag) == "term" and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    name = first_text(root, "title") or stem
    site = _place_join(root, "origPlace")
    period = first_text(root, "origDate")
    findspot = _place_join(root, "provenance")
    tm = _idno(root, "TM")
    kind = _keyword(root)
    notes = tuple(n for n in (f"TM {tm}" if tm else "", kind) if n)
    return DocumentMeta(name=name, site=site, period=period, findspot=findspot, notes=notes)


def _greek_blob_paths(repo: Path) -> list[str]:
    """The tree paths (``inscriptions/…/HD*.xml``) whose edition is ``xml:lang="grc"``, found by
    scanning the committed blobs (fast — one packfile, not 79k loose-file opens)."""
    out = subprocess.run(
        ["git", "-C", str(repo), "grep", "-l", "--no-color", _GREEK_EDITION, "HEAD", "--", "inscriptions/"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    # lines are "HEAD:inscriptions/1/1/HD000139.xml"
    return [line.split(":", 1)[1] for line in out.splitlines() if line.strip()]


def _read_blobs(repo: Path, paths: list[str]) -> list[tuple[str, bytes]]:
    """Stream the given committed blobs via one ``git cat-file --batch`` process. Returns
    (tree-path, content) pairs in request order."""
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    request = "".join(f"HEAD:{p}\n" for p in paths).encode()
    data, _ = proc.communicate(request)
    result: list[tuple[str, bytes]] = []
    i = 0
    for p in paths:
        nl = data.index(b"\n", i)
        header = data[i:nl].split()  # "<sha> blob <size>"
        size = int(header[2])
        start = nl + 1
        result.append((p, data[start : start + size]))
        i = start + size + 1  # skip content + its trailing newline
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to an epigraphic-database-heidelberg/data clone")
    ap.add_argument("-o", "--output", default="edh-corpus.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.core.provenance import Provenance

    repo = Path(args.source)
    paths = _greek_blob_paths(repo)
    print(f"candidate grc-edition blobs: {len(paths)}")

    docs: list[Document] = []
    greek = 0
    for path, content in _read_blobs(repo, paths):
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            continue
        if not _is_greek(root):
            continue
        edition = primary_edition(root)
        if edition is None:
            continue
        # EDH resolves <choice> to its edited member and joins parallel word-forms with a literal
        # '#'; keep one reading per token and route the other forms to Token.alt.
        token_lines = edition_tokens(edition, choice_prefer=True)
        if not token_lines:
            continue
        greek += 1
        stem = Path(path).stem
        tokens: list[Token] = []
        lines: list[list[int]] = []
        pos = 0
        for tl in token_lines:
            idxs: list[int] = []
            for word, status in tl:
                if not word:
                    continue
                text, alt = resolve_inline_variants(word)
                if not text:
                    continue
                tokens.append(
                    Token(
                        text=text, kind=TokenKind.WORD, line_no=len(lines),
                        position=pos, status=status, alt=alt,
                    )
                )
                idxs.append(pos)
                pos += 1
            if idxs:
                lines.append(idxs)
        if not tokens:
            continue
        docs.append(Document(id=stem, script_id="greek", tokens=tokens, lines=lines, meta=_metadata(root, stem)))
        if args.limit and len(docs) >= args.limit:
            break

    corpus = Corpus(
        docs,
        provenance=Provenance(
            source="EDH — Epigraphic Database Heidelberg, Ancient Greek inscriptions",
            license="CC-BY-SA-4.0 (Epigraphic Database Heidelberg / Heidelberg Academy of Sciences and Humanities)",
            url="https://github.com/epigraphic-database-heidelberg/data",
            edition_fidelity="apparatus-preserved,normalized",
        ),
        script_id="greek",
    )
    Path(args.output).write_text(corpus.to_json(), encoding="utf-8")
    print(f"Greek inscriptions with text: {greek}; documents written: {len(docs)}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
