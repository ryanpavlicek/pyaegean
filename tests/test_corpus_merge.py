"""Corpus.merge / Corpus.subset / aegean.combine, and the `aegean combine` CLI."""

from __future__ import annotations

import pytest

import aegean
from aegean.core.corpus import Corpus


def _two_disjoint():
    c = aegean.load("lineara")
    ids = [d.id for d in c]
    return c.subset(ids[:5]), c.subset(ids[5:10])


def test_subset_by_id_and_note() -> None:
    c = aegean.load("lineara")
    ids = [d.id for d in c][:4]
    s = c.subset(ids)
    assert [d.id for d in s] == ids
    assert "subset:" in c.subset(ids).cite()  # provenance note surfaces in the citation


def test_merge_disjoint() -> None:
    a, b = _two_disjoint()
    m = a.merge(b)
    assert len(m) == len(a) + len(b)
    assert [d.id for d in m] == [d.id for d in a] + [d.id for d in b]
    assert m.get([d.id for d in b][0]) is not None  # both halves are reachable


def test_merge_duplicate_ids_error_lists_collision() -> None:
    a, _ = _two_disjoint()
    with pytest.raises(ValueError) as exc:
        a.merge(a)  # every id collides
    assert "duplicate document ids" in str(exc.value)


def test_merge_dedupe_first_last_suffix() -> None:
    a, _ = _two_disjoint()
    assert len(a.merge(a, dedupe="first")) == len(a)
    assert len(a.merge(a, dedupe="last")) == len(a)
    suff = a.merge(a, dedupe="suffix")
    assert len(suff) == 2 * len(a)
    assert any(d.id.endswith("#2") for d in suff)


def test_merge_mixed_script_round_trips(tmp_path) -> None:
    la = aegean.load("lineara")
    gk = aegean.load("greek")
    a = la.subset([d.id for d in la][:5])
    g = gk.subset([d.id for d in gk][:2])
    m = a.merge(g)
    assert m.script_id == "mixed"
    assert m.sign_inventory is None
    assert len(m) == 7
    assert "Merged corpus" in m.cite()
    # JSON + SQLite round-trip preserve the merged corpus
    pj = tmp_path / "m.json"
    m.to_json(pj)
    assert len(Corpus.from_json(pj)) == 7
    pdb = tmp_path / "m.db"
    m.to_sql(pdb)
    assert len(Corpus.from_sql(pdb)) == 7


def test_combine_module_function() -> None:
    a, b = _two_disjoint()
    assert [d.id for d in aegean.combine([a])] == [d.id for d in a]
    assert len(aegean.combine([a, b])) == len(a) + len(b)
    with pytest.raises(ValueError):
        aegean.combine([])


def test_merge_fingerprint_deterministic() -> None:
    a, b = _two_disjoint()
    assert a.merge(b).fingerprint() == a.merge(b).fingerprint()


def test_corpus_collapses_duplicate_ids() -> None:
    import warnings

    c = aegean.load("lineara")
    d0, d1 = c.documents[0], c.documents[1]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        dup = Corpus([d0, d0, d1])
    assert len(dup) == 2  # the duplicate collapsed — .documents and len() now agree with .get()
    assert [d.id for d in dup.documents] == [d0.id, d1.id]
    assert dup.get(d0.id) is d0
    assert any("duplicate document id" in str(x.message) for x in w)


def test_corpus_unique_ids_no_warning() -> None:
    import warnings

    c = aegean.load("lineara")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Corpus(c.documents[:5])
    assert not w  # the normal case never warns


def test_cli_combine(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    a, b = _two_disjoint()
    pa, pb, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "out.db"
    a.to_json(pa)
    b.to_json(pb)
    r = CliRunner().invoke(_build_app(), ["combine", str(pa), str(pb), "-o", str(out)])
    assert r.exit_code == 0, r.output
    assert len(Corpus.from_sql(out)) == len(a) + len(b)
