"""Sign/word co-occurrence graphs, exportable to GEXF and GraphML.

A tiny, dependency-free graph builder + writers so a corpus's co-occurrence
structure can be opened in **Gephi** or loaded with **networkx** for
pattern-hunting: node = a sign (or word), edge = the two items sharing a
document (or a line), edge weight = how many documents (or lines) they share.

**Exploratory.** On the undeciphered scripts (Linear A, Cypro-Minoan) an edge is
shared *context*, not an asserted phrase, morpheme, or meaning. Treat the graph
as a lens for spotting structure to inspect, never as decipherment evidence; the
same caution applies to any small or fragmentary corpus, where a heavy edge can
be an artefact of a handful of documents.

Pure stdlib: ``import aegean`` stays instant and this module pulls in nothing
heavy. The writers serialise with :mod:`xml.etree.ElementTree` to the GEXF
1.2draft (``http://www.gexf.net/1.2draft``) and GraphML
(``http://graphml.graphdrawing.org/xmlns``) namespaces, so the output re-parses
and loads in both Gephi and networkx (``read_gexf`` / ``read_graphml``).

Access (not re-exported from ``aegean.analysis`` to keep the writers off the hot
import path)::

    from aegean.analysis.graph import cooccurrence_graph, to_gexf, to_graphml
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .._atomic import atomic_path
from ..core.model import Document, TokenKind

__all__ = [
    "GraphNode",
    "GraphEdge",
    "Graph",
    "cooccurrence_graph",
    "to_gexf",
    "to_graphml",
]

# XML 1.0 forbids most control characters; emitting them raw yields output that cannot be
# re-parsed. Mirrors ``aegean.io.epidoc._xml_clean`` — a hostile sign label (a stray NUL or
# other control char) is dropped so the serialised graph stays well-formed.
_XML_OK_WS = frozenset((0x09, 0x0A, 0x0D))  # tab, newline, carriage return


def _xml_safe(text: str) -> str:
    """Drop XML-1.0-invalid characters from a label so the serialised graph re-parses."""
    return "".join(
        c
        for c in text
        if ord(c) in _XML_OK_WS
        or 0x20 <= ord(c) <= 0xD7FF
        or 0xE000 <= ord(c) <= 0xFFFD
        or ord(c) >= 0x10000
    )


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One node: a sign or word label plus its total occurrence count in the corpus."""

    id: str
    frequency: int


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One undirected co-occurrence edge. ``source`` < ``target`` (canonical order);
    ``weight`` is the number of documents (or lines) the two items share."""

    source: str
    target: str
    weight: int


@dataclass(frozen=True, slots=True)
class Graph:
    """An undirected, weighted co-occurrence graph.

    ``nodes`` are the endpoints of the retained edges (a co-occurrence graph has no
    isolated nodes), ordered by descending frequency then label; ``edges`` are ordered
    by descending weight then endpoints. ``level`` is ``"sign"`` or ``"word"``;
    ``scope`` is ``"document"`` or ``"line"`` (what a shared unit means)."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    level: str
    scope: str

    def __len__(self) -> int:
        return len(self.nodes)


def _documents(corpus: Any) -> list[Document]:
    """Coerce a Corpus / QueryResults / iterable of Documents to a list (as the
    stats layer does), so the graph builder accepts the same inputs as ``aegean stats``."""
    docs = getattr(corpus, "documents", corpus)
    out = list(docs)
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _items(tokens: Iterable[Any], level: str) -> list[str]:
    """The countable items of a token stream — the same conventions as
    ``aegean.analysis.stats._items_of`` (and ``aegean stats`` / ``plot_sign_frequencies``):
    ``"word"`` counts WORD tokens; ``"sign"`` counts each token's decomposed signs."""
    if level == "word":
        return [t.text for t in tokens if t.kind is TokenKind.WORD]
    if level == "sign":
        out: list[str] = []
        for t in tokens:
            out.extend(t.signs or (t.text.split("-") if "-" in t.text else [t.text]))
        return out
    raise ValueError(f"level must be 'sign' or 'word', got {level!r}")


