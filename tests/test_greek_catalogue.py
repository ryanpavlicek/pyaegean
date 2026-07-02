"""The bundled Greek-works discovery catalogue: greek.catalog() + `aegean greek catalog`."""

from __future__ import annotations

from aegean import greek


def test_catalogue_is_large_and_well_formed() -> None:
    works = greek.catalog()
    assert len(works) > 1500  # the full reachable canon, not the 25 curated highlights
    ids = [w["id"] for w in works]
    assert len(ids) == len(set(ids))  # unique
    for w in works:
        assert set(w) >= {"id", "author", "title", "greek_title", "source"}
        assert w["id"].startswith("tlg")
        assert w["source"] in {"perseus", "first1k"}


def test_catalogue_contains_known_works() -> None:
    by_id = {w["id"]: w for w in greek.catalog()}
    iliad = by_id["tlg0012.tlg001"]
    assert iliad["author"] == "Homer"
    assert iliad["title"] == "Iliad"
    assert iliad["greek_title"] == "Ἰλιάς"
    assert by_id["tlg0059.tlg030"]["title"] == "Republic"  # Plato


def test_filters_combine_and_are_case_insensitive() -> None:
    homer = greek.catalog(author="homer")
    assert homer and all("Homer" in w["author"] for w in homer)
    # title matches Greek or English
    assert any(w["id"] == "tlg0012.tlg001" for w in greek.catalog(title="iliad"))
    assert any(w["id"] == "tlg0012.tlg001" for w in greek.catalog(title="Ἰλιάς"))
    # free-text query spans fields (use an author actually present in the open repos)
    assert greek.catalog("herodotus")
    # source filter
    assert all(w["source"] == "first1k" for w in greek.catalog(source="first1k"))


def test_catalogue_is_offline_and_curated_subset_still_works() -> None:
    # popular_works ids are a subset of the full catalogue
    cat_ids = {w["id"] for w in greek.catalog()}
    for w in greek.popular_works():
        assert w["id"] in cat_ids


def test_cli_catalog() -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()
    r = CliRunner().invoke(app, ["greek", "catalog", "--author", "Homer"])
    assert r.exit_code == 0, r.output
    assert "Iliad" in r.output

    rj = CliRunner().invoke(app, ["greek", "catalog", "herodotus", "--json"])
    assert rj.exit_code == 0, rj.output
    assert "tlg" in rj.output


def test_cli_catalog_save(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    out = tmp_path / "homer.json"
    r = CliRunner().invoke(
        _build_app(), ["greek", "catalog", "--author", "Homer", "-o", str(out)]
    )
    assert r.exit_code == 0, r.output
    import json

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert any(w["id"] == "tlg0012.tlg001" for w in saved["works"])
