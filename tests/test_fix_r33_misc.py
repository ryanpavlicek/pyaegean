"""Regression tests for three r33 fixes.

1. `perseus.canonical_citation` deduplicates comma-list refs with the same
   order-preserving logic `load_work` uses, so the citation lists exactly the
   distinct sections loaded (``"1.1,1.1"`` loads one document and cites one).
2. `io.review` credits a reviewer whose name contains a comma (``"Smith, John"``)
   as one person in the merged provenance note, never re-splitting a joined cell.
3. The Cypriot `analysis` docstrings frame low bridge coverage as a joint fact
   about lexicon scope AND corpus language composition (Eteocypriot / onomastic
   content in IG XV 1), not solely a fact about the lexicon's scope.
"""

from __future__ import annotations

import csv
from pathlib import Path

from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import (
    apply_merged,
    from_review_table,
    merge_review_tables,
    to_review_table,
)
from aegean.io.review import REVIEW_COLUMNS
from aegean.scripts.greek.perseus import canonical_citation, parse_tei_work

# The authored TEI fixture the offline work-addressing tests use: book 1 (two
# verse <l> lines 1.1 / 1.2) + chapter 2 (two <p> blocks).
BLOB = (Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml").read_bytes()


# ── (1) canonical_citation dedups comma-list refs, matching the loaded docs ──


def test_canonical_citation_dedups_exact_duplicate_refs() -> None:
    ref = "1.1,1.1"
    # load_work path: an exact-duplicate comma entry loads ONE document
    _, _, docs = parse_tei_work(BLOB, "w", ref=ref)
    assert [d.id for d in docs] == ["w:1.1"]
    # the citation must list exactly that one distinct section, not "1.1; 1.1"
    assert canonical_citation("tlg0012.tlg001", ref, "Homer", "Iliad") == "Homer, Iliad 1.1"


def test_canonical_citation_preserves_order_and_drops_a_shuffled_duplicate() -> None:
    ref = "1.2,1.1,1.2"
    _, _, docs = parse_tei_work(BLOB, "w", ref=ref)
    # source order kept, the repeated "1.2" collapses -> two distinct documents
    assert [d.id for d in docs] == ["w:1.2", "w:1.1"]
    # the citation echoes exactly those two, in the same order
    assert (
        canonical_citation("tlg0012.tlg001", ref, "Homer", "Iliad") == "Homer, Iliad 1.2; 1.1"
    )


def test_canonical_citation_distinct_refs_still_joined_with_semicolons() -> None:
    # the plain multi-ref case is unchanged (no false dedup of distinct entries)
    assert (
        canonical_citation("tlg0012.tlg001", "1.1,1.5", "Homer", "Iliad")
        == "Homer, Iliad 1.1; 1.5"
    )


# ── (2) a comma-bearing reviewer name is credited as one person ──────────────


def _corpus() -> Corpus:
    toks = [
        Token(text="ἦν", kind=TokenKind.WORD, line_no=0, position=0,
              annotations={"lemma": "εἰμί", "upos": "VERB"}),
        Token(text="ὁ", kind=TokenKind.WORD, line_no=0, position=1,
              annotations={"lemma": "ὁ", "upos": "DET"}),
        Token(text="λόγος", kind=TokenKind.WORD, line_no=0, position=2,
              annotations={"lemma": "λόγος", "upos": "NOUN"}),
    ]
    doc = Document(id="d", script_id="greek", tokens=toks, lines=[[0, 1, 2]])
    return Corpus([doc], provenance=Provenance(source="t", license="x", citation="Test 2026"),
                  script_id="greek")


def _read(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REVIEW_COLUMNS))
        w.writeheader()
        w.writerows(rows)


def _copy(path: Path, corpus: Corpus, edits: dict[str, dict[str, str]]) -> Path:
    to_review_table(corpus, path)
    rows = _read(path)
    for r in rows:
        for col, val in edits.get(r["token"], {}).items():
            r[col] = val
    _write(path, rows)
    return path


def _annotations(corpus: Corpus) -> dict[str, dict[str, str]]:
    return {t.text: dict(t.annotations) for doc in corpus.documents for t in doc.tokens}


def test_merged_note_credits_comma_bearing_reviewer_as_one_person(tmp_path) -> None:
    c = _corpus()
    # two reviewers on disjoint tokens; one reviewer's name contains a comma
    smith = _copy(tmp_path / "smith.csv", c,
                  {"λόγος": {"correct_lemma": "λέξις", "reviewer": "Smith, John"}})
    alice = _copy(tmp_path / "alice.csv", c,
                  {"ὁ": {"correct_lemma": "ho-fix", "reviewer": "Alice"}})

    merged = merge_review_tables([smith, alice], c)
    # the structured reviewer set keeps the comma-bearing name intact: exactly two people
    assert set(merged.reviewers) == {"Alice", "Smith, John"}
    assert len(merged.reviewers) == 2

    out = apply_merged(merged, c)
    ann = _annotations(out)
    assert ann["λόγος"]["reviewed_by"] == "Smith, John"   # attribution kept verbatim
    assert ann["ὁ"]["reviewed_by"] == "Alice"

    note = out.provenance.notes[-1]
    assert note.startswith("review: 2 tokens corrected by Alice, Smith, John")
    # the old bug split "Smith, John" and re-sorted every name -> "Alice, John, Smith"
    assert "Alice, John, Smith" not in note


def test_single_reviewer_comma_name_is_not_split(tmp_path) -> None:
    c = _corpus()
    path = tmp_path / "review.csv"
    to_review_table(c, path, reviewer="Smith, John")
    rows = _read(path)
    for r in rows:
        if r["token"] == "λόγος":
            r["correct_lemma"] = "λέξις"
    _write(path, rows)

    out = from_review_table(path, c)
    assert _annotations(out)["λόγος"]["reviewed_by"] == "Smith, John"
    note = out.provenance.notes[-1]
    assert note.startswith("review: 1 tokens corrected by Smith, John")
    assert "John, Smith" not in note  # the whole name, not split/reordered


# ── (3) Cypriot analysis docstrings frame corpus language composition ────────


def test_cypriot_analysis_docstrings_frame_language_composition() -> None:
    from aegean.scripts.cypriot import analysis

    mod_low = (analysis.__doc__ or "").lower()
    fn_low = (analysis.bridge_coverage.__doc__ or "").lower()

    # the module names the non-Greek / onomastic content of the IG XV 1 corpus
    assert "eteocypriot" in mod_low
    assert "onomastic" in mod_low
    # both docstrings frame low coverage as a JOINT fact (lexicon scope + language),
    # not solely a fact about the lexicon's scope
    assert "joint fact" in mod_low
    assert "joint fact" in fn_low
    assert "eteocypriot" in fn_low
    assert "language" in fn_low
