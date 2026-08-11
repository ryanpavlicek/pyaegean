"""Sentence segmentation over typed tokens whose punctuation is glued to the word.

Corpus editions attach a sentence-final mark to the word it follows instead of
emitting a separate punctuation token, so the named segmentation policy has to
read the mark inside the word token. These tests pin which marks each policy
commits to, which dots never end a sentence, and the warning that replaces a
silently unsegmented run.
"""

from __future__ import annotations

import warnings

import pytest

from aegean.core.model import ReadingStatus, SourceAlignment, Token, TokenKind
from aegean.greek.pipeline import (
    _UNSEGMENTED_RUN_TOKENS,
    _policy_terminals,
    pipeline_tokens,
)
from aegean.greek.sentence_segmentation import _TERMINAL, segment_text

WEAK_MARKS = (";", "·", "·", ";")  # Greek question mark, ano teleia
STRONG_MARKS = (".", "!", "?")


def words(*texts: str, status: ReadingStatus = ReadingStatus.CERTAIN) -> list[Token]:
    """Build word tokens exactly as a corpus loader emits them: punctuation glued on."""
    return [Token(text, TokenKind.WORD, status=status) for text in texts]


def sentences(tokens: list[Token], policy: str = "default") -> list[int]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return [record.sentence for record in pipeline_tokens(tokens, sentence_policy=policy)]


# --- the defect: a glued mark must end the sentence ------------------------------


@pytest.mark.parametrize("policy", ["default", "prose", "verse", "inscription", "papyrus"])
def test_glued_strong_mark_ends_the_sentence_under_every_policy(policy: str) -> None:
    tokens = words("ἐν", "ἀρχῇ", "ἦν.", "ὁ", "λόγος.")
    assert sentences(tokens, policy) == [0, 0, 0, 1, 1]


def test_glued_mark_splits_only_at_the_mark_not_at_every_token() -> None:
    # A comma is not a terminal mark under any policy.
    assert sentences(words("ὁ", "λόγος,", "καὶ", "θεός.")) == [0, 0, 0, 0]
    assert sentences(words("ὁ", "λόγος.", "καὶ", "θεός.")) == [0, 0, 1, 1]


def test_record_count_and_order_are_preserved_when_splitting() -> None:
    tokens = words("α.", "β.", "γ")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        records = pipeline_tokens(tokens)
    assert [record.text for record in records] == ["α.", "β.", "γ"]
    assert [(record.sentence, record.index) for record in records] == [(0, 1), (1, 1), (2, 1)]


# --- the policy still decides which marks count ----------------------------------


@pytest.mark.parametrize("mark", WEAK_MARKS)
@pytest.mark.parametrize("policy", ["default", "prose", "verse"])
def test_weak_marks_end_a_sentence_under_the_committing_policies(
    policy: str, mark: str
) -> None:
    assert sentences(words(f"θεόν{mark}", "καί"), policy) == [0, 1]


@pytest.mark.parametrize("mark", WEAK_MARKS)
@pytest.mark.parametrize("policy", ["inscription", "papyrus"])
def test_weak_marks_stay_uncommitted_on_inscriptions_and_papyri(
    policy: str, mark: str
) -> None:
    assert sentences(words(f"θεόν{mark}", "καί"), policy) == [0, 0]


@pytest.mark.parametrize("policy", ["inscription", "papyrus"])
@pytest.mark.parametrize("mark", STRONG_MARKS)
def test_strong_marks_still_end_a_sentence_on_inscriptions_and_papyri(
    policy: str, mark: str
) -> None:
    assert sentences(words(f"θεόν{mark}", "καί"), policy) == [0, 1]


