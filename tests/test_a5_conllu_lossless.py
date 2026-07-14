"""Focused A5 tests for lossless CoNLL-U structure and word projection."""

from __future__ import annotations

from dataclasses import replace

import pytest

from aegean.greek.ud import (
    UDNodeID,
    UDMiscEntry,
    UDSentence,
    UDToken,
    UnsupportedUDStructureError,
    dump_conllu,
    dumps_conllu,
    load_conllu,
    load_conllu_document,
    loads_conllu,
    pipeline_conllu,
    write_conllu,
)


RAW = (
    "# sent_id = a5\r\n"
    "# text = AB\r\n"
    "1-2\tAB\t_\t_\t_\t_\t_\t_\t_\tMWT=Yes\r\n"
    "1\tA\ta\tNOUN\t_\t_\t0\troot\t0:root\tSpaceAfter=No|Note=x|Note=y\r\n"
    "2\tB\tb\tNOUN\t_\t_\t1\tdep\t_\t_\r\n"
    "2.1\tC\tc\tX\t_\t_\t_\t_\t1:dep\t_\r\n"
    "\r\n"
)


def test_lossless_document_and_path_roundtrip_preserve_newlines(tmp_path) -> None:
    document = load_conllu_document(RAW, strict=True)
    sentence = document.sentences[0]

    assert document.dumps() == RAW
    assert dumps_conllu(document.sentences) == RAW
    assert sentence.items[0].text == "# sent_id = a5"
    assert sentence.multiword_tokens[0].misc[0].key == "MWT"
    assert sentence.empty_nodes[0].deps[0].head.raw == "1"
    assert sentence.tokens[0].misc[1].key == "Note"

    destination = tmp_path / "roundtrip.conllu"
    write_conllu(document, destination)
    assert destination.read_bytes().decode("utf-8") == RAW

    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"
    fixture_text = fixture.read_bytes().decode("utf-8")
    assert dumps_conllu(load_conllu(fixture)) == fixture_text
    assert load_conllu(fixture)[1].tokens[1].misc[0].key == "SpaceAfter"


def test_projection_uses_word_ordinals_and_records_omissions() -> None:
    sentence = load_conllu(RAW)[0]
    projection = sentence.projection

    assert projection.ordinal_to_id == ((1, 1), (2, 2))
    assert projection.word_ids == (1, 2)
    assert projection.omitted_ranges == ("1-2",)
    assert projection.omitted_empty_nodes == ("2.1",)
    assert projection.enhanced_dependencies_present
    assert UDNodeID.parse("0.1").kind == "empty"
    assert UDNodeID.parse("0.1").major == 0


def test_lenient_retains_opaque_rows_and_strict_errors_are_line_aware() -> None:
    malformed = "# sent_id = x\nnot-an-id\tbad\n1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    sentence = load_conllu(malformed)[0]
    assert len(sentence.tokens) == 1
    assert sentence.rows[0].id == "not-an-id"

    with pytest.raises(ValueError, match=r"line 2"):
        load_conllu(malformed, strict=True)

    with pytest.raises(ValueError, match=r"line 1.*ID 0"):
        load_conllu("0\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n", strict=True)


def test_pipeline_projects_structure_or_reports_cleanly() -> None:
    sentence = load_conllu(RAW)[0]
    projected = pipeline_conllu([sentence])
    assert "1-2\t" not in projected
    assert "2.1\t" not in projected
    assert projected.count("\n1\t") == 1
    assert projected.count("\n2\t") == 1

    with pytest.raises(UnsupportedUDStructureError, match="complete predictive"):
        pipeline_conllu([sentence], on_unsupported="error")


def test_canonical_output_is_deterministic_for_constructed_sentence() -> None:
    token = UDToken(1, "a", "_", "NOUN", "_", "_", 0, "root")
    sentence = UDSentence("constructed", "a", (token,))
    expected = "# sent_id = constructed\n# text = a\n1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    assert dump_conllu([sentence], canonical=True) == expected
    changed = replace(sentence, tokens=(replace(token, form="b"),))
    assert dump_conllu([changed], canonical=True).splitlines()[2].split("\t")[1] == "b"


