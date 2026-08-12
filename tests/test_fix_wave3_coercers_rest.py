"""The remaining analysis entry points read the documents they are handed.

`Corpus.query` returns `aegean.analysis.QueryResults`, whose matched documents are its
``inscriptions``. Accounting reconciliation, Harris segmentation, the editorial-apparatus
surface, Greek terminology rarity, co-occurrence grounding, and the Cypriot profiles all
measure a queried subset as itself: the answer equals the one from those same documents
handed in directly, and from the subset rebuilt as a `Corpus`, and differs from the whole
corpus's. A wrong argument fails with a ``TypeError`` naming what arrived, because a
silently empty or corpus-wide answer to a subset question is a wrong answer.

`variant_groups` is the exception and is pinned as one: it reports a *script's* sign
inventory, which no subset of documents can narrow, so it takes a script id and refuses a
corpus by name rather than answering about the whole catalogue.

All offline over the bundled ``lineara``, ``cypriot``, and ``greek`` corpora plus one
hand-built alt-bearing corpus; the assertions are known answers, not "the call runs".
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import aegean
from aegean.ai.grounding import cooccurrence_evidence
from aegean.analysis import FilterRow
from aegean.analysis.accounting import checkable_accounts
from aegean.analysis.allographs import variant_groups
from aegean.analysis.segmentation import candidate_morphs, segment
from aegean.core.apparatus import alt_readings, apparatus_summary
from aegean.core.corpus import Corpus
from aegean.greek.rarity import terminology_rarity
from aegean.scripts.cypriot.analysis import bridge_coverage, syllabary_profile

KHANIA = "Khania"
ZAKROS = "Zakros"
AMATHUS = "Amathus"
MARION = "Marion"


def _lineara(filters):
    """A bundled Linear A corpus and one of its queried subsets."""
    corpus = aegean.load("lineara")
    results = corpus.query(filters)
    return corpus, results, results.inscriptions


# ── accounting: the balancing accounts of a queried subset ───────────────────


def test_checkable_accounts_over_query_results_are_the_matched_documents() -> None:
    # The HT9* tablets: 19 documents, of which three are intact and balancing.
    corpus, results, docs = _lineara([FilterRow("id-contains", "HT9")])
    assert len(docs) == 19
    from_query = checkable_accounts(results)
    assert from_query == checkable_accounts(docs) == checkable_accounts(
        results.to_corpus(corpus)
    )
    assert [d.id for d in from_query] == ["HT9a", "HT9b", "HT94b"]
    # The whole corpus has seven, four of them outside this subset.
    assert [d.id for d in checkable_accounts(corpus)] == [
        "HT9a",
        "HT9b",
        "HT11b",
        "HT13",
        "HT89",
        "HT94b",
        "HT117a",
    ]


def test_checkable_accounts_of_a_subset_with_none_is_empty_not_the_corpus() -> None:
    # Every balancing account in the bundled corpus is from Haghia Triada, so the
    # Khania subset must answer with none of them rather than with the corpus's seven.
    _corpus, results, docs = _lineara([FilterRow("site-is", KHANIA)])
    assert len(docs) == 226
    assert checkable_accounts(results) == checkable_accounts(docs) == []


# ── segmentation: the vocabulary is the input's, not the corpus's ────────────


def test_candidate_morphs_over_query_results_use_the_subsets_vocabulary() -> None:
    corpus, results, docs = _lineara([FilterRow("site-is", KHANIA)])
    from_query = candidate_morphs(results, min_count=3)
    assert from_query == candidate_morphs(docs, min_count=3)
    assert from_query == candidate_morphs(results.to_corpus(corpus), min_count=3)
    # Known answer: Khania's 96 word types yield five recurring final morphs; the
    # whole corpus yields fifty, and the counts are an order of magnitude larger.
    assert from_query == [("JA", 4), ("SI", 4), ("NE", 3), ("RE", 3), ("TE", 3)]
    whole = candidate_morphs(corpus, min_count=3)
    assert len(whole) == 50 and whole[:3] == [("TE", 37), ("NA", 36), ("JA", 34)]


def test_segment_over_query_results_covers_the_subsets_word_types() -> None:
    corpus, results, docs = _lineara([FilterRow("site-is", KHANIA)])
    from_query = segment(results)
    assert from_query == segment(docs) == segment(results.to_corpus(corpus))
    # One record per distinct lexical word type of the subset, in first-appearance order.
    assert len(from_query) == 96
    assert [s.word for s in from_query] == list(
        dict.fromkeys(t.text for d in docs for t in d.tokens if t.kind.value == "word")
    )
    assert len(segment(corpus)) == len({w for w, _ in corpus.word_frequencies()})


def test_corpus_input_matches_the_documented_word_frequency_recipe() -> None:
    # The documented call is candidate_morphs([w for w, _ in c.word_frequencies()]);
    # handing the corpus over directly must not change a single row.
    corpus = aegean.load("lineara")
    types = [w for w, _ in corpus.word_frequencies()]
    assert candidate_morphs(corpus, min_count=5) == candidate_morphs(types, min_count=5)
    assert candidate_morphs(corpus, min_count=5)[:5] == [
        ("TE", 37),
        ("NA", 36),
        ("JA", 34),
        ("RE", 34),
        ("TI", 29),
    ]


def test_plain_word_strings_still_segment_as_words() -> None:
    # A list of strings is a vocabulary, not documents, and is unchanged by the coercion.
    words = ["KA-NU", "KA-NU-ID", "PA-RO", "PA-RO-ID", "SI-DA", "SI-DA-ID"]
    assert candidate_morphs(words, min_count=3) == [("ID", 3)]
    assert [s.word for s in segment(words)] == words


def test_words_only_results_carry_no_documents_to_segment() -> None:
    corpus = aegean.load("lineara")
    words = corpus.query([FilterRow("word-contains", "KU")], output="words")
    assert words.words and not words.inscriptions
    assert segment(words) == [] and candidate_morphs(words) == []


# ── apparatus: the profile of the documents handed in ────────────────────────


def _alt_corpus() -> Corpus:
    """A small corpus that carries an apparatus: alternate readings and a lost token."""
    return Corpus.from_records(
        [
            {
                "id": "A1",
                "meta": {"site": "Alpha"},
                "lines": [[{"text": "KU-RO", "alt": ["KU-RA"]}, "DA-RO"]],
            },
            {
                "id": "A2",
                "meta": {"site": "Alpha"},
                "lines": [[{"text": "PA-I-TO", "alt": ["PA-I-DE"], "status": "unclear"}]],
            },
            {
                "id": "B1",
                "meta": {"site": "Beta"},
                "lines": [[{"text": "SA-RA", "alt": ["SA-RO"]}, {"text": "X", "status": "lost"}]],
            },
        ],
        script_id="lineara",
    )


def test_alt_readings_over_query_results_are_the_subsets_apparatus() -> None:
    corpus = _alt_corpus()
    results = corpus.query([FilterRow("site-is", "Alpha")])
    from_query = alt_readings(results)
    assert from_query == alt_readings(results.inscriptions)
    # Known answer: the two Alpha tokens with variants, not B1's SA-RA.
    assert [(a.doc_id, a.text, a.alternates, a.status) for a in from_query] == [
        ("A1", "KU-RO", ("KU-RA",), "certain"),
        ("A2", "PA-I-TO", ("PA-I-DE",), "unclear"),
    ]
    assert [a.doc_id for a in alt_readings(corpus)] == ["A1", "A2", "B1"]


def test_apparatus_summary_over_query_results_profiles_the_subset() -> None:
    corpus = _alt_corpus()
    results = corpus.query([FilterRow("site-is", "Alpha")])
    subset = apparatus_summary(results)
    # Known answer: Alpha's two documents and three tokens, two of them with variants,
    # one unclear — B1's lost token belongs to the corpus profile, not this one.
    assert (subset.n_documents, subset.n_tokens, subset.alt_reading_tokens) == (2, 3, 2)
    assert subset.status_counts == {"certain": 2, "unclear": 1, "restored": 0, "lost": 0}
    whole = apparatus_summary(corpus)
    assert (whole.n_documents, whole.n_tokens, whole.alt_reading_tokens) == (3, 5, 3)
    assert whole.status_counts["lost"] == 1


def test_apparatus_summary_of_results_and_of_their_documents_agree() -> None:
    corpus = _alt_corpus()
    results = corpus.query([FilterRow("site-is", "Alpha")])
    from_docs = apparatus_summary(results.inscriptions)
    # A bare document list carries no provenance, so only ``source`` may differ: the
    # results keep the corpus's, which is what makes a subset summary citable.
    assert replace(apparatus_summary(results), source="") == from_docs
    assert apparatus_summary(results).source == "User-supplied corpus (Corpus.from_records)"
    assert from_docs.source == ""


def test_apparatus_summary_reads_the_script_the_documents_record() -> None:
    # A result set carries no ``script_id``; without reading it from the documents the
    # subset summary would report an empty script for a Linear A corpus.
    _corpus, results, docs = _lineara([FilterRow("site-is", KHANIA)])
    assert apparatus_summary(results).script_id == "lineara"
    assert apparatus_summary(docs).script_id == "lineara"
    assert apparatus_summary(docs[0]).script_id == "lineara"


def test_apparatus_summary_over_a_lineara_subset_counts_only_its_tokens() -> None:
    corpus, results, docs = _lineara([FilterRow("site-is", KHANIA)])
    subset = apparatus_summary(results)
    assert (subset.n_documents, subset.n_tokens) == (226, 899)
    assert subset.status_counts == {"certain": 689, "unclear": 35, "restored": 0, "lost": 175}
    whole = apparatus_summary(corpus)
    assert (whole.n_documents, whole.n_tokens) == (1721, 6406)
    assert apparatus_summary(docs).status_counts == subset.status_counts


# ── rarity: the reference register is the corpus handed in ───────────────────


def test_terminology_rarity_scores_against_a_queried_subset() -> None:
    corpus = aegean.load("greek")
    results = corpus.query([FilterRow("id-contains", "john")])
    assert [d.id for d in results.inscriptions] == ["john-1.1"]
    text = "μῆνιν ἄειδε θεὰ λόγος"
    against_subset = terminology_rarity(text, results)
    assert against_subset == terminology_rarity(text, results.inscriptions)
    # Against John alone the Iliad's opening words are absent; against the whole
    # five-text sample each is attested once, so the same text scores far easier.
    assert [(w.word, w.count, w.label) for w in against_subset.words] == [
        ("μῆνιν", 0, "absent"),
        ("ἄειδε", 0, "absent"),
        ("θεὰ", 0, "absent"),
        ("λόγος", 2, "rare"),
    ]
    assert (against_subset.corpus_lemmas, against_subset.corpus_tokens) == (8, 12)
    against_corpus = terminology_rarity(text, corpus)
    assert [(w.word, w.count, w.label) for w in against_corpus.words][:3] == [
        ("μῆνιν", 1, "hapax"),
        ("ἄειδε", 1, "hapax"),
        ("θεὰ", 1, "hapax"),
    ]
    assert (against_corpus.corpus_lemmas, against_corpus.corpus_tokens) == (23, 27)
    assert against_subset.overall > against_corpus.overall


# ── grounding: co-occurrence in the documents handed in ──────────────────────


def test_cooccurrence_evidence_over_query_results_counts_the_subsets_documents() -> None:
    corpus, results, docs = _lineara([FilterRow("site-is", ZAKROS)])
    from_query = cooccurrence_evidence(results, "KU-RO")
    assert from_query == cooccurrence_evidence(docs, "KU-RO")
    assert from_query == cooccurrence_evidence(results.to_corpus(corpus), "KU-RO")
    # Known answer: at Zakros KU-RO shares a tablet with KA-DI once, and with nothing
    # else — a different and much shorter list than the corpus-wide one.
    assert [g.content for g in from_query] == ["co-occurs with KU-RO: KA-DI (×1)"]
    assert [g.content for g in cooccurrence_evidence(corpus, "KU-RO", limit=3)] == [
        "co-occurs with KU-RO: KI-RO (×5)",
        "co-occurs with KU-RO: *306-TU (×4)",
        "co-occurs with KU-RO: KU-PA₃-NU (×4)",
    ]
    assert all(g.source == "analysis:cooccurrence" and g.ref == "KU-RO" for g in from_query)


def test_cooccurrence_evidence_still_takes_a_hand_built_corpus() -> None:
    # A document is anything carrying ``tokens``, so a stand-in corpus keeps working.
    stand_in = SimpleNamespace(
        documents=[
            SimpleNamespace(tokens=[SimpleNamespace(text=t) for t in doc])
            for doc in (("KU-RO", "DA-RO"), ("KU-RO", "DA-RO", "KI-RO"))
        ]
    )
    assert [g.content for g in cooccurrence_evidence(stand_in, "KU-RO")] == [
        "co-occurs with KU-RO: DA-RO (×2)",
        "co-occurs with KU-RO: KI-RO (×1)",
    ]


def test_cooccurrence_evidence_empty_means_no_cooccurrence_not_a_bad_argument() -> None:
    # An empty list is a finding about the word, so it must be reachable only from
    # real documents; a non-corpus argument refuses instead of imitating that finding.
    alone = SimpleNamespace(documents=[SimpleNamespace(tokens=[SimpleNamespace(text="KU-RO")])])
    assert cooccurrence_evidence(alone, "KU-RO") == []
    with pytest.raises(TypeError, match="corpus or documents, got SimpleNamespace"):
        cooccurrence_evidence(SimpleNamespace(), "KU-RO")


# ── the Cypriot profiles: the subset's own signs and readings ────────────────


def test_syllabary_profile_over_query_results_counts_the_subsets_signs() -> None:
    corpus = aegean.load("cypriot")
    results = corpus.query([FilterRow("site-is", AMATHUS)])
    assert len(results.inscriptions) == 61
    subset = syllabary_profile(results)
    assert subset == syllabary_profile(results.inscriptions)
    # Known answer: the Amathus subset writes 571 syllabogram occurrences over 50 of
    # the 55 grid cells, leaving five gaps; the whole corpus leaves one.
    assert (subset.sign_tokens, subset.attested_count, subset.gap_count) == (571, 50, 5)
    whole = syllabary_profile(corpus)
    assert (whole.sign_tokens, whole.attested_count, whole.gap_count) == (1621, 54, 1)
    assert set(whole.gaps) < set(subset.gaps)


def test_bridge_coverage_over_query_results_reads_only_the_subset() -> None:
    corpus = aegean.load("cypriot")
    amathus = corpus.query([FilterRow("site-is", AMATHUS)])
    marion = corpus.query([FilterRow("site-is", MARION)])
    subset = bridge_coverage(amathus)
    assert subset == bridge_coverage(amathus.inscriptions)
    # Known answer: the Amathus texts are the Eteocypriot core of IG XV 1, so the
    # Greek bridge reads none of their 157 words; Marion's Greek reads 21 of 192.
    assert (subset.word_tokens, subset.read_tokens, subset.coverage_pct) == (157, 0, 0.0)
    at_marion = bridge_coverage(marion)
    assert (at_marion.word_tokens, at_marion.read_tokens) == (192, 21)
    assert [(r.form, r.count) for r in at_marion.readings[:2]] == [("e-mi", 15), ("pa-i-se", 3)]
    whole = bridge_coverage(corpus)
    assert (whole.word_tokens, whole.read_tokens) == (448, 33)


# ── variant_groups reports a script, and says so ─────────────────────────────


def test_variant_groups_takes_a_script_id_and_reports_its_inventory() -> None:
    report = variant_groups("lineara")
    assert (report.script_id, report.n_signs) == ("lineara", 342)
    assert [g.base for g in report.groups] == ["PA", "PU", "RA", "TA"]
    assert variant_groups("linearb").n_signs == 211


def test_variant_groups_refuses_documents_rather_than_answering_about_the_script() -> None:
    # The report is read off the sign inventory, which 226 Khania tablets cannot
    # narrow: accepting them would hand back the whole 342-sign catalogue as if it
    # described the subset. Each refusal names what arrived and what to pass instead.
    corpus, results, docs = _lineara([FilterRow("site-is", KHANIA)])
    for arg, name in ((corpus, "Corpus"), (results, "QueryResults"), (docs, "list")):
        with pytest.raises(TypeError, match=f"expects a script id.*got {name}"):
            variant_groups(arg)
    with pytest.raises(TypeError, match="pass the script id"):
        variant_groups(results)
    assert variant_groups(corpus.script_id).n_signs == 342


# ── a wrong argument fails cleanly, naming what arrived ──────────────────────


CALLS = [
    pytest.param(lambda arg: checkable_accounts(arg), id="checkable_accounts"),
    pytest.param(lambda arg: segment(arg), id="segment"),
    pytest.param(lambda arg: candidate_morphs(arg), id="candidate_morphs"),
    pytest.param(lambda arg: terminology_rarity("λόγος", arg), id="terminology_rarity"),
    pytest.param(lambda arg: cooccurrence_evidence(arg, "KU-RO"), id="cooccurrence_evidence"),
    pytest.param(lambda arg: syllabary_profile(arg), id="syllabary_profile"),
    pytest.param(lambda arg: bridge_coverage(arg), id="bridge_coverage"),
]


@pytest.mark.parametrize("call", CALLS)
def test_non_iterable_argument_raises_typeerror_naming_it(call) -> None:
    with pytest.raises(TypeError, match="got int"):
        call(7)


@pytest.mark.parametrize("call", CALLS)
def test_wrong_element_type_raises_typeerror_naming_the_element(call) -> None:
    with pytest.raises(TypeError, match="got int"):
        call([7, 8])


def test_apparatus_keeps_its_own_clean_refusals() -> None:
    for call in (alt_readings, apparatus_summary):
        with pytest.raises(TypeError, match="query's results.*got int"):
            call(7)
        with pytest.raises(TypeError, match="must yield.*Documents; got a int"):
            call([7])
