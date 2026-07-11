"""Shared EpiDoc → pyaegean-Corpus build helpers (repo-only; used by the corpus build scripts).

The hard part — turning an EpiDoc ``<div type="edition">`` into clean running Greek text — is
`edition_tokens`, reused across every epigraphic corpus (I.Sicily, IIP, IOSPE, Cyrenaica, EDH).
Each token carries its editorial `ReadingStatus`, so a restored or damaged reading is preserved,
not silently flattened into certain text. Each corpus script supplies only its own Greek filter
and metadata mapping and calls `build_greek_corpus`. All licences permit redistributing the
derived corpus as a separate, self-licensed release asset (never bundled in the Apache-2.0
wheel), so pyaegean can mirror them.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from aegean.core.model import ReadingStatus  # noqa: E402

_TEI = "http://www.tei-c.org/ns/1.0"
_XML = "http://www.w3.org/XML/1998/namespace"

# Elements whose textual content is NOT part of the running reading text: editorial symbols
# (<g> palm/christogram/etc.), lost gaps, spaces/milestones, apparatus/notes, a section <head>
# label (EDH editions open with <head>Text</head>), and abbreviations (the <ex> expansion inside
# <expan> is kept; the raw <abbr> is dropped).
_SKIP = {"g", "gap", "space", "milestone", "note", "certainty", "lem", "rdg", "app", "abbr", "head"}

# Editorial certainty, least to most severe. A word that spans more than one apparatus span takes
# the most severe status any of its characters carry (a one-status-per-token round-up: EpiDoc marks
# apparatus at the letter level, a Token holds one status).
_SEVERITY: dict[ReadingStatus, int] = {
    ReadingStatus.CERTAIN: 0,
    ReadingStatus.UNCLEAR: 1,
    ReadingStatus.RESTORED: 2,
    ReadingStatus.LOST: 3,
}


def local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _elem_status(el: ET.Element, inherited: ReadingStatus) -> ReadingStatus:
    """The reading status an element imposes on its text, matching ``io/epidoc._status_index``:
    ``<supplied reason="undefined">`` -> LOST, other ``<supplied>`` -> RESTORED, ``<unclear>`` ->
    UNCLEAR, else the inherited status. Nesting keeps the most severe."""
    tag = local(el.tag)
    if tag == "supplied":
        st = ReadingStatus.LOST if el.get("reason") == "undefined" else ReadingStatus.RESTORED
    elif tag == "unclear":
        st = ReadingStatus.UNCLEAR
    else:
        st = inherited
    return st if _SEVERITY[st] >= _SEVERITY[inherited] else inherited


# A TEI <choice> presents mutually exclusive readings; only its edited member belongs in the
# running text. Prefer the expansion/regularization/correction over the raw abbr/orig/sic.
_CHOICE_PREFER = ("expan", "reg", "corr")


def _preferred_choice(choice: ET.Element) -> ET.Element | None:
    """The edited member of a ``<choice>`` (``<expan>``/``<reg>``/``<corr>``), else the first
    non-skipped child. Walking every member concatenates the alternatives into one garbled word
    (e.g. ``<corr>μ</corr><sic>Ν</sic>`` -> ``μΝ``), so a caller that resolves choices walks only
    this member."""
    kids = list(choice)
    for want in _CHOICE_PREFER:
        for k in kids:
            if local(k.tag) == want:
                return k
    for k in kids:
        if local(k.tag) not in _SKIP:
            return k
    return kids[0] if kids else None


def edition_tokens(
    edition: ET.Element, choice_prefer: bool = False
) -> list[list[tuple[str, ReadingStatus]]]:
    """The edition's reading text as physical lines of ``(word, ReadingStatus)`` pairs.

    ``<lb break="no"/>`` joins a word split across a line (Ἀ|λεξάνδρου → Ἀλεξάνδρου); a plain
    ``<lb/>`` starts a new line. Inter-word spaces come from the literal text nodes. Each word's
    status is the most severe apparatus status touching its characters (see `_elem_status`).

    With ``choice_prefer=True``, a ``<choice>`` contributes only its edited member (see
    `_preferred_choice`) instead of every alternative; the default keeps the historical behaviour
    (both members walked) so corpora built without it are byte-identical."""
    lines: list[list[tuple[str, ReadingStatus]]] = []
    buf: list[str] = []                 # characters of the current line
    cstat: list[ReadingStatus] = []     # per-character status, parallel to buf
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
        # split the char buffer into whitespace-separated words, each taking the most severe
        # status among its characters
        word: list[str] = []
        wstat: list[ReadingStatus] = []
        out_line: list[tuple[str, ReadingStatus]] = []

        def emit() -> None:
            if word:
                sev = max(wstat, key=lambda s: _SEVERITY[s])
                out_line.append(("".join(word), sev))
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

    def walk(el: ET.Element, inherited: ReadingStatus) -> None:
        tag = local(el.tag)
        if tag == "lb":
            if el.get("break") == "no":
                # drop a trailing space so the split word rejoins
                while buf and buf[-1].isspace():
                    buf.pop()
                    cstat.pop()
                join_next[0] = True
            else:
                flush()
            return
        if choice_prefer and tag == "choice":
            st = _elem_status(el, inherited)  # <choice> itself carries no apparatus status
            add(el.text, st)
            pick = _preferred_choice(el)
            if pick is not None:
                walk(pick, st)
                add(pick.tail, st)  # text inside <choice> after the chosen member (rare)
            return
        if tag in _SKIP:
            return
        st = _elem_status(el, inherited)
        add(el.text, st)
        for child in el:
            walk(child, st)
            add(child.tail, st)  # a child's tail is text still inside `el`, so it carries `el`'s status

    for child in edition:
        walk(child, ReadingStatus.CERTAIN)
        add(child.tail, ReadingStatus.CERTAIN)
    flush()
    return lines


def edition_lines(edition: ET.Element) -> list[str]:
    """The edition's reading text as plain physical lines (words joined by single spaces).

    A thin view over `edition_tokens` that drops the per-token status: the reading text is
    unchanged from before status tracking, so callers that only want the text are unaffected."""
    return [" ".join(w for w, _ in line) for line in edition_tokens(edition)]


def _strip_diplomatic_eq(seg: str) -> str:
    """Drop each EDH ``=`` correspondence marker and the run of capitals it introduces.

    EDH marks a diplomatic-to-edited letter correspondence inline as ``edited=DIPLOMATIC`` with the
    as-inscribed letters in capitals (e.g. ``Th=ΗΤ`` -> ``Th``, ``γυναι=Ι`` -> ``γυναι``). Keeping
    the edited side yields the reading; the capitalised diplomatic run is recorded, if at all, only
    by the separate diplomatic form of the ``#`` group."""
    out: list[str] = []
    i = 0
    n = len(seg)
    while i < n:
        c = seg[i]
        if c == "=":
            i += 1
            while i < n and seg[i].isalpha() and seg[i].isupper():
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def resolve_inline_variants(word: str) -> tuple[str, tuple[str, ...]]:
    """Split an EDH ``#``-joined multi-form token into one reading plus its alternates.

    EDH bakes several parallel forms of a word into the edition text joined by a literal ``#`` (the
    edited form first, further editorial variants, then the diplomatic all-capitals form) and marks
    inline letter correspondences as ``edited=DIPLOMATIC`` (see `_strip_diplomatic_eq`). The first
    form is kept as the token reading; each remaining distinct form becomes an alternate, so no
    ``#`` or ``=`` survives in the running text and the variant readings are preserved. A word
    without ``#`` is returned unchanged with no alternates."""
    if "#" not in word:
        return word, ()
    segs = [s for s in (_strip_diplomatic_eq(p) for p in word.split("#")) if s]
    if not segs:
        return word, ()
    primary = segs[0]
    alts: list[str] = []
    seen = {primary}
    for s in segs[1:]:
        if s not in seen:
            seen.add(s)
            alts.append(s)
    return primary, tuple(alts)


