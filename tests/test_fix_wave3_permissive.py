"""Malformed or unreadable input is reported, not accepted and half-loaded.

Four surfaces, one shape of problem: something the reader could not understand was taken
anyway, and the caller got a bare key name, an empty corpus, or a document with nothing in it.

* `Corpus.from_dict` — the entry point for every saved corpus — answered a hand-edited or
  third-party file with ``KeyError: 'kind'`` (the CLI showed only ``'kind'``), iterated an
  ``int`` where the document list belongs, and spread a string across a list-valued field.
* `Corpus.from_json` and `aegean.io.from_workbench_export` refused a JSON file carrying a
  UTF-8 BOM, and read a BOM-prefixed JSON *string* as a filename.
* `Corpus.filter` accepted a metadata field that does not exist and returned an empty
  corpus whose provenance note read exactly like a real filter.
* `aegean.io.from_csv` turned a row with an empty text cell into a zero-token document,
  where the text-file path raises on the same input.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import aegean
from aegean import io as aegean_io
from aegean.core.corpus import Corpus
from aegean.core.provenance import SCHEMA_VERSION

BOM = "﻿"
GREEK = "μῆνιν ἄειδε θεά"
# Bundled corpora: loadable with no network, and every script family the reader serves.
BUNDLED = ("lineara", "linearb", "cypriot", "cyprominoan", "greek")


def _corpus_dict(**document: object) -> dict[str, object]:
    """A minimal well-formed corpus dict with one document overridden by ``document``."""
    doc: dict[str, object] = {
        "id": "D1",
        "tokens": [{"text": "A-DU", "kind": "word"}],
        "lines": [[0]],
    }
    doc.update(document)
    return {"_meta": {"schemaVersion": SCHEMA_VERSION, "scriptId": "lineara"}, "documents": [doc]}


# ── from_dict: the malformed source is named, not guessed at ─────────────────


def test_from_dict_names_the_document_and_the_missing_token_field() -> None:
    """A token without 'kind' reported ``KeyError: 'kind'`` — a bare key name with no
    hint which of a corpus's documents to open."""
    with pytest.raises(ValueError) as exc:
        Corpus.from_dict(_corpus_dict(id="HT 13", tokens=[{"text": "A-DU"}]))
    message = str(exc.value)
    assert "HT 13" in message and "token 0" in message and "kind" in message

    with pytest.raises(ValueError) as exc:
        Corpus.from_dict(_corpus_dict(id="HT 13", tokens=[{"kind": "word"}]))
    assert "HT 13" in str(exc.value) and "text" in str(exc.value)


def test_from_dict_rejects_a_documents_value_that_cannot_hold_documents() -> None:
    """``{'documents': 5}`` raised ``TypeError: 'int' object is not iterable``."""
    with pytest.raises(ValueError) as exc:
        Corpus.from_dict({"documents": 5})
    assert "'documents'" in str(exc.value) and "array" in str(exc.value)

    with pytest.raises(ValueError) as exc:  # ``{'documents': [5]}`` → AttributeError
        Corpus.from_dict({"documents": [5]})
    assert "document 0" in str(exc.value) and "object" in str(exc.value)

    with pytest.raises(ValueError) as exc:  # a top-level array (a records file, say)
        Corpus.from_dict([])  # type: ignore[arg-type]
    assert "must be a JSON object" in str(exc.value)


def test_from_dict_lists_the_values_an_enum_field_accepts() -> None:
    with pytest.raises(ValueError) as exc:
        Corpus.from_dict(_corpus_dict(tokens=[{"text": "A-DU", "kind": "noun"}]))
    message = str(exc.value)
    assert "'noun'" in message and "'word'" in message and "'numeral'" in message

    with pytest.raises(ValueError) as exc:
        Corpus.from_dict(
            _corpus_dict(tokens=[{"text": "A-DU", "kind": "word", "status": "maybe"}])
        )
    assert "'maybe'" in str(exc.value) and "'restored'" in str(exc.value)


