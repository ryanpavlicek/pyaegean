"""Build the DDbDP document-URI map (repo-only; not shipped in the wheel).

The pyaegean ``ddbdp`` corpus stores each document's id as the idp.data file stem
(``bgu.1.100``, and division-suffixed stems such as ``aegyptus.103.69_1``) and a
``TM <id>`` note, but NOT the ``<idno type="ddb-hybrid">`` value (``bgu;1;100``)
that papyri.info document URLs are built from
(``https://papyri.info/ddbdp/bgu;1;100`` -- the semicolons are literal). Reversing
a stem to a hybrid is genuinely ambiguous: series names contain dots
(``c.epist.lat.10`` -> ``c.epist.lat;;10``) and many hybrids have an empty volume
component (the ``;;``), so a naive ``.`` -> ``;`` swap is wrong for tens of
thousands of documents. This script harvests the authoritative mapping straight
from the source rather than guessing it.

Source of truth: github.com/papyri/idp.data (CC BY 3.0), whose ``DDB_EpiDoc_XML``
files each carry their own ``<idno type="ddb-hybrid">``. Following
``build_ddbdp_corpus.py``, the corpus doc-id is exactly ``Path(path).stem`` of the
DDB file, so the harvested ``{stem: hybrid}`` map keys line up one-to-one with the
corpus ids (verified below).

Build technique (identical to build_ddbdp_corpus.py / build_edh_corpus.py):
``git clone --depth 1 --no-checkout`` pulls only the packfile (~236 MB, no 139k-file
working-tree checkout, which is pathological under Windows Defender), and
``git grep`` reads the ``ddb-hybrid`` idno lines straight out of that packfile in a
single process, no per-file filesystem opens. One grep over HEAD yields every
document's stem + hybrid.

Usage:
    python scripts/build_ddbdp_uri_map.py                 # clone to a temp dir, build, verify
    python scripts/build_ddbdp_uri_map.py <idp.data-clone>  # reuse an existing clone
    python scripts/build_ddbdp_uri_map.py -o ddbdp-uris.json.gz --clone-dir /path/to/clone

The output is a gzip-compressed JSON object ``{stem: hybrid}`` (the fetch layer's
``load_gzip_json`` reads it), hosted as the ``ddbdp-uris`` release asset and fetched
lazily by ``aegean.io.rdf`` to mint papyri.info document URIs.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_IDP_REPO = "https://github.com/papyri/idp.data.git"
# The ddb-hybrid idno as it appears verbatim in a DDB EpiDoc file.
_IDNO_RE = re.compile(r'<idno type="ddb-hybrid">(.*?)</idno>')
# A trailing ``_<digits>`` division suffix, stripped only as a FORWARD-COMPATIBLE
# fallback (see the note in verify(): every current corpus id resolves DIRECTLY).
_N_SUFFIX_RE = re.compile(r"_\d+$")


def parse_grep_line(line: str) -> tuple[str, str] | None:
    """Parse one ``git grep -n`` line into ``(stem, hybrid)``, or None if it has no
    ddb-hybrid idno.

    A grep line is ``HEAD:<path>:<lineno>:<content>``; the file stem gives the
    corpus doc-id base and the ``<idno type="ddb-hybrid">`` value gives the hybrid.
    XML entities in the idno text are unescaped (``&amp;`` -> ``&``)."""
    parts = line.split(":", 3)
    if len(parts) < 4:
        return None
    _head, path, _lineno, content = parts
    m = _IDNO_RE.search(content)
    if m is None:
        return None
    hybrid = html.unescape(m.group(1)).strip()
    if not hybrid:
        return None
    return Path(path).stem, hybrid


def harvest_map(grep_text: str) -> dict[str, str]:
    """Turn the raw ``git grep`` output into a ``{stem: hybrid}`` map (first hit wins
    per stem; a duplicate stem with a different hybrid is reported to stderr)."""
    out: dict[str, str] = {}
    for line in grep_text.splitlines():
        parsed = parse_grep_line(line)
        if parsed is None:
            continue
        stem, hybrid = parsed
        if stem in out and out[stem] != hybrid:
            print(
                f"WARNING: stem {stem!r} maps to both {out[stem]!r} and {hybrid!r}; "
                "keeping the first",
                file=sys.stderr,
            )
            continue
        out.setdefault(stem, hybrid)
    return out


def _git_grep_hybrids(repo: Path) -> str:
    """The raw ``git grep -n`` output for every ddb-hybrid idno under DDB_EpiDoc_XML,
    read from the clone's packfile at HEAD (one process, no working-tree checkout)."""
    return subprocess.run(
        ["git", "-C", str(repo), "grep", "-n", "--no-color",
         '<idno type="ddb-hybrid">', "HEAD", "--", "DDB_EpiDoc_XML/"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


def clone_or_reuse(source: str | None, clone_dir: Path) -> Path:
    """Return a usable idp.data clone: reuse ``source`` if it points at one, else do a
    packfile-only shallow clone into ``clone_dir``."""
    if source:
        repo = Path(source)
        if not (repo / ".git").exists() and not (repo / "DDB_EpiDoc_XML").exists():
            raise SystemExit(f"{source!r} is not an idp.data clone")
        return repo
    if (clone_dir / ".git").exists():
        print(f"reusing existing clone at {clone_dir}")
        return clone_dir
    print(f"cloning {_IDP_REPO} (packfile only) into {clone_dir} ...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--no-checkout", _IDP_REPO, str(clone_dir)],
        check=True,
    )
    return clone_dir


def verify(uri_map: dict[str, str]) -> tuple[int, int, list[str]]:
    """Check the map against the REAL cached DDbDP corpus.

    For every corpus doc-id, resolve it through the map: a DIRECT lookup first
    (the corpus id is the file stem, so this is the real correspondence -- every
    id resolves here), then a trailing ``_<digits>`` base-strip as a forward-
    compatible fallback. Returns ``(resolved, total, unresolved_ids)``; the caller
    must treat any unresolved id as a defect, not paper over it. Returns
    ``(0, 0, [])`` when the corpus is not cached (nothing to verify offline)."""
    try:
        from aegean.db import stream
        from aegean.scripts.greek.ddbdp import ddbdp_db
        db = ddbdp_db()
    except Exception as exc:  # corpus not fetched / offline
        print(f"(skipping corpus verification: {exc})")
        return 0, 0, []

    resolved = 0
    total = 0
    direct = 0
    unresolved: list[str] = []
    for doc in stream(db):
        total += 1
        if doc.id in uri_map:
            resolved += 1
            direct += 1
            continue
        base = _N_SUFFIX_RE.sub("", doc.id)
        if base != doc.id and base in uri_map:
            resolved += 1
            continue
        unresolved.append(doc.id)
    print(f"corpus ids: {total}; resolved: {resolved} (direct: {direct}); "
          f"unresolved: {len(unresolved)}")
    if unresolved:
        print("UNRESOLVED (first 50):", unresolved[:50], file=sys.stderr)
    return resolved, total, unresolved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", nargs="?", help="path to an existing papyri/idp.data clone")
    ap.add_argument("-o", "--output", default="ddbdp-uris.json.gz")
    ap.add_argument("--clone-dir", default="", help="where to clone when no source is given")
    ap.add_argument("--no-verify", action="store_true", help="skip the corpus cross-check")
    args = ap.parse_args()

    clone_dir = Path(args.clone_dir) if args.clone_dir else Path(tempfile.gettempdir()) / "idp.data"
    repo = clone_or_reuse(args.source, clone_dir)

    grep_text = _git_grep_hybrids(repo)
    uri_map = harvest_map(grep_text)
    print(f"harvested {len(uri_map)} stem->hybrid entries")

    out = Path(args.output)
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(dict(sorted(uri_map.items())), f, ensure_ascii=False)
    print(f"wrote {out} ({out.stat().st_size} bytes gzip)")

    if not args.no_verify:
        _resolved, total, unresolved = verify(uri_map)
        if total and unresolved:
            print(f"FAILED: {len(unresolved)} corpus ids do not resolve", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    raise SystemExit(main())
