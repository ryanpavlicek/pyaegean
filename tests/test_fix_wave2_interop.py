"""CoNLL-U reading and writing contracts for the interoperability envelope.

Four behaviors are pinned here:

* ``from_conllu(strict=True)`` validates the CoNLL-U it is given whether or not the
  file carries a pyaegean sidecar, while pyaegean's own projection of a partly
  analyzed document still round-trips.
* ``# sent_id`` is optional in CoNLL-U, so a file without it is read and given the
  stable positional identifiers the envelope needs to key its metadata.
* A leading UTF-8 byte-order mark is an encoding marker, not the first character of
  the first comment line.
* An emitted sidecar carries no literal U+2028/U+2029/U+0085, so a consumer that
  splits the file with ``str.splitlines`` still sees exactly one sidecar line.

The CoNLL-U model is shared with the evaluation path, so the gold-fold reading
invariants are pinned alongside them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegean.greek.ud import (
    UDDocument,
    UDSentence,
    UDToken,
    load_conllu,
    load_conllu_document,
)
from aegean.core.model import SourceAlignment
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import TokenRecord
from aegean.io.interop import (
    MAX_SIDECAR_BYTES,
    SIDECAR_COMMENT_PREFIX,
    InteropSchemaError,
    _native_signature,
    _partition_sidecar_comments,
    encode_sidecar,
    from_conllu,
    from_token_records,
    from_ud_document,
    to_conllu,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"

# One valid sentence, two words, with a final blank line as CoNLL-U requires.
VALID = (
    "# sent_id = s1\n"
    "# text = de x\n"
    "1\tde\tde\tADP\t_\t_\t0\troot\t_\t_\n"
    "2\tx\tx\tNOUN\t_\t_\t1\tdep\t_\t_\n"
    "\n"
)
# The same content without any "# sent_id" comment, which the format permits.
NO_SENT_ID = (
    "# text = de x\n"
    "1\tde\tde\tADP\t_\t_\t0\troot\t_\t_\n"
    "2\tx\tx\tNOUN\t_\t_\t1\tdep\t_\t_\n"
    "\n"
)
BOM = "\ufeff"
SEPARATORS = ["\u2028", "\u2029", "\u0085"]


def _sidecar_file(native: str) -> str:
    """A hand-built file whose sidecar is bound to exactly this native text."""
    document = from_ud_document(
        load_conllu_document(native, strict=False), source_text="de x"
    )
    sidecar = encode_sidecar(
        document, target="conllu", native_signature=_native_signature(native)
    )
    return SIDECAR_COMMENT_PREFIX + sidecar + "\n" + native


def _partial_records() -> list[TokenRecord]:
    """One analyzed word and one that carries no dependency: a partial analysis."""
    return [
        TokenRecord(
            0, 1, "de", "ADP", "de", LemmaSource.IDENTITY,
            alignment=SourceAlignment("d", "s1", "a", "de", 0, 2, "", "de"),
            head=None, relation=None,
        ),
        TokenRecord(
            0, 2, "x", "NOUN", "x", LemmaSource.IDENTITY,
            alignment=SourceAlignment("d", "s1", "b", "x", 3, 4, " ", "x"),
            head=1, relation="dep",
        ),
    ]


# --- strict validation is not switched off by a sidecar ------------------------


@pytest.mark.parametrize(
    "native,message",
    [
        # No final blank line: valid to read leniently, rejected by strict CoNLL-U.
        (VALID[:-1], "final blank line"),
        # A comment between data rows.
        (
            "# sent_id = s1\n"
            "1\tde\tde\tADP\t_\t_\t0\troot\t_\t_\n"
            "# late\n"
            "2\tx\tx\tNOUN\t_\t_\t1\tdep\t_\t_\n"
            "\n",
            "comments must precede",
        ),
        # An empty column where CoNLL-U requires a placeholder.
        (VALID.replace("\tADP\t_\t_\t0", "\tADP\t\t_\t0"), "empty CoNLL-U column"),
        # A malformed MISC entry.
        (VALID.replace("1\tdep\t_\t_", "1\tdep\t_\t=x"), "MISC key"),
    ],
    ids=["missing-final-blank-line", "comment-between-rows", "empty-column", "bad-misc"],
)
def test_strict_validates_the_conllu_even_when_a_sidecar_is_present(
    native: str, message: str
) -> None:
    raw = _sidecar_file(native)
    assert SIDECAR_COMMENT_PREFIX in raw

    with pytest.raises(InteropSchemaError, match=message):
        from_conllu(raw, strict=True)

    # The same malformation is reported for the bare CoNLL-U, and lenient reading of
    # the sidecar file still succeeds: only validation changed, not what is readable.
    with pytest.raises(InteropSchemaError, match=message):
        from_conllu(native, strict=True)
    assert from_conllu(raw, strict=False).value.source_text == "de x"


def test_strict_accepts_a_wellformed_sidecar_file() -> None:
    restored = from_conllu(_sidecar_file(VALID), strict=True)
    assert restored.value.source_text == "de x"
    assert [s.sent_id for s in restored.value.ud_document.sentences] == ["s1"]


def test_partly_analyzed_export_round_trips_under_the_default_strict_read() -> None:
    # A document analyzed in part projects a sentence whose words do not all carry a
    # HEAD.  That is pyaegean's own output, so its own reader must accept it.
    document = from_token_records(
        _partial_records(), source_text="de x", document_id="d"
    )
    exported = to_conllu(document)
    assert exported.sidecar is not None
    _sidecars, native = _partition_sidecar_comments(exported.value)
    assert "\t_\t_\t_\t_\n" in native  # word 1 really is unannotated

    restored = from_conllu(exported.value)  # default strict=True
    assert restored.value.token_metadata[("s1", 1)].head is None
    assert restored.value.token_metadata[("s1", 2)].head == 1
    assert to_conllu(restored.value).value == exported.value


def test_partial_dependencies_stay_invalid_in_a_plain_conllu_file() -> None:
    # The allowance belongs to the envelope's projection, not to CoNLL-U at large.
    native = VALID.replace("1\tde\tde\tADP\t_\t_\t0\troot", "1\tde\tde\tADP\t_\t_\t_\t_")
    with pytest.raises(InteropSchemaError, match="mixes annotated and unannotated"):
        from_conllu(native, strict=True)
    assert load_conllu_document(native, strict=False).sentences[0].tokens[0].head is None


def test_partial_dependency_allowance_is_off_by_default_in_the_shared_model() -> None:
    native = VALID.replace("1\tde\tde\tADP\t_\t_\t0\troot", "1\tde\tde\tADP\t_\t_\t_\t_")
    with pytest.raises(ValueError, match="mixes annotated and unannotated"):
        load_conllu_document(native, strict=True)
    document = load_conllu_document(
        native, strict=True, allow_partial_dependencies=True
    )
    assert [token.head for token in document.sentences[0].tokens] == [None, 1]


def test_partial_allowance_does_not_excuse_other_defects() -> None:
    # A cycle, an unknown HEAD, and a malformed row are still rejected with the
    # allowance switched on.
    for native, message in (
        (
            "1\ta\ta\tX\t_\t_\t0\troot\t_\t_\n"
            "2\tb\tb\tX\t_\t_\t3\tdep\t_\t_\n"
            "3\tc\tc\tX\t_\t_\t2\tdep\t_\t_\n"
            "\n",
            "cycle",
        ),
        (
            "1\ta\ta\tX\t_\t_\t9\tdep\t_\t_\n2\tb\tb\tX\t_\t_\t_\t_\t_\t_\n\n",
            "invalid basic HEAD",
        ),
        ("1\ta\ta\tX\t_\t_\t0\troot\t_\n\n", "10 tab-separated"),
    ):
        with pytest.raises(ValueError, match=message):
            load_conllu_document(
                native, strict=True, allow_partial_dependencies=True
            )


# --- an omitted "# sent_id" is synthesized, not rejected -----------------------


def test_file_without_sent_id_is_read_with_stable_positional_ids() -> None:
    raw = NO_SENT_ID + NO_SENT_ID
    result = from_conllu(raw)  # default strict=True

    sentences = result.value.ud_document.sentences
    assert [s.sent_id for s in sentences] == ["input:sentence:0", "input:sentence:1"]
    assert [[t.form for t in s.tokens] for s in sentences] == [["de", "x"], ["de", "x"]]
    # Stable: the identifiers come from position, not from a counter or a random key.
    assert [s.sent_id for s in from_conllu(raw).value.ud_document.sentences] == [
        "input:sentence:0",
        "input:sentence:1",
    ]


def test_synthesized_ids_fill_only_the_gaps_and_key_the_envelope() -> None:
    raw = VALID + NO_SENT_ID
    document = from_conllu(raw).value
    assert [s.sent_id for s in document.ud_document.sentences] == [
        "s1",
        "input:sentence:1",
    ]
    # The synthesized identifier is usable as an envelope key.
    exported = to_conllu(
        from_ud_document(document.ud_document, source_text="de x de x")
    )
    assert exported.sidecar is not None
    payload = json.loads(exported.sidecar.split(SIDECAR_COMMENT_PREFIX)[-1])["payload"]
    assert "input:sentence:1" in payload["conllu"]


def test_a_file_whose_own_id_collides_with_a_synthesized_one_is_a_clean_error() -> None:
    raw = VALID.replace("# sent_id = s1", "# sent_id = input:sentence:1") + NO_SENT_ID
    with pytest.raises(InteropSchemaError, match="duplicate sentence ID"):
        from_conllu(raw)


def test_synthesized_id_survives_export_and_reimport() -> None:
    # Whole path: read a file without sent_id, export it, read the exported bytes back.
    first = from_conllu(BOM + NO_SENT_ID).value
    exported = to_conllu(first).value
    assert "# sent_id = input:sentence:0\n" in exported

    second = from_conllu(exported).value

    assert [s.sent_id for s in second.ud_document.sentences] == ["input:sentence:0"]
    assert [t.form for t in second.ud_document.sentences[0].tokens] == ["de", "x"]
    # Reading its own output changes nothing further: the identifier is now written.
    assert to_conllu(second).value == exported


def test_sent_id_written_in_the_file_is_never_rewritten() -> None:
    document = from_conllu(VALID).value
    assert document.ud_document.sentences[0].sent_id == "s1"
    assert document.ud_document.dumps() == VALID


# --- a byte-order mark is an encoding marker -----------------------------------


@pytest.mark.parametrize("strict", [True, False], ids=["strict", "lenient"])
@pytest.mark.parametrize("as_path", [True, False], ids=["path", "string"])
def test_byte_order_mark_does_not_hide_the_first_comment(
    tmp_path: Path, strict: bool, as_path: bool
) -> None:
    source: str | Path
    if as_path:
        source = tmp_path / "bom.conllu"
        Path(source).write_text(BOM + VALID, encoding="utf-8", newline="")
    else:
        source = BOM + VALID

    document = from_conllu(source, strict=strict).value

    sentence = document.ud_document.sentences[0]
    assert sentence.sent_id == "s1"  # not swallowed by the BOM
    assert sentence.text == "de x"
    assert [token.form for token in sentence.tokens] == ["de", "x"]
    # Identical to the same file without a mark: the BOM carries no content.
    assert document.ud_document.dumps() == from_conllu(
        VALID, strict=strict
    ).value.ud_document.dumps()


def test_byte_order_mark_is_stripped_by_the_shared_conllu_loader(tmp_path: Path) -> None:
    path = tmp_path / "bom.conllu"
    path.write_text(BOM + VALID, encoding="utf-8", newline="")

    assert load_conllu(path)[0].sent_id == "s1"
    assert load_conllu(BOM + VALID)[0].sent_id == "s1"
    assert load_conllu_document(path, strict=True).sentences[0].sent_id == "s1"
    assert load_conllu_document(path).dumps() == load_conllu_document(VALID).dumps()


@pytest.mark.parametrize("as_path", [True, False], ids=["path", "string"])
def test_byte_order_mark_before_a_sidecar_does_not_lose_the_envelope(
    tmp_path: Path, as_path: bool
) -> None:
    # The sidecar is the first line, so a mark in front of it would leave the reader
    # seeing an ordinary comment and silently dropping every envelope field.
    document = from_ud_document(
        load_conllu_document(VALID, strict=False), source_text="de x"
    )
    exported = to_conllu(document)
    assert exported.sidecar is not None
    source: str | Path
    if as_path:
        source = tmp_path / "bom-sidecar.conllu"
        Path(source).write_text(BOM + exported.value, encoding="utf-8", newline="")
    else:
        source = BOM + exported.value

    restored = from_conllu(source)

    assert restored.sidecar == exported.sidecar
    assert restored.value.source_text == "de x"


def test_a_mark_inside_the_document_is_left_alone() -> None:
    # Only a leading mark is an encoding marker; one inside a form is data.
    raw = VALID.replace("\tde\tde\t", f"\t{BOM}de\tde\t", 1)
    token = from_conllu(raw).value.ud_document.sentences[0].tokens[0]
    assert token.form == BOM + "de"


# --- the writer emits no literal line separator --------------------------------


@pytest.mark.parametrize("separator", SEPARATORS, ids=["U+2028", "U+2029", "U+0085"])
def test_emitted_sidecar_escapes_unicode_line_separators(separator: str) -> None:
    source = "de" + separator + "x"
    document = from_ud_document(
        load_conllu_document(VALID, strict=False), source_text=source
    )
    exported = to_conllu(document)
    assert exported.sidecar is not None

    # Nothing a naive line splitter can trip over survives in the emitted text.
    assert separator not in exported.value
    assert separator not in exported.sidecar
    # A third-party consumer splitting on Unicode boundaries sees one sidecar line.
    lines = exported.value.splitlines()
    assert sum(line.startswith(SIDECAR_COMMENT_PREFIX) for line in lines) == 1
    assert lines[0].startswith(SIDECAR_COMMENT_PREFIX)
    assert not any(
        line.startswith(SIDECAR_COMMENT_PREFIX) for line in lines[1:]
    )
    # The escapes are JSON, so the exact character survives the round trip.
    assert json.loads(lines[0][len(SIDECAR_COMMENT_PREFIX):])["payload"][
        "source_text"
    ] == source
    restored = from_conllu(exported.value)
    assert restored.value.source_text == source
    assert to_conllu(restored.value).value == exported.value


@pytest.mark.parametrize("separator", SEPARATORS, ids=["U+2028", "U+2029", "U+0085"])
def test_a_sidecar_written_with_literal_separators_is_still_read(
    separator: str,
) -> None:
    # Reading the older, unescaped form must not regress.
    source = "de" + separator + "x"
    exported = to_conllu(
        from_ud_document(
            load_conllu_document(VALID, strict=False), source_text=source
        )
    )
    escape = "\\u%04x" % ord(separator)
    literal = exported.value.replace(escape, separator)
    assert separator in literal

    assert from_conllu(literal).value.source_text == source


def test_control_characters_json_already_escapes_are_untouched() -> None:
    # C0 characters are escaped by JSON itself; the writer adds nothing for them.
    source = "de\u000bx\u000cy\u001ez"
    exported = to_conllu(
        from_ud_document(
            load_conllu_document(VALID, strict=False), source_text=source
        )
    )
    assert exported.sidecar is not None
    assert all(character not in exported.value for character in "\u000b\u000c\u001e")
    assert from_conllu(exported.value).value.source_text == source


def test_writer_still_obeys_its_reader_after_escaping() -> None:
    # Escaping expands each separator from three bytes to six, so the size bound is
    # re-checked on the emitted text rather than on the unescaped form.
    oversized = "\u2028" * (MAX_SIDECAR_BYTES // 4)
    document = from_ud_document(
        load_conllu_document(VALID, strict=False), source_text=oversized
    )
    with pytest.raises(InteropSchemaError, match="exceeds maximum size"):
        to_conllu(document)


# --- the shared evaluation model is unchanged ----------------------------------


def _source_text(path: Path) -> str:
    """The file's text with its line endings as written.

    ``dumps()`` returns the source untouched, so comparing against it needs a read
    that performs no newline translation. Decoding the bytes is that read on every
    supported interpreter; ``Path.read_text``'s ``newline`` argument is 3.13 and up."""
    return path.read_bytes().decode("utf-8")


