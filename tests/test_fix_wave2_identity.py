"""Recorded identity and export-schema contracts.

Three properties are pinned here:

* ``Corpus.fingerprint()`` is a hash of *content*. The installed package version
  must not reach it, or a corpus whose bytes never changed hashes differently
  after every upgrade (missing every cached analysis, and invalidating any hash a
  reader wrote down). A real dataset identity must still separate two revisions.
* The token/word DataFrame (and the CSV/Parquet exports over it) leads with the
  columns that say which token a row is, and carries the wide typed ``form_*`` /
  ``alignment_*`` blocks only when an exported token actually has that state.
* ``SegmentationResult`` projects exactly one sentence per boundary, in boundary
  order, in the object and in its JSON, so ``sentences[i]`` describes
  ``boundaries[i]``.

Several tests here deliberately break the thing being guarded and assert that the
guard notices; without that, a passing assertion proves nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus, _data_identity, _token_row
from aegean.core.model import Document, ReadingStatus, Token, TokenFormState, TokenKind
from aegean.core.provenance import Provenance
from aegean.greek.sentence_segmentation import (
    POLICY_RULES,
    SegmentationResult,
    segment_text,
)
from aegean.io.tabular import _progress_dataframe, to_csv

IDENTITY_COLUMNS = [
    "doc_id", "line_no", "position", "text", "kind", "status", "site", "period",
]


def _corpus(
    *,
    data_version: str = "",
    text: str = "λόγος",
    form_state: TokenFormState | None = None,
    alignment: object | None = None,
    annotations: dict[str, str] | None = None,
    kind: TokenKind = TokenKind.WORD,
) -> Corpus:
    token = Token(
        text,
        kind,
        line_no=0,
        position=0,
        annotations=dict(annotations or {}),
        form_state=form_state,
        alignment=alignment,
    )
    doc = Document(id="d1", script_id="greek", tokens=[token], lines=[[0]])
    return Corpus(
        [doc],
        script_id="greek",
        provenance=Provenance(source="s", data_version=data_version),
    )


# ── Corpus.fingerprint: content, not the installed release ───────────────────
def test_bundled_fingerprint_survives_a_release_bump() -> None:
    """The same bundled bytes hash the same after a version bump.

    Runs in a subprocess: it rebinds ``aegean.__version__`` and reloads a corpus
    loader, which would otherwise leak a re-registered loader into other tests."""
    probe = """
import importlib
import aegean
import aegean.scripts.lineara.loader as loader

before = aegean.load("lineara")
aegean.__version__ = "99.9.9"
importlib.reload(loader)
after = aegean.load("lineara")

assert before.provenance.data_version == "0.58.0", before.provenance.data_version
assert after.provenance.data_version == "99.9.9", after.provenance.data_version
assert len(before) == len(after) and len(before) > 0
assert before.fingerprint() == after.fingerprint(), "the package version reached the hash"
print("OK")
"""
    done = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "OK" in done.stdout


def test_a_release_label_contributes_nothing_but_a_dataset_identity_does() -> None:
    none_at_all = _corpus().fingerprint()
    assert _corpus(data_version="0.58.0").fingerprint() == none_at_all
    assert _corpus(data_version="99.9.9").fingerprint() == none_at_all
    assert _corpus(data_version="1").fingerprint() == none_at_all
    assert _corpus(data_version="1.2.0rc1").fingerprint() == none_at_all

    # A revision of the data itself still separates two corpora with equal tokens,
    # which is how the fetched corpora record their identity.
    one = _corpus(data_version="damos-corpus-v1@2015-05-19").fingerprint()
    two = _corpus(data_version="damos-corpus-v2@2026-01-01").fingerprint()
    assert one != two
    assert one != none_at_all


def test_stability_claim_fails_when_the_release_label_is_folded_back_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Break the fix: fold the raw ``data_version`` again, as before. The
    equal-fingerprints assertion above must then fail, or it proves nothing."""
    monkeypatch.setattr(
        "aegean.core.corpus._data_identity",
        lambda p: p.data_version if p is not None and p.data_version else "",
    )
    assert _corpus(data_version="0.58.0").fingerprint() != _corpus(
        data_version="99.9.9"
    ).fingerprint()


