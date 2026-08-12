"""An unresolved sign position is not an attested sign, in SigLA and in Cypriot.

Two editions mark places where the scribe wrote something the editor does not read: a
SigLA ``blank`` attestation (transcribed ``*?``) and the Cypriot retrograde arrow ``↓``
of *Inscriptiones Graecae* XV 1, which records the direction of the next stretch of
text rather than a sign. Neither is a syllabogram, so the loaders leave both out of
``Token.signs``.

An empty ``Token.signs`` is not by itself enough to keep a token out of a sign count:
``analysis.stats._sign_labels`` falls back to the token's transliteration when a token
carries no decomposition, so a token that is nothing *but* such a marker re-enters the
sign stream as its own marker text. The rule that keeps it out is
``analysis.stats._bears_signs``, which drops a ``ReadingStatus.LOST`` token and every
``SEPARATOR``/``NUMERAL``/``PUNCT`` token. These tests pin each loader to the branch of
that rule its marker belongs in, and pin the resulting corpus-wide sign totals.

The status route is what SigLA needs: ``Token.kind`` decides the WORD count that
``training/results/corpus-facts.json`` pins, so a word of blanks stays a WORD token and
is excluded by its ``LOST`` status instead. The Cypriot arrow is not a sign position at
all, so it takes the kind route, agreeing with the Linear B loader's reading of the same
mark.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import aegean
import aegean.data as data
from aegean.analysis.stats import _bears_signs, _items_of
from aegean.core.model import ReadingStatus, TokenKind
from aegean.scripts.cypriot.loader import classify
from aegean.scripts.lineara import sigla
from aegean.scripts.linearb import loader as linearb_loader

_FACTS = json.loads(
    (Path(__file__).resolve().parent.parent / "training" / "results" / "corpus-facts.json")
    .read_text(encoding="utf-8")
)["corpora"]


# ── SigLA: a word of unresolved blanks ───────────────────────────────────────

def _sigla_doc(tmp_path, monkeypatch, atts):
    """One synthetic SigLA v2 document carrying ``atts`` (no network)."""
    payload = {
        "_meta": {"version": 2, "cite": "Fake.", "source_sha256": "ab" * 32},
        "documents": [{"id": "AP 1", "typology": "Tablet", "site": "S",
                       "period": "LM I", "attestations": atts}],
        "signs": [],
    }
    p = tmp_path / "sigla-corpus.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: p)
    return sigla.load_sigla().get("AP 1")


# a word with a surviving reading, a one-position blank word, and a two-position one
_BLANK_ATTS = [
    {"sign": "KU", "kind": "syllable", "word": 0},
    {"sign": "", "kind": "blank", "word": 0},
    {"sign": "NI", "kind": "syllable", "word": 0},
    {"sign": "", "kind": "blank", "word": 1},
    {"sign": "", "kind": "blank", "word": 2},
    {"sign": "", "kind": "blank", "word": 2},
]


def test_sigla_word_of_only_blanks_reads_lost_and_carries_no_signs(tmp_path, monkeypatch):
    """A word whose every position is an unresolved ``*?`` preserves no reading, so it
    reads LOST with empty signs; a word that still yields a sign around the blank keeps
    its UNCLEAR reading and its surviving labels."""
    doc = _sigla_doc(tmp_path, monkeypatch, _BLANK_ATTS)
    assert [t.text for t in doc.tokens] == ["KU-*?-NI", "*?", "*?-*?"]
    assert [t.signs for t in doc.tokens] == [("KU", "NI"), (), ()]
    assert [t.status for t in doc.tokens] == [
        ReadingStatus.UNCLEAR, ReadingStatus.LOST, ReadingStatus.LOST
    ]
    # the marker stays in the text of every one of them, marking the position
    assert all("*?" in t.text for t in doc.tokens)


def test_sigla_blank_word_stays_a_word_token(tmp_path, monkeypatch):
    """The exclusion is by status, not by kind: every one of these is still a WORD
    token, so the WORD count `training/results/corpus-facts.json` pins does not move."""
    doc = _sigla_doc(tmp_path, monkeypatch, _BLANK_ATTS)
    assert [t.kind for t in doc.tokens] == [TokenKind.WORD] * 3
    assert len(doc.words) == 3
    assert _items_of(doc, "words") == ["KU-*?-NI", "*?", "*?-*?"]


def test_sigla_blank_word_contributes_no_sign_item(tmp_path, monkeypatch):
    """The decisive claim: the sign stream holds the two read signs and nothing else.
    A two-position blank word is the case the transliteration fallback would split on
    its hyphen into two ``*?`` items, so it is counted here explicitly."""
    doc = _sigla_doc(tmp_path, monkeypatch, _BLANK_ATTS)
    assert _items_of(doc, "signs") == ["KU", "NI"]
    assert not any(_bears_signs(t) for t in doc.tokens if not t.signs)


def test_sigla_read_word_is_untouched_by_the_rule(tmp_path, monkeypatch):
    """A word with no blank in it is unaffected: CERTAIN, all its signs counted."""
    doc = _sigla_doc(tmp_path, monkeypatch, [
        {"sign": "KA", "kind": "syllable", "word": 0},
        {"sign": "U", "kind": "syllable", "word": 0},
        {"sign": "*302+*10", "kind": "logogram", "word": None},
    ])
    assert [t.status for t in doc.tokens] == [ReadingStatus.CERTAIN] * 2
    assert _items_of(doc, "signs") == ["KA", "U", "*302+*10"]


# ── Cypriot: the writing-direction arrow ─────────────────────────────────────

def test_cypriot_direction_marker_is_a_separator_carrying_no_signs():
    """``↓`` and ``↓?`` record which way the text runs, not a reading: a SEPARATOR
    with no signs, the marker kept in the token text and named in its annotations."""
    for text in ("↓", "↓?"):
        tok = classify(text, 0, 0)
        assert tok.kind is TokenKind.SEPARATOR, text
        assert tok.text == text and tok.signs == ()
        assert tok.annotations.get("note") == "writing-direction marker"
        assert not _bears_signs(tok)


def test_cypriot_direction_marker_agrees_with_linear_b():
    """Both editions print the arrow, and both loaders read it as apparatus that
    contributes no sign, so one sign stream is not two conventions."""
    cypriot_arrow = classify("↓", 0, 0)
    linearb_arrow = linearb_loader.classify("↓", 0, 0)
    assert cypriot_arrow.kind is linearb_arrow.kind is TokenKind.SEPARATOR
    assert cypriot_arrow.signs == linearb_arrow.signs == ()
    assert not _bears_signs(cypriot_arrow) and not _bears_signs(linearb_arrow)


def test_cypriot_reading_beside_a_direction_marker_is_untouched():
    """The arrow's own document keeps every syllabogram it does read."""
    doc = aegean.load("cypriot").get("IG XV 1, 47")
    assert [t.text for t in doc.tokens] == ["la-so", "↓"]
    assert _items_of(doc, "signs") == ["la", "so"]
    # the reading beside it keeps its own kind and editorial status
    assert doc.tokens[0].kind is TokenKind.WORD
    assert doc.tokens[0].status is ReadingStatus.UNCLEAR


