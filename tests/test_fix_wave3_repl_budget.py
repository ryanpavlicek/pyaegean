"""Two independent defects: the REPL's inline-JSON probes and label propagation's round budget.

The REPL decides twice whether a token is a corpus — once to validate ``use``, once to decide
whether a corpus-first line names its own corpus. Both probes must agree with what
:func:`aegean.core.resolve.read_corpus` actually loads, or the shell rewrites a line to read a
corpus the user did not name. A UTF-8 BOM is the case that separates them: it decodes to a
character, it is not whitespace, and the readers accept it.

Label propagation runs rounds until no node changes label. Stopping earlier returns labels still
in flight, which reads as a community split into fragments; the round budget must follow the
graph, and a run that exhausts it must say so.
"""

from __future__ import annotations

import warnings

import pytest

from aegean.analysis.multivariate import _default_max_iters, label_propagation
from aegean.cli._repl import (
    _looks_like_corpus,
    _opens_json,
    _session_corpus_error,
    _with_session_corpus,
)
from aegean.core.corpus import _BOM, Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.resolve import read_corpus


def _tiny_corpus() -> Corpus:
    """A two-document corpus with ids that no registered corpus uses."""
    docs = [
        Document(
            id=doc_id,
            script_id="lineara",
            tokens=[Token(text=text, kind=TokenKind.WORD, line_no=1, position=0)],
            lines=[[0]],
        )
        for doc_id, text in (("WAVE3-A", "alpha"), ("WAVE3-B", "beta"))
    ]
    return Corpus(script_id="lineara", documents=docs)


class TestReplJsonProbeBom:
    """The BOM'd payload is a corpus the resolver loads, so both probes must call it one."""

    def test_resolver_loads_the_bom_payload_as_json(self) -> None:
        # The premise the probes have to agree with: this spec is a loadable corpus.
        payload = _tiny_corpus().to_json()
        assert [d.id for d in read_corpus(_BOM + payload)] == ["WAVE3-A", "WAVE3-B"]

    def test_opens_json_matches_the_resolver_on_a_bom(self) -> None:
        payload = _tiny_corpus().to_json()
        assert _opens_json(payload) is True
        assert _opens_json(_BOM + payload) is True
        assert _opens_json(_BOM + "\n  " + payload) is True
        assert _opens_json("lineara") is False
        assert _opens_json(_BOM + "lineara") is False

    def test_session_corpus_rejects_bom_json_as_unreloadable(self) -> None:
        payload = _tiny_corpus().to_json()
        plain = _session_corpus_error(payload)
        bom = _session_corpus_error(_BOM + payload)
        assert plain is not None and "re-loadable" in plain
        # The BOM must not turn "this is inline JSON" into "I have never heard of this corpus".
        assert bom == plain
        assert "unknown corpus" not in bom

    def test_looks_like_corpus_sees_bom_json(self) -> None:
        payload = _tiny_corpus().to_json()
        assert _looks_like_corpus(payload) is True
        assert _looks_like_corpus(_BOM + payload) is True


class TestReplSessionCorpusSubstitution:
    """The consequence of a missed probe: the line is rewritten onto the wrong corpus."""

    def test_bom_json_keeps_its_own_corpus_in_the_corpus_position(self) -> None:
        payload = _tiny_corpus().to_json()
        for spec in (payload, _BOM + payload):
            rewritten = _with_session_corpus(["stats", spec], "lineara")
            assert rewritten == ["stats", spec], "the line names its own corpus; nothing is injected"

    def test_the_analysed_corpus_is_the_one_the_line_named(self) -> None:
        # What the rewrite decides is which documents get analysed. Resolve the corpus the
        # rewritten line actually points at and check it is the user's, not the session default.
        payload = _tiny_corpus().to_json()
        rewritten = _with_session_corpus(["stats", _BOM + payload], "lineara")
        analysed = read_corpus(rewritten[1])
        assert [d.id for d in analysed] == ["WAVE3-A", "WAVE3-B"]
        # And it is genuinely a different corpus from the session default it could have become.
        session = read_corpus("lineara")
        assert [d.id for d in analysed] != [d.id for d in session]
        assert len(analysed) < len(session)

    def test_a_non_corpus_token_still_receives_the_session_corpus(self) -> None:
        # The injection itself must keep working; the fix narrows nothing but the JSON probe.
        assert _with_session_corpus(["stats"], "lineara") == ["stats", "lineara"]
        assert _with_session_corpus(["show", "HT13"], "lineara") == ["show", "lineara", "HT13"]
        assert _with_session_corpus(["show", "linearb", "HT13"], "lineara") == [
            "show",
            "linearb",
            "HT13",
        ]


