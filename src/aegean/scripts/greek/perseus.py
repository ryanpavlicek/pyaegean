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
        "requests/hour; authenticate to raise it to 5,000/hour: run `gh auth login`, or set "
        "PYAEGEAN_GITHUB_TOKEN / GITHUB_TOKEN / GH_TOKEN."
    )


@lru_cache(maxsize=1)
def _gh_cli_token() -> str | None:
    """The token stored by the GitHub CLI (``gh auth login``), or ``None``.

    Many machines are authenticated through ``gh`` (the token lives in the OS keyring, not an
    environment variable), so this lets an already-``gh``-authenticated user hit the higher rate
    limit without exporting anything. Cached, so the subprocess runs at most once per process."""
    import shutil
    import subprocess

    if shutil.which("gh") is None:
        return None
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    token = result.stdout.strip()
    return token or None


def _github_token() -> str | None:
    """A GitHub token to raise the API rate limit, discovered in order: the
    ``PYAEGEAN_GITHUB_TOKEN`` / ``GITHUB_TOKEN`` / ``GH_TOKEN`` environment variables, then the
    GitHub CLI's stored auth (``gh auth token``) when ``gh`` is installed."""
    return (
        os.environ.get("PYAEGEAN_GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or _gh_cli_token()
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
    token = _github_token()
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


def _citation_scheme(root: Any) -> list[str]:
    """The ordered citation levels a work declares, read from its TEI ``<refsDecl>``.

    A CTS ``<cRefPattern n="LEVEL" matchPattern="(…)…">`` names one citation LEVEL
    (the deepest it addresses); the number of capture groups in its ``matchPattern``
    is that level's depth (1 = the top level). Read shallow→deep, the level names
    are the work's citation scheme, exactly as the edition declares it and with no
    author-specific guessing: the Iliad → ``["book", "line"]``, a Plato dialogue →
    ``["section"]``, Xenophon's Anabasis → ``["book", "chapter", "section"]``,
    Aristotle's Poetics → ``["chapter", "subchapter"]``. Returns ``[]`` when the
    work declares no CTS ``refsDecl`` (nothing to name; the caller falls back to
    generic wording). Descriptive only — this is what to try, not a promise every
    value resolves."""
    decls = list(root.iter(f"{_TEI}refsDecl"))
    patterns: list[Any] = []
    for decl in decls:  # prefer the CTS refsDecl when several are declared
        if decl.get("n") == "CTS":
            patterns = list(decl.iter(f"{_TEI}cRefPattern"))
            break
    if not patterns:
        for decl in decls:
            found = list(decl.iter(f"{_TEI}cRefPattern"))
            if found:
                patterns = found
                break
    by_depth: dict[int, str] = {}
    for pat in patterns:  # a commented-out cRefPattern is XML comment text, not an element
        name = (pat.get("n") or "").strip()
        match_pattern = pat.get("matchPattern") or ""
        if not name or not match_pattern:
            continue
        try:
            depth = re.compile(match_pattern).groups
        except re.error:
            depth = match_pattern.count("(") - match_pattern.count("(?")
        if depth < 1:
            continue
        by_depth.setdefault(depth, name)  # shallowest wins a depth (CTS declares one each)
    return [by_depth[d] for d in sorted(by_depth)]


def _scheme_path(scheme: list[str]) -> str:
    """The citation scheme as a dotted path for a message (``"book.line"``); a
    ``|``-alternated level name (the CapiTainS ``"epigraph|book"``) reads as
    ``epigraph/book``."""
    return ".".join(level.replace("|", "/") for level in scheme)


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


def _make_doc(
    work: str, title: str, part: Any, id_suffix: str, name_suffix: str,
    lo: int | None, hi: int | None,
) -> Document | None:
    """One `Document` from a textpart (optionally a verse line-range ``lo``–``hi``);
    ``None`` when the selection contains no text."""
    tokens, lines = _tokens_for(_blocks(part, lo, hi))
    if not tokens:
        return None
    return Document(
        id=f"{work}:{id_suffix}", script_id="greek", tokens=tokens, lines=lines,
        meta=DocumentMeta(name=f"{title} — {name_suffix}".strip(), notes=_collect_notes(part)),
    )


def _milestone_events(el: Any) -> list[tuple[str, Any]]:
    """Document-order stream of ``("ms", <milestone>)`` / ``("text", str)`` events over
    ``el``, skipping the editorial subtrees `_line_text` skips.

    A ``<milestone>`` is an empty marker: its content is the text that follows it (its
    tail, then following siblings) up to the next marker. Flattening to one stream makes
    that span recoverable across element nesting and even across ``<div>`` boundaries — a
    Bekker page runs through several subchapter divs, so a per-``<p>`` sibling walk would
    truncate it."""
    events: list[tuple[str, Any]] = []

    def walk(node: Any) -> None:
        if node.tag in _SKIP_TAGS:
            return
        if node.tag == f"{_TEI}milestone":
            events.append(("ms", node))
        if node.text:
            events.append(("text", node.text))
        for child in node:
            walk(child)
            if child.tail:
                events.append(("text", child.tail))

    walk(el)
    return events


def _select_milestone(
    part: Any, work: str, title: str, ref: str, marker: str
) -> Document | None:
    """Resolve a ref that names a ``<milestone>`` marker rather than a ``<div>`` — a
    Stephanus sub-page (Plato ``"17a"``) or a Bekker line (Aristotle ``"1447a10"``) the
    edition prints in the margin, outside the CTS ``<div>`` citation scheme.

    The span is the text between the matching marker and the next marker of the same
    ``unit`` — exactly what the markup delimits. Two shapes are read, both generic (no
    author or unit-name hardcoding — only the declared ``unit``/``n`` attributes):

    * a marker whose ``n`` equals ``marker`` (a Stephanus ``n="17a"``, a Bekker page
      ``n="1447a"``): the span runs to the next same-``unit`` marker;
    * a ``page+line`` composite (``"1447a10"``, where the line milestone carries the
      page-relative ``n="10"``): the longest marker ``n`` that is a proper prefix (the
      Bekker page ``"1447a"``) anchors a coarse span, and within it the marker whose
      ``n`` is the remainder (the line ``"10"``) delimits the span.

    Returns ``None`` when no marker matches (the caller then raises the scheme-naming
    error), so a work with no such markers behaves exactly as before."""
    events = _milestone_events(part)
    markers = [(i, ev[1]) for i, ev in enumerate(events) if ev[0] == "ms"]
    if not markers:
        return None

    def span_to(start_i: int, boundary_unit: str | None, hi: int) -> str:
        """Text from just after ``start_i`` to the next same-``boundary_unit`` marker
        before ``hi`` (else ``hi``)."""
        end = hi
        for j in range(start_i + 1, hi):
            if events[j][0] == "ms" and events[j][1].get("unit") == boundary_unit:
                end = j
                break
        text = "".join(e[1] for e in events[start_i + 1 : end] if e[0] == "text")
        return " ".join(text.split())

    text: str | None = None
    exact = [(i, m) for i, m in markers if (m.get("n") or "") == marker]
    if len(exact) == 1:
        i0, m0 = exact[0]
        text = span_to(i0, m0.get("unit"), len(events))
    elif not exact:
        # page+line composite: the longest marker n that is a *proper* prefix of the ref
        prefixes = [
            (i, m)
            for i, m in markers
            if (m.get("n") or "") and m.get("n") != marker and marker.startswith(m.get("n") or "")
        ]
        if prefixes:
            i0, coarse = max(prefixes, key=lambda im: len(im[1].get("n") or ""))
            remainder = marker[len(coarse.get("n") or "") :]
            # the coarse (page) span bounds the finer (line) search, so a page-relative
            # line n like "10" resolves to the "10" of *this* page, not any other
            coarse_end = len(events)
            for j in range(i0 + 1, len(events)):
                if events[j][0] == "ms" and events[j][1].get("unit") == coarse.get("unit"):
                    coarse_end = j
                    break
            fine = [
                (j, m)
                for j, m in markers
                if i0 < j < coarse_end and (m.get("n") or "") == remainder
            ]
            if len(fine) == 1:
                j0, f0 = fine[0]
                text = span_to(j0, f0.get("unit"), coarse_end)
    if not text:
        return None
    tokens, lines = _tokens_for([text])
    if not tokens:
        return None
    return Document(
        id=f"{work}:{ref}",
        script_id="greek",
        tokens=tokens,
        lines=lines,
        meta=DocumentMeta(name=f"{title} — {ref}".strip()),
    )


def _select_ref(
    edition_div: Any, work: str, title: str, ref: str, scheme: list[str]
) -> Document:
    """Resolve ONE citation ref — a textpart (``"1"``), a nested div (``"1.2"``), or a
    verse line-range within one book (``"1.1-1.50"``); no comma — to a `Document`.

    ``scheme`` is the work's declared citation levels (from `_citation_scheme`); when
    present it makes the error messages name how the work is addressed (``"cited by
    book.line"``) and label the available values by the declared level. Raises
    `ValueError` for a range that crosses textparts, an endpoint that resolves
    nowhere, or a ref that selects no text (the message names the sections or line
    numbers that ARE present, so a wrong address is actionable)."""
    start, end = _parse_ref(ref)
    part, rest = _navigate(edition_div, start)
    end_part, end_rest = _navigate(edition_div, end)
    # Named only when the TEI declares one; empty scheme keeps the generic wording so a
    # work without a refsDecl (e.g. an authored fixture) reads exactly as before.
    scheme_note = f" — cited by {_scheme_path(scheme)}" if scheme else ""
    if end_part is not part:
        # The two endpoints landed in different <div>s. Collecting across textparts isn't
        # supported (a Document is one textpart), and returning the start part labeled with
        # the full range would be a silent truncation — refuse instead.
        def where(components: list[str], unmatched: list[str]) -> str:
            matched = components[: len(components) - len(unmatched)]
            return f"textpart {'.'.join(matched)}" if matched else "no matching textpart"

        lo_ref, _dash, hi_ref = ref.partition("-")
        raise ValueError(
            f"{work}: ref {ref!r} crosses textparts{scheme_note}: the range start resolves "
            f"to {where(start, rest)} but the end to {where(end, end_rest)}. A hyphen range "
            f"must stay within one textpart; pass a comma list "
            f"('{lo_ref.strip()},{hi_ref.strip()}') to get one document per part, or load "
            "each part separately and merge the corpora."
        )

    def selected_no_text(lo: "int | None") -> ValueError:
        matched = len(start) - len(rest)  # how deep navigation reached before failing
        avail = [d.get("n") for d in part.iterfind(f"{_TEI}div") if d.get("n")]
        if avail:
            if scheme:
                level = scheme[matched] if matched < len(scheme) else scheme[-1]
                hint = (
                    f"; {level.replace('|', '/')} values present: "
                    f"{', '.join(str(a) for a in avail[:12])}"
                )
            else:
                hint = f"; sections here: {', '.join(str(a) for a in avail[:12])}"
        elif lo is not None:
            nums = [n for n in (_line_num(el) for el in part.iter(f"{_TEI}l")) if n is not None]
            if not nums:
                hint = ""
            elif scheme:
                hint = f"; {scheme[-1].replace('|', '/')} values present: {min(nums)}–{max(nums)}"
            else:
                hint = f"; lines present: {min(nums)}–{max(nums)}"
        else:
            hint = ""
        return ValueError(f"{work}: ref {ref!r} selected no text{scheme_note}{hint}")

    # A single non-numeric leftover may name a <milestone> the edition prints in the
    # margin (a Stephanus sub-page "17a", a Bekker line "1447a10") rather than a <div>.
    # These live outside the CTS <div> scheme but are addressable by extracting the span
    # between the marker and the next. Only a single ref (no hyphen range) is milestone-
    # addressable; a range or multi-part path falls through to the scheme-naming error.
    if start == end and len(rest) == 1 and not rest[-1].isdigit():
        milestone_doc = _select_milestone(part, work, title, ref, rest[-1])
        if milestone_doc is not None:
            return milestone_doc

    # After navigation, the only legitimate leftover is a single numeric verse-line
    # selector. Anything else (a non-numeric component like "abc", or several unmatched
    # components) means the ref did not resolve: refuse, instead of silently falling back
    # to the whole part mislabeled with the ref.
    for leftover in (rest, end_rest):
        if leftover and (not leftover[-1].isdigit() or len(leftover) > 1):
            raise selected_no_text(None)
    lo = int(rest[-1]) if rest and rest[-1].isdigit() else None
    hi = int(end_rest[-1]) if end_rest and end_rest[-1].isdigit() else lo
    doc = _make_doc(work, title, part, ref, ref, lo, hi)
    if doc is None:
        raise selected_no_text(lo)
    return doc


def _dedup_refs(ref: str) -> list[str]:
    """The distinct entries of a comma-list ``ref``, stripped and in source order
    (exact duplicates dropped, blank entries skipped).

    Shared by `_select_refs` and `canonical_citation` so the citation lists exactly
    the distinct sections that were loaded: ``"1.1,1.1"`` loads one document and
    cites one section, ``"1.5,1.1"`` keeps that order in both."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in ref.split(","):
        seg = raw.strip()
        if seg and seg not in seen:
            seen.add(seg)
            out.append(seg)
    return out


def _select_refs(
    edition_div: Any, work: str, title: str, ref: str, scheme: list[str]
) -> list[Document]:
    """Resolve ``ref`` — one citation ref, or several comma-separated (``"1.1,1.5"``,
    ``"1,3"``) — to one `Document` per selection (source order preserved, exact
    duplicates dropped). Each comma entry is resolved independently, so a multi-ref may
    span textparts (``"1.1,2.1"``) even though a single hyphen-range may not. ``scheme``
    is the work's declared citation levels, threaded to each entry for its errors."""
    if "," not in ref:
        return [_select_ref(edition_div, work, title, ref, scheme)]
    if any(raw.strip() == "" for raw in ref.split(",")):
        raise ValueError(
            f"malformed work ref {ref!r}: an empty entry in the comma list "
            "(use e.g. '1.1,1.5' or '1,3')"
        )
    return [_select_ref(edition_div, work, title, seg, scheme) for seg in _dedup_refs(ref)]


def parse_tei_work(
    blob: bytes, work: str, ref: str | None = None
) -> tuple[str, str, list[Document]]:
    """Parse one TEI work file into ``(title, author, documents)``.

    Without ``ref``: one `Document` per top-level textpart of the edition div (an
    Iliad book, a prose chapter run). With ``ref``: the addressed section(s) —

    * a textpart or nested div by its ``n`` (``"1"`` = book 1, ``"1.2"`` = book 1
      chapter 2);
    * a verse line-range within one book (``"1.1-1.50"`` = book 1, lines 1–50; the
      hi may drop the repeated prefix, ``"1.1-50"``);
    * a ``<milestone>`` marker the edition prints in the margin, outside the CTS ``<div>``
      scheme — a Stephanus sub-page (Plato ``"17a"``) or a Bekker line (Aristotle
      ``"1447a10"``, the page ``1447a`` line ``10``): the addressed text is the span
      between the marker and the next of its kind. A whole Bekker/Stephanus page also
      resolves (``"1447a"``, ``"17"``);
    * several of the above as a **comma list** (``"1.1,1.5"``, ``"1,3"``, ``"17a,17b"``),
      giving one `Document` per entry, in source order (exact duplicates dropped).

    A hyphen **range** must stay within one textpart: ``"1.1-2.50"`` (or the
    whole-part ``"1-2"``) raises `ValueError` naming both parts. A **comma list** has
    no such limit — each entry is resolved independently — so ``"1,2"`` returns both
    parts as separate documents. ``<note>``/``<bibl>`` are kept in
    ``DocumentMeta.notes`` (excluded from the running text, not dropped).

    A ``ref`` that resolves nowhere raises `ValueError` naming the work's **declared
    citation scheme** (read from the TEI ``<refsDecl>``, see `citation_scheme`): a
    Plato dialogue reports ``cited by section``, the Iliad ``cited by book.line``, so
    the message says how to address the work rather than only that the ref missed."""
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

    if ref is not None:
        scheme = _citation_scheme(root)  # the declared citation levels, for the messages
        return title, author, _select_refs(edition_div, work, title, ref, scheme)

    parts = [d for d in edition_div.iterfind(f"{_TEI}div")] or [edition_div]
    docs: list[Document] = []
    for i, part in enumerate(parts, start=1):
        n = part.get("n") or str(i)
        subtype = part.get("subtype") or "part"
        doc = _make_doc(work, title, part, n, f"{subtype} {n}".strip(), None, None)
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
    a nested div path (``"1.2"`` = book 1, chapter 2 of a prose work), a verse
    line-range (``"1.1-1.50"`` = book 1, lines 1–50), a marginal ``<milestone>``
    marker outside the CTS ``<div>`` scheme (a Stephanus sub-page ``"17a"``, a Bekker
    line ``"1447a10"`` or a whole Bekker page ``"1447a"``), or a comma list of any of
    these (``"1.1,1.5"``, ``"1,3"``, ``"17a,17b"``) giving one `Document` per entry. A
    hyphen range must stay within a single textpart: ``"1.1-2.50"`` (crossing from book 1
    into book 2) raises `ValueError`; use a comma list, or load each book separately and
    `Corpus.merge` the results. Without ``ref``, the corpus is one `Document` per
    top-level textpart. The corpus provenance's ``citation`` is the **canonical**
    scholarly citation of exactly what was selected (``"Homer, Iliad 1.1-1.50"``; see
    `canonical_citation`), so ``corpus.cite()`` echoes the selection.
    ``<note>``/``<bibl>`` ride along in ``Document.meta.notes``. Raises
    `aegean.data.DataNotAvailableError` when the work can't be found/fetched, or
    `ValueError` when ``ref`` matches nothing — that message names the work's declared
    citation scheme (``cited by book.line``); `citation_scheme` returns it directly."""
    from ...core.corpus import Corpus

    blob, src, filename = _fetch_xml(work, source, edition, force)
    title, author, docs = parse_tei_work(blob, work, ref)

    repo, _, license_ = _SOURCES[src]
    commit = _ref(src)
    scope = f"ref {ref} of {work}" if ref else f"every textpart of {work}"
    canon = canonical_citation(work, ref, author, title)
    provenance = Provenance(
        source=f"{repo} ({filename})",
        license=license_,
        # The exact canonical citation of what was selected, then the digitization
        # attribution: "Homer, Iliad 1.1-1.50. Digitized by …".
        citation=f"{canon}. Digitized by the Perseus Digital Library / Open Greek and Latin.".lstrip(". "),
        url=f"https://github.com/{repo}/blob/{commit}/{_work_dir(work)}/{filename}",
        data_version=f"{repo}@{commit[:12]}",
        notes=(f"fetched to cache; {scope}",),
    )
    return Corpus(docs, None, provenance, "greek")


def canonical_citation(
    work: str, ref: str | None = None, author: str = "", title: str = ""
) -> str:
    """The canonical scholarly citation for a loaded work or the exact section selected.

    ``"Homer, Iliad 1.1-1.50"`` — author and title, then the canonical reference. A
    comma list of refs is joined with ``"; "`` (``"Homer, Iliad 1.1; 1.5"``), with the
    same order-preserving deduplication `load_work` applies, so the citation lists exactly
    the distinct sections loaded (``"1.1,1.1"`` cites ``"1.1"`` once). A whole-work load
    (``ref=None``) is just ``"Homer, Iliad"``. ``work`` (the CTS id) is the fallback lead
    when author/title are unknown. This is the string ``corpus.cite()`` reports for a
    loaded work, and what a ``--cite`` echo prints — the exact citation for what was
    selected, ready to paste into an apparatus or bibliography."""
    lead = ", ".join(p for p in (author.strip(), title.strip()) if p) or work
    if not ref or not ref.strip():
        return lead
    refs = "; ".join(_dedup_refs(ref))
    return f"{lead} {refs}" if refs else lead


def citation_scheme(
    work: str, *, source: str = "auto", edition: str | None = None, force: bool = False
) -> list[str]:
    """How a Greek work is addressed: its ordered citation levels, from the TEI edition.

    Reads the work's declared CTS ``<refsDecl>`` and returns the citation levels
    shallow→deep, exactly as the edition names them (no author-specific guessing):
    the Iliad → ``["book", "line"]``, a Plato dialogue → ``["section"]``, Xenophon's
    Anabasis → ``["book", "chapter", "section"]``, Aristotle's Poetics →
    ``["chapter", "subchapter"]``. So ``["book", "line"]`` means a ``--ref`` looks
    like ``1`` (a whole book) or ``1.1`` / ``1.1-1.50`` (a line or line-range within a
    book); a single-level ``["section"]`` means ``--ref 17`` (one section).

    Returns ``[]`` when the work declares no CTS ``refsDecl``. Like `load_work`, the
    TEI file is fetched once to the cache (``source``/``edition``/``force`` as there);
    this is metadata about the edition, not its text. It reports the CTS ``<div>``
    levels the edition declares. Finer references some editions print in the margin (a
    Stephanus sub-page ``17a``, a Bekker line ``1447a10``) live in ``<milestone>``
    markers *outside* the CTS scheme, so they are not part of the returned levels — but
    `load_work`'s ``ref`` does resolve them directly (it extracts the span between the
    marker and the next)."""
    import xml.etree.ElementTree as ET

    blob, _src, _filename = _fetch_xml(work, source, edition, force)
    return _citation_scheme(ET.fromstring(blob))


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


def remove_fetched_works(
    ids: list[str] | None = None, *, author: str | None = None, remove_all: bool = False
) -> list[str]:
    """Delete downloaded Greek works from the cache, returning the ids actually removed (sorted).

    Select the targets one of three ways: explicit ``ids``; every fetched work by an ``author``
    (case-insensitive substring of the catalogue author, the same match as ``greek catalog
    --author``); or ``remove_all``. A no-op returning ``[]`` when nothing matches or nothing is
    cached. Removes every cached edition file for each targeted work (across sources/commits) and
    prunes the now-empty source/commit directories. Never touches the ``listings/`` cache."""
    root = cache_dir() / "greek-works"
    if not root.exists():
        return []
    fetched_ids = {w["id"] for w in list_fetched_works()}
    if remove_all:
        targets = set(fetched_ids)
    elif author is not None:
        needle = author.strip().lower()
        by_author = {w["id"] for w in _catalogue() if needle and needle in w.get("author", "").lower()}
        targets = fetched_ids & by_author
    elif ids:
        targets = {i for i in ids if i in fetched_ids}
    else:
        targets = set()
    if not targets:
        return []
    removed: set[str] = set()
    for source_dir in sorted(root.iterdir()):
        if not source_dir.is_dir() or source_dir.name == "listings":
            continue
        for commit_dir in sorted(source_dir.iterdir()):
            if not commit_dir.is_dir():
                continue
            for xml in sorted(commit_dir.glob("*.xml")):
                match = _WORK_ID_FROM_FILE.match(xml.name)
                if match is not None and match.group(1) in targets:
                    xml.unlink()
                    removed.add(match.group(1))
            try:  # prune an emptied commit directory
                if not any(commit_dir.iterdir()):
                    commit_dir.rmdir()
            except OSError:
                pass
        try:  # prune an emptied source directory
            if source_dir.exists() and not any(source_dir.iterdir()):
                source_dir.rmdir()
        except OSError:
            pass
    return sorted(removed)


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
