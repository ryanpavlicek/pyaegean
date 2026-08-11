"""A reviewer's correction must never be discarded in silence.

`from_review_table` documents that a correction which matches no token raises
`ValueError`. One path did not honour that: the parser gated rows on
``str.isdigit()``, which is wrong in both directions. It rejects values ``int``
accepts (a spreadsheet's ``-1``, ``+1``, or ``1.0``), dropping the whole row -- and
with it the reviewer's correction -- before any validation could report it; and it
accepts values ``int`` rejects (``²`` is a Unicode digit), which crashed with a raw
``ValueError`` from ``int()`` instead of the clean documented error.

This matters because the review table is a CSV a human edits in a spreadsheet, and
spreadsheets retype integer columns readily. Losing a scholar's corrections without
a word is the worst available outcome for this feature.
"""

from __future__ import annotations

import csv
import io

import pytest


from aegean.greek.annotate import annotate_corpus
from aegean.io import from_text_file
from aegean.io.review import from_review_table, to_review_table


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


TEXT = "ὁ ἀνὴρ λέγει τῷ παιδί.\n"


@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / "in.txt"
    source.write_text(TEXT, encoding="utf-8")
    corpus = annotate_corpus(from_text_file(source, script_id="greek"))
    table = tmp_path / "review.csv"
    to_review_table(corpus, table)
    return corpus, table, table.read_text(encoding="utf-8-sig")


def _write(tmp_path, base: str, *, position: str, correction: str | None):
    rows = list(csv.DictReader(io.StringIO(base)))
    if correction is not None:
        rows[1]["correct_lemma"] = correction
    rows[1]["position"] = position
    path = tmp_path / "edited.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("position", ["-1", "1.0", "abc", "", "²", "1e3"])
def test_correction_with_unusable_position_raises_instead_of_vanishing(
    prepared, tmp_path, position
):
    corpus, _table, base = prepared
    path = _write(tmp_path, base, position=position, correction="ΤΕΣΤΛΕΜΜΑ")
    with pytest.raises(ValueError) as excinfo:
        from_review_table(path, corpus)
    message = str(excinfo.value)
    assert "position" in message
    assert repr(position) in message or position in message


@pytest.mark.parametrize("position", ["1", " 1", "+1", "01"])
def test_positions_int_can_parse_still_apply(prepared, tmp_path, position):
    # ``+1`` and `` 1`` were previously DROPPED by the isdigit gate even though they
    # name a real token; parsing with ``int`` lands them correctly.
    corpus, _table, base = prepared
    path = _write(tmp_path, base, position=position, correction="ΤΕΣΤΛΕΜΜΑ")
    applied = from_review_table(path, corpus)
    token = applied.documents[0].tokens[1]
    assert (token.annotations or {}).get("lemma") == "ΤΕΣΤΛΕΜΜΑ"


@pytest.mark.parametrize("position", ["-1", "abc", "", "²"])
def test_row_without_a_correction_is_still_skipped_quietly(prepared, tmp_path, position):
    # Only a row that actually carries reviewer content is worth failing the run for.
    corpus, _table, base = prepared
    path = _write(tmp_path, base, position=position, correction=None)
    applied = from_review_table(path, corpus)
    assert [t.text for t in applied.documents[0].tokens] == [
        t.text for t in corpus.documents[0].tokens
    ]


def test_neighbouring_tokens_are_untouched_by_a_correction(prepared, tmp_path):
    corpus, _table, base = prepared
    path = _write(tmp_path, base, position="1", correction="ΤΕΣΤΛΕΜΜΑ")
    applied = from_review_table(path, corpus)
    tokens = applied.documents[0].tokens
    assert (tokens[1].annotations or {}).get("lemma") == "ΤΕΣΤΛΕΜΜΑ"
    for index in (0, 2, 3):
        before = (corpus.documents[0].tokens[index].annotations or {}).get("lemma")
        after = (tokens[index].annotations or {}).get("lemma")
        assert before == after


def test_documented_guards_still_fire(prepared, tmp_path):
    """The contract this fix restores must not have broken its siblings."""
    corpus, _table, base = prepared

    def edit(mutate):
        rows = list(csv.DictReader(io.StringIO(base)))
        rows[1]["correct_lemma"] = "ΤΕΣΤ"
        mutate(rows)
        path = tmp_path / "case.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return path

    with pytest.raises(ValueError):  # exported token text does not match the corpus
        from_review_table(edit(lambda r: r[1].__setitem__("token", "ΨΕΥΔΟΣ")), corpus)
    with pytest.raises(ValueError):  # corrected row matches no token
        from_review_table(edit(lambda r: r[1].__setitem__("position", "9999")), corpus)
    with pytest.raises(ValueError):  # conflicting duplicate corrections
        from_review_table(
            edit(lambda r: r.insert(2, {**r[1], "correct_lemma": "ΑΛΛΟ"})), corpus
        )
    with pytest.raises(ValueError):  # unknown document
        from_review_table(edit(lambda r: r[1].__setitem__("doc_id", "nosuchdoc")), corpus)
