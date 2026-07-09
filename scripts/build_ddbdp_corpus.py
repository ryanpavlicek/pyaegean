"""Build the DDbDP Greek documentary-papyri corpus (repo-only; not shipped).

DDbDP — the Duke Databank of Documentary Papyri, via papyri.info (github.com/papyri/idp.data,
``DDB_EpiDoc_XML/``). The data is CC BY 3.0 (repo-wide README + per-file ``<availability>``), so
pyaegean mirrors it as a self-licensed release asset. This is the largest corpus pyaegean ships —
tens of thousands of Greek documentary papyri, millions of tokens — so it is built and hosted as a
**SQLite** database (with FTS), not JSON: ``aegean.load("ddbdp")`` streams it and
``aegean db search ddbdp ...`` full-text-searches it without materialising all the tokens in memory.

Two build techniques make a corpus this size tractable:
  * The source is ~70k loose XML files; ``git grep`` + ``git cat-file --batch`` read the Greek ones
    straight from the clone's packfile (one process, no per-file filesystem opens; see EDH).
  * Documents are written to SQLite in batches (``append=True``), so the build never holds the whole
    corpus in memory at once.

Papyri carry a heavier editorial apparatus than inscriptions, so the reading text is extracted by a
DDbDP-specific walker that PICKS the preferred reading — ``<reg>`` over ``<orig>``, ``<corr>`` over
``<sic>``, ``<lem>`` over ``<rdg>``, ``<add>`` over ``<del>`` — and keeps abbreviation expansions
whole (``<expan><abbr>δραχ</abbr><ex>μὰς</ex></expan>`` -> ``δραχμὰς``).

Usage:  python scripts/build_ddbdp_corpus.py <path-to-idp.data-clone> -o ddbdp.sqlite
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from _epidoc import _SEVERITY, _elem_status, local, primary_edition  # noqa: E402

from aegean.core.model import ReadingStatus  # noqa: E402

_XML = "http://www.w3.org/XML/1998/namespace"
_TEI = "http://www.tei-c.org/ns/1.0"
_GREEK_EDITION = 'type="edition"'  # narrowed further by an xml:lang="grc" check per file

# Elements whose textual content is never part of the reading (editorial symbols, lost text, notes,
# hand changes, and the non-preferred half of an apparatus that is not routed by <choice>/<app>/<subst>).
_DROP = {
    "g", "gap", "space", "milestone", "note", "certainty", "handShift", "handNote",
    "del", "orig", "rdg", "sic", "head", "surplus", "figure",
}
# <choice> reading preference: regularised / corrected / expanded over the raw orig / sic / abbr.
_CHOICE_ORDER = ("reg", "corr", "expan", "abbr", "orig", "sic")


def _is_greek(root: ET.Element) -> bool:
    edition = primary_edition(root)
    return edition is not None and edition.get(f"{{{_XML}}}lang") == "grc"


def edition_tokens(edition: ET.Element) -> list[list[tuple[str, ReadingStatus]]]:
    """The DDbDP edition as physical lines of ``(word, ReadingStatus)``, resolving the
    papyrological apparatus (prefer ``<reg>``/``<lem>``/``<add>``) and carrying editorial status
    (``<supplied>``/``<unclear>``) per token, the most severe touching each word."""
    lines: list[list[tuple[str, ReadingStatus]]] = []
    buf: list[str] = []
    cstat: list[ReadingStatus] = []
    join_next = [False]

    def add(text: str | None, status: ReadingStatus) -> None:
        if not text:
            return
        if join_next[0]:
            text = text.lstrip()
            join_next[0] = False
        for ch in text:
            buf.append(ch)
            cstat.append(status)

    def flush() -> None:
        word: list[str] = []
        wstat: list[ReadingStatus] = []
        out_line: list[tuple[str, ReadingStatus]] = []

        def emit() -> None:
            if word:
                out_line.append(("".join(word), max(wstat, key=lambda s: _SEVERITY[s])))
                word.clear()
                wstat.clear()

        for ch, st in zip(buf, cstat):
            if ch.isspace():
                emit()
            else:
                word.append(ch)
                wstat.append(st)
        emit()
        if out_line:
            lines.append(out_line)
        buf.clear()
        cstat.clear()

    def recurse_into(el: ET.Element, status: ReadingStatus) -> None:
        add(el.text, status)
        for child in el:
            walk(child, status)
            add(child.tail, status)

    def walk(el: ET.Element, inherited: ReadingStatus) -> None:
        tag = local(el.tag)
        if tag == "lb":
            if el.get("break") == "no":
                while buf and buf[-1].isspace():
                    buf.pop()
                    cstat.pop()
                join_next[0] = True
            else:
                flush()
            return
        st = _elem_status(el, inherited)
        if tag == "choice":
            picked = None
            for pref in _CHOICE_ORDER:
                picked = next((c for c in el if local(c.tag) == pref), None)
                if picked is not None:
                    break
            if picked is None and len(el):
                picked = el[0]
            if picked is not None:
                walk(picked, st)
            return
        if tag in ("app", "subst"):
            want = "lem" if tag == "app" else "add"
            for c in el:
                if local(c.tag) == want:
                    walk(c, st)
            return
        if tag in _DROP:
            return
        recurse_into(el, st)

    for child in edition:
        walk(child, ReadingStatus.CERTAIN)
        add(child.tail, ReadingStatus.CERTAIN)
    flush()
    return lines


def edition_lines(edition: ET.Element) -> list[str]:
    """The reading text as plain physical lines (a status-dropping view of `edition_tokens`)."""
    return [" ".join(w for w, _ in line) for line in edition_tokens(edition)]


def _idno(root: ET.Element, typ: str) -> str:
    for el in root.iter():
        if local(el.tag) == "idno" and el.get("type") == typ and el.text and el.text.strip():
            return el.text.strip()
    return ""


def _head_child(root: ET.Element, want: str) -> str:
    """The text of the first ``<want>`` inside a ``<head>`` (the HGV-populated date / placeName)."""
    for head in root.iter(f"{{{_TEI}}}head"):
        for el in head.iter():
            if local(el.tag) == want and el.text and el.text.strip():
                return re.sub(r"\s+", " ", el.text).strip()
    return ""


def _citation(hybrid: str, stem: str) -> str:
    """"bgu;1;100" -> "BGU 1 100" (the human citation); fall back to the filename stem."""
    if hybrid:
        parts = [p for p in hybrid.split(";") if p]
        if parts:
            parts[0] = parts[0].upper()
            return " ".join(parts)
    return stem


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    hybrid = _idno(root, "ddb-hybrid")
    tm = _idno(root, "TM")
    hgv = _idno(root, "HGV")
    notes = tuple(n for n in (f"TM {tm}" if tm else "", f"HGV {hgv}" if hgv else "") if n)
    return DocumentMeta(
        name=_citation(hybrid, stem),
        site=_head_child(root, "placeName"),
        period=_head_child(root, "date"),
        notes=notes,
    )


def _greek_blob_paths(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "grep", "-l", "--no-color", _GREEK_EDITION, "HEAD", "--", "DDB_EpiDoc_XML/"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [line.split(":", 1)[1] for line in out.splitlines() if line.strip()]


def _iter_blobs(repo: Path, paths: list[str]):
    """Yield (tree-path, content) for the given committed blobs via one ``git cat-file --batch``.

    A background thread feeds the requests while the main thread reads the responses: writing all
    ~70k requests up-front and only then reading would deadlock once git's stdout pipe fills."""
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert proc.stdin and proc.stdout

    def feed() -> None:
        assert proc.stdin
        for p in paths:
            proc.stdin.write(f"HEAD:{p}\n".encode())
        proc.stdin.close()

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    for p in paths:  # cat-file responds in request order, so paths stay in lockstep
        header = proc.stdout.readline().split()  # "<sha> blob <size>" (or "<obj> missing")
        if len(header) < 3 or header[1] != b"blob":
            continue  # a "missing" line has no content body; skip this path
        size = int(header[2])
        content = proc.stdout.read(size)
        proc.stdout.read(1)  # trailing newline
        yield p, content
    writer.join()


