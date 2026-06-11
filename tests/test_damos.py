"""The DAMOS Linear B loader (offline — a synthetic corpus fixture, fetch monkeypatched)."""

from __future__ import annotations

import json

import aegean
import aegean.data as data
from aegean.core.model import TokenKind


def _fixture(tmp_path):
    payload = {
        "_meta": {
            "name": "DAMOS — Database of Mycenaean at Oslo",
            "license": "CC BY-NC-SA 4.0",
            "cite": "Aurora, F. (2015). DAMOS. Procedia 198, 21-31.",
            "generated": "2026-06-11",
            "document_count": 2,
        },
        "documents": [
            {
                "id": 1,
                "heading": "KN Fp(1) 1 + 31 (138)",
                "site": "Knossos",
                "series": "F",
                "chronology": "LM IIIA2 or LM IIIB",
                "lost": False,
                "trismegistos": "952769",
                "permalink": "https://damos.hf.uio.no/1",
                "content": ".1   de-u-ki-jo-jo   'me-no'\n.2   di-we  /  OLE   S   1",
            },
            {
                "id": 2,
                "heading": "PY Ta 641",
                "site": "Pylos",
                "series": "T",
                "chronology": "LH IIIB",
                "lost": True,
                "trismegistos": None,
                "permalink": "https://damos.hf.uio.no/2",
                "content": "",  # a lost/blank tablet — still a document, no tokens
            },
        ],
    }
    p = tmp_path / "damos-corpus.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_load_damos_builds_a_corpus(tmp_path, monkeypatch):
    p = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: p if name == "damos-corpus" else None)

    corpus = aegean.load("damos")
    assert corpus.script_id == "linearb"
    assert len(corpus.documents) == 2

    kn = corpus.documents[0]
    assert kn.id == "KN Fp(1) 1 + 31 (138)"
    assert kn.meta.site == "Knossos"
    assert kn.meta.period == "LM IIIA2 or LM IIIB"
    # the transliteration is preserved verbatim
    assert "de-u-ki-jo-jo" in kn.transcription
    # two content lines → two token-lines (the .1/.2 labels are stripped)
    assert len(kn.lines) == 2

    kinds = {t.text: t.kind for t in kn.tokens}
    assert kinds["de-u-ki-jo-jo"] == TokenKind.WORD          # syllabic word
    assert kinds["me-no"] == TokenKind.WORD                  # supraliteral quotes peeled
    assert kinds["/"] == TokenKind.SEPARATOR                 # word divider
    assert kinds["OLE"] == TokenKind.LOGOGRAM                # commodity ideogram
    assert any(t.kind == TokenKind.NUMERAL for t in kn.tokens)  # the "1"

    # an empty tablet is still a document, with no tokens
    py = corpus.documents[1]
    assert py.id == "PY Ta 641" and not py.tokens

    prov = corpus.provenance
    assert "CC BY-NC-SA 4.0" in prov.license
    assert "DAMOS" in prov.source and prov.url == "https://damos.hf.uio.no"
    assert prov.data_version.startswith("damos-corpus-v1@")


def test_damos_spec_registered():
    spec = data._REMOTE["damos-corpus"]
    assert "CC BY-NC-SA 4.0" in spec.license
    assert not spec.extract
    assert spec.sha256  # pinned to the published damos-corpus-v1 asset
