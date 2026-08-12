"""Corpus reader and workbench importer: bounded messages, located alignment errors,
and the filename/JSON overlap.

Every message these guards inspect quotes untrusted file content back at a terminal or a
log, so each asserts both halves of the contract: the offending value is capped, and what
the reader needs to act on (the field, the document, the token, the guidance) survives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, SourceAlignment, Token, TokenKind
from aegean.io.workbench import from_workbench_export, to_workbench

# Far longer than any legitimate id, field name, or token: a single record of this shape
# was echoed whole (half a megabyte) by each site below.
_HUGE = "A" * 500_000
# Room for the guidance and the known-field list around the capped value; every message
# under test measured over 500,000 characters before the cap.
_LIMIT = 400


def _corpus_with_alignment() -> Corpus:
    source = "λόγος καί"
    first = SourceAlignment(
        document_id="HT 13", sentence_id="s1", source_token_id="HT 13:t0:0-5",
        original_text="λόγος", start_char=0, end_char=5,
        whitespace_before="", normalized_text="λόγος", normalization_ops=(),
    )
    second = SourceAlignment(
        document_id="HT 13", sentence_id="s1", source_token_id="HT 13:t1:6-9",
        original_text="καί", start_char=6, end_char=9,
        whitespace_before=" ", normalized_text="και", normalization_ops=("unicode:nfc",),
    )
    doc = Document(
        id="HT 13", script_id="greek",
        tokens=[
            Token("λόγος", TokenKind.WORD, position=0, alignment=first),
            Token("καί", TokenKind.WORD, position=1, alignment=second),
        ],
        lines=[[0, 1]],
        source_text=source,
    )
    return Corpus([doc], script_id="greek")


def _mutated_payload(mutate) -> str:
    payload = json.loads(_corpus_with_alignment().to_json())
    mutate(payload["documents"][0])
    return json.dumps(payload)


# ── bounded error text ─────────────────────────────────────────────────────────────


def test_from_records_caps_the_record_it_quotes_back() -> None:
    with pytest.raises(ValueError) as missing:
        Corpus.from_records([{"text": _HUGE}])
    message = str(missing.value)
    assert len(message) < _LIMIT
    assert _HUGE not in message
    assert "missing 'id'" in message
    # The record is still recognizable: its own key survives the cap.
    assert "'text'" in message

    with pytest.raises(ValueError) as empty:
        Corpus.from_records([{"id": _HUGE}])
    message = str(empty.value)
    assert len(message) < _LIMIT
    assert _HUGE not in message
    # The guidance is the point of the message and must never be the part that is cut.
    assert "'lines', 'words', or 'text'" in message
    assert "AAA" in message


def test_filter_caps_both_the_unknown_names_and_how_many_are_listed() -> None:
    corpus = Corpus.from_records([{"id": "X1", "text": "KU-RO 10"}])

    with pytest.raises(ValueError) as one:
        corpus.filter(**{_HUGE: 1})
    message = str(one.value)
    assert len(message) < _LIMIT
    assert _HUGE not in message
    # The known-field list is the actionable half and stays whole.
    for field in ("site", "period", "scribe", "findspot"):
        assert field in message

    with pytest.raises(ValueError) as many:
        corpus.filter(**{f"field_{i}": i for i in range(200)})
    message = str(many.value)
    assert len(message) < _LIMIT
    assert "and 195 more" in message
    assert "'field_0'" in message
    assert "'field_199'" not in message


def test_workbench_import_caps_the_record_it_quotes_back() -> None:
    with pytest.raises(ValueError) as excinfo:
        from_workbench_export([{"words": [_HUGE]}])
    message = str(excinfo.value)
    assert len(message) < _LIMIT
    assert _HUGE not in message
    assert "without an id" in message


def test_a_valid_record_is_never_truncated_into_a_wrong_error() -> None:
    """The cap is presentation only: a record that is merely large still loads."""
    corpus = Corpus.from_records([{"id": "X" * 5_000, "text": "KU-RO 10"}])
    assert corpus.documents[0].id == "X" * 5_000
    assert [t.text for t in corpus.documents[0].tokens] == ["KU-RO", "10"]


# ── alignment errors name their document and token ─────────────────────────────────


@pytest.mark.parametrize(
    ("mutate", "detail"),
    [
        (lambda tok: tok.update(alignment="nope"), "expected an object"),
        (
            lambda tok: tok.update(
                alignment={"document_id": "HT 13", "start_char": 0, "end_char": 5,
                           "normalization_ops": "unicode:nfc"}
            ),
            "normalization_ops must be a JSON array",
        ),
        (
            lambda tok: tok.update(
                alignment={"document_id": "HT 13", "start_char": "0", "end_char": 5}
            ),
            "start_char must be an integer",
        ),
        (
            lambda tok: tok.update(
                alignment={"document_id": "HT 13", "start_char": 0, "end_char": None}
            ),
            "end_char must be an integer",
        ),
        # JSON true decodes to a Python int subclass, and is still not an offset.
        (
            lambda tok: tok.update(
                alignment={"document_id": "HT 13", "start_char": True, "end_char": 5}
            ),
            "start_char must be an integer",
        ),
        (
            lambda tok: tok.update(
                alignment={"document_id": "HT 13", "source_token_id": "HT 13:t0:0-5",
                           "original_text": "λόγος", "start_char": 5, "end_char": 2}
            ),
            "end_char must be greater than or equal to start_char",
        ),
    ],
)
def test_malformed_alignment_names_the_document_and_token(mutate, detail: str) -> None:
    payload = _mutated_payload(lambda doc: mutate(doc["tokens"][0]))
    with pytest.raises(ValueError) as excinfo:
        Corpus.from_json(payload)
    message = str(excinfo.value)
    assert "malformed token alignment" in message
    assert "document 'HT 13', token 0" in message
    assert detail in message


def test_the_reported_token_index_is_the_offending_one() -> None:
    payload = _mutated_payload(
        lambda doc: doc["tokens"][1].update(alignment={"start_char": 0, "end_char": "5"})
    )
    with pytest.raises(ValueError, match=r"document 'HT 13', token 1"):
        Corpus.from_json(payload)


def test_malformed_reader_fields_are_all_value_errors() -> None:
    """One `except ValueError` covers a malformed corpus file, alignment included."""
    for mutate in (
        lambda doc: doc["tokens"][0].update(alignment="nope"),
        lambda doc: doc["tokens"][0].update(
            alignment={"start_char": 0, "end_char": 5, "normalization_ops": "unicode:nfc"}
        ),
        lambda doc: doc["tokens"][0].update(alignment={"start_char": "0", "end_char": 5}),
        lambda doc: doc["tokens"][0].update(form_state="nope"),
        lambda doc: doc.update(source_text=17),
        lambda doc: doc["tokens"][0].update(kind="not-a-kind"),
    ):
        with pytest.raises(ValueError):
            Corpus.from_json(_mutated_payload(mutate))


def test_a_valid_alignment_still_round_trips() -> None:
    original = _corpus_with_alignment()
    restored = Corpus.from_json(original.to_json())
    assert restored.fingerprint() == original.fingerprint()
    alignment = restored.documents[0].tokens[1].alignment
    assert alignment is not None
    assert (alignment.start_char, alignment.end_char) == (6, 9)
    assert alignment.normalization_ops == ("unicode:nfc",)


# ── the filename/JSON overlap in the workbench importer ────────────────────────────


@pytest.mark.parametrize("name", ["[export].json", "{export}.json", "[a][b].json"])
def test_workbench_reads_a_file_whose_name_opens_like_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    records = to_workbench(
        Corpus.from_records(
            [{"id": "HT 13", "text": "KU-RO 10", "meta": {"site": "HT"}}], script_id="lineara"
        )
    )
    (tmp_path / name).write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    # The name has to reach the reader relative: an absolute path opens with a drive or a
    # separator and never takes the JSON probe, so it would not exercise this at all.
    monkeypatch.chdir(tmp_path)
    assert name.startswith(("[", "{"))

    corpus = from_workbench_export(name)
    assert [d.id for d in corpus] == ["HT 13"]
    assert [t.text for t in corpus.documents[0].tokens] == ["KU-RO", "10"]
    assert corpus.documents[0].meta.site == "HT"


def test_a_malformed_payload_still_reports_its_own_decode_error() -> None:
    """The path fallback must not mask a real JSON error: no such file exists."""
    with pytest.raises(json.JSONDecodeError):
        from_workbench_export('[{"id": "HT 13",')
    with pytest.raises(json.JSONDecodeError):
        from_workbench_export('{"inscriptions":')


def test_an_unusable_name_does_not_mask_the_decode_error() -> None:
    """A payload holding a NUL byte cannot name a file; the caller's error survives."""
    with pytest.raises(json.JSONDecodeError):
        from_workbench_export('[{"id": "HT\x0013",')


def test_json_strings_and_paths_both_still_load(tmp_path: Path) -> None:
    records = [{"id": "HT 13", "words": ["KU-RO", "10"], "site": "HT"}]
    text = json.dumps(records, ensure_ascii=False)
    assert [d.id for d in from_workbench_export(text)] == ["HT 13"]
    assert [d.id for d in from_workbench_export("﻿" + text)] == ["HT 13"]

    path = tmp_path / "export.json"
    path.write_text(text, encoding="utf-8")
    assert [d.id for d in from_workbench_export(path)] == ["HT 13"]
    assert [d.id for d in from_workbench_export(str(path))] == ["HT 13"]

    with pytest.raises(FileNotFoundError):
        from_workbench_export(str(tmp_path / "absent.json"))
