# Licensing inquiries (WP4)

Drafts for the corpus-licensing inquiries the roadmap commits to, and the place
to record each outcome — positive or negative — so the documentation can say
"we asked" rather than "we assumed". Letters are sent by the maintainer
personally; these files are working drafts.

| Inquiry | About | Status |
| --- | --- | --- |
| [DAMOS](damos.md) | License scope + machine-readable access for the Mycenaean (Linear B) corpus | **Sent 2026-06-11.** *Scouting:* content is **CC BY-NC-SA 4.0** (open — so this is access-path, not permission). DAMOS is a React SPA whose data API builds its URLs at runtime (`/just/<id>` is a client route, not a data endpoint; no `/api/*` responds; no public source repo or Zenodo deposit). The data layer is reachable only by capturing the SPA's live network calls in a browser, or by the reply naming a stable export — so the loader waits on one of those, not on permission. |
| [LiBER](liber.md) | Research-use permission for programmatic access (all rights reserved) | **Sent 2026-06-11.** *Scouting:* the tablet-list page is backed by `/_tablet_data_small` (a JSON index of ~5,638 tablets) and a `/database/api/tablet?query=` typeahead — but both are **metadata only** (site, findspot, museum, period, classification); **no transliterated text** is exposed there, and the data is **© CNR Edizioni, all rights reserved**. A gated metadata loader is therefore both thin (no corpus text) and against reserved data; the per-tablet *text* endpoint is not in the static surface. Interim path stands: a researcher's own copied selection → CSV → `Corpus.from_records` (their use; pyaegean fetches/redistributes nothing). Real integration waits on the reply. |
| SigLA | — | **License resolved without inquiry (2026-06-11):** the official site publishes "Dataset and drawings are available under the CC BY-NC-SA 4.0 license", so integration follows the PROIEL/UD fetch-to-cache pattern. *Deep scouting (same day):* the dataset ships **inside the web app** as OCaml-Marshal payloads (`database.js`; the app is js_of_ocaml); no download endpoint, API, or public source repository exists (GitHub/GitLab/Inria-GitLab searched). **Decode feasibility PROVEN (same day):** the SigLA paper documents the schema and explicitly invites reuse "outside the interface"; `scripts/explore_sigla_db.py` peels the two escape layers and verifies the Marshal streams, with document ids, sites, typology, periods, phonetic values, and per-sign GORILA position refs all recognizable. **The loader is buildable now** (Marshal reader + schema mapping, cross-validated against the bundled corpus); the courtesy contact (sent 2026-06-11) still adds value as a stability/format check, and the maintainers may prefer to publish an export. |

When an answer arrives: record the date and substance here, update
`NOTICE`/`docs/ROADMAP.md`/the wiki accordingly, and keep the correspondence
out of the repo (summaries only).
