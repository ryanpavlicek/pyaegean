"""CLI-friendliness foundation helpers: the shared did-you-mean/casefold corpus resolution
(`aegean.core.resolve.suggest`, the read_corpus final branch), the typer-free forgiving
document resolver (`resolve_document`) and its CLI wrapper's unchanged error text, the
file-write guard (`writing`, parent-dir creation + one-line OSError failures), the single
``wrote <path>`` confirmation in write_result, and the combined -o/--json epilogue
(`emit_result`)."""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

import aegean  # noqa: E402
from aegean.core.corpus import Corpus  # noqa: E402
from aegean.core.model import Document, Token, TokenKind  # noqa: E402
from aegean.core.resolve import (  # noqa: E402
    CorpusNotFound,
    read_corpus,
    resolve_document,
    suggest,
)

runner = CliRunner()

REGISTERED = ["cypriot", "cyprominoan", "damos", "greek", "lineara", "linearb", "nt", "sigla"]


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    from aegean.cli import _build_app

    return _build_app()


def _doc(did: str, word: str = "χ") -> Document:
    return Document(
        id=did, script_id="greek", tokens=[Token(text=word, kind=TokenKind.WORD)], lines=[[0]]
    )


def _tiny() -> Corpus:
    return Corpus(documents=[_doc("HT13"), _doc("HT13a")], script_id="greek")


# ── suggest ──────────────────────────────────────────────────────────────────
def test_suggest_known_answers() -> None:
    assert suggest("linera", REGISTERED, n=2) == ["lineara", "linearb"]
    assert suggest("greeek", REGISTERED) == ["greek"]
    assert suggest("lienarb", REGISTERED, n=1) == ["linearb"]
    assert suggest("zzzzzz", REGISTERED) == []


def test_suggest_is_case_insensitive_but_returns_original_spelling() -> None:
    assert suggest("GREEEK", REGISTERED) == ["greek"]
    assert suggest("ht13a", ["HT13", "HT13a"]) == ["HT13a", "HT13"]


# ── read_corpus: casefold + did-you-mean ─────────────────────────────────────
def test_read_corpus_forgives_case_on_registered_ids() -> None:
    assert len(read_corpus("LINEARA")) == 1721
    assert len(read_corpus("LineArA")) == 1721


def test_read_corpus_unknown_id_suggests_close_match() -> None:
    with pytest.raises(CorpusNotFound) as exc:
        read_corpus("linera")
    msg = str(exc.value)
    assert msg.startswith("unknown corpus 'linera' — did you mean 'lineara' or 'linearb'? ")
    # the accepted-forms sentence is still there, unchanged
    assert "expected a registered id (" in msg
    assert "tlg0012.tlg001" in msg and "'-' for JSON on stdin" in msg


def test_read_corpus_single_suggestion() -> None:
    with pytest.raises(CorpusNotFound, match="did you mean 'greek'\\?"):
        read_corpus("greeek")


def test_read_corpus_no_close_match_keeps_the_old_message() -> None:
    with pytest.raises(CorpusNotFound) as exc:
        read_corpus("definitely-not-a-corpus")
    msg = str(exc.value)
    assert "did you mean" not in msg
    assert msg.startswith("unknown corpus 'definitely-not-a-corpus'; expected a registered id (")


