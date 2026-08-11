"""Regressions for confidently-wrong answers about the meaning of a Greek word.

The through-line is that each defect returned something *grounded-looking* rather than
an honest miss, which is the worst failure mode for a research tool:

* the rule tier spliced a lowercase citation ending onto a MAJUSCULE stem, so an
  inscription's ΛΟΓΟΥ was reported as the lemma "ΛΟΓος" with ``needs_review`` False.
* a lexicon lookup that missed fell back on an accent-blind key, answering ``εἰ`` "if"
  with the entry for ``εἷ`` "where" and ``λαός`` "people" with ``λᾶος`` "stone".
* ``clean_gloss`` promised "" for a non-definition but let a paradigm or prosody note
  through, so the concise cascade reported "the penult. is regularly short" as the
  meaning of χείρ instead of falling through to Abbott-Smith's "the hand".
* the held-out scorers zipped gold against predictions non-strictly, so a tagger that
  returned too few predictions shrank the accuracy denominator instead of aborting.
* ``read_corpus("-")`` handed stdin to a loader that treats a non-JSON string as a
  filename, so piping the text ``cyp.json`` silently analysed that file.
"""

from __future__ import annotations

import pytest


from aegean import greek


@pytest.fixture(autouse=True, scope="module")
def _restore_backends():
    """Leave the process as this module found it.

    Backend activation is global session state, so a module that turns one on and walks
    away changes what unrelated tests see -- which under ``pytest -n`` means a different
    worker, and a failure with no visible cause. Everything this file activates is turned
    off again here."""
    yield
    from aegean import greek

    for name in (
        "disable_neural_pipeline",
        "disable_treebank",
        "disable_lsj",
        "disable_lexicon",
        "disable_paradigms",
        "disable_tagger",
        "disable_parser",
        "disable_lemmatizer",
        "disable_neural_lemmatizer",
        "disable_calibration",
    ):
        try:
            getattr(greek, name)()
        except Exception:  # pragma: no cover - a backend that was never active
            pass



# --- majuscule input gets a real Greek word, not a mixed-case splice ---------- #

MAJUSCULE = ["ΛΟΓΟΥ", "ΘΕΟΥ", "ΛΕΓΕΙ", "ΑΥΤΟΥ", "ΑΝΘΡΩΠΟΥΣ", "ΔΙΟΝΥΣΙΟΥ"]


@pytest.mark.parametrize("form", MAJUSCULE)
def test_rule_lemma_never_mixes_case(form: str) -> None:
    lemma, source = greek.lemmatize_sourced(form)
    assert lemma == lemma.lower(), f"{form} -> {lemma} is neither Greek nor a word"
    assert source.name == "RULE"


def test_minuscule_and_capitalised_forms_are_untouched() -> None:
    # A capitalised proper noun keeps its capital: only an all-uppercase stem folds.
    assert greek.lemmatize_sourced("Πέτρου")[0] == "Πέτρος"
    assert greek.lemmatize_sourced("Χριστοῦ")[0] == "Χριστός"
    assert greek.lemmatize_sourced("λέγει")[0] == "λέγω"


def test_no_shipped_corpus_word_gets_a_mixed_case_lemma() -> None:
    import aegean

    for corpus_id in ("iip", "isicily"):
        corpus = aegean.load(corpus_id)
        seen: set[str] = set()
        for document in corpus.documents:
            for token in document.tokens:
                if token.kind.name != "WORD" or token.text in seen:
                    continue
                seen.add(token.text)
                lemma = greek.lemmatize(token.text)
                if lemma.lower() == lemma or lemma.upper() == lemma:
                    continue
                # A mixed-case lemma is legitimate only when the SURFACE was mixed case.
                assert token.text.lower() != token.text.upper() and not token.text.isupper(), (
                    f"{token.text} -> {lemma}"
                )


# --- a lexicon miss is a miss, not a differently accented word ---------------- #

WRONG_HOMOGRAPHS = ["εἰ", "καλῶς", "λαός", "ἄλλος", "πρῶτος"]


@pytest.fixture(scope="module")
def lsj():
    pytest.importorskip("aegean.greek.lexicon")
    from aegean.greek import lexicon

    try:
        return lexicon.use_lsj(build=False)
    except Exception:  # pragma: no cover - the 270 MB index is not built here
        pytest.skip("LSJ index not available")


@pytest.mark.parametrize("word", WRONG_HOMOGRAPHS)
def test_accented_query_is_not_folded_onto_a_different_word(lsj, word: str) -> None:
    assert lsj.gloss(word) is None, f"{word} still resolves to another headword"


def test_the_folds_that_must_keep_working(lsj) -> None:
    assert (lsj.gloss("λόγος") or "").startswith("λόγος")
    assert (lsj.gloss("λογος") or "").startswith("λόγος")  # unaccented input still folds
    assert (lsj.gloss("καλὸς") or "").startswith("καλός")  # grave is a positional acute
    assert (lsj.gloss("ἄνθρωπός") or "").startswith("ἄνθρωπος")  # enclitic throwback


