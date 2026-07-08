"""The IGCyr Greek-inscriptions loader (offline — a synthetic corpus fixture, fetch patched).

``aegean.load("igcyr")`` fetches the project-hosted ``igcyr-corpus`` release asset (a
``Corpus.to_json`` document built from the CC BY EpiDoc corpus) and reads it back. The network
fetch is monkeypatched to a local fixture so the loader path is exercised offline.
"""

from __future__ import annotations

import aegean
import aegean.data as data
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance


def _fixture(tmp_path):
    doc = Document(
        id="gvcyr001",
        script_id="greek",
        tokens=[
            Token(text="Κοίσōνος", kind=TokenKind.WORD, line_no=0, position=0),
            Token(text="στάλα", kind=TokenKind.WORD, line_no=0, position=1),
        ],
        lines=[[0, 1]],
        meta=DocumentMeta(site="Cyrene", period="Late 3rd or 2nd century BCE", name="Epitaph of Koison"),
    )
    corpus = Corpus(
        [doc],
        provenance=Provenance(
            source="IGCyr (kingsdigitallab/igcyr), primary-Greek inscriptions",
            license="CC-BY-NC-SA-4.0 (IGCyr; Dobias-Lalou et al., Univ. di Bologna)",
            url="https://github.com/kingsdigitallab/igcyr",
        ),
        script_id="greek",
    )
    path = tmp_path / "igcyr-corpus.json"
    path.write_text(corpus.to_json(), encoding="utf-8")
    return path


def test_load_igcyr_reads_the_fetched_greek_corpus(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.load("igcyr")
    assert c.script_id == "greek"
    assert len(c.documents) == 1
    d = c.documents[0]
    assert d.id == "gvcyr001"
    assert d.meta.site == "Cyrene"  # the ancient find-place
    assert [t.text for t in d.tokens] == ["Κοίσōνος", "στάλα"]
    # the CC BY attribution travels with the corpus (never presented as unlicensed)
    assert "CC-BY-NC-SA-4.0" in c.provenance.license and "IGCyr" in c.provenance.source


def test_igcyr_resolves_through_read_corpus(tmp_path, monkeypatch):
    """The CLI/TUI corpus-spec entry (`read_corpus`) resolves the registered id, so
    `aegean info igcyr` / the corpus browser open it like any other corpus."""
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.read_corpus("igcyr")
    assert c.script_id == "greek" and len(c.documents) == 1


def test_igcyr_is_a_registered_fetchable_dataset():
    from aegean.data import _REMOTE

    spec = _REMOTE["igcyr-corpus"]
    assert "CC-BY-NC-SA-4.0" in spec.license
    assert spec.url.endswith("igcyr-corpus.json") and spec.sha256  # pinned, project-hosted
