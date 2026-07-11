"""Regression tests for two R33 fixes.

(1) ``geo.to_geodataframe(level="site")`` and ``geo.word_distribution`` collapse whitespace /
    line-split variants of one find-place into a single row keyed on the canonical gazetteer
    label, instead of emitting a duplicate row per raw ``meta.site`` spelling.
(2) ``analysis.graph.to_gexf`` writes the GEXF 1.2draft namespace that networkx's ``read_gexf``
    actually accepts (the 1.3 namespace produced a "No <graph> element" error), while GraphML
    keeps round-tripping through ``read_graphml``.

geopandas/shapely and networkx are optional, so each group importorskips its dependency.
"""

from __future__ import annotations

from collections import Counter
from xml.etree import ElementTree as ET

import pytest

import aegean
from aegean.analysis.graph import cooccurrence_graph, to_gexf, to_graphml
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.geo import _normalize_site


# --------------------------------------------------------------------------- helpers

def _geo_corpus(*rows: tuple[str, str, str]) -> Corpus:
    """Synthetic Greek corpus; each ``(doc_id, site, word)`` is a one-word document."""
    docs = [
        Document(
            id=doc_id,
            script_id="greek",
            tokens=[Token(text=word, kind=TokenKind.WORD, line_no=0, position=0)],
            lines=[[0]],
            meta=DocumentMeta(site=site, name=doc_id),
        )
        for doc_id, site, word in rows
    ]
    return Corpus(docs, provenance=Provenance(source="synthetic", license="CC0", url=""),
                  script_id="greek")


def _graph_doc(doc_id: str, words: list[str]) -> Document:
    tokens = [
        Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)
    ]
    return Document(id=doc_id, script_id="lineara", tokens=tokens,
                    lines=[list(range(len(tokens)))], meta=DocumentMeta())


# A hand-computable co-occurrence corpus (shared by the GEXF/GraphML round-trips):
#   ku-ro x3, pa-i-to x2, di-na x1; edges ku-ro–pa-i-to (2), di-na–ku-ro (1).
_GRAPH_HAND = [
    _graph_doc("D1", ["ku-ro", "pa-i-to"]),
    _graph_doc("D2", ["ku-ro", "pa-i-to"]),
    _graph_doc("D3", ["ku-ro", "di-na"]),
]


# ---------------------------------------------------- (1) whitespace-variant find-place dedup

# "Beth Shearim" is a real gazetteer row (Pleiades 929943122; display "Beth Shearim (Besara)").
# The line-split spelling normalizes to the same key and must not spawn a second row.
_SPLIT = "Beth\n                    Shearim"
_CLEAN = "Beth Shearim"


def test_normalize_collapses_the_two_beth_shearim_spellings() -> None:
    # No geopandas needed: the normalization these fixes key on is stdlib.
    assert _normalize_site(_SPLIT) == _normalize_site(_CLEAN) == "Beth Shearim"


def test_site_level_collapses_variants_and_conserves_total() -> None:
    pytest.importorskip("geopandas")
    corpus = _geo_corpus(
        ("d1", _CLEAN, "α"),
        ("d2", _SPLIT, "α"),      # same physical site, spelled with a line break
        ("d3", _CLEAN, "β"),
        ("d4", "Cyrene", "α"),    # a genuinely distinct site
    )
    sites = aegean.geo.to_geodataframe(corpus, level="site")
    insc = aegean.geo.to_geodataframe(corpus)  # inscription level, all four map

    # one row per physical site, not one per raw spelling
    assert len(sites) == 2
    # canonical gazetteer key is emitted as the 'site' value (never the line-split raw label)
    by_site = {r["site"]: r for _, r in sites.iterrows()}
    assert set(by_site) == {"Beth Shearim", "Cyrene"}
    assert int(by_site["Beth Shearim"]["inscriptions"]) == 3  # d1 + d2 + d3, variants summed
    assert int(by_site["Cyrene"]["inscriptions"]) == 1
    assert by_site["Beth Shearim"]["label"] == "Beth Shearim (Besara)"
    assert int(by_site["Beth Shearim"]["pleiades"]) == 929943122

    # no duplicate (site, geometry) pairs, and the counts sum to the mapped-inscription count
    pairs = [(r["site"], r.geometry.x, r.geometry.y) for _, r in sites.iterrows()]
    assert len(set(pairs)) == len(pairs)
    assert int(sites["inscriptions"].sum()) == len(insc) == 4


