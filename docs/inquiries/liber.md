# LiBER inquiry — DRAFT (not sent)

**To:** The LiBER team (Linear B Electronic Resources, CNR — Istituto di Scienze
del Patrimonio Culturale; the project is associated with Maurizio Del Freo and
Francesco Di Filippo) — *fill in the current contact address from the LiBER
site before sending.*

**Subject:** Research-use access to LiBER data from an open-source Python
toolkit — a permission request

---

Dear colleagues,

I maintain **pyaegean** (https://github.com/ryanpavlicek/pyaegean), an
open-source (Apache-2.0) Python toolkit for Ancient Greek and the Aegean
scripts, used by classicists and computational philologists for corpus work —
query, statistics, accounting reconciliation, citation-ready exports.

LiBER's editions are, to my knowledge, under all rights reserved, and I want to
be explicit that I am **asking permission, not assuming it**. My question: would
CNR-ISPC permit individual researchers to retrieve LiBER transliterations
**programmatically, on demand, into their own local cache**, through this
toolkit? Concretely:

- pyaegean would never bundle, re-host, mirror, or redistribute LiBER data;
- every retrieved record would carry LiBER's attribution and rights statement
  in its provenance metadata, surfaced in the citation the toolkit generates;
- access would be rate-limited and clearly identified, or follow any export
  route you prefer;
- if you set conditions (non-commercial use only, specific citation form,
  no derived datasets), the toolkit would state and enforce them as far as
  software can.

If the answer is no, pyaegean's documentation will record that plainly and
continue to support only user-supplied data. If some narrower arrangement —
for instance, a subset, or metadata only — would be acceptable, I would be glad
to implement exactly that.

Thank you for LiBER, and for considering this.

With best regards,

Ryan Pavlicek
https://github.com/ryanpavlicek/pyaegean

---

*Outcome (record here when answered):* —
