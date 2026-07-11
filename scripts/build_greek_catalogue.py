"""Build the bundled Greek-works discovery catalogue.

Crawls the two upstream repositories that :func:`aegean.greek.load_work` fetches
from — Perseus ``canonical-greekLit`` and ``First1KGreek`` — at the *pinned*
commits recorded in ``aegean.scripts.greek.perseus._SOURCES``, and writes a
metadata-only index of every work that has a Greek (``-grc``) edition:

    {"id": "tlg0012.tlg001", "author": "Homer", "title": "Iliad",
     "greek_title": "Ἰλιάς", "source": "perseus"}

Only facts (author/title/id) are recorded — never the texts — so the bundled
JSON stays license-clean (the texts themselves are CC BY-SA and are fetched on
demand, never bundled). The result is ``src/aegean/data/bundled/greek/works_catalogue.json``.

Usage:
    python scripts/build_greek_catalogue.py            # writes the bundled JSON
    python scripts/build_greek_catalogue.py --out X    # to a different path

Auth: tree listing uses the GitHub API. Set GITHUB_TOKEN / PYAEGEAN_GITHUB_TOKEN,
or have the `gh` CLI authenticated (the script falls back to `gh auth token`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Import the pins from the package so the catalogue can never drift from what
# load_work actually fetches.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from aegean.scripts.greek.perseus import _SOURCES  # noqa: E402

_CTS = "{http://chs.harvard.edu/xmlns/cts}"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_WORK_DIR_RE = re.compile(r"data/(tlg\d+)/(tlg\d+)/")
_OUT_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "src" / "aegean" / "data" / "bundled" / "greek" / "works_catalogue.json"
)


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("PYAEGEAN_GITHUB_TOKEN")
    if tok:
        return tok
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 — best effort; unauth still works for raw fetches
        pass
    return ""


def _get(url: str, token: str = "", *, retries: int = 2) -> bytes:
    headers = {"User-Agent": "pyaegean-catalogue"}
    # exact-hostname check: a substring test would leak the token to any URL that
    # merely CONTAINS "api.github.com" (in a path or query)
    if token and urlsplit(url).hostname == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()  # type: ignore[no-any-return]
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"GET failed {url}: {last}")


def _grc_works(repo: str, ref: str, token: str) -> set[str]:
    """Unique ``group.work`` ids that have a ``-grc*.xml`` edition (what load_work loads)."""
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    tree = json.loads(_get(url, token))
    if tree.get("truncated"):
        raise RuntimeError(f"{repo} tree truncated — need a paginated crawl")
    works: set[str] = set()
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        if entry.get("type") != "blob" or not path.endswith(".xml"):
            continue
        name = path.rsplit("/", 1)[-1]
        if name.startswith("__") or "-grc" not in name:
            continue
        m = _WORK_DIR_RE.search(path)
        if m:
            works.add(f"{m.group(1)}.{m.group(2)}")
    return works


def _pick_lang(elems: list[ET.Element], prefer: str) -> str:
    """Text of the preferred-language element, else the first non-empty one."""
    chosen = next((e for e in elems if e.get(_XML_LANG) == prefer), None)
    if chosen is None:
        chosen = next((e for e in elems if (e.text or "").strip()), None)
    return " ".join((chosen.text or "").split()) if chosen is not None else ""


def _raw_url(repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def _author(repo: str, ref: str, group: str, token: str) -> str:
    try:
        blob = _get(_raw_url(repo, ref, f"data/{group}/__cts__.xml"))
        root = ET.fromstring(blob)
        return _pick_lang(root.findall(f"{_CTS}groupname"), "eng")
    except Exception:  # noqa: BLE001
        return ""


def _title(repo: str, ref: str, work: str, token: str) -> tuple[str, str]:
    """(english_title, greek_title) from a work's __cts__.xml."""
    group, piece = work.split(".")
    try:
        blob = _get(_raw_url(repo, ref, f"data/{group}/{piece}/__cts__.xml"))
        root = ET.fromstring(blob)
    except Exception:  # noqa: BLE001
        return "", ""
    title = _pick_lang(root.findall(f"{_CTS}title"), "eng")
    grc = ""
    for ed in root.findall(f"{_CTS}edition"):
        if "-grc" in (ed.get("urn") or "") or ed.get(_XML_LANG) == "grc":
            label = ed.find(f"{_CTS}label")
            if label is not None and (label.text or "").strip():
                grc = " ".join(label.text.split())
                break
    if not title:  # last resort: a grc <title>, then the grc edition label
        title = _pick_lang(root.findall(f"{_CTS}title"), "grc") or grc
    return title, grc


def _harvest(source: str, token: str) -> dict[str, dict[str, str]]:
    repo, ref, _license = _SOURCES[source]
    print(f"[{source}] {repo}@{ref[:12]} — listing tree …", flush=True)
    works = sorted(_grc_works(repo, ref, token))
    groups = sorted({w.split(".")[0] for w in works})
    print(f"[{source}] {len(works)} grc works, {len(groups)} authors — fetching metadata …", flush=True)

    with ThreadPoolExecutor(max_workers=16) as pool:
        authors = dict(zip(groups, pool.map(lambda g: _author(repo, ref, g, token), groups)))
        titles = dict(zip(works, pool.map(lambda w: _title(repo, ref, w, token), works)))

    out: dict[str, dict[str, str]] = {}
    for w in works:
        title, greek_title = titles[w]
        out[w] = {
            "id": w,
            "author": authors.get(w.split(".")[0], ""),
            "title": title or w,
            "greek_title": greek_title,
            "source": source,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=_OUT_DEFAULT)
    args = ap.parse_args()
    token = _token()
    if not token:
        print("warning: no GitHub token — tree listing may hit the 60/hr limit", file=sys.stderr)

    # Perseus first so its entry wins on a collision (load_work tries perseus first).
    merged: dict[str, dict[str, str]] = {}
    for source in ("perseus", "first1k"):
        harvest = _harvest(source, token)
        for work_id, rec in harvest.items():
            if work_id in merged:
                # keep the existing (perseus) record but backfill empty fields
                for k, v in rec.items():
                    if k != "source" and not merged[work_id].get(k):
                        merged[work_id][k] = v
            else:
                merged[work_id] = rec

    works = [merged[k] for k in sorted(merged)]
    payload = {
        "_meta": {
            "description": "Discovery index of Ancient Greek works with a Greek (-grc) edition "
            "loadable via aegean.greek.load_work(). Metadata only — texts are CC BY-SA and "
            "fetched on demand, never bundled.",
            "sources": {
                src: {"repo": _SOURCES[src][0], "ref": _SOURCES[src][1], "license": _SOURCES[src][2]}
                for src in ("perseus", "first1k")
            },
            "count": len(works),
        },
        "works": works,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=0, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    size = args.out.stat().st_size
    with_author = sum(1 for w in works if w["author"])
    with_title = sum(1 for w in works if w["title"] != w["id"])
    print(
        f"wrote {len(works)} works to {args.out} ({size // 1024} KB); "
        f"{with_author} have an author, {with_title} a real title"
    )


if __name__ == "__main__":
    main()