def _path_graph(n: int) -> tuple[list[str], list[tuple[str, str, float]]]:
    """A path of ``n`` nodes: one connected community, and the structure that makes a label
    travel furthest, so it is the slowest shape for propagation to settle."""
    nodes = [f"n{i:04d}" for i in range(n)]
    return nodes, [(nodes[i], nodes[i + 1], 1.0) for i in range(n - 1)]


class TestLabelPropagationBudget:
    @pytest.mark.parametrize("n", [100, 200, 300])
    def test_a_connected_path_resolves_to_one_community(self, n: int) -> None:
        # A path is connected, so the settled labelling is a single community. A budget that
        # runs out mid-propagation reports it as several, which is a wrong answer, not a
        # coarse one.
        nodes, edges = _path_graph(n)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            got = label_propagation(nodes, edges)
        assert len(set(got.values())) == 1
        assert got == label_propagation(nodes, edges, max_iters=100_000)

    def test_an_exhausted_budget_warns_and_the_labelling_is_wrong(self) -> None:
        nodes, edges = _path_graph(200)
        with pytest.warns(UserWarning, match=r"still moving .* budget of 50 rounds"):
            cut = label_propagation(nodes, edges, max_iters=50)
        settled = label_propagation(nodes, edges, max_iters=100_000)
        # The warning is the only thing separating these two returns.
        assert len(set(cut.values())) > len(set(settled.values())) == 1

    def test_a_settled_run_is_silent(self) -> None:
        nodes, edges = _path_graph(40)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            label_propagation(nodes, edges, max_iters=100_000)

    def test_derived_budget_covers_the_documented_scale(self) -> None:
        # "A few hundred nodes" must settle without the caller naming a budget: a path needs
        # about 0.6 rounds per node, so the budget has to clear that across the range.
        for n in (100, 200, 300, 500, 632):
            assert _default_max_iters(n) >= 0.6 * n

    def test_derived_budget_regimes(self) -> None:
        assert _default_max_iters(632) == 632, "peak where the two limbs meet"
        assert _default_max_iters(633) < _default_max_iters(632), "work allowance takes over"
        assert _default_max_iters(2000) < _default_max_iters(1000), "budget falls with size"
        # Never below the floor, and never a division by zero on a degenerate graph.
        for n in (0, 1, 2, 6, 8000, 10_000, 10**6):
            assert _default_max_iters(n) >= 50

    def test_empty_and_single_node_graphs(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert label_propagation([], []) == {}
            assert label_propagation(["only"], []) == {"only": 0}

    def test_small_graph_results_are_unchanged_and_deterministic(self) -> None:
        # Two cliques joined by a weak bridge: the derived budget is the floor here, so the
        # community structure and the seeded determinism are exactly as before.
        nodes = ["a1", "a2", "a3", "b1", "b2", "b3"]
        edges: list[tuple[str, str, float]] = [
            ("a1", "a2", 5.0), ("a1", "a3", 5.0), ("a2", "a3", 5.0),
            ("b1", "b2", 5.0), ("b1", "b3", 5.0), ("b2", "b3", 5.0),
            ("a3", "b1", 1.0),
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            com = label_propagation(nodes, edges, seed=3)
        assert com["a1"] == com["a2"] == com["a3"] != com["b1"] == com["b2"] == com["b3"]
        assert com == label_propagation(nodes, edges, seed=3)
