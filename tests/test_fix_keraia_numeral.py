"""Regression: a Milesian numeral stays one token regardless of NFC.

The trailing keraia U+0374 (a numeral such as "delta-keraia" = 4) sits in the
Greek block, so raw text kept the numeral whole; but NFC folds U+0374 to U+02B9,
which is outside that block, so the mandated-canonical form used to split it into
the letter plus the sign (2 tokens vs 3). The numeral now stays one token in both
forms. Milesian numerals are common in exactly the dated/documentary Greek the
neural preprocessing targets.

Keeping the numeral whole must not reintroduce the elided-coordinator confusion
(the numeral looking like an elided "de") fixed in 0.44.0, so the coordinator
guard below is part of the fix.
"""

from __future__ import annotations

import unicodedata

from aegean.core.model import TokenKind
from aegean.greek import tokenize
from aegean.greek.documentary import COORDINATORS, coordinator_norm

KERAIA = "ʹ"        # GREEK NUMERAL SIGN (trailing); NFC-folds to U+02B9
KERAIA_NFC = "ʹ"    # MODIFIER LETTER PRIME, the NFC image of the keraia
LOWER_KERAIA = "͵"  # GREEK LOWER NUMERAL SIGN (leading thousands); NFC-stable
DELTA = "δ"         # δ
ALPHA = "α"         # α


def _texts(text: str) -> list[str]:
    return [token.text for token in tokenize(text)]


def test_trailing_keraia_numeral_is_one_token_in_both_normalizations() -> None:
    raw = "ἔτους " + DELTA + KERAIA          # "year 4"
    nfc = unicodedata.normalize("NFC", raw)
    assert raw != nfc  # NFC really does change the keraia here

    assert _texts(raw) == ["ἔτους", DELTA + KERAIA]
    assert _texts(nfc) == ["ἔτους", DELTA + KERAIA_NFC]
    # The point of the fix: the same numeral, one token either way (not 3).
    assert len(_texts(raw)) == len(_texts(nfc)) == 2

    numeral = tokenize(nfc)[1]
    assert numeral.kind is TokenKind.WORD


def test_leading_lower_keraia_thousands_is_one_token() -> None:
    raw = "ἔτους " + LOWER_KERAIA + ALPHA  # 1000
    nfc = unicodedata.normalize("NFC", raw)
    assert _texts(raw) == _texts(nfc) == ["ἔτους", LOWER_KERAIA + ALPHA]


def test_keraia_numeral_is_never_read_as_an_elided_coordinator() -> None:
    # The elided "de" (delta + apostrophe) is a coordinator; the numeral is not,
    # in either normalization.
    assert coordinator_norm(DELTA + "'") in COORDINATORS
    for numeral in (DELTA + KERAIA, DELTA + KERAIA_NFC):
        assert coordinator_norm(numeral) not in COORDINATORS
