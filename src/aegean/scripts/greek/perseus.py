"""Fetch-to-cache loader for real Greek works: Perseus canonical-greekLit + First1KGreek.

`load_work("tlg0012.tlg001")` downloads one work's Greek TEI edition (pinned to a
commit for reproducibility), parses it with the stdlib XML parser, and returns a
standard `Corpus` — one `Document` per top-level textpart (an Iliad book, a prose
chapter run), with `<l>` verse lines or `<p>` blocks as the physical lines. The
bundled 5-passage sample (``aegean.load("greek")``) stays the offline default;
this is the on-demand path to the actual corpora.

Both repositories are **CC BY-SA** (Perseus Digital Library; Open Greek and
Latin); files are fetched to the cache, never bundled or re-hosted. The pinned
commit is recorded as the corpus's ``Provenance.data_version``; override the ref
with ``PYAEGEAN_GREEKLIT_REF`` / ``PYAEGEAN_FIRST1K_REF`` to track a newer
upstream state.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import TYPE_CHECKING, Any

from ...core.model import Document, DocumentMeta, Token
from ...core.provenance import Provenance
from ...data import cache_dir

if TYPE_CHECKING:
    from ...core.corpus import Corpus

_TEI = "{http://www.tei-c.org/ns/1.0}"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# repo, pinned commit, license, citation — the ref pin is what makes a fetched
# work reproducible (record Provenance.data_version, or `aegean data versions`).
_SOURCES: dict[str, tuple[str, str, str]] = {
    "perseus": (
        "PerseusDL/canonical-greekLit",
        "d4fab69a2c26091454e999c994112b053defc512",
        "CC BY-SA 4.0 (Perseus Digital Library)",
    ),
    "first1k": (
        "OpenGreekAndLatin/First1KGreek",
        "4c9c843d80ee94b4371f52add5f7d68bbfe7ba4c",
        "CC BY-SA 4.0 (Open Greek and Latin, First1KGreek)",
    ),
}
_ENV_REF = {"perseus": "PYAEGEAN_GREEKLIT_REF", "first1k": "PYAEGEAN_FIRST1K_REF"}

# subtrees that are editorial apparatus, not text, when flattening a line/block
_SKIP_TAGS = {f"{_TEI}note", f"{_TEI}bibl", f"{_TEI}figDesc"}


def _ref(source: str) -> str:
    return os.environ.get(_ENV_REF[source]) or _SOURCES[source][1]


def _work_dir(work: str) -> str:
    group, _, piece = work.partition(".")
    if not (group and piece):
        raise ValueError(f"work must look like 'tlg0012.tlg001', got {work!r}")
    return f"data/{group}/{piece}"


def _github_listing(repo: str, path: str, ref: str) -> list[str]:
    """File names under ``path`` at ``ref`` (the GitHub contents API).

    The listing is cached on disk per (repo, ref, path) — a ref names an
    immutable commit, so the cache never goes stale — which keeps repeat
    `load_work` calls off the API entirely (the unauthenticated limit is
    60 requests/hour). Set ``PYAEGEAN_GITHUB_TOKEN`` or ``GITHUB_TOKEN`` to
    authenticate first-time discovery at scale."""
    safe = f"{repo.replace('/', '--')}@{ref[:12]}--{path.replace('/', '--')}.json"
    cache_file = cache_dir() / "greek-works" / "listings" / safe
    if cache_file.exists():
        names = json.loads(cache_file.read_text(encoding="utf-8"))
        return [str(n) for n in names]
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    headers = {"User-Agent": "pyaegean"}
    token = os.environ.get("PYAEGEAN_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        entries = json.loads(resp.read().decode("utf-8"))
    names = [e["name"] for e in entries]
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(names), encoding="utf-8")
    return names


def pick_edition(names: list[str], edition: str | None = None) -> str | None:
    """Choose the Greek edition file from a work directory listing.

    ``edition`` may be a full filename or a suffix fragment (``"perseus-grc1"``);
    otherwise the highest-numbered ``…-grc*.xml`` edition wins."""
    xml = [n for n in names if n.endswith(".xml") and not n.startswith("__")]
    if edition:
        for n in xml:
            if n == edition or edition in n:
                return n
        return None
    greek = sorted(n for n in xml if "-grc" in n)
    return greek[-1] if greek else None


def _fetch_xml(work: str, source: str, edition: str | None, force: bool) -> tuple[bytes, str, str]:
    """Download (or reuse) the work's TEI file; returns (bytes, source, filename)."""
    from ...data import DataNotAvailableError, download_file

    tried: list[str] = []
    sources = [source] if source in _SOURCES else list(_SOURCES)
    for src in sources:
        repo, _, _license = _SOURCES[src]
        ref = _ref(src)
        try:
            names = _github_listing(repo, _work_dir(work), ref)
        except Exception as exc:
            tried.append(f"{src}: {exc}")
            continue
        chosen = pick_edition(names, edition)
        if chosen is None:
            tried.append(f"{src}: no Greek edition among {names}")
            continue
        dest = cache_dir() / "greek-works" / src / ref[:12] / chosen
        if force or not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://raw.githubusercontent.com/{repo}/{ref}/{_work_dir(work)}/{chosen}"
            download_file(url, dest)
        return dest.read_bytes(), src, chosen
    raise DataNotAvailableError(
        f"could not fetch {work!r} ({'; '.join(tried)}). "
        "Works are addressed as 'tlgGROUP.tlgWORK', e.g. tlg0012.tlg001 (Iliad)."
    )


