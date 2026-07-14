"""A7 sentence-segmentation contract and whole-path regression tests."""

from __future__ import annotations

import pytest

from aegean.core.model import ReadingStatus, SourceAlignment, Token, TokenKind
from aegean.greek import (
    POLICY_IDS,
    POLICY_RULES,
    SegmentationResult,
    SentenceBoundary,
    RuleBasedSentenceSegmenter,
    segment_text,
    sentences,
    tokenize_aligned,
)
from aegean.greek.pipeline import pipeline, pipeline_tokens
from aegean.greek.runtime import GreekPipeline


def test_legacy_sentences_drop_terminal_marks_but_rich_spans_retain_them() -> None:
    text = "λόγος. ἄνθρωπος; τέλος!"
    assert sentences(text) == ["λόγος", "ἄνθρωπος", "τέλος"]
    result = segment_text(text)
    assert [result.source[b.start : b.end] for b in result.boundaries] == [
        "λόγος.",
        "ἄνθρωπος;",
        "τέλος!",
    ]
    assert all(boundary.confidence is None for boundary in result.boundaries)


def test_dotted_abbreviations_and_numeric_forms_do_not_false_split() -> None:
    assert sentences("π.χ. λέγει. 1.23 μέτρον") == ["π.χ. λέγει", "1.23 μέτρον"]
    assert sentences("1.23") == ["1.23"]
    assert sentences("ἄριθμος 1.2.3") == ["ἄριθμος 1.2.3"]


def test_verse_policy_uses_absolute_line_offsets() -> None:
    result = segment_text("  α\nβ", policy="verse")
    assert [(item.start, item.end) for item in result.boundaries] == [(2, 3), (4, 5)]


def test_inscription_and_papyrus_keep_weak_marks_conservative() -> None:
    assert len(segment_text("α; β", policy="default").boundaries) == 2
    assert len(segment_text("α; β", policy="inscription").boundaries) == 1
    assert len(segment_text("α; β", policy="papyrus").boundaries) == 1


def test_plugin_output_is_validated_and_stamped() -> None:
    result = segment_text("α β", segmenter=lambda text: [(0, len(text))])
    assert result.provenance == "plugin"
    assert result.boundaries[0].provenance == "plugin"
    with pytest.raises(ValueError, match="cover"):
        segment_text("α β", segmenter=lambda text: [(0, 1)])
    with pytest.raises(ValueError, match="confidence"):
        segment_text("α β", segmenter=lambda text: [{"start": 0, "end": 3, "confidence": 2}])
    confidence = segment_text("α β", segmenter=lambda text: [(0, len(text), 0.8)])
    assert confidence.boundaries[0].confidence == 0.8
    with pytest.raises(ValueError, match="policy must match"):
        segment_text("α β", segmenter=lambda text: [(0, len(text), "verse")])
    with pytest.raises(ValueError, match="both boundaries and segments"):
        segment_text(
            "α β",
            segmenter=lambda text: {
                "boundaries": [(0, len(text))],
                "segments": [(0, len(text))],
            },
        )
    with pytest.raises(ValueError, match="overlapping"):
        segment_text("αβγ", segmenter=lambda text: [(0, 2), (1, 3)])
    with pytest.raises(ValueError, match="outside"):
        segment_text("αβγ", segmenter=lambda text: [(0, 4)])

    class HostileDiscovery:
        @property
        def segment(self) -> object:
            raise RuntimeError("hostile discovery")

    with pytest.raises(ValueError, match="discovery"):
        segment_text("α", segmenter=HostileDiscovery())

    class HostileIdentity:
        @property
        def policy_id(self) -> str:
            raise RuntimeError("hostile identity")

        def segment(self, text: str) -> list[tuple[int, int]]:
            return [(0, len(text))]

    with pytest.raises(ValueError, match="policy identity"):
        segment_text("α", segmenter=HostileIdentity())


def test_aligned_tokenization_and_pipeline_share_sentence_ids() -> None:
    text = "λόγος. ἄνθρωπος!"
    tokens = tokenize_aligned(text, document_id="a7")
    records = pipeline(text, document_id="a7")
    assert [token.alignment.sentence_id for token in tokens] == [
        record.alignment.sentence_id for record in records
    ]
    terminal = [record for record in records if record.boundary_policy is not None]
    assert [record.boundary_provenance for record in terminal] == ["rule", "rule"]
    assert [(record.boundary_start_char, record.boundary_end_char) for record in terminal] == [
        (0, 6),
        (7, len(text)),
    ]


