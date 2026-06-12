"""Parity with the workbench signPattern.ts golden behavior."""

from aegean.analysis.patterns import (
    compile_sign_pattern,
    match_sign_pattern,
    word_matches_sign_pattern,
)


def test_compile():
    p = compile_sign_pattern("ra2-ro")
    assert p is not None and p.tokens == ("RA2", "RO") and not p.has_double_star
    assert compile_sign_pattern("KU-**").has_double_star  # type: ignore[union-attr]
    assert compile_sign_pattern("") is None


def test_single_wildcard():
    p = compile_sign_pattern("KU-*-RO")
    assert p is not None
    assert match_sign_pattern(["KU", "NE", "RO"], p)
    assert not match_sign_pattern(["KU", "RO"], p)
    assert match_sign_pattern(["RA₂", "RO"], compile_sign_pattern("RA2-RO"))  # subscript fold


def test_double_wildcard():
    p = compile_sign_pattern("KU-**")
    assert match_sign_pattern(["KU", "NE", "RO"], p)
    assert match_sign_pattern(["KU"], p)
    assert not match_sign_pattern(["DA", "RO"], p)
    pr = compile_sign_pattern("**-RO")
    assert match_sign_pattern(["KU", "NE", "RO"], pr)
    assert not match_sign_pattern(["KU", "NE"], pr)


def test_word_matches():
    assert word_matches_sign_pattern("KU-NE-RO", "KU-*-RO")
    assert not word_matches_sign_pattern("KU-RO", "KU-*-RO")
    assert word_matches_sign_pattern("KU-RO", "**")
    assert not word_matches_sign_pattern("KU", "**")  # single-sign word