def test_from_dict_requires_a_usable_document_id() -> None:
    with pytest.raises(ValueError) as exc:
        Corpus.from_dict({"documents": [{"tokens": []}]})
    assert "document 0" in str(exc.value) and "id" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Corpus.from_dict({"documents": [{"id": ""}]})
    assert "empty" in str(exc.value)


def test_from_dict_refuses_a_string_where_a_list_belongs() -> None:
    """The silent-wrongness case: ``"a translation"`` was iterated into one entry per
    character, and ``"HT 13"`` in ``meta.images`` became five image references."""
    with pytest.raises(ValueError) as exc:
        Corpus.from_dict(_corpus_dict(translations="a translation"))
    assert "'translations'" in str(exc.value) and "array" in str(exc.value)

    with pytest.raises(ValueError):
        Corpus.from_dict(_corpus_dict(meta={"images": "HT13.jpg"}))

    with pytest.raises(ValueError):
        Corpus.from_dict(_corpus_dict(tokens=[{"text": "A-DU", "kind": "word", "alt": "AB"}]))

    # the well-formed forms of the same fields still load
    c = Corpus.from_dict(
        _corpus_dict(
            translations=["a translation"],
            meta={"images": ["HT13.jpg"]},
            tokens=[{"text": "A-DU", "kind": "word", "alt": ["AB"]}],
        )
    )
    assert c.documents[0].translations == ["a translation"]
    assert c.documents[0].meta.images == ("HT13.jpg",)
    assert c.documents[0].tokens[0].alt == ("AB",)


def test_from_dict_validates_the_declared_schema_version() -> None:
    """The version is not decoration: it decides whether typed form state is read at all,
    so ``"3"`` as a string quietly downgraded the file and dropped that state."""
    from aegean.core.model import TokenFormState

    form_state = {
        "text": "A-DU", "kind": "word",
        "form_state": TokenFormState(diplomatic="A-DU").to_dict(),
    }
    for bad in ("3", True, 0, -1, 3.0):
        with pytest.raises(ValueError) as exc:
            Corpus.from_dict({"_meta": {"schemaVersion": bad}, "documents": []})
        assert "schemaVersion" in str(exc.value)

    with pytest.raises(ValueError) as exc:  # a file from a future release still says so
        Corpus.from_dict({"_meta": {"schemaVersion": SCHEMA_VERSION + 1}, "documents": []})
    assert "upgrade pyaegean" in str(exc.value)

    # the current version reads form state; a file that omits the version still loads
    loaded = Corpus.from_dict(
        {"_meta": {"schemaVersion": SCHEMA_VERSION}, "documents": [
            {"id": "D1", "tokens": [form_state], "lines": [[0]]}
        ]}
    )
    assert loaded.documents[0].tokens[0].form_state is not None
    assert len(Corpus.from_dict({"documents": [{"id": "D1", "tokens": []}]})) == 1


def test_from_dict_names_a_malformed_sign_inventory_and_provenance() -> None:
    with pytest.raises(ValueError) as exc:
        Corpus.from_dict({"documents": [], "signInventory": {"signs": [{"glyph": "𐘀"}]}})
    assert "signs[0]" in str(exc.value) and "label" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Corpus.from_dict({"documents": [], "provenance": "SigLA"})
    assert "'provenance'" in str(exc.value)


@pytest.mark.parametrize("name", BUNDLED)
def test_the_stricter_reader_still_round_trips_every_bundled_corpus(name: str) -> None:
    """The load-bearing check: stricter validation must not refuse real data. Each bundled
    corpus is re-read from its own serialization and must come back identical."""
    original = aegean.load(name)
    back = Corpus.from_json(original.to_json())
    assert len(back) == len(original)
    assert sum(len(d.tokens) for d in back) == sum(len(d.tokens) for d in original)
    assert back.fingerprint() == original.fingerprint()


