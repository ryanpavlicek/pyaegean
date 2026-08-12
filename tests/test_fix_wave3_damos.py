"""The DAMOS Linear B classifier separates the edition's apparatus from its readings.

A Mycenaean edition prints its own notation inside the transliteration line: the Leiden
brackets, and Latin abbreviations for the state of the object (``mut.`` mutila, ``vest.``
vestigia, ``vac.`` vacat, ``v.`` verso). None of it is a sign the scribe wrote, so none of
it may reach a sign frequency, dispersion, or keyness table. The qualified ideograms
(``OVIS:m`` the ram, ``TELA;1`` the first cloth variant) are the opposite case: real
logograms that the plain ideogram pattern could not match.

The fixtures quote DAMOS content verbatim, so the classifier is exercised on the shapes the
published edition actually uses.
"""

from __future__ import annotations

import json

import pytest

import aegean
import aegean.data as data
from aegean.analysis.accounting import is_checkable_account
from aegean.analysis.stats import _bears_signs, _items_of
from aegean.core.model import ReadingStatus, TokenKind
from aegean.scripts.linearb.loader import classify

# ── the apparatus ───────────────────────────────────────────────────────────────

# Markers that say the text at this position is destroyed or was not read.
LOST_MARKERS = [
    "mut.",         # mutila — the surface is mutilated
    "mutila",
    "vest.",        # vestigia — traces of signs, not read
    "vestigia",
    "deest",        # missing
    "[",            # Leiden lacuna: text lost after
    "]",            # Leiden lacuna: text lost before
    "?",            # an element the editor could not read
]
# Markers that record something else about the object, where no text is missing.
NOTATION_MARKERS = [
    "vac.",         # vacat — the scribe left the space blank
    "vacat",
    "v.",           # verso
    "r.",           # recto
    "v.↓",          # verso, written downwards
    "v.→",
    "sup.",         # superne — above
    "inf.",         # inferne — below
    "supra",
    "lat.",         # latus — a side of the object
    "sin.",
    "dex.",
    "sigillum",     # a seal impression
    "graffito",
    "fragmentum",
    "separatum",
    "angustum",
    "reliqua",
    "pars",
    "sine",
    "regulis",
    "prior",
    "⟦",            # an erasure delimiter: the deleted text is given by its own tokens
    "⟧",
]


@pytest.mark.parametrize("text", LOST_MARKERS + NOTATION_MARKERS)
def test_apparatus_is_never_a_sign(text: str) -> None:
    """No editorial marker reaches the sign stream, and none claims to be signs."""
    token = classify(text, 0, 0)
    assert token.text == text, "the marker stays in the text stream"
    assert token.signs == (), f"{text!r} contributed sign labels"
    assert not _bears_signs(token), f"{text!r} still counts as a sign"
    assert token.annotations["apparatus"], f"{text!r} carries no expansion"


@pytest.mark.parametrize("text", LOST_MARKERS)
def test_a_marker_for_missing_text_reads_lost(text: str) -> None:
    token = classify(text, 0, 0)
    assert token.status is ReadingStatus.LOST
    assert token.kind is TokenKind.UNKNOWN


@pytest.mark.parametrize("text", NOTATION_MARKERS)
def test_a_marker_for_present_text_does_not_claim_damage(text: str) -> None:
    """A vacat, a side label, or an erasure delimiter loses nothing: claiming ``LOST``
    would report damage the edition does not."""
    token = classify(text, 0, 0)
    assert token.status is ReadingStatus.CERTAIN
    assert token.kind is TokenKind.SEPARATOR


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("]vest.[", "vestigia — traces of signs, not read"),
        ("]vest.", "vestigia — traces of signs, not read"),
        ("vest.[", "vestigia — traces of signs, not read"),
        ("]vest.?[", "vestigia — traces of signs, not read"),
        ("⟦vest.⟧", "vestigia — traces of signs, not read"),
        ("]⟦vest.⟧[", "vestigia — traces of signs, not read"),
        ("ṃụṭ.", "mutila — mutilated"),          # underdotted: damaged but legible
        ("mut.?", "mutila — mutilated"),
        ("]vac.[", "vacat — space left blank"),
        ("[vest.]", "vestigia — traces of signs, not read"),
        ("]deest[", "missing"),
    ],
)
def test_brackets_underdots_and_queries_resolve_to_the_bare_marker(
    text: str, expected: str
) -> None:
    token = classify(text, 0, 0)
    assert token.annotations["apparatus"] == expected
    assert not _bears_signs(token)


