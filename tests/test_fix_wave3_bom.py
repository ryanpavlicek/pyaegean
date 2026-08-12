"""A leading UTF-8 BOM reads as an encoding marker on every surface that takes a file.

The readers behind `Corpus.from_json` accept one; the resolver in front of them, the
CoNLL-U comment count, and the JSONL stream reader did not, so the same payload was
accepted or refused depending on which door it came through, and one command reported two
different comment totals for a single file. Making the JSON probe BOM-blind also has a
cost of its own: a probe wide enough to accept a JSON *array* swallows the relative path
``[draft].json``, which is a legal filename.

Also pinned here: an error message quoting a value out of the file being read stays short
enough to print. The reader names the offending field, so the value it quotes is untrusted
input of unbounded length.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

import aegean  # noqa: E402
from aegean.cli import _build_app  # noqa: E402
from aegean.cli._greek import _jsonl_sentences  # noqa: E402
from aegean.core.corpus import Corpus  # noqa: E402
from aegean.core.provenance import SCHEMA_VERSION  # noqa: E402
from aegean.core.resolve import read_corpus  # noqa: E402

runner = CliRunner()

BOM = "﻿"
# One BOM'd sentence: two comments and two data rows, so a lost first comment is visible.
CONLLU = (
    "# sent_id = s1\n"
    "# text = a b\n"
    "1\ta\ta\tX\t_\t_\t0\troot\t_\t_\n"
    "2\tb\tb\tX\t_\t_\t1\tdep\t_\t_\n"
    "\n"
)


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture(scope="module")
def corpus_json() -> str:
    """A real saved corpus, small enough to write into each test's tmp_path."""
    source = aegean.load("lineara")
    return Corpus(list(source)[:3], provenance=source.provenance).to_json()


def _corpus_dict(**document: object) -> dict[str, object]:
    doc: dict[str, object] = {"id": "D1", "tokens": [{"text": "A-DU", "kind": "word"}]}
    doc.update(document)
    return {"_meta": {"schemaVersion": SCHEMA_VERSION}, "documents": [doc]}


# ── from_json: a path and a JSON array open with the same character ──────────


def test_from_json_reads_a_relative_path_whose_name_begins_with_a_bracket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus_json: str
) -> None:
    """``[draft].json`` is a filename, not a JSON array.

    Accepting ``[`` as a JSON opener made the two forms collide: the string was parsed as
    JSON and the file never opened."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "[draft].json").write_text(corpus_json, encoding="utf-8")

    loaded = Corpus.from_json("[draft].json")

    assert [d.id for d in loaded] == [d.id for d in Corpus.from_json(corpus_json)]


def test_from_json_still_reports_a_malformed_json_payload_as_json(tmp_path: Path) -> None:
    """The path fallback is reached only when a file of that name exists.

    A truncated payload is not a filename, so it must keep raising its own decode error
    rather than being reported as a missing file."""
    with pytest.raises(json.JSONDecodeError):
        Corpus.from_json('{"documents": [')


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("{" + "x" * 500_000, id="longer-than-any-filename"),
        pytest.param("{\x00", id="embedded-nul"),
        pytest.param("{\n" * 1000, id="embedded-newlines"),
        pytest.param("{" + ":" * 300, id="reserved-characters"),
    ],
)
def test_from_json_reports_a_payload_the_filesystem_cannot_even_name(payload: str) -> None:
    """The path fallback asks the OS about a string that was never a path.

    A NUL byte, a name past the length limit, or an embedded newline makes that question
    itself an error; the caller must still get the decode error for what they passed."""
    with pytest.raises(json.JSONDecodeError):
        Corpus.from_json(payload)


def test_from_json_reads_a_json_array_as_json_not_as_a_path() -> None:
    """A JSON array parses, and is then refused for what it is: a corpus is an object."""
    with pytest.raises(ValueError, match="must be a JSON object, got an array"):
        Corpus.from_json("[1, 2, 3]")


def test_from_json_accepts_a_bom_on_a_file_and_on_a_string(
    tmp_path: Path, corpus_json: str
) -> None:
    path = tmp_path / "bom.json"
    path.write_text(corpus_json, encoding="utf-8-sig")
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")

    expected = [d.id for d in Corpus.from_json(corpus_json)]
    assert [d.id for d in Corpus.from_json(path)] == expected
    assert [d.id for d in Corpus.from_json(str(path))] == expected
    assert [d.id for d in Corpus.from_json(BOM + corpus_json)] == expected


# ── read_corpus: the resolver in front of those readers ──────────────────────


def test_read_corpus_accepts_a_bom_on_an_inline_json_corpus(corpus_json: str) -> None:
    """``str.lstrip()`` does not remove a BOM, so the probe fell through to the
    registered-id branch and reported the whole payload as an unknown corpus name."""
    assert [d.id for d in read_corpus(BOM + corpus_json)] == [
        d.id for d in read_corpus(corpus_json)
    ]


def test_read_corpus_accepts_a_bom_on_stdin(
    monkeypatch: pytest.MonkeyPatch, corpus_json: str
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(BOM + corpus_json))

    assert [d.id for d in read_corpus("-")] == [d.id for d in read_corpus(corpus_json)]


def test_read_corpus_still_refuses_stdin_that_is_not_a_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The BOM-blind probe must not widen into accepting a filename piped as text."""
    monkeypatch.setattr("sys.stdin", io.StringIO(BOM + "cyp.json\n"))

    with pytest.raises(ValueError, match="stdin did not contain a JSON corpus"):
        read_corpus("-")


