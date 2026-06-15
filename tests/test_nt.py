"""The Greek New Testament loader (aegean.scripts.greek.nt / greek.load_nt).

Covers the fetched full-corpus path (via a synthetic asset), book + ref selection, the
per-token annotations, the Robinson->UD UPOS mapping, the offline bundled-sample
fallback, and the DataSpec registration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import aegean
from aegean import data, greek
from aegean.core.model import TokenKind
from aegean.data import DataNotAvailableError
from aegean.scripts.greek.nt import robinson_to_upos

_ASSET = {
    "_meta": {
        "name": "Test NT", "version": 1,
        "license": "CC0-1.0 (morphology); base text public domain",
        "cite": "Nestle, E. (1904). Novum Testamentum Graece.",
        "source_url": "https://github.com/biblicalhumanities/Nestle1904",
        "source_commit": "abc123def456", "generated": "2026-01-01", "document_count": 2,
    },
    "documents": [
        {"id": "John 1", "book": "John", "chapter": 1, "name": "John 1", "tokens": [
            {"t": "Ἐν", "v": 1, "lemma": "ἐν", "morph": "PREP", "strongs": "1722", "norm": "ἐν"},
            {"t": "ἀρχῇ", "v": 1, "lemma": "ἀρχή", "morph": "N-DSF", "strongs": "746", "norm": "ἀρχῇ"},
            {"t": "ἦν", "v": 1, "lemma": "εἰμί", "morph": "V-IAI-3S", "strongs": "1510", "norm": "ἦν"},
            {"t": "λόγος,", "v": 2, "lemma": "λόγος", "morph": "N-NSM", "strongs": "3056", "norm": "λόγος"},
            {"t": "θεόν.", "v": 3, "lemma": "θεός", "morph": "N-ASM", "strongs": "2316", "norm": "θεόν"},
        ]},
        {"id": "Matt 1", "book": "Matt", "chapter": 1, "name": "Matthew 1", "tokens": [
            {"t": "Βίβλος", "v": 1, "lemma": "βίβλος", "morph": "N-NSF", "strongs": "976", "norm": "Βίβλος"},
        ]},
    ],
}


@pytest.fixture()
def fetched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the loader's fetch('nt-corpus') at a synthetic on-disk asset (no network)."""
    p = tmp_path / "nt-corpus.json"
    p.write_text(json.dumps(_ASSET, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: p if name == "nt-corpus" else None)
    return p


def test_robinson_to_upos() -> None:
    assert robinson_to_upos("N-NSF") == "NOUN"
    assert robinson_to_upos("V-AAI-3S") == "VERB"
    assert robinson_to_upos("T-ASM") == "DET"
    assert robinson_to_upos("CONJ") == "CCONJ"
    assert robinson_to_upos("PREP") == "ADP"
    assert robinson_to_upos("P-GSM") == "PRON"
    assert robinson_to_upos("N-PRI") == "PROPN"   # indeclinable proper noun
    assert robinson_to_upos("A-NUI") == "NUM"     # indeclinable numeral
    assert robinson_to_upos("COND") == "SCONJ"


def test_load_nt_book_selection(fetched: Path) -> None:
    john = greek.load_nt("John")
    assert john.script_id == "greek"
    assert [d.id for d in john.documents] == ["John 1"]
    # accepts abbreviations and full names alike
    assert [d.id for d in greek.load_nt("Jn").documents] == ["John 1"]
    assert [d.id for d in greek.load_nt("Matthew").documents] == ["Matt 1"]


def test_load_nt_whole_corpus(fetched: Path) -> None:
    whole = greek.load_nt()
    assert {d.id for d in whole.documents} == {"John 1", "Matt 1"}


def test_load_nt_ref_selection(fetched: Path) -> None:
    v1 = greek.load_nt("John", ref="1.1")
    assert {t.line_no for t in v1.documents[0].tokens} == {1}
    assert len(v1.documents[0].tokens) == 3
    rng = greek.load_nt("John", ref="1.1-1.2")
    assert {t.line_no for t in rng.documents[0].tokens} == {1, 2}
    # shorthand: bare hi verse inherits the lo chapter
    assert {t.line_no for t in greek.load_nt("John", ref="1.1-2").documents[0].tokens} == {1, 2}


def test_token_annotations(fetched: Path) -> None:
    doc = greek.load_nt("John", ref="1.1").documents[0]
    en = doc.tokens[0]
    assert en.text == "Ἐν" and en.kind is TokenKind.WORD
    a = en.annotations
    assert a["lemma"] == "ἐν" and a["morph"] == "PREP" and a["strongs"] == "1722"
    assert a["normalized"] == "ἐν" and a["upos"] == "ADP" and a["ref"] == "John.1.1"
    assert a.get("gloss")  # self-glossed from the bundled Dodson lexicon (Strong's 1722)
    assert doc.tokens[2].annotations["upos"] == "VERB"  # ἦν / V-IAI-3S


def test_to_dataframe_exposes_annotations(fetched: Path) -> None:
    pd = pytest.importorskip("pandas")
    df = greek.load_nt("John").to_dataframe(level="word")
    assert {"lemma", "strongs", "upos"} <= set(df.columns)
    row = df.loc[df["text"] == "ἦν"].iloc[0]
    assert row["lemma"] == "εἰμί" and row["upos"] == "VERB"
    assert not pd.isna(row["strongs"])


def test_ref_requires_book(fetched: Path) -> None:
    with pytest.raises(ValueError, match="requires a book"):
        greek.load_nt(ref="1.1")


def test_unknown_book_raises(fetched: Path) -> None:
    with pytest.raises(ValueError, match="unknown NT book"):
        greek.load_nt("Habakkuk")  # an OT book — not in the NT


def test_offline_bundled_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the asset unavailable, load_nt falls back to the bundled one-book sample."""
    def _offline(name: str, **k: object) -> Path:
        raise DataNotAvailableError(f"{name} unavailable (test: simulated offline)")

    monkeypatch.setattr(data, "fetch", _offline)
    c = greek.load_nt("Philemon")
    assert c.script_id == "greek" and len(c.documents) == 1
    doc = c.documents[0]
    assert doc.id == "Phlm 1" and len(doc.tokens) > 100
    assert all("lemma" in t.annotations for t in doc.tokens)
    assert any("offline sample" in n for n in c.provenance.notes)


def test_nt_spec_registered() -> None:
    spec = data._REMOTE["nt-corpus"]
    assert spec.extract is False
    assert "CC0" in spec.license
    assert spec.url.endswith("nt-corpus.json")


def test_aegean_load_nt_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def _offline(name: str, **k: object) -> Path:
        raise DataNotAvailableError("simulated offline")

    monkeypatch.setattr(data, "fetch", _offline)
    assert len(aegean.load("nt").documents) == 1  # bundled sample
