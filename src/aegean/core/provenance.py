"""Provenance metadata that travels with every Corpus and is stamped into
exports — the structural backbone of the "single source of truth" guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a corpus came from and how to cite it."""

    source: str                      # e.g. "GORILA via mwenge/lineara.xyz"
    license: str = ""                # SPDX id or short description
    citation: str = ""               # human-readable citation
    url: str = ""
    schema_version: int = SCHEMA_VERSION
    notes: tuple[str, ...] = field(default_factory=tuple)

    def cite(self) -> str:
        """A one-line citation string for papers / logs."""
        bits = [self.citation or self.source]
        if self.url:
            bits.append(self.url)
        return " — ".join(bits)
