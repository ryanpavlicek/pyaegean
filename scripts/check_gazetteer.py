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

The default run is **network**: it fetches each linked site's live Pleiades point and validates
every linked row, so newly-added rows (e.g. the Greek-epigraphy find-places) are covered
automatically. ``--offline`` instead validates the stored coordinates against the pinned points in
``scripts/gazetteer_pins.json`` (the reprPoints recorded when those rows were verified), with the
same >6 km rule and no network — this is what CI/tests run per-commit, while the network run stays
the weekly job. A linked site with no pin is reported (network-only), not failed.

Network + repo-only (never shipped in the wheel); run on demand or weekly by ``.github/workflows/assets.yml``.

    python scripts/check_gazetteer.py                  # validate every Pleiades-linked site (network)
    python scripts/check_gazetteer.py --fail-km 6 --warn-km 3
    python scripts/check_gazetteer.py --offline        # validate against pinned points, no network
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

from aegean.geo import SiteCoord, site_coordinates

_UA = "pyaegean-gazetteer-check (+https://github.com/ryanpavlicek/pyaegean)"
_TIMEOUT = 60
_PINS = Path(__file__).resolve().parent / "gazetteer_pins.json"


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


def _load_pins() -> dict[int, tuple[float, float]]:
    """Pinned ``Pleiades id -> (lat, lon)`` reprPoints from ``scripts/gazetteer_pins.json``."""
    data = json.loads(_PINS.read_text(encoding="utf-8"))
    return {int(pid): (float(lat), float(lon)) for pid, (lat, lon) in data["points"].items()}


def _run_offline(linked: list[tuple[str, SiteCoord]], fail_km: float, warn_km: float) -> int:
    """Validate stored coords against the pinned reprPoints (no network). Returns failure count."""
    pins = _load_pins()
    print(f"== offline: validating {len(linked)} Pleiades-linked find-sites against "
          f"{len(pins)} pinned points (fail > {fail_km} km) ==")
    failures = no_pin = 0
    for name, sc in linked:
        pin = pins.get(int(sc.pleiades))  # type: ignore[arg-type]
        if pin is None:
            print(f"  [skip] {name:34} Pleiades {sc.pleiades}: no pin (network-only)")
            no_pin += 1
            continue
        km = _haversine_km(sc.lat, sc.lon, pin[0], pin[1])
        tag = "FAIL" if km > fail_km else ("warn" if km > warn_km else "OK ")
        print(f"  [{tag}] {name:34} {km:6.2f} km  (Pleiades {sc.pleiades})")
        failures += km > fail_km
    if failures:
        print(f"\n{failures} pinned site(s) off by more than {fail_km} km — fix the coordinate or the pin")
        return 1
    print(f"\nOK  every pinned find-site is within {fail_km} km of its pin "
          f"({no_pin} network-only site(s) skipped offline)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--fail-km", type=float, default=6.0,
                    help="fail a site whose stored coord is more than this far from its Pleiades point")
    ap.add_argument("--warn-km", type=float, default=3.0,
                    help="flag (but don't fail) a site beyond this distance — e.g. a parent-place link")
    ap.add_argument("--offline", action="store_true",
                    help="validate against scripts/gazetteer_pins.json instead of the live Pleiades API")
    args = ap.parse_args()

    coords = site_coordinates()
    linked = sorted((name, sc) for name, sc in coords.items() if sc.pleiades)
    skipped = sum(1 for sc in coords.values() if not sc.pleiades)

    if args.offline:
        return _run_offline(linked, args.fail_km, args.warn_km)

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
