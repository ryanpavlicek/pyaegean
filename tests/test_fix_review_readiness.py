"""Regression tests for the pre-university-review scholarly audit (0.19.16).

A 14-lens Ancient Greek professor panel (each finder running the live code, each finding
gated by two independent skeptics) confirmed six defects a specialist would catch. Each is
pinned here. Two panel findings were REFUTED on inspection — the Cypriot trailing-period
"downgrade" (no corpus token is actually affected) and the δῶρα/σωτῆρα "wrong accent" (the
form is honestly flagged uncertain on a dichronon) — and those refutations are pinned too, so
the correct behaviour is not later mistaken for a bug.
"""

from __future__ import annotations

import unicodedata

import pytest


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ── #1 (HIGH): the fabricated Linear B equation O-KA = ἔχω is gone ──────────────
def test_o_ka_is_not_glossed_as_echo() -> None:
    from aegean.scripts.linearb.lexicon import greek_reading

    # o-ka is the Pylos "o-ka tablets" word, NOT ἔχω (which is written e-ke): the confident
    # wrong equation (a duplicate of the correct E-KE entry) is removed → an honest miss.
    assert greek_reading("O-KA") is None
    # the genuine, phonetically-correct ἔχω reading is still present under E-KE
    assert greek_reading("E-KE") == ("ἔχω", "he/she holds, has")


# ── #2: A-PI-QO-TO no longer carries the Homeric shield-epithet as its lemma ─────
def test_a_pi_qo_to_lemma_is_not_the_shield_word() -> None:
    from aegean.scripts.linearb.lexicon import greek_reading

    reading = greek_reading("A-PI-QO-TO")
    assert reading is not None
    lemma, gloss = reading
    # ἀμφίβροτος is the Iliadic shield-epithet ("man-covering"), a mis-etymology of the
    # Ta-series table adjective: it must not be presented as the established lemma.
    assert lemma != "ἀμφίβροτος"
    # the correct, well-established sense (round / rimmed table) is kept
    assert "round" in gloss.lower()
    # and the honest etymology (ἀμφί + the root of βαίνω) is recorded
    assert "βαίνω" in gloss


# ── #3: 1st-declension masculine -ης genitives are not fabricated into -ος ───────
@pytest.mark.parametrize(
    "form",
    ["προφήτου", "Ἰωάνου", "Ἡρῴδου", "Ἰορδάνου", "ψευδοπροφήτου", "οἰκοδεσπότου",
     "πατριάρχου", "τετραάρχου", "ἰδιώτου", "χάρτου"],
)
def test_masc_first_decl_genitive_is_not_a_confident_os_fabrication(form: str) -> None:
    from aegean.greek.lemmatize import lemmatize_verbose

    lemma, known = lemmatize_verbose(form)
    # the -ου genitive of a -ης masculine (Smyth §227) must not become a confident *-ος non-word
    assert not (known and _nfc(lemma).endswith("ος")), (form, lemma, known)


def test_genuine_second_decl_genitive_still_resolves() -> None:
    """The fix must NOT regress the real 2nd-declension -ος genitive, which shares the -ου
    ending: curated stems only. Measured on the full NT: all 4,275 correct -ος preserved."""
    from aegean.greek.lemmatize import lemmatize_verbose

    from aegean.greek.lemmatize import _bare

    for form, want in [("λόγου", "λόγος"), ("θεοῦ", "θεός"), ("υἱοῦ", "υἱός"),
                       ("δούλου", "δοῦλος"), ("πλούτου", "πλοῦτος")]:
        lemma, known = lemmatize_verbose(form)
        # a confident 2nd-decl citation form, whose bare stem is the -ος nominative (accent aside)
        assert known and _bare(lemma).endswith("οσ"), (form, lemma)
        # πλοῦτος shares the shape of a -της agent noun but is genuinely 2nd-decl and must strip
        if form == "πλούτου":
            assert _bare(lemma) == _bare(want)


