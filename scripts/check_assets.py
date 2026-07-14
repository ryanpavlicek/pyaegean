#!/usr/bin/env python3
"""Asset-integrity check: every pinned remote asset pyaegean fetches still resolves.

pyaegean's reproducibility story (``aegean.data.versions()``, ``docs/benchmarks.md``)
rests on fetch-to-cache assets that live OUTSIDE the wheel:

* **project-hosted release assets** — the sha256-pinned tarballs/JSON on the
  pyaegean / linearaworkbench GitHub releases (models, corpora, prebuilt indexes).
  These are the fragile ones: a deleted release or a re-tagged asset silently
  breaks every pinned sha256.
* **commit-pinned upstream sources** — LSJ, AGDT, PROIEL, Scaife, Abbott-Smith,
  the UD treebanks, Nestle1904, lineara.xyz. A commit hash is immutable, so the
  only rot risk is the repository being deleted or renamed; a repo-existence probe
  catches that.

This script probes both. It is repo-only (never shipped in the wheel) and is run
on a schedule by ``.github/workflows/assets.yml``; a failure means a pin needs
refreshing before the next release.

    python scripts/check_assets.py                 # fast: every pinned URL still resolves
    python scripts/check_assets.py --verify-hashes # heavy: download + sha256-check the release assets
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request

from aegean.data import _REMOTE, _resolve_url, _urlopen_verified

_UA = "pyaegean-asset-check (+https://github.com/ryanpavlicek/pyaegean)"
_TIMEOUT = 60

# Commit-pinned upstream sources (the commit hash is immutable, so we only need to
# know the repo still exists). Kept here as a flat list so the check has no private
# coupling to each backend's module constants; if an upstream moves, this fails loudly.
_UPSTREAM_REPOS: dict[str, str] = {
    "lsj source (PerseusDL/lexica)": "https://github.com/PerseusDL/lexica",
    "agdt source (PerseusDL/treebank_data)": "https://github.com/PerseusDL/treebank_data",
    "proiel-treebank": "https://github.com/proiel/proiel-treebank",
    "scaife atlas-data-prep (Middle Liddell / Cunliffe)": "https://github.com/scaife-viewer/atlas-data-prep",
    "abbott-smith source": "https://github.com/translatable-exegetical-tools/Abbott-Smith",
    "UD Ancient Greek-Perseus": "https://github.com/UniversalDependencies/UD_Ancient_Greek-Perseus",
    "UD Ancient Greek-PROIEL": "https://github.com/UniversalDependencies/UD_Ancient_Greek-PROIEL",
    "nestle1904 NT source": "https://github.com/biblicalhumanities/Nestle1904",
    "lineara.xyz source": "https://github.com/mwenge/lineara.xyz",
}


def release_assets() -> list[tuple[str, str, str]]:
    """``(name, url, sha256)`` for every pinned release asset (skips bring-your-own
    specs that have no pinned URL)."""
    out = []
    for name, spec in sorted(_REMOTE.items()):
        url = _resolve_url(spec)
        if url:
            out.append((name, url, spec.sha256))
    return out


def _resolves(url: str) -> tuple[bool, str]:
    """A ranged GET — confirm the URL resolves without downloading the whole asset."""
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Range": "bytes=0-0"}
    )
    try:
        with _urlopen_verified(req, timeout=_TIMEOUT) as r:
            return 200 <= r.status < 400, str(r.status)
    except urllib.error.HTTPError as e:
        # 206 Partial Content and 416 Range Not Satisfiable both prove the URL resolves.
        if e.code in (206, 416):
            return True, str(e.code)
        return False, f"HTTP {e.code}"
    except Exception as e:  # pragma: no cover - network
        return False, type(e).__name__


def _sha256_of_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    h = hashlib.sha256()
    with _urlopen_verified(req, timeout=_TIMEOUT) as r:
        for block in iter(lambda: r.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_urls() -> int:
    failures = 0
    print("== release assets (project-hosted; the fragile pins) ==")
    for name, url, _ in release_assets():
        ok, status = _resolves(url)
        print(f"  [{'OK ' if ok else 'FAIL'}] {name:24} {status:8} {url}")
        failures += not ok
    print("== upstream sources (commit-pinned; probing repo existence) ==")
    for label, url in _UPSTREAM_REPOS.items():
        ok, status = _resolves(url)
        print(f"  [{'OK ' if ok else 'FAIL'}] {label:48} {status:8} {url}")
        failures += not ok
    print(f"\n{failures} unreachable" if failures else "\nOK  all pinned assets resolve")
    return 1 if failures else 0


def verify_hashes() -> int:
    failures = 0
    print("== verifying release-asset sha256 (downloading; this is slow) ==")
    for name, url, sha in release_assets():
        if not sha:
            print(f"  [skip] {name:24} (no pinned sha256)")
            continue
        try:
            got = _sha256_of_url(url)
        except Exception as e:  # pragma: no cover - network
            print(f"  [FAIL] {name:24} could not download: {type(e).__name__}")
            failures += 1
            continue
        ok = got == sha
        print(f"  [{'OK ' if ok else 'FAIL'}] {name:24} {'matches' if ok else f'expected {sha[:12]}…, got {got[:12]}…'}")
        failures += not ok
    print(f"\n{failures} mismatched" if failures else "\nOK  every release asset matches its pinned sha256")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--verify-hashes", action="store_true",
        help="also download every release asset and check its sha256 (slow; gigabytes)",
    )
    args = ap.parse_args()
    rc = check_urls()
    if args.verify_hashes:
        rc |= verify_hashes()
    return rc


if __name__ == "__main__":
    sys.exit(main())
