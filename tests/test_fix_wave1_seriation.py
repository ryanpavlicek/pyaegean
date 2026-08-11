"""seriate: the ordering survives permuting the input rows, and says so when it cannot.

``seriate`` promises an ordering that does not depend on the order the rows were supplied in,
up to the inherent reversal. Rows sharing no type at all break the similarity graph into
disconnected blocks, and a Laplacian with one zero eigenvalue per block has no single Fiedler
vector to sort by, so the promise held only for a connected graph. These tests pin the whole
contract: blocks are seriated separately and placed by a stated convention, connected inputs
keep the ordering they already had, and what the similarity genuinely leaves undetermined is
reported instead of being settled by an accident of input order.
"""

import itertools
import random
import warnings

import pytest

import aegean
from aegean.analysis.seriation import (
    _abundance_from_corpus,
    _components,
    brainerd_robinson,
    seriate,
)
from aegean.core.model import Document, DocumentMeta, Token, TokenKind

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _quiet_seriate(rows, **kwargs):
    """seriate() with the ambiguity warnings muted; the warnings have their own tests."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return seriate(rows, **kwargs)


def _content(rows, order):
    """The seriated sequence as row contents, so orderings of permuted inputs can be compared."""
    return tuple(tuple(rows[i]) for i in order)


def _reading(rows, **kwargs):
    return _content(rows, _quiet_seriate(rows, **kwargs).order)


def _shuffled_readings(rows, seeds, **kwargs):
    """The content ordering produced from each shuffle of ``rows``."""
    out = []
    for s in seeds:
        perm = list(range(len(rows)))
        random.Random(s).shuffle(perm)
        permuted = [rows[i] for i in perm]
        out.append((s, _reading(permuted, **kwargs)))
    return out


def _battleship(n, n_types, spread):
    """A planted seriation: each type's unimodal peak marches along the assemblage sequence,
    so row order 0..n-1 is the true ordering."""
    peaks = [t * (n - 1) / (n_types - 1) for t in range(n_types)]
    return [
        [max(0.0, 10.0 - spread * abs(a - peaks[t])) for t in range(n_types)] for a in range(n)
    ]


def _doc(doc_id, signs):
    tokens = [Token(text=s, kind=TokenKind.WORD, signs=(s,)) for s in signs]
    return Document(
        id=doc_id,
        script_id="toy",
        tokens=tokens,
        lines=[list(range(len(tokens)))],
        meta=DocumentMeta(),
    )


# Two pairs of assemblages with no type in common between the pairs: the similarity graph
# falls into two blocks, and the whole-matrix Fiedler vector is an arbitrary pick from a
# two-dimensional null space.
TWO_BLOCKS = [[10, 5, 0, 0], [8, 6, 0, 0], [0, 0, 10, 5], [0, 0, 8, 6]]


# --------------------------------------------------------------------------- #
# permutation invariance
# --------------------------------------------------------------------------- #


def test_disjoint_blocks_order_identically_under_every_permutation():
    readings = set()
    for perm in itertools.permutations(range(4)):
        rows = [TWO_BLOCKS[i] for i in perm]
        reading = _reading(rows)
        readings.add(min(reading, tuple(reversed(reading))))
    # One reading, not one per permutation: every arrangement of the input seriates the same.
    assert len(readings) == 1
    # And it is the compositional sequence, each block kept together.
    assert readings.pop() == (
        (0, 0, 8, 6),
        (0, 0, 10, 5),
        (8, 6, 0, 0),
        (10, 5, 0, 0),
    )


def test_disjoint_blocks_reading_is_stable_and_not_an_artefact_of_row_labels():
    base = _reading(TWO_BLOCKS)
    for _seed, reading in _shuffled_readings(TWO_BLOCKS, range(20)):
        assert reading == base or reading == tuple(reversed(base))


def test_fully_disconnected_matrix_is_invariant():
    # Six assemblages, no two sharing a type: six blocks, no similarity evidence anywhere.
    rows = [[0] * 6 for _ in range(6)]
    for i in range(6):
        rows[i][i] = i + 1
    result = _quiet_seriate(rows)
    assert len(result.components) == 6
    base = _content(rows, result.order)
    for seed, reading in _shuffled_readings(rows, range(10)):
        assert reading == base or reading == tuple(reversed(base)), seed


def test_real_linear_a_sample_is_invariant_under_twenty_shuffles():
    docs = sorted(aegean.load("lineara").documents, key=lambda d: d.id)[:60]
    matrix, _labels, _types = _abundance_from_corpus(docs)
    # The material really is disconnected: without per-block seriation this sample is the
    # arbitrary-null-space case, not a hypothetical one.
    assert len(_components(brainerd_robinson(matrix))) > 1
    base = _reading(matrix)
    for seed, reading in _shuffled_readings(matrix, range(20)):
        assert reading == base or reading == tuple(reversed(base)), seed


# --------------------------------------------------------------------------- #
# connected inputs keep the ordering they already had
# --------------------------------------------------------------------------- #


def test_connected_matrix_keeps_its_established_order():
    # A connected similarity graph has one block, so the established whole-matrix spectral
    # ordering is what runs, unchanged. These are the orderings it has always produced.
    planted = _battleship(12, 7, 2.2)
    assert _quiet_seriate(planted).order == tuple(range(12))

    rng = random.Random(3)
    dense = [[rng.randint(1, 15) for _ in range(6)] for _ in range(9)]
    result = _quiet_seriate(dense)
    assert len(result.components) == 1
    assert result.order == (6, 4, 5, 1, 3, 2, 8, 0, 7)


def test_connected_matrix_keeps_the_canonical_direction():
    result = _quiet_seriate(_battleship(8, 5, 2.2))
    assert result.order[0] < result.order[-1]


def test_connected_corpus_keeps_its_established_order():
    zakros = aegean.load("lineara").filter(site="Zakros")
    result = _quiet_seriate(zakros)
    assert len(result.components) == 1  # every Zakros tablet shares a sign with some other
    assert result.ordered_labels()[:6] == (
        "ZAWa38",
        "ZA11b",
        "ZAZb3",
        "ZA21b",
        "ZA6b",
        "ZA18a",
    )


def test_planted_order_still_recovered_from_a_shuffle():
    planted = _battleship(12, 7, 2.2)
    truth = list(range(12))
    for s in range(10):
        perm = truth[:]
        random.Random(s).shuffle(perm)
        recovered = [perm[i] for i in _quiet_seriate([planted[p] for p in perm]).order]
        assert recovered == truth or recovered == truth[::-1], s


# --------------------------------------------------------------------------- #
# components: what the result discloses about disconnection
# --------------------------------------------------------------------------- #


def test_components_partition_the_order():
    result = _quiet_seriate(TWO_BLOCKS)
    assert tuple(i for block in result.components for i in block) == result.order
    assert sorted(i for block in result.components for i in block) == [0, 1, 2, 3]
    assert [len(b) for b in result.components] == [2, 2]


def test_components_group_rows_that_share_a_type():
    # Rows 0 and 1 share type 0; row 2 shares nothing with either.
    result = _quiet_seriate([[5, 5, 0], [5, 1, 0], [0, 0, 7]])
    blocks = {frozenset(b) for b in result.components}
    assert blocks == {frozenset({0, 1}), frozenset({2})}


def test_block_test_separates_rescaling_residue_from_real_overlap():
    # Rescaling rows to percentages leaves ulps behind, so a disjoint pair scores a hair off
    # zero rather than exactly zero. That residue is not a shared type.
    disjoint = [[4, 1, 9, 0, 0], [0, 0, 0, 6, 3]]
    assert abs(brainerd_robinson(disjoint)[0][1]) < 1e-9
    assert len(_quiet_seriate(disjoint).components) == 2
    # An overlap of one occurrence in a million is real similarity, and keeps one block.
    shared = [[1_000_000, 1, 0], [0, 1, 1_000_000]]
    assert brainerd_robinson(shared)[0][1] == pytest.approx(2e-4, rel=1e-3)
    assert len(_quiet_seriate(shared).components) == 1


def test_single_row_corpus_has_one_block():
    result = _quiet_seriate(_doc("solo", ["A", "B", "A"]))
    assert result.order == (0,)
    assert result.components == ((0,),)
    assert result.ambiguous is False
    assert result.iterations == 0


# --------------------------------------------------------------------------- #
# what stays undetermined is reported, not invented
# --------------------------------------------------------------------------- #


def test_repeated_eigenvalue_is_reported():
    # A four-cycle of assemblages, each sharing one type with each neighbour: its Laplacian
    # eigenvalues are 0, 200, 200, 400, so the Fiedler eigenvalue is repeated and every vector
    # in its plane is an equally good axis.
    cycle = [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1]]
    with pytest.warns(UserWarning, match="axis undetermined for 4 of 4 rows"):
        result = seriate(cycle)
    assert result.ambiguous is True
    assert sorted(result.order) == [0, 1, 2, 3]  # still a usable permutation


def test_rows_at_one_axis_position_are_reported():
    # Rows 2 and 3 have different compositions but identical similarities to everything,
    # so the axis puts them at the same place and cannot order them.
    rows = [[1, 0, 0], [0, 1, 0], [1, 1, 1], [1, 1, 2]]
    with pytest.warns(UserWarning, match="2 of 4 rows of differing composition"):
        result = seriate(rows)
    assert result.ambiguous is True


def test_proportional_duplicates_are_not_reported_as_ambiguous():
    # One tablet with a single sign and one with three of that same sign are the same
    # assemblage to Brainerd-Robinson. They share an axis position, but arranging them is not
    # an ambiguity to report; it is settled by the counts the caller supplied.
    rows = [[3, 0], [1, 0], [1, 1]]
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning here would be noise on ordinary data
        result = seriate(rows)
    assert result.ambiguous is False
    reading = _content(rows, result.order)
    assert reading.index((1, 0)) < reading.index((3, 0))
    for seed, shuffled in _shuffled_readings(rows, range(10)):
        assert shuffled == reading or shuffled == tuple(reversed(reading)), seed


def test_ordinary_connected_data_reports_no_ambiguity():
    result = _quiet_seriate(_battleship(12, 7, 2.2))
    assert result.ambiguous is False


# --------------------------------------------------------------------------- #
# the large-block solver path (above the dense eigensolver's row limit)
# --------------------------------------------------------------------------- #


def test_large_block_recovers_the_planted_order():
    planted = _battleship(161, 60, 0.25)  # 161 rows: past the dense solver's limit
    result = _quiet_seriate(planted)
    assert result.iterations > 0
    assert result.ambiguous is False
    assert list(result.order) == list(range(161)) or list(result.order) == list(
        range(160, -1, -1)
    )


def test_large_block_is_invariant_under_shuffles():
    planted = _battleship(161, 60, 0.25)
    truth = list(range(161))
    for s in range(3):
        perm = truth[:]
        random.Random(s).shuffle(perm)
        recovered = [perm[i] for i in _quiet_seriate([planted[p] for p in perm]).order]
        assert recovered == truth or recovered == truth[::-1], s


def test_large_block_reports_an_axis_the_iteration_never_settled():
    # Stopped early the iteration still depends on its starting vector, so the ordering is
    # not one the data determines. Raising the budget settles it and the report clears.
    planted = _battleship(161, 40, 0.35)
    with pytest.warns(UserWarning, match="axis undetermined"):
        stopped_short = seriate(planted, max_iter=100)
    assert stopped_short.ambiguous is True

    settled = _quiet_seriate(planted, max_iter=400)
    assert settled.ambiguous is False
    truth = list(range(161))
    assert list(settled.order) == truth or list(settled.order) == truth[::-1]


# --------------------------------------------------------------------------- #
# the abundance table a corpus produces
# --------------------------------------------------------------------------- #


def test_corpus_columns_do_not_depend_on_document_order():
    docs = [_doc("one", ["B", "A"]), _doc("two", ["C", "A"]), _doc("three", ["B", "C"])]
    forward, labels, types = _abundance_from_corpus(docs)
    backward, back_labels, back_types = _abundance_from_corpus(list(reversed(docs)))
    assert types == ["A", "B", "C"] == back_types  # sorted, not first-seen
    assert labels == ["one", "two", "three"]
    assert back_labels == ["three", "two", "one"]
    # The same document yields the same row whichever way the corpus was walked.
    assert forward == list(reversed(backward))
    assert forward[0] == [1.0, 1.0, 0.0]  # "one" holds A and B, not C


def test_corpus_labels_travel_with_the_ordering():
    docs = [
        _doc("early-1", ["A", "A", "B"]),
        _doc("early-2", ["A", "B", "B"]),
        _doc("late-1", ["Y", "Z", "Z"]),
        _doc("late-2", ["Y", "Y", "Z"]),
    ]
    result = _quiet_seriate(docs)
    ordered = result.ordered_labels()
    assert sorted(ordered) == ["early-1", "early-2", "late-1", "late-2"]
    assert set(ordered[:2]) in ({"early-1", "early-2"}, {"late-1", "late-2"})
    # The two vocabularies share no sign, so they are two blocks and their relative order is
    # convention: the reading within each pair is what the similarity supports.
    assert {frozenset(b) for b in result.components} == {frozenset({0, 1}), frozenset({2, 3})}


# --------------------------------------------------------------------------- #
# adversarial input
# --------------------------------------------------------------------------- #


def test_every_row_blank():
    # Blank assemblages have identical (empty) profiles, so they are all mutually similar.
    result = _quiet_seriate([[0, 0], [0, 0], [0, 0]])
    assert sorted(result.order) == [0, 1, 2]
    assert len(result.components) == 1


def test_blank_row_among_real_ones():
    rows = [[0, 0, 0], [1, 2, 3], [3, 2, 1]]
    result = _quiet_seriate(rows)
    assert sorted(result.order) == [0, 1, 2]
    assert len(result.components) == 1  # a blank row is 100-similar to everything


def test_wide_sparse_matrix_of_singletons_is_invariant():
    # 40 assemblages over 40 types, each holding one type: 40 blocks, nothing to seriate
    # within any of them, and the order between them is pure convention.
    rows = [[1 if c == r else 0 for c in range(40)] for r in range(40)]
    result = _quiet_seriate(rows)
    assert len(result.components) == 40
    base = _content(rows, result.order)
    for seed, reading in _shuffled_readings(rows, range(5)):
        assert reading == base or reading == tuple(reversed(base)), seed


def test_bad_input_still_rejected_cleanly():
    for bad in ([], [[1, 2, 3], [1, 2]], [[1, -2], [3, 4]]):
        with pytest.raises(ValueError):
            seriate(bad)
    with pytest.raises(ValueError):
        seriate(TWO_BLOCKS, max_iter=0)
    with pytest.raises(ValueError):
        seriate(TWO_BLOCKS, labels=["only-one"])
