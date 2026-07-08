# Methodology

The analysis methods ported from the Linear A Research Workbench are documented
in the workbench `docs/METHODOLOGY.md` (in ryanpavlicek/linearaworkbench), and
each port is verified against shared golden fixtures, so the two repositories
cannot silently diverge on what a method computes.
Every exploratory method (cross-linguistic distance, morphology clustering,
accounting reconciliation, AI-generated readings) carries its caveat in the
docstring and is labeled exploratory/unverified at the point of use.