def _units(doc: Document, scope: str) -> list[list[Any]]:
    """The co-occurrence units of a document: the whole document, or each physical line."""
    if scope == "line":
        return doc.line_tokens
    if scope == "document":
        return [doc.tokens]
    raise ValueError(f"scope must be 'document' or 'line', got {scope!r}")


def cooccurrence_graph(
    corpus: Any,
    *,
    level: str = "sign",
    scope: str = "document",
    min_count: int = 1,
) -> Graph:
    """Build a co-occurrence graph from a corpus.

    ``level="sign"`` (default) makes each distinct sign a node; ``level="word"`` uses
    whole word tokens. ``scope="document"`` (default) counts two items as co-occurring
    once per document they both appear in — the same per-document counting as
    ``analysis.query.build_cooccurrence_map`` and ``viz.plot_collocation_network``;
    ``scope="line"`` counts per physical line instead (tighter adjacency, often the more
    telling scope for sign patterns). An edge's ``weight`` is that shared-unit count.

    Only edges with ``weight >= min_count`` are kept, and the nodes are exactly those
    edges' endpoints (frequency = the item's total occurrences in the corpus). A corpus
    with no qualifying co-occurrence yields a valid empty graph.

    **Exploratory** on undeciphered material — see the module docstring."""
    if min_count < 1:
        raise ValueError(f"min_count must be >= 1, got {min_count}")
    if level not in ("sign", "word"):
        raise ValueError(f"level must be 'sign' or 'word', got {level!r}")
    if scope not in ("document", "line"):
        raise ValueError(f"scope must be 'document' or 'line', got {scope!r}")

    docs = _documents(corpus)
    freq: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    for doc in docs:
        freq.update(_items(doc.tokens, level))
        for unit in _units(doc, scope):
            present = sorted(set(_items(unit, level)))
            for i, a in enumerate(present):
                for b in present[i + 1 :]:
                    pairs[(a, b)] += 1

    edges = [
        GraphEdge(a, b, n) for (a, b), n in pairs.items() if n >= min_count
    ]
    node_ids = {x for e in edges for x in (e.source, e.target)}
    nodes = [GraphNode(x, freq[x]) for x in node_ids]
    nodes.sort(key=lambda nd: (-nd.frequency, nd.id))
    edges.sort(key=lambda e: (-e.weight, e.source, e.target))
    return Graph(tuple(nodes), tuple(edges), level, scope)


# ── writers ──────────────────────────────────────────────────────────────────
#
# The namespace declarations are attached as literal attributes on the root element (rather
# than via ``ET.register_namespace``, which is process-global state). ElementTree serialises
# them verbatim, and on re-parse the unprefixed descendants land in the declared default
# namespace — so the output is a genuinely namespaced, spec-conformant document.

_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# GEXF 1.2draft: the namespace/version that networkx's ``read_gexf`` AND Gephi accept (and what
# networkx's own writer emits). The later 1.3 namespace (``http://gexf.net/1.3``) is rejected by
# networkx's reader ("No <graph> element"), so this is the interoperable choice.
_GEXF_NS = "http://www.gexf.net/1.2draft"
_GEXF_SCHEMA = "http://www.gexf.net/1.2draft http://www.gexf.net/1.2draft/gexf.xsd"

# GraphML (the canonical graphdrawing.org namespace, per the GraphML primer).
_GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
_GRAPHML_SCHEMA = (
    "http://graphml.graphdrawing.org/xmlns "
    "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
)


def _description(graph: Graph) -> str:
    return (
        f"pyaegean {graph.level} co-occurrence graph "
        f"(shared {graph.scope}; exploratory, not decipherment evidence)"
    )


