"""Bring-your-own-file import: aegean.io.from_text* / from_csv and `aegean import`."""

from __future__ import annotations

import pytest

import aegean
from aegean import io as aegean_io
from aegean.core.resolve import CorpusNotFound

JOHN = "ἐν ἀρχῇ ἦν ὁ λόγος."


def _texts(corpus, doc_index=0):
    return [t.text for t in corpus.documents[doc_index].tokens]


def test_from_text_whole_tokenizes_greek_and_drops_punctuation() -> None:
    c = aegean_io.from_text(JOHN, doc_id="john")
    assert len(c) == 1
    texts = _texts(c)
    assert texts == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]  # period dropped by the Greek tokenizer
    assert c.documents[0].id == "john"


def test_from_text_split_modes() -> None:
    text = "ἐν ἀρχῇ\nἦν ὁ λόγος\n\nκαὶ θεὸς\nἦν"
    assert len(aegean_io.from_text(text, split="whole")) == 1
    para = aegean_io.from_text(text, split="paragraph")
    assert len(para) == 2
    assert [d.id for d in para] == ["text:1", "text:2"]
    assert len(aegean_io.from_text(text, split="line")) == 4  # four non-empty lines


def test_from_text_empty_raises() -> None:
    with pytest.raises(ValueError):
        aegean_io.from_text("   \n\n  ")


def test_from_text_non_greek_uses_whitespace_and_splits_signs() -> None:
    c = aegean_io.from_text("KU-RO KI-RO", script_id="lineara", doc_id="x")
    toks = c.documents[0].tokens
    assert [t.text for t in toks] == ["KU-RO", "KI-RO"]
    assert toks[0].signs == ("KU", "RO")  # hyphenated tokens get their signs


def test_from_text_file_round_trips_through_read_corpus(tmp_path) -> None:
    f = tmp_path / "myplato.txt"
    f.write_text(JOHN, encoding="utf-8")
    c = aegean_io.from_text_file(f)
    assert c.documents[0].id == "myplato"  # id defaults to the stem
    out = tmp_path / "myplato.json"
    c.to_json(out)
    assert len(aegean.read_corpus(str(out))) == 1


def test_from_text_file_missing_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        aegean_io.from_text_file(tmp_path / "nope.txt")


def test_from_text_dir_one_doc_per_file_with_dedup(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("ἦν ὁ λόγος", encoding="utf-8")
    (tmp_path / "b.txt").write_text("καὶ θεὸς ἦν", encoding="utf-8")
    c = aegean_io.from_text_dir(tmp_path)
    assert sorted(d.id for d in c) == ["a", "b"]
    assert len(c) == 2


def test_from_text_dir_empty_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        aegean_io.from_text_dir(tmp_path)


def test_from_csv(tmp_path) -> None:
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "id,line,period\nP1,ἦν ὁ λόγος,Koine\nP2,καὶ θεὸς ἦν,Koine\n", encoding="utf-8"
    )
    c = aegean_io.from_csv(csv_path, text_col="line", id_col="id", meta_cols=["period"])
    assert [d.id for d in c] == ["P1", "P2"]
    assert c.documents[0].meta.period == "Koine"
    assert _texts(c) == ["ἦν", "ὁ", "λόγος"]


def test_from_csv_missing_text_col_raises(tmp_path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("id,body\n1,x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        aegean_io.from_csv(csv_path, text_col="text")


def test_read_corpus_txt_points_at_import(tmp_path) -> None:
    f = tmp_path / "stuff.txt"
    f.write_text(JOHN, encoding="utf-8")
    with pytest.raises(CorpusNotFound) as exc:
        aegean.read_corpus(str(f))
    assert "aegean import" in str(exc.value)


def test_cli_import_text_then_use(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    src = tmp_path / "myplato.txt"
    src.write_text(JOHN, encoding="utf-8")
    out = tmp_path / "myplato.json"
    app = _build_app()
    r = CliRunner().invoke(app, ["import", str(src), "-o", str(out)])
    assert r.exit_code == 0, r.output
    # the imported corpus now works with any corpus command
    r2 = CliRunner().invoke(app, ["stats", str(out), "--top", "3"])
    assert r2.exit_code == 0, r2.output
    assert "λόγος" in r2.output


def test_cli_import_csv(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    src = tmp_path / "rows.csv"
    src.write_text("id,text\nA,ἦν ὁ λόγος\n", encoding="utf-8")
    out = tmp_path / "rows.json"
    r = CliRunner().invoke(
        _build_app(), ["import", str(src), "-o", str(out), "--id-col", "id"]
    )
    assert r.exit_code == 0, r.output
    assert len(aegean.read_corpus(str(out))) == 1
