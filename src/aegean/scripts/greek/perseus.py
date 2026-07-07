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
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ...core.model import Document, DocumentMeta, Token
from ...core.provenance import Provenance
from ...data import DataNotAvailableError, FetchAborted, cache_dir

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

# The work id lives at the head of a cached edition filename
# (``tlg0012.tlg001.perseus-grc2.xml`` -> ``tlg0012.tlg001``).
_WORK_ID_FROM_FILE = re.compile(r"^(tlg\d+\.tlg\d+)", re.IGNORECASE)
# Offline / bad-token fail-fast for the bulk loop: after this many works fail in a
# row, stop rather than grind through hundreds of identical timeouts.
_MAX_CONSECUTIVE_FAILURES = 3


class GitHubRateLimitError(DataNotAvailableError):
    """The unauthenticated GitHub contents API (~60 requests/hour) is exhausted.

    Raised distinctly from a generic fetch failure so a bulk run can stop cleanly
    instead of burning the next request. Set ``PYAEGEAN_GITHUB_TOKEN`` or
    ``GITHUB_TOKEN`` to raise the limit to 5,000/hour."""


@dataclass(frozen=True)
class WorkFetchResult:
    """One work's outcome in a bulk fetch: ``status`` is ``"fetched"`` (downloaded
    now), ``"cached"`` (already on disk, no network), or ``"failed"`` (``error``
    holds why). A dataclass so the CLI ``--json`` path serialises it directly."""

    id: str
    author: str
    title: str
    status: str
    error: str | None = None


def _rate_limit_message(reset: str | None) -> str:
    when = ""
    if reset and reset.isdigit():
        import time

        when = " (resets ~" + time.strftime("%H:%M", time.localtime(int(reset))) + ")"
    return (
        "GitHub API rate limit reached" + when + ". The unauthenticated limit is ~60 "
        "requests/hour; set PYAEGEAN_GITHUB_TOKEN or GITHUB_TOKEN to raise it to 5,000/hour."
    )


def _ref(source: str) -> str:
    return os.environ.get(_ENV_REF[source]) or _SOURCES[source][1]