def test_gold_fold_reading_is_unchanged_by_the_interop_contracts() -> None:
    # The CoNLL-U model is shared with evaluation.  Pin the fixture fold exactly:
    # counts, every column of every row, and both dump modes.
    raw = _source_text(FIXTURE)
    document = load_conllu_document(FIXTURE)
    sentences = document.sentences

    assert [s.sent_id for s in sentences] == ["sample.tb.xml@1", "sample.tb.xml@2"]
    assert [len(s.tokens) for s in sentences] == [5, 3]
    first = sentences[0]
    assert [t.form for t in first.tokens] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]
    assert [t.head for t in first.tokens] == [3, 3, 0, 5, 3]
    assert [t.deprel for t in first.tokens] == ["case", "obl", "root", "det", "nsubj"]
    assert first.multiword_tokens[0].id == "4-5"
    assert first.empty_nodes[0].id == "5.1"
    # Reading returns the source bytes untouched, and the fold parses identically
    # whether or not it is read through the strict path.
    assert document.dumps() == raw
    assert load_conllu_document(FIXTURE, strict=False).dumps() == raw
    assert load_conllu(FIXTURE)[0].tokens == first.tokens


def test_gold_fold_sentences_survive_the_interop_envelope() -> None:
    document = from_conllu(FIXTURE, strict=False).value
    assert [s.sent_id for s in document.ud_document.sentences] == [
        "sample.tb.xml@1",
        "sample.tb.xml@2",
    ]
    assert document.ud_document.dumps() == _source_text(FIXTURE)


