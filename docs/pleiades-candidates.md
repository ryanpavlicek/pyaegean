# Pleiades alignment — coverage and upstream candidates

The find-site gazetteer (`src/aegean/data/bundled/geo/site_coordinates.json`)
aligns each site to a [Pleiades](https://pleiades.stoa.org/) place id for
linked-open-data work. **40 of 56** sites are aligned; every id is **verified by
coordinate** (the Pleiades representative point is within a few km of ours and the
place description matches the site), never guessed, and re-checked weekly by
`scripts/check_gazetteer.py` so a stray coordinate cannot quietly slip in.

## Trust pass (2026-06-29)

A full validation of all 56 sites against their Pleiades representative points:

- **Corrected five drifted coordinates** — Zominthos (~7.5 km), Kythera (~8.4 km),
  Pylos (~9.4 km), and the Cyprus and Margiana island centroids — each realigned to
  the Pleiades point.
- **Aligned seven more sites** (33 → 40), each coordinate-verified:

| Site | Pleiades | Identification |
| --- | --- | --- |
| Ugarit (Ras Shamra) | [668295](https://pleiades.stoa.org/places/668295) | the Ugarit tell; Pleiades carries the Greek harbour name "Leukos Limen" |
| Sitia | [590045](https://pleiades.stoa.org/places/590045) | ancient Setaea / Eteia at modern Sitia |
| Skoteino cave | [14671932](https://pleiades.stoa.org/places/14671932) | the Skotino sacred cave (coordinate corrected ~8 km) |
| Fourni | [589657](https://pleiades.stoa.org/places/589657) | the Archanes (Acharna) cemetery — a parent-place link |
| Troullos | [589657](https://pleiades.stoa.org/places/589657) | the easternmost sector of Archanes — same parent place |
| Pyrgos | [589949](https://pleiades.stoa.org/places/589949) | Myrtos-Pyrgos (the Linear A "PYR" find-spot; a 39 km mislocation corrected) |
| Poros Herakleion | [589802](https://pleiades.stoa.org/places/589802) | Poros-Katsambas, the harbour of Knossos — a parent-place link |

An earlier pass (2026-06-11) aligned Iouktas, Arkhalokhori, Syme, Psychro,
Apodoulou, Kardamoutsa, and Tel Haror.

## Candidates to contribute upstream

These sites returned **no matching Pleiades place**: minor findspots, peak
sanctuaries, and caves that legitimately are not yet in Pleiades. They are good
candidates to **contribute upstream** (a Pleiades place submission), which both
fills our nulls and improves the shared gazetteer:

- **Crete:** Vrysinas, Kophinas, Larani, Kannia (the Minoan villa, distinct from
  nearby Gortyn), Nerokourou, Platanos, Traostalos, Trypiti, Armenoi, Papoura,
  Prassa, Selakano, Schinias, Kalo Chorafi.
- **Mainland:** Hagios Stefanos (Laconia) — a dedicated Pleiades entry could not be
  confirmed (the only homonym is a Cypriot place ~930 km away), so it is left null
  pending a manual lookup rather than a guessed id.

"Crete (unspecified)" is a region placeholder, not a place, and is intentionally
left null.

*ToposText cross-ids* are a possible future addition, but ToposText has no clean
id API, so they are out of scope here.

## Method

For each linked site, fetch its Pleiades `/places/<id>/json`, read the `reprPoint`,
and accept the link only when the point is within a few km of ours **and** the
title/description matches the site; `scripts/check_gazetteer.py` automates exactly
this check (fail > 6 km) on a weekly schedule. For an unaligned site, search Pleiades
(`/search_rss?portal_type=Place`) and apply the same verification before adding an id.