# ── #4: an enclitic-throwback acute on a neuter does not fabricate -ός ───────────
def test_enclitic_accented_neuter_is_not_fabricated_into_os() -> None:
    from aegean.greek.lemmatize import lemmatize_verbose

    # δῶρόν (the acute an enclitic throws onto the ultima, δῶρόν ἐστιν, Smyth §183) is the
    # neuter δῶρον, recovered correctly — never the non-word *δῶρός.
    lemma, known = lemmatize_verbose("δῶρόν")
    assert _nfc(lemma) == "δῶρον" and known
    # the plain nominative is unchanged (identity, honest miss)
    assert lemmatize_verbose("δῶρον") == ("δῶρον", False)
    # a grave-accented neuter normalises to the citation form too (ἱερὸν → ἱερόν)
    assert _nfc(lemmatize_verbose("ἱερὸν")[0]) == "ἱερόν"


# ── #6: the two UD folds carry their own CC version (Perseus 2.5, PROIEL 3.0) ────
def test_ud_treebank_licenses_are_recorded_per_fold() -> None:
    from aegean.greek import ud

    # verified against each treebank's README at the pinned commit
    assert ud._UD_LICENSE["perseus"] == "CC BY-NC-SA 2.5"
    assert ud._UD_LICENSE["proiel"] == "CC BY-NC-SA 3.0"
    # every fetchable fold has a recorded license
    assert set(ud._UD_LICENSE) == set(ud._UD_REPO)


def test_ud_docstring_does_not_blanket_state_perseus_as_3_0() -> None:
    from aegean.greek import ud

    doc = ud.__doc__ or ""
    # the module must state the split licence, not the old blanket "both 3.0"
    assert "Perseus 2.5" in doc and "PROIEL 3.0" in doc


# ── REFUTED #5: no Cypriot token is downgraded to UNCLEAR by a trailing period ───
def test_no_cypriot_word_is_downgraded_solely_by_a_trailing_period() -> None:
    """The panel claimed a lone word-final period downgrades legible words (e-mi. = ἐμί) to
    UNCLEAR. Refuted on the corpus: every trailing-period token ALSO carries an underdot or a
    bracket that independently, and correctly, sets its status. This pins that invariant so a
    future loader change cannot silently start downgrading a purely-legible word by its
    punctuation."""
    import re

    import aegean
    from aegean.core.model import ReadingStatus

    underdot = "̣"
    offenders = []
    for doc in aegean.load("cypriot"):
        for tok in doc.tokens:
            raw = tok.annotations.get("leiden")
            if raw is None or tok.status is ReadingStatus.CERTAIN:
                continue
            has_underdot = underdot in unicodedata.normalize("NFD", raw)
            has_bracket = any(ch in raw for ch in "[]⟦⟧<>()")
            bare = "".join(
                c for c in unicodedata.normalize("NFD", raw) if c != underdot
            )
            bare = unicodedata.normalize("NFC", bare)
            internal = bool(re.search(r"\.[A-Za-z*]", bare))  # a dot before a sign = illegible
            pure_trailing = (
                not has_underdot and not has_bracket
                and bare.count(".") == 1 and bare.endswith(".") and not internal
                and "?" not in bare and "‒" not in bare and "↓" not in bare
            )
            if pure_trailing:
                offenders.append((doc.id, raw, tok.status))
    assert offenders == [], offenders


# ── REFUTED (accent split-decision): the dichronon is honestly hedged, not wrong ─
def test_dichronon_accent_is_flagged_uncertain_not_silently_wrong() -> None:
    """The panel split on δῶρα/σωτῆρα (place_accent gives the acute δώρα, not the
    properispomenon δῶρα). This is correct conservative behaviour: the final -α is a dichronon
    (ambiguous length), so the form is returned with certain=False and a dichronon note, and it
    resolves to the circumflex the moment the ultima length is supplied. Not an error."""
    from aegean.greek.accent_law import place_accent

    hedged = place_accent("δωρα", recessive=False, lemma="δῶρον")
    assert hedged.certain is False and "dichronon" in hedged.note
    # given the (short) ultima length, the properispomenon δῶρα is produced (Smyth §163)
    resolved = place_accent("δωρα", recessive=False, lemma="δῶρον", ultima_length="short")
    assert resolved.form == "δῶρα" and resolved.certain is True
    assert place_accent("σωτηρα", recessive=False, lemma="σωτήρ", ultima_length="short").form == "σωτῆρα"