def test_explicit_sentence_id_runs_override_punctuation_and_reject_partial() -> None:
    def alignment(sentence_id: str | None, source_id: str, text: str, start: int) -> SourceAlignment:
        return SourceAlignment("d", sentence_id, source_id, text, start, start + len(text), "", text)

    tokens = [
        Token("α", TokenKind.WORD, alignment=alignment("s0", "0", "α", 0)),
        Token(".", TokenKind.PUNCT, alignment=alignment("s0", "1", ".", 1)),
        Token("β", TokenKind.WORD, alignment=alignment("s0", "2", "β", 2)),
    ]
    assert [record.sentence for record in pipeline_tokens(tokens)] == [0, 0, 0]
    partial = [tokens[0], Token("β", TokenKind.WORD)]
    with pytest.raises(ValueError, match="complete"):
        pipeline_tokens(partial)
    noncontiguous = [
        Token("α", TokenKind.WORD, alignment=alignment("s0", "3", "α", 3)),
        Token("β", TokenKind.WORD, alignment=alignment("s1", "4", "β", 4)),
        Token("γ", TokenKind.WORD, alignment=alignment("s0", "5", "γ", 5)),
    ]
    with pytest.raises(ValueError, match="contiguous"):
        pipeline_tokens(noncontiguous)

    def must_not_run(text: str) -> list[tuple[int, int]]:
        raise AssertionError("explicit sentence IDs must take precedence")

    assert [record.sentence for record in pipeline_tokens(tokens, segmenter=must_not_run)] == [
        0,
        0,
        0,
    ]


def test_result_is_immutable_and_json_ready() -> None:
    result = SegmentationResult("α", (SentenceBoundary(0, 1),))
    with pytest.raises((AttributeError, TypeError)):
        result.boundaries = ()  # type: ignore[misc]
    assert result.to_dict()["boundaries"][0]["text"] == "α"


def test_clusters_and_editorial_bracket_policy() -> None:
    assert sentences("λόγος.” καί") == ["λόγος”", "καί"]
    assert sentences("λόγος... καί") == ["λόγος... καί"]
    assert sentences("[λόγος.] καί.", sentence_policy="papyrus") == ["[λόγος.] καί"]
    assert len(segment_text("[λόγος. καί.", policy="papyrus").boundaries) == 2
    assert [token.alignment.sentence_id for token in tokenize_aligned("λόγος.— καί")] == [
        "input:sentence:0",
        "input:sentence:0",
        "input:sentence:1",
    ]
    assert sentences("λόγος.— καί") == ["λόγος—", "καί"]


def test_policy_ids_and_json_round_trip_are_strict() -> None:
    result = segment_text("λόγος.", policy="prose")
    restored = SegmentationResult.from_json(result.to_json())
    assert restored == result
    assert result.policy_id == POLICY_IDS["prose"]
    with pytest.raises(TypeError):
        POLICY_RULES["default"] = "spoof"  # type: ignore[index]
    with pytest.raises(ValueError, match="keys"):
        SegmentationResult.from_dict({**result.to_dict(), "extra": True})
    malformed_boundary = result.to_dict()
    del malformed_boundary["boundaries"][0]["schema_version"]
    with pytest.raises(ValueError, match="boundary keys"):
        SegmentationResult.from_dict(malformed_boundary)
    bool_schema = result.to_dict()
    bool_schema["schema_version"] = True
    with pytest.raises(ValueError, match="schema"):
        SegmentationResult.from_dict(bool_schema)

    with pytest.raises(TypeError, match="not one string"):
        RuleBasedSentenceSegmenter(abbreviations="cf.")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="word-like"):
        RuleBasedSentenceSegmenter(abbreviations=["..."])


def test_plugin_boundary_inside_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="bisects"):
        tokenize_aligned("λόγος", segmenter=lambda text: [(0, 2), (2, len(text))])


def test_plugin_cannot_spoof_reserved_rule_policy_identity() -> None:
    spoofed = SegmentationResult(
        "α β",
        (
            SentenceBoundary(
                0,
                3,
                policy="default",
                provenance="plugin",
                policy_id="caller-plugin-v1",
            ),
        ),
        policy="default",
        provenance="plugin",
        policy_id="caller-plugin-v1",
    )
    object.__setattr__(spoofed, "policy_id", POLICY_IDS["default"])
    result = segment_text("α β", segmenter=lambda text: spoofed)
    assert result.policy_id == "caller-plugin-unversioned"
    assert result.boundaries[0].policy_id == "caller-plugin-unversioned"

    class SubclassSpoof(RuleBasedSentenceSegmenter):
        def segment(self, text: str) -> SegmentationResult:
            return SegmentationResult(text, (SentenceBoundary(0, len(text)),))

    subclass_result = segment_text("α β", segmenter=SubclassSpoof())
    assert subclass_result.provenance == "plugin"
    assert subclass_result.policy_id == "caller-plugin-unversioned"

    built_in = RuleBasedSentenceSegmenter()
    with pytest.raises((AttributeError, TypeError)):
        built_in.policy = "papyrus"  # type: ignore[misc]

    class IdentifiedPlugin:
        policy_id = "edition-segmenter-v2"

        def segment(self, text: str) -> SegmentationResult:
            return SegmentationResult(
                text,
                (
                    SentenceBoundary(
                        0,
                        len(text),
                        provenance="plugin",
                    ),
                ),
                provenance="plugin",
            )

    identified = segment_text("α β", segmenter=IdentifiedPlugin())
    assert identified.policy_id == "edition-segmenter-v2"
    assert identified.boundaries[0].policy_id == "edition-segmenter-v2"