def test_cli_names_the_document_and_field_for_a_malformed_corpus_file(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    bad = tmp_path / "hand-edited.json"
    bad.write_text(json.dumps(_corpus_dict(id="HT 13", tokens=[{"text": "A-DU"}])), "utf-8")
    result = CliRunner().invoke(_build_app(), ["info", str(bad)])
    assert result.exit_code == 1
    assert "HT 13" in result.output and "kind" in result.output


# ── a UTF-8 BOM is a file's encoding, not its content ────────────────────────


def test_from_json_reads_a_corpus_file_that_carries_a_bom(tmp_path) -> None:
    source = aegean.load("lineara").subset(["HT 13"])
    text = source.to_json()
    assert text is not None
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

    assert Corpus.from_json(path).fingerprint() == source.fingerprint()
    assert Corpus.from_json(str(path)).fingerprint() == source.fingerprint()
    # a BOM on the JSON *string* was read as a filename (OSError), not as JSON
    assert Corpus.from_json(BOM + text).fingerprint() == source.fingerprint()
    # and the file is reachable through every corpus-resolving entry point
    assert aegean.read_corpus(str(path)).fingerprint() == source.fingerprint()


def test_from_workbench_export_reads_an_export_that_carries_a_bom(tmp_path) -> None:
    records = [{"id": "HT 13", "words": ["A-DU", "10"], "site": "Haghia Triada"}]
    text = json.dumps(records, ensure_ascii=False)
    path = tmp_path / "export.json"
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

    for source in (path, str(path), BOM + text):
        loaded = aegean_io.from_workbench_export(source)
        assert [d.id for d in loaded] == ["HT 13"]
        assert loaded.documents[0].meta.site == "Haghia Triada"


def test_text_import_does_not_glue_a_bom_onto_the_first_word(tmp_path) -> None:
    """A syllabic script splits on whitespace, so the BOM became part of the first sign
    group: ``﻿A-DU`` matched no sign, no query, and no other corpus's ``A-DU``.
    (The Greek tokenizer drops it as a non-Greek character, which is why this hid.)"""
    path = tmp_path / "HT13.txt"
    path.write_bytes(b"\xef\xbb\xbf" + "A-DU 10".encode("utf-8"))

    from_file = aegean_io.from_text_file(path, script_id="lineara")
    assert [t.text for t in from_file.documents[0].tokens] == ["A-DU", "10"]

    from_string = aegean_io.from_text(BOM + "A-DU 10", script_id="lineara")
    assert [t.text for t in from_string.documents[0].tokens] == ["A-DU", "10"]

    folder = aegean_io.from_text_dir(tmp_path, script_id="lineara")
    assert folder.documents[0].tokens[0].text == "A-DU"

    greek = tmp_path / "iliad.txt"
    greek.write_bytes(b"\xef\xbb\xbf" + GREEK.encode("utf-8"))
    assert aegean_io.from_text_file(greek).documents[0].tokens[0].text == "μῆνιν"


def test_a_string_that_is_neither_json_nor_a_path_is_reported(tmp_path) -> None:
    """It was routed to the filesystem and surfaced ``OSError: [Errno 22] Invalid argument``."""
    with pytest.raises(ValueError) as exc:
        Corpus.from_json("this is not JSON and not a path " * 20)
    assert "corpus" in str(exc.value).lower()

    with pytest.raises(ValueError):
        aegean_io.from_workbench_export("not JSON, not a path " * 20)

    # a plain missing file keeps naming itself
    with pytest.raises(FileNotFoundError):
        Corpus.from_json(tmp_path / "absent.json")


# ── filter: a field that does not exist is a mistake, not an empty result ────


def test_filter_reports_an_unknown_metadata_field() -> None:
    corpus = aegean.load("lineara")
    with pytest.raises(ValueError) as exc:
        corpus.filter(sight="Haghia Triada")
    message = str(exc.value)
    assert "sight" in message and "site" in message  # names the typo and the near miss
    assert "period" in message  # and lists the fields that do exist

    with pytest.raises(ValueError):
        corpus.filter(site="Haghia Triada", perod="LMIB")

    # every real field still filters, and a real field with no matches still returns empty
    assert len(corpus.filter(site="Haghia Triada")) > 0
    empty = corpus.filter(site="Nowhere")
    assert len(empty) == 0
    assert empty.provenance is not None and "subset:" in empty.provenance.notes[-1]


# ── CSV rows and text lines agree about "there is nothing here" ──────────────


def test_from_csv_skips_a_row_with_an_empty_text_cell_and_records_it(tmp_path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text(f"id,text\nA,{GREEK}\nB,\nC,   \n", encoding="utf-8")
    corpus = aegean_io.from_csv(path, id_col="id")

    assert [d.id for d in corpus] == ["A"]  # not three documents, two of them empty
    assert all(len(d.tokens) > 0 for d in corpus)
    assert corpus.provenance is not None
    assert any(n.startswith("skipped 2 row(s)") for n in corpus.provenance.notes)


def test_from_csv_and_from_text_file_agree_on_input_with_no_text(tmp_path) -> None:
    """The inconsistency itself: the text path raised, the CSV path returned empty documents."""
    blank_csv = tmp_path / "blank.csv"
    blank_csv.write_text("id,text\nA,\nB,   \n", encoding="utf-8")
    blank_txt = tmp_path / "blank.txt"
    blank_txt.write_text("\n   \n\n", encoding="utf-8")

    with pytest.raises(ValueError) as csv_exc:
        aegean_io.from_csv(blank_csv, id_col="id")
    with pytest.raises(ValueError):
        aegean_io.from_text_file(blank_txt)
    assert "no text to import" in str(csv_exc.value)

    empty_csv = tmp_path / "header-only.csv"
    empty_csv.write_text("id,text\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        aegean_io.from_csv(empty_csv, id_col="id")
    assert "no rows to import" in str(exc.value)


def test_from_csv_keeps_a_row_whose_text_the_script_cannot_tokenize(tmp_path) -> None:
    """The deliberate boundary: text that is present but yields no tokens under this
    script is a wrong ``script_id``, not an empty cell, and the text path keeps such a
    line too — so the CSV path keeps the row rather than dropping data."""
    path = tmp_path / "latin.csv"
    path.write_text("id,text\nA,alpha beta\n", encoding="utf-8")
    corpus = aegean_io.from_csv(path, id_col="id", script_id="greek")
    assert [d.id for d in corpus] == ["A"]

    txt = tmp_path / "latin.txt"
    txt.write_text("alpha beta\n", encoding="utf-8")
    assert len(aegean_io.from_text_file(txt, script_id="greek")) == 1


def test_cli_import_reports_the_rows_it_skipped(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    src = tmp_path / "rows.csv"
    src.write_text(f"id,text\nA,{GREEK}\nB,\n", encoding="utf-8")
    out = tmp_path / "rows.json"
    result = CliRunner().invoke(
        _build_app(), ["import", str(src), "-o", str(out), "--id-col", "id"]
    )
    assert result.exit_code == 0, result.output
    assert "skipped 1 row(s)" in result.output
    assert len(aegean.read_corpus(str(out))) == 1

    # --json carries the same fact, and only when there is one: the payload of an import
    # that skipped nothing keeps exactly the keys it has always had.
    as_json = CliRunner().invoke(
        _build_app(),
        ["import", str(src), "-o", str(out), "--id-col", "id", "--json"],
    )
    payload = json.loads(as_json.stdout)
    assert payload["skipped"] == ["skipped 1 row(s) with an empty 'text' column"]

    whole = tmp_path / "whole.csv"
    whole.write_text(f"id,text\nA,{GREEK}\n", encoding="utf-8")
    clean = CliRunner().invoke(
        _build_app(),
        ["import", str(whole), "-o", str(tmp_path / "w.json"), "--id-col", "id", "--json"],
    )
    assert "skipped" not in json.loads(clean.stdout)

    blank = tmp_path / "blank.csv"
    blank.write_text("id,text\nA,\n", encoding="utf-8")
    failed = CliRunner().invoke(
        _build_app(), ["import", str(blank), "-o", str(tmp_path / "b.json"), "--id-col", "id"]
    )
    assert failed.exit_code == 1
    assert "no text to import" in failed.output
    assert not Path(tmp_path / "b.json").exists()  # nothing written for input with no text
