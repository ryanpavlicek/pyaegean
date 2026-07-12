"""Correctness tests for the r44 DBBE fold-builder fixes (scripts/build_dbbe_fold.py).

Three fixes, each pinned on hand-built inputs (no network):

FIX 1 — non-linguistic marker glyphs the DBBE gold mis-filed under a WORD postag (``+`` /
``∙`` / ``※`` / ``᾽`` / ``‧`` / ``++:+`` as NOUN/CCONJ/PART/…) are the mirror of the
alphabetic-under-punct case: they are dropped in place (own counter), never scored. And a
standalone ``+`` is an epigram terminal recognised by FORM not tag, so a ``+`` mis-tagged as a
word still segments (the merged-epigram run-on splits).

FIX 2 — the register date range is the DBBE's documented 7th-15th c. scope, not 9th-15th c.

FIX 3 — the docstring's ``c`` -> SCONJ example is a form that genuinely resolves to SCONJ
(ἐπεί stays CCONJ under the converter's convention), and the subordinator-lexicon size is not
quoted with a brittle count.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_dbbe_fold as bdf  # noqa: E402

# the word-class marker glyphs as (form, postag) exactly as they occur in the pinned gold
_MARKERS = [
    ("+", "n-s---mg-"),   # + mis-tagged NOUN
    ("+", "d--------"),   # + mis-tagged ADV
    ("+", "g--------"),   # + mis-tagged PART
    ("∙", "c--------"),   # ∙ mis-tagged CCONJ
    ("᾽", "g--------"),   # koronis mis-tagged PART
    ("᾽", "r--------"),   # koronis mis-tagged ADP
    ("※", "c--------"),   # ※ mis-tagged CCONJ
    ("‧", "r--------"),   # ‧ mis-tagged ADP
    ("++:+", "p-s---ng-"),  # compound marker mis-tagged PRON
]


# --- FIX 1: token_reason mirror guard --------------------------------------------


def test_marker_glyphs_flagged_marker_glyph() -> None:
    # a non-alphabetic form under a WORD postag → the new marker_glyph reason
    for form, postag in _MARKERS:
        assert bdf.token_reason(form, postag, form) == "marker_glyph", (form, postag)


def test_marker_guard_does_not_touch_legitimate_tokens() -> None:
    # a real word (has letters) and clean punctuation are unaffected
    assert bdf.token_reason("λόγος", "n-s---mn-", "λόγος") is None
    assert bdf.token_reason("·", "u--------", "·") is None
    # an illegibility filler under a WORD postag stays 'illegible' (its own case, checked first)
    assert bdf.token_reason("(...)", "n-s---fn-", "(...)") == "illegible"
    # the mirror's original half: an alphabetic token mis-filed under punct stays 'illegible'
    assert bdf.token_reason("suprascr.", "u--------", "suprascr.") == "illegible"


# --- FIX 1: '+'-by-FORM terminal segmentation ------------------------------------


def test_plus_is_terminal_by_form_not_tag() -> None:
    # a '+' tagged as a WORD (not 'u') is still a terminal — recognised by form
    assert bdf._is_terminal("+", "g--------") is True
    assert bdf._is_terminal("+", "n-s---mg-") is True
    assert bdf._is_terminal("+", "u--------") is True
    # non-'+' word markers are NOT terminals (only '+' is the epigram terminal)
    assert bdf._is_terminal("∙", "c--------") is False
    assert bdf._is_terminal("λόγος", "n-s---mn-") is False


def test_segment_splits_on_word_tagged_plus() -> None:
    rows = [
        ("λόγος", "n-s---mn-", "λόγος"),
        ("+", "n-s---mg-", "+"),        # word-tagged '+' → split by FORM
        ("δῶρον", "n-s---na-", "δῶρον"),
    ]
    sents = bdf.segment(rows)
    assert [[t[0] for t in s] for s in sents] == [["λόγος", "+"], ["δῶρον"]]


# --- FIX 1: end-to-end build (drop the marker, keep the words) --------------------


def test_build_run_on_splits_and_drops_plus_marker(tmp_path: Path) -> None:
    from aegean.greek.ud import load_conllu

    # a merged run-on: prayer + word-tagged '+' + a second epigram, closed by a final stop.
    tsv = tmp_path / "gold.tsv"
    tsv.write_text(
        "λόγος\tn-s---mn-\tλόγος\n"
        "σοφός\ta-s---mn-\tσοφός\n"
        "+\tn-s---mg-\t+\n"          # word-tagged '+' → splits (FORM) AND is dropped (marker)
        "δῶρον\tn-s---na-\tδῶρον\n"
        "καλόν\ta-s---na-\tκαλόν\n"
        "·\tu--------\t·\n",
        encoding="utf-8",
    )
    conllu, manifest = bdf.build(tsv, tmp_path)  # empty training_dir → leakage disabled

    assert manifest["sentences_in_source"] == 2   # the '+' created a second source sentence
    assert manifest["sentences_kept"] == 2
    assert manifest["dropped_marker_glyph_tokens"] == 1
    assert "leaked" not in manifest["excluded_sentences"]
    assert manifest["tokens_kept"] == 5           # 2 + 3, the '+' not counted

    out = tmp_path / "out.conllu"
    out.write_text(conllu, encoding="utf-8")
    sents = load_conllu(out)
    assert [[t.form for t in s.tokens] for s in sents] == [
        ["λόγος", "σοφός"],            # the '+' dropped, prayer split off
        ["δῶρον", "καλόν", "·"],
    ]
    assert "+" not in {t.form for s in sents for t in s.tokens}


def test_build_inline_markers_dropped_sentence_kept(tmp_path: Path) -> None:
    from aegean.greek.ud import load_conllu

    # the five non-'+' marker glyphs, inline in one sentence: each dropped, the words survive.
    tsv = tmp_path / "gold.tsv"
    tsv.write_text(
        "λόγος\tn-s---mn-\tλόγος\n"
        "∙\tc--------\t∙\n"
        "σοφός\ta-s---mn-\tσοφός\n"
        "᾽\tg--------\t᾽\n"
        "※\tc--------\t※\n"
        "‧\tr--------\t‧\n"
        "καλός\ta-s---mn-\tκαλός\n"
        "++:+\tp-s---ng-\t++:+\n"
        ".\tu--------\t.\n",
        encoding="utf-8",
    )
    conllu, manifest = bdf.build(tsv, tmp_path)

    assert manifest["dropped_marker_glyph_tokens"] == 5
    assert manifest["sentences_kept"] == 1
    assert manifest["tokens_kept"] == 4

    out = tmp_path / "out.conllu"
    out.write_text(conllu, encoding="utf-8")
    (sent,) = load_conllu(out)
    assert [t.form for t in sent.tokens] == ["λόγος", "σοφός", "καλός", "."]


def test_build_plus_split_leaves_punct_only_no_word(tmp_path: Path) -> None:
    # mirror of the real @5 case: '... ἰωάννης + .' — splitting at the word-'+' leaves a
    # trailing '.' fragment that is punctuation-only → excluded as no_word (its '.' not scored).
    tsv = tmp_path / "gold.tsv"
    tsv.write_text(
        "ἰωάννης\tn-s---mn-\tἸωάννης\n"
        "+\tn-s---mg-\t+\n"
        ".\tu--------\t.\n",
        encoding="utf-8",
    )
    conllu, manifest = bdf.build(tsv, tmp_path)

    assert manifest["excluded_sentences"].get("no_word") == 1
    assert manifest["dropped_marker_glyph_tokens"] == 1
    assert manifest["dropped_noise_punct_tokens"] == 0
    assert manifest["sentences_kept"] == 1
    assert manifest["tokens_kept"] == 1
    assert conllu.count("# sent_id") == 1
    assert "\t+\t" not in conllu and "\t.\t" not in conllu  # neither the marker nor the '.'


# --- FIX 2: register date range ---------------------------------------------------


def test_docstring_date_range_is_7th_15th(tmp_path: Path) -> None:
    assert "7th-15th c." in bdf.__doc__
    assert "9th-15th c." not in bdf.__doc__
    # the manifest register string carries the corrected, documented scope
    tsv = tmp_path / "g.tsv"
    tsv.write_text("λόγος\tn-s---mn-\tλόγος\n·\tu--------\t·\n", encoding="utf-8")
    _, manifest = bdf.build(tsv, tmp_path)
    assert "7th-15th c." in manifest["register"]
    assert "9th-15th c." not in manifest["register"]


# --- FIX 3: the SCONJ docstring example + no brittle count ------------------------


def test_docstring_sconj_example_resolves_to_sconj() -> None:
    doc = bdf.__doc__
    # the example subordinator is one that genuinely resolves to SCONJ under the converter
    assert "ὅτι" in doc
    assert "ἐπεί" not in doc            # the false example is gone
    assert "67-form" not in doc         # the brittle (wrong) count is gone
    # prove the doc claim is now accurate against the actual converter
    assert bdf.upos_from_xpos("ὅτι", "c--------") == "SCONJ"
    assert bdf.upos_from_xpos("ἵνα", "c--------") == "SCONJ"
    assert bdf.upos_from_xpos("ἐπεί", "c--------") == "CCONJ"  # why ἐπεί was wrong to cite
