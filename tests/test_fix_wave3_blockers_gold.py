"""Gold-file decoding and corpus coercion on two entry points that lacked both.

- ``greek.evaluate_on_ud`` reads a caller-supplied gold CoNLL-U as ``utf-8-sig``, so a
  fold exported with a leading byte-order mark scores identically to the same fold
  without one. The system side of the same comparison is read as plain ``utf-8``
  because it is the file the function itself just wrote; the premise behind that
  asymmetry (pyaegean's own CoNLL-U carries no BOM) is asserted here too, so the two
  reads cannot be quietly unified in either direction.
- ``analysis.classify_corpus`` accepts a `Corpus`, the results of a `Corpus.query`, or a
  plain list of documents, matching its sibling analysis entry points, and classifies
  exactly the documents handed in.
"""

from __future__ import annotations

from itertools import chain
from pathlib import Path

import pytest

CONLLU = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"
BOM = "﻿"


def _require_evaluator() -> None:
    """Fetch the official conll18 evaluator once; skip if offline (the test_ud pattern)."""
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            from aegean.greek.ud import _eval_module

            _eval_module()
        except Exception as exc:
            pytest.skip(f"official evaluator unavailable offline: {exc}")


# --- the gold file is decoded as utf-8-sig ----------------------------------------


def test_evaluate_on_ud_scores_a_bom_prefixed_gold_file_identically(tmp_path: Path) -> None:
    """A BOM on the caller's gold fold changes no score and raises nothing.

    Before the gold handle was opened as ``utf-8-sig`` the mark was glued to the first
    line, and the evaluator rejected the leading ``# newdoc`` comment as a row with the
    wrong number of columns: a column-count complaint about a line that has no columns.
    """
    _require_evaluator()
    from aegean.greek.ud import evaluate_on_ud

    raw = CONLLU.read_bytes()
    plain = tmp_path / "plain.conllu"
    plain.write_bytes(raw)
    bom = tmp_path / "bom.conllu"
    bom.write_bytes(BOM.encode("utf-8") + raw)

    plain_scores = evaluate_on_ud(source=plain, parse=False)
    bom_scores = evaluate_on_ud(source=bom, parse=False)

    assert bom_scores == plain_scores
    # Not a comparison of two empty results: the fixture's rows were actually scored.
    assert plain_scores["n_sentences"] == 2
    assert plain_scores["n_words"] == 8
    assert plain_scores["lemma"] == 1.0


def test_bootstrap_ud_and_genre_slices_read_a_bom_prefixed_gold_file(tmp_path: Path) -> None:
    """The other two entry points that take a caller-supplied ``source=`` gold fold.

    ``bootstrap_ud`` and ``evaluate_by_genre`` re-read the gold file to split it into
    per-sentence blocks, so a byte-order mark reaches the evaluator through them too.
    """
    _require_evaluator()
    from aegean.greek.ud import bootstrap_ud, evaluate_by_genre

    raw = CONLLU.read_bytes()
    plain = tmp_path / "plain.conllu"
    plain.write_bytes(raw)
    bom = tmp_path / "bom.conllu"
    bom.write_bytes(BOM.encode("utf-8") + raw)

    assert bootstrap_ud(source=bom, parse=False, n_resamples=20, seed=3) == bootstrap_ud(
        source=plain, parse=False, n_resamples=20, seed=3
    )
    by_genre = evaluate_by_genre(source=bom, parse=False)
    assert by_genre == evaluate_by_genre(source=plain, parse=False)
    # Again, not an equality between two empty results: a real slice was scored.
    scored = [v for k, v in by_genre.items() if not k.startswith("_")]
    assert scored and all(s["n_words"] for s in scored)
    assert sum(s["n_words"] for s in scored) == 8


def test_pipeline_conllu_output_carries_no_bom() -> None:
    """The premise licensing the plain-utf-8 read of the system side.

    ``evaluate_on_ud`` writes the system CoNLL-U and reads it back in the same call, so
    that handle stays on exact ``utf-8``. That is only correct while the emitted text is
    BOM-less; if the emitter ever prefixed one, the system read would need the gold
    read's tolerance.
    """
    from aegean.greek.ud import load_conllu, pipeline_conllu

    emitted = pipeline_conllu(load_conllu(CONLLU), parse=False)
    assert not emitted.startswith(BOM)
    assert emitted.lstrip().startswith("#")


# --- classify_corpus takes a corpus, a query's results, or documents ---------------


@pytest.fixture(scope="module")
def lineara():
    import aegean

    return aegean.load("lineara")


@pytest.fixture(scope="module")
def haghia_triada(lineara):
    """A proper, non-empty subset of the bundled Linear A corpus."""
    from aegean.analysis.query import FilterRow

    results = lineara.query([FilterRow(field="site-is", value="Haghia Triada")])
    assert 0 < len(results.inscriptions) < len(lineara)
    return results


def test_classify_corpus_over_query_results_classifies_the_queried_subset(
    lineara, haghia_triada
) -> None:
    """A query's results classify as their own documents do, not as the whole corpus."""
    from aegean.analysis import classify_corpus

    subset = classify_corpus(haghia_triada)

    # Equal to the same call over exactly those documents.
    assert subset == classify_corpus(list(haghia_triada.inscriptions))
    # And distinguishable from the whole corpus, so "it ran" cannot pass for "it ran
    # over the subset".
    whole = classify_corpus(lineara)
    assert subset != whole
    # The classified ids ARE the queried ids: nothing outside the subset leaked in and
    # nothing inside it was dropped.
    assert set(chain.from_iterable(subset.values())) == {
        d.id for d in haghia_triada.inscriptions
    }
    assert sum(len(v) for v in subset.values()) == len(haghia_triada.inscriptions)
    # Every category key is still present, empty ones included.
    assert set(subset) == set(whole)


def test_classify_corpus_preserves_the_order_it_was_handed(haghia_triada) -> None:
    from aegean.analysis import classify_corpus, classify_structure

    docs = list(haghia_triada.inscriptions)
    reversed_buckets = classify_corpus(docs[::-1])
    forward_buckets = classify_corpus(docs)
    for key, ids in forward_buckets.items():
        assert reversed_buckets[key] == ids[::-1], key
    # And the bucket a document lands in is the single-document verdict.
    for key, ids in forward_buckets.items():
        for doc in docs:
            if doc.id in ids:
                assert classify_structure(doc) == key
                break


def test_classify_corpus_matches_a_plain_corpus_and_its_document_list(lineara) -> None:
    """The pre-existing whole-corpus behavior is unchanged by the coercion."""
    from aegean.analysis import classify_corpus

    assert classify_corpus(lineara) == classify_corpus(list(lineara))


@pytest.mark.parametrize(
    ("bad", "named"),
    [
        (42, "int"),
        (None, "NoneType"),
        (object(), "object"),
        ("HT13", "str"),
        ([1, 2], "int"),
    ],
)
def test_classify_corpus_names_what_arrived_instead_of_a_raw_traceback(
    bad, named: str
) -> None:
    """Adversarial input gets a TypeError naming the offending type."""
    from aegean.analysis import classify_corpus

    with pytest.raises(TypeError) as exc:
        classify_corpus(bad)
    message = str(exc.value)
    assert "expected a corpus or documents" in message
    assert named in message
    # Not an unbounded dump of whatever was passed.
    assert len(message) < 200
