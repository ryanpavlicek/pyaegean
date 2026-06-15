"""Scribal-hand analysis (aegean.analysis.scribal): hand profiles + per-hand keyness."""

from __future__ import annotations

import pytest

from aegean.analysis import HandProfile, hand_keyness, scribal_hands
from aegean.core.corpus import Corpus


def _corpus() -> Corpus:
    return Corpus.from_records(
        [
            {"id": "t1", "text": "DA-RE DA-RE WA-DU", "meta": {"scribe": "117", "site": "KN", "period": "LM IIIA"}},
            {"id": "t2", "text": "DA-RE KU-RO", "meta": {"scribe": "117", "site": "KN"}},
            {"id": "t3", "text": "PO-TI A-DU", "meta": {"scribe": "103", "site": "PY"}},
            {"id": "t4", "text": "X Y", "meta": {}},  # no hand -> skipped
        ],
        script_id="linearb",
    )


def test_scribal_hands_profiles() -> None:
    profiles = scribal_hands(_corpus())
    assert [p.hand for p in profiles] == ["117", "103"]   # by tablet count desc
    h = profiles[0]
    assert isinstance(h, HandProfile)
    assert h.doc_count == 2 and h.word_count == 5
    assert h.sites == {"KN": 2}
    assert h.periods == {"LM IIIA": 1}
    assert h.top_words[0] == ("DA-RE", 3)


def test_scribal_hands_min_docs() -> None:
    assert [p.hand for p in scribal_hands(_corpus(), min_docs=2)] == ["117"]


def test_hand_keyness_finds_characteristic_word() -> None:
    rows = hand_keyness(_corpus(), "117")
    by_item = {r.item: r for r in rows}
    assert "DA-RE" in by_item                     # 3x for hand 117, 0x elsewhere
    assert by_item["DA-RE"].log_ratio > 0         # overused in the target hand
    assert by_item["DA-RE"].reference_count == 0


def test_hand_keyness_unknown_hand_raises() -> None:
    with pytest.raises(ValueError, match="no documents attributed"):
        hand_keyness(_corpus(), "999")
