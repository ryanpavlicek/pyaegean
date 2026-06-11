"""Build the DAMOS Linear B corpus asset from the public DAMOS ajax API.

DAMOS — the Database of Mycenaean at Oslo (https://damos.hf.uio.no, Aurora 2015) —
publishes the Mycenaean (Linear B) corpus under CC BY-NC-SA 4.0. Its web app reads
two endpoints, with no rate limit or auth:

  POST /ajaxgetfilter        -> {tables: [{id, value, ...}], collections: [...], ...}
                                the enumeration of every document (id + heading)
  GET  /ajaxitem/<id>/        -> {item: {...87 fields incl. `content` = the
                                transliteration...}, meta: {...}, bibliography, legends}

This script crawls every document once — politely (one request at a time, a short
delay, a descriptive User-Agent, resumable raw cache) — and writes a single compact
`damos-corpus.json` (transliterations + core metadata; no imagery). That artifact is
hosted as a pyaegean release asset and fetched on demand by aegean.load("damos"); the
CC BY-NC-SA NonCommercial + ShareAlike obligations pass through to the user, and the
corpus is never bundled in the Apache-2.0 wheel.

Usage:  py -3.12 scripts/build_damos_corpus.py [--out PATH] [--delay 0.2] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

BASE = "https://damos.hf.uio.no"
UA = "pyaegean-corpus-builder/0.8 (+https://github.com/ryanpavlicek/pyaegean)"

# The item fields worth keeping: the transliteration plus stable identifiers and
# provenance. (The full record carries 87 fields, many internal/editorial.)
LICENSE = "CC BY-NC-SA 4.0"
ATTRIBUTION = (
    "DAMOS — Database of Mycenaean at Oslo (F. Aurora, University of Oslo); "
    "https://damos.hf.uio.no"
)
CITE = (
    "Aurora, F. (2015). DAMOS (Database of Mycenaean at Oslo). Annotating a "
    "fragmentarily attested language. Procedia - Social and Behavioral Sciences, "
    "198, 21-31."
)


def _get(url: str, *, data: bytes | None = None, retries: int = 4) -> bytes:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)  # noqa: S310 (fixed host)
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
                return r.read()
        except Exception as e:  # pragma: no cover - network
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"giving up on {url}: {last}")


def enumerate_ids() -> list[int]:
    raw = _get(f"{BASE}/ajaxgetfilter", data=b"{}")
    flt = json.loads(raw)
    return sorted({t["id"] for t in flt["tables"]})


def site_of(item: dict, meta: dict, heading: str) -> str:
    site = (meta or {}).get("Site")
    if site:
        return str(site)
    # Fallback: the two-letter site code that opens every heading (KN, PY, TH, ...).
    prefix = heading.split(" ", 1)[0] if heading else ""
    return {
        "KN": "Knossos", "PY": "Pylos", "TH": "Thebes", "MY": "Mycenae",
        "TI": "Tiryns", "KH": "Khania",
    }.get(prefix, prefix or "unknown")


def to_record(payload: dict) -> dict:
    it = payload["item"]
    meta = payload.get("meta") or {}
    heading = it.get("heading") or ""
    return {
        "id": it.get("id"),
        "heading": heading,
        "heading_short": it.get("heading_short") or None,
        "site": site_of(it, meta, heading),
        "series": it.get("series") or None,
        "subseries": it.get("subseries") or None,
        "set": it.get("set") or None,
        "chronology": it.get("chronology1") or (meta.get("Chronology") if meta else None),
        "lost": bool(it.get("lost")),
        "trismegistos": str(it["trismegistos"]) if it.get("trismegistos") else None,
        "permalink": it.get("permalink1") or f"{BASE}/{it.get('id')}",
        "content": (it.get("content") or "").strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="damos-corpus.json", type=Path)
    ap.add_argument("--delay", default=0.2, type=float, help="seconds between requests (per worker)")
    ap.add_argument("--workers", default=1, type=int, help="concurrent fetchers (default 1)")
    ap.add_argument("--limit", default=0, type=int, help="crawl only the first N ids (testing)")
    ap.add_argument("--raw-dir", default=Path("damos-raw"), type=Path,
                    help="per-item raw JSON cache (makes the crawl resumable)")
    args = ap.parse_args()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    ids = enumerate_ids()
    if args.limit:
        ids = ids[: args.limit]
    print(f"enumerated {len(ids)} documents; crawling to {args.raw_dir}/ "
          f"with {args.workers} worker(s) ...", flush=True)

    progress = {"done": 0, "fetched": 0}
    lock = Lock()

    def ensure(doc_id: int) -> None:
        """Populate the per-id cache (skip if already present)."""
        cache = args.raw_dir / f"{doc_id}.json"
        if not cache.exists():
            payload = _get(f"{BASE}/ajaxitem/{doc_id}/")
            json.loads(payload)  # validate
            cache.write_bytes(payload)
            with lock:
                progress["fetched"] += 1
            time.sleep(args.delay)
        with lock:
            progress["done"] += 1
            if progress["done"] % 250 == 0:
                print(f"  {progress['done']}/{len(ids)} "
                      f"({progress['fetched']} freshly fetched)", flush=True)

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(ensure, ids))
    else:
        for doc_id in ids:
            ensure(doc_id)

    # Build records from the (now complete) cache — deterministic, single-threaded.
    records: list[dict] = []
    for doc_id in ids:
        try:
            payload = json.loads((args.raw_dir / f"{doc_id}.json").read_text(encoding="utf-8"))
            records.append(to_record(payload))
        except Exception as e:  # pragma: no cover
            print(f"  ! id {doc_id}: {e}", file=sys.stderr)

    with_text = sum(1 for r in records if r["content"])
    out = {
        "_meta": {
            "name": "DAMOS — Database of Mycenaean at Oslo",
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "cite": CITE,
            "source_url": BASE,
            "source_api": "ajaxitem / ajaxgetfilter",
            "generated": time.strftime("%Y-%m-%d"),
            "document_count": len(records),
            "documents_with_text": with_text,
            "note": (
                "Linear B transliterations and core metadata decoded from the DAMOS "
                "public web API; no imagery. Content is CC BY-NC-SA 4.0 — the "
                "NonCommercial + ShareAlike obligations pass through to the user, and "
                "the corpus is never bundled in the Apache-2.0 wheel. Transliteration "
                "conventions follow DAMOS (Latin syllabograms, *NNN ideograms, line "
                "numbers, editorial brackets)."
            ),
        },
        "documents": records,
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    size_mb = args.out.stat().st_size / 1e6
    print(f"wrote {args.out} — {len(records)} docs, {with_text} with text, {size_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