@pytest.mark.parametrize("policy", ["default", "prose", "verse", "inscription", "papyrus"])
@pytest.mark.parametrize("mark", sorted(_TERMINAL))
def test_glued_marks_match_the_same_policy_over_raw_source(policy: str, mark: str) -> None:
    """The typed path commits to exactly the marks the raw-source policy commits to."""
    raw = f"θεόν{mark} καί"
    expected = len(segment_text(raw, policy=policy).boundaries)
    assert len(set(sentences(words(f"θεόν{mark}", "καί"), policy))) == expected


def test_policy_terminals_are_taken_from_the_shared_definitions() -> None:
    for policy in ("default", "prose", "verse"):
        assert _policy_terminals(policy) == _TERMINAL
    for policy in ("inscription", "papyrus"):
        assert _policy_terminals(policy) == _TERMINAL & frozenset(".!?")
        assert not _policy_terminals(policy) & frozenset(WEAK_MARKS)


# --- dots that never end a sentence ----------------------------------------------


@pytest.mark.parametrize(
    "tokens",
    [
        ("cf.", "λόγος"),  # a known abbreviation
        ("κ.τ.λ.", "λόγος"),  # a dotted abbreviation chain
        ("pp.", "λόγος"),
        ("1.23", "μέτρον"),  # a dotted number
        ("λόγος...", "καί"),  # an ellipsis
        ("J.", "smith"),  # a Latin initial before a lower-case word
        ("3.", "16"),  # a citation number split across tokens
    ],
)
def test_protected_dots_do_not_end_a_sentence(tokens: tuple[str, ...]) -> None:
    assert len(set(sentences(words(*tokens)))) == 1


def test_terminal_dot_after_a_dotted_number_still_ends_the_sentence() -> None:
    assert sentences(words("1.23.", "μέτρον")) == [0, 1]


def test_a_mark_inside_a_token_is_not_a_sentence_end() -> None:
    # Only a mark that closes the token counts; an interior citation dot does not.
    assert sentences(words("Choer.489,12", "λόγος")) == [0, 0]


@pytest.mark.parametrize("closer", ['"', "”", ")", "]", "»", "⟧"])
def test_closing_punctuation_after_the_mark_still_ends_the_sentence(closer: str) -> None:
    assert sentences(words(f"λόγος.{closer}", "καί")) == [0, 1]


def test_papyrus_ignores_a_mark_inside_balanced_editorial_brackets() -> None:
    assert sentences(words("[λόγος.]", "καί"), "papyrus") == [0, 0]
    # The same token is a boundary once the brackets are not balanced around it.
    assert sentences(words("λόγος.", "καί"), "papyrus") == [0, 1]


@pytest.mark.parametrize(
    "status", [ReadingStatus.RESTORED, ReadingStatus.UNCLEAR, ReadingStatus.LOST]
)
def test_editorially_uncertain_word_token_is_not_an_observed_boundary(
    status: ReadingStatus,
) -> None:
    tokens = [
        Token("λόγος.", TokenKind.WORD, status=status),
        Token("καί", TokenKind.WORD),
    ]
    assert sentences(tokens) == [0, 0]


# --- behaviour that must not change ----------------------------------------------


def test_explicit_sentence_ids_still_win_over_glued_marks() -> None:
    def aligned(text: str, ordinal: int, sentence_id: str) -> Token:
        return Token(
            text,
            TokenKind.WORD,
            alignment=SourceAlignment(
                "d", sentence_id, str(ordinal), text, ordinal, ordinal + len(text), " ", text
            ),
        )

    tokens = [
        aligned("λόγος.", 0, "s1"),
        aligned("καί.", 1, "s1"),
        aligned("θεός", 2, "s2"),
    ]
    assert sentences(tokens) == [0, 0, 1]


def test_separate_punctuation_tokens_keep_their_existing_boundaries() -> None:
    tokens = [
        Token("λόγος", TokenKind.WORD),
        Token(".", TokenKind.PUNCT),
        Token("καί", TokenKind.WORD),
    ]
    assert sentences(tokens) == [0, 0, 1]
    editorial = [
        Token("λόγος", TokenKind.WORD),
        Token(".", TokenKind.PUNCT, status=ReadingStatus.RESTORED),
        Token("καί", TokenKind.WORD),
    ]
    assert sentences(editorial) == [0, 0, 0]