def _line_text(el: Any) -> str:
    """Flatten one line/block to text, skipping editorial subtrees."""
    parts: list[str] = []

    def walk(node: Any) -> None:
        if node.tag in _SKIP_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return " ".join("".join(parts).split())


def _line_num(el: Any) -> int | None:
    """The leading integer of a line/div ``n`` (``"1"`` → 1, ``"1a"`` → 1)."""
    n = el.get("n") or ""
    digits = ""
    for ch in n:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return int(digits) if digits else None


def _blocks(part: Any, line_lo: int | None = None, line_hi: int | None = None) -> list[str]:
    """The physical lines of a textpart: verse ``<l>`` lines, else ``<p>`` blocks,
    else the part's own flattened text. ``line_lo``/``line_hi`` (inclusive) filter
    verse ``<l>`` by their numeric ``n`` — the line-range selector."""
    lines_el = list(part.iter(f"{_TEI}l"))
    if line_lo is not None or line_hi is not None:
        def in_range(el: Any) -> bool:
            num = _line_num(el)
            if num is None:
                return False
            return (line_lo is None or num >= line_lo) and (line_hi is None or num <= line_hi)
        lines_el = [el for el in lines_el if in_range(el)]
    lines = [t for t in (_line_text(el) for el in lines_el) if t]
    if lines:
        return lines
    if line_lo is None and line_hi is None:
        paras = [t for t in (_line_text(p) for p in part.iter(f"{_TEI}p")) if t]
        if paras:
            return paras
        whole = _line_text(part)
        return [whole] if whole else []
    return []


def _collect_notes(part: Any) -> tuple[str, ...]:
    """Editorial ``<note>`` / ``<bibl>`` text under a textpart — carried into
    ``DocumentMeta.notes`` instead of being silently dropped."""
    out: list[str] = []
    for tag in (f"{_TEI}note", f"{_TEI}bibl"):
        for el in part.iter(tag):
            text = " ".join("".join(el.itertext()).split())
            if text:
                out.append(text)
    return tuple(out)


def _parse_ref(ref: str) -> tuple[list[str], list[str]]:
    """``"1.1-1.50"`` → ``(['1','1'], ['1','50'])``; ``"1"`` → ``(['1'], ['1'])``;
    ``"1.1-50"`` → ``(['1','1'], ['1','50'])`` (the hi inherits the lo's prefix)."""
    lo, _, hi = ref.partition("-")
    start = [c for c in lo.split(".") if c]
    if not start:
        raise ValueError(f"empty work ref {ref!r}")
    if not hi:
        return start, list(start)
    end = [c for c in hi.split(".") if c]
    if len(end) < len(start):
        end = start[: len(start) - len(end)] + end
    return start, end


def _navigate(div: Any, components: list[str]) -> tuple[Any, list[str]]:
    """Descend ``<div>``s matching ``n`` for each component; return the deepest
    matched element and the components that did not match a div (line numbers)."""
    el = div
    matched = 0
    for comp in components:
        child = next((d for d in el.iterfind(f"{_TEI}div") if d.get("n") == comp), None)
        if child is None:
            break
        el = child
        matched += 1
    return el, components[matched:]


def _tokens_for(blocks: list[str]) -> tuple[list[Token], list[list[int]]]:
    from ...greek.tokenize import tokenize

    tokens: list[Token] = []
    lines: list[list[int]] = []
    pos = 0
    for line_no, block in enumerate(blocks):
        idxs: list[int] = []
        for tok in tokenize(block):
            tokens.append(
                Token(tok.text, tok.kind, line_no=line_no, position=pos)
            )
            idxs.append(pos)
            pos += 1
        lines.append(idxs)
    return tokens, lines


