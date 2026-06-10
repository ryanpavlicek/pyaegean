"""Tests for the Cypro-Minoan plugin (offline; sign data bundled from the Unicode UCD).

Cypro-Minoan is undeciphered, so the contract is deliberately small: a registered script, a sign
inventory with no phonetic values, sign-sequence tokenization, and a loadable illustrative sample.
"""

from __future__ import annotations

import aegean
from aegean.core.model import TokenKind
from aegean.core.script import get_script
from aegean.scripts.cyprominoan.inventory import cyprominoan_inventory


def test_registered() -> None:
    assert "cyprominoan" in aegean.registered_scripts()
    assert get_script("cyprominoan").name == "Cypro-Minoan"


def test_sign_inventory_is_undeciphered() -> None:
    signs = list(cyprominoan_inventory())
    assert len(signs) == 99
    assert all(s.phonetic is None for s in signs)  # undeciphered: no settled values
    cm001 = next(s for s in signs if s.label == "CM001")
    assert cm001.glyph and cm001.attrs["unicodeName"] == "CYPRO-MINOAN SIGN CM001"


def test_tokenize_sign_sequences() -> None:
    tokens = get_script("cyprominoan").tokenize("CM005-CM023-CM002 CM008")
    assert tokens[0].kind is TokenKind.WORD
    assert tokens[0].signs == ("CM005", "CM023", "CM002")
    assert tokens[1].kind is TokenKind.UNKNOWN  # a lone sign has no reading to resolve


def test_corpus_loads() -> None:
    corpus = aegean.load("cyprominoan")
    assert len(corpus) >= 1
    ids = {doc.id for doc in corpus}
    assert "cm-enkomi-ball" in ids
    doc = corpus.get("cm-enkomi-ball")
    assert doc.meta.site == "Enkomi"
    assert all(t.kind is TokenKind.WORD for t in doc.tokens)
