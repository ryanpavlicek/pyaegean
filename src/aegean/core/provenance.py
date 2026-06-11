"""Provenance metadata that travels with every Corpus and is stamped into
exports — the structural backbone of the "single source of truth" guarantee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SCHEMA_VERSION = 1

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a corpus came from and how to cite it."""

    source: str                      # e.g. "GORILA via mwenge/lineara.xyz"
    license: str = ""                # SPDX id or short description
    citation: str = ""               # human-readable citation
    url: str = ""
    schema_version: int = SCHEMA_VERSION
    notes: tuple[str, ...] = field(default_factory=tuple)
    data_version: str = ""           # version of the dataset itself (see aegean.data.versions)

    def cite(self) -> str:
        """A one-line citation string for papers / logs."""
        bits = [self.citation or self.source]
        if self.url:
            bits.append(self.url)
        return " — ".join(bits)

    def _year(self) -> str | None:
        """The first plausible year in the citation string, if any."""
        m = _YEAR_RE.search(self.citation)
        return m.group(0) if m else None

    def bibtex(self, key: str = "aegean-corpus") -> str:
        """A BibTeX ``@misc`` entry for this source.

        Best-effort formatting of the recorded free-text provenance: only fields
        actually known are emitted; the first year found in the citation string
        (if any) becomes ``year``; the license and any provenance notes (e.g.
        the subset note `Corpus.filter` records) go into ``note``."""
        fields: list[tuple[str, str]] = [("title", self.citation or self.source)]
        year = self._year()
        if year:
            fields.append(("year", year))
        if self.url:
            fields.append(("url", self.url))
        note_bits = [f"License: {self.license}"] if self.license else []
        note_bits.extend(self.notes)
        note_bits.append("Accessed via pyaegean")
        fields.append(("note", ". ".join(note_bits)))
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
        return f"@misc{{{key},\n{body},\n}}"

    def apa(self) -> str:
        """An APA-style reference line (``n.d.`` when no year is recoverable).

        Best-effort formatting of the recorded free-text provenance; notes
        (e.g. the subset note `Corpus.filter` records) follow in brackets."""
        title = (self.citation or self.source).rstrip(" .")
        year = self._year() or "n.d."
        out = f"{title}. ({year})."
        if self.url:
            out += f" {self.url}"
        if self.notes:
            out += f" [{'; '.join(self.notes)}]"
        return out