def test_accent_compatibility_rule() -> None:
    from aegean.greek.lexindex import compatible_accents

    assert compatible_accents("ἄνθρωπός", "ἄνθρωπος")  # one extra acute: throwback
    assert compatible_accents("καλὸς", "καλός")  # grave levels to acute
    assert not compatible_accents("εἰ", "εἷ")  # different marks entirely
    assert not compatible_accents("λαός", "λᾶος")
    assert not compatible_accents("καλῶς", "κάλως")


def test_an_ambiguous_stripped_key_resolves_to_nothing() -> None:
    from aegean.greek.lexicons import LexiconInfo
    from aegean.greek.lexindex import IndexLexicon

    info = LexiconInfo(
        id="probe",
        name="probe",
        scope="classical",
        license="test",
        source="https://example.invalid",
        hosted=False,
    )
    data = {
        "λαός": {"hw": "λαός", "def": "people"},
        "λᾶος": {"hw": "λᾶος", "def": "stone"},
        "λόγος": {"hw": "λόγος", "def": "word"},
    }
    lexicon = IndexLexicon(info, data)
    assert lexicon.lookup("λαός").gloss == "people"  # exact key still wins
    assert lexicon.lookup("λαος") is None  # ambiguous: two headwords strip to λαος
    assert lexicon.lookup("λογος").gloss == "word"  # unambiguous: still folds


# --- the concise cascade reports a meaning, never apparatus ------------------- #

APPARATUS_WORDS = {
    "εἰμί": "to be",
    "ἔχω": "to have",
    "χείρ": "the hand",
    "πολύς": "much",
    "πατήρ": "a father",
    "πόλις": "a city",
    "ποιέω": "to make",
}


@pytest.mark.parametrize("word,expected", sorted(APPARATUS_WORDS.items()))
def test_concise_gloss_falls_through_apparatus(word: str, expected: str) -> None:
    from aegean import ai

    for dictionary in ("middle-liddell", "cunliffe", "abbott-smith"):
        try:
            greek.use_lexicon(dictionary)
        except Exception:  # pragma: no cover - index not built in this environment
            pytest.skip(f"{dictionary} index not available")
    assert ai.concise_gloss(word) == expected


@pytest.mark.parametrize(
    "line",
    [
        "The whole of the pres. ind. (except 2nd sg.)",
        "the penult. is regularly short, when the ult. is long",
        "the Ionic declension πολλός is retained",
        "for the poet. form ἔσχεθον",
        "Att. Poets often use the penult. short",
    ],
)
def test_clean_gloss_returns_empty_for_apparatus(line: str) -> None:
    from aegean.ai import clean_gloss

    assert clean_gloss(line) == ""


@pytest.mark.parametrize(
    "line,expected",
    [
        ("λόγος: a word", "a word"),
        ("χείρ: the hand", "the hand"),
        ("the formation of a city", "the formation of a city"),
        ("πολύς: much, many", "much, many"),
    ],
)
def test_clean_gloss_keeps_a_real_definition(line: str, expected: str) -> None:
    from aegean.ai import clean_gloss

    assert clean_gloss(line) == expected


# --- a short prediction list aborts instead of shrinking the denominator ------ #


def _split(sentences: int = 4, tokens: int = 3):
    from aegean.greek.heldout import HeldoutSplit, HeldoutToken

    rows = tuple(
        tuple(
            HeldoutToken(form=chr(97 + i), lemma=chr(97 + i), upos="NOUN", seen=False, scored=True)
            for i in range(tokens)
        )
        for _ in range(sentences)
    )
    return HeldoutSplit(sentences=rows, train_forms=frozenset(), train_lemma={}, train_pos={})


def test_full_predictions_score_every_token() -> None:
    from aegean.greek.heldout import score

    assert score(lambda forms: [(f, "NOUN") for f in forms], split=_split())["n_all"] == 12


def test_short_tag_batch_aborts() -> None:
    from aegean.greek.heldout import score

    with pytest.raises(ValueError, match="predictions for a sentence"):
        score(
            lambda forms: [(f, "NOUN") for f in forms],
            split=_split(),
            batch_size=2,
            tag_batch=lambda batch: [[(s[0], "NOUN")] for s in batch],
        )


def test_short_tag_sentence_aborts_in_error_analysis() -> None:
    from aegean.greek.erroranalysis import analyze_errors

    with pytest.raises(ValueError, match="predictions for a sentence"):
        analyze_errors(lambda forms: [(forms[0], "NOUN")], _split().sentences)


# --- stdin is parsed as JSON, never as a path -------------------------------- #


@pytest.mark.parametrize("payload", ["cyp.json", "hello world", "", "   "])
def test_stdin_corpus_never_reads_a_file(monkeypatch, tmp_path, payload: str) -> None:
    import io
    import sys

    from aegean.core.resolve import CorpusNotFound, read_corpus

    (tmp_path / "cyp.json").write_text('{"documents": []}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    with pytest.raises(CorpusNotFound, match="stdin did not contain a JSON corpus"):
        read_corpus("-")


def test_stdin_still_accepts_a_real_corpus(monkeypatch) -> None:
    import io
    import sys

    import aegean
    from aegean.core.resolve import read_corpus

    payload = aegean.load("cypriot").to_json()
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert len(read_corpus("-").documents) == len(aegean.load("cypriot").documents)
