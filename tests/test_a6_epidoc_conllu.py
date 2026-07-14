"""A6 documentary-form journeys for EpiDoc and CoNLL-U adapters."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from aegean.core.model import (
    Document,
    FormSegment,
    ReadingStatus,
    SourceMarkupRef,
    Token,
    TokenFormState,
    TokenKind,
)
from aegean.greek.ud import (
    UDMultiwordToken,
    UDEmptyNode,
    dump_conllu,
    load_conllu,
    load_conllu_document,
    pipeline_conllu,
)
from aegean.io.epidoc import read_epidoc, to_epidoc


_FIXTURES = Path(__file__).parent / "fixtures" / "a6"


def _strict_conllu_fixture() -> str:
    """Return the fixture with the format-required final sentence separator."""

    raw = (_FIXTURES / "structure.conllu").read_bytes().decode("utf-8")
    assert raw.endswith("\n") and not raw.endswith("\n\n")
    return raw + "\n"


def test_epidoc_choices_and_partial_apparatus_are_typed() -> None:
    document = read_epidoc(_FIXTURES / "choices.xml")[0]
    assert [token.text for token in document.tokens] == ["λόγος", "ἔχει", "δραχμάς", "Μουσαίους"]

    regularized = document.tokens[0].form_state
    assert regularized is not None
    assert regularized.diplomatic == "λογος"
    assert regularized.regularized == "λόγος"
    assert regularized.model_input is None
    assert regularized.segments[0].source_ref is not None
    assert regularized.segments[0].source_ref.tag == "reg"

    corrected = document.tokens[1].form_state
    assert corrected is not None
    assert corrected.diplomatic == "εχει"
    assert corrected.regularized == "ἔχει"

    expanded = document.tokens[2].form_state
    assert expanded is not None
    assert expanded.diplomatic == "δρ"
    assert expanded.regularized == "δραχμάς"

    damaged = document.tokens[3]
    assert damaged.status is ReadingStatus.LOST
    assert damaged.form_state is not None
    assert [(segment.text, segment.status) for segment in damaged.form_state.segments] == [
        ("Μου", ReadingStatus.CERTAIN),
        ("σαίου", ReadingStatus.RESTORED),
        ("ς", ReadingStatus.UNCLEAR),
        ("", ReadingStatus.LOST),
    ]
    assert [segment.source_ref.tag for segment in damaged.form_state.segments[1:] if segment.source_ref] == [
        "supplied", "unclear", "gap"
    ]
    paths = [
        segment.source_ref.path
        for segment in damaged.form_state.segments
        if segment.source_ref is not None
    ]
    assert len(paths) == len(set(paths))


@pytest.mark.parametrize(
    ("expansion", "expected"),
    [("δραχ<ex>μάς</ex>", "δραχμάς"), ("<abbr>δρ</abbr><ex>αχμάς</ex>", "δραχμάς")],
)
def test_epidoc_expansion_keeps_full_selected_form(
    tmp_path: Path, expansion: str, expected: str,
) -> None:
    path = tmp_path / "expansion.xml"
    path.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        f'<div type="edition"><ab><w><choice><expan>{expansion}</expan>'
        '<abbr>δρ</abbr></choice></w></ab></div></body></text></TEI>',
        encoding="utf-8",
    )
    token = read_epidoc(path)[0].tokens[0]
    assert token.text == expected
    assert token.form_state is not None
    assert token.form_state.regularized == expected
    assert token.form_state.diplomatic == "δρ"


def test_epidoc_state_semantically_roundtrips_without_source_byte_claim(tmp_path: Path) -> None:
    source = read_epidoc(_FIXTURES / "choices.xml")[0]
    output = tmp_path / "roundtrip.xml"
    output.write_text(to_epidoc(source), encoding="utf-8")
    back = read_epidoc(output)[0]

    assert [(token.text, token.status) for token in back.tokens] == [
        (token.text, token.status) for token in source.tokens
    ]
    for before, after in zip(source.tokens, back.tokens, strict=True):
        assert after.form_state is not None and before.form_state is not None
        assert after.form_state.diplomatic == before.form_state.diplomatic
        assert after.form_state.regularized == before.form_state.regularized
        assert [(segment.text, segment.status, segment.source_ref.tag if segment.source_ref else None)
                for segment in after.form_state.segments] == [
            (segment.text, segment.status, segment.source_ref.tag if segment.source_ref else None)
            for segment in before.form_state.segments
        ]
    assert back.source_text is None


def test_epidoc_writer_uses_typed_state_and_preserves_source_attributes(
    tmp_path: Path,
) -> None:
    ref = SourceMarkupRef(
        "ed",
        "supplied[1]",
        "supplied",
        (("reason", "lost"), ("resp", "#editor"), ("{urn:test}evidence", "visible")),
    )
    state = TokenFormState(
        diplomatic="λογος",
        regularized="λόγος",
        segments=(FormSegment("λόγος", ReadingStatus.RESTORED, ref),),
    )
    document = Document(
        "d",
        "greek",
        [Token("display-only", TokenKind.WORD, status=ReadingStatus.RESTORED, form_state=state)],
        [[0]],
    )
    xml = to_epidoc(document)
    assert "display-only" not in xml
    assert "<reg>" in xml
    assert 'resp="#editor"' in xml
    assert 'evidence="visible"' in xml
    path = tmp_path / "typed-writer.xml"
    # Read through a temporary file because the public reader deliberately accepts paths.
    path.write_text(xml, encoding="utf-8")
    back = read_epidoc(path)[0].tokens[0]
    assert back.text == "λόγος"
    assert back.form_state is not None
    restored = next(
        segment for segment in back.form_state.segments
        if segment.status is ReadingStatus.RESTORED
    )
    assert restored.source_ref is not None
    assert dict(restored.source_ref.attrs)["resp"] == "#editor"
    assert dict(restored.source_ref.attrs)["{urn:test}evidence"] == "visible"


def test_epidoc_projects_edition_forms_but_full_archives_keep_model_forms(
    tmp_path: Path,
) -> None:
    state = TokenFormState(
        diplomatic="λογος",
        regularized="λόγος",
        normalized="λόγοσ",
        model_input="λόγοσ",
        segments=(FormSegment("λόγος"),),
        model_input_ops=("unicode:nfc",),
        model_input_source="normalized",
    )
    document = Document(
        "d", "greek", [Token("λόγος", TokenKind.WORD, form_state=state)], [[0]]
    )
    path = tmp_path / "edition-projection.xml"
    path.write_text(to_epidoc(document), encoding="utf-8")
    projected = read_epidoc(path)[0].tokens[0].form_state
    assert projected is not None
    assert projected.diplomatic == "λογος"
    assert projected.regularized == "λόγος"
    assert projected.normalized is None
    assert projected.model_input is None


def test_epidoc_writer_rejects_invalid_source_attribute_names_cleanly() -> None:
    ref = SourceMarkupRef("ed", "gap[1]", "gap", (("bad name", "value"),))
    state = TokenFormState(
        diplomatic="",
        segments=(FormSegment("", ReadingStatus.LOST, ref),),
    )
    document = Document(
        "d", "greek", [Token("", TokenKind.WORD, status=ReadingStatus.LOST, form_state=state)], [[0]]
    )
    with pytest.raises(ValueError, match="invalid XML attribute name"):
        to_epidoc(document)


def test_epidoc_writer_rejects_inconsistent_typed_state_cleanly() -> None:
    mismatched = TokenFormState(
        diplomatic="a",
        regularized="b",
        segments=(FormSegment("a"),),
    )
    document = Document(
        "d", "greek", [Token("b", TokenKind.WORD, form_state=mismatched)], [[0]]
    )
    with pytest.raises(ValueError, match="segments do not compose"):
        to_epidoc(document)

    conflicting_status = TokenFormState(
        diplomatic="x",
        segments=(
            FormSegment(
                "x",
                ReadingStatus.LOST,
                SourceMarkupRef("d", "supplied[1]", "supplied", (("reason", "lost"),)),
            ),
        ),
    )
    document = Document(
        "d",
        "greek",
        [Token("x", TokenKind.WORD, status=ReadingStatus.LOST, form_state=conflicting_status)],
        [[0]],
    )
    with pytest.raises(ValueError, match="conflict.*editorial status"):
        to_epidoc(document)

    prefixed = TokenFormState(
        diplomatic="x",
        segments=(
            FormSegment(
                "x",
                ReadingStatus.RESTORED,
                SourceMarkupRef("d", "supplied[1]", "supplied", (("foo:bar", "v"),)),
            ),
        ),
    )
    document = Document(
        "d",
        "greek",
        [Token("x", TokenKind.WORD, status=ReadingStatus.RESTORED, form_state=prefixed)],
        [[0]],
    )
    with pytest.raises(ValueError, match="unbound XML attribute prefix"):
        to_epidoc(document)


def test_epidoc_deep_input_remains_iterative(tmp_path: Path) -> None:
    depth = 10_000
    body = "<seg>" * depth + "<w>a</w>" + "</seg>" * depth
    path = tmp_path / "deep.xml"
    path.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        f'<div type="edition"><ab>{body}</ab></div></body></text></TEI>',
        encoding="utf-8",
    )
    start = time.perf_counter()
    documents = read_epidoc(path)
    assert len(documents) == 1
    assert len(documents[0].tokens) == 1
    assert time.perf_counter() - start < 10.0


def test_conllu_legacy_structure_roundtrip_is_exact() -> None:
    raw = _strict_conllu_fixture()
    document = load_conllu_document(raw, strict=True)
    assert document.dumps() == raw
    sentence = document.sentences[0]
    assert isinstance(sentence.rows[0], UDMultiwordToken)
    assert isinstance(sentence.rows[-1], UDEmptyNode)
    assert sentence.tokens[0].misc[0].key == "SpaceAfter"
    assert sentence.tokens[0].misc[1].key == "Unknown"


def test_conllu_form_state_projection_is_reversible_and_safe() -> None:
    raw = _strict_conllu_fixture()
    sentence = load_conllu(raw, strict=True)[0]
    state = TokenFormState(
        diplomatic="lo|gos=\\",
        regularized="λόγος",
        segments=(FormSegment("λόγος"),),
    )
    changed = replace(sentence, tokens=(replace(sentence.tokens[0], form_state=state), *sentence.tokens[1:]))
    output = dump_conllu([changed], canonical=True)
    state_value = next(
        item.split("=", 1)[1]
        for item in output.splitlines()[3].split("\t")[-1].split("|")
        if item.startswith("AegeanFormState=")
    )
    assert "|" not in state_value and "=" not in state_value
    decoded = json.loads(
        base64.urlsafe_b64decode(state_value + "=" * (-len(state_value) % 4))
    )
    assert decoded["schema"] == 1
    assert decoded["state"]["diplomatic"] == "lo|gos=\\"

    back = load_conllu(output, strict=True)[0]
    assert back.tokens[0].form_state == state
    assert isinstance(back.rows[0], UDMultiwordToken)
    assert isinstance(back.rows[-1], UDEmptyNode)
    assert back.tokens[0].misc[0].key == "SpaceAfter"
    assert back.tokens[0].misc[1].key == "Unknown"


def test_conllu_writer_rejects_state_its_strict_reader_cannot_reload() -> None:
    state = TokenFormState("x" * 800_000)
    sentence = load_conllu("1\tx\t_\tX\t_\t_\t0\troot\t_\t_\n\n", strict=True)[0]
    changed = replace(
        sentence,
        tokens=(replace(sentence.tokens[0], form_state=state),),
    )
    with pytest.raises(ValueError, match="1,000,000-character limit"):
        dump_conllu([changed], canonical=True)


def test_conllu_malformed_form_state_is_clean_strict_error_and_lenient_opaque() -> None:
    raw = (
        "# sent_id = bad\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\tAegeanFormState=not-valid\n\n"
    )
    lenient = load_conllu(raw, strict=False)[0].tokens[0]
    assert lenient.form_state is None
    assert lenient.misc[0].key == "AegeanFormState"
    assert dump_conllu(load_conllu(raw)) == raw
    with pytest.raises(ValueError, match=r"line 2.*AegeanFormState"):
        load_conllu(raw, strict=True)


def test_conllu_form_state_schema_and_reserved_key_collisions_are_safe() -> None:
    future_payload = base64.urlsafe_b64encode(
        json.dumps({"schema": 2, "state": {}}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    raw = (
        "# sent_id = future\n"
        f"1\ta\t_\tNOUN\t_\t_\t0\troot\t_\tAegeanFormState={future_payload}\n\n"
    )
    assert load_conllu(raw, strict=False)[0].tokens[0].form_state is None
    with pytest.raises(ValueError, match=r"line 2.*AegeanFormState"):
        load_conllu(raw, strict=True)

    sentence = load_conllu(raw, strict=False)[0]
    state = TokenFormState("a")
    changed = replace(sentence, tokens=(replace(sentence.tokens[0], form_state=state),))
    canonical = dump_conllu([changed], canonical=True)
    assert canonical.count("AegeanFormState=") == 1
    assert load_conllu(canonical, strict=True)[0].tokens[0].form_state == state


def test_conllu_oversized_form_state_is_a_clean_strict_error() -> None:
    raw = (
        "# sent_id = huge\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\tAegeanFormState="
        + "A" * 1_000_001
        + "\n\n"
    )
    assert load_conllu(raw, strict=False)[0].tokens[0].form_state is None
    with pytest.raises(ValueError, match=r"line 2.*1,000,000-character limit"):
        load_conllu(raw, strict=True)


def test_default_pipeline_projection_does_not_emit_a6_state() -> None:
    sentence = load_conllu(
        "# sent_id = default\n1\tλόγος\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    )[0]
    state = TokenFormState("λογος", regularized="λόγος", segments=(FormSegment("λόγος"),))
    sentence = replace(sentence, tokens=(replace(sentence.tokens[0], form_state=state),))
    predicted = pipeline_conllu([sentence])
    assert "AegeanFormState=" not in predicted
    assert "\n1\tλόγος\t" in predicted