def test_word_distribution_collapses_variants_to_one_row() -> None:
    pytest.importorskip("geopandas")
    corpus = _geo_corpus(
        ("d1", _CLEAN, "εὐμ"),
        ("d2", _SPLIT, "εὐμ"),    # split spelling contributes to the same site
        ("d3", "Cyrene", "εὐμ"),
        ("d4", _CLEAN, "other"),  # not the queried word
    )
    wd = aegean.geo.word_distribution(corpus, "εὐμ")
    by_site = {r["site"]: int(r["count"]) for _, r in wd.iterrows()}
    # Beth Shearim once (count summed across both spellings), Cyrene once
    assert by_site == {"Beth Shearim": 2, "Cyrene": 1}
    row = next(r for _, r in wd.iterrows() if r["site"] == "Beth Shearim")
    assert row["label"] == "Beth Shearim (Besara)"


def test_iip_site_level_deduped_and_conserved() -> None:
    """The finding's live figures, pinned where the (asset-pinned) iip corpus is cached."""
    pytest.importorskip("geopandas")
    from aegean import data as _data
    from pathlib import Path

    if not (Path(_data.cache_dir()) / "iip-corpus").exists():
        pytest.skip("iip corpus not cached")
    c = aegean.load("iip")
    sites = aegean.geo.to_geodataframe(c, level="site")
    insc = aegean.geo.to_geodataframe(c)

    # 10 unique physical places (was 13 rows before the dedup), 1605 mapped inscriptions conserved
    assert len(sites) == 10
    assert len(set(sites["site"])) == 10
    assert int(sites["inscriptions"].sum()) == len(insc) == 1605
    pairs = [(r["site"], r.geometry.x, r.geometry.y) for _, r in sites.iterrows()]
    assert len(set(pairs)) == len(pairs)  # no duplicate geometry+site rows

    # Beth Shearim's find-place is carried two ways in iip (clean + line-split); the word
    # 'Εὐμύρι' is attested at both spellings and must resolve to ONE row summing them.
    token = _iip_beth_shearim_token(c, target_docs=14)
    wd = aegean.geo.word_distribution(c, token)
    beth = [r for _, r in wd.iterrows() if r["site"] == "Beth Shearim"]
    assert len(beth) == 1
    assert int(beth[0]["count"]) == 14
    assert int(beth[0]["pleiades"]) == 929943122


def _iip_beth_shearim_token(corpus: Corpus, *, target_docs: int) -> str:
    """The exact stored token attested in ``target_docs`` Beth Shearim documents (spanning both
    the clean and line-split spellings). Derived from the corpus so no fragile hardcoded
    polytonic literal is compared against the corpus's own Unicode composition."""
    beth = [d for d in corpus if _normalize_site(d.meta.site) == "Beth Shearim"]
    variants = {d.meta.site for d in beth}
    assert len(variants) >= 2, "expected iip to carry Beth Shearim in >1 spelling"
    by_fold: dict[str, str] = {}
    doc_counts: Counter[str] = Counter()
    for d in beth:
        seen = set()
        for t in d.words:
            by_fold.setdefault(t.text.casefold(), t.text)
            seen.add(t.text.casefold())
        doc_counts.update(seen)
    fold = next(f for f, n in doc_counts.items() if n == target_docs)
    return by_fold[fold]


# --------------------------------------------------------- (2) GEXF namespace networkx can read

def test_gexf_declares_the_networkx_readable_namespace(tmp_path) -> None:
    g = cooccurrence_graph(_GRAPH_HAND, level="word", min_count=1)
    root = ET.parse(to_gexf(g, tmp_path / "g.gexf")).getroot()
    assert root.tag == "{http://www.gexf.net/1.2draft}gexf"
    assert root.get("version") == "1.2"


def test_gexf_round_trips_through_networkx(tmp_path) -> None:
    nx = pytest.importorskip("networkx")
    g = cooccurrence_graph(_GRAPH_HAND, level="word", min_count=1)
    path = to_gexf(g, tmp_path / "g.gexf")

    read = nx.read_gexf(path)  # raised "No <graph> element" under the 1.3 namespace
    assert read.number_of_nodes() == len(g.nodes) == 3
    assert read.number_of_edges() == len(g.edges) == 2
    labels = {data.get("label") for _, data in read.nodes(data=True)}
    assert labels == {"ku-ro", "pa-i-to", "di-na"}
    weights = sorted(int(data["weight"]) for _, _, data in read.edges(data=True))
    assert weights == [1, 2]


def test_graphml_still_round_trips_through_networkx(tmp_path) -> None:
    nx = pytest.importorskip("networkx")
    g = cooccurrence_graph(_GRAPH_HAND, level="word", min_count=1)
    path = to_graphml(g, tmp_path / "g.graphml")

    read = nx.read_graphml(path)
    assert read.number_of_nodes() == 3 and read.number_of_edges() == 2
    labels = {data.get("label") for _, data in read.nodes(data=True)}
    assert labels == {"ku-ro", "pa-i-to", "di-na"}
    weights = sorted(int(data["weight"]) for _, _, data in read.edges(data=True))
    assert weights == [1, 2]
