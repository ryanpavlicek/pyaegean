"""Cross-script phonetic comparison: the Greek romanizer + bridge comparisons (offline)."""

from __future__ import annotations

import pytest

from aegean.analysis import compare


# ── romanize_greek ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("greek", "expected"),
    [
        ("ποιμήν", "poimēn"),       # accents + η→ē
        ("βασιλεύς", "basileus"),   # final ς→s, diphthong kept (eu)
        ("πατήρ", "patēr"),
        ("θεός", "theos"),          # θ→th
        ("χθών", "khthōn"),         # χ→kh, ω→ō
        ("ξένος", "ksenos"),        # ξ→ks
        ("ψυχή", "psukhē"),         # ψ→ps, υ→u, χ→kh
        ("ἄγγελος", "angelos"),     # γ before γ = nasal
        ("σάλπιγξ", "salpinks"),    # γ before ξ = nasal
        ("ἄνθρωπος", "anthrōpos"),
    ],
)
def test_romanize_greek(greek, expected):
    assert compare.romanize_greek(greek) == expected


def test_romanize_greek_fold_aspiration():
    assert compare.romanize_greek("θεός", fold_aspiration=True) == "teos"
    assert compare.romanize_greek("χθών", fold_aspiration=True) == "ktōn"
    assert compare.romanize_greek("φιλόσοφος", fold_aspiration=True) == "pilosopos"


def test_romanize_greek_drops_breathing_and_passes_unknown():
    assert compare.romanize_greek("ἑν") == "en"     # rough breathing dropped
    assert compare.romanize_greek("abc") == "abc"   # non-Greek passes through


# ── to_phonemes dispatch ─────────────────────────────────────────────────────


def test_to_phonemes_per_script():
    assert compare.to_phonemes("po-me", "linearb") == "pome"
    assert compare.to_phonemes("pa-si-le-u-se", "cypriot") == "pasileuse"
    assert compare.to_phonemes("KU-RO", "lineara") == "kuro"
    assert compare.to_phonemes("θεός", "greek") == "theos"


def test_to_phonemes_rejects_undeciphered():
    with pytest.raises(ValueError, match="cyprominoan"):
        compare.to_phonemes("CM001", "cyprominoan")


# ── phonetic_compare ─────────────────────────────────────────────────────────


def test_compare_linearb_to_greek_bridge():
    cmp = compare.phonetic_compare("po-me", "linearb", "ποιμήν", "greek")
    assert cmp.phonemes_a == "pome" and cmp.phonemes_b == "poimēn"
    assert 0.0 < cmp.distance < 0.5
    assert cmp.similarity == pytest.approx(1.0 - cmp.distance)
    assert cmp.alignment[0].op == "match"  # p ~ p


def test_compare_labiovelar_reflex_is_a_far_sub():
    # qa-si-re-u 'basileus': the qʷ → b reflex is a "far" substitution at position 0
    cmp = compare.phonetic_compare("qa-si-re-u", "linearb", "βασιλεύς", "greek")
    assert cmp.alignment[0].a == "q" and cmp.alignment[0].b == "b"
    assert cmp.alignment[0].op == "sub-far"


def test_compare_cypriot_to_greek():
    cmp = compare.phonetic_compare("pa-si-le-u-se", "cypriot", "βασιλεύς", "greek")
    # Cypriot writes the final consonant, so it is closer than the Linear B form
    assert cmp.similarity > 0.75


def test_compare_fold_aspiration_helps_true_cognate():
    plain = compare.phonetic_compare("te-o", "linearb", "θεός", "greek")
    folded = compare.phonetic_compare("te-o", "linearb", "θεός", "greek", fold_aspiration=True)
    assert folded.distance < plain.distance  # θ→t aligns te-o with theos→teos


# ── nearest ──────────────────────────────────────────────────────────────────


def test_nearest_ranks_true_cognate_first():
    greek = ["ποιμήν", "βασιλεύς", "πατήρ", "θεός", "δοῦλος", "θυγάτηρ"]
    ranked = compare.nearest("qa-si-re-u", "linearb", greek, "greek", top=3, fold_aspiration=True)
    assert ranked[0][0] == "βασιλεύς"
    assert ranked[0][1] < ranked[1][1]  # strictly nearest
    assert len(ranked) == 3


def test_nearest_top_zero_returns_all_and_skips_unromanizable():
    out = compare.nearest("po-me", "linearb", ["ποιμήν", "πατήρ"], "greek", top=0)
    assert len(out) == 2
    assert [w for w, _ in out][0] == "ποιμήν"  # nearest first


# ── CLI ──────────────────────────────────────────────────────────────────────


def test_cli_compare_and_nearest():
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    runner = CliRunner()
    app = _build_app()
    r = runner.invoke(app, ["analyze", "compare", "po-me", "ποιμήν", "--json"])
    assert r.exit_code == 0, r.output
    assert '"similarity"' in r.output

    r2 = runner.invoke(
        app, ["analyze", "nearest", "qa-si-re-u", "greek", "--top", "5", "--json"]
    )
    assert r2.exit_code == 0, r2.output

    r3 = runner.invoke(app, ["analyze", "compare", "x", "y", "--script-a", "cyprominoan"])
    assert r3.exit_code == 1  # undeciphered script rejected
