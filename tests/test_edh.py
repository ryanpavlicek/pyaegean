"""The EDH Greek-inscriptions loader (offline — a synthetic corpus fixture, fetch patched).

``aegean.load("edh")`` fetches the project-hosted ``edh-corpus`` release asset (a ``Corpus.to_json``
document built from the CC BY-SA EpiDoc dump) and reads it back. The network fetch is monkeypatched
to a local fixture so the loader path is exercised offline.
"""

from __future__ import annotations

import aegean
import aegean.data as data
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance


def _fixture(tmp_path):
    doc = Document(
        id="HD043667",
        script_id="greek",
        tokens=[Token(text="Ἀπολλοδώρου.", kind=TokenKind.WORD, line_no=0, position=0)],
        lines=[[0]],
        meta=DocumentMeta(
            name="Grenzmarkierung auf Fels",
            site="Asia, Proconnesus, insula",
            findspot="Mandıra, Türkei",
            notes=("TM 176151", "Grenzmarkierung"),
        ),
    )
    corpus = Corpus(
        [doc],
        provenance=Provenance(
            source="EDH — Epigraphic Database Heidelberg, Ancient Greek inscriptions",
            license="CC-BY-SA-4.0 (Epigraphic Database Heidelberg / Heidelberg Academy of Sciences and Humanities)",
            url="https://github.com/epigraphic-database-heidelberg/data",
        ),
        script_id="greek",
    )
    path = tmp_path / "edh-corpus.json"
    path.write_text(corpus.to_json(), encoding="utf-8")
    return path


def test_load_edh_reads_the_fetched_greek_corpus(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.load("edh")
    assert c.script_id == "greek"
    assert len(c.documents) == 1
    d = c.documents[0]
    assert d.id == "HD043667"
    assert d.meta.site == "Asia, Proconnesus, insula"
    assert [t.text for t in d.tokens] == ["Ἀπολλοδώρου."]
    assert "TM 176151" in d.meta.notes  # the Trismegistos id is kept for cross-referencing
    # the CC BY-SA attribution travels with the corpus (never presented as unlicensed)
    assert "CC-BY-SA-4.0" in c.provenance.license and "Heidelberg" in c.provenance.source


def test_edh_resolves_through_read_corpus(tmp_path, monkeypatch):
    """The CLI/TUI corpus-spec entry (`read_corpus`) resolves the registered id, so
    `aegean info edh` / the corpus browser open it like any other corpus."""
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.read_corpus("edh")
    assert c.script_id == "greek" and len(c.documents) == 1


def test_edh_is_a_registered_fetchable_dataset():
    from aegean.data import _REMOTE

    spec = _REMOTE["edh-corpus"]
    assert "CC-BY-SA-4.0" in spec.license
    assert spec.url.endswith("edh-corpus.json") and spec.sha256  # pinned, project-hosted
