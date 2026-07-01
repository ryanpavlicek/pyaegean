"""Regression tests: the Cypriot loader decodes the IG Leiden apparatus.

The IG XV 1 edition marks damaged-but-legible signs with a combining underdot and
editorially supplied text with square lacuna brackets. The loader must map them to
`ReadingStatus.UNCLEAR` / `RESTORED`, strip the markers from the emitted token text,
and keep the marked form in ``annotations["leiden"]``. The pinned examples below are
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
    # 131 tokens carry underdots and 56 fall in restoration spans in the bundled IG
    # source; 13 carry both and land in RESTORED.
    assert counts[ReadingStatus.RESTORED] == 56
    assert counts[ReadingStatus.UNCLEAR] == 118
    assert counts[ReadingStatus.LOST] == 0
    assert counts[ReadingStatus.CERTAIN] == len(tokens) - 174
    # no apparatus characters leak into emitted text or sign labels
    for t in tokens:
        assert "[" not in t.text and "]" not in t.text and _UNDERDOT not in t.text
        assert all(s and "[" not in s and "]" not in s for s in t.signs)


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
            assert bare.replace("[", "").replace("]", "") == t.text
    assert seen == 165  # every marker-carrying token keeps its marked form


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
