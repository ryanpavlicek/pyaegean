"""Input that cannot be read is reported, not accepted with an empty or unusable result.

Two surfaces, one shape of problem: something the code cannot represent or cannot
understand was taken anyway, and the caller got a plausible-looking nothing.

* `aegean.core.numerals.parse_value` answered a 300-digit reading with infinity, which
  `format_value` then could not render at all, and read another script's digits (Arabic-Indic
  ٣, Devanagari ७) as Aegean quantities.
* `aegean.io.review.from_review_table` read a CSV that is not a review table (or an empty
  file) as zero corrections, wrote the unchanged corpus and reported success.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.numerals import (
    check_balances,
    format_value,
    is_value_token,
    line_value,
    parse_account_lines,
    parse_value,
)
from aegean.core.provenance import Provenance
from aegean.io.review import (
    REVIEW_COLUMNS,
    apply_review_table,
    from_review_table,
    merge_review_tables,
    to_review_table,
)

# ── numerals: every parsed value is one format_value can render ──────────────

_ABSURD = "9" * 400  # more digits than a float can hold


def test_parse_value_and_format_value_round_trip() -> None:
    """The pair's invariant: anything parse_value reads, format_value renders."""
    candidates = [
        "1", "10", "197", "0", _ABSURD, "9" * 309, "1" * 400,
        "¾", "³⁄₄", "3/4", "1/2", "13/20", "⅝", "≈ ¹⁄₆", "¹⁄₁₆",
        f"{_ABSURD}/2", f"1/{_ABSURD}", "5/0", "KU-RO", "", "≈",
    ]
    for token in candidates:
        value = parse_value(token)
        if value is None:
            continue
        assert value == value and abs(value) != float("inf"), token  # finite: not inf, not nan
        assert format_value(value)  # renders, rather than raising OverflowError


def test_a_reading_too_large_to_represent_is_not_a_value() -> None:
    assert parse_value(_ABSURD) is None
    assert not is_value_token(_ABSURD)
    assert parse_value(f"{_ABSURD}/2") is None
    # the boundary: the largest float-representable digit run still reads
    assert parse_value("9" * 308) == int("9" * 308)
    assert parse_value("9" * 309) is None


def test_absurd_reading_leaves_the_rest_of_the_line_summable() -> None:
    """It is skipped like any other unreadable token, not summed as infinity.

    The infinity answer poisoned every downstream total: the sum was no longer a
    quantity, and format_value could not print it."""
    assert line_value(["5", _ABSURD, "3"]) == 8.0
    assert format_value(line_value(["5", _ABSURD, "3"])) == "8"


def test_absurd_reading_leaves_a_tablet_total_reportable() -> None:
    lines = parse_account_lines([["GRA", "10"], ["VIN", _ABSURD], ["KU-RO", "10"]])
    (check,) = check_balances(lines)
    assert check.computed_sum == 10 and check.balances
    assert format_value(check.difference) == "0"


@pytest.mark.parametrize(
    "token",
    ["٣", "١٢٣", "۵", "۵۶", "७", "٣/٤", "۵/۶"],  # Arabic-Indic, Eastern Arabic, Devanagari
)
def test_another_scripts_digits_are_not_aegean_numerals(token: str) -> None:
    assert parse_value(token) is None
    assert not is_value_token(token)


def test_decimal_exponent_and_signed_forms_are_not_numerals() -> None:
    """The fraction path went through ``float``, which accepts far more than a numeral."""
    for token in ("1.5/2", "1e5/2", "-1/2", "+1/2", "inf/2", "nan/2", " /2"):
        assert parse_value(token) is None, token


# ── numerals: the readings the editions actually carry are unchanged ─────────