def _work_dir(work: str) -> str:
    group, _, piece = work.partition(".")
    if not (group and piece):
        raise ValueError(f"work must look like 'tlg0012.tlg001', got {work!r}")
    # The id is spliced into a GitHub URL pinned to PerseusDL/canonical-greekLit@<commit>;
    # a path separator or ".." would let a crafted id escape that repo/commit and fetch a
    # forged edition from an arbitrary repository. Reject them (the guard the MCP tool has).
    if any(bad in work for bad in ("/", "\\", "..")):
        raise ValueError(f"work id must not contain a path separator or '..', got {work!r}")
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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            entries = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # GitHub signals an exhausted rate limit with 403 + X-RateLimit-Remaining: 0.
        if exc.code == 403 and (
            exc.headers.get("X-RateLimit-Remaining") == "0"
            or "rate limit" in (exc.reason or "").lower()
        ):
            raise GitHubRateLimitError(
                _rate_limit_message(exc.headers.get("X-RateLimit-Reset"))
            ) from exc
        raise
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
    from ...data import download_file

    tried: list[str] = []
    sources = [source] if source in _SOURCES else list(_SOURCES)
    for src in sources:
        repo, _, _license = _SOURCES[src]
        ref = _ref(src)
        try:
            names = _github_listing(repo, _work_dir(work), ref)
        except GitHubRateLimitError:
            # A rate limit is global — retrying the other source would waste another
            # request and every remaining work would fail identically. Stop now.
            raise
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
    ``"1.1-50"`` → ``(['1','1'], ['1','50'])`` (the hi inherits the lo's prefix).

    Malformed refs (empty components like ``"1..2"`` or ``".1"``, a stray ``"-"``)
    and descending verse ranges (``"1.50-1.1"``) raise `ValueError` with the reason."""
    if not ref.strip():
        raise ValueError("empty work ref")
    if "--" in ref or ref.startswith("-") or ref.endswith("-"):
        raise ValueError(f"malformed work ref {ref!r}: a range is 'lo-hi', e.g. '1.1-1.50'")
    lo, _sep, hi = ref.partition("-")

    def components(part: str, label: str) -> list[str]:
        comps = [c.strip() for c in part.split(".")]
        if any(c == "" for c in comps):
            raise ValueError(
                f"malformed work ref {ref!r}: empty component in {label} {part!r} "
                "(use e.g. '1', '1.2', or '1.1-1.50')"
            )
        return comps

    start = components(lo, "ref")
    if not hi:
        return start, list(start)
    end = components(hi, "range end")
    if len(end) < len(start):
        end = start[: len(start) - len(end)] + end
    if (
        start[-1].isdigit()
        and end[-1].isdigit()
        and start[:-1] == end[:-1]
        and int(end[-1]) < int(start[-1])
    ):
        raise ValueError(
            f"descending work ref {ref!r}: end {end[-1]} is before start {start[-1]}"
        )
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
    filters verse ``<l>`` lines. A range must stay within one textpart: a ref
    whose endpoints resolve to different textparts (``"1.1-2.50"``) raises
    `ValueError` naming both parts. ``<note>``/``<bibl>`` are kept in
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
        end_part, end_rest = _navigate(edition_div, end)
        if end_part is not part:
            # The two endpoints landed in different <div>s. Collecting across
            # textparts isn't supported (a Document is one textpart), and
            # returning the start part labeled with the full range would be a
            # silent truncation — refuse instead.
            def where(components: list[str], unmatched: list[str]) -> str:
                matched = components[: len(components) - len(unmatched)]
                return f"textpart {'.'.join(matched)}" if matched else "no matching textpart"

            raise ValueError(
                f"{work}: ref {ref!r} crosses textparts: the range start resolves to "
                f"{where(start, rest)} but the end to {where(end, end_rest)}. A range "
                "must stay within one textpart; load each part separately (one "
                "load_work call per book/chapter) and merge the corpora."
            )
        def selected_no_text(lo: "int | None") -> ValueError:
            avail = [d.get("n") for d in part.iterfind(f"{_TEI}div") if d.get("n")]
            if avail:
                hint = f"; sections here: {', '.join(str(a) for a in avail[:12])}"
            elif lo is not None:
                nums = [n for n in (_line_num(el) for el in part.iter(f"{_TEI}l")) if n is not None]
                hint = f"; lines present: {min(nums)}–{max(nums)}" if nums else ""
            else:
                hint = ""
            return ValueError(f"{work}: ref {ref!r} selected no text{hint}")

        # After navigation, the only legitimate leftover is a single numeric verse-line
        # selector. Anything else (a non-numeric component like "abc", or several
        # unmatched components) means the ref did not resolve: refuse, instead of
        # silently falling back to the whole part mislabeled with the ref.
        for leftover in (rest, end_rest):
            if leftover and (not leftover[-1].isdigit() or len(leftover) > 1):
                raise selected_no_text(None)
        lo = int(rest[-1]) if rest and rest[-1].isdigit() else None
        hi = int(end_rest[-1]) if end_rest and end_rest[-1].isdigit() else lo
        doc = make_doc(part, ref, ref, lo, hi)
        if doc is None:
            raise selected_no_text(lo)
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
    line-range (``"1.1-1.50"`` = book 1, lines 1–50). A range must stay within a
    single textpart: ``"1.1-2.50"`` (crossing from book 1 into book 2) raises
    `ValueError`; load each book separately and `Corpus.merge` the results.
    Without ``ref``, the corpus is one `Document` per top-level textpart.
    ``<note>``/``<bibl>`` ride along in ``Document.meta.notes``. Raises
    `aegean.data.DataNotAvailableError` when the work can't be found/fetched, or
    `ValueError` when ``ref`` matches nothing."""
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


# A small, curated catalog of well-known works for discovery. Every id below was verified to
# resolve against the live source. This is a STARTING POINT, not the full canon: load_work
# accepts any Perseus canonical-greekLit / First1KGreek CTS id — browse the complete
# catalogue at the Scaife Viewer (https://scaife.perseus.org).
POPULAR_WORKS: tuple[dict[str, str], ...] = (
    {"id": "tlg0012.tlg001", "author": "Homer", "title": "Iliad"},
    {"id": "tlg0012.tlg002", "author": "Homer", "title": "Odyssey"},
    {"id": "tlg0020.tlg001", "author": "Hesiod", "title": "Theogony"},
    {"id": "tlg0020.tlg002", "author": "Hesiod", "title": "Works and Days"},
    {"id": "tlg0085.tlg004", "author": "Aeschylus", "title": "Seven Against Thebes"},
    {"id": "tlg0085.tlg005", "author": "Aeschylus", "title": "Agamemnon"},
    {"id": "tlg0085.tlg006", "author": "Aeschylus", "title": "Libation Bearers"},
    {"id": "tlg0011.tlg001", "author": "Sophocles", "title": "Trachiniae"},
    {"id": "tlg0011.tlg002", "author": "Sophocles", "title": "Antigone"},
    {"id": "tlg0011.tlg003", "author": "Sophocles", "title": "Ajax"},
    {"id": "tlg0011.tlg004", "author": "Sophocles", "title": "Oedipus Tyrannus"},
    {"id": "tlg0006.tlg001", "author": "Euripides", "title": "Cyclops"},
    {"id": "tlg0006.tlg002", "author": "Euripides", "title": "Alcestis"},
    {"id": "tlg0006.tlg003", "author": "Euripides", "title": "Medea"},
    {"id": "tlg0019.tlg002", "author": "Aristophanes", "title": "Knights"},
    {"id": "tlg0019.tlg003", "author": "Aristophanes", "title": "Clouds"},
    {"id": "tlg0016.tlg001", "author": "Herodotus", "title": "Histories"},
    {"id": "tlg0003.tlg001", "author": "Thucydides", "title": "History of the Peloponnesian War"},
    {"id": "tlg0032.tlg002", "author": "Xenophon", "title": "Memorabilia"},
    {"id": "tlg0032.tlg006", "author": "Xenophon", "title": "Anabasis"},
    {"id": "tlg0059.tlg002", "author": "Plato", "title": "Apology"},
    {"id": "tlg0059.tlg003", "author": "Plato", "title": "Crito"},
    {"id": "tlg0059.tlg004", "author": "Plato", "title": "Phaedo"},
    {"id": "tlg0059.tlg030", "author": "Plato", "title": "Republic"},
    {"id": "tlg0086.tlg010", "author": "Aristotle", "title": "Nicomachean Ethics"},
)


def popular_works() -> list[dict[str, str]]:
    """A curated, verified catalog of well-known Greek works loadable with :func:`load_work`.

    Each entry is ``{'id', 'author', 'title'}`` where ``id`` is the CTS id passed to
    ``load_work`` (e.g. ``'tlg0012.tlg001'`` → the Iliad). This is a deliberately small
    starting point — for the full reachable canon use :func:`catalog`, or browse the
    Scaife Viewer (https://scaife.perseus.org). Pure metadata — no download."""
    return [dict(w) for w in POPULAR_WORKS]


@lru_cache(maxsize=1)
def _catalogue() -> tuple[dict[str, str], ...]:
    """The bundled discovery index, loaded once (metadata only — never the texts)."""
    from ...data import load_bundled_json

    data = load_bundled_json("greek", "works_catalogue.json")
    return tuple(dict(w) for w in data["works"])


def catalog(
    query: str | None = None,
    *,
    author: str | None = None,
    title: str | None = None,
    source: str | None = None,
) -> list[dict[str, str]]:
    """Search the **full** bundled index of Greek works loadable with :func:`load_work`.

    Unlike :func:`popular_works` (25 curated highlights), this covers every work with a
    Greek (``-grc``) edition in Perseus canonical-greekLit + First1KGreek — ~1,800 works.
    Each entry is ``{'id', 'author', 'title', 'greek_title', 'source'}``; pass any ``id``
    straight to ``load_work``. Pure bundled metadata — no network, no download.

    All filters are case-insensitive substring matches and combine with AND:

    * ``query`` — matches across id, author, English title, and Greek title (the catch-all)
    * ``author`` — e.g. ``"plato"``
    * ``title`` — matches the English **or** Greek title
    * ``source`` — ``"perseus"`` or ``"first1k"``

    Returns a list of dicts; pure bundled metadata, so it works offline and is instant.
    """
    works = _catalogue()

    def keep(w: dict[str, str]) -> bool:
        if author and author.lower() not in w["author"].lower():
            return False
        if title and title.lower() not in f"{w['title']} {w.get('greek_title', '')}".lower():
            return False
        if source and w["source"] != source:
            return False
        if query:
            hay = f"{w['id']} {w['author']} {w['title']} {w.get('greek_title', '')}".lower()
            if query.lower() not in hay:
                return False
        return True

    return [dict(w) for w in works if keep(w)]


def list_fetched_works() -> list[dict[str, Any]]:
    """Which Greek works are already downloaded to the cache — a pure local scan, no network.

    Walks ``cache_dir()/greek-works/<source>/<commit>/*.xml``, recovers each CTS id from the
    edition filename (``tlg0012.tlg001.perseus-grc2.xml`` -> ``tlg0012.tlg001``), and joins the
    bundled catalogue for author/title. Returns ``[{'id','author','title','source','path','bytes'}]``
    sorted by id (one entry per work, even if present under several sources/commits); ``[]`` when
    nothing is cached. Ignores the ``listings/`` cache and any ``.part``/``.lock`` files."""
    root = cache_dir() / "greek-works"
    if not root.exists():
        return []
    by_id = {w["id"]: w for w in _catalogue()}
    seen: dict[str, dict[str, Any]] = {}
    for source_dir in sorted(root.iterdir()):
        if not source_dir.is_dir() or source_dir.name == "listings":
            continue
        for commit_dir in sorted(source_dir.iterdir()):
            if not commit_dir.is_dir():
                continue
            for xml in sorted(commit_dir.glob("*.xml")):
                match = _WORK_ID_FROM_FILE.match(xml.name)
                if match is None:
                    continue
                work_id = match.group(1)
                if work_id in seen:
                    continue
                meta = by_id.get(work_id, {})
                seen[work_id] = {
                    "id": work_id,
                    "author": meta.get("author", ""),
                    "title": meta.get("title", ""),
                    "source": source_dir.name,
                    "path": str(xml),
                    "bytes": xml.stat().st_size,
                }
    return sorted(seen.values(), key=lambda w: w["id"])


def fetch_works(
    author: str | None = None,
    *,
    works: list[dict[str, str]] | None = None,
    source: str | None = None,
    force: bool = False,
    limit: int | None = None,
    on_progress: Callable[[int, int, dict[str, str]], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> Iterator[WorkFetchResult]:
    """Fetch every catalogue work matching ``author`` into the cache, yielding a
    :class:`WorkFetchResult` per work as it completes.

    Shared by the CLI (``greek work all``) and the TUI works screen. ``works`` overrides the
    catalogue query (pass a pre-filtered list). Already-cached works are yielded ``"cached"`` with
    no network, so re-running resumes idempotently. ``on_progress(i, total, work)`` fires BEFORE
    each work (a UI "downloading…" cue). ``limit`` caps NEW downloads (cached works do not count).
    ``abort()`` is polled between works.

    Terminal conditions raise, so the caller learns why the batch stopped:
    :class:`GitHubRateLimitError` (API exhausted), :class:`aegean.data.FetchAborted` (aborted), or
    :class:`aegean.data.DataNotAvailableError` (stopped after too many consecutive failures)."""
    items = works if works is not None else catalog(author=author, source=source)
    total = len(items)
    fetched_ids = {w["id"] for w in list_fetched_works()}
    attempted = 0
    consecutive_failures = 0
    for i, work in enumerate(items, start=1):
        if abort is not None and abort():
            raise FetchAborted("bulk fetch canceled")
        if on_progress is not None:
            on_progress(i, total, work)
        wid, wauthor, wtitle = work["id"], work.get("author", ""), work.get("title", "")
        if not force and wid in fetched_ids:
            yield WorkFetchResult(wid, wauthor, wtitle, "cached")
            continue
        if limit is not None and attempted >= limit:
            return  # the NEW-download cap is reached; stop cleanly
        attempted += 1
        try:
            load_work(wid, source=source or "auto", force=force)
            consecutive_failures = 0
            yield WorkFetchResult(wid, wauthor, wtitle, "fetched")
        except GitHubRateLimitError:
            raise  # global — stop the whole batch
        except Exception as exc:  # noqa: BLE001 — this work only; keep going
            consecutive_failures += 1
            yield WorkFetchResult(wid, wauthor, wtitle, "failed", str(exc))
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                raise DataNotAvailableError(
                    f"stopped after {consecutive_failures} consecutive failures — check your "
                    "connection, or set PYAEGEAN_GITHUB_TOKEN"
                ) from exc
