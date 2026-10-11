"""Source preservation journeys; constructed import diagnostics and attributed TEI evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import unicodedata

import pytest

from aegean import Corpus, db, io
from aegean.core.model import TokenKind
from aegean.scripts.greek.perseus import parse_tei_work


@pytest.mark.parametrize("value", ["12", "0.5", "0012", "", "not-a-number"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_epidoc_num_source_value_survives_semantic_and_archive_roundtrips(tmp_path, value, wrapped):
    import xml.etree.ElementTree as ET

    ns = "{http://www.tei-c.org/ns/1.0}"
    root = ET.fromstring(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition"><ab><lb n="1"/><num>ιβʹ</num></ab></div>'
        '</body></text></TEI>'
    )
    num = root.find(f".//{ns}num")
    num.set("value", value)
    if wrapped:
        num.text = None
        ET.SubElement(num, f"{ns}unclear").text = "ιβʹ"
    source = tmp_path / "source.xml"
    ET.ElementTree(root).write(source, encoding="utf-8")
    corpus = io.from_epidoc(source, script_id="greek")
    token = corpus.documents[0].tokens[0]
    assert token.kind is TokenKind.NUMERAL
    assert token.annotations["epidoc:num_value"] == value
    assert token.text == "ιβʹ"
    assert token.status.value == ("unclear" if wrapped else "certain")
    exported = ET.fromstring(io.to_epidoc(corpus.documents[0]))
    assert exported.find(f".//{ns}num").get("value") == value
    assert Corpus.from_json(corpus.to_json()).documents[0].tokens[0].annotations == token.annotations
    database = tmp_path / "source.sqlite"
    db.to_sqlite(corpus, database)
    assert db.from_sqlite(database).documents[0].tokens[0].annotations == token.annotations


def reconstruct(document) -> str:
    """Reconstruct from recorded spans/gaps, including the source's terminal whitespace."""
    document.validate_source_alignment()
    parts = []
    end = 0
    for token in document.tokens:
        alignment = token.alignment
        assert alignment is not None
        assert document.source_text[alignment.start_char:alignment.end_char] == alignment.original_text
        parts.extend((alignment.whitespace_before, alignment.original_text))
        end = alignment.end_char
    parts.append(document.source_text[end:])
    return "".join(parts)


@pytest.mark.parametrize("text", ["hello world", "λόγος Latin 123 λόγος", "λόγος· λόγος;"])
def test_assessed_import_boundaries_preserve_the_complete_source(text):
    corpus = io.from_text(text)
    document = corpus.documents[0]
    assert reconstruct(document) == text
    assert document.source_text == text
    assert json.loads(corpus.to_json())["documents"][0]["source_text"] == text
    if text == "hello world":
        assert document.words == []
        assert [(token.text, token.kind) for token in document.tokens] == [
            ("hello", TokenKind.UNKNOWN), ("world", TokenKind.UNKNOWN),
        ]
    elif "Latin" in text:
        assert [(token.text, token.kind) for token in document.tokens] == [
            ("λόγος", TokenKind.WORD), ("Latin", TokenKind.UNKNOWN),
            ("123", TokenKind.NUMERAL), ("λόγος", TokenKind.WORD),
        ]
        assert corpus.word_frequencies() == [("λόγος", 2)]
    assert "word view excludes" in " ".join(corpus.provenance.notes)


def test_mixed_unicode_spans_keep_originals_and_only_normalize_the_alignment_view():
    decomposed = unicodedata.normalize("NFD", "λόγος")
    text = f" \t{decomposed},Latin123 ١٢ Ⅳ €\r\n"
    document = io.from_text(text).documents[0]
    assert reconstruct(document) == text
    assert [token.text for token in document.numerals] == ["123", "١٢", "Ⅳ"]
    assert [token.text for token in document.words] == [decomposed]
    alignment = document.words[0].alignment
    assert alignment.original_text == decomposed
    assert alignment.normalized_text == "λόγος"
    assert alignment.normalization_ops == ("unicode:nfc",)