def test_the_bundled_linear_a_readings_are_unchanged() -> None:
    """Hand-checked values that occur in the bundled corpus (HT 6a, HT 12, HT 51b,
    HT 123+124b, KH 104), so tightening the parser cannot quietly drop a real quantity."""
    known = {
        "1": 1, "10": 10, "100": 100,
        "1/2": 0.5, "13/20": 0.65, "³⁄₄": 0.75, "¹⁄₁₆": 0.0625,
        "⅝": 0.625, "≈ ¹⁄₆": pytest.approx(1 / 6),
    }
    corpus = aegean.load("lineara")
    texts = {tok.text for doc in corpus.documents for tok in doc.tokens}
    for token, value in known.items():
        assert token in texts, f"{token!r} is no longer in the bundled corpus"
        assert parse_value(token) == value


def test_every_quantity_shaped_token_in_the_bundled_corpus_still_reads() -> None:
    """Every token written wholly in digits, fraction glyphs and slashes is a quantity, and
    must read as one.

    The shape test is deliberately independent of the parser: the corpus's own
    ``TokenKind.NUMERAL`` is assigned by `parse_value` at load, so filtering on it would
    make any narrowing of the parser invisible here."""
    quantity = re.compile(r"^≈?\s*[0-9⁰-⁹₀-₉½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞⁄/]+$")
    corpus = aegean.load("lineara")
    shaped = [
        tok.text for doc in corpus.documents for tok in doc.tokens if quantity.match(tok.text)
    ]
    assert len(shaped) == 1301  # the bundled corpus's quantity tokens
    unread = sorted({t for t in shaped if parse_value(t) is None})
    assert unread == []
    assert all(format_value(parse_value(t)) for t in shaped)  # type: ignore[arg-type]


# ── review tables: a file that is not one is refused ─────────────────────────


def _corpus() -> Corpus:
    tokens = [
        Token("νόμου", TokenKind.WORD, line_no=0, position=0, annotations={"lemma": "νόμου"}),
        Token("πατρός", TokenKind.WORD, line_no=0, position=1, annotations={"lemma": "πατρός"}),
    ]
    doc = Document(id="d", script_id="greek", tokens=tokens, lines=[[0, 1]])
    return Corpus([doc], script_id="greek", provenance=Provenance(source="test"))


def _reviewed(tmp_path: Path, edits: dict[str, dict[str, str]], name: str = "r.csv") -> Path:
    """A real export with ``edits`` written into it, keyed by token text."""
    path = tmp_path / name
    corpus = _corpus()
    to_review_table(corpus, path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row.update(edits.get(row["token"], {}))
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("shopping.csv", "name,qty\napples,3\npears,4\n"),   # someone else's spreadsheet
        ("empty.csv", ""),                                    # nothing at all
        ("blank-lines.csv", "\n\n"),                          # no header
        ("half.csv", "doc_id,position,token\nd,0,νόμου\n"),   # join key, nowhere to correct
        ("payload.csv", "correct_lemma\nπατήρ\n"),            # corrections, no join key
        ("notes.txt", "just some prose about the text\n"),    # not a table at all
    ],
)
def test_applying_a_file_that_is_not_a_review_table_is_reported(
    tmp_path: Path, name: str, text: str
) -> None:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="not a review table"):
        from_review_table(path, _corpus())