def parse_tei_work(
    blob: bytes, work: str, ref: str | None = None
) -> tuple[str, str, list[Document]]:
    """Parse one TEI work file into ``(title, author, documents)``.

    Without ``ref``: one `Document` per top-level textpart of the edition div (an
    Iliad book, a prose chapter run). With ``ref`` (e.g. ``"1"``, ``"1.2"``,
    ``"1.1-1.50"``): the matching textpart or verse line-range is selected —
    nested ``<div>``s are addressed by their ``n``, and a trailing numeric range
    filters verse ``<l>`` lines. ``<note>``/``<bibl>`` are kept in
    ``DocumentMeta.notes`` (excluded from the running text, not dropped)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(blob)
    title_el = root.find(f".//{_TEI}titleStmt/{_TEI}title")
    for cand in root.iterfind(f".//{_TEI}titleStmt/{_TEI}title"):
        if cand.get(_XML_LANG) == "grc":
            title_el = cand
            break
    title = _line_text(title_el) if title_el is not None else work
    author_el = root.find(f".//{_TEI}titleStmt/{_TEI}author")
    author = _line_text(author_el) if author_el is not None else ""

    body = root.find(f".//{_TEI}body")
    if body is None:
        raise ValueError(f"{work}: no TEI <body>")
    edition_div = next(
        (d for d in body.iterfind(f"{_TEI}div") if d.get("type") == "edition"),
        body.find(f"{_TEI}div"),
    )
    if edition_div is None:
        raise ValueError(f"{work}: no edition <div>")

    def make_doc(
        part: Any, id_suffix: str, name_suffix: str, lo: int | None, hi: int | None
    ) -> Document | None:
        tokens, lines = _tokens_for(_blocks(part, lo, hi))
        if not tokens:
            return None
        return Document(
            id=f"{work}:{id_suffix}", script_id="greek", tokens=tokens, lines=lines,
            meta=DocumentMeta(name=f"{title} — {name_suffix}".strip(), notes=_collect_notes(part)),
        )

    if ref is not None:
        start, end = _parse_ref(ref)
        part, rest = _navigate(edition_div, start)
        _, end_rest = _navigate(edition_div, end)
        lo = int(rest[-1]) if rest and rest[-1].isdigit() else None
        hi = int(end_rest[-1]) if end_rest and end_rest[-1].isdigit() else lo
        doc = make_doc(part, ref, ref, lo, hi)
        if doc is None:
            raise ValueError(f"{work}: ref {ref!r} selected no text")
        return title, author, [doc]

    parts = [d for d in edition_div.iterfind(f"{_TEI}div")] or [edition_div]
    docs: list[Document] = []
    for i, part in enumerate(parts, start=1):
        n = part.get("n") or str(i)
        subtype = part.get("subtype") or "part"
        doc = make_doc(part, n, f"{subtype} {n}".strip(), None, None)
        if doc is not None:
            docs.append(doc)
    return title, author, docs


def load_work(
    work: str,
    *,
    ref: str | None = None,
    source: str = "auto",
    edition: str | None = None,
    force: bool = False,
) -> "Corpus":
    """Load one Greek work from Perseus canonical-greekLit / First1KGreek.

    ``work`` is the CTS-style id (``"tlg0012.tlg001"`` = the Iliad). ``source``
    is ``"perseus"``, ``"first1k"``, or ``"auto"`` (try both, in that order);
    ``edition`` picks a specific edition file when a work has several. The TEI
    file is fetched once into the cache (network on first use only).

    ``ref`` selects a sub-section instead of the whole work — a citation address
    matching the work's structure: a textpart number (``"1"`` = Iliad book 1),
    a nested div path (``"1.2"`` = book 1, chapter 2 of a prose work), or a verse
    line-range (``"1.1-1.50"`` = book 1, lines 1–50). Without it, the corpus is
    one `Document` per top-level textpart. ``<note>``/``<bibl>`` ride along in
    ``Document.meta.notes``. Raises `aegean.data.DataNotAvailableError` when the
    work can't be found/fetched, or `ValueError` when ``ref`` matches nothing."""
    from ...core.corpus import Corpus

    blob, src, filename = _fetch_xml(work, source, edition, force)
    title, author, docs = parse_tei_work(blob, work, ref)

    repo, _, license_ = _SOURCES[src]
    commit = _ref(src)
    scope = f"ref {ref} of {work}" if ref else f"every textpart of {work}"
    provenance = Provenance(
        source=f"{repo} ({filename})",
        license=license_,
        citation=f"{author}. {title}. Digitized by the Perseus Digital Library / Open Greek and Latin.".lstrip(". "),
        url=f"https://github.com/{repo}/blob/{commit}/{_work_dir(work)}/{filename}",
        data_version=f"{repo}@{commit[:12]}",
        notes=(f"fetched to cache; {scope}",),
    )
    return Corpus(docs, None, provenance, "greek")