def test_cypriot_illegible_and_direction_marks_take_different_routes():
    """An illegible run is a lost reading (``LOST``); the arrow is notation about the
    object, so calling it lost would claim damage the edition does not report. Both
    end outside the sign stream, by the two branches of the one rule."""
    illegible = classify("..", 0, 0)
    arrow = classify("↓", 0, 0)
    assert illegible.status is ReadingStatus.LOST
    assert illegible.kind is TokenKind.UNKNOWN
    assert arrow.status is not ReadingStatus.LOST
    assert arrow.kind is TokenKind.SEPARATOR
    assert not _bears_signs(illegible) and not _bears_signs(arrow)


# ── corpus-wide ──────────────────────────────────────────────────────────────

def test_cypriot_corpus_sign_stream_holds_no_apparatus():
    """The bundled Cypriot corpus counts 1,774 signs, none of them a direction arrow,
    with its pinned document/token/word facts unmoved."""
    c = aegean.load("cypriot")
    items = [s for d in c for s in _items_of(d, "signs")]
    assert len(items) == 1774
    assert "↓" not in items and "↓?" not in items
    facts = _FACTS["cypriot"]
    ntok = sum(len(d.tokens) for d in c)
    nwords = sum(len(d.words) for d in c)
    assert (len(c), ntok, nwords) == (
        facts["documents"], facts["tokens"], facts["words"]
    )


_SIGLA_CACHED = data.is_downloaded(data._REMOTE["sigla-corpus"], data.cache_dir())


@pytest.mark.skipif(not _SIGLA_CACHED, reason="sigla-corpus not cached (no network in CI)")
def test_sigla_corpus_sign_stream_holds_no_unresolved_position():
    """On the real SigLA asset the sign stream counts 4,372 signs over 321 distinct
    labels, none of them the unresolved ``*?``, with the pinned document/token/word
    facts unmoved. The 119 words of blanks read LOST; nothing else changes status."""
    c = aegean.load("sigla")
    facts = _FACTS["sigla"]
    if len(c) != facts["documents"]:
        pytest.skip("cached sigla asset predates the v4 refresh")
    items = [s for d in c for s in _items_of(d, "signs")]
    assert len(items) == 4372
    assert len(set(items)) == 321
    assert "*?" not in items
    counts = {s: sum(1 for d in c for t in d.tokens if t.status is s) for s in ReadingStatus}
    assert counts[ReadingStatus.CERTAIN] == 2296
    assert counts[ReadingStatus.UNCLEAR] == 201
    assert counts[ReadingStatus.LOST] == 119
    assert counts[ReadingStatus.RESTORED] == 0
    ntok = sum(len(d.tokens) for d in c)
    nwords = sum(len(d.words) for d in c)
    assert (len(c), ntok, nwords) == (
        facts["documents"], facts["tokens"], facts["words"]
    )


def test_no_unread_position_reaches_the_sign_stream():
    """The class, stated over every Aegean corpus that loads offline (and SigLA when
    it is cached): a token the sign rule admits carries a recorded decomposition, so
    ``_sign_labels`` never has to read a sign out of a token's transliteration and no
    editorial marker can enter a count that way."""
    corpus_ids = ["lineara", "linearb", "cypriot", "cyprominoan"]
    if _SIGLA_CACHED:
        corpus_ids.append("sigla")
    for corpus_id in corpus_ids:
        c = aegean.load(corpus_id)
        offenders = [
            (d.id, t.text) for d in c for t in d.tokens if _bears_signs(t) and not t.signs
        ]
        assert offenders == [], f"{corpus_id}: {offenders[:5]}"