def test_the_refusal_names_the_file_and_the_way_out(tmp_path: Path) -> None:
    path = tmp_path / "shopping.csv"
    path.write_text("name,qty\napples,3\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        from_review_table(path, _corpus())
    message = str(excinfo.value)
    assert "shopping.csv" in message
    assert "correct_lemma" in message and "doc_id" in message  # what was missing
    assert "review export" in message                          # how to get a real one


def test_merging_a_file_that_is_not_a_review_table_is_reported(tmp_path: Path) -> None:
    good = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ", "reviewer": "a"}})
    bad = tmp_path / "shopping.csv"
    bad.write_text("name,qty\napples,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a review table"):
        merge_review_tables([good, bad], _corpus())


def test_a_real_review_table_still_applies(tmp_path: Path) -> None:
    """The refusal must not reach a table that works: this is the whole journey."""
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ"}})
    corrected = from_review_table(path, _corpus(), reviewer="me")
    token = corrected.documents[0].tokens[1]
    assert token.annotations["lemma"] == "πατήρ"
    assert token.annotations["lemma__pred"] == "πατρός"
    assert token.annotations["reviewed_by"] == "me"


def test_a_table_without_the_form_columns_still_applies(tmp_path: Path) -> None:
    """Tables predating the form_* columns carry the join key and the corrections, which
    is all a review table needs."""
    full = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ"}})
    with open(full, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    columns = [c for c in REVIEW_COLUMNS if not c.startswith(("form_", "alignment_"))]
    trimmed = tmp_path / "legacy.csv"
    with open(trimmed, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{c: row[c] for c in columns} for row in rows])
    corrected = from_review_table(trimmed, _corpus())
    assert corrected.documents[0].tokens[1].annotations["lemma"] == "πατήρ"


def test_a_malformed_review_csv_is_reported_cleanly(tmp_path: Path) -> None:
    """A real review header whose body is broken raises ValueError, never csv.Error."""
    oversized = '"' + "x" * (csv.field_size_limit() + 1000) + '"'
    path = tmp_path / "broken.csv"
    path.write_text(",".join(REVIEW_COLUMNS) + f"\nd,0,{oversized}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed review CSV"):
        from_review_table(path, _corpus())


# ── review tables: an apply that landed nothing says so ──────────────────────


def test_apply_reports_what_the_table_held_and_what_landed(tmp_path: Path) -> None:
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ"}})
    result = apply_review_table(path, _corpus(), reviewer="me")
    assert (result.rows, result.corrections, result.corrected) == (2, 1, 1)
    assert result.corpus.documents[0].tokens[1].annotations["lemma"] == "πατήρ"


def test_an_untouched_table_reports_no_corrections(tmp_path: Path) -> None:
    """Rows were read, nobody filled anything in: distinguishable from a real apply."""
    path = _reviewed(tmp_path, {})
    result = apply_review_table(path, _corpus())
    assert result.rows == 2
    assert result.corrections == 0 and result.corrected == 0


def test_a_correction_matching_the_prediction_reports_zero_corrected(tmp_path: Path) -> None:
    """A reviewer who confirmed the machine value offered a correction that changes
    nothing; the counts keep those two states apart."""
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατρός"}})
    result = apply_review_table(path, _corpus())
    assert result.rows == 2 and result.corrections == 1 and result.corrected == 0
    assert result.corpus.provenance is not None
    assert result.corpus.provenance.notes == ()  # nothing changed, nothing claimed


def test_from_review_table_returns_the_same_corpus_as_the_reporting_form(
    tmp_path: Path,
) -> None:
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ"}})
    plain = from_review_table(path, _corpus(), reviewer="me")
    reported = apply_review_table(path, _corpus(), reviewer="me").corpus
    assert plain.fingerprint() == reported.fingerprint()
    assert plain.provenance is not None and reported.provenance is not None
    assert plain.provenance.notes == reported.provenance.notes


# ── the existing guards must still fire ──────────────────────────────────────


def test_a_row_naming_a_different_word_still_raises(tmp_path: Path) -> None:
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ", "token": "ΨΕΥΔΟΣ"}})
    with pytest.raises(ValueError, match="different token"):
        from_review_table(path, _corpus())


def test_a_correction_matching_no_token_still_raises(tmp_path: Path) -> None:
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ", "position": "9999"}})
    with pytest.raises(ValueError, match="match no token"):
        from_review_table(path, _corpus())


def test_duplicate_rows_with_conflicting_corrections_still_raise(tmp_path: Path) -> None:
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ"}})
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    clash = dict(rows[1])
    clash["correct_lemma"] = "πάτρα"
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS))
        writer.writeheader()
        writer.writerows([*rows, clash])
    with pytest.raises(ValueError, match="conflicting corrections"):
        from_review_table(path, _corpus())


def test_a_correction_on_an_unusable_position_still_raises(tmp_path: Path) -> None:
    path = _reviewed(tmp_path, {"πατρός": {"correct_lemma": "πατήρ", "position": "1.0"}})
    with pytest.raises(ValueError, match="unusable position"):
        from_review_table(path, _corpus())
