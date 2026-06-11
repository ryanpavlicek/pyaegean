# Licensing inquiries (WP4)

Drafts for the corpus-licensing inquiries the roadmap commits to, and the place
to record each outcome — positive or negative — so the documentation can say
"we asked" rather than "we assumed". Letters are sent by the maintainer
personally; these files are working drafts.

| Inquiry | About | Status |
| --- | --- | --- |
| [DAMOS](damos.md) | License scope + machine-readable access for the Mycenaean (Linear B) corpus | **Sent 2026-06-11.** Awaiting reply. |
| [LiBER](liber.md) | Research-use permission for programmatic access (all rights reserved) | **Sent 2026-06-11.** *Scouting (liber.cnr.it/howto, same day):* the documented interface is the web UI only — no API, no downloadable dataset, no export formats, no licensing statement; the sole export is "copied to memory (e.g., to be pasted into an *Excel* spreadsheet)". So integration waits on the answer; meanwhile the documented interim path is a researcher's own copied selection → CSV → `Corpus.from_records` (their use, nothing fetched or redistributed by pyaegean). |
| SigLA | — | **License resolved without inquiry (2026-06-11):** the official site publishes "Dataset and drawings are available under the CC BY-NC-SA 4.0 license", so integration follows the PROIEL/UD fetch-to-cache pattern. *Deep scouting (same day):* the dataset ships **inside the web app** as OCaml-Marshal payloads (`database.js`; the app is js_of_ocaml); no download endpoint, API, or public source repository exists (GitHub/GitLab/Inria-GitLab searched). **Decode feasibility PROVEN (same day):** the SigLA paper documents the schema and explicitly invites reuse "outside the interface"; `scripts/explore_sigla_db.py` peels the two escape layers and verifies the Marshal streams, with document ids, sites, typology, periods, phonetic values, and per-sign GORILA position refs all recognizable. **The loader is buildable now** (Marshal reader + schema mapping, cross-validated against the bundled corpus); the courtesy contact (sent 2026-06-11) still adds value as a stability/format check, and the maintainers may prefer to publish an export. |

When an answer arrives: record the date and substance here, update
`NOTICE`/`docs/ROADMAP.md`/the wiki accordingly, and keep the correspondence
out of the repo (summaries only).