def test_fingerprint_still_separates_genuinely_different_content() -> None:
    assert _corpus(text="λόγος").fingerprint() != _corpus(text="λογος").fingerprint()
    lineara = aegean.load("lineara")
    assert lineara.fingerprint() != aegean.load("linearb").fingerprint()
    assert lineara.subset(["HT13"]).fingerprint() != lineara.fingerprint()
    assert lineara.copy().fingerprint() == lineara.fingerprint()


def test_data_identity_handles_odd_and_absent_provenance() -> None:
    assert _data_identity(None) == ""
    assert _data_identity(Provenance(source="s")) == ""
    # Not bare release numbers: a dated or hashed revision is a real identity.
    for value in ("2026-01-01", "v1", "1.0.0+build", "  ", "sigla-corpus-v4@9a5e4783"):
        assert _data_identity(Provenance(source="s", data_version=value)) == value


# ── tabular exports: identity first, no empty typed blocks ───────────────────
def _state() -> TokenFormState:
    return TokenFormState("λόγος", regularized="λόγος", normalized="λόγος")


def _alignment() -> object:
    from aegean.core.model import SourceAlignment

    return SourceAlignment(
        document_id="input",
        sentence_id="input:s0",
        source_token_id="input:t0:0-5",
        original_text="λόγος",
        start_char=0,
        end_char=5,
        whitespace_before="",
        normalized_text="λόγος",
    )


def test_token_frame_leads_with_identity_and_omits_unused_blocks() -> None:
    pytest.importorskip("pandas")
    frame = aegean.load("lineara").to_dataframe("token")
    assert list(frame.columns)[: len(IDENTITY_COLUMNS)] == IDENTITY_COLUMNS
    assert not [c for c in frame.columns if c.startswith(("form_", "alignment_"))]
    assert not [c for c in frame.columns if frame[c].isna().all()]


def test_each_typed_block_appears_exactly_when_a_token_carries_it() -> None:
    pytest.importorskip("pandas")
    plain = _corpus().to_dataframe("token")
    assert list(plain.columns) == IDENTITY_COLUMNS

    forms = _corpus(form_state=_state()).to_dataframe("token")
    assert list(forms.columns)[: len(IDENTITY_COLUMNS)] == IDENTITY_COLUMNS
    assert "form_diplomatic" in forms.columns
    assert forms["form_diplomatic"].iloc[0] == "λόγος"
    assert not [c for c in forms.columns if c.startswith("alignment_")]

    aligned = _corpus(alignment=_alignment()).to_dataframe("token")
    assert "alignment_start_char" in aligned.columns
    assert aligned["alignment_start_char"].iloc[0] == 0
    assert not [c for c in aligned.columns if c.startswith("form_")]

    both = _corpus(form_state=_state(), alignment=_alignment()).to_dataframe("token")
    assert list(both.columns)[: len(IDENTITY_COLUMNS)] == IDENTITY_COLUMNS
    assert {"form_diplomatic", "alignment_start_char"} <= set(both.columns)


def test_a_block_follows_the_tokens_the_level_actually_exports() -> None:
    """Form state on a punctuation token: the token frame carries the block, the
    word frame (which drops that token) does not."""
    pytest.importorskip("pandas")
    corpus = _corpus(text=".", kind=TokenKind.PUNCT, form_state=TokenFormState("."))
    assert "form_diplomatic" in corpus.to_dataframe("token").columns
    word_frame = corpus.to_dataframe("word")
    assert word_frame.empty
    assert not [c for c in word_frame.columns if c.startswith("form_")]