def test_a_lacuna_bracket_is_lost_but_an_erasure_bracket_is_not() -> None:
    """``⟦ 40 o 33 ⟧`` gives the erased reading in the tokens between the delimiters,
    so the delimiter itself preserves everything; ``]`` says text is gone."""
    assert classify("]", 0, 0).status is ReadingStatus.LOST
    assert classify("⟧[", 0, 0).status is ReadingStatus.LOST  # a lacuna opens after it
    assert classify("⟦", 0, 0).status is ReadingStatus.CERTAIN
    assert classify("⟧", 0, 0).status is ReadingStatus.CERTAIN


# ── readings must be untouched ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("a-mi-ni-so-de", TokenKind.WORD),
        ("de-u-ki-jo-jo", TokenKind.WORD),
        ("to-so", TokenKind.WORD),          # the Linear B total marker
        ("ka-ra-re-we", TokenKind.WORD),
        ("OLE+WE", TokenKind.LOGOGRAM),
        ("VIR", TokenKind.LOGOGRAM),
        ("*146", TokenKind.LOGOGRAM),
        ("pa", TokenKind.UNKNOWN),          # a single syllabogram, still a sign
        ("o", TokenKind.UNKNOWN),           # o = o-pe-ro, the deficit abbreviation
    ],
)
def test_a_reading_is_not_taken_for_apparatus(text: str, kind: TokenKind) -> None:
    token = classify(text, 0, 0)
    assert token.kind is kind
    assert token.annotations.get("apparatus") is None
    assert _bears_signs(token), f"{text!r} stopped counting as a sign"


@pytest.mark.parametrize("text", ["18", "38", "1"])
def test_a_transcribed_numeral_stays_a_numeral(text: str) -> None:
    """Numerals were already outside the sign stream, by kind; nothing about them moves."""
    token = classify(text, 0, 0)
    assert token.kind is TokenKind.NUMERAL
    assert token.signs == (text,)
    assert token.annotations.get("apparatus") is None


def test_an_editorially_restored_reading_still_carries_its_signs() -> None:
    token = classify("[KO]", 0, 0)
    assert token.status is ReadingStatus.RESTORED
    assert token.signs == ("KO",)
    assert _bears_signs(token)


# ── the qualified ideograms ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "OVIS:m",     # the sex of the animal: m male, f female, x not determined
        "OVIS:f",
        "OVIS:x",
        "CAP:f",      # goat
        "CAP:m",
        "BOS:m",      # ox
        "BOS:f",
        "SUS:f",      # pig
        "SUS:m",
        "EQU:f",      # equid
        "TELA;1",     # the numbered variant of the cloth ideogram
        "TELA;2",
        "TELA;x",
        "TELA;1+TE",  # a qualified ideogram ligatured with a syllabogram
        "TELA;3+PU",
        "*146;2",     # a sign known only by its number, with a variant
        "OVIS:m[",    # a lacuna opens right after the ideogram
        "OVIS[:m",    # …or between the label and its qualifier
    ],
)
def test_a_qualified_ideogram_is_a_logogram(text: str) -> None:
    token = classify(text, 0, 0)
    assert token.kind is TokenKind.LOGOGRAM, f"{text!r} was not read as a logogram"
    assert token.signs == (text,), "a qualified ideogram is one sign, label and qualifier"
    assert _bears_signs(token)


def test_the_sex_qualifier_keeps_the_ideogram_one_sign() -> None:
    """``OVIS:m`` is one written sign, distinct from the unqualified ``OVIS``."""
    ram, sheep = classify("OVIS:m", 0, 0), classify("OVIS", 0, 0)
    assert ram.signs == ("OVIS:m",) and sheep.signs == ("OVIS",)
    assert ram.kind is sheep.kind is TokenKind.LOGOGRAM


@pytest.mark.parametrize("text", [":", ";", "OVIS:", "TELA;", "ki-ri-ti-jo-jo"])
def test_the_qualifier_pattern_does_not_invent_logograms(text: str) -> None:
    assert classify(text, 0, 0).kind is not TokenKind.LOGOGRAM


