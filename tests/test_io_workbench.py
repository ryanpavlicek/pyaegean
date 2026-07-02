"""Round-trip with linearaworkbench: to_workbench / from_workbench_export."""

from __future__ import annotations

import json

import pytest

from aegean.core.corpus import Corpus
from aegean.io import from_workbench_export, to_workbench


@pytest.fixture()
def small_corpus() -> Corpus:
    return Corpus.from_records(
        [
            {
                "id": "X1",
                "lines": [["KU-RO", "10"], ["PA-I-TO"]],
                "translations": ["total", "", ""],
                "meta": {
                    "site": "Haghia Triada",
                    "support": "tablet",
                    "scribe": "Scribe 1",
                    "findspot": "Magazine",
                    "period": "LMIB",
                    "name": "X1 name",
                },
            },
            {"id": "X2", "words": ["A-DU"]},
        ],
        script_id="lineara",
    )


def test_to_workbench_emits_full_record_shape(small_corpus: Corpus) -> None:
    records = to_workbench(small_corpus)
    assert [r["id"] for r in records] == ["X1", "X2"]
    r = records[0]
    assert r["site"] == "Haghia Triada"
    assert r["context"] == "LMIB"  # the workbench's name for the period field
    assert r["name"] == "X1 name"
    assert r["words"] == ["KU-RO", "10", "PA-I-TO"]
    assert r["lines"] == [["KU-RO", "10"], ["PA-I-TO"]]
    assert r["translations"] == ["total", "", ""]
    # every workbench field is present so the app needs no special-casing
    for key in (
        "scribe", "findspot", "glyphs", "transcription",
        "facsimileImages", "images", "imageRights", "imageRightsURL",
    ):
        assert key in r
    # documents without metadata fall back to the id as the display name
    assert records[1]["name"] == "X2"


def test_to_workbench_writes_json(tmp_path, small_corpus: Corpus) -> None:
    out = tmp_path / "corpus.json"
    records = to_workbench(small_corpus, out)
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == records


def test_round_trip_preserves_text_and_metadata(small_corpus: Corpus) -> None:
    back = from_workbench_export(to_workbench(small_corpus))
    assert len(back) == len(small_corpus)
    for orig, rt in zip(small_corpus, back):
        assert rt.id == orig.id
        assert [t.text for t in rt.tokens] == [t.text for t in orig.tokens]
        assert [[t.text for t in line] for line in rt.line_tokens] == [
            [t.text for t in line] for line in orig.line_tokens
        ]
        assert rt.meta.site == orig.meta.site
        assert rt.meta.period == orig.meta.period
        assert rt.translations == orig.translations


def test_from_workbench_export_accepts_schema_v1_object(tmp_path) -> None:
    export = {
        "_meta": {
            "tool": "Linear A Research Workbench",
            "schemaVersion": 1,
            "exportedAt": "2026-06-12T00:00:00Z",
            "scopeSummary": "Haghia Triada",
        },
        "inscriptions": [
            {
                "id": "HT13",
                "site": "Haghia Triada",
                "period": "LMIB",
                "words": ["KA-U-DE-TA", "KU-RO"],
                "glyphs": "\U00010613",
                "transcription": "KA-U-DE-TA KU-RO",
                "facsimileImages": ["images/HT13.png"],
                "images": ["photos/HT13.jpg"],
                "derived": {"balance": {"ok": True}},  # ignored
            }
        ],
    }
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export), encoding="utf-8")

    corpus = from_workbench_export(path)
    assert len(corpus) == 1
    doc = corpus.get("HT13")
    assert doc is not None
    assert [t.text for t in doc.tokens] == ["KA-U-DE-TA", "KU-RO"]
    assert doc.meta.period == "LMIB"
    assert doc.glyphs == "\U00010613"
    assert doc.transcription == "KA-U-DE-TA KU-RO"
    # facsimile + photo references merge into meta.images
    assert doc.meta.images == ("images/HT13.png", "photos/HT13.jpg")
    # the export's own metadata is visible in the provenance
    assert "schema v1" in corpus.provenance.source
    assert "scope: Haghia Triada" in corpus.provenance.source


def test_from_workbench_export_rejects_non_exports() -> None:
    with pytest.raises(ValueError, match="inscriptions"):
        from_workbench_export({"foo": 1})
    with pytest.raises(ValueError, match="without an id"):
        from_workbench_export([{"words": ["A"]}])


def test_bundled_lineara_round_trips_through_workbench_shape() -> None:
    corpus = Corpus.load("lineara")
    records = to_workbench(corpus)
    assert len(records) == len(corpus)
    ht13 = next(r for r in records if r["id"] == "HT13")
    doc = corpus.get("HT13")
    assert doc is not None
    assert ht13["words"] == [t.text for t in doc.tokens]
    assert ht13["images"] == list(doc.meta.images)
    back = from_workbench_export(records)
    assert len(back) == len(corpus)
    rt = back.get("HT13")
    assert rt is not None
    assert [t.text for t in rt.tokens] == [t.text for t in doc.tokens]
