# Pleiades alignment — coverage and upstream candidates

The find-site gazetteer (`src/aegean/data/bundled/geo/site_coordinates.json`)
aligns each site to a [Pleiades](https://pleiades.stoa.org/) place id for
linked-open-data work. **33 of 56** sites are aligned; every id is **verified by
coordinate** (the Pleiades representative point is within a few km of ours and
the place description matches the site), never guessed — the verification caught
several false near-matches (e.g. Kannia is *not* Gortyn; Ugarit's own name search
surfaces only neighbouring places).

## Recently aligned (2026-06-11)

Seven sites gained a verified id, taking coverage from 26 to 33:

| Site | Pleiades | Identification |
| --- | --- | --- |
| Iouktas (Mt Juktas) | [589826](https://pleiades.stoa.org/places/589826) | "Gioukhtas" mountain + peak sanctuary |
| Arkhalokhori | [220781958](https://pleiades.stoa.org/places/220781958) | the Arkalochori cave sanctuary (the bronze axes) |
| Syme sanctuary | [589805](https://pleiades.stoa.org/places/589805) | Hermes & Aphrodite sanctuary, Kato Syme Viannou |
| Psychro cave | [589675](https://pleiades.stoa.org/places/589675) | Aigaion Antron (the putative Diktaean cave) |
| Apodoulou | [119143959](https://pleiades.stoa.org/places/119143959) | the Apodoulou tholos tomb |
| Kardamoutsa | [589839](https://pleiades.stoa.org/places/589839) | BAtlas 60 D2 Kardamoutsa (our coordinate corrected) |
| Tel Haror | [687907](https://pleiades.stoa.org/places/687907) | Gerar (the standard identification) |

## Candidates to contribute upstream

These sites returned **no matching Pleiades place** when searched and verified by
coordinate. Most are minor findspots, peak sanctuaries, or caves that legitimately
aren't yet in Pleiades — good candidates to **contribute upstream** (a Pleiades
place submission), which both fills our nulls and improves the shared gazetteer:

- **Crete:** Pyrgos (Myrtos Pyrgos), Vrysinas, Kophinas, Larani, Poros Herakleion,
  Kannia (the Minoan villa — distinct from nearby Gortyn), Nerokourou, Platanos,
  Sitia (ancient Eteia), Skoteino cave, Traostalos, Trypiti, Armenoi, Fourni
  (Knossos cemetery), Troullos, Papoura, Prassa, Selakano, Schinias, Kalo Chorafi.
- **Mainland:** Hagios Stefanos (Laconia).
- **Levant:** Ugarit / Ras Shamra — a major site, but its own name search did not
  surface a distinct Pleiades place; pending manual confirmation rather than a
  guessed id.

"Crete (unspecified)" is a region placeholder, not a place, and is intentionally
left null.

*ToposText cross-ids* are a possible future addition, but ToposText has no clean
id API, so they are out of scope here.

## Method

For each unaligned site: search Pleiades (`/search_rss?portal_type=Place`),
fetch each candidate's `/places/<id>/json`, and accept only a place whose
`reprPoint` is within ~5 km of ours **and** whose title/description matches the
site. This page records the verified result.