# ── whole-corpus behaviour, on verbatim DAMOS content ───────────────────────────

# KN Ce 144 (124-B) and PY Fr 1184, quoted from the published DAMOS transliterations.
KN_CE_144 = ".0        sup. mut.\n.1        e-re-pa-ṛọ     BOS   ZE  [\n.2        a-pa-ta-ẉạ [\n.3              ]vest. [\n           inf. mut."
PY_FR_1184 = (
    ".1          ko-ka-ro  ,  a-pe-do-ke  ,  e-ra3-wo  ,  to-so\n"
    ".2        e-u-me-de-i                              OLE+WE   18\n"
    ".3        pa-ro  ,  i-pe-se-wa  ,  ka-ra-re-we   38\n"
    ".4                                                              vac."
)
# The same account, mutilated above — the edition now reports lost text.
PY_FR_1184_MUTILATED = ".0        sup. mut.\n" + PY_FR_1184
# One flock line, all four qualified-ideogram shapes.
FLOCK = ".1   ki-ri-ti-jo-jo  OVIS:m  6  OVIS:f  2  TELA;1+TE  1  *146;2  4"


def _corpus(tmp_path, monkeypatch, contents: dict[str, str]):
    payload = {
        "_meta": {"version": 2, "generated": "2026-06-11", "document_count": len(contents)},
        "documents": [
            {"id": str(i), "heading": heading, "site": "Knossos", "content": content}
            for i, (heading, content) in enumerate(contents.items(), start=1)
        ],
    }
    path = tmp_path / "damos-corpus.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: path if name == "damos-corpus" else None)
    return aegean.read_corpus("damos")


def test_apparatus_never_reaches_the_sign_table(tmp_path, monkeypatch) -> None:
    corpus = _corpus(tmp_path, monkeypatch, {"KN Ce 144": KN_CE_144, "PY Fr 1184": PY_FR_1184})
    signs = [s for d in corpus.documents for s in _items_of(d, "signs")]
    for marker in ("sup.", "inf.", "mut.", "vest.", "vac.", "[", "]", "]vest."):
        assert marker not in signs, f"{marker!r} is being counted as a sign"
    # the readings on the same tablets survive intact
    assert {"e", "re", "pa", "ṛọ", "BOS", "ZE"} <= set(signs)
    assert {"ko", "ka", "ro", "OLE+WE"} <= set(signs)


def test_the_token_set_is_unchanged_only_its_classification(tmp_path, monkeypatch) -> None:
    """Classification moves kind and status, never the tokens themselves: the document,
    token, and word counts recorded for DAMOS must not move."""
    corpus = _corpus(tmp_path, monkeypatch, {"KN Ce 144": KN_CE_144, "PY Fr 1184": PY_FR_1184})
    tokens = [t for d in corpus.documents for t in d.tokens]
    assert len(corpus.documents) == 2
    assert len(tokens) == 29
    assert sum(1 for t in tokens if t.kind is TokenKind.WORD) == 10
    # every apparatus token is still present, in its original position
    assert [t.text for t in corpus.documents[0].tokens[:2]] == ["sup.", "mut."]
    assert corpus.documents[1].tokens[-1].text == "vac."


def test_qualified_ideograms_are_visible_to_logogram_aware_operations(
    tmp_path, monkeypatch
) -> None:
    corpus = _corpus(tmp_path, monkeypatch, {"KN Dk 1": FLOCK})
    logograms = [t.text for t in corpus.documents[0].logograms]
    assert logograms == ["OVIS:m", "OVIS:f", "TELA;1+TE", "*146;2"]


def test_a_blank_stretch_does_not_disqualify_an_intact_account(
    tmp_path, monkeypatch
) -> None:
    """A ``vacat`` is not damage, so an otherwise securely read account stays checkable;
    a ``mut.`` on the same account is damage, and disqualifies it."""
    corpus = _corpus(
        tmp_path,
        monkeypatch,
        {"PY Fr 1184": PY_FR_1184, "PY Fr 1184 mut": PY_FR_1184_MUTILATED},
    )
    intact, mutilated = corpus.documents
    assert is_checkable_account(intact)
    assert not is_checkable_account(mutilated)
