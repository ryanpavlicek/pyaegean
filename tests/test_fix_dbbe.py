"""Correctness tests for the DBBE Byzantine book-epigram tagging fold builder.

``scripts/build_dbbe_fold.py`` converts the DBBE linguistic-annotation gold standard
(coswaele/ByzantineGreekDatasets, ``lingAnn_GS_medievalGreek.tsv`` — AGDT 9-position postag +
lemma over unedited Byzantine verse) to a UD CoNLL-U tagging fold using pyaegean's OWN
AGDT->UD converter. These tests pin the conversion OUTPUT on hand-built inputs (no network):
the tagset mapping (the ``c`` -> CCONJ/SCONJ split that dilemma's crude first-char map gets
wrong, ``l`` -> DET, ``u`` -> PUNCT with lemma = surface form, copular ``v`` staying VERB
without a tree), the token-selection reasons, sentence segmentation, the leakage predicate,
and an end-to-end build whose product loads under pyaegean's own ``load_conllu``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_dbbe_fold as bdf  # noqa: E402


# --- read_gold -------------------------------------------------------------------


def test_read_gold_parses_and_normalizes(tmp_path: Path) -> None:
    p = tmp_path / "g.tsv"
    # a normal 3-column row, a 2-column short row (missing lemma), a tab-only blank row
    p.write_text("Αἶνος\tn-----mn-\tαἶνος\nφῶς\tn-s---na-\n\t\t\n", encoding="utf-8")
    rows = bdf.read_gold(p)
    assert rows[0] == ("Αἶνος", "n-----mn-", "αἶνος")
    assert rows[1] == ("φῶς", "n-s---na-", "")  # short row: missing slots are empty
    assert rows[2] == ("", "", "")  # blank/tab-only row preserved for the segmenter


# --- token_reason ----------------------------------------------------------------


def test_token_reason_clean_word_and_punct() -> None:
    assert bdf.token_reason("λόγος", "n-s---mn-", "λόγος") is None
    assert bdf.token_reason("·", "u--------", "·") is None  # clean punctuation


def test_token_reason_flags_bad_tokens() -> None:
    assert bdf.token_reason("", "", "") == "empty"
    assert bdf.token_reason("μελι(...)α", "n-s---fn-", "μελι(...)α") == "illegible"
    assert bdf.token_reason("suprascr.", "u--------", "suprascr.") == "illegible"  # alpha in punct
    assert bdf.token_reason("κἀν", "c_crasis--------", "ἄν") == "malformed_tag"  # '_' artifact
    assert bdf.token_reason("ἀνάκτων", "n-pplusr--mg-", "ἄναξ") == "malformed_tag"  # len > 9
    # a short postag (missing trailing dashes) is usable — it is padded, not dropped
    assert bdf.token_reason("ευφραδεία", "n-s---fd", "εὐφράδεια") is None


# --- terminal punctuation + segmentation -----------------------------------------


def test_is_terminal() -> None:
    assert bdf._is_terminal("·", "u--------") is True  # ano teleia
    assert bdf._is_terminal(".", "u--------") is True
    assert bdf._is_terminal("+", "u--------") is True  # epigram marker
    assert bdf._is_terminal('","', "u--------") is False  # comma is non-terminal
    assert bdf._is_terminal("λόγος", "n-s---mn-") is False  # a word is never terminal


def test_segment_splits_on_terminal_and_blank() -> None:
    rows = [
        ("α", "n-s---mn-", "α"),
        ("·", "u--------", "·"),          # terminal → close sentence 1
        ("β", "n-s---mn-", "β"),
        ("", "", ""),                       # blank row → hard break, closes sentence 2
        ("γ", "n-s---mn-", "γ"),            # trailing, unterminated → sentence 3
    ]
    sents = bdf.segment(rows)
    assert [[t[0] for t in s] for s in sents] == [["α", "·"], ["β"], ["γ"]]


# --- the AGDT -> UD mapping (the core correctness surface) ------------------------


def _fields(block: str) -> list[list[str]]:
    return [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]


def test_sentence_to_conllu_tagset_mapping() -> None:
    # article, subordinating conj (ὡς), coordinating conj (καί under c), particle (τε under g),
    # a verb, and punctuation — one of each of the mapping's decision points.
    toks = [
        ("τῶν", "l-p---mg-", "ὁ"),
        ("ὡς", "c--------", "ὡς"),
        ("καὶ", "c--------", "καί"),
        ("τε", "g--------", "τε"),
        ("πρέπει", "v3spia---", "πρέπω"),
        ("·", "u--------", "·"),
    ]
    block, forms = bdf.sentence_to_conllu("dbbe:lingann@0", toks)
    rows = _fields(block)
    upos = [r[3] for r in rows]
    assert upos == ["DET", "SCONJ", "CCONJ", "PART", "VERB", "PUNCT"]
    # the c->SCONJ/CCONJ split is exactly what dilemma's first-char map (c->CCONJ) gets wrong
    assert rows[1][3] == "SCONJ" and rows[2][3] == "CCONJ"
    # article lemma preserved, XPOS is the padded 9-char tag, FEATS rendered from it
    assert rows[0][2] == "ὁ" and rows[0][4] == "l-p---mg-"
    assert rows[0][5] == "Case=Gen|Gender=Masc|Number=Plur"
    # punctuation lemma is the surface form (training convention), FEATS "_"
    assert rows[5][1] == "·" and rows[5][2] == "·" and rows[5][5] == "_"
    # placeholder tree: token 1 is root, the rest attach to it (never scored)
    assert rows[0][6] == "0" and rows[0][7] == "root"
    assert all(r[6] == "1" and r[7] == "dep" for r in rows[1:])
    assert forms == ("τῶν", "ὡς", "καὶ", "τε", "πρέπει", "·")


def test_copula_stays_verb_without_tree() -> None:
    # εἰμί would be AUX under a copular tree signal (a PNOM dependent); the tagging-only source
    # has no tree, so has_pnom_child=False and it scores VERB (the documented systematic cap).
    block, _ = bdf.sentence_to_conllu("dbbe:lingann@1", [("ἐστίν", "v3spia---", "εἰμί")])
    assert _fields(block)[0][3] == "VERB"


def test_short_tag_padded_to_nine() -> None:
    # an 8-char postag (missing the trailing degree dash) pads to a valid 9-char XPOS
    block, _ = bdf.sentence_to_conllu("dbbe:lingann@2", [("ευφραδεία", "n-s---fd", "εὐφράδεια")])
    row = _fields(block)[0]
    assert row[4] == "n-s---fd-" and row[3] == "NOUN"
    assert row[5] == "Case=Dat|Gender=Fem|Number=Sing"


# --- leakage predicate -----------------------------------------------------------


def test_is_leaked() -> None:
    keys = {("θεός", "λόγος"), ("μόνον",)}
    assert bdf.is_leaked(("θεός", "λόγος"), keys) is True
    assert bdf.is_leaked(("ἄλλος", "τις"), keys) is False
    # punctuation-stripped match: the full tuple has a punct token, the stripped one is in keys
    assert bdf.is_leaked(("θεός", "λόγος", "·"), keys) is True
    assert bdf.is_leaked(("anything",), set()) is False  # no reference data → never leaked


# --- end-to-end build ------------------------------------------------------------


def test_build_end_to_end(tmp_path: Path) -> None:
    from aegean.greek.ud import load_conllu

    tsv = tmp_path / "gold.tsv"
    tsv.write_text(
        # sentence 1: clean, terminated
        "Αἶνος\tn-----mn-\tαἶνος\n"
        "θεῶ\tn-s---md-\tθεός\n"
        "·\tu--------\t·\n"
        # sentence 2: contains an illegible WORD → whole sentence excluded
        "μελι(...)α\tn-s---fn-\tμελι(...)α\n"
        "λόγος\tn-s---mn-\tλόγος\n"
        ".\tu--------\t.\n"
        # sentence 3: a noise (empty-form) punctuation token is dropped, the words survive
        "φῶς\tn-s---na-\tφῶς\n"
        "\tu--------\t\n"
        "λάμπει\tv3spia---\tλάμπω\n"
        "+\tu--------\t+\n"
        # a punctuation-only trailing fragment → no_word
        "·\tu--------\t·\n",
        encoding="utf-8",
    )
    # training_dir has no jsonl → empty leakage key set (nothing excluded as leaked)
    conllu, manifest = bdf.build(tsv, tmp_path)

    assert manifest["excluded_sentences"].get("illegible") == 1
    assert "leaked" not in manifest["excluded_sentences"]  # no reference data present
    assert manifest["dropped_noise_punct_tokens"] == 1  # the empty-form punct in sentence 3
    assert manifest["sentences_kept"] == 2  # sentences 1 and 3 survive
    assert manifest["source_commit"] == bdf.REPO_COMMIT

    # the product is valid CoNLL-U that pyaegean's own loader accepts
    out = tmp_path / "out.conllu"
    out.write_text(conllu, encoding="utf-8")
    sents = load_conllu(out)
    assert len(sents) == 2
    # sentence 3 kept its 3 real tokens (the blank punct dropped)
    kept_forms = [t.form for t in sents[1].tokens]
    assert kept_forms == ["φῶς", "λάμπει", "+"]
    assert all(t.upos for s in sents for t in s.tokens)  # every token got a UPOS
