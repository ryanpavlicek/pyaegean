"""Review row selection, validation, and correction/re-export round trips."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Literal

import pytest
from typer.testing import CliRunner

from aegean import greek
from aegean.cli import _build_app, _review
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import REVIEW_COLUMNS, from_review_table, needs_review_flag, to_review_table


def _corpus() -> Corpus:
    # Labels and annotations are fixtures for review state, not linguistic judgments.
    records = [
        ("resolved", {
            "lemma": "resolved-pred", "upos": "NOUN", "lemma_source": "neural",
            "lemma_resolved": "true", "lemma_verified": "false",
            "review_recommended": "false", "review_status": "corrected",
            "reviewed_by": "prior-reviewer", "lemma_confidence": "1.0",
        }),
        ("verified-flagged", {
            "lemma": "verified-pred", "lemma_source": "attested",
            "lemma_verified": "TrUe", "review_recommended": "TRUE",
        }),
        ("user-no-marker", {
            "lemma": "user-pred", "lemma_source": "user",
            "review_status": "corrected", "reviewed_by": "prior-reviewer",
        }),
        ("legacy-unresolved", {"lemma": "legacy-pred", "lemma_source": "unresolved"}),
        ("absent-metadata", {}),
        ("malformed-marker", {
            "lemma": "malformed-pred", "lemma_source": "rule", "lemma_verified": " true ",
        }),
        ("empty-marker", {
            "lemma": "empty-pred", "lemma_source": "attested", "lemma_verified": "",
        }),
        ("false-marker", {
            "lemma": "false-pred", "lemma_known": "FALSE", "lemma_verified": "FALSE",
        }),
        ("source-gold", {"lemma": "source-pred", "morph": "fixture-morph"}),
        ("verified-unflagged", {
            "lemma": "verified-other-pred", "lemma_source": "unresolved",
            "lemma_verified": "TRUE", "review_recommended": "false",
        }),
        ("source-overrides-known", {
            "lemma": "source-known-pred", "lemma_source": "rule", "lemma_known": "false",
        }),
        ("malformed-review-flag", {
            "lemma": "flag-pred", "lemma_source": "identity", "review_recommended": "yes",
        }),
    ]
    tokens = [
        Token(text=text, kind=TokenKind.WORD, position=i, line_no=0, annotations=annotations)
        for i, (text, annotations) in enumerate(records)
    ]
    tokens.extend([
        Token(text=",", kind=TokenKind.PUNCT, position=len(tokens), line_no=0,
              annotations={"lemma_source": "unresolved", "review_recommended": "true"}),
        Token(text="no-position", kind=TokenKind.WORD,
              annotations={"lemma_source": "unresolved", "review_recommended": "true"}),
    ])
    return Corpus(
        [Document(id="d", script_id="greek", tokens=tokens, lines=[list(range(len(tokens)))])],
        script_id="greek",
        provenance=Provenance(source="fixture", license="test", citation="Fixture citation"),
    )


def _expected_row(
    position: int, token: str, lemma: str = "", *,
    evidence: str = "", flag: str = "", pos: str = "", morph: str = "",
) -> dict[str, str]:
    row = dict.fromkeys(REVIEW_COLUMNS, "")
    row.update(
        doc_id="d", position=str(position), line_no="0", ref="d", token=token,
        pred_lemma=lemma, pred_pos=pos, pred_morph=morph, evidence_class=evidence,
        needs_review=flag, source_citation="Fixture citation",
    )
    return row


EXPECTED_ALL = [
    _expected_row(0, "resolved", "resolved-pred", evidence="neural", pos="NOUN"),
    _expected_row(1, "verified-flagged", "verified-pred", evidence="attested", flag="yes"),
    _expected_row(2, "user-no-marker", "user-pred", evidence="user"),
    _expected_row(3, "legacy-unresolved", "legacy-pred", evidence="unresolved", flag="yes"),
    _expected_row(4, "absent-metadata"),
    _expected_row(5, "malformed-marker", "malformed-pred", evidence="rule"),
    _expected_row(6, "empty-marker", "empty-pred", evidence="attested"),
    _expected_row(7, "false-marker", "false-pred", flag="yes"),
    _expected_row(8, "source-gold", "source-pred", morph="fixture-morph"),
    _expected_row(9, "verified-unflagged", "verified-other-pred", evidence="unresolved"),
    _expected_row(10, "source-overrides-known", "source-known-pred", evidence="rule"),
    _expected_row(11, "malformed-review-flag", "flag-pred", evidence="identity", flag="yes"),
]
EXPECTED_FLAGGED = [EXPECTED_ALL[i] for i in (1, 3, 7, 11)]
EXPECTED_UNVERIFIED = [EXPECTED_ALL[i] for i in (0, 2, 3, 4, 5, 6, 7, 8, 10, 11)]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames or ()) == REVIEW_COLUMNS
        return list(reader)


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize(("selection", "expected"), [
    ("all", EXPECTED_ALL),
    ("flagged", EXPECTED_FLAGGED),
    ("unverified", EXPECTED_UNVERIFIED),
])
def test_selection_exports_complete_rows_without_mutating_annotations(
    tmp_path: Path,
    selection: Literal["all", "flagged", "unverified"],
    expected: list[dict[str, str]],
) -> None:
    corpus = _corpus()
    before = corpus.to_json()
    path = tmp_path / "review.csv"

    assert to_review_table(corpus, path, selection=selection) == len(expected)
    assert _read_rows(path) == expected
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert corpus.to_json() == before


def test_default_selection_is_all(tmp_path: Path) -> None:
    corpus = _corpus()
    default = tmp_path / "default.csv"
    explicit = tmp_path / "all.csv"
    assert to_review_table(corpus, default) == len(EXPECTED_ALL)
    assert to_review_table(corpus, explicit, selection="all") == len(EXPECTED_ALL)
    assert _read_rows(default) == EXPECTED_ALL
    assert default.read_bytes() == explicit.read_bytes()


def test_selection_preserves_custom_source_key_and_flag_precedence(tmp_path: Path) -> None:
    records = [
        {"lemma_source": "unresolved", "other_source": "attested", "lemma_known": "false"},
        {"lemma_source": "attested", "other_source": "identity"},
        {"other_source": "unresolved", "review_recommended": "FALSE"},
        {"other_source": "attested", "review_recommended": "true", "lemma_verified": "true"},
        {"lemma_known": "false"},
    ]
    tokens = [Token(text=f"token-{i}", kind=TokenKind.WORD, position=i, annotations=a)
              for i, a in enumerate(records)]
    corpus = Corpus(
        [Document(id="d", script_id="greek", tokens=tokens, lines=[list(range(len(tokens)))])],
        script_id="greek",
    )
    before = corpus.to_json()
    assert [needs_review_flag(a, source_key="other_source") for a in records] == [
        False, True, False, True, True,
    ]
    for selection, positions, flags in [
        ("all", ["0", "1", "2", "3", "4"], ["", "yes", "", "yes", "yes"]),
        ("flagged", ["1", "3", "4"], ["yes", "yes", "yes"]),
        ("unverified", ["0", "1", "2", "4"], ["", "yes", "", "yes"]),
    ]:
        path = tmp_path / f"{selection}.csv"
        assert to_review_table(
            corpus, path, source_key="other_source", selection=selection,
        ) == len(positions)
        rows = _read_rows(path)
        assert [row["position"] for row in rows] == positions
        assert [row["needs_review"] for row in rows] == flags
        assert [row["evidence_class"] for row in rows] == [
            records[int(position)].get("other_source", "") for position in positions
        ]
    assert corpus.to_json() == before


@pytest.mark.parametrize("invalid", ["", "All", "unknown", "flagged ", True, False, None])
@pytest.mark.parametrize("exists", [False, True])
def test_api_invalid_selection_leaves_destination_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: object, exists: bool,
) -> None:
    import aegean.io.review as review

    path = tmp_path / "review.csv"
    original = b"existing destination\x00\xff\n"
    if exists:
        path.write_bytes(original)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("invalid selection must not inspect tokens or write output")

    monkeypatch.setattr(review, "needs_review_flag", forbidden)
    monkeypatch.setattr(review, "_write_review_rows", forbidden)
    with pytest.raises(ValueError, match="selection must be 'all', 'flagged', or 'unverified'"):
        to_review_table(_corpus(), path, selection=invalid)  # type: ignore[arg-type]
    assert path.exists() is exists
    if exists:
        assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == ([path] if exists else [])


@pytest.mark.parametrize("invalid", ["All", "unknown", "flagged ", ""])
@pytest.mark.parametrize("exists", [False, True])
def test_cli_rejects_invalid_selection_before_load_annotate_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str, exists: bool,
) -> None:
    path = tmp_path / "review.csv" if exists else tmp_path / "new-dir" / "review.csv"
    original = b"existing destination\x00\xff\n"
    if exists:
        path.write_bytes(original)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("invalid selection must fail before loading, annotating, or writing")

    monkeypatch.setattr(_review, "load_corpus", forbidden)
    monkeypatch.setattr(_review, "_activate", forbidden)
    monkeypatch.setattr(_review, "writing", forbidden)
    monkeypatch.setattr(greek, "annotate_corpus", forbidden)
    result = CliRunner().invoke(_build_app(), [
        "review", "export", "not-a-corpus", "-o", str(path), "--selection", invalid,
        "--annotate", "--neural",
    ])
    assert result.exit_code == 1, result.output
    assert "--selection must be 'all', 'flagged', or 'unverified'" in result.output
    assert "Traceback" not in result.output
    assert isinstance(result.exception, SystemExit)
    assert path.exists() is exists
    if exists:
        assert path.read_bytes() == original
    else:
        assert not path.parent.exists()


@pytest.mark.parametrize(("selection", "expected"), [
    (None, EXPECTED_ALL),
    ("all", EXPECTED_ALL),
    ("flagged", EXPECTED_FLAGGED),
    ("unverified", EXPECTED_UNVERIFIED),
])
def test_cli_api_selection_parity(
    tmp_path: Path,
    selection: Literal["all", "flagged", "unverified"] | None,
    expected: list[dict[str, str]],
) -> None:
    corpus = _corpus()
    source = tmp_path / "source.json"
    corpus.to_json(source)
    source_bytes = source.read_bytes()
    cli_path = tmp_path / "cli.csv"
    api_path = tmp_path / "api.csv"
    args = ["review", "export", str(source), "-o", str(cli_path)]
    if selection is not None:
        args.extend(["--selection", selection])
    result = CliRunner().invoke(_build_app(), args)
    assert result.exit_code == 0, result.output
    assert to_review_table(corpus, api_path, selection=selection or "all") == len(expected)
    assert _read_rows(cli_path) == expected
    assert cli_path.read_bytes() == api_path.read_bytes()
    assert source.read_bytes() == source_bytes


@pytest.mark.parametrize(("marker", "included"), [
    (True, True),
    (False, True),
    (None, True),
    (0, True),
    (1, True),
    (1.5, True),
    ([], True),
    (["true"], True),
    ({}, True),
    ({"value": "true"}, True),
    ("true", False),
    ("TRUE", False),
])
def test_json_loaded_verification_metadata_api_cli_parity(
    tmp_path: Path, marker: object, included: bool,
) -> None:
    token = Token(
        text="loaded-word", kind=TokenKind.WORD, position=0, line_no=0,
        annotations={"lemma": "loaded-pred", "lemma_source": "attested"},
    )
    corpus = Corpus(
        [Document(id="d", script_id="greek", tokens=[token], lines=[[0]])],
        script_id="greek",
        provenance=Provenance(source="fixture", license="test", citation="Fixture citation"),
    )
    serialized = corpus.to_json()
    assert isinstance(serialized, str)
    data = json.loads(serialized)
    data["documents"][0]["tokens"][0]["annotations"]["lemma_verified"] = marker
    source = tmp_path / "source.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    source_bytes = source.read_bytes()

    loaded = Corpus.from_json(source)
    before = loaded.to_json()
    loaded_marker = loaded.documents[0].tokens[0].annotations["lemma_verified"]
    assert type(loaded_marker) is type(marker)
    assert loaded_marker == marker
    all_path = tmp_path / "all.csv"
    expected_row = _expected_row(0, "loaded-word", "loaded-pred", evidence="attested")
    assert to_review_table(loaded, all_path, selection="all") == 1
    assert _read_rows(all_path) == [expected_row]

    api_path = tmp_path / "api.csv"
    expected = [expected_row] if included else []
    assert to_review_table(loaded, api_path, selection="unverified") == len(expected)
    assert _read_rows(api_path) == expected
    cli_path = tmp_path / "cli.csv"
    result = CliRunner().invoke(_build_app(), [
        "review", "export", str(source), "-o", str(cli_path), "--selection", "unverified",
    ])
    assert result.exit_code == 0, result.output
    assert result.exception is None
    assert "Traceback" not in result.output
    assert _read_rows(cli_path) == expected
    assert cli_path.read_bytes() == api_path.read_bytes()
    assert loaded.to_json() == before
    assert source.read_bytes() == source_bytes
    assert Corpus.from_json(source).to_json() == before


@pytest.mark.parametrize("via_cli", [False, True])
def test_correct_persist_reload_and_reexport_unverified(
    tmp_path: Path, via_cli: bool,
) -> None:
    corpus = _corpus()
    original = corpus.to_json()
    source = tmp_path / "source.json"
    corpus.to_json(source)
    source_bytes = source.read_bytes()
    review_path = tmp_path / "review.csv"
    fixed_path = tmp_path / "fixed.json"
    reexport_path = tmp_path / "remaining.csv"
    app = _build_app()
    runner = CliRunner()
    if via_cli:
        result = runner.invoke(app, [
            "review", "export", str(source), "-o", str(review_path),
            "--selection", "unverified",
        ])
        assert result.exit_code == 0, result.output
    else:
        assert to_review_table(corpus, review_path, selection="unverified") == 10
    rows = _read_rows(review_path)
    assert rows == EXPECTED_UNVERIFIED
    for row in rows:
        if row["token"] == "legacy-unresolved":
            row["correct_lemma"] = "changed-lemma"
        elif row["token"] == "resolved":
            row["correct_pos"] = "VERB"
        elif row["token"] == "user-no-marker":
            row["correct_lemma"] = row["pred_lemma"]  # an unchanged acceptance
    _write_rows(review_path, rows)

    if via_cli:
        result = runner.invoke(app, [
            "review", "apply", str(source), str(review_path), "-o", str(fixed_path),
            "--reviewer", "fixture-reviewer",
        ])
        assert result.exit_code == 0, result.output
    else:
        corrected = from_review_table(review_path, corpus, reviewer="fixture-reviewer")
        corrected.to_json(fixed_path)
    reloaded = Corpus.from_json(fixed_path)
    annotations = {t.text: t.annotations for t in reloaded.documents[0].tokens}
    lemma_expected = {
        "lemma": "changed-lemma", "lemma__pred": "legacy-pred",
        "lemma_source": "user", "lemma_source__pred": "unresolved",
        "lemma_resolved": "true", "lemma_verified": "true", "review_recommended": "false",
        "lemma_known": "true", "review_status": "corrected", "reviewed_by": "fixture-reviewer",
    }
    assert {key: annotations["legacy-unresolved"][key] for key in lemma_expected} == lemma_expected
    assert annotations["legacy-unresolved"]["lemma_review_decision"] == "correct"
    assert json.loads(annotations["legacy-unresolved"]["review_history"])[0]["prediction"] == "legacy-pred"
    resolved_before = corpus.documents[0].tokens[0].annotations
    pos_expected = {
        **resolved_before, "upos": "VERB", "upos__pred": "NOUN",
        "reviewed_by": "fixture-reviewer", "review_status": "corrected",
    }
    assert {key: annotations["resolved"][key] for key in pos_expected} == pos_expected
    assert annotations["resolved"]["upos_review_decision"] == "correct"
    assert annotations["resolved"]["upos_verified"] == "true"
    assert annotations["resolved"]["lemma_verified"] == "false"
    assert annotations["user-no-marker"] == corpus.documents[0].tokens[2].annotations
    assert "lemma_verified" not in annotations["user-no-marker"]
    assert corpus.to_json() == original
    assert source.read_bytes() == source_bytes

    if via_cli:
        result = runner.invoke(app, [
            "review", "export", str(fixed_path), "-o", str(reexport_path),
            "--selection", "unverified",
        ])
        assert result.exit_code == 0, result.output
    else:
        assert to_review_table(reloaded, reexport_path, selection="unverified") == 9
    expected_remaining = [
        dict(row, pred_pos="VERB") if row["token"] == "resolved" else row
        for row in EXPECTED_UNVERIFIED if row["token"] != "legacy-unresolved"
    ]
    assert _read_rows(reexport_path) == expected_remaining
    all_path = tmp_path / "all-corrected.csv"
    assert to_review_table(reloaded, all_path) == len(EXPECTED_ALL)
    corrected_row = next(r for r in _read_rows(all_path) if r["token"] == "legacy-unresolved")
    assert corrected_row["pred_lemma"] == "changed-lemma"
    assert corrected_row["evidence_class"] == "user"
    assert corrected_row["needs_review"] == ""
