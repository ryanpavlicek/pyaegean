"""Regression tests: append-mode provenance/inventory preservation and Greek-aware search
case folding (aegean.db), and schema-correct empty GeoDataFrames (aegean.geo)."""

from __future__ import annotations

from pathlib import Path

import pytest

import aegean
from aegean import db
from aegean.core.corpus import Corpus
from aegean.core.model import Sign, SignInventory
from aegean.core.provenance import Provenance

PROV_A = Provenance(source="Corpus A", license="CC0", citation="Corpus A (2020).")
PROV_B = Provenance(source="Corpus B", license="CC BY 4.0", citation="Corpus B (2021).")


def _corpus(items, script_id="lineara", provenance=None, sign_inventory=None) -> Corpus:
    return Corpus.from_records(
        [{"id": i, "text": t} for i, t in items],
        script_id=script_id, provenance=provenance, sign_inventory=sign_inventory,
    )


# ── db append: every corpus's provenance / license / inventory survives ──


def test_append_preserves_both_provenances(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    _corpus([("X1", "AA")], provenance=PROV_A).to_sql(p)
    _corpus([("X2", "BB")], provenance=PROV_B).to_sql(p, append=True)
    back = db.from_sqlite(p)
    assert back.provenance is not None
    # every source that went in is named, and both licenses survive
    assert "Corpus A (2020)." in back.provenance.citation
    assert "Corpus B (2021)." in back.provenance.citation
    assert "CC0" in back.provenance.license and "CC BY 4.0" in back.provenance.license
    assert any(n.startswith("appended: 2 corpora") for n in back.provenance.notes)
    cited = back.cite()
    assert "Corpus A (2020)." in cited and "Corpus B (2021)." in cited


def test_append_without_provenance_keeps_original_intact(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    _corpus([("X1", "AA")], provenance=PROV_A).to_sql(p)
    # a corpus that truly carries no provenance (from_records would synthesize one)
    bare = Corpus(_corpus([("X2", "BB")]).documents, None, None, "lineara")
    bare.to_sql(p, append=True)  # nothing new to record
    assert db.from_sqlite(p).provenance == PROV_A  # byte-for-byte, no merged wrapper


def test_reappending_same_source_does_not_duplicate(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    _corpus([("X1", "AA")], provenance=PROV_A).to_sql(p)
    _corpus([("X1", "AA BB")], provenance=PROV_A).to_sql(p, append=True)  # a correction upsert
    assert db.from_sqlite(p).provenance == PROV_A


def test_three_way_append_names_each_source_once(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    prov_c = Provenance(source="Corpus C", license="CC0", citation="Corpus C (2022).")
    _corpus([("X1", "AA")], provenance=PROV_A).to_sql(p)
    _corpus([("X2", "BB")], provenance=PROV_B).to_sql(p, append=True)
    _corpus([("X3", "CC")], provenance=prov_c).to_sql(p, append=True)
    back = db.from_sqlite(p)
    assert back.provenance is not None
    for name in ("Corpus A (2020).", "Corpus B (2021).", "Corpus C (2022)."):
        assert back.provenance.citation.count(name) == 1
    assert any(n.startswith("appended: 3 corpora") for n in back.provenance.notes)


def test_append_adopts_inventory_when_db_has_none(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    inv = SignInventory([Sign("KU", glyph="\U00010613", script_id="lineara")], "lineara")
    _corpus([("X1", "AA")]).to_sql(p)
    _corpus([("X2", "KU")], sign_inventory=inv).to_sql(p, append=True)
    back = db.from_sqlite(p)
    assert back.sign_inventory is not None
    assert [s.label for s in back.sign_inventory.signs] == ["KU"]


def test_mixed_append_clears_single_script_inventory(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    inv = SignInventory([Sign("KU", glyph="\U00010613", script_id="lineara")], "lineara")
    _corpus([("X1", "KU")], sign_inventory=inv).to_sql(p)
    _corpus([("G1", "λόγος")], script_id="greek").to_sql(p, append=True)
    back = db.from_sqlite(p)
    assert back.script_id == "mixed"
    assert back.sign_inventory is None  # the Corpus.merge rule: a mixed corpus has none


# ── db search: Greek case folding in both modes ──────────────────────────


def _greek_db(tmp_path: Path, fts: bool) -> Path:
    p = tmp_path / f"greek_{fts}.db"
    Corpus.from_records(
        [
            {"id": "G1", "text": "λόγος"},
            {"id": "G2", "text": "ΛΌΓΟΣ ἀρχή"},
            {"id": "L1", "text": "KU-RO PO-TO-KU-RO"},
        ],
    ).to_sql(p, fts=fts)
    return p


@pytest.mark.parametrize("fts", [True, False])
def test_search_token_mode_folds_greek_case(tmp_path: Path, fts: bool) -> None:
    p = _greek_db(tmp_path, fts)
    # an uppercase query finds the lowercase token and vice versa (final sigma folds too)
    for query in ("ΛΌΓΟΣ", "λόγος"):
        hits = {(d, t) for d, _pos, t in db.search(p, query)}
        assert hits == {("G1", "λόγος"), ("G2", "ΛΌΓΟΣ")}, f"fts={fts}, query={query!r}"
    # diacritics still have to match: the unaccented form is a different string
    assert db.search(p, "λογος") == []
    # ASCII behavior unchanged: exact whole-token match, either case
    assert {t for _d, _pos, t in db.search(p, "ku-ro")} == {"KU-RO"}


@pytest.mark.parametrize("fts", [True, False])
def test_search_substring_mode_folds_greek_case(tmp_path: Path, fts: bool) -> None:
    p = _greek_db(tmp_path, fts)
    hits = {t for _d, _pos, t in db.search(p, "ΌΓΟ", mode="substring")}
    assert hits == {"λόγος", "ΛΌΓΟΣ"}, f"fts={fts}"
    # ASCII behavior unchanged: a substring query still over-matches by design
    ascii_hits = {t for _d, _pos, t in db.search(p, "ku-ro", mode="substring")}
    assert ascii_hits == {"KU-RO", "PO-TO-KU-RO"}, f"fts={fts}"


def test_search_substring_respects_limit(tmp_path: Path) -> None:
    p = _greek_db(tmp_path, True)
    assert len(db.search(p, "ΌΓΟ", mode="substring", limit=1)) == 1


# ── geo: zero-match results keep the GeoDataFrame schema ─────────────────


def _unmapped_corpus() -> Corpus:
    # a corpus whose (fictional) site is not in the gazetteer: zero mappable rows
    return Corpus.from_records(
        [{"id": "X1", "text": "AA BB", "meta": {"site": "Atlantis"}}], script_id="lineara"
    )


def test_to_geodataframe_empty_corpus_keeps_schema() -> None:
    pytest.importorskip("geopandas")
    full = aegean.geo.to_geodataframe(aegean.load("lineara"))
    empty = aegean.geo.to_geodataframe(_unmapped_corpus())
    assert len(empty) == 0
    assert list(empty.columns) == list(full.columns)  # schema matches a populated result
    assert str(empty.crs).upper().endswith("4326")
    assert empty.geometry.name == "geometry"
    assert str(empty["geometry"].dtype) == "geometry"


def test_to_geodataframe_empty_site_level_keeps_schema() -> None:
    pytest.importorskip("geopandas")
    full = aegean.geo.to_geodataframe(aegean.load("lineara"), level="site")
    empty = aegean.geo.to_geodataframe(_unmapped_corpus(), level="site")
    assert len(empty) == 0
    assert list(empty.columns) == list(full.columns)
    assert str(empty.crs).upper().endswith("4326")
    assert empty.geometry.name == "geometry"


def test_word_distribution_unattested_word_keeps_schema() -> None:
    pytest.importorskip("geopandas")
    c = aegean.load("lineara")
    attested = aegean.geo.word_distribution(c, "KU-RO")
    empty = aegean.geo.word_distribution(c, "ZZZ-NOT-A-WORD")
    assert len(empty) == 0
    assert list(empty.columns) == list(attested.columns)
    assert str(empty.crs).upper().endswith("4326")
    assert empty.geometry.name == "geometry"


def test_empty_geodataframe_exports_geojson() -> None:
    # the CLI --output path writes gdf.to_json(); the empty frame must survive it
    pytest.importorskip("geopandas")
    import json

    gj = json.loads(aegean.geo.word_distribution(_unmapped_corpus(), "AA").to_json())
    assert gj["type"] == "FeatureCollection" and gj["features"] == []