def test_nfd_latin_marks_stay_with_foreign_text_and_bare_marks_are_not_greek_words():
    text = "cafe\u0301 λόγος \u0301"
    corpus = io.from_text(text)
    document = corpus.documents[0]
    assert [(token.text, token.kind) for token in document.tokens] == [
        ("cafe\u0301", TokenKind.UNKNOWN), ("λόγος", TokenKind.WORD), ("\u0301", TokenKind.UNKNOWN),
    ]
    assert corpus.word_frequencies() == [("λόγος", 1)]
    assert document.tokens[0].alignment.normalized_text == "café"
    assert reconstruct(document) == text


@pytest.mark.parametrize("sign", ["\u0301", "῀", "϶", "ʹ", "ϣ"])
def test_a_greek_tokenizer_sign_without_a_greek_alphabetic_base_is_not_a_word(sign):
    corpus = io.from_text(sign)
    assert corpus.documents[0].words == []
    assert reconstruct(corpus.documents[0]) == sign


@pytest.mark.parametrize("split, count", [("whole", 1), ("paragraph", 3), ("line", 3)])
def test_split_documents_partition_blank_lines_and_exact_line_endings(split, count):
    text = "\r\n  λόγος·\r\n\r\nLatin 123\r\n\n  καί;\r\n \r\n"
    corpus = io.from_text(text, split=split, doc_id="fragment")
    assert len(corpus) == count
    assert "".join(reconstruct(document) for document in corpus) == text
    for document in corpus:
        for line_no, tokens in enumerate(document.line_tokens):
            assert all(token.line_no == line_no for token in tokens)


def test_source_preserving_import_survives_json_and_sqlite_without_a_shadow_model(tmp_path):
    text = "\n" + unicodedata.normalize("NFD", "μῆνιν") + ", Latin 123\r\nκαί;\n"
    original = io.from_text(text, split="line", doc_id="edition-fragment")
    path = tmp_path / "source.sqlite"
    db.to_sqlite(original, path)
    snapshots = [Corpus.from_json(original.to_json()), db.from_sqlite(path)]
    for loaded in snapshots:
        assert json.loads(loaded.to_json()) == json.loads(original.to_json())
        assert "".join(reconstruct(document) for document in loaded) == text


def test_explicit_legacy_word_import_records_what_was_lost():
    text = "λόγος Latin 123 λόγος;\n\nκαί"
    corpus = io.from_text(text, token_view="words")
    document = corpus.documents[0]
    assert [token.text for token in document.tokens] == ["λόγος", "λόγος", "καί"]
    assert document.lines == [[0, 1], [2]]
    assert document.source_text is None
    assert all(token.alignment is None for token in document.tokens)
    report = " ".join(corpus.provenance.notes)
    assert "excluded 3 source token(s)" in report
    assert "raw source text, whitespace, and source spans are unavailable" in report


@pytest.mark.parametrize("factory", [io.from_text, io.from_text_file, io.from_text_dir, io.from_csv])
def test_all_import_surfaces_reject_an_unknown_token_view(tmp_path, factory):
    path = tmp_path / "text.txt"
    path.write_text("λόγος")
    csv_path = tmp_path / "text.csv"
    csv_path.write_text("text\nλόγος\n")
    argument = "λόγος" if factory is io.from_text else tmp_path if factory is io.from_text_dir else csv_path if factory is io.from_csv else path
    with pytest.raises(ValueError, match="token_view"):
        factory(argument, token_view="arbitrary")


def test_files_directory_collisions_and_multiline_csv_cells_preserve_source(tmp_path):
    text = "  λόγος\r\nLatin 123\r\n"
    first = tmp_path / "a" / "same.txt"
    second = tmp_path / "b" / "same.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(text.encode("utf-8"))
    second.write_bytes(text.encode("utf-8"))
    assert reconstruct(io.from_text_file(first).documents[0]) == text
    directory = io.from_text_dir(tmp_path, glob="**/*.txt")
    assert [document.id for document in directory] == ["same", "same#2"]
    assert [reconstruct(document) for document in directory] == [text, text]
    assert all(token.alignment.document_id == "same#2" for token in directory.documents[1].tokens)
    path = tmp_path / "rows.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "text"])
        writer.writerow(["row", text])
    assert reconstruct(io.from_csv(path, id_col="id").documents[0]) == text
    legacy = io.from_csv(path, id_col="id", token_view="words").documents[0]
    assert legacy.lines == [[0]]  # the former CSV importer flattened a multiline cell