def test_cli_info_forgives_case_and_suggests(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["info", "LINEARA", "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["documents"] == 1721
    res = runner.invoke(app, ["info", "linera"])
    assert res.exit_code == 1
    assert "did you mean 'lineara'" in res.output


# ── resolve_document (typer-free) ────────────────────────────────────────────
def test_resolve_document_exact_and_folded() -> None:
    c = _tiny()
    doc, near = resolve_document(c, "HT13")
    assert doc is not None and doc.id == "HT13" and near == []
    doc, near = resolve_document(c, "ht13")  # unique casefold
    assert doc is not None and doc.id == "HT13" and near == []


def test_resolve_document_space_fold() -> None:
    c = Corpus(documents=[_doc("PY Ta 641")], script_id="greek")
    doc, near = resolve_document(c, "py ta 641")
    assert doc is not None and doc.id == "PY Ta 641" and near == []
    doc, near = resolve_document(c, "PYTA641")
    assert doc is not None and doc.id == "PY Ta 641"


def test_resolve_document_section_tail() -> None:
    c = Corpus(
        documents=[_doc("tlg0099.tlg001:1", "μῆνιν"), _doc("tlg0099.tlg001:2", "ἄειδε")],
        script_id="greek",
    )
    doc, near = resolve_document(c, "1")
    assert doc is not None and doc.id == "tlg0099.tlg001:1" and near == []


def test_resolve_document_ambiguous_tail_is_not_guessed() -> None:
    c = Corpus(documents=[_doc("a:1"), _doc("b:1")], script_id="greek")
    doc, near = resolve_document(c, "1")
    assert doc is None
    assert near == ["a:1", "b:1"]  # both offered, neither guessed


def test_resolve_document_near_matches_and_total_miss() -> None:
    doc, near = resolve_document(_tiny(), "ht1")
    assert doc is None and near == ["HT13", "HT13a"]
    doc, near = resolve_document(_tiny(), "zz")
    assert doc is None and near == []


def test_resolve_document_on_a_real_corpus() -> None:
    c = aegean.load("lineara")
    doc, _ = resolve_document(c, "ht13")
    assert doc is not None and doc.id == "HT13"


# ── resolve_doc CLI wrapper: error text is byte-identical ────────────────────
def test_resolve_doc_error_text_without_near_matches(capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import resolve_doc

    with pytest.raises(typer.Exit) as exc:
        resolve_doc(_tiny(), "tiny", "zz")
    assert exc.value.exit_code == 1
    assert capsys.readouterr().err == (
        "aegean: no document 'zz' in 'tiny'. (2 documents; `aegean load tiny` lists them)\n"
    )


def test_resolve_doc_error_text_with_near_matches(capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import resolve_doc

    with pytest.raises(typer.Exit):
        resolve_doc(_tiny(), "tiny", "ht1")
    assert capsys.readouterr().err == (
        "aegean: no document 'ht1' in 'tiny'. close: HT13, HT13a. "
        "(2 documents; `aegean load tiny` lists them)\n"
    )


def test_cli_show_unknown_doc_message_unchanged(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["show", "lineara", "NOPE99"])
    assert res.exit_code == 1
    assert (
        "no document 'NOPE99' in 'lineara'. "
        "(1721 documents; `aegean load lineara` lists them)"
    ) in res.output


# ── writing(): the shared file-write guard ───────────────────────────────────
def test_writing_creates_parent_directories(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import writing

    out = tmp_path / "a" / "b" / "r.txt"
    with writing(out) as p:
        p.write_text("data", encoding="utf-8")
    assert out.read_text(encoding="utf-8") == "data"


def test_writing_maps_oserror_to_one_line(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import writing

    target = tmp_path / "taken.json"
    target.mkdir()  # writing to a directory raises OSError
    with pytest.raises(typer.Exit) as exc:
        with writing(target):
            target.write_text("x", encoding="utf-8")
    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith(f"aegean: cannot write {target}: ")
    assert err.count("\n") == 1  # exactly one line


def test_writing_lets_other_exceptions_through(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import fail, writing

    with pytest.raises(ValueError, match="domain"):
        with writing(tmp_path / "x.txt"):
            raise ValueError("domain")
    # an inner fail() (typer.Exit) passes through untouched, not double-wrapped
    with pytest.raises(typer.Exit):
        with writing(tmp_path / "y.txt"):
            raise fail("inner")


# ── write_corpus / write_result: parents, sqlite, wrote line ─────────────────
def test_write_corpus_creates_parents_and_round_trips(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import write_corpus

    pj = tmp_path / "new1" / "c.json"
    pdb = tmp_path / "new2" / "c.db"
    write_corpus(_tiny(), pj)
    write_corpus(_tiny(), pdb)
    assert [d.id for d in read_corpus(str(pj))] == ["HT13", "HT13a"]
    assert [d.id for d in read_corpus(str(pdb))] == ["HT13", "HT13a"]


def test_write_corpus_sqlite_failure_is_one_line(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import write_corpus

    target = tmp_path / "taken.db"
    target.mkdir()  # sqlite cannot open a directory
    with pytest.raises(typer.Exit) as exc:
        write_corpus(_tiny(), target)
    assert exc.value.exit_code == 1
    assert capsys.readouterr().err.startswith(f"aegean: cannot write {target}: ")


def test_write_result_creates_parents_and_confirms_on_stderr(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import write_result

    data = [{"item": "A", "count": 3}]
    out = tmp_path / "deep" / "r.json"
    write_result(data, out)
    assert json.loads(out.read_text(encoding="utf-8")) == data
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout stays clean for --json
    assert captured.err == f"wrote {out}\n"


def test_write_result_oserror_is_one_line_and_no_wrote(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import write_result

    target = tmp_path / "taken.json"
    target.mkdir()
    with pytest.raises(typer.Exit):
        write_result([{"a": 1}], target)
    err = capsys.readouterr().err
    assert err.startswith(f"aegean: cannot write {target}: ") and "wrote" not in err


def test_write_helpers_extension_errors_unchanged(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import write_corpus, write_result

    with pytest.raises(typer.Exit):
        write_corpus(_tiny(), tmp_path / "c.xyz")
    assert "use a .json or .db/.sqlite extension" in capsys.readouterr().err
    with pytest.raises(typer.Exit):
        write_result([{"a": 1}], tmp_path / "r.png")
    err = capsys.readouterr().err
    assert "use a .json, .csv, or .txt extension" in err and "wrote" not in err


# ── emit_result: -o and --json combine ───────────────────────────────────────
def test_emit_result_honors_both_flags(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import emit_result

    data = [{"item": "A", "count": 3}]
    out = tmp_path / "r.json"
    assert emit_result(data, json_output=True, output=out) is True
    captured = capsys.readouterr()
    assert json.loads(out.read_text(encoding="utf-8")) == data  # -o wrote the file
    assert json.loads(captured.out) == data  # --json still printed
    assert captured.err == f"wrote {out}\n"


def test_emit_result_single_flag_and_human_path(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._common import emit_result

    data = {"n": 1}
    out = tmp_path / "solo.json"
    assert emit_result(data, json_output=False, output=out) is True
    captured = capsys.readouterr()
    assert captured.out == "" and out.exists()
    assert emit_result(data, json_output=True, output=None) is True
    assert json.loads(capsys.readouterr().out) == data
    assert emit_result(data, json_output=False, output=None) is False  # human rendering
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


# ── end-to-end through a real command ────────────────────────────────────────
def test_cli_stats_output_into_missing_directory(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "not" / "yet" / "s.json"
    res = runner.invoke(app, ["stats", "lineara", "--top", "3", "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 3
    assert f"wrote {out}" in res.output


def test_cli_stats_output_cannot_write_is_one_line(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "taken.json"
    target.mkdir()
    res = runner.invoke(app, ["stats", "lineara", "--top", "3", "-o", str(target)])
    assert res.exit_code == 1
    assert res.output.startswith(f"aegean: cannot write {target}: ")
    assert res.output.strip().count("\n") == 0  # one line, no traceback