def primary_edition(root: ET.Element) -> ET.Element | None:
    """The primary edition div (``subtype="primary"`` if present, else the first edition)."""
    editions = [d for d in root.iter(f"{{{_TEI}}}div") if d.get("type") == "edition"]
    for d in editions:
        if d.get("subtype") == "primary":
            return d
    return editions[0] if editions else None


def first_text(root: ET.Element, *locals_: str) -> str:
    for want in locals_:
        for el in root.iter():
            if local(el.tag) == want:
                text = re.sub(r"\s+", " ", "".join(el.itertext())).strip()
                if text:
                    return text
    return ""


def main_lang(root: ET.Element) -> str:
    for el in root.iter():
        if local(el.tag) == "textLang":
            return el.get("mainLang", "")
    return ""


def geo_coords(root: ET.Element) -> str:
    for el in root.iter():
        if local(el.tag) == "geo" and el.text and el.text.strip():
            return el.text.strip().replace("\n", " ")
    return ""


def build_greek_corpus(
    insc_dir: str | Path,
    *,
    is_greek: Callable[[ET.Element], bool],
    metadata: Callable[[ET.Element, str], Any],
    out: str | Path,
    source: str,
    license: str,
    url: str,
    script_id: str = "greek",
    limit: int = 0,
    edition_fidelity: str = "apparatus-preserved,normalized",
) -> tuple[int, int]:
    """Filter the Greek inscriptions of an EpiDoc directory, extract each primary edition's Greek
    reading (with per-token editorial status), and write a compact pyaegean ``Corpus`` JSON.
    Returns (greek_with_text, documents)."""
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.core.provenance import Provenance

    files = sorted(Path(insc_dir).glob("*.xml"))
    docs: list[Document] = []
    greek = 0
    for f in files:
        try:
            root = ET.parse(str(f)).getroot()
        except ET.ParseError:
            continue
        if not is_greek(root):
            continue
        edition = primary_edition(root)
        if edition is None:
            continue
        token_lines = edition_tokens(edition)
        if not token_lines:
            continue
        greek += 1
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
            continue
        docs.append(Document(id=f.stem, script_id=script_id, tokens=tokens, lines=lines, meta=metadata(root, f.stem)))
        if limit and len(docs) >= limit:
            break

    prov = Provenance(source=source, license=license, url=url, edition_fidelity=edition_fidelity)
    corpus = Corpus(docs, provenance=prov, script_id=script_id)
    Path(out).write_text(corpus.to_json(), encoding="utf-8")
    return greek, len(docs)
