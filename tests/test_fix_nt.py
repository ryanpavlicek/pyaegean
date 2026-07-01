"""Regression tests for the NT loader fixes (aegean.scripts.greek.nt).

Three fixes, each with an output-verifying test:

1. ``robinson_to_upos``: suffixed closed-class tags (``PRT-N``, ``CONJ-N``, ``ADV-I``,
   ``COND-K``, ...) mapped to ``X`` because only the bare tags were in the lookup and the
   multi-letter prefixes missed the single-letter prefix map. A suffix marks a subtype
   (negative, interrogative, ...), never a different word class, so the bare tag decides.
   Before the fix 3,767 of 137,779 corpus tokens carried ``upos='X'``; after it only the
   201 genuinely unmappable ARAM/HEB tokens do.
2. ``load_nt`` NFC-normalizes token text / lemma / normalized form at load time (the
   source edition mixes oxia and tonos precomposition; the rest of the library is NFC).
3. The offline fallback names the bundled sample and the fetch failure when a valid
   book outside the sample is requested, instead of a generic "no text matched"."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from aegean import data, greek
from aegean.data import DataNotAvailableError
from aegean.scripts.greek.nt import _BARE_UPOS, robinson_to_upos

# Precomposed oxia forms (as stored in the source data) and their NFC (tonos)
# versions, spelled with explicit escapes so the file itself cannot be NFC-folded.
_KAI_OXIA = "καί"    # κα + iota-with-oxia: not NFC
_KAI_NFC = "καί"     # κα + iota-with-tonos: the NFC form
_ARCHE_OXIA = "ἀρχή"  # ἀρχ + eta-with-oxia
_ARCHE_NFC = "ἀρχή"   # ἀρχ + eta-with-tonos
assert _KAI_OXIA != _KAI_NFC
assert unicodedata.normalize("NFC", _KAI_OXIA) == _KAI_NFC

_ASSET = {
    "_meta": {"name": "Test NT", "version": 1, "document_count": 1},
    "documents": [
        {"id": "John 1", "book": "John", "chapter": 1, "name": "John 1", "tokens": [
            {"t": "Οὐκ", "v": 1, "lemma": "οὐ", "morph": "PRT-N", "strongs": "3756", "norm": "οὐκ"},
            {"t": _KAI_OXIA, "v": 1, "lemma": _KAI_OXIA, "morph": "CONJ", "strongs": "2532", "norm": _KAI_OXIA},
            {"t": _ARCHE_OXIA, "v": 1, "lemma": _ARCHE_OXIA, "morph": "N-DSF", "strongs": "746", "norm": _ARCHE_OXIA},
        ]},
    ],
}


@pytest.fixture()
def fetched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the loader's fetch('nt-corpus') at a synthetic on-disk asset (no network)."""
    p = tmp_path / "nt-corpus.json"
    p.write_text(json.dumps(_ASSET, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: p if name == "nt-corpus" else None)
    return p


@pytest.fixture()
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make fetch('nt-corpus') fail, forcing the bundled one-book (Phlm) sample."""
    def _fail(name: str, **k: object) -> Path:
        raise DataNotAvailableError(f"{name} unavailable (test: simulated offline)")

    monkeypatch.setattr(data, "fetch", _fail)


# --- fix 1: suffixed closed-class Robinson tags -------------------------------------


def test_suffixed_closed_class_tags() -> None:
    # The exact tags that made up the 3,566 wrongly-X tokens in the full corpus.
    assert robinson_to_upos("PRT-N") == "PART"    # οὐ / μή, 2,701 tokens
    assert robinson_to_upos("PRT-I") == "PART"
    assert robinson_to_upos("CONJ-N") == "CCONJ"
    assert robinson_to_upos("CONJ-P") == "CCONJ"
    assert robinson_to_upos("COND-K") == "SCONJ"
    for suffix in ("I", "N", "S", "C", "K"):
        assert robinson_to_upos(f"ADV-{suffix}") == "ADV"


def test_suffix_never_changes_word_class() -> None:
    # Property: for every bare closed-class tag, any '-'-suffix maps to the same UPOS.
    for bare, upos in _BARE_UPOS.items():
        for suffix in ("N", "I", "S", "C", "K", "ATT"):
            assert robinson_to_upos(f"{bare}-{suffix}") == upos, f"{bare}-{suffix}"


def test_aram_heb_stay_x() -> None:
    assert robinson_to_upos("ARAM") == "X"
    assert robinson_to_upos("HEB") == "X"
    assert robinson_to_upos("") == "X"            # no tag at all stays unmappable


def test_open_class_and_bare_tags_unchanged() -> None:
    # The pre-fix mappings the fix must not disturb.
    assert robinson_to_upos("N-NSF") == "NOUN"
    assert robinson_to_upos("V-AAI-3S") == "VERB"
    assert robinson_to_upos("T-ASM") == "DET"
    assert robinson_to_upos("A-NSM") == "ADJ"
    assert robinson_to_upos("P-GSM") == "PRON"
    assert robinson_to_upos("N-PRI") == "PROPN"
    assert robinson_to_upos("A-NUI") == "NUM"
    assert robinson_to_upos("CONJ") == "CCONJ"
    assert robinson_to_upos("PREP") == "ADP"
    assert robinson_to_upos("PRT") == "PART"
    assert robinson_to_upos("COND") == "SCONJ"
    assert robinson_to_upos("INJ") == "INTJ"


def test_negative_particle_in_loaded_corpus(fetched: Path) -> None:
    doc = greek.load_nt("John").documents[0]
    ouk = doc.tokens[0]
    assert ouk.annotations["morph"] == "PRT-N"
    assert ouk.annotations["upos"] == "PART"      # was 'X' before the fix


# --- fix 2: NFC normalization at load time -------------------------------------------


def test_load_nt_emits_nfc(fetched: Path) -> None:
    doc = greek.load_nt("John").documents[0]
    kai, arche = doc.tokens[1], doc.tokens[2]
    # Byte-exact: the oxia precompositions come out as the tonos (NFC) forms.
    assert kai.text == _KAI_NFC
    assert kai.annotations["lemma"] == _KAI_NFC
    assert kai.annotations["normalized"] == _KAI_NFC
    assert arche.text == _ARCHE_NFC
    assert arche.annotations["lemma"] == _ARCHE_NFC


def test_bundled_sample_is_nfc(offline: None) -> None:
    # The raw bundled JSON holds 225 non-NFC lemmas and 95 non-NFC token texts;
    # the loader must fold every one of them.
    doc = greek.load_nt("Philemon").documents[0]
    assert len(doc.tokens) > 100
    for tok in doc.tokens:
        for s in (tok.text, tok.annotations["lemma"], tok.annotations["normalized"]):
            assert unicodedata.normalize("NFC", s) == s, repr(s)


def test_nt_eval_sees_nfc_gold(fetched: Path) -> None:
    """A gold-echo tagger keyed on NFC forms scores 1.0: the eval's inputs are NFC."""
    gold = {
        "οὐκ": ("οὐ", "PART"),
        _KAI_NFC: (_KAI_NFC, "CCONJ"),
        _ARCHE_NFC: (_ARCHE_NFC, "NOUN"),
    }

    def tag(forms: list[str]) -> list[tuple[str, str]]:
        return [gold[f] for f in forms]           # KeyError if any form is non-NFC

    r = greek.evaluate_on_nt(tag, corpus=greek.load_nt("John"))
    assert r["lemma"] == 1.0 and r["upos"] == 1.0 and r["n"] == 3


# --- fix 3: the offline-fallback error -----------------------------------------------


def test_offline_missing_book_names_the_sample(offline: None) -> None:
    with pytest.raises(ValueError, match=r"not in the bundled offline sample.*Phlm"):
        greek.load_nt("Matthew")


def test_offline_unknown_book_message_unchanged(offline: None) -> None:
    with pytest.raises(ValueError, match="unknown NT book"):
        greek.load_nt("Habakkuk")


def test_offline_empty_ref_in_sample_book(offline: None) -> None:
    # Philemon has one chapter: an out-of-range ref keeps the accurate generic message.
    with pytest.raises(ValueError, match="no New Testament text matched"):
        greek.load_nt("Philemon", ref="9")


def test_offline_bundled_book_still_loads(offline: None) -> None:
    c = greek.load_nt("Philemon")
    assert c.documents[0].id == "Phlm 1" and len(c.documents[0].tokens) > 100