def test_canonical_output_updates_standard_metadata_comments() -> None:
    sentence = load_conllu(
        "# sent_id = old\n# text = old text\n# note = retained\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    )[0]
    changed = replace(sentence, sent_id="new", text="new text")
    output = dump_conllu([changed], canonical=True)
    assert "# sent_id = new\n" in output
    assert "# text = new text\n" in output
    assert "# note = retained\n" in output
    assert "# sent_id = old" not in output


def test_iterable_roundtrip_keeps_document_edge_comments() -> None:
    raw = (
        "# preamble\n\n"
        "# sent_id = one\n1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
        "# trailer\n\n"
    )
    assert dumps_conllu(loads_conllu(raw)) == raw


def _strict_block(rows: str) -> str:
    return "# sent_id = invalid\n" + rows + "\n"


@pytest.mark.parametrize(
    "rows",
    [
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n3\tc\t_\tNOUN\t_\t_\t1\tdep\t_\t_",
        "2\tb\t_\tNOUN\t_\t_\t0\troot\t_\t_\n1\ta\t_\tNOUN\t_\t_\t2\tdep\t_\t_",
        "1-2\tab\t_\t_\t_\t_\t_\t_\t_\t_\n2-3\tbc\t_\t_\t_\t_\t_\t_\t_\t_\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n"
        "3\tc\t_\tNOUN\t_\t_\t1\tdep\t_\t_",
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n1-2\tab\t_\t_\t_\t_\t_\t_\t_\t\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_",
        "1-3\tabc\t_\t_\t_\t_\t_\t_\t_\t\n1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_",
        "2.1\tC\t_\tX\t_\t_\t_\t_\t1:dep\t_\n1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_",
        "1.1\tC\t_\tX\t_\t_\t_\t_\t_\t_",
        "1-2\tab\t_\t_\t_\t_\t0\t_\t_\t_\n1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_",
        "1.1\tC\t_\tX\t_\t_\t_\tdep\t1:dep\t_",
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t9:dep\t_",
    ],
)
def test_strict_validator_rejects_structural_and_reference_defects(rows: str) -> None:
    with pytest.raises(ValueError):
        load_conllu(_strict_block(rows), strict=True)


def test_duplicate_misc_is_ordered_and_default_pipeline_stays_word_only() -> None:
    sentence = load_conllu(RAW, strict=True)[0]
    assert [entry.key for entry in sentence.tokens[0].misc] == ["SpaceAfter", "Note", "Note"]
    projected = pipeline_conllu([sentence])
    rows = [line.split("\t") for line in projected.splitlines() if line and not line.startswith("#")]
    assert [row[0] for row in rows] == ["1", "2"]
    assert all(row[8:] == ["_", "_"] for row in rows)


def test_strict_accepts_official_typo_feature_on_multiword_row() -> None:
    block = (
        "1-2\tab\t_\t_\t_\tTypo=Yes\t_\t_\t_\t_\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n\n"
    )
    assert load_conllu(block, strict=True)[0].multiword_tokens[0].form == "ab"


@pytest.mark.parametrize(
    "rows, message",
    [
        (
            "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
            "1.2\tx\t_\tX\t_\t_\t_\t_\t1:dep\t_\n"
            "1.1\ty\t_\tX\t_\t_\t_\t_\t1:dep\t_\n",
            "ordered and sequential",
        ),
        (
            "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
            "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n"
            "1.1\tx\t_\tX\t_\t_\t_\t_\t1:dep\t_\n",
            "must precede word 2",
        ),
    ],
)
def test_strict_rejects_misordered_empty_nodes_with_line_context(
    rows: str, message: str
) -> None:
    with pytest.raises(ValueError, match=rf"{message}.*line"):
        load_conllu(rows + "\n", strict=True)


def test_strict_requires_comment_preamble_and_final_blank_line() -> None:
    no_separator = "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
    with pytest.raises(ValueError, match=r"line 1.*final blank"):
        load_conllu(no_separator, strict=True)

    late_comment = (
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "# late\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n\n"
    )
    with pytest.raises(ValueError, match=r"line 2.*comments must precede"):
        load_conllu(late_comment, strict=True)


def test_strict_cross_row_errors_include_source_line() -> None:
    with pytest.raises(ValueError, match=r"HEAD 99.*line 1"):
        load_conllu("1\ta\t_\tNOUN\t_\t_\t99\troot\t_\t_\n\n", strict=True)


def test_strict_requires_multiword_row_immediately_before_its_words() -> None:
    rows = (
        "1-2\tab\t_\t_\t_\t_\t_\t_\t_\t_\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "3-4\tcd\t_\t_\t_\t_\t_\t_\t_\t_\n"
        "2\tb\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n"
        "3\tc\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n"
        "4\td\t_\tNOUN\t_\t_\t1\tdep\t_\t_\n\n"
    )
    with pytest.raises(ValueError, match=r"immediately precede.*line 3"):
        load_conllu(rows, strict=True)


def test_complete_prediction_rejects_lenient_opaque_rows() -> None:
    sentence = load_conllu(
        "# sent_id = opaque\nnot-an-id\tbad\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    )[0]
    with pytest.raises(UnsupportedUDStructureError, match="opaque"):
        pipeline_conllu([sentence], on_unsupported="error")


def test_changed_typed_annotations_do_not_reuse_stale_raw_columns() -> None:
    sentence = load_conllu(RAW)[0]
    changed_token = replace(sentence.tokens[0], misc=(UDMiscEntry("Changed", "yes"),))
    changed = replace(sentence, tokens=(changed_token, *sentence.tokens[1:]))
    output = dump_conllu([changed], canonical=True)
    first_row = next(line for line in output.splitlines() if line.startswith("1\t"))
    assert first_row.split("\t")[-1] == "Changed=yes"
