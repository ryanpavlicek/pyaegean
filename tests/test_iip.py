"""The IIP Greek-inscriptions loader (offline — a synthetic corpus fixture, fetch patched).

``aegean.load("iip")`` fetches the project-hosted ``iip-corpus`` release asset (a
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
        id="abur0001",
        script_id="greek",
        tokens=[
            Token(text="ΜΝΗΣΘΗΤΙ", kind=TokenKind.WORD, line_no=0, position=0),
            Token(text="ΤΟΥ", kind=TokenKind.WORD, line_no=0, position=1),
        ],
        lines=[[0, 1]],
        meta=DocumentMeta(site="Bethennim", period="", name="x"),
    )
    corpus = Corpus(
        [doc],
        provenance=Provenance(
            source="IIP (Brown-University-Library/iip-texts), primary-Greek inscriptions",
            license="CC-BY-NC-4.0 (IIP; M. L. Satlow, Brown University)",
            url="https://github.com/Brown-University-Library/iip-texts",
        ),
        script_id="greek",
    )
    path = tmp_path / "iip-corpus.json"
    path.write_text(corpus.to_json(), encoding="utf-8")
    return path


def test_load_iip_reads_the_fetched_greek_corpus(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.load("iip")
    assert c.script_id == "greek"
    assert len(c.documents) == 1
    d = c.documents[0]
    assert d.id == "abur0001"
    assert d.meta.site == "Bethennim"  # the ancient find-place
    assert [t.text for t in d.tokens] == ["ΜΝΗΣΘΗΤΙ", "ΤΟΥ"]
    # the CC BY attribution travels with the corpus (never presented as unlicensed)
    assert "CC-BY-NC-4.0" in c.provenance.license and "IIP" in c.provenance.source


def test_iip_resolves_through_read_corpus(tmp_path, monkeypatch):
    """The CLI/TUI corpus-spec entry (`read_corpus`) resolves the registered id, so
    `aegean info iip` / the corpus browser open it like any other corpus."""
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.read_corpus("iip")
    assert c.script_id == "greek" and len(c.documents) == 1


def test_iip_is_a_registered_fetchable_dataset():
    from aegean.data import _REMOTE

    spec = _REMOTE["iip-corpus"]
    assert "CC-BY-NC-4.0" in spec.license
    assert spec.url.endswith("iip-corpus.json") and spec.sha256  # pinned, project-hosted
