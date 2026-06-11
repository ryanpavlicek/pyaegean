# DAMOS inquiry — DRAFT (not sent)

**To:** Dr. Federico Aurora (DAMOS — Database of Mycenaean at Oslo, University of
Oslo Library) — *fill in the current contact address from the DAMOS site before
sending.*

**Subject:** DAMOS data in an open-source Python toolkit — license scope and a
recommended access path

---

Dear Dr. Aurora,

I maintain **pyaegean** (https://github.com/ryanpavlicek/pyaegean), an
open-source (Apache-2.0) Python toolkit for Ancient Greek and the Aegean
scripts used by classicists and computational philologists. It already reads
DAMOS-style EpiDoc: a researcher can point the library at their own export and
work with the tablets programmatically — query, statistics, accounting
reconciliation, dataframes, citation.

DAMOS is, as far as I can tell, the only comprehensive open digital corpus of
Mycenaean Linear B, and I would like pyaegean to support it as well — and as
respectfully — as possible. Two questions:

1. **License scope.** I understand the DAMOS data to be CC BY-NC-SA 4.0. Does
   that license cover *programmatic* retrieval of transliterations for research
   use? My toolkit would fetch data **on demand to the individual researcher's
   local cache**, clearly labeled with the license and attribution; it would
   never bundle, re-host, or redistribute the data, and the NonCommercial
   obligation would be passed through to the user. (This is the pattern I
   already use for the PROIEL treebank and the Universal Dependencies Ancient
   Greek data, which carry the same license family.)

2. **Access path.** Is there a recommended machine-readable route — a bulk
   EpiDoc export, a stable per-inscription URL scheme, or an API — that you
   would prefer tools to use? I would rather follow your preferred path than
   scrape, and I am happy to rate-limit, cache aggressively, identify the
   client, or mirror nothing at all, as you prefer.

Whatever the answer, pyaegean's documentation will state it plainly — including
"the maintainers prefer the data not be accessed programmatically", if that is
the answer. Attribution to DAMOS and to your publications already appears in
the project's NOTICE file and provenance metadata.

Thank you for DAMOS, and for your time.

With best regards,

Ryan Pavlicek
https://github.com/ryanpavlicek/pyaegean

---

*Outcome (record here when answered):* —
