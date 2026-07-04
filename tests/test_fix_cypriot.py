"""Regression tests: the Cypriot loader decodes the IG Leiden apparatus.

The IG XV 1 edition marks damaged-but-legible signs with a combining underdot, erasures
with ⟦⟧, editor-supplied text with square lacuna brackets or angle brackets, and
abbreviation expansions with parentheses. The loader maps them to `ReadingStatus`
(UNCLEAR / RESTORED / CERTAIN), strips every bracket from the emitted token text and
signs, and keeps the marked form in ``annotations["leiden"]``. The pinned examples below are
verified against the raw bundled source strings (which store the underdot as the
combining U+0323, so the expected marked forms are spelled with explicit escapes).
"""

from __future__ import annotations

import json
import unicodedata

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import ReadingStatus
from aegean.core.script import get_script

_UNDERDOT = "̣"  # combining dot below


def _doc(doc_id: str):
    corpus = aegean.load("cypriot")
    return next(d for d in corpus if d.id == doc_id)


# ── pinned inscriptions (raw source strings checked by eye) ─────────────────
def test_underdot_reads_unclear_and_is_stripped() -> None:
    # IG XV 1, 3 line 1 starts 'wi-ti-ḷẹ-ra-nu': the le sign is damaged but read.
    tok = _doc("IG XV 1, 3").tokens[0]
    assert tok.status is ReadingStatus.UNCLEAR
    assert tok.text == "wi-ti-le-ra-nu"                  # dot stripped from the emitted text
    assert tok.signs == ("wi", "ti", "le", "ra", "nu")   # sign labels are clean
    # the marked form is preserved exactly as the source stores it
    assert tok.annotations["leiden"] == "wi-ti-ḷẹ-ra-nu"


def test_brackets_read_restored_and_are_stripped() -> None:
    # IG XV 1, 192 line 3: '[ta]' is wholly editor-supplied; 'ẹ-ṃị' before it is damaged.
    doc = _doc("IG XV 1, 192")
    ta = doc.tokens[3]
    assert ta.status is ReadingStatus.RESTORED
    assert ta.text == "ta" and ta.signs == ("ta",)
    assert ta.annotations["leiden"] == "[ta]"
    emi = doc.tokens[2]
    assert emi.status is ReadingStatus.UNCLEAR and emi.text == "e-mi"


def test_partly_restored_word_and_certain_twin() -> None:
    # IG XV 1, 91 alternates '[lu]-sa-to-ro' (line 3, restored lu) with plain
    # 'lu-sa-to-ro' (line 2): same clean text, different status.
    doc = _doc("IG XV 1, 91")
    plain, restored = doc.tokens[1], doc.tokens[2]
    assert plain.text == restored.text == "lu-sa-to-ro"
    assert plain.status is ReadingStatus.CERTAIN and not plain.annotations
    assert restored.status is ReadingStatus.RESTORED
    assert restored.annotations["leiden"] == "[lu]-sa-to-ro"
    # line 1 '[lu]-sa-ṭọ-ṛọ' carries both marks: the restoration bracket wins,
    # and both kinds of marker are stripped.
    both = doc.tokens[0]
    assert both.status is ReadingStatus.RESTORED
    assert both.text == "lu-sa-to-ro"
    assert both.annotations["leiden"] == "[lu]-sa-ṭọ-ṛọ"


def test_restoration_span_crosses_the_word_divider() -> None:
    # IG XV 1, 189 line 5 reads '[o ti]-ma-ko-ra-u': the bracket opens in one token
    # and closes in the next; both are (partly) supplied.
    doc = _doc("IG XV 1, 189")
    o, tima = doc.tokens[8], doc.tokens[9]
    assert (o.text, o.status) == ("o", ReadingStatus.RESTORED)
    assert tima.text == "ti-ma-ko-ra-u" and tima.status is ReadingStatus.RESTORED


def test_clean_inscription_stays_certain() -> None:
    # IG XV 1, 95 carries no apparatus at all: every token stays CERTAIN, unannotated.
    doc = _doc("IG XV 1, 95")
    assert doc.tokens[0].text == "ta-ma-ti-ri"
    assert all(t.status is ReadingStatus.CERTAIN and not t.annotations for t in doc.tokens)


