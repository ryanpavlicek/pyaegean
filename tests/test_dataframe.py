"""pandas interop — the headline 'corpus as a DataFrame' feature."""

import pytest

import aegean


def test_to_dataframe_levels():
    pytest.importorskip("pandas")
    c = aegean.load("lineara")

    docdf = c.to_dataframe(level="document")
    assert len(docdf) == 1721
    assert {"id", "site", "n_words"} <= set(docdf.columns)

    worddf = c.to_dataframe(level="word")
    assert {"doc_id", "text", "kind"} <= set(worddf.columns)
    assert (worddf["kind"] == "word").all()


def test_to_dataframe_bad_level():
    c = aegean.load("lineara")
    with pytest.raises(ValueError):
        c.to_dataframe(level="bogus")