# --- hostile input -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        BOM + "not conllu at all",
        BOM + "1\tde\n",
        "# sent_id = s1\n1\tde\tde\tADP\t_\t_\t0\troot\t_\t_\n# late comment\n\n",
        SIDECAR_COMMENT_PREFIX + "{}\n" + VALID,
        SIDECAR_COMMENT_PREFIX + "not json\n" + VALID,
    ],
    ids=["prose", "short-row", "comment-after-rows", "empty-sidecar", "unparsable-sidecar"],
)
def test_malformed_input_raises_a_typed_error(raw: str) -> None:
    with pytest.raises(InteropSchemaError):
        from_conllu(raw, strict=True)


def test_non_text_source_is_rejected_by_type() -> None:
    with pytest.raises(InteropSchemaError):
        from_conllu(b"# sent_id = s1\n")  # type: ignore[arg-type]


def test_empty_document_reads_as_no_sentences() -> None:
    assert from_conllu("").value.ud_document.sentences == ()
    assert from_conllu(BOM).value.ud_document.sentences == ()


def test_synthesized_ids_do_not_disturb_a_document_built_in_memory() -> None:
    native = UDDocument(
        (
            UDSentence(
                "kept",
                "de",
                (UDToken(1, "de", "de", "ADP", "_", "_", 0, "root"),),
            ),
        )
    )
    document = from_ud_document(native, source_text="de")
    assert document.ud_document is native
