"""Regression tests for aegean.io fixes.

- `write_epidoc` on a Corpus: two document ids that sanitize to the same filename must not
  silently overwrite each other; the collision is disambiguated deterministically (in id order)
  with a warning, and every document round-trips back intact.
- `to_parquet`: a genuine round-trip through pyarrow (the token rows and columns survive
  exactly), not just "the file exists".
"""

from __future__ import annotations

from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.io import from_epidoc, to_parquet, write_epidoc


def _doc(doc_id: str, word: str) -> Document:
    return Document(
        id=doc_id, script_id="linearb",
        tokens=[Token(word, TokenKind.WORD, line_no=0, position=0)], lines=[[0]],
        meta=DocumentMeta(name=doc_id),
    )


def test_write_epidoc_colliding_ids_write_distinct_files(tmp_path: Path) -> None:
    # "KN X 1" and "KN,X;1" both sanitize to "KN_X_1"; before the fix the second write
    # clobbered the first and only one document survived.
    docs = [_doc("KN,X;1", "TO-SO"), _doc("KN X 1", "KU-RO")]  # corpus order ≠ id order
    out = tmp_path / "epidoc"
    with pytest.warns(UserWarning, match=r"'KN X 1', 'KN,X;1'"):
        write_epidoc(Corpus(docs, script_id="linearb"), out)

    # two files, suffixed deterministically in id order ("KN X 1" sorts first, keeps the base name)
    assert sorted(p.name for p in out.glob("*.xml")) == ["KN_X_1-2.xml", "KN_X_1.xml"]
    assert from_epidoc(out / "KN_X_1.xml", script_id="linearb").documents[0].id == "KN X 1"
    assert from_epidoc(out / "KN_X_1-2.xml", script_id="linearb").documents[0].id == "KN,X;1"

    # both documents round-trip with their own content
    back = {d.id: d for d in from_epidoc(out, script_id="linearb").documents}
    assert [t.text for t in back["KN X 1"].tokens] == ["KU-RO"]
    assert [t.text for t in back["KN,X;1"].tokens] == ["TO-SO"]


def test_write_epidoc_suffix_skips_an_existing_document_name(tmp_path: Path) -> None:
    # the -2 suffix for the "A B"/"A#B" collision is itself taken by the id "A_B-2";
    # the suffix must skip ahead rather than overwrite that document's file.
    docs = [_doc("A B", "KU-RO"), _doc("A#B", "TO-SO"), _doc("A_B-2", "PA-I-TO")]
    out = tmp_path / "epidoc"
    with pytest.warns(UserWarning, match=r"'A B', 'A#B'"):
        write_epidoc(Corpus(docs, script_id="linearb"), out)

    assert sorted(p.name for p in out.glob("*.xml")) == ["A_B-2.xml", "A_B-3.xml", "A_B.xml"]
    back = {d.id: [t.text for t in d.tokens] for d in from_epidoc(out, script_id="linearb").documents}
    assert back == {"A B": ["KU-RO"], "A#B": ["TO-SO"], "A_B-2": ["PA-I-TO"]}


def test_write_epidoc_unique_ids_warn_nothing(tmp_path: Path) -> None:
    import warnings

    out = tmp_path / "epidoc"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        write_epidoc(Corpus([_doc("KN X 1", "KU-RO"), _doc("KN X 2", "TO-SO")], script_id="linearb"), out)
    assert sorted(p.name for p in out.glob("*.xml")) == ["KN_X_1.xml", "KN_X_2.xml"]


def test_to_parquet_token_level_roundtrips_exactly(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    import pandas as pd
    import pyarrow.parquet as pq

    corpus = aegean.load("linearb")
    expected = corpus.to_dataframe("token")
    assert len(expected) > 0  # a trivially-empty frame would make the comparison vacuous

    p = tmp_path / "lb.parquet"
    to_parquet(corpus, p, level="token")
    got = pq.read_table(p).to_pandas()

    assert list(got.columns) == list(expected.columns)
    pd.testing.assert_frame_equal(got, expected)
