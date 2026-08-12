"""hands, profiling, and scribal take a query's results wherever they take a corpus.

`Corpus.query` returns `aegean.analysis.QueryResults`, whose matched documents are its
``inscriptions``, so "query, then analyse" is how a subset is measured. These three
modules read the matched documents the way every other analysis coercer does: a queried
subset answers exactly what those same documents answer when they are handed in
directly, and what the subset rebuilt as a `Corpus` answers, while a wrong argument
still fails with a ``TypeError`` naming what arrived.

The archival-series grouping is judged against the script the documents themselves
record when the container carries none, so a Linear B query keeps its series breakdown
and a Linear A one still gets no dossiers.

All offline over the bundled ``lineara`` and ``linearb`` corpora; the assertions are
known answers from those corpora, not "the call runs".
"""

from __future__ import annotations

import pytest

import aegean
from aegean.analysis import FilterRow
from aegean.analysis.hands import by_hand, dossiers, hand_profile
from aegean.analysis.profiling import (
    account_dossiers,
    document_type_profile,
    metrology_profile,
)
from aegean.analysis.scribal import hand_keyness, scribal_hands

KHANIA = "Khania"
PYLOS = "Pylos"
KNOSSOS = "Knossos"


def _lineara_khania():
    """The Khania documents of the bundled Linear A corpus, as `Corpus.query` returns them."""
    corpus = aegean.load("lineara")
    results = corpus.query([FilterRow("site-is", KHANIA)])
    assert len(results.inscriptions) == 226  # the subset the assertions below rest on
    return corpus, results, results.inscriptions


def _linearb_pylos():
    """The Pylos tablets of the bundled Linear B sample, as `Corpus.query` returns them."""
    corpus = aegean.load("linearb")
    results = corpus.query([FilterRow("site-is", PYLOS)])
    assert len(results.inscriptions) == 11
    return corpus, results, results.inscriptions


# ── profiling: the three corpus profiles ─────────────────────────────────────


def test_document_type_profile_over_query_results_matches_the_matched_documents() -> None:
    corpus, results, docs = _lineara_khania()
    assert document_type_profile(results) == document_type_profile(docs)
    # Known answer: Khania's 226 documents are 104 tablets, 101 roundels, 20 nodules,
    # 1 clay vessel — and the counts are the subset's, not the whole corpus's.
    counts = {row.type: row.count for row in document_type_profile(results)}
    assert counts == {"Tablet": 104, "Roundel": 101, "Nodule": 20, "Clay vessel": 1}
    assert sum(counts.values()) == 226
    assert {r.type: r.count for r in document_type_profile(corpus)}["Nodule"] == 886


def test_account_dossiers_over_query_results_match_the_matched_documents() -> None:
    corpus, results, docs = _lineara_khania()
    assert account_dossiers(results) == account_dossiers(docs)
    # Khania yields 21 account-head candidates; the whole corpus yields 427.
    assert len(account_dossiers(results)) == 21
    assert len(account_dossiers(corpus)) == 427
    heads = {d.word for d in account_dossiers(results)}
    assert "A-DU" in heads


def test_metrology_profile_over_query_results_matches_the_matched_documents() -> None:
    corpus, results, docs = _lineara_khania()
    assert metrology_profile(results) == metrology_profile(docs)
    # Known answer: the Khania subset carries 200 numeral tokens (76 fractional,
    # 124 integer) over 8 distinct fraction values; the corpus carries 1,621.
    subset = metrology_profile(results)
    assert (subset.numeral_tokens, subset.fraction_tokens, subset.integer_tokens) == (200, 76, 124)
    assert subset.distinct_fraction_values == 8
    assert [(r.display, r.count) for r in subset.fraction_rows[:2]] == [("1/2", 31), ("1/4", 13)]
    assert metrology_profile(corpus).numeral_tokens == 1621


# ── scribal: hand profiles and hand keyness ──────────────────────────────────


def test_scribal_hands_over_query_results_match_the_matched_documents() -> None:
    corpus, results, docs = _lineara_khania()
    assert scribal_hands(results) == scribal_hands(docs)
    # Known answer: 18 hands are attested at Khania against 102 corpus-wide, and the
    # largest of them, KH Scribe 1, wrote 28 of the subset's tablets.
    profiles = scribal_hands(results)
    assert len(profiles) == 18
    assert len(scribal_hands(corpus)) == 102
    assert (profiles[0].hand, profiles[0].doc_count, profiles[0].token_count) == (
        "KH Scribe 1",
        28,
        251,
    )


def test_hand_keyness_over_query_results_matches_the_matched_documents() -> None:
    corpus, results, docs = _lineara_khania()
    from_query = hand_keyness(results, "KH Scribe 1", min_target=1)
    assert from_query == hand_keyness(docs, "KH Scribe 1", min_target=1)
    # The reference side is the rest of the *subset*: KH Scribe 1's 15 lexical words
    # against the other Khania hands' 107, not against the whole corpus.
    assert {(r.target_total, r.reference_total) for r in from_query} == {(15, 107)}
    assert from_query != hand_keyness(corpus, "KH Scribe 1", min_target=1)


# ── hands: groupings by attribution and by archival series ───────────────────


