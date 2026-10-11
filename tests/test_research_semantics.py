"""Hand-counted constructed corpora: operational semantics, not scholarly gold."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import asdict, replace
from fractions import Fraction

import pytest
from typer.testing import CliRunner

from aegean import db
from aegean._view import balance_rows
from aegean.analysis import (
    FilterRow, balance_check, build_cooccurrence_map, build_word_index,
    checkable_accounts, eval_query, is_checkable_account,
)
from aegean.cli import _build_app
from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document, DocumentMeta, FormSegment, ReadingStatus, Token, TokenFormState, TokenKind,
)
from aegean.core.provenance import Provenance
from aegean.core.numerals import check_balances, parse_account_lines


def word(text: str, lemma: object = None, *, status: ReadingStatus = ReadingStatus.CERTAIN,
         source: str | None = None) -> Token:
    annotations = {"lemma": lemma}
    if source is not None:
        annotations["lemma_source"] = source
    return Token(text=text, kind=TokenKind.WORD, status=status, annotations=annotations)


def reference_corpus() -> Corpus:
    unclear = word("λόγος", "λόγος", source="source_annotation")
    unclear = replace(unclear, form_state=TokenFormState(
        diplomatic="λόγος", segments=(FormSegment("λό"), FormSegment("γος", ReadingStatus.UNCLEAR)),
    ))
    tokens = [
        word("λόγος", "λόγος", source="source_annotation"),
        word("ΛΌΓΟΣ", "ΛΌΓΟΣ", source="model_prediction"),
        word(unicodedata.normalize("NFD", "λόγος")),
        word("λογος", "λόγος"),
        word("λόγου", "λόγος", status=ReadingStatus.RESTORED, source="source_annotation"),
        unclear,
        Token(text="ΣΩ", kind=TokenKind.UNKNOWN, annotations={"role": "speaker"}),
        Token(text=";", kind=TokenKind.PUNCT),
        Token(text="3", kind=TokenKind.NUMERAL),
    ]
    tokens = [replace(token, position=position) for position, token in enumerate(tokens)]
    second = [word("λόγος", "λόγος"), word("λόγος", "λόγος"), word("ἄνθρωπος", "")]
    second = [replace(token, position=position) for position, token in enumerate(second)]
    return Corpus([
        Document("one", "greek", tokens=tokens, lines=[list(range(len(tokens)))], meta=DocumentMeta(site="A")),
        Document("two", "greek", tokens=second, lines=[list(range(len(second)))], meta=DocumentMeta(site="B")),
        Document("empty", "greek", tokens=[], lines=[]),
    ], provenance=Provenance(source="constructed reference", data_version="fixture-v1"))


def account(lines: list[list[str]], *, status: ReadingStatus = ReadingStatus.CERTAIN) -> Document:
    tokens = []
    indexes = []
    for line in lines:
        indexes.append(list(range(len(tokens), len(tokens) + len(line))))
        tokens.extend(Token(text=text, kind=TokenKind.WORD, status=status) for text in line)
    return Document("account", "lineara", tokens=tokens, lines=indexes)


def test_hand_counted_surface_normalized_and_lemma_populations() -> None:
    corpus = reference_corpus()
    surface = corpus.word_frequencies()
    assert isinstance(surface, list)
    assert dict(surface)["λόγος"] == 4
    assert dict(surface)["ΛΌΓΟΣ"] == 1
    assert len(surface) == 6
    assert surface.metadata["denominator"] == 9
    assert surface.provenance is corpus.provenance

    normalized = corpus.word_frequencies(view="normalized")
    assert dict(normalized) == {"λόγοσ": 6, "λογοσ": 1, "λόγου": 1, "ἄνθρωποσ": 1}
    assert list(corpus.iter_words(view="normalized")).count("λόγοσ") == 6
    assert "diacritics preserved" in normalized.metadata["normalization"]
    assert "token denominator=9" in normalized.cite()

    lemmas = corpus.word_frequencies(view="lemma")
    assert lemmas == [("λόγοσ", 7)]
    assert lemmas.metadata["denominator"] == 7
    assert lemmas.metadata["selected_word_tokens"] == 9
    assert lemmas.metadata["missing_lemma_tokens"] == 2
    assert lemmas.metadata["lemma_sources"] == {
        "model_prediction": 1, "source_annotation": 3, "unspecified": 3,
    }


def test_document_frequency_denominator_includes_empty_documents() -> None:
    frequencies = reference_corpus().word_frequencies(view="normalized", count_unit="document")
    assert dict(frequencies)["λόγοσ"] == 2
    assert frequencies.metadata["denominator"] == 3
    assert frequencies.metadata["represented_word_tokens"] == 9
    assert sum(dict(reference_corpus().word_frequencies(view="normalized")).values()) == 9


def test_status_sensitivity_includes_partial_editorial_state() -> None:
    corpus = reference_corpus()
    secure = corpus.word_frequencies(view="lemma", statuses=[ReadingStatus.CERTAIN])
    assert secure == [("λόγοσ", 5)]
    assert secure.metadata["excluded_word_tokens"] == 2
    assert secure.metadata["selected_word_tokens"] == 7
    assert secure.metadata["denominator"] == 5
    restored = corpus.word_frequencies(view="lemma", statuses=["restored"])
    assert restored == [("λόγοσ", 1)]
    # A status selection applies to each segment, not just the token's aggregate label.
    uncertain_allowed = corpus.word_frequencies(view="lemma", statuses=["certain", "unclear"])
    assert uncertain_allowed == [("λόγοσ", 6)]


def test_compound_queries_share_keys_counts_and_population_metadata() -> None:
    corpus = reference_corpus()
    rows = [FilterRow("word-prefix", "ΛΌΓ")]
    query = corpus.query(rows, "words", view="normalized")
    assert query.words == [("λόγοσ", 2), ("λόγου", 1)]
    assert query.metadata["denominator"] == 3
    token_query = corpus.query(rows, "words", view="normalized", count_unit="token")
    assert token_query.words == [("λόγοσ", 6), ("λόγου", 1)]
    assert token_query.metadata["denominator"] == 9
    assert "view=normalized" in token_query.cite()
    surface = corpus.query(rows, "words", view="surface")
    assert surface.words == [("ΛΌΓΟΣ", 1)]
    # Omitted view keeps legacy uppercase matching and separate surface counts.
    legacy = corpus.query(rows, "words")
    assert dict(legacy.words)["λόγος"] == 2
    assert "legacy:" in legacy.metadata["predicate_normalization"]
    lemmas = corpus.query([FilterRow("ins-contains-word", "ΛΌΓΟΣ")], view="lemma")
    assert [d.id for d in lemmas.inscriptions] == ["one", "two"]
    subset = corpus.query([FilterRow("site-is", "A")], "words", view="lemma", count_unit="token")
    assert subset.words == [("λόγοσ", 5)]
    assert subset.metadata["denominator"] == 5
    assert subset.metadata["missing_lemma_tokens"] == 1


def test_prebuilt_query_indices_cannot_override_explicit_population() -> None:
    corpus = reference_corpus()
    docs = list(corpus)
    raw_index = build_word_index(docs)
    raw_cooccur = build_cooccurrence_map(docs)
    for view in ("normalized", "lemma"):
        for unit in ("token", "document"):
            direct = eval_query([], "words", docs, raw_index, set(), raw_cooccur,
                                view=view, count_unit=unit, statuses=["certain"])
            expected = corpus.word_frequencies(view=view, count_unit=unit, statuses=["certain"])
            assert direct.words == expected
            assert direct.metadata["denominator"] == expected.metadata["denominator"]
    direct = eval_query([], "words", docs, raw_index, set(), {}, statuses=["certain"])
    assert "λόγου" not in dict(direct.words)
    rows = [FilterRow("word-cooccurs-with", "ΛΌΓΟΣ")]
    direct = eval_query(rows, "words", docs, raw_index, set(), raw_cooccur,
                        view="normalized", statuses=["certain"])
    assert direct.words == corpus.query(rows, "words", view="normalized", statuses=["certain"]).words


@pytest.mark.parametrize("fts", [True, False])
def test_sqlite_search_matches_hand_counted_views(tmp_path, fts: bool) -> None:
    corpus = reference_corpus()
    path = tmp_path / "reference.db"
    db.to_sqlite(corpus, path, fts=fts)
    assert len(db.search(path, "λόγος", view="surface", limit=0)) == 4
    assert len(db.search(path, "ΛΌΓΟΣ", view="normalized", limit=0)) == 6
    assert len(db.search(path, "ΛΌΓΟΣ", view="lemma", limit=0)) == 7
    assert len(db.search(path, "λόγος", view="lemma", statuses=["certain"], limit=0)) == 5
    assert len(db.search(path, "λογος", view="normalized", limit=0)) == 1
    assert len(db.search(path, "λόγ", view="normalized", mode="substring", limit=0)) == 7
    assert {hit[2] for hit in db.search(path, "λόγος", view="lemma", limit=0)} >= {"λόγου", "ΛΌΓΟΣ"}
    assert db.search(path, ";", statuses=["certain"]) == [("one", 7, ";")]


def test_normalization_preserves_iota_subscript_and_folds_final_sigma(tmp_path) -> None:
    corpus = Corpus([Document("forms", "greek", tokens=[
        word("ἐκκλησίᾳ"), word("ἐκκλησίαι"), word("Σ"), word("ς"), word("σ"),
    ], lines=[[0, 1, 2, 3, 4]])])
    normalized = dict(corpus.word_frequencies(view="normalized"))
    assert normalized["σ"] == 3
    assert normalized["ἐκκλησίᾳ"] == normalized["ἐκκλησίαι"] == 1
    path = tmp_path / "forms.db"
    db.to_sqlite(corpus, path)
    assert len(db.search(path, "ἐκκλησίᾳ", view="normalized")) == 1


@pytest.mark.parametrize("stored_status", [None, ""])
def test_explicit_search_reads_legacy_empty_status_as_certain(tmp_path, stored_status) -> None:
    import sqlite3

    corpus = reference_corpus()
    path = tmp_path / "legacy.db"
    corpus.to_sql(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE tokens SET status = ? WHERE doc_id = 'two'", (stored_status,))
    assert len(db.search(path, "λόγος", view="surface", statuses=["certain"], limit=0)) == 3
    assert len(db.search(path, "λόγος", view="lemma", statuses=["certain"], limit=0)) == 5


def test_exact_eligibility_is_separate_from_legacy_zero_tolerance() -> None:
    mismatch = account([["A", "131"], ["KU-RO", "130", "½"]])
    assert is_checkable_account(mismatch, tolerance=0)
    assert not is_checkable_account(mismatch, exact=True)
    assert checkable_accounts([mismatch], exact=True) == []
    check = balance_check(mismatch)[0]
    assert check.difference == 0.5
    assert check.exact_difference == Fraction(1, 2)
    assert not check.exact_balances
    row = balance_rows(mismatch)[0]
    assert row["account_eligible"] and not row["account_eligible_exact"]
    assert row["exact_difference"] == "1/2"
    assert not balance_rows(mismatch, exact=True)[0]["account_eligible"]


def test_exact_rational_fraction_sums_and_subtotals() -> None:
    seventh = account([["A", "1/7"]] * 7 + [["KU-RO", "1"]])
    check = balance_check(seventh, exact=True)[0]
    assert check.exact_difference == 0 and check.balances
    assert is_checkable_account(seventh, exact=True)
    tiny = account([["A", "1/10000000"], ["KU-RO", "0"]])
    assert balance_check(tiny)[0].balances  # legacy 1e-6 cutoff
    assert not balance_check(tiny, exact=True)[0].balances
    assert not check_balances(parse_account_lines([["A", "1/10000000"], ["KU-RO", "0"]]), exact=True)[0].balances
    assert not is_checkable_account(tiny, exact=True)
    thirds = account([
        ["A", "⅓"], ["B", "²⁄₃"], ["KU-RO", "1"],
        ["C", "½"], ["PO-TO-KU-RO", "1", "½"],
    ])
    assert all(check.exact_balances for check in balance_check(thirds))
    # Exact arithmetic does not certify damaged text.
    thirds.tokens[0] = replace(thirds.tokens[0], form_state=TokenFormState(
        diplomatic="A", segments=(FormSegment("A", ReadingStatus.RESTORED),),
    ))
    assert not is_checkable_account(thirds, exact=True)
    # Exact source arithmetic survives integer magnitudes above float precision.
    large = account([["A", "9007199254740993"], ["KU-RO", "9007199254740992"]])
    assert balance_check(large)[0].balances
    assert balance_check(large, exact=True)[0].exact_difference == 1
    assert not balance_check(large, exact=True)[0].balances
    from aegean.cli._common import to_plain

    mapped = to_plain(balance_check(seventh, exact=True))
    assert json.loads(json.dumps(mapped))[0]["exact_difference"] == "0"


def test_cli_and_mcp_expose_selected_counts_and_eligibility(tmp_path, monkeypatch) -> None:
    import aegean.mcp_server as mcp

    corpus = reference_corpus()
    path = tmp_path / "reference.json"
    corpus.to_json(path)
    runner = CliRunner()
    app = _build_app()
    result = runner.invoke(app, ["stats", str(path), "--view", "lemma", "--statuses", "certain", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["frequencies"] == [{"item": "λόγοσ", "count": 5}]
    assert payload["metadata"]["denominator"] == 5
    result = runner.invoke(app, ["query", str(path), "--view", "normalized", "--output-kind", "words", "--count-unit", "token", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["metadata"]["denominator"] == 9
    database = tmp_path / "reference.db"
    corpus.to_sql(database)
    result = runner.invoke(app, ["db", "search", str(database), "λόγος", "--view", "lemma", "--statuses", "certain", "--json"])
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)) == 5
    from aegean.core.corpus import _LOADERS

    monkeypatch.setitem(_LOADERS, "constructed-reference", lambda: corpus)
    query = mcp.query_corpus("constructed-reference", [], "words", view="lemma", count_unit="token", statuses=["certain"])
    assert query["words"] == [{"word": "λόγοσ", "count": 5}]
    assert query["metadata"]["denominator"] == 5
    result = runner.invoke(app, ["balance", "lineara", "HT13", "--exact", "--strict", "--json"])
    assert result.exit_code == 1
    row = json.loads(result.output)[0]
    assert row["exact_difference"] == "1/2" and not row["account_eligible"]
    assert mcp.balance_accounts("lineara", "HT13", exact=True)[0] == row
    from aegean.tui.data import balance_rows as tui_balance_rows
    import aegean

    assert asdict(tui_balance_rows(aegean.load("lineara").get("HT13"))[0]) == balance_rows(aegean.load("lineara").get("HT13"))[0]


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_account_tolerance_rejected_even_for_empty_corpus(value: float) -> None:
    with pytest.raises(ValueError, match="finite, nonnegative"):
        checkable_accounts([], tolerance=value)


def test_unknown_views_and_count_units_are_not_silently_ignored(tmp_path) -> None:
    corpus = reference_corpus()
    with pytest.raises(ValueError, match="view must"):
        corpus.word_frequencies(view="accentless")
    with pytest.raises(ValueError, match="count_unit must"):
        corpus.query([], "words", count_unit="author")
    with pytest.raises(ValueError):
        corpus.word_frequencies(statuses=["secure"])
