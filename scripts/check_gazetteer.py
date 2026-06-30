#!/usr/bin/env python3
"""Gazetteer-integrity check: every Pleiades-linked find-site sits near its Pleiades point.

The bundled geo gazetteer (``src/aegean/data/bundled/geo/site_coordinates.json``) hand-maintains a
coordinate for each Aegean find-site and, where the site aligns to a Pleiades place, its stable id.
A wrong coordinate (a transposed digit, a homonymous site, a copy-paste from the wrong place) silently
mislocates *where Aegean writing was physically found* on any map drawn from the gazetteer. This script
fetches each linked site's Pleiades representative point and fails when the stored coordinate has
drifted too far from it: the data analogue of the project's "correctness test, not a smoke test" rule.

It catches the class of bug found by hand in the past (Kardamoutsa was ~23 km off; Kythera, Pylos,
Zominthos, Skoteino and a mislinked Pyrgos each 8-39 km off). Sites with no Pleiades id (peak
sanctuaries, caves, the generic catch-alls) are honest nulls and are skipped, not failed.

Network + repo-only (never shipped in the wheel); run on demand or weekly by ``.github/workflows/assets.yml``.

    python scripts/check_gazetteer.py                  # validate every Pleiades-linked site
    python scripts/check_gazetteer.py --fail-km 6 --warn-km 3
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request

from aegean.geo import site_coordinates

_UA = "pyaegean-gazetteer-check (+https://github.com/ryanpavlicek/pyaegean)"
_TIMEOUT = 60


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS84 points."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _pleiades_reprpoint(pid: int) -> tuple[float, float, str]:
    """``(lat, lon, title)`` for a Pleiades place id, via its public JSON endpoint.

    Pleiades ``reprPoint`` is GeoJSON order ``[lon, lat]``."""
    url = f"https://pleiades.stoa.org/places/{pid}/json"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310 (fixed host)
        data = json.loads(r.read())
    rp = data.get("reprPoint")
    if not rp or len(rp) < 2:
        raise ValueError("place has no reprPoint")
    return float(rp[1]), float(rp[0]), str(data.get("title", ""))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--fail-km", type=float, default=6.0,
                    help="fail a site whose stored coord is more than this far from its Pleiades point")
    ap.add_argument("--warn-km", type=float, default=3.0,
                    help="flag (but don't fail) a site beyond this distance — e.g. a parent-place link")
    args = ap.parse_args()

    coords = site_coordinates()
    linked = sorted((name, sc) for name, sc in coords.items() if sc.pleiades)
    skipped = sum(1 for sc in coords.values() if not sc.pleiades)
    print(f"== validating {len(linked)} Pleiades-linked find-sites "
          f"(fail > {args.fail_km} km; {skipped} unmapped sites skipped) ==")

    failures = 0
    for name, sc in linked:
        try:
            plat, plon, title = _pleiades_reprpoint(int(sc.pleiades))  # type: ignore[arg-type]
        except Exception as e:  # pragma: no cover - network
            print(f"  [FAIL] {name:22} Pleiades {sc.pleiades}: cannot fetch ({type(e).__name__})")
            failures += 1
            continue
        km = _haversine_km(sc.lat, sc.lon, plat, plon)
        tag = "FAIL" if km > args.fail_km else ("warn" if km > args.warn_km else "OK ")
        print(f"  [{tag}] {name:22} {km:6.2f} km  (Pleiades {sc.pleiades} '{title}')")
        failures += km > args.fail_km

    if failures:
        print(f"\n{failures} site(s) off by more than {args.fail_km} km — fix the coordinate or the id")
        return 1
    print(f"\nOK  every linked find-site is within {args.fail_km} km of its Pleiades point")
    return 0


if __name__ == "__main__":
    sys.exit(main())
