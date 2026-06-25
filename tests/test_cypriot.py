"""Tests for the Cypriot syllabary plugin (offline; sign data bundled from the Unicode UCD)."""

from __future__ import annotations

import aegean
from aegean.core.script import get_script
from aegean.scripts.cypriot import gloss, greek_reading, word_to_phonetic
from aegean.scripts.cypriot.inventory import cypriot_inventory


def test_registered() -> None:
    assert "cypriot" in aegean.registered_scripts()
    assert get_script("cypriot").name == "Cypriot syllabary"


def test_sign_inventory() -> None:
    signs = list(cypriot_inventory())
    assert len(signs) == 55
    assert all(s.phonetic for s in signs)  # deciphered: every sign has a value
    ka = next(s for s in signs if s.label == "KA")
    assert ka.phonetic == "ka"
    xa = next(s for s in signs if s.label == "XA")
    assert xa.phonetic == "ksa"  # the x-series writes the /ks/ cluster (ξ)


def test_word_to_phonetic() -> None:
    assert word_to_phonetic("PA-SI-LE-U-SE") == "pasileuse"  # βασιλεύς
    assert word_to_phonetic("A-PO-LO-NI") == "apoloni"        # Ἀπόλλωνι, "to Apollo"


def test_greek_bridge() -> None:
    assert greek_reading("PA-SI-LE-U-SE") == ("βασιλεύς", "king")
    assert greek_reading("pa-si-le-u-se") == ("βασιλεύς", "king")  # case-insensitive
    assert gloss("TU-KA") == "fortune (Cypriot τύχα)"
    assert greek_reading("XX-YY") is None


def test_corpus_loads() -> None:
    corpus = aegean.load("cypriot")
    assert len(corpus) >= 100  # the IG XV 1 corpus plus the illustrative samples
    all_texts = {t.text for doc in corpus for t in doc.tokens}
    assert "O-NA-SI-LO-SE" in all_texts  # the illustrative sample is still present


def test_ig_corpus_present_and_attributed() -> None:
    corpus = aegean.load("cypriot")
    by_id = {doc.id: doc for doc in corpus}
    assert "IG XV 1, 1" in by_id
    doc = by_id["IG XV 1, 1"]
    assert doc.meta.site == "Amathus"
    assert any("telota.bbaw.de" in n for n in doc.meta.notes)  # CC-BY link-back per inscription
    prov = corpus.provenance
    assert "CC BY 4.0" in prov.license and "telota.bbaw.de" in prov.url
