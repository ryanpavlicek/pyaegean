"""Greek syllable quantity (metrical weight)."""

from __future__ import annotations

import pytest

from aegean.greek import scan, syllable_quantities

H, L, C = "heavy", "light", "common"


@pytest.mark.parametrize(
    "word,quantities",
    [
        ("λόγος", [L, H]),              # λό open short; γος closed (by position)
        ("ἄνθρωπος", [H, H, H]),        # ἄν closed; θρω long ω; πος closed
        ("μῆνιν", [H, H]),             # μῆ long (circumflex); νιν closed
        ("θάλασσα", [C, H, C]),        # ἄ/ἄ dichrona open; λασ closed
        ("ποικιλόθρον", [H, C, L, H]),  # ποι diphthong; κι common; λό short; θρον closed
        ("τῷ", [H]),                   # iota subscript → long
        ("ἀρχῇ", [H, H]),             # ἀρ closed; χῇ iota subscript long
    ],
)
def test_syllable_quantities(word, quantities):
    assert syllable_quantities(word) == quantities


def test_scan_pairs_syllables_with_quantities():
    assert scan("λόγος") == [("λό", L), ("γος", H)]


def test_diphthong_nucleus_is_heavy():
    # αυ is a diphthong → long; the open syllable is heavy on nucleus length
    assert syllable_quantities("αὐτος")[0] == H


def test_short_open_is_light_long_open_is_heavy():
    assert syllable_quantities("ε") == [L]   # bare short vowel, open
    assert syllable_quantities("ω") == [H]   # bare long vowel, open
    assert syllable_quantities("α") == [C]   # bare dichronon, open → common