def _document(path: str, content: bytes):  # type: ignore[no-untyped-def]
    from aegean.core.model import Document, Token, TokenKind

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    if not _is_greek(root):
        return None
    edition = primary_edition(root)
    if edition is None:
        return None
    token_lines = edition_tokens(edition)
    if not token_lines:
        return None
    stem = Path(path).stem
    tokens: list[Token] = []
    lines: list[list[int]] = []
    pos = 0
    for tl in token_lines:
        idxs: list[int] = []
        for word, status in tl:
            if not word:
                continue
            tokens.append(
                Token(text=word, kind=TokenKind.WORD, line_no=len(lines), position=pos, status=status)
            )
            idxs.append(pos)
            pos += 1
        if idxs:
            lines.append(idxs)
    if not tokens:
        return None
    return Document(id=stem, script_id="greek", tokens=tokens, lines=lines, meta=_metadata(root, stem))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to a papyri/idp.data clone")
    ap.add_argument("-o", "--output", default="ddbdp.sqlite")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=2000)
    args = ap.parse_args()

    from aegean.core.corpus import Corpus
    from aegean.core.provenance import Provenance
    from aegean.db import to_sqlite

    repo = Path(args.source)
    out = Path(args.output)
    if out.exists():
        out.unlink()

    paths = _greek_blob_paths(repo)
    print(f"candidate grc-edition blobs: {len(paths)}")

    provenance = Provenance(
        source="DDbDP — Duke Databank of Documentary Papyri (papyri.info), Greek documentary papyri",
        license="CC-BY-3.0 (DDbDP / Duke Collaboratory for Classics Computing, papyri.info)",
        url="https://github.com/papyri/idp.data",
        edition_fidelity="apparatus-preserved,normalized",
    )

    batch: list = []
    written = 0
    seen = 0
    first = True

    def flush() -> None:
        nonlocal batch, written, first
        if not batch:
            return
        corpus = Corpus(batch, provenance=provenance, script_id="greek")
        to_sqlite(corpus, out, fts=True, append=not first)
        written += len(batch)
        first = False
        batch = []

    for path, content in _iter_blobs(repo, paths):
        doc = _document(path, content)
        if doc is None:
            continue
        batch.append(doc)
        seen += 1
        if len(batch) >= args.batch:
            flush()
            print(f"  written {written + len(batch)}...", flush=True)
        if args.limit and seen >= args.limit:
            break
    flush()

    print(f"Greek papyri with text: {written}")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