def test_annotations_follow_identity_and_never_displace_a_canonical_column() -> None:
    pytest.importorskip("pandas")
    corpus = _corpus(
        form_state=_state(),
        annotations={"text": "spoof", "form_diplomatic": "spoof", "lemma": "λόγος"},
    )
    frame = corpus.to_dataframe("token")
    columns = list(frame.columns)
    assert columns[: len(IDENTITY_COLUMNS)] == IDENTITY_COLUMNS
    assert len(columns) == len(set(columns))  # a clashing name is one column, not two
    row = frame.iloc[0]
    assert row["text"] == "λόγος"  # the token's text, not the annotation's
    assert row["form_diplomatic"] == "λόγος"  # the typed state, not the annotation's
    assert row["lemma"] == "λόγος"

    # With no clash, the annotations sit directly behind the identity columns.
    clean = _corpus(annotations={"lemma": "λόγος", "gloss": "word"}).to_dataframe("token")
    assert list(clean.columns) == [*IDENTITY_COLUMNS, "lemma", "gloss"]


def test_reading_status_is_still_carried_for_epigraphic_rows() -> None:
    pytest.importorskip("pandas")
    token = Token("[λόγος]", TokenKind.WORD, status=ReadingStatus.RESTORED, position=0)
    corpus = Corpus(
        [Document(id="d1", script_id="greek", tokens=[token], lines=[[0]])],
        script_id="greek",
    )
    assert corpus.to_dataframe("token")["status"].iloc[0] == "restored"