# ── corpus-wide measurement ──────────────────────────────────────────────────
def test_corpus_status_distribution() -> None:
    corpus = aegean.load("cypriot")
    tokens = [t for d in corpus for t in d.tokens]
    counts = {s: sum(1 for t in tokens if t.status is s) for s in ReadingStatus}
    # UNCLEAR = underdotted (damaged but legible) + ⟦⟧ erasures + tokens with an illegibly-read
    # sign (a Leiden dot "..", a figure-dash "‒", an unread "?"); RESTORED = square-bracket
    # lacuna restorations + <> editorial insertions; LOST = a token that is entirely apparatus
    # (only illegible marks, nothing legibly read).
    assert counts[ReadingStatus.RESTORED] == 51
    assert counts[ReadingStatus.UNCLEAR] == 188
    assert counts[ReadingStatus.LOST] == 19
    assert counts[ReadingStatus.CERTAIN] == len(tokens) - 258
    # brackets/underdot never survive in the emitted text; NO apparatus marker (bracket,
    # illegible dot/dash, unread ?, direction ↓) survives in a sign label (illegible dots stay
    # in the token text to show a lost-sign position, but are never syllabograms)
    for t in tokens:
        assert not any(ch in t.text for ch in "[]⟦⟧<>()") and _UNDERDOT not in t.text
        assert all(s and not any(ch in s for ch in "[]⟦⟧<>().‒?↓") for s in t.signs)


def test_leiden_annotation_round_trips_to_the_clean_text() -> None:
    # Property: stripping the apparatus from the preserved marked form reproduces
    # the emitted text, so nothing else was altered.
    corpus = aegean.load("cypriot")
    seen = 0
    for d in corpus:
        for t in d.tokens:
            raw = t.annotations.get("leiden")
            if raw is None:
                continue
            seen += 1
            nfd = unicodedata.normalize("NFD", raw)
            bare = unicodedata.normalize("NFC", nfd.replace(_UNDERDOT, ""))
            for ch in "[]⟦⟧<>()":
                bare = bare.replace(ch, "")
            assert bare == t.text
    assert seen == 169  # every marker-carrying token keeps its marked form


def test_status_survives_the_json_round_trip() -> None:
    corpus = aegean.load("cypriot")
    again = Corpus.from_dict(json.loads(corpus.to_json()))
    doc = next(d for d in again if d.id == "IG XV 1, 192")
    assert doc.tokens[3].status is ReadingStatus.RESTORED
    assert doc.tokens[3].annotations["leiden"] == "[ta]"


def test_tokenize_decodes_the_apparatus_too() -> None:
    # The Script.tokenize path uses the same classifier (no span state, but per-token
    # marks are decoded).
    toks = get_script("cypriot").tokenize("wi-ti-ḷẹ-ra-nu [ta]")
    assert toks[0].text == "wi-ti-le-ra-nu" and toks[0].status is ReadingStatus.UNCLEAR
    assert toks[1].text == "ta" and toks[1].status is ReadingStatus.RESTORED


# ── the illegible-sign / notation apparatus (IG XV 1 Leiden conventions) ──────
def test_illegible_dots_are_not_signs_and_read_unclear() -> None:
    from aegean.core.model import TokenKind
    from aegean.scripts.cypriot.loader import classify

    # a Leiden dot on the line marks an illegible sign (a dot-run "..-.." = several); the dots
    # are kept in the token text (to show a lost-sign position) but are never syllabograms, and
    # the token reads UNCLEAR, not CERTAIN.
    t = classify("i-te-o-..-..-..-ja", 0, 0)
    assert t.kind is TokenKind.WORD
    assert t.signs == ("i", "te", "o", "ja")           # the "..".. are not signs
    assert t.text == "i-te-o-..-..-..-ja"               # kept in the text
    assert t.status is ReadingStatus.UNCLEAR
    # a token that is only illegible dots is LOST, with no signs
    lost = classify("..", 0, 0)
    assert lost.signs == () and lost.status is ReadingStatus.LOST


def test_figure_dash_and_trailing_period_are_not_signs() -> None:
    from aegean.scripts.cypriot.loader import classify

    # the figure-dash "‒" fills a lost-sign slot (here inside a lacuna) — not a syllabogram
    t = classify("‒]-se", 0, 0)
    assert "se" in t.signs and all("‒" not in s for s in t.signs)
    # a trailing period is stripped off the sign label (se. -> se)
    assert classify("ti-ma-ko-ra-se.", 0, 0).signs == ("ti", "ma", "ko", "ra", "se")


def test_direction_arrow_and_unread_marker() -> None:
    from aegean.core.model import TokenKind
    from aegean.scripts.cypriot.loader import classify

    # ↓ is a writing-direction marker, not a sign: no signs, flagged as notation
    arrow = classify("↓", 0, 0)
    assert arrow.kind is TokenKind.UNKNOWN and arrow.signs == ()
    assert arrow.annotations.get("note") == "writing-direction marker"
    # a bare "?" is an unread sign: no legible reading -> LOST, no signs
    q = classify("?", 0, 0)
    assert q.signs == () and q.status is ReadingStatus.LOST