def test_typed_terminal_cluster_is_one_boundary() -> None:
    tokens = [
        Token("α", TokenKind.WORD),
        Token("?", TokenKind.PUNCT),
        Token("!", TokenKind.PUNCT),
        Token("β", TokenKind.WORD),
    ]
    records = pipeline_tokens(tokens)
    assert [record.sentence for record in records] == [0, 0, 0, 1]

    dash_cluster = [
        Token("λόγος", TokenKind.WORD),
        Token(".", TokenKind.PUNCT),
        Token("—", TokenKind.PUNCT),
        Token("καί", TokenKind.WORD),
    ]
    assert [record.sentence for record in pipeline_tokens(dash_cluster)] == [0, 0, 0, 1]


def test_typed_rules_match_raw_single_letter_and_papyrus_boundaries() -> None:
    ordinary = [
        Token("α", TokenKind.WORD),
        Token(".", TokenKind.PUNCT),
        Token("β", TokenKind.WORD),
    ]
    assert [record.sentence for record in pipeline_tokens(ordinary)] == [0, 0, 1]

    papyrus = [
        Token("[", TokenKind.PUNCT),
        Token("λόγος", TokenKind.WORD),
        Token(".", TokenKind.PUNCT),
        Token("]", TokenKind.PUNCT),
        Token("καί", TokenKind.WORD),
        Token(".", TokenKind.PUNCT),
    ]
    assert {
        record.sentence
        for record in pipeline_tokens(papyrus, sentence_policy="papyrus")
    } == {0}

    dotted_number = [Token("1.23", TokenKind.PUNCT), Token("μέτρον", TokenKind.WORD)]
    assert {record.sentence for record in pipeline_tokens(dotted_number)} == {0}
    terminal_number = [Token("1.23.", TokenKind.PUNCT), Token("μέτρον", TokenKind.WORD)]
    assert [record.sentence for record in pipeline_tokens(terminal_number)] == [0, 1]


@pytest.mark.parametrize(
    "status",
    [ReadingStatus.RESTORED, ReadingStatus.UNCLEAR, ReadingStatus.LOST],
)
def test_typed_editorial_punctuation_is_not_observed_boundary(
    status: ReadingStatus,
) -> None:
    tokens = [
        Token("α", TokenKind.WORD),
        Token(".", TokenKind.PUNCT, status=status),
        Token("β", TokenKind.WORD),
    ]
    assert {record.sentence for record in pipeline_tokens(tokens)} == {0}


def test_typed_aligned_boundaries_expose_only_proven_source_offsets() -> None:
    def aligned(text: str, ordinal: int, start: int, whitespace: str) -> Token:
        return Token(
            text,
            TokenKind.PUNCT if text == "." else TokenKind.WORD,
            alignment=SourceAlignment(
                "d",
                None,
                str(ordinal),
                text,
                start,
                start + len(text),
                whitespace,
                text,
            ),
        )

    records = pipeline_tokens(
        [aligned("λόγος", 0, 0, ""), aligned(".", 1, 5, ""), aligned("β", 2, 7, " ")]
    )
    assert (records[1].boundary_start_char, records[1].boundary_end_char) == (0, 6)
    assert (records[2].boundary_start_char, records[2].boundary_end_char) == (7, 8)
    unaligned = pipeline_tokens([Token("λόγος", TokenKind.WORD)])
    assert unaligned[0].boundary_start_char is None
    assert unaligned[0].boundary_end_char is None

    explicit = pipeline_tokens(tokenize_aligned("λόγος. βίβλος", document_id="d"))
    explicit_terminal = [record for record in explicit if record.boundary_policy is not None]
    assert [
        (record.boundary_start_char, record.boundary_end_char)
        for record in explicit_terminal
    ] == [(0, 6), (7, 13)]


def test_named_policy_rows_expose_boundary_identity() -> None:
    from aegean._view import pipeline_rows

    rows = pipeline_rows("α\nβ", sentence_policy="verse")
    assert rows[1]["boundary_policy_id"] == POLICY_IDS["verse"]


def test_baseline_parser_count_mismatch_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegean.greek import syntax

    class FakeTree:
        tokens = [object(), object()]

    monkeypatch.setattr(syntax, "parse", lambda text: FakeTree())
    with pytest.raises(ValueError, match="different token count"):
        GreekPipeline().analyze("λόγος.", parse=True)