def test_csv_header_leads_with_identity_and_reads_back(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    path = tmp_path / "tokens.csv"
    to_csv(aegean.load("lineara"), path, level="token")
    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[: len(IDENTITY_COLUMNS)] == IDENTITY_COLUMNS
    assert not [c for c in header if c.startswith(("form_", "alignment_"))]


def test_progress_export_builds_the_same_frame_as_the_plain_path() -> None:
    """The progress-reporting export and ``to_dataframe`` share their row builders;
    ``DataFrame.equals`` compares column names, order, and values, so a divergent
    copy of either builder fails here."""
    pytest.importorskip("pandas")
    corpus = _corpus(
        form_state=_state(), alignment=_alignment(), annotations={"lemma": "λόγος"}
    )
    for level in ("document", "token", "word"):
        expected = corpus.to_dataframe(level)
        actual = _progress_dataframe(corpus, level, lambda done, total: None)
        assert actual.equals(expected), level
    for level in ("document", "token", "word"):
        plain = aegean.load("lineara").to_dataframe(level)
        assert _progress_dataframe(aegean.load("lineara"), level, lambda d, t: None).equals(plain)


def test_export_parity_check_notices_a_divergent_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Break the fix: give ``to_dataframe`` the old column order. The parity
    assertion above must then fail."""
    pytest.importorskip("pandas")
    corpus = _corpus(annotations={"lemma": "λόγος"})
    old_order = corpus.to_dataframe("token")[["text", "doc_id", "lemma"]]
    monkeypatch.setattr(Corpus, "to_dataframe", lambda self, level="document": old_order)
    assert not _progress_dataframe(corpus, "token", lambda d, t: None).equals(
        corpus.to_dataframe("token")
    )


def test_progress_export_rejects_an_unknown_level() -> None:
    pytest.importorskip("pandas")
    with pytest.raises(ValueError, match="level must be"):
        _progress_dataframe(_corpus(), "paragraph", lambda done, total: None)


def test_token_row_builder_keeps_identity_first_without_pandas() -> None:
    """The row contract holds in the builder itself, so it is testable with no
    optional dependency installed."""
    corpus = _corpus(annotations={"lemma": "λόγος"}, form_state=_state())
    document = corpus.documents[0]
    row = _token_row(document, document.tokens[0], form_state=True, alignment=False)
    assert list(row)[: len(IDENTITY_COLUMNS)] == IDENTITY_COLUMNS
    assert list(row)[len(IDENTITY_COLUMNS)] == "lemma"
    bare = _token_row(document, document.tokens[0], form_state=False, alignment=False)
    assert list(bare) == [*IDENTITY_COLUMNS, "lemma"]


# ── SegmentationResult: one sentence per boundary, in order ──────────────────
SOURCES = [
    "ἦν ὁ λόγος. καὶ θεὸς ἦν ὁ λόγος· οὗτος ἦν ἐν ἀρχῇ.",
    "τίς οὗτος; ὁ κύριος! ἀμήν",
    "μία μόνη πρότασις χωρὶς τέλους",
    "Choer.489,12 δεύτερον. τρίτον.",
    "«ἄλφα βῆτα.» γάμμα δέλτα;",
    # A boundary whose span is nothing but a delimiter. Without one of these the
    # non-empty assertion below passes even when the projection can return "".
    "λόγος. ; καί.",
    "λόγος. ... καί.",
]


def _alnum(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum())


def test_every_boundary_projects_exactly_one_sentence_at_its_own_index() -> None:
    for source in SOURCES:
        for policy in POLICY_RULES:
            result = segment_text(source, policy=policy)
            assert len(result.sentences) == len(result.boundaries), (source, policy)
            for boundary, sentence in zip(result.boundaries, result.sentences, strict=True):
                # Derived independently of the projection: it only drops terminal
                # punctuation, so the span's letters and digits must survive intact.
                assert _alnum(sentence) == _alnum(boundary.text(source))
                assert sentence


def test_json_boundaries_and_sentences_are_index_aligned() -> None:
    for source in SOURCES:
        payload = json.loads(segment_text(source).to_json())
        boundaries = payload["boundaries"]
        sentences = payload["sentences"]
        assert len(boundaries) == len(sentences)
        for boundary, sentence in zip(boundaries, sentences, strict=True):
            assert _alnum(sentence) == _alnum(source[boundary["start"] : boundary["end"]])
            assert _alnum(sentence) == _alnum(boundary["text"])


def test_alignment_check_notices_a_projection_that_drops_a_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Break the fix: filter the projection, as a dropping projection would. The
    one-per-boundary assertion above must then fail."""
    source = "ἦν ὁ λόγος. καὶ θεὸς ἦν."
    monkeypatch.setattr(
        SegmentationResult,
        "sentences",
        property(lambda self: tuple(self._project(b) for b in self.boundaries[1:])),
    )
    result = segment_text(source)
    assert len(result.boundaries) == 2
    assert len(result.sentences) != len(result.boundaries)


def test_from_dict_names_a_sentence_count_mismatch() -> None:
    payload = segment_text("ἦν ὁ λόγος. καὶ θεὸς ἦν.").to_dict()
    assert len(payload["sentences"]) == 2
    payload["sentences"] = payload["sentences"][:1]
    with pytest.raises(ValueError, match="2 boundaries and 1 sentences"):
        SegmentationResult.from_dict(payload)


def test_from_dict_rejects_a_sentence_that_is_not_its_boundary() -> None:
    payload = segment_text("ἦν ὁ λόγος. καὶ θεὸς ἦν.").to_dict()
    payload["sentences"][1] = "something else"
    with pytest.raises(ValueError, match="do not match source spans"):
        SegmentationResult.from_dict(payload)


def test_round_trip_preserves_the_aligned_projection() -> None:
    for source in SOURCES:
        original = segment_text(source)
        restored = SegmentationResult.from_json(original.to_json())
        assert restored.sentences == original.sentences
        assert restored.boundaries == original.boundaries


def test_documented_fingerprints_reproduce():
    """A bundled fingerprint printed in the documentation must be the real one.

    The hash used to fold the package version, so every release silently invalidated the
    two hexes shown in the wiki; they were stale for roughly thirty releases and no guard
    noticed. Now that a bundled corpus has a stable data identity the value is durable, so
    it can be pinned: this fails if the identity changes without the documentation moving
    with it, which is the only way that drift can recur.
    """
    import re

    import aegean

    documented = {
        "wiki/Analysis.md": "lineara",
        "wiki/Architecture.md": "lineara",
    }
    root = Path(__file__).resolve().parents[1]
    hex16 = re.compile(r"fingerprint\(\)\[:16\][^\n]*?'([0-9a-f]{16})'")
    for relative, corpus_id in documented.items():
        text = (root / relative).read_text(encoding="utf-8")
        shown = hex16.findall(text)
        assert shown, f"{relative}: no fingerprint example found; update this guard"
        expected = aegean.load(corpus_id).fingerprint()[:16]
        for value in shown:
            assert value == expected, (
                f"{relative} shows fingerprint {value} but {corpus_id} hashes to {expected}"
            )