def test_syllabic_sign_groups_keep_their_classification_and_source():
    text = "\n A-DU\t10\r\n\nKU-RO 10  \n"
    document = io.from_text(text, script_id="lineara").documents[0]
    assert reconstruct(document) == text
    assert document.words[0].signs == ("A", "DU")
    assert [token.text for token in document.numerals] == ["10", "10"]


def test_euthyphro_source_speakers_survive_selection_counting_and_archiving(tmp_path):
    """Actual Euthyphro 2a source evidence; no new grammatical gold is claimed."""
    path = Path(__file__).parent / "fixtures" / "greeklit" / "euthyphro-speakers.xml"
    _title, _author, documents = parse_tei_work(path.read_bytes(), "tlg0059.tlg001", ref="2a")
    document = documents[0]
    labels = [token for token in document.tokens if token.annotations.get("role") == "speaker"]
    assert [(token.text, token.kind, token.annotations["who"]) for token in labels] == [
        ("ΕΥΘ.", TokenKind.UNKNOWN, "#Εὐθύφρων"),
        ("ΣΩ.", TokenKind.UNKNOWN, "#Σωκράτης"),
    ]
    assert document.words[0].text == "τί"
    assert document.words[0].annotations["speaker"] == "Εὐθύφρων"
    assert document.words[0].annotations["speech_id"] == "said[1]"
    assert "φῄς" not in [token.text for token in document.words]  # 2b is beyond the boundary
    assert reconstruct(document).startswith("ΕΥΘ. τί νεώτερον")
    corpus = Corpus(documents, script_id="greek")
    frequencies = dict(corpus.word_frequencies())
    assert not any(label in frequencies for label in ("ΕΥΘ", "ΣΩ", "ΕΥΘ.", "ΣΩ."))
    target = tmp_path / "dialogue.sqlite"
    db.to_sqlite(corpus, target)
    for loaded in (Corpus.from_json(corpus.to_json()), db.from_sqlite(target)):
        assert json.loads(loaded.to_json()) == json.loads(corpus.to_json())
        assert reconstruct(loaded.documents[0]) == document.source_text


def test_mid_speech_milestone_keeps_identity_without_inventing_a_label():
    # Constructed structure diagnostic: markup inheritance across a citation boundary.
    xml = b'''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition">
    <p><said who="#socrates"><label>S.</label> alpha <milestone unit="section" n="2a"/>
    \xce\xbb\xcf\x8c<hi>\xce\xb3\xce\xbf\xcf\x82</hi><milestone unit="section" n="2b"/> beta</said></p>
    </div></body></text></TEI>'''
    _, _, documents = parse_tei_work(xml, "w", ref="2a")
    document = documents[0]
    assert [token.text for token in document.words] == ["λόγος"]
    assert document.words[0].annotations == {
        "speech_id": "said[1]", "who": "#socrates", "speaker": "socrates", "speaker_label": "S.",
    }
    assert all(token.annotations.get("role") != "speaker" for token in document.tokens)


def test_speaker_markup_separates_a_label_from_adjacent_words_without_losing_text():
    xml = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition">
    <p><sp who="#chorus"><speaker>ΧΟ</speaker>λό<hi>γος</hi></sp></p>
    </div></body></text></TEI>'''.encode()
    _, _, documents = parse_tei_work(xml, "w")
    document = documents[0]
    assert [(token.text, token.kind) for token in document.tokens] == [
        ("ΧΟ", TokenKind.UNKNOWN), ("λόγος", TokenKind.WORD),
    ]
    assert reconstruct(document) == "ΧΟλόγος"
    assert document.words[0].annotations["who"] == "#chorus"


def test_a_missing_verse_range_endpoint_cannot_be_cited_as_loaded():
    path = Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml"
    with pytest.raises(ValueError, match="endpoint 99 is unavailable"):
        parse_tei_work(path.read_bytes(), "w", ref="1.1-1.99")