def test_by_hand_over_query_results_matches_the_matched_documents() -> None:
    corpus, results, docs = _linearb_pylos()
    assert by_hand(results) == by_hand(docs) == by_hand(results.to_corpus(corpus))
    # Known answer: the two attributed Pylos tablets, each with its own series.
    assert [(g.hand, g.doc_count, g.series, g.sites) for g in by_hand(results)] == [
        ("Hand 1", 1, {"Er": 1}, {PYLOS: 1}),
        ("Hand 2", 1, {"Ta": 1}, {PYLOS: 1}),
    ]
    # And the subset is genuinely the subset: no Knossos tablet records a hand.
    assert by_hand(corpus.query([FilterRow("site-is", KNOSSOS)])) == []


def test_hand_profile_over_query_results_matches_the_matched_documents() -> None:
    corpus, results, docs = _linearb_pylos()
    from_query = hand_profile(results, "Hand 2")
    assert from_query == hand_profile(docs, "Hand 2") == hand_profile(
        results.to_corpus(corpus), "Hand 2"
    )
    assert (from_query.doc_count, from_query.doc_ids) == (1, ["PY Ta 641"])
    assert (from_query.series, from_query.sites) == ({"Ta": 1}, {PYLOS: 1})
    assert (from_query.token_count, from_query.word_count) == (6, 4)
    # Hand 2 wrote no Knossos tablet, so the Knossos subset has nothing to profile.
    with pytest.raises(ValueError, match="no documents attributed"):
        hand_profile(corpus.query([FilterRow("site-is", KNOSSOS)]), "Hand 2")


def test_dossiers_over_query_results_match_the_matched_documents() -> None:
    corpus, results, docs = _linearb_pylos()
    from_query = dossiers(results)
    assert from_query == dossiers(docs) == dossiers(results.to_corpus(corpus))
    # Known answer: the ten Pylos (site, series) groupings, Fr the only one with two
    # tablets. The Knossos and Mycenae dossiers of the whole corpus are excluded.
    assert sorted((d.site, d.series, d.doc_count) for d in from_query) == [
        (PYLOS, "Cn", 1),
        (PYLOS, "Eb", 1),
        (PYLOS, "En", 1),
        (PYLOS, "Eo", 1),
        (PYLOS, "Er", 1),
        (PYLOS, "Fr", 2),
        (PYLOS, "Jn", 1),
        (PYLOS, "Sa", 1),
        (PYLOS, "Ta", 1),
        (PYLOS, "Un", 1),
    ]
    whole = {(d.site, d.series): d.doc_count for d in dossiers(corpus)}
    assert whole[(KNOSSOS, "Np")] == 3 and whole[("Mycenae", "Ge")] == 3


# ── the series convention is judged against the documents' own script ────────


def test_series_grouping_reads_the_script_the_documents_record() -> None:
    # A result set carries no ``script_id``, so the script comes from the documents.
    # Without it the Linear B breakdown would silently come back empty and the
    # dossier grouping would refuse a corpus it is defined for.
    corpus, results, docs = _linearb_pylos()
    assert all(d.script_id == "linearb" for d in docs)
    assert by_hand(results)[0].series == {"Er": 1}
    assert hand_profile(results, "Hand 2").series == {"Ta": 1}
    assert dossiers(results)


def test_dossiers_still_refuses_a_non_linear_b_query() -> None:
    # The series parse follows the Linear B designation convention; Linear A ids
    # ("HT 13") must not be read for one, whichever way the documents arrive.
    _corpus, results, docs = _lineara_khania()
    for arg in (results, docs):
        with pytest.raises(ValueError, match="Linear B"):
            dossiers(arg)


# ── a result set with no matched documents reads as no documents ─────────────


def test_words_only_results_behave_like_no_documents() -> None:
    corpus = aegean.load("lineara")
    words = corpus.query([FilterRow("word-contains", "KU")], output="words")
    assert words.words and not words.inscriptions
    for empty in (words, []):
        assert document_type_profile(empty) == []
        assert account_dossiers(empty) == []
        assert metrology_profile(empty).numeral_tokens == 0
        assert scribal_hands(empty) == []
        assert by_hand(empty) == []
        with pytest.raises(ValueError, match="no documents attributed"):
            hand_profile(empty, "KH Scribe 1")
        with pytest.raises(ValueError, match="no documents attributed"):
            hand_keyness(empty, "KH Scribe 1")
        with pytest.raises(ValueError, match="Linear B"):
            dossiers(empty)


# ── a wrong argument still fails cleanly, naming what arrived ────────────────


CALLS = [
    pytest.param(lambda arg: document_type_profile(arg), id="document_type_profile"),
    pytest.param(lambda arg: account_dossiers(arg), id="account_dossiers"),
    pytest.param(lambda arg: metrology_profile(arg), id="metrology_profile"),
    pytest.param(lambda arg: scribal_hands(arg), id="scribal_hands"),
    pytest.param(lambda arg: hand_keyness(arg, "Hand 2"), id="hand_keyness"),
    pytest.param(lambda arg: by_hand(arg), id="by_hand"),
    pytest.param(lambda arg: hand_profile(arg, "Hand 2"), id="hand_profile"),
    pytest.param(lambda arg: dossiers(arg), id="dossiers"),
]


@pytest.mark.parametrize("call", CALLS)
def test_non_iterable_argument_raises_typeerror_naming_it(call) -> None:
    with pytest.raises(TypeError, match="corpus or documents, got int"):
        call(7)


@pytest.mark.parametrize("call", CALLS)
def test_list_of_non_documents_raises_typeerror_naming_the_element(call) -> None:
    with pytest.raises(TypeError, match="corpus or documents, got str"):
        call(["not", "a", "document"])