def _gexf_tree(graph: Graph) -> ET.ElementTree:
    root = ET.Element("gexf")
    root.set("xmlns", _GEXF_NS)
    root.set("version", "1.2")
    root.set("xmlns:xsi", _XSI)
    root.set("xsi:schemaLocation", _GEXF_SCHEMA)

    meta = ET.SubElement(root, "meta")
    ET.SubElement(meta, "creator").text = "pyaegean"
    ET.SubElement(meta, "description").text = _description(graph)

    g = ET.SubElement(root, "graph", {"mode": "static", "defaultedgetype": "undirected"})
    attrs = ET.SubElement(g, "attributes", {"class": "node"})
    ET.SubElement(attrs, "attribute", {"id": "frequency", "title": "frequency", "type": "integer"})

    # Integer ids keep the structural graph clean regardless of the (possibly hostile)
    # labels; the label rides in the ``label`` attribute, XML-escaped and control-stripped.
    index = {nd.id: str(i) for i, nd in enumerate(graph.nodes)}
    nodes_el = ET.SubElement(g, "nodes")
    for nd in graph.nodes:
        node_el = ET.SubElement(
            nodes_el, "node", {"id": index[nd.id], "label": _xml_safe(nd.id)}
        )
        avs = ET.SubElement(node_el, "attvalues")
        ET.SubElement(avs, "attvalue", {"for": "frequency", "value": str(nd.frequency)})

    edges_el = ET.SubElement(g, "edges")
    for i, e in enumerate(graph.edges):
        ET.SubElement(
            edges_el,
            "edge",
            {
                "id": str(i),
                "source": index[e.source],
                "target": index[e.target],
                "weight": str(e.weight),
            },
        )
    return ET.ElementTree(root)


def _graphml_tree(graph: Graph) -> ET.ElementTree:
    root = ET.Element("graphml")
    root.set("xmlns", _GRAPHML_NS)
    root.set("xmlns:xsi", _XSI)
    root.set("xsi:schemaLocation", _GRAPHML_SCHEMA)

    # Attribute definitions must precede the graph element.
    ET.SubElement(
        root, "key",
        {"id": "label", "for": "node", "attr.name": "label", "attr.type": "string"},
    )
    ET.SubElement(
        root, "key",
        {"id": "frequency", "for": "node", "attr.name": "frequency", "attr.type": "long"},
    )
    ET.SubElement(
        root, "key",
        {"id": "weight", "for": "edge", "attr.name": "weight", "attr.type": "long"},
    )

    g = ET.SubElement(root, "graph", {"id": "G", "edgedefault": "undirected"})
    index = {nd.id: f"n{i}" for i, nd in enumerate(graph.nodes)}
    for nd in graph.nodes:
        node_el = ET.SubElement(g, "node", {"id": index[nd.id]})
        ET.SubElement(node_el, "data", {"key": "label"}).text = _xml_safe(nd.id)
        ET.SubElement(node_el, "data", {"key": "frequency"}).text = str(nd.frequency)
    for i, e in enumerate(graph.edges):
        edge_el = ET.SubElement(
            g, "edge",
            {"id": f"e{i}", "source": index[e.source], "target": index[e.target]},
        )
        ET.SubElement(edge_el, "data", {"key": "weight"}).text = str(e.weight)
    return ET.ElementTree(root)


def to_gexf(graph: Graph, path: str | Path) -> Path:
    """Write ``graph`` to a GEXF 1.2draft file (Gephi's native format; also read by networkx's
    ``read_gexf``). Returns the path.

    The write is atomic (temp file + replace), so a failed write never truncates an
    existing export. Node labels are XML-escaped and control-stripped, so any label
    (quotes, Unicode, stray control chars) yields a well-formed, re-parseable document."""
    with atomic_path(path) as tmp:
        _gexf_tree(graph).write(tmp, encoding="utf-8", xml_declaration=True)
    return Path(path)


def to_graphml(graph: Graph, path: str | Path) -> Path:
    """Write ``graph`` to a GraphML file (networkx ``read_graphml`` loads it). Returns
    the path. Atomic like :func:`to_gexf`, with the same label-escaping guarantee."""
    with atomic_path(path) as tmp:
        _graphml_tree(graph).write(tmp, encoding="utf-8", xml_declaration=True)
    return Path(path)
