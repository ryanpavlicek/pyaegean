"""Sign/word co-occurrence graph export (GEXF 1.3 / GraphML). Pure stdlib — no extras."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from aegean.analysis.graph import (
    Graph,
    GraphEdge,
    GraphNode,
    cooccurrence_graph,
    to_gexf,
    to_graphml,
)
from aegean.core.model import Document, DocumentMeta, Token, TokenKind

GEXF_NS = "http://gexf.net/1.3"
GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _doc(doc_id: str, words: list[str], lines: list[list[int]] | None = None) -> Document:
    tokens = [
        Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)
    ]
    if lines is None:
        lines = [list(range(len(tokens)))] if tokens else []
    return Document(id=doc_id, script_id="lineara", tokens=tokens, lines=lines,
                    meta=DocumentMeta())


# A corpus whose co-occurrence graph is fully hand-computable:
#   D1: ku-ro pa-i-to   D2: ku-ro pa-i-to   D3: ku-ro di-na
HAND = [
    _doc("D1", ["ku-ro", "pa-i-to"]),
    _doc("D2", ["ku-ro", "pa-i-to"]),
    _doc("D3", ["ku-ro", "di-na"]),
]


# ── building ──────────────────────────────────────────────────────────────────


def test_word_document_graph_exact_nodes_edges_weights():
    g = cooccurrence_graph(HAND, level="word", scope="document", min_count=1)
    # freq: ku-ro in 3 docs, pa-i-to in 2, di-na in 1; nodes sorted by -freq then id
    assert [(n.id, n.frequency) for n in g.nodes] == [
        ("ku-ro", 3), ("pa-i-to", 2), ("di-na", 1)
    ]
    # ku-ro+pa-i-to share D1,D2 => 2; ku-ro+di-na share D3 => 1; edges sorted -weight,src,tgt
    assert [(e.source, e.target, e.weight) for e in g.edges] == [
        ("ku-ro", "pa-i-to", 2), ("di-na", "ku-ro", 1)
    ]
    assert g.level == "word" and g.scope == "document"


def test_min_count_filters_edges_and_prunes_isolated_nodes():
    g = cooccurrence_graph(HAND, level="word", min_count=2)
    assert [(e.source, e.target, e.weight) for e in g.edges] == [("ku-ro", "pa-i-to", 2)]
    # di-na only co-occurred at weight 1, so it and its endpoint drop out
    assert {n.id for n in g.nodes} == {"ku-ro", "pa-i-to"}


def test_sign_level_counts_decomposed_signs():
    g = cooccurrence_graph(HAND, level="sign", scope="document", min_count=1)
    freq = {n.id: n.frequency for n in g.nodes}
    # ku,ro appear once per doc (3 docs); pa,i,to twice; di,na once
    assert freq["ku"] == 3 and freq["ro"] == 3
    assert freq["pa"] == 2 and freq["i"] == 2 and freq["to"] == 2
    weights = {(e.source, e.target): e.weight for e in g.edges}
    assert weights[("ku", "ro")] == 3  # every doc has ku-ro
    assert weights[("i", "pa")] == 2   # only D1, D2
    assert weights[("di", "na")] == 1  # only D3


def test_line_scope_is_tighter_than_document_scope():
    # one document, two lines: a-b|c-d on line 1, c-d|e-f on line 2
    doc = _doc("L", ["a-b", "c-d", "c-d", "e-f"], lines=[[0, 1], [2, 3]])
    line_g = cooccurrence_graph([doc], level="word", scope="line", min_count=1)
    doc_g = cooccurrence_graph([doc], level="word", scope="document", min_count=1)
    line_pairs = {(e.source, e.target) for e in line_g.edges}
    doc_pairs = {(e.source, e.target) for e in doc_g.edges}
    assert line_pairs == {("a-b", "c-d"), ("c-d", "e-f")}
    # a-b and e-f share the document but never a line
    assert ("a-b", "e-f") in doc_pairs
    assert ("a-b", "e-f") not in line_pairs


def test_empty_corpus_is_a_valid_empty_graph():
    g = cooccurrence_graph([], level="sign")
    assert g.nodes == () and g.edges == () and len(g) == 0
    solo = cooccurrence_graph([_doc("S", ["lonely"])], level="word")
    assert solo.nodes == () and solo.edges == ()  # nothing co-occurs


def test_builder_validates_arguments():
    with pytest.raises(ValueError, match="level"):
        cooccurrence_graph(HAND, level="glyph")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="scope"):
        cooccurrence_graph(HAND, scope="tablet")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="min_count"):
        cooccurrence_graph(HAND, min_count=0)
    with pytest.raises(TypeError, match="corpus or documents"):
        cooccurrence_graph(["not", "a", "doc"])


# ── GEXF export ───────────────────────────────────────────────────────────────


def test_gexf_reparses_namespace_correct(tmp_path):
    g = cooccurrence_graph(HAND, level="word", min_count=1)
    path = to_gexf(g, tmp_path / "g.gexf")
    root = ET.parse(path).getroot()
    assert root.tag == f"{{{GEXF_NS}}}gexf"
    assert root.get("version") == "1.3"
    assert root.get(f"{{{XSI}}}schemaLocation", "").startswith(GEXF_NS)
    # node label + frequency attvalue round-trip
    nodes = root.findall(f".//{{{GEXF_NS}}}node")
    labels = {n.get("label") for n in nodes}
    assert labels == {"ku-ro", "pa-i-to", "di-na"}
    freq_decl = root.find(f".//{{{GEXF_NS}}}attribute")
    assert freq_decl is not None and freq_decl.get("title") == "frequency"
    ku = next(n for n in nodes if n.get("label") == "ku-ro")
    av = ku.find(f"{{{GEXF_NS}}}attvalues/{{{GEXF_NS}}}attvalue")
    assert av is not None and av.get("value") == "3"
    # edge weights
    weights = sorted(int(e.get("weight")) for e in root.findall(f".//{{{GEXF_NS}}}edge"))
    assert weights == [1, 2]


def test_graphml_reparses_namespace_correct(tmp_path):
    g = cooccurrence_graph(HAND, level="word", min_count=1)
    path = to_graphml(g, tmp_path / "g.graphml")
    root = ET.parse(path).getroot()
    assert root.tag == f"{{{GRAPHML_NS}}}graphml"
    assert root.get(f"{{{XSI}}}schemaLocation", "").startswith(GRAPHML_NS)
    keys = {k.get("id") for k in root.findall(f"{{{GRAPHML_NS}}}key")}
    assert {"label", "frequency", "weight"} <= keys
    # node labels via <data key="label">
    labels = {
        d.text
        for d in root.findall(f".//{{{GRAPHML_NS}}}node/{{{GRAPHML_NS}}}data")
        if d.get("key") == "label"
    }
    assert labels == {"ku-ro", "pa-i-to", "di-na"}
    weights = sorted(
        int(d.text)
        for d in root.findall(f".//{{{GRAPHML_NS}}}edge/{{{GRAPHML_NS}}}data")
        if d.get("key") == "weight"
    )
    assert weights == [1, 2]


def test_empty_graph_writes_valid_documents(tmp_path):
    g = cooccurrence_graph([], level="sign")
    gexf = ET.parse(to_gexf(g, tmp_path / "e.gexf")).getroot()
    assert gexf.findall(f".//{{{GEXF_NS}}}node") == []
    assert gexf.findall(f".//{{{GEXF_NS}}}edge") == []
    graphml = ET.parse(to_graphml(g, tmp_path / "e.graphml")).getroot()
    assert graphml.findall(f".//{{{GRAPHML_NS}}}node") == []
    assert graphml.findall(f".//{{{GRAPHML_NS}}}edge") == []


def test_hostile_labels_escape_and_stay_well_formed(tmp_path):
    # quotes, angle brackets, ampersand, non-BMP unicode, and XML-invalid control chars
    hostile = _doc("H", ['a"<&\U0001076b', "b\x00c\x01", "z"])
    g = cooccurrence_graph([hostile], level="word", min_count=1)
    assert {n.id for n in g.nodes} == {'a"<&\U0001076b', "b\x00c\x01", "z"}

    for writer, ns, finder in (
        (to_gexf, GEXF_NS, lambda r: [n.get("label") for n in r.findall(f".//{{{GEXF_NS}}}node")]),
        (
            to_graphml, GRAPHML_NS,
            lambda r: [
                d.text
                for d in r.findall(f".//{{{GRAPHML_NS}}}node/{{{GRAPHML_NS}}}data")
                if d.get("key") == "label"
            ],
        ),
    ):
        path = writer(g, tmp_path / f"h.{ns[-4:]}")
        root = ET.parse(path).getroot()  # would raise if control chars leaked
        labels = set(finder(root))
        # control chars dropped ("b\x00c\x01" -> "bc"); the rest round-trips escaped
        assert labels == {'a"<&\U0001076b', "bc", "z"}


def test_writes_are_atomic_no_leftover_tmp(tmp_path):
    g = cooccurrence_graph(HAND, level="word")
    p = to_gexf(g, tmp_path / "a.gexf")
    to_graphml(g, tmp_path / "a.graphml")
    assert p.exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_writers_accept_a_prebuilt_graph_and_str_path(tmp_path):
    g = Graph(
        nodes=(GraphNode("X", 2), GraphNode("Y", 1)),
        edges=(GraphEdge("X", "Y", 4),),
        level="word", scope="document",
    )
    path = to_gexf(g, str(tmp_path / "manual.gexf"))
    root = ET.parse(path).getroot()
    assert int(root.find(f".//{{{GEXF_NS}}}edge").get("weight")) == 4
