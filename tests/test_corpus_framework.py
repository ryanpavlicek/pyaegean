"""Corpus framework: data versioning, Corpus.from_records, variant readings."""

from __future__ import annotations

import json

import pytest

import aegean
from aegean import data
from aegean.core.corpus import Corpus, register_loader
from aegean.core.model import ReadingStatus, Token, TokenKind
from aegean.core.provenance import Provenance


# ── streaming views ──────────────────────────────────────────────────────────
def test_iterators_are_lazy_and_consistent():
    from collections import Counter
    from collections.abc import Iterator

    corpus = aegean.load("lineara")
    assert isinstance(corpus.iter_tokens(), Iterator)
    assert isinstance(corpus.iter_words(), Iterator)

    # iter_documents matches iteration / the document list
    assert [d.id for d in corpus.iter_documents()] == [d.id for d in corpus]

    # iter_tokens streams every token across documents, in order
    assert sum(1 for _ in corpus.iter_tokens()) == sum(len(d.tokens) for d in corpus)

    # iter_words is the unit word_frequencies counts — same multiset
    assert Counter(corpus.iter_words()) == Counter(dict(corpus.word_frequencies()))
    assert sum(1 for _ in corpus.iter_words()) == sum(len(d.words) for d in corpus)


def test_iterators_do_not_materialize_a_list():
    # a generator is consumed once; a second pass over the same object is empty
    corpus = aegean.load("linearb")
    it = corpus.iter_tokens()
    first = list(it)
    assert first and list(it) == []  # exhausted — it was lazy, not a list


# ── data versioning ──────────────────────────────────────────────────────────
def test_versions_manifest_shape():
    manifest = data.versions()
    assert manifest["package"] == aegean.__version__
    assert "lineara/inscriptions.json" in manifest["bundled"]
    for info in manifest["bundled"].values():
        assert len(info["sha256"]) == 64 and info["bytes"] > 0
    assert "grc-joint" in manifest["fetched"]
    assert manifest["fetched"]["grc-joint"]["sha256"]  # pinned
    assert isinstance(manifest["fetched"]["grc-joint"]["cached"], bool)


def test_versions_manifest_is_stable_and_json_serializable():
    a, b = data.versions(), data.versions()
    assert a == b  # deterministic for a given install
    json.dumps(a)  # pinnable for papers


def test_bundled_corpora_carry_the_data_version():
    for script in ("lineara", "linearb", "cypriot", "cyprominoan", "greek"):
        prov = aegean.load(script).provenance
        assert prov is not None and prov.data_version == aegean.__version__


def test_data_version_survives_the_json_roundtrip():
    c = aegean.load("cypriot")
    again = Corpus.from_dict(json.loads(c.to_json()))
    assert again.provenance.data_version == aegean.__version__


# ── Corpus.from_records ──────────────────────────────────────────────────────
def test_from_records_minimal():
    c = Corpus.from_records(
        [
            {"id": "X1", "text": "KU-RO 10", "meta": {"site": "Somewhere"}},
            {"id": "X2", "words": ["A-DU", "SA-RA"]},
            {"id": "X3", "lines": [["TE-TU", "5"], ["KI-RO", "2"]]},
        ],
        script_id="lineara",
    )
    assert len(c) == 3
    d1 = c.get("X1")
    assert d1.meta.site == "Somewhere"
    assert [t.text for t in d1.tokens] == ["KU-RO", "10"]
    assert d1.tokens[0].kind is TokenKind.WORD and d1.tokens[0].signs == ("KU", "RO")
    assert d1.tokens[1].kind is TokenKind.NUMERAL  # inferred by parseability
    assert c.get("X3").lines == [[0, 1], [2, 3]]
    assert c.provenance is not None and "from_records" in c.provenance.source


def test_from_records_token_dicts():
    c = Corpus.from_records(
        [{"id": "Y1", "lines": [[
            {"text": "KU-RO", "status": "unclear", "alt": ["KI-RO"]},
            {"text": "10", "kind": "numeral"},
        ]]}],
    )
    tok = c.get("Y1").tokens[0]
    assert tok.status is ReadingStatus.UNCLEAR and tok.alt == ("KI-RO",)
    assert c.get("Y1").tokens[1].kind is TokenKind.NUMERAL


def test_from_records_full_api_works():
    c = Corpus.from_records(
        [{"id": f"Z{i}", "text": "KU-RO 1", "meta": {"site": "A" if i < 2 else "B"}}
         for i in range(4)],
        provenance=Provenance(source="My dig notebook", citation="Me (2026). Notes."),
    )
    assert len(c.filter(site="A")) == 2
    assert c.word_frequencies()[0] == ("KU-RO", 4)
    assert "My dig notebook" in c.cite() or "Me (2026)" in c.cite()
    again = Corpus.from_dict(json.loads(c.to_json()))  # lossless round-trip
    assert [d.id for d in again] == [d.id for d in c]


def test_from_records_validation():
    with pytest.raises(ValueError, match="missing 'id'"):
        Corpus.from_records([{"text": "A"}])
    with pytest.raises(ValueError, match="needs 'lines'"):
        Corpus.from_records([{"id": "X"}])


def test_register_loader_recipe():
    c = Corpus.from_records([{"id": "R1", "text": "A-DU"}], script_id="myfind")
    register_loader("myfind-test", lambda: c)
    # load returns an independent copy (mutation isolation), not the loader's own instance
    loaded = aegean.load("myfind-test")
    assert loaded is not c
    assert loaded.fingerprint() == c.fingerprint()
    assert [d.id for d in loaded] == [d.id for d in c]


# ── variant readings ─────────────────────────────────────────────────────────
def test_token_alt_json_roundtrip():
    tok = Token("KU-RO", TokenKind.WORD, alt=("KI-RO", "KU-RA"))
    c = Corpus.from_records(
        [{"id": "V1", "lines": [[{"text": tok.text, "alt": list(tok.alt)}]]}]
    )
    again = Corpus.from_dict(json.loads(c.to_json()))
    assert again.get("V1").tokens[0].alt == ("KI-RO", "KU-RA")


def test_token_alt_default_is_empty_and_compact():
    c = Corpus.from_records([{"id": "V2", "text": "A-DU"}])
    blob = c.to_json()
    assert '"alt"' not in blob  # omitted when empty → back-compatible JSON


def test_epidoc_roundtrip_with_variants(tmp_path):
    pytest.importorskip("lxml")
    from aegean.io import write_epidoc
    from aegean.scripts.linearb.epidoc import parse_epidoc

    c = Corpus.from_records(
        [{"id": "T1", "lines": [[
            {"text": "po-me", "alt": ["po-ma"]},
            {"text": "to-so", "status": "unclear", "alt": ["to-sa"]},
            "OVIS",
        ]]}],
        script_id="linearb",
    )
    out = tmp_path / "T1.xml"
    write_epidoc(c.get("T1"), out)
    xml = out.read_text(encoding="utf-8")
    assert "<app>" in xml and "<lem>" in xml and "<rdg>" in xml
    docs = parse_epidoc(out)
    toks = docs[0].tokens
    assert [t.text for t in toks] == ["PO-ME", "TO-SO", "OVIS"]
    assert toks[0].alt == ("PO-MA",)
    assert toks[1].alt == ("TO-SA",) and toks[1].status is ReadingStatus.UNCLEAR
    assert toks[2].alt == ()
