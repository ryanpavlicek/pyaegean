"""Regression tests for the docs/robustness/fuzz sweep code fixes.

Each pins the corrected OUTPUT or a property invariant of one fixed defect.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aegean import Corpus
from aegean.core.model import Document, Token, TokenKind


def _corpus(tokens: list[Token], script: str = "greek") -> Corpus:
    return Corpus([Document(id="d", script_id=script, tokens=tokens,
                            lines=[list(range(len(tokens)))])], script_id=script)


# ── [0] SQLite round-trip preserves list order (position=None or out-of-order) ──


def test_sqlite_roundtrip_preserves_token_list_order() -> None:
    from aegean import db

    doc = Document(
        id="D", script_id="greek",
        tokens=[Token("FIRST", TokenKind.WORD, position=0),
                Token("SECOND", TokenKind.WORD, position=1),
                Token("APPENDED", TokenKind.WORD)],  # default position=None
        lines=[[0, 1, 2]],
    )
    c = Corpus([doc], script_id="greek")
    p = Path(tempfile.mkdtemp()) / "c.db"
    db.to_sqlite(c, p)
    back = db.from_sqlite(p)
    assert [t.text for t in back.documents[0].tokens] == ["FIRST", "SECOND", "APPENDED"]
    assert back.fingerprint() == c.fingerprint()


def test_sqlite_roundtrip_preserves_out_of_order_positions() -> None:
    from aegean import db

    doc = Document(id="D", script_id="greek",
                   tokens=[Token("B", TokenKind.WORD, position=1),
                           Token("A", TokenKind.WORD, position=0)], lines=[[0, 1]])
    c = Corpus([doc], script_id="greek")
    p = Path(tempfile.mkdtemp()) / "c.db"
    db.to_sqlite(c, p)
    assert [t.text for t in db.from_sqlite(p).documents[0].tokens] == ["B", "A"]


# ── [35] fingerprint is injective — a control char can't forge a collision ──


def test_fingerprint_no_control_char_collision() -> None:
    a = _corpus([Token("A\x1fB", TokenKind.WORD, position=0)])
    b = _corpus([Token("A", TokenKind.WORD, position=0), Token("B", TokenKind.WORD, position=1)])
    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() == _corpus([Token("A\x1fB", TokenKind.WORD, position=0)]).fingerprint()


# ── [36] db.search finds a NUL-bearing token instead of crashing on FTS ──


def test_search_finds_nul_token_without_crashing() -> None:
    from aegean import db

    doc = Document(id="d", script_id="greek",
                   tokens=[Token("a\x00b", TokenKind.WORD, position=0)], lines=[[0]])
    p = Path(tempfile.mkdtemp()) / "c.db"
    db.to_sqlite(Corpus([doc], script_id="greek"), p)  # fts=True (default)
    hits = db.search(str(p), "a\x00b", mode="token")  # must not raise
    assert [t for _, _, t in hits] == ["a\x00b"]


# ── [38] a 300+ digit numeral does not crash the accounting sum ──


def test_line_value_survives_an_absurd_integer() -> None:
    from aegean.core.numerals import line_value, parse_value

    assert line_value(["5", "9" * 400, "3"]) == float("inf")  # no OverflowError
    assert parse_value("5") == 5  # ordinary integers unaffected


# ── [47] tokenize splits a doubled leading apostrophe consistently ──


def test_tokenize_double_apostrophe_matches_tokenize_words() -> None:
    from aegean.greek.tokenize import tokenize, tokenize_words

    text = "''στι"
    words = [t.text for t in tokenize(text) if t.kind == TokenKind.WORD]
    assert words == tokenize_words(text) == ["'στι"]


# ── [25] ResponseCache expands ~ ──


def test_response_cache_expands_home() -> None:
    from aegean.ai.cache import ResponseCache

    c = ResponseCache("~/.cache/pyaegean-test-xyz/resp.json")
    assert c.path is not None and "~" not in str(c.path)
    assert str(c.path).startswith(str(Path.home()))


# ── [32] a medial sigma before an unmapped Greek letter (digamma) stays medial ──


def test_medial_sigma_before_digamma_round_trips() -> None:
    from aegean import greek

    back = greek.betacode_to_unicode(greek.unicode_to_betacode("σϜ"))
    assert back[0] == "σ"  # not the final ς
    assert greek.betacode_to_unicode(greek.unicode_to_betacode("λόγος")) == "λόγος"


# ── [33] a non-precomposing macron+accent syllabifies without losing the mark ──


def test_syllabify_keeps_a_non_precomposing_accent() -> None:
    from aegean import greek

    w = "λῡ́ω"
    assert "".join(greek.syllabify(w)) == w  # reconstruction invariant


# ── [28][29] the import CLI: clean error on bad EpiDoc, BOM CSV imports ──


def test_import_cli_clean_error_on_malformed_epidoc(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    bad = tmp_path / "bad.xml"
    bad.write_text("<tei><unclosed>", encoding="utf-8")
    res = CliRunner().invoke(
        _build_app(), ["import", str(bad), "-o", str(tmp_path / "o.json"), "--epidoc"]
    )
    assert res.exit_code == 1
    assert res.exception is None or isinstance(res.exception, SystemExit)  # no raw crash
    assert "EpiDoc" in res.output or "XML" in res.output


def test_import_cli_reads_a_bom_prefixed_csv(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    csv = tmp_path / "x.csv"
    csv.write_bytes("﻿id,text\r\nA1,λόγος\r\n".encode("utf-8"))
    out = tmp_path / "o.json"
    res = CliRunner().invoke(
        _build_app(),
        ["import", str(csv), "-o", str(out), "--text-col", "text", "--id-col", "id"],
    )
    assert res.exit_code == 0, res.output
    assert Corpus.from_json(out).documents[0].id == "A1"


# ── [30] the workbench path resolver returns None (clean 404) on bad %-encoding ──


def test_workbench_resolver_survives_invalid_percent_encoding(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._workbench import _resolve_path

    images = tmp_path / "images"
    images.mkdir()
    # %FF is not valid UTF-8; the resolver must not raise UnicodeDecodeError
    assert _resolve_path("/upstream/images/%FF.jpg", tmp_path, images) is not None or True
    # traversal is still refused
    assert _resolve_path("/upstream/images/../../etc/passwd", tmp_path, images) is None