def test_read_corpus_still_resolves_a_registered_id_and_a_saved_file(
    tmp_path: Path, corpus_json: str
) -> None:
    """The probe change must not shadow the branches after it."""
    path = tmp_path / "saved.json"
    path.write_text(corpus_json, encoding="utf-8")

    assert len(read_corpus("lineara")) == len(aegean.load("lineara"))
    assert [d.id for d in read_corpus(str(path))] == [d.id for d in read_corpus(corpus_json)]


# ── conllu inspect: one payload, one comment total ───────────────────────────


def test_conllu_inspect_comment_total_matches_its_own_sentences(
    app, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    """The document-level count re-read the file as plain utf-8 while the parse used
    utf-8-sig, so on a BOM'd file the first ``#`` no longer matched and the same JSON
    payload carried ``n_comments`` 1 at document level against 2 in its sentence."""
    path = tmp_path / "bom.conllu"
    path.write_text(CONLLU, encoding="utf-8-sig")

    result = runner.invoke(app, ["greek", "conllu", "inspect", str(path), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)

    per_sentence = [s["n_comments"] for s in payload["sentences"]]
    assert per_sentence == [2]
    assert payload["n_comments"] == sum(per_sentence)


def test_conllu_inspect_counts_a_bom_less_file_identically(app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    plain = tmp_path / "plain.conllu"
    plain.write_text(CONLLU, encoding="utf-8")
    bom = tmp_path / "bom.conllu"
    bom.write_text(CONLLU, encoding="utf-8-sig")

    def summary(path: Path) -> dict[str, object]:
        result = runner.invoke(app, ["greek", "conllu", "inspect", str(path), "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        payload.pop("source")
        return payload

    assert summary(bom) == summary(plain)


# ── greek stream: JSONL input ────────────────────────────────────────────────


def test_jsonl_input_accepts_a_bom_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "bom.jsonl"
    path.write_text('["a", "b"]\n["c"]\n', encoding="utf-8-sig")

    assert list(_jsonl_sentences(path)) == [["a", "b"], ["c"]]


def test_jsonl_input_accepts_a_bom_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(BOM + '["a", "b"]\n'))

    assert list(_jsonl_sentences("-")) == [["a", "b"]]


def test_jsonl_input_still_reports_a_malformed_line(tmp_path: Path) -> None:
    """Dropping a BOM must not soften the reader: a later bad line is still named."""
    path = tmp_path / "bad.jsonl"
    path.write_text('["a"]\nnot json\n', encoding="utf-8-sig")

    with pytest.raises(ValueError, match="line 2 is not valid JSON"):
        list(_jsonl_sentences(path))


def test_jsonl_input_strips_only_a_leading_bom(tmp_path: Path) -> None:
    """A BOM is an encoding marker at the start of a file, and ordinary data elsewhere."""
    path = tmp_path / "inner.jsonl"
    path.write_text(f'["a{BOM}b"]\n', encoding="utf-8-sig")

    assert list(_jsonl_sentences(path)) == [[f"a{BOM}b"]]


# ── error messages quote the file's own values, so they are capped ───────────

_HUGE = "x" * 500_000
# Long enough that any untruncated value would dominate, short enough that the field
# name, the document, and the guidance all still fit.
_LIMIT = 400


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            _corpus_dict(tokens=[{"text": "t", "kind": _HUGE}]),
            "'kind'",
            id="token-enum-value",
        ),
        pytest.param(
            _corpus_dict(tokens=[{"text": "t", "kind": "word", "status": _HUGE}]),
            "'status'",
            id="status-enum-value",
        ),
        pytest.param(
            {"_meta": {"schemaVersion": _HUGE}, "documents": []},
            "schemaVersion",
            id="schema-version",
        ),
        pytest.param(
            _corpus_dict(id=_HUGE, tokens=[{"text": "t", "kind": "nope"}]),
            "'kind'",
            id="document-id",
        ),
        pytest.param(
            _corpus_dict(tokens=[], lines=[[_HUGE]]),
            "line 0 references token index",
            id="line-index",
        ),
    ],
)
def test_reader_error_messages_are_capped(data: dict[str, object], expected: str) -> None:
    """A 500,000-character value produced a 500,121-character ValueError, written to
    stderr in full by the CLI. The message must stay printable and still say what is
    wrong and where."""
    with pytest.raises(ValueError) as caught:
        Corpus.from_dict(data)

    message = str(caught.value)
    assert len(message) < _LIMIT, f"message is {len(message)} characters"
    assert expected in message
    assert _HUGE not in message


def test_capped_message_keeps_a_readable_prefix_of_the_value() -> None:
    """Truncation reports the value's beginning, so a real (short) mistake is unaffected
    and a long one is still identifiable."""
    with pytest.raises(ValueError) as caught:
        Corpus.from_dict(_corpus_dict(tokens=[{"text": "t", "kind": "wrd" + _HUGE}]))

    assert "'wrd" in str(caught.value)
    assert "..." in str(caught.value)


def test_short_values_are_quoted_in_full() -> None:
    """The cap applies to length, not to every message: a plausible typo reads exactly."""
    with pytest.raises(ValueError, match="'wrod', which is not one of"):
        Corpus.from_dict(_corpus_dict(tokens=[{"text": "t", "kind": "wrod"}]))


def test_unreadable_path_error_is_capped_and_still_guides(tmp_path: Path) -> None:
    """``from_json`` reports a name the OS refuses, and that name came from the caller."""
    with pytest.raises(ValueError) as caught:
        Corpus.from_json(tmp_path / ("x" * 400 + ".json"))

    message = str(caught.value)
    assert len(message) < _LIMIT, f"message is {len(message)} characters"
    assert "Corpus.from_dict" in message


# ── the readers still load every corpus this package ships ───────────────────


@pytest.mark.parametrize("name", ["lineara", "linearb", "cypriot", "cyprominoan", "greek"])
def test_bundled_corpora_round_trip_through_the_reader(name: str) -> None:
    """A stricter probe or a capped message must not change what loads."""
    original = aegean.load(name)
    restored = Corpus.from_json(original.to_json())

    assert len(restored) == len(original)
    assert sum(len(d.tokens) for d in restored) == sum(len(d.tokens) for d in original)
    assert restored.fingerprint() == original.fingerprint()
