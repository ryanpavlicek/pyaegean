"""Reconstructed IPA transcription (Attic + Koine).

Assertions are restricted to rock-solid, uncontroversial values for each period
(aspirates vs fricatives, breathing, the velar nasal, iotacism), not the
contested fine points (ε/η quality, the long diphthongs)."""

from __future__ import annotations

import pytest

from aegean.greek import to_ipa


@pytest.mark.parametrize(
    "word,ipa",
    [
        ("λόγος", "loɡos"),
        ("θεός", "tʰeos"),       # θ aspirated
        ("μῆνιν", "mɛːnin"),     # η long; circumflex
        ("ὁ", "ho"),             # rough breathing → /h/
        ("αὐτός", "au̯tos"),      # αυ diphthong
        ("ἄγγελος", "aŋɡelos"),  # γγ → velar nasal
        ("τῷ", "tɔː"),           # iota subscript → long
    ],
)
def test_attic_ipa(word, ipa):
    assert to_ipa(word) == ipa
    assert to_ipa(word, "attic") == ipa


@pytest.mark.parametrize(
    "word,ipa",
    [
        ("θεός", "θeos"),    # θ fricative in Koine
        ("φῶς", "fos"),      # φ → /f/
        ("βίος", "vios"),    # β → /v/
        ("χάρις", "xaris"),  # χ → /x/
        ("καί", "ke"),       # αι → /e/ (iotacism)
        ("ὁ", "o"),          # breathing lost in Koine
    ],
)
def test_koine_ipa(word, ipa):
    assert to_ipa(word, "koine") == ipa


def test_period_differs_for_aspirates():
    assert to_ipa("φθόνος", "attic").startswith("pʰtʰ")  # aspirated stops
    assert to_ipa("φθόνος", "koine").startswith("fθ")     # fricatives


def test_multiword_and_validation():
    assert to_ipa("ὁ λόγος") == "ho loɡos"
    with pytest.raises(ValueError, match="attic"):
        to_ipa("λόγος", "mycenaean")  # type: ignore[arg-type]
