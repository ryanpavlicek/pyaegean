"""The headline data-layer contract for Linear A."""

import aegean


def test_load_count_and_inventory():
    c = aegean.load("lineara")
    assert len(c) == 1721
    assert c.script_id == "lineara"
    assert c.sign_inventory is not None and len(c.sign_inventory) == 84


def test_filter_and_word_frequencies():
    c = aegean.load("lineara")
    ht = c.filter(site="Haghia Triada")
    assert 0 < len(ht) < len(c)
    assert all(d.meta.site == "Haghia Triada" for d in ht)

    freqs = c.word_frequencies()
    assert freqs
    assert freqs[0][1] >= freqs[-1][1]  # sorted descending
    assert freqs[0][1] > 1              # the top word recurs


def test_registered_and_provenance_and_export():
    assert "lineara" in aegean.registered_scripts()
    c = aegean.load("lineara")
    assert "GORILA" in c.provenance.source
    assert c.provenance.cite()  # non-empty formatted citation

    d = c.to_dict()
    assert d["_meta"]["documentCount"] == 1721
    assert d["_meta"]["scriptId"] == "lineara"
    assert len(d["documents"]) == 1721


def test_tokenize_classifies_kinds():
    la = aegean.get_script("lineara")
    toks = la.tokenize("KU-RO 5 GRA")
    kinds = [t.kind.value for t in toks]
    assert kinds == ["word", "numeral", "logogram"]
    assert toks[0].signs == ("KU", "RO")
