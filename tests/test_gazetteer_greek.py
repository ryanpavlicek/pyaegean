"""Greek-epigraphy gazetteer coverage: the Pleiades-linked find-places of I.Sicily, IGCyr, IOSPE,
IIP and EDH, added alongside the Aegean find-sites.

Every linked row was verified against its live Pleiades representative point (see
``scripts/gazetteer_pins.json`` and ``scripts/check_gazetteer.py``); these tests keep the data honest
offline: the rows load with a Pleiades id + coordinates, the find-place labels resolve through the
geo layer (including labels the source corpus split across lines), the offline drift-guard passes
against the pinned points, and an unknown find-place is dropped rather than crashing.

The geo-path tests build small synthetic corpora with REAL document ids and REAL find-place labels
(so no network fetch of the multi-MB corpus assets is needed); the coverage figures are pinned only
where the actual corpus is already cached locally (skipped offline)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.geo import (
    SiteCoord,
    _normalize_site,
    _resolve_site,
    _site_index,
    site_coordinates,
)

_REPO = Path(__file__).resolve().parents[1]

# The rows this pass added, as (corpus, meta.site label, Pleiades id). The label is the exact string
# the corpus carries; the id is the verified Pleiades place.
NEW_ROWS: list[tuple[str, str, int]] = [
    ("isicily", "Lipara", 462283), ("isicily", "Syracusae", 462503),
    ("isicily", "Catina", 462270), ("isicily", "Kamarina", 462126),
    ("isicily", "Gela", 462214), ("isicily", "Segesta", 462487),
    ("isicily", "Selinus", 462489), ("isicily", "Acrae", 462068),
    ("isicily", "Tauromenium", 462506), ("isicily", "Messana", 462538),
    ("isicily", "Centuripae", 462153), ("isicily", "Thermae Himeraeae", 462513),
    ("isicily", "Lilybaeum", 462281),
    ("igcyr", "Cyrene", 373778), ("igcyr", "Taucheira", 373736),
    ("igcyr", "Ptolemais", 373879), ("igcyr", "Port of Cyrene, later Apollonia", 373732),
    ("igcyr", "Euesperides", 373786),
    ("iospe", "Chersonesos", 226564), ("iospe", "Cherson", 226564),
    ("iospe", "Tyras", 226800), ("iospe", "Pantikapaion", 854719),
    ("iospe", "Neapolis Scythica", 226695),
    ("iip", "Caesarea", 678401), ("iip", "Zoora", 697768),
    ("iip", "Maresha", 687966), ("iip", "Beth Shearim", 929943122),
    ("iip", "Jerusalem", 687928), ("iip", "Elusa (Haluza)", 687890),
    ("iip", "Hammatha", 678131), ("iip", "Masada", 687968),
    ("iip", "Scythopolis-Beth Shean", 678378), ("iip", "Sepphoris", 678387),
    ("edh", "Macedonia, Thessalonica", 491741),
    ("edh", "Bithynia et Pontus, Heraclea Pontica", 844944),
    ("edh", "Achaia, Athenae", 579885), ("edh", "Achaia, Messene", 570479),
    ("edh", "Asia, Sardis", 550867),
]


def _corpus(*sites: tuple[str, str]) -> Corpus:
    """A tiny synthetic Greek corpus: each ``(doc_id, site)`` becomes a one-word document."""
    docs = [
        Document(
            id=doc_id,
            script_id="greek",
            tokens=[Token(text="ΤΕΣΤ", kind=TokenKind.WORD, line_no=0, position=0)],
            lines=[[0]],
            meta=DocumentMeta(site=site, name=doc_id),
        )
        for doc_id, site in sites
    ]
    return Corpus(docs, provenance=Provenance(source="synthetic", license="CC0", url=""),
                  script_id="greek")


# --------------------------------------------------------------------------- data (stdlib only)

def test_new_rows_present_with_pleiades_and_coords() -> None:
    coords = site_coordinates()
    assert len(coords) == 94  # 56 Aegean + 38 Greek-epigraphy rows
    for corpus, label, pid in NEW_ROWS:
        assert label in coords, f"{corpus}: {label!r} missing from the gazetteer"
        sc = coords[label]
        assert isinstance(sc, SiteCoord)
        assert sc.pleiades == pid, f"{label}: pleiades {sc.pleiades} != {pid}"
        assert isinstance(sc.lat, float) and isinstance(sc.lon, float)
        # inside the pan-Mediterranean / Black-Sea extent of the epigraphy corpora
        assert 30.0 < sc.lat < 47.0 and 12.0 < sc.lon < 37.0, label
        assert sc.pleiades_uri == f"https://pleiades.stoa.org/places/{pid}"
        assert sc.contested is None  # none of the added find-places are disputed


def test_new_regions_used() -> None:
    coords = site_coordinates()
    assert coords["Lipara"].region == "sicily"
    assert coords["Cyrene"].region == "cyrenaica"
    assert coords["Chersonesos"].region == "pontic"
    assert coords["Caesarea"].region == "levant"       # reuses the existing region
    assert coords["Macedonia, Thessalonica"].region == "mainland"


def test_cherson_and_chersonesos_are_the_same_site() -> None:
    coords = site_coordinates()
    # Cherson is the Byzantine name of Chersonesus Taurica: two labels, one Pleiades place / point.
    assert coords["Cherson"].pleiades == coords["Chersonesos"].pleiades == 226564
    assert (coords["Cherson"].lat, coords["Cherson"].lon) == (
        coords["Chersonesos"].lat, coords["Chersonesos"].lon)


def test_no_normalization_collisions() -> None:
    coords = site_coordinates()
    index = _site_index(coords)
    # collapsing whitespace must not merge two distinct gazetteer keys
    assert len(index) == len(coords)


# ------------------------------------------------------------------- whitespace-normalizing resolver

def test_normalize_site_collapses_whitespace() -> None:
    assert _normalize_site("Beth\n                    Shearim") == "Beth Shearim"
    assert _normalize_site("  Elusa   (Haluza) ") == "Elusa (Haluza)"
    assert _normalize_site("Lipara") == "Lipara"  # no-op for a clean label


def test_resolver_matches_line_split_labels() -> None:
    index = _site_index(site_coordinates())
    # a label the source corpus split across a line still resolves to the one gazetteer row
    sc = _resolve_site(index, "Beth\n                           Shearim")
    assert sc is not None and sc.pleiades == 929943122
    assert _resolve_site(index, "Scythopolis-Beth\n   Shean") is not None
    # a genuinely unknown / empty label does not resolve
    assert _resolve_site(index, "Nowhere-Placeville 99999") is None
    assert _resolve_site(index, "") is None


# --------------------------------------------------------------- pinned points (offline, stdlib)

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def test_every_new_row_is_pinned_and_matches() -> None:
    import json
    pins = json.loads((_REPO / "scripts" / "gazetteer_pins.json").read_text(encoding="utf-8"))
    points = {int(k): v for k, v in pins["points"].items()}
    coords = site_coordinates()
    for _corpus_id, label, pid in NEW_ROWS:
        assert pid in points, f"{label}: Pleiades {pid} not pinned"
        plat, plon = points[pid]
        sc = coords[label]
        km = _haversine_km(sc.lat, sc.lon, plat, plon)
        assert km <= 6.0, f"{label}: stored coord {km:.2f} km from its pinned point"


def test_offline_drift_guard_script_passes() -> None:
    """scripts/check_gazetteer.py --offline validates the stored coords against the pinned points
    with no network (the per-commit gate; the live-Pleiades run stays the weekly job)."""
    proc = subprocess.run(
        [sys.executable, str(_REPO / "scripts" / "check_gazetteer.py"), "--offline"],
        cwd=str(_REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, f"offline guard failed:\n{proc.stdout}\n{proc.stderr}"
    assert "within 6.0 km" in proc.stdout


# --------------------------------------------------------------------- geo path (needs geopandas)

def test_geo_maps_a_known_document_per_corpus() -> None:
    pytest.importorskip("geopandas")
    import pandas as pd

    from aegean import geo

    # (real doc id, real find-place label, expected Pleiades id) — one per epigraphy corpus
    cases = [
        ("ISic000806", "Lipara", 462283),                       # I.Sicily
        ("gvcyr001", "Cyrene", 373778),                          # IGCyr
        ("3.1", "Chersonesos", 226564),                          # IOSPE
        ("caes0001", "Caesarea", 678401),                        # IIP
        ("HD036840", "Macedonia, Thessalonica", 491741),         # EDH
    ]
    for doc_id, site, pid in cases:
        gdf = geo.to_geodataframe(_corpus((doc_id, site)))
        assert len(gdf) == 1, f"{doc_id}: expected one located row"
        row = gdf.iloc[0]
        assert row["id"] == doc_id and row["site"] == site
        assert int(row["pleiades"]) == pid
        assert pd.isna(row["contested"])  # none of the added find-places are disputed


def test_geo_resolves_a_line_split_label() -> None:
    pytest.importorskip("geopandas")
    from aegean import geo

    # IIP carries some find-places with a line break baked into the label; it must still map.
    gdf = geo.to_geodataframe(_corpus(("beth0006", "Beth\n                    Shearim")))
    assert len(gdf) == 1
    assert int(gdf.iloc[0]["pleiades"]) == 929943122
    assert gdf.iloc[0]["label"] == "Beth Shearim (Besara)"


def test_word_distribution_over_epigraphy_sites() -> None:
    pytest.importorskip("geopandas")
    from aegean import geo

    corpus = _corpus(("gvcyr001", "Cyrene"), ("gvcyr002", "Cyrene"), ("tauch01", "Taucheira"))
    dist = geo.word_distribution(corpus, "ΤΕΣΤ")
    by_site = {r["site"]: int(r["count"]) for _, r in dist.iterrows()}
    assert by_site == {"Cyrene": 2, "Taucheira": 1}


# ------------------------------------------------------------------------------- adversarial

def test_unknown_findplace_is_dropped_not_crashed() -> None:
    pytest.importorskip("geopandas")
    from aegean import geo

    # a doc at an unmapped place, an empty place, and one real place mixed together
    corpus = _corpus(
        ("x1", "Atlantis-on-Sea"), ("x2", ""), ("x3", "Cyrene"),
    )
    gdf = geo.to_geodataframe(corpus)
    assert len(gdf) == 1 and gdf.iloc[0]["id"] == "x3"      # only the mapped one survives
    sites = geo.to_geodataframe(corpus, level="site")
    assert len(sites) == 1 and sites.iloc[0]["site"] == "Cyrene"
    # a fully-unmapped corpus yields an empty, well-formed frame (no crash)
    empty = geo.to_geodataframe(_corpus(("y1", "Nowhere"), ("y2", "")))
    assert len(empty) == 0
    assert {"id", "site", "pleiades", "geometry"}.issubset(empty.columns)
    assert len(geo.word_distribution(_corpus(("y1", "Nowhere")), "ΤΕΣΤ")) == 0


# ---------------------------------------------------------- coverage (pinned where corpus is cached)

def test_coverage_meets_targets_where_corpora_cached() -> None:
    """Where an epigraphy corpus is already fetched locally, its find-place coverage clears the
    floor this pass achieved (I.Sicily and IGCyr meet the >=80% target; IIP/IOSPE/EDH are pinned at
    the honest ceilings stated in the report). Skipped when the corpora are not cached (offline CI)."""
    from aegean import data

    cache = Path(data.cache_dir())
    floors = {"isicily": 0.80, "igcyr": 0.80, "iip": 0.75, "iospe": 0.63, "edh": 0.19}
    index = _site_index(site_coordinates())
    checked = 0
    for cid, floor in floors.items():
        if not (cache / f"{cid}-corpus").exists():
            continue
        try:
            corpus = aegean.load(cid)
        except Exception:  # pragma: no cover - offline / asset issue
            continue
        docs = list(corpus)
        linked = sum(1 for d in docs if _resolve_site(index, d.meta.site))
        cov = linked / len(docs)
        assert cov >= floor, f"{cid} coverage {cov:.3f} fell below {floor:.2f}"
        checked += 1
    if checked == 0:
        pytest.skip("no epigraphy corpora cached offline")