def test_unmarked_tokens_remain_one_sentence() -> None:
    assert sentences(words("Κοίσōνος", "στάλα", "ἔστασαν")) == [0, 0, 0]


# --- the long unsegmented run warns ----------------------------------------------


def test_long_run_without_a_committed_mark_warns_and_stays_one_sentence() -> None:
    tokens = words(*["λόγος"] * (_UNSEGMENTED_RUN_TOKENS + 1))
    with pytest.warns(UserWarning, match="no sentence-final mark"):
        records = pipeline_tokens(tokens)
    assert len({record.sentence for record in records}) == 1
    assert len(records) == _UNSEGMENTED_RUN_TOKENS + 1


def test_a_run_at_the_threshold_does_not_warn() -> None:
    tokens = words(*["λόγος"] * _UNSEGMENTED_RUN_TOKENS)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        assert len({record.sentence for record in pipeline_tokens(tokens)}) == 1


def test_a_long_but_segmented_document_does_not_warn() -> None:
    tokens = words(*(["λόγος", "καί", "θεός."] * 200))
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        records = pipeline_tokens(tokens)
    assert len({record.sentence for record in records}) == 200


def test_the_warning_names_the_policy_and_the_longest_run() -> None:
    tokens = words(*(["λόγος"] * 300 + ["θεός."] + ["καί"] * 400))
    with pytest.warns(UserWarning) as caught:
        pipeline_tokens(tokens, sentence_policy="inscription")
    message = str(caught[0].message)
    assert "'inscription'" in message
    assert "2 token run(s)" in message
    assert "longest 400 tokens" in message


# --- adversarial input ------------------------------------------------------------


def test_pathological_token_content_is_handled_without_a_traceback() -> None:
    # A degenerate run of dots is an ellipsis, never a sentence end.
    assert sentences(words("λόγος" + "." * 50_000, "καί")) == [0, 0]
    # A token made only of closing punctuation carries no terminal mark.
    assert sentences(words("λόγος", ")" * 5_000, "καί")) == [0, 0, 0]
    # A mark buried behind thousands of closers still ends the sentence.
    assert sentences(words("λόγος." + ")" * 5_000, "καί")) == [0, 1]


def test_a_token_that_is_only_a_terminal_mark_still_ends_the_sentence() -> None:
    # Loaders do not emit this, but a hand-built corpus can; it must not be dropped.
    assert sentences(words("λόγος", ".", "καί")) == [0, 0, 1]


def test_non_token_input_is_refused_with_a_clean_error() -> None:
    with pytest.raises(TypeError):
        pipeline_tokens(["λόγος."])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        pipeline_tokens("λόγος.")  # type: ignore[arg-type]


def test_unknown_policy_is_refused_before_any_backend_work() -> None:
    with pytest.raises(ValueError, match="unknown segmentation policy"):
        pipeline_tokens(words("λόγος."), sentence_policy="epigram")


# --- corpus-scale correctness -----------------------------------------------------


@pytest.mark.parametrize(
    "policy,expected",
    [("default", 65), ("prose", 65), ("verse", 65), ("inscription", 46), ("papyrus", 46)],
)
def test_nt_john_1_splits_at_exactly_its_committed_marks(policy: str, expected: int) -> None:
    """John 1 carries 46 periods, 12 Greek question marks and 7 ano teleia."""
    import aegean

    document = next(
        item for item in aegean.load("nt").documents if item.id == "John 1"
    )
    assert all(token.kind is TokenKind.WORD for token in document.tokens)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        records = pipeline_tokens(document.tokens, sentence_policy=policy)
    assert len(records) == len(document.tokens)
    assert len({record.sentence for record in records}) == expected
